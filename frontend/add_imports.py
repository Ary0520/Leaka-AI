import re

def add_import(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'import { useWorkspace } from "@/app/providers";' not in content:
        content = 'import { useWorkspace } from "@/app/providers";\n' + content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

add_import(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\new\page.tsx')
add_import(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\suites\page.tsx')
add_import(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\tests\page.tsx')
add_import(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\ci\page.tsx')

print("Added imports")
