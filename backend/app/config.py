import os
from dotenv import load_dotenv

load_dotenv()

_PB_PATH = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
if _PB_PATH:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.abspath(_PB_PATH)


def _parse_list(value: str | None, default: list[str] | None = None) -> list[str]:
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    RUN_MODE: str = os.getenv("RUN_MODE", "celery").lower()
    PLAYWRIGHT_BROWSERS_PATH: str | None = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./revguard.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_RESULT_BACKEND: str = os.getenv(
        "REDIS_RESULT_BACKEND", "redis://localhost:6379/1"
    )

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    LLM_MODEL_OPENAI: str = os.getenv("LLM_MODEL_OPENAI", "gpt-4.1-mini")
    LLM_MODEL_ANTHROPIC: str = os.getenv("LLM_MODEL_ANTHROPIC", "claude-sonnet-4-0")
    LLM_MODEL_OPENROUTER: str = os.getenv(
        "LLM_MODEL_OPENROUTER", "anthropic/claude-sonnet-4.5"
    )
    OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")

    SCREENSHOT_DIR: str = os.getenv("SCREENSHOT_DIR", "screenshots")
    CORS_ORIGINS: list[str] = _parse_list(
        os.getenv("CORS_ORIGINS"), ["http://localhost:3000"]
    )

    LINEAR_API_KEY: str | None = os.getenv("LINEAR_API_KEY")
    LINEAR_TEAM_ID: str | None = os.getenv("LINEAR_TEAM_ID")

    RESEND_API_KEY: str | None = os.getenv("RESEND_API_KEY")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "Leaka AI <qa@leaka.ai>")
    EMAIL_ALERT_TO: list[str] = _parse_list(os.getenv("EMAIL_ALERT_TO"))

    SLACK_WEBHOOK_URL: str | None = os.getenv("SLACK_WEBHOOK_URL")
    CI_WEBHOOK_TOKEN: str = os.getenv("CI_WEBHOOK_TOKEN", "revguard-ci-token-change-me")


settings = Settings()
