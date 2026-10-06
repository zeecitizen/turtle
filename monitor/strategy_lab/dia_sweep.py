"""dia_sweep.py — parameter SWEEPS of ZeeUHV_Diamond in MT5's own optimiser.

Zee, 2026-09-29: "run the MT5 strategy tester on the EA ... try to increase the Winrate of
the EA to maximum possible ... Loop until you have maximized the winrate by tuning the EA
and testing it only in MT5 strategy tester (python tests are not useful we documented this)"

WHY AN OPTIMISER AND NOT A LOOP OF BACKTESTS. One real-tick backtest of a 9-day window takes
~10.5 minutes, so a serial loop buys about five configs an hour. MT5's optimiser runs the
same real-tick passes across all 8 local agents at once, which is the difference between
five configs an hour and forty. Nothing about the measurement changes: every pass is a full
Strategy Tester run on the broker's stored ticks with the recorded spread and a 163 ms
execution delay, exactly as diamond_lab.py runs a single one.

AND THE RANKING IS ALREADY THE OBJECTIVE. ZeeUHV_Diamond's OnTester() returns
(wins/trades)*100 - the win rate MT5 itself measured - and returns 0.0 for any pass with
fewer than InpMinTrades trades or a net loss. So OptimizationCriterion=6 (custom max) IS
"maximise win rate", with the two guards that stop the search cheating: it cannot win by
taking one lucky trade, and it cannot win by bleeding money at a high hit rate.

THE TRAP THIS FILE CANNOT REMOVE, ONLY REPORT. Win rate in this geometry is largely bought,
not earned: NullEntry - an EA with NO RULES that fires every 30 minutes - scored 92.42% over
1,716 trades on the same 1-point target and 20-point stop. So a wider stop WILL raise the
win rate and that is arithmetic, not an edge. Every table this prints therefore carries net
profit and trade count beside the win rate, and `dia_winrate.py` re-runs any winner as a
single backtest to recover the loss distribution the optimiser's report does not carry.

  py monitor/strategy_lab/dia_sweep.py sweep.json
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import diamond_lab as D   # noqa: E402  - same rig, same kill-by-path safety, same EA sync

REPORTS = D.ROOT / "mt5" / "_tester_runs" / "diamond"
CAMEL = {"InpTrendMode": "1", "InpHighTest": "1"}


def build_ini(sweep: dict, frm: str, to: str, name: str) -> Path:
    """Write [Tester] + [TesterInputs], pinning EVERY input and ranging the swept ones.

    Pinning all of them is not belt-and-braces. mt5_headless.py writes only [Tester], so
    MT5 falls back to whatever inputs were last cached in MQL5/Profiles/Tester/<EA>.set -
    and there is no ZeeUHV_Diamond.set in the rig at all, so the fallback would be the
    EA's compiled defaults silently substituting for the configuration under test.
    """
    cfg = dict(D.SHIPPED)
    cfg.update(CAMEL)
    cfg.update({k: str(v) for k, v in sweep.get("pin", {}).items()})

    lines = ["[Tester]"]
    for k, v in [("Expert", D.EA), ("Symbol", D.SYMBOL), ("Period", "M1"),
                 ("Model", sweep.get("model", 4)),
                 ("FromDate", frm), ("ToDate", to),
                 ("Deposit", sweep.get("deposit", 100000)),
                 ("Currency", "USD"), ("Leverage", "1:500"),
                 ("ExecutionMode", 163),
                 # 1 = SLOW COMPLETE. 2 is genetic and stops early - it once ran 176 of
                 # 5,280 passes and looked like a finished sweep.
                 ("Optimization", 1),
                 ("OptimizationCriterion", 6),        # 6 = custom = OnTester = win rate
                 ("Report", name), ("ReplaceReport", 1),
                 ("ShutdownTerminal", 1), ("Visual", 0)]:
        lines.append("%s=%s" % (k, v))

    lines += ["", "[TesterInputs]"]
    ranges = sweep["ranges"]
    for k, v in cfg.items():
        if k in ranges:
            continue
        lines.append("%s=%s" % (k, v))
    # MT5's range syntax: value||start||step||stop||Y   (Y = include in the sweep)
    for k, r in ranges.items():
        lines.append("%s=%s||%s||%s||%s||Y" % (k, r["start"], r["start"], r["step"], r["stop"]))

    ini = D.ROOT / "mt5" / "_diamond_sweep.ini"
    ini.write_text("\n".join(lines) + "\n", encoding="utf-16")
    return ini


def n_passes(sweep: dict) -> int:
    n = 1
    for r in sweep["ranges"].values():
        start, step, stop = float(r["start"]), float(r["step"]), float(r["stop"])
        n *= max(1, int(round((stop - start) / step)) + 1)
    return n


def run(sweep: dict) -> Path | None:
    frm, to = sweep["window"]
    name = "SWP_%s" % datetime.now().strftime("%H%M%S")
    ini = build_ini(sweep, frm, to, name)
    print("[sweep] %s" % sweep.get("title", name))
    print("[sweep] %s -> %s  ·  %d passes  ·  %s"
          % (frm, to, n_passes(sweep),
             " x ".join("%s %s..%s/%s" % (k, r["start"], r["stop"], r["step"])
                        for k, r in sweep["ranges"].items())), flush=True)
    D.sync_ea()
    D.kill_rig()
    t0 = datetime.now()
    try:
        subprocess.run([str(D.EXE), "/portable", "/config:" + str(ini)],
                       timeout=sweep.get("timeout", 20000), capture_output=True)
    except subprocess.TimeoutExpired:
        print("[sweep] TIMEOUT — killing the rig; a partial report may still exist")
        D.kill_rig()
    print("[sweep] finished in %.0f min" % ((datetime.now() - t0).total_seconds() / 60.0),
          flush=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    for ext in (".xml", ".htm"):
        src = D.RIG / (name + ext)
        if src.exists():
            dst = REPORTS / (name + ext)
            dst.write_bytes(src.read_bytes())
            try:
                src.unlink()
            except Exception:
                pass
            if ext == ".xml":
                return dst
    print("[sweep] NO REPORT — check the rig's Tester logs")
    return None


def read(path: Path, top: int = 25) -> list:
    raw = path.read_bytes()
    t = raw.decode("utf-16", errors="ignore") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") \
        else raw.decode("utf-8", errors="ignore")
    rows = re.findall(r"<Row[^>]*>(.*?)</Row>", t, re.S)
    if not rows:
        print("[sweep] report has no rows")
        return []
    cells = lambda r: [c.strip() for c in re.findall(r"<Data[^>]*>(.*?)</Data>", r, re.S)]
    hdr = cells(rows[0])
    ins = [h for h in hdr if h.startswith("Inp")]
    out = []
    for r in rows[1:]:
        c = cells(r)
        if len(c) < len(hdr):
            continue
        d = dict(zip(hdr, c))
        try:
            d["Custom"] = float(d["Custom"])
            d["Profit"] = float(d["Profit"])
            d["Trades"] = int(d["Trades"])
        except Exception:
            continue
        out.append(d)

    print("\n" + "=" * 100)
    print("%s — %d passes · real ticks · WR is MT5's own STAT_PROFIT_TRADES/STAT_TRADES"
          % (path.name, len(out)))
    print("=" * 100)
    scored = [d for d in out if d["Custom"] > 0]
    print("  highest WR (guarded)   : %.1f%%" % (max((d["Custom"] for d in scored), default=0.0)))
    print("  passes at 90%%+ and green: %d of %d" % (sum(1 for d in scored if d["Custom"] >= 90), len(out)))
    print("  zeroed (loss or <%s trades): %d" % (D.SHIPPED["InpMinTrades"], len(out) - len(scored)))
    print()
    print("  %6s %10s %6s   %s" % ("win%", "profit", "trd", "  ".join("%12s" % i[3:] for i in ins)))
    for d in sorted(scored, key=lambda x: (-x["Custom"], -x["Profit"]))[:top]:
        print("  %6.1f %10.2f %6d   %s"
              % (d["Custom"], d["Profit"], d["Trades"],
                 "  ".join("%12s" % d[i] for i in ins)))
    print()
    print("  BY PROFIT (same passes, so the cost of each win-rate point stays visible)")
    for d in sorted(out, key=lambda x: -x["Profit"])[:8]:
        print("  %6.1f %10.2f %6d   %s"
              % (d["Custom"], d["Profit"], d["Trades"],
                 "  ".join("%12s" % d[i] for i in ins)))
    return out


if __name__ == "__main__":
    sweep = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    rpt = run(sweep)
    if rpt:
        read(rpt, top=int(sweep.get("top", 25)))
