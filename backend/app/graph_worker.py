"""
Graph worker — the I/O edge that persists Application Graph reconciliation.

This module is the thin, side-effecting counterpart to the PURE
`intelligence/reconciliation.py` engine. Its job (Task 6, design 1.3):

  reconcile_explore(explore_run_id):
    1. Load the run's raw discoveries (AppMapNodes) + the current graph.
    2. Call the pure `reconcile(...)` engine.
    3. Persist nodes / fingerprints / edges / snapshot inside ONE transaction,
       serialized per application_id via a Postgres advisory lock (R10.7).
    4. On failure, roll back and record a classified reason on the ExploreRun,
       leaving the prior graph completely intact (R10.2) — never partial-write.

It is DELIBERATELY separate from `explore_worker` (which owns AppMapNode / live
steps / status) so reconciliation is a purely additive downstream step: if it
fails, the explore result the user already sees is unaffected.

Dispatch mirrors the existing `RUN_MODE` pattern used by `explore_worker`:
  - RUN_MODE=celery    → reconcile_explore.delay(...)   (separate worker)
  - RUN_MODE=sync_demo → reconcile_explore.run(...) in a background thread
`explore_worker` calls `_dispatch_reconcile(...)` on successful completion; we
keep the helper HERE (not in main.py) so the worker never imports the FastAPI
app — no heavy/circular coupling to the API layer.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from sqlalchemy import text as sql_text

from .celery_app import celery_app
from .config import settings
from .database import SessionLocal, engine
from .intelligence.fingerprint import Discovery, NodeSignatures
from .intelligence import reconciliation as R
from .intelligence import risk as RISK
from .intelligence import coverage as COV
from .models import (
    Application,
    AppMapNode,
    ExploreRun,
    GraphNode,
    GraphEdge,
    NodeFingerprint,
    GraphSnapshot,
    SnapshotMember,
    CoverageVerdict,
    CoverageLink,
    TestCase,
    TestRun,
    TestRunStatus,
)

logger = logging.getLogger("revguard.graph")


# ---------------------------------------------------------------------------
# Dispatch (mirrors _dispatch_explore_task in main.py, kept local to the worker)
# ---------------------------------------------------------------------------
_SYNC_EXECUTOR: Optional[ThreadPoolExecutor] = None
_EXECUTOR_LOCK = threading.Lock()


def _get_sync_executor() -> ThreadPoolExecutor:
    global _SYNC_EXECUTOR
    with _EXECUTOR_LOCK:
        if _SYNC_EXECUTOR is None:
            _SYNC_EXECUTOR = ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="revguard_graph"
            )
    return _SYNC_EXECUTOR


def _dispatch_reconcile(explore_run_id: int) -> Optional[str]:
    """
    Enqueue reconciliation for a completed explore run.

    Returns a task id (celery) / synthetic id (sync_demo), or None if dispatch
    itself could not be initiated (never raises — reconciliation is a best-effort
    downstream step and must not affect the explore result the user already has).
    """
    try:
        if settings.RUN_MODE == "sync_demo":
            def _run_local():
                try:
                    reconcile_explore.run(explore_run_id)
                except Exception as exc:  # noqa: BLE001 — task writes its own failure
                    logger.exception(
                        "sync_demo reconcile raised (explore_run_id=%s): %s",
                        explore_run_id, exc,
                    )
            _get_sync_executor().submit(_run_local)
            return f"sync-reconcile-{explore_run_id}"

        task = reconcile_explore.delay(explore_run_id)
        return task.id
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to dispatch reconcile for run %s: %s", explore_run_id, exc)
        return None


# ---------------------------------------------------------------------------
# Advisory lock (Postgres only; no-op elsewhere) — serialize per application
# ---------------------------------------------------------------------------
def _acquire_app_lock(db, application_id: int) -> None:
    """
    Serialize reconciliation for a single application so two concurrent explores
    cannot corrupt the shared graph (R10.7). Transaction-scoped: auto-released
    on commit/rollback. No-op on SQLite (local dev without Postgres).
    """
    if not settings.DATABASE_URL.startswith("postgres"):
        return
    # hashtext gives a stable int from a namespaced key; xact lock releases with
    # the surrounding transaction.
    db.execute(
        sql_text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"graph_reconcile:{application_id}"},
    )


# ---------------------------------------------------------------------------
# ORM → pure-input mappers
# ---------------------------------------------------------------------------
def _existing_nodes(db, application_id: int) -> list[R.ExistingNode]:
    rows = (
        db.query(GraphNode)
        .filter(GraphNode.application_id == application_id)
        .all()
    )
    out: list[R.ExistingNode] = []
    for n in rows:
        latest_fp = (
            db.query(NodeFingerprint)
            .filter(NodeFingerprint.node_id == n.id)
            .order_by(NodeFingerprint.id.desc())
            .first()
        )
        sigs = None
        if latest_fp is not None:
            sigs = NodeSignatures(
                node_type=n.node_type,
                url_signature=latest_fp.url_signature or "",
                text_signature=latest_fp.text_signature or "",
                dom_signature=latest_fp.dom_signature,
                aria_signature=latest_fp.aria_signature,
            )
        out.append(
            R.ExistingNode(
                canonical_key=n.canonical_key,
                node_type=n.node_type,
                label=n.label,
                url_pattern=n.url_pattern,
                business_category=n.business_category,
                role_association=n.role_association or "unknown",
                status=n.status or "active",
                signatures=sigs,
                manual_overrides=_load_json(n.manual_overrides),
            )
        )
    return out


def _existing_edges(db, application_id: int) -> list[R.ExistingEdge]:
    # Edges are keyed by graph_node.id in the DB, but the pure engine works in
    # canonical_key space. Build an id→key map to translate.
    id_to_key = {
        nid: key
        for nid, key in db.query(GraphNode.id, GraphNode.canonical_key)
        .filter(GraphNode.application_id == application_id)
        .all()
    }
    rows = (
        db.query(GraphEdge)
        .filter(GraphEdge.application_id == application_id)
        .all()
    )
    out: list[R.ExistingEdge] = []
    for e in rows:
        src = id_to_key.get(e.source_node_id)
        tgt = id_to_key.get(e.target_node_id)
        if not src or not tgt:
            continue  # dangling edge; skip (never fabricate)
        out.append(
            R.ExistingEdge(
                source_key=src,
                target_key=tgt,
                edge_type=e.edge_type,
                confidence=int(e.confidence or 100),
                status=e.status or "active",
            )
        )
    return out


def _discoveries(db, explore_run_id: int) -> list[Discovery]:
    rows = (
        db.query(AppMapNode)
        .filter(AppMapNode.explore_run_id == explore_run_id)
        .all()
    )
    return [Discovery.from_app_map_node(n) for n in rows]


def _evidence_from_app_map_nodes(rows) -> tuple[list, dict]:
    """
    From a run's AppMapNodes, derive:
      - edge_evidence: navigates_to edges resolved from each node's `connects_to`
        (label list) → the canonical_key of the target node with that label.
        Only edges to labels that ACTUALLY exist in this run are emitted — never
        fabricated (R2.2/R2.3).
      - category_by_key: {canonical_key -> business_category} the explorer observed.

    Both operate in canonical_key space (computed identically to reconcile()).
    Returns (edge_evidence, category_by_key).
    """
    import json as _json
    from .intelligence.fingerprint import compute_canonical_key

    # Build label → canonical_key and key → category maps for this run.
    key_by_label: dict[str, str] = {}
    category_by_key: dict[str, str] = {}
    disc_by_row = []
    for n in rows:
        disc = Discovery.from_app_map_node(n)
        key = compute_canonical_key(disc)
        disc_by_row.append((n, disc, key))
        lbl = (n.label or "").strip().lower()
        if lbl:
            key_by_label.setdefault(lbl, key)  # first node with a label wins
        cat = (getattr(n, "business_category", None) or "").strip().lower()
        if cat:
            category_by_key.setdefault(key, cat)

    edge_evidence: list = []
    seen_edges: set = set()  # (source_key, target_key, edge_type)

    def _labels(raw) -> list[str]:
        if not raw:
            return []
        try:
            v = _json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return []
        return [str(x) for x in v] if isinstance(v, list) else []

    def _add_edge(src_key: str, tgt_key: str, edge_type: str) -> None:
        if not tgt_key or tgt_key == src_key:
            return  # target must exist in this run; no self-loops
        dedup = (src_key, tgt_key, edge_type)
        if dedup in seen_edges:
            return
        seen_edges.add(dedup)
        edge_evidence.append(
            R.EdgeEvidence(source_key=src_key, target_key=tgt_key, edge_type=edge_type)
        )

    for n, disc, src_key in disc_by_row:
        # navigates_to: this node → each node it links to.
        for t in _labels(getattr(n, "connects_to", None)):
            tgt = key_by_label.get(t.strip().lower())
            if tgt:
                _add_edge(src_key, tgt, "navigates_to")

        # depends_on: this node → each precondition it observed. In-degree of a
        # node's depends_on = "how many flows depend on it" → drives centrality
        # (blast radius). Direction: dependent(source) → dependency(target).
        for t in _labels(getattr(n, "depends_on", None)):
            tgt = key_by_label.get(t.strip().lower())
            if tgt:
                _add_edge(src_key, tgt, "depends_on")

        # part_of_flow: each step → the flow it composes. In-degree of the flow
        # = number of steps → the flow accrues centrality (it "contains" risk).
        # (src_key here is the flow node; emit step→flow so the flow gains
        # in-degree, matching the risk engine's centrality direction.)
        for step_lbl in _labels(getattr(n, "flow_steps", None)):
            step_key = key_by_label.get(step_lbl.strip().lower())
            if step_key:
                _add_edge(step_key, src_key, "part_of_flow")

    return edge_evidence, category_by_key


def _load_json(val) -> dict:
    if not val:
        return {}
    import json
    try:
        parsed = json.loads(val)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _dump_json(obj) -> str:
    import json
    return json.dumps(obj, default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------
# The task
# ---------------------------------------------------------------------------
@celery_app.task(
    max_retries=1,
    autoretry_for=(),
    name="app.graph_worker.reconcile_explore",
)
def reconcile_explore(explore_run_id: int) -> dict:
    """Reconcile a completed explore run's discoveries into the persistent graph."""
    db = SessionLocal()
    try:
        run = db.query(ExploreRun).filter(ExploreRun.id == explore_run_id).first()
        if run is None:
            logger.warning("reconcile_explore: run %s not found", explore_run_id)
            return {"status": "skipped", "reason": "run_not_found"}

        application_id = run.application_id
        owner_id = run.owner_id

        # ── one transaction, serialized per application ────────────────────
        _acquire_app_lock(db, application_id)

        existing_nodes = _existing_nodes(db, application_id)
        existing_edges = _existing_edges(db, application_id)
        run_rows = (
            db.query(AppMapNode)
            .filter(AppMapNode.explore_run_id == explore_run_id)
            .all()
        )
        discoveries = [Discovery.from_app_map_node(n) for n in run_rows]
        edge_evidence, category_by_key = _evidence_from_app_map_nodes(run_rows)
        previous_members = _load_previous_members(db, application_id)

        result = R.reconcile(
            existing_nodes,
            existing_edges,
            discoveries,
            edge_evidence=edge_evidence,       # navigates_to from observed connects_to
            category_by_key=category_by_key,   # observed business categories
            previous_members=previous_members,
        )

        _persist(db, result, application_id=application_id,
                 owner_id=owner_id, explore_run_id=explore_run_id)

        db.commit()
        # Graph changed → refresh coverage verdicts (R4.6). Best-effort enqueue.
        _dispatch_recompute_coverage(application_id, reason="graph_reconciled")
        logger.info(
            "reconcile_explore done: run=%s app=%s nodes=%s edges=%s (+%s ~%s -%s)",
            explore_run_id, application_id, result.node_count, result.edge_count,
            result.diff_summary["counts"]["added"],
            result.diff_summary["counts"]["changed"],
            result.diff_summary["counts"]["removed"],
        )
        return {
            "status": "completed",
            "application_id": application_id,
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "diff": result.diff_summary["counts"],
        }
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        reason = _classify_reconcile_error(exc)
        logger.exception("reconcile_explore failed (run=%s): %s", explore_run_id, reason)
        # Best-effort: record the reason on the run WITHOUT touching the graph.
        _record_failure(explore_run_id, reason)
        return {"status": "failed", "reason": reason}
    finally:
        db.close()


