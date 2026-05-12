"""
VSISA backtest on 60 days of XAUUSD (via GC=F gold futures with real volume).

Same pattern logic as vsisa_backtest.py but reads pre-aggregated M5 data
from yfinance CSV instead of aggregating from ticks. Since this dataset
has 13K+ bars (vs 1.5K from ticks), we can sweep parameters and pick the
configuration with the best win-rate × profit factor.
"""
import os, sys, io, csv, json, math
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DATA_PATH = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_60d_m5.csv")
REPORT_PATH = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\VSISA_BACKTEST_REPORT.md")
TUNE_LOG_PATH = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\VSISA_TUNE_LOG.md")
LIVE_CONFIG_PATH = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\vsisa_live_config.json")

LOTS = 0.30
DOLLAR_PER_PT = LOTS * 100.0
SL_BUFFER_PT = 0.10
SLIP_COST = 1.0


def load_m5(path):
    """Load M5 OHLCV from yfinance CSV. Format: Datetime, Adj Close, Close, High, Low, Open, Volume."""
    bars = []
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        # Skip first 3 header rows from yfinance multi-index
        next(reader); next(reader); next(reader)
        for row in reader:
            if not row or not row[0]: continue
            try:
                ts = datetime.fromisoformat(row[0].split("+")[0])
                # Adj Close, Close, High, Low, Open, Volume
                close = float(row[2])
                high = float(row[3])
                low = float(row[4])
                open_ = float(row[5])
                vol = int(float(row[6]))
                bars.append({"ts": ts, "o": open_, "h": high, "l": low, "c": close, "v": vol})
            except (ValueError, IndexError):
                continue
    return bars


