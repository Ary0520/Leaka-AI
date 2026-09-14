import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

# Add _get_owned_test_case
get_tc_func = '''def _get_owned_test_case(db: Session, tc_id: int, user: dict) -> "TestCase":
    tc = db.query(TestCase).filter(TestCase.id == tc_id).first()
    if not tc:
        raise HTTPException(404, "Test case not found")
        
    user_id = user.get("sub")
    if tc.owner_id == user_id:
        return tc
        
    if tc.workspace_id:
        from .models import WorkspaceMember
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == tc.workspace_id,
            WorkspaceMember.user_id == user_id
        ).first()
        if member:
            return tc
            
    raise HTTPException(404, "Test case not found")
'''

# Add _get_owned_suite
get_suite_func = '''def _get_owned_suite(db: Session, suite_id: int, user: dict) -> "TestSuite":
    s = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not s:
        raise HTTPException(404, "Suite not found")
        
    user_id = user.get("sub")
    if s.owner_id == user_id:
        return s
        
    if s.workspace_id:
        from .models import WorkspaceMember
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == s.workspace_id,
            WorkspaceMember.user_id == user_id
        ).first()
        if member:
            return s
            
    raise HTTPException(404, "Suite not found")
'''

# Insert these functions near _get_owned_run
content = content.replace('def _get_owned_run(', get_tc_func + '\n' + get_suite_func + '\ndef _get_owned_run(')

# Patch get_test_case
content = content.replace(
    'tc = db.query(TestCase).filter(TestCase.id == id, TestCase.owner_id == user["sub"]).first()\n    if not tc:\n        raise HTTPException(404, "Test case not found")\n    return tc',
    'return _get_owned_test_case(db, id, user)'
)

# Patch update_test_case
content = content.replace(
    'tc = db.query(TestCase).filter(TestCase.id == id, TestCase.owner_id == user["sub"]).first()\n    if not tc:\n        raise HTTPException(404, "Test case not found")\n    for',
    'tc = _get_owned_test_case(db, id, user)\n    for'
)

# Patch delete_test_case
content = content.replace(
    'tc = db.query(TestCase).filter(TestCase.id == id, TestCase.owner_id == user["sub"]).first()\n    if not tc:\n        raise HTTPException(404, "Test case not found")\n    db.delete(tc)',
    'tc = _get_owned_test_case(db, id, user)\n    db.delete(tc)'
)

# Patch toggle_quarantine
content = content.replace(
    'tc = db.query(TestCase).filter(TestCase.id == id, TestCase.owner_id == user["sub"]).first()\n    if not tc:\n        raise HTTPException(404, "Test case not found")',
    'tc = _get_owned_test_case(db, id, user)'
)

# Patch get_suite
content = content.replace(
    's = db.query(TestSuite).filter(TestSuite.id == id, TestSuite.owner_id == user["sub"]).first()\n    if not s:\n        raise HTTPException(404, "Suite not found")\n    return s',
    'return _get_owned_suite(db, id, user)'
)

# Patch update_suite
content = content.replace(
    's = db.query(TestSuite).filter(TestSuite.id == id, TestSuite.owner_id == user["sub"]).first()\n    if not s:\n        raise HTTPException(404, "Suite not found")\n    for',
    's = _get_owned_suite(db, id, user)\n    for'
)

# Patch delete_suite
content = content.replace(
    's = db.query(TestSuite).filter(TestSuite.id == id, TestSuite.owner_id == user["sub"]).first()\n    if not s:\n        raise HTTPException(404, "Suite not found")\n    db.delete(s)',
    's = _get_owned_suite(db, id, user)\n    db.delete(s)'
)

# Patch run_suite
content = content.replace(
    's = db.query(TestSuite).filter(TestSuite.id == id, TestSuite.owner_id == user["sub"]).first()\n    if not s:\n        raise HTTPException(404, "Suite not found")',
    's = _get_owned_suite(db, id, user)'
)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)

print("Patched all RBAC checks")
