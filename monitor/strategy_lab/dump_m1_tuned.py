"""dump_m1_tuned.py — re-run M1 with the proven "soft-vrat-only" config and save fires."""
from __future__ import annotations
import subprocess, json, sys, os
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
PY = r"C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe"
M1 = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/screener_canonical_uhv_m1.py")
ORIG = M1.read_text(encoding="utf-8")

# soft-vrat-only config: body=0.50, mom=0.65, vrat=0.85, sl=1.5, tp=3.0, hard=True
TP_PATCH_BUY = "                if cands: tp = max(cands)\n                if tp is None or (tp - entry) < sl_dist:\n                    tp = entry + sl_dist * 2.5"
TP_PATCH_SELL = "                if cands: tp = min(cands)\n                if tp is None or (entry - tp) < sl_dist:\n                    tp = entry - sl_dist * 2.5"

mod = ORIG.replace("HARD_TREND       = True", "HARD_TREND       = True\nTP_FIXED_PTS     = 3.0")
mod = mod.replace(TP_PATCH_BUY,  "                tp = entry + TP_FIXED_PTS")
mod = mod.replace(TP_PATCH_SELL, "                tp = entry - TP_FIXED_PTS")
mod = (mod
    .replace('UHV_BODY_MIN     = 0.50',       'UHV_BODY_MIN     = 0.50')
    .replace('BREAKOUT_VOL_MAX_RATIO = 0.75', 'BREAKOUT_VOL_MAX_RATIO = 0.85')
    .replace('MOM_THRESH       = 0.65',       'MOM_THRESH       = 0.65')
    .replace('SL_BUFFER        = 2.00',       'SL_BUFFER        = 1.50')
)
M1.write_text(mod, encoding="utf-8")
try:
    r = subprocess.run([PY, str(M1), "--days", "7"],
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True, timeout=180)
    print(r.stdout[-1500:])
finally:
    M1.write_text(ORIG, encoding="utf-8")
