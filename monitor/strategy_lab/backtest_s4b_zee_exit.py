"""backtest_s4b_zee_exit.py — Program Zee's ACTUAL exit into S4b and backtest it.

Zee's exit from the Feb-11 report:
  - Avg win: 1.54 pts  (he rides winners for 1-2 pts, sometimes 6 pts on big moves)
  - Avg loss: 0.16 pts (he SCRATCHES losers at essentially breakeven - just spread)
  - He exits the INSTANT it goes against him — no fixed SL

EA exit logic to replicate this:
  1. Track price tick-by-tick after entry
  2. SCRATCH: if adverse excursion from entry exceeds scratch_pts → EXIT (tiny loss)
  3. TRAIL: once profit exceeds min_profit → trail with tight give-back from peak
  4. TIME SCRATCH: if after N seconds still not in profit → exit at market

Sweep parameters to find the best config, then project at different lot sizes.

Run: py backtest_s4b_zee_exit.py
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
MOM_BODY_FRAC = 0.55


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


def detect(m1, er_min=0.15):
    sigs = []
    start = TREND_LB + RETRACE_LB + 2
    for i in range(start, len(m1)):
        bo = m1[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < MOM_BODY_FRAC: continue
        win = m1[i - RETRACE_LB:i]
        avgbody = sum(abs(b["close"] - b["open"]) for b in win) / len(win)
        if body < avgbody: continue
        tw = m1[i - TREND_LB:i]
        if er_min > 0 and efficiency_ratio(tw) < er_min: continue
        td = trend_dir(tw)
        if bo["close"] > bo["open"] and td == 1:
            reds = [b for b in win if b["close"] < b["open"]]
            if reds:
                uhv = max(reds, key=lambda b: b["vol"])
                if bo["vol"] < uhv["vol"] and bo["close"] > uhv["high"] and bo["open"] <= uhv["high"]:
                    sigs.append({"side": +1, "fire_time": bo["time"] + timedelta(minutes=1)})
                    continue
        if bo["close"] < bo["open"] and td == -1:
            greens = [b for b in win if b["close"] > b["open"]]
            if greens:
                uhv = max(greens, key=lambda b: b["vol"])
                if bo["vol"] < uhv["vol"] and bo["close"] < uhv["low"] and bo["open"] >= uhv["low"]:
                    sigs.append({"side": -1, "fire_time": bo["time"] + timedelta(minutes=1)})
    return sigs


def replay_zee_exit(ticks, sigs, scratch_pts, trail_give, min_profit=0.0,
                    scratch_secs=None, profit_cap=None, max_conc=3):
    """Zee's exit: scratch losers fast, trail winners tight.

    scratch_pts:  max adverse excursion before scratch exit (e.g. 0.3 = exit if -$0.30)
    trail_give:   once in profit, give-back from peak before exit (e.g. 0.2)
    min_profit:   profit threshold to activate trailing (0 = trail from entry)
    scratch_secs: time-based scratch — if not in profit after N secs, exit at market
    profit_cap:   hard cap — grab profit immediately at this level
    """
    ppp = LOTS * CONTRACT
    done = []
    it = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pend = next(it, None)
    units = []

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]

        for u in units[:]:
            s = u["side"]
            # current P&L in price pts
            if s > 0:
                cur_price = bid  # sell to exit buy
                prof = cur_price - u["e"]
            else:
                cur_price = ask  # buy to exit sell
                prof = u["e"] - cur_price

            # Update peak favorable excursion
            if prof > u.get("peak_prof", 0):
                u["peak_prof"] = prof

            # 1. PROFIT CAP — hard take-profit
            if profit_cap is not None and prof >= profit_cap:
                u["pnl"] = prof * ppp
                u["exit_reason"] = "cap"
                done.append(u); units.remove(u); continue

            # 2. SCRATCH — adverse excursion from entry exceeds threshold
            if prof <= -scratch_pts:
                u["pnl"] = prof * ppp
                u["exit_reason"] = "scratch"
                done.append(u); units.remove(u); continue

            # 3. TRAILING — once past min_profit, exit on give-back from peak
            peak = u.get("peak_prof", 0)
            if peak >= min_profit and peak > 0:
                if prof <= peak - trail_give:
                    u["pnl"] = prof * ppp
                    u["exit_reason"] = "trail"
                    done.append(u); units.remove(u); continue

            # 4. TIME SCRATCH — not in profit after N seconds
            if scratch_secs is not None and prof < 0:
                elapsed = (t - u["open_t"]).total_seconds()
                if elapsed >= scratch_secs:
                    u["pnl"] = prof * ppp
                    u["exit_reason"] = "time_scratch"
                    done.append(u); units.remove(u); continue

        # Fire new entries
        while pend is not None and t >= pend["fire_time"]:
            if len(units) < max_conc:
                e = ask if pend["side"] > 0 else bid
                units.append({"side": pend["side"], "e": e, "open_t": t, "peak_prof": 0.0})
            pend = next(it, None)

    # Close remaining at EOD
    if ticks:
        last = ticks[-1]
        for u in units:
            prof = ((last["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - last["ask"]))
            u["pnl"] = prof * ppp
            u["exit_reason"] = "eod"
            done.append(u)
    return done


def stat(trades, nd):
    n = len(trades)
    if not n: return "n=0", 0, 0, 0
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    w = len(wins)
    wr = w / n if n > 0 else 0
    tot = sum(t["pnl"] for t in trades)
    avg_w = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
    avg_l = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
    s = (f"n={n:>4} {n/nd:>5.1f}/d  WR={wr:>5.1%}  "
         f"W=${avg_w:>5.1f}  L=${avg_l:>+5.1f}  TOT=${tot:>+9.1f}")
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
    print(f"S4b ZEE-EXIT BACKTEST — {nd} broker-tick days, {LOTS} lots\n")

    sig = {d: detect(cache[d]["m1"]) for d in days}
    nsig = sum(len(sig[d]) for d in days)
    print(f"Entry signals: {nsig} over {nd} days = {nsig/nd:.1f}/day\n")

    # ══════════════════════════════════════════════════════════════
    # BASELINE comparison
    # ══════════════════════════════════════════════════════════════
    print("=== BASELINES (for comparison) ===")
    from backtest_s4_tp_sweep_and_trend import replay as replay_fixed
    for lbl, tp, sl in [("S4b: TP5/SL6", 5, 6), ("S4: TP12/SL6", 12, 6)]:
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay_fixed(cache[d]["ticks"], sig[d], tp_pts=tp, sl_pts=sl)
            allt += tr
            if k >= mid: testt += tr
        s1, _, _, _ = stat(allt, nd)
        s2, _, _, _ = stat(testt, nd - mid)
        print(f"  {lbl:<25} ALL: {s1}")
        print(f"  {'':25} OOS: {s2}")
    print()

    # ══════════════════════════════════════════════════════════════
    # SWEEP 1: Scratch distance (how fast we cut losers)
    # ══════════════════════════════════════════════════════════════
    print("=" * 90)
    print("SWEEP 1: Scratch distance (trail_give=0.3, min_profit=0.3)")
    print("=" * 90)
    best = None
    for scratch in (0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0):
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay_zee_exit(cache[d]["ticks"], sig[d],
                                 scratch_pts=scratch, trail_give=0.3, min_profit=0.3)
            allt += tr
            if k >= mid: testt += tr
        s1, wr1, t1, _ = stat(allt, nd)
        s2, wr2, t2, _ = stat(testt, nd - mid)
        flag = " ★" if wr1 >= 0.85 and t1 > 0 else ""
        print(f"  scratch={scratch:<4.1f}  ALL: {s1}{flag}")
        print(f"  {'':14} OOS: {s2}")
        if t1 > 0 and (best is None or t1 > best[1]):
            best = (scratch, t1, wr1)
    print(f"\n  Best scratch: {best[0]} (tot=${best[1]:.0f}, WR={best[2]:.1%})\n" if best else "")

    # ══════════════════════════════════════════════════════════════
    # SWEEP 2: Trail give-back (how tight we trail winners)
    # ══════════════════════════════════════════════════════════════
    print("=" * 90)
    print("SWEEP 2: Trail give-back (scratch=0.3, min_profit=0.3)")
    print("=" * 90)
    for trail in (0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0, 1.5, 2.0):
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay_zee_exit(cache[d]["ticks"], sig[d],
                                 scratch_pts=0.3, trail_give=trail, min_profit=0.3)
            allt += tr
            if k >= mid: testt += tr
        s1, wr1, t1, _ = stat(allt, nd)
        s2, _, _, _ = stat(testt, nd - mid)
        flag = " ★" if wr1 >= 0.85 and t1 > 0 else ""
        print(f"  trail={trail:<4.2f}  ALL: {s1}{flag}")
        print(f"  {'':13} OOS: {s2}")
    print()

    # ══════════════════════════════════════════════════════════════
    # SWEEP 3: Min profit to activate trailing
    # ══════════════════════════════════════════════════════════════
    print("=" * 90)
    print("SWEEP 3: Min profit before trailing (scratch=0.3, trail=0.3)")
    print("=" * 90)
    for mp in (0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0):
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay_zee_exit(cache[d]["ticks"], sig[d],
                                 scratch_pts=0.3, trail_give=0.3, min_profit=mp)
            allt += tr
            if k >= mid: testt += tr
        s1, wr1, t1, _ = stat(allt, nd)
        s2, _, _, _ = stat(testt, nd - mid)
        flag = " ★" if wr1 >= 0.85 and t1 > 0 else ""
        print(f"  min_prof={mp:<4.1f}  ALL: {s1}{flag}")
        print(f"  {'':16} OOS: {s2}")
    print()

    # ══════════════════════════════════════════════════════════════
    # SWEEP 4: Time scratch (exit if not profitable after N secs)
    # ══════════════════════════════════════════════════════════════
    print("=" * 90)
    print("SWEEP 4: Time scratch (scratch=0.3, trail=0.3, min_profit=0.3)")
    print("=" * 90)
    for ts in (None, 5, 10, 15, 20, 30, 45, 60):
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay_zee_exit(cache[d]["ticks"], sig[d],
                                 scratch_pts=0.3, trail_give=0.3, min_profit=0.3,
                                 scratch_secs=ts)
            allt += tr
            if k >= mid: testt += tr
        s1, wr1, t1, _ = stat(allt, nd)
        s2, _, _, _ = stat(testt, nd - mid)
        lbl = f"{ts}s" if ts else "OFF"
        print(f"  time_scratch={lbl:<4}  ALL: {s1}")
        print(f"  {'':20} OOS: {s2}")
    print()

    # ══════════════════════════════════════════════════════════════
    # SWEEP 5: Profit cap (hard grab)
    # ══════════════════════════════════════════════════════════════
    print("=" * 90)
    print("SWEEP 5: Profit cap (scratch=0.3, trail=0.3, min_profit=0.3)")
    print("=" * 90)
    for cap in (None, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 12.0):
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay_zee_exit(cache[d]["ticks"], sig[d],
                                 scratch_pts=0.3, trail_give=0.3, min_profit=0.3,
                                 profit_cap=cap)
            allt += tr
            if k >= mid: testt += tr
        s1, wr1, t1, _ = stat(allt, nd)
        s2, _, _, _ = stat(testt, nd - mid)
        lbl = f"${cap}" if cap else "OFF"
        print(f"  cap={lbl:<5}  ALL: {s1}")
        print(f"  {'':12} OOS: {s2}")
    print()

    # ══════════════════════════════════════════════════════════════
    # FULL GRID: best combos (scratch × trail × cap)
    # ══════════════════════════════════════════════════════════════
    print("=" * 90)
    print("FULL GRID — best combos (walk-forward: both halves must be positive)")
    print("=" * 90)
    results = []
    for scratch in (0.2, 0.3, 0.5, 0.7, 1.0):
        for trail in (0.15, 0.2, 0.3, 0.5, 0.7):
            for mp in (0.0, 0.3, 0.5, 1.0):
                for cap in (None, 2.0, 3.0, 5.0):
                    train, test = [], []
                    for k, d in enumerate(days):
                        tr = replay_zee_exit(cache[d]["ticks"], sig[d],
                                             scratch_pts=scratch, trail_give=trail,
                                             min_profit=mp, profit_cap=cap)
                        (train if k < mid else test).extend(tr)
                    a = sum(t["pnl"] for t in train)
                    b = sum(t["pnl"] for t in test)
                    n_all = len(train) + len(test)
                    w_all = sum(1 for t in train + test if t["pnl"] > 0)
                    wr = w_all / n_all if n_all > 0 else 0
                    if a > 0 and b > 0:
                        results.append({
                            "scratch": scratch, "trail": trail, "mp": mp,
                            "cap": cap, "train": a, "test": b, "total": a + b,
                            "wr": wr, "n": n_all, "ntrain": len(train), "ntest": len(test)
                        })

    # Sort by WR (we want highest WR that's still profitable)
    results.sort(key=lambda r: (-r["wr"], -r["total"]))
    print(f"\n  Top 20 combos by WR (both halves positive):\n")
    print(f"  {'scratch':>7} {'trail':>5} {'mp':>4} {'cap':>5}  {'WR':>6}  {'n':>4}  "
          f"{'TRAIN':>9}  {'TEST':>9}  {'TOTAL':>9}")
    for r in results[:20]:
        cap_s = f"${r['cap']}" if r['cap'] else "OFF"
        print(f"  {r['scratch']:>7.1f} {r['trail']:>5.2f} {r['mp']:>4.1f} {cap_s:>5}  "
              f"{r['wr']:>5.1%}  {r['n']:>4}  "
              f"${r['train']:>+8.1f}  ${r['test']:>+8.1f}  ${r['total']:>+8.1f}")

    # Also top 10 by total P&L
    results.sort(key=lambda r: -r["total"])
    print(f"\n  Top 10 combos by total P&L (both halves positive):\n")
    print(f"  {'scratch':>7} {'trail':>5} {'mp':>4} {'cap':>5}  {'WR':>6}  {'n':>4}  "
          f"{'TRAIN':>9}  {'TEST':>9}  {'TOTAL':>9}")
    for r in results[:10]:
        cap_s = f"${r['cap']}" if r['cap'] else "OFF"
        print(f"  {r['scratch']:>7.1f} {r['trail']:>5.02f} {r['mp']:>4.1f} {cap_s:>5}  "
              f"{r['wr']:>5.1%}  {r['n']:>4}  "
              f"${r['train']:>+8.1f}  ${r['test']:>+8.1f}  ${r['total']:>+8.1f}")

    # ══════════════════════════════════════════════════════════════
    # LOT PROJECTIONS for the best high-WR config
    # ══════════════════════════════════════════════════════════════
    if results:
        # Pick the best WR config with reasonable n
        hi_wr = [r for r in results if r["wr"] >= 0.80 and r["n"] >= 50]
        if not hi_wr:
            hi_wr = [r for r in results if r["wr"] >= 0.70 and r["n"] >= 50]
        if not hi_wr:
            hi_wr = results[:1]  # fallback to best total
        hi_wr.sort(key=lambda r: (-r["wr"], -r["total"]))
        best = hi_wr[0]

        print(f"\n{'='*90}")
        print(f"LOT SIZE PROJECTIONS — Best high-WR config")
        print(f"  scratch={best['scratch']}, trail={best['trail']}, "
              f"min_profit={best['mp']}, cap={best['cap']}")
        print(f"  WR={best['wr']:.1%}, n={best['n']}, TRAIN=${best['train']:.0f}, "
              f"TEST=${best['test']:.0f}")
        print(f"{'='*90}")

        # Per-day breakdown at 0.10 lots
        print(f"\n  Per-day breakdown @0.10 lots:")
        worst_day = 0
        daily_pnls = []
        for d in days:
            tr = replay_zee_exit(cache[d]["ticks"], sig[d],
                                 scratch_pts=best["scratch"], trail_give=best["trail"],
                                 min_profit=best["mp"], profit_cap=best["cap"])
            tot = sum(t["pnl"] for t in tr)
            w = sum(1 for t in tr if t["pnl"] > 0)
            n = len(tr)
            daily_pnls.append(tot)
            if tot < worst_day: worst_day = tot
            print(f"    {d}: {n:>3} tr  {w}W/{n-w}L  ${tot:>+8.1f}")
        pos = sum(1 for p in daily_pnls if p > 0)
        print(f"    => {pos}/{nd} green days, worst day: ${worst_day:.1f}")

        # Lot projections
        base_daily = sum(daily_pnls) / nd
        print(f"\n  Projected P&L at different lot sizes (avg ${base_daily:.1f}/day @0.10):")
        print(f"  {'Lots':>6}  {'Daily':>10}  {'Worst day':>10}  {'FTMO safe?':>12}  {'Monthly':>10}")
        for lots in (0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 1.00):
            mult = lots / LOTS
            daily = base_daily * mult
            worst = worst_day * mult
            ftmo = "YES" if abs(worst) < 300 else "NO"
            monthly = daily * 22
            print(f"  {lots:>6.2f}  ${daily:>+8.1f}  ${worst:>+8.1f}  {'   ' + ftmo:>12}  ${monthly:>+8.0f}")

        # Exit reason distribution
        print(f"\n  Exit reason distribution (all trades):")
        all_tr = []
        for d in days:
            all_tr += replay_zee_exit(cache[d]["ticks"], sig[d],
                                      scratch_pts=best["scratch"], trail_give=best["trail"],
                                      min_profit=best["mp"], profit_cap=best["cap"])
        reasons = {}
        for t in all_tr:
            r = t.get("exit_reason", "unknown")
            if r not in reasons: reasons[r] = {"n": 0, "pnl": 0}
            reasons[r]["n"] += 1
            reasons[r]["pnl"] += t["pnl"]
        for r, v in sorted(reasons.items(), key=lambda x: -x[1]["n"]):
            wr_r = sum(1 for t in all_tr if t.get("exit_reason") == r and t["pnl"] > 0) / v["n"] if v["n"] else 0
            print(f"    {r:<15} n={v['n']:>4}  WR={wr_r:.1%}  ${v['pnl']:>+8.1f}")


if __name__ == "__main__":
    main()
