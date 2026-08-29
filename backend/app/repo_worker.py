"""
Repo worker — the I/O edge for PR Intelligence (Task 20, Requirements 6.4, 6.5,
7.1, 7.3, 7.5, 10.1, 10.2).

Two Celery tasks over the pure mapping engine:

  ingest_diff(code_diff_id):
    Fetch the PR's changed files via the GitHub client (using the connection's
    encrypted token), persist them on the CodeDiff, mark it 'ingested', then
    enqueue mapping. On failure: classified reason, status='failed', NO partial
    writes (R6.5).

  map_code_diff(code_diff_id):
    Load the app's active graph + coverage + risk, build the pure mapping
    inputs, call intelligence.mapping.map_diff(...), and persist FlowMapping
    rows (dedup by (code_diff, node)) in ONE transaction.

Ingested code is UNTRUSTED and NEVER executed (R6.6/R9.4) — we only fetch/parse.
Dispatch mirrors graph_worker's RUN_MODE pattern; kept local so the worker never
imports the FastAPI app.
"""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from .celery_app import celery_app
from .config import settings
from .database import SessionLocal
from .intelligence import mapping as MAP
from .models import (
    Application,
    AppMapNode,
    CodeDiff,
    RepoConnection,
    FlowMapping,
    GraphNode,
    CoverageVerdict,
    CoverageLink,
)

logger = logging.getLogger("revguard.repo")


# ---------------------------------------------------------------------------
# Dispatch (RUN_MODE, local to the worker)
# ---------------------------------------------------------------------------
_SYNC_EXECUTOR: Optional[ThreadPoolExecutor] = None
_EXECUTOR_LOCK = threading.Lock()


def _get_sync_executor() -> ThreadPoolExecutor:
    global _SYNC_EXECUTOR
    with _EXECUTOR_LOCK:
        if _SYNC_EXECUTOR is None:
            _SYNC_EXECUTOR = ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="revguard_repo"
            )
    return _SYNC_EXECUTOR


def _dispatch_ingest(code_diff_id: int) -> Optional[str]:
    """Enqueue diff ingestion. Never raises (webhook must not fail on dispatch)."""
    try:
        if settings.RUN_MODE == "sync_demo":
            def _run_local():
                try:
                    ingest_diff.run(code_diff_id)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("sync_demo ingest_diff raised (diff=%s): %s", code_diff_id, exc)
            _get_sync_executor().submit(_run_local)
            return f"sync-ingest-{code_diff_id}"
        task = ingest_diff.delay(code_diff_id)
        return task.id
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to dispatch ingest for diff %s: %s", code_diff_id, exc)
        return None


def _dispatch_map(code_diff_id: int) -> Optional[str]:
    try:
        if settings.RUN_MODE == "sync_demo":
            def _run_local():
                try:
                    map_code_diff.run(code_diff_id)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("sync_demo map_code_diff raised (diff=%s): %s", code_diff_id, exc)
            _get_sync_executor().submit(_run_local)
            return f"sync-map-{code_diff_id}"
        task = map_code_diff.delay(code_diff_id)
        return task.id
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to dispatch map for diff %s: %s", code_diff_id, exc)
        return None


def _classify_repo_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "authentication" in msg or "401" in msg:
        return "GitHub authentication failed (token invalid or expired)."
    if "forbidden" in msg or "rate" in msg or "403" in msg:
        return "GitHub access forbidden or rate-limited."
    if "not found" in msg or "404" in msg:
        return "Pull request or repository not found."
    if "network" in msg or "timeout" in msg or "connection" in msg:
        return "Network error reaching GitHub."
    return f"Ingestion failed: {exc}"[:500]


# ---------------------------------------------------------------------------
# ingest_diff
# ---------------------------------------------------------------------------
@celery_app.task(max_retries=1, autoretry_for=(), name="app.repo_worker.ingest_diff")
def ingest_diff(code_diff_id: int) -> dict:
    """Fetch + persist a PR's changed files, then enqueue mapping."""
    db = SessionLocal()
    try:
        diff = db.query(CodeDiff).filter(CodeDiff.id == code_diff_id).first()
        if diff is None:
            return {"status": "skipped", "reason": "code_diff_not_found"}
        conn = db.query(RepoConnection).filter(RepoConnection.id == diff.repo_connection_id).first()
        if conn is None:
            _mark_ingest_failed(db, diff, "Repo connection missing.")
            return {"status": "failed", "reason": "connection_missing"}

        if not diff.pr_number:
            # Push events without a PR number: nothing to fetch via the PR files
            # endpoint. Mark ingested with empty files (honest — no partial state).
            diff.changed_files = json.dumps([])
            diff.ingest_status = "ingested"
            db.commit()
            _dispatch_map(diff.id)
            return {"status": "completed", "files": 0, "note": "no pr_number (push event)"}

        from .integrations import github_client as GH
        from .secrets_store import resolve_secret_ref

        token = resolve_secret_ref(conn.secret_ref)
        if not token:
            _mark_ingest_failed(db, diff, "No usable access token for the repo connection.")
            return {"status": "failed", "reason": "no_token"}

        try:
            files = GH.fetch_pr_files(token, conn.repo_full_name, diff.pr_number)
        except Exception as exc:  # noqa: BLE001 — classified, no partial write
            _mark_ingest_failed(db, diff, _classify_repo_error(exc))
            return {"status": "failed", "reason": _classify_repo_error(exc)}

        # Persist changed files (paths + patch hunks — UNTRUSTED text, never run).
        diff.changed_files = json.dumps(files, default=str)
        diff.ingest_status = "ingested"
        db.commit()

        logger.info("ingest_diff done: diff=%s files=%s", diff.id, len(files))
        _dispatch_map(diff.id)
        return {"status": "completed", "files": len(files)}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("ingest_diff failed (diff=%s): %s", code_diff_id, exc)
        # Best-effort failure record without partial mapping state.
        try:
            d = db.query(CodeDiff).filter(CodeDiff.id == code_diff_id).first()
            if d is not None:
                _mark_ingest_failed(db, d, _classify_repo_error(exc))
        except Exception:
            db.rollback()
        return {"status": "failed", "reason": _classify_repo_error(exc)}
    finally:
        db.close()


