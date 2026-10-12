"""Small-account survival: one-month runs starting at each month, per deposit tier.
usage: python phaseE2.py RIG DEP [DEP ...]   -> appends to zee_tiers_monthly.jsonl"""
import sys, json, subprocess
from pathlib import Path
P = r"C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\python.exe"
HERE = Path(__file__).parent
rig, deps = sys.argv[1], sys.argv[2:]
months = [("2026.01.06", "2026.02.01"), ("2026.02.01", "2026.03.01"), ("2026.03.01", "2026.04.01"),
          ("2026.04.01", "2026.05.01"), ("2026.05.01", "2026.06.01"), ("2026.06.01", "2026.07.01"),
          ("2026.07.01", "2026.08.01"), ("2026.08.01", "2026.09.01"), ("2026.09.01", "2026.10.01")]
arms = ["InpLots=0.01", "InpRiskPct=2,InpMinLotRiskPct=50"]
for dep in deps:
    for frm, to in months:
        subprocess.run([P, str(HERE / "saad_v4.py"), "--rig", rig, "--nocompile", "--ea", "Saad_strategy_15min",
                        "--exec", "200", "--period", "M15", "--symbol", "XAUUSD_TK", "--from", frm, "--to", to,
                        "--deposit", dep, "--leverage", "1:1000", "--out", "zee_tiers_monthly.jsonl"] + arms)
