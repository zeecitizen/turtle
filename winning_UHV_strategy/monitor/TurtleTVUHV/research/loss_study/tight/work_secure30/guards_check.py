"""guards_check.py - every rule's lift per stack-half with a binomial p, and on BASE again with the trades the secure setting's own guards
already block (NY rollover 16:45-17:45, breakout spread >= 1.0 pip) taken out - so a rule cannot look general by re-finding them.
HYPOTHESIS ONLY.   Run: NUMBA_CPU_NAME=generic py guards_check.py  (writes guards_check.txt)"""
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

from scipy.stats import binom

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import api_tight as AT  # noqa: E402
import rules as RL  # noqa: E402

NY = ZoneInfo("America/New_York")


def guarded(t):
    ny = dt.datetime.fromtimestamp(t["t_dec"], NY)
    m = ny.hour * 60 + ny.minute
    return (16 * 60 + 45 <= m < 17 * 60 + 45) or t["trig_spread_pips"] >= 1.0 - 1e-9


def cell(res, part):
    x = res[part]; n = x["removed"]; k = x["losses_removed"]; p = x["losses"] / x["trades"]
    pv = binom.sf(k - 1, n, p) if n else 1.0
    return f"{part[:2]} {k}L/{n} lift {k / max(n * p, 1e-9):.2f} p={pv:.3f} WR {x['wr_before']}->{x['wr_after']}"


lines = ["lift = loss rate among removed / the stack-half's loss rate; p = binomial P(>= that many losses among removed). HYPOTHESIS ONLY."]
for r in RL.RULES:
    s = AT.score(r, "secure"); b = AT.score(r, "base")
    bg = AT.score(lambda t, A, r=r: (not guarded(t)) and r(t, A), "base")
    lines.append(f"{r.__name__:22s} SECURE {cell(s, 'train')} | {cell(s, 'test')}")
    lines.append(f"{'':22s} BASE   {cell(b, 'train')} | {cell(b, 'test')}")
    lines.append(f"{'':22s} BASE beyond the rollover + spread-1.0 guards: {cell(bg, 'train')} | {cell(bg, 'test')}")
g = AT.score(lambda t, A: guarded(t), "base")
lines.append(f"{'the guards themselves':22s} BASE   {cell(g, 'train')} | {cell(g, 'test')}")
print("\n".join(lines))
open(os.path.join(HERE, "guards_check.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