def aggregate_to_h1(m5_bars):
    """Roll up M5 → H1."""
    by_hr = {}
    for b in m5_bars:
        h_ts = b["ts"].replace(minute=0, second=0, microsecond=0)
        if h_ts not in by_hr:
            by_hr[h_ts] = {"ts": h_ts, "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b["v"]}
        else:
            agg = by_hr[h_ts]
            agg["h"] = max(agg["h"], b["h"])
            agg["l"] = min(agg["l"], b["l"])
            agg["c"] = b["c"]
            agg["v"] += b["v"]
    return [by_hr[k] for k in sorted(by_hr)]


def ema(values, period):
    out = [None] * len(values)
    if not values: return out
    k = 2.0 / (period + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i-1] * (1 - k)
    return out


def session_volume_thresholds(m5_bars, idx, lookback_bars, big_pct, low_pct):
    if idx < lookback_bars: return float("inf"), float("inf")
    vols = sorted(b["v"] for b in m5_bars[max(0, idx-lookback_bars):idx] if b["v"] > 0)
    if not vols: return float("inf"), float("inf")
    return vols[int(len(vols)*big_pct)], vols[int(len(vols)*low_pct)]


def detect_setup(m5_bars, idx, big_pct, low_pct, body_coverage, lookback_bars):
    if idx < 1: return None
    e, r = m5_bars[idx-1], m5_bars[idx]
    if e["v"] == 0 or r["v"] == 0: return None  # skip zero-volume bars (overnight gaps)
    big_v, low_v = session_volume_thresholds(m5_bars, idx, lookback_bars, big_pct, low_pct)
    if e["v"] < big_v: return None
    if r["v"] >= low_v: return None
    e_dir = "up" if e["c"] > e["o"] else "dn"
    r_dir = "up" if r["c"] > r["o"] else "dn"
    if e_dir == r_dir: return None
    e_lo, e_hi = min(e["o"], e["c"]), max(e["o"], e["c"])
    r_lo, r_hi = min(r["o"], r["c"]), max(r["o"], r["c"])
    e_size = e_hi - e_lo
    if e_size <= 0: return None
    overlap = max(0.0, min(e_hi, r_hi) - max(e_lo, r_lo))
    if overlap / e_size < body_coverage: return None
    if r_dir == "dn" and r_lo > e_lo: return None
    if r_dir == "up" and r_hi < e_hi: return None
    return ("sell", idx-1) if r_dir == "dn" else ("buy", idx-1)


def h1_trend_at(h1_bars, ts, ema_vals, lookback=3):
    idx = -1
    for i, b in enumerate(h1_bars):
        if b["ts"] <= ts: idx = i
        else: break
    if idx < lookback + 1 or ema_vals[idx] is None or ema_vals[max(0, idx-lookback)] is None:
        return "neutral"
    slope = ema_vals[idx] - ema_vals[max(0, idx-lookback)]
    px = h1_bars[idx]["c"]
    if px > ema_vals[idx] and slope > 0: return "up"
    if px < ema_vals[idx] and slope < 0: return "dn"
    return "neutral"


def in_fib_zone(h1_bars, ts, entry_px, direction, swing_bars, fib_lo, fib_hi):
    idx = -1
    for i, b in enumerate(h1_bars):
        if b["ts"] <= ts: idx = i
        else: break
    if idx < swing_bars: return False
    window = h1_bars[max(0, idx-swing_bars):idx+1]
    swing_hi = max(b["h"] for b in window)
    swing_lo = min(b["l"] for b in window)
    if swing_hi <= swing_lo: return False
    if direction == "sell":
        retr = (entry_px - swing_lo) / (swing_hi - swing_lo)
    else:
        retr = (swing_hi - entry_px) / (swing_hi - swing_lo)
    return fib_lo <= retr <= fib_hi


def simulate(m5_bars, sig_idx, direction, entry, sl, tp_r, max_bars=60):
    risk = abs(entry - sl)
    if risk < 0.05: return None
    tp = entry - tp_r * risk if direction == "sell" else entry + tp_r * risk
    for offset in range(1, max_bars+1):
        i = sig_idx + offset
        if i >= len(m5_bars): break
        b = m5_bars[i]
        if direction == "sell" and b["h"] >= sl:
            return {"reason": "sl", "pnl": (entry-sl)*DOLLAR_PER_PT - SLIP_COST, "R": -1.0, "age": offset}
        if direction == "buy" and b["l"] <= sl:
            return {"reason": "sl", "pnl": (sl-entry)*DOLLAR_PER_PT - SLIP_COST, "R": -1.0, "age": offset}
        if direction == "sell" and b["l"] <= tp:
            return {"reason": "tp", "pnl": (entry-tp)*DOLLAR_PER_PT - SLIP_COST, "R": tp_r, "age": offset}
        if direction == "buy" and b["h"] >= tp:
            return {"reason": "tp", "pnl": (tp-entry)*DOLLAR_PER_PT - SLIP_COST, "R": tp_r, "age": offset}
    last = m5_bars[min(sig_idx + max_bars, len(m5_bars)-1)]
    move = (entry - last["c"]) if direction == "sell" else (last["c"] - entry)
    R = move / risk
    return {"reason": "time", "pnl": move*DOLLAR_PER_PT - SLIP_COST, "R": R, "age": max_bars}


def backtest(m5, h1, h1_ema, params):
    p = params
    trades = []
    for idx in range(p["lookback_bars"], len(m5)-1):
        sig = detect_setup(m5, idx, p["big_pct"], p["low_pct"], p["body_cov"], p["lookback_bars"])
        if not sig: continue
        direction, eff_idx = sig
        r = m5[idx]
        entry = r["c"]
        sl = (r["h"] + SL_BUFFER_PT) if direction == "sell" else (r["l"] - SL_BUFFER_PT)
        if p["use_h1"]:
            t = h1_trend_at(h1, r["ts"], h1_ema)
            if direction == "sell" and t != "dn": continue
            if direction == "buy" and t != "up": continue
        if p["use_fib"]:
            if not in_fib_zone(h1, r["ts"], entry, direction, p["fib_swing"], p["fib_lo"], p["fib_hi"]):
                continue
        out = simulate(m5, idx, direction, entry, sl, p["tp_r"])
        if out is None: continue
        out.update({"ts": r["ts"].strftime("%Y-%m-%d %H:%M"), "dir": direction,
                    "entry": entry, "sl": sl})
        trades.append(out)
    return trades


def stats(trades):
    if not trades: return {"n": 0, "wr": 0, "net": 0, "avg_R": 0, "pf": 0, "max_dd": 0}
    n = len(trades)
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [t["pnl"] for t in trades if t["pnl"] <= 0]
    wr = 100.0 * len(wins) / n
    net = sum(t["pnl"] for t in trades)
    avg_R = sum(t["R"] for t in trades) / n
    gross_w = sum(wins) if wins else 0
    gross_l = abs(sum(losses)) if losses else 0
    pf = gross_w / gross_l if gross_l > 0 else float("inf")
    # Equity curve drawdown
    equity = 0
    peak = 0
    max_dd = 0
    for t in trades:
        equity += t["pnl"]
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {"n": n, "wr": round(wr, 1), "net": round(net, 2), "avg_R": round(avg_R, 2),
            "pf": round(pf, 2) if pf != float("inf") else 999.0, "max_dd": round(max_dd, 2)}


def main():
    print(f"Loading {DATA_PATH}...")
    m5 = load_m5(DATA_PATH)
    print(f"M5 bars: {len(m5)}")
    if not m5:
        print("ERROR: no data loaded")
        return
    h1 = aggregate_to_h1(m5)
    print(f"H1 bars: {len(h1)}")
    h1_ema = ema([b["c"] for b in h1], 20)

    # Volume distribution sanity
    vols = sorted(b["v"] for b in m5 if b["v"] > 0)
    if vols:
        print(f"Vol distribution: 25%={vols[len(vols)//4]} 50%={vols[len(vols)//2]} 75%={vols[3*len(vols)//4]} 95%={vols[19*len(vols)//20]}")

    # === Phase 1: Default config ===
    default = {
        "big_pct": 0.65, "low_pct": 0.50, "body_cov": 0.70,
        "lookback_bars": 100, "tp_r": 2.0,
        "use_h1": False, "use_fib": False,
        "fib_swing": 20, "fib_lo": 0.50, "fib_hi": 0.618,
    }
    print("\n=== Default config ===")
    for v in [
        ("V1 Pure", {"use_h1": False, "use_fib": False}),
        ("V2 +H1", {"use_h1": True, "use_fib": False}),
        ("V3 +Fib", {"use_h1": False, "use_fib": True}),
        ("V4 +H1+Fib", {"use_h1": True, "use_fib": True}),
    ]:
        p = {**default, **v[1]}
        t = backtest(m5, h1, h1_ema, p)
        s = stats(t)
        print(f"  {v[0]:<14} n={s['n']:>4} wr={s['wr']:>5}% net=${s['net']:>+9.2f} pf={s['pf']:>5} avgR={s['avg_R']:>+5} maxDD=${s['max_dd']:>7.2f}")

    # === Phase 2: Parameter sweep — find best config for max WR with reasonable n ===
    print("\n=== Parameter sweep (looking for best WR with n>=20) ===")
    best = None
    sweep_results = []
    for big_pct in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        for low_pct in [0.30, 0.40, 0.50, 0.60]:
            for body_cov in [0.60, 0.70, 0.80, 0.90]:
                for tp_r in [1.5, 2.0, 2.5, 3.0]:
                    for use_h1 in [False, True]:
                        p = {**default, "big_pct": big_pct, "low_pct": low_pct,
                             "body_cov": body_cov, "tp_r": tp_r, "use_h1": use_h1}
                        t = backtest(m5, h1, h1_ema, p)
                        s = stats(t)
                        if s["n"] < 20: continue
                        # Score: weighted toward WR + PF
                        score = s["wr"] + 20 * (s["pf"] - 1.0) if s["pf"] != 999.0 else s["wr"]
                        sweep_results.append((score, p, s))
                        if best is None or score > best[0]:
                            best = (score, p, s)
    sweep_results.sort(key=lambda x: -x[0])
    print(f"\nTop 10 sweeps (sorted by score = WR + 20*(PF-1)):")
    print(f"{'big':>5} {'low':>5} {'body':>5} {'tpR':>5} {'h1':>4} | n  wr%   net      pf    avgR   maxDD")
    for score, p, s in sweep_results[:10]:
        print(f"{p['big_pct']:>5} {p['low_pct']:>5} {p['body_cov']:>5} {p['tp_r']:>5} {str(p['use_h1'])[:4]:>4} | "
              f"{s['n']:>3} {s['wr']:>5}% ${s['net']:>+8.2f} {s['pf']:>5} {s['avg_R']:>+5} ${s['max_dd']:>6.2f}")

    if best:
        score, bp, bs = best
        print(f"\n=== BEST CONFIG (score {score:.1f}) ===")
        for k, v in bp.items():
            print(f"  {k}: {v}")
        print(f"  Stats: n={bs['n']}, wr={bs['wr']}%, net=${bs['net']}, pf={bs['pf']}, avgR={bs['avg_R']}, maxDD=${bs['max_dd']}")

        # Save best config for live daemon
        with LIVE_CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump({**bp, "stats": bs, "tuned_at": datetime.now().isoformat(timespec="seconds")}, f, indent=2)
        print(f"\nSaved live config to {LIVE_CONFIG_PATH}")

    # Write report
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        f.write(f"# VSISA Backtest — XAUUSD 60d (GC=F)\n\n")
        f.write(f"Run: {datetime.now().isoformat(timespec='minutes')}\n\n")
        f.write(f"## Data\n\n- Source: yfinance GC=F (gold futures, M5)\n")
        f.write(f"- Bars: {len(m5)} M5 / {len(h1)} H1\n")
        if m5:
            f.write(f"- Range: {m5[0]['ts']} to {m5[-1]['ts']}\n\n")
        f.write(f"## Parameter Sweep — Top 10\n\n")
        f.write(f"| big | low | body | tpR | h1 | N | WR% | Net | PF | AvgR | MaxDD |\n")
        f.write(f"|---|---|---|---|---|---|---|---|---|---|---|\n")
        for score, p, s in sweep_results[:10]:
            f.write(f"| {p['big_pct']} | {p['low_pct']} | {p['body_cov']} | {p['tp_r']} | "
                    f"{p['use_h1']} | {s['n']} | {s['wr']} | ${s['net']:+.2f} | {s['pf']} | "
                    f"{s['avg_R']:+.2f} | ${s['max_dd']:.2f} |\n")
        if best:
            f.write(f"\n## Selected for live config\n\n")
            f.write(f"```json\n{json.dumps({**bp, 'stats': bs}, indent=2)}\n```\n")

    print(f"\nReport written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
