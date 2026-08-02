"""feb11_exit_validation.py — S6 of the autopilot state machine.

THE question (post-mortem 2026-07-21): is the −$177 caused by an INVERTED exit
(winners capped 1.3pt / losers wide 2-6pt), and does the Feb-11 asymmetric exit
(cut losers tiny, let winners run) turn it net-positive?

Method (honest, per doctrine — validate on P&L, not WR):
  1. Reuse the SAME M1 UHV entry detector the live EA logic mirrors
     (screener_canonical_uhv_m1.detect) over all available tick-days.
  2. For each entry, simulate several EXIT policies at TICK level (accurate for
     trailing) from the fill forward.
  3. Compare per-policy: trades, WR, avg win, avg loss, R:R, max single loss,
     NET P&L (in price points AND $ at 0.30 lot).

Entry is FROZEN (see memory exit-is-the-edge). We only vary the EXIT here.

Usage: py monitor/strategy_lab/feb11_exit_validation.py --days 40
"""
from __future__ import annotations
import argparse, csv, json, sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from screener_canonical_uhv_m1 import build_m1, detect, TICK_DIR, OUT_DIR  # reuse detector

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

DOLLAR_PER_PT_PER_LOT = 100.0   # XAUUSD: $1 price move × 1 lot = $100
LOT = 0.30                      # current live-demo lot
SLIP_PTS = 0.15                 # round-trip spread/slippage cost in price points
WINDOW_MIN = 120                # max hold before force-exit at market


# ── Exit policies (price points, entry-relative). tp=None → no fixed target ──
POLICIES = {
    # what the EA does NOW: tiny TP, wide UHV-based SL  → the inverted config
    "CURRENT_live":      {"tp": 1.3,  "sl": "uhv", "arm": None, "give": None},
    # isolate the SL fix only: same tiny TP but tight loss-cut
    "current_tightSL":   {"tp": 1.3,  "sl": 1.5,   "arm": None, "give": None},
    # Feb-11 style: cut losers tiny, LET WINNERS RUN with late-arm wide-give trail
    "feb11_A":           {"tp": 8.0,  "sl": 1.5,   "arm": 3.0,  "give": 1.5},
    "feb11_B":           {"tp": 10.0, "sl": 1.5,   "arm": 4.0,  "give": 2.0},
    "feb11_C":           {"tp": 8.0,  "sl": 2.0,   "arm": 3.0,  "give": 1.5},
    "feb11_tight":       {"tp": 6.0,  "sl": 1.5,   "arm": 2.0,  "give": 1.0},
    "feb11_runwide":     {"tp": None, "sl": 1.5,   "arm": 5.0,  "give": 2.5},
    "feb11_2pt_run":     {"tp": None, "sl": 2.0,   "arm": 4.0,  "give": 2.0},
}


def load_ticks_by_date():
    """date_str(YYYY-MM-DD) -> sorted [(dt, bid, ask)]."""
    out = {}
    for p in sorted(TICK_DIR.glob("shano_ticks_2026-*.csv")):
        date_str = p.stem.replace("shano_ticks_", "")
        ticks = []
        try:
            with p.open(newline="", encoding="utf-8", errors="ignore") as f:
                r = csv.DictReader(f)
                for row in r:
                    ts = row.get("ts_broker") or row.get("ts") or row.get("t")
                    if not ts: continue
                    if "." in ts.split(" ", 1)[-1]:
                        ts = ts.rsplit(".", 1)[0]
                    try: dt = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
                    except ValueError: continue
                    try: bid = float(row["bid"]); ask = float(row["ask"])
                    except (KeyError, ValueError): continue
                    ticks.append((dt, bid, ask))
        except Exception:
            continue
        ticks.sort(key=lambda x: x[0])
        if ticks: out[date_str] = ticks
    return out


def find_idx(ticks, target):
    lo, hi = 0, len(ticks) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if ticks[mid][0] < target: lo = mid + 1
        else: hi = mid
    return lo if lo < len(ticks) and ticks[lo][0] >= target else None


