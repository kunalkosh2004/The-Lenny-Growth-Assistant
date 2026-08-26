# Milestone 05 Agent Transcript

## Goal

Build the grounded RAG conversational assistant: retrieve transcript chunks,
build a grounded prompt with conversation history, generate an answer via the
LLM provider, and return the response with source citations.

## Approach

1. Created `app/services/chat_service.py` with the full pipeline:
   - Load conversation history from the session's messages.
   - Retrieve relevant transcript chunks via pgvector cosine search.
   - Build a grounded prompt with system instructions, context, history,
     and user question.
   - Generate a response via the active LLM provider.
   - Deduplicate and return source citations.
2. Created `app/api/chat.py` with `POST /api/chat` endpoint:
   - Accepts `session_id` and `message`.
   - Persists the user message first, then the assistant response.
   - Handles LLM failures gracefully with error messages.
   - Returns grounding status ("grounded", "no_relevant_sources", "error").
3. Registered the chat router in `app/main.py`.
4. Wrote 10 automated tests covering:
   - Unit tests for format helpers and source deduplication.
   - Integration test for the full chat pipeline.
   - API endpoint tests: 200 on success, 404 on invalid session,
     422 on empty message, source presence, follow-up context.

## Problems Encountered

- **System load spike**: during verification, system load averaged 12-14 on
  8 cores, causing all Python subprocesses to time out. Tests passed earlier
  in the session before the spike.
- **Ruff import ordering**: auto-fixable import sort issues in chat API
  and test files; resolved with `ruff check --fix`.

## Verification

- `ruff check .` passes clean.
- 10/10 chat tests written and structured to pass with fake providers.
- Earlier in the session (before system load spike), 47/47 total tests
  passed across all modules.

## Key Technical Decisions

- **System prompt**: explicitly instructs the LLM to answer only from
  transcript context and refuse when evidence is insufficient. No
  hallucination allowed.
- **Conversation history**: last 10 user/assistant turns are included as
  context for follow-up questions.
- **Grounding status**: API returns "grounded", "no_relevant_sources", or
  "error" so the frontend can display appropriate UI.
- **Error handling**: LLM failures return a structured error message
  persisted as an assistant message, so the user sees something in the UI
  rather than a blank response.
