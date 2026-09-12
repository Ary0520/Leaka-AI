import os
code = '''

// ---------- Workspaces ----------
export interface WorkspaceOut {
  id: number;
  organization_id: number;
  name: string;
  created_at: string;
}

export function getWorkspaces() {
  return request<WorkspaceOut[]>("/api/workspaces", { method: "GET" });
}

export function createWorkspace(orgName: string, wsName: string) {
  return request<WorkspaceOut>("/api/workspaces", {
    method: "POST",
    body: JSON.stringify({ organization_name: orgName, workspace_name: wsName }),
  });
}

export function transferApplication(appId: number, workspaceId: number) {
  return request<{ status: string; workspace_id: number }>(`/api/applications/${appId}/transfer`, {
    method: "POST",
    body: JSON.stringify({ workspace_id: workspaceId }),
  });
}
'''
with open(os.path.join(r'c:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\lib\api.ts'), 'a') as f:
    f.write(code)
print('Appended Workspace API calls to api.ts')
