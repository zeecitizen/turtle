"""target_r_court.py — does a 1:2 R:R target beat the Diamond's flat 1.00 target?

Zee, 2026-09-04: "check for every basket we took in past few days + today, what
would've happened if we set TP to 1:2 R:R .. instead of the current tight TP"

WHY THIS IS NOT A PYTHON REPLAY. Answering that question by walking our own fills and
asking "would the 2R level have been touched before the stop" is computing which of
stop-or-target came first, which IS simulating trades — the exact move CLAUDE.md
records as the failure that turned a real -$657 into a reported +$876. So the question
goes to MT5's Strategy Tester on REAL TICKS (model 4), which is the only thing allowed
to answer it.

THE CONFOUND THIS RUN EXISTS TO CONTROL. InpMaxHoldMin = 20 closes the basket at market
after twenty minutes. The stock target is 1.00 in price and is often hit in a few
minutes; a 2R target on v1.14's structural stop is ~4 away and usually cannot be
reached inside twenty. Testing 2R at hold 20 would therefore measure the hold cap, not
the target. Every R arm is run at 20 / 60 / 120 minutes so the two are separable.

SAFETY. ZeeUHV_Diamond (magic 88154) is ATTACHED AND LIVE with an open basket.
Recompiling it would hot-reload the live EA, so this court runs ZeeUHV_DiamondTR
(magic 88164), compiled straight into the portable rig at C:/mt5_rig. The live
terminal's folder is never written to.

    py monitor/strategy_lab/target_r_court.py --window this_week
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

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent.parent
EA = "ZeeUHV_DiamondTR"
SRC = ROOT / "mt5" / f"{EA}.mq5"
METAEDITOR = Path(r"C:/Program Files/Blueberry Markets MetaTrader 5/metaeditor64.exe")

# label, InpTargetR, InpMaxHoldMin
ARMS = [
    ("BASELINE flat 1.00 / hold 20", 0.0, 20),
    ("1R / hold 20",                 1.0, 20),
    ("2R / hold 20",                 2.0, 20),
    ("2R / hold 60",                 2.0, 60),
    ("2R / hold 120",                2.0, 120),
    ("3R / hold 120",                3.0, 120),
]

WINDOWS = {
    # what he actually asked for: the baskets of the past few days, and today
    "this_week": ("2026.08.31", "2026.09.05"),
    # the two out-of-sample windows VERSION_HISTORY uses to kill candidates
    "oos_aug17": ("2026.08.17", "2026.08.22"),
    "oos_aug05": ("2026.08.05", "2026.08.08"),
}


def compile_into_rig():
    """Compile the test arm into the PORTABLE RIG ONLY. The live terminal, which has
    the Diamond attached over an open basket, is never written to."""
    dst_dir = RIG / "MQL5" / "Experts"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / SRC.name
    shutil.copy(SRC, dst)
    log = RIG / "compile_tr.log"
    subprocess.run([str(METAEDITOR), f"/compile:{dst}", f"/log:{log}"],
                   capture_output=True, timeout=180)   # exit code = files compiled
    ex5 = dst.with_suffix(".ex5")
    text = ""
    for enc in ("utf-16", "utf-8"):
        try:
            text = log.read_text(encoding=enc, errors="replace")
            break
        except Exception:
            continue
    errors = [l for l in text.splitlines() if " error " in l.lower()]
    if errors or not ex5.exists():
        print(f"[court] COMPILE FAILED for {EA}")
        for l in errors[:15]:
            print("   ", l.strip())
        return False
    print(f"[court] compiled {EA}.ex5 into the rig ({ex5.stat().st_size} bytes)")
    return True


def write_run_ini(path, ea, symbol, period, frm, to, model, deposit, delay,
                  report, inputs):
    """MT5 takes EA inputs in a [TesterInputs] section. mt5_headless.write_ini only
    emits one section, so this writes both."""
    lines = ["[Tester]"]
    for k, v in [("Expert", ea), ("Symbol", symbol), ("Period", period),
                 ("Model", model), ("FromDate", frm), ("ToDate", to),
                 ("Deposit", deposit), ("Currency", "USD"), ("Leverage", "1:500"),
                 ("ExecutionMode", delay), ("Optimization", 0),
                 ("Report", report), ("ReplaceReport", 1),
                 ("ShutdownTerminal", 1), ("Visual", 0)]:
        lines.append(f"{k}={v}")
    lines.append("")
    lines.append("[TesterInputs]")
    for k, v in inputs.items():
        lines.append(f"{k}={v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-16")


def parse_report(p: Path) -> dict:
    try:
        text = p.read_text(encoding="utf-16-le", errors="replace")
    except Exception:
        text = p.read_text(encoding="utf-8", errors="replace")
    plain = re.sub(r"<[^>]+>", " ", text)
    plain = re.sub(r"\s+", " ", plain)

    def grab(pat, default=None):
        m = re.search(pat, plain, re.I)
        return m.group(1).strip() if m else default

    # MT5 GROUPS THOUSANDS WITH A SPACE: "Total Net Profit: -1 577.10". A naive
    # ([\-\d\.]+) stops at that space and returns "-1", which reads as a one-dollar
    # loss instead of a fifteen-hundred-dollar one. Every arm that lost four figures
    # in the 2026-09-04 target-R court came back as "net -1" until this was fixed.
    NUM = r"(-?[\d  ]*\d(?:\.\d+)?)"

    def num(pat, default=None):
        v = grab(pat, None)
        if v is None:
            return default
        v = v.replace(" ", "").replace(" ", "")
        return v or default

    d = {
        "net":     num(rf"Total Net Profit:?\s*{NUM}"),
        "pf":      num(r"Profit Factor:?\s*(-?[\d\.]+)"),
        "trades":  num(r"Total Trades:?\s*(\d+)"),
        # two capture groups here (money, percent) — we want the percent, group 2
        "dd_pct":  (lambda m: m.group(2) if m else None)(
                       re.search(rf"Equity Drawdown Maximal:?\s*{NUM}\s*\(([\d\.]+)%\)",
                                 plain, re.I)),
        "won_pct": grab(r"Profit Trades \(% of total\):?\s*\d+\s*\(([\d\.]+)%\)"),
        "bars":    num(rf"Bars:?\s*{NUM}"),
        "ticks":   num(rf"Ticks:?\s*{NUM}"),
        # The report states its own modelling quality — trust this over ticks/bar.
        "quality": grab(r"History Quality:?\s*([\d]+% real ticks)"),
    }
    # TICK-QUALITY GUARD, testing/test_tips.md Part 1: ratio < 50 means the run
    # silently fell back to OHLC modelling and CANNOT judge a small target.
    try:
        d["tpb"] = int(d["ticks"]) / max(1, int(d["bars"]))
    except Exception:
        d["tpb"] = None
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="this_week", choices=list(WINDOWS))
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--deposit", type=int, default=50000)   # never let the window censor
    ap.add_argument("--delay", type=int, default=163)       # live median, shano_open_log
    ap.add_argument("--model", type=int, default=4)         # REAL TICKS
    args = ap.parse_args()

    frm, to = WINDOWS[args.window]
    live_is_safe()
    if not compile_into_rig():
        sys.exit(1)
    sync_experts()
    REPORTS.mkdir(parents=True, exist_ok=True)

    print(f"\n[court] window {args.window}: {frm} -> {to} on {args.symbol}, "
          f"model {args.model}, delay {args.delay}ms, {len(ARMS)} arms\n")

    results = []
    for label, tr, hold in ARMS:
        stamp = datetime.now().strftime("%H%M%S")
        name = f"TR_{args.window}_{str(tr).replace('.','p')}_{hold}_{stamp}"
        ini = ROOT / "mt5" / "_target_r_run.ini"
        write_run_ini(ini, EA, args.symbol, "M1", frm, to, args.model,
                      args.deposit, args.delay, name,
                      {"InpTargetR": tr, "InpMaxHoldMin": hold})
        t0 = time.time()
        print(f"[court] {label} …", flush=True)
        try:
            subprocess.run([str(TEST_EXE), "/portable", f"/config:{ini}"],
                           timeout=5400, capture_output=True)
        except subprocess.TimeoutExpired:
            print(f"[court] {label} TIMED OUT")
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"Get-Process terminal64 | Where-Object {{ $_.Path -eq "
                            f"'{TEST_EXE}' }} | Stop-Process -Force"],
                           capture_output=True)
        rpt = None
        for ext in (".htm", ".html"):
            s = RIG / (name + ext)
            if s.exists():
                rpt = REPORTS / (name + ext)
                shutil.copy(s, rpt)
                break
        if not rpt:
            print(f"[court] {label}: NO REPORT — check the rig's logs")
            results.append((label, tr, hold, None))
            continue
        m = parse_report(rpt)
        m["secs"] = time.time() - t0
        results.append((label, tr, hold, m))
        print(f"[court]   net {m['net']}  PF {m['pf']}  trades {m['trades']}  "
              f"won {m['won_pct']}%  DD {m['dd_pct']}%  ticks/bar "
              f"{m['tpb'] and round(m['tpb'])}  ({m['secs']:.0f}s)", flush=True)

    print(f"\n=== TARGET-R COURT — {args.window} ({frm} -> {to}), REAL TICKS ===")
    hdr = f"{'arm':<30}{'trades':>7}{'won%':>7}{'net $':>11}{'PF':>7}{'DD%':>7}{'t/bar':>7}"
    print(hdr)
    print("-" * len(hdr))
    for label, tr, hold, m in results:
        if not m:
            print(f"{label:<30}{'NO REPORT':>39}")
            continue
        flag = "" if (m["tpb"] or 0) > 50 else "  <-- NOT REAL TICKS, VOID"
        print(f"{label:<30}{m['trades'] or '?':>7}{m['won_pct'] or '?':>7}"
              f"{m['net'] or '?':>11}{m['pf'] or '?':>7}{m['dd_pct'] or '?':>7}"
              f"{m['tpb'] and round(m['tpb']) or '?':>7}{flag}")
    print("\nNOT PROMOTED by this run alone — one window is a hypothesis. "
          "Out-of-sample: --window oos_aug17 and --window oos_aug05.")


if __name__ == "__main__":
    main()
