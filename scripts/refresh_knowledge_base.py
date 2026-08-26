#!/usr/bin/env python3
"""Refresh the knowledge base: only re-ingest changed or missing transcripts."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(PROJECT_ROOT)

from scripts.ingest_transcripts import main

if __name__ == "__main__":
    sys.exit(main())
