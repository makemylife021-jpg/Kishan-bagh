#!/usr/bin/env bash
# Install the AI video-editing toolchain. Safe to re-run: anything already
# installed is skipped. Works on Linux and macOS (Windows: use WSL).
#
#   bash editing/setup.sh
#
# Installs: FFmpeg, yt-dlp, OpenAI Whisper, Remotion (project deps),
# Hyperframes CLI. Openverse/Freesound need nothing but Python 3.
set -euo pipefail
cd "$(dirname "$0")"
EDITING_DIR="$PWD"

have() { command -v "$1" >/dev/null 2>&1; }
say()  { printf '\n==> %s\n' "$*"; }

# uv is the recommended way to install Python CLI tools in isolated envs.
if ! have uv; then
  say "Installing uv (Python tool installer)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# ---------------------------------------------------------------- FFmpeg
if have ffmpeg && have ffprobe; then
  say "FFmpeg already installed: $(ffmpeg -version | head -1)"
else
  say "Installing FFmpeg"
  if have apt-get; then sudo apt-get update && sudo apt-get install -y ffmpeg
  elif have brew; then brew install ffmpeg
  elif have dnf; then sudo dnf install -y ffmpeg
  else echo "Install FFmpeg from https://ffmpeg.org/download.html" >&2; exit 1; fi
fi

# ---------------------------------------------------------------- yt-dlp
if have yt-dlp; then
  say "yt-dlp already installed ($(yt-dlp --version)); updating"
  uv tool upgrade yt-dlp >/dev/null 2>&1 || yt-dlp -U || true
else
  say "Installing yt-dlp (with recommended extras)"
  uv tool install "yt-dlp[default]"
fi
# YouTube now needs a JavaScript runtime; Node is already required for Remotion.
mkdir -p "$HOME/.config/yt-dlp"
grep -qs -- "--js-runtimes" "$HOME/.config/yt-dlp/config" || echo "--js-runtimes node" >> "$HOME/.config/yt-dlp/config"

# ---------------------------------------------------------------- Whisper
if have whisper; then
  say "Whisper already installed"
else
  say "Installing OpenAI Whisper"
  if have nvidia-smi; then
    uv tool install openai-whisper                      # CUDA build of PyTorch
  else
    uv tool install openai-whisper \
      --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match  # small CPU-only PyTorch
  fi
fi

# ---------------------------------------------------------------- Node check
if ! have node || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 22 ]; then
  echo "Node.js 22+ is required for Remotion and Hyperframes: https://nodejs.org" >&2
  exit 1
fi

# ---------------------------------------------------------------- Remotion
say "Installing Remotion project dependencies (editing/remotion)"
(cd "$EDITING_DIR/remotion" && npm ci --no-audit --no-fund)

# ---------------------------------------------------------------- Hyperframes
if have hyperframes; then
  say "Hyperframes already installed ($(hyperframes --version))"
else
  say "Installing Hyperframes CLI"
  npm install -g hyperframes
fi

say "Done. Run: bash editing/check.sh"
