#!/usr/bin/env python3
"""Hinglish explainer: WhatsApp Business Cloud app in Make (vertical reel).

  python3 build.py                          # preview, timing estimated from the script
  python3 build.py --voice vo.mp3 --render  # final: Whisper times every word to the voiceover

script.json rows are [scene, roman_caption, voice_text]. The voice text (Devanagari + English)
is what the voice reads; the Roman text is what viewers read. Both have the same word count,
so each caption word takes the timing of its voice word.
  *word* = big green keyword in the captions      ^word = an on-screen animation fires here
"""
from __future__ import annotations

import argparse
import difflib
import html
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1080, 1920
BG = "#0A0B12"
GREEN = "#2BE07A"
PURPLE = "#8B5CF6"
CHAPTERS = {"hook": "", "features": "KYA KAR SAKTE HO", "needs": "REQUIREMENTS", "coexist": "COEXISTENCE MODE",
            "connect": "CONNECTION", "webhook": "WEBHOOK", "setup": "WEBHOOK SETUP", "outro": "TEMPLATES"}


# ------------------------------------------------------------------ words + timing
def load_words() -> tuple[list[dict], list[str]]:
    rows = json.loads((HERE / "script.json").read_text())
    words, order = [], []
    for si, (scene, roman, voice) in enumerate(rows):
        r, v = roman.split(), voice.split()
        assert len(r) == len(v), f"row {si}: caption and voice text need the same number of words"
        if scene not in order:
            order.append(scene)
        for i, (rw, vw) in enumerate(zip(r, v)):
            words.append({"text": rw.lstrip("^").replace("*", ""), "key": "*" in rw, "beat": rw.startswith("^"),
                          "voice": vw, "scene": scene, "sent": si, "last": i == len(r) - 1})
    return words, order


def norm(t: str) -> str:
    return re.sub(r"[^\w]", "", t.lower().replace("।", ""))


def estimate(words: list[dict]) -> None:
    t, prev_scene = 0.4, words[0]["scene"]
    for w in words:
        if w["scene"] != prev_scene:
            t += 0.35
            prev_scene = w["scene"]
        d = 0.16 + 0.034 * len(w["text"])
        w["start"], w["end"] = round(t, 3), round(t + d, 3)
        t += d + 0.03
        if w["text"][-1] in ",;:":
            t += 0.18
        elif w["text"][-1] in ".?!":
            t += 0.38


def align(words: list[dict], voice: Path) -> None:
    out = HERE / ".whisper"
    out.mkdir(exist_ok=True)
    subprocess.run(["whisper", str(voice), "--model", "small", "--language", "hi", "--word_timestamps", "True",
                    "--initial_prompt", " ".join(w["voice"] for w in words[:40]),
                    "--output_format", "json", "--output_dir", str(out)], check=True)
    data = json.loads((out / (voice.stem + ".json")).read_text())
    heard = [w for s in data["segments"] for w in s.get("words", [])]
    (HERE / "transcript.json").write_text(json.dumps(heard, ensure_ascii=False, indent=1))
    a, b = [norm(w["voice"]) for w in words], [norm(h["word"]) for h in heard]
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            words[blk.a + k]["start"], words[blk.a + k]["end"] = heard[blk.b + k]["start"], heard[blk.b + k]["end"]
    known = [i for i, w in enumerate(words) if "start" in w]
    print(f"Matched {len(known)}/{len(words)} voice words directly; the rest are interpolated.")
    if not known:
        raise SystemExit("Could not match the voiceover to script.json")
    for i, w in enumerate(words):  # interpolate unmatched words between their matched neighbours
        if "start" in w:
            continue
        p = max((k for k in known if k < i), default=None)
        n = min((k for k in known if k > i), default=None)
        t0 = words[p]["end"] if p is not None else max(0.0, words[n]["start"] - 0.5)
        t1 = words[n]["start"] if n is not None else t0 + 0.5
        lo, hi = (p if p is not None else -1), (n if n is not None else len(words))
        frac0, frac1 = (i - lo - 1) / (hi - lo - 1), (i - lo) / (hi - lo - 1)
        w["start"], w["end"] = round(t0 + (t1 - t0) * frac0, 3), round(t0 + (t1 - t0) * frac1, 3)


