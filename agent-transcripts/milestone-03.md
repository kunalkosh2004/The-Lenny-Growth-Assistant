# Milestone 03 Agent Transcript

## Goal

Build the complete transcript ingestion pipeline: validate, parse, chunk, embed,
and store Lenny's Podcast transcripts in PostgreSQL/pgvector for vector retrieval.

## Approach

1. Cloned `ChatPRD/lennys-podcast-transcripts` into `knowledge-source/` (2.6 MB,
   303 episodes).
2. Added `pgvector` extension and `TranscriptChunk` model with a migration.
3. Built `app/knowledge/` package: `parser.py` (frontmatter + discovery),
   `chunker.py` (clean + chunk), `embeddings.py` (Ollama/OpenAI abstraction),
   `ingest.py` (ingestion with content-hash refresh), `retrieval.py` (cosine
   similarity search).
4. Added operational scripts: `validate_transcripts.py`, `ingest_transcripts.py`
   (with `--limit` for testing), `refresh_knowledge_base.py`.
5. Added `/api/knowledge/status` and `/api/knowledge/search` endpoints.
6. Wrote 26 automated tests covering parser, chunker, ingestion, retrieval, and
   API with a deterministic `FakeEmbeddingProvider`.

## Problems Encountered

- **Alembic revision mismatch**: the migration referenced `001_initial_persistence_schema`
  but the actual revision was `001_initial_persistence`. Fixed by correcting the
  `down_revision` value.
- **Test isolation**: leftover "Live verification" session from manual testing
  caused a listing assertion to fail. Fixed by adding `DELETE FROM` cleanup for
  all relevant tables in the per-test fixture.
- **Embedding provider in API tests**: the `/api/knowledge/search` endpoint calls
  `get_embedding_provider(settings)` from the embeddings module, not the
  retrieval module. Fixed by monkeypatching `app.knowledge.embeddings.get_embedding_provider`
  in the test.
- **Ollama ingestion speed**: embedding 303 transcripts (15K+ chunks) via Ollama
  on CPU is slow (>10 min). Added per-episode commits and a `--limit` flag so
  progress is incremental and the pipeline can be verified on a subset.
- **CWD-relative paths**: scripts run from `backend/` but `.env` defaults point
  at project-root paths. Added `os.chdir(PROJECT_ROOT)` to all scripts.

## Verification

- `ruff check .` passes.
- 32/32 pytest tests pass (parser, chunker, ingestion, retrieval, API, sessions).
- Ingested 3 episodes (282 chunks) with real Ollama `nomic-embed-text` embeddings.
- Retrieval query "How should a startup improve retention?" returned 3 relevant
  chunks from Adam Fishman's episode with scores 0.69–0.71 and correct metadata.
- All source metadata (guest, title, source_path) preserved through the pipeline.

## Key Technical Decisions

- **Embedding dimension**: pgvector column is dimensionless for flexibility.
  Switching providers (e.g. OpenAI 1536-dim vs Ollama 768-dim) requires
  re-ingestion.
- **Content-hash refresh**: each episode's SHA-256 is stored. On rerun, unchanged
  episodes are skipped, changed episodes are re-chunked and re-embedded.
- **Per-episode commits**: each successfully ingested episode is committed
  immediately so partial progress is preserved if ingestion is interrupted.
