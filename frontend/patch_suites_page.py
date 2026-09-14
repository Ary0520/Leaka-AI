import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\suites\page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Make sure useWorkspace is imported
if 'useWorkspace' not in content:
    content = content.replace('import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";', 
                              'import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";\nimport { useWorkspace } from "@/app/providers";')

# Get activeWorkspaceId inside component
if 'const { activeWorkspaceId } = useWorkspace();' not in content:
    content = content.replace('export default function SuitesPage() {', 
                              'export default function SuitesPage() {\n  const { activeWorkspaceId } = useWorkspace();')

# Add workspace_id to createSuite
content = content.replace(
    'mutationFn: () => api.createSuite(newSuite)',
    'mutationFn: () => api.createSuite({ ...newSuite, workspace_id: activeWorkspaceId === "personal" ? undefined : activeWorkspaceId })'
)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\suites\page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched suites/page.tsx")
