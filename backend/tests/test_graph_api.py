"""
API tests for the Application Graph endpoints (Task 7).

Uses FastAPI's TestClient with dependency_overrides to inject a fake auth'd
user (the standard FastAPI testing approach), exercising the REAL endpoint
logic and owner-scoping against the configured DB. Two distinct owners verify
tenant isolation (404 on cross-tenant, Property 8 shape).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user
from app.database import SessionLocal, engine, Base
from app.models import (
    Application, ExploreRun, ExploreRunStatus, AppMapNode,
    GraphNode, GraphEdge, GraphSnapshot, SnapshotMember, NodeFingerprint,
    CoverageVerdict, CoverageLink,
)
from app import graph_worker as G

Base.metadata.create_all(bind=engine)

OWNER_A = f"APITEST_A_{uuid.uuid4().hex[:8]}"
OWNER_B = f"APITEST_B_{uuid.uuid4().hex[:8]}"

_current_owner = {"sub": OWNER_A}


def _fake_user():
    return dict(_current_owner)


@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[get_current_user] = _fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)


def _as(owner: str):
    _current_owner["sub"] = owner


def _seed_reconciled_app(owner: str, nodes: list[dict]) -> int:
    """Create an app + completed explore run + AppMapNodes, then reconcile."""
    db = SessionLocal()
    try:
        app_row = Application(owner_id=owner, name="APITestApp", base_url="https://s.com")
        db.add(app_row)
        db.flush()
        run = ExploreRun(
            owner_id=owner, application_id=app_row.id,
            job_id=f"job-{uuid.uuid4().hex[:12]}", status=ExploreRunStatus.COMPLETED,
        )
        db.add(run)
        db.flush()
        for n in nodes:
            db.add(AppMapNode(
                owner_id=owner, application_id=app_row.id, explore_run_id=run.id,
                node_type=n.get("node_type", "page"), label=n["label"], url=n.get("url"),
            ))
        db.commit()
        app_id, run_id = app_row.id, run.id
    finally:
        db.close()
    G.reconcile_explore.run(run_id)
    return app_id


def _settle():
    """Wait for background coverage-recompute tasks enqueued by reconcile/reads."""
    import time
    time.sleep(0.3)
    ex = getattr(G, "_SYNC_EXECUTOR", None)
    if ex is not None:
        try:
            futures = [ex.submit(lambda: None) for _ in range(4)]
            for f in futures:
                f.result(timeout=30)
        except Exception:
            pass


def _cleanup(owner: str):
    _settle()
    db = SessionLocal()
    try:
        app_ids = [a.id for a in db.query(Application).filter(Application.owner_id == owner).all()]
        if app_ids:
            snap_ids = [s.id for s in db.query(GraphSnapshot).filter(GraphSnapshot.application_id.in_(app_ids)).all()]
            if snap_ids:
                db.query(SnapshotMember).filter(SnapshotMember.snapshot_id.in_(snap_ids)).delete(synchronize_session=False)
                db.query(GraphSnapshot).filter(GraphSnapshot.id.in_(snap_ids)).delete(synchronize_session=False)
            node_ids = [n.id for n in db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).all()]
            if node_ids:
                db.query(NodeFingerprint).filter(NodeFingerprint.node_id.in_(node_ids)).delete(synchronize_session=False)
            db.query(CoverageLink).filter(CoverageLink.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(CoverageVerdict).filter(CoverageVerdict.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(GraphEdge).filter(GraphEdge.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(AppMapNode).filter(AppMapNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(ExploreRun).filter(ExploreRun.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_graph_endpoint_returns_nodes_and_empty_state():
    _as(OWNER_A)
    try:
        app_id = _seed_reconciled_app(OWNER_A, [
            {"label": "Login", "url": "https://s.com/login"},
            {"label": "Cart", "url": "https://s.com/cart"},
        ])
        r = client.get(f"/api/applications/{app_id}/graph")
        assert r.status_code == 200
        body = r.json()
        assert body["is_empty"] is False
        assert body["total_nodes"] == 2
        assert {n["label"] for n in body["nodes"]} == {"Login", "Cart"}
        assert all(n["status"] == "active" for n in body["nodes"])
    finally:
        _cleanup(OWNER_A)


def test_empty_graph_is_explicit_not_error():
    _as(OWNER_A)
    db = SessionLocal()
    try:
        app_row = Application(owner_id=OWNER_A, name="Empty", base_url="https://s.com")
        db.add(app_row)
        db.commit()
        app_id = app_row.id
    finally:
        db.close()
    try:
        r = client.get(f"/api/applications/{app_id}/graph")
        assert r.status_code == 200
        body = r.json()
        assert body["is_empty"] is True
        assert body["total_nodes"] == 0
        assert body["nodes"] == []
    finally:
        _cleanup(OWNER_A)


def test_cross_tenant_graph_is_404():
    _as(OWNER_A)
    try:
        app_id = _seed_reconciled_app(OWNER_A, [{"label": "Login", "url": "https://s.com/login"}])
        # Owner B must not see owner A's graph — 404, never 403, never data.
        _as(OWNER_B)
        r = client.get(f"/api/applications/{app_id}/graph")
        assert r.status_code == 404
    finally:
        _as(OWNER_A)
        _cleanup(OWNER_A)


def test_node_override_is_authoritative_and_audited():
    _as(OWNER_A)
    try:
        app_id = _seed_reconciled_app(OWNER_A, [{"label": "Billing", "url": "https://s.com/billing"}])
        g = client.get(f"/api/applications/{app_id}/graph").json()
        node_id = g["nodes"][0]["id"]

        r = client.patch(
            f"/api/applications/{app_id}/graph/nodes/{node_id}",
            json={"business_category": "billing", "role_association": "admin",
                  "risk": {"level": "Critical", "score": 95}},
        )
        assert r.status_code == 200
        detail = r.json()
        assert detail["business_category"] == "billing"
        assert detail["role_association"] == "admin"
        assert detail["risk"] == {"level": "Critical", "score": 95}
        # manual_overrides persisted with provenance for audit.
        assert detail["manual_overrides"]["business_category"] == "billing"
        assert detail["provenance"]["overrides"], "override provenance not recorded"

        # A re-explore (reconcile) must NOT revert the human correction.
        db = SessionLocal()
        try:
            run = ExploreRun(
                owner_id=OWNER_A, application_id=app_id,
                job_id=f"job-{uuid.uuid4().hex[:12]}", status=ExploreRunStatus.COMPLETED,
            )
            db.add(run); db.flush()
            db.add(AppMapNode(owner_id=OWNER_A, application_id=app_id, explore_run_id=run.id,
                              node_type="page", label="Billing", url="https://s.com/billing"))
            db.commit()
            run_id = run.id
        finally:
            db.close()
        G.reconcile_explore.run(run_id)

        after = client.get(f"/api/applications/{app_id}/graph/nodes/{node_id}").json()
        assert after["business_category"] == "billing", "reconcile reverted a manual override"
        assert after["role_association"] == "admin"
    finally:
        _cleanup(OWNER_A)


def test_snapshots_list_and_diff():
    _as(OWNER_A)
    try:
        app_id = _seed_reconciled_app(OWNER_A, [{"label": "Login", "url": "https://s.com/login"}])
        # Second run adds a node → a second snapshot with a non-empty diff.
        db = SessionLocal()
        try:
            run = ExploreRun(owner_id=OWNER_A, application_id=app_id,
                             job_id=f"job-{uuid.uuid4().hex[:12]}", status=ExploreRunStatus.COMPLETED)
            db.add(run); db.flush()
            for lbl, url in [("Login", "https://s.com/login"), ("Cart", "https://s.com/cart")]:
                db.add(AppMapNode(owner_id=OWNER_A, application_id=app_id, explore_run_id=run.id,
                                  node_type="page", label=lbl, url=url))
            db.commit(); run_id = run.id
        finally:
            db.close()
        G.reconcile_explore.run(run_id)

        lst = client.get(f"/api/applications/{app_id}/snapshots").json()
        assert lst["total"] == 2
        ids = sorted(s["id"] for s in lst["snapshots"])
        older, newer = ids[0], ids[1]

        d = client.get(f"/api/applications/{app_id}/snapshots/{older}/diff/{newer}")
        assert d.status_code == 200
        diff = d.json()["diff"]
        assert diff["counts"]["added"] == 1  # Cart was added
        assert "cart" not in diff["removed"]
    finally:
        _cleanup(OWNER_A)
