"""backtest_btc_setups.py — quick BTCUSD validation of S1 and S3 setups.

We have no BTC tick data, so this uses BAR-CLOSE replay on M1 bars:
  • Detect signal on M5 bar close
  • Open at next M1 bar's open (proxy for next tick)
  • Walk forward M1-by-M1: SL hit if bar.low ≤ SL, TP hit if bar.high ≥ TP
  • Less precise than tick replay, but tells us if the edge exists at all

BTC vs XAU specifics:
  • Price ~$78,000 (vs gold ~$4,500). Moves 100× larger in dollar terms.
  • Contract = 1.0 (1 BTC per lot, not 100 like XAU)
  • Typical M5 range $50-$500 (vs gold $0.50-$3)
  • TP/SL parameters need full re-tuning, not 1:1 transfer

Sweeps multiple TP_$ × SL_$ to find the BTC-equivalent edge.
"""
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

COMMON     = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
BTC_CSV    = COMMON / "btc_m1.csv"
CONTRACT   = 1.0       # BTC: 1 unit per lot (1 lot = 1 BTC)


def load_btc_m1():
    bars = []
    with open(BTC_CSV, encoding="ascii", errors="replace") as f:
        for r in csv.DictReader(f):
            try:
                tm = datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S")
            except Exception:
                continue
            bars.append({"time": tm, "open": float(r["open"]), "high": float(r["high"]),
                         "low": float(r["low"]), "close": float(r["close"]),
                         "vol": int(r["tick_volume"])})
    bars.sort(key=lambda b: b["time"])
    return bars


