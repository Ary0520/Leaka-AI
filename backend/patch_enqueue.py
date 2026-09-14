import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'r') as f:
    content = f.read()

# Replace run = TestRun( in enqueue_test
# There is a section:
#     if test_case_id:
#         tc = db.query(TestCase).filter(TestCase.id == test_case_id, TestCase.owner_id == owner_id).first()
# We should change it to also grab workspace_id
idx_enqueue = content.find('def enqueue_test')
end_enqueue = content.find('def list_runs', idx_enqueue)

enqueue_body = content[idx_enqueue:end_enqueue]

# Update TestRun instantiation to include workspace_id
enqueue_body = enqueue_body.replace(
    'test_case_id=test_case_id,',
    'test_case_id=test_case_id,\n        workspace_id=body.workspace_id if body.workspace_id else (tc.workspace_id if test_case_id and tc else None),'
)

content = content[:idx_enqueue] + enqueue_body + content[end_enqueue:]

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py', 'w') as f:
    f.write(content)

print("Patched main.py enqueue_test")
