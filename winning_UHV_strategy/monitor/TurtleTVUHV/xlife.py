"""xlife.py - the EXTENDED Trade Lifecycle (Zee 2026-10-27: "a complete tree with all the possible options we have ... turn on and off all
the diff kinds of exits ... prune and select the best exits out of all possible ones, the best targets, the best modes").

Every exit the tester AND the EA both run (so whatever is found here can go straight to MT5's Strategy Tester), as a catalog of modules:
  family  -> module -> off + presets (each preset = a set of EA inputs).
A "draft" = the exit mode + one choice per module, on top of the settings on the chart. The page toggles modules and the tester re-runs.
Two background jobs:
  impacts  - for the draft: what switching each module off costs, or what its best preset would add, and every other mode / stop.
  optimise - per exit mode: start bare (no optional exits), add the module / preset that helps most, swap presets, drop what stops paying,
             until nothing improves (the guard: no more risk than the live setting). Rankings of every target, cutter, protector...
Tester hypotheses only - MT5 decides (CLAUDE.md)."""
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import dexlab
import exitlab
import sim

WHY = exitlab.WHY
FAMILIES = [
    ("mode", "Exit mode", "The core rule that ends a trade: the backbone every other exit hangs on."),
    ("stop", "Initial stop", "Where the trade is proven wrong. Always on: it is the hard limit on a loss."),
    ("targets", "Targets", "Where profit is taken."),
    ("protect", "Profit protection", "Once a trade is in profit: bank part of it, or move the stop so it cannot turn into a loss."),
    ("cut", "Loss cutters", "Close a failing trade before it reaches the full stop."),
    ("time", "Time & regime", "Close a trade because of the clock or the market's state, not the price."),
    ("mode0", "v1.23 exits (mode 0)", "Exit mode 0's own management: breakeven, partial at TP1 and the trail."),
]


def _v(i, label, sets):
    return {"id": i, "label": label, "sets": {k: str(v) for k, v in sets.items()}}


