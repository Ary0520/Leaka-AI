from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field

from .models import TestRunStatus


# -------------- Test Cases --------------
class TestCaseBase(BaseModel):
    name: str
    prompt: str
    success_criteria: Optional[str] = None
    target_url: Optional[str] = None
    suite_id: Optional[int] = None


class TestCaseCreate(TestCaseBase):
    pass


class TestCaseOut(TestCaseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# -------------- Test Suites --------------
class TestSuiteBase(BaseModel):
    name: str
    description: Optional[str] = None


class TestSuiteCreate(TestSuiteBase):
    pass


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
    max_steps: Optional[int] = 100


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
    stage: Optional[str] = None
    progress: Optional[dict[str, Any]] = None
    total_steps: Optional[int] = None
    duration_seconds: Optional[int] = None
    result_summary: Optional[str] = None
    final_result: Optional[str] = None
    error_message: Optional[str] = None
    is_successful: Optional[bool] = None
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
    test_run_id: int
    title: Optional[str] = None
    description: Optional[str] = None


class LinearTicketResponse(BaseModel):
    success: bool
    issue_id: Optional[str] = None
    identifier: Optional[str] = None
    title: Optional[str] = None
