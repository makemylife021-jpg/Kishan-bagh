"""Reel: "5 AI employees that cost Rs 0" - English, energetic, dark-humour, dark theme.

Re-uses the engine in make_reel.py (effects, karaoke subtitles, TTE decrypt, music,
sfx, ElevenLabs --voice-dir loading) and only defines new scenes + script.

    python reel_ai_employees.py --voice-dir voice_en -o ai_employees.mp4
"""
import math
import sys

from PIL import Image, ImageDraw

import make_reel as m
from make_reel import (W, YELLOW, WHITE, MUTED, clamp, prog, out_back, out_cubic, hexc, font, text, paste,
                       rrect, chip, check, tte_text)

RED = hexc("FF3B4E")
DARK = hexc("0B0B12")
m.BG = m.gradient_bg("050508", "1C0812")  # darker, moodier background
SKULL = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

VOICE = {  # (text spoken, subtitle). One ElevenLabs take per scene: voice_en/<scene>.mp3
    "hook": [("", "Your business is dying of paperwork."), ("", "So let's hire 5 employees who never sleep,"),
             ("", "and never ask for a raise.")],
    "claude": [("", "Employee #1: Claude."), ("", "Writes your captions, emails & proposals."),
               ("", "Doesn't even need coffee.")],
    "sheets": [("", "Number 2: Google Sheets."), ("", "Tracks every order and every rupee."),
               ("", "Your accountant is quietly crying.")],
    "gmail": [("", "Number 3: Gmail drafts."), ("", "20 follow-ups before breakfast."), ("", "You just hit send.")],
    "metricool": [("", "Number 4: Metricool."), ("", "Posts 3 times a day while you sleep."),
                  ("", "Or cry. Whatever works.")],
    "pipeboard": [("", "Number 5: Pipeboard."), ("", "Runs your Meta ads when you just ask."),
                  ("", "No agency. No drama.")],
    "cta": [("", "Total salary? Zero."), ("", "Sick days? Zero."),
            ("", "Follow for the full setup, before your competitor does.")],
}
MIN_DUR = {k: 4.2 for k in VOICE}


def stamp(base, t, start, label, col=RED, y=1380, rot=-9):
    p = out_back(prog(t, start, 0.35), 2.5)
    if p <= 0:
        return
    f = font(58, "Black")
    w = int(f.getlength(label)) + 70
    im = Image.new("RGBA", (w, 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 4, w - 5, 115], 18, outline=col, width=8, fill=(20, 0, 6, 200))
    d.text((w / 2, 60), label, font=f, fill=col, anchor="mm")
    paste(base, im, W / 2, y, alpha=clamp(p), scale=2.2 - 1.2 * clamp(p), rot=rot)


def employee_header(base, t, n, name, role, col):
    p = out_back(prog(t, 0.05, 0.45))
    paste(base, chip(f"EMPLOYEE #{n}", str(n), col), W / 2, 210 - (1 - p) * 60, alpha=clamp(p))
    p2 = out_back(prog(t, 0.2, 0.45))
    text(base, name, W / 2, 335, 96, WHITE, alpha=clamp(p2), scale=0.7 + 0.3 * p2, weight="Black")
    p3 = out_cubic(prog(t, 0.45, 0.4))
    text(base, role, W / 2, 425 + (1 - p3) * 30, 40, MUTED, alpha=p3, weight="Medium")
    p4 = out_back(prog(t, 0.7, 0.4))
    badge = rrect((300, 64), 32, hexc("1FA463"))
    paste(base, badge, W - 200, 520, alpha=clamp(p4), scale=0.6 + 0.4 * p4)
    text(base, "SALARY: ₹0", W - 200, 520, 32, WHITE, alpha=clamp(p4), weight="Black")


def card(base, t, h=760, fill=hexc("F7F6F2"), cy=1000):
    p = out_cubic(prog(t, 0.35, 0.45))
    cy = cy + (1 - p) * 120
    paste(base, rrect((940, h), 40, fill), W / 2, cy, alpha=p)
    return p, (W - 940) // 2, int(cy - h / 2)


