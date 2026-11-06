"""exitlab.py - the Exit Lab of the Turtle TV Tester (Zee 2026-10-20: "create an Exit Lab tab where we can test out all the different kinds of
exits possible. including trailing, partial close etc. the exit lab should be really really intelligently made").

The ENTRIES stay the EA's own (the settings on screen); only the exit changes. Every exit runs inside the same engine as the Turtle TV Tester
(sim_full.run_full, the lab's rules switched on by the vector E), so a trade held longer still blocks the next setup, stand-asides and
cool-downs still act, and with the lab off the engine is untouched (exitlab_regress.py).

Two kinds of rows:
  "In the EA"  - exits the EA already has (exit modes, stop size, day-close loss cut): MT5's Strategy Tester can check them now.
  "Lab only"   - new exits (targets in R / ATR / $, partials, breakeven, locks, trails, close-based and time exits): hypotheses until
                 they are built into the EA ("Make it an EA setting") and MT5 confirms them.
Python numbers are hypotheses (CLAUDE.md); MT5 decides."""
import math
import os
import threading
import time
from datetime import datetime, timezone

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import numpy as np  # noqa: E402

import optimizer  # noqa: E402
import sim  # noqa: E402
import sim_full  # noqa: E402

# ---------------------------------------------------------------- the building blocks (the UI's form, the search's grids)
TGT = [(0, "the EA's own: the next EMA beyond the entry"), (1, "none: the stop, a trail, time or a signal decides"),
       (2, "R multiple (x the stop distance)"), (3, "ATR multiple"), (4, "$ distance")]
FB = [(0, "close back across the fast EMA (the EA)"), (1, "close back across the slow EMA"), (2, "nothing: other rules decide")]
CX = [(0, "off"), (1, "close back across the fast EMA"), (2, "close back across the slow EMA"), (3, "fast EMA crosses the slow against the trade"),
      (4, "an opposite signal candle (pin / hammer / marubozu against)"), (5, "an engulfing candle against"), (6, "N candles in a row closing against")]
CXW = [(0, "always"), (1, "only when the trade is in profit"), (2, "only when the trade is in loss")]
TR = [(0, "off"), (1, "$ distance from the best price"), (2, "ATR x k from the best price (chandelier)"), (3, "keep k% of the best open profit"),
      (4, "the fast EMA (at each close)"), (5, "the slow EMA (at each close)"), (6, "the previous candle's low / high"),
      (7, "the lowest low / highest high of N candles"), (8, "the last swing low / high")]

GROUPS = [
    ("Target", "Where the trade takes its profit. 'R' = the distance from the entry to the first stop.", [
        {"f": "tgt", "t": "sel", "opts": TGT, "d": 0, "label": "Target"},
        {"f": "tgt_k", "t": "num", "d": 2.0, "step": 0.25, "min": 0.25, "label": "k (R / ATR / $)", "show": "tgt>=2"}]),
    ("When no EMA lies beyond the entry", "Exit mode 1's fallback: the EA has no EMA to aim for and waits for a close back across the fast EMA.", [
        {"f": "fb", "t": "sel", "opts": FB, "d": 0, "label": "Then"},
        {"f": "fb_buf", "t": "num", "d": 0.0, "step": 0.05, "min": 0, "label": "the close must clear it by (x ATR)", "show": "fb<=1"},
        {"f": "fb_n", "t": "int", "d": 1, "step": 1, "min": 1, "label": "closes in a row", "show": "fb<=1"}]),
    ("Close-based exit", "For every trade, judged at each 15-minute close (never the entry candle's own close).", [
        {"f": "cx", "t": "sel", "opts": CX, "d": 0, "label": "Exit on"},
        {"f": "cx_buf", "t": "num", "d": 0.0, "step": 0.05, "min": 0, "label": "buffer (x ATR)", "show": "cx>=1&&cx<=3"},
        {"f": "cx_n", "t": "int", "d": 1, "step": 1, "min": 1, "label": "candles in a row", "show": "cx>=1"},
        {"f": "cx_when", "t": "sel", "opts": CXW, "d": 0, "label": "when", "show": "cx>=1"},
        {"f": "cx_after", "t": "int", "d": 0, "step": 1, "min": 0, "label": "ignore the first N candles", "show": "cx>=1"}]),
    ("Partial closes", "Close part of the trade at a profit; the rest runs on the other rules.", [
        {"f": "p1_r", "t": "num", "d": 0.0, "step": 0.25, "min": 0, "label": "first part at +R (0 = off)"},
        {"f": "p1_frac", "t": "num", "d": 0.5, "step": 0.05, "min": 0.05, "max": 1, "label": "share closed", "show": "p1_r>0"},
        {"f": "p1_be", "t": "bool", "d": 0, "label": "then the stop to breakeven", "show": "p1_r>0"},
        {"f": "p2_r", "t": "num", "d": 0.0, "step": 0.25, "min": 0, "label": "second part at +R (0 = off)", "show": "p1_r>0"},
        {"f": "p2_frac", "t": "num", "d": 0.25, "step": 0.05, "min": 0.05, "max": 1, "label": "share closed", "show": "p2_r>0"}]),
    ("Breakeven and profit lock", "Move the stop once the trade has gone far enough your way.", [
        {"f": "be_r", "t": "num", "d": 0.0, "step": 0.25, "min": 0, "label": "breakeven at +R (0 = off)"},
        {"f": "be_off", "t": "num", "d": 0.0, "step": 0.05, "min": -0.5, "label": "stop at entry + R", "show": "be_r>0"},
        {"f": "lock_r", "t": "num", "d": 0.0, "step": 0.25, "min": 0, "label": "lock ladder every R (0 = off)"}]),
    ("Trailing stop", "The stop follows the price; it only ever moves your way.", [
        {"f": "tr", "t": "sel", "opts": TR, "d": 0, "label": "Trail"},
        {"f": "tr_k", "t": "num", "d": 2.0, "step": 0.25, "min": 0.25, "label": "k ($ / x ATR / % / N candles)", "show": "tr==1||tr==2||tr==3||tr==7"},
        {"f": "tr_act", "t": "num", "d": 0.0, "step": 0.25, "min": 0, "label": "starts at +R", "show": "tr>=1"},
        {"f": "tr_buf", "t": "num", "d": 0.0, "step": 0.25, "min": 0, "label": "buffer ($)", "show": "tr>=4"}]),
    ("Loss cutters (v1.31)", "Cut what a losing trade can cost before it reaches the stop. R = the distance from the entry to the first stop.", [
        {"f": "lcap", "t": "num", "d": 0.0, "step": 0.5, "min": 0, "label": "the stop never further than $ from the entry (0 = off)"},
        {"f": "lp_r", "t": "num", "d": 0.0, "step": 0.05, "min": 0, "label": "cut part of the trade when it is R in loss (0 = off)"},
        {"f": "lp_frac", "t": "num", "d": 0.5, "step": 0.05, "min": 0.05, "max": 1, "label": "share cut", "show": "lp_r>0"},
        {"f": "dc_bars", "t": "int", "d": 0, "step": 1, "min": 0, "label": "tighten the stop after N candles (0 = off)"},
        {"f": "dc_r", "t": "num", "d": -0.5, "step": 0.05, "min": -1, "label": "... to the entry + R (negative = in loss)", "show": "dc_bars>0"}]),
    ("Time and other", "", [
        {"f": "max_bars", "t": "int", "d": 0, "step": 1, "min": 0, "label": "close after N candles (0 = off)"},
        {"f": "stale_bars", "t": "int", "d": 0, "step": 1, "min": 0, "label": "no progress after N candles (0 = off)"},
        {"f": "stale_r", "t": "num", "d": 0.5, "step": 0.25, "label": "... means less than +R", "show": "stale_bars>0"},
        {"f": "adx_exit", "t": "num", "d": 0.0, "step": 1, "min": 0, "label": "close when ADX falls below (0 = off)"},
        {"f": "fri_hour", "t": "int", "d": 0, "step": 1, "min": 0, "max": 23, "label": "Friday close at server hour (0 = off)"}]),
    ("Realism", "", [
        {"f": "pess", "t": "bool", "d": 1, "label": "tick trails: the minute's adverse range counts (as MT5 trails tick by tick)"}]),
]
FIELDS = {x["f"]: x for g in GROUPS for x in g[2]}
DEFAULT = {f: x["d"] for f, x in FIELDS.items()}
WHY = {1: "stop", 2: "EMA target", 3: "close back across the EMA", 4: "day-close loss cut", 5: "take profit", 6: "trailing stop", 7: "breakeven stop",
       8: "time exit", 9: "lab target", 11: "partial", 12: "close-based exit", 13: "no progress", 14: "ADX faded", 15: "Friday close", 16: "decay stop",
       17: "loss cut"}
