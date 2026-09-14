with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

old_list_runs = '''def list_runs(
    status: Optional[TestRunStatus] = None,
    test_case_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    q = db.query(TestRun).filter(TestRun.workspace_id == None)'''

new_list_runs = '''def list_runs(
    status: Optional[TestRunStatus] = None,
    test_case_id: Optional[int] = None,
    workspace_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if workspace_id:
        q = db.query(TestRun).filter(TestRun.workspace_id == workspace_id)
    else:
        q = db.query(TestRun).filter(TestRun.workspace_id == None)'''

if old_list_runs in content:
    content = content.replace(old_list_runs, new_list_runs)
    print("Fixed list_runs")
else:
    print("list_runs not found")

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)
