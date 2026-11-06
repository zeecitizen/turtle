"""tplab.py - Take Profit Lab: where do we take profit? Runs the Turtle TV tester on the current settings with the
take-profit distance set to each value (InpFixTpPips, pips; 0 = the rules' own targets) and reports what each one earns.
Results are the tester's (MT5 decides - see the Exit Lab's validation). Nothing here changes an EA default."""
import time
import threading
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import sim

TP_PIPS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 50, 60, 80]


def _stats(tr):
    pnl = np.asarray([x[6] for x in tr if x[10] == 0], dtype=float)
    n = int(len(pnl))
    if n == 0:
        return {"n": 0, "net": 0.0, "pf": None, "wr": None, "avg_win": None, "avg_loss": None, "worst": None}
    w = pnl[pnl > 0]; l = pnl[pnl <= 0]
    gl = -l.sum()
    return {"n": n, "net": round(float(pnl.sum()), 2), "pf": round(float(w.sum() / gl), 2) if gl > 0 else None,
            "wr": round(100.0 * len(w) / n, 1), "avg_win": round(float(w.mean()), 2) if len(w) else None,
            "avg_loss": round(float(l.mean()), 2) if len(l) else None, "worst": round(float(pnl.min()), 2)}


def run(inputs, ds="year1", mode="ea", tp_values=None):
    """the sweep: one tester run per take-profit distance, side by side"""
    t0 = time.time()
    vals = tp_values or TP_PIPS
    chart = mode == "chart"

    def one(v):
        inp = dict(inputs, InpFixTpPips=str(v))
        tr = sim.simulate(inp, ds=ds, chart=chart)[0]
        return {"tp_pips": v, **_stats(tr)}

    sim.simulate(dict(inputs, InpFixTpPips="0"), ds=ds, chart=chart)     # warm the caches before the parallel runs
    with ThreadPoolExecutor(max_workers=6) as ex:
        rows = list(ex.map(one, vals))
    best = max(rows, key=lambda r: r["net"]) if rows else None
    return {"ds": ds, "rows": rows, "best": best, "seconds": round(time.time() - t0, 1),
            "note": "tp_pips 0 = the settings' own targets (support, EMA, resistance); the others are a fixed take-profit distance"}


# ---- sliders and the scan over every take-profit setting
TP_SETTINGS = {                                  # the take-profit inputs the EA has, with the values the scan tries
    "InpFixTpPips": [0, 5, 10, 15, 20, 25, 30, 40, 50, 60],          # fixed target distance, pips (0 = own targets)
    "InpLongTpPips": [0, 5, 10, 20, 30],                             # long: take profit this many pips before the exit EMA
    "InpMinTpPips": [0, 5, 10, 20],                                  # the target at least this far from the entry
    "InpBeTpPct": [0, 0.5, 0.75, 0.9],                               # move the stop to entry after this share of the way to the target
}


def one(inputs, ds="year1", mode="ea", overrides=None):
    """one tester run with some take-profit inputs changed: the slider's numbers + the trades' P&L (for the diagram)"""
    chart = mode == "chart"
    inp = dict(inputs, **{k: str(v) for k, v in (overrides or {}).items()})
    tr = sim.simulate(inp, ds=ds, chart=chart)[0]
    st = _stats(tr)
    pnl = [round(float(x[6]), 2) for x in tr if x[10] == 0]
    return {"stats": st, "pnl": pnl[:4000], "overrides": overrides or {}}


PROG = {"running": False, "done": 0, "total": 0, "current": "", "result": None, "error": None, "started": 0.0}


def scan(inputs, ds="year1", mode="ea", settings=None):
    """every take-profit setting, one value at a time (the others as on screen); the best per setting.
    Progress is written to PROG as each run finishes (the page polls it)."""
    t0 = time.time()
    if settings is None:
        settings = TP_SETTINGS if str(inputs.get("InpExitMode", "0")) == "0" else {
            "InpFixTpPips": TP_SETTINGS["InpFixTpPips"],
        }
    jobs = [(k, v) for k, vals in settings.items() for v in vals]
    PROG.update(running=True, done=0, total=len(jobs), current="baseline", result=None, error=None, started=t0)
    try:
        base = sim.simulate(inputs, ds=ds, chart=(mode == "chart"))[0]
        def go(job):
            k, v = job
            PROG["current"] = f"{tp_label(k)} → {v}"
            inp = dict(inputs, **{k: _sv(v)})
            tr = sim.simulate(inp, ds=ds, chart=(mode == "chart"))[0]
            PROG["done"] += 1
            return {"setting": k, "value": v, **_stats(tr)}
        with ThreadPoolExecutor(max_workers=6) as ex:
            rows = list(ex.map(go, jobs))
        best = {}
        for r in rows:
            if r["net"] is not None and (r["setting"] not in best or r["net"] > best[r["setting"]]["net"]):
                best[r["setting"]] = r
        PROG["result"] = {"ds": ds, "base": _stats(base), "rows": rows, "best": best, "seconds": round(time.time() - t0, 1)}
    except Exception as e:                                       # noqa: BLE001
        PROG["error"] = str(e)
    finally:
        PROG["running"] = False
    return PROG["result"]


