"""
Cousin's "Filtered Line Break" Strategy Backtest (2026-05-05 night session)

Setup (per Zee's cousin's guidance, with optimized parameters):
  Chart:  3-Line Break (constructed from M1 bars)
  Filters:
    - VWAP (regime)            : price > VWAP for longs, price < VWAP for shorts
    - ADX(7), threshold 25     : require trending market
    - MACD(5,13,8) cross       : momentum trigger
    - BOP (14-SMA smoothed)    : control (above 0 = bulls, below 0 = bears)
    - Raw volume spike         : confirmation
  Entry:    new same-side Line Break block + above filters all aligned
  Stop:     beyond extreme of previous opposing block
  Exit:     MACD cross against position, or end-of-day window

Inputs: tick CSV → aggregated to M1 OHLCV (volume = tick count per minute proxy).

We test on the same 5 days as the relaxation backtest for direct comparison.
"""
import csv
import math
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

TICKS_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
REPORT_PATH = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\COUSIN_STRATEGY_REPORT.md")

# Trade params (matching current EA for fair comparison)
LOTS = 0.30
DOLLAR_PER_PT = LOTS * 100.0   # $30 per 1pt move
SLIP_COST = 1.0                # round-trip slip+spread cost in $
SESSION_END_MINUTES = 16 * 60  # cap each day's trading at 16 hours from session start


# ─── Data loading: tick CSV → M1 bars ──────────────────────────────────────

def load_m1_bars(date_str):
    """Aggregate tick CSV into 1-minute OHLCV bars.
    Volume = tick count for that minute (proxy — broker doesn't report real volume on FX).
    Price = mid (bid+ask)/2.
    """
    f = TICKS_DIR / f"shano_ticks_{date_str}.csv"
    if not f.exists():
        return []
    bars = {}
    with f.open("r", encoding="utf-8", errors="ignore") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            try:
                ts = datetime.strptime(row[0], "%Y.%m.%d %H:%M:%S")
                bid = float(row[2])
                ask = float(row[3])
                mid = (bid + ask) / 2.0
            except (ValueError, IndexError):
                continue
            bar_key = ts.replace(second=0)
            if bar_key not in bars:
                bars[bar_key] = {"o": mid, "h": mid, "l": mid, "c": mid, "v": 1, "ts": bar_key}
            else:
                b = bars[bar_key]
                b["h"] = max(b["h"], mid)
                b["l"] = min(b["l"], mid)
                b["c"] = mid
                b["v"] += 1
    return [bars[k] for k in sorted(bars)]


# ─── Indicators ────────────────────────────────────────────────────────────

def ema(values, period):
    """Exponential moving average. Returns list same length as input (None for warmup bars)."""
    out = [None] * len(values)
    if not values:
        return out
    k = 2.0 / (period + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i-1] * (1 - k)
    return out

def sma(values, period):
    out = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= period:
            s -= values[i - period]
        if i >= period - 1:
            out[i] = s / period
    return out

def macd(closes, fast=5, slow=13, signal=8):
    """MACD line + signal + histogram. Returns (macd_line, signal_line, hist) lists."""
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = [(ef - es) if (ef is not None and es is not None) else None
                 for ef, es in zip(ema_fast, ema_slow)]
    valid_macd = [v for v in macd_line if v is not None]
    if not valid_macd:
        return macd_line, [None]*len(closes), [None]*len(closes)
    # Compute signal as EMA of macd_line where valid
    sig_full = [None] * len(closes)
    sig_local = ema(valid_macd, signal)
    j = 0
    for i, v in enumerate(macd_line):
        if v is not None:
            sig_full[i] = sig_local[j]
            j += 1
    hist = [(m - s) if (m is not None and s is not None) else None
            for m, s in zip(macd_line, sig_full)]
    return macd_line, sig_full, hist

