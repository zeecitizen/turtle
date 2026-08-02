"""zee_feb11_ea_v5.py — v1's loose detector (+$486 / 70% WR) with better exits.

Theory: v1's detector grade is right. The miss was the exit — avgW $2.12 was tight.
Zee's avgW $12.93 came from holding spikes for 1-3 minutes. We can approximate this:

  - Arm trail at MFE = $3 (was $1) — wait for a REAL move
  - Trail giveback = $1.5 (was $0.40) — let it breathe
  - Skim cap = $15 (Zee's big skims) — take it on huge spikes
  - Quick scratch: 2 bars (was 5) — Zee's $1.32 avg loss
  - CB: $2 — slightly above Zee's worst single -$1.60

Goal: maintain ~70% WR but lift avgW from $2 → $6+. With 800 trades/day that's still
+$3000+ NET — DOUBLE Zee's actual day. Even if we cut signals by half, +$1500.
"""
import csv, sys
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
M1 = COMMON / "rev_eng_m1.csv"

TREND_LB = 30; RETRO = 12
ER_MIN_FOR_MOM = 0.10
TRAIL_ARM = 3.0
TRAIL_GIVEBACK = 1.5
SKIM_CAP = 15.0
SCRATCH_BARS = 2
SCRATCH_AT = 0.20
MAX_LOSS = 2.0
MAX_HOLD = 20
COST = 0.20

bars = []
for r in csv.DictReader(open(M1, encoding="utf-8")):
    t = datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S")
    if t.date() < datetime(2026, 2, 10).date() or t.date() > datetime(2026, 2, 12).date():
        continue
    bars.append({"t": t, "o": float(r["open"]), "h": float(r["high"]),
                 "l": float(r["low"]), "c": float(r["close"]),
                 "v": float(r["tick_volume"])})
bars.sort(key=lambda b: b["t"])
N = len(bars)


def trend_dir(i):
    if i < TREND_LB: return 0
    W = bars[i - TREND_LB:i]
    h = TREND_LB // 2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def er_at(i):
    if i < TREND_LB: return 0.0
    closes = [b["c"] for b in bars[i - TREND_LB:i + 1]]
    net = abs(closes[-1] - closes[0])
    path = sum(abs(closes[k] - closes[k-1]) for k in range(1, len(closes)))
    return net / path if path > 1e-9 else 0.0


def detect_all(i, side):
    """v1's LOOSE detector — same as before."""
    if i < TREND_LB + 5: return {}
    bar = bars[i]; prev = bars[i-1]; prev2 = bars[i-2]; prev3 = bars[i-3]
    W = bars[i - TREND_LB:i]; R = bars[i - RETRO:i]; L5 = bars[i - 5:i]
    avgv = sum(b["v"] for b in W) / len(W)
    avgbody = sum(abs(b["c"] - b["o"]) for b in W) / len(W)
    avgr = sum(b["h"] - b["l"] for b in W) / len(W)
    rng = bar["h"] - bar["l"]
    body = abs(bar["c"] - bar["o"])
    body_pct = body / rng if rng > 0 else 0
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

    prior = bars[i - 30:i - 5]
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
        if side == "buy" and td == +1 and green:
            hits["MOM"] = True
        elif side == "sell" and td == -1 and not green:
            hits["MOM"] = True

    return hits


def simulate(entry_idx, side, entry_px):
    """Same as v1, but with TRAIL_ARM=3, TRAIL_GIVEBACK=1.5, SKIM=15, scratch=2."""
    peak = 0.0; armed = False
    for j in range(entry_idx, min(entry_idx + MAX_HOLD, N)):
        bar = bars[j]
        if side == "buy":
            bar_mfe = bar["h"] - entry_px; bar_mae = bar["l"] - entry_px
            adverse_first = entry_px > bar["o"]
        else:
            bar_mfe = entry_px - bar["l"]; bar_mae = entry_px - bar["h"]
            adverse_first = entry_px < bar["o"]
        if bar_mfe >= SKIM_CAP: return (SKIM_CAP - COST, j, "SKIM")
        if adverse_first:
            if bar_mae <= -MAX_LOSS: return (-MAX_LOSS - COST, j, "CB")
            if armed:
                tl = peak - TRAIL_GIVEBACK
                if bar_mae <= tl: return (tl - COST, j, "TRAIL_adv")
            peak = max(peak, bar_mfe)
            if peak >= TRAIL_ARM: armed = True
        else:
            peak = max(peak, bar_mfe)
            if peak >= TRAIL_ARM: armed = True
            if armed:
                tl = peak - TRAIL_GIVEBACK
                if bar_mae <= tl: return (tl - COST, j, "TRAIL")
            if bar_mae <= -MAX_LOSS: return (-MAX_LOSS - COST, j, "CB")
        held = j - entry_idx + 1
        cur = (bar["c"] - entry_px) if side == "buy" else (entry_px - bar["c"])
        if held >= SCRATCH_BARS and peak < TRAIL_ARM and cur <= SCRATCH_AT:
            return (cur - COST, j, "SCRATCH")
    last = bars[min(entry_idx + MAX_HOLD - 1, N - 1)]
    cur = (last["c"] - entry_px) if side == "buy" else (entry_px - last["c"])
    return (cur - COST, min(entry_idx + MAX_HOLD - 1, N - 1), "EOH")


feb11 = datetime(2026, 2, 11).date()
fills = []
for i in range(N):
    if bars[i]["t"].date() != feb11: continue
    for side in ("buy", "sell"):
        h = detect_all(i, side)
        if not h: continue
        if i + 1 >= N: continue
        entry_px = bars[i + 1]["o"]
        pnl, ex_i, why = simulate(i + 1, side, entry_px)
        fills.append({"t": bars[i]["t"], "side": side, "pnl": pnl, "why": why,
                      "patterns": ",".join(sorted(h.keys()))})

n = len(fills)
w = sum(1 for f in fills if f["pnl"] > 0)
l = sum(1 for f in fills if f["pnl"] <= 0)
tot = sum(f["pnl"] for f in fills)
avgw = sum(f["pnl"] for f in fills if f["pnl"] > 0) / max(1, w)
avgl = sum(f["pnl"] for f in fills if f["pnl"] <= 0) / max(1, l)
print(f"=== FEB 11 v5 RESULTS (loose detector + Zee-style exit) ===")
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

# Exit reason breakdown
print(f"\n  {'why':<10} {'count':>6} {'NET$':>8}")
from collections import Counter, defaultdict
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