def scan_start(inputs, ds="year1", mode="ea"):
    """start the scan in the background (one at a time)"""
    with TUNE_LOCK:
        if PROG["running"] or TUNE["running"]:
            return {"ok": False, "busy": True}
        PROG["running"] = True
    threading.Thread(target=scan, args=(inputs, ds, mode), daemon=True).start()
    return {"ok": True}


def tp_label(name):
    c = TP_CONTROL.get(name)
    return c["label"] if c else name


def progress():
    p = dict(PROG)
    p["seconds"] = round(time.time() - p["started"], 1) if p["started"] else 0
    p.pop("started", None)
    return p


# ---- the path of every trade: how far price went for us (MFE) and against us (MAE), and what each target would earn
PIP = 0.1                       # gold: 1 pip = $0.10 of price (the EA's pip)
USD_PER_PIP = 20.0              # 2 lots: $20 per pip


def paths(inputs, ds="year1", mode="ea"):
    """one tester run, then each trade's excursions from the candles, the hit rate for every target distance, and the
    estimated earnings of each (a target is hit when the excursion reaches it; other trades keep what they made).
    An estimate to aim the tester - the tester run with the target set is the judge."""
    tr = sim.simulate(inputs, ds=ds, chart=(mode == "chart"))[0]
    D = sim.data(ds)
    t1, h1, l1 = np.asarray(D["t1"]), np.asarray(D["h1"]), np.asarray(D["l1"])
    rows = []
    for x in tr:
        if x[10] != 0:
            continue
        side, tin, en, tout, pnl = int(x[0]), float(x[1]), float(x[2]), float(x[4]), float(x[6])
        a = int(np.searchsorted(t1, tin, side="left")); b = int(np.searchsorted(t1, tout, side="right"))
        if b <= a:
            continue
        hi, lo = float(h1[a:b].max()), float(l1[a:b].min())
        fav = (hi - en) if side > 0 else (en - lo)          # best move for us, price units
        adv = (en - lo) if side > 0 else (hi - en)          # worst move against us
        rows.append({"side": side, "t": tin, "mfe": max(0.0, fav) / PIP, "mae": max(0.0, adv) / PIP, "pnl": pnl})
    if not rows:
        return {"trades": 0}
    mfe = np.array([r["mfe"] for r in rows]); pnl = np.array([r["pnl"] for r in rows])
    grid = list(range(5, 81, 5))
    curve = []
    for X in grid:
        hit = mfe >= X
        ev = np.where(hit, X * USD_PER_PIP, pnl)           # estimate: hit -> the target's pips; miss -> the trade's own result
        curve.append({"tp": X, "hit_rate": round(100.0 * float(hit.mean()), 1), "est_net": round(float(ev.sum()), 0),
                      "est_avg": round(float(ev.mean()), 2)})
    best = max(curve, key=lambda c: c["est_net"])
    hist, edges = np.histogram(mfe, bins=np.arange(0, 121, 5))
    maes = np.array([r["mae"] for r in rows])
    return {"trades": len(rows), "actual_net": round(float(pnl.sum()), 0), "curve": curve, "best": best,
            "mfe_hist": {"edges": edges.tolist(), "counts": hist.tolist()},
            "mfe_median": round(float(np.median(mfe)), 1), "mfe_p75": round(float(np.percentile(mfe, 75)), 1),
            "mae_median": round(float(np.median(maes)), 1), "mae_p75": round(float(np.percentile(maes, 75)), 1),
            "scatter": [[round(r["mfe"], 1), round(r["pnl"], 0)] for r in rows[:3000]],
            "note": "estimate: hit = the excursion reached the target; losers and the rest keep their own result. Aim with it, then confirm with a tester run."}


# ---- every take-profit related EA input: slider (number) or choice (bool / enum), with the values the scan tries
def _c(name, label, group, lo, hi, step, vals):
    return {"name": name, "label": label, "group": group, "kind": "num", "min": lo, "max": hi, "step": step, "vals": vals}


def _e(name, label, group, opts, vals=None):
    return {"name": name, "label": label, "group": group, "kind": "enum", "options": opts, "vals": vals or [v for v, _ in opts]}