# ------------------------------------------------------------------ captions
def chunks(words):
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= 3 or cur[-1]["text"][-1] in ".,?!;:" or cur[-1]["sent"] != w["sent"]
                    or (w["key"] and any(x["key"] for x in cur))):
            out.append(cur)
            cur = []
        cur.append(w)
    return out + ([cur] if cur else [])


def key_size(text):
    return max(92, min(160, int(800 / (0.68 * len(text)))))


def build_captions(words, total):
    groups, tweens, pops = [], [], []
    cs = chunks(words)
    for ci, c in enumerate(cs):
        start = max(0.0, c[0]["start"] - 0.06)
        end = cs[ci + 1][0]["start"] - 0.06 if ci + 1 < len(cs) else min(total, c[-1]["end"] + 1.0)
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
                txt = html.escape(w["text"].rstrip(".,;:"))
                style = f' style="font-size:{key_size(w["text"])}px"' if cls == "cap-key" else ""
                spans.append(f'<span id="{wid}" class="cap-w"{style}>{txt}</span>')
                if cls == "cap-key":
                    tweens.append(f'tl.fromTo("#{wid}", {{ opacity: 0, scale: 1.6 }}, {{ opacity: 1, scale: 1, duration: 0.22, ease: "back.out(2.4)" }}, {w["start"]:.3f});')
                    pops.append(round(w["start"] - 0.02, 3))
                else:
                    tweens.append(f'tl.fromTo("#{wid}", {{ opacity: 0, y: 22 }}, {{ opacity: 1, y: 0, duration: 0.14, ease: "power2.out" }}, {w["start"]:.3f});')
            row_html.append(f'<div class="cap-row {cls}">{" ".join(spans)}</div>')
        groups.append(f'    <div id="cap{ci}" class="clip cap" data-start="{start:.3f}" data-duration="{end - start:.3f}" '
                      f'data-track-index="0">{"".join(row_html)}</div>')
    return f'''<template>
  <style>
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    .cap {{ position: absolute; left: 90px; right: 150px; top: 1060px; height: 240px; display: flex; flex-direction: column;
      align-items: center; justify-content: center; text-align: center; }}
    .cap-row {{ width: 100%; font-family: Montserrat, sans-serif; color: #fff; line-height: 1.02;
      text-shadow: 0 4px 18px rgba(0,0,0,.9), 0 0 2px rgba(0,0,0,.9); }}
    .cap-w {{ display: inline-block; }}
    .cap-small {{ font-size: 52px; font-weight: 800; color: #F2F2F2; }}
    .cap-solo {{ font-size: 64px; font-weight: 900; }}
    .cap-key {{ font-weight: 900; letter-spacing: -0.03em; color: {GREEN}; margin: -4px 0 2px;
      text-shadow: 0 0 28px rgba(43,224,122,.55), 0 0 64px rgba(43,224,122,.25), 0 6px 18px rgba(0,0,0,.85); }}
  </style>
  <div id="root" data-composition-id="captions" data-width="{W}" data-height="{H}">
{chr(10).join(groups)}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
{chr(10).join("    " + t for t in tweens)}
    window.__timelines["captions"] = tl;
  </script>
</template>
''', pops


# ------------------------------------------------------------------ scenes
COMMON_CSS = """
    #root { position: absolute; inset: 0; font-family: Inter, sans-serif; color: #EEF0F6; }
    .chap { position: absolute; left: 90px; right: 150px; top: 226px; text-align: center; font: 800 30px/1 Montserrat, sans-serif;
      letter-spacing: .22em; color: #9AA0B4; }
    .card { position: absolute; border-radius: 28px; background: #151826; border: 2px solid #262B3F;
      box-shadow: 0 24px 60px rgba(0,0,0,.45); }
    .pill { position: absolute; border-radius: 999px; text-align: center; font: 800 34px/1 Montserrat, sans-serif; }
    .ico { position: absolute; border-radius: 22px; display: flex; align-items: center; justify-content: center;
      font: 900 40px/1 Montserrat, sans-serif; color: #0A0B12; }
    .lbl { position: absolute; font: 800 40px/1.1 Montserrat, sans-serif; }
    .sub { position: absolute; font: 600 30px/1.2 Inter, sans-serif; color: #9AA0B4; }
    .g { background: #2BE07A; } .p { background: #8B5CF6; color: #fff; }
"""

