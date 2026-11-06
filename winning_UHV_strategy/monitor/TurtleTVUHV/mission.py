"""mission.py - Mission Control: "i run an EA tomorrow using some capital and it brings in some profit" (Zee 2026-10-21).

From the strategy's own trades on the data (the Turtle TV Tester, the settings on screen, optionally the exit on the Exit Lab bench):
  - the size: lots for the capital, from a drawdown the account can live with (a $200 account was liquidated on SIZE, not direction)
  - the days: how often a day is green, a typical day, a bad day, the worst week / month, red-day streaks
  - the futures: thousands of 1-month / 3-month / 1-year paths bootstrapped from real days (in 5-day blocks: streaks stay streaks) -
    the chance of being up, the bad case, the chance of a deep drawdown and of a margin call
  - the guardrails: the EA's own daily stop (InpDayLossUsd) and daily target (InpDayTargetUsd), run through the engine at that size
  - the form: is the edge alive lately? the last 30 trading days against every 30-day window of the past
Python tester numbers: hypotheses until MT5 confirms them. Gold: 1 lot = 100 oz."""
import os
import threading
import time
from datetime import datetime, timezone

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import numpy as np  # noqa: E402

import exitlab  # noqa: E402
import sim  # noqa: E402


def _days(real, ds, lots_run):
    """P&L per trading day for 1 lot (every day with data, zero when nothing traded)"""
    D = sim.data(ds)
    days = np.unique(D["t1"] // 86400)
    d = {int(x): 0.0 for x in days}
    for x in real:
        k = int(x[4]) // 86400
        if k in d:
            d[k] += float(x[6]) / lots_run
    keys = np.array(sorted(d), dtype=np.int64)
    return keys, np.array([d[k] for k in keys])


def _maxdd(eq):
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    return float(np.max(peak - eq)) if len(eq) else 0.0


def _mc(daily, n_days, paths=2000, block=5, seed=7):
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n_days / block))
    starts = rng.integers(0, max(1, len(daily) - block), size=(paths, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(paths, -1)[:, :n_days]
    p = daily[idx]
    eq = np.cumsum(p, axis=1)
    dd = np.max(np.maximum.accumulate(np.concatenate([np.zeros((paths, 1)), eq], axis=1), axis=1)[:, 1:] - eq, axis=1)   # along time, per path
    return eq[:, -1], dd, eq.min(axis=1)


class Job:
    def __init__(self, inputs, ds, lab, capital, mode, lots, risk_pct, leverage, max_dd_pct, lego=None):
        self.inputs, self.ds, self.lab, self.lego = inputs, ("year" if ds == "tv" else ds), lab or None, lego or None
        self.capital, self.mode, self.lots, self.risk_pct = float(capital), mode, float(lots or 0), float(risk_pct or 1)
        self.leverage, self.max_dd = float(leverage or 500), float(max_dd_pct or 20) / 100.0
        self.running, self.done, self.error, self.phase, self.result, self.t0 = False, False, None, "starting", None, None
        self.jid = f"mission-{time.time_ns()}"

    def state(self):
        return {"jid": self.jid, "running": self.running, "done": self.done, "error": self.error, "phase": self.phase,
                "seconds": round(time.time() - self.t0, 1) if self.t0 else 0, "result": self.result}

    def run(self):
        self.running, self.t0 = True, time.time()
        try:
            self.result = self._run()
        except Exception as e:                                    # noqa: BLE001
            import traceback
            self.error, self.tb = str(e), traceback.format_exc()
        finally:
            self.running, self.done = False, True

    def _sim(self, lots, extra=None):
        inp = dict(self.inputs, InpLots=f"{lots:.2f}", InpRiskPct="0", **(extra or {}))
        sets = {} if not self.lab or str(inp.get("InpExitMode")) in ("1", "2") else {"InpExitMode": "1"}
        _, real, oe = exitlab.run(inp, self.ds, lab=self.lab, sets=sets, lego=self.lego)
        return real, oe

    def _run(self):
        self.phase = "the strategy's trades, for 1 lot"
        L0 = max(0.01, float(self.inputs.get("InpLots", 1) or 1))
        scale = {k: f"{float(self.inputs.get(k, 0) or 0) / L0:.2f}" for k in ("InpDayLossUsd", "InpDayTargetUsd")}   # the EA's $ day limits, per lot
        real, oe = self._sim(1.0, scale)
        keys, per_lot = _days(real, self.ds, 1.0)
        D = sim.data(self.ds)
        price = float(D["c15"][-1])
        R = real[:, 17]
        med_r = float(np.median(R)) if len(R) else 5.0
        margin_per_lot = price * 100.0 / self.leverage
        # the size
        if self.mode == "risk":
            lots = max(0.01, np.floor(self.capital * self.risk_pct / 100.0 / (med_r * 100.0) / 0.01) * 0.01)
        else:
            lots = max(0.01, self.lots)
        self.phase = "finding the size the account can live with"
        _, dd_year, _ = _mc(per_lot, 252)
        dd95 = float(np.percentile(dd_year, 95))
        hist_dd = _maxdd(np.cumsum(per_lot))
        rec = max(0.0, np.floor(min(self.max_dd * self.capital / max(dd95, 1e-9), self.max_dd * self.capital / max(hist_dd, 1e-9)) / 0.01) * 0.01)
        daily = per_lot * lots
        eq = np.cumsum(daily)
        # the days
        traded = daily[daily != 0]
        wk = np.convolve(daily, np.ones(5), mode="valid") if len(daily) >= 5 else daily
        mo = np.convolve(daily, np.ones(21), mode="valid") if len(daily) >= 21 else daily
        red = best = 0
        for v in daily:
            red = red + 1 if v < 0 else (red if v == 0 else 0)
            best = max(best, red)
        days = {"n": int(len(daily)), "traded": int(len(traded)), "green_pct": round(float(100 * (traded > 0).mean()), 1) if len(traded) else 0,
                "avg": round(float(daily.mean())), "avg_traded": round(float(traded.mean())) if len(traded) else 0, "median_traded": round(float(np.median(traded))) if len(traded) else 0,
                "best": round(float(daily.max())), "worst": round(float(daily.min())), "worst_week": round(float(wk.min())), "worst_month": round(float(mo.min())),
                "bad_day": round(float(np.percentile(traded, 5))) if len(traded) else 0, "good_day": round(float(np.percentile(traded, 95))) if len(traded) else 0,
                "red_streak": int(best), "max_dd": round(_maxdd(eq)), "max_dd_pct": round(100 * _maxdd(eq) / self.capital, 1), "net": round(float(eq[-1])) if len(eq) else 0,
                "per_month": round(float(daily.mean() * 21)), "trades_per_day": round(len(real) / max(1, len(daily)), 2)}
        # the futures
        self.phase = "simulating 2,000 futures"
        fut = {}
        margin = lots * margin_per_lot
        for nm, n in (("1 month", 21), ("3 months", 63), ("1 year", 252)):
            fin, dd, low = _mc(daily, n)
            fut[nm] = {"up_pct": round(float(100 * (fin > 0).mean()), 1), "median": round(float(np.median(fin))), "p5": round(float(np.percentile(fin, 5))),
                       "p95": round(float(np.percentile(fin, 95))), "dd_p95": round(float(np.percentile(dd, 95))),
                       "deep_dd_pct": round(float(100 * (dd > self.max_dd * self.capital).mean()), 1),
                       "ruin_pct": round(float(100 * ((self.capital + low) < margin).mean()), 1)}
        # the form: the last 30 trading days against every 30-day window of the past
        roll = np.convolve(per_lot, np.ones(30), mode="valid") if len(per_lot) >= 30 else per_lot
        form = {"last30": round(float(roll[-1] * lots)), "pct": round(float(100 * (roll < roll[-1]).mean()), 1), "median30": round(float(np.median(roll) * lots)),
                "curve": [round(float(v * lots)) for v in roll[::max(1, len(roll) // 300)]]}
        # the guardrails: the EA's daily stop / target at this size, through the engine
        self.phase = "testing daily stops and targets"
        grid = []
        stops = [0, 0.01, 0.02, 0.03, 0.05]
        targets = [0, 0.02, 0.04, 0.08]
        for sp in stops:
            row = []
            for tg in targets:
                extra = {"InpDayLossUsd": f"{sp * self.capital:.0f}", "InpDayTargetUsd": f"{tg * self.capital:.0f}"}
                r2, _ = self._sim(lots, extra)
                _, dd2 = _days(r2, self.ds, 1.0)
                tr2 = dd2[dd2 != 0]
                row.append({"stop": round(sp * self.capital), "target": round(tg * self.capital), "net": round(float(dd2.sum())), "worst": round(float(dd2.min())) if len(dd2) else 0,
                            "green_pct": round(float(100 * (tr2 > 0).mean()), 1) if len(tr2) else 0, "max_dd": round(_maxdd(np.cumsum(dd2))), "n": int(len(r2))})
            grid.append(row)
        step = max(1, len(eq) // 400)
        worst_dd = max(dd95, hist_dd)                             # per lot: the bad simulated year, or the worst real stretch
        return {"capital": self.capital, "lots": round(float(lots), 2), "recommended_lots": round(float(rec), 2), "max_dd_pct": round(100 * self.max_dd),
                "dd_per_lot": round(worst_dd), "min_capital_001": round(0.01 * worst_dd / self.max_dd), "per_lot_month": round(float(per_lot.mean() * 21)),
                "median_stop": round(med_r, 2), "risk_per_trade": round(med_r * 100 * lots), "risk_per_trade_pct": round(100 * med_r * 100 * lots / self.capital, 2),
                "margin": round(margin), "price": round(price, 2), "days": days, "futures": fut, "form": form, "grid": grid,
                "equity": [round(float(v)) for v in eq[::step]], "dates": [datetime.fromtimestamp(int(keys[i]) * 86400, timezone.utc).strftime("%Y-%m-%d") for i in range(0, len(keys), step)],
                "stuck": bool(oe.get("n") and oe.get("days", 0) > 14), "ds": self.ds, "with_lab": bool(self.lab), "lab": exitlab.describe(self.lab) if self.lab else "",
                "lego": self.lego or {}}


def start(inputs, ds, lab, capital, mode, lots, risk_pct, leverage, max_dd_pct, lego=None):
    j = Job(inputs, ds, lab, capital, mode, lots, risk_pct, leverage, max_dd_pct, lego)
    threading.Thread(target=j.run, daemon=True).start()
    return j
