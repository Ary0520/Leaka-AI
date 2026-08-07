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
