# Design

## Principles

- Make the product feel like an internal workbench, not a marketing page.
- Keep model/provider state visible because AI availability directly affects
  trust.
- Put source citations close to answers so users can inspect grounding quickly.
- Render artifacts beside the conversation to preserve writing context.
- Prefer quiet, dense layouts that support repeated use.

## Information Architecture

- **Sidebar:** brand, new chat action, session list, provider/model status.
- **Chat:** conversation history, sources, loading/error states, composer.
- **Artifact Viewer:** rendered Markdown or sandboxed HTML/CSS preview.

## Component Hierarchy

```text
AppShell
├── SessionSidebar
├── ChatPanel
│   ├── MessageList
│   ├── SourceList
│   └── MessageComposer
└── ArtifactViewer
    ├── MarkdownPreview
    └── HtmlSandbox
```

## Key States

- Empty chat: concise prompt examples and clear model status.
- Sending: composer disabled and message appears optimistically only after API
  acceptance.
- Retrieving: answer area shows retrieval progress.
- No knowledge found: assistant explains that the transcript base does not
  contain enough evidence.
- Provider unavailable: visible status and actionable configuration hint.
- Database unavailable: structured backend error and frontend recovery state.
- Artifact blocked: viewer explains why unsafe content did not render.

## Responsive Behavior

Desktop uses a three-column workspace. Smaller screens stack the sidebar, chat,
and artifact viewer while preserving the chat composer as the primary action.

## Accessibility

Controls use semantic buttons, labels, visible focus states, sufficient color
contrast, and readable fixed font sizes. Icon-only buttons include accessible
labels.
