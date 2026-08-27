"""Ollama LLM provider implementation.

Uses the Ollama HTTP API (``/api/chat``) for chat completions and
``/api/tags`` for model listing.  Fully local — no API key required.

Behaviour:

- ``is_available()`` pings ``/api/tags`` and checks the configured model
  is present.
- ``generate()`` posts to ``/api/chat`` and streams the full response.
- ``ProviderModelNotFoundError`` is raised when the model is missing.
- ``ProviderTimeoutError`` is raised on network timeouts.
"""

from __future__ import annotations

import logging

import httpx

from app.providers.base import (
    ChatMessage,
    GenerateResult,
    ProviderError,
    ProviderModelNotFoundError,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60.0


class OllamaProvider:
    """Local LLM provider backed by Ollama."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    # ------------------------------------------------------------------
    # Health / availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        try:
            models = self._list_models()
            return any(m.get("name", "").startswith(self._model) for m in models)
        except ProviderError:
            return False
        except Exception:
            logger.debug("Ollama availability check failed", exc_info=True)
            return False

    def _list_models(self) -> list[dict]:
        try:
            resp = httpx.get(
                f"{self._base_url}/api/tags",
                timeout=min(self._timeout, 10.0),
            )
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise ProviderError(
                f"Unable to connect to Ollama at {self._base_url}. "
                "Make sure Ollama is running."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"Ollama connection timed out at {self._base_url}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Ollama returned HTTP {exc.response.status_code}"
            ) from exc
        return resp.json().get("models", [])

    def _ensure_model(self) -> None:
        models = self._list_models()
        if not any(m.get("name", "").startswith(self._model) for m in models):
            available = [m.get("name", "") for m in models]
            raise ProviderModelNotFoundError(
                f"Model '{self._model}' is not installed in Ollama. "
                f"Available models: {available or '(none)'}. "
                f"Run: ollama pull {self._model}"
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
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            resp = httpx.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise ProviderError(
                f"Unable to connect to Ollama at {self._base_url} for generation."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"Ollama generation timed out after {self._timeout}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Ollama returned HTTP {exc.response.status_code} during generation: "
                f"{exc.response.text[:300]}"
            ) from exc

        data = resp.json()
        content = data.get("message", {}).get("content", "")
        if not content:
            raise ProviderError(
                "Ollama returned an empty response. The model may not support "
                "chat-style prompts."
            )

        # Ollama returns eval_count as an integer; normalize to a dict.
        eval_count = data.get("eval_count", 0)
        usage: dict = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": eval_count,
            "total_tokens": data.get("prompt_eval_count", 0) + eval_count,
        }

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
            "base_url": self._base_url,
            "available": available,
            "status": "connected" if available else "disconnected",
        }
