"""profit_pulse_hawk.py — the "this feels like a LOT, the urge to grab is real" hawk.

Zee's ask (2026-05-22): build a system that FEELS a big floating profit like a human
and lets him grab it with one tap. This watcher reads each EA's heartbeat (which now
writes floating_usd + bigness = floating / avg_winner), and when the profit crosses a
"that's a lot" threshold it WhatsApps Zee a human-voiced alert with a one-tap GRAB link.

It does NOT close anything itself — tapping the link hits the dashboard /grab endpoint,
which drops a command file the EAs read and close on. Feeling = here. Decision = Zee's.

Run:  py profit_pulse_hawk.py            (single check)
      py profit_pulse_hawk.py --loop     (every 20s; this is how the dashboard restarts it)
"""
import sys
import json
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
STATE_FILES = ["s3_trader_state.json", "s1_trader_state.json", "nsnd_trader_state.json"]
PW_FILE = SCRIPT_DIR / ".dashboard_password"
PULSE_STATE = SCRIPT_DIR / ".profit_pulse_state.json"
LOG = SCRIPT_DIR / "profit_pulse_hawk.log"

GRAB_BASE = "https://me.claudezeeshan.com/grab"
ALERT_BIGNESS = 1.5        # below this it doesn't "feel like a lot" — stay quiet
TIER_COOLDOWN_S = 1800     # don't re-nag the same tier for 30 min
LOOP_SECONDS = 20


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_mt5_json(path: Path):
    """MT5 FILE_TXT writes UTF-16-LE w/ BOM. Decode then parse."""
    b = path.read_bytes()
    if b[:2] == b"\xff\xfe":
        text = b[2:].decode("utf-16-le")
    elif b[:3] == b"\xef\xbb\xbf":
        text = b[3:].decode("utf-8")
    else:
        text = b.decode("utf-8", "ignore")
    return json.loads(text)


def read_pulse():
    """Aggregate floating P&L + max bigness across the live EAs."""
    floating, n_open, bigness = 0.0, 0, 0.0
    for fn in STATE_FILES:
        p = COMMON / fn
        if not p.exists():
            continue
        # ignore stale heartbeats (>60s old) so we don't alert on a frozen file
        if time.time() - p.stat().st_mtime > 60:
            continue
        try:
            d = read_mt5_json(p)
        except Exception:
            continue
        f = d.get("floating_usd")
        if isinstance(f, (int, float)):
            floating += f
            n_open += int(d.get("n_open", 0) or 0)
            bigness = max(bigness, float(d.get("bigness", 0) or 0))
    return round(floating, 2), n_open, round(bigness, 2)


def tier_of(bigness):
    if bigness >= 4.0:
        return 3
    if bigness >= 2.5:
        return 2
    if bigness >= ALERT_BIGNESS:
        return 1
    return 0


def message_for(tier, floating, n_open, bigness, url):
    pos = f"{n_open} trade{'s' if n_open != 1 else ''}"
    if tier == 3:
        head = f"🤑🤑 *HUGE* — +${floating:.0f} floating on {pos}"
        body = f"That's *{bigness:.1f}× your average winner*. The urge to grab it is REAL."
    elif tier == 2:
        head = f"🤑 +${floating:.0f} floating on {pos}"
        body = f"That's *{bigness:.1f}× a normal winner* — that's a LOT. Urge to grab is real."
    else:
        head = f"👀 +${floating:.0f} floating on {pos}"
        body = f"{bigness:.1f}× your average winner — a nice chunk is building."
    return (f"{head}\n{body}\n\n"
            f"🫡 *Tap to GRAB it all now:*\n{url}\n\n"
            f"…or let it ride — breakeven's already locked, so it can't round-trip to a loss. Your call.")


def load_state():
    try:
        return json.loads(PULSE_STATE.read_text("utf-8"))
    except Exception:
        return {"last_tier": 0, "last_alert_ts": 0}


def save_state(s):
    try:
        PULSE_STATE.write_text(json.dumps(s), "utf-8")
    except Exception:
        pass


def grab_url():
    try:
        pw = PW_FILE.read_text("utf-8").strip()
    except Exception:
        pw = ""
    return f"{GRAB_BASE}?key={pw}"


def send_whatsapp(msg):
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from broadcast import broadcast_to
        ok = broadcast_to("zeeshan", msg)
        log(f"WHATSAPP -> zeeshan: {'sent' if ok else 'FAILED'}")
        return ok
    except Exception as e:
        log(f"WHATSAPP_ERR: {e}")
        return False


def check_once():
    floating, n_open, bigness = read_pulse()
    tier = tier_of(bigness)
    st = load_state()
    now = time.time()

    # episode ended (profit faded / closed) → reset so the next surge re-alerts
    if tier == 0:
        if st.get("last_tier", 0) != 0:
            log(f"pulse faded (floating ${floating}, bigness {bigness}) — reset")
        save_state({"last_tier": 0, "last_alert_ts": 0})
        return

    # alert when we climb to a higher tier, or after the cooldown for the same tier
    climbed = tier > st.get("last_tier", 0)
    cooled = (now - st.get("last_alert_ts", 0)) > TIER_COOLDOWN_S
    if climbed or cooled:
        msg = message_for(tier, floating, n_open, bigness, grab_url())
        send_whatsapp(msg)
        log(f"ALERT tier={tier} floating=${floating} bigness={bigness}x n={n_open}")
        save_state({"last_tier": tier, "last_alert_ts": now})
    else:
        log(f"holding (tier {tier}, floating ${floating}, bigness {bigness}x) — already alerted")


def main():
    loop = "--loop" in sys.argv
    log(f"Profit Pulse Hawk start (loop={loop}, alert>= {ALERT_BIGNESS}x avg winner)")
    while True:
        try:
            check_once()
        except Exception as e:
            log(f"ERR: {e}")
        if not loop:
            break
        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    main()
