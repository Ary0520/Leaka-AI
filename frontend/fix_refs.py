import re

def fix_imports(filepath, function_name):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'useWorkspace' not in content:
        content = content.replace('import { useQuery', 'import { useWorkspace } from "@/app/providers";\nimport { useQuery')
        
    if 'const { activeWorkspaceId } = useWorkspace();' not in content:
        content = content.replace(f'export default function {function_name}() {{', 
                                  f'export default function {function_name}() {{\n  const {{ activeWorkspaceId }} = useWorkspace();')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

fix_imports(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\new\page.tsx', 'NewTestPage')
fix_imports(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\suites\page.tsx', 'SuitesPage')
fix_imports(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\tests\page.tsx', 'TestsPage')
fix_imports(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\ci\page.tsx', 'CIPage')

print("Fixed Next.js ReferenceErrors")
