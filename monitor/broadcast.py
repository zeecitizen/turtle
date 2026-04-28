"""
Broadcast Module — Send WhatsApp messages to all registered numbers.

Usage:
    from broadcast import broadcast, broadcast_to

    broadcast("Shano trade le lo!")                    # sends to everyone
    broadcast_to("shano", "Sirf tumhare liye!")       # sends to one person

Add/remove numbers by editing broadcast_list.json.
"""

import json
from pathlib import Path

try:
    import requests as req
except ImportError:
    req = None

SCRIPT_DIR = Path(__file__).parent
WA_CONFIG = SCRIPT_DIR / ".whatsapp_config.json"
BROADCAST_LIST = SCRIPT_DIR / "broadcast_list.json"


def _ensure_list():
    """Create broadcast_list.json with defaults if it doesn't exist."""
    if not BROADCAST_LIST.exists():
        default = {
            "contacts": [
                {"name": "shano", "phone": "923364863368", "chat_id": "923364863368@c.us", "active": True},
                {"name": "zeeshan", "phone": "4915119175329", "chat_id": "4915119175329@c.us", "active": True},
            ]
        }
        BROADCAST_LIST.write_text(json.dumps(default, indent=2), encoding="utf-8")


def _load_contacts() -> list[dict]:
    _ensure_list()
    try:
        data = json.loads(BROADCAST_LIST.read_text("utf-8"))
        return [c for c in data.get("contacts", []) if c.get("active", True)]
    except Exception:
        return []


def _send_one(msg: str, chat_id: str) -> bool:
    """Send a single message to one chat_id via Green API."""
    if not req:
        return False
    try:
        cfg = json.loads(WA_CONFIG.read_text("utf-8"))
        url = f"{cfg['api_host']}/waInstance{cfg['instance_id']}/sendMessage/{cfg['api_token']}"
        r = req.post(url, json={"chatId": chat_id, "message": msg}, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def broadcast(msg: str) -> int:
    """Send message to ALL active contacts. Returns count of successful sends."""
    contacts = _load_contacts()
    sent = 0
    for c in contacts:
        if _send_one(msg, c["chat_id"]):
            sent += 1
    return sent


def broadcast_to(name: str, msg: str) -> bool:
    """Send message to a specific contact by name."""
    contacts = _load_contacts()
    for c in contacts:
        if c["name"].lower() == name.lower():
            return _send_one(msg, c["chat_id"])
    return False


def add_contact(name: str, phone: str):
    """Add a new contact to the broadcast list."""
    _ensure_list()
    data = json.loads(BROADCAST_LIST.read_text("utf-8"))
    # Remove country + prefix, build chat_id
    digits = "".join(d for d in phone if d.isdigit())
    chat_id = f"{digits}@c.us"
    # Check if already exists
    for c in data["contacts"]:
        if c["phone"] == digits:
            c["active"] = True
            c["name"] = name
            BROADCAST_LIST.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return
    data["contacts"].append({"name": name, "phone": digits, "chat_id": chat_id, "active": True})
    BROADCAST_LIST.write_text(json.dumps(data, indent=2), encoding="utf-8")


def remove_contact(name: str):
    """Deactivate a contact (doesn't delete, just sets active=False)."""
    _ensure_list()
    data = json.loads(BROADCAST_LIST.read_text("utf-8"))
    for c in data["contacts"]:
        if c["name"].lower() == name.lower():
            c["active"] = False
    BROADCAST_LIST.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_contacts() -> list[dict]:
    """Return all contacts (active and inactive)."""
    _ensure_list()
    data = json.loads(BROADCAST_LIST.read_text("utf-8"))
    return data.get("contacts", [])