# the search's grids (lo, hi, step) - the numeric fields of each building block
GRID = {"tgt_k": {2: (0.5, 6, 0.25), 3: (0.5, 6, 0.25), 4: (2, 40, 1)}, "fb_buf": (0, 1.5, 0.05), "fb_n": (1, 4, 1), "cx_buf": (0, 1, 0.05),
        "cx_n": (1, 5, 1), "cx_after": (0, 8, 1), "p1_r": (0.25, 3, 0.25), "p1_frac": (0.1, 0.9, 0.1), "p2_r": (0.5, 4, 0.25), "p2_frac": (0.1, 0.9, 0.1),
        "be_r": (0.25, 3, 0.25), "be_off": (-0.25, 0.5, 0.05), "lock_r": (0.25, 3, 0.25),
        "tr_k": {1: (1, 30, 1), 2: (0.5, 6, 0.25), 3: (10, 90, 5), 7: (2, 30, 1)}, "tr_act": (0, 3, 0.25), "tr_buf": (0, 3, 0.25),
        "max_bars": (1, 96, 1), "stale_bars": (1, 32, 1), "stale_r": (-0.5, 1.5, 0.25), "adx_exit": (10, 40, 1), "fri_hour": (12, 23, 1),
        "lcap": (1, 60, 0.5), "lp_r": (0.1, 0.95, 0.05), "lp_frac": (0.1, 1, 0.1), "dc_bars": (1, 64, 1), "dc_r": (-0.95, 0.5, 0.05)}


def clean(lab):
    """only what differs from 'off' (keeps the recipe short and its key stable)"""
    out = {}
    for f, v in (lab or {}).items():
        if f not in FIELDS:
            continue
        v = float(v)
        if f == "pess":
            if v < 0.5:
                out[f] = 0.0
            continue
        if f in ("tgt_k",) and float(lab.get("tgt", 0)) < 2:
            continue
        if f in ("fb_buf", "fb_n") and (float(lab.get("fb", 0)) > 1 or float(lab.get("tgt", 0)) > 0):
            continue
        if f in ("cx_buf", "cx_n", "cx_when", "cx_after") and float(lab.get("cx", 0)) < 1:
            continue
        if f in ("p1_frac", "p1_be", "p2_r", "p2_frac") and float(lab.get("p1_r", 0)) <= 0:
            continue
        if f == "p2_frac" and float(lab.get("p2_r", 0)) <= 0:
            continue
        if f == "be_off" and float(lab.get("be_r", 0)) <= 0:
            continue
        if f in ("tr_k", "tr_act", "tr_buf") and float(lab.get("tr", 0)) < 1:
            continue
        if f == "stale_r" and float(lab.get("stale_bars", 0)) <= 0:
            continue
        if f == "lp_frac" and float(lab.get("lp_r", 0)) <= 0:
            continue
        if f == "dc_r" and float(lab.get("dc_bars", 0)) <= 0:
            continue
        if f in ("fb_n", "cx_n") and v <= 1:
            continue
        if v != 0 or f in ("p1_frac", "p2_frac", "lp_frac", "dc_r"):        # (their parent is on: a 0 here is a real value, not 'off')
            out[f] = round(v, 4)
    if "p1_r" in out:
        out.setdefault("p1_frac", float(lab.get("p1_frac", 0.5)))
    if "p2_r" in out:
        out.setdefault("p2_frac", float(lab.get("p2_frac", 0.25)))
    if "tr" in out:
        out.setdefault("tr_k", float(lab.get("tr_k", 2.0)))
    if "lp_r" in out:
        out.setdefault("lp_frac", float(lab.get("lp_frac", 0.5)))
    if "dc_bars" in out:
        out.setdefault("dc_r", float(lab.get("dc_r", -0.5)))
    out["pess"] = out.get("pess", 1.0)
    return out


