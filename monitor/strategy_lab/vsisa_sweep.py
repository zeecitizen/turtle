"""vsisa_sweep.py — the VARIANT SEARCH, run as an MT5 optimisation.

Zee, 2026-09-09: "Find any variants / loosen - tighten the laws to find out the most
profitable variant"

WHY THIS FILE EXISTS ALONGSIDE vsisa_court.py. A single backtest occupies ONE core and
costs ~10 minutes almost regardless of window length — the cost is loading real ticks,
not simulating them. Forty variants that way is seven hours. An OPTIMISATION run splits
the same grid across the rig's 8 local agents and reports every pass in one XML, so the
coarse search costs a fraction of that.

What it gives up: the XML has no trade list, so it cannot answer "which day paid". That
is exactly what vsisa_court.py is for. The division of labour is deliberate —
    sweep  -> narrow 40 variants down to 3 finalists
    court  -> take those 3 apart per day, with the funnel printed

MT5 sweep syntax, both learned the hard way:
  * a swept input is  Name=default||start||step||stop||Y
  * a BOOLEAN must be written NUMERICALLY (0||0||1||1||Y). "false||0||true" is rejected
    with "no optimized parameter selected" and the run exits in ~55s having written a
    header-only report that looks like a legitimate empty result.

    py monitor/strategy_lab/vsisa_sweep.py --grid open
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from mt5_headless import RIG, REPORTS, TEST_EXE, live_is_safe, sync_experts  # noqa: E402
from trend_lab import block_autoupdate, kill_stubs, stage  # noqa: E402
from vsisa_court import EA, build, ea_log_tail  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent.parent

# Each entry is either a fixed "Inp=value" or a sweep "Inp=d||start||step||stop||Y".
GRIDS = {
    # Where does the engine start producing a usable number of setups at all?
    "open": [
        "InpBigMode=1||0||1||1||Y",
        "InpClusterBars=2||2||1||3||Y",
        "InpBigPct=0.50||0.35||0.15||0.80||Y",
        "InpLowVolPct=0.80||0.50||0.15||0.95||Y",
        "InpBigAvg=1.20",
        "InpBodyFrac=0.35",
        "InpTargetR=2.0",
    ],
    # THE EDGES. The first "open" sweep returned BigPct=0.80 and LowVolPct=0.95 in
    # every one of its top rows — and both were the LARGEST value offered. When a
    # winner sits on the wall of the grid, the grid picked it, not the data. This runs
    # past both walls. LowVolPct deliberately goes ABOVE 1.0, where the trigger stops
    # constraining anything: if the best result is out there, LAW 3 as coded contributes
    # nothing and I need to say so rather than keep it because the teacher stressed it.
    "edges": [
        "InpBigPct=0.80||0.70||0.10||1.00||Y",
        "InpLowVolPct=0.95||0.80||0.10||1.30||Y",
        "InpQuietRef=0||0||1||1||Y",
        "InpClusterBars=2||2||1||3||Y",
        "InpBigMode=1",
        "InpBigAvg=1.20",
        "InpBodyFrac=0.35",
        "InpTargetR=2.0",
    ],
    # Given a cluster shape that fires, what geometry pays?
    "geom": [
        "InpTargetR=2.0||1.0||0.5||4.0||Y",
        "InpSlBufPts=30||10||20||70||Y",
        "InpMinSlPts=60||30||30||120||Y",
        "InpBreakEvenR=0||0||1||1||Y",
    ],
    # The laws that ship OFF, swept together so an interaction can show.
    "laws": [
        "InpWickMode=0||0||1||2||Y",
        "InpAnomaly=0||0||1||1||Y",
        "InpFakeBreak=0||0||1||1||Y",
        "InpEngulf=0||0||1||1||Y",
        "InpTrendTF=0||0||60||60||Y",
    ],
    # His two entries: the aggressive one on the reaction bar, and the confirmed one
    # that waits for a no-supply test. Part 17 says the confirmed entry costs a wider
    # stop (22-30 pips against 8-9) and buys fewer stop-outs — so the two cannot be
    # compared on win rate alone, only on net.
    "confirm": [
        "InpConfirmMode=0||0||1||1||Y",
        "InpTestVolPct=0.70||0.50||0.20||0.90||Y",
        "InpTargetR=2.0||1.5||0.5||3.0||Y",
        "InpBigMode=1",
        "InpClusterBars=2",
        "InpLowVolPct=0.80",
        "InpBigPct=0.50",
        "InpBigAvg=1.20",
        "InpBodyFrac=0.35",
    ],
    # GEOMETRY x THE OPTIONAL LAWS, on the cluster shape the "edges" sweep chose.
    # 336 passes costs the same wall-clock as 64 did: 96 passes took 644s against 64
    # passes at 639s, because ~9 minutes of every run is tick-history synchronisation
    # and each pass itself takes 0.44s. Cheap breadth — so take it.
    "big": [
        "InpTargetR=2.0||1.0||0.5||4.0||Y",
        "InpSlBufPts=30||10||20||70||Y",
        "InpBreakEvenR=0||0||1||1||Y",
        "InpWickMode=0||0||1||2||Y",
        "InpFakeBreak=0||0||1||1||Y",
        "InpBigMode=1",
        "InpClusterBars=2",
        "InpBigPct=0.80",
        "InpLowVolPct=1.00",
        "InpQuietRef=0",
        "InpBigAvg=1.20",
        "InpBodyFrac=0.35",
    ],
    # THE FINAL QUESTIONS, asked over SEVEN MONTHS rather than one. Does his confirmed
    # entry (the no-supply test) beat his aggressive one? Does the H1 trend filter earn
    # its place? Run across Feb-Aug so the answer is not another August artefact.
    "final": [
        "InpConfirmMode=0||0||1||1||Y",
        "InpTrendTF=0||0||60||60||Y",
        "InpTargetR=2.5||2.0||0.5||3.0||Y",
        "InpSlBufPts=30||30||20||50||Y",
        "InpBreakEvenR=1||0||1||1||Y",
        "InpClusterBars=2||2||1||3||Y",
        "InpBigMode=1",
        "InpBigPct=0.80",
        "InpLowVolPct=1.00",
        "InpQuietRef=0",
        "InpBigAvg=1.20",
        "InpBodyFrac=0.35",
    ],
    # THE NO-SUPPLY TEST, RE-ASKED after the reference bug was fixed. The first attempt
    # compared the test bar to the already-quiet reaction bar and fired zero trades in
    # 48 passes — that was my arithmetic, not his rule, so the law had not actually been
    # tested at all. Now measured against the climax like every other "small volume".
    "confirm2": [
        "InpConfirmMode=0||0||1||1||Y",
        "InpTestVolPct=0.90||0.70||0.20||1.30||Y",
        "InpTrendTF=60||0||60||60||Y",
        "InpBigMode=1",
        "InpClusterBars=2",
        "InpBigPct=0.80",
        "InpLowVolPct=1.00",
        "InpQuietRef=0",
        "InpBigAvg=1.20",
        "InpBodyFrac=0.35",
        "InpTargetR=2.5",
        "InpSlBufPts=30",
        "InpBreakEvenR=1",
    ],
    # THE LAWS NOTHING ELSE COVERED. The August "big" sweep tested the wick and the
    # fake break but never touched the anomaly, the engulfing reaction, rising cluster
    # volume, or the lookback length. Untested is not the same as rejected, so they get
    # their own run rather than a shrug in the writeup.
    "rest": [
        "InpAnomaly=0||0||1||1||Y",
        "InpEngulf=0||0||1||1||Y",
        "InpRisingVol=0||0||1||1||Y",
        "InpVolLookback=100||60||40||140||Y",
        "InpBigMode=1",
        "InpClusterBars=2",
        "InpBigPct=0.80",
        "InpLowVolPct=1.00",
        "InpQuietRef=0",
        "InpBigAvg=1.20",
        "InpBodyFrac=0.35",
        "InpTargetR=2.5",
        "InpSlBufPts=30",
        "InpBreakEvenR=1",
        "InpTrendTF=60",
    ],
    # HOW FAR BACK IS "RECENT". The "rest" sweep returned VolLookback=60 as best — and
    # 60 was the SMALLEST value offered, so the wall picked it again. This goes below.
    # 60 M5 bars is 5 hours, i.e. roughly one session, which is what he actually says
    # ("compare with this session, and the last two or three days").
    "look": [
        "InpVolLookback=60||30||15||105||Y",
        "InpBigMode=1",
        "InpClusterBars=2",
        "InpBigPct=0.80",
        "InpLowVolPct=1.00",
        "InpQuietRef=0",
        "InpBigAvg=1.20",
        "InpBodyFrac=0.35",
        "InpTargetR=2.5",
        "InpSlBufPts=30",
        "InpBreakEvenR=1",
        "InpTrendTF=60",
    ],
    # Is "low volume" measured against the climax, or against normal?
    "quiet": [
        "InpQuietRef=0||0||1||1||Y",
        "InpLowVolPct=0.80||0.40||0.10||1.20||Y",
        "InpBigMode=1",
        "InpClusterBars=2",
    ],
}


def parse_xml(p: Path):
    """MT5's optimisation XML is SpreadsheetML: one Row per pass, first Row the header.
    Column names vary by build, so they are read rather than assumed."""
    try:
        tree = ET.parse(p)
    except Exception as e:  # noqa: BLE001
        print("[sweep] cannot parse %s: %s" % (p.name, e))
        return []
    ns = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
    rows = tree.getroot().iter("{%s}Row" % ns["ss"])
    out, head = [], None
    for row in rows:
        cells = []
        for c in row.iter("{%s}Cell" % ns["ss"]):
            d = c.find("{%s}Data" % ns["ss"])
            cells.append("" if d is None or d.text is None else d.text.strip())
        if head is None:
            head = cells
            continue
        if len(cells) < len(head):
            cells += [""] * (len(head) - len(cells))
        out.append(dict(zip(head, cells)))
    return out


def num(x, default=0.0):
    """Zero-trade passes leave Profit Factor EMPTY. An untolerant float() threw here and
    silently DISCARDED those rows, which once turned 50 minutes of correct testing into
    'no arm completed'."""
    try:
        return float(str(x).replace(" ", "").replace(",", ""))
    except (TypeError, ValueError):
        return default


def col(row, *names):
    for n in names:
        for k in row:
            if k.lower().strip() == n.lower():
                return row[k]
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="open")
    ap.add_argument("--from", dest="frm", default="2026.08.05")
    ap.add_argument("--to", dest="to", default="2026.09.06")
    ap.add_argument("--period", default="M5")
    ap.add_argument("--deposit", type=int, default=50000)
    ap.add_argument("--delay", type=int, default=163)
    ap.add_argument("--model", type=int, default=4)
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    grid = GRIDS.get(args.grid)
    if not grid:
        sys.exit("[sweep] unknown grid %r — have %s" % (args.grid, ", ".join(GRIDS)))

    live_is_safe()
    stage()
    sync_experts()
    if not build():
        sys.exit(1)

    name = "VSISASWEEP_%s_%s" % (args.grid, datetime.now().strftime("%H%M%S"))
    ini = ROOT / "mt5" / "_vsisa_sweep.ini"
    lines = ["[Tester]"]
    for k, v in [("Expert", EA), ("Symbol", "XAUUSD"), ("Period", args.period),
                 ("Model", args.model), ("FromDate", args.frm), ("ToDate", args.to),
                 ("Deposit", args.deposit), ("Currency", "USD"), ("Leverage", "1:500"),
                 ("ExecutionMode", args.delay),
                 # 1 = SLOW COMPLETE. 2 is genetic and stops early, which for a grid
                 # this small would hide variants rather than save time.
                 ("Optimization", 1),
                 ("OptimizationCriterion", 0),   # 0 = max balance; we re-rank ourselves
                 ("Report", name), ("ReplaceReport", 1),
                 ("ShutdownTerminal", 1), ("Visual", 0)]:
        lines.append("%s=%s" % (k, v))
    lines += ["", "[TesterInputs]"] + list(grid)
    ini.write_text("\n".join(lines) + "\n", encoding="utf-16")

    block_autoupdate()
    kill_stubs()
    print("[sweep] grid %s · %s %s -> %s · real ticks · 8 agents"
          % (args.grid, args.period, args.frm, args.to), flush=True)
    for g in grid:
        print("        " + g)
    t0 = time.time()
    try:
        subprocess.run([str(TEST_EXE), "/portable", "/config:" + str(ini)],
                       timeout=28800, capture_output=True)
    except subprocess.TimeoutExpired:
        print("[sweep] TIMED OUT")

    src = None
    for ext in (".xml", ".htm", ".html"):
        c = RIG / (name + ext)
        if c.exists():
            src = REPORTS / (name + ext)
            shutil.copy(c, src)
            if ext == ".xml":
                break
    if not src:
        print("[sweep] NO REPORT after %.0fs" % (time.time() - t0))
        for l in ea_log_tail():
            print("        " + l)
        sys.exit(1)

    rows = parse_xml(src)
    print("\n[sweep] %d passes in %.0fs -> %s\n" % (len(rows), time.time() - t0, src.name))
    if not rows:
        sys.exit(0)

    swept = [g.split("=")[0] for g in grid if "||" in g]
    scored = []
    for r in rows:
        trades = int(num(col(r, "Trades", "Total Trades")))
        scored.append({
            "profit": num(col(r, "Profit", "Net Profit")),
            "trades": trades,
            "pf": num(col(r, "Profit Factor")),
            "dd": num(col(r, "Equity DD %", "Drawdown", "Equity Drawdown Maximal")),
            "vals": {s: col(r, s) for s in swept},
        })
    scored.sort(key=lambda x: -x["profit"])

    hdr = "%9s %7s %6s %8s   " % ("profit", "trades", "PF", "DD%") + \
          "  ".join("%-15s" % s.replace("Inp", "") for s in swept)
    print(hdr)
    print("-" * len(hdr))
    for r in scored[:args.top]:
        print("%9.2f %7d %6.2f %8.2f   " % (r["profit"], r["trades"], r["pf"], r["dd"])
              + "  ".join("%-15s" % r["vals"].get(s, "") for s in swept))

    live = [r for r in scored if r["trades"] >= 10]
    print("\n[sweep] %d/%d passes took >=10 trades; best of those:" % (len(live), len(scored)))
    for r in live[:5]:
        print("   %9.2f  %3d trades  PF %.2f   %s"
              % (r["profit"], r["trades"], r["pf"],
                 "  ".join("%s=%s" % (k.replace("Inp", ""), v)
                           for k, v in r["vals"].items())))
    if not live:
        print("   NONE — the engine is not producing trades at any point in this grid.")


if __name__ == "__main__":
    main()
