"""PineConnector Webhook Sender — Fire trades directly to MT5.

Usage:
    python pc_webhook.py buy BTCUSD 0.10
    python pc_webhook.py sell BTCUSD 0.10
    python pc_webhook.py buy BTCUSD 0.10 --tp=2000 --sl=300
    python pc_webhook.py sell XAUUSDm 0.40 --tp=520 --sl=150
    python pc_webhook.py closelong BTCUSD
    python pc_webhook.py closeshort BTCUSD
    python pc_webhook.py closeall
"""

import sys
import requests

LICENSE = "87782869895251"
WEBHOOK_URL = "https://webhook.pineconnector.com"

def fire(action, symbol=None, lots=None, tp=None, sl=None):
    parts = [LICENSE, action]
    if symbol:
        parts.append(symbol)
    if lots:
        parts.append(f"risk={lots}")
    if tp:
        parts.append(f"tp={tp}")
    if sl:
        parts.append(f"sl={sl}")
    msg = ",".join(parts)
    print(f">> {msg}")
    r = requests.post(WEBHOOK_URL, data=msg, headers={"Content-Type": "text/plain"})
    print(f"<< {r.status_code} {r.text}")
    return r

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    action = args[0].lower()
    symbol = args[1] if len(args) > 1 else None
    lots = args[2] if len(args) > 2 else None

    tp = sl = None
    for a in args:
        if a.startswith("--tp="):
            tp = a.split("=")[1]
        if a.startswith("--sl="):
            sl = a.split("=")[1]

    fire(action, symbol, lots, tp, sl)
