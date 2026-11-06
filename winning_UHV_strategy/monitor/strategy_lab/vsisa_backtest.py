"""
VSISA Backtest — Sir Sajid Ahmad's Volume Spread Imbalance Shift Analysis
                 applied to XAUUSD (no CSM, per Zee's clarification 2026-05-07)

Pattern (SELL setup; BUY = mirror):
  effort bar:    bullish or bearish candle with BIG volume vs last-3-day big volumes
  reaction bar:  bearish full-body engulf of effort body, with LOW volume (< 60% of effort)
                 (closes below effort.open ; opens at-or-above effort.close)

Exit:
  SL = engulf bar's high + 0.10pt buffer (sells); low - 0.10pt for buys
  TP = 2R (R = entry-to-SL distance)
  No partial exits in this baseline; track 1R and 4R touches for analytics

Filter variants:
  V1 — pure VSISA (no extra filter)
  V2 — VSISA + H1 trend alignment (sell only if H1 down, buy only if H1 up)
  V3 — VSISA + Fib zone (entry must be in 50-61.8% of last H1 swing)
  V4 — VSISA + H1 trend + Fib zone (most selective)

Data: aggregated from monitor/_vsa_audio/.../shano_ticks_YYYY-MM-DD.csv
      ticks (1Hz bid/ask) → M5 OHLCV (vol = tick count) → also M15, H1
"""
import os
import csv
import sys
import io
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

TICKS_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
REPORT_PATH = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\VSISA_BACKTEST_REPORT.md")

# === Trade params ===
LOTS = 0.30
DOLLAR_PER_PT_PER_LOT = 100.0  # XAUUSD: 1 lot=100oz; $1 move = $100/lot
DOLLAR_PER_PT = LOTS * DOLLAR_PER_PT_PER_LOT  # $30/pt at 0.30 lots
SL_BUFFER_PT = 0.10
TP_R = 2.0       # take-profit at 2R
SLIP_COST = 1.0  # round-trip slip+spread cost in $

# === VSISA params ===
# Speaker says "low volume on reaction" = below the session AVERAGE (the VSA "pink" zone),
# not necessarily lower than the effort bar. Effort just needs to be BIG.
LOW_VOL_THRESHOLD_PCT = 0.50    # reaction.vol < median of session (rolling)
BIG_VOL_PERCENTILE = 0.65       # effort.vol must be >= 65th percentile (loosened from 75 — was firing too rarely)
SESSION_LOOKBACK_DAYS = 3
MIN_BARS_FOR_DETECTION = 30
ENGULF_BODY_COVERAGE = 0.70     # reaction body must cover >=70% of effort body (loosened from 80)

# === Multi-TF params ===
H1_TREND_EMA = 20
FIB_LOW = 0.50
FIB_HIGH = 0.618
FIB_SWING_BARS = 20  # H1 swing detection lookback


# ─── Tick → Bar aggregation ────────────────────────────────────────────

def load_ticks(date_str):
    """Returns list of (datetime, mid_price)."""
    f = TICKS_DIR / f"shano_ticks_{date_str}.csv"
    if not f.exists():
        return []
    out = []
    with f.open(encoding="utf-8", errors="ignore") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            try:
                ts = datetime.strptime(row[0], "%Y.%m.%d %H:%M:%S")
                mid = (float(row[2]) + float(row[3])) / 2.0
                out.append((ts, mid))
            except (ValueError, IndexError):
                continue
    return out


