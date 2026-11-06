import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
TF = json.load(open(os.path.join(HERE, "tickfeats.json")))
SPLIT = 1782864000
ST = {st: json.load(open(os.path.join(HERE, "..", f"trades_{st}.json"), encoding="utf-8")) for st in ("tight", "secure", "base")}
keys = sys.argv[1:] or ["cyc_60"]
for key in keys:
    print("==", key)
    for st in ("tight", "secure", "base"):
        R = ST[st]
        x = np.array([TF[t["id"]][key] for t in R], float); w = np.array([t["win"] for t in R]); tr = np.array([t["t_dec"] < SPLIT for t in R])
        vals = np.unique(x)
        if len(vals) <= 12:
            bins = [(v, v) for v in vals]
        else:
            qs = np.unique(np.quantile(x, [0, .2, .4, .6, .8, .9, .95, 1.0])); bins = list(zip(qs[:-1], qs[1:]))
        line = []
        for a, b in bins:
            m = (x == a) if a == b else ((x >= a) & ((x < b) if b < bins[-1][1] else (x <= b)))
            n = int(m.sum()); L = int((~w[m]).sum())
            ntr, Ltr = int((m & tr).sum()), int((~w[m & tr]).sum()); nte, Lte = int((m & ~tr).sum()), int((~w[m & ~tr]).sum())
            lab = f"{a:g}" if a == b else f"[{a:.3g},{b:.3g}]"
            line.append(f"{lab}: {n} L{L} {100*L/max(n,1):.1f}% (tr {Ltr}/{ntr} {100*Ltr/max(ntr,1):.1f} te {Lte}/{nte} {100*Lte/max(nte,1):.1f})")
        print(f"  {st:6s} " + " | ".join(line))
