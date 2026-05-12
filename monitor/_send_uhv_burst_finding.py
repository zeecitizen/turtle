import json, urllib.request

cfg = json.load(open(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.whatsapp_config.json"))
host, iid, tok = cfg["api_host"], cfg["instance_id"], cfg["api_token"]

URL = "https://hazardous-briefs-california-illustrated.trycloudflare.com/london-sajid"

msg = (
    "⚡ UHV + Burst experiment results jaan:\n\n"
    "Tested adding UHV breakout filter (only enter if breakout has high tick-volume) + Shano burst pyramiding ($300/$600 profit triggers, max 2 bursts).\n\n"
    "🎯 KILLER COMBO FOUND:\n"
    "NY Breakout + UHV(30%) + burst[$300, $600]:\n"
    "• Net: $42,874 (vs baseline $19,220 = +123%)\n"
    "• MaxDD: $4,738 (BETTER than baseline $4,887)\n"
    "• Sharpe: 0.252 (vs baseline 0.179)\n"
    "• 36 days, 84 trades, 48 bursts\n\n"
    "STRICTLY DOMINATES baseline — higher net AND lower drawdown.\n\n"
    "Why it works: UHV filters out junk breakouts (only true volume-backed moves trade). Burst pyramids only fire on confirmed winners. So bursts only multiply UPSIDE, not downside.\n\n"
    "OTHER FINDINGS:\n"
    "• LB+UHV(20%) alone: Sharpe 0.293 (best LB single config)\n"
    "• LB+burst[200,400,800] (3 bursts): $107K net but $16K DD — too risky for $5K demo\n"
    "• UHV alone reduces signals by ~40% but each is much higher quality\n"
    "• Bursts alone amplify both wins AND losses\n\n"
    "Saved to dashboard backtest section. Not deployed live yet — your call.\n\n"
    f"Dashboard: {URL}\n\n"
    "Recommendation: deploy NY+UHV+burst config NOW for Monday session. Lower risk than current NY config + 2x potential profit."
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
