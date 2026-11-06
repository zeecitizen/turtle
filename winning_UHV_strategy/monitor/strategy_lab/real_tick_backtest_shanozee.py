"""Shano-Zee backtest on Blueberry real-tick stream (pure Python).

Reads:  monitor/strategy_lab/_xauusd_ticks.parquet
Writes: monitor/strategy_lab/_real_tick_results.json + _real_tick_trades.csv

Logic (matches startup.bat / CLAUDE.md spec):
  Signal:  body[N-1] > BIG_RATIO * body[N-2] AND dir[N-1] == dir[N]
           (bigness on FIRST bar; 2nd bar same direction, any size)
  Probe:   0.01 lot at next tick after signal; confirm at +$0.58 within 50s,
           fail at -$3.00, else timeout
  Main:    0.40 lot at probe direction at next tick after probe confirm;
           TP at +$10, SL at -$10
  P&L:     XAUUSD digits=2, 1 lot * 1 price unit = $100. So 0.01 lot * 1 = $1,
           and $0.58 profit on 0.01 lot = 0.58 price units of movement.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json, sys

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_real_tick_results.json")
OUT_C = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_real_tick_trades.csv")

# Strategy config
PROBE_LOT = 0.01
MAIN_LOT  = 0.40
PROBE_CONFIRM_USD = 0.58
PROBE_FAIL_USD = -3.0
PROBE_TIMEOUT_S = 50
MAIN_TP_USD = 10.0
MAIN_SL_USD = -10.0
BIG_RATIO = 1.5
M5_SECONDS = 300
CONTRACT_SIZE = 100  # oz per lot

print("[LOAD] reading parquet...", flush=True)
df = pd.read_parquet(CACHE)
df = df.sort_values("time_msc").reset_index(drop=True)
print(f"[LOAD] {len(df):,} ticks", flush=True)

# Build M5 bars on bid (the side we'd act on for sells; mid would also work)
df["m5_bucket"] = (df["time_msc"] // (M5_SECONDS * 1000)).astype(np.int64)
bars = df.groupby("m5_bucket", sort=True).agg(
    open=("bid", "first"),
    high=("bid", "max"),
    low=("bid", "min"),
    close=("bid", "last"),
    n=("bid", "count"),
    ts_start_ms=("time_msc", "first"),
    ts_end_ms=("time_msc", "last"),
).reset_index()
print(f"[BARS] built {len(bars):,} M5 bars", flush=True)

# Detect signals (vectorized)
bars["body"] = (bars["close"] - bars["open"]).abs()
bars["dir"]  = np.sign(bars["close"] - bars["open"]).astype(int)
bars["body_prev"] = bars["body"].shift(1)
bars["body_prev2"] = bars["body"].shift(2)
bars["dir_prev"] = bars["dir"].shift(1)
bars["big_prev"] = bars["body_prev"] > BIG_RATIO * bars["body_prev2"]

bars["sig_buy"]  = bars["big_prev"] & (bars["dir_prev"] == 1) & (bars["dir"] == 1)
bars["sig_sell"] = bars["big_prev"] & (bars["dir_prev"] == -1) & (bars["dir"] == -1)
n_buy  = int(bars["sig_buy"].sum())
n_sell = int(bars["sig_sell"].sum())
print(f"[SIG] {n_buy} buy, {n_sell} sell signals over {len(bars):,} M5 bars", flush=True)

# Convert ticks to numpy for fast iteration
ts   = df["time_msc"].to_numpy()
bids = df["bid"].to_numpy()
asks = df["ask"].to_numpy()

def find_idx(t_ms):
    """First tick index strictly after t_ms."""
    i = np.searchsorted(ts, t_ms, side="right")
    return i

trades = []
sig_bars = bars[bars["sig_buy"] | bars["sig_sell"]]
for _, r in sig_bars.iterrows():
    side = "buy" if r["sig_buy"] else "sell"
    sig_ts = int(r["ts_end_ms"])
    pi = find_idx(sig_ts)
    if pi >= len(ts):
        continue
    p_entry_ts = int(ts[pi])
    p_entry_bid = float(bids[pi]); p_entry_ask = float(asks[pi])
    p_entry = p_entry_ask if side == "buy" else p_entry_bid

    timeout_ts = p_entry_ts + PROBE_TIMEOUT_S * 1000
    end_idx = find_idx(timeout_ts)
    sub_ts = ts[pi:end_idx]
    sub_bid = bids[pi:end_idx]
    sub_ask = asks[pi:end_idx]
    if side == "buy":
        pnl_arr = (sub_bid - p_entry) * CONTRACT_SIZE * PROBE_LOT
    else:
        pnl_arr = (p_entry - sub_ask) * CONTRACT_SIZE * PROBE_LOT

    confirm_idx = np.argmax(pnl_arr >= PROBE_CONFIRM_USD) if (pnl_arr >= PROBE_CONFIRM_USD).any() else -1
    fail_idx    = np.argmax(pnl_arr <= PROBE_FAIL_USD)    if (pnl_arr <= PROBE_FAIL_USD).any() else -1

    probe_outcome = None; probe_exit_ts = None; probe_pnl = 0.0
    if confirm_idx >= 0 and (fail_idx < 0 or confirm_idx <= fail_idx):
        probe_outcome = "confirm"; probe_exit_ts = int(sub_ts[confirm_idx]); probe_pnl = float(pnl_arr[confirm_idx])
    elif fail_idx >= 0:
        probe_outcome = "fail"; probe_exit_ts = int(sub_ts[fail_idx]); probe_pnl = float(pnl_arr[fail_idx])
    else:
        probe_outcome = "timeout"; probe_exit_ts = int(sub_ts[-1]) if len(sub_ts) else p_entry_ts; probe_pnl = float(pnl_arr[-1]) if len(pnl_arr) else 0.0

    trade = {
        "ts": datetime.fromtimestamp(sig_ts/1000, tz=timezone.utc).isoformat(),
        "date": datetime.fromtimestamp(sig_ts/1000, tz=timezone.utc).strftime("%Y-%m-%d"),
        "side": side,
        "probe_outcome": probe_outcome,
        "probe_pnl": round(probe_pnl, 4),
        "probe_entry": round(p_entry, 2),
        "probe_spread_pts": round((p_entry_ask - p_entry_bid) * 100, 1),
        "probe_dur_s": round((probe_exit_ts - p_entry_ts) / 1000.0, 1),
        "main_outcome": None, "main_pnl": 0.0, "main_dur_s": None, "main_entry": None,
    }

    if probe_outcome != "confirm":
        trade["total_pnl"] = round(probe_pnl, 4)
        trades.append(trade)
        continue

    # Main entry at next tick after probe confirm
    mi = find_idx(probe_exit_ts)
    if mi >= len(ts):
        trade["total_pnl"] = round(probe_pnl, 4); trades.append(trade); continue
    m_entry_ts = int(ts[mi])
    m_entry_bid = float(bids[mi]); m_entry_ask = float(asks[mi])
    m_entry = m_entry_ask if side == "buy" else m_entry_bid

    # Cap main holding at 1 hour to avoid pathological holds in this baseline
    main_cap_ts = m_entry_ts + 3600 * 1000
    end_idx2 = find_idx(main_cap_ts)
    sub_ts2 = ts[mi:end_idx2]
    sub_bid2 = bids[mi:end_idx2]
    sub_ask2 = asks[mi:end_idx2]
    if side == "buy":
        m_pnl_arr = (sub_bid2 - m_entry) * CONTRACT_SIZE * MAIN_LOT
    else:
        m_pnl_arr = (m_entry - sub_ask2) * CONTRACT_SIZE * MAIN_LOT

    tp_idx = np.argmax(m_pnl_arr >= MAIN_TP_USD) if (m_pnl_arr >= MAIN_TP_USD).any() else -1
    sl_idx = np.argmax(m_pnl_arr <= MAIN_SL_USD) if (m_pnl_arr <= MAIN_SL_USD).any() else -1

    if tp_idx >= 0 and (sl_idx < 0 or tp_idx <= sl_idx):
        m_outcome = "tp"; m_exit_idx_local = tp_idx
    elif sl_idx >= 0:
        m_outcome = "sl"; m_exit_idx_local = sl_idx
    else:
        m_outcome = "cap"; m_exit_idx_local = len(m_pnl_arr) - 1 if len(m_pnl_arr) else -1

    if m_exit_idx_local < 0:
        m_pnl_realized = 0.0; m_dur_s = 0.0
    else:
        m_pnl_realized = float(m_pnl_arr[m_exit_idx_local])
        m_dur_s = round((sub_ts2[m_exit_idx_local] - m_entry_ts) / 1000.0, 1)

    trade["main_outcome"] = m_outcome
    trade["main_pnl"] = round(m_pnl_realized, 4)
    trade["main_dur_s"] = m_dur_s
    trade["main_entry"] = round(m_entry, 2)
    trade["total_pnl"] = round(probe_pnl + m_pnl_realized, 4)
    trades.append(trade)

print(f"[SIM] {len(trades)} signals processed", flush=True)

tdf = pd.DataFrame(trades)
tdf.to_csv(OUT_C, index=False)

# Aggregates
def stats(sub: pd.DataFrame, label: str) -> dict:
    if not len(sub):
        return {"label": label, "n": 0}
    wins = sub[sub["total_pnl"] > 0]
    losses = sub[sub["total_pnl"] < 0]
    net = float(sub["total_pnl"].sum())
    gross_w = float(wins["total_pnl"].sum())
    gross_l = float(-losses["total_pnl"].sum())
    pf = round(gross_w / gross_l, 2) if gross_l > 0 else None
    eq = sub["total_pnl"].cumsum()
    dd = float((eq.cummax() - eq).max())
    return {
        "label": label, "n": int(len(sub)),
        "wr": round(len(wins) / len(sub) * 100, 2),
        "wins": int(len(wins)), "losses": int(len(losses)),
        "net_pnl": round(net, 2), "avg_pnl": round(net / len(sub), 3),
        "pf": pf, "max_dd": round(dd, 2),
        "best": round(float(sub["total_pnl"].max()), 2),
        "worst": round(float(sub["total_pnl"].min()), 2),
    }

confirmed = tdf[tdf["probe_outcome"] == "confirm"]
all_stats = stats(tdf, "all_probes")
confirm_stats = stats(confirmed, "main_trades_only")
buy_stats = stats(tdf[tdf["side"] == "buy"], "buy_only")
sell_stats = stats(tdf[tdf["side"] == "sell"], "sell_only")

# Outcome distribution
outcome_dist = tdf["probe_outcome"].value_counts().to_dict() if len(tdf) else {}
main_dist = confirmed["main_outcome"].value_counts().to_dict() if len(confirmed) else {}

result = {
    "ran_at": datetime.now(timezone.utc).isoformat(),
    "data": {
        "ticks": int(len(df)),
        "bars_m5": int(len(bars)),
        "span_start": datetime.fromtimestamp(df["time_msc"].min()/1000, tz=timezone.utc).isoformat(),
        "span_end":   datetime.fromtimestamp(df["time_msc"].max()/1000, tz=timezone.utc).isoformat(),
        "median_spread_pts": int(((df["ask"] - df["bid"]) * 100).median()),
    },
    "config": {
        "PROBE_LOT": PROBE_LOT, "MAIN_LOT": MAIN_LOT,
        "PROBE_CONFIRM_USD": PROBE_CONFIRM_USD, "PROBE_FAIL_USD": PROBE_FAIL_USD,
        "PROBE_TIMEOUT_S": PROBE_TIMEOUT_S,
        "MAIN_TP_USD": MAIN_TP_USD, "MAIN_SL_USD": MAIN_SL_USD,
        "BIG_RATIO": BIG_RATIO,
    },
    "signals": {"buy": n_buy, "sell": n_sell, "total": n_buy + n_sell},
    "probe_outcomes": outcome_dist,
    "main_outcomes": main_dist,
    "all_probes": all_stats,
    "main_trades_only": confirm_stats,
    "by_side_all": {"buy": buy_stats, "sell": sell_stats},
}

OUT_J.write_text(json.dumps(result, indent=2, default=str))

print()
print("===== RESULTS =====")
print(json.dumps(result, indent=2, default=str))
