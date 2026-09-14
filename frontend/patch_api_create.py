import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\lib\api.ts', 'r') as f:
    content = f.read()

# Add workspace_id to TestCaseCreate interface
content = content.replace(
    'application_id?: number | null;',
    'application_id?: number | null;\n  workspace_id?: string | number | null;'
)

# Add workspace_id to TestRunRequest interface
content = content.replace(
    'fixture_id?: number | null;',
    'fixture_id?: number | null;\n  workspace_id?: string | number | null;'
)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\lib\api.ts', 'w') as f:
    f.write(content)

print("Patched api.ts types")
