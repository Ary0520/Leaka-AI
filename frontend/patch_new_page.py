import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\new\page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Make sure useWorkspace is imported
if 'useWorkspace' not in content:
    content = content.replace('import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";', 
                              'import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";\nimport { useWorkspace } from "@/app/providers";')

# Get activeWorkspaceId inside component
if 'const { activeWorkspaceId } = useWorkspace();' not in content:
    content = content.replace('export default function NewRunPage() {', 
                              'export default function NewRunPage() {\n  const { activeWorkspaceId } = useWorkspace();')

# Add workspace_id to createTestCase
content = content.replace(
    'const saved = await api.createTestCase({',
    'const saved = await api.createTestCase({\n          workspace_id: activeWorkspaceId === "personal" ? undefined : activeWorkspaceId,'
)

# Add workspace_id to enqueueRun
content = content.replace(
    'return api.enqueueRun({',
    'return api.enqueueRun({\n        workspace_id: activeWorkspaceId === "personal" ? undefined : activeWorkspaceId,'
)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\new\page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched new/page.tsx")