def aggregate(ticks, minutes):
    """Aggregate ticks to OHLCV bars of `minutes` length. vol = tick count."""
    bars = {}
    for ts, mid in ticks:
        bucket = ts.replace(second=0, microsecond=0)
        bucket = bucket.replace(minute=(bucket.minute // minutes) * minutes)
        b = bars.setdefault(bucket, {"o": mid, "h": mid, "l": mid, "c": mid, "v": 0, "ts": bucket})
        b["h"] = max(b["h"], mid)
        b["l"] = min(b["l"], mid)
        b["c"] = mid
        b["v"] += 1
    return [bars[k] for k in sorted(bars)]


# ─── Indicators ────────────────────────────────────────────────────────

def ema(values, period):
    out = [None] * len(values)
    if not values:
        return out
    k = 2.0 / (period + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i-1] * (1 - k)
    return out


def session_volume_thresholds(m5_bars, idx):
    """Returns (big_vol_threshold, low_vol_threshold) from rolling session lookback."""
    if idx < MIN_BARS_FOR_DETECTION:
        return float("inf"), float("inf")
    cur_date = m5_bars[idx]["ts"].date()
    cutoff = cur_date - timedelta(days=SESSION_LOOKBACK_DAYS)
    vols = [b["v"] for b in m5_bars[:idx] if cutoff <= b["ts"].date() < cur_date]
    if len(vols) < 50:
        vols = [b["v"] for b in m5_bars[max(0, idx-100):idx]]
    if not vols:
        return float("inf"), float("inf")
    vols.sort()
    big = vols[int(len(vols) * BIG_VOL_PERCENTILE)]
    low = vols[int(len(vols) * LOW_VOL_THRESHOLD_PCT)]
    return big, low


# ─── Pattern detection ────────────────────────────────────────────────

def detect_engulf_setup(m5_bars, idx):
    """Returns ('sell', effort_idx) or ('buy', ...) or None."""
    if idx < 1:
        return None
    effort = m5_bars[idx - 1]
    reaction = m5_bars[idx]

    big_vol, low_vol = session_volume_thresholds(m5_bars, idx)
    if effort["v"] < big_vol:
        return None
    if reaction["v"] >= low_vol:
        return None  # reaction must be below session median

    eff_o, eff_c = effort["o"], effort["c"]
    rxn_o, rxn_c = reaction["o"], reaction["c"]
    eff_dir = "up" if eff_c > eff_o else "dn"
    rxn_dir = "up" if rxn_c > rxn_o else "dn"
    if rxn_dir == eff_dir:
        return None

    eff_body_lo, eff_body_hi = min(eff_o, eff_c), max(eff_o, eff_c)
    rxn_body_lo, rxn_body_hi = min(rxn_o, rxn_c), max(rxn_o, rxn_c)
    eff_body_size = eff_body_hi - eff_body_lo
    if eff_body_size <= 0:
        return None

    # Body coverage: reaction body must cover >= ENGULF_BODY_COVERAGE of effort body
    overlap_lo = max(eff_body_lo, rxn_body_lo)
    overlap_hi = min(eff_body_hi, rxn_body_hi)
    overlap = max(0.0, overlap_hi - overlap_lo)
    if overlap / eff_body_size < ENGULF_BODY_COVERAGE:
        return None
    # Reaction body must extend beyond effort in direction of reaction
    if rxn_dir == "dn" and rxn_body_lo > eff_body_lo:
        return None
    if rxn_dir == "up" and rxn_body_hi < eff_body_hi:
        return None

    return ("sell", idx - 1) if rxn_dir == "dn" else ("buy", idx - 1)


# ─── Filters ──────────────────────────────────────────────────────────

def h1_trend_at(h1_bars, ts, ema_vals):
    """Returns 'up'/'dn'/'neutral' based on H1 EMA direction at `ts`."""
    # find the H1 bar that contains ts
    idx = -1
    for i, b in enumerate(h1_bars):
        if b["ts"] <= ts:
            idx = i
        else:
            break
    if idx < H1_TREND_EMA + 2:
        return "neutral"
    # trend: EMA slope over last 3 bars
    e_now = ema_vals[idx]
    e_prev = ema_vals[max(0, idx - 3)]
    if e_now is None or e_prev is None:
        return "neutral"
    slope = e_now - e_prev
    # also: price vs EMA
    px = h1_bars[idx]["c"]
    if px > e_now and slope > 0:
        return "up"
    if px < e_now and slope < 0:
        return "dn"
    return "neutral"


def in_fib_zone(h1_bars, ts, entry_px, direction):
    """Check if entry_px is in the 50-61.8% retracement of the most recent H1 swing."""
    idx = -1
    for i, b in enumerate(h1_bars):
        if b["ts"] <= ts:
            idx = i
        else:
            break
    if idx < FIB_SWING_BARS:
        return False
    window = h1_bars[max(0, idx - FIB_SWING_BARS):idx + 1]
    swing_hi = max(b["h"] for b in window)
    swing_lo = min(b["l"] for b in window)
    if swing_hi <= swing_lo:
        return False
    # For SELL: we want entry in 50-61.8% retracement of a DOWN swing's bounce up
    # i.e., price has moved down then bounced; entry is at the 50-61.8% bounce level
    if direction == "sell":
        retr = (entry_px - swing_lo) / (swing_hi - swing_lo)
    else:  # buy: 50-61.8% pullback of an up swing
        retr = (swing_hi - entry_px) / (swing_hi - swing_lo)
    return FIB_LOW <= retr <= FIB_HIGH


# ─── Trade simulation ────────────────────────────────────────────────

def simulate_trade(m5_bars, signal_idx, direction, entry_price, sl_price, max_bars=60):
    """Simulate a single VSISA trade. Returns dict with reason, pnl, age, R."""
    risk_pt = abs(entry_price - sl_price)
    if risk_pt < 0.05:
        return None
    tp_price = entry_price - TP_R * risk_pt if direction == "sell" else entry_price + TP_R * risk_pt
    peak_pt = 0.0

    for offset in range(1, max_bars + 1):
        i = signal_idx + offset
        if i >= len(m5_bars):
            break
        bar = m5_bars[i]
        # check stop loss first (worst-case fill)
        if direction == "sell" and bar["h"] >= sl_price:
            move_pt = entry_price - sl_price
            return {"reason": "sl", "pnl": move_pt * DOLLAR_PER_PT - SLIP_COST, "age_bars": offset, "R": -1.0}
        if direction == "buy" and bar["l"] <= sl_price:
            move_pt = sl_price - entry_price
            return {"reason": "sl", "pnl": move_pt * DOLLAR_PER_PT - SLIP_COST, "age_bars": offset, "R": -1.0}
        # check take profit
        if direction == "sell" and bar["l"] <= tp_price:
            move_pt = entry_price - tp_price
            return {"reason": "tp", "pnl": move_pt * DOLLAR_PER_PT - SLIP_COST, "age_bars": offset, "R": TP_R}
        if direction == "buy" and bar["h"] >= tp_price:
            move_pt = tp_price - entry_price
            return {"reason": "tp", "pnl": move_pt * DOLLAR_PER_PT - SLIP_COST, "age_bars": offset, "R": TP_R}
        # track favorable peak (for analytics)
        cur_pt = (entry_price - bar["c"]) if direction == "sell" else (bar["c"] - entry_price)
        peak_pt = max(peak_pt, cur_pt)

    # ran out of bars — exit at last close
    last = m5_bars[min(signal_idx + max_bars, len(m5_bars) - 1)]
    move_pt = (entry_price - last["c"]) if direction == "sell" else (last["c"] - entry_price)
    R = move_pt / risk_pt
    return {"reason": "time", "pnl": move_pt * DOLLAR_PER_PT - SLIP_COST, "age_bars": max_bars, "R": R}


# ─── Backtest run ────────────────────────────────────────────────────

def run_backtest(m5_bars, h1_bars, variant):
    """variant: 'V1', 'V2', 'V3', 'V4'."""
    h1_closes = [b["c"] for b in h1_bars]
    h1_ema = ema(h1_closes, H1_TREND_EMA)

    trades = []
    for idx in range(MIN_BARS_FOR_DETECTION, len(m5_bars) - 1):
        sig = detect_engulf_setup(m5_bars, idx)
        if not sig:
            continue
        direction, eff_idx = sig
        reaction = m5_bars[idx]
        entry = reaction["c"]
        sl = (reaction["h"] + SL_BUFFER_PT) if direction == "sell" else (reaction["l"] - SL_BUFFER_PT)

        # Apply variant filters
        if variant in ("V2", "V4"):
            t = h1_trend_at(h1_bars, reaction["ts"], h1_ema)
            if direction == "sell" and t != "dn":
                continue
            if direction == "buy" and t != "up":
                continue

        if variant in ("V3", "V4"):
            if not in_fib_zone(h1_bars, reaction["ts"], entry, direction):
                continue

        result = simulate_trade(m5_bars, idx, direction, entry, sl)
        if result is None:
            continue
        result.update({
            "ts": reaction["ts"].strftime("%Y-%m-%d %H:%M"),
            "dir": direction,
            "entry": entry,
            "sl": sl,
            "variant": variant,
        })
        trades.append(result)
    return trades


def summarize(trades, label):
    if not trades:
        return {"label": label, "n": 0, "wr": 0, "net": 0, "avg_R": 0,
                "wins": 0, "losses": 0, "tp": 0, "sl": 0, "time": 0}
    n = len(trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    net = sum(t["pnl"] for t in trades)
    avg_R = sum(t["R"] for t in trades) / n
    wr = 100.0 * len(wins) / n
    by_reason = {r: sum(1 for t in trades if t["reason"] == r) for r in ("tp", "sl", "time")}
    return {
        "label": label, "n": n, "wins": len(wins), "losses": len(losses),
        "wr": round(wr, 1), "net": round(net, 2), "avg_R": round(avg_R, 2),
        "tp": by_reason.get("tp", 0), "sl": by_reason.get("sl", 0), "time": by_reason.get("time", 0),
    }


def main():
    dates = ["2026-04-29", "2026-04-30", "2026-05-01", "2026-05-04",
             "2026-05-05", "2026-05-06", "2026-05-07"]
    all_ticks = []
    for d in dates:
        ticks = load_ticks(d)
        if ticks:
            print(f"loaded {len(ticks):,} ticks from {d}")
            all_ticks.extend(ticks)
    print(f"\nTotal: {len(all_ticks):,} ticks")

    print("\nAggregating bars...")
    m5_bars = aggregate(all_ticks, 5)
    h1_bars = aggregate(all_ticks, 60)
    print(f"  M5: {len(m5_bars)} bars")
    print(f"  H1: {len(h1_bars)} bars")

    print("\n=== Backtest results ===")
    print(f"{'Variant':<35} {'N':>4} {'Wins':>5} {'Losses':>7} {'WR%':>6} {'AvgR':>6} {'TP':>4} {'SL':>4} {'Time':>5} {'Net P&L':>10}")
    print("-" * 100)
    summaries = []
    for v, label in [("V1", "Pure VSISA (no extra filter)"),
                     ("V2", "VSISA + H1 trend"),
                     ("V3", "VSISA + Fib zone"),
                     ("V4", "VSISA + H1 trend + Fib zone")]:
        trades = run_backtest(m5_bars, h1_bars, v)
        s = summarize(trades, label)
        summaries.append((s, trades))
        print(f"{label:<35} {s['n']:>4} {s['wins']:>5} {s['losses']:>7} "
              f"{s['wr']:>5.1f}% {s['avg_R']:>5.2f} {s['tp']:>4} {s['sl']:>4} {s['time']:>5} "
              f"${s['net']:>+9.2f}")

    # Detailed best variant (most trades)
    best = max(summaries, key=lambda x: x[0]["n"])
    print(f"\n=== Sample trades from best-N variant: {best[0]['label']} ===")
    for t in best[1][:12]:
        print(f"  {t['ts']}  {t['dir']:>4} entry={t['entry']:.2f} sl={t['sl']:.2f} -> "
              f"{t['reason']:<5} pnl=${t['pnl']:>+8.2f} R={t['R']:>+5.2f} ({t['age_bars']} bars)")

    # Write report
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        f.write(f"# VSISA Backtest — XAUUSD\n\nRun: {datetime.now().isoformat(timespec='minutes')}\n\n")
        f.write(f"## Setup\n\n")
        f.write(f"- Instrument: XAUUSD\n")
        f.write(f"- Period: {dates[0]} to {dates[-1]} (~{len(dates)} days, weekend gap)\n")
        f.write(f"- Lots: {LOTS} | $/pt: {DOLLAR_PER_PT} | TP: {TP_R}R | SL buffer: {SL_BUFFER_PT}pt | slip cost: ${SLIP_COST}\n")
        f.write(f"- Big-vol threshold: {int(BIG_VOL_PERCENTILE*100)}th pct of last {SESSION_LOOKBACK_DAYS} sessions\n")
        f.write(f"- Reaction low-vol: below {int(LOW_VOL_THRESHOLD_PCT*100)}th percentile of session volumes\n")
        f.write(f"- Engulf body coverage: >= {int(ENGULF_BODY_COVERAGE*100)}% of effort body\n")
        f.write(f"- H1 trend EMA: {H1_TREND_EMA}\n")
        f.write(f"- Fib zone: {FIB_LOW}-{FIB_HIGH} of last {FIB_SWING_BARS}-H1-bar swing\n\n")
        f.write(f"## Results\n\n")
        f.write(f"| Variant | N | W | L | WR% | AvgR | TP | SL | Time | Net P&L |\n")
        f.write(f"|---|---|---|---|---|---|---|---|---|---|\n")
        for s, _ in summaries:
            f.write(f"| {s['label']} | {s['n']} | {s['wins']} | {s['losses']} | "
                    f"{s['wr']}% | {s['avg_R']} | {s['tp']} | {s['sl']} | {s['time']} | "
                    f"${s['net']:+.2f} |\n")
        f.write("\n## Sample trades — best-N variant\n\n")
        f.write(f"### {best[0]['label']}\n\n")
        for t in best[1][:30]:
            f.write(f"- {t['ts']} **{t['dir']}** entry={t['entry']:.2f} sl={t['sl']:.2f} "
                    f"→ {t['reason']} ${t['pnl']:+.2f} R={t['R']:+.2f}\n")

    print(f"\nReport written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
