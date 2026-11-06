"""run.py - score every rule in rules.py with api.report and save the results (results.txt, results.json, hits.json).
  1. crash check: every rule is called directly on all blind trades (api.score would silently keep a trade on an exception)
  2. look-ahead audit: every rule is re-run on arrays CUT at bar k (humps filtered to known_at_bar <= k); any read past k
     raises, any difference in the answer is reported
  3. api.report for every rule (the official numbers)
  4. hit matrix: which rules skip each of the 21 batch losses and the 42 twins
Run: py run.py [rule_name ...]"""
import contextlib
import io
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, STUDY)
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules as R  # noqa: E402

A = api.A
BLIND = [api._blind(t) for t in api.TRADES]
only = set(sys.argv[1:])
RULES = [r for r in R.ALL if not only or r.__name__ in only]


class Cut:
    """per-trade view of the arrays, ending at bar k (reading k+1 or later raises IndexError)"""
    def __init__(self, k):
        for name in ("t", "o", "h", "l", "c", "v", "atr", "adx", "camEff", "camStk", "camT", "camHV", "camLV", "camL0V"):
            setattr(self, name, getattr(A, name)[:k + 1])
        self.humps = A.humps[A.humps[:, 7] <= k]
        self.PIP = A.PIP

    def pivots(self, k, p=1, look=120):
        return api.Arrays.pivots(self, k, p, look)

    def humps_known(self, k):
        H = self.humps
        return H[H[:, 7] <= k] if len(H) else H


lines, out = [], {}
for r in RULES:
    name = r.__name__
    crash, diff, first_err = 0, 0, ""
    for t in BLIND:
        try:
            full = bool(r(t, A))
        except Exception as e:                             # noqa: BLE001
            crash += 1; first_err = first_err or repr(e); continue
        try:
            cut = bool(r(t, Cut(t["k"])))
        except IndexError:
            cut = None
        except Exception:                                  # noqa: BLE001
            cut = None
        if cut is None or cut != full:
            diff += 1
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res = api.report(r, name)
    line = buf.getvalue().rstrip()
    line += f"  | crashes {crash}  look-ahead diffs {diff}"
    print(line, flush=True)
    lines.append(line)
    res["crashes"], res["lookahead_diffs"], res["first_err"] = crash, diff, first_err
    out[name] = res

# hit matrix on the batch
batch = json.load(open(os.path.join(STUDY, "batch_1.json"), encoding="utf-8"))
byid = {t["id"]: t for t in BLIND}
hits = {"losses": {}, "twins": {}}
for grp in ("losses", "twins"):
    for card in batch[grp]:
        t = byid[card["id"]]
        hits[grp][card["id"]] = [r.__name__ for r in RULES if r(t, A)]

tag = "_".join(sorted(only)) if only else "all"
with open(os.path.join(HERE, f"results_{tag}.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
json.dump(out, open(os.path.join(HERE, f"results_{tag}.json"), "w", encoding="utf-8"), indent=1)
json.dump(hits, open(os.path.join(HERE, f"hits_{tag}.json"), "w", encoding="utf-8"), indent=1)
print()
for grp in ("losses", "twins"):
    print(grp)
    for k_, v_ in hits[grp].items():
        print(f"  {k_:16s} {', '.join(v_) if v_ else '-'}")
