"""saad_tune_all.py - one chart setting at a time: MT5 optimizer -> pick -> set it on the TradingView indicator -> next.

Zee 2026-10-17: "please run one by one on all settings in tradingview -> the MT5 optimizer -> pick a setting -> get optimizer
result -> set it in tradingview indicator -> and keep going till all are optimized"

    py saad_tune_all.py                 # all steps not done yet (resumes from saad_tune_log.json)
    py saad_tune_all.py --from iSlPips  # start at that setting

Each step:
  1. read the indicator's settings from the chart (Zee may have changed something meanwhile)
  2. MT5 complete optimization of that ONE EA input, XAUUSD_BB real ticks, the chart's timeframe, Jan 1 - Oct 17,
     everything else = the chart; score = OnTester (net / max drawdown, InpOptScore 0)
  3. pick: a value wins only if its score AVERAGED WITH ITS NEIGHBOURS beats the current value's (a lone spike next to two
     weak values is luck); and its own profit must beat the current profit. Otherwise the chart keeps its value.
  4. set the winner on the chart, read it back
  5. log the whole table (value, profit, PF, drawdown, win rate, trades) to saad_tune_log.json / .md
Whole-year tuning fits the year: when all steps are done the result is checked on Jan-Jun vs Jul-Oct with random delay.
"""
import json
import re
import sys
import time
from pathlib import Path

import axi_rig
import saad_optimize as so

sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_compare")
import server  # noqa: E402

HERE = Path(__file__).resolve().parent
# Zee 2026-10-17 (after the first pass): "what we're trying to get is winrate. so that we're dead sure we're making something,
# even if small amount ... since real market drops the winrate we must aim for as high as we can". --wr: score = win rate of
# whole trades (EA v1.25 InpOptScore 2), only for a profitable year; ONLY what picks the setups is tuned - stop, max risk, TP1,
# partial, trails stay frozen (his standing rule: fewer losing trades at a FIXED geometry, never buy win rate with wider stops)
WR = "--wr" in sys.argv
# Zee 2026-10-17: "first optimize for everything related to TP and SL ... since most effect should come from best TP / SL
# settings". --tpsl: the highest win rate (with neighbours) among values whose net / drawdown (with neighbours) is at least the
# chart's own - win rate may not be bought with bigger losses
TPSL = "--tpsl" in sys.argv
# Zee 2026-10-17: "have u tested other numbers of fixed $2.. let's keep optimizing for winrate." --tpwr: TP1 = Fixed $, every
# TP / SL setting that acts in that mode, pure win rate (the year must stay in profit)
TPWR = "--tpwr" in sys.argv
# --step NAME START STEP STOP: one setting on its own, win rate (Zee 2026-10-17: max risk under Fixed $1.50)
ONE = sys.argv[sys.argv.index("--step") + 1:sys.argv.index("--step") + 5] if "--step" in sys.argv else None
WR = WR or TPSL or TPWR or bool(ONE)
LOG = HERE / ("saad_tune_step_log.json" if ONE else "saad_tune_tpwr_log.json" if TPWR else "saad_tune_tpsl_log.json" if TPSL else "saad_tune_wr_log.json" if WR else "saad_tune_log.json")
MD = HERE / ("saad_tune_step_log.md" if ONE else "saad_tune_tpwr_log.md" if TPWR else "saad_tune_tpsl_log.md" if TPSL else "saad_tune_wr_log.md" if WR else "saad_tune_log.md")
SRC = server.PINE.read_text(encoding="utf-8")
PERIODS = {"1": "M1", "5": "M5", "15": "M15", "30": "M30", "60": "H1"}

