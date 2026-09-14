import re

def fix_worker(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Reconstruct the broken RECOVERY RULES append block
    old_broken_block = """    task_parts.append(
        "\\n--- RECOVERY RULES ---\\n"
        "If you cannot find an element you need (e.g. a button disappeared or changed name)

    task_parts.append(
        "\\n--- INFINITE LOOP & DEBUGGING PREVENTION ---\\n"
        "If a UI action fails to produce the expected result after 2 attempts, "
        "immediately mark the test as FAILED using done(success=False, result='UI action failed after 2 attempts.'). "
        "Do NOT attempt to decompile JS bundles, extract tokens, write custom evaluate scripts, or debug the backend API. "
        "You are a UI test agent, not a backend developer. Your job is to report UI failures, not fix them."
    )
, DO NOT fail immediately. "
        "Instead, call the `recover_missing_element` action with a description of what you are looking for. "
        "It will use AI semantic search over past test runs to find the element's new location."
    )"""

    fixed_block = """    task_parts.append(
        "\\n--- RECOVERY RULES ---\\n"
        "If you cannot find an element you need (e.g. a button disappeared or changed name), DO NOT fail immediately. "
        "Instead, call the `recover_missing_element` action with a description of what you are looking for. "
        "It will use AI semantic search over past test runs to find the element's new location."
    )

    task_parts.append(
        "\\n--- INFINITE LOOP & DEBUGGING PREVENTION ---\\n"
        "If a UI action fails to produce the expected result after 2 attempts, "
        "immediately mark the test as FAILED using done(success=False, result='UI action failed after 2 attempts.'). "
        "Do NOT attempt to decompile JS bundles, extract tokens, write custom evaluate scripts, or debug the backend API. "
        "You are a UI test agent, not a backend developer. Your job is to report UI failures, not fix them."
    )"""

    if old_broken_block in content:
        content = content.replace(old_broken_block, fixed_block)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Fixed worker.py")
    else:
        print("Could not find exact broken block!")

fix_worker(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\worker.py')
