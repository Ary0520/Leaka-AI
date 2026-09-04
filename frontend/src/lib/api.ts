const BASE = 
  (typeof window !== "undefined")
    ? "" // On the client browser, use relative paths so Vercel's secure rewrites handle it
    : ((typeof process !== "undefined" && process.env?.NEXT_PUBLIC_BACKEND_URL) ||
       "http://localhost:8000");


// ── Auth token storage (set by providers.tsx on session change) ───────────────
let _authToken: string | null = null;
export function setAuthToken(token: string | null) {
  _authToken = token;
}
export function getAuthToken(): string | null {
  return _authToken;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const url = path.startsWith("http")
    ? path
    : `${BASE.replace(/\/$/, "")}${path.startsWith("/") ? "" : "/"}${path}`;

  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string>),
  };
  if (
    init.method !== "GET" &&
    init.body &&
    !(init.body instanceof FormData) &&
    !headers["Content-Type"]
  ) {
    headers["Content-Type"] = "application/json";
  }
  // Attach Supabase JWT to every request
  if (_authToken) {
    headers["Authorization"] = `Bearer ${_authToken}`;
  }

  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (data?.detail) msg = String(data.detail);
      else if (data?.message) msg = String(data.message);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as unknown as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.blob()) as unknown as T;
}

// ---------- Types ----------
export type RunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface Screenshot {
  id: number;
  file_path: string;
  url?: string | null;
  caption?: string | null;
  step_index?: number | null;
  is_failure_point: boolean;
  created_at: string;
}

export interface RunStatusResponse {
  job_id: string;
  task_id?: string | null;
  validation_for_job_id?: string | null;
  status: RunStatus;
  name: string;
  prompt: string;
  target_url?: string | null;
  stage?: string | null;
  progress?: {
    stage?: string;
    step?: number;
    total?: number;
    pct?: number;
  } | null;
  total_steps?: number | null;
  duration_seconds?: number | null;
  result_summary?: string | null;
  final_result?: string | null;
  error_message?: string | null;
  steps_log?: string | null;
  visited_urls?: string | null;
  live_steps?: string | null;
  console_logs?: string | null;
  har_data?: string | null;
  rca_category?: string | null;
  is_successful?: boolean | null;
  assertions?: string | null;          // JSON string: Assertion[]
  assertion_results?: string | null;   // JSON string: AssertionResult[]
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  screenshots: Screenshot[];
}

export interface RunListEntry {
  job_id: string;
  name: string;
  status: RunStatus;
  is_successful?: boolean | null;
  duration_seconds?: number | null;
  has_visual_proof: boolean;
  created_at: string;
  completed_at?: string | null;
}

export type AssertionType =
  | "page_contains_text"
  | "page_not_contains_text"
  | "url_contains"
  | "url_equals"
  | "page_contains_regex";

export interface Assertion {
  type: AssertionType;
  value: string;
  case_sensitive?: boolean;
}

export interface AssertionResult {
  type: string;
  value: string;
  passed: boolean;
  detail?: string | null;
}

export interface TestRunRequest {
  name?: string | null;
  prompt: string;
  success_criteria?: string | null;
  target_url?: string | null;
  test_case_id?: number | null;
  use_vision?: boolean;
  max_steps?: number;
  assertions?: Assertion[] | null;
  environment_id?: number | null;
  fixture_id?: number | null;
}

export interface EnqueueResponse {
  job_id: string;
  task_id: string;
  status: string;
}

export interface TestCaseOut {
  id: number;
  name: string;
  prompt: string;
  success_criteria?: string | null;
  target_url?: string | null;
  suite_id?: number | null;
  assertions?: Assertion[] | null;
  is_quarantined?: boolean;
  created_at: string;
  updated_at: string;
}

export interface TestCaseCreate {
  name: string;
  prompt: string;
  success_criteria?: string | null;
  target_url?: string | null;
  suite_id?: number | null;
  assertions?: Assertion[] | null;
  // Optional authoritative coverage linkage: when a test is generated from a
  // graph node, pass both so the backend records a CoverageLink (R4.3).
  application_id?: number | null;
  node_id?: number | null;
}

