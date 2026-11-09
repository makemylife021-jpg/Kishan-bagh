---
name: instagram-video-autopilot
description: Fully automatic Instagram Reel creation and posting. Use when the user asks to make, plan, batch, schedule or post Instagram Reels / short vertical videos ("make 7 reels about X", "fill my Instagram queue", "post a reel today", "render this script as a video"). Writes reel scripts into content/queue, renders 1080x1920 videos with free text-to-speech, stock footage and burned-in captions, and publishes them through the Instagram Graph API (manually or via the daily GitHub Actions workflow).
---

# Instagram Video Autopilot

Pipeline: **topic → script JSON → voice-over + visuals + captions → 9:16 MP4 → Instagram Reel**.

```
content/queue/*.json   ← you (Claude) write scripts here
instagram_autopilot/   ← make_video.py, publish_instagram.py, autopilot.py
.github/workflows/instagram-autopilot.yml  ← posts one reel per day, oldest first
content/posted/        ← scripts move here after posting
```

## 1. Writing scripts (the main job)

When the user gives a niche/topic, create one file per reel in `content/queue/`,
named `NNN-short-slug.json` with the next free 3-digit number (order = posting order).

```json
{
  "title": "3 morning habits that change your day",
  "voice": "en-US-AndrewNeural",
  "scenes": [
    {"text": "Hook sentence that stops the scroll.", "keywords": "stock footage search words"},
    {"text": "Point one.", "keywords": "..."}
  ],
  "caption": "Caption text with a question to drive comments.",
  "hashtags": ["#niche", "#topic", "#reels"]
}
```

Rules for good reels:
- **Scene 1 is the hook** - under 10 words, a bold claim, question or number.
- 4-7 scenes, each one sentence of 6-16 words. Total 20-45 seconds (~2.6 words/sec). Never exceed 90 s (API limit).
- Last scene is a call to action (follow / save / comment).
- `keywords`: 1-3 concrete visual nouns for Pexels (e.g. "coffee cup", "city night"), not abstract ideas.
- `caption`: 1-3 lines, ≤ 2200 chars total with hashtags. 3-8 relevant hashtags.
- `voice`: any edge-tts voice. Hindi: `hi-IN-MadhurNeural` / `hi-IN-SwaraNeural`; Indian English: `en-IN-PrabhatNeural` / `en-IN-NeerjaNeural`; US: `en-US-AndrewNeural` / `en-US-AvaNeural`. Match the voice to the script language.
- No copyrighted lyrics, no medical/financial claims presented as fact, no impersonation.

After writing, run `python -m instagram_autopilot.autopilot status` and tell the user how many are queued.

## 2. Rendering a preview

```bash
pip install -r instagram_autopilot/requirements.txt   # also needs ffmpeg on PATH
python -m instagram_autopilot.make_video content/queue/001-xyz.json -o out/
```

Output: `out/<slug>.mp4` and `out/<slug>.caption.txt`.
- With `PEXELS_API_KEY` set → real stock video backgrounds; without → animated gradients.
- `--music path.mp3` (or `REEL_MUSIC`) mixes royalty-free music at low volume.
- If TTS has no internet access it falls back to silent audio and logs a warning - tell the user.
- Check a frame: `ffmpeg -ss 3 -i out/x.mp4 -frames:v 1 frame.png`.

## 3. Publishing

Instagram fetches the video from a **public https URL**, then publishes it.

- **Automatic (recommended):** the workflow runs daily, renders the oldest queued script,
  hosts the mp4 on the repo's `media` branch (repo must be public), posts it, and moves the
  script to `content/posted/`. Trigger it now from the Actions tab → *Instagram Reel Autopilot* → *Run workflow*.
- **Manual:** `python -m instagram_autopilot.publish_instagram --video-url <public-url> --caption-file out/x.caption.txt`

Required GitHub secrets (Settings → Secrets and variables → Actions):

| Secret | What |
|---|---|
| `IG_USER_ID` | Instagram Business/Creator account id |
| `IG_ACCESS_TOKEN` | Long-lived token with `instagram_basic`, `instagram_content_publish` |
| `PEXELS_API_KEY` | optional, free at pexels.com/api |

Never print, commit or ask the user to paste tokens into chat - they go only in GitHub secrets or local env vars.

## Troubleshooting

- `Graph API error ... (#10) / (#200)` → token missing `instagram_content_publish` or account not Business/Creator.
- Status `ERROR` while processing → video URL not public, or video >90 s / wrong format.
- Workflow says queue empty → write more scripts (section 1).
- Private repo → replace the "Host video" workflow step with an upload to S3/R2/any public host and pass that URL.
