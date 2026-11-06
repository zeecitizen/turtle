"""runner_grid_C.py - Zee 2026-11-02: "some trade go until lab target which can give a profit of 2000+ ... can we try to bring this kind of behavior
of large wins on 2026-11-01 08-38-10 where each win is capped at nearly 400". Candidate B of the paper job (60% off at $2 + BE, 40% rides to $26)
lost $37k to C under MT5 random delay. This grid asks whether a smaller runner, a nearer runner target, or more same-side positions flips the sign.
Turtle TV Tester = hypothesis; the top rows go to MT5 (research/mt5_years.py "file:" gate). Output: research/runner_grid_C.json"""
import json, sys, time, itertools, numpy as np
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import server, sim
HERE = r"C:\Users\zeesh\turtle\monitor\saad_view"
C = json.load(open(HERE + r"\settings\saved\2026-11-01 08-38-10.json", encoding="utf-8"))["inputs"]
R0 = 26.0                                                      # C's stop = $26 of price -> InpX*R are fractions of it


def run(name, changes):
    inp = dict(C); inp.update({k: str(v) for k, v in changes.items()})
    t0 = time.time()
    tr, _, _ = sim.simulate(server.full_inputs(inp), ds="m15"); tr = tr[tr[:, 10] == 0]
    pnl = tr[:, 6]; reason = tr[:, 13].astype(int)
    row = {"name": name, "changes": changes, "n": int(len(tr)), "wr": round(100 * float((pnl > 0).mean()), 2), "net": round(float(pnl.sum())),
           "worst": round(float(pnl.min())), "full_stops": int((pnl <= -4000).sum()), "wins_2000plus": int((pnl >= 2000).sum()),
           "net_2000plus": round(float(pnl[pnl >= 2000].sum())), "be_exits": int((reason == 7).sum()), "target_exits": int((reason == 9).sum()),
           "secs": round(time.time() - t0, 1)}
    print(json.dumps(row), flush=True)
    return row


rows = [run("C (base, TP $400)", {})]
# runner share = 1 - InpXP1Frac; the partial sits at C's $2 win (0.077 R); the runner goes to breakeven and rides to InpXTgtK dollars
for frac, tgt in itertools.product((0.6, 0.75, 0.9), (8, 13, 18, 26)):
    rows.append(run(f"runner {round(100 * (1 - frac))}% to ${tgt}", {"InpFixTpPips": 0, "InpXP1R": f"{2 / R0:.6f}", "InpXP1Frac": frac, "InpXP1Be": "true", "InpXTgt": 4, "InpXTgtK": tgt}))
# the same with 3 same-side positions so a riding runner does not block the next entry
for frac, tgt in ((0.75, 13), (0.75, 26), (0.9, 26), (0.6, 26)):
    rows.append(run(f"runner {round(100 * (1 - frac))}% to ${tgt} + MaxPos 3 same side", {"InpFixTpPips": 0, "InpXP1R": f"{2 / R0:.6f}", "InpXP1Frac": frac, "InpXP1Be": "true", "InpXTgt": 4, "InpXTgtK": tgt, "InpMaxPos": 3, "InpExtraDir": 1}))
rows.append(run("C + MaxPos 3 same side (TP untouched)", {"InpMaxPos": 3, "InpExtraDir": 1}))
json.dump(rows, open(HERE + r"\research\runner_grid_C.json", "w", encoding="utf-8"), indent=1)
print("done", len(rows))
