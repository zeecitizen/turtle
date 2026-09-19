"""HOW OFTEN DOES THE SETUP ACTUALLY APPEAR ON M5?

Zee, 2026-09-19: "on a 5 minute chart. the setup from VSISA comes alot more than once per
day.. doesn't it? check? selling campaign, low volume reaction (wick check), price
continues upwards on low volume.."

Fair challenge. VSISA takes 143 trades in 8.5 months - 0.8 a day - and if the raw pattern
appears far more often than that, the gap is the EA's extra gates rejecting setups he would
have taken, which is worth knowing exactly.

This COUNTS OCCURRENCES ONLY. It computes no P&L and simulates no trades - that would be a
Python backtest, which this project does not allow to promote anything (CLAUDE.md). It
answers one question: how many times does the three-stage pattern appear per day?

Built from the OANDA minutes aggregated to M5 on clock boundaries, TradingView convention
(green = close > open), using the EA's own thresholds.
"""
import csv
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

CSV = r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_bars.csv"

CAMP_VOL = 1.15      # campaign bars average >= this x the baseline
CAMP_MIN = 2         # at least this many bars in the run
RELEASE  = 0.85      # reaction volume <= this x the campaign average
BASE_N   = 20        # bars of baseline
WICK_FRAC = 0.30     # for the wick check: lower wick >= this x the bar range

rows = [r for r in csv.reader(open(CSV)) if len(r) >= 6]
M1 = [{"t": r[0], "o": float(r[1]), "h": float(r[2]), "l": float(r[3]),
       "c": float(r[4]), "v": float(r[5])} for r in rows]

# --- aggregate to M5 on clock boundaries
M5 = []
for b in M1:
    mins = int(b["t"][14:16])
    if not M5 or mins % 5 == 0:
        M5.append({"t": b["t"], "o": b["o"], "h": b["h"], "l": b["l"],
                   "c": b["c"], "v": b["v"]})
    else:
        k = M5[-1]
        k["h"] = max(k["h"], b["h"]); k["l"] = min(k["l"], b["l"])
        k["c"] = b["c"]; k["v"] += b["v"]

days = sorted({b["t"][:10] for b in M5})
print("M1 minutes %d  ->  M5 candles %d  over %d sessions (%s .. %s)"
      % (len(M1), len(M5), len(days), days[0], days[-1]))
print()

found = defaultdict(list)
funnel = defaultdict(int)

i = BASE_N
while i < len(M5) - 3:
    base = sum(M5[k]["v"] for k in range(i - BASE_N, i)) / BASE_N
    if base <= 0:
        i += 1; continue

    d = 1 if M5[i]["c"] > M5[i]["o"] else (-1 if M5[i]["c"] < M5[i]["o"] else 0)
    if d == 0:
        i += 1; continue

    # 1. the campaign - a run in one direction
    run, vsum = 0, 0.0
    j = i
    while j < len(M5) and ((M5[j]["c"] > M5[j]["o"]) == (d > 0)) and M5[j]["c"] != M5[j]["o"]:
        vsum += M5[j]["v"]; run += 1; j += 1
    if run < CAMP_MIN:
        i += 1; continue
    campAvg = vsum / run
    if campAvg < base * CAMP_VOL:
        i = j; continue
    funnel["1 campaign"] += 1

    # 2. the reaction - first opposite bar on lower volume
    if j >= len(M5):
        break
    r = M5[j]
    if not ((r["c"] > r["o"]) == (d < 0) and r["c"] != r["o"]):
        i = j; continue
    funnel["2 opposite bar"] += 1
    if r["v"] > campAvg * RELEASE:
        i = j; continue
    funnel["3 ...on lower volume"] += 1

    rng = r["h"] - r["l"]
    wick = (min(r["o"], r["c"]) - r["l"]) if d < 0 else (r["h"] - max(r["o"], r["c"]))
    haswick = rng > 0 and (wick / rng) >= WICK_FRAC
    if haswick:
        funnel["4 ...with a wick"] += 1

    # 3. continuation on light volume
    if j + 1 < len(M5):
        n = M5[j + 1]
        cont = ((n["c"] > n["o"]) == (d < 0)) and n["v"] <= campAvg
        if cont:
            funnel["5 ...then continued"] += 1
            found[r["t"][:10]].append((r["t"], run, campAvg, r["v"], haswick))
    i = j + 1

print("THE FUNNEL on M5")
for k in sorted(funnel):
    print("  %-24s %5d   (%.2f per session)" % (k, funnel[k], funnel[k] / len(days)))

print()
tot = sum(len(v) for v in found.values())
print("FULL three-stage setups (campaign -> quiet reaction -> continuation): %d" % tot)
print("  per session: %.2f" % (tot / len(days)))
withwick = sum(1 for v in found.values() for x in v if x[4])
print("  of those, with a wick on the reaction: %d (%.0f%%)"
      % (withwick, 100.0 * withwick / max(tot, 1)))
print()
print("  per day:")
for dd in days:
    n = len(found.get(dd, []))
    print("    %s  %2d  %s" % (dd, n, "#" * n))
print()
print("VSISA the EA takes 143 trades in 8.5 months = 0.8 a day, for comparison.")
