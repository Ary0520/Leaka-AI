"""
Celery worker: runs a browser-use Agent for a given QA test.

WINDOWS NOTE: Python 3.13 on Windows uses SelectorEventLoop by default,
which cannot spawn subprocesses (Playwright/Chromium). We must set
WindowsProactorEventLoopPolicy before any asyncio.run() call.
"""

import asyncio
import base64
import json
import logging
import os
import platform
import shutil
import sys
import uuid
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("revguard.worker")

# ── CRITICAL WINDOWS FIX ──────────────────────────────────────────────────────
# On Windows, asyncio.run() defaults to SelectorEventLoop which raises
# NotImplementedError when trying to spawn subprocesses (Playwright launching
# Chromium). ProactorEventLoop supports subprocesses on Windows.
# This must be set at module import time, before any asyncio.run() call.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ─────────────────────────────────────────────────────────────────────────────

from .celery_app import celery_app
from .config import settings
from .database import SessionLocal
from .llm import get_llm
from .models import (
    LinearIssue,
    TestRun,
    TestRunStatus,
    TestScreenshot,
)

# ---------------------------------------------------------------------------
# Patch browser-use SchemaOptimizer to strip 'minimum'/'maximum' from schemas.
# Anthropic, Azure Bedrock, and other providers reject JSON schemas that
# contain 'minimum'/'maximum' on integer fields (OpenAI extension, not
# standard JSON Schema Draft 7). browser-use keeps these for OpenAI strict
# mode but they cause 400 errors on every other provider.
# ---------------------------------------------------------------------------
# SchemaOptimizer patch no longer needed — minimum/maximum removed directly
# from the installed browser_use/llm/schema.py to fix 400 errors on
# Anthropic/Azure/Bedrock providers.

# Ensure all tables exist in the worker process.
# The FastAPI app calls init_db() on startup, but the Celery worker
# is a separate process and must create tables itself — otherwise
# any table added after the worker was first started (e.g. UserSettings)
# will be missing and queries will raise OperationalError, silently
# swallowed by the integration try/except blocks.
from .database import init_db as _init_db
_init_db()


SCREENSHOT_ROOT = os.path.abspath(settings.SCREENSHOT_DIR)
os.makedirs(SCREENSHOT_ROOT, exist_ok=True)


# ---------------------------------------------------------------------------
# QA Incident context extractor
# ---------------------------------------------------------------------------