def _discoveries_for_application(db, application_id: int) -> list[Discovery]:
    """
    Load discoveries from ALL of an application's AppMapNodes (regardless of
    which explore run produced them). Used by the backfill path (B1), where
    legacy nodes may have a NULL explore_run_id. Deterministic order by id.
    """
    rows = (
        db.query(AppMapNode)
        .filter(AppMapNode.application_id == application_id)
        .order_by(AppMapNode.id.asc())
        .all()
    )
    return [Discovery.from_app_map_node(n) for n in rows]


def backfill_application_graph(application_id: int) -> dict:
    """
    One-time, idempotent backfill (B1): synthesize a graph + initial snapshot
    for an application from its existing AppMapNodes.

    Reuses the SAME pure reconcile() engine and the SAME persistence path as
    `reconcile_explore`, so a backfilled graph is identical to one produced by
    a live explore, and re-running is a no-op (canonical_key dedup + snapshot
    diff). Callers should skip applications that already have graph nodes; this
    function is also safe to call again regardless (it will MATCH, not dupe).

    Runs in ONE transaction under the per-application advisory lock. On failure
    it rolls back and leaves any prior state intact (never partial-write).
    """
    db = SessionLocal()
    try:
        app_row = db.query(Application).filter(Application.id == application_id).first()
        if app_row is None:
            return {"status": "skipped", "reason": "application_not_found"}

        owner_id = app_row.owner_id
        # Provenance run: the app's most recent explore run, if any (nullable).
        latest_run = (
            db.query(ExploreRun)
            .filter(ExploreRun.application_id == application_id)
            .order_by(ExploreRun.id.desc())
            .first()
        )
        run_pk = latest_run.id if latest_run else None

        _acquire_app_lock(db, application_id)

        existing_nodes = _existing_nodes(db, application_id)
        existing_edges = _existing_edges(db, application_id)
        all_rows = (
            db.query(AppMapNode)
            .filter(AppMapNode.application_id == application_id)
            .order_by(AppMapNode.id.asc())
            .all()
        )
        discoveries = [Discovery.from_app_map_node(n) for n in all_rows]
        if not discoveries:
            return {"status": "skipped", "reason": "no_app_map_nodes"}
        edge_evidence, category_by_key = _evidence_from_app_map_nodes(all_rows)
        previous_members = _load_previous_members(db, application_id)

        result = R.reconcile(
            existing_nodes,
            existing_edges,
            discoveries,
            edge_evidence=edge_evidence,
            category_by_key=category_by_key,
            previous_members=previous_members,
        )

        _persist(db, result, application_id=application_id,
                 owner_id=owner_id, explore_run_id=run_pk)

        db.commit()
        logger.info(
            "backfill done: app=%s nodes=%s (+%s ~%s -%s)",
            application_id, result.node_count,
            result.diff_summary["counts"]["added"],
            result.diff_summary["counts"]["changed"],
            result.diff_summary["counts"]["removed"],
        )
        return {
            "status": "completed",
            "application_id": application_id,
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "diff": result.diff_summary["counts"],
        }
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("backfill failed (app=%s): %s", application_id, exc)
        return {"status": "failed", "reason": _classify_reconcile_error(exc)}
    finally:
        db.close()


