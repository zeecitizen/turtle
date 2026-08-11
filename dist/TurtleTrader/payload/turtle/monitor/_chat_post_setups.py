import json, time
from pathlib import Path

CHAT = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/cc_chat.jsonl")

msg = (
    "💎 Setup labelling page is LIVE jaan:\n\n"
    "https://setups.claudezeeshan.com/setups.html\n\n"
    "36 S1 setups (last 2 days), each with chart + UHV marker + entry arrow. "
    "Below every chart: Zee textbox + Shano textbox, each with Save Comment.\n\n"
    "Type your thoughts, hit Save — I'll generate fix-tasks per label and iterate "
    "the EA toward 80%+ WR for Tuesday."
)

entry = {"ts": int(time.time()*1000), "from": "claude", "text": msg}
with CHAT.open("a", encoding="utf-8") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
print("posted to /me chat:", entry["ts"])