def aggregate_to_tf(m1, k):
    out = {}
    for b in m1:
        ts = b["time"]
        bucket_min = (ts.minute // k) * k
        bt = ts.replace(minute=bucket_min, second=0, microsecond=0)
        if bt not in out:
            out[bt] = {"time": bt, "open": b["open"], "high": b["high"],
                       "low": b["low"], "close": b["close"], "vol": b["vol"]}
        else:
            x = out[bt]
            x["high"] = max(x["high"], b["high"])
            x["low"]  = min(x["low"],  b["low"])
            x["close"] = b["close"]
            x["vol"] += b["vol"]
    return sorted(out.values(), key=lambda x: x["time"])


def aggregate_to_h1(m1):
    out = {}
    for b in m1:
        bt = b["time"].replace(minute=0, second=0, microsecond=0)
        if bt not in out:
            out[bt] = {"time": bt, "open": b["open"], "high": b["high"],
                       "low": b["low"], "close": b["close"], "vol": b["vol"]}
        else:
            x = out[bt]
            x["high"] = max(x["high"], b["high"])
            x["low"]  = min(x["low"],  b["low"])
            x["close"] = b["close"]
            x["vol"] += b["vol"]
    return sorted(out.values(), key=lambda x: x["time"])


def find_h1_fvgs(h1):
    fvgs = []
    for i in range(2, len(h1)):
        gl, gh = h1[i-2]["high"], h1[i]["low"]
        if gh <= gl: continue
        filled_at = None
        for j in range(i+1, len(h1)):
            if h1[j]["low"] < gl:
                filled_at = h1[j]["time"]; break
        fvgs.append({"t0": h1[i]["time"], "gap_low": gl, "gap_high": gh,
                     "filled_at": filled_at, "side": "bullish"})
    return fvgs


def fvg_tapped_at(fvgs, side, bar):
    for f in fvgs:
        if f["side"] != side: continue
        if f["t0"] >= bar["time"]: continue
        if f["filled_at"] is not None and f["filled_at"] <= bar["time"]: continue
        if bar["low"] <= f["gap_high"] and bar["high"] >= f["gap_low"]:
            return True
    return False


def is_uptrend(m5, idx, lookback, threshold):
    if idx < lookback: return False
    return m5[idx]["close"] - m5[idx-lookback]["close"] > threshold


def find_retracement_reds(m5, idx, max_lookback):
    reds = []
    for j in range(idx-1, max(idx - max_lookback - 1, -1), -1):
        b = m5[j]
        if b["close"] >= b["open"]:
            if reds and b["high"] > m5[reds[-1]]["high"]: break
        else:
            reds.append(j)
    return reds


# ─── S1 & S3 detectors (BTC-tuned thresholds) ───
def detect_s1_buy(m5, idx, h1_fvgs, sl_buffer_pts, trend_lookback=24, trend_threshold=50.0):
    """S1 UHV BO BUY for BTC. trend_threshold is in $ (BTC moves are 25-100× XAU)."""
    bo = m5[idx]
    if bo["close"] <= bo["open"]: return None
    if not is_uptrend(m5, idx, trend_lookback, trend_threshold): return None
    reds = find_retracement_reds(m5, idx, max_lookback=15)
    if not reds: return None
    uhv_idx = max(reds, key=lambda j: m5[j]["vol"])
    uhv = m5[uhv_idx]
    if bo["close"] <= uhv["high"]: return None
    if bo["open"]  >  uhv["high"]: return None
    swept = any(m5[j]["low"] < uhv["low"] for j in range(uhv_idx+1, idx+1))
    if not swept: return None
    tapped = any(fvg_tapped_at(h1_fvgs, "bullish", m5[j]) for j in reds)
    if not tapped: return None
    entry = bo["close"]
    sl    = uhv["low"] - sl_buffer_pts
    return entry, sl, {"setup": "S1_buy", "ref_t": uhv["time"]}


def detect_s3_buy(m5, idx, h1_fvgs, sl_buffer_pts, trend_lookback=24, trend_threshold=50.0):
    bo = m5[idx]
    if bo["close"] <= bo["open"]: return None
    if not is_uptrend(m5, idx, trend_lookback, trend_threshold): return None
    reds = find_retracement_reds(m5, idx, max_lookback=15)
    if not reds: return None
    for red_idx in reds:
        red = m5[red_idx]
        if bo["low"] >= red["low"]: continue
        if bo["close"] <= red["low"]: continue
        if bo["vol"] <= red["vol"]: continue
        tapped = any(fvg_tapped_at(h1_fvgs, "bullish", m5[j]) for j in reds)
        if not tapped: continue
        entry = bo["close"]
        sl    = bo["low"] - sl_buffer_pts
        return entry, sl, {"setup": "S3_buy", "ref_t": red["time"]}
    return None


# ─── Bar-replay (M1 forward walk) ───
def replay_with_bars(m1_bars, signals, tp_price_pts, lots):
    """TP is now in PRICE POINTS (USD) above/below entry — not dollar P&L.
    For each signal: open at next M1 bar's open, walk forward, exit on SL/TP/EOD."""
    ppp = lots * CONTRACT
    done = []
    for s in sorted(signals, key=lambda x: x["fire_time"]):
        entry_idx = None
        for i, b in enumerate(m1_bars):
            if b["time"] >= s["fire_time"]:
                entry_idx = i; break
        if entry_idx is None: continue
        if entry_idx + 1 >= len(m1_bars): continue
        entry_bar = m1_bars[entry_idx]
        e  = entry_bar["open"]
        sl = s["sl"]
        tp = e + tp_price_pts if s["side"] > 0 else e - tp_price_pts
        why = None
        pnl = 0
        for j in range(entry_idx + 1, len(m1_bars)):
            b = m1_bars[j]
            if s["side"] > 0:
                if b["low"]  <= sl: pnl = (sl - e) * ppp; why = "sl"; break
                if b["high"] >= tp: pnl = (tp - e) * ppp; why = "tp"; break
            else:
                if b["high"] >= sl: pnl = (e - sl) * ppp; why = "sl"; break
                if b["low"]  <= tp: pnl = (e - tp) * ppp; why = "tp"; break
        if why is None:
            last = m1_bars[-1]
            pnl = (last["close"] - e) * ppp if s["side"] > 0 else (e - last["close"]) * ppp
            why = "eod"
        done.append({"setup": s["setup"], "side": s["side"], "e": e, "sl": sl, "tp": tp,
                     "pnl": pnl, "why": why, "fire_time": s["fire_time"]})
    return done


def detect_signals(m5, h1_fvgs, detector_fn, sl_buffer_pts, trend_threshold):
    sigs = []
    fired = set()
    for idx in range(30, len(m5)):
        r = detector_fn(m5, idx, h1_fvgs, sl_buffer_pts=sl_buffer_pts,
                        trend_threshold=trend_threshold)
        if r is None: continue
        entry, sl, ref = r
        if ref["ref_t"] in fired: continue
        fired.add(ref["ref_t"])
        sigs.append({"fire_time": m5[idx]["time"] + timedelta(minutes=5),
                     "side": +1, "entry": entry, "sl": sl, "setup": ref["setup"]})
    return sigs


def summarize(label, trades, lots, days, multiplier):
    n = len(trades)
    if n == 0:
        print(f"  {label:<35}   no trades")
        return None
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [t["pnl"] for t in trades if t["pnl"] < 0]
    n_w, n_l = len(wins), len(losses)
    pwin = n_w/(n_w+n_l) if (n_w+n_l) else 0
    w_avg = sum(wins)/n_w if n_w else 0
    l_avg = -sum(losses)/n_l if n_l else 0
    total = sum(t["pnl"] for t in trades)
    ev = pwin*w_avg - (1-pwin)*l_avg
    print(f"  {label:<35}   n={n:>3}  pwin={pwin:.3f}  Wavg=${w_avg:>7.1f}  Lavg=${l_avg:>7.1f}  EV=${ev:>+8.1f}  TOTAL=${total:>+10.1f}  @lots×{multiplier}=${total*multiplier:>+10.1f}")
    return total


def main():
    print("Loading BTC M1 bars...")
    m1 = load_btc_m1()
    days = (m1[-1]["time"] - m1[0]["time"]).total_seconds() / 86400
    print(f"  {len(m1)} M1 bars  span={days:.1f} days  price range ${min(b['low'] for b in m1):.0f}–${max(b['high'] for b in m1):.0f}")

    m5 = aggregate_to_tf(m1, 5)
    h1 = aggregate_to_h1(m1)
    h1_fvgs = find_h1_fvgs(h1)
    print(f"  {len(m5)} M5 bars, {len(h1)} H1 bars, {len(h1_fvgs)} bullish H1 FVGs\n")

    LOTS = 0.01
    MULTIPLIER_FOR_REPORT = 40   # report at 0.40 BTC equivalent for $/day comparison

    # SL buffer = how far below UHV/wicking-low (PRICE points = USD on BTC)
    sl_buffers = [10.0, 25.0, 50.0, 100.0]
    # TP = PRICE points above entry (USD on BTC). BTC typical 5-min range $50-$500.
    tp_price_pts_values = [50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0]
    trend_threshold = 100.0

    print(f"Config: lots={LOTS} BTC, contract=1, trend_threshold=${trend_threshold}")
    print(f"Showing P&L at lots={LOTS} AND projected at lots*{MULTIPLIER_FOR_REPORT}=({LOTS*MULTIPLIER_FOR_REPORT} BTC)\n")

    for setup_name, detector_fn in [("S1_buy", detect_s1_buy), ("S3_buy", detect_s3_buy)]:
        print(f"=== {setup_name} on BTCUSD ===")
        best = None
        for sl_buf in sl_buffers:
            sigs = detect_signals(m5, h1_fvgs, detector_fn, sl_buf, trend_threshold)
            if not sigs:
                print(f"  SL=${sl_buf:>5.0f}  no signals at all")
                continue
            for tp_pts in tp_price_pts_values:
                trades = replay_with_bars(m1, sigs, tp_pts, LOTS)
                total = summarize(f"SLbuf=${sl_buf:>4.0f}  TP=${tp_pts:>5.0f}pts",
                                   trades, LOTS, days, MULTIPLIER_FOR_REPORT)
                if total is not None and (best is None or total > best[0]):
                    best = (total, sl_buf, tp_pts, len(trades))
        print()
        if best:
            print(f"  BEST {setup_name}: SLbuf=${best[1]} TPpts=${best[2]} n={best[3]} ==> ${best[0]:+.1f} @ {LOTS} lots ==> ${best[0]*MULTIPLIER_FOR_REPORT:+.1f} @ {LOTS*MULTIPLIER_FOR_REPORT} lots")
        print()


if __name__ == "__main__":
    main()
