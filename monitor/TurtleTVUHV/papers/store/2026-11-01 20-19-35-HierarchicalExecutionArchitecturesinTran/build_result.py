"""Compose result.json + setting.json for the Research page from mt5_years.json (the judge) and the
saved candidate files. Run after the MT5 passes finished. The verdict text is filled in from the numbers."""
import json, os, datetime as dt
ID = "2026-11-01 20-19-35-HierarchicalExecutionArchitecturesinTran"
STORE = r"C:\Users\zeesh\turtle\monitor\saad_view\papers\store\\" + ID
SAVED = r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved"
TITLE = "Hierarchical Execution Architectures in Transformer-Driven Algorithmic Trading: Bridging the Signal-to-Profit Gap via Dynamic Sub-Trade Lot Allocation"
BASE = "2026-11-01 08-38-10"
CAND = ID + " candidate"
CANDB = ID + " candidate B"
rows = json.load(open(r"C:\Users\zeesh\turtle\monitor\saad_view\research\mt5_years.json", encoding="utf-8"))
TV = json.load(open(os.path.join(STORE, "tester_variants.json"), encoding="utf-8"))


def wr_of(x):
    ts = x.get("trade_stats") or {}
    if x.get("wr"):
        return round(float(str(x["wr"]).rstrip("%")), 2)
    n, aw, al, net = ts.get("n") or 0, ts.get("avg_win") or 0, ts.get("avg_loss") or 0, x.get("net") or 0
    if n and (aw - al):
        return round(100 * (net - n * al) / (aw - al) / n, 2)
    return 0.0


def mt5_block(gate):
    rs = [x for x in rows if x.get("gate") == gate and x.get("period") == "M15" and x.get("year") in (2023, 2024, 2025, 2026)]
    out = {"rows": [], "total_none": {"trades": 0, "net": 0.0, "wr": 0.0}, "total_random": {"trades": 0, "net": 0.0, "wr": 0.0}}
    acc = {"none": [0, 0.0, 0.0], "random": [0, 0.0, 0.0]}      # trades, net, wins
    for x in sorted(rs, key=lambda r: (r["year"], r["delay"])):
        ts = x.get("trade_stats") or {}
        n = ts.get("n") or x.get("trades") or 0
        wr = wr_of(x)
        try:
            pf = float(str(x.get("pf") or "0").replace(" ", ""))
        except ValueError:
            pf = 0.0
        out["rows"].append({"year": int(x["year"]), "delay": x["delay"], "trades": int(n), "net": round(float(x.get("net") or 0), 2), "wr": wr,
                            "worst": round(-abs(float(ts.get("largest_loss") or 0)), 2), "pf": pf, "error": x.get("error")})
        a = acc[x["delay"]]; a[0] += n; a[1] += float(x.get("net") or 0); a[2] += n * wr / 100.0
    for d in ("none", "random"):
        n, net, w = acc[d]
        out["total_" + d] = {"trades": int(n), "net": round(net, 2), "wr": round(100 * w / n, 2) if n else 0.0}
    out["complete"] = len(rs) == 8
    return out


def tester_block(key):
    t = TV[key]; s = t["score"]
    return {"n": s["n"], "wr": s["wr"], "net": s["net"], "pf": s["pf"], "worst_loss": s["worst_loss"], "dd": s["dd"],
            "per_year": {y: {"n": v[0], "wr": v[1], "net": v[2]} for y, v in t["per_year"].items() if y in ("2023", "2024", "2025", "2026")}, "hypothesis": True}


cand = json.load(open(os.path.join(SAVED, CAND + ".json"), encoding="utf-8"))
candB = json.load(open(os.path.join(SAVED, CANDB + ".json"), encoding="utf-8"))
base = json.load(open(os.path.join(SAVED, BASE + ".json"), encoding="utf-8"))
m_c, m_b, m_base = mt5_block("save:" + CAND), mt5_block("save:" + CANDB), mt5_block("save:" + BASE)

K = "W6 TP off; paper split 40% at $2 + BE, 30% at $5; 30% trails 2.5 ATR after the partial"
KB = "W5 TP off; 60% at $2 + BE; 40% to the $26 lab target (1R)"
KBASE = "W0 base"


def fmt(b, d):
    t = b["total_" + d]
    return f"{t['trades']} trades, {t['wr']:.1f}% WR, net ${t['net']:,.0f}"


