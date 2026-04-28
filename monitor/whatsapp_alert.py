"""
WhatsApp Breakout Alert — sends via Green API (sub-second delivery).
Usage:
  python whatsapp_alert.py --direction sell --price 4749.33 --uhv-key "Green_4749.33"
  python whatsapp_alert.py --direction sell --price 4749.33 --uhv-key "Green_4749.33" --mode headsup

Config: .whatsapp_config.json (instance_id, api_token, chat_id)
"""
import argparse
import json
import sys
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).parent
CONFIG     = SCRIPT_DIR / ".whatsapp_config.json"


def _send(msg: str):
    """Broadcast a message to ALL active contacts via broadcast module."""
    try:
        from broadcast import broadcast
        sent = broadcast(msg)
        print(f"WHATSAPP_BROADCAST: sent to {sent} contacts")
        return sent > 0
    except ImportError:
        # Fallback: send to Shano only (legacy)
        return _send_single(msg, "923364863368@c.us")


def _send_single(msg: str, chat_id: str):
    """Send to a single number (fallback if broadcast module unavailable)."""
    try:
        cfg = json.loads(CONFIG.read_text("utf-8"))
    except Exception as e:
        print(f"WHATSAPP_SKIP: config error — {e}")
        return False

    url = f"{cfg['api_host']}/waInstance{cfg['instance_id']}/sendMessage/{cfg['api_token']}"

    try:
        r = requests.post(url, json={"chatId": chat_id, "message": msg}, timeout=10)
        if r.status_code == 200:
            print(f"WHATSAPP_SENT: {r.json()}")
            return True
        else:
            print(f"WHATSAPP_ERR: HTTP {r.status_code} — {r.text}")
            return False
    except Exception as e:
        print(f"WHATSAPP_SKIP: {e}")
        return False


def _eta_text(gap: float) -> str:
    """Estimate time to breakout based on gap distance. Very rough for XAUUSD 1m."""
    if gap <= 0.10:
        return "seconds mein"
    elif gap <= 0.30:
        return "1-2 minute mein"
    elif gap <= 0.80:
        return "2-3 minute mein"
    elif gap <= 2.00:
        return "5 minute mein"
    else:
        return "kuch der mein"


def send_alert(direction: str, price: float, uhv_key: str, candle_high: float, candle_low: float):
    color = uhv_key.split("_")[0].lower() if "_" in uhv_key else "?"
    side_urdu = "Buy" if direction == "buy" else "Sell"

    msg = (
        f"Shano yar trade le lo {side_urdu} ki at {price:.2f} .. abiiii.. "
        f"kyunke {color} candle ka breakout hogaya hai.. "
        f"XAUUSD ki 0.4 lots theek hain, SL 15 pe, TP 52 pe.."
    )

    print(f"Sending breakout alert: {direction.upper()} @ {price}")
    _send(msg)


def send_headsup(direction: str, price: float, uhv_key: str):
    color = uhv_key.split("_")[0].lower() if "_" in uhv_key else "?"
    move = "neechay" if direction == "sell" else "upar"
    side_urdu = "Buy" if direction == "buy" else "Sell"

    msg = (
        f"Shano suno yar, scene ye hai keh high volume {color} candle mil gayi hai.. "
        f"agar price {price:.2f} se {move} jati hai toh {side_urdu} ka trade lagayenge.. "
        f"tayyar raho yar!"
    )

    print(f"Sending heads-up: {direction} watching {price}")
    _send(msg)


def send_nearby(direction: str, price: float, gap: float):
    move = "neechay" if direction == "sell" else "upar"
    side_urdu = "Buy" if direction == "buy" else "Sell"
    eta = _eta_text(gap)

    msg = (
        f"Shano ready ho jao yar scene ON hai! "
        f"Breakout anay wala hai bass.. price sirf {gap:.2f} door hai.. "
        f"jaisay hi {price:.2f} se {move} jaey, {side_urdu} fire hogi.. "
        f"phone haath mein rakho! Bass {eta} trade letay hain"
    )

    print(f"Sending nearby alert: gap={gap:.2f}")
    _send(msg)


def send_result(direction: str, price: float, pnl: float, peak: float, closed_by: str):
    side_urdu = "Buy" if direction == "buy" else "Sell"
    ai_tag = " (Claude AI ne decide kiya)" if "claude" in closed_by.lower() else ""

    if pnl >= 15:
        msg = (
            f"Shano woh {side_urdu} trade jo li thi {price:.2f} pe, usmein profit hua! "
            f"+${pnl:.2f} ban gaye alhamdulillah.. "
            f"peak ${peak:.2f} tak gayi thi.. badhiya raha yar!{ai_tag}"
        )
    elif pnl >= 0:
        msg = (
            f"Shano woh {side_urdu} trade jo li thi {price:.2f} pe, profit mein band hui.. "
            f"+${pnl:.2f}.. accha raha!{ai_tag}"
        )
    elif closed_by == "hawk_dud":
        msg = (
            f"Shano woh {side_urdu} trade jo li thi {price:.2f} pe, jaldi band kar di kyunke signal kamzor tha.. "
            f"-${abs(pnl):.2f} ka chota sa loss.. bada loss se bacha liya!"
        )
    else:
        msg = (
            f"Shano woh {side_urdu} trade jo li thi {price:.2f} pe, usmein thora loss hua yar.. "
            f"-${abs(pnl):.2f}.. koi nai, next time inshaAllah profit hoga!{ai_tag}"
        )

    print(f"Sending result: pnl=${pnl:.2f}")
    _send(msg)


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--direction", required=True, help="buy or sell")
        parser.add_argument("--price", type=float, required=True, help="UHV level price")
        parser.add_argument("--uhv-key", required=True, help="e.g. Green_4749.33")
        parser.add_argument("--candle-high", type=float, default=0, help="UHV candle high")
        parser.add_argument("--candle-low", type=float, default=0, help="UHV candle low")
        parser.add_argument("--mode", default="breakout", choices=["breakout", "headsup", "nearby", "result"],
                            help="breakout = fire, headsup = UHV detected, nearby = almost, result = post-trade")
        parser.add_argument("--gap", type=float, default=0, help="distance from UHV level (nearby mode)")
        parser.add_argument("--pnl", type=float, default=0, help="P&L in USD (result mode)")
        parser.add_argument("--peak", type=float, default=0, help="peak P&L in USD (result mode)")
        parser.add_argument("--closed-by", default="", help="how trade closed (result mode)")
        args = parser.parse_args()
        if args.mode == "headsup":
            send_headsup(args.direction, args.price, args.uhv_key)
        elif args.mode == "nearby":
            send_nearby(args.direction, args.price, args.gap)
        elif args.mode == "result":
            send_result(args.direction, args.price, args.pnl, args.peak, args.closed_by)
        else:
            send_alert(args.direction, args.price, args.uhv_key, args.candle_high, args.candle_low)
    except Exception as e:
        print(f"WHATSAPP_SKIP: fatal error — {e}")
        sys.exit(0)
