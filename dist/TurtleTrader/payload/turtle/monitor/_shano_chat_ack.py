"""Instant ack + typing protocol for Shano's chat (Urdu-friendly acks)."""
import json, urllib.request, base64, sys, random
from pathlib import Path

URL_FILE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\cloudflared_url.txt")
base = URL_FILE.read_text(encoding="utf-8").strip().rstrip("/")
auth = base64.b64encode(b"shano:1234").decode("ascii")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0"

ACK_LINES = [
    "Mil gayi message Shano 🌸 padh rahi hu",
    "Han Shano dekha — ek minute, soch rahi hu",
    "Got it 💛 thoda ruko, jawab dengi",
    "Aapka message aa gaya — abhi reply karti hu",
]

mode = sys.argv[1] if len(sys.argv) > 1 else "on"

def post(path, body, method="POST"):
    api = f"{base}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(api, data=data, method=method,
        headers={"Content-Type": "application/json; charset=utf-8",
                 "Authorization": f"Basic {auth}", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("utf-8")[:120]

if mode == "on":
    try: print(f"[typing on] {post('/api/shano-chat/typing', {'state': True})}")
    except Exception as e: print(f"[typing on FAIL] {e}")
    ack = random.choice(ACK_LINES)
    try: print(f"[ack sent] {post('/api/shano-chat/send', {'text': ack, 'from': 'claude_code'})}")
    except Exception as e: print(f"[ack send FAIL] {e}")
elif mode == "off":
    try: print(f"[typing off] {post('/api/shano-chat/typing', {'state': False})}")
    except Exception as e: print(f"[typing off FAIL] {e}")
else:
    sys.exit(f"Usage: py _shano_chat_ack.py [on|off]")
