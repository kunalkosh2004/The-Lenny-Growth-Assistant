# The Lenny Growth Assistant

An evaluator-friendly full-stack AI product for asking grounded product and
growth questions over a local Lenny's Podcast transcript knowledge base.

Current state: Milestone 1 foundation is in progress. The repository now has a
real FastAPI backend, a Next.js app shell, Docker foundations, and the core
planning docs. Retrieval, sessions, providers, and artifact generation arrive in
later milestones.

## Features

- Health and readiness API endpoints.
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

Milestone 1 provides Docker Compose with a pgvector-enabled PostgreSQL service.
Schema migrations begin in Milestone 2.

```bash
docker compose config
docker compose up postgres
```

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

- Milestone 1 has no session persistence, ingestion, retrieval, or generation.
- Readiness can report degraded until PostgreSQL is running.
- Frontend chat controls are a non-persistent foundation shell for now.

## Extension Ideas

- Hybrid retrieval with topic index metadata.
- Evaluation dataset for retrieval and grounded answer quality.
- Admin dashboard for ingestion status and transcript coverage.
- Export artifacts to Markdown, HTML, or Google Docs.
