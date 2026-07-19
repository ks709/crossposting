"""Refresh the long-lived Instagram token and print the new one to stdout.

Called weekly by the refresh-ig-token workflow, which captures stdout and
writes it back to the IG_ACCESS_TOKEN repository secret. All logging goes to
stderr so stdout contains only the token.
"""
from __future__ import annotations

import logging
import os
import sys

from . import instagram


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        sys.exit("Missing IG_ACCESS_TOKEN")

    payload = instagram.refresh_long_lived_token(token)
    new_token = payload.get("access_token")
    if not new_token:
        sys.exit(f"Refresh returned no access_token: {payload}")

    logging.getLogger("refresh").info(
        "Token refreshed; expires in %s seconds", payload.get("expires_in")
    )
    print(new_token)  # stdout -> captured by the workflow


if __name__ == "__main__":
    main()
