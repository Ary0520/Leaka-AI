import re

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # The authorization check to inject
    auth_check = """
    if workspace_id:
        from .models import WorkspaceMember
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user["sub"]
        ).first()
        if not member:
            raise HTTPException(404, "Workspace not found or access denied")
"""

    def inject_auth(func_name, code):
        pattern = re.compile(r'(def ' + func_name + r'\(.*?\):)', re.DOTALL)
        match = pattern.search(code)
        if match:
            sig = match.group(1)
            # Find the end of the signature
            idx = match.end()
            return code[:idx] + auth_check + code[idx:]
        return code

    content = inject_auth("list_test_cases", content)
    content = inject_auth("list_suites", content)
    content = inject_auth("list_runs", content)
    content = inject_auth("list_quarantined_tests", content)
    content = inject_auth("list_run_groups", content)
    
    # For dashboard_kpis, the owner var is set at the top. Let's insert after owner = user["sub"]
    pattern = re.compile(r'(def dashboard_kpis\(.*?\):\n\s+owner = user\["sub"\])', re.DOTALL)
    match = pattern.search(content)
    if match:
        idx = match.end()
        content = content[:idx] + auth_check + content[idx:]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched list endpoints!")

if __name__ == "__main__":
    patch_file(r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py")
