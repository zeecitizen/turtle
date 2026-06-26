"""ea_health_watchdog.py — local hourly watchdog for S1Trader EA.

Designed to run via Windows Task Scheduler every hour. Reads local EA state,
detects bad conditions, sends WhatsApp alert to Zee (not Shano) if anything
is wrong. Always writes status log.

NO AI involvement — just python rules. No hallucination risk.

Alerts on:
  - Heartbeat stale > 5 min during market hours (Mon-Fri 22:00-21:00 UTC weekly)
  - Day P&L worse than -$150 (catastrophic)
  - 3 consecutive SL hits today
  - EA not running (no terminal64 process)
"""
import json, re, time, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib import request as urlreq

sys.stdout.reconfigure(encoding="utf-8")

# ── Paths ──
COMMON_FILES = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
TERMINAL_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8")
WHATSAPP_CFG = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/.whatsapp_config.json")
STATUS_LOG   = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/.watchdog_status.jsonl")
ALERT_NUMBER = "923009687022@c.us"   # 2026-06-23: Mehboob bhai (Zee's brother + EA manager). Zee does NOT monitor WhatsApp.

# ── Thresholds ──
HEARTBEAT_STALE_SEC      = 300   # 5 min stale = alert (during market hours)
DAY_PNL_DISASTER_USD     = -150  # alert if day loss > this
SL_STREAK_THRESHOLD      = 3     # 3 consecutive SLs = alert
LOTS                      = 0.30
DOLLARS_PER_POINT_AT_LOT = 100 * LOTS


def is_market_open_utc(dt_utc: datetime) -> bool:
    """XAUUSD market: Sun 22:00 UTC → Fri 22:00 UTC (approx)."""
    wd = dt_utc.weekday()   # Mon=0..Sun=6
    h = dt_utc.hour
    # Fri after 22:00 = closed until Sun 22:00
    if wd == 4 and h >= 22:   return False
    if wd == 5:                return False    # Saturday
    if wd == 6 and h < 22:    return False
    return True


def read_heartbeat():
    p = COMMON_FILES / "s1_trader_state_m1.json"
    if not p.exists(): return None
    raw = p.read_bytes()
    s = raw[2:].decode("utf-16le", errors="ignore") if raw[:2] == b"\xff\xfe" else raw.decode("utf-8", errors="ignore")
    try:
        return {
            "data": json.loads(s),
            "mtime_age_sec": time.time() - p.stat().st_mtime,
        }
    except Exception:
        return None


def today_utc_date():
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def get_today_trades_from_log():
    """Parse Experts log for today's fills + auto-closes + SL hits + grabs."""
    log = TERMINAL_DIR / f"MQL5/Logs/{today_utc_date()}.log"
    if not log.exists():
        # Try broker date — may differ from UTC due to GMT+2
        for delta in [0, -1]:
            d = (datetime.now(timezone.utc) + timedelta(days=delta)).strftime("%Y%m%d")
            log_candidate = TERMINAL_DIR / f"MQL5/Logs/{d}.log"
            if log_candidate.exists():
                log = log_candidate
                break
        else:
            return None
    content = log.read_bytes().decode("utf-16le", errors="ignore")
    fills    = re.findall(r"\[FILLED\] ticket=(\d+)", content)
    autoc    = re.findall(r"AUTO-CLOSE-MS[^\n]*after \d+ms: ([+-]?\d+\.\d+)pts = \$([+-]?\d+\.\d+)", content)
    sl_hits  = re.findall(r"\[sl ", content)
    return {
        "log_file": log.name,
        "fills": len(fills),
        "auto_closes": len(autoc),
        "sl_hits": len(sl_hits),
        "auto_close_pnl_list": [float(usd) for _, usd in autoc],
    }


def compute_sl_streak(log_content: str) -> int:
    """Count consecutive SL hits at the END of today's trade list."""
    # Each "AUTO-CLOSE-MS ... $-X.XX" indicates a close with $ result.
    # A streak is N negative closes in a row at the end.
    closes = re.findall(r"AUTO-CLOSE-MS[^\n]*\$([+-]?\d+\.\d+)|\[sl ([\d.]+)\]", log_content)
    # Each match is either (pnl_usd, "") or ("", sl_price)
    streak = 0
    for pnl_usd, sl_price in reversed(closes):
        if pnl_usd:
            if float(pnl_usd) < 0: streak += 1
            else:                  break
        elif sl_price:
            streak += 1
        else:
            break
    return streak


