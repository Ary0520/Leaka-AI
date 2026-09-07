import sys

with open('frontend/src/lib/api.ts', 'r') as f: content = f.read()

content = content.replace('/api/tests/\/toggle-quarantine', '/api/tests//toggle-quarantine')
content = content.replace('/api/test-suites/\/run', '/api/test-suites//run')

with open('frontend/src/lib/api.ts', 'w') as f: f.write(content)
