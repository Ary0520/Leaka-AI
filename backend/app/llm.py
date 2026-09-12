import asyncio
import os
from typing import Any

from .config import settings


def _extract_clean_json(text: str) -> str:
    if not isinstance(text, str):
        return text
    start_idx = -1
    for i, char in enumerate(text):
        if char in ('{', '['):
            start_idx = i
            break
    if start_idx == -1:
        return text
        
    start_char = text[start_idx]
    end_char = '}' if start_char == '{' else ']'
    stack = 0
    in_string = False
    escape = False
    
    for i in range(start_idx, len(text)):
        char = text[i]
        if in_string:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == start_char:
                stack += 1
            elif char == end_char:
                stack -= 1
                if stack == 0:
                    return text[start_idx:i+1]
    return text

def _clean_message_payloads(msg: Any) -> None:
    if hasattr(msg, "content") and isinstance(msg.content, str):
        msg.content = _extract_clean_json(msg.content)
    if hasattr(msg, "tool_calls") and isinstance(msg.tool_calls, list):
        for tc in msg.tool_calls:
            if "args" in tc and isinstance(tc["args"], str):
                tc["args"] = _extract_clean_json(tc["args"])
            elif "function" in tc and "arguments" in tc["function"] and isinstance(tc["function"]["arguments"], str):
                tc["function"]["arguments"] = _extract_clean_json(tc["function"]["arguments"])
    if hasattr(msg, "additional_kwargs") and "tool_calls" in msg.additional_kwargs:
        for tc in msg.additional_kwargs["tool_calls"]:
            if "function" in tc and "arguments" in tc["function"] and isinstance(tc["function"]["arguments"], str):
                tc["function"]["arguments"] = _extract_clean_json(tc["function"]["arguments"])

def get_llm(owner_id: str | None = None) -> Any:
    """
    Build the browser-use LLM client.
    First tries the user's BYOK settings (if owner_id is provided),
    then falls back to the global settings in .env.
    """
    provider = None
    model = None
    api_key = None

    if owner_id:
        from .database import SessionLocal
        from .models import UserSettings
        db = SessionLocal()
        try:
            cfg = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).first()
            if cfg and cfg.llm_provider and (cfg.llm_api_key or cfg.llm_provider == "ollama"):
                provider = cfg.llm_provider.lower().strip()
                api_key = cfg.llm_api_key
                model = cfg.llm_model
        finally:
            db.close()

    if not provider:
        provider = (settings.LLM_PROVIDER or "openai").lower().strip()

    if provider == "openai":
        from browser_use.llm import ChatOpenAI  # type: ignore[import]
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set for user or in .env")
        mod = model or settings.LLM_MODEL_OPENAI

        class SafeChatOpenAI(ChatOpenAI):
            async def ainvoke(self, messages: Any, output_format: Any | None = None, **kwargs: Any) -> Any:
                if output_format is not None:
                    orig = output_format.model_validate_json
                    def safe_validate(json_data, *a, **kw):
                        return orig(_extract_clean_json(json_data), *a, **kw)
                    output_format.model_validate_json = safe_validate
                    try:
                        return await super().ainvoke(messages, output_format=output_format, **kwargs)
                    finally:
                        output_format.model_validate_json = orig
                else:
                    res = await super().ainvoke(messages, output_format=output_format, **kwargs)
                    if hasattr(res, "completion") and isinstance(res.completion, str):
                        res.completion = _extract_clean_json(res.completion)
                    return res

        return SafeChatOpenAI(model=mod, api_key=key, temperature=0.0)

    if provider == "anthropic":
        from browser_use.llm import ChatAnthropic  # type: ignore[import]
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set for user or in .env")
        mod = model or settings.LLM_MODEL_ANTHROPIC
        return ChatAnthropic(model=mod, api_key=key, temperature=0.0)

    if provider == "openrouter":
        from browser_use.llm import ChatOpenRouter  # type: ignore[import]
        key = api_key or settings.OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set for user or in .env")
        mod = model or settings.LLM_MODEL_OPENROUTER

        class SafeChatOpenRouter(ChatOpenRouter):
            """Wraps OpenRouter to automatically strip trailing conversational garbage
            that models like gpt-5.6-luna append after the JSON block."""
            async def ainvoke(self, messages: Any, output_format: Any | None = None, **kwargs: Any) -> Any:
                if output_format is not None:
                    orig = output_format.model_validate_json
                    def safe_validate(json_data, *a, **kw):
                        return orig(_extract_clean_json(json_data), *a, **kw)
                    output_format.model_validate_json = safe_validate
                    try:
                        return await super().ainvoke(messages, output_format=output_format, **kwargs)
                    finally:
                        output_format.model_validate_json = orig
                else:
                    res = await super().ainvoke(messages, output_format=output_format, **kwargs)
                    if hasattr(res, "completion") and isinstance(res.completion, str):
                        res.completion = _extract_clean_json(res.completion)
                    return res
                
        return SafeChatOpenRouter(model=mod, api_key=key, temperature=0.0)

    if provider == "ollama":
        from browser_use.llm import ChatOllama  # type: ignore[import]
        mod = model or settings.OLLAMA_MODEL
        return ChatOllama(model=mod, host=settings.OLLAMA_BASE_URL)

    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'.")


