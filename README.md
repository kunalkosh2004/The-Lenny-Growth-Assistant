# The Lenny Growth Assistant

An evaluator-friendly full-stack AI product for asking grounded product and
growth questions over a local Lenny's Podcast transcript knowledge base.

Users can ask complex product management questions, receive answers grounded
in transcript knowledge with source citations, generate Ship 30 for 30-style
essays, and create Markdown/HTML artifacts — all powered by Ollama locally
or a cloud LLM provider.

## Features

- **Grounded conversational AI** — answers sourced from 303 Lenny's Podcast
  transcripts with source citations (guest name, episode title, date).
- **Multiple chat sessions** — independent conversation contexts persisted
  in PostgreSQL.
- **Follow-up questions** — conversation history provides context for
  multi-turn grounded dialogue.
- **Ship 30 for 30 writing skill** — generates ~1,250-word essays with
  structured hooks, actionable insights, and source grounding.
- **Artifact generation** — Markdown documents and complete HTML/CSS pages
  generated from transcript knowledge.
- **Secure artifact viewer** — HTML rendered in a sandboxed iframe with
  scripts blocked.
- **LLM provider abstraction** — switch between Ollama (local) and OpenAI
  (cloud) without code changes via environment variable or API.
- **Vector search** — pgvector cosine similarity retrieval over chunked
  and embedded transcripts.
- **Structured logging** — request IDs for end-to-end tracing.
- **Health endpoints** — `/health` and `/health/ready` for monitoring.

## Architecture

```text
┌──────────────────────────────────────────────────────────┐
│                     Next.js Frontend                     │
│  ┌──────────┬──────────────────┬──────────────────────┐  │
│  │ Sidebar  │    Chat Panel    │   Artifact Viewer    │  │
│  │ Sessions │ Messages/Sources │  MD/HTML (sandboxed) │  │
│  └──────────┴──────────────────┴──────────────────────┘  │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTP
┌───────────────────────┴──────────────────────────────────┐
│                    FastAPI Backend                        │
│  ┌─────────┬──────────┬──────────┬──────────┬─────────┐  │
│  │ Sessions│  Chat    │Artifacts │ Skills   │Providers│  │
│  └────┬────┴────┬─────┴────┬─────┴────┬─────┴────┬────┘  │
│       │         │          │          │          │        │
│  ┌────┴─────────┴──────────┴──────────┴──────────┴────┐  │
│  │              ChatService / RetrievalService          │  │
│  └────────────────────────┬───────────────────────────┘  │
│                           │                              │
│  ┌────────────────────────┴───────────────────────────┐  │
│  │         LLM Provider Abstraction Layer              │  │
│  │    ┌──────────────┐        ┌──────────────┐        │  │
│  │    │OllamaProvider│        │OpenAIProvider│        │  │
│  │    └──────────────┘        └──────────────┘        │  │
│  └────────────────────────────────────────────────────┘  │
└───────────────────────┬──────────────────────────────────┘
                        │
┌───────────────────────┴──────────────────────────────────┐
│              PostgreSQL + pgvector                        │
│  ┌─────────────┬──────────────┬───────────────────────┐  │
│  │   Sessions  │  Artifacts   │  Transcript Chunks    │  │
│  │   Messages  │              │  (embeddings + meta)  │  │
│  └─────────────┴──────────────┴───────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

See [architecture.md](architecture.md) for detailed design decisions.

## Tech Stack

| Layer    | Technology                                             |
| -------- | ------------------------------------------------------ |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 3     |
| Backend  | Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic   |
| Database | PostgreSQL 16, pgvector                                |
| AI       | Ollama (local, mandatory), OpenAI, Anthropic, Google Gemini |
| Testing  | pytest (backend), TypeScript strict mode (frontend)    |
| Deploy   | Docker Compose                                         |

## Prerequisites

- Python 3.11+
- Node.js 22+
- Docker and Docker Compose
- Ollama (for local LLM demo)

## Getting Started (From Scratch)

Everything below has been run end-to-end and verified working, including a
clean `docker compose up --build` with no prior local setup.

### 0. Install Ollama first (needed by both paths below)

The demo is required to run locally on Ollama — do this before anything else:

```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Pull the models this project uses
ollama pull nomic-embed-text   # embeddings, required for ingestion + retrieval
ollama pull qwen2.5:3b         # generation — small, fast, works well on a laptop CPU
# llama3.1:8b also works (set as OLLAMA_MODEL) but is noticeably slower on CPU-only machines
```

### 1. Clone and configure

```bash
git clone https://github.com/kunalkosh2004/The-Lenny-Growth-Assistant.git
cd The-Lenny-Growth-Assistant
cp .env.example .env
```

`.env.example` ships with safe local defaults — nothing else is required to
run the local-Ollama demo. Cloud provider keys (`OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`) are optional; leave them blank to stay
fully local.

### 2. Get the transcript knowledge base

The app needs Lenny's Podcast transcripts on disk before it has anything to
ground answers in:

```bash
git clone --depth 1 https://github.com/ChatPRD/lennys-podcast-transcripts.git \
  knowledge-source/lennys-podcast-transcripts
