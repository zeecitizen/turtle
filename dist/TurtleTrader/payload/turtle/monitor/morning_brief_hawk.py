"""morning_brief_hawk.py - daily 06:25 PKT pre-Session1 reminder + state summary.

Fires once per day, 5 minutes before validated Session1 opens (06:30 PKT =
01:30 UTC). Sends Zee a chat ping with:
  - Yesterday's final P&L (from turtle_fills)
  - 7-day rolling P&L + WR
  - EA heartbeat
  - Open tasks
  - Anything in memory.md wall-of-shame added in last 24h
"""
import sys, time, json, csv, urllib.request, base64
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8")
UTC = timezone.utc
PKT = timezone(timedelta(hours=5))

ROOT       = Path(__file__).resolve().parent.parent
URL_FILE   = ROOT / "monitor" / "cloudflared_url.txt"
PASS_FILE  = ROOT / "monitor" / ".dashboard_password"
COMMON     = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
FILLS_CSV  = COMMON / "turtle_fills.csv"
STATE_JSON = COMMON / "feb11_state_88011.json"
TASKS_MD   = ROOT / "tasks.md"


def send_chat(text):
    base = URL_FILE.read_text(encoding="utf-8").strip().rstrip("/")
    PASS = PASS_FILE.read_text(encoding="utf-8").strip()
    auth = base64.b64encode(f"zee:{PASS}".encode()).decode()
    data = json.dumps({"text": text, "from": "claude_code"}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{base}/api/cc-chat/send", data=data, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "Authorization": f"Basic {auth}",
                 "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64) Chrome/140.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8")[:200]


def yesterday_pnl():
    yesterday = (datetime.now(tz=UTC) - timedelta(days=1)).strftime("%Y.%m.%d")
    if not FILLS_CSV.exists(): return None, 0, 0, 0
    pnl = 0; w = 0; l = 0; n = 0
    with open(FILLS_CSV, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f); next(rdr, None)
        for r in rdr:
            if not r or not r[0].startswith(yesterday): continue
            try: p = float(r[7])
            except: continue
            n += 1; pnl += p
            if p > 0: w += 1
            elif p < 0: l += 1
    return pnl, w, l, n


def week_pnl():
    cutoff_prefix = (datetime.now(tz=UTC) - timedelta(days=7)).strftime("%Y.%m.%d")
    pnl = 0; w = 0; l = 0; n = 0
    if not FILLS_CSV.exists(): return None, 0, 0, 0
    with open(FILLS_CSV, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f); next(rdr, None)
        for r in rdr:
            if not r or len(r) < 8: continue
            if r[0][:10].replace(".", "-") < cutoff_prefix.replace(".", "-"): continue
            try: p = float(r[7])
            except: continue
            n += 1; pnl += p
            if p > 0: w += 1
            elif p < 0: l += 1
    return pnl, w, l, n


def open_tasks():
    if not TASKS_MD.exists(): return []
    out = []
    text = TASKS_MD.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("## TASK-"):
            # extract status by looking for "CLOSED" in subsequent block
            num = line.split("TASK-")[1].split(" ")[0]
            desc = line.split("—", 1)[1].strip() if "—" in line else ""
            out.append((num, desc))
    # Filter closed
    open_only = []
    for num, desc in out:
        # crude: re-read full text and look for "TASK-NNN ... CLOSED" pattern
        m = f"TASK-{num}"
        i = text.find(m)
        rest = text[i:] if i >= 0 else ""
        # next "## TASK-" or end
        nxt = rest.find("\n## ", 5)
        block = rest if nxt < 0 else rest[:nxt]
        if "**CLOSED**" not in block: open_only.append((num, desc))
    return open_only


def main():
    now_pkt = datetime.now(tz=UTC).astimezone(PKT)
    y_pnl, yw, yl, yn = yesterday_pnl()
    w_pnl, ww, wl, wn = week_pnl()
    tasks = open_tasks()
    # Heartbeat
    hb = "—"
    if STATE_JSON.exists():
        try:
            age = (datetime.now(tz=UTC).timestamp() - STATE_JSON.stat().st_mtime)
            hb = f"{age:.0f}s ago" if age < 60 else f"{age/60:.0f}m ago" if age < 3600 else f"{age/3600:.1f}h ago"
        except: pass
    y_pnl_str = f"${y_pnl:+.2f}" if y_pnl is not None else "n/a"
    w_pnl_str = f"${w_pnl:+.2f}" if w_pnl is not None else "n/a"
    msg = (
        f"Morning Zee, {now_pkt.strftime('%H:%M PKT')} — Session1 opens in 5 min.\n\n"
        f"Yesterday: {y_pnl_str}  ({yw}W/{yl}L, n={yn})\n"
        f"Last 7 days: {w_pnl_str}  ({ww}W/{wl}L, n={wn})\n"
        f"EA heartbeat: {hb}\n\n"
        f"Open tasks ({len(tasks)}):\n" +
        ("\n".join(f"  TASK-{n}: {d}" for n, d in tasks[:5]) if tasks else "  (none)") +
        "\n\nReply 'close NNN' to close any task."
    )
    print(msg)
    try:
        send_chat(msg)
        print("[morning-brief] sent")
    except Exception as e:
        print(f"[morning-brief] send failed: {e}")


def loop():
    """Fire once per day at 06:25 PKT (01:25 UTC)."""
    while True:
        now = datetime.now(tz=UTC)
        target = now.replace(hour=1, minute=25, second=0, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
        wait = (target - now).total_seconds()
        print(f"[morning-brief] sleeping {wait:.0f}s until {target.strftime('%Y-%m-%d %H:%M UTC')}")
        time.sleep(wait)
        try:
            main()
        except Exception as e:
            print(f"[morning-brief] crash: {e}")


if __name__ == "__main__":
    if "--loop" in sys.argv: loop()
    else: main()
