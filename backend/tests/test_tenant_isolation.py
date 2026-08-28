"""
Property 8 — Tenant isolation (Requirements 9.1, 9.2).

  "For any resource, a query by a non-owner returns empty/404 — no cross-tenant
   row is ever returned."

Validated across the memory service (retrieve) and the graph/coverage/snapshot
API reads, with randomized owner ids. Uses the configured DB + a mockable auth
dependency for the API layer.
"""

from __future__ import annotations

import uuid

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user
from app.database import SessionLocal, engine, Base
from app.models import (
    Application, GraphNode, MemoryItem, MemoryWriteQueue,
    CoverageVerdict, CoverageLink, GraphEdge, GraphSnapshot, SnapshotMember,
    NodeFingerprint,
)
from app import memory as MEM

Base.metadata.create_all(bind=engine)

_current = {"sub": "unset"}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: dict(_current)
    yield
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)


def _seed_app_with_memory(owner: str) -> tuple[int, int]:
    db = SessionLocal()
    try:
        app_row = Application(owner_id=owner, name="Iso", base_url="https://s.com")
        db.add(app_row); db.flush()
        node = GraphNode(owner_id=owner, application_id=app_row.id,
                         canonical_key=uuid.uuid4().hex[:16], node_type="page",
                         label="Secret", status="active")
        db.add(node); db.commit()
        app_id, node_id = app_row.id, node.id
    finally:
        db.close()
    db = SessionLocal()
    try:
        MEM.write(db, MEM.MemoryWrite(application_id=app_id, kind="timing",
                                      owner_id=owner, node_id=node_id, payload={"ms": 42}))
    finally:
        db.close()
    return app_id, node_id


def _cleanup(owner: str):
    db = SessionLocal()
    try:
        app_ids = [a.id for a in db.query(Application).filter(Application.owner_id == owner).all()]
        if app_ids:
            db.query(MemoryItem).filter(MemoryItem.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(MemoryWriteQueue).filter(MemoryWriteQueue.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(CoverageLink).filter(CoverageLink.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(CoverageVerdict).filter(CoverageVerdict.application_id.in_(app_ids)).delete(synchronize_session=False)
            node_ids = [n.id for n in db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).all()]
            if node_ids:
                db.query(NodeFingerprint).filter(NodeFingerprint.node_id.in_(node_ids)).delete(synchronize_session=False)
            db.query(GraphEdge).filter(GraphEdge.application_id.in_(app_ids)).delete(synchronize_session=False)
            snap_ids = [s.id for s in db.query(GraphSnapshot).filter(GraphSnapshot.application_id.in_(app_ids)).all()]
            if snap_ids:
                db.query(SnapshotMember).filter(SnapshotMember.snapshot_id.in_(snap_ids)).delete(synchronize_session=False)
                db.query(GraphSnapshot).filter(GraphSnapshot.id.in_(snap_ids)).delete(synchronize_session=False)
            db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


_OWNER_ID = st.text(alphabet="abcdefghijklmnop0123456789", min_size=6, max_size=12)


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
@given(data=st.data())
def test_memory_retrieve_is_tenant_scoped(data):
    """A non-owner's retrieve() over another owner's app returns nothing."""
    owner_a = "A_" + data.draw(_OWNER_ID)
    owner_b = "B_" + data.draw(_OWNER_ID)
    if owner_a == owner_b:
        owner_b += "x"
    try:
        app_id, node_id = _seed_app_with_memory(owner_a)
        db = SessionLocal()
        try:
            # Owner A sees their memory.
            own = MEM.retrieve(db, app_id, owner_id=owner_a, node_id=node_id)
            assert len(own) == 1
            # Owner B sees NOTHING for owner A's app (tenant isolation).
            other = MEM.retrieve(db, app_id, owner_id=owner_b, node_id=node_id)
            assert other == []
        finally:
            db.close()
    finally:
        _cleanup(owner_a)


@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
@given(data=st.data())
def test_graph_and_coverage_reads_are_404_cross_tenant(data):
    """Graph / coverage / snapshot reads by a non-owner return 404, never data."""
    owner_a = "A_" + data.draw(_OWNER_ID)
    owner_b = "B_" + data.draw(_OWNER_ID)
    if owner_a == owner_b:
        owner_b += "x"
    try:
        app_id, node_id = _seed_app_with_memory(owner_a)

        # Owner B (non-owner) must get 404 on every read surface.
        _current["sub"] = owner_b
        assert client.get(f"/api/applications/{app_id}/graph").status_code == 404
        assert client.get(f"/api/applications/{app_id}/graph/nodes/{node_id}").status_code == 404
        assert client.get(f"/api/applications/{app_id}/coverage").status_code == 404
        assert client.get(f"/api/applications/{app_id}/snapshots").status_code == 404

        # Owner A still has access (sanity).
        _current["sub"] = owner_a
        assert client.get(f"/api/applications/{app_id}/graph").status_code == 200
    finally:
        _cleanup(owner_a)
