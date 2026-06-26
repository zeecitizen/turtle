"""zee_feb11_ea_v2.py — tighten v1 toward Zee's 24-setup signature.

v1 fired 849 trades vs Zee's 24. Issues:
  - SWEEP pattern alone fires 464 — too loose. Require sweep + reversal candle + vol.
  - NSND fires 246 — most dead-vol bars don't have a real signal after. Add vol-confirm.
  - MOM continuation fires whenever body > 1.3×avg. Require it ALSO be > $1.5 in $ terms.
  - PB pattern hurts (62% WR, -$3). Drop it.
  - avgW $2.12 vs $12.93. Trail is too tight ($0.40 giveback).

v2 changes:
  - Stricter detectors: require entry bar to itself be a momentum bar (body% >= 0.5) in trend
    direction OR strong UHV with vol-mult >= 2.0
  - Single-bar window per pattern: prevents double-firing on consecutive bars
  - Wider trail: $0.80 giveback after MFE >= $2 (lets winners breathe)
  - Quicker scratch: 2 bars (Zee scratched fast when wrong)
  - Tighter CB: $1.5 (Zee's worst loss was -$1.60)
"""
import csv, sys
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
M1 = COMMON / "rev_eng_m1.csv"

TREND_LB = 30; RETRO = 12
TRAIL_ARM = 2.0
TRAIL_GIVEBACK = 0.80
SCRATCH_BARS = 2
SCRATCH_AT = 0.0
MAX_LOSS = 1.5
COST = 0.20
COOLDOWN_BARS = 3   # don't re-fire same side within 3 bars

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


def detect(i, side):
    if i < TREND_LB + 5: return None
    bar = bars[i]; prev = bars[i-1]; prev2 = bars[i-2]; prev3 = bars[i-3]
    W = bars[i - TREND_LB:i]; R = bars[i - RETRO:i]; L5 = bars[i - 5:i]
    avgv = sum(b["v"] for b in W) / len(W)
    avgbody = sum(abs(b["c"] - b["o"]) for b in W) / len(W)
    avgr = sum(b["h"] - b["l"] for b in W) / len(W)
    rng = bar["h"] - bar["l"]
    body = abs(bar["c"] - bar["o"])
    body_pct = body / rng if rng > 0 else 0
    green = bar["c"] > bar["o"]
    td = trend_dir(i)
    er = er_at(i)

    # Entry-bar quality gate: must be a real candle with momentum
    # (body >= $0.40 AND body_pct >= 0.40) OR (body >= $1.0 absolute)
    strong_candle = (body >= 0.40 and body_pct >= 0.40) or body >= 1.0
    if not strong_candle: return None
    # Direction must match
    if side == "buy" and not green: return None
    if side == "sell" and green: return None

    hits = []

    # [A] UHV: strong-vol opposite candle in retracement, current bar breaks it
    if side == "buy":
        reds = [b for b in R if b["c"] < b["o"]]
        if reds:
            uhv = max(reds, key=lambda b: b["v"])
            if uhv["v"] >= 1.5 * avgv and bar["c"] > uhv["h"] and bar["o"] <= uhv["h"] + 1.0:
                hits.append("UHV")
    else:
        grns = [b for b in R if b["c"] > b["o"]]
        if grns:
            uhv = max(grns, key=lambda b: b["v"])
            if uhv["v"] >= 1.5 * avgv and bar["c"] < uhv["l"] and bar["o"] >= uhv["l"] - 1.0:
                hits.append("UHV")

    # [B] NS/ND: TIGHT — dead-vol AND tiny-range candle within last 3, current bar breaks
    dead = None
    for b in [prev, prev2, prev3]:
        if b["v"] < 0.5 * avgv and (b["h"] - b["l"]) < 0.5 * avgr:
            dead = b; break
    if dead is not None:
        if side == "buy" and bar["c"] > dead["h"] + 0.10:
            hits.append("NSND")
        elif side == "sell" and bar["c"] < dead["l"] - 0.10:
            hits.append("NSND")

    # [C] SWEEP — must be SAME bar that swept (more selective)
    prior = bars[i - 30:i - 1]
    if prior:
        if side == "buy":
            prior_lo = min(b["l"] for b in prior)
            if prev["l"] < prior_lo and prev["c"] > prior_lo and bar["c"] > prev["c"]:
                hits.append("SWEEP")
        else:
            prior_hi = max(b["h"] for b in prior)
            if prev["h"] > prior_hi and prev["c"] < prior_hi and bar["c"] < prev["c"]:
                hits.append("SWEEP")

    # [D] MOMENTUM continuation in trend (replaces both MOM and PB from v1)
    # Require: trend aligned, ER >= 0.15, body >= 1.5x avgbody, body >= $1.0
    if er >= 0.15 and body >= 1.5 * avgbody and body >= 1.0:
        if side == "buy" and td == +1:
            hits.append("MOM")
        elif side == "sell" and td == -1:
            hits.append("MOM")

    return hits if hits else None


