"""filter_scan_C.py - Zee 2026-11-02: "go through all the saved settings. cherry pick the setting's filters which specifically cut down the trades ...
make a list of all the priority filters that matter -> e.g. the top 20 that have most effect on cutting lossy trades -> then add them to the range box
table". Every distinct (entry-filter input, value) used by any saved setting is applied alone to setting C (2026-11-01 08-38-10, 1,615 trades);
the trades that disappear are attributed to winners / losers. Ranking: net of the cut trades (most negative = cuts the most losing money), then
selectivity (loser-cut rate / winner-cut rate; >= 2.8 adds money at C's $400 / $4,900 geometry). Tester hypothesis, in-sample. -> research/filter_scan_C.json"""
import json, glob, sys, time, collections
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view"); sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\strategy_lab")
import server, sim, axi_rig
HERE = r"C:\Users\zeesh\turtle\monitor\saad_view"
OUT = HERE + r"\research\filter_scan_C.json"
dfl = axi_rig.ea_defaults("Saad_strategy_15min_view")
C = json.load(open(HERE + r"\settings\saved\2026-11-01 08-38-10.json", encoding="utf-8"))["inputs"]
FILTERS = ["InpEmaGapPips", "InpChopEr", "InpSessFrom", "InpSessTo", "InpSkipDow", "InpAtrMinUsd", "InpAtrMaxUsd", "InpMinRangeAtr", "InpMaxSpreadPts", "InpAdxMin",
           "InpBandsB", "InpBandsS", "InpBandOff", "InpHours", "InpDayTargetUsd", "InpDayLossPct", "InpDayLossUsd", "InpHamRatio", "InpHamNose", "InpNoseMax", "InpStar",
           "InpHammer", "InpTouchPips", "InpWickMin", "InpBodyMax", "InpMaruBody", "InpSkipBothEma", "InpLongRule", "InpShortLine", "InpBreakBars", "InpBreakPips",
           "InpMaxPos", "InpExtraDir", "InpRangeLook", "InpRangeLookS"] + [k for k in dfl if k.startswith("TvBox_")]
cands = collections.Counter()
for f in glob.glob(HERE + r"\settings\saved\*.json"):
    try:
        inp = json.load(open(f, encoding="utf-8")).get("inputs", {})
    except Exception:                                          # noqa: BLE001
        continue
    for k in FILTERS:
        if k in inp and k in dfl and str(inp[k]) != str(dfl[k]) and str(inp[k]) != str(C.get(k)):     # a value C does not already have
            cands[(k, str(inp[k]))] += 1


def trades(inp):
    tr, _, _ = sim.simulate(server.full_inputs(inp), ds="m15"); tr = tr[tr[:, 10] == 0]
    return {(int(r[11]), 1 if r[0] > 0 else -1): float(r[6]) for r in tr}


t0 = time.time()
base = trades(C); losers = {k for k, p in base.items() if p <= 0}; winners = set(base) - losers
rows = []
done = {}
if __import__("os").path.exists(OUT):                          # resume
    try:
        rows = json.load(open(OUT, encoding="utf-8"))["rows"]; done = {(r["input"], r["value"]) for r in rows}
    except Exception:                                          # noqa: BLE001
        rows, done = [], set()
print(json.dumps({"C": {"n": len(base), "losers": len(losers), "net": round(sum(base.values()))}, "candidates": len(cands), "resumed": len(done)}), flush=True)
for i, ((k, v), used) in enumerate(sorted(cands.items(), key=lambda x: -x[1])):
    if (k, v) in done:
        continue
    inp = dict(C); inp[k] = v
    try:
        t = trades(inp)
    except Exception as e:                                     # noqa: BLE001
        rows.append({"input": k, "value": v, "used_by": used, "error": str(e)[:200]}); continue
    cut = {kk: base[kk] for kk in set(base) - set(t)}; added = {kk: t[kk] for kk in set(t) - set(base)}
    cl = {kk for kk, p in cut.items() if p <= 0}; cw = set(cut) - cl
    sel = (len(cl) / max(1, len(losers))) / (len(cw) / max(1, len(winners))) if cw else (999 if cl else None)
    row = {"input": k, "value": v, "default": str(dfl[k]), "c_value": str(C.get(k)), "used_by": used, "cut_n": len(cut), "cut_losers": len(cl), "cut_winners": len(cw),
           "cut_net": round(sum(cut.values())), "cut_wr": round(100 * len(cw) / len(cut), 1) if cut else None, "added_n": len(added), "added_net": round(sum(added.values())),
           "with_n": len(t), "with_wr": round(100 * sum(p > 0 for p in t.values()) / max(1, len(t)), 2), "with_net": round(sum(t.values())), "d_net": round(sum(t.values()) - sum(base.values())),
           "selectivity": None if sel is None else round(sel, 2), "secs": round(time.time() - t0)}
    rows.append(row)
    print(json.dumps({kk: row[kk] for kk in ("input", "value", "cut_n", "cut_losers", "cut_winners", "cut_net", "added_n", "d_net", "selectivity")}), flush=True)
    if i % 5 == 0:
        json.dump({"C": {"n": len(base), "losers": len(losers), "net": round(sum(base.values()))}, "rows": rows}, open(OUT, "w", encoding="utf-8"), indent=1)
ranked = sorted([r for r in rows if "error" not in r and r["cut_losers"] >= 2], key=lambda r: (r["cut_net"], -(r["selectivity"] or 0)))
json.dump({"C": {"n": len(base), "losers": len(losers), "net": round(sum(base.values()))}, "secs": round(time.time() - t0), "rows": rows,
           "top20_by_cut_net": [{k: r[k] for k in ("input", "value", "cut_n", "cut_losers", "cut_winners", "cut_net", "d_net", "selectivity", "used_by")} for r in ranked[:20]],
           "top20_by_selectivity": [{k: r[k] for k in ("input", "value", "cut_n", "cut_losers", "cut_winners", "cut_net", "d_net", "selectivity", "used_by")} for r in sorted(ranked, key=lambda r: -(r["selectivity"] or 0))[:20]]},
          open(OUT, "w", encoding="utf-8"), indent=1)
print("done", len(rows), "candidates", round(time.time() - t0), "s")
