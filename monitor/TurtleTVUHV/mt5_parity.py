r"""mt5_parity.py - does the Turtle TV UHV tester (uhv_engine, InpUhvExec 1) give what MT5's Strategy Tester gives?

Runs the native EA (mt5/ZeeUHV_*.mq5) in the PXBT rig with RANDOM DELAY on real ticks and compares, trade by trade, with the engine on the
same settings:
  entries   the same tick (millisecond) and side
  outcomes  MT5's "target held at the broker" result of each trade against the engine's probability of a win over every delay
            (a contradiction = MT5 lost a trade the engine says always wins, or won one it says always loses)
  totals    MT5's trades not at target / net against the engine's average over every delay (+- its run-to-run spread)
PASS = no impossible outcome, and at most one run in twenty beyond 2 run-to-run spreads. The last line prints PASS or FAIL (exit code 0 / 1).

    py monitor/TurtleTVUHV/mt5_parity.py [runs of B3, default 2] [only: a name filter]

Zee 2026-11-14: "fix our internal python tester so it has no or near zero differences with MT5 tester ... then instead of going to MT5 for
each run we can rely on the internal python tester". Run this after any change to uhv_engine.py / uhv_filters.py / uhv_diamond.py / the EA."""
import datetime as dt
import glob
import json
import os
import re
import shutil
import sys
import time

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "strategy_lab"))
import numpy as np  # noqa: E402

import axi_rig  # noqa: E402
import uhv_engine as U  # noqa: E402

COMMON = r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files"
FRM, TO = "2026.03.06", "2026.11.05"
CUT = dt.datetime(2026, 11, 5, tzinfo=dt.timezone.utc).timestamp()
OUT = os.path.join(HERE, "runs", "mt5_parity")
CC = {"InpUhvEntry": "0", "InpUhvPreBreak": "0"}
RR = lambda r: {"InpUhvStopMode": "2", "InpUhvSlBeyond": "3", "InpUhvFixTp": "0", "InpUhvRR": str(r)}   # noqa: E731
# name -> (EA, the EA inputs changed for the run, the same change in the engine on top of the saved B3)
CASES = {
    "B3": ("ZeeUHV_B3", {}, {}),
    "B4 (half rule 0.5)": ("ZeeUHV_B4", {}, {"InpUhvMaxEntryPos": "0.5"}),
    "B3 no pre-break": ("ZeeUHV_B3_NoPreBreak", {}, {"InpUhvPreBreak": "0"}),
    "B3 candle close": ("ZeeUHV_B3_CandleClose", {}, CC),
    "B3 candle close, no momentum rule": ("ZeeUHV_B3_CandleClose", {"InpDetMomBody": "0"}, dict(CC, InpDetMomBody="0")),
    "B4 candle close": ("ZeeUHV_B4_CandleClose", {}, dict(CC, InpUhvMaxUhvClosePos="0.5")),
    "B3 candle close, spread filter off": ("ZeeUHV_B3_CandleClose_NoSpread", {}, dict(CC, InpUhvMaxTrigSpread="0")),
    "B4 candle close, spread filter off": ("ZeeUHV_B4_CandleClose_NoSpread", {}, dict(CC, InpUhvMaxUhvClosePos="0.5", InpUhvMaxTrigSpread="0")),
    "B4, stop 3 pips beyond the candle, 1:1": ("ZeeUHV_B4", RR(1), dict(RR(1), InpUhvMaxEntryPos="0.5")),
    "B4, stop 3 pips beyond the candle, 1:2": ("ZeeUHV_B4", RR(2), dict(RR(2), InpUhvMaxEntryPos="0.5")),
    "B3 candle close, stop 3 pips, 1:1": ("ZeeUHV_B3_CandleClose", RR(1), dict(CC, **RR(1))),
    "B3 candle close, stop 3 pips, 1:2": ("ZeeUHV_B3_CandleClose", RR(2), dict(CC, **RR(2))),
    "B4, exit when the hump line turns against": ("ZeeUHV_B4", {"InpUhvCamExit": "1"}, {"InpUhvMaxEntryPos": "0.5", "InpUhvCamExit": "1"}),
    "B4 (half rule 0.5), again": ("ZeeUHV_B4", {}, {"InpUhvMaxEntryPos": "0.5"}),
    "B3 purified (candle close, retracement from its first candle)": ("ZeeUHV_B3_Pure", {}, dict(CC, InpDetRetStart="1", InpDetDojiUhv="1")),
    "B3, 2 positions at a time": ("ZeeUHV_B3", {"InpMaxPos": "2"}, {"InpMaxPos": "2"}),
    "B3, 1 position at a time": ("ZeeUHV_B3", {"InpMaxPos": "1"}, {"InpMaxPos": "1"}),
}


def b3():
    for f in glob.glob(os.path.join(HERE, "settings", "saved", "MT5-LABEL B3*.json")):
        return dict(json.load(open(f, encoding="utf-8"))["inputs"])
    raise SystemExit("the saved setting MT5-LABEL B3 is missing")


def engine(inp):
    tr, _, cnt = U.simulate({k: str(v) for k, v in inp.items()})
    E = U.LAST_EXP
    m = (tr[:, 10] == 0) & (tr[:, 1] < CUT)
    return tr[m], E[m], cnt