# (pine variable, start, step, stop) - None = true/false; "choice" = every option of the dropdown
STEPS = [
    ("tpMode", "choice"), ("tpFixB", 0.5, 0.5, 10), ("tpFixS", 0.5, 0.5, 10), ("tpFib", 100, 10, 300), ("tpPart", 0.1, 0.1, 1.0),
    ("tpPartTr", 0.5, 0.5, 5), ("tpNoFix", "choice"),
    ("iSlPips", 20, 2, 60), ("iMaxRisk", 0, 1, 20), ("iPartial", 0, 0.05, 1), ("iBePct", 0, 0.05, 1), ("iTp1Be", None),
    ("iLTrail", 0.5, 0.5, 5), ("iSTrail", 0.5, 0.5, 5), ("iTrAtr", 0.1, 0.1, 2.0), ("pkGap", 0, 0.25, 2), ("pkLockAt", 0, 0.5, 10),
    ("pkLockUsd", 0, 0.5, 5), ("iCloseM", 0, 1, 10), ("iMinTp", 0, 1, 10), ("iLTpP", 0, 1, 10), ("iSTpP", 0, 1, 10),
    ("iPivot", 1, 1, 12), ("iLook", 10, 5, 100), ("iMaxTp", 0, 5, 60),
    ("iBreakP", 0, 1, 12), ("iBreakB", 1, 1, 5), ("iTouchP", 0, 1, 5), ("iTouchM", "choice"), ("iLRule", "choice"), ("iSLine", "choice"),
    ("iLExitAb", None), ("iUsePin", None), ("iPinDir", None), ("iPinCol", None), ("iMaru", None), ("iMaruB", 0.30, 0.03, 0.90),
    ("iHammer", None), ("iStar", None), ("iHamR", 1.0, 0.25, 5.0), ("iHamN", 0.10, 0.05, 0.60), ("iMinAtr", 0, 0.05, 1.0),
    ("iEr", 0, 0.01, 0.20), ("iErLen", 4, 2, 30), ("iGap", None), ("adRunN", 0, 1, 10), ("htReq", "choice"), ("htEma", 5, 5, 100),
    ("rpPause", 1, 1, 10),
] + [(f"rpB{i:02d}", None) for i in range(21)] + [(f"rpS{i:02d}", None) for i in range(21)]
STEPS_TPSL = [("iSlPips", 20, 2, 60), ("tpMode", "choice"), ("tpFib", 100, 10, 300), ("tpFixB", 0.5, 0.5, 10),
    ("tpFixS", 0.5, 0.5, 10), ("tpPart", 0.1, 0.1, 1.0), ("tpPartTr", 0.5, 0.5, 5), ("tpNoFix", "choice"),
    ("iPartial", 0, 0.05, 1), ("iBePct", 0, 0.05, 1), ("iTp1Be", None), ("iLTrail", 0.5, 0.5, 5), ("iSTrail", 0.5, 0.5, 5),
    ("iTrAtr", 0.1, 0.1, 2.0), ("pkGap", 0, 0.25, 2), ("pkLockAt", 0, 0.5, 10), ("pkLockUsd", 0, 0.5, 5), ("iCloseM", 0, 1, 10),
    ("iMinTp", 0, 1, 10), ("iLTpP", 0, 1, 10), ("iSTpP", 0, 1, 10), ("iPivot", 1, 1, 12), ("iLook", 10, 5, 100),
    ("iMaxTp", 0, 5, 60), ("adRunN", 0, 1, 10), ("iSlPips", 20, 2, 60)]
STEPS_TPWR = [("tpFixB", 0.5, 0.5, 10), ("tpFixS", 0.5, 0.5, 10), ("iPartial", 0, 0.05, 1), ("iBePct", 0, 0.05, 1),
    ("iTp1Be", None), ("iLTrail", 0.5, 0.5, 5), ("iSTrail", 0.5, 0.5, 5), ("pkLockAt", 0, 0.5, 10), ("pkLockUsd", 0, 0.5, 5),
    ("iCloseM", 0, 1, 10), ("iMinTp", 0, 1, 10), ("tpNoFix", "choice"), ("adRunN", 0, 1, 10), ("iSlPips", 20, 2, 60),
    ("tpFixB", 0.5, 0.5, 10), ("tpFixS", 0.5, 0.5, 10)]
