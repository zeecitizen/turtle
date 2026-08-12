"""atmos_guard.py — watches the Atmos NOVA challenge and shouts before the cliff.

Zee, 2026-08-12, on running ZeeUHV at 0.10 lots on the live challenge:
    "0.1 is an okay lot since our system did fine in the LIVE environment on blueberry,
     it can do fine on Atmos too ;)"

His call, and it stands. This exists because the two accounts fail differently:

    Blueberry demo   $4,123, no rules   a -$800 loss is a bad day you trade out of
    Atmos challenge  $10,000, 8% cap    a -$800 loss ENDS the account

That is a cliff, not a slope. Nothing here blocks a trade or closes a position — Zee
decides that. What it does is make the edge of the cliff VISIBLE while there is still
room to step back, because the challenge rules are enforced by Atmos silently and
retroactively: you find out you failed after it has already happened.

    py monitor/atmos_guard.py              # one look
    py monitor/atmos_guard.py --loop 60    # keep watch
"""
import argparse
import csv
import glob
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TERM = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/59CFBA1C032A5059FF08EAB8C724EDCD")
COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")

# The NOVA rules as recorded in memory. If Atmos publishes different numbers, these are
# the ones to correct — every threshold below is derived from them.
ACCOUNT = 10000.0
DAILY_LOSS_PCT = 4.0
MAX_LOSS_PCT = 8.0
TARGET_PCT = 5.0
# Two engines now share this account, and they carry very different risk.
ENGINES = {88094: "ZeeUHV     (0.10 lots)",
           88095: "ZeeUHV v2  (OANDA volume)",
           88096: "BrainExec  (0.01 lots)"}
MAGIC = 88094


def atmos_fills():
    """Atmos trades, separated from Blueberry's. Prefer a dedicated file; otherwise fall
    back to the shared one filtered by magic — and say so, because the magic column was
    blank on every recent row and a filter that silently matches nothing is worse than
    no filter at all."""
    ded = COMMON / "atmos_fills.csv"
    if ded.exists():
        rows = list(csv.DictReader(ded.open(errors="ignore")))
        return rows, "atmos_fills.csv (dedicated)"
    shared = COMMON / "turtle_fills.csv"
    if not shared.exists():
        return [], "no fills file at all"
    rows = [r for r in csv.DictReader(shared.open(errors="ignore"))
            if (r.get("magic") or "").strip() == str(MAGIC)]
    if not rows:
        return [], ("turtle_fills.csv — but NO row carries magic %d, so Atmos trades "
                    "cannot be told from Blueberry's. Set InpFileName=atmos_fills.csv "
                    "on the Atmos TurtleTradeLogger." % MAGIC)
    return rows, "turtle_fills.csv filtered by magic"


def terminal_state():
    """What the terminal itself last said about the account."""
    out = {}
    fs = sorted(glob.glob(str(TERM / "logs" / "*.log")), key=os.path.getmtime)
    if not fs:
        return out
    try:
        t = Path(fs[-1]).read_text(encoding="utf-16", errors="ignore")
    except Exception:
        t = Path(fs[-1]).read_text(errors="ignore")
    out["log_age_min"] = (time.time() - os.path.getmtime(fs[-1])) / 60
    for l in t.splitlines():
        m = re.search(r"'(\d+)': authorized on (\S+)", l)
        if m:
            out["account"], out["server"] = m.group(1), m.group(2)
        m = re.search(r"(\d+) positions, (\d+) orders", l)
        if m:
            out["positions"], out["orders"] = int(m.group(1)), int(m.group(2))
    # which timeframe is the EA on? H1 would mean it is not running Zee's strategy.
    for d in ("MQL5/Logs", "logs"):
        for f in sorted(glob.glob(str(TERM / d / "*.log")), key=os.path.getmtime)[-2:]:
            try:
                tt = Path(f).read_text(encoding="utf-16", errors="ignore")
            except Exception:
                tt = Path(f).read_text(errors="ignore")
            for m in re.finditer(r"ZeeUHV\w*\s+\((\w+),(\w+)\)", tt):
                out["symbol"], out["timeframe"] = m.group(1), m.group(2)
    return out


