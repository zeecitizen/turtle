"""target_r_sweep.py — the target-R court again, but across ALL CORES.

Zee, 2026-09-04, looking at the tester's agent panel: "i noticed that during testing
only 1 core is being used.."

He is right, and it is not a fault. MT5 runs a SINGLE BACKTEST on one agent — one pass
through the tick stream, inherently sequential, so seven cores sit "ready". The local
agent farm only fills up during an OPTIMISATION, where MT5 hands each agent a different
parameter combination and runs them concurrently.

target_r_court.py ran six arms one after another at one core each. This runs the same
question as one optimisation: MT5 builds the grid itself and spreads it over all eight
agents. Same tester, same real ticks, same EA — roughly 8x the throughput.

DO NOT USE MQL5 CLOUD NETWORK for this. The cloud sends the compiled EA to strangers'
machines to execute. Our strategy is the asset; local agents only.

    py monitor/strategy_lab/target_r_sweep.py --window oos_aug17
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from mt5_headless import RIG, REPORTS, TEST_EXE, live_is_safe, sync_experts  # noqa: E402
from target_r_court import EA, WINDOWS, compile_into_rig  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent.parent

# MT5 sweep syntax: Name=current||start||step||stop||Y  (Y = include in optimisation)
# InpTargetR 0 keeps the stock flat InpTargetPts target — the control arm is IN the grid.
GRID = {
    "InpTargetR":    "0||0||1||3||Y",       # 0 (flat) · 1R · 2R · 3R
    "InpMaxHoldMin": "20||20||20||120||Y",  # 20 · 40 · 60 · 80 · 100 · 120 minutes
}


def write_opt_ini(path, symbol, frm, to, model, deposit, delay, report):
    lines = ["[Tester]"]
    for k, v in [("Expert", EA), ("Symbol", symbol), ("Period", "M1"),
                 ("Model", model), ("FromDate", frm), ("ToDate", to),
                 ("Deposit", deposit), ("Currency", "USD"), ("Leverage", "1:500"),
                 ("ExecutionMode", delay),
                 # 1 = SLOW COMPLETE. 2 is genetic and stops early, which would hide
                 # exactly the corner of the grid we are trying to price.
                 ("Optimization", 1),
                 ("OptimizationCriterion", 0),   # 0 = maximise balance; we read every pass anyway
                 ("Report", report), ("ReplaceReport", 1),
                 ("ShutdownTerminal", 1), ("Visual", 0)]:
        lines.append(f"{k}={v}")
    lines.append("")
    lines.append("[TesterInputs]")
    for k, v in GRID.items():
        lines.append(f"{k}={v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-16")


def parse_opt(p: Path):
    """An optimisation report is a TABLE of passes, not the single-run summary that
    target_r_court.parse_report reads. One row per parameter combination.

    FORMAT NOTE: MT5 writes the OPTIMISATION report as Excel SpreadsheetML (.xml) —
    <Row><Cell><Data>… — NOT as the <table><tr><td> HTML a single backtest produces.
    Parsing it with the HTML shape silently finds zero rows, which looks exactly like
    a failed run. Columns: Pass, Result, Profit, Expected Payoff, Profit Factor,
    Recovery Factor, Sharpe Ratio, Custom, Equity DD %, Trades, then one per swept
    input."""
    text = ""
    for enc in ("utf-8", "utf-16", "utf-16-le"):
        try:
            text = p.read_text(encoding=enc, errors="replace")
            if "<Workbook" in text or "<Row" in text or "<tr" in text.lower():
                break
        except Exception:
            continue

    out, header = [], None
    for r in re.findall(r"<Row[^>]*>(.*?)</Row>", text, re.S | re.I):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<Cell[^>]*>(.*?)</Cell>", r, re.S | re.I)]
        if not cells:
            continue
        if header is None:
            if any(c.lower() == "profit" for c in cells):
                header = cells
            continue
        if len(cells) == len(header):
            out.append(dict(zip(header, cells)))
    if out:
        return header, out

    # fall back to the HTML shape, in case MT5 ever writes .htm for an optimisation
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I):
        cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S | re.I)]
        if not cells:
            continue
        if header is None and any(c.lower() == "profit" for c in cells):
            header = cells
            continue
        if header and len(cells) == len(header):
            out.append(dict(zip(header, cells)))
    return header, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="oos_aug17", choices=list(WINDOWS))
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--deposit", type=int, default=50000)
    ap.add_argument("--delay", type=int, default=163)
    ap.add_argument("--model", type=int, default=4)
    args = ap.parse_args()

    frm, to = WINDOWS[args.window]
    live_is_safe()
    if not compile_into_rig():
        sys.exit(1)
    sync_experts()
    REPORTS.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%H%M%S")
    name = f"SWEEP_{args.window}_{stamp}"
    ini = ROOT / "mt5" / "_target_r_sweep.ini"
    write_opt_ini(ini, args.symbol, frm, to, args.model, args.deposit,
                  args.delay, name)

    n = 4 * 6
    print(f"[sweep] {args.window}: {frm} -> {to}, {n} combinations across the local "
          f"agent farm (all cores), real ticks", flush=True)
    t0 = time.time()
    try:
        subprocess.run([str(TEST_EXE), "/portable", f"/config:{ini}"],
                       timeout=10800, capture_output=True)
    except subprocess.TimeoutExpired:
        print("[sweep] TIMED OUT — killing the rig")
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Get-Process terminal64 | Where-Object {{ $_.Path -eq "
                        f"'{TEST_EXE}' }} | Stop-Process -Force"], capture_output=True)
    print(f"[sweep] done in {time.time()-t0:.0f}s", flush=True)

    rpt = None
    for ext in (".htm", ".html", ".xml"):
        s = RIG / (name + ext)
        if s.exists():
            rpt = REPORTS / (name + ext)
            shutil.copy(s, rpt)
            break
    if not rpt:
        print("[sweep] NO REPORT — check the rig's logs")
        sys.exit(1)
    print(f"[sweep] report -> {rpt}")

    header, rows = parse_opt(rpt)
    if not rows:
        print("[sweep] report parsed but no pass rows found; open it by hand")
        return

    def col(d, *names):
        for n_ in names:
            for k in d:
                if k.lower().replace(" ", "") == n_.lower().replace(" ", ""):
                    return d[k]
        return "?"

    print(f"\n=== TARGET-R SWEEP — {args.window} ({frm} -> {to}), REAL TICKS ===")
    print(f"{'TargetR':>8}{'hold':>6}{'trades':>8}{'net $':>11}{'PF':>7}{'DD%':>8}")
    print("-" * 48)
    def keyf(d):
        try:
            return (float(col(d, "InpTargetR")), float(col(d, "InpMaxHoldMin")))
        except Exception:
            return (0.0, 0.0)
    for d in sorted(rows, key=keyf):
        print(f"{col(d,'InpTargetR'):>8}{col(d,'InpMaxHoldMin'):>6}"
              f"{col(d,'Trades'):>8}{col(d,'Profit'):>11}"
              f"{col(d,'ProfitFactor','Profit Factor'):>7}"
              f"{col(d,'EquityDD%','Equity DD %'):>8}")
    print("\nNOT PROMOTED. One window is a hypothesis; agreement across "
          "this_week + oos_aug17 + oos_aug05 is the bar.")


if __name__ == "__main__":
    main()
