"""DishPlannerPort: what to buy, and how much, to cook a named dish for a number of people."""

from dataclasses import dataclass
from typing import Literal, Protocol

Unit = Literal["g", "ml", "piece"]


@dataclass(frozen=True)
class PlannedItem:
    need: str  # plain grocery name, e.g. "basmati rice"
    amount: float  # the flat amount in `unit` (the whole amount when per_person is 0)
    unit: Unit
    staple: bool = False  # salt, oil, common spices: most homes already have them
    alt: tuple[str, ...] = ()  # other names a shop may use for it ("curd", "dahi"), tried if the first finds nothing
    per_person: float = 0.0  # extra amount for each person; `amount` is the flat part that does not grow

    def total(self, people: int) -> float:
        """The amount to buy for this many people: flat part plus the per-person part."""
        return self.amount + self.per_person * people


@dataclass(frozen=True)
class DishPlan:
    items: list[PlannedItem]
    assumption: str = ""  # the version of the dish that was assumed, one short sentence ("a vegetarian version")
    recognised: bool = True  # False when the dish name is not a dish (misheard, nonsense)


class DishPlannerPort(Protocol):
    async def plan(self, dish: str, notes: str | None) -> DishPlan | None:
        """The ingredients, with amounts that scale with the number of people (so the plan can be prepared before
        anyone says how many), or None if the planner is unavailable."""
        ...