```

### Option A — Docker Compose (recommended, one command)

```bash
docker compose up --build
```

This builds and starts PostgreSQL (with pgvector), the backend, and the
frontend together. Database migrations run automatically as part of the
backend container's startup — no separate migration step needed. Once it's
up:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000 (`/health`, `/health/ready`)

Then ingest transcripts from a separate terminal (this talks to the
dockerized Postgres over its published port, and to Ollama on the host —
neither needs to run inside a container):

```bash
cd backend
uv sync --all-groups
DATABASE_URL="postgresql+psycopg://lenny:lenny_dev_password@localhost:5432/lenny_growth_assistant" \
  uv run python ../scripts/ingest_transcripts.py --limit 15   # drop --limit for the full 303-episode set
```

### Option B — Native local dev (faster iteration while coding)

```bash
# Backend deps
cd backend
uv sync --all-groups

# Start Postgres only (still via Docker)
cd ..
docker compose up postgres -d

# Run migrations and ingest
cd backend
uv run alembic upgrade head
uv run python ../scripts/ingest_transcripts.py --limit 15

# Start the backend + frontend together
cd ..
./start.sh          # backend on :8001, checks Postgres/Ollama first
# in a second terminal:
cd frontend && npm install && npm run dev   # frontend on :3000
```

`start.sh` is the script actually used during development of this project —
it sources `.env`, verifies Postgres and Ollama are reachable before
starting, and prints which cloud providers have keys configured. Prefer it
over hand-rolling a raw `uvicorn` command; it avoids an env-loading footgun
(pydantic-settings looks for `.env` relative to the process's working
directory, not the repo root, so a bare `uv run uvicorn ...` from `backend/`
can silently miss root-level `.env` values unless `start.sh`'s explicit
`source .env` step runs first).

### 3. Verify it's working

```bash
curl http://localhost:8001/health/ready   # Option B; use :8000 for Option A
```

Then open the frontend, start a new chat, and ask something like *"How
should startups improve retention?"* — you should get a grounded answer with
source citations, and the sidebar should show Ollama as connected.

## API Endpoints

| Method   | Path                             | Description                    |
| -------- | -------------------------------- | ------------------------------ |
| GET      | `/health`                        | Application health             |
| GET      | `/health/ready`                  | Readiness (DB check)           |
| POST     | `/api/sessions`                  | Create a new chat session      |
| GET      | `/api/sessions`                  | List all sessions              |
| GET      | `/api/sessions/{id}`             | Get session with messages      |
| POST     | `/api/sessions/{id}/messages`    | Add a message to a session     |
| POST     | `/api/chat`                      | Send a grounded chat message   |
| GET      | `/api/providers`                 | List LLM providers             |
| POST     | `/api/providers/select`          | Switch active provider         |
| GET      | `/api/knowledge/status`          | Knowledge base statistics      |
| POST     | `/api/knowledge/search`          | Search transcript chunks       |
| POST     | `/api/artifacts/generate`        | Generate a Markdown/HTML artifact |
| GET      | `/api/artifacts/{id}`            | Retrieve a stored artifact     |
| POST     | `/api/skills/ship30`             | Generate a Ship 30 essay       |

## Running Tests

```bash
# Backend
cd backend
TEST_DATABASE_URL="postgresql+psycopg://lenny:lenny_dev_password@localhost:5432/lenny_growth_assistant" \
  uv run pytest -v

