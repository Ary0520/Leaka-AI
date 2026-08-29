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
    # Optional authoritative coverage linkage (R4.3, R11.5): when a test is
    # generated from a graph node, the client passes these so the backend
    # records a CoverageLink. Both must be present to create a link; they are
    # NOT persisted on the TestCase itself.
    application_id: Optional[int] = None
    node_id: Optional[int] = None


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


# -------------- Application Graph (Layer 1) --------------
# JSON-shaped columns (semantics/risk/manual_overrides/provenance/diff_summary)
# are stored as Text (JSON strings) in the ORM; these schemas expose them as
# parsed objects for the client. Parsing is done in the endpoint layer.


class GraphNodeOut(BaseModel):
    id: int
    canonical_key: str
    node_type: str
    business_category: Optional[str] = None
    label: str
    url_pattern: Optional[str] = None
    role_association: Optional[str] = None
    dependencies_incomplete: bool = False
    status: str = "active"
    semantics: Optional[dict] = None
    risk: Optional[dict] = None
    manual_overrides: Optional[dict] = None
    # Coverage cross-reference (R4.1, R8.1): the node's latest stored
    # CoverageVerdict joined at read time so the graph view can color nodes by
    # coverage. None = no verdict computed yet (honest "undetermined").
    coverage_state: Optional[str] = None          # covered|partially_covered|uncovered
    coverage_confidence: Optional[float] = None    # [0.0, 1.0]
    first_seen_run: Optional[int] = None
    last_seen_run: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class GraphEdgeOut(BaseModel):
    id: int
    source_node_id: int
    target_node_id: int
    edge_type: str
    confidence: int = 100
    status: str = "active"


class GraphResponse(BaseModel):
    application_id: int
    nodes: List[GraphNodeOut] = []
    edges: List[GraphEdgeOut] = []
    total_nodes: int = 0
    total_edges: int = 0
    # Explicit empty-graph state (R1.9): true when no explore/reconcile has run.
    is_empty: bool = False
    skip: int = 0
    limit: int = 0


class GraphNodeDetail(GraphNodeOut):
    # Provenance + downstream intelligence. risk/coverage/memory are placeholders
    # until their engines (Tasks 9–15) are built — returned as null, never faked.
    provenance: Optional[dict] = None
    coverage: Optional[dict] = None
    memory: Optional[dict] = None


class GraphNodeOverride(BaseModel):
    """Authoritative manual correction of a node (Req 2.7, 3.5)."""
    node_type: Optional[str] = None
    business_category: Optional[str] = None
    role_association: Optional[str] = None
    # risk override: {"level": "...", "score": 0..100} — accepted as-is.
    risk: Optional[dict] = None


class SnapshotOut(BaseModel):
    id: int
    application_id: int
    explore_run_id: Optional[int] = None
    node_count: int = 0
    edge_count: int = 0
    diff_summary: Optional[dict] = None
    created_at: datetime


class SnapshotListResponse(BaseModel):
    application_id: int
    snapshots: List[SnapshotOut] = []
    total: int = 0
    skip: int = 0
    limit: int = 0


class SnapshotDiffResponse(BaseModel):
    application_id: int
    from_snapshot_id: int
    to_snapshot_id: int
    diff: dict


# -------------- Coverage Intelligence (Layer 2) --------------
class CoverageRollupOut(BaseModel):
    scope: str                       # "application" | category name
    percent: float                   # risk-weighted coverage %
    node_count: int
    covered_count: int
    partial_count: int
    uncovered_count: int


class CoverageGapOut(BaseModel):
    node_id: int
    canonical_key: str
    label: str
    state: str                       # partially_covered | uncovered
    confidence: float
    risk_score: int
    risk_level: str
    business_category: Optional[str] = None
    suggested_prompt: Optional[str] = None
    url: Optional[str] = None


class CoverageResponse(BaseModel):
    application_id: int
    is_empty: bool = False
    application_rollup: Optional[CoverageRollupOut] = None
    category_rollups: List[CoverageRollupOut] = []
    gaps: List[CoverageGapOut] = []
    total_gaps: int = 0
    skip: int = 0
    limit: int = 0


# -------------- Memory transparency (Layer 3) --------------
class MemoryItemOut(BaseModel):
    id: int
    kind: str                        # locator|timing|auth_pattern|outcome|fingerprint
    node_id: Optional[int] = None
    payload: dict
    version: int = 1
    provenance: Optional[dict] = None
    created_at: datetime


class MemoryListResponse(BaseModel):
    application_id: int
    items: List[MemoryItemOut] = []
    total: int = 0
    skip: int = 0
    limit: int = 0


# -------------- PR Intelligence: repo connection (Layer 4) --------------
class RepoConnectRequest(BaseModel):
    """Connect a repo. `token` and `webhook_secret` are write-only secrets."""
    provider: str = "github"
    repo_full_name: str = Field(..., min_length=3)   # "owner/repo"
    token: str = Field(..., min_length=1)            # stored as secret ref, never echoed
    webhook_secret: Optional[str] = None             # stored as secret ref, never echoed


class RepoStatusOut(BaseModel):
    """
    Repo connection status — NEVER includes token/webhook_secret. `secret_set`
    and `webhook_secret_set` are booleans only; `masked_*` are constant masks.
    """
    id: int
    application_id: int
    provider: str
    repo_full_name: str
    status: str                      # connected | failed
    last_error: Optional[str] = None
    secret_set: bool = False
    webhook_secret_set: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None


class WebhookAck(BaseModel):
    received: bool
    detail: str
    diff_id: Optional[int] = None


# -------------- PR Intelligence: diffs + recommendations (Layer 4) --------------
class CodeDiffOut(BaseModel):
    id: int
    application_id: int
    pr_number: Optional[str] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    ingest_status: str
    changed_file_count: int = 0
    created_at: datetime


class CodeDiffListResponse(BaseModel):
    application_id: int
    diffs: List[CodeDiffOut] = []
    total: int = 0
    skip: int = 0
    limit: int = 0


class FlowMappingOut(BaseModel):
    node_id: Optional[int] = None
    canonical_key: Optional[str] = None
    label: Optional[str] = None
    confidence: float
    signals: List[dict] = []
    recommended_test_ids: List[int] = []
    coverage_state: str
    risk_score: int = 0
    risk_level: str = "Trivial"
    chain: dict = {}
    no_coverage_warning: bool = False
    suggested_prompt: Optional[str] = None


class DiffRecommendationResponse(BaseModel):
    application_id: int
    diff_id: int
    status: str                       # ok | no_graph | stale | pending
    message: str
    mappings: List[FlowMappingOut] = []
    recommended_test_ids: List[int] = []


class DiffRunResponse(BaseModel):
    message: str
    diff_id: int
    job_ids: List[str] = []
