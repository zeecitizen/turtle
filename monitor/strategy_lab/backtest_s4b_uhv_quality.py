"""backtest_s4b_uhv_quality.py — Test: UHV candle must be STRONG (not just high volume).

Hypothesis: requiring the UHV candle to have a significant body/range ratio
(strong institutional candle, not a high-vol doji/spinning top) improves signal quality.

Current S4b only checks:
  ✅ Breakout candle is momentum (body/range >= 0.55)
  ✅ Breakout vol < UHV vol
  ❌ No quality check on the UHV candle itself

Test: sweep UHV body/range minimum (0 = any, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
Also test UHV range minimum (the UHV candle should have meaningful range, not tiny).

Run: py backtest_s4b_uhv_quality.py
"""
import sys, glob
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import group_bars_by_day

CONTRACT = 100.0
LOTS = 0.10
TREND_LB = 30
RETRACE_LB = 12
TP = 5.0
SL = 6.0


def trend_dir(win):
    h = len(win) // 2
    older, recent = win[:h], win[h:]
    if not older or not recent: return 0
    if max(b["high"] for b in recent) > max(b["high"] for b in older) and \
       min(b["low"] for b in recent) > min(b["low"] for b in older): return 1
    if max(b["high"] for b in recent) < max(b["high"] for b in older) and \
       min(b["low"] for b in recent) < min(b["low"] for b in older): return -1
    return 0


def efficiency_ratio(seg):
    if len(seg) < 2: return 0.0
    net = abs(seg[-1]["close"] - seg[0]["close"])
    path = sum(abs(seg[k]["close"] - seg[k-1]["close"]) for k in range(1, len(seg)))
    return (net / path) if path > 0 else 0.0