def adx(highs, lows, closes, period=7):
    """ADX (no normalization to leverage volatility). Returns ADX list."""
    n = len(closes)
    if n < 2:
        return [None] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i-1]
        dn = lows[i-1] - lows[i]
        plus_dm[i] = up if (up > dn and up > 0) else 0.0
        minus_dm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = max(highs[i] - lows[i],
                    abs(highs[i] - closes[i-1]),
                    abs(lows[i] - closes[i-1]))
    # Smoothed (Wilder's) sums
    s_pdm = [0.0] * n
    s_mdm = [0.0] * n
    s_tr  = [0.0] * n
    if n > period:
        s_pdm[period] = sum(plus_dm[1:period+1])
        s_mdm[period] = sum(minus_dm[1:period+1])
        s_tr[period]  = sum(tr[1:period+1])
        for i in range(period+1, n):
            s_pdm[i] = s_pdm[i-1] - s_pdm[i-1]/period + plus_dm[i]
            s_mdm[i] = s_mdm[i-1] - s_mdm[i-1]/period + minus_dm[i]
            s_tr[i]  = s_tr[i-1]  - s_tr[i-1]/period  + tr[i]
    out = [None] * n
    dx_series = [None] * n
    for i in range(period, n):
        if s_tr[i] == 0:
            continue
        plus_di  = 100.0 * s_pdm[i] / s_tr[i]
        minus_di = 100.0 * s_mdm[i] / s_tr[i]
        denom = plus_di + minus_di
        if denom == 0:
            continue
        dx_series[i] = 100.0 * abs(plus_di - minus_di) / denom
    # ADX = period-SMA of DX
    valid_dx = [(i, v) for i, v in enumerate(dx_series) if v is not None]
    if len(valid_dx) >= period:
        # Wilder smoothing of DX
        first_idx = valid_dx[period-1][0]
        out[first_idx] = sum(v for _, v in valid_dx[:period]) / period
        prev = out[first_idx]
        for k in range(period, len(valid_dx)):
            i, v = valid_dx[k]
            cur = (prev * (period - 1) + v) / period
            out[i] = cur
            prev = cur
    return out

def bop(opens, highs, lows, closes):
    """Balance of Power per bar."""
    out = []
    for o, h, l, c in zip(opens, highs, lows, closes):
        rng = h - l
        out.append((c - o) / rng if rng > 0 else 0.0)
    return out

def atr(highs, lows, closes, period=14):
    """Average True Range — Wilder's."""
    n = len(closes)
    tr = [0.0] * n
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i],
                    abs(highs[i] - closes[i-1]),
                    abs(lows[i] - closes[i-1]))
    out = [None] * n
    if n > period:
        out[period] = sum(tr[1:period+1]) / period
        for i in range(period+1, n):
            out[i] = (out[i-1] * (period - 1) + tr[i]) / period
    return out


def keltner_bands(closes, atr_vals, ema_period=20, atr_mult=1.5):
    """Returns (upper, middle, lower) bands."""
    mid = ema(closes, ema_period)
    upper = []
    lower = []
    for m, a in zip(mid, atr_vals):
        if m is None or a is None:
            upper.append(None); lower.append(None)
        else:
            upper.append(m + atr_mult * a)
            lower.append(m - atr_mult * a)
    return upper, mid, lower


def macd_v(closes, atr_vals, fast=12, slow=26, signal=9):
    """Volatility-normalized MACD: standard MACD divided by ATR.
    Returns (macd_v, signal_line, hist) — MACD-V is dimensionless after scaling.
    """
    macd_line, sig_line, _ = macd(closes, fast, slow, signal)
    norm_macd = []
    for m, a in zip(macd_line, atr_vals):
        if m is None or a is None or a == 0:
            norm_macd.append(None)
        else:
            norm_macd.append(m / a)
    valid = [v for v in norm_macd if v is not None]
    sig_full = [None] * len(closes)
    if valid:
        sig_local = ema(valid, signal)
        j = 0
        for i, v in enumerate(norm_macd):
            if v is not None:
                sig_full[i] = sig_local[j]
                j += 1
    hist = [(m - s) if (m is not None and s is not None) else None
            for m, s in zip(norm_macd, sig_full)]
    return norm_macd, sig_full, hist


def cvd_proxy(bars):
    """Cumulative Volume Delta proxy from tick-aggregated bars.
    Without aggressor-side flag, we approximate using close vs open within each bar:
      - Bar close > open  → bar was net-buy: contribute +volume
      - Bar close < open  → bar was net-sell: contribute -volume
    This is the standard 'tick rule' approximation when aggressor data isn't available.
    Returns cumulative-running CVD list (resets per session/day).
    """
    out = []
    cum = 0.0
    cur_day = None
    for b in bars:
        d = b["ts"].date()
        if d != cur_day:
            cur_day = d
            cum = 0.0
        sign = 1 if b["c"] > b["o"] else (-1 if b["c"] < b["o"] else 0)
        cum += sign * b["v"]
        out.append(cum)
    return out


