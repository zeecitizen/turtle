"""Tick-by-tick post-mortem on every closed XAUUSD trade today.

For each trade:
  1. Entry tick → exit tick = trade lifetime
  2. Walk every tick within that window
  3. Compute running P&L and find peak
  4. Report: peak P&L, time-to-peak, time-to-reverse, what early-exit would have done

Tests Zee's hypothesis: were we holding too long? Did peaks happen <30s in?
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import json

if not mt5.initialize(timeout=15000):
    print(f"[FAIL] {mt5.last_error()}"); raise SystemExit

CONTRACT_SIZE = 100
SYMBOL = "XAUUSD"

now = datetime.now(timezone.utc)
window_start = now - timedelta(hours=48)  # last 48h to capture yesterday's mains too

# Get all deals in window
deals = mt5.history_deals_get(window_start, now)
if not deals: print("No deals"); raise SystemExit
xau_deals = [d for d in deals if "XAUUSD" in (d.symbol or "")]
print(f"Total XAUUSD deals today: {len(xau_deals)}")

# Pair opens with closes by position_id
positions_dict = {}  # position_id -> {open: deal, close: deal}
for d in xau_deals:
    pid = d.position_id
    if pid == 0: continue
    if pid not in positions_dict:
        positions_dict[pid] = {}
    if d.entry == 0: positions_dict[pid]["open"] = d
    elif d.entry == 1: positions_dict[pid]["close"] = d

closed_positions = [(pid, p) for pid, p in positions_dict.items() if "open" in p and "close" in p]
print(f"Closed positions in 48h window: {len(closed_positions)}")
print()

# Also pull currently OPEN positions (to track live trade)
open_now = mt5.positions_get(symbol=SYMBOL) or []
print(f"Currently open: {len(open_now)}")
for o in open_now:
    print(f"  ticket={o.ticket} {('BUY' if o.type==0 else 'SELL')} {o.volume} @ {o.price_open} floating ${o.profit:.2f} comment={o.comment!r}")
print()

# Identify position categories
def category(o):
    c = (o.comment or "")
    vol = o.volume
    if "Burst1" in c or "MG_Burst" in c: return "MAIN"
    if "PineConnector" in c and abs(vol - 0.01) < 0.005: return "PROBE"
    if "LSL_LB" in c: return "LB_LIVE"
    if "LSL_VSISA" in c: return "VSISA_LIVE"
    if abs(vol - 0.01) < 0.005: return "PROBE"
    return f"OTHER({vol})"

# Group: only do post-mortem on MAIN trades (the big ones that matter)
main_positions = []
for pid, p in closed_positions:
    cat = category(p["open"])
    if cat in ("MAIN", "LB_LIVE", "VSISA_LIVE"):
        main_positions.append((pid, p, cat))

# Also analyze currently-open trades in real-time
print("=== CURRENTLY OPEN TRADES — tick-by-tick paths ===")
for o in open_now:
    cat = category(o)  # close enough; comment is the same field
    side = "buy" if o.type == 0 else "sell"
    entry_price = o.price_open
    entry_ts = datetime.fromtimestamp(o.time, tz=timezone.utc)
    ticks = mt5.copy_ticks_range(SYMBOL, entry_ts - timedelta(seconds=2), now, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) < 2: continue
    ts_arr = ticks["time_msc"].astype(np.int64)
    bid = ticks["bid"].astype(float); ask = ticks["ask"].astype(float)
    if side == "buy":
        rpnl = (bid - entry_price) * CONTRACT_SIZE * o.volume
    else:
        rpnl = (entry_price - ask) * CONTRACT_SIZE * o.volume
    peak = float(rpnl.max()); peak_idx = int(np.argmax(rpnl))
    peak_age = (int(ts_arr[peak_idx]) - int(ts_arr[0])) / 1000.0
    age_now = (now - entry_ts).total_seconds()
    cur = float(rpnl.iloc[-1])
    print(f"  ticket={o.ticket} {side.upper()} {o.volume} entry={entry_price:.2f} | NOW: ${cur:+.2f} after {age_now:.0f}s | peak: ${peak:+.2f} at {peak_age:.0f}s | from peak: ${cur-peak:+.2f}")
    # Show every 30s of running P&L
    print(f"    P&L path (every 30s):")
    interval_s = 30
    last_ts = int(ts_arr[0])
    samples = []
    for i, t in enumerate(ts_arr):
        if int(t) - last_ts >= interval_s * 1000 or i == 0:
            samples.append((int(t) - int(ts_arr[0]), float(rpnl.iloc[i])))
            last_ts = int(t)
    samples.append((int(ts_arr.iloc[-1]) - int(ts_arr[0]), float(rpnl.iloc[-1])))
    for sec, p in samples:
        bar = "█" * max(0, int(p / 5)) if p > 0 else ("─" * max(0, int(-p / 5)))
        print(f"      +{sec:>4}s: ${p:+7.2f}  {bar}")
print()

print(f"Main-class positions to analyze: {len(main_positions)}\n")

print(f"{'pid':>10} {'cat':>10} {'side':>4} {'entry':>8} {'exit':>8} {'pnl$':>8} {'lifetime':>10} {'peak$':>8} {'peak_age':>9} {'fav%':>6} {'underwater':>11}")
print("-" * 120)

# === ANALYZE EACH ===
analysis = []
for pid, p, cat in main_positions:
    o = p["open"]; c = p["close"]
    side = "buy" if o.type == 0 else "sell"
    entry_price = o.price
    entry_ts_ms = o.time_msc
    exit_price = c.price
    exit_ts_ms = c.time_msc
    lots = o.volume
    pnl = c.profit
    lifetime_s = (exit_ts_ms - entry_ts_ms) / 1000.0

    # Pull ticks during trade's lifetime
    t_start = datetime.fromtimestamp(entry_ts_ms/1000 - 1, tz=timezone.utc)
    t_end = datetime.fromtimestamp(exit_ts_ms/1000 + 1, tz=timezone.utc)
    ticks = mt5.copy_ticks_range(SYMBOL, t_start, t_end, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) < 2:
        print(f"{pid:>10} {cat:>10} {side:>4} (no tick data)")
        continue

    # Compute running P&L
    ts = ticks["time_msc"].astype(np.int64)
    bid = ticks["bid"].astype(float)
    ask = ticks["ask"].astype(float)
    if side == "buy":
        running_pnl = (bid - entry_price) * CONTRACT_SIZE * lots
    else:
        running_pnl = (entry_price - ask) * CONTRACT_SIZE * lots

    peak_pnl = float(running_pnl.max())
    peak_idx = int(np.argmax(running_pnl))
    peak_ts_ms = int(ts[peak_idx])
    peak_age_s = (peak_ts_ms - entry_ts_ms) / 1000.0
    fav_pct = peak_pnl / max(0.01, abs(pnl)) * 100 if pnl < 0 else 0
    underwater_pct = float((running_pnl < 0).mean()) * 100  # % of trade time spent underwater

    print(f"{pid:>10} {cat:>10} {side:>4} {entry_price:>8.2f} {exit_price:>8.2f} {pnl:>8.2f} {lifetime_s:>9.0f}s {peak_pnl:>8.2f} {peak_age_s:>8.0f}s {fav_pct:>5.0f}% {underwater_pct:>10.0f}%")

    analysis.append({
        "pid": pid, "cat": cat, "side": side, "entry": entry_price, "exit": exit_price,
        "pnl": pnl, "lifetime_s": lifetime_s, "peak_pnl": peak_pnl,
        "peak_age_s": peak_age_s, "fav_pct": fav_pct, "underwater_pct": underwater_pct,
    })

# === EARLY-EXIT WHAT-IF ===
# What if we'd exited when peak hit $X for various X?
print("\n=== EARLY-EXIT WHAT-IF ===")
print("If we'd exited the moment peak P&L reached the threshold, what would total be?")
print()
print(f"{'threshold':>10} {'n_hit':>6} {'orig_total':>11} {'early_total':>12} {'delta':>10}")
print("-" * 55)

# We need the running P&L for each trade
trade_paths = []
for pid, p, cat in main_positions:
    o = p["open"]; c = p["close"]
    side = "buy" if o.type == 0 else "sell"
    t_start = datetime.fromtimestamp(o.time_msc/1000 - 1, tz=timezone.utc)
    t_end = datetime.fromtimestamp(c.time_msc/1000 + 1, tz=timezone.utc)
    ticks = mt5.copy_ticks_range(SYMBOL, t_start, t_end, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) < 2: continue
    bid = ticks["bid"].astype(float); ask = ticks["ask"].astype(float)
    if side == "buy":
        rpnl = (bid - o.price) * CONTRACT_SIZE * o.volume
    else:
        rpnl = (o.price - ask) * CONTRACT_SIZE * o.volume
    trade_paths.append({"pid": pid, "rpnl": rpnl, "actual_pnl": c.profit, "side": side})

# What-if: exit if peak >= threshold; else SL hit if running <= -threshold/2 etc
# Simpler: trail-based — once running >= trigger, close on first drop of $drop from peak
trail_configs = [
    {"trigger": 5, "drop": 2},
    {"trigger": 8, "drop": 3},
    {"trigger": 10, "drop": 4},
    {"trigger": 15, "drop": 5},
    {"trigger": 22, "drop": 6},  # current Shano-Zee config
]
for trc in trail_configs:
    early_total = 0.0; n_triggered = 0; n_baseline = 0
    for tp in trade_paths:
        rp = tp["rpnl"]
        peak_so_far = -1e9; exited = False; final = float(float(rp[-1]))
        for v in rp:
            if v > peak_so_far: peak_so_far = v
            if peak_so_far >= trc["trigger"] and (peak_so_far - v) >= trc["drop"]:
                final = float(v); exited = True; break
        if exited: n_triggered += 1
        early_total += final
        n_baseline += 1
    orig_total = sum(tp["actual_pnl"] for tp in trade_paths)
    delta = early_total - orig_total
    print(f"  T={trc['trigger']}/${trc['drop']:>2} | {n_triggered:>4}/{n_baseline:>3} | {orig_total:>10.2f} | {early_total:>11.2f} | {delta:>+9.2f}")

# Tighter trails — book partial early
print("\n=== AGGRESSIVE BOOK-PARTIAL WHAT-IFS ===")
print("Book ENTIRE position the moment running P&L hits $X (no drawback at all)")
print()
for fixed_tp in [3, 5, 8, 10, 15, 20]:
    early_total = 0.0; n_hit = 0
    for tp in trade_paths:
        rp = tp["rpnl"]
        booked = False; final = float(float(rp[-1]))
        for v in rp:
            if v >= fixed_tp:
                final = fixed_tp; booked = True; break
            # if SL would have hit (using actual final SL distance)
        if booked: n_hit += 1
        early_total += final
    delta = early_total - sum(tp["actual_pnl"] for tp in trade_paths)
    print(f"  fixed_tp=${fixed_tp:>2} | n_hit={n_hit:>3}/{len(trade_paths):>2} | total={early_total:>9.2f}  delta={delta:>+9.2f}")

mt5.shutdown()
