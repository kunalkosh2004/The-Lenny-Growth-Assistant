"""LLM provider abstraction.

Every provider implements a common interface so the application can switch
between Ollama and cloud providers without changing business logic. The
provider is selected via the ``LLM_PROVIDER`` environment variable (or
runtime override) and instantiated through the factory in ``factory.py``.

Design choices:

- The interface is deliberately minimal: a chat-completions-style
  ``generate`` method plus introspection properties.  This keeps the
  contract stable as new providers are added.
- Providers raise ``ProviderError`` (or a subclass) on connection failures,
  auth issues, or timeouts so callers get actionable error messages instead
  of opaque HTTP exceptions.
- Providers never log secrets.  API keys are accepted via constructor args
  only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Raised when an LLM provider is unreachable or misconfigured."""


class ProviderTimeoutError(ProviderError):
    """Raised when the provider does not respond within the configured timeout."""


class ProviderAuthError(ProviderError):
    """Raised when the provider rejects the configured credentials."""


class ProviderModelNotFoundError(ProviderError):
    """Raised when the requested model is not available on the provider."""


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class GenerateResult:
    content: str
    model: str
    provider: str
    usage: dict = field(default_factory=dict)
    """Token usage: ``{"prompt_tokens": int, "completion_tokens": int, ...}``"""


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol that every LLM provider must satisfy."""

    @property
    def name(self) -> str:
        """Human-readable provider name, e.g. ``'ollama'``."""
        ...

    @property
    def model(self) -> str:
        """Currently configured model identifier."""
        ...

    def is_available(self) -> bool:
        """Return ``True`` if the provider is reachable and healthy.

        Implementations should perform a lightweight connectivity check
        (e.g. listing models or a ping) and return ``False`` on any error
        rather than raising.
        """
        ...

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> GenerateResult:
        """Send a chat-style request and return the assistant response.

        Raises ``ProviderError`` on failures.
        """
        ...

    def to_info(self) -> dict:
        """Return a JSON-serialisable snapshot of the provider state."""
        ...