def _build_incident_context(
    *,
    name: str,
    job_id: str,
    prompt: str,
    target_url: Optional[str],
    success_criteria: Optional[str],
    steps_log_json: str,
    final_result_text: Any,
    error_message: Optional[str],
    total_steps_count: int,
    duration: int,
    screenshots_persisted: list,
    final_failure_shot_rel: Optional[str],
    completed_at: "datetime",
    dashboard_base_url: Optional[str],
    linear_issue_url: Optional[str],
    linear_identifier: Optional[str],
) -> dict[str, Any]:
    """
    Extracts all real, available execution fields into a flat dict
    ready for slack_client.send_qa_incident().
    Nothing is fabricated — if a field isn't available it is None.
    """

    # ── Parse steps log ───────────────────────────────────────────────────────
    actions: list[dict] = []
    try:
        raw = json.loads(steps_log_json) if isinstance(steps_log_json, str) else []
        if isinstance(raw, list):
            actions = raw
    except Exception:
        pass

    # ── Find first step that has an error ─────────────────────────────────────
    failed_step_index: Optional[int] = None
    failed_action_label: Optional[str] = None
    preceding_action_label: Optional[str] = None

    for i, entry in enumerate(actions):
        if entry.get("error"):
            # 1-based for human display
            failed_step_index = entry.get("step", i) + 1
            action_dict = entry.get("action", {})
            action_name = next(iter(action_dict), None) if action_dict else None
            if action_name:
                params = action_dict[action_name]
                if isinstance(params, dict):
                    param_str = ", ".join(
                        f"{k}={str(v)[:60]}" for k, v in list(params.items())[:2]
                    )
                    failed_action_label = f"{action_name}({param_str})" if param_str else action_name
                else:
                    failed_action_label = action_name
            # Preceding action
            if i > 0:
                prev = actions[i - 1]
                prev_action_dict = prev.get("action", {})
                prev_name = next(iter(prev_action_dict), None) if prev_action_dict else None
                if prev_name:
                    preceding_action_label = prev_name
            break

    # ── Reproduction steps from actions (up to 10, readable labels) ──────────
    repro_steps: list[str] = []
    for entry in actions[:15]:
        action_dict = entry.get("action", {})
        action_name = next(iter(action_dict), None) if action_dict else None
        if not action_name or action_name in ("unknown", "done"):
            continue
        params = action_dict.get(action_name, {})
        if isinstance(params, dict):
            # navigate → "Navigate to https://..."
            if action_name == "navigate" and params.get("url"):
                repro_steps.append(f"Navigate to {params['url'][:80]}")
            elif action_name in ("click", "type", "fill") and params.get("selector"):
                repro_steps.append(f"{action_name.capitalize()} `{params['selector'][:60]}`")
            elif action_name == "type" and params.get("text"):
                repro_steps.append(f"Type: {params['text'][:60]}")
            elif params:
                first_val = str(list(params.values())[0])[:60]
                repro_steps.append(f"{action_name}: {first_val}")
            else:
                repro_steps.append(action_name)
        else:
            repro_steps.append(str(action_name)[:60])

        if len(repro_steps) >= 10:
            break

    # ── Screenshot URL ─────────────────────────────────────────────────────────
    # Find the failure-point screenshot; prefer the explicit final_failure_shot_rel
    screenshot_server_url: Optional[str] = None
    if dashboard_base_url:
        # Find the screenshot DB id from persisted list — we only have paths here,
        # so we build a URL using the run detail page which shows screenshots inline
        if final_failure_shot_rel or screenshots_persisted:
            # Point to the run's evidence section; the exact screenshot is one click away
            screenshot_server_url = None  # set after DB write — handled in caller

    # ── Dashboard deep link ───────────────────────────────────────────────────
    dashboard_run_url: Optional[str] = None
    if dashboard_base_url:
        base = dashboard_base_url.rstrip("/")
        dashboard_run_url = f"{base}/runs/{job_id}"

    return {
        "test_name": name,
        "job_id": job_id,
        "timestamp_iso": completed_at.isoformat() if completed_at else None,
        "target_url": target_url,
        "expected_result": success_criteria or None,
        "actual_result": str(final_result_text)[:500] if final_result_text else None,
        "failed_step_index": failed_step_index,
        "total_steps": total_steps_count,
        "failed_action_label": failed_action_label,
        "preceding_action_label": preceding_action_label,
        "duration_seconds": duration,
        "repro_steps": repro_steps if repro_steps else None,
        "dashboard_run_url": dashboard_run_url,
        "error_message": error_message,
        "linear_issue_url": linear_issue_url,
        "linear_identifier": linear_identifier,
    }


def _job_screenshot_dir(job_id: str) -> str:
    path = os.path.join(SCREENSHOT_ROOT, job_id)
    os.makedirs(path, exist_ok=True)
    return path


def _update_db_status(
    job_id: str,
    *,
    status: Optional[TestRunStatus] = None,
    patch: Optional[dict[str, Any]] = None,
):
    """Update a TestRun row by job_id in a standalone session."""
    db = SessionLocal()
    try:
        run = db.query(TestRun).filter(TestRun.job_id == job_id).first()
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


def _copy_screenshot(src_path: Optional[str], dest_dir: str, name: str) -> Optional[str]:
    """Copy a browser-use screenshot file into our managed dir. Returns relative path."""
    if not src_path or not os.path.isfile(src_path):
        return None
    ext = os.path.splitext(src_path)[1] or ".png"
    dest_path = os.path.join(dest_dir, f"{name}{ext}")
    try:
        shutil.copyfile(src_path, dest_path)
    except Exception:
        return None
    return os.path.relpath(dest_path, start=os.path.dirname(SCREENSHOT_ROOT))


