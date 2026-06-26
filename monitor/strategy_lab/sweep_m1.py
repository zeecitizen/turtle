from __future__ import annotations
import subprocess, json, sys, os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PY = r"C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe"
SCRIPT = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/screener_canonical_uhv_m1.py")
ORIG = SCRIPT.read_text(encoding="utf-8")

# (body_min, vol_ratio, mom_thresh, retrace_lookback)
GRID = [
    (0.40, 0.75, 0.60, 60),  # baseline
    (0.50, 0.75, 0.70, 60),
    (0.50, 0.60, 0.70, 60),
    (0.55, 0.60, 0.75, 45),  # stricter
    (0.60, 0.50, 0.80, 30),  # strictest
    (0.45, 0.65, 0.65, 90),  # wider retracement
    (0.50, 0.50, 0.75, 60),
]
OUT = []
DAYS = 10

for body, vrat, mom, lkb in GRID:
    mod = (ORIG
        .replace("UHV_BODY_MIN     = 0.40", f"UHV_BODY_MIN     = {body}")
        .replace("BREAKOUT_VOL_MAX_RATIO = 0.75", f"BREAKOUT_VOL_MAX_RATIO = {vrat}")
        .replace("MOM_THRESH       = 0.60", f"MOM_THRESH       = {mom}")
        .replace("RETRACE_LOOKBACK = 60", f"RETRACE_LOOKBACK = {lkb}")
    )
    SCRIPT.write_text(mod, encoding="utf-8")
    subprocess.run([PY, str(SCRIPT), "--days", str(DAYS)], env={**os.environ,"PYTHONIOENCODING":"utf-8"},
                   capture_output=True, text=True)
    res = json.loads(Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/results_m1_10d.json").read_text("utf-8"))
    row = dict(body=body, vrat=vrat, mom=mom, lkb=lkb,
               fires=res["setups"], W=res["wins"], L=res["losses"],
               WR=round(res["wr_pct"],1),
               PF=round(res["pf"],2) if res["pf"]!=float("inf") else "inf",
               PNL=round(res["pnl_pts"],2))
    OUT.append(row)
    print(f"  body={body} vrat={vrat} mom={mom} lkb={lkb} → fires={row['fires']} W={row['W']} L={row['L']} WR={row['WR']}% PF={row['PF']} PNL={row['PNL']:+.2f}")

SCRIPT.write_text(ORIG, encoding="utf-8")
Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/sweep_m1.json").write_text(json.dumps(OUT,indent=2), "utf-8")
best_wr = max(OUT, key=lambda r: r["WR"])
best_pnl = max(OUT, key=lambda r: r["PNL"])
best_combo = max([r for r in OUT if r["fires"]>=5 and r["WR"]>=60], key=lambda r: r["PNL"], default=None)
print(f"\nBest WR:   {best_wr}")
print(f"Best PNL:  {best_pnl}")
print(f"Best (5+ fires, ≥60% WR): {best_combo}")
