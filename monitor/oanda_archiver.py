"""oanda_archiver.py — never lose a bar again (2026-08-06).

The bridge's oanda_m1.csv is a rolling ~7h window; every law trial kept starving
on one day of tape. This daemon appends new bars (dedup by time_unix) to a
permanent history file so the law exams grow stronger every day.

Run:  py monitor/oanda_archiver.py --loop 600
History: monitor/strategy_lab/oanda_m1_history.csv (same columns as the live file)
"""
import csv, sys, time
from pathlib import Path

LIVE = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.csv")
HIST = Path(__file__).parent / "strategy_lab" / "oanda_m1_history.csv"

def archive_once():
    if not LIVE.exists(): return 0
    rows = list(csv.DictReader(LIVE.open(encoding="utf-8")))
    if not rows: return 0
    seen = set()
    if HIST.exists():
        for r in csv.DictReader(HIST.open(encoding="utf-8")):
            seen.add(r["time_unix"])
    new = [r for r in rows[:-1] if r["time_unix"] not in seen]   # skip the forming bar
    if not new: return 0
    write_header = not HIST.exists()
    with HIST.open("a", newline="", encoding="utf-8") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if write_header: wtr.writeheader()
        for r in new: wtr.writerow(r)
    return len(new)

if __name__ == "__main__":
    if "--loop" in sys.argv:
        period = int(sys.argv[sys.argv.index("--loop") + 1])
        print(f"[archiver] appending new bars every {period}s -> {HIST}")
        while True:
            try:
                n = archive_once()
                if n: print(f"[archiver] +{n} bars archived")
            except Exception as e:
                print("[archiver] err:", e, file=sys.stderr)
            time.sleep(period)
    else:
        print(f"  archived {archive_once()} bars -> {HIST}")
