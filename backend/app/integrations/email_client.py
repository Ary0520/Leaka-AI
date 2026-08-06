import os
from typing import Any, Iterable, Optional

from .config import settings


def _ensure_resend():
    try:
        import resend  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "resend package not installed. Run: pip install resend"
        ) from e

    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured.")
    resend.api_key = settings.RESEND_API_KEY
    return resend


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
    Thin wrapper over resend.Emails.send with sane defaults.

    attachments: [ {"filename": str, "content": list[int] (bytes)}, ... ]
    """
    resend = _ensure_resend()
    params: dict[str, Any] = {
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
        params["attachments"] = attachments
    if tags:
        params["tags"] = tags
    return resend.Emails.send(params)


def send_test_failure_alert(
    *,
    test_name: str,
    job_id: str,
    steps_summary: str,
    screenshot_path: Optional[str] = None,
    dashboard_url: Optional[str] = None,
) -> dict[str, Any]:
    """Preset: send a failure alert to EMAIL_ALERT_TO."""
    to = settings.EMAIL_ALERT_TO
    if not to:
        raise RuntimeError(
            "EMAIL_ALERT_TO not configured. Set env var or pass `to=` explicitly."
        )

    attachments: list[dict[str, Any]] = []
    if screenshot_path and os.path.isfile(screenshot_path):
        with open(screenshot_path, "rb") as f:
            attachments.append(
                {
                    "filename": os.path.basename(screenshot_path),
                    "content": list(f.read()),
                }
            )

    html_parts = [
        "<h2 style='color:#b91c1c'>🚨 QA Test FAILED</h2>",
        f"<p><strong>Test:</strong> {test_name}</p>",
        f"<p><strong>Job ID:</strong> <code>{job_id}</code></p>",
    ]
    if dashboard_url:
        html_parts.append(
            f"<p><a href='{dashboard_url}'>View in dashboard</a></p>"
        )
    html_parts.append("<h3>Steps before failure:</h3>")
    html_parts.append(f"<pre style='background:#f6f8fa;padding:12px;overflow:auto'>{steps_summary}</pre>")
    if attachments:
        html_parts.append("<p>Screenshot attached to this email.</p>")

    return send_email(
        to=to,
        subject=f"[QA FAILURE] {test_name}",
        html="\n".join(html_parts),
        attachments=attachments or None,
        tags=[{"name": "category", "value": "qa-failure"}],
    )