async def _test_llm_connection(owner_id: str | None = None) -> dict[str, Any]:
    """
    Validate the current LLM configuration by making a lightweight live API call.

    Strategy per provider (chosen to consume zero tokens where possible):
      - openai / openrouter : client.models.list() — pure auth check, no tokens
      - anthropic           : client.messages.count_tokens() — no tokens consumed
      - ollama              : HTTP GET {host}/api/tags — checks server is reachable

    Returns {"ok": bool, "provider": str, "model": str, "detail": str}
    """
    provider = None
    model = None
    api_key = None

    if owner_id:
        from .database import SessionLocal
        from .models import UserSettings
        db = SessionLocal()
        try:
            cfg = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).first()
            if cfg and cfg.llm_provider and (cfg.llm_api_key or cfg.llm_provider == "ollama"):
                provider = cfg.llm_provider.lower().strip()
                api_key = cfg.llm_api_key
                model = cfg.llm_model
        finally:
            db.close()

    if not provider:
        provider = (settings.LLM_PROVIDER or "openai").lower().strip()

    # ── OpenAI ────────────────────────────────────────────────────────────────
    if provider == "openai":
        key = api_key or os.getenv("OPENAI_API_KEY")
        mod = model or settings.LLM_MODEL_OPENAI
        if not key:
            return {"ok": False, "provider": provider, "model": mod,
                    "detail": "OPENAI_API_KEY is not set. Add it in Settings."}
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=key)
            await client.models.list()
            return {"ok": True, "provider": provider, "model": mod,
                    "detail": "API key is valid and active."}
        except Exception as exc:
            return {"ok": False, "provider": provider, "model": mod,
                    "detail": _classify_api_error(str(exc))}

    # ── OpenRouter ────────────────────────────────────────────────────────────
    if provider == "openrouter":
        key = api_key or settings.OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY")
        mod = model or settings.LLM_MODEL_OPENROUTER
        if not key:
            return {"ok": False, "provider": provider, "model": mod,
                    "detail": "OPENROUTER_API_KEY is not set. Add it in Settings."}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {key}"},
                )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                label = data.get("label") or "connected"
                limit = data.get("limit")
                usage = data.get("usage", 0)
                remaining = f" · ${round(limit - usage, 4)} remaining" if limit else ""
                return {"ok": True, "provider": provider, "model": mod,
                        "detail": f"API key is valid ({label}){remaining}."}
            elif resp.status_code in (401, 403):
                return {"ok": False, "provider": provider, "model": mod,
                        "detail": _classify_api_error(resp.text[:200])}
            else:
                return {"ok": False, "provider": provider, "model": mod,
                        "detail": f"OpenRouter returned HTTP {resp.status_code}."}
        except Exception as exc:
            return {"ok": False, "provider": provider, "model": mod,
                    "detail": _classify_api_error(str(exc))}

    # ── Anthropic ─────────────────────────────────────────────────────────────
    if provider == "anthropic":
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        mod = model or settings.LLM_MODEL_ANTHROPIC
        if not key:
            return {"ok": False, "provider": provider, "model": mod,
                    "detail": "ANTHROPIC_API_KEY is not set. Add it in Settings."}
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=key)
            await client.messages.count_tokens(
                model=mod,
                messages=[{"role": "user", "content": "ping"}],
            )
            return {"ok": True, "provider": provider, "model": mod,
                    "detail": "API key is valid and active."}
        except Exception as exc:
            return {"ok": False, "provider": provider, "model": mod,
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