def simulate_exit(ticks, start_idx, side, entry, policy, uhv_sl_dist):
    """Return (reason, pnl_pts) for one entry under one exit policy, tick-level."""
    if start_idx is None or start_idx >= len(ticks):
        return ("no_data", 0.0)
    sl = policy["sl"]
    sl_dist = uhv_sl_dist if sl == "uhv" else float(sl)
    tp = policy["tp"]; arm = policy["arm"]; give = policy["give"]
    start_ts = ticks[start_idx][0]
    end_ts = start_ts + timedelta(minutes=WINDOW_MIN)
    peak = 0.0
    for i in range(start_idx, len(ticks)):
        ts, bid, ask = ticks[i]
        prof = (bid - entry) if side == "BUY" else (entry - ask)  # points, close-side
        if ts > end_ts:
            return ("window", prof - SLIP_PTS)
        peak = max(peak, prof)
        # order: hard SL first (conservative), then TP ceiling, then trail
        if prof <= -sl_dist:
            return ("sl", -sl_dist - SLIP_PTS)
        if tp is not None and prof >= tp:
            return ("tp", tp - SLIP_PTS)
        if arm is not None and peak >= arm and (peak - prof) >= give:
            return ("trail", (peak - give) - SLIP_PTS)
    # ran out of ticks
    ts, bid, ask = ticks[-1]
    prof = (bid - entry) if side == "BUY" else (entry - ask)
    return ("eod", prof - SLIP_PTS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=40)
    args = ap.parse_args()

    tick_csvs = sorted(TICK_DIR.glob("shano_ticks_2026-*.csv"))[-args.days:]
    if not tick_csvs:
        print("no tick csvs"); return
    print(f"Loading {len(tick_csvs)} tick CSVs ({tick_csvs[0].stem[-10:]} … {tick_csvs[-1].stem[-10:]})")

    bars = build_m1(tick_csvs)
    print(f"Built {len(bars)} M1 bars")
    fires = detect(bars)
    print(f"Detected {len(fires)} canonical UHV entries (ENTRY FROZEN)\n")

    ticks_by_date = load_ticks_by_date()

    # results[policy] = list of pnl_pts
    results = {name: [] for name in POLICIES}
    fire_days = set()
    for s in fires:
        open_dt = datetime.strptime(s.open_t, "%Y-%m-%d %H:%M")
        date_str = open_dt.strftime("%Y-%m-%d")
        ticks = ticks_by_date.get(date_str)
        if not ticks: continue
        # entry = close of breakout bar ≈ bar minute + 60s
        entry_ts = open_dt + timedelta(seconds=60)
        idx = find_idx(ticks, entry_ts)
        if idx is None: continue
        fire_days.add(date_str)
        uhv_sl_dist = abs(s.entry - s.sl)
        for name, pol in POLICIES.items():
            reason, pnl = simulate_exit(ticks, idx, s.side, s.entry, pol, uhv_sl_dist)
            results[name].append(pnl)

    # report
    dpp = LOT * DOLLAR_PER_PT_PER_LOT   # $ per point at current lot
    print(f"Entries simulated: {len(results['CURRENT_live'])} across {len(fire_days)} days  (lot={LOT}, ${dpp:.0f}/pt)\n")
    hdr = f"{'Policy':<18} {'N':>4} {'WR%':>6} {'AvgW':>7} {'AvgL':>7} {'R:R':>5} {'MaxL':>7} {'Net pts':>9} {'Net $':>10}"
    print(hdr); print("-" * len(hdr))
    summary = {}
    for name, pnls in results.items():
        if not pnls: continue
        wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p <= 0]
        wr = 100.0 * len(wins) / len(pnls)
        avg_w = sum(wins)/len(wins) if wins else 0
        avg_l = sum(losses)/len(losses) if losses else 0
        rr = (avg_w/abs(avg_l)) if avg_l else 0
        maxl = min(pnls)
        net = sum(pnls)
        summary[name] = {"n": len(pnls), "wr": round(wr,1), "avg_w": round(avg_w,3),
                         "avg_l": round(avg_l,3), "rr": round(rr,2), "max_loss": round(maxl,2),
                         "net_pts": round(net,2), "net_usd": round(net*dpp,2)}
        print(f"{name:<18} {len(pnls):>4} {wr:>5.1f}% {avg_w:>+7.2f} {avg_l:>+7.2f} {rr:>5.2f} "
              f"{maxl:>+7.2f} {net:>+9.2f} {net*dpp:>+10.2f}")

    # winner
    best = max(summary.items(), key=lambda kv: kv[1]["net_usd"])
    cur = summary.get("CURRENT_live", {})
    print(f"\nCURRENT_live net: ${cur.get('net_usd',0):+.2f}")
    print(f"BEST policy:      {best[0]}  net ${best[1]['net_usd']:+.2f}  "
          f"(WR {best[1]['wr']}%, R:R {best[1]['rr']}, maxL {best[1]['max_loss']}pt)")

    p = OUT_DIR / "exit_validation.json"
    p.write_text(json.dumps({"days": args.days, "entries": len(results['CURRENT_live']),
                             "fire_days": len(fire_days), "lot": LOT, "policies": POLICIES,
                             "summary": summary}, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved → {p}")


if __name__ == "__main__":
    main()
