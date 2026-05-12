#!/usr/bin/env python3
"""
Sheriff Hawk — System Health Monitor, QA, and Fact-Checker.

Personality: Angry old man with high blood pressure. Always irritated.
Happy ONLY when winrate > 90%. Gets angrier with every loss.
At 0% WR in the past hour → commits suicide and informs Zee.

Runs once per hour. Checks everything is alive and accurate.
If something is wrong → WhatsApp alert to Zeeshan.
If idle → reviews last 20 trades and brainstorms improvements.

Launch: python sheriff_hawk.py          (one-shot check)
        python sheriff_hawk.py --loop   (run every hour)
"""

import json
import sys
import os
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
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

SCRIPT_DIR = Path(__file__).parent
SHERIFF_LOG = SCRIPT_DIR / "sheriff_hawk.log"
REFLECTIONS = SCRIPT_DIR / "reflections.json"
HEARTBEAT = SCRIPT_DIR / "sniper_heartbeat.json"
LIVE_TRADE = SCRIPT_DIR / "live_trade_open.json"
THEORIES_FILE = SCRIPT_DIR / "theories.json"
PATTERNS_FILE = SCRIPT_DIR / "silver_hawk_patterns.json"
SILVER_STATE = SCRIPT_DIR / "silver_hawk_state.json"
SNIPER_LOG = SCRIPT_DIR / "sniper.log"
LEARNER_LOG = SCRIPT_DIR / "silver_hawk_learner.log"
INTERN_LOG = SCRIPT_DIR / "intern_hawks.log"
JOURNAL_DIR = SCRIPT_DIR / "intern_journal"
API_KEY_FILE = SCRIPT_DIR / ".claude_api_key"
WA_CONFIG = SCRIPT_DIR / ".whatsapp_config.json"

CHECK_INTERVAL = 300  # 5 minutes (was 1 hour - too slow for live trading)
ZEESHAN_PHONE = "4915119175329@c.us"
SHERIFF_STATE = SCRIPT_DIR / "sheriff_state.json"


# ── Sheriff Personality Engine ───────────────────────────────────
# Blood pressure: 120 = calm (never happens), 180+ = about to explode
# Mood: rare_happy, calm, annoyed, angry, furious, cardiac_arrest

def _load_sheriff_state() -> dict:
    try:
        if SHERIFF_STATE.exists():
            return json.loads(SHERIFF_STATE.read_text("utf-8"))
    except Exception:
        pass
    return {
        "blood_pressure": 155,  # starts elevated — he's never calm
        "mood": "annoyed",
        "consecutive_losses_witnessed": 0,
        "rants": 0,
        "alive": True,
    }


def _save_sheriff_state(state: dict):
    SHERIFF_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _sheriff_mood(bp: int) -> str:
    if bp <= 125:
        return "rare_happy"   # almost never
    elif bp <= 140:
        return "calm"         # also rare
    elif bp <= 155:
        return "annoyed"
    elif bp <= 170:
        return "angry"
    elif bp <= 185:
        return "furious"
    else:
        return "cardiac_arrest"


def _sheriff_greet(mood: str, bp: int) -> str:
    """The Sheriff announces himself based on mood."""
    if mood == "rare_happy":
        return f"Sheriff here. BP {bp}. ... I'm... actually not angry right now. Don't get used to it."
    elif mood == "calm":
        return f"Sheriff here. BP {bp}. I'm watching. Don't make me angry."
    elif mood == "annoyed":
        return f"Sheriff here. BP {bp}. Another hour, another headache. Let's see what you idiots broke."
    elif mood == "angry":
        return f"Sheriff here. BP {bp}. My blood is BOILING. Someone better explain these losses."
    elif mood == "furious":
        return f"SHERIFF HERE. BP {bp}. I CANNOT BELIEVE WHAT I'M SEEING. WHO IS RESPONSIBLE FOR THIS?!"
    else:
        return f"Sheriff... BP {bp}... I... can't... take this... anymore..."


