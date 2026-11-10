"""Reel: "How to make Claude Code work" - English, energetic, uses the user's own clips as B-roll.

Re-uses the make_reel.py engine (karaoke subs, TTE decrypt, glitch transitions, music, sfx).
B-roll clips (1080x1920) are streamed with ffmpeg; pass them with --clips <hook> <shop> <polaroid>.

    python reel_claude_code.py --clips hook.mp4 shop.mp4 polaroid.mp4 -o claude_code.mp4
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import make_reel as m
from make_reel import (W, H, FPS, YELLOW, WHITE, MUTED, clamp, prog, out_back, out_cubic, hexc, font, text, paste,
                       rrect, chip, tte_text)

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONOB = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
CORAL = hexc("D97757")
GREEN = hexc("3FD68A")
m.BG = m.gradient_bg("07070D", "141022")


# ---------------------------------------------------------------- streamed B-roll
class Clip:
    """Sequential frame reader: frame(t) returns the clip frame at clip-time t (seconds)."""

    def __init__(self, path, start=0.0, zoom=1.0, cy=0.5, dim=0.0):
        self.path, self.start, self.zoom, self.cy, self.dim = path, start, zoom, cy, dim
        self.proc, self.idx, self.last = None, -1, None

    def _open(self, t0):
        if self.proc:
            self.proc.kill()
        vf = f"fps={FPS},scale={W}:{H}"
        if self.zoom != 1.0:
            ch = int(H / self.zoom) // 2 * 2
            cw = int(W / self.zoom) // 2 * 2
            y = int(H * self.cy - ch / 2)
            vf = f"fps={FPS},scale={W}:{H},crop={cw}:{ch}:{(W - cw) // 2}:{max(0, min(H - ch, y))},scale={W}:{H}"
        self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{self.start + t0:.3f}", "-i", self.path,
                                      "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.idx = int(round(t0 * FPS)) - 1

    def frame(self, t):
        want = max(0, int(round(t * FPS)))
        if self.proc is None or want <= self.idx - 1 or want > self.idx + 90:
            self._open(want / FPS)
        while self.idx < want:
            buf = self.proc.stdout.read(W * H * 3)
            if len(buf) < W * H * 3:
                break
            self.last = buf
            self.idx += 1
        img = Image.frombytes("RGB", (W, H), self.last).convert("RGBA")
        if self.dim:
            img.alpha_composite(Image.new("RGBA", (W, H), (5, 5, 12, int(255 * self.dim))))
        return img


CLIPS = {}


def bottom_shade(base, strength=200):
    sh = np.zeros((H, W, 4), np.uint8)
    a = np.clip((np.linspace(0, 1, H) - 0.6) / 0.4, 0, 1) * strength
    sh[..., 3] = a[:, None].astype(np.uint8)
    base.alpha_composite(Image.fromarray(sh, "RGBA"))


# ---------------------------------------------------------------- terminal widget
def terminal(base, t, lines, top=620, h=900, appear=0.3, title="~/my-business  —  claude"):
    p = out_cubic(prog(t, appear, 0.45))
    if p <= 0.02:
        return
    cw = 980
    y0 = int(top + (1 - p) * 120)
    x0 = (W - cw) // 2
    win = rrect((cw, h), 28, hexc("0E0F16", 245), outline=hexc("2A2D3A"), width=3)
    paste(base, win, W / 2, y0 + h / 2, alpha=p)
    d = ImageDraw.Draw(base)
    for i, c in enumerate(["FF5F57", "FEBC2E", "28C840"]):
        d.ellipse([x0 + 30 + i * 40, y0 + 26, x0 + 54 + i * 40, y0 + 50], fill=hexc(c))
    d.text((x0 + cw / 2, y0 + 38), title, font=ImageFont.truetype(MONO, 26), fill=hexc("8A8FA8"), anchor="mm")
    f = ImageFont.truetype(MONO, 34)
    fb = ImageFont.truetype(MONOB, 34)
    y = y0 + 100
    for st, kind, s in lines:
        if t < st:
            break
        if kind == "cmd":
            n = int(clamp((t - st) / max(0.4, len(s) / 26)) * len(s))
            d.text((x0 + 36, y), "$", font=fb, fill=GREEN)
            d.text((x0 + 80, y), s[:n], font=f, fill=WHITE)
            if n < len(s) and int(t * 3) % 2 == 0:
                cx = x0 + 80 + f.getlength(s[:n])
                d.rectangle([cx + 2, y + 4, cx + 20, y + 40], fill=WHITE)
            y += 58
        elif kind == "out":
            a = int(255 * clamp((t - st) / 0.2))
            d.text((x0 + 36, y), s, font=f, fill=hexc("A9B1D6", a))
            y += 52
        elif kind == "ok":
            a = int(255 * clamp((t - st) / 0.2))
            d.text((x0 + 36, y), "✓ " + s, font=f, fill=hexc("3FD68A", a))
            y += 52
        elif kind == "claude":
            a = int(255 * clamp((t - st) / 0.2))
            d.text((x0 + 36, y), "●", font=fb, fill=(CORAL[0], CORAL[1], CORAL[2], a))
            d.text((x0 + 80, y), s, font=f, fill=hexc("F2E9E1", a))
            y += 52
        elif kind == "box":
            pb = out_back(prog(t, st, 0.35))
            bx = rrect((900, 250), 18, hexc("1B1D2A"), outline=CORAL, width=3, shadow=False)
            paste(base, bx, W / 2, y + 125, alpha=clamp(pb), scale=0.85 + 0.15 * pb)
            if pb > 0.6:
                d.text((x0 + 70, y + 30), s, font=fb, fill=WHITE)
                d.text((x0 + 70, y + 95), "❯ 1. Yes", font=fb, fill=GREEN)
                d.text((x0 + 70, y + 150), "  2. No, tell Claude what to change", font=f, fill=MUTED)
            y += 270
        elif kind == "gap":
            y += 30
    return y


def step_header(base, t, n, title, col=CORAL):
    p = out_back(prog(t, 0.05, 0.45))
    paste(base, chip(f"STEP {n}" if n else "PRO TIP", str(n) if n else "★", col), W / 2, 230 - (1 - p) * 60, alpha=clamp(p))
    p2 = out_back(prog(t, 0.2, 0.45))
    text(base, title, W / 2, 360, 76, WHITE, alpha=clamp(p2), scale=0.7 + 0.3 * p2, weight="Black")


# ---------------------------------------------------------------- scenes
def s_hook(base, t):
    ph = m.PH["hook"]
    cut = ph[2][0] - 0.1
    if t < cut:
        base.alpha_composite(CLIPS["hook"].frame(t))
        bottom_shade(base)
        p = out_back(prog(t, 0.1, 0.4))
        paste(base, rrect((760, 110), 55, hexc("FF3B4E"), shadow=False), W / 2, 1450, alpha=clamp(p), scale=0.7 + 0.3 * p)
        text(base, "STILL COPY-PASTING CODE?", W / 2, 1450, 46, WHITE, alpha=clamp(p), scale=0.7 + 0.3 * p, weight="Black")
    else:
        lt = t - cut
        base.alpha_composite(CLIPS["shop"].frame(lt))
        bottom_shade(base, 230)
        tte_text(base, "CLAUDE CODE", W / 2, 1230, 104, prog(lt, 0.0, 0.9))
        p = out_cubic(prog(lt, 0.5, 0.4))
        text(base, "your AI developer, in the terminal", W / 2, 1350 + (1 - p) * 30, 44, WHITE, alpha=p, weight="Bold")


def s_install(base, t):
    ph = m.PH["install"]
    step_header(base, t, 1, "Install it")
    terminal(base, t, [(ph[1][0], "cmd", "npm install -g @anthropic-ai/claude-code"),
                       (ph[2][0], "ok", "added claude-code"),
                       (ph[2][0] + 0.4, "out", "Needs Node.js 18+"),
                       ], h=520)
    p = out_cubic(prog(t, ph[2][0] + 0.5, 0.4))
    text(base, "Mac  ·  Linux  ·  Windows (WSL)", W / 2, 1260, 40, MUTED, alpha=p, weight="SemiBold")


def s_run(base, t):
    ph = m.PH["run"]
    step_header(base, t, 2, "Open your project")
    terminal(base, t, [(ph[0][0] + 0.6, "cmd", "cd my-business"),
                       (ph[1][0], "cmd", "claude"),
                       (ph[1][0] + 0.9, "out", "/login  ->  sign in with Claude"),
                       (ph[2][0], "ok", "Reading your codebase..."),
                       (ph[2][0] + 0.6, "ok", "Ready. What should we build?"),
                       ], h=640)


def s_ask(base, t):
    ph = m.PH["ask"]
    step_header(base, t, 3, "Just talk to it")
    terminal(base, t, [(ph[1][0], "cmd", "add a contact form and test it"),
                       (ph[2][0], "claude", "Reading src/pages/contact.html"),
                       (ph[2][0] + 0.45, "claude", "Writing ContactForm + validation"),
                       (ph[2][0] + 0.9, "claude", "Running tests..."),
                       (ph[2][0] + 1.4, "ok", "12 tests passed"),
                       ], h=700)


def s_approve(base, t):
    ph = m.PH["approve"]
    step_header(base, t, 4, "You stay the boss")
    terminal(base, t, [(0.4, "claude", "Edit src/pages/contact.html"),
                       (0.6, "out", "+ <form id=\"contact\"> ... </form>"),
                       (0.8, "gap", ""),
                       (ph[1][0], "box", "Do you want to make this edit?"),
                       (ph[2][0] + 0.3, "ok", "Edited contact.html"),
                       ], h=820)


def s_tip(base, t):
    ph = m.PH["tip"]
    step_header(base, t, 0, "Give it a memory", YELLOW)
    terminal(base, t, [(ph[0][0] + 0.5, "cmd", "/init"),
                       (ph[1][0], "ok", "Created CLAUDE.md"),
                       (ph[1][0] + 0.4, "out", "# Project rules"),
                       (ph[1][0] + 0.7, "out", "- Use Hindi + English copy"),
                       (ph[1][0] + 1.0, "out", "- Always run tests first"),
                       (ph[2][0], "claude", "Got it. I'll follow these rules."),
                       ], h=700)


def s_cta(base, t):
    ph = m.PH["cta"]
    base.alpha_composite(CLIPS["polaroid"].frame(t))
    bottom_shade(base, 160)
    p = out_back(prog(t, 0.1, 0.5))
    pulse = 1 + 0.05 * math.sin(t * 7) if t > 0.6 else 1
    paste(base, m.grad_rect((760, 160), 80, hexc("D97757"), hexc("8B3DFF")), W / 2, 1180, alpha=clamp(p),
          scale=(0.6 + 0.4 * p) * pulse)
    text(base, "FOLLOW", W / 2, 1180, 76, WHITE, alpha=clamp(p), scale=(0.6 + 0.4 * p) * pulse, weight="Black")
    p2 = out_back(prog(t, ph[1][0], 0.45))
    paste(base, rrect((900, 120), 30, hexc("0E0F16", 230), shadow=False), W / 2, 1360, alpha=clamp(p2))
    text(base, "Part 2: Claude Code + Gmail + Sheets", W / 2, 1360, 42, YELLOW, alpha=clamp(p2), weight="ExtraBold")


VOICE = {
    "hook": [("", "Still copy-pasting code from a chat window?"), ("", "What was that?!"),
             ("", "Let me show you Claude Code.")],
    "install": [("", "Step one: install it."), ("", "One npm command in your terminal."),
                ("", "You just need Node 18 or newer.")],
    "run": [("", "Step two: open your project folder,"), ("", "type claude, and log in."),
            ("", "Now it can see your whole codebase.")],
    "ask": [("", "Step three: just talk to it."), ("", "Add a contact form and test it."),
            ("", "It reads your files, writes the code, and runs the tests.")],
    "approve": [("", "Step four: you stay the boss."), ("", "It asks before it edits or runs anything."),
                ("", "Approve, or tell it what to change.")],
    "tip": [("", "Pro tip: type slash init."), ("", "It writes a CLAUDE.md file with your project rules,"),
            ("", "so it remembers how you like things done.")],
    "cta": [("", "Follow for part two,"), ("", "where Claude Code runs your Gmail and Google Sheets.")],
}
SPOKEN = {  # what Kokoro actually says (pronunciation-friendly)
    "hook": ["Still copy pasting code from a chat window?", "What was that?!", "Let me show you Claude Code."],
    "install": ["Step one: install it.", "One N P M command in your terminal.", "You just need Node eighteen, or newer."],
    "run": ["Step two: open your project folder,", "type claude, and log in.", "Now it can see your whole codebase."],
    "ask": ["Step three: just talk to it.", "Add a contact form, and test it.",
            "It reads your files, writes the code, and runs the tests."],
    "approve": ["Step four: you stay the boss.", "It asks before it edits, or runs anything.",
                "Approve, or tell it what to change."],
    "tip": ["Pro tip: type, slash init.", "It writes a Claude dot M D file, with your project rules,",
            "so it remembers how you like things done."],
    "cta": ["Follow for part two,", "where Claude Code runs your Gmail and Google Sheets."],
}
m.VOICE = VOICE
m.MIN_DUR = {k: 4.0 for k in VOICE}
m.RENDER = {"hook": s_hook, "install": s_install, "run": s_run, "ask": s_ask, "approve": s_approve, "tip": s_tip,
            "cta": s_cta}


def hits():
    out = []
    for name, st, _ in m.SCENES:
        if name == "hook":
            out.append(st + m.PH["hook"][1][0])
        if name == "approve":
            out.append(st + m.PH["approve"][2][0] + 0.3)
    return out


m.HIT_FN = hits


def make_voice(outdir, model_dir, voice="am_michael", speed=1.12):
    import soundfile as sf
    from kokoro_onnx import Kokoro

    os.makedirs(outdir, exist_ok=True)
    k = Kokoro(os.path.join(model_dir, "kokoro-v1.0.onnx"), os.path.join(model_dir, "voices-v1.0.bin"))
    for name, ps in SPOKEN.items():
        parts, sr = [], 24000
        for i, p in enumerate(ps):
            a, sr = k.create(p, voice=voice, speed=speed, lang="en-us")
            parts.append(a)
            if i < len(ps) - 1:
                parts.append(np.zeros(int(0.32 * sr), np.float32))
        wav = os.path.join(outdir, name + ".wav")
        sf.write(wav, np.concatenate(parts), sr)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-b:a", "160k", wav[:-4] + ".mp3"], check=True)
        os.remove(wav)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--clips" in args:
        i = args.index("--clips")
        hook, shop, pol = args[i + 1:i + 4]
        del args[i:i + 4]
    else:
        raise SystemExit("pass --clips <hook.mp4> <shop.mp4> <polaroid.mp4>")
    if "--make-voice" in args:
        i = args.index("--make-voice")
        make_voice("voice_claude_code", args[i + 1])
        del args[i:i + 2]
    CLIPS["hook"] = Clip(hook, 0.0)
    CLIPS["shop"] = Clip(shop, 0.3, zoom=1.35, cy=0.62, dim=0.15)
    CLIPS["polaroid"] = Clip(pol, 7.0, dim=0.25)
    sys.argv = [sys.argv[0], "--voice-dir", "voice_claude_code", "--tempo", "1.0"] + args
    m.main()
