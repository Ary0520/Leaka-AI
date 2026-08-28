"""
Explore worker — Application Intelligence.

Runs a browser-use Agent in "explore" mode against an application to
autonomously discover its pages, forms, and user flows, then persists a
structured application map.

This module is DELIBERATELY separate from worker.py. It reuses the same proven
patterns (Windows event-loop policy, fresh ProactorEventLoop per run, live-step
callback) but writes ONLY to the Application / ExploreRun / AppMapNode tables.
It never imports or mutates the test-run execution path, so it cannot affect
existing QA test runs.
"""

import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("revguard.explore")

# ── CRITICAL WINDOWS FIX (same as worker.py) ────────────────────────────────
# ProactorEventLoop is required on Windows to spawn Chromium subprocesses.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ────────────────────────────────────────────────────────────────────────────

from .celery_app import celery_app
from .database import SessionLocal
from .llm import get_llm
from .models import (
    Application,
    AppMapNode,
    ExploreRun,
    ExploreRunStatus,
)


# ---------------------------------------------------------------------------
# Structured output schema — what the exploration agent must return.
# browser-use 0.13.7 supports Agent(output_model_schema=...) and exposes
# history.structured_output. This turns the map into validated data, not text.
# ---------------------------------------------------------------------------
class DiscoveredNode(BaseModel):
    node_type: str = Field(description="One of: page, form, flow")
    label: str = Field(description="Short human name, e.g. 'Checkout' or 'Login form'")
    url: Optional[str] = Field(default=None, description="URL where this lives, if known")
    description: Optional[str] = Field(default=None, description="What it does / contains")
    suggested_prompt: Optional[str] = Field(
        default=None,
        description="A natural-language QA test prompt that would exercise this node",
    )


class ApplicationMap(BaseModel):
    nodes: list[DiscoveredNode] = Field(default_factory=list)
    summary: Optional[str] = Field(
        default=None, description="One-paragraph summary of what the application is"
    )


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------
def _update_explore_status(
    job_id: str,
    *,
    status: Optional[ExploreRunStatus] = None,
    patch: Optional[dict[str, Any]] = None,
) -> None:
    db = SessionLocal()
    try:
        run = db.query(ExploreRun).filter(ExploreRun.job_id == job_id).first()
        if not run:
            return
        if status is not None:
            run.status = status
        if patch:
            for key, value in patch.items():
                if hasattr(run, key):
                    setattr(run, key, value)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# The explore task
