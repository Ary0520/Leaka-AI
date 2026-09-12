import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

# 1. list_runs
runs_pattern = r'''@app\.get\("/api/runs", response_model=list\[TestRunOut\]\)
def list_runs\(
    status: Optional\[TestRunStatus\] = None,
    db: Session = Depends\(get_db\),
    user: dict = Depends\(get_current_user\),
\):
    q = db\.query\(TestRun\)\.filter\(TestRun\.owner_id == user\["sub"\]\)'''

runs_repl = '''@app.get("/api/runs", response_model=list[TestRunOut])
def list_runs(
    status: Optional[TestRunStatus] = None,
    workspace_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if workspace_id:
        q = db.query(TestRun).join(TestCase, TestCase.id == TestRun.test_case_id).join(Application, Application.id == TestCase.application_id).filter(Application.workspace_id == workspace_id)
    else:
        q = db.query(TestRun).filter(TestRun.owner_id == user["sub"])'''

content = re.sub(runs_pattern, runs_repl, content)


# 2. list_test_cases
cases_pattern = r'''@app\.get\("/api/test-cases", response_model=list\[TestCaseOut\]\)
def list_test_cases\(
    suite_id: Optional\[int\] = None,
    db: Session = Depends\(get_db\),
    user: dict = Depends\(get_current_user\),
\):
    q = db\.query\(TestCase\)\.filter\(TestCase\.owner_id == user\["sub"\]\)'''

cases_repl = '''@app.get("/api/test-cases", response_model=list[TestCaseOut])
def list_test_cases(
    suite_id: Optional[int] = None,
    workspace_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if workspace_id:
        q = db.query(TestCase).join(Application, Application.id == TestCase.application_id).filter(Application.workspace_id == workspace_id)
    else:
        q = db.query(TestCase).filter(TestCase.owner_id == user["sub"])'''

content = re.sub(cases_pattern, cases_repl, content)


# 3. list_run_groups
groups_pattern = r'''@app\.get\("/api/run-groups"\)
def list_run_groups\(db: Session = Depends\(get_db\), user: dict = Depends\(get_current_user\)\):
    groups = db\.query\(
        TestRun\.run_group_id,
        func\.count\(TestRun\.id\)\.label\("total_runs"\),
        func\.sum\(case\(\(TestRun\.is_successful == True, 1\), else_=0\)\)\.label\("passed_runs"\),
        func\.max\(TestRun\.created_at\)\.label\("created_at"\)
    \)\.filter\(
        TestRun\.owner_id == user\["sub"\],
        TestRun\.run_group_id != None
    \)'''

groups_repl = '''@app.get("/api/run-groups")
def list_run_groups(workspace_id: Optional[int] = None, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    q = db.query(
        TestRun.run_group_id,
        func.count(TestRun.id).label("total_runs"),
        func.sum(case((TestRun.is_successful == True, 1), else_=0)).label("passed_runs"),
        func.max(TestRun.created_at).label("created_at")
    )
    if workspace_id:
        groups = q.join(TestCase, TestCase.id == TestRun.test_case_id).join(Application, Application.id == TestCase.application_id).filter(Application.workspace_id == workspace_id, TestRun.run_group_id != None)
    else:
        groups = q.filter(TestRun.owner_id == user["sub"], TestRun.run_group_id != None)'''

content = re.sub(groups_pattern, groups_repl, content)

# 4. list_quarantined_tests
quarantine_pattern = r'''@app\.get\("/api/quarantine", response_model=list\[TestCaseOut\]\)
def list_quarantined_tests\(db: Session = Depends\(get_db\), user: dict = Depends\(get_current_user\)\):
    return db\.query\(TestCase\)\.filter\(TestCase\.owner_id == user\["sub"\], TestCase\.is_quarantined == True\)\.order_by\(TestCase\.updated_at\.desc\(\)\)\.all\(\)'''

quarantine_repl = '''@app.get("/api/quarantine", response_model=list[TestCaseOut])
def list_quarantined_tests(workspace_id: Optional[int] = None, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    if workspace_id:
        return db.query(TestCase).join(Application, Application.id == TestCase.application_id).filter(Application.workspace_id == workspace_id, TestCase.is_quarantined == True).order_by(TestCase.updated_at.desc()).all()
    else:
        return db.query(TestCase).filter(TestCase.owner_id == user["sub"], TestCase.is_quarantined == True).order_by(TestCase.updated_at.desc()).all()'''

content = re.sub(quarantine_pattern, quarantine_repl, content)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)

print("Patched main.py successfully.")