def send_whatsapp(msg: str) -> bool:
    """Send WhatsApp via GreenAPI to Mehboob bhai (Zee's brother, EA manager)."""
    try:
        cfg = json.loads(WHATSAPP_CFG.read_text())
        instance = cfg["instance_id"]
        token = cfg["api_token"]
        host = cfg["api_host"]
        url = f"{host}/waInstance{instance}/sendMessage/{token}"
        payload = json.dumps({"chatId": ALERT_NUMBER, "message": msg}).encode("utf-8")
        req = urlreq.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urlreq.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception as e:
        print(f"  whatsapp send failed: {e}")
        return False


def log_status(status: dict):
    STATUS_LOG.parent.mkdir(parents=True, exist_ok=True)
    status["ts_utc"] = datetime.now(timezone.utc).isoformat()
    with STATUS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(status) + "\n")
    # Also write LATEST status to a file the dashboard can show
    latest = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/.watchdog_latest.json")
    latest.write_text(json.dumps(status, indent=2))


def main():
    now_utc = datetime.now(timezone.utc)
    market_open = is_market_open_utc(now_utc)

    status = {
        "now_utc": now_utc.isoformat(),
        "market_open": market_open,
        "alerts": [],
    }

    hb = read_heartbeat()
    if hb is None:
        status["alerts"].append("HEARTBEAT_FILE_MISSING")
    else:
        d = hb["data"]
        status["ea_version"] = d.get("version", "?")
        status["broker_t"]   = d.get("t", "?")
        status["signals"]    = d.get("signals_today", 0)
        status["entries"]    = d.get("entries_today", 0)
        status["heartbeat_age_sec"] = round(hb["mtime_age_sec"])
        # Stale alert (only during market hours)
        if market_open and hb["mtime_age_sec"] > HEARTBEAT_STALE_SEC:
            status["alerts"].append(f"HEARTBEAT_STALE_{int(hb['mtime_age_sec']/60)}min")
        # Version drift alert — accept 3.00+ as healthy
        v = d.get("version", "0")
        try:
            major = int(v.split(".")[0])
            if major < 3:
                status["alerts"].append(f"VERSION_NOT_LATEST_{v}")
        except Exception:
            status["alerts"].append(f"VERSION_PARSE_FAIL_{v}")

    log_data = get_today_trades_from_log()
    if log_data:
        status["log_file"]    = log_data["log_file"]
        status["fills"]       = log_data["fills"]
        status["auto_closes"] = log_data["auto_closes"]
        status["sl_hits"]     = log_data["sl_hits"]
        day_pnl = sum(log_data["auto_close_pnl_list"])
        status["day_pnl_auto_close"] = round(day_pnl, 2)
        if day_pnl <= DAY_PNL_DISASTER_USD:
            status["alerts"].append(f"DAY_PNL_DISASTER_${day_pnl:.2f}")
        # SL streak — read raw content for analysis
        log_path = TERMINAL_DIR / f"MQL5/Logs/{log_data['log_file']}"
        if log_path.exists():
            content = log_path.read_bytes().decode("utf-16le", errors="ignore")
            streak = compute_sl_streak(content)
            status["sl_streak"] = streak
            if streak >= SL_STREAK_THRESHOLD:
                status["alerts"].append(f"SL_STREAK_{streak}")

    # WhatsApp alert if any condition met
    if status["alerts"]:
        msg_lines = [
            "🚨 EA WATCHDOG ALERT 🚨",
            f"Time: {now_utc.strftime('%Y-%m-%d %H:%M UTC')}",
            f"EA: v{status.get('ea_version', '?')}",
            f"Day P&L: ${status.get('day_pnl_auto_close', 0):+.2f}",
            f"Heartbeat age: {status.get('heartbeat_age_sec', '?')}s",
            f"Issues:",
        ] + [f"  - {a}" for a in status["alerts"]]
        msg = "\n".join(msg_lines)
        sent = send_whatsapp(msg)
        status["alert_sent"] = sent
        print(msg)
        print(f"alert sent: {sent}")
    else:
        print(f"OK · v{status.get('ea_version','?')} · "
              f"signals={status.get('signals')} entries={status.get('entries')} "
              f"sl_hits={status.get('sl_hits', 0)} "
              f"day_pnl=${status.get('day_pnl_auto_close', 0):+.2f}")

    log_status(status)
    return 1 if status["alerts"] else 0


if __name__ == "__main__":
    sys.exit(main())
