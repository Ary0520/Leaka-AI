import sys

with open('backend/app/explore_worker.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '        from browser_use.browser.context import BrowserContext\n',
    ''
)

content = content.replace(
    '        async def recover_missing_element(intent: str, browser: BrowserContext) -> str:',
    '        async def recover_missing_element(intent: str, browser_session: BrowserSession) -> str:'
)

content = content.replace(
    '                page = await browser.get_current_page()',
    '                page = await browser_session.get_current_page()'
)

with open('backend/app/explore_worker.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated explore_worker.py')