POP_IN = 'tl.fromTo("{sel}", {{ opacity: 0, y: 40, scale: .92 }}, {{ opacity: 1, y: 0, scale: 1, duration: .38, ease: "back.out(1.8)" }}, {t});'


DIM_IN = 'tl.fromTo("{sel}", {{ opacity: 0, y: 30 }}, {{ opacity: .3, y: 0, duration: .35, ease: "power3.out" }}, {t});'
LIGHT = 'tl.to("{sel}", {{ opacity: 1, duration: .2 }}, {t});\n    tl.to("{sel}", {{ scale: 1.05, duration: .15, yoyo: true, repeat: 1, ease: "power2.out" }}, {t});'


def pop(sel, t):
    return POP_IN.format(sel=sel, t=t)


def scene_doc(sid, dur, beats, body, css, anim):
    for i, b in enumerate(beats):
        anim = anim.replace(f"%b{i}%", f"{b:.3f}")
    anim = anim.replace("%d%", f"{dur:.3f}")
    if re.search(r"%b\d%", anim):
        raise SystemExit(f"scene {sid}: script.json is missing a ^beat this scene needs")
    chap = ""  # chapter labels removed: they sit under Instagram's top bar
    chap_html = f'    <div class="chap" id="{sid}-chap">{chap}</div>\n' if chap else ""
    chap_anim = f'tl.fromTo("#{sid}-chap", {{ opacity: 0, y: -20 }}, {{ opacity: 1, y: 0, duration: .3 }}, 0);\n    ' if chap else ""
    return f'''<template>
  <style>{COMMON_CSS}{css}
  </style>
  <div id="root" data-composition-id="{sid}" data-width="{W}" data-height="{H}">
{chap_html}{body}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {chap_anim}{anim}
    window.__timelines["{sid}"] = tl;
  </script>
</template>
'''


def s_hook(d, b):
    body = '''    <div class="card" id="hk-wa" style="left:240px;top:300px;width:600px;height:200px">
      <div class="ico g" style="left:36px;top:46px;width:108px;height:108px">WA</div>
      <div class="lbl" style="left:170px;top:58px">WhatsApp</div><div class="sub" style="left:170px;top:112px">Business Cloud</div></div>
    <svg id="hk-link" style="position:absolute;left:520px;top:500px;width:40px;height:200px" viewBox="0 0 40 200">
      <line id="hk-line" x1="20" y1="10" x2="20" y2="190" stroke="#8B5CF6" stroke-width="8" stroke-linecap="round" stroke-dasharray="14 16"/></svg>
    <div class="card" id="hk-mk" style="left:240px;top:700px;width:600px;height:200px">
      <div class="ico p" style="left:36px;top:46px;width:108px;height:108px">M</div>
      <div class="lbl" style="left:170px;top:58px">Make</div><div class="sub" style="left:170px;top:112px">Automation, no code</div></div>
    <div class="pill" id="hk-badge" style="left:330px;top:960px;width:420px;height:76px;line-height:76px;background:#2BE07A;color:#0A0B12">NO CODING</div>'''
    anim = (pop("#hk-wa", 0) + "\n    " + pop("#hk-mk", 0.15) +
            '\n    tl.fromTo("#hk-line", { attr: { "stroke-dashoffset": 0 } }, { attr: { "stroke-dashoffset": -300 }, duration: %d%, ease: "none" }, 0);'
            '\n    tl.fromTo("#hk-badge", { opacity: 0, scale: .4 }, { opacity: 1, scale: 1, duration: .35, ease: "back.out(2.5)" }, %b0%);')
    return scene_doc("hook", d, b, body, "", anim)


