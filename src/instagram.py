"""Thin client for the Instagram API with Instagram Login (graph.instagram.com).

Used to list the account's reels, download their video files, and refresh the
long-lived access token.
"""
from __future__ import annotations

import logging
import os
from typing import Iterator, Sequence

import requests

log = logging.getLogger(__name__)

GRAPH_HOST = "https://graph.instagram.com"
DEFAULT_VERSION = "v25.0"
MEDIA_FIELDS = "id,caption,media_type,media_product_type,media_url,permalink,timestamp"


class InstagramError(RuntimeError):
    pass


class InstagramClient:
    def __init__(
        self,
        access_token: str,
        user_id: str = "me",
        version: str = DEFAULT_VERSION,
        session: requests.Session | None = None,
    ) -> None:
        self.access_token = access_token
        self.user_id = user_id or "me"
        self.version = version
        self.session = session or requests.Session()

    def iter_media(self, fields: str = MEDIA_FIELDS, page_size: int = 50) -> Iterator[dict]:
        """Yield every media object on the account, following pagination."""
        url = f"{GRAPH_HOST}/{self.version}/{self.user_id}/media"
        params: dict | None = {
            "fields": fields,
            "limit": page_size,
            "access_token": self.access_token,
        }
        while url:
            resp = self.session.get(url, params=params, timeout=60)
            # 'paging.next' is a fully-formed URL that already carries the query.
            params = None
            if resp.status_code != 200:
                raise InstagramError(
                    f"GET media failed: {resp.status_code} {resp.text}"
                )
            payload = resp.json()
            yield from payload.get("data", [])
            url = payload.get("paging", {}).get("next")

    def list_reels(
        self,
        include_product_types: Sequence[str] = ("REELS",),
        exclude_ids: Sequence[str] = (),
    ) -> list[dict]:
        allowed = set(include_product_types)
        excluded = set(exclude_ids)
        reels = []
        for item in self.iter_media():
            if item.get("media_product_type") not in allowed:
                continue
            if item.get("id") in excluded:
                continue
            reels.append(item)
        log.info("Found %d eligible reel(s) on the account", len(reels))
        return reels

    def download_media(self, media_url: str, dest_path: str) -> str:
        """Stream a reel's video file to disk. CDN URLs expire, so call this
        promptly after listing."""
        with self.session.get(media_url, stream=True, timeout=180) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    if chunk:
                        fh.write(chunk)
        return dest_path

    def download(self, reel: dict, dest_path: str) -> str:
        """Fetch a reel's video, whichever way works.

        The API's media_url is the supported path and stays the default. For
        the reels it withholds a media_url for, fall back to the public page.
        """
        media_url = reel.get("media_url")
        if media_url:
            return self.download_media(media_url, dest_path)

        permalink = reel.get("permalink")
        if not permalink:
            raise InstagramError(
                f"Reel {reel.get('id')} has neither media_url nor permalink"
            )
        log.info(
            "Reel %s has no media_url; falling back to its permalink", reel.get("id")
        )
        return download_via_permalink(permalink, dest_path)


def download_via_permalink(permalink: str, dest_path: str) -> str:
    """Download a reel from its public page instead of the API.

    Instagram withholds media_url for some reels (reels using licensed audio
    are the common case), which leaves the API with no way to hand over the
    file. Scraping the public page via yt-dlp does get it, at the cost of
    depending on yt-dlp's Instagram extractor: it breaks whenever Instagram
    reshapes the page, and it only sees reels that are publicly visible.
    Failures here are expected and handled by the caller, not fatal.
    """
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - dependency is in requirements
        raise InstagramError(
            "yt-dlp is needed to download reels the API withholds a media_url for"
        ) from exc

    # yt-dlp chooses the container, so hand it a template with no extension and
    # move whatever it produced into place afterwards.
    base = os.path.splitext(dest_path)[0]
    opts = {
        "outtmpl": base + ".%(ext)s",
        # Prefer a single progressive mp4 so there is nothing to remux.
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(permalink, download=True)
        except Exception as exc:  # yt-dlp raises a wide range of its own errors
            raise InstagramError(f"Permalink download failed for {permalink}: {exc}") from exc
        produced = ydl.prepare_filename(info)

    if not os.path.exists(produced):
        raise InstagramError(f"Permalink download produced no file for {permalink}")
    if produced != dest_path:
        os.replace(produced, dest_path)
    return dest_path


def refresh_long_lived_token(
    access_token: str, session: requests.Session | None = None
) -> dict:
    """Extend a long-lived token's life by 60 days. Returns the API payload
    containing the new 'access_token' and 'expires_in'."""
    session = session or requests.Session()
    resp = session.get(
        f"{GRAPH_HOST}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": access_token},
        timeout=60,
    )
    if resp.status_code != 200:
        raise InstagramError(
            f"Token refresh failed: {resp.status_code} {resp.text}"
        )
    return resp.json()
