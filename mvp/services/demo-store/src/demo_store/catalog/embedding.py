"""Gemini embeddings for catalogue search, guarded so nothing calls Google without a project.

`require_gcp_project()` refuses unless `GCP_PROJECT` is set to the dedicated TalkToBuy project
(not empty, not a `REPLACE_…` placeholder, never the machine's gcloud default project).
"""

import json
import logging
from functools import lru_cache

import numpy as np

from demo_store.config import gcp_project_or_none, get_settings

log = logging.getLogger(__name__)

MODEL = "gemini-embedding-2"
FALLBACK_MODEL = "gemini-embedding-001"
DIMENSIONS = 768


class GcpNotConfigured(RuntimeError):
    pass


def require_gcp_project() -> str:
    project = gcp_project_or_none()
    if project is None:
        raise GcpNotConfigured(
            "GCP_PROJECT is not set to the TalkToBuy project; refusing to call Gemini."
        )
    return project


@lru_cache
def _client():
    from google import genai  # imported lazily: only when a project is configured

    project = require_gcp_project()
    return genai.Client(vertexai=True, project=project, location=get_settings().gcp_location)


def vectors_model() -> str | None:
    """The model that built data/vectors.npy (queries must use the same one), or None."""
    meta = get_settings().data_dir / "vectors_meta.json"
    if not meta.exists():
        return None
    return json.loads(meta.read_text("utf-8")).get("model")


def embed_texts(texts: list[str], task_type: str, model: str) -> np.ndarray:
    """L2-normalised embeddings, shape (len(texts), 768). Raises GcpNotConfigured."""
    from google.genai import types

    config = types.EmbedContentConfig(output_dimensionality=DIMENSIONS, task_type=task_type)
    resp = _client().models.embed_content(model=model, contents=texts, config=config)
    vectors = np.array([e.values for e in resp.embeddings], dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def pick_document_model() -> str:
    """Prefer MODEL; fall back to FALLBACK_MODEL if the project/region lacks it (R6 risk)."""
    try:
        embed_texts(["probe"], "RETRIEVAL_DOCUMENT", MODEL)
        return MODEL
    except GcpNotConfigured:
        raise
    except Exception as exc:  # noqa: BLE001 - model availability varies by project and region
        log.warning("%s unavailable (%s); using %s", MODEL, str(exc)[:120], FALLBACK_MODEL)
        return FALLBACK_MODEL


@lru_cache(maxsize=512)
def _embed_query_cached(text: str) -> np.ndarray | None:
    try:
        model = vectors_model()
        if model is None:
            return None
        return embed_texts([text], "RETRIEVAL_QUERY", model)[0]
    except GcpNotConfigured:
        return None
    except Exception as exc:  # noqa: BLE001 - search must degrade to lexical, never fail
        log.warning("query embedding failed: %s", exc)
        return None


def embed_query(text: str) -> np.ndarray | None:
    """Query vector, or None (→ lexical search) when Gemini is unavailable or not configured."""
    if gcp_project_or_none() is None:
        return None
    return _embed_query_cached(text)
