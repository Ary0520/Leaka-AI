import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

new_get = '''def _get_owned_run(
    db: Session,
    job_id: str,
    user: Optional[dict],
) -> "TestRun":
    run = db.query(TestRun).filter(TestRun.job_id == job_id).first()
    if not run:
        raise HTTPException(404, "Job not found")

    if user is not None:
        user_id = user.get("sub")
        if run.workspace_id:
            member = db.query(WorkspaceMember).filter(
                WorkspaceMember.workspace_id == run.workspace_id,
                WorkspaceMember.user_id == user_id
            ).first()
            if not member:
                raise HTTPException(404, "Job not found")
        elif run.owner_id and run.owner_id != user_id:
            raise HTTPException(404, "Job not found")

    return run'''

content = re.sub(r'def _get_owned_run\(.*?return run', new_get, content, flags=re.DOTALL)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)

print("Patched _get_owned_run")
