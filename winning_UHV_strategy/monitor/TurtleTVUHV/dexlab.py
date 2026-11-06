"""dexlab.py - Dexter's Lab on the LIVE setting (Zee 2026-10-26): the setting on the chart is diagnosed, then every experiment
runs on it with the Turtle TV tester; sliders fine-tune an experiment, Autotune finds its best values, and the winners are
stacked into one "Dexter's pick". Every experiment changes only EA inputs that BOTH the tester and the EA read, so what is
applied is what MT5 later verifies. Tester numbers are hypotheses - MT5 decides (CLAUDE.md)."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import exitlab
import sim

# ---------------------------------------------------------------- the experiments
# param: name, label, min, max, step, default (a number, or "auto" = from the diagnosis), unit
# build(p, ctx) -> the EA inputs it changes; ctx = {"bar_min": minutes per chart candle, "ea": the live inputs}


def _bars(minutes, ctx):
    return str(max(1, int(round(float(minutes) / ctx["bar_min"]))))


def _risk(p):
    """B / C's risk slider: 0 must SET fixed lots - leaving InpRiskPct out let a risk-sized live setting compound through"""
    return {"InpRiskPct": f"{max(0.0, float(p.get('risk_pct', 0))):g}"}


EXPS = [
    {"key": "baseline", "letter": "0", "title": "Baseline", "family": "reference",
     "why": "The setting on the chart, unchanged. Every experiment is compared with this.", "params": [], "build": lambda p, c: {}},
    {"key": "risk", "letter": "A", "title": "Risk-based lot sizing", "family": "sizing",
     "why": "Each trade is sized so a stop-out costs a fixed % of equity. Same trades; the swings scale with the account instead of fixed lots. Profit and drawdown both grow with the %, so judge A by profit ÷ drawdown - with 'the most profit' Autotune simply picks the most risk.",
     "params": [["risk_pct", "Risk per trade (% of equity)", 0.1, 3, 0.05, 0.5, "%"]],
     "build": lambda p, c: {"InpRiskPct": f"{p['risk_pct']:g}"}},
    {"key": "candle_stop", "letter": "B", "title": "Stop behind the signal candle", "family": "stop",
     "why": "The stop sits just beyond the pin bar's low (buy) / high (sell): where the idea is proven wrong. Risk 0 = fixed lots (isolates the stop); above 0 = sized like Experiment A.",
     "params": [["buffer", "Buffer beyond the candle ($ of price)", 0, 20, 0.5, 0.5, "$"], ["risk_pct", "Risk per trade (%, 0 = fixed lots)", 0, 3, 0.05, 0, "%"]],
     "build": lambda p, c: {"InpSlMode": "0", "InpSlPips": str(int(round(p["buffer"] * 10))), **_risk(p)}},
    {"key": "atr_stop", "letter": "C", "title": "ATR stop", "family": "stop",
     "why": "Stop = ATR(14) of the last closed candle × multiple: wider in fast markets, tighter in quiet ones. Risk 0 = fixed lots; above 0 = sized like A.",
     "params": [["atr_mult", "ATR multiple", 0.3, 8, 0.1, 1.7, "×"], ["risk_pct", "Risk per trade (%, 0 = fixed lots)", 0, 3, 0.05, 0, "%"]],
     "build": lambda p, c: {"InpSlMode": "1", "InpSlAtrMult": f"{p['atr_mult']:g}", **_risk(p)}},
    {"key": "decay", "letter": "D", "title": "Stop decay on stalled trades", "family": "cut",
     "why": "A trade that is still open after N minutes has its stop pulled in towards the entry: the slow losers pay less.",
     "params": [["minutes", "Stop tightens after (minutes)", 5, 720, 5, "auto", "min"], ["decay_r", "…to the entry + this R", -1, 0.5, 0.05, -0.5, "R"]],
     "build": lambda p, c: {"InpXDecayBars": _bars(p["minutes"], c), "InpXDecayR": f"{p['decay_r']:g}"}},
    {"key": "tight_stop", "letter": "E", "title": "Tight stop", "family": "stop",
     "why": "A stop at the distance most winners never dip to. Losers are cut at a fraction of today's stop; the few winners that dip further are the price.",
     "params": [["stop_usd", "Stop ($ from the entry)", 1, 80, 0.5, "auto", "$"]],
     "build": lambda p, c: {"InpSlMode": "2", "InpSlUsd": f"{p['stop_usd']:g}"}},
    {"key": "time_stop", "letter": "F", "title": "Time stop", "family": "cut",
     "why": "A trade still open after N minutes closes at the market. When winners resolve fast and losers drag, the clock separates them.",
     "params": [["minutes", "Close after (minutes)", 5, 1440, 5, "auto", "min"]],
     "build": lambda p, c: {"InpXMaxBars": _bars(p["minutes"], c)}},
    {"key": "tight_time", "letter": "G", "title": "Tight stop + time stop", "family": "cut",
     "why": "E and F together: the stop catches the fast losers, the clock the slow ones.",
     "params": [["stop_usd", "Stop ($ from the entry)", 1, 80, 0.5, "auto", "$"], ["minutes", "Close after (minutes)", 5, 1440, 5, "auto", "min"]],
     "build": lambda p, c: {"InpSlMode": "2", "InpSlUsd": f"{p['stop_usd']:g}", "InpXMaxBars": _bars(p["minutes"], c)}},
    {"key": "loss_cap", "letter": "H", "title": "Loss cap", "family": "stop",
     "why": "Keeps the setting's own stop, but never further than $X from the entry: only the widest stops are cut.",
     "params": [["cap_usd", "Stop never further than ($)", 1, 80, 0.5, "auto", "$"]],
     "build": lambda p, c: {"InpXLossCap": f"{p['cap_usd']:g}"}},
    {"key": "one_pos", "letter": "I", "title": "Fewer open positions", "family": "exposure",
     "why": "Two positions open together can be stopped together: the worst day is two stops, not one. Fewer positions cap that.",
     "params": [["max_pos", "Positions open at once", 1, 3, 1, 1, ""]],
     "build": lambda p, c: {"InpMaxPos": str(int(p["max_pos"]))}},
    {"key": "breakeven", "letter": "J", "title": "Breakeven", "family": "protect",
     "why": "Once a trade has been +R in profit its stop moves to the entry: a winner that turns around costs nothing.",
     "params": [["be_r", "Breakeven at +R", 0.1, 5, 0.05, 1, "R"]],
     "build": lambda p, c: {"InpXBeR": f"{p['be_r']:g}"}},
    {"key": "partial", "letter": "K", "title": "Partial take-profit", "family": "protect",
     "why": "Part of the trade closes at +R and banks profit; the rest keeps running under the setting's own exit.",
     "params": [["p1_r", "Partial at +R", 0.1, 10, 0.05, 1, "R"], ["frac", "Share closed", 0.1, 0.9, 0.05, 0.5, ""]],
     "build": lambda p, c: {"InpXP1R": f"{p['p1_r']:g}", "InpXP1Frac": f"{p['frac']:g}"}},
    {"key": "stale", "letter": "L", "title": "No-progress exit", "family": "cut",
     "why": "After N minutes a trade that has not made at least +R is closed: dead trades are the ones that turn into full losses.",
     "params": [["minutes", "Check after (minutes)", 5, 1440, 5, "auto", "min"], ["stale_r", "Must have made at least (R)", 0, 2, 0.05, 0.5, "R"]],
     "build": lambda p, c: {"InpXStaleBars": _bars(p["minutes"], c), "InpXStaleR": f"{p['stale_r']:g}"}},
    {"key": "atr_ceiling", "letter": "M", "title": "Volatility ceiling", "family": "filter",
     "why": "No new trades while ATR is above $X: the biggest losses tend to come in the wildest candles.",
     "params": [["atr_max", "Skip when ATR is above ($)", 0.2, 60, 0.1, "auto", "$"]],
     "build": lambda p, c: {"InpAtrMaxUsd": f"{p['atr_max']:g}"}},
    {"key": "day_stop", "letter": "N", "title": "Daily loss stop", "family": "exposure",
     "why": "After losing $X in a day, no new trades until tomorrow: a bad day cannot become a disaster.",
     "params": [["day_loss", "Stop for the day after losing ($)", 250, 30000, 250, "auto", "$"]],
     "build": lambda p, c: {"InpDayLossUsd": f"{p['day_loss']:g}"}},
    {"key": "loss_cut", "letter": "O", "title": "Partial loss cut", "family": "cut",
     "why": "When a trade is R in loss, part of it is closed: the full stop then costs less.",
     "params": [["lp_r", "Cut when in loss by (R)", 0.1, 0.95, 0.05, 0.5, "R"], ["lp_frac", "Share cut", 0.1, 0.9, 0.05, 0.5, ""]],
     "build": lambda p, c: {"InpXLpR": f"{p['lp_r']:g}", "InpXLpFrac": f"{p['lp_frac']:g}"}},
    {"key": "cooldown", "letter": "P", "title": "Cool-down after a loss", "family": "filter",
     "why": "After a losing trade, no new setups for N minutes: losses cluster, and the next setup in the same mess often fails too.",
     "params": [["minutes", "Pause after a loss (minutes)", 5, 720, 5, "auto", "min"]],
     "build": lambda p, c: {"InpCoolBars": _bars(p["minutes"], c)}},
    {"key": "direction", "letter": "Q", "title": "One direction only", "family": "filter",
     "why": "Trades only buys or only sells. Worth it only if the weaker side loses in BOTH halves - otherwise it is curve-fitting.",
     "params": [["side", "Trade (1 = buys only, 2 = sells only)", 1, 2, 1, 1, ""]],
     "build": lambda p, c: {"InpBuys": "true", "InpSells": "false"} if int(p["side"]) == 1 else {"InpBuys": "false", "InpSells": "true"}},
]
EXP = {e["key"]: e for e in EXPS}
STOP_FAMILY = {"candle_stop", "atr_stop", "tight_stop", "tight_time"}       # set the stop type: only one of them in a stack


