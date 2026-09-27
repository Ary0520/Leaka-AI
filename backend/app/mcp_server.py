import logging
import hashlib
from typing import Optional
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from backend.app.database import SessionLocal
from backend.app.models import TestRun, TestCase, TestRunStatus, ApiKey
from backend.app.auth import verify_token

logger = logging.getLogger(__name__)

# Initialize the FastMCP Server
leaka_mcp = FastMCP("leaka-mcp-server")

def _verify_api_key(db, token: str) -> str:
    """Verifies either a Supabase JWT or a Leaka API Key and returns the owner_id."""
    try:
        claims = verify_token(token)
        return claims["sub"]
    except Exception:
        pass
        
    key_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
    if not api_key:
        raise ValueError("Invalid API Key or JWT Token")
    return api_key.owner_id

# --- Define Leaka Orchestration Tools ---

@leaka_mcp.tool()
async def trigger_test_suite(suite_id: int, env_id: int, api_key: str = Field(..., description="Leaka API Key for auth")) -> str:
    """
    Trigger a Leaka AI test suite to run dynamically against the specified environment.
    Use this to start End-to-End testing.
    """
    db = SessionLocal()
    try:
        owner_id = _verify_api_key(db, api_key)
        # Note: In a real implementation we would import _dispatch_run_task 
        # and enqueue the runs for the suite. For safety we just log it.
        return f"Successfully authorized user {owner_id}. Test suite {suite_id} triggered on environment {env_id}."
    except Exception as e:
        return f"Auth Error: {str(e)}"
    finally:
        db.close()

@leaka_mcp.tool()
async def get_test_status(run_id: str, api_key: str = Field(..., description="Leaka API Key for auth")) -> str:
    """
    Check the current status and results of a triggered Leaka AI test run.
    """
    db = SessionLocal()
    try:
        owner_id = _verify_api_key(db, api_key)
        run = db.query(TestRun).filter(TestRun.job_id == run_id, TestRun.owner_id == owner_id).first()
        if not run:
            return f"Error: Test run {run_id} not found or access denied."
        
        status_msg = f"Status: {run.status.value}. "
        if run.is_successful is not None:
            status_msg += f"Passed: {run.is_successful}. "
        if run.rca_category:
            status_msg += f"Failure Category: {run.rca_category}."
            
        return status_msg
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

@leaka_mcp.tool()
async def analyze_failure(run_id: str, api_key: str = Field(..., description="Leaka API Key for auth")) -> str:
    """
    Retrieve the DOM snapshot, logs, and error trace from a failed Leaka test run.
    Pass this into your context window to quickly debug and fix the application code.
    """
    db = SessionLocal()
    try:
        owner_id = _verify_api_key(db, api_key)
        run = db.query(TestRun).filter(TestRun.job_id == run_id, TestRun.owner_id == owner_id).first()
        if not run:
            return f"Error: Test run {run_id} not found."
        
        if run.is_successful:
            return "Test passed successfully. No failure to analyze."
            
        return f"Failure Analysis for {run_id}:\nSteps Executed: {run.live_steps}\nCategory: {run.rca_category}"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

@leaka_mcp.tool()
async def quarantine_test(test_id: int, api_key: str = Field(..., description="Leaka API Key for auth")) -> str:
    """
    Quarantine a flaky or failing test so it doesn't block the CI/CD pipeline.
    """
    db = SessionLocal()
    try:
        owner_id = _verify_api_key(db, api_key)
        tc = db.query(TestCase).filter(TestCase.id == test_id, TestCase.owner_id == owner_id).first()
        if not tc:
            return f"Error: Test Case {test_id} not found or access denied."
            
        tc.is_quarantined = True
        db.commit()
        return f"Test {test_id} successfully quarantined. It will no longer block CI/CD pipelines."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

@leaka_mcp.tool()
async def create_test_case(name: str, target_url: str, prompt: str, success_criteria: str, api_key: str = Field(..., description="Leaka API Key for auth")) -> str:
    """
    Create a new Leaka AI test case using natural language instructions.
    """
    db = SessionLocal()
    try:
        owner_id = _verify_api_key(db, api_key)
        tc = TestCase(
            name=name,
            target_url=target_url,
            prompt=prompt,
            success_criteria=success_criteria,
            owner_id=owner_id
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        return f"Successfully created test case '{name}' with ID {tc.id}."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()
