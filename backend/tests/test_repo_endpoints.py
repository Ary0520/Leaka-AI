"""
Repo connection + webhook endpoint tests (Task 18 & 18.1).

Covers: connect stores only encrypted secret refs (never plaintext, never
echoed — R9.3); GET is masked; cross-tenant 404; and Property 12 (webhook
authenticity): mismatched-HMAC always rejected, replayed delivery ids deduped.
`verify_connection` is mocked (no network); webhook bodies are signed with the
real HMAC helper.
"""

from __future__ import annotations

import json
import uuid

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user
from app.database import SessionLocal, engine, Base
from app.models import Application, RepoConnection, CodeDiff
from app.integrations import github_client as GH

Base.metadata.create_all(bind=engine)

OWNER = f"REPOEP_{uuid.uuid4().hex[:8]}"
OTHER = f"OTHER_{uuid.uuid4().hex[:8]}"
_current = {"sub": OWNER}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: dict(_current)
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _mock_verify(monkeypatch):
    # Repo connection verification never hits the network in tests.
    monkeypatch.setattr(GH, "verify_connection",
                        lambda token, repo: {"connected": True, "reason": "Connected.",
                                             "repo": repo, "private": True})
    yield


client = TestClient(app)


def _seed_app(owner: str) -> int:
    db = SessionLocal()
    try:
        a = Application(owner_id=owner, name="RepoEP", base_url="https://s.com")
        db.add(a); db.commit()
        return a.id
    finally:
        db.close()