def catalog(bar_min):
    """the modules; time presets are given in minutes and turned into candles of this data (1-min data: 1 candle = 1 minute)"""
    b = lambda m: max(1, int(round(m / bar_min)))                       # noqa: E731
    hm = lambda m: f"{m // 60} h" if m >= 60 and m % 60 == 0 else f"{m} min"    # noqa: E731
    M = []
    M.append({"key": "mode", "family": "mode", "name": "Exit mode", "choice": True, "modes": [0, 1, 2], "reasons": [],
              "def": "0: the v1.23 exits (EMA / support target, partial, breakeven, trail). 1: close at the next EMA beyond the entry. "
                     "2: no target - out when a completed candle closes back across the slow EMA.",
              "off": None, "variants": [_v("m0", "0 · v1.23 exits", {"InpExitMode": 0}), _v("m1", "1 · next EMA beyond the entry", {"InpExitMode": 1}),
                                        _v("m2", "2 · close back across the slow EMA", {"InpExitMode": 2})]})
    M.append({"key": "stop", "family": "stop", "name": "Initial stop", "choice": True, "modes": [0, 1, 2], "reasons": [1],
              "def": "The first stop-loss. 'R' everywhere else = the distance from the entry to this stop.", "off": None,
              "variants": [_v(f"usd{x}", f"${x} from the entry", {"InpSlMode": 2, "InpSlUsd": x}) for x in (10, 15, 20, 25, 35, 50)]
              + [_v(f"atr{x}", f"{x} x ATR from the entry", {"InpSlMode": 1, "InpSlAtrMult": x}) for x in (1, 1.5, 2, 3)]
              + [_v(f"pip{x}", f"{x} pips beyond the setup candle", {"InpSlMode": 0, "InpSlPips": x}) for x in (20, 50, 95)]})
    M.append({"key": "target", "family": "targets", "name": "Lab target", "modes": [1, 2], "reasons": [9],
              "def": "A fixed target set at the entry. Touch it and the whole trade closes at once, mid-candle. Only ever fires in profit.",
              "off": {"InpXTgt": "0"}, "off_label": "off · the mode's own target",
              "variants": [_v("none", "none at all (stop / trail / time decide)", {"InpXTgt": 1})]
              + [_v(f"r{x}", f"{x} R", {"InpXTgt": 2, "InpXTgtK": x}) for x in (0.5, 1, 1.5, 2, 3)]
              + [_v(f"a{x}", f"{x} x ATR", {"InpXTgt": 3, "InpXTgtK": x}) for x in (0.5, 1, 2, 3)]
              + [_v(f"d{x}", f"${x}", {"InpXTgt": 4, "InpXTgtK": x}) for x in (5, 10, 15, 20, 26, 35, 50, 80)]})
    M.append({"key": "fixtp", "family": "targets", "name": "Broker take-profit", "modes": [0, 1, 2], "reasons": [5],
              "def": "A take-profit order sent to the broker with the trade, in pips (1 pip = $0.10). Works in every exit mode.",
              "off": {"InpFixTpPips": "0"}, "variants": [_v(f"p{x}", f"{x} pips (${x / 10:g})", {"InpFixTpPips": x}) for x in (10, 20, 30, 50, 80, 150)]})
    M.append({"key": "fallback", "family": "targets", "name": "No-EMA fallback", "choice": True, "modes": [1], "reasons": [3],
              "def": "Mode 1 only: when no EMA lies beyond the entry there is no target - this decides when such a trade closes.",
              "off": None, "variants": [_v("fast", "close back across the fast EMA (the EA's)", {"InpXFb": 0}),
                                        _v("slow", "close back across the slow EMA", {"InpXFb": 1}),
                                        _v("none", "nothing: other rules decide", {"InpXFb": 2})]})
    M.append({"key": "partial", "family": "protect", "name": "Partial close", "modes": [1, 2], "reasons": [11],
              "def": "Close part of the trade at +R and bank it; the rest runs on the other exits.",
              "off": {"InpXP1R": "0", "InpXP2R": "0"},
              "variants": [_v(f"p{r}_{f}", f"{int(f * 100)}% at +{r} R", {"InpXP1R": r, "InpXP1Frac": f, "InpXP1Be": "false", "InpXP2R": 0})
                           for r, f in ((0.5, 0.5), (1, 0.5), (1.5, 0.5), (2, 0.5), (1, 0.25), (1, 0.75))]
              + [_v("p1be", "50% at +1 R, then the stop to breakeven", {"InpXP1R": 1, "InpXP1Frac": 0.5, "InpXP1Be": "true", "InpXP2R": 0}),
                 _v("p12", "50% at +1 R and 25% at +2 R", {"InpXP1R": 1, "InpXP1Frac": 0.5, "InpXP1Be": "false", "InpXP2R": 2, "InpXP2Frac": 0.25})]})
    M.append({"key": "be", "family": "protect", "name": "Breakeven", "modes": [1, 2], "reasons": [7],
              "def": "Once the trade has been +R in profit, its stop moves to the entry: a winner that turns round costs nothing.",
              "off": {"InpXBeR": "0"},
              "variants": [_v(f"b{x}", f"at +{x} R", {"InpXBeR": x, "InpXBeOff": 0}) for x in (0.5, 1, 1.5, 2)]
              + [_v("b1o", "at +1 R, stop at entry + 0.25 R", {"InpXBeR": 1, "InpXBeOff": 0.25})]})
    M.append({"key": "lock", "family": "protect", "name": "Profit lock ladder", "modes": [1, 2], "reasons": [],
              "def": "Every R the trade gains, the stop climbs one R behind it: profit is locked in steps.",
              "off": {"InpXLockR": "0"}, "variants": [_v(f"l{x}", f"every {x} R", {"InpXLockR": x}) for x in (0.5, 1, 1.5, 2)]})
    M.append({"key": "trail", "family": "protect", "name": "Trailing stop", "modes": [1, 2], "reasons": [6],
              "def": "The stop follows the price, only ever towards profit: lets winners run, gives back a slice when they turn.",
              "off": {"InpXTr": "0"},
              "variants": [_v(f"t1_{x}", f"${x} behind the best price", {"InpXTr": 1, "InpXTrK": x, "InpXTrAct": 0, "InpXTrBuf": 0}) for x in (3, 5, 10, 20)]
              + [_v(f"t2_{x}", f"{x} x ATR behind the best", {"InpXTr": 2, "InpXTrK": x, "InpXTrAct": 0, "InpXTrBuf": 0}) for x in (1, 2, 3)]
              + [_v("t2_2a1", "2 x ATR, starting at +1 R", {"InpXTr": 2, "InpXTrK": 2, "InpXTrAct": 1, "InpXTrBuf": 0})]
              + [_v(f"t3_{x}", f"keep {x}% of the best profit", {"InpXTr": 3, "InpXTrK": x, "InpXTrAct": 0.5, "InpXTrBuf": 0}) for x in (50, 70)]
              + [_v("t4", "the fast EMA", {"InpXTr": 4, "InpXTrAct": 0, "InpXTrBuf": 0}), _v("t5", "the slow EMA", {"InpXTr": 5, "InpXTrAct": 0, "InpXTrBuf": 0}),
                 _v("t6", "the previous candle's low / high", {"InpXTr": 6, "InpXTrAct": 0, "InpXTrBuf": 0}),
                 _v("t7", "the 5-candle low / high", {"InpXTr": 7, "InpXTrK": 5, "InpXTrAct": 0, "InpXTrBuf": 0}),
                 _v("t8", "the last swing low / high", {"InpXTr": 8, "InpXTrAct": 0, "InpXTrBuf": 0})]})
    cx = lambda c, n=1, w=0: {"InpXCx": c, "InpXCxBuf": 0, "InpXCxN": n, "InpXCxWhen": w, "InpXCxAfter": 0}      # noqa: E731
    M.append({"key": "cx", "family": "cut", "name": "Close-based exit", "modes": [1, 2], "reasons": [12],
              "def": "At each completed candle: close when it confirms the chosen signal against the trade.",
              "off": {"InpXCx": "0"},
              "variants": [_v("c1", "close across the fast EMA", cx(1)), _v("c1l", "close across the fast EMA, only in loss", cx(1, 1, 2)),
                           _v("c2", "close across the slow EMA", cx(2)), _v("c2l", "close across the slow EMA, only in loss", cx(2, 1, 2)),
                           _v("c3", "the EMAs cross against", cx(3)), _v("c4", "an opposite signal candle", cx(4)),
                           _v("c5", "an engulfing candle against", cx(5)), _v("c6", "3 candles in a row against", cx(6, 3))]})
    M.append({"key": "lcap", "family": "cut", "name": "Loss cap", "modes": [1, 2], "reasons": [],
              "def": "Keeps the stop the rules chose, but never further than $X from the entry: only the widest stops are cut.",
              "off": {"InpXLossCap": "0"}, "variants": [_v(f"c{x}", f"never more than ${x}", {"InpXLossCap": x}) for x in (5, 8, 12, 16, 20, 30, 40)]})
    M.append({"key": "lp", "family": "cut", "name": "Partial loss cut", "modes": [1, 2], "reasons": [17],
              "def": "When the trade is R in loss, part of it is closed: the full stop then costs less.",
              "off": {"InpXLpR": "0"},
              "variants": [_v(f"lp{r}_{f}", f"cut {int(f * 100)}% at −{r} R", {"InpXLpR": r, "InpXLpFrac": f}) for r, f in ((0.3, 0.5), (0.5, 0.5), (0.75, 0.5), (0.5, 0.25))]})
    M.append({"key": "decay", "family": "cut", "name": "Decay stop", "modes": [1, 2], "reasons": [16],
              "def": "A trade still open after a while has its stop pulled towards the entry: the slow losers pay less.",
              "off": {"InpXDecayBars": "0"},
              "variants": [_v(f"d{m}_{r}", f"after {hm(m)} to {'entry' if r == 0 else f'{r} R'}", {"InpXDecayBars": b(m), "InpXDecayR": r})
                           for m, r in ((30, -0.5), (60, -0.5), (60, 0), (120, -0.5), (240, 0), (480, 0))]})
    M.append({"key": "time", "family": "time", "name": "Time stop", "modes": [1, 2], "reasons": [8],
              "def": "A trade still open after N minutes closes at the market.",
              "off": {"InpXMaxBars": "0"}, "variants": [_v(f"t{m}", f"after {hm(m)}", {"InpXMaxBars": b(m)}) for m in (15, 30, 60, 120, 240, 480, 1440)]})
    M.append({"key": "stale", "family": "time", "name": "No-progress exit", "modes": [1, 2], "reasons": [13],
              "def": "After N minutes, a trade that has not made at least +R is closed as dead.",
              "off": {"InpXStaleBars": "0"},
              "variants": [_v(f"s{m}_{r}", f"after {hm(m)}, less than +{r} R", {"InpXStaleBars": b(m), "InpXStaleR": r})
                           for m, r in ((15, 0.25), (30, 0.5), (60, 0.5), (120, 0.5), (60, 0))]})
    M.append({"key": "adx", "family": "time", "name": "ADX fade", "modes": [1, 2], "reasons": [14],
              "def": "Close when the trend strength (ADX) falls below a level: the move has died.",
              "off": {"InpXAdxExit": "0"}, "variants": [_v(f"a{x}", f"ADX below {x}", {"InpXAdxExit": x}) for x in (15, 20, 25, 30)]})
    M.append({"key": "fri", "family": "time", "name": "Friday close", "modes": [1, 2], "reasons": [15],
              "def": "Out on Friday at this server hour, before the weekend gap. Can be a big win OR a big loss.",
              "off": {"InpXFriHour": "0"}, "variants": [_v(f"f{x}", f"Friday {x}:00", {"InpXFriHour": x}) for x in (12, 16, 20, 22)]})
    M.append({"key": "m0be", "family": "mode0", "name": "Breakeven (share to TP)", "modes": [0], "reasons": [7],
              "def": "Mode 0: the stop to the entry once price covered this share of the way to the target.",
              "off": {"InpBeTpPct": "0"}, "variants": [_v(f"b{x}", f"at {int(x * 100)}% of the way", {"InpBeTpPct": x}) for x in (0.5, 0.75, 0.9)]})
    M.append({"key": "m0beusd", "family": "mode0", "name": "Breakeven ($ moved)", "modes": [0], "reasons": [],
              "def": "Mode 0: the stop to the entry once price moved $X the right way.",
              "off": {"InpBeUsd": "0"}, "variants": [_v(f"u{x}", f"after ${x}", {"InpBeUsd": x}) for x in (1, 2, 3, 5)]})
    M.append({"key": "m0part", "family": "mode0", "name": "Partial at TP1", "modes": [0], "reasons": [],
              "def": "Mode 0: close this share of the position at the first target.",
              "off": {"InpPartialPct": "0"}, "variants": [_v(f"p{x}", f"{int(x * 100)}% at TP1", {"InpPartialPct": x}) for x in (0.25, 0.5, 0.75)]})
    M.append({"key": "m0trail", "family": "mode0", "name": "Trail (v1.23)", "modes": [0], "reasons": [6],
              "def": "Mode 0: the trailing stop after the first target.",
              "off": {"InpTrail": "false"}, "variants": [_v("atr", "ATR behind the best", {"InpTrail": "true", "InpTrailMode": 2}),
                                                         _v("pips", "pips behind the best", {"InpTrail": "true", "InpTrailMode": 1}),
                                                         _v("ncandle", "low / high of the last N candles", {"InpTrail": "true", "InpTrailMode": 0})]})
    return M


