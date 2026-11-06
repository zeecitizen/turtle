"""final_scores.py - every r_* rule in rules.py: api.score numbers + verdict (GOOD: lift>=2 on train AND test and >=4 losers removed;
EXCELLENT: lift>=4 on both), written to final_scores.json; plus which GOOD/EXCELLENT rules remove each batch-4 loss and twin."""
import inspect
import io
import json
import os
import sys
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules  # noqa: E402

B = json.load(open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "batch_4.json"), encoding="utf-8"))
byid = {t["id"]: t for t in api.TRADES}
out = {}
for n, f in inspect.getmembers(rules, inspect.isfunction):
    if not n.startswith("r_"):
        continue
    buf = io.StringIO()
    with redirect_stdout(buf):
        r = api.report(f, n)
    a, tr, te = r["all"], r["train"], r["test"]
    ok = lambda x, th: x is not None and x >= th
    verdict = ("EXCELLENT" if ok(tr["lift"], 4) and ok(te["lift"], 4) and a["losers_removed"] >= 4 else
               "GOOD" if ok(tr["lift"], 2) and ok(te["lift"], 2) and a["losers_removed"] >= 4 else "NOT SELECTIVE")
    out[n] = {"line": buf.getvalue().strip(), "lift_all": a["lift"], "lift_train": tr["lift"], "lift_test": te["lift"],
              "losers_removed": a["losers_removed"], "winners_removed": a["winners_removed"], "net": a["net_change_usd_1lot"],
              "tagged": r["tagged_out"], "verdict": verdict, "doc": (f.__doc__ or "").strip(), "code": inspect.getsource(f)}
good = [n for n, v in out.items() if v["verdict"] != "NOT SELECTIVE"]
per = {}
for i, L in enumerate(B["losses"]):
    t = api._blind(byid[L["id"]])
    per[L["id"]] = [n for n in good if getattr(rules, n)(t, api.A)]
twins = {n: sum(1 for w in B["twins"] if getattr(rules, n)(api._blind(byid[w["id"]]), api.A)) for n in out}
json.dump({"rules": out, "per_loss_good_rules": per, "twins_removed_of_44": twins}, open(os.path.join(HERE, "final_scores.json"), "w"), indent=1)
for n, v in sorted(out.items(), key=lambda kv: -(kv[1]["lift_all"] or 0)):
    print(f"{v['verdict']:13s} twins {twins[n]:2d}/44  {v['line']}")
print()
for k, v in per.items():
    print(k, v)
