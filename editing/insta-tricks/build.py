#!/usr/bin/env python3
"""Build the "3 hidden Instagram tricks" reel from script.txt (+ your voice).

  python3 build.py                       # preview: timing estimated from the script
  python3 build.py --voice my-voice.m4a  # final: Whisper times every word to your voice
  python3 build.py --voice my-voice.m4a --render

Writes index.html and compositions/*.html. Every caption, the 1-2-3 tracker and
each scene's animation beat are timed from the words, so re-running after a new
recording re-syncs everything.
"""
from __future__ import annotations

import argparse
import difflib
import html
import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1080, 1920
LIME = "#C8FF2E"
BG = "#07110A"

NUM_WORDS = {"three": "3", "one": "1", "two": "2", "fifteen": "15"}


# ----------------------------------------------------------------- script
def parse_script(path: Path) -> list[dict]:
    segs, cur = [], None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"\[(\w+)\]", line)
        if m:
            cur = {"id": m.group(1), "words": []}
            segs.append(cur)
            continue
        for tok in line.split():
            beat = tok.startswith("^")
            tok = tok.lstrip("^")
            key = "*" in tok
            text = tok.replace("*", "")
            cur["words"].append({"text": text, "key": key, "beat": beat, "seg": cur["id"]})
    return segs


def norm(t: str) -> str:
    t = re.sub(r"[^a-z0-9']", "", t.lower())
    return NUM_WORDS.get(t, t)


# ----------------------------------------------------------------- timing
def estimate_times(segs: list[dict]) -> None:
    t = 0.3
    for si, seg in enumerate(segs):
        if si:
            t += 0.45
        for w in seg["words"]:
            dur = 0.17 + 0.036 * len(w["text"])
            w["start"], w["end"] = round(t, 3), round(t + dur, 3)
            t += dur + 0.03
            if w["text"][-1] in ",;":
                t += 0.16
            elif w["text"][-1] in ".?!":
                t += 0.32


def whisper_times(segs: list[dict], voice: Path) -> None:
    tj = HERE / "transcript.json"
    out = HERE / ".whisper"
    out.mkdir(exist_ok=True)
    subprocess.run(["whisper", str(voice), "--model", "small.en", "--language", "en",
                    "--word_timestamps", "True", "--output_format", "json",
                    "--output_dir", str(out)], check=True)
    data = json.loads((out / (voice.stem + ".json")).read_text())
    heard = [{"text": w["word"].strip(), "start": w["start"], "end": w["end"]}
             for s in data["segments"] for w in s.get("words", [])]
    tj.write_text(json.dumps(heard, indent=1))
    words = [w for s in segs for w in s["words"]]
    a, b = [norm(w["text"]) for w in words], [norm(h["text"]) for h in heard]
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            words[blk.a + k]["start"] = heard[blk.b + k]["start"]
            words[blk.a + k]["end"] = heard[blk.b + k]["end"]
    # words Whisper heard differently: interpolate between known neighbours
    known = [i for i, w in enumerate(words) if "start" in w]
    pct = 100 * len(known) / len(words)
    print(f"Matched {len(known)}/{len(words)} script words ({pct:.0f}%) to the recording.")
    if pct < 70:
        print("WARNING: the recording differs a lot from script.txt - edit script.txt to match what you said, then re-run.")
    if not known:
        raise SystemExit("Could not match the recording to script.txt")
    for i, w in enumerate(words):
        if "start" in w:
            continue
        prev = max((k for k in known if k < i), default=None)
        nxt = min((k for k in known if k > i), default=None)
        t0 = words[prev]["end"] if prev is not None else max(0, words[nxt]["start"] - 0.4)
        t1 = words[nxt]["start"] if nxt is not None else t0 + 0.4
        span = (nxt if nxt is not None else i + 1) - (prev if prev is not None else i - 1) - 1
        pos = i - (prev if prev is not None else i - 1)
        w["start"] = round(t0 + (t1 - t0) * (pos - 1) / max(span, 1), 3)
        w["end"] = round(t0 + (t1 - t0) * pos / max(span, 1), 3)


