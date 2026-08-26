#!/usr/bin/env python3
"""Ingest Lenny's Podcast transcripts into the PostgreSQL/pgvector knowledge base."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(PROJECT_ROOT)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from alembic.config import Config
from alembic import command
from app.core.config import get_settings
from app.knowledge.embeddings import get_embedding_provider
from app.knowledge.ingest import IngestionService
from app.knowledge.parser import TranscriptSourceError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)




def run_alembic() -> None:
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Ingest transcripts")
    parser.add_argument("--limit", type=int, default=None,
                        help="Ingest at most N episodes (for testing)")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("Database connection verified.")

    run_alembic()
    logger.info("Migrations applied.")

    try:
        provider = get_embedding_provider(settings)
        logger.info("Embedding provider: %s (model=%s)",
                    settings.embedding_provider, provider.model_name)
    except Exception as exc:
        logger.error("Embedding provider error: %s", exc)
        return 1

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        service = IngestionService(db, settings, embedding_provider=provider)
        logger.info("Starting ingestion from: %s", settings.transcripts_dir)
        summary = service.run(prune_missing=True, limit=args.limit)

        logger.info("--- Ingestion Summary ---")
        for key, value in summary.as_dict().items():
            logger.info("  %s: %s", key, value)

        if summary.failures:
            logger.warning("%d transcript(s) failed.", len(summary.failures))
            return 1
        return 0
    except TranscriptSourceError as exc:
        logger.error("%s", exc)
        return 1
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
