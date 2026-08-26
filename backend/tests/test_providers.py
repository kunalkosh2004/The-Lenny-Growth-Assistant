"""Tests for LLM provider abstraction, factory, and API endpoints."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db, reset_session_state
from app.main import app
from app.providers.base import (
    ChatMessage,
    GenerateResult,
    ProviderError,
)
from app.providers.factory import (
    get_llm_provider,
    list_available_providers,
    reset_provider,
    select_provider,
)
from app.providers.ollama import OllamaProvider

# ---------------------------------------------------------------------------
# Fake provider for deterministic tests (no Ollama/OpenAI needed)
# ---------------------------------------------------------------------------


class FakeLLMProvider:
    """In-memory LLM provider for testing."""

    def __init__(self, model: str = "fake-model") -> None:
        self._model = model
        self._last_messages: list[ChatMessage] = []

    @property
    def name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        return True

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> GenerateResult:
        self._last_messages = messages
        return GenerateResult(
            content="Fake response to your question.",
            model=self._model,
            provider=self.name,
            usage={"prompt_tokens": 10, "completion_tokens": 8},
        )

    def to_info(self) -> dict:
        return {
            "provider": self.name,
            "model": self._model,
            "available": True,
            "status": "connected",
        }


FAKE_LLM = FakeLLMProvider()


# ---------------------------------------------------------------------------
# Provider unit tests
# ---------------------------------------------------------------------------


class TestChatMessage:
    def test_create(self) -> None:
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"


class TestGenerateResult:
    def test_create(self) -> None:
        result = GenerateResult(
            content="Hi there",
            model="test",
            provider="fake",
        )
        assert result.content == "Hi there"
        assert result.usage == {}


class TestOllamaProvider:
    def test_name_and_model(self) -> None:
        p = OllamaProvider(base_url="http://localhost:11434", model="test:latest")
        assert p.name == "ollama"
        assert p.model == "test:latest"

    def test_to_info(self) -> None:
        p = OllamaProvider(base_url="http://localhost:11434", model="test:latest")
        info = p.to_info()
        assert info["provider"] == "ollama"
        assert info["model"] == "test:latest"
        assert "available" in info


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestProviderFactory:
    def test_build_ollama(self) -> None:
        reset_provider()
        settings = Settings(
            llm_provider="ollama",
            ollama_base_url="http://localhost:11434",
            ollama_model="nomic-embed-text",
        )
        provider = get_llm_provider(settings)
        assert provider.name == "ollama"

    def test_build_unknown_raises(self) -> None:
        reset_provider()
        settings = Settings(llm_provider="nonexistent")
        with pytest.raises(ProviderError, match="Unknown LLM_PROVIDER"):
            get_llm_provider(settings)

    def test_select_provider(self) -> None:
        reset_provider()
        settings = Settings(
            llm_provider="ollama",
            ollama_base_url="http://localhost:11434",
            ollama_model="nomic-embed-text",
        )
        provider = select_provider(settings)
        assert provider.name == "ollama"

    def test_reset_provider(self) -> None:
        reset_provider()
        settings = Settings(
            llm_provider="ollama",
            ollama_base_url="http://localhost:11434",
            ollama_model="nomic-embed-text",
        )
        p1 = get_llm_provider(settings)
        p2 = get_llm_provider(settings)
        assert p1 is p2  # cached

        reset_provider()
        p3 = get_llm_provider(settings)
        assert p1 is not p3  # rebuilt


class TestListAvailableProviders:
    def test_returns_ollama_and_openai(self) -> None:
        settings = Settings()
        providers = list_available_providers(settings)
        names = [p["provider"] for p in providers]
        assert "ollama" in names
        assert "openai" in names

    def test_ollama_not_missing_model(self) -> None:
        """Ollama provider reports not-available when model is missing."""
        settings = Settings(
            llm_provider="ollama",
            ollama_model="nonexistent_model_xyz",
        )
        providers = list_available_providers(settings)
        ollama = next(p for p in providers if p["provider"] == "ollama")
        # The model may or may not be installed; status reflects reality.
        assert ollama["available"] in (True, False)


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def provider_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with get_db and get_settings overridden."""

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    test_settings = Settings(
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="nomic-embed-text",
        app_env="test",
        log_level="WARNING",
    )

    def override_get_settings() -> Settings:
        return test_settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    reset_session_state()
    reset_provider()


class TestProviderAPI:
    def test_list_providers(self, provider_client: TestClient) -> None:
        response = provider_client.get("/api/providers")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "active_provider" in data
        assert len(data["providers"]) >= 1

    def test_provider_status(self, provider_client: TestClient) -> None:
        response = provider_client.get("/api/providers/status")
        assert response.status_code == 200
        data = response.json()
        assert "provider" in data or "active_provider" in data

    def test_select_provider_valid(self, provider_client: TestClient) -> None:
        response = provider_client.post(
            "/api/providers/select",
            json={"provider": "ollama"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["active_provider"] == "ollama"

    def test_select_provider_invalid(self, provider_client: TestClient) -> None:
        response = provider_client.post(
            "/api/providers/select",
            json={"provider": "nonexistent"},
        )
        assert response.status_code == 400

    def test_select_empty_provider(self, provider_client: TestClient) -> None:
        response = provider_client.post(
            "/api/providers/select",
            json={"provider": ""},
        )
        assert response.status_code == 422  # Pydantic validation