def describe(lab):
    """a recipe in plain English"""
    L = dict(DEFAULT, **(lab or {}))
    g = lambda f: float(L.get(f, 0))  # noqa: E731
    parts = []
    t = int(g("tgt"))
    parts.append({0: "EA target (next EMA)", 1: "no target", 2: f"target {g('tgt_k'):g}R", 3: f"target {g('tgt_k'):g} ATR", 4: f"target ${g('tgt_k'):g}"}[t])
    if t == 0 and (g("fb") or g("fb_buf") or g("fb_n") > 1):
        fb = int(g("fb"))
        if fb == 2:
            parts.append("no fallback")
        else:
            parts.append(f"fallback: close across the {'fast' if fb == 0 else 'slow'} EMA" + (f" by {g('fb_buf'):g} ATR" if g("fb_buf") else "") +
                         (f", {int(g('fb_n'))} closes" if g("fb_n") > 1 else ""))
    if g("cx"):
        c = int(g("cx"))
        s = {1: "close across the fast EMA", 2: "close across the slow EMA", 3: "EMA cross", 4: "opposite signal candle", 5: "engulfing against",
             6: f"{int(max(1, g('cx_n')))} candles against"}[c]
        if c in (1, 2, 3) and g("cx_buf"):
            s += f" by {g('cx_buf'):g} ATR"
        if c != 6 and g("cx_n") > 1:
            s += f", {int(g('cx_n'))} in a row"
        s += {0: "", 1: " (in profit)", 2: " (in loss)"}[int(g("cx_when"))]
        if g("cx_after"):
            s += f" after {int(g('cx_after'))} candles"
        parts.append("exit on " + s)
    if g("p1_r"):
        s = f"{round(100 * g('p1_frac'))}% off at {g('p1_r'):g}R"
        if g("p1_be"):
            s += " + breakeven"
        if g("p2_r"):
            s += f", {round(100 * g('p2_frac'))}% at {g('p2_r'):g}R"
        parts.append(s)
    if g("be_r"):
        parts.append(f"breakeven at {g('be_r'):g}R" + (f" (+{g('be_off'):g}R)" if g("be_off") else ""))
    if g("lock_r"):
        parts.append(f"lock ladder every {g('lock_r'):g}R")
    if g("tr"):
        tm = int(g("tr"))
        s = {1: f"trail ${g('tr_k'):g}", 2: f"trail {g('tr_k'):g} ATR", 3: f"keep {g('tr_k'):g}% of the best profit", 4: "trail the fast EMA",
             5: "trail the slow EMA", 6: "trail the previous candle", 7: f"trail the {int(g('tr_k'))}-candle low/high", 8: "trail the last swing"}[tm]
        if g("tr_act"):
            s += f" from +{g('tr_act'):g}R"
        if tm >= 4 and g("tr_buf"):
            s += f" (${g('tr_buf'):g} buffer)"
        parts.append(s)
    if g("lcap"):
        parts.append(f"stop never beyond ${g('lcap'):g} from the entry")
    if g("lp_r"):
        parts.append(f"cut {round(100 * g('lp_frac'))}% at -{g('lp_r'):g}R")
    if g("dc_bars"):
        parts.append(f"after {int(g('dc_bars'))} candles the stop to {g('dc_r'):+g}R")
    if g("max_bars"):
        parts.append(f"out after {int(g('max_bars'))} candles")
    if g("stale_bars"):
        parts.append(f"out if not +{g('stale_r'):g}R after {int(g('stale_bars'))} candles")
    if g("adx_exit"):
        parts.append(f"out when ADX < {g('adx_exit'):g}")
    if g("fri_hour"):
        parts.append(f"Friday close at {int(g('fri_hour'))}:00")
    return " · ".join(parts)


# ---------------------------------------------------------------- running one exit
def window_of(ds, inputs):
    o = optimizer.Optimizer(inputs, ds=ds)
    if o.window:
        return o.window, list(o.labels)
    return (0, optimizer.TRAIN_END, optimizer.TRAIN_END, 1 << 40), list(o.labels)


def _part(r):
    n = len(r)
    if n == 0:
        return {"n": 0, "net": 0.0, "wr": 0.0, "pf": 0.0, "dd": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "worst": 0.0, "streak": 0}
    r = r[np.argsort(r[:, 4])]
    p = r[:, 6]
    gw, gl = p[p > 0].sum(), -p[p <= 0].sum()
    eq = np.cumsum(p)
    dd = float(np.max(np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:] - eq))
    st = best = 0
    for v in p:
        st = st + 1 if v <= 0 else 0
        best = max(best, st)
    w = p[p > 0]
    lo = p[p <= 0]
    return {"n": n, "net": round(float(p.sum())), "wr": round(float(100 * (p > 0).mean()), 1), "pf": round(float(gw / gl), 2) if gl > 0 else 99.0,
            "dd": round(dd), "avg_win": round(float(w.mean())) if len(w) else 0, "avg_loss": round(float(lo.mean())) if len(lo) else 0,
            "worst": round(float(p.min())), "streak": best}


def run(inputs, ds, lab=None, sets=None, worst=False, lego=None):
    """one exit over the data -> (trades array, real trades, still open at the end: {n, days}); lego = Strategy Lego pieces"""
    inp = dict(inputs, **(sets or {}))
    tr, _, st = sim.simulate(inp, ds=ds, lab=clean(lab) if lab else None, lego=lego or None, worst_case=1.0 if worst else 0.0)
    end = float(sim.data(ds)["t1"][-1])
    oe = {"n": int(st.get("open_at_end", 0)), "days": round((end - st.get("open_since", 0)) / 86400.0, 1) if st.get("open_at_end") else 0.0,
          "since": int(st.get("open_since", 0))}
    return tr, tr[tr[:, 10] == 0], oe


def stats(real, window, base_keys=None, base_pnl=None, open_end=None):
    a0, a1, b0, b1 = window
    tr_, te_ = real[(real[:, 1] >= a0) & (real[:, 1] < a1)], real[(real[:, 1] >= b0) & (real[:, 1] < b1)]
    s = {"train": _part(tr_), "test": _part(te_), "all": _part(real)}
    s["total"] = s["train"]["net"] + s["test"]["net"]
    why = {}
    for x in real:
        d = why.setdefault(WHY.get(int(x[13]), str(int(x[13]))), [0, 0, 0.0])
        d[0] += 1; d[1] += int(x[6] > 0); d[2] += float(x[6])
    s["why"] = {k: {"n": v[0], "wins": v[1], "net": round(v[2])} for k, v in sorted(why.items(), key=lambda kv: -kv[1][0])}
    s["partials"] = int((real[:, 19] > 0).sum()) if real.shape[1] > 19 else 0
    s["longest_h"] = round(float((real[:, 4] - real[:, 1]).max()) / 3600.0, 1) if len(real) else 0.0
    s["open_end"] = open_end or {"n": 0, "days": 0.0, "since": 0}
    # a trade nothing closes (it blocks every later setup): open at the end for far longer than any trade that did close
    s["stuck"] = bool(s["open_end"]["n"] and s["open_end"]["days"] > max(14.0, 3.0 * s["longest_h"] / 24.0))
    s["sides"] = {}
    for sd, nm in ((1, "BUY"), (-1, "SELL")):
        r = real[real[:, 0] == sd]
        a, b = r[(r[:, 1] >= a0) & (r[:, 1] < a1)], r[(r[:, 1] >= b0) & (r[:, 1] < b1)]
        s["sides"][nm] = {"n": int(len(r)), "net": round(float(r[:, 6].sum())), "train": round(float(a[:, 6].sum())), "test": round(float(b[:, 6].sum())),
                          "wr": round(float(100 * (r[:, 6] > 0).mean()), 1) if len(r) else 0.0}
    if base_keys is not None:
        keys = {(int(x[1]), int(x[0])): float(x[6]) for x in real}
        s["new"] = len(set(keys) - base_keys)
        s["gone"] = len(base_keys - set(keys))
        s["changed"] = sum(1 for k, v in keys.items() if k in base_pnl and abs(v - base_pnl[k]) > 0.5)
    years = {}
    for x in real:
        y = datetime.fromtimestamp(x[1], timezone.utc).year
        d = years.setdefault(y, [0, 0, 0.0])
        d[0] += 1; d[1] += int(x[6] > 0); d[2] += float(x[6])
    s["years"] = {str(y): {"n": v[0], "wr": round(100 * v[1] / v[0], 1) if v[0] else 0, "net": round(v[2])} for y, v in sorted(years.items())}
    return s


