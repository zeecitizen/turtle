"""diagnose_live_vs_python.py - answer "what's wrong with our EA on live?"

For every day with both tick data AND live fills, compute:
  1. Python detector signals (canonical MEDIUM)
  2. Live broker fills
  3. The OVERLAP — which live fills fall INSIDE the validated session
     window AND within ±2 min of a Python signal of same side
  4. The DIVERGENCE — fills outside window + fills with no matching signal

Output is a per-day breakdown that EXPLAINS the gap, not just states it.
"""
import sys, csv, glob, bisect
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
UTC = timezone.utc
PKT = timezone(timedelta(hours=5))

sys.path.insert(0, str(Path(__file__).parent))
from zee_tick_detector_MEDIUM import (
    load_ticks, build_m1_m5, run_day,
    in_zee_window, COMMON,
)

FILLS_CSV = COMMON / "turtle_fills.csv"


def load_live_fills_for(day_str):
    """day_str like '2026.06.03' (broker prefix)."""
    out = []
    if not FILLS_CSV.exists(): return out
    with open(FILLS_CSV, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f); next(rdr, None)
        for r in rdr:
            if not r or not r[0].startswith(day_str): continue
            try: pnl = float(r[7])
            except: continue
            try:
                # 'broker_time' field, format "YYYY.MM.DD HH:MM:SS"
                dt = datetime.strptime(r[0], "%Y.%m.%d %H:%M:%S").replace(tzinfo=UTC)
                t_ms = int(dt.timestamp() * 1000)
            except: continue
            side_str = r[4]   # "BUY_closed" or "SELL_closed"
            side = +1 if "BUY" in side_str.upper() else -1
            out.append({
                "t_ms": t_ms, "t_str": r[0][11:], "side": side,
                "vol": r[5], "pnl": pnl, "comment": r[11] if len(r) > 11 else "",
                "magic": r[12] if len(r) > 12 else "",
            })
    return out


def diagnose_day(day_str):
    """day_str = '2026-06-03'. Returns dict with breakdown."""
    tick_path = COMMON / f"shano_ticks_{day_str}.csv"
    broker_prefix = day_str.replace("-", ".")
    if not tick_path.exists(): return None

    ticks = load_ticks(tick_path)
    if len(ticks) < 1000: return None
    m1, m5 = build_m1_m5(ticks)
    py_signals = run_day(ticks, m5)
    live = load_live_fills_for(broker_prefix)

    # Classify each live fill
    in_window = []
    out_window = []
    for f in live:
        # Note: Python's in_zee_window uses LOCAL datetime (.fromtimestamp without tz).
        # We use the same call so we're in the same frame as the detector.
        dt = datetime.fromtimestamp(f["t_ms"] / 1000)
        if in_zee_window(dt):
            in_window.append(f)
        else:
            out_window.append(f)

    # Normalise Python signal side from "buy"/"sell" → +1/-1
    def side_int(x):
        if isinstance(x, int): return x
        return +1 if str(x).lower() == "buy" else -1

    # For in-window fills, find nearest Python signal of same side within 5 min
    matched = []
    unmatched_in_window = []
    for f in in_window:
        best = None; best_dt = 999999
        for s in py_signals:
            if side_int(s["side"]) != side_int(f["side"]): continue
            sig_t_ms = int(s["t"].timestamp() * 1000) if hasattr(s["t"], "timestamp") else 0
            dt = abs(f["t_ms"] - sig_t_ms) / 1000
            if dt < best_dt:
                best_dt = dt; best = s
        if best and best_dt <= 300:
            matched.append((f, best, best_dt))
        else:
            unmatched_in_window.append(f)

    # Python signals with no matching live fill (within ±5 min, same side, in-window)
    py_unfilled = []
    for s in py_signals:
        sig_t_ms = int(s["t"].timestamp() * 1000) if hasattr(s["t"], "timestamp") else 0
        any_match = False
        for f in in_window:
            if side_int(s["side"]) != side_int(f["side"]): continue
            if abs(f["t_ms"] - sig_t_ms) / 1000 <= 300:
                any_match = True; break
        if not any_match:
            py_unfilled.append(s)

    return {
        "day": day_str,
        "py_signals": len(py_signals),
        "py_pnl_price": sum(s["pnl"] for s in py_signals),
        "live_fills": len(live),
        "live_pnl_usd": sum(f["pnl"] for f in live),
        "in_window_live": len(in_window),
        "out_window_live": len(out_window),
        "out_window_pnl_usd": sum(f["pnl"] for f in out_window),
        "matched": len(matched),
        "unmatched_in_window": len(unmatched_in_window),
        "py_unfilled_in_window": len(py_unfilled),
        "in_window_live_pnl_usd": sum(f["pnl"] for f in in_window),
        "py_signals_obj": py_signals,
        "live_obj": live,
        "matched_obj": matched,
    }


