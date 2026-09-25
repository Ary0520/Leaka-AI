import re

def patch_main_vault_prompts():
    path = r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py"
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    old_prompts = """@app.post("/api/vault/prompts")
def store_vault_prompts(body: VaultPromptsRequest, db: Session = Depends(get_db)):
    # The recorded NL prompts from the extension.
    # We could save this as a draft TestCase or send to frontend via websocket.
    print(f"[VAULT] Received {len(body.prompts)} prompts in workspace {body.workspace_id}")
    for p in body.prompts:
        print(f" - {p}")
    return {"status": "ok", "message": "Prompts received successfully."}"""

    new_prompts = """@app.post("/api/vault/prompts")
def store_vault_prompts(body: VaultPromptsRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    # The recorded NL prompts from the extension.
    # We automatically save this as a draft TestCase in the workspace.
    
    prompt_str = "\\n".join([f"{i+1}. {p}" for i, p in enumerate(body.prompts)])
    
    workspace_id = None
    if body.workspace_id and body.workspace_id != "personal":
        try:
            workspace_id = int(body.workspace_id)
        except ValueError:
            pass
            
    tc = TestCase(
        owner_id=user["sub"],
        workspace_id=workspace_id,
        name=f"Recorded Flow ({len(body.prompts)} steps)",
        prompt=f"Execute the following recorded flow precisely:\\n{prompt_str}",
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)
    
    return {"status": "ok", "message": "Test Case created successfully from recorded flow.", "test_case_id": tc.id}"""

    # We also need to add get_current_user to the params of store_vault_cookies
    old_cookies = """@app.post("/api/vault/cookies")
def store_vault_cookies(body: VaultCookiesRequest, db: Session = Depends(get_db)):"""
    
    new_cookies = """@app.post("/api/vault/cookies")
def store_vault_cookies(body: VaultCookiesRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):"""

    content = content.replace(old_prompts, new_prompts)
    content = content.replace(old_cookies, new_cookies)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched main.py for actual Vault implementation")

if __name__ == "__main__":
    patch_main_vault_prompts()
