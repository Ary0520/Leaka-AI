import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

# Fix _dispatch_run_task call
idx = content.find('task_id = _dispatch_run_task(')
end = content.find(')', idx)

dispatch_call = content[idx:end]
new_dispatch_call = re.sub(r'\s*workspace_id=body\.workspace_id if body\.workspace_id else \(tc\.workspace_id if test_case_id and tc else None\),', '', dispatch_call)

content = content[:idx] + new_dispatch_call + content[end:]

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)

print("Fixed _dispatch_run_task")
