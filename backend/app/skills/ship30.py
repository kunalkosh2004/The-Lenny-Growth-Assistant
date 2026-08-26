"""Ship 30 for 30 writing skill: generates grounded, long-form essays.

This skill encodes Ship 30 for 30 writing principles and applies them to
transcript-grounded content generation.  It is designed to be reusable:

    Ship30Skill
    ├── Writing principles (encoded, not a one-off prompt)
    ├── Grounded outline generation
    ├── Full article generation (~1,250 words)
    └── Source attachment

Usage::

    skill = Ship30Skill(retrieval, llm_provider)
    result = skill.generate(topic="How to improve retention")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.knowledge.retrieval import RetrievedChunk
from app.providers.base import ChatMessage

logger = logging.getLogger(__name__)

TARGET_WORD_COUNT = 1250

# ---------------------------------------------------------------------------
# Ship 30 for 30 Writing Principles
# ---------------------------------------------------------------------------

WRITING_PRINCIPLES = """\
## Ship 30 for 30 Writing Principles

### Structure
- **Hook**: Open with a bold, specific claim or surprising data point that
  makes the reader want to continue.  No generic introductions.
- **Context**: In 1-2 paragraphs, explain why this topic matters right now
  and who it is for.
- **Body**: 3-5 major sections, each with a clear heading.  Each section
  should deliver one actionable insight grounded in evidence.
- **Conclusion**: End with a specific, actionable takeaway the reader can
  apply immediately.

### Voice and Tone
- Write like a smart friend explaining something over coffee: direct,
  opinionated, specific.
- Use first person sparingly.  Prefer active voice.
- Avoid jargon, buzzwords, and filler phrases ("in today's fast-paced
  world", "it's no secret that").

### Formatting
- Use **bold** for key terms and takeaways the reader should remember.
- Use bullet points for lists of 3+ items.
- Use subheadings to break up long sections.
- Keep paragraphs to 3-5 sentences maximum.
- Include at least one specific example, quote, or data point per section.

### Grounding Rules
- Every claim MUST be grounded in the provided transcript context.
- When referencing a guest, use their name and context (e.g. "Derek Sivers,
  founder of CD Baby, explains...").
- If the transcript context is insufficient for a section, state what is
  missing rather than fabricating content.
- Never invent statistics, quotes, or anecdotes.

### Content Quality
- Aim for ~1,250 words total.
- Each section should be 200-350 words.
- The hook should be 2-3 sentences max.
- The conclusion should be 1-2 paragraphs.
- Avoid repeating the same point in different words.
"""

OUTLINE_TEMPLATE = """\
Create a detailed outline for a ~{target_words}-word article on the topic
below.  The outline should include:

1. A compelling hook (2-3 sentences)
2. A brief context section (1 paragraph)
3. 3-5 body sections with clear headings and key points for each
4. A conclusion with a specific actionable takeaway

Use the transcript context to ground every section in real evidence.

TRANSCRIPT CONTEXT:
{context}

TOPIC: {topic}
"""

ARTICLE_TEMPLATE = """\
Write a ~{target_words}-word article on the topic below using the outline
and transcript context provided.  Follow these Ship 30 for 30 writing
principles:

{principles}

OUTLINE:
{outline}

TRANSCRIPT CONTEXT:
{context}

Requirements:
- Target approximately {target_words} words.
- Use the hook, structure, and section headings from the outline.
- Every claim must be grounded in the transcript context.
- Use bold for key terms, bullet points for lists, and clear subheadings.
- End with a specific, actionable takeaway.
- Do NOT fabricate any content not supported by the transcripts.
"""


@dataclass
class SkillResult:
    content: str
    word_count: int
    sources: list[dict] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "word_count": self.word_count,
            "sources": self.sources,
            "model": self.model,
            "provider": self.provider,
            "usage": self.usage,
        }


class Ship30Skill:
    """Reusable Ship 30 for 30 essay generation skill.

    The skill follows a structured two-pass generation process:

    1. **Outline pass**: given transcript context, generate a detailed
       outline grounded in the retrieved evidence.
    2. **Article pass**: expand the outline into a full ~1,250-word article
       following the encoded writing principles.

    This two-pass approach produces better structure and grounding than a
    single prompt.
    """

    def __init__(self, retrieval_service, llm_provider) -> None:
        self._retrieval = retrieval_service
        self._llm = llm_provider

    def _build_sources(self, chunks: list[RetrievedChunk]) -> list[dict]:
        seen: set[str] = set()
        sources: list[dict] = []
        for chunk in chunks:
            key = chunk.metadata.get("title", chunk.source_path)
            if key in seen:
                continue
            seen.add(key)
            sources.append({
                "title": chunk.metadata.get("title", ""),
                "guest": chunk.metadata.get("guest", ""),
                "publish_date": chunk.metadata.get("publish_date", ""),
                "youtube_url": chunk.metadata.get("youtube_url", ""),
                "source_path": chunk.source_path,
                "relevance": f"Score: {chunk.score:.3f}",
            })
        return sources

    def _format_context(self, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return "(No relevant transcript excerpts found.)"
        parts: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.metadata
            header = f"[Source {i}]"
            title = source.get("title", "")
            guest = source.get("guest", "")
            if title:
                header += f" {title}"
            if guest:
                header += f" — Guest: {guest}"
            parts.append(f"{header}\n{chunk.content}")
        return "\n\n---\n\n".join(parts)

    def generate(
        self,
        topic: str,
        *,
        top_k: int = 10,
        target_words: int = TARGET_WORD_COUNT,
    ) -> SkillResult:
        """Generate a Ship 30 for 30 article grounded in transcript context.

        1. Retrieve relevant transcript chunks for the topic.
        2. Generate a structured outline from the context.
        3. Expand the outline into a full article following writing principles.
        4. Return the article with source citations.
        """
        if not topic.strip():
            raise ValueError("Topic cannot be empty.")

        # 1. Retrieve transcript context.
        try:
            chunks = self._retrieval.search(topic, top_k=top_k)
        except Exception as exc:
            logger.warning("Retrieval failed for article generation: %s", exc)
            chunks = []

        context_text = self._format_context(chunks)
        sources = self._build_sources(chunks)

        # 2. Outline pass.
        outline_prompt = OUTLINE_TEMPLATE.format(
            target_words=target_words,
            context=context_text,
            topic=topic,
        )
        outline_messages = [
            ChatMessage(
                role="system",
                content="You are a structured content outline generator.",
            ),
            ChatMessage(role="user", content=outline_prompt),
        ]
        outline_result = self._llm.generate(
            outline_messages, temperature=0.5, max_tokens=1500,
        )
        outline = outline_result.content

        # 3. Article pass.
        article_prompt = ARTICLE_TEMPLATE.format(
            target_words=target_words,
            principles=WRITING_PRINCIPLES,
            outline=outline,
            context=context_text,
        )
        article_messages = [
            ChatMessage(role="system", content="You are an expert writer."),
            ChatMessage(role="user", content=article_prompt),
        ]
        article_result = self._llm.generate(
            article_messages, temperature=0.7, max_tokens=4096,
        )
        article = article_result.content
        word_count = len(article.split())

        return SkillResult(
            content=article,
            word_count=word_count,
            sources=sources,
            model=article_result.model,
            provider=article_result.provider,
            usage=article_result.usage,
        )