def _save_b64_screenshot(b64_data: str, dest_dir: str, name: str) -> Optional[str]:
    """Decode a base64 PNG string and save it to dest_dir. Returns relative path."""
    dest_path = os.path.join(dest_dir, f"{name}.png")
    try:
        raw = base64.b64decode(b64_data)
        with open(dest_path, "wb") as f:
            f.write(raw)
        return os.path.relpath(dest_path, start=os.path.dirname(SCREENSHOT_ROOT))
    except Exception:
        return None


@celery_app.task(
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    name="app.worker.run_browser_test",
)
def run_browser_test(
    job_id: str,
    name: str,
    prompt: str,
    target_url: Optional[str] = None,
    success_criteria: Optional[str] = None,
    use_vision: bool = True,
    max_steps: int = 100,
    test_case_id: Optional[int] = None,
) -> dict[str, Any]:
    """
    Run a browser-use Agent against a natural-language QA prompt.

    Lifecycle:
      1. Update TestRun → RUNNING, set started_at
      2. Build the LLM (honours LLM_PROVIDER env)
      3. Run Agent async via asyncio.run()
      4. Persist screenshots, result, DOM, steps
      5. Update TestRun → COMPLETED / FAILED
      6. Auto-trigger integrations (Linear, Resend, Slack) if configured
    """
    import traceback

    _update_db_status(
        job_id,
        status=TestRunStatus.RUNNING,
        patch={"started_at": datetime.utcnow()},
    )

    try:
        llm = get_llm()
    except Exception as exc:
        _update_db_status(
            job_id,
            status=TestRunStatus.FAILED,
            patch={
                "error_message": f"LLM init failed: {exc}",
                "completed_at": datetime.utcnow(),
                "is_successful": False,
            },
        )
        raise RuntimeError(f"LLM init failed: {exc}") from exc

    # Build the full task string
    task_parts = []
    if target_url:
        task_parts.append(f"Target URL: {target_url}")
    task_parts.append(f"Task: {prompt}")
    if success_criteria:
        task_parts.append(f"Success criteria to validate after execution: {success_criteria}")
    task_text = "\n".join(task_parts)

    async def _run_agent():
        from browser_use import Agent
        from browser_use.browser.session import BrowserSession

        browser_session = BrowserSession(headless=True)

        # ── Live step writer ──────────────────────────────────────────────────
        # Fired by browser-use after EVERY agent step.
        # Writes the step immediately to DB so the frontend can show it live
        # while the agent is still running (via the 3-second polling loop).
        live_step_buffer: list[dict] = []

        def _on_step(browser_state_summary, agent_output, step_index: int):
            """Sync callback — extract action + result and persist immediately."""
            try:
                step_entry: dict = {"step": step_index, "action": {}, "result": None}

                # Extract the action name + params from agent_output
                if agent_output and hasattr(agent_output, "action"):
                    actions = agent_output.action
                    if actions:
                        action = actions[0]  # first action of this step
                        action_dict = action.model_dump(exclude_none=True, mode="json")
                        meta_keys = {"result", "error", "interacted_element", "step"}
                        action_keys = [k for k in action_dict if k not in meta_keys]
                        if action_keys:
                            name = action_keys[0]
                            step_entry["action"] = {name: action_dict.get(name, {})}

                # Extract URL from browser state
                if browser_state_summary and hasattr(browser_state_summary, "url"):
                    step_entry["url"] = browser_state_summary.url

                live_step_buffer.append(step_entry)

                # Write to DB
                db = SessionLocal()
                try:
                    run = db.query(TestRun).filter(TestRun.job_id == job_id).first()
                    if run:
                        run.live_steps = json.dumps(live_step_buffer, default=str)
                        run.total_steps = step_index + 1
                        db.commit()
                except Exception:
                    pass
                finally:
                    db.close()
            except Exception:
                pass  # never let callback errors break the agent

        agent = Agent(
            task=task_text,
            llm=llm,
            browser_session=browser_session,
            use_vision=use_vision,
            max_failures=5,
            max_actions_per_step=5,
            step_timeout=60,
            llm_timeout=60,
            message_compaction=False,   # disable cross-run memory contamination
            register_new_step_callback=_on_step,
        )
        history = await agent.run(max_steps=max_steps)

        # --- Capture final-state screenshot via actor Page API ---
        # browser_use 0.13.7: BrowserSession.get_current_page() returns
        # an actor Page whose .screenshot() returns a base64 PNG string.
        dom_html: Optional[str] = None
        final_failure_shot_rel: Optional[str] = None

        try:
            page = await browser_session.get_current_page()
            if page is not None:
                # Attempt DOM capture via JS evaluate
                try:
                    dom_html = await page.evaluate("() => document.documentElement.outerHTML")
                except Exception:
                    dom_html = None

                # Capture full-page failure screenshot if run looks failed
                try:
                    is_done = history.is_done()
                    is_failure_like = not is_done or history.has_errors()
                except Exception:
                    is_failure_like = True

                if is_failure_like:
                    try:
                        dest_dir = _job_screenshot_dir(job_id)
                        shot_name = f"final_failure_{uuid.uuid4().hex[:8]}"
                        # screenshot() returns base64 PNG string
                        b64 = await page.screenshot(format="png")
                        final_failure_shot_rel = _save_b64_screenshot(b64, dest_dir, shot_name)
                    except Exception:
                        final_failure_shot_rel = None
        except Exception:
            pass

        # Gracefully close the browser session
        try:
            await browser_session.stop()
        except Exception:
            pass

        return history, dom_html, final_failure_shot_rel

    try:
        # Use a fresh ProactorEventLoop per run instead of asyncio.run().
        # asyncio.run() closes the loop immediately after the coroutine
        # finishes, which causes "Event loop is closed" errors when
        # browser-use's cleanup callbacks (httpx, anyio) fire during GC.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            history, dom_html, final_failure_shot_rel = loop.run_until_complete(_run_agent())
        finally:
            # Give pending callbacks a chance to finish before closing
            try:
                loop.run_until_complete(asyncio.sleep(0.1))
            except Exception:
                pass
            loop.close()
            asyncio.set_event_loop(None)
    except Exception as exc:
        tb = traceback.format_exc()
        _update_db_status(
            job_id,
            status=TestRunStatus.FAILED,
            patch={
                "error_message": f"Agent runtime error: {exc}\n{tb}",
                "completed_at": datetime.utcnow(),
                "is_successful": False,
            },
        )
        # Fire Slack alert for hard crashes (timeouts, OOM, etc.)
        # The normal integration block below is never reached on re-raise.
        try:
            from .integrations import slack_client as _sc
            from .models import UserSettings as _US
            _db = SessionLocal()
            try:
                _run = _db.query(TestRun).filter(TestRun.job_id == job_id).first()
                _owner = _run.owner_id if _run else None
                _u = _db.query(_US).filter(_US.owner_id == _owner).first() if _owner else None
                _wh = (_u.slack_webhook_url if _u else None) or settings.SLACK_WEBHOOK_URL
                _enabled = _u.slack_auto_alert_on_failure if _u else True
                _dash = (_u.dashboard_base_url if _u else None) or settings.DASHBOARD_BASE_URL
                if _wh and _enabled:
                    _sc.send_qa_incident(
                        webhook_url=_wh,
                        test_name=name,
                        job_id=job_id,
                        target_url=target_url,
                        expected_result=success_criteria or None,
                        actual_result=None,
                        error_message=f"Agent runtime error: {str(exc)[:400]}",
                        dashboard_run_url=f"{_dash.rstrip('/')}/runs/{job_id}" if _dash else None,
                    )
                    logger.info("Slack crash alert sent (job_id=%s)", job_id)
            finally:
                _db.close()
        except Exception as _se:
            logger.warning("Slack crash alert failed (job_id=%s): %s", job_id, _se)
        raise

    # --- Process result history ---
    dest_dir = _job_screenshot_dir(job_id)
    # Each element: (rel_path, caption, step_index, is_failure_point)
    screenshots_persisted: list[tuple[str, str, Optional[int], bool]] = []

    try:
        urls_visited = history.urls() or []          # list[str|None]
        shot_paths = history.screenshot_paths(
            return_none_if_not_screenshot=False
        ) or []                                      # list[str] (non-None only)
        total_steps_count = history.number_of_steps() or 0
        duration = int(history.total_duration_seconds() or 0)
        final_result_text = history.final_result() or ""
        is_done = history.is_done()
        any_errors = history.has_errors()            # bool in 0.13.7

        # ── Determine success correctly ───────────────────────────────────────
        # browser-use's done() action accepts a boolean success flag.
        # history.is_done() returns True for ANY done() call — including
        # done(False) / done("FAILED ..."). We must check is_successful()
        # which reflects the actual flag the agent passed to done().
        #
        # Additionally guard against agents that write "FAILED" / "failed"
        # in their final result text (as seen in the wild) without using
        # done(False) — treat those as failures too.
        #
        # Precedence:
        #  1. history.is_successful() if available (most accurate)
        #  2. Explicit failure keywords in final_result_text
        #  3. Original fallback: is_done and non-empty result
        try:
            # browser-use ≥ 0.1.x exposes is_successful() on AgentHistory
            agent_says_successful: Optional[bool] = history.is_successful()
        except Exception:
            agent_says_successful = None

        _result_lower = (final_result_text or "").lower()
        _result_signals_failure = any(
            kw in _result_lower
            for kw in (
                "test failed",
                "test marked as failed",
                "marked as failed",
                "task failed",
                "verification failed",
                "assertion failed",
                "did not match",
                "not found",
                "qa test failed",
                "expected number",
                "actual number",
            )
        )

        if agent_says_successful is False:
            # Agent explicitly called done(success=False) — trust this above all
            is_successful = False
        elif _result_signals_failure:
            # Agent wrote clear failure language in result text
            is_successful = False
        elif agent_says_successful is True and not _result_signals_failure:
            # Agent called done(success=True) and result has no failure language
            is_successful = True
        else:
            # Original fallback
            is_successful = is_done and bool(final_result_text)

        logger.info(
            "Success determination: job_id=%s agent_says_successful=%s "
            "result_signals_failure=%s is_done=%s → is_successful=%s | "
            "final_result_preview=%s",
            job_id, agent_says_successful, _result_signals_failure,
            is_done, is_successful,
            (final_result_text or "")[:120],
        )

        # Copy agent-saved screenshot files into our managed dir
        for idx, src in enumerate(shot_paths):
            is_last = idx == len(shot_paths) - 1
            rel = _copy_screenshot(src, dest_dir, f"step_{idx:03d}")
            if rel:
                capt = urls_visited[idx] if idx < len(urls_visited) else None
                screenshots_persisted.append(
                    (rel, capt or "", idx, is_last and not is_successful)
                )

        # Append the explicit full-page failure screenshot we captured above
        if final_failure_shot_rel:
            screenshots_persisted.append(
                (
                    final_failure_shot_rel,
                    "Final failure state (full-page capture)",
                    len(shot_paths),
                    True,
                )
            )

        # Build structured steps log from action_history()
        # Returns list[list[dict]] — one inner list per step; flatten to 200 actions
        # In browser-use 0.13.7, each dict has the action name as top-level key
        # e.g. {"navigate": {"url": "..."}, "result": "...", "interacted_element": ...}
        try:
            actions_flat: list[dict] = []
            for step_idx, step_actions in enumerate(history.action_history() or []):
                for action_dict in step_actions:
                    # Find the action key (everything except known meta keys)
                    meta_keys = {"result", "error", "interacted_element", "step"}
                    action_keys = [k for k in action_dict if k not in meta_keys]
                    action_name = action_keys[0] if action_keys else "unknown"
                    action_params = action_dict.get(action_name, {})

                    entry: dict = {
                        "step": step_idx,
                        "action": {action_name: action_params},
                        "result": action_dict.get("result"),
                        "error": action_dict.get("error"),
                    }
                    actions_flat.append(entry)
                    if len(actions_flat) >= 200:
                        break
                if len(actions_flat) >= 200:
                    break
            steps_log_json = json.dumps(actions_flat, default=str, ensure_ascii=False)
        except Exception:
            steps_log_json = json.dumps({"note": "action_history_unavailable"})

        patch: dict[str, Any] = {
            "total_steps": total_steps_count,
            "duration_seconds": duration,
            "visited_urls": json.dumps(
                [u for u in urls_visited if u], ensure_ascii=False
            ),
            "steps_log": steps_log_json,
            "final_result": str(final_result_text) if final_result_text else None,
            "dom_snapshot": dom_html,
            "result_summary": (
                f"Steps: {total_steps_count} | Duration: {duration}s | "
                f"Done: {is_done} | Intermediate errors: {any_errors}"
            ),
            "has_visual_proof": len(screenshots_persisted) > 0,
            "is_successful": is_successful,
            "completed_at": datetime.utcnow(),
        }

        final_status = (
            TestRunStatus.COMPLETED if is_successful else TestRunStatus.FAILED
        )
        _update_db_status(job_id, status=final_status, patch=patch)

        # Persist screenshot rows in DB
        if screenshots_persisted:
            db = SessionLocal()
            try:
                run = db.query(TestRun).filter(TestRun.job_id == job_id).first()
                if run:
                    for rel_path, caption, idx, is_failure in screenshots_persisted:
                        db.add(TestScreenshot(
                            test_run_id=run.id,
                            file_path=rel_path,
                            url=None,
                            caption=caption or None,
                            step_index=idx,
                            is_failure_point=is_failure,
                        ))
                    db.commit()
            finally:
                db.close()

        # --- Auto-integrations on FAILURE ---
        if final_status == TestRunStatus.FAILED:
            logger.info("AUTO-INTEGRATIONS TRIGGERED for job_id=%s", job_id)
            try:
                from .integrations import linear_client, email_client, slack_client

                db = SessionLocal()
                try:
                    run = db.query(TestRun).filter(TestRun.job_id == job_id).first()
                    run_id: Optional[int] = run.id if run else None

                    shot_count = len(screenshots_persisted)

                    # ---- Linear auto-ticket ----
                    if (
                        run_id is not None
                        and settings.LINEAR_API_KEY
                        and settings.LINEAR_TEAM_ID
                    ):
                        try:
                            existing = (
                                db.query(LinearIssue)
                                .filter(LinearIssue.test_run_id == run_id)
                                .first()
                            )
                            if not existing:
                                lin_title = f"[QA FAILURE] {name} — {job_id[:8]}"
                                lin_desc = (
                                    f"### Test run failed\n\n"
                                    f"- **Name:** {name}\n"
                                    f"- **Job ID:** `{job_id}`\n"
                                    f"- **Target URL:** {target_url or 'N/A'}\n"
                                    f"- **Duration:** {duration}s over {total_steps_count} steps\n"
                                    f"- **Success criteria:** {success_criteria or 'N/A'}\n\n"
                                    f"### Prompt executed\n\n```\n{prompt}\n```\n\n"
                                    f"### Agent result\n\n```\n"
                                    f"{(final_result_text or '(empty)')[:4000]}\n```\n\n"
                                    f"Screenshots captured: {shot_count}. "
                                    f"View failure screenshots in dashboard (job `{job_id}`)."
                                )
                                lin_res = linear_client.create_issue(
                                    title=lin_title,
                                    description_md=lin_desc,
                                )
                                if lin_res.get("success"):
                                    db.add(LinearIssue(
                                        test_run_id=run_id,
                                        issue_id=lin_res["issue_id"],
                                        identifier=lin_res.get("identifier"),
                                        title=lin_res.get("title") or lin_title,
                                        url=lin_res.get("url"),
                                    ))
                                    db.commit()
                        except Exception:
                            pass  # integration failure must never block test result

                    # Resolve failure screenshot abs path for email attachment
                    email_shot_abs: Optional[str] = None
                    if final_failure_shot_rel:
                        fp = final_failure_shot_rel
                        candidate = (
                            fp if os.path.isabs(fp)
                            else os.path.normpath(
                                os.path.join(os.path.dirname(SCREENSHOT_ROOT), fp)
                            )
                        )
                        if os.path.isfile(candidate):
                            email_shot_abs = candidate

                    # ---- Resend email auto-alert ----
                    if settings.RESEND_API_KEY and settings.EMAIL_ALERT_TO:
                        try:
                            steps_payload = (
                                patch.get("steps_log")
                                or (run.steps_log if run else None)
                                or "(steps log unavailable)"
                            )
                            email_client.send_test_failure_alert(
                                test_name=name,
                                job_id=job_id,
                                steps_summary=steps_payload,
                                screenshot_path=email_shot_abs,
                            )
                        except Exception:
                            pass

                    # ---- Slack QA incident auto-alert (per-user) ----
                    # Look up the run owner's saved Slack settings first.
                    # Falls back to global SLACK_WEBHOOK_URL from .env for
                    # single-tenant / self-hosted deployments.
                    from ..models import UserSettings as _UserSettings
                    user_slack_url: Optional[str] = None
                    user_slack_enabled: bool = True
                    user_dashboard_base: Optional[str] = None

                    if run and run.owner_id:
                        try:
                            u_cfg = (
                                db.query(_UserSettings)
                                .filter(_UserSettings.owner_id == run.owner_id)
                                .first()
                            )
                            if u_cfg:
                                user_slack_url = u_cfg.slack_webhook_url
                                user_slack_enabled = u_cfg.slack_auto_alert_on_failure
                                user_dashboard_base = u_cfg.dashboard_base_url.strip() if u_cfg.dashboard_base_url else None
                                logger.info(
                                    "Slack lookup: owner=%s url_set=%s enabled=%s",
                                    run.owner_id, bool(user_slack_url), user_slack_enabled,
                                )
                            else:
                                logger.info(
                                    "Slack lookup: no UserSettings row for owner=%s",
                                    run.owner_id,
                                )
                        except Exception as _lookup_exc:
                            logger.warning(
                                "Slack UserSettings lookup failed (owner=%s): %s",
                                run.owner_id, _lookup_exc,
                            )
                    else:
                        logger.info(
                            "Slack lookup: run has no owner_id (job_id=%s), "
                            "falling back to global SLACK_WEBHOOK_URL",
                            job_id,
                        )

                    effective_webhook = user_slack_url or settings.SLACK_WEBHOOK_URL
                    logger.info(
                        "Slack gate: effective_webhook=%s enabled=%s (job_id=%s)",
                        bool(effective_webhook), user_slack_enabled, job_id,
                    )

                    if effective_webhook and user_slack_enabled:
                        try:
                            # Resolve any Linear issue just created
                            lin_url: Optional[str] = None
                            lin_id: Optional[str] = None
                            if run_id is not None:
                                lin_issue = (
                                    db.query(LinearIssue)
                                    .filter(LinearIssue.test_run_id == run_id)
                                    .first()
                                )
                                if lin_issue:
                                    lin_url = lin_issue.url
                                    lin_id = lin_issue.identifier

                            ctx = _build_incident_context(
                                name=name,
                                job_id=job_id,
                                prompt=prompt,
                                target_url=target_url,
                                success_criteria=success_criteria,
                                steps_log_json=steps_log_json,
                                final_result_text=final_result_text,
                                error_message=run.error_message if run else None,
                                total_steps_count=total_steps_count,
                                duration=duration,
                                screenshots_persisted=screenshots_persisted,
                                final_failure_shot_rel=final_failure_shot_rel,
                                completed_at=datetime.utcnow(),
                                dashboard_base_url=(
                                    user_dashboard_base
                                    or settings.DASHBOARD_BASE_URL
                                ),
                                linear_issue_url=lin_url,
                                linear_identifier=lin_id,
                            )
                            slack_client.send_qa_incident(
                                webhook_url=effective_webhook,
                                **ctx,
                            )
                        except Exception as _slack_exc:
                            logger.warning(
                                "Slack QA incident send failed (job_id=%s): %s",
                                job_id, _slack_exc, exc_info=True,
                            )
                finally:
                    db.close()
            except Exception:
                pass

        return {
            "job_id": job_id,
            "status": final_status.value,
            "is_successful": is_successful,
            "total_steps": total_steps_count,
            "duration_seconds": duration,
            "final_result": str(final_result_text) if final_result_text else None,
            "screenshots_count": len(screenshots_persisted),
        }

    except Exception as exc:
        tb = traceback.format_exc()
        _update_db_status(
            job_id,
            status=TestRunStatus.FAILED,
            patch={
                "error_message": f"Result processing error: {exc}\n{tb}",
                "completed_at": datetime.utcnow(),
                "is_successful": False,
            },
        )
        raise
