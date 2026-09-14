import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

# The second dispatch call is inside enqueue_test
idx = content.find('def enqueue_test')
end = content.find('def list_runs', idx)

body_text = content[idx:end]
new_body_text = re.sub(r'\s*workspace_id=body\.workspace_id if body\.workspace_id else \(tc\.workspace_id if test_case_id and tc else None\),', '', body_text)

content = content[:idx] + new_body_text + content[end:]

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)

print("Fixed second dispatch")
