"""Try fetching the reels the Instagram API won't serve a media_url for.

The crossposter falls back to scraping a reel's public page when the API
withholds its media_url. That fallback depends on yt-dlp's Instagram extractor
and on the reel being publicly visible, so it is worth confirming before
trusting it. This downloads to a temp directory and uploads nothing.

    python scripts/check_permalink_download.py          # try 3 of them
    python scripts/check_permalink_download.py --limit 10
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import instagram  # noqa: E402
from src.config import load_config  # noqa: E402

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=3, help="how many reels to try")
    args = parser.parse_args()

    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        sys.exit("Missing IG_ACCESS_TOKEN (put it in .env or the environment).")

    cfg = load_config()
    ig = instagram.InstagramClient(
        access_token=token, user_id=os.environ.get("IG_USER_ID", "me")
    )
    reels = ig.list_reels(
        include_product_types=cfg["instagram"]["include_product_types"],
        exclude_ids=cfg["instagram"]["exclude_media_ids"],
    )

    withheld = [r for r in reels if not r.get("media_url")]
    print(f"{len(withheld)} of {len(reels)} reel(s) have no media_url.\n")
    if not withheld:
        return

    ok = 0
    with tempfile.TemporaryDirectory() as tmp:
        for reel in withheld[: args.limit]:
            permalink = reel.get("permalink")
            print(f"{reel['id']}  {permalink or '(no permalink either)'}")
            if not permalink:
                continue
            dest = os.path.join(tmp, f"{reel['id']}.mp4")
            try:
                instagram.download_via_permalink(permalink, dest)
            except Exception as exc:
                print(f"  FAILED: {exc}\n")
                continue
            print(f"  ok: {os.path.getsize(dest) / 1e6:.1f} MB\n")
            ok += 1

    tried = min(args.limit, len(withheld))
    print(f"{ok} of {tried} downloaded. ", end="")
    print(
        "The fallback works — these reels will crosspost on the next runs."
        if ok
        else "The fallback does not work for these reels."
    )


if __name__ == "__main__":
    main()