# ---------------------------------------------------------------- scenes
def s_hook(base, t):
    ph = m.PH["hook"]
    # tombstone
    p = out_back(prog(t, 0.0, 0.6))
    ts = Image.new("RGBA", (520, 640), (0, 0, 0, 0))
    d = ImageDraw.Draw(ts)
    d.rounded_rectangle([20, 20, 500, 660], 240, fill=hexc("3A3A46"))
    d.rounded_rectangle([20, 20, 500, 660], 240, outline=hexc("5A5A6A"), width=8)
    d.text((260, 190), "R.I.P.", font=font(92, "Black"), fill=hexc("C9C9D6"), anchor="mm")
    d.text((260, 300), "YOUR BUSINESS", font=font(46, "ExtraBold"), fill=WHITE, anchor="mm")
    d.text((260, 370), "cause of death:", font=font(32, "Medium"), fill=hexc("A0A0B0"), anchor="mm")
    d.text((260, 420), "PAPERWORK", font=font(52, "Black"), fill=RED, anchor="mm")
    out = out_cubic(prog(t, ph[1][0] - 0.2, 0.4))
    paste(base, ts, W / 2, 820 - (1 - clamp(p)) * 400 - out * 260, alpha=clamp(p) * (1 - 0.75 * out),
          scale=1 - 0.35 * out, rot=(1 - clamp(p)) * 8)
    # grass line
    if p > 0:
        ImageDraw.Draw(base).rectangle([0, 1150 - int(out * 260), W, 1158 - int(out * 260)], fill=hexc("1FA463", int(180 * (1 - out))))
    # decrypt headline
    if t > ph[1][0]:
        tte_text(base, "NOW HIRING:", W / 2, 760, 80, prog(t, ph[1][0], 0.7))
        tte_text(base, "5 AI EMPLOYEES", W / 2, 870, 92, prog(t, ph[1][0] + 0.15, 0.8))
        perks = ["never sleep", "never complain", "never ask for a raise"]
        for i, s in enumerate(perks):
            pp = out_back(prog(t, ph[1][0] + 0.6 + i * 0.25 if i < 2 else ph[2][0], 0.4))
            col = RED if i == 2 else WHITE
            paste(base, rrect((620, 90), 45, (255, 255, 255, 22), outline=col, width=3, shadow=False),
                  W / 2, 1040 + i * 115, alpha=clamp(pp), scale=0.6 + 0.4 * pp)
            text(base, "✓ " + s if i < 2 else "✗ " + s, W / 2, 1040 + i * 115, 44, col, alpha=clamp(pp),
                 scale=0.6 + 0.4 * pp, weight="ExtraBold")


def s_claude(base, t):
    ph = m.PH["claude"]
    employee_header(base, t, 1, "Claude", "writer · planner · email machine", m.CLAUDE)
    p, x0, y0 = card(base, t, 720)
    if p < 0.05:
        return
    d = ImageDraw.Draw(base)
    d.ellipse([x0 + 34, y0 + 30, x0 + 84, y0 + 80], fill=m.CLAUDE)
    d.text((x0 + 104, y0 + 55), "Claude", font=font(36, "Bold"), fill=hexc("1F1E1D"), anchor="lm")
    msg = "Write 3 captions for my bakery"
    n = int(len(msg) * clamp(prog(t, 0.7, 0.9)))
    if n:
        f = font(36, "SemiBold")
        bw = int(f.getlength(msg)) + 60
        d.rounded_rectangle([x0 + 900 - bw, y0 + 120, x0 + 900, y0 + 200], 30, fill=hexc("ECE9DF"))
        d.text((x0 + 930 - bw, y0 + 160), msg[:n], font=f, fill=hexc("1F1E1D"), anchor="lm")
    lines = ["1. Fresh out the oven. Gone by noon.", "2. Carbs that love you back.",
             "3. Diet starts Monday. Cake starts now."]
    for i, s in enumerate(lines):
        pa = out_cubic(prog(t, ph[1][0] + 0.2 + i * 0.35, 0.3))
        if pa > 0:
            d.text((x0 + 50 + (1 - pa) * 30, y0 + 260 + i * 80), s, font=font(36, "Medium"),
                   fill=hexc("1F1E1D", int(255 * pa)))
    stamp(base, t, ph[2][0] + 0.25, "NO COFFEE NEEDED")


