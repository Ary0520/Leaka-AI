"""
Property 11 — Embedding dedup (Requirements 5.11).

"Embedding the same (content, model_id) twice performs at most one provider
call and yields exactly one embeddings row."

These tests run against the live embeddings table but use a FAKE provider that
counts calls, so they are fast (no real model load) and deterministic. They
clean up their own rows via a unique test owner_id.
"""

from __future__ import annotations

import uuid

import pytest
from hypothesis import given, settings, strategies as st
from sqlalchemy import text as sql_text

from app.database import SessionLocal, engine
from app.config import settings as app_settings
from app.intelligence import embeddings as E


pytestmark = pytest.mark.skipif(
    not app_settings.DATABASE_URL.startswith("postgres"),
    reason="embedding dedup test requires Postgres + pgvector",
)


class _CountingProvider:
    """A fake embedder that records how many texts it was asked to embed."""

    dim = 384
    model_id = "test/counting"

    def __init__(self) -> None:
        self.calls = 0
        self.embedded_texts: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.embedded_texts.extend(texts)
        # deterministic tiny vectors (dim 384)
        return [[float(len(t) % 7)] * self.dim for t in texts]


def _cleanup(owner_id: str) -> None:
    db = SessionLocal()
    try:
        db.execute(sql_text("DELETE FROM embeddings WHERE owner_id = :o"), {"o": owner_id})
        db.commit()
    finally:
        db.close()


@settings(max_examples=25, deadline=None)
@given(
    contents=st.lists(
        st.text(min_size=1, max_size=40),
        min_size=1,
        max_size=6,
    )
)
def test_embedding_dedup_property(contents: list[str]):
    """
    For any set of contents (with arbitrary duplicates), after embedding twice:
      - the provider is called at most once per UNIQUE content
      - the embeddings table holds exactly one row per unique content
    """
    owner = f"PROPTEST_{uuid.uuid4().hex[:12]}"
    provider = _CountingProvider()
    unique_count = len({c for c in contents})

    db = SessionLocal()
    try:
        # First pass
        E.embed_and_store(db, contents, owner_id=owner, application_id=1, embedder=provider)
        # Provider must have embedded each unique content at most once
        assert len(set(provider.embedded_texts)) <= unique_count
        assert provider.calls <= 1  # single batch call for the miss set

        rows_after_first = db.execute(
            sql_text("SELECT count(*) FROM embeddings WHERE owner_id = :o"),
            {"o": owner},
        ).scalar()
        assert rows_after_first == unique_count

        # Second pass with identical content — must add ZERO rows and ZERO new calls
        calls_before = provider.calls
        E.embed_and_store(db, contents, owner_id=owner, application_id=1, embedder=provider)
        rows_after_second = db.execute(
            sql_text("SELECT count(*) FROM embeddings WHERE owner_id = :o"),
            {"o": owner},
        ).scalar()

        assert rows_after_second == unique_count, "re-embedding created duplicate rows"
        assert provider.calls == calls_before, "re-embedding called the provider again"
    finally:
        db.close()
        _cleanup(owner)


def test_embedding_dedup_simple():
    """Concrete example: 3 inputs, 2 unique → 2 rows, 1 provider call, idempotent."""
    owner = f"PROPTEST_{uuid.uuid4().hex[:12]}"
    provider = _CountingProvider()
    db = SessionLocal()
    try:
        texts = ["alpha", "beta", "alpha"]
        m1 = E.embed_and_store(db, texts, owner_id=owner, application_id=1, embedder=provider)
        assert len(m1) == 2
        assert provider.calls == 1

        rows = db.execute(
            sql_text("SELECT count(*) FROM embeddings WHERE owner_id = :o"),
            {"o": owner},
        ).scalar()
        assert rows == 2

        m2 = E.embed_and_store(db, texts, owner_id=owner, application_id=1, embedder=provider)
        assert m2 == m1  # identical ids
        assert provider.calls == 1  # no new provider call
    finally:
        db.close()
        _cleanup(owner)
