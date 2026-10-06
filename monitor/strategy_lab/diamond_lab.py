"""diamond_lab.py — batch ZeeUHV_Diamond configs through MT5 and report them walk-forward.

Zee, 2026-09-17: the Diamond "sometimes cannot predict the turning of the trend and fires
when the breakout results in a failure", and asked whether the VSISA work could help.

It can, and the answer was already in the EA: `InpTrendMode` has a CamelTrend setting
(mode 1) that has never been shipped — the default is mode 0, the stale-pivot reader the
source itself calls "structurally blind at the very moment a leg pushes into new ground"
and which "keeps saying 'uptrend' through the confirmation lag at the top". That last
phrase IS his complaint. VSISA found the same thing independently: the camel reading beat
the slope reading at every timeframe and was the only change to improve win rate, drawdown,
streak and risk-adjusted return in both walk-forward halves.

But the 61.1% figure quoted in the source comes from BasedOnLaws, a different EA, ported
across. It has never been measured in the Diamond. This measures it.

TWO THINGS THIS FILE EXISTS TO AVOID:

  1. THE .set CACHE TRAP. monitor/mt5_headless.py writes only [Tester], so MT5 silently
     reuses whatever inputs were last used for this EA. That has already cost this project
     a night once. Every run here pins EVERY input explicitly.
  2. THE OANDA WINDOW. InpOandaStrict makes a minute without OANDA volume unreadable, so a
     backtest outside the table's coverage refuses everything and returns a clean, empty,
     meaningless zero. The table currently runs 2026.08.05 15:11 -> now, so FULL/H1/H2
     below sit inside it deliberately.
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent.parent
RIG = Path(r"C:/mt5_rig")
EXE = RIG / "terminal64.exe"
REPORTS = ROOT / "mt5" / "_tester_runs" / "diamond"
LIVE = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal"
            r"/DBE9B8B347D025DD139E103EE3B63FD8")
EA = "ZeeUHV_Diamond"
SYMBOL = "XAUUSD"

# inside the OANDA table's coverage, with a week of run-up before H1 starts
FULL = ("2026.08.06", "2026.09.17")
H1 = ("2026.08.06", "2026.08.27")
H2 = ("2026.08.27", "2026.09.17")

# v1.17 as it runs on Blueberry right now. Every input pinned.
SHIPPED = {
    "InpLots": "0.10", "InpMagicNumber": "88154", "InpOandaVolume": "1",
    "InpOandaStrict": "true", "InpVolFreshSec": "90",
    "InpTrendLook": "20", "InpPivot": "2", "InpRequireTrend": "true",
    "InpRetraceBack": "20", "InpUhvBodyMin": "0.5", "InpBreakWindow": "12",
    "InpStopPts": "20.0", "InpTargetPts": "1.0", "InpMaxHoldMin": "20",
    "InpMaxOpen": "1", "InpCooldownBar": "3", "InpMaxGapSec": "300",
    "InpVerbose": "false", "InpMinTrades": "15",
    "InpUseDiamonds": "true", "InpMaxRisk": "0.0", "InpStackLots": "true",
    "InpStackStep": "0.0", "InpStackMult": "2", "InpOneOrder": "false",
    "InpSpaceSec": "0.0", "InpReqLaws": "4", "InpFailCandles": "0",
    "InpStructStop": "0.50", "InpDiaLoudMult": "1.30", "InpSlMode": "0",
    "InpTargetR": "0.0", "InpBreakEvenR": "0.0", "InpBeBufferPts": "0.0",
    "InpMaxHumps": "2", "InpNyOnly": "false", "InpNyFromHour": "15",
    "InpNyToHour": "24", "InpTrendTF": "0", "InpTrendMode": "0",
    "InpHighTest": "1", "InpEmaSlopeBars": "10", "InpLastLowMode": "0",
    "InpStopOnLastLow": "false",
    # v1.20 - THE JURY (Zee 2026-09-29). Pinned OFF here so every run that does not
    # explicitly ask for it is measuring the machine without it.
    "InpJuryMode": "0", "InpJuryBars": "2", "InpJuryVotes": "2",
    "InpJuryRsiN": "14", "InpJuryMomN": "14", "InpJuryAdxN": "14",
    "InpJuryStochK": "5", "InpJuryStochD": "3", "InpJuryStochS": "3",
    # v1.21 - THE BAIL ("it has to succeed immediately"). Pinned OFF.
    "InpBailSec": "0", "InpBailAt": "0.0",
    # v1.22 - THE DETECTION FIXES. Pinned OFF: the baseline must stay the
    # baseline, and each fix is credited only when asked for explicitly.
    "InpRetraceFix": "false", "InpOandaColour": "false",
    "InpBreakBodyMin": "0.0",   # v1.23 - his clause (a). 0.70 is his number.
    "InpOandaPrice": "false",   # v1.24 - camel humps on HIS highs/lows.
}


def kill_rig() -> None:
    """Kill ONLY the rig's terminal — matched BY PATH, never the one Zee trades on."""
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq terminal64.exe", "/FO", "CSV"],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return
    for line in out.splitlines()[1:]:
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) < 2:
            continue
        pid = parts[1]
        try:
            path = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").ExecutablePath"],
                capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:
            continue
        if path and "mt5_rig" in path.replace("\\", "/"):
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)


