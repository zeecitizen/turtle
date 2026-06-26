"""Update weekly_tracker.json for current week (2026-06-22 to 2026-06-28)."""
import re, json
from pathlib import Path

TERMINAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8/MQL5/Logs")
TRACKER = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/weekly_tracker.json")


def day_pnl(date_str):
    """date_str like '20260622'."""
    log = TERMINAL / f"{date_str}.log"
    if not log.exists():
        return None
    content = log.read_bytes().decode("utf-16le", errors="ignore")
    autoc = re.findall(r"AUTO-CLOSE-MS[^\n]*after \d+ms: [+-]?\d+\.\d+pts = \$([+-]?\d+\.\d+)", content)
    sl_hits = re.findall(r"\[sl ", content)
    fills = re.findall(r"\[FILLED\]", content)
    total = sum(float(x) for x in autoc)
    return {
        "fills": len(fills),
        "auto_close_pnl": round(total, 2),
        "sl_hits": len(sl_hits),
    }


mon_22 = day_pnl("20260622")
tue_23 = day_pnl("20260623")
print(f"Mon 06-22: {mon_22}")
print(f"Tue 06-23: {tue_23}")
print()

# Build current week structure
current = json.loads(TRACKER.read_text())

# Archive old week
old = {k: current[k] for k in ("week_starts", "ea_version", "lot_size", "days")}
if "archive" not in current:
    current["archive"] = []
current["archive"].append(old)

# New week (2026-06-22 to 2026-06-28)
current["week_starts"] = "2026-06-22"
current["ea_version"] = "v3.01 (canonical UHV + 4 quality gates + time-window)"
current["lot_size"] = 0.30
current["days"] = [
    {
        "day": "Monday",
        "date": "2026-06-22",
        "expected_usd": None,
        "actual_usd": mon_22["auto_close_pnl"] if mon_22 else None,
        "notes": f"v3.00 attached. Auto-close bug fired at 596ms despite runtime=0. Caused -$7.20. v3.01 source hard-codes auto_close=0."
    },
    {
        "day": "Tuesday",
        "date": "2026-06-23",
        "expected_usd": None,
        "actual_usd": tue_23["auto_close_pnl"] if tue_23 else None,
        "notes": f"v3.01 LIVE. Mehboob bhai supervising. Fills so far: {tue_23['fills'] if tue_23 else 0}."
    },
    {
        "day": "Wednesday",
        "date": "2026-06-24",
        "expected_usd": None,
        "actual_usd": None,
        "notes": ""
    },
    {
        "day": "Thursday",
        "date": "2026-06-25",
        "expected_usd": None,
        "actual_usd": None,
        "notes": ""
    },
    {
        "day": "Friday",
        "date": "2026-06-26",
        "expected_usd": None,
        "actual_usd": None,
        "notes": ""
    },
    {
        "day": "Saturday",
        "date": "2026-06-27",
        "expected_usd": 0,
        "actual_usd": None,
        "notes": "market closed"
    },
    {
        "day": "Sunday",
        "date": "2026-06-28",
        "expected_usd": 0,
        "actual_usd": None,
        "notes": "market closed"
    }
]

TRACKER.write_text(json.dumps(current, indent=2))
print(f"Wrote {TRACKER}")
print()
print(json.dumps({k: current[k] for k in ("week_starts","ea_version","lot_size","days")}, indent=2)[:1000])
