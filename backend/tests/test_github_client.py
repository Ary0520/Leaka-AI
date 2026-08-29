"""
GitHub client tests (Task 17, Requirements 6.1, 6.2, 6.3, 6.7, 9.5).

Webhook signature verification is validated against GitHub's OFFICIAL published
test vector. Connection/PR-files calls mock `requests` (no network).
"""

from __future__ import annotations

import pytest

from app.integrations import github_client as GH


# ---------------------------------------------------------------------------
# Webhook signature — validated against GitHub's official test vector.
# secret = "It's a Secret to Everybody", payload = "Hello, World!"
# expected = sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17
# (from docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
# ---------------------------------------------------------------------------
_OFFICIAL_SECRET = "It's a Secret to Everybody"
_OFFICIAL_BODY = b"Hello, World!"
_OFFICIAL_SIG = "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"


def test_compute_signature_matches_github_official_vector():
    assert GH.compute_signature(_OFFICIAL_BODY, _OFFICIAL_SECRET) == _OFFICIAL_SIG


def test_verify_webhook_signature_accepts_valid():
    assert GH.verify_webhook_signature(_OFFICIAL_BODY, _OFFICIAL_SIG, _OFFICIAL_SECRET) is True


def test_verify_webhook_signature_rejects_tampered_body():
    assert GH.verify_webhook_signature(b"Goodbye, World!", _OFFICIAL_SIG, _OFFICIAL_SECRET) is False


def test_verify_webhook_signature_rejects_wrong_secret():
    assert GH.verify_webhook_signature(_OFFICIAL_BODY, _OFFICIAL_SIG, "wrong-secret") is False


def test_verify_webhook_signature_rejects_missing_or_malformed():
    assert GH.verify_webhook_signature(_OFFICIAL_BODY, None, _OFFICIAL_SECRET) is False
    assert GH.verify_webhook_signature(_OFFICIAL_BODY, "", _OFFICIAL_SECRET) is False
    assert GH.verify_webhook_signature(_OFFICIAL_BODY, "sha1=abc", _OFFICIAL_SECRET) is False
    assert GH.verify_webhook_signature(_OFFICIAL_BODY, "no-prefix", _OFFICIAL_SECRET) is False
    assert GH.verify_webhook_signature(_OFFICIAL_BODY, _OFFICIAL_SIG, "") is False


def test_roundtrip_sign_then_verify():
    body = b'{"action":"opened","number":42}'
    secret = "s3cr3t-token"
    sig = GH.compute_signature(body, secret)
    assert GH.verify_webhook_signature(body, sig, secret) is True
    # Any byte change breaks verification.
    assert GH.verify_webhook_signature(body + b" ", sig, secret) is False


# ---------------------------------------------------------------------------
# Repo split
# ---------------------------------------------------------------------------
def test_split_repo():
    assert GH._split_repo("org/repo") == ("org", "repo")
    assert GH._split_repo(" org/repo/ ") == ("org", "repo")
    for bad in ["", "no-slash", "a/b/c", "/x", "x/"]:
        with pytest.raises(ValueError):
            GH._split_repo(bad)


# ---------------------------------------------------------------------------
# verify_connection — mock requests
# ---------------------------------------------------------------------------
class _Resp:
    def __init__(self, status_code, json_data=None, headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = headers or {}
        self.content = b"x" if json_data is not None else b""

    def json(self):
        return self._json


def test_verify_connection_success(monkeypatch):
    monkeypatch.setattr(GH.requests, "get", lambda *a, **k: _Resp(200, {"private": True}))
    out = GH.verify_connection("tok", "org/repo")
    assert out["connected"] is True
    assert out["private"] is True


def test_verify_connection_401(monkeypatch):
    monkeypatch.setattr(GH.requests, "get", lambda *a, **k: _Resp(401))
    out = GH.verify_connection("badtok", "org/repo")
    assert out["connected"] is False
    assert "Authentication failed" in out["reason"]


def test_verify_connection_404(monkeypatch):
    monkeypatch.setattr(GH.requests, "get", lambda *a, **k: _Resp(404))
    out = GH.verify_connection("tok", "org/missing")
    assert out["connected"] is False
    assert "not found" in out["reason"].lower()


def test_verify_connection_rate_limited(monkeypatch):
    monkeypatch.setattr(GH.requests, "get",
                        lambda *a, **k: _Resp(403, headers={"X-RateLimit-Remaining": "0"}))
    out = GH.verify_connection("tok", "org/repo")
    assert out["connected"] is False
    assert "rate limit" in out["reason"].lower()


def test_verify_connection_no_token():
    out = GH.verify_connection("", "org/repo")
    assert out["connected"] is False


def test_verify_connection_bad_repo():
    out = GH.verify_connection("tok", "not-a-repo")
    assert out["connected"] is False
    assert "owner/repo" in out["reason"]


# ---------------------------------------------------------------------------
# fetch_pr_files — mock requests (single page + pagination + error)
# ---------------------------------------------------------------------------
def test_fetch_pr_files_single_page(monkeypatch):
    files = [
        {"filename": "src/app/checkout.py", "status": "modified", "additions": 10,
         "deletions": 2, "changes": 12, "patch": "@@ -1 +1 @@"},
        {"filename": "README.md", "status": "added", "additions": 5, "deletions": 0,
         "changes": 5, "patch": "@@ +1 @@"},
    ]
    monkeypatch.setattr(GH.requests, "get", lambda *a, **k: _Resp(200, files))
    out = GH.fetch_pr_files("tok", "org/repo", 42)
    assert len(out) == 2
    assert out[0]["path"] == "src/app/checkout.py"
    assert out[0]["status"] == "modified"
    assert out[0]["patch"] == "@@ -1 +1 @@"


def test_fetch_pr_files_pagination(monkeypatch):
    # First page full (100), second page short → stops.
    page1 = [{"filename": f"f{i}.py", "status": "modified", "additions": 1,
              "deletions": 0, "changes": 1, "patch": "p"} for i in range(100)]
    page2 = [{"filename": "last.py", "status": "added", "additions": 1,
              "deletions": 0, "changes": 1, "patch": "p"}]

    calls = {"n": 0}

    def _get(url, headers=None, params=None, timeout=None):
        calls["n"] += 1
        return _Resp(200, page1 if params["page"] == 1 else page2)

    monkeypatch.setattr(GH.requests, "get", _get)
    out = GH.fetch_pr_files("tok", "org/repo", 7)
    assert len(out) == 101
    assert calls["n"] == 2


def test_fetch_pr_files_auth_error_raises(monkeypatch):
    monkeypatch.setattr(GH.requests, "get", lambda *a, **k: _Resp(401))
    with pytest.raises(RuntimeError):
        GH.fetch_pr_files("badtok", "org/repo", 1)
