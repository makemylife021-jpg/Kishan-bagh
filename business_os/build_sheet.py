"""Builds the 'One-Person AI Company - Client Engine' workbook (uploaded to Google Sheets)."""
import sys
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEAD = PatternFill("solid", fgColor="1A1035")
HFONT = Font(bold=True, color="FFFFFF")

PLAN = [
    ("Phase", "Step", "What", "Tool", "How (exact action)", "When", "Output / KPI"),
    ("A. Foundation", 1, "Pick offer: 'AI automation setup for small businesses'", "Claude",
     "Ask Claude: list 5 pains of shops/coaches/e-com; turn top 3 into fixed-price packages (Starter / Growth / Done-for-you)", "Day 1", "1-page offer + prices"),
    ("A. Foundation", 2, "Brand + profiles", "Canva, Instagram, Facebook, YouTube",
     "Same name/logo/bio everywhere; bio = result + CTA ('DM AUTOMATE')", "Day 1", "3 profiles ready"),
    ("A. Foundation", 3, "Business Gmail + signature + labels", "Gmail",
     "Labels: Leads / Replied / Proposal / Client / Invoice. Signature with WhatsApp + booking link", "Day 1", "Inbox organised"),
    ("A. Foundation", 4, "This Google Sheet = your CRM + log", "Google Sheets",
     "Tabs: Leads, Content Calendar, Activity Log. Every action gets a row (what / when / how)", "Day 1", "Single source of truth"),
    ("B. Automation stack", 5, "Claude skills", "Claude Code skills",
     "Skills already in repo: instagram-video-autopilot (scripts + render). Add: lead-research, outreach-writer, proposal-writer (see 'Claude Skills' tab)", "Week 1", "Repeatable 1-command workflows"),
    ("B. Automation stack", 6, "Social media autopilot", "Metricool",
     "Connect IG + FB + YT in one Metricool brand; schedule 3 posts/day (8 AM, 2 PM, 9 PM IST); review drafts before they go live", "Week 1", "21 posts/week"),
    ("B. Automation stack", 7, "Meta ads + leads", "Pipeboard (Meta Ads)",
     "Boost best Reel each week (Rs 200-500/day), Lead-gen form 'Free AI audit'; pull leads into Leads tab", "Week 2+", "Cost per lead < Rs 50"),
    ("B. Automation stack", 8, "Calendar discipline", "Google Calendar",
     "Recurring blocks: content 8/2/9, outreach 11 AM, follow-ups 5 PM, Sunday review", "Week 1", "Habit on autopilot"),
    ("C. Get clients", 9, "Build lead list (20/day)", "Claude + Google Maps + Instagram",
     "Search niche + city; add name, handle, email/phone, 1 pain you noticed to Leads tab", "Daily 11 AM", "20 new leads/day"),
    ("C. Get clients", 10, "Personal outreach", "Gmail drafts + Instagram DM",
     "Claude writes a personalised first line per lead; drafts in Gmail; YOU review and send", "Daily 11:30 AM", "20 messages/day"),
    ("C. Get clients", 11, "Follow-up 3x", "Gmail",
     "Day 3, Day 7, Day 14 follow-ups (templates in Gmail drafts)", "Daily 5 PM", "Reply rate 5-10%"),
    ("C. Get clients", 12, "Free 15-min AI audit call", "Google Calendar + Meet",
     "Send booking slot; show 1 automation live on the call", "On reply", "Call -> proposal"),
    ("C. Get clients", 13, "Proposal + close", "Claude + Google Docs",
     "Claude drafts proposal from call notes; 50% advance", "Within 24h of call", "Close rate 20-30%"),
    ("D. Deliver", 14, "Onboard client", "Google Sheets + Gmail",
     "Copy this template for the client; set up their Metricool/Sheets/Gmail automations", "Week 1 of client", "Live in 7 days"),
    ("D. Deliver", 15, "Monthly retainer report", "Metricool reports + Sheets",
     "Send growth numbers every month -> upsell", "Monthly", "Retention 6+ months"),
    ("E. Scale", 16, "Content -> inbound", "Reels/Shorts 3x day",
     "Topics from 'Content Calendar'; every video ends with CTA 'Comment AUTOMATE'", "Daily", "Inbound DMs"),
    ("E. Scale", 17, "Case studies", "Canva + Reels",
     "Turn every client result into a before/after Reel", "Per client", "Social proof"),
    ("E. Scale", 18, "Templates / digital products", "Gumroad/Instamojo",
     "Sell the Sheets + prompt pack you already use", "Month 3+", "Passive income"),
]

