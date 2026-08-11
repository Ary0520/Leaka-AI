import asyncio
import os
from typing import Any

from .config import settings


def get_llm() -> Any:
    """
    Build the browser-use LLM client based on settings.LLM_PROVIDER.

    Correct imports verified against browser-use==0.13.7 installed package.
    All Chat* classes live under browser_use.llm, not the top-level package.

    Supports:
      - openai      : ChatOpenAI (official OpenAI API)
      - anthropic   : ChatAnthropic (official Anthropic API)
      - openrouter  : ChatOpenRouter (OpenRouter multi-provider gateway)
      - ollama      : ChatOllama (100% free, local LLM via Ollama server)
    """
    provider = (settings.LLM_PROVIDER or "openai").lower().strip()

    if provider == "openai":
        from browser_use.llm import ChatOpenAI  # type: ignore[import]

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set in .env"
            )
        return ChatOpenAI(model=settings.LLM_MODEL_OPENAI, temperature=0.0)

    if provider == "anthropic":
        from browser_use.llm import ChatAnthropic  # type: ignore[import]

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set in .env"
            )
        return ChatAnthropic(model=settings.LLM_MODEL_ANTHROPIC, temperature=0.0)

    if provider == "openrouter":
        from browser_use.llm import ChatOpenRouter  # type: ignore[import]

        api_key = settings.OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is not set."
            )
        return ChatOpenRouter(
            model=settings.LLM_MODEL_OPENROUTER,
            api_key=api_key,
            temperature=0.0,
        )

    if provider == "ollama":
        from browser_use.llm import ChatOllama  # type: ignore[import]

        # ChatOllama in browser-use 0.13.7 uses `host` (not `base_url`)
        # Verified from: browser_use.llm.ollama.chat.__init__ signature
        return ChatOllama(
            model=settings.OLLAMA_MODEL,
            host=settings.OLLAMA_BASE_URL,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        "Choose one of: openai, anthropic, openrouter, ollama."
    )


async def _test_llm_connection() -> dict[str, Any]:
    """
    Validate the current LLM configuration by making a lightweight live API call.

    Strategy per provider (chosen to consume zero tokens where possible):
      - openai / openrouter : client.models.list() — pure auth check, no tokens
      - anthropic           : client.messages.count_tokens() — no tokens consumed
      - ollama              : HTTP GET {host}/api/tags — checks server is reachable

    Returns {"ok": bool, "provider": str, "model": str, "detail": str}
    """
    provider = (settings.LLM_PROVIDER or "openai").lower().strip()

    # ── OpenAI ────────────────────────────────────────────────────────────────
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"ok": False, "provider": provider, "model": settings.LLM_MODEL_OPENAI,
                    "detail": "OPENAI_API_KEY is not set. Add it in Settings."}
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            await client.models.list()
            return {"ok": True, "provider": provider, "model": settings.LLM_MODEL_OPENAI,
                    "detail": "API key is valid and active."}
        except Exception as exc:
            return {"ok": False, "provider": provider, "model": settings.LLM_MODEL_OPENAI,
                    "detail": _classify_api_error(str(exc))}

    # ── OpenRouter ────────────────────────────────────────────────────────────
    if provider == "openrouter":
        api_key = settings.OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return {"ok": False, "provider": provider, "model": settings.LLM_MODEL_OPENROUTER,
                    "detail": "OPENROUTER_API_KEY is not set. Add it in Settings."}
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
            )
            await client.models.list()
            return {"ok": True, "provider": provider, "model": settings.LLM_MODEL_OPENROUTER,
                    "detail": "API key is valid and active."}
        except Exception as exc:
            return {"ok": False, "provider": provider, "model": settings.LLM_MODEL_OPENROUTER,
                    "detail": _classify_api_error(str(exc))}

    # ── Anthropic ─────────────────────────────────────────────────────────────
    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return {"ok": False, "provider": provider, "model": settings.LLM_MODEL_ANTHROPIC,
                    "detail": "ANTHROPIC_API_KEY is not set. Add it in Settings."}
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            # count_tokens is a free endpoint — no tokens consumed
            await client.messages.count_tokens(
                model=settings.LLM_MODEL_ANTHROPIC,
                messages=[{"role": "user", "content": "ping"}],
            )
            return {"ok": True, "provider": provider, "model": settings.LLM_MODEL_ANTHROPIC,
                    "detail": "API key is valid and active."}
        except Exception as exc:
            return {"ok": False, "provider": provider, "model": settings.LLM_MODEL_ANTHROPIC,
                    "detail": _classify_api_error(str(exc))}

    # ── Ollama ────────────────────────────────────────────────────────────────
    if provider == "ollama":
        import httpx
        host = settings.OLLAMA_BASE_URL.rstrip("/")
        model = settings.OLLAMA_MODEL
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"{host}/api/tags")
                if resp.status_code != 200:
                    return {"ok": False, "provider": provider, "model": model,
                            "detail": f"Ollama server returned HTTP {resp.status_code}. Is it running?"}
                # Check if the configured model is available
                tags = resp.json()
                available = [m.get("name", "") for m in tags.get("models", [])]
                if not any(model in m for m in available):
                    return {
                        "ok": False, "provider": provider, "model": model,
                        "detail": (
                            f"Ollama is running but model '{model}' is not pulled. "
                            f"Run: ollama pull {model}"
                        ),
                    }
                return {"ok": True, "provider": provider, "model": model,
                        "detail": f"Ollama is running and model '{model}' is available."}
        except httpx.ConnectError:
            return {"ok": False, "provider": provider, "model": model,
                    "detail": f"Cannot connect to Ollama at {host}. Make sure Ollama is running."}
        except Exception as exc:
            return {"ok": False, "provider": provider, "model": model,
                    "detail": f"Ollama check failed: {exc}"}

    return {"ok": False, "provider": provider, "model": "unknown",
            "detail": f"Unknown LLM provider '{provider}'."}


def _classify_api_error(raw: str) -> str:
    """Turn a raw API exception string into a clean, actionable user message."""
    low = raw.lower()
    if "403" in low or "key limit exceeded" in low or "limit exceeded" in low:
        return "Credit limit exceeded (HTTP 403). Top up your account or switch providers."
    if "401" in low or "unauthorized" in low or "invalid api key" in low or "incorrect api key" in low:
        return "Invalid API key (HTTP 401). Check your key is correct and hasn't been revoked."
    if "429" in low or "rate limit" in low or "too many requests" in low:
        return "Rate limit hit (HTTP 429). Wait a moment or upgrade your plan."
    if "404" in low and "model" in low:
        return "Model not found (HTTP 404). Check the model name is correct for this provider."
    if "connection" in low or "connect" in low or "timeout" in low:
        return "Connection failed. Check your internet connection and try again."
    # Return the first 200 chars of the raw error as a fallback
    return raw[:200]
