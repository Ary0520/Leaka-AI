import re

def fix_imports():
    path = r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py"
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "VaultCookiesRequest" not in content[:2000]:  # roughly where imports are
        # find the end of the from .schemas import block
        # it ends with a closing parenthesis
        new_import = "    VaultCookiesRequest,\n    VaultPromptsRequest,\n"
        content = content.replace("    ApplicationCreate,\n", "    ApplicationCreate,\n" + new_import)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Fixed imports in main.py")

if __name__ == "__main__":
    fix_imports()
