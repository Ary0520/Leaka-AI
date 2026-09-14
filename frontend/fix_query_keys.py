import re
import glob

def fix_query_keys(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    content = content.replace(
        'queryKey: ["testcases"],',
        'queryKey: ["testcases", activeWorkspaceId],'
    )
    content = content.replace(
        'queryKey: ["suites"],',
        'queryKey: ["suites", activeWorkspaceId],'
    )
    content = content.replace(
        'queryKey: ["applications"],',
        'queryKey: ["applications", activeWorkspaceId],'
    )
    # also for tests/page.tsx and ci/page.tsx
    content = content.replace(
        'queryKey: ["suites", statusFilter, activeWorkspaceId]',
        'queryKey: ["suites", statusFilter, activeWorkspaceId]' # just in case
    )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for path in glob.glob(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\**\*.tsx', recursive=True):
    fix_query_keys(path)

print("Fixed query keys")
