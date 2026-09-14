import re

def fix_main(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    old_code = """        if run.workspace_id:
            member = db.query(WorkspaceMember).filter("""
            
    new_code = """        if run.workspace_id:
            from .models import WorkspaceMember
            member = db.query(WorkspaceMember).filter("""

    if old_code in content:
        content = content.replace(old_code, new_code)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Fixed WorkspaceMember NameError in _get_owned_run")
    else:
        print("Could not find the exact code block to replace!")

fix_main(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py')
