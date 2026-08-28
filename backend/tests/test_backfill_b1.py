"""
Backfill B1 integration test (Task 8, Requirements 11.2, 11.3).

Verifies that existing AppMapNodes for an already-explored application are
upgraded into a GraphNode set + an initial snapshot, preserving their data,
that the legacy `/map` heuristic endpoint keeps working throughout, and that
the backfill is idempotent (re-running creates no duplicate nodes/graphs).
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
)
from app import graph_worker as G

Base.metadata.create_all(bind=engine)

OWNER = f"B1TEST_{uuid.uuid4().hex[:8]}"
_current = {"sub": OWNER}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: dict(_current)
    yield
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)


def _seed_legacy_app(with_run: bool) -> int:
    """
    Create an application with AppMapNodes but NO graph. If with_run is False,
    the AppMapNodes have a NULL explore_run_id (legacy shape).
    """
    db = SessionLocal()
    try:
        app_row = Application(owner_id=OWNER, name="Legacy", base_url="https://saucedemo.com")
        db.add(app_row)
        db.flush()

        run_id = None
        if with_run:
            run = ExploreRun(
                owner_id=OWNER, application_id=app_row.id,
                job_id=f"job-{uuid.uuid4().hex[:12]}", status=ExploreRunStatus.COMPLETED,
            )
            db.add(run)
            db.flush()
            run_id = run.id

        for lbl, url, desc, prompt in [
            ("Login", "https://saucedemo.com/", "Login page", "Log in with valid creds"),
            ("Inventory", "https://saucedemo.com/inventory.html", "Product list", "Verify products load"),
            ("Cart", "https://saucedemo.com/cart.html", "Shopping cart", "Add item and open cart"),
        ]:
            db.add(AppMapNode(
                owner_id=OWNER, application_id=app_row.id, explore_run_id=run_id,
                node_type="page", label=lbl, url=url, description=desc, suggested_prompt=prompt,
            ))
        db.commit()
        return app_row.id
    finally:
        db.close()


def _cleanup():
    db = SessionLocal()
    try:
        app_ids = [a.id for a in db.query(Application).filter(Application.owner_id == OWNER).all()]
        if app_ids:
            snap_ids = [s.id for s in db.query(GraphSnapshot).filter(GraphSnapshot.application_id.in_(app_ids)).all()]
            if snap_ids:
                db.query(SnapshotMember).filter(SnapshotMember.snapshot_id.in_(snap_ids)).delete(synchronize_session=False)
                db.query(GraphSnapshot).filter(GraphSnapshot.id.in_(snap_ids)).delete(synchronize_session=False)
            node_ids = [n.id for n in db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).all()]
            if node_ids:
                db.query(NodeFingerprint).filter(NodeFingerprint.node_id.in_(node_ids)).delete(synchronize_session=False)
            from app.models import CoverageLink as _CL, CoverageVerdict as _CV
            db.query(_CL).filter(_CL.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(_CV).filter(_CV.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(GraphEdge).filter(GraphEdge.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(AppMapNode).filter(AppMapNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(ExploreRun).filter(ExploreRun.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_backfill_creates_graph_and_preserves_map():
    try:
        app_id = _seed_legacy_app(with_run=True)

        # Precondition: /map works and shows 3 nodes; no graph yet.
        m = client.get(f"/api/applications/{app_id}/map").json()
        assert m["total_nodes"] == 3
        g_before = client.get(f"/api/applications/{app_id}/graph").json()
        assert g_before["is_empty"] is True

        # Run B1.
        out = G.backfill_all_pending()
        assert app_id in out["backfilled"]

        # Graph now exists with 3 nodes + an initial snapshot.
        g = client.get(f"/api/applications/{app_id}/graph").json()
        assert g["is_empty"] is False
        assert g["total_nodes"] == 3
        assert {n["label"] for n in g["nodes"]} == {"Login", "Inventory", "Cart"}
        # url_pattern preserved (normalized) for each.
        assert any(n["url_pattern"] == "/inventory.html" for n in g["nodes"])

        snaps = client.get(f"/api/applications/{app_id}/snapshots").json()
        assert snaps["total"] == 1

        # /map STILL works and is unchanged (backfill is additive).
        m2 = client.get(f"/api/applications/{app_id}/map").json()
        assert m2["total_nodes"] == 3
    finally:
        _cleanup()


def test_backfill_handles_legacy_null_run_nodes():
    try:
        app_id = _seed_legacy_app(with_run=False)  # AppMapNodes with NULL run
        out = G.backfill_application_graph(app_id)
        assert out["status"] == "completed"
        assert out["node_count"] == 3
        g = client.get(f"/api/applications/{app_id}/graph").json()
        assert g["total_nodes"] == 3
    finally:
        _cleanup()


def test_backfill_is_idempotent():
    try:
        app_id = _seed_legacy_app(with_run=True)
        G.backfill_all_pending()
        count1 = _graph_node_count(app_id)
        assert count1 == 3

        # Re-run backfill_all_pending — app already has a graph, so the guard
        # filters it out BEFORE processing: it appears in NO result bucket.
        out = G.backfill_all_pending()
        assert app_id not in out["backfilled"]
        assert app_id not in out["skipped"]
        assert app_id not in [f["application_id"] for f in out["failed"]]

        # Directly calling backfill again is also a no-op (MATCH, no dupes).
        again = G.backfill_application_graph(app_id)
        assert again["status"] == "completed"
        assert again["diff"]["added"] == 0
        assert _graph_node_count(app_id) == 3
    finally:
        _cleanup()


def _graph_node_count(app_id: int) -> int:
    db = SessionLocal()
    try:
        return db.query(GraphNode).filter(GraphNode.application_id == app_id).count()
    finally:
        db.close()
