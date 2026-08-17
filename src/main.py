"""Entry point: crosspost Instagram reels to YouTube.

Usage:
    python -m src.main new        # post recently-published reels
    python -m src.main backlog    # drip-post the oldest un-posted reel(s)
    python -m src.main new --dry-run   # show what would happen, upload nothing
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

from . import captions, instagram, youtube
from . import state as state_mod
from .config import DEFAULT_PATH, load_config

log = logging.getLogger("crosspost")

STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "state", "state.json")

# How many times a reel's download may fail before it is given up on. Reels
# without a media_url are fetched by scraping their public page, which fails
# for transient reasons often enough to be worth retrying, but not forever.
MAX_DOWNLOAD_ATTEMPTS = 3

# Spare candidates to pull into a run beyond the upload budget, so a reel
# that fails to download costs an attempt rather than the run's posting slot.
EXTRA_DOWNLOAD_ATTEMPTS = 2

try:  # optional convenience for local runs
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing required environment variable: {name}")
    return value


def _parse_ig_timestamp(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None


def _last_posted_at(state: dict) -> datetime | None:
    """Timestamp of the most recent successful upload, for the minimum-gap check."""
    times: list[datetime] = []
    for entry in state.get("posted", {}).values():
        raw = entry.get("posted_at")
        if not raw:
            continue
        try:
            times.append(datetime.fromisoformat(raw))
        except ValueError:
            continue
    return max(times) if times else None


def _select_candidates(
    reels, state, start_date, mode
) -> tuple[list[tuple[datetime, dict]], list[dict]]:
    """Return (postable candidates oldest-first, reels with no downloadable file)."""
    candidates = []
    unpostable = []
    for reel in reels:
        if state_mod.is_posted(state, reel["id"]):
            continue
        ts = _parse_ig_timestamp(reel.get("timestamp"))
        if ts is None:
            log.warning("Skipping reel %s: unparseable timestamp", reel.get("id"))
            continue
        is_new = ts >= start_date
        if (mode == "new") != is_new:
            continue
        # Instagram withholds media_url for some reels (those using licensed
        # audio are the common case). Those are still fetchable from their
        # public permalink, so they stay in the queue; what gets dropped is
        # reels with no source at all, and reels whose downloads have failed
        # MAX_DOWNLOAD_ATTEMPTS times.
        #
        # Dropping them HERE rather than skipping inside the upload loop below
        # is what keeps the queue moving: selection is deterministic and capped
        # at one reel per run, so a reel that can never be fetched would
        # otherwise be re-picked and re-skipped on every future run, stalling
        # everything behind it while each run still exited 0.
        if not reel.get("media_url") and not reel.get("permalink"):
            unpostable.append(reel)
            continue
        if state_mod.download_attempts(state, reel["id"]) >= MAX_DOWNLOAD_ATTEMPTS:
            unpostable.append(reel)
            continue
        candidates.append((ts, reel))
    candidates.sort(key=lambda pair: pair[0])  # oldest first
    return candidates, unpostable


def run(mode: str, dry_run: bool) -> None:
    cfg = load_config()
    state = state_mod.load_state(STATE_PATH)

    start_date = datetime.fromisoformat(cfg["start_date"]).replace(tzinfo=timezone.utc)

    # Minimum spacing between uploads. Checked up front, before touching the
    # Instagram API, so a skipped run costs nothing. It reads the whole posting
    # history, so it applies across BOTH modes — a backlog run can't fire right
    # after a new-reel run, and vice versa.
    min_gap = timedelta(hours=float(cfg.get("min_gap_hours") or 0))
    last_post = _last_posted_at(state)
    if min_gap and last_post is not None:
        elapsed = datetime.now(timezone.utc) - last_post
        if elapsed < min_gap:
            log.info(
                "Last upload was %.2fh ago; minimum gap is %.1fh (%.2fh to go). Nothing to do.",
                elapsed.total_seconds() / 3600,
                min_gap.total_seconds() / 3600,
                (min_gap - elapsed).total_seconds() / 3600,
            )
            return

    ig = instagram.InstagramClient(
        access_token=_require_env("IG_ACCESS_TOKEN"),
        user_id=os.environ.get("IG_USER_ID", "me"),
    )
    reels = ig.list_reels(
        include_product_types=cfg["instagram"]["include_product_types"],
        exclude_ids=cfg["instagram"]["exclude_media_ids"],
    )

    candidates, unpostable = _select_candidates(reels, state, start_date, mode)
    if unpostable:
        # Count only: this fires on every run, and the ids are just noise until
        # there is nothing left to post. They get listed in that case below.
        log.warning(
            "Passing over %d %s reel(s) with no downloadable video.",
            len(unpostable),
            mode,
        )

    # Apply the daily safety cap and per-run limit.
    remaining = cfg["backlog"]["max_uploads_per_day"] - state_mod.uploads_today(state)
    if remaining <= 0:
        log.info("Daily upload cap reached; nothing to do.")
        return
    if mode == "backlog":
        remaining = min(remaining, cfg["backlog"]["per_run"])
    if min_gap:
        # A second upload in the same run would land seconds after the first,
        # so cap every run at one whenever a gap is enforced. (This is what
        # previously let "new" mode post several reels in the same minute.)
        remaining = min(remaining, 1)
    # Downloads can fail — the permalink fallback is scraping, and scraping
    # breaks — so pull in a couple of spares past the upload budget and stop as
    # soon as the budget is met. Dry runs list exactly what would be posted.
    upload_budget = remaining
    if not dry_run:
        remaining += EXTRA_DOWNLOAD_ATTEMPTS
    candidates = candidates[:remaining]

    if not candidates:
        if unpostable:
            log.warning(
                "No postable %s reels: all %d remaining have no downloadable "
                "video, or have failed %d download attempts (%s).",
                mode,
                len(unpostable),
                MAX_DOWNLOAD_ATTEMPTS,
                ", ".join(reel["id"] for reel in unpostable),
            )
        else:
            log.info("No %s reels to post.", mode)
        return

    uploaded = 0
    yt = None
    for ts, reel in candidates:
        title = captions.build_title(
            reel.get("caption"),
            reel.get("timestamp"),
            cfg["title"]["max_length"],
            cfg["title"]["empty_fallback"],
        )
        description = captions.build_description(reel.get("caption"))
        source = "media_url" if reel.get("media_url") else "permalink"
        log.info(
            "[%s] reel %s (%s, via %s) -> %r",
            mode,
            reel["id"],
            reel.get("timestamp"),
            source,
            title,
        )

        if dry_run:
            continue

        with tempfile.TemporaryDirectory() as tmp:
            video_path = os.path.join(tmp, f"{reel['id']}.mp4")
            try:
                ig.download(reel, video_path)
            except Exception as exc:
                # Don't let one un-fetchable reel take the whole run down: bank
                # the failure so it is eventually skipped, and try the next one.
                attempts = state_mod.record_download_failure(state, reel["id"], str(exc))
                state_mod.save_state(STATE_PATH, state)
                log.warning(
                    "Download failed for reel %s (attempt %d of %d): %s",
                    reel["id"],
                    attempts,
                    MAX_DOWNLOAD_ATTEMPTS,
                    exc,
                )
                continue

            if yt is None:
                yt = youtube.build_youtube(
                    _require_env("YT_CLIENT_ID"),
                    _require_env("YT_CLIENT_SECRET"),
                    _require_env("YT_REFRESH_TOKEN"),
                )
            video_id = youtube.upload_video(
                yt,
                video_path,
                title,
                description,
                privacy_status=cfg["youtube"]["privacy_status"],
                category_id=cfg["youtube"]["category_id"],
                made_for_kids=cfg["youtube"]["made_for_kids"],
            )

        state_mod.clear_download_failure(state, reel["id"])
        state_mod.mark_posted(state, reel["id"], video_id, mode)
        state_mod.save_state(STATE_PATH, state)  # persist after each success
        uploaded += 1
        log.info("Uploaded https://youtu.be/%s", video_id)
        if uploaded >= upload_budget:
            break

    # Selecting reels and then uploading none means something skipped silently.
    # Exit non-zero so the workflow's failure step files an alert issue instead
    # of the run going green with nothing posted.
    if not dry_run and uploaded == 0:
        sys.exit(
            f"Selected {len(candidates)} {mode} reel(s) but uploaded none; "
            "treating as a failed run."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Crosspost Instagram reels to YouTube.")
    parser.add_argument("mode", choices=["new", "backlog"])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be posted without downloading or uploading.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if not os.path.exists(DEFAULT_PATH):
        sys.exit(f"Config not found at {DEFAULT_PATH}")

    run(args.mode, args.dry_run)


if __name__ == "__main__":
    main()