def report():
    st = terminal_state()
    rows, source = atmos_fills()
    print(f"ATMOS GUARD — {datetime.now(timezone.utc):%a %d %b %H:%M} UTC\n")
    print(f"   account   {st.get('account','?')} on {st.get('server','?')}")
    print(f"   terminal  log {st.get('log_age_min', 9999):.0f} min old · "
          f"{st.get('positions','?')} positions open")
    tf = st.get("timeframe")
    if tf:
        flag = "" if tf == "M1" else "   <-- NOT M1. Every rule in ZeeUHV is built for M1."
        print(f"   EA on     {st.get('symbol','?')} {tf}{flag}")
    print(f"   fills     {source}")
    print()
    if not rows:
        print("   no Atmos fills yet — nothing to measure.")
        print()
        print("   WHAT EACH ENGINE CAN COST ON ONE LOSING STACK:")
        for mg, name in ENGINES.items():
            lots = 0.01 if mg == 88096 else 0.10
            n = 4 if mg == 96 else (5 if mg == 88094 else 4)
            worst = n * 20 * (lots / 0.10) * 10
            print(f"      {name:26s} {n} tickets -> ${worst:,.0f}  "
                  f"({worst/ACCOUNT*100:.1f}% of the account)"
                  + ("   <-- alone exceeds the 8% cap" if worst > ACCOUNT*MAX_LOSS_PCT/100 else ""))
    else:
        today = datetime.now().strftime("%Y.%m.%d")
        day = [float(r["net_pnl"]) for r in rows if r["broker_time"].startswith(today)]
        allp = [float(r["net_pnl"]) for r in rows]
        dpl, tpl = sum(day), sum(allp)
        dlim, mlim = ACCOUNT * DAILY_LOSS_PCT / 100, ACCOUNT * MAX_LOSS_PCT / 100
        print(f"   today     ${dpl:+,.2f}   of a ${dlim:,.0f} daily limit "
              f"({abs(min(dpl,0))/dlim*100:5.1f}% used)")
        print(f"   overall   ${tpl:+,.2f}   of a ${mlim:,.0f} max limit "
              f"({abs(min(tpl,0))/mlim*100:5.1f}% used)")
        print(f"   target    ${ACCOUNT*TARGET_PCT/100:,.0f}  "
              f"({tpl/(ACCOUNT*TARGET_PCT/100)*100:5.1f}% of the way)")
        print()
        print("   BY ENGINE:")
        import collections as _c
        by = _c.defaultdict(list)
        for r in rows:
            by[(r.get("magic") or "?").strip()].append(float(r["net_pnl"]))
        for mg, v in sorted(by.items()):
            name = ENGINES.get(int(mg) if mg.isdigit() else 0, f"magic {mg}")
            w = sum(1 for x in v if x > 0)
            print(f"      {name:26s} {len(v):3d} fills · {w}W/{len(v)-w}L · ${sum(v):+9,.2f}")
        print()
        for label, val, lim in (("TODAY", dpl, dlim), ("OVERALL", tpl, mlim)):
            used = abs(min(val, 0)) / lim
            if used >= 0.75:
                print(f"   *** {label}: {used*100:.0f}% OF THE LIMIT IS GONE. "
                      f"One more losing stack likely ends it. ***")
            elif used >= 0.5:
                print(f"   ** {label}: half the limit used. **")
    print()
    # the thing that makes 0.10 lots a cliff rather than a slope
    stack_loss = 4 * 20 * 10        # 4 tickets x 20 points x $10/point at 0.10 lots
    print(f"   at 0.10 lots a 4-ticket stack stopping out costs ${stack_loss:,} "
          f"= {stack_loss/ACCOUNT*100:.0f}% of the account")
    print(f"   the daily limit is {DAILY_LOSS_PCT:.0f}% and the hard cap {MAX_LOSS_PCT:.0f}% — "
          f"so ONE such stack breaches both.")


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
