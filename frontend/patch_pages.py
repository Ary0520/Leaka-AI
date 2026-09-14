import re

# 1. new/page.tsx
with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\new\page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'queryFn: () => api.listTestCases({ limit: 100 }),',
    'queryFn: () => api.listTestCases({ limit: 100, workspace_id: activeWorkspaceId }),'
)
content = content.replace(
    'queryFn: () => api.listSuites({ limit: 100 }),',
    'queryFn: () => api.listSuites({ limit: 100, workspace_id: activeWorkspaceId }),'
)
content = content.replace(
    'queryFn: () => api.listApplications(),',
    'queryFn: () => api.listApplications(activeWorkspaceId),'
)
with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\new\page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

# 2. suites/page.tsx
with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\suites\page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'queryFn: () => api.listSuites(),',
    'queryFn: () => api.listSuites({ workspace_id: activeWorkspaceId }),'
)
with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\suites\page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

# 3. tests/page.tsx
with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\tests\page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

if 'activeWorkspaceId' not in content:
    content = content.replace('import { useQuery } from "@tanstack/react-query";',
                              'import { useQuery } from "@tanstack/react-query";\nimport { useWorkspace } from "@/app/providers";')
    content = content.replace('export default function TestsPage() {',
                              'export default function TestsPage() {\n  const { activeWorkspaceId } = useWorkspace();')

content = content.replace(
    'queryFn: () => api.listTestCases(),',
    'queryFn: () => api.listTestCases({ workspace_id: activeWorkspaceId }),'
)
with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\tests\page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

# 4. ci/page.tsx
with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\ci\page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

if 'activeWorkspaceId' not in content:
    content = content.replace('import { useQuery } from "@tanstack/react-query";',
                              'import { useQuery } from "@tanstack/react-query";\nimport { useWorkspace } from "@/app/providers";')
    content = content.replace('export default function CIPage() {',
                              'export default function CIPage() {\n  const { activeWorkspaceId } = useWorkspace();')

content = content.replace(
    'queryFn: () => api.listSuites(),',
    'queryFn: () => api.listSuites({ workspace_id: activeWorkspaceId }),'
)
with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\ci\page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched all page usages")
