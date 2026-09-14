import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\lib\api.ts', 'r') as f:
    content = f.read()

# listTestCases
content = content.replace(
    'listTestCases: (params?: { suite_id?: number; skip?: number; limit?: number }) => {',
    'listTestCases: (params?: { suite_id?: number; skip?: number; limit?: number; workspace_id?: string }) => {'
)
content = content.replace(
    'if (params?.limit) qs.set("limit", String(params.limit));',
    'if (params?.limit) qs.set("limit", String(params.limit));\n      if (params?.workspace_id && params.workspace_id !== "personal") qs.set("workspace_id", params.workspace_id);'
)

# listSuites
content = content.replace(
    'listSuites: (params?: { skip?: number; limit?: number }) => {',
    'listSuites: (params?: { skip?: number; limit?: number; workspace_id?: string }) => {'
)
content = content.replace(
    'if (params?.limit) qs.set("limit", String(params.limit));',
    'if (params?.limit) qs.set("limit", String(params.limit));\n      if (params?.workspace_id && params.workspace_id !== "personal") qs.set("workspace_id", params.workspace_id);'
)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\lib\api.ts', 'w') as f:
    f.write(content)

print("Patched api.ts")
