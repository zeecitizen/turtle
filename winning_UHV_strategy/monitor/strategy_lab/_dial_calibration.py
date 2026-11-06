"""DOES THE LEFT DIAL PREDICT ANYTHING? - calibrating imbalance strength against outcomes.

Zee, 2026-09-18: "can u test this dial's accuracy somehow? the left dial.. as u said
nothing in it has been calibrated against what happened next".

Right. Every constant in ImbalanceStrength (weights 45/30/25, the 0.60 and 1.30 cutoffs,
the 80% READY line) was chosen by me so that three examples he showed me scored sensibly.
That is not calibration, it is decoration, and the dial has been telling him READY without
anyone ever checking whether READY means anything.

THE TEST. Replicate the MQL5 arithmetic minute by minute over the whole OANDA table, then
look at what price actually did over the next 1, 3, 5 and 10 minutes IN THE DIRECTION THE
DIAL POINTED. Bucket by strength. If the dial works, the hit rate should CLIMB with the
bucket: readings of 80-100% should beat readings of 0-20%. If every bucket sits near the
same number, the strength score carries no information and the READY light is theatre.

*** THIS IS PYTHON, SO IT IS A HYPOTHESIS, NOT A PROMOTION (CLAUDE.md) ***
It measures bar-to-bar price moves on the OANDA feed. It has no spread, no slippage and no
execution. The spread on gold is roughly 20-30 points, so a column is reported net of 25
points as well - a move has to clear that before it is worth anything. Python's measured
win-rate haircut on this project is ~16 points; treat any hit rate here as optimistic.
"""
import csv
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

CSV = r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_bars.csv"

# --- these MUST match the EA's inputs or the study measures a different instrument
METER_BARS = 5
DECAY = 0.55
BASE_BARS = 20
SPREAD_PTS = 0.25          # ~25 points, a realistic gold round trip
DIR_MARGIN = 1.15          # the EA needs one side 15% cheaper before it calls a direction

rows = [r for r in csv.reader(open(CSV)) if len(r) >= 6]
B = [{"t": r[0], "o": float(r[1]), "h": float(r[2]), "l": float(r[3]),
      "c": float(r[4]), "v": float(r[5])} for r in rows]
print("OANDA minutes loaded: %d   (%s .. %s)" % (len(B), B[0]["t"], B[-1]["t"]))


def strength_at(n):
    """The EA's ImbalanceStrength, computed as if the newest closed bar were B[n]."""
    frm = n - METER_BARS + 1
    if frm - BASE_BARS < 0:
        return None
    upP = dnP = upV = dnV = volNow = wsum = 0.0
    for i in range(frm, n + 1):
        w = DECAY ** (n - i)
        body = B[i]["c"] - B[i]["o"]
        v = B[i]["v"]
        volNow += v * w
        wsum += w
        if v <= 0:
            continue
        if body > 0:
            upP += body * w; upV += v * w
        elif body < 0:
            dnP += -body * w; dnV += v * w
    if wsum <= 0:
        return None
    volNow /= wsum
    base = [B[i]["v"] for i in range(frm - BASE_BARS, frm)]
    volBase = sum(base) / len(base)
    if volBase <= 0:
        return None

    effUp = upP / upV if upV > 0 else 0.0
    effDn = dnP / dnV if dnV > 0 else 0.0
    if effUp + effDn <= 0:
        return None
    gap = abs(effUp - effDn) / (effUp + effDn)
    winV, loseV = (upV, dnV) if effUp >= effDn else (dnV, upV)
    share = winV / (winV + loseV) if (winV + loseV) > 0 else 0.5
    push = volNow / volBase

    g = min(1.0, gap / 0.60)
    s = min(1.0, max(0.0, (share - 0.50) * 2.0))
    p = min(1.0, max(0.0, (push - 0.70) / 0.60))
    st = min(1.0, g * 0.45 + s * 0.30 + p * 0.25)

    # the EA's direction rule
    d = 0
    if effUp > effDn * DIR_MARGIN:
        d = 1
    elif effDn > effUp * DIR_MARGIN:
        d = -1
    return st, d


HORIZONS = (1, 3, 5, 10)
BUCKETS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
stat = defaultdict(lambda: defaultdict(list))
called = 0

for n in range(BASE_BARS + METER_BARS, len(B) - max(HORIZONS) - 1):
    r = strength_at(n)
    if not r:
        continue
    st, d = r
    if d == 0:
        continue
    called += 1
    entry = B[n]["c"]
    for hz in HORIZONS:
        move = (B[n + hz]["c"] - entry) * d      # positive = the dial was right
        for lo, hi in BUCKETS:
            if lo <= st < hi:
                stat[(lo, hi)][hz].append(move)
                break

print("readings with a direction called: %d\n" % called)
print("%-14s %7s | %s" % ("strength", "n", "  ".join("%-22s" % ("next %d min" % h)
                                                     for h in HORIZONS)))
print("%-14s %7s | %s" % ("", "", "  ".join("%-22s" % "right%  net25%  avg pts"
                                            for _ in HORIZONS)))
print("-" * 116)
for lo, hi in BUCKETS:
    cells = []
    n0 = 0
    for hz in HORIZONS:
        v = stat[(lo, hi)][hz]
        n0 = max(n0, len(v))
        if not v:
            cells.append("%-22s" % "-")
            continue
        right = 100.0 * sum(1 for x in v if x > 0) / len(v)
        net = 100.0 * sum(1 for x in v if x > SPREAD_PTS) / len(v)
        avg = sum(v) / len(v) * 100.0          # in points
        cells.append("%-22s" % ("%5.1f%%  %5.1f%%  %+7.1f" % (right, net, avg)))
    print("%-14s %7d | %s" % ("%.0f-%.0f%%" % (lo * 100, hi * 100), n0, "  ".join(cells)))

print()
print("READ IT DOWN THE COLUMNS: if the dial works, right%% should CLIMB from the top row")
print("to the bottom. Flat columns mean the strength score carries no information.")
print("net25%% is the share that cleared a realistic 25-point spread - the honest bar.")
