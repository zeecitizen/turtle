"""losing_chain_forensic.py — isolate and dissect the 1 losing chain in LIVE config baseline.

Runs the LIVE filter stack, captures per-chain metadata (entry, dir, c1/c2 OHLC,
UHV bar, trend EMA values, spread, tick-speed, etc.), then prints:
  - The losing chain in full detail
  - All winning chains for side-by-side comparison
  - Distinguishing features (where loser differs from winners)
"""
from __future__ import annotations
import sys, csv, random, statistics
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import build_1m_bars, ticks_in_range, get_emas, SHADOW_CSV, CONTRACT_SIZE
from filter_loo_correct import (
    actual_tick_speed, actual_spread_check, trend_at, m15_trend_at,
    setup1_active, get_uhv_bar
)

random.seed(42)
PROBE_LOTS = 0.01; PROBE_CONFIRM = 0.45; HORIZON_SEC = 600; PIP_SIZE = 0.10
SLIP_PIPS = 0.5; LAT_MEAN = 300; LAT_STDEV = 100; LAT_MIN = 150; LAT_MAX = 600
COMMISSION_PER_LOT = 3.5


def slipped_fill(when, ticks, dir_sign, intended_price):
    while True:
        ms = random.gauss(LAT_MEAN, LAT_STDEV)
        if LAT_MIN <= ms <= LAT_MAX: break
    target = when + timedelta(milliseconds=ms)
    actual = None
    for dt, bid, ask in ticks:
        if dt >= target: actual = (dt, bid, ask); break
    if actual is None and ticks: actual = ticks[-1]
    if actual is None: return None, None
    dt, bid, ask = actual
    slip = SLIP_PIPS * PIP_SIZE
    return (dt, ask + slip) if dir_sign == 1 else (dt, bid - slip)


def burst_delta_pos(when, dir_sign, lookback_sec):
    end = when; start = end - timedelta(seconds=lookback_sec)
    ticks = ticks_in_range(start, end)
    if len(ticks) < 5: return True
    up = down = 0; prev_mid = None
    for _, bid, ask in ticks:
        mid = (bid + ask) / 2
        if prev_mid is not None:
            if mid > prev_mid: up += 1
            elif mid < prev_mid: down += 1
        prev_mid = mid
    if up + down < 3: return True
    delta = up - down
    return (dir_sign == 1 and delta > 0) or (dir_sign == -1 and delta < 0)


def sim_main(intended_dt, dir_sign, intended_price, ticks, fear_ideal, lots, trail_t, trail_d):
    if not ticks: return 0.0, None, 0.0
    actual_dt, actual_price = slipped_fill(intended_dt, ticks, dir_sign, intended_price)
    if actual_dt is None: return 0.0, None, 0.0
    forward = [t for t in ticks if t[0] >= actual_dt]
    if not forward: return 0.0, None, 0.0
    peak = 0.0; intended_exit_dt = None; intended_exit_price = None
    for dt, bid, ask in forward:
        cur = bid if dir_sign == 1 else ask
        profit = ((cur - actual_price) if dir_sign == 1 else (actual_price - cur)) * lots * CONTRACT_SIZE
        if profit > peak: peak = profit
        if profit <= -fear_ideal: intended_exit_dt = dt; intended_exit_price = cur; break
        if peak >= trail_t and (peak - profit) >= trail_d: intended_exit_dt = dt; intended_exit_price = cur; break
    if intended_exit_dt is None:
        intended_exit_dt = forward[-1][0]
        intended_exit_price = forward[-1][1] if dir_sign == 1 else forward[-1][2]
    actual_exit_dt, actual_exit_price = slipped_fill(intended_exit_dt, forward, -dir_sign, intended_exit_price)
    if actual_exit_dt is None: actual_exit_price = intended_exit_price
    final = ((actual_exit_price - actual_price) if dir_sign == 1 else (actual_price - actual_exit_price)) * lots * CONTRACT_SIZE
    final -= 2 * COMMISSION_PER_LOT * lots
    return round(final, 2), actual_exit_dt, round(peak, 2)


