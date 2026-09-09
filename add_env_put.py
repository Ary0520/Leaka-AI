import sys

with open('backend/app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_route = '''
@app.put("/api/applications/{app_id}/environments/{env_id}", response_model=EnvironmentOut)
def update_environment(
    app_id: int,
    env_id: int,
    body: EnvironmentUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _get_owned_application(db, app_id, user)
    env_row = db.query(Environment).filter(Environment.id == env_id, Environment.application_id == app_id).first()
    if not env_row:
        raise HTTPException(404, "Environment not found")
        
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(env_row, field, value)
        
    db.commit()
    db.refresh(env_row)
    return env_row
'''

content = content.replace(
    '    db.refresh(env_row)\n    return env_row\n\n\n@app.delete("/api/applications/{app_id}/environments/{env_id}")',
    '    db.refresh(env_row)\n    return env_row\n' + new_route + '\n\n@app.delete("/api/applications/{app_id}/environments/{env_id}")'
)

with open('backend/app/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated main.py with update_environment route')
