#!/usr/bin/env bash
# Quick end-to-end test of every video-editing tool. Prints a checklist.
#
#   bash editing/check.sh            # full test (renders + transcription, ~1 min)
#
# Test outputs go to out/check/ (git-ignored).
set -uo pipefail
cd "$(dirname "$0")/.."
REPO="$PWD"
OUT="$REPO/out/check"; rm -rf "$OUT"; mkdir -p "$OUT"
export PATH="$HOME/.local/bin:$PATH"

# Cloud sessions ship Chrome Headless Shell here; on a normal computer the
# tools find or download their own browser.
HS=/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell
[ -x "$HS" ] && export HYPERFRAMES_BROWSER_PATH="${HYPERFRAMES_BROWSER_PATH:-$HS}"

declare -a RESULTS
pass() { RESULTS+=("✅ $1 — $2"); }
fail() { RESULTS+=("❌ $1 — $2"); }
log()  { echo "--- $*"; }

# 1. FFmpeg: synthesize a clip with a tone, then probe it
log FFmpeg
if ffmpeg -v error -y -f lavfi -i testsrc2=size=1080x1920:rate=30:duration=2 \
     -f lavfi -i sine=frequency=440:duration=2 -c:v libx264 -pix_fmt yuv420p -c:a aac \
     -shortest "$OUT/ffmpeg.mp4" 2>"$OUT/ffmpeg.log" &&
   [ "$(ffprobe -v error -show_entries stream=codec_type -of csv=p=0 "$OUT/ffmpeg.mp4" | sort | tr '\n' ' ')" = "audio video " ]; then
  pass FFmpeg "$(ffmpeg -version | head -1 | cut -d' ' -f1-3); encoded H.264+AAC test clip"
else fail FFmpeg "see $OUT/ffmpeg.log"; fi

# 2. yt-dlp: download a CC-licensed track and extract audio with FFmpeg
log yt-dlp
URL="https://prod-1.storage.jamendo.com/?trackid=1670486&format=mp32"
if yt-dlp -q --no-warnings -x --audio-format wav -o "$OUT/ytdlp.%(ext)s" "$URL" >"$OUT/ytdlp.log" 2>&1 &&
   [ -s "$OUT/ytdlp.wav" ]; then
  pass yt-dlp "v$(yt-dlp --version); downloaded + converted audio"
else fail yt-dlp "v$(yt-dlp --version 2>/dev/null); download failed, see $OUT/ytdlp.log"; fi

# 3. Whisper: transcribe a short speech clip to SRT with word timings
log Whisper
SPEECH="$OUT/speech.wav"
ffmpeg -v error -y -i editing/tools/testdata/speech-cc0.mp3 -ar 16000 -ac 1 "$SPEECH"
if whisper "$SPEECH" --model base --language en --word_timestamps True --output_format srt \
     --output_dir "$OUT" >"$OUT/whisper.log" 2>&1 && [ -s "$OUT/speech.srt" ]; then
  pass Whisper "base model; SRT: \"$(sed -n 3p "$OUT/speech.srt" | cut -c1-50)…\""
else fail Whisper "see $OUT/whisper.log"; fi

# 4. Remotion: render 1 second of the starter composition
log Remotion
if (cd editing/remotion && npx remotion render HelloWorld "$OUT/remotion.mp4" --frames=0-29) >"$OUT/remotion.log" 2>&1 &&
   [ -s "$OUT/remotion.mp4" ]; then
  pass Remotion "v$(node -p "require('./editing/remotion/node_modules/remotion/package.json').version"); rendered 1080p test"
else fail Remotion "see $OUT/remotion.log"; fi

# 5. Hyperframes: lint + render the starter composition
log Hyperframes
if (cd editing/hyperframes && hyperframes lint . && hyperframes render -o "$OUT/hyperframes.mp4" </dev/null) \
     >"$OUT/hyperframes.log" 2>&1 && [ -s "$OUT/hyperframes.mp4" ]; then
  pass Hyperframes "v$(hyperframes --version); rendered 1080x1920 test"
else fail Hyperframes "see $OUT/hyperframes.log"; fi

# 6/7. Openverse music + Freesound SFX via the media tool
log Openverse
if python3 editing/tools/media_search.py get "acoustic guitar" --kind music --out "$OUT/audio/music" \
     >"$OUT/openverse.log" 2>&1; then
  pass "Openverse (music)" "$(head -1 "$OUT/openverse.log" | sed "s#$OUT/##")"
else fail "Openverse (music)" "see $OUT/openverse.log"; fi

log Freesound
if python3 editing/tools/media_search.py search "whoosh" --kind sfx -n 3 >"$OUT/freesound-search.log" 2>&1 &&
   [ -s "$OUT/freesound-search.log" ]; then
  if python3 editing/tools/media_search.py get "whoosh" --kind sfx --max-seconds 3 --out "$OUT/audio/sfx" \
       >"$OUT/freesound.log" 2>&1; then
    pass "Freesound SFX" "search + download OK ($(head -1 "$OUT/freesound.log" | sed "s#$OUT/##" | cut -c1-60))"
  else
    fail "Freesound SFX" "search OK, but freesound.org refused the download from this network (see $OUT/freesound.log)"
  fi
else fail "Freesound SFX" "search failed, see $OUT/freesound-search.log"; fi

echo; echo "========== Video editing toolchain =========="
printf '%s\n' "${RESULTS[@]}"
