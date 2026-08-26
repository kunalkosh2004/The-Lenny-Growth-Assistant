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
    try:
        resp = httpx.get(f"{base_url}/api/tags", timeout=10.0)
        resp.raise_for_status()
        raw_models = resp.json().get("models", [])
        models = []
        for m in raw_models:
            name = m.get("name", "")
            # Separate generation models from embedding models
            caps = m.get("capabilities", [])
            is_embedding = "embedding" in caps and "completion" not in caps
            models.append({
                "name": name,
                "size": m.get("size", 0),
                "parameter_size": m.get("details", {}).get("parameter_size", ""),
                "family": m.get("details", {}).get("family", ""),
                "context_length": m.get("details", {}).get("context_length", 0),
                "is_embedding": is_embedding,
            })
        generation_models = [m for m in models if not m["is_embedding"]]
        embedding_models = [m for m in models if m["is_embedding"]]
        return {
            "generation_models": generation_models,
            "embedding_models": embedding_models,
        }
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Unable to connect to Ollama. Make sure Ollama is running.",
        ) from None
    except Exception as exc:
        logger.error("Failed to list Ollama models: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list Ollama models: {exc}",
        ) from exc


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
        if request.provider.lower() == "ollama":
            override["ollama_model"] = request.model
        elif request.provider.lower() == "openai":
            override["openai_model"] = request.model
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