def s_sheets(base, t):
    ph = m.PH["sheets"]
    employee_header(base, t, 2, "Google Sheets", "accountant · CRM · stock keeper", m.SHEETS)
    p, x0, y0 = card(base, t, 720, WHITE)
    if p < 0.05:
        return
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([x0, y0, x0 + 940, y0 + 80], 40, fill=m.SHEETS)
    d.rectangle([x0, y0 + 50, x0 + 940, y0 + 80], fill=m.SHEETS)
    d.text((x0 + 40, y0 + 42), "Orders - auto", font=font(36, "Bold"), fill=WHITE, anchor="lm")
    rows = [("Riya", "Cake", 850, 1), ("Arjun", "Cookies", 320, 1), ("Hotel Sun", "Bread x40", 4200, 0),
            ("Meera", "Cupcakes", 600, 1)]
    total = 0
    for i, (c, it, a, paid) in enumerate(rows):
        pr = out_cubic(prog(t, 0.9 + i * 0.4, 0.3))
        y = y0 + 130 + i * 95
        d.line([x0 + 20, y + 70, x0 + 920, y + 70], fill=hexc("E3E3E3"), width=2)
        if pr <= 0:
            continue
        total += a * pr
        al = int(255 * pr)
        for x, s in [(40, c), (290, it), (560, f"₹{a:,}")]:
            d.text((x0 + x, y + 32), s, font=font(36, "Medium"), fill=hexc("202124", al), anchor="lm")
        pc = m.SHEETS if paid else hexc("F29900")
        d.rounded_rectangle([x0 + 760, y + 10, x0 + 900, y + 56], 23, fill=(pc[0], pc[1], pc[2], al))
        d.text((x0 + 830, y + 33), "Paid" if paid else "Due", font=font(28, "Bold"), fill=hexc("FFFFFF", al), anchor="mm")
    d.text((x0 + 40, y0 + 650), "TOTAL", font=font(40, "ExtraBold"), fill=hexc("137333"), anchor="lm")
    d.text((x0 + 900, y0 + 650), f"₹{int(total):,}", font=font(52, "Black"), fill=hexc("137333"), anchor="rm")
    stamp(base, t, ph[2][0] + 0.2, "ACCOUNTANT: CRYING")


def s_gmail(base, t):
    ph = m.PH["gmail"]
    employee_header(base, t, 3, "Gmail Drafts", "follow-ups · replies · proposals", hexc("EA4335"))
    p, x0, y0 = card(base, t, 720, WHITE)
    if p < 0.05:
        return
    d = ImageDraw.Draw(base)
    names = ["Riya's Bakery", "FitWithArjun", "Sun Hotel", "Meera Designs", "Glow Salon"]
    sent = 0
    for i, nme in enumerate(names):
        y = y0 + 50 + i * 120
        pr = out_cubic(prog(t, 0.8 + i * 0.25, 0.3))
        if pr <= 0:
            continue
        al = int(255 * pr)
        d.ellipse([x0 + 40, y + 10, x0 + 110, y + 80], fill=hexc("EA4335", al))
        d.text((x0 + 75, y + 45), nme[0], font=font(36, "Black"), fill=hexc("FFFFFF", al), anchor="mm")
        d.text((x0 + 140, y + 28), nme, font=font(36, "Bold"), fill=hexc("202124", al), anchor="lm")
        d.text((x0 + 140, y + 68), "Follow-up #2 - quick idea for you", font=font(28, "Medium"), fill=hexc("5F6368", al), anchor="lm")
        if t > ph[2][0] + i * 0.12:
            sent += 1
            d.rounded_rectangle([x0 + 760, y + 22, x0 + 900, y + 70], 24, fill=hexc("1FA463"))
            d.text((x0 + 830, y + 46), "SENT", font=font(28, "Black"), fill=WHITE, anchor="mm")
    cnt = int(20 * clamp(prog(t, ph[1][0], 1.2)))
    text(base, f"{cnt}/20 follow-ups ready", W / 2, y0 + 680, 40, hexc("EA4335"), weight="ExtraBold")
    stamp(base, t, ph[2][0] + 0.6, "YOU: JUST HIT SEND", hexc("FFD84D"))