# ----------------------------------------------------------------- captions
def chunks(words: list[dict]) -> list[list[dict]]:
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= 4 or cur[-1]["text"][-1] in ".,?!;"
                    or (w["key"] and any(x["key"] for x in cur))
                    or cur[-1]["seg"] != w["seg"]):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def key_size(text: str) -> int:
    return max(96, min(170, int(800 / (0.68 * len(text)))))


def build_captions(words: list[dict], total: float) -> tuple[str, list[float]]:
    groups, tweens, pops = [], [], []
    cs = chunks(words)
    for ci, c in enumerate(cs):
        start = max(0, c[0]["start"] - 0.06)
        end = cs[ci + 1][0]["start"] - 0.06 if ci + 1 < len(cs) else min(total, c[-1]["end"] + 0.9)
        end = min(end, c[-1]["end"] + 1.2)
        k = next((i for i, w in enumerate(c) if w["key"]), None)
        rows = [c] if k is None else [c[:k], [c[k]], c[k + 1:]]
        row_html = []
        for ri, row in enumerate(rows):
            if not row:
                continue
            cls = "cap-key" if (k is not None and ri == 1) else ("cap-solo" if k is None else "cap-small")
            spans = []
            for w in row:
                wid = f"w{words.index(w)}"
                style = f' style="font-size:{key_size(w["text"])}px"' if cls == "cap-key" else ""
                spans.append(f'<span id="{wid}" class="cap-w"{style}>{html.escape(w["text"].rstrip(".,;"))}</span>')
                t = round(w["start"] - start, 3)
                if cls == "cap-key":
                    tweens.append(f'tl.fromTo("#{wid}", {{ opacity: 0, scale: 1.7 }}, {{ opacity: 1, scale: 1, duration: 0.22, ease: "back.out(2.4)" }}, {round(start + t, 3)});')
                    pops.append(round(w["start"] - 0.02, 3))
                else:
                    tweens.append(f'tl.fromTo("#{wid}", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.14, ease: "power2.out" }}, {round(start + t, 3)});')
            row_html.append(f'<div class="cap-row {cls}">{" ".join(spans)}</div>')
        groups.append(f'    <div id="cap{ci}" class="clip cap" data-start="{start:.3f}" '
                      f'data-duration="{end - start:.3f}" data-track-index="0">{"".join(row_html)}</div>')
    doc = f'''<template>
  <style>
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    .cap {{ position: absolute; left: 90px; right: 150px; top: 1090px; height: 250px;
      display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }}
    .cap-row {{ font-family: Montserrat, sans-serif; color: #fff; line-height: 1;
      text-shadow: 0 4px 18px rgba(0,0,0,.85), 0 0 2px rgba(0,0,0,.9); }}
    .cap-w {{ display: inline-block; }}
    .cap-small {{ font-size: 58px; font-weight: 800; letter-spacing: -0.01em; color: #F2F2F2; }}
    .cap-solo {{ font-size: 76px; font-weight: 900; letter-spacing: -0.015em; }}
    .cap-key {{ font-weight: 900; letter-spacing: -0.03em; color: {LIME}; margin: -6px 0 2px;
      text-shadow: 0 0 28px rgba(200,255,46,.55), 0 0 64px rgba(200,255,46,.25), 0 6px 18px rgba(0,0,0,.8); }}
  </style>
  <div id="root" data-composition-id="captions" data-width="{W}" data-height="{H}">
{chr(10).join(groups)}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {chr(10).join("    " + t for t in tweens).strip()}
    window.__timelines["captions"] = tl;
  </script>
</template>
'''
    return doc, pops


