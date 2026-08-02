"""sessions.py — when each market is actually awake.

Zee 2026-08-03: *"Turtle Desktop pe hum clocks dikha sakte hain, taake ye software session
open waghera ka time dikhaye user ko easy way mein."*

Sessions are defined as LOCAL business hours in each city's own timezone and converted with
`zoneinfo`, so daylight saving is handled by the system instead of by hard-coded offsets
that quietly rot twice a year. That mattered the day it was written: the web page's
hand-coded Sydney offset disagreed with ForexFactory by exactly an hour.

It also answers the question that actually matters for this system — *when does GOLD start
trading* — which is not the generic FX open. Gold follows Sydney, so in AEST that is 22:00
UTC, an hour after the FX week technically begins.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CITIES = [
    ("Sydney",   "Australia/Sydney", 8, 17),
    ("Tokyo",    "Asia/Tokyo",       9, 18),
    ("London",   "Europe/London",    8, 17),
    ("New York", "America/New_York", 8, 17),
]


def _fmt(mins):
    mins = int(mins)
    h, m = divmod(max(mins, 0), 60)
    return (f"{h}h {m}m" if h else f"{m}m")


def fx_week_open(now=None):
    """The FX/metals week: Sunday 21:00 UTC to Friday 21:00 UTC."""
    now = now or datetime.now(timezone.utc)
    d = (now.weekday() + 1) % 7          # 0 = Sunday
    m = now.hour * 60 + now.minute
    if d == 6:
        return False
    if d == 0:
        return m >= 21 * 60
    if d == 5:
        return m < 21 * 60
    return True


def fx_opens_in(now=None):
    now = now or datetime.now(timezone.utc)
    d = (now.weekday() + 1) % 7
    m = now.hour * 60 + now.minute
    mins = ((7 - d) % 7) * 1440 + 21 * 60 - m
    if mins <= 0:
        mins += 7 * 1440
    return mins


def status(now=None):
    """One row per city: local time, whether it is trading, and what happens next."""
    now = now or datetime.now(timezone.utc)
    week = fx_week_open(now)
    rows = []
    for city, tz, oh, ch in CITIES:
        local = now.astimezone(ZoneInfo(tz))
        off = local.utcoffset().total_seconds() / 3600.0
        o = int((oh - off) % 24)          # local open  -> UTC hour
        c = int((ch - off) % 24)          # local close -> UTC hour
        m = now.hour * 60 + now.minute
        inside = (o * 60 <= m < c * 60) if o < c else (m >= o * 60 or m < c * 60)
        open_now = inside and week
        if not week:
            note, mins = "weekend", fx_opens_in(now)
        elif open_now:
            note, mins = "ends in", (c * 60 - m) % 1440
        else:
            note, mins = "opens in", (o * 60 - m) % 1440
        rows.append({"city": city, "tz": tz, "local": local.strftime("%H:%M"),
                     "local_12": local.strftime("%I:%M %p").lstrip("0"),
                     "utc_offset": off, "open_utc": o, "close_utc": c,
                     "open": open_now, "note": note, "mins": mins,
                     "in": _fmt(mins)})
    return rows


def gold_note(now=None):
    """Gold does not start with the generic FX open — it starts with Sydney."""
    now = now or datetime.now(timezone.utc)
    syd = next(r for r in status(now) if r["city"] == "Sydney")
    if not fx_week_open(now):
        return f"gold closed · the week opens in {_fmt(fx_opens_in(now))}"
    if syd["open"]:
        return f"gold trading · Sydney is open, {syd['in']} left"
    return (f"gold quiet · the FX week is open but Sydney is not "
            f"({syd['in']} away) — prices barely move until it is")


def to_text(now=None):
    rows = status(now)
    now = now or datetime.now(timezone.utc)
    out = [f"SESSIONS   {now.strftime('%a %d %b %H:%M')} UTC", "=" * 56, ""]
    for r in rows:
        state = "OPEN " if r["open"] else "     "
        out.append(f"  {state} {r['city']:<9} {r['local_12']:>9} local   "
                   f"{r['note']} {r['in']:<8} "
                   f"(UTC {r['open_utc']:02d}:00-{r['close_utc']:02d}:00)")
    out += ["", "  " + gold_note(now)]
    return "\n".join(out)


if __name__ == "__main__":
    print(to_text())
