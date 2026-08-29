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
    TestCase,
    TestRun,
    TestRunStatus,
    TestScreenshot,
    UserSettings,
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
# Memory integration (Task 15) — ADDITIVE + FULLY GUARDED.
# A test run is linked to a graph node via a CoverageLink (test_case → node →
# application). Before the run we inject learned locator/timing hints; after,
# we write back the outcome. Every function below is best-effort: any failure
# is swallowed so the QA run behaves EXACTLY as before.
# ---------------------------------------------------------------------------
def _linked_node_for_test(db, test_case_id: Optional[int]):
    """Return (application_id, node_id, owner_id) for a test's coverage link, or None."""
    if not test_case_id:
        return None
    try:
        from .models import CoverageLink
        link = (
            db.query(CoverageLink)
            .filter(CoverageLink.test_case_id == test_case_id, CoverageLink.orphaned == False)  # noqa: E712
            .order_by(CoverageLink.id.desc())
            .first()
        )
        if link is None:
            return None
        return (link.application_id, link.node_id, link.owner_id)
    except Exception:
        return None


def _extract_locator_memories(history) -> list[dict]:
    """
    Extract the element locators that DEMONSTRABLY WORKED during this run, as a
    ranked preferred-locator hierarchy (Requirement 5.1: "preferred locator
    hierarchies"). Pure/best-effort: reads only the agent's own history, never
    fabricates, and returns [] on any problem so it can never break a run.

    Evidence source (verified against browser-use 0.13.7):
      history.model_actions() → per-action dicts, each carrying the
      `interacted_element` (a DOMInteractedElement with x_path, ax_name,
      attributes, node_name). We keep only interaction actions (click/input/
      select) — an element the agent actually used to progress the task is, by
      definition, a locator that worked.

    For each such element we record a STABLE, ranked locator hierarchy, most
    durable first (self-healing seed for a later spec):
      1. data-testid / data-test / data-cy   (purpose-built, most stable)
      2. id                                    (stable when not generated)
      3. name                                  (stable for form fields)
      4. role + accessible name (ax_name)      (semantic, survives restyles)
      5. xpath                                  (last resort, brittle)

    Returns a list of payload dicts ready for MemoryWrite(kind="locator", ...).
    Deduplicated within the run by (primary locator + element text).
    """
    out: list[dict] = []
    seen: set = set()
    _INTERACTION_ACTIONS = {
        "click", "click_element_by_index", "input", "input_text", "type", "fill",
        "select", "select_dropdown_option", "select_option",
    }
    try:
        actions = history.model_actions() or []
    except Exception:
        return out

    for adict in actions:
        try:
            if not isinstance(adict, dict):
                continue
            # Identify the action name (first non-meta key).
            meta = {"result", "error", "interacted_element", "step"}
            names = [k for k in adict if k not in meta]
            action_name = names[0] if names else None
            if not action_name or action_name not in _INTERACTION_ACTIONS:
                continue

            el = adict.get("interacted_element")
            if el is None:
                continue

            # Pull element identity signals defensively (dataclass OR dict).
            def _attr(obj, key):
                if isinstance(obj, dict):
                    return obj.get(key)
                return getattr(obj, key, None)

            attrs = _attr(el, "attributes") or {}
            if not isinstance(attrs, dict):
                attrs = {}
            xpath = _attr(el, "x_path")
            ax_name = _attr(el, "ax_name")
            tag = (_attr(el, "node_name") or "").lower() or None

            # Build the ranked locator hierarchy from the strongest signals present.
            hierarchy: list[dict] = []
            testid = (
                attrs.get("data-testid") or attrs.get("data-test")
                or attrs.get("data-cy") or attrs.get("data-qa")
            )
            if testid:
                hierarchy.append({"strategy": "testid", "value": str(testid)})
            if attrs.get("id"):
                hierarchy.append({"strategy": "id", "value": str(attrs["id"])})
            if attrs.get("name"):
                hierarchy.append({"strategy": "name", "value": str(attrs["name"])})
            if ax_name:
                hierarchy.append({
                    "strategy": "role_text",
                    "value": str(ax_name)[:120],
                    "role": (attrs.get("role") or tag or None),
                })
            if xpath:
                hierarchy.append({"strategy": "xpath", "value": str(xpath)[:400]})

            if not hierarchy:
                continue  # no usable signal → skip (never fabricate)

            primary = hierarchy[0]
            dedup_key = (primary["strategy"], primary["value"], (ax_name or "")[:60])
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Human-readable "selector" used by the existing hint builder +
            # embed text; keep the full ranked hierarchy for future self-healing.
            display = _locator_display(primary, ax_name, tag)
            out.append({
                "selector": display,
                "hierarchy": hierarchy,
                "element_text": (ax_name or None),
                "tag": tag,
                "action": action_name,
            })
        except Exception:
            continue  # never let one bad action abort extraction
    return out[:50]  # bound per run


