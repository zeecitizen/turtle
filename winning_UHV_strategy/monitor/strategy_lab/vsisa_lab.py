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

# v1.23 AS SHIPPED — re-pinned 2026-09-17 straight from the `input` lines of
# mt5/VSISA.mq5. The previous copy of this dict was still v1.19 (wick 2, ratchet step
# 1.0, swing 10, target 5R) and carried no fade inputs at all, so every "baseline" it
# printed was a config that has not been shipped for four versions. Every experiment
# below is THIS, with one or two things moved.
SHIPPED = {
    "InpLots": "0.28", "InpTickets": "1", "InpMaxOpen": "2", "InpDayLossStop": "0.00",
    "InpSetupAuto": "true", "InpSetupMin": "2", "InpSetupMax": "10",
    "InpSetupBars": "2", "InpSetupGaps": "0", "InpRisingVol": "false",
    "InpStrictDir": "true", "InpOandaVolume": "0", "InpOandaStrict": "true",
    "InpVolWindow": "1", "InpSwingPivot": "3", "InpSwingMin": "5",
    "InpVolLookback": "200", "InpBigMode": "1", "InpBigPct": "0.80",
    "InpBigAvg": "1.20", "InpQuietRef": "0", "InpLowVolPct": "1.00",
    "InpMinVolPct": "0.00", "InpBodyFrac": "0.35", "InpReactSpread": "0.00",
    "InpSizeBySpread": "false", "InpConfirmMode": "0", "InpTestVolPct": "0.90",
    "InpTestRed": "false", "InpRetrace": "false", "InpTestExit": "0.00",
    "InpTestWindow": "3", "InpTestAvgBars": "20", "InpEngulf": "false",
    "InpStopRef": "0", "InpSlBufPts": "120", "InpMinSlPts": "60",
    "InpMaxSlPts": "900", "InpTargetR": "10.0", "InpTargetMode": "0",
    "InpTargetPts": "300", "InpTgtMinR": "0.50", "InpTgtMaxR": "0.00",
    "InpBreakEvenR": "0.0", "InpRatchetStart": "2.00", "InpRatchetStep": "8.00",
    "InpWickMode": "0", "InpWickFrac": "0.35", "InpAnomaly": "false",
    "InpCapVol": "0.00", "InpCloseLoc": "0.00", "InpEffortMin": "0.00",
    "InpFakeBreak": "true", "InpSweepLook": "30",
    "InpFadeMode": "1", "InpFadeLook": "4", "InpFadePct": "0.60",
    "InpFadeBigPct": "0.80",
    "InpTrendTF": "30", "InpTrendBars": "20", "InpTrendMode": "1",
    "InpCamelPivot": "2", "InpCamelLook": "120",
    "InpSessFrom": "0", "InpSessTo": "24", "InpCoolBars": "0",
    "InpBuys": "true", "InpSells": "true",
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
