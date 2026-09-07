import sys

with open('frontend/src/lib/api.ts', 'r') as f: content = f.read()

new_methods = """
  toggleQuarantine: (id: number) =>
    request<{ success: boolean; is_quarantined: boolean }>(
      /api/tests/\/toggle-quarantine,
      { method: "POST" }
    ),
  listQuarantined: () =>
    request<Array<{
      id: number;
      name: string;
      target_url: string;
      is_quarantined: boolean;
      updated_at: string;
    }>>(/api/quarantine),
  listRunGroups: () =>
    request<Array<{
      id: string;
      total_runs: number;
      passed_runs: number;
      failed_runs: number;
      created_at: string;
    }>>(/api/run-groups),
  runSuite: (id: number) =>
    request<{ runs: string[] }>(/api/test-suites/\/run, { method: "POST" }),
  createSuite: (data: { name: string; description: string }) =>
    request<any>(/api/test-suites, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listSuites: () =>
    request<Array<{
      id: number;
      name: string;
      description: string;
      created_at: string;
    }>>(/api/test-suites),
"""

content = content.replace('export const api = {', 'export const api = {' + new_methods)
with open('frontend/src/lib/api.ts', 'w') as f: f.write(content)
print('Injected methods into api.ts!')