# ----------------------------------------------------------------- scenes
PHONE_CSS = """
    .phone { position: absolute; left: 300px; top: 330px; width: 480px; height: 760px; border-radius: 64px;
      background: #0E0F12; border: 10px solid #2A2D33; box-shadow: 0 30px 80px rgba(0,0,0,.6), 0 0 0 2px #3A3F47, 0 0 120px rgba(200,255,46,.12);
      overflow: hidden; font-family: Inter, sans-serif; color: #EDEDED; }
    .notch { position: absolute; left: 175px; top: 14px; width: 110px; height: 30px; border-radius: 16px; background: #000; }
    .bar { position: absolute; left: 0; right: 0; top: 60px; height: 70px; padding: 0 26px; display: flex; align-items: center;
      gap: 16px; font-weight: 700; font-size: 30px; border-bottom: 1px solid #22252B; }
    .avatar { width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, #8E7CFF, #FF7AB6); flex: none; }
    .row { position: absolute; left: 18px; right: 18px; height: 74px; border-radius: 18px; padding: 0 20px;
      display: flex; align-items: center; justify-content: space-between; font-size: 28px; font-weight: 600; }
    .hl { position: absolute; border-radius: 18px; border: 4px solid """ + LIME + """; box-shadow: 0 0 24px rgba(200,255,46,.6); opacity: 0; }
    .label { position: absolute; left: 0; right: 0; text-align: center; font-family: Montserrat, sans-serif; font-weight: 900;
      color: """ + LIME + """; text-shadow: 0 0 24px rgba(200,255,46,.5); }
"""


def scene(sid: str, dur: float, beats: list[float], body: str, css: str, anim: str) -> str:
    subs = {f"{{b{i}}}": str(round(t, 3)) for i, t in enumerate(beats)}
    subs["{d}"] = str(round(dur, 3))
    for k, v in subs.items():
        anim = anim.replace(k, v)
    if re.search(r"\{b\d\}", anim):
        raise SystemExit(f"{sid}: script.txt is missing a ^beat marker this scene needs")
    return f'''<template>
  <style>
    #root {{ position: absolute; inset: 0; }}
{PHONE_CSS if "phone" in body else ""}{css}
  </style>
  <div id="root" data-composition-id="{sid}" data-width="{W}" data-height="{H}">
{body}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {anim}
    window.__timelines["{sid}"] = tl;
  </script>
</template>
'''


def scene_hook(dur, beats):
    body = f'''    <div id="hook-glow"></div>
    <div id="hook-num">3</div>
    <div id="hook-tag">HIDDEN TRICKS</div>
    <div id="hook-sub">INSTAGRAM</div>'''
    css = f'''    #hook-glow {{ position: absolute; left: 140px; top: 260px; width: 800px; height: 800px; border-radius: 50%;
      background: radial-gradient(circle, rgba(200,255,46,.35) 0%, rgba(200,255,46,0) 65%); }}
    #hook-num {{ position: absolute; left: 0; right: 0; top: 330px; text-align: center; font: 900 500px/1 Montserrat, sans-serif;
      color: {LIME}; text-shadow: 0 0 60px rgba(200,255,46,.6); letter-spacing: -0.05em; }}
    #hook-sub {{ position: absolute; left: 90px; right: 150px; top: 850px; text-align: center; font: 800 54px/1 Montserrat, sans-serif;
      color: #fff; letter-spacing: 0.32em; }}
    #hook-tag {{ position: absolute; left: 90px; right: 150px; top: 920px; text-align: center; font: 900 84px/1 Montserrat, sans-serif;
      color: #fff; letter-spacing: -0.01em; }}'''
    anim = '''tl.fromTo("#hook-num", { scale: 0.9, rotation: -4 }, { scale: 1, rotation: 0, duration: 0.5, ease: "back.out(2)" }, 0);
    tl.fromTo("#hook-glow", { scale: 0.7, opacity: 0.4 }, { scale: 1.1, opacity: 1, duration: {d}, ease: "sine.inOut" }, 0);
    tl.fromTo("#hook-sub", { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }, 0.25);
    tl.fromTo("#hook-tag", { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }, 0.4);'''
    return scene("hook", dur, beats, body, css, anim)


