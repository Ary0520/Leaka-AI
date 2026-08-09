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
    """
    Dynamic settings — every attribute reads from os.environ at access time.
    This means changes via /api/settings/integrations (which updates os.environ)
    take effect immediately for the next request, with no restart needed.
    In production (docker/cloud), env vars are injected at container start.
    """

    @property
    def RUN_MODE(self) -> str:
        return os.getenv("RUN_MODE", "celery").lower()

    @property
    def PLAYWRIGHT_BROWSERS_PATH(self) -> str | None:
        return os.environ.get("PLAYWRIGHT_BROWSERS_PATH")

    @property
    def DATABASE_URL(self) -> str:
        return os.getenv("DATABASE_URL", "sqlite:///./revguard.db")

    @property
    def REDIS_URL(self) -> str:
        return os.getenv("REDIS_URL", "redis://localhost:6379/0")

    @property
    def REDIS_RESULT_BACKEND(self) -> str:
        return os.getenv("REDIS_RESULT_BACKEND", "redis://localhost:6379/1")

    @property
    def LLM_PROVIDER(self) -> str:
        return os.getenv("LLM_PROVIDER", "openai")

    @property
    def LLM_MODEL_OPENAI(self) -> str:
        return os.getenv("LLM_MODEL_OPENAI", "gpt-4.1-mini")

    @property
    def LLM_MODEL_ANTHROPIC(self) -> str:
        return os.getenv("LLM_MODEL_ANTHROPIC", "claude-sonnet-4-0")

    @property
    def LLM_MODEL_OPENROUTER(self) -> str:
        return os.getenv("LLM_MODEL_OPENROUTER", "anthropic/claude-sonnet-4.5")

    @property
    def OPENROUTER_API_KEY(self) -> str | None:
        return os.getenv("OPENROUTER_API_KEY")

    @property
    def OLLAMA_BASE_URL(self) -> str:
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    @property
    def OLLAMA_MODEL(self) -> str:
        return os.getenv("OLLAMA_MODEL", "qwen3:4b")

    @property
    def SCREENSHOT_DIR(self) -> str:
        return os.getenv("SCREENSHOT_DIR", "screenshots")

    @property
    def CORS_ORIGINS(self) -> list[str]:
        return _parse_list(os.getenv("CORS_ORIGINS"), ["http://localhost:3000"])

    @property
    def LINEAR_API_KEY(self) -> str | None:
        return os.getenv("LINEAR_API_KEY")

    @property
    def LINEAR_TEAM_ID(self) -> str | None:
        return os.getenv("LINEAR_TEAM_ID")

    @property
    def SUPABASE_JWKS_URL(self) -> str | None:
        return os.getenv("SUPABASE_JWKS_URL")

    @property
    def SUPABASE_URL(self) -> str | None:
        return os.getenv("SUPABASE_URL")

    @property
    def RESEND_API_KEY(self) -> str | None:
        return os.getenv("RESEND_API_KEY")

    @property
    def EMAIL_FROM(self) -> str:
        return os.getenv("EMAIL_FROM", "Leaka AI <qa@leaka.ai>")

    @property
    def EMAIL_ALERT_TO(self) -> list[str]:
        return _parse_list(os.getenv("EMAIL_ALERT_TO"))

    @property
    def SLACK_WEBHOOK_URL(self) -> str | None:
        return os.getenv("SLACK_WEBHOOK_URL")

    @property
    def DASHBOARD_BASE_URL(self) -> str | None:
        """Fallback dashboard base URL for single-tenant / self-hosted use."""
        return os.getenv("DASHBOARD_BASE_URL")

    @property
    def CI_WEBHOOK_TOKEN(self) -> str:
        return os.getenv("CI_WEBHOOK_TOKEN", "revguard-ci-token-change-me")


settings = Settings()

