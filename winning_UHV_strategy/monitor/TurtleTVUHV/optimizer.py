"""optimizer.py - Zee 2026-10-20: "we toggle a setting in plus and minus 1 step. if it results in an improvement we further take steps until there's
no effect of that setting. we do this for all settings."

Coordinate descent on the Turtle TV Tester (sim.py, ~7 ms a year):
  for each setting: try one step up and one step down; while a step improves the score (by at least MIN_GAIN), keep stepping that way;
  then the next setting; repeat whole passes until a pass changes nothing.
Guards (the advisor, 2026-10-20): the score is measured on TRAIN (Jan - Jun) only; TEST (Jul - Oct) is reported beside every result but never
used to accept a step; the range boxes stay out unless asked for; the best result is checked in MT5 before anyone trusts it.
"Keep optimizing" restarts from shaken copies of the best (a few settings moved several steps) to look past the nearest hill."""
import random
import threading
import time
from datetime import datetime

import numpy as np

import sim

TRAIN_END = int((datetime(2026, 7, 1) - datetime(1970, 1, 1)).total_seconds())    # server time
MIN_GAIN = 0.01                                                                    # a step must improve the score by 1 %

# (input, kind, values): the settings sim.py implements, with their step grids
SPACE = [
    ("InpEmaFast", "int", (5, 40, 1)), ("InpEmaSlow", "int", (14, 120, 2)),
    ("InpWickMin", "num", (0.20, 0.80, 0.05)), ("InpBodyMax", "num", (0.20, 0.80, 0.05)), ("InpNoseMax", "num", (0.05, 0.50, 0.05)),
    ("InpMaruBody", "num", (0.30, 0.90, 0.05)), ("InpHamRatio", "num", (1.5, 4.0, 0.25)), ("InpHamNose", "num", (0.20, 0.80, 0.05)),
    ("InpMinRangeAtr", "num", (0.0, 1.5, 0.05)), ("InpTouchPips", "num", (0.0, 5.0, 0.5)), ("InpTouchMode", "enum", (0, 1)),
    ("InpLongRule", "enum", (0, 1, 2)), ("InpShortLine", "enum", (0, 1, 2)),
    ("InpUsePin", "bool", None), ("InpMarubozu", "bool", None), ("InpHammer", "bool", None), ("InpStar", "bool", None),
    ("InpBreakBars", "int", (1, 3, 1)), ("InpBreakPips", "num", (0.0, 8.0, 0.5)),
    ("InpSlAtrMult", "num", (0.8, 3.0, 0.1)), ("InpMaxRiskUsd", "int", (8, 40, 1)),
    ("InpAdxMin", "int", (0, 45, 1)), ("InpSessFrom", "int", (0, 12, 1)), ("InpSessTo", "int", (14, 24, 1)),
    ("InpRangeLook", "int", (3, 20, 1)), ("InpRangeLookS", "int", (3, 20, 1)),
    ("InpExitMode", "enum", (1, 2)), ("InpBandOff", "enum", (0, 1)),
]
RISK_SPACE = {
    "stop": [
        ("InpMaxRiskUsd", "enum", (0, 5, 10, 15, 20, 25, 30)),
        ("InpXLossCap", "enum", (0, 5, 10, 15, 20, 25)),
    ],
    "time": [
        ("InpXDecayBars", "enum", (0, 4, 8, 12, 16, 24, 32)),
        ("InpXDecayR", "num", (-1.0, 0.0, 0.25)),
        ("InpXStaleBars", "enum", (0, 4, 8, 12, 16, 24, 32)),
        ("InpXMaxBars", "enum", (0, 8, 12, 16, 24, 32, 48)),
    ],
    "target": [
        ("InpFixTpPips", "enum", (0, 20, 40, 60, 80, 100)),
    ],
    "session": [
        ("InpCloseLossMins", "enum", (0, 15, 30, 60, 120)),
    ],
    "daily": [
        ("InpDayLossUsd", "enum", (0, 500, 1000, 1500, 2000, 3000, 4000, 5000)),
    ],
}
OBJECTIVES = {"ret_dd": "net ÷ max drawdown", "net": "net profit", "pf": "profit factor", "wr": "win rate",
              "avg_loss": "Cut down Avg Loss", "worst_loss": "Cut down Worst Loss"}


