"""Tests for the grounded chat service and API endpoint."""

from __future__ import annotations

import hashlib
from collections.abc import Generator

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
from app.services.chat_service import ChatService

FIXTURES_DIR = (
    __import__("pathlib").Path(__file__).parent / "fixtures" / "transcripts"
)


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
    def __init__(self, response: str = "Test response from LLM.") -> None:
        self._response = response
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
            content=self._response,
            model=self.model,
            provider=self.name,
            usage={"prompt_tokens": 50, "completion_tokens": 20},
        )

    def to_info(self) -> dict:
        return {"provider": self.name, "model": self.model, "available": True}


FAKE_EMBED = FakeEmbeddingProvider()
FAKE_LLM = FakeLLMProvider()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session_with_knowledge(
    migrated_database: str,
) -> Generator[Session, None, None]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(migrated_database)
    connection = engine.connect()
    transaction = connection.begin()
    for table in ("transcript_chunks", "messages", "chat_sessions", "users"):
        connection.execute(text(f"DELETE FROM {table}"))
    session = sessionmaker(
        bind=connection, autoflush=False, autocommit=False
    )()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
    engine.dispose()


@pytest.fixture()
def chat_client(
    db_session_with_knowledge: Session,
) -> Generator[TestClient, None, None]:
    from app.schemas.session import SessionCreateRequest

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

    # Ingest fixture transcripts.
    ingest = IngestionService(
        db_session_with_knowledge, settings,
        embedding_provider=FAKE_EMBED,
    )
    ingest.run()

    # Create a session.
    from app.services.session_service import SessionService
    svc = SessionService(db_session_with_knowledge)
    session = svc.create_session(SessionCreateRequest(title="Test chat"))
    session_id = str(session.id)

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session_with_knowledge
        finally:
            pass

    def override_get_settings() -> Settings:
        return settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    # Patch the providers for the chat service.
    import app.knowledge.embeddings as embeddings_mod
    import app.providers.factory as factory_mod
    import app.services.chat_service as chat_service_mod

    old_embedding = embeddings_mod.get_embedding_provider
    old_llm = factory_mod.get_llm_provider
    old_chat_llm = chat_service_mod.get_llm_provider
    embeddings_mod.get_embedding_provider = lambda s: FAKE_EMBED
    factory_mod.get_llm_provider = lambda s=None: FAKE_LLM
    chat_service_mod.get_llm_provider = lambda s=None: FAKE_LLM

    with TestClient(app) as client:
        client._session_id = session_id  # type: ignore[attr-defined]
        yield client

    chat_service_mod.get_llm_provider = old_chat_llm
    factory_mod.get_llm_provider = old_llm
    embeddings_mod.get_embedding_provider = old_embedding
    app.dependency_overrides.clear()
    reset_session_state()
    reset_provider()


# ---------------------------------------------------------------------------
# ChatService unit tests
# ---------------------------------------------------------------------------


class TestChatServiceUnit:
    def test_format_context_empty(self, db_session_with_knowledge: Session) -> None:
        settings = Settings(
            database_url="unused",
            transcripts_dir=str(FIXTURES_DIR),
            embedding_provider="fake",
        retrieval_min_score=0.0,
            llm_provider="fake",
        )
        svc = ChatService(db_session_with_knowledge, settings)
        result = svc._format_context([])
        assert "No relevant" in result

    def test_format_history_empty(self, db_session_with_knowledge: Session) -> None:
        settings = Settings(
            database_url="unused",
            transcripts_dir=str(FIXTURES_DIR),
            embedding_provider="fake",
        retrieval_min_score=0.0,
            llm_provider="fake",
        )
        svc = ChatService(db_session_with_knowledge, settings)
        result = svc._format_history([])
        assert "No prior" in result

    def test_build_sources_deduplicates(self, db_session_with_knowledge: Session) -> None:
        from app.knowledge.retrieval import RetrievedChunk

        settings = Settings(
            database_url="unused",
            transcripts_dir=str(FIXTURES_DIR),
            embedding_provider="fake",
        retrieval_min_score=0.0,
            llm_provider="fake",
        )
        svc = ChatService(db_session_with_knowledge, settings)
        chunks = [
            RetrievedChunk(
                content="test", score=0.8, source_path="a/transcript.md",
                chunk_index=0, metadata={"title": "Same Title", "guest": "A"},
            ),
            RetrievedChunk(
                content="test2", score=0.7, source_path="a/transcript.md",
                chunk_index=1, metadata={"title": "Same Title", "guest": "A"},
            ),
            RetrievedChunk(
                content="test3", score=0.6, source_path="b/transcript.md",
                chunk_index=0, metadata={"title": "Different", "guest": "B"},
            ),
        ]
        sources = svc._build_sources(chunks)
        titles = {s.title for s in sources}
        assert len(sources) == 2
        assert "Same Title" in titles
        assert "Different" in titles


