"""OpenAI LLM provider implementation.

Uses the OpenAI Chat Completions API (``/v1/chat/completions``).
Requires a valid ``OPENAI_API_KEY`` environment variable.

Behaviour:

- ``is_available()`` makes a lightweight ``/v1/models`` call and checks
  the configured model is listed.
- ``generate()`` posts to ``/v1/chat/completions``.
- ``ProviderAuthError`` is raised on HTTP 401.
- ``ProviderModelNotFoundError`` is raised when the model is missing.
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


class OpenAIProvider:
    """Cloud LLM provider backed by the OpenAI API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1-mini",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key:
            raise ProviderError(
                "OpenAI API key is not configured. Set OPENAI_API_KEY or "
                "switch LLM_PROVIDER=ollama."
            )
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._base_url = "https://api.openai.com"

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _handle_http_error(self, exc: httpx.HTTPStatusError) -> None:
        status = exc.response.status_code
        if status == 401:
            raise ProviderAuthError(
                "OpenAI rejected the configured API key (HTTP 401). "
                "Verify your OPENAI_API_KEY."
            ) from exc
        if status == 429:
            raise ProviderError(
                "OpenAI rate limit exceeded (HTTP 429). "
                "Retry shortly or use a different provider."
            ) from exc
        if status == 404:
            raise ProviderModelNotFoundError(
                f"Model '{self._model}' was not found on OpenAI (HTTP 404). "
                "Check OPENAI_MODEL."
            ) from exc
        raise ProviderError(
            f"OpenAI returned HTTP {status}: {exc.response.text[:300]}"
        ) from exc

    # ------------------------------------------------------------------
    # Health / availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        try:
            resp = httpx.get(
                f"{self._base_url}/v1/models",
                headers=self._headers(),
                timeout=min(self._timeout, 10.0),
            )
            if resp.status_code == 401:
                return False
            resp.raise_for_status()
            models = resp.json().get("data", [])
            return any(m.get("id") == self._model for m in models)
        except Exception:
            logger.debug("OpenAI availability check failed", exc_info=True)
            return False

    def _ensure_model(self) -> None:
        resp = httpx.get(
            f"{self._base_url}/v1/models",
            headers=self._headers(),
            timeout=min(self._timeout, 10.0),
        )
        if resp.status_code == 401:
            raise ProviderAuthError(
                "OpenAI rejected the configured API key (HTTP 401)."
            )
        resp.raise_for_status()
        models = resp.json().get("data", [])
        if not any(m.get("id") == self._model for m in models):
            available = [m.get("id", "") for m in models]
            raise ProviderModelNotFoundError(
                f"Model '{self._model}' is not available on OpenAI. "
                f"Available models include: {available[:10]}. "
                "Check OPENAI_MODEL."
            )

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> GenerateResult:
        self._ensure_model()

        payload = {
            "model": self._model,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = httpx.post(
                f"{self._base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"OpenAI generation timed out after {self._timeout}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._handle_http_error(exc)

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return GenerateResult(
            content=content,
            model=self._model,
            provider=self.name,
            usage=usage,
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def to_info(self) -> dict:
        available = self.is_available()
        return {
            "provider": self.name,
            "model": self._model,
            "available": available,
            "status": "connected" if available else "disconnected",
        }
