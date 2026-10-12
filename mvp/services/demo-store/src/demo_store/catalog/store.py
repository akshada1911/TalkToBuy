"""Catalogue storage: `data/catalog.json` loaded into memory and validated at startup.

The catalogue is a small read-only snapshot (hundreds of items), so an in-memory index is used
instead of SQLite; there is nothing to write back.
"""

import json
from functools import lru_cache
from pathlib import Path

from demo_store.config import get_settings
from demo_store.models.domain import Product

CURRENCY = "INR"


class Catalog:
    def __init__(self, products: list[Product]) -> None:
        self._by_id = {p.id: p for p in products}
        if len(self._by_id) != len(products):
            raise ValueError("duplicate product ids in catalog.json")

    @classmethod
    def from_file(cls, path: Path) -> "Catalog":
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw["products"] if isinstance(raw, dict) else raw
        return cls([Product.model_validate(item) for item in items])

    def get(self, product_id: str) -> Product | None:
        return self._by_id.get(product_id)

    def lookup(self, ids: list[str]) -> list[Product]:
        """Products in request order; unknown ids are omitted."""
        return [self._by_id[i] for i in ids if i in self._by_id]

    def all(self) -> list[Product]:
        return list(self._by_id.values())


@lru_cache
def get_catalog() -> Catalog:
    return Catalog.from_file(get_settings().data_dir / "catalog.json")


def image_url(product: Product) -> str:
    """Absolute image URL (hand-added items use a store-relative `/static/...` path)."""
    if product.image.startswith("/"):
        return get_settings().store_base_url.rstrip("/") + product.image
    return product.image


def to_ucp(product: Product) -> dict:
    """UCP catalog product with the full domain Product under `metadata.talktobuy`."""
    price = {"amount": product.price_minor, "currency": CURRENCY}
    description = {"plain": product.listing.description}
    return {
        "id": product.id,
        "title": product.name,
        "description": description,
        "categories": [{"value": product.category}],
        "price_range": {"min": price, "max": price},
        "media": [{"type": "image", "url": image_url(product), "alt_text": product.name}],
        "variants": [
            {
                "id": product.id,
                "title": product.size,
                "description": description,
                "price": price,
                "availability": {"available": product.in_stock},
            }
        ],
        "metadata": {"talktobuy": product.model_dump(mode="json")},
    }
