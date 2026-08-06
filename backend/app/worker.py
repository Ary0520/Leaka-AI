import asyncio
import json
import os
import shutil
import uuid
from datetime import datetime
from typing import Any, Optional

from .celery_app import celery_app
from .config import settings
from .database import SessionLocal
from .llm import get_llm
from .models import (
    TestRun,
    TestRunStatus,
    TestScreenshot,
    TestCase,
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
    """Copy a browser-use screenshot into our managed dir. Returns new relative path."""
    if not src_path or not os.path.isfile(src_path):
        return None
    ext = os.path.splitext(src_path)[1] or ".png"
    dest_path = os.path.join(dest_dir, f"{name}{ext}")
    try:
        shutil.copyfile(src_path, dest_path)
    except Exception:
        return None
    # Store relative path for portability
    return os.path.relpath(dest_path, start=os.path.dirname(SCREENSHOT_ROOT))


@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    name="app.worker.run_browser_test",
)
def run_browser_test(
    self,
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
    Run a browser-use Agent against the given natural-language QA prompt.

    Lifecycle:
      1. Update TestRun to RUNNING, set started_at
      2. Build the LLM (honours LLM_PROVIDER env setting)
      3. Run Agent(...) async via asyncio
      4. Persist screenshots, result, DOM, steps
      5. Update TestRun to COMPLETED / FAILED
    """
    import traceback

    self.update_state(
        state="PROGRESS",
        meta={"stage": "initializing_browser", "step": 0, "total": max_steps},
    )
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

    # Build the full task string with structure per the browser-use prompting guide
    task_parts = []
    if target_url:
        task_parts.append(f"Target URL: {target_url}")
    task_parts.append(f"Task: {prompt}")
    if success_criteria:
        task_parts.append(f"Success criteria to validate after execution: {success_criteria}")
    task_text = "\n".join(task_parts)

    self.update_state(
        state="PROGRESS",
        meta={"stage": "running_agent", "step": 0, "total": max_steps},
    )

    async def _run_agent():
        # Import here so worker startup stays fast even if playwright has issues
        from browser_use import Agent

        agent = Agent(
            task=task_text,
            llm=llm,
            use_vision=use_vision,
            max_failures=3,
            max_actions_per_step=3,
            directly_open_url=bool(target_url),
            step_timeout=180,
            llm_timeout=120,
        )
        return await agent.run(max_steps=max_steps)

    try:
        history = asyncio.run(_run_agent())
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
    screenshots_persisted: list[tuple[str, str, Optional[int], bool]] = []

    try:
        urls_visited = history.urls() or []
        shot_paths = history.screenshot_paths() or []
        all_errors = history.errors() or []
        total_steps_count = history.number_of_steps() or 0
        duration = int(history.total_duration_seconds() or 0)
        final_result_text = history.final_result() or ""
        is_done = bool(history.is_done())
        any_errors = any(e is not None for e in all_errors)

        is_successful = is_done and not any_errors

        # Copy screenshot files
        for idx, src in enumerate(shot_paths):
            is_last = idx == len(shot_paths) - 1
            rel = _copy_screenshot(src, dest_dir, f"step_{idx:03d}")
            if rel:
                capt = urls_visited[idx] if idx < len(urls_visited) else None
                screenshots_persisted.append(
                    (rel, capt or "", idx, is_last and (not is_successful))
                )

        # Build structured steps log from action history (truncated for DB)
        try:
            actions_list = []
            for item in list(history.action_history() or [])[:200]:
                actions_list.append({k: v for k, v in dict(item).items() if k in {
                    "step", "action", "url", "result", "error",
                }})
            steps_log_json = json.dumps(actions_list, default=str, ensure_ascii=False)
        except Exception:
            steps_log_json = json.dumps({"note": "action_history_unavailable"})

        patch: dict[str, Any] = {
            "total_steps": total_steps_count,
            "duration_seconds": duration,
            "visited_urls": json.dumps(urls_visited, ensure_ascii=False),
            "steps_log": steps_log_json,
            "final_result": str(final_result_text) if final_result_text else None,
            "result_summary": (
                f"Steps: {total_steps_count} | Duration: {duration}s | "
                f"Done: {is_done} | Errors: {any_errors}"
            ),
            "has_visual_proof": len(screenshots_persisted) > 0,
            "is_successful": is_successful,
            "completed_at": datetime.utcnow(),
        }

        final_status = (
            TestRunStatus.COMPLETED if is_successful else TestRunStatus.FAILED
        )
        _update_db_status(job_id, status=final_status, patch=patch)

        # Persist screenshot rows
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