export interface TestCaseUpdate {
  name?: string | null;
  prompt?: string | null;
  success_criteria?: string | null;
  target_url?: string | null;
  suite_id?: number | null;
  assertions?: Assertion[] | null;
  is_quarantined?: boolean | null;
}

export interface TestSuiteOut {
  id: number;
  name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
  tests: TestCaseOut[];
}

export interface TestSuiteCreate {
  name: string;
  description?: string | null;
}

export interface TestSuiteUpdate {
  name?: string | null;
  description?: string | null;
}

export interface TestSuiteRunResponse {
  message: string;
  suite_id: number;
  count: number;
  job_ids: string[];
}

// ---------- Application Intelligence (Explore Mode) ----------
export type ExploreStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface ApplicationOut {
  id: number;
  name: string;
  base_url: string;
  description?: string | null;
  login_hint?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationCreate {
  name: string;
  base_url: string;
  description?: string | null;
  login_hint?: string | null;
}

export interface EnvironmentOut {
  id: number;
  application_id: number;
  name: string;
  base_url: string;
  variables?: string | null;
  policies?: string | null;
  auth_strategy?: string | null;
  auth_api_url?: string | null;
  auth_payload?: string | null;
  auth_token_path?: string | null;
  auth_state_template?: string | null;
  created_at: string;
}

export interface EnvironmentCreate {
  name: string;
  base_url: string;
  variables?: string | null;
  policies?: string | null;
  auth_strategy?: string | null;
  auth_api_url?: string | null;
  auth_payload?: string | null;
  auth_token_path?: string | null;
  auth_state_template?: string | null;
}

export interface TestFixtureOut {
  id: number;
  application_id: number;
  name: string;
  setup_api_url: string;
  setup_payload?: string | null;
  teardown_api_url?: string | null;
  teardown_payload?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TestFixtureCreate {
  name: string;
  setup_api_url: string;
  setup_payload?: string | null;
  teardown_api_url?: string | null;
  teardown_payload?: string | null;
}

export interface AppMapNodeOut {
  id: number;
  node_type: string; // "page" | "form" | "flow"
  label: string;
  url?: string | null;
  description?: string | null;
  suggested_prompt?: string | null;
  is_covered?: boolean | null;
  created_at: string;
}

export interface ExploreRunStatusResponse {
  job_id: string;
  task_id?: string | null;
  application_id: number;
  status: ExploreStatus;
  max_steps?: number | null;
  nodes_found?: number | null;
  result_summary?: string | null;
  error_message?: string | null;
  live_steps?: string | null;
  visited_urls?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ApplicationMapResponse {
  application: ApplicationOut;
  latest_explore?: ExploreRunStatusResponse | null;
  nodes: AppMapNodeOut[];
  total_nodes: number;
  covered_nodes: number;
}

// ---------- Application Graph (Layer 1) ----------
export interface GraphNodeOut {
  id: number;
  canonical_key: string;
  node_type: string; // page|flow|form|action|role
  business_category?: string | null;
  label: string;
  url_pattern?: string | null;
  role_association?: string | null;
  dependencies_incomplete: boolean;
  status: string; // active|stale
  semantics?: Record<string, unknown> | null;
  risk?: Record<string, unknown> | null;
  manual_overrides?: Record<string, unknown> | null;
  // Coverage cross-reference joined at read time by GET /graph and
  // /graph/nodes/{id}. null = no verdict computed yet (undetermined).
  coverage_state?: string | null; // covered|partially_covered|uncovered
  coverage_confidence?: number | null; // [0.0, 1.0]
  first_seen_run?: number | null;
  last_seen_run?: number | null;
  created_at: string;
  updated_at?: string | null;
}

export interface GraphEdgeOut {
  id: number;
  source_node_id: number;
  target_node_id: number;
  edge_type: string; // navigates_to|contains|requires_role|depends_on|part_of_flow
  confidence: number;
  status: string;
}

export interface GraphResponse {
  application_id: number;
  nodes: GraphNodeOut[];
  edges: GraphEdgeOut[];
  total_nodes: number;
  total_edges: number;
  is_empty: boolean;
  skip: number;
  limit: number;
}

export interface GraphNodeDetail extends GraphNodeOut {
  provenance?: Record<string, unknown> | null;
  coverage?: Record<string, unknown> | null; // placeholder until coverage engine
  memory?: Record<string, unknown> | null;   // placeholder until memory engine
}

export interface GraphNodeOverride {
  node_type?: string | null;
  business_category?: string | null;
  role_association?: string | null;
  risk?: Record<string, unknown> | null;
}

export interface SnapshotOut {
  id: number;
  application_id: number;
  explore_run_id?: number | null;
  node_count: number;
  edge_count: number;
  diff_summary?: Record<string, unknown> | null;
  created_at: string;
}

export interface SnapshotListResponse {
  application_id: number;
  snapshots: SnapshotOut[];
  total: number;
  skip: number;
  limit: number;
}

export interface SnapshotDiffResponse {
  application_id: number;
  from_snapshot_id: number;
  to_snapshot_id: number;
  diff: Record<string, unknown>;
}

// ---------- Coverage Intelligence (Layer 2) ----------
export interface CoverageRollupOut {
  scope: string;
  percent: number;
  node_count: number;
  covered_count: number;
  partial_count: number;
  uncovered_count: number;
}

export interface CoverageGapOut {
  node_id: number;
  canonical_key: string;
  label: string;
  state: string; // partially_covered | uncovered
  confidence: number;
  risk_score: number;
  risk_level: string;
  business_category?: string | null;
  suggested_prompt?: string | null;
  url?: string | null;
}

export interface CoverageResponse {
  application_id: number;
  is_empty: boolean;
  application_rollup?: CoverageRollupOut | null;
  category_rollups: CoverageRollupOut[];
  gaps: CoverageGapOut[];
  total_gaps: number;
  skip: number;
  limit: number;
}

// ---------- Memory transparency (Layer 3) ----------
export interface MemoryItemOut {
  id: number;
  kind: string; // locator|timing|auth_pattern|outcome|fingerprint
  node_id?: number | null;
  payload: Record<string, unknown>;
  version: number;
  provenance?: Record<string, unknown> | null;
  created_at: string;
}

export interface MemoryListResponse {
  application_id: number;
  items: MemoryItemOut[];
  total: number;
  skip: number;
  limit: number;
}

// ---------- PR Intelligence: repo connection (Layer 4) ----------
export interface RepoConnectRequest {
  provider?: string; // "github"
  repo_full_name: string; // "owner/repo"
  token: string; // write-only; never returned
  webhook_secret?: string | null; // write-only; never returned
}

export interface RepoStatusOut {
  id: number;
  application_id: number;
  provider: string;
  repo_full_name: string;
  status: string; // connected | failed
  last_error?: string | null;
  secret_set: boolean;
  webhook_secret_set: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface CodeDiffOut {
  id: number;
  application_id: number;
  pr_number?: string | null;
  commit_sha?: string | null;
  branch?: string | null;
  ingest_status: string;
  changed_file_count: number;
  created_at: string;
}

export interface CodeDiffListResponse {
  application_id: number;
  diffs: CodeDiffOut[];
  total: number;
  skip: number;
  limit: number;
}

export interface FlowMappingOut {
  node_id?: number | null;
  canonical_key?: string | null;
  label?: string | null;
  confidence: number;
  signals: Record<string, unknown>[];
  recommended_test_ids: number[];
  coverage_state: string;
  risk_score: number;
  risk_level: string;
  chain: Record<string, unknown>;
  no_coverage_warning: boolean;
  suggested_prompt?: string | null;
}

export interface DiffRecommendationResponse {
  application_id: number;
  diff_id: number;
  status: string; // ok | no_graph | stale | pending | failed
  message: string;
  mappings: FlowMappingOut[];
  recommended_test_ids: number[];
}

export interface DiffRunResponse {
  message: string;
  diff_id: number;
  job_ids: string[];
}

// ---------- API ----------
export const api = {
  health: () => request<{ status: string; llm_provider: string; llm_model: string }>("/api/health"),

  // LLM connection test
  testLlmConnection: () =>
    request<{ ok: boolean; provider: string; model: string; detail: string }>(
      "/api/settings/llm/test-connection",
      { method: "POST" },
    ),

  // Dashboard health grid
  dashboardHealth: (limit = 14) =>
    request<Array<{
      id: number;
      name: string;
      target_url: string | null;
      last_status: string | null;
      last_successful: boolean | null;
      pass_rate: number | null;
      total_runs: number;
      runs: Array<{
        job_id: string;
        status: string;
        is_successful: boolean | null;
        created_at: string | null;
        duration_seconds: number | null;
      }>;
    }>>(`/api/dashboard/health?limit=${limit}`),

  // Demo seed
  seedDemo: () => request<{ message: string; created: number }>("/api/demo/seed", { method: "POST" }),

  // Integration settings
  getIntegrationSettings: () => request<{
    linear: { api_key: string; api_key_set: boolean; team_id: string };
    resend: { api_key: string; api_key_set: boolean; email_from: string; email_alert_to: string };
    slack: { webhook_url: string; webhook_url_set: boolean };
    llm: { provider: string; openrouter_model: string; openai_model: string; anthropic_model: string; ollama_model: string; openrouter_key_set: boolean; openai_key_set: boolean; anthropic_key_set: boolean };
    ci: { webhook_token: string };
  }>("/api/settings/integrations"),
  updateIntegrationSettings: (body: {
    linear_api_key?: string; linear_team_id?: string;
    resend_api_key?: string; email_from?: string; email_alert_to?: string;
    slack_webhook_url?: string;
    llm_provider?: string; llm_model_openrouter?: string;
    openrouter_api_key?: string; openai_api_key?: string; anthropic_api_key?: string;
    ci_webhook_token?: string;
  }) => request<{ message: string; updated: string[] }>("/api/settings/integrations", {
    method: "PATCH",
    body: JSON.stringify(body),
  }),

  // Runs
  enqueueRun: (body: TestRunRequest) =>
    request<EnqueueResponse>("/api/tests/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getRunStatus: (jobId: string) =>
    request<RunStatusResponse>(`/api/tests/status/${jobId}`),
  getRunDetail: (jobId: string) =>
    request<RunStatusResponse>(`/api/tests/${jobId}`),
  cancelRun: (jobId: string) =>
    request<RunStatusResponse>(`/api/tests/${jobId}/cancel`, { method: "POST" }),
  listRuns: (params?: {
    status?: RunStatus;
    test_case_id?: number;
    skip?: number;
    limit?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.test_case_id) qs.set("test_case_id", String(params.test_case_id));
    if (params?.skip) qs.set("skip", String(params.skip));
    if (params?.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<RunListEntry[]>(
      `/api/tests${q ? `?${q}` : ""}`,
    );
  },
  // Test cases
  listTestCases: (params?: { suite_id?: number; skip?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.suite_id) qs.set("suite_id", String(params.suite_id));
    if (params?.skip) qs.set("skip", String(params.skip));
    if (params?.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<TestCaseOut[]>(
      `/api/test-cases${q ? `?${q}` : ""}`,
    );
  },
  createTestCase: (body: TestCaseCreate) =>
    request<TestCaseOut>("/api/test-cases", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateTestCase: (id: number, body: TestCaseUpdate) =>
    request<TestCaseOut>(`/api/test-cases/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteTestCase: (id: number) =>
    request<void>(`/api/test-cases/${id}`, { method: "DELETE" }),

  // Test suites
  listSuites: (params?: { skip?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.skip) qs.set("skip", String(params.skip));
    if (params?.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<TestSuiteOut[]>(`/api/test-suites${q ? `?${q}` : ""}`);
  },
  getSuite: (id: number) =>
    request<TestSuiteOut>(`/api/test-suites/${id}`),
  createSuite: (body: TestSuiteCreate) =>
    request<TestSuiteOut>("/api/test-suites", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateSuite: (id: number, body: TestSuiteUpdate) =>
    request<TestSuiteOut>(`/api/test-suites/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteSuite: (id: number) =>
    request<void>(`/api/test-suites/${id}`, { method: "DELETE" }),
  runSuite: (id: number, params?: { use_vision?: boolean; max_steps?: number }) => {
    const qs = new URLSearchParams();
    if (params?.use_vision != null) qs.set("use_vision", String(params.use_vision));
    if (params?.max_steps) qs.set("max_steps", String(params.max_steps));
    const q = qs.toString();
    return request<TestSuiteRunResponse>(
      `/api/test-suites/${id}/run${q ? `?${q}` : ""}`,
      { method: "POST" },
    );
  },

  // Environments & Fixtures
  listEnvironments: (appId: number) =>
    request<EnvironmentOut[]>(`/api/applications/${appId}/environments`),
  createEnvironment: (appId: number, body: EnvironmentCreate) =>
    request<EnvironmentOut>(`/api/applications/${appId}/environments`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listFixtures: (appId: number) =>
    request<TestFixtureOut[]>(`/api/applications/${appId}/fixtures`),
  createFixture: (appId: number, body: TestFixtureCreate) =>
    request<TestFixtureOut>(`/api/applications/${appId}/fixtures`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Linear
  createLinearIssue: (body: {
    job_id: string;
    title?: string | null;
    description?: string | null;
  }) =>
    request<{
      success: boolean;
      issue_id?: string | null;
      identifier?: string | null;
      title?: string | null;
    }>("/api/integrations/linear/issue", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Email alert
  sendFailureEmail: (jobId: string, dashboardBaseUrl?: string) => {
    const form = new FormData();
    if (dashboardBaseUrl) form.append("dashboard_base_url", dashboardBaseUrl);
    return request<{ sent: boolean; result: unknown }>(
      `/api/integrations/email/alert-failure/${jobId}`,
      {
        method: "POST",
        body: form,
      },
    );
  },

  // Slack alert
  sendSlackAlert: (jobId: string, dashboardBaseUrl?: string) => {
    const form = new FormData();
    if (dashboardBaseUrl) form.append("dashboard_base_url", dashboardBaseUrl);
    return request<{ sent: boolean; result: unknown }>(
      `/api/integrations/slack/alert-failure/${jobId}`,
      {
        method: "POST",
        body: form,
      },
    );
  },

  // Per-user Slack settings
  getUserSlackSettings: () =>
    request<{
      slack_webhook_url_set: boolean;
      slack_webhook_url_masked: string;
      slack_auto_alert_on_failure: boolean;
      dashboard_base_url: string;
    }>("/api/user/slack-settings"),

  updateUserSlackSettings: (body: {
    slack_webhook_url?: string;
    slack_auto_alert_on_failure?: boolean;
    dashboard_base_url?: string;
  }) =>
    request<{ message: string; auto_alert: boolean }>("/api/user/slack-settings", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  testSlackPing: () =>
    request<{ ok: boolean; message: string }>("/api/user/slack-settings/test-ping", {
      method: "POST",
    }),

  // Onboarding
  getOnboardingStatus: () =>
    request<{ onboarding_completed: boolean }>("/api/user/onboarding"),
  completeOnboarding: () =>
    request<{ onboarding_completed: boolean }>("/api/user/onboarding/complete", {
      method: "POST",
    }),

  // CI webhook — dashboard-triggered runs authenticate as the logged-in user
  // via the Bearer JWT that request() attaches automatically. The CI secret
  // token is ONLY used by external CI systems (GitHub Actions), never shipped
  // to the browser.
  triggerCI: (body: {
    suite_id?: number | null;
    test_case_ids?: number[] | null;
    branch?: string | null;
    commit_sha?: string | null;
    triggered_by?: string | null;
  }) =>
    request<{ message: string; job_ids: string[] }>("/api/webhooks/ci", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Application Intelligence (Explore Mode)
  listApplications: () => request<ApplicationOut[]>("/api/applications"),
  getApplication: (id: number) => request<ApplicationOut>(`/api/applications/${id}`),
  createApplication: (body: ApplicationCreate) =>
    request<ApplicationOut>("/api/applications", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateApplication: (id: number, body: Partial<ApplicationCreate>) =>
    request<ApplicationOut>(`/api/applications/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteApplication: (id: number) =>
    request<void>(`/api/applications/${id}`, { method: "DELETE" }),
  exploreApplication: (id: number, maxSteps = 40) =>
    request<{ job_id: string; task_id: string; status: string }>(
      `/api/applications/${id}/explore?max_steps=${maxSteps}`,
      { method: "POST" },
    ),
  getExploreStatus: (jobId: string) =>
    request<ExploreRunStatusResponse>(`/api/explore/status/${jobId}`),
  getApplicationMap: (id: number) =>
    request<ApplicationMapResponse>(`/api/applications/${id}/map`),
  generateTestMatrix: (id: number, app_map_node_id?: number, graph_node_id?: number) =>
    request<{ test_cases: Array<{ name: string; prompt: string; success_criteria: string; assertions: any[] }> }>(
      `/api/applications/${id}/generate-matrix`,
      { method: "POST", body: JSON.stringify({ app_map_node_id, graph_node_id }) },
    ),

  // Application Graph (Layer 1)
  getApplicationGraph: (
    id: number,
    params?: { skip?: number; limit?: number; include_stale?: boolean },
  ) => {
    const qs = new URLSearchParams();
    if (params?.skip != null) qs.set("skip", String(params.skip));
    if (params?.limit != null) qs.set("limit", String(params.limit));
    if (params?.include_stale != null) qs.set("include_stale", String(params.include_stale));
    const q = qs.toString();
    return request<GraphResponse>(`/api/applications/${id}/graph${q ? `?${q}` : ""}`);
  },
  getGraphNode: (id: number, nodeId: number) =>
    request<GraphNodeDetail>(`/api/applications/${id}/graph/nodes/${nodeId}`),
  overrideGraphNode: (id: number, nodeId: number, body: GraphNodeOverride) =>
    request<GraphNodeDetail>(`/api/applications/${id}/graph/nodes/${nodeId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  listSnapshots: (id: number, params?: { skip?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.skip != null) qs.set("skip", String(params.skip));
    if (params?.limit != null) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<SnapshotListResponse>(`/api/applications/${id}/snapshots${q ? `?${q}` : ""}`);
  },
  diffSnapshots: (id: number, fromId: number, toId: number) =>
    request<SnapshotDiffResponse>(`/api/applications/${id}/snapshots/${fromId}/diff/${toId}`),

  // Coverage Intelligence (Layer 2)
  getApplicationCoverage: (id: number, params?: { skip?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.skip != null) qs.set("skip", String(params.skip));
    if (params?.limit != null) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<CoverageResponse>(`/api/applications/${id}/coverage${q ? `?${q}` : ""}`);
  },

  // Memory transparency (Layer 3)
  getApplicationMemory: (
    id: number,
    params?: { kind?: string; skip?: number; limit?: number },
  ) => {
    const qs = new URLSearchParams();
    if (params?.kind) qs.set("kind", params.kind);
    if (params?.skip != null) qs.set("skip", String(params.skip));
    if (params?.limit != null) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<MemoryListResponse>(`/api/applications/${id}/memory${q ? `?${q}` : ""}`);
  },

  // PR Intelligence: repo connection (Layer 4). Secrets are write-only.
  connectRepo: (id: number, body: RepoConnectRequest) =>
    request<RepoStatusOut>(`/api/applications/${id}/repo`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getRepo: (id: number) =>
    request<RepoStatusOut | null>(`/api/applications/${id}/repo`),
  disconnectRepo: (id: number) =>
    request<void>(`/api/applications/${id}/repo`, { method: "DELETE" }),

  // PR Intelligence: diffs + recommendations (Layer 4)
  listDiffs: (id: number, params?: { skip?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.skip != null) qs.set("skip", String(params.skip));
    if (params?.limit != null) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<CodeDiffListResponse>(`/api/applications/${id}/diffs${q ? `?${q}` : ""}`);
  },
  getDiffRecommendation: (id: number, diffId: number) =>
    request<DiffRecommendationResponse>(
      `/api/applications/${id}/diffs/${diffId}/recommendation`,
    ),
  runDiffRecommendation: (id: number, diffId: number) =>
    request<DiffRunResponse>(`/api/applications/${id}/diffs/${diffId}/run`, {
      method: "POST",
    }),
};

export const BACKEND_URL = BASE;

// Supabase sign-out helper (client-side)
export async function signOut() {
  const { createClient } = await import("@/lib/supabase/client");
  const supabase = createClient();
  await supabase.auth.signOut();
  setAuthToken(null);
  window.location.href = "/login";
}
