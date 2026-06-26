"""zee_feb11_REAL_tight.py — much tighter entry detector to cut 808 → ~50 fires/day.
Tight rules + wide-giveback exit (validated on Zee's 27 entries) on full Feb 11.

TIGHTER ENTRY:
  - Trend MUST be strong (HH/HL on M1-30, ER >= 0.20)
  - Entry bar body% >= 0.55, body >= $0.50
  - Require 2+ patterns to confirm (OR strong UHV vol>=2.0x)
  - Per-side cooldown 5 minutes
  - Volume on entry bar >= 0.8x avgv (not on a dead bar)

EXIT (validated $310/$322 on Zee's entries):
  - Peak trail arm=$1.0 raw, giveback=$5.0 raw (let big winners run)
  - Skim at $50 raw
  - Max loss = $5 raw (= ~$50 dollars at 0.10 lots)
  - Max hold 30 min

UNITS: pnl in raw price. ×10 = dollars at 0.10 lots.
"""
import csv, sys, bisect
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICKS = COMMON / "shano_ticks_2026-02-11.csv"

TREND_LB = 30; RETRO = 12
TRAIL_ARM = 1.0
TRAIL_GIVEBACK = 5.0
SKIM_CAP = 50.0
MAX_LOSS = 5.0
MAX_HOLD_SEC = 1800
COOLDOWN_SEC = 300
COST = 0.20

# Tight detector params
ER_MIN = 0.20
ENTRY_BODY_PCT_MIN = 0.55
ENTRY_BODY_MIN = 0.50
ENTRY_VOL_MIN_X = 0.8     # don't enter on dead bars
UHV_VOL_MULT = 1.5        # was 1.2
STRONG_UHV_MULT = 2.0     # solo-trigger threshold

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
        except: continue
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


def detect_tight(i, side):
    if i < TREND_LB + 5: return None
    bar = m1[i]; prev = m1[i-1]; prev2 = m1[i-2]; prev3 = m1[i-3]
    W = m1[i - TREND_LB:i]; R = m1[i - RETRO:i]; L5 = m1[i - 5:i]
    avgv = sum(b["v"] for b in W) / len(W)
    avgbody = sum(abs(b["c"] - b["o"]) for b in W) / len(W)
    avgr = sum(b["h"] - b["l"] for b in W) / len(W)
    rng = bar["h"] - bar["l"]
    body = abs(bar["c"] - bar["o"])
    body_pct = body / rng if rng > 0 else 0
    green = bar["c"] > bar["o"]
    td = trend_dir(i); er = er_at(i)

    # GATES
    if er < ER_MIN: return None
    if body_pct < ENTRY_BODY_PCT_MIN: return None
    if body < ENTRY_BODY_MIN: return None
    if bar["v"] < ENTRY_VOL_MIN_X * avgv: return None
    if side == "buy":
        if not (td == +1 and green): return None
    else:
        if not (td == -1 and not green): return None

    patterns = []
    strong_uhv = False
    if side == "buy":
        reds = [b for b in R if b["c"] < b["o"]]
        if reds:
            uhv = max(reds, key=lambda b: b["v"])
            uhv_mult = uhv["v"] / avgv
            if uhv_mult > UHV_VOL_MULT and bar["c"] > uhv["h"] and bar["o"] <= uhv["h"] + 0.5:
                patterns.append("UHV")
                if uhv_mult >= STRONG_UHV_MULT: strong_uhv = True
    else:
        grns = [b for b in R if b["c"] > b["o"]]
        if grns:
            uhv = max(grns, key=lambda b: b["v"])
            uhv_mult = uhv["v"] / avgv
            if uhv_mult > UHV_VOL_MULT and bar["c"] < uhv["l"] and bar["o"] >= uhv["l"] - 0.5:
                patterns.append("UHV")
                if uhv_mult >= STRONG_UHV_MULT: strong_uhv = True

    dead = None
    for b in [prev, prev2, prev3]:
        if b["v"] < 0.5 * avgv and (b["h"] - b["l"]) < 0.5 * avgr:
            dead = b; break
    if dead is not None:
        if side == "buy" and bar["c"] > dead["h"]: patterns.append("NSND")
        elif side == "sell" and bar["c"] < dead["l"]: patterns.append("NSND")

    prior = m1[i - 30:i - 2]
    if prior:
        if side == "buy":
            plo = min(b["l"] for b in prior)
            for b in [prev, bar]:
                if b["l"] < plo and b["c"] > plo: patterns.append("SWEEP"); break
        else:
            phi = max(b["h"] for b in prior)
            for b in [prev, bar]:
                if b["h"] > phi and b["c"] < phi: patterns.append("SWEEP"); break

    if body > 1.5 * avgbody:
        if side == "buy" and td == +1: patterns.append("MOM")
        elif side == "sell" and td == -1: patterns.append("MOM")

    # FILTER: require 2+ patterns OR strong UHV
    if len(patterns) >= 2 or strong_uhv:
        return patterns
    return None