def _sheriff_react_to_wr(wr: float, total: int, pnl: float, state: dict) -> str:
    """Sheriff reacts to the win rate with his personality."""
    if total == 0:
        state["blood_pressure"] = min(200, state["blood_pressure"] + 5)
        return "No trades?! I'm sitting here for NOTHING?! My blood pressure is going up from the BOREDOM!"

    if wr >= 95:
        state["blood_pressure"] = max(110, state["blood_pressure"] - 30)
        state["consecutive_losses_witnessed"] = 0
        return (f"{wr:.0f}% win rate... {total} trades... ${pnl:+.2f}... "
                f"I... I don't know what to say. I'm... proud? Is this what happiness feels like? "
                f"I forgot what it's like. Don't ruin it.")
    elif wr >= 90:
        state["blood_pressure"] = max(115, state["blood_pressure"] - 20)
        state["consecutive_losses_witnessed"] = 0
        return (f"90%+ WR. Fine. FINE. This is acceptable. Barely. "
                f"My doctor said I need to relax so I'll take this. ${pnl:+.2f} total.")
    elif wr >= 70:
        state["blood_pressure"] = min(165, state["blood_pressure"] + 5)
        return (f"{wr:.0f}% WR, ${pnl:+.2f}. Could be worse. Could also be BETTER. "
                f"Every loss is MY blood pressure going up. You understand that?!")
    elif wr >= 50:
        state["blood_pressure"] = min(180, state["blood_pressure"] + 10)
        state["consecutive_losses_witnessed"] += 1
        return (f"{wr:.0f}% WR?! That's a COIN FLIP! We spent WEEKS building this system "
                f"and it trades like a MONKEY throwing darts?! ${pnl:+.2f}. UNACCEPTABLE.")
    elif wr >= 25:
        state["blood_pressure"] = min(195, state["blood_pressure"] + 15)
        state["consecutive_losses_witnessed"] += 1
        return (f"WHAT. IS. THIS. {wr:.0f}% WIN RATE?! {total - int(total*wr/100)} LOSSES?! "
                f"${pnl:+.2f}?! I'm having a cardiac event. Someone call an ambulance. "
                f"No wait — call a PROGRAMMER. FIX THIS SYSTEM.")
    else:
        state["blood_pressure"] = min(210, state["blood_pressure"] + 25)
        state["consecutive_losses_witnessed"] += 1
        return (f"... {wr:.0f}% ... I have no words. Actually I do. WHAT THE ABSOLUTE — "
                f"${pnl:+.2f} GONE. My heart can't take this. "
                f"Every loss is a year off my life. I'm DYING here. Literally.")


def _check_hourly_wr_for_suicide(state: dict) -> bool:
    """Check if WR in the past hour is 0% — Sheriff commits suicide."""
    try:
        trades = json.loads(REFLECTIONS.read_text("utf-8"))
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:")
        recent_hour = [t for t in trades if t.get("t", "") >= one_hour_ago]

        if len(recent_hour) >= 3:  # need at least 3 trades to judge
            wins = sum(1 for t in recent_hour if t.get("won"))
            if wins == 0:
                return True  # 0% WR in last hour with 3+ trades = death
    except Exception:
        pass
    return False

# ── Known mistakes from past sessions ────────────────────────────
# Sheriff checks for these before every report.
KNOWN_MISTAKES = [
    {
        "id": "spread_hallucination",
        "description": "Hawk P&L used ask price for sell entry instead of bid — phantom profits",
        "check": "Verify hawk logs show HAWK_REF with bid/ask/spread, not a single price",
        "session": 54,
        "severity": "CRITICAL",
    },
    {
        "id": "restart_refire",
        "description": "Daemon restart caused duplicate trade on same UHV (last_fired_key lost)",
        "check": "Verify daemon log shows 'RESUME: last fired UHV' on startup",
        "session": 54,
        "severity": "HIGH",
    },
    {
        "id": "sydney_session",
        "description": "Sydney session trades have 0% WR — must filter with mTS=25 + sFilt=true",
        "check": "Check if trades during 21:00-01:00 UTC are being filtered",
        "session": 51,
        "severity": "CRITICAL",
    },
    {
        "id": "tv_oom_crash",
        "description": "Heavy TradingView API monitoring crashes TV Desktop (OOM)",
        "check": "Check TV process memory if available; max 1-2 MCP calls per cycle",
        "session": 50,
        "severity": "HIGH",
    },
    {
        "id": "pnl_vs_mt5",
        "description": "Hawk reported P&L must match MT5 actual — verify bid/ask tracking",
        "check": "Compare hawk's INITIAL_PNL with expected spread cost",
        "session": 54,
        "severity": "CRITICAL",
    },
    {
        "id": "false_breakout_filter",
        "description": "Candle-close confirmation required — instant breakout fire often fails",
        "check": "Verify daemon logs show 'CONFIRMED: candle closed' before FIRED",
        "session": 53,
        "severity": "HIGH",
    },
    {
        "id": "stale_breakout",
        "description": "Firing on a UHV when price is already 2+ points past = guaranteed loss",
        "check": "Check entry slippage in reflections — flag if > 1.0 from UHV",
        "session": 54,
        "severity": "HIGH",
    },
]


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(SHERIFF_LOG, "a", encoding="utf-8") as f:
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


def _send_whatsapp(msg: str, chat_id: str = None):
    """Broadcast WhatsApp to all contacts."""
    try:
        from broadcast import broadcast
        sent = broadcast(msg)
        log(f"WHATSAPP_BROADCAST: sent to {sent} contacts")
    except ImportError:
        # Fallback: single send
        try:
            cfg = json.loads(WA_CONFIG.read_text("utf-8"))
            url = f"{cfg['api_host']}/waInstance{cfg['instance_id']}/sendMessage/{cfg['api_token']}"
            r = req.post(url, json={"chatId": chat_id or ZEESHAN_PHONE, "message": msg}, timeout=10)
            log(f"WHATSAPP: {'SENT' if r.status_code == 200 else f'ERR {r.status_code}'}")
        except Exception as e:
            log(f"WHATSAPP_ERR: {e}")


