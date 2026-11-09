"""Render a vertical (1080x1920) Instagram Reel from a script JSON file.

Script format (see content/queue/*.json):
{
  "title": "...",
  "voice": "en-US-AndrewNeural",          # optional, any edge-tts voice
  "scenes": [{"text": "...", "keywords": "stock search words"}, ...],
  "caption": "...",
  "hashtags": ["#a", "#b"]
}

Per scene: free Microsoft Edge text-to-speech -> background (Pexels stock clip
when PEXELS_API_KEY is set, otherwise an animated gradient) -> burned-in
subtitles. Scenes are joined, optional background music is mixed in.

Usage:
    python -m instagram_autopilot.make_video content/queue/001-morning-habits.json -o out/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
DEFAULT_VOICE = "en-US-AndrewNeural"
FONT_CANDIDATES = [
    os.environ.get("REEL_FONT", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
GRADIENTS = [
    ("0x0f2027", "0x2c5364"), ("0x42275a", "0x734b6d"), ("0x141e30", "0x243b55"),
    ("0x3a1c71", "0xd76d77"), ("0x093028", "0x237a57"), ("0x232526", "0x414345"),
]


def log(msg: str) -> None:
    print(f"[make_video] {msg}", flush=True)


def run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr[-3000:])
        raise RuntimeError(f"command failed: {' '.join(cmd[:4])} ...")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "reel"


def media_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def find_font(size: int) -> ImageFont.FreeTypeFont:
    for f in FONT_CANDIDATES:
        if f and Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


# ---------------------------------------------------------------- voice-over
async def _edge_tts(text: str, voice: str, dest: Path) -> None:
    import edge_tts  # imported lazily so --help works without it

    await edge_tts.Communicate(text, voice).save(str(dest))


def synth_voice(text: str, voice: str, dest: Path) -> Path:
    """Free TTS via edge-tts. Falls back to silence if the service is unreachable."""
    try:
        asyncio.run(_edge_tts(text, voice, dest))
        if dest.exists() and dest.stat().st_size > 0:
            return dest
    except Exception as exc:  # network blocked, bad voice, ...
        log(f"TTS failed ({exc.__class__.__name__}); using silent audio for this scene")
    seconds = max(2.5, len(text.split()) / 2.6)  # ~156 words per minute
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", f"{seconds:.2f}", "-q:a", "9", str(dest)])
    return dest


# ---------------------------------------------------------------- background
def pexels_clip(keywords: str, dest: Path) -> Path | None:
    key = os.environ.get("PEXELS_API_KEY")
    if not key or not keywords:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            params={"query": keywords, "orientation": "portrait", "per_page": 10, "size": "medium"},
            headers={"Authorization": key}, timeout=20,
        )
        r.raise_for_status()
        videos = r.json().get("videos", [])
        random.shuffle(videos)
        for v in videos:
            files = [f for f in v.get("video_files", [])
                     if f.get("height", 0) >= 1280 and f.get("file_type") == "video/mp4"]
            if not files:
                continue
            best = min(files, key=lambda f: abs(f["height"] - 1920))
            with requests.get(best["link"], stream=True, timeout=60) as resp:
                resp.raise_for_status()
                with open(dest, "wb") as fh:
                    for chunk in resp.iter_content(1 << 16):
                        fh.write(chunk)
            return dest
    except Exception as exc:
        log(f"Pexels lookup for '{keywords}' failed: {exc}")
    return None


# ---------------------------------------------------------------- subtitles
def subtitle_png(text: str, dest: Path) -> Path:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = find_font(76)
    lines = textwrap.wrap(text, width=20)
    line_h = 96
    block_h = line_h * len(lines)
    y = int(H * 0.62) - block_h // 2
    pad = 36
    widths = [draw.textlength(l, font=font) for l in lines]
    box_w = int(max(widths) + pad * 2)
    draw.rounded_rectangle(
        [(W - box_w) // 2, y - pad, (W + box_w) // 2, y + block_h + pad // 2],
        radius=36, fill=(0, 0, 0, 150),
    )
    for line, lw in zip(lines, widths):
        draw.text(((W - lw) / 2, y), line, font=font, fill="white",
                  stroke_width=4, stroke_fill="black")
        y += line_h
    img.save(dest)
    return dest


# ---------------------------------------------------------------- scenes
def render_scene(idx: int, scene: dict, voice: str, work: Path) -> Path:
    text = scene["text"].strip()
    audio = synth_voice(text, voice, work / f"s{idx}.mp3")
    dur = media_duration(audio) + 0.35
    subs = subtitle_png(text, work / f"s{idx}.png")
    clip = pexels_clip(scene.get("keywords", ""), work / f"s{idx}_bg.mp4")
    out = work / f"s{idx}.mp4"

    if clip:
        bg_in = ["-stream_loop", "-1", "-i", str(clip)]
        bg_filter = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                     f"crop={W}:{H},fps={FPS},eq=brightness=-0.08[bg]")
    else:
        c1, c2 = random.choice(GRADIENTS)
        bg_in = ["-f", "lavfi", "-i",
                 f"gradients=s={W}x{H}:c0={c1}:c1={c2}:x0=0:y0=0:x1={W}:y1={H}:speed=0.02:r={FPS}"]
        bg_filter = "[0:v]format=yuv420p[bg]"

    run([
        "ffmpeg", "-y", *bg_in, "-loop", "1", "-i", str(subs), "-i", str(audio),
        "-filter_complex", f"{bg_filter};[bg][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
        "-map", "[v]", "-map", "2:a", "-t", f"{dur:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
        "-af", "apad", str(out),
    ])
    return out


def build_reel(script: dict, out_dir: Path, music: Path | None = None) -> tuple[Path, Path]:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required (apt install ffmpeg / brew install ffmpeg)")
    scenes = script.get("scenes") or []
    if not scenes:
        raise SystemExit("script has no scenes")
    voice = script.get("voice") or DEFAULT_VOICE
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(script.get("title", "reel"))
    final = out_dir / f"{slug}.mp4"

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        parts = []
        for i, sc in enumerate(scenes):
            log(f"scene {i + 1}/{len(scenes)}: {sc['text'][:50]}")
            parts.append(render_scene(i, sc, voice, work))
        listing = work / "list.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        joined = work / "joined.mp4"
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c", "copy", str(joined)])

        if music and music.exists():
            run(["ffmpeg", "-y", "-i", str(joined), "-stream_loop", "-1", "-i", str(music),
                 "-filter_complex", "[1:a]volume=0.12[m];[0:a][m]amix=inputs=2:duration=first[a]",
                 "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                 "-movflags", "+faststart", str(final)])
        else:
            run(["ffmpeg", "-y", "-i", str(joined), "-c", "copy",
                 "-movflags", "+faststart", str(final)])

    caption = script.get("caption", "").strip()
    tags = " ".join(script.get("hashtags", []))
    caption_file = out_dir / f"{slug}.caption.txt"
    caption_file.write_text(f"{caption}\n\n{tags}".strip() + "\n", encoding="utf-8")

    dur = media_duration(final)
    if dur > 90:
        log(f"warning: reel is {dur:.0f}s; Instagram Reels must be 3-90s via the API")
    log(f"done -> {final} ({dur:.1f}s)")
    return final, caption_file


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", type=Path, help="script JSON file")
    ap.add_argument("-o", "--out", type=Path, default=Path("out"))
    ap.add_argument("--music", type=Path, default=os.environ.get("REEL_MUSIC") or None,
                    help="optional background music file (royalty-free)")
    args = ap.parse_args()
    script = json.loads(args.script.read_text(encoding="utf-8"))
    build_reel(script, args.out, args.music)


if __name__ == "__main__":
    main()
