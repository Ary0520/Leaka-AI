import re

def patch_main_vault_prompts_no_auth():
    path = r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py"
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    old_prompts = """@app.post("/api/vault/prompts")
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

    new_prompts = """@app.post("/api/vault/prompts")
def store_vault_prompts(body: VaultPromptsRequest, db: Session = Depends(get_db)):
    # The recorded NL prompts from the extension.
    # Note: In a full production launch, we would use an Extension API Key here.
    
    prompt_str = "\\n".join([f"{i+1}. {p}" for i, p in enumerate(body.prompts)])
    
    workspace_id = None
    if body.workspace_id and body.workspace_id != "personal":
        try:
            workspace_id = int(body.workspace_id)
        except ValueError:
            pass
            
    # Find any user to assign this to (for demo purposes)
    from .models import WorkspaceMember
    owner = "extension-recorded-user"
    if workspace_id:
        member = db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == workspace_id).first()
        if member:
            owner = member.user_id

    tc = TestCase(
        owner_id=owner,
        workspace_id=workspace_id,
        name=f"Recorded Flow ({len(body.prompts)} steps)",
        prompt=f"Execute the following recorded flow precisely:\\n{prompt_str}",
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)
    
    return {"status": "ok", "message": "Test Case created successfully from recorded flow.", "test_case_id": tc.id}"""

    old_cookies = """@app.post("/api/vault/cookies")
def store_vault_cookies(body: VaultCookiesRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):"""
    
    new_cookies = """@app.post("/api/vault/cookies")
def store_vault_cookies(body: VaultCookiesRequest, db: Session = Depends(get_db)):"""

    content = content.replace(old_prompts, new_prompts)
    content = content.replace(old_cookies, new_cookies)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched main.py to remove auth for extension test")

if __name__ == "__main__":
    patch_main_vault_prompts_no_auth()
