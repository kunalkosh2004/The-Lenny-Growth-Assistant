# Milestone 08 Agent Transcript

> **Note on provenance:** built with Codebuff; no live transcript was preserved.
> Reconstructed honestly from commit `6819e28` and the current component tree —
> see the note at the top of `milestone-04.md` for the same caveat.

## Goal

Build the polished three-panel frontend: session sidebar with provider status,
chat area with message history and source citations, and an artifact viewer
with Markdown rendering and a sandboxed HTML iframe.

## Approach (from commit `6819e28`)

1. Restructured `frontend/src/app/page.tsx` into a three-column layout
   (session sidebar / chat / artifact panel), +439 lines over the prior app
   shell.
2. Added `SessionSidebar.tsx`: session list, new-chat action, provider/model
   status display.
3. Added `ChatMessage.tsx`: user/assistant bubbles, loading state, error
   state.
4. Added `SourceCard.tsx`: per-source citation chip (guest, episode, date).
5. Added `ArtifactViewer.tsx`: Markdown-to-HTML rendering for Markdown
   artifacts, sandboxed `<iframe>` for HTML artifacts.
6. Wired a full API client (`lib/api.ts`) covering sessions, chat, artifacts,
   and providers, with loading/error states for each.

## Verification (per commit message)

- TypeScript strict mode passes.
- Empty-state guidance covers the no-session and no-messages cases.

## Key Technical Decisions

- The artifact viewer was built with the sandbox model already in mind:
  Markdown is converted to HTML client-side and rendered directly (trusted,
  since it's just formatting), while HTML artifacts are rendered inside an
  `<iframe sandbox="allow-same-origin">` with no `allow-scripts` — this
  decision from Milestone 08 is what Milestone 07's artifact generation had
  to design its system prompts around (no `<script>`, no external resources).
- State management stayed plain React `useState`/`useEffect` rather than
  introducing Redux/Zustand — reasonable for the three-panel scope, though
  `page.tsx` grew into a fairly large single file as a result (later sessions
  added artifact history, a Ship 30 tab, and independent panel scrolling on
  top of this same file without decomposing it further).

## Later Follow-up

Later live Claude sessions (see `milestone-11` and this repository's more
recent commits) added: a runtime model-selector dropdown, artifact history,
a provider/model badge per chat message, a Ship 30 essay tab, session
deletion, and independent scrolling per panel — all built on top of this
milestone's three-panel structure without replacing it.
