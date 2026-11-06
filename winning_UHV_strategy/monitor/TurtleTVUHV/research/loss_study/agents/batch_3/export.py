"""export.py - every rule in rules.py as a standalone `def rule(t, A):` source, exec'd alone (np + math only) and re-scored with api.score."""
import inspect, json, math, os, re, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import api  # noqa: E402
import rules as M  # noqa: E402
out = []
for n, f in inspect.getmembers(M, inspect.isfunction):
    if f.__module__ != M.__name__:
        continue
    src = inspect.getsource(f)
    src = re.sub(r"^def\s+" + n + r"\s*\(", "def rule(", src, count=1)
    ns = {"np": np, "math": math}
    exec(src, ns)
    for t in api.TRADES[:50]:
        ns["rule"](api._blind(t), api.A)
    r = api.score(ns["rule"])
    r0 = api.score(f)
    assert r == r0, n
    a, tr, te = r["all"], r["train"], r["test"]
    L = a["losers_removed"]
    if tr["lift"] and te["lift"] and L >= 4 and tr["lift"] >= 4 and te["lift"] >= 4:
        v = "EXCELLENT"
    elif tr["lift"] and te["lift"] and L >= 4 and tr["lift"] >= 2 and te["lift"] >= 2:
        v = "GOOD"
    else:
        v = "NOT SELECTIVE"
    out.append({"rule_id": n, "doc": (f.__doc__ or "").strip(), "code": src, "lift_all": a["lift"], "lift_train": tr["lift"], "lift_test": te["lift"],
                "losers_removed": L, "winners_removed": a["winners_removed"], "verdict_auto": v, "wr_after": a["wr_after"],
                "net": a["net_change_usd_1lot"], "tagged": r["tagged_out"], "train_LW": (tr["losers_removed"], tr["winners_removed"]),
                "test_LW": (te["losers_removed"], te["winners_removed"])})
json.dump(out, open(os.path.join(HERE, "rules_scored.json"), "w"), indent=1)
for o in sorted(out, key=lambda o: -(o["lift_all"] or 0)):
    print(f"{o['rule_id']:24s} {o['verdict_auto']:14s} all x{o['lift_all']}  tr x{o['lift_train']} {o['train_LW']}  te x{o['lift_test']} {o['test_LW']}  L{o['losers_removed']} W{o['winners_removed']}  WR {o['wr_after']}  net {o['net']:+,.0f}  Zee22 {o['tagged']}")