def s_features(d, b):
    items = [("✉", "Messages bhejo", "g"), ("T", "Template messages", "p"), ("⇅", "Media upload / download", "g"),
             ("◉", "Events monitor", "p"), ("☺", "Business profile update", "g")]
    body = "".join(f'''    <div class="card" id="ft{i}" style="left:120px;top:{290 + i * 150}px;width:840px;height:124px">
      <div class="ico {c}" style="left:22px;top:20px;width:84px;height:84px">{ic}</div>
      <div class="lbl" style="left:132px;top:42px;font-size:38px">{t}</div></div>
''' for i, (ic, t, c) in enumerate(items))
    anim = "\n    ".join(DIM_IN.format(sel=f"#ft{i}", t=round(.1 * i, 2)) + "\n    " + LIGHT.format(sel=f"#ft{i}", t=f"%b{i}%") for i in range(5))
    return scene_doc("features", d, b, body, "", anim)


def s_needs(d, b):
    items = ["Facebook account", "Meta Business Suite account", "WhatsApp Business number"]
    body = "".join(f'''    <div class="card" id="nd{i}" style="left:120px;top:{290 + i * 150}px;width:840px;height:124px">
      <div class="ico g" id="nd{i}-ok" style="left:22px;top:20px;width:84px;height:84px">&#10003;</div>
      <div class="lbl" style="left:132px;top:42px;font-size:38px">{t}</div></div>
''' for i, t in enumerate(items))
    body += '''    <div class="card" id="nd-warn" style="left:120px;top:770px;width:840px;height:150px;border-color:#FF6B6B">
      <div class="lbl" style="left:36px;top:34px;font-size:38px;color:#FF8A8A">2-step verification</div>
      <div class="sub" style="left:36px;top:86px">pehle OFF karo</div>
      <div id="nd-tog" style="position:absolute;right:36px;top:45px;width:110px;height:60px;border-radius:30px;background:#2BE07A">
        <div id="nd-knob" style="position:absolute;left:54px;top:6px;width:48px;height:48px;border-radius:50%;background:#fff"></div></div></div>'''
    anim = "\n    ".join(DIM_IN.format(sel=f"#nd{i}", t=round(.1 * i, 2)) + "\n    " + LIGHT.format(sel=f"#nd{i}", t=f"%b{i}%") for i in range(3))
    anim += ('\n    ' + pop("#nd-warn", "%b3% - .2") +
             '\n    tl.fromTo("#nd-knob", { x: 0 }, { x: -46, duration: .25, ease: "power2.inOut" }, %b3% + .6);'
             '\n    tl.fromTo("#nd-tog", { backgroundColor: "#2BE07A" }, { backgroundColor: "#3A3F52", duration: .25 }, %b3% + .6);')
    return scene_doc("needs", d, b, body, "", anim)


def s_coexist(d, b):
    body = '''    <div class="card" id="cx-a" style="left:110px;top:330px;width:380px;height:440px">
      <div class="ico g" style="left:130px;top:60px;width:120px;height:120px">WA</div>
      <div class="lbl" style="left:0;right:0;top:220px;text-align:center;font-size:36px">WhatsApp<br>Business App</div></div>
    <div class="card" id="cx-b" style="left:590px;top:330px;width:380px;height:440px">
      <div class="ico p" style="left:130px;top:60px;width:120px;height:120px">M</div>
      <div class="lbl" style="left:0;right:0;top:220px;text-align:center;font-size:36px">Make<br>Cloud app</div></div>
    <div id="cx-arrow" style="position:absolute;left:470px;top:500px;width:140px;text-align:center;font:900 64px/1 Montserrat,sans-serif;color:#2BE07A">&#8644;</div>
    <div class="pill" id="cx-mode" style="left:250px;top:820px;width:580px;height:84px;line-height:84px;background:#8B5CF6;color:#fff">COEXISTENCE MODE</div>
    <div class="pill" id="cx-geo" style="left:250px;top:930px;width:580px;height:76px;line-height:72px;border:4px solid #FFC94D;color:#FFC94D;font-size:30px">CHECK: COUNTRY SUPPORT</div>'''
    anim = (pop("#cx-a", 0) + "\n    " + pop("#cx-b", .15) +
            '\n    tl.fromTo("#cx-mode", { opacity: 0, scale: .5 }, { opacity: 1, scale: 1, duration: .35, ease: "back.out(2.2)" }, %b0%);'
            '\n    tl.fromTo("#cx-arrow", { opacity: 0, scale: .5 }, { opacity: 1, scale: 1, duration: .3, ease: "back.out(2)" }, %b1% - .1);'
            '\n    tl.fromTo("#cx-arrow", { x: -14 }, { x: 14, duration: .4, ease: "sine.inOut", yoyo: true, repeat: 3 }, %b1% + .2);'
            '\n    ' + pop("#cx-geo", "%b2%"))
    return scene_doc("coexist", d, b, body, "", anim)


