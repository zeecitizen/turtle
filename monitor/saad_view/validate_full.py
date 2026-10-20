"""validate_full.py - the settings that used to say "MT5 only": each group switched on, the Turtle TV Tester (sim_full) vs MT5 (rig axi7, no delay)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "monitor" / "strategy_lab"))
sys.stdout.reconfigure(encoding="utf-8")
import sim, axi_rig
EA = "Saad_strategy_15min"
dfl = axi_rig.ea_defaults(EA)
V123 = {"InpExitMode": "0", "InpBandsB": "1" * 21, "InpBandsS": "1" * 21, "InpAdxMin": "0"}
VAR = {
    "v1.23 exits (TP1, partial, BE, $ trail, TP2/3)": V123,
    "v1.23 exits, no ride (ATR trail off, broker TP)": dict(V123, InpRide="false", InpTrail="false", InpShortTouch="0", InpLongTouch="0"),
    "entry mode 1 (dip)": {"InpEntryMode": "1", "InpBreakBars": "2"},
    "entry mode 2 (sweep)": {"InpEntryMode": "2", "InpSweepPips": "3"},
    "filters: chop 0.11, trend align, no Fridays, cool 4": {"InpChopEr": "0.11", "InpTrendAlign": "true", "InpSkipDow": "5", "InpCoolBars": "4"},
    "risk 1% sizing + day loss $3000": {"InpRiskPct": "1", "InpDayLossUsd": "3000"},
    "2 positions, BE at $8, lock": {"InpMaxPos": "2", "InpBeUsd": "8", "InpLockAtUsd": "6", "InpLockUsd": "2"},
    "HTF 60 trend + ADX 20 length + max bars 12": {"InpHtfMin": "60", "InpAdxPeriod": "20", "InpMaxBars": "12"},
}
axi_rig.kill_rig("axi7"); axi_rig.compile_ea(EA, rig="axi7")
rows = []
for name, s in VAR.items():
    a = sim.score(sim.simulate(dict(dfl, **s))[0], 1)
    r = axi_rig.run(EA, "XAUUSD_BB", "M15", dict(s, InpLogCsv="false"), frm="2026.01.01", to="2026.10.17", deposit=100000, rig="axi7", tag="vfull", exec_mode=0)
    rows.append({"name": name, "sim": a, "mt5": {k: r.get(k) for k in ("net", "pf", "trades")}})
    print(f"{name:52} sim {a['net']:+11,.0f} PF {a['pf']:5.2f} n {a['n']:4} | MT5 {r.get('net'):+11,.0f} PF {r.get('pf')} n {r.get('trades')}", flush=True)
(HERE / "simdata" / "validate_full.json").write_text(json.dumps(rows, indent=1))
