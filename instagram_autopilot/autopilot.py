"""Queue runner: take the oldest script in content/queue, render it, and
(optionally) publish it, then move the script to content/posted.

    python -m instagram_autopilot.autopilot render          # render next script, write out/next.env
    python -m instagram_autopilot.autopilot publish URL     # publish the rendered reel from URL
    python -m instagram_autopilot.autopilot done            # move the script to content/posted
    python -m instagram_autopilot.autopilot status          # show queue length

The GitHub Actions workflow calls these steps in order and hosts the mp4 in
between (see .github/workflows/instagram-autopilot.yml).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from .make_video import build_reel
from .publish_instagram import publish_reel

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "content" / "queue"
POSTED = ROOT / "content" / "posted"
OUT = ROOT / "out"
STATE = OUT / "next.env"


def next_script() -> Path | None:
    items = sorted(QUEUE.glob("*.json"))
    return items[0] if items else None


def read_state() -> dict:
    if not STATE.exists():
        sys.exit("nothing rendered yet; run `render` first")
    return dict(line.split("=", 1) for line in STATE.read_text().splitlines() if "=" in line)


def cmd_render() -> None:
    script_path = next_script()
    if not script_path:
        print("queue is empty - add scripts to content/queue/")
        STATE.parent.mkdir(exist_ok=True)
        STATE.write_text("EMPTY=1\n")
        return
    music = os.environ.get("REEL_MUSIC")
    video, caption = build_reel(json.loads(script_path.read_text(encoding="utf-8")), OUT,
                                Path(music) if music else None)
    STATE.write_text(f"SCRIPT={script_path}\nVIDEO={video}\nCAPTION={caption}\n")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as fh:
            fh.write(f"video={video}\ncaption={caption}\nscript={script_path}\n")


def cmd_publish(url: str) -> None:
    st = read_state()
    user_id, token = os.environ.get("IG_USER_ID"), os.environ.get("IG_ACCESS_TOKEN")
    if not user_id or not token:
        sys.exit("IG_USER_ID / IG_ACCESS_TOKEN not set - skipping publish")
    caption = Path(st["CAPTION"]).read_text(encoding="utf-8")
    publish_reel(url, caption[:2200], user_id, token)


def cmd_done() -> None:
    st = read_state()
    src = Path(st["SCRIPT"])
    POSTED.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), POSTED / src.name)
    print(f"moved {src.name} -> content/posted/")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "render":
        cmd_render()
    elif cmd == "publish" and len(sys.argv) == 3:
        cmd_publish(sys.argv[2])
    elif cmd == "done":
        cmd_done()
    elif cmd == "status":
        print(f"{len(list(QUEUE.glob('*.json')))} script(s) in queue")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
