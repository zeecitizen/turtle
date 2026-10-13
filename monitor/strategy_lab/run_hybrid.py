"""Backtest the Saad15 x VSISA5 hybrid variants on one rig (XAUUSD_TK real ticks, M5, 200 ms).
    py run_hybrid.py <rig> <variant> [<variant> ...]      results -> testing/hybrid_runs.jsonl
Per-engine, per-position win rates come from the EA's own [HYBRID-STATS] lines in the agent log."""
import json, sys, time
from pathlib import Path
import axi_rig

ML_OFF = {"InpMetaMode": 0, "InpRegimeMode": 0, "InpExhMode": 0}
V = {
    "m1_05R":      {"InpHybMature": 1, "InpHybMatureR": 0.5},
    "m1_10R":      {"InpHybMature": 1, "InpHybMatureR": 1.0},
    "m0_open":     {"InpHybMature": 0},
    "m2_be":       {"InpHybMature": 2},
    "m1_05R_close": {"InpHybMature": 1, "InpHybMatureR": 0.5, "InpHybCloseAdds": "true"},
    "side_by_side": {"InpHybNeedProbe": "false"},
    "vsisa_only":  {"InpHybSaad": "false", "InpHybNeedProbe": "false"},
    "m1_05R_mloff": {"InpHybMature": 1, "InpHybMatureR": 0.5, **ML_OFF},
    "side_mloff":  {"InpHybNeedProbe": "false", **ML_OFF},
    "vsisa_only_mloff": {"InpHybSaad": "false", "InpHybNeedProbe": "false", **ML_OFF},
}
PERIODS = {"full": ("2026.01.06", "2026.10.08"), "julo": ("2026.07.01", "2026.10.08")}
OUT = Path(r"C:\Users\zeesh\turtle\testing\hybrid_runs.jsonl")


def hyb_lines(t0):
    """[HYBRID...] lines from the agent log written during this run (read only the tail: the logs are big)."""
    logs = [f for f in (axi_rig.RIG / "Tester").glob("Agent-*/logs/*.log") if f.stat().st_mtime >= t0]
    out = []
    for f in logs:
        with open(f, "rb") as fh:
            fh.seek(max(0, f.stat().st_size - 4_000_000))
            txt = fh.read().decode("utf-16-le", errors="ignore")
        out += [ln.strip()[ln.find("[HYBRID"):] for ln in txt.splitlines() if "[HYBRID" in ln and "v1.00" not in ln]
    return out


rig = sys.argv[1]
axi_rig.use(rig)
for name in sys.argv[2:]:
    var, per = name.rsplit("@", 1)
    frm, to = PERIODS[per]
    sets = {"InpVerbose": "false", **V[var]}
    for attempt in range(3):
        t0 = time.time() - 2
        r = axi_rig.run("Hybrid_Saad15_VSISA5", "XAUUSD_TK", "M5", sets, frm=frm, to=to, exec_mode=200,
                        tag=f"hyb_{var}_{per}")
        if "error" not in r and r.get("trades", 1) != 0:
            break
        time.sleep(20)
    r["hybrid"] = hyb_lines(t0)
    r["variant"], r["per"] = var, per
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(r) + "\n")
    print(name, r.get("net"), r.get("hybrid"), flush=True)
