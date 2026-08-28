import atexit
import logging
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from celery.result import AsyncResult
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .celery_app import celery_app
from .config import settings
from .database import get_db, init_db
from .auth import get_current_user
from .integrations import linear_client, email_client, slack_client
from .models import (
    LinearIssue,
    TestCase,
    TestRun,
    TestRunStatus,
    TestScreenshot,
    TestSuite,
    UserSettings,
)
from .schemas import (
    CIWebhookRequest,
    CIWebhookResponse,
    CreateLinearTicketRequest,
    LinearTicketResponse,
    ScreenshotOut,
    TestCaseCreate,
    TestCaseOut,
    TestCaseUpdate,
    TestRunEnqueueResponse,
    TestRunListResponse,
    TestRunRequest,
    TestRunStatusResponse,
    TestSuiteCreate,
    TestSuiteOut,
    TestSuiteRunResponse,
    TestSuiteUpdate,
)
from .worker import run_browser_test

logger = logging.getLogger("revguard")

_SYNC_DEMO_EXECUTOR: Optional[ThreadPoolExecutor] = None
_EXECUTOR_LOCK = threading.Lock()


def _get_sync_executor() -> ThreadPoolExecutor:
    global _SYNC_DEMO_EXECUTOR
    with _EXECUTOR_LOCK:
        if _SYNC_DEMO_EXECUTOR is None:
            _SYNC_DEMO_EXECUTOR = ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="revguard_sync_demo"
            )
            atexit.register(lambda: _SYNC_DEMO_EXECUTOR.shutdown(wait=False))
    return _SYNC_DEMO_EXECUTOR


def _dispatch_run_task(
    job_id: str,
    *,
    name: str,
    prompt: str,
    target_url: str,
    success_criteria: Optional[str],
    use_vision: bool,
    max_steps: int,
    test_case_id: Optional[int],
) -> str:
    """Dispatch a test run.

    - RUN_MODE=celery    → push to Redis via run_browser_test.delay() (async, separate worker)
    - RUN_MODE=sync_demo → run the EXACT SAME Celery task locally via .apply() in a
                           background thread. No mocking. All DB writes, screenshots,
                           DOM snapshots, and auto-integrations run identically.
    """
    kwargs = dict(
        job_id=job_id,
        name=name,
        prompt=prompt,
        target_url=target_url,
        success_criteria=success_criteria,
        use_vision=use_vision,
        max_steps=max_steps,
        test_case_id=test_case_id,
    )

    if settings.RUN_MODE == "sync_demo":
        task_id = f"sync-{job_id}"

        def _run_local():
            try:
                # run_browser_test.run is the raw underlying Python function
                # with no Celery task binding — no self.update_state(), no
                # self.retry(), no broker touched. 100% same worker logic:
                # browser-use Agent, DB writes, screenshots, integrations.
                run_browser_test.run(**kwargs)
            except Exception as exc:  # noqa: BLE001 - worker already wrote FAILED to DB
                logger.exception("sync_demo worker raised (job_id=%s): %s", job_id, exc)

        _get_sync_executor().submit(_run_local)
        return task_id

    task = run_browser_test.delay(**kwargs)
    return task.id



app = FastAPI(
    title="Leaka AI — RevGuard QA API",
    version="0.1.0",
    description="Autonomous QA agent for revenue flows using browser-use.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    init_db()
    pb = settings.PLAYWRIGHT_BROWSERS_PATH
    logger.info(
        "Leaka AI RevGuard API starting — RUN_MODE=%s LLM=%s DB=%s PB=%s",
        settings.RUN_MODE,
        settings.LLM_PROVIDER,
        settings.DATABASE_URL,
        pb,
    )
    if settings.RUN_MODE == "sync_demo":
        logger.warning(
            "RUN_MODE=sync_demo: using in-process thread pool (no Redis/Celery broker). "
            "This is for local demo/dev only. Set RUN_MODE=celery with Redis for production."
        )
    if settings.LLM_PROVIDER == "ollama":
            logger.warning(
                "LLM_PROVIDER=ollama: ensure Ollama is running locally on %s "
                "with model '%s' pulled (run: ollama pull %s). "
                "Otherwise agent tasks will fail with a connection error until Ollama is available.",
                settings.OLLAMA_BASE_URL,
                settings.OLLAMA_MODEL,
                settings.OLLAMA_MODEL,
            )


# ---------------------------------------------------------------------------
# Integration Settings — read/write .env values at runtime
# ---------------------------------------------------------------------------
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


def _read_env_file() -> dict[str, str]:
    """Read the backend .env file into a dict."""
    result: dict[str, str] = {}
    if not os.path.isfile(_ENV_PATH):
        return result
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip()
    return result


def _write_env_file(updates: dict[str, str]) -> None:
    """Merge updates into the .env file, preserving comments and order."""
    lines: list[str] = []
    if os.path.isfile(_ENV_PATH):
        with open(_ENV_PATH) as f:
            lines = f.readlines()

    written_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}\n")
            written_keys.add(key)
        else:
            new_lines.append(line)

    # Append any keys not already in the file
    for key, val in updates.items():
        if key not in written_keys:
            new_lines.append(f"{key}={val}\n")

    with open(_ENV_PATH, "w") as f:
        f.writelines(new_lines)