ROUTINE = [
    ("Time (IST)", "Block", "Tool", "Done when"),
    ("08:00", "Post #1 goes live (scheduled) + reply to comments 10 min", "Metricool / IG / FB / YT", "Replied to all comments"),
    ("09:00", "Plan day: check Leads tab + inbox", "Sheets, Gmail", "Top 3 tasks written"),
    ("11:00", "Lead research (20 leads)", "Claude, Maps, Instagram", "20 rows in Leads"),
    ("11:30", "Outreach: review Claude drafts and send", "Gmail, Instagram DM", "20 sent"),
    ("14:00", "Post #2 goes live + engage 15 min in niche", "Metricool", "15 comments on others' posts"),
    ("15:00", "Client work / calls", "Meet, Calendar", "Delivered"),
    ("17:00", "Follow-ups (D3 / D7 / D14)", "Gmail", "All due follow-ups sent"),
    ("18:00", "Batch tomorrow's 3 videos", "Claude skill + make_reel.py", "3 videos in Metricool drafts"),
    ("21:00", "Post #3 goes live + log the day in Activity Log", "Metricool, Sheets", "Log row added"),
    ("Sunday 19:00", "Weekly review: posts, leads, calls, revenue", "Metricool reports, Sheets", "Next week's topics chosen"),
]

TOPICS = [
    "One-person company: 5 AI employees that cost Rs 0",
    "Google Sheets + Claude = CRM that updates itself",
    "Gmail automation: reply to 50 leads in 10 minutes",
    "Claude skills: turn any task into a 1-word command",
    "Metricool: 21 posts a week while you sleep",
    "Pipeboard: run Meta ads by just asking",
    "How I find 20 clients a day with AI (no cold calling)",
    "AI follow-ups: the money is in the 3rd email",
    "Google Calendar autopilot for solo founders",
    "From zero to first client in 7 days with AI",
    "Stop hiring, start automating: the 1-person agency",
    "AI audit call script that closes",
    "Trending: AI agents doing your admin work",
    "Your business, but running at 3 AM",
    "5 Claude prompts every freelancer needs",
    "Turn 1 video into 10 posts with AI",
    "Biggest mistake solo founders make with AI",
    "How to price AI automation services",
    "Client onboarding in 1 click (Sheets + Gmail)",
    "Weekly review that makes you money",
    "The lazy genius' content system",
]

SKILLS = [
    ("Skill / automation", "Trigger (what you type)", "What it does", "Status"),
    ("instagram-video-autopilot", "\"Make 3 reels about X\"", "Writes scripts, renders 1080x1920 videos, queues posts", "In repo (.claude/skills)"),
    ("make_reel.py", "python videos/.../make_reel.py --voice-dir ...", "Motion-graphics reel + voice + karaoke subtitles + effects", "In repo"),
    ("lead-research (to build)", "\"Find 20 bakeries in Jaipur\"", "Returns leads with pain point, adds rows to Leads", "Planned"),
    ("outreach-writer (to build)", "\"Draft outreach for today's leads\"", "Personalised Gmail drafts, never auto-sends", "Planned"),
    ("proposal-writer (to build)", "\"Proposal for <client> from call notes\"", "Google Doc proposal with packages + price", "Planned"),
    ("Metricool scheduling", "\"Schedule tomorrow's 3 videos\"", "Creates IG/FB/YT drafts at 8/2/9 IST", "Connected"),
    ("Pipeboard Meta Ads", "\"Boost my best reel for Rs 300/day\"", "Creates campaign (needs your approval)", "Connector available"),
    ("Google Calendar", "\"Block outreach time daily\"", "Recurring events", "Connected"),
]


def sheet(ws, rows, widths):
    for r in rows:
        ws.append(list(r))
    for c in ws[1]:
        c.fill, c.font = HEAD, HFONT
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"


def main(out, log_rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "A-Z Plan"
    sheet(ws, PLAN, [18, 6, 40, 26, 60, 16, 26])
    sheet(wb.create_sheet("Daily Routine"), ROUTINE, [14, 50, 30, 30])
    sheet(wb.create_sheet("Leads"),
          [("Date added", "Business", "Niche", "City", "Contact (email/handle)", "Pain noticed", "Status",
            "Last touch", "Next follow-up", "Notes")], [12, 24, 16, 14, 28, 34, 14, 12, 14, 30])
    cal = [("Day", "Slot (IST)", "Topic", "Hook", "CTA", "Status")]
    for i, tpc in enumerate(TOPICS):
        cal.append((f"Day {i // 3 + 1}", ["08:00", "14:00", "21:00"][i % 3], tpc, "", "Comment AUTOMATE / Follow",
                    "Video ready (draft)" if i == 0 else "To make"))
    sheet(wb.create_sheet("Content Calendar"), cal, [8, 10, 52, 30, 26, 18])
    sheet(wb.create_sheet("Claude Skills"), SKILLS, [28, 40, 52, 22])
    sheet(wb.create_sheet("Activity Log"), [("Date", "Time (IST)", "What was done", "How (tool / method)", "Result / link")] + log_rows,
          [12, 10, 50, 40, 50])
    wb.save(out)


if __name__ == "__main__":
    import json
    main(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else [])
