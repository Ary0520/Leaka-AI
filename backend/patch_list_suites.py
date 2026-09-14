import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

old_list_suites = '''@app.get("/api/test-suites", response_model=list[TestSuiteOut])
def list_suites(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return (
        db.query(TestSuite).filter(TestSuite.owner_id == user["sub"])
        .order_by(TestSuite.created_at.desc())
        .offset(skip).limit(limit).all()
    )'''

new_list_suites = '''@app.get("/api/test-suites", response_model=list[TestSuiteOut])
def list_suites(skip: int = 0, limit: int = 100, workspace_id: Optional[int] = None, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    if workspace_id:
        return (
            db.query(TestSuite).filter(TestSuite.workspace_id == workspace_id)
            .order_by(TestSuite.created_at.desc())
            .offset(skip).limit(limit).all()
        )
    else:
        return (
            db.query(TestSuite).filter(TestSuite.workspace_id == None, TestSuite.owner_id == user["sub"])
            .order_by(TestSuite.created_at.desc())
            .offset(skip).limit(limit).all()
        )'''

if old_list_suites in content:
    content = content.replace(old_list_suites, new_list_suites)
    print("Patched list_suites")
else:
    print("Could not find list_suites to patch")

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)
