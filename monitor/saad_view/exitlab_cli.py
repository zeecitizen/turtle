"""exitlab_cli.py - the Exit Lab as a command line, for Claude's exit research (Zee 2026-10-21: "i want it to be a claude intelligence ai based lab
where the exit's philosophy is refined by claude by doing research").

  py monitor/saad_view/exitlab_cli.py --base <settings.json> --ds m15 diagnose
  py monitor/saad_view/exitlab_cli.py --base <settings.json> --ds m15 test --lab '{"tr": 2, "tr_k": 2, "tr_act": 1}' [--sets '{"InpSlAtrMult": "1.4"}']
  py monitor/saad_view/exitlab_cli.py --base <settings.json> --ds m15 givebacks --n 30       # the winners that gave back the most, with context
  py monitor/saad_view/exitlab_cli.py --base <settings.json> --ds m15 slice --by hour|weekday|side|year|adx|atr|mfe_r|bars   # where the giveback sits
  py monitor/saad_view/exitlab_cli.py blocks                                                 # the building blocks and their fields

Every number is the Turtle TV Tester's (Python): a hypothesis until MT5 confirms it. Output is JSON."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np  # noqa: E402

import exitlab  # noqa: E402
import server  # noqa: E402
import sim  # noqa: E402


def trades_frame(inp, ds, lab=None, sets=None):
    _, real, oe = exitlab.run(inp, ds, lab=lab, sets=sets)
    D = sim.data(ds)
    rows = []
    for x in real:
        k0, k1 = int(x[11]), int(x[12])
        R = max(float(x[17]), 0.05)
        lots = float(x[18]) or float(inp.get("InpLots", 1))
        mfe_usd = float(x[15]) * lots * 100.0
        t = datetime.fromtimestamp(int(x[1]), timezone.utc)
        rows.append({"entry": t.strftime("%Y-%m-%d %H:%M"), "side": "BUY" if x[0] > 0 else "SELL", "pnl": round(float(x[6])), "why": exitlab.WHY.get(int(x[13]), ""),
                     "R": round(R, 2), "mfe_r": round(float(x[15]) / R, 2), "mae_r": round(float(x[16]) / R, 2), "result_r": round(float(x[6]) / (R * lots * 100), 2),
                     "giveback": round(mfe_usd - float(x[6])), "bars": k1 - k0, "hour": t.hour, "weekday": t.strftime("%a"), "year": t.year,
                     "adx": round(float(D["adx"][max(0, k0 - 1)]), 1), "atr": round(float(D["atr"][max(0, k0 - 1)]), 2), "k_in": k0, "k_out": k1})
    return rows, oe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="JSON file with the EA settings (the page writes it for each research job)")
    ap.add_argument("--ds", default="m15", choices=["year", "m15"])
    ap.add_argument("cmd", choices=["diagnose", "test", "givebacks", "slice", "blocks"])
    ap.add_argument("--lab", default="{}")
    ap.add_argument("--sets", default="{}")
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--by", default="hour")
    a = ap.parse_args()
    if a.cmd == "blocks":
        print(exitlab.blocks_text())
        return
    inp = server.full_inputs(json.loads(Path(a.base).read_text(encoding="utf-8")) if a.base else {})
    lab, sets = json.loads(a.lab), json.loads(a.sets)
    win, labels = exitlab.window_of(a.ds, inp)
    if a.cmd == "diagnose":
        d = exitlab.diagnose(inp, a.ds)
        d.pop("scatter", None); d.pop("trades", None)
        print(json.dumps(d, default=str))
    elif a.cmd == "test":
        sets2 = dict({} if str(inp.get("InpExitMode")) in ("1", "2") or not lab else {"InpExitMode": "1"}, **sets)
        _, real, oe = exitlab.run(inp, a.ds, lab=lab or None, sets=sets2)
        s = exitlab.stats(real, win, open_end=oe)
        _, b, boe = exitlab.run(inp, a.ds)
        bs = exitlab.stats(b, win, open_end=boe)
        out = {"labels": labels, "exit": exitlab.describe(lab) if lab else "the EA's own exit", "sets": sets}
        for nm, x in (("this", s), ("yours", bs)):
            out[nm] = {"train": x["train"], "test": x["test"], "total": x["total"], "wr": x["all"]["wr"], "pf": x["all"]["pf"], "dd": x["all"]["dd"], "n": x["all"]["n"],
                       "why": x["why"], "sides": x["sides"], "stuck": x["stuck"]}
        print(json.dumps(out, default=str))
    elif a.cmd == "givebacks":
        rows, _ = trades_frame(inp, a.ds, lab, sets)
        win_rows = sorted([r for r in rows if r["pnl"] > 0], key=lambda r: -r["giveback"])
        tot = sum(r["giveback"] for r in rows if r["pnl"] > 0)
        print(json.dumps({"winners": len(win_rows), "giveback_total": tot, "top": win_rows[:a.n]}, default=str))
    elif a.cmd == "slice":
        rows, _ = trades_frame(inp, a.ds, lab, sets)
        key = {"hour": lambda r: r["hour"], "weekday": lambda r: r["weekday"], "side": lambda r: r["side"], "year": lambda r: r["year"],
               "adx": lambda r: int(r["adx"] // 10 * 10), "atr": lambda r: round(r["atr"] // 2 * 2), "mfe_r": lambda r: min(8, int(r["mfe_r"])),
               "bars": lambda r: min(64, 2 ** int(np.log2(max(1, r["bars"])))), "why": lambda r: r["why"]}[a.by]
        g = {}
        for r in rows:
            d = g.setdefault(str(key(r)), {"n": 0, "wins": 0, "net": 0, "giveback": 0})
            d["n"] += 1; d["wins"] += r["pnl"] > 0; d["net"] += r["pnl"]; d["giveback"] += r["giveback"] if r["pnl"] > 0 else 0
        print(json.dumps({"by": a.by, "groups": g}, default=str))


if __name__ == "__main__":
    main()
