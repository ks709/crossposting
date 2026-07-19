# Privacy Policy — Pulse (Instagram → YouTube Crossposter)

_Last updated: 2026-07-19_

Pulse is a personal automation tool operated by a single individual for their
own social media accounts. It reposts the operator's own Instagram Reels to the
operator's own YouTube channel. It is **not** a public product and has no other
end users.

## What data the app accesses

- **YouTube (Google) data.** Using the OAuth scope
  `https://www.googleapis.com/auth/youtube.upload`, the app uploads videos to the
  operator's own YouTube channel via the `videos.insert` endpoint. It sets each
  video's title and description. It does **not** read, list, analyze, or display
  any other YouTube account's data.
- **Instagram data.** Using the operator's own Instagram Graph API access token,
  the app reads the operator's own media (reels, captions, timestamps) and
  downloads the operator's own video files in order to re-upload them.

## How the data is used

The accessed data is used solely to copy the operator's own Instagram Reels to
the operator's own YouTube channel with the same caption. No other use is made of
it.

## Storage and sharing

- The app runs on the operator's own infrastructure (a private GitHub repository
  using GitHub Actions, and the operator's local machine).
- API tokens are stored as **encrypted GitHub Actions secrets** and in a local
  environment file that is never committed to source control.
- A small state file records which reels have already been posted (by ID), to
  avoid duplicates. No video content is retained after upload — downloaded files
  are written to a temporary directory and deleted after each run.
- **No data is sold, shared with third parties, or transferred to anyone.**
  Nothing leaves the operator's own accounts and infrastructure.

## Google API Services User Data Policy

Pulse's use of information received from Google APIs adheres to the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements. Google user data is used only to provide
the single-purpose feature described above and is not used for advertising,
sold, or shared.

## Data retention and deletion

The app stores no personal data beyond the operator's own API tokens (revocable
at any time from the respective Google and Meta account settings) and a list of
already-posted video IDs. Revoking the tokens immediately ends all access.

## Contact

Operator: kanhashaurya05@gmail.com
