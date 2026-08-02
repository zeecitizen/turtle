"""backtest_s4c_tick_entry_v2.py — FIXED tick-level entry.

V1 PROBLEM: 246 entries/day (vs 17 at bar-close) because:
  - Price is already beyond UHV level when the level is recalculated → instant false entry
  - Same UHV candle triggers entries on consecutive bars
  - No "opens inside, closes through" equivalent at tick level

V2 FIXES:
  1. FRESH CROSS: when a new bar recalculates UHV levels, check if price is ALREADY
     beyond the level. If yes, DON'T arm that signal (we missed it).
  2. ONE ENTRY PER UHV: track which UHV candle time produced the level. Don't re-enter
     on the same UHV candle across multiple bars.
  3. CROSS FROM CORRECT SIDE: price must be on the non-broken side at bar open,
     then cross through during the bar.

V1 KEY INSIGHT: Trail exits had 89.1% WR (+$11,880). The exit WORKS. The problem
was purely too many junk entries that immediately got scratched.

Run: py backtest_s4c_tick_entry_v2.py
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


def trend_dir(bars):
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


def find_uhv(bars):
    """From last RETRACE_LB bars, find UHV red (for buy) and UHV green (for sell).
    Returns (buy_level, sell_level, buy_uhv_time, sell_uhv_time, buy_uhv_vol, sell_uhv_vol)."""
    if len(bars) < RETRACE_LB: return None, None, None, None, 0, 0
    window = bars[-RETRACE_LB:]

    reds = [b for b in window if b["close"] < b["open"]]
    buy_level, buy_time, buy_vol = None, None, 0
    if reds:
        uhv = max(reds, key=lambda b: b["vol"])
        buy_level = uhv["high"]
        buy_time = uhv["time"]
        buy_vol = uhv["vol"]

    greens = [b for b in window if b["close"] > b["open"]]
    sell_level, sell_time, sell_vol = None, None, 0
    if greens:
        uhv = max(greens, key=lambda b: b["vol"])
        sell_level = uhv["low"]
        sell_time = uhv["time"]
        sell_vol = uhv["vol"]

    return buy_level, sell_level, buy_time, sell_time, buy_vol, sell_vol


def run_tick_backtest(m1_bars, ticks, scratch_pts=0.5, trail_give=0.3,
                      min_profit=0.3, profit_cap=None, er_min=0.15,
                      confirm_ticks=1, max_conc=1):
    """V2 tick-level entry with fresh-cross + one-per-UHV guards."""
    ppp = LOTS * CONTRACT
    done = []
    positions = []

    bar_times = [b["time"] for b in m1_bars]
    completed_bars = []
    current_bar_idx = 0

    # Setup state
    buy_level = None
    sell_level = None
    buy_armed = False  # True = price started on the correct side, signal is live
    sell_armed = False
    buy_uhv_time = None   # track which UHV candle is being used
    sell_uhv_time = None
    last_buy_uhv_time = None  # last UHV we entered on (don't re-enter)
    last_sell_uhv_time = None
    buy_uhv_vol = 0
    sell_uhv_vol = 0
    entered_this_bar = False

    buy_confirm = 0
    sell_confirm = 0
    forming_ticks = 0
    forming_open_mid = None

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        mid = (bid + ask) / 2

        # ── New bar detection ──
        while current_bar_idx < len(m1_bars) - 1 and t >= bar_times[current_bar_idx + 1]:
            completed_bars.append(m1_bars[current_bar_idx])
            current_bar_idx += 1
            entered_this_bar = False
            buy_confirm = 0
            sell_confirm = 0
            forming_ticks = 0
            forming_open_mid = None

            if len(completed_bars) >= TREND_LB + RETRACE_LB:
                td = trend_dir(completed_bars)
                er = efficiency_ratio(completed_bars)
                bl, sl_lev, bt, st, bv, sv = find_uhv(completed_bars)

                # BUY setup
                if td == 1 and (er_min <= 0 or er >= er_min) and bl is not None:
                    # Only arm if this is a NEW UHV (not the same one we already traded)
                    if bt != last_buy_uhv_time:
                        buy_level = bl
                        buy_uhv_time = bt
                        buy_uhv_vol = bv
                        # FRESH CHECK: is price already beyond the level?
                        buy_armed = (ask <= bl)  # price must be AT or BELOW the level
                    else:
                        buy_armed = False
                else:
                    buy_level = None
                    buy_armed = False

                # SELL setup
                if td == -1 and (er_min <= 0 or er >= er_min) and sl_lev is not None:
                    if st != last_sell_uhv_time:
                        sell_level = sl_lev
                        sell_uhv_time = st
                        sell_uhv_vol = sv
                        sell_armed = (bid >= sl_lev)  # price must be AT or ABOVE
                    else:
                        sell_armed = False
                else:
                    sell_level = None
                    sell_armed = False

        # Track forming bar
        forming_ticks += 1
        if forming_open_mid is None:
            forming_open_mid = mid
            # Also check arm status on first tick of new bar
            if buy_level is not None and ask <= buy_level:
                buy_armed = True
            if sell_level is not None and bid >= sell_level:
                sell_armed = True

        # ── Manage positions ──
        for u in positions[:]:
            s = u["side"]
            prof = (bid - u["e"]) if s > 0 else (u["e"] - ask)
            if prof > u.get("peak_prof", 0): u["peak_prof"] = prof

            if profit_cap is not None and prof >= profit_cap:
                u["pnl"] = prof * ppp; u["exit_reason"] = "cap"
                done.append(u); positions.remove(u); continue
            if prof <= -scratch_pts:
                u["pnl"] = prof * ppp; u["exit_reason"] = "scratch"
                done.append(u); positions.remove(u); continue
            peak = u.get("peak_prof", 0)
            if peak >= min_profit and peak > 0 and prof <= peak - trail_give:
                u["pnl"] = prof * ppp; u["exit_reason"] = "trail"
                done.append(u); positions.remove(u); continue

        # ── Tick-level entry ──
        if entered_this_bar or len(positions) >= max_conc:
            continue

        # BUY: was below level, now crosses above
        if buy_armed and buy_level is not None and ask > buy_level:
            # Momentum: forming bar is green
            if forming_open_mid is not None and mid > forming_open_mid:
                # Low vol: forming bar has fewer ticks than UHV candle
                if forming_ticks < buy_uhv_vol:
                    buy_confirm += 1
                    if buy_confirm >= confirm_ticks:
                        positions.append({"side": +1, "e": ask, "open_t": t, "peak_prof": 0.0})
                        entered_this_bar = True
                        buy_armed = False
                        last_buy_uhv_time = buy_uhv_time  # don't re-enter same UHV
                        continue
        else:
            buy_confirm = 0

        # SELL: was above level, now crosses below
        if sell_armed and sell_level is not None and bid < sell_level:
            if forming_open_mid is not None and mid < forming_open_mid:
                if forming_ticks < sell_uhv_vol:
                    sell_confirm += 1
                    if sell_confirm >= confirm_ticks:
                        positions.append({"side": -1, "e": bid, "open_t": t, "peak_prof": 0.0})
                        entered_this_bar = True
                        sell_armed = False
                        last_sell_uhv_time = sell_uhv_time
                        continue
        else:
            sell_confirm = 0

    # EOD close
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

    print(f"S4c V2 — TICK ENTRY (fresh-cross + one-per-UHV) + ZEE EXIT")
    print(f"{nd} broker-tick days, {LOTS} lots")
    print(f"{'='*90}\n")

    # Baseline
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
    print(f"  ALL: {s1}\n  OOS: {s2}\n")

    # ══════════════════════════════════════════════════════════
    # FULL GRID: scratch × trail × cap × confirm
    # ══════════════════════════════════════════════════════════
    print("=" * 90)
    print("FULL GRID — tick entry + scratch/trail (walk-forward: both halves +)")
    print("=" * 90)

    results = []
    for scratch in (0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0):
        for trail in (0.2, 0.3, 0.5, 0.7, 1.0):
            for mp in (0.0, 0.3, 0.5, 1.0):
                for cap in (None, 2.0, 3.0, 5.0, 8.0, 12.0):
                    for confirm in (1, 3):
                        train, test = [], []
                        for k, d in enumerate(days):
                            tr = run_tick_backtest(cache[d]["m1"], cache[d]["ticks"],
                                                   scratch_pts=scratch, trail_give=trail,
                                                   min_profit=mp, profit_cap=cap,
                                                   confirm_ticks=confirm)
                            (train if k < mid else test).extend(tr)
                        a = sum(t["pnl"] for t in train)
                        b = sum(t["pnl"] for t in test)
                        n_all = len(train) + len(test)
                        w_all = sum(1 for t in train + test if t["pnl"] > 0)
                        wr = w_all / n_all if n_all > 0 else 0
                        results.append({
                            "scratch": scratch, "trail": trail, "mp": mp,
                            "cap": cap, "confirm": confirm, "train": a, "test": b,
                            "total": a + b, "wr": wr, "n": n_all,
                            "all_t": train + test, "test_t": test
                        })

    # Walk-forward positive results
    wf_pos = [r for r in results if r["train"] > 0 and r["test"] > 0 and r["n"] >= 20]
    wf_pos.sort(key=lambda r: (-r["wr"], -r["total"]))

    print(f"\n  Walk-forward positive combos: {len(wf_pos)} / {len(results)}\n")

    if wf_pos:
        print(f"  Top 25 by WR (both halves positive, n≥20):\n")
        print(f"  {'scratch':>7} {'trail':>5} {'mp':>4} {'cap':>5} {'cf':>2}  {'WR':>6}  {'n':>4}  "
              f"{'n/d':>5}  {'TRAIN':>9}  {'TEST':>9}  {'TOTAL':>9}")
        for r in wf_pos[:25]:
            cap_s = f"${r['cap']}" if r['cap'] else "OFF"
            print(f"  {r['scratch']:>7.1f} {r['trail']:>5.2f} {r['mp']:>4.1f} {cap_s:>5} {r['confirm']:>2}  "
                  f"{r['wr']:>5.1%}  {r['n']:>4}  {r['n']/nd:>5.1f}  "
                  f"${r['train']:>+8.1f}  ${r['test']:>+8.1f}  ${r['total']:>+8.1f}")

        # Also by total P&L
        wf_pos2 = sorted(wf_pos, key=lambda r: -r["total"])
        print(f"\n  Top 15 by total P&L:\n")
        print(f"  {'scratch':>7} {'trail':>5} {'mp':>4} {'cap':>5} {'cf':>2}  {'WR':>6}  {'n':>4}  "
              f"{'n/d':>5}  {'TRAIN':>9}  {'TEST':>9}  {'TOTAL':>9}")
        for r in wf_pos2[:15]:
            cap_s = f"${r['cap']}" if r['cap'] else "OFF"
            print(f"  {r['scratch']:>7.1f} {r['trail']:>5.02f} {r['mp']:>4.1f} {cap_s:>5} {r['confirm']:>2}  "
                  f"{r['wr']:>5.1%}  {r['n']:>4}  {r['n']/nd:>5.1f}  "
                  f"${r['train']:>+8.1f}  ${r['test']:>+8.1f}  ${r['total']:>+8.1f}")

        # Pick best high-WR config for detailed analysis
        best = wf_pos[0]  # highest WR
        print(f"\n{'='*90}")
        print(f"BEST HIGH-WR CONFIG: scratch={best['scratch']}, trail={best['trail']}, "
              f"mp={best['mp']}, cap={best['cap']}, confirm={best['confirm']}")
        print(f"  WR={best['wr']:.1%}, n={best['n']}, TRAIN=${best['train']:.0f}, TEST=${best['test']:.0f}")
        print(f"{'='*90}")

        # Per-day
        print(f"\n  Per-day breakdown @{LOTS} lots:")
        worst_day = 0
        daily_pnls = []
        for d in days:
            tr = run_tick_backtest(cache[d]["m1"], cache[d]["ticks"],
                                   scratch_pts=best["scratch"], trail_give=best["trail"],
                                   min_profit=best["mp"], profit_cap=best["cap"],
                                   confirm_ticks=best["confirm"])
            tot = sum(t["pnl"] for t in tr)
            w = sum(1 for t in tr if t["pnl"] > 0)
            n = len(tr)
            daily_pnls.append(tot)
            if tot < worst_day: worst_day = tot
            print(f"    {d}: {n:>3} tr  {w}W/{n-w}L  ${tot:>+8.1f}")
        pos = sum(1 for p in daily_pnls if p > 0)
        avg_daily = sum(daily_pnls) / nd
        print(f"    => {pos}/{nd} green days, worst: ${worst_day:.1f}, avg: ${avg_daily:.1f}/day")

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

        # Exit reasons
        print(f"\n  Exit reason distribution:")
        all_tr = best["all_t"]
        reasons = {}
        for t in all_tr:
            r = t.get("exit_reason", "unknown")
            if r not in reasons: reasons[r] = {"n": 0, "w": 0, "pnl": 0}
            reasons[r]["n"] += 1; reasons[r]["pnl"] += t["pnl"]
            if t["pnl"] > 0: reasons[r]["w"] += 1
        for r, v in sorted(reasons.items(), key=lambda x: -x[1]["n"]):
            wr_r = v["w"] / v["n"] if v["n"] else 0
            print(f"    {r:<12} n={v['n']:>4}  WR={wr_r:.1%}  ${v['pnl']:>+8.1f}")

    else:
        print("  No walk-forward positive combos found.")
        # Show best OOS configs anyway
        results.sort(key=lambda r: -r["test"])
        print(f"\n  Top 10 by OOS (not walk-forward robust but informative):\n")
        for r in results[:10]:
            cap_s = f"${r['cap']}" if r['cap'] else "OFF"
            print(f"  sc={r['scratch']:.1f} tr={r['trail']:.2f} mp={r['mp']:.1f} cap={cap_s} cf={r['confirm']}  "
                  f"WR={r['wr']:.1%} n={r['n']}  TRAIN=${r['train']:+.0f}  TEST=${r['test']:+.0f}")

    # ══════════════════════════════════════════════════════════
    # TICK ENTRY + FIXED TP/SL (cleaner comparison)
    # ══════════════════════════════════════════════════════════
    print(f"\n{'='*90}")
    print("TICK ENTRY + FIXED TP/SL (does tick entry help with fixed exits?)")
    print("=" * 90)
    for lbl, tp, sl in [("TP5/SL6", 5, 6), ("TP5/SL3", 5, 3), ("TP3/SL3", 3, 3),
                          ("TP12/SL6", 12, 6), ("TP8/SL4", 8, 4), ("TP2/SL2", 2, 2)]:
        train_t, test_t = [], []
        for k, d in enumerate(days):
            tr = run_tick_backtest(cache[d]["m1"], cache[d]["ticks"],
                                   scratch_pts=sl, trail_give=999, min_profit=999,
                                   profit_cap=tp, confirm_ticks=1)
            (train_t if k < mid else test_t).extend(tr)
        all_t = train_t + test_t
        s1, wr1, t1, n1 = stat(all_t, nd)
        s2, wr2, t2, n2 = stat(test_t, nd - mid)
        a = sum(t["pnl"] for t in train_t)
        b = sum(t["pnl"] for t in test_t)
        wf = "✓" if a > 0 and b > 0 else " "
        print(f"  [{wf}] {lbl:<12} ALL: {s1}")
        print(f"      {'':12} OOS: {s2}")


if __name__ == "__main__":
    main()
