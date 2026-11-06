"""ENTRY QUALITY ONLY - the deal of 2026-09-18.

Zee: "then perfect me the entry 100% and i'll exit myself. i'll start the EA only when i'm
sitting on the computer."

So the exit is no longer mine to design, and every test tonight that scored a whole
strategy was measuring my exit as much as his entry. This measures the entry ALONE.

THE YARDSTICK: a symmetric 1:1 race. Target 100 points, stop 100 points, nothing else -
no ratchet, no trailing, no time exit, no brake. Then the win rate answers exactly one
question: after this signal, does price travel 100 points MY way before it travels 100
points against? That number cannot be flattered by a clever exit, and it cannot be
manufactured by refusing to take losses the way his real exit does.

    > 50%  the entry has genuine directional edge
    = 50%  a coin flip - the entry is worthless whatever exit is bolted on
    < 50%  the signal is inverted

Judged on ALL FOUR windows at once, with the out-of-sample ones weighted equally to the
one everything was found on. A config that only clears 50% in AUG-SEP is the same
selection artefact that has already fooled me three times tonight.
"""
import re
import subprocess
import sys

sys.path.insert(0, 'monitor/strategy_lab')
sys.stdout.reconfigure(encoding='utf-8')

from vsisa_lab import stats, PY as PYEXE, SWEEP

WINDOWS = [
    ("AUG-SEP", "2026.08.15", "2026.09.16"),   # where everything was found
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
    # THE YARDSTICK - symmetric, dumb, identical for every config
    "InpExitMode": "0", "InpTargetPts": "100", "InpStopPts": "100",
    "InpHoldBars": "9999", "InpTrailOnBar": "false",
    "InpProfitPts": "80", "InpMaxHoldBars": "600", "InpMaxAdverse": "0",
    "InpDayLossStop": "0.0", "InpCoolBars": "1",
    "InpBuys": "true", "InpSells": "true", "InpSessFrom": "0", "InpSessTo": "24",
    "InpVerbose": "false",
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


def judge(name, over):
    """Print the 1:1 hit rate in every window. The worst window is the verdict."""
    cells, rates, total = [], [], 0
    for lab, frm, to in WINDOWS:
        r = run(over, frm, to)
        s = stats(r) if r else None
        if s:
            cells.append("%3.0f%% (%d)" % (s['wr'], s['n']))
            rates.append(s['wr'])
            total += s['n']
        else:
            cells.append("   -    ")
    worst = min(rates) if rates else 0
    avg = sum(rates) / len(rates) if rates else 0
    flag = "EDGE" if worst > 50 else ("mixed" if avg > 50 else "")
    print("  %-24s %s | avg %3.0f%%  worst %3.0f%%  n=%-4d %s"
          % (name, " ".join("%-10s" % c for c in cells), avg, worst, total, flag),
          flush=True)


print("ENTRY QUALITY - symmetric 1:1 race (TP 100 / SL 100), no exit cleverness")
print("does price go 100 pts your way before 100 pts against? >50%% = real edge")
print()
print("  %-24s %s" % ("config", " ".join("%-10s" % w[0] for w in WINDOWS)))
print("  " + "-" * 86)
judge("v1.20 defaults", {})
judge("absorb 1.15", {"InpAbsorbVol": "1.15"})
judge("absorb 1.60", {"InpAbsorbVol": "1.60"})
judge("release 0.70 (quieter)", {"InpReleaseVol": "0.70"})
judge("release 1.00 (looser)", {"InpReleaseVol": "1.00"})
judge("edge 1.60", {"InpSideMult": "1.60"})
judge("edge 2.00", {"InpSideMult": "2.00"})
judge("confirm 2 bars", {"InpConfirmBars": "2"})
judge("body 0.60", {"InpBodyFrac": "0.60"})
judge("leg 1.00 (deeper dip)", {"InpLegMin": "1.00"})
judge("LONG only", {"InpSells": "false"})
judge("SHORT only", {"InpBuys": "false"})