class TestChatServiceIntegration:
    def test_chat_returns_grounded_response(
        self, db_session_with_knowledge: Session,
    ) -> None:
        settings = Settings(
            database_url="unused",
            transcripts_dir=str(FIXTURES_DIR),
            embedding_provider="fake",
        retrieval_min_score=0.0,
            llm_provider="fake",
        )
        FAKE_LLM._response = "Based on the transcripts, retention is important."
        FAKE_LLM._last_messages = []

        # Ingest fixture transcripts so retrieval has real chunks to ground on.
        ingest = IngestionService(
            db_session_with_knowledge, settings,
            embedding_provider=FAKE_EMBED,
        )
        ingest.run()

        from app.schemas.session import SessionCreateRequest as SCR
        from app.services.session_service import SessionService as SS

        svc = SS(db_session_with_knowledge)
        session = svc.create_session(SCR(title="Test"))

        chat_svc = ChatService(
            db_session_with_knowledge, settings,
            retrieval_service=None, llm_provider=FAKE_LLM,
        )
        chat_svc._retrieval.__init__(
            db_session_with_knowledge, settings,
            embedding_provider=FAKE_EMBED,
        )

        response = chat_svc.chat(
            session_id=session.id,
            user_message="How should startups improve retention?",
        )

        assert response.content == "Based on the transcripts, retention is important."
        assert response.provider == "fake-llm"
        assert len(FAKE_LLM._last_messages) >= 2
        # System prompt is first message.
        assert FAKE_LLM._last_messages[0].role == "system"
        assert "Lenny" in FAKE_LLM._last_messages[0].content

    def test_chat_empty_message_raises(self, db_session_with_knowledge: Session) -> None:
        settings = Settings(
            database_url="unused",
            transcripts_dir=str(FIXTURES_DIR),
            embedding_provider="fake",
        retrieval_min_score=0.0,
            llm_provider="fake",
        )
        from app.schemas.session import SessionCreateRequest as SCR
        from app.services.session_service import SessionService as SS

        svc = SS(db_session_with_knowledge)
        session = svc.create_session(SCR(title="Test"))

        chat_svc = ChatService(
            db_session_with_knowledge, settings, llm_provider=FAKE_LLM,
        )
        chat_svc._retrieval.__init__(
            db_session_with_knowledge, settings,
            embedding_provider=FAKE_EMBED,
        )

        with pytest.raises(ValueError, match="empty"):
            chat_svc.chat(session_id=session.id, user_message="  ")


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestChatAPI:
    def test_chat_endpoint_returns_200(
        self, chat_client: TestClient,
    ) -> None:
        session_id = chat_client._session_id
        response = chat_client.post(
            "/api/chat",
            json={
                "session_id": session_id,
                "message": "How should startups improve retention?",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"]["role"] == "assistant"
        assert len(data["message"]["content"]) > 0
        assert "provider" in data
        assert "grounding_status" in data

    def test_chat_persists_both_messages(
        self, chat_client: TestClient,
    ) -> None:
        session_id = chat_client._session_id
        chat_client.post(
            "/api/chat",
            json={
                "session_id": session_id,
                "message": "What about growth loops?",
            },
        )
        response = chat_client.get(f"/api/sessions/{session_id}")
        data = response.json()
        assert data["message_count"] >= 2
        roles = [m["role"] for m in data["messages"]]
        assert "user" in roles
        assert "assistant" in roles

    def test_chat_invalid_session_returns_404(
        self, chat_client: TestClient,
    ) -> None:
        response = chat_client.post(
            "/api/chat",
            json={
                "session_id": "00000000-0000-0000-0000-000000000001",
                "message": "Hello?",
            },
        )
        assert response.status_code == 404

    def test_chat_empty_message_returns_422(
        self, chat_client: TestClient,
    ) -> None:
        session_id = chat_client._session_id
        response = chat_client.post(
            "/api/chat",
            json={"session_id": session_id, "message": ""},
        )
        assert response.status_code == 422

    def test_chat_includes_sources(
        self, chat_client: TestClient,
    ) -> None:
        session_id = chat_client._session_id
        response = chat_client.post(
            "/api/chat",
            json={
                "session_id": session_id,
                "message": "Tell me about product-market fit",
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Sources may be empty or non-empty depending on retrieval;
        # but the key must always be present.
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_follow_up_uses_conversation_context(
        self, chat_client: TestClient,
    ) -> None:
        session_id = chat_client._session_id
        # First message.
        chat_client.post(
            "/api/chat",
            json={
                "session_id": session_id,
                "message": "What is product-market fit?",
            },
        )
        # Follow-up that references prior context.
        response = chat_client.post(
            "/api/chat",
            json={
                "session_id": session_id,
                "message": "Can you tell me more about that?",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["message"]["content"]) > 0
        # Should now have 4 messages (2 user + 2 assistant).
        session_detail = chat_client.get(f"/api/sessions/{session_id}").json()
        assert session_detail["message_count"] == 4