def _eq(a, b):
    sa, sb = str(a).strip().lower(), str(b).strip().lower()
    if sa == sb:
        return True
    try:
        return abs(float(sa) - float(sb)) < 1e-9
    except ValueError:
        return False


def _keys(m):
    ks = set((m["off"] or {}).keys())
    for v in m["variants"]:
        ks |= set(v["sets"])
    return sorted(ks)


def _bar_min(ds):
    t = np.asarray(sim.data(ds)["t15"][:200])
    return max(1, int(np.min(np.diff(t))) // 60) if len(t) > 1 else 15


def spec(inputs, ds):
    """the catalog + the draft that matches the settings on the chart (a 'cur' preset when the chart's values match none)"""
    M = catalog(_bar_min(ds))
    sel = {}
    for m in M:
        cur = {k: str(inputs.get(k, "")) for k in _keys(m)}
        if m["off"] is not None and all(_eq(cur.get(k), v) for k, v in m["off"].items()):
            sel[m["key"]] = "off"
            continue
        hit = next((v["id"] for v in m["variants"] if all(_eq(cur.get(k), x) for k, x in v["sets"].items())), None)
        if hit is None:
            label = ", ".join(f"{k.replace('Inp', '')}={cur[k]}" for k in cur if cur[k] != "")
            m["variants"].insert(0, {"id": "cur", "label": "as on the chart: " + label, "sets": {k: v for k, v in cur.items() if v != ""}})
            hit = "cur"
        sel[m["key"]] = hit
    return {"modules": M, "families": [{"key": k, "name": n, "text": t} for k, n, t in FAMILIES], "sel": sel,
            "mode": int(float(inputs.get("InpExitMode", 1))), "bar_min": _bar_min(ds)}


def overrides(M, sel):
    """the draft -> EA inputs (every module's chosen preset, or its off values)"""
    out = {}
    for m in M:
        s = sel.get(m["key"])
        if s == "off" and m["off"] is not None:
            out.update(m["off"])
        else:
            v = next((v for v in m["variants"] if v["id"] == s), None)
            if v is not None:
                out.update(v["sets"])
    return out


def mode_of(sel):
    return {"m0": 0, "m1": 1, "m2": 2}.get(sel.get("mode"), 1)


def applies(m, mode):
    return mode in m["modes"]


# ---------------------------------------------------------------- running (cached)
_CACHE = {}
_CL = threading.Lock()


def _small(s):
    if not s:
        return None
    return {k: s[k] for k in ("n", "net", "wr", "pf", "avg_win", "avg_loss", "worst", "dd", "net_dd", "train", "test", "streak")}


def run(inputs, ds, chart, over, window):
    ih = hashlib.md5(json.dumps([inputs, ds, chart], sort_keys=True).encode()).hexdigest()
    k = ih + json.dumps(over, sort_keys=True)
    with _CL:
        if k in _CACHE:
            return _CACHE[k]
    rows = [x for x in sim.simulate(dict(inputs, **over), ds=ds, chart=chart)[0] if x[10] == 0]
    st = _small(dexlab.stats(rows, window)) if rows else None
    why = {}
    for x in rows:
        d = why.setdefault(int(x[13]), [0, 0.0, 0])
        d[0] += 1; d[1] += float(x[6]); d[2] += 1 if x[6] > 0 else 0
    out = {"stats": st, "why": {str(r): {"n": v[0], "net": round(v[1]), "wr": round(100.0 * v[2] / v[0], 1)} for r, v in why.items()}}
    with _CL:
        if len(_CACHE) > 6000:
            _CACHE.clear()
        _CACHE[k] = out
    return out


def _ctx(inputs, ds, mode):
    return dict(inputs), ds, mode == "chart", exitlab.window_of(ds, inputs)[0]


def attribute(M, sel, why):
    """which module closed how many trades: each exit reason goes to the module that owns it (the mode card takes the rest)"""
    mode = mode_of(sel)
    owners = {}
    for m in M:
        if m["key"] == "mode" or not applies(m, mode):
            continue
        if m["off"] is not None and sel.get(m["key"]) == "off":
            continue
        for r in m["reasons"]:
            owners.setdefault(r, m["key"])
    if sel.get("trail") not in (None, "off") and mode in (1, 2):
        owners[6] = "trail"
    elif sel.get("lock") not in (None, "off") and mode in (1, 2):
        owners[6] = "lock"
    res = {}
    for r, d in why.items():
        k = owners.get(int(r), "mode")
        g = res.setdefault(k, {"n": 0, "net": 0, "reasons": []})
        g["n"] += d["n"]; g["net"] += d["net"]; g["reasons"].append({"r": int(r), "why": WHY.get(int(r), r), **d})
    return res


def evaluate(inputs, ds, mode, sel):
    inp, ds, chart, window = _ctx(inputs, ds, mode)
    M = spec(inputs, ds)["modules"]
    over = overrides(M, sel)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.map(lambda o: run(inp, ds, chart, o, window), [over, {}])
    return {"stats": a["stats"], "live": b["stats"], "why": a["why"], "by_module": attribute(M, sel, a["why"]), "over": over,
            "changed": {k: v for k, v in over.items() if not _eq(inputs.get(k, ""), v)}}


# ---------------------------------------------------------------- scoring and the guard
def score(s, objective):
    if not s:
        return -1e18
    if objective == "net_dd":
        return s["net_dd"] if s["net_dd"] is not None else -1e18
    if objective == "pf":
        return (s["pf"] or 0) + s["net"] / 1e9
    return s["net"]


def guard_ok(s, ref, guard):
    """no more risk than the live setting: at most 25% more drawdown, a worst loss at most 25% bigger, a third of its trades,
    and each half of the data profitable if it was (never worse if it wasn't)"""
    if not s:
        return False
    if not guard or not ref:
        return True
    halves = all((s[h] > 0) if ref[h] > 0 else (s[h] >= ref[h]) for h in ("train", "test"))
    return (halves and s["n"] >= max(10, ref["n"] / 3) and s["dd"] <= 1.25 * max(ref["dd"], 1)
            and s["worst"] >= 1.25 * min(ref["worst"], -1))


# ---------------------------------------------------------------- background jobs
JOB = {"id": 0, "running": False, "kind": "", "done": 0, "total": 0, "phase": "", "result": None, "error": None, "started": 0.0, "stop": False}
JL = threading.Lock()


def _alts(m, sel):
    """the choices a module could switch to from the draft: off (if it has one) and every other preset"""
    cur = sel.get(m["key"])
    out = []
    if m["off"] is not None and cur != "off":
        out.append("off")
    out += [v["id"] for v in m["variants"] if v["id"] != cur]
    return out


def _start(kind, fn):
    with JL:
        if JOB["running"] and JOB["kind"] == "optimise":
            return {"ok": False, "error": "The optimiser is running - wait for it or press Stop"}
        JOB["id"] += 1
        jid = JOB["id"]
        JOB.update(running=True, kind=kind, done=0, total=0, phase="starting", result=None, error=None, started=time.time(), stop=False)

    def go():
        try:
            res = fn(jid)
            if JOB["id"] == jid:
                JOB["result"] = res
                JOB["phase"] = "stopped" if JOB["stop"] else "done"
        except Exception as ex:                                      # noqa: BLE001 - shown on the page
            import traceback
            traceback.print_exc()
            if JOB["id"] == jid:
                JOB["error"] = f"{type(ex).__name__}: {ex}"
                JOB["phase"] = "failed"
        finally:
            if JOB["id"] == jid:
                JOB["running"] = False
    threading.Thread(target=go, daemon=True).start()
    return {"ok": True, "id": jid}


def _live(jid):
    return JOB["id"] == jid and not JOB["stop"]


def _tick(jid, n=1):
    with JL:
        if JOB["id"] == jid:
            JOB["done"] += n


def impacts_start(inputs, ds, mode, sel, objective="net", guard=True):
    """for the draft: every module switched off / to each preset, and every other mode, side by side"""
    inp, ds_, chart, window = _ctx(inputs, ds, mode)
    M = spec(inputs, ds)["modules"]
    sel = dict(sel)
    md = mode_of(sel)

    def fn(jid):
        ref = run(inp, ds_, chart, {}, window)["stats"]
        base = run(inp, ds_, chart, overrides(M, sel), window)["stats"]
        todo = [(m["key"], a) for m in M if applies(m, md) or m["key"] == "mode" for a in _alts(m, sel)]
        JOB["total"] = len(todo)
        res = {}
        with ThreadPoolExecutor(max_workers=5) as pool:
            def one(t):
                if not _live(jid):
                    return t, None
                s = run(inp, ds_, chart, overrides(M, {**sel, t[0]: t[1]}), window)["stats"]
                _tick(jid)
                JOB["phase"] = t[0]
                return t, s
            for (k, a), s in pool.map(one, todo):
                if s is None:
                    continue
                res.setdefault(k, {})[a] = {"stats": s, "ok": guard_ok(s, ref, guard), "d": s["net"] - (base["net"] if base else 0)}
        out = {}
        for k, alts in res.items():
            best = max((a for a in alts if alts[a]["ok"] and a != "off"), key=lambda a: score(alts[a]["stats"], objective), default=None)
            out[k] = {"alts": alts, "best": best, "off": alts.get("off")}
        return {"base": base, "ref": ref, "modules": out, "objective": objective, "guard": guard}
    return _start("impacts", fn)


def optimise_start(inputs, ds, mode, objective="net", guard=True, modes=(1, 2), seed_sel=None):
    """per exit mode: bare -> add / swap / drop modules greedily while the score improves (guard held); then rankings"""
    inp, ds_, chart, window = _ctx(inputs, ds, mode)
    sp = spec(inputs, ds)
    M = sp["modules"]
    live_sel = dict(seed_sel or sp["sel"])

    def fn(jid):
        ref = run(inp, ds_, chart, {}, window)["stats"]
        ev = lambda s_: run(inp, ds_, chart, overrides(M, s_), window)["stats"]          # noqa: E731
        ok = lambda st: guard_ok(st, ref, guard)                                          # noqa: E731
        sc = lambda st: score(st, objective) if ok(st) else -1e18                         # noqa: E731
        per_mode, rankings = {}, {}
        est = sum(sum(len(_alts(m, {})) + 1 for m in M if applies(m, md) and m["key"] != "mode") for md in modes)
        JOB["total"] = est * 4
        with ThreadPoolExecutor(max_workers=5) as pool:
            for md in modes:
                if not _live(jid):
                    break
                sel = {m["key"]: ("off" if m["off"] is not None else live_sel.get(m["key"])) for m in M}
                sel["mode"] = f"m{md}"
                if md == 1 and sel.get("fallback") in (None, "cur"):
                    sel["fallback"] = live_sel.get("fallback") or "fast"
                cur = ev(sel); cur_sc = sc(cur)
                bare = cur
                path = [{"step": "start bare", "label": f"mode {md}, no optional exits", "stats": cur}]
                first = None
                for rnd in range(10):
                    if not _live(jid):
                        break
                    JOB["phase"] = f"mode {md} · round {rnd + 1}"
                    cands = [(m["key"], a) for m in M if applies(m, md) and m["key"] != "mode" for a in _alts(m, sel)]
                    res = list(pool.map(lambda t: (t, ev({**sel, t[0]: t[1]})), cands))
                    _tick(jid, len(cands))
                    if first is None:
                        first = res
                    good = [(t, s) for t, s in res if sc(s) > -1e17]
                    if not good:
                        break
                    (k, a), s = max(good, key=lambda z: sc(z[1]))
                    if sc(s) <= cur_sc + max(1.0, abs(cur_sc) * 0.002):
                        break
                    m = next(x for x in M if x["key"] == k)
                    was = sel.get(k)
                    sel[k] = a
                    lab = "off" if a == "off" else next(v["label"] for v in m["variants"] if v["id"] == a)
                    act = "drop" if a == "off" else ("add" if was == "off" else "swap")
                    path.append({"step": act, "module": k, "name": m["name"], "label": lab, "stats": s, "d": s["net"] - cur["net"]})
                    cur, cur_sc = s, sc(s)
                per_mode[md] = {"sel": dict(sel), "stats": cur, "score": cur_sc if cur_sc > -1e17 else None, "path": path, "bare": bare,
                                "over": overrides(M, sel)}
                # rankings: every preset of every module, alone on the bare mode (what each one is worth by itself)
                rk = {}
                for (k, a), s in (first or []):
                    if a == "off" or not s:
                        continue
                    m = next(x for x in M if x["key"] == k)
                    rk.setdefault(m["family"], []).append({"module": k, "name": m["name"], "id": a, "label": next(v["label"] for v in m["variants"] if v["id"] == a),
                                                           "net": s["net"], "d": s["net"] - bare["net"] if bare else None, "wr": s["wr"], "worst": s["worst"],
                                                           "dd": s["dd"], "ok": ok(s)})
                for f in rk:
                    rk[f].sort(key=lambda z: -z["net"])
                rankings[md] = rk
        best = max((md for md in per_mode if per_mode[md]["score"] is not None), key=lambda md: per_mode[md]["score"], default=None)
        return {"ref": ref, "modes": per_mode, "best": best, "rankings": rankings, "objective": objective, "guard": guard}
    return _start("optimise", fn)


def job():
    with JL:
        p = dict(JOB)
    p["seconds"] = round(time.time() - p["started"], 1) if p["started"] else 0
    return p


def stop():
    JOB["stop"] = True
    return {"ok": True}
