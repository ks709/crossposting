"""YouTube Data API v3 upload helper.

Builds an authenticated client from a long-lived OAuth refresh token (no
browser needed at run time) and performs a resumable video upload. Vertical
videos up to 3 minutes are auto-classified as Shorts by YouTube.
"""
from __future__ import annotations

import logging
import random
import time

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

log = logging.getLogger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
RETRIABLE_STATUS = {500, 502, 503, 504}


def build_youtube(client_id: str, client_secret: str, refresh_token: str):
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(
    youtube,
    file_path: str,
    title: str,
    description: str,
    privacy_status: str = "public",
    category_id: str = "22",
    made_for_kids: bool = False,
) -> str:
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": str(category_id),
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": bool(made_for_kids),
        },
    }
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = _execute_resumable(request)
    return response["id"]


def _execute_resumable(request, max_retries: int = 5) -> dict:
    response = None
    retry = 0
    while response is None:
        try:
            _status, response = request.next_chunk()
            if response is not None and "id" not in response:
                raise RuntimeError(f"Unexpected upload response: {response}")
        except HttpError as exc:
            if exc.resp.status not in RETRIABLE_STATUS:
                raise
            retry = _backoff(retry, max_retries, exc)
        except (OSError, ConnectionError) as exc:
            retry = _backoff(retry, max_retries, exc)
    return response


def _backoff(retry: int, max_retries: int, exc: Exception) -> int:
    retry += 1
    if retry > max_retries:
        raise exc
    sleep = min(2 ** retry, 60) + random.random()
    log.warning("Retriable upload error (%s); retry %d in %.1fs", exc, retry, sleep)
    time.sleep(sleep)
    return retry
