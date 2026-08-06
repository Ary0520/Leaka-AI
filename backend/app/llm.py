import os
from typing import Any

from .config import settings


def get_llm() -> Any:
    """
    Build the browser-use LLM client based on settings.LLM_PROVIDER.

    Supports:
      - openai      : ChatOpenAI (official OpenAI API)
      - anthropic   : ChatAnthropic (official Anthropic API)
      - openrouter  : ChatOpenAI with base_url=OpenRouter, model in provider/model format
      - ollama      : langchain_ollama.ChatOllama (100% free, local LLM)
    """
    provider = (settings.LLM_PROVIDER or "openai").lower().strip()

    if provider == "openai":
        from browser_use import ChatOpenAI

        return ChatOpenAI(model=settings.LLM_MODEL_OPENAI, temperature=0.0)

    if provider == "anthropic":
        from browser_use import ChatAnthropic

        return ChatAnthropic(model=settings.LLM_MODEL_ANTHROPIC, temperature=0.0)

    if provider == "openrouter":
        api_key = settings.OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is not set."
            )
        from browser_use import ChatOpenAI

        return ChatOpenAI(
            model=settings.LLM_MODEL_OPENROUTER,
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            temperature=0.0,
        )

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as e:
            raise RuntimeError(
                "LLM_PROVIDER=ollama requires 'langchain-ollama' installed. "
                "Run: pip install langchain-ollama"
            ) from e

        return ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        "Choose one of: openai, anthropic, openrouter, ollama."
    )