def _fmt(kind, v):
    if kind == "bool":
        return "true" if v else "false"
    if kind in ("int", "enum"):
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".") if abs(v - round(v)) > 1e-9 else str(int(round(v)))


def neighbours(inputs, name, kind, grid, direction):
    """The setting moved one step (direction +1 / -1); None at the edge."""
    cur = inputs[name]
    if kind == "bool":
        return None if direction < 0 else ("false" if str(cur).lower() == "true" else "true")
    if kind == "enum":
        vals = list(grid)
        try:
            i = vals.index(int(float(cur)))
        except ValueError:
            i = 0
        j = i + direction
        return str(vals[j]) if 0 <= j < len(vals) else None
    lo, hi, st = grid
    v = float(cur) + direction * st
    if v < lo - 1e-9 or v > hi + 1e-9:
        return None
    return _fmt(kind, round(v / st) * st if kind == "num" else v)


def evaluate(inputs, objective="ret_dd", min_trades=30, window=None, ds="year"):
    """One simulated year -> (train score, train stats, test stats, year stats)."""
    if int(float(inputs["InpEmaSlow"])) <= int(float(inputs["InpEmaFast"])) or int(float(inputs["InpSessTo"])) <= int(float(inputs["InpSessFrom"])):
        return -1e12, None, None, None
    tr = sim.simulate(inputs, ds=ds)[0]
    if window:                                                   # (train from, train to, test from, test to), server time - walk-forward
        a0, a1, b0, b1 = window
        trn, tst = tr[(tr[:, 1] >= a0) & (tr[:, 1] < a1)], tr[(tr[:, 1] >= b0) & (tr[:, 1] < b1)]
    else:
        trn, tst = tr[tr[:, 1] < TRAIN_END], tr[tr[:, 1] >= TRAIN_END]
    a, b, y = sim.score(trn, min_trades), sim.score(tst, 10), sim.score(tr, min_trades)
    s = (a["ret_dd"] if objective == "ret_dd" else a["net"] if objective == "net" else a["pf"] if objective == "pf"
         else a["avg_loss"] if objective == "avg_loss" else a["worst_loss"] if objective == "worst_loss" else a["wr"])
    if a["n"] < min_trades:
        s = -1e9 + a["n"]
    return float(s), a, b, y


