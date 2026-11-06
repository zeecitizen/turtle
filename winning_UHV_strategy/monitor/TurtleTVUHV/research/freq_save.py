"""freq_save.py - write chosen points of research/freq_grow_<start>.json into Turtle TV's saved settings (settings/saved/<name>.json),
in the page's format (inputs, changed vs the EA defaults, ds m15, result) with a note saying how it was built.
A point = the setting after the first N steps of the search (the steps are replayed from the start setting).

    py research/freq_save.py "2026-10-30 23-08-23" 1,3,8
"""
import json, sys, time
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view"); sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\strategy_lab")
import server, axi_rig
from freq_grow import run, met, S0

SV = r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved"
START = sys.argv[1]
NS = [int(x) for x in sys.argv[2].split(",")]
G = json.load(open(rf"C:\Users\zeesh\turtle\monitor\saad_view\research\freq_grow_{START.replace(' ', '_')}.json"))
dfl = axi_rig.ea_defaults(server.EA)


def replay(n):
    cur = dict(S0)
    for s in G["steps"][:n]:
        w = s["move"].split()
        if len(w) == 4 and w[1] == "box":                       # "InpBandsS box 19 on"
            k, b = w[0], int(w[2]); v = list(cur.get(k) or "1" * 64)
            v[b] = "1" if w[3] == "on" else "0"; cur[k] = "".join(v)
        else:                                                    # "InpAtrMinUsd 1.5->1.25"
            cur[w[0]] = w[1].split("->")[1]
    return cur


stamp = time.strftime("%Y-%m-%d %H-%M")
for i, n in enumerate(NS):
    cur = replay(n)
    m = met(run(cur))
    assert m["n"] == G["steps"][n - 1]["n"] and m["L"] == G["steps"][n - 1]["L"], (m, G["steps"][n - 1])
    inp = server.full_inputs(cur)
    name = f"{stamp}-{i:02d} freq {m['days']} days WR {m['wr']:.1f}"
    moves = [s["move"] for s in G["steps"][:n]]
    note = (f"Built {time.strftime('%Y-%m-%d')} by research/freq_grow.py from '{START}' ({G['m0']['n']} trades on {G['m0']['days']} trading days, "
            f"{G['m0']['wr']}%): entry filters LOOSENED only, target / stop / exits as saved. Each step had to add trading days in BOTH halves "
            f"(2023-24, 2025-26) on its own, paying at most one loser per {G['steps'][n - 1]['lambda']:g} days. Steps: " + "; ".join(moves) +
            f". Tester m15: {m['n']} trades on {m['days']} of 983 weekdays, {m['L']} losers ({m['full_stops']} full stops), WR {m['wr']}% "
            f"(2023-24 {m['wr1']}%, 2025-26 {m['wr2']}%), weekdays between trades median {m['gap_med']:.0f} / 90% {m['gap_p90']:.0f} / max "
            f"{m['gap_max']}. Tester = hypothesis; needs EA v1.38 on an M15 chart.")
    row = {"name": name, "inputs": inp, "changed": {a: b for a, b in inp.items() if str(dfl.get(a)) != str(b)}, "ds": "m15", "mode": "ea",
           "result": {"n": m["n"], "net": float(m["net"]), "pf": m["pf"], "wr": round(float(m["wr"]), 1), "avg_loss": float(m["avg_loss"]),
                      "worst_loss": float(m["worst"]), "dd": float(m["dd"]), "ret_dd": m["net"] / max(1, m["dd"])},
           "lab": {}, "lab_describe": "", "note": note}
    json.dump(row, open(SV + "\\" + name + ".json", "w"), indent=1)
    print("saved", name, {k: m[k] for k in ("n", "L", "wr", "wr1", "wr2", "days", "net", "dd")})
