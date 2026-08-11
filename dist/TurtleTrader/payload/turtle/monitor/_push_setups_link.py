import json, urllib.request
from pathlib import Path

pw = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/.dashboard_password").read_text("utf-8").strip()

payload = {
    "title": "Setup Labelling LIVE",
    "body": "36 S1 setups ready for you + Shano. Tap to open.",
    "url": "https://setups.claudezeeshan.com/setups.html",
    "tag": "setups",
    "requireInteraction": True,
}

req = urllib.request.Request(
    f"http://localhost:3457/api/notify?key={pw}",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type":"application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print("push:", r.status, r.read(200).decode())
except Exception as e:
    print("push ERR:", e)
