"""Monitor /me chat inbox; print one line per NEW message from 'zee'.

Used as the command in a Claude Code Monitor tool. Tracks the last-seen
timestamp in monitor/.chat_monitor_last_ts so we only emit truly-new
messages across polls and across session restarts.
"""
import json, urllib.request, base64, time, sys
from pathlib import Path

URL_FILE  = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\cloudflared_url.txt")
PASS_FILE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.dashboard_password")
TS_FILE   = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.chat_monitor_last_ts")

POLL_SEC = 30
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36")

def read_inbox():
    base = URL_FILE.read_text(encoding="utf-8").strip().rstrip("/")
    PASS = PASS_FILE.read_text(encoding="utf-8").strip()
    auth = base64.b64encode(f"zee:{PASS}".encode()).decode("ascii")
    req = urllib.request.Request(
        f"{base}/api/cc-chat",
        headers={"Authorization": f"Basic {auth}", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("messages") or data.get("items") or []
    return []

def load_last_ts():
    if TS_FILE.exists():
        try: return int(TS_FILE.read_text().strip())
        except: pass
    return 0

def save_last_ts(ts):
    TS_FILE.write_text(str(ts), encoding="utf-8")

def main():
    # Init from latest seen so we don't replay history on monitor start
    msgs = read_inbox()
    zee_msgs = [m for m in msgs if m.get("from") == "zee"]
    last_ts = zee_msgs[-1].get("ts", 0) if zee_msgs else 0
    save_last_ts(last_ts)
    sys.stdout.write(f"[chat-monitor] armed, last zee ts={last_ts}, "
                     f"polling every {POLL_SEC}s\n")
    sys.stdout.flush()

    while True:
        time.sleep(POLL_SEC)
        try:
            msgs = read_inbox()
        except Exception as e:
            sys.stdout.write(f"[chat-monitor] poll-fail: {e}\n")
            sys.stdout.flush()
            continue
        last_ts = load_last_ts()
        new_msgs = [m for m in msgs
                    if m.get("from") == "zee" and m.get("ts", 0) > last_ts]
        if new_msgs:
            for m in new_msgs:
                text = (m.get("text") or "").replace("\n", " ")[:240]
                ts = m.get("ts", 0)
                sys.stdout.write(f"ZEE_MSG ts={ts} text={text}\n")
                sys.stdout.flush()
            save_last_ts(max(m["ts"] for m in new_msgs))

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