class Optimizer:
    def __init__(self, start, objective="ret_dd", boxes=False, keep_going=False, min_trades=30, window=None, ds="year",
                 space=None, trade_floor_ratio=0, exhaustive=False):
        self.ds = ds
        if window is None and ds in ("m15", "m1x"):                       # 4 years: tune on 2023 + 2024, judge on 2025 + 2026 (never seen while tuning)
            s, m = sim._ep(sim.datetime(2023, 1, 1)), sim._ep(sim.datetime(2025, 1, 1))
            window = (s, m, m, sim._ep(sim.datetime(2027, 1, 1)))
        self.labels = ("2023 – 2024", "2025 – 2026") if ds in ("m15", "m1x") else ("Jan – Jun", "Jul – Oct")
        self.window = window
        self.start = {k: str(v) for k, v in start.items()}
        self.objective, self.boxes, self.keep, self.min_trades = objective, boxes, keep_going, min_trades
        self.space = list(SPACE if space is None else space) + ([(f"box{s}{b:02d}", "box", None) for s in "BS" for b in range(21)] if boxes else [])
        self.trade_floor_ratio = trade_floor_ratio
        self.trade_floor = min_trades
        self.exhaustive = exhaustive
        self.log, self.best, self.board = [], None, []
        self.evals, self.passes, self.restarts, self.running, self.done, self.error = 0, 0, 0, False, False, None
        self.t0 = None
        self._stop = False
        self._lock = threading.Lock()

    # range boxes as single settings: toggle one box
    def _get(self, inp, name, kind, grid, direction):
        if kind != "box":
            return neighbours(inp, name, kind, grid, direction)
        if direction < 0:
            return None
        key = "InpBands" + name[3]
        b = int(name[4:])
        s = list(str(inp[key]).ljust(21, "1")[:21])
        s[b] = "0" if s[b] == "1" else "1"
        return "".join(s)

    def _key(self, name, kind):
        return ("InpBands" + name[3]) if kind == "box" else name

    def _eval(self, inp):
        self.evals += 1
        return evaluate(inp, self.objective, self.min_trades, self.window, self.ds)

    def descend(self, inp, label):
        sc, a, b, y = self._eval(inp)
        changed = True
        while changed and not self._stop:
            changed = False
            self.passes += 1
            for name, kind, grid in self.space:
                if self._stop:
                    break
                key = self._key(name, kind)
                if self.exhaustive and kind != "box":
                    if kind == "bool":
                        values = ("false", "true")
                    elif kind == "enum":
                        values = tuple(str(int(v)) for v in grid)
                    else:
                        lo, hi, step = grid
                        values = tuple(_fmt(kind, lo + i * step) for i in range(int(round((hi - lo) / step)) + 1))
                    best_step = None
                    for value in values:
                        try:
                            unchanged = float(value) == float(inp[key]) if kind != "bool" else value == str(inp[key]).lower()
                        except (TypeError, ValueError):
                            unchanged = value == str(inp[key])
                        if self._stop or unchanged:
                            continue
                        cand = dict(inp, **{key: value})
                        s2, a2, b2, y2 = self._eval(cand)
                        if s2 > sc + abs(sc) * MIN_GAIN and s2 > sc + 1e-9 and (best_step is None or s2 > best_step[0]):
                            best_step = (s2, cand, a2, b2, y2, value)
                    if best_step:
                        s2, cand, a2, b2, y2, value = best_step
                        with self._lock:
                            self.log.append({"run": label, "setting": key, "from": inp[key], "to": value, "score": round(s2, 3),
                                             "train": a2, "test": b2, "year": y2, "t": round(time.time() - self.t0, 2), "inputs": dict(cand)})
                        inp, sc, a, b, y = cand, s2, a2, b2, y2
                        changed = True
                        self._offer(inp, sc, a, b, y, label)
                    continue
                for direction in (+1, -1):
                    moved = False
                    while not self._stop:
                        v = self._get(inp, name, kind, grid, direction)
                        if v is None:
                            break
                        cand = dict(inp, **{key: v})
                        s2, a2, b2, y2 = self._eval(cand)
                        if s2 > sc + abs(sc) * MIN_GAIN and s2 > sc + 1e-9:
                            with self._lock:
                                self.log.append({"run": label, "setting": key if kind != "box" else f"{'BUY' if name[3] == 'B' else 'SELL'} box {int(name[4:]) * 5}%",
                                                 "from": inp[key] if kind != "box" else str(inp[key])[int(name[4:])], "to": v if kind != "box" else v[int(name[4:])],
                                                 "score": round(s2, 3), "train": a2, "test": b2, "year": y2, "t": round(time.time() - self.t0, 2), "inputs": dict(cand)})
                            inp, sc, a, b, y = cand, s2, a2, b2, y2
                            moved = changed = True
                            self._offer(inp, sc, a, b, y, label)
                        else:
                            break
                    if moved:
                        break                                   # this setting found its direction
        return inp, sc, a, b, y

    def _offer(self, inp, sc, a, b, y, label):
        with self._lock:
            if self.best is None or sc > self.best["score"]:
                self.best = {"inputs": dict(inp), "score": sc, "train": a, "test": b, "year": y, "found_by": label, "t": round(time.time() - self.t0, 2)}

    def run(self):
        self.running, self.t0 = True, time.time()
        try:
            sc, a, b, y = self._eval(self.start)
            if self.trade_floor_ratio:
                self.trade_floor = max(self.min_trades, int(np.ceil(a["n"] * self.trade_floor_ratio)))
                self.min_trades = self.trade_floor
            self.baseline = {"score": sc, "train": a, "test": b, "year": y}
            self._offer(self.start, sc, a, b, y, "start")
            inp, sc, a, b, y = self.descend(dict(self.start), "pass from your settings")
            self._board(inp, sc, a, b, y)
            rnd = random.Random(7)
            while self.keep and not self._stop:
                self.restarts += 1
                shaken = dict(self.best["inputs"])
                for name, kind, grid in rnd.sample(self.space, min(4, len(self.space))):
                    for _ in range(rnd.randint(2, 6)):
                        v = neighbours(shaken, name, kind, grid, rnd.choice((1, -1)))
                        if v is not None:
                            shaken[name] = v
                inp, sc, a, b, y = self.descend(shaken, f"restart {self.restarts}")
                self._board(inp, sc, a, b, y)
        except Exception as e:                              # noqa: BLE001
            self.error = str(e)
        finally:
            self.running, self.done = False, True

    def _board(self, inp, sc, a, b, y):
        with self._lock:
            sig = tuple(sorted(inp.items()))
            if all(tuple(sorted(x["inputs"].items())) != sig for x in self.board):
                self.board.append({"inputs": dict(inp), "score": sc, "train": a, "test": b, "year": y})
                self.board.sort(key=lambda x: -x["score"])
                del self.board[12:]

    def stop(self):
        self._stop = True

    def state(self):
        with self._lock:
            ch = lambda inp: {k: v for k, v in inp.items() if str(v) != str(self.start.get(k))}
            return {"running": self.running, "done": self.done, "error": self.error, "evals": self.evals, "passes": self.passes, "restarts": self.restarts,
                    "seconds": round(time.time() - self.t0, 1) if self.t0 else 0, "objective": self.objective, "objectives": list(OBJECTIVES),
                    "ds": self.ds, "labels": self.labels, "boxes": self.boxes, "keep": self.keep, "trade_floor": self.trade_floor,
                    "exhaustive": self.exhaustive,
                    "baseline": getattr(self, "baseline", None), "log": self.log[-200:], "mt5": getattr(self, "mt5", None),
                    "best": dict(self.best, changed=ch(self.best["inputs"])) if self.best else None,
                    "board": [dict(x, changed=ch(x["inputs"])) for x in self.board]}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(sim.HERE.parents[1] / "monitor" / "strategy_lab"))
    import axi_rig
    o = Optimizer(axi_rig.ea_defaults("Saad_strategy_15min"))
    t = time.time()
    o.run()
    s = o.state()
    print(f"{s['evals']} evaluations, {s['passes']} passes, {time.time() - t:.1f} s")
    for l in s["log"]:
        print(f"  {l['setting']}: {l['from']} -> {l['to']}  score {l['score']}  train {l['train']['net']:+,.0f} WR {l['train']['wr']}% | "
              f"test {l['test']['net']:+,.0f} WR {l['test']['wr']}%")
    print("baseline:", s["baseline"]["train"]["net"], s["baseline"]["test"]["net"], "| best changed:", s["best"]["changed"])