def spec():
    return [{k: v for k, v in e.items() if k != "build"} for e in EXPS]


# ---------------------------------------------------------------- running
_CACHE = {}
_DIAG_DEFAULTS = {}                                           # the last diagnosis' starting values, per live setting
_CLOCK = threading.Lock()


def _ctx(inputs, ds):
    t = np.asarray(sim.data(ds)["t15"][:200])
    bar = int(np.min(np.diff(t))) if len(t) > 1 else 900
    return {"bar_min": max(1, bar // 60), "ea": inputs}


def stats(tr, window):
    a0, a1, b0, b1 = window
    rows = [x for x in tr if x[10] == 0]
    if not rows:
        return None
    order = np.argsort([x[4] for x in rows])
    t = np.array([x[1] for x in rows]); p = np.array([x[6] for x in rows])
    po = p[order]; eq = np.cumsum(po); peak = np.maximum.accumulate(np.r_[0.0, eq])
    dd = float((peak - np.r_[0.0, eq]).max())
    streak = cur = 0
    for v in po:
        cur = cur + 1 if v <= 0 else 0; streak = max(streak, cur)
    w = p > 0; gl = -p[~w].sum()
    k = max(1, len(eq) // 90)
    tin, tout = np.array([x[1] for x in rows]), np.array([x[4] for x in rows])
    worst_pair = 0.0                                              # the worst loss of trades open at the same time
    idx = np.argsort(tin)
    for a in range(len(idx)):
        i = idx[a]
        for b in range(a + 1, min(a + 6, len(idx))):
            j = idx[b]
            if tin[j] < tout[i] and p[i] < 0 and p[j] < 0:
                worst_pair = min(worst_pair, p[i] + p[j])
    return {"n": int(len(p)), "net": round(float(p.sum())), "wr": round(100 * float(w.mean()), 1),
            "pf": round(float(p[w].sum() / gl), 2) if gl > 0 else None,
            "avg_win": round(float(p[w].mean())) if w.any() else 0, "avg_loss": round(float(p[~w].mean())) if (~w).any() else 0,
            "worst": round(float(p.min())), "worst_pair": round(worst_pair), "dd": round(dd), "streak": int(streak),
            "net_dd": round(float(p.sum()) / dd, 2) if dd > 0 else None,
            "train": round(float(p[(t >= a0) & (t < a1)].sum())), "test": round(float(p[(t >= b0) & (t < b1)].sum())),
            "eq": [round(float(v)) for v in eq[::k]]}


def run(inputs, ds, mode, key, params=None):
    """one experiment on the live setting -> its stats and the inputs it changed"""
    e = EXP[key]
    ctx = _ctx(inputs, ds)
    dd = _DIAG_DEFAULTS.get(json.dumps([inputs, ds, mode], sort_keys=True), {}).get(key, {})
    p = {x[0]: (float(x[5]) if x[5] != "auto" else float(dd.get(x[0], (float(x[2]) + float(x[3])) / 2))) for x in e["params"]}
    p.update({k: float(v) for k, v in (params or {}).items()})
    sets = e["build"](p, ctx) if e["params"] or key == "baseline" else {}
    ck = json.dumps([inputs, ds, mode, sets], sort_keys=True)
    with _CLOCK:
        if ck in _CACHE:
            return _CACHE[ck]
    window = exitlab.window_of(ds, inputs)[0]
    tr = sim.simulate(dict(inputs, **sets), ds=ds, chart=(mode == "chart"))[0]
    out = {"key": key, "params": p, "sets": sets, "stats": stats(tr, window)}
    with _CLOCK:
        if len(_CACHE) > 4000:
            _CACHE.clear()
        _CACHE[ck] = out
    return out


def run_sets(inputs, ds, mode, sets):
    window = exitlab.window_of(ds, inputs)[0]
    return stats(sim.simulate(dict(inputs, **sets), ds=ds, chart=(mode == "chart"))[0], window)


# ---------------------------------------------------------------- the diagnosis of the live setting
def diagnose(inputs, ds, mode):
    window, labels = exitlab.window_of(ds, inputs)
    tr = [x for x in sim.simulate(inputs, ds=ds, chart=(mode == "chart"))[0] if x[10] == 0]
    base = stats(tr, window) if tr else None
    if not tr:
        return {"base": None, "insights": ["This setting takes no trades on this data."], "defaults": {}, "labels": labels}
    D = sim.data(ds)
    t1, h1, l1 = np.asarray(D["t1"]), np.asarray(D["h1"]), np.asarray(D["l1"])
    t15, atr = np.asarray(D["t15"]), np.asarray(D["atr"])
    ctx = _ctx(inputs, ds)
    rows = []
    for x in tr:
        side, tin, en, tout, pnl = int(x[0]), float(x[1]), float(x[2]), float(x[4]), float(x[6])
        a = int(np.searchsorted(t1, tin - 59)); b = int(np.searchsorted(t1, tout, side="right"))
        hi, lo = (float(h1[a:b].max()), float(l1[a:b].min())) if b > a else (en, en)
        k = max(0, int(np.searchsorted(t15, tin, side="right")) - 2)
        rows.append({"win": pnl > 0, "pnl": pnl, "mins": (tout - tin) / 60.0, "hour": int((tin // 3600) % 24), "side": side,
                     "mae": max(0.0, (en - lo) if side > 0 else (hi - en)), "mfe": max(0.0, (hi - en) if side > 0 else (en - lo)),
                     "atr": float(atr[k]) if k < len(atr) else 0.0, "stop": abs(float(x[3]) - en) if x[3] else 0.0})
    W = [r for r in rows if r["win"]]; L = [r for r in rows if not r["win"]]
    q = lambda arr, pc: round(float(np.percentile(arr, pc)), 2) if len(arr) else 0.0      # noqa: E731
    wm, lm = [r["mins"] for r in W], [r["mins"] for r in L]
    wmae, lmae = [r["mae"] for r in W], [r["mae"] for r in L]
    atrs = [r["atr"] for r in rows if r["atr"] > 0]
    stops = [r["stop"] for r in rows if r["stop"] > 0]
    big = sorted(rows, key=lambda r: r["pnl"])[: max(3, len(rows) // 20)]
    by_hour = {}
    for r in rows:
        by_hour.setdefault(r["hour"], []).append(r["pnl"])
    hours = sorted(((h, round(sum(v)), len(v)) for h, v in by_hour.items()), key=lambda z: z[1])
    sides = {s: [r["pnl"] for r in rows if r["side"] == s] for s in (1, -1)}
    d = {
        "trades": len(rows), "wins": len(W), "losses": len(L),
        "avg_win": base["avg_win"], "avg_loss": base["avg_loss"],
        "ratio": round(abs(base["avg_loss"]) / base["avg_win"], 2) if base["avg_win"] else None,
        "breakeven_wr": round(100 * abs(base["avg_loss"]) / (abs(base["avg_loss"]) + base["avg_win"]), 1) if base["avg_win"] else None,
        "win_minutes": {"p50": q(wm, 50), "p90": q(wm, 90)}, "loss_minutes": {"p50": q(lm, 50), "p90": q(lm, 90)},
        "big_loss_minutes": q([r["mins"] for r in big], 50),
        "win_mae": {f"p{p}": q(wmae, p) for p in (50, 75, 90, 95, 98)}, "loss_mae": {f"p{p}": q(lmae, p) for p in (50, 90)},
        "win_mfe_p50": q([r["mfe"] for r in W], 50), "loss_mfe_p50": q([r["mfe"] for r in L], 50),
        "stop_p50": q(stops, 50), "atr": {"p10": q(atrs, 10), "p50": q(atrs, 50), "p90": q(atrs, 90), "p99": q(atrs, 99)},
        "big_loss_atr_p50": q([r["atr"] for r in big], 50),
        "worst_hours": hours[:3], "side": {"buys": [len(sides[1]), round(sum(sides[1]))], "sells": [len(sides[-1]), round(sum(sides[-1]))]},
        "bar_min": ctx["bar_min"],
    }
    # starting values for the experiments, from this setting's own trades
    win_p95_mins = max(ctx["bar_min"], d["win_minutes"]["p90"] * 1.5)
    defaults = {
        "tight_stop": {"stop_usd": max(1.0, round(d["win_mae"]["p95"] * 2) / 2)},
        "time_stop": {"minutes": int(max(ctx["bar_min"], round(win_p95_mins / 5) * 5))},
        "tight_time": {"stop_usd": max(1.0, round(d["win_mae"]["p95"] * 2) / 2), "minutes": int(max(ctx["bar_min"], round(win_p95_mins / 5) * 5))},
        "loss_cap": {"cap_usd": max(1.0, round(d["win_mae"]["p98"] * 2) / 2)},
        "decay": {"minutes": int(max(ctx["bar_min"], round(win_p95_mins / 5) * 5))},
        "stale": {"minutes": int(max(ctx["bar_min"], round(win_p95_mins / 5) * 5))},
        "cooldown": {"minutes": int(max(ctx["bar_min"], 4 * ctx["bar_min"]))},
        "atr_ceiling": {"atr_max": max(0.2, round(d["atr"]["p90"], 1))},
        "day_loss": {"day_loss": max(250, round(abs(base["avg_loss"]) * 2 / 250) * 250)},
        "day_stop": {"day_loss": max(250, round(abs(base["avg_loss"]) * 2 / 250) * 250)},
    }
    ins = []
    if d["ratio"]:
        if d["ratio"] >= 1:
            ins.append(f"One average loss (${abs(base['avg_loss']):,}) costs {d['ratio']}× an average win (${base['avg_win']:,}): this setting needs a "
                       f"{d['breakeven_wr']}% win rate to break even and runs at {base['wr']}% - a margin of {base['wr'] - d['breakeven_wr']:.1f} points. "
                       "A small target with a wide stop: cut the losers (E, F, G, H) rather than chase win rate.")
        else:
            ins.append(f"An average win (${base['avg_win']:,}) is {1 / d['ratio']:.1f}× an average loss (${abs(base['avg_loss']):,}): this setting breaks even at a "
                       f"{d['breakeven_wr']}% win rate and runs at {base['wr']}% (+{base['wr'] - d['breakeven_wr']:.1f} points). Its edge is the big winners - "
                       "experiments that take profit earlier (J, K) usually raise the win rate and lower the profit.")
    if d["win_minutes"]["p50"] and d["loss_minutes"]["p50"] > 2 * d["win_minutes"]["p50"]:
        ins.append(f"Winners close in a median {d['win_minutes']['p50']:g} min, losers in {d['loss_minutes']['p50']:g} min (the biggest losers {d['big_loss_minutes']:g}): "
                   "time separates them - the time stop (F), no-progress exit (L) and stop decay (D) should help.")
    if d["stop_p50"] and d["win_mae"]["p95"] < 0.6 * d["stop_p50"]:
        ins.append(f"95% of winners never dip more than ${d['win_mae']['p95']:g}, but the stop is ${d['stop_p50']:g} away: losers pay for room winners don't use - "
                   "try the tight stop (E), the loss cap (H) and G.")
    if base["worst_pair"] < base["worst"]:
        ins.append(f"Two losing trades were open together; the worst pair lost ${abs(base['worst_pair']):,} against ${abs(base['worst']):,} for the worst single trade - "
                   "fewer open positions (I) caps that.")
    if base["streak"] >= 6:
        ins.append(f"The deepest drawdown comes with a run of {base['streak']} losses in a row: a daily loss stop (N) and a cool-down (P) target the clusters.")
    if d["big_loss_atr_p50"] and d["atr"]["p50"] and d["big_loss_atr_p50"] > 1.3 * d["atr"]["p50"]:
        ins.append(f"The biggest losses came with ATR ${d['big_loss_atr_p50']:g} against ${d['atr']['p50']:g} for a typical trade: the volatility ceiling (M) is worth a look.")
    if base["train"] > 0 and base["test"] > 0 and min(base["train"], base["test"]) < 0.25 * max(base["train"], base["test"]):
        ins.append(f"Profit is lopsided between the halves ({labels[0]} ${base['train']:,} vs {labels[1]} ${base['test']:,}): judge every experiment on both, "
                   "not on the total.")
    if not ins:
        ins.append("No single weakness stands out; Autotune everything will test every lever.")
    _DIAG_DEFAULTS[json.dumps([inputs, ds, mode], sort_keys=True)] = defaults
    return {"base": base, "diag": d, "defaults": defaults, "insights": ins, "labels": labels}


# ---------------------------------------------------------------- autotune and the stack
def score(s, objective, base):
    if not s:
        return -1e18
    if objective == "net":
        return s["net"]
    if objective == "net_dd":
        return s["net_dd"] or -1e18
    if objective == "worst":
        return s["worst"] + s["net"] / 1e9
    if objective == "pf":
        return s["pf"] or -1e18
    if objective == "wr":
        return s["wr"] + s["net"] / 1e12
    return s["net"]


def ok(s, base, guard):
    """the guard: both halves profitable, at least a third of the baseline's trades, and no more risk - at most 25% more drawdown
    and a worst loss at most 25% bigger (without it, 'the most profit' just buys a bigger bet: 3% risk compounding)"""
    if not s:
        return False
    if not guard:
        return True
    return (s["train"] > 0 and s["test"] > 0 and s["n"] >= max(10, base["n"] / 3)
            and s["dd"] <= 1.25 * max(base["dd"], 1) and s["worst"] >= 1.25 * min(base["worst"], -1))


def _grid(par, cur):
    lo, hi, step = float(par[2]), float(par[3]), float(par[4])
    n = int(round((hi - lo) / step)) + 1
    vals = list(np.linspace(lo, hi, min(n, 11)))
    vals.append(float(cur))
    vals = sorted({round(round(v / step) * step, 6) for v in vals})
    return [v for v in vals if lo - 1e-9 <= v <= hi + 1e-9]


JOB = {"running": False, "kind": "", "done": 0, "total": 0, "phase": "", "result": None, "error": None, "started": 0.0}
JLOCK = threading.Lock()


def tune(inputs, ds, mode, key, params, objective, guard, base, pool):
    """coordinate search: each parameter swept on a grid (others held), the best kept, two passes; then a finer sweep round the best"""
    e = EXP[key]
    best_p = {x[0]: float(params.get(x[0], x[5] if x[5] != "auto" else (x[2] + x[3]) / 2)) for x in e["params"]}
    best = run(inputs, ds, mode, key, best_p)
    best_sc = score(best["stats"], objective, base) if ok(best["stats"], base, guard) else -1e18
    curves = {}
    for _pass in range(2 if len(e["params"]) > 1 else 1):
        for par in e["params"]:
            vals = _grid(par, best_p[par[0]])
            res = list(pool.map(lambda v: run(inputs, ds, mode, key, {**best_p, par[0]: v}), vals))
            JOB["done"] += len(vals)
            curves[par[0]] = [{"v": v, "net": r["stats"]["net"] if r["stats"] else None, "score": score(r["stats"], objective, base) if r["stats"] else None,
                               "ok": ok(r["stats"], base, guard)} for v, r in zip(vals, res)]
            for v, r in zip(vals, res):
                sc = score(r["stats"], objective, base) if ok(r["stats"], base, guard) else -1e18
                if sc > best_sc:
                    best_sc, best, best_p = sc, r, {**best_p, par[0]: v}
    for par in e["params"]:                                      # a finer look either side of the winner
        step = float(par[4]); c = best_p[par[0]]
        vals = sorted({round(min(float(par[3]), max(float(par[2]), c + k * step)), 6) for k in (-2, -1, 1, 2)} - {c})
        res = list(pool.map(lambda v: run(inputs, ds, mode, key, {**best_p, par[0]: v}), vals))
        JOB["done"] += len(vals)
        for v, r in zip(vals, res):
            sc = score(r["stats"], objective, base) if ok(r["stats"], base, guard) else -1e18
            if sc > best_sc:
                best_sc, best, best_p = sc, r, {**best_p, par[0]: v}
    return {"key": key, "params": best_p, "result": best, "score": best_sc if best_sc > -1e17 else None, "curves": curves,
            "found": best_sc > -1e17}


def stack(inputs, ds, mode, tuned, objective, guard, base):
    """Dexter's pick: add the tuned experiment that helps most, again and again, while the score improves (one stop type only)"""
    cur, used, sets = base, [], {}
    cur_sc = score(base, objective, base)
    while True:
        cands = [k for k, t in tuned.items() if t["found"] and k not in used and k != "baseline"
                 and not (k in STOP_FAMILY and any(u in STOP_FAMILY for u in used))]
        if not cands:
            break
        trial = {k: run_sets(inputs, ds, mode, {**sets, **tuned[k]["result"]["sets"]}) for k in cands}
        JOB["done"] += len(cands)
        good = {k: s for k, s in trial.items() if ok(s, base, guard)}
        if not good:
            break
        k = max(good, key=lambda z: score(good[z], objective, base))
        if score(good[k], objective, base) <= cur_sc:
            break
        used.append(k); sets.update(tuned[k]["result"]["sets"]); cur = good[k]; cur_sc = score(cur, objective, base)
        JOB["phase"] = f"Dexter's pick: + {EXP[k]['letter']} {EXP[k]['title']}"
    return {"used": used, "sets": sets, "stats": cur, "letters": [EXP[k]["letter"] for k in used]}


def _job(kind, fn):
    with JLOCK:
        if JOB["running"]:
            return {"error": "Dexter's Lab is already busy - wait for it or press Stop"}
        JOB.update(running=True, kind=kind, done=0, total=0, phase="starting", result=None, error=None, started=time.time(), stop=False)

    def go():
        try:
            JOB["result"] = fn()
            JOB["phase"] = "done"
        except Exception as ex:                                  # noqa: BLE001
            import traceback
            JOB["error"] = f"{type(ex).__name__}: {ex}"
            JOB["phase"] = "failed"
            traceback.print_exc()
        finally:
            JOB["running"] = False
    threading.Thread(target=go, daemon=True).start()
    return {"ok": True}


def start(body, full_inputs):
    inputs = full_inputs(body.get("inputs") or {})
    ds, mode = body.get("ds") or "year1", body.get("mode") or "ea"
    objective, guard = body.get("objective") or "net", bool(body.get("guard", True))
    params = body.get("params") or {}
    kind = body.get("kind") or "all"

    def all_runs():
        keys = [e["key"] for e in EXPS]
        JOB["total"] = len(keys)
        JOB["phase"] = "every experiment on the live setting"
        out = {}
        with ThreadPoolExecutor(max_workers=5) as pool:
            for k, r in zip(keys, pool.map(lambda k: run(inputs, ds, mode, k, params.get(k)), keys)):
                out[k] = r; JOB["done"] += 1
        return {"kind": "all", "runs": out}

    def tune_one():
        key = body["key"]
        base = run(inputs, ds, mode, "baseline")["stats"]
        n = sum(len(_grid(x, x[2])) for x in EXP[key]["params"]) * (2 if len(EXP[key]["params"]) > 1 else 1) + 4 * len(EXP[key]["params"])
        JOB["total"] = n; JOB["phase"] = f"autotuning {EXP[key]['letter']} · {EXP[key]['title']}"
        with ThreadPoolExecutor(max_workers=5) as pool:
            t = tune(inputs, ds, mode, key, params.get(key) or {}, objective, guard, base, pool)
        return {"kind": "tune", "tuned": {key: t}, "base": base}

    def tune_all():
        base = run(inputs, ds, mode, "baseline")["stats"]
        keys = [e["key"] for e in EXPS if e["params"]]
        JOB["total"] = sum(sum(len(_grid(x, x[2])) for x in EXP[k]["params"]) * (2 if len(EXP[k]["params"]) > 1 else 1) + 4 * len(EXP[k]["params"]) for k in keys) + 60
        tuned = {}
        with ThreadPoolExecutor(max_workers=5) as pool:
            for k in keys:
                if JOB.get("stop"):
                    break
                JOB["phase"] = f"autotuning {EXP[k]['letter']} · {EXP[k]['title']}"
                tuned[k] = tune(inputs, ds, mode, k, params.get(k) or {}, objective, guard, base, pool)
        JOB["phase"] = "Dexter's pick: stacking the experiments that help"
        pick = stack(inputs, ds, mode, tuned, objective, guard, base)
        return {"kind": "tune_all", "tuned": tuned, "base": base, "pick": pick, "objective": objective, "guard": guard}

    return _job(kind, {"all": all_runs, "tune": tune_one, "tune_all": tune_all}[kind])


def job_state():
    j = dict(JOB)
    j["seconds"] = round(time.time() - j["started"], 1) if j["started"] else 0
    return j


def stop():
    JOB["stop"] = True
    return {"ok": True}
