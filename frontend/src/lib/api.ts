const BASE =
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_BACKEND_URL) ||
  "http://localhost:8000";

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
  is_successful?: boolean | null;
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

// ---------- API ----------
export const api = {
  health: () => request<{ status: string; llm_provider: string }>("/api/health"),

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
