import re

def patch_backend_for_vault_ui():
    schemas_path = r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\schemas.py"
    with open(schemas_path, 'r', encoding='utf-8') as f:
        schemas_content = f.read()

    # Add environment_id to Vault requests
    schemas_content = schemas_content.replace(
        "class VaultCookiesRequest(BaseModel):\n    workspace_id: Optional[str] = None",
        "class VaultCookiesRequest(BaseModel):\n    workspace_id: Optional[str] = None\n    environment_id: Optional[int] = None"
    )
    schemas_content = schemas_content.replace(
        "class VaultPromptsRequest(BaseModel):\n    workspace_id: Optional[str] = None",
        "class VaultPromptsRequest(BaseModel):\n    workspace_id: Optional[str] = None\n    environment_id: Optional[int] = None"
    )

    # Add schema for Vault Context
    vault_context_schema = """
class VaultEnvironmentOut(BaseModel):
    id: int
    name: str

class VaultApplicationOut(BaseModel):
    id: int
    name: str
    environments: List[VaultEnvironmentOut]

class VaultContextResponse(BaseModel):
    applications: List[VaultApplicationOut]
"""
    if "class VaultContextResponse" not in schemas_content:
        schemas_content += vault_context_schema

    with open(schemas_path, 'w', encoding='utf-8') as f:
        f.write(schemas_content)


    main_path = r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py"
    with open(main_path, 'r', encoding='utf-8') as f:
        main_content = f.read()

    # Make sure we import the new schemas
    if "VaultContextResponse" not in main_content:
        main_content = main_content.replace(
            "VaultPromptsRequest,",
            "VaultPromptsRequest,\n    VaultContextResponse,\n    VaultApplicationOut,\n    VaultEnvironmentOut,"
        )

    # New Context Endpoint
    context_endpoint = """
@app.get("/api/vault/context", response_model=VaultContextResponse)
def get_vault_context(db: Session = Depends(get_db)):
    # Note: No auth for testing purposes. In prod, use Depends(get_current_user)
    from .models import Application, Environment
    apps = db.query(Application).all() # Just grab all for demo extension
    
    result = []
    for app in apps:
        envs = db.query(Environment).filter(Environment.application_id == app.id).all()
        result.append(VaultApplicationOut(
            id=app.id,
            name=app.name,
            environments=[VaultEnvironmentOut(id=e.id, name=e.name) for e in envs]
        ))
    return VaultContextResponse(applications=result)
"""
    if "@app.get(\"/api/vault/context\"" not in main_content:
        # insert before the cookies post
        main_content = main_content.replace("@app.post(\"/api/vault/cookies\")", context_endpoint + "\n@app.post(\"/api/vault/cookies\")")

    # Update store_vault_cookies
    old_cookies = """@app.post("/api/vault/cookies")
def store_vault_cookies(body: VaultCookiesRequest, db: Session = Depends(get_db)):
    # In a real enterprise app, cookies should be encrypted at rest.
    # For now, we store them as a JSON string in a generic memory or settings table,
    # or print them out for the worker to pick up.
    ls_count = 0
    if body.origins:
        ls_count = sum(len(o.localStorage) for o in body.origins)
        
    print(f"[VAULT] Received {len(body.cookies)} cookies and {ls_count} localStorage items for {body.domain} in workspace {body.workspace_id}")
    return {"status": "ok", "message": "Auth state (Cookies + LocalStorage) stored in Leaka Vault."}"""

    new_cookies = """@app.post("/api/vault/cookies")
def store_vault_cookies(body: VaultCookiesRequest, db: Session = Depends(get_db)):
    import json
    ls_count = 0
    if body.origins:
        ls_count = sum(len(o.localStorage) for o in body.origins)
        
    print(f"[VAULT] Received {len(body.cookies)} cookies and {ls_count} localStorage items for {body.domain}")
    
    if body.environment_id:
        from .models import Environment
        env = db.query(Environment).filter(Environment.id == body.environment_id).first()
        if env:
            # Build Playwright storageState JSON
            state = {
                "cookies": [c.dict() for c in body.cookies],
                "origins": [o.dict() for o in body.origins] if body.origins else []
            }
            env.auth_strategy = "state_cache"
            env.auth_state_template = json.dumps(state)
            db.commit()
            print(f"[VAULT] Successfully saved Golden State to Environment {env.name} ({env.id})")
            
    return {"status": "ok", "message": "Auth state successfully saved to Environment."}"""

    main_content = main_content.replace(old_cookies, new_cookies)

    # Update store_vault_prompts
    old_prompts = """    tc = TestCase(
        owner_id=owner,
        workspace_id=workspace_id,
        name=f"Recorded Flow ({len(body.prompts)} steps)",
        prompt=f"Execute the following recorded flow precisely:\\n{prompt_str}",
    )"""

    new_prompts = """    # If environment_id is provided, link it
    from .models import Environment
    app_id = None
    if body.environment_id:
        env = db.query(Environment).filter(Environment.id == body.environment_id).first()
        if env:
            app_id = env.application_id

    tc = TestCase(
        owner_id=owner,
        workspace_id=workspace_id,
        name=f"Recorded Flow ({len(body.prompts)} steps)",
        prompt=f"Execute the following recorded flow precisely:\\n{prompt_str}",
        environment_id=body.environment_id,
        # suite_id = None, but we could link it to an app if we had application_id on TestCase
    )"""
    main_content = main_content.replace(old_prompts, new_prompts)

    with open(main_path, 'w', encoding='utf-8') as f:
        f.write(main_content)
    print("Backend patched for Environment linking")

if __name__ == "__main__":
    patch_backend_for_vault_ui()
