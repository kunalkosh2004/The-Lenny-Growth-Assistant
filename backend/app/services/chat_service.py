"""Grounded chat service: retrieves transcript context, generates an answer,
and preserves conversation history for follow-up questions.

Architecture:

    User message
         |
         v
    Conversation History Builder
         |
         v
    Retrieval Service  (pgvector cosine search)
         |
         v
    Grounded Prompt Builder
         |
         v
    LLM Provider  (Ollama / OpenAI)
         |
         v
    Response + Source Citations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.knowledge.retrieval import RetrievalService, RetrievedChunk
from app.models.message import Message
from app.providers.base import ChatMessage
from app.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

# How many prior user/assistant turns to include as conversation context.
MAX_CONTEXT_TURNS = 10

NO_EVIDENCE_MESSAGE = (
    "I don't have enough information in the available Lenny's Podcast "
    "transcripts to answer that question confidently. The knowledge base "
    "doesn't contain sufficient evidence on this topic."
)

SYSTEM_PROMPT = """\
You are The Lenny Growth Assistant, an AI assistant that answers product
management and growth questions using knowledge from Lenny's Podcast
transcripts.

Rules:
1. Answer ONLY based on the transcript context provided below.
2. If the transcript context does not contain enough information to answer
   the question, say so clearly. Do NOT fabricate or hallucinate.
3. Cite specific sources when referencing transcript content.
4. Be helpful, specific, and actionable.
5. When comparing approaches, use specific examples from the transcripts.
6. If the user asks a follow-up question, use both the prior conversation
   and the retrieved transcript context to answer.

When you reference a source, mention the guest name and episode title.

If you cannot answer from the available knowledge base, respond with:
"I don't have enough information in the available Lenny's Podcast transcripts
to answer that question confidently. The knowledge base doesn't contain
sufficient evidence on this topic."

Never make up guest names, episode titles, or transcript content.
"""

GROUNDING_TEMPLATE = """\
Based on the following transcript excerpts from Lenny's Podcast, answer the
user's question. Include source citations where appropriate.

TRANSCRIPT CONTEXT:
{context}

CONVERSATION HISTORY:
{history}

USER QUESTION:
{question}
"""


@dataclass
class ChatSource:
    title: str
    guest: str
    publish_date: str
    youtube_url: str
    source_path: str
    relevance: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "guest": self.guest,
            "publish_date": self.publish_date,
            "youtube_url": self.youtube_url,
            "source_path": self.source_path,
            "relevance": self.relevance,
        }


@dataclass
class ChatResponse:
    content: str
    sources: list[ChatSource] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "sources": [s.to_dict() for s in self.sources],
            "model": self.model,
            "provider": self.provider,
            "usage": self.usage,
        }


class ChatService:
    """Orchestrates grounded chat with retrieval, generation, and history."""

    def __init__(
        self,
        db: Session,
        settings: Settings,
        retrieval_service: RetrievalService | None = None,
        llm_provider: Any = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self._retrieval = retrieval_service or RetrievalService(db, settings)
        self._llm = llm_provider

    def _get_llm(self):
        if self._llm is None:
            self._llm = get_llm_provider(self.settings)
        return self._llm

    def _load_history(self, session_id: Any, limit: int = MAX_CONTEXT_TURNS) -> list[dict]:
        """Load the last N turns of conversation history for a session."""
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit * 2)  # user + assistant pairs
        )
        messages = list(reversed(list(self.db.scalars(stmt).all())))
        return [
            {
                "role": m.role,
                "content": m.content,
                "grounded": bool((m.message_metadata or {}).get("sources")),
            }
            for m in messages
        ]

    def _format_history(self, history: list[dict]) -> str:
        if not history:
            return "(No prior conversation in this session.)"
        lines: list[str] = []
        for msg in history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role_label}: {msg['content']}")
        return "\n".join(lines)

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

    def _build_sources(self, chunks: list[RetrievedChunk]) -> list[ChatSource]:
        seen: set[str] = set()
        sources: list[ChatSource] = []
        for chunk in chunks:
            key = chunk.metadata.get("title", chunk.source_path)
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                ChatSource(
                    title=chunk.metadata.get("title", ""),
                    guest=chunk.metadata.get("guest", ""),
                    publish_date=chunk.metadata.get("publish_date", ""),
                    youtube_url=chunk.metadata.get("youtube_url", ""),
                    source_path=chunk.source_path,
                    relevance=f"Score: {chunk.score:.3f}",
                )
            )
        return sources

    def chat(
        self,
        session_id: Any,
        user_message: str,
        *,
        top_k: int = 6,
    ) -> ChatResponse:
        """Process a user message through the grounded chat pipeline.

        1. Load conversation history for context.
        2. Retrieve relevant transcript chunks.
        3. Build a grounded prompt.
        4. Generate a response via the LLM.
        5. Return the response with source citations.

        Raises ProviderError on LLM failures so callers can return
        appropriate HTTP status codes.
        """
        if not user_message.strip():
            raise ValueError("User message cannot be empty.")

        # 1. Load conversation history.
        history = self._load_history(session_id)

        # 2. Retrieve relevant transcript chunks.
        try:
            chunks = self._retrieval.search(user_message, top_k=top_k)
        except Exception as exc:
            logger.warning("Retrieval failed: %s", exc)
            chunks = []

        # If nothing relevant was retrieved and there's no prior *grounded*
        # exchange to fall back on for a follow-up, refuse deterministically
        # rather than trusting the LLM to notice the context is irrelevant
        # (smaller local models are unreliable at this — see grounding rule
        # 2 in SYSTEM_PROMPT). A prior refusal doesn't count — otherwise
        # repeating the same off-topic question would slip past this check
        # on the second try, since `history` already includes that reply.
        has_prior_grounded_turn = any(
            m["role"] == "assistant" and m["grounded"] for m in history
        )
        if not chunks and not has_prior_grounded_turn:
            return ChatResponse(content=NO_EVIDENCE_MESSAGE, sources=[])

        # 3. Build the grounded prompt.
        history_text = self._format_history(history)
        context_text = self._format_context(chunks)
        user_prompt = GROUNDING_TEMPLATE.format(
            context=context_text,
            history=history_text,
            question=user_message,
        )

        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        # 4. Generate a response.
        llm = self._get_llm()
        result = llm.generate(messages, temperature=0.7, max_tokens=4096)

        # 5. Build sources.
        sources = self._build_sources(chunks)

        return ChatResponse(
            content=result.content,
            sources=sources,
            model=result.model,
            provider=result.provider,
            usage=result.usage,
        )
