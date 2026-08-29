"""
Task 15 tests — memory wired into workers + transparency endpoint.

Covers the guarded worker helpers (hint retrieval + outcome write-back keyed to
a test's linked node) and the owner-scoped GET /api/applications/{id}/memory.
Browser execution itself is not run; we test the helpers and endpoint directly.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user
from app.database import SessionLocal, engine, Base
from app.models import (
    Application, GraphNode, TestCase, CoverageLink,
    MemoryItem, MemoryWriteQueue,
)
from app import worker as W

Base.metadata.create_all(bind=engine)

OWNER = f"MEMWIRE_{uuid.uuid4().hex[:8]}"
OTHER = f"OTHER_{uuid.uuid4().hex[:8]}"

_current = {"sub": OWNER}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: dict(_current)
    yield
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)


def _seed_linked_test(owner: str) -> tuple[int, int, int]:
    """Create app + graph node + test case + coverage link. Returns ids."""
    db = SessionLocal()
    try:
        app_row = Application(owner_id=owner, name="MemWire", base_url="https://s.com")
        db.add(app_row); db.flush()
        node = GraphNode(owner_id=owner, application_id=app_row.id,
                         canonical_key=uuid.uuid4().hex[:16], node_type="page",
                         label="Login", status="active")
        db.add(node); db.flush()
        tc = TestCase(owner_id=owner, name="Login test", prompt="log in")
        db.add(tc); db.flush()
        db.add(CoverageLink(owner_id=owner, application_id=app_row.id,
                            node_id=node.id, test_case_id=tc.id, source="generated"))
        db.commit()
        return app_row.id, node.id, tc.id
    finally:
        db.close()


def _cleanup(owner: str):
    db = SessionLocal()
    try:
        app_ids = [a.id for a in db.query(Application).filter(Application.owner_id == owner).all()]
        if app_ids:
            db.query(MemoryItem).filter(MemoryItem.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(MemoryWriteQueue).filter(MemoryWriteQueue.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(CoverageLink).filter(CoverageLink.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        db.query(TestCase).filter(TestCase.owner_id == owner).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_outcome_writeback_and_hint_roundtrip():
    try:
        app_id, node_id, tc_id = _seed_linked_test(OWNER)

        # Simulate a completed run → write outcome + timing memory for the node.
        W._write_run_outcome_memory(tc_id, is_successful=True, duration_seconds=3)

        db = SessionLocal()
        try:
            kinds = {m.kind for m in db.query(MemoryItem).filter(
                MemoryItem.application_id == app_id).all()}
            assert "outcome" in kinds
            assert "timing" in kinds
        finally:
            db.close()

        # A locator memory → the hint block should surface it for the linked test.
        db = SessionLocal()
        try:
            from app import memory as MEM
            MEM.write(db, MEM.MemoryWrite(application_id=app_id, kind="locator",
                                          owner_id=OWNER, node_id=node_id,
                                          payload={"selector": "#login-btn"}))
        finally:
            db.close()

        hint = W._memory_hints_for_test(tc_id)
        assert hint is not None
        assert "#login-btn" in hint
        assert "LEAKA MEMORY" in hint
    finally:
        _cleanup(OWNER)


def test_hint_is_none_for_unlinked_test():
    # A test with no coverage link → no hint, no error.
    db = SessionLocal()
    try:
        tc = TestCase(owner_id=OWNER, name="Unlinked", prompt="do a thing")
        db.add(tc); db.commit()
        tc_id = tc.id
    finally:
        db.close()
    try:
        assert W._memory_hints_for_test(tc_id) is None
        # Write-back is a no-op (guarded) for an unlinked test.
        W._write_run_outcome_memory(tc_id, is_successful=False, duration_seconds=1)
    finally:
        _cleanup(OWNER)


def test_memory_endpoint_owner_scoped_and_filterable():
    try:
        app_id, node_id, tc_id = _seed_linked_test(OWNER)
        W._write_run_outcome_memory(tc_id, is_successful=True, duration_seconds=2)

        # Owner sees their memory.
        _current["sub"] = OWNER
        r = client.get(f"/api/applications/{app_id}/memory")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 1
        kinds = {it["kind"] for it in body["items"]}
        assert "outcome" in kinds

        # Filter by kind.
        r2 = client.get(f"/api/applications/{app_id}/memory?kind=timing")
        assert all(it["kind"] == "timing" for it in r2.json()["items"])

        # Cross-tenant → 404, never data.
        _current["sub"] = OTHER
        assert client.get(f"/api/applications/{app_id}/memory").status_code == 404
    finally:
        _current["sub"] = OWNER
        _cleanup(OWNER)
