with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

# Fix list_runs
content = content.replace(
    'q = db.query(TestRun).filter(TestRun.workspace_id == None)',
    'q = db.query(TestRun).filter(TestRun.workspace_id == None, TestRun.owner_id == user["sub"])'
)

# Fix list_test_cases
content = content.replace(
    'q = db.query(TestCase).filter(TestCase.workspace_id == None)',
    'q = db.query(TestCase).filter(TestCase.workspace_id == None, TestCase.owner_id == user["sub"])'
)

# Fix list_quarantined_tests
content = content.replace(
    'return db.query(TestCase).filter(TestCase.workspace_id == None, TestCase.is_quarantined == True).order_by(TestCase.updated_at.desc()).all()',
    'return db.query(TestCase).filter(TestCase.workspace_id == None, TestCase.owner_id == user["sub"], TestCase.is_quarantined == True).order_by(TestCase.updated_at.desc()).all()'
)

# Fix list_run_groups
content = content.replace(
    'base_q = base_q.filter(TestRun.workspace_id == None)',
    'base_q = base_q.filter(TestRun.workspace_id == None, TestRun.owner_id == user["sub"])'
)

# Fix dashboard_kpis
content = content.replace(
    'return query.filter(model.workspace_id == None)',
    'return query.filter(model.workspace_id == None, model.owner_id == owner)'
)

content = content.replace(
    'return query.filter(TestCase.workspace_id == None)',
    'return query.filter(TestCase.workspace_id == None, TestCase.owner_id == owner)'
)

# Also fix _get_owned_run just in case we need to allow workspace-level access!
# Wait, if someone clicks a run in a workspace, does _get_owned_run allow it if owner_id != user?
# If the run is in a workspace, they should be able to view it!
# But for now, let's fix the personal runs leak.

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)

print("Fixed owner_id leak")
