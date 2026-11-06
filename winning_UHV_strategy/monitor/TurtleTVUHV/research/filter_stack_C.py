"""filter_stack_C.py - Zee 2026-11-02: "the filters dont act alone, they act in combinations ... after i apply 1 filter, the effect of other filter
becomes visible". Forward search over the loser-cutting catalog (B's 8 groups + the scan's top 20) on setting C: at every step each box not yet
applied is measured on the CURRENT state (so interactions count); the box whose application adds the most net is applied; stop when no box adds
money (or when a weaker rule is asked: stop when no box cuts a net-losing group). Also reports, for each applied step, the single-filter effect
measured on the original C so the interaction (combined - sum of singles) is visible. Tester hypothesis, in-sample. -> research/filter_stack_C.json"""
import json, sys, time
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import server, sim
HERE = r"C:\Users\zeesh\turtle\monitor\saad_view"
C = json.load(open(HERE + r"\settings\saved\2026-11-01 08-38-10.json", encoding="utf-8"))["inputs"]
cat = server.lcf_catalog()["groups"]
OBJ = sys.argv[1] if len(sys.argv) > 1 else "net"             # "net": apply the box that raises total net most; "cutloss": the box whose cut trades lose the most


def trades(inp):
    tr, _, _ = sim.simulate(server.full_inputs(inp), ds="m15"); tr = tr[tr[:, 10] == 0]
    return {(int(r[11]), 1 if r[0] > 0 else -1): float(r[6]) for r in tr}


def measure(state, g):
    inp = dict(state); inp.update(g["set"]); t = trades(inp)
    base = trades_cache[json.dumps(state, sort_keys=True)]
    cut = {k: base[k] for k in set(base) - set(t)}; cl = sum(p <= 0 for p in cut.values()); cw = len(cut) - cl
    return {"key": g["key"], "name": g["name"], "with_n": len(t), "with_wr": round(100 * sum(p > 0 for p in t.values()) / max(1, len(t)), 2), "with_net": round(sum(t.values())),
            "d_net": round(sum(t.values()) - sum(base.values())), "cut_n": len(cut), "cut_losers": cl, "cut_winners": cw, "cut_net": round(sum(cut.values()))}, t


trades_cache = {}
t0 = time.time()
state = dict(C); trades_cache[json.dumps(state, sort_keys=True)] = trades(state)
base0 = trades_cache[json.dumps(state, sort_keys=True)]
print(json.dumps({"C": {"n": len(base0), "net": round(sum(base0.values())), "losers": sum(p <= 0 for p in base0.values())}, "boxes": len(cat), "objective": OBJ}), flush=True)
singles = {}
applied, path = [], []
for step in range(12):
    cands = []
    for g in cat:
        if g["key"] in applied or all(str(state.get(k)) == v for k, v in g["set"].items()):
            continue
        m, t = measure(state, g)
        if step == 0:
            singles[g["key"]] = m
        cands.append((m, t))
    if not cands:
        break
    cands.sort(key=lambda x: (-x[0]["d_net"]) if OBJ == "net" else (x[0]["cut_net"]))
    best, tb = cands[0]
    ok = best["d_net"] > 0 if OBJ == "net" else best["cut_net"] < 0
    print(json.dumps({"step": step + 1, "best": best, "ok": ok, "runner_up": cands[1][0]["name"] if len(cands) > 1 else None, "secs": round(time.time() - t0)}), flush=True)
    if not ok:
        break
    g = next(x for x in cat if x["key"] == best["key"]); state.update(g["set"]); applied.append(g["key"])
    trades_cache[json.dumps(state, sort_keys=True)] = tb
    sum_singles = sum(singles[k]["d_net"] for k in applied)
    path.append({**best, "cumulative_d_net": round(sum(tb.values()) - sum(base0.values())), "sum_of_single_effects": sum_singles, "interaction": round(sum(tb.values()) - sum(base0.values()) - sum_singles)})
json.dump({"objective": OBJ, "C": {"n": len(base0), "net": round(sum(base0.values()))}, "path": path, "singles_on_C": singles, "final_inputs_changed": {k: state[k] for k in state if str(state[k]) != str(C.get(k))},
           "secs": round(time.time() - t0)}, open(HERE + rf"\research\filter_stack_C_{OBJ}.json", "w", encoding="utf-8"), indent=1)
print("done", len(path), "steps", round(time.time() - t0), "s")