# ---------------------------------------------------------------------------
@celery_app.task(
    max_retries=1,
    autoretry_for=(),  # do NOT auto-retry exploration; it's expensive
    name="app.explore_worker.explore_application",
)
def explore_application(
    job_id: str,
    application_id: int,
    owner_id: Optional[str],
    base_url: str,
    login_hint: Optional[str] = None,
    max_steps: int = 40,
) -> dict[str, Any]:
    """
    Explore an application and persist its map.

    Lifecycle:
      1. ExploreRun → RUNNING
      2. Build LLM, run an exploration Agent with structured output
      3. Persist discovered nodes to AppMapNode
      4. ExploreRun → COMPLETED / FAILED
    """
    import traceback

    _update_explore_status(
        job_id,
        status=ExploreRunStatus.RUNNING,
        patch={"started_at": datetime.utcnow()},
    )

    try:
        llm = get_llm()
    except Exception as exc:
        _update_explore_status(
            job_id,
            status=ExploreRunStatus.FAILED,
            patch={
                "error_message": f"LLM init failed: {exc}",
                "completed_at": datetime.utcnow(),
            },
        )
        raise RuntimeError(f"LLM init failed: {exc}") from exc

    # ── Build the exploration task prompt ──────────────────────────────────
    task_parts = [
        f"You are mapping the web application at: {base_url}",
        "",
        "GOAL: Systematically explore this application and build a map of its "
        "important pages, forms, and user flows. Navigate like a curious new "
        "user. Click into main navigation links, open key pages, and identify "
        "interactive forms (login, signup, search, checkout, contact, etc.).",
        "",
        "RULES:",
        "1. Do NOT submit forms with real data, do NOT complete purchases, and "
        "do NOT perform destructive actions (delete, cancel, pay). Only OBSERVE.",
        "2. Prefer breadth over depth — visit many distinct areas rather than "
        "going very deep into one.",
        "3. For each important thing you find, record it as a node: a page, a "
        "form, or a multi-step flow (like 'checkout' or 'onboarding').",
        "4. For each node, draft a short natural-language QA test prompt that "
        "would verify it works (e.g. 'Log in with valid credentials and verify "
        "the dashboard loads').",
        "5. When finished, call done() and return the structured application map.",
    ]
    if login_hint:
        task_parts += [
            "",
            f"LOGIN HINT (use only to access authenticated areas): {login_hint}",
        ]
    task_text = "\n".join(task_parts)

    async def _run_explore():
        from browser_use import Agent
        from browser_use.browser.session import BrowserSession

        browser_session = BrowserSession(headless=True)
        live_step_buffer: list[dict] = []
        visited: list[str] = []

        def _on_step(browser_state_summary, agent_output, step_index: int):
            try:
                entry: dict = {"step": step_index, "action": {}}
                if agent_output and hasattr(agent_output, "action"):
                    actions = agent_output.action
                    if actions:
                        action_dict = actions[0].model_dump(exclude_none=True, mode="json")
                        meta = {"result", "error", "interacted_element", "step"}
                        keys = [k for k in action_dict if k not in meta]
                        if keys:
                            entry["action"] = {keys[0]: action_dict.get(keys[0], {})}
                if browser_state_summary and hasattr(browser_state_summary, "url"):
                    entry["url"] = browser_state_summary.url
                    if browser_state_summary.url and browser_state_summary.url not in visited:
                        visited.append(browser_state_summary.url)
                live_step_buffer.append(entry)

                db = SessionLocal()
                try:
                    run = db.query(ExploreRun).filter(ExploreRun.job_id == job_id).first()
                    if run:
                        run.live_steps = json.dumps(live_step_buffer, default=str)
                        run.visited_urls = json.dumps(visited, ensure_ascii=False)
                        db.commit()
                except Exception:
                    pass
                finally:
                    db.close()
            except Exception:
                pass  # never let the callback break the agent

        agent = Agent(
            task=task_text,
            llm=llm,
            browser_session=browser_session,
            use_vision=True,
            use_thinking=False,
            max_failures=5,
            max_actions_per_step=5,
            step_timeout=60,
            llm_timeout=60,
            message_compaction=False,
            output_model_schema=ApplicationMap,
            register_new_step_callback=_on_step,
        )
        history = await agent.run(max_steps=max_steps)

        # Extract structured output
        app_map: Optional[ApplicationMap] = None
        try:
            structured = history.structured_output
            if isinstance(structured, ApplicationMap):
                app_map = structured
        except Exception:
            app_map = None

        try:
            await browser_session.stop()
        except Exception:
            pass

        return history, app_map, visited

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            history, app_map, visited = loop.run_until_complete(_run_explore())
        finally:
            try:
                loop.run_until_complete(asyncio.sleep(0.1))
            except Exception:
                pass
            loop.close()
            asyncio.set_event_loop(None)
    except Exception as exc:
        tb = traceback.format_exc()
        _update_explore_status(
            job_id,
            status=ExploreRunStatus.FAILED,
            patch={
                "error_message": f"Explore runtime error: {exc}\n{tb}"[:4000],
                "completed_at": datetime.utcnow(),
            },
        )
        raise

    # ── Persist discovered nodes ────────────────────────────────────────────
    nodes = list(app_map.nodes) if app_map else []
    summary = app_map.summary if app_map else None

    db = SessionLocal()
    try:
        run_row = db.query(ExploreRun).filter(ExploreRun.job_id == job_id).first()
        run_pk = run_row.id if run_row else None
        for n in nodes[:200]:  # hard cap
            node_type = (n.node_type or "page").strip().lower()
            if node_type not in ("page", "form", "flow"):
                node_type = "page"
            db.add(AppMapNode(
                owner_id=owner_id,
                application_id=application_id,
                explore_run_id=run_pk,
                node_type=node_type,
                label=(n.label or "Untitled")[:500],
                url=(n.url or None),
                description=(n.description or None),
                suggested_prompt=(n.suggested_prompt or None),
            ))
        db.commit()
    finally:
        db.close()

    _update_explore_status(
        job_id,
        status=ExploreRunStatus.COMPLETED,
        patch={
            "nodes_found": len(nodes),
            "result_summary": summary or f"Discovered {len(nodes)} node(s).",
            "visited_urls": json.dumps(visited, ensure_ascii=False),
            "completed_at": datetime.utcnow(),
        },
    )

    return {
        "job_id": job_id,
        "status": ExploreRunStatus.COMPLETED.value,
        "nodes_found": len(nodes),
    }
