"""Generate MQL5-mirror Feb 11 entry timestamps + exit info as JSON, so the
feb11_lab visualizer can highlight the candles where the realistic (one-position-
at-a-time, broker-SL-included) backtest fires.

Outputs: dashboard/claude_trader/feb11_mirror_signals.json
"""
import sys, json, importlib.util
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "mirror", str(Path(__file__).parent / "dry_run_mql5_mirror.py"))
mirror = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirror)

ROOT = Path(__file__).resolve().parent.parent.parent
COMMON = mirror.COMMON
TICK_PATH = COMMON / "shano_ticks_2026-02-11.csv"
OUT = ROOT / "dashboard" / "claude_trader" / "feb11_mirror_signals.json"

ticks = mirror.load_ticks(TICK_PATH)
fills = mirror.run_day_mql_mirror(ticks)

# Each fill: {t, side, entry, exit_pnl_price, exit_pnl_usd, reason, hold_s}
# We need t as UNIX seconds for lightweight-charts compatibility
from datetime import datetime, timezone
UTC = timezone.utc

out = []
# Re-run with timing info — quick re-parse using same logic but capture entry_ms
times = [t["t_ms"] for t in ticks]
bids = [t["bid"] for t in ticks]
asks = [t["ask"] for t in ticks]
mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]
m5_bars = mirror.build_m5_from_ticks(ticks)

# Re-run with timestamp capture
import bisect
last_fire_buy = 0; last_fire_sell = 0
session_pnl_price = 0.0
consec_losses = 0
pause_until_ms = 0
tick_counter = 0
k = 50
trades = []
while k < len(ticks):
    t = times[k]
    dt = datetime.fromtimestamp(t / 1000, tz=UTC)
    bid = bids[k]; ask = asks[k]
    if bid <= 0 or ask <= 0: k += 1; continue
    tick_counter += 1
    if tick_counter % mirror.CHECK_EVERY_TICKS != 0: k += 1; continue
    if not mirror.in_session_utc(dt): k += 1; continue
    if (ask - bid) > mirror.SPREAD_MAX: k += 1; continue
    if session_pnl_price <= -mirror.DAILY_DD_PRICE: k += 1; continue
    if t < pause_until_ms: k += 1; continue
    k_60  = bisect.bisect_left(times, t - 60_000)
    k_300 = bisect.bisect_left(times, t - 300_000)
    if k_60 >= k - 1: k += 1; continue
    w60 = mids[k_60:k]; w300 = mids[k_300:k] if k_300 < k else w60
    rng60 = max(w60) - min(w60)
    if rng60 < mirror.RNG60_MIN: k += 1; continue
    range_300 = (max(w300) - min(w300)) if w300 else rng60
    rng60_norm = rng60 / max(0.10, range_300 / 5.0)
    if rng60_norm < mirror.RNG60_NORM_MIN: k += 1; continue
    td = mirror.m5_trend_mql_mirror(m5_bars, t)
    if td == 0: k += 1; continue
    side = +1 if td > 0 else -1
    last_fire = last_fire_buy if side > 0 else last_fire_sell
    if t - last_fire < mirror.COOLDOWN_SEC * 1000: k += 1; continue

    entry_px = ask if side > 0 else bid
    broker_sl = entry_px - mirror.BROKER_SL_PRICE if side > 0 else entry_px + mirror.BROKER_SL_PRICE
    broker_tp = entry_px + mirror.BROKER_TP_PRICE if side > 0 else entry_px - mirror.BROKER_TP_PRICE
    entry_ms = t; peak = 0.0; armed = False
    exit_pnl_price = 0.0; reason = "?"; exit_ms = entry_ms
    j = k
    while j < len(ticks):
        t2 = times[j]; bid2 = bids[j]; ask2 = asks[j]
        cur = (bid2 - entry_px) if side > 0 else (entry_px - ask2)
        if side > 0:
            if bid2 <= broker_sl: exit_pnl_price = -mirror.BROKER_SL_PRICE; reason = "BROKER_SL"; exit_ms = t2; break
            if bid2 >= broker_tp: exit_pnl_price = mirror.BROKER_TP_PRICE; reason = "BROKER_TP"; exit_ms = t2; break
        else:
            if ask2 >= broker_sl: exit_pnl_price = -mirror.BROKER_SL_PRICE; reason = "BROKER_SL"; exit_ms = t2; break
            if ask2 <= broker_tp: exit_pnl_price = mirror.BROKER_TP_PRICE; reason = "BROKER_TP"; exit_ms = t2; break
        if cur >= mirror.SKIM_CAP: exit_pnl_price = cur; reason = "SKIM"; exit_ms = t2; break
        if cur > peak: peak = cur
        if peak >= mirror.TRAIL_ARM: armed = True
        if armed and cur <= peak - mirror.TRAIL_GIVEBACK: exit_pnl_price = cur; reason = "TRAIL"; exit_ms = t2; break
        if cur <= -mirror.MAX_LOSS: exit_pnl_price = cur; reason = "CB"; exit_ms = t2; break
        if (t2 - entry_ms) > mirror.MAX_HOLD_SEC * 1000: exit_pnl_price = cur; reason = "EOH"; exit_ms = t2; break
        j += 1
    pnl_usd = exit_pnl_price * mirror.USD_PER_PRICE_UNIT - mirror.COST_PER_TRADE
    session_pnl_price += exit_pnl_price
    if exit_pnl_price > 0: consec_losses = 0
    else:
        consec_losses += 1
        if consec_losses >= mirror.LOSS_STREAK_N:
            pause_until_ms = t2 + mirror.LOSS_STREAK_PAUSE * 1000
            consec_losses = 0
    trades.append({
        "entry_ts": entry_ms // 1000,   # lightweight-charts uses unix seconds
        "exit_ts":  exit_ms // 1000,
        "side": "buy" if side > 0 else "sell",
        "entry_px": round(entry_px, 2),
        "pnl_price": round(exit_pnl_price, 2),
        "pnl_usd": round(pnl_usd, 2),
        "reason": reason,
        "hold_s": (exit_ms - entry_ms) // 1000,
    })
    if side > 0: last_fire_buy = t
    else: last_fire_sell = t
    k = max(k + 1, j)

# Summary stats
n = len(trades)
w = sum(1 for t in trades if t["pnl_price"] > 0)
total_usd = sum(t["pnl_usd"] for t in trades)

OUT.write_text(json.dumps({
    "date": "2026-02-11",
    "config": "MQL5-mirror (Feb11TickMedium.mq5 v1.18), 0.05 lots, broker SL $25 / TP $50",
    "n_trades": n,
    "wins": w, "losses": n - w,
    "wr_pct": round(100 * w / max(1, n), 1),
    "total_usd": round(total_usd, 2),
    "trades": trades,
}, indent=2))
print(f"Wrote {n} trades, ${total_usd:+.2f} at 0.05L → {OUT}")
