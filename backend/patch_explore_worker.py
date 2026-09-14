import re

def patch_explore_worker(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    loop_prevention_rule = '''
        "\\n--- INFINITE LOOP & DEBUGGING PREVENTION ---\\n",
        "If a UI action fails to produce the expected result after 2 attempts, ",
        "immediately stop trying that specific path. ",
        "Do NOT attempt to decompile JS bundles, extract tokens, write custom evaluate scripts, or debug the backend API. ",
        "You are an automated explorer, not a backend developer. If a page or form is broken, move on.",
'''
    if '--- INFINITE LOOP & DEBUGGING PREVENTION ---' in content:
        print(f"Already patched {filepath}")
        return

    # Find the end of the task_parts array in explore_worker.py
    # Look for the last rule
    idx = content.find("business function you actually observed (authentication, billing, ")
    end_idx = content.find(']', idx)
    
    content = content[:end_idx] + loop_prevention_rule + content[end_idx:]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Patched {filepath}")

patch_explore_worker(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\explore_worker.py')
