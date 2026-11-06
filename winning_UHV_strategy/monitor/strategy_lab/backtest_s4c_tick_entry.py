"""backtest_s4c_tick_entry.py — Tick-level entry + Zee's scratch/trail exit.

Instead of waiting for bar close, detect the UHV breakout the INSTANT price
crosses the UHV level on an incoming tick. Combined with scratch+trail exit.

ENTRY CONFIRMATION METHODS TO TEST:
1. Simple cross — enter the moment price crosses UHV level
2. Sustained cross — price must stay beyond UHV for N consecutive ticks  
3. Tick velocity — N ticks in same direction before crossing
4. Cross + momentum — cross AND the forming bar's body is in the right direction

EXIT (Zee's style):
- Scratch: exit if adverse excursion from entry >= scratch_pts
- Trail: once profit >= min_profit, exit if price reverses trail_give from peak
- Cap: hard take-profit

Run: py backtest_s4c_tick_entry.py
"""
import sys, glob
from datetime import timedelta, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import group_bars_by_day

CONTRACT = 100.0
LOTS = 0.10
TREND_LB = 30
RETRACE_LB = 12
MOM_BODY_FRAC = 0.55


def trend_dir(bars):
    """Same-TF HH/HL structure from completed bars."""
    if len(bars) < TREND_LB: return 0
    h = TREND_LB // 2
    recent = bars[-h:]
    older = bars[-(TREND_LB):-(h)]
    if not older or not recent: return 0
    if max(b["high"] for b in recent) > max(b["high"] for b in older) and \
       min(b["low"] for b in recent) > min(b["low"] for b in older): return 1
    if max(b["high"] for b in recent) < max(b["high"] for b in older) and \
       min(b["low"] for b in recent) < min(b["low"] for b in older): return -1
    return 0


def efficiency_ratio(bars):
    seg = bars[-TREND_LB:]
    if len(seg) < 2: return 0.0
    net = abs(seg[-1]["close"] - seg[0]["close"])
    path = sum(abs(seg[k]["close"] - seg[k-1]["close"]) for k in range(1, len(seg)))
    return (net / path) if path > 0 else 0.0


def find_uhv_levels(bars):
    """From the last RETRACE_LB completed bars, find the UHV red and green candles.
    Returns (buy_level, sell_level, buy_uhv_vol, sell_uhv_vol) or Nones."""
    if len(bars) < RETRACE_LB: return None, None, 0, 0
    window = bars[-RETRACE_LB:]
    avg_vol = sum(b["vol"] for b in window) / len(window) if window else 1

    # BUY: UHV RED candle's high is the breakout level
    reds = [b for b in window if b["close"] < b["open"]]
    buy_level, buy_vol = None, 0
    if reds:
        uhv = max(reds, key=lambda b: b["vol"])
        buy_level = uhv["high"]
        buy_vol = uhv["vol"]

    # SELL: UHV GREEN candle's low is the breakout level
    greens = [b for b in window if b["close"] > b["open"]]
    sell_level, sell_vol = None, 0
    if greens:
        uhv = max(greens, key=lambda b: b["vol"])
        sell_level = uhv["low"]
        sell_vol = uhv["vol"]

    return buy_level, sell_level, buy_vol, sell_vol


