"""In-memory StatePort (tests and local dev without GCP)."""

from session_server.models.domain import Session


class MemoryState:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.daily: dict[str, int] = {}

    async def save(self, session: Session) -> None:
        self.sessions[session.session_id] = session.model_copy(deep=True)

    async def load(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    async def incr_daily_tickets(self, day: str) -> int:
        self.daily[day] = self.daily.get(day, 0) + 1
        return self.daily[day]
