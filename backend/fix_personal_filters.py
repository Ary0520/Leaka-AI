with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

replacements = [
    # list_runs personal fallback
    (
        'q = db.query(TestRun).filter(TestRun.owner_id == user["sub"])',
        'q = db.query(TestRun).filter(TestRun.workspace_id == None)'
    ),
    # list_test_cases personal fallback
    (
        'q = db.query(TestCase).filter(TestCase.owner_id == user["sub"])',
        'q = db.query(TestCase).filter(TestCase.workspace_id == None)'
    ),
    # list_run_groups personal fallback
    (
        'groups = q.filter(TestRun.owner_id == user["sub"], TestRun.run_group_id != None)',
        'groups = q.filter(TestRun.workspace_id == None, TestRun.run_group_id != None)'
    ),
    # list_quarantine personal fallback
    (
        'return db.query(TestCase).filter(TestCase.owner_id == user["sub"], TestCase.is_quarantined == True).order_by(TestCase.updated_at.desc()).all()',
        'return db.query(TestCase).filter(TestCase.workspace_id == None, TestCase.is_quarantined == True).order_by(TestCase.updated_at.desc()).all()'
    ),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"Fixed: {old[:60]}...")
    else:
        print(f"NOT FOUND: {old[:60]}...")

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)

print("Done!")
