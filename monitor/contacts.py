"""contacts.py - the WhatsApp chat ids and the dashboard password, read from private files that are NOT in git.

The repository is public (2026-11-15), so no phone number and no password is written in any tracked file:

    monitor/.contacts.json        {"zee": "<number>@c.us", "shano": "<number>@c.us", "mehboob": "<number>@c.us"}
    monitor/.dashboard_password   the /me dashboard password (the dashboard server reads the same file)

On a new machine copy monitor/contacts.example.json to monitor/.contacts.json and fill in the real numbers.

    from contacts import CONTACTS, DASH_PW
    wa_send(msg, CONTACTS["zee"])
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


class _Contacts(dict):
    def __missing__(self, name):
        raise KeyError(f'no WhatsApp contact "{name}": add it to monitor/.contacts.json (see monitor/contacts.example.json)')


def _load():
    try:
        with open(os.path.join(_HERE, ".contacts.json"), encoding="utf-8") as f:
            return _Contacts(json.load(f))
    except (OSError, ValueError):
        return _Contacts()


def _password():
    try:
        with open(os.path.join(_HERE, ".dashboard_password"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


CONTACTS = _load()
DASH_PW = _password()
