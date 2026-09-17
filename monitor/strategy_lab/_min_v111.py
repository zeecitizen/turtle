"""VSISA_Minute v1.03 - HIS actual exit, and the only question that matters about it.

Zee, 2026-09-18: "i don't have a SL or TP set. i just trade this volume effort imbalance in
a way that i enter.. it goes into profit .. yaay my guess was right. close profitable
positions.. if its in loss.. i wait a minute more.. and usually it goes my way.. and i then
close profitable positions."

THIS EXIT MANUFACTURES THE WIN RATE, so the win rate is not the test. Almost any entry with
a slight edge wins 90%+ of the time if losses are never taken and price is simply given more
minutes; the trades that would have been losers are not losses yet. His 10-for-10 is mostly
this rule rather than the entry, which is why imposing a 100-point stop on it (v1.01, v1.02)
measured something he has never traded.

What a no-stop system has instead is a TAIL: many small wins and then one trade that does
not come back. That is the number to find, and a backtest can find it where four decisions
cannot. So this run is read on:

    maxDD          - how deep the worst episode actually went
    worst trade    - the one that did not come back
    streak         - how many in a row it got wrong

InpMaxAdverse is the catastrophe brake his hand does not have; the sweep includes 0 (none)
so the TRUE tail is visible, not the braked one. If the unbraked tail is ruinous, the honest
answer is that his method needs his judgement to close it, and an EA should not run it.
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
    "InpAbsorbStuck": "1.60", "InpLegMin": "0.50", "InpReleaseVol": "0.00",
    "InpBodyFrac": "0.40", "InpConfirmBars": "1",
    "InpSideBars": "3", "InpSideMult": "1.30", "InpSideMeasure": "0",  # HIS word: height
    "InpUseAbsorb": "true",
    "InpExitMode": "1", "InpProfitPts": "80", "InpMaxHoldBars": "120",
    "InpMaxAdverse": "600",
    "InpHoldBars": "10", "InpTargetPts": "150", "InpStopPts": "100",
    "InpTrailOnBar": "false", "InpDayLossStop": "0.0", "InpCoolBars": "1",
    "InpBuys": "true", "InpSells": "true", "InpSessFrom": "0", "InpSessTo": "24",
    "InpVerbose": "false",
    "InpIntrabar": "false", "InpTickWindow": "240", "InpTickSlice": "80",
    "InpTickMult": "1.40", "InpTickMinBar": "120", "InpTickStall": "0.35",
    "InpNoOpenBefore": "0", "InpBreakHour": "0", "InpBreakMin": "0",
    "InpFlatAtBreak": "false", "InpLots": "1.00",
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
        line = ("n %4d  net %+8.0f  wr %2.0f%%  exp %7.2f  maxDD %7.0f  worst streak %2d"
                % (s['n'], s['net'], s['wr'], s['net'] / s['n'], s['dd'], s['streak']))
    else:
        line = "NO TRADES"
    print("  %-28s %s" % (name, line), flush=True)


print("VSISA_Minute v1.11 - BAR ENGINE ONLY (InpIntrabar pinned false)")
print("the stuck threshold 1.20 -> 1.60 was FITTED to one trade - this is its test")
print()
show("v1.11, mode 0 (stop+tp)", {"InpExitMode": "0"})
show("v1.11, his exit brake600", {})
show("v1.11, his exit NO brake", {"InpMaxAdverse": "0", "InpMaxHoldBars": "600"})
show("stuck back to 1.20", {"InpExitMode": "0", "InpAbsorbStuck": "1.20"})
show("stuck 2.00 (looser still)", {"InpExitMode": "0", "InpAbsorbStuck": "2.00"})
show("edge 1.60", {"InpExitMode": "0", "InpSideMult": "1.60"})
show("edge 2.00", {"InpExitMode": "0", "InpSideMult": "2.00"})
show("range measure", {"InpExitMode": "0", "InpSideMeasure": "1"})
show("side window 6", {"InpExitMode": "0", "InpSideBars": "6"})
show("release-quiet back ON", {"InpExitMode": "0", "InpReleaseVol": "0.85"})
