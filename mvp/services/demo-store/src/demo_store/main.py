"""FastAPI entry point for the demo store."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from demo_store.ap2.keys import mandate_key, store_key
from demo_store.catalog.routes import router as catalog_router
from demo_store.catalog.search import get_searcher
from demo_store.checkout.routes import router as checkout_router
from demo_store.config import SERVICE_DIR, get_settings
from demo_store.demo.browse import router as browse_router
from demo_store.demo.routes import router as demo_router
from demo_store.demo.routes import seed
from demo_store.discovery.manifest import router as discovery_router
from demo_store.http.middleware import UcpHeadersMiddleware
from demo_store.payment_surface.routes import router as payment_router
from demo_store.ucp.errors import InvalidRequestError, UcpError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Fail fast on a bad catalogue, seed or key rather than on the first request.
    get_searcher()
    seed()
    store_key()
    mandate_key()
    yield


app = FastAPI(title="TalkToBuy demo store", version="0.1.0", lifespan=lifespan)
app.add_middleware(UcpHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().shop_origin.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Demo-Admin-Key"],
)


def _envelope(exc: UcpError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_response().model_dump(mode="json"))


@app.exception_handler(UcpError)
async def ucp_error_handler(request: Request, exc: UcpError) -> JSONResponse:
    return _envelope(exc)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []))
    return _envelope(InvalidRequestError(f"invalid request at {where}: {first.get('msg', '')}"))


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "RESOURCE_NOT_FOUND" if exc.status_code == 404 else "INVALID_REQUEST"
    return _envelope(UcpError(str(exc.detail), code=code, status_code=exc.status_code))


app.include_router(discovery_router)
app.include_router(catalog_router)
app.include_router(checkout_router)
app.include_router(payment_router)
app.include_router(demo_router)
app.include_router(browse_router)
app.mount("/static", StaticFiles(directory=SERVICE_DIR / "static"), name="static")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
