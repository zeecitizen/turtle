"""expected.py (work_wf) - what Zee's 100% zone should do on NEW trades: break-even from its own numbers, binomial bounds on 0/308,
neighbour-band rates (perturb_out.json), empirical-Bayes posteriors, the walk-forward out-of-sample rates (wf_out.json), and the doctrine's
mandatory Python-haircut line. Python replay = hypothesis; NOT PROMOTED."""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "..")))     # .../monitor (doctrine.py)
from doctrine import python_says  # noqa: E402

PJ = json.load(open(os.path.join(HERE, "perturb_out.json")))
lines = []


def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); lines.append(s)


n, net = PJ["ZEE (h2-3, ER 0.30-0.35, bars 16, lat 0.3)"]["all"]["n"], PJ["ZEE (h2-3, ER 0.30-0.35, bars 16, lat 0.3)"]["all"]["net"]
w = net / n
nb_losses = [v["avg_loss"] for k, v in PJ.items() if isinstance(v, dict) and v.get("avg_loss", 0) < -150]
L_typ = sorted(nb_losses)[len(nb_losses) // 2]
L_tight = (-203.0 - 200.0 - 220.0 - 40.0) / 4
for lab, L in (("typical full-stop loss (median of neighbour runs)", L_typ), ("mean of tight's 4 losses", L_tight)):
    p_be = w / (w - L)
    P(f"break-even with {lab} {L:+.0f}$ and avg win {w:+.3f}$: loss rate {100*p_be:.2f}% -> WR {100*(1-p_be):.2f}%")
p_be = w / (w - L_typ)
ub95 = 1 - 0.05 ** (1 / n); ub975 = 1 - 0.025 ** (1 / n)
P(f"\nbinomial on 0 losses / {n}: one-sided 95% upper bound on the loss rate {100*ub95:.2f}% (WR >= {100*(1-ub95):.2f}%); two-sided 95% CI WR [{100*(1-ub975):.2f}%, 100%]")
for lab, p in (("break-even", p_be), ("tight overall 4/714", 4 / 714), ("ring around the box 14/1060", 14 / 1060), ("secure 30/2237", 30 / 2237)):
    P(f"   P(0 losses in {n} | true loss rate {100*p:.2f}% = {lab}) = {(1-p)**n:.3f}")
P("\nempirical-Bayes posterior mean loss rate for the box (Beta prior from a neighbourhood, then 0/308):")
for lab, a, b in (("ring 14/1060, full weight", 14, 1046), ("ring rate, weight = 308 trades", 14 / 1060 * 308, (1 - 14 / 1060) * 308),
                  ("tight minus the box 4/406, full weight", 4, 402), ("secure 30/2237, full weight", 30, 2207)):
    m = a / (a + b + n)
    P(f"   prior {lab:40s}: loss rate {100*m:.2f}% -> WR {100*(1-m):.2f}%")
W = json.load(open(os.path.join(HERE, "wf_out.json")))
P(f"\nwalk-forward out-of-sample: A (pick on Mar-Jun) {W['A']['chosen']['key']} Jul-Nov {W['A']['chosen']['jn']}; "
  f"B (pick on Jul-Nov) {W['B']['chosen']['key']} Mar-Jun {W['B']['chosen']['mj']}")
for d in ("A", "B"):
    fo, eo = W[d]["family_oos"], W[d]["eligible_oos"]
    P(f"   {d}: in-sample-100% family OOS {fo['L']}/{fo['n']} = WR {100*(1-fo['L']/fo['n']):.2f}%  vs every eligible combo OOS WR {100*(1-eo['L']/eo['n']):.2f}%  (Spearman IS vs OOS {W[d]['spearman']:+.3f})")
tpm = n / 7.95
for p in (0.006, 0.008, 0.010, 0.013):
    P(f"at loss rate {100*p:.1f}%: {tpm*p:.2f} losses / month ({tpm:.0f} trades / month) = one {L_typ:+.0f}$ loss every {1/(tpm*p):.1f} months; "
      f"net {tpm*((1-p)*w + p*L_typ):+.1f}$/month at 1 lot; P(>= 1 loss in the next 100 trades) {1-(1-p)**100:.2f}")
P("\ndoctrine (monitor/doctrine.py, mandatory for any Python win rate):")
import io, contextlib  # noqa: E402,E401
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    python_says("Zee's 100% zone (Python replay, PrimeXBT EUR/USD ticks)", win_pct=100.0, need_pct=round(100 * (1 - p_be), 1))
for s in buf.getvalue().splitlines():
    P(s)
open(os.path.join(HERE, "expected_out.txt"), "w").write("\n".join(lines))
