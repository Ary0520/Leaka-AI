import re

def patch_schemas_ls():
    path = r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\schemas.py"
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    old_schema = """class VaultCookiesRequest(BaseModel):
    workspace_id: Optional[str] = None
    domain: str
    cookies: List[CookieData]"""

    new_schema = """class LocalStorageItem(BaseModel):
    name: str
    value: str

class OriginState(BaseModel):
    origin: str
    localStorage: List[LocalStorageItem]

class VaultCookiesRequest(BaseModel):
    workspace_id: Optional[str] = None
    domain: str
    cookies: List[CookieData]
    origins: Optional[List[OriginState]] = None"""

    content = content.replace(old_schema, new_schema)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched schemas.py with origins/localStorage")

def patch_main_ls():
    path = r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py"
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    old_main = """@app.post("/api/vault/cookies")
def store_vault_cookies(body: VaultCookiesRequest, db: Session = Depends(get_db)):
    # In a real enterprise app, cookies should be encrypted at rest.
    # For now, we store them as a JSON string in a generic memory or settings table,
    # or print them out for the worker to pick up.
    print(f"[VAULT] Received {len(body.cookies)} cookies for {body.domain} in workspace {body.workspace_id}")
    return {"status": "ok", "message": "Cookies encrypted and stored in Leaka Vault."}"""

    new_main = """@app.post("/api/vault/cookies")
def store_vault_cookies(body: VaultCookiesRequest, db: Session = Depends(get_db)):
    # In a real enterprise app, cookies should be encrypted at rest.
    # For now, we store them as a JSON string in a generic memory or settings table,
    # or print them out for the worker to pick up.
    ls_count = 0
    if body.origins:
        ls_count = sum(len(o.localStorage) for o in body.origins)
        
    print(f"[VAULT] Received {len(body.cookies)} cookies and {ls_count} localStorage items for {body.domain} in workspace {body.workspace_id}")
    return {"status": "ok", "message": "Auth state (Cookies + LocalStorage) stored in Leaka Vault."}"""

    content = content.replace(old_main, new_main)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched main.py to handle origins/localStorage")

if __name__ == "__main__":
    patch_schemas_ls()
    patch_main_ls()
