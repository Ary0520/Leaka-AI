with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

# Fix list_run_groups — it's the old version without workspace_id support
old = '''def list_run_groups(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    # Group runs by run_group_id
    from sqlalchemy import func, Integer
    
    rows = db.query(
        TestRun.run_group_id,
        func.count(TestRun.id).label("total"),
        func.sum(func.cast(TestRun.is_successful, Integer)).label("passed"),
        func.max(TestRun.created_at).label("created_at")
    ).filter(
        TestRun.owner_id == user["sub"],
        TestRun.run_group_id != None
    ).group_by(TestRun.run_group_id).order_by(func.max(TestRun.created_at).desc()).limit(50).all()'''

new = '''def list_run_groups(workspace_id: Optional[int] = None, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    # Group runs by run_group_id
    from sqlalchemy import func, Integer
    
    base_q = db.query(
        TestRun.run_group_id,
        func.count(TestRun.id).label("total"),
        func.sum(func.cast(TestRun.is_successful, Integer)).label("passed"),
        func.max(TestRun.created_at).label("created_at")
    ).filter(TestRun.run_group_id != None)
    
    if workspace_id:
        base_q = base_q.filter(TestRun.workspace_id == workspace_id)
    else:
        base_q = base_q.filter(TestRun.workspace_id == None)
    
    rows = base_q.group_by(TestRun.run_group_id).order_by(func.max(TestRun.created_at).desc()).limit(50).all()'''

if old in content:
    content = content.replace(old, new)
    print("Fixed list_run_groups")
else:
    print("Pattern not found, searching...")
    idx = content.find("TestRun.owner_id == user")
    print(repr(content[max(0,idx-200):idx+200]))

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)
