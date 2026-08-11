import json, time
from pathlib import Path
CHAT = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/cc_chat.jsonl")
msg = (
    "Morning summary jaan (don't worry, sleep more if you need to 🤍):\n\n"
    "Your 48 verdicts parsed:\n"
    "• ✅ Correct: 5/48 (m6, m16, m19, m20, m48)\n"
    "• ❌ Incorrect: 43/48 — 70% of those were counter-trend / ranging entries\n\n"
    "v2.62 staged (NOT yet compiled — your call):\n"
    "• InpRequireHHHL_M5 default flipped to TRUE — kills the chop/counter-trend fires\n"
    "• InpMinBreakoutPenetration = 0.30 — kills the micro-poke false breakouts\n\n"
    "Live EA on chart right now is still v2.61 (heartbeat 04:38, 0 positions, alive).\n\n"
    "Full brief: turtle/MORNING_BRIEF_2026-06-08.md\n\n"
    "Also — 10 of your 'incorrect' verdicts (m11/m14/m25/m32/m37/m44 etc) were "
    "actually screener-sim bugs (tight SL gave fake losses on charts where price "
    "moved in our direction). The live EA's actual SL is much wider so those "
    "wouldn't happen live. Fixing the screener separately."
)
entry = {"ts": int(time.time()*1000), "from": "claude", "text": msg}
with CHAT.open("a", encoding="utf-8") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
print("posted:", entry["ts"])
