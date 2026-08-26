"""Embedding provider abstraction.

Providers:
- OllamaEmbeddingProvider: fully local, default for the demo
  (model ``nomic-embed-text``).
- OpenAIEmbeddingProvider: cloud fallback requiring ``OPENAI_API_KEY``.

Both implement the same interface so ingestion and retrieval never depend on a
vendor. Failures raise EmbeddingProviderError with actionable messages.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingProviderError(Exception):
    """Raised when an embedding provider is unreachable or misconfigured."""


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    @property
    def model_name(self) -> str: ...


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError as exc:
        raise EmbeddingProviderError(
            f"Unable to connect to the embedding provider at {url}. "
            "Make sure the service is running and reachable."
        ) from exc
    except httpx.TimeoutException as exc:
        raise EmbeddingProviderError(
            f"The embedding provider at {url} timed out after {timeout}s."
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300]
        raise EmbeddingProviderError(
            f"Embedding provider returned HTTP {exc.response.status_code}: {detail}"
        ) from exc


class OllamaEmbeddingProvider:
    """Local embeddings via the Ollama ``/api/embed`` endpoint."""

    def __init__(self, base_url: str, model: str, timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = _post_json(
            f"{self._base_url}/api/embed",
            {"model": self._model, "input": texts},
            self._timeout,
        )
        embeddings = data.get("embeddings")
        if not embeddings or len(embeddings) != len(texts):
            raise EmbeddingProviderError(
                f"Ollama did not return {len(texts)} embeddings. "
                f"Is the model '{self._model}' installed? Try: ollama pull {self._model}"
            )
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class OpenAIEmbeddingProvider:
    """Cloud embeddings via the OpenAI embeddings API."""

    def __init__(self, api_key: str | None, model: str, timeout: float = 60.0) -> None:
        if not api_key:
            raise EmbeddingProviderError(
                "OpenAI API key is not configured. Configure OPENAI_API_KEY "
                "or switch EMBEDDING_PROVIDER=ollama."
            )
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            response = httpx.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json={"model": self._model, "input": inputs},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise EmbeddingProviderError(
                    "OpenAI rejected the configured API key (HTTP 401)."
                ) from exc
            raise EmbeddingProviderError(
                f"OpenAI embeddings returned HTTP {exc.response.status_code}: "
                f"{exc.response.text[:300]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingProviderError(f"Unable to reach OpenAI embeddings: {exc}") from exc
        data = response.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda d: d["index"])]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Build the configured embedding provider."""
    provider = settings.embedding_provider.lower()
    timeout = settings.embedding_timeout_seconds
    if provider == "ollama":
        logger.info("Using Ollama embeddings (model=%s)", settings.ollama_embedding_model)
        return OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_embedding_model,
            timeout=timeout,
        )
    if provider == "openai":
        logger.info("Using OpenAI embeddings (model=%s)", settings.openai_embedding_model)
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            timeout=timeout,
        )
    raise EmbeddingProviderError(
        f"Unknown EMBEDDING_PROVIDER '{settings.embedding_provider}'. "
        "Supported values: ollama, openai."
    )
