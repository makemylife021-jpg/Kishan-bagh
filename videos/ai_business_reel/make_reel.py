"""~30-second vertical reel: "Claude + Google Sheets + Canva = your business team".

* Hindi voice-over: Kokoro TTS (open source, runs offline; model files from
  github.com/thewh1teagle/kokoro-onnx releases) -> scene lengths follow the voice.
* Text effect: terminaltexteffects' Decrypt effect, parsed from its ANSI frames.
* Word-by-word karaoke subtitles, glitch/RGB-split slide transitions, zoom
  punches, camera shake, flashes, vignette + film grain.
* Generated music bed that ducks under the voice, whooshes, pops, riser + impact.

    pip install kokoro-onnx soundfile terminaltexteffects pillow numpy   # + ffmpeg
    python make_reel.py --models <dir with kokoro-v1.0.onnx, voices-v1.0.bin> -o out.mp4
"""
import argparse
import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
FD = "/usr/share/fonts/opentype/inter/"
_fc = {}


def font(size, weight="Bold"):
    k = (size, weight)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(f"{FD}Inter-{weight}.otf", size)
    return _fc[k]


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, start, dur):
    return clamp((t - start) / dur)


def out_cubic(x):
    return 1 - (1 - x) ** 3


def out_back(x, s=1.70158):
    x -= 1
    return x * x * ((s + 1) * x + s) + 1


def in_out(x):
    return 3 * x * x - 2 * x * x * x


