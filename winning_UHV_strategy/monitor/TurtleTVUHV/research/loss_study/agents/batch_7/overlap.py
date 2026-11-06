"""overlap.py - batch 7: are the four liquidity/time rules independent? + threshold ladders (official api.report numbers)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE))); sys.path.insert(0, HERE)
import api  # noqa: E402
import rules as R  # noqa: E402
PIP = 1e-4
fc, ro, th, sl = R.rule_friday_close, R.rule_rollover, R.rule_thin_vm30, R.rule_slip
print("--- overlap")
api.report(lambda t, A: sl(t, A) and not (fc(t, A) or ro(t, A)), "slip & not(fri|roll)")
api.report(lambda t, A: sl(t, A) and not (fc(t, A) or ro(t, A) or th(t, A)), "slip & not(fri|roll|thin)")
api.report(lambda t, A: th(t, A) and not (fc(t, A) or ro(t, A)), "thin & not(fri|roll)")
api.report(lambda t, A: th(t, A) and not (fc(t, A) or ro(t, A) or sl(t, A)), "thin & not(fri|roll|slip)")
api.report(lambda t, A: ro(t, A) and not fc(t, A), "roll & not fri")
api.report(lambda t, A: fc(t, A) or ro(t, A), "fri | roll")
api.report(lambda t, A: fc(t, A) or ro(t, A) or th(t, A), "fri | roll | thin")
api.report(lambda t, A: fc(t, A) or ro(t, A) or th(t, A) or sl(t, A), "UNION fri|roll|thin|slip")
api.report(lambda t, A: R.rule_post_spike(t, A) and not (fc(t, A) or ro(t, A) or th(t, A) or sl(t, A)), "post_spike & not union")
api.report(lambda t, A: R.rule_loud_breakout(t, A) and not (fc(t, A) or ro(t, A) or th(t, A) or sl(t, A)), "loud_brk & not union")
print("--- ladder: slip")
for x in (0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 2.0):
    api.report(lambda t, A, x=x: t["side"] * (t["fill"] - t["level"]) >= x * PIP, f"slip>={x}")
print("--- ladder: vm30")
for x in (15, 20, 25, 30, 35, 40, 50):
    api.report(lambda t, A, x=x: A.v[t["k"] - 29:t["k"] + 1].mean() < x, f"vm30<{x}")
print("--- ladder: friday close (NY)")
for hh, mm in ((15, 30), (16, 0), (16, 15), (16, 30), (16, 45)):
    api.report(lambda t, A, a=hh * 60 + mm: (lambda m, wd: wd == 4 and m >= a)(*R._ny(t["t_in"])), f"fri NY>={hh}:{mm:02d}")
print("--- ladder: rollover window (NY)")
for a, b in ((16 * 60 + 30, 17 * 60 + 30), (16 * 60 + 40, 17 * 60 + 15), (16 * 60 + 40, 17 * 60 + 30), (16 * 60 + 40, 17 * 60 + 45),
             (16 * 60 + 40, 18 * 60), (16 * 60 + 50, 17 * 60 + 30), (16 * 60 + 45, 17 * 60 + 40)):
    api.report(lambda t, A, a=a, b=b: (lambda m, wd: a <= m < b)(*R._ny(t["t_in"])), f"roll NY {a//60}:{a%60:02d}-{b//60}:{b%60:02d}")
print("--- ladder: post_spike / loud_breakout")
for x in (5, 6, 7, 8, 10):
    api.report(lambda t, A, x=x: (A.h[t["k"] - 59:t["k"] + 1] - A.l[t["k"] - 59:t["k"] + 1]).max() >= x * A.atr[t["k"]], f"post_spike>={x}atr")
for x in (0.8, 0.85, 0.9, 0.95):
    api.report(lambda t, A, x=x: t["brk_ticks_so_far"] >= x * t["uhv_v"], f"loud_brk>={x}")
