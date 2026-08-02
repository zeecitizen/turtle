"""zee_feb11_REAL.py — THE real backtest. Blueberry Demo Feb 11 ticks (448,294 ticks),
v1's loose multi-pattern detector, Zee-style tick-level peak-trail exit.

Target: 65W/4L (94% WR), NET +$835, avgW +$12.93, avgL -$1.32
"""
import csv, sys, bisect
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter, defaultdict
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICKS = COMMON / "shano_ticks_2026-02-11.csv"
M1_CSV = COMMON / "rev_eng_m1.csv"

# === EA params (Zee-style tick exits) ===
TREND_LB = 30; RETRO = 12
ER_MIN_FOR_MOM = 0.10
TRAIL_ARM = 1.0          # arm trail at +$1.0 MFE
TRAIL_GIVEBACK = 0.30    # tight giveback (tick-precise)
SKIM_CAP = 15.0
SCRATCH_SEC = 90         # 1.5 min no-profit → scratch
SCRATCH_AT = 0.0
MAX_LOSS = 2.0           # CB at -$2 (matches Zee's worst -$1.60)
MAX_HOLD_SEC = 600
COST = 0.20

# Cooldown: don't fire same side within N seconds
COOLDOWN_SEC = 30

print("Loading Feb 11 ticks (Blueberry-Demo)...")
ticks = []
with open(TICKS, encoding="utf-8") as f:
    next(f)  # header
    for line in f:
        parts = line.strip().split(",")
        if len(parts) < 3: continue
        try:
            # 2026.02.11 01:00:09.108
            t_str = parts[0]
            date_p, time_p = t_str.split(" ")
            hms, ms_str = time_p.split(".") if "." in time_p else (time_p, "0")
            dt = datetime.strptime(date_p + " " + hms, "%Y.%m.%d %H:%M:%S")
            t_ms = int(dt.timestamp() * 1000) + int(ms_str)
            ticks.append({"t_ms": t_ms, "bid": float(parts[1]), "ask": float(parts[2])})
        except (ValueError, IndexError):
            continue
print(f"  {len(ticks):,} ticks loaded")

# Build M1 bars from ticks (so volume is tick count = native)
print("Building M1 bars from ticks...")
m1 = []
cur = None
for tk in ticks:
    m_key = tk["t_ms"] // 60000
    mid = (tk["bid"] + tk["ask"]) / 2
    if cur is None or m_key != cur["m_key"]:
        if cur: m1.append(cur)
        cur = {"m_key": m_key, "o": mid, "h": mid, "l": mid, "c": mid, "v": 1,
               "t_start_ms": m_key * 60000, "t_end_ms": (m_key + 1) * 60000 - 1}
    else:
        cur["h"] = max(cur["h"], mid); cur["l"] = min(cur["l"], mid)
        cur["c"] = mid; cur["v"] += 1
if cur: m1.append(cur)
for b in m1:
    b["t"] = datetime.fromtimestamp(b["t_start_ms"] / 1000)
print(f"  {len(m1)} M1 bars built\n")

N = len(m1)
tick_times = [t["t_ms"] for t in ticks]


def trend_dir(i):
    if i < TREND_LB: return 0
    W = m1[i - TREND_LB:i]
    h = TREND_LB // 2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def er_at(i):
    if i < TREND_LB: return 0.0
    closes = [b["c"] for b in m1[i - TREND_LB:i + 1]]
    net = abs(closes[-1] - closes[0])
    path = sum(abs(closes[k] - closes[k-1]) for k in range(1, len(closes)))
    return net / path if path > 1e-9 else 0.0