dc, db, dbase = m_c["total_random"], m_b["total_random"], m_base["total_random"]
better = dc["net"] > dbase["net"]
betterB = db["net"] > dbase["net"]
verdict = (
    f"MT5 Strategy Tester, M15 chart, Blueberry real ticks, $100k, 2 lots, 2023-2026, RANDOM delay (the verdict): "
    f"base {fmt(m_base, 'random')}; candidate (the paper's 40/30/30 sub-trade split: 40% off at the base's $2 win + breakeven, 30% at $5, 30% on a 2.5 x ATR trail) "
    f"{fmt(m_c, 'random')}; candidate B (fixed-anchor half only: 60% at $2 + breakeven, 40% to the $26 1R target) {fmt(m_b, 'random')}. "
    f"No delay: base {fmt(m_base, 'none')}, candidate {fmt(m_c, 'none')}, candidate B {fmt(m_b, 'none')}. "
    + ("The paper's sub-trade architecture " + ("IMPROVES" if better else "does NOT improve") + f" the base under random delay (net {dc['net'] - dbase['net']:+,.0f} $, WR {dc['wr'] - dbase['wr']:+.1f} points); "
       "the fixed-anchor variant " + ("improves" if betterB else "does not improve") + f" it either (net {db['net'] - dbase['net']:+,.0f} $, WR {db['wr'] - dbase['wr']:+.1f} points). ")
    + "Note: MT5's report counts the candidates' partial closes and the runners' breakeven exits as separate trades (a breakeven exit is a 'loss' of a few dollars), so their MT5 win rates "
      "(77% / 69%) are not per position like the base's 96% - the tester's per-position hypothesis was 96.1% / 96.3%; compare the net and the drawdown. The telling row is 2025: the candidate made $75,813 with no delay and $31,780 under random delay (PF 1.70 -> 1.21, DD 9.1% -> 17.6%) - "
      "the delay lands on the partial fills and the breakeven stop moves that the architecture depends on, exactly where the lock-and-ride research of 2026-11-01 already saw the half-lock die. "
    + "Both candidates keep the entry, the filters and the $26 stop and change ONLY the exit geometry (the paper is about exits): the 20-pip broker TP is replaced by lab partials "
      "at the same $2 level, so part of the position rides. The Turtle TV tester numbers (base $402,831 / 97.2%; candidate $356,496 / 96.1%; candidate B $373,738 / 96.3%) are hypotheses, "
      "and they already said the same: on this entry, every lot that does not take the $2 win pays for it - gold's M15 noise closes the ATR-trailed and breakeven runners for less than "
      "the fixed win they gave up, and the runner holding the single allowed position blocks the next setup (the paper's own 'state gating', fewer trades). The paper's Direct-vs-Subtrade "
      "result was one in-sample H1 backtest with a different (transformer) signal and no delay model; its mechanism does not transfer to this 97%-WR, $2-win / $26-stop machine. "
      "The ATR-adaptive stop (the paper's 'Adaptive' category on the stop itself) lost 2-6 WR points in every tester form tried, including the min(6 ATR, $26) version that only tightens stops, "
      "and was not sent to MT5. Recommendation: keep the base; nothing from this paper is promoted."
)

