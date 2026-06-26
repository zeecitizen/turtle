"""zee_feb11_REAL_v2.py — sweep exit params on real Blueberry Feb 11 ticks.
Find the (TRAIL_ARM, TRAIL_GIVEBACK, SCRATCH_SEC, MAX_LOSS, COOLDOWN_SEC) combo
that best reproduces Zee's day shape: high WR + asymmetric win/loss ratio.
"""
import csv, sys, bisect
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICKS = COMMON / "shano_ticks_2026-02-11.csv"

TREND_LB = 30; RETRO = 12
ER_MIN_FOR_MOM = 0.10
SKIM_CAP = 20.0
SCRATCH_AT = 0.0
MAX_HOLD_SEC = 900
COST = 0.20

print("Loading...")
ticks = []
with open(TICKS, encoding="utf-8") as f:
    next(f)
    for line in f:
        parts = line.strip().split(",")
        if len(parts) < 3: continue
        try:
            t_str = parts[0]
            date_p, time_p = t_str.split(" ")
            hms, ms_str = time_p.split(".") if "." in time_p else (time_p, "0")
            dt = datetime.strptime(date_p + " " + hms, "%Y.%m.%d %H:%M:%S")
            t_ms = int(dt.timestamp() * 1000) + int(ms_str)
            ticks.append({"t_ms": t_ms, "bid": float(parts[1]), "ask": float(parts[2])})
        except (ValueError, IndexError): continue
print(f"  {len(ticks):,} ticks")

m1 = []; cur = None
for tk in ticks:
    m_key = tk["t_ms"] // 60000
    mid = (tk["bid"] + tk["ask"]) / 2
    if cur is None or m_key != cur["m_key"]:
        if cur: m1.append(cur)
        cur = {"m_key": m_key, "o": mid, "h": mid, "l": mid, "c": mid, "v": 1,
               "t_end_ms": (m_key + 1) * 60000 - 1}
    else:
        cur["h"] = max(cur["h"], mid); cur["l"] = min(cur["l"], mid)
        cur["c"] = mid; cur["v"] += 1
if cur: m1.append(cur)
for b in m1: b["t"] = datetime.fromtimestamp(b["m_key"] * 60)
print(f"  {len(m1)} M1 bars\n")

N = len(m1)
tick_times = [t["t_ms"] for t in ticks]


def trend_dir(i):
    if i < TREND_LB: return 0
    W = m1[i - TREND_LB:i]; h = TREND_LB // 2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def er_at(i):
    if i < TREND_LB: return 0.0
    cs = [b["c"] for b in m1[i - TREND_LB:i + 1]]
    net = abs(cs[-1] - cs[0])
    path = sum(abs(cs[k] - cs[k-1]) for k in range(1, len(cs)))
    return net / path if path > 1e-9 else 0.0


def detect_all(i, side):
    if i < TREND_LB + 5: return {}
    bar = m1[i]; prev = m1[i-1]; prev2 = m1[i-2]; prev3 = m1[i-3]
    W = m1[i - TREND_LB:i]; R = m1[i - RETRO:i]; L5 = m1[i - 5:i]
    avgv = sum(b["v"] for b in W) / len(W)
    avgbody = sum(abs(b["c"] - b["o"]) for b in W) / len(W)
    avgr = sum(b["h"] - b["l"] for b in W) / len(W)
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
        if side == "buy" and bar["c"] > dead["h"] and green: hits["NSND"] = True
        elif side == "sell" and bar["c"] < dead["l"] and not green: hits["NSND"] = True
    prior = m1[i - 30:i - 5]
    if prior:
        if side == "buy":
            plo = min(b["l"] for b in prior)
            for b in L5:
                if b["l"] < plo and b["c"] > plo: hits["SWEEP"] = True; break
        else:
            phi = max(b["h"] for b in prior)
            for b in L5:
                if b["h"] > phi and b["c"] < phi: hits["SWEEP"] = True; break
    if er >= ER_MIN_FOR_MOM and body > 1.3 * avgbody:
        if side == "buy" and td == +1 and green: hits["MOM"] = True
        elif side == "sell" and td == -1 and not green: hits["MOM"] = True
    return hits


