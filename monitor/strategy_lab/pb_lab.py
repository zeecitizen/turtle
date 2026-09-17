"""pb_lab.py — batch VSISA_Pullbacks configs, pinned to ITS OWN shipped defaults.

vsisa_lab.py pins VSISA's defaults; running the pullback EA through it silently mixes two
EAs' settings, which is the exact drift that made every "baseline" wrong for four versions.
This dict is read line-by-line from the `input` declarations of mt5/VSISA_Pullbacks.mq5.

OWN-MONEY MODE. Zee, 2026-09-18: "what if we were trading with our own money .. where we
could take leverage .. and no daily drawdown limit." The funded-account rules are off, so
drawdown stops being a hard gate and becomes a survivability question. Ranking is by
EXPECTANCY per trade and raw net; drawdown is still printed, because risk of ruin replaces
the 5% rule as the thing that ends the account.
"""
from __future__ import annotations
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SWEEP = ROOT / "monitor" / "strategy_lab" / "axi_sweep.py"
PY_EXE = r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
EA = "VSISA_Pullbacks"

FULL = ("2026.01.01", "2026.09.16")
H1 = ("2026.01.01", "2026.05.15")
H2 = ("2026.05.15", "2026.09.16")

SHIPPED = {
    "InpLots": "0.28", "InpTickets": "1", "InpMagicNumber": "88202", "InpMaxOpen": "2",
    "InpDayLossStop": "0.00", "InpSetupAuto": "true", "InpSetupMin": "2",
    "InpSetupMax": "10", "InpSetupBars": "2", "InpSetupGaps": "0",
    "InpRisingVol": "false", "InpStrictDir": "true", "InpOandaVolume": "0",
    "InpVolWindow": "1", "InpSwingPivot": "3", "InpSwingMin": "5",
    "InpVolLookback": "200", "InpBigMode": "1", "InpBigPct": "0.70", "InpBigAvg": "1.10",
    "InpQuietRef": "0", "InpLowVolPct": "5.00", "InpMinVolPct": "0.00",
    "InpBodyFrac": "0.35", "InpReactSpread": "0.00", "InpSizeBySpread": "false",
    "InpConfirmMode": "0", "InpTestRed": "false", "InpRetrace": "false",
    "InpTestExit": "0.00", "InpEngulf": "false", "InpStopRef": "0",
    "InpSlBufPts": "120", "InpMinSlPts": "60", "InpMaxSlPts": "900",
    "InpTargetR": "10.0", "InpTargetMode": "0", "InpTargetPts": "300",
    "InpTgtMinR": "0.50", "InpTgtMaxR": "0.00", "InpBreakEvenR": "0.0",
    "InpRatchetStart": "1.50", "InpRatchetStep": "8.00", "InpWickMode": "0",
    "InpWickFrac": "0.35", "InpAnomaly": "false", "InpCapVol": "0.00",
    "InpCloseLoc": "0.00", "InpEffortMin": "0.00", "InpFakeBreak": "false",
    "InpSweepLook": "30", "InpFadeMode": "1", "InpFadeLook": "5", "InpFadePct": "0.70",
    "InpFadeBigPct": "0.80", "InpTrendTF": "0", "InpTrendBars": "20",
    "InpTrendMode": "1", "InpCamelPivot": "2", "InpCamelLook": "120",
    "InpSessFrom": "0", "InpSessTo": "24", "InpCoolBars": "0",
    "InpBuys": "true", "InpSells": "true",
}

sys.path.insert(0, str(ROOT / "monitor" / "strategy_lab"))
from vsisa_lab import stats  # noqa: E402  - same report parser, MT5's own numbers


def run(over: dict, frm: str, to: str):
    cfg = dict(SHIPPED); cfg.update({k: str(v) for k, v in over.items()})
    out = subprocess.run(
        [PY_EXE, str(SWEEP), "--backtest", "--from", frm, "--to", to, "--model", "4",
         "--ea", EA, "--inputs", " ".join("%s=%s" % kv for kv in cfg.items())],
        capture_output=True, text=True, errors="replace").stdout
    m = re.findall(r"AXI_bt_\d+", out)
    return m[-1] if m else None


def evaluate(name: str, over: dict, halves: bool = True):
    f = run(over, *FULL); sf = stats(f) if f else None
    if not sf:
        print("  %-26s NO TRADES" % name, flush=True); return None
    out = {"name": name, "over": over, "full": sf, "stem": f}
    if halves:
        for tag, win in (("h1", H1), ("h2", H2)):
            r = run(over, *win); out[tag] = stats(r) if r else None
    print("  %-26s done  n=%d net=%+.0f" % (name, sf["n"], sf["net"]), flush=True)
    return out


DAYS = 182.0
HDR = ("config                     |     net  | trades | tr/day |  exp  |  WR | maxDD  | "
       "strk | ratio | h1 net | h2 net")


def report(title: str, res: list) -> None:
    print("\n" + "=" * 118); print(title); print("=" * 118)
    print(HDR); print("-" * 118)
    for e in sorted([x for x in res if x], key=lambda x: -x["full"]["net"]):
        f = e["full"]; h1 = e.get("h1"); h2 = e.get("h2")
        print("%-26s | %+8.0f | %6d | %6.2f | %5.2f | %2.0f%% | $%-5.0f | %3d  | %5.2f | %6s | %6s"
              % (e["name"][:26], f["net"], f["n"], f["n"] / DAYS, f["net"] / f["n"],
                 f["wr"], f["dd"], f["streak"], f["ratio"],
                 ("%+.0f" % h1["net"]) if h1 else "-",
                 ("%+.0f" % h2["net"]) if h2 else "-"))
