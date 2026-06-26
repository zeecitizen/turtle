"""sweep_m1_v2.py — M1 v2.62-equivalent gate sweep on last 7 days.

Goal: find any M1 config that beats M5 v2.63's +30pts/7d at 50% WR.
Hypothesis: M1 needs different SL/TP/body thresholds than M5.
"""
from __future__ import annotations
import subprocess, json, sys, os, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PY = r"C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe"
SCRIPT = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/screener_canonical_uhv_m1.py")
ORIG = SCRIPT.read_text(encoding="utf-8")

# Each config: (body, vrat, mom, sl, hard_trend, tag, lookback, max_len, retrace_max_bars)
GRID = [
    # baseline (v2.62 M1)
    (0.50, 0.75, 0.65, 2.00, True,  "baseline",     60, 40),
    # softer body
    (0.40, 0.75, 0.65, 2.00, True,  "body-0.40",    60, 40),
    (0.30, 0.75, 0.65, 2.00, True,  "body-0.30",    60, 40),
    # tighter momentum
    (0.50, 0.75, 0.75, 2.00, True,  "mom-0.75",     60, 40),
    # smaller SL
    (0.50, 0.75, 0.65, 1.00, True,  "sl-1.0",       60, 40),
    # wider SL
    (0.50, 0.75, 0.65, 3.00, True,  "sl-3.0",       60, 40),
    # no trend gate
    (0.50, 0.75, 0.65, 2.00, False, "no-trend",     60, 40),
    (0.40, 0.75, 0.60, 2.00, False, "no-trend-loose", 60, 40),
    # tighter volume
    (0.50, 0.60, 0.65, 2.00, True,  "vrat-0.60",    60, 40),
    # short retracement
    (0.50, 0.75, 0.65, 2.00, True,  "lookback-30",  30, 20),
    # very tight + many fires
    (0.40, 1.00, 0.55, 1.50, False, "scalp",        30, 20),
    # alt trend window
    (0.50, 0.75, 0.65, 2.00, True,  "trend-15",     60, 40),
]
DAYS = 7
RESULTS = []

for body, vrat, mom, sl, hard, tag, lkb, mlen in GRID:
    mod = (ORIG
        .replace('UHV_BODY_MIN     = 0.50',         f'UHV_BODY_MIN     = {body}')
        .replace('BREAKOUT_VOL_MAX_RATIO = 0.75',   f'BREAKOUT_VOL_MAX_RATIO = {vrat}')
        .replace('MOM_THRESH       = 0.65',         f'MOM_THRESH       = {mom}')
        .replace('SL_BUFFER        = 2.00',         f'SL_BUFFER        = {sl}')
        .replace('HARD_TREND       = True',         f'HARD_TREND       = {hard}')
        .replace('RETRACE_LOOKBACK = 60',           f'RETRACE_LOOKBACK = {lkb}')
        .replace('RETRACE_MAX_LEN  = 40',           f'RETRACE_MAX_LEN  = {mlen}')
    )
    # Trend-15 variant only changes TREND_BARS
    if tag == "trend-15":
        mod = mod.replace('TREND_BARS       = 30', 'TREND_BARS       = 15')
    SCRIPT.write_text(mod, encoding="utf-8")
    r = subprocess.run([PY, str(SCRIPT), "--days", str(DAYS)],
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True, timeout=120)
    try:
        res = json.loads(Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/results_m1_7d.json").read_text("utf-8"))
        row = dict(tag=tag, body=body, vrat=vrat, mom=mom, sl=sl, hard=hard, lkb=lkb,
                   fires=res["setups"], W=res["wins"], L=res["losses"],
                   WR=round(res["wr_pct"], 1),
                   PF=round(res["pf"], 2) if res["pf"]!=float("inf") else 99.99,
                   PNL=round(res["pnl_pts"], 2))
        RESULTS.append(row)
        print(f"  {tag:22s} fires={row['fires']:3d} W={row['W']:2d}/L={row['L']:2d} WR={row['WR']:5.1f}% PF={row['PF']:5.2f} PNL={row['PNL']:+8.2f}")
    except Exception as e:
        print(f"  {tag}: ERR {e}")

# Restore original
SCRIPT.write_text(ORIG, encoding="utf-8")

print(f"\n=== SWEEP COMPLETE ({len(RESULTS)} configs, 7 days M1) ===")
profitable = [r for r in RESULTS if r["PNL"] > 0]
print(f"Profitable: {len(profitable)}/{len(RESULTS)}")
if profitable:
    best_pnl = max(profitable, key=lambda r: r["PNL"])
    best_wr = max(profitable, key=lambda r: r["WR"])
    print(f"BEST PNL: {best_pnl['tag']} → fires={best_pnl['fires']} WR={best_pnl['WR']}% PNL={best_pnl['PNL']}")
    print(f"BEST WR:  {best_wr['tag']} → fires={best_wr['fires']} WR={best_wr['WR']}% PNL={best_wr['PNL']}")
else:
    print("NO profitable M1 config found in this sweep.")

Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/sweep_m1_v2.json").write_text(
    json.dumps(RESULTS, indent=2), encoding="utf-8")
