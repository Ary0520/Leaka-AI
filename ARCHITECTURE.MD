# TECHNICAL ARCHITECTURE: RevGuard QA

## 1. System Overview
RevGuard QA uses a decoupled, asynchronous architecture. 
*   The **Frontend (Next.js)** acts purely as a control panel and dashboard. 
*   The **Backend (FastAPI)** acts as the orchestration layer.
*   The **Agent Engine (browser-use)** is installed as a Python package dependency to execute the core logic locally.
*   A **Message Queue (Redis/Celery)** bridges the frontend and backend, ensuring long-running browser tasks do not cause HTTP timeouts.

## 2. Directory Structure (Monorepo)
```text
revguard-qa/
├── frontend/             # Next.js 14 (App Router), Tailwind, React Query
├── backend/              # Python 3.12, FastAPI, Celery
│   ├── main.py           # API endpoints (FastAPI)
│   ├── worker.py         # Background task logic (Celery + browser-use)
│   └── requirements.txt  # Contains: fastapi, browser-use, celery, redis, playwright
└── docker-compose.yml    # Spins up Postgres, Redis, Frontend, and Backend

3. The Execution Flow (Step-by-Step)
Trigger: User submits a natural language test prompt via the Next.js frontend (e.g., "Log in and check pricing").

API Call: Next.js sends a POST /api/tests/run request containing the prompt to the FastAPI backend.

Queueing: FastAPI does NOT run the test immediately. It generates a job_id, pushes the prompt and job_id to the Redis queue, and immediately returns the job_id to the frontend.

Execution (The Agent): The Celery worker picks up the job from Redis. It initializes the browser-use Agent (via from browser_use import Agent), spins up a headless Chromium browser using Playwright, and executes the steps using the LLM.

Polling: Meanwhile, the Next.js frontend uses React Query to poll GET /api/tests/status/{job_id} every 3 seconds to update the UI (Pending -> Running -> Completed/Failed).

Storage: Once the Celery worker finishes, it saves the results, screenshots, and logs to the PostgreSQL database and updates the job status.

4. LLM Configuration Strategy
The browser-use engine in the Celery worker must be configurable via .env variables to support two modes:

Production Mode: Uses langchain-anthropic (Claude 3.5 Sonnet) or langchain-openai (GPT-4o) via API keys for maximum reasoning capabilities.

Bootstrapper Mode: Uses langchain-community with Ollama to route requests to a locally running model (e.g., qwen2.5-coder) for zero-cost development.

5. Enterprise Integration Endpoints (To be built)
Linear/Jira API: A Python utility module that formats failed test results (screenshot + steps) into a GraphQL/REST payload to create tickets.

Webhooks: A specific FastAPI route (POST /api/webhooks/ci) that allows GitHub Actions to trigger test suites programmatically using an API token.