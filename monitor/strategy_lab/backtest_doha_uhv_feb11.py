"""backtest_doha_uhv_feb11.py — sanity check DohaUHV.mq5 logic against Feb 11 reality.

Zee's actual Feb 11: 70 trades, 65W/4L (94% WR), +$835 USD.
But only ~56% of his setups were pure UHV Breakout (the rest were Sweep/NSND/Momentum/Tape).

So the EXPECTED backtest result for DohaUHV (which implements UHV only):
- Should fire a SUBSET of Zee's 70 trades (probably 30-40 trades)
- Should preserve a high WR (since UHV bars in retracements signal real exhaustion)
- Expected P&L: maybe 30-50% of $835 = ~$250-$400 IF the logic correctly matches Zee's UHV calls
- If we get ZERO or very few fires → the UHV-detection threshold is too strict
- If we get LOTS of fires (more than Zee did) → too loose, capturing noise
- If WR is BAD → the rng60_norm gate is missing or UHV-detection is misfiring

This backtest models a SINGLE-POSITION EA (one trade at a time) — matches DohaUHV
architecture exactly. Uses tick-count per M1 bar as volume proxy.
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
FEB11 = COMMON / "shano_ticks_2026-02-11.csv"
COST = 0.50
LOTS = 0.10
USD_PER_PRICE = LOTS * 100  # 10 at 0.10 lots

# DohaUHV params (current EA defaults)
UHV_VOL_MULT     = 2.0
UHV_LOOKBACK     = 30
UHV_MIN_BODY     = 0.30
UHV_VALID_SEC    = 600
BREAKOUT_BUFFER  = 0.05
SPREAD_MAX       = 0.50
COOLDOWN_SEC     = 20
TARGET_HOLD_SEC  = 90
MAX_HOLD_SEC     = 600
QUICK_PROFIT_USD = 5.0
TRAIL_ARM        = 5.0
TRAIL_GB         = 5.0
SKIM             = 15.0
MAX_LOSS         = 10.0
BROKER_SL_USD    = 50.0
BROKER_TP_USD    = 100.0
DAILY_DD         = 30.0   # in price units = $300 at 0.10 lots
LOSS_STREAK_N    = 1
LOSS_STREAK_PAUSE = 300

# Universal Feb 11 gate
RNG60_NORM_MIN   = 1.20

def usd_to_price(usd): return usd / USD_PER_PRICE


def load_ticks(path):
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
                    t_ms = int(dt.timestamp() * 1000) + ms
                    out.append({"t_ms": t_ms, "bid": float(parts[2]), "ask": float(parts[3])})
                except: continue
            else:
                if len(parts) < 3: continue
                try:
                    t_str = parts[0]
                    date_p, time_p = t_str.split(" ")
                    hms, ms_str = time_p.split(".") if "." in time_p else (time_p, "0")
                    dt = datetime.strptime(date_p + " " + hms, "%Y.%m.%d %H:%M:%S")
                    t_ms = int(dt.timestamp() * 1000) + int(ms_str)
                    out.append({"t_ms": t_ms, "bid": float(parts[1]), "ask": float(parts[2])})
                except: continue
    return out


def build_m1_bars(ticks):
    """Build M1 OHLCV bars from ticks. Volume = tick count (proxy)."""
    m1 = []; cur = None
    for tk in ticks:
        m_key = tk["t_ms"] // 60000
        mid = (tk["bid"] + tk["ask"]) / 2
        if cur is None or m_key != cur["m_key"]:
            if cur: m1.append(cur)
            cur = {"m_key": m_key, "o": mid, "h": mid, "l": mid, "c": mid, "v": 1,
                   "t_start_ms": m_key*60000, "t_end_ms": (m_key+1)*60000-1,
                   "dt": datetime.fromtimestamp(m_key*60)}
        else:
            cur["h"] = max(cur["h"], mid)
            cur["l"] = min(cur["l"], mid)
            cur["c"] = mid
            cur["v"] += 1
    if cur: m1.append(cur)
    return m1


def compute_rng60_norm(m1_bars, bar_idx):
    """Approximate rng60_norm from M1 bars at index bar_idx.
    rng60 ≈ just-closed bar's range, range_300 ≈ range over last 5 bars."""
    if bar_idx < 5: return 0
    rng60 = m1_bars[bar_idx]["h"] - m1_bars[bar_idx]["l"]
    if rng60 <= 0: return 0
    hi = max(b["h"] for b in m1_bars[bar_idx-4:bar_idx+1])
    lo = min(b["l"] for b in m1_bars[bar_idx-4:bar_idx+1])
    range_300 = hi - lo
    denom = max(0.10, range_300 / 5.0)
    return rng60 / denom