def lot_for_burst(b, start, step, max_lot, min_lot=0.01):
    lot = start + b * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def body(bar): return abs(bar[4] - bar[1])
def rng(bar): return bar[2] - bar[3]
def color(bar): return "RED" if bar[4] < bar[1] else "GREEN" if bar[4] > bar[1] else "DOJI"


def fmt_bar(bar, label=""):
    if bar is None: return f"{label}: None"
    return (f"{label}{bar[0].strftime('%H:%M')} {color(bar):<5s}  "
            f"O={bar[1]:.2f} H={bar[2]:.2f} L={bar[3]:.2f} C={bar[4]:.2f}  "
            f"body={body(bar):.2f}pt  range={rng(bar):.2f}pt  body%={body(bar)/max(rng(bar),0.001)*100:.0f}%  ticks={bar[5]}")


def get_c1_c2(entry_time, bars_1m, bar_idx_1m):
    bm = entry_time.replace(second=0, microsecond=0)
    c2_idx = bar_idx_1m.get(bm)
    if c2_idx is None:
        for d in range(1, 5):
            t = bm - timedelta(minutes=d)
            c2_idx = bar_idx_1m.get(t)
            if c2_idx is not None: break
    if c2_idx is None or c2_idx < 1: return None, None, None
    return bars_1m[c2_idx - 1], bars_1m[c2_idx], c2_idx


def run_with_capture():
    rows = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
    rows.sort(key=lambda r: r.get("entry_time", ""))
    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)
    ema_m15_f, _, bar_idx_15m, _ = get_emas(21, 21, 15)

    chain_records = []
    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue
        ticks = ticks_in_range(entry_time, close_time)
        if not ticks: continue
        actual_entry_dt, actual_entry = slipped_fill(entry_time, ticks, dir_sign, entry_price)
        if actual_entry_dt is None: continue
        entry_time = actual_entry_dt; entry_price = actual_entry
        confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None
        for dt, bid, ask in [t for t in ticks if t[0] >= entry_time]:
            if dir_sign == 1: fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else: fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
                confirm_speed = (dt - entry_time).total_seconds(); break
        if confirm_dt is None: continue

        # LIVE filters
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        if dir_sign == 1 and trigger[4] < uhv[2] + 0.3: continue
        if dir_sign == -1 and trigger[4] > uhv[3] - 0.3: continue
        ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
        if ts is None or ts > 15: continue
        if not actual_spread_check(confirm_dt, 1.2): continue
        ema_v = m15_trend_at(confirm_dt, ema_m15_f, bar_idx_15m)
        if ema_v is not None:
            price = (confirm_bid + confirm_ask) / 2
            if dir_sign == 1 and price <= ema_v: continue
            if dir_sign == -1 and price >= ema_v: continue
        if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10): continue

        # Capture metadata
        c1, c2, c2_idx = get_c1_c2(entry_time, bars_1m, bar_idx_1m)

        # Run main + bursts
        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        cur_dt = confirm_dt; cur_intended = intended_entry; burst_idx = 0
        results = []; peaks = []; exit_dts = []
        while burst_idx < 7:
            lots = lot_for_burst(burst_idx, 0.30, -0.07, 0.30)
            horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
            tt = ticks_in_range(cur_dt, horizon_end)
            pnl, exit_dt, peak = sim_main(cur_dt, dir_sign, cur_intended, tt, 100, lots, 25, 8)
            results.append((lots, pnl))
            peaks.append(peak); exit_dts.append(exit_dt)
            if pnl <= 0: break
            if exit_dt is None: break
            t2 = trend_at(exit_dt, ema_f, ema_s, bar_idx_2m, 2)
            if t2 is None or t2 == 0 or t2 != dir_sign: break
            uhv2, _, _ = get_uhv_bar(exit_dt, bars_1m, bar_idx_1m, 20)
            if uhv2 is None: break
            recent = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
            if recent:
                _, b, a = recent[-1]
                cp = b if dir_sign == -1 else a
                if dir_sign == 1 and cp <= uhv2[2]: break
                if dir_sign == -1 and cp >= uhv2[3]: break
            if not burst_delta_pos(exit_dt, dir_sign, 5): break
            cur_dt = exit_dt
            nt = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
            if nt:
                _, b, a = nt[0]
                cur_intended = a if dir_sign == 1 else b
            else: break
            burst_idx += 1

        chain_pnl = sum(p for _, p in results)
        chain_records.append({
            "entry_time": entry_time, "confirm_dt": confirm_dt, "confirm_speed_sec": confirm_speed,
            "dir": "BUY" if dir_sign == 1 else "SELL", "dir_sign": dir_sign,
            "entry_price": entry_price, "confirm_mid": (confirm_bid + confirm_ask) / 2,
            "uhv_bar": uhv, "trigger_bar": trigger, "c1": c1, "c2": c2,
            "tick_speed_sec": ts, "m15_ema": ema_v,
            "results": results, "peaks": peaks, "exit_dts": exit_dts,
            "chain_pnl": round(chain_pnl, 2), "n_mains": len(results),
            "first_main_pnl": results[0][1] if results else 0,
        })
    return chain_records


