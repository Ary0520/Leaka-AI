"""
Atlassian Jira Cloud REST API v3 Integration Client for Leaka AI.

Handles:
- Domain normalization & Basic Authentication (email:api_token)
- Connection verification & health ping (GET /rest/api/3/myself)
- Project & issue type discovery (GET /rest/api/3/project)
- Standard Atlassian Document Format (ADF) JSON document builder
- Smart JQL defect deduplication to prevent Kanban board spam
- Issue creation (POST /rest/api/3/issue)
- Comment appending on duplicate regressions (POST /rest/api/3/issue/{issueKey}/comment)
- Failure screenshot upload with X-Atlassian-Token: nocheck
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Optional

import requests

logger = logging.getLogger("revguard.integrations.jira")


def normalize_jira_url(domain_or_url: str) -> str:
    """
    Ensure the Jira domain is an absolute HTTPS URL.
    Handles:
    - 'https://company.atlassian.net/' -> 'https://company.atlassian.net'
    - 'company.atlassian.net' -> 'https://company.atlassian.net'
    - 'company' -> 'https://company.atlassian.net'
    """
    d = (domain_or_url or "").strip().rstrip("/")
    if not d:
        return ""
    if d.startswith("http://") or d.startswith("https://"):
        return d
    if ".atlassian.net" in d:
        return f"https://{d}"
    return f"https://{d}.atlassian.net"


_CLOUD_ID_CACHE: dict[str, str] = {}


def get_cloud_id(domain_or_url: str) -> Optional[str]:
    """
    Resolve the Atlassian Cloud ID for a given domain from /_edge/tenant_info.
    This enables seamless support for modern Atlassian Scoped API Tokens (ATATT3xF...)
    which require routing through https://api.atlassian.com/ex/jira/{cloudId}.
    """
    site_url = normalize_jira_url(domain_or_url)
    if not site_url:
        return None
    if site_url in _CLOUD_ID_CACHE:
        return _CLOUD_ID_CACHE[site_url]
    try:
        resp = requests.get(f"{site_url}/_edge/tenant_info", timeout=10)
        if resp.status_code == 200:
            cid = resp.json().get("cloudId")
            if cid:
                _CLOUD_ID_CACHE[site_url] = str(cid)
                return str(cid)
    except Exception as e:
        logger.debug("Failed to resolve tenant_info cloudId for %s: %s", site_url, e)
    return None


def get_api_base_url(domain_or_url: str) -> str:
    """
    Returns the appropriate API base URL.
    Prefers https://api.atlassian.com/ex/jira/{cloudId} if cloudId is available
    (supporting both scoped ATATT tokens and classic tokens).
    Falls back to direct site URL https://{domain}.
    """
    cid = get_cloud_id(domain_or_url)
    if cid:
        return f"https://api.atlassian.com/ex/jira/{cid}"
    return normalize_jira_url(domain_or_url)


def get_auth_headers(email: str, api_token: str) -> dict[str, str]:
    """Build Basic Auth headers using Base64(email:api_token)."""
    cred = f"{email.strip()}:{api_token.strip()}".encode("utf-8")
    b64_cred = base64.b64encode(cred).decode("utf-8")
    return {
        "Authorization": f"Basic {b64_cred}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def verify_connection(domain: str, email: str, api_token: str) -> dict[str, Any]:
    """
    Test authentication and verify connectivity against Jira Cloud.
    Calls GET /rest/api/3/myself.
    """
    site_url = normalize_jira_url(domain)
    if not site_url:
        raise ValueError("Jira domain is required.")
    if not email or not api_token:
        raise ValueError("Jira email and API token are required.")

    api_base = get_api_base_url(domain)
    endpoint = f"{api_base}/rest/api/3/myself"
    headers = get_auth_headers(email, api_token)

    try:
        resp = requests.get(endpoint, headers=headers, timeout=15)
        # If gateway fails or domain changed, attempt fallback directly to site_url
        if resp.status_code == 401 and api_base != site_url:
            fallback_endpoint = f"{site_url}/rest/api/3/myself"
            resp_fallback = requests.get(fallback_endpoint, headers=headers, timeout=15)
            if resp_fallback.status_code == 200:
                resp = resp_fallback
                api_base = site_url

        if resp.status_code == 401:
            raise PermissionError("Invalid Jira credentials. Please check your email and API token.")
        if resp.status_code == 403:
            raise PermissionError("Access forbidden. Ensure your Atlassian user has access to this Jira instance.")
        if resp.status_code == 404:
            raise ValueError(f"Jira instance '{site_url}' not found. Please verify your domain.")

        resp.raise_for_status()
        data = resp.json()
        return {
            "ok": True,
            "display_name": data.get("displayName", "Jira User"),
            "email_address": data.get("emailAddress", email),
            "account_id": data.get("accountId"),
            "active": data.get("active", True),
            "domain": site_url,
        }
    except requests.RequestException as e:
        logger.error("Jira connection verification failed: %s", e)
        raise RuntimeError(f"Failed to connect to Jira at {site_url}: {e}") from e


def list_projects(domain: str, email: str, api_token: str) -> list[dict[str, Any]]:
    """
    Fetch accessible Jira projects.
    Calls GET /rest/api/3/project.
    """
    api_base = get_api_base_url(domain)
    endpoint = f"{api_base}/rest/api/3/project"
    headers = get_auth_headers(email, api_token)

    resp = requests.get(endpoint, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    projects = []
    for p in data:
        projects.append({
            "id": p.get("id"),
            "key": p.get("key"),
            "name": p.get("name"),
            "project_type_key": p.get("projectTypeKey"),
            "avatar_url": (p.get("avatarUrls") or {}).get("48x48"),
        })
    return projects
def list_issue_types(domain: str, email: str, api_token: str, project_key: Optional[str] = None) -> list[dict[str, Any]]:
    """
    Fetch supported issue types for a given project or globally.
    Calls GET /rest/api/3/project/{project_key} or GET /rest/api/3/issuetype.
    """
    api_base = get_api_base_url(domain)
    headers = get_auth_headers(email, api_token)

    try:
        if project_key:
            endpoint = f"{api_base}/rest/api/3/project/{project_key.strip().upper()}"
            resp = requests.get(endpoint, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                types = []
                for t in data.get("issueTypes", []):
                    if not t.get("subtask", False):
                        types.append({
                            "id": t.get("id"),
                            "name": t.get("name"),
                            "description": t.get("description"),
                            "icon_url": t.get("iconUrl"),
                        })
                if types:
                    return types

        endpoint = f"{api_base}/rest/api/3/issuetype"
        resp = requests.get(endpoint, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        raw_list = data.get("values", data) if isinstance(data, dict) else data
        types = []
        for t in raw_list:
            if not t.get("subtask", False):  # Exclude sub-tasks
                types.append({
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "description": t.get("description"),
                    "icon_url": t.get("iconUrl"),
                })
        return types
    except Exception as e:
        logger.warning("Failed to fetch issue types for Jira project %s: %s", project_key, e)
        return [{"id": "10004", "name": "Bug", "description": "A problem which impairs or prevents the functions of the product."}]


def build_adf_description(
    test_name: str,
    job_id: str,
    target_url: Optional[str] = None,
    duration_seconds: int = 0,
    total_steps: int = 0,
    rca_category: Optional[str] = None,
    error_message: Optional[str] = None,
    prompt: Optional[str] = None,
    final_result: Optional[str] = None,
    dashboard_run_url: Optional[str] = None,
    screenshot_count: int = 0,
) -> dict[str, Any]:
    """
    Generate valid Atlassian Document Format (ADF) JSON for Jira Cloud REST API v3.
    Jira Cloud strictly requires ADF structure for issue descriptions.
    """
    content: list[dict[str, Any]] = []

    # 1. Header Banner / Executive Summary
    content.append({
        "type": "heading",
        "attrs": {"level": 2},
        "content": [{"type": "text", "text": "🚨 Leaka AI — Automated QA Defect Report"}],
    })

    # 2. RCA Callout Panel (if Root Cause Analysis was performed)
    if rca_category and rca_category != "UNKNOWN":
        panel_type = "error" if rca_category == "PRODUCT_BUG" else "warning"
        content.append({
            "type": "panel",
            "attrs": {"panelType": panel_type},
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Root Cause Analysis (RCA): ", "marks": [{"type": "strong"}]},
                        {"type": "text", "text": f"{rca_category} — Confidence Verified by Leaka Engine"},
                    ],
                }
            ],
        })

    # 3. Bullet List of Execution Details
    bullet_items = [
        ("Test Name", test_name),
        ("Job ID", job_id),
        ("Target URL", target_url or "N/A"),
        ("Execution Duration", f"{duration_seconds}s over {total_steps} browser steps"),
    ]
    if screenshot_count > 0:
        bullet_items.append(("Visual Proof", f"{screenshot_count} screenshot(s) captured & attached to this issue"))

    list_nodes = []
    for label, val in bullet_items:
        list_nodes.append({
            "type": "listItem",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": f"{label}: ", "marks": [{"type": "strong"}]},
                        {"type": "text", "text": str(val)},
                    ],
                }
            ],
        })

    content.append({
        "type": "bulletList",
        "content": list_nodes,
    })

    # 4. Error Message / Abort Reason
    if error_message:
        content.append({
            "type": "heading",
            "attrs": {"level": 3},
            "content": [{"type": "text", "text": "Error Summary"}],
        })
        content.append({
            "type": "codeBlock",
            "attrs": {"language": "text"},
            "content": [{"type": "text", "text": error_message[:2000]}],
        })

    # 5. Executed Prompt
    if prompt:
        content.append({
            "type": "heading",
            "attrs": {"level": 3},
            "content": [{"type": "text", "text": "Executed User Scenario"}],
        })
        content.append({
            "type": "codeBlock",
            "attrs": {"language": "text"},
            "content": [{"type": "text", "text": prompt[:1500]}],
        })

    # 6. Deep Link to Leaka AI Dashboard
    if dashboard_run_url:
        content.append({
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "🔗 Replay Full Autonomous Session: ", "marks": [{"type": "strong"}]},
                {
                    "type": "text",
                    "text": "Open in Leaka AI Dashboard ↗",
                    "marks": [{"type": "link", "attrs": {"href": dashboard_run_url}}],
                },
            ],
        })

    return {
        "version": 1,
        "type": "doc",
        "content": content,
    }


def search_open_issue(
    domain: str,
    email: str,
    api_token: str,
    project_key: str,
    label_identifier: str,
) -> Optional[dict[str, Any]]:
    """
    Search for an existing non-resolved Jira issue using JQL to prevent duplicate ticket spam.
    Query: project = '{project_key}' AND labels = '{label_identifier}' AND statusCategory != Done
    """
    site_url = normalize_jira_url(domain)
    api_base = get_api_base_url(domain)
    endpoint = f"{api_base}/rest/api/3/search"
    headers = get_auth_headers(email, api_token)

    clean_proj = project_key.strip().replace("'", "")
    clean_label = label_identifier.strip().replace("'", "")
    jql = f"project = '{clean_proj}' AND labels = '{clean_label}' AND statusCategory != Done"

    params = {
        "jql": jql,
        "maxResults": 1,
        "fields": "id,key,summary,status",
    }

    try:
        resp = requests.get(endpoint, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning("Jira JQL search returned status %s: %s", resp.status_code, resp.text)
            return None

        data = resp.json()
        issues = data.get("issues", [])
        if issues:
            iss = issues[0]
            return {
                "id": iss.get("id"),
                "key": iss.get("key"),
                "summary": iss.get("fields", {}).get("summary"),
                "url": f"{site_url}/browse/{iss.get('key')}",
            }
        return None
    except Exception as e:
        logger.warning("Failed to search Jira for duplicate issue: %s", e)
        return None


def add_comment(
    domain: str,
    email: str,
    api_token: str,
    issue_key: str,
    comment_text: str,
    dashboard_run_url: Optional[str] = None,
) -> bool:
    """
    Append an execution trace comment to an existing Jira issue when repeated test runs fail.
    Calls POST /rest/api/3/issue/{issueKey}/comment.
    """
    api_base = get_api_base_url(domain)
    endpoint = f"{api_base}/rest/api/3/issue/{issue_key}/comment"
    headers = get_auth_headers(email, api_token)

    content_nodes: list[dict[str, Any]] = [
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "🔄 Regression Recurrence Detected by Leaka AI:", "marks": [{"type": "strong"}]},
            ],
        },
        {
            "type": "codeBlock",
            "attrs": {"language": "text"},
            "content": [{"type": "text", "text": comment_text[:2000]}],
        },
    ]

    if dashboard_run_url:
        content_nodes.append({
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "View latest failed execution: "},
                {
                    "type": "text",
                    "text": "Leaka Run Details ↗",
                    "marks": [{"type": "link", "attrs": {"href": dashboard_run_url}}],
                },
            ],
        })

    payload = {
        "body": {
            "version": 1,
            "type": "doc",
            "content": content_nodes,
        }
    }

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=15)
        return resp.status_code in (200, 201)
    except Exception as e:
        logger.error("Failed to append comment to Jira issue %s: %s", issue_key, e)
        return False


def create_issue(
    domain: str,
    email: str,
    api_token: str,
    project_key: str,
    summary: str,
    description_adf: dict[str, Any],
    issue_type: str = "Bug",
    priority: str = "High",
    labels: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Create a new Jira Cloud defect via POST /rest/api/3/issue.
    Returns: {"success": bool, "id": str, "key": str, "url": str, "error": str}
    """
    site_url = normalize_jira_url(domain)
    api_base = get_api_base_url(domain)
    endpoint = f"{api_base}/rest/api/3/issue"
    headers = get_auth_headers(email, api_token)

    clean_proj = project_key.strip().upper()
    target_type = (issue_type or "Bug").strip()
    resolved_issue_type = target_type
    try:
        proj_types = list_issue_types(domain, email, api_token, project_key=clean_proj)
        type_names = [t.get("name") for t in proj_types if t.get("name")]
        if type_names:
            matched = next((tn for tn in type_names if tn.lower() == target_type.lower()), None)
            if matched:
                resolved_issue_type = matched
            else:
                fallback = next((tn for tn in type_names if tn in ("Bug", "Task", "Story", "Incident")), type_names[0])
                resolved_issue_type = fallback
                logger.info("Project %s issue types %s do not include '%s'; using '%s'", clean_proj, type_names, target_type, fallback)
    except Exception as e:
        logger.debug("Failed to verify issue types for project %s: %s", clean_proj, e)

    issue_labels = ["leaka-ai", "automated-qa"]
    if labels:
        for lbl in labels:
            sanitized = lbl.strip().replace(" ", "-")
            if sanitized and sanitized not in issue_labels:
                issue_labels.append(sanitized)

    payload = {
        "fields": {
            "project": {"key": clean_proj},
            "summary": summary[:255],
            "description": description_adf,
            "issuetype": {"name": resolved_issue_type},
            "labels": issue_labels,
        }
    }

    # Set priority if standard Jira Cloud priority exists
    if priority in ("Highest", "High", "Medium", "Low", "Lowest"):
        payload["fields"]["priority"] = {"name": priority}

    resp = requests.post(endpoint, headers=headers, json=payload, timeout=25)
    if resp.status_code not in (200, 201):
        err_msg = resp.text
        try:
            err_json = resp.json()
            err_msg = json.dumps(err_json.get("errors") or err_json.get("errorMessages") or err_json)
        except Exception:
            pass
        logger.error("Jira issue creation failed (HTTP %s): %s", resp.status_code, err_msg)
        return {"success": False, "error": err_msg}

    data = resp.json()
    issue_id = data.get("id")
    issue_key = data.get("key")
    issue_url = f"{site_url}/browse/{issue_key}"

    return {
        "success": True,
        "id": issue_id,
        "key": issue_key,
        "url": issue_url,
    }


