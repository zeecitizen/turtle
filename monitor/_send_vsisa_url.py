import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); from contacts import CONTACTS, DASH_PW  # private, not in git
import json, urllib.request, urllib.parse, sys

cfg = json.load(open(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.whatsapp_config.json"))
host = cfg["api_host"]; iid = cfg["instance_id"]; tok = cfg["api_token"]

NEW_URL = "https://annie-textiles-grateful-repair.trycloudflare.com/vsisa"

msg = (
    "VSISA dashboard back online jaan.\n"
    f"Public URL: {NEW_URL}\n"
    "Paper-trader live (config big=0.80 low=0.60 body=0.90 TP=3R +H1 trend).\n"
    "Backtest baseline: 30 trades / 50% WR / PF 3.1 / +$5,439 / max DD $841.\n"
    "0 live trades yet (waiting for first VSISA setup) — refreshes every 2s."
)

targets = [CONTACTS["zee"], CONTACTS["shano"]]
url = f"{host}/waInstance{iid}/sendMessage/{tok}"

for chat in targets:
    body = json.dumps({"chatId": chat, "message": msg}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = r.read().decode("utf-8")
            print(f"[OK] {chat}: {resp}")
    except Exception as e:
        print(f"[FAIL] {chat}: {e}")