def s_connect(d, b):
    steps = [("Meta Business Suite", "Business portfolio banao"), ("WhatsApp Business", "Account create karo"),
             ("Make", "Connection create karo")]
    body = "".join(f'''    <div class="card" id="cn{i}" style="left:120px;top:{300 + i * 220}px;width:840px;height:180px">
      <div class="ico" id="cn{i}-n" style="left:30px;top:40px;width:100px;height:100px;border-radius:50%;border:5px solid #2BE07A;color:#2BE07A">{i + 1}</div>
      <div class="lbl" style="left:160px;top:44px;font-size:40px">{t}</div><div class="sub" style="left:160px;top:100px">{s}</div></div>
''' for i, (t, s) in enumerate(steps))
    anim = "\n    ".join(pop(f"#cn{i}", 0.1 * i) for i in range(3))
    for i in range(3):
        anim += (f'\n    tl.fromTo("#cn{i}-n", {{ backgroundColor: "rgba(43,224,122,0)", color: "#2BE07A" }}, '
                 f'{{ backgroundColor: "rgba(43,224,122,1)", color: "#0A0B12", duration: .2 }}, %b{i}%);'
                 f'\n    tl.fromTo("#cn{i}", {{ borderColor: "#262B3F" }}, {{ borderColor: "#2BE07A", duration: .2 }}, %b{i}%);')
    return scene_doc("connect", d, b, body, "", anim)


def s_webhook(d, b):
    body = '''    <div class="card" id="wh-msg" style="left:240px;top:290px;width:600px;height:150px">
      <div class="ico g" style="left:30px;top:33px;width:84px;height:84px">&#9993;</div>
      <div class="lbl" style="left:140px;top:52px;font-size:40px">Naya message</div></div>
    <div class="card" id="wh-hook" style="left:240px;top:540px;width:600px;height:150px;border-color:#8B5CF6">
      <div class="ico p" style="left:30px;top:33px;width:84px;height:84px">&#8634;</div>
      <div class="lbl" style="left:140px;top:52px;font-size:40px">Webhook</div></div>
    <div class="card" id="wh-sc" style="left:240px;top:790px;width:600px;height:150px">
      <div class="ico" id="wh-play" style="left:30px;top:33px;width:84px;height:84px;background:#3A3F52;color:#fff">&#9654;</div>
      <div class="lbl" style="left:140px;top:52px;font-size:40px">Scenario start</div></div>
    <div id="wh-dot" style="position:absolute;left:522px;top:440px;width:36px;height:36px;border-radius:50%;background:#2BE07A;box-shadow:0 0 30px #2BE07A;opacity:0"></div>'''
    anim = (pop("#wh-msg", 0) + "\n    " + pop("#wh-hook", "%b0%") + "\n    " + pop("#wh-sc", "%b0% + .2") +
            '\n    tl.fromTo("#wh-dot", { opacity: 1, y: 0 }, { opacity: 1, y: 350, duration: .7, ease: "power1.inOut" }, %b1% - .3);'
            '\n    tl.to("#wh-dot", { opacity: 0, duration: .15 }, %b1% + .4);'
            '\n    tl.fromTo("#wh-play", { backgroundColor: "#3A3F52" }, { backgroundColor: "#2BE07A", color: "#0A0B12", duration: .2 }, %b1% + .4);'
            '\n    tl.to("#wh-sc", { scale: 1.06, duration: .18, yoyo: true, repeat: 1, ease: "power2.out" }, %b1% + .4);')
    return scene_doc("webhook", d, b, body, "", anim)


