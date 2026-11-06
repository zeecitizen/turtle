"""dexter_grid.py - the win-rate / worst-loss / net trade-off of a saved setting, mapped on a grid of its stop and exit
levers with the Turtle TV tester (4-year 15-minute data, tune 2023-24 / judge 2025-26). Hypotheses for MT5.
py dexter_grid.py ["saved name"]  -> simdata/dexter_grid.json"""
import itertools, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "monitor" / "strategy_lab"))
import axi_rig, optimizer, sim  # noqa: E402
from dexter_search import stats  # noqa: E402

TARGETS = [("target $8", {"InpXTgt": "4", "InpXTgtK": "8"}), ("target $12", {"InpXTgt": "4", "InpXTgtK": "12"}),
           ("target $16", {"InpXTgt": "4", "InpXTgtK": "16"}), ("target $20", {"InpXTgt": "4", "InpXTgtK": "20"}), ("target as saved", {})]
STOPS = [(f"stop ${v}", {"InpSlMode": "2", "InpSlUsd": str(v)}) for v in (10, 15, 20, 25, 30)] + \
        [(f"ATR stop x{v}", {"InpSlMode": "1", "InpSlAtrMult": str(v)}) for v in (1.5, 2.0, 2.5)] + [("stop as saved", {})]
TIMES = [("no time stop", {}), ("time stop 16", {"InpXMaxBars": "16"}), ("time stop 32", {"InpXMaxBars": "32"})]
PARTS = [("no partial", {}), ("partial 0.5R", {"InpXP1R": "0.5", "InpXP1Frac": "0.5"})]
BES = [("no breakeven", {}), ("breakeven 1R", {"InpXBeR": "1.0"})]


def main(name):
    d = json.loads((HERE / "settings" / "saved" / f"{name}.json").read_text(encoding="utf-8"))
    base = dict(axi_rig.ea_defaults("Saad_strategy_15min_view"), **d["inputs"])
    window = optimizer.Optimizer(base, ds="m15").window
    combos = list(itertools.product(TARGETS, STOPS, TIMES, PARTS, BES))
    done = [0]; t0 = time.time()
    def one(c):
        sets, lab = {}, []
        for l, s in c:
            sets.update(s); lab.append(l)
        st = stats(sim.simulate(dict(base, **sets), ds="m15")[0], window)
        done[0] += 1
        if done[0] % 40 == 0:
            print(done[0], "/", len(combos), round(time.time() - t0), "s", flush=True)
        return {"label": " · ".join(lab), "sets": sets, "stats": st}
    with ThreadPoolExecutor(max_workers=5) as ex:
        rows = list(ex.map(one, combos))
    out = {"start": name, "window": window, "rows": rows}
    (HERE / "simdata" / "dexter_grid.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("done", len(rows), round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2026-10-26 01-48-34")
