"""dexter_validate.py - the grid's candidates in MT5 (rig axi7, view EA, XAUUSD_BB M15, 2026.01.01-10.17, no delay)
beside the tester's own 2026 numbers for the same settings. py dexter_validate.py -> simdata/dexter_validate.json"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "monitor" / "strategy_lab"))
import axi_rig, sim  # noqa: E402

NAME = "2026-10-26 01-48-34"
CANDS = [("saved", {}), ("stop $15", {"InpSlMode": "2", "InpSlUsd": "15"}),
         ("stop $15 + partial 0.5R", {"InpSlMode": "2", "InpSlUsd": "15", "InpXP1R": "0.5", "InpXP1Frac": "0.5"})]
A = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp(); B = datetime(2026, 10, 17, tzinfo=timezone.utc).timestamp()


def tester2026(inp):
    tr = [x for x in sim.simulate(inp, ds="m15")[0] if x[10] == 0 and A <= x[1] < B]
    p = np.array([x[6] for x in tr]); w = p > 0
    return {"n": len(p), "net": round(float(p.sum())), "wr": round(100 * float(w.mean()), 1), "worst": round(float(p.min())),
            "pf": round(float(p[w].sum() / -p[~w].sum()), 2)}


def main():
    d = json.loads((HERE / "settings" / "saved" / f"{NAME}.json").read_text(encoding="utf-8"))
    base = dict(axi_rig.ea_defaults("Saad_strategy_15min_view"), **d["inputs"]); base.pop("InpExportM1", None)
    out = []
    axi_rig.kill_rig("axi7"); axi_rig.compile_ea("Saad_strategy_15min_view", rig="axi7")
    for lab, sets in CANDS:
        inp = dict(base, **sets)
        t = tester2026(inp)
        r = {}
        for attempt in range(3):
            r = axi_rig.run("Saad_strategy_15min_view", "XAUUSD_BB", "M15", dict(inp, InpLogCsv="false"), frm="2026.01.01", to="2026.10.17",
                            deposit=100000, rig="axi7", tag="dexval", exec_mode=0)
            if r.get("error") not in ("authorization failed", "no report"):
                break
            axi_rig.kill_rig("axi7")
        ts = r.get("trade_stats") or {}
        m = {"n": r.get("trades"), "net": r.get("net"), "pf": r.get("pf"), "dd": r.get("dd"), "worst": ts.get("largest_loss"), "wr": r.get("wr"), "error": r.get("error")}
        out.append({"label": lab, "sets": sets, "tester_2026": t, "mt5_2026": m})
        print(lab, "| tester", t, "| MT5", m, flush=True)
        (HERE / "simdata" / "dexter_validate.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