def scene_trick1(dur, beats):
    body = '''    <div class="phone" id="t1-phone">
      <div class="notch"></div>
      <div class="bar"><span>&lsaquo;</span><span>Chat details</span></div>
      <div id="t1-head" class="row" style="top:150px;height:120px;justify-content:flex-start;gap:18px">
        <div class="avatar" style="width:72px;height:72px"></div><div><div style="font-size:30px;font-weight:800">alex.k</div>
        <div style="font-size:28px;color:#8A8F98;margin-top:6px">View profile</div></div></div>
      <div class="row" style="top:300px">Mute messages <span class="tog" id="t1-tog-a"><i></i></span></div>
      <div class="row" id="t1-rr" style="top:380px">Read receipts <span class="tog on" id="t1-tog"><i id="t1-knob"></i></span></div>
      <div class="row" style="top:460px">Vanish mode <span style="color:#8A8F98">Off</span></div>
      <div class="row" style="top:540px">Privacy &amp; safety <span style="color:#8A8F98">&rsaquo;</span></div>
      <div class="hl" id="t1-hl1" style="left:14px;top:146px;width:432px;height:128px"></div>
      <div class="hl" id="t1-hl2" style="left:14px;top:376px;width:432px;height:82px"></div>
      <div id="t1-seen">Seen &#10007;</div>
    </div>'''
    css = f'''    .tog {{ position: relative; width: 78px; height: 44px; border-radius: 22px; background: #3A3F47; }}
    .tog i {{ position: absolute; left: 4px; top: 4px; width: 36px; height: 36px; border-radius: 50%; background: #fff; }}
    #t1-tog {{ background: {LIME}; }}
    #t1-knob {{ left: 38px; }}
    #t1-seen {{ position: absolute; left: 0; right: 0; top: 640px; text-align: center; font: 800 30px/1 Inter, sans-serif; color: #FF5B5B; opacity: 0; }}'''
    anim = '''tl.fromTo("#t1-phone", { y: 160, opacity: 0, rotation: 4 }, { y: 0, opacity: 1, rotation: 0, duration: 0.5, ease: "power3.out" }, 0);
    tl.fromTo("#t1-hl1", { opacity: 0, scale: 1.08 }, { opacity: 1, scale: 1, duration: 0.2, ease: "power2.out" }, {b0});
    tl.to("#t1-hl1", { opacity: 0, duration: 0.2 }, {b1} - 0.25);
    tl.fromTo("#t1-hl2", { opacity: 0, scale: 1.08 }, { opacity: 1, scale: 1, duration: 0.2, ease: "power2.out" }, {b1} - 0.2);
    tl.fromTo("#t1-knob", { x: 0 }, { x: -34, duration: 0.22, ease: "power2.inOut" }, {b1});
    tl.fromTo("#t1-tog", { backgroundColor: "#C8FF2E" }, { backgroundColor: "#3A3F47", duration: 0.22 }, {b1});
    tl.fromTo("#t1-seen", { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.3, ease: "back.out(2)" }, {b1} + 0.5);'''
    return scene("trick1", dur, beats, body, css, anim)


