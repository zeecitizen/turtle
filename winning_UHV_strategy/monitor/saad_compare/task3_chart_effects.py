"""task3_chart_effects.py - Task 3 (Zee 2026-10-18): "try different settings on the tradingview chart (note down their effect) ->
note down all parameters that effect us majorly on 1 minute time frame -> make a list of settings we can change vs their effect on
winrate/drawdown/profit -> note these results in to an md file"

One setting at a time on the live TradingView indicator (BLUEBERRY:XAUUSD, 1 min): change it, wait for the chart to recompute, read
the indicator's own trade list (its export table), note trades / win rate / net / max drawdown, put the setting back. At the end every
setting is compared with the snapshot taken at the start and restored if anything drifted.
The chart holds ~1 week of 1-minute history, so these are the effects on THAT week. Task 5 (MT5, full year) is merged in next to them.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import server  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "saad_strategy_1min_optimized" / "optimizer_results"
OUT.mkdir(parents=True, exist_ok=True)
SRC = server.PINE.read_text(encoding="utf-8")

# numeric tests (pine var -> values to try); bools are flipped; dropdowns try every other option
NUM = {"iFast": [2, 5, 8], "iSlow": [4, 10, 20], "iWick": [0.3, 0.5, 0.6], "iBodyMax": [0.4, 0.8], "iNose": [0.1, 0.35], "iMaruB": [0.45, 0.65],
       "iHamR": [1.5, 3], "iHamN": [0.2, 0.5], "iMinAtr": [0, 0.2, 0.6], "iTouchP": [0, 2, 8], "iBreakB": [2, 3], "iBreakP": [0, 2, 8],
       "iSlPips": [5, 10, 25], "iSlAtrM": [1.5, 2.5], "iMaxRisk": [0, 2, 8], "tpFixB": [1, 4], "tpFixS": [1, 4], "tpFib": [161.8, 300],
       "tpPart": [0.5, 1], "tpPartTr": [0.3, 1.5], "iPartial": [0.5, 0.95], "iBePct": [0, 0.5, 1], "iLTrail": [0.5, 2], "iSTrail": [1, 3],
       "iTrAtr": [0.5, 2], "pkGap": [0, 0.5], "iCloseM": [0, 5], "iMinTp": [0, 10], "iLTpP": [5], "iSTpP": [5], "iEr": [0, 0.1, 0.2],
       "iErLen": [8, 24], "adRunN": [0, 3, 6], "coolN": [0, 3], "reBars": [5, 60], "rpLook": [5, 12], "rpLookS": [5, 12], "rpPause": [3],
       "htEma": [20, 50], "pkBeUsd": [1], "pkLockAt": [2], "pkTrail": [1], "pkAtr": [1], "pkLowN": [3], "adBars": [10], "adMaxUsd": [3]}
BOOLS = ["iUsePin", "iMaru", "iHammer", "iStar", "iPinDir", "iPinCol", "iLExitAb", "iTp1Be", "iGap", "coolWin", "reOn", "adEmaX", "fxOn"]
CHOICES = ["tpMode", "iSlMode", "iLRule", "iSLine", "iTouchM", "htReq", "rpOff", "coolDir", "enMode", "tpNoFix"]
CHART_ONLY = {"pkBeUsd", "pkLockAt", "pkTrail", "pkAtr", "pkLowN", "adBars", "adMaxUsd", "adEmaX", "fxOn", "enMode", "iTightTrail", "iSkipBoth"}


def options(var):
    m = re.search(rf"^{var}\s*=\s*input\.string\([^\n]*options\s*=\s*\[([^\]]*)\]", SRC, re.M)
    return re.findall(r'"([^"]*)"', m.group(1)) if m else []


def table_rows():
    data = server.tv("data", "tables", "--filter", "Saad")
    tabs = [t for s in data.get("studies", []) for t in s.get("tables", [])]
    ex = next((t for t in tabs if t["rows"] and t["rows"][0].startswith("# | side")), None)
    return ex["rows"][1:] if ex else None


def read_stable(prev=None, maxwait=40):
    """the export table once it stops changing (and differs from `prev`, or 8 s passed)"""
    t0, last = time.time(), None
    while time.time() - t0 < maxwait:
        time.sleep(1.5)
        r = table_rows()
        if r is not None and r == last and (r != prev or time.time() - t0 > 8):
            return r
        last = r
    return last or []


def stats(rows):
    pn = []
    for r in rows:
        c = [x.strip() for x in r.split("|")]
        if len(c) >= 8:
            pn.append(server.money(c[7]))
    n = len(pn)
    w = sum(p > 0 for p in pn)
    eq = peak = dd = 0.0
    for p in pn:
        eq += p
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return {"n": n, "wr": 100 * w / n if n else 0, "net": sum(pn), "dd": dd}


def main():
    st, base, _, _ = server.read_settings()
    names = server.pine_inputs()
    json.dump(base, open(OUT / "task3_chart_snapshot.json", "w"), indent=1, default=str)
    sid = st["id"]
    setv = lambda k, v: server.set_input(sid, names.index(k), v)
    if not base["exOn"]:
        setv("exOn", True)
    ref = read_stable(None)
    b = stats(ref)
    print(f"base: {b}", flush=True)
    res = {"_base": b, "_chart": f"{st['symbol']} {st['res']} min"}
    tests = [(k, v) for k, vs in NUM.items() if k in base for v in vs if str(v) != str(base[k])]
    tests += [(k, not base[k]) for k in BOOLS if k in base]
    tests += [(k, o) for k in CHOICES if k in base for o in options(k) if o != base[k]]
    prev = ref
    for i, (k, v) in enumerate(tests, 1):
        try:
            setv(k, v)
            rows = read_stable(prev)
            s = stats(rows)
            res.setdefault(k, []).append({"v": v, **s})
            print(f"[{i}/{len(tests)}] {k}={v}: {s}", flush=True)
            setv(k, base[k])
            prev = read_stable(rows)
        except Exception as e:
            print(f"[{i}] {k}={v}: failed {e}", flush=True)
            try:
                setv(k, base[k])
            except Exception:
                pass
        json.dump(res, open(OUT / "task3_chart_effects.json", "w"), indent=1, default=str)
    # put everything back exactly
    st, now, _, _ = server.read_settings()
    for k, v in base.items():
        if str(now.get(k)) != str(v):
            setv(k, v)
    if not base["exOn"]:
        setv("exOn", False)
    time.sleep(4)
    _, now, _, _ = server.read_settings()
    drift = {k: (now.get(k), v) for k, v in base.items() if str(now.get(k)) != str(v)}
    print("restored; still different:", drift, flush=True)
    res["_restored_drift"] = drift
    json.dump(res, open(OUT / "task3_chart_effects.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
