"""task3_report.py - Task 3 md: every setting's effect on the TradingView chart's week (task3_chart_effects.json) next to its effect over
the full year in MT5 (Task 5, TASK5.json, when it exists). Sorted by how much each setting moves the chart's net."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import server  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "saad_strategy_1min_optimized" / "optimizer_results"
C = json.load(open(OUT / "task3_chart_effects.json"))
Y = json.load(open(OUT / "TASK5.json")) if (OUT / "TASK5.json").exists() else {}
EA = dict(server.DIRECT)
EA.update({k: v[0] for k, v in server.CHOICES.items()})
EA.update({"rpPause": "InpBandPauseBars"})
CHOICE_MAP = {k: v[1] for k, v in server.CHOICES.items()}
CHART_ONLY = {"pkBeUsd", "pkLockAt", "pkTrail", "pkAtr", "pkLowN", "adBars", "adMaxUsd", "adEmaX", "fxOn", "enMode", "rpOff", "rpLook", "rpLookS"}
snap = json.load(open(OUT / "task3_chart_snapshot.json"))
base = C["_base"]


def year_for(var, val):
    ea = EA.get(var)
    if not ea or ea not in Y:
        return None
    v = val
    if var in CHOICE_MAP:
        v = CHOICE_MAP[var].get(val, val)
    if isinstance(v, bool):
        v = "true" if v else "false"
    for r in Y[ea]:
        try:
            if abs(float(r["v"]) - float(v)) < 1e-6:
                return r
        except (TypeError, ValueError):
            if str(r["v"]).lower() == str(v).lower():
                return r
    return None


rows = []
for var, tests in C.items():
    if var.startswith("_"):
        continue
    for t in tests:
        rows.append((abs(t["net"] - base["net"]), var, t))
rows.sort(key=lambda r: -r[0])
L = ["# Task 3 — what each setting does on 1 minute (TradingView chart week vs MT5 full year)", "",
     f"Chart: {C['_chart']}, the indicator's own trades over the history the chart holds (about one week, Oct 12–16). "
     f"Unchanged settings on the chart: **{base['n']} trades, win rate {base['wr']:.1f}%, net {base['net']:+,.0f}, max drawdown {base['dd']:,.0f}**.",
     "Each line changes ONE setting and keeps everything else as it was; every setting was put back afterwards.", "",
     "The last columns show the same change over the **full year in MT5** (Task 5: XAUUSD_BB real ticks, Jan 1 – Oct 16, from the same base) where it exists. "
     "A setting that helps on the chart week but not over the year is fitted to that week.", "",
     "| # | Setting | Chart value | Tried | Chart week: trades / WR / net / max DD | vs unchanged (net) | MT5 year: PF / WR / net |", "|---|---|---|---|---|---|---|"]
for i, (_, var, t) in enumerate(rows, 1):
    y = year_for(var, t["v"])
    tag = " (chart-only)" if var in CHART_ONLY else ""
    L.append(f"| {i} | {var}{tag} | {snap.get(var)} | **{t['v']}** | {t['n']} / {t['wr']:.1f}% / {t['net']:+,.0f} / {t['dd']:,.0f} | {t['net'] - base['net']:+,.0f} | " +
             (f"{y['pf']:.2f} / {y['wr']:.1f}% / {y['net']:+,.0f}" if y else "–") + " |")
big = [r for r in rows if r[0] >= 3000][:15]
L += ["", "## The settings that move the chart's results the most", ""]
seen = set()
for _, var, t in big:
    if var in seen:
        continue
    seen.add(var)
    L.append(f"- **{var}**: {t['v']} → net {t['net'] - base['net']:+,.0f}, win rate {t['wr'] - base['wr']:+.1f} pts, drawdown {t['dd'] - base['dd']:+,.0f} on the chart week")
(OUT / "TASK3_setting_effects.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("written", OUT / "TASK3_setting_effects.md", len(rows), "rows")
