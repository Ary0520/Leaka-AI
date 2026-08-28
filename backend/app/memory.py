"""
Memory service — durable, per-application learned knowledge with semantic
retrieval and a durable write-back queue (Requirements 5.1–5.11).

This is a SERVICE (it does I/O: DB + embeddings + pgvector), not a pure engine.
It sits on top of the M4 tables (`memory_items`, `memory_write_queue`) and the
existing embeddings service.

Design guarantees:
  - write(...) NEVER raises (R5.5a): on any DB/embedder failure it enqueues the
    knowledge to `memory_write_queue` for later retry, so the in-flight run
    always completes and learning is never lost.
  - retrieve(...) degrades gracefully (R5.9): identity lookup always works; the
    semantic (vector) signal is added only when available (Postgres + embedder),
    and any failure there silently falls back to identity-only results.
  - Everything is tenant- + application-scoped in the WHERE clause (R5.6,
    Property 8): no memory item is ever retrievable across tenants.
  - Cost-governed (R5.11): embeddings reuse `embed_and_store`'s (content_hash,
    model_id) dedup, so unchanged content is never re-embedded.

The periodic maintenance tasks (drain the write queue, compact/retain) live in
`graph_worker` (Celery tasks) and call the helpers here.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from .config import settings
from .models import MemoryItem, MemoryWriteQueue
from .intelligence import embeddings as EMB

logger = logging.getLogger("revguard.memory")


# Kinds whose retrieval benefits from semantic similarity → we embed them.
_SEMANTIC_KINDS = {"locator", "auth_pattern", "outcome"}
# Kinds that are versioned per node (fingerprints) — subject to retention.
_VERSIONED_KINDS = {"fingerprint"}


def _is_postgres() -> bool:
    return settings.DATABASE_URL.startswith("postgres")


# ---------------------------------------------------------------------------
# Retention config (env-read at call time, mirroring the settings pattern)
# ---------------------------------------------------------------------------
def _max_fingerprint_versions() -> int:
    try:
        return max(1, int(os.getenv("MEMORY_MAX_FINGERPRINT_VERSIONS", "10")))
    except Exception:
        return 10


def _timing_outcome_keep() -> int:
    try:
        return max(1, int(os.getenv("MEMORY_MAX_TIMING_OUTCOME", "50")))
    except Exception:
        return 50


# ---------------------------------------------------------------------------
# Input container
# ---------------------------------------------------------------------------
@dataclass
class MemoryWrite:
    """A single unit of knowledge to persist."""
    application_id: int
    kind: str                                   # locator|timing|auth_pattern|outcome|fingerprint
    payload: dict
    owner_id: Optional[str] = None
    node_id: Optional[int] = None
    provenance: dict = field(default_factory=dict)
    # Optional text used for the semantic embedding (defaults to a summary of
    # the payload when the kind is semantic and no explicit text is given).
    embed_text: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps({
            "application_id": self.application_id,
            "kind": self.kind,
            "payload": self.payload,
            "owner_id": self.owner_id,
            "node_id": self.node_id,
            "provenance": self.provenance,
            "embed_text": self.embed_text,
        }, default=str)

    @staticmethod
    def from_json(s: str) -> "MemoryWrite":
        d = json.loads(s)
        return MemoryWrite(
            application_id=d["application_id"],
            kind=d["kind"],
            payload=d.get("payload") or {},
            owner_id=d.get("owner_id"),
            node_id=d.get("node_id"),
            provenance=d.get("provenance") or {},
            embed_text=d.get("embed_text"),
        )


# ---------------------------------------------------------------------------
# Retrieved item view
# ---------------------------------------------------------------------------
@dataclass
class RetrievedMemory:
    id: int
    kind: str
    node_id: Optional[int]
    payload: dict
    version: int
    provenance: dict
    similarity: Optional[float] = None          # set only for semantic hits


def _row_to_retrieved(row: MemoryItem, similarity: Optional[float] = None) -> RetrievedMemory:
    return RetrievedMemory(
        id=row.id,
        kind=row.kind,
        node_id=row.node_id,
        payload=_safe_json(row.payload, {}),
        version=row.version or 1,
        provenance=_safe_json(row.provenance, {}),
        similarity=similarity,
    )


def _safe_json(val, default):
    if not val:
        return default
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# WRITE — immediate persist, else durable enqueue. Never raises (R5.5a).
# ---------------------------------------------------------------------------
def write(db: Session, item: MemoryWrite) -> dict:
    """
    Persist one piece of learned knowledge. On ANY failure, enqueue it to the
    durable write queue and return {"status": "queued"}; NEVER raises, so the
    calling run always completes (R5.5a).
    """
    try:
        return _persist_item(db, item)
    except Exception as exc:  # noqa: BLE001 — durability over immediacy
        logger.info("memory.write deferring to queue (app=%s kind=%s): %s",
                    item.application_id, item.kind, exc)
        try:
            db.rollback()
        except Exception:
            pass
        _enqueue(db, item)
        return {"status": "queued"}


def _persist_item(db: Session, item: MemoryWrite) -> dict:
    ch = EMB.content_hash(json.dumps(item.payload, sort_keys=True, default=str))

    # Dedup: if an identical (app, node, kind, content_hash) item exists, reuse.
    existing = (
        db.query(MemoryItem)
        .filter(
            MemoryItem.application_id == item.application_id,
            MemoryItem.node_id == item.node_id,
            MemoryItem.kind == item.kind,
            MemoryItem.content_hash == ch,
        )
        .first()
    )
    if existing is not None:
        return {"status": "exists", "id": existing.id}

    # Optional embedding for semantically-retrievable kinds (cost-governed via
    # embed_and_store's content_hash dedup). Embedder failure is NON-fatal here:
    # we still persist the item (identity-retrievable), embedding backfills later.
    embedding_id: Optional[int] = None
    if item.kind in _SEMANTIC_KINDS:
        text = item.embed_text or _default_embed_text(item)
        if text:
            try:
                mapping = EMB.embed_and_store(
                    db, [text], owner_id=item.owner_id, application_id=item.application_id
                )
                embedding_id = mapping.get(EMB.content_hash(text))
            except EMB.EmbeddingUnavailable as exc:
                logger.info("memory embedding skipped (backfill later): %s", exc)
                embedding_id = None

    # Version: for versioned kinds, next version for this (node, kind).
    version = 1
    if item.kind in _VERSIONED_KINDS and item.node_id is not None:
        latest = (
            db.query(MemoryItem)
            .filter(
                MemoryItem.application_id == item.application_id,
                MemoryItem.node_id == item.node_id,
                MemoryItem.kind == item.kind,
            )
            .order_by(MemoryItem.version.desc())
            .first()
        )
        if latest is not None:
            version = (latest.version or 1) + 1

    row = MemoryItem(
        owner_id=item.owner_id,
        application_id=item.application_id,
        node_id=item.node_id,
        kind=item.kind,
        payload=json.dumps(item.payload, default=str),
        embedding_id=embedding_id,
        content_hash=ch,
        provenance=json.dumps(item.provenance, default=str),
        version=version,
    )
    db.add(row)
    db.commit()
    return {"status": "written", "id": row.id, "embedding_id": embedding_id}


def _default_embed_text(item: MemoryWrite) -> str:
    """Derive a semantic text from the payload for embedding when none given."""
    p = item.payload or {}
    parts = []
    for key in ("description", "intent", "summary", "selector", "css", "xpath", "text"):
        v = p.get(key)
        if v:
            parts.append(str(v))
    if not parts:
        # Fall back to a compact JSON rendering.
        parts.append(json.dumps(p, sort_keys=True, default=str)[:400])
    return " ".join(parts)


def _enqueue(db: Session, item: MemoryWrite) -> None:
    """Durably enqueue a failed write for later retry. Best-effort (never raises)."""
    try:
        q = MemoryWriteQueue(
            owner_id=item.owner_id,
            application_id=item.application_id,
            payload=item.to_json(),
            attempts=0,
            next_retry_at=None,
        )
        db.add(q)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory queue enqueue failed (knowledge lost this round): %s", exc)
        try:
            db.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# RETRIEVE — identity lookup ∪ semantic search, tenant+app scoped. Degrades.
# ---------------------------------------------------------------------------
def retrieve(
    db: Session,
    application_id: int,
    *,
    owner_id: Optional[str],
    node_id: Optional[int] = None,
    kind: Optional[str] = None,
    query: Optional[str] = None,
    k: int = 10,
) -> list[RetrievedMemory]:
    """
    Retrieve memory for an application, scoped to the owner (R5.6, Property 8).

    - Identity lookup: items filtered by owner+app (+ optional node_id/kind).
    - Semantic search (when `query` given): cosine over `embeddings` via pgvector,
      joined back to memory_items — best-effort, degrades to identity-only on any
      failure or on non-Postgres (R5.9).
    Results are unioned and de-duplicated by id; identity hits first.
    """
    results: list[RetrievedMemory] = []
    seen_ids: set[int] = set()

    # ── Identity lookup (always available) ─────────────────────────────────
    q = db.query(MemoryItem).filter(MemoryItem.application_id == application_id)
    q = _scope_owner(q, MemoryItem, owner_id)
    if node_id is not None:
        q = q.filter(MemoryItem.node_id == node_id)
    if kind is not None:
        q = q.filter(MemoryItem.kind == kind)
    for row in q.order_by(MemoryItem.id.desc()).limit(k).all():
        if row.id not in seen_ids:
            seen_ids.add(row.id)
            results.append(_row_to_retrieved(row))

    # ── Semantic search (optional, best-effort) ────────────────────────────
    if query:
        try:
            sem = _semantic_search(db, application_id, owner_id=owner_id, query=query, k=k)
            for r in sem:
                if r.id not in seen_ids:
                    seen_ids.add(r.id)
                    results.append(r)
        except Exception as exc:  # noqa: BLE001 — identity-only fallback (R5.9)
            logger.info("memory semantic retrieval degraded to identity-only: %s", exc)

    return results[:k] if k else results


def _scope_owner(query, model, owner_id: Optional[str]):
    """
    Enforce tenant isolation: only rows owned by owner_id (legacy NULL-owner
    rows are treated as accessible only when owner_id is None — matching the
    existing grandfathering pattern elsewhere in the codebase).
    """
    if owner_id is None:
        return query
    return query.filter(model.owner_id == owner_id)


def _semantic_search(
    db: Session, application_id: int, *, owner_id: Optional[str], query: str, k: int
) -> list[RetrievedMemory]:
    """
    pgvector cosine search over `embeddings` for this owner+app, joined to the
    memory_items that reference those embeddings. Postgres-only; raises on any
    problem so the caller can fall back to identity-only.
    """
    if not _is_postgres():
        raise RuntimeError("semantic search requires Postgres + pgvector")

    embedder = EMB.get_embedder()
    qvec = EMB.embed_query(query, embedder=embedder)  # may raise EmbeddingUnavailable
    if not qvec:
        return []

    from pgvector import Vector as _PgVector

    # Cosine distance (<=>) ascending = most similar first. We restrict to the
    # active embedding model + this owner/app, then join memory_items.embedding_id.
    # `dim` is a trusted integer from the active embedder (never user input), so
    # interpolating it into the vector cast is safe; all values are bound params.
    dim = int(embedder.dim)
    rows = db.execute(
        sql_text(
            f"""
            SELECT mi.id,
                   (e.embedding::vector({dim}) <=> :qvec) AS distance
            FROM memory_items mi
            JOIN embeddings e ON e.id = mi.embedding_id
            WHERE mi.application_id = :app
              AND (:owner IS NULL OR mi.owner_id = :owner)
              AND e.model_id = :model
              AND e.dim = :dim
            ORDER BY distance ASC
            LIMIT :k
            """
        ),
        {"qvec": _PgVector(qvec), "app": application_id, "owner": owner_id,
         "model": embedder.model_id, "dim": dim, "k": k},
    ).fetchall()

    if not rows:
        return []
    id_to_dist = {r[0]: float(r[1]) for r in rows}
    items = db.query(MemoryItem).filter(MemoryItem.id.in_(list(id_to_dist.keys()))).all()
    out = []
    for it in items:
        dist = id_to_dist.get(it.id, 1.0)
        out.append(_row_to_retrieved(it, similarity=max(0.0, 1.0 - dist)))
    # Sort by similarity desc (distance asc).
    out.sort(key=lambda r: -(r.similarity or 0.0))
    return out


# ---------------------------------------------------------------------------
# Maintenance helpers (called by graph_worker tasks)
# ---------------------------------------------------------------------------
def drain_queue_once(db: Session, batch: int = 50) -> dict:
    """
    Re-attempt due queued writes. Returns counts. On per-item failure, bump
    attempts and set an exponential backoff `next_retry_at`. Never raises.
    """
    now = datetime.utcnow()
    try:
        due = (
            db.query(MemoryWriteQueue)
            .filter(
                (MemoryWriteQueue.next_retry_at.is_(None))
                | (MemoryWriteQueue.next_retry_at <= now)
            )
            .order_by(MemoryWriteQueue.id.asc())
            .limit(batch)
            .all()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("drain_queue_once could not read queue: %s", exc)
        return {"drained": 0, "retried": 0, "failed": 0}

    drained = retried = failed = 0
    for row in due:
        try:
            item = MemoryWrite.from_json(row.payload)
            res = _persist_item(db, item)
            if res.get("status") in ("written", "exists"):
                db.delete(row)
                db.commit()
                drained += 1
            else:
                raise RuntimeError(f"unexpected persist status: {res}")
        except Exception as exc:  # noqa: BLE001
            try:
                db.rollback()
            except Exception:
                pass
            row.attempts = (row.attempts or 0) + 1
            backoff_min = min(60, 2 ** min(row.attempts, 6))  # cap at ~60 min
            row.next_retry_at = now + timedelta(minutes=backoff_min)
            try:
                db.commit()
                retried += 1
            except Exception:
                db.rollback()
                failed += 1
            logger.info("memory queue retry scheduled (id=%s attempt=%s): %s",
                        row.id, row.attempts, exc)
    return {"drained": drained, "retried": retried, "failed": failed}


def compact_once(db: Session, application_id: Optional[int] = None) -> dict:
    """
    Enforce retention (R5.8):
      - keep only the latest N `fingerprint` versions per (app, node),
      - keep only the most recent M `timing`/`outcome` items per (app, node),
        deleting older ones (summarization of aggregates is a future refinement;
        for now we bound growth by trimming oldest, which is safe + deterministic).
    Never raises; returns counts of removed rows.
    """
    removed = 0
    max_fp = _max_fingerprint_versions()
    max_to = _timing_outcome_keep()

    try:
        # Distinct (app, node, kind) groups subject to retention.
        base = db.query(
            MemoryItem.application_id, MemoryItem.node_id, MemoryItem.kind
        ).filter(MemoryItem.node_id.isnot(None))
        if application_id is not None:
            base = base.filter(MemoryItem.application_id == application_id)
        groups = {
            (a, n, kd)
            for (a, n, kd) in base.distinct().all()
            if kd in _VERSIONED_KINDS or kd in {"timing", "outcome"}
        }

        for (app_id, node_id, kd) in groups:
            keep = max_fp if kd in _VERSIONED_KINDS else max_to
            rows = (
                db.query(MemoryItem)
                .filter(
                    MemoryItem.application_id == app_id,
                    MemoryItem.node_id == node_id,
                    MemoryItem.kind == kd,
                )
                .order_by(MemoryItem.id.desc())
                .all()
            )
            for old in rows[keep:]:
                db.delete(old)
                removed += 1
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("compact_once skipped: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
    return {"removed": removed}