def upload_attachment(
    domain: str,
    email: str,
    api_token: str,
    issue_key: str,
    file_path: str,
) -> bool:
    """
    Upload a screenshot file attachment to a Jira issue.
    Calls POST /rest/api/3/issue/{issueKey}/attachments.
    CRITICAL: Jira requires 'X-Atlassian-Token: nocheck' header to bypass XSRF checks.
    """
    if not file_path or not os.path.isfile(file_path):
        logger.warning("Jira attachment file does not exist: %s", file_path)
        return False

    api_base = get_api_base_url(domain)
    endpoint = f"{api_base}/rest/api/3/issue/{issue_key}/attachments"

    # Basic auth without Content-Type (requests sets multipart boundary automatically)
    cred = f"{email.strip()}:{api_token.strip()}".encode("utf-8")
    b64_cred = base64.b64encode(cred).decode("utf-8")
    headers = {
        "Authorization": f"Basic {b64_cred}",
        "X-Atlassian-Token": "nocheck",  # Mandatory Jira requirement
        "Accept": "application/json",
    }

    filename = os.path.basename(file_path)
    try:
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, "image/png")}
            resp = requests.post(endpoint, headers=headers, files=files, timeout=30)
            if resp.status_code in (200, 201):
                logger.info("Successfully uploaded failure screenshot %s to Jira %s", filename, issue_key)
                return True
            else:
                logger.warning("Failed to upload screenshot to Jira %s (HTTP %s): %s", issue_key, resp.status_code, resp.text)
                return False
    except Exception as e:
        logger.error("Exception uploading attachment to Jira %s: %s", issue_key, e)
        return False


