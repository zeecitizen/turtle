"""sweep_m1_more_fires.py — soften gates × fixed TP, target ≥3 fires/day at ≥60% WR."""
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

# (body, mom, vrat, sl, tp, hard, trend_bars, lookback, max_len, tag)
GRID = [
    (0.40, 0.55, 0.85, 1.5, 3.0, True,  30, 60, 40, "softer-body+mom"),
    (0.35, 0.50, 1.00, 1.5, 3.0, True,  30, 60, 40, "softest-body+mom"),
    (0.50, 0.55, 0.85, 1.5, 3.0, True,  30, 60, 40, "soft-mom-only"),
    (0.50, 0.65, 0.85, 1.5, 3.0, True,  30, 60, 40, "soft-vrat-only"),
    (0.40, 0.55, 0.85, 1.5, 3.0, True,  15, 60, 40, "soft+shorttrend"),
    (0.40, 0.55, 0.85, 1.5, 3.0, True,  10, 60, 40, "soft+verytrend"),
    (0.35, 0.50, 1.00, 2.0, 4.0, True,  30, 60, 40, "wider-SL-TP"),
    (0.50, 0.65, 0.75, 1.0, 1.5, True,  30, 60, 40, "tight-scalp"),
    (0.40, 0.55, 0.85, 1.0, 2.0, True,  30, 60, 40, "soft-tight"),
    (0.40, 0.55, 0.85, 1.5, 3.0, True,  30, 90, 60, "longer-retrace"),
]
DAYS = 7
RESULTS = []

TP_PATCH_BUY = "                if cands: tp = max(cands)\n                if tp is None or (tp - entry) < sl_dist:\n                    tp = entry + sl_dist * 2.5"
TP_REPLACE_BUY = "                tp = entry + TP_FIXED_PTS"
TP_PATCH_SELL = "                if cands: tp = min(cands)\n                if tp is None or (entry - tp) < sl_dist:\n                    tp = entry - sl_dist * 2.5"
TP_REPLACE_SELL = "                tp = entry - TP_FIXED_PTS"

for body, mom, vrat, sl, tp, hard, trend_bars, lkb, mlen, tag in GRID:
    mod = ORIG.replace("HARD_TREND       = True", f"HARD_TREND       = {hard}\nTP_FIXED_PTS     = {tp}")
    mod = mod.replace(TP_PATCH_BUY, TP_REPLACE_BUY).replace(TP_PATCH_SELL, TP_REPLACE_SELL)
    mod = (mod
        .replace('UHV_BODY_MIN     = 0.50',       f'UHV_BODY_MIN     = {body}')
        .replace('BREAKOUT_VOL_MAX_RATIO = 0.75', f'BREAKOUT_VOL_MAX_RATIO = {vrat}')
        .replace('MOM_THRESH       = 0.65',       f'MOM_THRESH       = {mom}')
        .replace('SL_BUFFER        = 2.00',       f'SL_BUFFER        = {sl}')
        .replace('RETRACE_LOOKBACK = 60',         f'RETRACE_LOOKBACK = {lkb}')
        .replace('RETRACE_MAX_LEN  = 40',         f'RETRACE_MAX_LEN  = {mlen}')
        .replace('TREND_BARS       = 30',         f'TREND_BARS       = {trend_bars}')
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
    bw = max(profit, key=lambda r: r["WR"])
    bf = max(profit, key=lambda r: r["fires"])
    print(f"BEST PNL: {bp['tag']} → fires={bp['fires']} WR={bp['WR']}% PNL={bp['PNL']}")
    print(f"BEST WR:  {bw['tag']} → fires={bw['fires']} WR={bw['WR']}% PNL={bw['PNL']}")
    print(f"MOST FIRES (profitable): {bf['tag']} → fires={bf['fires']} WR={bf['WR']}% PNL={bf['PNL']}")
Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/sweep_m1_more_fires.json").write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
