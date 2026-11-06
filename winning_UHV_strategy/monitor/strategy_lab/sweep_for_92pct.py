"""sweep_for_92pct.py — try ultra-strict + fixed-TP configs to find 92%+ WR config.

Zee says she had a 92% WR before. Searching aggressive configs across both M5 and M1
to see if any yield ≥ 92% WR with at least 5 fires on 29 days.
"""
from __future__ import annotations
import subprocess, json, sys, os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PY = r"C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe"

M5 = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/screener_canonical_uhv.py")
M1 = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/screener_canonical_uhv_m1.py")
M5_ORIG = M5.read_text(encoding="utf-8")
M1_ORIG = M1.read_text(encoding="utf-8")

# (timeframe, body, mom, vrat, sl, tp_logic, hard, lookback, max_len, tag)
GRID = [
    # M5 ultra-strict
    ("M5", 0.60, 0.75, 0.50, 1.5, "fixed-3",   True, 15, 15, "M5-ultra-tight-1.5/3"),
    ("M5", 0.60, 0.75, 0.50, 2.0, "fixed-4",   True, 15, 15, "M5-ultra-tight-2/4"),
    ("M5", 0.70, 0.75, 0.50, 1.0, "fixed-2",   True, 15, 15, "M5-extreme-strict"),
    ("M5", 0.55, 0.70, 0.60, 1.5, "fixed-1.5", True, 15, 15, "M5-strict-1.5/1.5"),
    ("M5", 0.60, 0.80, 0.50, 1.0, "fixed-1",   True, 15, 15, "M5-tight-1/1"),
    ("M5", 0.55, 0.70, 0.50, 2.0, "dynamic",   True, 15, 15, "M5-strict-dynamic"),
    # M1 ultra-strict
    ("M1", 0.55, 0.70, 0.60, 1.5, "fixed-3",   True, 60, 40, "M1-strict-1.5/3"),
    ("M1", 0.60, 0.75, 0.50, 1.0, "fixed-2",   True, 60, 40, "M1-extreme-strict"),
    ("M1", 0.55, 0.70, 0.50, 1.0, "fixed-1.5", True, 60, 40, "M1-strict-1/1.5"),
    ("M1", 0.60, 0.80, 0.50, 1.5, "fixed-3",   True, 60, 40, "M1-very-strict"),
    ("M1", 0.50, 0.65, 0.60, 1.0, "fixed-1.5", True, 60, 40, "M1-scalp-strict"),
    ("M1", 0.50, 0.65, 0.85, 1.5, "fixed-3",   True, 60, 40, "M1-soft-vrat-29d"),  # the 73% winner from 7d sweep, but 29d
]

DAYS = 29
RESULTS = []

TP_PATCH_BUY = "                if cands: tp = max(cands)\n                if tp is None or (tp - entry) < sl_dist:\n                    tp = entry + sl_dist * 2.5"
TP_PATCH_SELL = "                if cands: tp = min(cands)\n                if tp is None or (entry - tp) < sl_dist:\n                    tp = entry - sl_dist * 2.5"

for tf, body, mom, vrat, sl, tp_logic, hard, lkb, mlen, tag in GRID:
    src = M5 if tf == "M5" else M1
    orig = M5_ORIG if tf == "M5" else M1_ORIG
    mod = orig
    # Apply TP logic
    if tp_logic.startswith("fixed-"):
        tp_pts = float(tp_logic.split("-")[1])
        mod = mod.replace("HARD_TREND       = True", f"HARD_TREND       = {hard}\nTP_FIXED_PTS     = {tp_pts}")
        mod = mod.replace(TP_PATCH_BUY,  "                tp = entry + TP_FIXED_PTS")
        mod = mod.replace(TP_PATCH_SELL, "                tp = entry - TP_FIXED_PTS")
    else:
        mod = mod.replace("HARD_TREND       = True", f"HARD_TREND       = {hard}")
    # gates
    mod = (mod
        .replace('UHV_BODY_MIN     = 0.50',       f'UHV_BODY_MIN     = {body}')
        .replace('BREAKOUT_VOL_MAX_RATIO = 0.75', f'BREAKOUT_VOL_MAX_RATIO = {vrat}')
        .replace('MOM_THRESH       = 0.65',       f'MOM_THRESH       = {mom}')
        .replace('SL_BUFFER        = 2.00',       f'SL_BUFFER        = {sl}')
    )
    if tf == "M5":
        mod = mod.replace('RETRACE_LOOKBACK = 15', f'RETRACE_LOOKBACK = {lkb}')
        mod = mod.replace('RETRACE_MAX_LEN  = 15', f'RETRACE_MAX_LEN  = {mlen}')
    else:
        mod = mod.replace('RETRACE_LOOKBACK = 60', f'RETRACE_LOOKBACK = {lkb}')
        mod = mod.replace('RETRACE_MAX_LEN  = 40', f'RETRACE_MAX_LEN  = {mlen}')
    src.write_text(mod, encoding="utf-8")
    cmd = [PY, str(src), "--days", str(DAYS)] + (["--fvg", "none"] if tf == "M5" else [])
    r = subprocess.run(cmd, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True, timeout=180)
    try:
        results_file = f"results_fvg-none_{DAYS}d.json" if tf == "M5" else f"results_m1_{DAYS}d.json"
        res = json.loads(Path(f"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/{results_file}").read_text("utf-8"))
        row = dict(tag=tag, tf=tf, fires=res["setups"], W=res["wins"], L=res["losses"],
                   WR=round(res["wr_pct"],1),
                   PF=round(res["pf"],2) if res["pf"]!=float("inf") else 99.99,
                   PNL=round(res["pnl_pts"],2))
        RESULTS.append(row)
        flag = "  ⭐" if row["WR"] >= 92 and row["fires"] >= 3 else ""
        print(f"  {tag:24s} fires={row['fires']:3d} W={row['W']:2d}/L={row['L']:2d} WR={row['WR']:5.1f}% PF={row['PF']:5.2f} PNL={row['PNL']:+8.2f}{flag}")
    except Exception as e:
        print(f"  {tag}: ERR {e}")

# Restore originals
M5.write_text(M5_ORIG, encoding="utf-8")
M1.write_text(M1_ORIG, encoding="utf-8")

print()
high_wr = [r for r in RESULTS if r["WR"] >= 90 and r["fires"] >= 3]
print(f"≥90% WR with ≥3 fires: {len(high_wr)}")
for r in high_wr:
    print(f"  {r['tag']:24s} {r['tf']} fires={r['fires']:3d} WR={r['WR']}% PNL={r['PNL']}")

Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/sweep_92pct.json").write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
