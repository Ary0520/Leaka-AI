"""
Root Cause Analysis (RCA) Intelligence Engine.

This module evaluates forensic evidence captured during a test failure 
(error message, console logs, network errors, DOM state) and confidently 
categorizes the root cause to save engineers debugging time.
"""

from __future__ import annotations

import json
import logging
from typing import Optional, Any
from pydantic import BaseModel

logger = logging.getLogger("revguard.intelligence.rca")

class RCAResult(BaseModel):
    category: str
    explanation: str


def analyze_failure(
    llm: Any,
    error_message: str,
    console_logs: str,
    har_data: str,
    dom_snapshot: Optional[str] = None,
    last_action: Optional[str] = None
) -> RCAResult:
    """
    Given forensic evidence, run it through the LLM with structured output
    to categorize the root cause.
    """
    if not llm:
        return RCAResult(category="UNKNOWN", explanation="No LLM available for analysis.")

    # Filter out excessive HAR data to just the errors (status >= 400 or failed requests)
    # A full HAR file can be massive, so we do a quick reduction here.
    network_errors = []
    try:
        if har_data:
            har_json = json.loads(har_data)
            entries = har_json.get("log", {}).get("entries", [])
            for e in entries:
                status = e.get("response", {}).get("status", 0)
                if status >= 400 or status == 0:
                    req_url = e.get("request", {}).get("url", "")
                    method = e.get("request", {}).get("method", "")
                    error_text = e.get("response", {}).get("content", {}).get("text", "")
                    if status == 0:
                        error_text = e.get("response", {}).get("_error", "Unknown network failure")
                    network_errors.append(f"{method} {req_url} -> {status}: {error_text[:200]}")
    except Exception as exc:
        logger.warning(f"Failed to parse HAR data for RCA: {exc}")

    network_summary = "\\n".join(network_errors) if network_errors else "No prominent network errors."
    
    # Truncate console logs and dom slightly to fit well
    console_summary = (console_logs[-2000:] if console_logs else "No console logs captured.")
    
    prompt = f"""
You are an expert QA Root Cause Analysis (RCA) engine for Leaka AI.
A browser automated test has failed. I will provide you with the forensic evidence.
Your job is to categorize the failure into EXACTLY ONE of the following categories, and provide a 1-2 sentence explanation.

Categories:
1. PRODUCT_BUG: The application threw a visible error, a network API returned a 500/400 error, or a Javascript exception occurred that blocked execution.
2. ENVIRONMENT_TIMEOUT: The environment was too slow, a page took too long to load, or a 503/504 gateway timeout occurred.
3. FLAKY_SELECTOR: The test failed because an expected DOM element was not found (and self-healing failed), but there are no underlying network/JS errors indicating a product crash.
4. UNKNOWN: If none of the above cleanly apply.

--- EVIDENCE ---
Error Message from Agent: {error_message}
Last Action Attempted: {last_action or "None recorded"}

Network Errors (HAR subset):
{network_summary}

Console Logs (last 2000 chars):
{console_summary}
----------------

Evaluate the evidence carefully. If there is a 500 network error, it's a PRODUCT_BUG. If a button is just missing with no errors, it's a FLAKY_SELECTOR.

Return the result.
"""
    try:
        # LangChain structured output invocation
        # browser_use's llm is usually a Langchain ChatModel
        structured_llm = llm.with_structured_output(RCAResult)
        result: RCAResult = structured_llm.invoke(prompt)
        return result
    except Exception as exc:
        logger.error(f"RCA analysis failed: {exc}")
        return RCAResult(category="UNKNOWN", explanation=f"RCA LLM analysis failed: {exc}")
