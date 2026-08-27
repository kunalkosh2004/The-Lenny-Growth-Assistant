# Milestone 12 Agent Transcript (Claude, live session — 2026-08-27)

## Goal

Resume an already-mature, feature-complete project (built through Milestone 11
by Codebuff) as a live Claude session: fix real bugs found through actual
usage, close remaining gaps against the assignment (Ship 30 UI, session
deletion), verify the deployment path end-to-end, and honestly document
architecture decisions the assignment expects to see justified — all with a
real, unedited record of what broke and how it was actually fixed, including
the times a first fix wasn't good enough.

## Approach and Problems Encountered

This session was almost entirely reactive debugging driven by actually using
the running product, not upfront design. Each item below is a real
problem → fix → verification cycle, in the order encountered.

### 1. `start.sh` reload storm

Running the backend via `uv run uvicorn --reload` looked hung on first start.
Root cause: `--reload` was watching the entire `backend/` directory including
`.venv`, so `uv`'s first-run dependency install touched hundreds of `.venv`
files and triggered one long reload cycle. Fixed with
`--reload-exclude ".venv/*"`. Verified: clean single-cycle startup on rerun.

### 2. A real regression caught before it shipped

While preparing to push, `git status` showed unstaged changes to
`backend/pyproject.toml`, `backend/app/main.py`, and
`backend/app/models/__init__.py` that I hadn't made. Investigated instead of
assuming they were fine:

- `pyproject.toml` had moved `httpx` into the `dev` dependency group and
  dropped `pgvector`/`pyyaml` entirely — but `httpx` is imported directly by
  all four LLM providers and the embeddings module, and the `Dockerfile` runs
  `pip install --no-cache-dir .`, which does **not** install the `dev` group.
  A fresh Docker build would have installed with `httpx`/`pgvector`/`pyyaml`
  all missing, crashing every provider call and the entire knowledge pipeline
  at import time.
- `app/main.py` had stopped registering `RequestIDMiddleware`, silently
  disabling the request-ID observability the assignment explicitly asks for.
- `README.md` and `docs/manual-test-plan.md` had also been reverted to an
  early "Milestone 2" draft, discarding all the finished-feature
  documentation.

Reverted all of it with `git checkout -- <files>`, then proved the revert was
correct rather than just assuming: ran `docker compose build backend` end to
end (succeeded, all three deps installed correctly) and the full backend test
suite (84/84 passing at the time) before pushing anything.

### 3. Test fixtures with real bugs, found by actually running them with a DB

`backend/tests/conftest.py`'s default `TEST_DATABASE_URL` pointed at port
5432, but the project's actual dev Postgres runs on 5434 — so 39 persistence
tests were silently skipping via "PostgreSQL is not available" every run.
Pointing it at 5434 surfaced three previously-hidden bugs:

- `test_chat.py`, `test_artifacts.py`, `test_skills.py` each had
  `chat_client._session_id = ...` — setting the attribute on the **fixture
  function object**, not the yielded `TestClient`. Fixed by setting it on the
  actual client instance inside the `with TestClient(app) as client:` block.
- The same three files patched `app.providers.factory.get_llm_provider` to
  inject a fake LLM, but `app/api/skills.py`, `app/api/artifacts.py`, and
  `app/services/chat_service.py` each do
  `from app.providers.factory import get_llm_provider` at module scope —
  patching the factory module's attribute never reached those already-bound
  names. Fixed by patching each consuming module's own bound name instead.
- `test_generate_html` asserted the wrong title-extraction precedence (`<h1>`
  over `<title>`) when the implementation's own docstring says `<title>`
  wins — the mock's `<title>` and `<h1>` values intentionally differed, so
  this was a test bug, not an implementation bug. Fixed the assertion.
- `test_multiple_sessions_remain_independent` failed once real Postgres was
  used, because a genuine leftover "Live verification" row from earlier
  manual testing was sitting in the shared dev database. Confirmed the
  per-test transaction-rollback isolation was actually working (0 rows after
  a full suite run) before concluding it was stale data, not a fixture bug,
  and cleaned it up rather than papering over it.

Verification: went from 44 passed / 1 failed / 39 skipped to 84/84 passing.

### 4. Artifact viewer showing raw ` ```html ` text