def simulate(entry_idx, side, entry_px):
    peak = 0.0; armed = False
    for j in range(entry_idx, min(entry_idx + 30, N)):
        bar = bars[j]
        if side == "buy":
            bar_mfe = bar["h"] - entry_px; bar_mae = bar["l"] - entry_px
            adverse_first = entry_px > bar["o"]
        else:
            bar_mfe = entry_px - bar["l"]; bar_mae = entry_px - bar["h"]
            adverse_first = entry_px < bar["o"]
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
        # End of bar checks: scratch if not in profit after SCRATCH_BARS
        held = j - entry_idx + 1
        cur = (bar["c"] - entry_px) if side == "buy" else (entry_px - bar["c"])
        if held >= SCRATCH_BARS and peak < TRAIL_ARM and cur <= SCRATCH_AT:
            return (cur - COST, j, "SCRATCH")
    last = bars[min(entry_idx + 29, N - 1)]
    cur = (last["c"] - entry_px) if side == "buy" else (entry_px - last["c"])
    return (cur - COST, min(entry_idx + 29, N - 1), "EOH")


feb11 = datetime(2026, 2, 11).date()
fills = []
last_fire = {"buy": -999, "sell": -999}
for i in range(N):
    if bars[i]["t"].date() != feb11: continue
    for side in ("buy", "sell"):
        if i - last_fire[side] < COOLDOWN_BARS: continue
        h = detect(i, side)
        if not h: continue
        if i + 1 >= N: continue
        entry_bar = bars[i + 1]
        entry_px = entry_bar["o"]
        pnl, ex_i, why = simulate(i + 1, side, entry_px)
        fills.append({"t": bars[i]["t"], "side": side, "entry_t": entry_bar["t"],
                      "entry": entry_px, "pnl": pnl, "exit_t": bars[ex_i]["t"],
                      "why": why, "patterns": ",".join(h)})
        last_fire[side] = i

n = len(fills)
w = sum(1 for f in fills if f["pnl"] > 0)
l = sum(1 for f in fills if f["pnl"] <= 0)
tot = sum(f["pnl"] for f in fills)
avgw = sum(f["pnl"] for f in fills if f["pnl"] > 0) / max(1, w)
avgl = sum(f["pnl"] for f in fills if f["pnl"] <= 0) / max(1, l)
print(f"=== FEB 11 v2 RESULTS ===")
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

# Print first 30 fills
print(f"\n  {'entry_t':>10} {'side':>4} {'entry':>8} {'pnl':>7} {'why':<10} {'patterns':<15}")
for f in fills[:30]:
    print(f"  {f['entry_t'].strftime('%H:%M:%S'):>10} {f['side']:>4} {f['entry']:>8.2f} "
          f"{f['pnl']:>+7.2f} {f['why']:<10} {f['patterns']:<15}")
