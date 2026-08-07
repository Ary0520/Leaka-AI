from typing import Any, Optional

import requests

from ..config import settings


def _webhook_available() -> bool:
    return bool(settings.SLACK_WEBHOOK_URL)


def send_test_failure_alert(
    test_name: str,
    job_id: str,
    total_steps: Optional[int] = None,
    duration_seconds: Optional[int] = None,
    success_criteria: Optional[str] = None,
    error_message: Optional[str] = None,
    target_url: Optional[str] = None,
    dashboard_url: Optional[str] = None,
) -> dict[str, Any]:
    if not _webhook_available():
        return {
            "ok": False,
            "reason": "SLACK_WEBHOOK_URL is not configured in environment.",
        }

    duration_fmt = (
        f"{duration_seconds}s"
        if isinstance(duration_seconds, int)
        else "—"
    )
    steps_fmt = str(total_steps) if isinstance(total_steps, int) else "—"
    criteria_preview = (
        success_criteria[:200] + ("…" if len(success_criteria) > 200 else "")
        if success_criteria
        else "N/A"
    )
    error_preview = (
        error_message[:200] + ("…" if len(error_message) > 200 else "")
        if error_message
        else "No error captured"
    )

    blocks: list[dict[str, Any]] = []

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "🚨 QA Test Failure Detected",
            "emoji": True,
        },
    })

    blocks.append({
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"*Test:*\n{test_name}"},
            {"type": "mrkdwn", "text": f"*Job ID:*\n`{job_id[:12]}…{job_id[-6:]}`"},
            {"type": "mrkdwn", "text": f"*Steps:*\n{steps_fmt}"},
            {"type": "mrkdwn", "text": f"*Duration:*\n{duration_fmt}"},
        ],
    })

    if target_url:
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Target URL:*\n<{target_url}|Open in browser>",
                },
            ],
        })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*Success Criteria:*\n{criteria_preview}",
        },
    })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*Error / Failure Reason:*\n```\n{error_preview}\n```",
        },
    })

    action_elements: list[dict[str, Any]] = []
    if dashboard_url:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "View in Dashboard", "emoji": True},
            "style": "danger",
            "url": dashboard_url,
        })
    if target_url:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Open Target URL", "emoji": False},
            "url": target_url,
        })
    if action_elements:
        blocks.append({"type": "actions", "elements": action_elements})

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "_Automatic alert from Leaka AI — verify and escalate via Linear ticket in dashboard._",
            }
        ],
    })

    payload: dict[str, Any] = {
        "text": f"🚨 QA failure: {test_name} (job {job_id[:8]}…)",
        "blocks": blocks,
    }

    try:
        resp = requests.post(
            settings.SLACK_WEBHOOK_URL,
            json=payload,
            timeout=10,
        )
        if resp.status_code >= 200 and resp.status_code < 300:
            return {"ok": True, "status_code": resp.status_code}
        return {
            "ok": False,
            "status_code": resp.status_code,
            "body": resp.text[:500],
        }
    except Exception as exc:
        return {"ok": False, "reason": f"request_error: {exc}"}
