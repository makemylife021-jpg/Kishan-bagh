"""Publish a video as an Instagram Reel through the official Instagram Graph API.

Requirements:
  * An Instagram Business or Creator account linked to a Facebook Page.
  * IG_USER_ID      - the Instagram account id (not the username).
  * IG_ACCESS_TOKEN - a long-lived token with instagram_basic and
                      instagram_content_publish permissions.
  * The video must be reachable at a PUBLIC https URL (Instagram downloads it).

Usage:
    python -m instagram_autopilot.publish_instagram --video-url https://... --caption-file out/x.caption.txt
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import requests

GRAPH = os.environ.get("IG_GRAPH_URL", "https://graph.facebook.com/v21.0")


def log(msg: str) -> None:
    print(f"[publish] {msg}", flush=True)


def _check(resp: requests.Response) -> dict:
    data = resp.json() if resp.content else {}
    if resp.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Graph API error {resp.status_code}: {data.get('error', data)}")
    return data


def publish_reel(video_url: str, caption: str, user_id: str, token: str,
                 share_to_feed: bool = True, timeout_s: int = 600) -> str:
    log("creating media container")
    container = _check(requests.post(
        f"{GRAPH}/{user_id}/media",
        data={"media_type": "REELS", "video_url": video_url, "caption": caption,
              "share_to_feed": str(share_to_feed).lower(), "access_token": token},
        timeout=60,
    ))["id"]

    deadline = time.time() + timeout_s
    while True:
        status = _check(requests.get(
            f"{GRAPH}/{container}",
            params={"fields": "status_code,status", "access_token": token}, timeout=30,
        ))
        code = status.get("status_code")
        log(f"processing status: {code}")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram could not process the video: {status}")
        if time.time() > deadline:
            raise TimeoutError("timed out waiting for Instagram to process the video")
        time.sleep(10)

    media_id = _check(requests.post(
        f"{GRAPH}/{user_id}/media_publish",
        data={"creation_id": container, "access_token": token}, timeout=60,
    ))["id"]
    log(f"published! media id {media_id}")
    return media_id


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video-url", required=True, help="public https URL of the mp4")
    ap.add_argument("--caption-file", type=Path)
    ap.add_argument("--caption", default="")
    ap.add_argument("--no-feed", action="store_true", help="post to Reels tab only")
    args = ap.parse_args()

    user_id = os.environ.get("IG_USER_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not user_id or not token:
        sys.exit("Set IG_USER_ID and IG_ACCESS_TOKEN environment variables first.")
    caption = args.caption_file.read_text(encoding="utf-8") if args.caption_file else args.caption
    publish_reel(args.video_url, caption[:2200], user_id, token, share_to_feed=not args.no_feed)


if __name__ == "__main__":
    main()
