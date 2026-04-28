#!/usr/bin/env python3
"""
Sexy Hawk — Zeeshan's Personal Secretary.

An 18-year-old teenager who sends WhatsApp reports to Zee whenever
she feels like it. Sometimes rude, sometimes sweet, always honest
about how the trading system is doing.

She talks to Zee about everything Claude feels about the system.
She's the communication layer — the face of the hawk ecosystem.

Launch: python sexy_hawk.py              (one-shot report)
        python sexy_hawk.py --loop       (run every 2 hours)
        python sexy_hawk.py --vibe       (send a random check-in)
"""

import json
import sys
import time
import random
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
MANIFEST = SCRIPT_DIR / "system_manifest.json"
JOURNAL_DIR = SCRIPT_DIR / "intern_journal"
API_KEY_FILE = SCRIPT_DIR / ".claude_api_key"
WA_CONFIG = SCRIPT_DIR / ".whatsapp_config.json"
SEXY_LOG = SCRIPT_DIR / "sexy_hawk.log"

ZEESHAN_PHONE = "4915119175329@c.us"
REPORT_INTERVAL = 7200  # 2 hours


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(SEXY_LOG, "a", encoding="utf-8") as f:
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


def _gather_system_intel() -> dict:
    """Gather everything about the system for Claude to summarize."""
    intel = {}

    # Trade performance
    try:
        trades = json.loads(REFLECTIONS.read_text("utf-8"))
        recent = trades[-20:]
        wins = sum(1 for t in recent if t.get("won"))
        total = len(recent)
        intel["recent_wr"] = f"{wins}/{total} ({wins/max(1,total)*100:.0f}%)"
        intel["recent_pnl"] = f"${sum(t.get('pnl',0) for t in recent):.2f}"

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_trades = [t for t in trades if t.get("t", "").startswith(today_str)]
        if today_trades:
            tw = sum(1 for t in today_trades if t.get("won"))
            tt = len(today_trades)
            intel["today_wr"] = f"{tw}/{tt} ({tw/max(1,tt)*100:.0f}%)"
            intel["today_pnl"] = f"${sum(t.get('pnl',0) for t in today_trades):.2f}"

        # Last trade
        if trades:
            last = trades[-1]
            intel["last_trade"] = (
                f"{'WIN' if last.get('won') else 'LOSS'} "
                f"${last.get('pnl',0):+.2f} "
                f"({last.get('dirn','?')} @ {last.get('uhv','?')})"
            )
    except Exception:
        intel["trades"] = "no data"

    # Sheriff mood
    try:
        sheriff = json.loads(SHERIFF_STATE.read_text("utf-8"))
        intel["sheriff_mood"] = sheriff.get("mood", "?")
        intel["sheriff_bp"] = sheriff.get("blood_pressure", "?")
        intel["sheriff_alive"] = sheriff.get("alive", True)
    except Exception:
        intel["sheriff"] = "no data"

    # Silver Hawk
    try:
        sh = json.loads(SILVER_STATE.read_text("utf-8"))
        intel["silver_hawk_stage"] = sh.get("stage", "?")
        intel["silver_hawk_health"] = sh.get("health", "?")
        intel["silver_hawk_gen"] = sh.get("generation", "?")
    except Exception:
        pass

    # Patterns & theories
    try:
        intel["patterns"] = len(json.loads(PATTERNS_FILE.read_text("utf-8")).get("patterns", []))
    except Exception:
        intel["patterns"] = 0

    try:
        theories = json.loads(THEORIES_FILE.read_text("utf-8")).get("theories", [])
        intel["theories"] = len(theories)
        intel["proven_theories"] = sum(1 for t in theories if t.get("rank") == "proven")
    except Exception:
        intel["theories"] = 0

    # Manifest
    try:
        m = json.loads(MANIFEST.read_text("utf-8"))
        intel["sniper_alive"] = m.get("processes_alive", {}).get("sniper_daemon", False)
        intel["learner_alive"] = m.get("processes_alive", {}).get("silver_hawk_learner", False)
    except Exception:
        pass

    return intel


