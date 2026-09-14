import re
import glob

def fix_use_client(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if '"use client";' in content or "'use client';" in content:
        # Remove it from wherever it is
        content = content.replace('"use client";\n', '')
        content = content.replace("'use client';\n", '')
        content = content.replace('"use client"', '')
        content = content.replace("'use client'", '')
        
        # Put it at the very top
        content = '"use client";\n' + content.lstrip()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

for path in glob.glob(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\app\**\*.tsx', recursive=True):
    fix_use_client(path)

print("Fixed use client directives")
