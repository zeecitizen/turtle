"""zee_feb11_ea_v3.py — change angle: detect SETUP CONDITIONS (not entry bar direction),
fire at bar_t close, enter at bar_{t+1} OPEN. Don't require entry-bar color match.

Conditions for BUY (mirror for sell):
  GATE: M1-30 trend = HH/HL up OR last-3-bar net move > +$3 in trend direction
  ANY ONE of:
    [A] UHV-PULLBACK: high-vol red candle in last 12, current bar tested below it
        but closed back above; ER >= 0.10  (Zee's S1-style entry after probe)
    [B] DEAD-VOL DOJI: prev bar is dead-vol (<0.5 avg) AND small range (<0.5 avgr) AND
        within last 5 bars there was a stronger green/red move in trend direction
        (the "rest before continuation")
    [C] BIG-BAR CONTINUATION: any of last 3 bars closed strongly in trend dir
        (body >= $2.0 and body% >= 0.55) AND current bar hasn't reversed sharply
    [D] SWEEP-REVERSE: last 2 bars wicked beyond prior 25-bar extreme then closed back

EXIT (Zee-style, wider trail to capture big wins):
  - Peak-trail: arm at +$1.5, giveback $1.0  (lets +$5-10 winners breathe)
  - Skim cap: if MFE >= $8 → take it (Zee's big skim)
  - Scratch: at end of bar 3, if NOT in profit >= $0.10 → exit at close (close-to-bk)
  - Circuit breaker: -$1.60 (matches Zee's worst Feb-11 loss)
  - Max hold: 15 M1 bars (Zee's longest scratch held 25min but was an outlier)
"""
import csv, sys
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
M1 = COMMON / "rev_eng_m1.csv"

TREND_LB = 30; RETRO = 12
TRAIL_ARM = 1.5
TRAIL_GIVEBACK = 1.0
SKIM_CAP = 8.0
SCRATCH_BARS = 3
SCRATCH_AT = 0.10
MAX_LOSS = 1.60
MAX_HOLD = 15
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


def setup(i, side):
    """Detect setup using info up to (and including) bar i. Entry will be at bar i+1 open."""
    if i < TREND_LB + 5 or i + 1 >= N: return None
    bar = bars[i]; prev = bars[i-1]; prev2 = bars[i-2]; prev3 = bars[i-3]
    W = bars[i - TREND_LB:i + 1]
    R = bars[i - RETRO:i + 1]
    L3 = [prev, prev2, prev3]
    L5 = bars[i - 5:i]
    avgv = sum(b["v"] for b in W) / len(W)
    avgbody = sum(abs(b["c"] - b["o"]) for b in W) / len(W)
    avgr = sum(b["h"] - b["l"] for b in W) / len(W)
    td = trend_dir(i)
    er = er_at(i)

    # GATE
    last3_net = bar["c"] - bars[i-3]["c"]
    if side == "buy":
        if not (td == +1 or last3_net >= 3.0): return None
    else:
        if not (td == -1 or last3_net <= -3.0): return None

    hits = []

    # [A] UHV pullback then close back
    if side == "buy":
        reds = [b for b in R if b["c"] < b["o"]]
        if reds:
            uhv = max(reds, key=lambda b: b["v"])
            if uhv["v"] >= 1.3 * avgv:
                # current bar dipped below UHV high then closed above
                if bar["l"] <= uhv["h"] and bar["c"] > uhv["h"] and er >= 0.10:
                    hits.append("UHV")
    else:
        grns = [b for b in R if b["c"] > b["o"]]
        if grns:
            uhv = max(grns, key=lambda b: b["v"])
            if uhv["v"] >= 1.3 * avgv:
                if bar["h"] >= uhv["l"] and bar["c"] < uhv["l"] and er >= 0.10:
                    hits.append("UHV")

    # [B] Dead-vol doji as continuation rest
    if (bar["v"] < 0.6 * avgv and (bar["h"] - bar["l"]) < 0.6 * avgr):
        # was there a strong move in trend dir in last 5?
        if side == "buy" and any(b["c"] > b["o"] and (b["c"] - b["o"]) > 1.5 * avgbody for b in L5):
            hits.append("REST")
        elif side == "sell" and any(b["c"] < b["o"] and (b["o"] - b["c"]) > 1.5 * avgbody for b in L5):
            hits.append("REST")

    # [C] Big-bar continuation: last 3 bars had a strong trend-dir move, current bar didn't reverse hard
    if side == "buy":
        had_big = any(b["c"] > b["o"] and (b["c"] - b["o"]) >= 2.0 and (b["c"]-b["o"])/(b["h"]-b["l"]+1e-9) >= 0.55 for b in L3)
        not_reversed = bar["c"] >= bar["o"] - 0.5  # didn't crash this bar
        if had_big and not_reversed: hits.append("CONT")
    else:
        had_big = any(b["c"] < b["o"] and (b["o"] - b["c"]) >= 2.0 and (b["o"]-b["c"])/(b["h"]-b["l"]+1e-9) >= 0.55 for b in L3)
        not_reversed = bar["c"] <= bar["o"] + 0.5
        if had_big and not_reversed: hits.append("CONT")

    # [D] Sweep reverse over last 2 bars
    prior = bars[i - 30:i - 2]
    if prior:
        L2 = [bars[i-1], bars[i]]
        if side == "buy":
            prior_lo = min(b["l"] for b in prior)
            if any(b["l"] < prior_lo and b["c"] > prior_lo for b in L2):
                hits.append("SWP")
        else:
            prior_hi = max(b["h"] for b in prior)
            if any(b["h"] > prior_hi and b["c"] < prior_hi for b in L2):
                hits.append("SWP")

    return hits if hits else None