def trade_list(real):
    return [[int(x[0]), int(x[1]), round(float(x[2]), 5), round(float(x[3]), 5), int(x[4]), round(float(x[5]), 5), round(float(x[6]), 2),   # TurtleTVUHV: EUR/USD prices
             WHY.get(int(x[13]), str(int(x[13]))), round(float(x[15]), 2), round(float(x[16]), 2), round(float(x[17]), 2), int(x[19])] for x in real]


# ---------------------------------------------------------------- where the exits leave money (the EA's own exit, before any test)
def diagnose(inputs, ds):
    window, labels = window_of(ds, inputs)
    tr, real, oe = run(inputs, ds)
    D = sim.data(ds)
    lots = float(inputs.get("InpLots", 1) or 1)
    R = np.maximum(real[:, 17], 0.05)
    mfe, mae, pnl = real[:, 15], real[:, 16], real[:, 6]
    lot = np.where(real[:, 18] > 0, real[:, 18], lots)
    res_r = pnl / (R * lot * 100.0)
    mfe_r = mfe / R
    win = pnl > 0
    # after the exit: how far did price go on in the trade's direction (and against it) in the next 4 hours of 1-minute candles,
    # starting the minute AFTER the exit (the exit candle's own earlier high / low happened before the exit)
    t1 = D["t1"]
    after_fav, after_adv = np.zeros(len(real)), np.zeros(len(real))
    for n, x in enumerate(real):
        a = int(np.searchsorted(t1, int(x[4]) - int(x[4]) % 60, side="right"))
        b = min(len(t1), a + 240)
        if a >= b:
            continue
        hi, lo = D["h1"][a:b].max(), D["l1"][a:b].min()
        after_fav[n] = (hi - x[5]) if x[0] > 0 else (x[5] - lo)
        after_adv[n] = (x[5] - lo) if x[0] > 0 else (hi - x[5])
    is_stop = real[:, 13] == 1
    # which came FIRST after the exit: 1R further the trade's way, or 1R against? (both in one minute counts as against: the cautious reading)
    first = np.zeros(len(real), dtype=np.int64)                              # 1 = +1R first, -1 = -1R first, 0 = neither within 4 hours
    for n, x in enumerate(real):
        a = int(np.searchsorted(t1, int(x[4]) - int(x[4]) % 60, side="right"))
        b = min(len(t1), a + 240)
        if a >= b:
            continue
        hi, lo, ex, r_ = D["h1"][a:b], D["l1"][a:b], x[5], R[n]
        fav = (hi >= ex + r_) if x[0] > 0 else (lo <= ex - r_)
        adv = (lo <= ex - r_) if x[0] > 0 else (hi >= ex + r_)
        fi = int(np.argmax(fav)) if fav.any() else 1 << 30
        ai = int(np.argmax(adv)) if adv.any() else 1 << 30
        if fi < ai:
            first[n] = 1
        elif ai < 1 << 30:
            first[n] = -1
    early = (first == 1) & ~is_stop                                          # closed by a RULE, then +1R came before -1R: the rule came early
    stop_back = is_stop & (first == 1)                                       # stopped out, then price came back ~to the entry before 1R more against
    early_by = {}
    for n, x in enumerate(real):
        d = early_by.setdefault(WHY.get(int(x[13]), str(int(x[13]))), [0, 0])
        d[0] += 1
        d[1] += int(first[n] == 1)
        d.append(0) if len(d) < 3 else None
        d[2] += int(first[n] == -1)
    reach = {f"{t:g}R": round(float(100 * (mfe_r >= t).mean()), 1) for t in (0.25, 0.5, 1, 1.5, 2, 3, 5)} if len(real) else {}
    lost_after = (~win) & (mfe_r >= 1)
    lost_after_half = (~win) & (mfe_r >= 0.5)
    capture = float(pnl[win].sum() / max(1.0, (mfe[win] * lot[win] * 100.0).sum())) if win.any() else 0.0
    giveback = float(((mfe[win] * lot[win] * 100.0) - pnl[win]).sum()) if win.any() else 0.0
    q = lambda arr, p: round(float(np.percentile(arr, p)), 2) if len(arr) else 0  # noqa: E731
    out = {
        "labels": labels, "ds": ds, "n": int(len(real)), "stats": stats(real, window, open_end=oe),
        "losers_were_1r": {"n": int(lost_after.sum()), "net": round(float(pnl[lost_after].sum()))},
        "losers_were_half_r": {"n": int(lost_after_half.sum()), "net": round(float(pnl[lost_after_half].sum()))},
        "winners": {"n": int(win.sum()), "capture_pct": round(100 * capture, 1), "giveback": round(giveback)},
        "early": {"n": int(early.sum()), "of": int((~is_stop).sum()), "right": int(((first == -1) & ~is_stop).sum())},
        "stop_back": {"n": int(stop_back.sum()), "of": int(is_stop.sum()), "right": int(((first == -1) & is_stop).sum())},
        "saved": {"n": int(((after_adv >= R) & ~win).sum())},
        "early_by": {k: {"n": v[0], "early": v[1], "right": v[2] if len(v) > 2 else 0} for k, v in early_by.items()},
        "reach": reach,
        "mae_winners_r": {"p50": q(mae[win] / R[win], 50), "p75": q(mae[win] / R[win], 75), "p90": q(mae[win] / R[win], 90)},
        "mfe_r": {"p50": q(mfe_r, 50), "p75": q(mfe_r, 75), "p90": q(mfe_r, 90)},
        "risk": {"p50": q(R, 50), "p90": q(R, 90)},
        "scatter": [[round(float(mfe_r[n]), 2), round(float(res_r[n]), 2), int(real[n, 0]), int(real[n, 1])] for n in range(len(real))],
        "trades": trade_list(real),
    }
    return out


