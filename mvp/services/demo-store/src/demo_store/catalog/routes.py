"""`POST /ucp/v1/catalog/search` and `/catalog/lookup` (T048), validated with ucp-sdk models."""

from typing import Any

from fastapi import APIRouter, Body
from pydantic import ValidationError
from ucp_sdk.models.schemas.shopping.catalog_lookup import LookupRequest
from ucp_sdk.models.schemas.shopping.catalog_search import SearchRequest

from demo_store.catalog import seeded
from demo_store.catalog.search import MAX_LIMIT, SearchResult, get_searcher
from demo_store.catalog.store import get_catalog, to_ucp
from demo_store.config import get_settings
from demo_store.ucp.errors import UCP_VERSION, InvalidRequestError

router = APIRouter(prefix="/ucp/v1/catalog", tags=["catalog"])


def _parse(model, body: dict[str, Any]):
    try:
        return model.model_validate(body)
    except ValidationError as exc:
        raise InvalidRequestError(f"invalid request: {exc.errors()[0]['msg']}") from None


def run_search(req: SearchRequest) -> SearchResult:
    filters = req.filters
    categories = filters.categories if filters else None
    price = filters.price if filters else None
    limit = min((req.pagination.limit if req.pagination and req.pagination.limit else MAX_LIMIT), MAX_LIMIT)
    query = req.query or ""
    if get_settings().search_mode == "seeded":
        ids = seeded.lookup(query)
        if ids is not None:
            products = [
                p for p in get_catalog().lookup(ids)
                if not categories or p.category in categories
            ][:limit]
            products.sort(key=lambda p: not p.in_stock)
            scores = {p.id: round(1.0 - 0.1 * i, 2) for i, p in enumerate(products)}
            return SearchResult(products, scores, ambiguous=False)
    return get_searcher().search(
        query,
        categories=categories,
        price_min=price.min if price else None,
        price_max=price.max if price else None,
        limit=limit,
    )


@router.post("/search")
def search(body: dict[str, Any] = Body(default_factory=dict)) -> dict:
    result = run_search(_parse(SearchRequest, body))
    return {
        "ucp": {"version": UCP_VERSION},
        "products": [to_ucp(p) for p in result.products],
        "pagination": {"has_next_page": False},
        "metadata": {"talktobuy": {"ambiguous": result.ambiguous, "scores": result.scores}},
    }


@router.post("/lookup")
def lookup(body: dict[str, Any] = Body(...)) -> dict:
    req = _parse(LookupRequest, body)
    return {"ucp": {"version": UCP_VERSION}, "products": [to_ucp(p) for p in get_catalog().lookup(req.ids)]}
