"""verify_final.py - exec every standalone rule string of final_rules.py in a fresh namespace (numpy + math only), score it with
api.score / api.report, and record which of the batch-2 losses each rule catches. Writes final_scores.json."""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, STUDY)
sys.path.insert(0, HERE)
import api  # noqa: E402
from final_rules import RULES  # noqa: E402

batch = json.load(open(os.path.join(STUDY, "batch_2.json"), encoding="utf-8"))
ids = [c["id"] for c in batch["losses"]]
byid = {t["id"]: t for t in api.TRADES}
out = []
for r in RULES:
    ns = {"np": np, "math": math}
    exec(r["code"], ns)
    f = ns["rule"]
    res = api.report(f, r["rule_id"][:28])
    caught = []
    for i in ids:
        try:
            if f(api._blind(byid[i]), api.A):
                caught.append(i)
        except Exception:      # noqa: BLE001
            pass
    out.append({**r, "score": res, "batch_losses_caught": caught})
json.dump(out, open(os.path.join(HERE, "final_scores.json"), "w"), indent=1)
print()
for o in out:
    print(o["rule_id"], "->", o["batch_losses_caught"])
