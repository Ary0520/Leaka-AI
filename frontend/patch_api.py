import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\lib\api.ts', 'r') as f:
    content = f.read()

# listTestCases
content = re.sub(
    r'listTestCases: \(suiteId\?: number\) =>\s+request<TestCaseOut\[\]>\(suiteId \? `/api/test-cases\?suite_id=\${suiteId}` : "/api/test-cases"\),',
    r'listTestCases: (suiteId?: number, workspaceId?: string) => {\n    let url = "/api/test-cases";\n    const params = new URLSearchParams();\n    if (suiteId) params.append("suite_id", suiteId.toString());\n    if (workspaceId && workspaceId !== "personal") params.append("workspace_id", workspaceId);\n    if (params.toString()) url += "?" + params.toString();\n    return request<TestCaseOut[]>(url);\n  },',
    content
)

# getRuns
content = re.sub(
    r'getRuns: \(status\?: string\) =>\s+request<TestRunOut\[\]>\(status \? `/api/runs\?status=\${status}` : "/api/runs"\),',
    r'getRuns: (status?: string, workspaceId?: string) => {\n    let url = "/api/runs";\n    const params = new URLSearchParams();\n    if (status) params.append("status", status);\n    if (workspaceId && workspaceId !== "personal") params.append("workspace_id", workspaceId);\n    if (params.toString()) url += "?" + params.toString();\n    return request<TestRunOut[]>(url);\n  },',
    content
)

# getRunGroups
content = re.sub(
    r'getRunGroups: \(\) =>\s+request<RunGroupOut\[\]>\("/api/run-groups"\),',
    r'getRunGroups: (workspaceId?: string) =>\n    request<RunGroupOut[]>(workspaceId && workspaceId !== "personal" ? `/api/run-groups?workspace_id=${workspaceId}` : "/api/run-groups"),',
    content
)

# getQuarantine
content = re.sub(
    r'getQuarantine: \(\) =>\s+request<TestCaseOut\[\]>\("/api/quarantine"\),',
    r'getQuarantine: (workspaceId?: string) =>\n    request<TestCaseOut[]>(workspaceId && workspaceId !== "personal" ? `/api/quarantine?workspace_id=${workspaceId}` : "/api/quarantine"),',
    content
)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\lib\api.ts', 'w') as f:
    f.write(content)

print("Patched api.ts successfully.")