def scene_trick2(dur, beats):
    cards = "".join(f'<div class="card" id="t2-c{i}" style="top:{150 + i * 190}px"><div class="avatar"></div>'
                    f'<div class="ln"></div><div class="tag" id="t2-tag{i}">{t}</div></div>'
                    for i, t in enumerate(["2 min ago", "15 min ago", "1 h ago"]))
    body = f'''    <div class="phone" id="t2-phone">
      <div class="notch"></div>
      <div class="bar" id="t2-logo" style="font-size:30px;font-weight:800">Instagram <span style="font-size:28px">&#9662;</span></div>
      {cards}
      <div id="t2-menu"><div class="mi" id="t2-fol">Following</div><div class="mi">Favorites</div></div>
      <div class="hl" id="t2-hl" style="left:18px;top:62px;width:250px;height:66px"></div>
    </div>'''
    css = '''    .card { position: absolute; left: 22px; right: 22px; height: 170px; border-radius: 22px; background: #1A1C21; }
    .card .avatar { position: absolute; left: 20px; top: 20px; }
    .card .ln { position: absolute; left: 80px; top: 32px; width: 180px; height: 18px; border-radius: 9px; background: #30343B; }
    .tag { position: absolute; left: 20px; bottom: 22px; font: 700 28px/1 Inter, sans-serif; color: #8A8F98; }
    #t2-menu { position: absolute; left: 30px; top: 132px; width: 280px; border-radius: 20px; background: #24272E;
      box-shadow: 0 20px 50px rgba(0,0,0,.6); overflow: hidden; opacity: 0; }
    .mi { height: 72px; padding: 0 24px; display: flex; align-items: center; font: 700 26px/1 Inter, sans-serif; }
    #t2-fol { background: rgba(200,255,46,0); }'''
    anim = '''tl.fromTo("#t2-phone", { y: 160, opacity: 0, rotation: -4 }, { y: 0, opacity: 1, rotation: 0, duration: 0.5, ease: "power3.out" }, 0);
    tl.fromTo("#t2-hl", { opacity: 0 }, { opacity: 1, duration: 0.15 }, {b0} - 0.1);
    tl.to("#t2-hl", { opacity: 0, duration: 0.15 }, {b0} + 0.35);
    tl.fromTo("#t2-menu", { opacity: 0, y: -20 }, { opacity: 1, y: 0, duration: 0.25, ease: "power2.out" }, {b0});
    tl.fromTo("#t2-fol", { backgroundColor: "rgba(200,255,46,0)", color: "#EDEDED" }, { backgroundColor: "rgba(200,255,46,1)", color: "#07110A", duration: 0.15 }, {b1});
    tl.to("#t2-menu", { opacity: 0, duration: 0.2 }, {b1} + 0.45);
    tl.fromTo(["#t2-c0", "#t2-c1", "#t2-c2"], { y: 40, opacity: 0.75 }, { y: 0, opacity: 1, duration: 0.35, stagger: 0.08, ease: "power3.out" }, {b1} + 0.5);
    tl.fromTo(["#t2-tag0", "#t2-tag1", "#t2-tag2"], { color: "#8A8F98" }, { color: "#C8FF2E", duration: 0.2, stagger: 0.08 }, {b1} + 0.7);'''
    return scene("trick2", dur, beats, body, css, anim)


def scene_trick3(dur, beats):
    body = '''    <div class="phone" id="t3-phone">
      <div class="notch"></div>
      <div class="bar"><div class="avatar"></div><span>alex.k</span></div>
      <div class="bub them" style="top:170px">are we still on for tomorrow?</div>
      <div class="bub me" id="t3-bub"><span id="t3-typo">See you tomorow!</span><span id="t3-fix">See you tomorrow!</span></div>
      <div id="t3-edited">Edited</div>
      <div id="t3-menu"><div class="mi">Reply</div><div class="mi">Copy</div><div class="mi" id="t3-edit">Edit</div><div class="mi" style="color:#FF5B5B">Unsend</div></div>
      <div id="t3-badge">15 MIN</div>
    </div>'''
    css = f'''    .bub {{ position: absolute; max-width: 330px; padding: 20px 24px; border-radius: 28px; font: 600 28px/1.25 Inter, sans-serif; }}
    .them {{ left: 24px; background: #24272E; }}
    .me {{ right: 24px; top: 300px; background: #7B5CFF; color: #fff; width: 300px; height: 76px; }}
    #t3-bub span {{ position: absolute; left: 24px; top: 22px; white-space: nowrap; }}
    #t3-fix {{ opacity: 0; }}
    #t3-edited {{ position: absolute; right: 30px; top: 384px; font: 600 28px/1 Inter, sans-serif; color: #8A8F98; opacity: 0; }}
    #t3-menu {{ position: absolute; right: 24px; top: 392px; width: 240px; border-radius: 20px; background: #24272E;
      box-shadow: 0 20px 50px rgba(0,0,0,.6); overflow: hidden; opacity: 0; }}
    .mi {{ height: 66px; padding: 0 24px; display: flex; align-items: center; font: 700 28px/1 Inter, sans-serif; }}
    #t3-badge {{ position: absolute; left: 140px; top: 560px; width: 200px; height: 80px; border-radius: 40px; background: {LIME};
      color: {BG}; font: 900 36px/80px Montserrat, sans-serif; text-align: center; box-shadow: 0 0 40px rgba(200,255,46,.6); opacity: 0; }}'''
    anim = '''tl.fromTo("#t3-phone", { y: 160, opacity: 0, rotation: 4 }, { y: 0, opacity: 1, rotation: 0, duration: 0.5, ease: "power3.out" }, 0);
    tl.fromTo("#t3-bub", { scale: 1 }, { scale: 1.07, duration: 0.25, ease: "power2.out" }, {b0} - 0.1);
    tl.fromTo("#t3-menu", { opacity: 0, y: -16 }, { opacity: 1, y: 0, duration: 0.22, ease: "power2.out" }, {b0} + 0.05);
    tl.fromTo("#t3-edit", { backgroundColor: "rgba(200,255,46,0)", color: "#EDEDED" }, { backgroundColor: "rgba(200,255,46,1)", color: "#07110A", duration: 0.15 }, {b1});
    tl.to("#t3-menu", { opacity: 0, duration: 0.2 }, {b1} + 0.4);
    tl.to("#t3-bub", { scale: 1, duration: 0.25, ease: "power2.out" }, {b1} + 0.4);
    tl.fromTo("#t3-typo", { opacity: 1 }, { opacity: 0, duration: 0.15 }, {b1} + 0.55);
    tl.fromTo("#t3-fix", { opacity: 0 }, { opacity: 1, duration: 0.15 }, {b1} + 0.6);
    tl.fromTo("#t3-edited", { opacity: 0 }, { opacity: 1, duration: 0.2 }, {b1} + 0.7);
    tl.fromTo("#t3-badge", { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.35, ease: "back.out(2.5)" }, {b2} - 0.1);'''
    return scene("trick3", dur, beats, body, css, anim)


