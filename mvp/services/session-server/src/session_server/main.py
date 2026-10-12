"""FastAPI entry point for the session server."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from session_server.adapters.memory.state import MemoryState
from session_server.config import get_settings
from session_server.http import agent_profile, tickets, ws
from session_server.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    if settings.gcp_ready and settings.state_backend == "firestore":
        from session_server.adapters.firestore.state import FirestoreState

        app.state.ticket_state = FirestoreState(settings)
    else:
        app.state.ticket_state = MemoryState()
    yield


app = FastAPI(title="TalkToBuy session server", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().shop_origin],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)
app.include_router(tickets.router)
app.include_router(agent_profile.router)
app.include_router(ws.router)


@app.get("/healthz")
async def healthz() -> dict[str, object]:
    return {"status": "ok", "gcp_configured": get_settings().gcp_ready}
