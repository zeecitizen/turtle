"""vsisa_lab.py — batch VSISA configs through MT5 and report them walk-forward.

Zee, 2026-09-16, going to bed: "i want you to through the night experiment thoroughly
with the following: wicks .. finding out if we're taking all possible setups .. solving
the no-supply candle's mystery .. tuning this strategy further, try diff config
combinations .. increasing the frequency of trading .. keep working in a loop till you
find optimal values."

WHY THIS EXISTS. Every finding tonight has to survive the same test the shipped ones did:
full window AND both halves, because a night of single-window numbers is how you end up
shipping a spike. Doing that by hand costs three backtests and a hand-written table per
idea; this does it in one line and prints the three numbers that actually decide:

    net per $1 of drawdown   — the only fair comparison across different position risk
    win rate                 — what Zee asked for
    worst losing streak      — what makes it bearable

RULE INHERITED FROM CLAUDE.md: MT5's Strategy Tester is the only thing here that may
PROMOTE a config. This file runs the tester and parses ITS reports; it simulates nothing.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SWEEP = ROOT / "monitor" / "strategy_lab" / "axi_sweep.py"
REPORTS = ROOT / "mt5" / "_tester_runs" / "axi"
PY = r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"

FULL = ("2026.01.01", "2026.09.16")
H1 = ("2026.01.01", "2026.05.15")
H2 = ("2026.05.15", "2026.09.16")

# v1.19 AS SHIPPED. Every experiment below is this, with one or two things moved.
SHIPPED = {
    "InpLots": "0.28", "InpVolWindow": "1", "InpSetupAuto": "true",
    "InpStrictDir": "true", "InpRisingVol": "false", "InpStopRef": "0",
    "InpMaxOpen": "2", "InpCoolBars": "0", "InpQuietRef": "0", "InpBigMode": "1",
    "InpVolLookback": "200", "InpOandaVolume": "0", "InpFakeBreak": "true",
    "InpSweepLook": "30", "InpEngulf": "false", "InpAnomaly": "false",
    "InpCapVol": "0", "InpEffortMin": "0", "InpCloseLoc": "0", "InpTestExit": "0",
    "InpRetrace": "false", "InpSetupGaps": "0", "InpConfirmMode": "0",
    "InpReactSpread": "0", "InpSizeBySpread": "false", "InpDayLossStop": "0",
    "InpSetupMin": "2", "InpSetupMax": "10", "InpSwingPivot": "3", "InpSwingMin": "10",
    "InpBigPct": "0.80", "InpBigAvg": "1.20", "InpBodyFrac": "0.35",
    "InpSlBufPts": "120", "InpMinSlPts": "60", "InpMaxSlPts": "900",
    "InpBreakEvenR": "0", "InpRatchetStart": "2.0", "InpRatchetStep": "1.0",
    "InpLowVolPct": "1.00", "InpMinVolPct": "0.00", "InpWickMode": "2",
    "InpWickFrac": "0.35", "InpTargetMode": "0", "InpTargetR": "5.0",
    "InpTgtMinR": "0.25", "InpTgtMaxR": "0", "InpSessFrom": "0", "InpSessTo": "24",
    "InpTrendTF": "30", "InpTrendMode": "1", "InpTrendBars": "20",
    "InpCamelPivot": "2", "InpCamelLook": "120", "InpTestVolPct": "0.9",
    "InpTestRed": "false", "InpMinVolPct": "0.00",
}


def run(over: dict, frm: str, to: str) -> str | None:
    """One tester pass. Returns the report stem, or None if it produced nothing."""
    cfg = dict(SHIPPED)
    cfg.update({k: str(v) for k, v in over.items()})
    inputs = " ".join("%s=%s" % kv for kv in cfg.items())
    out = subprocess.run(
        [PY, str(SWEEP), "--backtest", "--from", frm, "--to", to,
         "--model", "4", "--inputs", inputs],
        capture_output=True, text=True, errors="replace").stdout
    m = re.findall(r"AXI_bt_\d+", out)
    return m[-1] if m else None


def stats(stem: str) -> dict | None:
    """Everything that matters, read out of MT5's OWN report."""
    p = REPORTS / (stem + ".htm")
    if not p.exists():
        return None
    h = p.read_bytes().decode("utf-16-le", errors="replace")
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
            "dd": dd, "streak": streak, "ratio": (net / dd) if dd else 0.0,
            "avgwin": (sum(wins) / len(wins)) if wins else 0.0}


def evaluate(name: str, over: dict, halves: bool = True) -> dict | None:
    """Full window plus both halves — the shape of the evidence, not one number."""
    f = run(over, *FULL)
    sf = stats(f) if f else None
    if not sf:
        print("  %-26s NO TRADES" % name, flush=True)
        return None
    out = {"name": name, "over": over, "full": sf}
    if halves:
        for tag, win in (("h1", H1), ("h2", H2)):
            r = run(over, *win)
            out[tag] = stats(r) if r else None
    return out


HDR = ("config                     |   net    | trades | WR  | maxDD  | strk | "
       "ratio | h1 ratio | h2 ratio")


def line(e: dict) -> str:
    f = e["full"]
    h1 = e.get("h1")
    h2 = e.get("h2")
    return ("%-26s | %+8.0f | %5d  | %2.0f%% | $%-5.0f | %3d  | %5.2f | %8s | %8s"
            % (e["name"][:26], f["net"], f["n"], f["wr"], f["dd"], f["streak"],
               f["ratio"],
               ("%.2f" % h1["ratio"]) if h1 else "-",
               ("%.2f" % h2["ratio"]) if h2 else "-"))


def report(title: str, results: list) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)
    print(HDR)
    print("-" * 100)
    for e in results:
        if e:
            print(line(e), flush=True)
