"""Backtest bread_winner_shot variants on one rig (XAUUSD_TK real ticks, M1 chart, 200 ms, $10,000).
    py run_shot.py <rig> <variant@per> ...      results -> testing/bread_shot_runs.jsonl
Scores DAYS: a 'bread day' ends >= $10; every weekday counts (no shot = a miss)."""
import json, os, sys, time, zlib, shutil, datetime as dt
from pathlib import Path
import axi_rig

LOT = 0.11                      # $1 of price x 0.11 lots = $11 - $0.44 commission = $10.56
BASE = {"D_InpLots": LOT, "D_InpUseDiamonds": "false", "D_InpStackLots": "false", "D_InpStackMult": 1,
        "InpShotLots": LOT, "InpShotTp": 1.0, "InpShotSl": 6.0, "V_InpVerbose": "false"}
NOCTX = {"InpCtxTrend": 0, "InpCtxMinER": 0}
V = {
    "dia_win":        {"InpTrig": 1},
    "dia_win_noctx":  {"InpTrig": 1, **NOCTX},
    "dia_win_er38":   {"InpTrig": 1, "InpCtxMinER": 0.38},
    "dia_win_er38t3": {"InpTrig": 1, "InpCtxMinER": 0.38, "InpCtxTrend": 3},
    "dia_allday":     {"InpTrig": 1, "InpWinFrom": 0, "InpWinTo": 24},
    "dia_allday_noctx": {"InpTrig": 1, "InpWinFrom": 0, "InpWinTo": 24, **NOCTX},
    "rand_ctx":       {"InpTrig": 16, "InpRandDir": 0},
    "rand_trend":     {"InpTrig": 16, "InpRandDir": 0, "InpCtxMinER": 0},
    "rand_coin":      {"InpTrig": 16, "InpRandDir": 1, **NOCTX},
    "pulse_ctx":      {"InpTrig": 8},
    "pulse_er30":     {"InpTrig": 8, "InpCtxMinER": 0.30},
    "saad_ctx":       {"InpTrig": 2},
    "saad_noctx":     {"InpTrig": 2, **NOCTX},
    "vsisa_ctx":      {"InpTrig": 4},
    "vsisa_noctx":    {"InpTrig": 4, **NOCTX},
    "s_w12":          {"InpTrig": 2, "InpWinFrom": 12},
    "s_all":          {"InpTrig": 2, "InpWinFrom": 0, "InpWinTo": 24},
    "s_er38":         {"InpTrig": 2, "InpCtxMinER": 0.38},
    "s_er30":         {"InpTrig": 2, "InpCtxMinER": 0.30},
    "s_er38_w12":     {"InpTrig": 2, "InpCtxMinER": 0.38, "InpWinFrom": 12},
    "s_er30_w12":     {"InpTrig": 2, "InpCtxMinER": 0.30, "InpWinFrom": 12},
    "s_er25t2_w12":   {"InpTrig": 2, "InpCtxMinER": 0.25, "InpCtxTrend": 2, "InpWinFrom": 12},
    "s_m5_w12":       {"InpTrig": 2, "S_InpTF": 5, "InpWinFrom": 12},
    "u_ds":           {"InpTrig": 3, "InpCtxMask": 2},
    "u_ds_er38_w12":  {"InpTrig": 3, "InpCtxMask": 2, "InpCtxMinER": 0.38, "InpWinFrom": 12},
    "u_dsv_w12":      {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 12},
    "d_w12":          {"InpTrig": 1, **NOCTX, "InpWinFrom": 12},
    "u_dsv_w12_early": {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 12, "InpVsLate": "false"},
    "u_dsv_w12_late":  {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 12, "InpVsLate": "true"},
    "u_dsv_w12_slate": {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 12, "InpVsLate": "true", "InpSaadLate": "true"},
    "u_dsv_w12_vctx":  {"InpTrig": 7, "InpCtxMask": 6, "InpWinFrom": 12, "InpVsLate": "true"},
    "v_late_w12":      {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 12, "InpVsLate": "true"},
    "u_dsv_w11":       {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 11, "InpVsLate": "true"},
    "u_dsv_w10":       {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 10, "InpVsLate": "true"},
    "u_dsv_w12_er38":  {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 12, "InpVsLate": "true", "InpCtxMinER": 0.38},
    "u_dsv_w12_t2":    {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 12, "InpVsLate": "true", "InpCtxTrend": 2},
    "dv_w12":          {"InpTrig": 5, "InpCtxMask": 0, "InpWinFrom": 12, "InpVsLate": "false"},
    "dv_w12_cap8":     {"InpTrig": 5, "InpCtxMask": 0, "InpWinFrom": 12, "InpVsLate": "false", "InpDiaMaxStop": 8},
    "dsv_sny":         {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 12, "InpVsLate": "false", "InpSaadFrom": 18.5},
    "dsv_sny_cap8":    {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 12, "InpVsLate": "false", "InpSaadFrom": 18.5, "InpDiaMaxStop": 8},
    "dsv_sny_cap6":    {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 12, "InpVsLate": "false", "InpSaadFrom": 18.5, "InpDiaMaxStop": 6},
    "dsv_sny_cap10":   {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 12, "InpVsLate": "false", "InpSaadFrom": 18.5, "InpDiaMaxStop": 10},
    "v_early_w12":     {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 12, "InpVsLate": "false"},
    "dv_all":          {"InpTrig": 5, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpVsLate": "false"},
    "d_w12_cap8":      {"InpTrig": 1, **NOCTX, "InpWinFrom": 12, "InpDiaMaxStop": 8},
    # CENSUS: every trigger, every time, all day (shots per day uncapped) - building blocks for the daily policy
    "census_dsv":      {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false"},
    "census_s_noctx":  {"InpTrig": 2, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99},
    "census_v_late":   {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "true"},
    "census_v_m1":     {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpTF": 1, "V_InpMetaMode": 0, "V_InpRegimeMode": 0, "V_InpExhMode": 0},
    "census_v_m15":    {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpTF": 15, "V_InpMetaMode": 0, "V_InpRegimeMode": 0, "V_InpExhMode": 0},
    "census_s_m5":     {"InpTrig": 2, "InpCtxMask": 2, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "S_InpTF": 5},
    "census_pulse":    {"InpTrig": 8, "InpCtxMask": 8, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99},
    "census_dsv_sl10": {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "InpShotSl": 10},
    "census_dsv_sl4":  {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "InpShotSl": 4},
    "census_vA_big60":   {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpBigPct": 0.60, "V_InpBigAvg": 1.00},
    "census_vB_low120":  {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpLowVolPct": 1.20},
    "census_vC_notrend": {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpTrendTF": 0},
    "census_vD_body25":  {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpBodyFrac": 0.25},
    "census_vE_bigmode0": {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpBigMode": 0},
    "census_vF_trend60": {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpTrendTF": 60},
    "census_vAD":      {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpBigPct": 0.60, "V_InpBigAvg": 1.00, "V_InpBodyFrac": 0.25},
    "census_vD_h20":   {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpBodyFrac": 0.25, "InpShotHoldMin": 20},
    "census_vlo_h10":  {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpBigPct": 0.60, "V_InpBigAvg": 1.00, "InpShotHoldMin": 10},
    "census_vlo_h20":  {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpBigPct": 0.60, "V_InpBigAvg": 1.00, "InpShotHoldMin": 20},
    "census_vlo_h30":  {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpBigPct": 0.60, "V_InpBigAvg": 1.00, "InpShotHoldMin": 30},
    "census_vlo_h60":  {"InpTrig": 4, "InpCtxMask": 0, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "V_InpBigPct": 0.60, "V_InpBigAvg": 1.00, "InpShotHoldMin": 60},
    "census_dsv_h20":  {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "InpShotHoldMin": 20},
    "census_dsv_h30":  {"InpTrig": 7, "InpCtxMask": 2, "InpWinFrom": 0, "InpWinTo": 24, "InpShotMax": 99, "InpVsLate": "false", "InpShotHoldMin": 30},
}
PERIODS = {"full": ("2026.01.06", "2026.10.08"), "julo": ("2026.07.01", "2026.10.08"), "tune": ("2026.01.06", "2026.07.01")}
OUT = Path(r"C:\Users\zeesh\turtle\testing\bread_shot_runs.jsonl")
HOLIDAYS = {"2026.04.03"}


def weekdays(frm, to):
    d, e, out = dt.datetime.strptime(frm, "%Y.%m.%d"), dt.datetime.strptime(to, "%Y.%m.%d"), []
    while d < e:
        s = d.strftime("%Y.%m.%d")
        if d.weekday() < 5 and s not in HOLIDAYS: out.append(s)
        d += dt.timedelta(days=1)
    return out


def day_stats(r, frm, to):
    days = weekdays(frm, to)
    daily = r.get("daily") or {}
    v = [daily.get(d) for d in days]
    shot = [x for x in v if x is not None and abs(x) > 1e-9]
    n = len(days)
    bread = sum(1 for x in shot if x >= 10.0)
    near = sum(1 for x in shot if 9.0 <= x < 10.0)
    red = sum(1 for x in shot if x < 0)
    return {"weekdays": n, "shot_days": len(shot), "bread": bread, "near": near, "red": red,
            "bread_pct": round(100 * bread / n, 1), "shot_wr": round(100 * sum(1 for x in shot if x > 0) / len(shot), 1) if shot else 0,
            "worst": round(min(shot), 2) if shot else 0, "net": round(sum(shot), 2), "per_weekday": round(sum(shot) / n, 2)}


def lines(t0):
    out = []
    for f in [f for f in (axi_rig.RIG / "Tester").glob("Agent-*/logs/*.log") if f.stat().st_mtime >= t0]:
        with open(f, "rb") as fh:
            fh.seek(max(0, f.stat().st_size - 2_000_000) // 2 * 2)
            txt = fh.read().decode("utf-16-le", errors="ignore").splitlines()
        out += [ln.strip()[ln.find("[BREAD-SHOT]"):] for ln in txt if "[BREAD-SHOT]" in ln][-1:]
        out += [ln.strip()[ln.find("[BREAD-TRIG]"):] for ln in txt if "[BREAD-TRIG]" in ln][-1:]
    return out


def run(sets, per, tag):
    frm, to = PERIODS[per]
    s = dict(BASE); s.update(sets)
    for _ in range(3):
        t0 = time.time() - 2
        r = axi_rig.run("bread_winner_shot", "XAUUSD_TK", "M1", s, frm=frm, to=to, exec_mode=int(os.environ.get("HYB_EXEC", "200")),
                        tag=tag, deposit=10000, timeout=3600)
        if "error" not in r and r.get("trades", 0) > 0:
            break
        time.sleep(15)
    r["shot"] = lines(t0)
    r["days"] = day_stats(r, frm, to)
    return r


if __name__ == "__main__":
    axi_rig.use(sys.argv[1])
    for name in sys.argv[2:]:
        var, per = name.rsplit("@", 1)
        r = run({**V[var], "InpShotTag": zlib.crc32(name.encode()) % 100000}, per, f"shot_{var}_{per}")
        r.update(variant=var, per=per)
        tag = zlib.crc32(name.encode()) % 100000
        src = Path(os.path.expandvars(r"%APPDATA%")) / "MetaQuotes" / "Terminal" / "Common" / "Files" / f"bread_shots_{tag}.csv"
        if src.exists():
            shutil.copy(src, OUT.parent / f"bread_shots_{var}_{per}.csv")
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(r) + "\n")
        d = r["days"]
        print(f"{name}: bread days {d['bread']}/{d['weekdays']} ({d['bread_pct']}%) | shot days {d['shot_days']} WR {d['shot_wr']}% red {d['red']} worst {d['worst']} | net {d['net']} ({d['per_weekday']}/weekday) | {r['shot']}", flush=True)
