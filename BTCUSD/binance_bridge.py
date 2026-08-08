"""binance_bridge.py — clean 24/7 Bitcoin M1 bars straight from Binance's public API.

Why not TradingView (2026-08-08): OANDA's BTCUSD is a CFD that closes with forex on
Friday — its chart froze at 20:59 UTC. And the TradingView desktop, left unattended,
delivered half-empty bars. Binance's public klines endpoint needs no key, no browser
and no window in focus, and it carries REAL exchange volume — which is the whole
point of Zee's method.

Volume is fractional BTC, so it is stored x1000 as an integer: every rule in the
strategy is RELATIVE, so the unit never matters, but int() truncation would have
destroyed the signal.

    py BTCUSD/binance_bridge.py            # once
    py BTCUSD/binance_bridge.py --loop 20  # daemon
"""
import argparse, csv, json, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

OUT = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/btc_m1.csv")
API = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit={n}"
HDR = {"User-Agent": "Mozilla/5.0"}


def pull(n=500):
    req = urllib.request.Request(API.format(n=n), headers=HDR)
    return json.load(urllib.request.urlopen(req, timeout=20))


def write(rows):
    tmp = OUT.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_unix", "open", "high", "low", "close", "volume"])
        for k in rows:
            w.writerow([int(k[0] // 1000), k[1], k[2], k[3], k[4],
                        int(round(float(k[5]) * 1000))])
    tmp.replace(OUT)
    return len(rows)


def once():
    rows = pull()
    n = write(rows)
    a = datetime.fromtimestamp(rows[0][0] / 1000, tz=timezone.utc)
    b = datetime.fromtimestamp(rows[-1][0] / 1000, tz=timezone.utc)
    print(f"[binance_bridge] wrote {n} M1 bars ({a:%m-%d %H:%M} .. {b:%m-%d %H:%M} UTC) "
          f"-> {OUT.name}   last {float(rows[-1][4]):,.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="poll every N seconds (0 = once)")
    a = ap.parse_args()
    while True:
        try:
            once()
        except Exception as e:
            print(f"[binance_bridge] ERROR: {e}")
        if not a.loop:
            break
        time.sleep(a.loop)