def hexc(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


# ---------------------------------------------------------------- palette
BG1, BG2 = "#0B1020", "#1A1035"
WHITE = hexc("FFFFFF")
MUTED = hexc("A9B1D6")
YELLOW = hexc("FFD84D")
CLAUDE = hexc("D97757")
SHEETS = hexc("1FA463")
CANVA = hexc("8B3DFF")
CANVA2 = hexc("00C4CC")

TRANS = 0.35  # seconds of slide/glitch transition into each scene


def gradient_bg(c1, c2):
    a = np.array(hexc(c1)[:3], float)
    b = np.array(hexc(c2)[:3], float)
    y = np.linspace(0, 1, H)[:, None, None]
    x = np.linspace(0, 1, W)[None, :, None]
    m = clamp_arr(0.65 * y + 0.35 * x)
    img = a * (1 - m) + b * m
    return Image.fromarray(img.astype(np.uint8), "RGB").convert("RGBA")


def clamp_arr(a):
    return np.clip(a, 0, 1)


def blob_layer():
    lay = Image.new("RGBA", (W + 400, H + 400), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for (cx, cy, r, col) in [
        (300, 400, 380, hexc("8B3DFF", 90)),
        (1100, 900, 420, hexc("00C4CC", 70)),
        (400, 1700, 400, hexc("D97757", 80)),
        (1150, 2000, 300, hexc("1FA463", 70)),
    ]:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    return lay.filter(ImageFilter.GaussianBlur(140))


BG = gradient_bg(BG1, BG2)
BLOBS = blob_layer()


def background(t):
    img = BG.copy()
    ox = int(200 + 160 * math.sin(t * 0.35))
    oy = int(200 + 160 * math.cos(t * 0.27))
    img.alpha_composite(BLOBS.crop((ox, oy, ox + W, oy + H)))
    return img


# ---------------------------------------------------------------- drawing helpers
_tc = {}


def text_img(text, size, color, weight="Bold"):
    k = (text, size, color, weight)
    if k not in _tc:
        f = font(size, weight)
        l, t_, r, b = f.getbbox(text)
        im = Image.new("RGBA", (r - l + 8, b - t_ + 8), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((4 - l, 4 - t_), text, font=f, fill=color)
        _tc[k] = im
    return _tc[k]


def paste(base, im, cx, cy, alpha=1.0, scale=1.0, rot=0.0, anchor="c"):
    if alpha <= 0.01 or scale <= 0.01:
        return
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1.0:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    x = int(cx - im.width / 2) if anchor == "c" else int(cx)
    y = int(cy - im.height / 2)
    _safe_comp(base, im, x, y)


def _safe_comp(base, im, x, y):
    sx, sy = max(0, -x), max(0, -y)
    x, y = max(0, x), max(0, y)
    if sx >= im.width or sy >= im.height or x >= base.width or y >= base.height:
        return
    crop = im.crop((sx, sy, min(im.width, sx + base.width - x), min(im.height, sy + base.height - y)))
    base.alpha_composite(crop, (x, y))


def text(base, s, cx, cy, size, color=WHITE, alpha=1.0, scale=1.0, weight="Bold", anchor="c", rot=0.0):
    paste(base, text_img(s, size, color, weight), cx, cy, alpha, scale, rot, anchor)


def rrect(size, radius, fill, outline=None, width=0, shadow=True):
    w, h = size
    pad = 40 if shadow else 0
    im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([pad, pad + 14, pad + w, pad + h + 14], radius, fill=(0, 0, 0, 120))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    ImageDraw.Draw(im).rounded_rectangle([pad, pad, pad + w, pad + h], radius, fill=fill, outline=outline, width=width)
    return im


def grad_rect(size, radius, c1, c2):
    w, h = size
    a = np.array(c1[:3], float)
    b = np.array(c2[:3], float)
    m = np.linspace(0, 1, w)[None, :, None] * 0.6 + np.linspace(0, 1, h)[:, None, None] * 0.4
    arr = (a * (1 - m) + b * m).astype(np.uint8)
    im = Image.fromarray(arr, "RGB").convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius, fill=255)
    im.putalpha(mask)
    return im


def check(d, x, y, s, col, width=6):
    d.line([(x, y + s * 0.5), (x + s * 0.38, y + s * 0.85), (x + s, y + s * 0.1)], fill=col, width=width, joint="curve")


def chip(label, num, col):
    f = font(40, "ExtraBold")
    tw = f.getlength(label)
    w = int(tw + 150)
    im = Image.new("RGBA", (w, 84), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, 83], 42, fill=(255, 255, 255, 28), outline=col, width=3)
    d.ellipse([10, 10, 74, 74], fill=col)
    fn = font(30, "Black")
    d.text((42, 42), num, font=fn, fill=WHITE, anchor="mm")
    d.text((96, 42), label, font=f, fill=WHITE, anchor="lm")
    return im


def scene_header(base, t, num, label, col, title, subtitle=None):
    p = out_back(prog(t, 0.1, 0.5))
    paste(base, chip(label, num, col), W / 2, 230 - (1 - p) * 60, alpha=clamp(p))
    p2 = out_cubic(prog(t, 0.25, 0.5))
    text(base, title, W / 2, 360 + (1 - p2) * 50, 72, WHITE, alpha=p2, weight="Black")
    if subtitle:
        p3 = out_cubic(prog(t, 0.4, 0.5))
        text(base, subtitle, W / 2, 445 + (1 - p3) * 40, 40, MUTED, alpha=p3, weight="Medium")


def pop(t):
    POPS.append(t)
    return t


# ---------------------------------------------------------------- terminaltexteffects (TTE) decrypt
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
_tte = {}


def tte_frames(s):
    """Run terminaltexteffects' Decrypt effect and parse each ANSI frame into [(char, rgb)]."""
    if s not in _tte:
        import re
        from terminaltexteffects.effects.effect_decrypt import Decrypt
        from terminaltexteffects.utils.graphics import Color

        eff = Decrypt(s)
        eff.effect_config.final_gradient_stops = (Color("FFD84D"), Color("FFFFFF"))
        eff.effect_config.typing_speed = 2
        pat = re.compile(r"\x1b\[38;2;(\d+);(\d+);(\d+)m(.)\x1b\[0m|(.)")
        frames = []
        for fr in eff:
            row = []
            for m in pat.finditer(fr.split("\n")[-1]):
                if m.group(4) is not None:
                    row.append((m.group(4), (int(m.group(1)), int(m.group(2)), int(m.group(3)), 255)))
                else:
                    row.append((m.group(5), (255, 255, 255, 0)))
            frames.append(row)
        _tte[s] = frames
    return _tte[s]


def tte_text(base, s, cx, cy, size, p, alpha=1.0):
    """Draw the TTE decrypt animation of `s` at progress p (0..1)."""
    if p <= 0:
        return
    frames = tte_frames(s)
    row = frames[min(len(frames) - 1, int(p * (len(frames) - 1)))]
    f = ImageFont.truetype(MONO, size)
    adv = f.getlength("M")
    x0 = cx - adv * len(s) / 2
    d = ImageDraw.Draw(base)
    for i, (ch, col) in enumerate(row):
        if ch.strip() and col[3]:
            # soft glow
            d.text((x0 + i * adv + adv / 2, cy), ch, font=f, anchor="mm",
                   fill=(col[0], col[1], col[2], int(255 * alpha)))


# ---------------------------------------------------------------- scene: hook
def s_hook(base, t):
    ph = PH["hook"]
    swap = ph[1][0] - 0.1  # "Ab nahi" starts
    lines = [("Business ka", 0.0, WHITE), ("saara kaam", 0.35, WHITE), ("AKELE?", 0.7, YELLOW)]
    out = out_cubic(prog(t, swap - 0.2, 0.3))
    for i, (s, st, col) in enumerate(lines):
        p = out_back(prog(t, st, 0.4))
        size = 150 if i == 2 else 110
        y = 640 + i * 180 - out * 300
        text(base, s, W / 2, y, size, col, alpha=clamp(p) * (1 - out), scale=0.6 + 0.4 * p, weight="Black",
             rot=(-3 if i == 2 else 0))
    if t > swap:
        tte_text(base, "AB NAHI.", W / 2, 700, 130, prog(t, swap, 0.9))
        st2 = ph[2][0]
        p2 = out_cubic(prog(t, st2, 0.4))
        text(base, "Ye 3 AI tools", W / 2, 880 + (1 - p2) * 40, 78, YELLOW, alpha=p2, weight="ExtraBold")
        text(base, "aapki team ban jaayenge", W / 2, 980 + (1 - p2) * 40, 58, WHITE, alpha=p2, weight="SemiBold")
        for i, (col, name) in enumerate([(CLAUDE, "Claude"), (SHEETS, "Sheets"), (CANVA, "Canva")]):
            pp = out_back(prog(t, st2 + 0.3 + i * 0.15, 0.4))
            cx = W / 2 + (i - 1) * 300
            paste(base, rrect((240, 96), 48, col), cx, 1220, alpha=clamp(pp), scale=0.5 + 0.5 * pp)
            text(base, name, cx, 1220, 44, WHITE, alpha=clamp(pp), scale=0.5 + 0.5 * pp, weight="ExtraBold")
        if t > st2 + 0.8:
            yy = 1420 + 18 * math.sin(t * 9)
            text(base, "↓", W / 2, yy, 110, YELLOW, alpha=out_cubic(prog(t, st2 + 0.8, 0.3)), weight="Black")


# ---------------------------------------------------------------- scene: claude
CHAT_USER = "Mere bagh ke liye 3 Instagram captions likho"
CHAT_AI = [
    "1. Taaza phal, seedha bagh se aapke ghar tak.",
    "2. 100% organic - swaad jo yaad rahe.",
    "3. Aaj order karein, kal taaza delivery!",
]


def wrap(s, f, maxw):
    words, lines, cur = s.split(), [], ""
    for w_ in words:
        test = (cur + " " + w_).strip()
        if f.getlength(test) <= maxw:
            cur = test
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def s_claude(base, t):
    scene_header(base, t, "1", "CLAUDE", CLAUDE, "Likhna & sochna", "Captions, replies, plans, ideas")
    p = out_cubic(prog(t, 0.45, 0.5))
    cw, ch = 940, 900
    card = rrect((cw, ch), 44, hexc("FAF9F5"))
    cy = 1080 + (1 - p) * 120
    paste(base, card, W / 2, cy, alpha=p)
    if p < 0.05:
        return
    x0, y0 = (W - cw) // 2, int(cy - ch / 2)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    # top bar
    d.ellipse([x0 + 34, y0 + 34, x0 + 84, y0 + 84], fill=CLAUDE)
    d.text((x0 + 59, y0 + 59), "*", font=font(44, "Black"), fill=WHITE, anchor="mm")
    d.text((x0 + 104, y0 + 59), "Claude", font=font(38, "Bold"), fill=hexc("1F1E1D"), anchor="lm")
    d.line([x0 + 30, y0 + 112, x0 + cw - 30, y0 + 112], fill=hexc("E8E4DA"), width=3)
    # user bubble typing
    f = font(36, "SemiBold")
    n = int(len(CHAT_USER) * clamp(prog(t, 0.9, 1.3)))
    typed = CHAT_USER[:n]
    if n > 0:
        lines = wrap(CHAT_USER, f, 600)
        shown, rem = [], typed
        for ln in lines:
            shown.append(rem[: len(ln)])
            rem = rem[len(ln) + 1:]
        bw = int(max(f.getlength(l) for l in lines)) + 60
        bh = 50 * len(lines) + 44
        bx1 = x0 + cw - 40
        d.rounded_rectangle([bx1 - bw, y0 + 150, bx1, y0 + 150 + bh], 30, fill=hexc("F0EEE6"))
        for i, ln in enumerate(shown):
            d.text((bx1 - bw + 30, y0 + 172 + i * 50), ln, font=f, fill=hexc("1F1E1D"))
    # thinking dots
    if 2.3 < t < 2.9:
        for i in range(3):
            a = 0.4 + 0.6 * abs(math.sin(t * 8 + i))
            cx = x0 + 70 + i * 34
            d.ellipse([cx - 10, y0 + 360 - 10, cx + 10, y0 + 360 + 10], fill=hexc("D97757", int(255 * a)))
    # AI answer lines
    fa = font(37, "Medium")
    yy = y0 + 330
    for i, s in enumerate(CHAT_AI):
        st = 2.9 + i * 0.45
        pa = out_cubic(prog(t, st, 0.35))
        if pa <= 0:
            break
        for ln in wrap(s, fa, cw - 120):
            d.text((x0 + 50 + (1 - pa) * 30, yy), ln, font=fa, fill=hexc("1F1E1D", int(255 * pa)))
            yy += 52
        yy += 22
    # done badge
    pd = out_back(prog(t, 4.5, 0.4))
    if pd > 0:
        d.rounded_rectangle([x0 + 50, y0 + ch - 120, x0 + 360, y0 + ch - 50], 35, fill=hexc("1FA463", int(255 * clamp(pd))))
        check(d, x0 + 75, y0 + ch - 103, 34, WHITE)
        d.text((x0 + 130, y0 + ch - 85), "5 second", font=font(36, "Bold"), fill=WHITE, anchor="lm")
    base.alpha_composite(lay)


# ---------------------------------------------------------------- scene: sheets
ROWS = [
    ("Ramesh", "Aam 5kg", 750, True),
    ("Sunita", "Amrood 3kg", 360, True),
    ("Hotel Raj", "Mix 40kg", 6400, False),
    ("Priya", "Papita 4kg", 240, True),
    ("Kirana Co.", "Aam 70kg", 10700, True),
]


def s_sheets(base, t):
    scene_header(base, t, "2", "GOOGLE SHEETS", SHEETS, "Hisaab-kitaab", "Orders, stock, payments - ek jagah")
    p = out_cubic(prog(t, 0.45, 0.5))
    cw, ch = 980, 860
    cy = 1060 + (1 - p) * 120
    paste(base, rrect((cw, ch), 30, WHITE), W / 2, cy, alpha=p)
    if p < 0.05:
        return
    x0, y0 = (W - cw) // 2, int(cy - ch / 2)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([x0, y0, x0 + cw, y0 + 90], 30, fill=SHEETS)
    d.rectangle([x0, y0 + 60, x0 + cw, y0 + 90], fill=SHEETS)
    d.text((x0 + 40, y0 + 45), "Orders - November", font=font(38, "Bold"), fill=WHITE, anchor="lm")
    cols = [("Customer", 40), ("Item", 330), ("Amount", 600), ("Status", 800)]
    hy = y0 + 120
    d.rectangle([x0 + 20, hy - 10, x0 + cw - 20, hy + 54], fill=hexc("E6F4EA"))
    for name, cx in cols:
        d.text((x0 + cx, hy + 22), name, font=font(32, "Bold"), fill=hexc("137333"), anchor="lm")
    fr = font(34, "Medium")
    total = 0
    for i, (cust, item, amt, paid) in enumerate(ROWS):
        st = 1.1 + i * 0.42
        pr = out_cubic(prog(t, st, 0.3))
        ry = hy + 80 + i * 92
        d.line([x0 + 20, ry + 70, x0 + cw - 20, ry + 70], fill=hexc("E0E0E0"), width=2)
        if pr <= 0:
            continue
        total += amt * pr
        a = int(255 * pr)
        off = (1 - pr) * 40
        d.text((x0 + 40 + off, ry + 30), cust, font=fr, fill=hexc("202124", a), anchor="lm")
        d.text((x0 + 330 + off, ry + 30), item, font=fr, fill=hexc("202124", a), anchor="lm")
        d.text((x0 + 600 + off, ry + 30), f"₹{amt:,}", font=fr, fill=hexc("202124", a), anchor="lm")
        pc = SHEETS if paid else hexc("F29900")
        d.rounded_rectangle([x0 + 800, ry + 8, x0 + 940, ry + 54], 23, fill=(pc[0], pc[1], pc[2], a))
        d.text((x0 + 870, ry + 31), "Paid" if paid else "Due", font=font(28, "Bold"), fill=hexc("FFFFFF", a), anchor="mm")
    # total row
    tp = out_back(prog(t, 3.4, 0.45))
    if tp > 0:
        ty = y0 + ch - 120
        d.rounded_rectangle([x0 + 20, ty, x0 + cw - 20, ty + 90], 20, fill=hexc("E6F4EA", int(255 * clamp(tp))))
        d.text((x0 + 50, ty + 45), "TOTAL (auto)", font=font(38, "ExtraBold"), fill=hexc("137333"), anchor="lm")
        cnt = int(18450 * out_cubic(prog(t, 3.4, 1.0)))
        d.text((x0 + cw - 50, ty + 45), f"₹{cnt:,}", font=font(50, "Black"), fill=hexc("137333"), anchor="rm")
    base.alpha_composite(lay)


# ---------------------------------------------------------------- scene: canva
def poster(kind):
    w, h = 420, 520
    if kind == 0:
        im = grad_rect((w, h), 34, hexc("FF8A00"), hexc("FF3D6E"))
        d = ImageDraw.Draw(im)
        d.text((w / 2, 120), "MANGO", font=font(72, "Black"), fill=WHITE, anchor="mm")
        d.text((w / 2, 200), "SALE", font=font(72, "Black"), fill=WHITE, anchor="mm")
        d.ellipse([w / 2 - 95, 255, w / 2 + 95, 445], fill=hexc("FFD84D"))
        d.text((w / 2, 335), "-20%", font=font(58, "Black"), fill=hexc("C2185B"), anchor="mm")
        d.text((w / 2, 395), "sirf aaj", font=font(30, "Bold"), fill=hexc("C2185B"), anchor="mm")
        d.text((w / 2, 480), "Instagram Post", font=font(26, "SemiBold"), fill=hexc("FFFFFF", 220), anchor="mm")
    elif kind == 1:
        im = grad_rect((w, h), 34, hexc("0F5132"), hexc("1FA463"))
        d = ImageDraw.Draw(im)
        d.text((w / 2, 90), "KISHAN BAGH", font=font(46, "Black"), fill=hexc("FFD84D"), anchor="mm")
        d.text((w / 2, 145), "Organic Fruits", font=font(34, "SemiBold"), fill=WHITE, anchor="mm")
        for i, s in enumerate(["Aam", "Amrood", "Papita", "Kela"]):
            yy = 215 + i * 58
            d.rounded_rectangle([60, yy, w - 60, yy + 46], 23, fill=hexc("FFFFFF", 40))
            d.text((90, yy + 23), s, font=font(30, "Bold"), fill=WHITE, anchor="lm")
            d.text((w - 90, yy + 23), "✓", font=font(30, "Bold"), fill=hexc("FFD84D"), anchor="rm")
        d.text((w / 2, 480), "Flyer", font=font(26, "SemiBold"), fill=hexc("FFFFFF", 220), anchor="mm")
    else:
        im = grad_rect((w, h), 34, CANVA, CANVA2)
        d = ImageDraw.Draw(im)
        d.ellipse([w / 2 - 70, 110, w / 2 + 70, 250], fill=hexc("FFFFFF", 60))
        d.polygon([(w / 2 - 22, 145), (w / 2 - 22, 215), (w / 2 + 38, 180)], fill=WHITE)
        d.text((w / 2, 320), "Bagh se", font=font(56, "Black"), fill=WHITE, anchor="mm")
        d.text((w / 2, 385), "Ghar tak", font=font(56, "Black"), fill=hexc("FFD84D"), anchor="mm")
        d.text((w / 2, 480), "Reel Cover", font=font(26, "SemiBold"), fill=hexc("FFFFFF", 220), anchor="mm")
    sh = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([40, 56, 40 + w, 56 + h], 34, fill=(0, 0, 0, 130))
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    sh.alpha_composite(im, (40, 40))
    return sh


POSTERS = [poster(i) for i in range(3)]


def s_canva(base, t):
    scene_header(base, t, "3", "CANVA", CANVA, "Design, bina designer", "Posts, flyers, reels - template se")
    spots = [(330, 900, -8, 0.8), (750, 1000, 7, 1.15), (540, 1250, -2, 1.5)]
    for i, (cx, cy, rot, st) in enumerate(spots):
        p = out_back(prog(t, st, 0.5))
        if p <= 0:
            continue
        float_y = 10 * math.sin(t * 2 + i)
        paste(base, POSTERS[i], cx, cy + float_y + (1 - clamp(p)) * 200, alpha=clamp(p),
              scale=(0.5 + 0.5 * p) * (0.9 if i < 2 else 1.0), rot=rot * p)
    # "magic" sparkle cursor
    if t > 2.4:
        pc = in_out(prog(t, 2.4, 1.2))
        x = 200 + pc * 680
        y = 1500 - math.sin(pc * math.pi) * 250
        text(base, "✦", x, y, 70, YELLOW, alpha=1 - prog(t, 3.8, 0.3), rot=t * 90, weight="Black")


# ---------------------------------------------------------------- scene: flow
def node(label, sub, col):
    im = rrect((760, 150), 40, (255, 255, 255, 24), outline=col, width=4)
    d = ImageDraw.Draw(im)
    d.ellipse([70, 75, 160, 165], fill=col)
    d.text((115, 120), label[0], font=font(48, "Black"), fill=WHITE, anchor="mm")
    d.text((190, 98), label, font=font(46, "ExtraBold"), fill=WHITE, anchor="lm")
    d.text((190, 148), sub, font=font(32, "Medium"), fill=MUTED, anchor="lm")
    return im


NODES = [node("Claude", "content likhta hai", CLAUDE), node("Sheets", "hisaab rakhta hai", SHEETS),
         node("Canva", "design banata hai", CANVA)]


def s_flow(base, t):
    ph = PH["flow"]
    tte_text(base, "AAPKI AI TEAM", W / 2, 330, 84, prog(t, 0.1, 1.3))
    for i, nd in enumerate(NODES):
        pn = out_back(prog(t, 0.35 + i * 0.3, 0.45))
        y = 560 + i * 230
        paste(base, nd, W / 2 + (1 - clamp(pn)) * (-300 if i % 2 == 0 else 300), y, alpha=clamp(pn))
        if i < 2:
            pa = out_cubic(prog(t, 0.6 + i * 0.3, 0.3))
            if pa > 0:
                d = ImageDraw.Draw(base)
                d.line([W / 2, y + 90, W / 2, y + 90 + 55 * pa], fill=YELLOW, width=8)
                if pa > 0.9:
                    d.polygon([(W / 2 - 18, y + 132), (W / 2 + 18, y + 132), (W / 2, y + 152)], fill=YELLOW)
    ps = out_back(prog(t, ph[1][0], 0.5))
    if ps > 0:
        sc = 0.7 + 0.3 * ps
        paste(base, rrect((900, 280), 50, hexc("FFD84D")), W / 2, 1380, alpha=clamp(ps), scale=sc)
        text(base, "8 ghante ka kaam", W / 2, 1325, 62, hexc("1A1035"), alpha=clamp(ps), scale=sc, weight="ExtraBold")
        strike = ph[2][0]
        if t > strike:
            ws = out_cubic(prog(t, strike, 0.25))
            ImageDraw.Draw(base).line([W / 2 - 250, 1325, W / 2 - 250 + 500 * ws, 1325], fill=hexc("E0245E"), width=9)
        pz = out_back(prog(t, strike + 0.15, 0.45))
        text(base, "→ sirf 1 ghanta", W / 2, 1430, 84, hexc("1A1035"), alpha=clamp(pz), scale=0.6 + 0.4 * pz, weight="Black")


# ---------------------------------------------------------------- scene: cta
def s_cta(base, t):
    p = out_back(prog(t, 0.05, 0.5))
    text(base, "Kaam kam.", W / 2, 620, 120, WHITE, alpha=clamp(p), scale=0.7 + 0.3 * p, weight="Black")
    p2 = out_back(prog(t, 0.35, 0.5))
    text(base, "Business zyada.", W / 2, 770, 110, YELLOW, alpha=clamp(p2), scale=0.7 + 0.3 * p2, weight="Black")
    p3 = out_back(prog(t, 0.9, 0.5))
    pulse = 1 + 0.04 * math.sin(t * 7) if t > 1.4 else 1
    btn = grad_rect((720, 150), 75, hexc("FF3D6E"), hexc("8B3DFF"))
    paste(base, btn, W / 2, 1080, alpha=clamp(p3), scale=(0.6 + 0.4 * p3) * pulse)
    text(base, "FOLLOW karo", W / 2, 1080, 64, WHITE, alpha=clamp(p3), scale=(0.6 + 0.4 * p3) * pulse, weight="Black")
    p4 = out_cubic(prog(t, 1.3, 0.5))
    text(base, "aur aisi AI tricks ke liye", W / 2, 1220 + (1 - p4) * 30, 46, MUTED, alpha=p4, weight="SemiBold")
    p5 = out_cubic(prog(t, 1.7, 0.5))
    text(base, "SAVE karo - baad mein kaam aayega", W / 2, 1480 + (1 - p5) * 30, 44, WHITE, alpha=p5, weight="Bold")


RENDER = {"hook": s_hook, "claude": s_claude, "sheets": s_sheets, "canva": s_canva, "flow": s_flow, "cta": s_cta}

# ---------------------------------------------------------------- voice-over script
# (Hindi text spoken by Kokoro TTS, Hinglish subtitle shown on screen)
VOICE = {
    "hook": [("सारा काम अकेले?", "Saara kaam akele?"), ("अब नहीं!", "Ab nahi!"),
             ("ये तीन एआई टूल्स, आपकी टीम बनेंगे।", "Ye 3 AI tools aapki team banenge")],
    "claude": [("पहला, क्लॉड।", "Pehla: Claude"), ("कैप्शन, रिप्लाई, प्लान।", "Captions, replies, plans"),
               ("घंटों का लिखना, सेकंडों में।", "Ghanton ka likhna, seconds mein")],
    "sheets": [("दूसरा, गूगल शीट्स।", "Doosra: Google Sheets"), ("ऑर्डर, स्टॉक, पेमेंट।", "Orders, stock, payment"),
               ("सारा हिसाब, अपने आप।", "Saara hisaab, apne aap")],
    "canva": [("तीसरा, कैनवा।", "Teesra: Canva"), ("पोस्ट, फ्लायर, रील।", "Post, flyer, reel"),
              ("प्रो डिज़ाइन, दो मिनट में।", "Pro design, 2 minute mein")],
    "flow": [("तीनों साथ मिलें, तो", "Teeno saath milein, to"), ("आठ घंटे का काम,", "8 ghante ka kaam"),
             ("सिर्फ़ एक घंटे में!", "sirf 1 ghante mein!")],
    "cta": [("ऐसी और ट्रिक्स के लिए,", "Aisi aur tricks ke liye"), ("फॉलो करें, और सेव करें!", "FOLLOW karein, SAVE karein!")],
}
MIN_DUR = {"hook": 3.6, "claude": 5.6, "sheets": 5.2, "canva": 5.0, "flow": 3.4, "cta": 3.2}
VOICE_DELAY, GAP, TAIL = 0.25, 0.12, 0.35
SR = 44100
PH = {}  # scene -> [(start, end)] of each spoken phrase, scene-local seconds
SUBS = []  # (global start, global end, subtitle text)
SCENES, POPS = [], []
DUR, NF = 30.0, 900


def synth_phrases(model_dir, voice, speed):
    """Kokoro TTS (open-source, offline). Returns {scene: [mono float32 @ SR per phrase]}."""
    from kokoro_onnx import Kokoro

    k = Kokoro(os.path.join(model_dir, "kokoro-v1.0.onnx"), os.path.join(model_dir, "voices-v1.0.bin"))
    out = {}
    for sc, items in VOICE.items():
        out[sc] = []
        for hi, _ in items:
            a, sr = k.create(hi, voice=voice, speed=speed, lang="hi")
            a = np.asarray(a, dtype=np.float64)
            # trim leading/trailing silence
            nz = np.where(np.abs(a) > 0.01)[0]
            if len(nz):
                a = a[max(0, nz[0] - int(0.02 * sr)): nz[-1] + int(0.05 * sr)]
            x_new = np.arange(int(len(a) * SR / sr)) / SR
            out[sc].append(np.interp(x_new, np.arange(len(a)) / sr, a))
    return out


def build_timeline(clips):
    """Scene durations follow the voice-over; fills SCENES, PH, SUBS, POPS, DUR, NF."""
    global DUR, NF
    t0 = 0.0
    for name in VOICE:
        cur, ph = VOICE_DELAY, []
        for (_, sub), c in zip(VOICE[name], clips[name]):
            ln = len(c) / SR
            ph.append((cur, cur + ln))
            SUBS.append((t0 + cur, t0 + cur + ln, sub))
            cur += ln + GAP
        dur = max(MIN_DUR[name], cur - GAP + TAIL)
        PH[name] = ph
        SCENES.append((name, t0, t0 + dur))
        t0 += dur
    DUR = round(t0 + 0.4, 2)
    NF = int(DUR * FPS)
    local = {
        "hook": [0.0, 0.35, 0.7],
        "claude": [0.1, 0.45, 2.9, 3.35, 3.8, 4.5],
        "sheets": [0.1, 0.45, 1.1, 1.52, 1.94, 2.36, 2.78, 3.4],
        "canva": [0.1, 0.8, 1.15, 1.5],
        "flow": [0.35, 0.65, 0.95],
        "cta": [0.05, 0.35, 0.9],
    }
    for name, st, _ in SCENES:
        for lt in local[name]:
            POPS.append(st + lt)
    POPS.append(SCENES[0][1] + PH["hook"][1][0])
    for ps in PH["hook"][2:]:
        for i in range(3):
            POPS.append(ps[0] + 0.3 + i * 0.15)
    fl = [s for s in SCENES if s[0] == "flow"][0][1]
    POPS.extend([fl + PH["flow"][1][0], fl + PH["flow"][2][0]])


# ---------------------------------------------------------------- subtitles (word-by-word karaoke)
def draw_subs(img, t):
    cur = [s for s in SUBS if s[0] - 0.05 <= t <= s[1] + 0.25]
    if not cur:
        return
    st, en, s = cur[-1]
    words = s.split()
    lens = np.cumsum([len(w) + 1 for w in words])
    frac = clamp((t - st) / max(0.01, en - st))
    active = int(np.searchsorted(lens / lens[-1], frac, side="right"))
    active = min(active, len(words) - 1)
    f = font(64, "Black")
    space = f.getlength(" ")
    # wrap into lines
    lines, line, wsum = [], [], 0
    for i, w in enumerate(words):
        wl = f.getlength(w)
        if line and wsum + space + wl > 940:
            lines.append(line)
            line, wsum = [], 0
        line.append(i)
        wsum += wl + (space if len(line) > 1 else 0)
    lines.append(line)
    pin = out_back(prog(t, st - 0.05, 0.25))
    d = ImageDraw.Draw(img)
    y0 = 1700 - (len(lines) - 1) * 42
    for li, ln in enumerate(lines):
        total = sum(f.getlength(words[i]) for i in ln) + space * (len(ln) - 1)
        x = W / 2 - total / 2
        y = y0 + li * 84 + (1 - clamp(pin)) * 30
        for i in ln:
            w = words[i]
            col = YELLOW if i == active else WHITE
            if i == active:
                wl = f.getlength(w)
                d.rounded_rectangle([x - 12, y - 46, x + wl + 12, y + 46], 18, fill=(0, 0, 0, 150))
            d.text((x, y), w, font=f, fill=col, anchor="lm", stroke_width=6, stroke_fill=(0, 0, 0, 255))
            x += f.getlength(w) + space


# ---------------------------------------------------------------- finishing effects
def _vignette():
    y, x = np.mgrid[0:H, 0:W]
    r = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
    a = (np.clip(r - 0.75, 0, 1) * 210).astype(np.uint8)
    lay = np.zeros((H, W, 4), np.uint8)
    lay[..., 3] = a
    return Image.fromarray(lay, "RGBA")


VIGNETTE = _vignette()
_rng = np.random.default_rng(7)
GRAIN = []
for _ in range(4):
    g = _rng.integers(0, 255, (H // 2, W // 2), dtype=np.uint8)
    lay = np.zeros((H // 2, W // 2, 4), np.uint8)
    lay[..., 0] = lay[..., 1] = lay[..., 2] = g
    lay[..., 3] = 9
    GRAIN.append(Image.fromarray(lay, "RGBA").resize((W, H), Image.NEAREST))


def rgb_split(img, k):
    if k < 1:
        return img
    r, g, b, a = img.split()
    r = r.transform(img.size, Image.AFFINE, (1, 0, -k, 0, 1, 0))
    b = b.transform(img.size, Image.AFFINE, (1, 0, k, 0, 1, 0))
    return Image.merge("RGBA", (r, g, b, a))


def zoom(img, s, dx=0, dy=0):
    if abs(s - 1) < 1e-3 and not dx and not dy:
        return img
    w, h = int(W * s), int(H * s)
    big = img.resize((w, h), Image.BILINEAR)
    x, y = (w - W) // 2 + dx, (h - H) // 2 + dy
    return big.crop((x, y, x + W, y + H))


def scene_frame(idx, t_global):
    name, st, en = SCENES[idx]
    img = background(t_global)
    RENDER[name](img, t_global - st)
    return img


def frame(i):
    t = i / FPS
    idx = max(k for k, s in enumerate(SCENES) if s[1] <= t)
    name, st, _ = SCENES[idx]
    lt = t - st
    glitch = 0
    if idx > 0 and lt < TRANS:
        x = in_out(lt / TRANS)
        prev = scene_frame(idx - 1, t)
        cur = scene_frame(idx, t)
        img = Image.new("RGBA", (W, H))
        off = int(H * x)
        img.paste(prev.crop((0, off, W, H)), (0, 0))
        if off > 0:
            img.paste(cur.crop((0, 0, W, off)), (0, H - off))
        glitch = 22 * math.sin(math.pi * x)
    else:
        img = scene_frame(idx, t)
    # zoom punch after each cut + shake on "AKELE?" and on the strike-through
    punch = 1 + 0.06 * (1 - out_cubic(prog(lt, TRANS if idx else 0, 0.45)))
    dx = dy = 0
    shakes = [SCENES[0][1] + 0.7]
    fl = [s for s in SCENES if s[0] == "flow"][0][1]
    shakes.append(fl + PH["flow"][2][0])
    for sh in shakes:
        if 0 <= t - sh < 0.35:
            amp = 16 * (1 - (t - sh) / 0.35)
            dx += int(amp * math.sin(t * 90))
            dy += int(amp * math.cos(t * 77))
    img = zoom(img, punch if (dx == 0 and dy == 0) else max(punch, 1.03), dx, dy)
    img = rgb_split(img, glitch)
    # flash on scene cuts and on the "1 ghanta" reveal
    flashes = [s[1] for s in SCENES[1:]] + [fl + PH["flow"][2][0] + 0.15]
    fa = max([0] + [0.55 * (1 - (t - f) / 0.25) for f in flashes if 0 <= t - f < 0.25])
    if fa > 0:
        img.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fa))))
    img.alpha_composite(VIGNETTE)
    img.alpha_composite(GRAIN[(i // 3) % 4])
    draw_subs(img, t)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=(255, 255, 255, 40))
    d.rectangle([0, 0, int(W * t / DUR), 10], fill=YELLOW)
    d.text((W / 2, 1855), "@kishanbagh", font=font(32, "SemiBold"), fill=hexc("FFFFFF", 120), anchor="mm")
    fade = min(1, t / 0.25, (DUR - t) / 0.4)
    if fade < 1:
        img = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), img, max(0, fade))
    return img.convert("RGB")


# ---------------------------------------------------------------- audio
def music(n, tt, rng):
    mix = np.zeros(n)
    bpm = 112
    beat = 60 / bpm
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 261.63, 329.63], [196.0, 246.94, 293.66]]
    bar = 4 * beat
    for b in range(int(DUR / bar) + 1):
        s0 = int(b * bar * SR)
        s1 = min(n, int((b + 1) * bar * SR))
        if s0 >= n:
            break
        seg = tt[s0:s1] - b * bar
        env = np.minimum(1, seg / 0.3) * np.minimum(1, (bar - seg) / 0.3)
        for f in chords[b % 4]:
            for det in (0.997, 1.003):
                mix[s0:s1] += 0.05 * env * np.sin(2 * np.pi * f * det * seg)
        mix[s0:s1] += 0.12 * env * np.sin(2 * np.pi * chords[b % 4][0] / 2 * seg)
    for k in range(int(DUR / (beat / 2))):
        s0 = int(k * beat / 2 * SR)
        L = int(0.25 * SR)
        if s0 + L >= n:
            break
        f = chords[int(k * beat / 2 / bar) % 4][k % 3] * 2
        seg = np.arange(L) / SR
        mix[s0:s0 + L] += 0.06 * np.exp(-seg * 14) * np.sin(2 * np.pi * f * seg)
    drums_start = SCENES[1][1]
    for k in range(int(DUR / beat)):
        tb = k * beat
        if tb >= DUR - 0.5:
            break
        s0 = int(tb * SR)
        if tb >= drums_start or k % 2 == 0:
            L = min(int(0.35 * SR), n - s0)
            seg = np.arange(L) / SR
            kick = np.sin(2 * np.pi * np.cumsum(50 + 90 * np.exp(-seg * 30)) / SR) * np.exp(-seg * 9)
            mix[s0:s0 + L] += (0.55 if tb >= drums_start else 0.3) * kick
        if tb >= drums_start:
            h0 = int((tb + beat / 2) * SR)
            L = int(0.06 * SR)
            if h0 + L < n:
                hat = rng.standard_normal(L) * np.exp(-np.arange(L) / SR * 60)
                mix[h0:h0 + L] += 0.08 * np.diff(np.concatenate([[0], hat]))
            if k % 2 == 1 and s0 + int(0.18 * SR) < n:
                L = int(0.18 * SR)
                mix[s0:s0 + L] += 0.12 * rng.standard_normal(L) * np.exp(-np.arange(L) / SR * 22)
    return mix


