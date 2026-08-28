"""
Integration test for graph_worker.reconcile_explore (Task 6).

Exercises the REAL persistence path end-to-end against the configured database
(SQLite locally, Postgres in CI): seed an Application + ExploreRun + AppMapNodes,
run reconcile_explore in-process, and assert the persistent graph, an initial
snapshot, idempotency on re-run, and stale-not-delete on a shrinking run.

Uses a unique owner_id per test and cleans up its own rows.
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal, engine, Base
from app.models import (
    Application,
    ExploreRun,
    ExploreRunStatus,
    AppMapNode,
    GraphNode,
    GraphEdge,
    GraphSnapshot,
    SnapshotMember,
    NodeFingerprint,
    CoverageVerdict,
    CoverageLink,
)
from app import graph_worker as G


# Ensure all tables (including graph tables) exist for the test DB.
Base.metadata.create_all(bind=engine)


def _seed_run(db, owner: str, nodes: list[dict]) -> tuple[int, int]:
    """Create an Application + a completed ExploreRun + its AppMapNodes."""
    app = Application(owner_id=owner, name="TestApp", base_url="https://s.com")
    db.add(app)
    db.flush()

    run = ExploreRun(
        owner_id=owner,
        application_id=app.id,
        job_id=f"job-{uuid.uuid4().hex[:12]}",
        status=ExploreRunStatus.COMPLETED,
    )
    db.add(run)
    db.flush()

    for n in nodes:
        db.add(AppMapNode(
            owner_id=owner,
            application_id=app.id,
            explore_run_id=run.id,
            node_type=n.get("node_type", "page"),
            label=n["label"],
            url=n.get("url"),
            description=n.get("description"),
        ))
    db.commit()
    return app.id, run.id


def _new_run_for(db, owner: str, application_id: int, nodes: list[dict]) -> int:
    run = ExploreRun(
        owner_id=owner,
        application_id=application_id,
        job_id=f"job-{uuid.uuid4().hex[:12]}",
        status=ExploreRunStatus.COMPLETED,
    )
    db.add(run)
    db.flush()
    for n in nodes:
        db.add(AppMapNode(
            owner_id=owner,
            application_id=application_id,
            explore_run_id=run.id,
            node_type=n.get("node_type", "page"),
            label=n["label"],
            url=n.get("url"),
        ))
    db.commit()
    return run.id


def _settle() -> None:
    """
    reconcile_explore enqueues a coverage recompute on the graph_worker sync
    executor (RUN_MODE=sync_demo). Wait for those background tasks to finish so
    they don't write CoverageVerdict rows during/after cleanup.
    """
    import time
    ex = getattr(G, "_SYNC_EXECUTOR", None)
    # Give any just-submitted task a moment to be picked up, then drain.
    time.sleep(0.2)
    if ex is not None:
        # Submit a barrier task and wait — ensures prior tasks completed.
        try:
            ex.submit(lambda: None).result(timeout=30)
        except Exception:
            pass


def _cleanup(owner: str) -> None:
    _settle()
    db = SessionLocal()
    try:
        app_ids = [a.id for a in db.query(Application).filter(Application.owner_id == owner).all()]
        if app_ids:
            snap_ids = [
                s.id for s in db.query(GraphSnapshot)
                .filter(GraphSnapshot.application_id.in_(app_ids)).all()
            ]
            if snap_ids:
                db.query(SnapshotMember).filter(SnapshotMember.snapshot_id.in_(snap_ids)).delete(synchronize_session=False)
                db.query(GraphSnapshot).filter(GraphSnapshot.id.in_(snap_ids)).delete(synchronize_session=False)
            node_ids = [
                n.id for n in db.query(GraphNode)
                .filter(GraphNode.application_id.in_(app_ids)).all()
            ]
            if node_ids:
                db.query(NodeFingerprint).filter(NodeFingerprint.node_id.in_(node_ids)).delete(synchronize_session=False)
            # Coverage rows FK to graph_nodes — delete them first (reconcile now
            # enqueues a coverage recompute that may have written verdicts).
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


def test_reconcile_builds_graph_and_snapshot():
    owner = f"GWTEST_{uuid.uuid4().hex[:12]}"
    db = SessionLocal()
    try:
        app_id, run_id = _seed_run(db, owner, [
            {"label": "Login", "url": "https://s.com/login"},
            {"label": "Cart", "url": "https://s.com/cart", "node_type": "page"},
            {"label": "Add coupon", "node_type": "form"},  # URL-less
        ])

        out = G.reconcile_explore.run(run_id)
        assert out["status"] == "completed"
        assert out["node_count"] == 3

        # Graph nodes persisted, all active, with fingerprints + first/last seen.
        nodes = db.query(GraphNode).filter(GraphNode.application_id == app_id).all()
        assert len(nodes) == 3
        assert all(n.status == "active" for n in nodes)
        assert all(n.first_seen_run == run_id and n.last_seen_run == run_id for n in nodes)
        for n in nodes:
            fps = db.query(NodeFingerprint).filter(NodeFingerprint.node_id == n.id).count()
            assert fps == 1, "each new node should have exactly one fingerprint version"

        # An initial snapshot with frozen members exists.
        snaps = db.query(GraphSnapshot).filter(GraphSnapshot.application_id == app_id).all()
        assert len(snaps) == 1
        members = db.query(SnapshotMember).filter(SnapshotMember.snapshot_id == snaps[0].id).all()
        assert len(members) == 3

        # No edges (flat explorer provides no relationship evidence).
        assert db.query(GraphEdge).filter(GraphEdge.application_id == app_id).count() == 0
    finally:
        db.close()
        _cleanup(owner)


def test_reconcile_is_idempotent_on_reexplore():
    owner = f"GWTEST_{uuid.uuid4().hex[:12]}"
    db = SessionLocal()
    try:
        nodes = [
            {"label": "Login", "url": "https://s.com/login"},
            {"label": "Cart", "url": "https://s.com/cart"},
        ]
        app_id, run1 = _seed_run(db, owner, nodes)
        G.reconcile_explore.run(run1)
        count_after_first = db.query(GraphNode).filter(GraphNode.application_id == app_id).count()
        assert count_after_first == 2

        # A brand-new explore run with the SAME discoveries → no new nodes.
        run2 = _new_run_for(db, owner, app_id, nodes)
        out = G.reconcile_explore.run(run2)
        assert out["status"] == "completed"
        count_after_second = db.query(GraphNode).filter(GraphNode.application_id == app_id).count()
        assert count_after_second == 2, "re-explore created duplicate nodes"

        # Two snapshots now exist (append-only); the second's diff is empty.
        snaps = db.query(GraphSnapshot).filter(GraphSnapshot.application_id == app_id).order_by(GraphSnapshot.id).all()
        assert len(snaps) == 2
        assert out["diff"]["added"] == 0
        assert out["diff"]["changed"] == 0
        assert out["diff"]["removed"] == 0

        # last_seen_run advanced to run2 on the matched nodes; first_seen stayed run1.
        for n in db.query(GraphNode).filter(GraphNode.application_id == app_id).all():
            assert n.first_seen_run == run1
            assert n.last_seen_run == run2
    finally:
        db.close()
        _cleanup(owner)


def test_reconcile_stales_not_deletes():
    owner = f"GWTEST_{uuid.uuid4().hex[:12]}"
    db = SessionLocal()
    try:
        app_id, run1 = _seed_run(db, owner, [
            {"label": "Login", "url": "https://s.com/login"},
            {"label": "Cart", "url": "https://s.com/cart"},
        ])
        G.reconcile_explore.run(run1)

        # Next run only observes Login → Cart must be staled, not deleted.
        run2 = _new_run_for(db, owner, app_id, [{"label": "Login", "url": "https://s.com/login"}])
        out = G.reconcile_explore.run(run2)
        assert out["node_count"] == 1  # active count

        nodes = {n.label: n for n in db.query(GraphNode).filter(GraphNode.application_id == app_id).all()}
        assert len(nodes) == 2, "staled node was deleted (must be retained)"
        assert nodes["Login"].status == "active"
        assert nodes["Cart"].status == "stale"
    finally:
        db.close()
        _cleanup(owner)
