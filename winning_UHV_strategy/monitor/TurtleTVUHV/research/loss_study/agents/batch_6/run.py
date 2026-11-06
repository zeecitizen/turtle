"""run.py - score every rule in rules.py (or the names given) with api.report; also prints which batch-6 losses each rule removes.
py agents/batch_6/run.py [rule_name ...]"""
import importlib
import inspect
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, LS)
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules  # noqa: E402

importlib.reload(rules)
B = json.load(open(os.path.join(LS, "batch_6.json"), encoding="utf-8"))
byid = {t["id"]: t for t in api.TRADES}
LOSS_IDS = [L["id"] for L in B["losses"]]
TWIN_IDS = [w["id"] for w in B["twins"]]


def batch_hits(fn):
    lo = [i for i in LOSS_IDS if fn(api._blind(byid[i]), api.A)]
    tw = [i for i in TWIN_IDS if fn(api._blind(byid[i]), api.A)]
    return lo, tw


if __name__ == "__main__":
    names = sys.argv[1:] or [n for n, f in inspect.getmembers(rules, inspect.isfunction) if n.startswith("rule_")]
    out = {}
    for n in names:
        fn = getattr(rules, n)
        r = api.report(fn, n)
        lo, tw = batch_hits(fn)
        print(f"{'':28s}   batch-6 losses removed {len(lo)}/22 {lo}  twins removed {len(tw)}/44")
        out[n] = {"score": r, "batch_losses": lo, "batch_twins": tw}
    json.dump(out, open(os.path.join(HERE, "scores_last.json"), "w"), indent=1)
