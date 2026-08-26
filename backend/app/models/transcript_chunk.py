import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TranscriptChunk(Base):
    """A searchable chunk of a Lenny's Podcast transcript.

    Each chunk traces back to its source episode via ``source_path`` (the
    relative path of the transcript file inside the episodes directory) plus
    structured metadata extracted from the file's YAML frontmatter.
    """

    __tablename__ = "transcript_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    """Relative path of the episode's transcript.md inside TRANSCRIPTS_DIR."""

    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    """SHA-256 of the raw transcript file; used to skip unchanged episodes on refresh."""

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(), nullable=True)
    """pgvector embedding. Dimension is enforced at write time from the active
    embedding provider so providers with different dimensions can coexist with
    a re-ingestion."""

    chunk_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    """Episode metadata: title, guest, youtube_url, publish_date, duration, keywords."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "uq_transcript_chunks_source_chunk",
            "source_path",
            "chunk_index",
            unique=True,
        ),
        Index("ix_transcript_chunks_file_hash", "file_hash"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<TranscriptChunk {self.source_path}#{self.chunk_index}>"
