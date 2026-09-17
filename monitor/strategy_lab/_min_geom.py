"""VSISA_Minute geometry - the deficit is arithmetic, not signal.

Every v1.01 config lost, but the win rates were 50%, 51% and 57% (both directions). The EA
risks 150 points to make 100: at a 50% win rate that is -25 points per trade BY
CONSTRUCTION, and the measured -20.89 matches. A perfect signal on that geometry still
loses.

Break-even needs target/stop >= (1-WR)/WR. At the observed 57% that is 0.75; the shipped
pair is 0.67. So this sweep is derived from the arithmetic, NOT from tuning until something
prints green - the prediction is that the payoff ratio, not the absorption reading, is what
is missing. If a ratio above 0.75 does not turn it positive, the signal has no edge and the
EA should be abandoned rather than fitted.

Both directions is ON throughout: absorption is symmetric (heavy volume that cannot push
price UP is demand exhausting), and the tester already said the short side is the better
half, even though all ten of his live tickets were buys.
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
    "InpBodyFrac": "0.40", "InpConfirmBars": "1", "InpHoldBars": "5",
    "InpTargetPts": "100", "InpStopPts": "150", "InpTrailOnBar": "false",
    "InpDayLossStop": "400.0", "InpCoolBars": "1", "InpBuys": "true",
    "InpSells": "true", "InpSessFrom": "0", "InpSessTo": "24", "InpVerbose": "false",
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


def show(name, over, ratio):
    r = run(over)
    s = stats(r) if r else None
    if s:
        need = (100.0 - s['wr']) / s['wr'] if s['wr'] else 9
        line = ("n %4d  net %+8.0f  wr %2.0f%%  exp %7.2f  dd %6.0f  | tp/sl %.2f  need %.2f"
                % (s['n'], s['net'], s['wr'], s['net'] / s['n'], s['dd'], ratio, need))
    else:
        line = "NO TRADES"
    print("  %-24s %s" % (name, line), flush=True)


print("VSISA_Minute - does the PAYOFF RATIO explain the deficit? (M1 real ticks, both ways)")
print()
show("tp100 sl150 (shipped)", {}, 0.67)
show("tp100 sl100", {"InpStopPts": "100"}, 1.00)
show("tp150 sl100", {"InpTargetPts": "150", "InpStopPts": "100"}, 1.50)
show("tp200 sl100", {"InpTargetPts": "200", "InpStopPts": "100"}, 2.00)
show("tp150 sl80", {"InpTargetPts": "150", "InpStopPts": "80"}, 1.88)
show("tp250 sl120 hold10", {"InpTargetPts": "250", "InpStopPts": "120",
                            "InpHoldBars": "10"}, 2.08)
show("tp150 sl100 hold10", {"InpTargetPts": "150", "InpStopPts": "100",
                            "InpHoldBars": "10"}, 1.50)
