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
| AI       | Ollama (local), OpenAI (cloud)                         |
| Testing  | pytest (backend), TypeScript strict mode (frontend)    |
| Deploy   | Docker Compose                                         |

## Prerequisites

- Python 3.11+
- Node.js 22+
- Docker and Docker Compose
- Ollama (for local LLM demo)

## Quick Start

```bash
# 1. Clone the repository
git clone <repository-url>
cd lenny-growth-assistant

# 2. Copy environment file
cp .env.example .env

# 3. Start PostgreSQL
docker compose up postgres -d

# 4. Install backend dependencies
cd backend
uv sync --all-groups

# 5. Run database migrations
uv run alembic upgrade head

# 6. Start the backend
uv run uvicorn app.main:app --reload

# 7. In a separate terminal, install and start the frontend
cd frontend
npm install
npm run dev
```

## Transcript Setup

The knowledge base requires Lenny's Podcast transcripts:

```bash
# Clone the transcript repository
git clone --depth 1 https://github.com/ChatPRD/lennys-podcast-transcripts.git \
  knowledge-source/lennys-podcast-transcripts

# Validate transcript source
./backend/.venv/bin/python scripts/validate_transcripts.py

# Ingest transcripts into the knowledge base (requires Ollama)
DATABASE_URL="postgresql+psycopg://lenny:lenny_dev_password@localhost:5432/lenny_growth_assistant" \
  EMBEDDING_PROVIDER=ollama \
  ./backend/.venv/bin/python scripts/ingest_transcripts.py

# For faster verification, ingest a subset
./backend/.venv/bin/python scripts/ingest_transcripts.py --limit 10
```

## Ollama Setup

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull nomic-embed-text    # Embeddings (768 dims)
ollama pull llama3.1:8b         # Generation (recommended)
# or
ollama pull qwen2.5-coder:1.5b  # Smaller/faster alternative
```

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

## Docker Compose

```bash
# Start all services
docker compose up --build

# Start only PostgreSQL
docker compose up postgres -d
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
