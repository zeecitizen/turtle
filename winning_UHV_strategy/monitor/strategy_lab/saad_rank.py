"""Rank runs in a jsonl: python saad_rank.py FILE [--sort net|pf|dd] [--since N] [--grep TEXT]"""
import json, sys, argparse
ap = argparse.ArgumentParser(); ap.add_argument("file"); ap.add_argument("--sort", default="net")
ap.add_argument("--since", type=int, default=0); ap.add_argument("--grep", default=""); ap.add_argument("--top", type=int, default=200)
a = ap.parse_args()
rows = [json.loads(l) for l in open(a.file)][a.since:]
out = []
for r in rows:
    if "net" not in r or not r.get("day_stats", {}).get("days"):
        out.append((-1e18, f"{r.get('arm','?')[:70]:70s} ERROR {r.get('error','')}")); continue
    if a.grep and a.grep not in r["arm"]: continue
    ds = r["day_stats"]; m = r.get("months", {})
    dd = float(r["dd"].split("(")[1].rstrip("%)")) if "(" in r["dd"] else 0
    pf = float(r["pf"] or 0)
    key = {"net": r["net"], "pf": pf, "dd": -dd, "ratio": r["net"] / max(dd, 0.1)}[a.sort]
    out.append((key, f"{r['arm'][:70]:70s} net {r['net']:>10.0f} tr {r['trades']:>5} WR {r['wr']:>7} PF {pf:4.2f} DD {dd:5.1f}% "
                     f"$/tr {r.get('trade_stats',{}).get('per_trade',0):>6.0f} $/day {r['net']/max(ds['days'],1):>6.0f} bigL {r.get('trade_stats',{}).get('largest_loss',0):>6.0f} strk {r.get('trade_stats',{}).get('max_loss_streak',0):>2} "
                     f"green {ds['green']}/{ds['days']} worst {ds['worst']:>8.0f} lm {sum(v < 0 for v in m.values())} "
                     f"ex{r.get('exec','?')} {r.get('build','?')} disc {r.get('discard','?')}"))
for k, t in sorted(out, key=lambda x: -x[0])[:a.top]: print(t)