# ---------------------------------------------------------------- the catalogue: every kind of exit
def _ea_rows(inputs):
    """exits the EA already has - MT5 can check these now"""
    rows = []
    cur = str(inputs.get("InpExitMode", "1"))
    for m, nm in (("1", "Exit mode 1: the next EMA beyond the entry (v1.25+)"), ("2", "Exit mode 2: out after a close back across the slow EMA"),
                  ("0", "Exit mode 0: the v1.23 exits (TP1 + partial + trail)")):
        if m != cur:
            rows.append({"fam": "EA exit modes", "name": nm, "sets": {"InpExitMode": m}, "trust": "untrusted" if m == "0" else "ok"})
    if str(inputs.get("InpSlMode", "1")) == "1":
        cur_k = float(inputs.get("InpSlAtrMult", 1.6))
        for k in (1.0, 1.2, 1.4, 1.8, 2.0, 2.5, 3.0):
            if abs(k - cur_k) > 1e-9:
                rows.append({"fam": "Stop (EA setting)", "name": f"Stop {k:g} x ATR", "sets": {"InpSlAtrMult": f"{k:g}"}, "axis": k})
    for p in (0, 10, 20):
        rows.append({"fam": "Stop (EA setting)", "name": f"Stop beyond the setup candle + {p / 10:g} $", "sets": {"InpSlMode": "0", "InpSlPips": str(p)}})
    for u in (5, 8, 12):
        rows.append({"fam": "Stop (EA setting)", "name": f"Stop ${u} from the entry", "sets": {"InpSlMode": "2", "InpSlUsd": str(u)}})
    cl = str(inputs.get("InpCloseLossMins", "3"))
    for m in ("0", "3", "15", "60"):
        if m != cl:
            rows.append({"fam": "Day-close loss cut (EA setting)", "name": "No day-close loss cut" if m == "0" else f"Close losing trades {m} min before the daily close",
                         "sets": {"InpCloseLossMins": m}})
    tr = ea_trust()
    same = lambda a, b: abs(float(a) - float(b)) < 1e-9 if str(a).replace(".", "", 1).lstrip("-").isdigit() and str(b).replace(".", "", 1).lstrip("-").isdigit() else str(a) == str(b)  # noqa: E731
    rows = [r for r in rows if not all(same(v, inputs.get(k, "")) for k, v in r["sets"].items())]
    for r in rows:
        r["kind"] = "ea"
        if r.get("trust") != "untrusted":
            v = [tr.get(k) for k in r["sets"]]
            r["trust"] = "untrusted" if "opposite" in v else ("check" if "differ" in v else "ok")
    return rows


