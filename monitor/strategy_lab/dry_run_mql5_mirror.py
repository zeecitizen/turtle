"""dry_run_mql5_mirror.py - Python port of Feb11TickMedium.mq5 OnTick loop.

If this script's output MATCHES zee_tick_detector_MEDIUM.py on the same ticks,
the MQL5 EA logic is faithful — divergence is broker (latency/spread/exec).
If output DIFFERS, MQL5 has a logic bug Python doesn't.

Ports as faithfully as possible:
  - AddTick → rolling deque keyed by (t, mid, bid, ask)
  - ComputeRanges → looks back over 60s/300s using rolling deque
  - M5TrendDir → walks M5 bars built from ticks; recent half = newest 7 closed
                 bars after the current incomplete bar (matches r[1..7] with
                 ArraySetAsSeries in MQL5)
  - In-session: minute-of-day in UTC (Atmos GMT+0 inputs 90/150/1005/1185)
  - ManageOpen: SKIM → trail-arm → trail-gb → CB → EOH (MQL5 order)
  - Broker-side SL/TP placed at +/- UsdToPriceDist(broker_sl_usd / broker_tp_usd)
    Computed exactly: ticks = usd / (tick_value * lots), price = ticks * tick_size
    XAUUSD: tick_value=1 per 1.0-lot per 0.01-price; at 0.05 lots,
            SL=25 USD -> 5.0 price; TP=50 USD -> 10.0 price.
"""
import sys, glob, bisect
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
UTC = timezone.utc

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
COST_PER_TRADE = 0.20

# MEDIUM variant Inp values (v1.18, Atmos GMT+0)
LOTS                  = 0.05
SESSION1_START        = 90
SESSION1_END          = 150
SESSION2_START        = 1005
SESSION2_END          = 1185
RNG60_NORM_MIN        = 0.8
RNG60_MIN             = 0.8
SPREAD_MAX            = 0.50
COOLDOWN_SEC          = 30
M5_LOOKBACK           = 14
CHECK_EVERY_TICKS     = 10
TRAIL_ARM             = 5.0
TRAIL_GIVEBACK        = 15.0
SKIM_CAP              = 10.0
MAX_LOSS              = 10.0
MAX_HOLD_SEC          = 2400
DAILY_DD_PRICE        = 70.0    # v1.18 input
LOSS_STREAK_N         = 1
LOSS_STREAK_PAUSE     = 300
BROKER_SL_USD         = 25.0
BROKER_TP_USD         = 50.0
TICK_VALUE_PER_LOT    = 1.0     # XAUUSD: $1 per 0.01-price-tick per 1.0-lot
TICK_SIZE             = 0.01

USD_PER_PRICE_UNIT    = LOTS * 100   # 1 price unit at 0.05 lots = $5 USD


def usd_to_price_dist(usd):
    """Mirror of MQL5 UsdToPriceDist (lines 472-479 of Feb11TickMedium.mq5)."""
    ticks = usd / (TICK_VALUE_PER_LOT * LOTS)
    return ticks * TICK_SIZE


# Pre-compute broker SL/TP price distances at deployment lot size
BROKER_SL_PRICE = usd_to_price_dist(BROKER_SL_USD)   # at 0.05L: 25/(1*0.05)*0.01 = 5.0
BROKER_TP_PRICE = usd_to_price_dist(BROKER_TP_USD)   # at 0.05L: 50/(1*0.05)*0.01 = 10.0


def in_session_utc(t_dt):
    """v1.18 source uses MinutesInDay(broker_time). Atmos GMT+0 means broker
    minute-of-day == UTC minute-of-day. Match against Inp values 90/150/1005/1185."""
    m = t_dt.hour * 60 + t_dt.minute
    return (SESSION1_START <= m <= SESSION1_END) or (SESSION2_START <= m <= SESSION2_END)


