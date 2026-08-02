"""verify_thorough.py — independent verification before touching Shano's live account.

A) S3: does its LIVE 2R-Free-Roll (BE@+1R + partial 50%@+1.5R) help or hurt vs plain
   SL/TP, on 18 days? (If plain wins, turn 2R OFF.)
B) S1: is the td24>=$7 trend filter robust, or fit to the single 9/9 split? Tested
   across MANY split points + the full threshold neighbourhood.

Reuses winrate_improvement.py's exact detectors + tick data.
Run:  py verify_thorough.py
"""
import sys, glob
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
from winrate_improvement import (load_m1, build_m5, load_ticks, detect_s1, detect_s3,
                                 replay_enhanced, CONTRACT, LOTS, COMMON)

BE_BUF = 0.30


def replay_2r(ticks, sigs, lots, beR=1.0, partialR=1.5, frac=0.5):
    """S3's deployed 2R-Free-Roll: BE at +1R, bank `frac` at +1.5R, runner to TP/BE."""
    ppp = lots * CONTRACT
    done, units = [], []
    it = iter(sorted(sigs, key=lambda x: x["fire"])); pend = next(it, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            buy = u["side"] == "BUY"; R = u["sl"]
            fav = (bid - u["e"]) if buy else (u["e"] - ask)
            if not u["be"] and fav >= beR * R:
                u["be"] = True
            if not u["part"] and fav >= partialR * R:
                px = bid if buy else ask
                u["banked"] += ((px - u["e"]) if buy else (u["e"] - px)) * ppp * frac
                u["frac"] -= frac; u["part"] = True; u["be"] = True
            stop = (u["e"] + BE_BUF) if u["be"] else (u["e"] - R) if buy else \
                   ((u["e"] - BE_BUF) if u["be"] else (u["e"] + R))
            # buy exits
            if buy:
                if bid <= stop:
                    u["pnl"] = u["banked"] + (stop - u["e"]) * ppp * u["frac"]; done.append(u); units.remove(u)
                elif bid >= u["e"] + u["tp"]:
                    u["pnl"] = u["banked"] + u["tp"] * ppp * u["frac"]; done.append(u); units.remove(u)
            else:
                if ask >= stop:
                    u["pnl"] = u["banked"] + (u["e"] - stop) * ppp * u["frac"]; done.append(u); units.remove(u)
                elif ask <= u["e"] - u["tp"]:
                    u["pnl"] = u["banked"] + u["tp"] * ppp * u["frac"]; done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            e = ask if pend["side"] == "BUY" else bid
            units.append({**pend, "e": e, "be": False, "part": False, "frac": 1.0, "banked": 0.0})
            pend = next(it, None)
    last = ticks[-1]
    for u in units:
        px = last["bid"] if u["side"] == "BUY" else last["ask"]
        u["pnl"] = u["banked"] + (((px - u["e"]) if u["side"] == "BUY" else (u["e"] - px)) * ppp * u["frac"])
        done.append(u)
    return done


def wf(trades, days, split):
    tr = sum(t["pnl"] for t in trades if t["day"] in set(days[:split]))
    te = sum(t["pnl"] for t in trades if t["day"] in set(days[split:]))
    return tr, te


def main():
    m1 = load_m1(); m5 = build_m5(m1)
    cache, days = {}, []
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        d = Path(tf).stem.split("_")[-1]; tks = load_ticks(tf)
        if len(tks) < 500: continue
        cache[d] = tks; days.append(d)
    days.sort(); nd = len(days)
    print(f"  {nd} days: {days[0]} → {days[-1]}\n")

    # ════ A) S3: 2R-Free-Roll vs plain ════
    print("══ A) S3 — deployed 2R-Free-Roll (BE@1R + partial 50%@1.5R) vs PLAIN SL/TP ══")
    s3_plain, s3_2r = [], []
    for d in days:
        sg = detect_s3(m5, d)
        for u in replay_enhanced(cache[d], sg, LOTS): u["day"] = d; s3_plain.append(u)
        for u in replay_2r(cache[d], sg, LOTS):       u["day"] = d; s3_2r.append(u)
    pb, p2 = sum(t["pnl"] for t in s3_plain), sum(t["pnl"] for t in s3_2r)
    print(f"  PLAIN  (2R OFF): total ${pb:+8.1f}   n={len(s3_plain)}")
    print(f"  2R-FREE-ROLL ON: total ${p2:+8.1f}   n={len(s3_2r)}")
    print(f"  → turning 2R OFF changes P&L by ${pb-p2:+.1f}\n  walk-forward OOS across splits:")
    for sp in range(nd//3, 2*nd//3 + 1):
        _, te_b = wf(s3_plain, days, sp); _, te_2 = wf(s3_2r, days, sp)
        print(f"    split@day{sp:>2} ({days[sp]}): PLAIN OOS ${te_b:+7.1f}  vs  2R OOS ${te_2:+7.1f}  → {'PLAIN' if te_b>te_2 else '2R'} better")

    # ════ B) S1: td24 threshold robustness across many splits ════
    print("\n══ B) S1 — td24 trend filter, robustness across split points ══")
    s1 = []
    for d in days:
        for u in replay_enhanced(cache[d], detect_s1(m5, d), LOTS):
            u["day"] = d; s1.append(u)
    print(f"  {len(s1)} S1 trades total")
    thresholds = [2.0, 5.0, 7.0, 9.0]
    splits = list(range(nd//3, 2*nd//3 + 1))
    print(f"  thresholds {thresholds} × {len(splits)} split points (day {splits[0]}–{splits[-1]})")
    print(f"  {'thr':>5} {'trades':>7} {'total':>9} {'OOS range (min..max across splits)':>38} {'beats $2 baseline?':>20}")
    base_oos = {}
    rows = {}
    for thr in thresholds:
        ft = [t for t in s1 if t["td24"] >= thr]
        tot = sum(t["pnl"] for t in ft)
        ooss = [wf(ft, days, sp)[1] for sp in splits]
        rows[thr] = (len(ft), tot, ooss)
        if thr == 2.0:
            base_oos = ooss
    for thr in thresholds:
        n, tot, ooss = rows[thr]
        beats = sum(1 for i in range(len(splits)) if ooss[i] >= base_oos[i])
        tag = f"{beats}/{len(splits)} splits" if thr != 2.0 else "(baseline)"
        print(f"  {thr:>5.0f} {n:>7} ${tot:>+8.1f}   {min(ooss):>+8.1f} .. {max(ooss):>+8.1f}            {tag:>20}")
    print("\n  (robust = higher threshold beats $2 baseline OOS across MOST splits, not just one)")


if __name__ == "__main__":
    main()
