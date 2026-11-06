"""Backtest UhvNativeTrader.mq5 v1.00 logic on full parquet tick data.

Mirrors the EA's actual logic exactly:
  - UHV detection: highest-vol M1 bar in last 20 closed bars (excl. current)
  - Stale check: discard if UHV > 10 bars old
  - Body % gate: UHV body must be >= 50% of range
  - Direction: red UHV → BUY, green UHV → SELL
  - Pre-offset entry: fire when ask reaches level - $1 (BUY) or bid reaches level + $1 (SELL)
  - Body breakout: cur close OR prev close past UHV level
  - Sydney filter: skip 00-06 GMT (memory-validated 0% WR)
  - Min spacing: 60s between entries

Two exit modes (run both for comparison):
  A) Fixed-TP: +$3 TP, $15 SL, 5s kill
  B) Trailing:  arm at +$8, exit on $2 drop, 30s scratch, 60s timeout, $15 catastrophic

Lots = 0.10 (matches EA default). 1 point of XAUUSD price = $10 P&L per 0.10 lot.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_uhv_native_trader_backtest.json")

LOTS          = 0.10
COMMISSION    = 7.0 * LOTS         # $0.70 per round-trip
CONTRACT_SIZE = 100                # XAUUSD 1 lot = 100 oz, so $1 PnL per 0.01 price-move at 1.0 lot
PIP_PRICE     = 0.10               # 1 pip in price units (broker pip size)

# === EA settings (mirrors UhvNativeTrader v1.00 defaults) ===
UHV_LOOKBACK         = 20
UHV_MAX_AGE_BARS     = 10
MIN_BODY_PCT         = 0.65        # was 0.50; tightened to match VSA spec
PRE_OFFSET_PTS       = 1.0
REQUIRE_BODY_CLOSE   = True
MIN_SPACING_SEC      = 60
SKIP_SYDNEY          = True
DAILY_LOSS_USD       = 100.0
REQUIRE_BG_CONTEXT   = True
BG_LOOKBACK_BARS     = 5
REQUIRE_BG_MIN_COUNT = 3           # at least 3 of 5 bg bars opposite color (vs simple majority)
REQUIRE_NO_SUPPLY    = True        # NEW: cur bar volume must be < UHV volume × MAX_VOL_RATIO
MAX_VOL_RATIO        = 0.70        # cur bar must be quieter than UHV (no-supply confirmation)

EXIT_MODE_FIXED = {
    "label":         "Fixed-TP (default)",
    "use_trailing":  False,
    "tp_usd":        3.0,
    "sl_usd":        15.0,
    "kill_sec":      5,
}
EXIT_MODE_TRAILING = {
    "label":         "Trailing (Zee's preferred)",
    "use_trailing":  True,
    "trail_trigger": 8.0,
    "trail_drop":    2.0,
    "scratch_sec":   30,
    "max_hold_sec":  60,
    "sl_usd":        15.0,    # catastrophic stop, both modes
}

print("[LOAD] parquet...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
print(f"  {len(df):,} ticks, {df['time_msc'].iloc[0]} .. {df['time_msc'].iloc[-1]}", flush=True)

# Aggregate to M1 bars (mid is fine for OHLCV; entries use ask/bid separately)
df["m1"] = (df["time_msc"] // 60_000).astype(np.int64)
m1_grp = df.groupby("m1", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m1")
m1_grp["dt"] = pd.to_datetime(m1_grp["ts_end_ms"], unit="ms", utc=True)
m1_grp["date"] = m1_grp["dt"].dt.strftime("%Y-%m-%d")
m1_grp["hour"] = m1_grp["dt"].dt.hour
m1 = m1_grp.to_dict("records")
print(f"[LOAD] M1 bars: {len(m1):,}", flush=True)

ts_arr   = df["time_msc"].to_numpy(dtype=np.int64)
bids_arr = df["bid"].to_numpy(dtype=np.float64)
asks_arr = df["ask"].to_numpy(dtype=np.float64)


# === UHV DETECTION (matches EA UhvNativeTrader::DetectBreakout) ===
def detect_signal(idx):
    """Returns dict if UHV breakout setup is active at end of M1 bar idx, else None."""
    if idx < UHV_LOOKBACK + 2:
        return None
    # Find highest-volume CLOSED bar in shifts 1..UHV_LOOKBACK
    win_lo = idx - UHV_LOOKBACK
    win_hi = idx          # exclusive — bar at idx is the "current" / triggering bar
    uhv_idx = max(range(win_lo, win_hi), key=lambda j: m1[j]["v"])
    uhv = m1[uhv_idx]
    if uhv["v"] <= 0:
        return None
    # Stale check
    if (idx - uhv_idx) > UHV_MAX_AGE_BARS:
        return None
    # Body % gate
    rng = uhv["h"] - uhv["l"]
    body = abs(uhv["c"] - uhv["o"])
    if rng <= 0 or (body / rng) < MIN_BODY_PCT:
        return None
    is_red = uhv["c"] < uhv["o"]
    is_green = uhv["c"] > uhv["o"]
    if not (is_red or is_green):
        return None
    # Background context filter (Wyckoff selling-climax / buying-climax pattern)
    # For LONG (red UHV): majority of N bars BEFORE UHV should be RED (sell-off context)
    # For SHORT (green UHV): majority should be GREEN (rally context)
    if REQUIRE_BG_CONTEXT:
        bg_lo = max(0, uhv_idx - BG_LOOKBACK_BARS)
        bg_bars = m1[bg_lo:uhv_idx]
        if not bg_bars:
            return None
        red_n   = sum(1 for b in bg_bars if b["c"] < b["o"])
        green_n = sum(1 for b in bg_bars if b["c"] > b["o"])
        needed  = (BG_LOOKBACK_BARS // 2) + 1
        if is_red and red_n < needed:    # buy setup needs red bg
            return None
        if is_green and green_n < needed:  # sell setup needs green bg
            return None
    cur = m1[idx]
    prev = m1[idx - 1] if idx > 0 else cur
    pre = PRE_OFFSET_PTS * 0.01      # 1 point = $0.01 in price

    if is_red:  # BUY setup — break above UHV high
        trigger = uhv["h"] - pre
        # Body breakout confirmation
        body_ok = (cur["c"] > uhv["h"]) or (prev["c"] > uhv["h"]) if REQUIRE_BODY_CLOSE else True
        if not body_ok:
            return None
        # Did bar close trigger price at all? Use bar high as proxy for "ask reached trigger"
        if cur["h"] < trigger:
            return None
        return {
            "side": "buy", "trigger_price": trigger, "level": uhv["h"],
            "uhv_h": uhv["h"], "uhv_l": uhv["l"], "ts_end_ms": cur["ts_end_ms"],
        }
    else:       # SELL setup — break below UHV low
        trigger = uhv["l"] + pre
        body_ok = (cur["c"] < uhv["l"]) or (prev["c"] < uhv["l"]) if REQUIRE_BODY_CLOSE else True
        if not body_ok:
            return None
        if cur["l"] > trigger:
            return None
        return {
            "side": "sell", "trigger_price": trigger, "level": uhv["l"],
            "uhv_h": uhv["h"], "uhv_l": uhv["l"], "ts_end_ms": cur["ts_end_ms"],
        }


def find_fill_tick(sig, search_from_ms):
    """Walk ticks from search_from_ms forward (within +5min window). Return (idx, fill_price, fill_ts) or None."""
    end_ts = search_from_ms + 5 * 60 * 1000
    i0 = int(np.searchsorted(ts_arr, search_from_ms, side="left"))
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    for k in range(i0, i1):
        if sig["side"] == "buy":
            if asks_arr[k] >= sig["trigger_price"]:
                return k, asks_arr[k], int(ts_arr[k])
        else:
            if bids_arr[k] <= sig["trigger_price"]:
                return k, bids_arr[k], int(ts_arr[k])
    return None


def walk_exit(side, fill_idx, entry_price, entry_ts, mode):
    """Walk ticks from fill_idx forward, return exit info (pnl, reason, age_s, peak_pnl)."""
    end_ts = entry_ts + (mode.get("max_hold_sec", 600) + 60) * 1000
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    peak_pnl_usd = -1e9
    has_been_positive = False
    trail_armed = False

    for k in range(fill_idx + 1, i1):
        elapsed = (ts_arr[k] - entry_ts) / 1000.0
        if side == "buy":
            cur_pnl_usd = (bids_arr[k] - entry_price) * CONTRACT_SIZE * LOTS
            exit_price = bids_arr[k]
        else:
            cur_pnl_usd = (entry_price - asks_arr[k]) * CONTRACT_SIZE * LOTS
            exit_price = asks_arr[k]
        peak_pnl_usd = max(peak_pnl_usd, cur_pnl_usd)
        if cur_pnl_usd > 0:
            has_been_positive = True
        # Catastrophic SL — both modes
        if cur_pnl_usd <= -mode["sl_usd"]:
            return {"pnl_usd": cur_pnl_usd - COMMISSION, "reason": "SL",
                    "age_s": elapsed, "peak_pnl_usd": peak_pnl_usd, "exit_price": exit_price}
        if mode["use_trailing"]:
            if not trail_armed and peak_pnl_usd >= mode["trail_trigger"]:
                trail_armed = True
            if trail_armed and (peak_pnl_usd - cur_pnl_usd) >= mode["trail_drop"]:
                return {"pnl_usd": cur_pnl_usd - COMMISSION, "reason": "TRAIL",
                        "age_s": elapsed, "peak_pnl_usd": peak_pnl_usd, "exit_price": exit_price}
            if not has_been_positive and elapsed > mode["scratch_sec"]:
                return {"pnl_usd": cur_pnl_usd - COMMISSION, "reason": "SCRATCH",
                        "age_s": elapsed, "peak_pnl_usd": peak_pnl_usd, "exit_price": exit_price}
            if elapsed >= mode["max_hold_sec"]:
                return {"pnl_usd": cur_pnl_usd - COMMISSION, "reason": "TIMEOUT",
                        "age_s": elapsed, "peak_pnl_usd": peak_pnl_usd, "exit_price": exit_price}
        else:
            # Fixed-TP mode
            if cur_pnl_usd >= mode["tp_usd"]:
                return {"pnl_usd": cur_pnl_usd - COMMISSION, "reason": "TP",
                        "age_s": elapsed, "peak_pnl_usd": peak_pnl_usd, "exit_price": exit_price}
            if elapsed >= mode["kill_sec"]:
                return {"pnl_usd": cur_pnl_usd - COMMISSION, "reason": "KILL",
                        "age_s": elapsed, "peak_pnl_usd": peak_pnl_usd, "exit_price": exit_price}
    return {"pnl_usd": 0.0, "reason": "OUT_OF_DATA",
            "age_s": 0, "peak_pnl_usd": peak_pnl_usd if peak_pnl_usd > -1e8 else 0, "exit_price": entry_price}


def run_backtest(mode):
    print(f"\n{'='*80}\nMODE: {mode['label']}\n{'='*80}", flush=True)
    trades = []
    last_entry_ts = 0
    daily_pnl = {}     # date_str → realized P&L
    halted_dates = set()

    for idx in range(UHV_LOOKBACK + 5, len(m1)):
        bar = m1[idx]
        date = bar["date"]
        # Sydney filter
        if SKIP_SYDNEY and bar["hour"] < 6:
            continue
        # Daily loss halt
        if date in halted_dates:
            continue
        if daily_pnl.get(date, 0) <= -DAILY_LOSS_USD:
            halted_dates.add(date)
            continue
        # Min spacing
        if int(bar["ts_end_ms"]) - last_entry_ts < MIN_SPACING_SEC * 1000:
            continue

        sig = detect_signal(idx)
        if not sig:
            continue
        fill = find_fill_tick(sig, sig["ts_end_ms"])
        if fill is None:
            continue
        fill_idx, fill_price, fill_ts = fill
        result = walk_exit(sig["side"], fill_idx, fill_price, fill_ts, mode)
        pnl = result["pnl_usd"]
        daily_pnl[date] = daily_pnl.get(date, 0) + pnl
        trades.append({
            "date": date, "time": pd.to_datetime(fill_ts, unit="ms", utc=True).strftime("%H:%M:%S"),
            "side": sig["side"], "entry": round(fill_price, 2),
            "uhv_h": round(sig["uhv_h"], 2), "uhv_l": round(sig["uhv_l"], 2),
            "trigger": round(sig["trigger_price"], 2),
            "pnl_usd": round(pnl, 2), "reason": result["reason"],
            "age_s": round(result["age_s"], 1), "peak_pnl": round(result["peak_pnl_usd"], 2),
        })
        last_entry_ts = fill_ts

    # Aggregate
    n = len(trades)
    if n == 0:
        return {"label": mode["label"], "n": 0, "summary": "no signals"}
    wins = sum(1 for t in trades if t["pnl_usd"] > 0)
    losses = sum(1 for t in trades if t["pnl_usd"] < 0)
    net = sum(t["pnl_usd"] for t in trades)
    avg = net / n
    by_reason = {}
    for t in trades:
        by_reason[t["reason"]] = by_reason.get(t["reason"], 0) + 1
    days_traded = len(set(t["date"] for t in trades))
    days_profit = sum(1 for d, p in daily_pnl.items() if p > 0)
    days_loss   = sum(1 for d, p in daily_pnl.items() if p < 0)
    print(f"  Trades: {n}   WR: {wins/n*100:.1f}%   Wins: {wins}  Losses: {losses}", flush=True)
    print(f"  Net:    ${net:+.2f}  Avg/trade: ${avg:+.2f}", flush=True)
    print(f"  Days:   traded {days_traded}   profitable {days_profit}   losing {days_loss}   halted {len(halted_dates)}", flush=True)
    print(f"  Reasons: {by_reason}", flush=True)
    print(f"  Last 10 trades:", flush=True)
    for t in trades[-10:]:
        print(f"    {t['date']} {t['time']} {t['side']:>4}  pnl=${t['pnl_usd']:+7.2f} ({t['reason']:>8} {t['age_s']:>5.1f}s)  peak=${t['peak_pnl']:+.2f}", flush=True)
    return {
        "label": mode["label"], "n": n, "wins": wins, "losses": losses,
        "wr_pct": round(wins / n * 100, 1), "net_usd": round(net, 2), "avg_usd": round(avg, 2),
        "days_traded": days_traded, "days_profit": days_profit, "days_loss": days_loss,
        "days_halted": len(halted_dates),
        "by_reason": by_reason,
        "daily_pnl": {d: round(p, 2) for d, p in sorted(daily_pnl.items())},
        "trades": trades,
    }


print(f"[BACKTEST] starting full-parquet UhvNativeTrader v1.00 backtest", flush=True)
print(f"  Lots:        {LOTS}", flush=True)
print(f"  Commission:  ${COMMISSION:.2f} per round trip", flush=True)
print(f"  Sydney filter: {'ON (skip 00-06 GMT)' if SKIP_SYDNEY else 'OFF'}", flush=True)
print(f"  Daily loss limit: ${DAILY_LOSS_USD}", flush=True)

results = {
    "started":     datetime.now(timezone.utc).isoformat(),
    "data_range":  f"{m1[0]['date']} .. {m1[-1]['date']}",
    "ticks":       len(df),
    "m1_bars":     len(m1),
    "lots":        LOTS,
    "fixed_tp":    run_backtest(EXIT_MODE_FIXED),
    "trailing":    run_backtest(EXIT_MODE_TRAILING),
}

# Strip per-trade detail before JSON dump (huge); keep summary
slim = {k: v for k, v in results.items() if k not in ("fixed_tp", "trailing")}
slim["fixed_tp"]  = {k: v for k, v in results["fixed_tp"].items()  if k != "trades"}
slim["trailing"]  = {k: v for k, v in results["trailing"].items()  if k != "trades"}
slim["fixed_tp"]["trades_csv"]  = "see _uhv_native_trader_backtest_fixed.csv"
slim["trailing"]["trades_csv"]  = "see _uhv_native_trader_backtest_trailing.csv"
OUT_J.write_text(json.dumps(slim, indent=2, default=str))

# Per-trade CSVs for deep-dive
for mode_key, results_obj in [("fixed", results["fixed_tp"]), ("trailing", results["trailing"])]:
    if results_obj.get("trades"):
        df_out = pd.DataFrame(results_obj["trades"])
        df_out.to_csv(OUT_J.parent / f"_uhv_native_trader_backtest_{mode_key}.csv", index=False)

print(f"\n[DONE] -> {OUT_J}", flush=True)
print(f"[DONE] CSVs in {OUT_J.parent}", flush=True)
