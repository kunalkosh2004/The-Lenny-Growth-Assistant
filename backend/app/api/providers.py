"""LLM provider API endpoints for listing, status, and runtime switching."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.providers.base import ProviderError
from app.providers.factory import (
    get_llm_provider,
    list_available_providers,
    select_provider,
)

router = APIRouter(prefix="/api/providers", tags=["providers"])


class ProviderSelectRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    """Provider name: 'ollama' or 'openai'."""


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
    """Switch the active LLM provider at runtime without restarting."""
    new_settings = Settings(
        **{**settings.model_dump(), "llm_provider": request.provider}
    )
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