TP_CONTROLS = [
    _e("InpSlMode", "Initial stop-loss method", "Initial risk",
       [(0, "Pips beyond setup candle"), (1, "ATR multiple from entry"), (2, "Price distance from entry")]),
    _c("InpSlPips", "Initial stop distance (pips; used by stop method 0)", "Initial risk", 1, 300, 1, [15, 30, 50, 95]),
    _c("InpSlAtrMult", "Initial stop distance (ATR multiple; used by stop method 1)", "Initial risk", 0.1, 10, 0.1, [0.5, 1, 1.2, 1.7, 2]),
    _c("InpSlUsd", "Initial stop distance (price units; used by stop method 2)", "Initial risk", 0.1, 100, 0.1, [5, 10, 25, 50]),
    _c("InpMaxRiskUsd", "Skip entry if initial stop exceeds this price distance (0 = off)", "Initial risk", 0, 1000, 10, [0, 10, 20, 50, 100]),
    _c("InpFixTpPips", "Fixed target (pips, 0 = the rules' own)", "Targets", 0, 80, 5, [0, 5, 10, 15, 20, 25, 30, 40, 50, 60]),
    _c("InpLongTpPips", "Long: pips before the exit EMA", "Targets", 0, 40, 5, [0, 5, 10, 20, 30]),
    _c("InpShortTpPips", "Short: pips before the support", "Targets", 0, 40, 5, [0, 5, 10, 20, 30]),
    _c("InpMinTpPips", "Target at least this far from entry (pips)", "Targets", 0, 30, 5, [0, 5, 10, 20]),
    _c("InpMaxTpPips", "Skip a short if its support is further (pips, 0 = off)", "Targets", 0, 200, 10, [0, 50, 100, 150]),
    _c("InpBeTpPct", "Breakeven: share of the way to the target", "Breakeven", 0, 1, 0.05, [0, 0.25, 0.5, 0.75, 0.9]),
    _c("InpBeUsd", "Breakeven once price moved $ (0 = off)", "Breakeven", 0, 10, 0.5, [0, 1, 2, 3, 5]),
    _c("InpPartialPct", "Partial close at TP1 (share of position)", "Partial close", 0, 1, 0.05, [0, 0.25, 0.5, 0.75]),
    _c("InpLockPips", "Lock the stop this many pips short of the TP", "Trail", 0, 30, 1, [0, 2, 5, 10]),
    _c("InpLongTrailUsd", "Long trail: $ behind the market", "Trail", 0.5, 10, 0.5, [0.5, 1, 2, 3, 5]),
    _c("InpShortTrailUsd", "Short trail: $ above the market", "Trail", 0.5, 10, 0.5, [0.5, 1, 2, 3, 5]),
    _c("InpTrailStepUsd", "Widen the trail by $ at each TP reached (0 = fixed)", "Trail", 0, 5, 0.5, [0, 0.5, 1, 2]),
    _e("InpRideLock", "When the TP is reached, lock the stop at", "Trail", [(0, "the TP"), (1, "the entry"), (2, "don't lock")]),
    _e("InpLongTouch", "Long at the exit EMA: touch-trail mode", "Trail", [(0, "old exit"), (1, "touch + trail")]),
    _e("InpShortTouch", "Short at the support: touch-trail mode", "Trail", [(0, "old exit"), (1, "touch + trail")]),
    _e("InpLongResTp", "Long: aim for the next resistance (TP2)", "Trail", [(0, "off"), (1, "on")], [False, True]),
    _e("InpLongResTp1", "Long with no EMA target: TP1 = next resistance", "Trail", [(0, "off"), (1, "on")], [False, True]),
    _e("InpTp1Be", "At TP1 the rest of the stop never below entry", "Partial close", [(0, "off"), (1, "on")], [False, True]),
    _e("InpExitMode", "Exit mode (0 = v1.23 exits, 1 = next EMA beyond entry)", "Exit mode", [(0, "v1.23"), (1, "next EMA")]),
    _e("InpXTgt", "Lab target type", "Lab partials", [(0, "the mode's own"), (1, "none"), (2, "R multiple"), (3, "ATR multiple"), (4, "$ distance")]),
    _c("InpXTgtK", "Lab target size (R / x ATR / $)", "Lab partials", 0.5, 10, 0.5, [1, 2, 3, 4]),
    _c("InpXP1R", "Lab partial 1 at +R (0 = off)", "Lab partials", 0, 5, 0.25, [0, 1, 1.5, 2, 3]),
    _c("InpXP1Frac", "Lab partial 1: share closed", "Lab partials", 0, 1, 0.05, [0.25, 0.5, 0.75]),
    _e("InpXP1Be", "Lab partial 1: then stop to breakeven", "Lab partials", [(0, "off"), (1, "on")], [False, True]),
    _c("InpXP2R", "Lab partial 2 at +R (0 = off)", "Lab partials", 0, 8, 0.25, [0, 2, 3, 4, 6]),
    _c("InpXP2Frac", "Lab partial 2: share closed", "Lab partials", 0, 1, 0.05, [0.25, 0.5]),
    _c("InpXBeR", "Lab breakeven at +R (0 = off)", "Lab breakeven & trail", 0, 3, 0.25, [0, 0.5, 1, 1.5, 2]),
    _c("InpXLockR", "Lab lock ladder every R (0 = off)", "Lab breakeven & trail", 0, 3, 0.25, [0, 0.5, 1, 2]),
    _e("InpXTr", "Lab trail type", "Lab breakeven & trail", [(0, "off"), (1, "$ from best"), (2, "ATR from best"), (3, "keep % of best"), (4, "fast EMA"), (5, "slow EMA"), (6, "previous N candles")]),
    _c("InpXTrK", "Lab trail size (k)", "Lab breakeven & trail", 0.5, 10, 0.5, [1, 2, 3, 4]),
    _c("InpXTrAct", "Lab trail starts at +R", "Lab breakeven & trail", 0, 4, 0.25, [0, 1, 2]),
]