def sfx(n, rng):
    out = np.zeros(n)
    for _, st, _ in SCENES[1:]:  # whooshes
        L = int(0.5 * SR)
        s0 = int((st - 0.25) * SR)
        seg = np.arange(L) / L
        noise = rng.standard_normal(L)
        k1 = np.convolve(noise, np.ones(40) / 40, "same")
        out[s0:s0 + L] += 0.5 * (k1 * (1 - seg) + noise * 0.25 * seg) * np.sin(np.pi * seg) ** 2
    for pt in sorted(set(round(p, 2) for p in POPS)):  # pops
        s0 = int(pt * SR)
        L = int(0.09 * SR)
        if s0 + L >= n:
            continue
        seg = np.arange(L) / SR
        f = 900 + 700 * np.exp(-seg * 40)
        out[s0:s0 + L] += 0.16 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-seg * 45)
    fl = [s for s in SCENES if s[0] == "flow"][0][1]  # riser into the reveal + impact
    hit = fl + PH["flow"][2][0]
    L = int(1.0 * SR)
    s0 = int((hit - 1.0) * SR)
    seg = np.arange(L) / SR
    out[s0:s0 + L] += 0.12 * (seg / 1.0) ** 2 * np.sin(2 * np.pi * np.cumsum(300 + 900 * seg) / SR)
    L = int(0.6 * SR)
    seg = np.arange(L) / SR
    out[int(hit * SR):int(hit * SR) + L] += 0.6 * np.sin(2 * np.pi * np.cumsum(45 + 60 * np.exp(-seg * 20)) / SR) * np.exp(-seg * 6)
    return out


