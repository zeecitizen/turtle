"""run_opt14.py - MT5 genetic optimisation of Saad15_opt14 (test copy of Saad_strategy_15min v1.23) for ONE day.

Zee 2026-10-15: "optimize the bot such that it trades with a high winrate on yesterday 14th october in specific".
PXBT rig, XAUUSDp real ticks, 14-15 Oct (the tester cannot run a single day); the EA's OnTester scores only
positions entered on InpOptDay: round(win% x 10) x 1e6 + (net + 500000), 0 under InpOptMinTrades trades.

    py run_opt14.py            # writes C:/mt5_rig_pxbt/reports/opt14.xml, then prints the top passes
"""
import re, subprocess, sys, time, html
from pathlib import Path
import axi_rig

axi_rig.use("pxbt")
RIG = axi_rig.RIG
EA = "Saad15_opt14"
# name: (start, step, stop) - optimised; everything else pinned to the EA's own defaults
OPT = {
    "InpEmaFast":     (7, 1, 12),
    "InpEmaSlow":     (20, 10, 60),
    "InpSlPips":      (25, 5, 45),
    "InpMaxRiskUsd":  (10, 5, 20),
    "InpChopEr":      (0, 0.05, 0.25),
    "InpBreakPips":   (0, 2, 4),
    "InpMinRangeAtr": (0.4, 0.1, 0.8),
    "InpMaruBody":    (0.45, 0.1, 0.65),
    "InpBeTpPct":     (0.5, 0.25, 1.0),
    "InpLongRule":    (0, 1, 2),
    "InpShortLine":   (0, 1, 2),
    "InpTrendAlign":  (0, 1, 1),
}
FIXED = {"InpLots": "1", "InpLogCsv": "false", "InpOptDay": "2026.10.14", "InpOptMinTrades": "3"}


def main():
    axi_rig.compile_ea(EA)
    inputs = axi_rig.ea_defaults(EA)
    inputs.update(FIXED)
    lines = []
    for k, v in inputs.items():
        if k in OPT:
            a, s, b = OPT[k]
            if k == "InpTrendAlign":
                lines.append(f"{k}=false||false||0||true||Y")
            else:
                lines.append(f"{k}={a}||{a}||{s}||{b}||Y")
        else:
            lines.append(f"{k}={v}||{v}||0||{v}||N")
    ini = ("[Tester]\r\nExpert=" + EA + "\r\nSymbol=XAUUSDp\r\nPeriod=M15\r\nModel=4\r\n"
           "FromDate=2026.10.14\r\nToDate=2026.10.15\r\nDeposit=25000\r\nCurrency=USD\r\nLeverage=1:500\r\n"
           "ExecutionMode=163\r\nOptimization=2\r\nOptimizationCriterion=6\r\n"
           "Report=reports\\opt14\r\nReplaceReport=1\r\nShutdownTerminal=1\r\nVisual=0\r\n[TesterInputs]\r\n" + "\r\n".join(lines) + "\r\n")
    (RIG / "reports").mkdir(exist_ok=True)
    (RIG / "opt14.ini").write_text(ini, encoding="utf-16")
    axi_rig.prune_logs()
    t0 = time.time()
    subprocess.run([str(RIG / "terminal64.exe"), "/portable", f"/config:{RIG / 'opt14.ini'}"], timeout=4 * 3600)
    print(f"optimisation finished in {time.time() - t0:.0f}s")
    top()


def top(n=25):
    """Decode the custom criterion of every pass in the XML report and print the best by win rate, then net."""
    rep = next((p for p in [RIG / "reports" / "opt14.xml", RIG / "reports" / "opt14.htm"] if p.exists()), None)
    if rep is None:
        sys.exit("no optimisation report")
    t = rep.read_bytes().decode("utf-8", errors="ignore") if rep.suffix == ".xml" else rep.read_text(encoding="utf-16", errors="ignore")
    rows = re.findall(r"<Row>(.*?)</Row>", t, re.S)
    cells = [[html.unescape(c) for c in re.findall(r"<Data[^>]*>(.*?)</Data>", r, re.S)] for r in rows]
    head, body = cells[0], cells[1:]
    ci = head.index("Custom")
    out = []
    for r in body:
        c = float(r[ci])
        if c <= 0:
            continue
        wr = int(c // 1e6) / 10
        net = round(c % 1e6 - 500000)
        out.append((wr, net, {h: r[i] for i, h in enumerate(head) if h in OPT or h in ("Pass", "Trades")}))
    out.sort(key=lambda x: (-x[0], -x[1]))
    print(f"{len(body)} passes, {len(out)} with >= {FIXED['InpOptMinTrades']} trades on the day")
    for wr, net, p in out[:n]:
        print(f"WR {wr:5.1f}%  net {net:+8d}  " + " ".join(f"{k[3:]}={v}" for k, v in p.items()))
    return out


if __name__ == "__main__":
    top() if "--top" in sys.argv else main()
