# Milestone 04 Agent Transcript

> **Note on provenance:** this milestone (and 08, 10) were originally built with
> Codebuff rather than Claude, and no live turn-by-turn transcript was preserved
> at the time. This file is an honest reconstruction from the actual commit
> (`079ff7c`), diff, and test suite — not a fabricated debugging narrative. It
> was filled in later (see `docs/manual-test-plan.md` and later milestone
> transcripts for material from live Claude sessions with full transcripts).

## Goal

Add an LLM provider abstraction so the application can switch between a local
model (Ollama, mandatory for the demo) and a cloud model (OpenAI) without
changing application code.

## Approach (from commit `079ff7c`)

1. Defined a `Protocol`-based `LLMProvider` interface in `app/providers/base.py`
   (`ChatMessage`, `GenerateResult` dataclasses, a typed error hierarchy:
   `ProviderError`, `ProviderTimeoutError`, `ProviderAuthError`,
   `ProviderModelNotFoundError`).
2. Implemented `OllamaProvider` (`app/providers/ollama.py`) against the local
   `/api/chat` and `/api/tags` endpoints, with model-availability checks.
3. Implemented `OpenAIProvider` (`app/providers/openai.py`) against the Chat
   Completions API.
4. Built `app/providers/factory.py`: reads `LLM_PROVIDER` from `Settings`,
   caches the active provider, and exposes `select_provider()` for runtime
   switching without a process restart.
5. Added `GET /api/providers` (status/availability per provider) and
   `POST /api/providers/select` (runtime switch) in `app/api/providers.py`.
6. Wrote 15 automated tests (`tests/test_providers.py`) covering provider
   construction, error mapping, and the factory's caching/switching behavior.

## Verification (per commit message)

- 15/15 provider tests passing.
- Verified real Ollama generation locally with `qwen2.5-coder:1.5b`.

## Key Technical Decisions

- Provider errors are mapped to a typed hierarchy at each provider's boundary
  (connection vs timeout vs auth vs missing model) rather than surfacing raw
  HTTP/SDK exceptions, so API handlers can return meaningful status codes and
  messages instead of a generic 500.
- The factory caches the active provider as module-level state and only
  rebuilds it on an explicit `select_provider()` call — this is what later
  powers the frontend's runtime model-switcher dropdown without restarting the
  backend.

## Later Follow-up

Anthropic and Google Gemini providers were added afterward (commit `e8b2c04`,
"feat: add Anthropic, Google Gemini, and runtime model selection dropdown"),
extending this same abstraction to four total providers.
