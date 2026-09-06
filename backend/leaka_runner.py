import argparse
import asyncio
import os
import requests
import json
import logging
import tempfile
from typing import Any

from pydantic import SecretStr
from browser_use import Agent
from browser_use.browser.session import BrowserSession

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("leaka-runner")

API_BASE = os.getenv("LEAKA_API_URL", "http://127.0.0.1:8000")

def pull_job(job_id: str, token: str) -> dict:
    url = f"{API_BASE}/api/runner/v1/jobs/{job_id}/pull"
    logger.info(f"Pulling job {job_id} from {url}")
    resp = requests.post(url, headers={"X-Runner-Token": token, "Bypass-Tunnel-Reminder": "true"}, timeout=30)
    resp.raise_for_status()
    return resp.json()

def update_status(job_id: str, token: str, payload: dict):
    url = f"{API_BASE}/api/runner/v1/jobs/{job_id}/status"
    resp = requests.post(url, headers={"X-Runner-Token": token, "Bypass-Tunnel-Reminder": "true"}, json=payload, timeout=30)
    resp.raise_for_status()

async def run_job(job_id: str, token: str):
    try:
        job = pull_job(job_id, token)
        update_status(job_id, token, {"status": "RUNNING"})
    except Exception as e:
        logger.error(f"Failed to initialize job: {e}")
        return

    logger.info(f"Executing: {job['name']}")
    
    # Configure LLM (Honors standard env vars)
    llm_provider = os.getenv("LLM_PROVIDER", "openai").lower()
    
    if llm_provider == "anthropic":
        from browser_use.llm import ChatAnthropic
        llm = ChatAnthropic(
            model_name="claude-3-5-sonnet-20241022",
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        )
    elif llm_provider == "openrouter":
        from browser_use.llm import ChatOpenRouter
        llm = ChatOpenRouter(
            model=os.getenv("LLM_MODEL", "openai/gpt-4o"), # BYOK: Allow passing model in env
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
        )
    else:
        from browser_use.llm import ChatOpenAI
        llm = ChatOpenAI(
            model="gpt-4o",
            api_key=os.getenv("OPENAI_API_KEY", ""),
        )

    # Auth Strategy handling
    auth_state_path = None
    env_cfg = job.get("environment")
    if env_cfg and env_cfg.get("auth_strategy") == "api_injection":
        logger.info("Executing API Injection Auth Strategy...")
        try:
            payload = json.loads(env_cfg["auth_payload"]) if env_cfg.get("auth_payload") else {}
            auth_resp = requests.post(env_cfg["auth_api_url"], json=payload, timeout=15)
            auth_resp.raise_for_status()
            token_val = auth_resp.json().get(env_cfg.get("auth_token_path") or "token")
            
            template = env_cfg.get("auth_state_template", "")
            state_json = template.replace("{{token}}", str(token_val))
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as f:
                f.write(state_json)
                auth_state_path = f.name
            logger.info("Successfully provisioned headless session.")
        except Exception as e:
            logger.error(f"Auth injection failed: {e}")
            update_status(job_id, token, {
                "status": "FAILED",
                "is_successful": False,
                "error_message": f"Auth Strategy failed: {e}"
            })
            return

    storage_state_dict = None
    if auth_state_path and os.path.exists(auth_state_path):
        with open(auth_state_path, "r") as f:
            storage_state_dict = json.load(f)

    # Initialize Browser Session for CI/CD (must be headless with no-sandbox)
    browser_session = BrowserSession(
        headless=True, 
        storage_state=storage_state_dict,
        chromium_sandbox=False,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--disable-setuid-sandbox"]
    )

    try:
        agent = Agent(
            task=job["prompt"],
            llm=llm,
            browser_session=browser_session,
            use_vision=True,
            max_actions_per_step=4,
            use_thinking=False,
        )

        history = await agent.run(max_steps=50)
        
        is_success = history.is_successful()
        result_text = history.final_result() or "Agent completed without final result text."
        
        # Format steps
        live_steps = []
        for i, res in enumerate(history.history):
            action_names = []
            if res.model_output and hasattr(res.model_output, "action"):
                for a in res.model_output.action:
                    for k, v in a.model_dump(exclude_unset=True).items():
                        if v is not None: action_names.append(k)
            live_steps.append({
                "step": i + 1,
                "actions": action_names,
                "eval": res.model_output.current_state.evaluation_previous_goal if res.model_output else "",
                "memory": res.model_output.current_state.memory if res.model_output else "",
                "next_goal": res.model_output.current_state.next_goal if res.model_output else ""
            })

        update_status(job_id, token, {
            "status": "COMPLETED" if is_success else "FAILED",
            "is_successful": is_success,
            "result_summary": result_text,
            "final_result": result_text,
            "live_steps": live_steps
        })
        logger.info(f"Job finished. Success: {is_success}")
        
    except Exception as e:
        logger.exception("Agent crashed")
        update_status(job_id, token, {
            "status": "FAILED",
            "is_successful": False,
            "error_message": str(e)
        })
    finally:
        await browser_session.close()
        if auth_state_path and os.path.exists(auth_state_path):
            os.remove(auth_state_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Leaka AI Self-Hosted Runner")
    parser.add_argument("--job-id", required=True, help="Job ID to execute")
    parser.add_argument("--token", required=True, help="Runner Auth Token")
    args = parser.parse_args()
    
    asyncio.run(run_job(args.job_id, args.token))