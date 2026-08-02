"""zee_feb11_ea_v1.py — first honest attempt at an EA that reproduces Zee's Feb-11
on his BROKER's M1 bars (rev_eng_m1.csv).

DESIGN (per tick-forensics findings + ZEE 24-setup analysis):
  ENTRY (OR of patterns) — fires on M1 bar close:
    [A] UHV-red-then-break (S1/S4 pattern) — buy
    [A] UHV-green-then-break — sell
    [B] NS/ND: dead-volume candle in last 3, current bar breaks its high/low in trend
    [C] SWEEP: recent extreme wicked beyond, current bar closes back inside
    [D] CONTINUATION: trend-aligned momentum bar (body > 1.3×avgbody) in HH/HL trend
    [E] PULLBACK BREAK: small-body bar in trend, breaks recent 5-bar high (buy) / low (sell)

  EXIT (matches Zee's tape-reading):
    - Peak trail: arm when MFE >= $1; trail at peak - $0.40 (give back $0.40)
    - Time scratch: if bar `t+N` not in profit (close <= entry +/- $0.20), exit at close
    - Max floating loss circuit breaker: −$3 hard cut (Zee's worst loss Feb 11 = -$1.60,
      so $3 is well outside his pain threshold)
    - Per-side single-position (no cluster pyramid; multi-fills already captured by
      Zee's same-minute clusters but we mechanize as 1 lot per signal)

  CONSERVATIVE SIM (M1 bar-level, no ticks):
    For each entry at bar i+1 open:
      walk bars j = i+1 ..
        bar high/low touched → conservative ordering:
          buy: assume bar HIGH first if entry < bar open; LOW first if entry > bar open
          (i.e. price moved from open toward extreme away from entry first)
        check trail exit, scratch exit, circuit breaker

Cost model: spread $0.20 per side absorbed in entry/exit.
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

# === EA params (tuned by hand for first run) ===
TREND_LB = 30; RETRO = 12
ER_MIN_FOR_MOM = 0.10       # only allow continuation when not chop
# Trail
TRAIL_ARM = 1.0             # arm trail when MFE crosses +$1.0
TRAIL_GIVEBACK = 0.40       # trail price = peak - $0.40
# Scratch
SCRATCH_BARS = 5            # if after 5 bars not in profit >= $0.20, scratch
SCRATCH_AT = 0.20           # "in profit" threshold for scratch decision
# Circuit breaker (hard cut)
MAX_LOSS = 3.0
COST = 0.20                 # per round-trip spread/commission proxy

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
print(f"Loaded {N} M1 bars (Feb 10-12 window from rev_eng_m1)\n")


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
    """Returns dict of {pattern_name: True} for every pattern firing on bar i."""
    if i < TREND_LB + 5: return {}
    bar = bars[i]; prev = bars[i-1]; prev2 = bars[i-2]; prev3 = bars[i-3]
    W = bars[i - TREND_LB:i]
    R = bars[i - RETRO:i]
    L5 = bars[i - 5:i]
    avgv = sum(b["v"] for b in W) / len(W)
    avgbody = sum(abs(b["c"] - b["o"]) for b in W) / len(W)
    avgr = sum(b["h"] - b["l"] for b in W) / len(W)
    rng = bar["h"] - bar["l"]
    body = abs(bar["c"] - bar["o"])
    body_pct = body / rng if rng > 0 else 0
    green = bar["c"] > bar["o"]
    td = trend_dir(i)
    er = er_at(i)

    hits = {}
    # [A] UHV-red breakout (buy) / UHV-green breakdown (sell)
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

    # [B] NS/ND: dead-vol candle in last 3, current bar breaks its high (buy) / low (sell) in trend
    dead = None
    for b in [prev, prev2, prev3]:
        if b["v"] < 0.7 * avgv and (b["h"] - b["l"]) < 0.7 * avgr:
            dead = b; break
    if dead is not None:
        if side == "buy" and bar["c"] > dead["h"] and green:
            hits["NSND"] = True
        elif side == "sell" and bar["c"] < dead["l"] and not green:
            hits["NSND"] = True

    # [C] SWEEP: in last 5, an extreme beyond prior 25, closed back inside
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

    # [D] CONTINUATION: trend-aligned momentum bar with ER >= ER_MIN_FOR_MOM
    if er >= ER_MIN_FOR_MOM and body > 1.3 * avgbody:
        if side == "buy" and td == +1 and green:
            hits["MOM"] = True
        elif side == "sell" and td == -1 and not green:
            hits["MOM"] = True

    # [E] PULLBACK BREAK: 1-3 small bars then break of recent 5-bar extreme
    smalls = sum(1 for b in [prev, prev2, prev3] if abs(b["c"] - b["o"]) < 0.5 * avgbody)
    if smalls >= 2:
        last5_hi = max(b["h"] for b in L5)
        last5_lo = min(b["l"] for b in L5)
        if side == "buy" and bar["c"] > last5_hi and green and td >= 0:
            hits["PB"] = True
        elif side == "sell" and bar["c"] < last5_lo and not green and td <= 0:
            hits["PB"] = True
    return hits


def simulate_trade(entry_idx, side, entry_px):
    """M1-bar exit simulation per design above. Returns (pnl, exit_idx, exit_reason)."""
    peak = 0.0          # MFE in $
    armed = False
    for j in range(entry_idx, min(entry_idx + 60, N)):  # 60-min hard timeout
        bar = bars[j]
        # Compute MFE and MAE for this bar conservatively
        if side == "buy":
            bar_mfe = bar["h"] - entry_px
            bar_mae = bar["l"] - entry_px
        else:
            bar_mfe = entry_px - bar["l"]
            bar_mae = entry_px - bar["h"]
        # Order of touch: if entry_px > bar open, bar moved AWAY from us first (low first if buy)
        if side == "buy":
            adverse_first = entry_px > bar["o"]
        else:
            adverse_first = entry_px < bar["o"]

        # Check adverse touch first if applicable
        if adverse_first:
            # Hit circuit breaker?
            if bar_mae <= -MAX_LOSS:
                return (-MAX_LOSS - COST, j, "CB")
            # Hit trail?
            if armed:
                trail_lvl = peak - TRAIL_GIVEBACK
                if bar_mae <= trail_lvl:   # bar went below trail price
                    return (trail_lvl - COST, j, "TRAIL_adv")
            # Update peak from this bar's MFE
            peak = max(peak, bar_mfe)
            if peak >= TRAIL_ARM: armed = True
            # Trail might also hit after peak update
            if armed:
                trail_lvl = peak - TRAIL_GIVEBACK
                # If peak was earlier this bar (high before low), trail would have hit on adverse leg
                # already handled. If peak after, check at bar close
                if bar["c"] - entry_px if side == "buy" else entry_px - bar["c"] <= trail_lvl:
                    pass  # let close logic handle
        else:
            # Favorable first: update peak
            peak = max(peak, bar_mfe)
            if peak >= TRAIL_ARM: armed = True
            if armed:
                trail_lvl = peak - TRAIL_GIVEBACK
                if bar_mae <= trail_lvl:
                    return (trail_lvl - COST, j, "TRAIL")
            if bar_mae <= -MAX_LOSS:
                return (-MAX_LOSS - COST, j, "CB")

        # End-of-bar checks: scratch if after SCRATCH_BARS we're not nicely in profit
        bars_held = j - entry_idx + 1
        cur_pnl = (bar["c"] - entry_px) if side == "buy" else (entry_px - bar["c"])
        if bars_held >= SCRATCH_BARS and cur_pnl < SCRATCH_AT and peak < TRAIL_ARM:
            return (cur_pnl - COST, j, "SCRATCH")
    last = bars[min(entry_idx + 59, N - 1)]
    cur_pnl = (last["c"] - entry_px) if side == "buy" else (entry_px - last["c"])
    return (cur_pnl - COST, min(entry_idx + 59, N - 1), "EOH")


# ── Run on Feb 11 only ──
feb11 = datetime(2026, 2, 11).date()
fills = []
for i in range(N):
    if bars[i]["t"].date() != feb11: continue
    for side in ("buy", "sell"):
        h = detect_all(i, side)
        if not h: continue
        if i + 1 >= N: continue
        entry_bar = bars[i + 1]
        entry_px = entry_bar["o"]
        pnl, ex_i, reason = simulate_trade(i + 1, side, entry_px)
        fills.append({
            "t": bars[i]["t"], "side": side, "entry_t": entry_bar["t"],
            "entry": entry_px, "pnl": pnl, "exit_t": bars[ex_i]["t"],
            "why": reason, "patterns": ",".join(sorted(h.keys()))
        })

n = len(fills)
w = sum(1 for f in fills if f["pnl"] > 0)
l = sum(1 for f in fills if f["pnl"] <= 0)
tot = sum(f["pnl"] for f in fills)
avgw = sum(f["pnl"] for f in fills if f["pnl"] > 0) / max(1, w)
avgl = sum(f["pnl"] for f in fills if f["pnl"] <= 0) / max(1, l)
print(f"=== FEB 11 RESULTS (bar-conservative M1 sim) ===")
print(f"  Fills: {n}   Wins: {w}   Losses: {l}   WR: {100*w/max(1,n):.0f}%")
print(f"  NET:    ${tot:+.2f}    avgW ${avgw:+.2f}    avgL ${avgl:+.2f}")
print(f"  TARGET: 65W/4L (94% WR), NET +$835, avgW +$12.93, avgL -$1.32\n")

# Per-pattern breakdown
print(f"  {'pattern':<10} {'fires':>5} {'wins':>5} {'WR%':>5} {'NET$':>8}")
all_pats = set()
for f in fills: all_pats |= set(f["patterns"].split(","))
for p in sorted(all_pats):
    sub = [f for f in fills if p in f["patterns"].split(",")]
    nn = len(sub); ww = sum(1 for x in sub if x["pnl"] > 0)
    print(f"  {p:<10} {nn:>5} {ww:>5} {100*ww/max(1,nn):>4.0f}% {sum(x['pnl'] for x in sub):>+8.2f}")

# Print every fill
print(f"\n  {'entry_t':>10} {'side':>4} {'entry':>8} {'pnl':>7} {'why':<10} {'patterns':<20}")
for f in fills[:30]:
    print(f"  {f['entry_t'].strftime('%H:%M:%S'):>10} {f['side']:>4} {f['entry']:>8.2f} "
          f"{f['pnl']:>+7.2f} {f['why']:<10} {f['patterns']:<20}")

# Match to Zee's 24 setups
ZEE_MIN = [
    ("01:32","buy"),("01:59","buy"),("02:09","sell"),("02:29","buy"),
    ("16:49","buy"),("16:52","buy"),("16:54","buy"),("16:58","buy"),
    ("17:02","buy"),("17:36","buy"),("17:37","buy"),("17:49","buy"),
    ("18:24","buy"),("18:41","buy"),("19:08","sell"),("19:11","sell"),
    ("19:20","sell"),("19:26","sell"),("19:29","buy"),("19:32","buy"),
    ("19:36","buy"),("19:38","buy"),("19:41","sell"),("19:42","sell"),
]
matches = 0
for hm, sd in ZEE_MIN:
    hh, mm = map(int, hm.split(":"))
    tmin = hh * 60 + mm
    for f in fills:
        fm = f["t"].hour * 60 + f["t"].minute
        if f["side"] == sd and abs(fm - tmin) <= 2:
            matches += 1; break
print(f"\n  Captured Zee's setups: {matches} / 24 (±2 min, same side)")
