"""verify_s4_hours.py — is S4's 'skip hours 12-13' a real edge or overfit?

Compares S4 configs on 18 days and tests OOS robustness across many split points.
Key question: does ADDING the hour filter to a trend filter help across splits, or
only on the lucky single split? (Hour buckets are ~5-7 trades — overfit-prone.)
"""
import sys, glob
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
from winrate_improvement import (load_m1, build_m5, load_ticks, detect_s4,
                                 replay_enhanced, LOTS, COMMON)


def main():
    m1 = load_m1(); m5 = build_m5(m1)
    cache, days = {}, []
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        d = Path(tf).stem.split("_")[-1]; tks = load_ticks(tf)
        if len(tks) < 500: continue
        cache[d] = tks; days.append(d)
    days.sort(); nd = len(days)
    trades = []
    for d in days:
        for u in replay_enhanced(cache[d], detect_s4(m5, d), LOTS):
            u["day"] = d; u["hr"] = u["fire"].hour; trades.append(u)
    print(f"  S4: {len(trades)} trades over {nd} days\n")

    def subset(f):
        return [t for t in trades if f(t)]

    configs = {
        "baseline (all)":            lambda t: True,
        "td24>=7":                   lambda t: t["td24"] >= 7,
        "td24>=9":                   lambda t: t["td24"] >= 9,
        "skip h12-13 only":          lambda t: t["hr"] not in (12, 13),
        "td24>=7 + skip h12-13":     lambda t: t["td24"] >= 7 and t["hr"] not in (12, 13),
        "td24>=9 + skip h12-13":     lambda t: t["td24"] >= 9 and t["hr"] not in (12, 13),
    }
    splits = list(range(nd // 3, 2 * nd // 3 + 1))

    def oos(ts, sp):
        return sum(t["pnl"] for t in ts if t["day"] in set(days[sp:]))

    base_oos = [oos(trades, sp) for sp in splits]
    print(f"  {'config':<26}{'n':>4}{'total':>9}{'maxDD':>8}  OOS vs baseline across {len(splits)} splits")
    for name, f in configs.items():
        ts = subset(f)
        tot = sum(t["pnl"] for t in ts)
        # simple maxDD (running trough of cumulative)
        cum = 0; peak = 0; dd = 0
        for t in sorted(ts, key=lambda x: x["fire"]):
            cum += t["pnl"]; peak = max(peak, cum); dd = max(dd, peak - cum)
        oss = [oos(ts, sp) for sp in splits]
        beats = sum(1 for i in range(len(splits)) if oss[i] >= base_oos[i] - 0.01)
        tag = "(baseline)" if name == "baseline (all)" else f"{beats}/{len(splits)} splits beat base"
        print(f"  {name:<26}{len(ts):>4}${tot:>+7.1f}${dd:>6.1f}   {tag}")

    # the decisive comparison: does the hour filter ADD value over trend-only?
    print("\n  Hour-filter marginal value (td24>=7 vs td24>=7+skip-hours), per split:")
    a = subset(lambda t: t["td24"] >= 7)
    b = subset(lambda t: t["td24"] >= 7 and t["hr"] not in (12, 13))
    wins = 0
    for sp in splits:
        oa, ob = oos(a, sp), oos(b, sp)
        better = ob > oa + 0.01
        wins += better
        print(f"    split@day{sp:>2} ({days[sp]}): trend-only ${oa:+6.1f}  vs  +skip-hours ${ob:+6.1f}  → {'hours help' if better else 'no gain'}")
    print(f"\n  Hours added value in {wins}/{len(splits)} splits — "
          f"{'ROBUST' if wins >= len(splits)*0.7 else 'NOT robust (overfit / noise)'}")


if __name__ == "__main__":
    main()
