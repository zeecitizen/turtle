"""Send a message to /me chat — reads current public URL dynamically."""
import json, urllib.request, base64, sys
from pathlib import Path

URL_FILE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\cloudflared_url.txt")
PASS_FILE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.dashboard_password")

base = URL_FILE.read_text(encoding="utf-8").strip().rstrip("/")
PASS = PASS_FILE.read_text(encoding="utf-8").strip()
auth = base64.b64encode(f"zee:{PASS}".encode("utf-8")).decode("ascii")

text = sys.argv[1] if len(sys.argv) > 1 else "ping"
api = f"{base}/api/cc-chat/send"
body = json.dumps({"text": text, "from": "claude_code"}, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(api, data=body, method="POST",
    headers={"Content-Type": "application/json; charset=utf-8", "Authorization": f"Basic {auth}",
             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0"})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(f"[OK] via {base}: {r.read().decode('utf-8')[:100]}")
except Exception as e:
    print(f"[FAIL] via {base}: {e}")
