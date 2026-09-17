"""MT5 test of VSISA_Minute v1.01 - absorption then release.

v1.00 read his method backwards: it hunted quiet efficient bars anywhere and REJECTED the
very bar he bought (22:28, volume 1.46x the loudest recent bar, price stuck). It found 9
setups a month and lost about the spread on each (-$22.51 over 183 trades at confirm 1).

v1.01 looks for the two-stage pattern the replay of his own window actually showed: price
falls into a LOUD window that goes NOWHERE (supply absorbed), then a QUIET decided bar (the
release). Across the whole OANDA M1 table that fires 4.0 times a session - his cadence.

The exit is corrected too. His fills ran 87-161 POINTS, which is 3-5 M1 bars, not one; a
one-bar exit takes a ~20 point slice and pays ~25 of it to the spread.

M1, real ticks, one month. HYPOTHESIS until this says otherwise - four decisions is not a
strategy, and a config that only prints a profit after enough tuning is fitted, not found.
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
    "InpSells": "false", "InpSessFrom": "0", "InpSessTo": "24", "InpVerbose": "false",
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
        line = ("n %4d  net %+8.0f  wr %2.0f%%  dd %6.0f  exp %7.2f  strk %2d"
                % (s['n'], s['net'], s['wr'], s['dd'], s['net'] / s['n'], s['streak']))
    else:
        line = "NO TRADES"
    print("  %-26s %s" % (name, line), flush=True)
    return s


print("VSISA_Minute v1.01 ABSORPTION - M1 real ticks, 15 Aug - 16 Sep, 1.00 lot")
print()
show("v1.01 defaults", {})
show("hold 3", {"InpHoldBars": "3"})
show("hold 8", {"InpHoldBars": "8"})
show("tp 160 sl 200", {"InpTargetPts": "160", "InpStopPts": "200"})
show("tp 0 (time exit only)", {"InpTargetPts": "0"})
show("absorb 1.15 (looser)", {"InpAbsorbVol": "1.15"})
show("absorb 1.60 (stricter)", {"InpAbsorbVol": "1.60"})
show("release 0.70", {"InpReleaseVol": "0.70"})
show("stuck 0.80 (tighter)", {"InpAbsorbStuck": "0.80"})
show("both directions", {"InpSells": "true"})
show("trail, no tp", {"InpTrailOnBar": "true", "InpTargetPts": "0", "InpHoldBars": "20"})