def vwap_intraday(bars):
    """VWAP that resets each session (each calendar day here)."""
    out = []
    cum_pv = 0.0
    cum_v = 0.0
    cur_day = None
    for b in bars:
        d = b["ts"].date()
        if d != cur_day:
            cur_day = d
            cum_pv = 0.0
            cum_v = 0.0
        typical = (b["h"] + b["l"] + b["c"]) / 3.0
        cum_pv += typical * b["v"]
        cum_v += b["v"]
        out.append(cum_pv / cum_v if cum_v else b["c"])
    return out


# ─── 3-Line Break block construction ───────────────────────────────────────

def line_break_blocks(bars, n_lines=3):
    """Build 3-Line Break blocks from M1 bars.
    A new block forms only when:
      - Continuation: close > current block's high (bull) → new bull block
                      OR close < current block's low (bear) → new bear block
      - Reversal: close exceeds the extreme of the past `n_lines` opposing blocks.

    Returns list of {start_idx, end_idx, dir, hi, lo} representing each block.
    """
    blocks = []
    cur = None
    for i, b in enumerate(bars):
        c = b["c"]
        if not blocks:
            # Seed with first bar
            cur = {"start_idx": i, "end_idx": i, "dir": "up" if c >= b["o"] else "dn",
                   "hi": b["h"], "lo": b["l"]}
            blocks.append(cur)
            continue
        last = blocks[-1]
        if last["dir"] == "up":
            # Continuation up: close > last["hi"] → extend or new up
            if c > last["hi"]:
                blocks.append({"start_idx": i, "end_idx": i, "dir": "up",
                               "hi": max(last["hi"], b["h"]), "lo": last["hi"]})
                continue
            # Reversal down: close < lowest low of last n_lines up-blocks
            up_blocks = [bl for bl in blocks[-n_lines:] if bl["dir"] == "up"]
            ref_low = min((bl["lo"] for bl in up_blocks), default=last["lo"])
            if c < ref_low:
                blocks.append({"start_idx": i, "end_idx": i, "dir": "dn",
                               "hi": ref_low, "lo": min(ref_low, b["l"])})
        else:  # last dir = dn
            if c < last["lo"]:
                blocks.append({"start_idx": i, "end_idx": i, "dir": "dn",
                               "hi": last["lo"], "lo": min(last["lo"], b["l"])})
                continue
            dn_blocks = [bl for bl in blocks[-n_lines:] if bl["dir"] == "dn"]
            ref_high = max((bl["hi"] for bl in dn_blocks), default=last["hi"])
            if c > ref_high:
                blocks.append({"start_idx": i, "end_idx": i, "dir": "up",
                               "hi": max(ref_high, b["h"]), "lo": ref_high})
    return blocks


# ─── Strategy logic ────────────────────────────────────────────────────────

