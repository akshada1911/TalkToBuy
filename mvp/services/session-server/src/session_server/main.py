"""FastAPI entry point for the session server."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from session_server.adapters.memory.state import MemoryState
from session_server.config import get_settings
from session_server.http import agent_profile, tickets, ws
from session_server.logging import configure_logging, get_logger

log = get_logger(__name__)


async def _record_greetings(settings) -> None:
    """Record the opening line for the demo shopper in both languages, so the first hello is instant.

    In the cloud the store starts in the same container a moment after this server, so it retries."""
    from session_server.adapters.ucp.client import UcpCommerce
    from session_server.core import greeting
    from session_server.core.prompts import opening_text

    for attempt in range(12):
        try:
            shopper = await UcpCommerce(settings).shopper(tickets.DEMO_SHOPPER)
            break
        except Exception:
            await asyncio.sleep(3)
    else:
        log.warning("greeting_warmup_skipped")
        return
    for language in ("en", "hi"):
        await greeting.ensure(settings, opening_text(shopper, language), language)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    if settings.gcp_ready and settings.state_backend == "firestore":
        from session_server.adapters.firestore.state import FirestoreState

        app.state.ticket_state = FirestoreState(settings)
    else:
        app.state.ticket_state = MemoryState()
    warm = None
    if settings.gcp_ready and settings.greeting_enabled:
        warm = asyncio.create_task(_record_greetings(settings))
    yield
    if warm is not None:
        warm.cancel()


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
