"""Demo catalogue browsing for the shop app's Home, list and product screens (read-only).

The assistant still shops through the UCP catalogue search; this is a plain list for the screens
a shopper can look through. Prices are whole rupees, images are absolute URLs.
"""

from collections import Counter

from fastapi import APIRouter, Query

from demo_store.catalog.store import get_catalog, image_url
from demo_store.models.domain import Product
from demo_store.ucp.errors import ResourceNotFoundError

router = APIRouter(prefix="/demo/catalog", tags=["demo"])

MAX_LIMIT = 100


def _card(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "local_name": p.local_name,
        "brand": p.brand,
        "size": p.size,
        "price": round(p.price_minor / 100),
        "image": image_url(p),
        "image_credit": p.image_credit,
        "category": p.category,
        "in_stock": p.in_stock,
        "description": p.listing.description,
        "usage": p.listing.usage,
    }


def _haystack(p: Product) -> str:
    return " ".join([p.name, p.local_name, p.brand or "", *p.synonyms]).lower()


def _score(p: Product, tokens: list[str]) -> int | None:
    """None when a token is missing; otherwise lower is better (name matches rank first)."""
    hay = _haystack(p)
    if not all(t in hay for t in tokens):
        return None
    name = f"{p.name} {p.local_name}".lower()
    return sum(0 if t in name else 1 for t in tokens)


@router.get("")
def browse(
    category: str | None = None,
    q: str | None = None,
    limit: int = Query(40, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> dict:
    products = get_catalog().all()
    if category:
        products = [p for p in products if p.category == category]
    tokens = [t for t in (q or "").lower().split() if t]
    if tokens:
        scored = [(s, p) for p in products if (s := _score(p, tokens)) is not None]
        scored.sort(key=lambda sp: (not sp[1].in_stock, sp[0]))
        products = [p for _, p in scored]
    else:
        products = sorted(products, key=lambda p: not p.in_stock)
    return {
        "items": [_card(p) for p in products[offset : offset + limit]],
        "total": len(products),
        "limit": limit,
        "offset": offset,
    }


@router.get("/categories")
def categories() -> list[dict]:
    counts = Counter(p.category for p in get_catalog().all())
    return [{"id": cid, "count": n} for cid, n in counts.most_common()]


@router.get("/{product_id}")
def product(product_id: str) -> dict:
    p = get_catalog().get(product_id)
    if p is None:
        raise ResourceNotFoundError(f"product {product_id} not found")
    similar = [
        _card(s) for s in get_catalog().all()
        if s.category == p.category and s.id != p.id and s.in_stock
    ][:8]
    return {**_card(p), "similar": similar}
