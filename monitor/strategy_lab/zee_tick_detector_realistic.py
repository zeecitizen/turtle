"""zee_tick_detector_realistic.py — Gemini Deep Research's state-machine fix.

Same AGGRESSIVE config as zee_tick_detector_OOS.py BUT:
  - in_trade lock (no new fires while an open trade is managed)
  - tick-by-tick state stepping (no nested forward-look for exit)
  - daily_pnl only accrues AFTER trade closes (matches live)
  - NO broker-side SL/TP — pure EA-internal SKIM/TRAIL/CB exits

This is the cleanest answer to: "what is the AGGRESSIVE config's REAL edge,
without the canonical's chronological leak, without the broker parachute?"

Per Gemini's prediction: 10-15 trades/day, +$30 across 27 days at 0.05L
would already be a 'goldmine'. We will see.

Config copied VERBATIM from zee_tick_detector_OOS.py — only run_day() changed.
"""
import sys, glob, bisect
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
UTC = timezone.utc

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
COST = 0.20

# AGGRESSIVE config (Feb11TickTrader.mq5)
RNG_N_MIN = 0.5
RNG_MIN = 0.5
SPR_MAX = 0.50
COOLDOWN_SEC = 10            # unused in state-machine — kept for API parity
TRAIL_ARM = 5.0
TRAIL_GB = 15.0
MAX_LOSS = 10.0
SKIM = 10.0
MAX_HOLD_SEC = 2400
M5_LB = 14
CHECK_EVERY = 3
DAILY_DD_STOP = 100.0
LOSS_STREAK_N = 1
LOSS_STREAK_PAUSE = 300

LOTS = 0.05
USD_PER_PRICE = LOTS * 100


def in_zee_window(t):
    mins = t.hour * 60 + t.minute
    return (90 <= mins <= 150) or (1005 <= mins <= 1185)


def load_ticks(path):
    out = []
    with open(path, encoding="utf-8") as f:
        header = next(f).strip()
        is_b = header.startswith("ts_broker")
        for line in f:
            parts = line.strip().split(",")
            try:
                if is_b:
                    if len(parts) < 4: continue
                    dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
                    ms = int(parts[1])
                    t_ms = int(dt.timestamp() * 1000) + ms
                    out.append({"t_ms": t_ms, "bid": float(parts[2]), "ask": float(parts[3])})
                else:
                    if len(parts) < 3: continue
                    date_p, time_p = parts[0].split(" ")
                    hms, ms_str = (time_p.split(".") if "." in time_p else (time_p, "0"))
                    dt = datetime.strptime(date_p + " " + hms, "%Y.%m.%d %H:%M:%S")
                    t_ms = int(dt.timestamp() * 1000) + int(ms_str)
                    out.append({"t_ms": t_ms, "bid": float(parts[1]), "ask": float(parts[2])})
            except: continue
    return out


def build_m1_m5(ticks):
    m1 = []; cur = None
    for tk in ticks:
        m_key = tk["t_ms"] // 60000
        mid = (tk["bid"] + tk["ask"]) / 2
        if cur is None or m_key != cur["m_key"]:
            if cur: m1.append(cur)
            cur = {"m_key": m_key, "o": mid, "h": mid, "l": mid, "c": mid, "v": 1,
                   "t_start_ms": m_key*60000, "t_end_ms": (m_key+1)*60000-1}
        else:
            cur["h"] = max(cur["h"], mid); cur["l"] = min(cur["l"], mid)
            cur["c"] = mid; cur["v"] += 1
    if cur: m1.append(cur)
    m5 = []
    for i in range(0, len(m1), 5):
        c = m1[i:i+5]
        if not c: continue
        m5.append({"t_start_ms": c[0]["t_start_ms"], "t_end_ms": c[-1]["t_end_ms"],
                   "o": c[0]["o"], "h": max(b["h"] for b in c),
                   "l": min(b["l"] for b in c), "c": c[-1]["c"]})
    return m1, m5


def m5_trend(m5, ts_ms, lb=M5_LB):
    idx = -1
    for i, b in enumerate(m5):
        if b["t_end_ms"] > ts_ms: break
        idx = i
    if idx < lb: return (0, 0.0, 0.0)
    W = m5[idx - lb + 1:idx + 1]; h = len(W)//2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: d = +1
    elif rH < oH and rL < oL: d = -1
    else: d = 0
    closes = [b["c"] for b in W]
    net = abs(closes[-1] - closes[0])
    path = sum(abs(closes[k] - closes[k-1]) for k in range(1, len(closes)))
    er = net / path if path > 1e-9 else 0.0
    abs_move = closes[-1] - closes[0]
    return (d, er, abs_move)