def _lab_rows():
    rows = []

    def add(fam, name, lab, axis=None):
        rows.append({"fam": fam, "name": name, "lab": lab, "kind": "lab", "axis": axis})
    for k in (0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3, 4, 5):
        add("Fixed target (R)", f"Target {k:g}R", {"tgt": 2, "tgt_k": k}, k)
    for k in (0.5, 1, 1.5, 2, 3, 4):
        add("Fixed target (ATR)", f"Target {k:g} x ATR", {"tgt": 3, "tgt_k": k}, k)
    for k in (3, 5, 8, 12, 20, 30):
        add("Fixed target ($)", f"Target ${k}", {"tgt": 4, "tgt_k": k}, k)
    for n in (2, 4, 8, 16, 32, 64):
        add("No target: hold N candles", f"No target, out after {n} candles", {"tgt": 1, "max_bars": n}, n)
    add("No target: hold N candles", "No target: the stop or 96 candles (one day)", {"tgt": 1, "max_bars": 96})
    for b in (0.1, 0.25, 0.5, 1.0):
        add("Fallback (no EMA beyond the entry)", f"Fallback close must clear the fast EMA by {b:g} ATR", {"fb_buf": b}, b)
    for n in (2, 3):
        add("Fallback (no EMA beyond the entry)", f"Fallback needs {n} closes in a row", {"fb_n": n}, n)
    add("Fallback (no EMA beyond the entry)", "Fallback on the slow EMA instead", {"fb": 1})
    add("Fallback (no EMA beyond the entry)", "No fallback: the stop or 96 candles (one day)", {"fb": 2, "max_bars": 96})
    add("Fallback (no EMA beyond the entry)", "No fallback: the stop or 16 candles", {"fb": 2, "max_bars": 16})
    for b in (0.0, 0.25, 0.5):
        add("Close-based exits", f"Plus: close back across the fast EMA{f' by {b:g} ATR' if b else ''}", {"cx": 1, "cx_buf": b}, b)
    for b in (0.0, 0.25):
        add("Close-based exits", f"Plus: close back across the slow EMA{f' by {b:g} ATR' if b else ''}", {"cx": 2, "cx_buf": b}, b)
    add("Close-based exits", "Plus: fast EMA crosses the slow against", {"cx": 3})
    add("Close-based exits", "Plus: an opposite signal candle", {"cx": 4})
    add("Close-based exits", "Plus: an engulfing candle against", {"cx": 5})
    for n in (2, 3, 4):
        add("Close-based exits", f"Plus: {n} candles in a row against", {"cx": 6, "cx_n": n}, n)
    add("Close-based exits", "Plus: close across the fast EMA, only in loss", {"cx": 1, "cx_when": 2})
    add("Close-based exits", "Plus: close across the fast EMA, only in profit", {"cx": 1, "cx_when": 1})
    add("Close-based exits", "No target: out on a close across the slow EMA", {"tgt": 1, "cx": 2})
    add("Close-based exits", "No target: out on a close across the fast EMA", {"tgt": 1, "cx": 1})
    for r in (0.5, 0.75, 1, 1.5, 2):
        add("Breakeven", f"Breakeven at +{r:g}R", {"be_r": r}, r)
    add("Breakeven", "Breakeven at +1R, stop at +0.1R", {"be_r": 1, "be_off": 0.1})
    for r in (0.5, 1, 1.5, 2):
        add("Profit lock ladder", f"Lock ladder every {r:g}R", {"lock_r": r}, r)
    for (r, f, be) in ((0.5, 0.5, 1), (1, 0.5, 0), (1, 0.5, 1), (1.5, 0.5, 1), (2, 0.5, 1), (1, 0.33, 1)):
        add("Partial close", f"{round(100 * f)}% off at {r:g}R" + (" + breakeven" if be else ""), {"p1_r": r, "p1_frac": f, "p1_be": be})
    add("Partial close", "33% at 1R + 33% at 2R + breakeven", {"p1_r": 1, "p1_frac": 0.33, "p1_be": 1, "p2_r": 2, "p2_frac": 0.33})
    for k in (2, 3, 5, 8, 12, 20):
        add("Trailing ($)", f"Trail ${k}", {"tr": 1, "tr_k": k}, k)
    for k in (3, 5, 8):
        add("Trailing ($)", f"Trail ${k} from +1R", {"tr": 1, "tr_k": k, "tr_act": 1})
    for k in (1, 1.5, 2, 3, 4):
        add("Trailing (ATR)", f"Trail {k:g} ATR", {"tr": 2, "tr_k": k}, k)
    for k in (1, 2, 3):
        add("Trailing (ATR)", f"Trail {k:g} ATR from +1R", {"tr": 2, "tr_k": k, "tr_act": 1})
    for k in (2, 3):
        add("Trailing (ATR)", f"No target, trail {k:g} ATR (chandelier)", {"tgt": 1, "tr": 2, "tr_k": k})
    for k, a in ((30, 1), (50, 1), (70, 1), (50, 2)):
        add("Trailing (keep % of the best profit)", f"Keep {k}% of the best profit from +{a}R", {"tr": 3, "tr_k": k, "tr_act": a})
    for tm, nm in ((4, "the fast EMA"), (5, "the slow EMA"), (6, "the previous candle"), (8, "the last swing")):
        add("Trailing (EMA / candles / swing)", f"Trail {nm}", {"tr": tm})
        add("Trailing (EMA / candles / swing)", f"No target, trail {nm}", {"tgt": 1, "tr": tm})
    for n in (3, 5, 10, 20):
        add("Trailing (EMA / candles / swing)", f"Trail the {n}-candle low / high", {"tr": 7, "tr_k": n}, n)
    add("Trailing (EMA / candles / swing)", "No target, trail the 10-candle low / high (turtle)", {"tgt": 1, "tr": 7, "tr_k": 10})
    add("Trailing (EMA / candles / swing)", "No target, trail the 20-candle low / high (turtle)", {"tgt": 1, "tr": 7, "tr_k": 20})
    for n in (4, 8, 16, 32):
        add("Time", f"Plus: out after {n} candles", {"max_bars": n}, n)
    for n, r in ((4, 0.5), (8, 0.5), (8, 0), (16, 0.5)):
        add("Time", f"Plus: out if not +{r:g}R after {n} candles", {"stale_bars": n, "stale_r": r})
    for a in (20, 25):
        add("Time", f"Plus: out when ADX falls below {a}", {"adx_exit": a}, a)
    add("Time", "Plus: Friday close at 21:00 server", {"fri_hour": 21})
    combos = [
        ("2R target + breakeven at 1R", {"tgt": 2, "tgt_k": 2, "be_r": 1}),
        ("3R target + breakeven at 1R", {"tgt": 2, "tgt_k": 3, "be_r": 1}),
        ("1.5R target + breakeven at 0.75R", {"tgt": 2, "tgt_k": 1.5, "be_r": 0.75}),
        ("Half at 1R + breakeven, rest to the EA's target", {"p1_r": 1, "p1_frac": 0.5, "p1_be": 1}),
        ("Half at 1R + breakeven, rest trails 2 ATR", {"p1_r": 1, "p1_frac": 0.5, "p1_be": 1, "tgt": 1, "tr": 2, "tr_k": 2}),
        ("Half at 1R + breakeven, rest trails the previous candle", {"p1_r": 1, "p1_frac": 0.5, "p1_be": 1, "tgt": 1, "tr": 6}),
        ("Thirds: 1R, 2R, the rest trails 3 ATR", {"p1_r": 1, "p1_frac": 0.33, "p1_be": 1, "p2_r": 2, "p2_frac": 0.33, "tgt": 1, "tr": 2, "tr_k": 3}),
        ("EA target + breakeven at 1R + out after 16 candles", {"be_r": 1, "max_bars": 16}),
        ("EA target, fallback by 0.25 ATR, breakeven at 1R", {"fb_buf": 0.25, "be_r": 1}),
        ("EA target + keep 50% of the best profit from 1R", {"tr": 3, "tr_k": 50, "tr_act": 1}),
        ("EA target + trail 2 ATR from 1R", {"tr": 2, "tr_k": 2, "tr_act": 1}),
        ("No target: slow-EMA close + breakeven at 1R", {"tgt": 1, "cx": 2, "be_r": 1}),
        ("No target: trail 3 ATR + 4R target cap", {"tgt": 2, "tgt_k": 4, "tr": 2, "tr_k": 3}),
        ("EA target + 2-close fallback + out if not +0.5R after 8", {"fb_n": 2, "stale_bars": 8, "stale_r": 0.5}),
    ]
    for nm, lab in combos:
        add("Combinations", nm, lab)
    return rows


def catalogue(inputs):
    return _ea_rows(inputs) + _lab_rows()


