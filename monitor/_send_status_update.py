import json, urllib.request

cfg = json.load(open(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.whatsapp_config.json"))
host, iid, tok = cfg["api_host"], cfg["instance_id"], cfg["api_token"]

URL = "https://hazardous-briefs-california-illustrated.trycloudflare.com/london-sajid"

msg = (
    "Status update jaan:\n\n"
    f"Dashboard: {URL}\n\n"
    "Found + fixed major bug: 8 zombie daemons were running concurrently due to broken kill semantics. Each was firing duplicate LB trades.\n\n"
    "Fixes applied:\n"
    "• PID lockfile — only one daemon can run\n"
    "• Persistent date-guard — LB fires max once per day\n"
    "• NY Breakout added (PF 1.66/1.46 OOS validated)\n"
    "• Dashboard now shows LB + NY + VSISA blocks\n\n"
    "Backtest research findings:\n"
    "• Peak-trail (book early) DESTROYS LB edge — keeps WR high but kills PF (1.96 → 1.13). LB depends on big runners.\n"
    "• Shano-Zee post-mortem on yesterday's mains: -$191 actual vs -$115 with peak-trail T=$5/$2. That insight applies to scalp-style trades, NOT position-trade strategies like LB/NY.\n\n"
    "State now:\n"
    "• 1 daemon (PID 15228) running clean\n"
    "• Balance $4864 (lost ~$40 to today's chaos before the lockfile fix)\n"
    "• LB done for today (next opportunity Monday)\n"
    "• NY breakout will fire after 13:00 UTC if breakout occurs\n"
    "• VSISA watching M5 closes for effort+reaction patterns\n\n"
    "Continuing with walk-forward validation."
)

url = f"{host}/waInstance{iid}/sendMessage/{tok}"
for chat in ["4915119175329@c.us"]:
    body = json.dumps({"chatId": chat, "message": msg}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"[OK] {chat}")
    except Exception as e:
        print(f"[FAIL] {chat}: {e}")