def load_ticks(path):
    """Same loader as zee_tick_detector_OOS.py."""
    out = []
    with open(path, encoding="utf-8") as f:
        header = next(f).strip()
        is_b = header.startswith("ts_broker")
        for line in f:
            parts = line.strip().split(",")
            if is_b:
                if len(parts) < 4: continue
                try:
                    dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
                    ms = int(parts[1])
                    t_ms = int(dt.replace(tzinfo=UTC).timestamp() * 1000) + ms
                    out.append({"t_ms": t_ms, "bid": float(parts[2]), "ask": float(parts[3])})
                except: continue
            else:
                if len(parts) < 3: continue
                try:
                    date_p, time_p = parts[0].split(" ")
                    hms, ms_str = (time_p.split(".", 1) if "." in time_p else (time_p, "0"))
                    dt = datetime.strptime(date_p + " " + hms, "%Y.%m.%d %H:%M:%S")
                    t_ms = int(dt.replace(tzinfo=UTC).timestamp() * 1000) + int(ms_str)
                    out.append({"t_ms": t_ms, "bid": float(parts[1]), "ask": float(parts[2])})
                except: continue
    return out


def build_m5_from_ticks(ticks):
    """Build M5 OHLC from ticks, indexed by 5-min bucket. Returns list ordered
    chronologically of bars that have CLOSED (i.e. their bucket is fully past)."""
    m5 = {}
    for tk in ticks:
        m_key = tk["t_ms"] // 300000   # 5min bucket
        mid = (tk["bid"] + tk["ask"]) / 2
        if m_key not in m5:
            m5[m_key] = {"key": m_key, "o": mid, "h": mid, "l": mid, "c": mid,
                         "t_start_ms": m_key * 300000, "t_end_ms": (m_key + 1) * 300000 - 1}
        b = m5[m_key]
        if mid > b["h"]: b["h"] = mid
        if mid < b["l"]: b["l"] = mid
        b["c"] = mid
    return [m5[k] for k in sorted(m5.keys())]


