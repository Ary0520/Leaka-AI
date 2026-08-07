"""
Resend email integration — verified against resend==2.35.0 (installed).

API surface used:
  resend.Emails.SendParams  — TypedDict with keys: from, to, subject, html,
                               attachments (list[Attachment]), tags
  resend.Emails.SendOptions — optional second arg to .send()
  resend.emails._attachment.Attachment — TypedDict:
      content: list[int] | str   (list of byte values OR base64 string)
      filename: str
      content_type: NotRequired[str]
  resend.Emails.send(params)  → resend.Emails.SendResponse
"""
import os
from typing import Any, Iterable, Optional

import resend as resend_module  # import as alias to avoid shadowing

from ..config import settings


def _ensure_resend() -> Any:
    """Validate API key and return the resend module."""
    if not settings.RESEND_API_KEY:
        raise RuntimeError(
            "RESEND_API_KEY is not configured. Add it to backend/.env."
        )
    resend_module.api_key = settings.RESEND_API_KEY
    return resend_module


def send_email(
    *,
    to: Iterable[str],
    subject: str,
    html: str,
    from_email: Optional[str] = None,
    reply_to: Optional[str] = None,
    cc: Optional[Iterable[str]] = None,
    bcc: Optional[Iterable[str]] = None,
    attachments: Optional[list[dict[str, Any]]] = None,
    tags: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    """
    Thin wrapper over resend.Emails.send().

    attachments format (resend.Attachment):
        [{"filename": "shot.png", "content": list(open("f","rb").read())}]
    """
    r = _ensure_resend()

    params: resend_module.Emails.SendParams = {
        "from": from_email or settings.EMAIL_FROM,
        "to": list(to),
        "subject": subject,
        "html": html,
    }
    if reply_to:
        params["reply_to"] = reply_to
    if cc:
        params["cc"] = list(cc)
    if bcc:
        params["bcc"] = list(bcc)
    if attachments:
        params["attachments"] = attachments  # type: ignore[typeddict-item]
    if tags:
        params["tags"] = tags  # type: ignore[typeddict-item]

    response = r.Emails.send(params)
    # SendResponse is a dataclass-like object; convert to dict for callers
    if hasattr(response, "__dict__"):
        return vars(response)
    return dict(response) if hasattr(response, "__iter__") else {"id": str(response)}


def send_test_failure_alert(
    *,
    test_name: str,
    job_id: str,
    steps_summary: str,
    screenshot_path: Optional[str] = None,
    dashboard_url: Optional[str] = None,
) -> dict[str, Any]:
    """Send a QA failure alert email to EMAIL_ALERT_TO with optional screenshot attachment."""
    to = settings.EMAIL_ALERT_TO
    if not to:
        raise RuntimeError(
            "EMAIL_ALERT_TO not configured. Set it in backend/.env."
        )

    # Build attachment list using resend.Attachment format (content: list[int])
    attachments: list[dict[str, Any]] = []
    if screenshot_path and os.path.isfile(screenshot_path):
        with open(screenshot_path, "rb") as f:
            raw_bytes = f.read()
        attachments.append(
            {
                "filename": os.path.basename(screenshot_path),
                # resend docs: content is list of byte integers
                "content": list(raw_bytes),
                "content_type": "image/png",
            }
        )

    html_parts = [
        "<h2 style='color:#b91c1c'>🚨 QA Test FAILED — Leaka AI</h2>",
        f"<p><strong>Test:</strong> {test_name}</p>",
        f"<p><strong>Job ID:</strong> <code>{job_id}</code></p>",
    ]
    if dashboard_url:
        html_parts.append(
            f"<p><a href='{dashboard_url}' style='color:#1d4ed8'>→ View in Leaka AI dashboard</a></p>"
        )
    html_parts += [
        "<h3>Steps before failure</h3>",
        f"<pre style='background:#f6f8fa;padding:12px;overflow:auto;font-size:13px'>"
        f"{steps_summary[:8000]}</pre>",
    ]
    if attachments:
        html_parts.append(
            "<p><em>Failure-point screenshot is attached to this email.</em></p>"
        )

    return send_email(
        to=to,
        subject=f"[QA FAILURE] {test_name}",
        html="\n".join(html_parts),
        attachments=attachments or None,
        tags=[{"name": "category", "value": "qa-failure"}],
    )