def detect_signals(bars, *,
                   require_line_break=True,
                   require_volume_spike=True,
                   adx_period=7,
                   adx_threshold=25.0,
                   vol_spike_mult=1.5,
                   require_keltner_break=False,
                   keltner_atr_mult=1.5,
                   use_macd_v=False,
                   require_cvd_align=False):
    """Walk bars, compute indicators, identify entry signals.
    Knobs allow testing relaxations of the cousin's strict rule set.
    """
    if len(bars) < 50:
        return []

    closes = [b["c"] for b in bars]
    opens  = [b["o"] for b in bars]
    highs  = [b["h"] for b in bars]
    lows   = [b["l"] for b in bars]
    vols   = [b["v"] for b in bars]

    atr_vals = atr(highs, lows, closes, period=14)
    if use_macd_v:
        macd_line, sig_line, _ = macd_v(closes, atr_vals, fast=5, slow=13, signal=8)
    else:
        macd_line, sig_line, _ = macd(closes, 5, 13, 8)
    adx_vals = adx(highs, lows, closes, period=adx_period)
    bop_raw = bop(opens, highs, lows, closes)
    bop_smoothed = sma(bop_raw, 14)
    vwap = vwap_intraday(bars)
    vol_avg = sma(vols, 14)
    kel_up, kel_mid, kel_dn = keltner_bands(closes, atr_vals, ema_period=20, atr_mult=keltner_atr_mult)
    cvd = cvd_proxy(bars)
    cvd_sma = sma(cvd, 10)

    # Build line-break blocks; map each bar to block.dir
    blocks = line_break_blocks(bars, n_lines=3)
    bar_to_block = {}
    for blk in blocks:
        bar_to_block[blk["start_idx"]] = blk

    # Entry signals
    signals = []
    last_macd_state = None  # "above" or "below"
    for i in range(20, len(bars) - 1):  # leave room for indicators + at least 1 forward bar
        if (macd_line[i] is None or sig_line[i] is None or adx_vals[i] is None
            or bop_smoothed[i] is None or vol_avg[i] is None):
            continue

        macd_above = macd_line[i] > sig_line[i]
        cross_up   = (last_macd_state == "below" and macd_above)
        cross_dn   = (last_macd_state == "above" and not macd_above)
        last_macd_state = "above" if macd_above else "below"

        # Only signal on a fresh cross (not every bar above/below)
        if not (cross_up or cross_dn):
            continue

        adx_ok = adx_vals[i] >= adx_threshold
        if not adx_ok:
            continue

        vol_spike = vols[i] >= vol_spike_mult * vol_avg[i]
        if require_volume_spike and not vol_spike:
            continue

        # Direction-specific
        # Stop calculation: must be on the opposite side of entry.
        # Use lowest low / highest high of last 5 M1 bars as a robust structural stop,
        # with a minimum distance of 0.5pt and max of 3.0pt to keep risk bounded.
        lookback_lo = min(lows[max(0, i-4):i+1])
        lookback_hi = max(highs[max(0, i-4):i+1])
        entry_price = bars[i+1]["o"]

        if cross_up:
            if not (closes[i] > vwap[i] and bop_smoothed[i] > 0):
                continue
            if require_keltner_break and (kel_up[i] is None or closes[i] <= kel_up[i]):
                continue
            if require_cvd_align and (cvd_sma[i] is None or cvd[i] <= cvd_sma[i]):
                continue
            if require_line_break:
                blk = bar_to_block.get(i)
                if blk and blk["dir"] != "up":
                    continue
            stop = min(lookback_lo, entry_price - 0.5)  # ensure stop < entry
            stop = max(stop, entry_price - 3.0)         # cap distance at 3pt
            signals.append({"idx": i, "dir": "buy", "ts": bars[i]["ts"],
                            "entry": entry_price, "stop_ref": stop})
        elif cross_dn:
            if not (closes[i] < vwap[i] and bop_smoothed[i] < 0):
                continue
            if require_keltner_break and (kel_dn[i] is None or closes[i] >= kel_dn[i]):
                continue
            if require_cvd_align and (cvd_sma[i] is None or cvd[i] >= cvd_sma[i]):
                continue
            if require_line_break:
                blk = bar_to_block.get(i)
                if blk and blk["dir"] != "dn":
                    continue
            stop = max(lookback_hi, entry_price + 0.5)  # ensure stop > entry
            stop = min(stop, entry_price + 3.0)
            signals.append({"idx": i, "dir": "sell", "ts": bars[i]["ts"],
                            "entry": entry_price, "stop_ref": stop})
    return signals, macd_line, sig_line


def simulate_trade(bars, signal, macd_line, sig_line, max_bars=60):
    """Simulate a single trade from entry signal until exit.

    Exit rules (per cousin):
      1. Stop-loss hit (price crosses stop_ref)
      2. MACD reversal (cross back against position)
      3. Time-based: max_bars (60 = 1 hour) cap
    """
    start_idx = signal["idx"] + 1  # entry on next bar
    if start_idx >= len(bars):
        return None
    entry = signal["entry"]
    direction = signal["dir"]
    stop = signal["stop_ref"]

    for offset in range(0, max_bars):
        i = start_idx + offset
        if i >= len(bars):
            i = len(bars) - 1
            exit_price = bars[i]["c"]
            move = (exit_price - entry) if direction == "buy" else (entry - exit_price)
            return {"reason": "eod", "entry": entry, "exit": exit_price,
                    "pnl": move * DOLLAR_PER_PT - SLIP_COST, "bars_held": offset}

        b = bars[i]
        # Stop-loss check (use bar's high/low as worst-case fill)
        if direction == "buy" and b["l"] <= stop:
            return {"reason": "stop", "entry": entry, "exit": stop,
                    "pnl": (stop - entry) * DOLLAR_PER_PT - SLIP_COST, "bars_held": offset}
        if direction == "sell" and b["h"] >= stop:
            return {"reason": "stop", "entry": entry, "exit": stop,
                    "pnl": (entry - stop) * DOLLAR_PER_PT - SLIP_COST, "bars_held": offset}
        # MACD reversal (after at least 2 bars to avoid instant exit on entry-bar wiggles)
        if offset >= 2 and macd_line[i] is not None and sig_line[i] is not None:
            macd_above = macd_line[i] > sig_line[i]
            if (direction == "buy" and not macd_above) or (direction == "sell" and macd_above):
                exit_price = b["c"]
                move = (exit_price - entry) if direction == "buy" else (entry - exit_price)
                return {"reason": "macd_reverse", "entry": entry, "exit": exit_price,
                        "pnl": move * DOLLAR_PER_PT - SLIP_COST, "bars_held": offset}
    # Hit max_bars cap
    i = min(start_idx + max_bars - 1, len(bars) - 1)
    exit_price = bars[i]["c"]
    move = (exit_price - entry) if direction == "buy" else (entry - exit_price)
    return {"reason": "time", "entry": entry, "exit": exit_price,
            "pnl": move * DOLLAR_PER_PT - SLIP_COST, "bars_held": max_bars - 1}