def s_metricool(base, t):
    ph = m.PH["metricool"]
    employee_header(base, t, 4, "Metricool", "social media manager · night shift", hexc("4F7CFF"))
    for i, (tm, lab) in enumerate([("8 AM", "Reel"), ("2 PM", "Short"), ("9 PM", "Post")]):
        pp = out_back(prog(t, 0.6 + i * 0.25, 0.45))
        cx = W / 2 + (i - 1) * 310
        ph_img = rrect((270, 480), 36, hexc("15151F"), outline=hexc("4F7CFF"), width=4)
        paste(base, ph_img, cx, 900 + (1 - clamp(pp)) * 200, alpha=clamp(pp))
        if pp > 0.2:
            text(base, tm, cx, 760, 54, WHITE, alpha=clamp(pp), weight="Black")
            text(base, lab, cx, 830, 36, MUTED, alpha=clamp(pp), weight="SemiBold")
            for k, net in enumerate(["IG", "FB", "YT"]):
                text(base, net, cx - 70 + k * 70, 920, 32, YELLOW, alpha=clamp(pp), weight="Black")
            ok = out_back(prog(t, ph[1][0] + 0.3 + i * 0.2, 0.3))
            if ok > 0:
                paste(base, rrect((200, 56), 28, hexc("1FA463"), shadow=False), cx, 1030, alpha=clamp(ok))
                text(base, "Scheduled", cx, 1030, 30, WHITE, alpha=clamp(ok), weight="Black")
    if t > ph[1][0]:
        z = t - ph[1][0]
        for k in range(3):
            zp = (z * 0.8 + k * 0.33) % 1
            text(base, "z", 860 + k * 40 + zp * 40, 1240 - zp * 160 - k * 30, 50 + k * 14, hexc("A9B1D6"),
                 alpha=1 - zp, weight="Black")
        from PIL import ImageFont
        a = int(255 * out_cubic(prog(t, ph[1][0], 0.4)))
        ImageDraw.Draw(base).text((760, 1230), "☾", font=ImageFont.truetype(SKULL, 130),
                                  fill=(YELLOW[0], YELLOW[1], YELLOW[2], a), anchor="mm")
    stamp(base, t, ph[2][0] + 0.3, "WORKS WHILE YOU CRY", hexc("4F7CFF"))


def s_pipeboard(base, t):
    ph = m.PH["pipeboard"]
    employee_header(base, t, 5, "Pipeboard", "Meta ads manager · no agency fees", hexc("0866FF"))
    p, x0, y0 = card(base, t, 720, hexc("10131C"))
    if p < 0.05:
        return
    d = ImageDraw.Draw(base)
    msg = "Boost my best reel, ₹300/day"
    d.rounded_rectangle([x0 + 40, y0 + 40, x0 + 900, y0 + 120], 30, fill=hexc("23283A"))
    n = int(len(msg) * clamp(prog(t, 0.7, 0.9)))
    d.text((x0 + 70, y0 + 80), msg[:n], font=font(36, "SemiBold"), fill=WHITE, anchor="lm")
    vals = [0.2, 0.28, 0.35, 0.5, 0.62, 0.8, 1.0]
    for i, v in enumerate(vals):
        g = out_cubic(prog(t, ph[1][0] + 0.1 + i * 0.12, 0.4))
        h = int(380 * v * g)
        bx = x0 + 80 + i * 115
        d.rounded_rectangle([bx, y0 + 600 - h, bx + 80, y0 + 600], 14, fill=hexc("0866FF") if i < 6 else YELLOW)
    pct = int(312 * clamp(prog(t, ph[1][0] + 0.3, 1.2)))
    d.text((x0 + 900, y0 + 200), f"+{pct}% leads", font=font(52, "Black"), fill=YELLOW, anchor="rm")
    stamp(base, t, ph[2][0] + 0.2, "NO AGENCY. NO DRAMA.")


