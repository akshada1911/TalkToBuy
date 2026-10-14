"""WebSocket /v1/session (T034): the composition root that wires ports to adapters."""

import asyncio
import contextlib
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from session_server.config import Settings, get_settings
from session_server.core.cart import adopt_cart
from session_server.core.prompts import build_system_instruction, cart_note, opening_note
from session_server.core.runtime import Runtime
from session_server.core.session import ConversationSession
from session_server.core.tool_router import ToolRouter, load_tool_specs
from session_server.core.tools import HANDLERS
from session_server.core.ui import cart_msg, rupees
from session_server.http.tickets import registry, verify_ticket
from session_server.logging import get_logger
from session_server.models.domain import Session, Usage
from session_server.models.messages import ErrorMsg
from session_server.ports.live import LiveConfig

log = get_logger(__name__)
router = APIRouter()

LANGUAGE_CODES = {"hi": "hi-IN", "en": "en-IN"}  # speech in and out for the chosen language

BASE_VOCABULARY = ["Parle-G", "Amul", "Aashirvaad", "Milkmaid", "Nestlé", "Cadbury", "Bakers",
                   "Weikfield", "maida", "atta", "aata", "मैदा", "आटा", "पाव", "किलो"]


class WsUi:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.lock = asyncio.Lock()

    async def send_json(self, message: BaseModel | dict[str, Any]) -> None:
        data = message.model_dump(mode="json") if isinstance(message, BaseModel) else message
        async with self.lock:
            await self.ws.send_text(json.dumps(data, ensure_ascii=False))

    async def send_bytes(self, data: bytes) -> None:
        async with self.lock:
            await self.ws.send_bytes(data)


def build_adapters(settings: Settings) -> dict[str, Any]:
    """Google adapters only with an explicit TalkToBuy project (never the gcloud default)."""
    from session_server.adapters.gemini_flash.classifier import FlashClassifier
    from session_server.adapters.gemini_flash.translate import FlashTranslate
    from session_server.adapters.gemini_live.session import GeminiLive
    from session_server.adapters.memory.state import MemoryState
    from session_server.adapters.ucp.client import UcpCommerce

    if settings.state_backend == "firestore":
        from session_server.adapters.firestore.state import FirestoreState

        state = FirestoreState(settings)
    else:
        state = MemoryState()
    return {
        "live": GeminiLive(settings),
        "commerce": UcpCommerce(settings),
        "state": state,
        "translate": FlashTranslate(settings),
        "classifier": FlashClassifier(settings),
    }


@router.websocket("/v1/session")
async def session_ws(ws: WebSocket, ticket: str = "", media_mode: str = "", language: str = "hi", cart: str = "") -> None:
    settings = get_settings()
    await ws.accept()
    ui = WsUi(ws)
    shopper_id = verify_ticket(ticket, settings.ticket_signing_secret)
    if shopper_id is None:
        await ui.send_json(ErrorMsg(type="error", code="bad_ticket", message_hi="सत्र मान्य नहीं है।",
                                    message_en="Invalid or expired session ticket."))
        await ws.close(code=4401)
        return
    if not settings.gcp_ready:
        await ui.send_json(ErrorMsg(type="error", code="not_configured",
                                    message_hi="सहायक अभी चालू नहीं है।",
                                    message_en="The assistant is not configured (GCP_PROJECT missing)."))
        await ws.close(code=4503)
        return
    if registry.count() >= settings.max_concurrent_sessions:
        await ui.send_json(ErrorMsg(type="error", code="busy", message_hi="अभी सब व्यस्त हैं, थोड़ी देर बाद आइए।",
                                    message_en="The assistant is busy; please try again shortly."))
        await ws.close(code=4429)
        return

    session_id = f"s-{uuid.uuid4().hex[:12]}"
    registry.active.add(session_id)
    try:
        ports = build_adapters(settings)
        commerce = ports["commerce"]
        shopper = await commerce.shopper(shopper_id)
        session = Session(
            session_id=session_id, shopper_id=shopper_id, started_at=time.time(),
            language=language if language in LANGUAGE_CODES else "hi",
            # Voice only: video (avatar) mode is not offered, whatever the widget asks for.
            media_mode="audio_only",
            usage=Usage(audio_in_s=0, audio_out_s=0, video_in_s=0, tokens_in=0, tokens_out=0, est_cost_usd=0),
        )
        rt = Runtime(session=session, shopper=shopper, commerce=commerce, live=ports["live"], ui=ui,
                     settings=settings)
        # A cart the shopper already filled in the shop is this session's cart too (one cart).
        cart_text = None
        if cart:
            try:
                if await adopt_cart(rt, cart) and rt.cart and rt.cart.lines:
                    cart_text = cart_note(
                        [(l.product_id, rt.products[l.product_id].name if l.product_id in rt.products else l.product_id, l.qty)
                         for l in rt.cart.lines],
                        rupees(rt.cart.total_minor),
                    )
            except Exception:  # a cart that cannot be picked up must never stop the conversation
                log.exception("cart_adopt_failed")
                rt.session.cart_ref = rt.session.checkout_id = None
                rt.cart = None
        usual = await commerce.last_order(shopper_id)
        vocabulary = BASE_VOCABULARY + [w for p, _ in (usual.lines if usual else []) for w in (p.name, p.local_name)]
        await rt.live.connect(LiveConfig(
            system_instruction=build_system_instruction(shopper, session.pace, language=session.language, cart=cart_text),
            tools=load_tool_specs(), media_mode=session.media_mode, vocabulary=vocabulary,
            language_code=LANGUAGE_CODES[session.language],
        ))
        convo = ConversationSession(rt, ToolRouter(rt, HANDLERS), ports["state"],
                                    translate=ports["translate"], classifier=ports["classifier"])

        if rt.cart is not None:
            await ui.send_json(cart_msg(rt.cart, rt.products))
        await rt.live.send_text(opening_note(shopper, session.language), role="system_note")  # greet first

        async def pump_client() -> None:
            with contextlib.suppress(WebSocketDisconnect):
                while True:
                    msg = await ws.receive()
                    if msg.get("type") == "websocket.disconnect":
                        return
                    if msg.get("bytes") is not None:
                        await convo.on_client_bytes(msg["bytes"])
                    elif msg.get("text") is not None:
                        await convo.on_client_json(json.loads(msg["text"]))

        tasks = [asyncio.ensure_future(pump_client()), asyncio.ensure_future(convo.run())]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in tasks:
            task.cancel()
        await convo.end("disconnected")
    except Exception:
        log.exception("session_failed", session_id=session_id)
        with contextlib.suppress(Exception):
            await ui.send_json(ErrorMsg(type="error", code="internal", message_hi="कुछ गड़बड़ हुई, माफ़ कीजिए।",
                                        message_en="Something went wrong. Sorry."))
    finally:
        registry.active.discard(session_id)
        with contextlib.suppress(Exception):
            await ws.close()
