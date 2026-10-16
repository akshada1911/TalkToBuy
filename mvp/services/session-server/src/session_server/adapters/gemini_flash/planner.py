"""DishPlannerPort via a fast Gemini text model with structured output.

The live voice model is poor at arithmetic and slow when it has to think, so the amounts for a dish
are worked out here, in text, with a schema. The server then turns each amount into catalogue packs
deterministically (units/packs.py).
"""

import asyncio
import json

from google import genai
from google.genai import types

from session_server.config import Settings
from session_server.logging import get_logger
from session_server.ports.planner import DishPlan, PlannedItem

log = get_logger(__name__)

TIMEOUT_S = 18  # per attempt; a second attempt follows on the lighter model
MAX_ITEMS = 20

PROMPT = """You are an experienced Indian home cook and grocery planner.
Dish: {dish}
Special requirements: {notes}

First decide whether "{dish}" is a real dish, snack, drink or meal that people cook or prepare. If it is
not (misheard, nonsense, not food), set recognised=false and return no items.
If the dish can be made in different ways (vegetarian or not, regional versions), pick the most common
version, taking the special requirements into account, and say in one short sentence which version you
assumed (assumption).

List every ingredient to BUY for this dish, the way a grocery catalogue sells it.
Rules:
- Give each amount in g, ml or piece (never "packets" or "servings") as two numbers: per_person, the
  amount for ONE person, and fixed, an extra flat amount that does not grow with the number of people.
  The total for N people is fixed + per_person x N. Main ingredients (rice, paneer, vegetables, dal,
  flour, meat) use per_person only, with fixed 0. Seasoning mixes both (salt: fixed 5, per_person 2;
  cumin seeds: fixed 3, per_person 0.3; cooking oil: fixed 10, per_person 8).
- Use realistic cooking amounts for a full meal for one person (for example: dry rice 80-100 g for a rice
  dish; paneer 60-80 g; leafy greens 150 g; onions 40-60 g), rounded to sensible kitchen amounts.
- Include only what THIS dish really uses. Never add unrelated items. Never include water.
- Use the plain names an Indian grocery store uses, with no brands, singular and generic: "paneer",
  "spinach", "onion", "basmati rice", "garam masala", "curd" (not yogurt), "refined sunflower oil" (for
  cooking oil), "green chilli", "coriander leaves", "jeera", "maida" (for all-purpose flour), "besan", "haldi". Put each vegetable on its own line ("carrot",
  "green beans", "potato"); never "mixed vegetables". Give up to 2 other names a shop may use in alt
  (for example need "curd", alt ["dahi", "yogurt"]). One line per item, at most {max_items} items.
- Mark staple=true for salt, cooking oil, ghee, sugar and common dry spices that most homes already
  have; staple=false for everything the dish is really built on.
- Eggs, bread and similar are counted in piece; liquids in ml; everything else in g."""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "recognised": {"type": "BOOLEAN"},
        "assumption": {"type": "STRING"},
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "need": {"type": "STRING"},
                    "per_person": {"type": "NUMBER"},
                    "fixed": {"type": "NUMBER"},
                    "unit": {"type": "STRING", "enum": ["g", "ml", "piece"]},
                    "staple": {"type": "BOOLEAN"},
                    "alt": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["need", "per_person", "fixed", "unit", "staple"],
            },
        }
    },
    "required": ["recognised", "items"],
}


class FlashPlanner:
    def __init__(self, settings: Settings):
        self.models = [settings.flash_model, settings.translate_model]  # the second is the lighter fallback
        self.client = genai.Client(
            vertexai=True, project=settings.require_gcp(), location=settings.gcp_location
        )

    async def _ask(self, prompt: str, dish: str) -> dict | None:
        """One answer from the planner model; a failure (timeout, quota, bad reply) retries on the next model."""
        for model in self.models:
            try:
                resp = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.2, response_mime_type="application/json", response_schema=SCHEMA,
                            thinking_config=types.ThinkingConfig(thinking_budget=0),  # ~4 s instead of ~9 s; same amounts
                        ),
                    ),
                    TIMEOUT_S,
                )
                data = json.loads(resp.text or "")
                if isinstance(data, dict) and "items" in data:
                    return data
                raise ValueError("reply has no items")
            except Exception as exc:
                log.warning("dish_planner_failed", dish=dish, model=model, error=f"{type(exc).__name__}: {str(exc)[:200]}")
        return None

    async def plan(self, dish: str, notes: str | None) -> DishPlan | None:
        prompt = PROMPT.format(dish=dish, notes=notes or "none", max_items=MAX_ITEMS)
        data = await self._ask(prompt, dish)
        if data is None:
            return None
        raw = data.get("items", [])
        items: list[PlannedItem] = []
        for row in raw[:MAX_ITEMS]:
            need = str(row.get("need", "")).strip()
            try:
                fixed = max(0.0, float(row.get("fixed") or 0))
                per_person = max(0.0, float(row.get("per_person") or 0))
            except (TypeError, ValueError):
                continue
            if need and (fixed > 0 or per_person > 0) and row.get("unit") in ("g", "ml", "piece"):
                alt = tuple(str(a).strip() for a in (row.get("alt") or [])[:2] if str(a).strip())
                items.append(PlannedItem(need, fixed, row["unit"], bool(row.get("staple")), alt, per_person))
        recognised = bool(data.get("recognised", True)) and bool(items)
        return DishPlan(items, str(data.get("assumption") or "").strip()[:160], recognised)
