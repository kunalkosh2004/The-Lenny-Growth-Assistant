# Product Requirements Document

## User and Problem

The primary users are product managers, growth leads, founders, and operators
who want fast, citation-backed access to product and growth lessons from
Lenny's Podcast transcripts.

They need to turn scattered long-form interview knowledge into grounded answers,
strategy memos, Ship 30 for 30-style essays, and reusable artifacts without
manually searching hundreds of transcripts.

## Success Metrics

- At least 90% of grounded answers include one or more retrieved transcript
  sources when relevant evidence exists.
- A user can generate a reusable grounded content artifact in under three
  minutes after ingestion is complete.
- Empty or weak retrieval results produce an explicit insufficient-evidence
  response rather than unsupported advice.

## Assumptions

- The transcript repository is prepared locally before ingestion.
- PostgreSQL with pgvector is acceptable as both persistence and vector store.
- Ollama is available locally for the demo, but the app must handle it being
  unavailable.
- Cloud LLM credentials may be absent during local development.

## Scope

Included:

- Full-stack chat application.
- Local transcript ingestion into PostgreSQL + pgvector.
- Grounded Q&A with source citations.
- Multiple chat sessions.
- Ship 30 for 30 writing skill.
- Markdown and HTML/CSS artifact generation.
- Secure artifact rendering.
- Ollama and one cloud provider.

Excluded:

- Multi-user authentication in the first production pass. The assignment focuses
  on internal evaluator usage and grounded AI workflow.
- Real-time collaborative editing. Artifacts are generated and viewed, not
  co-edited.
- Automatic GitHub transcript fetching during normal app usage. The local
  transcript repository is the source of truth.

## User Flows

1. User starts the app, sees model/provider status, and creates a chat.
2. User asks a product or growth question.
3. Backend retrieves relevant transcript chunks from pgvector.
4. LLM generates a grounded answer with sources.
5. User asks follow-up questions in the same session.
6. User asks for a Ship 30 essay or Markdown/HTML artifact.
7. Generated artifact opens beside the chat and is stored with the session.

## Acceptance Criteria

- Health and readiness endpoints respond with structured JSON.
- Sessions and messages persist in PostgreSQL after Milestone 2.
- Ingestion discovers every `**/transcript.md` under the local episodes
  directory after Milestone 3.
- Retrieved chunks include traceable source metadata.
- Chat answers cite only retrieved transcript sources.
- Generated HTML artifacts render without script execution.
- README supports fresh evaluator setup.

## Risks and Trade-offs

- Hallucination risk is mitigated by retrieval-only grounding and explicit
  insufficient-evidence responses.
- Retrieval quality depends on chunking and embedding model selection.
- Local Ollama responses may be slower or lower quality than cloud responses.
- Cloud providers introduce cost and credential handling.
- Sandboxed artifact rendering improves safety but limits interactive HTML.
- Docker Compose improves reproducibility but adds operational complexity.