def make_audio(path, clips):
    n = int(SR * DUR)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(1)
    voice = np.zeros(n)
    for name, st, _ in SCENES:
        for (ps, _), c in zip(PH[name], clips[name]):
            s0 = int((st + ps) * SR)
            voice[s0:s0 + len(c)] += c[: n - s0]
    voice /= max(1e-6, np.max(np.abs(voice))) / 0.9
    # ducking: music drops while the voice speaks
    env = np.convolve((np.abs(voice) > 0.02).astype(float), np.ones(int(0.25 * SR)) / int(0.25 * SR), "same")
    duck = 1 - 0.6 * np.clip(env * 3, 0, 1)
    bed = music(n, tt, rng) * duck * 0.55 + sfx(n, rng) * 0.6
    mix = np.tanh((bed + voice) * 1.1)
    fade = np.clip(np.minimum(tt / 0.3, (DUR - tt) / 1.0), 0, 1)
    mix *= fade
    mix /= np.max(np.abs(mix)) / 0.89
    data = (mix * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(np.repeat(data[:, None], 2, axis=1).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="ai_business_reel.mp4")
    ap.add_argument("--models", default=os.environ.get("KOKORO_DIR", "kokoro"),
                    help="folder with kokoro-v1.0.onnx and voices-v1.0.bin")
    ap.add_argument("--voice", default="hm_omega", help="Kokoro Hindi voice: hm_omega, hm_psi, hf_alpha, hf_beta")
    ap.add_argument("--speed", type=float, default=1.2)
    ap.add_argument("--still", type=float, nargs="*", help="render frames at these times to PNGs and exit")
    a = ap.parse_args()
    clips = synth_phrases(a.models, a.voice, a.speed)
    build_timeline(clips)
    print("scenes:", [(n, round(s, 2), round(e, 2)) for n, s, e in SCENES], "total", DUR)
    if a.still:
        for s in a.still:
            frame(int(s * FPS)).save(f"{a.out}_{s}.png")
        return
    wav = a.out + ".wav"
    make_audio(wav, clips)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "21",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", a.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(NF):
        proc.stdin.write(frame(i).tobytes())
        if i % 150 == 0:
            print(f"frame {i}/{NF}", flush=True)
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