Reported directly by the user with a screenshot. The LLM had wrapped its HTML
output in a fence, and my first fix (`_strip_code_fence`) used an *anchored*
regex requiring the whole response to be nothing but the fence — it broke on
the very next case, where the model added lead-in/trailing prose around the
fence ("Here is the requested..." / "This HTML document includes..."). Fixed
properly: search for a fenced block anywhere in the text (not anchored), and
for HTML specifically, extract the `<!DOCTYPE html>...</html>` document
directly via regex — discarding any prose whether or not it was fenced.
Applied both server-side (`artifact_service.py`, so new artifacts are clean at
the source) and client-side (`ArtifactViewer.tsx`, so artifacts already
generated before the fix still render). Verified against the user's exact
reported case before and after.

### 5. Gemini silently truncating a full HTML artifact

A regenerated artifact still failed — this time cut off mid-CSS with no
closing tags at all (1253 raw chars, no `</html>`, no closing fence). Traced
it to the actual response, not guessed: fetched the stored artifact's raw
content and confirmed the cutoff point. Root cause: Gemini 2.5 models spend
part of the shared token budget on internal "thinking" before producing
visible output, so a complex generation task silently ran out of budget well
before the visible completion looked anywhere near the `max_tokens` limit
from the outside. Fixed by setting `thinkingConfig: {"thinkingBudget": 0}` in
the Gemini payload (this app's use cases don't need extended reasoning) and
added a guard that raises a clear error if Gemini ever returns
`finishReason: MAX_TOKENS` with zero visible content. Verified: regenerated
the same artifact, got a complete 6960-char document starting with
`<!DOCTYPE html>` and ending with a proper `</html>`.

### 6. RAG hallucination — three iterations, not one

The user reported that asking "What is the capital of France?" sometimes got
a real (fabricated) answer instead of a refusal, even though the system
prompt explicitly instructs the LLM to refuse when context doesn't support an
answer — a small local model (`qwen2.5:3b`) just didn't reliably follow it.

- **First fix:** added a minimum cosine-similarity threshold
  (`retrieval_min_score`, calibrated against real measured scores: on-topic
  queries scored ~0.65-0.71, off-topic ones ~0.37-0.45) and made `chat()`
  short-circuit to a deterministic refusal when no chunks cleared the bar and
  there was no history at all. This broke immediately on retest: the chat API
  persists the user's message *before* calling `chat()`, so `history` always
  contains at least the current turn — the "no history" condition was
  effectively dead code, and the France question still went to the LLM every
  time.
- **Second fix:** changed the check to require a prior *grounded* assistant
  turn (one with real sources), not just any history. This fixed the retry
  case but the user found a new failure: asking a grounded question, a
  follow-up, then France *once* still got a hallucinated answer, because the
  turn immediately before it (the follow-up) was itself grounded — "any prior
  grounded turn unlocks the LLM forever afterward in that session" was still
  too permissive.
