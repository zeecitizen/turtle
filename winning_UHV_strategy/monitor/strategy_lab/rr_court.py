"""rr_court.py — the teacher's economics against the Diamond's flat target, PER DAY.

Zee, 2026-09-08:
  "ok YES let's make Diamond NY only.. to target a 91% winrate"
  "the idea is that if we maintain a low with us. we then have an SL for a trade at the
   last low (the deeper low amongst the lows if there's more than one confirmed low).
   then we target R:R ratio 1:2 as the TP. at R:R ratio 1:1 we breakeven and let it run
   to R:R ratio 1:2 in TP. This is what the original author of the strategy said."
  "Show me per day numbers compared to per day numbers of the current EA"

WHY SINGLE BACKTESTS AND NOT AN OPTIMISATION. An optimisation report is one row per
pass — profit, PF, drawdown — and carries NO trade list, so it cannot answer "per day".
Each arm therefore runs as its own backtest and the DEALS table is parsed out of the
HTML report, which is where the realised profit of every closing deal lives.

THE ARMS ARE CUMULATIVE ON PURPOSE. NY-only alone, then the geometry alone, then both,
so a gain can be attributed instead of just observed. If both changes only pay when
combined, that shows here rather than hiding inside one headline number.

    py monitor/strategy_lab/rr_court.py --from 2026.08.17 --to 2026.09.05
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from mt5_headless import RIG, REPORTS, TEST_EXE, live_is_safe, sync_experts  # noqa: E402
from trend_lab import block_autoupdate, build, kill_stubs, stage  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent.parent

BASE = ["InpOandaVolume=1", "InpOandaStrict=true"]

# InpSlMode=1 uses g_guard, the level the TREND ENGINE defends — and TrendEngine sets
# lastLow=0 in mode 0 (TrendNow has no concept of a defended level). So a "deep low"
# arm run at InpTrendMode=0 silently falls back to the retracement extreme and returns
# a result identical to the arm above it, which is exactly what happened on the first
# court: arms 3 and 4 matched to the cent. His SL idea needs InpTrendMode=1 to exist.
ARMS = [
    ("CURRENT  flat 1.00, 24/7", [
        "InpNyOnly=false", "InpTargetR=0", "InpBreakEvenR=0", "InpSlMode=0"]),
    ("NY only, same geometry", [
        "InpNyOnly=true", "InpTargetR=0", "InpBreakEvenR=0", "InpSlMode=0"]),
    ("24/7 + 2R + BE@1R", [
        "InpNyOnly=false", "InpTargetR=2", "InpBreakEvenR=1", "InpSlMode=0"]),
    ("NY + 2R + BE@1R", [
        "InpNyOnly=true", "InpTargetR=2", "InpBreakEvenR=1", "InpSlMode=0"]),
    ("NY + 2R + BE + deep low (camel)", [
        "InpNyOnly=true", "InpTargetR=2", "InpBreakEvenR=1", "InpSlMode=1",
        "InpTrendMode=1"]),
    ("NY + 2R, NO breakeven", [
        "InpNyOnly=true", "InpTargetR=2", "InpBreakEvenR=0", "InpSlMode=0"]),
    ("NY + 1.5R + BE@1R", [
        "InpNyOnly=true", "InpTargetR=1.5", "InpBreakEvenR=1", "InpSlMode=0"]),
]


def read_report(p: Path) -> str:
    for enc in ("utf-16", "utf-16-le", "utf-8"):
        try:
            t = p.read_text(encoding=enc, errors="replace")
            if "<" in t:
                return t
        except Exception:
            continue
    return ""


def per_day(p: Path):
    """Realised P&L by broker day, from the report's DEALS table.

    Only 'out' deals carry profit; 'in' deals open a position and always show 0.00.
    Summing every row would double-count nothing but would drag the balance rows in,
    so the direction column is what selects a close."""
    t = read_report(p)
    if not t:
        return {}, 0, 0
    i = t.lower().find(">deals<")
    if i < 0:
        return {}, 0, 0
    seg = t[i:]
    day = defaultdict(float)
    wins = losses = 0
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", seg, re.S | re.I):
        cells = [re.sub(r"<[^>]+>", "", c).replace(" ", " ").strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        if len(cells) < 12:
            continue
        stamp, direction = cells[0], cells[4]
        if direction.lower() != "out":
            continue
        m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", stamp)
        if not m:
            continue
        # NET, not gross. Columns run ... Commission(8) Swap(9) Profit(10), and
        # the report's own "Total Net Profit" is the sum of all three. Summing
        # Profit alone under-reported a known window by $54.40 - small here, but
        # swap took 45% of the gross on the 04 Sep live basket, so it is not a
        # rounding detail.
        def cell(n):
            try:
                return float(re.sub(r'[^0-9.+-]', '', cells[n]))
            except (ValueError, IndexError):
                return 0.0
        profit = cell(8) + cell(9) + cell(10)
        day["%s-%s-%s" % m.groups()] += profit
        if profit > 0:
            wins += 1
        elif profit < 0:
            losses += 1
    return dict(day), wins, losses


def run_arm(label, inputs, frm, to, deposit, delay, model, idx):
    name = "RR_%d_%s" % (idx, datetime.now().strftime("%H%M%S"))
    ini = ROOT / "mt5" / "_rr_court.ini"
    lines = ["[Tester]"]
    for k, v in [("Expert", "ZeeUHV_Diamond"), ("Symbol", "XAUUSD"), ("Period", "M1"),
                 ("Model", model), ("FromDate", frm), ("ToDate", to),
                 ("Deposit", deposit), ("Currency", "USD"), ("Leverage", "1:500"),
                 ("ExecutionMode", delay), ("Optimization", 0),
                 ("Report", name), ("ReplaceReport", 1),
                 ("ShutdownTerminal", 1), ("Visual", 0)]:
        lines.append(str(k) + "=" + str(v))
    lines += ["", "[TesterInputs]"] + BASE + inputs
    ini.write_text("\n".join(lines) + "\n", encoding="utf-16")

    block_autoupdate()
    kill_stubs()
    t0 = time.time()
    print("[rr] %-30s running…" % label, flush=True)
    try:
        subprocess.run([str(TEST_EXE), "/portable", "/config:" + str(ini)],
                       timeout=14400, capture_output=True)
    except subprocess.TimeoutExpired:
        print("[rr] %s TIMED OUT" % label)
    rpt = None
    for ext in (".htm", ".html"):
        srcp = RIG / (name + ext)
        if srcp.exists():
            rpt = REPORTS / (name + ext)
            shutil.copy(srcp, rpt)
            break
    if not rpt:
        print("[rr] %s: NO REPORT" % label)
        return None
    d, w, l = per_day(rpt)
    print("[rr] %-30s %d days, %dW/%dL, net %.2f  (%.0fs)"
          % (label, len(d), w, l, sum(d.values()), time.time() - t0), flush=True)
    return {"label": label, "day": d, "wins": w, "losses": l, "report": rpt}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", default="2026.08.17")
    ap.add_argument("--to", dest="to", default="2026.09.05")
    ap.add_argument("--deposit", type=int, default=50000)
    ap.add_argument("--delay", type=int, default=163)
    ap.add_argument("--model", type=int, default=4)
    args = ap.parse_args()

    live_is_safe()
    stage()
    sync_experts()
    if not build():
        sys.exit(1)
    print("[rr] %s -> %s, real ticks, %d arms\n" % (args.frm, args.to, len(ARMS)),
          flush=True)

    out = []
    for i, (label, inputs) in enumerate(ARMS):
        r = run_arm(label, inputs, args.frm, args.to, args.deposit, args.delay,
                    args.model, i)
        if r:
            out.append(r)
    if not out:
        sys.exit("[rr] nothing completed")

    days = sorted({d for r in out for d in r["day"]})
    print("\n=== PER DAY (broker) — real ticks, %s to %s ===" % (args.frm, args.to))
    head = "%-12s" % "day" + "".join("%13s" % ("arm %d" % i) for i in range(len(out)))
    print(head)
    print("-" * len(head))
    for d in days:
        print("%-12s" % d + "".join("%13.2f" % r["day"].get(d, 0.0) for r in out))
    print("-" * len(head))
    print("%-12s" % "TOTAL" + "".join("%13.2f" % sum(r["day"].values()) for r in out))
    print("%-12s" % "per day" + "".join(
        "%13.2f" % (sum(r["day"].values()) / max(1, len(r["day"]))) for r in out))
    print("%-12s" % "green days" + "".join(
        "%13s" % ("%d/%d" % (sum(1 for v in r["day"].values() if v > 0), len(r["day"])))
        for r in out))
    print("%-12s" % "W/L" + "".join("%13s" % ("%d/%d" % (r["wins"], r["losses"]))
                                    for r in out))
    print("%-12s" % "win rate" + "".join(
        "%12.0f%%" % (100.0 * r["wins"] / max(1, r["wins"] + r["losses"])) for r in out))
    print()
    for i, r in enumerate(out):
        print("  arm %d = %s" % (i, r["label"]))


if __name__ == "__main__":
    main()