# ---------------------------------------------------------------- jobs: catalogue / search / heatmap / single test
class Job:
    def __init__(self, action, inputs, ds, **kw):
        self.action, self.inputs, self.ds, self.kw = action, inputs, ("year" if ds == "tv" else ds), kw
        self.running, self.done, self.error, self.phase, self.progress, self.total = False, False, None, "starting", 0, 0
        self.result, self.partial_result, self.t0, self._stop = None, None, None, False
        self.jid = f"{action}-{time.time_ns()}"
        self.window, self.labels = window_of(self.ds, inputs)
        mode = str(inputs.get("InpExitMode", "1"))
        self.lab_sets = {} if mode in ("1", "2") else {"InpExitMode": "1"}       # the lab's exits work on top of exit modes 1-2
        self._base = None

    def stop(self):
        self._stop = True

    # the EA's own exit (the lab off) = the baseline every row is compared with
    def base(self):
        if self._base is None:
            _, real, oe = run(self.inputs, self.ds)
            s = stats(real, self.window, open_end=oe)
            self._base = (s, {(int(x[1]), int(x[0])) for x in real}, {(int(x[1]), int(x[0])): float(x[6]) for x in real},
                          {(int(x[1]), int(x[0])): x for x in real})
        return self._base

    def eval(self, lab=None, sets=None, worst=False):
        b = self.base()
        sets2 = dict(self.lab_sets, **(sets or {})) if lab else (sets or {})
        _, real, oe = run(self.inputs, self.ds, lab=lab, sets=sets2, worst=worst)
        return stats(real, self.window, b[1], b[2], open_end=oe), real

    def score(self, s, objective):
        if s.get("stuck"):
            return -1e12                                              # a trade never closes: the numbers are not usable
        t = s["train"]
        if t["n"] < 20:
            return -1e12 + t["n"]
        if objective == "ret_dd":
            return t["net"] / max(1.0, t["dd"])
        if objective == "pf":
            return t["pf"]
        if objective == "wr":
            return t["wr"] + t["net"] / 1e9
        return t["net"]

    def run(self):
        self.running, self.t0 = True, time.time()
        try:
            self.result = getattr(self, "_" + self.action)()
        except Exception as e:                                      # noqa: BLE001
            import traceback
            self.error = f"{e}"
            self.tb = traceback.format_exc()
        finally:
            self.running, self.done = False, True

    def state(self):
        return {"action": self.action, "jid": self.jid, "req": getattr(self, "req", None), "running": self.running, "done": self.done, "error": self.error, "phase": self.phase,
                "progress": self.progress,
                "total": self.total, "seconds": round(time.time() - self.t0, 1) if self.t0 else 0, "ds": self.ds, "labels": self.labels,
                "partial_result": self.partial_result,
                "lab_sets": self.lab_sets, "result": self.result}

    # ---- diagnose
    def _diagnose(self):
        self.phase = "reading where your exits leave money"
        return diagnose(self.inputs, self.ds)

    # ---- one exit
    def _test(self):
        lab, sets = self.kw.get("lab") or {}, self.kw.get("sets") or {}
        self.phase, self.total = "testing", 2
        b = self.base()[0]
        s, real = self.eval(lab=lab or None, sets=sets)
        self.progress = 1
        self.phase = "worst-case check (adverse move first inside each minute)"
        bw, _ = self.eval(worst=True)
        sw, _ = self.eval(lab=lab or None, sets=sets, worst=True)
        self.progress = 2
        return {"lab": clean(lab) if lab else {}, "sets": sets, "describe": describe(lab) if lab else "the EA's own exit", "stats": s, "base": b,
                "worst": {"total": sw["total"], "base_total": bw["total"]}, "trades": trade_list(real), "diffs": self._diffs(real)}

    def _diffs(self, real):
        """the trades this exit changed most against the EA's own exit (same entry), and the entries it added or lost"""
        bx = self.base()[3]
        rows, new = [], []
        for x in real:
            k = (int(x[1]), int(x[0]))
            y = bx.get(k)
            if y is None:
                new.append(x)
                continue
            d = float(x[6]) - float(y[6])
            if abs(d) > 0.5:
                rows.append([int(x[1]), int(x[0]), round(float(y[6])), round(float(x[6])), WHY.get(int(y[13]), ""), WHY.get(int(x[13]), ""), int(y[4]), int(x[4]), round(d)])
        keys = {(int(x[1]), int(x[0])) for x in real}
        gone = [x for k, x in bx.items() if k not in keys]
        rows.sort(key=lambda r: r[8])
        return {"gain": rows[::-1][:10], "loss": rows[:10], "n": len(rows), "up": sum(1 for r in rows if r[8] > 0),
                "new": {"n": len(new), "net": round(float(sum(x[6] for x in new)))}, "gone": {"n": len(gone), "net": round(float(sum(x[6] for x in gone)))}}

    # ---- every exit
    def _catalogue(self):
        rows = catalogue(self.inputs)
        self.total = len(rows) + 2
        self.phase = "the EA's own exit"
        b = self.base()[0]
        out = []
        for r in rows:
            if self._stop:
                break
            self.phase = f"{r['fam']}: {r['name']}"
            s, _ = self.eval(lab=r.get("lab"), sets=r.get("sets"))
            row = {k: v for k, v in r.items()}
            row["stats"] = {k: s[k] for k in ("train", "test", "all", "total", "new", "gone", "changed", "partials", "why", "longest_h", "open_end", "stuck")}
            row["describe"] = describe(r["lab"]) if r.get("lab") else ""
            out.append(row)
            self.progress += 1
        # robustness: a row whose neighbours in its family (the next value either side) also beat yours
        fams = {}
        for n, r in enumerate(out):
            if r.get("axis") is not None:
                fams.setdefault(r["fam"], []).append(n)
        bt = b["total"]
        for idx in fams.values():
            idx = sorted(idx, key=lambda n: out[n]["axis"])
            for p, n in enumerate(idx):
                nb = [out[m]["stats"]["total"] > bt for m in (idx[p - 1] if p > 0 else None, idx[p + 1] if p + 1 < len(idx) else None) if m is not None]
                out[n]["plateau"] = bool(out[n]["stats"]["total"] > bt and nb and all(nb))
        # the worst-case order for the best 20
        self.phase = "worst-case check of the best 20"
        bw = self.eval(worst=True)[0]["total"]
        top = sorted(range(len(out)), key=lambda n: -out[n]["stats"]["total"])[:20]
        self.total += len(top)
        for n in top:
            if self._stop:
                break
            r = out[n]
            sw, _ = self.eval(lab=r.get("lab"), sets=r.get("sets"), worst=True)
            r["worst"] = {"total": sw["total"], "base_total": bw}
            self.progress += 1
        return {"base": b, "rows": out, "lab_sets": self.lab_sets, "stopped": bool(self._stop), "of": len(rows)}

    # ---- the smart search: chosen on the first half only, judged on the unseen half
    def _neighbours(self, lab, f, d):
        g = GRID.get(f)
        if isinstance(g, dict):
            g = g.get(int(lab.get("tgt" if f == "tgt_k" else "tr", 0)))
        if not g:
            return None
        lo, hi, st = g
        v = float(lab.get(f, DEFAULT.get(f, 0))) + d * st
        if v < lo - 1e-9 or v > hi + 1e-9:
            return None
        return round(v / st) * st if st >= 1 else round(v, 4)

    def _active(self, lab):
        c = clean(lab)
        fs = [f for f in c if f in GRID]
        if int(c.get("tgt", 0)) >= 2 and "tgt_k" not in fs:
            fs.append("tgt_k")
        return fs

    def _descend(self, lab, objective, best_s, log, tag):
        lab = dict(lab)
        improved = True
        while improved and not self._stop:
            improved = False
            for f in self._active(lab):
                for d in (1, -1):
                    while not self._stop:
                        v = self._neighbours(lab, f, d)
                        if v is None:
                            break
                        cand = dict(lab, **{f: v})
                        s, _ = self.eval(lab=cand)
                        self.progress += 1
                        if self.score(s, objective) > self.score(best_s, objective):
                            log.append({"stage": tag, "change": f"{f} {lab.get(f, DEFAULT.get(f))} -> {v}", "lab": clean(cand), "describe": describe(cand),
                                        "train": s["train"], "test": s["test"], "total": s["total"]})
                            lab, best_s, improved = cand, s, True
                        else:
                            break
        return lab, best_s

    def _search(self):
        objective = self.kw.get("objective") or "net"
        b = self.base()[0]
        self.phase = "testing every exit first (the starting points)"
        cat = self.kw.get("cat_rows")
        if not cat:
            cat = self._catalogue()["rows"]
        labs = [r for r in cat if r["kind"] == "lab"]
        seeds = sorted(labs, key=lambda r: -self.score(r["stats"], objective))[:6]
        log, finals = [], []
        self.total = self.progress + 600
        for sd in seeds:
            if self._stop:
                break
            self.phase = f"tuning: {sd['name']}"
            s0, _ = self.eval(lab=sd["lab"])
            lab, s = self._descend(sd["lab"], objective, s0, log, sd["name"])
            # add-ons: each kind of exit that is not in the recipe yet, kept only if the first half improves
            self.phase = f"adding to: {sd['name']}"
            for add in ({"be_r": 1}, {"be_r": 0.5}, {"lock_r": 1}, {"p1_r": 1, "p1_frac": 0.5, "p1_be": 1}, {"tr": 2, "tr_k": 2, "tr_act": 1},
                        {"tr": 6, "tr_act": 1}, {"max_bars": 16}, {"max_bars": 32}, {"stale_bars": 8, "stale_r": 0.25}, {"adx_exit": 20},
                        {"cx": 1, "cx_buf": 0.25, "cx_when": 2}, {"fb_buf": 0.25}, {"fb_n": 2}):
                if self._stop:
                    break
                if any(k in clean(lab) for k in add if k not in ("p1_frac", "p1_be", "tr_k", "tr_act", "cx_buf", "cx_when", "stale_r")):
                    continue
                cand = dict(lab, **add)
                s2, _ = self.eval(lab=cand)
                self.progress += 1
                if self.score(s2, objective) > self.score(s, objective):
                    log.append({"stage": sd["name"], "change": "add " + describe(dict({"tgt": 0}, **add)).replace("EA target (next EMA) · ", ""),
                                "lab": clean(cand), "describe": describe(cand), "train": s2["train"], "test": s2["test"], "total": s2["total"]})
                    lab, s = cand, s2
            lab, s = self._descend(lab, objective, s, log, sd["name"])
            finals.append({"seed": sd["name"], "lab": clean(lab), "describe": describe(lab), "stats": s})
        # robustness of each final: every numeric part one step either side - how many still beat yours in BOTH halves?
        self.phase = "robustness: one step either side of every number"
        for fin in finals:
            if self._stop:
                break
            ok = tot = 0
            for f in self._active(fin["lab"]):
                for d in (1, -1):
                    v = self._neighbours(fin["lab"], f, d)
                    if v is None:
                        continue
                    s, _ = self.eval(lab=dict(fin["lab"], **{f: v}))
                    self.progress += 1
                    tot += 1
                    ok += int(s["train"]["net"] > b["train"]["net"] and s["test"]["net"] > b["test"]["net"])
            fin["plateau"] = [ok, tot]
            sw, _ = self.eval(lab=fin["lab"], worst=True)
            fin["worst"] = sw["total"]
        bw = self.eval(worst=True)[0]["total"]
        finals.sort(key=lambda r: -self.score(r["stats"], objective))
        return {"base": b, "base_worst": bw, "finals": finals, "log": log, "objective": objective}

    # ---- every lever of the research bench over its range: what each value does to WR / PF / net (Zee: "Win 25% winrate by moving this slider to X")
    LEVERS = {"sl": [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0, 4.0], "tg": [0, 1, 1.5, 2, 3, 4, 6, 10, 15, 21, 30], "tr": [0, 1, 1.5, 2, 3, 4, 6, 10, 20, 30],
              "ta": [0, 0.5, 1, 1.5, 2, 3, 5, 8], "be": [0, 0.5, 1, 1.5, 2, 3, 5], "p1": [0, 0.5, 1, 1.5, 2, 3, 5, 8]}

    def _sweep(self):
        """every setting the EA has, a few steps either way, from the bench (scan.py - the runs spread over the cores)"""
        import scan
        return scan.run_all(self, self.inputs, self.ds, self.kw.get("lab") or {}, self.kw.get("sets") or {}, self.window, self.kw.get("focus"))

    # ---- two numbers against each other
    def _heatmap(self):
        lab = dict(self.kw.get("lab") or {})
        fx, fy = self.kw["fx"], self.kw["fy"]
        xs, ys = self.kw["xs"], self.kw["ys"]
        b = self.base()[0]
        self.total = len(xs) * len(ys)
        grid = []
        for yv in ys:
            row = []
            for xv in xs:
                if self._stop:
                    break
                self.phase = f"{fx} {xv} · {fy} {yv}"
                s, _ = self.eval(lab=dict(lab, **{fx: xv, fy: yv}))
                row.append({"train": s["train"]["net"], "test": s["test"]["net"], "total": s["total"], "wr": s["all"]["wr"], "n": s["all"]["n"], "stuck": s["stuck"]})
                self.progress += 1
            grid.append(row)
        return {"base": b, "fx": fx, "fy": fy, "xs": xs, "ys": ys, "grid": grid, "lab": clean(lab), "describe": describe(lab)}