# the boxes first: with every box ticked the lookbacks change nothing (17 Oct: identical 3..30)
STEPS_WR = [(f"rpB{i:02d}", None) for i in range(21)] + [(f"rpS{i:02d}", None) for i in range(21)] + [("rpPause", 1, 1, 10), ("rpLook", 3, 1, 30), ("rpLookS", 3, 1, 30),
    ("iEr", 0, 0.01, 0.20), ("iErLen", 4, 2, 30), ("iMinAtr", 0, 0.05, 1.0), ("iWick", 0.10, 0.05, 0.90),
    ("iBodyMax", 0.20, 0.05, 1.0), ("iNose", 0.0, 0.025, 0.50), ("iHamR", 1.0, 0.25, 5.0), ("iHamN", 0.10, 0.05, 0.60),
    ("iMaruB", 0.30, 0.03, 0.90), ("iBreakP", 0, 1, 12), ("iBreakB", 1, 1, 5), ("iTouchP", 0, 1, 5), ("iTouchM", "choice"),
    ("iLRule", "choice"), ("iSLine", "choice"), ("iLExitAb", None), ("iUsePin", None), ("iPinDir", None), ("iPinCol", None),
    ("iMaru", None), ("iHammer", None), ("iStar", None), ("htReq", "choice"), ("htEma", 5, 5, 100), ("iGap", None),
    ("iFast", 3, 1, 20), ("iSlow", 20, 5, 100)]


def ea_input(pv):
    if pv in server.DIRECT:
        return server.DIRECT[pv]
    if pv in server.CHOICES:
        return server.CHOICES[pv][0]
    if pv == "rpPause":
        return "InpBandPauseBars"
    m = re.match(r"rp([BS])(\d\d)$", pv)
    return f"Inp{m.group(1)}{m.group(2)}"


def is_int(pv):
    return bool(re.search(rf"^{pv}\s*=\s*input\.int\(", SRC, re.M))


def to_chart(pv, ea_val):
    """An EA value from the optimizer -> the indicator's value."""
    if pv in server.CHOICES:
        inv = {str(v): k for k, v in server.CHOICES[pv][1].items()}
        return inv[str(ea_val)]
    if str(ea_val).lower() in ("true", "false"):
        return str(ea_val).lower() == "true"
    f = float(ea_val)
    return int(round(f)) if is_int(pv) else round(f, 4)


def base_sets(sets):
    s = dict(sets, InpBarSource="0", InpOptScore="2" if WR else "0", InpOptMinTrades="150" if WR else "100", InpBoxInputs="true")
    for i in range(21):
        s[f"InpB{i:02d}"] = "true" if sets["InpBandsB"][i] == "1" else "false"
        s[f"InpS{i:02d}"] = "true" if sets["InpBandsS"][i] == "1" else "false"
    return s


def chart():
    for i in range(10):
        try:
            return server.read_settings()
        except Exception as e:                                       # TradingView busy / reloading: try again
            print(f"[tune] reading the chart failed ({e}) - retrying", flush=True)
            time.sleep(10)
    return server.read_settings()


