"""tv_sweep.py - measure turtle.pine's scorecard under many settings, on the real indicator.

    python pine/tv_sweep.py plan.json results.jsonl

plan.json: {"base": {name: value, ...}, "runs": [{"label": "...", "set": {name: value}}, ...]}
Every run starts from "base" + its own overrides, so runs never leak into each other. Each
result line: label, settings, labels judged (n), won, win rate, older/newer half, sim P&L.
At the end the chart is put back on "base".
"""
import json
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import tv_lab as L  # noqa: E402


def read_stable(prev=None, tries=8):
    """Read the scorecard until two reads agree (TradingView recomputes for a few seconds)."""
    last = None
    for _ in range(tries):
        r = L.parse_score(L.score(wait=2.5))
        if r and last and r == last and (prev is None or r != prev or _ > 3):
            return r
        last = r
    return last


def main(plan_path, out_path):
    plan = json.load(open(plan_path, encoding="utf-8"))
    sid = L.the_study()
    src_names = L.names(L.SRC.read_text(encoding="utf-8"))
    base = dict(plan["base"])
    # every setting any run touches must be reset between runs - fill missing ones from the chart
    current = L.by_name(L.inputs_of(sid), src_names)
    for run in plan["runs"]:
        for k in run.get("set", {}):
            if k not in base:
                base[k] = current[k]
    prev = None
    with open(out_path, "a", encoding="utf-8") as out:
        for run in plan["runs"]:
            cfg = dict(base)
            cfg.update(run.get("set", {}))
            L.set_by_name(sid, src_names, cfg)
            r = read_stable(prev)
            prev = r
            rec = {"label": run["label"], "set": run.get("set", {}), **(r or {"n": 0})}
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(f'{run["label"]:<34} n={rec.get("n")!s:>4}  wr={rec.get("wr")!s:>5}  '
                  f'old={rec.get("older")} new={rec.get("newer")}  random={rec.get("random")}% edge={rec.get("edge")}', flush=True)
    L.set_by_name(sid, src_names, base)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