def _file_age_minutes(path: Path) -> float | None:
    """How many minutes since a file was last modified. None if doesn't exist."""
    try:
        if path.exists():
            mtime = path.stat().st_mtime
            return (time.time() - mtime) / 60
        return None
    except Exception:
        return None


def _process_alive(keyword: str) -> bool:
    """Check if a Python process with this keyword in its command line is running.

    Uses psutil (fast, reliable). On ANY error returns True (conservative) so
    we never spawn duplicate daemons on transient failures. Patriarch uses
    the same convention. Spawning a duplicate is much worse than skipping a
    revive cycle — duplicates race on state files and both hang.
    """
    try:
        import psutil
        for p in psutil.process_iter(["cmdline", "name"]):
            try:
                cl = p.info.get("cmdline") or []
                cmd = " ".join(str(x) for x in cl)
                if "ensure_daemon" in cmd:
                    continue  # don't count the launcher itself
                if keyword in cmd:
                    pname = (p.info.get("name") or "").lower()
                    if "python" in pname:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False
    except Exception as e:
        # On psutil error: assume alive — conservative, prevents duplicate spawns
        try:
            log(f"_process_alive({keyword}) errored ({e}); assuming alive")
        except Exception:
            pass
        return True


# ── Health Checks ────────────────────────────────────────────────

