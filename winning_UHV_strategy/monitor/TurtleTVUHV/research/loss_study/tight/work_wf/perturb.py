"""perturb.py (work_wf) - engine runs around Zee's 100% file (2026-11-06 07-33-17.json), ONE input changed at a time; neighbour bands as
their own zones (their loss RATES); a fine ER heat map at humps 2-3; Zee's setting month by month. Writes perturb_out.json / .txt."""
import json
import os

import numpy as np

from common import run, summ, SPLIT, OUT, month

lines, J = [], {}


def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); lines.append(s)


def line(lab, r):
    a, m, j = summ(r), summ(r, hi=SPLIT), summ(r, lo=SPLIT)
    rate = 100 * a["L"] / a["n"] if a["n"] else float("nan")
    u = np.asarray(r["usd"]); avl = float(u[u <= 0].mean()) if (u <= 0).any() else 0.0
    P(f"{lab:34s} {a['n']:4d} tr {a['L']:2d} L  loss rate {rate:5.2f}%  WR {a['wr']:6.2f}%  net {a['net']:+9.2f}  | Mar-Jun {m['n']:3d}/{m['L']}L  Jul-Nov {j['n']:3d}/{j['L']}L"
      + (f"  avg loss {avl:+.0f}" if a["L"] else ""))
    J[lab] = {"all": a, "mj": m, "jn": j, "avg_loss": avl}
    return a


P("=== Zee's file, one input at a time (engine) ===")
z = run(); line("ZEE (h2-3, ER 0.30-0.35, bars 16, lat 0.3)", z)
REQ = [("ER max 0.33", {"InpUhvSafeErMax": "0.33"}), ("ER max 0.34", {"InpUhvSafeErMax": "0.34"}), ("ER max 0.36", {"InpUhvSafeErMax": "0.36"}),
       ("ER max 0.37", {"InpUhvSafeErMax": "0.37"}), ("ER max 0.40", {"InpUhvSafeErMax": "0.40"}),
       ("ER min 0.27", {"InpUhvSafeErMin": "0.27"}), ("ER min 0.28", {"InpUhvSafeErMin": "0.28"}), ("ER min 0.32", {"InpUhvSafeErMin": "0.32"}),
       ("humps 2-2", {"InpUhvSafeHumpsMax": "2"}), ("humps 2-4", {"InpUhvSafeHumpsMax": "4"}), ("humps 1-3", {"InpUhvSafeHumpsMin": "1"}),
       ("ER bars 12", {"InpUhvSafeErBars": "12"}), ("ER bars 20", {"InpUhvSafeErBars": "20"}), ("latency 0.5 s", {"InpUhvLatency": "0.5"})]
for lab, o in REQ:
    line(lab, run(o))
P("\n--- extras (same file, one input at a time) ---")
EXTRA = [("ER max 0.351", {"InpUhvSafeErMax": "0.351"}), ("ER max 0.353", {"InpUhvSafeErMax": "0.353"}), ("ER max 0.38", {"InpUhvSafeErMax": "0.38"}),
         ("ER max 0.45 (= tight)", {"InpUhvSafeErMax": "0.45"}), ("ER min 0.25", {"InpUhvSafeErMin": "0.25"}), ("ER min 0.29", {"InpUhvSafeErMin": "0.29"}),
         ("ER min 0.31", {"InpUhvSafeErMin": "0.31"}), ("humps 3-3", {"InpUhvSafeHumpsMin": "3"}), ("humps 2-5", {"InpUhvSafeHumpsMax": "5"}),
         ("humps 1-2", {"InpUhvSafeHumpsMin": "1", "InpUhvSafeHumpsMax": "2"})]
EXTRA += [(f"ER bars {b}", {"InpUhvSafeErBars": str(b)}) for b in (10, 14, 15, 17, 18, 24)]
EXTRA += [(f"latency {x} s", {"InpUhvLatency": str(x)}) for x in ("0.0", "0.1", "0.2", "0.4", "0.6", "0.8", "1.0", "1.5", "2.0", "3.0")]
EXTRA += [("spread guard off", {"InpUhvMaxTrigSpread": "0"}), ("spread guard 0.8", {"InpUhvMaxTrigSpread": "0.8"}),
          ("spread guard 1.2", {"InpUhvMaxTrigSpread": "1.2"}), ("NY rollover guard off", {"InpUhvNoClose": "0"})]
for lab, o in EXTRA:
    line(lab, run(o))