def mt5(ea, sets, tag):
    f = os.path.join(COMMON, ea + "_trades.csv")
    if os.path.exists(f):
        os.remove(f)
    r = axi_rig.run(ea, "EURUSDp", "M1", sets, frm=FRM, to=TO, deposit=10000000, exec_mode=-1, model=4, leverage="1:400", rig="pxbt", tag=tag, timeout=1500)
    if r.get("error") or not os.path.exists(f):
        raise SystemExit(f"{tag}: {r.get('error') or 'the EA wrote no trade file'}")
    os.makedirs(OUT, exist_ok=True)
    shutil.copy2(f, os.path.join(OUT, tag + ".csv"))
    A = np.array([[float(x) for x in ln.strip().split(",")] for ln in open(f) if ln.strip()])
    log = max(glob.glob(r"C:\mt5_rig_pxbt\Tester\Agent-*\logs\*.log"), key=os.path.getmtime)
    net = re.findall(r"TARGET HELD AT THE BROKER: .*? net ([+-][\d.]+)", open(log, encoding="utf-16", errors="ignore").read())
    return A[A[:, 5] == 0], int((A[:, 5] == 1).sum()), r.get("secs"), float(net[-1]) if net else float("nan")


def compare(name, ea, sets, einp, runs=1):
    R, E, cnt = engine(einp)
    usd = 10.0                                                    # $ a pip at 1 lot
    ke = np.round(R[:, 1] * 1000).astype(np.int64) * 2 + (R[:, 0] > 0)
    o = np.argsort(ke); ks = ke[o]
    exp_lost = float((1 - E[:, 0]).sum()); sd = float(np.sqrt((E[:, 0] * (1 - E[:, 0])).sum())); exp_net = float(E[:, 1].sum()) * usd
    shown_lost = int((R[:, 6] <= 0).sum())
    print(f"\n{name}\n  engine: {len(R)} trades | the shown run: {shown_lost} not won, {100 * (1 - shown_lost / max(len(R), 1)):.2f}%, net {R[:, 6].sum():+,.0f}"
          f" | average over every delay: {exp_lost:.1f} not won (run to run +-{sd:.1f}), {100 * (1 - exp_lost / max(len(R), 1)):.2f}%, net {exp_net:+,.0f}")
    res = []
    for k in range(runs):
        A, ended, secs, mnet = mt5(ea, sets, re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") + f"_{k}")
        ka = A[:, 0].astype(np.int64) * 2 + (A[:, 1] > 0)
        j = np.clip(np.searchsorted(ks, ka), 0, max(len(ks) - 1, 0)); hit = (ks[j] == ka) if len(ks) else np.zeros(len(A), bool)
        pw = np.where(hit, E[o[j], 0] if len(ks) else 0, np.nan); won = (A[:, 3] == 1) | (A[:, 4] > 0)   # at the target, or closed in profit (a 24 h close)
        lost_always_win = int((hit & ~won & (pw > 0.9999)).sum()); won_always_lose = int((hit & won & (pw < 0.0001)).sum())
        res.append({"n": len(A), "same": int(hit.sum()), "ea_only": int((~hit).sum()), "engine_only": len(R) - int(hit.sum()), "lost": int((~won).sum()),
                    "lost_same": int((hit & ~won).sum()), "lost_ea_only": int((~hit & ~won).sum()), "net": mnet, "contra": (lost_always_win, won_always_lose), "ended": ended, "secs": secs,
                    "A": A, "hit": hit, "pw": pw})
        z = (res[-1]["lost"] - exp_lost) / sd if sd > 0 else 0.0
        res[-1]["z"] = z
        print(f"  MT5 run {k + 1}: {len(A)} trades | same tick and side {hit.sum()} | only in MT5 {(~hit).sum()} | only in the engine {len(R) - hit.sum()}"
              f" | not won {(~won).sum()} = {100 * won.mean():.2f}% ({z:+.1f} run-to-run spreads from the engine's average) | net {mnet:+,.0f}"
              f" | MT5 lost a sure win {lost_always_win}, won a sure loss {won_always_lose} | still open at the end {ended} | {secs} s")
    return {"name": name, "engine_n": len(R), "exp_lost": exp_lost, "sd": sd, "exp_net": exp_net, "shown_lost": shown_lost, "shown_net": float(R[:, 6].sum()), "runs": res, "R": R, "E": E}


if __name__ == "__main__":
    nb3 = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    only = sys.argv[2].lower() if len(sys.argv) > 2 else ""
    base = b3()
    for ea in sorted({c[0] for c in CASES.values()}):
        axi_rig.compile_ea(ea, rig="pxbt")
    t0 = time.time(); tot = []
    for name, (ea, sets, einp) in CASES.items():
        if only and only not in name.lower():
            continue
        tot.append(compare(name, ea, sets, dict(base, **einp), nb3 if name == "B3" else 1))
    n = sum(r["n"] for c in tot for r in c["runs"]); same = sum(r["same"] for c in tot for r in c["runs"])
    con = sum(sum(r["contra"]) for c in tot for r in c["runs"])
    print(f"\nALL: {n:,} MT5 trades in {sum(len(c['runs']) for c in tot)} runs | {same:,} on the engine's tick and side ({100 * same / max(n, 1):.2f}%) | {con} outcomes the engine calls impossible"
          f" | {time.time() - t0:.0f} s")
    # the pass rule (Zee 2026-11-14, "ok"): no outcome the engine calls impossible, and no more than one run in twenty further than 2 run-to-run
    # spreads from the engine's average (chance alone puts about one in twenty there)
    runs = [r for c in tot for r in c["runs"]]
    far = [(c["name"], r["z"]) for c in tot for r in c["runs"] if abs(r["z"]) > 2.0]
    allowed = max(1, -(-len(runs) // 20))
    ok = con == 0 and len(far) <= allowed
    print(f"{'PASS' if ok else 'FAIL'}: {con} impossible outcomes (0 allowed) | {len(far)} of {len(runs)} runs beyond 2 spreads ({allowed} allowed)"
          + ("".join(f"\n   {nm}: {z:+.1f} spreads" for nm, z in far)))
    sys.exit(0 if ok else 1)
