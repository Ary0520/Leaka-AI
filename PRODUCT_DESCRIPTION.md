# PRODUCT SPECIFICATION: Leaka AI
**Tagline:** Autonomous QA Agent for E-Commerce and SaaS Revenue Flows.
**Document Purpose:** Provide the AI IDE with full market context, architectural constraints, and feature requirements to ensure product-driven coding decisions.

## 1. Market Positioning & Value Proposition
Leaka AI is a Vertical AI Operator designed for non-technical Product Managers and RevOps teams. It replaces brittle, code-heavy End-to-End (E2E) testing (like Cypress or Playwright) with natural language, self-healing browser agents. 

The core utility is protecting revenue-critical workflows (e.g., checkout flows, user onboarding, pricing page interactions). It does not just report failures; it provides actionable, visual bug reports. We are selling "completed QA work" and "uptime peace of mind," not a developer tool.

## 2. Core Architectural Mandate (CRITICAL)
This product is completely independent of the paid Browser Use Cloud API. 
*   **Frontend (UI Shell):** We are adopting the UI, UX from the https://github.com/browser-use/qa-use repository, but **ALL** integrations to their cloud platform must be stripped out.
*   **Backend (Execution Engine):** A custom Python FastAPI server. The backend receives HTTP requests from our frontend and executes them locally using the **free, open-source** `browser-use` Python package: https://github.com/browser-use/browser-use

*   **LLM Strategy:** The backend AI engine must support two modes:
    1.  **Production Mode:** Connects to Anthropic (Claude 3.5 Sonnet) and OpenAI AND openrouter, via API keys for high-accuracy, low-cost (pennies per run) execution.
    2.  **Bootstrapper Mode:** Supports Ollama for 100% free, local LLM execution during local development and testing.

## 3. Core Features & Capabilities
*   **Natural Language Test Builder:** Users write test parameters in plain English (EXAMPLE: "Add a $50 item to cart, apply promo code WELCOME, and verify the total is $45"). No code required.
*   **Self-Healing Execution:** Because the agent visually parses the DOM in real-time, if a UI element changes (e.g., a button moves, or a class name changes from `btn-blue` to `btn-red`), the agent adapts autonomously without test failure.
*   **Headless Background Execution:** Tests run headlessly in local Chromium instances. Because these tasks take 30-120 seconds, they must be processed asynchronously via a Redis/Celery queue so the UI does not block or timeout.
*   **Visual Proof & Telemetry:** Upon a test failure, the agent must save:
    1.  The final DOM state.
    2.  A screenshot of the exact failure point.
    3.  A summary of the steps taken before failure.

## 4. Enterprise Integrations (The Startup Moat)
To elevate this from a "project" to a "fundable startup," the platform must integrate into existing corporate workflows:
*   **Auto-Ticketing (Linear/Jira):** When a test fails, the Python backend automatically drafts a bug report containing reproduction steps, expected vs. actual outcomes, and the failure screenshot, pushing it directly to the engineering backlog via API.
*   **CI/CD Pipeline Hooks:** Provide a secure webhook endpoint so clients can trigger RevGuard QA natively from their GitHub Actions, blocking bad code from merging to production.
*   **Asynchronous Alerting (Slack/Resend):** Instant alerts routing specific test failures to specific Slack channels or email addresses using the Resend API.

## 5. IDE Instruction & Workflow Rules
*   When generating backend code, rely strictly on the `browser-use` Python package and the github repo attached. It's a MUST. NEVER assume code or any other information based on your model training data; you MUST always verify any information using WEBSEARCH OR ASKING ME(dont hesitate), before implementing any code.
*   Always implement error handling for headless browser timeouts and LLM rate limits.

You DO NOT clone the browser-use GitHub repository.

You simply open your terminal and run: pip install browser-use.

This downloads the pre-packaged, fully functioning agentic engine into your Python virtual environment.

How does the AI IDE know how to use it? It doesn't need to read the source code; you just give the AI IDE the Documentation URL (via the @Docs feature in Cursor or Windsurf). The IDE reads the docs, sees how to write the commands, and writes a file in your project that says: from browser_use import Agent.

you MUST use these docs:(use websearch or ask me for docs/codes etc)
https://docs.browser-use.com/open-source/introduction
https://github.com/browser-use/browser-use
https://playwright.dev/python/docs/intro ( (For headless browser configuration and screenshot extraction)
For the Async Queue (Backend):

Use when: Setting up the Redis/Celery queue so tasks run in the background.

URL: [https://docs.celeryq.dev/en/stable/getting-started/introduction.html](https://docs.celeryq.dev/en/stable/getting-started/introduction.html)

URL: [https://fastapi.tiangolo.com/tutorial/background-tasks/](https://fastapi.tiangolo.com/tutorial/background-tasks/)

For the Frontend Dashboard (Frontend):

Use when: Building the dashboard, test builder UI, and API routes.

URL: [https://nextjs.org/docs](https://nextjs.org/docs) (Specify App Router architecture).

URL: [https://ui.shadcn.com/docs](https://ui.shadcn.com/docs) (For rapid, enterprise-looking UI components).

For Enterprise Integrations:

Use when: Writing the Python functions that create tickets upon a failed test.

URL: [https://developers.linear.app/docs/graphql/working-with-the-graphql-api](https://developers.linear.app/docs/graphql/working-with-the-graphql-api) (Linear Integration).

URL: [https://resend.com/docs/send-with-python](https://resend.com/docs/send-with-python) (Email Notifications).