def backfill_all_pending() -> dict:
    """
    Backfill every application that has AppMapNodes but NO graph nodes yet
    (R11.2 idempotency guard). Applications that already have a graph are
    skipped. Safe to run repeatedly; used by the B1 migration.
    """
    db = SessionLocal()
    try:
        # App ids that have at least one AppMapNode.
        app_ids_with_nodes = {
            row[0]
            for row in db.query(AppMapNode.application_id).distinct().all()
            if row[0] is not None
        }
        # App ids that already have a graph.
        app_ids_with_graph = {
            row[0]
            for row in db.query(GraphNode.application_id).distinct().all()
            if row[0] is not None
        }
        pending = sorted(app_ids_with_nodes - app_ids_with_graph)
    finally:
        db.close()

    results = {"backfilled": [], "skipped": [], "failed": []}
    for app_id in pending:
        out = backfill_application_graph(app_id)
        status = out.get("status")
        if status == "completed":
            results["backfilled"].append(app_id)
        elif status == "failed":
            results["failed"].append({"application_id": app_id, "reason": out.get("reason")})
        else:
            results["skipped"].append(app_id)
    if pending:
        logger.info(
            "backfill_all_pending: %s backfilled, %s skipped, %s failed",
            len(results["backfilled"]), len(results["skipped"]), len(results["failed"]),
        )
    return results