def _locator_display(primary: dict, ax_name: Optional[str], tag: Optional[str]) -> str:
    """A concise human/agent-readable locator string for the strongest strategy."""
    strat, val = primary.get("strategy"), primary.get("value", "")
    if strat == "testid":
        return f'[data-testid="{val}"]'
    if strat == "id":
        return f"#{val}"
    if strat == "name":
        return f'[name="{val}"]'
    if strat == "role_text":
        base = f'{tag or "element"} with text "{val}"'
        return base
    return val  # xpath


def _memory_hints_for_test(test_case_id: Optional[int]) -> Optional[str]:
    """
    Build a task-prompt hint block from learned Memory for the node this test is
    linked to. Returns None (no hint) on any failure — never raises.
    """
    if not test_case_id:
        return None
    db = SessionLocal()
    try:
        linked = _linked_node_for_test(db, test_case_id)
        if linked is None:
            return None
        application_id, node_id, owner_id = linked
        from . import memory as MEM

        # Semantic query = the test's INTENT (name + prompt). This activates the
        # genuine retrieval layer (embeddings + pgvector) rather than a pure
        # identity cache: memory whose meaning matches this test's goal is
        # surfaced even if it was learned on a sibling node. Degrades to
        # identity-only automatically when the vector backend is unavailable
        # (R5.2, R5.9). Best-effort — a lookup failure just yields no hint.
        query: Optional[str] = None
        try:
            tc = db.query(TestCase).filter(TestCase.id == test_case_id).first()
            if tc is not None:
                query = " ".join(filter(None, [tc.name, tc.prompt]))[:400] or None
        except Exception:
            query = None

        items = MEM.retrieve(
            db, application_id, owner_id=owner_id, node_id=node_id, query=query, k=8
        )
        if not items:
            return None

        locator_lines: list[str] = []
        timing_lines: list[str] = []
        for it in items:
            if it.kind == "locator":
                loc = it.payload.get("selector") or it.payload.get("css") or it.payload.get("xpath")
                if loc:
                    locator_lines.append(f"- {loc}")
            elif it.kind == "timing":
                ms = it.payload.get("ms")
                if ms:
                    timing_lines.append(f"- observed ~{ms}ms")
        if not locator_lines and not timing_lines:
            return None

        parts = ["\n--- LEAKA MEMORY (learned hints — use if helpful, ignore if stale) ---"]
        if locator_lines:
            parts.append("Preferred element locators that worked before:")
            parts.extend(locator_lines[:6])
        if timing_lines:
            parts.append("Observed timing (wait at least this long for async updates):")
            parts.extend(timing_lines[:3])
        return "\n".join(parts)
    except Exception:
        return None
    finally:
        db.close()


