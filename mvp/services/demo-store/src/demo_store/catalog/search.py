"""Hybrid catalogue search (research R6).

score = 0.6·similarity + 0.3·exact name/local_name/synonym match + 0.1·brand match

- `similarity` is the cosine between the query and product embeddings when `data/vectors.npy`
  exists and a TalkToBuy GCP project is configured; otherwise it is a lexical stand-in (fuzzy
  token coverage of the query over the product's words). Tests run in lexical mode.
- In-stock products rank first; `ambiguous` is true when the top two scores are within 0.05.
- A size in the query ("paav kilo", "5 kg") nudges packs of exactly that size up by 0.06.
"""

import json
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache

import numpy as np

from demo_store.catalog import normalize
from demo_store.catalog.embedding import embed_query
from demo_store.catalog.store import Catalog, get_catalog
from demo_store.config import get_settings
from demo_store.models.domain import Product

W_SIM, W_EXACT, W_BRAND = 0.6, 0.3, 0.1
SIZE_BONUS = 0.06
AMBIGUITY_GAP = 0.05
MAX_LIMIT = 10
MIN_COVERAGE = 0.5
AUTO_HINDI_WEIGHT = 0.75  # generated (unreviewed) Hindi names count less than curated ones
SEMANTIC_TOP_K = 20


@dataclass
class Indexed:
    product: Product
    phrases: list[list[str]]
    words: set[str]
    brand: set[str]
    curated: bool


@dataclass
class SearchResult:
    products: list[Product]
    scores: dict[str, float] = field(default_factory=dict)
    ambiguous: bool = False


def _index(product: Product) -> Indexed:
    phrases = [normalize.tokens(t) for t in [product.name, product.local_name, *product.synonyms]]
    phrases = [p for p in phrases if p]
    words = {w for p in phrases for w in p} | set(normalize.tokens(product.category))
    brand = set(normalize.tokens(product.brand or ""))
    curated = "talktobuy:auto-hindi" not in product.source_categories
    return Indexed(product, phrases, words | brand, brand, curated)


def _match(q: str, w: str) -> float:
    """Similarity of two phonetic tokens in [0, 1]."""
    if q == w:
        return 1.0
    if min(len(q), len(w)) >= 4 and (w.startswith(q) or q.startswith(w)):
        return 0.9
    if min(len(q), len(w)) >= 4:
        ratio = SequenceMatcher(None, q, w).ratio()
        if ratio >= 0.8:
            return ratio * 0.9
    return 0.0


def _best(q: str, words) -> float:
    return max((_match(q, w) for w in words), default=0.0)


class Searcher:
    def __init__(self, catalog: Catalog, vectors: np.ndarray | None = None,
                 vector_ids: list[str] | None = None) -> None:
        self.catalog = catalog
        self.index = {p.id: _index(p) for p in catalog.all()}
        self.vectors = vectors
        self.vector_row = {pid: i for i, pid in enumerate(vector_ids or [])}

    def _lexical(self, item: Indexed, q_tokens: list[str]) -> tuple[float, float, float]:
        coverage = sum(_best(q, item.words) for q in q_tokens) / len(q_tokens)
        exact = 0.0
        for phrase in item.phrases:
            matched = sum(_best(q, phrase) for q in q_tokens)
            exact = max(exact, matched / max(len(q_tokens), len(phrase)))
        if not item.curated:
            exact *= AUTO_HINDI_WEIGHT
        brand = 1.0 if item.brand and any(_best(q, item.brand) >= 0.9 for q in q_tokens) else 0.0
        return coverage, exact, brand

    def _semantic(self, query: str) -> dict[str, float] | None:
        if self.vectors is None:
            return None
        qvec = embed_query(query)
        if qvec is None:
            return None
        sims = self.vectors @ qvec
        top = np.argsort(-sims)[:SEMANTIC_TOP_K]
        ids = list(self.vector_row)
        return {ids[i]: float(sims[i]) for i in top}

    def search(self, query: str, categories: list[str] | None = None,
               price_min: int | None = None, price_max: int | None = None,
               limit: int = MAX_LIMIT) -> SearchResult:
        limit = max(1, min(limit or MAX_LIMIT, MAX_LIMIT))
        pool = [
            item for item in self.index.values()
            if (not categories or item.product.category in categories)
            and (price_min is None or item.product.price_minor >= price_min)
            and (price_max is None or item.product.price_minor <= price_max)
        ]
        q_tokens = normalize.tokens(query or "")
        if not q_tokens:
            if (query or "").strip():
                return SearchResult([])  # only quantity/filler words
            pool.sort(key=lambda i: (not i.product.in_stock, i.product.id))
            return SearchResult([i.product for i in pool[:limit]])

        hint = normalize.size_hint(query)
        numbers = normalize.numbers(query)
        semantic = self._semantic(query)
        scored: list[tuple[float, Indexed]] = []
        for item in pool:
            coverage, exact, brand = self._lexical(item, q_tokens)
            if semantic is not None:
                if item.product.id not in semantic and coverage < MIN_COVERAGE:
                    continue
                similarity = semantic.get(item.product.id, 0.0)
            else:
                if coverage < MIN_COVERAGE:
                    continue
                similarity = coverage
            score = W_SIM * similarity + W_EXACT * exact + W_BRAND * brand
            p = item.product
            if hint and p.unit == hint[1] and abs(p.unit_qty - hint[0]) < 1e-6:
                score += SIZE_BONUS
            elif not hint and numbers and numbers & normalize.numbers(f"{p.name} {p.size}"):
                score += SIZE_BONUS  # e.g. "7 inch cake tin"
            scored.append((round(score, 4), item))

        # Take the best `limit` by score (so an out-of-stock best match is never dropped), then
        # list in-stock products first.
        scored.sort(key=lambda s: (-s[0], not s[1].curated, s[1].product.unit_qty, s[1].product.id))
        top = sorted(scored[:limit], key=lambda s: not s[1].product.in_stock)
        ambiguous = len(scored) >= 2 and scored[0][0] - scored[1][0] < AMBIGUITY_GAP
        return SearchResult(
            products=[item.product for _, item in top],
            scores={item.product.id: score for score, item in top},
            ambiguous=ambiguous,
        )


@lru_cache
def get_searcher() -> Searcher:
    data_dir = get_settings().data_dir
    vectors_path, ids_path = data_dir / "vectors.npy", data_dir / "vector_ids.json"
    if vectors_path.exists() and ids_path.exists():
        return Searcher(get_catalog(), np.load(vectors_path),
                        json.loads(ids_path.read_text(encoding="utf-8")))
    return Searcher(get_catalog())
