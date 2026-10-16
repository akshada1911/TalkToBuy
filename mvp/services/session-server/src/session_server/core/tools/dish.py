"""plan_dish: any dish -> ingredients with proper amounts -> catalogue packs -> a goal list on screen."""

import asyncio
import math
import re
from typing import Any

from session_server.core import goal
from session_server.core.runtime import Runtime
from session_server.core.tool_router import ToolError
from session_server.logging import get_logger
from session_server.models.domain import Product
from session_server.ports.planner import DishPlan, PlannedItem
from session_server.units.packs import PackOption, packs_needed
from session_server.units.parser import Amount

log = get_logger(__name__)

MAX_PACKS = 20  # the most packs of one product one list line may ask for
SEARCH_PARALLEL = 5
SEARCH_LIMIT = 12  # looked at on the server only, so more than the voice model sees
FILLER = {"fresh", "raw", "whole", "pure", "plain", "organic", "ripe", "dry", "dried", "chopped", "sliced"}
UNITS = {"g", "gm", "gms", "kg", "ml", "l", "ltr", "litre", "liter", "pc", "pcs", "piece", "pieces", "pack", "of"}
# Words in a product name that say nothing about what it is.
NOISE = {"value", "pack", "combo", "family", "premium", "special", "classic", "regular", "small", "large", "big", "mini"}
# Colour words that may be dropped from a need when the shop has the plain product ("red chilli powder").
COLOURS = {"red", "yellow"}
# Words that make a product something other than the raw ingredient (Garlic Pickle, Ginger Snap Cookies,
# Tomato Ketchup): such a product is only right when the need itself says so.
PROCESSED = {"pickle", "achar", "cookie", "biscuit", "snap", "chip", "juice", "squash", "jam", "sauce", "ketchup",
             "candy", "chocolate", "cake", "namkeen", "drink", "soda", "noodle", "instant", "ready", "flavour",
             "flavor", "spread", "cheese", "tea", "coffee", "butter", "powder", "paste", "flour", "puree", "pulp", "toffee", "wafer", "cracker", "bar", "shake", "syrup", "soup"}
