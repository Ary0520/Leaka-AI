import os
import sys
import uuid
import json

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Application, Environment, TestRun, TestRunStatus, TestCase
from app.worker import run_browser_test

# 1. Setup the DB data
db = SessionLocal()

# Ensure we have a dummy application
app = db.query(Application).filter(Application.name == "Mock Customer App").first()
if not app:
    app = Application(name="Mock Customer App", base_url="http://127.0.0.1:8001", owner_id="test-owner-123")
    db.add(app)
    db.commit()

# Create the test environment using the NEW API INJECTION fields
env = db.query(Environment).filter(Environment.name == "Mock Staging with API Auth").first()
if not env:
    env = Environment(
        application_id=app.id,
        name="Mock Staging with API Auth",
        base_url="http://127.0.0.1:8001",
        auth_strategy="api_injection",
        auth_api_url="http://127.0.0.1:8001/api/login",
        auth_payload=json.dumps({"username": "admin", "password": "password"}),
        auth_token_path="data.access_token",
        auth_state_template=json.dumps({
            "origins": [{
                "origin": "http://127.0.0.1:8001",
                "localStorage": [{"name": "token", "value": "{{token}}"}]
            }]
        })
    )
    db.add(env)
    db.commit()

# Create a dummy TestRun
job_id = str(uuid.uuid4())
run = TestRun(
    job_id=job_id,
    test_case_id=None, # Mock
    owner_id="test-owner-123",
    name="Verify Invoice Total",
    prompt="Navigate to /dashboard. Verify what the Invoice Total amount is.",
    status=TestRunStatus.PENDING
)
db.add(run)
db.commit()
env_id = env.id
db.close()

print(f"--- Triggering Test Run {job_id} ---")
print("This will execute the orchestrator auth strategy, fetch the token, inject it, and verify the invoice amount on the dashboard.")

try:
    result = run_browser_test(
        job_id=job_id,
        name="Verify Invoice Total",
        prompt="Navigate to /dashboard. Verify what the Invoice Total amount is. It should be visible on the screen.",
        target_url="/dashboard",
        environment_id=env_id,
        use_vision=True,
    )
    print("Test finished successfully!")
    print(result)
except Exception as e:
    print(f"Test failed with error: {e}")
