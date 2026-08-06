import os
import uuid
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
from sqlalchemy.orm import Session

from .celery_app import celery_app
from .config import settings
from .database import get_db, init_db
from .integrations import linear_client, email_client
from .models import (
    LinearIssue,
    TestCase,
    TestRun,
    TestRunStatus,
    TestScreenshot,
    TestSuite,
)
from .schemas import (
    CIWebhookRequest,
    CIWebhookResponse,
    CreateLinearTicketRequest,
    LinearTicketResponse,
    ScreenshotOut,
    TestCaseCreate,
    TestCaseOut,
    TestRunEnqueueResponse,
    TestRunListResponse,
    TestRunRequest,
    TestRunStatusResponse,
    TestSuiteCreate,
    TestSuiteOut,
)
from .worker import run_browser_test


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


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "llm_provider": settings.LLM_PROVIDER}


# ---------------------------------------------------------------------------
# Test Cases CRUD
# ---------------------------------------------------------------------------
@app.post("/api/test-cases", response_model=TestCaseOut)
def create_test_case(body: TestCaseCreate, db: Session = Depends(get_db)):
    tc = TestCase(**body.model_dump())
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
):
    q = db.query(TestCase)
    if suite_id:
        q = q.filter(TestCase.suite_id == suite_id)
    return q.order_by(TestCase.created_at.desc()).offset(skip).limit(limit).all()


@app.get("/api/test-cases/{id}", response_model=TestCaseOut)
def get_test_case(id: int, db: Session = Depends(get_db)):
    tc = db.query(TestCase).filter(TestCase.id == id).first()
    if not tc:
        raise HTTPException(404, "Test case not found")
    return tc


# ---------------------------------------------------------------------------
# Test Suites CRUD
# ---------------------------------------------------------------------------
@app.post("/api/test-suites", response_model=TestSuiteOut)
def create_suite(body: TestSuiteCreate, db: Session = Depends(get_db)):
    s = TestSuite(**body.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@app.get("/api/test-suites", response_model=list[TestSuiteOut])
def list_suites(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(TestSuite)
        .order_by(TestSuite.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@app.get("/api/test-suites/{id}", response_model=TestSuiteOut)
def get_suite(id: int, db: Session = Depends(get_db)):
    s = db.query(TestSuite).filter(TestSuite.id == id).first()
    if not s:
        raise HTTPException(404, "Suite not found")
    return s


# ---------------------------------------------------------------------------
# Test Run Enqueue + Poll (THE CORE FLOW)
# ---------------------------------------------------------------------------
@app.post("/api/tests/run", response_model=TestRunEnqueueResponse)
def enqueue_test(body: TestRunRequest, db: Session = Depends(get_db)):
    job_id = uuid.uuid4().hex
    run_name = body.name or (body.prompt[:60].strip() or f"Run {job_id[:8]}")

    # Resolve full prompt + target_url from test_case_id if given
    prompt = body.prompt
    target_url = body.target_url
    success_criteria = body.success_criteria
    test_case_id = body.test_case_id
    if test_case_id:
        tc = db.query(TestCase).filter(TestCase.id == test_case_id).first()
        if tc:
            prompt = prompt or tc.prompt
            target_url = target_url or tc.target_url
            success_criteria = success_criteria or tc.success_criteria
            if not body.name:
                run_name = tc.name

    # Create DB record (PENDING)
    run = TestRun(
        job_id=job_id,
        task_id=None,
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

    # Enqueue to Celery
    task = run_browser_test.delay(
        job_id=job_id,
        name=run_name,
        prompt=prompt,
        target_url=target_url,
        success_criteria=success_criteria,
        use_vision=bool(body.use_vision),
        max_steps=body.max_steps or 100,
        test_case_id=test_case_id,
    )

    # Update with celery task_id so we can poll via Celery too
    run.task_id = task.id
    db.commit()

    return {
        "job_id": job_id,
        "task_id": task.id,
        "status": TestRunStatus.PENDING.value,
    }


@app.get("/api/tests/status/{job_id}", response_model=TestRunStatusResponse)
def get_run_status(job_id: str, db: Session = Depends(get_db)):
    run = db.query(TestRun).filter(TestRun.job_id == job_id).first()
    if not run:
        raise HTTPException(404, "Job not found")

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
        stage=stage,
        progress=progress,
        total_steps=run.total_steps,
        duration_seconds=run.duration_seconds,
        result_summary=run.result_summary,
        final_result=run.final_result,
        error_message=run.error_message,
        is_successful=run.is_successful,
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
):
    q = db.query(TestRun)
    if status:
        q = q.filter(TestRun.status == status)
    if test_case_id:
        q = q.filter(TestRun.test_case_id == test_case_id)
    rows = (
        q.order_by(TestRun.created_at.desc()).offset(skip).limit(limit).all()
    )
    return [
        TestRunListResponse(
            job_id=r.job_id,
            name=r.name,
            status=r.status,
            is_successful=r.is_successful,
            duration_seconds=r.duration_seconds,
            has_visual_proof=r.has_visual_proof or False,
            created_at=r.created_at,
            completed_at=r.completed_at,
        )
        for r in rows
    ]


@app.get("/api/tests/{job_id}", response_model=TestRunStatusResponse)
def get_run_detail(job_id: str, db: Session = Depends(get_db)):
    return get_run_status(job_id, db=db)


# ---------------------------------------------------------------------------
# Screenshot file serving
# ---------------------------------------------------------------------------
SCREENSHOT_ROOT = os.path.abspath(settings.SCREENSHOT_DIR)


@app.get("/api/screenshots/{screenshot_id}")
def get_screenshot(screenshot_id: int, db: Session = Depends(get_db)):
    shot = db.query(TestScreenshot).filter(TestScreenshot.id == screenshot_id).first()
    if not shot:
        raise HTTPException(404, "Screenshot not found")

    # file_path is stored relative to the parent of SCREENSHOT_ROOT, or absolute
    if os.path.isabs(shot.file_path):
        full_path = shot.file_path
    else:
        full_path = os.path.normpath(os.path.join(os.path.dirname(SCREENSHOT_ROOT), shot.file_path))

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
    token = x_ci_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()

    if token != settings.CI_WEBHOOK_TOKEN:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid CI webhook token")

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
            test_case_id=tc.id,
            name=f"[CI] {tc.name}",
            prompt=tc.prompt,
            target_url=tc.target_url,
            success_criteria=tc.success_criteria,
            status=TestRunStatus.PENDING,
        )
        db.add(run)
        db.flush()
        task = run_browser_test.delay(
            job_id=job_id,
            name=run.name,
            prompt=tc.prompt,
            target_url=tc.target_url,
            success_criteria=tc.success_criteria,
            use_vision=True,
            max_steps=100,
            test_case_id=tc.id,
        )
        run.task_id = task.id
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
def create_linear_ticket(body: CreateLinearTicketRequest, db: Session = Depends(get_db)):
    run = db.query(TestRun).filter(TestRun.id == body.test_run_id).first()
    if not run:
        raise HTTPException(404, "Test run not found")

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
):
    run = db.query(TestRun).filter(TestRun.job_id == job_id).first()
    if not run:
        raise HTTPException(404, "Job not found")

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