def s_setup(d, b):
    body = '''    <div class="card" id="su-panel" style="left:110px;top:280px;width:860px;height:780px">
      <div style="position:absolute;left:0;right:0;top:0;height:120px;border-bottom:2px solid #262B3F">
        <div class="ico g" style="left:30px;top:24px;width:72px;height:72px;font-size:30px">WA</div>
        <div class="lbl" style="left:124px;top:26px;font-size:34px">Watch Events</div>
        <div class="pill" id="su-inst" style="left:124px;top:70px;width:200px;height:44px;line-height:44px;font-size:28px;background:#8B5CF6;color:#fff">INSTANT</div></div>
      <div class="pill" id="su-create" style="left:40px;top:150px;width:780px;height:80px;line-height:76px;border:4px solid #2BE07A;color:#2BE07A;font-size:32px">+ Create a webhook</div>
      <div class="sub" style="left:40px;top:262px">Webhook name</div>
      <div class="fld" id="su-f1" style="top:300px"><span id="su-name">My WhatsApp hook</span></div>
      <div class="sub" style="left:40px;top:398px">Connection</div>
      <div class="fld" id="su-f2" style="top:436px"><span id="su-conn">My WhatsApp connection &#9662;</span></div>
      <div class="sub" style="left:40px;top:534px">Events</div>
      <div class="chk" id="su-c1" style="left:40px">&#10003; Messages</div><div class="chk" id="su-c2" style="left:300px">&#10003; Statuses</div>
      <div class="pill" id="su-save" style="left:520px;top:670px;width:300px;height:80px;line-height:80px;background:#2BE07A;color:#0A0B12">Save</div></div>
    <div class="pill" id="su-ok" style="left:240px;top:1000px;width:600px;height:80px;line-height:80px;background:#2BE07A;color:#0A0B12;font-size:32px">&#10003; Webhook ready</div>'''
    css = '''
    .fld { position: absolute; left: 40px; width: 780px; height: 76px; border-radius: 16px; background: #0E101A; border: 2px solid #2D3247;
      font: 700 30px/72px Inter, sans-serif; padding-left: 24px; color: #EEF0F6; }
    .fld span { opacity: 0; }
    .chk { position: absolute; top: 576px; width: 240px; height: 66px; border-radius: 16px; border: 2px solid #2D3247;
      font: 700 28px/62px Inter, sans-serif; text-align: center; color: #6B7186; }'''
    anim = (pop("#su-panel", 0) +
            '\n    tl.fromTo("#su-inst", { scale: 1 }, { scale: 1.25, duration: .3, yoyo: true, repeat: 1 }, %b0%);'
            '\n    tl.fromTo("#su-create", { backgroundColor: "rgba(43,224,122,0)", color: "#2BE07A" }, { backgroundColor: "rgba(43,224,122,1)", color: "#0A0B12", duration: .2 }, %b1%);'
            '\n    tl.fromTo("#su-name", { opacity: 0 }, { opacity: 1, duration: .25 }, %b2%);'
            '\n    tl.fromTo("#su-f1", { borderColor: "#2D3247" }, { borderColor: "#2BE07A", duration: .2 }, %b2%);'
            '\n    tl.fromTo("#su-conn", { opacity: 0 }, { opacity: 1, duration: .25 }, %b3%);'
            '\n    tl.fromTo("#su-f2", { borderColor: "#2D3247" }, { borderColor: "#2BE07A", duration: .2 }, %b3%);'
            '\n    tl.fromTo(["#su-c1", "#su-c2"], { color: "#6B7186", borderColor: "#2D3247" }, { color: "#2BE07A", borderColor: "#2BE07A", duration: .2, stagger: .25 }, %b4%);'
            '\n    tl.fromTo("#su-save", { scale: 1 }, { scale: .9, duration: .12, yoyo: true, repeat: 1 }, %b5%);'
            '\n    tl.fromTo("#su-ok", { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: .35, ease: "back.out(2)" }, %b6% - .3);')
    return scene_doc("setup", d, b, body, css, anim)