def detect_all(i, side):
    if i < TREND_LB + 5: return {}
    bar = m1[i]; prev = m1[i-1]; prev2 = m1[i-2]; prev3 = m1[i-3]
    W = m1[i - TREND_LB:i]; R = m1[i - RETRO:i]; L5 = m1[i - 5:i]
    avgv = sum(b["v"] for b in W) / len(W)
    avgbody = sum(abs(b["c"] - b["o"]) for b in W) / len(W)
    avgr = sum(b["h"] - b["l"] for b in W) / len(W)
    rng = bar["h"] - bar["l"]
    body = abs(bar["c"] - bar["o"])
    green = bar["c"] > bar["o"]
    td = trend_dir(i); er = er_at(i)

    hits = {}
    if side == "buy":
        reds = [b for b in R if b["c"] < b["o"]]
        if reds:
            uhv = max(reds, key=lambda b: b["v"])
            if uhv["v"] > 1.2 * avgv and bar["c"] > uhv["h"] and bar["o"] <= uhv["h"] + 0.5 and green:
                hits["UHV"] = True
    else:
        grns = [b for b in R if b["c"] > b["o"]]
        if grns:
            uhv = max(grns, key=lambda b: b["v"])
            if uhv["v"] > 1.2 * avgv and bar["c"] < uhv["l"] and bar["o"] >= uhv["l"] - 0.5 and not green:
                hits["UHV"] = True

    dead = None
    for b in [prev, prev2, prev3]:
        if b["v"] < 0.7 * avgv and (b["h"] - b["l"]) < 0.7 * avgr:
            dead = b; break
    if dead is not None:
        if side == "buy" and bar["c"] > dead["h"] and green:
            hits["NSND"] = True
        elif side == "sell" and bar["c"] < dead["l"] and not green:
            hits["NSND"] = True

    prior = m1[i - 30:i - 5]
    if prior:
        if side == "buy":
            prior_lo = min(b["l"] for b in prior)
            for b in L5:
                if b["l"] < prior_lo and b["c"] > prior_lo:
                    hits["SWEEP"] = True; break
        else:
            prior_hi = max(b["h"] for b in prior)
            for b in L5:
                if b["h"] > prior_hi and b["c"] < prior_hi:
                    hits["SWEEP"] = True; break

    if er >= ER_MIN_FOR_MOM and body > 1.3 * avgbody:
        if side == "buy" and td == +1 and green: hits["MOM"] = True
        elif side == "sell" and td == -1 and not green: hits["MOM"] = True

    return hits


def simulate_tick(signal_ms, side):
    """Enter at first tick after signal_ms. Manage at tick level."""
    k0 = bisect.bisect_left(tick_times, signal_ms)
    if k0 >= len(ticks): return None
    entry_ms = ticks[k0]["t_ms"]
    entry_px = ticks[k0]["ask"] if side == "buy" else ticks[k0]["bid"]
    peak = 0.0; armed = False
    for k in range(k0, len(ticks)):
        tk = ticks[k]; t = tk["t_ms"]
        if (t - entry_ms) > MAX_HOLD_SEC * 1000:
            cur = (tk["bid"] - entry_px) if side == "buy" else (entry_px - tk["ask"])
            return (cur - COST, t, "EOH", peak)
        if side == "buy":
            cur = tk["bid"] - entry_px
        else:
            cur = entry_px - tk["ask"]
        if cur >= SKIM_CAP: return (cur - COST, t, "SKIM", peak)
        if cur > peak: peak = cur
        if peak >= TRAIL_ARM: armed = True
        if armed and cur <= peak - TRAIL_GIVEBACK:
            return (cur - COST, t, "TRAIL", peak)
        if cur <= -MAX_LOSS: return (-MAX_LOSS - COST, t, "CB", peak)
        if (t - entry_ms) > SCRATCH_SEC * 1000 and peak < TRAIL_ARM and cur <= SCRATCH_AT:
            return (cur - COST, t, "SCRATCH", peak)
    last = ticks[-1]
    cur = (last["bid"] - entry_px) if side == "buy" else (entry_px - last["ask"])
    return (cur - COST, last["t_ms"], "EOD", peak)


# Run
fills = []
last_fire_ms = {"buy": 0, "sell": 0}
for i in range(N):
    for side in ("buy", "sell"):
        h = detect_all(i, side)
        if not h: continue
        # signal fires at bar close = t_end_ms
        signal_ms = m1[i]["t_end_ms"]
        if signal_ms - last_fire_ms[side] < COOLDOWN_SEC * 1000: continue
        result = simulate_tick(signal_ms, side)
        if result is None: continue
        pnl, exit_ms, why, peak = result
        fills.append({
            "t": m1[i]["t"], "side": side, "pnl": pnl, "why": why,
            "patterns": ",".join(sorted(h.keys())), "peak": peak,
        })
        last_fire_ms[side] = signal_ms

