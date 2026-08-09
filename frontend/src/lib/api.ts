const BASE =
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_BACKEND_URL) ||
  "http://localhost:8000";

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
  is_successful?: boolean | null;
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

export interface TestRunRequest {
  name?: string | null;
  prompt: string;
  success_criteria?: string | null;
  target_url?: string | null;
  test_case_id?: number | null;
  use_vision?: boolean;
  max_steps?: number;
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
  created_at: string;
  updated_at: string;
}

export interface TestCaseCreate {
  name: string;
  prompt: string;
  success_criteria?: string | null;
  target_url?: string | null;
  suite_id?: number | null;
}

export interface TestCaseUpdate {
  name?: string | null;
  prompt?: string | null;
  success_criteria?: string | null;
  target_url?: string | null;
  suite_id?: number | null;
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

// ---------- API ----------
export const api = {
  health: () => request<{ status: string; llm_provider: string; llm_model: string }>("/api/health"),

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

  // CI webhook
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
      headers: {
        "X-CI-Token":
          (typeof process !== "undefined" && process.env?.CI_WEBHOOK_TOKEN) ||
          "revguard-ci-token-change-me",
      },
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
