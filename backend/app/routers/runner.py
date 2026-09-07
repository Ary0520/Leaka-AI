from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import TestRun, Environment, TestFixture, TestScreenshot
from ..auth import get_runner_user
import json
from datetime import datetime

router = APIRouter(prefix="/api/runner/v1/jobs", tags=["Runner"])

@router.post("/{job_id}/pull")
def pull_job(job_id: str, db: Session = Depends(get_db), runner_user: dict = Depends(get_runner_user),
    background_tasks: BackgroundTasks = None):
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

def categorize_failure_bg(run_id: int):
    from app.database import SessionLocal
    from app.llm import get_llm_for_provider
    from app.models import TestRun
    import json
    
    db = SessionLocal()
    try:
        run = db.query(TestRun).filter(TestRun.id == run_id).first()
        if not run or run.status != "FAILED" or run.rca_category:
            return
            
        llm = get_llm_for_provider()
        
        prompt = f"""You are an expert QA engineer. Analyze the following end-to-end test failure and categorize the root cause.
Return ONLY ONE of the following exact strings as your entire response. Do not add any markdown, punctuation, or explanation.

Categories:
- "App Bug: 404 Not Found" (If a page or endpoint was explicitly not found)
- "App Bug: UI Changed" (If elements couldn't be found because the layout or selectors changed)
- "App Bug: Assertion Failed" (If the app loaded, but didn't behave as expected)
- "Infra: DNS Resolution Failed" (If the target URL could not be resolved or network failed)
- "Infra: Timeout" (If the page took too long to load or respond)
- "Test Flake: Unknown" (If the error is ambiguous or transient)

Test Final Result:
{run.final_result}

Error Message:
{run.error_message}
"""
        response = llm.invoke(prompt)
        category = response.content.strip()
        
        valid_categories = [
            "App Bug: 404 Not Found", "App Bug: UI Changed", "App Bug: Assertion Failed",
            "Infra: DNS Resolution Failed", "Infra: Timeout", "Test Flake: Unknown"
        ]
        
        matched = "Test Flake: Unknown"
        for vc in valid_categories:
            if vc.lower() in category.lower():
                matched = vc
                break
                
        run.rca_category = matched
        db.commit()
    except Exception as e:
        print("RCA Categorization failed:", e)
    finally:
        db.close()


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
    runner_user: dict = Depends(get_runner_user),
    background_tasks: BackgroundTasks = None
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
    if status == "FAILED" and background_tasks:
        background_tasks.add_task(categorize_failure_bg, run.id)

    return {"success": True}