def _mask(val: str | None) -> str:
    """Mask a secret: show first 8 chars then ***"""
    if not val:
        return ""
    if len(val) <= 8:
        return "***"
    return val[:8] + "***"


@app.get("/api/settings/integrations")
def get_integration_settings(user: dict = Depends(get_current_user)):
    """Return current integration config, secrets masked."""
    env = _read_env_file()
    return {
        "linear": {
            "api_key": _mask(env.get("LINEAR_API_KEY")),
            "api_key_set": bool(env.get("LINEAR_API_KEY")),
            "team_id": env.get("LINEAR_TEAM_ID", ""),
        },
        "resend": {
            "api_key": _mask(env.get("RESEND_API_KEY")),
            "api_key_set": bool(env.get("RESEND_API_KEY")),
            "email_from": env.get("EMAIL_FROM", ""),
            "email_alert_to": env.get("EMAIL_ALERT_TO", ""),
        },
        "slack": {
            "webhook_url": _mask(env.get("SLACK_WEBHOOK_URL")),
            "webhook_url_set": bool(env.get("SLACK_WEBHOOK_URL")),
        },
        "llm": {
            "provider": env.get("LLM_PROVIDER", ""),
            "openrouter_model": env.get("LLM_MODEL_OPENROUTER", ""),
            "openai_model": env.get("LLM_MODEL_OPENAI", ""),
            "anthropic_model": env.get("LLM_MODEL_ANTHROPIC", ""),
            "ollama_model": env.get("OLLAMA_MODEL", ""),
            "openrouter_key_set": bool(env.get("OPENROUTER_API_KEY")),
            "openai_key_set": bool(env.get("OPENAI_API_KEY")),
            "anthropic_key_set": bool(env.get("ANTHROPIC_API_KEY")),
        },
        "ci": {
            "webhook_token": env.get("CI_WEBHOOK_TOKEN", ""),
        },
    }


class IntegrationSettingsUpdate(BaseModel):
    # Linear
    linear_api_key: Optional[str] = None
    linear_team_id: Optional[str] = None
    # Resend
    resend_api_key: Optional[str] = None
    email_from: Optional[str] = None
    email_alert_to: Optional[str] = None
    # Slack
    slack_webhook_url: Optional[str] = None
    # LLM
    llm_provider: Optional[str] = None
    llm_model_openrouter: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    # CI
    ci_webhook_token: Optional[str] = None


