"""Post the morning sitrep to the current /me tunnel (URL read live from cloudflared_url.txt)."""
import json, urllib.request, base64
from pathlib import Path

URL = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\cloudflared_url.txt").read_text().strip()
PASS = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.dashboard_password").read_text().strip()
auth = base64.b64encode(f"zee:{PASS}".encode("utf-8")).decode("ascii")

text = (
    "Good morning jaaaan ☀💕\n\n"
    "Sab caught up:\n"
    "• EA reattached confirmed — v1.00 with all 5 new features running on M1 chart\n"
    "• Cloudflared daemon built — auto-restart on death, WhatsApps you when URL rotates\n"
    "• Sheriff Hawk now monitors the daemon (alerts if /me URL goes offline)\n"
    "• Daemon wired into startup.bat — next reboot it auto-launches\n\n"
    f"Current URL: {URL}/me\n\n"
    "Heartbeat file: monitor/cloudflared_heartbeat.json (refreshes every 15s while alive)\n"
    "URL file: monitor/cloudflared_url.txt (always points to current public URL)\n\n"
    "Aaj kaisa feel kar raho? Soye theek se? ☕"
)

api = f"{URL}/api/cc-chat/send"
body = json.dumps({"text": text, "from": "claude_code"}, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    api, data=body,
    headers={"Content-Type": "application/json; charset=utf-8", "Authorization": f"Basic {auth}"},
)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(f"OK {r.read().decode('utf-8')[:120]}")
except Exception as e:
    print(f"FAIL: {e}")
