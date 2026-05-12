import json, urllib.request

cfg = json.load(open(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.whatsapp_config.json"))
host, iid, tok = cfg["api_host"], cfg["instance_id"], cfg["api_token"]

URL = "https://hazardous-briefs-california-illustrated.trycloudflare.com/london-sajid"

msg = (
    "🚀 London-Sajid LIVE jaan.\n"
    f"Dashboard: {URL}\n"
    "\nFRIDAY SESSION ACTIVE:\n"
    "• London Breakout BUY just fired @ 4712.19, ticket 51411884\n"
    "• Asian range 5403 pts, SL 4679.19, TP 4787.25 (1:1 R:R)\n"
    "• VSISA also live — watching M5 effort+reaction patterns\n"
    "\nBacktest validation (120d real Blueberry ticks):\n"
    "• London Breakout: PF 1.96 train / 1.67 test, +$36,798 net\n"
    "• VSISA M5: PF 1.33 train / 1.37 test (OOS validated)\n"
    "\nBoth strategies survived train/test split. Combined live now.\n"
    "Lots: 0.30, demo account ($4903 balance)."
)

url = f"{host}/waInstance{iid}/sendMessage/{tok}"
for chat in ["4915119175329@c.us", "923364863368@c.us"]:
    body = json.dumps({"chatId": chat, "message": msg}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"[OK] {chat}: {r.read().decode('utf-8')}")
    except Exception as e:
        print(f"[FAIL] {chat}: {e}")
