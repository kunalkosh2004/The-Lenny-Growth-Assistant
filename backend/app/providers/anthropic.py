"""Anthropic Claude LLM provider implementation.

Uses the Anthropic Messages API (``/v1/messages``).
Requires a valid ``ANTHROPIC_API_KEY`` environment variable.
"""

from __future__ import annotations

import logging

import httpx

from app.providers.base import (
    ChatMessage,
    GenerateResult,
    ProviderAuthError,
    ProviderError,
    ProviderModelNotFoundError,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60.0


class AnthropicProvider:
    """Cloud LLM provider backed by the Anthropic API."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key:
            raise ProviderError(
                "Anthropic API key is not configured. Set ANTHROPIC_API_KEY or "
                "switch LLM_PROVIDER=ollama."
            )
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._base_url = "https://api.anthropic.com"

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _handle_http_error(self, exc: httpx.HTTPStatusError) -> None:
        status = exc.response.status_code
        if status == 401:
            raise ProviderAuthError(
                "Anthropic rejected the configured API key (HTTP 401). "
                "Verify your ANTHROPIC_API_KEY."
            ) from exc
        if status == 429:
            raise ProviderError(
                "Anthropic rate limit exceeded (HTTP 429). "
                "Retry shortly or use a different provider."
            ) from exc
        if status == 404:
            raise ProviderModelNotFoundError(
                f"Model '{self._model}' was not found on Anthropic (HTTP 404). "
                "Check ANTHROPIC_MODEL."
            ) from exc
        raise ProviderError(
            f"Anthropic returned HTTP {status}: {exc.response.text[:300]}"
        ) from exc

    def is_available(self) -> bool:
        try:
            # Anthropic doesn't have a models list endpoint; try a minimal request.
            resp = httpx.post(
                f"{self._base_url}/v1/messages",
                headers=self._headers(),
                json={
                    "model": self._model,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
                timeout=min(self._timeout, 10.0),
            )
            if resp.status_code == 401:
                return False
            if resp.status_code == 200:
                return True
            # Model not found or other error — still mark as available if key works.
            return resp.status_code not in (400, 404)
        except Exception:
            logger.debug("Anthropic availability check failed", exc_info=True)
            return False

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> GenerateResult:
        # Separate system message from conversation messages (Anthropic requires it).
        system_text = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_text += m.content + "\n"
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        if not chat_messages:
            raise ProviderError("No user/assistant messages to send to Anthropic.")

        payload: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": chat_messages,
            "temperature": temperature,
        }
        if system_text.strip():
            payload["system"] = system_text.strip()

        try:
            resp = httpx.post(
                f"{self._base_url}/v1/messages",
                headers=self._headers(),
                json=payload,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"Anthropic generation timed out after {self._timeout}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._handle_http_error(exc)

        data = resp.json()
        # Extract text from content blocks.
        content_blocks = data.get("content", [])
        content = "".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        )
        usage = data.get("usage", {})

        return GenerateResult(
            content=content,
            model=self._model,
            provider=self.name,
            usage=usage,
        )

    def to_info(self) -> dict:
        available = self.is_available()
        return {
            "provider": self.name,
            "model": self._model,
            "available": available,
            "status": "connected" if available else "disconnected",
        }
