"""Google Gemini LLM provider implementation.

Uses the Google AI Generative Language API (``/v1beta/models``).
Requires a valid ``GOOGLE_API_KEY`` environment variable.
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


class GoogleProvider:
    """Cloud LLM provider backed by the Google Gemini API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key:
            raise ProviderError(
                "Google API key is not configured. Set GOOGLE_API_KEY or "
                "switch LLM_PROVIDER=ollama."
            )
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._base_url = "https://generativelanguage.googleapis.com"

    @property
    def name(self) -> str:
        return "google"

    @property
    def model(self) -> str:
        return self._model

    def _handle_http_error(self, exc: httpx.HTTPStatusError) -> None:
        status = exc.response.status_code
        if status == 401 or status == 403:
            raise ProviderAuthError(
                "Google rejected the configured API key (HTTP 401/403). "
                "Verify your GOOGLE_API_KEY."
            ) from exc
        if status == 429:
            raise ProviderError(
                "Google rate limit exceeded (HTTP 429). "
                "Retry shortly or use a different provider."
            ) from exc
        if status == 404:
            raise ProviderModelNotFoundError(
                f"Model '{self._model}' was not found on Google (HTTP 404). "
                "Check GOOGLE_MODEL."
            ) from exc
        raise ProviderError(
            f"Google returned HTTP {status}: {exc.response.text[:300]}"
        ) from exc

    def is_available(self) -> bool:
        try:
            resp = httpx.get(
                f"{self._base_url}/v1beta/models/{self._model}",
                params={"key": self._api_key},
                timeout=min(self._timeout, 10.0),
            )
            if resp.status_code in (401, 403):
                return False
            return resp.status_code == 200
        except Exception:
            logger.debug("Google availability check failed", exc_info=True)
            return False

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> GenerateResult:
        # Build contents for Gemini API.
        contents = []
        for m in messages:
            role = "model" if m.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m.content}]})

        if not contents:
            raise ProviderError("No messages to send to Google Gemini.")

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                # Gemini 2.5 models spend part of maxOutputTokens on internal
                # "thinking" before producing visible text, which can silently
                # truncate longer completions (e.g. a full HTML+CSS document)
                # well before the visible output looks anywhere near the
                # limit. Disable it for this app's use cases (grounded Q&A,
                # artifact/article generation), none of which need extended
                # reasoning. Ignored harmlessly by models that don't support it.
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }

        try:
            resp = httpx.post(
                f"{self._base_url}/v1beta/models/{self._model}:generateContent",
                params={"key": self._api_key},
                json=payload,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"Google generation timed out after {self._timeout}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._handle_http_error(exc)

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ProviderError("Google Gemini returned no candidates.")

        parts = candidates[0].get("content", {}).get("parts", [])
        content = "".join(part.get("text", "") for part in parts)
        usage = data.get("usageMetadata", {})

        finish_reason = candidates[0].get("finishReason", "")
        if finish_reason == "MAX_TOKENS" and not content.strip():
            raise ProviderError(
                "Google Gemini hit its token limit before producing any "
                "visible output (likely spent on internal reasoning). "
                "Try again or increase max_tokens."
            )

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