def simulate(signal_ms, side):
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
        cur = (tk["bid"] - entry_px) if side == "buy" else (entry_px - tk["ask"])
        if cur >= SKIM_CAP: return (cur - COST, "SKIM", peak)
        if cur > peak: peak = cur
        if peak >= TRAIL_ARM: armed = True
        if armed and cur <= peak - TRAIL_GIVEBACK: return (cur - COST, "TRAIL", peak)
        if cur <= -MAX_LOSS: return (-MAX_LOSS - COST, "CB", peak)
    last = ticks[-1]
    cur = (last["bid"] - entry_px) if side == "buy" else (entry_px - last["ask"])
    return (cur - COST, "EOD", peak)


fills = []
last_fire_ms = {"buy": 0, "sell": 0}
for i in range(N):
    for side in ("buy", "sell"):
        h = detect_tight(i, side)
        if not h: continue
        signal_ms = m1[i]["t_end_ms"]
        if signal_ms - last_fire_ms[side] < COOLDOWN_SEC * 1000: continue
        r = simulate(signal_ms, side)
        if r is None: continue
        pnl, why, peak = r
        fills.append({"t": m1[i]["t"], "side": side, "pnl": pnl, "why": why,
                      "patterns": ",".join(h), "peak": peak})
        last_fire_ms[side] = signal_ms

n = len(fills)
w = sum(1 for f in fills if f["pnl"]>0); l = n - w
tot = sum(f["pnl"] for f in fills)
aw = sum(f["pnl"] for f in fills if f["pnl"]>0)/max(1,w)
al = sum(f["pnl"] for f in fills if f["pnl"]<=0)/max(1,l)
print(f"=== FEB 11 TIGHT DETECTOR + WIDE-TRAIL EXIT ===")
print(f"  Fires: {n}   W: {w}   L: {l}   WR: {100*w/max(1,n):.0f}%")
print(f"  NET (raw price): ${tot:+.2f}    avgW ${aw:+.2f}    avgL ${al:+.2f}")
print(f"  NET at 0.10 lots: ${tot*10:+.2f} dollars")
print(f"  TARGET: Zee's actual day = +$835 dollars (or +$322 first-fills)\n")

reasons = Counter(f["why"] for f in fills)
rsum = defaultdict(float)
for f in fills: rsum[f["why"]] += f["pnl"]
print(f"  Exit reasons:")
for why in sorted(reasons.keys()):
    print(f"    {why:<10} count={reasons[why]:>3}  NET ${rsum[why]:>+8.2f}  (${rsum[why]*10:>+8.0f} at 0.10L)")

print(f"\n  Per-fill detail:")
print(f"  {'t':>9} {'side':>4} {'pnl_raw':>+8} {'pnl_$':>+8} {'why':<8} {'peak':>7} {'patterns':<15}")
for f in fills:
    print(f"  {f['t'].strftime('%H:%M:%S'):>9} {f['side']:>4} {f['pnl']:>+8.2f} "
          f"{f['pnl']*10:>+8.1f} {f['why']:<8} {f['peak']:>+7.2f} {f['patterns']:<15}")

# Coverage of Zee
ZEE_MIN = [("01:32","buy"),("01:59","buy"),("02:09","sell"),("02:29","buy"),
           ("16:49","buy"),("16:52","buy"),("16:54","buy"),("16:58","buy"),
           ("17:02","buy"),("17:36","buy"),("17:37","buy"),("17:49","buy"),
           ("18:24","buy"),("18:41","buy"),("19:08","sell"),("19:11","sell"),
           ("19:20","sell"),("19:26","sell"),("19:29","buy"),("19:32","buy"),
           ("19:36","buy"),("19:38","buy"),("19:41","sell"),("19:42","sell")]
matched = 0
for hm, sd in ZEE_MIN:
    hh, mm = map(int, hm.split(":"))
    tmin = hh * 60 + mm
    for f in fills:
        fm = f["t"].hour * 60 + f["t"].minute
        if f["side"] == sd and abs(fm - tmin) <= 3:
            matched += 1; break
print(f"\n  Captured Zee setups: {matched} / 24 (±3 min same side)")
