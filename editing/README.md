# AI video editing toolkit

Everything Claude needs to cut, caption, animate and score videos for this channel.

| Tool | What it's for | Where |
|---|---|---|
| **FFmpeg** | Cutting, joining, resizing, mixing audio, burning in captions | system (`ffmpeg`, `ffprobe`) |
| **yt-dlp** | Downloading source clips and audio from links (YouTube, Instagram, direct files…) | `yt-dlp` |
| **Whisper** | Transcripts and caption files (SRT/VTT/JSON, word-level timing) in 99 languages, including Hindi | `whisper` |
| **Remotion** | Videos written in React: templates, animated captions, data-driven reels | `editing/remotion/` |
| **Hyperframes** | Videos written in HTML/CSS/GSAP: motion graphics, titles, overlays, 450+ ready-made blocks | `editing/hyperframes/` |
| **Openverse** | Free music and sound search (Jamendo, Freesound, Wikimedia), with licence and credit text | `editing/tools/media_search.py` |
| **Freesound** | Free sound-effects library (~600k sounds) | `editing/tools/media_search.py` |

## Set up / check

```bash
bash editing/setup.sh   # installs whatever is missing (safe to re-run)
bash editing/check.sh   # quick test of every tool, prints a ✅/❌ checklist
```

## Everyday commands

```bash
# Download a clip (best mp4) or just its audio
yt-dlp -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]" -o "in/%(title)s.%(ext)s" URL
yt-dlp -x --audio-format wav -o "in/%(title)s.%(ext)s" URL

# Transcribe + captions (use --language hi for Hindi; small/medium = more accurate, slower)
whisper in/clip.mp4 --model small --language en --word_timestamps True --output_format all --output_dir out/

# Burn captions into a vertical reel
ffmpeg -i in/clip.mp4 -vf "subtitles=out/clip.srt:force_style='FontSize=14,Alignment=2,MarginV=60'" -c:a copy out/captioned.mp4

# Sound effects and music (licence + attribution saved to editing/assets/audio/CREDITS.md)
python3 editing/tools/media_search.py search "whoosh" --kind sfx
python3 editing/tools/media_search.py get "whoosh transition" --kind sfx --max-seconds 3 --count 3
python3 editing/tools/media_search.py get "calm acoustic" --kind music --min-seconds 60
python3 editing/tools/media_search.py get "rain" --kind sfx --license cc0 --wav   # no credit needed

# Remotion: live preview studio / render
cd editing/remotion && npm run dev
cd editing/remotion && npx remotion render HelloWorld ../../out/video.mp4

# Hyperframes: preview / check / render
cd editing/hyperframes && hyperframes preview
cd editing/hyperframes && hyperframes lint . && hyperframes render -o ../../out/video.mp4
```

### Licences for music and SFX

By default `media_search.py` only returns audio that allows **commercial use and editing**
(CC0, CC BY, CC BY-SA), so it is safe for monetised posts. CC BY and CC BY-SA need a
credit line: copy it from `editing/assets/audio/CREDITS.md` into the post description.
Use `--license cc0` when you don't want to credit anyone.

Optional keys (set as environment variables):

- `FREESOUND_API_KEY`: searches Freesound directly, with more filters. Free key from
  <https://freesound.org/apiv2/apply>.
- `OPENVERSE_CLIENT_ID` / `OPENVERSE_CLIENT_SECRET`: higher Openverse rate limits. Register at
  <https://api.openverse.org/v1/#tag/auth/operation/register>.

## Notes for cloud (claude.ai) sessions

- Use the **"Kishan-bagh media tools"** cloud environment. It allows Openverse, Freesound,
  the Whisper model server, Jamendo and Wikimedia.
- Remotion and Hyperframes use the preinstalled Chromium at `/opt/pw-browsers`
  (set in `remotion.config.ts`, and through `HYPERFRAMES_BROWSER_PATH`).
- **YouTube** downloads don't work from the cloud sandbox: YouTube serves video from
  per-server `*.googlevideo.com` hosts, which a fixed allowlist can't cover, and it blocks
  datacenter IPs. Run yt-dlp on your own computer, or upload the clip.
- **Freesound** blocks downloads from some cloud IPs (it returns 403). Search still works, and
  downloads work from a home connection. In the cloud, use `--kind music` / Jamendo, or try
  again later.

## Agent skills included

- `editing/remotion/.claude/skills/`: official Remotion skills (captions, rendering, best practices…)
- `.claude/skills/hyperframes*`, `media-use`, …: official Hyperframes skills
- `.claude/skills/instagram-video-autopilot`: this repo's reel pipeline