def _mark_ingest_failed(db, diff: CodeDiff, reason: str) -> None:
    diff.ingest_status = "failed"
    # Record the reason on the diff without touching mapping state.
    existing = diff.changed_files
    diff.changed_files = json.dumps({"error": reason}) if not existing else existing
    db.commit()


# ---------------------------------------------------------------------------
# map_code_diff
# ---------------------------------------------------------------------------
@celery_app.task(max_retries=1, autoretry_for=(), name="app.repo_worker.map_code_diff")
def map_code_diff(code_diff_id: int) -> dict:
    """Run the pure mapping engine over an ingested diff and persist FlowMappings."""
    db = SessionLocal()
    try:
        diff = db.query(CodeDiff).filter(CodeDiff.id == code_diff_id).first()
        if diff is None:
            return {"status": "skipped", "reason": "code_diff_not_found"}
        application_id = diff.application_id
        owner_id = diff.owner_id

        changed = _load_changed_files(diff)
        map_nodes, graph_state = _build_map_nodes(db, application_id)

        diff_input = MAP.DiffInput(
            changed_files=tuple(
                MAP.ChangedFile(path=f.get("path") or "", status=f.get("status") or "modified")
                for f in changed if f.get("path")
            ),
            graph_state=graph_state,
            semantic={},  # semantic signal is optional; embedding I/O deferred
        )

        result = MAP.map_diff(diff_input, map_nodes)

        # Persist FlowMappings (dedup by (code_diff, node)); replace prior rows
        # for this diff so a re-map is idempotent.
        db.query(FlowMapping).filter(FlowMapping.code_diff_id == diff.id).delete(
            synchronize_session=False
        )
        for m in result.mappings:
            db.add(FlowMapping(
                owner_id=owner_id,
                application_id=application_id,
                code_diff_id=diff.id,
                node_id=m.node_id,
                confidence_milli=MAP.confidence_to_milli(m.confidence),
                signals=json.dumps([{"name": s.name, "detail": s.detail} for s in m.signals], default=str),
                recommended_tests=json.dumps(list(m.recommended_test_ids)),
                coverage_state=m.coverage_state,
            ))
        db.commit()

        logger.info("map_code_diff done: diff=%s status=%s mappings=%s",
                    diff.id, result.status, len(result.mappings))
        return {"status": "completed", "map_status": result.status,
                "mappings": len(result.mappings)}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("map_code_diff failed (diff=%s): %s", code_diff_id, exc)
        return {"status": "failed", "reason": str(exc)[:300]}
    finally:
        db.close()


def _load_changed_files(diff: CodeDiff) -> list[dict]:
    if not diff.changed_files:
        return []
    try:
        data = json.loads(diff.changed_files)
    except Exception:
        return []
    if isinstance(data, list):
        return data
    return []  # {"error": ...} shape → no files


def _build_map_nodes(db, application_id: int) -> tuple[list, str]:
    """
    Build mapping.MapNode inputs from the app's active graph, joining coverage
    verdicts (state) + coverage links (covering tests) + risk. Returns
    (nodes, graph_state). graph_state is 'empty' if no active nodes, else 'active'.
    """
    nodes = (
        db.query(GraphNode)
        .filter(GraphNode.application_id == application_id, GraphNode.status == "active")
        .all()
    )
    if not nodes:
        return [], MAP.GRAPH_EMPTY

    verdicts = {
        v.node_id: v for v in
        db.query(CoverageVerdict).filter(CoverageVerdict.application_id == application_id).all()
    }
    # Covering (non-orphaned) tests per node.
    covers: dict[int, list[int]] = {}
    for l in db.query(CoverageLink).filter(
        CoverageLink.application_id == application_id, CoverageLink.orphaned == False  # noqa: E712
    ).all():
        covers.setdefault(l.node_id, []).append(l.test_case_id)

    # suggested_prompt per node via AppMapNode canonical_key join.
    from .intelligence.fingerprint import Discovery, compute_canonical_key
    prompt_by_key: dict[str, str] = {}
    for amn in db.query(AppMapNode).filter(AppMapNode.application_id == application_id).all():
        key = compute_canonical_key(Discovery.from_app_map_node(amn))
        if amn.suggested_prompt:
            prompt_by_key.setdefault(key, amn.suggested_prompt)

    out = []
    for n in nodes:
        risk = _load_json(n.risk)
        verdict = verdicts.get(n.id)
        cov_state = verdict.state if verdict else MAP.COV_UNDETERMINED
        out.append(MAP.MapNode(
            node_id=n.id,
            canonical_key=n.canonical_key,
            url_pattern=n.url_pattern,
            business_category=n.business_category,
            risk_score=int(risk.get("score", 0) or 0),
            risk_level=str(risk.get("level", "Trivial")),
            coverage_state=cov_state,
            covering_test_ids=tuple(sorted(set(covers.get(n.id, [])))),
            suggested_prompt=prompt_by_key.get(n.canonical_key),
        ))
    return out, MAP.GRAPH_ACTIVE


def _load_json(val) -> dict:
    if not val:
        return {}
    try:
        parsed = json.loads(val)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}
