"""
Migration M4 + memory model tests (Task 13, Requirements 5.1, 5.5a, 11.1).

Verifies the memory tables are created idempotently, the dedup unique
constraint on memory_items holds, and the write queue accepts durable rows.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, engine, Base, init_db
from app.migrations import run_migrations
from app.models import (
    Application, GraphNode, MemoryItem, MemoryWriteQueue,
)

init_db()
Base.metadata.create_all(bind=engine)


def test_m4_is_idempotent_and_creates_tables():
    run_migrations()
    run_migrations()  # twice — must not error
    insp = inspect(engine)
    tables = insp.get_table_names()
    assert "memory_items" in tables
    assert "memory_write_queue" in tables


def _seed_node(owner: str) -> tuple[int, int]:
    db = SessionLocal()
    try:
        app_row = Application(owner_id=owner, name="MemApp", base_url="https://s.com")
        db.add(app_row); db.flush()
        node = GraphNode(
            owner_id=owner, application_id=app_row.id,
            canonical_key=uuid.uuid4().hex[:16], node_type="page", label="Login",
            status="active",
        )
        db.add(node)
        db.commit()
        return app_row.id, node.id
    finally:
        db.close()


def _cleanup(owner: str):
    db = SessionLocal()
    try:
        app_ids = [a.id for a in db.query(Application).filter(Application.owner_id == owner).all()]
        if app_ids:
            db.query(MemoryItem).filter(MemoryItem.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(MemoryWriteQueue).filter(MemoryWriteQueue.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_memory_item_dedup_per_app_node_kind_hash():
    owner = f"MEMM4_{uuid.uuid4().hex[:8]}"
    try:
        app_id, node_id = _seed_node(owner)
        db = SessionLocal()
        try:
            db.add(MemoryItem(
                owner_id=owner, application_id=app_id, node_id=node_id,
                kind="locator", payload=json.dumps({"css": "#login"}),
                content_hash="abc123", version=1,
            ))
            db.commit()
            # Same (app, node, kind, content_hash) must violate the unique index.
            db.add(MemoryItem(
                owner_id=owner, application_id=app_id, node_id=node_id,
                kind="locator", payload=json.dumps({"css": "#login2"}),
                content_hash="abc123", version=2,
            ))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        finally:
            db.close()
    finally:
        _cleanup(owner)


def test_memory_write_queue_accepts_rows():
    owner = f"MEMM4_{uuid.uuid4().hex[:8]}"
    try:
        app_id, _ = _seed_node(owner)
        db = SessionLocal()
        try:
            q = MemoryWriteQueue(
                owner_id=owner, application_id=app_id,
                payload=json.dumps({"kind": "timing", "payload": {"ms": 2500}}),
                attempts=0, next_retry_at=None,
            )
            db.add(q)
            db.commit()
            assert q.id is not None
            assert q.attempts == 0
        finally:
            db.close()
    finally:
        _cleanup(owner)
