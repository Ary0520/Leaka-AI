import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\new\page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'function NewTestContent() {',
    'function NewTestContent() {\n  const { activeWorkspaceId } = useWorkspace();'
)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\new\page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed new/page.tsx")
