import re

def fix_explore(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    loop_prevention_rule = """
    task_parts.append(
        "\\n--- INFINITE LOOP & DEBUGGING PREVENTION ---\\n"
        "If a UI action fails to produce the expected result after 2 attempts, "
        "immediately stop trying that specific path. "
        "Do NOT attempt to decompile JS bundles, extract tokens, write custom evaluate scripts, or debug the backend API. "
        "You are an automated explorer, not a backend developer. If a page or form is broken, move on."
    )
"""
    # Just append it before `task_text = "\\n".join(task_parts)`
    idx = content.find('task_text = "\\n".join(task_parts)')
    
    if '--- INFINITE LOOP & DEBUGGING PREVENTION ---' in content:
        return
        
    content = content[:idx] + loop_prevention_rule + "\n    " + content[idx:]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed explore_worker.py")

fix_explore(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\explore_worker.py')