def s_outro(d, b):
    cards = "".join(f'<div class="card tg" id="og{i}" style="left:{120 + (i % 3) * 290}px;top:{300 + (i // 3) * 250}px">'
                    f'<div class="ico {"gp"[i % 2]}" style="left:24px;top:24px;width:64px;height:64px;font-size:30px">{"WA" if i % 2 == 0 else "M"}</div>'
                    f'<div class="bar1"></div><div class="bar2"></div></div>' for i in range(6))
    body = f'''    {cards}
    <div class="pill" id="og-k" style="left:200px;top:820px;width:680px;height:84px;line-height:84px;background:#8B5CF6;color:#fff">1000s OF TEMPLATES</div>
    <div class="pill" id="og-f" style="left:240px;top:940px;width:600px;height:84px;line-height:78px;border:4px solid #2BE07A;color:#2BE07A">SAVE + FOLLOW</div>'''
    css = '''
    .tg { width: 260px; height: 220px; }
    .bar1 { position: absolute; left: 24px; top: 120px; width: 200px; height: 18px; border-radius: 9px; background: #2D3247; }
    .bar2 { position: absolute; left: 24px; top: 156px; width: 140px; height: 18px; border-radius: 9px; background: #2D3247; }'''
    anim = "\n    ".join(pop(f"#og{i}", f"%b0% - .6 + {i * .08:.2f}") for i in range(6))
    anim += ('\n    tl.fromTo("#og-k", { opacity: 0, scale: .5 }, { opacity: 1, scale: 1, duration: .35, ease: "back.out(2.2)" }, %b0%);'
             '\n    ' + pop("#og-f", "%b1%") +
             '\n    tl.to("#og-f", { scale: 1.06, duration: .3, yoyo: true, repeat: 3, ease: "sine.inOut" }, %b1% + .5);')
    return scene_doc("outro", d, b, body, css, anim)


SCENES = {"hook": s_hook, "features": s_features, "needs": s_needs, "coexist": s_coexist, "connect": s_connect,
          "webhook": s_webhook, "setup": s_setup, "outro": s_outro}


def build_bg(total):
    return f'''<template>
  <style>
    #root {{ position: absolute; inset: 0; background: {BG}; overflow: hidden; }}
    #bg-a {{ position: absolute; left: -300px; top: -250px; width: 1100px; height: 1100px; border-radius: 50%;
      background: radial-gradient(circle, rgba(139,92,246,.30), rgba(139,92,246,0) 65%); }}
    #bg-b {{ position: absolute; left: 380px; top: 1050px; width: 1000px; height: 1000px; border-radius: 50%;
      background: radial-gradient(circle, rgba(43,224,122,.20), rgba(43,224,122,0) 65%); }}
    #bg-bar {{ position: absolute; left: 90px; width: 840px; top: 176px; height: 8px; border-radius: 4px; background: #2BE07A; transform-origin: 0 50%; }}
    #bg-track {{ position: absolute; left: 90px; width: 840px; top: 176px; height: 8px; border-radius: 4px; background: #1E2233; }}
  </style>
  <div id="root" data-composition-id="bg" data-width="{W}" data-height="{H}">
    <div id="bg-a" data-layout-allow-overflow></div><div id="bg-b" data-layout-allow-overflow></div>
    <div id="bg-track"></div><div id="bg-bar"></div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo("#bg-a", {{ x: 0, y: 0 }}, {{ x: 240, y: 180, duration: {total:.2f}, ease: "sine.inOut" }}, 0);
    tl.fromTo("#bg-b", {{ x: 0, y: 0 }}, {{ x: -260, y: -200, duration: {total:.2f}, ease: "sine.inOut" }}, 0);
    tl.fromTo("#bg-bar", {{ scaleX: 0 }}, {{ scaleX: 1, duration: {total:.2f}, ease: "none" }}, 0);
    window.__timelines["bg"] = tl;
  </script>
</template>
'''


