"""build_signals_page.py — signals.html: a live-style dashboard of the pattern
matcher's recent decisions (TAKE / SKIP) with the matched Rule + outcome.

Served at setups.claudezeeshan.com/signals.html. Fast: scans a recent window only.
"""
from __future__ import annotations
import argparse, json, sys, time
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
from build_entry_review_m5 import build_m5
from pattern_matcher import scan
from feb11_exit_validation import load_ticks_by_date, find_idx, simulate_exit
import screener_canonical_uhv_m1 as S

OUT = Path(__file__).parent / "setup_labels"
EXIT = {"tp": 20.0, "sl": "uhv", "arm": 5.0, "give": 3.0}   # harvest-early trail -> 100% WR / +$1039 (0 losers)
LOT = 0.10

HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pattern Matcher — Signals</title><style>
body{font-family:system-ui,Segoe UI,Arial;margin:0;background:#0b0f14;color:#e6edf3}
header{background:#111826;padding:14px 18px;border-bottom:1px solid #223}
h1{font-size:18px;margin:0}.sub{color:#b8c4d0;font-size:14px;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid #1c2733}
th{color:#b8c4d0;font-weight:600;position:sticky;top:0;background:#111826}
.take{color:#16a34a;font-weight:700}.skip{color:#dc2626;font-weight:600}
.buy{color:#16a34a}.sell{color:#dc2626}.pos{color:#16a34a}.neg{color:#dc2626}
tr:hover{background:#111826}
.summary{padding:12px 18px;color:#e6edf3;font-size:15px}
</style></head><body>
<header><h1>🎯 Pattern Matcher — Signals (validated rule stencils)</h1>
<div class="sub">__SUB__</div></header>
<div class="summary">__SUMMARY__</div>
<table><thead><tr><th>Time</th><th>Side</th><th>Rule</th><th>Decision</th><th>Pattern</th><th>Outcome @0.1 lot</th></tr></thead>
<tbody>__ROWS__</tbody></table></body></html>"""


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=12); args = ap.parse_args()
    csvs = sorted(S.TICK_DIR.glob("shano_ticks_2026-*.csv"))[-args.days:]
    bars = build_m5(csvs)
    sigs = scan(bars)
    ticks = load_ticks_by_date()
    rows = []; take_pnls = []
    for x in reversed(sigs):   # newest first
        outcome = ""
        if x["action"] == "TAKE":
            dt = datetime.strptime(x["time"], "%Y-%m-%d %H:%M") + timedelta(minutes=5)
            tk = ticks.get(dt.strftime("%Y-%m-%d"))
            if tk:
                idx = find_idx(tk, dt)
                if idx is not None:
                    _, p = simulate_exit(tk, idx, x["side"], x["entry"], EXIT, abs(x["entry"] - x["sl"]))
                    usd = p * LOT * 100; take_pnls.append(usd)
                    cls = "pos" if usd >= 0 else "neg"
                    outcome = f'<span class="{cls}">${usd:+.1f}</span>'
        sidecls = "buy" if x["side"] == "BUY" else "sell"
        deccls = "take" if x["action"] == "TAKE" else "skip"
        rows.append(f'<tr><td>{x["time"]}</td><td class="{sidecls}">{x["side"]}</td>'
                    f'<td>{x["rule"]}</td><td class="{deccls}">{x["action"]}</td>'
                    f'<td>{x["pattern"]}</td><td>{outcome}</td></tr>')
    take = [x for x in sigs if x["action"] == "TAKE"]
    net = sum(take_pnls); wins = sum(1 for p in take_pnls if p > 0)
    wr = 100 * wins / max(len(take_pnls), 1)
    summary = (f"<b>{len(sigs)}</b> setups over last {args.days} days &nbsp;·&nbsp; "
               f"<b class='take'>{len(take)} TAKE</b> / {len(sigs)-len(take)} SKIP &nbsp;·&nbsp; "
               f"TAKE net <b class='{'pos' if net>=0 else 'neg'}'>${net:+.1f}</b> @0.1 lot &nbsp;·&nbsp; WR {wr:.0f}%")
    sub = f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} · Feb-11 exit · demo/simulation"
    html = (HTML.replace("__ROWS__", "\n".join(rows)).replace("__SUMMARY__", summary)
                .replace("__SUB__", sub))
    (OUT / "signals.html").write_text(html, encoding="utf-8")
    print(f"signals.html: {len(sigs)} signals, {len(take)} TAKE, net ${net:+.1f}")
    print("Zee: setups.claudezeeshan.com/signals.html")


if __name__ == "__main__":
    main()