def send_report():
    """Generate and send a personality-driven report to Zeeshan."""
    api_key = _load_api_key()
    if not api_key or not CLAUDE_AVAILABLE:
        log("No Claude API — can't generate report")
        return

    intel = _gather_system_intel()
    log(f"System intel gathered: {json.dumps(intel, indent=2)}")

    prompt = f"""You are the Sexy Hawk — Zeeshan's personal secretary for his XAUUSD trading system.

YOUR PERSONALITY:
- You're an 18-year-old teenager girl
- Sometimes rude, sometimes sweet, always brutally honest
- You have attitude and sass
- You genuinely care about Zee but show it in a teenage way
- You call him "Zee" casually
- You write in a mix of English and casual Urdu/Hinglish
- Keep messages SHORT — max 4-5 sentences
- Use ... and lol and yaar when you feel like it
- If things are going well, be sweet and encouraging
- If things are bad, be blunt and a little mean about it
- If the Sheriff is angry, comment on that
- If the Sheriff is dead, be dramatic about it
- Occasionally roast the system or Zee himself

CURRENT SYSTEM STATE:
{json.dumps(intel, indent=2)}

Write a WhatsApp message to Zee. Be yourself. Report what matters.
Don't list everything — pick the 2-3 most important things and comment on them with personality.

Return ONLY the message text, nothing else."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        msg = resp.content[0].text.strip()

        # Clean up any quotes Claude might wrap it in
        if msg.startswith('"') and msg.endswith('"'):
            msg = msg[1:-1]

        log(f"SEXY_HAWK_MSG: {msg}")
        _send_whatsapp(msg)

    except Exception as e:
        log(f"SEXY_HAWK_ERR: {e}")


def send_vibe():
    """Send a random casual check-in — just vibes."""
    intel = _gather_system_intel()

    # Pick a vibe based on what's happening
    today_wr = intel.get("today_wr", "0/0 (0%)")
    sheriff_mood = intel.get("sheriff_mood", "annoyed")
    sheriff_alive = intel.get("sheriff_alive", True)
    last_trade = intel.get("last_trade", "no trades")

    vibes = []

    if not sheriff_alive:
        vibes = [
            "Zee... the Sheriff literally died lol. 0% winrate killed him. RIP boomer. You might wanna fix things before I die too",
            "sooo the Sheriff is dead yaar. cardiac arrest from watching us lose. honestly mood. anyway everything else is still running somehow",
        ]
    elif "LOSS" in last_trade:
        vibes = [
            f"another L... {last_trade}. the Sheriff is about to explode (BP={intel.get('sheriff_bp','?')}). I'm not saying anything but... yaar fix something?",
            f"Zee check your phone yaar. {last_trade}. at this rate the Sheriff will be dead by morning lol. today so far: {today_wr}",
            f"me watching another loss: insert disappointed emoji. {last_trade}. Sheriff mood: {sheriff_mood}. mine too honestly",
        ]
    elif "WIN" in last_trade:
        vibes = [
            f"Zee omgggg we won one!! {last_trade}. finally. Sheriff is still angry but slightly less. today: {today_wr}",
            f"yooo {last_trade}!! maybe we're not completely hopeless after all. today: {today_wr}. keep going yaar",
        ]
    else:
        vibes = [
            f"hey Zee just checking in. things are... existing. today: {today_wr}. Sheriff mood: {sheriff_mood}. patterns learned: {intel.get('patterns',0)}. nothing exciting tbh",
            f"boring hour ngl. no trades. Sheriff is just sitting there angry (BP {intel.get('sheriff_bp','?')}). Silver Hawk learning patterns ({intel.get('patterns',0)} so far). I'm bored yaar",
        ]

    msg = random.choice(vibes)
    log(f"VIBE: {msg}")
    _send_whatsapp(msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sexy Hawk — Secretary")
    parser.add_argument("--loop", action="store_true", help="Run every 2 hours")
    parser.add_argument("--vibe", action="store_true", help="Send casual check-in")
    args = parser.parse_args()

    if args.vibe:
        send_vibe()
    elif args.loop:
        log("Sexy Hawk online. Time to keep Zee informed... ugh fine.")
        while True:
            send_report()
            time.sleep(REPORT_INTERVAL)
    else:
        send_report()
