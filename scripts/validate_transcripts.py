#!/usr/bin/env python3
"""Validate the local Lenny's Podcast transcript source directory."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(PROJECT_ROOT)

from app.core.config import get_settings
from app.knowledge.parser import (
    TranscriptSourceError,
    discover_transcripts,
    missing_metadata_report,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    episodes_dir = Path(settings.transcripts_dir)

    try:
        transcripts = discover_transcripts(episodes_dir)
    except TranscriptSourceError as exc:
        logger.error("%s", exc)
        return 1

    logger.info("Transcripts discovered: %d", len(transcripts))
    logger.info("Directory: %s", episodes_dir)

    missing = missing_metadata_report(transcripts)
    if missing:
        logger.warning("Episodes with missing title or guest: %d", len(missing))
        for path in missing[:10]:
            logger.warning("  - %s", path)
    else:
        logger.info("All episodes have title and guest metadata.")

    sizes = [t.path.stat().st_size for t in transcripts]
    logger.info("Transcript sizes: min=%d, max=%d, avg=%d bytes",
                min(sizes), max(sizes), sum(sizes) // len(sizes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
