with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

old_list_cases = '''def list_test_cases(
    suite_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    q = db.query(TestCase).filter(TestCase.workspace_id == None)'''

new_list_cases = '''def list_test_cases(
    suite_id: Optional[int] = None,
    workspace_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if workspace_id:
        q = db.query(TestCase).filter(TestCase.workspace_id == workspace_id)
    else:
        q = db.query(TestCase).filter(TestCase.workspace_id == None)'''

if old_list_cases in content:
    content = content.replace(old_list_cases, new_list_cases)
    print("Fixed list_test_cases")

old_quarantine = '''def list_quarantined_tests(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return db.query(TestCase).filter(TestCase.workspace_id == None, TestCase.is_quarantined == True).order_by(TestCase.updated_at.desc()).all()'''

new_quarantine = '''def list_quarantined_tests(workspace_id: Optional[int] = None, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    if workspace_id:
        return db.query(TestCase).filter(TestCase.workspace_id == workspace_id, TestCase.is_quarantined == True).order_by(TestCase.updated_at.desc()).all()
    else:
        return db.query(TestCase).filter(TestCase.workspace_id == None, TestCase.is_quarantined == True).order_by(TestCase.updated_at.desc()).all()'''

if old_quarantine in content:
    content = content.replace(old_quarantine, new_quarantine)
    print("Fixed list_quarantine")

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)
