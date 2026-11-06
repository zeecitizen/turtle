"""verify_rules.py (batch_8) - for every rule in rules.ALL: takes the function's OWN source, renames it to `def rule(t, A)`, execs it in a
fresh namespace (only numpy as np + math), scores it with api.report, and splits the removed losers by exit kind (why 1 = stop, 8 = forced
weekly-close / 24 h exit). Writes final_rules.json (code + scores + batch-8 losses removed).
Run from research/loss_study:  py agents/batch_8/verify_rules.py"""
import inspect
import json
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, LS)
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules  # noqa: E402

B8 = {c["id"] for c in json.load(open(os.path.join(LS, "batch_8.json"), encoding="utf-8"))["losses"]}
out = []
for f in rules.ALL:
    src = inspect.getsource(f)
    code = re.sub(r"^def \w+\(t, A\):", "def rule(t, A):", src, count=1)
    ns = {"np": np, "math": math}
    exec(code, ns)
    rule = ns["rule"]
    r = api.report(rule, f.__name__)
    why = {}
    b8 = []
    for t in api.TRADES:
        b = api._blind(t)
        try:
            sk = bool(rule(b, api.A))
        except Exception as e:                                        # noqa: BLE001
            print("   !! rule raised", f.__name__, repr(e)); sk = False
        if sk and not t["win"]:
            why[t["why"]] = why.get(t["why"], 0) + 1
            if t["id"] in B8:
                b8.append(t["id"])
    print(f"{'':28s} removed losers by exit: {dict(sorted(why.items()))}   batch-8 ({len(b8)}): {', '.join(sorted(b8))}")
    out.append({"rule_id": f.__name__, "code": code, "score": r, "losers_by_why": why, "batch8": sorted(b8)})
json.dump(out, open(os.path.join(HERE, "final_rules.json"), "w", encoding="utf-8"), indent=1)