MODE2_CONTROLS = [
    _c("InpEmaSlow", "Slow EMA period (Mode 2 exit line)", "Mode 2 target", 2, 200, 1, [20, 32, 50, 100]),
    _e("InpSlMode", "Initial stop-loss method", "Initial risk",
       [(0, "Pips beyond setup candle"), (1, "ATR multiple from entry"), (2, "Price distance from entry")]),
    _c("InpSlPips", "Initial stop distance (pips; used by stop method 0)", "Initial risk", 1, 300, 1, [15, 30, 50, 95]),
    _c("InpSlAtrMult", "Initial stop distance (ATR multiple; used by stop method 1)", "Initial risk", 0.1, 10, 0.1, [0.5, 1, 1.2, 1.7, 2]),
    _c("InpSlUsd", "Initial stop distance (price units; used by stop method 2)", "Initial risk", 0.1, 100, 0.1, [5, 10, 25, 50]),
    _c("InpMaxRiskUsd", "Skip entry if initial stop exceeds this price distance (0 = off)", "Initial risk", 0, 1000, 10, [0, 10, 20, 50, 100]),
    _c("InpFixTpPips", "Fixed broker target (pips; 0 = off)", "Target overlays", 0, 100, 1, [0, 10, 20, 40, 60]),
    _e("InpXTgt", "Exit Lab target type (in addition to the slow-EMA close)", "Target overlays",
       [(0, "Mode 2 slow-EMA close"), (1, "No extra target"), (2, "R multiple"), (3, "ATR multiple"), (4, "Price distance")]),
    _c("InpXTgtK", "Exit Lab target size (R / ATR / price)", "Target overlays", 0.5, 100, 0.5, [1, 2, 4, 10, 25]),
    _e("InpXCx", "Additional close-based exit", "Close confirmations",
       [(0, "Off"), (1, "Close across fast EMA"), (2, "Close across slow EMA"), (3, "EMA cross"), (4, "Opposite signal"), (5, "Engulfing candle"), (6, "N candles against")]),
    _c("InpXCxBuf", "Close-exit buffer (ATR multiples)", "Close confirmations", 0, 3, 0.1, [0, 0.25, 0.5, 1]),
    _c("InpXCxN", "Consecutive confirming candles", "Close confirmations", 1, 10, 1, [1, 2, 3, 4]),
    _e("InpXCxWhen", "Allow close-based exit", "Close confirmations", [(0, "Always"), (1, "Only in profit"), (2, "Only in loss")]),
    _c("InpXCxAfter", "Ignore first N candles", "Close confirmations", 0, 48, 1, [0, 1, 2, 4, 8, 12]),
    _c("InpXP1R", "Partial 1 at +R (0 = off)", "Partial closes", 0, 8, 0.25, [0, 0.5, 1, 1.5, 2, 3]),
    _c("InpXP1Frac", "Partial 1: share closed", "Partial closes", 0.05, 0.95, 0.05, [0.25, 0.5, 0.75]),
    _e("InpXP1Be", "Move remaining stop to breakeven after partial 1", "Partial closes", [(0, "Off"), (1, "On")], [False, True]),
    _c("InpXP2R", "Partial 2 at +R (0 = off)", "Partial closes", 0, 8, 0.25, [0, 1, 2, 3, 4, 6]),
    _c("InpXP2Frac", "Partial 2: share closed", "Partial closes", 0.05, 0.95, 0.05, [0.25, 0.5, 0.75]),
    _c("InpXBeR", "Move stop at +R (0 = off)", "Breakeven & locks", 0, 5, 0.25, [0, 0.5, 1, 1.5, 2, 3]),
    _c("InpXBeOff", "Stop offset from entry (R)", "Breakeven & locks", -1, 2, 0.1, [-0.5, 0, 0.25, 0.5, 1]),
    _c("InpXLockR", "Lock ladder step (R; 0 = off)", "Breakeven & locks", 0, 3, 0.25, [0, 0.5, 1, 1.5, 2]),
    _e("InpXTr", "Trailing stop type", "Trailing stop",
       [(0, "Off"), (1, "Price distance from best"), (2, "ATR distance from best"), (3, "Keep % of best profit"),
        (4, "Fast EMA"), (5, "Slow EMA"), (6, "Previous candle"), (7, "N-candle range"), (8, "Last swing")]),
    _c("InpXTrK", "Trail distance / percentage / candles", "Trailing stop", 0.5, 100, 0.5, [1, 2, 4, 10, 25]),
    _c("InpXTrAct", "Start trailing at +R", "Trailing stop", 0, 5, 0.25, [0, 0.5, 1, 1.5, 2]),
    _c("InpXTrBuf", "Trail buffer (price units)", "Trailing stop", 0, 10, 0.1, [0, 0.5, 1, 2]),
    _c("InpXMaxBars", "Maximum bars to hold (0 = off)", "Time & regime exits", 0, 96, 1, [0, 4, 8, 12, 16, 24, 48]),
    _c("InpXStaleBars", "Exit if no progress after N bars (0 = off)", "Time & regime exits", 0, 96, 1, [0, 4, 8, 12, 16, 24]),
    _c("InpXStaleR", "Required progress in R by stale check", "Time & regime exits", -1, 3, 0.1, [-0.5, 0, 0.25, 0.5, 1]),
    _c("InpXAdxExit", "Exit if ADX falls below (0 = off)", "Time & regime exits", 0, 60, 1, [0, 10, 15, 20, 25, 30]),
    _c("InpXFriHour", "Friday close at server hour (0 = off)", "Time & regime exits", 0, 23, 1, [0, 12, 15, 18, 20, 22]),
    _c("InpXLossCap", "Maximum initial stop distance (price; 0 = off)", "Loss protection", 0, 50, 0.5, [0, 5, 10, 15, 20, 25]),
    _c("InpXLpR", "Close a share at this loss in R (0 = off)", "Loss protection", 0, 3, 0.1, [0, 0.5, 1, 1.5, 2]),
    _c("InpXLpFrac", "Loss-cut share to close", "Loss protection", 0.05, 0.95, 0.05, [0.25, 0.5, 0.75]),
    _c("InpXDecayBars", "Tighten stop after N bars (0 = off)", "Loss protection", 0, 96, 1, [0, 4, 8, 12, 16, 24]),
    _c("InpXDecayR", "Tightened stop level from entry (R)", "Loss protection", -2, 2, 0.1, [-1, -0.5, 0, 0.5, 1]),
]

