# Manual Test Plan

This document describes manual tests for verifying The Lenny Growth Assistant
works correctly end-to-end. Each test includes steps, expected results, and
acceptance criteria.

## Prerequisites

1. `docker compose up postgres -d` (or local PostgreSQL on port 5434).
2. `cd backend && uv run alembic upgrade head`.
3. `uv run uvicorn app.main:app --reload`.
4. Ollama running with `nomic-embed-text` (embeddings) and `llama3.1:8b` or
   `qwen2.5-coder:1.5b` (generation) installed.
5. Transcript ingestion completed: `uv run python ../scripts/ingest_transcripts.py`.
6. Frontend running: `cd frontend && npm run dev`.

## Test 1: Health and Readiness

**Steps:**
1. `curl http://localhost:8000/health`
2. `curl http://localhost:8000/health/ready`

**Expected:**
- Health returns `{"status": "ok", "app_env": "development"}`.
- Readiness returns `{"status": "ready"}` with database check passing.

## Test 2: New Chat Session

**Steps:**
1. Open `http://localhost:3000`.
2. Click the "+" button in the sidebar to create a new chat.
3. Verify the sidebar shows the new chat.

**Expected:**
- A new chat session appears in the sidebar.
- The chat area shows an empty state with suggested questions.
- The welcome message is displayed.

## Test 3: Send a Grounded Question

**Steps:**
1. Create a new chat session.
2. Type "How should an early-stage startup improve retention?".
3. Press Enter or click Send.

**Expected:**
- The user message appears on the right.
- A loading indicator shows while the assistant responds.
- The assistant responds with a grounded answer referencing specific guests.
- Source citations appear below the response as clickable tags.
- Each source shows guest name, episode title, and date.
- The model/provider info appears below the response.

## Test 4: Follow-Up Questions

**Steps:**
1. Send the retention question from Test 3.
2. After the response, send "Can you give me a specific example?".

**Expected:**
- The assistant uses both the conversation history and new retrieval.
- The response references a specific guest or episode from the transcripts.
- Previous messages are visible in the chat.

## Test 5: Empty Retrieval Handling

**Steps:**
1. Send a question about a topic unlikely to be in transcripts:
   "What is the capital of France?"

**Expected:**
- The assistant responds that it doesn't have enough information in the
  available transcripts.
- No hallucinated content is presented as fact.
- No source citations are shown (or a "no relevant sources" warning appears).

## Test 6: Session Switching

**Steps:**
1. Create two chat sessions (Chat A and Chat B).
2. Send a message in Chat A.
3. Switch to Chat B from the sidebar.
4. Verify Chat B has no messages from Chat A.
5. Switch back to Chat A.

**Expected:**
- Each session maintains independent conversation context.
- Session titles update in the sidebar.
- Message history is preserved per session.

## Test 7: Provider Status Display

**Steps:**
1. Look at the sidebar provider status panel.
2. Verify the current provider and model are displayed.
3. Verify the connection status indicator (green/red dot).

**Expected:**
- The active provider (Ollama/OpenAI) is displayed.
- The model name is shown.
- Green dot if connected, red if disconnected.

## Test 8: Ship 30 Essay Generation

**Steps:**
1. Click the "Artifacts" button in the chat header.
2. Select "Markdown" as the artifact type.
3. Enter a topic: "How to build a high-performing growth team".
4. Click "Generate".

**Expected:**
- A loading indicator shows during generation.
- The artifact viewer opens with a rendered Markdown article.
- The article is approximately 1,000-1,500 words.
- The article has headings, bold text, bullet points.
- Source citations are included.
- The article is grounded in transcript content (not fabricated).

## Test 9: HTML/CSS Artifact Generation

**Steps:**
1. Click "Artifacts" button.
2. Select "HTML/CSS" as the artifact type.
3. Enter: "Create a landing page explaining retention frameworks".
4. Click "Generate".

**Expected:**
- The artifact viewer shows a preview label "HTML/CSS Preview (sandboxed)".
- The page renders with proper styling (fonts, colors, spacing).
- No JavaScript executes (check browser console for script errors).
- The page is responsive and readable.

## Test 10: Artifact Security

**Steps:**
1. Generate an HTML artifact.
2. Inspect the iframe element in browser DevTools.
3. Verify the `sandbox` attribute is present.

**Expected:**
- The iframe has `sandbox="allow-same-origin"` (no `allow-scripts`).
- Generated `<script>` tags do not execute.
- No `allow-forms`, `allow-popups`, or other dangerous capabilities.

## Test 11: Error States

**Steps:**
1. Stop the Ollama service.
2. Send a chat message.

**Expected:**
- An error message appears in the chat explaining the issue.
- The UI remains functional (no crash, no blank screen).
- The user can retry after restarting Ollama.

## Test 12: Request IDs in Logs

**Steps:**
1. Send a chat message.
2. Check the backend terminal output.

**Expected:**
- Each request has a `[request_id]` in the log output.
- The request ID is consistent across related log lines.
- The `X-Request-ID` header is present in API responses.

## Test 13: Docker Compose Startup

**Steps:**
1. `docker compose down -v`
2. `cp .env.example .env`
3. `docker compose up --build`

**Expected:**
- All services start (postgres, backend, frontend).
- Backend health endpoint returns OK.
- Frontend loads in browser.
- Database migrations run automatically.

## Test 14: Transcript Ingestion Verification

**Steps:**
1. `./backend/.venv/bin/python scripts/validate_transcripts.py`
2. Check the output for transcript count and metadata.

**Expected:**
- 303 transcripts discovered.
- 1 episode with missing title/guest is reported.
- Transcript size statistics are shown.

## Test 15: Provider Switching

**Steps:**
1. `curl -X POST http://localhost:8000/api/providers/select -H 'Content-Type: application/json' -d '{"provider": "ollama"}'`
2. `curl -X POST http://localhost:8000/api/providers/select -H 'Content-Type: application/json' -d '{"provider": "openai"}'`

**Expected:**
- First call returns success with ollama active.
- Second call returns 400 if OpenAI key is not configured.
- Provider switch takes effect immediately without restart.

## Test 16: Knowledge Base Status

**Steps:**
1. `curl http://localhost:8000/api/knowledge/status`

**Expected:**
- Returns episode count, chunk count, embedding model info.
- Shows episodes discovered on disk vs. indexed.

## Test 17: Multiple Artifact Retrieval

**Steps:**
1. Generate 2 artifacts in the same session.
2. `curl http://localhost:8000/api/artifacts/session/{session_id}`

**Expected:**
- Both artifacts are listed with titles, types, and timestamps.
- Artifacts are ordered by creation time (newest first).
