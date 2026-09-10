"""vsisa_court.py — VSISA in MT5's Strategy Tester, on M5, on real ticks.

Zee, 2026-09-09: "Implement this strategy as an EA. then test this EA's performance on
the 5 minute chart... Find any variants / loosen - tighten the laws to find out the most
profitable variant"

WHY BACKTESTS AND NOT AN OPTIMISATION RUN. An optimisation report is one row per pass —
net, PF, drawdown — with NO trade list, so it cannot say which day paid or how many
setups a tightening actually refused. Every arm here is its own backtest and the DEALS
table is parsed out of the HTML, which is the only place realised per-deal profit lives.

Each arm is ONE law moved off its default, so a change in the number can be attributed
to a law rather than to a soup. That is the whole point of the file.

    py monitor/strategy_lab/vsisa_court.py --arms core
    py monitor/strategy_lab/vsisa_court.py --arms laws --from 2026.08.05 --to 2026.09.06
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
from trend_lab import block_autoupdate, kill_stubs, stage  # noqa: E402
from rr_court import read_report  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent.parent
EA = "VSISA"
ME = Path(r"C:/Program Files/Blueberry Markets MetaTrader 5/metaeditor64.exe")

# The EA's own defaults are the baseline; an arm lists ONLY what it changes.
ARM_SETS = {
    # CALIBRATION. v1.00's literal reading of LAW 5 fired ZERO trades in two days:
    # 1104 candidates, 597 lost to the 3-same-direction rule, 498 to loudness, leaving
    # 9 that ever reached the trigger — and the quietest reaction was 0.83x cluster
    # against a 0.60x requirement. So the funnel is starved at the top, not at the
    # trigger. These arms open it, one loosening at a time.
    "calib": [
        ("BASE  literal LAW 5", []),
        ("bigmode1 loudest bar", ["InpBigMode=1"]),
        ("bigmode1 + 2-bar", ["InpBigMode=1", "InpClusterBars=2"]),
        ("big 0.50/1.30", ["InpBigPct=0.50", "InpBigAvg=1.30"]),
        ("big 0.40/1.20 + 2-bar", ["InpBigPct=0.40", "InpBigAvg=1.20",
                                   "InpClusterBars=2"]),
        ("bigmode1 + quiet 0.80", ["InpBigMode=1", "InpLowVolPct=0.80"]),
        ("bigmode1 + 2-bar + quiet 0.80", ["InpBigMode=1", "InpClusterBars=2",
                                           "InpLowVolPct=0.80"]),
        ("open: 2-bar q0.90 b0.40", ["InpBigMode=1", "InpClusterBars=2",
                                     "InpLowVolPct=0.90", "InpBigPct=0.40",
                                     "InpBigAvg=1.20", "InpBodyFrac=0.35"]),
    ],
    # Does the engine fire at all, and does the shape of the cluster matter?
    "core": [
        ("BASE  3-bar, 2R", []),
        ("2-bar cluster", ["InpClusterBars=2"]),
        ("3-bar + rising volume", ["InpRisingVol=true"]),
        ("looser big (0.55x max)", ["InpBigPct=0.55", "InpBigAvg=1.30"]),
        ("tighter big (0.85x max)", ["InpBigPct=0.85", "InpBigAvg=2.00"]),
        ("looser quiet (0.80x)", ["InpLowVolPct=0.80"]),
        ("tighter quiet (0.40x)", ["InpLowVolPct=0.40"]),
    ],
    # The laws that ship OFF. Each gets exactly one arm.
    "laws": [
        ("BASE", []),
        ("LAW 6  wick required", ["InpWickMode=1"]),
        ("LAW 6  wick as override", ["InpWickMode=2"]),
        ("LAW 7  anomaly cluster", ["InpAnomaly=true"]),
        ("LAW 13 fake break", ["InpFakeBreak=true"]),
        ("LAW 9  H1 trend only", ["InpTrendTF=60"]),
        ("LAW 2+ engulfing reaction", ["InpEngulf=true"]),
    ],
    # LAW 8 — the geometry he insists on, against wider variants.
    "geom": [
        ("BASE  2R, buf 30, floor 60", []),
        ("1.5R", ["InpTargetR=1.5"]),
        ("3R", ["InpTargetR=3"]),
        ("4R", ["InpTargetR=4"]),
        ("2R + BE at 1R", ["InpBreakEvenR=1"]),
        ("tight stop  buf 10 floor 30", ["InpSlBufPts=10", "InpMinSlPts=30"]),
        ("wide stop  buf 60 floor 120", ["InpSlBufPts=60", "InpMinSlPts=120"]),
    ],
}


def build():
    """Compile the working tree into the rig. MUST run after sync_experts(), which
    copies the LIVE terminal's older .ex5 over the top and would otherwise silently
    test yesterday's build."""
    src = ROOT / "mt5" / (EA + ".mq5")
    dst = RIG / "MQL5" / "Experts" / src.name
    shutil.copy(src, dst)
    log = RIG / "vsisa_compile.log"
    subprocess.run([str(ME), "/compile:" + str(dst), "/log:" + str(log)],
                   capture_output=True, timeout=180)
    txt = ""
    for enc in ("utf-16", "utf-8"):
        try:
            txt = log.read_text(encoding=enc, errors="replace")
            if txt.strip():
                break
        except Exception:
            pass
    errs = [l for l in txt.splitlines() if " error " in l.lower()]
    if errs or not dst.with_suffix(".ex5").exists():
        print("[vsisa] COMPILE FAILED")
        for e in errs[:10]:
            print("   ", e.strip())
        return False
    return True


