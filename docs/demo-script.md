# Demo Script — The Lenny Growth Assistant

## Duration: 2-3 minutes

## Recommended Demo Flow

### 1. Problem Explanation (30 seconds)

**Talking points:**
- Product and growth teams spend hours searching through podcast transcripts
  and internal knowledge for actionable insights.
- Existing AI tools hallucinate — they don't ground answers in your actual
  knowledge base.
- The Lenny Growth Assistant solves this: a grounded AI assistant that
  answers questions using Lenny's Podcast transcript knowledge base with
  verifiable source citations.

**Show:** The landing page with the three-panel layout.

---

### 2. Product Demonstration (90 seconds)

**Step 1: Create a new chat (5 seconds)**
- Click the "+" button to create a new chat session.
- Point out the sidebar showing sessions and provider status.

**Step 2: Ask a grounded question (30 seconds)**
- Type: "How should an early-stage startup improve retention?"
- While it's loading, explain: "The system is retrieving relevant transcript
  chunks, building a grounded prompt, and generating an answer via the LLM."
- After the response appears:
  - "Notice the source citations below — these are real episodes from
    Lenny's Podcast that support this answer."
  - "The system will refuse to answer if it doesn't have enough evidence."

**Step 3: Ask a follow-up question (30 seconds)**
- Type: "Can you give me a specific example from the transcripts?"
- "The system maintains conversation context — it knows what we were
  discussing and retrieves additional relevant chunks."

**Step 4: Generate an artifact (25 seconds)**
- Click the "Artifacts" button in the header.
- Select "Markdown" and type: "Create a retention strategy document"
- Click Generate.
- "The system generates a structured document grounded in transcript
  knowledge — with headings, bold key terms, and source attribution."
- Scroll through the rendered article in the artifact viewer.

---

### 3. Local Ollama Demonstration (30 seconds)

**Talking points:**
- "Everything you just saw is running locally on my machine using Ollama."
- Point to the sidebar: "The provider panel shows Ollama is connected."
- "The embedding model is nomic-embed-text for vector search, and the
  generation model is llama3.1:8b — no API keys, no cloud costs."
- "The same codebase supports OpenAI as a cloud provider — just set
  `LLM_PROVIDER=openai` and add your API key."

**Show:** The provider status in the sidebar.

---

### 4. Technical Trade-off (30 seconds)

**Recommended trade-off to explain:**

"We made a deliberate choice to use **pgvector** (PostgreSQL extension)
instead of a dedicated vector database like Pinecone or Weaviate. This means:

- **Pro**: One fewer operational dependency — PostgreSQL handles both
  session persistence and vector search.
- **Pro**: No external service to manage or pay for.
- **Trade-off**: Vector search performance is good for our scale (~30K
  chunks) but wouldn't scale to millions of documents without additional
  tuning.
- **Trade-off**: The pgvector column is dimensionless, so switching
  embedding providers (e.g. OpenAI 1536-dim vs Ollama 768-dim) requires
  re-ingestion.

For an internal tool serving a single team, this is the right call —
simplicity over theoretical scalability."

---

## Exact Features to Demonstrate

1. ✅ Session creation and sidebar
2. ✅ Grounded chat with source citations
3. ✅ Follow-up questions with conversation context
4. ✅ Artifact generation (Markdown)
5. ✅ Artifact rendering in the viewer
6. ✅ Provider status display (Ollama local)
7. ✅ Error handling (empty retrieval / no hallucination)

## What NOT to Demo

- HTML/CSS artifact generation (more impressive in a written walkthrough)
- Ship 30 essay generation (takes longer, better as a supplementary demo)
- Provider switching (quick but less visual impact)

## Evaluator Checklist

Before the demo, verify:

- [ ] PostgreSQL is running and migrations are applied
- [ ] Ollama is running with `nomic-embed-text` and a generation model
- [ ] At least a few transcripts are ingested (use `--limit 10` for speed)
- [ ] Backend starts without errors (`uvicorn app.main:app --reload`)
- [ ] Frontend loads at `http://localhost:3000`
- [ ] `/health` returns 200
- [ ] A grounded chat question produces a response with sources

## Backup Plan

If Ollama is too slow during the demo:
- Pre-warm the model before starting: `curl http://localhost:11434/api/generate -d '{"model":"llama3.1:8b","prompt":"hello"}'`
- Use `qwen2.5-coder:1.5b` for faster responses (already installed)
- Keep follow-up questions specific to reduce retrieval scope

If the frontend fails to connect:
- Verify `NEXT_PUBLIC_API_BASE_URL` matches the backend port
- Check CORS settings in `.env`
- Fall back to API-only demo using curl/HTTPie