def simulate(signal_ms, side, trail_arm, trail_gb, scratch_sec, max_loss):
    k0 = bisect.bisect_left(tick_times, signal_ms)
    if k0 >= len(ticks): return None
    entry_ms = ticks[k0]["t_ms"]
    entry_px = ticks[k0]["ask"] if side == "buy" else ticks[k0]["bid"]
    peak = 0.0; armed = False
    for k in range(k0, len(ticks)):
        tk = ticks[k]; t = tk["t_ms"]
        if (t - entry_ms) > MAX_HOLD_SEC * 1000:
            cur = (tk["bid"] - entry_px) if side == "buy" else (entry_px - tk["ask"])
            return (cur - COST, "EOH", peak)
        if side == "buy": cur = tk["bid"] - entry_px
        else: cur = entry_px - tk["ask"]
        if cur >= SKIM_CAP: return (cur - COST, "SKIM", peak)
        if cur > peak: peak = cur
        if peak >= trail_arm: armed = True
        if armed and cur <= peak - trail_gb: return (cur - COST, "TRAIL", peak)
        if cur <= -max_loss: return (-max_loss - COST, "CB", peak)
        if (t - entry_ms) > scratch_sec * 1000 and peak < trail_arm and cur <= SCRATCH_AT:
            return (cur - COST, "SCRATCH", peak)
    last = ticks[-1]
    cur = (last["bid"] - entry_px) if side == "buy" else (entry_px - last["ask"])
    return (cur - COST, "EOD", peak)


def run(trail_arm, trail_gb, scratch_sec, max_loss, cooldown_sec):
    fills = []
    last_fire_ms = {"buy": 0, "sell": 0}
    for i in range(N):
        for side in ("buy", "sell"):
            h = detect_all(i, side)
            if not h: continue
            signal_ms = m1[i]["t_end_ms"]
            if signal_ms - last_fire_ms[side] < cooldown_sec * 1000: continue
            r = simulate(signal_ms, side, trail_arm, trail_gb, scratch_sec, max_loss)
            if r is None: continue
            pnl, why, peak = r
            fills.append({"t": m1[i]["t"], "side": side, "pnl": pnl, "why": why, "peak": peak})
            last_fire_ms[side] = signal_ms
    return fills


# Sweep
print(f"  {'arm':>5} {'gb':>5} {'scr':>5} {'CB':>5} {'cool':>5} | "
      f"{'n':>4} {'W':>4} {'L':>4} {'WR%':>5} {'NET$':>7} {'avgW':>6} {'avgL':>6} {'cap24':>6}")
best = (-9999, None, None)
ZEE_MIN = [("01:32","buy"),("01:59","buy"),("02:09","sell"),("02:29","buy"),
           ("16:49","buy"),("16:52","buy"),("16:54","buy"),("16:58","buy"),
           ("17:02","buy"),("17:36","buy"),("17:37","buy"),("17:49","buy"),
           ("18:24","buy"),("18:41","buy"),("19:08","sell"),("19:11","sell"),
           ("19:20","sell"),("19:26","sell"),("19:29","buy"),("19:32","buy"),
           ("19:36","buy"),("19:38","buy"),("19:41","sell"),("19:42","sell")]
configs = [
    (1.0, 0.30,  90, 2.0,   30),
    (1.0, 0.50,  90, 2.0,  120),
    (1.5, 0.50,  60, 2.0,  120),
    (1.5, 0.80, 120, 3.0,  180),
    (2.0, 1.00, 120, 3.0,  300),
    (2.5, 1.50, 180, 3.0,  600),
    (3.0, 2.00, 240, 4.0,  600),
    (0.5, 0.20,  60, 1.5,   60),    # very tight Zee-style
    (1.0, 0.40,  60, 1.5,   60),
    (1.0, 0.30,  60, 2.0,   60),
]
for cfg in configs:
    arm, gb, scr, ml, cd = cfg
    fills = run(arm, gb, scr, ml, cd)
    n = len(fills); w = sum(1 for f in fills if f["pnl"]>0); l = n - w
    tot = sum(f["pnl"] for f in fills)
    aw = sum(f["pnl"] for f in fills if f["pnl"]>0)/max(1,w)
    al = sum(f["pnl"] for f in fills if f["pnl"]<=0)/max(1,l)
    matched = 0
    for hm, sd in ZEE_MIN:
        hh, mm = map(int, hm.split(":")); tmin = hh*60+mm
        for f in fills:
            fm = f["t"].hour*60 + f["t"].minute
            if f["side"] == sd and abs(fm - tmin) <= 2:
                matched += 1; break
    print(f"  {arm:>5.1f} {gb:>5.2f} {scr:>5} {ml:>5.1f} {cd:>5} | "
          f"{n:>4} {w:>4} {l:>4} {100*w/max(1,n):>4.0f}% {tot:>+7.1f} {aw:>+6.2f} {al:>+6.2f} {matched:>4}/24")
    if tot > best[0]: best = (tot, cfg, fills)

print(f"\n=== BEST: arm={best[1][0]} gb={best[1][1]} scr={best[1][2]} CB={best[1][3]} cool={best[1][4]} → NET ${best[0]:+.2f} ===")
fills = best[2]
print(f"\n  Exit reasons:")
reasons = Counter(f["why"] for f in fills)
rsum = defaultdict(float)
for f in fills: rsum[f["why"]] += f["pnl"]
for why in sorted(reasons.keys()):
    print(f"    {why:<10} count={reasons[why]:>4}  NET ${rsum[why]:>+8.2f}")
