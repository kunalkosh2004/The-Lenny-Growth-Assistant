"""Artifact generation service: produces Markdown and HTML/CSS artifacts
grounded in transcript knowledge.

Supported artifact types:

- ``markdown``: structured Markdown documents (strategy memos, outlines, etc.)
- ``html``: complete HTML/CSS pages rendered in a sandboxed iframe

Each generation follows the same pattern:

1. Retrieve relevant transcript chunks.
2. Build a generation prompt with context.
3. Generate the artifact content via the LLM.
4. Wrap the content with appropriate metadata.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.knowledge.retrieval import RetrievalService, RetrievedChunk
from app.providers.base import ChatMessage

logger = logging.getLogger(__name__)

MARKDOWN_SYSTEM_PROMPT = """\
You are an expert content writer creating a structured Markdown document.
Write clear, professional content with proper Markdown formatting:
- Use # for title, ## for sections, ### for subsections
- Use **bold** for key terms
- Use bullet points and numbered lists
- Use blockquotes for key insights
- Aim for 800-1500 words
- Ground all claims in the provided transcript context
- Never fabricate information not present in the context
"""

HTML_SYSTEM_PROMPT = """\
You are an expert front-end developer creating a self-contained HTML page
with embedded CSS. The page should:

- Be a COMPLETE HTML document (<!DOCTYPE html>, <html>, <head>, <body>)
- Include all CSS in a <style> tag in the <head>
- Use modern, clean design (system fonts, good spacing, readable typography)
- Be responsive (use max-width, flexible layouts)
- Use a professional color scheme
- NOT use any JavaScript
- NOT load external resources (fonts, scripts, images from CDNs)
- NOT use <iframe>, <object>, <embed>, or <form> elements
- Be safe to render in a sandboxed iframe

Design guidelines:
- Max content width: 720px, centered
- Font: system font stack (sans-serif)
- Colors: dark text (#1a1a1a) on white (#ffffff) background
- Accent color: #2563eb (blue) for headings and links
- Section spacing: 2rem between major sections
- Line height: 1.6 for body text
"""

ARTICLE_TEMPLATE = """\
Based on the following transcript context from Lenny's Podcast, generate
the requested content.  Ground all claims in the provided evidence.

TRANSCRIPT CONTEXT:
{context}

REQUEST:
{request}
"""

VALID_TYPES = {"markdown", "html"}


@dataclass
class ArtifactResult:
    content: str
    artifact_type: str
    title: str
    sources: list[dict] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "type": self.artifact_type,
            "title": self.title,
            "sources": self.sources,
            "model": self.model,
            "provider": self.provider,
            "usage": self.usage,
        }


class ArtifactService:
    """Generates grounded artifacts in Markdown or HTML/CSS format."""

    def __init__(self, retrieval_service: RetrievalService, llm_provider) -> None:
        self._retrieval = retrieval_service
        self._llm = llm_provider

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
                "source_path": chunk.source_path,
            })
        return sources

    def _strip_code_fence(self, content: str) -> str:
        """Extract a fenced ```lang ... ``` code block's contents, if present.

        LLMs frequently wrap generated HTML/Markdown in a fenced code block
        even when instructed to return raw content, sometimes with extra
        commentary before/after the fence ("Here is the requested..."). This
        searches for the first fenced block anywhere in the text rather than
        requiring the whole response to be just the fence, so leading/
        trailing prose gets discarded along with the fence markers.
        """
        match = re.search(r"```[a-zA-Z0-9]*\s*\n(.*?)\n```", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return content.strip()

    def _extract_html_document(self, content: str) -> str:
        """Extract just the <html>...</html> document, discarding any prose
        commentary the LLM added before/after it (fenced or not).
        """
        match = re.search(r"<!DOCTYPE html.*?</html>", content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(0).strip()
        match = re.search(r"<html.*?</html>", content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(0).strip()
        return content

    def _extract_title(self, content: str, artifact_type: str) -> str:
        """Extract a title from the generated content."""
        if artifact_type == "markdown":
            # Look for first # heading.
            match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if match:
                return match.group(1).strip()
        elif artifact_type == "html":
            # Look for <title> or first <h1>.
            title_match = re.search(r"<title>([^<]+)</title>", content, re.IGNORECASE)
            if title_match:
                return title_match.group(1).strip()
            h1_match = re.search(r"<h1[^>]*>([^<]+)</h1>", content, re.IGNORECASE)
            if h1_match:
                return h1_match.group(1).strip()
        return "Generated Artifact"

    def generate(
        self,
        artifact_type: str,
        request_text: str,
        *,
        top_k: int = 10,
    ) -> ArtifactResult:
        """Generate an artifact of the given type.

        Args:
            artifact_type: "markdown" or "html"
            request_text: description of what to generate
            top_k: number of transcript chunks to retrieve

        Raises:
            ValueError: if artifact_type is invalid or request is empty
        """
        if artifact_type not in VALID_TYPES:
            raise ValueError(
                f"Invalid artifact type '{artifact_type}'. "
                f"Supported types: {sorted(VALID_TYPES)}"
            )
        if not request_text.strip():
            raise ValueError("Artifact request cannot be empty.")

        # 1. Retrieve transcript context.
        try:
            chunks = self._retrieval.search(request_text, top_k=top_k)
        except Exception as exc:
            logger.warning("Retrieval failed for artifact: %s", exc)
            chunks = []

        context_text = self._format_context(chunks)
        sources = self._build_sources(chunks)

        # 2. Select system prompt based on type.
        if artifact_type == "markdown":
            system_prompt = MARKDOWN_SYSTEM_PROMPT
        else:
            system_prompt = HTML_SYSTEM_PROMPT

        # 3. Generate the artifact.
        user_prompt = ARTICLE_TEMPLATE.format(
            context=context_text, request=request_text,
        )
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]
        result = self._llm.generate(messages, temperature=0.7, max_tokens=4096)
        content = self._strip_code_fence(result.content)
        if artifact_type == "html":
            content = self._extract_html_document(content)
        title = self._extract_title(content, artifact_type)

        return ArtifactResult(
            content=content,
            artifact_type=artifact_type,
            title=title,
            sources=sources,
            model=result.model,
            provider=result.provider,
            usage=result.usage,
        )
