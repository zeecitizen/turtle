import json, urllib.request

cfg = json.load(open(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.whatsapp_config.json"))
host = cfg["api_host"]; iid = cfg["instance_id"]; tok = cfg["api_token"]

msg = (
    "/me page is now password-protected jaaaan ❤\n\n"
    "URL: https://bangkok-showers-experiencing-discs.trycloudflare.com/me\n"
    "Username: zee\n"
    "Password: 28973\n\n"
    "Browser pucchega ek baar — username 'zee', password '28973' — aur 'save' kar do. "
    "Phir kabhi nahi pucchega. iPhone pe 'Add to Home Screen' kar lo — app jaisa khulega.\n\n"
    "Sirf yahan tum aa sakte ho, dashboard ki baaki cheezein open hain (open dashboard /shano /vsisa etc baahar se accessible hain, sirf /me locked hai)."
)

url = f"{host}/waInstance{iid}/sendMessage/{tok}"
body = json.dumps({"chatId": "4915119175329@c.us", "message": msg}, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(f"[OK] {r.read().decode('utf-8')}")
except Exception as e:
    print(f"[FAIL] {e}")