# ---------------------------------------------------------------- survey: every entry / every exit setting, one at a time
# Zee 2026-10-20: "give an option called entries and another called exits .. the results show diff exits and their results etc as well as diff entries"
SURVEY = {
    "entries": [("InpEmaFast", [8, 10, 12, 14, 16, 18, 20, 24]), ("InpEmaSlow", [24, 28, 32, 36, 40, 50, 60]),
                ("InpWickMin", [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]), ("InpBodyMax", [0.3, 0.4, 0.5, 0.6, 0.7]),
                ("InpNoseMax", [0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5]), ("InpMaruBody", [0.4, 0.5, 0.53, 0.6, 0.7]),
                ("InpHamRatio", [1.5, 2, 2.5, 3, 4]), ("InpHamNose", [0.3, 0.4, 0.5, 0.6]), ("InpMinRangeAtr", [0, 0.3, 0.45, 0.55, 0.7, 0.9]),
                ("InpUsePin", ["true", "false"]), ("InpMarubozu", ["true", "false"]), ("InpHammer", ["true", "false"]), ("InpStar", ["true", "false"]),
                ("InpTouchMode", [0, 1]), ("InpTouchPips", [0, 0.5, 1, 2, 3]), ("InpLongRule", [0, 1, 2]), ("InpShortLine", [0, 1, 2]),
                ("InpBreakBars", [1, 2, 3]), ("InpBreakPips", [0, 1, 2, 3, 4, 6]), ("InpAdxMin", [0, 15, 20, 25, 28, 30, 32, 35, 40]),
                ("InpSessFrom", [0, 3, 8, 10, 15]), ("InpSessTo", [17, 19, 22, 24]), ("InpRangeLook", [5, 7, 10, 14]), ("InpRangeLookS", [5, 7, 10, 14]),
                ("InpBandOff", [0, 1]), ("InpBandsB", ["1" * 21]), ("InpBandsS", ["1" * 21]), ("InpEntryMode", [0, 1, 2]),
                ("InpChopEr", [0, 0.05, 0.1, 0.15]), ("InpTrendAlign", ["true", "false"]), ("InpPriceSide", ["true", "false"]), ("InpHtfMin", [0, 60, 240]),
                ("InpCoolBars", [0, 2, 4, 8]), ("InpSkipDow", [-1, 1, 5]), ("InpSkipBothEma", ["true", "false"])],
    "exits": [("InpExitMode", [0, 1, 2]), ("InpSlMode", [0, 1, 2]), ("InpSlAtrMult", [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5]),
              ("InpSlPips", [20, 31, 40, 60]), ("InpSlUsd", [3, 5, 8, 12]), ("InpMaxRiskUsd", [0, 10, 15, 20, 25, 30]),
              ("InpCloseLossMins", [0, 3, 15]), ("InpBeUsd", [0, 3, 5, 8, 12]), ("InpLockAtUsd", [0, 5, 8, 12]), ("InpFixTpPips", [0, 20, 40, 60, 100]),
              ("InpMaxBars", [0, 4, 8, 16, 32]),
              ("InpLongTouch", [0, 1]), ("InpShortTouch", [0, 1]), ("InpPartialPct", [0, 0.25, 0.5, 0.75]), ("InpTp1Be", ["false", "true"]),
              ("InpLongTrailUsd", [1, 2, 3, 5, 8]), ("InpShortTrailUsd", [1, 2, 3, 5, 8]), ("InpTrail", ["false", "true"]),
              ("InpTrailMode", [0, 1, 2]), ("InpTrailAtr", [1, 1.5, 2, 3]), ("InpRide", ["false", "true"]), ("InpBeTpPct", [0, 0.5, 0.75, 0.9]),
              ("InpMinTpPips", [5, 15, 30]), ("InpSwingPivot", [2, 3, 5])],
}
EXIT0 = set(__import__("sim_full").MODE0_ONLY)                         # v1.23's exit options (BeUsd, LockAtUsd, FixTpPips, MaxBars too): only act with exit mode 0
SLMODE = {"InpSlPips": "0", "InpSlUsd": "2"}                             # a stop size only acts in its own stop mode


