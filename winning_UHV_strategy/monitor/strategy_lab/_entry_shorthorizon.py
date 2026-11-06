"""ENTRY QUALITY AT HIS TIMESCALE - seconds and minutes, not months.

Zee, 2026-09-18: "its not about months anymore.. we're talking about minutes and seconds
here. based on the meters i take a trade every few minutes / seconds.. so its much more
granular than trying to get a monthly winrate.. its more like winrate this 10 minutes."

He is right that the earlier test may have measured the wrong thing. The 1:1 race used a
100-point target and a 100-point stop; on gold that can take twenty or thirty minutes to
resolve, so a signal whose edge lasts two minutes and then decays would score ~50% there
even if it were genuinely predictive at HIS horizon.

So this runs the same fair symmetric race at the distances he actually trades:

    20 points  - a fast scalp, resolves in a minute or two
    30 points
    50 points
    100 points - the original, kept for comparison

Symmetric every time, so 50% is still the coin flip and nothing can be flattered by a
clever exit. If the hit rate CLIMBS as the distance shrinks, the edge is real but
short-lived, and the meter should be used for fast trades exactly as he describes. If it
is flat near 44% at every distance, the signal does not predict direction at any horizon
and the honest answer stands.

Four windows, three of them never used to build or tune anything.
"""
import re
import subprocess
import sys

sys.path.insert(0, 'monitor/strategy_lab')
sys.stdout.reconfigure(encoding='utf-8')

from vsisa_lab import stats, PY as PYEXE, SWEEP

WINDOWS = [
    ("AUG-SEP", "2026.08.15", "2026.09.16"),
    ("JUN-JUL", "2026.06.01", "2026.07.15"),
    ("JUL-AUG", "2026.07.15", "2026.08.15"),
    ("APR-MAY", "2026.04.01", "2026.05.15"),
]

BASE = {
    "InpLots": "1.00", "InpTickets": "1", "InpMagicNumber": "88203", "InpMaxOpen": "1",
    "InpLook": "20", "InpAbsorbBars": "6", "InpAbsorbVol": "1.30",
    "InpAbsorbStuck": "1.20", "InpLegMin": "0.50", "InpReleaseVol": "0.85",
    "InpBodyFrac": "0.40", "InpConfirmBars": "1",
    "InpSideBars": "3", "InpSideMult": "1.30", "InpSideMeasure": "0",
    "InpUseAbsorb": "true",
    "InpExitMode": "0", "InpHoldBars": "9999", "InpTrailOnBar": "false",
    "InpProfitPts": "80", "InpMaxHoldBars": "600", "InpMaxAdverse": "0",
    "InpDayLossStop": "0.0", "InpCoolBars": "1",
    "InpBuys": "true", "InpSells": "true", "InpSessFrom": "0", "InpSessTo": "24",
    "InpVerbose": "false", "InpMeterOnly": "false",
    "InpIntrabar": "false", "InpTickWindow": "240", "InpTickSlice": "80",
    "InpTickMult": "1.40", "InpTickMinBar": "120", "InpTickStall": "0.35",
    "InpNoOpenBefore": "0", "InpBreakHour": "0", "InpBreakMin": "0",
    "InpFlatAtBreak": "false",
}


def run(over, frm, to):
    cfg = dict(BASE)
    cfg.update({k: str(v) for k, v in over.items()})
    out = subprocess.run(
        [PYEXE, str(SWEEP), "--backtest", "--from", frm, "--to", to, "--model", "4",
         "--ea", "VSISA_Minute", "--period", "M1",
         "--inputs", " ".join("%s=%s" % kv for kv in cfg.items())],
        capture_output=True, text=True, errors="replace").stdout
    m = re.findall(r"AXI_bt_\d+", out)
    return m[-1] if m else None


def judge(label, over):
    cells, rates, n = [], [], 0
    for lab, frm, to in WINDOWS:
        r = run(over, frm, to)
        s = stats(r) if r else None
        if s:
            cells.append("%3.0f%% (%d)" % (s['wr'], s['n']))
            rates.append(s['wr'])
            n += s['n']
        else:
            cells.append("    -     ")
    avg = sum(rates) / len(rates) if rates else 0
    worst = min(rates) if rates else 0
    verdict = "EDGE" if worst > 50 else ("promising" if avg > 52 else "")
    print("  %-22s %s | avg %3.0f%%  worst %3.0f%%  n=%-5d %s"
          % (label, " ".join("%-11s" % c for c in cells), avg, worst, n, verdict),
          flush=True)


print("SAME SIGNAL, MEASURED AT HIS HORIZON - symmetric race, 50% = coin flip")
print("if the hit rate climbs as the distance shrinks, the edge is real but short-lived")
print()
print("  %-22s %s" % ("distance", " ".join("%-11s" % w[0] for w in WINDOWS)))
print("  " + "-" * 92)
for d in ("20", "30", "50", "100"):
    judge("%s pts each way" % d, {"InpTargetPts": d, "InpStopPts": d})
