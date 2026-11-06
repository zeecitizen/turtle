"""run.py - score batch 5 rules with the harness. Each rule's SOURCE is exec'd in a fresh namespace (so the numbers belong to the exact
code that is shipped), then api.report runs it. Also lists which of the 21 batch-5 losses each rule removes.
Usage: py agents/batch_5/run.py [rule_name ...]        writes agents/batch_5/results.json + results.log"""
import inspect
import json
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules  # noqa: E402

BATCH = json.load(open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "batch_5.json"), encoding="utf-8"))
MY = {L["id"] for L in BATCH["losses"]}
BYID = {t["id"]: t for t in api.TRADES}


def compiled(name):
    src = textwrap.dedent(inspect.getsource(getattr(rules, name)))
    src = src.replace(f"def {name}(", "def rule(", 1)
    ns = {}
    exec(src, ns)                                   # fresh namespace: no module globals
    return ns["rule"], src


if __name__ == "__main__":
    names = sys.argv[1:] or [n for n, _ in inspect.getmembers(rules, inspect.isfunction) if n.startswith("rule_")]
    out = {}
    lines = []
    for n in names:
        f, src = compiled(n)
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = api.report(f, n)
        line = buf.getvalue().strip()
        print(line)
        lines.append(line)
        mine = sorted(i for i in MY if f(api._blind(BYID[i]), api.A))
        print(f"    batch-5 losses removed: {len(mine)} {mine}")
        lines.append(f"    batch-5 losses removed: {len(mine)} {mine}")
        out[n] = {"score": r, "batch5_losses": mine, "code": src}
    if not sys.argv[1:]:
        json.dump(out, open(os.path.join(HERE, "results.json"), "w", encoding="utf-8"), indent=1)
        open(os.path.join(HERE, "results.log"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
