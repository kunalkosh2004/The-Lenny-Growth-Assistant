"""Ingestion service: transcripts -> chunks -> embeddings -> PostgreSQL/pgvector.

Refresh strategy: each episode's raw file is hashed (SHA-256). On ingest, an
episode whose stored chunk rows all carry the current ``file_hash`` is skipped;
changed or new episodes have their old rows deleted and are re-chunked and
re-embedded. Episodes removed from disk can be pruned with ``prune_missing``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.knowledge.chunker import chunk_text
from app.knowledge.embeddings import (
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.knowledge.parser import (
    TranscriptFile,
    TranscriptSourceError,
    discover_transcripts,
)
from app.models.transcript_chunk import TranscriptChunk

logger = logging.getLogger(__name__)


@dataclass
class IngestionSummary:
    discovered: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    chunks_created: int = 0
    chunks_stored: int = 0
    failures: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "transcripts_discovered": self.discovered,
            "transcripts_processed": self.processed,
            "transcripts_skipped": self.skipped,
            "transcripts_failed": self.failed,
            "chunks_created": self.chunks_created,
            "chunks_stored": self.chunks_stored,
            "failures": self.failures,
        }


class IngestionService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.embedding_provider = embedding_provider

    def _provider(self) -> EmbeddingProvider:
        if self.embedding_provider is None:
            from app.knowledge.embeddings import get_embedding_provider

            self.embedding_provider = get_embedding_provider(self.settings)
        return self.embedding_provider

    def _stored_hashes(self) -> dict[str, set[str]]:
        rows = self.db.execute(
            select(TranscriptChunk.source_path, TranscriptChunk.file_hash)
        ).all()
        hashes: dict[str, set[str]] = {}
        for source_path, file_hash in rows:
            hashes.setdefault(source_path, set()).add(file_hash)
        return hashes

    def _is_current(self, transcript: TranscriptFile, stored: dict[str, set[str]]) -> bool:
        hashes = stored.get(transcript.source_path)
        return bool(hashes) and hashes == {transcript.file_hash}

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        provider = self._provider()
        embeddings: list[list[float]] = []
        batch_size = max(1, self.settings.ingestion_batch_size)
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            try:
                embeddings.extend(provider.embed_documents(batch))
            except EmbeddingProviderError:
                raise
        return embeddings

    def ingest_transcript(self, transcript: TranscriptFile) -> int:
        """Chunk, embed, and store one transcript. Returns stored chunk count."""
        chunks = chunk_text(
            transcript.content,
            target_chars=self.settings.chunk_target_chars,
            overlap_chars=self.settings.chunk_overlap_chars,
        )
        if not chunks:
            raise ValueError("Transcript produced no usable content after cleaning.")

        embeddings = self._embed_batch(chunks)
        if len(embeddings) != len(chunks):
            raise ValueError(
                f"Embedding count mismatch: {len(embeddings)} embeddings "
                f"for {len(chunks)} chunks."
            )

        for index, (content, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
            self.db.add(
                TranscriptChunk(
                    source_path=transcript.source_path,
                    file_hash=transcript.file_hash,
                    chunk_index=index,
                    content=content,
                    embedding=embedding,
                    chunk_metadata=transcript.metadata,
                )
            )
        return len(chunks)

    def run(self, prune_missing: bool = False, limit: int | None = None) -> IngestionSummary:
        episodes_dir = Path(self.settings.transcripts_dir)
        transcripts = discover_transcripts(episodes_dir)
        summary = IngestionSummary(discovered=len(transcripts))
        logger.info("Discovered %d transcripts in %s", len(transcripts), episodes_dir)

        stored_hashes = self._stored_hashes()
        known_paths = {t.source_path for t in transcripts}

        if prune_missing:
            stale = [p for p in stored_hashes if p not in known_paths]
            for path in stale:
                self.db.execute(
                    delete(TranscriptChunk).where(TranscriptChunk.source_path == path)
                )
            if stale:
                logger.info("Pruned %d removed episodes", len(stale))
                self.db.commit()

        count = 0
        for transcript in transcripts:
            if limit is not None and count >= limit:
                logger.info("Reached limit of %d episodes", limit)
                break
            if self._is_current(transcript, stored_hashes):
                summary.skipped += 1
                count += 1
                continue
            try:
                self.db.execute(
                    delete(TranscriptChunk).where(
                        TranscriptChunk.source_path == transcript.source_path
                    )
                )
                created = self.ingest_transcript(transcript)
                self.db.commit()
                summary.processed += 1
                summary.chunks_created += created
                summary.chunks_stored += created
                count += 1
                logger.info(
                    "Ingested %s (%d chunks) [%d/%d]",
                    transcript.source_path, created, count, len(transcripts),
                )
            except Exception as exc:  # noqa: BLE001 - keep ingesting other files
                summary.failed += 1
                summary.failures.append(f"{transcript.source_path}: {exc}")
                logger.exception("Failed to ingest %s", transcript.source_path)
                self.db.rollback()

        return summary

    def status(self) -> dict:
        episodes_dir = Path(self.settings.transcripts_dir)
        chunks = self.db.scalar(func.count(TranscriptChunk.id)) or 0
        indexed = self.db.execute(
            select(func.count(func.distinct(TranscriptChunk.source_path)))
        ).scalar() or 0

        discovered = 0
        missing_metadata = 0
        try:
            transcripts = discover_transcripts(episodes_dir)
            discovered = len(transcripts)
            missing_metadata = sum(
                1
                for t in transcripts
                if not t.metadata.get("title") or not t.metadata.get("guest")
            )
        except TranscriptSourceError:
            pass

        return {
            "episodes_discovered_on_disk": discovered,
            "episodes_indexed": indexed,
            "chunks_indexed": chunks,
            "episodes_missing_title_or_guest": missing_metadata,
            "embedding_model": (
                self._provider().model_name if self.embedding_provider else None
            ),
            "source_directory": str(episodes_dir),
        }