def file_or_update_defect(
    domain: str,
    email: str,
    api_token: str,
    project_key: str,
    test_name: str,
    job_id: str,
    test_identifier: str,
    target_url: Optional[str] = None,
    duration_seconds: int = 0,
    total_steps: int = 0,
    rca_category: Optional[str] = None,
    error_message: Optional[str] = None,
    prompt: Optional[str] = None,
    final_result: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    dashboard_run_url: Optional[str] = None,
    issue_type: str = "Bug",
) -> dict[str, Any]:
    """
    High-level orchestrator:
    1. Checks JQL deduplication for an open defect tagged 'leaka-test-{test_identifier}'.
    2. If found: appends a run trace comment with timestamp and replay link.
    3. If none found: creates a fresh Jira issue with full ADF document.
    4. Uploads failure screenshot proof directly to the issue.
    5. Returns dict with success, key, url, is_duplicate.
    """
    label_id = f"leaka-test-{test_identifier}"

    # 1. Smart Deduplication Check
    existing_issue = search_open_issue(
        domain=domain,
        email=email,
        api_token=api_token,
        project_key=project_key,
        label_identifier=label_id,
    )

    if existing_issue:
        issue_key = existing_issue["key"]
        comment_summary = (
            f"Run ID: {job_id}\n"
            f"Duration: {duration_seconds}s over {total_steps} steps\n"
            f"RCA Category: {rca_category or 'UNKNOWN'}\n"
            f"Error: {error_message or 'Failure detected during execution'}"
        )
        add_comment(
            domain=domain,
            email=email,
            api_token=api_token,
            issue_key=issue_key,
            comment_text=comment_summary,
            dashboard_run_url=dashboard_run_url,
        )
        if screenshot_path:
            upload_attachment(domain, email, api_token, issue_key, screenshot_path)

        return {
            "success": True,
            "id": existing_issue.get("id"),
            "key": issue_key,
            "url": existing_issue.get("url"),
            "is_duplicate": True,
        }

    # 2. Fresh Issue Creation
    summary = f"[QA BUG] {test_name} — {job_id[:8]}"
    description_adf = build_adf_description(
        test_name=test_name,
        job_id=job_id,
        target_url=target_url,
        duration_seconds=duration_seconds,
        total_steps=total_steps,
        rca_category=rca_category,
        error_message=error_message,
        prompt=prompt,
        final_result=final_result,
        dashboard_run_url=dashboard_run_url,
        screenshot_count=1 if screenshot_path else 0,
    )

    res = create_issue(
        domain=domain,
        email=email,
        api_token=api_token,
        project_key=project_key,
        summary=summary,
        description_adf=description_adf,
        issue_type=issue_type,
        labels=[label_id],
    )

    if res.get("success") and res.get("key"):
        issue_key = res["key"]
        if screenshot_path:
            upload_attachment(domain, email, api_token, issue_key, screenshot_path)
        res["is_duplicate"] = False

    return res