def run_day(ticks, m5):
    """Gemini Deep Research's state-machine version. AGGRESSIVE config.
    No future-peek, no parallel trades, no broker parachute."""
    times = [t["t_ms"] for t in ticks]
    bids  = [t["bid"]  for t in ticks]
    asks  = [t["ask"]  for t in ticks]
    mids  = [(t["bid"] + t["ask"]) / 2 for t in ticks]

    fills = []
    daily_pnl = 0.0
    consec_losses = 0
    pause_until_ms = 0

    in_trade = False
    side = None
    entry_px = 0.0
    entry_ms = 0
    peak = 0.0
    armed = False

    for k in range(50, len(ticks)):
        t = times[k]
        dt = datetime.fromtimestamp(t / 1000)

        # 1. MANAGE OPEN POSITION (every tick while in_trade)
        if in_trade:
            hold_time = t - entry_ms
            cur = (bids[k] - entry_px) if side == "buy" else (entry_px - asks[k])
            exit_pnl = 0
            exit_why = ""
            if hold_time > MAX_HOLD_SEC * 1000:
                exit_pnl = cur; exit_why = "EOH"
            elif cur >= SKIM:
                exit_pnl = cur; exit_why = "SKIM"
            elif cur <= -MAX_LOSS:
                exit_pnl = cur; exit_why = "CB"
            else:
                if cur > peak: peak = cur
                if peak >= TRAIL_ARM: armed = True
                if armed and cur <= peak - TRAIL_GB:
                    exit_pnl = cur; exit_why = "TRAIL"

            if exit_why != "":
                pnl = exit_pnl - COST
                daily_pnl += pnl
                if pnl > 0:
                    consec_losses = 0
                else:
                    consec_losses += 1
                    if consec_losses >= LOSS_STREAK_N:
                        pause_until_ms = t + LOSS_STREAK_PAUSE * 1000
                fills.append({
                    "entry_ts": entry_ms // 1000, "exit_ts": t // 1000,
                    "side": side, "pnl": pnl, "why": exit_why,
                    "peak": peak, "hold_s": hold_time // 1000,
                })
                in_trade = False
            continue   # do not look for new entries this tick

        # 2. ENTRY SCAN (throttled)
        if k % CHECK_EVERY != 0: continue
        if not in_zee_window(dt): continue
        if asks[k] - bids[k] > SPR_MAX: continue
        if daily_pnl <= -DAILY_DD_STOP: continue
        if t < pause_until_ms: continue

        k_60 = bisect.bisect_left(times, t - 60_000)
        k_300 = bisect.bisect_left(times, t - 300_000)
        if k_60 >= k - 1: continue
        w60 = mids[k_60:k]; w300 = mids[k_300:k] if k_300 < k else w60
        rng60 = max(w60) - min(w60)
        if rng60 < RNG_MIN: continue
        range_300 = (max(w300) - min(w300)) if w300 else rng60
        rng60_norm = rng60 / max(0.10, range_300 / 5.0)
        if rng60_norm < RNG_N_MIN: continue

        td, er, abs_move = m5_trend(m5, t)
        if td == 0: continue

        in_trade = True
        side = "buy" if td > 0 else "sell"
        entry_px = asks[k] if side == "buy" else bids[k]
        entry_ms = t
        peak = 0.0
        armed = False

    return fills


def main():
    print("Realistic state-machine (AGGRESSIVE config, no future-peek, no parallel, no broker parachute)")
    print("=" * 95)
    print(f"{'date':<12}{'n':>5}{'W':>4}{'L':>4}{'WR%':>5}{'pnl_price':>11}"
          f"{'pnl_usd':>10}  hold_avg  reasons")
    total_usd = 0; total_n = 0; total_w = 0; total_l = 0
    days_pos = 0; days_neg = 0
    for path in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        day = Path(path).stem.replace("shano_ticks_", "")
        ticks = load_ticks(path)
        if len(ticks) < 1000: continue
        m1, m5 = build_m1_m5(ticks)
        fills = run_day(ticks, m5)
        n = len(fills)
        w = sum(1 for f in fills if f["pnl"] > 0)
        l = sum(1 for f in fills if f["pnl"] < 0)
        pnl_price = sum(f["pnl"] for f in fills)
        pnl_usd = pnl_price * USD_PER_PRICE
        wr = 100 * w / max(1, w + l) if (w + l) else 0
        reasons = {}
        for f in fills: reasons[f["why"]] = reasons.get(f["why"], 0) + 1
        reasons_str = " ".join(f"{k}={v}" for k, v in sorted(reasons.items())) or "-"
        avg_hold = sum(f["hold_s"] for f in fills) / max(1, n)
        print(f"{day:<12}{n:>5}{w:>4}{l:>4}{wr:>4.0f}%{pnl_price:>+11.2f}"
              f"{pnl_usd:>+10.2f}  {avg_hold:>7.0f}s  {reasons_str}")
        total_usd += pnl_usd; total_n += n; total_w += w; total_l += l
        if pnl_usd > 0: days_pos += 1
        elif pnl_usd < 0: days_neg += 1
    wr_tot = 100 * total_w / max(1, total_w + total_l)
    print("-" * 95)
    print(f"TOTAL: {total_n} fills, {wr_tot:.1f}% WR, "
          f"${total_usd:+,.2f} (at {LOTS} lots) over 27 days = ${total_usd/27:+.2f}/day")
    print(f"  winning days: {days_pos} / losing days: {days_neg}")
    print()
    print("Gemini predicted: 10-15 trades/day, +$30 over 27 days at 0.05L = 'goldmine'")


