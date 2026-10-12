"""search_catalog (T050): search + deterministic pack plans + out-of-stock alternatives."""

from typing import Any

from session_server.core import confirm
from session_server.core.runtime import Runtime
from session_server.core.ui import model_product
from session_server.models.domain import Product
from session_server.units import PackOption, parse, plan


def _interpretation(phrase: str, product: Product, qty: int) -> tuple[str, str]:
    return (f"'{phrase}' = {qty} × {product.size} {product.name}",
            f"'{phrase}' = {qty} पैक {product.size} {product.local_name}")


async def search_catalog(rt: Runtime, args: dict[str, Any]) -> dict[str, Any]:
    filters = args.get("filters") or {}
    result = await rt.commerce.search(
        args["query"],
        categories=[filters["category"]] if filters.get("category") else None,
        max_price_minor=filters["max_price"] * 100 if filters.get("max_price") else None,
        limit=10,
    )
    products = result.products
    if filters.get("brand"):
        brand = filters["brand"].lower()
        products = [p for p in products if p.brand and brand in p.brand.lower()] or products
    if filters.get("in_stock_only"):
        products = [p for p in products if p.in_stock]
    rt.remember(products)

    out: dict[str, Any] = {"products": [model_product(p) for p in products], "ambiguous": result.ambiguous}

    phrase = args.get("amount_phrase")
    if phrase:
        amount = parse(phrase)
        if amount is None:
            out["amount_not_understood"] = phrase
        else:
            options = [PackOption(p.id, p.unit_qty, p.unit) for p in products if p.in_stock]
            by_id = {p.id: p for p in products}
            plans = []
            for rank, (pid, qty) in enumerate(plan(amount, options)):
                en, hi = _interpretation(phrase, by_id[pid], qty)
                plans.append({"product_id": pid, "qty": qty, "interpreted_en": en,
                              "interpreted_hi": hi, "recommended": rank == 0})
            out["pack_plans"] = plans

    if products and not products[0].in_stock:
        best = products[0]
        alts = [p for p in products[1:] if p.in_stock and p.category == best.category][:2]
        out["alternatives"] = [
            {"product_id": p.id,
             "reason": f"{best.name} is out of stock; {p.name} ({p.size}) is the closest in-stock "
                       f"{best.category} item."}
            for p in alts
        ]

    if rt.camera_active and products:
        confirm.arm(rt, "camera", [p.id for p in products[:3]])
        out["note"] = "Recognised from the camera: name the product and ask before adding."
    return out
