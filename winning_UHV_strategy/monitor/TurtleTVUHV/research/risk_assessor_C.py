"""risk_assessor_C.py - Zee 2026-11-02: "2026-10-30 23-08-23 has a NEAR 100 percent winrate -> find out what exactly is making it avoid the bad entries
... use those features to build a risk assessor -> apply to frequent trader settings like 1615 trade of 2026-11-01 08-38-10 to cherry pick and avoid losses".
B (23-08-23) and C (08-38-10) are the same strategy with different hand filters. The EA applies each of B's filter groups to C's own trades:
every trade C takes that disappears under a filter is attributed to winner / loser. A filter that removes losers faster than winners is a risk feature.
Turtle TV Tester hypothesis (and in-sample: both saves were tuned on these 4 years). Output research/risk_assessor_C.json"""
import json, sys, time, numpy as np
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import server, sim
HERE = r"C:\Users\zeesh\turtle\monitor\saad_view"
B = json.load(open(HERE + r"\settings\saved\2026-10-30 23-08-23.json", encoding="utf-8"))["inputs"]
C = json.load(open(HERE + r"\settings\saved\2026-11-01 08-38-10.json", encoding="utf-8"))["inputs"]
# B's filter groups (what B has that C has not) - from the input-by-input diff of the two saves
GROUPS = {
    "EMA gap >= 22.5 pips (C: 2.5)": {"InpEmaGapPips": B["InpEmaGapPips"]},
    "session ends 19:00 + hour 11 off (C: 24h)": {"InpSessTo": B["InpSessTo"], "InpHours": B["InpHours"]},
    "price bands B/S + BandOff": {"InpBandsB": B["InpBandsB"], "InpBandsS": B["InpBandsS"], "InpBandOff": B["InpBandOff"]},
    "stricter shape (HamRatio 2.25, Nose 0.8, NoseMax 0.05, no stars)": {"InpHamRatio": B["InpHamRatio"], "InpHamNose": B["InpHamNose"], "InpNoseMax": B["InpNoseMax"], "InpStar": B["InpStar"]},
    "touch 3.5 pips + MinRangeAtr 0.8": {"InpTouchPips": B["InpTouchPips"], "InpMinRangeAtr": B["InpMinRangeAtr"]},
    "day caps $2000 target / 2% loss (C: 2500 / 1%)": {"InpDayTargetUsd": B["InpDayTargetUsd"], "InpDayLossPct": B["InpDayLossPct"]},
    "TvBox kelt_S / vwap_B masks": {"TvBox_kelt_S": B["TvBox_kelt_S"], "TvBox_vwap_B": B["TvBox_vwap_B"]},
    "B's exits (Friday 22h exit, no candle exit)": {"InpXFriHour": B["InpXFriHour"], "InpXCx": B["InpXCx"], "InpXCxN": B["InpXCxN"]},
    "EMA 19/58 (C: 20/62) - changes the setups": {"InpEmaFast": B["InpEmaFast"], "InpEmaSlow": B["InpEmaSlow"]},
}
ENTRY_FILTERS = [g for g in GROUPS if not g.startswith("B's exits") and not g.startswith("EMA 19")]


def trades(inp):
    tr, _, _ = sim.simulate(server.full_inputs(inp), ds="m15"); tr = tr[tr[:, 10] == 0]
    return {(int(r[11]), int(np.sign(r[0]))): float(r[6]) for r in tr}, tr


t0 = time.time()
base, trB = trades(C)
losers = {k for k, p in base.items() if p <= 0}; winners = {k for k, p in base.items() if p > 0}
full = {k for k, p in base.items() if p <= -4000}
print(json.dumps({"C": {"n": len(base), "winners": len(winners), "losers": len(losers), "full_stops": len(full), "net": round(sum(base.values()))}}), flush=True)
out = {"C": {"n": len(base), "losers": len(losers), "full_stops": len(full), "net": round(sum(base.values()))}, "filters": []}


def attribute(name, changes):
    inp = dict(C); inp.update({k: str(v) for k, v in changes.items()})
    t, tr = trades(inp)
    kept = set(t) & set(base); removed = set(base) - set(t); added = set(t) - set(base)
    row = {"filter": name, "changes": changes, "n": len(t), "net": round(sum(t.values())), "wr": round(100 * float(np.mean([p > 0 for p in t.values()])), 2),
           "removed_losers": len(removed & losers), "removed_full_stops": len(removed & full), "removed_winners": len(removed & winners),
           "kept_losers": len(kept & losers), "added_trades": len(added), "added_net": round(sum(t[k] for k in added)),
           "loser_block_rate": round(100 * len(removed & losers) / max(1, len(losers)), 1), "winner_block_rate": round(100 * len(removed & winners) / max(1, len(winners)), 1),
           "per_year_removed_losers": {}}
    for k in removed & losers:
        y = str(np.datetime64(int(trB[trB[:, 11] == k[0]][0, 1]), "s"))[:4] if (trB[:, 11] == k[0]).any() else "?"
        row["per_year_removed_losers"][y] = row["per_year_removed_losers"].get(y, 0) + 1
    print(json.dumps(row), flush=True)
    out["filters"].append(row)
    return row


for g, ch in GROUPS.items():
    attribute(g, ch)
allf = {}
for g in ENTRY_FILTERS:
    allf.update(GROUPS[g])
attribute("ALL of B's entry filters together", allf)
allB = {k: v for k, v in B.items() if str(C.get(k)) != str(v)}
attribute("B itself (every B input on C's frame)", allB)
# greedy risk assessor: add the filter with the best losers-blocked per winner-blocked ratio, one at a time, until no filter removes a loser
chosen, cur = [], {}
rank = sorted([r for r in out["filters"] if r["filter"] in ENTRY_FILTERS and r["removed_losers"] > 0],
              key=lambda r: -(r["removed_losers"] / max(1, r["removed_winners"])))
out["greedy"] = []
for r in rank:
    cur.update(GROUPS[r["filter"]]); chosen.append(r["filter"])
    out["greedy"].append(attribute("GREEDY: " + " + ".join(s.split(" (")[0] for s in chosen), dict(cur)))
out["secs"] = round(time.time() - t0)
json.dump(out, open(HERE + r"\research\risk_assessor_C.json", "w", encoding="utf-8"), indent=1)
print("done", out["secs"], "s")
