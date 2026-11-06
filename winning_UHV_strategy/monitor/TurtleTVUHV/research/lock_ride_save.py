"""lock_ride_save.py - write rows of research/lock_ride.json (exit variants on setting B) into Turtle TV's saved settings, in the page's format
(inputs, changed vs the EA defaults, ds m15, result, note), so mt5_years.py can run them in MT5 as "save:<name>".

    py lock_ride_save.py "lock +$2 at +$4, target $26" ["<row name>" ...]
    py lock_ride_save.py --sets '{"InpXBeR": 0.153846, ...}' --name "<row name>"        (runs the variant first if it is not in the json)
Prints the saved names (one per line, prefixed "saved ").
"""
import json, re, sys, time
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view"); sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\strategy_lab")
import server, axi_rig
import lock_ride as L

dfl = axi_rig.ea_defaults(server.EA)
args = sys.argv[1:]
rows = L.load()
if "--sets" in args:
    sets = json.loads(args[args.index("--sets") + 1]); name = args[args.index("--name") + 1]
    if name not in rows:
        rows = L.save({name: L.one(name, "adhoc", sets)})
    names = [name]
else:
    names = args
stamp = time.strftime("%Y-%m-%d %H-%M")
for i, n in enumerate(names):
    x = rows[n]; m = x["m"]
    inp = server.full_inputs({**L.B, **x["sets"]})
    short = re.sub(r" +", " ", re.sub(r"[^A-Za-z0-9 +.-]", "", n.replace("$", ""))).strip()[:48]     # no ',' (mt5_years.py splits its gate list on commas) and no '%' / ':'
    name = f"{stamp}-{i:02d} ride WR{m['wr']:.1f} {m['net'] / 1000:+.0f}k {short}"
    note = (f"Built {time.strftime('%Y-%m-%d')} by research/lock_ride.py: setting '{L.NAME_B}' (399 trades, 99.7%, TP $2 / stop $26) with its exits changed to "
            f"'{n}' - Zee's 'lock the +$400 and ride' idea as real EA inputs ({', '.join(f'{k}={v}' for k, v in x['sets'].items())}). "
            f"Tester m15 2023-2026: {m['n']} trades, WR {m['wr']}% (2023-24 {m['wr1']}%, 2025-26 {m['wr2']}%), net {m['net']:+,} "
            f"(halves {m['net1']:+,} / {m['net2']:+,}), PF {m['pf']}, DD {m['dd']:,}, worst {m['worst']:,}, {m['full_stops']} full stops, "
            f"avg win {m['avg_win']:,} / avg loss {m['avg_loss']:,}, median hold {m['hold_med']} min, {m['fri']} Friday closes, exits {m['why']}. "
            f"Tester = hypothesis (lab rows read 4-8% high vs MT5); needs EA v1.38+ on an M15 chart.")
    row = {"name": name, "inputs": inp, "changed": {a: b for a, b in inp.items() if str(dfl.get(a)) != str(b)}, "ds": "m15", "mode": "ea",
           "result": {"n": m["n"], "net": float(m["net"]), "pf": m["pf"], "wr": round(float(m["wr"]), 1), "avg_loss": float(m["avg_loss"]),
                      "worst_loss": float(m["worst"]), "dd": float(m["dd"]), "ret_dd": m["net"] / max(1, m["dd"])},
           "lab": {}, "lab_describe": "", "note": note, "lock_ride_row": n}
    json.dump(row, open(L.SV + "\\" + name + ".json", "w"), indent=1)
    print("saved", name)
