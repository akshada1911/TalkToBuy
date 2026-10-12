"""UCP request middleware for `/ucp/v1/*` (T022).

- `UCP-Agent` and `Request-Id` are required on every call; `Idempotency-Key` on POST/PUT.
- Responses (below 500) are cached by Idempotency-Key and replayed for the same method, path and
  body; the same key with a different request returns 409 `IDEMPOTENCY_CONFLICT`.
"""

import hashlib
import json

import rfc8785
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from demo_store.state import STATE, CachedResponse
from demo_store.ucp.errors import IdempotencyConflictError, InvalidRequestError, UcpError

UCP_PREFIX = "/ucp/v1"


def _error(exc: UcpError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_response().model_dump(mode="json"))


def _fingerprint(request: Request, body: bytes) -> str:
    try:
        canonical = rfc8785.dumps(json.loads(body)) if body.strip() else b""
    except (ValueError, rfc8785.CanonicalizationError):
        canonical = body
    return hashlib.sha256(f"{request.method} {request.url.path}\n".encode() + canonical).hexdigest()


class UcpHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not request.url.path.startswith(UCP_PREFIX):
            return await call_next(request)
        missing = [h for h in ("UCP-Agent", "Request-Id") if not request.headers.get(h)]
        key = request.headers.get("Idempotency-Key")
        if request.method in {"POST", "PUT"} and not key:
            missing.append("Idempotency-Key")
        if missing:
            return _error(InvalidRequestError(f"missing required header(s): {', '.join(missing)}"))
        request_id = request.headers["Request-Id"]
        if request.method not in {"POST", "PUT"}:
            response = await call_next(request)
            response.headers["Request-Id"] = request_id
            return response

        body = await request.body()
        fingerprint = _fingerprint(request, body)
        with STATE.lock:
            cached = STATE.idempotency.get(key)
        if cached is not None:
            if cached.fingerprint != fingerprint:
                return _error(IdempotencyConflictError(
                    "Idempotency-Key was already used with a different request"))
            return Response(cached.body, status_code=cached.status, media_type=cached.media_type,
                            headers={"Request-Id": request_id, "Idempotent-Replayed": "true"})

        response = await call_next(request)
        chunks = [chunk async for chunk in response.body_iterator]
        content = b"".join(c if isinstance(c, bytes) else c.encode() for c in chunks)
        media_type = response.headers.get("content-type", "application/json")
        if response.status_code < 500:
            with STATE.lock:
                STATE.idempotency[key] = CachedResponse(fingerprint, response.status_code, content, media_type)
        headers = {k: v for k, v in response.headers.items() if k.lower() not in {"content-length", "content-type"}}
        headers["Request-Id"] = request_id
        return Response(content, status_code=response.status_code, media_type=media_type, headers=headers)
