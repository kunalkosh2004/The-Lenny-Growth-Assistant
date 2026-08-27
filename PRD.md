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
- The "agent layer" requirement is satisfied by a custom, provider-agnostic
  skill/router architecture rather than the literal `claude-agent-sdk`
  package — see the Agent Layer Decision note under Risks and Trade-offs
  for why.

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

### Agent Layer Decision: custom router vs. `claude-agent-sdk`

The assignment asks for the agent layer to be built with the Anthropic
Claude Agent SDK or Pi Coding Agent. We evaluated `claude-agent-sdk`
(the Python package matching that name) and chose **not** to build the
core routing layer on top of it, for two concrete reasons found during
evaluation rather than by assumption:

1. **It doesn't run in-process.** `claude-agent-sdk` spawns the `claude`
   CLI binary as a subprocess (`shutil.which("claude")`); no binary is
   bundled with the pip package. In practice that means installing
   Node.js and the `@anthropic-ai/claude-code` npm package inside the
   backend's Docker image purely to route a request — a heavy runtime
   dependency for a stateless FastAPI request handler.
2. **It only talks to Anthropic's own models.** There is no path to
   route an Agent SDK session through Ollama or any other provider.
   Since the assignment separately requires the demo to run **locally
   on Ollama, mandatory**, making the core grounded-assistant pipeline
   depend on the Agent SDK would mean the primary demo path stops
   working without an `ANTHROPIC_API_KEY` — directly contradicting the
   "must work locally" requirement.

Given that conflict, we built the agent layer as a custom, explicit
skill/router architecture instead (`ChatService`, `ArtifactService`,
`Ship30Skill` in `backend/app/services` and `backend/app/skills`,
selected by dedicated API routes rather than free-form intent
detection — see `architecture.md` for the routing diagram). It keeps
clear skill boundaries, works identically regardless of which LLM
provider is active (Ollama, OpenAI, Anthropic, or Gemini), and adds no
extra deployment dependency.

**Trade-off accepted:** this satisfies the spirit of "clear skill
boundaries and reliable routing" from the evaluation criteria, but not
the literal letter of "built with the Claude Agent SDK." If cloud-only
deployment (Anthropic key always present, no local-Ollama requirement)
were the actual target environment, adopting the Agent SDK for
intent-based routing would be a reasonable follow-up — it is a good
fit once the Node.js/Anthropic-only constraints stop being blockers.
