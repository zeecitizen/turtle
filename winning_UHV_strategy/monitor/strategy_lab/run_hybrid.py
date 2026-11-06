"""Backtest the Saad15 x VSISA5 hybrid variants on one rig (XAUUSD_TK real ticks, M5, 200 ms).
    py run_hybrid.py <rig> <variant> [<variant> ...]      results -> testing/hybrid_blend_runs.jsonl
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
    # blend (Zee 2026-10-14): VSISA is the outer confirmation, Saad the inner trade
    "saad_only": {"InpHybVsisa": "false"},
    "sg1_open":   {"InpHybNeedProbe": "false", "InpHybSaadGate": 1},
    "sg2_60":     {"InpHybNeedProbe": "false", "InpHybSaadGate": 2, "InpHybWinMin": 60},
    "sg2_240":    {"InpHybNeedProbe": "false", "InpHybSaadGate": 2, "InpHybWinMin": 240},
    "sg3_60":     {"InpHybNeedProbe": "false", "InpHybSaadGate": 3, "InpHybWinMin": 60},
    "sg3_240":    {"InpHybNeedProbe": "false", "InpHybSaadGate": 3, "InpHybWinMin": 240},
    "sg3_240_mloff": {"InpHybNeedProbe": "false", "InpHybSaadGate": 3, "InpHybWinMin": 240, **ML_OFF},
    "boost1_open": {"InpHybNeedProbe": "false", "InpHybSaadGate": 1, "InpHybSaadAct": 1},
    "boost2_240": {"InpHybNeedProbe": "false", "InpHybSaadGate": 2, "InpHybWinMin": 240, "InpHybSaadAct": 1},
    "boost3_240": {"InpHybNeedProbe": "false", "InpHybSaadGate": 3, "InpHybWinMin": 240, "InpHybSaadAct": 1},
    # reverse: Saad confirms VSISA
    "vg2_240":    {"InpHybVsGate": 2, "InpHybWinMin": 240},
    "vg3_60":     {"InpHybVsGate": 3, "InpHybWinMin": 60},
    "vg3_240":    {"InpHybVsGate": 3, "InpHybWinMin": 240},
    # both must agree
    "both3_240":  {"InpHybVsGate": 3, "InpHybSaadGate": 3, "InpHybWinMin": 240},
    "boost2_60":  {"InpHybNeedProbe": "false", "InpHybSaadGate": 2, "InpHybWinMin": 60, "InpHybSaadAct": 1},
    "mir_05R":    {"InpHybNeedProbe": "false", "InpHybSaadGate": 1, "InpHybSaadMature": 1, "InpHybSaadMatR": 0.5},
    "mir_be":     {"InpHybNeedProbe": "false", "InpHybSaadGate": 1, "InpHybSaadMature": 2},
    "side_big0":  {"InpHybNeedProbe": "false", "InpBigMode": 0},
    "b3_60_big0": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 3, "InpHybWinMin": 60, "InpBigMode": 0},
    "b3_120_big0": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 3, "InpHybWinMin": 120, "InpBigMode": 0},
    "b2_60": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 2, "InpHybWinMin": 60},
    "b2_90": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 2, "InpHybWinMin": 90},
    "b2_120": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 2, "InpHybWinMin": 120},
    "b2_180": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 2, "InpHybWinMin": 180},
    "b4_03_60": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 4, "InpHybSigThr": 0.3, "InpHybWinMin": 60},
    "b4_03_120": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 4, "InpHybSigThr": 0.3, "InpHybWinMin": 120},
    "b4_02_60": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 4, "InpHybSigThr": 0.2, "InpHybWinMin": 60},
    "b4_02_120": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 4, "InpHybSigThr": 0.2, "InpHybWinMin": 120},
    "b4_01_60": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 4, "InpHybSigThr": 0.1, "InpHybWinMin": 60},
    "b4_01_120": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 4, "InpHybSigThr": 0.1, "InpHybWinMin": 120},
    "b4_00_60": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 4, "InpHybSigThr": 0.0, "InpHybWinMin": 60},
    "b4_00_120": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 4, "InpHybSigThr": 0.0, "InpHybWinMin": 120},
    "b3_60": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 3, "InpHybWinMin": 60},
    "b3_120": {"InpHybNeedProbe": "false", "InpHybSaadAct": 1, "InpHybSaadGate": 3, "InpHybWinMin": 120},
}
PERIODS = {"full": ("2026.01.06", "2026.10.08"), "julo": ("2026.07.01", "2026.10.08")}
OUT = Path(r"C:\Users\zeesh\turtle\testing\hybrid_blend_runs.jsonl")


def hyb_lines(t0):
    """[HYBRID...] lines from the agent log written during this run (read only the tail: the logs are big)."""
    logs = [f for f in (axi_rig.RIG / "Tester").glob("Agent-*/logs/*.log") if f.stat().st_mtime >= t0]
    out = []
    for f in logs:
        with open(f, "rb") as fh:
            fh.seek(max(0, f.stat().st_size - 4_000_000))
            txt = fh.read().decode("utf-16-le", errors="ignore")
        lines = txt.splitlines()
        start = max([i for i, ln in enumerate(lines) if "[HYBRID Saad15xVSISA5]" in ln] or [0])   # this run only
        out += [ln.strip()[ln.find("[HYBRID"):] for ln in lines[start:] if "[HYBRID" in ln and "v1.00" not in ln]
    return out


rig = sys.argv[1]
axi_rig.use(rig)
for name in sys.argv[2:]:
    var, per = name.rsplit("@", 1)
    frm, to = PERIODS[per]
    sets = {"InpVerbose": "false", **V[var]}
    for attempt in range(3):
        t0 = time.time() - 2
        r = axi_rig.run("Hybrid_Saad15_VSISA5", "XAUUSD_TK", "M5", sets, frm=frm, to=to, exec_mode=int(__import__("os").environ.get("HYB_EXEC", "200")),
                        tag=f"hyb_{var}_{per}")
        r["exec"] = __import__("os").environ.get("HYB_EXEC", "200")
        if "error" not in r and r.get("trades", 1) != 0:
            break
        time.sleep(20)
    r["hybrid"] = hyb_lines(t0)
    r["variant"], r["per"] = var, per
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(r) + "\n")
    print(name, round(r.get("net") or 0), r.get("wr"), len(r.get("hybrid", [])), "lines", flush=True)