def main_with_metrics():
    """Same as main() but computes Gemini's 5 metrics across all days
    and reports them in one consolidated view."""
    all_fills = []
    daily_pnl_usd = []
    for path in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        day = Path(path).stem.replace("shano_ticks_", "")
        ticks = load_ticks(path)
        if len(ticks) < 1000: continue
        m1, m5 = build_m1_m5(ticks)
        day_fills = run_day(ticks, m5)
        for f in day_fills: f["day"] = day
        all_fills.extend(day_fills)
        day_pnl_usd = sum(f["pnl"] for f in day_fills) * USD_PER_PRICE
        daily_pnl_usd.append((day, day_pnl_usd))

    n = len(all_fills)
    wins   = [f for f in all_fills if f["pnl"] > 0]
    losses = [f for f in all_fills if f["pnl"] < 0]
    gross_profits = sum(f["pnl"] for f in wins) * USD_PER_PRICE
    gross_losses  = abs(sum(f["pnl"] for f in losses)) * USD_PER_PRICE
    total_usd = sum(f["pnl"] for f in all_fills) * USD_PER_PRICE
    wr = 100 * len(wins) / max(1, len(wins) + len(losses))
    pf = gross_profits / max(0.01, gross_losses)
    avg_hold = sum(f["hold_s"] for f in all_fills) / max(1, n)
    median_hold = sorted(f["hold_s"] for f in all_fills)[n // 2] if n else 0

    # Max drawdown — cumulative equity curve, peak-to-trough
    equity = 0; peak_eq = 0; max_dd = 0
    for d, p in daily_pnl_usd:
        equity += p
        if equity > peak_eq: peak_eq = equity
        dd = peak_eq - equity
        if dd > max_dd: max_dd = dd

    print()
    print("=" * 95)
    print("GEMINI'S 5 METRICS — Realistic state-machine, AGGRESSIVE config, 0.05 lots, 27 days")
    print("=" * 95)
    print(f"  1. Trade count:        {n} fills total  ({n/27:.1f} per day average)")
    print(f"     Gemini expected:    10-15 to 40 per day")
    print(f"     Verdict:            {'✓ in band' if 270 <= n <= 1080 else ('⚠ low: less fires than expected' if n < 270 else '⚠ high: still leaking parallels')}")
    print()
    print(f"  2. Win Rate:           {wr:.1f}%")
    print(f"     Gemini expected:    65-78% (≥62% structurally profitable, ≥75% elite)")
    print(f"     Verdict:            {'✓ structurally profitable' if wr >= 62 else '✗ below profitable threshold'}")
    print()
    print(f"  3. Profit Factor:      {pf:.2f}  (gross profits ${gross_profits:.2f} / gross losses ${gross_losses:.2f})")
    print(f"     Gemini expected:    1.25-1.60 (≥1.20 green light, ≤1.0 edge was fake)")
    print(f"     Verdict:            {'✓ tradeable edge' if pf >= 1.20 else ('⚠ marginal' if pf >= 1.0 else '✗ no edge')}")
    print()
    print(f"  4. Avg hold time:      {avg_hold:.0f}s   (median {median_hold}s)")
    print(f"     Gemini expected:    seconds to several minutes")
    print(f"     Verdict:            {'✓ realistic' if avg_hold >= 1 else '✗ same-tick artefact'}")
    print()
    print(f"  5. Max drawdown:       ${max_dd:.2f}  (peak equity ${peak_eq:.2f}, current ${equity:.2f})")
    print(f"     Atmos daily DD:     $400  /  max DD: $800")
    print(f"     Verdict:            {'✓ safe' if max_dd < 800 else ('⚠ near max-loss limit' if max_dd < 1000 else '✗ blows max-loss')}")
    print()
    print(f"  TOTAL: ${total_usd:+,.2f} over 27 days at 0.05 lots = ${total_usd/27:+.2f}/day")
    print(f"  Time to Atmos $500 target: {500/(total_usd/27):.1f} days" if total_usd > 0 else "  Strategy is LOSING — not deployable")


if __name__ == "__main__":
    main()
    main_with_metrics()