P("\n=== neighbour bands, each run as its own zone (engine) - the local loss RATE ===")
BANDS = [("h2-3 ER[.20,.25)", 2, 3, .20, .25), ("h2-3 ER[.25,.30)", 2, 3, .25, .30), ("h2-3 ER[.30,.35) = ZEE", 2, 3, .30, .35),
         ("h2-3 ER[.35,.40)", 2, 3, .35, .40), ("h2-3 ER[.40,.45)", 2, 3, .40, .45), ("h2-3 ER[.45,.50)", 2, 3, .45, .50),
         ("h2-3 ER[.35,.45)", 2, 3, .35, .45), ("h2-3 ER[.25,.30)+[.35,.40) ring", None, None, None, None),
         ("h1 ER[.30,.35)", 1, 1, .30, .35), ("h4 ER[.30,.35)", 4, 4, .30, .35), ("h4-6 ER[.30,.35)", 4, 6, .30, .35),
         ("h1 ER[.25,.40)", 1, 1, .25, .40), ("h4 ER[.25,.40)", 4, 4, .25, .40)]
ring = []
for lab, a, b, c, d in BANDS:
    if a is None:
        continue
    r = run({"InpUhvSafeHumpsMin": a, "InpUhvSafeHumpsMax": b, "InpUhvSafeErMin": f"{c:.2f}", "InpUhvSafeErMax": f"{d:.2f}"})
    line(lab, r)
    if lab in ("h2-3 ER[.25,.30)", "h2-3 ER[.35,.40)", "h1 ER[.30,.35)", "h4 ER[.30,.35)"):
        ring.append(J[lab]["all"])
rn, rL = sum(x["n"] for x in ring), sum(x["L"] for x in ring)
P(f"RING around Zee's box (h2-3 ER[.25,.30) + h2-3 ER[.35,.40) + h1 ER[.30,.35) + h4 ER[.30,.35)): {rL}/{rn} = loss rate {100*rL/rn:.2f}%")
J["ring"] = {"n": rn, "L": rL}

P("\n=== fine ER heat map at humps 2-3 (engine): losses / trades; rows ER min, cols ER max ===")
EMIN = [round(0.20 + 0.01 * i, 2) for i in range(15)]          # 0.20 .. 0.34
EMAX = [round(0.31 + 0.01 * i, 2) for i in range(20)]          # 0.31 .. 0.50
HM = {}
P("min\max " + "".join(f"{x:.2f}".rjust(8) for x in EMAX))
for a in EMIN:
    row = f"{a:.2f}    "
    for b in EMAX:
        if a >= b - 1e-9:
            row += "".rjust(8); continue
        r = run({"InpUhvSafeErMin": f"{a:.2f}", "InpUhvSafeErMax": f"{b:.2f}"})
        s = summ(r); HM[f"{a:.2f}-{b:.2f}"] = s
        row += f"{s['L']}/{s['n']}".rjust(8)
    P(row)
zero = [(k, v) for k, v in HM.items() if v["L"] == 0]
P(f"zero-loss cells: {len(zero)} of {len(HM)}; with >= 250 trades: " + ", ".join(f"{k}({v['n']})" for k, v in sorted(zero, key=lambda kv: -kv[1]['n']) if v['n'] >= 250))
J["heatmap"] = HM

P("\n=== Zee's setting month by month (engine; fill time UTC) ===")
t = np.asarray(z["t"]); u = np.asarray(z["usd"])
mons = sorted(set(month(x) for x in t))
MB = {}
for m in mons:
    msk = np.array([month(x) == m for x in t])
    n = int(msk.sum()); L = int((u[msk] <= 0).sum())
    MB[m] = {"n": n, "L": L, "net": round(float(u[msk].sum()), 2), "min_win": round(float(u[msk].min()), 2)}
    P(f"   {m}: {n:3d} trades  {L} losses  net {u[msk].sum():+8.2f}  smallest result {u[msk].min():+.2f}" + ("   (from Mar 6)" if m == "2026-03" else "   (Nov 1-4 only)" if m == "2026-11" else ""))
J["months"] = MB
# the neighbours by month too (their losses)
for lab, o in (("tight h2-3 ER .30-.45", {"InpUhvSafeErMax": "0.45"}), ("secure h2-5 ER .15-.45", {"InpUhvSafeHumpsMax": "5", "InpUhvSafeErMin": "0.15", "InpUhvSafeErMax": "0.45"})):
    r = run(o); tt = np.asarray(r["t"]); uu = np.asarray(r["usd"])
    P(f"   {lab}: " + "  ".join(f"{m[5:]} {int(sum(1 for x, y in zip(tt, uu) if month(x) == m and y <= 0))}/{int(sum(1 for x in tt if month(x) == m))}" for m in mons))
json.dump(J, open(os.path.join(OUT, "perturb_out.json"), "w"), indent=1)
open(os.path.join(OUT, "perturb_out.txt"), "w").write("\n".join(lines))