# ---------------------------------------------------------------------------
# Persistence (ReconcileResult → ORM), all within the caller's transaction
# ---------------------------------------------------------------------------
def _persist(db, result: R.ReconcileResult, *, application_id: int,
             owner_id: Optional[str], explore_run_id: int) -> None:
    # Load current nodes once, indexed by canonical_key, for upserts.
    node_by_key: dict[str, GraphNode] = {
        n.canonical_key: n
        for n in db.query(GraphNode).filter(GraphNode.application_id == application_id).all()
    }

    now = datetime.utcnow()

    for change in result.nodes:
        node = node_by_key.get(change.canonical_key)
        if node is None:
            # NEW node
            node = GraphNode(
                owner_id=owner_id,
                application_id=application_id,
                canonical_key=change.canonical_key,
                node_type=change.node_type,
                business_category=change.business_category,
                label=change.label,
                url_pattern=change.url_pattern,
                role_association=change.role_association or "unknown",
                status="active",
                first_seen_run=explore_run_id,
                last_seen_run=explore_run_id,
            )
            db.add(node)
            db.flush()  # assign node.id for fingerprint linkage
            node_by_key[change.canonical_key] = node
            _append_fingerprint(db, node.id, change, explore_run_id)
        elif change.change == "staled":
            # Mark stale; NEVER delete. Preserve all other fields.
            node.status = "stale"
            node.updated_at = now
        else:
            # MATCHED — update metadata (overrides already applied by the engine),
            # refresh last_seen, reactivate if previously stale.
            node.node_type = change.node_type
            node.label = change.label
            node.url_pattern = change.url_pattern
            node.business_category = change.business_category
            node.role_association = change.role_association or "unknown"
            node.status = "active"
            node.last_seen_run = explore_run_id
            node.updated_at = now
            if change.fingerprint_drifted:
                _append_fingerprint(db, node.id, change, explore_run_id)

    # ── Edges (dedup by unique constraint on app+src+tgt+type) ─────────────
    _persist_edges(db, result, application_id=application_id, owner_id=owner_id,
                   node_by_key=node_by_key)

    # ── Snapshot + frozen members (append-only) ────────────────────────────
    snapshot = GraphSnapshot(
        owner_id=owner_id,
        application_id=application_id,
        explore_run_id=explore_run_id,
        node_count=result.node_count,
        edge_count=result.edge_count,
        diff_summary=_dump_json(result.diff_summary),
    )
    db.add(snapshot)
    db.flush()

    for m in result.members:
        node = node_by_key.get(m.canonical_key)
        db.add(SnapshotMember(
            snapshot_id=snapshot.id,
            node_id=node.id if node else None,
            canonical_key=m.canonical_key,
            node_state=_dump_json({
                "canonical_key": m.canonical_key,
                "node_type": m.node_type,
                "label": m.label,
                "url_pattern": m.url_pattern,
                "business_category": m.business_category,
                "role_association": m.role_association,
                "status": m.status,
                "text_signature": m.text_signature,
                "url_signature": m.url_signature,
            }),
        ))


