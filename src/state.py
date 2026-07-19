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
        return {"version": 1, "posted": {}}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("posted", {})
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


def uploads_today(state: dict) -> int:
    """Count reels already posted today (UTC), to respect the daily cap."""
    today = datetime.now(timezone.utc).date().isoformat()
    return sum(
        1
        for entry in state.get("posted", {}).values()
        if str(entry.get("posted_at", "")).startswith(today)
    )