def scene_outro(dur, beats):
    body = '''    <div id="o-glow"></div>
    <svg id="o-mark" viewBox="0 0 200 260"><path id="o-fill" d="M30 20 H170 V240 L100 185 L30 240 Z" fill="#C8FF2E" fill-opacity="0"
      stroke="#C8FF2E" stroke-width="14" stroke-linejoin="round"/></svg>
    <div id="o-btn">FOLLOW FOR MORE</div>'''
    css = f'''    #o-glow {{ position: absolute; left: 190px; top: 260px; width: 700px; height: 700px; border-radius: 50%;
      background: radial-gradient(circle, rgba(200,255,46,.3), rgba(200,255,46,0) 65%); }}
    #o-mark {{ position: absolute; left: 400px; top: 360px; width: 280px; height: 364px; filter: drop-shadow(0 0 30px rgba(200,255,46,.6)); }}
    #o-btn {{ position: absolute; left: 230px; top: 820px; width: 620px; height: 110px; border-radius: 55px; border: 5px solid {LIME};
      color: {LIME}; font: 900 48px/100px Montserrat, sans-serif; text-align: center; letter-spacing: 0.02em; }}'''
    anim = '''tl.fromTo("#o-mark", { scale: 0.6, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.4, ease: "back.out(2)" }, 0);
    tl.fromTo("#o-fill", { attr: { "fill-opacity": 0 } }, { attr: { "fill-opacity": 1 }, duration: 0.25 }, {b0});
    tl.fromTo("#o-mark", { y: 0 }, { y: -24, duration: 0.18, ease: "power2.out", yoyo: true, repeat: 1 }, {b0});
    tl.fromTo("#o-btn", { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }, 0.5);
    tl.fromTo("#o-glow", { scale: 0.8 }, { scale: 1.15, duration: {d}, ease: "sine.inOut" }, 0);'''
    return scene("outro", dur, beats, body, css, anim)


SCENES = {"hook": scene_hook, "trick1": scene_trick1, "trick2": scene_trick2,
          "trick3": scene_trick3, "outro": scene_outro}