def blocks_text():
    """the building blocks for Claude: field, what it does, its options"""
    out = []
    for title, hint, fields in GROUPS:
        for x in fields:
            s = f"{x['f']} ({x['label']})"
            if x["t"] == "sel":
                s += ": " + "; ".join(f"{k} = {v}" for k, v in x["opts"])
            out.append(f"[{title}] {s}")
    return "\n".join(out)


def ea_trust():
    """settings where the Turtle TV Tester and MT5 move the result in opposite directions (verify_settings.py)"""
    import json
    from pathlib import Path
    p = Path(__file__).parent / "simdata" / "verify_settings.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                               # noqa: BLE001
        return {}
    out = {}
    for k, v in d.items():
        try:
            dm, ds_ = v["mt5"]["net"] - v["mt5_base"]["net"], v["sim"]["net"] - v["sim_base"]["net"]
        except Exception:                                           # noqa: BLE001
            continue
        sg = lambda x: 0 if abs(x) < 300 else (1 if x > 0 else -1)  # noqa: E731
        out[k] = "agree" if sg(dm) == sg(ds_) else ("opposite" if sg(dm) * sg(ds_) == -1 else "differ")
    return out


def start(action, inputs, ds, **kw):
    j = Job(action, inputs, ds, **kw)
    threading.Thread(target=j.run, daemon=True).start()
    return j