def _append_fingerprint(db, node_id: int, change: R.NodeChange, explore_run_id: int) -> None:
    db.add(NodeFingerprint(
        node_id=node_id,
        url_signature=change.fingerprint.url_signature or None,
        dom_signature=change.fingerprint.dom_signature,
        aria_signature=change.fingerprint.aria_signature,
        text_signature=change.fingerprint.text_signature,
        embedding_id=None,
        observed_run=explore_run_id,
    ))


def _persist_edges(db, result: R.ReconcileResult, *, application_id: int,
                   owner_id: Optional[str], node_by_key: dict) -> None:
    if not result.edges:
        return
    # Index existing edges by the same dedup key the engine uses.
    existing = {
        (e.source_node_id, e.target_node_id, e.edge_type): e
        for e in db.query(GraphEdge).filter(GraphEdge.application_id == application_id).all()
    }
    key_to_id = {k: n.id for k, n in node_by_key.items()}

    for ec in result.edges:
        src_id = key_to_id.get(ec.source_key)
        tgt_id = key_to_id.get(ec.target_key)
        if src_id is None or tgt_id is None:
            continue  # endpoints must exist; never fabricate
        dedup = (src_id, tgt_id, ec.edge_type)
        row = existing.get(dedup)
        if ec.change == "staled":
            if row is not None:
                row.status = "stale"
            continue
        if row is None:
            db.add(GraphEdge(
                owner_id=owner_id,
                application_id=application_id,
                source_node_id=src_id,
                target_node_id=tgt_id,
                edge_type=ec.edge_type,
                confidence=int(ec.confidence),
                status="active",
            ))
        else:
            row.status = "active"
            row.confidence = int(ec.confidence)


def _load_previous_members(db, application_id: int) -> list[R.SnapshotMemberState]:
    """Load the most recent snapshot's frozen members for diffing."""
    latest = (
        db.query(GraphSnapshot)
        .filter(GraphSnapshot.application_id == application_id)
        .order_by(GraphSnapshot.id.desc())
        .first()
    )
    if latest is None:
        return []
    members = db.query(SnapshotMember).filter(SnapshotMember.snapshot_id == latest.id).all()
    out: list[R.SnapshotMemberState] = []
    for m in members:
        st = _load_json(m.node_state)
        if not st:
            continue
        out.append(R.SnapshotMemberState(
            canonical_key=st.get("canonical_key", m.canonical_key or ""),
            node_type=st.get("node_type", "page"),
            label=st.get("label", ""),
            url_pattern=st.get("url_pattern"),
            business_category=st.get("business_category"),
            role_association=st.get("role_association", "unknown"),
            status=st.get("status", "active"),
            text_signature=st.get("text_signature", ""),
            url_signature=st.get("url_signature", ""),
        ))
    return out


# ---------------------------------------------------------------------------
# Failure handling (classified, non-corrupting — R10.2)
# ---------------------------------------------------------------------------
def _classify_reconcile_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "lock" in msg or "deadlock" in msg:
        return "Reconciliation could not acquire the application lock; another run may be in progress."
    if "connection" in msg or "operationalerror" in msg or "could not connect" in msg:
        return "Database connection error during reconciliation; the prior graph is unchanged."
    if "constraint" in msg or "integrityerror" in msg:
        return "Reconciliation hit a data constraint; the prior graph is unchanged."
    return f"Reconciliation failed: {exc}"[:500]


