"""
End-to-end PR Intelligence test (Task 20): ingest_diff → map_code_diff →
/recommendation → /run. GitHub calls and test-run dispatch are mocked (no
network, no real browser).
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user
from app.database import SessionLocal, engine, Base
from app.models import (
    Application, GraphNode, CoverageVerdict, CoverageLink, TestCase,
    RepoConnection, CodeDiff, FlowMapping, AppMapNode,
)
from app import repo_worker as RW
from app.integrations import github_client as GH

Base.metadata.create_all(bind=engine)

OWNER = f"REPOW_{uuid.uuid4().hex[:8]}"
_current = {"sub": OWNER}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: dict(_current)
    yield
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)


def _seed() -> dict:
    """App + active graph node (/checkout) + coverage link to a test + repo conn + a pending diff."""
    db = SessionLocal()
    try:
        a = Application(owner_id=OWNER, name="RepoW", base_url="https://s.com")
        db.add(a); db.flush()
        node = GraphNode(owner_id=OWNER, application_id=a.id,
                         canonical_key=uuid.uuid4().hex[:16], node_type="page",
                         label="Checkout", url_pattern="/checkout", status="active",
                         risk=json.dumps({"level": "Critical", "score": 95}))
        db.add(node); db.flush()
        # AppMapNode so canonical_key + suggested_prompt join works.
        db.add(AppMapNode(owner_id=OWNER, application_id=a.id, node_type="page",
                          label="Checkout", url="https://s.com/checkout",
                          suggested_prompt="Test checkout"))
        tc = TestCase(owner_id=OWNER, name="Checkout test", prompt="do checkout")
        db.add(tc); db.flush()
        db.add(CoverageLink(owner_id=OWNER, application_id=a.id, node_id=node.id,
                            test_case_id=tc.id, source="generated"))
        db.add(CoverageVerdict(owner_id=OWNER, application_id=a.id, node_id=node.id,
                               state="covered", confidence_milli=900))
        conn = RepoConnection(owner_id=OWNER, application_id=a.id, provider="github",
                              repo_full_name="org/repo", secret_ref="enc:v1:dummy")
        db.add(conn); db.flush()
        diff = CodeDiff(owner_id=OWNER, application_id=a.id, repo_connection_id=conn.id,
                        pr_number="42", ingest_status="pending", delivery_id=f"d-{uuid.uuid4().hex[:8]}")
        db.add(diff); db.commit()
        return {"app_id": a.id, "node_id": node.id, "tc_id": tc.id,
                "conn_id": conn.id, "diff_id": diff.id}
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
            db.query(CoverageLink).filter(CoverageLink.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(CoverageVerdict).filter(CoverageVerdict.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(AppMapNode).filter(AppMapNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        # Test runs created by /run.
        from app.models import TestRun
        db.query(TestRun).filter(TestRun.owner_id == OWNER).delete(synchronize_session=False)
        db.query(TestCase).filter(TestCase.owner_id == OWNER).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_ingest_map_recommend_run(monkeypatch):
    try:
        ids = _seed()
        # Mock GitHub: return a changed file that route-matches /checkout, and a
        # usable token via secrets_store.resolve_secret_ref.
        monkeypatch.setattr(GH, "fetch_pr_files", lambda token, repo, pr: [
            {"path": "src/pages/checkout.tsx", "status": "modified",
             "additions": 5, "deletions": 1, "changes": 6, "patch": "@@ +1 @@"},
            {"path": "README.md", "status": "modified", "additions": 1,
             "deletions": 0, "changes": 1, "patch": None},
        ])
        import app.repo_worker as RWmod
        monkeypatch.setattr(RWmod, "_dispatch_map", lambda diff_id: RWmod.map_code_diff.run(diff_id))
        # Provide a token.
        import app.secrets_store as SS
        monkeypatch.setattr(SS, "resolve_secret_ref", lambda ref: "ghp_token")
        # repo_worker imports resolve_secret_ref locally inside ingest_diff, so
        # patch the module attribute it will import from.
        monkeypatch.setattr("app.secrets_store.resolve_secret_ref", lambda ref: "ghp_token")

        out = RW.ingest_diff.run(ids["diff_id"])
        assert out["status"] == "completed"
        assert out["files"] == 2

        # A FlowMapping for the checkout node now exists.
        db = SessionLocal()
        try:
            fms = db.query(FlowMapping).filter(FlowMapping.code_diff_id == ids["diff_id"]).all()
            assert len(fms) == 1
            assert fms[0].node_id == ids["node_id"]
        finally:
            db.close()

        # /recommendation returns the affected flow + recommended test.
        rec = client.get(f"/api/applications/{ids['app_id']}/diffs/{ids['diff_id']}/recommendation").json()
        assert rec["status"] == "ok"
        assert len(rec["mappings"]) == 1
        assert rec["mappings"][0]["label"] == "Checkout"
        assert ids["tc_id"] in rec["recommended_test_ids"]

        # /run dispatches the recommended test (mock the run dispatch).
        import app.main as MAIN
        monkeypatch.setattr(MAIN, "_dispatch_run_task", lambda **kw: "task-mock")
        run = client.post(f"/api/applications/{ids['app_id']}/diffs/{ids['diff_id']}/run").json()
        assert len(run["job_ids"]) == 1
    finally:
        _cleanup()


def test_ingest_failure_no_partial_writes(monkeypatch):
    try:
        ids = _seed()
        monkeypatch.setattr("app.secrets_store.resolve_secret_ref", lambda ref: "ghp_token")

        def _boom(token, repo, pr):
            raise RuntimeError("Authentication failed fetching PR files (token invalid/expired).")
        monkeypatch.setattr(GH, "fetch_pr_files", _boom)

        out = RW.ingest_diff.run(ids["diff_id"])
        assert out["status"] == "failed"

        db = SessionLocal()
        try:
            d = db.query(CodeDiff).filter(CodeDiff.id == ids["diff_id"]).first()
            assert d.ingest_status == "failed"
            # No FlowMappings written on failure.
            assert db.query(FlowMapping).filter(FlowMapping.code_diff_id == ids["diff_id"]).count() == 0
        finally:
            db.close()

        rec = client.get(f"/api/applications/{ids['app_id']}/diffs/{ids['diff_id']}/recommendation").json()
        assert rec["status"] == "failed"
    finally:
        _cleanup()


def test_list_diffs():
    try:
        ids = _seed()
        r = client.get(f"/api/applications/{ids['app_id']}/diffs").json()
        assert r["total"] == 1
        assert r["diffs"][0]["pr_number"] == "42"
    finally:
        _cleanup()
