#!/usr/bin/env python3
"""Search and download free sound effects and music for video edits.

Sources
-------
* Openverse (https://openverse.org) - no key needed. Indexes ~600k Freesound
  sound effects, ~650k Jamendo music tracks and ~4M Wikimedia audio files, all
  under Creative Commons licences or public domain.
* Freesound API (https://freesound.org/docs/api/) - optional, used when
  FREESOUND_API_KEY is set (free key: https://freesound.org/apiv2/apply).

Every download is logged with its licence and attribution in CREDITS.md and
credits.jsonl next to the files, so crediting the creators is copy-paste.

Examples
--------
  python editing/tools/media_search.py search "whoosh" --kind sfx
  python editing/tools/media_search.py get "whoosh transition" --kind sfx --count 3
  python editing/tools/media_search.py get "upbeat acoustic" --kind music --min-seconds 60
  python editing/tools/media_search.py get "rain on leaves" --kind sfx --license cc0 --wav
  python editing/tools/media_search.py download <openverse-id>
  python editing/tools/media_search.py get "door slam" --provider freesound   # needs key

Standard library only (plus ffmpeg for --wav).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "assets" / "audio"
OPENVERSE = "https://api.openverse.org/v1"
FREESOUND = "https://freesound.org/apiv2"
# Several CDNs (Freesound's included) reject browser-like user agents from
# cloud IPs, so identify honestly as a tool.
UA = "kishan-bagh-media-search/1.0 (+https://openverse.org; video editing helper)"

LICENSE_TYPES = {
    # commercial use AND modification allowed (cutting/mixing into an edit is a
    # modification, so NoDerivatives tracks are excluded). Safe for monetised posts.
    "commercial": {"license_type": "commercial,modification"},
    "cc0": {"license": "cc0,pdm"},  # no attribution needed
    "any": {},
}


# --------------------------------------------------------------------------- http
def _request(url: str, *, data: bytes | None = None, headers: dict | None = None,
             retries: int = 3) -> bytes:
    hdrs = {"User-Agent": UA, "Accept": "*/*"}
    hdrs.update(headers or {})
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = int(e.headers.get("Retry-After") or 2 ** (attempt + 1))
                time.sleep(min(wait, 30))
                continue
            raise
        except urllib.error.URLError as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise
    raise last  # pragma: no cover


def _json(url: str, **kw) -> dict:
    return json.loads(_request(url, **kw))


# ---------------------------------------------------------------------- openverse
_token_cache: dict = {}


def _openverse_headers() -> dict:
    """Use client credentials when provided (higher rate limits), else anonymous."""
    cid, secret = os.getenv("OPENVERSE_CLIENT_ID"), os.getenv("OPENVERSE_CLIENT_SECRET")
    if not (cid and secret):
        return {}
    if not _token_cache or _token_cache["exp"] < time.time():
        body = urllib.parse.urlencode({"grant_type": "client_credentials",
                                       "client_id": cid, "client_secret": secret}).encode()
        tok = _json(f"{OPENVERSE}/auth_tokens/token/", data=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
        _token_cache.update(tok=tok["access_token"], exp=time.time() + tok["expires_in"] - 60)
    return {"Authorization": f"Bearer {_token_cache['tok']}"}


def _ext(r: dict) -> str:
    ext = (r.get("filetype") or Path(urllib.parse.urlparse(r["url"]).path).suffix.lstrip(".") or "mp3").lower()
    return "mp3" if ext.startswith("mp3") else ext  # Jamendo reports "mp32"


def _ov_item(r: dict) -> dict:
    return {
        "provider": "openverse",
        "id": r["id"],
        "title": r.get("title") or "untitled",
        "creator": r.get("creator") or "unknown",
        "source": r.get("source"),
        "seconds": round((r.get("duration") or 0) / 1000, 1),
        "url": r["url"],
        "ext": _ext(r),
        "license": f"{r.get('license', '').upper()} {r.get('license_version') or ''}".strip(),
        "license_url": r.get("license_url"),
        "page": r.get("foreign_landing_url"),
        "attribution": r.get("attribution"),
    }


def openverse_search(query: str, kind: str, license_: str, n: int,
                     min_s: float, max_s: float, source: str | None) -> list[dict]:
    headers = _openverse_headers()
    # Anonymous requests may ask for at most 20 results per page.
    params = {"q": query, "page_size": 50 if headers else 20}
    params.update(LICENSE_TYPES[license_])
    if source:
        params["source"] = source
    elif kind == "sfx":
        params["source"] = "freesound"
    elif kind == "music":
        params["category"] = "music"
    items: list[dict] = []
    for page in range(1, 4):  # a few pages so duration filters still find enough
        params["page"] = page
        try:
            data = _json(f"{OPENVERSE}/audio/?{urllib.parse.urlencode(params)}", headers=headers)
        except urllib.error.HTTPError as e:
            if page > 1 and e.code in (400, 401, 404):
                break  # ran past the last page / anonymous page limit
            raise
        batch = [_ov_item(r) for r in data.get("results", [])]
        items += [i for i in batch
                  if (not min_s or i["seconds"] >= min_s) and (not max_s or i["seconds"] <= max_s)]
        if len(items) >= n or page >= data.get("page_count", 1):
            break
    return items[:n]


def openverse_get(ov_id: str) -> dict:
    return _ov_item(_json(f"{OPENVERSE}/audio/{ov_id}/", headers=_openverse_headers()))


# ---------------------------------------------------------------------- freesound
FS_LICENSES = {
    "cc0": 'license:"Creative Commons 0"',
    "commercial": '(license:"Creative Commons 0" OR license:"Attribution")',
    "any": "",
}


def _fs_url(path: str, params: dict) -> str:
    key = os.getenv("FREESOUND_API_KEY")
    if key:
        params = {**params, "token": key}
    return f"{FREESOUND}{path}?{urllib.parse.urlencode(params)}"


def freesound_search(query: str, license_: str, n: int, min_s: float, max_s: float) -> list[dict]:
    flt = [FS_LICENSES[license_]] if FS_LICENSES[license_] else []
    if min_s or max_s:
        flt.append(f"duration:[{min_s or 0} TO {max_s or '*'}]")
    params = {"query": query, "page_size": min(max(n, 1) * 3, 150),
              "fields": "id,name,username,license,duration,previews,url",
              "sort": "score"}
    if flt:
        params["filter"] = " ".join(flt)
    data = _json(_fs_url("/search/text/", params))
    out = []
    for r in data.get("results", [])[:n]:
        lic = r.get("license", "")
        short = ("CC0" if "zero" in lic else "CC BY-NC" if "nc" in lic else
                 "CC BY" if "/by/" in lic else lic)
        out.append({
            "provider": "freesound", "id": str(r["id"]), "title": r["name"],
            "creator": r["username"], "source": "freesound",
            "seconds": round(r.get("duration") or 0, 1),
            "url": r["previews"]["preview-hq-mp3"], "ext": "mp3",
            "license": short, "license_url": lic, "page": r["url"],
            "attribution": f"\"{r['name']}\" by {r['username']} ({r['url']}), licensed {short} ({lic})",
        })
    return out


# ---------------------------------------------------------------------- download
def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "audio"


def download(item: dict, out_dir: Path, wav: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{_slug(item['title'])}__{item['provider'][:2]}-{str(item['id'])[:8]}"
    dest = out_dir / f"{name}.{item['ext']}"
    if not dest.exists():
        dest.write_bytes(_request(item["url"]))
    if wav:
        if not shutil.which("ffmpeg"):
            raise SystemExit("ffmpeg not found; install it or drop --wav")
        wav_path = dest.with_suffix(".wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(dest), "-ar", "48000",
                        "-ac", "2", str(wav_path)], check=True)
        dest = wav_path
    _record_credit(item, dest, out_dir)
    return dest


def _record_credit(item: dict, path: Path, out_dir: Path) -> None:
    root = out_dir if out_dir.name not in ("sfx", "music") else out_dir.parent
    rec = {**item, "file": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
           "downloaded": dt.date.today().isoformat()}
    jl = root / "credits.jsonl"
    seen = set()
    if jl.exists():
        seen = {json.loads(l)["file"] for l in jl.read_text().splitlines() if l.strip()}
    if rec["file"] in seen:
        return
    with jl.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    md = root / "CREDITS.md"
    if not md.exists():
        md.write_text("# Audio credits\n\nPaste the relevant lines into your video description.\n\n")
    with md.open("a") as f:
        f.write(f"- `{rec['file']}` - {item['attribution'] or item['title']} "
                f"[{item['license']}]({item['license_url'] or ''}) - source: {item['page'] or item['url']}\n")


# ---------------------------------------------------------------------- cli
def _search(args) -> list[dict]:
    provider = args.provider
    if provider == "auto":
        provider = "freesound" if (args.kind == "sfx" and os.getenv("FREESOUND_API_KEY")) else "openverse"
    if provider == "freesound":
        return freesound_search(args.query, args.license, args.count * 4 if args.cmd == "get" else args.n,
                                args.min_seconds, args.max_seconds)
    n = args.count * 4 if args.cmd == "get" else args.n
    return openverse_search(args.query, args.kind, args.license, n,
                            args.min_seconds, args.max_seconds, args.source)


def _print(items: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps(items, indent=2, ensure_ascii=False))
        return
    if not items:
        print("No results. Try broader words, --license any, or other duration limits.")
    for i, it in enumerate(items, 1):
        print(f"{i:2}. {it['title'][:60]:60} {it['seconds']:7.1f}s  {it['license']:12} "
              f"{it['source']:16} id={it['id']}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("query")
        sp.add_argument("--kind", choices=["sfx", "music", "any"], default="any",
                        help="sfx = Freesound sounds, music = music tracks (Jamendo etc.)")
        sp.add_argument("--license", choices=list(LICENSE_TYPES), default="commercial",
                        help="commercial (default: commercial use + editing allowed), cc0 (no credit needed), any")
        sp.add_argument("--min-seconds", type=float, default=0)
        sp.add_argument("--max-seconds", type=float, default=0)
        sp.add_argument("--source", help="Openverse source, e.g. freesound, jamendo, wikimedia_audio, ccmixter")
        sp.add_argument("--provider", choices=["auto", "openverse", "freesound"], default="auto")

    s = sub.add_parser("search", help="list matches")
    common(s)
    s.add_argument("-n", type=int, default=10)
    s.add_argument("--json", action="store_true")

    g = sub.add_parser("get", help="search and download the best matches")
    common(g)
    g.add_argument("--count", type=int, default=1)
    g.add_argument("--out", type=Path)
    g.add_argument("--wav", action="store_true", help="also convert to 48 kHz WAV")

    d = sub.add_parser("download", help="download Openverse ids")
    d.add_argument("ids", nargs="+")
    d.add_argument("--out", type=Path, default=DEFAULT_OUT / "misc")
    d.add_argument("--wav", action="store_true")

    args = p.parse_args(argv)

    if args.cmd == "search":
        _print(_search(args), args.json)
        return 0

    if args.cmd == "download":
        for i in args.ids:
            print(download(openverse_get(i), args.out, args.wav))
        return 0

    out = args.out or DEFAULT_OUT / {"sfx": "sfx", "music": "music"}.get(args.kind, "misc")
    got = 0
    for item in _search(args):
        try:
            path = download(item, out, args.wav)
        except (urllib.error.URLError, subprocess.CalledProcessError) as e:
            print(f"  skip {item['title'][:40]!r}: {e}", file=sys.stderr)
            continue
        print(f"{path}  [{item['license']}] {item['seconds']}s  by {item['creator']}")
        got += 1
        if got >= args.count:
            break
    if not got:
        print("Nothing downloaded (no results, or every file host refused).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