# Over-buying up to half of what is needed is fine (a 250 g pack for 200 g); more than that is not.
OVERSHOOT_OK = 0.5


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[\w']+", text.lower()))


def _stem(word: str) -> str:
    """Plain plurals and spellings: tomatoes -> tomato, chillies and chilly -> chili, eggs -> egg."""
    if len(word) > 4 and word.endswith("oes"):
        word = word[:-2]
    elif len(word) > 4 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    if len(word) > 3 and word.endswith("y"):
        word = word[:-1] + "i"
    return re.sub(r"(.)\1+", r"\1", word)  # chilli -> chili, ghee -> ghe: both sides spelled alike


def _tokens(text: str) -> set[str]:
    return {_stem(t) for t in _norm(text).split() if len(t) > 1}


def _matches_on_hand(need: str, on_hand: list[str]) -> bool:
    n = _tokens(need)
    for phrase in on_hand:
        p = _tokens(phrase)
        if p and n and (p <= n or n <= p):
            return True
    return False


def _name_words(p: Product) -> set[str]:
    """The words that say WHAT the product is (no size, unit or brand): 'Garlic Pickle', not '200 g Double Horse'."""
    brand = _tokens(p.brand or "")
    return {t for t in _tokens(p.name) if not t.isdigit() and t not in UNITS and t not in NOISE and t not in brand}


def _pick_candidates(need: str, products: list[Product]) -> list[Product]:
    """In-stock products that really are this ingredient, and only those.

    Every word of the need must appear in the product, and among those the closest names win, so
    'garlic' finds Garlic (not Garlic Pickle) and 'ginger' never finds Ginger Snap Cookies. Better to
    say "not in the catalogue" than to put the wrong thing in the cart.
    """
    base = _tokens(need) - FILLER or _tokens(need)
    for words in (base, (base - {_stem(c) for c in COLOURS}) or base):  # exact words first, then without a colour
        covered = []
        for p in products:
            if not p.in_stock:
                continue
            if words <= _tokens(" ".join([p.name, p.local_name, *p.synonyms])):
                name = _name_words(p)
                if (name & {_stem(w) for w in PROCESSED}) - words:
                    continue
                covered.append((len(words & name) / max(1, len(name)), p))
        if covered:
            best = max(score for score, _ in covered)
            return [p for score, p in covered if score >= best - 0.01]
    return []


def _choose_packs(amount: Amount, candidates: list[Product]) -> tuple[str, int] | None:
    """The pack and count to buy: fewest packs that do not over-buy by more than half, else the least over-buy."""
    options = []
    for p in candidates:
        opt = PackOption(p.id, p.unit_qty, p.unit)
        packs = packs_needed(amount, opt)
        if packs is not None:
            options.append((packs, packs * p.unit_qty - amount.value, p.id))
    if not options:
        return None
    sensible = [o for o in options if o[1] <= OVERSHOOT_OK * amount.value]
    packs, _, pid = min(sensible or options, key=(lambda o: (o[0], o[1])) if sensible else (lambda o: (o[1], o[0])))
    return pid, packs


def _readable(amount: float, unit: str) -> str:
    if unit == "g":
        return f"{amount / 1000:g} kg" if amount >= 1000 else f"{amount:g} g"
    if unit == "ml":
        return f"{amount / 1000:g} litre" if amount >= 1000 else f"{amount:g} ml"
    return f"{amount:g}" if amount == 1 else f"{amount:g} pieces"


async def _candidates_for(rt: Runtime, item: PlannedItem, gate: asyncio.Semaphore) -> list[Product]:
    """The catalogue products for one planned ingredient. They do not depend on the headcount, so they are
    found while the shopper is still saying how many people."""
    cached = rt.dish_candidates.get(item.need)
    if cached is not None:
        return cached
    candidates: list[Product] = []
    for name in (item.need, *item.alt):  # the planner's name first, then other names a shop may use
        try:
            async with gate:
                found = await rt.commerce.search(name, limit=SEARCH_LIMIT)
        except Exception:
            log.warning("dish_search_failed", need=name)
            continue
        rt.remember(found.products)
        candidates = _pick_candidates(name, found.products)
        if candidates:
            break
    rt.dish_candidates[item.need] = candidates
    return candidates


def _resolve(rt: Runtime, item: PlannedItem, candidates: list[Product], people: int) -> dict[str, Any]:
    """The pack count for one ingredient for this many people (no waiting: everything is already found)."""
    total = item.total(people)
    out: dict[str, Any] = {"need": item.need, "amount": _readable(total, item.unit),
                           "staple": item.staple, "product": None, "product_id": None, "qty": 1}
    if not candidates:
        return out
    amount = Amount(max(1, math.ceil(total)), item.unit)
    chosen = _choose_packs(amount, candidates)
    if not chosen and item.unit in ("g", "ml"):  # sold by the other measure (ghee in g, milk in ml): about 1 g per ml
        chosen = _choose_packs(Amount(amount.value, "ml" if item.unit == "g" else "g"), candidates)
    if chosen:
        pid, qty = chosen
    else:  # units do not match (e.g. "2 pieces" of something sold by weight): one pack, said plainly
        pid, qty = candidates[0].id, 1
        out["approximate"] = True
    if qty > MAX_PACKS:
        qty = MAX_PACKS
        out["capped"] = True
    product = rt.products[pid]
    out.update(product=product.name, product_id=pid, qty=qty,
               total=_readable(product.unit_qty * qty, product.unit), price=round(product.price_minor * qty / 100))
    return out


async def _prepare(rt: Runtime, dish: str, notes: str | None) -> DishPlan | None:
    """Plan the dish and find its products. Runs in the background as soon as the dish is named."""
    plan = await rt.planner.plan(dish, notes)
    if plan is not None and plan.recognised:
        gate = asyncio.Semaphore(SEARCH_PARALLEL)
        await asyncio.gather(*(_candidates_for(rt, it, gate) for it in plan.items))
    return plan


async def plan_dish(rt: Runtime, args: dict[str, Any]) -> dict[str, Any]:
    dish = " ".join(args["dish"].split())
    people = int(args["people"]) if args.get("people") else None
    notes = (args.get("notes") or "").strip() or None
    on_hand = [x for x in (args.get("on_hand") or []) if x and x.strip()]

    if rt.planner is None:
        raise ToolError("Dish planning is not available. Plan the list yourself: work out amounts, "
                        "search_catalog each item with amount_phrase, then show_products.", retryable=False)
    key = (_norm(dish), _norm(notes or ""))
    task = rt.dish_tasks.get(key)
    if task is None:
        task = rt.dish_tasks[key] = rt.spawn(_prepare(rt, dish, notes))
    if people is None:  # the dish was just named: get ready while the shopper says how many people
        return {"ok": True, "status": "preparing", "dish": dish,
                "instruction": "The ingredient list is being prepared in the background. Do NOT say anything about "
                               "ingredients yet. Now ask the shopper how many people it is for, then wait."}

    dish_plan: DishPlan | None = rt.dish_plans.get(key)
    if dish_plan is None:
        dish_plan = await asyncio.shield(task)
        if dish_plan is None:
            rt.dish_tasks.pop(key, None)  # try again from scratch next time
            raise ToolError("The dish planner did not answer. Say 'one moment' and call plan_dish again with the "
                            "same dish and people. If it fails a second time, say sorry and ask whether to try "
                            "once more; do not invent a list.", retryable=True)
        if not dish_plan.recognised:
            rt.dish_tasks.pop(key, None)
            raise ToolError(f"'{dish}' was not recognised as a dish. Ask the shopper to say the dish again or "
                            "describe it. Do not guess another dish.", retryable=False)
        rt.dish_plans[key] = dish_plan
    rt.dish_confirmed.add((key[0], people))

    rows = [_resolve(rt, it, rt.dish_candidates.get(it.need, []), people) for it in dish_plan.items]
    goal_items = []
    for row in rows:
        at_home = _matches_on_hand(row["need"], on_hand)
        row["on_hand"] = at_home
        goal_items.append({"need": row["need"], "product_id": row["product_id"], "qty": row["qty"],
                           "struck": at_home, "struck_reason": "on_hand" if at_home else None})
    g = await goal.build(rt, {"goal_text": f"{dish} for {people} people", "items": goal_items})

    by_need = {i.need: i for i in g.items}
    for row in rows:  # the goal builder also strikes items that are already in the cart
        built = by_need.get(row["need"])
        row["in_cart"] = bool(built and built.struck and built.struck_reason == "in_cart")
    to_buy = [r for r in rows if r["product_id"] and not r["on_hand"] and not r["in_cart"]]
    result: dict[str, Any] = {
        "ok": True,
        "dish": dish,
        "people": people,
        "goal_id": g.goal_id,
        "items": rows,
        "items_to_buy": len(to_buy),
        "not_in_catalogue": [r["need"] for r in rows if not r["product_id"]],
        "ask_if_at_home": [r["need"] for r in rows if r["staple"] and not r["on_hand"]],
        "assumption": dish_plan.assumption,
        "estimated_total_rupees": sum(r.get("price", 0) for r in to_buy),
        "instruction": (
            f"The list for {dish} for {people} people is on the shopper's screen; always call it by that name. "
            "Keep it VERY SHORT: two short sentences, then the question. Sentence one: if assumption is not empty, "
            "say it in a few words, then how many items there are and the estimated total in rupees. Sentence two: "
            "name at most 3 main ingredients with amount and unit in the shopper's language (for example 'five kilo "
            "chawal'; never packet counts for weights), say the rest are on the screen, and say which items are not "
            "in the catalogue. Do NOT read the whole list. Then ask ONE question: whether they already have any of it "
            "at home. If they name items they have, call plan_dish again with the same dish, people and on_hand, then "
            "ask 'Shall I add the rest?'. If they say they have none (a plain 'no'), that is NOT a refusal: ask 'Shall "
            "I add everything?'. On a clear yes, or 'add everything', call add_to_cart(goal_id) once and do not ask "
            "again."),
    }
    if rt.goal_problems.get(g.goal_id):
        result["problems"] = rt.goal_problems[g.goal_id]
    return result
