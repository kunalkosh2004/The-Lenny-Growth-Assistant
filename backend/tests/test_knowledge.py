"""Tests for the knowledge base: parsing, chunking, ingestion, and retrieval."""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.knowledge.chunker import chunk_text, clean_text
from app.knowledge.ingest import IngestionService
from app.knowledge.parser import (
    TranscriptSourceError,
    _clean_metadata,
    _strip_frontmatter,
    discover_transcripts,
)
from app.knowledge.retrieval import RetrievalService

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "transcripts"

# ---------------------------------------------------------------------------
# Fake embedding provider for deterministic tests (no external service needed)
# ---------------------------------------------------------------------------


class FakeEmbeddingProvider:
    """Deterministic embeddings based on text hash for testing only."""

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


FAKE_PROVIDER = FakeEmbeddingProvider()

# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestStripFrontmatter:
    def test_parses_valid_frontmatter(self) -> None:
        raw = "---\nguest: Alice\ntitle: Foo\n---\n\nBody here."
        meta, body = _strip_frontmatter(raw)
        assert meta["guest"] == "Alice"
        assert meta["title"] == "Foo"
        assert body.strip() == "Body here."

    def test_no_frontmatter_returns_full_body(self) -> None:
        raw = "# Just a heading\n\nSome content."
        meta, body = _strip_frontmatter(raw)
        assert meta == {}
        assert body == raw

    def test_broken_frontmatter_returns_full_body(self) -> None:
        raw = "---\n  invalid yaml: [\n---\nBody"
        meta, body = _strip_frontmatter(raw)
        assert meta == {}
        assert "Body" in body

    def test_empty_metadata(self) -> None:
        raw = "---\n---\n\nBody"
        meta, body = _strip_frontmatter(raw)
        assert meta == {}
        assert body.strip() == "Body"


class TestCleanMetadata:
    def test_keeps_known_fields(self) -> None:
        raw = {
            "title": "Test",
            "guest": "Bob",
            "youtube_url": "https://youtube.com/watch?v=123",
            "publish_date": "2024-01-01",
            "keywords": ["growth", "retention"],
            "irrelevant_field": "should be dropped",
        }
        result = _clean_metadata(raw)
        assert result["title"] == "Test"
        assert result["guest"] == "Bob"
        assert result["youtube_url"] == "https://youtube.com/watch?v=123"
        assert "irrelevant_field" not in result
        assert result["keywords"] == ["growth", "retention"]

    def test_coerces_numeric_fields(self) -> None:
        result = _clean_metadata({
            "duration_seconds": "1234.5",
            "view_count": "5000",
        })
        assert result["duration_seconds"] == 1234
        assert result["view_count"] == 5000

    def test_drops_empty_values(self) -> None:
        result = _clean_metadata({"title": "", "guest": None})
        assert result == {}


class TestDiscoverTranscripts:
    def test_discovers_fixture_transcripts(self) -> None:
        transcripts = discover_transcripts(FIXTURES_DIR)
        assert len(transcripts) == 2
        titles = {t.metadata.get("title") for t in transcripts}
        assert "Building retention: lessons from CD Baby and beyond" in titles
        assert "Growth strategy for early-stage startups" in titles

    def test_hashes_are_correct(self) -> None:
        transcripts = discover_transcripts(FIXTURES_DIR)
        for t in transcripts:
            expected = hashlib.sha256(t.path.read_bytes()).hexdigest()
            assert t.file_hash == expected

    def test_missing_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(TranscriptSourceError, match="not found"):
            discover_transcripts(tmp_path / "nonexistent")

    def test_empty_directory_raises(self, tmp_path: Path) -> None:
        (tmp_path / "episodes").mkdir()
        with pytest.raises(TranscriptSourceError, match="No.*found"):
            discover_transcripts(tmp_path / "episodes")


# ---------------------------------------------------------------------------
# Chunker tests
# ---------------------------------------------------------------------------


class TestCleanText:
    def test_strips_timestamps(self) -> None:
        raw = "Lenny (00:01:23):\nHello world."
        result = clean_text(raw)
        assert "(00:01:23)" not in result
        assert "Hello world." in result

    def test_removes_markdown_headers(self) -> None:
        raw = "# Title\n## Subtitle\nActual content here."
        result = clean_text(raw)
        assert "# Title" not in result
        assert "Actual content" in result

    def test_collapses_multiple_newlines(self) -> None:
        raw = "a\n\n\n\n\nb"
        result = clean_text(raw)
        assert "\n\n\n" not in result


class TestChunkText:
    def test_short_text_single_chunk(self) -> None:
        chunks = chunk_text("Short text.", target_chars=1000)
        assert len(chunks) == 1
        assert "Short text." in chunks[0]

    def test_long_text_produces_multiple_chunks(self) -> None:
        paragraphs = [
            f"Paragraph {i}. {'x' * 200}" for i in range(20)
        ]
        body = "\n\n".join(paragraphs)
        chunks = chunk_text(body, target_chars=500, overlap_chars=50)
        assert len(chunks) > 1
        combined = "\n".join(chunks)
        assert "Paragraph 0" in combined
        assert "Paragraph 19" in combined

    def test_empty_body_returns_empty(self) -> None:
        assert chunk_text("") == []
        assert chunk_text("   ") == []


# ---------------------------------------------------------------------------
# Ingestion + Retrieval (database-backed)
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session_with_knowledge(
    migrated_database: str,
) -> Generator[Session, None, None]:
    """Yield a DB session with transcript_chunks also cleaned."""
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


