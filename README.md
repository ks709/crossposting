# Instagram Reels → YouTube crossposter

Automatically reposts your Instagram reels to YouTube (as Shorts) with the same
caption, and slowly drips your **older** reels to YouTube a few per day. Runs
free on GitHub Actions — no PC needs to stay on.

- **New reels** are checked every 2 hours and posted to YouTube.
- **Older reels** are posted oldest-first, ~3 per day, until the backlog is clear.
- Only **public** reels are crossposted. Trial reels aren't on your public
  profile, so the API never returns them until you share them publicly.

---

## How it works

| Piece | What it does |
| --- | --- |
| `src/instagram.py` | Lists your reels and downloads their video files via the Instagram API. |
| `src/youtube.py` | Uploads a video to YouTube using a saved OAuth refresh token. |
| `src/captions.py` | Turns the IG caption into a YouTube title + description. |
| `src/state.py` + `state/state.json` | Remembers which reels are already posted, so nothing is duplicated. |
| `src/main.py` | `new` and `backlog` modes; `--dry-run` to preview. |
| `.github/workflows/` | Cron schedules that run it all in the cloud. |

The daily cap (`max_uploads_per_day: 6` in `config.yaml`) exists because
YouTube's API allows roughly **6 uploads per day** on the default quota.

---

## Setup

You only do this once. It has four parts: Instagram, YouTube/Google, GitHub,
and the audit form. Budget ~30–40 minutes.

### 1. Instagram

1. Make sure your Instagram is a **Business** or **Creator** account
   (Instagram app → Settings → *Account type and tools* → switch — it's free).
2. Go to <https://developers.facebook.com/> → **My Apps** → **Create App**.
3. Add the **Instagram** product → **API setup with Instagram login**.
4. Add yourself as an Instagram tester and accept the invite (in your IG app,
   Settings → *Apps and websites* → Tester invites).
5. Generate a **long-lived access token** for your own account with the
   `instagram_business_basic` permission. Copy the token and your
   **Instagram user ID** — these become the `IG_ACCESS_TOKEN` and `IG_USER_ID`
   secrets.

### 2. YouTube / Google

1. Go to <https://console.cloud.google.com/> → create a project.
2. **APIs & Services → Library** → enable **YouTube Data API v3**.
3. **APIs & Services → OAuth consent screen**:
   - User type **External**.
   - Add yourself under **Test users**.
   - **Publish the app** (set publishing status to *In production*). This
     matters: while the app is in "testing", refresh tokens expire every
     7 days and the automation stops. "In production" but unverified is fine
     for personal use.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID →
   Desktop app**. Download the JSON as `client_secret.json`.
5. On your own machine, mint the refresh token:
   ```bash
   pip install -r requirements.txt
   python scripts/get_youtube_token.py client_secret.json
   ```
   Approve the YouTube permission in the browser. It prints
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, and `YT_REFRESH_TOKEN`.

### 3. The audit (so uploads are public, not private)

Google forces uploads from un-audited API projects to **private**. Until you
pass the audit, every crossposted reel lands as a private video that you can
manually flip to public.

Submit the **YouTube API Services – Audit and Compliance** form (linked from
your project in the Cloud Console). Describe it as a personal tool that
reposts your own Instagram reels to your own channel. Approval is typically
quick for personal use. Once approved, `privacy_status: public` in
`config.yaml` takes effect automatically.

### 4. GitHub

1. Create a new **private** GitHub repo and push this folder to it:
   ```bash
   git init
   git add .
   git commit -m "Initial crossposter"
   git branch -M main
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```
2. Create a **fine-grained personal access token** (GitHub → Settings →
   Developer settings → Fine-grained tokens) scoped to this repo with
   **Secrets: Read and write**. This is the `GH_PAT` secret (it lets the
   weekly job save the refreshed Instagram token).
3. In the repo: **Settings → Secrets and variables → Actions → New repository
   secret** and add all seven:

   | Secret | From |
   | --- | --- |
   | `IG_ACCESS_TOKEN` | Instagram step 5 |
   | `IG_USER_ID` | Instagram step 5 |
   | `YT_CLIENT_ID` | YouTube step 5 |
   | `YT_CLIENT_SECRET` | YouTube step 5 |
   | `YT_REFRESH_TOKEN` | YouTube step 5 |
   | `GH_PAT` | GitHub step 2 |

4. Open `config.yaml` and set `start_date` to today. Reels **before** this date
   are treated as backlog; reels **after** are treated as new.

---

## Running it

- **Preview without posting** (recommended first):
  ```bash
  python -m src.main backlog --dry-run
  python -m src.main new --dry-run
  ```
- **Real run**, locally: copy `.env.example` to `.env`, fill it in, then
  `python -m src.main new`.
- **In the cloud**: the workflows run on their schedules automatically. To test
  immediately, open the repo's **Actions** tab and use **Run workflow** on
  *Crosspost new reels* and *Drip backlog reels*.

---

## Tuning

Everything lives in `config.yaml`:

- `backlog.per_run` and the cron times in `.github/workflows/backlog.yml`
  control the backlog pace (currently 3×/day × 1 = ~3/day).
- `youtube.privacy_status` — set to `unlisted` or `private` if you'd rather
  review before publishing.
- `instagram.exclude_media_ids` — paste any IG media id here to permanently
  skip that reel.

## Notes & limits

- **YouTube quota** caps uploads at ~6/day. The `new` and `backlog` jobs share
  a running daily counter and stop at `max_uploads_per_day`.
- **Copyrighted audio** in a reel may be muted or blocked by YouTube's Content
  ID once on YouTube — nothing this tool can change.
- **Reels over 3 minutes** upload as normal videos, not Shorts.
- The Instagram token auto-refreshes weekly; if that job ever fails, GitHub
  emails you and you can re-run it from the Actions tab.