- **Third fix (the one that actually held up):** measured real embedding
  scores instead of continuing to guess: "what is the capital of France?"
  scores ~0.38 on its own regardless of conversation state, while short
  follow-ups ("elaborate on that", "give a specific example", even "ok
  thanks") reliably score ~0.5-0.6, because vague phrasing turns out to be
  *less* semantically distinctive, not less relevant. Dropped the
  history-based heuristic entirely — the check is now purely "did this
  message's own retrieval find anything," which is simpler and held up
  against the exact reported repro sequence (grounded question → follow-up →
  France question, asked once) on live retest.

### 7. Ship 30 essay reliably timing out on local Ollama

Wiring up a UI entry point for the (already-implemented, already-tested)
Ship 30 endpoint surfaced a real bug: it reliably timed out at exactly 60
seconds on Ollama, across three separate live runs, timeout message and all.
Traced to `backend/app/providers/factory.py`:
`getattr(settings, "ollama_timeout_seconds", 60.0)` — the `Settings` class
never actually declared `ollama_timeout_seconds` as a field, so
`OLLAMA_TIMEOUT_SECONDS=60` in `.env` had been a complete no-op the whole
time; `getattr` always fell through to the hardcoded 60s default regardless
of what was configured. Declared the field properly (180s default, since a
two-pass ~1,250-word generation on a small local CPU model needs real
headroom), removed the dead fallback, and separately learned that reloading
via `--reload` doesn't re-source `start.sh`'s exported env vars — had to fully
restart the process for the fix to actually take effect. Verified: a complete
successful generation (734 words, 3 sources, correctly persisted).

### 8. Session deletion not implemented at all

Wiring up a delete button in the sidebar revealed the frontend's `api.ts`
already had a `deleteSession()` client function calling
`DELETE /api/sessions/{id}` — but the backend never implemented that route at
all; it would have 404'd. Implemented `DELETE /api/sessions/{id}` and
`SessionService.delete_session`, relying on the ORM cascade
(`cascade="all, delete-orphan"` on `ChatSession.messages`/`.artifacts`, which
was already correctly configured) and verified the cascade against real
Postgres, not just the ORM layer.

### 9. Deletion working on the backend but not reflecting in the UI

After implementing delete, the user reported having to refresh the page to
see a deleted chat disappear. The shared `request()` helper in `api.ts`
unconditionally called `res.json()` on every successful response, but
`DELETE` returns `204 No Content` with an empty body — parsing that as JSON
throws, and the exception was silently swallowed by the caller's
`try/catch`, so `setSessions(...)` never ran even though the backend really
had deleted it. Confirmed the exact failure with a raw `fetch()` call against
the running backend (`json() threw as expected: Unexpected end of JSON
input`) before fixing it, rather than guessing. Fixed by skipping
`res.json()` for 204 responses.

### 10. Claude Agent SDK requirement — investigated, not assumed

The assignment names the Anthropic Claude Agent SDK as the expected way to
build the agent layer. Rather than skip it or force-fit it, installed the
actual `claude-agent-sdk` pip package into a scratch venv and read its
transport source directly: it spawns the `claude` CLI as a subprocess (no
bundled binary ships with the pip package — confirmed by `find`-ing the
package for a `_bundled` directory and finding none), and only talks to
Anthropic's own models. Both facts conflict with this project's mandatory
local-Ollama demo requirement. Documented the investigation and the resulting
trade-off explicitly in `PRD.md` and `architecture.md`, including why the
existing custom skill/router architecture (`ChatService`, `Ship30Skill`,
`ArtifactService`) was kept instead — this is a documented, evidence-backed
engineering decision, not an omission.

### 11. Docker Compose end-to-end, actually run for the first time

Ran `docker compose up --build` for real (not just a backend image build) for
the first time this session. Both images built cleanly. The only failure was
port 8000 being held by an unrelated project's container already running on
this machine (`clipforge-api-1`) — not a project bug. Verified with a
temporary `API_PORT` override rather than touching that other container:
health, readiness (DB check), frontend serving, and session creation all
confirmed working through the fully dockerized stack, and confirmed that
Alembic migrations run automatically via the backend `Dockerfile`'s `CMD`
(`alembic upgrade head && uvicorn ...`), so a fresh evaluator's empty database
gets migrated with no extra manual step.

## Verification Summary

- Backend test suite: 84 → 87 passing (added delete-session cascade, 404, and
  isolation tests) across all fixes in this session.
- Every fix above was verified against the *real* running system (real
  Postgres, real Ollama/Gemini/OpenAI calls, real browser screenshots from the
  user) — not just unit tests in isolation.
- `docker compose up --build` confirmed working end-to-end for the first time.
- Frontend `tsc --noEmit` clean after every change.

## Key Technical Decisions

- Chose to measure real retrieval scores against the actual ingested corpus
  before writing grounding logic, rather than reasoning about thresholds in
  the abstract — this is what ultimately distinguished "elaborate on that"
  (should work) from "what is the capital of France?" (should refuse), and
  earlier attempts based on conversation-history heuristics kept finding new
  failure modes precisely because they weren't grounded in real data.
- When a fix looked plausible but hadn't been proven against the exact
  reported scenario, retested against that exact scenario rather than
  declaring victory on a plausible-sounding explanation — this caught two
  separate "looks fixed but isn't" cases (the France hallucination's second
  iteration, and the Ollama timeout config's `--reload`-doesn't-re-source-env
  gotcha).
- Preferred reverting a suspicious change and proving the revert was correct
  (Docker build + full test suite) over assuming an unexplained diff was
  intentional, especially this close to a submission deadline.