def build_tracker(t1: float, t2: float, t3: float, end: float) -> str:
    dots = "".join(f'<div class="dot" id="tr-d{i}">{i}</div>' + ('<div class="ln"></div>' if i < 3 else "")
                   for i in (1, 2, 3))
    on = '{ backgroundColor: "#C8FF2E", color: "#07110A", scale: 1.15, boxShadow: "0 0 30px rgba(200,255,46,.8)", duration: 0.25, ease: "back.out(2)" }'
    off = '{ backgroundColor: "rgba(200,255,46,0)", color: "#C8FF2E", scale: 1, boxShadow: "0 0 0px rgba(200,255,46,0)", duration: 0.2 }'
    init = '{ backgroundColor: "rgba(200,255,46,0)", color: "#C8FF2E", scale: 1, boxShadow: "0 0 0px rgba(200,255,46,0)" }'
    return f'''<template>
  <style>
    #root {{ position: absolute; inset: 0; }}
    #tr {{ position: absolute; left: 0; right: 0; top: 200px; display: flex; justify-content: center; align-items: center; gap: 14px; }}
    .dot {{ width: 76px; height: 76px; border-radius: 50%; border: 5px solid {LIME}; color: {LIME};
      font: 900 40px/66px Montserrat, sans-serif; text-align: center; }}
    .ln {{ width: 60px; height: 5px; border-radius: 3px; background: {LIME}; opacity: .6; }}
  </style>
  <div id="root" data-composition-id="tracker" data-width="{W}" data-height="{H}">
    <div id="tr">{dots}</div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo("#tr", {{ opacity: 0, y: -30 }}, {{ opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }}, 0);
    tl.fromTo("#tr-d1", {init}, {on}, 0.1);
    tl.fromTo("#tr-d2", {init}, {on}, {t2 - t1:.3f});
    tl.to("#tr-d1", {off}, {t2 - t1:.3f});
    tl.fromTo("#tr-d3", {init}, {on}, {t3 - t1:.3f});
    tl.to("#tr-d2", {off}, {t3 - t1:.3f});
    window.__timelines["tracker"] = tl;
  </script>
</template>
'''


def build_bg(total: float) -> str:
    return f'''<template>
  <style>
    #root {{ position: absolute; inset: 0; background: {BG}; overflow: hidden; }}
    #bg-a {{ position: absolute; left: -300px; top: -200px; width: 1100px; height: 1100px; border-radius: 50%;
      background: radial-gradient(circle, rgba(120,190,20,.35), rgba(120,190,20,0) 65%); }}
    #bg-b {{ position: absolute; left: 400px; top: 1100px; width: 1000px; height: 1000px; border-radius: 50%;
      background: radial-gradient(circle, rgba(200,255,46,.22), rgba(200,255,46,0) 65%); }}
    #bg-v {{ position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 40%, rgba(0,0,0,.65) 100%); }}
  </style>
  <div id="root" data-composition-id="bg" data-width="{W}" data-height="{H}">
    <div id="bg-a" data-layout-allow-overflow></div><div id="bg-b" data-layout-allow-overflow></div><div id="bg-v"></div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo("#bg-a", {{ x: 0, y: 0 }}, {{ x: 220, y: 160, duration: {total:.2f}, ease: "sine.inOut" }}, 0);
    tl.fromTo("#bg-b", {{ x: 0, y: 0 }}, {{ x: -260, y: -220, duration: {total:.2f}, ease: "sine.inOut" }}, 0);
    window.__timelines["bg"] = tl;
  </script>
</template>
'''


