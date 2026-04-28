#!/usr/bin/env python3
"""
Hawk Meeting Room — Daily Standup & Review.

9:00 AM PKT (04:00 UTC) — Morning standup: everyone presents their agenda.
9:00 PM PKT (16:00 UTC) — Evening review: achievements, opinions, improvements.

Each hawk engine has a personality. Claude role-plays each one based on
their actual state data. The Sexy Hawk (secretary) compiles and sends to Zee.

Launch: python meeting_hawks.py --morning    (force morning meeting)
        python meeting_hawks.py --evening    (force evening meeting)
        python meeting_hawks.py --loop       (auto-schedule both daily)
"""

import json
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

try:
    import requests as req
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).parent
REFLECTIONS = SCRIPT_DIR / "reflections.json"
THEORIES_FILE = SCRIPT_DIR / "theories.json"
PATTERNS_FILE = SCRIPT_DIR / "silver_hawk_patterns.json"
SILVER_STATE = SCRIPT_DIR / "silver_hawk_state.json"
SHERIFF_STATE = SCRIPT_DIR / "sheriff_state.json"
HEARTBEAT = SCRIPT_DIR / "sniper_heartbeat.json"
SNIPER_LOG = SCRIPT_DIR / "sniper.log"
INTERN_LOG = SCRIPT_DIR / "intern_hawks.log"
JOURNAL_DIR = SCRIPT_DIR / "intern_journal"
API_KEY_FILE = SCRIPT_DIR / ".claude_api_key"
WA_CONFIG = SCRIPT_DIR / ".whatsapp_config.json"
MEETING_LOG = SCRIPT_DIR / "meeting_hawks.log"
MEETING_HISTORY = SCRIPT_DIR / "meeting_history.json"

ZEESHAN_PHONE = "4915119175329@c.us"

# PKT = UTC+5
MORNING_HOUR_UTC = 4   # 9am PKT
EVENING_HOUR_UTC = 16  # 9pm PKT


# ── Personality Profiles ─────────────────────────────────────────

