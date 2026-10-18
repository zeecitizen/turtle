"""saad_tasks_queue.py - Zee's tasks of 2026-10-18 for the MT5 optimizer, run one after another (one optimizer at a time: the laptop
runs out of memory otherwise). Every result is a real MT5 Strategy Tester run on Blueberry real ticks (XAUUSD_BB).

  Task 1  max risk x breakeven x SL (+ trend-alignment timeframe x its EMA), 1 min, full year, for the best PROFIT FACTOR
  Task 7  the Saad_strategy_15min v1.23 self-tuner (saad15_selftune.py)
  Task 5  the best value of EVERY setting (one at a time from the base), 1 min, full year
  Task 2  every setting at once (minus the ranges), genetic, learn Jan-Jun, MT5 forward-tests Jul-Oct

    py saad_tasks_queue.py              # all, in that order
    py saad_tasks_queue.py task5 task2  # only these

Base = Zee's 1-min chart frozen in saad_tasks_base_m1.json. Searches run with no delay (same numbers every pass); the winners are
checked again with random delay on Jan-Jun and Jul-Oct apart. Results: saad_strategy_1min_optimized/optimizer_results/*.md + .json
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import axi_rig
import saad_optimize as so

HERE = Path(__file__).resolve().parent
OUTD = HERE.parents[1] / "saad_strategy_1min_optimized" / "optimizer_results"
OUTD.mkdir(parents=True, exist_ok=True)
STATUS = OUTD / "status.md"
EA = "Saad_strategy_1min"
BASE = json.load(open(HERE / "saad_tasks_base_m1.json"))["ea_inputs"]
BASE = dict(BASE, InpBarSource="0", InpLogCsv="false")
YEAR = ("2026.01.01", "2026.10.17")


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M} {msg}"
    print(line, flush=True)
    with open(STATUS, "a", encoding="utf-8") as f:
        f.write(line + "  \n")


def optimize(name, base, opt, frm, to, algo=1, forward=None, score="4", min_trades="1"):
    """MT5 optimization of `opt` on top of `base` -> rows (dicts) from MT5's own report (and the forward report)."""
    sets_file = HERE / f"saad_opt_base_sets_q{name[:2]}.json"      # one file per task (the base is rewritten before every run)
    sets_file.write_text(json.dumps(dict(base, InpOptScore=score, InpOptMinTrades=min_trades), indent=1), encoding="utf-8")
    so.FROM, so.TO = frm, to
    if forward:
        so.FORWARD = forward
    so.JOBS[name] = {"sets": sets_file.name, "period": "M1", "algo": algo, "forward": bool(forward), "delay": 0, "fixed": {}, "opt": opt}
    t0 = time.time()
    so.start(name)
    R = Path(axi_rig._R(so.RIG)) / "reports"
    rows = so._rows(R / f"opt_{name}.xml")
    fwd = so._rows(R / f"opt_{name}.forward.xml") if forward and (R / f"opt_{name}.forward.xml").exists() else []
    log(f"  {name}: {len(rows)} passes in {(time.time() - t0) / 60:.0f} min")
    return rows, fwd


def num(r, k):
    try:
        return float(r.get(k) or 0)
    except ValueError:
        return 0.0


def single(sets, frm, to, delay=-1, tag="q"):
    for a in range(3):
        r = axi_rig.run(EA, "XAUUSD_BB", "M1", dict(sets, InpOptScore="4", InpOptMinTrades="1"), frm=frm, to=to, deposit=10000000, rig="axi", tag=tag, exec_mode=delay)
        if r.get("error") not in ("authorization failed", "no report"):
            break
        axi_rig.kill_rig("axi"); time.sleep(5)
    ts = r.get("trade_stats") or {}
    n, aw, al, net = ts.get("n") or 0, ts.get("avg_win") or 0, ts.get("avg_loss") or 0, r.get("net") or 0
    wr = 100 * ((net + n * -al) / (aw - al)) / n if n and aw - al else 0
    return {"net": net, "wr": wr, "pf": r.get("pf"), "n": n, "dd": r.get("dd"), "months": r.get("months") or {}, "err": r.get("error")}


