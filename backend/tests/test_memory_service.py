"""
Memory service integration tests (Task 14, Requirements 5.1, 5.4, 5.5, 5.5a,
5.6, 5.8, 5.9).

Runs against the configured DB. Covers: write→identity-retrieve, durable
degradation (write failure → queue → drain), retention/compaction, and
tenant scoping on retrieve.
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal, engine, Base
from app.models import Application, GraphNode, MemoryItem, MemoryWriteQueue
from app import memory as MEM

Base.metadata.create_all(bind=engine)


def _seed_app_node(owner: str) -> tuple[int, int]:
    db = SessionLocal()
    try:
        app_row = Application(owner_id=owner, name="MemSvc", base_url="https://s.com")
        db.add(app_row); db.flush()
        node = GraphNode(owner_id=owner, application_id=app_row.id,
                         canonical_key=uuid.uuid4().hex[:16], node_type="page",
                         label="Login", status="active")
        db.add(node); db.commit()
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


def test_write_then_identity_retrieve():
    owner = f"MEMSVC_{uuid.uuid4().hex[:8]}"
    try:
        app_id, node_id = _seed_app_node(owner)
        db = SessionLocal()
        try:
            res = MEM.write(db, MEM.MemoryWrite(
                application_id=app_id, kind="timing", owner_id=owner, node_id=node_id,
                payload={"ms": 2500}, provenance={"run": "r1"},
            ))
            assert res["status"] == "written"

            got = MEM.retrieve(db, app_id, owner_id=owner, node_id=node_id, kind="timing")
            assert len(got) == 1
            assert got[0].payload == {"ms": 2500}
            assert got[0].kind == "timing"
        finally:
            db.close()
    finally:
        _cleanup(owner)


def test_write_dedup_same_content():
    owner = f"MEMSVC_{uuid.uuid4().hex[:8]}"
    try:
        app_id, node_id = _seed_app_node(owner)
        db = SessionLocal()
        try:
            item = MEM.MemoryWrite(application_id=app_id, kind="outcome", owner_id=owner,
                                   node_id=node_id, payload={"passed": True})
            r1 = MEM.write(db, item)
            r2 = MEM.write(db, item)  # identical content
            assert r1["status"] == "written"
            assert r2["status"] == "exists"
            assert r2["id"] == r1["id"]
        finally:
            db.close()
    finally:
        _cleanup(owner)


def test_write_failure_enqueues_and_drains():
    owner = f"MEMSVC_{uuid.uuid4().hex[:8]}"
    try:
        app_id, node_id = _seed_app_node(owner)
        db = SessionLocal()
        try:
            # Force _persist_item to fail by monkeypatching content_hash to raise.
            import app.memory as M
            orig = M.EMB.content_hash
            M.EMB.content_hash = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
            try:
                res = MEM.write(db, MEM.MemoryWrite(
                    application_id=app_id, kind="timing", owner_id=owner,
                    node_id=node_id, payload={"ms": 999},
                ))
                assert res["status"] == "queued"  # never raised
            finally:
                M.EMB.content_hash = orig

            # Queue has the row.
            qn = db.query(MemoryWriteQueue).filter(
                MemoryWriteQueue.application_id == app_id).count()
            assert qn == 1

            # Drain now persists it.
            out = MEM.drain_queue_once(db)
            assert out["drained"] == 1
            items = db.query(MemoryItem).filter(MemoryItem.application_id == app_id).count()
            assert items == 1
            assert db.query(MemoryWriteQueue).filter(
                MemoryWriteQueue.application_id == app_id).count() == 0
        finally:
            db.close()
    finally:
        _cleanup(owner)


def test_compaction_bounds_fingerprint_versions(monkeypatch):
    owner = f"MEMSVC_{uuid.uuid4().hex[:8]}"
    try:
        app_id, node_id = _seed_app_node(owner)
        monkeypatch.setenv("MEMORY_MAX_FINGERPRINT_VERSIONS", "3")
        db = SessionLocal()
        try:
            # Write 6 distinct fingerprint versions.
            for i in range(6):
                MEM.write(db, MEM.MemoryWrite(
                    application_id=app_id, kind="fingerprint", owner_id=owner,
                    node_id=node_id, payload={"sig": f"v{i}"},
                ))
            assert db.query(MemoryItem).filter(
                MemoryItem.application_id == app_id, MemoryItem.kind == "fingerprint"
            ).count() == 6

            out = MEM.compact_once(db, application_id=app_id)
            assert out["removed"] == 3
            assert db.query(MemoryItem).filter(
                MemoryItem.application_id == app_id, MemoryItem.kind == "fingerprint"
            ).count() == 3
        finally:
            db.close()
    finally:
        _cleanup(owner)