# Frontend
cd frontend
npx tsc --noEmit
```

## Troubleshooting

| Issue                        | Solution                                                    |
| ---------------------------- | ----------------------------------------------------------- |
| Database unavailable         | Confirm PostgreSQL is running; check `DATABASE_URL`         |
| Port 5432 already in use     | Start with `POSTGRES_PORT=5434` and update `DATABASE_URL`  |
| Ollama unavailable           | Ensure Ollama is running and models are installed           |
| Model not found              | Run `ollama pull <model-name>`                              |
| Missing cloud key            | Set `OPENAI_API_KEY` or use `LLM_PROVIDER=ollama`          |
| Transcript directory missing | Clone transcript repo into `knowledge-source/`              |
| Ingestion too slow           | Use `--limit N` for faster testing                          |
| Frontend can't reach backend | Check `NEXT_PUBLIC_API_BASE_URL` matches backend port       |

## Project Structure

```text
lenny-growth-assistant/
├── backend/                    FastAPI application
│   ├── app/
│   │   ├── api/                Route handlers (chat, sessions, artifacts, etc.)
│   │   ├── core/               Config, logging
│   │   ├── db/                 Database session management
│   │   ├── knowledge/          Retrieval, ingestion, embeddings, chunking
│   │   ├── models/             SQLAlchemy models
│   │   ├── providers/          LLM provider abstraction (Ollama, OpenAI)
│   │   ├── schemas/            Pydantic request/response schemas
│   │   ├── services/           Business logic (chat, session, artifact)
│   │   └── skills/             Reusable AI skills (Ship 30)
│   ├── alembic/                Database migrations
│   └── tests/                  Automated tests
├── frontend/                   Next.js application
│   └── src/
│       ├── app/                Pages and layouts
│       ├── components/         React components
│       ├── lib/                API client, config
│       └── types/              TypeScript types
├── knowledge-source/           Local transcript repository
├── scripts/                    Operational scripts (ingest, validate)
├── docs/                       Documentation
├── agent-transcripts/          Development logs
├── docker-compose.yml
├── .env.example
└── README.md
```

## Documentation

- [PRD.md](PRD.md) — Product Requirements Document
- [design.md](design.md) — UI/UX Design Document
- [architecture.md](architecture.md) — Architecture Document
- [docs/manual-test-plan.md](docs/manual-test-plan.md) — 17 Manual Tests
- [docs/implementation-plan.md](docs/implementation-plan.md) — Implementation Plan

## Known Limitations

- Full ingestion of 303 transcripts takes ~10+ minutes on Ollama CPU.
  Use `--limit N` for faster development verification.
- pgvector column is dimensionless: switching embedding providers requires
  re-ingestion of all transcripts.
- Generated HTML artifacts may contain script tags, but these are blocked
  by the sandboxed iframe.
- No user authentication (internal tool scope).
- No real-time streaming of LLM responses (added in a future milestone).

## Extension Ideas

- Streaming LLM responses for real-time output.
- Hybrid retrieval with keyword search alongside vector search.
- Evaluation dataset for retrieval quality.
- Admin dashboard for ingestion status and transcript coverage.
- Export artifacts to PDF or Google Docs.
- User authentication and team workspaces.
