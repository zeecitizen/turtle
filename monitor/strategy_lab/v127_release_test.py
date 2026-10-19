"""v127_release_test.py - Saad_strategy_15min v1.27 with PURE defaults (only InpLogCsv off), full year, two random-delay runs (page paused)."""
import json
import sys
from pathlib import Path

sys.argv = sys.argv[:1]
import v127_night_run as v  # noqa: E402  (run_many, page)

v.EA = "Saad_strategy_15min"
was = v.page().get("auto", True)
v.page(False)
res = v.run_many([("v1.27 #1", {}), ("v1.27 #2", {})], "2026.01.01", "2026.10.17")
v.page(bool(was))
for n, r in res.items():
    m = r.get("months") or {}
    r["h1"] = round(sum(x for k, x in m.items() if k <= "2026.06")); r["h2"] = round(sum(x for k, x in m.items() if k >= "2026.07"))
    print(f"{n}: net {r['net']:+,.0f} PF {r['pf']:.2f} WR {r['wr']:.1f}% trades {r['n']} DD {r['dd']:,.0f} | Jan-Jun {r['h1']:+,} Jul-Oct {r['h2']:+,} | "
          + " ".join(f"{k[5:]}:{x / 1000:+.1f}k" for k, x in m.items()))
json.dump(res, open(Path(__file__).with_name("v127_release_test.json"), "w"), indent=1)
