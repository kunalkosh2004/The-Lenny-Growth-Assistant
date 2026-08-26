"""Provider factory: builds the active LLM provider from application settings.

The factory is the single entry point for obtaining an ``LLMProvider``
instance.  It reads ``LLM_PROVIDER`` from the environment (via
``Settings``) and constructs the matching implementation.

Runtime provider switching:

- The factory caches the active provider per ``Settings`` object so
  repeated calls are cheap.
- ``select_provider()`` clears the cache and constructs a new provider
  without restarting the process, enabling runtime switching.
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.providers.base import LLMProvider, ProviderError

logger = logging.getLogger(__name__)

_active_provider: LLMProvider | None = None


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Return the active LLM provider, building it if necessary.

    If ``settings`` is ``None``, a fresh ``Settings()`` is created so
    the factory works outside request contexts (e.g. scripts, tests).
    """
    global _active_provider  # noqa: PLW0603

    if _active_provider is not None:
        return _active_provider

    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()

    _active_provider = _build_provider(settings)
    return _active_provider


def select_provider(settings: Settings) -> LLMProvider:
    """Force-rebuild the provider with the given settings.

    Used by the ``/api/providers/select`` endpoint to switch providers
    at runtime.
    """
    global _active_provider  # noqa: PLW0603

    old = _active_provider
    _active_provider = None
    try:
        provider = _build_provider(settings)
        _active_provider = provider
        return provider
    except Exception:
        _active_provider = old
        raise


def reset_provider() -> None:
    """Clear the cached provider.  Used by tests."""
    global _active_provider  # noqa: PLW0603
    _active_provider = None


def _build_provider(settings: Settings) -> LLMProvider:
    name = settings.llm_provider.lower().strip()

    if name == "ollama":
        from app.providers.ollama import OllamaProvider

        logger.info(
            "Building Ollama provider (model=%s, url=%s)",
            settings.ollama_model,
            settings.ollama_base_url,
        )
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=getattr(settings, "ollama_timeout_seconds", 60.0),
        )

    if name == "openai":
        from app.providers.openai import OpenAIProvider

        logger.info("Building OpenAI provider (model=%s)", settings.openai_model)
        return OpenAIProvider(
            api_key=settings.openai_api_key or "",
            model=settings.openai_model,
        )

    if name == "anthropic":
        from app.providers.anthropic import AnthropicProvider

        logger.info("Building Anthropic provider (model=%s)", settings.anthropic_model)
        return AnthropicProvider(
            api_key=settings.anthropic_api_key or "",
            model=settings.anthropic_model,
        )

    if name == "google":
        from app.providers.google import GoogleProvider

        logger.info("Building Google provider (model=%s)", settings.google_model)
        return GoogleProvider(
            api_key=settings.google_api_key or "",
            model=settings.google_model,
        )

    raise ProviderError(
        f"Unknown LLM_PROVIDER '{settings.llm_provider}'. "
        "Supported values: ollama, openai, anthropic, google."
    )


def list_available_providers(settings: Settings) -> list[dict]:
    """Build and probe every supported provider, returning status info.

    This is used by the ``/api/providers`` endpoint so the frontend can
    display all providers and their connection status.
    """
    providers_info: list[dict] = []
    candidate_names = ["ollama", "openai", "anthropic", "google"]

    for name in candidate_names:
        test_settings = Settings(
            **{**settings.model_dump(), "llm_provider": name}
        )
        try:
            provider = _build_provider(test_settings)
            info = provider.to_info()
            providers_info.append(info)
        except ProviderError as exc:
            providers_info.append({
                "provider": name,
                "available": False,
                "status": "error",
                "error": str(exc),
            })
        except Exception as exc:
            providers_info.append({
                "provider": name,
                "available": False,
                "status": "error",
                "error": str(exc),
            })

    return providers_info