AGENT_LOG = Path(r"C:/mt5_rig/Tester/Agent-127.0.0.1-3000/logs")


def ea_log_tail(n=6):
    """The EA's FUNNEL and REACH lines land in the agent log, not the HTML report.
    Without them a zero-trade arm is indistinguishable from a broken one — which is
    exactly how the first five-day run was wasted. Logs are UTF-16."""
    try:
        f = sorted(AGENT_LOG.glob("*.log"))[-1]
        txt = f.read_bytes()[-4_000_000:].decode("utf-16-le", errors="replace")
    except Exception:
        return []
    hits = [l.split("	")[-1].strip() for l in txt.splitlines()
            if "[VSISA] FUNNEL" in l or "[VSISA] REACH" in l
            or "[VSISA] VOLUME SOURCE" in l]
    return hits[-n:]


def per_day(p: Path):
    """Realised P&L by broker day. Only 'out' deals carry profit.

    NET, not gross: columns run ... Commission(8) Swap(9) Profit(10) and the report's
    own Total Net Profit is the sum of all three. Summing Profit alone under-reported a
    known window by $54.40."""
    t = read_report(p)
    if not t:
        return {}, 0, 0
    i = t.lower().find(">deals<")
    if i < 0:
        return {}, 0, 0
    day = defaultdict(float)
    wins = losses = 0
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", t[i:], re.S | re.I):
        cells = [re.sub(r"<[^>]+>", "", c).replace("\u00a0", " ").strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        if len(cells) < 12 or cells[4].lower() != "out":
            continue
        m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", cells[0])
        if not m:
            continue

        def cell(n):
            try:
                return float(re.sub(r"[^0-9.+-]", "", cells[n]))
            except (ValueError, IndexError):
                return 0.0

        profit = cell(8) + cell(9) + cell(10)
        day["%s-%s-%s" % m.groups()] += profit
        if profit > 0:
            wins += 1
        elif profit < 0:
            losses += 1
    return dict(day), wins, losses


def run_arm(label, inputs, frm, to, period, deposit, delay, model, idx,
            symbol="XAUUSD"):
    name = "VSISA_%d_%s" % (idx, datetime.now().strftime("%H%M%S"))
    ini = ROOT / "mt5" / "_vsisa_court.ini"
    lines = ["[Tester]"]
    for k, v in [("Expert", EA), ("Symbol", symbol), ("Period", period),
                 ("Model", model), ("FromDate", frm), ("ToDate", to),
                 ("Deposit", deposit), ("Currency", "USD"), ("Leverage", "1:500"),
                 ("ExecutionMode", delay), ("Optimization", 0),
                 ("Report", name), ("ReplaceReport", 1),
                 ("ShutdownTerminal", 1), ("Visual", 0)]:
        lines.append("%s=%s" % (k, v))
    # NEVER SEND AN EMPTY [TesterInputs]. Doing so does NOT fall back to the compiled
    # defaults — MT5 reuses whatever inputs it cached for this EA from a previous run.
    # A "defaults" validation run came back with 0 trades and a REACH line quoting
    # thresholds that had been replaced two hours earlier. Every arm states its values.
    if not inputs:
        raise SystemExit("[vsisa] refusing to run with an empty input list — state the "
                         "config explicitly; MT5 will silently reuse cached inputs")
    lines += ["", "[TesterInputs]"] + list(inputs)
    ini.write_text("\n".join(lines) + "\n", encoding="utf-16")

    block_autoupdate()
    kill_stubs()
    t0 = time.time()
    print("[vsisa] %-28s running…" % label, flush=True)
    try:
        subprocess.run([str(TEST_EXE), "/portable", "/config:" + str(ini)],
                       timeout=14400, capture_output=True)
    except subprocess.TimeoutExpired:
        print("[vsisa] %s TIMED OUT" % label)
    rpt = None
    for ext in (".htm", ".html"):
        srcp = RIG / (name + ext)
        if srcp.exists():
            rpt = REPORTS / (name + ext)
            shutil.copy(srcp, rpt)
            break
    if not rpt:
        print("[vsisa] %s: NO REPORT" % label)
        return None
    d, w, l = per_day(rpt)
    for line in ea_log_tail():
        print("        " + line, flush=True)
    print("[vsisa] %-28s %2d days  %3dW/%3dL  net %9.2f  (%.0fs)"
          % (label, len(d), w, l, sum(d.values()), time.time() - t0), flush=True)
    return {"label": label, "day": d, "wins": w, "losses": l,
            "report": rpt, "inputs": inputs}


def table(out, frm, to, period):
    days = sorted({d for r in out for d in r["day"]})
    print("\n=== VSISA PER DAY — %s real ticks, %s to %s ===" % (period, frm, to))
    head = "%-12s" % "day" + "".join("%12s" % ("arm %d" % i) for i in range(len(out)))
    print(head)
    print("-" * len(head))
    for d in days:
        print("%-12s" % d + "".join("%12.2f" % r["day"].get(d, 0.0) for r in out))
    print("-" * len(head))
    print("%-12s" % "TOTAL" + "".join("%12.2f" % sum(r["day"].values()) for r in out))
    print("%-12s" % "trades" + "".join("%12d" % (r["wins"] + r["losses"]) for r in out))
    print("%-12s" % "win rate" + "".join(
        "%11.0f%%" % (100.0 * r["wins"] / max(1, r["wins"] + r["losses"])) for r in out))
    print("%-12s" % "green days" + "".join(
        "%12s" % ("%d/%d" % (sum(1 for v in r["day"].values() if v > 0), len(r["day"])))
        for r in out))
    print()
    for i, r in enumerate(out):
        print("  arm %d = %-28s %s" % (i, r["label"], " ".join(r["inputs"]) or "(defaults)"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", default="2026.08.05")
    ap.add_argument("--to", dest="to", default="2026.09.06")
    ap.add_argument("--period", default="M5")
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--arms", default="core")
    ap.add_argument("--inputs", default="", help="one-off arm, space separated Inp=..")
    ap.add_argument("--deposit", type=int, default=50000)
    ap.add_argument("--delay", type=int, default=163)
    ap.add_argument("--model", type=int, default=4)
    args = ap.parse_args()

    live_is_safe()
    stage()
    sync_experts()
    if not build():
        sys.exit(1)

    if args.inputs:
        arms = [("one-off", args.inputs.split())]
    else:
        arms = ARM_SETS.get(args.arms)
        if not arms:
            sys.exit("[vsisa] unknown arm set %r — have %s"
                     % (args.arms, ", ".join(ARM_SETS)))

    print("[vsisa] %s %s -> %s, real ticks, %d arms\n"
          % (args.period, args.frm, args.to, len(arms)), flush=True)
    out = []
    for i, (label, inputs) in enumerate(arms):
        r = run_arm(label, inputs, args.frm, args.to, args.period,
                    args.deposit, args.delay, args.model, i, args.symbol)
        if r:
            out.append(r)
    if not out:
        sys.exit("[vsisa] nothing completed")
    table(out, args.frm, args.to, args.period)


if __name__ == "__main__":
    main()