def run_step(step, st, settings, sets):
    pv = step[0]
    ea = ea_input(pv)
    base = base_sets(sets)
    # the chart's "Pause" only acts when a range is unticked AND the mode is Pause: tune it as the EA input it maps to
    period = PERIODS.get(st["res"], "M15")
    (HERE / "saad_opt_base_sets_now.json").write_text(json.dumps(base, indent=1), encoding="utf-8")
    if len(step) == 2 and step[1] == "choice":
        opts = sorted(set(server.CHOICES[pv][1].values()), key=lambda v: str(v))
        vals = [str(v) for v in opts]
        if set(vals) == {"false", "true"}:
            rng = None
        elif all(re.fullmatch(r"\d+", v) for v in vals) and [int(v) for v in sorted(vals, key=int)] == list(range(len(vals))):
            rng = (0, 1, len(vals) - 1)
        else:
            rng = ("list", vals)
    elif len(step) == 2:
        rng = None                                                   # bool
    else:
        a, s, b = step[1:]
        c = float(base.get(ea))
        a = min(a, c - ((c - a) // s) * s if c >= a else c)          # put the chart's own value on the grid
        a = round(c - round((c - a) / s) * s, 6)
        b = max(b, c)
        rng = (a, s, b)
    cur = base.get(ea)
    if isinstance(rng, tuple) and rng and rng[0] == "list":          # values that are not a 0..N range (htReq): one pass each
        rows = []
        for v in rng[1]:
            r = axi_rig.run(server.EA, "XAUUSD_BB", period, dict(base, **{ea: v}), frm=so.FROM, to=so.TO, deposit=10000000,
                            rig=so.RIG, tag="tune_one", exec_mode=0)
            rows.append({ea: v, "Profit": r.get("net") or 0, "Profit Factor": r.get("pf"), "Equity DD %": None,
                         "Result": _score(r), "Trades": r.get("trades"), "wr": r.get("wr")})
    else:
        so.JOBS["tune"] = {"sets": "saad_opt_base_sets_now.json", "period": period, "algo": 1, "forward": False,
                           "fixed": {}, "opt": {ea: rng}}
        so.start("tune")
        rows = so._rows(Path(axi_rig._R(so.RIG)) / "reports" / "opt_tune.xml")
    return ea, cur, rows


def _score(r):
    n = r.get("trades") or 0
    net = r.get("net") or 0
    dd = float(str(r.get("dd") or "0").split("(")[0].replace(" ", "") or 0)
    if n < 100:
        return -1e9 + n
    return net / 1000.0 if net <= 0 else net / max(dd, 1.0)


def pick(ea, cur, rows, numeric):
    """-> (winner value, table sorted by value, reason)."""
    def key(r):
        v = r[ea]
        return float(v) if numeric else str(v)
    rows = sorted(rows, key=key)
    if TPSL:                                   # net / drawdown from the report's own columns (deposit $10M: DD % x 1e5 = $)
        for r in rows:
            dd = float(r.get("Equity DD %") or 0) * 1e5
            r["nd"] = float(r["Profit"]) / max(dd, 1.0) if float(r["Result"]) > 0 else -1e9
    sc = [float(r["Result"]) for r in rows]
    if numeric:
        sm = [sum(sc[max(0, i - 1):i + 2]) / len(sc[max(0, i - 1):i + 2]) for i in range(len(sc))]
    else:
        sm = sc[:]
    for r, s in zip(rows, sm):
        r["smooth"] = s
    if TPSL:
        nd = [r["nd"] for r in rows]
        nds = [sum(nd[max(0, i - 1):i + 2]) / len(nd[max(0, i - 1):i + 2]) for i in range(len(nd))] if numeric else nd[:]
        for r, s in zip(rows, nds):
            r["nd_smooth"] = s
    best = max(range(len(rows)), key=lambda i: sm[i])
    ci = next((i for i, r in enumerate(rows) if (abs(float(r[ea]) - float(cur)) < 1e-6 if numeric else str(r[ea]).lower() == str(cur).lower())), None)
    if ci is None:
        return cur, rows, "the chart's value is not on the grid - kept"
    if best == ci:
        return cur, rows, "the chart's value is already the best"
    if TPSL:
        ok = [i for i in range(len(rows)) if float(rows[i]["Result"]) > 0 and nds[i] >= nds[ci] - 1e-9]
        best = max(ok, key=lambda i: (sm[i], nds[i])) if ok else ci
        if best != ci and sm[best] > sm[ci] + 0.3:
            return rows[best][ea], rows, (f"higher win rate {sm[best]:.1f}% vs {sm[ci]:.1f}% at profit/drawdown {nds[best]:.2f} vs {nds[ci]:.2f} "
                                          f"(with neighbours), profit {float(rows[best]['Profit']):+,.0f} vs {float(rows[ci]['Profit']):+,.0f}")
        return cur, rows, f"kept: no value with a higher win rate and at least the same profit/drawdown ({sm[ci]:.1f}%, {nds[ci]:.2f})"
    if WR and sm[best] > sm[ci] + 0.3 and float(rows[best]["Result"]) > 0:      # +0.3 win-rate points with neighbours, year in profit
        return rows[best][ea], rows, f"higher win rate: {sm[best]:.1f}% vs {sm[ci]:.1f}% (with neighbours), profit {float(rows[best]['Profit']):+,.0f} vs {float(rows[ci]['Profit']):+,.0f}"
    if WR:
        return cur, rows, f"no clear win-rate gain (best {rows[best][ea]}: {sm[best]:.1f}% vs {sm[ci]:.1f}%) - kept"
    if sm[best] > sm[ci] * 1.02 + 1e-9 and float(rows[best]["Profit"]) > float(rows[ci]["Profit"]):
        return rows[best][ea], rows, f"better: score {sm[best]:.2f} vs {sm[ci]:.2f} (with neighbours), profit {float(rows[best]['Profit']):+,.0f} vs {float(rows[ci]['Profit']):+,.0f}"
    return cur, rows, f"no clear gain (best {rows[best][ea]}: {sm[best]:.2f} vs {sm[ci]:.2f}) - kept"


def set_chart(st, pv, value):
    names = server.pine_inputs()
    server.set_input(st["id"], names.index(pv), value)
    for _ in range(10):
        time.sleep(1.5)
        _, settings, _, _ = server.read_settings()
        if str(settings.get(pv)) == str(value) or settings.get(pv) == value:
            return True
    return False


def write_md(log):
    out = ["# Saad 1-min EA - one setting at a time (MT5 optimizer, Blueberry XAUUSD_BB, Jan 1 - Oct 17 2026)", "",
           "Zee 2026-10-17: *\"run one by one on all settings in tradingview -> the MT5 optimizer -> pick a setting -> ... set it in "
           "tradingview indicator -> and keep going till all are optimized\"*", "",
           "Score = net / max drawdown (OnTester). Execution delay 0 while searching. A value wins only if it beats the chart's "
           "value with its neighbours averaged in, and on profit.", "",
           "| # | Setting | Was | Now | Profit was → now | Why |", "|---|---|---|---|---|---|"]
    for i, s in enumerate(log["steps"], 1):
        wr = f" (WR {s.get('wr_was')} → {s.get('wr_now')})" if s.get("wr_was") else ""
        out.append(f"| {i} | {s['pv']} ({s['ea']}) | {s['was']} | **{s['now']}** | {s['p_was']} → {s['p_now']}{wr} | {s['why']} |")
    MD.write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {"steps": []}
    done = len(log["steps"])
    start_at = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else None
    if ONE:
        log["steps"] = log["steps"]                                  # appended to, never skipped
        steps = [(ONE[0], float(ONE[1]), float(ONE[2]), float(ONE[3]))]
        start_at = ONE[0]
    else:
        steps = None
    steps = steps or (STEPS_TPWR if TPWR else STEPS_TPSL if TPSL else STEPS_WR if WR else STEPS)
    todo = steps
    if start_at:
        todo = steps[[s[0] for s in steps].index(start_at):]
    for n, step in enumerate(todo):
        pv = step[0]
        if not start_at and n < done:
            continue
        st, settings, sets, notes = chart()
        t0 = time.time()
        numeric = len(step) == 4
        ea, cur, rows = run_step(step, st, settings, sets)
        if not rows:
            print(f"[tune] {pv}: no results - skipped", flush=True)
            continue
        win, rows, why = pick(ea, cur, rows, numeric)
        was_v = settings.get(pv)
        now_v = to_chart(pv, win)
        if str(win) != str(cur):
            ok = set_chart(st, pv, now_v)
            if not ok:
                why += " | COULD NOT SET IT ON THE CHART"
        ci = next((r for r in rows if str(r[ea]).lower() == str(cur).lower() or (numeric and abs(float(r[ea]) - float(cur)) < 1e-6)), None)
        wi = next((r for r in rows if str(r[ea]) == str(win)), None)
        rec = {"pv": pv, "ea": ea, "was": was_v, "now": now_v, "why": why, "mins": round((time.time() - t0) / 60, 1),
               "p_was": f"{float(ci['Profit']):+,.0f}" if ci else "?", "p_now": f"{float(wi['Profit']):+,.0f}" if wi else "?",
               "table": [{k: r.get(k) for k in (ea, "Profit", "Profit Factor", "Equity DD %", "Trades", "Result", "smooth", "nd", "nd_smooth")} for r in rows]}
        log["steps"].append(rec)
        LOG.write_text(json.dumps(log, indent=1), encoding="utf-8")
        write_md(log)
        if WR:
            rec["wr_was"] = f"{float(ci['Result']):.1f}%" if ci else "?"
            rec["wr_now"] = f"{float(wi['Result']):.1f}%" if wi else "?"
            LOG.write_text(json.dumps(log, indent=1), encoding="utf-8")
            write_md(log)
        print(f"[tune] {pv}: {was_v} -> {now_v} | {rec['p_was']} -> {rec['p_now']} | WR {rec.get('wr_was', '')} -> {rec.get('wr_now', '')} | {why} ({rec['mins']} min)", flush=True)
    print("[tune] all steps done", flush=True)


if __name__ == "__main__":
    main()
