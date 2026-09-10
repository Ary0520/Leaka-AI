import sys

with open('backend/app/explore_worker.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '        from browser_use.controller.service import Controller\n',
    '        from browser_use import Controller\n'
)

with open('backend/app/explore_worker.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated explore_worker.py again')