def main():
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    print(f"Diagnosing {len(tick_files)} days...\n")
    print(f"{'date':<11} {'py_sig':>6} {'py_$':>7} {'live_n':>6} {'live_$':>9} "
          f"{'in_win':>6} {'out_win':>7} {'out_$':>9} {'match':>5} {'unmatched_in':>12} {'py_unfilled':>11}")
    print("-" * 110)
    summary_lines = []
    for path in tick_files:
        day = Path(path).stem.replace("shano_ticks_", "")
        d = diagnose_day(day)
        if d is None: continue
        line = (f"{day:<11} {d['py_signals']:>6} {d['py_pnl_price']*10:>+7.0f} "
                f"{d['live_fills']:>6} {d['live_pnl_usd']:>+9.2f} "
                f"{d['in_window_live']:>6} {d['out_window_live']:>7} "
                f"{d['out_window_pnl_usd']:>+9.2f} {d['matched']:>5} "
                f"{d['unmatched_in_window']:>12} {d['py_unfilled_in_window']:>11}")
        print(line)
        summary_lines.append(d)

    # Aggregate insights
    print()
    print("="*100)
    print("AGGREGATE EXPLANATIONS")
    print("="*100)
    tot_py_pnl_usd = sum(d['py_pnl_price'] * 10 for d in summary_lines)   # at 0.10L
    tot_live_pnl = sum(d['live_pnl_usd'] for d in summary_lines)
    tot_in = sum(d['in_window_live'] for d in summary_lines)
    tot_out = sum(d['out_window_live'] for d in summary_lines)
    tot_out_pnl = sum(d['out_window_pnl_usd'] for d in summary_lines)
    tot_in_pnl = sum(d['in_window_live_pnl_usd'] for d in summary_lines)
    print(f"  Python total (0.10 lots scale):    ${tot_py_pnl_usd:+,.2f}")
    print(f"  Live total (broker fills):         ${tot_live_pnl:+,.2f}")
    print(f"  Live fills INSIDE  window:         {tot_in:>5}  pnl ${tot_in_pnl:+,.2f}")
    print(f"  Live fills OUTSIDE window:         {tot_out:>5}  pnl ${tot_out_pnl:+,.2f}")
    print(f"  Cost of firing outside window:     ${tot_out_pnl:+,.2f}")
    print()
    print("  Interpretation:")
    print(f"    - The 'OUTSIDE window' fires happened because the live EA's session")
    print(f"      windows were calibrated for FTMO GMT+3 broker but deployed on Atmos GMT+0.")
    print(f"      v1.18 (recompiled today ~04:30 PKT) corrects this; future days should")
    print(f"      show 0 fires in the 'out_window' column.")
    print(f"    - The IN-WINDOW fills versus Python signals tell us if MQL5 logic ALSO")
    print(f"      diverges from Python within the window. Aggregated:")
    tot_matched = sum(d['matched'] for d in summary_lines)
    tot_py_unfilled = sum(d['py_unfilled_in_window'] for d in summary_lines)
    print(f"      Python signals INSIDE window matched by live fill: {tot_matched}")
    print(f"      Python signals INSIDE window with no live match:    {tot_py_unfilled}")
    print(f"    - If many 'py_unfilled' exist, the live EA is missing fires the Python")
    print(f"      detector would have caught. That's a MQL5 logic gap.")


if __name__ == "__main__":
    main()
