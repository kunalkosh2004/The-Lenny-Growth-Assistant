# Manual Test Plan

## Milestone 1

- Start the backend and confirm `GET /health` returns `{"status":"ok"}`.
- Start the frontend and confirm the app shell renders with sidebar, chat panel,
  provider status, composer, and artifact viewer.
- Validate Docker Compose parses successfully.

## Milestone 2

- Start PostgreSQL and run `uv run alembic upgrade head`.
- Confirm `GET /health/ready` reports database readiness as `ready`.
- Create a session with `POST /api/sessions`.
- Append user and assistant messages with `POST /api/sessions/{id}/messages`.
- Fetch session history with `GET /api/sessions/{id}` and confirm message order.
- Create a second session and confirm histories remain independent.

## Future Milestones

- Ask a grounded product question and inspect citations.
- Ask a follow-up question and verify prior context is used.
- Configure Ollama and verify provider status.
- Configure cloud provider credentials and verify graceful missing-key behavior.
- Generate a Ship 30 essay and check structure/source support.
- Generate Markdown and HTML/CSS artifacts.
- Confirm generated HTML scripts do not execute.
- Exercise database unavailable, provider unavailable, and empty-retrieval
  error states.
