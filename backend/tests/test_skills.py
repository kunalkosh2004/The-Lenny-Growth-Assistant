"""Tests for the Ship 30 writing skill and API endpoint."""

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
from app.skills.ship30 import Ship30Skill, SkillResult

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
    """Returns different content for outline vs article pass."""

    def __init__(self) -> None:
        self._call_count = 0
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
        self._call_count += 1

        if self._call_count == 1:
            # Outline pass.
            return GenerateResult(
                content=(
                    "# Outline\n\n## Hook\nBold claim."
                    "\n\n## Section 1\nKey insight."
                    "\n\n## Conclusion\nTakeaway."
                ),
                model=self.model, provider=self.name,
            )
        else:
            # Article pass.
            article = (
                "# Why Retention Is the Only Growth Metric That Matters\n\n"
                "If your users aren't coming back, nothing else matters.\n\n"
                "## The Foundation of Growth\n\n"
                "**Retention** is the foundation that all growth is built on. "
                "As Derek Sivers explains, at CD Baby, retention came from "
                "listening to every customer email and fixing problems fast. "
                "This created trust that made customers want to stay.\n\n"
                "The key insight is that retention starts with **activation**. "
                "If users don't get value in the first session, they never "
                "come back.\n\n"
                "## Growth Loops Compound on Retention\n\n"
                "Growth loops are what make retention compound. When a retained "
                "user brings in a new user, and that new user also retains, "
                "you get a flywheel.\n\n"
                "Sarah Chen emphasizes that you need to nail the core value "
                "proposition before trying to scale growth.\n\n"
                "## The Metrics That Matter\n\n"
                "Focus on three metrics:\n\n"
                "- **Activation rate**: percentage reaching the aha moment\n"
                "- **Retention curves**: week-over-week cohort retention\n"
                "- **Revenue per user**: per-user economics\n\n"
                "Everything else is a vanity metric until these are solid.\n\n"
                "## Key Takeaway\n\n"
                "Start with retention. Nail activation. Then build growth "
                "loops on top. The rest follows."
            )
            return GenerateResult(
                content=article, model=self.model, provider=self.name,
                usage={"prompt_tokens": 100, "completion_tokens": 200},
            )

    def to_info(self) -> dict:
        return {"provider": self.name, "model": self.model, "available": True}


