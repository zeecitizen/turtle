"""backtest_today_vs_live.py — sanity check: does backtest predict today's actual P&L?

Zee asked: "is $1.25M really true? Can we backtest the current EA on today's tick
data to see what it reports as earning today?"

This runs the EXACT live config (broker_sl_usd=50, aggressive params) on today's
tick file ONLY, computes predicted P&L, and compares to actual turtle_fills P&L.
Honest gap analysis exposes any backtest blindspots.
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TODAY_FILE = COMMON / "shano_ticks_2026-06-02.csv"
COST = 0.50
LOTS = 0.05
USD_PER_PRICE = LOTS * 100  # 5

# Current LIVE config (as of post-iteration 3)
RNG_N_MIN = 0.5
RNG_MIN = 0.5
SPR_MAX = 0.50
COOLDOWN_SEC = 10
TRAIL_ARM = 5.0
TRAIL_GB = 15.0
SKIM = 10.0
MAX_LOSS = 10.0
BROKER_SL_USD = 50.0   # JUST CHANGED to 50
BROKER_TP_USD = 50.0
MAX_HOLD_SEC = 2400
M5_LB = 14
CHECK_EVERY = 3
DAILY_DD_STOP = 70.0
LOSS_STREAK_N = 1
LOSS_STREAK_PAUSE = 300

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
    for b in m1: b["t"] = datetime.fromtimestamp(b["m_key"] * 60)
    m5 = []
    for i in range(0, len(m1), 5):
        c = m1[i:i+5]
        if not c: continue
        m5.append({"t_start_ms": c[0]["t_start_ms"], "t_end_ms": c[-1]["t_end_ms"],
                   "o": c[0]["o"], "h": max(b["h"] for b in c),
                   "l": min(b["l"] for b in c), "c": c[-1]["c"],
                   "v": sum(b["v"] for b in c), "t": c[0]["t"]})
    return m1, m5


def m5_trend(m5, ts_ms, lb=M5_LB):
    idx = -1
    for i, b in enumerate(m5):
        if b["t_end_ms"] > ts_ms: break
        idx = i
    if idx < lb: return 0
    W = m5[idx - lb + 1:idx + 1]; h = len(W)//2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def run_day(ticks, m5):
    broker_sl_price = usd_to_price(BROKER_SL_USD)
    broker_tp_price = usd_to_price(BROKER_TP_USD)
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]
    fills = []
    last_fire_ms = {"buy": 0, "sell": 0}
    daily_pnl = 0.0
    consec_losses = 0
    pause_until_ms = 0
    hits = {"sl":0, "tp":0, "skim":0, "cb":0, "trail":0, "eoh":0}
    for k in range(50, len(ticks), CHECK_EVERY):
        t = times[k]
        if asks[k] - bids[k] > SPR_MAX: continue
        if daily_pnl <= -DAILY_DD_STOP: continue
        if t < pause_until_ms: continue
        k_60 = bisect.bisect_left(times, t - 60000)
        k_300 = bisect.bisect_left(times, t - 300000)
        if k_60 >= k - 1: continue
        w60 = mids[k_60:k]
        w300 = mids[k_300:k] if k_300 < k else w60
        rng60 = max(w60) - min(w60)
        if rng60 < RNG_MIN: continue
        range_300 = max(w300) - min(w300) if w300 else rng60
        rng60_norm = rng60 / max(0.10, range_300 / 5.0)
        if rng60_norm < RNG_N_MIN: continue
        td = m5_trend(m5, t)
        if td == 0: continue
        side = "buy" if td > 0 else "sell"
        if t - last_fire_ms[side] < COOLDOWN_SEC * 1000: continue
        entry_px = asks[k] if side == "buy" else bids[k]
        entry_ms = t
        peak = 0.0; armed = False
        exit_pnl = 0
        for j in range(k, len(ticks)):
            t2 = times[j]
            cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
            if cur <= -broker_sl_price: exit_pnl = cur; hits["sl"] += 1; break
            if cur >= broker_tp_price: exit_pnl = cur; hits["tp"] += 1; break
            if cur >= SKIM: exit_pnl = cur; hits["skim"] += 1; break
            if (t2 - entry_ms) > MAX_HOLD_SEC * 1000: exit_pnl = cur; hits["eoh"] += 1; break
            if cur > peak: peak = cur
            if peak >= TRAIL_ARM: armed = True
            if armed and cur <= peak - TRAIL_GB: exit_pnl = cur; hits["trail"] += 1; break
            if cur <= -MAX_LOSS: exit_pnl = cur; hits["cb"] += 1; break
        pnl = exit_pnl - COST
        daily_pnl += pnl
        if pnl > 0:
            consec_losses = 0
        else:
            consec_losses += 1
            if consec_losses >= LOSS_STREAK_N:
                pause_until_ms = t + LOSS_STREAK_PAUSE * 1000
                consec_losses = 0
        fills.append(pnl)
        last_fire_ms[side] = t
    return fills, hits

# Load today's ticks
print(f"Loading {TODAY_FILE.name}...")
ticks = load_ticks(TODAY_FILE)
print(f"  {len(ticks)} ticks (broker timestamps {ticks[0]['t_ms']//1000} → {ticks[-1]['t_ms']//1000})")
print(f"  Time span: {datetime.fromtimestamp(ticks[0]['t_ms']//1000)} → {datetime.fromtimestamp(ticks[-1]['t_ms']//1000)}")
m1, m5 = build_m1_m5(ticks)
print(f"  {len(m1)} M1 bars, {len(m5)} M5 bars")
print()
fills, hits = run_day(ticks, m5)
n = len(fills)
w = sum(1 for f in fills if f > 0)
tot_price = sum(fills)
tot_usd = tot_price * USD_PER_PRICE
print(f"=== BACKTEST PREDICTION (current LIVE config on today's tick data) ===")
print(f"  Fills:  {n}")
print(f"  Wins:   {w}  ({100*w/max(1,n):.1f}%)")
print(f"  Losses: {n-w}")
print(f"  P&L @ 0.05 lots: ${tot_usd:+.2f}")
print(f"  Exit reasons: SL={hits['sl']} TP={hits['tp']} SKIM={hits['skim']} TRAIL={hits['trail']} CB={hits['cb']} EOH={hits['eoh']}")
print()
# Actual live result
print(f"=== ACTUAL LIVE RESULT (from turtle_fills.csv) ===")
ea_pnl = 0; ea_n = 0; ea_w = 0
with open(COMMON / "turtle_fills.csv") as f:
    for line in f:
        p = line.strip().split(",")
        if len(p) < 14 or not p[0].startswith("2026.06.02") or p[3] != "XAUUSD" or p[13] != "Feb11_MED": continue
        try: v = float(p[10])
        except: continue
        ea_pnl += v; ea_n += 1
        if v > 0: ea_w += 1
print(f"  Fills:  {ea_n}")
print(f"  Wins:   {ea_w}  ({100*ea_w/max(1,ea_n):.1f}%)")
print(f"  P&L (USD): ${ea_pnl:+.2f}")
print()
print(f"=== GAP ANALYSIS ===")
print(f"  Backtest predicts: {n} fills, ${tot_usd:+.2f}")
print(f"  Reality:           {ea_n} fills, ${ea_pnl:+.2f}")
fire_ratio = n / max(1, ea_n)
pnl_ratio = tot_usd / max(0.01, ea_pnl) if ea_pnl > 0 else 0
print(f"  Fire-rate ratio: backtest fires {fire_ratio:.1f}x more often than reality")
if pnl_ratio:
    print(f"  P&L ratio: backtest predicts {pnl_ratio:.1f}x more profit")
print()
print(f"Likely reasons for the gap:")
print(f"  1. Backtest uses 24h of data but live EA hasn't been running 24h on aggressive yet")
print(f"     (we switched to aggressive at 21:51 broker, ~2h ago)")
print(f"  2. Real Atmos broker has FOK rejections, real spread variation, latency")
print(f"  3. Backtest's $0.50/trade slippage may be optimistic; real may be $1-2")
print(f"  4. Backtest uses Exness tick data; Atmos may have different micro-behavior")