def _same(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-9
    except ValueError:
        return str(a).lower() == str(b).lower()


class Survey:
    def __init__(self, start, group, ds="year"):
        o = Optimizer(start, ds=ds)
        self.start, self.group, self.ds, self.window, self.labels = o.start, group, ds, o.window, o.labels
        self.rows, self.evals, self.running, self.done, self.error, self.t0, self._stop = [], 0, False, False, None, None, False
        self.baseline = None

    def _ev(self, inp):
        self.evals += 1
        _, a, b, _y = evaluate(inp, "net", 1, self.window, self.ds)
        return a, b

    def run(self):
        self.running, self.t0 = True, time.time()
        try:
            a, b = self._ev(self.start)
            self.baseline = {"train": a, "test": b}
            jobs = []                                       # every (setting, value) to run, in the order the rows are shown
            for name, vals in SURVEY[self.group]:
                if name not in self.start:
                    continue
                for v in vals:
                    extra = {}
                    if name in EXIT0 and self.start.get("InpExitMode") != "0":
                        extra["InpExitMode"] = "0"
                    if name in SLMODE and self.start.get("InpSlMode") != SLMODE[name]:
                        extra["InpSlMode"] = SLMODE[name]
                    if _same(self.start[name], v):
                        continue                                  # the value on screen (with exit mode 0 added it is just the InpExitMode 0 row again)
                    inp = dict(self.start, **extra)
                    inp[name] = str(v)
                    jobs.append((name, v, extra, inp))
            # the runs are independent: the tester's numba core releases the lock, so they run side by side (8 cores)
            from concurrent.futures import ThreadPoolExecutor
            def one(job):
                if self._stop:
                    return None
                name, v, extra, inp = job
                self.evals += 1
                _, ra, rb, _y = evaluate(inp, "net", 1, self.window, self.ds)
                return ra, rb
            with ThreadPoolExecutor(max_workers=6) as ex:
                results = list(ex.map(one, jobs))
            B0 = self.baseline
            for (name, v, extra, inp), res in zip(jobs, results):
                if self._stop:
                    return
                if res is None:
                    continue
                a, b = res
                if a is None:
                    continue
                noop = abs(a["net"] - B0["train"]["net"]) < 1 and abs(b["net"] - B0["test"]["net"]) < 1 and a["n"] == B0["train"]["n"] and b["n"] == B0["test"]["n"]
                v123 = inp.get("InpExitMode") == "0"           # the v1.23 exits: where the tester and MT5 disagree (verify_settings.py)
                self.rows.append({"setting": name, "value": str(v), "with": extra, "train": a, "test": b, "noop": noop, "v123": v123,
                                  "total": round(a["net"] + b["net"]), "inputs": inp})
        except Exception as e:                                           # noqa: BLE001
            self.error = str(e)
        finally:
            self.running, self.done = False, True

    def stop(self):
        self._stop = True

    def state(self):
        return {"kind": "survey", "group": self.group, "running": self.running, "done": self.done, "error": self.error, "evals": self.evals,
                "seconds": round(time.time() - self.t0, 1) if self.t0 else 0, "ds": self.ds, "labels": self.labels, "baseline": self.baseline,
                "rows": sorted(self.rows, key=lambda r: -r["total"]), "objective": self.group, "log": [], "best": None, "board": []}


# ---------------------------------------------------------------- ranges: grow the number of 100%-win range boxes, lock each one once it is perfect
# Zee 2026-10-20: "it optimizes for achieving the maximum number of ranges ticked to be 100%. so for example for 1 range it reaches 100% winrate,
# it leaves that range alone and tries another range ... some settings gave alot of 100% winrate ranges.. those settings usually had great results"
#  1. every box ticked (no range filter), so each box shows its own trades
#  2. each setting one step up / down; a step is kept only if it does NOT break a locked (perfect) box and it raises
#     (perfect boxes, trades inside them, their net) - a box counts only with >= MIN_BOX trades, so one lucky trade is not "100%"
#  3. a box that turns perfect is locked: later steps must keep it perfect ("leave that range alone and try another")
#  4. passes until nothing helps; then only the perfect boxes are ticked, and 2025 - 2026 (never looked at) shows if they stay perfect
MIN_BOX = 3
ALL_ON = "1" * 21


def box_stats(tr):
    """(side 'B'/'S', box 0..20) -> [trades, wins, net] of the real trades"""
    out = {}
    for x in tr[tr[:, 10] == 0]:
        k = ("B" if x[0] > 0 else "S", int(round(x[8])))
        d = out.setdefault(k, [0, 0, 0.0]); d[0] += 1; d[1] += int(x[6] > 0); d[2] += float(x[6])
    return out


def _wilson(w, n, z=1.2816):
    if n == 0:
        return 0.0
    p = w / n
    return (p + z * z / (2 * n) - z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5) / (1 + z * z / n)


class RangeOpt:
    def __init__(self, start, ds="year", min_box=MIN_BOX):
        o = Optimizer(start, ds=ds)
        self.ds, self.window, self.labels, self.min_box = ds, o.window, o.labels, min_box
        self.start = dict(o.start, InpBandsB=ALL_ON, InpBandsS=ALL_ON, InpBandOff="0")
        self.log, self.evals, self.passes, self.running, self.done, self.error, self.t0, self._stop = [], 0, 0, False, False, None, None, False
        self.cur = self.cur_key = self.cur_boxes = self.baseline = self.final = None
        self.locked = set()

    def _split(self, tr):
        if self.window:
            a0, a1, b0, b1 = self.window
            return tr[(tr[:, 1] >= a0) & (tr[:, 1] < a1)], tr[(tr[:, 1] >= b0) & (tr[:, 1] < b1)]
        return tr[tr[:, 1] < TRAIN_END], tr[tr[:, 1] >= TRAIN_END]

    def _ev(self, inp):
        self.evals += 1
        if int(float(inp["InpEmaSlow"])) <= int(float(inp["InpEmaFast"])) or int(float(inp["InpSessTo"])) <= int(float(inp["InpSessFrom"])):
            return None
        trn, tst = self._split(sim.simulate(inp, ds=self.ds)[0])
        bx = box_stats(trn)
        perfect = {k for k, d in bx.items() if d[0] >= self.min_box and d[1] == d[0]}
        # the slope towards 100%: each box's win rate at 90% confidence (Wilson lower bound) - grows as a box loses fewer and gathers more trades
        pure = sum(_wilson(d[1], d[0]) for d in bx.values() if d[0] >= self.min_box)
        key = (len(perfect), round(pure, 3), sum(bx[k][0] for k in perfect), round(sum(bx[k][2] for k in perfect)))
        return key, perfect, bx, trn, tst

    def run(self):
        self.running, self.t0 = True, time.time()
        try:
            r = self._ev(self.start)
            self.cur, (self.cur_key, perfect, self.cur_boxes, trn, tst) = dict(self.start), r
            self.locked = set(perfect)
            self.baseline = {"train": sim.score(trn, 1), "test": sim.score(tst, 1), "perfect": len(perfect)}
            improved = True
            while improved and not self._stop:
                improved, self.passes = False, self.passes + 1
                for name, kind, grid in SPACE:
                    for direction in (1, -1):
                        while not self._stop:                       # a step that helps is repeated
                            v = neighbours(self.cur, name, kind, grid, direction)
                            if v is None:
                                break
                            inp = dict(self.cur, **{name: v})
                            r = self._ev(inp)
                            if r is None:
                                break
                            key, perfect, bx, trn, tst = r
                            if not self.locked <= perfect or key <= self.cur_key:
                                break
                            new = sorted(perfect - self.locked)
                            self.log.append({"setting": name, "from": self.cur[name], "to": v, "perfect": key[0], "pure": key[1], "trades": key[2], "net": key[3],
                                             "new": [f"{s} {b}" for s, b in new], "inputs": self._ticked(inp, perfect)})
                            self.cur, self.cur_key, self.cur_boxes = inp, key, bx
                            self.locked |= perfect
                            improved = True
            self._finish()
        except Exception as e:                                       # noqa: BLE001
            self.error = str(e)
        finally:
            self.running, self.done = False, True

    @staticmethod
    def _ticked(inp, perfect):
        b = "".join("1" if ("B", i) in perfect else "0" for i in range(21))
        s = "".join("1" if ("S", i) in perfect else "0" for i in range(21))
        return dict(inp, InpBandsB=b if "1" in b else "0" * 21, InpBandsS=s if "1" in s else "0" * 21, InpBandOff="0")

    def _finish(self):
        all_on = self._split(sim.simulate(self.cur, ds=self.ds)[0])
        tb = box_stats(all_on[1])
        fin = self._ticked(self.cur, self.locked)
        trn, tst = self._split(sim.simulate(fin, ds=self.ds)[0])
        boxes = []
        for side, b in sorted(self.locked):
            a, t = self.cur_boxes.get((side, b), [0, 0, 0.0]), tb.get((side, b), [0, 0, 0.0])
            boxes.append({"side": side, "box": b, "n": a[0], "net": round(a[2]), "tn": t[0], "tw": t[1], "tnet": round(t[2])})
        self.final = {"inputs": fin, "train": sim.score(trn, 1), "test": sim.score(tst, 1), "boxes": boxes,
                      "kept": sum(1 for x in boxes if x["tn"] and x["tw"] == x["tn"])}

    def stop(self):
        self._stop = True

    def state(self):
        return {"kind": "ranges", "running": self.running, "done": self.done, "error": self.error, "evals": self.evals, "passes": self.passes,
                "seconds": round(time.time() - self.t0, 1) if self.t0 else 0, "ds": self.ds, "labels": self.labels, "baseline": self.baseline,
                "perfect": self.cur_key[0] if self.cur_key else 0, "locked": sorted(f"{s} {b}" for s, b in self.locked), "min_box": self.min_box,
                "steps": self.log, "final": self.final, "objective": "ranges", "log": [], "best": None, "board": []}
