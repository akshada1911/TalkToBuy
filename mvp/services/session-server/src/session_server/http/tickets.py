"""Session tickets (T034, Constitution III, finding S1).

- POST /v1/demo-ticket: keyless, for the demo shop only. Origin-restricted, rate-limited per IP,
  capped by concurrent sessions and a daily quota, and behind a kill switch. It only ever issues
  tickets for the demo shopper. No secret is ever bundled into a frontend.
- POST /v1/tickets: server-to-server for a host app's own backend, authenticated by DEMO_ADMIN_KEY.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from session_server.config import Settings, get_settings

router = APIRouter()

DEMO_SHOPPER = "u-ghanshyam"
TICKET_TTL_S = 600
RATE_PER_MIN = 10


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign_ticket(shopper_id: str, secret: str, ttl_s: int = TICKET_TTL_S, now: float | None = None) -> str:
    payload = {"sub": shopper_id, "exp": int((now or time.time()) + ttl_s), "jti": secrets.token_hex(8)}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_ticket(ticket: str, secret: str, now: float | None = None) -> str | None:
    """Return the shopper id if the ticket is authentic and unexpired."""
    try:
        body, sig = ticket.split(".", 1)
        expected = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_unb64(body))
        if payload["exp"] < (now or time.time()):
            return None
        return str(payload["sub"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


class SessionRegistry:
    """Counts live sessions for the concurrency cap."""

    def __init__(self) -> None:
        self.active: set[str] = set()

    def count(self) -> int:
        return len(self.active)


registry = SessionRegistry()
_hits: dict[str, deque[float]] = defaultdict(deque)


def _rate_limited(ip: str, now: float) -> bool:
    window = _hits[ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_PER_MIN:
        return True
    window.append(now)
    return False


class TicketResponse(BaseModel):
    ticket: str
    expires_in: int


@router.post("/v1/demo-ticket", response_model=TicketResponse)
async def demo_ticket(
    request: Request,
    origin: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> TicketResponse:
    if not settings.demo_tickets_enabled:
        raise HTTPException(503, "The demo is paused.")
    if origin != settings.shop_origin:
        raise HTTPException(403, "Tickets are only issued to the demo shop.")
    ip = request.client.host if request.client else "unknown"
    if _rate_limited(ip, time.time()):
        raise HTTPException(429, "Too many requests; try again in a minute.")
    if registry.count() >= settings.max_concurrent_sessions:
        raise HTTPException(429, "The assistant is busy right now; please try again shortly.")
    state = request.app.state.ticket_state
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if await state.incr_daily_tickets(today) > settings.daily_session_quota:
        raise HTTPException(429, "Today's demo quota is used up.")
    return TicketResponse(ticket=sign_ticket(DEMO_SHOPPER, settings.ticket_signing_secret),
                          expires_in=TICKET_TTL_S)


class AdminTicketRequest(BaseModel):
    shopper_id: str


@router.post("/v1/tickets", response_model=TicketResponse)
async def admin_ticket(
    body: AdminTicketRequest,
    x_demo_admin_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> TicketResponse:
    if not x_demo_admin_key or not hmac.compare_digest(x_demo_admin_key, settings.demo_admin_key):
        raise HTTPException(401, "Invalid admin key.")
    return TicketResponse(ticket=sign_ticket(body.shopper_id, settings.ticket_signing_secret),
                          expires_in=TICKET_TTL_S)