def m5_trend_mql_mirror(m5_bars, ts_ms, lookback=M5_LOOKBACK):
    """Mirror of MQL5 M5TrendDir (lines 392-419 of Feb11TickMedium.mq5).

      MqlRates r[]; ArraySetAsSeries(r, true);
      CopyRates(SYMBOL, PERIOD_M5, 0, lb+1, r);  // r[0]=current incomplete, r[1..lb]=closed
      recent half: r[1..h]   (newest closed h bars)
      older  half: r[h+1..lb] (next-older h bars)

    Python equivalent: find LATEST closed bar (t_end_ms < now), call it newest.
    Then recent = newest .. newest-(h-1) (descending), older = (recent end)-1 ..."""
    h = lookback // 2
    # Find the most recent CLOSED bar (t_end_ms < ts_ms)
    idx = -1
    for i, b in enumerate(m5_bars):
        if b["t_end_ms"] < ts_ms:
            idx = i
        else:
            break
    if idx < lookback: return 0
    # MQL5 r[1]..r[h] = newest h closed bars (in series order, newest first).
    # In our chronological list: bars [idx - h + 1 .. idx] are the newest h closed.
    # MQL5 r[h+1]..r[lb] = next-older h bars = bars [idx - lookback + 1 .. idx - h]
    recent = m5_bars[idx - h + 1 : idx + 1]
    older  = m5_bars[idx - lookback + 1 : idx - h + 1]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older);  oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def run_day_mql_mirror(ticks):
    """Replays Feb11TickMedium.mq5 OnTick loop on a day's ticks. Returns
    list of fills with PRICE-unit pnl (multiply by USD_PER_PRICE_UNIT for USD)."""
    times = [t["t_ms"] for t in ticks]
    bids  = [t["bid"]  for t in ticks]
    asks  = [t["ask"]  for t in ticks]
    mids  = [(t["bid"] + t["ask"]) / 2 for t in ticks]

    m5_bars = build_m5_from_ticks(ticks)
    fills = []
    last_fire_buy_ms = 0
    last_fire_sell_ms = 0
    session_pnl_price = 0.0
    consec_losses = 0
    pause_until_ms = 0
    tick_counter = 0

    # No open position state — we handle ManageOpen inline by walking ticks
    # forward from each fire until an exit fires.

    k = 50
    while k < len(ticks):
        t = times[k]
        dt = datetime.fromtimestamp(t / 1000, tz=UTC)

        # ResetIfNewDay — at UTC midnight, zero counters
        # (handled by running per-day; not needed within a single day-of-ticks)

        bid = bids[k]; ask = asks[k]
        if bid <= 0 or ask <= 0:
            k += 1; continue

        # Throttle: every Nth tick
        tick_counter += 1
        if tick_counter % CHECK_EVERY_TICKS != 0:
            k += 1; continue

        if not in_session_utc(dt):
            k += 1; continue
        if (ask - bid) > SPREAD_MAX:
            k += 1; continue
        if session_pnl_price <= -DAILY_DD_PRICE:
            k += 1; continue
        if t < pause_until_ms:
            k += 1; continue

        # rng60 + rng60_norm via rolling tick window
        k_60  = bisect.bisect_left(times, t - 60_000)
        k_300 = bisect.bisect_left(times, t - 300_000)
        if k_60 >= k - 1:
            k += 1; continue
        w60  = mids[k_60:k]
        w300 = mids[k_300:k] if k_300 < k else w60
        rng60 = max(w60) - min(w60)
        if rng60 < RNG60_MIN:
            k += 1; continue
        range_300 = (max(w300) - min(w300)) if w300 else rng60
        rng60_norm = rng60 / max(0.10, range_300 / 5.0)
        if rng60_norm < RNG60_NORM_MIN:
            k += 1; continue

        td = m5_trend_mql_mirror(m5_bars, t)
        if td == 0:
            k += 1; continue

        side = +1 if td > 0 else -1
        last_fire = last_fire_buy_ms if side > 0 else last_fire_sell_ms
        if t - last_fire < COOLDOWN_SEC * 1000:
            k += 1; continue

        # FIRE!
        entry_px = ask if side > 0 else bid
        # Broker SL/TP placed at +/- BROKER_SL_PRICE / BROKER_TP_PRICE
        broker_sl_buy  = entry_px - BROKER_SL_PRICE if side > 0 else entry_px + BROKER_SL_PRICE
        broker_tp_buy  = entry_px + BROKER_TP_PRICE if side > 0 else entry_px - BROKER_TP_PRICE
        entry_ms = t
        peak = 0.0
        armed = False
        exit_pnl_price = 0.0
        exit_reason = "?"
        exit_ms = entry_ms

        j = k
        while j < len(ticks):
            t2 = times[j]
            bid2 = bids[j]; ask2 = asks[j]
            cur = (bid2 - entry_px) if side > 0 else (entry_px - ask2)

            # Broker-side parachute check FIRST (MQL5 broker fills it before EA's OnTick)
            if side > 0:
                if bid2 <= broker_sl_buy:
                    exit_pnl_price = -BROKER_SL_PRICE
                    exit_reason = "BROKER_SL"; exit_ms = t2; break
                if bid2 >= broker_tp_buy:
                    exit_pnl_price = BROKER_TP_PRICE
                    exit_reason = "BROKER_TP"; exit_ms = t2; break
            else:
                if ask2 >= broker_sl_buy:
                    exit_pnl_price = -BROKER_SL_PRICE
                    exit_reason = "BROKER_SL"; exit_ms = t2; break
                if ask2 <= broker_tp_buy:
                    exit_pnl_price = BROKER_TP_PRICE
                    exit_reason = "BROKER_TP"; exit_ms = t2; break

            # EA-managed exits (ManageOpen order in MQL5: SKIM → trail → CB → EOH)
            if cur >= SKIM_CAP:
                exit_pnl_price = cur; exit_reason = "SKIM"; exit_ms = t2; break
            if cur > peak: peak = cur
            if peak >= TRAIL_ARM: armed = True
            if armed and cur <= peak - TRAIL_GIVEBACK:
                exit_pnl_price = cur; exit_reason = "TRAIL"; exit_ms = t2; break
            if cur <= -MAX_LOSS:
                exit_pnl_price = cur; exit_reason = "CB"; exit_ms = t2; break
            if (t2 - entry_ms) > MAX_HOLD_SEC * 1000:
                exit_pnl_price = cur; exit_reason = "EOH"; exit_ms = t2; break
            j += 1

        # Round-trip cost (commissions/spread). MQL5 doesn't subtract this — it's
        # part of broker accounting. We DO subtract to match Python canonical's
        # USD reporting.
        pnl_usd = exit_pnl_price * USD_PER_PRICE_UNIT - COST_PER_TRADE
        session_pnl_price += exit_pnl_price
        if exit_pnl_price > 0:
            consec_losses = 0
        else:
            consec_losses += 1
            if consec_losses >= LOSS_STREAK_N:
                pause_until_ms = t2 + LOSS_STREAK_PAUSE * 1000
                consec_losses = 0

        fills.append({
            "t": datetime.fromtimestamp(entry_ms / 1000, tz=UTC).strftime("%H:%M:%S"),
            "side": "buy" if side > 0 else "sell",
            "entry": round(entry_px, 2),
            "exit_pnl_price": round(exit_pnl_price, 2),
            "exit_pnl_usd": round(pnl_usd, 2),
            "reason": exit_reason,
            "hold_s": (exit_ms - entry_ms) // 1000,
        })
        if side > 0: last_fire_buy_ms = t
        else:         last_fire_sell_ms = t

        # Skip forward to the exit tick so we don't re-fire during the same trade
        k = max(k + 1, j)

    return fills


