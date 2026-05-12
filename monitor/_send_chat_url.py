"""One-off: send the Cloudflare quick-tunnel chat URL to Zee via WhatsApp."""
import json, urllib.request

cfg = json.load(open(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.whatsapp_config.json"))
host = cfg["api_host"]; iid = cfg["instance_id"]; tok = cfg["api_token"]

URL = "https://bangkok-showers-experiencing-discs.trycloudflare.com/"

msg = (
    "Phone-to-Claude-Code chat is live.\n\n"
    f"{URL}\n\n"
    "Bookmark this. Tap the orange chat icon (bottom-right) to talk to me directly while I'm working on your trading algos.\n"
    "I poll every ~90s — async chat, not realtime.\n"
    "Tunnel runs as long as the cloudflared window stays open on your laptop."
)

url = f"{host}/waInstance{iid}/sendMessage/{tok}"
body = json.dumps({"chatId": "4915119175329@c.us", "message": msg}).encode("utf-8")
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(f"[OK] {r.read().decode('utf-8')}")
except Exception as e:
    print(f"[FAIL] {e}")
