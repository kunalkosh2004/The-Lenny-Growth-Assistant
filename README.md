# The Lenny Growth Assistant

An evaluator-friendly full-stack AI product for asking grounded product and
growth questions over a local Lenny's Podcast transcript knowledge base.

Current state: Milestone 0 discovery and implementation planning is complete.
The application code will begin in Milestone 1 after approval.

## Planned Stack

- Backend: Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, pgvector
- Frontend: Next.js, React, TypeScript, Tailwind CSS
- AI: Ollama for local demo, OpenAI as the first cloud provider
- Retrieval: transcript chunk embeddings stored in PostgreSQL with pgvector
- Testing: pytest for backend, frontend lint/type checks and targeted UI tests
- Deployment: Docker Compose for PostgreSQL, backend, and frontend

## Planned Knowledge Source

The raw transcript source will live locally at:

```text
knowledge-source/lennys-podcast-transcripts/
```

Normal chat usage will not fetch from GitHub or load all transcripts into the
LLM context. Transcripts will be ingested once, or refreshed explicitly, into a
searchable PostgreSQL + pgvector knowledge base.

## Milestones

See [docs/implementation-plan.md](docs/implementation-plan.md) for the full
milestone plan, architecture proposal, assumptions, risks, and implementation
decisions.