def summary(fills):
    n = len(fills)
    w = sum(1 for f in fills if f["exit_pnl_price"] > 0)
    l = sum(1 for f in fills if f["exit_pnl_price"] < 0)
    pnl_price = sum(f["exit_pnl_price"] for f in fills)
    pnl_usd = sum(f["exit_pnl_usd"] for f in fills)
    wr = 100 * w / max(1, w + l) if (w + l) else 0
    reasons = {}
    for f in fills:
        reasons[f["reason"]] = reasons.get(f["reason"], 0) + 1
    return n, w, l, wr, pnl_price, pnl_usd, reasons


def main():
    print("=" * 90)
    print("MQL5-MIRROR Python (Feb11TickMedium.mq5 v1.18 logic) on real ticks")
    print(f"  Lots: {LOTS}  Sessions: {SESSION1_START}-{SESSION1_END} + {SESSION2_START}-{SESSION2_END} (UTC minutes)")
    print(f"  Broker SL: ${BROKER_SL_USD} = {BROKER_SL_PRICE} price units at {LOTS}L")
    print(f"  Broker TP: ${BROKER_TP_USD} = {BROKER_TP_PRICE} price units at {LOTS}L")
    print("=" * 90)
    print(f"{'date':<12}{'n':>5}{'W':>4}{'L':>4}{'WR%':>5}{'pnl_price':>11}{'pnl_usd':>10}  reasons")
    total_usd = 0; total_n = 0
    for path in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        day = Path(path).stem.replace("shano_ticks_", "")
        ticks = load_ticks(path)
        if len(ticks) < 1000: continue
        fills = run_day_mql_mirror(ticks)
        n, w, l, wr, pnl_price, pnl_usd, reasons = summary(fills)
        reasons_str = " ".join(f"{k}={v}" for k, v in reasons.items()) or "-"
        print(f"{day:<12}{n:>5}{w:>4}{l:>4}{wr:>4.0f}%{pnl_price:>+11.2f}{pnl_usd:>+10.2f}  {reasons_str}")
        total_n += n
        total_usd += pnl_usd

    print("-" * 90)
    print(f"TOTAL MQL5-MIRROR: {total_n} fills, ${total_usd:+,.2f} (at {LOTS} lots)")
    print()
    print("Compare to:")
    print("  Python canonical MEDIUM (in-window):  +$167,692 at 0.10L = +$83,846 at 0.05L over 27d")
    print("  Live broker reality:                  -$5,917 over 27d (mostly out-of-window)")


if __name__ == "__main__":
    main()