n = len(fills)
w = sum(1 for f in fills if f["pnl"] > 0)
l = sum(1 for f in fills if f["pnl"] <= 0)
tot = sum(f["pnl"] for f in fills)
avgw = sum(f["pnl"] for f in fills if f["pnl"] > 0) / max(1, w)
avgl = sum(f["pnl"] for f in fills if f["pnl"] <= 0) / max(1, l)
print(f"=== FEB 11 REAL TICK BACKTEST (Blueberry-Demo, 0.10 lots equiv) ===")
print(f"  Fills: {n}   Wins: {w}   Losses: {l}   WR: {100*w/max(1,n):.0f}%")
print(f"  NET:    ${tot:+.2f}    avgW ${avgw:+.2f}    avgL ${avgl:+.2f}")
print(f"  TARGET: 65W/4L (94% WR), NET +$835, avgW +$12.93, avgL -$1.32\n")

print(f"  {'pattern':<10} {'fires':>5} {'wins':>5} {'WR%':>5} {'NET$':>8} {'avgW':>6} {'avgL':>6}")
all_p = set()
for f in fills: all_p |= set(f["patterns"].split(","))
for p in sorted(all_p):
    sub = [f for f in fills if p in f["patterns"].split(",")]
    nn = len(sub); ww = sum(1 for x in sub if x["pnl"] > 0)
    aw = sum(x["pnl"] for x in sub if x["pnl"]>0)/max(1,ww)
    al = sum(x["pnl"] for x in sub if x["pnl"]<=0)/max(1,nn-ww)
    print(f"  {p:<10} {nn:>5} {ww:>5} {100*ww/max(1,nn):>4.0f}% {sum(x['pnl'] for x in sub):>+8.2f} {aw:>+6.2f} {al:>+6.2f}")

print(f"\n  {'why':<10} {'count':>6} {'NET$':>8}")
reasons = Counter(f["why"] for f in fills)
rsum = defaultdict(float)
for f in fills: rsum[f["why"]] += f["pnl"]
for why in sorted(reasons.keys()):
    print(f"  {why:<10} {reasons[why]:>6} {rsum[why]:>+8.2f}")

ZEE_MIN = [
    ("01:32","buy"),("01:59","buy"),("02:09","sell"),("02:29","buy"),
    ("16:49","buy"),("16:52","buy"),("16:54","buy"),("16:58","buy"),
    ("17:02","buy"),("17:36","buy"),("17:37","buy"),("17:49","buy"),
    ("18:24","buy"),("18:41","buy"),("19:08","sell"),("19:11","sell"),
    ("19:20","sell"),("19:26","sell"),("19:29","buy"),("19:32","buy"),
    ("19:36","buy"),("19:38","buy"),("19:41","sell"),("19:42","sell"),
]
matched = 0
for hm, sd in ZEE_MIN:
    hh, mm = map(int, hm.split(":"))
    tmin = hh * 60 + mm
    for f in fills:
        fm = f["t"].hour * 60 + f["t"].minute
        if f["side"] == sd and abs(fm - tmin) <= 2:
            matched += 1; break
print(f"\n  Captured Zee setups: {matched} / 24 (±2 min same side)")

# Filter to just Zee's trading hours (01:30-02:30, 16:45-19:45)
zee_hours_fills = [f for f in fills if
                   (1 <= f["t"].hour < 3) or
                   (16 <= f["t"].hour < 20)]
if zee_hours_fills:
    nh = len(zee_hours_fills); wh = sum(1 for f in zee_hours_fills if f["pnl"]>0)
    toth = sum(f["pnl"] for f in zee_hours_fills)
    print(f"\n  === RESTRICTED TO ZEE'S TRADING HOURS (01:30-02:30 + 16:45-19:45) ===")
    print(f"  Fills: {nh}   WR: {100*wh/nh:.0f}%   NET: ${toth:+.2f}")
