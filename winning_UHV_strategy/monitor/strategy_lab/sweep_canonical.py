"""sweep_canonical.py — sweep UHV body min × breakout vol ratio × days, log WR/PF/PNL."""
from __future__ import annotations
import subprocess, json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PY = r"C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe"
SCRIPT = r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/screener_canonical_uhv.py"
SRC = Path(SCRIPT)
ORIG = SRC.read_text(encoding="utf-8")

# (body_min, breakout_vol_ratio, mom_thresh)
GRID = [
    (0.35, 1.00, 0.55),
    (0.35, 0.75, 0.55),
    (0.40, 0.75, 0.60),
    (0.50, 0.75, 0.65),
    (0.50, 0.60, 0.65),
    (0.50, 1.00, 0.65),
    (0.40, 1.00, 0.55),
    (0.30, 1.00, 0.55),
]

DAYS = 10
OUT = []

for body, vrat, mom in GRID:
    mod = (ORIG
        .replace("UHV_BODY_MIN     = 0.50", f"UHV_BODY_MIN     = {body}")
        .replace("BREAKOUT_VOL_MAX_RATIO = 0.75", f"BREAKOUT_VOL_MAX_RATIO = {vrat}")
        .replace("MOM_THRESH       = 0.65", f"MOM_THRESH       = {mom}")
    )
    SRC.write_text(mod, encoding="utf-8")
    r = subprocess.run([PY, SCRIPT, "--days", str(DAYS), "--fvg", "none"],
                       capture_output=True, text=True, env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    # parse last results json
    res_p = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/results_fvg-none_10d.json")
    d = json.loads(res_p.read_text(encoding="utf-8"))
    row = {
        "body": body, "vrat": vrat, "mom": mom,
        "fires": d["setups"], "W": d["wins"], "L": d["losses"], "open": d["open"],
        "WR": round(d["wr_pct"], 1),
        "PF": round(d["pf"], 2) if d["pf"] != float("inf") else "inf",
        "PNL": round(d["pnl_pts"], 2),
    }
    OUT.append(row)
    print(f"  body={body} vrat={vrat} mom={mom} → fires={row['fires']} W={row['W']} L={row['L']} WR={row['WR']}% PF={row['PF']} PNL={row['PNL']:+.2f}")

# Restore original
SRC.write_text(ORIG, encoding="utf-8")

# Save sweep
out_p = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/sweep.json")
out_p.write_text(json.dumps(OUT, indent=2), encoding="utf-8")
print("\n=== Sweep complete ===")
print(f"Best WR: {max(OUT, key=lambda r: r['WR'])}")
print(f"Best PNL: {max(OUT, key=lambda r: r['PNL'])}")
print(f"Most fires (with WR≥70%): {sorted([r for r in OUT if r['WR']>=70], key=lambda r: -r['fires'])[:2]}")
