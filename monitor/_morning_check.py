"""Morning status check for v3.00."""
import re, time, csv
from pathlib import Path
from datetime import datetime, timezone
import sys

sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
TERMINAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8")

# Heartbeat
p = COMMON / "s1_trader_state_m1.json"
raw = p.read_bytes()
s = raw[2:].decode("utf-16le", errors="ignore") if raw[:2] == b"\xff\xfe" else raw.decode("utf-8", errors="ignore")
age = time.time() - p.stat().st_mtime
def g(pat):
    m = re.search(pat, s); return m.group(1) if m else "?"
tag = "LIVE" if age < 30 else f"STALE {age/60:.0f}min"
print(f"EA: v{g(r'\"version\":\"([^\"]+)\"')} [{tag}]")
print(f"  broker_t: {g(r'\"t\":\"([^\"]+)\"')}")
print(f"  signals: {g(r'\"signals_today\":(\\d+)')}  entries: {g(r'\"entries_today\":(\\d+)')}  late: {g(r'\"late_setups\":(\\d+)')}  open: {g(r'\"n_open\":(\\d+)')}")
print()

# Today's MT5 Experts log
latest = sorted((TERMINAL / "MQL5/Logs").glob("20260622.log"))
if not latest:
    latest = sorted((TERMINAL / "MQL5/Logs").glob("20260*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:1]
if latest:
    log = latest[0]
    with open(log, "rb") as f:
        content = f.read().decode("utf-16le", errors="ignore")
    triggers = re.findall(r"\d{2}:\d{2}:\d{2}\.\d+\s+S1Trader[^\n]*LIVE TRIGGER[^\n]*", content)
    fills = re.findall(r"(\d{2}:\d{2}:\d{2}\.\d+)\s+S1Trader[^\n]*\[FILLED\] ticket=(\d+)", content)
    autoclose = re.findall(r"AUTO-CLOSE-MS[^\n]*after (\d+)ms: ([+-]?\d+\.\d+)pts = \$([+-]?\d+\.\d+)", content)
    grabs = re.findall(r"\[GRAB\][^\n]*", content)
    sl_hits = re.findall(r"\[sl ", content)
    inits = re.findall(r"S1Trader Init", content)
    deinits = re.findall(r"S1Trader Deinit", content)
    print(f"=== {log.name} ({log.stat().st_size/1024:.0f}kB) ===")
    print(f"  init: {len(inits)}  deinit: {len(deinits)}")
    print(f"  triggers: {len(triggers)}  fills: {len(fills)}  auto-closes: {len(autoclose)}  grabs: {len(grabs)}  sl-hits: {len(sl_hits)}")
    print()
    if triggers:
        print("First 3 triggers (verify origin_shift logged):")
        for l in triggers[:3]:
            print(f"  {l.strip()[:250]}")
        if len(triggers) > 6:
            print(f"  ... ({len(triggers)-6} more) ...")
            for l in triggers[-3:]:
                print(f"  {l.strip()[:250]}")
    else:
        print("(No LIVE TRIGGER lines yet — market open but no setups passed all gates)")

# Fills CSV
print()
print("=== Fills CSV since 06-22 00:00 ===")
fp = COMMON / "turtle_fills.csv"
age = (time.time() - fp.stat().st_mtime) / 60
print(f"  Last modified: {age:.0f}min ago")
trades = []
with open(fp) as f:
    f.readline()
    for r in csv.reader(f):
        if not r or not r[0]: continue
        if r[0] >= "2026.06.22 00:00":
            trades.append(r)
if not trades:
    print("  (no fills today)")
else:
    net = 0
    for t in trades:
        pnl = float(t[10] or t[7])
        net += pnl
        emoji = "🎉" if pnl > 0 else "💔"
        print(f"  {emoji} {t[0]}  {t[4]:>12s}  vol={t[5]}  pnl=${pnl:+.2f}  {t[11]}")
    wins = sum(1 for t in trades if float(t[10] or t[7]) > 0)
    print(f"  Total: {len(trades)} trades  W:{wins}/L:{len(trades)-wins}  net=${net:+.2f}")
