"""volume_source_court.py — broker volume vs HIS OANDA volume, on the real Diamond.

Zee, 2026-09-06: "we donot wish to use broker volume, we want to completely transition
to OANDA volume taken from tradingview. any broker volume trades waste our time"

The decision is his and is already shipped (ZeeUHV_Diamond v1.15 defaults
InpOandaVolume=1, InpOandaStrict=true). This court exists to put a number beside it,
not to gate it — and to catch the one thing a directive cannot: whether STRICT mode
starves the machine of trades on windows where his table has holes.

Sweeps InpOandaVolume 0/1 on the SAME EA, same window, real ticks. What changes is
only which feed ranks the UHVs; levels, stops and fills stay Blueberry's either way.

Needs Common\\Files\\oanda_vol.csv inside the rig (the portable install resolves
FILE_COMMON to C:/mt5_rig/Common/Files, not the live terminal's). Coverage as of
2026-09-06 is 22,748 minutes, 05 Aug -> 04 Sep — enough for all three court windows.

    py monitor/strategy_lab/volume_source_court.py --window oos_aug17
"""
import argparse
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from mt5_headless import RIG, REPORTS, TEST_EXE, live_is_safe, sync_experts  # noqa: E402
from target_r_court import WINDOWS  # noqa: E402
from target_r_sweep import parse_opt  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent.parent
EA = "ZeeUHV_Diamond"
LIVE_COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")


def stage_tables():
    """The rig reads its OWN Common\\Files. Without this the EA finds no table, and
    under strict mode that is indistinguishable from 'his chart refused everything'."""
    dst = RIG / "Common" / "Files"
    dst.mkdir(parents=True, exist_ok=True)
    for n in ("oanda_vol.csv", "oanda_bars.csv"):
        src = LIVE_COMMON / n
        if src.exists():
            shutil.copy(src, dst / n)
            print(f"[vol] staged {n} ({src.stat().st_size/1e6:.1f} MB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="this_week", choices=list(WINDOWS))
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--deposit", type=int, default=50000)
    ap.add_argument("--delay", type=int, default=163)
    ap.add_argument("--model", type=int, default=4)
    args = ap.parse_args()

    frm, to = WINDOWS[args.window]
    live_is_safe()
    stage_tables()
    sync_experts()
    REPORTS.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%H%M%S")
    name = f"VOL_{args.window}_{stamp}"
    ini = ROOT / "mt5" / "_vol_source.ini"
    lines = ["[Tester]"]
    for k, v in [("Expert", EA), ("Symbol", args.symbol), ("Period", "M1"),
                 ("Model", args.model), ("FromDate", frm), ("ToDate", to),
                 ("Deposit", args.deposit), ("Currency", "USD"), ("Leverage", "1:500"),
                 ("ExecutionMode", args.delay), ("Optimization", 1),
                 ("OptimizationCriterion", 0), ("Report", name), ("ReplaceReport", 1),
                 ("ShutdownTerminal", 1), ("Visual", 0)]:
        lines.append(f"{k}={v}")
    lines += ["", "[TesterInputs]",
              "InpOandaVolume=0||0||1||1||Y",   # 0 = broker, 1 = his chart
              "InpOandaStrict=true||false||0||true||Y"]
    ini.write_text("\n".join(lines) + "\n", encoding="utf-16")

    print(f"[vol] {args.window}: {frm} -> {to}, broker vs OANDA, real ticks", flush=True)
    t0 = time.time()
    try:
        subprocess.run([str(TEST_EXE), "/portable", f"/config:{ini}"],
                       timeout=10800, capture_output=True)
    except subprocess.TimeoutExpired:
        print("[vol] TIMED OUT")
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Get-Process terminal64 | Where-Object {{ $_.Path -eq "
                        f"'{TEST_EXE}' }} | Stop-Process -Force"], capture_output=True)
    print(f"[vol] done in {time.time()-t0:.0f}s", flush=True)

    rpt = None
    for ext in (".xml", ".htm", ".html"):
        s = RIG / (name + ext)
        if s.exists():
            rpt = REPORTS / (name + ext)
            shutil.copy(s, rpt)
            break
    if not rpt:
        print("[vol] NO REPORT — check the rig's logs")
        sys.exit(1)
    print(f"[vol] report -> {rpt}")

    header, rows = parse_opt(rpt)
    if not rows:
        print("[vol] no pass rows parsed; open the report by hand")
        return

    def f(d, k):
        for kk in d:
            if kk.lower().replace(" ", "") == k.lower().replace(" ", ""):
                return d[kk]
        return "?"

    print(f"\n=== VOLUME SOURCE — {args.window} ({frm} -> {to}), REAL TICKS ===")
    print(f"{'feed':<10}{'strict':<9}{'trades':>8}{'net $':>12}{'PF':>8}{'DD%':>8}")
    print("-" * 54)
    for d in sorted(rows, key=lambda r: str(f(r, "InpOandaVolume"))):
        feed = "OANDA" if str(f(d, "InpOandaVolume")).startswith("1") else "broker"
        try:
            net = f"{float(f(d,'Profit')):.2f}"
            dd = f"{float(f(d,'Equity DD %')):.2f}"
        except Exception:
            net, dd = f(d, "Profit"), f(d, "Equity DD %")
        print(f"{feed:<10}{str(f(d,'InpOandaStrict')):<9}{f(d,'Trades'):>8}"
              f"{net:>12}{f(d,'Profit Factor'):>8}{dd:>8}")
    print("\nTrade COUNT is the number to watch as closely as the money: strict mode "
          "refuses any window his table cannot cover, so a collapse in count means the "
          "bridge's coverage is the binding constraint, not the laws.")


if __name__ == "__main__":
    main()
