"""why_no_trade.py — for a window of M5 bars, say which gate each candidate died at.

Zee, 2026-09-17, looking at a chart: "so right now it seems there has been a setup.. can
u check why our EA didnt take it?"

The tester's FUNNEL line gives the aggregate — 123 candidates, 115 not loud, 8 fake, 0
fired — but not WHICH bar he was looking at. This walks every bar in a window as a
candidate reaction and prints the first gate it fails, in the EA's own order, so the
answer is a specific bar and a specific rule rather than a count.

THIS IS A DIAGNOSTIC, NOT A BACKTEST. It explains a decision MT5 already made; it never
promotes anything. The gates mirror mt5/VSISA.mq5 v1.20 as shipped.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CSV = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/vsisa_bars_now.csv")

# v1.20 shipped
SETUP_MIN, SETUP_MAX = 2, 10
SWING_PIVOT, SWING_MIN, SWING_CAP = 3, 5, 200
BIG_PCT, BIG_AVG = 0.80, 1.20
LOW_VOL_PCT = 1.00
BODY_FRAC = 0.35
SWEEP_LOOK = 30


def load():
    rows = list(csv.DictReader(open(CSV)))
    return [{"t": r["time_iso"], "o": float(r["open"]), "h": float(r["high"]),
             "l": float(r["low"]), "c": float(r["close"]),
             "v": int(r["tick_volume"])} for r in rows]


def swing_len(b, frm, side):
    """Bars back to the pivot that began this leg — the EA's yardstick."""
    cap = min(SWING_CAP, len(b) - frm - SWING_PIVOT - 1)
    for k in range(frm + SWING_PIVOT, frm + max(cap, SWING_MIN + 1)):
        if k + SWING_PIVOT >= len(b):
            break
        piv = True
        for q in range(1, SWING_PIVOT + 1):
            if side > 0:
                if b[k]["h"] <= b[k - q]["h"] or b[k]["h"] <= b[k + q]["h"]:
                    piv = False
            else:
                if b[k]["l"] >= b[k - q]["l"] or b[k]["l"] >= b[k + q]["l"]:
                    piv = False
            if not piv:
                break
        if piv and (k - frm + 1) >= SWING_MIN:
            return k - frm + 1
    return max(SWING_MIN, min(SWING_CAP, len(b) - frm - 1))


def judge(b, i, side):
    """Bar i is the candidate REACTION. Return the first gate it fails, or None."""
    r = b[i]
    up = r["c"] > r["o"]
    if side > 0 and not up:
        return "reaction not UP"
    if side < 0 and up:
        return "reaction not DOWN"

    # the run behind it
    run = 0
    for k in range(1, SETUP_MAX + 1):
        j = i - k
        if j < 0:
            break
        ours = (b[j]["c"] < b[j]["o"]) if side > 0 else (b[j]["c"] > b[j]["o"])
        if not ours:
            break
        run += 1
    if run < SETUP_MIN:
        return "DIR — only %d bar(s) run into the reaction, needs %d" % (run, SETUP_MIN)

    c0 = i - 1
    setup = [b[c0 - q] for q in range(run)]
    frm = c0 - run + 1
    span = swing_len(b, frm, side)
    look = b[max(0, frm - span):frm]
    if len(look) < 3:
        return "not enough history for the yardstick"
    vmax = max(x["v"] for x in look)
    vavg = sum(x["v"] for x in look) / len(look)
    vsetup = sum(x["v"] for x in setup) / len(setup)
    loudest = max(x["v"] for x in setup) / vmax

    if loudest < BIG_PCT:
        return ("NOT LOUD — loudest setup bar is %.2fx the %d-bar swing max (needs %.2f)"
                % (loudest, span, BIG_PCT))
    if vsetup < BIG_AVG * vavg:
        return ("NOT LOUD — setup averages %.2fx the swing average (needs %.2f)"
                % (vsetup / vavg, BIG_AVG))

    # LAW 13 — the fake break
    lvl = min(x["l"] for x in b[max(0, frm - SWEEP_LOOK):frm]) if side > 0 \
        else max(x["h"] for x in b[max(0, frm - SWEEP_LOOK):frm])
    ext = min(x["l"] for x in setup) if side > 0 else max(x["h"] for x in setup)
    if side > 0:
        if ext >= lvl:
            return "FAKE BREAK — never swept the %d-bar low %.2f (setup low %.2f)" % (
                SWEEP_LOOK, lvl, ext)
        if r["c"] <= lvl:
            return "FAKE BREAK — reaction closed %.2f, still below the swept low %.2f" % (
                r["c"], lvl)
    else:
        if ext <= lvl:
            return "FAKE BREAK — never swept the %d-bar high %.2f (setup high %.2f)" % (
                SWEEP_LOOK, lvl, ext)
        if r["c"] >= lvl:
            return "FAKE BREAK — reaction closed %.2f, still above the swept high %.2f" % (
                r["c"], lvl)

    rng = r["h"] - r["l"]
    if rng <= 0 or abs(r["c"] - r["o"]) < BODY_FRAC * rng:
        return "BODY — reaction body is only %.0f%% of its range (needs %.0f%%)" % (
            100 * abs(r["c"] - r["o"]) / rng if rng else 0, 100 * BODY_FRAC)
    if r["v"] > LOW_VOL_PCT * vsetup:
        return "NOT QUIET — reaction %.2fx the setup's volume (needs <= %.2f)" % (
            r["v"] / vsetup, LOW_VOL_PCT)
    return None


def main():
    b = load()
    frm, to = sys.argv[1], sys.argv[2]
    print("Every bar in the window judged as a candidate REACTION (v1.20 gates).")
    print("A bar has to pass DIR, then LOUD, then the FAKE BREAK, then body and quiet.\n")
    print("%-6s %-5s %s" % ("time", "side", "first gate it fails"))
    print("-" * 96)
    for i, x in enumerate(b):
        if not (frm <= x["t"] <= to):
            continue
        for side, name in ((1, "BUY"), (-1, "SELL")):
            why = judge(b, i, side)
            if why and why.startswith("reaction not"):
                continue
            print("%-6s %-5s %s" % (x["t"][11:16], name, why or ">>> WOULD FIRE <<<"))


if __name__ == "__main__":
    main()
