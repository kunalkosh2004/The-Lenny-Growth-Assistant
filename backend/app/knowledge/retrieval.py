"""Retrieval service: vector search over transcript chunks with source metadata."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.knowledge.embeddings import (
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.models.transcript_chunk import TranscriptChunk

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 6


@dataclass
class RetrievedChunk:
    content: str
    score: float
    source_path: str
    chunk_index: int
    metadata: dict

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "score": round(self.score, 4),
            "source": {
                "title": self.metadata.get("title", ""),
                "guest": self.metadata.get("guest", ""),
                "publish_date": self.metadata.get("publish_date", ""),
                "youtube_url": self.metadata.get("youtube_url", ""),
                "source_path": self.source_path,
            },
        }


class RetrievalService:
    def __init__(
        self, db: Session, settings: Settings, embedding_provider: EmbeddingProvider | None = None
    ) -> None:
        self.db = db
        self.settings = settings
        self._embedding_provider = embedding_provider

    def _provider(self) -> EmbeddingProvider:
        if self._embedding_provider is None:
            from app.knowledge.embeddings import get_embedding_provider

            self._embedding_provider = get_embedding_provider(self.settings)
        return self._embedding_provider

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[RetrievedChunk]:
        """Return the most relevant transcript chunks for a query.

        Raises EmbeddingProviderError if the provider cannot embed the query.
        Raises nothing on empty retrieval — callers receive an empty list so
        they can respond with "insufficient knowledge base" messaging instead
        of hallucinating.
        """
        if not query.strip():
            return []

        try:
            query_embedding = self._provider().embed_query(query)
        except EmbeddingProviderError:
            raise

        if not query_embedding:
            logger.warning("Query embedding is empty; returning no results.")
            return []

        # pgvector cosine distance: 0 = identical, 2 = opposite.
        distance = TranscriptChunk.embedding.cosine_distance(query_embedding)

        stmt = (
            select(TranscriptChunk, distance.label("distance"))
            .order_by(distance)
            .limit(top_k)
        )

        rows = self.db.execute(stmt).all()
        results: list[RetrievedChunk] = []
        for chunk, distance_val in rows:
            # Convert cosine distance to similarity score: 1 - distance, clamped.
            score = max(0.0, 1.0 - (distance_val or 1.0))
            if score < self.settings.retrieval_min_score:
                # Rows are ordered by distance ascending (score descending),
                # so every remaining row is also below threshold.
                break
            results.append(
                RetrievedChunk(
                    content=chunk.content,
                    score=score,
                    source_path=chunk.source_path,
                    chunk_index=chunk.chunk_index,
                    metadata=chunk.chunk_metadata or {},
                )
            )
        return results
