"""
Celery worker: runs a browser-use Agent for a given QA test.

WINDOWS NOTE: Python 3.13 on Windows uses SelectorEventLoop by default,
which cannot spawn subprocesses (Playwright/Chromium). We must set
WindowsProactorEventLoopPolicy before any asyncio.run() call.
"""

import asyncio
import base64
import json
import os
import platform
import shutil
import sys
import uuid
from datetime import datetime
from typing import Any, Optional

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


SCREENSHOT_ROOT = os.path.abspath(settings.SCREENSHOT_DIR)
os.makedirs(SCREENSHOT_ROOT, exist_ok=True)


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

        # In browser-use 0.13.7 the correct action name for navigation
        # is 'navigate', not 'go_to_url'. However initial_actions is not
        # needed — the target URL is already baked into task_text so the
        # LLM will navigate there as its first step. Remove initial_actions
        # entirely to avoid version-specific action name issues.
        agent = Agent(
            task=task_text,
            llm=llm,
            browser_session=browser_session,
            use_vision=use_vision,
            max_failures=5,
            max_actions_per_step=5,
            step_timeout=60,
            llm_timeout=60,
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

        # A run is successful if the agent called done() AND produced a
        # final result. Intermediate step errors (retries, timeouts,
        # element-not-found) are normal browser-use behavior — they
        # should not mark the entire run failed when the agent ultimately
        # completed the task and returned a meaningful result.
        is_successful = is_done and bool(final_result_text)

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

                    # ---- Slack webhook auto-alert ----
                    if settings.SLACK_WEBHOOK_URL:
                        try:
                            slack_client.send_test_failure_alert(
                                test_name=name,
                                job_id=job_id,
                                total_steps=total_steps_count,
                                duration_seconds=duration,
                                success_criteria=success_criteria,
                                error_message=None,
                                target_url=target_url,
                            )
                        except Exception:
                            pass
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
