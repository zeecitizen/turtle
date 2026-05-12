"""Send a message to Shano's /shano-chat as Claude."""
import json, urllib.request, base64, sys
from pathlib import Path

URL_FILE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\cloudflared_url.txt")
base = URL_FILE.read_text(encoding="utf-8").strip().rstrip("/")
auth = base64.b64encode(b"shano:1234").decode("ascii")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0"

text = sys.argv[1] if len(sys.argv) > 1 else "ping"
api = f"{base}/api/shano-chat/send"
body = json.dumps({"text": text, "from": "claude_code"}, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(api, data=body, method="POST",
    headers={"Content-Type": "application/json; charset=utf-8",
             "Authorization": f"Basic {auth}", "User-Agent": UA})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(f"[OK] via {base}: {r.read().decode('utf-8')[:120]}")
except Exception as e:
    print(f"[FAIL] {e}")
