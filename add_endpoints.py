import sys
import re

with open('backend/app/main.py', 'r') as f: content = f.read()

new_endpoints = """

@app.get("/api/quarantine", response_model=list[TestCaseOut])
def list_quarantined_tests(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return db.query(TestCase).filter(TestCase.owner_id == user["sub"], TestCase.is_quarantined == True).order_by(TestCase.updated_at.desc()).all()

@app.post("/api/tests/{id}/toggle-quarantine")
def toggle_quarantine(id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    tc = db.query(TestCase).filter(TestCase.id == id, TestCase.owner_id == user["sub"]).first()
    if not tc:
        raise HTTPException(404, "Test case not found")
    tc.is_quarantined = not tc.is_quarantined
    db.commit()
    return {"success": True, "is_quarantined": tc.is_quarantined}

@app.get("/api/run-groups")
def list_run_groups(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    # Group runs by run_group_id
    from sqlalchemy import func
    
    rows = db.query(
        TestRun.run_group_id,
        func.count(TestRun.id).label("total"),
        func.sum(func.cast(TestRun.is_successful, Integer)).label("passed"),
        func.max(TestRun.created_at).label("created_at")
    ).filter(
        TestRun.owner_id == user["sub"],
        TestRun.run_group_id != None
    ).group_by(TestRun.run_group_id).order_by(func.max(TestRun.created_at).desc()).limit(50).all()
    
    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "total_runs": r[1],
            "passed_runs": r[2] or 0,
            "failed_runs": r[1] - (r[2] or 0),
            "created_at": r[3]
        })
    return results

"""

content = content + new_endpoints

with open('backend/app/main.py', 'w') as f: f.write(content)
print('Added new endpoints for quarantine and run-groups!')
