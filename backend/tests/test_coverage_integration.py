"""
Integration tests for Task 12 — coverage recompute worker + /map supersession
+ /coverage endpoint + generate-test authoritative link.

Runs against the configured DB with a mocked auth user. RUN_MODE defaults to
sync_demo, so any dispatched recompute runs in a background thread; these tests
call recompute_coverage.run(...) directly for determinism.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user
from app.database import SessionLocal, engine, Base
from app.models import (
    Application, ExploreRun, ExploreRunStatus, AppMapNode, GraphNode,
    GraphSnapshot, SnapshotMember, NodeFingerprint, GraphEdge,
    CoverageVerdict, CoverageLink, TestCase,
)
from app import graph_worker as G

Base.metadata.create_all(bind=engine)

OWNER = f"COVINT_{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: {"sub": OWNER}
    yield
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)


def _seed_reconciled(nodes: list[dict]) -> tuple[int, int]:
    db = SessionLocal()
    try:
        app_row = Application(owner_id=OWNER, name="CovIntApp", base_url="https://s.com")
        db.add(app_row); db.flush()
        run = ExploreRun(owner_id=OWNER, application_id=app_row.id,
                         job_id=f"job-{uuid.uuid4().hex[:12]}", status=ExploreRunStatus.COMPLETED)
        db.add(run); db.flush()
        for n in nodes:
            db.add(AppMapNode(owner_id=OWNER, application_id=app_row.id, explore_run_id=run.id,
                              node_type=n.get("node_type", "page"), label=n["label"],
                              url=n.get("url"), suggested_prompt=n.get("prompt")))
        db.commit()
        app_id, run_id = app_row.id, run.id
    finally:
        db.close()
    G.reconcile_explore.run(run_id)  # builds graph (also enqueues recompute in bg)
    return app_id, run_id


def _cleanup():
    db = SessionLocal()
    try:
        app_ids = [a.id for a in db.query(Application).filter(Application.owner_id == OWNER).all()]
        if app_ids:
            db.query(CoverageLink).filter(CoverageLink.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(CoverageVerdict).filter(CoverageVerdict.application_id.in_(app_ids)).delete(synchronize_session=False)
            snap_ids = [s.id for s in db.query(GraphSnapshot).filter(GraphSnapshot.application_id.in_(app_ids)).all()]
            if snap_ids:
                db.query(SnapshotMember).filter(SnapshotMember.snapshot_id.in_(snap_ids)).delete(synchronize_session=False)
                db.query(GraphSnapshot).filter(GraphSnapshot.id.in_(snap_ids)).delete(synchronize_session=False)
            node_ids = [n.id for n in db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).all()]
            if node_ids:
                db.query(NodeFingerprint).filter(NodeFingerprint.node_id.in_(node_ids)).delete(synchronize_session=False)
            db.query(GraphEdge).filter(GraphEdge.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(AppMapNode).filter(AppMapNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(ExploreRun).filter(ExploreRun.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        db.query(TestCase).filter(TestCase.owner_id == OWNER).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_recompute_produces_verdicts_and_coverage_endpoint():
    try:
        app_id, _ = _seed_reconciled([
            {"label": "Login", "url": "https://s.com/login"},
            {"label": "Checkout", "url": "https://s.com/checkout"},
        ])
        out = G.recompute_coverage.run(app_id, "test")
        assert out["status"] == "completed"
        assert out["verdicts"] == 2

        cov = client.get(f"/api/applications/{app_id}/coverage").json()
        assert cov["is_empty"] is False
        assert cov["application_rollup"] is not None
        # No tests yet → all gaps, 0% coverage.
        assert cov["application_rollup"]["percent"] == 0.0
        assert cov["total_gaps"] == 2
        # Gaps ranked by risk (both similar here) — deterministic order present.
        assert all(g["state"] == "uncovered" for g in cov["gaps"])
    finally:
        _cleanup()


def test_generate_test_creates_link_and_flips_coverage():
    try:
        app_id, _ = _seed_reconciled([{"label": "Checkout", "url": "https://s.com/checkout",
                                       "prompt": "Complete checkout"}])
        # Get the real GraphNode id.
        g = client.get(f"/api/applications/{app_id}/graph").json()
        node_id = g["nodes"][0]["id"]

        # Generate a test FROM the node (authoritative link path, R4.3/R11.5).
        created = client.post("/api/test-cases", json={
            "name": "Checkout test", "prompt": "Complete checkout",
            "application_id": app_id, "node_id": node_id,
        })
        assert created.status_code == 200
        tc_id = created.json()["id"]

        # A CoverageLink now exists.
        db = SessionLocal()
        try:
            link = db.query(CoverageLink).filter(
                CoverageLink.application_id == app_id,
                CoverageLink.node_id == node_id,
                CoverageLink.test_case_id == tc_id,
            ).first()
            assert link is not None
            assert link.source == "generated"
        finally:
            db.close()

        # Recompute → the node flips to covered (linked test, no failing run).
        G.recompute_coverage.run(app_id, "after_link")
        cov = client.get(f"/api/applications/{app_id}/coverage").json()
        assert cov["application_rollup"]["covered_count"] == 1
        assert cov["total_gaps"] == 0

        # /map reflects covered via stored verdicts (superseded heuristic).
        m = client.get(f"/api/applications/{app_id}/map").json()
        assert m["covered_nodes"] == 1
    finally:
        _cleanup()


def test_map_falls_back_when_no_verdicts():
    try:
        # Seed an app whose AppMapNode label/url match a test case, but do NOT
        # build a graph → no verdicts → heuristic fallback should mark covered.
        db = SessionLocal()
        try:
            app_row = Application(owner_id=OWNER, name="Heur", base_url="https://s.com")
            db.add(app_row); db.flush()
            db.add(AppMapNode(owner_id=OWNER, application_id=app_row.id, explore_run_id=None,
                              node_type="page", label="Login", url="https://s.com/login"))
            db.add(TestCase(owner_id=OWNER, name="Login test", prompt="log in",
                            target_url="https://s.com/login"))
            db.commit()
            app_id = app_row.id
        finally:
            db.close()

        m = client.get(f"/api/applications/{app_id}/map").json()
        # Heuristic matches Login by URL → covered, response shape intact.
        assert m["total_nodes"] == 1
        assert m["covered_nodes"] == 1
    finally:
        _cleanup()
