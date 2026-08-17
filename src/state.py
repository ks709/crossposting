"""Persistent record of which Instagram reels have been crossposted.

The state file maps each Instagram media id to the YouTube video it became, so
we never post the same reel twice. It is committed back to the repo by the
GitHub Actions workflows after every run.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {"version": 1, "posted": {}, "download_failures": {}}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("posted", {})
    data.setdefault("download_failures", {})
    return data


def save_state(path: str, state: dict) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def is_posted(state: dict, media_id: str) -> bool:
    return media_id in state.get("posted", {})


def mark_posted(state: dict, media_id: str, yt_video_id: str, mode: str) -> None:
    state.setdefault("posted", {})[media_id] = {
        "yt_video_id": yt_video_id,
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
    }


def download_attempts(state: dict, media_id: str) -> int:
    """How many times fetching this reel's video has already failed."""
    entry = state.get("download_failures", {}).get(media_id, {})
    return int(entry.get("attempts", 0))


def record_download_failure(state: dict, media_id: str, error: str) -> int:
    """Note a failed download and return the new attempt count.

    Reels are retried a few times before being given up on, so a transient
    failure costs a slot rather than the reel, while a reel that genuinely
    cannot be fetched stops being re-picked and stalling the queue.
    """
    failures = state.setdefault("download_failures", {})
    entry = failures.setdefault(media_id, {"attempts": 0})
    entry["attempts"] = int(entry.get("attempts", 0)) + 1
    entry["last_error"] = error[:500]
    entry["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
    return entry["attempts"]


def clear_download_failure(state: dict, media_id: str) -> None:
    """Forget a reel's failures once it has been fetched successfully."""
    state.get("download_failures", {}).pop(media_id, None)


def uploads_today(state: dict) -> int:
    """Count reels already posted today (UTC), to respect the daily cap."""
    today = datetime.now(timezone.utc).date().isoformat()
    return sum(
        1
        for entry in state.get("posted", {}).values()
        if str(entry.get("posted_at", "")).startswith(today)
    )
