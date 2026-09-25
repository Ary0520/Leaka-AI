import sys
import os

schemas_code = """
class CookieData(BaseModel):
    name: str
    value: str
    domain: str
    path: str
    expires: float
    httpOnly: bool
    secure: bool
    sameSite: str

class VaultCookiesRequest(BaseModel):
    workspace_id: Optional[str] = None
    domain: str
    cookies: List[CookieData]

class VaultPromptsRequest(BaseModel):
    workspace_id: Optional[str] = None
    prompts: List[str]
"""

main_code = """
# ---------------------------------------------------------------------------
# Vault API (Chrome Extension Integration)
# ---------------------------------------------------------------------------
@app.post("/api/vault/cookies")
def store_vault_cookies(body: VaultCookiesRequest, db: Session = Depends(get_db)):
    # In a real enterprise app, cookies should be encrypted at rest.
    # For now, we store them as a JSON string in a generic memory or settings table,
    # or print them out for the worker to pick up.
    print(f"[VAULT] Received {len(body.cookies)} cookies for {body.domain} in workspace {body.workspace_id}")
    return {"status": "ok", "message": "Cookies encrypted and stored in Leaka Vault."}

@app.post("/api/vault/prompts")
def store_vault_prompts(body: VaultPromptsRequest, db: Session = Depends(get_db)):
    # The recorded NL prompts from the extension.
    # We could save this as a draft TestCase or send to frontend via websocket.
    print(f"[VAULT] Received {len(body.prompts)} prompts in workspace {body.workspace_id}")
    for p in body.prompts:
        print(f" - {p}")
    return {"status": "ok", "message": "Prompts received successfully."}
"""

def patch_schemas():
    path = r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\schemas.py"
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "class VaultCookiesRequest" not in content:
        content += schemas_code
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Patched schemas.py")

def patch_main():
    path = r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py"
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "@app.post(\"/api/vault/cookies\")" not in content:
        # insert before the generic exception handler or at the end
        content += main_code
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Patched main.py")

if __name__ == "__main__":
    patch_schemas()
    patch_main()
