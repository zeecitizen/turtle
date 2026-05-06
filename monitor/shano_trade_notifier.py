"""
shano_trade_notifier.py — auto-WhatsApp Shano whenever the EA opens a MAIN trade.

Watches shano_live.json's positions array; when a new MAIN ticket appears
(lots > 0.01), fires a WhatsApp message to Shano so she can mirror-trade.
Also pings on close so she knows when to exit.

Run as a daemon via ensure_daemon.py shano_trade_notifier.py.
"""
import json
import time
import sys
import os
import urllib.request
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
LIVE_PATH = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_live.json")
STATE_PATH = ROOT / "monitor" / ".shano_trade_notifier_state.json"
LOG_PATH = ROOT / "monitor" / "shano_trade_notifier.log"

# WhatsApp credentials — loaded from monitor/.whatsapp_config.json (gitignored).
# Do NOT hardcode secrets here.
WA_CONFIG = ROOT / "monitor" / ".whatsapp_config.json"
SHANO_CHAT = "923364863368@c.us"
ZEE_CHAT   = "4915119175329@c.us"


def _load_whatsapp() -> tuple[str, str]:
    """Returns (send_url, error_message_or_empty)."""
    try:
        cfg = json.loads(WA_CONFIG.read_text())
    except Exception as e:
        return "", f"could not load {WA_CONFIG}: {e}"
    host = cfg.get("api_host", "").rstrip("/")
    inst = cfg.get("instance_id", "")
    token = cfg.get("api_token", "")
    if not (host and inst and token):
        return "", "whatsapp_config missing api_host/instance_id/api_token"
    return f"{host}/waInstance{inst}/sendMessage/{token}", ""

POLL_SEC = 2

# Only mains qualify (probes are 0.01).
MAIN_LOT_MIN = 0.05


def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {"seen_open_tickets": [], "seen_close_keys": []}


def save_state(state: dict) -> None:
    try:
        STATE_PATH.write_text(json.dumps(state))
    except OSError:
        pass


def whatsapp(chat_id: str, message: str) -> bool:
    send_url, err = _load_whatsapp()
    if err:
        log(f"WhatsApp config error: {err}")
        return False
    body = json.dumps({"chatId": chat_id, "message": message}).encode("utf-8")
    req = urllib.request.Request(
        send_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
        return True
    except Exception as e:
        log(f"WhatsApp send failed to {chat_id}: {e}")
        return False


def format_open_message(pos: dict) -> str:
    direction = pos.get("dir", "?").upper()
    lots = pos.get("lots", 0)
    entry = pos.get("entry", 0)
    role = pos.get("role", "main").upper()
    opened = pos.get("opened", "")
    return (
        f"🎯 TRADE OPENED — XAUUSD {direction} {lots} lots @ {entry:.2f}\n"
        f"Time: {opened}\nRole: {role}\n\n"
        f"Follow karna chahein toh abhi {direction} le lein. "
        f"System khud manage karega exit (TRAIL / FEAR_IDEAL etc.)."
    )


def format_close_message(history_entry: dict) -> str:
    when = history_entry.get("time", "")
    direction = history_entry.get("dir", "?").upper()
    lots = history_entry.get("lots", 0)
    pnl = history_entry.get("pnl", 0)
    comment = history_entry.get("comment", "")
    role = "PROBE" if lots <= 0.01 else "MAIN"
    icon = "✅" if pnl > 0 else "❌"
    return (
        f"{icon} TRADE CLOSED ({role}) — XAUUSD {direction} {lots} lots\n"
        f"PnL: ${pnl:+.2f}\nReason: {comment}\nTime: {when}"
    )


def main() -> None:
    log("shano_trade_notifier starting (poll=2s)")
    if not LIVE_PATH.exists():
        log(f"shano_live.json missing at {LIVE_PATH}; idling")
    state = load_state()
    seen_opens = set(state.get("seen_open_tickets", []))
    seen_closes = set(state.get("seen_close_keys", []))

    # On first run, seed seen-sets with current state to avoid pinging old trades.
    bootstrap = not seen_opens and not seen_closes
    if bootstrap:
        try:
            with LIVE_PATH.open() as f:
                d = json.load(f)
            for p in d.get("positions", []):
                seen_opens.add(int(p.get("ticket", 0)))
            for h in d.get("history", []):
                key = f"{h.get('time')}|{h.get('ticket')}"
                seen_closes.add(key)
            log(f"bootstrap: seeded {len(seen_opens)} open + {len(seen_closes)} close keys (no notifications sent)")
        except Exception as e:
            log(f"bootstrap read failed: {e}")
        state["seen_open_tickets"] = sorted(seen_opens)
        state["seen_close_keys"] = sorted(seen_closes)
        save_state(state)

    while True:
        try:
            with LIVE_PATH.open() as f:
                d = json.load(f)
        except Exception as e:
            log(f"live read failed: {e}")
            time.sleep(POLL_SEC)
            continue

        # Detect new opens (mains only).
        for pos in d.get("positions", []):
            tk = int(pos.get("ticket", 0))
            if tk in seen_opens:
                continue
            seen_opens.add(tk)
            lots = pos.get("lots", 0)
            if lots < MAIN_LOT_MIN:
                continue  # skip probes; only main fires interest Shano
            msg = format_open_message(pos)
            if whatsapp(SHANO_CHAT, msg):
                log(f"OPEN ping sent to Shano: ticket={tk} dir={pos.get('dir')} lots={lots} entry={pos.get('entry')}")

        # Detect new closes (mains only — probe noise is too high).
        for h in d.get("history", []):
            key = f"{h.get('time')}|{h.get('ticket')}"
            if key in seen_closes:
                continue
            seen_closes.add(key)
            lots = h.get("lots", 0)
            if lots < MAIN_LOT_MIN:
                continue
            msg = format_close_message(h)
            if whatsapp(SHANO_CHAT, msg):
                log(f"CLOSE ping sent to Shano: ticket={h.get('ticket')} pnl={h.get('pnl')}")

        # Persist state every cycle (cheap; small JSON file).
        # Cap the close-key set to prevent unbounded growth.
        if len(seen_closes) > 500:
            seen_closes = set(sorted(seen_closes)[-300:])
        state["seen_open_tickets"] = sorted(seen_opens)[-300:]
        state["seen_close_keys"] = sorted(seen_closes)
        save_state(state)

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("interrupted")
    except Exception as e:
        log(f"fatal: {e}")
        raise
