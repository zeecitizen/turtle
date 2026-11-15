"""exitlab_check.py - each Exit Lab building block, checked trade by trade against its own definition (not just "the totals look sane").

   py monitor/saad_view/exitlab_check.py [year|m15]

Every check prints how many trades obey the rule and lists the first offenders. A building block that breaks its own rule is a bug."""
import os
import sys
from pathlib import Path

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import exitlab  # noqa: E402
import server  # noqa: E402
import sim  # noqa: E402

DS = sys.argv[1] if len(sys.argv) > 1 else "year"
INP = server.full_inputs({})
D = sim.data(DS)
P, _, _ = sim.pvec_all(INP)
EF, ES = sim.emas(P[0], P[1], DS)
BAD = 0


def run(lab):
    _, r, _oe = exitlab.run(INP, DS, lab=lab)
    return r


def check(name, real, ok, why=None):
    global BAD
    sel = real if why is None else real[np.isin(real[:, 13], why)]
    good = np.array([bool(ok(x)) for x in sel], dtype=bool)
    n_bad = int((~good).sum())
    BAD += n_bad > 0
    print(f"{'OK  ' if n_bad == 0 else 'FAIL'} {name}: {len(sel) - n_bad}/{len(sel)} obey")
    for x in sel[~good][:3]:
        print("      offender: side", int(x[0]), "in", int(x[1]), "en", round(x[2], 2), "out", int(x[4]), "ex", round(x[5], 2), "pnl", round(x[6], 2),
              "why", int(x[13]), "EK", int(x[11]), "kout", int(x[12]), "mfe", round(x[15], 2), "R0", round(x[17], 2), "lots", x[18], "partials", int(x[19]))


lots = float(INP["InpLots"])
# 1. the lab's target in R: exits at the level, or better when price opened through it
for k in (1.0, 2.0):
    r = run({"tgt": 2, "tgt_k": k})
    check(f"target {k}R exits at its level (or better on a gap)", r, lambda x: (x[5] - (x[2] + x[0] * k * x[17])) * x[0] >= -0.011, why=[9])
    check(f"target {k}R: the best move reached the target", r, lambda x: x[15] >= k * x[17] - 0.011, why=[9])
# 2. breakeven: a breakeven stop leaves at the entry (or worse only on a gap), never in profit beyond the spread
r = run({"be_r": 1})
check("breakeven exits at the entry", r, lambda x: abs(x[5] - x[2]) < 0.011 or (x[5] - x[2]) * x[0] < 0, why=[7])
check("breakeven only after +1R", r, lambda x: x[15] >= x[17] - 0.011, why=[7])
# 3. time exit: closed at the open of candle EK + N + 1 (N full candles after the entry candle)
for n in (4, 16):
    r = run({"max_bars": n})
    check(f"out after {n} candles closes exactly then", r, lambda x: int(x[12]) - int(x[11]) == n + 1, why=[8])
# 4. $ trail: a trailing exit is never better than (best price - k) (or the first stop)
for k in (3.0, 8.0):
    r = run({"tr": 1, "tr_k": k})
    check(f"$ {k:g} trail never exits better than best - {k:g}", r, lambda x: (x[5] - x[2]) * x[0] <= x[15] - k + 0.011, why=[6])
# 5. N candles against: the N candles before the exit candle all closed against the trade
r = run({"cx": 6, "cx_n": 3})
check("3 candles against: the last 3 closed candles were against", r,
      lambda x: all(((D["c15"][int(x[12]) - 1 - s] < D["o15"][int(x[12]) - 1 - s]) if x[0] > 0 else (D["c15"][int(x[12]) - 1 - s] > D["o15"][int(x[12]) - 1 - s]))
                    for s in range(3)), why=[12])
# 6. the fallback with a buffer: its close-back exits came after a close beyond the fast EMA by the buffer
r = run({"fb_buf": 0.25})
check("fallback by 0.25 ATR: the exit candle closed beyond the fast EMA by 0.25 ATR", r,
      lambda x: x[9] != -1 or ((D["c15"][int(x[12]) - 1] < EF[int(x[12]) - 1] - 0.25 * D["atr"][int(x[12]) - 1]) if x[0] > 0
                                else (D["c15"][int(x[12]) - 1] > EF[int(x[12]) - 1] + 0.25 * D["atr"][int(x[12]) - 1])), why=[3])
r = run({"fb_n": 2})
check("fallback 2 closes: the last 2 closes beyond the fast EMA", r,
      lambda x: x[9] != -1 or all(((D["c15"][int(x[12]) - 1 - s] < EF[int(x[12]) - 1 - s]) if x[0] > 0 else (D["c15"][int(x[12]) - 1 - s] > EF[int(x[12]) - 1 - s]))
                                  for s in range(2)), why=[3])
# 7. partials: half at +1R then breakeven -> a breakeven exit banks about half of 1R (plus swap)
r = run({"p1_r": 1, "p1_frac": 0.5, "p1_be": 1})
check("half at 1R + breakeven: the breakeven exits bank >= half of 1R (less swap)", r,
      lambda x: x[19] >= 1 and (x[6] - 0.0) >= 0.5 * x[18] * 100 * x[17] - 200 * x[18] - 0.5, why=[7])
check("half at 1R: every trade that reached +1R had its partial", r, lambda x: x[15] < x[17] - 0.011 or x[19] >= 1 or x[13] == 1)
# 8. the N-candle trail never moves against the trade, and a trailing exit sits at or below the N-candle low of its time
r = run({"tgt": 1, "tr": 7, "tr_k": 10})
def ratchet(x, n=10):
    """the trail's level at the exit: it only moves the trade's way, so it is the best N-candle low (BUY) / high (SELL) of any close since the entry"""
    ek, ko = int(x[11]), int(x[12])
    lv = x[3] if x[0] > 0 else x[3]
    lv = -1e18 if x[0] > 0 else 1e18
    for i in range(ek + 1, ko):
        w = slice(max(0, i - n + 1), i + 1)
        lv = max(lv, D["l15"][w].min()) if x[0] > 0 else min(lv, D["h15"][w].max())
    return lv


check("10-candle trail: a trailing exit is at or beyond the trail's level (never better than it)", r,
      lambda x: (x[5] <= ratchet(x) + 0.011) if x[0] > 0 else (x[5] >= ratchet(x) - 0.011), why=[6])
# 9. the lab off and on-but-empty are the EA itself
a = sim.simulate(INP, ds=DS)[0][:, :15]
b = sim.simulate(INP, ds=DS, lab=exitlab.clean({}))[0][:, :15]
print("OK   lab on with nothing changed = the EA" if np.array_equal(a, b) else "FAIL lab on with nothing changed differs from the EA")
BAD += not np.array_equal(a, b)
print("\nALL CHECKS PASS" if not BAD else f"\n{BAD} CHECK(S) FAILED")
sys.exit(1 if BAD else 0)
