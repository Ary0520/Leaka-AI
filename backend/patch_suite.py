import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\schemas.py', 'r') as f:
    content = f.read()

content = content.replace(
    'class TestSuiteCreate(TestSuiteBase):\n    pass',
    'class TestSuiteCreate(TestSuiteBase):\n    workspace_id: Optional[int] = None'
)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\schemas.py', 'w') as f:
    f.write(content)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\lib\api.ts', 'r') as f:
    content = f.read()

content = content.replace(
    'export interface TestSuiteCreate {\n  name: string;\n  description?: string | null;\n}',
    'export interface TestSuiteCreate {\n  name: string;\n  description?: string | null;\n  workspace_id?: string | number | null;\n}'
)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\lib\api.ts', 'w') as f:
    f.write(content)

print("Patched TestSuite schemas")