def detect(m1, er_min=0.15, bo_body_frac=0.55, uhv_body_frac=0.0, uhv_range_min=0.0):
    """S4b detect with additional UHV quality filters.

    uhv_body_frac: minimum body/range for the UHV candle (0=any, 0.5=strong)
    uhv_range_min: minimum range in price pts for UHV candle (0=any, 0.5=meaningful)
    """
    sigs = []
    start = TREND_LB + RETRACE_LB + 2
    for i in range(start, len(m1)):
        bo = m1[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < bo_body_frac: continue

        win = m1[i - RETRACE_LB:i]
        avgbody = sum(abs(b["close"] - b["open"]) for b in win) / len(win)
        if body < avgbody: continue

        tw = m1[i - TREND_LB:i]
        if er_min > 0 and efficiency_ratio(tw) < er_min: continue
        td = trend_dir(tw)
        if td == 0: continue

        # BUY: green breakout over UHV red
        if bo["close"] > bo["open"] and td == 1:
            reds = [b for b in win if b["close"] < b["open"]]
            if reds:
                # Filter reds by UHV quality BEFORE picking max volume
                qualified_reds = reds
                if uhv_body_frac > 0 or uhv_range_min > 0:
                    qualified_reds = []
                    for r in reds:
                        r_rng = r["high"] - r["low"]
                        if r_rng <= 0: continue
                        r_body = abs(r["close"] - r["open"])
                        if uhv_body_frac > 0 and r_body / r_rng < uhv_body_frac: continue
                        if uhv_range_min > 0 and r_rng < uhv_range_min: continue
                        qualified_reds.append(r)
                if not qualified_reds: continue
                uhv = max(qualified_reds, key=lambda b: b["vol"])
                if bo["vol"] < uhv["vol"] and bo["close"] > uhv["high"] and bo["open"] <= uhv["high"]:
                    sigs.append({"side": +1, "fire_time": bo["time"] + timedelta(minutes=1),
                                 "uhv_body_frac": abs(uhv["close"]-uhv["open"])/(uhv["high"]-uhv["low"]) if (uhv["high"]-uhv["low"])>0 else 0,
                                 "uhv_range": uhv["high"]-uhv["low"]})
                    continue

        # SELL: red breakout under UHV green
        if bo["close"] < bo["open"] and td == -1:
            greens = [b for b in win if b["close"] > b["open"]]
            if greens:
                qualified_greens = greens
                if uhv_body_frac > 0 or uhv_range_min > 0:
                    qualified_greens = []
                    for g in greens:
                        g_rng = g["high"] - g["low"]
                        if g_rng <= 0: continue
                        g_body = abs(g["close"] - g["open"])
                        if uhv_body_frac > 0 and g_body / g_rng < uhv_body_frac: continue
                        if uhv_range_min > 0 and g_rng < uhv_range_min: continue
                        qualified_greens.append(g)
                if not qualified_greens: continue
                uhv = max(qualified_greens, key=lambda b: b["vol"])
                if bo["vol"] < uhv["vol"] and bo["close"] < uhv["low"] and bo["open"] >= uhv["low"]:
                    sigs.append({"side": -1, "fire_time": bo["time"] + timedelta(minutes=1),
                                 "uhv_body_frac": abs(uhv["close"]-uhv["open"])/(uhv["high"]-uhv["low"]) if (uhv["high"]-uhv["low"])>0 else 0,
                                 "uhv_range": uhv["high"]-uhv["low"]})
    return sigs


def replay(ticks, sigs, tp_pts=TP, sl_pts=SL, max_conc=3):
    ppp = LOTS * CONTRACT
    done = []
    it = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pend = next(it, None)
    units = []
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            s = u["side"]
            if s > 0:
                if bid <= u["e"] - sl_pts:
                    u["pnl"] = -sl_pts * ppp; u["result"] = "L"; done.append(u); units.remove(u); continue
                if bid >= u["e"] + tp_pts:
                    u["pnl"] = tp_pts * ppp; u["result"] = "W"; done.append(u); units.remove(u); continue
            else:
                if ask >= u["e"] + sl_pts:
                    u["pnl"] = -sl_pts * ppp; u["result"] = "L"; done.append(u); units.remove(u); continue
                if ask <= u["e"] - tp_pts:
                    u["pnl"] = tp_pts * ppp; u["result"] = "W"; done.append(u); units.remove(u); continue
        while pend is not None and t >= pend["fire_time"]:
            if len(units) < max_conc:
                units.append({"side": pend["side"], "e": ask if pend["side"] > 0 else bid,
                              "open_t": t, "sig": pend})
            pend = next(it, None)
    if ticks:
        last = ticks[-1]
        for u in units:
            p = ((last["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - last["ask"])) * ppp
            u["pnl"] = p; u["result"] = "W" if p > 0 else "L"
            done.append(u)
    return done


def stat(trades, nd):
    n = len(trades)
    if not n: return "n=0", 0, 0, 0
    w = sum(1 for t in trades if t.get("result") == "W")
    wr = w / n
    tot = sum(t["pnl"] for t in trades)
    avg_w = sum(t["pnl"] for t in trades if t["pnl"] > 0) / w if w else 0
    avg_l = sum(t["pnl"] for t in trades if t["pnl"] <= 0) / (n - w) if (n - w) else 0
    s = f"n={n:>4} {n/nd:>5.1f}/d  WR={wr:>5.1%}  W=${avg_w:>5.1f}  L=${avg_l:>+5.1f}  TOT=${tot:>+9.1f}"
    return s, wr, tot, n


def main():
    bars = load_m1_merged()
    days_b = group_bars_by_day(bars)
    cache = {}
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        d = Path(tf).stem.split("_")[-1]
        if d not in days_b or len(days_b[d]) < 200: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[d] = {"m1": days_b[d], "ticks": ticks}
    days = sorted(cache)
    nd = len(days); mid = nd // 2

    print(f"S4b UHV QUALITY TEST — {nd} broker-tick days, TP${TP}/SL${SL}, {LOTS} lots")
    print(f"{'='*100}\n")

    # ── BASELINE ──
    print("=== BASELINE (current S4b: no UHV quality check) ===")
    sig = {d: detect(cache[d]["m1"]) for d in days}
    allt, testt = [], []
    for k, d in enumerate(days):
        tr = replay(cache[d]["ticks"], sig[d])
        allt += tr
        if k >= mid: testt += tr
    s1, _, _, _ = stat(allt, nd)
    s2, _, _, _ = stat(testt, nd - mid)
    print(f"  ALL: {s1}")
    print(f"  OOS: {s2}\n")

    # ── POST-HOC: what UHV body fractions are our trades using? ──
    print("=== POST-HOC: UHV body/range distribution of current signals ===")
    all_sigs = []
    for d in days: all_sigs += sig[d]
    buckets = [(0, 0.2), (0.2, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)]
    for lo, hi in buckets:
        n = sum(1 for s in all_sigs if lo <= s.get("uhv_body_frac", 0) < hi)
        print(f"  UHV body/range [{lo:.1f}–{hi:.1f}): {n:>4} signals ({n/len(all_sigs)*100:.0f}%)" if all_sigs else "")
    print()

    # Also check which UHV body fractions produce winners
    print("=== POST-HOC: WR by UHV body/range bucket ===")
    for lo, hi in buckets:
        bucket_sigs = [s for s in all_sigs if lo <= s.get("uhv_body_frac", 0) < hi]
        if not bucket_sigs: continue
        # replay each day and match signals
        bucket_trades = []
        for d in days:
            d_sigs = [s for s in sig[d] if lo <= s.get("uhv_body_frac", 0) < hi]
            if d_sigs:
                bucket_trades += replay(cache[d]["ticks"], d_sigs)
        if bucket_trades:
            s, wr, tot, n = stat(bucket_trades, nd)
            print(f"  UHV body [{lo:.1f}–{hi:.1f}):  {s}")
    print()

    # UHV range distribution
    print("=== POST-HOC: UHV range (pts) distribution ===")
    ranges = [s.get("uhv_range", 0) for s in all_sigs]
    for lo, hi in [(0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 100)]:
        bucket_sigs_all = [s for s in all_sigs if lo <= s.get("uhv_range", 0) < hi]
        if not bucket_sigs_all: continue
        bucket_trades = []
        for d in days:
            d_sigs = [s for s in sig[d] if lo <= s.get("uhv_range", 0) < hi]
            if d_sigs: bucket_trades += replay(cache[d]["ticks"], d_sigs)
        if bucket_trades:
            s, wr, tot, n = stat(bucket_trades, nd)
            print(f"  UHV range [{lo:.1f}–{hi:.1f}):  {s}")
    print()

    # ── SWEEP 1: UHV body/range minimum ──
    print("=" * 100)
    print("SWEEP 1: UHV candle body/range minimum (must be a STRONG candle)")
    print("=" * 100)
    for ubf in (0.0, 0.20, 0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80):
        sig = {d: detect(cache[d]["m1"], uhv_body_frac=ubf) for d in days}
        train, test = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sig[d])
            (train if k < mid else test).extend(tr)
        a = sum(t["pnl"] for t in train)
        b = sum(t["pnl"] for t in test)
        wf = "✓" if a > 0 and b > 0 else " "
        s1, wr1, _, n1 = stat(train + test, nd)
        s2, wr2, _, n2 = stat(test, nd - mid)
        flag = ""
        if wr1 >= 0.75: flag = " ★★★"
        elif wr1 >= 0.65: flag = " ★★"
        elif wr1 >= 0.58: flag = " ★"
        print(f"  [{wf}] uhv_body>={ubf:.2f}  ALL: {s1}{flag}")
        print(f"      {'':18} OOS: {s2}")
    print()

    # ── SWEEP 2: UHV range minimum ──
    print("=" * 100)
    print("SWEEP 2: UHV candle range minimum (pts) (must be a meaningful candle, not tiny)")
    print("=" * 100)
    for urm in (0.0, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0):
        sig = {d: detect(cache[d]["m1"], uhv_range_min=urm) for d in days}
        train, test = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sig[d])
            (train if k < mid else test).extend(tr)
        a = sum(t["pnl"] for t in train)
        b = sum(t["pnl"] for t in test)
        wf = "✓" if a > 0 and b > 0 else " "
        s1, wr1, _, n1 = stat(train + test, nd)
        s2, wr2, _, n2 = stat(test, nd - mid)
        flag = ""
        if wr1 >= 0.75: flag = " ★★★"
        elif wr1 >= 0.65: flag = " ★★"
        elif wr1 >= 0.58: flag = " ★"
        print(f"  [{wf}] uhv_range>={urm:.1f}  ALL: {s1}{flag}")
        print(f"      {'':19} OOS: {s2}")
    print()

    # ── SWEEP 3: Combined UHV body + range + breakout body ──
    print("=" * 100)
    print("SWEEP 3: Combined — UHV body × UHV range × breakout body")
    print("=" * 100)
    combos = []
    for ubf in (0.0, 0.3, 0.4, 0.5, 0.6, 0.7):
        for urm in (0.0, 0.5, 1.0, 1.5, 2.0):
            for bbf in (0.55, 0.65, 0.70, 0.80):
                sig = {d: detect(cache[d]["m1"], uhv_body_frac=ubf, uhv_range_min=urm,
                                 bo_body_frac=bbf) for d in days}
                train, test = [], []
                for k, d in enumerate(days):
                    tr = replay(cache[d]["ticks"], sig[d])
                    (train if k < mid else test).extend(tr)
                a = sum(t["pnl"] for t in train)
                b = sum(t["pnl"] for t in test)
                n_all = len(train) + len(test)
                w_all = sum(1 for t in train + test if t.get("result") == "W")
                wr = w_all / n_all if n_all > 0 else 0
                combos.append({
                    "ubf": ubf, "urm": urm, "bbf": bbf,
                    "wr": wr, "n": n_all, "train": a, "test": b, "total": a + b
                })

    wf_pos = [c for c in combos if c["train"] > 0 and c["test"] > 0 and c["n"] >= 15]
    wf_pos.sort(key=lambda c: (-c["wr"], -c["total"]))

    print(f"\n  Walk-forward positive combos: {len(wf_pos)} / {len(combos)}\n")
    if wf_pos:
        print(f"  Top 20 by WR (both halves positive, n≥15):\n")
        print(f"  {'uhv_body':>8} {'uhv_rng':>7} {'bo_body':>7}  {'WR':>6}  {'n':>4}  "
              f"{'n/d':>5}  {'TRAIN':>9}  {'TEST':>9}  {'TOTAL':>9}")
        for c in wf_pos[:20]:
            print(f"  {c['ubf']:>8.2f} {c['urm']:>7.1f} {c['bbf']:>7.2f}  {c['wr']:>5.1%}  {c['n']:>4}  "
                  f"{c['n']/nd:>5.1f}  ${c['train']:>+8.1f}  ${c['test']:>+8.1f}  ${c['total']:>+8.1f}")

        # Best by total P&L
        wf_pos2 = sorted(wf_pos, key=lambda c: -c["total"])
        print(f"\n  Top 10 by total P&L:\n")
        print(f"  {'uhv_body':>8} {'uhv_rng':>7} {'bo_body':>7}  {'WR':>6}  {'n':>4}  "
              f"{'n/d':>5}  {'TRAIN':>9}  {'TEST':>9}  {'TOTAL':>9}")
        for c in wf_pos2[:10]:
            print(f"  {c['ubf']:>8.2f} {c['urm']:>7.1f} {c['bbf']:>7.02f}  {c['wr']:>5.1%}  {c['n']:>4}  "
                  f"{c['n']/nd:>5.1f}  ${c['train']:>+8.1f}  ${c['test']:>+8.1f}  ${c['total']:>+8.1f}")

        # Per-day for best WR config
        best = wf_pos[0]
        print(f"\n{'='*100}")
        print(f"BEST CONFIG: uhv_body>={best['ubf']}, uhv_range>={best['urm']}, bo_body>={best['bbf']}")
        print(f"  WR={best['wr']:.1%}, n={best['n']}, TRAIN=${best['train']:.0f}, TEST=${best['test']:.0f}")
        print(f"{'='*100}")
        sig = {d: detect(cache[d]["m1"], uhv_body_frac=best["ubf"], uhv_range_min=best["urm"],
                         bo_body_frac=best["bbf"]) for d in days}
        print(f"\n  Per-day @{LOTS} lots:")
        worst_day = 0
        daily_pnls = []
        for d in days:
            tr = replay(cache[d]["ticks"], sig[d])
            tot = sum(t["pnl"] for t in tr)
            w = sum(1 for t in tr if t.get("result") == "W")
            n = len(tr)
            daily_pnls.append(tot)
            if tot < worst_day: worst_day = tot
            print(f"    {d}: {n:>3} tr  {w}W/{n-w}L  ${tot:>+8.1f}")
        pos_days = sum(1 for p in daily_pnls if p > 0)
        avg_daily = sum(daily_pnls) / nd
        print(f"    => {pos_days}/{nd} green days, worst: ${worst_day:.1f}, avg: ${avg_daily:.1f}/day")

        # Lot projections
        print(f"\n  Lot size projections (best WR config):")
        print(f"  {'Lots':>6}  {'Daily':>10}  {'Worst day':>10}  {'FTMO?':>8}  {'Monthly':>10}")
        for lots in (0.02, 0.05, 0.10, 0.20, 0.30, 0.50):
            mult = lots / LOTS
            daily = avg_daily * mult
            worst = worst_day * mult
            ftmo = "YES" if abs(worst) < 300 else "NO"
            monthly = daily * 22
            print(f"  {lots:>6.2f}  ${daily:>+8.1f}  ${worst:>+8.1f}  {ftmo:>8}  ${monthly:>+8.0f}")
    else:
        print("  No walk-forward positive combos.")


if __name__ == "__main__":
    main()
