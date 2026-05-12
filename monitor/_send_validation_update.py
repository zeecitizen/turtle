import json, urllib.request

cfg = json.load(open(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.whatsapp_config.json"))
host, iid, tok = cfg["api_host"], cfg["instance_id"], cfg["api_token"]

URL = "https://hazardous-briefs-california-illustrated.trycloudflare.com/london-sajid"

msg = (
    "🎯 Big validation update jaan:\n\n"
    "WALK-FORWARD VALIDATION (45d train / 15d test rolling):\n"
    "• London Breakout: 2/3 windows positive (PF 3.27, 2.87, 0.96)\n"
    "• NY Breakout: 3/3 windows positive (PF 1.83, 1.49, 3.48) ← MOST ROBUST\n"
    "• VSISA M5: 3/3 windows positive (PF 1.61, 1.05, 1.40)\n\n"
    "PORTFOLIO ANALYSIS (combined daily P&L 86d):\n"
    "• LB alone: $36,798 net, MaxDD $6,830, Sharpe 0.225\n"
    "• NY alone: $19,032, MaxDD $4,884, Sharpe 0.161\n"
    "• VSISA alone: $10,358, MaxDD $3,352, Sharpe 0.169\n"
    "• COMBINED: $66,188 net, MaxDD $7,214, Sharpe 0.256 ⭐\n\n"
    "Diversification cuts drawdown ~50% vs sum-of-DDs.\n"
    "Correlations: LB↔NY 0.57, LB↔VSISA 0.20, NY↔VSISA -0.18\n\n"
    "SAFETY ADDED:\n"
    "✅ PID lockfile (no more zombie daemons)\n"
    "✅ Persistent date guard (1 LB + 1 NY per day max)\n"
    "✅ Equity halt at -$200 daily loss\n"
    "✅ Friday session-end auto-close at 21:00 UTC (weekend gap protection)\n\n"
    f"Dashboard (now with all stats): {URL}\n\n"
    "Daemon running clean. NY breakout window opens 13:00 UTC (~2h)."
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
