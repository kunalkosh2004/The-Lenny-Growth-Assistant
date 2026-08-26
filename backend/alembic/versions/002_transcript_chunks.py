"""add transcript_chunks knowledge base table

Revision ID: 002_transcript_chunks
Revises: 001_initial_persistence_schema
Create Date: 2026-08-26

"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "002_transcript_chunks"
down_revision = "001_initial_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "transcript_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_path", sa.String(length=1024), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        # Dimensionless vector: dimension consistency is enforced per provider
        # at ingestion/query time so switching providers only needs re-ingestion.
        sa.Column("embedding", Vector(), nullable=True),
        sa.Column("chunk_metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_transcript_chunks_source_chunk",
        "transcript_chunks",
        ["source_path", "chunk_index"],
        unique=True,
    )
    op.create_index(
        "ix_transcript_chunks_file_hash", "transcript_chunks", ["file_hash"]
    )


def downgrade() -> None:
    op.drop_index("ix_transcript_chunks_file_hash", table_name="transcript_chunks")
    op.drop_index("uq_transcript_chunks_source_chunk", table_name="transcript_chunks")
    op.drop_table("transcript_chunks")
