"""Backtest Trinity_1min on one rig (XAUUSD_TK real ticks, M1 chart, 200 ms).
    py run_tri.py <rig> <variant@per> ...      results -> testing/trinity_runs.jsonl
DEPOSIT env var (default 500)."""
import json, os, sys, time
from pathlib import Path
import axi_rig

OFF = {"InpUseSaad": "false", "InpUseVsisa": "false", "InpUseDia": "false"}
V = {
    # transplant checks: each engine alone at its ORIGINAL timeframe and size, on the M1 chart
    "chk_saad":  {**OFF, "InpUseSaad": "true", "S_InpTF": 15, "S_InpLots": 1.0},
    "chk_vsisa": {**OFF, "InpUseVsisa": "true", "V_InpTF": 5, "V_InpLots": 0.28, "V_InpVerbose": "false"},
    "chk_dia":   {**OFF, "InpUseDia": "true", "D_InpTF": 1, "D_InpLots": 0.02, "D_InpStackMult": 2},
    # 0.01 lots, native timeframes, on the M1 chart
    "native001": {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false"},
    "native001_nodia": {"S_InpTF": 15, "V_InpTF": 5, "InpUseDia": "false", "V_InpVerbose": "false"},
    "dialog":   {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "true"},
    "df_none":  {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false"},
    "df_tr1":   {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaTrend": 1},
    "df_tr2":   {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaTrend": 2},
    "df_tr3":   {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaTrend": 3},
    "df_er":    {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaMinER": 0.25},
    "df_noopp": {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaVsNoOpp": "true"},
    "df_ny":    {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaHourFrom": 15, "InpDiaHourTo": 20},
    "df_reg":   {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaRegSkip": 4},
    "df_tr3_noopp_ny": {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaTrend": 3, "InpDiaVsNoOpp": "true", "InpDiaHourFrom": 15, "InpDiaHourTo": 20},
    "dfA_er38":  {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaMinER": 0.38},
    "dfB_er45":  {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaMinER": 0.45},
    "dfC_er38_tr3": {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaMinER": 0.38, "InpDiaTrend": 3},
    "dfD_er38_reg": {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaMinER": 0.38, "InpDiaRegSkip": 4},
    "dfE_er42_reg": {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaMinER": 0.42, "InpDiaRegSkip": 4},
    "dfF_er38_reg_tr3": {"S_InpTF": 15, "V_InpTF": 5, "D_InpTF": 1, "V_InpVerbose": "false", "InpDiaLog": "false", "InpDiaMinER": 0.38, "InpDiaRegSkip": 4, "InpDiaTrend": 3},
    "default":  {},
    # everything on true 1-minute candles, untuned
    "pure1m": {"S_InpTF": 1, "V_InpTF": 1, "D_InpTF": 1, "V_InpVerbose": "false", "V_InpMetaMode": 0, "V_InpRegimeMode": 0, "V_InpExhMode": 0},
}
PERIODS = {"full": ("2026.01.06", "2026.10.08"), "julo": ("2026.07.01", "2026.10.08"), "janjun": ("2026.01.06", "2026.07.01")}
OUT = Path(r"C:\Users\zeesh\turtle\testing\trinity_runs.jsonl")


def stats(t0):
    out = []
    for f in [f for f in (axi_rig.RIG / "Tester").glob("Agent-*/logs/*.log") if f.stat().st_mtime >= t0]:
        with open(f, "rb") as fh:
            fh.seek(max(0, f.stat().st_size - 3_000_000) // 2 * 2)
            txt = fh.read().decode("utf-16-le", errors="ignore").splitlines()
        st = max([i for i, ln in enumerate(txt) if "[TRINITY] v" in ln] or [0])
        out += [ln.strip()[ln.find("[TRINITY"):] for ln in txt[st:] if "[TRINITY-STATS]" in ln or "[TRINITY-DIA]" in ln]
    return out


def run(sets, per, tag, deposit=None):
    frm, to = PERIODS[per]
    dep = deposit or int(os.environ.get("DEPOSIT", "500"))
    for _ in range(3):
        t0 = time.time() - 2
        r = axi_rig.run("Trinity_1min", "XAUUSD_TK", "M1", sets, frm=frm, to=to, exec_mode=int(os.environ.get("HYB_EXEC", "200")),
                        tag=tag, deposit=dep, timeout=3600)
        if "error" not in r and r.get("trades", 0) > 0:
            break
        time.sleep(15)
    r["engines"] = stats(t0)
    days = r.get("day_stats", {}).get("days") or 0
    r["per_day"] = round(r.get("net", 0) / days, 2) if days else 0
    return r


if __name__ == "__main__":
    axi_rig.use(sys.argv[1])
    for name in sys.argv[2:]:
        var, per = name.rsplit("@", 1)
        dep = 25000 if var.startswith(("chk_", "dialog")) else None
        r = run(V[var], per, f"tri_{var}_{per}", dep)
        r.update(variant=var, per=per)
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(r) + "\n")
        print(name, round(r.get("net") or 0, 2), "per trading day", r["per_day"], "dd", r.get("dd"), r["engines"], flush=True)
