from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import TestRun, Environment, TestFixture, TestScreenshot
from ..auth import get_runner_user
import json
from datetime import datetime

router = APIRouter(prefix="/api/runner/v1/jobs", tags=["Runner"])

@router.post("/{job_id}/pull")
def pull_job(job_id: str, db: Session = Depends(get_db), runner_user: dict = Depends(get_runner_user)):
    run = db.query(TestRun).filter(TestRun.job_id == job_id, TestRun.owner_id == runner_user["sub"]).first()
    if not run:
        raise HTTPException(404, "Job not found")
        
    env = None
    if run.environment_id:
        env = db.query(Environment).filter(Environment.id == run.environment_id).first()
        
    fixture = None
    if run.fixture_id:
        fixture = db.query(TestFixture).filter(TestFixture.id == run.fixture_id).first()
        
    return {
        "job_id": run.job_id,
        "name": run.name,
        "prompt": run.prompt,
        "target_url": run.target_url,
        "success_criteria": run.success_criteria,
        "assertions": json.loads(run.assertions) if run.assertions else None,
        "environment": {
            "auth_strategy": env.auth_strategy if env else "none",
            "auth_api_url": env.auth_api_url if env else None,
            "auth_payload": env.auth_payload if env else None,
            "auth_token_path": env.auth_token_path if env else None,
            "auth_state_template": env.auth_state_template if env else None,
            "variables": env.variables if env else None,
            "policies": env.policies if env else None
        } if env else None,
        "fixture": {
            "setup_api_url": fixture.setup_api_url if fixture else None,
            "setup_payload": fixture.setup_payload if fixture else None,
            "teardown_api_url": fixture.teardown_api_url if fixture else None,
            "teardown_payload": fixture.teardown_payload if fixture else None,
        } if fixture else None
    }

@router.post("/{job_id}/status")
def update_job_status(
    job_id: str, 
    status: str = Body(...), 
    live_steps: list = Body(default=[]),
    result_summary: str = Body(default=None),
    final_result: str = Body(default=None),
    error_message: str = Body(default=None),
    is_successful: bool = Body(default=None),
    has_visual_proof: bool = Body(default=None),
    db: Session = Depends(get_db), 
    runner_user: dict = Depends(get_runner_user)
):
    run = db.query(TestRun).filter(TestRun.job_id == job_id, TestRun.owner_id == runner_user["sub"]).first()
    if not run:
        raise HTTPException(404, "Job not found")
        
    run.status = status
    if status == "RUNNING" and not run.started_at:
        run.started_at = datetime.utcnow()
    elif status in ["COMPLETED", "FAILED"]:
        run.completed_at = datetime.utcnow()
        if run.started_at:
            run.duration_seconds = int((run.completed_at - run.started_at).total_seconds())
            
    if live_steps:
        run.live_steps = json.dumps(live_steps)
        run.total_steps = len(live_steps)
        
    if result_summary is not None: run.result_summary = result_summary
    if final_result is not None: run.final_result = final_result
    if error_message is not None: run.error_message = error_message
    if is_successful is not None: run.is_successful = is_successful
    if has_visual_proof is not None: run.has_visual_proof = has_visual_proof
    
    db.commit()
    
    # If completed/failed, we could trigger RCA/Linear auto-ticketing asynchronously here.
    return {"success": True}