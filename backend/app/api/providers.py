"""LLM provider API endpoints for listing, status, and runtime switching."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.providers.base import ProviderError
from app.providers.factory import (
    get_llm_provider,
    list_available_providers,
    select_provider,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/providers", tags=["providers"])


class ProviderSelectRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    """Provider name: 'ollama' or 'openai'."""
    model: str | None = None
    """Optional model override (e.g. 'qwen2.5-coder:1.5b')."""


@router.get("")
def list_providers(
    settings: Settings = Depends(get_settings),
) -> dict:
    """List all configured LLM providers and their connection status."""
    providers = list_available_providers(settings)
    active = get_llm_provider(settings)
    return {
        "providers": providers,
        "active_provider": active.name,
        "active_model": active.model,
    }


@router.get("/models")
def list_ollama_models(
    settings: Settings = Depends(get_settings),
) -> dict:
    """List all models available on the Ollama server."""
    base_url = settings.ollama_base_url.rstrip("/")
    # --- Ollama local models ---
    ollama_gen: list[dict] = []
    ollama_embed: list[dict] = []
    try:
        resp = httpx.get(f"{base_url}/api/tags", timeout=10.0)
        resp.raise_for_status()
        raw_models = resp.json().get("models", [])
        for m in raw_models:
            name = m.get("name", "")
            caps = m.get("capabilities", [])
            is_embedding = "embedding" in caps and "completion" not in caps
            entry = {
                "name": name,
                "size": m.get("size", 0),
                "parameter_size": m.get("details", {}).get("parameter_size", ""),
                "family": m.get("details", {}).get("family", ""),
                "context_length": m.get("details", {}).get("context_length", 0),
                "is_embedding": is_embedding,
            }
            if is_embedding:
                ollama_embed.append(entry)
            else:
                ollama_gen.append(entry)
    except httpx.ConnectError:
        logger.warning("Ollama not reachable at %s", base_url)
    except Exception as exc:
        logger.warning("Failed to list Ollama models: %s", exc)

    # --- Cloud provider models (hardcoded popular options) ---
    cloud_models: list[dict] = []

    if settings.openai_api_key:
        cloud_models.extend([
            {
                "name": "gpt-4.1-mini",
                "provider": "openai",
                "family": "GPT-4",
                "context_length": 1047576,
            },
            {
                "name": "gpt-4.1",
                "provider": "openai",
                "family": "GPT-4",
                "context_length": 1047576,
            },
            {
                "name": "gpt-4o",
                "provider": "openai",
                "family": "GPT-4o",
                "context_length": 128000,
            },
            {
                "name": "gpt-4o-mini",
                "provider": "openai",
                "family": "GPT-4o",
                "context_length": 128000,
            },
            {
                "name": "o3-mini",
                "provider": "openai",
                "family": "o3",
                "context_length": 200000,
            },
        ])

    if settings.anthropic_api_key:
        cloud_models.extend([
            {
                "name": "claude-sonnet-4-20250514",
                "provider": "anthropic",
                "family": "Claude 4",
                "context_length": 200000,
            },
            {
                "name": "claude-3-5-sonnet-20241022",
                "provider": "anthropic",
                "family": "Claude 3.5",
                "context_length": 200000,
            },
            {
                "name": "claude-3-5-haiku-20241022",
                "provider": "anthropic",
                "family": "Claude 3.5",
                "context_length": 200000,
            },
        ])

    if settings.google_api_key:
        cloud_models.extend([
            {
                "name": "gemini-2.0-flash",
                "provider": "google",
                "family": "Gemini 2.0",
                "context_length": 1048576,
            },
            {
                "name": "gemini-2.5-pro",
                "provider": "google",
                "family": "Gemini 2.5",
                "context_length": 1048576,
            },
            {
                "name": "gemini-2.5-flash",
                "provider": "google",
                "family": "Gemini 2.5",
                "context_length": 1048576,
            },
        ])

    # Mark cloud models that lack API keys as unavailable
    for m in cloud_models:
        if m["provider"] == "openai":
            m["available"] = bool(settings.openai_api_key)
        elif m["provider"] == "anthropic":
            m["available"] = bool(settings.anthropic_api_key)
        elif m["provider"] == "google":
            m["available"] = bool(settings.google_api_key)
        else:
            m["available"] = False

    return {
        "generation_models": ollama_gen,
        "embedding_models": ollama_embed,
        "cloud_models": cloud_models,
    }


@router.get("/status")
def provider_status(
    settings: Settings = Depends(get_settings),
) -> dict:
    """Return the status of the currently active LLM provider."""
    try:
        provider = get_llm_provider(settings)
        info = provider.to_info()
        info["active"] = True
        return info
    except ProviderError as exc:
        return {
            "active_provider": settings.llm_provider,
            "available": False,
            "status": "error",
            "error": str(exc),
        }


@router.post("/select")
def select_active_provider(
    request: ProviderSelectRequest,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Switch the active LLM provider and/or model at runtime."""
    override: dict = {"llm_provider": request.provider}
    if request.model:
        # Set the model for the selected provider
        provider_lower = request.provider.lower()
        model_map = {
            "ollama": "ollama_model",
            "openai": "openai_model",
            "anthropic": "anthropic_model",
            "google": "google_model",
        }
        if provider_lower in model_map:
            override[model_map[provider_lower]] = request.model
    new_settings = Settings(**{**settings.model_dump(), **override})
    try:
        provider = select_provider(new_settings)
        return {
            "status": "ok",
            "active_provider": provider.name,
            "active_model": provider.model,
            "info": provider.to_info(),
        }
    except ProviderError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to switch provider: {exc}",
        ) from exc
