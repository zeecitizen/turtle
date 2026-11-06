"""v252_hhhl_screener.py — pre-test the v2.52 HH+HL structural gate on real ticks.

Purpose: BEFORE asking Zee to F7+rerun MT5 Strategy Tester, simulate the new
gate against the 8 v2.51 entries on 2026-06-03 and predict which entries the
gate would have blocked. Mirrors the MQL5 logic in HasHHHLTrend() exactly.

This is NOT a re-implementation of the whole EA — it ONLY answers the question:
"For the 8 actual v2.51 entry timestamps, would PassHHHLUptrendGate() /
PassHHHLDowntrendGate() have returned true or false?"

That tells us whether the gate adds value (kills losers) or destroys edge
(kills winners). Output guides the next param sweep in MT5 Strategy Tester.

Run:
    py monitor/strategy_lab/v252_hhhl_screener.py
"""
from __future__ import annotations
import csv, sys
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass

sys.stdout.reconfigure(encoding="utf-8")

TICK_CSV = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/shano_ticks_2026-06-03.csv")

# v2.51 actual entries (from MT5 Strategy Tester journal parse, 03:06 run)
ENTRIES = [
    # (entry_time, side, entry_px, exit_time, exit_px, pnl_usd, outcome)
    ("2026-06-03 07:40:00", "sell", 4471.51, "2026-06-03 10:30:04", 4455.52, +15.99, "W"),
    ("2026-06-03 10:30:05", "sell", 4455.43, "2026-06-03 11:58:08", 4441.51, +13.92, "W"),
    ("2026-06-03 12:29:48", "sell", 4441.61, "2026-06-03 13:06:05", 4454.13, -12.52, "L"),
    ("2026-06-03 13:15:00", "buy",  4463.31, "2026-06-03 16:25:00", 4450.04, -13.27, "L"),
    ("2026-06-03 16:42:51", "sell", 4436.04, "2026-06-03 16:44:24", 4432.57,  +3.47, "W"),
    ("2026-06-03 18:20:35", "sell", 4444.28, "2026-06-03 19:24:13", 4435.01,  +9.27, "W"),
    ("2026-06-03 19:24:13", "sell", 4434.70, "2026-06-03 20:09:20", 4447.23, -12.53, "L"),
    ("2026-06-03 23:50:00", "sell", 4431.46, "2026-06-03 23:59:58", 4435.11,  -3.65, "L"),
]


@dataclass
class Bar:
    t: datetime
    o: float
    h: float
    l: float
    c: float
    v: int  # tick count


