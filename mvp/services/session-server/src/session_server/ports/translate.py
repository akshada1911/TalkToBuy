"""TranslatePort: display-only Hindi→English caption translation (R10)."""

from typing import Protocol


class TranslatePort(Protocol):
    async def to_english(self, text_hi: str) -> str | None:
        """Return the English translation, or None if unavailable."""
        ...