def s_cta(base, t):
    ph = m.PH["cta"]
    rows = [("SALARY", "₹0", ph[0][0] + 0.6), ("SICK DAYS", "0", ph[1][0] + 0.5), ("COMPLAINTS", "0", ph[1][0] + 0.9)]
    for i, (k, v, st) in enumerate(rows):
        pp = out_back(prog(t, st - 0.5, 0.4))
        y = 400 + i * 160
        paste(base, rrect((860, 130), 30, (255, 255, 255, 20), outline=hexc("FFFFFF", 60), width=2, shadow=False),
              W / 2, y, alpha=clamp(pp))
        text(base, k, W / 2 - 380, y, 52, MUTED, alpha=clamp(pp), weight="ExtraBold", anchor="l")
        pv = out_back(prog(t, st, 0.35), 3)
        text(base, v, W / 2 + 330, y, 84, hexc("1FA463"), alpha=clamp(pv), scale=2 - clamp(pv), weight="Black")
    st = ph[2][0]
    p3 = out_back(prog(t, st, 0.5))
    pulse = 1 + 0.05 * math.sin(t * 7) if t > st + 0.5 else 1
    paste(base, m.grad_rect((760, 160), 80, hexc("FF3B4E"), hexc("8B3DFF")), W / 2, 1000, alpha=clamp(p3),
          scale=(0.6 + 0.4 * p3) * pulse)
    text(base, "FOLLOW", W / 2, 1000, 76, WHITE, alpha=clamp(p3), scale=(0.6 + 0.4 * p3) * pulse, weight="Black")
    p4 = out_cubic(prog(t, st + 0.5, 0.4))
    text(base, "for the full setup", W / 2, 1140 + (1 - p4) * 30, 48, WHITE, alpha=p4, weight="SemiBold")
    p5 = out_back(prog(t, st + 1.3, 0.45))
    if p5 > 0:
        from PIL import ImageFont
        d = ImageDraw.Draw(base)
        d.text((W / 2 - 300, 1290), "☠", font=ImageFont.truetype(SKULL, 80), fill=RED, anchor="mm")
        text(base, "before your competitor does", W / 2 + 50, 1290, 44, RED, alpha=clamp(p5), weight="ExtraBold")
    text(base, "Comment AUTOMATE for the free checklist", W / 2, 1450, 38, YELLOW,
         alpha=out_cubic(prog(t, st + 1.8, 0.4)), weight="Bold")


def hits():
    out = []
    for name, st, _ in m.SCENES:
        if name in ("claude", "sheets", "gmail", "metricool", "pipeboard"):
            out.append(st + m.PH[name][2][0] + 0.25)
    hook = [s for s in m.SCENES if s[0] == "hook"][0]
    out.append(hook[1] + 0.05)
    return out


m.VOICE = VOICE
m.MIN_DUR = MIN_DUR
m.RENDER = {"hook": s_hook, "claude": s_claude, "sheets": s_sheets, "gmail": s_gmail, "metricool": s_metricool,
            "pipeboard": s_pipeboard, "cta": s_cta}
m.HIT_FN = hits

if __name__ == "__main__":
    if "--voice-dir" not in sys.argv:
        sys.argv += ["--voice-dir", "voice_en"]
    m.main()
