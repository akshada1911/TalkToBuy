"""ClassifierPort: second-opinion warning-sign classification (R8)."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SafetyVerdict:
    warning_sign: bool
    sign: str | None = None


class ClassifierPort(Protocol):
    async def classify(self, text: str) -> SafetyVerdict | None:
        """Return a verdict, or None if the classifier is unavailable."""
        ...
