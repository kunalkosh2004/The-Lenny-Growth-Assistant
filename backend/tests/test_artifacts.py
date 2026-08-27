"""Tests for artifact generation service and API endpoints."""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db, reset_session_state
from app.knowledge.ingest import IngestionService
from app.main import app
from app.providers.base import ChatMessage, GenerateResult
from app.providers.factory import reset_provider
from app.services.artifact_service import ArtifactResult, ArtifactService

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "transcripts"


# ---------------------------------------------------------------------------
# Fake providers
# ---------------------------------------------------------------------------


class FakeEmbeddingProvider:
    def __init__(self, dim: int = 16) -> None:
        self._dim = dim

    @property
    def model_name(self) -> str:
        return "fake"

    def _hash_to_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vec: list[float] = []
        for i in range(self._dim):
            byte_val = digest[i % len(digest)]
            vec.append((byte_val / 255.0) * 2 - 1)
        norm = sum(v * v for v in vec) ** 0.5
        return [v / norm for v in vec] if norm > 0 else vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_to_vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._hash_to_vector(text)


class FakeLLMProvider:
    def __init__(self, content: str = "# Test Artifact\n\nTest content.") -> None:
        self._content = content
        self._last_messages: list[ChatMessage] = []

    @property
    def name(self) -> str:
        return "fake-llm"

    @property
    def model(self) -> str:
        return "fake-model"

    def is_available(self) -> bool:
        return True

    def generate(
        self, messages: list[ChatMessage], *, temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> GenerateResult:
        self._last_messages = messages
        return GenerateResult(
            content=self._content,
            model=self.model,
            provider=self.name,
            usage={"prompt_tokens": 50, "completion_tokens": 20},
        )

    def to_info(self) -> dict:
        return {"provider": self.name, "model": self.model, "available": True}


FAKE_EMBED = FakeEmbeddingProvider()
FAKE_LLM = FakeLLMProvider()


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestArtifactService:
    def test_generate_markdown(self) -> None:
        fake_llm = FakeLLMProvider(
            content="# Growth Strategy\n\n## Overview\n\nThis is a test."
        )

        class MockRetrieval:
            def search(self, query, top_k=10):
                from app.knowledge.retrieval import RetrievedChunk
                return [
                    RetrievedChunk(
                        content="Growth loops are powerful.",
                        score=0.8,
                        source_path="test/transcript.md",
                        chunk_index=0,
                        metadata={"title": "Growth", "guest": "Test"},
                    )
                ]

        service = ArtifactService(MockRetrieval(), fake_llm)
        result = service.generate("markdown", "Create a growth strategy document")
        assert isinstance(result, ArtifactResult)
        assert result.artifact_type == "markdown"
        assert "Growth Strategy" in result.content
        assert len(result.sources) == 1

    def test_generate_html(self) -> None:
        fake_llm = FakeLLMProvider(
            content=(
                "<!DOCTYPE html><html><head><title>Test Page</title>"
                "<style>body{font-family:sans-serif;}</style></head>"
                "<body><h1>Landing Page</h1><p>Content here.</p></body></html>"
            )
        )

        class MockRetrieval:
            def search(self, query, top_k=10):
                return []

        service = ArtifactService(MockRetrieval(), fake_llm)
        result = service.generate("html", "Create a landing page")
        assert result.artifact_type == "html"
        assert "<!DOCTYPE html>" in result.content
        assert result.title == "Test Page"

    def test_invalid_type_raises(self) -> None:
        fake_llm = FakeLLMProvider()
        service = ArtifactService(None, fake_llm)
        with pytest.raises(ValueError, match="Invalid artifact type"):
            service.generate("pdf", "test")

    def test_empty_request_raises(self) -> None:
        fake_llm = FakeLLMProvider()
        service = ArtifactService(None, fake_llm)
        with pytest.raises(ValueError, match="empty"):
            service.generate("markdown", "  ")

    def test_extract_title_markdown(self) -> None:
        fake_llm = FakeLLMProvider()
        service = ArtifactService(None, fake_llm)
        title = service._extract_title("# My Article\n\nContent", "markdown")
        assert title == "My Article"

    def test_extract_title_html(self) -> None:
        fake_llm = FakeLLMProvider()
        service = ArtifactService(None, fake_llm)
        html = "<html><head><title>Page Title</title></head></html>"
        title = service._extract_title(html, "html")
        assert title == "Page Title"

    def test_extract_title_fallback(self) -> None:
        fake_llm = FakeLLMProvider()
        service = ArtifactService(None, fake_llm)
        title = service._extract_title("No heading here", "markdown")
        assert title == "Generated Artifact"

    def test_format_context_empty(self) -> None:
        fake_llm = FakeLLMProvider()
        service = ArtifactService(None, fake_llm)
        assert "No relevant" in service._format_context([])

    def test_build_sources_deduplicates(self) -> None:
        from app.knowledge.retrieval import RetrievedChunk

        fake_llm = FakeLLMProvider()
        service = ArtifactService(None, fake_llm)
        chunks = [
            RetrievedChunk(
                content="a", score=0.9, source_path="x/transcript.md",
                chunk_index=0, metadata={"title": "Same", "guest": "A"},
            ),
            RetrievedChunk(
                content="b", score=0.8, source_path="x/transcript.md",
                chunk_index=1, metadata={"title": "Same", "guest": "A"},
            ),
        ]
        sources = service._build_sources(chunks)
        assert len(sources) == 1

    def test_result_to_dict(self) -> None:
        result = ArtifactResult(
            content="test", artifact_type="html", title="T",
            sources=[{"title": "x"}],
        )
        d = result.to_dict()
        assert d["type"] == "html"
        assert d["title"] == "T"


# ---------------------------------------------------------------------------
# Security tests
# ---------------------------------------------------------------------------


class TestArtifactSecurity:
    """Tests that validate the artifact security model.

    Generated HTML should be safe to render in a sandboxed iframe.
    These tests verify that the system:
    1. Stores HTML artifacts as plain text (not executed on the server).
    2. Provides type metadata so the frontend can render in a sandboxed iframe.
    3. Does not expose any server-side rendering or evaluation of HTML.
    """

    def test_html_stored_as_text_not_executed(self) -> None:
        """HTML content is stored as a string, never eval'd or rendered server-side."""
        fake_llm = FakeLLMProvider(
            content='<html><body><script>alert("xss")</script></body></html>'
        )

        class MockRetrieval:
            def search(self, query, top_k=10):
                return []

        service = ArtifactService(MockRetrieval(), fake_llm)
        result = service.generate("html", "Create a page with a script")
        # Content should be the raw string — not executed.
        assert '<script>alert("xss")</script>' in result.content
        assert result.artifact_type == "html"

    def test_artifact_type_is_metadata_only(self) -> None:
        """The type field tells the frontend how to render, not the backend."""
        result = ArtifactResult(
            content="<p>Hello</p>",
            artifact_type="html",
            title="Test",
        )
        d = result.to_dict()
        assert d["type"] == "html"
        # The backend never processes the HTML — it just stores it.


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def artifact_client(
    migrated_database: str,
) -> Generator[TestClient, None, None]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(migrated_database)
    connection = engine.connect()
    transaction = connection.begin()
    for table in ("transcript_chunks", "artifacts", "messages", "chat_sessions", "users"):
        connection.execute(text(f"DELETE FROM {table}"))
    db_session = sessionmaker(
        bind=connection, autoflush=False, autocommit=False
    )()

    settings = Settings(
        database_url="unused",
        transcripts_dir=str(FIXTURES_DIR),
        embedding_provider="fake",
        retrieval_min_score=0.0,
        chunk_target_chars=400,
        chunk_overlap_chars=50,
        ingestion_batch_size=16,
        llm_provider="fake",
        app_env="test",
        log_level="WARNING",
    )
    IngestionService(db_session, settings, embedding_provider=FAKE_EMBED).run()

    # Create a session for artifact tests.
    from app.schemas.session import SessionCreateRequest
    from app.services.session_service import SessionService
    svc = SessionService(db_session)
    session = svc.create_session(SessionCreateRequest(title="Artifact session"))
    session_id = str(session.id)

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    def override_get_settings() -> Settings:
        return settings

    import app.api.artifacts as artifacts_mod
    import app.knowledge.embeddings as embeddings_mod
    import app.providers.factory as factory_mod

    old_emb = embeddings_mod.get_embedding_provider
    old_llm = factory_mod.get_llm_provider
    old_artifacts_llm = artifacts_mod.get_llm_provider
    embeddings_mod.get_embedding_provider = lambda s: FAKE_EMBED
    factory_mod.get_llm_provider = lambda s=None: FAKE_LLM
    artifacts_mod.get_llm_provider = lambda s=None: FAKE_LLM

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    with TestClient(app) as client:
        client._session_id = session_id  # type: ignore[attr-defined]
        yield client

    factory_mod.get_llm_provider = old_llm
    artifacts_mod.get_llm_provider = old_artifacts_llm
    embeddings_mod.get_embedding_provider = old_emb
    app.dependency_overrides.clear()
    reset_session_state()
    reset_provider()
    db_session.close()
    transaction.rollback()
    connection.close()
    engine.dispose()


class TestArtifactAPI:
    def test_generate_markdown_artifact(
        self, artifact_client: TestClient,
    ) -> None:
        FAKE_LLM._content = "# Growth Strategy\n\n## Key Insights\n\nGrowth matters."
        response = artifact_client.post(
            "/api/artifacts/generate",
            json={
                "session_id": artifact_client._session_id,
                "artifact_type": "markdown",
                "request": "Create a growth strategy document",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "markdown"
        assert len(data["content"]) > 0
        assert "artifact_id" in data

    def test_generate_html_artifact(
        self, artifact_client: TestClient,
    ) -> None:
        FAKE_LLM._content = (
            "<!DOCTYPE html><html><head><title>Landing</title>"
            "<style>body{font-family:sans-serif;}</style></head>"
            "<body><h1>Landing Page</h1><p>Content</p></body></html>"
        )
        response = artifact_client.post(
            "/api/artifacts/generate",
            json={
                "session_id": artifact_client._session_id,
                "artifact_type": "html",
                "request": "Create a landing page",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "html"
        assert "<!DOCTYPE html>" in data["content"]

    def test_invalid_type_returns_422(
        self, artifact_client: TestClient,
    ) -> None:
        response = artifact_client.post(
            "/api/artifacts/generate",
            json={
                "session_id": artifact_client._session_id,
                "artifact_type": "pdf",
                "request": "Create a PDF",
            },
        )
        assert response.status_code == 422

    def test_get_artifact(self, artifact_client: TestClient) -> None:
        FAKE_LLM._content = "# Test\n\nContent."
        gen = artifact_client.post(
            "/api/artifacts/generate",
            json={
                "session_id": artifact_client._session_id,
                "artifact_type": "markdown",
                "request": "Create a test document",
            },
        )
        artifact_id = gen.json()["artifact_id"]
        response = artifact_client.get(f"/api/artifacts/{artifact_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "markdown"
        assert "content" in data

    def test_get_nonexistent_returns_404(
        self, artifact_client: TestClient,
    ) -> None:
        response = artifact_client.get(
            "/api/artifacts/00000000-0000-0000-0000-000000000001",
        )
        assert response.status_code == 404

    def test_list_session_artifacts(
        self, artifact_client: TestClient,
    ) -> None:
        FAKE_LLM._content = "# List Test\n\nContent."
        artifact_client.post(
            "/api/artifacts/generate",
            json={
                "session_id": artifact_client._session_id,
                "artifact_type": "markdown",
                "request": "Create a document for listing",
            },
        )
        response = artifact_client.get(
            f"/api/artifacts/session/{artifact_client._session_id}",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert data["artifacts"][0]["type"] == "markdown"
