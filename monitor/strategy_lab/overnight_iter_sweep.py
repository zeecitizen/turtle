"""overnight_iter_sweep.py — multi-filter entry quality sweep.

Tests several entry-quality enhancements layered on top of base config.
Each variant: 24h trading, parallel cap=4, current exits (broker SL $25, TP $50, trail 5/15).

Goal: find filter combination that produces 70%+ WR (matching Zee's manual).
Test on TODAY's tick data + Feb 11 + 1 other day for cross-validation.

Variants:
  A: baseline (current LIVE config)
  B: + body/range filter (require M1 entry-bar body >= 0.55 of range)
  C: + M15 trend confirmation (M5 and M15 must agree)
  D: + body filter AND M15 confirmation
  E: + tighter rng60 ABSOLUTE ($1.0 minimum, not just relative)
  F: + sustained rng60_norm (must be >= 1.2 for 3+ consecutive seconds)
  G: + all of the above (most selective)
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TEST_FILES = [
    COMMON / "shano_ticks_2026-06-02.csv",
    COMMON / "shano_ticks_2026-02-11.csv",
    COMMON / "shano_ticks_2026-06-01.csv",
]

COST = 0.50
LOTS = 0.05
USD_PER_PRICE = LOTS * 100
RNG_MIN_BASE = 0.5
SPR_MAX = 0.50
COOLDOWN_SEC = 10
M5_LB = 14
CHECK_EVERY = 3
MAX_HOLD_SEC = 2400
MAX_CONCURRENT = 4
TRAIL_ARM = 5.0
TRAIL_GB = 15.0
SKIM = 10.0
MAX_LOSS = 10.0
BROKER_SL_USD = 25.0
BROKER_TP_USD = 50.0

def usd_to_price(usd): return usd / USD_PER_PRICE

def load_ticks(path):
    if not path.exists(): return []
    out = []
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 4: continue
            try:
                dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
                ms = int(parts[1])
                t_ms = int(dt.timestamp() * 1000) + ms
                out.append({"t_ms": t_ms, "bid": float(parts[2]), "ask": float(parts[3])})
            except: continue
    return out

def build_m1(ticks):
    m1 = {}
    for tk in ticks:
        m_key = tk["t_ms"] // 60000
        mid = (tk["bid"] + tk["ask"]) / 2
        if m_key not in m1:
            m1[m_key] = {"o": mid, "h": mid, "l": mid, "c": mid, "v": 1, "t_start_ms": m_key*60000}
        b = m1[m_key]
        b["h"] = max(b["h"], mid); b["l"] = min(b["l"], mid); b["c"] = mid; b["v"] += 1
    return [m1[k] for k in sorted(m1.keys())]

def build_mn_from_m1(m1_list, n):
    """Aggregate M1 into M-N bars (M5 if n=5, M15 if n=15)."""
    out = []
    cur = None
    for b in m1_list:
        m_key = b["t_start_ms"] // (n * 60000)
        if cur is None or cur["m_key"] != m_key:
            if cur: out.append(cur)
            cur = {"m_key": m_key, "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b["v"],
                   "t_start_ms": m_key * n * 60000}
        else:
            cur["h"] = max(cur["h"], b["h"]); cur["l"] = min(cur["l"], b["l"])
            cur["c"] = b["c"]; cur["v"] += b["v"]
    if cur: out.append(cur)
    return out

def hh_hl_trend(bars, ts_ms, lb=14):
    idx = -1
    period_ms = (bars[1]["t_start_ms"] - bars[0]["t_start_ms"]) if len(bars) > 1 else 300000
    for i, b in enumerate(bars):
        if b["t_start_ms"] + period_ms > ts_ms: break
        idx = i
    if idx < lb: return 0
    W = bars[idx - lb + 1: idx + 1]
    h = len(W) // 2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0

def m1_at(m1_list, ts_ms):
    """Return the M1 bar containing ts_ms."""
    idx = -1
    for i, b in enumerate(m1_list):
        if b["t_start_ms"] + 60000 > ts_ms: break
        idx = i
    return m1_list[idx] if idx >= 0 else None

def run_variant(ticks, m1_list, m5_list, m15_list, variant):
    """Run backtest with the variant's filter rules."""
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]
    positions = []
    fills = []
    last_fire_ms = {"buy": 0, "sell": 0}
    daily_pnl_usd = 0.0
    pause_until_ms = 0
    consec_losses = 0
    broker_sl_price = usd_to_price(BROKER_SL_USD)
    broker_tp_price = usd_to_price(BROKER_TP_USD)

    for k in range(len(ticks)):
        t = times[k]; bid = bids[k]; ask = asks[k]
        # Manage positions
        i = 0
        while i < len(positions):
            p = positions[i]
            cur = (bid - p["entry"]) if p["side"] > 0 else (p["entry"] - ask)
            close_reason = None
            if cur <= -broker_sl_price: close_reason = "BSL"
            elif cur >= broker_tp_price: close_reason = "BTP"
            elif cur >= SKIM: close_reason = "SKIM"
            elif (t - p["open_ms"]) > MAX_HOLD_SEC * 1000: close_reason = "EOH"
            else:
                if cur > p["peak"]: p["peak"] = cur
                if p["peak"] >= TRAIL_ARM: p["armed"] = True
                if p["armed"] and cur <= p["peak"] - TRAIL_GB: close_reason = "TRAIL"
                elif cur <= -MAX_LOSS: close_reason = "CB"
            if close_reason:
                pnl_usd = (cur - COST / USD_PER_PRICE) * USD_PER_PRICE
                daily_pnl_usd += pnl_usd
                fills.append({"pnl_usd": pnl_usd})
                if pnl_usd > 0: consec_losses = 0
                else:
                    consec_losses += 1
                    if consec_losses >= 5:
                        pause_until_ms = t + 300 * 1000
                        consec_losses = 0
                positions.pop(i)
            else: i += 1
        if daily_pnl_usd <= -400.0: continue
        if k % CHECK_EVERY != 0: continue
        if t < pause_until_ms: continue
        if (ask - bid) > SPR_MAX: continue
        if len(positions) >= MAX_CONCURRENT: continue
        # Range checks
        k_60 = bisect.bisect_left(times, t - 60000)
        k_300 = bisect.bisect_left(times, t - 300000)
        if k_60 >= k - 1: continue
        w60 = mids[k_60:k]
        w300 = mids[k_300:k] if k_300 < k else w60
        rng60 = max(w60) - min(w60)
        rng_min = variant.get("rng60_abs", RNG_MIN_BASE)
        if rng60 < rng_min: continue
        range_300 = max(w300) - min(w300) if w300 else rng60
        rng60_norm = rng60 / max(0.10, range_300 / 5.0)
        if rng60_norm < variant.get("rng60_norm", 0.5): continue
        # M5 trend
        td5 = hh_hl_trend(m5_list, t)
        if td5 == 0: continue
        # M15 confirmation (variants C, D, G)
        if variant.get("require_m15", False):
            td15 = hh_hl_trend(m15_list, t)
            if td15 != td5: continue
        # Body/range filter (variants B, D, G)
        if variant.get("body_min", 0) > 0:
            bar = m1_at(m1_list, t)
            if bar is None: continue
            rng = bar["h"] - bar["l"]
            body = abs(bar["c"] - bar["o"])
            if rng <= 0 or body / rng < variant["body_min"]: continue
        # Cooldown
        side = "buy" if td5 > 0 else "sell"
        if t - last_fire_ms[side] < COOLDOWN_SEC * 1000: continue
        entry_px = ask if td5 > 0 else bid
        positions.append({"side": td5, "entry": entry_px, "open_ms": t, "peak": 0, "armed": False})
        last_fire_ms[side] = t

    if positions:
        last_bid = bids[-1]; last_ask = asks[-1]
        for p in positions:
            cur = (last_bid - p["entry"]) if p["side"] > 0 else (p["entry"] - last_ask)
            pnl_usd = cur * USD_PER_PRICE - COST
            daily_pnl_usd += pnl_usd
            fills.append({"pnl_usd": pnl_usd})

    n = len(fills)
    wins = sum(1 for f in fills if f["pnl_usd"] > 0)
    return {"n": n, "wins": wins, "wr": 100*wins/max(1,n), "pnl_usd": daily_pnl_usd}