# ----------------------------------------------------------------- root
def build(voice: Path | None) -> Path:
    segs = parse_script(HERE / "script.txt")
    if voice:
        whisper_times(segs, voice)
    else:
        estimate_times(segs)
    words = [w for s in segs for w in s["words"]]
    total = round(words[-1]["end"] + 1.3, 2)

    bounds = []
    for i, s in enumerate(segs):
        st = 0.0 if i == 0 else round(s["words"][0]["start"] - 0.3, 3)
        bounds.append(st)
    bounds.append(total)

    comp = HERE / "compositions"
    comp.mkdir(exist_ok=True)
    hosts = []
    for i, s in enumerate(segs):
        st, en = bounds[i], bounds[i + 1]
        beats = [w["start"] - st for w in s["words"] if w["beat"]]
        (comp / f"{s['id']}.html").write_text(SCENES[s["id"]](en - st, beats))
        hosts.append((s["id"], st, en - st, 1))

    idx = {s["id"]: i for i, s in enumerate(segs)}
    t1, t2, t3 = (bounds[idx[k]] for k in ("trick1", "trick2", "trick3"))
    (comp / "tracker.html").write_text(build_tracker(t1, t2, t3, bounds[idx["trick3"] + 1]))
    cap_html, pops = build_captions(words, total)
    (comp / "captions.html").write_text(cap_html)
    (comp / "bg.html").write_text(build_bg(total))

    host_html = [f'      <div id="bg" data-composition-id="bg" data-composition-src="compositions/bg.html" data-start="0" '
                 f'data-duration="{total}" data-track-index="0" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>']
    for sid, st, du, lane in hosts:
        host_html.append(f'      <div id="{sid}" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html" '
                         f'data-start="{st:.3f}" data-duration="{du:.3f}" data-track-index="{lane}" data-track-kind="graphics" '
                         f'data-width="{W}" data-height="{H}"></div>')
    host_html.append(f'      <div id="tracker" data-composition-id="tracker" data-composition-src="compositions/tracker.html" '
                     f'data-start="{t1:.3f}" data-duration="{bounds[idx["trick3"] + 1] - t1:.3f}" data-track-index="2" '
                     f'data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>')
    host_html.append(f'      <div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" '
                     f'data-start="0" data-duration="{total}" data-track-index="3" data-track-kind="captions" '
                     f'data-width="{W}" data-height="{H}"></div>')

    audio = []
    vfile = next(iter(sorted((HERE / "assets").glob("voice.*"))), None)
    if vfile:
        audio.append(f'      <audio id="voice" src="assets/{vfile.name}" data-start="0" data-duration="{total}" data-track-index="4" data-volume="1"></audio>')
    music_vol = 0.13 if vfile else 0.32
    audio.append(f'      <audio id="music" src="assets/music.mp3" data-start="0" data-duration="{total}" data-track-index="5" '
                 f'data-volume="{music_vol}" data-fade-in="0.3" data-fade-out="1.5"></audio>')
    for i, st in enumerate(bounds[1:-1]):
        audio.append(f'      <audio id="whoosh{i}" src="assets/whoosh.wav" data-start="{max(0, st - 0.35):.3f}" data-duration="0.6" data-track-index="6" data-volume="0.45"></audio>')
    for i, t in enumerate(pops):
        audio.append(f'      <audio id="pop{i}" src="assets/pop.wav" data-start="{t:.3f}" data-duration="0.09" data-track-index="7" data-volume="0.35"></audio>')

    doc = f'''<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <!-- Generated by build.py from script.txt - edit those, then re-run build.py -->
    <script src="assets/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: {BG}; }}
      #root {{ position: relative; width: 100%; height: 100%; background: {BG}; }}
      #bg {{ z-index: 0; }}
      #hook, #trick1, #trick2, #trick3, #outro {{ z-index: 1; }}
      #tracker {{ z-index: 2; }}
      #captions {{ z-index: 3; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="{W}" data-height="{H}">
{chr(10).join(host_html)}
{chr(10).join(audio)}
    </div>
    <script>
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
'''
    (HERE / "index.html").write_text(doc)
    print(f"Built {total:.1f} s reel ({'voice-timed' if voice else 'estimated timing, no voice'}), "
          f"{len(chunks(words))} caption groups, {len(pops)} keyword pops.")
    return HERE / "index.html"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", type=Path, help="your recording (m4a/mp3/wav/...)")
    ap.add_argument("--render", action="store_true", help="also render to ../../out/insta-tricks.mp4")
    a = ap.parse_args()
    voice = None
    if a.voice:
        for old in (HERE / "assets").glob("voice.*"):
            old.unlink()
        voice = HERE / "assets" / "voice.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(a.voice), "-af",
                        "highpass=f=80,loudnorm=I=-16:TP=-1.5", "-ar", "48000", "-ac", "1", str(voice)], check=True)
    build(voice)
    if a.render:
        out = HERE.parents[1] / "out" / ("insta-tricks.mp4" if voice else "insta-tricks-preview.mp4")
        out.parent.mkdir(exist_ok=True)
        subprocess.run(["hyperframes", "render", "-o", str(out)], cwd=HERE, check=True, stdin=subprocess.DEVNULL)
        print(out)


if __name__ == "__main__":
    main()
