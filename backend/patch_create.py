import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\schemas.py', 'r') as f:
    content = f.read()

# Add workspace_id to TestCaseCreate
content = content.replace(
    'application_id: Optional[int] = None\n    node_id: Optional[int] = None',
    'application_id: Optional[int] = None\n    node_id: Optional[int] = None\n    workspace_id: Optional[int] = None'
)

# Add workspace_id to TestRunRequest
content = content.replace(
    'fixture_id: Optional[int] = None',
    'fixture_id: Optional[int] = None\n    workspace_id: Optional[int] = None'
)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\schemas.py', 'w') as f:
    f.write(content)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

# Update create_test_case to handle workspace_id (it will naturally be included in **data if we don't pop it!)
# Wait, if we don't pop it, it gets passed to TestCase(**data).
# Since workspace_id is in TestCaseCreate, it'll be in data! And TestCase model has workspace_id!
# So create_test_case is magically fixed just by adding it to schemas.py!

# Let's check run_test
# Wait, run_test creates TestRun, we need to see how it's created.
print("Patched schemas.py")
