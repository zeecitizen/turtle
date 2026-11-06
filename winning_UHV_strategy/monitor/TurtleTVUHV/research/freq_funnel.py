"""freq_funnel.py - what cuts the trade count of a saved setting (default "2026-10-30 23-08-23": 399 trades, 99.7% WR on m15 2023 -> now)?
Each entry filter is switched off ON ITS OWN (everything else as saved) in the Overview's tester (sim.simulate, ds m15). For each: trades,
WR, net, and the trades it added / removed (matched by entry time and side) with their win rate. Also how often the setting trades (days).
Tester = hypothesis; MT5 (M15 chart) promotes.

    py research/freq_funnel.py ["2026-10-30 23-08-23"]
"""
import json, sys, numpy as np
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import server, sim, rbox

SV = r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved"
NAME = sys.argv[1] if len(sys.argv) > 1 else "2026-10-30 23-08-23"
S = json.load(open(SV + "\\" + NAME + ".json"))["inputs"]
D = sim.data("m15")
DAYS = np.unique((D["t15"] // 86400)[(((D["t15"] // 86400) + 4) % 7 >= 1) & (((D["t15"] // 86400) + 4) % 7 <= 5)])   # Mon-Fri with candles


def run(sets):
    tr, _, st = sim.simulate(server.full_inputs({**S, **sets}), ds="m15")
    return np.array([x for x in tr if x[10] == 0]), st


def summ(t):
    p = t[:, 6]
    m = 1735689600                          # 2025-01-01: halves 2023-24 / 2025-26
    a_, b_ = p[t[:, 1] < m], p[t[:, 1] >= m]
    d = np.unique(t[:, 1] // 86400)
    return dict(n=len(p), wr=round(100 * (p > 0).mean(), 2), losses=int((p <= 0).sum()), net=round(p.sum()), worst=round(p.min()),
                wr1=round(100 * (a_ > 0).mean(), 2), wr2=round(100 * (b_ > 0).mean(), 2), days=len(d))


def diff(base, t):
    kb = {(round(x[1]), int(x[0])): x[6] for x in base}
    kt = {(round(x[1]), int(x[0])): x[6] for x in t}
    add = np.array([v for k, v in kt.items() if k not in kb]); rem = np.array([v for k, v in kb.items() if k not in kt])
    f = lambda a: f"{len(a):4d} ({100 * (a > 0).mean():5.1f}% WR)" if len(a) else "   0         "  # noqa: E731
    return f(add), f(rem), int((add <= 0).sum()) if len(add) else 0


ONES = lambda k: {k: "1" * len(str(S.get(k, "")))}  # noqa: E731
RELAX = [
    ("EMA gap >= 22.5 pips (InpEmaGapPips -> 0)", {"InpEmaGapPips": 0}),
    ("chop ER 0.05 (InpChopEr -> 0)", {"InpChopEr": 0}),
    ("session 3-19 (InpSessFrom/To -> 0/24)", {"InpSessFrom": 0, "InpSessTo": 24}),
    ("weekday skip Tue (InpSkipDow -> -1)", {"InpSkipDow": -1}),
    ("ATR >= $1.5 (InpAtrMinUsd -> 0)", {"InpAtrMinUsd": 0}),
    ("candle >= 0.8 ATR (InpMinRangeAtr -> 0)", {"InpMinRangeAtr": 0}),
    ("max spread 20 pts (InpMaxSpreadPts -> 0)", {"InpMaxSpreadPts": 0}),
    ("BUY entry boxes (InpBandsB all on)", {"InpBandsB": "1" * 21}),
    ("SELL entry boxes (InpBandsS all on)", {"InpBandsS": "1" * 21}),
    ("both entry boxes all on", {"InpBandsB": "1" * 21, "InpBandsS": "1" * 21}),
    ("ghost stand-aside off (InpBandOff 1 -> 0)", {"InpBandOff": 0}),
    ("entry hours (InpHours all on)", {"InpHours": "1" * 24}),
] + [(f"range box {k} (TvBox_{k} all on)", {**ONES(f"TvBox_{k}_B"), **ONES(f"TvBox_{k}_S")}) for k, *_ in rbox.FAM if f"TvBox_{k}_B" in S] + [
    ("all range boxes on", {k: "1" * len(v) for k, v in S.items() if k.startswith("TvBox_")}),
    ("day target $2000 (InpDayTargetUsd -> 0)", {"InpDayTargetUsd": 0}),
    ("day loss 2% (InpDayLossPct -> 0)", {"InpDayLossPct": 0}),
    ("one position (InpMaxPos 1 -> 2)", {"InpMaxPos": 2}),
    ("gap cancel (InpGapCancel -> false)", {"InpGapCancel": "false"}),
    ("break within 5 bars (InpBreakBars -> 8)", {"InpBreakBars": 8}),
    ("break 4 pips (InpBreakPips -> 2)", {"InpBreakPips": 2}),
    ("touch 3.5 pips (InpTouchPips -> 6)", {"InpTouchPips": 6}),
    ("long rule fast EMA only (InpLongRule 0 -> 2 both)", {"InpLongRule": 2}),
    ("short line fast EMA (InpShortLine 1 -> 2 both)", {"InpShortLine": 2}),
    ("star off (InpStar -> true)", {"InpStar": "true"}),
    ("pin body <= 0.45 (InpBodyMax -> 0.6)", {"InpBodyMax": 0.6}),
    ("pin wick >= 0.3 (InpWickMin -> 0.2)", {"InpWickMin": 0.2}),
    ("pin nose <= 0.05 (InpNoseMax -> 0.15)", {"InpNoseMax": 0.15}),
    ("marubozu body >= 0.55 (InpMaruBody -> 0.45)", {"InpMaruBody": 0.45}),
    ("hammer ratio 2.25 (InpHamRatio -> 1.75)", {"InpHamRatio": 1.75}),
    ("hammer nose 0.8 (InpHamNose -> 1.0)", {"InpHamNose": 1.0}),
]

if __name__ == "__main__":
    base, st = run({})
    b = summ(base)
    tdays = np.unique(base[:, 1] // 86400)
    gaps = np.diff(np.searchsorted(DAYS, tdays))
    yrs = {}
    for x in base:
        y = 1970 + int(x[1] // 31556952)
        yrs[y] = yrs.get(y, 0) + 1
    print(f"SETTING {NAME}: {b}")
    print(f"  stats {st}")
    print(f"  weekdays with candles {len(DAYS)}, days with a trade {len(tdays)} ({100 * len(tdays) / len(DAYS):.0f}%), trades per weekday {b['n'] / len(DAYS):.2f}")
    print(f"  gap between trading days (weekdays): median {np.median(gaps):.0f}, 90th pct {np.percentile(gaps, 90):.0f}, max {gaps.max()}; trades by year {yrs}")
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda r: run(r[1]), RELAX))
    print(f"\n{'switch off, alone':52s} {'trades':>6s} {'WR':>6s} {'loss':>4s} {'net':>9s} {'wr23-24':>7s} {'wr25-26':>7s}  added (WR)       removed (WR)")
    rows = []
    for (lab, ch), (t, _) in zip(RELAX, res):
        s = summ(t); a, r, al = diff(base, t)
        rows.append({"switch": lab, "sets": ch, **s, "added": a.strip(), "removed": r.strip()})
        print(f"{lab:52s} {s['n']:6d} {s['wr']:6.2f} {s['losses']:4d} {s['net']:9,d} {s['wr1']:7.2f} {s['wr2']:7.2f}  {a}  {r}")
    json.dump({"setting": NAME, "base": b, "stats": st, "rows": rows}, open(rf"C:\Users\zeesh\turtle\monitor\saad_view\research\freq_funnel_{NAME.replace(' ', '_')}.json", "w"), indent=1)
