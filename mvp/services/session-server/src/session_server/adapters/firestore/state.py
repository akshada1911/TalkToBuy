"""Firestore StatePort (T027). Persists session fields and usage only — never media or
transcripts (FR-040)."""

from google.cloud import firestore

from session_server.config import Settings
from session_server.models.domain import Session


class FirestoreState:
    def __init__(self, settings: Settings):
        self.db = firestore.AsyncClient(
            project=settings.require_gcp(), database=settings.firestore_database
        )

    async def save(self, session: Session) -> None:
        await self.db.collection("sessions").document(session.session_id).set(
            session.model_dump(mode="json")
        )

    async def load(self, session_id: str) -> Session | None:
        snap = await self.db.collection("sessions").document(session_id).get()
        return Session.model_validate(snap.to_dict()) if snap.exists else None

    async def incr_daily_tickets(self, day: str) -> int:
        ref = self.db.collection("ticket_quota").document(day)
        await ref.set({"count": firestore.Increment(1)}, merge=True)
        snap = await ref.get()
        return int((snap.to_dict() or {}).get("count", 0))
