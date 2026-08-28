from datetime import datetime
from typing import Optional, List, Any, Literal
from pydantic import BaseModel, Field

from .models import TestRunStatus


# -------------- Assertions (deterministic test oracle) --------------
# Each assertion is checked in Python against the captured final DOM / URL
# after the agent finishes — independent of what the LLM claims.
AssertionType = Literal[
    "page_contains_text",
    "page_not_contains_text",
    "url_contains",
    "url_equals",
    "page_contains_regex",
]


class Assertion(BaseModel):
    type: AssertionType
    value: str = Field(..., min_length=1, description="Text / URL / regex to check")
    case_sensitive: bool = False


class AssertionResult(BaseModel):
    type: str
    value: str
    passed: bool
    detail: Optional[str] = None


# -------------- Test Cases --------------
class TestCaseBase(BaseModel):
    name: str
    prompt: str
    success_criteria: Optional[str] = None
    target_url: Optional[str] = None
    suite_id: Optional[int] = None
    assertions: Optional[List[Assertion]] = None


class TestCaseCreate(TestCaseBase):
    pass


class TestCaseUpdate(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    success_criteria: Optional[str] = None
    target_url: Optional[str] = None
    suite_id: Optional[int] = None
    assertions: Optional[List[Assertion]] = None


class TestCaseOut(BaseModel):
    id: int
    name: str
    prompt: str
    success_criteria: Optional[str] = None
    target_url: Optional[str] = None
    suite_id: Optional[int] = None
    # Stored as a JSON string in the DB column; exposed as a parsed list.
    assertions: Optional[List[Assertion]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        # When reading from the ORM object, `assertions` is a JSON string
        # (or None). Parse it into a list so the response is structured.
        if hasattr(obj, "assertions") and isinstance(getattr(obj, "assertions"), str):
            import json as _json
            try:
                parsed = _json.loads(obj.assertions)
            except Exception:
                parsed = None
            # Build a shallow copy dict for validation
            data = {
                "id": obj.id,
                "name": obj.name,
                "prompt": obj.prompt,
                "success_criteria": obj.success_criteria,
                "target_url": obj.target_url,
                "suite_id": obj.suite_id,
                "assertions": parsed,
                "created_at": obj.created_at,
                "updated_at": obj.updated_at,
            }
            return super().model_validate(data, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)


# -------------- Test Suites --------------
class TestSuiteBase(BaseModel):
    name: str
    description: Optional[str] = None


class TestSuiteCreate(TestSuiteBase):
    pass


class TestSuiteUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class TestSuiteRunResponse(BaseModel):
    message: str
    suite_id: int
    count: int
    job_ids: List[str]


class TestSuiteOut(TestSuiteBase):
    id: int
    created_at: datetime
    updated_at: datetime
    tests: List[TestCaseOut] = []

    class Config:
        from_attributes = True


# -------------- Screenshots --------------
class ScreenshotOut(BaseModel):
    id: int
    file_path: str
    url: Optional[str] = None
    caption: Optional[str] = None
    step_index: Optional[int] = None
    is_failure_point: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# -------------- Test Runs --------------
class TestRunRequest(BaseModel):
    name: Optional[str] = None
    prompt: str = Field(..., min_length=3, description="Natural language QA test steps")
    success_criteria: Optional[str] = None
    target_url: Optional[str] = None
    test_case_id: Optional[int] = None
    use_vision: Optional[bool] = True
    max_steps: Optional[int] = 50
    assertions: Optional[List[Assertion]] = None


class TestRunEnqueueResponse(BaseModel):
    job_id: str
    task_id: str
    status: str


class TestRunStatusResponse(BaseModel):
    job_id: str
    task_id: Optional[str]
    status: TestRunStatus
    name: str
    prompt: str
    target_url: Optional[str] = None
    stage: Optional[str] = None
    progress: Optional[dict[str, Any]] = None
    total_steps: Optional[int] = None
    duration_seconds: Optional[int] = None
    result_summary: Optional[str] = None
    final_result: Optional[str] = None
    error_message: Optional[str] = None
    steps_log: Optional[str] = None        # JSON string: list[dict] — agent action history
    visited_urls: Optional[str] = None     # JSON string: list[str]
    live_steps: Optional[str] = None       # JSON string: steps written live during run
    is_successful: Optional[bool] = None
    assertions: Optional[str] = None            # JSON string: the assertions requested
    assertion_results: Optional[str] = None     # JSON string: per-assertion pass/fail
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    screenshots: List[ScreenshotOut] = []


class TestRunListResponse(BaseModel):
    job_id: str
    name: str
    status: TestRunStatus
    is_successful: Optional[bool] = None
    duration_seconds: Optional[int] = None
    has_visual_proof: bool = False
    created_at: datetime
    completed_at: Optional[datetime] = None


# -------------- CI Webhook --------------
class CIWebhookRequest(BaseModel):
    suite_id: Optional[int] = None
    test_case_ids: Optional[List[int]] = None
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    triggered_by: Optional[str] = None


class CIWebhookResponse(BaseModel):
    message: str
    job_ids: List[str]


# -------------- Linear --------------
class CreateLinearTicketRequest(BaseModel):
    job_id: str
    title: Optional[str] = None
    description: Optional[str] = None


class LinearTicketResponse(BaseModel):
    success: bool
    issue_id: Optional[str] = None
    identifier: Optional[str] = None
    title: Optional[str] = None


# -------------- Application Intelligence (Explore Mode) --------------
from .models import ExploreRunStatus


class ApplicationCreate(BaseModel):
    name: str = Field(..., min_length=1)
    base_url: str = Field(..., min_length=3)
    description: Optional[str] = None
    login_hint: Optional[str] = None


class ApplicationUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    description: Optional[str] = None
    login_hint: Optional[str] = None


class ApplicationOut(BaseModel):
    id: int
    name: str
    base_url: str
    description: Optional[str] = None
    login_hint: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppMapNodeOut(BaseModel):
    id: int
    node_type: str
    label: str
    url: Optional[str] = None
    description: Optional[str] = None
    suggested_prompt: Optional[str] = None
    # Coverage cross-reference (filled in Stage C). None = not computed.
    is_covered: Optional[bool] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ExploreEnqueueResponse(BaseModel):
    job_id: str
    task_id: str
    status: str


class ExploreRunStatusResponse(BaseModel):
    job_id: str
    task_id: Optional[str] = None
    application_id: int
    status: ExploreRunStatus
    max_steps: Optional[int] = None
    nodes_found: Optional[int] = None
    result_summary: Optional[str] = None
    error_message: Optional[str] = None
    live_steps: Optional[str] = None
    visited_urls: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ApplicationMapResponse(BaseModel):
    application: ApplicationOut
    latest_explore: Optional[ExploreRunStatusResponse] = None
    nodes: List[AppMapNodeOut] = []
    total_nodes: int = 0
    covered_nodes: int = 0
