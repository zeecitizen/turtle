"""v127_single_changes.py - after the night search: every change the top-40 passes kept repeating, applied ALONE to v1.26, full year, random
delay - an improvement counts only if it helps in BOTH halves (Jan-Jun and Jul-Oct). Writes v127_single.json."""
import json
import sys
from pathlib import Path

sys.argv = sys.argv[:1]
import v127_night_run as v  # noqa: E402

CH = [("v1.26", {}), ("ADX 30 -> 20", {"InpAdxMin": "20"}), ("fast EMA 16 -> 12", {"InpEmaFast": "12"}), ("slow EMA 32 -> 24", {"InpEmaSlow": "24"}),
      ("SELL range look 7 -> 9", {"InpRangeLookS": "9"}), ("BUY range look 7 -> 8", {"InpRangeLook": "8"}), ("stand aside -> skip", {"InpBandOff": "0"}),
      ("ATR min $3", {"InpAtrMinUsd": "3"}), ("ATR max $25", {"InpAtrMaxUsd": "25"}), ("breakeven at +$8", {"InpX1BeUsd": "8"}),
      ("at +$12 lock +$2", {"InpX1LockAt": "12", "InpX1LockUsd": "2"}), ("at +$12 lock +$4", {"InpX1LockAt": "12", "InpX1LockUsd": "4"}),
      ("trade until server 22 (midnight PKT)", {"InpSessTo": "22"}), ("chop 0.1", {"InpChopEr": "0.1"}), ("max risk $20 -> $15", {"InpMaxRiskUsd": "15"}),
      ("SELL setups on either EMA", {"InpShortLine": "2"}), ("break 3 -> 6 pips", {"InpBreakPips": "6"}), ("body max 0.6 -> 0.7", {"InpBodyMax": "0.7"}),
      ("LONG rule: fast EMA only", {"InpLongRule": "0"})]
res = v.run_many(CH, "2026.01.01", "2026.10.17")
for name, r in res.items():
    m = r.get("months") or {}
    r["h1"] = round(sum(x for k, x in m.items() if k <= "2026.06"))
    r["h2"] = round(sum(x for k, x in m.items() if k >= "2026.07"))
json.dump(res, open(Path(__file__).with_name("v127_single.json"), "w"), indent=1)
b = res["v1.26"]
print(f"\nv1.26: year {b['net']:+,.0f} PF {b['pf']:.2f} DD {b['dd']:,.0f} | Jan-Jun {b['h1']:+,} Jul-Oct {b['h2']:+,}")
for name, r in sorted(res.items(), key=lambda x: -x[1]["net"]):
    both = r["h1"] > b["h1"] and r["h2"] > b["h2"]
    print(f"{'BOTH HALVES BETTER | ' if both else ''}{name}: year {r['net']:+,.0f} PF {r['pf']:.2f} WR {r['wr']:.0f}% DD {r['dd']:,.0f} | "
          f"Jan-Jun {r['h1'] - b['h1']:+,} Jul-Oct {r['h2'] - b['h2']:+,} vs v1.26")
