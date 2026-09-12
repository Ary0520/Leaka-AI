import os
import re

components = {
    r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\runs\page.tsx": [
        (r'const { data: runs, isLoading } = useQuery\({', r'const { activeWorkspaceId } = useWorkspace();\n  const { data: runs, isLoading } = useQuery({'),
        (r'queryKey: \["runs"\]', r'queryKey: ["runs", activeWorkspaceId]'),
        (r'queryFn: \(\) => api\.getRuns\(\)', r'queryFn: () => api.getRuns(undefined, activeWorkspaceId)'),
        (r'export default function RunsPage\(\) {', r'import { useWorkspace } from "@/app/providers";\n\nexport default function RunsPage() {')
    ],
    r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\run-groups\page.tsx": [
        (r'const { data: groups, isLoading } = useQuery\({', r'const { activeWorkspaceId } = useWorkspace();\n  const { data: groups, isLoading } = useQuery({'),
        (r'queryKey: \["run-groups"\]', r'queryKey: ["run-groups", activeWorkspaceId]'),
        (r'queryFn: \(\) => api\.getRunGroups\(\)', r'queryFn: () => api.getRunGroups(activeWorkspaceId)'),
        (r'export default function RunGroupsPage\(\) {', r'import { useWorkspace } from "@/app/providers";\n\nexport default function RunGroupsPage() {')
    ],
    r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\tests\page.tsx": [
        (r'const { data: tests, isLoading: testsLoading } = useQuery\({', r'const { activeWorkspaceId } = useWorkspace();\n  const { data: tests, isLoading: testsLoading } = useQuery({'),
        (r'queryKey: \["test-cases"\]', r'queryKey: ["test-cases", activeWorkspaceId]'),
        (r'queryFn: \(\) => api\.listTestCases\(\)', r'queryFn: () => api.listTestCases(undefined, activeWorkspaceId)'),
        (r'export default function TestsPage\(\) {', r'import { useWorkspace } from "@/app/providers";\n\nexport default function TestsPage() {')
    ],
    r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\quarantine\page.tsx": [
        (r'const { data: tests, isLoading } = useQuery\({', r'const { activeWorkspaceId } = useWorkspace();\n  const { data: tests, isLoading } = useQuery({'),
        (r'queryKey: \["quarantine-tests"\]', r'queryKey: ["quarantine-tests", activeWorkspaceId]'),
        (r'queryFn: \(\) => api\.getQuarantine\(\)', r'queryFn: () => api.getQuarantine(activeWorkspaceId)'),
        (r'export default function QuarantinePage\(\) {', r'import { useWorkspace } from "@/app/providers";\n\nexport default function QuarantinePage() {')
    ]
}

for filepath, replacements in components.items():
    if not os.path.exists(filepath):
        print(f"Skipping {filepath}, does not exist")
        continue
        
    with open(filepath, 'r') as f:
        content = f.read()
        
    # Prevent double-import
    if 'useWorkspace' in content and 'import { useWorkspace }' not in content:
        pass
        
    for pattern, repl in replacements:
        if repl in content:
            continue
        content = re.sub(pattern, repl, content)
        
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"Patched {filepath}")