def run_day(date_str, **kwargs):
    bars = load_m1_bars(date_str)
    if len(bars) < 100:
        return {"date": date_str, "no_data": True, "bars": len(bars)}
    result = detect_signals(bars, **kwargs)
    if not result:
        return {"date": date_str, "bars": len(bars), "signals": 0, "trades": []}
    signals, macd_line, sig_line = result

    trades = []
    for s in signals:
        t = simulate_trade(bars, s, macd_line, sig_line, max_bars=60)
        if t:
            t["dir"] = s["dir"]
            t["entry_ts"] = s["ts"].strftime("%H:%M")
            trades.append(t)

    sum_pnl = sum(t["pnl"] for t in trades)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    return {"date": date_str, "bars": len(bars), "signals": len(signals),
            "trades": trades, "sum_pnl": round(sum_pnl, 2),
            "wins": wins, "losses": losses,
            "winrate": round(100.0*wins/max(1,wins+losses), 1)}


def run_variant(label, dates, **kwargs):
    grand_sum = 0.0
    grand_w = grand_l = grand_t = 0
    details = []
    for d in dates:
        r = run_day(d, **kwargs)
        if r.get("no_data"):
            continue
        grand_sum += r.get("sum_pnl", 0)
        grand_w += r.get("wins", 0)
        grand_l += r.get("losses", 0)
        grand_t += len(r.get("trades", []))
        details.append(r)
    wr = round(100*grand_w/max(1, grand_w+grand_l), 1)
    return {"label": label, "trades": grand_t, "wins": grand_w, "losses": grand_l,
            "wr": wr, "sum": round(grand_sum, 2), "details": details}


