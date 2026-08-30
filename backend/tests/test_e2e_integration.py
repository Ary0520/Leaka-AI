"""
Task 23 — End-to-end integration verification + migration safety.

This is the whole-pipeline proof for Application Intelligence. Where earlier
tests exercise engines/workers in isolation, this file wires the FULL chain
together and asserts the guarantees the spec (design.md "Testing Strategy" +
Requirements 10.2/10.3/10.4/11.x) promises:

  A. Explore-discovery → reconcile → snapshot; RE-RUN → idempotent (no dupes,
     append-only snapshots).                                    (R1.6, R1.10, R10.3)
  B. Generate-test-from-node → authoritative coverage link → node flips to
     `covered` → rollup updates, without a re-explore.          (R4.3, R4.6, R11.5)
  C. Mock GitHub connect → diff ingest → diff→flow mapping → recommendation →
     CI dispatch (chain: changed file → node → test).          (R6/R7)
  D. Degradation: force the embedder to fail → coverage recompute + memory
     write/retrieve STILL succeed (no run fails, reduced signal). (R10.4, R5.9)
  E. Migration safety: run ALL migrations twice cleanly (idempotent) and the
     backfill loses no data + is idempotent.                    (R11.1, R11.2)

The browser-use agent itself is NOT run here (that is a live runtime concern).
We seed the discoveries an explore WOULD produce (AppMapNodes) and drive the
real workers — so this tests the actual reconcile→risk→coverage→memory→PR
pipeline deterministically, on both RUN_MODEs (the workers' `.run(...)` path is
dispatch-agnostic; `_dispatch_*` is smoke-checked separately).
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user
from app.database import SessionLocal, engine, Base
from app.migrations import run_migrations
from app.models import (
    Application, ExploreRun, ExploreRunStatus, AppMapNode, GraphNode, GraphEdge,
    GraphSnapshot, SnapshotMember, NodeFingerprint, CoverageVerdict, CoverageLink,
    MemoryItem, MemoryWriteQueue, TestCase, TestRun,
    RepoConnection, CodeDiff, FlowMapping,
)
from app import graph_worker as G
from app import memory as MEM

Base.metadata.create_all(bind=engine)

OWNER = f"E2E_{uuid.uuid4().hex[:8]}"
_current = {"sub": OWNER}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: dict(_current)
    yield
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)


# ---------------------------------------------------------------------------
# Seed helpers — the discoveries an explore of a small e-commerce app produces.
# A gated checkout (depends_on Login) so the graph has REAL dependency edges.
# ---------------------------------------------------------------------------
def _seed_explore_run() -> tuple[int, int]:
    """Create app + a COMPLETED explore run with realistic AppMapNodes."""
    db = SessionLocal()
    try:
        a = Application(owner_id=OWNER, name="E2EShop", base_url="https://shop.test")
        db.add(a); db.flush()
        run = ExploreRun(owner_id=OWNER, application_id=a.id,
                         job_id=f"job-{uuid.uuid4().hex[:12]}",
                         status=ExploreRunStatus.COMPLETED)
        db.add(run); db.flush()
        nodes = [
            {"label": "Products", "url": "https://shop.test/products",
             "cat": "content", "connects": ["Cart"]},
            {"label": "Cart", "url": "https://shop.test/cart",
             "cat": "checkout", "connects": ["Checkout"]},
            {"label": "Checkout", "url": "https://shop.test/checkout",
             "cat": "checkout", "depends": ["Login"]},
            {"label": "Login", "url": "https://shop.test/login", "cat": "authentication"},
        ]
        for n in nodes:
            db.add(AppMapNode(
                owner_id=OWNER, application_id=a.id, explore_run_id=run.id,
                node_type="page", label=n["label"], url=n["url"],
                business_category=n["cat"],
                connects_to=json.dumps(n["connects"]) if n.get("connects") else None,
                depends_on=json.dumps(n["depends"]) if n.get("depends") else None,
                suggested_prompt=f"Test {n['label']}",
            ))
        db.commit()
        return a.id, run.id
    finally:
        db.close()


def _counts(app_id: int) -> dict:
    db = SessionLocal()
    try:
        return {
            "nodes": db.query(GraphNode).filter(GraphNode.application_id == app_id).count(),
            "edges": db.query(GraphEdge).filter(GraphEdge.application_id == app_id).count(),
            "snapshots": db.query(GraphSnapshot).filter(GraphSnapshot.application_id == app_id).count(),
            "verdicts": db.query(CoverageVerdict).filter(CoverageVerdict.application_id == app_id).count(),
        }
    finally:
        db.close()


def _cleanup():
    db = SessionLocal()
    try:
        app_ids = [a.id for a in db.query(Application).filter(Application.owner_id == OWNER).all()]
        if app_ids:
            db.query(FlowMapping).filter(FlowMapping.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(CodeDiff).filter(CodeDiff.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(RepoConnection).filter(RepoConnection.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(MemoryItem).filter(MemoryItem.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(MemoryWriteQueue).filter(MemoryWriteQueue.application_id.in_(app_ids)).delete(synchronize_session=False)
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
        db.query(TestRun).filter(TestRun.owner_id == OWNER).delete(synchronize_session=False)
        db.query(TestCase).filter(TestCase.owner_id == OWNER).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


# ===========================================================================
# A. Explore → reconcile → snapshot; re-run idempotent
# ===========================================================================
def test_A_reconcile_builds_graph_and_reexplore_is_idempotent():
    try:
        app_id, run_id = _seed_explore_run()

        # First reconcile builds the graph + one snapshot.
        out1 = G.reconcile_explore.run(run_id)
        assert out1["status"] == "completed"
        c1 = _counts(app_id)
        assert c1["nodes"] == 4, "expected 4 graph nodes from 4 discoveries"
        # depends_on Checkout→Login + navigates_to edges are derived.
        assert c1["edges"] >= 1, "expected at least the depends_on edge"
        assert c1["snapshots"] == 1

        # A depends_on edge must exist (the blast-radius signal).
        db = SessionLocal()
        try:
            dep = db.query(GraphEdge).filter(
                GraphEdge.application_id == app_id, GraphEdge.edge_type == "depends_on"
            ).count()
            assert dep >= 1, "Checkout depends_on Login edge must be derived"
        finally:
            db.close()

        # Re-run the SAME explore run → idempotent: no new nodes, snapshot appended
        # (append-only history) but node/edge identity unchanged.
        G.reconcile_explore.run(run_id)
        c2 = _counts(app_id)
        assert c2["nodes"] == c1["nodes"], "re-explore must NOT duplicate nodes (R1.6)"
        assert c2["edges"] == c1["edges"], "re-explore must NOT duplicate edges"
        assert c2["snapshots"] == 2, "snapshots are append-only (R1.10)"
    finally:
        _cleanup()


# ===========================================================================
# B. Generate test from node → coverage link → node flips covered → rollup
# ===========================================================================
def test_B_generate_test_flips_coverage_without_reexplore():
    try:
        app_id, run_id = _seed_explore_run()
        G.reconcile_explore.run(run_id)
        G.recompute_coverage.run(app_id, "seed")

        # Everything uncovered initially.
        cov0 = client.get(f"/api/applications/{app_id}/coverage").json()
        assert cov0["application_rollup"]["percent"] == 0.0

        # Pick the Checkout node and generate a test FROM it (authoritative link).
        g = client.get(f"/api/applications/{app_id}/graph").json()
        checkout = next(n for n in g["nodes"] if n["label"] == "Checkout")
        created = client.post("/api/test-cases", json={
            "name": "Checkout E2E", "prompt": "complete checkout",
            "application_id": app_id, "node_id": checkout["id"],
        })
        assert created.status_code == 200
        tc_id = created.json()["id"]

        # Link exists and is authoritative.
        db = SessionLocal()
        try:
            link = db.query(CoverageLink).filter(
                CoverageLink.node_id == checkout["id"], CoverageLink.test_case_id == tc_id
            ).first()
            assert link is not None and link.source == "generated"
        finally:
            db.close()

        # Recompute (no re-explore) → Checkout flips to covered, rollup rises.
        G.recompute_coverage.run(app_id, "after_link")
        cov1 = client.get(f"/api/applications/{app_id}/coverage").json()
        assert cov1["application_rollup"]["covered_count"] >= 1
        assert cov1["application_rollup"]["percent"] > 0.0

        # The graph node now carries coverage_state=covered (read-path join).
        g2 = client.get(f"/api/applications/{app_id}/graph").json()
        checkout2 = next(n for n in g2["nodes"] if n["label"] == "Checkout")
        assert checkout2["coverage_state"] == "covered"
    finally:
        _cleanup()


# ===========================================================================
# C. Mock GitHub → diff ingest → mapping → recommendation → CI dispatch
# ===========================================================================
def test_C_pr_chain_end_to_end(monkeypatch):
    try:
        app_id, run_id = _seed_explore_run()
        G.reconcile_explore.run(run_id)
        G.recompute_coverage.run(app_id, "seed")

        # Link a test to Checkout so the recommendation has something to recommend.
        g = client.get(f"/api/applications/{app_id}/graph").json()
        checkout = next(n for n in g["nodes"] if n["label"] == "Checkout")
        created = client.post("/api/test-cases", json={
            "name": "Checkout E2E", "prompt": "complete checkout",
            "application_id": app_id, "node_id": checkout["id"],
        })
        tc_id = created.json()["id"]
        G.recompute_coverage.run(app_id, "after_link")

        # Repo connection + a pending diff (seed directly; connect endpoint is
        # covered by its own tests — here we drive the worker chain).
        db = SessionLocal()
        try:
            conn = RepoConnection(owner_id=OWNER, application_id=app_id, provider="github",
                                  repo_full_name="org/shop", secret_ref="enc:v1:dummy")
            db.add(conn); db.flush()
            diff = CodeDiff(owner_id=OWNER, application_id=app_id, repo_connection_id=conn.id,
                            pr_number="7", ingest_status="pending",
                            delivery_id=f"d-{uuid.uuid4().hex[:8]}")
            db.add(diff); db.commit()
            diff_id = diff.id
        finally:
            db.close()

        from app.integrations import github_client as GH
        import app.repo_worker as RW
        # Mock GitHub: a changed file that route-matches /checkout.
        monkeypatch.setattr(GH, "fetch_pr_files", lambda token, repo, pr: [
            {"path": "src/pages/checkout.tsx", "status": "modified",
             "additions": 3, "deletions": 0, "changes": 3, "patch": "@@ +1 @@"},
        ])
        monkeypatch.setattr("app.secrets_store.resolve_secret_ref", lambda ref: "ghp_token")
        monkeypatch.setattr(RW, "_dispatch_map", lambda d: RW.map_code_diff.run(d))

        out = RW.ingest_diff.run(diff_id)
        assert out["status"] == "completed"

        # Recommendation surfaces the affected node + recommended test with the chain.
        rec = client.get(f"/api/applications/{app_id}/diffs/{diff_id}/recommendation").json()
        assert rec["status"] == "ok"
        assert any(m["label"] == "Checkout" for m in rec["mappings"])
        assert tc_id in rec["recommended_test_ids"]

        # CI dispatch fires for the recommended test (mock the actual run dispatch).
        import app.main as MAIN
        monkeypatch.setattr(MAIN, "_dispatch_run_task", lambda **kw: "task-mock")
        run = client.post(f"/api/applications/{app_id}/diffs/{diff_id}/run").json()
        assert len(run["job_ids"]) >= 1
    finally:
        _cleanup()


# ===========================================================================
# D. Degradation — embedder down → coverage + memory still work, no failure
# ===========================================================================
def test_D_degrades_gracefully_when_embedder_unavailable(monkeypatch):
    try:
        app_id, run_id = _seed_explore_run()
        G.reconcile_explore.run(run_id)

        # Force the embedder to be unavailable everywhere it's used.
        from app.intelligence import embeddings as EMB

        def _boom(*a, **k):
            raise EMB.EmbeddingUnavailable("forced outage for degradation test")

        monkeypatch.setattr(EMB, "get_embedder", _boom)

        # 1. Coverage recompute STILL completes (semantic signal skipped).
        out = G.recompute_coverage.run(app_id, "degraded")
        assert out["status"] == "completed"
        assert out["verdicts"] == 4

        cov = client.get(f"/api/applications/{app_id}/coverage").json()
        assert cov["is_empty"] is False  # verdicts still computed from link+route

        # 2. Memory write STILL succeeds (item persists identity-retrievable; the
        #    embedding is simply skipped and can backfill later) — never raises.
        db = SessionLocal()
        try:
            node = db.query(GraphNode).filter(
                GraphNode.application_id == app_id, GraphNode.label == "Login"
            ).first()
            res = MEM.write(db, MEM.MemoryWrite(
                application_id=app_id, kind="locator", owner_id=OWNER,
                node_id=node.id, payload={"selector": "#login-btn"},
                embed_text="login button",
            ))
            assert res["status"] in ("written", "exists", "queued")

            # 3. Identity retrieval STILL returns the item (degrades to identity-only).
            items = MEM.retrieve(db, app_id, owner_id=OWNER, node_id=node.id,
                                 query="login", k=5)
            assert any(i.kind == "locator" for i in items)
        finally:
            db.close()
    finally:
        _cleanup()


# ===========================================================================
# E. Migration safety — all migrations idempotent; backfill lossless + idempotent
# ===========================================================================
def test_E_migrations_run_twice_cleanly():
    # Running the full migration set twice must not error and must leave all
    # Application-Intelligence tables present (R11.1).
    run_migrations()
    run_migrations()

    from sqlalchemy import inspect
    tables = set(inspect(engine).get_table_names())
    required = {
        "graph_nodes", "graph_edges", "node_fingerprints", "graph_snapshots",
        "snapshot_members", "coverage_verdicts", "coverage_links",
        "memory_items", "memory_write_queue",
        "repo_connections", "code_diffs", "flow_mappings",
    }
    missing = required - tables
    assert not missing, f"migrations left tables missing: {missing}"


def test_E_backfill_is_lossless_and_idempotent():
    """
    An app with legacy AppMapNodes but no graph is backfilled into a graph
    without losing labels/urls, and re-running the backfill creates no dupes
    (R11.2, R11.3).
    """
    try:
        # Seed legacy AppMapNodes WITHOUT reconciling (no graph yet).
        db = SessionLocal()
        try:
            a = Application(owner_id=OWNER, name="Legacy", base_url="https://legacy.test")
            db.add(a); db.flush()
            for lbl, url in [("Home", "https://legacy.test/"),
                             ("Pricing", "https://legacy.test/pricing")]:
                db.add(AppMapNode(owner_id=OWNER, application_id=a.id, explore_run_id=None,
                                  node_type="page", label=lbl, url=url,
                                  suggested_prompt=f"Test {lbl}"))
            db.commit()
            app_id = a.id
        finally:
            db.close()

        # No graph yet.
        assert _counts(app_id)["nodes"] == 0

        r1 = G.backfill_application_graph(app_id)
        assert r1["status"] == "completed"
        c1 = _counts(app_id)
        assert c1["nodes"] == 2, "backfill must create a node per legacy AppMapNode"

        # Labels preserved (lossless).
        db = SessionLocal()
        try:
            labels = {n.label for n in db.query(GraphNode).filter(
                GraphNode.application_id == app_id).all()}
            assert labels == {"Home", "Pricing"}
        finally:
            db.close()

        # Re-run backfill → idempotent (no duplicate nodes).
        G.backfill_application_graph(app_id)
        assert _counts(app_id)["nodes"] == 2, "backfill re-run must not duplicate nodes"
    finally:
        _cleanup()


def _settle_background():
    """
    Drain the sync_demo background executor so no fire-and-forget recompute is
    still running when we tear down (otherwise a late thread races the cleanup
    delete and logs a harmless-but-noisy FK error). No-op under celery.
    """
    import time
    time.sleep(0.3)
    ex = getattr(G, "_SYNC_EXECUTOR", None)
    if ex is not None:
        try:
            for f in [ex.submit(lambda: None) for _ in range(4)]:
                f.result(timeout=30)
        except Exception:
            pass


def test_E_dispatch_helpers_are_mode_agnostic():
    """
    The RUN_MODE dispatch helpers must be safe to call and return a task/thread
    handle without raising, so the pipeline behaves on both sync_demo and celery
    (the worker `.run(...)` logic tested above is identical across modes).
    """
    try:
        app_id, run_id = _seed_explore_run()
        # These enqueue (sync_demo → background thread; celery → task). They must
        # never raise regardless of mode.
        tok1 = G._dispatch_reconcile(run_id)
        tok2 = G._dispatch_recompute_coverage(app_id, "smoke")
        assert tok1 is None or isinstance(tok1, str)
        assert tok2 is None or isinstance(tok2, str)
        # Wait for the enqueued background work to finish BEFORE cleanup so it
        # cannot race the teardown delete.
        _settle_background()
    finally:
        _settle_background()
        _cleanup()