def detect_uhv(m1_bars, bar_idx):
    """Returns +1 (bullish UHV), -1 (bearish UHV), or 0 (not UHV).
    Matches MQL5 DetectUhv() logic."""
    if bar_idx < UHV_LOOKBACK + 1: return 0
    bar = m1_bars[bar_idx]
    vol_now = bar["v"]
    if vol_now <= 0: return 0
    vols = sorted([m1_bars[bar_idx - i]["v"] for i in range(1, UHV_LOOKBACK + 1)])
    median = vols[len(vols)//2]
    if median <= 0: return 0
    if vol_now / median < UHV_VOL_MULT: return 0
    body = abs(bar["c"] - bar["o"])
    if body < UHV_MIN_BODY: return 0
    return 1 if bar["c"] > bar["o"] else -1


def run_doha_backtest(ticks, m1_bars):
    """Single-position EA. Each tick: manage open position OR check UHV state machine on M1 bar close."""
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    fills = []
    daily_pnl = 0.0
    consec_losses = 0
    pause_until_ms = 0
    last_fire_ms = {"buy": 0, "sell": 0}

    # UHV state machine
    state = "WATCHING"
    uhv = {"bar_idx": -1, "h": 0, "l": 0, "vol": 0, "side": 0}
    last_m1_idx_processed = -1  # last M1 bar we've checked for UHV/breakout

    open_pos = None  # {"side":+1/-1, "entry":px, "open_ms":t_ms, "peak":0, "armed":False, "entered_bar_idx":idx}

    broker_sl_price = usd_to_price(BROKER_SL_USD)
    broker_tp_price = usd_to_price(BROKER_TP_USD)
    skim_price = SKIM
    cb_price = MAX_LOSS

    log = []  # human-readable trace

    for k in range(len(ticks)):
        t = times[k]; bid = bids[k]; ask = asks[k]
        spread = ask - bid

        # 1. Manage open position
        if open_pos:
            cur = (bid - open_pos["entry"]) if open_pos["side"] > 0 else (open_pos["entry"] - ask)
            cur_usd = cur * USD_PER_PRICE
            hold_sec = (t - open_pos["open_ms"]) / 1000

            # Exit logic
            close_reason = None
            # Broker SL
            if cur <= -broker_sl_price: close_reason = "BSL"
            # Broker TP
            elif cur >= broker_tp_price: close_reason = "BTP"
            # SKIM
            elif cur >= skim_price: close_reason = "SKIM"
            # Quick profit (after target hold time)
            elif hold_sec >= TARGET_HOLD_SEC and cur_usd >= QUICK_PROFIT_USD: close_reason = "QUICK"
            # Trail
            elif open_pos["armed"] and cur <= open_pos["peak"] - TRAIL_GB: close_reason = "TRAIL"
            # CB
            elif cur <= -cb_price: close_reason = "CB"
            # EOH
            elif hold_sec > MAX_HOLD_SEC: close_reason = "EOH"

            if close_reason:
                pnl = cur - COST / USD_PER_PRICE   # subtract cost in price units
                pnl_usd = pnl * USD_PER_PRICE
                daily_pnl += pnl
                fills.append({"open_t": open_pos["open_ms"], "close_t": t, "side": open_pos["side"],
                              "entry": open_pos["entry"], "pnl": pnl, "pnl_usd": pnl_usd,
                              "reason": close_reason, "hold_sec": hold_sec})
                if pnl > 0:
                    consec_losses = 0
                else:
                    consec_losses += 1
                    if consec_losses >= LOSS_STREAK_N:
                        pause_until_ms = t + LOSS_STREAK_PAUSE * 1000
                        consec_losses = 0
                log.append(f"  {datetime.fromtimestamp(t/1000)} CLOSE {close_reason} side={open_pos['side']:+d} pnl_usd={pnl_usd:+.2f} hold={hold_sec:.0f}s")
                open_pos = None
            else:
                # Update peak / arm trail
                if cur > open_pos["peak"]: open_pos["peak"] = cur
                if open_pos["peak"] >= TRAIL_ARM: open_pos["armed"] = True
            continue

        # 2. Global filters
        if spread > SPREAD_MAX: continue
        if daily_pnl <= -DAILY_DD: continue
        if t < pause_until_ms: continue

        # 3. New M1 bar close detection
        bar_idx = -1
        for i, b in enumerate(m1_bars):
            if b["t_end_ms"] >= t: break
            bar_idx = i
        if bar_idx <= last_m1_idx_processed: continue
        last_m1_idx_processed = bar_idx
        if bar_idx < UHV_LOOKBACK + 1: continue

        # 4. State machine on new bar
        if state == "WATCHING":
            u = detect_uhv(m1_bars, bar_idx)
            if u != 0:
                bar = m1_bars[bar_idx]
                state = "UHV_FOUND"
                uhv = {"bar_idx": bar_idx, "h": bar["h"], "l": bar["l"], "vol": bar["v"], "side": u,
                       "found_at_ms": bar["t_end_ms"]}
                log.append(f"  {datetime.fromtimestamp(t/1000)} UHV detected: {'BULL' if u>0 else 'BEAR'} hi={bar['h']:.3f} lo={bar['l']:.3f} vol={bar['v']}")

        elif state == "UHV_FOUND":
            # Check UHV expiry
            if (t - uhv["found_at_ms"]) > UHV_VALID_SEC * 1000:
                log.append(f"  {datetime.fromtimestamp(t/1000)} UHV expired")
                state = "WATCHING"
                continue
            # Breakout check on the just-closed bar (NOT the UHV bar itself)
            if bar_idx <= uhv["bar_idx"]: continue   # need at least 1 bar after UHV
            brk_bar = m1_bars[bar_idx]
            # Must have LOWER volume than UHV bar (divergence)
            if brk_bar["v"] >= uhv["vol"]: continue
            # Direction check
            brk_side = 0
            if uhv["side"] > 0 and brk_bar["c"] > uhv["h"] + BREAKOUT_BUFFER: brk_side = +1
            elif uhv["side"] < 0 and brk_bar["c"] < uhv["l"] - BREAKOUT_BUFFER: brk_side = -1
            if brk_side == 0: continue
            # Universal gate
            rng60n = compute_rng60_norm(m1_bars, bar_idx)
            if rng60n < RNG60_NORM_MIN:
                log.append(f"  {datetime.fromtimestamp(t/1000)} breakout but rng60_norm={rng60n:.2f} < {RNG60_NORM_MIN}, skip")
                continue
            # Cooldown
            side_key = "buy" if brk_side > 0 else "sell"
            if t - last_fire_ms[side_key] < COOLDOWN_SEC * 1000: continue
            # FIRE
            entry_px = ask if brk_side > 0 else bid
            open_pos = {"side": brk_side, "entry": entry_px, "open_ms": t,
                        "peak": 0, "armed": False, "entered_bar_idx": bar_idx}
            last_fire_ms[side_key] = t
            state = "WATCHING"
            log.append(f"  {datetime.fromtimestamp(t/1000)} OPEN {'BUY' if brk_side>0 else 'SELL'} @ {entry_px:.3f} rng60n={rng60n:.2f}")

    return fills, log


print("=== DohaUHV backtest on Feb 11 tick data ===")
print(f"  Lots: {LOTS}  | USD per price unit: ${USD_PER_PRICE}")
print(f"  UHV: vol >= {UHV_VOL_MULT}× median of last {UHV_LOOKBACK} bars, body >= ${UHV_MIN_BODY}")
print(f"  Breakout: next-bar close beyond UHV high/low + ${BREAKOUT_BUFFER} buffer, with LOWER volume")
print(f"  Universal gate: rng60_norm >= {RNG60_NORM_MIN}")
print(f"  Exits: SKIM ${SKIM}p, CB -${MAX_LOSS}p, broker SL ${BROKER_SL_USD}USD, broker TP ${BROKER_TP_USD}USD,")
print(f"         quick-profit @ +${QUICK_PROFIT_USD} after {TARGET_HOLD_SEC}s, EOH {MAX_HOLD_SEC}s")
print()
ticks = load_ticks(FEB11)
print(f"Loaded {len(ticks)} ticks from {FEB11.name}")
m1_bars = build_m1_bars(ticks)
print(f"Built {len(m1_bars)} M1 bars")
print()
fills, log = run_doha_backtest(ticks, m1_bars)
n = len(fills)
wins = sum(1 for f in fills if f["pnl"] > 0)
losses = n - wins
tot_usd = sum(f["pnl_usd"] for f in fills)
print(f"=== Results ===")
print(f"  Trades: {n}  ({wins}W / {losses}L = {100*wins/max(1,n):.1f}% WR)")
print(f"  Total P&L: ${tot_usd:+.2f}")
print(f"  Avg per trade: ${tot_usd/max(1,n):+.2f}")
if fills:
    holds = [f["hold_sec"] for f in fills]
    print(f"  Hold time: min={min(holds):.0f}s  median={sorted(holds)[n//2]:.0f}s  max={max(holds):.0f}s")
    print(f"  Exit reasons: " + ", ".join(f"{r}={sum(1 for f in fills if f['reason']==r)}" for r in set(f['reason'] for f in fills)))
print()
print(f"=== Compare to Zee's actual Feb 11 ===")
print(f"  Actual: 70 trades, 65W/4L (94% WR), +$835 USD")
print(f"  Note: Zee used 5 strategies; DohaUHV implements ONLY UHV Breakout (56% of his setups)")
print(f"  Theoretical best-case capture: ~$835 × 0.56 = ~$468")
print()
if fills:
    print(f"=== Trade-by-trade log (first 30) ===")
    for line in log[:60]:
        print(line)
else:
    print("No trades fired. UHV-detection threshold may be too strict, OR rng60_norm gate too high.")
