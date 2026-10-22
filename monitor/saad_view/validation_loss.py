"""validation_loss.py - the loss cutter's suggestions, validated: the loss scan on the primary save (the same moves and the same limits the
page's ✂️ loss cutter ranks), the top ones run in the tester and in MT5 (2026, 1-minute, invisible rig). Writes simdata/validation_loss.json.
py validation_loss.py [--top N]"""
import json, sys, time, datetime as dt
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import exitlab, scan, server, sim
from validation_run import mt5
OUT = r"C:\Users\zeesh\turtle\monitor\saad_view\simdata\validation_loss.json"

def cuts(W, tol=1.5, keep=0.85):                     # the loss cutter's own rule (static/exitlab_research.js lossCuts)
    now = W.now; L0 = now["L"]; out = []
    for m in W.moves:
        r = m["r"]
        if not r or r["stuck"] or r["n"] < 20 or not r.get("L") or r["L"]["margin"] is None: continue
        L = r["L"]
        c = {k: (abs(L0[k2]) - abs(L[k2])) / abs(L0[k2]) for k, k2 in (("avg", "avg_loss"), ("tail", "tail"), ("worst", "worst"))}
        c["lpt"] = (L0["lpt"] - L["lpt"]) / L0["lpt"] if L0["lpt"] else 0
        dm = L["margin"] - L0["margin"]
        if not (c["avg"] >= 0.02 or c["tail"] >= 0.03 or c["lpt"] >= 0.02 or c["worst"] >= 0.05): continue
        if c["avg"] <= -0.05 or c["tail"] <= -0.05 or dm < -0.3: continue
        if L["wr"] < L0["wr"] - tol or r["n"] < keep * now["n"]: continue
        if (now["train"] > 0 and r["train"] <= 0) or (now["test"] > 0 and r["test"] <= 0): continue
        out.append((dm + 1.5 * c["tail"] + c["avg"] + c["lpt"], m))
    out.sort(key=lambda x: -x[0])
    return [m for _, m in out]

def main():
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 10
    base = server.full_inputs(json.load(open(r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved\2026-10-21 05-55-20.json"))["inputs"])
    base["InpXEntryWait"] = "true"
    j = exitlab.Job("sweep", base, "year1", lab={}, sets={}, focus="loss"); j.run()
    W = j.result
    picks = cuts(W)[:top]
    rows = []
    for i, m in enumerate(picks):
        s = dict(base, **m["sets"], **m["xs"])
        import numpy as np
        tr, _, _ = sim.simulate(s, ds="year1"); r = tr[tr[:, 10] == 0]
        tn, tp = int(len(r)), round(float(r[:, 6].sum()))
        rid, mn, mp = mt5(s, f"loss-cut {m['key']} {m['to']}")
        ok = mn is not None and abs(tn - mn) <= 0.10 * max(tn, 1) and (tp > 0) == (mp > 0)
        rows.append({"key": m["key"], "label": m["label"], "group": "the loss cutter", "from": m["from"], "to": m["to"],
                     "tester": {"trades": tn, "net": tp}, "mt5": {"trades": mn, "net": mp, "run": rid}, "match": bool(ok),
                     "at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "why": m.get("why", "")})
        json.dump({"base": "2026-10-21 05-55-20", "count": len(rows), "of": len(picks), "rows": rows}, open(OUT, "w"), indent=1)
        print(i + 1, len(picks), m["label"], tn, tp, mn, mp, "MATCH" if ok else "differs", flush=True)

if __name__ == "__main__":
    main()