def _cleanup(owner: str):
    db = SessionLocal()
    try:
        app_ids = [a.id for a in db.query(Application).filter(Application.owner_id == owner).all()]
        if app_ids:
            db.query(CodeDiff).filter(CodeDiff.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(RepoConnection).filter(RepoConnection.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_connect_repo_never_echoes_secret_and_stores_ref():
    _current["sub"] = OWNER
    try:
        app_id = _seed_app(OWNER)
        secret_token = "ghp_SUPERSECRETTOKEN123"
        webhook_secret = "wh_SECRET_456"
        r = client.post(f"/api/applications/{app_id}/repo", json={
            "repo_full_name": "org/repo", "token": secret_token,
            "webhook_secret": webhook_secret,
        })
        assert r.status_code == 200
        body = r.json()
        # Response never contains the secrets.
        raw = json.dumps(body)
        assert secret_token not in raw
        assert webhook_secret not in raw
        assert body["secret_set"] is True
        assert body["webhook_secret_set"] is True
        assert body["status"] == "connected"

        # DB stores encrypted refs, NOT plaintext.
        db = SessionLocal()
        try:
            conn = db.query(RepoConnection).filter(RepoConnection.application_id == app_id).first()
            assert conn.secret_ref and secret_token not in conn.secret_ref
            assert conn.secret_ref.startswith("enc:v1:")
            assert conn.webhook_secret_ref and webhook_secret not in conn.webhook_secret_ref
        finally:
            db.close()
    finally:
        _cleanup(OWNER)


def test_get_repo_masked_and_cross_tenant_404():
    _current["sub"] = OWNER
    try:
        app_id = _seed_app(OWNER)
        client.post(f"/api/applications/{app_id}/repo", json={
            "repo_full_name": "org/repo", "token": "ghp_x", "webhook_secret": "wh"})

        got = client.get(f"/api/applications/{app_id}/repo").json()
        assert got["repo_full_name"] == "org/repo"
        assert "token" not in json.dumps(got)

        # Cross-tenant → 404.
        _current["sub"] = OTHER
        assert client.get(f"/api/applications/{app_id}/repo").status_code == 404
    finally:
        _current["sub"] = OWNER
        _cleanup(OWNER)


def test_disconnect_repo():
    _current["sub"] = OWNER
    try:
        app_id = _seed_app(OWNER)
        client.post(f"/api/applications/{app_id}/repo", json={
            "repo_full_name": "org/repo", "token": "ghp_x"})
        assert client.delete(f"/api/applications/{app_id}/repo").status_code == 204
        assert client.get(f"/api/applications/{app_id}/repo").json() is None
    finally:
        _cleanup(OWNER)


def _connect_with_webhook_secret(app_id: int, repo: str, wh_secret: str):
    client.post(f"/api/applications/{app_id}/repo", json={
        "repo_full_name": repo, "token": "ghp_x", "webhook_secret": wh_secret})


def _pr_payload(repo: str) -> bytes:
    return json.dumps({
        "action": "opened", "number": 42,
        "repository": {"full_name": repo},
        "pull_request": {"number": 42, "head": {"sha": "abc123", "ref": "feature"}},
    }).encode("utf-8")


def test_webhook_valid_signature_accepted():
    _current["sub"] = OWNER
    try:
        app_id = _seed_app(OWNER)
        repo, wh = "org/hooktest", "wh_secret_valid"
        _connect_with_webhook_secret(app_id, repo, wh)

        body = _pr_payload(repo)
        sig = GH.compute_signature(body, wh)
        r = client.post("/api/webhooks/github", content=body, headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Delivery": "delivery-aaa",
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        })
        assert r.status_code == 200
        assert r.json()["received"] is True
        assert r.json()["diff_id"] is not None
    finally:
        _cleanup(OWNER)


def test_webhook_replay_is_deduped():
    _current["sub"] = OWNER
    try:
        app_id = _seed_app(OWNER)
        repo, wh = "org/replaytest", "wh_secret_replay"
        _connect_with_webhook_secret(app_id, repo, wh)
        body = _pr_payload(repo)
        sig = GH.compute_signature(body, wh)
        headers = {"X-Hub-Signature-256": sig, "X-GitHub-Delivery": "delivery-dup",
                   "X-GitHub-Event": "pull_request", "Content-Type": "application/json"}
        r1 = client.post("/api/webhooks/github", content=body, headers=headers)
        r2 = client.post("/api/webhooks/github", content=body, headers=headers)
        assert r1.status_code == 200 and r2.status_code == 200
        assert "Duplicate" in r2.json()["detail"]
        # Only ONE CodeDiff created for the replayed delivery.
        db = SessionLocal()
        try:
            n = db.query(CodeDiff).filter(CodeDiff.delivery_id == "delivery-dup").count()
            assert n == 1
        finally:
            db.close()
    finally:
        _cleanup(OWNER)


def test_webhook_no_secret_rejected():
    _current["sub"] = OWNER
    try:
        app_id = _seed_app(OWNER)
        # Connect WITHOUT a webhook secret.
        client.post(f"/api/applications/{app_id}/repo", json={
            "repo_full_name": "org/nosecret", "token": "ghp_x"})
        body = _pr_payload("org/nosecret")
        r = client.post("/api/webhooks/github", content=body, headers={
            "X-Hub-Signature-256": "sha256=deadbeef",
            "X-GitHub-Delivery": "d1", "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json"})
        assert r.status_code == 401
    finally:
        _cleanup(OWNER)


# ---------------------------------------------------------------------------
# Property 12 — webhook authenticity: mismatched HMAC ALWAYS rejected.
# ---------------------------------------------------------------------------
@settings(max_examples=25, deadline=None,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
@given(bad_sig_suffix=st.text(alphabet="0123456789abcdef", min_size=0, max_size=64))
def test_property_mismatched_hmac_always_rejected(bad_sig_suffix):
    _current["sub"] = OWNER
    try:
        app_id = _seed_app(OWNER)
        repo, wh = f"org/prop{uuid.uuid4().hex[:6]}", "wh_prop_secret"
        _connect_with_webhook_secret(app_id, repo, wh)
        body = _pr_payload(repo)
        # A signature that is NOT the correct HMAC for (body, wh).
        wrong_sig = "sha256=" + (bad_sig_suffix or "00")
        # Ensure it's actually wrong (astronomically unlikely to collide, but guard).
        if wrong_sig == GH.compute_signature(body, wh):
            wrong_sig = "sha256=deadbeefdeadbeef"
        r = client.post("/api/webhooks/github", content=body, headers={
            "X-Hub-Signature-256": wrong_sig,
            "X-GitHub-Delivery": f"d-{uuid.uuid4().hex[:8]}",
            "X-GitHub-Event": "pull_request", "Content-Type": "application/json"})
        assert r.status_code == 401, "a mismatched HMAC was NOT rejected"
    finally:
        _cleanup(OWNER)
