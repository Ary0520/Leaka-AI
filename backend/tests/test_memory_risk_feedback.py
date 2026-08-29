"""
Integration test — Memory → Risk feedback loop (Requirements 3.3, 3.6).

Proves the "compounding" promise: a node that has FAILED recently accrues a
higher risk score than an identical node with a clean history, because the
recompute worker now feeds a recency-weighted historical_failure_rate (derived
from stored `outcome` memory) into the pure risk engine.

Determinism and the "no history → unchanged" invariant are also asserted so we
never regress the existing risk behavior for nodes without outcome memory.
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.database import SessionLocal, engine, Base
from app.models import (
    Application, ExploreRun, ExploreRunStatus, AppMapNode, GraphNode,
    GraphSnapshot, SnapshotMember, NodeFingerprint, GraphEdge,
    CoverageVerdict, CoverageLink, MemoryItem, TestCase,
)
from app import graph_worker as G

Base.metadata.create_all(bind=engine)

OWNER = f"MEMRISK_{uuid.uuid4().hex[:8]}"


def _seed_two_identical_nodes() -> tuple[int, int, int]:
    """Build a graph with two identical 'content' pages. Returns (app_id, node_a_id, node_b_id)."""
    db = SessionLocal()
    try:
        app_row = Application(owner_id=OWNER, name="MemRiskApp", base_url="https://s.com")
        db.add(app_row); db.flush()
        run = ExploreRun(owner_id=OWNER, application_id=app_row.id,
                         job_id=f"job-{uuid.uuid4().hex[:12]}", status=ExploreRunStatus.COMPLETED)
        db.add(run); db.flush()
        db.add(AppMapNode(owner_id=OWNER, application_id=app_row.id, explore_run_id=run.id,
                          node_type="page", label="Alpha", url="https://s.com/alpha",
                          business_category="content"))
        db.add(AppMapNode(owner_id=OWNER, application_id=app_row.id, explore_run_id=run.id,
                          node_type="page", label="Beta", url="https://s.com/beta",
                          business_category="content"))
        db.commit()
        app_id, run_id = app_row.id, run.id
    finally:
        db.close()
    G.reconcile_explore.run(run_id)

    db = SessionLocal()
    try:
        nodes = db.query(GraphNode).filter(GraphNode.application_id == app_id).order_by(GraphNode.label).all()
        a_id = next(n.id for n in nodes if n.label == "Alpha")
        b_id = next(n.id for n in nodes if n.label == "Beta")
        return app_id, a_id, b_id
    finally:
        db.close()


def _write_outcomes(app_id: int, node_id: int, outcomes: list[bool]) -> None:
    """Write outcome memory rows for a node in chronological order."""
    db = SessionLocal()
    try:
        for i, passed in enumerate(outcomes):
            db.add(MemoryItem(
                owner_id=OWNER, application_id=app_id, node_id=node_id,
                kind="outcome",
                payload=json.dumps({"passed": passed, "duration_seconds": 3}),
                content_hash=f"{node_id}-{i}-{passed}",  # unique so dedup doesn't collapse
                provenance=json.dumps({"source": "test"}),
                version=1,
            ))
        db.commit()
    finally:
        db.close()


def _risk_score(app_id: int, node_id: int) -> int:
    db = SessionLocal()
    try:
        n = db.query(GraphNode).filter(GraphNode.id == node_id).first()
        risk = json.loads(n.risk) if n and n.risk else {}
        return int(risk.get("score", 0) or 0)
    finally:
        db.close()


def _cleanup():
    db = SessionLocal()
    try:
        app_ids = [a.id for a in db.query(Application).filter(Application.owner_id == OWNER).all()]
        if app_ids:
            db.query(MemoryItem).filter(MemoryItem.application_id.in_(app_ids)).delete(synchronize_session=False)
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
        db.commit()
    finally:
        db.close()


def test_failing_history_raises_risk_relative_to_clean_node():
    try:
        app_id, a_id, b_id = _seed_two_identical_nodes()

        # Baseline: identical nodes, no outcome memory → identical risk.
        G.recompute_coverage.run(app_id, "baseline")
        base_a = _risk_score(app_id, a_id)
        base_b = _risk_score(app_id, b_id)
        assert base_a == base_b, "identical nodes should score identically with no history"

        # Alpha fails its recent runs; Beta stays clean.
        _write_outcomes(app_id, a_id, [False, False, False])
        _write_outcomes(app_id, b_id, [True, True, True])

        G.recompute_coverage.run(app_id, "after_outcomes")
        after_a = _risk_score(app_id, a_id)
        after_b = _risk_score(app_id, b_id)

        # The failing node's risk rose; the clean node's did not.
        assert after_a > base_a, "failing history must raise risk (R3.3)"
        assert after_b == base_b, "clean history must not change risk"
        assert after_a > after_b, "failing node must now outrank the identical clean node"
    finally:
        _cleanup()


def test_recompute_is_deterministic_with_history():
    try:
        app_id, a_id, _ = _seed_two_identical_nodes()
        _write_outcomes(app_id, a_id, [False, True, False])

        G.recompute_coverage.run(app_id, "run1")
        s1 = _risk_score(app_id, a_id)
        G.recompute_coverage.run(app_id, "run2")
        s2 = _risk_score(app_id, a_id)
        assert s1 == s2, "identical memory state must yield identical risk"
    finally:
        _cleanup()