result = {
    "id": ID, "title": TITLE, "authors": "Abiodun Aremu (FxChartAI Inc.)", "year": 2026,
    "summary": ("The author argues that predictive accuracy is not profitability: the same transformer 'sentiment' signals on XAUUSD H1 (Jul-Nov 2025) lost 99.99% when traded as "
                "one position with a static SL/TP ('Direct'), and made +$1.31M (PF 4.95, 80 trades, DD 33.9%) when every signal was split into five sub-trades: two 'Fixed' "
                "(fixed-pip trails, fast 30% and slow 10%, the slow one also gating new signals) and three 'Adaptive' (ATR-multiple trails 1x / 2.5x / 5x, 30/20/10%). "
                "Evidence is two in-sample MT5 tester reports and a 325-row sentiment dataset; pip values and ATR multipliers are not disclosed, no delay or slippage model."),
    "ideas": [
        {"idea": "Split one signal into sub-trades with different exits (dynamic sub-trade lot allocation 10/30/30/20/10)", "where": "exit", "implementable": True,
         "mapping": "InpFixTpPips 0 (broker TP off) + InpXP1R 0.077 / InpXP1Frac 0.4 / InpXP1Be true (fixed anchor at the base's $2 win, 0.077 of the $26 stop), InpXP2R 0.192 / InpXP2Frac 0.3 (second anchor at $5), InpXTr 2 / InpXTrK 2.5 / InpXTrAct 0.077 (the rest on a 2.5 x ATR trail), InpXTgt 1 - the candidate"},
        {"idea": "Fixed sub-trades (Matt fast / Matthew slow fixed-pip trails) bank the first impulse", "where": "exit", "implementable": True,
         "mapping": "the partial at the $2 level with InpXP1Be (candidate B keeps 60% there and sends 40% to the $26 1R target InpXTgt 4 / InpXTgtK 26 that the base already carries)"},
        {"idea": "Adaptive sub-trades: stops that breathe with ATR (Mark 1x, Luke 2.5x, John 5x)", "where": "exit", "implementable": True,
         "mapping": "InpXTr 2 (ATR from the best) with InpXTrK 1 / 2.5 / 5 on the remainder; tested as W7 / W2-W4 / W3 - all below the base in the tester (hypothesis)"},
        {"idea": "ATR-based initial stop instead of a static one (avoid 'stop hunts')", "where": "exit", "implementable": True,
         "mapping": "InpSlMode 1 / InpSlAtrMult k (+ InpXLossCap 26 so the stop is never wider than the base's $26); tester: k=4 91.6% WR, min(6 ATR,$26) 94.8% vs base 97.2% - rejected, not sent to MT5; the base's $26 stop is already wider than 6 ATR in 2023-24"},
        {"idea": "State gating: no new signal cycle until the slow anchor closes (fewer trades, no over-trading in chop)", "where": "filter", "implementable": True,
         "mapping": "already the base's: InpMaxPos 1, InpReplace false; the riding tranche extends it mechanically (tester n 1615 -> 1503 / 1391)"},
        {"idea": "Adaptive thresholding - 'cash is a position', trade only when signal strength clears a threshold", "where": "filter", "implementable": True,
         "mapping": "the EA's signal-strength gates InpChopEr (base 0.05), InpAdxMin, InpMinRangeAtr, the band masks; not changed here - the paper gives no threshold and the entry is frozen by doctrine"},
        {"idea": "Transformer time-series model producing the 0/1 sentiment signal", "where": "entry", "implementable": False,
         "mapping": "no model, no data, no code published; the project's own learned gate is InpMlFilter (v1.39, off, model pending) - not applicable to a rule-based M15 gold EA"},
        {"idea": "Risk split across sub-trades sized by percentage of the intended lots", "where": "sizing", "implementable": True,
         "mapping": "InpXP1Frac / InpXP2Frac shares of InpLots (2 lots -> 0.8 / 0.6 / 0.6); a 5-way split needs the lot step 0.01 and would need new code for more than two partials"},
    ],
    "base_setting": {"name": BASE, "result": base["result"]},
    "setting": {"name": cand["name"], "inputs": cand["inputs"], "changed": cand["changed"], "note": cand["note"], "ds": "m15", "mode": "ea", "result": cand["result"], "lab": {}, "lab_describe": ""},
    "setting_b": {"name": candB["name"], "inputs": candB["inputs"], "changed": candB["changed"], "note": candB["note"], "ds": "m15", "mode": "ea", "result": candB["result"], "lab": {}, "lab_describe": ""},
    "needs_code": {"required": False, "version": None, "files": [], "inputs": [],
                   "summary": "No new EA code: the sub-trade split is expressed with the existing exit-lab inputs (InpXP1*/InpXP2*/InpXTr*/InpXTgt) and InpFixTpPips 0. A faithful five-way split (more than two partials, two fixed-pip trails of different speeds) would need new code; not built because the two-partial version already loses to the base."},
    "tester": tester_block(K),
    "tester_b": tester_block(KB),
    "tester_base": tester_block(KBASE),
    "mt5": m_c, "mt5_b": m_b, "base_mt5": m_base,
    "verdict": verdict,
    "status": "done" if (m_c["complete"] and m_base["complete"]) else "failed",
    "error": None if (m_c["complete"] and m_base["complete"]) else f"MT5 rows incomplete: candidate {len(m_c['rows'])}/8, base {len(m_base['rows'])}/8",
    "built": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}
json.dump(result, open(os.path.join(STORE, "result.json"), "w", encoding="utf-8"), indent=1)
setting = dict(cand, source_note="candidate of the Research page job; see result.json")
json.dump(setting, open(os.path.join(STORE, "setting.json"), "w", encoding="utf-8"), indent=1)
print("status", result["status"], result["error"])
print("BASE  none", m_base["total_none"], "random", m_base["total_random"])
print("CAND  none", m_c["total_none"], "random", m_c["total_random"])
print("CANDB none", m_b["total_none"], "random", m_b["total_random"])
for b, nm in ((m_base, "base"), (m_c, "cand"), (m_b, "candB")):
    for r in b["rows"]:
        print(f"  {nm:5s} {r['year']} {r['delay']:6s} n {r['trades']:4d} net {r['net']:10,.0f} wr {r['wr']:6.2f} worst {r['worst']:9,.0f} pf {r['pf']}")
