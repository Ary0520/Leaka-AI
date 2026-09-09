import sys

with open('backend/app/schemas.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '    login_hint: Optional[str] = None\n\n\nclass ApplicationUpdate',
    '    login_hint: Optional[str] = None\n    openapi_spec: Optional[str] = None\n\n\nclass ApplicationUpdate'
)

content = content.replace(
    '    login_hint: Optional[str] = None\n\n\nclass ApplicationOut',
    '    login_hint: Optional[str] = None\n    openapi_spec: Optional[str] = None\n\n\nclass ApplicationOut'
)

content = content.replace(
    '    login_hint: Optional[str] = None\n    created_at: datetime',
    '    login_hint: Optional[str] = None\n    openapi_spec: Optional[str] = None\n    created_at: datetime'
)

with open('backend/app/schemas.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated schemas.py')