def _record_failure(explore_run_id: int, reason: str) -> None:
    """
    Record the reconciliation failure on the ExploreRun without disturbing the
    graph. We append to result_summary rather than overwriting status, because
    the EXPLORE itself succeeded — only its downstream reconciliation failed.
    Guarded so a failure here can never escalate.
    """
    db = SessionLocal()
    try:
        run = db.query(ExploreRun).filter(ExploreRun.id == explore_run_id).first()
        if run is not None:
            note = f"[reconcile] {reason}"
            run.result_summary = (
                f"{run.result_summary}\n{note}" if run.result_summary else note
            )[:4000]
            db.commit()
    except Exception:  # noqa: BLE001 — never let failure-recording corrupt anything
        db.rollback()
    finally:
        db.close()


# ===========================================================================
# COVERAGE RECOMPUTE (Task 12) — the I/O worker over the pure coverage engine.
# Computes risk (for weighting) + coverage verdicts for every active node and
# upserts them. Enqueued on graph change / test add-edit-delete / run complete.
# ===========================================================================


def _dispatch_recompute_coverage(application_id: int, reason: str) -> Optional[str]:
    """
    Enqueue a coverage recompute. Mirrors _dispatch_reconcile's RUN_MODE pattern.
    Never raises — coverage is a downstream, best-effort refresh.
    """
    try:
        if settings.RUN_MODE == "sync_demo":
            def _run_local():
                try:
                    recompute_coverage.run(application_id, reason)
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "sync_demo recompute_coverage raised (app=%s): %s", application_id, exc
                    )
            _get_sync_executor().submit(_run_local)
            return f"sync-coverage-{application_id}"
        task = recompute_coverage.delay(application_id, reason)
        return task.id
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to dispatch recompute_coverage for app %s: %s", application_id, exc)
        return None


def _recent_pass_by_test(db, owner_id: Optional[str], test_ids: list[int]) -> dict[int, Optional[bool]]:
    """Most-recent run outcome per test_case_id (True/False/None). Owner-scoped."""
    out: dict[int, Optional[bool]] = {}
    if not test_ids:
        return out
    for tid in test_ids:
        run = (
            db.query(TestRun)
            .filter(TestRun.test_case_id == tid)
            .order_by(TestRun.id.desc())
            .first()
        )
        if run is None:
            out[tid] = None
        elif run.status == TestRunStatus.COMPLETED:
            out[tid] = bool(run.is_successful) if run.is_successful is not None else None
        else:
            out[tid] = None
    return out