MODE1_CONTROLS = [
    _c("InpEmaFast", "Fast EMA period (nearer target)", "EMA target", 2, 100, 1, [5, 9, 20, 50]),
    _c("InpEmaSlow", "Slow EMA period (nearer target)", "EMA target", 2, 200, 1, [20, 32, 50, 100]),
    _e("InpSlMode", "Initial stop-loss method", "Initial risk",
       [(0, "Pips beyond setup candle"), (1, "ATR multiple from entry"), (2, "Price distance from entry")]),
    _c("InpSlPips", "Initial stop distance (pips; used by stop method 0)", "Initial risk", 1, 300, 1, [15, 30, 50, 95]),
    _c("InpSlAtrMult", "Initial stop distance (ATR multiple; used by stop method 1)", "Initial risk", 0.1, 10, 0.1, [0.5, 1, 1.2, 1.7, 2]),
    _c("InpSlUsd", "Initial stop distance (price units; used by stop method 2)", "Initial risk", 0.1, 100, 0.1, [5, 10, 25, 50]),
    _c("InpMaxRiskUsd", "Skip entry if initial stop exceeds this price distance (0 = off)", "Initial risk", 0, 1000, 10, [0, 10, 20, 50, 100]),
    _c("InpFixTpPips", "Fixed broker target (pips; 0 = off)", "Target overlays", 0, 100, 1, [0, 10, 20, 40, 60]),
    _e("InpXFb", "Fallback when no EMA is beyond entry", "No-EMA fallback",
       [(0, "Close back across fast EMA"), (1, "Close back across slow EMA"), (2, "No fallback close")]),
    _c("InpXFbBuf", "Fallback close buffer (ATR multiples)", "No-EMA fallback", 0, 3, 0.1, [0, 0.25, 0.5, 1]),
    _c("InpXFbN", "Consecutive fallback close confirmations", "No-EMA fallback", 1, 10, 1, [1, 2, 3, 4]),
    _e("InpXEntryWait", "Wait out the entry minute before EMA-target exits", "EMA target",
       [(0, "Off"), (1, "On")], [False, True]),
] + [dict(c, options=list(c["options"])) if "options" in c else dict(c)
     for c in MODE2_CONTROLS if c["name"].startswith("InpX") and c["name"] not in {"InpXFb", "InpXFbBuf", "InpXFbN"}]
for _c_ in MODE1_CONTROLS:
    if _c_["name"] == "InpXTgt":
        _c_["label"] = "Exit Lab target type"
        _c_["options"][0] = (0, "The mode's own EMA target")

import sim_full as _sf
for _c_ in TP_CONTROLS:                                            # live only under exit mode 0 (the v1.23 exits)?
    _c_["mode0_only"] = _c_["name"] in _sf.MODE0_ONLY
TP_CONTROL = {c["name"]: c for c in TP_CONTROLS}
TP_SCAN_NAMES = {"InpFixTpPips", "InpLongTpPips", "InpMinTpPips", "InpBeTpPct"}
TP_SETTINGS = {c["name"]: c["vals"] for c in TP_CONTROLS if c["name"] in TP_SCAN_NAMES}


def _sv(v):
    """a value as the EA's input text (bools as the inputs file writes them)"""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def one_set(inputs, ds="year1", mode="ea", overrides=None):
    """one run with any take-profit settings changed (the tuner's controls)"""
    chart = mode == "chart"
    inp = dict(inputs, **{k: _sv(v) for k, v in (overrides or {}).items()})
    tr = sim.simulate(inp, ds=ds, chart=chart)[0]
    return {"stats": _stats(tr), "overrides": overrides or {}}


TUNE = {"running": False, "done": 0, "total": 0, "current": None, "best": None,
        "baseline": None, "result": None, "error": None, "started": 0.0}
TUNE_LOCK = threading.Lock()


