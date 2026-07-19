"""Turn an Instagram caption into a YouTube title and description.

YouTube rejects titles/descriptions containing angle brackets and caps titles
at 100 characters, so both are sanitised here. The full caption (hashtags
included, since they aid Shorts discovery) becomes the description.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _strip_brackets(text: str) -> str:
    return text.replace("<", "").replace(">", "")


def _is_hashtag_only(line: str) -> bool:
    tokens = line.split()
    return bool(tokens) and all(tok.startswith(("#", "@")) for tok in tokens)


def _format_date(timestamp: str | None) -> str:
    dt = _parse_timestamp(timestamp)
    return (dt or datetime.now(timezone.utc)).strftime("%Y-%m-%d")


def _parse_timestamp(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    try:
        return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    cut = text[:max_length]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip()


def build_title(
    caption: str | None,
    timestamp: str | None,
    max_length: int = 100,
    fallback: str = "Reel",
) -> str:
    caption = (caption or "").strip()
    title = ""

    # Prefer the first line that carries real words (not just hashtags).
    for line in caption.splitlines():
        line = line.strip()
        if line and not _is_hashtag_only(line):
            title = line
            break

    # Otherwise take the first non-empty line at all.
    if not title:
        for line in caption.splitlines():
            if line.strip():
                title = line.strip()
                break

    title = _strip_brackets(title).strip()
    if not title:
        return f"{fallback} – {_format_date(timestamp)}"

    return _truncate(title, max_length)


def build_description(caption: str | None) -> str:
    return _strip_brackets((caption or "").strip())
