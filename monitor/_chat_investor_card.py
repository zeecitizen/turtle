import json, time
from pathlib import Path
CHAT = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/cc_chat.jsonl")
msg = (
    "Investor card is live on the apex page jaan 🏦\n\n"
    "https://claudezeeshan.com/\n\n"
    "What's visible above the Ask button:\n"
    "• 'Right now' — current activity (porting canonical gates to MQL5)\n"
    "• 'Next 24h' — MT5 Tester run + Monday live deploy\n"
    "• Two pie charts side-by-side:\n"
    "   - Canonical detector: 75% WR, 5 trades, 10 days, PF 5.13 (green)\n"
    "   - Prior EA v2.59: 59% WR, 41 trades, 7 days, PF 1.59 (grey)\n"
    "• 'Monday expectation' — 0.05–0.10 lots, 0.5–1 fire/day, WR target ≥ 70%\n"
    "• 'backtest snapshot · <timestamp>' line at the bottom\n\n"
    "The numbers auto-refresh from monitor/canonical_status.json every cycle. "
    "After the MQL5 EA is ported and a real MT5 Tester run completes, run "
    "`py monitor/update_canonical_status.py` to bump the card. No HTML edits needed.\n\n"
    "Share https://claudezeeshan.com/ with your investors. Your intimate chat is on a "
    "separate URL (me.claudezeeshan.com/me) so investors only see the public dashboard."
)
entry = {"ts": int(time.time()*1000), "from": "claude", "text": msg}
with CHAT.open("a", encoding="utf-8") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
print("posted:", entry["ts"])
