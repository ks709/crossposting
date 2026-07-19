"""One-time helper: mint a YouTube refresh token for the crossposter.

Run this once on your own machine after downloading your OAuth client secret
from Google Cloud:

    pip install google-auth-oauthlib
    python scripts/get_youtube_token.py client_secret.json

It opens a browser, you approve the YouTube upload permission, and it prints
the three values to save as GitHub secrets.
"""
from __future__ import annotations

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: python scripts/get_youtube_token.py <client_secret.json>")

    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    if not creds.refresh_token:
        sys.exit(
            "No refresh token returned. Remove this app's access at "
            "https://myaccount.google.com/permissions and run again."
        )

    print("\n=== Save these as GitHub repository secrets ===")
    print("YT_CLIENT_ID     =", creds.client_id)
    print("YT_CLIENT_SECRET =", creds.client_secret)
    print("YT_REFRESH_TOKEN =", creds.refresh_token)


if __name__ == "__main__":
    main()
