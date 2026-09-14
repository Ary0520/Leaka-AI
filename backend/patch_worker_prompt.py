import re
import glob

def patch_worker(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    loop_prevention_rule = '''
    task_parts.append(
        "\\n--- INFINITE LOOP & DEBUGGING PREVENTION ---\\n"
        "If a UI action fails to produce the expected result after 2 attempts, "
        "immediately mark the test as FAILED using done(success=False, result='UI action failed after 2 attempts.'). "
        "Do NOT attempt to decompile JS bundles, extract tokens, write custom evaluate scripts, or debug the backend API. "
        "You are a UI test agent, not a backend developer. Your job is to report UI failures, not fix them."
    )
'''
    if '--- INFINITE LOOP & DEBUGGING PREVENTION ---' in content:
        print(f"Already patched {filepath}")
        return

    # Find where OBSERVATION RULES or RECOVERY RULES are appended to task_parts
    if 'task_parts.append(' in content and 'RECOVERY RULES' in content:
        # Insert after RECOVERY RULES
        idx = content.find('--- RECOVERY RULES ---')
        end_idx = content.find(')', idx) + 1
        
        content = content[:end_idx] + "\n" + loop_prevention_rule + content[end_idx:]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Patched {filepath}")

patch_worker(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\worker.py')
