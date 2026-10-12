"""Embed the catalogue for hybrid search (T045). Requires the TalkToBuy GCP project.

Embeds `"{name} | {brand} | {size} | {category} | {local_name} | {synonyms}"` per product with
`gemini-embedding-2` at 768 dimensions (fallback `gemini-embedding-001`), task type
RETRIEVAL_DOCUMENT, L2-normalised, and writes `data/vectors.npy` + `data/vector_ids.json`.

Refuses to run unless GCP_PROJECT is the dedicated TalkToBuy project (never a placeholder and
never the machine's gcloud default project).

Usage (from mvp/): python -m uv run python services/demo-store/scripts/embed_catalog.py
"""

import json
import sys

import numpy as np

from demo_store.catalog.embedding import (
    GcpNotConfigured,
    embed_texts,
    pick_document_model,
    require_gcp_project,
)
from demo_store.catalog.store import get_catalog
from demo_store.config import get_settings

BATCH = 50


def document_text(p) -> str:
    return " | ".join([p.name, p.brand or "", p.size, p.category, p.local_name, ", ".join(p.synonyms)])


def main() -> None:
    try:
        project = require_gcp_project()
    except GcpNotConfigured as exc:
        sys.exit(str(exc))
    products = get_catalog().all()
    model = pick_document_model()
    print(f"embedding {len(products)} products in project {project} with {model}")
    chunks = []
    for start in range(0, len(products), BATCH):
        batch = products[start:start + BATCH]
        chunks.append(embed_texts([document_text(p) for p in batch], "RETRIEVAL_DOCUMENT", model))
    vectors = np.vstack(chunks).astype(np.float32)
    data_dir = get_settings().data_dir
    np.save(data_dir / "vectors.npy", vectors)
    (data_dir / "vector_ids.json").write_text(json.dumps([p.id for p in products]), "utf-8")
    (data_dir / "vectors_meta.json").write_text(
        json.dumps({"model": model, "dimensions": int(vectors.shape[1]), "count": len(products)}), "utf-8"
    )
    print(f"wrote {vectors.shape} ({model}) to {data_dir / 'vectors.npy'}")


if __name__ == "__main__":
    main()
