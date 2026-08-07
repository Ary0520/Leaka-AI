import json
from typing import Any, Optional

import requests

from ..config import settings

LINEAR_ENDPOINT = "https://api.linear.app/graphql"


def _headers() -> dict[str, str]:
    if not settings.LINEAR_API_KEY:
        raise RuntimeError("LINEAR_API_KEY is not configured.")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.LINEAR_API_KEY}",
    }


def create_issue(
    title: str,
    description_md: str,
    team_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Create a Linear issue via the GraphQL API.

    Returns a dict with: success (bool), issue_id, identifier, title
    """
    tid = team_id or settings.LINEAR_TEAM_ID
    if not tid:
        raise RuntimeError(
            "LINEAR_TEAM_ID not set. Pass team_id or configure env var."
        )

    mutation = """
    mutation IssueCreate($input: IssueCreateInput!) {
        issueCreate(input: $input) {
            success
            issue { id title identifier url }
        }
    }
    """
    variables = {
        "input": {
            "title": title[:500],
            "description": description_md,
            "teamId": tid,
        }
    }

    resp = requests.post(
        LINEAR_ENDPOINT,
        headers=_headers(),
        data=json.dumps({"query": mutation, "variables": variables}),
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data", {}).get("issueCreate", {})
    issue = data.get("issue") or {}
    return {
        "success": bool(data.get("success")),
        "issue_id": issue.get("id"),
        "identifier": issue.get("identifier"),
        "title": issue.get("title"),
        "url": issue.get("url"),
    }


def list_teams() -> list[dict[str, Any]]:
    """Helper to list Linear teams so user can pick a TEAM_ID."""
    query = """
    query Teams { teams { nodes { id name } } }
    """
    resp = requests.post(
        LINEAR_ENDPOINT,
        headers=_headers(),
        data=json.dumps({"query": query}),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("data", {}).get("teams", {}).get("nodes", []) or []
