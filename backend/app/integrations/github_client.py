"""
GitHub client — repo connection verification, PR diff ingestion, and webhook
signature verification for PR Intelligence (Requirements 6.1, 6.2, 6.3, 6.6,
6.7, 9.4, 9.5).

All GitHub REST calls follow the current (2026) official API:
  - Base URL: https://api.github.com
  - Headers: Accept: application/vnd.github+json, Authorization: Bearer <token>,
             X-GitHub-Api-Version: 2026-03-10
  - Verify repo/auth: GET /repos/{owner}/{repo}
  - List PR files:    GET /repos/{owner}/{repo}/pulls/{pull_number}/files
                      (array of {sha, filename, status, additions, deletions,
                       changes, patch}; max 3000 files, 30/page, per_page ≤ 100)
  - Webhook signature: X-Hub-Signature-256 = "sha256=" + HMAC-SHA256(secret, raw_body)
    verified with a timing-safe compare (hmac.compare_digest).
  Source: GitHub REST docs — pulls/pulls and webhooks/validating-webhook-deliveries.

SECURITY — ingested code is UNTRUSTED and NEVER executed (R6.6, R9.4):
  This module only performs network reads and text parsing. It contains NO
  exec/eval/compile of ingested content, spawns NO subprocess, and writes NO
  files. Any downstream analysis of the fetched patches must likewise treat
  their contents strictly as data.

Uses `requests`, matching the other integration clients (linear/slack).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Optional

import requests

logger = logging.getLogger("revguard.github")

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"
_TIMEOUT = 15  # seconds — never block a request indefinitely
_MAX_FILES = 3000          # GitHub's hard cap for the PR files endpoint
_PER_PAGE = 100            # max page size


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------
def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "Leaka-AI-RevGuard",
    }


def _split_repo(repo_full_name: str) -> tuple[str, str]:
    """'owner/repo' → ('owner', 'repo'). Raises ValueError on malformed input."""
    parts = (repo_full_name or "").strip().strip("/").split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("repo must be in 'owner/repo' format")
    return parts[0], parts[1]


# ---------------------------------------------------------------------------
# Connection verification (R6.1, R6.2)
# ---------------------------------------------------------------------------
def verify_connection(token: str, repo_full_name: str) -> dict[str, Any]:
    """
    Verify a repo connection: token auth + repo reachability via
    GET /repos/{owner}/{repo}. Returns a classified result — never raises.

    Returns: {connected: bool, reason: str, repo: str, private: bool|None}
    """
    if not token:
        return {"connected": False, "reason": "No access token provided.", "repo": repo_full_name}
    try:
        owner, repo = _split_repo(repo_full_name)
    except ValueError as exc:
        return {"connected": False, "reason": str(exc), "repo": repo_full_name}

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    try:
        resp = requests.get(url, headers=_headers(token), timeout=_TIMEOUT)
    except requests.RequestException as exc:
        return {"connected": False, "reason": f"Network error reaching GitHub: {exc}",
                "repo": repo_full_name}

    if resp.status_code == 200:
        data = resp.json() if resp.content else {}
        return {"connected": True, "reason": "Connected.", "repo": repo_full_name,
                "private": bool(data.get("private"))}
    if resp.status_code == 401:
        return {"connected": False, "reason": "Authentication failed — the token is invalid or expired.",
                "repo": repo_full_name}
    if resp.status_code == 403:
        # Could be rate limit or insufficient scope.
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            return {"connected": False, "reason": "GitHub rate limit exceeded — try again later.",
                    "repo": repo_full_name}
        return {"connected": False, "reason": "Access forbidden — the token lacks permission for this repo.",
                "repo": repo_full_name}
    if resp.status_code == 404:
        return {"connected": False,
                "reason": "Repository not found or the token has no access to it.",
                "repo": repo_full_name}
    return {"connected": False,
            "reason": f"Unexpected GitHub response ({resp.status_code}).",
            "repo": repo_full_name}


# ---------------------------------------------------------------------------
# PR diff ingestion (R6.3)
# ---------------------------------------------------------------------------
def fetch_pr_files(token: str, repo_full_name: str, pr_number: int | str) -> list[dict[str, Any]]:
    """
    Fetch the changed files (paths + patch hunks) for a pull request via
    GET /repos/{owner}/{repo}/pulls/{pull_number}/files, following pagination.

    Returns a list of {path, status, additions, deletions, changes, patch}.
    The `patch` text is UNTRUSTED data — callers must never execute it.

    Raises RuntimeError on auth/reachability failure so the caller (repo_worker)
    can record a classified ingest failure without partial writes (R6.5).
    """
    owner, repo = _split_repo(repo_full_name)
    out: list[dict[str, Any]] = []
    page = 1
    while len(out) < _MAX_FILES:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        try:
            resp = requests.get(
                url, headers=_headers(token),
                params={"per_page": _PER_PAGE, "page": page}, timeout=_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Network error fetching PR files: {exc}") from exc

        if resp.status_code == 401:
            raise RuntimeError("Authentication failed fetching PR files (token invalid/expired).")
        if resp.status_code == 403:
            raise RuntimeError("Access forbidden or rate-limited fetching PR files.")
        if resp.status_code == 404:
            raise RuntimeError("Pull request or repository not found.")
        if resp.status_code != 200:
            raise RuntimeError(f"Unexpected GitHub response fetching PR files ({resp.status_code}).")

        batch = resp.json() if resp.content else []
        if not isinstance(batch, list) or not batch:
            break
        for f in batch:
            out.append({
                "path": f.get("filename"),
                "status": f.get("status"),            # added|modified|removed|renamed|...
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "changes": f.get("changes", 0),
                "patch": f.get("patch"),              # UNTRUSTED text; may be None for binary
                "previous_filename": f.get("previous_filename"),
            })
        if len(batch) < _PER_PAGE:
            break  # last page
        page += 1

    return out[:_MAX_FILES]


# ---------------------------------------------------------------------------
# Webhook signature verification (R6.7, R9.5)
# ---------------------------------------------------------------------------
def verify_webhook_signature(
    raw_body: bytes, signature_header: Optional[str], secret: str
) -> bool:
    """
    Verify a GitHub webhook delivery per the official spec:
      expected = "sha256=" + HMAC_SHA256(secret, raw_body).hexdigest()
    compared to the X-Hub-Signature-256 header with a TIMING-SAFE compare.

    Args:
      raw_body: the EXACT raw request body bytes (never re-serialized JSON).
      signature_header: the X-Hub-Signature-256 header value ("sha256=...").
      secret: the shared webhook secret.

    Returns True only on an authentic, matching signature. Missing header/secret
    or any malformed input returns False (reject).
    """
    if not signature_header or not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    if raw_body is None:
        return False

    mac = hmac.new(
        secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    )
    expected = "sha256=" + mac.hexdigest()
    # Constant-time comparison to mitigate timing attacks (never use ==).
    try:
        return hmac.compare_digest(expected, signature_header)
    except Exception:
        return False


def compute_signature(raw_body: bytes, secret: str) -> str:
    """
    Helper (used by tests and to sign outbound test payloads): produce the
    X-Hub-Signature-256 value for a body + secret.
    """
    mac = hmac.new(secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256)
    return "sha256=" + mac.hexdigest()

def post_commit_status(token: str, repo_full_name: str, sha: str, state: str, description: str, target_url: Optional[str] = None, context: str = "leaka-ai/qa") -> bool:
    """
    Update a commit status in GitHub for CI/CD pipeline gating.
    State must be one of: error, failure, pending, or success.
    """
    if not token or not repo_full_name or not sha:
        return False
        
    try:
        owner, repo = _split_repo(repo_full_name)
    except ValueError:
        return False

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/statuses/{sha}"
    payload = {
        "state": state,
        "description": description[:140], # GitHub max
        "context": context
    }
    if target_url:
        payload["target_url"] = target_url
        
    try:
        resp = requests.post(url, json=payload, headers=_headers(token), timeout=_TIMEOUT)
        if resp.status_code == 201:
            logger.info("Successfully posted %s commit status to %s on %s", state, sha, repo_full_name)
            return True
        logger.warning("Failed to post commit status: HTTP %s: %s", resp.status_code, resp.text)
        return False
    except Exception as e:
        logger.error("Exception posting commit status: %s", e)
        return False
