"""run_rules.py (batch_8) - scores every rule in rules.py with api.report and lists which of batch 8's 22 losses each one removes.
Run from research/loss_study:  py agents/batch_8/run_rules.py [rule_name ...]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, LS)
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules  # noqa: E402

B8 = {c["id"] for c in json.load(open(os.path.join(LS, "batch_8.json"), encoding="utf-8"))["losses"]}
BY = {t["id"]: t for t in api.TRADES}
want = sys.argv[1:]
out = {}
for f in rules.ALL:
    if want and f.__name__ not in want:
        continue
    r = api.report(f, f.__name__)
    caught = sorted(i for i in B8 if f(api._blind(BY[i]), api.A))
    print(f"{'':28s} batch-8 losses removed ({len(caught)}/22): {', '.join(caught)}")
    out[f.__name__] = {"score": r, "batch8": caught}
json.dump(out, open(os.path.join(HERE, "scores.json"), "w"), indent=1)
