"""zee_feb11_ea_v6.py — keep v1's WR (70%) and lift avgW via better hold logic.

v1 (+$486 / 70%) and v5 (-$76 / 34%) showed the trade-off:
  v1: MAX_LOSS=$3, scratch=5 bars → 70% WR but avgW $2.12
  v5: MAX_LOSS=$2, scratch=2 bars → killed by noise wicks (CB 328 times)

Insight: M1-bar bar-conservative simulation has structural noise wicks. Need:
  - Filter entries to clean bars (body% >= 0.5, low wick)
  - Use generous MAX_LOSS ($3) to avoid noise stops
  - Use BAR-CLOSE for adverse decisions, not bar low/high (less whipsaw)
  - Wider TRAIL_GIVEBACK with higher TRAIL_ARM
"""
import csv, sys
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
M1 = COMMON / "rev_eng_m1.csv"

TREND_LB = 30; RETRO = 12
ER_MIN_FOR_MOM = 0.10
TRAIL_ARM = 2.0
TRAIL_GIVEBACK = 1.0
SKIM_CAP = 10.0
SCRATCH_BARS = 4
SCRATCH_AT = 0.20
MAX_LOSS = 3.0
MAX_HOLD = 20
COST = 0.20

# Entry-bar quality
ENTRY_BAR_MIN_BODY_PCT = 0.50

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

    # ── ENTRY BAR QUALITY (NEW) ──
    if body_pct < ENTRY_BAR_MIN_BODY_PCT: return {}
    if body < 0.30: return {}                 # absolute min body $0.30
    if side == "buy" and not green: return {}
    if side == "sell" and green: return {}

    hits = {}
    if side == "buy":
        reds = [b for b in R if b["c"] < b["o"]]
        if reds:
            uhv = max(reds, key=lambda b: b["v"])
            if uhv["v"] > 1.2 * avgv and bar["c"] > uhv["h"] and bar["o"] <= uhv["h"] + 0.5:
                hits["UHV"] = True
    else:
        grns = [b for b in R if b["c"] > b["o"]]
        if grns:
            uhv = max(grns, key=lambda b: b["v"])
            if uhv["v"] > 1.2 * avgv and bar["c"] < uhv["l"] and bar["o"] >= uhv["l"] - 0.5:
                hits["UHV"] = True

    dead = None
    for b in [prev, prev2, prev3]:
        if b["v"] < 0.7 * avgv and (b["h"] - b["l"]) < 0.7 * avgr:
            dead = b; break
    if dead is not None:
        if side == "buy" and bar["c"] > dead["h"]:
            hits["NSND"] = True
        elif side == "sell" and bar["c"] < dead["l"]:
            hits["NSND"] = True

    prior = bars[i - 30:i - 2]
    if prior:
        # current bar swept or previous bar swept
        if side == "buy":
            prior_lo = min(b["l"] for b in prior)
            for b in [prev, bar]:
                if b["l"] < prior_lo and b["c"] > prior_lo:
                    hits["SWEEP"] = True; break
        else:
            prior_hi = max(b["h"] for b in prior)
            for b in [prev, bar]:
                if b["h"] > prior_hi and b["c"] < prior_hi:
                    hits["SWEEP"] = True; break

    if er >= ER_MIN_FOR_MOM and body > 1.3 * avgbody:
        if side == "buy" and td == +1: hits["MOM"] = True
        elif side == "sell" and td == -1: hits["MOM"] = True

    return hits


def simulate(entry_idx, side, entry_px):
    """Use BAR CLOSE for CB/scratch decisions (less whipsaw than bar low/high).
    Use bar high/low for TRAIL_arm (capture peaks)."""
    peak = 0.0; armed = False
    for j in range(entry_idx, min(entry_idx + MAX_HOLD, N)):
        bar = bars[j]
        if side == "buy":
            bar_mfe = bar["h"] - entry_px
            close_pnl = bar["c"] - entry_px
        else:
            bar_mfe = entry_px - bar["l"]
            close_pnl = entry_px - bar["c"]
        # Skim on bar high
        if bar_mfe >= SKIM_CAP: return (SKIM_CAP - COST, j, "SKIM")
        # Update peak
        peak = max(peak, bar_mfe)
        if peak >= TRAIL_ARM: armed = True
        # Trail check uses bar close (less whipsaw)
        if armed:
            tl = peak - TRAIL_GIVEBACK
            if close_pnl <= tl: return (max(tl, close_pnl) - COST, j, "TRAIL")
        # CB on close (not low) — more forgiving
        if close_pnl <= -MAX_LOSS: return (-MAX_LOSS - COST, j, "CB")
        # Scratch
        held = j - entry_idx + 1
        if held >= SCRATCH_BARS and peak < TRAIL_ARM and close_pnl <= SCRATCH_AT:
            return (close_pnl - COST, j, "SCRATCH")
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
print(f"=== FEB 11 v6 RESULTS (clean-candle filter + close-based exits) ===")
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
