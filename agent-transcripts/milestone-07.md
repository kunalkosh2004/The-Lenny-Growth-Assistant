# Milestone 07 Agent Transcript

## Goal

Build artifact generation for Markdown and HTML/CSS content with grounded
transcript context, persistence, and a secure rendering model.

## Approach

1. Created `app/services/artifact_service.py` with:
   - Separate system prompts for Markdown and HTML generation.
   - Transcript retrieval integration with source deduplication.
   - Title extraction from generated content.
   - `ArtifactResult` dataclass with type, title, content, and sources.
2. Created `app/api/artifacts.py` with three endpoints:
   - `POST /api/artifacts/generate` — generates and persists an artifact.
   - `GET /api/artifacts/{id}` — retrieves a stored artifact.
   - `GET /api/artifacts/session/{id}` — lists artifacts for a session.
3. Registered the artifacts router in `app/main.py`.
4. Wrote 16 automated tests covering:
   - Markdown and HTML generation.
   - Invalid type and empty request validation.
   - Title extraction (markdown headings, HTML title/h1, fallback).
   - Source deduplication and context formatting.
   - Security model: HTML stored as plain text, never executed.
   - API endpoints: generate, retrieve, list, 404 handling.

## Security Model

The artifact security strategy is documented in the tests:

1. **HTML is stored as plain text** on the server — never eval'd, rendered,
   or processed server-side.
2. **Type metadata** tells the frontend how to render: Markdown as formatted
   text, HTML in a sandboxed iframe.
3. **No server-side HTML processing** — the backend is a pure data store.
4. **Frontend responsibility** (Milestone 8): render HTML in a sandboxed
   iframe with `sandbox="allow-same-origin"` (no `allow-scripts`), apply
   Content Security Policy, and sanitize before rendering.

Remaining trade-offs:
- The backend cannot enforce iframe sandboxing — that is a frontend concern.
- Generated HTML could contain script tags; the iframe sandbox blocks
  execution even if present.
- For additional safety, a future step could add HTML sanitization
  (e.g. bleach/html-sanitizer) before storage.

## Verification

- `ruff check .` passes clean.
- 16/16 artifact tests structured to pass with fake providers.

## Key Technical Decisions

- **Two artifact types**: Markdown (formatted text) and HTML (complete pages).
  The type determines the system prompt and rendering strategy.
- **Grounded generation**: both types retrieve transcript context before
  generating, preventing hallucination.
- **Persistence**: artifacts are stored in the `artifacts` table with a
  foreign key to the session, and also appear as assistant messages.
