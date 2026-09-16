import re

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Patch dashboard_health
    # We'll just replace the signature and the query
    old_health_sig = """def dashboard_health(
    limit: int = 14,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    owner = user["sub"]
    result = []

    # 1. Test cases that have associated runs
    cases = (
        db.query(TestCase)
        .filter(TestCase.owner_id == owner)
        .order_by(TestCase.created_at.asc())
        .all()
    )"""
    new_health_sig = """def dashboard_health(
    workspace_id: Optional[int] = None,
    limit: int = 14,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    owner = user["sub"]
    result = []
    
    if workspace_id:
        from .models import WorkspaceMember
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user["sub"]
        ).first()
        if not member:
            raise HTTPException(404, "Workspace not found or access denied")

    # 1. Test cases that have associated runs
    if workspace_id:
        cases = (
            db.query(TestCase)
            .filter(TestCase.workspace_id == workspace_id)
            .order_by(TestCase.created_at.asc())
            .all()
        )
    else:
        cases = (
            db.query(TestCase)
            .filter(TestCase.workspace_id == None, TestCase.owner_id == owner)
            .order_by(TestCase.created_at.asc())
            .all()
        )"""
    content = content.replace(old_health_sig, new_health_sig)
    
    old_runs = """        runs = (
            db.query(TestRun)
            .filter(TestRun.test_case_id == tc.id, TestRun.owner_id == owner)
            .order_by(TestRun.created_at.desc())
            .limit(limit)
            .all()
        )"""
    new_runs = """        if workspace_id:
            runs = (
                db.query(TestRun)
                .filter(TestRun.test_case_id == tc.id, TestRun.workspace_id == workspace_id)
                .order_by(TestRun.created_at.desc())
                .limit(limit)
                .all()
            )
        else:
            runs = (
                db.query(TestRun)
                .filter(TestRun.test_case_id == tc.id, TestRun.workspace_id == None, TestRun.owner_id == owner)
                .order_by(TestRun.created_at.desc())
                .limit(limit)
                .all()
            )"""
    content = content.replace(old_runs, new_runs)
    
    # 2. Patch trigger_pr_check
    old_pr = """        tc = db.query(TestCase).filter(
            TestCase.id == tc_id, TestCase.owner_id == owner_id
        ).first()"""
    new_pr = """        try:
            tc = _get_owned_test_case(db, tc_id, user={"sub": owner_id})
        except HTTPException:
            tc = None"""
    content = content.replace(old_pr, new_pr)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched remaining missed endpoints!")

if __name__ == "__main__":
    patch_file(r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py")