def simulate(entry_idx, side, entry_px):
    """Enter at bars[entry_idx]['o'] (we passed entry_idx as next-bar index)."""
    peak = 0.0; armed = False
    for j in range(entry_idx, min(entry_idx + MAX_HOLD, N)):
        bar = bars[j]
        if side == "buy":
            bar_mfe = bar["h"] - entry_px; bar_mae = bar["l"] - entry_px
            adverse_first = entry_px > bar["o"]
        else:
            bar_mfe = entry_px - bar["l"]; bar_mae = entry_px - bar["h"]
            adverse_first = entry_px < bar["o"]
        # Skim cap on MFE
        if bar_mfe >= SKIM_CAP:
            return (SKIM_CAP - COST, j, "SKIM")
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
        h = setup(i, side)
        if not h: continue
        entry_px = bars[i+1]["o"]
        pnl, ex_i, why = simulate(i+1, side, entry_px)
        fills.append({"t": bars[i]["t"], "side": side, "entry_t": bars[i+1]["t"],
                      "entry": entry_px, "pnl": pnl, "exit_t": bars[ex_i]["t"],
                      "why": why, "patterns": ",".join(h)})

n = len(fills)
w = sum(1 for f in fills if f["pnl"] > 0)
l = sum(1 for f in fills if f["pnl"] <= 0)
tot = sum(f["pnl"] for f in fills)
avgw = sum(f["pnl"] for f in fills if f["pnl"] > 0) / max(1, w)
avgl = sum(f["pnl"] for f in fills if f["pnl"] <= 0) / max(1, l)
print(f"=== FEB 11 v3 RESULTS ===")
print(f"  Fills: {n}   Wins: {w}   Losses: {l}   WR: {100*w/max(1,n):.0f}%")
print(f"  NET:    ${tot:+.2f}    avgW ${avgw:+.2f}    avgL ${avgl:+.2f}")
print(f"  TARGET: 65W/4L (94% WR), NET +$835, avgW +$12.93, avgL -$1.32\n")

print(f"  {'pattern':<10} {'fires':>5} {'wins':>5} {'WR%':>5} {'NET$':>8}")
all_p = set()
for f in fills: all_p |= set(f["patterns"].split(","))
for p in sorted(all_p):
    sub = [f for f in fills if p in f["patterns"].split(",")]
    nn = len(sub); ww = sum(1 for x in sub if x["pnl"] > 0)
    print(f"  {p:<10} {nn:>5} {ww:>5} {100*ww/max(1,nn):>4.0f}% {sum(x['pnl'] for x in sub):>+8.2f}")

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