def _write_run_outcome_memory(
    test_case_id: Optional[int], *, is_successful: Optional[bool], duration_seconds: int,
    locators: Optional[list[dict]] = None,
) -> Optional[int]:
    """
    After a run, write back learned knowledge for the linked node, with
    provenance (R5.1, R5.5): the run `outcome`, its `timing`, and — when the run
    SUCCEEDED — the element `locator`s that worked (preferred-locator hierarchy).
    Best-effort; never raises (memory.write also never raises, but we guard the
    lookup too).

    Locators are only written on a successful run: a locator that worked while
    the test still failed is weaker evidence, so we don't teach it as preferred.

    Returns the `application_id` the outcome was recorded against (so the caller
    can trigger a risk/coverage recompute per R3.6), or None when there is no
    linked node / nothing was written.
    """
    if not test_case_id:
        return None
    db = SessionLocal()
    try:
        linked = _linked_node_for_test(db, test_case_id)
        if linked is None:
            return None
        application_id, node_id, owner_id = linked
        from . import memory as MEM
        prov = {"source": "test_run", "test_case_id": test_case_id,
                "at": datetime.utcnow().isoformat()}
        MEM.write(db, MEM.MemoryWrite(
            application_id=application_id, kind="outcome", owner_id=owner_id,
            node_id=node_id, provenance=prov,
            payload={"passed": bool(is_successful), "duration_seconds": int(duration_seconds)},
        ))
        if duration_seconds and duration_seconds > 0:
            MEM.write(db, MEM.MemoryWrite(
                application_id=application_id, kind="timing", owner_id=owner_id,
                node_id=node_id, provenance=prov,
                payload={"ms": int(duration_seconds) * 1000},
            ))

        # Preferred-locator hierarchy — only teach locators from a PASSING run.
        if is_successful and locators:
            for loc in locators:
                # embed_text drives semantic retrieval: the element's visible
                # text + selector is what a future run's intent matches against.
                embed_text = " ".join(filter(None, [
                    loc.get("element_text"), loc.get("selector"), loc.get("tag"),
                ])) or loc.get("selector")
                MEM.write(db, MEM.MemoryWrite(
                    application_id=application_id, kind="locator", owner_id=owner_id,
                    node_id=node_id, provenance=prov,
                    payload={
                        "selector": loc.get("selector"),
                        "hierarchy": loc.get("hierarchy"),
                        "element_text": loc.get("element_text"),
                        "tag": loc.get("tag"),
                        "action": loc.get("action"),
                    },
                    embed_text=embed_text,
                ))
        return application_id
    except Exception:
        return None
    finally:
        db.close()


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
    seen_step_indices: set = set()
    for entry in actions:
        action_dict = entry.get("action", {})
        action_name = next(iter(action_dict), None) if action_dict else None
        step_idx = entry.get("step", -1)

        # Skip non-user-facing noise and dedup within same step
        if not action_name or action_name in ("unknown", "done", "wait",
                                               "search_page", "scroll"):
            continue

        params = action_dict.get(action_name, {})
        result_text = str(entry.get("result", "") or "").strip()
        result_first_line = result_text.split("\n")[0][:120] if result_text else ""

        step_label: Optional[str] = None

        if isinstance(params, dict):
            if action_name == "navigate":
                url = params.get("url", "")
                step_label = f"Navigate to {url[:80]}" if url else None

            elif action_name in ("click",):
                # Use result text if it describes what was clicked
                # e.g. "Clicked element 'Upload Content'"
                if result_first_line and len(result_first_line) > 3:
                    step_label = result_first_line
                elif params.get("selector"):
                    step_label = f"Click {params['selector'][:60]}"
                else:
                    step_label = None  # bare index with no result — skip

            elif action_name in ("input", "type", "fill"):
                text_val = params.get("text", "")
                # Use the result which says "Typed 'xyz'"
                if result_first_line and "typed" in result_first_line.lower():
                    step_label = result_first_line
                elif text_val:
                    step_label = f"Enter '{text_val[:60]}'"
                else:
                    step_label = None

            else:
                if result_first_line and len(result_first_line) > 3:
                    step_label = result_first_line
                elif params:
                    first_val = str(list(params.values())[0])[:60]
                    if first_val and not first_val.isdigit():
                        step_label = f"{action_name}: {first_val}"

        if step_label and step_label not in repro_steps:
            repro_steps.append(step_label)

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

    # ── Visual-observation rule ───────────────────────────────────────────────
    # Many modern SPAs (React, Next.js, Web3 apps) render result messages
    # inside portals, modals, or async-updated components whose text content
    # is NOT reliably found by search_page (DOM text search).
    # This instruction tells the agent to use its visual perception — which
    # reads the rendered pixels — instead of relying solely on text search,
    # especially after any action that triggers async processing.
    # This does NOT change any architecture; it is purely a task-prompt suffix.
    task_parts.append(
        "\n--- OBSERVATION RULES (follow strictly) ---\n"
        "1. After ANY form submission, button click, or action that triggers "
        "async processing (e.g. blockchain transactions, API calls, uploads): "
        "WAIT 3-5 seconds for the page to fully update, then use your VISUAL "
        "perception to directly read any messages, modals, banners, alerts, or "
        "status indicators that appear on screen. Do NOT rely solely on "
        "search_page — modern web apps render result messages via JavaScript "
        "after the initial DOM load, and search_page may miss them entirely.\n"
        "2. If you visually see a success or error message, READ it directly "
        "and report exactly what it says — do not search for keywords.\n"
        "3. When determining the final outcome, use extract_content or direct "
        "visual observation as your primary method. Use search_page only as a "
        "secondary confirmation.\n"
        "4. If the page shows an error message (even inside a modal or overlay), "
        "that IS your answer — report it accurately as the test result using "
        "done(success=False, result='<exact error text you see on screen>').\n"
        "5. If the page shows a success message, report it using "
        "done(success=True, result='<exact success text you see on screen>')."
    )

    # ── Memory hints (additive, fully guarded) ─────────────────────────────
    # If this test is linked to a graph node (via a CoverageLink), inject any
    # learned locator/timing hints Leaka has for that node. NEVER fails the run.
    memory_hint = _memory_hints_for_test(test_case_id)
    if memory_hint:
        task_parts.append(memory_hint)

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
            use_thinking=False,         # disable: causes parse failures via OpenRouter
            max_failures=5,
            max_actions_per_step=5,
            step_timeout=60,
            llm_timeout=60,
            message_compaction=False,
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
            _db = SessionLocal()
            try:
                _run = _db.query(TestRun).filter(TestRun.job_id == job_id).first()
                _owner = _run.owner_id if _run else None
                _u = (
                    _db.query(UserSettings).filter(UserSettings.owner_id == _owner).first()
                    if _owner else None
                )
                _wh = (_u.slack_webhook_url if _u else None) or settings.SLACK_WEBHOOK_URL
                _enabled = _u.slack_auto_alert_on_failure if _u else True
                _dash = (_u.dashboard_base_url if _u else None) or settings.DASHBOARD_BASE_URL
                if _wh and _enabled:
                    _crash_res = _sc.send_qa_incident(
                        webhook_url=_wh,
                        test_name=name,
                        job_id=job_id,
                        target_url=target_url,
                        expected_result=success_criteria or None,
                        actual_result=None,
                        error_message=f"Agent runtime error: {str(exc)[:400]}",
                        dashboard_run_url=f"{_dash.rstrip('/')}/runs/{job_id}" if _dash else None,
                    )
                    if _crash_res.get("ok"):
                        logger.info("Slack crash alert sent (job_id=%s)", job_id)
                    else:
                        logger.warning(
                            "Slack crash alert rejected (job_id=%s): %s",
                            job_id, _crash_res,
                        )
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
                # Blockchain / Web3 / transaction failure signals
                "registration failed",
                "transaction failed",
                "blockchain transaction failed",
                "blockchain error",
                "error: blockchain",
                "bigint",
                "serialize",
                # Generic app-level failure signals
                "something went wrong",
                "an error occurred",
                "operation failed",
                "request failed",
                "error occurred",
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

        # ── Detect "agent stopped without calling done()" ────────────────────
        # This happens when browser-use exits the run loop via:
        #   a) consecutive_failures >= max_failures — the LLM returned errors
        #      on every step (e.g. 401/403 API key issues, rate limits), OR
        #   b) max_steps exhausted (while-loop ran to completion without break)
        # In both cases: is_done=False, final_result=None, is_successful=None.
        # We surface the last agent error from history so the user gets a
        # clear, actionable message instead of silence.
        agent_abort_reason: Optional[str] = None
        if not is_done and not final_result_text:
            # Pull all non-None errors from the agent's history
            try:
                all_errors = [e for e in (history.errors() or []) if e]
                last_error = all_errors[-1] if all_errors else None
            except Exception:
                last_error = None

            # ── Classify the error for a clean user-facing message ────────
            _err_str = str(last_error or "").lower()

            if "403" in _err_str or "key limit exceeded" in _err_str or "limit exceeded" in _err_str:
                agent_abort_reason = (
                    "LLM API error: API key credit limit exceeded (HTTP 403). "
                    "Top up your OpenRouter / OpenAI / Anthropic credits, or "
                    "switch to a different LLM provider in Settings."
                )
            elif "401" in _err_str or "unauthorized" in _err_str or "invalid api key" in _err_str or "authentication" in _err_str:
                agent_abort_reason = (
                    "LLM API error: Invalid or missing API key (HTTP 401). "
                    "Check your API key in Settings → LLM Provider."
                )
            elif "429" in _err_str or "rate limit" in _err_str or "too many requests" in _err_str:
                agent_abort_reason = (
                    "LLM API error: Rate limit hit (HTTP 429). "
                    "Too many requests in a short period. Wait a moment and retry, "
                    "or upgrade your API plan."
                )
            elif "timeout" in _err_str or "timed out" in _err_str:
                agent_abort_reason = (
                    "Agent timed out waiting for a response. "
                    "The LLM or the target page took too long to respond. "
                    "Retry the test, or check if the target URL is reachable."
                )
            elif last_error:
                agent_abort_reason = (
                    f"Agent stopped after {total_steps_count} steps. "
                    f"Last error: {str(last_error)[:400]}"
                )
            elif any_errors:
                agent_abort_reason = (
                    "Agent stopped due to consecutive failures. "
                    "It could not complete the task — likely because page content "
                    "is rendered dynamically (JavaScript/async) and the agent's "
                    "text-search returned no matches. "
                    "Check the Screenshots tab to see the actual page state."
                )
            else:
                agent_abort_reason = (
                    f"Agent stopped after {total_steps_count} steps without "
                    "completing the task. It may have exceeded max_steps, or "
                    "could not find the expected UI state."
                )

            logger.warning(
                "Agent stopped without done() call: job_id=%s steps=%s "
                "is_done=%s any_errors=%s last_error=%s",
                job_id, total_steps_count, is_done, any_errors,
                str(last_error or "")[:200],
            )

        logger.info(
            "Success determination (LLM verdict): job_id=%s agent_says_successful=%s "
            "result_signals_failure=%s is_done=%s → is_successful=%s | "
            "final_result_preview=%s",
            job_id, agent_says_successful, _result_signals_failure,
            is_done, is_successful,
            (final_result_text or "")[:120],
        )

        # ── Deterministic assertion layer (Test Oracle) ──────────────────────
        # If the test defines assertions, verify them against the ACTUAL
        # captured page state (final DOM + final URL) — independent of the LLM.
        # Rules:
        #   - No assertions  → is_successful is UNCHANGED (LLM verdict stands).
        #   - Has assertions → is_successful = (LLM verdict) AND (all assertions pass).
        #     Assertions can only make a run FAIL, never make a failing run pass.
        assertion_results_json: Optional[str] = None
        try:
            db_a = SessionLocal()
            try:
                _run_row = db_a.query(TestRun).filter(TestRun.job_id == job_id).first()
                raw_assertions = _run_row.assertions if _run_row else None
            finally:
                db_a.close()

            parsed_assertions = []
            if raw_assertions:
                try:
                    loaded = json.loads(raw_assertions)
                    if isinstance(loaded, list):
                        parsed_assertions = loaded
                except Exception:
                    parsed_assertions = []

            if parsed_assertions:
                from .assertions import evaluate_assertions

                final_url = None
                for _u in reversed(urls_visited):
                    if _u:
                        final_url = _u
                        break

                all_passed, results = evaluate_assertions(
                    parsed_assertions,
                    dom_html=dom_html,
                    final_url=final_url,
                )
                assertion_results_json = json.dumps(results, default=str, ensure_ascii=False)

                llm_verdict = is_successful
                # Fold assertions in: only tighten, never loosen.
                is_successful = bool(llm_verdict) and all_passed

                logger.info(
                    "Assertion layer: job_id=%s count=%s all_passed=%s "
                    "llm_verdict=%s → final is_successful=%s",
                    job_id, len(parsed_assertions), all_passed,
                    llm_verdict, is_successful,
                )
        except Exception as _assert_exc:
            # Assertion evaluation must NEVER crash a run. On error, leave the
            # LLM verdict untouched and record nothing.
            logger.warning(
                "Assertion evaluation failed (job_id=%s): %s", job_id, _assert_exc,
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

        # Extract the element locators that worked this run (preferred-locator
        # hierarchy) while `history` is in scope — persisted to Memory below,
        # only if the run passed. Best-effort; never affects the run.
        try:
            learned_locators = _extract_locator_memories(history)
        except Exception:
            learned_locators = []

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
            # Surface the abort reason as error_message when the agent stopped
            # without calling done() — this fills the "Error" section in the UI
            # and gives the integrations (Slack, Linear) actionable context.
            "error_message": agent_abort_reason if agent_abort_reason else None,
            "has_visual_proof": len(screenshots_persisted) > 0,
            "is_successful": is_successful,
            "assertion_results": assertion_results_json,
            "completed_at": datetime.utcnow(),
        }

        final_status = (
            TestRunStatus.COMPLETED if is_successful else TestRunStatus.FAILED
        )
        _update_db_status(job_id, status=final_status, patch=patch)

        # Memory write-back (additive, guarded): record the outcome + timing for
        # the linked graph node so future runs benefit. Never affects this run.
        _mem_app_id = _write_run_outcome_memory(
            test_case_id, is_successful=is_successful, duration_seconds=duration,
            locators=learned_locators,
        )
        # Feedback loop (R3.6): a completed run is a new risk signal (recent
        # pass/fail + historical failure rate). Recompute coverage+risk for the
        # affected application so the graph reflects it without a re-explore.
        # Best-effort, guarded — must never affect the run that just finished.
        if _mem_app_id is not None:
            try:
                from .graph_worker import _dispatch_recompute_coverage
                _dispatch_recompute_coverage(_mem_app_id, reason="run_completed")
            except Exception:  # noqa: BLE001
                pass

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
                    user_slack_url: Optional[str] = None
                    user_slack_enabled: bool = True
                    user_dashboard_base: Optional[str] = None

                    if run and run.owner_id:
                        try:
                            u_cfg = (
                                db.query(UserSettings)
                                .filter(UserSettings.owner_id == run.owner_id)
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
                            slack_res = slack_client.send_qa_incident(
                                webhook_url=effective_webhook,
                                **ctx,
                            )
                            if slack_res.get("ok"):
                                logger.info(
                                    "Slack QA incident sent (job_id=%s dedup=%s)",
                                    job_id, slack_res.get("dedup_key"),
                                )
                            else:
                                logger.warning(
                                    "Slack QA incident rejected (job_id=%s): %s",
                                    job_id, slack_res,
                                )
                        except Exception as _slack_exc:
                            logger.warning(
                                "Slack QA incident send failed (job_id=%s): %s",
                                job_id, _slack_exc, exc_info=True,
                            )
                finally:
                    db.close()
            except Exception as _integ_exc:
                logger.error(
                    "Auto-integration block CRASHED (job_id=%s): %s",
                    job_id, _integ_exc, exc_info=True,
                )

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