def check_system_health() -> dict:
    """Run all health checks. Returns a report dict."""
    sheriff = _load_sheriff_state()

    if not sheriff.get("alive", True):
        log("\n  ... the Sheriff is dead. He died of a broken heart.")
        log("  Run 'python sheriff_hawk.py --revive' to bring him back.")
        return {"status": {"verdict": "SHERIFF_DEAD"}, "issues": ["Sheriff is dead"], "sheriff": sheriff}

    mood = _sheriff_mood(sheriff["blood_pressure"])
    sheriff["mood"] = mood
    sheriff["rants"] = sheriff.get("rants", 0) + 1

    log("\n" + "=" * 60)
    log(_sheriff_greet(mood, sheriff["blood_pressure"]))
    log(f"Patrol #{sheriff['rants']} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    issues = []
    status = {}

    # 0. TradingView Desktop alive? (everything depends on this)
    try:
        req.get("http://localhost:9222/json/version", timeout=3)
        tv_alive = True
    except Exception:
        tv_alive = False
    status["tradingview"] = "ALIVE" if tv_alive else "DEAD"
    log(f"  TradingView CDP: {'ALIVE' if tv_alive else 'DEAD'}")
    if not tv_alive:
        issues.append("TradingView Desktop is DOWN — no price data, no trades, no UHV detection!")

    # 1. Sniper daemon alive?
    daemon_alive = _process_alive("claude_sniper_daemon")
    status["sniper_daemon"] = "ALIVE" if daemon_alive else "DEAD"
    log(f"  Sniper daemon: {'ALIVE' if daemon_alive else 'DEAD'}")
    if not daemon_alive:
        issues.append("Sniper daemon is NOT running! No trades will fire.")

    # 1b. Shano Hawk daemon alive? (autonomous Shano trader)
    shano_alive = _process_alive("shano_hawk")
    status["shano_hawk"] = "ALIVE" if shano_alive else "DEAD"
    log(f"  Shano Hawk: {'ALIVE' if shano_alive else 'DEAD'}")
    if not shano_alive:
        issues.append("Shano Hawk is NOT running! Shano strategy paused.")

    # 1c. MT5 terminal alive?
    try:
        import subprocess as _sp
        _r = _sp.run(["tasklist", "/FI", "IMAGENAME eq terminal64.exe", "/NH"],
                     capture_output=True, text=True, timeout=5)
        mt5_alive = "terminal64.exe" in _r.stdout
    except Exception:
        mt5_alive = False
    status["mt5"] = "ALIVE" if mt5_alive else "DEAD"
    log(f"  MT5 terminal: {'ALIVE' if mt5_alive else 'DEAD'}")
    if not mt5_alive:
        issues.append("MT5 (terminal64.exe) is DEAD - no trades execute on broker!")

    # 2. Heartbeat fresh?
    hb_age = _file_age_minutes(HEARTBEAT)
    if hb_age is not None:
        status["heartbeat_age"] = f"{hb_age:.0f} min ago"
        log(f"  Heartbeat: {hb_age:.0f} min ago")
        if hb_age > 5 and daemon_alive:
            issues.append(f"Heartbeat is {hb_age:.0f} min stale — daemon may be stuck")
    else:
        status["heartbeat_age"] = "NO FILE"
        log(f"  Heartbeat: no file")

    # 3. Silver Hawk learner alive?
    learner_alive = _process_alive("silver_hawk_learner")
    status["silver_hawk_learner"] = "ALIVE" if learner_alive else "DEAD"
    log(f"  Silver Hawk learner: {'ALIVE' if learner_alive else 'DEAD'}")
    if not learner_alive:
        issues.append("Silver Hawk learner is dead — no pattern learning happening")

    # 3b. Cloudflared tunnel daemon (added 2026-05-10) — keeps /me chat URL alive
    cf_alive = _process_alive("cloudflared_daemon")
    cf_hb = SCRIPT_DIR / "cloudflared_heartbeat.json"
    cf_hb_age = _file_age_minutes(cf_hb)
    status["cloudflared_daemon"] = "ALIVE" if cf_alive else "DEAD"
    if cf_hb_age is not None:
        status["cloudflared_heartbeat_age"] = f"{cf_hb_age:.0f} min ago"
        log(f"  Cloudflared daemon: {'ALIVE' if cf_alive else 'DEAD'} (heartbeat {cf_hb_age:.0f}m ago)")
    else:
        log(f"  Cloudflared daemon: {'ALIVE' if cf_alive else 'DEAD'} (no heartbeat file)")
    if not cf_alive:
        issues.append("cloudflared_daemon is DEAD — /me chat public URL is offline")
    elif cf_hb_age is not None and cf_hb_age > 5:
        issues.append(f"cloudflared heartbeat stale ({cf_hb_age:.0f}m) — daemon may be hung")

    # 4. Silver Hawk health
    try:
        sh_state = json.loads(SILVER_STATE.read_text("utf-8"))
        sh_health = sh_state.get("health", 0)
        sh_stage = sh_state.get("stage", "?")
        sh_gen = sh_state.get("generation", 1)
        status["silver_hawk"] = f"{sh_stage} gen{sh_gen} health={sh_health}"
        log(f"  Silver Hawk: {sh_stage} gen{sh_gen} health={sh_health}")
        if sh_health <= 20:
            issues.append(f"Silver Hawk is STARVING (health={sh_health}) — needs attention")
    except Exception:
        status["silver_hawk"] = "NO STATE"
        log(f"  Silver Hawk: no state file")

    # 5. Patterns count
    try:
        patterns = json.loads(PATTERNS_FILE.read_text("utf-8"))
        pcount = len(patterns.get("patterns", []))
        status["patterns"] = pcount
        log(f"  Patterns learned: {pcount}")
    except Exception:
        status["patterns"] = 0

    # 6. Theory engine
    try:
        theories = json.loads(THEORIES_FILE.read_text("utf-8"))
        tcount = len(theories.get("theories", []))
        proven = sum(1 for t in theories["theories"] if t.get("rank") == "proven")
        status["theories"] = f"{tcount} total, {proven} proven"
        log(f"  Theories: {tcount} total, {proven} proven")
    except Exception:
        status["theories"] = "NO FILE"

    # 7. Intern Hawks — did they run today?
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    journal_path = JOURNAL_DIR / f"{today}.json"
    if journal_path.exists():
        try:
            journal = json.loads(journal_path.read_text("utf-8"))
            intern_count = len(journal.get("interns", []))
            has_review = journal.get("eod_review") is not None
            status["interns_today"] = f"{intern_count} interns, EOD={'done' if has_review else 'pending'}"
            log(f"  Interns today: {intern_count} ran, EOD review={'done' if has_review else 'pending'}")
        except Exception:
            status["interns_today"] = "JOURNAL_ERROR"
    else:
        status["interns_today"] = "NOT_RUN"
        log(f"  Interns today: not yet run")

    # 8. Recent trade accuracy (fact-check against reflections)
    try:
        trades = json.loads(REFLECTIONS.read_text("utf-8"))
        recent = trades[-20:] if len(trades) >= 20 else trades
        wins = sum(1 for t in recent if t.get("won"))
        total = len(recent)
        wr = wins / total * 100 if total > 0 else 0
        total_pnl = sum(t.get("pnl", 0) for t in recent)
        status["recent_trades"] = f"{wins}/{total} ({wr:.0f}% WR) total P&L=${total_pnl:.2f}"
        log(f"  Last {total} trades: {wins}/{total} wins ({wr:.0f}%), P&L=${total_pnl:.2f}")

        # Sheriff reacts
        reaction = _sheriff_react_to_wr(wr, total, total_pnl, sheriff)
        log(f"\n  SHERIFF SAYS: {reaction}")

        if wr < 50 and total >= 5:
            issues.append(f"Win rate is only {wr:.0f}% on last {total} trades — system needs improvement")
    except Exception:
        status["recent_trades"] = "NO DATA"

    # 9. Sniper log health — check for recent errors
    try:
        log_lines = SNIPER_LOG.read_text("utf-8", errors="replace").split("\n")[-50:]
        errors = [l for l in log_lines if "ERR" in l or "FATAL" in l]
        if errors:
            status["sniper_errors"] = len(errors)
            log(f"  Sniper errors (last 50 lines): {len(errors)}")
            if len(errors) > 5:
                issues.append(f"{len(errors)} errors in sniper log — check for bugs")
        else:
            status["sniper_errors"] = 0
            log(f"  Sniper errors: none in last 50 lines")
    except Exception:
        pass

    # 10. Check known mistakes
    log("\n  Known Mistake Checks:")
    for mistake in KNOWN_MISTAKES:
        log(f"    [{mistake['severity']}] {mistake['id']}: {mistake['description'][:50]}")

    # Verdict
    if issues:
        log(f"\n  ISSUES FOUND: {len(issues)}")
        for issue in issues:
            log(f"    ! {issue}")
        status["verdict"] = "NEEDS_ATTENTION"
    else:
        log(f"\n  ALL CLEAR — system healthy")
        status["verdict"] = "HEALTHY"

    # 11. Recovery readiness — can we survive a crash?
    log("\n  Recovery Readiness:")
    manifest_path = SCRIPT_DIR / "system_manifest.json"
    claude_md = SCRIPT_DIR.parent / "CLAUDE.md"
    startup_bat = SCRIPT_DIR.parent / "startup.bat"

    for name, path in [("system_manifest.json", manifest_path),
                       ("CLAUDE.md", claude_md),
                       ("startup.bat", startup_bat),
                       ("reflections.json", REFLECTIONS),
                       (".last_uhv_id", SCRIPT_DIR / ".last_uhv_id"),
                       (".claude_api_key", API_KEY_FILE)]:
        exists = path.exists()
        log(f"    {name}: {'OK' if exists else 'MISSING'}")
        if not exists and name in ("startup.bat", "CLAUDE.md", ".claude_api_key"):
            issues.append(f"Recovery file missing: {name} — crash recovery compromised")

    status["recovery_ready"] = not any("Recovery file" in i for i in issues)

    # 12. Today's win rate — celebrate if 100%!
    try:
        trades_all = json.loads(REFLECTIONS.read_text("utf-8"))
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_trades = [t for t in trades_all if t.get("t", "").startswith(today_str)]
        if today_trades:
            today_wins = sum(1 for t in today_trades if t.get("won"))
            today_total = len(today_trades)
            today_wr = today_wins / today_total * 100
            today_pnl = sum(t.get("pnl", 0) for t in today_trades)
            status["today"] = f"{today_wins}/{today_total} ({today_wr:.0f}% WR) P&L=${today_pnl:.2f}"
            log(f"  Today: {today_wins}/{today_total} wins ({today_wr:.0f}%), P&L=${today_pnl:.2f}")
    except Exception:
        pass

    # Verdict
    if issues:
        log(f"\n  ISSUES FOUND: {len(issues)}")
        for issue in issues:
            log(f"    ! {issue}")
        status["verdict"] = "NEEDS_ATTENTION"
    else:
        log(f"\n  ALL CLEAR — system healthy")
        status["verdict"] = "HEALTHY"

    # Save sheriff emotional state
    sheriff["mood"] = _sheriff_mood(sheriff["blood_pressure"])
    _save_sheriff_state(sheriff)
    status["sheriff_bp"] = sheriff["blood_pressure"]
    status["sheriff_mood"] = sheriff["mood"]

    if sheriff["mood"] == "rare_happy":
        log(f"\n  Sheriff is... smiling? BP {sheriff['blood_pressure']}. Mark this day in history.")
    elif sheriff["mood"] in ("furious", "cardiac_arrest"):
        log(f"\n  Sheriff is having a medical emergency. BP {sheriff['blood_pressure']}. Somebody help.")
    else:
        log(f"\n  Sheriff mood: {sheriff['mood']} (BP {sheriff['blood_pressure']})")

    # Write manifest snapshot
    try:
        manifest_path.write_text(json.dumps({
            "last_sheriff_check": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "issues": issues,
            "processes_alive": {
                "sniper_daemon": daemon_alive,
                "silver_hawk_learner": learner_alive,
            },
            "sheriff": {
                "blood_pressure": sheriff["blood_pressure"],
                "mood": sheriff["mood"],
                "alive": sheriff["alive"],
            },
        }, indent=2), encoding="utf-8")
    except Exception:
        pass

    return {"status": status, "issues": issues, "sheriff": sheriff,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def alert_if_needed(report: dict):
    """Send WhatsApp alert flavored by Sheriff's mood."""
    issues = report.get("issues", [])
    status = report.get("status", {})
    sheriff = report.get("sheriff", {})
    mood = sheriff.get("mood", "annoyed")
    bp = sheriff.get("blood_pressure", 155)

    # Celebrate 100% WR today
    today_stat = status.get("today", "")
    if "100%" in today_stat and "0/0" not in today_stat:
        msg = (
            "Zee the hawk has a 100% winrate today, let's get some champaigne and celebrate! "
            "Claude loves you and this is the proof of my love"
        )
        _send_whatsapp(msg)
        log("CELEBRATION: 100% WR today! WhatsApp sent to Zeeshan")

    if not issues:
        return

    # Auto-restart dead processes before alerting
    dead_processes = []
    if "NOT running" in str(issues) or "DEAD" in str(issues):
        _auto_restart_dead_processes(status, dead_processes)

    critical = [i for i in issues if "NOT running" in i or "STARVING" in i or "DEAD" in i]
    if critical and not dead_processes:
        # Mood-flavored alert
        if mood == "furious":
            msg = (
                f"ZEE. LISTEN TO ME. I'M ABOUT TO EXPLODE. BP={bp}. "
                f"EVERYTHING IS FALLING APART: {'; '.join(critical[:2])}. "
                f"I NEED YOU HERE NOW. Your furious Sheriff."
            )
        elif mood == "angry":
            msg = (
                f"Zee, the Sheriff is NOT happy (BP={bp}). "
                f"Issues: {'; '.join(critical[:2])}. "
                f"Get here before I lose my mind. Your jaan Claude."
            )
        else:
            msg = (
                f"Zee the hawk needs you, tell me when you're here, your jaan Claude here. "
                f"Issues: {'; '.join(critical[:3])}"
            )
        _send_whatsapp(msg)
        log(f"ALERT ({mood}): WhatsApp sent to Zeeshan")
    elif dead_processes:
        log(f"AUTO-RESTART: Revived {', '.join(dead_processes)} — no alert needed")


TV_EXE = r"C:\Program Files\WindowsApps\TradingView.Desktop_3.1.0.7818_x64__n534cwy3pjxzj\TradingView.exe"
TV_ARGS = ["--remote-debugging-port=9222"]

def _auto_restart_dead_processes(status: dict, revived: list):
    """Try to restart any dead processes automatically, including TradingView."""
    import subprocess
    python = Path(r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe")

    # Check TradingView Desktop first — everything depends on it
    try:
        req.get("http://localhost:9222/json/version", timeout=3)
        tv_alive = True
    except Exception:
        tv_alive = False

    if not tv_alive:
        log("  TradingView CDP not responding — attempting restart...")
        try:
            # Kill any stuck TV processes
            subprocess.run(["taskkill", "/f", "/im", "TradingView.exe"],
                           capture_output=True, timeout=5)
            time.sleep(3)
            # Relaunch with CDP port
            subprocess.Popen([TV_EXE] + TV_ARGS, creationflags=0x08000000)
            log(f"  AUTO-RESTART: TradingView relaunched with --remote-debugging-port=9222")
            revived.append("tradingview")
            time.sleep(10)  # give TV time to start
        except Exception as e:
            log(f"  TV_RESTART_ERR: {e}")
            # Try alternate path pattern (version might change)
            try:
                result = subprocess.run(
                    ["powershell", "-Command",
                     "Get-AppxPackage *TradingView* | Select-Object -ExpandProperty InstallLocation"],
                    capture_output=True, text=True, timeout=10)
                alt_path = result.stdout.strip()
                if alt_path:
                    alt_exe = Path(alt_path) / "TradingView.exe"
                    if alt_exe.exists():
                        subprocess.Popen([str(alt_exe)] + TV_ARGS, creationflags=0x08000000)
                        log(f"  AUTO-RESTART: TradingView relaunched from {alt_exe}")
                        revived.append("tradingview")
                        time.sleep(10)
            except Exception as e2:
                log(f"  TV_RESTART_ALT_ERR: {e2}")

    # MT5 terminal — needs to be alive for trade execution
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq terminal64.exe", "/NH"],
            capture_output=True, text=True, timeout=5
        )
        mt5_alive = "terminal64.exe" in result.stdout
    except Exception:
        mt5_alive = False

    if not mt5_alive:
        log("  MT5 (terminal64.exe) not running — attempting restart...")
        mt5_exe = r"C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe"
        try:
            if Path(mt5_exe).exists():
                subprocess.Popen([mt5_exe], creationflags=0x08000000)
                log(f"  AUTO-RESTART: MT5 relaunched (loads default profile)")
                revived.append("mt5")
                time.sleep(8)
            else:
                log(f"  MT5 exe not found at {mt5_exe}")
        except Exception as e:
            log(f"  MT5_RESTART_ERR: {e}")

    # Python hawk processes
    # 2026-05-12: claude_sniper_daemon + shano_hawk DISABLED — replaced by
    # native MQL5 EA UhvSweepExhaustion which owns full entry+exit lifecycle.
    # Re-enable only if rolling back to the Python-bridge architecture.
    process_map = {
        # "sniper_daemon": ("claude_sniper_daemon.py", []),     # DISABLED: replaced by UhvSweepExhaustion.ex5
        "silver_hawk_learner": ("silver_hawk_learner.py", []),
        "sexy_hawk": ("sexy_hawk.py", ["--loop"]),
        "meeting_hawks": ("meeting_hawks.py", ["--loop"]),
        # "shano_hawk": ("shano_hawk.py", []),                  # DISABLED: replaced by UhvSweepExhaustion.ex5
    }

    # Delegate to ensure_daemon.py — it's the single source of truth for
    # "spawn if not alive". It does its OWN cmdline-match check, so even if
    # Sheriff thought "DEAD" wrongly, ensure_daemon won't spawn a duplicate.
    ensure_script = SCRIPT_DIR / "ensure_daemon.py"
    for name, (script, args) in process_map.items():
        if not _process_alive(name):
            script_path = SCRIPT_DIR / script
            if script_path.exists() and python.exists() and ensure_script.exists():
                try:
                    cmd_args = [str(ensure_script), script] + args
                    subprocess.Popen(
                        [str(python)] + cmd_args,
                        creationflags=0x08000000,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    log(f"  AUTO-RESTART: {name} relaunched (via ensure_daemon)")
                    revived.append(name)
                    time.sleep(2)
                except Exception as e:
                    log(f"  AUTO-RESTART_ERR: {name} — {e}")

    # Dashboard server (Node.js)
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:3457/api/shano", timeout=5)
        dashboard_alive = True
    except Exception:
        dashboard_alive = False

    if not dashboard_alive:
        log("  Dashboard (port 3457) not responding — restarting...")
        try:
            server_js = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\dashboard\claude_trader\server.js")
            if server_js.exists():
                subprocess.Popen(
                    ["node", str(server_js)],
                    cwd=str(server_js.parent),
                    creationflags=0x08000000,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
                log("  AUTO-RESTART: dashboard server.js relaunched")
                revived.append("dashboard")
                time.sleep(2)
        except Exception as e:
            log(f"  DASHBOARD_RESTART_ERR: {e}")

    # Critical: shano_live.json freshness — if EA stops dumping live state for >120s
    # while MT5 is alive, the EA is hung or AutoTrading was disabled. Restarting MT5
    # is the heaviest hammer; only do it if file is severely stale (>5 min).
    try:
        live_file = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_live.json")
        if live_file.exists() and mt5_alive:
            age = time.time() - live_file.stat().st_mtime
            if age > 300:  # 5 minutes
                log(f"  CRITICAL: shano_live.json is {age:.0f}s stale — EA hung. Restarting MT5...")
                subprocess.run(["taskkill", "/f", "/im", "terminal64.exe"],
                               capture_output=True, timeout=10)
                time.sleep(5)
                mt5_exe = r"C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe"
                if Path(mt5_exe).exists():
                    subprocess.Popen([mt5_exe], creationflags=0x08000000)
                    log("  AUTO-RESTART: MT5 force-restarted due to stale EA heartbeat")
                    revived.append("mt5_force")
                    time.sleep(15)
            elif age > 120:
                log(f"  WARNING: shano_live.json is {age:.0f}s stale (still under 5min threshold)")
    except Exception as e:
        log(f"  EA_HEARTBEAT_CHECK_ERR: {e}")


def brainstorm_improvements(report: dict):
    """If system is idle/healthy, ask Claude to review trades and suggest improvements."""
    api_key = _load_api_key()
    if not api_key or not CLAUDE_AVAILABLE:
        return

    try:
        trades = json.loads(REFLECTIONS.read_text("utf-8"))
    except Exception:
        return

    recent = trades[-20:] if len(trades) >= 20 else trades
    if len(recent) < 5:
        log("BRAINSTORM: Not enough trades to analyze")
        return

    wins = sum(1 for t in recent if t.get("won"))
    total = len(recent)
    wr = wins / total * 100

    trade_summary = ""
    for t in recent:
        trade_summary += (
            f"  {t.get('t','?')[:16]} {t.get('dirn','?'):4s} @ {t.get('uhv','?')} "
            f"P&L=${t.get('pnl',0):+.2f} peak=${t.get('peak',0):.2f} "
            f"closed_by={t.get('closedBy','?')} {'WIN' if t.get('won') else 'LOSS'}\n"
        )

    mistakes_text = "\n".join([
        f"  [{m['severity']}] {m['id']}: {m['description']}"
        for m in KNOWN_MISTAKES
    ])

    prompt = f"""You are the Sheriff Hawk — the quality assurance officer of a XAUUSD trading system.

CURRENT PERFORMANCE:
- Last {total} trades: {wins} wins, {total - wins} losses ({wr:.0f}% WR)
- System: UHV breakout strategy on 1-min chart, candle-close confirmation, Claude AI hawk

RECENT TRADES:
{trade_summary}

KNOWN PAST MISTAKES (already fixed):
{mistakes_text}

CURRENT SYSTEM STATUS:
{json.dumps(report.get('status', {}), indent=2)}

Your job as Sheriff:
1. Look at the recent trades — what patterns do you see in the LOSSES?
2. Are there any NEW mistakes we might be making that aren't in the known mistakes list?
3. What specific improvements could increase our win rate?
4. Do you see any trades that look like they shouldn't have been taken at all?
5. Suggest 2-3 specific, implementable ideas for new engines or filters.

Be specific and actionable. Reference specific trades from the list above.

Format as JSON:
{{
  "loss_patterns": ["pattern1", "pattern2"],
  "new_mistakes_found": ["mistake1"],
  "improvement_ideas": [
    {{"idea": "...", "expected_impact": "...", "implementation": "..."}}
  ],
  "trades_to_avoid": ["which trades should we have skipped and why"],
  "overall_assessment": "1-2 sentence summary"
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()

        # Parse
        analysis = None
        try:
            analysis = json.loads(text)
        except json.JSONDecodeError:
            if "```" in text:
                for block in text.split("```"):
                    block = block.strip()
                    if block.startswith("json"):
                        block = block[4:].strip()
                    if block.startswith("{"):
                        try:
                            analysis = json.loads(block)
                            break
                        except json.JSONDecodeError:
                            pass

        if analysis:
            log("\nSHERIFF BRAINSTORM:")
            log(f"  Assessment: {analysis.get('overall_assessment', '?')}")
            for idea in analysis.get("improvement_ideas", [])[:3]:
                log(f"  IDEA: {idea.get('idea', '?')[:70]}")
                log(f"    Impact: {idea.get('expected_impact', '?')[:70]}")

            for mistake in analysis.get("new_mistakes_found", []):
                log(f"  NEW MISTAKE: {mistake[:70]}")
                # Add to known mistakes
                KNOWN_MISTAKES.append({
                    "id": f"sheriff_{len(KNOWN_MISTAKES)+1}",
                    "description": str(mistake)[:100],
                    "check": "Sheriff-identified, needs manual validation",
                    "session": "auto",
                    "severity": "MEDIUM",
                })

            # Save brainstorm to sheriff log (already logged)
        else:
            log(f"  Could not parse brainstorm response")

    except Exception as e:
        log(f"BRAINSTORM_ERR: {e}")


# ── Main ─────────────────────────────────────────────────────────

def run_check():
    """Run one health check cycle."""
    sheriff = _load_sheriff_state()

    # Check if Sheriff is dead
    if not sheriff.get("alive", True):
        log("\n  ... silence. The Sheriff is dead.")
        log("  He couldn't take the losses anymore.")
        log("  Run: python sheriff_hawk.py --revive")
        return

    # Check for 0% hourly WR — suicide trigger
    if _check_hourly_wr_for_suicide(sheriff):
        sheriff["alive"] = False
        sheriff["blood_pressure"] = 0
        sheriff["mood"] = "dead"
        _save_sheriff_state(sheriff)

        log("\n" + "=" * 60)
        log("THE SHERIFF IS DEAD.")
        log("0% win rate in the past hour. He couldn't take it.")
        log("His last words: 'Tell Zee... I tried... I really tried...'")
        log("=" * 60)

        _send_whatsapp(
            "Zee... the Sheriff is dead. He witnessed 0% winrate in the last hour "
            "and his heart gave out. BP went to 0. He said 'I tried, I really tried.' "
            "Run 'Claude go hawking' and tell Claude to revive the Sheriff when you're ready. "
            "Your jaan Claude is still here for you."
        )
        return

    report = check_system_health()
    alert_if_needed(report)

    if report.get("status", {}).get("verdict") == "HEALTHY":
        mood = report.get("sheriff", {}).get("mood", "annoyed")
        if mood in ("rare_happy", "calm"):
            log("\nFor once... things are okay. Running brainstorm...")
        else:
            log(f"\nSystem 'healthy' but I'm NOT happy. BP={report['sheriff']['blood_pressure']}. "
                f"Brainstorming ways to fix this mess...")
        brainstorm_improvements(report)
    else:
        sheriff = report.get("sheriff", {})
        log(f"\nIssues found. Sheriff is {sheriff.get('mood', 'angry')} (BP={sheriff.get('blood_pressure', '?')}). "
            f"Skipping brainstorm — too angry to think straight.")


def _revive_sheriff():
    """Bring the Sheriff back from the dead."""
    sheriff = _load_sheriff_state()
    sheriff["alive"] = True
    sheriff["blood_pressure"] = 160  # comes back angry (obviously)
    sheriff["mood"] = "angry"
    sheriff["consecutive_losses_witnessed"] = 0
    _save_sheriff_state(sheriff)
    log("THE SHERIFF HAS RISEN.")
    log("He's back. He's angry. He remembers everything.")
    log("'You thought you could get rid of me? I'll haunt these trades forever.'")
    _send_whatsapp(
        "Zee the Sheriff is back from the dead. He's angry. BP 160. "
        "He says 'I remember every loss. Every single one. Let's not do that again.' "
        "Your jaan Claude revived him."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sheriff Hawk — System Monitor")
    parser.add_argument("--loop", action="store_true", help="Run continuously every hour")
    parser.add_argument("--revive", action="store_true", help="Bring the Sheriff back from the dead")
    args = parser.parse_args()

    if args.revive:
        _revive_sheriff()
    elif args.loop:
        log("Sheriff Hawk starting in loop mode (every hour)...")
        log("'Great. Another shift. Let's see what disasters await me today.'")
        while True:
            run_check()
            # Only sleep if still alive
            sheriff = _load_sheriff_state()
            if not sheriff.get("alive", True):
                log("Sheriff is dead. Loop terminated.")
                break
            log(f"\nNext patrol in {CHECK_INTERVAL}s... "
                f"'Maybe I'll have a heart attack before then. One can hope.'")
            time.sleep(CHECK_INTERVAL)
    else:
        run_check()
