# Kishan-bagh

## Instagram Reel Autopilot

Fully automatic Instagram video creation and posting:

1. **Write** - Claude (via the `instagram-video-autopilot` skill in `.claude/skills/`) writes reel scripts into `content/queue/`.
   Just ask: *"Make 7 reels about organic farming tips in Hindi"*.
2. **Render** - `instagram_autopilot/make_video.py` turns each script into a 1080×1920 reel: free Microsoft Edge
   text-to-speech voice-over, Pexels stock footage (or animated gradients), and big burned-in captions.
3. **Post** - a GitHub Actions workflow runs every day, renders the next script and publishes it as a Reel with the
   official Instagram Graph API.

### One-time setup

1. Make your Instagram a **Business or Creator** account and link it to a Facebook Page.
2. In [Meta for Developers](https://developers.facebook.com/) create an app, add *Instagram Graph API*, and generate a
   **long-lived access token** with `instagram_basic` and `instagram_content_publish`. Note your Instagram **user id**.
3. In this repo: **Settings → Secrets and variables → Actions** add:
   - `IG_USER_ID`
   - `IG_ACCESS_TOKEN`
   - `PEXELS_API_KEY` (optional, free at <https://www.pexels.com/api/>)
4. The repo must be **public** so Instagram can download the video from the `media` branch
   (or change the hosting step in `.github/workflows/instagram-autopilot.yml`).
5. Actions tab → *Instagram Reel Autopilot* → **Run workflow** to test. After that it posts daily at 12:17 UTC.

### Run locally

```bash
pip install -r instagram_autopilot/requirements.txt   # plus ffmpeg
python -m instagram_autopilot.make_video content/queue/001-morning-habits.json -o out/
```
