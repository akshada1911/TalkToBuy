"""StatePort: persistence for session snapshots and usage (never media or transcripts)."""

from typing import Protocol

from session_server.models.domain import Session


class StatePort(Protocol):
    async def save(self, session: Session) -> None: ...

    async def load(self, session_id: str) -> Session | None: ...

    async def incr_daily_tickets(self, day: str) -> int:
        """Atomically increment and return today's ticket count (demo quota, S1)."""
        ...
