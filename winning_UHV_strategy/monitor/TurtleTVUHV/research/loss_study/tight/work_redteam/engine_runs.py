"""engine_runs.py (work_judge) - engine (uhv_engine.simulate) confirmation of the cures that an EXISTING Turtle TV input implements, on top
of the tight (2026-11-06 09-00-00), zee100 (2026-11-06 07-33-17) and secure (2026-11-06 09-10-00) settings. Python tick replay =
HYPOTHESIS, NOT PROMOTED.

  * baselines first (tight 714 / 4 / +$376, zee100 308 / 0 / +$444.06, secure ~2238 / 30 / -$2,976 expected)
  * receipt that uhv_filters.skip() loss filters are INERT under InpUhvRiskMgr 2 (skip() runs only when `not sec`, and every trade that
    survives RiskMgr 2 has sec = True): InpUhvRunPips 8.1 / InpUhvRunBars 60 (the exact twin of rule_with_move60) and InpUhvNewsNY 1
  * InpUhvMaxTrigSpread 0.5 (= rule_wide_spread), InpUhvSafeRangeAtr 9.2 + InpUhvSafeRangeBars 120 (= rule_range_bound120), and both
Split at 2026-07-01 00:00 UTC on FILL time rows[:,1] (decision time + the 0.3 s latency). rows[:,10] == 0 = real trades, win = rows[:,6] > 0.
Run: cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/tight/work_judge/engine_runs.py"""
import contextlib
import io
import json
import os
import sys
import time

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:/Users/zeesh/turtle/monitor/TurtleTVUHV"
sys.path.insert(0, ROOT)
sys.path.insert(0, r"C:/Users/zeesh/turtle/monitor")
import numpy as np  # noqa: E402

import uhv_engine as U  # noqa: E402

SPLIT = 1782864000
SAVED = os.path.join(ROOT, "settings", "saved")


def inputs(fn):
    return json.load(open(os.path.join(SAVED, fn), encoding="utf-8"))["inputs"]


BASE = {"tight": inputs("2026-11-06 09-00-00.json"), "zee100": inputs("2026-11-06 07-33-17.json"), "secure": inputs("2026-11-06 09-10-00.json")}


def stats(rows):
    R = rows[rows[:, 10] == 0]
    out = {}
    for part, m in (("all", np.ones(len(R), bool)), ("train", R[:, 1] < SPLIT), ("test", R[:, 1] >= SPLIT)):
        p = R[m, 6]
        n, L = int(len(p)), int((p <= 0).sum())
        out[part] = {"n": n, "L": L, "wr": round(100 * (1 - L / max(n, 1)), 2), "net": round(float(p.sum()), 2)}
    return out, R


def fmt(s):
    return "  ".join(f"{h} {s[h]['n']}/{s[h]['L']}L {s[h]['wr']}% {s[h]['net']:+.2f}" for h in ("all", "train", "test"))


RES = {}


def run(stack, label, **chg):
    x = dict(BASE[stack])
    x.update({k: str(v) for k, v in chg.items()})
    t0 = time.time()
    rows, _, cnt = U.simulate(x)
    s, R = stats(rows)
    RES[f"{stack} | {label}"] = {"changes": chg, "stats": s, "losses": [[float(r[1]), int(r[0]), round(float(r[6]), 2)] for r in R if r[6] <= 0]}
    print(f"{stack:6s} | {label:44s} | {fmt(s)}   ({time.time() - t0:.1f}s)", flush=True)
    return s, R


def main():
    print("ENGINE runs (uhv_engine.simulate). Python tick replay = HYPOTHESIS, NOT PROMOTED. Format: trades/losses WR net at 1 lot.", flush=True)
    base_R = {}
    for st in ("tight", "zee100", "secure"):
        _, base_R[st] = run(st, "AS SAVED (baseline)")
    print("-- receipt: loss filters under InpUhvRiskMgr 2 (expected IDENTICAL to the baseline)", flush=True)
    for st in ("zee100", "tight"):
        s, R = run(st, "+ InpUhvRunPips 8.1 / RunBars 60 (with_move60)", InpUhvRunPips=8.1, InpUhvRunBars=60)
        print(f"         identical rows to baseline: {R.shape == base_R[st].shape and bool(np.allclose(R[:, :7], base_R[st][:, :7]))}", flush=True)
        s, R = run(st, "+ InpUhvNewsNY 1", InpUhvNewsNY=1)
        print(f"         identical rows to baseline: {R.shape == base_R[st].shape and bool(np.allclose(R[:, :7], base_R[st][:, :7]))}", flush=True)
    print("-- the cures an existing input implements", flush=True)
    for st in ("tight", "zee100", "secure"):
        run(st, "+ InpUhvMaxTrigSpread 0.5 (wide_spread)", InpUhvMaxTrigSpread=0.5)
        run(st, "+ SafeRangeAtr 9.2 / SafeRangeBars 120 (range120)", InpUhvSafeRangeAtr=9.2, InpUhvSafeRangeBars=120)
        run(st, "+ both", InpUhvMaxTrigSpread=0.5, InpUhvSafeRangeAtr=9.2, InpUhvSafeRangeBars=120)
    json.dump(RES, open(os.path.join(HERE, "engine_runs.json"), "w", encoding="utf-8"), indent=1)
    from doctrine import python_says
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print("\nDOCTRINE (monitor/doctrine.py), break-even ~99.3% (avg win ~$1.44, typical stop ~-$213):")
        for k in ("zee100 | AS SAVED (baseline)", "tight | AS SAVED (baseline)", "secure | AS SAVED (baseline)",
                  "tight | + InpUhvMaxTrigSpread 0.5 (wide_spread)", "secure | + InpUhvMaxTrigSpread 0.5 (wide_spread)",
                  "secure | + SafeRangeAtr 9.2 / SafeRangeBars 120 (range120)"):
            python_says(k, win_pct=RES[k]["stats"]["all"]["wr"], need_pct=99.3)
    print(buf.getvalue(), flush=True)


if __name__ == "__main__":
    main()