def _historical_failure_rates(
    db, application_id: int, node_ids: list[int],
) -> dict[int, float]:
    """
    Compute a recency-weighted historical failure rate in [0.0, 1.0] per node
    from its stored `outcome` Memory items (R3.3, R3.6). This is the feedback
    loop that lets a node that has been FAILING recently accrue higher risk —
    turning Leaka's learned outcomes into a live risk signal.

    Evidence source: MemoryItem(kind="outcome", payload={"passed": bool, ...}),
    written after each run by `worker._write_run_outcome_memory`. Memory is
    already node-scoped and bounded by compaction (latest N outcomes), so this
    is naturally recency-limited.

    Weighting: newer outcomes (higher id = more recent) count more, via a linear
    recency weight. A node with no outcome memory is simply absent from the map
    (the caller then passes historical_failure_rate=None → the risk engine skips
    the factor entirely, exactly as before). Fully guarded: any error yields an
    empty map so risk scoring proceeds unchanged (never breaks recompute).

    Deterministic: pure function of the stored rows (ordered by id), no time or
    randomness — so risk stays reproducible for identical memory state.
    """
    if not node_ids:
        return {}
    try:
        from .models import MemoryItem  # local import; graph_worker stays light
    except Exception:  # noqa: BLE001
        return {}

    rates: dict[int, float] = {}
    try:
        rows = (
            db.query(MemoryItem)
            .filter(
                MemoryItem.application_id == application_id,
                MemoryItem.kind == "outcome",
                MemoryItem.node_id.in_(node_ids),
            )
            .order_by(MemoryItem.id.asc())
            .all()
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("historical failure rate skipped (app=%s): %s", application_id, exc)
        return {}

    # Group outcomes per node, in chronological order (id asc).
    by_node: dict[int, list[bool]] = {}
    for r in rows:
        payload = _load_json(r.payload)
        passed = payload.get("passed")
        if passed is None:
            continue
        by_node.setdefault(r.node_id, []).append(bool(passed))

    for node_id, outcomes in by_node.items():
        if not outcomes:
            continue
        # Linear recency weights: the i-th (0-based) of N outcomes gets weight
        # (i+1), so the most recent run dominates. failure_rate = weighted mean
        # of "failed" (passed == False → 1.0).
        total_w = 0.0
        fail_w = 0.0
        n = len(outcomes)
        for i, passed in enumerate(outcomes):
            w = float(i + 1)          # oldest=1 … newest=n
            total_w += w
            if not passed:
                fail_w += w
        if total_w > 0:
            rate = fail_w / total_w
            rates[node_id] = max(0.0, min(1.0, round(rate, 6)))
    return rates


def _semantic_similarities(
    db, owner_id: Optional[str], application_id: int,
    nodes: list, tests: list,
) -> dict:
    """
    Best-effort semantic similarity per (node_id, test_case_id) using the
    embeddings service. Degrades to an EMPTY map (no semantic signal) if the
    embedder is unavailable (R10.4) — the pure engine then relies on link+route.

    Returns {(node_id, test_case_id): cosine_in_0_1}. Small sets → in-memory
    cosine; we never load all vectors for scanning at scale (that path uses
    pgvector, added when volume warrants).
    """
    sims: dict = {}
    # Guard: only attempt if there is anything to compare.
    if not nodes or not tests:
        return sims
    try:
        from .intelligence import embeddings as EMB
        embedder = EMB.get_embedder()

        def _node_text(n) -> str:
            return " ".join(filter(None, [n.label or "", n.business_category or "", n.url_pattern or ""]))

        def _test_text(t) -> str:
            return " ".join(filter(None, [t.name or "", t.prompt or ""]))

        node_texts = [_node_text(n) for n in nodes]
        test_texts = [_test_text(t) for t in tests]
        node_vecs = embedder.embed(node_texts)
        test_vecs = embedder.embed(test_texts)

        def _cos(a: list[float], b: list[float]) -> float:
            import math
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            if na == 0 or nb == 0:
                return 0.0
            return max(0.0, min(1.0, dot / (na * nb)))

        for i, n in enumerate(nodes):
            for j, t in enumerate(tests):
                sims[(n.id, t.id)] = _cos(node_vecs[i], test_vecs[j])
    except Exception as exc:  # EmbeddingUnavailable or anything → degrade
        logger.info("Coverage semantic signal skipped (app=%s): %s", application_id, exc)
        return {}
    return sims


@celery_app.task(
    max_retries=1,
    autoretry_for=(),
    name="app.graph_worker.recompute_coverage",
)
def recompute_coverage(application_id: int, reason: str = "manual") -> dict:
    """
    Recompute + persist coverage verdicts for every ACTIVE node of an app.
    Owner-scoped, advisory-locked, single transaction, non-corrupting on failure.
    """
    db = SessionLocal()
    try:
        app_row = db.query(Application).filter(Application.id == application_id).first()
        if app_row is None:
            return {"status": "skipped", "reason": "application_not_found"}
        owner_id = app_row.owner_id

        _acquire_app_lock(db, application_id)

        nodes = (
            db.query(GraphNode)
            .filter(GraphNode.application_id == application_id, GraphNode.status == "active")
            .all()
        )
        if not nodes:
            db.commit()
            return {"status": "completed", "application_id": application_id, "verdicts": 0}

        # Risk per node (for rollup weighting + gap ranking), from the risk engine.
        edges = _existing_edges(db, application_id)
        risk_graph = RISK.RiskGraph.from_edges(
            [(e.source_key, e.target_key, e.edge_type) for e in edges]
        )
        # Memory→risk feedback loop (R3.3, R3.6): recency-weighted historical
        # failure rate per node from stored `outcome` memory. Nodes with no
        # outcome memory are absent → historical_failure_rate stays None (the
        # risk engine then skips that factor, exactly as before).
        failure_rates = _historical_failure_rates(db, application_id, [n.id for n in nodes])
        key_risk: dict[str, RISK.RiskResult] = {}
        for n in nodes:
            rn = RISK.RiskNode(
                canonical_key=n.canonical_key,
                node_type=n.node_type,
                business_category=n.business_category,
                role_association=n.role_association or "unknown",
                manual_overrides=_load_json(n.manual_overrides),
            )
            signals = RISK.RiskSignals(
                historical_failure_rate=failure_rates.get(n.id),
            )
            key_risk[n.canonical_key] = RISK.score_node(rn, risk_graph, signals)

        # Candidate tests: this owner's test cases (coverage is owner-scoped).
        tests = db.query(TestCase).filter(TestCase.owner_id == owner_id).all() if owner_id else \
            db.query(TestCase).all()

        # Authoritative links for this application → {(node_id, test_id): source}
        links = db.query(CoverageLink).filter(CoverageLink.application_id == application_id).all()
        link_map: dict = {(l.node_id, l.test_case_id): l.source for l in links}

        recent_pass = _recent_pass_by_test(db, owner_id, [t.id for t in tests])
        sims = _semantic_similarities(db, owner_id, application_id, nodes, tests)

        verdict_count = 0
        for n in nodes:
            risk_res = key_risk.get(n.canonical_key)
            cov_node = COV.CoverageNode(
                node_id=n.id,
                canonical_key=n.canonical_key,
                url_pattern=n.url_pattern,
                business_category=n.business_category,
                status="active",
                risk_score=risk_res.score if risk_res else 0,
                risk_level=risk_res.level if risk_res else "Trivial",
            )
            cov_tests = []
            for t in tests:
                linked = (n.id, t.id) in link_map
                cov_tests.append(COV.CoverageTest(
                    test_case_id=t.id,
                    target_url=t.target_url,
                    name=t.name,
                    prompt=t.prompt,
                    linked=linked,
                    link_source=link_map.get((n.id, t.id)),
                    semantic_similarity=sims.get((n.id, t.id)),
                    last_run_passed=recent_pass.get(t.id),
                ))
            verdict = COV.classify_node_coverage(cov_node, cov_tests)
            _upsert_verdict(db, owner_id, application_id, verdict)
            verdict_count += 1

            # Persist recomputed risk on the node too (transparency; overrides
            # already applied by the engine).
            if risk_res is not None:
                n.risk = _dump_json(RISK.result_to_dict(risk_res))

        # Orphan flagging: links whose node is stale.
        _flag_orphan_links(db, application_id)

        db.commit()
        logger.info("recompute_coverage done: app=%s verdicts=%s reason=%s",
                    application_id, verdict_count, reason)
        return {"status": "completed", "application_id": application_id, "verdicts": verdict_count}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("recompute_coverage failed (app=%s): %s", application_id, exc)
        return {"status": "failed", "reason": _classify_reconcile_error(exc)}
    finally:
        db.close()


def _upsert_verdict(db, owner_id, application_id: int, verdict: COV.CoverageVerdict) -> None:
    row = (
        db.query(CoverageVerdict)
        .filter(CoverageVerdict.application_id == application_id,
                CoverageVerdict.node_id == verdict.node_id)
        .first()
    )
    evidence_json = _dump_json(COV.verdict_to_evidence_list(verdict))
    milli = COV.confidence_to_milli(verdict.confidence)
    if row is None:
        db.add(CoverageVerdict(
            owner_id=owner_id, application_id=application_id, node_id=verdict.node_id,
            state=verdict.state, confidence_milli=milli, evidence=evidence_json,
        ))
    else:
        row.state = verdict.state
        row.confidence_milli = milli
        row.evidence = evidence_json
        row.updated_at = datetime.utcnow()


def _flag_orphan_links(db, application_id: int) -> None:
    """Flag (not drop) coverage links whose node is stale (R4.9)."""
    stale_ids = {
        nid for (nid,) in db.query(GraphNode.id)
        .filter(GraphNode.application_id == application_id, GraphNode.status == "stale")
        .all()
    }
    links = db.query(CoverageLink).filter(CoverageLink.application_id == application_id).all()
    for l in links:
        should_orphan = l.node_id in stale_ids
        if bool(l.orphaned) != should_orphan:
            l.orphaned = should_orphan


# ===========================================================================
# MEMORY MAINTENANCE (Task 14) — periodic Celery tasks over the memory service.
# drain_memory_queue: retry durably-queued writes (R5.5a).
# compact_memory: enforce retention/compaction (R5.8).
# Both are safe to run repeatedly and never corrupt state.
# ===========================================================================


@celery_app.task(name="app.graph_worker.drain_memory_queue")
def drain_memory_queue(batch: int = 50) -> dict:
    """Drain due memory write-queue rows with retry+backoff."""
    from . import memory as MEM
    db = SessionLocal()
    try:
        out = MEM.drain_queue_once(db, batch=batch)
        logger.info("drain_memory_queue: %s", out)
        return {"status": "completed", **out}
    except Exception as exc:  # noqa: BLE001
        logger.exception("drain_memory_queue failed: %s", exc)
        return {"status": "failed", "reason": str(exc)[:300]}
    finally:
        db.close()


@celery_app.task(name="app.graph_worker.compact_memory")
def compact_memory(application_id: Optional[int] = None) -> dict:
    """Enforce memory retention/compaction (bounded growth per node)."""
    from . import memory as MEM
    db = SessionLocal()
    try:
        out = MEM.compact_once(db, application_id=application_id)
        logger.info("compact_memory: %s", out)
        return {"status": "completed", **out}
    except Exception as exc:  # noqa: BLE001
        logger.exception("compact_memory failed: %s", exc)
        return {"status": "failed", "reason": str(exc)[:300]}
    finally:
        db.close()
