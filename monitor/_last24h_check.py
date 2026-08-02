"""Check trades since 06-23 morning (last 24 hours)."""
import re, json, sys, time
from pathlib import Path
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
TERMINAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8")

# Heartbeat
p = COMMON / "s1_trader_state_m1.json"
raw = p.read_bytes()
s = raw[2:].decode("utf-16le", errors="ignore") if raw[:2] == b"\xff\xfe" else raw.decode("utf-8", errors="ignore")
hb = json.loads(s)
age = time.time() - p.stat().st_mtime
print(f"EA: v{hb.get('version')} [{'LIVE' if age < 60 else f'STALE {age:.0f}s'}]")
print(f"  broker_t: {hb.get('t')}  (broker time)")
print(f"  signals_today: {hb.get('signals_today')}  entries_today: {hb.get('entries_today')}  open: {hb.get('n_open')}")
print(f"  late_setups: {hb.get('late_setups')}  last_signal: {hb.get('last_signal_t')}")
print()

for date_str in ["20260623", "20260624"]:
    log = TERMINAL / f"MQL5/Logs/{date_str}.log"
    if not log.exists():
        print(f"{date_str}.log: (no file)")
        continue
    content = log.read_bytes().decode("utf-16le", errors="ignore")
    triggers = re.findall(r"(\d{2}:\d{2}:\d{2}\.\d+)\s+S1Trader[^\n]*LIVE TRIGGER[^\n]*", content)
    fills = re.findall(r"(\d{2}:\d{2}:\d{2}\.\d+)\s+S1Trader[^\n]*\[FILLED\]", content)
    autoc = re.findall(r"AUTO-CLOSE-MS[^\n]*after (\d+)ms: ([+-]?\d+\.\d+)pts = \$([+-]?\d+\.\d+)", content)
    sl_hits = re.findall(r"\[sl ", content)
    misses = re.findall(r"S1Trader[^\n]*\[MISS\]", content)
    inits = re.findall(r"S1Trader Init", content)

    print(f"--- {date_str}.log ({log.stat().st_size/1024:.0f}kB) ---")
    print(f"  init: {len(inits)} | triggers: {len(triggers)} | fills: {len(fills)}")
    print(f"  auto-closes: {len(autoc)} | sl-hits: {len(sl_hits)} | [MISS] events: {len(misses)}")
    if autoc:
        total = sum(float(usd) for _, _, usd in autoc)
        print(f"  Auto-close $ total: ${total:+.2f}")
        for ms, pts, usd in autoc:
            print(f"    {ms}ms → ${float(usd):+.2f}")
    if triggers:
        for t in triggers:
            # Find the full line for this trigger
            for line in content.split("\n"):
                if t in line and "LIVE TRIGGER" in line:
                    print(f"  TRIGGER: {line.strip()[:200]}")
                    break
    print()