def main():
    dates = ["2026-04-29", "2026-04-30", "2026-05-01", "2026-05-04", "2026-05-05"]
    print("Cousin's Filtered Line Break Strategy — variant sweep\n")
    variants = [
        # Original strict baseline
        ("Strict (cousin's original spec)", dict(require_line_break=True, require_volume_spike=True, adx_period=7, adx_threshold=25)),
        # Add Keltner regime filter on top of strict
        ("Strict + Keltner break (1.5 ATR)", dict(require_line_break=True, require_volume_spike=True, adx_period=7, adx_threshold=25, require_keltner_break=True, keltner_atr_mult=1.5)),
        ("Strict + Keltner break (1.0 ATR)", dict(require_line_break=True, require_volume_spike=True, adx_period=7, adx_threshold=25, require_keltner_break=True, keltner_atr_mult=1.0)),
        # Replace MACD with MACD-V (volatility-normalized)
        ("Strict + MACD-V (vol-normalized)", dict(require_line_break=True, require_volume_spike=True, adx_period=7, adx_threshold=25, use_macd_v=True)),
        # Add CVD alignment
        ("Strict + CVD alignment", dict(require_line_break=True, require_volume_spike=True, adx_period=7, adx_threshold=25, require_cvd_align=True)),
        # All enhancements together
        ("Strict + Keltner + MACD-V + CVD", dict(require_line_break=True, require_volume_spike=True, adx_period=7, adx_threshold=25, require_keltner_break=True, use_macd_v=True, require_cvd_align=True)),
        # Looser variants for completeness
        ("Loose: indicators only (no LB/vol)", dict(require_line_break=False, require_volume_spike=False, adx_period=7, adx_threshold=25)),
        ("Loose: indicators + Keltner", dict(require_line_break=False, require_volume_spike=False, adx_period=7, adx_threshold=25, require_keltner_break=True, keltner_atr_mult=1.0)),
    ]
    print(f"{'Variant':<45} {'Trades':>7} {'Wins':>5} {'Loss':>5} {'WR%':>6} {'Sum P&L':>10}")
    print("-" * 80)
    all_results = []
    for label, kw in variants:
        r = run_variant(label, dates, **kw)
        all_results.append(r)
        print(f"{label:<45} {r['trades']:>7} {r['wins']:>5} {r['losses']:>5} "
              f"{r['wr']:>5.1f}% ${r['sum']:>+9.2f}")
    # Print best variant's per-day breakdown
    best = max(all_results, key=lambda r: r["sum"])
    print(f"\n=== Best variant: {best['label']} (${best['sum']:+.2f}) ===")
    for d in best["details"]:
        if not d["trades"]:
            continue
        print(f"\n{d['date']}: {len(d['trades'])} trades, WR {d['winrate']}%, P&L ${d['sum_pnl']:+.2f}")
        for t in d["trades"][:8]:
            print(f"  {t['entry_ts']}  {t['dir']:>4}  entry={t['entry']:.2f} exit={t['exit']:.2f} "
                  f"reason={t['reason']:<14} bars={t['bars_held']:>3} pnl=${t['pnl']:>+8.2f}")

    # Decision against Shano-Zee benchmark (today: +$26.93 with 0 mains)
    print(f"\nBaseline Shano-Zee (today only): +$26.93, 96 closes, 52% WR, 0 fearIdeal trips")
    print()
    if best["sum"] > 200 and best["wr"] >= 55 and best["trades"] >= 10:
        print(f"VERDICT: variant '{best['label']}' could WORTH FORWARD-TESTING")
        print(f"         net +${best['sum']:.2f} over 5 days, {best['trades']} trades, {best['wr']}% WR")
    elif best["sum"] > 0:
        print(f"VERDICT: best variant marginally profitable but NOT obviously better than Shano-Zee")
    else:
        print(f"VERDICT: cousin's strategy as-implemented is UNDERPERFORMING vs Shano-Zee on this 5-day sample")

    # Write full report
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        f.write(f"# Cousin's Filtered Line Break Strategy — Variant Sweep\n\n")
        f.write(f"Run: {datetime.now().isoformat(timespec='minutes')}\n\n")
        f.write(f"## Variants tested\n\n")
        f.write(f"| Variant | Trades | Wins | Losses | WR% | Net P&L |\n")
        f.write(f"|---|---|---|---|---|---|\n")
        for r in all_results:
            f.write(f"| {r['label']} | {r['trades']} | {r['wins']} | {r['losses']} | "
                    f"{r['wr']}% | ${r['sum']:+.2f} |\n")
        f.write(f"\n## Per-trade detail (best variant)\n\n")
        f.write(f"### {best['label']}\n\n")
        for d in best["details"]:
            if not d["trades"]:
                continue
            f.write(f"#### {d['date']} (P&L ${d['sum_pnl']:+.2f}, WR {d['winrate']}%)\n\n")
            for t in d["trades"]:
                f.write(f"- {t['entry_ts']} **{t['dir']}** entry={t['entry']:.2f} exit={t['exit']:.2f} "
                        f"({t['reason']}, {t['bars_held']} bars) → ${t['pnl']:+.2f}\n")
            f.write("\n")
        f.write(f"## Comparison to Shano-Zee\n\n")
        f.write(f"Today (2026-05-05) Shano-Zee: +$26.93 / 96 closes / 52% WR / 0 fearIdeal trips.\n\n")
        f.write(f"Best cousin's variant: ${best['sum']:+.2f} / {best['trades']} trades / {best['wr']}% WR over 5 days.\n\n")
        if best["sum"] > 200:
            f.write(f"Cousin's strategy beats Shano-Zee on cumulative basis. Worth forward-testing.\n")
        else:
            f.write(f"Cousin's strategy as-implemented does NOT clearly beat Shano-Zee on this sample.\n")
    print(f"\nReport written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
