import re

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    old = """            try:
                app_row = _get_owned_application(db, link_app_id, user)
            except HTTPException:
                app_row = None
            if app_row"""
    new = """            try:
                app_row = _get_owned_application(db, link_app_id, user)
            except HTTPException:
                app_row = None
            if app_row"""
            
    content = content.replace(old, new)
    
    # Let's also patch the coverage map one
    old_coverage = """    cases = None
    if not have_verdicts:
        # Fallback path: heuristic + enqueue a recompute for next time.
        if app_row.workspace_id:
            cases = db.query(TestCase).filter(TestCase.workspace_id == app_row.workspace_id).all()
        else:
            cases = db.query(TestCase).filter(TestCase.workspace_id == None, TestCase.owner_id == user["sub"]).all()"""
    new_coverage = """    cases = None
    if not have_verdicts:
        # Fallback path: heuristic + enqueue a recompute for next time.
        if app_row.workspace_id:
            cases = db.query(TestCase).filter(TestCase.workspace_id == app_row.workspace_id).all()
        else:
            cases = db.query(TestCase).filter(TestCase.workspace_id == None, TestCase.owner_id == user["sub"]).all()"""
    content = content.replace(old_coverage, new_coverage)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched remaining missed endpoints part 2!")

if __name__ == "__main__":
    patch_file(r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\patch_remaining2.py")
