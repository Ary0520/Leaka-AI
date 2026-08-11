"""
Slack QA Incident Notification
================================
Sends a structured QA incident report to a Slack channel via Incoming Webhooks
(free, no OAuth, no Slack subscription tier required — just a webhook URL).

Design contract:
  - A FAILED TEST is NOT a confirmed product bug. The message says "test failure /
    QA incident" and provides evidence for a human to investigate.
  - All fields are derived from actual execution data. Nothing is invented.
  - Diagnosis is deterministic pattern-matching, explicitly labelled "assessment".
  - Severity is labelled "suggested", not authoritative.
  - Deduplication key is exposed so callers can suppress repeated identical failures.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

import requests


# ---------------------------------------------------------------------------
# Diagnosis helpers — deterministic, no LLM call, no cost
# ---------------------------------------------------------------------------

_CATEGORY_PATTERNS: list[tuple[list[str], str, str]] = [
    # (keywords_in_error_or_result, category_label, example_note)
    (
        ["timeout", "timed out", "navigation timeout", "waiting for"],
        "Environment / infrastructure issue",
        "The agent timed out waiting for a page element or navigation. "
        "This may indicate a slow environment, a broken page state, or a "
        "flaky network condition rather than a product logic error.",
    ),
    (
        ["element not found", "no element", "could not find", "unable to locate",
         "selector", "xpath", "locator"],
        "Test configuration / selector issue",
        "The agent could not locate an expected UI element. "
        "The element may have been renamed, removed, or the test prompt may "
        "need updating to match the current UI.",
    ),
    (
        ["login", "sign in", "authentication", "unauthorized", "403", "401",
         "session", "credentials"],
        "Test configuration / test-data issue",
        "The failure occurred during or after an authentication step. "
        "Test credentials or session state may be invalid or expired.",
    ),
    (
        ["price", "total", "amount", "discount", "coupon", "promo", "charge",
         "payment", "checkout", "cart", "order", "billing"],
        "Possible product behavior issue",
        "The failure involves a financial or commerce flow. "
        "The observed result differed from the expected calculation or state. "
        "Requires human verification against product requirements.",
    ),
    (
        ["max steps", "max_steps", "exceeded", "limit reached"],
        "Agent execution issue",
        "The agent reached its step limit without completing the task. "
        "The flow may be longer than expected, or the agent may be stuck "
        "in a loop. Consider increasing max_steps or simplifying the prompt.",
    ),
]


def _classify_failure(
    final_result: Optional[str],
    error_message: Optional[str],
    success_criteria: Optional[str],
    failed_action: Optional[str],
) -> tuple[str, str, str]:
    """
    Returns (category, note, confidence) based on available text signals.
    Confidence: 'High' | 'Medium' | 'Low'
    """
    corpus = " ".join(
        s.lower() for s in [
            final_result or "",
            error_message or "",
            success_criteria or "",
            failed_action or "",
        ]
    )

    for keywords, category, note in _CATEGORY_PATTERNS:
        if any(kw in corpus for kw in keywords):
            confidence = "High" if sum(1 for kw in keywords if kw in corpus) >= 2 else "Medium"
            return category, note, confidence

    return (
        "Unknown",
        "Insufficient evidence to determine a likely failure category. "
        "Review the execution trace and screenshot in the dashboard.",
        "Low",
    )


def _infer_severity(
    category: str,
    success_criteria: Optional[str],
    failed_action: Optional[str],
) -> Optional[str]:
    """
    Returns 'Critical' | 'High' | 'Medium' | 'Low' | None.
    Only returns a value when there is reasonable signal.
    """
    corpus = " ".join(s.lower() for s in [
        success_criteria or "",
        failed_action or "",
        category.lower(),
    ])

    critical_signals = ["payment", "charge", "transaction", "purchase", "checkout",
                        "billing", "fraud", "data loss", "security"]
    high_signals = ["price", "total", "discount", "coupon", "promo", "order",
                    "cart", "revenue", "possible product behavior"]
    low_signals = ["test configuration", "agent execution", "selector",
                   "environment / infrastructure"]

    if any(s in corpus for s in critical_signals):
        return "Critical"
    if any(s in corpus for s in high_signals):
        return "High"
    if any(s in corpus for s in low_signals):
        return "Low"
    if "unknown" not in corpus:
        return "Medium"
    return None


# ---------------------------------------------------------------------------
# Deduplication key
# ---------------------------------------------------------------------------

def incident_dedup_key(
    test_name: str,
    failed_action: Optional[str],
    category: str,
) -> str:
    """
    A stable hash of (test_name, failed_action, category).
    Callers can use this to suppress repeated identical incidents
    within a time window (e.g. store in Redis with a TTL).
    Currently exposed for future use — not enforced here.
    """
    raw = f"{test_name}|{failed_action or ''}|{category}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Public send function
# ---------------------------------------------------------------------------

def send_qa_incident(
    *,
    webhook_url: str,
    # Identity
    test_name: str,
    job_id: str,
    timestamp_iso: Optional[str] = None,
    target_url: Optional[str] = None,
    # What happened
    expected_result: Optional[str] = None,   # = success_criteria
    actual_result: Optional[str] = None,     # = final_result from agent
    # Failure location (derived from action_history)
    failed_step_index: Optional[int] = None,  # 1-based for display
    total_steps: Optional[int] = None,
    failed_action_label: Optional[str] = None,  # human-readable action
    preceding_action_label: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    # Reproduction
    repro_steps: Optional[list[str]] = None,
    # Evidence
    screenshot_url: Optional[str] = None,   # direct URL to the screenshot
    dashboard_run_url: Optional[str] = None,
    # Raw error (hard crashes only)
    error_message: Optional[str] = None,
    # Linear
    linear_issue_url: Optional[str] = None,
    linear_identifier: Optional[str] = None,
) -> dict[str, Any]:
    """
    POST a structured QA incident Block Kit message to a Slack Incoming Webhook.
    Returns {"ok": True} on success, {"ok": False, "reason": ...} on failure.
    """

    # ── Diagnosis ─────────────────────────────────────────────────────────────
    category, diag_note, confidence = _classify_failure(
        actual_result, error_message, expected_result, failed_action_label
    )
    severity = _infer_severity(category, expected_result, failed_action_label)

    # ── Dedup key (returned in response for caller use) ──────────────────────
    dedup_key = incident_dedup_key(test_name, failed_action_label, category)

    # ── Timestamp ─────────────────────────────────────────────────────────────
    ts_display = timestamp_iso or "—"
    if ts_display and "T" in ts_display:
        # "2026-08-08T14:32:11.000000" → "Aug 8, 2026 · 14:32"
        # Avoid %-d (POSIX-only); strip leading zero from %d for Windows too.
        try:
            from datetime import datetime as _dt
            dt = _dt.fromisoformat(ts_display.replace("Z", ""))
            ts_display = dt.strftime("%b %d, %Y · %H:%M").replace(" 0", " ", 1)
        except Exception:
            ts_display = ts_display[:16].replace("T", " · ")

    # ── Build blocks ──────────────────────────────────────────────────────────
    blocks: list[dict[str, Any]] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": "🔴  TEST FAILED — QA Incident", "emoji": True},
    })

    # Status row
    status_fields: list[dict] = [
        {"type": "mrkdwn", "text": f"*Test*\n{test_name}"},
        {"type": "mrkdwn", "text": f"*Run*\n{ts_display}"},
    ]
    if target_url:
        status_fields.append({"type": "mrkdwn", "text": f"*Environment*\n<{target_url}|{target_url}>"})
    blocks.append({"type": "section", "fields": status_fields})

    blocks.append({"type": "divider"})

    # What happened
    what_fields: list[dict] = []
    if expected_result:
        what_fields.append({
            "type": "mrkdwn",
            "text": f"*EXPECTED*\n{expected_result[:300]}",
        })
    if actual_result:
        what_fields.append({
            "type": "mrkdwn",
            "text": f"*ACTUAL*\n{actual_result[:300]}",
        })
    if what_fields:
        blocks.append({"type": "section", "fields": what_fields})
    elif error_message:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*WHAT HAPPENED*\n```{error_message[:400]}```",
            },
        })

    # Failure location
    if failed_step_index is not None or failed_action_label:
        step_str = (
            f"Step {failed_step_index} / {total_steps}"
            if failed_step_index and total_steps
            else f"Step {failed_step_index}" if failed_step_index
            else "—"
        )
        location_lines = [f"*FAILED AT*\n{step_str}"]
        if failed_action_label:
            location_lines.append(f"*Failed action:* {failed_action_label}")
        if preceding_action_label:
            location_lines.append(f"*Preceding action:* {preceding_action_label}")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(location_lines)},
        })

    # Reproduction steps
    if repro_steps:
        numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(repro_steps[:10]))
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*REPRODUCTION*\n{numbered}",
            },
        })

    blocks.append({"type": "divider"})

    # Assessment
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f"*ASSESSMENT* _(not a confirmed root cause)_\n"
                f"*{category}*\n"
                f"{diag_note}\n"
                f"_Confidence: {confidence}_"
            ),
        },
    })

    # Severity
    if severity:
        sev_emoji = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(severity, "⚪")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*SUGGESTED SEVERITY*\n{sev_emoji} {severity}",
            },
        })

    blocks.append({"type": "divider"})

    # Action buttons
    action_elements: list[dict] = []
    if dashboard_run_url:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "View Run", "emoji": True},
            "url": dashboard_run_url,
            "style": "danger",
        })
    if screenshot_url:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "View Screenshot", "emoji": True},
            "url": screenshot_url,
        })
    if dashboard_run_url:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Technical Evidence", "emoji": True},
            "url": f"{dashboard_run_url}#evidence" if "#" not in dashboard_run_url else dashboard_run_url,
        })
    if linear_issue_url:
        label = f"Linear {linear_identifier}" if linear_identifier else "Linear Issue"
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": label, "emoji": True},
            "url": linear_issue_url,
        })

    if action_elements:
        # Slack limits action blocks to 5 elements
        blocks.append({"type": "actions", "elements": action_elements[:5]})

    # Context footer
    duration_str = f" · {duration_seconds}s" if isinstance(duration_seconds, int) else ""
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": (
                f"Leaka AI · job `{job_id[:12]}…`{duration_str} · "
                f"dedup key `{dedup_key}` · "
                "_Assess before escalating. Not a confirmed bug._"
            ),
        }],
    })

    # ── POST ──────────────────────────────────────────────────────────────────
    fallback_text = (
        f"🔴 TEST FAILED: {test_name}"
        + (f" — {actual_result[:120]}" if actual_result else "")
    )
    payload = {"text": fallback_text, "blocks": blocks}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if 200 <= resp.status_code < 300:
            return {"ok": True, "status_code": resp.status_code, "dedup_key": dedup_key}
        return {
            "ok": False,
            "status_code": resp.status_code,
            "body": resp.text[:500],
            "dedup_key": dedup_key,
        }
    except Exception as exc:
        return {"ok": False, "reason": f"request_error: {exc}", "dedup_key": dedup_key}
