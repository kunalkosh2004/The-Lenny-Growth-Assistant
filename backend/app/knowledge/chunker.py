"""Transcript cleaning and chunking.

Strategy: normalize whitespace, drop structural markdown headers, then split
into chunks of roughly ``chunk_target_chars`` characters on paragraph (then
sentence) boundaries with a small character overlap so ideas that straddle a
split stay retrievable from at least one chunk.
"""

from __future__ import annotations

import logging
import re

from app.knowledge.parser import normalize_speaker_line

logger = logging.getLogger(__name__)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def clean_text(body: str) -> str:
    """Normalize raw transcript markdown into plain flowing text."""
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith("#"):  # structural headers, not content
            continue
        lines.append(normalize_speaker_line(stripped))
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def chunk_text(
    body: str,
    target_chars: int = 1200,
    overlap_chars: int = 150,
) -> list[str]:
    """Split cleaned transcript text into overlapping chunks.

    Returns at least one chunk for any non-empty input. Very short transcripts
    produce a single chunk; overlap never duplicates the whole previous chunk.
    """
    cleaned = clean_text(body)
    if not cleaned:
        return []

    paragraphs = _split_paragraphs(cleaned)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("\n\n".join(current).strip())
        tail = chunks[-1][-overlap_chars:] if chunks and overlap_chars > 0 else ""
        # Start the next chunk with a small tail of the previous one.
        current = [tail] if len(chunks[-1]) > overlap_chars else ([chunks[-1]] if chunks else [])
        current_len = sum(len(part) + 2 for part in current)

    for paragraph in paragraphs:
        if len(paragraph) > target_chars:
            # Oversized paragraph: split by sentence.
            sentences = _SENTENCE_END.split(paragraph)
            for sentence in sentences:
                if current_len + len(sentence) + 2 > target_chars and current:
                    flush()
                current.append(sentence)
                current_len += len(sentence) + 2
            continue

        if current_len + len(paragraph) + 2 > target_chars and current:
            flush()
        current.append(paragraph)
        current_len += len(paragraph) + 2

    if current:
        final = "\n\n".join(current).strip()
        # Avoid a trailing chunk that is only the carried-over overlap.
        if chunks and final == chunks[-1]:
            pass
        elif chunks and final.endswith(chunks[-1]):
            remainder = final[: -len(chunks[-1])].strip()
            if remainder:
                chunks.append(remainder)
        else:
            chunks.append(final)

    return [c for c in chunks if c]
