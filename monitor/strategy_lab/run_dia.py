"""Backtest UHV Diamond inside saad_vsisa_hybrid (svh_diamond) on one rig. XAUUSD_TK real ticks, Axi volume.
    py run_dia.py <rig> <variant@per> ...        results -> testing/svh_diamond_runs.jsonl"""
import json, os, sys, time
from pathlib import Path
import axi_rig

OFF = {"InpHybSaad": "false", "InpHybVsisa": "false"}
V = {   # (EA, chart, inputs)
    "plain_diamond": ("ZeeUHV_Diamond", "M1", {"InpOandaVolume": 0}),
    "dia_only":      ("svh_diamond", "M5", {**OFF, "InpHybDiaGate": 0}),
    "free":          ("svh_diamond", "M5", {"InpHybDiaGate": 0}),
    "gate_any":      ("svh_diamond", "M5", {"InpHybDiaGate": 1}),
    "gate_same":     ("svh_diamond", "M5", {"InpHybDiaGate": 2}),
    "svh_only":      ("svh_diamond", "M5", {"InpHybDia": "false"}),
    "dia_boost3_240": ("svh_diamond", "M5", {"InpHybDiaGate": 2, "InpHybSaadGate": 3, "InpHybWinMin": 240}),
    "dia_b3_120":     ("svh_diamond", "M5", {"InpHybDiaGate": 2, "InpHybSaadGate": 3, "InpHybWinMin": 120}),
    "dia_boost2_240": ("svh_diamond", "M5", {"InpHybDiaGate": 2, "InpHybSaadGate": 2, "InpHybWinMin": 240}),
}
PERIODS = {"full": ("2026.01.06", "2026.10.08"), "julo": ("2026.07.01", "2026.10.08")}
OUT = Path(r"C:\Users\zeesh\turtle\testing\svh_diamond_runs.jsonl")


def lines(t0):
    out = []
    for f in [f for f in (axi_rig.RIG / "Tester").glob("Agent-*/logs/*.log") if f.stat().st_mtime >= t0]:
        with open(f, "rb") as fh:
            fh.seek(max(0, f.stat().st_size - 6_000_000) // 2 * 2)
            txt = fh.read().decode("utf-16-le", errors="ignore").splitlines()
        st = max([i for i, ln in enumerate(txt) if "svh_diamond (research)" in ln or "[DIA]" in ln and "init" in ln.lower()] or [0])
        out += [ln.strip()[ln.find("[HYBRID"):] for ln in txt[st:] if "[HYBRID-" in ln]
    return out


axi_rig.use(sys.argv[1])
for name in sys.argv[2:]:
    var, per = name.rsplit("@", 1)
    ea, tf, sets = V[var]
    frm, to = PERIODS[per]
    ex = int(os.environ.get("HYB_EXEC", "200"))
    for attempt in range(3):
        t0 = time.time() - 2
        r = axi_rig.run(ea, "XAUUSD_TK", tf, {"InpVerbose": "false", **sets} if ea != "ZeeUHV_Diamond" else sets,
                        frm=frm, to=to, exec_mode=ex, tag=f"svhd_{var}_{per}")
        if "error" not in r and r.get("trades", 0) > 0:
            break
        time.sleep(20)
    r["hybrid"] = lines(t0)
    r.update(variant=var, per=per, exec=str(ex))
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(r) + "\n")
    print(name, round(r.get("net") or 0, 2), r.get("trades"), r.get("wr"), r.get("secs"), flush=True)