def build(voice: Path | None):
    words, order = load_words()
    align(words, voice) if voice else estimate(words)
    total = round(words[-1]["end"] + 1.4, 2)
    starts = [0.0] + [round(next(w for w in words if w["scene"] == s)["start"] - 0.3, 3) for s in order[1:]]
    bounds = starts + [total]
    comp = HERE / "compositions"
    comp.mkdir(exist_ok=True)
    hosts = [f'      <div id="bg" data-composition-id="bg" data-composition-src="compositions/bg.html" data-start="0" '
             f'data-duration="{total}" data-track-index="0" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>']
    for i, sid in enumerate(order):
        st, du = bounds[i], bounds[i + 1] - bounds[i]
        beats = [w["start"] - st for w in words if w["scene"] == sid and w["beat"]]
        (comp / f"{sid}.html").write_text(SCENES[sid](du, beats))
        hosts.append(f'      <div id="{sid}" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html" '
                     f'data-start="{st:.3f}" data-duration="{du:.3f}" data-track-index="1" data-track-kind="graphics" '
                     f'data-width="{W}" data-height="{H}"></div>')
    cap, pops = build_captions(words, total)
    (comp / "captions.html").write_text(cap)
    (comp / "bg.html").write_text(build_bg(total))
    hosts.append(f'      <div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" '
                 f'data-start="0" data-duration="{total}" data-track-index="2" data-track-kind="captions" data-width="{W}" data-height="{H}"></div>')
    audio = []
    vfile = next(iter(sorted((HERE / "assets").glob("voice.*"))), None)
    if vfile:
        audio.append(f'      <audio id="voice" src="assets/{vfile.name}" data-start="0" data-duration="{total}" data-track-index="3" data-volume="1"></audio>')
    audio.append(f'      <audio id="music" src="assets/music.mp3" data-start="0" data-duration="{min(total, 98)}" data-track-index="4" '
                 f'data-volume="{0.12 if vfile else 0.3}" data-fade-in="0.3" data-fade-out="1.5"></audio>')
    for i, st in enumerate(bounds[1:-1]):
        audio.append(f'      <audio id="whoosh{i}" src="assets/whoosh.wav" data-start="{max(0, st - 0.35):.3f}" data-duration="0.6" data-track-index="5" data-volume="0.4"></audio>')
    for i, t in enumerate(pops):
        audio.append(f'      <audio id="pop{i}" src="assets/pop.wav" data-start="{t:.3f}" data-duration="0.09" data-track-index="6" data-volume="0.3"></audio>')
    scene_ids = ", ".join("#" + s for s in order)
    (HERE / "index.html").write_text(f'''<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <!-- Generated by build.py from script.json: edit those and re-run build.py -->
    <script src="assets/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: {BG}; }}
      #root {{ position: relative; width: 100%; height: 100%; background: {BG}; }}
      #bg {{ z-index: 0; }} {scene_ids} {{ z-index: 1; }} #captions {{ z-index: 2; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="{W}" data-height="{H}">
{chr(10).join(hosts)}
{chr(10).join(audio)}
    </div>
    <script>
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
''')
    print(f"Built {total:.1f} s video ({'voice-timed' if voice else 'estimated timing'}), {len(pops)} keywords.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", type=Path)
    ap.add_argument("--render", action="store_true")
    a = ap.parse_args()
    voice = None
    if a.voice:
        for old in (HERE / "assets").glob("voice.*"):
            old.unlink()
        voice = HERE / "assets" / "voice.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(a.voice), "-af", "loudnorm=I=-16:TP=-1.5",
                        "-ar", "48000", "-ac", "1", str(voice)], check=True)
    build(voice)
    if a.render:
        out = HERE.parents[1] / "out" / ("make-whatsapp.mp4" if voice else "make-whatsapp-preview.mp4")
        subprocess.run(["hyperframes", "render", "-o", str(out)], cwd=HERE, check=True, stdin=subprocess.DEVNULL)
        print(out)


if __name__ == "__main__":
    main()
