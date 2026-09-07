import sys
import re

with open('backend/app/routers/runner.py', 'r') as f: content = f.read()

# Add BackgroundTasks import if missing
if 'BackgroundTasks' not in content:
    content = content.replace('from fastapi import APIRouter, Depends, HTTPException, Body', 'from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks')
    content = content.replace('from fastapi import APIRouter, Depends, Body, HTTPException', 'from fastapi import APIRouter, Depends, Body, HTTPException, BackgroundTasks')

# Inject the categorizer function before update_job_status
categorizer = """
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
        
        prompt = f"You are an expert QA engineer. Analyze the following end-to-end test failure and categorize the root cause.
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
"
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
"""

if 'categorize_failure_bg' not in content:
    content = content.replace('def update_job_status(', categorizer + '\n\ndef update_job_status(')

# Update update_job_status signature and body
content = content.replace('runner_user: dict = Depends(get_runner_user)', 'runner_user: dict = Depends(get_runner_user),\n    background_tasks: BackgroundTasks = None')

rca_trigger = """
    # If completed/failed, we could trigger RCA/Linear auto-ticketing asynchronously here.
    if status == "FAILED" and background_tasks:
        background_tasks.add_task(categorize_failure_bg, run.id)
"""
content = content.replace('    # If completed/failed, we could trigger RCA/Linear auto-ticketing asynchronously here.', rca_trigger)

with open('backend/app/routers/runner.py', 'w') as f: f.write(content)
print('Injected RCA categorization!')
