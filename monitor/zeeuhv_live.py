"""zeeuhv_live.py — the live scoreboard for ZeeUHV, against what the tester promised.

Zee attached ZeeUHV to the gold chart on 2026-08-11 (demo account). Until that moment
its 93.3% rested on 1,608 TESTER trades and zero live fills, which is the one gap no
amount of backtesting can close.

This watches only ZeeUHV's own fills — it tags every order `zee_buy` / `zee_sell`, and
CaseSignalExecutor is still on the same chart, so filtering by comment is what keeps the
two apart. Reading them together would tell us nothing about either.

THE NUMBER TO BEAT, and it must stay visible while the live sample is still tiny:

    tester, 1,608 trades over 103 days   93.28%
    tester, Feb 11 and Aug 5-10 unseen   100.00%

A live win rate below about 85% over a meaningful number of fills would say the tester
is flattering us; at 90%+ it is confirmed where it counts. Twenty fills decide nothing —
the honest threshold is a week.

    py monitor/zeeuhv_live.py            # scoreboard now
    py monitor/zeeuhv_live.py --loop 300 # keep watching
"""
import argparse
import csv
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

FILLS = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/turtle_fills.csv")
TESTED_WR = 93.28

# The moment ZeeUHV was first attached, read from its own init line in the terminal log.
# WITHOUT THIS the "[tp" fingerprint sweeps up every take-profit fill in the entire
# history — on 2026-08-11 that produced "108 fills, +$5,010, 100%", which I very nearly
# reported to Zee as a live result. A fingerprint with no time anchor is not a filter.
START = (Path(__file__).with_name(".zeeuhv_start").read_text(encoding="utf-8").strip()
         if Path(__file__).with_name(".zeeuhv_start").exists() else "2026.08.11 00:33:30")


def load():
    """ZeeUHV's fills only. The comment is the only thing distinguishing them from the
    ghost's, because turtle_fills.csv carries no magic number column."""
    if not FILLS.exists():
        return []
    out = []
    for r in csv.DictReader(FILLS.open(errors="ignore")):
        c = (r.get("comment") or "").lower()
        # 2026-08-11: MT5 OVERWRITES the order comment with "[tp ...]" or "[sl ...]"
        # when the broker closes a position, so zee_buy/zee_sell is wiped on exactly the
        # fills we most want to count. The first morning of live trading was therefore
        # attributed entirely to the ghost, and Zee spotted it because the SIZES were
        # wrong — the ghost scalps $0.20-0.50 and these were $10.
        #
        # Two fingerprints survive the overwrite:
        #   "[tp" — ZeeUHV is the only engine on that chart using a fixed take-profit;
        #           the ghost trails a stop and always closes "[sl".
        #   a P&L near $10 at 0.10 lots — that is TP 1.00 point, its signature.
        if r["broker_time"] < START:          # before it was ever attached
            continue
        looks_like_zee = ("zee_" in c) or ("[tp" in c)
        if not looks_like_zee:
            continue
        if "XAU" not in (r.get("symbol") or "").upper():
            continue
        try:
            out.append(dict(t=r["broker_time"], side=r["direction"].replace("_closed", ""),
                            lots=float(r["volume"]), px=float(r["close_price"]),
                            pnl=float(r["net_pnl"]), comment=r.get("comment", "")))
        except Exception:
            continue
    return out


def report():
    f = load()
    age = (time.time() - FILLS.stat().st_mtime) / 60 if FILLS.exists() else 9999
    print(f"ZeeUHV LIVE — {datetime.now(timezone.utc):%a %d %b %H:%M} UTC "
          f"(fills file {age:.0f} min old)\n")
    if not f:
        print("   no ZeeUHV fills yet.")
        print("   It fires only on a lawful setup: trend + valid retracement + a UHV with")
        print("   body >= 0.5 + a quieter breakout through it. In the tester that was about")
        print("   16 trades a day, so a quiet hour or two is normal, not a fault.")
        return
    pnl = [x["pnl"] for x in f]
    w = [x for x in pnl if x > 0]
    l = [x for x in pnl if x <= 0]
    wr = len(w) / len(pnl) * 100
    print(f"   {len(f)} fills · {len(w)}W / {len(l)}L = {wr:.1f}%   (tester said {TESTED_WR:.1f}%)")
    print(f"   net ${sum(pnl):+.2f}")
    if w:
        print(f"   avg win  ${statistics.mean(w):+.2f}   best ${max(w):+.2f}")
    if l:
        print(f"   avg loss ${statistics.mean(l):+.2f}   worst ${min(l):+.2f}")
    print()
    # the honest read on how much this sample can support
    if len(f) < 20:
        verdict = "far too few to mean anything — keep going"
    elif wr >= 90:
        verdict = "holding up against the tester"
    elif wr >= 85:
        verdict = "slightly under the tester, within reach of noise"
    else:
        verdict = "BELOW the tester — if this holds past 50 fills, the tester was flattering us"
    print(f"   verdict: {verdict}")
    print(f"\n   last {min(10, len(f))} fills:")
    for x in f[-10:]:
        print(f"      {x['t'][11:]}  {x['side']:4s} {x['lots']:.2f} @ {x['px']:9.2f}  ${x['pnl']:+7.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0)
    a = ap.parse_args()
    while True:
        report()
        if not a.loop:
            break
        print()
        time.sleep(a.loop)