def _tune_candidates(control, current):
    if control["kind"] == "enum":
        values = [value for value, _ in control["options"]]
    else:
        lo, hi, step = (Decimal(str(control[k])) for k in ("min", "max", "step"))
        count = int((hi - lo) // step)
        values = [float(lo + step * i) for i in range(count + 1)]
        if values and Decimal(str(values[-1])) < hi:
            values.append(float(hi))
        if step == step.to_integral_value():
            values = [int(value) for value in values]
    if current not in values:
        values.append(current)
    return sorted(values, key=lambda value: (abs(float(value) - float(current)), float(value) > float(current), float(value)))


def _tune_worker(inputs, ds, mode, name, overrides, current, job_id):
    control = next(c for c in MODE2_CONTROLS if c["name"] == name)
    base_overrides = dict(overrides)
    base_overrides.pop(name, None)
    try:
        baseline = one_set(inputs, ds, mode, {**base_overrides, name: current, "InpExitMode": 2})["stats"]
        candidates = _tune_candidates(control, current)
        best = {"value": current, "stats": baseline}
        outcomes = []
        with TUNE_LOCK:
            if TUNE["id"] != job_id:
                return
            TUNE.update(total=len(candidates), baseline=baseline, best=best)
        for value in candidates:
            result = one_set(inputs, ds, mode, {**base_overrides, name: value, "InpExitMode": 2})["stats"]
            outcomes.append(result)
            with TUNE_LOCK:
                if TUNE["id"] != job_id:
                    return
                TUNE["done"] += 1
                TUNE["current"] = value
                if (result["net"] > best["stats"]["net"]
                        or (result["net"] == best["stats"]["net"]
                            and (result["pf"] or 0) > (best["stats"]["pf"] or 0))):
                    best = {"value": value, "stats": result}
                    TUNE["best"] = best
        with TUNE_LOCK:
            if TUNE["id"] == job_id:
                TUNE["result"] = {"name": name, "best": best, "baseline": baseline,
                                  "tested": len(candidates), "material_effect": any(row != baseline for row in outcomes),
                                  "range": ([control["min"], control["max"], control["step"]]
                                            if control["kind"] == "num" else [len(control["options"])])}
    except Exception as error:  # surface simulator and validation failures to the UI
        with TUNE_LOCK:
            if TUNE["id"] == job_id:
                TUNE["error"] = str(error)
    finally:
        with TUNE_LOCK:
            if TUNE["id"] == job_id:
                TUNE["running"] = False


def tune_start(inputs, ds="year1", mode="ea", name=None, overrides=None):
    """Test every allowed value for one Mode 2 setting, keeping other inputs fixed."""
    if ds not in ("year", "m15", "tv", "year1", "m1x", "m5x"):
        return {"ok": False, "error": "Unsupported dataset"}
    if mode not in ("ea", "chart"):
        return {"ok": False, "error": "Unsupported simulation mode"}
    control = next((c for c in MODE2_CONTROLS if c["name"] == name), None)
    if not control:
        return {"ok": False, "error": "Unknown Mode 2 setting"}
    clean_overrides = {}
    for key, value in (overrides or {}).items():
        item = next((c for c in MODE2_CONTROLS if c["name"] == key), None)
        if not item:
            return {"ok": False, "error": f"Unknown Mode 2 override: {key}"}
        if item["kind"] == "enum":
            value_text = str(value).lower()
            if value_text in ("true", "false"):
                index = 1 if value_text == "true" else 0
                option = item["options"][min(index, len(item["options"]) - 1)][0]
            else:
                option = next((v for v, _ in item["options"] if str(v).lower() == value_text), None)
            if option is None:
                return {"ok": False, "error": f"Invalid choice for {key}"}
            clean_overrides[key] = option
        else:
            try:
                number = float(value)
            except (TypeError, ValueError):
                return {"ok": False, "error": f"Invalid number for {key}"}
            if not np.isfinite(number) or number < item["min"] or number > item["max"]:
                return {"ok": False, "error": f"Value outside the allowed range for {key}"}
            clean_overrides[key] = number

    raw_current = clean_overrides.get(name, inputs.get(name, control["vals"][0]))
    if control["kind"] == "enum":
        current_text = str(raw_current).lower()
        if current_text in ("true", "false"):
            index = 1 if current_text == "true" else 0
            current = control["options"][min(index, len(control["options"]) - 1)][0]
        else:
            current = next((v for v, _ in control["options"] if str(v).lower() == current_text), None)
        if current is None:
            return {"ok": False, "error": f"Invalid current choice for {name}"}
    else:
        try:
            current = float(raw_current)
        except (TypeError, ValueError):
            return {"ok": False, "error": f"Invalid current value for {name}"}
        if not np.isfinite(current):
            return {"ok": False, "error": f"Invalid current value for {name}"}
        if Decimal(str(control["step"])) == Decimal(str(control["step"])).to_integral_value() and current.is_integer():
            current = int(current)

    clean_overrides.pop(name, None)
    with TUNE_LOCK:
        if PROG["running"]:
            return {"ok": False, "busy": True, "error": "A Take Profit scan is already running"}
        if TUNE["running"]:
            return {"ok": False, "busy": True, "error": "Another setting is already being auto-tuned"}
        job_id = TUNE.get("id", 0) + 1
        TUNE.clear()
        TUNE.update(id=job_id, running=True, done=0, total=0, name=name, current=None,
                    best=None, baseline=None, result=None, error=None, started=time.time())
    threading.Thread(target=_tune_worker,
                     args=(dict(inputs), ds, mode, name, clean_overrides, current, job_id),
                     daemon=True).start()
    return {"ok": True, "id": job_id}


def tune_progress():
    with TUNE_LOCK:
        progress = dict(TUNE)
    progress["seconds"] = round(time.time() - progress["started"], 1) if progress["started"] else 0
    return progress


# ---- auto-tune (Zee 2026-10-27: "an auto-tune button which can select the best values automatically ... tune all with one button")
# One box = one group of settings of the chosen exit style. Coordinate search: each setting swept on a grid (the others held),
# the best kept, two passes, then a finer look round the winner. "Tune all" tunes every box from the original settings, then
# stacks the box winners that keep helping. The guard keeps "most profit" from buying it with more risk. Tester hypotheses only.
MODE0_EXTRA = {"InpFixTpPips", "InpTp1Be", "InpSlMode", "InpSlPips", "InpSlAtrMult", "InpSlUsd", "InpMaxRiskUsd"}
AUTO = {"running": False, "kind": "", "done": 0, "total": 0, "phase": "", "groups": {}, "stack": None, "base": None,
        "error": None, "started": 0.0, "stop": False, "id": 0}
AUTO_LOCK = threading.Lock()


def controls_for(exit_mode):
    """the boxes the page shows for this exit style (same choice as selectedControls() in tplab.js)"""
    m = int(exit_mode)
    if m == 1:
        return MODE1_CONTROLS
    if m == 2:
        return MODE2_CONTROLS
    return [c for c in TP_CONTROLS if c.get("mode0_only") or c["name"] in MODE0_EXTRA]


def _cur_value(c, inputs):
    raw = inputs.get(c["name"], c["vals"][0])
    if c["kind"] == "enum":
        t = str(raw).strip().lower()
        t = "1" if t == "true" else "0" if t == "false" else t
        return next((v for v, _ in c["options"] if str(v).lower() == t), c["options"][0][0])
    try:
        v = float(raw)
    except (TypeError, ValueError):
        v = float(c["min"])
    return int(v) if float(c["step"]).is_integer() and v.is_integer() else v


def _num(v, st):
    return int(v) if float(st).is_integer() and float(v).is_integer() else v


def _grid(c, cur):
    if c["kind"] == "enum":
        return [v for v, _ in c["options"]]
    lo, hi, st = float(c["min"]), float(c["max"]), float(c["step"])
    vals = {round(round(v / st) * st, 6) for v in np.linspace(lo, hi, min(int(round((hi - lo) / st)) + 1, 11))}
    vals.add(float(cur))
    return [_num(v, st) for v in sorted(v for v in vals if lo - 1e-9 <= v <= hi + 1e-9 or v == float(cur))]


def _guard_ok(s, base, guard):
    """no more risk than the original: at most 25% more drawdown, a worst loss at most 25% bigger, at least a third of the
    trades, and each half of the data profitable if it was (never worse if it wasn't)"""
    if not s:
        return False
    if not guard:
        return True
    halves = all((s[h] > 0) if base[h] > 0 else (s[h] >= base[h]) for h in ("train", "test"))
    return (halves and s["n"] >= max(10, base["n"] / 3) and s["dd"] <= 1.25 * max(base["dd"], 1)
            and s["worst"] >= 1.25 * min(base["worst"], -1))


class _Auto:
    """one tuning job: the runs it made (cached) and the original settings' stats"""
    def __init__(self, inputs, ds, mode, guard, pool, job_id):
        import dexlab
        import exitlab
        self.inputs, self.ds, self.chart, self.guard, self.pool, self.id = inputs, ds, mode == "chart", guard, pool, job_id
        self.window = exitlab.window_of(ds, inputs)[0]
        self.stats_of = dexlab.stats
        self.cache = {}
        self.base = self.run({})

    def run(self, over):
        k = tuple(sorted((n, str(v)) for n, v in over.items()))
        if k not in self.cache:
            tr = sim.simulate(dict(self.inputs, **{n: _sv(v) for n, v in over.items()}), ds=self.ds, chart=self.chart)[0]
            s = self.stats_of(tr, self.window)
            if s:
                s.pop("eq", None)
            self.cache[k] = s
        return self.cache[k]

    def live(self):
        return AUTO["id"] == self.id and not AUTO["stop"]

    def ok(self, s):
        return _guard_ok(s, self.base, self.guard)

    def sweep(self, over, name, vals):
        res = list(self.pool.map(lambda v: self.run({**over, name: v}), vals))
        with AUTO_LOCK:
            if AUTO["id"] == self.id:
                AUTO["done"] += len(vals)
        return res

    def group(self, ctrls, start):
        """tune one box from `start` (its current values); returns the best values, stats and each setting's curve"""
        orig = {c["name"]: _cur_value(c, self.inputs) for c in ctrls}
        best_v = {**orig, **{k: v for k, v in start.items() if k in orig}}
        best = self.run(best_v)
        best_sc = best["net"] if self.ok(best) else -1e18
        curves = {}
        for _ in range(2 if len(ctrls) > 1 else 1):
            for c in ctrls:
                if not self.live():
                    break
                vals = _grid(c, best_v[c["name"]])
                res = self.sweep(best_v, c["name"], vals)
                curves[c["name"]] = [{"v": v, "net": r["net"] if r else None, "ok": self.ok(r)} for v, r in zip(vals, res)]
                for v, r in zip(vals, res):
                    if self.ok(r) and r["net"] > best_sc:
                        best_sc, best, best_v = r["net"], r, {**best_v, c["name"]: v}
        for c in ctrls:                                           # a finer look either side of the winner
            if c["kind"] != "num" or not self.live():
                continue
            st, cv = float(c["step"]), float(best_v[c["name"]])
            vals = [_num(v, st) for v in sorted({round(min(float(c["max"]), max(float(c["min"]), cv + k * st)), 6)
                                                for k in (-2, -1, 1, 2)} - {cv})]
            for v, r in zip(vals, self.sweep(best_v, c["name"], vals)):
                if self.ok(r) and r["net"] > best_sc:
                    best_sc, best, best_v = r["net"], r, {**best_v, c["name"]: v}
        changed = {k: v for k, v in best_v.items() if str(v) != str(orig[k])}
        return {"values": best_v, "changed": changed, "stats": best, "found": bool(changed) and best_sc > -1e17,
                "curves": curves, "names": [c["name"] for c in ctrls]}

    def stack(self, groups):
        """the best combination: add the box winner that helps most, again and again, while net improves (guard held)"""
        cur, used, over = self.base, [], {}
        cur_sc = cur["net"] if self.ok(cur) else -1e18
        while self.live():
            cands = [g for g, r in groups.items() if r["found"] and g not in used]
            if not cands:
                break
            trial = {g: self.run({**over, **groups[g]["changed"]}) for g in cands}
            with AUTO_LOCK:
                AUTO["done"] += len(cands)
            good = {g: s for g, s in trial.items() if self.ok(s) and s["net"] > cur_sc}
            if not good:
                break
            g = max(good, key=lambda z: good[z]["net"])
            used.append(g); over.update(groups[g]["changed"]); cur = good[g]; cur_sc = cur["net"]
            AUTO["phase"] = f"best combination: + {g}"
        return {"groups": used, "over": over, "stats": cur}


def _estimate(ctrls):
    one = sum(len(_grid(c, _cur_value(c, {}))) for c in ctrls)
    return one * (2 if len(ctrls) > 1 else 1) + 4 * sum(1 for c in ctrls if c["kind"] == "num")


def auto_start(inputs, ds="year1", mode="ea", group=None, start=None, guard=True):
    """group = one box's name -> tune that box (from `start`, its values on screen); group None -> tune every box from the
    original settings, then the best combination"""
    exit_mode = int(float(inputs.get("InpExitMode", 0)))
    ctrls = controls_for(exit_mode)
    groups = list(dict.fromkeys(c["group"] for c in ctrls))
    if group is not None and group not in groups:
        return {"ok": False, "error": f"Unknown box: {group}"}
    todo = [group] if group is not None else groups
    with AUTO_LOCK:
        if AUTO["running"] or TUNE.get("running") or PROG["running"]:
            return {"ok": False, "busy": True, "error": "Another tune or scan is running - wait for it or press Stop"}
        job_id = AUTO["id"] + 1
        AUTO.update(id=job_id, running=True, kind="group" if group is not None else "all", done=0,
                    total=sum(_estimate([c for c in ctrls if c["group"] == g]) for g in todo) + (0 if group else len(todo) * 3),
                    phase="the original settings", groups={}, stack=None, base=None, error=None, started=time.time(),
                    stop=False, exit_mode=exit_mode, ds=ds, guard=bool(guard), todo=todo)

    def go():
        try:
            with ThreadPoolExecutor(max_workers=5) as pool:
                job = _Auto(dict(inputs), ds, mode, bool(guard), pool, job_id)
                AUTO["base"] = job.base
                for g in todo:
                    if not job.live():
                        break
                    AUTO["phase"] = g
                    AUTO["groups"][g] = job.group([c for c in ctrls if c["group"] == g], (start or {}) if group is not None else {})
                if group is None and job.live():
                    AUTO["phase"] = "best combination"
                    AUTO["stack"] = job.stack(AUTO["groups"])
            AUTO["phase"] = "stopped" if AUTO["stop"] else "done"
        except Exception as ex:                                   # noqa: BLE001 - shown on the page
            import traceback
            traceback.print_exc()
            AUTO["error"] = f"{type(ex).__name__}: {ex}"
            AUTO["phase"] = "failed"
        finally:
            with AUTO_LOCK:
                if AUTO["id"] == job_id:
                    AUTO["running"] = False
    threading.Thread(target=go, daemon=True).start()
    return {"ok": True, "id": job_id}


def auto_progress():
    with AUTO_LOCK:
        p = dict(AUTO)
    p["seconds"] = round(time.time() - p["started"], 1) if p["started"] else 0
    return p


def auto_stop():
    AUTO["stop"] = True
    return {"ok": True}
