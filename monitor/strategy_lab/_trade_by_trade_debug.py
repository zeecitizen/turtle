"""Trade-by-trade comparison: for each LIVE main entry, replay backtest's view at that moment.

Goal: figure out WHY backtest missed each live main (or extra mains).

Live mains today (from MT5 history):
  01:01:00 BUY 0.30 Burst1
  13:15:00 BUY 0.30 Burst1
  13:15:59 BUY 0.22 MG_Burst2
  17:25:17 BUY 0.30 Burst1
  19:16:22 SELL 0.30 Burst1
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")

CFG = {
    "probeConfirm": 0.75, "probeFail": 3.0, "probeLots": 0.01,
    "uhvFilter": True, "uhvLookback": 20, "triggerPastUhvPts": 0.3,
    "trendFilter": True, "m15TrendFilter": True,
    "setup1Filter": True, "setup1LookbackBars": 3, "setup1PatternLookback": 10,
    "setup1EffortResult": True, "effortBodyMin": 0.50, "effortWickMax": 0.40,
    "burstDeltaFilter": True, "burstDeltaLookbackSec": 5,
    "BIG_RATIO": 1.5, "SQUARE_BAR": 0.50,
    "tickSpeedMaxSec": 15, "spreadMaxMult": 1.2,
}
CONTRACT_SIZE = 100; COMMISSION = 7.0

# Live mains (from MT5 history pull earlier today)
LIVE_MAINS = [
    ("01:01:00", "buy",  4696.74, "Burst1"),
    ("13:15:00", "buy",  4735.35, "Burst1"),
    ("13:15:59", "buy",  4735.99, "MG_Burst2"),
    ("17:25:17", "buy",  4758.99, "Burst1"),
    ("19:16:22", "sell", 4711.57, "Burst1"),
]

print("[LOAD] reading parquet...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
last_msc = int(df["time_msc"].max())
last_dt = datetime.fromtimestamp(last_msc/1000, tz=timezone.utc)
today_start = datetime(last_dt.year, last_dt.month, last_dt.day, 0, 0, 0, tzinfo=timezone.utc)
context_start = today_start - timedelta(days=3)
df = df[df["time_msc"] >= int(context_start.timestamp() * 1000)].reset_index(drop=True)
ts   = df["time_msc"].to_numpy(dtype=np.int64)
bids = df["bid"].to_numpy(dtype=np.float64)
asks = df["ask"].to_numpy(dtype=np.float64)

def find_idx(t_ms): return int(np.searchsorted(ts, t_ms, side="right"))

def build_bars(tf_sec):
    bucket = (df["time_msc"] // (tf_sec * 1000)).astype(np.int64)
    g = df.assign(_b=bucket).groupby("_b", sort=True).agg(
        open=("bid","first"), high=("bid","max"), low=("bid","min"),
        close=("bid","last"), n_ticks=("bid","count"),
        ts_end_ms=("time_msc","last"),
    ).reset_index().drop(columns="_b")
    g["body"] = (g["close"] - g["open"]).abs()
    g["dir"]  = np.sign(g["close"] - g["open"]).astype(int)
    return g

b_m1  = build_bars(60)
b_m2  = build_bars(120)
b_m15 = build_bars(900)

m1_o = b_m1["open"].to_numpy();   m1_h = b_m1["high"].to_numpy()
m1_l = b_m1["low"].to_numpy();    m1_c = b_m1["close"].to_numpy()
m1_v = b_m1["n_ticks"].to_numpy(); m1_ts_end = b_m1["ts_end_ms"].to_numpy()

def ema(values, period):
    alpha = 2/(period+1); out = np.zeros(len(values)); out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i-1]
    return out

m2_close = b_m2["close"].to_numpy(); m2_ts = b_m2["ts_end_ms"].to_numpy()
m2_ema34 = ema(m2_close, 34); m2_ema89 = ema(m2_close, 89)
m15_close = b_m15["close"].to_numpy(); m15_ts = b_m15["ts_end_ms"].to_numpy()
m15_ema34 = ema(m15_close, 34); m15_ema89 = ema(m15_close, 89)

def trend_at(ts_ms, ef, es, bts, dir_sign):
    idx = int(np.searchsorted(bts, ts_ms, side="right")) - 1
    if idx < 89: return "no_data", None
    f = ef[idx]; s = es[idx]; fp = ef[idx-1]
    if dir_sign == 1:
        if f > s and f > fp: return "PASS", f"f={f:.2f}>s={s:.2f}, f>fp={fp:.2f}"
        return "FAIL", f"f={f:.2f} s={s:.2f} fp={fp:.2f} (need f>s & f>fp for buy)"
    else:
        if f < s and f < fp: return "PASS", f"f={f:.2f}<s={s:.2f}, f<fp={fp:.2f}"
        return "FAIL", f"f={f:.2f} s={s:.2f} fp={fp:.2f} (need f<s & f<fp for sell)"

def uhv_breakout_check(sig_ts_ms, dir_sign, trigger_close):
    idx = int(np.searchsorted(m1_ts_end, sig_ts_ms, side="right")) - 1
    if idx < CFG["uhvLookback"] + 1: return "no_data", None
    lb = max(0, idx - CFG["uhvLookback"])
    look_v = m1_v[lb:idx]
    if len(look_v) == 0: return "no_data", None
    uhv_g = lb + int(np.argmax(look_v))
    margin = CFG["triggerPastUhvPts"]
    if dir_sign == 1:
        ok = trigger_close > m1_h[uhv_g] + margin
        return ("PASS" if ok else "FAIL", f"trigger_close={trigger_close:.2f} vs UHV_high={m1_h[uhv_g]:.2f}+{margin}={m1_h[uhv_g]+margin:.2f}")
    else:
        ok = trigger_close < m1_l[uhv_g] - margin
        return ("PASS" if ok else "FAIL", f"trigger_close={trigger_close:.2f} vs UHV_low={m1_l[uhv_g]:.2f}-{margin}={m1_l[uhv_g]-margin:.2f}")

def setup1_check(sig_ts_ms, dir_sign):
    idx = int(np.searchsorted(m1_ts_end, sig_ts_ms, side="right")) - 1
    needed = CFG["setup1LookbackBars"] + CFG["setup1PatternLookback"] + 2
    if idx < needed: return "no_data", None
    notes = []
    for trig_off in range(CFG["setup1LookbackBars"]):
        trig_idx = idx - trig_off
        s_start = max(0, trig_idx - CFG["setup1PatternLookback"]); s_end = trig_idx
        if s_end <= s_start: notes.append(f"trig_off={trig_off}: window empty"); continue
        match_red = (dir_sign == 1)
        uhv_idx = -1; uhv_vol = -1
        for s in range(s_start, s_end):
            isRed = m1_c[s] < m1_o[s]; isGreen = m1_c[s] > m1_o[s]
            colored = isRed if match_red else isGreen
            if colored and m1_v[s] > uhv_vol:
                uhv_vol = m1_v[s]; uhv_idx = s
        if uhv_idx < 0:
            notes.append(f"trig_off={trig_off}: no matching-color UHV in pattern window"); continue
        swept = False
        for s in range(uhv_idx + 1, trig_idx):
            if dir_sign == 1 and m1_l[s] < m1_l[uhv_idx]: swept = True; break
            if dir_sign == -1 and m1_h[s] > m1_h[uhv_idx]: swept = True; break
        if not swept:
            notes.append(f"trig_off={trig_off}: UHV @bar{uhv_idx} not swept"); continue
        if CFG["setup1EffortResult"]:
            rng = m1_h[uhv_idx] - m1_l[uhv_idx]
            if rng <= 0:
                notes.append(f"trig_off={trig_off}: UHV @bar{uhv_idx} zero range"); continue
            body = abs(m1_c[uhv_idx] - m1_o[uhv_idx])
            uw = m1_h[uhv_idx] - max(m1_o[uhv_idx], m1_c[uhv_idx])
            lw = min(m1_o[uhv_idx], m1_c[uhv_idx]) - m1_l[uhv_idx]
            if body / rng < CFG["effortBodyMin"]:
                notes.append(f"trig_off={trig_off}: UHV body/range={body/rng:.2f}<{CFG['effortBodyMin']}"); continue
            if uw / rng > CFG["effortWickMax"]:
                notes.append(f"trig_off={trig_off}: UHV upper_wick/range={uw/rng:.2f}>{CFG['effortWickMax']}"); continue
            if lw / rng > CFG["effortWickMax"]:
                notes.append(f"trig_off={trig_off}: UHV lower_wick/range={lw/rng:.2f}>{CFG['effortWickMax']}"); continue
        isGreenT = m1_c[trig_idx] > m1_o[trig_idx]; isRedT = m1_c[trig_idx] < m1_o[trig_idx]
        if dir_sign == 1 and isGreenT and m1_c[trig_idx] > m1_h[uhv_idx]:
            return "PASS", f"trig_off={trig_off}: UHV@bar{uhv_idx} (vol={uhv_vol}), trigger@bar{trig_idx} green close={m1_c[trig_idx]:.2f}>UHV_high={m1_h[uhv_idx]:.2f}"
        if dir_sign == -1 and isRedT and m1_c[trig_idx] < m1_l[uhv_idx]:
            return "PASS", f"trig_off={trig_off}: UHV@bar{uhv_idx} (vol={uhv_vol}), trigger@bar{trig_idx} red close={m1_c[trig_idx]:.2f}<UHV_low={m1_l[uhv_idx]:.2f}"
        notes.append(f"trig_off={trig_off}: trigger@bar{trig_idx} doesn't break UHV")
    return "FAIL", "; ".join(notes[:3])

# Detect signals on M1
body = b_m1["body"].to_numpy(); direction = b_m1["dir"].to_numpy()
m1_range = m1_h - m1_l
prev_body = np.roll(body, 1); prev_range = np.roll(m1_range, 1)
square_ok_prev = np.zeros(len(body), dtype=bool)
square_ok_prev[1:] = np.where(prev_range[1:] > 0, prev_body[1:] / prev_range[1:] >= CFG["SQUARE_BAR"], False)
n = len(body)
big_prev = np.zeros(n, dtype=bool)
big_prev[2:] = body[1:-1] > CFG["BIG_RATIO"] * body[:-2]
dir_prev = np.roll(direction, 1)
sig_buy  = big_prev & (dir_prev == 1)  & (direction == 1) & square_ok_prev
sig_sell = big_prev & (dir_prev == -1) & (direction == -1) & square_ok_prev
sig_buy[:2] = False; sig_sell[:2] = False
sig_bars = []
for i in np.where(sig_buy)[0]: sig_bars.append((i, int(m1_ts_end[i]), 1, float(m1_c[i])))
for i in np.where(sig_sell)[0]: sig_bars.append((i, int(m1_ts_end[i]), -1, float(m1_c[i])))
sig_bars.sort(key=lambda x: x[1])

print(f"[SIG] {len(sig_bars)} M1 signals across context window\n")

# === FOR EACH LIVE MAIN, FIND BACKTEST'S VIEW ===
print("=" * 100)
print("TRADE-BY-TRADE: for each LIVE main, what did the backtest see?")
print("=" * 100)
for hms, side_str, live_price, label in LIVE_MAINS:
    side = 1 if side_str == "buy" else -1
    h, m, s = map(int, hms.split(":"))
    main_dt = today_start.replace(hour=h, minute=m, second=s)
    main_ts_ms = int(main_dt.timestamp() * 1000)

    # Backtest probe should fire ~5-60s before main entry (probe → confirm → main)
    # Look at signals in the last 5 minutes before main entry
    window_start = main_ts_ms - 5*60*1000
    candidates = [s for s in sig_bars if window_start <= s[1] <= main_ts_ms + 60*1000]

    print(f"\n{'='*100}")
    print(f"LIVE MAIN @ {hms} UTC | {side_str.upper()} {live_price} | {label}")
    print(f"{'='*100}")

    if not candidates:
        # Maybe live signal happened in the same minute as main entry
        # Look at the M1 bar containing main_ts_ms
        bar_idx = int(np.searchsorted(m1_ts_end, main_ts_ms, side="right"))
        # Check signals on neighboring M1 bars
        print(f"  ⚠ NO BACKTEST SIGNAL in last 5min window. Checking nearby bars...")
        for delta in range(-3, 2):
            bi = bar_idx + delta
            if 0 <= bi < len(m1_o):
                t = datetime.fromtimestamp(m1_ts_end[bi]/1000, tz=timezone.utc).strftime("%H:%M:%S")
                cur_dir = "G" if m1_c[bi] > m1_o[bi] else "R" if m1_c[bi] < m1_o[bi] else "D"
                prev_dir = "G" if bi > 0 and m1_c[bi-1] > m1_o[bi-1] else "R" if bi > 0 and m1_c[bi-1] < m1_o[bi-1] else "D"
                this_body = body[bi]; prev_body_v = body[bi-1] if bi > 0 else 0
                ratio = this_body / prev_body_v if prev_body_v > 0 else 0
                square = (prev_body[bi] / prev_range[bi]) if (bi >= 1 and prev_range[bi] > 0) else 0
                in_sigs = sig_buy[bi] or sig_sell[bi]
                print(f"    bar@{t} O={m1_o[bi]:.2f} H={m1_h[bi]:.2f} L={m1_l[bi]:.2f} C={m1_c[bi]:.2f}"
                      f" dir={cur_dir} prev={prev_dir} body={this_body:.2f} prev_body={prev_body_v:.2f}"
                      f" ratio={ratio:.2f} sq_prev={square:.2f} sig={in_sigs}")
        continue

    for bar_i, sig_ts_ms, sig_side, trig_close in candidates:
        t = datetime.fromtimestamp(sig_ts_ms/1000, tz=timezone.utc).strftime("%H:%M:%S")
        sig_side_str = "buy" if sig_side == 1 else "sell"
        side_match = "✓" if sig_side == side else "✗ DIRECTION MISMATCH"
        print(f"\n  Signal @ {t} | {sig_side_str.upper()} | trigger_close={trig_close:.2f} | {side_match}")

        # Run all filter checks
        uhv_status, uhv_msg = uhv_breakout_check(sig_ts_ms, sig_side, trig_close)
        print(f"    UHV breakout:    {uhv_status:<6}  {uhv_msg or ''}")

        t2_status, t2_msg = trend_at(sig_ts_ms, m2_ema34, m2_ema89, m2_ts, sig_side)
        print(f"    M2 trend EMA:    {t2_status:<6}  {t2_msg or ''}")

        m15_status, m15_msg = trend_at(sig_ts_ms, m15_ema34, m15_ema89, m15_ts, sig_side)
        print(f"    M15 trend EMA:   {m15_status:<6}  {m15_msg or ''}")

        s1_status, s1_msg = setup1_check(sig_ts_ms, sig_side)
        print(f"    Setup 1 gate:    {s1_status:<6}  {s1_msg or ''}")

        # Check probe outcome
        pi = find_idx(sig_ts_ms)
        if pi < len(ts):
            p_entry = asks[pi] if sig_side == 1 else bids[pi]
            end_p = find_idx(ts[pi] + 600 * 1000)
            if sig_side == 1:
                pa = (bids[pi:end_p] - p_entry) * CONTRACT_SIZE * CFG["probeLots"]
            else:
                pa = (p_entry - asks[pi:end_p]) * CONTRACT_SIZE * CFG["probeLots"]
            ci = int(np.argmax(pa >= CFG["probeConfirm"])) if (pa >= CFG["probeConfirm"]).any() else -1
            fi = int(np.argmax(pa <= -CFG["probeFail"])) if (pa <= -CFG["probeFail"]).any() else -1
            if ci >= 0 and (fi < 0 or ci <= fi):
                print(f"    Probe outcome:   CONFIRM at +${pa[ci]:.2f}")
            elif fi >= 0:
                print(f"    Probe outcome:   FAIL at -${abs(pa[fi]):.2f}")
            else:
                print(f"    Probe outcome:   TIMEOUT")