VARIANTS = {
    "A_baseline": {},
    "B_body55": {"body_min": 0.55},
    "C_m15": {"require_m15": True},
    "D_body+m15": {"body_min": 0.55, "require_m15": True},
    "E_rng1": {"rng60_abs": 1.0},
    "F_normGate12": {"rng60_norm": 1.20},
    "G_all": {"body_min": 0.55, "require_m15": True, "rng60_abs": 1.0, "rng60_norm": 1.20},
    "H_strict": {"body_min": 0.70, "require_m15": True, "rng60_abs": 1.5, "rng60_norm": 1.50},
}

# Run each variant on each day, aggregate
results = {}
day_labels = []
for path in TEST_FILES:
    if not path.exists(): continue
    label = path.stem.replace("shano_ticks_", "")
    day_labels.append(label)
    print(f"Loading {path.name}...", end=" ", flush=True)
    ticks = load_ticks(path)
    m1 = build_m1(ticks)
    m5 = build_mn_from_m1(m1, 5)
    m15 = build_mn_from_m1(m1, 15)
    print(f"{len(ticks)} ticks, {len(m1)} M1, {len(m5)} M5, {len(m15)} M15")
    for name, cfg in VARIANTS.items():
        r = run_variant(ticks, m1, m5, m15, cfg)
        if name not in results: results[name] = {}
        results[name][label] = r

print()
print(f"{'Variant':<15} ", end="")
for label in day_labels: print(f"{label:>30}", end="")
print(f"{'TOTAL':>14}")
print("-" * (15 + 30*len(day_labels) + 14))
for name in VARIANTS:
    print(f"{name:<15} ", end="")
    total_n = 0; total_wins = 0; total_pnl = 0
    for label in day_labels:
        r = results[name].get(label, {})
        n, w, wr, p = r.get("n",0), r.get("wins",0), r.get("wr",0), r.get("pnl_usd",0)
        total_n += n; total_wins += w; total_pnl += p
        print(f"  n={n:>3} WR={wr:>4.1f}% ${p:>+7.0f}", end="  ")
    total_wr = 100*total_wins/max(1,total_n)
    print(f"  n={total_n:>3} WR={total_wr:>4.1f}% ${total_pnl:>+6.0f}")
