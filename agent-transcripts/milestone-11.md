# Milestone 11 Agent Transcript

## Goal

Prepare a concise 2-3 minute demo flow, demo script, technical trade-off
explanation, and evaluator checklist for the final submission.

## Approach

1. Created `docs/demo-script.md` with:
   - 4-section demo flow (problem, product, Ollama, trade-off).
   - Exact features to demonstrate and what to skip.
   - Pre-demo verification checklist.
   - Backup plan for slow models or frontend issues.
2. Key demo features: grounded chat with sources, follow-up context,
   artifact generation, provider status, Ollama local demo.
3. Technical trade-off: pgvector vs dedicated vector database — chosen
   for simplicity of a single PostgreSQL dependency.

## Key Decisions

- **Demo length**: 2-3 minutes keeps it focused and evaluator-friendly.
- **Trade-off choice**: pgvector was the most impactful technical decision
   to explain because it directly affects architecture and scalability.
- **Backup plan**: pre-warming Ollama models and having a smaller model
   available ensures the demo doesn't stall on slow generation.
