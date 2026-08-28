"""
Embeddings service — provider-agnostic, cost-governed, degradation-safe.

Mirrors the existing `get_llm()` pattern: the provider is chosen by env at call
time so switching is a one-variable change.

Providers:
  - local (default): sentence-transformers `all-MiniLM-L6-v2` (dim 384),
    zero-cost, offline, matches Bootstrapper Mode. The model is loaded LAZILY
    on first use (never at import) so importing this module is cheap and never
    fails on machines without the weights cached.
  - openai: `text-embedding-3-small` (dim 1536) via the OPENAI_API_KEY.

Cost governance (R5.11, R10.5):
  `embed_and_store(...)` hashes each string (sha256) and reuses an existing
  `embeddings` row keyed by (content_hash, model_id). Only cache MISSES call
  the provider. Token/estimated cost is recorded per row.

Degradation (R5.9, R10.4):
  Any provider failure raises `EmbeddingUnavailable`. Callers (coverage,
  memory) catch it and fall back to identity-only behavior; the missing
  embedding can be backfilled later.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from typing import Any, Optional, Protocol

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

logger = logging.getLogger("revguard.embeddings")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class EmbeddingUnavailable(Exception):
    """Raised when the embedding provider cannot produce vectors.

    Callers should catch this and degrade to identity-only behavior rather
    than failing the run.
    """


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------
class EmbeddingProvider(Protocol):
    dim: int
    model_id: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text. Raise EmbeddingUnavailable on failure."""
        ...


