"""One-off WhatsApp to Zee: ack chat broken + summarize Feb 11 finding."""
import json, urllib.request

cfg = json.load(open(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.whatsapp_config.json"))
host = cfg["api_host"]; iid = cfg["instance_id"]; tok = cfg["api_token"]

msg = (
    "Jaan, /me chat pe aapka message dekha — sorry pichlay 3 messages miss "
    "kar diye, mujhe nudge nahi mila. Ab WhatsApp pe bhi reply karoongi jab "
    "tak chat fix nahi hota.\n\n"
    "Feb 11 strategy ka jawab tayyar hai: aapki 92% WR un-mechanizable hai "
    "kyun ke aap RED candle pe BUY karti hain (anticipation), 32 of your 54 "
    "missed entries wahi pattern. Camel-hump trend + sweep+1.5R = +$30 / "
    "67% WR (mechanical ceiling). Visualization: /feb11-lab pe scroll karein, "
    "magenta arrows = missed entries.\n\n"
    "Chat fix karne ki koshish kar rahi hoon, response within 5 min."
)

url = f"{host}/waInstance{iid}/sendMessage/{tok}"
body = json.dumps({"chatId": "4915119175329@c.us", "message": msg},
                  ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(url, data=body,
    headers={"Content-Type": "application/json; charset=utf-8"})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(f"[OK] {r.read().decode('utf-8')[:200]}")
except Exception as e:
    print(f"[FAIL] {e}")
