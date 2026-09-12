import os
code = '''

# ===========================================================================
# WORKSPACE APIs (Institutional Identity)
# ===========================================================================

class WorkspaceCreate(BaseModel):
    organization_name: str
    workspace_name: str

class WorkspaceOut(BaseModel):
    id: int
    organization_id: int
    name: str
    created_at: datetime
    class Config:
        orm_mode = True

class AppTransfer(BaseModel):
    workspace_id: int

@app.post("/api/workspaces", response_model=WorkspaceOut)
def create_workspace(
    body: WorkspaceCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    from .models import Organization, Workspace, WorkspaceMember, RoleEnum
    
    org = Organization(name=body.organization_name)
    db.add(org)
    db.commit()
    db.refresh(org)
    
    workspace = Workspace(name=body.workspace_name, organization_id=org.id)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user["sub"],
        role=RoleEnum.ADMIN
    )
    db.add(member)
    db.commit()
    
    return workspace

@app.get("/api/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    from .models import Workspace, WorkspaceMember
    members = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user["sub"]).all()
    workspace_ids = [m.workspace_id for m in members]
    if not workspace_ids:
        return []
    workspaces = db.query(Workspace).filter(Workspace.id.in_(workspace_ids)).all()
    return workspaces

@app.post("/api/applications/{app_id}/transfer")
def transfer_application(
    app_id: int,
    body: AppTransfer,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    # Ensure they own the app directly
    app_row = db.query(Application).filter(Application.id == app_id).first()
    if not app_row:
        raise HTTPException(404, "Application not found")
    if app_row.owner_id != user["sub"]:
        raise HTTPException(403, "Only the direct owner can transfer the application")
        
    # Ensure they are an ADMIN in the target workspace
    from .models import WorkspaceMember, RoleEnum
    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == body.workspace_id,
        WorkspaceMember.user_id == user["sub"]
    ).first()
    if not member or member.role != RoleEnum.ADMIN:
        raise HTTPException(403, "You must be an ADMIN of the target workspace to transfer an application.")
        
    app_row.workspace_id = body.workspace_id
    db.commit()
    return {"status": "success", "workspace_id": body.workspace_id}
'''
with open(os.path.join(r'c:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py'), 'a') as f:
    f.write(code)
print('Appended Workspace APIs to main.py')