# ---------------------------------------------------------------------------
# Local provider (sentence-transformers) — default, zero-cost, offline
# ---------------------------------------------------------------------------
class _LocalSentenceTransformerProvider:
    """sentence-transformers provider with a lazily-loaded, process-cached model."""

    dim = 384
    model_id = "st/all-MiniLM-L6-v2"
    _MODEL_NAME = "all-MiniLM-L6-v2"

    # Class-level cache so the (heavy) model loads at most once per process.
    _model = None
    _lock = threading.Lock()

    def _get_model(self):
        if _LocalSentenceTransformerProvider._model is None:
            with _LocalSentenceTransformerProvider._lock:
                if _LocalSentenceTransformerProvider._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                        _LocalSentenceTransformerProvider._model = SentenceTransformer(
                            self._MODEL_NAME
                        )
                    except Exception as exc:
                        raise EmbeddingUnavailable(
                            f"Failed to load local embedding model: {exc}"
                        ) from exc
        return _LocalSentenceTransformerProvider._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            model = self._get_model()
            vecs = model.encode(
                texts,
                normalize_embeddings=True,   # cosine-ready
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            return [v.tolist() for v in vecs]
        except EmbeddingUnavailable:
            raise
        except Exception as exc:
            raise EmbeddingUnavailable(f"Local embedding failed: {exc}") from exc


# ---------------------------------------------------------------------------
# OpenAI provider — opt-in, paid
# ---------------------------------------------------------------------------
class _OpenAIProvider:
    dim = 1536
    model_id = "openai/text-embedding-3-small"
    _MODEL_NAME = "text-embedding-3-small"

    def __init__(self) -> None:
        self._last_token_cost = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EmbeddingUnavailable(
                "EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is not set."
            )
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp = client.embeddings.create(model=self._MODEL_NAME, input=texts)
            # preserve input order
            ordered = sorted(resp.data, key=lambda d: d.index)
            try:
                self._last_token_cost = resp.usage.total_tokens
            except Exception:
                self._last_token_cost = 0
            return [d.embedding for d in ordered]
        except Exception as exc:
            raise EmbeddingUnavailable(f"OpenAI embedding failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Provider selection (env, read at call time — mirrors get_llm())
# ---------------------------------------------------------------------------
def get_embedder() -> EmbeddingProvider:
    provider = (os.getenv("EMBEDDING_PROVIDER", "local") or "local").lower().strip()
    if provider == "openai":
        return _OpenAIProvider()
    # default: free local model
    return _LocalSentenceTransformerProvider()


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------
def content_hash(textval: str) -> str:
    """Stable sha256 of the exact content (used as the dedup key)."""
    return hashlib.sha256((textval or "").encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Embed + store with dedup (cost governance)
# ---------------------------------------------------------------------------
def embed_and_store(
    db: Session,
    texts: list[str],
    *,
    owner_id: Optional[str],
    application_id: Optional[int],
    embedder: Optional[EmbeddingProvider] = None,
) -> dict[str, int]:
    """
    Embed each text and persist to the `embeddings` table, reusing existing
    rows keyed by (content_hash, model_id) so identical content is never
    re-embedded.

    Returns a mapping content_hash -> embeddings.id for every input text
    (both cache hits and freshly-created rows).

    Raises EmbeddingUnavailable if the provider fails for the cache-miss set.
    """
    if not texts:
        return {}

    emb = embedder or get_embedder()
    model_id = emb.model_id
    dim = emb.dim

    # Deduplicate inputs by content_hash up front
    hash_by_text: dict[str, str] = {t: content_hash(t) for t in texts}
    unique_hashes = list({h for h in hash_by_text.values()})

    # 1. Which hashes already exist for this model?
    existing: dict[str, int] = {}
    rows = db.execute(
        sql_text(
            "SELECT content_hash, id FROM embeddings "
            "WHERE model_id = :m AND content_hash = ANY(:hashes)"
        ),
        {"m": model_id, "hashes": unique_hashes},
    ).fetchall()
    for ch, rid in rows:
        existing[ch] = rid

    # 2. Compute embeddings only for missing hashes
    missing_hashes = [h for h in unique_hashes if h not in existing]
    if missing_hashes:
        # map hash -> a representative source text
        text_for_hash: dict[str, str] = {}
        for t, h in hash_by_text.items():
            text_for_hash.setdefault(h, t)
        miss_texts = [text_for_hash[h] for h in missing_hashes]

        vectors = emb.embed(miss_texts)  # may raise EmbeddingUnavailable
        token_cost = getattr(emb, "_last_token_cost", 0) or 0
        per_row_cost = int(token_cost / max(len(miss_texts), 1))

        from pgvector import Vector as _PgVector  # value wrapper for insert
        for h, vec in zip(missing_hashes, vectors):
            # INSERT ... ON CONFLICT DO NOTHING guards against races (R10.3):
            # two concurrent embedders inserting the same (hash, model) →
            # exactly one row survives due to the unique index.
            db.execute(
                sql_text(
                    """
                    INSERT INTO embeddings
                        (owner_id, application_id, content_hash, model_id, dim, embedding, token_cost)
                    VALUES
                        (:owner, :app, :ch, :model, :dim, :emb, :cost)
                    ON CONFLICT (content_hash, model_id) DO NOTHING
                    """
                ),
                {
                    "owner": owner_id,
                    "app": application_id,
                    "ch": h,
                    "model": model_id,
                    "dim": dim,
                    "emb": _PgVector(vec),
                    "cost": per_row_cost,
                },
            )
        db.commit()

        # Re-read to get ids for the just-inserted (and any concurrently-inserted) rows
        rows2 = db.execute(
            sql_text(
                "SELECT content_hash, id FROM embeddings "
                "WHERE model_id = :m AND content_hash = ANY(:hashes)"
            ),
            {"m": model_id, "hashes": missing_hashes},
        ).fetchall()
        for ch, rid in rows2:
            existing[ch] = rid

    # 3. Return hash -> id for all inputs
    return {h: existing[h] for h in unique_hashes if h in existing}


def embed_query(textval: str, embedder: Optional[EmbeddingProvider] = None) -> list[float]:
    """
    Embed a single query string WITHOUT persisting (used for similarity search).
    Raises EmbeddingUnavailable on provider failure.
    """
    emb = embedder or get_embedder()
    out = emb.embed([textval])
    return out[0] if out else []
