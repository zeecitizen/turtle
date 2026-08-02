"""sweep_m1_fixed_tp.py — try FIXED TPs on M1 (scalp style)."""
from __future__ import annotations
import subprocess, json, sys, os
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
PY = r"C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe"
SCRIPT = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/screener_canonical_uhv_m1.py")
ORIG = SCRIPT.read_text(encoding="utf-8")

# Patch simulate() to use a fixed-pt TP instead of finding peak.
# Configs: (sl_pts, tp_pts, body, mom, hard, vrat, tag)
GRID = [
    (1.0, 0.5, 0.50, 0.65, True,  0.75, "SL1-TP0.5"),
    (1.0, 1.0, 0.50, 0.65, True,  0.75, "SL1-TP1"),
    (1.0, 1.5, 0.50, 0.65, True,  0.75, "SL1-TP1.5"),
    (2.0, 1.0, 0.50, 0.65, True,  0.75, "SL2-TP1"),
    (2.0, 2.0, 0.50, 0.65, True,  0.75, "SL2-TP2"),
    (2.0, 3.0, 0.50, 0.65, True,  0.75, "SL2-TP3"),
    (1.0, 1.0, 0.40, 0.55, False, 1.00, "noTrend-SL1-TP1"),
    (1.0, 0.5, 0.40, 0.55, False, 1.00, "noTrend-SL1-TP0.5"),
    (1.5, 3.0, 0.50, 0.65, True,  0.75, "SL1.5-TP3"),
    (1.5, 1.5, 0.50, 0.70, True,  0.60, "tighter-SL1.5-TP1.5"),
]
DAYS = 7
RESULTS = []

# Patch the TP block to use a fixed pt distance
TP_PATCH_BUY = "                if cands: tp = max(cands)\n                if tp is None or (tp - entry) < sl_dist:\n                    tp = entry + sl_dist * 2.5"
TP_REPLACE_BUY = "                tp = entry + TP_FIXED_PTS"

TP_PATCH_SELL = "                if cands: tp = min(cands)\n                if tp is None or (entry - tp) < sl_dist:\n                    tp = entry - sl_dist * 2.5"
TP_REPLACE_SELL = "                tp = entry - TP_FIXED_PTS"

for sl_pts, tp_pts, body, mom, hard, vrat, tag in GRID:
    mod = ORIG
    # Inject TP_FIXED_PTS into the tunables block
    mod = mod.replace("HARD_TREND       = True", f"HARD_TREND       = {hard}\nTP_FIXED_PTS     = {tp_pts}")
    # Replace TP calculations
    mod = mod.replace(TP_PATCH_BUY, TP_REPLACE_BUY)
    mod = mod.replace(TP_PATCH_SELL, TP_REPLACE_SELL)
    mod = (mod
        .replace('UHV_BODY_MIN     = 0.50',       f'UHV_BODY_MIN     = {body}')
        .replace('BREAKOUT_VOL_MAX_RATIO = 0.75', f'BREAKOUT_VOL_MAX_RATIO = {vrat}')
        .replace('MOM_THRESH       = 0.65',       f'MOM_THRESH       = {mom}')
        .replace('SL_BUFFER        = 2.00',       f'SL_BUFFER        = {sl_pts}')
    )
    SCRIPT.write_text(mod, encoding="utf-8")
    r = subprocess.run([PY, str(SCRIPT), "--days", str(DAYS)],
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True, timeout=120)
    try:
        res = json.loads(Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/results_m1_7d.json").read_text("utf-8"))
        row = dict(tag=tag, fires=res["setups"], W=res["wins"], L=res["losses"],
                   WR=round(res["wr_pct"],1),
                   PF=round(res["pf"],2) if res["pf"]!=float("inf") else 99.99,
                   PNL=round(res["pnl_pts"],2))
        RESULTS.append(row)
        print(f"  {tag:24s} fires={row['fires']:3d} W={row['W']:2d}/L={row['L']:2d} WR={row['WR']:5.1f}% PF={row['PF']:5.2f} PNL={row['PNL']:+8.2f}")
    except Exception as e:
        print(f"  {tag}: ERR {e}")

SCRIPT.write_text(ORIG, encoding="utf-8")
profit = [r for r in RESULTS if r["PNL"] > 0]
print(f"\nProfitable: {len(profit)}/{len(RESULTS)}")
if profit:
    bp = max(profit, key=lambda r: r["PNL"])
    print(f"BEST: {bp['tag']} → fires={bp['fires']} WR={bp['WR']}% PNL={bp['PNL']}")
Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/sweep_m1_fixed_tp.json").write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
