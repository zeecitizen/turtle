"""run_s1_tester.py — autonomous MT5 Strategy Tester orchestrator for S1Trader.

Runs MT5 Strategy Tester twice (baseline vs InpRequireH1Bias=true) over a
multi-day period on Blueberry, parses the HTML report, prints a verdict.

Usage:
    py monitor/run_s1_tester.py --from 2026.05.10 --to 2026.06.04

The tester period is editable; defaults to last ~4 weeks ending today.
"""
from __future__ import annotations
import argparse, os, re, subprocess, sys, time, shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

TERMINAL_EXE = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
TERMINAL_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/81A933A9AFC5DE3C23B15CAB19C63850")
SYMBOL = "XAUUSD"
TESTER_DIR   = TERMINAL_DIR / "Tester"
FILES_DIR    = TERMINAL_DIR / "MQL5" / "Files"
LOG_DIR      = TERMINAL_DIR / "Tester" / "logs"
REPO_DIR     = Path(r"c:/Users/zeesh/Documents/GitHub/turtle")
INI_DIR      = REPO_DIR / "mt5" / "_tester_runs"
INI_DIR.mkdir(parents=True, exist_ok=True)

INI_TEMPLATE = """[Tester]
Expert=S1Trader.ex5
Symbol={symbol}
Period=M5
Login=
Model=0
ExecutionMode=0
Optimization=0
OptimizationCriterion=6
FromDate={frm}
ToDate={to}
ForwardMode=0
Deposit=10000
Currency=USD
ProfitInPips=0
Leverage=100
Replace=1
ShutdownTerminal=1
Visual=0
Report={report}

[TesterInputs]
InpRequireHHHL_M5={hhhl_m5}
InpRequireHHHL_H1={hhhl_h1}
InpRequireH1Bias={h1bias}
"""


def write_ini(name: str, frm: str, to: str, hhhl_m5: bool, hhhl_h1: bool, h1bias: bool) -> Path:
    ini = INI_DIR / f"tester_{name}.ini"
    report = f"tester_S1Trader_{name}"
    body = INI_TEMPLATE.format(
        symbol=SYMBOL,
        frm=frm, to=to, report=report,
        hhhl_m5=str(hhhl_m5).lower(),
        hhhl_h1=str(hhhl_h1).lower(),
        h1bias=str(h1bias).lower(),
    )
    ini.write_text(body, encoding="utf-8")
    return ini


def find_report(name: str) -> Path | None:
    """Find report file written by tester. MT5 writes Report=name to terminal's data dir root (or absolute path)."""
    candidates = []
    for ext in (".htm", ".html", ".xml"):
        # Tester writes to the data folder root
        for p in [TERMINAL_DIR / f"tester_S1Trader_{name}{ext}",
                  FILES_DIR / f"tester_S1Trader_{name}{ext}",
                  TESTER_DIR / f"tester_S1Trader_{name}{ext}"]:
            if p.exists():
                candidates.append(p)
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    return None


def parse_report(html_path: Path) -> dict:
    """Extract key metrics from MT5 tester HTML report."""
    try:
        text = html_path.read_text(encoding="utf-16-le", errors="replace")
    except Exception:
        text = html_path.read_text(encoding="utf-8", errors="replace")
    # Strip HTML tags for line-based parsing of key:value pairs
    plain = re.sub(r"<[^>]+>", " ", text)
    plain = re.sub(r"\s+", " ", plain)

    def grab(pat: str, default=None):
        m = re.search(pat, plain, re.I)
        return m.group(1).strip() if m else default

    metrics = {
        "total_net_profit": grab(r"Total Net Profit:?\s*([\-\d\.]+)"),
        "profit_factor":    grab(r"Profit Factor:?\s*([\-\d\.]+)"),
        "expected_payoff":  grab(r"Expected Payoff:?\s*([\-\d\.]+)"),
        "recovery_factor":  grab(r"Recovery Factor:?\s*([\-\d\.]+)"),
        "sharpe_ratio":     grab(r"Sharpe Ratio:?\s*([\-\d\.]+)"),
        "total_trades":     grab(r"Total Trades:?\s*([\d]+)"),
        "wr_long":          grab(r"Long Trades \(won %\):?\s*\d+\s*\(([\d\.]+)%\)"),
        "wr_short":         grab(r"Short Trades \(won %\):?\s*\d+\s*\(([\d\.]+)%\)"),
        "max_dd_money":     grab(r"Maximal Drawdown:?\s*([\-\d\.]+)"),
        "equity_dd_pct":    grab(r"Equity Drawdown Maximal:?\s*[\-\d\.]+\s*\(([\d\.]+)%\)"),
    }
    # Compute aggregate WR if both sides given
    return metrics