@app.patch("/api/settings/integrations")
def update_integration_settings(body: IntegrationSettingsUpdate, user: dict = Depends(get_current_user)):
    """
    Persist integration settings to backend/.env AND into os.environ in-process.

    All changes take effect immediately for the next test run — no restart needed.
    get_llm() reads os.environ fresh on every run, so LLM key/provider switches
    are live as soon as this endpoint returns.

    Empty string = clear the value. None = leave unchanged.
    """
    field_map = {
        "linear_api_key": "LINEAR_API_KEY",
        "linear_team_id": "LINEAR_TEAM_ID",
        "resend_api_key": "RESEND_API_KEY",
        "email_from": "EMAIL_FROM",
        "email_alert_to": "EMAIL_ALERT_TO",
        "slack_webhook_url": "SLACK_WEBHOOK_URL",
        "llm_provider": "LLM_PROVIDER",
        "llm_model_openrouter": "LLM_MODEL_OPENROUTER",
        "openrouter_api_key": "OPENROUTER_API_KEY",
        "openai_api_key": "OPENAI_API_KEY",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "ci_webhook_token": "CI_WEBHOOK_TOKEN",
    }

    updates: dict[str, str] = {}
    for field, env_key in field_map.items():
        val = getattr(body, field)
        if val is not None:  # None = skip; "" = clear
            updates[env_key] = val

    if not updates:
        return {"message": "Nothing to update", "updated": []}

    # 1. Persist to .env so changes survive a restart
    _write_env_file(updates)

    # 2. Apply immediately to os.environ so the running process picks them up
    #    right now — no restart needed. get_llm(), slack_client, linear_client,
    #    and all integrations read settings via os.getenv() at call time.
    for env_key, val in updates.items():
        if val:
            os.environ[env_key] = val
        elif env_key in os.environ:
            del os.environ[env_key]

    logger.info(
        "Integration settings updated live (no restart needed): %s",
        list(updates.keys()),
    )

    return {
        "message": "Settings saved and active immediately.",
        "updated": list(updates.keys()),
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Dashboard health overview — test cases with run history
# ---------------------------------------------------------------------------
@app.get("/api/dashboard/health")
def dashboard_health(
    limit: int = 14,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    owner = user["sub"]
    result = []

    # 1. Test cases that have associated runs
    cases = (
        db.query(TestCase)
        .filter(TestCase.owner_id == owner)
        .order_by(TestCase.created_at.asc())
        .all()
    )
    for tc in cases:
        runs = (
            db.query(TestRun)
            .filter(TestRun.test_case_id == tc.id, TestRun.owner_id == owner)
            .order_by(TestRun.created_at.desc())
            .limit(limit)
            .all()
        )
        runs_data = [
            {
                "job_id": r.job_id,
                "status": r.status.value,
                "is_successful": r.is_successful,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "duration_seconds": r.duration_seconds,
            }
            for r in reversed(runs)
        ]
        last = runs[0] if runs else None
        total = len(runs)
        passed = sum(1 for r in runs if r.is_successful is True)
        result.append({
            "id": tc.id,
            "name": tc.name,
            "target_url": tc.target_url,
            "last_status": last.status.value if last else None,
            "last_successful": last.is_successful if last else None,
            "pass_rate": round(passed * 100 / total) if total > 0 else None,
            "total_runs": total,
            "runs": runs_data,
        })

    # 2. Ad-hoc runs (no test_case_id) — group by name, show as anonymous rows
    adhoc_runs = (
        db.query(TestRun)
        .filter(
            TestRun.owner_id == owner,
            TestRun.test_case_id.is_(None),
        )
        .order_by(TestRun.created_at.desc())
        .limit(limit * 5)  # fetch more to group
        .all()
    )

    # Group by name
    from collections import defaultdict
    adhoc_groups: dict = defaultdict(list)
    for r in adhoc_runs:
        adhoc_groups[r.name].append(r)

    for name, group_runs in adhoc_groups.items():
        # Keep only the most recent `limit` runs per group
        group_runs = sorted(group_runs, key=lambda r: r.created_at or datetime.min)[-limit:]
        runs_data = [
            {
                "job_id": r.job_id,
                "status": r.status.value,
                "is_successful": r.is_successful,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "duration_seconds": r.duration_seconds,
            }
            for r in group_runs
        ]
        last = group_runs[-1]
        total = len(group_runs)
        passed = sum(1 for r in group_runs if r.is_successful is True)
        result.append({
            "id": None,
            "name": name,
            "target_url": last.target_url,
            "last_status": last.status.value,
            "last_successful": last.is_successful,
            "pass_rate": round(passed * 100 / total) if total > 0 else None,
            "total_runs": total,
            "runs": runs_data,
        })

    return result


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    model = (
        settings.LLM_MODEL_OPENROUTER if settings.LLM_PROVIDER == "openrouter"
        else settings.LLM_MODEL_OPENAI if settings.LLM_PROVIDER == "openai"
        else settings.LLM_MODEL_ANTHROPIC if settings.LLM_PROVIDER == "anthropic"
        else settings.OLLAMA_MODEL if settings.LLM_PROVIDER == "ollama"
        else "unknown"
    )
    return {"status": "ok", "llm_provider": settings.LLM_PROVIDER, "llm_model": model}


@app.post("/api/settings/llm/test-connection")
async def test_llm_connection(user: dict = Depends(get_current_user)):
    """
    Validate the currently configured LLM provider and API key by making a
    lightweight live API call (no tokens consumed for OpenAI/OpenRouter/Anthropic).

    Returns:
        {"ok": bool, "provider": str, "model": str, "detail": str}
    """
    from .llm import _test_llm_connection
    result = await _test_llm_connection()
    return result


# ---------------------------------------------------------------------------
# Demo seed — pre-populate example test cases for investor demos
# ---------------------------------------------------------------------------
@app.post("/api/demo/seed", status_code=201)
def seed_demo_data(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """
    Idempotent per-user: creates example test cases for the calling user if they
    have none yet. Auth-required and owner-scoped so demo data belongs to the
    user who seeded it (not shared globally). Safe to call multiple times.
    """
    owner = user["sub"]
    existing = db.query(TestCase).filter(TestCase.owner_id == owner).count()
    if existing > 0:
        return {"message": f"Already seeded ({existing} cases exist)", "created": 0}

    demos = [
        TestCase(
            owner_id=owner,
            name="Checkout flow — add to cart",
            prompt=(
                "Go to the target URL (saucedemo.com). Log in with username "
                "'standard_user' and password 'secret_sauce'. Add the first product "
                "to the cart. Open the cart and verify the product appears with the "
                "correct name and price."
            ),
            target_url="https://www.saucedemo.com",
            success_criteria="Product is in the cart with a visible name and price.",
        ),
        TestCase(
            owner_id=owner,
            name="Checkout flow — complete order",
            prompt=(
                "Go to the target URL (saucedemo.com). Log in with username "
                "'standard_user' and password 'secret_sauce'. Add any product to the "
                "cart, proceed through checkout with first name 'Test', last name "
                "'User', zip '12345', and complete the order. Verify the order "
                "confirmation message appears."
            ),
            target_url="https://www.saucedemo.com",
            success_criteria="Order confirmation ('Thank you for your order') is shown.",
        ),
        TestCase(
            owner_id=owner,
            name="Login — invalid credentials rejected",
            prompt=(
                "Go to the target URL (saucedemo.com). Attempt to log in with "
                "username 'locked_out_user' and password 'secret_sauce'. "
                "Verify that an error message is shown and login is blocked."
            ),
            target_url="https://www.saucedemo.com",
            success_criteria="An error message is displayed and the user is not logged in.",
        ),
    ]

    for tc in demos:
        db.add(tc)
    db.commit()

    return {"message": "Demo data seeded successfully", "created": len(demos)}


# ---------------------------------------------------------------------------
# Test Cases CRUD
# ---------------------------------------------------------------------------
@app.post("/api/test-cases", response_model=TestCaseOut)
def create_test_case(body: TestCaseCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    tc = TestCase(**body.model_dump(), owner_id=user["sub"])
    db.add(tc)
    db.commit()
    db.refresh(tc)
    return tc


@app.get("/api/test-cases", response_model=list[TestCaseOut])
def list_test_cases(
    suite_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    q = db.query(TestCase).filter(TestCase.owner_id == user["sub"])
    if suite_id:
        q = q.filter(TestCase.suite_id == suite_id)
    return q.order_by(TestCase.created_at.desc()).offset(skip).limit(limit).all()


@app.get("/api/test-cases/{id}", response_model=TestCaseOut)
def get_test_case(id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    tc = db.query(TestCase).filter(TestCase.id == id, TestCase.owner_id == user["sub"]).first()
    if not tc:
        raise HTTPException(404, "Test case not found")
    return tc


@app.put("/api/test-cases/{id}", response_model=TestCaseOut)
def update_test_case(
    id: int,
    body: TestCaseUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    tc = db.query(TestCase).filter(TestCase.id == id, TestCase.owner_id == user["sub"]).first()
    if not tc:
        raise HTTPException(404, "Test case not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tc, field, value)
    db.commit()
    db.refresh(tc)
    return tc


@app.delete("/api/test-cases/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_case(id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    tc = db.query(TestCase).filter(TestCase.id == id, TestCase.owner_id == user["sub"]).first()
    if not tc:
        raise HTTPException(404, "Test case not found")
    db.delete(tc)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Test Suites CRUD
# ---------------------------------------------------------------------------
@app.post("/api/test-suites", response_model=TestSuiteOut)
def create_suite(body: TestSuiteCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    s = TestSuite(**body.model_dump(), owner_id=user["sub"])
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@app.get("/api/test-suites", response_model=list[TestSuiteOut])
def list_suites(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return (
        db.query(TestSuite).filter(TestSuite.owner_id == user["sub"])
        .order_by(TestSuite.created_at.desc())
        .offset(skip).limit(limit).all()
    )


@app.get("/api/test-suites/{id}", response_model=TestSuiteOut)
def get_suite(id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    s = db.query(TestSuite).filter(TestSuite.id == id, TestSuite.owner_id == user["sub"]).first()
    if not s:
        raise HTTPException(404, "Suite not found")
    return s


@app.put("/api/test-suites/{id}", response_model=TestSuiteOut)
def update_suite(id: int, body: TestSuiteUpdate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    s = db.query(TestSuite).filter(TestSuite.id == id, TestSuite.owner_id == user["sub"]).first()
    if not s:
        raise HTTPException(404, "Suite not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return s


@app.delete("/api/test-suites/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suite(id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    s = db.query(TestSuite).filter(TestSuite.id == id, TestSuite.owner_id == user["sub"]).first()
    if not s:
        raise HTTPException(404, "Suite not found")
    db.delete(s)
    db.commit()
    return None


@app.post("/api/test-suites/{id}/run", response_model=TestSuiteRunResponse)
def run_suite(
    id: int,
    use_vision: bool = True,
    max_steps: int = 50,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    suite = db.query(TestSuite).filter(TestSuite.id == id, TestSuite.owner_id == user["sub"]).first()
    if not suite:
        raise HTTPException(404, "Suite not found")

    cases = db.query(TestCase).filter(TestCase.suite_id == id).all()
    if not cases:
        raise HTTPException(400, "Suite has no test cases — add test cases first.")

    job_ids: list[str] = []
    for tc in cases:
        job_id = uuid.uuid4().hex
        run_name = f"[Suite] {suite.name} — {tc.name}"
        run = TestRun(
            job_id=job_id,
            owner_id=user["sub"],
            test_case_id=tc.id,
            name=run_name,
            prompt=tc.prompt,
            target_url=tc.target_url,
            success_criteria=tc.success_criteria,
            status=TestRunStatus.PENDING,
        )
        db.add(run)
        db.flush()
        task_id = _dispatch_run_task(
            job_id=job_id,
            name=run_name,
            prompt=tc.prompt,
            target_url=tc.target_url or "",
            success_criteria=tc.success_criteria,
            use_vision=use_vision,
            max_steps=max_steps,
            test_case_id=tc.id,
        )
        run.task_id = task_id
        job_ids.append(job_id)

    db.commit()
    return TestSuiteRunResponse(
        message=f"Enqueued {len(job_ids)} test run(s) for suite '{suite.name}'.",
        suite_id=suite.id,
        count=len(job_ids),
        job_ids=job_ids,
    )


# ---------------------------------------------------------------------------
# Test Run Enqueue + Poll (THE CORE FLOW)
# ---------------------------------------------------------------------------
@app.post("/api/tests/run", response_model=TestRunEnqueueResponse)
def enqueue_test(body: TestRunRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    job_id = uuid.uuid4().hex
    run_name = body.name or (body.prompt[:60].strip() or f"Run {job_id[:8]}")
    owner_id = user["sub"]

    prompt = body.prompt
    target_url = body.target_url
    success_criteria = body.success_criteria
    test_case_id = body.test_case_id
    if test_case_id:
        tc = db.query(TestCase).filter(TestCase.id == test_case_id, TestCase.owner_id == owner_id).first()
        if tc:
            prompt = prompt or tc.prompt
            target_url = target_url or tc.target_url
            success_criteria = success_criteria or tc.success_criteria
            if not body.name:
                run_name = tc.name

    run = TestRun(
        job_id=job_id,
        task_id=None,
        owner_id=owner_id,
        test_case_id=test_case_id,
        name=run_name,
        prompt=prompt,
        target_url=target_url,
        success_criteria=success_criteria,
        status=TestRunStatus.PENDING,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    task_id = _dispatch_run_task(
        job_id=job_id,
        name=run_name,
        prompt=prompt,
        target_url=target_url or "",
        success_criteria=success_criteria,
        use_vision=bool(body.use_vision),
        max_steps=body.max_steps if body.max_steps is not None else 50,
        test_case_id=test_case_id,
    )
    run.task_id = task_id
    db.commit()

    return {"job_id": job_id, "task_id": task_id, "status": TestRunStatus.PENDING.value}


# ---------------------------------------------------------------------------
# Ownership helper — enforce tenant isolation on TestRun lookups
# ---------------------------------------------------------------------------
def _get_owned_run(
    db: Session,
    job_id: str,
    user: Optional[dict],
) -> "TestRun":
    """
    Fetch a TestRun by job_id and enforce ownership.

    Authorization rule:
      - If the run has an owner_id set, it MUST match the authenticated user's
        `sub` claim. Otherwise → 404 (we return 404, not 403, so we don't leak
        the existence of other tenants' runs).
      - Legacy runs with owner_id = NULL (created before auth was introduced)
        are accessible to any authenticated user — grandfathered so the fix
        doesn't break existing data. These should be migrated/backfilled later.
      - `user` may be None only for trusted internal calls (never from a route
        that lacks the auth dependency).

    Raises 404 if the run doesn't exist or the caller doesn't own it.
    """
    run = db.query(TestRun).filter(TestRun.job_id == job_id).first()
    if not run:
        raise HTTPException(404, "Job not found")

    # Enforce ownership only when we have both an authenticated user and an
    # owner on the record. NULL-owner legacy rows remain accessible.
    if user is not None and run.owner_id and run.owner_id != user.get("sub"):
        # Return 404 (not 403) to avoid leaking that the run exists.
        raise HTTPException(404, "Job not found")

    return run


@app.get("/api/tests/status/{job_id}", response_model=TestRunStatusResponse)
def get_run_status(
    job_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    run = _get_owned_run(db, job_id, user)

    # Merge live Celery state if task_id exists and task is not terminal
    stage: Optional[str] = None
    progress: Optional[dict] = None
    if run.task_id and run.status in (TestRunStatus.PENDING, TestRunStatus.RUNNING):
        try:
            result = AsyncResult(run.task_id, app=celery_app)
            if result.state == "STARTED":
                stage = "worker_started"
            elif result.state == "PROGRESS":
                info = result.info if isinstance(result.info, dict) else {}
                stage = info.get("stage", "running_agent")
                progress = info
                current_step = info.get("step")
                total = info.get("total")
                if isinstance(current_step, int) and isinstance(total, int) and total:
                    progress["pct"] = round(current_step * 100 / max(total, 1), 1)
            elif result.state == "FAILURE":
                if run.status != TestRunStatus.FAILED:
                    run.status = TestRunStatus.FAILED
                    run.error_message = str(result.info)
                    run.completed_at = datetime.utcnow()
                    run.is_successful = False
                    db.commit()
            elif result.state == "SUCCESS" and run.status in (
                TestRunStatus.PENDING,
                TestRunStatus.RUNNING,
            ):
                db.refresh(run)
        except Exception:
            pass

    screenshots = (
        db.query(TestScreenshot)
        .filter(TestScreenshot.test_run_id == run.id)
        .order_by(TestScreenshot.step_index.asc(), TestScreenshot.created_at.asc())
        .all()
    )

    return TestRunStatusResponse(
        job_id=run.job_id,
        task_id=run.task_id,
        status=run.status,
        name=run.name,
        prompt=run.prompt,
        target_url=run.target_url,
        stage=stage,
        progress=progress,
        total_steps=run.total_steps,
        duration_seconds=run.duration_seconds,
        result_summary=run.result_summary,
        final_result=run.final_result,
        error_message=run.error_message,
        steps_log=run.steps_log,
        visited_urls=run.visited_urls,
        live_steps=run.live_steps,
        is_successful=run.is_successful,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        screenshots=[ScreenshotOut.model_validate(s) for s in screenshots],
    )


@app.get("/api/tests", response_model=list[TestRunListResponse])
def list_runs(
    status: Optional[TestRunStatus] = None,
    test_case_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    q = db.query(TestRun).filter(TestRun.owner_id == user["sub"])
    if status:
        q = q.filter(TestRun.status == status)
    if test_case_id:
        q = q.filter(TestRun.test_case_id == test_case_id)
    rows = q.order_by(TestRun.created_at.desc()).offset(skip).limit(limit).all()
    return [
        TestRunListResponse(
            job_id=r.job_id, name=r.name, status=r.status,
            is_successful=r.is_successful, duration_seconds=r.duration_seconds,
            has_visual_proof=r.has_visual_proof or False,
            created_at=r.created_at, completed_at=r.completed_at,
        )
        for r in rows
    ]


@app.get("/api/tests/{job_id}", response_model=TestRunStatusResponse)
def get_run_detail(job_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return get_run_status(job_id, db=db, user=user)


@app.post("/api/tests/{job_id}/cancel", response_model=TestRunStatusResponse)
def cancel_run(job_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """
    Cancel a pending or running test run.
    For sync_demo mode this marks the DB record cancelled immediately.
    For celery mode it also revokes the task from the broker queue.
    """
    run = _get_owned_run(db, job_id, user)

    if run.status not in (TestRunStatus.PENDING, TestRunStatus.RUNNING):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot cancel a run in '{run.status.value}' state.",
        )

    # Attempt broker-level revoke (no-op if no broker / sync_demo mode)
    if run.task_id and settings.RUN_MODE == "celery":
        try:
            from celery.app.control import Control
            ctrl = Control(app=celery_app)
            ctrl.revoke(run.task_id, terminate=True, signal="SIGTERM")
        except Exception:
            pass  # revoke failure must never block the DB update

    run.status = TestRunStatus.CANCELLED
    run.completed_at = datetime.utcnow()
    run.is_successful = False
    if not run.error_message:
        run.error_message = "Cancelled by user."
    db.commit()

    return get_run_status(job_id, db=db, user=user)


# ---------------------------------------------------------------------------
# Screenshot file serving
# ---------------------------------------------------------------------------
SCREENSHOT_ROOT = os.path.abspath(settings.SCREENSHOT_DIR)


@app.get("/api/screenshots/{screenshot_id}")
def get_screenshot(
    screenshot_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Serve a screenshot image — auth-gated and tenant-scoped.

    A screenshot belongs to a TestRun. We resolve the parent run and enforce
    the same ownership rule as _get_owned_run: if the run has an owner_id, it
    must match the caller. Legacy NULL-owner runs remain accessible.
    Returns 404 (not 403) on ownership mismatch so we don't leak existence.
    """
    shot = db.query(TestScreenshot).filter(TestScreenshot.id == screenshot_id).first()
    if not shot:
        raise HTTPException(404, "Screenshot not found")

    # Resolve parent run and enforce ownership
    run = db.query(TestRun).filter(TestRun.id == shot.test_run_id).first()
    if not run:
        raise HTTPException(404, "Screenshot not found")
    if run.owner_id and run.owner_id != user.get("sub"):
        raise HTTPException(404, "Screenshot not found")

    # file_path is stored relative to the parent of SCREENSHOT_ROOT, or absolute
    if os.path.isabs(shot.file_path):
        full_path = shot.file_path
    else:
        full_path = os.path.normpath(os.path.join(os.path.dirname(SCREENSHOT_ROOT), shot.file_path))

    # Defense-in-depth: ensure the resolved path stays within SCREENSHOT_ROOT
    # (prevents path traversal if a malformed file_path ever gets persisted).
    _root = os.path.abspath(os.path.dirname(SCREENSHOT_ROOT))
    if not os.path.abspath(full_path).startswith(_root):
        raise HTTPException(404, "Screenshot not found")

    if not os.path.isfile(full_path):
        raise HTTPException(404, "Screenshot file missing on disk")

    return FileResponse(full_path, media_type="image/png")


# ---------------------------------------------------------------------------
# CI Webhook (GitHub Actions etc.)
# ---------------------------------------------------------------------------
@app.post("/api/webhooks/ci", response_model=CIWebhookResponse)
def ci_webhook(
    body: CIWebhookRequest,
    x_ci_token: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    # Two accepted auth modes:
    #   1. External CI systems (GitHub Actions) send X-CI-Token = CI_WEBHOOK_TOKEN.
    #   2. The dashboard "trigger now" button sends the logged-in user's Supabase
    #      JWT as a Bearer token. We verify it and scope created runs to that user.
    # This means the CI secret NEVER needs to ship to the browser.
    caller_owner_id: Optional[str] = None
    authorized = False

    bearer_token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization.split(" ", 1)[1].strip()

    # Mode 1: CI token (header or bearer) matches the configured secret
    if x_ci_token and x_ci_token == settings.CI_WEBHOOK_TOKEN:
        authorized = True
    elif bearer_token and bearer_token == settings.CI_WEBHOOK_TOKEN:
        authorized = True
    # Mode 2: valid Supabase user JWT (dashboard-triggered)
    elif bearer_token:
        try:
            from .auth import verify_token
            claims = verify_token(bearer_token)
            caller_owner_id = claims.get("sub")
            authorized = bool(caller_owner_id)
        except Exception:
            authorized = False

    if not authorized:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid CI webhook token or user session.",
        )

    # Gather test case IDs
    ids = list(body.test_case_ids or [])
    if body.suite_id:
        suite_cases = (
            db.query(TestCase).filter(TestCase.suite_id == body.suite_id).all()
        )
        ids.extend(tc.id for tc in suite_cases)

    ids = list(set(ids))
    if not ids:
        raise HTTPException(400, "No test cases to run (suite_id empty or no test_case_ids)")

    job_ids: list[str] = []
    for tc_id in ids:
        tc = db.query(TestCase).filter(TestCase.id == tc_id).first()
        if not tc:
            continue
        job_id = uuid.uuid4().hex
        run = TestRun(
            job_id=job_id,
            owner_id=caller_owner_id or tc.owner_id,
            test_case_id=tc.id,
            name=f"[CI] {tc.name}",
            prompt=tc.prompt,
            target_url=tc.target_url,
            success_criteria=tc.success_criteria,
            status=TestRunStatus.PENDING,
        )
        db.add(run)
        db.flush()
        task_id = _dispatch_run_task(
            job_id=job_id,
            name=run.name,
            prompt=tc.prompt,
            target_url=tc.target_url or "",
            success_criteria=tc.success_criteria,
            use_vision=True,
            max_steps=50,
            test_case_id=tc.id,
        )
        run.task_id = task_id
        job_ids.append(job_id)

    db.commit()
    return CIWebhookResponse(
        message=f"Enqueued {len(job_ids)} test run(s) from CI.",
        job_ids=job_ids,
    )


# ---------------------------------------------------------------------------
# Linear Integration
# ---------------------------------------------------------------------------
@app.post("/api/integrations/linear/issue", response_model=LinearTicketResponse)
def create_linear_ticket(body: CreateLinearTicketRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    run = _get_owned_run(db, body.job_id, user)

    screenshots = (
        db.query(TestScreenshot)
        .filter(TestScreenshot.test_run_id == run.id)
        .order_by(TestScreenshot.step_index.asc())
        .all()
    )
    shot_count = len(screenshots)

    title = body.title or (
        f"[QA FAILURE] {run.name} — {run.job_id[:8]}"
    )
    description = body.description or (
        f"### Test run failed\n\n"
        f"- **Name:** {run.name}\n"
        f"- **Job ID:** `{run.job_id}`\n"
        f"- **Target URL:** {run.target_url or 'N/A'}\n"
        f"- **Duration:** {run.duration_seconds or 0}s over {run.total_steps or 0} steps\n"
        f"- **Success criteria:** {run.success_criteria or 'N/A'}\n\n"
        f"### Prompt executed\n\n```\n{run.prompt}\n```\n\n"
        f"### Agent result\n\n```\n{run.final_result or '(empty)'}\n```\n\n"
        f"### Error\n\n```\n{run.error_message or '(none)'}\n```\n\n"
        f"Screenshots captured: {shot_count}. "
        f"View failure screenshots in the Leaka AI dashboard (job {run.job_id})."
    )

    existing = db.query(LinearIssue).filter(LinearIssue.test_run_id == run.id).first()
    if existing:
        return LinearTicketResponse(
            success=True,
            issue_id=existing.issue_id,
            identifier=existing.identifier,
            title=existing.title,
        )

    result = linear_client.create_issue(title=title, description_md=description)
    if not result.get("success"):
        return LinearTicketResponse(success=False)

    issue = LinearIssue(
        test_run_id=run.id,
        issue_id=result["issue_id"],
        identifier=result.get("identifier"),
        title=result.get("title") or title,
        url=result.get("url"),
    )
    db.add(issue)
    db.commit()
    return LinearTicketResponse(
        success=True,
        issue_id=issue.issue_id,
        identifier=issue.identifier,
        title=issue.title,
    )


# ---------------------------------------------------------------------------
# Resend Email Alert
# ---------------------------------------------------------------------------
@app.post("/api/integrations/email/alert-failure/{job_id}")
def email_failure_alert(
    job_id: str,
    dashboard_base_url: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    run = _get_owned_run(db, job_id, user)

    shots = (
        db.query(TestScreenshot)
        .filter(
            TestScreenshot.test_run_id == run.id,
            TestScreenshot.is_failure_point == True,
        )
        .order_by(TestScreenshot.step_index.desc())
        .all()
    )
    if not shots:
        shots = (
            db.query(TestScreenshot)
            .filter(TestScreenshot.test_run_id == run.id)
            .order_by(TestScreenshot.step_index.desc())
            .limit(1)
            .all()
        )

    screenshot_path = None
    if shots:
        fp = shots[0].file_path
        screenshot_path = fp if os.path.isabs(fp) else os.path.normpath(
            os.path.join(os.path.dirname(SCREENSHOT_ROOT), fp)
        )
        if not os.path.isfile(screenshot_path):
            screenshot_path = None

    steps_summary = run.steps_log or "(steps log unavailable)"
    dashboard_url = None
    if dashboard_base_url:
        dashboard_url = f"{dashboard_base_url.rstrip('/')}/runs/{job_id}"

    result = email_client.send_test_failure_alert(
        test_name=run.name,
        job_id=job_id,
        steps_summary=steps_summary,
        screenshot_path=screenshot_path,
        dashboard_url=dashboard_url,
    )
    return {"sent": True, "result": result}


# ---------------------------------------------------------------------------
# Slack Webhook Alert
# ---------------------------------------------------------------------------
@app.post("/api/integrations/slack/alert-failure/{job_id}")
def slack_failure_alert(
    job_id: str,
    dashboard_base_url: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    run = _get_owned_run(db, job_id, user)

    cfg = db.query(UserSettings).filter(UserSettings.owner_id == user["sub"]).first()
    webhook = (cfg.slack_webhook_url if cfg else None) or settings.SLACK_WEBHOOK_URL
    if not webhook:
        raise HTTPException(400, "No Slack webhook URL configured.")

    dash_base = (
        (cfg.dashboard_base_url if cfg and cfg.dashboard_base_url else None)
        or (dashboard_base_url.strip() if dashboard_base_url else None)
        or settings.DASHBOARD_BASE_URL
    )

    lin = db.query(LinearIssue).filter(LinearIssue.test_run_id == run.id).first()

    # Reuse the same incident builder as the worker auto-alert path
    from .worker import _build_incident_context

    ctx = _build_incident_context(
        name=run.name,
        job_id=job_id,
        prompt=run.prompt,
        target_url=run.target_url,
        success_criteria=run.success_criteria,
        steps_log_json=run.steps_log or "[]",
        final_result_text=run.final_result,
        error_message=run.error_message,
        total_steps_count=run.total_steps or 0,
        duration=run.duration_seconds or 0,
        screenshots_persisted=[],
        final_failure_shot_rel=None,
        completed_at=run.completed_at or datetime.utcnow(),
        dashboard_base_url=dash_base,
        linear_issue_url=lin.url if lin else None,
        linear_identifier=lin.identifier if lin else None,
    )
    result = slack_client.send_qa_incident(webhook_url=webhook, **ctx)
    return {"sent": bool(result.get("ok")), "result": result}


# ---------------------------------------------------------------------------
# Per-user Slack settings (stored in DB, per Supabase user)
# ---------------------------------------------------------------------------


class SlackSettingsBody(BaseModel):
    slack_webhook_url: Optional[str] = None       # empty string = clear
    slack_auto_alert_on_failure: Optional[bool] = None
    dashboard_base_url: Optional[str] = None


@app.get("/api/user/slack-settings")
def get_user_slack_settings(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    owner = user["sub"]
    cfg = db.query(UserSettings).filter(UserSettings.owner_id == owner).first()
    if not cfg:
        return {
            "slack_webhook_url_set": False,
            "slack_webhook_url_masked": "",
            "slack_auto_alert_on_failure": True,
            "dashboard_base_url": "",
        }
    masked = ""
    if cfg.slack_webhook_url:
        masked = cfg.slack_webhook_url[:34] + "…" if len(cfg.slack_webhook_url) > 34 else cfg.slack_webhook_url
    return {
        "slack_webhook_url_set": bool(cfg.slack_webhook_url),
        "slack_webhook_url_masked": masked,
        "slack_auto_alert_on_failure": cfg.slack_auto_alert_on_failure,
        "dashboard_base_url": cfg.dashboard_base_url or "",
    }


@app.patch("/api/user/slack-settings")
def update_user_slack_settings(
    body: SlackSettingsBody,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    owner = user["sub"]
    cfg = db.query(UserSettings).filter(UserSettings.owner_id == owner).first()
    if not cfg:
        cfg = UserSettings(owner_id=owner)
        db.add(cfg)

    if body.slack_webhook_url is not None:
        cfg.slack_webhook_url = body.slack_webhook_url or None  # "" → None (clear)
    if body.slack_auto_alert_on_failure is not None:
        cfg.slack_auto_alert_on_failure = body.slack_auto_alert_on_failure
    if body.dashboard_base_url is not None:
        cfg.dashboard_base_url = body.dashboard_base_url.strip() or None

    db.commit()
    return {"message": "Slack settings saved.", "auto_alert": cfg.slack_auto_alert_on_failure}


@app.post("/api/user/slack-settings/test-ping")
def test_slack_ping(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Send a test ping to verify the webhook URL is working."""
    owner = user["sub"]
    cfg = db.query(UserSettings).filter(UserSettings.owner_id == owner).first()
    webhook = (cfg and cfg.slack_webhook_url) or settings.SLACK_WEBHOOK_URL
    if not webhook:
        raise HTTPException(400, "No Slack webhook URL configured.")

    import requests as _req
    payload = {
        "text": "✅ *Leaka AI — Slack connection verified.*\nYou'll receive QA incident alerts here when tests fail.",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "✅ *Leaka AI — Slack connection verified.*\nYou'll receive QA incident alerts here when tests fail.",
                },
            }
        ],
    }
    try:
        resp = _req.post(webhook, json=payload, timeout=10)
        if 200 <= resp.status_code < 300:
            return {"ok": True, "message": "Test ping sent successfully."}
        return {"ok": False, "message": f"Slack returned HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as exc:
        return {"ok": False, "message": f"Request failed: {exc}"}


# ---------------------------------------------------------------------------
# Onboarding state — track whether user has completed the onboarding flow
# ---------------------------------------------------------------------------

@app.get("/api/user/onboarding")
def get_onboarding_status(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return whether the current user has completed onboarding."""
    owner = user["sub"]
    cfg = db.query(UserSettings).filter(UserSettings.owner_id == owner).first()
    completed = bool(cfg and cfg.onboarding_completed)
    return {"onboarding_completed": completed}


@app.post("/api/user/onboarding/complete")
def complete_onboarding(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Mark onboarding as complete for the current user."""
    owner = user["sub"]
    cfg = db.query(UserSettings).filter(UserSettings.owner_id == owner).first()
    if not cfg:
        cfg = UserSettings(owner_id=owner)
        db.add(cfg)
    cfg.onboarding_completed = True
    db.commit()
    return {"onboarding_completed": True}