def build_bars(tick_csv: Path, timeframe_min: int) -> list[Bar]:
    """Build OHLC bars from a tick CSV. Uses mid (bid+ask)/2 as price."""
    bars: dict[datetime, Bar] = {}
    with tick_csv.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = row.get("ts_broker") or row.get("ts")
            if not ts:
                continue
            try:
                # ts_broker format: 2026.06.03 01:01:01
                dt = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
            except ValueError:
                continue
            # Floor to timeframe
            floor_min = (dt.minute // timeframe_min) * timeframe_min
            bar_t = dt.replace(minute=floor_min, second=0, microsecond=0)
            bid = float(row["bid"])
            ask = float(row["ask"])
            mid = (bid + ask) / 2.0
            b = bars.get(bar_t)
            if b is None:
                bars[bar_t] = Bar(bar_t, mid, mid, mid, mid, 1)
            else:
                if mid > b.h: b.h = mid
                if mid < b.l: b.l = mid
                b.c = mid
                b.v += 1
    return sorted(bars.values(), key=lambda b: b.t)


def has_hhhl_trend(bars: list[Bar], at_time: datetime, lookback: int, pivot_str: int, want_uptrend: bool) -> tuple[bool, list]:
    """Mirror of MQL5 HasHHHLTrend(). Returns (passed, pivot_details_for_debug).

    bar shift 1 = the most recently CLOSED bar at at_time (bar that closed just before at_time).
    Walk from oldest (shift = lookback - pivot_str) to newest (shift = pivot_str + 1).
    """
    # Find the index of the last CLOSED bar at at_time
    last_closed_idx = None
    for i in range(len(bars) - 1, -1, -1):
        # Bar at index i closes at bars[i].t + 5min. Closed means close_time <= at_time.
        # Actually for our purposes: shift 1 = the bar whose CLOSE time is <= at_time
        # bar.t is the OPEN time. Close time = open + tf_min.
        # For M5, close = bar.t + 5min. Shift 1 = the closed bar most recent before at_time.
        tf_min = (bars[1].t - bars[0].t).total_seconds() / 60 if len(bars) > 1 else 5
        close_t = bars[i].t + timedelta(minutes=tf_min)
        if close_t <= at_time:
            last_closed_idx = i
            break
    if last_closed_idx is None:
        return (False, ["no closed bars before " + str(at_time)])

    # Build shift -> bar map. shift 1 = last_closed_idx, shift 2 = last_closed_idx-1, etc.
    def bar_at_shift(shift: int) -> Bar | None:
        idx = last_closed_idx - (shift - 1)
        if idx < 0 or idx >= len(bars):
            return None
        return bars[idx]

    hi1 = hi2 = 0.0
    lo1 = lo2 = 0.0
    hi_cnt = lo_cnt = 0
    pivots_debug = []

    # Walk shift from (lookback - pivot_str) DOWN TO (pivot_str + 1)  — oldest first
    for shift in range(lookback - pivot_str, pivot_str, -1):
        b = bar_at_shift(shift)
        if b is None:
            continue
        is_pivot_hi = True
        is_pivot_lo = True
        for k in range(1, pivot_str + 1):
            bL = bar_at_shift(shift + k)  # older neighbor (larger shift)
            bR = bar_at_shift(shift - k)  # newer neighbor (smaller shift)
            if bL is None or bR is None:
                is_pivot_hi = False
                is_pivot_lo = False
                break
            if b.h <= bL.h or b.h <= bR.h:
                is_pivot_hi = False
            if b.l >= bL.l or b.l >= bR.l:
                is_pivot_lo = False
        if is_pivot_hi:
            hi2 = hi1
            hi1 = b.h
            hi_cnt += 1
            pivots_debug.append(("HI", shift, b.t.strftime("%H:%M"), b.h))
        if is_pivot_lo:
            lo2 = lo1
            lo1 = b.l
            lo_cnt += 1
            pivots_debug.append(("LO", shift, b.t.strftime("%H:%M"), b.l))

    if hi_cnt < 2 or lo_cnt < 2:
        return (False, [f"insufficient pivots: hi={hi_cnt} lo={lo_cnt}"] + pivots_debug)
    if want_uptrend:
        passed = (hi1 > hi2 and lo1 > lo2)
    else:
        passed = (hi1 < hi2 and lo1 < lo2)
    return (passed, pivots_debug + [f"hi1={hi1:.2f} hi2={hi2:.2f} lo1={lo1:.2f} lo2={lo2:.2f}"])


def has_h1_bias(bars: list[Bar], at_time: datetime, bias_bars: int, want_uptrend: bool) -> bool:
    """Mirror of MQL5 PassH1BiasGate(): H1.close[1] vs H1.close[InpH1BiasBars]."""
    # Find shift-1 (most recent closed) and shift-bias_bars
    last_closed_idx = None
    tf_min = (bars[1].t - bars[0].t).total_seconds() / 60 if len(bars) > 1 else 60
    for i in range(len(bars) - 1, -1, -1):
        close_t = bars[i].t + timedelta(minutes=tf_min)
        if close_t <= at_time:
            last_closed_idx = i
            break
    if last_closed_idx is None:
        return False
    idx_recent = last_closed_idx
    idx_older = last_closed_idx - (bias_bars - 1)
    if idx_older < 0:
        return False
    recent = bars[idx_recent].c
    older = bars[idx_older].c
    return (recent > older) if want_uptrend else (recent < older)


def main():
    print(f"Loading ticks from {TICK_CSV.name}...")
    if not TICK_CSV.exists():
        print(f"  MISSING — check path"); return
    m5 = build_bars(TICK_CSV, 5)
    h1 = build_bars(TICK_CSV, 60)
    print(f"  Built {len(m5)} M5 bars, {len(h1)} H1 bars")
    if len(m5) < 20:
        print("  too few M5 bars — aborting"); return
    print(f"  First M5: {m5[0].t}  Last M5: {m5[-1].t}")
    print()

    # Gate config (same defaults as v2.52 inputs)
    PIVOT_STR = 3
    LOOKBACK_M5 = 60
    LOOKBACK_H1 = 24

    H1_BIAS_BARS = 6

    print(f"{'#':>2} {'TIME':<19} {'SIDE':<5} {'PNL':>6} {'WL':>3} | "
          f"{'M5 HHHL':>8} {'H1 HHHL':>8} {'H1 BIAS':>8} | DIAGNOSIS")
    print("-" * 110)

    results = []
    for i, (et, side, epx, xt, xpx, pnl, wl) in enumerate(ENTRIES, 1):
        at = datetime.strptime(et, "%Y-%m-%d %H:%M:%S")
        want_up = (side == "buy")
        m5_ok, m5_dbg = has_hhhl_trend(m5, at, LOOKBACK_M5, PIVOT_STR, want_up)
        h1_ok, h1_dbg = has_hhhl_trend(h1, at, LOOKBACK_H1, PIVOT_STR, want_up)
        h1bias_ok = has_h1_bias(h1, at, H1_BIAS_BARS, want_up)
        # gate_blocks: assume all gates ON together. If ANY gate fails → block.
        gate_blocks = (not m5_ok) or (not h1_ok) or (not h1bias_ok)
        decision = "BLOCK" if gate_blocks else "ALLOW"
        if gate_blocks:
            verdict = "✓ saves $%.2f" % abs(pnl) if wl == "L" else "✗ KILLS WIN $%.2f" % pnl
        else:
            verdict = "neutral (gate inert)"
        m5_str = "PASS" if m5_ok else "FAIL"
        h1_str = "PASS" if h1_ok else "FAIL"
        bias_str = "PASS" if h1bias_ok else "FAIL"
        print(f"{i:>2} {et:<19} {side:<5} {pnl:>+6.2f} {wl:>3} | "
              f"{m5_str:>8} {h1_str:>8} {bias_str:>8} | {decision} → {verdict}")
        results.append({
            "i": i, "time": et, "side": side, "pnl": pnl, "wl": wl,
            "m5_ok": m5_ok, "h1_ok": h1_ok, "h1bias_ok": h1bias_ok,
            "blocked": gate_blocks, "m5_dbg": m5_dbg, "h1_dbg": h1_dbg
        })

    print()
    def wr(rs):
        if not rs: return 0.0
        return 100 * sum(1 for r in rs if r["wl"] == "W") / len(rs)

    def pnl(rs): return sum(r["pnl"] for r in rs)

    configs = [
        ("baseline v2.51 (no gate)",       results),
        ("v2.52 + InpRequireHHHL_M5",      [r for r in results if r["m5_ok"]]),
        ("v2.52 + InpRequireHHHL_H1",      [r for r in results if r["h1_ok"]]),
        ("v2.52 + both HHHL (M5+H1)",      [r for r in results if r["m5_ok"] and r["h1_ok"]]),
        ("v2.52 + InpRequireH1Bias ONLY",  [r for r in results if r["h1bias_ok"]]),
        ("v2.52 + H1Bias + HHHL_M5",       [r for r in results if r["h1bias_ok"] and r["m5_ok"]]),
        ("v2.52 + ALL GATES",              [r for r in results if r["h1bias_ok"] and r["m5_ok"] and r["h1_ok"]]),
    ]

    print("=" * 80)
    print("SUMMARY — what each gate combo would have produced on 2026-06-03:")
    print(f"  {'CONFIG':<38} {'n':>3} {'WR':>5} {'PnL':>10}")
    print("  " + "-" * 65)
    for name, rs in configs:
        print(f"  {name:<38} {len(rs):>3} {wr(rs):>4.0f}% ${pnl(rs):>+9.2f}")
    print()
    best = max(configs, key=lambda c: pnl(c[1]))
    print(f"BEST CONFIG (PnL ranking on this single day): {best[0]} = ${pnl(best[1]):+.2f}")
    print()
    print("CAVEATS:")
    print("  - This is a SINGLE DAY screener (2026-06-03). Don't extrapolate.")
    print("  - Mid-price M5/H1 bars built from ticks may differ slightly from broker bars.")
    print("  - Real MT5 Strategy Tester run REQUIRED for final verdict.")
    print("  - But: this tells us which gate combo is worth running through the Tester first.")


if __name__ == "__main__":
    main()