def _ingest_settings(**overrides) -> Settings:
    defaults = dict(
        database_url="unused",
        transcripts_dir=str(FIXTURES_DIR),
        embedding_provider="fake",
        chunk_target_chars=400,
        chunk_overlap_chars=50,
        ingestion_batch_size=16,
        # The fake embedding provider produces hash-based vectors unrelated
        # to real semantic similarity, so the production relevance
        # threshold would flakily filter out matches in these tests.
        retrieval_min_score=0.0,
    )
    defaults.update(overrides)
    return Settings(**defaults)


class TestIngestion:
    def test_ingest_fixture_transcripts(self, db_session_with_knowledge: Session) -> None:
        settings = _ingest_settings()
        service = IngestionService(
            db_session_with_knowledge, settings,
            embedding_provider=FAKE_PROVIDER,
        )
        summary = service.run()
        assert summary.discovered == 2
        assert summary.failed == 0
        assert summary.chunks_created > 2
        assert summary.chunks_stored == summary.chunks_created

    def test_skips_unchanged_on_rerun(self, db_session_with_knowledge: Session) -> None:
        settings = _ingest_settings()
        service = IngestionService(
            db_session_with_knowledge, settings,
            embedding_provider=FAKE_PROVIDER,
        )
        service.run()
        second = service.run()
        assert second.skipped == 2
        assert second.chunks_created == 0

    def test_status_returns_counts(self, db_session_with_knowledge: Session) -> None:
        settings = _ingest_settings()
        service = IngestionService(
            db_session_with_knowledge, settings,
            embedding_provider=FAKE_PROVIDER,
        )
        service.run()
        status = service.status()
        assert status["episodes_indexed"] == 2
        assert status["chunks_indexed"] > 2
        assert status["episodes_discovered_on_disk"] == 2


class TestRetrieval:
    def test_search_returns_relevant_chunks(
        self, db_session_with_knowledge: Session,
    ) -> None:
        settings = _ingest_settings()
        IngestionService(
            db_session_with_knowledge, settings,
            embedding_provider=FAKE_PROVIDER,
        ).run()
        retrieval = RetrievalService(
            db_session_with_knowledge, settings,
            embedding_provider=FAKE_PROVIDER,
        )
        results = retrieval.search("retention and activation", top_k=3)
        assert len(results) > 0
        assert len(results) <= 3
        for r in results:
            assert r.content
            assert 0 <= r.score <= 1

    def test_search_metadata_preserved(
        self, db_session_with_knowledge: Session,
    ) -> None:
        settings = _ingest_settings()
        IngestionService(
            db_session_with_knowledge, settings,
            embedding_provider=FAKE_PROVIDER,
        ).run()
        retrieval = RetrievalService(
            db_session_with_knowledge, settings,
            embedding_provider=FAKE_PROVIDER,
        )
        results = retrieval.search("product market fit metrics", top_k=10)
        guests = {r.metadata.get("guest") for r in results}
        assert "Derek Sivers" in guests or "Sarah Chen" in guests

    def test_empty_query_returns_empty(
        self, db_session_with_knowledge: Session,
    ) -> None:
        settings = _ingest_settings()
        retrieval = RetrievalService(
            db_session_with_knowledge, settings,
            embedding_provider=FAKE_PROVIDER,
        )
        assert retrieval.search("") == []
        assert retrieval.search("   ") == []


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_with_knowledge_overrides(
    db_session_with_knowledge: Session,
) -> Generator[TestClient, None, None]:
    from app.core.config import get_settings
    from app.db.session import get_db, reset_session_state
    from app.main import app

    test_settings = Settings(
        database_url="unused",
        transcripts_dir=str(FIXTURES_DIR),
        embedding_provider="ollama",
        retrieval_min_score=0.0,
        app_env="test",
        log_level="WARNING",
    )

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session_with_knowledge
        finally:
            pass

    def override_get_settings() -> Settings:
        return test_settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    reset_session_state()


class TestKnowledgeAPI:
    def test_status_endpoint(
        self,
        db_session_with_knowledge: Session,
        client_with_knowledge_overrides: TestClient,
    ) -> None:
        response = client_with_knowledge_overrides.get("/api/knowledge/status")
        assert response.status_code == 200
        data = response.json()
        assert "episodes_indexed" in data
        assert "chunks_indexed" in data

    def test_search_endpoint(
        self,
        db_session_with_knowledge: Session,
        client_with_knowledge_overrides: TestClient,
    ) -> None:
        settings = _ingest_settings()
        IngestionService(
            db_session_with_knowledge, settings,
            embedding_provider=FAKE_PROVIDER,
        ).run()

        import app.knowledge.embeddings as embeddings_mod

        original_get_embedding = embeddings_mod.get_embedding_provider
        embeddings_mod.get_embedding_provider = lambda s: FAKE_PROVIDER
        try:
            response = client_with_knowledge_overrides.post(
                "/api/knowledge/search",
                json={"query": "retention loops", "top_k": 5},
            )
        finally:
            embeddings_mod.get_embedding_provider = original_get_embedding

        assert response.status_code == 200
        data = response.json()
        assert data["count"] > 0
        assert "source" in data["results"][0]

    def test_search_empty_query_returns_422(
        self,
        client_with_knowledge_overrides: TestClient,
    ) -> None:
        response = client_with_knowledge_overrides.post(
            "/api/knowledge/search", json={"query": ""}
        )
        assert response.status_code == 422
