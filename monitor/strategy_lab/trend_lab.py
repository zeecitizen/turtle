"""trend_lab.py — sweep trend-engine implementations across several windows at once.

Zee, 2026-09-08: "our diamond EA is only lacking one thing. a proper trend checking
system ... Reliably loop through implementations and find the one which works on
accurately predicting the trend exhaustion avoiding that one last trade that fails.
AND ensuring that we're not missing out on setups during the strong trending move"

TWO FAILURE MODES, ONE SCORE. A gate that blocks everything avoids the bad trade and
fails his second requirement; a gate that blocks nothing keeps every setup and fails
the first. So every arm is scored on BOTH: net money AND the trade count it kept, on
every window — and an arm is only a candidate if it holds its sign across ALL windows.

Runs one MT5 optimisation per window over the whole grid, so all 8 local agents work.
Never touches the live terminal: compiles the working-tree EA into C:/mt5_rig only, and
does it AFTER sync_experts(), which copies the LIVE .ex5 in and would otherwise
overwrite the build under test.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from mt5_headless import RIG, REPORTS, TEST_EXE, live_is_safe, sync_experts  # noqa: E402
from target_r_sweep import parse_opt  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent.parent
EA = "ZeeUHV_Diamond"
ME = Path(r"C:/Program Files/Blueberry Markets MetaTrader 5/metaeditor64.exe")
LIVE_COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")

WINDOWS = {
    "aug05": ("2026.08.05", "2026.08.08"),
    "aug17": ("2026.08.17", "2026.08.22"),
    "aug24": ("2026.08.24", "2026.08.29"),
    "aug31": ("2026.08.31", "2026.09.05"),
    "sep07": ("2026.09.07", "2026.09.08"),
}


LIVEUPDATE = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal"
                  r"/C98725B0876AA950E33E16CBB01E4F0E/liveupdate")


def block_autoupdate():
    """MT5 DESTROYS OVERNIGHT COURTS BY UPDATING ITSELF.

    Twice now the rig downloaded build 6182 mid-sweep; every launch afterwards tried to
    install it, hit a sharing violation on its own running exe, and exited in ~1s having
    tested nothing. On 2026-09-08 that killed 3 of 4 windows AFTER the first had already
    succeeded, so the failure arrived looking like "three windows found no result".

    Deleting the staged payload is not enough — it re-downloads. Putting a FILE where the
    staging DIRECTORY must go means MT5 cannot create it at all. Cheap, reversible
    (delete the file), and it only touches the rig's own data folder, never Blueberry's.
    """
    try:
        if LIVEUPDATE.is_dir():
            shutil.rmtree(LIVEUPDATE, ignore_errors=True)
        if not LIVEUPDATE.exists():
            LIVEUPDATE.write_text(
                "blocked by trend_lab: MT5 auto-update destroyed overnight "
                "courts on 2026-09-07 and 2026-09-08", encoding="utf-8")
    except Exception as e:
        print("[lab] could not block auto-update: " + str(e))


def kill_stubs():
    """Stop any stranded LiveUpdate helper. Matched BY PATH — the Blueberry terminal
    that trades his money must never be in this list."""
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process terminal64 -ErrorAction SilentlyContinue | "
                    "Where-Object { $_.Path -like '*liveupdate*' } | Stop-Process -Force"],
                   capture_output=True)


def stage():
    d = RIG / "Common" / "Files"
    d.mkdir(parents=True, exist_ok=True)
    for n in ("oanda_vol.csv", "oanda_bars.csv"):
        if (LIVE_COMMON / n).exists():
            shutil.copy(LIVE_COMMON / n, d / n)


def build():
    """Compile the working tree into the rig. MUST run after sync_experts()."""
    src = ROOT / "mt5" / (EA + ".mq5")
    dst = RIG / "MQL5" / "Experts" / src.name
    shutil.copy(src, dst)
    log = RIG / "trendlab_compile.log"
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
        print("[lab] COMPILE FAILED")
        for e in errs[:10]:
            print("   ", e.strip())
        return False
    return True


def run_window(win, grid, deposit=50000, delay=163, model=4, tag="g",
               period="M1"):
    frm, to = WINDOWS[win]
    stamp = datetime.now().strftime("%H%M%S")
    name = "TL_" + tag + "_" + win + "_" + stamp
    ini = ROOT / "mt5" / "_trend_lab.ini"
    lines = ["[Tester]"]
    for k, v in [("Expert", EA), ("Symbol", "XAUUSD"), ("Period", period),
                 ("Model", model), ("FromDate", frm), ("ToDate", to),
                 ("Deposit", deposit), ("Currency", "USD"), ("Leverage", "1:500"),
                 ("ExecutionMode", delay), ("Optimization", 1),
                 ("OptimizationCriterion", 0), ("Report", name),
                 ("ReplaceReport", 1), ("ShutdownTerminal", 1), ("Visual", 0)]:
        lines.append(str(k) + "=" + str(v))
    lines += ["", "[TesterInputs]"] + grid
    ini.write_text("\n".join(lines) + "\n", encoding="utf-16")

    t0 = time.time()
    block_autoupdate()
    kill_stubs()
    try:
        subprocess.run([str(TEST_EXE), "/portable", "/config:" + str(ini)],
                       timeout=14400, capture_output=True)
    except subprocess.TimeoutExpired:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-Process terminal64 | Where-Object { $_.Path -eq '"
                        + str(TEST_EXE) + "' } | Stop-Process -Force"],
                       capture_output=True)
    rpt = None
    for ext in (".xml", ".htm"):
        srcp = RIG / (name + ext)
        if srcp.exists():
            rpt = REPORTS / (name + ext)
            shutil.copy(srcp, rpt)
            break
    if not rpt:
        print("[lab] " + win + ": NO REPORT")
        return None, time.time() - t0
    hdr, rows = parse_opt(rpt)
    return (hdr, rows), time.time() - t0


def num(x, default=0.0):
    """MT5 leaves Profit Factor EMPTY for a pass that took no trades. A strict float()
    raised there, the row was discarded by the caller's except, the arm then failed the
    "completed every window" test \u2014 and a sweep that had tested all four windows
    correctly for 50 minutes reported "no arm completed every window". An empty cell is
    a zero, not a parse failure."""
    t = str(x).replace(" ", "").replace("\u00a0", "").strip()
    if not t:
        return default
    try:
        return float(t)
    except ValueError:
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True, help="JSON list of TesterInputs lines")
    ap.add_argument("--dials", required=True, help="comma-separated input names")
    ap.add_argument("--windows", default="aug17,aug31,sep07")
    ap.add_argument("--tag", default="g")
    ap.add_argument("--period", default="M1",
                    help="chart timeframe the EA runs on (M1/M5/M15)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    grid = json.loads(args.grid)
    dials = [d.strip() for d in args.dials.split(",")]
    wins = [w.strip() for w in args.windows.split(",")]

    live_is_safe()
    stage()
    sync_experts()
    if not build():
        sys.exit(1)
    print("[lab] period=" + args.period + "  grid=" + str(grid))
    print("[lab] windows=" + str(wins) + "  dials=" + str(dials) + "\n", flush=True)

    block_autoupdate()
    per = {}
    for w in wins:
        res, secs = run_window(w, grid, tag=args.tag, period=args.period)
        if not res:
            # one retry: a window that returns nothing is nearly always the terminal
            # having been hijacked by its own updater, which the block above prevents
            print("[lab] " + w + ": retrying once")
            block_autoupdate(); kill_stubs()
            res, secs = run_window(w, grid, tag=args.tag + "r", period=args.period)
        if not res:
            continue
        hdr, rows = res
        missing = [d for d in dials
                   if not any(d.lower() == h.lower() for h in (hdr or []))]
        if missing:
            # A report without the swept column is a run that tested NOTHING — the
            # "no optimized parameter selected" failure, which exits 0 and writes a
            # header-only file. Never let that read as a finding.
            print("[lab] " + w + ": report lacks " + str(missing)
                  + " — the run tested nothing")
            sys.exit(1)
        print("[lab] " + w + ": " + str(len(rows)) + " passes in "
              + str(int(secs)) + "s", flush=True)
        for r in rows:
            k = tuple(str(r.get(d, "?")).strip() for d in dials)
            per.setdefault(k, {})[w] = (num(r.get("Profit", 0)),
                                        int(num(r.get("Trades", 0))),
                                        num(r.get("Profit Factor", 0)),
                                        num(r.get("Equity DD %", 0)))

    done = {k: v for k, v in per.items() if len(v) == len(wins)}
    if not done:
        print("[lab] no arm completed every window")
        sys.exit(1)

    def total(v):
        return sum(x[0] for x in v.values())

    def trades(v):
        return sum(x[1] for x in v.values())

    ranked = sorted(done.items(), key=lambda kv: -total(kv[1]))
    head = "  ".join(("{:<9}".format(d.replace("Inp", ""))) for d in dials)
    print("\n=== TREND LAB — " + ", ".join(wins) + " · REAL TICKS ===")
    print(head + "".join("{:>11}{:>6}".format(w + " net", "tk") for w in wins)
          + "{:>11}{:>7}{:>6}".format("TOTAL", "trades", "win"))
    print("-" * (len(head) + 17 * len(wins) + 24))
    for k, v in ranked:
        cells = "".join("{:>11.2f}{:>6}".format(v[w][0], v[w][1]) for w in wins)
        pos = sum(1 for w in wins if v[w][0] > 0)
        star = "  <<<" if pos == len(wins) else ""
        print("  ".join("{:<9}".format(x) for x in k) + cells
              + "{:>11.2f}{:>7}{:>4}/{}".format(total(v), trades(v), pos, len(wins))
              + star)
    print("\n<<< = positive on EVERY window. Anything else is a single-window "
          "artefact until proven otherwise. Trade count is shown beside every net so "
          "an arm that 'wins' by refusing to trade is visible immediately.")
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"|".join(k): {w: list(x) for w, x in v.items()} for k, v in done.items()},
            indent=1), encoding="utf-8")
        print("[lab] json -> " + args.out)


if __name__ == "__main__":
    main()
