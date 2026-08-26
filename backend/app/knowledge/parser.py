"""Transcript discovery and YAML frontmatter parsing."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

TRANSCRIPT_FILENAME = "transcript.md"


class TranscriptSourceError(Exception):
    """Raised when the configured transcript source directory is unusable."""


@dataclass
class TranscriptFile:
    """One discovered episode transcript on disk."""

    path: Path
    source_path: str  # relative to the episodes directory, POSIX style
    file_hash: str  # sha256 of raw bytes
    metadata: dict = field(default_factory=dict)
    content: str = ""  # markdown body below the frontmatter


def _strip_frontmatter(raw: str) -> tuple[dict, str]:
    """Split a transcript into (frontmatter_dict, body).

    Files without frontmatter parse as empty metadata plus full body so that
    malformed episodes are still ingested with path-based traceability.
    """
    if not raw.startswith("---"):
        return {}, raw

    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw

    try:
        parsed = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse YAML frontmatter: %s", exc)
        return {}, parts[2]

    if not isinstance(parsed, dict):
        return {}, parts[2]
    return parsed, parts[2]


def _clean_metadata(metadata: dict) -> dict:
    """Keep known episode fields and coerce values to UI-friendly types."""
    keep = [
        "title",
        "guest",
        "youtube_url",
        "video_id",
        "publish_date",
        "description",
        "duration",
        "duration_seconds",
        "view_count",
        "channel",
        "keywords",
    ]
    cleaned: dict = {}
    for key in keep:
        value = metadata.get(key)
        if value in (None, ""):
            continue
        if key == "keywords":
            cleaned[key] = [str(k) for k in value][:30] if isinstance(value, list) else [str(value)]
        elif key in ("duration_seconds", "view_count"):
            try:
                cleaned[key] = int(float(value))
            except (TypeError, ValueError):
                continue
        else:
            cleaned[key] = str(value).strip()
    return cleaned


def discover_transcripts(episodes_dir: Path) -> list[TranscriptFile]:
    """Recursively find every ``**/transcript.md`` under ``episodes_dir``.

    Raises TranscriptSourceError when the directory does not exist or no
    transcripts can be found, so callers never fail silently.
    """
    if not episodes_dir.exists() or not episodes_dir.is_dir():
        raise TranscriptSourceError(
            "Transcript source directory was not found.\n"
            f"\nExpected location:\n{episodes_dir}\n\n"
            "Please ensure the Lenny's Podcast transcript repository is available "
            "in the knowledge-source directory before running ingestion."
        )

    files: list[TranscriptFile] = []
    for path in sorted(episodes_dir.rglob(TRANSCRIPT_FILENAME)):
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        metadata, body = _strip_frontmatter(text)
        files.append(
            TranscriptFile(
                path=path,
                source_path=path.relative_to(episodes_dir).as_posix(),
                file_hash=hashlib.sha256(raw).hexdigest(),
                metadata=_clean_metadata(metadata),
                content=body,
            )
        )

    if not files:
        raise TranscriptSourceError(
            f"No '{TRANSCRIPT_FILENAME}' files were found under {episodes_dir}."
        )
    return files


def missing_metadata_report(transcripts: list[TranscriptFile]) -> list[str]:
    """Return source paths whose frontmatter lacks a title or guest."""
    return [
        t.source_path
        for t in transcripts
        if not t.metadata.get("title") or not t.metadata.get("guest")
    ]


_TIMESTAMP_PATTERN = re.compile(r"\((\d{1,2}:\d{2}(:\d{2})?)\)")


def normalize_speaker_line(line: str) -> str:
    """Strip inline timestamps like ``Lenny (00:12:34):`` down to the words."""
    return _TIMESTAMP_PATTERN.sub("", line)