def run_tester(ini_path: Path, label: str, timeout_min: int = 30) -> dict:
    print(f"\n=== Running tester: {label} ===")
    print(f"Config: {ini_path}")
    # Clean any prior report
    for p in [TERMINAL_DIR / f"tester_S1Trader_{label}.htm",
              TERMINAL_DIR / f"tester_S1Trader_{label}.html",
              TERMINAL_DIR / f"tester_S1Trader_{label}.xml"]:
        if p.exists():
            p.unlink()

    t0 = time.time()
    cmd = [TERMINAL_EXE, f"/config:{ini_path}"]
    print(f"Cmd: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd)
    # Wait for terminal to exit (ShutdownTerminal=1 will close it when tester done)
    try:
        rc = proc.wait(timeout=timeout_min * 60)
    except subprocess.TimeoutExpired:
        proc.kill()
        print(f"!! Timed out after {timeout_min} min")
        return {"label": label, "error": "timeout"}
    elapsed = time.time() - t0
    print(f"Terminal exited rc={rc} in {elapsed:.0f}s")

    rep = find_report(label)
    if rep is None:
        print(f"!! Report file not found. Searched terminal dir + Files dir + Tester dir.")
        print(f"   Listing terminal root for .htm:")
        for p in TERMINAL_DIR.glob("tester*"):
            print(f"     {p}")
        return {"label": label, "error": "no_report"}

    print(f"Report: {rep}")
    metrics = parse_report(rep)
    metrics["label"] = label
    metrics["report_path"] = str(rep)
    metrics["elapsed_sec"] = round(elapsed, 1)
    return metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", default="2026.05.10")
    ap.add_argument("--to", dest="to", default="2026.06.04")
    ap.add_argument("--timeout-min", type=int, default=30)
    args = ap.parse_args()

    print(f"Period: {args.frm} → {args.to}")
    print(f"Terminal: {TERMINAL_EXE}")
    print(f"Data dir: {TERMINAL_DIR}")

    # Run A: baseline (all gates OFF)
    ini_a = write_ini("A_baseline", args.frm, args.to, False, False, False)
    res_a = run_tester(ini_a, "A_baseline", args.timeout_min)

    # Run B: H1Bias gate ON
    ini_b = write_ini("B_h1bias", args.frm, args.to, False, False, True)
    res_b = run_tester(ini_b, "B_h1bias", args.timeout_min)

    # Run C: HHHL_H1 gate ON
    ini_c = write_ini("C_hhhl_h1", args.frm, args.to, False, True, False)
    res_c = run_tester(ini_c, "C_hhhl_h1", args.timeout_min)
    print("\nRun C (HHHL_H1=true) metrics:")
    for k in ["total_net_profit","profit_factor","total_trades","wr_long","wr_short"]:
        print(f"  {k}: {res_c.get(k)}")

    # Verdict
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)
    fmt = "{:<22} {:>16} {:>16}"
    print(fmt.format("Metric", "A (baseline)", "B (H1Bias ON)"))
    print("-" * 60)
    for k in ["total_net_profit", "profit_factor", "expected_payoff",
              "total_trades", "wr_long", "wr_short", "max_dd_money", "equity_dd_pct"]:
        a = res_a.get(k, "—") or "—"
        b = res_b.get(k, "—") or "—"
        print(fmt.format(k, str(a), str(b)))

    try:
        a_pf = float(res_a.get("profit_factor", "0") or 0)
        b_pf = float(res_b.get("profit_factor", "0") or 0)
        a_pl = float(res_a.get("total_net_profit", "0") or 0)
        b_pl = float(res_b.get("total_net_profit", "0") or 0)
        print()
        print(f"PF delta: {b_pf - a_pf:+.2f}")
        print(f"Total $ delta: {b_pl - a_pl:+.2f}")
        if b_pf >= a_pf + 0.15 and b_pl > a_pl:
            print("\n✅ SHIP IT: H1Bias improves PF ≥0.15 AND total > baseline")
        elif b_pf > a_pf and b_pl > a_pl:
            print("\n🟡 MARGINAL: H1Bias improves both but PF gain <0.15. Hold for more days.")
        else:
            print("\n❌ DO NOT SHIP: H1Bias does not improve over baseline.")
    except (TypeError, ValueError):
        print("\n(could not compute verdict — parse failure on one or both reports)")


if __name__ == "__main__":
    main()
