# The Lenny Growth Assistant

An evaluator-friendly full-stack AI product for asking grounded product and
growth questions over a local Lenny's Podcast transcript knowledge base.

Current state: Milestone 2 persistence is complete. The repository has a
real FastAPI backend with health and session APIs, Alembic migrations,
PostgreSQL models for sessions/messages/artifacts, a Next.js app shell,
Docker foundations, and the core planning docs. Transcript ingestion,
retrieval, providers, and artifact generation arrive in later milestones.

## Features

- Health and readiness API endpoints.
- Session and message persistence APIs.
- PostgreSQL models for users, chat sessions, messages, and artifacts.
- Alembic migrations for schema management.
- Three-panel product shell: session sidebar, chat workspace, artifact viewer.
- PostgreSQL + pgvector Docker foundation.
- Environment-driven configuration.
- Documentation for product, design, architecture, and manual testing.

Planned features:

- Transcript ingestion from `knowledge-source/lennys-podcast-transcripts`.
- Grounded RAG answers with citations.
- Multiple persisted chat sessions.
- Ollama and cloud LLM provider abstraction.
- Ship 30 for 30 essay skill.
- Markdown and sandboxed HTML/CSS artifact rendering.

## Architecture Overview

```text
Next.js frontend
      |
      v
FastAPI backend
      |
      +--> PostgreSQL session/artifact persistence
      +--> PostgreSQL + pgvector transcript retrieval
      +--> Ollama / OpenAI provider abstraction
```

See [architecture.md](architecture.md) for details.

## Tech Stack

- Backend: Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, pgvector
- Frontend: Next.js, React, TypeScript, Tailwind CSS
- AI: Ollama for local demo, OpenAI as the first cloud provider
- Testing: pytest for backend, frontend lint/type checks
- Deployment: Docker Compose

## Prerequisites

- Python 3.11+
- Node.js 22+
- Docker and Docker Compose
- Ollama for local model execution

## Installation

```bash
cp .env.example .env
```

Backend:

```bash
cd backend
uv sync --all-groups
uv run uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Environment Setup

Start from `.env.example`. Do not commit `.env` or API keys.

Important variables:

- `DATABASE_URL`: PostgreSQL connection string.
- `TRANSCRIPTS_DIR`: local transcript episodes directory.
- `LLM_PROVIDER`: `ollama` by default.
- `OLLAMA_BASE_URL`: local Ollama server URL.
- `OLLAMA_MODEL`: default local model candidate.
- `OPENAI_API_KEY`: optional cloud provider key.

## Database Setup

Milestone 2 adds Alembic migrations and PostgreSQL models for sessions,
messages, and artifacts.

```bash
docker compose up postgres -d
cd backend
uv run alembic upgrade head
```

If port `5432` is already in use locally, set an alternate host port before
starting PostgreSQL:

```bash
POSTGRES_PORT=5434 docker compose up postgres -d
```

Then point `DATABASE_URL` at that port for migrations and local API runs.

## Ollama Setup

Install Ollama locally and pull the configured model:

```bash
ollama pull llama3.1:8b
```

The app will treat Ollama availability as a provider health concern in
Milestone 4.

## Cloud Provider Setup

OpenAI is the planned first cloud provider. Set `OPENAI_API_KEY` in `.env` when
using cloud generation. Missing credentials will be handled gracefully.

## Transcript Ingestion

Place the transcript repository at:

```text
knowledge-source/lennys-podcast-transcripts/
```

The ingestion pipeline will read:

```text
knowledge-source/lennys-podcast-transcripts/episodes/**/transcript.md
```

Normal chat usage will query PostgreSQL + pgvector, not the raw transcript files.

## Running Locally

Backend health:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

Session API examples:

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{"title":"Retention strategy"}'

curl http://localhost:8000/api/sessions

curl -X POST http://localhost:8000/api/sessions/<session-id>/messages \
  -H 'Content-Type: application/json' \
  -d '{"role":"user","content":"How do guests describe PMF?"}'

curl http://localhost:8000/api/sessions/<session-id>
```

Frontend:

```bash
open http://localhost:3000
```

## Docker Instructions

After creating `.env`:

```bash
docker compose up --build
```

Milestone 1 also supports:

```bash
docker compose config
```

to validate the Compose file shape.

## Running Tests

Backend:

```bash
cd backend
uv run pytest
```

Frontend:

```bash
cd frontend
npm run typecheck
npm run build
```

## Troubleshooting

- **Database unavailable:** confirm PostgreSQL is running and `DATABASE_URL` is
  correct.
- **Port 5432 already in use:** start Compose with `POSTGRES_PORT=5434` (or
  another free port) and update `DATABASE_URL` accordingly.
- **Ollama unavailable:** confirm Ollama is installed, running, and has the
  configured model.
- **Missing cloud key:** set `OPENAI_API_KEY` or use `LLM_PROVIDER=ollama`.
- **Transcript directory missing:** clone or place the transcript repository
  under `knowledge-source/lennys-podcast-transcripts/`.

## Project Structure

```text
backend/              FastAPI app
frontend/             Next.js app
scripts/              Operational scripts
docs/                 Manual test and implementation docs
knowledge-source/     Local raw transcript repository location
agent-transcripts/    Milestone development logs
```

## Documentation

- [PRD.md](PRD.md)
- [design.md](design.md)
- [architecture.md](architecture.md)
- [docs/implementation-plan.md](docs/implementation-plan.md)
- [docs/manual-test-plan.md](docs/manual-test-plan.md)

## Known Limitations

- Milestone 2 persists sessions and messages, but chat is not yet grounded in
  transcript retrieval.
- Readiness can report degraded until PostgreSQL is running.
- Frontend chat controls are a non-persistent foundation shell for now.

## Extension Ideas

- Hybrid retrieval with topic index metadata.
- Evaluation dataset for retrieval and grounded answer quality.
- Admin dashboard for ingestion status and transcript coverage.
- Export artifacts to Markdown, HTML, or Google Docs.