def main():
    print("Running LIVE-config backtest with full per-chain capture...\n")
    chains = run_with_capture()
    print(f"Captured {len(chains)} chains\n")

    losers = [c for c in chains if c["chain_pnl"] < 0]
    winners = [c for c in chains if c["chain_pnl"] > 0]
    print(f"Winners: {len(winners)}  |  Losers: {len(losers)}\n")

    print("=" * 110)
    print("OVERVIEW: each chain's first-main P&L and chain total")
    print("=" * 110)
    for i, c in enumerate(chains):
        flag = " <<< LOSING CHAIN" if c["chain_pnl"] < 0 else ""
        print(f"  [{i+1}] {c['entry_time'].strftime('%Y-%m-%d %H:%M:%S')}  {c['dir']}  "
              f"first_main=${c['first_main_pnl']:+7.2f}  chain_total=${c['chain_pnl']:+7.2f}  "
              f"n_mains={c['n_mains']}{flag}")
    print()

    if not losers:
        print("No losing chains found.")
        return

    print("=" * 110)
    print("LOSING CHAIN — full forensic detail")
    print("=" * 110)
    for c in losers:
        print(f"\nEntry: {c['entry_time']}  Confirm: {c['confirm_dt']} ({c['confirm_speed_sec']:.1f}s after entry)")
        print(f"  Direction: {c['dir']}  Entry price: {c['entry_price']:.2f}  Confirm mid: {c['confirm_mid']:.2f}")
        m15 = c['m15_ema'] if c['m15_ema'] is not None else 0
        side = 'above' if c['confirm_mid'] > m15 else 'below'
        print(f"  M15 21-EMA at confirm: {m15:.2f}  (price was {side} EMA)")
        print(f"  Tick-speed (entry to UHV cross): {c['tick_speed_sec']}s")
        print(f"  Day of week: {c['entry_time'].strftime('%A')}  Hour UTC: {c['entry_time'].hour}")
        print()
        print(f"  c1 (Shano bigness trigger): {fmt_bar(c['c1'])}")
        print(f"  c2 (Shano confirm bar):     {fmt_bar(c['c2'])}")
        print(f"  UHV bar (Setup 1 catalyst): {fmt_bar(c['uhv_bar'])}")
        print(f"  Setup 1 trigger bar:        {fmt_bar(c['trigger_bar'])}")
        print()
        print(f"  Mains in chain:")
        for j, ((lots, pnl), peak, exit_dt) in enumerate(zip(c["results"], c["peaks"], c["exit_dts"])):
            print(f"    [{j+1}] lots={lots:.2f}  pnl=${pnl:+7.2f}  peak=${peak:+6.2f}  exit={exit_dt}")
        print(f"  CHAIN TOTAL: ${c['chain_pnl']:+.2f}")

    print("\n" + "=" * 110)
    print("WINNERS — for comparison (key features)")
    print("=" * 110)
    for c in winners:
        c1_body = body(c["c1"]) if c["c1"] else 0
        c2_body = body(c["c2"]) if c["c2"] else 0
        c2_strength = (c2_body / rng(c["c2"]) * 100) if c["c2"] and rng(c["c2"]) > 0 else 0
        uhv_body = body(c["uhv_bar"]) if c["uhv_bar"] else 0
        uhv_strength = (uhv_body / rng(c["uhv_bar"]) * 100) if c["uhv_bar"] and rng(c["uhv_bar"]) > 0 else 0
        print(f"  {c['entry_time'].strftime('%H:%M')}  {c['dir']:<4s}  "
              f"chain=${c['chain_pnl']:+7.2f}  "
              f"c1_body={c1_body:.2f}pt  c2_body={c2_body:.2f}pt  c2_strength={c2_strength:.0f}%  "
              f"UHV_body={uhv_body:.2f}pt  UHV_strength={uhv_strength:.0f}%  "
              f"tick_speed={c['tick_speed_sec']}s")

    print("\n" + "=" * 110)
    print("LOSER vs WINNERS — distinguishing features")
    print("=" * 110)
    if losers and winners:
        l = losers[0]
        l_c1 = body(l["c1"]) if l["c1"] else 0
        l_c2 = body(l["c2"]) if l["c2"] else 0
        l_c2_str = (l_c2 / rng(l["c2"]) * 100) if l["c2"] and rng(l["c2"]) > 0 else 0
        l_uhv = body(l["uhv_bar"]) if l["uhv_bar"] else 0
        l_uhv_str = (l_uhv / rng(l["uhv_bar"]) * 100) if l["uhv_bar"] and rng(l["uhv_bar"]) > 0 else 0
        l_tspd = l["tick_speed_sec"]

        feats = {
            "c1_body":      [body(c["c1"]) for c in winners if c["c1"]],
            "c2_body":      [body(c["c2"]) for c in winners if c["c2"]],
            "c2_strength":  [(body(c["c2"])/rng(c["c2"])*100) for c in winners if c["c2"] and rng(c["c2"]) > 0],
            "UHV_body":     [body(c["uhv_bar"]) for c in winners if c["uhv_bar"]],
            "UHV_strength": [(body(c["uhv_bar"])/rng(c["uhv_bar"])*100) for c in winners if c["uhv_bar"] and rng(c["uhv_bar"]) > 0],
            "tick_speed":   [c["tick_speed_sec"] for c in winners if c["tick_speed_sec"] is not None],
            "confirm_speed":[c["confirm_speed_sec"] for c in winners if c["confirm_speed_sec"] is not None],
        }
        loser_vals = {
            "c1_body": l_c1, "c2_body": l_c2, "c2_strength": l_c2_str,
            "UHV_body": l_uhv, "UHV_strength": l_uhv_str,
            "tick_speed": l_tspd, "confirm_speed": l["confirm_speed_sec"],
        }
        print(f"  {'feature':<18s}  {'loser':>9s}  {'win_min':>8s}  {'win_med':>8s}  {'win_max':>8s}  {'verdict':<30s}")
        for k, vals in feats.items():
            if not vals: continue
            v = loser_vals[k]
            mn, md, mx = min(vals), statistics.median(vals), max(vals)
            verdict = ""
            if v < mn: verdict = "BELOW any winner"
            elif v > mx: verdict = "ABOVE any winner"
            else:
                if v < md: verdict = "below winner median"
                else: verdict = "above winner median"
            print(f"  {k:<18s}  {v:>9.2f}  {mn:>8.2f}  {md:>8.2f}  {mx:>8.2f}  {verdict}")

    print("\n" + "=" * 110)
    print("Day-of-week + hour distribution (looking for time clusters)")
    print("=" * 110)
    for c in chains:
        flag = "L" if c["chain_pnl"] < 0 else "W"
        print(f"  [{flag}]  {c['entry_time'].strftime('%a %Y-%m-%d %H:%M UTC')}  ${c['chain_pnl']:+7.2f}")


if __name__ == "__main__":
    main()
