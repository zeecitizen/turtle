"""VSISA_Minute v1.02 - HIS crossover, plus the geometry fix.

Two corrections at once, and both were derived, not fished for.

1. THE SIGNAL. Zee, reading his own trade back: "how easy it is for X volume to move Y
   spread (height of candle) .. ok sellers seem to not be able to move it further.. ok
   buyers seem to move it relatively easily now". That is a COMPARISON between the two
   sides - progress per unit of volume for the up bars against the down bars - not a
   threshold on one bar. It is self-scaling, so it survives the tape speeding up or
   slowing down. v1.01 asked only "is this bar quiet vs the absorption", which rejects a
   buyer lifting price easily on moderate volume - exactly his signal.

2. THE GEOMETRY. Every v1.01 config lost, but the win rates were 50-57%. The EA risked
   150 to make 100: at 50% that is -25 points a trade BY CONSTRUCTION, and the measured
   -20.89 matches. Break-even needs target/stop >= (1-WR)/WR, which at 57% is 0.75 against
   a shipped 0.67. So the deficit was arithmetic before it was ever about the signal.

Both directions is ON: absorption is symmetric, and v1.01 already showed the short side is
the better half (-2.87 a trade vs -20.89) even though all ten of his live tickets were buys.

If the crossover plus honest geometry still loses, the edge is in his judgement rather than
in anything measurable here, and the EA should be abandoned rather than tuned further.
"""
import re
import subprocess
import sys

sys.path.insert(0, 'monitor/strategy_lab')
sys.stdout.reconfigure(encoding='utf-8')

from vsisa_lab import stats, PY as PYEXE, SWEEP

BASE = {
    "InpLots": "1.00", "InpTickets": "1", "InpMagicNumber": "88203", "InpMaxOpen": "1",
    "InpLook": "20", "InpAbsorbBars": "6", "InpAbsorbVol": "1.30",
    "InpAbsorbStuck": "1.20", "InpLegMin": "0.50", "InpReleaseVol": "0.85",
    "InpBodyFrac": "0.40", "InpConfirmBars": "1",
    "InpSideBars": "6", "InpSideMult": "1.30", "InpSideMeasure": "0",
    "InpUseAbsorb": "true",
    "InpHoldBars": "10", "InpTargetPts": "150", "InpStopPts": "100",
    "InpTrailOnBar": "false", "InpDayLossStop": "400.0", "InpCoolBars": "1",
    "InpBuys": "true", "InpSells": "true", "InpSessFrom": "0", "InpSessTo": "24",
    "InpVerbose": "false",
}


def run(over, frm="2026.08.15", to="2026.09.16"):
    cfg = dict(BASE)
    cfg.update({k: str(v) for k, v in over.items()})
    out = subprocess.run(
        [PYEXE, str(SWEEP), "--backtest", "--from", frm, "--to", to, "--model", "4",
         "--ea", "VSISA_Minute", "--period", "M1",
         "--inputs", " ".join("%s=%s" % kv for kv in cfg.items())],
        capture_output=True, text=True, errors="replace").stdout
    m = re.findall(r"AXI_bt_\d+", out)
    return m[-1] if m else None


def show(name, over):
    r = run(over)
    s = stats(r) if r else None
    if s:
        need = (100.0 - s['wr']) / s['wr'] if s['wr'] else 9
        line = ("n %4d  net %+8.0f  wr %2.0f%%  exp %7.2f  dd %6.0f  strk %2d  need tp/sl %.2f"
                % (s['n'], s['net'], s['wr'], s['net'] / s['n'], s['dd'], s['streak'], need))
    else:
        line = "NO TRADES"
    print("  %-26s %s" % (name, line), flush=True)


print("VSISA_Minute v1.02 - his crossover + honest geometry (M1 real ticks, both ways)")
print()
show("v1.02 defaults", {})
show("crossover ONLY (no absorb)", {"InpUseAbsorb": "false"})
show("edge 1.60", {"InpSideMult": "1.60"})
show("edge 2.00", {"InpSideMult": "2.00"})
show("edge 1.60, no absorb", {"InpSideMult": "1.60", "InpUseAbsorb": "false"})
show("measure = range (his word)", {"InpSideMeasure": "1"})
show("side window 10", {"InpSideBars": "10"})
show("tp 200 sl 100", {"InpTargetPts": "200", "InpStopPts": "100"})
show("tp 250 sl 120 hold 15", {"InpTargetPts": "250", "InpStopPts": "120",
                               "InpHoldBars": "15"})
show("long only (his way)", {"InpSells": "false"})
