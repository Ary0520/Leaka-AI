import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

# Fix list_runs
content = re.sub(
    r'q = db\.query\(TestRun\)\.join.*?\.filter\(Application\.workspace_id == workspace_id\)',
    r'q = db.query(TestRun).filter(TestRun.workspace_id == workspace_id)',
    content
)

# Fix list_test_cases
content = re.sub(
    r'q = db\.query\(TestCase\)\.join.*?\.filter\(Application\.workspace_id == workspace_id\)',
    r'q = db.query(TestCase).filter(TestCase.workspace_id == workspace_id)',
    content
)

# Fix list_run_groups
content = re.sub(
    r'groups = q\.join\(TestCase.*?\)\.filter\(Application\.workspace_id == workspace_id, TestRun\.run_group_id != None\)',
    r'groups = q.filter(TestRun.workspace_id == workspace_id, TestRun.run_group_id != None)',
    content
)

# Fix list_quarantined_tests
content = re.sub(
    r'return db\.query\(TestCase\)\.join\(Application.*?\.filter\(Application\.workspace_id == workspace_id, TestCase\.is_quarantined == True\)\.order_by\(TestCase\.updated_at\.desc\(\)\)\.all\(\)',
    r'return db.query(TestCase).filter(TestCase.workspace_id == workspace_id, TestCase.is_quarantined == True).order_by(TestCase.updated_at.desc()).all()',
    content
)

# Fix dashboard_kpis
content = re.sub(
    r'def apply_filters\(query, model\):\s+if workspace_id:\s+return query\.join\(TestCase.*?\.filter\(Application\.workspace_id == workspace_id\)\s+else:\s+return query\.filter\(model\.owner_id == owner\)',
    r'def apply_filters(query, model):\n        if workspace_id:\n            return query.filter(model.workspace_id == workspace_id)\n        else:\n            return query.filter(model.owner_id == owner)',
    content
)

content = re.sub(
    r'def apply_testcase_filters\(query\):\s+if workspace_id:\s+return query\.join\(Application.*?\.filter\(Application\.workspace_id == workspace_id\)\s+else:\s+return query\.filter\(TestCase\.owner_id == owner\)',
    r'def apply_testcase_filters(query):\n        if workspace_id:\n            return query.filter(TestCase.workspace_id == workspace_id)\n        else:\n            return query.filter(TestCase.owner_id == owner)',
    content
)


with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)

print("Fixed main.py")
