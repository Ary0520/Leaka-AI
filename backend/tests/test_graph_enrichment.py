"""
Front-1 enrichment test: the explorer now captures business_category and
connects_to, so reconciliation must produce REAL graph edges + categorized
nodes + differentiated risk (not the flat 0-edge / all-Low graph).

Seeds AppMapNodes directly (simulating an enriched explore), runs
reconcile_explore + recompute risk/coverage, and asserts edges & categories &
risk spread actually appear.
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.database import SessionLocal, engine, Base
from app.models import (
    Application, ExploreRun, ExploreRunStatus, AppMapNode, GraphNode, GraphEdge,
    GraphSnapshot, SnapshotMember, NodeFingerprint, CoverageVerdict, CoverageLink,
)
from app import graph_worker as G

Base.metadata.create_all(bind=engine)

OWNER = f"ENRICH_{uuid.uuid4().hex[:8]}"


def _seed_enriched_run(nodes: list[dict]) -> tuple[int, int]:
    db = SessionLocal()
    try:
        app_row = Application(owner_id=OWNER, name="Enriched", base_url="https://s.com")
        db.add(app_row); db.flush()
        run = ExploreRun(owner_id=OWNER, application_id=app_row.id,
                         job_id=f"job-{uuid.uuid4().hex[:12]}", status=ExploreRunStatus.COMPLETED)
        db.add(run); db.flush()
        for n in nodes:
            db.add(AppMapNode(
                owner_id=OWNER, application_id=app_row.id, explore_run_id=run.id,
                node_type=n.get("node_type", "page"), label=n["label"], url=n.get("url"),
                business_category=n.get("business_category"),
                connects_to=json.dumps(n["connects_to"]) if n.get("connects_to") else None,
                depends_on=json.dumps(n["depends_on"]) if n.get("depends_on") else None,
                flow_steps=json.dumps(n["flow_steps"]) if n.get("flow_steps") else None,
            ))
        db.commit()
        return app_row.id, run.id
    finally:
        db.close()


def _settle():
    """Drain the background coverage/risk recompute enqueued by reconcile."""
    import time
    time.sleep(0.3)
    ex = getattr(G, "_SYNC_EXECUTOR", None)
    if ex is not None:
        try:
            for f in [ex.submit(lambda: None) for _ in range(4)]:
                f.result(timeout=30)
        except Exception:
            pass


def _cleanup():
    _settle()
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
            # A late background recompute (sync_demo runs it on a thread pool) can
            # insert coverage_verdicts AFTER the delete above and just before we
            # drop graph_nodes, causing an FK violation. Settle once more and
            # re-delete verdicts immediately before removing the nodes so cleanup
            # is race-free regardless of recompute timing (test-only hardening).
            _settle()
            db.query(CoverageVerdict).filter(CoverageVerdict.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(AppMapNode).filter(AppMapNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(ExploreRun).filter(ExploreRun.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_reconcile_produces_edges_categories_and_risk_spread():
    try:
        # A realistic e-commerce slice with observed navigation + categories.
        app_id, run_id = _seed_enriched_run([
            {"label": "Login", "url": "https://s.com/login", "node_type": "form",
             "business_category": "authentication", "connects_to": ["Products"]},
            {"label": "Products", "url": "https://s.com/products",
             "business_category": "content", "connects_to": ["Cart"]},
            {"label": "Cart", "url": "https://s.com/cart",
             "business_category": "checkout", "connects_to": ["Checkout"]},
            {"label": "Checkout", "url": "https://s.com/checkout", "node_type": "flow",
             "business_category": "billing", "connects_to": []},
        ])
        out = G.reconcile_explore.run(run_id)
        assert out["status"] == "completed"
        # Risk is computed by recompute_coverage; run it synchronously so the
        # assertion is deterministic (reconcile enqueues it in the background).
        G.recompute_coverage.run(app_id, "test")

        db = SessionLocal()
        try:
            nodes = db.query(GraphNode).filter(GraphNode.application_id == app_id).all()
            edges = db.query(GraphEdge).filter(GraphEdge.application_id == app_id).all()

            # REAL edges now exist (Login→Products→Cart→Checkout).
            assert len(edges) == 3, f"expected 3 navigates_to edges, got {len(edges)}"
            assert all(e.edge_type == "navigates_to" for e in edges)

            # Categories are populated (not all Unknown).
            cats = {n.business_category for n in nodes}
            assert "billing" in cats and "authentication" in cats and "checkout" in cats

            # Risk is DIFFERENTIATED, not all Low: billing/checkout/auth should
            # outrank a plain content page.
            risk_by_label = {}
            for n in nodes:
                r = json.loads(n.risk) if n.risk else {}
                risk_by_label[n.label] = r.get("score", 0)
            # Revenue-critical flows clearly outrank a plain content page — the
            # whole point of the enrichment. (navigates_to is not a dependency,
            # so it correctly does NOT inflate centrality; category drives the
            # spread here.)
            assert risk_by_label["Checkout"] > risk_by_label["Products"] + 20, risk_by_label
            assert risk_by_label["Login"] > risk_by_label["Products"] + 20, risk_by_label
            assert risk_by_label["Cart"] > risk_by_label["Products"] + 20, risk_by_label
            # Content page stays low.
            assert risk_by_label["Products"] < 30, risk_by_label
        finally:
            db.close()
    finally:
        _cleanup()


def test_depends_on_drives_centrality_and_blast_radius():
    """
    A node that MANY flows depend on becomes genuinely high-risk via graph
    centrality — the enterprise 'blast radius' signal. Here 3 nodes depend on
    'Login'; Login should score materially higher than the same node with no
    dependents would.
    """
    try:
        app_id, run_id = _seed_enriched_run([
            {"label": "Login", "url": "https://s.com/login", "node_type": "form",
             "business_category": "authentication"},
            {"label": "Cart", "url": "https://s.com/cart", "business_category": "content",
             "depends_on": ["Login"]},
            {"label": "Checkout", "url": "https://s.com/checkout", "node_type": "flow",
             "business_category": "content", "depends_on": ["Login"],
             "flow_steps": ["Cart"]},
            {"label": "Orders", "url": "https://s.com/orders", "business_category": "content",
             "depends_on": ["Login"]},
        ])
        G.reconcile_explore.run(run_id)
        G.recompute_coverage.run(app_id, "test")

        db = SessionLocal()
        try:
            edges = db.query(GraphEdge).filter(GraphEdge.application_id == app_id).all()
            # 3 depends_on (→Login) + 1 part_of_flow (Cart→Checkout) = 4 edges.
            types = sorted(e.edge_type for e in edges)
            assert types.count("depends_on") == 3, types
            assert types.count("part_of_flow") == 1, types

            nodes = db.query(GraphNode).filter(GraphNode.application_id == app_id).all()
            risk = {n.label: (json.loads(n.risk) if n.risk else {}).get("score", 0) for n in nodes}
            # Login is 'authentication' AND has 3 dependents → centrality lifts it
            # into a genuinely high score (blast radius), far above a lone
            # content page like Orders.
            assert risk["Login"] > risk["Orders"] + 40, risk
            assert risk["Login"] >= 60, risk  # High band: auth category + centrality

            # Prove centrality specifically contributed: the graph_centrality
            # factor is non-zero because 3 nodes depend on Login.
            login = next(n for n in nodes if n.label == "Login")
            factors = {f["name"]: f["contribution"]
                       for f in (json.loads(login.risk).get("factors") or [])}
            assert factors.get("graph_centrality", 0) > 0, factors
        finally:
            db.close()
    finally:
        _cleanup()


def test_no_fabricated_edges_to_unknown_labels():
    """connects_to referencing a non-existent label produces NO edge."""
    try:
        app_id, run_id = _seed_enriched_run([
            {"label": "Home", "url": "https://s.com/", "business_category": "navigation",
             "connects_to": ["Nonexistent Page", "Home"]},  # bad ref + self-ref
        ])
        G.reconcile_explore.run(run_id)
        db = SessionLocal()
        try:
            edges = db.query(GraphEdge).filter(GraphEdge.application_id == app_id).count()
            assert edges == 0, "edges were fabricated for unknown/self labels"
        finally:
            db.close()
    finally:
        _cleanup()
