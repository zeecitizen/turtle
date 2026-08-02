"""Compute today's real P&L from MT5 Experts log (auto-close-ms exits)."""
from pathlib import Path
import re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
TERMINAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8")
logs = sorted((TERMINAL / "MQL5/Logs").glob("20260619*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
with open(logs[0], "rb") as f:
    content = f.read().decode("utf-16le", errors="ignore")

pattern = re.compile(r"AUTO-CLOSE-MS[^\n]*after (\d+)ms: ([+-]?\d+\.\d+)pts = \$([+-]?\d+\.\d+)")
closes = pattern.findall(content)
print(f"AUTO-CLOSE-MS exits today: {len(closes)}")
total_pnl = 0.0
wins = losses = 0
total_ms = 0
for ms, pts, usd in closes:
    pnl = float(usd)
    total_pnl += pnl
    total_ms += int(ms)
    if pnl > 0: wins += 1
    else: losses += 1
n = len(closes)
print(f"Today net (auto-close-ms only): ${total_pnl:+.2f}")
print(f"  Wins:    {wins}")
print(f"  Losses:  {losses}")
print(f"  WR:      {100*wins/max(n,1):.1f}%")
print(f"  Avg close time: {total_ms/max(n,1):.0f}ms")

# Show all closes
print()
print("All exits:")
all_exits = []
for m in pattern.finditer(content):
    # Find the timestamp for this match
    upto = content[:m.start()]
    last_time = re.findall(r"(\d{2}:\d{2}:\d{2})\.\d+\s+S1Trader", upto)
    t = last_time[-1] if last_time else "?"
    all_exits.append({
        "t": t,
        "ms": int(m.group(1)),
        "pts": float(m.group(2)),
        "usd": float(m.group(3)),
    })

# Print all
for e in all_exits:
    emoji = "🎉" if e["usd"] > 0 else "💔"
    print(f"  {emoji} {e['t']}  {e['ms']}ms  {e['pts']:+.3f}pts  ${e['usd']:+.2f}")