def run_tick_backtest(m1_bars, ticks, scratch_pts=0.3, trail_give=0.3,
                      min_profit=0.3, profit_cap=None, er_min=0.15,
                      confirm_ticks=1, max_conc=3, require_low_vol=True):
    """Tick-level entry backtest.
    
    confirm_ticks: how many consecutive ticks beyond UHV level before entering
                   (1 = enter immediately on cross, 3 = need 3 ticks confirming)
    require_low_vol: if True, track the forming bar's tick count and require it to be
                     less than the UHV candle's volume (matching S4's low-vol breakout rule)
    """
    ppp = LOTS * CONTRACT
    done = []
    positions = []  # active positions

    # Build a time-indexed map of completed bars
    # We'll track which bars have completed as ticks flow
    bar_times = [b["time"] for b in m1_bars]
    completed_bars = []  # bars that have fully closed
    current_bar_idx = 0  # index into m1_bars
    
    # Setup state (recalculated each time a new bar completes)
    buy_level = None
    sell_level = None
    buy_uhv_vol = 0
    sell_uhv_vol = 0
    td = 0
    er = 0.0
    entered_this_bar = False
    
    # Tick-level confirmation state
    buy_confirm_count = 0
    sell_confirm_count = 0
    
    # Forming bar state (to track volume/momentum of current bar)
    forming_bar_ticks = 0
    forming_bar_open = None
    forming_bar_high = -1e18
    forming_bar_low = 1e18
    
    last_bar_time = None

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        mid = (bid + ask) / 2

        # ── Check if a new M1 bar has started ──
        # Find which M1 bar this tick belongs to
        while current_bar_idx < len(m1_bars) - 1 and t >= bar_times[current_bar_idx + 1]:
            # Bar at current_bar_idx has completed
            completed_bars.append(m1_bars[current_bar_idx])
            current_bar_idx += 1
            entered_this_bar = False
            buy_confirm_count = 0
            sell_confirm_count = 0
            forming_bar_ticks = 0
            forming_bar_open = None
            forming_bar_high = -1e18
            forming_bar_low = 1e18

            # Recalculate setup from completed bars
            if len(completed_bars) >= TREND_LB + RETRACE_LB:
                td = trend_dir(completed_bars)
                er = efficiency_ratio(completed_bars)
                bl, sl_lev, bv, sv = find_uhv_levels(completed_bars)
                buy_level = bl if td == 1 and (er_min <= 0 or er >= er_min) else None
                sell_level = sl_lev if td == -1 and (er_min <= 0 or er >= er_min) else None
                buy_uhv_vol = bv
                sell_uhv_vol = sv

        # Track forming bar
        forming_bar_ticks += 1
        if forming_bar_open is None:
            forming_bar_open = mid
        forming_bar_high = max(forming_bar_high, mid)
        forming_bar_low = min(forming_bar_low, mid)

        # ── Manage existing positions ──
        for u in positions[:]:
            s = u["side"]
            if s > 0:
                prof = bid - u["e"]
            else:
                prof = u["e"] - ask

            # Track peak
            if prof > u.get("peak_prof", 0):
                u["peak_prof"] = prof

            # Profit cap
            if profit_cap is not None and prof >= profit_cap:
                u["pnl"] = prof * ppp; u["exit_reason"] = "cap"
                done.append(u); positions.remove(u); continue

            # Scratch
            if prof <= -scratch_pts:
                u["pnl"] = prof * ppp; u["exit_reason"] = "scratch"
                done.append(u); positions.remove(u); continue

            # Trail
            peak = u.get("peak_prof", 0)
            if peak >= min_profit and peak > 0:
                if prof <= peak - trail_give:
                    u["pnl"] = prof * ppp; u["exit_reason"] = "trail"
                    done.append(u); positions.remove(u); continue

        # ── Check for tick-level entry ──
        if entered_this_bar or len(positions) >= max_conc:
            continue

        # BUY: ask crosses above UHV red candle's high
        if buy_level is not None and ask > buy_level:
            # Volume check: forming bar tick count < UHV vol (low-vol breakout)
            vol_ok = (not require_low_vol) or (forming_bar_ticks < buy_uhv_vol)
            # Momentum: forming bar is green (price going up)
            if forming_bar_open is not None:
                mom_ok = mid > forming_bar_open
            else:
                mom_ok = True

            if vol_ok and mom_ok:
                buy_confirm_count += 1
                if buy_confirm_count >= confirm_ticks:
                    positions.append({"side": +1, "e": ask, "open_t": t, "peak_prof": 0.0})
                    entered_this_bar = True
                    buy_level = None  # consume the signal
                    continue
            else:
                buy_confirm_count = 0
        else:
            buy_confirm_count = 0

        # SELL: bid crosses below UHV green candle's low
        if sell_level is not None and bid < sell_level:
            vol_ok = (not require_low_vol) or (forming_bar_ticks < sell_uhv_vol)
            if forming_bar_open is not None:
                mom_ok = mid < forming_bar_open
            else:
                mom_ok = True

            if vol_ok and mom_ok:
                sell_confirm_count += 1
                if sell_confirm_count >= confirm_ticks:
                    positions.append({"side": -1, "e": bid, "open_t": t, "peak_prof": 0.0})
                    entered_this_bar = True
                    sell_level = None
                    continue
            else:
                sell_confirm_count = 0
        else:
            sell_confirm_count = 0

    # Close remaining at EOD
    if ticks:
        last = ticks[-1]
        for u in positions:
            prof = ((last["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - last["ask"]))
            u["pnl"] = prof * ppp; u["exit_reason"] = "eod"
            done.append(u)

    return done


def stat(trades, nd):
    n = len(trades)
    if not n: return f"n={0:>4}", 0, 0, 0
    w = sum(1 for t in trades if t["pnl"] > 0)
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

    print(f"S4c TICK-LEVEL ENTRY + ZEE EXIT — {nd} broker-tick days, {LOTS} lots")
    print(f"{'='*90}\n")

    # ══════════════════════════════════════════════════════════
    # BASELINE: bar-close S4b for comparison
    # ══════════════════════════════════════════════════════════
    from backtest_s4_tp_sweep_and_trend import detect, replay
    sig = {d: detect(cache[d]["m1"], require_trend=True, er_min=0.15) for d in days}
    allt, testt = [], []
    for k, d in enumerate(days):
        tr = replay(cache[d]["ticks"], sig[d], tp_pts=5.0, sl_pts=6.0)
        allt += tr
        if k >= mid: testt += tr
    s1, _, _, _ = stat(allt, nd)
    s2, _, _, _ = stat(testt, nd - mid)
    print(f"BASELINE S4b (bar-close, TP5/SL6):")
    print(f"  ALL: {s1}")
    print(f"  OOS: {s2}\n")

    # ══════════════════════════════════════════════════════════
    # TICK-LEVEL ENTRY SWEEPS
    # ══════════════════════════════════════════════════════════

    # SWEEP 1: Confirmation ticks + scratch+trail exit
    print("=" * 90)
    print("SWEEP 1: Tick entry confirm ticks × scratch/trail params")
    print("=" * 90)

    configs = [
        # (label, scratch, trail, min_prof, cap, confirm, low_vol)
        ("cross+scratch0.3+trail0.3",              0.3, 0.3, 0.3, None, 1, True),
        ("cross+scratch0.3+trail0.3+cap5",         0.3, 0.3, 0.3, 5.0, 1, True),
        ("cross+scratch0.5+trail0.3",              0.5, 0.3, 0.3, None, 1, True),
        ("cross+scratch0.5+trail0.5",              0.5, 0.5, 0.5, None, 1, True),
        ("cross+scratch0.5+trail0.3+cap3",         0.5, 0.3, 0.3, 3.0, 1, True),
        ("cross+scratch0.5+trail0.3+cap5",         0.5, 0.3, 0.3, 5.0, 1, True),
        ("cross+scratch1.0+trail0.5",              1.0, 0.5, 0.5, None, 1, True),
        ("cross+scratch1.0+trail0.5+cap5",         1.0, 0.5, 0.5, 5.0, 1, True),
        ("3tick+scratch0.3+trail0.3",              0.3, 0.3, 0.3, None, 3, True),
        ("3tick+scratch0.5+trail0.3",              0.5, 0.3, 0.3, None, 3, True),
        ("3tick+scratch0.5+trail0.3+cap5",         0.5, 0.3, 0.3, 5.0, 3, True),
        ("5tick+scratch0.3+trail0.3",              0.3, 0.3, 0.3, None, 5, True),
        ("5tick+scratch0.5+trail0.3",              0.5, 0.3, 0.3, None, 5, True),
        ("5tick+scratch0.5+trail0.5+cap5",         0.5, 0.5, 0.5, 5.0, 5, True),
        # Without low-vol requirement
        ("cross+scratch0.3+trail0.3 NO_LVOL",      0.3, 0.3, 0.3, None, 1, False),
        ("cross+scratch0.5+trail0.3 NO_LVOL",      0.5, 0.3, 0.3, None, 1, False),
        ("cross+scratch0.5+trail0.3+cap5 NO_LVOL", 0.5, 0.3, 0.3, 5.0, 1, False),
    ]

    results = []
    for lbl, scratch, trail, mp, cap, confirm, lvol in configs:
        train_t, test_t = [], []
        for k, d in enumerate(days):
            tr = run_tick_backtest(cache[d]["m1"], cache[d]["ticks"],
                                   scratch_pts=scratch, trail_give=trail,
                                   min_profit=mp, profit_cap=cap,
                                   confirm_ticks=confirm, require_low_vol=lvol)
            (train_t if k < mid else test_t).extend(tr)
        all_t = train_t + test_t
        s1, wr1, t1, n1 = stat(all_t, nd)
        s2, wr2, t2, n2 = stat(test_t, nd - mid)
        a = sum(t["pnl"] for t in train_t)
        b = sum(t["pnl"] for t in test_t)
        wf = "✓" if a > 0 and b > 0 else " "
        flag = ""
        if wr1 >= 0.85: flag = " ★★★"
        elif wr1 >= 0.70: flag = " ★★"
        elif wr1 >= 0.55: flag = " ★"
        print(f"  [{wf}] {lbl:<45} ALL: {s1}{flag}")
        print(f"      {'':45} OOS: {s2}")
        results.append({"lbl": lbl, "scratch": scratch, "trail": trail, "mp": mp,
                        "cap": cap, "confirm": confirm, "lvol": lvol,
                        "wr": wr1, "total": t1, "train": a, "test": b, "n": n1,
                        "wr_oos": wr2, "all_trades": all_t, "test_trades": test_t})
    print()

    # ══════════════════════════════════════════════════════════
    # SWEEP 2: Tick entry with FIXED TP/SL (for comparison)
    # ══════════════════════════════════════════════════════════
    print("=" * 90)
    print("SWEEP 2: Tick entry + FIXED TP/SL (does tick entry help even with fixed exits?)")
    print("=" * 90)

    for lbl, tp, sl, confirm in [
        ("tick1 TP5/SL6",  5, 6, 1),
        ("tick1 TP5/SL3",  5, 3, 1),
        ("tick1 TP3/SL3",  3, 3, 1),
        ("tick1 TP2/SL2",  2, 2, 1),
        ("tick1 TP12/SL6", 12, 6, 1),
        ("tick3 TP5/SL6",  5, 6, 3),
        ("tick3 TP5/SL3",  5, 3, 3),
        ("tick5 TP5/SL6",  5, 6, 5),
    ]:
        train_t, test_t = [], []
        for k, d in enumerate(days):
            # Use tick entry but with fixed TP/SL (large scratch = SL, cap = TP)
            tr = run_tick_backtest(cache[d]["m1"], cache[d]["ticks"],
                                   scratch_pts=sl, trail_give=999, min_profit=999,
                                   profit_cap=tp, confirm_ticks=confirm)
            (train_t if k < mid else test_t).extend(tr)
        all_t = train_t + test_t
        s1, wr1, t1, _ = stat(all_t, nd)
        s2, wr2, t2, _ = stat(test_t, nd - mid)
        a = sum(t["pnl"] for t in train_t)
        b = sum(t["pnl"] for t in test_t)
        wf = "✓" if a > 0 and b > 0 else " "
        print(f"  [{wf}] {lbl:<25} ALL: {s1}")
        print(f"      {'':25} OOS: {s2}")
    print()

    # ══════════════════════════════════════════════════════════
    # BEST CONFIG: per-day breakdown + lot projections
    # ══════════════════════════════════════════════════════════
    # Pick best walk-forward positive config
    wf_pos = [r for r in results if r["train"] > 0 and r["test"] > 0]
    if not wf_pos:
        # Fallback: best OOS
        wf_pos = sorted(results, key=lambda r: -r["test"])[:1]
    
    if wf_pos:
        wf_pos.sort(key=lambda r: (-r["wr"], -r["total"]))
        best = wf_pos[0]
        print("=" * 90)
        print(f"BEST CONFIG: {best['lbl']}")
        print(f"  WR={best['wr']:.1%}, n={best['n']}, TRAIN=${best['train']:.0f}, TEST=${best['test']:.0f}")
        print("=" * 90)

        print(f"\n  Per-day breakdown @{LOTS} lots:")
        worst_day = 0
        daily_pnls = []
        for d in days:
            tr = run_tick_backtest(cache[d]["m1"], cache[d]["ticks"],
                                   scratch_pts=best["scratch"], trail_give=best["trail"],
                                   min_profit=best["mp"], profit_cap=best["cap"],
                                   confirm_ticks=best["confirm"], require_low_vol=best["lvol"])
            tot = sum(t["pnl"] for t in tr)
            w = sum(1 for t in tr if t["pnl"] > 0)
            n = len(tr)
            daily_pnls.append(tot)
            if tot < worst_day: worst_day = tot
            print(f"    {d}: {n:>3} tr  {w}W/{n-w}L  ${tot:>+8.1f}")
        pos = sum(1 for p in daily_pnls if p > 0)
        avg_daily = sum(daily_pnls) / nd
        print(f"    => {pos}/{nd} green days, worst day: ${worst_day:.1f}, avg: ${avg_daily:.1f}/day")

        # Lot projections
        print(f"\n  Lot size projections:")
        print(f"  {'Lots':>6}  {'Daily':>10}  {'Worst day':>10}  {'FTMO?':>8}  {'Monthly':>10}")
        for lots in (0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 1.00):
            mult = lots / LOTS
            daily = avg_daily * mult
            worst = worst_day * mult
            ftmo = "YES" if abs(worst) < 300 else "NO"
            monthly = daily * 22
            print(f"  {lots:>6.2f}  ${daily:>+8.1f}  ${worst:>+8.1f}  {ftmo:>8}  ${monthly:>+8.0f}")

        # Exit reason distribution
        print(f"\n  Exit reason distribution:")
        all_tr = best["all_trades"]
        reasons = {}
        for t in all_tr:
            r = t.get("exit_reason", "unknown")
            if r not in reasons: reasons[r] = {"n": 0, "w": 0, "pnl": 0}
            reasons[r]["n"] += 1
            reasons[r]["pnl"] += t["pnl"]
            if t["pnl"] > 0: reasons[r]["w"] += 1
        for r, v in sorted(reasons.items(), key=lambda x: -x[1]["n"]):
            wr_r = v["w"] / v["n"] if v["n"] else 0
            print(f"    {r:<12} n={v['n']:>4}  WR={wr_r:.1%}  ${v['pnl']:>+8.1f}")


if __name__ == "__main__":
    main()