FAKE_EMBED = FakeEmbeddingProvider()
FAKE_LLM = FakeLLMProvider()


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestShip30Skill:
    def test_generate_returns_article(self) -> None:
        """Test with a mock retrieval that returns chunks."""
        fake_llm = FakeLLMProvider()

        class MockRetrieval:
            def search(self, query, top_k=10):
                from app.knowledge.retrieval import RetrievedChunk

                return [
                    RetrievedChunk(
                        content="Retention is about listening to customers.",
                        score=0.85,
                        source_path="test/transcript.md",
                        chunk_index=0,
                        metadata={
                            "title": "Building retention",
                            "guest": "Derek Sivers",
                            "publish_date": "2024-01-15",
                            "youtube_url": "https://youtube.com/watch?v=test",
                        },
                    )
                ]

        skill = Ship30Skill(MockRetrieval(), fake_llm)
        result = skill.generate(topic="How to improve retention")

        assert isinstance(result, SkillResult)
        assert len(result.content) > 100
        assert result.word_count > 0
        assert result.model == "fake-model"
        assert len(result.sources) == 1
        assert result.sources[0]["guest"] == "Derek Sivers"
        # Outline + article = 2 LLM calls.
        assert fake_llm._call_count == 2

    def test_generate_empty_topic_raises(self) -> None:
        fake_llm = FakeLLMProvider()

        class MockRetrieval:
            def search(self, query, top_k=10):
                return []

        skill = Ship30Skill(MockRetrieval(), fake_llm)
        with pytest.raises(ValueError, match="empty"):
            skill.generate(topic="  ")

    def test_format_context_empty(self) -> None:
        fake_llm = FakeLLMProvider()
        skill = Ship30Skill(None, fake_llm)
        assert "No relevant" in skill._format_context([])

    def test_build_sources_deduplicates(self) -> None:
        from app.knowledge.retrieval import RetrievedChunk

        fake_llm = FakeLLMProvider()
        skill = Ship30Skill(None, fake_llm)
        chunks = [
            RetrievedChunk(
                content="a", score=0.9, source_path="x/transcript.md",
                chunk_index=0, metadata={"title": "Same", "guest": "A"},
            ),
            RetrievedChunk(
                content="b", score=0.8, source_path="x/transcript.md",
                chunk_index=1, metadata={"title": "Same", "guest": "A"},
            ),
            RetrievedChunk(
                content="c", score=0.7, source_path="y/transcript.md",
                chunk_index=0, metadata={"title": "Different", "guest": "B"},
            ),
        ]
        sources = skill._build_sources(chunks)
        assert len(sources) == 2

    def test_result_to_dict(self) -> None:
        result = SkillResult(
            content="Test article",
            word_count=100,
            sources=[{"title": "Test"}],
            model="m",
            provider="p",
        )
        d = result.to_dict()
        assert d["word_count"] == 100
        assert len(d["sources"]) == 1


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def skills_client(
    migrated_database: str,
) -> Generator[TestClient, None, None]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(migrated_database)
    connection = engine.connect()
    transaction = connection.begin()
    for table in ("transcript_chunks", "messages", "chat_sessions", "users"):
        connection.execute(text(f"DELETE FROM {table}"))
    db_session = sessionmaker(
        bind=connection, autoflush=False, autocommit=False
    )()

    # Ingest fixtures.
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

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    def override_get_settings() -> Settings:
        return settings

    import app.api.skills as skills_mod
    import app.knowledge.embeddings as embeddings_mod
    import app.providers.factory as factory_mod

    old_emb = embeddings_mod.get_embedding_provider
    old_llm = factory_mod.get_llm_provider
    old_skills_llm = skills_mod.get_llm_provider
    embeddings_mod.get_embedding_provider = lambda s: FAKE_EMBED
    factory_mod.get_llm_provider = lambda s=None: FAKE_LLM
    skills_mod.get_llm_provider = lambda s=None: FAKE_LLM

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    with TestClient(app) as client:
        yield client

    factory_mod.get_llm_provider = old_llm
    skills_mod.get_llm_provider = old_skills_llm
    embeddings_mod.get_embedding_provider = old_emb
    app.dependency_overrides.clear()
    reset_session_state()
    reset_provider()
    db_session.close()
    transaction.rollback()
    connection.close()
    engine.dispose()


class TestShip30API:
    def test_generate_article(self, skills_client: TestClient) -> None:
        FAKE_LLM._call_count = 0
        response = skills_client.post(
            "/api/skills/ship30",
            json={"topic": "How to improve retention for startups"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert len(data["content"]) > 100
        assert data["word_count"] > 0
        assert isinstance(data["sources"], list)

    def test_empty_topic_returns_error(self, skills_client: TestClient) -> None:
        response = skills_client.post(
            "/api/skills/ship30",
            json={"topic": "ab"},
        )
        # min_length=3 in schema, so "ab" is too short.
        assert response.status_code == 422

    def test_generate_with_session_persists(
        self, skills_client: TestClient,
    ) -> None:
        # Create a session first.
        session_resp = skills_client.post(
            "/api/sessions", json={"title": "Article session"},
        )
        session_id = session_resp.json()["id"]

        FAKE_LLM._call_count = 0
        response = skills_client.post(
            "/api/skills/ship30",
            json={
                "topic": "Product-market fit strategies",
                "session_id": session_id,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

        # Verify article was persisted in the session.
        detail = skills_client.get(f"/api/sessions/{session_id}").json()
        assert detail["message_count"] >= 1
        msgs = detail["messages"]
        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["metadata"].get("skill") == "ship30"