def check(label, sets):
    """the winners again, with random delay: full year + the two halves"""
    out = {k: single(sets, a, b) for k, (a, b) in {"year": YEAR, "Jan-Jun": ("2026.01.01", "2026.07.01"), "Jul-Oct": ("2026.07.01", "2026.10.17")}.items()}
    log(f"  check {label}: " + " | ".join(f"{k} net {v['net']:+,.0f} WR {v['wr']:.1f}% PF {v['pf']}" for k, v in out.items()))
    return out


def md_row(cells):
    return "| " + " | ".join(str(c) for c in cells) + " |"


# ── Task 1 ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def task1():
    log("TASK 1: max risk x breakeven x SL + trend alignment, profit factor, 1 min full year")
    base = dict(BASE, InpSlMode="0")
    best = dict(base)
    pick = lambda rows: max(rows, key=lambda r: num(r, "Result")) if rows else None
    A, _ = optimize("t1_htf_a", best, {"InpHtfIdx": (0, 1, 5), "InpHtfEma": (10, 10, 100)}, *YEAR, score="5", min_trades="500")
    a = pick(A); best.update(InpHtfIdx=a["InpHtfIdx"], InpHtfEma=a["InpHtfEma"])
    B, _ = optimize("t1_sl_risk_be", best, {"InpSlPips": (2, 2, 20), "InpMaxRiskUsd": (0, 1, 10), "InpBeTpPct": (0, 0.25, 1)}, *YEAR, score="5", min_trades="500")
    b = pick(B); best.update(InpSlPips=b["InpSlPips"], InpMaxRiskUsd=b["InpMaxRiskUsd"], InpBeTpPct=b["InpBeTpPct"])
    C, _ = optimize("t1_htf_c", best, {"InpHtfIdx": (0, 1, 5), "InpHtfEma": (10, 10, 100)}, *YEAR, score="5", min_trades="500")
    c = pick(C); best.update(InpHtfIdx=c["InpHtfIdx"], InpHtfEma=c["InpHtfEma"])
    chk_base, chk_best = check("base (Zee's chart)", base), check("Task 1 best", best)
    HTF = {"0": "off", "1": "5 min", "2": "15 min", "3": "30 min", "4": "1 hour", "5": "4 hours"}
    L = ["# Task 1 - max risk x breakeven x SL x trend alignment (1 min, full year, best PROFIT FACTOR)", "",
         "MT5 Strategy Tester, Saad_strategy_1min v1.37, XAUUSD_BB (Blueberry real ticks), M1, Jan 1 - Oct 16 2026, no delay while searching. "
         "Base = Zee's 1-min chart of 18 Oct. Score = profit factor = gross profit / gross loss (dollars won per dollar lost), 0 if fewer than 500 trades.", "",
         "## Winner", "", md_row(["Setting", "Zee's chart", "Best"]), md_row(["---"] * 3)]
    for k in ("InpSlPips", "InpMaxRiskUsd", "InpBeTpPct", "InpHtfIdx", "InpHtfEma"):
        L.append(md_row([k, base.get(k, "-1 (off)") if k != "InpHtfIdx" else "off", (HTF.get(str(int(float(best[k])))) if k == "InpHtfIdx" else best[k])]))
    L += ["", "## Checked with random delay", "", md_row(["", "Year net", "WR", "PF", "Jan-Jun net", "Jul-Oct net"]), md_row(["---"] * 6)]
    for lab, ch in (("Zee's chart", chk_base), ("Task 1 best", chk_best)):
        L.append(md_row([lab, f"{ch['year']['net']:+,.0f}", f"{ch['year']['wr']:.1f}%", ch['year']['pf'], f"{ch['Jan-Jun']['net']:+,.0f}", f"{ch['Jul-Oct']['net']:+,.0f}"]))
    for title, rows, keys in (("Trend alignment (first pass)", A, ("InpHtfIdx", "InpHtfEma")), ("SL x max risk x breakeven - best 25", B, ("InpSlPips", "InpMaxRiskUsd", "InpBeTpPct")),
                              ("Trend alignment (with the best SL / risk / BE)", C, ("InpHtfIdx", "InpHtfEma"))):
        L += ["", f"## {title}", "", md_row(list(keys) + ["PF", "Net", "Trades", "Max DD %"]), md_row(["---"] * (len(keys) + 4))]
        for r in sorted(rows, key=lambda r: -num(r, "Result"))[:25]:
            L.append(md_row([HTF.get(r[k], r[k]) if k == "InpHtfIdx" else r[k] for k in keys] + [f"{num(r, 'Result'):.3f}", f"{num(r, 'Profit'):+,.0f}", r["Trades"], r["Equity DD %"][:6]]))
    (OUTD / "TASK1_sl_risk_breakeven_trend.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    json.dump({"A": A, "B": B, "C": C, "best": best, "check_base": chk_base, "check_best": chk_best}, open(OUTD / "TASK1.json", "w"), indent=1)
    log("TASK 1 done -> TASK1_sl_risk_breakeven_trend.md")
    return best


# ── Task 5 ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
SWEEP = [  # (EA input, start, step, stop) - bools/choices as 0/1 ranges; the chop filter first (Zee asked for it by name)
    ("InpChopEr", 0, 0.02, 0.40), ("InpChopErLook", 4, 4, 32),
    ("InpEmaFast", 2, 1, 10), ("InpEmaSlow", 4, 2, 20),
    ("InpWickMin", 0.2, 0.1, 0.8), ("InpBodyMax", 0.2, 0.1, 1.0), ("InpNoseMax", 0, 0.05, 0.5), ("InpMaruBody", 0.3, 0.05, 0.9),
    ("InpHamRatio", 1, 0.5, 4), ("InpHamNose", 0.1, 0.05, 0.6), ("InpMinRangeAtr", 0, 0.1, 1.2),
    ("InpUsePin", None), ("InpPinDir", None), ("InpPinColor", None), ("InpMarubozu", None), ("InpHammer", None), ("InpStar", None),
    ("InpLongRule", 0, 1, 2), ("InpShortLine", 0, 1, 2), ("InpTouchMode", 0, 1, 1), ("InpTouchPips", 0, 1, 6), ("InpLongExitAbove", None),
    ("InpBreakBars", 1, 1, 4), ("InpBreakPips", 0, 1, 10),
    ("InpSlMode", 0, 1, 1), ("InpSlPips", 2, 2, 24), ("InpMaxRiskUsd", 0, 1, 12),
    ("InpTpMode", 0, 1, 3), ("InpTpFixUsdB", 0.5, 0.5, 5), ("InpTpFixUsdS", 0.5, 0.5, 5), ("InpTpFibPct", 100, 25, 400),
    ("InpTpPartPct", 0.1, 0.1, 1.0), ("InpTpPartTrailUsd", 0.2, 0.2, 3.0), ("InpTpNoFixSkip", None),
    ("InpPartialPct", 0, 0.1, 1.0), ("InpBeTpPct", 0, 0.1, 1.0), ("InpTp1Be", None),
    ("InpLongTrailUsd", 0.5, 0.5, 4), ("InpShortTrailUsd", 0.5, 0.5, 4), ("InpTrailAtr", 0.1, 0.2, 2.5), ("InpTrailGapUsd", 0, 0.1, 1.0),
    ("InpLockAtUsd", 0, 1, 6), ("InpLockUsd", 0, 0.5, 3), ("InpCloseLossMins", 0, 1, 10), ("InpMinTpPips", 0, 2, 20),
    ("InpLongTpPips", 0, 2, 20), ("InpShortTpPips", 0, 2, 20), ("InpSwingPivot", 1, 1, 12), ("InpSwingLook", 10, 10, 100), ("InpMaxTpPips", 0, 10, 60),
    ("InpGapCancel", None), ("InpCutRunN", 0, 1, 10), ("InpHtfIdx", 0, 1, 5), ("InpHtfEma", 5, 5, 100),
    ("InpCoolN", 0, 1, 10), ("InpCoolDir", 0, 1, 1), ("InpCoolWinOnly", None), ("InpReEntry", None), ("InpReEntryBars", 5, 15, 125),
]


def task5():
    log("TASK 5: the best value of every setting (one at a time from Zee's chart), 1 min full year")
    res = {}
    for item in SWEEP:
        k = item[0]
        rng = None if len(item) == 2 else item[1:]
        try:
            rows, _ = optimize("t5_" + k, BASE, {k: rng}, *YEAR, score="4")
        except BaseException as e:
            log(f"  {k}: failed {e}")
            continue
        res[k] = [{"v": r[k], "wr": num(r, "Result"), "pf": num(r, "Profit Factor"), "net": num(r, "Profit"), "deals": int(num(r, "Trades")),
                   "dd": num(r, "Equity DD %")} for r in rows]
        json.dump(res, open(OUTD / "TASK5.json", "w"), indent=1)
        write_task5(res)
    log("TASK 5 sweeps done; checking the combined best values")
    combo = dict(BASE)
    for k, rows in res.items():
        ok = [r for r in rows if r["deals"] >= 600]
        if not ok:
            continue
        b = max(ok, key=lambda r: r["pf"])
        cur = next((r for r in rows if _same(r["v"], BASE.get(k))), None)
        if cur is None or b["pf"] > cur["pf"] + 0.01:
            combo[k] = b["v"]
    res["_combined"] = {"sets": {k: v for k, v in combo.items() if str(BASE.get(k)) != str(v)}, "check_base": check("base", BASE), "check_combined": check("all best values together", combo)}
    json.dump(res, open(OUTD / "TASK5.json", "w"), indent=1)
    write_task5(res)
    log("TASK 5 done -> TASK5_best_value_per_setting.md")


def _same(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return str(a).lower() == str(b).lower()


def write_task5(res):
    L = ["# Task 5 - the best value of every setting (1 min, full year)", "",
         "MT5 Strategy Tester, Saad_strategy_1min, XAUUSD_BB (Blueberry real ticks), M1, Jan 1 - Oct 16 2026, no delay. "
         "Each setting is swept ON ITS OWN from Zee's 1-min chart of 18 Oct (everything else unchanged). PF = profit factor; "
         "WR = whole-trade win rate; 'best' = highest PF with at least 600 trades.", "",
         md_row(["Setting", "Chart value", "Chart: PF / WR / net", "Best value", "Best: PF / WR / net", "Effect on PF"]), md_row(["---"] * 6)]
    for k, rows in res.items():
        if k.startswith("_"):
            continue
        cur = next((r for r in rows if _same(r["v"], BASE.get(k))), None)
        ok = [r for r in rows if r["deals"] >= 600] or rows
        b = max(ok, key=lambda r: r["pf"])
        f = lambda r: f"{r['pf']:.3f} / {r['wr']:.1f}% / {r['net']:+,.0f}" if r else "-"
        L.append(md_row([k, BASE.get(k), f(cur), f"**{b['v']}**", f(b), f"{b['pf'] - (cur['pf'] if cur else 0):+.3f}" if cur else "-"]))
    if "_combined" in res:
        c = res["_combined"]
        L += ["", "## All the best values together (checked with random delay)", "", "Changed: " + ", ".join(f"{k}={v}" for k, v in c["sets"].items()), "",
              md_row(["", "Year net", "WR", "PF", "Jan-Jun net", "Jul-Oct net"]), md_row(["---"] * 6)]
        for lab, ch in (("Zee's chart", c["check_base"]), ("all best values", c["check_combined"])):
            L.append(md_row([lab, f"{ch['year']['net']:+,.0f}", f"{ch['year']['wr']:.1f}%", ch['year']['pf'], f"{ch['Jan-Jun']['net']:+,.0f}", f"{ch['Jul-Oct']['net']:+,.0f}"]))
    L += ["", "## Every value of every setting", ""]
    for k, rows in res.items():
        if k.startswith("_"):
            continue
        L.append(f"**{k}** (chart: {BASE.get(k)}): " + " · ".join(f"{r['v']}: PF {r['pf']:.2f}, WR {r['wr']:.0f}%, {r['net'] / 1000:+.0f}k" for r in sorted(rows, key=lambda r: float(r['v']) if str(r['v']).replace('.', '').replace('-', '').isdigit() else 0)))
        L.append("")
    (OUTD / "TASK5_best_value_per_setting.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ── Task 2 ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def task2():
    log("TASK 2: every setting at once (minus ranges), genetic, learn Jan-Jun, forward Jul-Oct - hours")
    opt = {}
    for item in SWEEP:
        opt[item[0]] = None if len(item) == 2 else item[1:]
    rows, fwd = optimize("t2_all", BASE, opt, "2026.01.01", "2026.10.17", algo=2, forward="2026.07.01", score="5", min_trades="250")
    byp = {r["Pass"]: r for r in rows}
    top = sorted(fwd or rows, key=lambda r: -num(r, "Forward Result" if fwd else "Result"))[:10]
    L = ["# Task 2 - every setting at once (minus the ranges), MT5 genetic optimizer, 1 min", "",
         "Saad_strategy_1min v1.37, XAUUSD_BB (Blueberry real ticks), M1. Learned on Jan 1 - Jun 30 2026; MT5 then ran every result on "
         "Jul 1 - Oct 16 (forward, never used to choose). Score = profit factor, 0 with fewer than 250 trades.", "",
         f"Passes: {len(rows)}", "", md_row(["#", "PF Jan-Jun", "PF Jul-Oct (forward)", "Net Jan-Jun", "Net Jul-Oct"]), md_row(["---"] * 5)]
    for i, r in enumerate(top, 1):
        b = byp.get(r["Pass"], r)
        L.append(md_row([i, f"{num(b, 'Result'):.3f}", f"{num(r, 'Forward Result'):.3f}" if fwd else "-", f"{num(b, 'Profit'):+,.0f}", f"{num(r, 'Profit'):+,.0f}" if fwd else "-"]))
    if top:
        best = dict(BASE)
        for k in opt:
            if k in top[0]:
                best[k] = top[0][k]
        chk = check("Task 2 best (forward)", best)
        L += ["", "## The best forward result, checked again with random delay", "",
              md_row(["", "Year net", "WR", "PF", "Jan-Jun net", "Jul-Oct net"]), md_row(["---"] * 6),
              md_row(["Task 2 best", f"{chk['year']['net']:+,.0f}", f"{chk['year']['wr']:.1f}%", chk['year']['pf'], f"{chk['Jan-Jun']['net']:+,.0f}", f"{chk['Jul-Oct']['net']:+,.0f}"]),
              "", "Settings: " + ", ".join(f"{k}={best[k]}" for k in opt if str(BASE.get(k)) != str(best[k]))]
    (OUTD / "TASK2_genetic_all_settings.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    json.dump({"rows": rows, "forward": fwd}, open(OUTD / "TASK2.json", "w"))
    log("TASK 2 done -> TASK2_genetic_all_settings.md")


def task7():
    log("TASK 7: Saad_strategy_15min v1.23 self-tuner (tree search with pruning across time folds + ensemble vote)")
    import saad15_selftune
    saad15_selftune.main(log=log)
    import shutil
    shutil.copy(saad15_selftune.MD, OUTD / "TASK7_saad15_selftune.md")
    log("TASK 7 done -> TASK7_saad15_selftune.md")


if __name__ == "__main__":
    want = [a for a in sys.argv[1:]] or ["task1", "task7", "task5", "task2"]
    axi_rig.compile_ea(EA, rig="axi")
    for t in want:
        try:
            globals()[t]()
        except BaseException as e:
            log(f"{t.upper()} FAILED: {e!r}")
    log("queue finished")
