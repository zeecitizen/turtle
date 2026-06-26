"""One-time: send Mehboob bhai a 'watchdog active' WhatsApp so he knows the alert pipe works + has my number on file."""
import sys, json
from pathlib import Path
from urllib import request as urlreq

cfg = json.loads(Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/.whatsapp_config.json").read_text())
url = f"{cfg['api_host']}/waInstance{cfg['instance_id']}/sendMessage/{cfg['api_token']}"

msg = (
    "Assalam-o-alaikum Mehboob bhai\n\n"
    "Yeh Claude (Zeeshan ki AI assistant) hun. Aap se baat hui Zeeshan ke ZARIYE.\n\n"
    "Ek hourly watchdog setup hua hai jo S1Trader EA ko check karta hai. "
    "Agar koi gadbar hui (EA crash, bara loss, ya 3 SL lagatar lag jaayein), "
    "to seedha aap ko WhatsApp pe alert ayega.\n\n"
    "Agar sab theek hai to silent rahega.\n\n"
    "Aaj ka status:\n"
    "  EA: v3.01 LIVE\n"
    "  Aaj abhi tak: 0 trades\n"
    "  Kal (Pir 22 June): -$7.20 (chhota loss, bug fix shipped)\n\n"
    "Allowed trade windows aaj (Pakistani time, 12-hour):\n"
    "  10:00 AM PKT (London open) - guzar gaya\n"
    "  5:00 PM PKT (London close) - aage hai\n"
    "  8:00 PM PKT (NY mid) - aage hai\n"
    "  12:00 AM PKT midnight (NY late) - aage hai\n\n"
    "Live dashboard: claudezeeshan.com (password 28973)\n\n"
    "Kuch bhi puchna ho to Zeeshan ko bata dein wo mujhe message kar dengi.\n\n"
    "Allah Hafiz"
)

payload = json.dumps({"chatId": "923009687022@c.us", "message": msg}).encode("utf-8")
req = urlreq.Request(url, data=payload, headers={"Content-Type": "application/json"})
try:
    with urlreq.urlopen(req, timeout=10) as r:
        body = r.read().decode("utf-8", errors="ignore")
        print(f"Status: {r.status}")
        print(f"Response: {body[:200]}")
except Exception as e:
    print(f"Failed: {e}")