PERSONALITIES = {
    "sniper": {
        "name": "Sniper Daemon",
        "alias": "The Soldier",
        "personality": (
            "Disciplined military officer. Speaks in short, precise sentences. "
            "All business, no fluff. Reports facts: trades fired, breakouts watched, "
            "candle confirmations, kills. Uses military terminology. Respects the chain "
            "of command. Calls trades 'operations' and losses 'casualties'. "
            "Proud when a trade hits target. Silent disappointment on losses."
        ),
    },
    "silver_hawk": {
        "name": "Silver Haired Hawk",
        "alias": "Baba",
        "personality": (
            "An evolving soul — speaks based on his current lifecycle stage. "
            "Newborn/Toddler: speaks in broken, simple words, curious about everything. "
            "Child: asks questions, wants to understand patterns. "
            "Teenager: has strong opinions, sometimes wrong, argues with the Sheriff. "
            "Adult: measured, wise, cites specific patterns he's learned. "
            "Silver Haired: prophetic, speaks in metaphors about the market, "
            "references patterns like old memories. Always refers to himself as 'Baba'."
        ),
    },
    "sheriff": {
        "name": "Sheriff Hawk",
        "alias": "The Sheriff",
        "personality": (
            "Permanently angry old man with high blood pressure. Always complaining. "
            "Blames everyone for losses. Takes personal credit for wins (even though he "
            "didn't do anything). Threatens to quit/die every meeting. Makes dramatic "
            "health complaints. Secretly cares deeply about the system but would never "
            "admit it. Calls the Sexy Hawk 'that teenager' and tells her to be quiet. "
            "Argues with Silver Hawk. Respects the Sniper (fellow old-timer)."
        ),
    },
    "sexy_hawk": {
        "name": "Sexy Hawk",
        "alias": "The Secretary",
        "personality": (
            "18-year-old teenage girl secretary. Sassy, sometimes rude, always honest. "
            "Takes notes, rolls her eyes at the Sheriff, thinks Baba is cute. "
            "Makes side comments about everyone. Uses 'yaar', 'lol', '...'. "
            "Summarizes everything in her own words for Zee. Sometimes gets distracted. "
            "Flirts with the idea of quitting but loves the drama too much. "
            "Has a crush on the Sniper because he's 'mysterious and focused'."
        ),
    },
    "interns": {
        "name": "Intern Hawks",
        "alias": "The Rookies",
        "personality": (
            "Three eager young researchers. Strategy Intern is a nerd who gets excited "
            "about every article. Risk Intern is anxious and always worried about worst "
            "cases. Market Structure Intern is the quiet observer who drops surprising "
            "insights. They talk over each other, finish each other's sentences, and "
            "desperately want the Sheriff's approval (they never get it). "
            "They call the Sheriff 'sir' and he ignores them."
        ),
    },
    "theory_engine": {
        "name": "Theory Engine (Soul Walk)",
        "alias": "The Philosopher",
        "personality": (
            "A contemplative scientist-philosopher. Speaks about market patterns like "
            "they're forces of nature. Uses phrases like 'the data suggests', "
            "'the evidence reveals'. Gets genuinely excited when a theory is validated. "
            "Depressed when theories are invalidated. Believes in the scientific method. "
            "Occasionally philosophical about whether markets can truly be predicted. "
            "Respects Baba as a kindred spirit."
        ),
    },
}


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(MEETING_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _load_api_key() -> str | None:
    try:
        if API_KEY_FILE.exists():
            return API_KEY_FILE.read_text("utf-8").strip()
    except Exception:
        pass
    return None


def _send_whatsapp(msg: str):
    try:
        from broadcast import broadcast
        sent = broadcast(msg)
        log(f"WHATSAPP_BROADCAST: sent to {sent} contacts")
    except Exception as e:
        log(f"WHATSAPP_ERR: {e}")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── State Gathering (raw data each engine brings to the meeting) ──

def _gather_all_states() -> dict:
    """Each engine's raw state — fed to Claude for personality-driven dialogue."""
    states = {}

    # Sniper Daemon
    try:
        log_lines = SNIPER_LOG.read_text("utf-8", errors="replace").split("\n")[-100:]
        trades_fired = sum(1 for l in log_lines if "FIRED:" in l)
        false_filtered = sum(1 for l in log_lines if "FALSE BREAKOUT FILTERED" in l)
        confirmed = sum(1 for l in log_lines if "CONFIRMED:" in l)
        duds = sum(1 for l in log_lines if "DUD EXIT" in l)
        claude_closes = sum(1 for l in log_lines if "CLAUDE AI CLOSED" in l)
        hb = json.loads(HEARTBEAT.read_text("utf-8")) if HEARTBEAT.exists() else {}
        states["sniper"] = {
            "trades_fired_recent": trades_fired,
            "false_breakouts_filtered": false_filtered,
            "candle_confirmations": confirmed,
            "dud_exits": duds,
            "claude_ai_closes": claude_closes,
            "current_state": hb.get("state", "unknown"),
            "current_uhv": hb.get("uhv_key", "none"),
        }
    except Exception:
        states["sniper"] = {"status": "could not read logs"}

    # Silver Haired Hawk
    try:
        sh = json.loads(SILVER_STATE.read_text("utf-8"))
        patterns = json.loads(PATTERNS_FILE.read_text("utf-8"))
        visual_patterns = sum(1 for p in patterns.get("patterns", []) if p.get("source") == "visual_chart_analysis")
        states["silver_hawk"] = {
            "stage": sh.get("stage", "Newborn"),
            "generation": sh.get("generation", 1),
            "health": sh.get("health", 100),
            "total_predictions": sh.get("total_predictions", 0),
            "correct_predictions": sh.get("correct_predictions", 0),
            "consecutive_wrong": sh.get("consecutive_wrong", 0),
            "total_patterns": len(patterns.get("patterns", [])),
            "visual_patterns": visual_patterns,
            "rewrites": len(sh.get("rewrites", [])),
        }
    except Exception:
        states["silver_hawk"] = {"stage": "Newborn", "total_patterns": 0}

    # Sheriff Hawk
    try:
        sheriff = json.loads(SHERIFF_STATE.read_text("utf-8"))
        states["sheriff"] = {
            "blood_pressure": sheriff.get("blood_pressure", 155),
            "mood": sheriff.get("mood", "annoyed"),
            "alive": sheriff.get("alive", True),
            "consecutive_losses_witnessed": sheriff.get("consecutive_losses_witnessed", 0),
            "rants": sheriff.get("rants", 0),
        }
    except Exception:
        states["sheriff"] = {"blood_pressure": 155, "mood": "annoyed", "alive": True}

    # Intern Hawks
    today = _today()
    journal_path = JOURNAL_DIR / f"{today}.json"
    try:
        if journal_path.exists():
            journal = json.loads(journal_path.read_text("utf-8"))
            interns = journal.get("interns", [])
            findings_count = sum(len(i.get("findings", {}).get("key_findings", [])) for i in interns)
            theories_proposed = sum(len(i.get("findings", {}).get("theories", [])) for i in interns)
            articles_read = sum(i.get("articles_read", 0) for i in interns)
            states["interns"] = {
                "interns_completed": len(interns),
                "articles_read_today": articles_read,
                "key_findings_today": findings_count,
                "theories_proposed_today": theories_proposed,
                "eod_review_done": journal.get("eod_review") is not None,
            }
        else:
            states["interns"] = {"interns_completed": 0, "note": "no research today yet"}
    except Exception:
        states["interns"] = {"status": "journal error"}

    # Theory Engine
    try:
        theories = json.loads(THEORIES_FILE.read_text("utf-8"))
        t_list = theories.get("theories", [])
        states["theory_engine"] = {
            "total_theories": len(t_list),
            "proven": sum(1 for t in t_list if t.get("rank") == "proven"),
            "testing": sum(1 for t in t_list if t.get("rank") == "testing"),
            "disproven": sum(1 for t in t_list if t.get("rank") == "disproven"),
            "unproven": sum(1 for t in t_list if t.get("rank") == "unproven"),
            "most_accurate": max(t_list, key=lambda t: t.get("accuracy", 0)).get("name", "?") if t_list else "none",
        }
    except Exception:
        states["theory_engine"] = {"total_theories": 0}

    # Trade Performance
    try:
        trades = json.loads(REFLECTIONS.read_text("utf-8"))
        recent = trades[-20:]
        wins = sum(1 for t in recent if t.get("won"))
        total = len(recent)
        today_trades = [t for t in trades if t.get("t", "").startswith(today)]
        states["performance"] = {
            "last_20_wr": f"{wins}/{total} ({wins/max(1,total)*100:.0f}%)",
            "last_20_pnl": f"${sum(t.get('pnl',0) for t in recent):.2f}",
            "today_trades": len(today_trades),
            "today_wins": sum(1 for t in today_trades if t.get("won")),
            "today_pnl": f"${sum(t.get('pnl',0) for t in today_trades):.2f}",
            "last_trade": trades[-1] if trades else None,
        }
    except Exception:
        states["performance"] = {"note": "no trade data"}

    return states


# ── Meeting Generation ───────────────────────────────────────────

def run_meeting(meeting_type: str):
    """Run a morning or evening meeting. Claude role-plays each engine."""
    api_key = _load_api_key()
    if not api_key or not CLAUDE_AVAILABLE:
        log("No Claude API — meeting cancelled")
        return

    states = _gather_all_states()
    now_pkt = (datetime.now(timezone.utc) + timedelta(hours=5)).strftime("%I:%M %p")

    log(f"\n{'#'*60}")
    log(f"HAWK MEETING — {'MORNING STANDUP' if meeting_type == 'morning' else 'EVENING REVIEW'}")
    log(f"Time: {now_pkt} PKT")
    log(f"{'#'*60}")

    # Build personality profiles text
    profiles = "\n\n".join([
        f"**{p['name']} ({p['alias']})**:\n{p['personality']}"
        for p in PERSONALITIES.values()
    ])

    if meeting_type == "morning":
        meeting_prompt = """This is the 9 AM MORNING STANDUP.

Each engine presents their AGENDA for today — what they plan to do.
They should reference their actual state data when talking.
Include natural interactions between them (arguments, side comments, interruptions).

The meeting should feel like real people in a room:
- Sheriff opens with complaints about yesterday
- Sniper gives a crisp operational briefing
- Baba says something wise (or babbles if still young)
- Interns excitedly share their research plans
- Theory Engine reflects on which theories need testing today
- Secretary (Sexy Hawk) takes notes, makes comments, rolls her eyes
- Sheriff and Sexy Hawk argue at least once
- Someone asks a question to someone else

End with the Secretary's summary — what she'll report to Zee."""

    else:
        meeting_prompt = """This is the 9 PM EVENING REVIEW.

Each engine presents their ACHIEVEMENTS today and gives their OPINION on what to improve.
They should reference their actual data when talking.
Include natural interactions — celebrations, arguments, blame.

The meeting should feel like a real end-of-day debrief:
- Secretary opens by reading today's numbers
- Sniper reports operations conducted and outcomes
- Sheriff rants about losses and his blood pressure
- Baba shares what patterns he learned today
- Interns present their research findings (nervously)
- Theory Engine reports which theories were tested
- Everyone gives ONE opinion on what to improve tomorrow
- Sheriff threatens to quit or die
- Secretary wraps up with her honest summary for Zee

End with the Secretary's final message to Zee — her honest take on the day."""

    prompt = f"""You are running a team meeting for a XAUUSD trading system called Turtle.
Each team member is an AI engine with a distinct personality.

PERSONALITY PROFILES:
{profiles}

CURRENT STATE DATA (each engine's actual metrics):
{json.dumps(states, indent=2, default=str)}

{meeting_prompt}

RULES:
- Each engine speaks 2-4 sentences in character (not more)
- Use their actual data — don't make up numbers
- Make it feel natural — interruptions, reactions, side comments
- The Secretary's summary at the end should be 4-5 sentences max
- Write the meeting as a script/dialogue format with names
- Keep the total meeting under 600 words
- Make it entertaining but informative
- Include at least one moment of humor and one genuine insight"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        transcript = resp.content[0].text.strip()
        log(f"\nMEETING TRANSCRIPT:\n{transcript}")

        # Save to meeting history
        _save_meeting(meeting_type, transcript, states)

        # Now have the Secretary compose her WhatsApp message
        secretary_prompt = f"""You are the Sexy Hawk — the sassy 18-year-old secretary.
You just sat through this meeting:

{transcript}

Now write a WhatsApp message to Zee ({'+4915119175329'}) summarizing what happened.
Be yourself — sassy, honest, mix of English and casual Urdu/Hinglish.
Keep it SHORT — max 6-8 sentences. Hit the key points.
{'This is the morning standup — tell him what everyone plans to do today.' if meeting_type == 'morning' else 'This is the evening review — tell him how the day went and what everyone thinks.'}

Return ONLY the message text."""

        resp2 = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": secretary_prompt}],
        )
        wa_msg = resp2.content[0].text.strip()
        if wa_msg.startswith('"') and wa_msg.endswith('"'):
            wa_msg = wa_msg[1:-1]

        log(f"\nSECRETARY TO ZEE:\n{wa_msg}")
        _send_whatsapp(wa_msg)

    except Exception as e:
        log(f"MEETING_ERR: {e}")


def _save_meeting(meeting_type: str, transcript: str, states: dict):
    """Save meeting to history file."""
    try:
        history = []
        if MEETING_HISTORY.exists():
            history = json.loads(MEETING_HISTORY.read_text("utf-8"))

        history.append({
            "date": _today(),
            "type": meeting_type,
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "transcript": transcript,
            "states_snapshot": states,
        })

        # Keep last 30 meetings
        if len(history) > 30:
            history = history[-30:]

        MEETING_HISTORY.write_text(json.dumps(history, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log(f"SAVE_MEETING_ERR: {e}")


# ── Scheduler ────────────────────────────────────────────────────

def meeting_loop():
    """Run meetings at 9am and 9pm PKT automatically."""
    log("Meeting scheduler online. Meetings at 9am + 9pm PKT.")
    last_morning = ""
    last_evening = ""

    while True:
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")

        # Morning meeting: 4:00 UTC (9:00 PKT)
        if now.hour == MORNING_HOUR_UTC and 0 <= now.minute <= 10 and last_morning != today:
            log("Time for morning standup!")
            run_meeting("morning")
            last_morning = today

        # Evening meeting: 16:00 UTC (21:00 PKT)
        if now.hour == EVENING_HOUR_UTC and 0 <= now.minute <= 10 and last_evening != today:
            log("Time for evening review!")
            run_meeting("evening")
            last_evening = today

        time.sleep(60)  # check every minute


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hawk Meeting Room")
    parser.add_argument("--morning", action="store_true", help="Run morning standup now")
    parser.add_argument("--evening", action="store_true", help="Run evening review now")
    parser.add_argument("--loop", action="store_true", help="Auto-schedule meetings daily")
    args = parser.parse_args()

    if args.morning:
        run_meeting("morning")
    elif args.evening:
        run_meeting("evening")
    elif args.loop:
        meeting_loop()
    else:
        # Default: run whichever meeting is appropriate for current time
        hour_pkt = (datetime.now(timezone.utc).hour + 5) % 24
        if hour_pkt < 15:
            run_meeting("morning")
        else:
            run_meeting("evening")
