"""cause_settings_eval.py - every loss-filter / cause setting of Turtle TV UHV (uhv_filters.py) switched on alone, on the 97.7% setting, in
the engine itself (so freed slots and one-position blocking are real). For each: trades left, losses left, win rate, how many of the 172
original losses it removes, and the share of trading days with NO loss (Zee 2026-11-06: "we're aggressively trying to achieve a 100% winrate
on most days"). Train (Mar-Jun) / test (Jul-Nov) loss rates show whether it holds on both halves. Python tick replay = hypothesis.
Run: py research/loss_study/cause_settings_eval.py [base_setting.json]"""
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import uhv_engine as U  # noqa: E402

NY = ZoneInfo("America/New_York")
SPLIT = 1782864000
base_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json")
B = json.load(open(base_file, encoding="utf-8"))["inputs"]


def nyday(ts):
    d = dt.datetime.fromtimestamp(ts, NY)
    return (d + dt.timedelta(hours=7)).strftime("%Y-%m-%d")      # the FX day rolls at 17:00 NY


def stats(inp):
    tr, _, _ = U.simulate(inp)
    r = tr[tr[:, 10] == 0]
    loss = r[:, 6] < 0
    days = {}
    for x, lz in zip(r, loss):
        k = nyday(x[1]); days[k] = days.get(k, False) or bool(lz)
    tr_m, te_m = r[:, 1] < SPLIT, r[:, 1] >= SPLIT
    keys = {(int(x[0]), round(x[1])) for x in r[loss]}
    return {"n": len(r), "L": int(loss.sum()), "wr": 100 * (1 - loss.mean()) if len(r) else 0, "net": float(r[:, 6].sum()),
            "days": len(days), "clean_days": 100 * sum(1 for v in days.values() if not v) / max(len(days), 1),
            "lr_tr": 100 * loss[tr_m].mean() if tr_m.any() else 0, "lr_te": 100 * loss[te_m].mean() if te_m.any() else 0, "keys": keys}


if __name__ == "__main__":
    base = stats(B)
    print(f"BASE {os.path.basename(base_file)}: {base['n']} trades, {base['L']} losses, WR {base['wr']:.2f}%, loss-free days {base['clean_days']:.0f}% of {base['days']}, "
          f"loss rate train {base['lr_tr']:.2f}% / test {base['lr_te']:.2f}%, net {base['net']:,.0f}")
    TESTS = [
        ("rollover NY 16:45-17:45", {"InpUhvNoClose": "1"}),
        ("breakout spread >= 1.0", {"InpUhvMaxTrigSpread": "1.0"}),
        ("S/R just ahead 0.5 pip", {"InpUhvSRAhead": "0.5"}), ("S/R just ahead 1.0 pip", {"InpUhvSRAhead": "1.0"}),
        ("round figure 1.0 pip (100)", {"InpUhvBigFig": "1.0"}), ("round figure 1.0 pip (50)", {"InpUhvBigFig": "1.0", "InpUhvFigStep": "50"}),
        ("S/R 3 pips (60 bars)", {"InpUhvSRPips": "3"}),
        ("min humps 2", {"InpUhvMinHumps": "2"}), ("min humps 3", {"InpUhvMinHumps": "3"}),
        ("counter-move 6 ATR / 90", {"InpUhvCounterAtr": "6"}), ("structure HH+HL", {"InpUhvStruct": "1"}),
        ("Friday after 13 NY", {"InpUhvFriCutNY": "13"}), ("Friday after 15 NY", {"InpUhvFriCutNY": "15"}),
        ("run 8 pips / 30", {"InpUhvRunPips": "8"}), ("run 6 pips / 30", {"InpUhvRunPips": "6"}),
        ("loud breakout 0.9", {"InpUhvLoudBrk": "0.9"}), ("loud breakout 0.8", {"InpUhvLoudBrk": "0.8"}), ("max humps 6", {"InpUhvMaxHumps": "6"}),
        ("dead tape < 20", {"InpUhvMinTicks": "20"}), ("dead tape < 30", {"InpUhvMinTicks": "30"}), ("Sunday open 60 min", {"InpUhvSunOpenMins": "60"}),
        ("US data minutes", {"InpUhvNewsNY": "1"}), ("US data, 5 min before", {"InpUhvNewsNY": "1", "InpUhvNewsMins": "5"}),
        ("spike 3 ATR / 15", {"InpUhvSpikeAtr": "3"}), ("spike 4 ATR / 15", {"InpUhvSpikeAtr": "4"}), ("holidays", {"InpUhvHoliday": "1"}),
        ("ATR < 1.0 pip", {"InpUhvMinAtrPips": "1.0"}), ("range 10 bars < 2 ATR", {"InpUhvRangeAtr": "2"}),
        ("gap through level 0.6", {"InpUhvMaxGapPips": "0.6"}), ("gap through level 0.3", {"InpUhvMaxGapPips": "0.3"}),
    ]
    print(f"{'setting (on alone)':30s} {'trades':>6s} {'losses':>6s} {'WR':>7s} {'of 172 out':>10s} {'clean days':>10s} {'loss% tr/te':>13s} {'net':>9s}")
    for name, x in TESTS:
        s = stats(dict(B, **x))
        gone = len(base["keys"] - s["keys"])
        print(f"{name:30s} {s['n']:6d} {s['L']:6d} {s['wr']:6.2f}% {gone:10d} {s['clean_days']:9.0f}% {s['lr_tr']:6.2f}/{s['lr_te']:5.2f} {s['net']:9,.0f}", flush=True)