def sync_ea() -> None:
    src = LIVE / "MQL5" / "Experts" / (EA + ".ex5")
    if src.exists():
        dst = RIG / "MQL5" / "Experts" / (EA + ".ex5")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())


def run(over: dict, frm: str, to: str, model: int = 4,
        deposit: int = 4123) -> str | None:
    # DEPOSIT IS AN ARGUMENT, not a constant (2026-09-29). A run that blows the account
    # stops early and reports a net CENSORED AT THE BALANCE, which looks like a result.
    # A wide structural stop makes that reachable: at InpStructStop 20 one 8-ticket basket
    # can lose ~$1,600, which is 39% of the old hardcoded $4,123. When the question is a
    # RATE rather than a P&L, fund the test well enough to finish the window.
    cfg = dict(SHIPPED)
    cfg.update({k: str(v) for k, v in over.items()})
    name = "DIA_%s" % datetime.now().strftime("%H%M%S%f")[:12]
    ini = ROOT / "mt5" / "_diamond_run.ini"
    lines = ["[Tester]"]
    for k, v in [("Expert", EA), ("Symbol", SYMBOL), ("Period", "M1"),
                 ("Model", model), ("FromDate", frm), ("ToDate", to),
                 ("Deposit", deposit), ("Currency", "USD"), ("Leverage", "1:500"),
                 ("ExecutionMode", 163), ("Optimization", 0),
                 ("Report", name), ("ReplaceReport", 1),
                 ("ShutdownTerminal", 1), ("Visual", 0)]:
        lines.append("%s=%s" % (k, v))
    lines += ["", "[TesterInputs]"] + ["%s=%s" % kv for kv in cfg.items()]
    ini.write_text("\n".join(lines) + "\n", encoding="utf-16")

    kill_rig()
    try:
        subprocess.run([str(EXE), "/portable", "/config:" + str(ini)],
                       timeout=5400, capture_output=True)
    except subprocess.TimeoutExpired:
        kill_rig()
    REPORTS.mkdir(parents=True, exist_ok=True)
    for ext in (".htm", ".html"):
        src = RIG / (name + ext)
        if src.exists():
            dst = REPORTS / (name + ".htm")
            dst.write_bytes(src.read_bytes())
            try:
                src.unlink()
            except Exception:
                pass
            return name
    return None


def stats(stem: str) -> dict | None:
    p = REPORTS / (stem + ".htm")
    if not p.exists():
        return None
    raw = p.read_bytes()
    try:
        h = raw.decode("utf-16-le")
    except Exception:
        h = raw.decode("utf-8", errors="replace")
    flat = re.sub(r"\s+", " ", re.sub("<.*?>", " ", h)).replace("\xa0", "")
    m = re.search(r"Balance Drawdown Maximal:\s*([\d ]+\.\d\d)", flat)
    dd = float(m.group(1).replace(" ", "")) if m else 0.0

    pnl, comm = [], 0.0
    for row in re.findall(r'<tr bgcolor="#[0-9A-F]{6}" align=right>(.*?)</tr>', h, re.S):
        c = [re.sub("<.*?>", "", x).replace("\xa0", "").strip()
             for x in re.findall(r"<td.*?>(.*?)</td>", row, re.S)]
        if len(c) >= 13 and c[3] in ("buy", "sell"):
            try:
                comm += float(c[8].replace(" ", "") or 0)
            except ValueError:
                pass
            if c[4] == "out":
                pnl.append(float(c[10].replace(" ", "")))
    if not pnl:
        return None
    wins = [x for x in pnl if x > 0]
    streak = cur = 0
    for x in pnl:
        cur = cur + 1 if x <= 0 else 0
        streak = max(streak, cur)
    net = sum(pnl) + comm
    return {"net": net, "n": len(pnl), "wr": 100.0 * len(wins) / len(pnl),
            "dd": dd, "streak": streak, "ratio": (net / dd) if dd else 0.0}


def evaluate(name: str, over: dict, halves: bool = True) -> dict | None:
    f = run(over, *FULL)
    sf = stats(f) if f else None
    if not sf:
        print("  %-26s NO TRADES" % name, flush=True)
        return None
    out = {"name": name, "full": sf}
    if halves:
        for tag, win in (("h1", H1), ("h2", H2)):
            r = run(over, *win)
            out[tag] = stats(r) if r else None
    print("  %-26s done" % name, flush=True)
    return out


def report(title: str, results: list) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)
    print("config                     |   net    | trades | WR  | maxDD  | strk | "
          "ratio | h1 ratio | h2 ratio")
    print("-" * 100)
    for e in results:
        if not e:
            continue
        f, h1, h2 = e["full"], e.get("h1"), e.get("h2")
        print("%-26s | %+8.0f | %5d  | %2.0f%% | $%-5.0f | %3d  | %5.2f | %8s | %8s"
              % (e["name"][:26], f["net"], f["n"], f["wr"], f["dd"], f["streak"],
                 f["ratio"],
                 ("%.2f" % h1["ratio"]) if h1 else "-",
                 ("%.2f" % h2["ratio"]) if h2 else "-"))
