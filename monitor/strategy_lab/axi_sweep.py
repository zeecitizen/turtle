"""axi_sweep.py — VSISA variant search on AXI's OWN data, in a portable Axi rig.

Zee, 2026-09-12: "i want you to test and find the highest profit variant of the current
VSISA EA on AXI volume.. take your time. test as deeply as possible."

WHY A SEPARATE RIG. The Blueberry harness (mt5_headless, C:/mt5_rig) replays Blueberry
data, and the whole point here is AXI's volume — a different broker, a different tick
stream, a different symbol (XAUUSD.pro). C:/axi_rig is a portable clone of the Axi
install plus a copy of its history, so nothing in this file can reach the terminal Zee
has the EA attached to.

WHAT AXI ACTUALLY HAS, measured rather than hoped:
  ticks  202609.tkc only  -> real-tick testing is SEPTEMBER ONLY, about 12 days
  bars   2024.hcc, 2026.hcc (2025 was locked by the running terminal)

That makes overfitting the central danger, not a footnote. Twelve days of one broker
will happily crown a variant that means nothing. So this file reports the SHAPE of the
result — whether the winner sits on a plateau or a spike, and whether its neighbours
agree — not just the top row.

    py monitor/strategy_lab/axi_sweep.py --grid shape
    py monitor/strategy_lab/axi_sweep.py --backtest --inputs "InpTargetR=2.5"
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent.parent
RIG = Path(r"C:/axi_rig")
EXE = RIG / "terminal64.exe"
SYMBOL = "XAUUSD.pro"
REPORTS = ROOT / "mt5" / "_tester_runs" / "axi"
LIVE_AXI = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal"
                r"/6FBEE76C719DC78AB2AE839B5A0C7442")

# The real-tick window Axi actually holds.
FROM, TO = "2026.09.01", "2026.09.12"

BASE = [
    "InpSetupBars=2", "InpBigMode=1", "InpBigPct=0.80", "InpBigAvg=1.20",
    "InpVolLookback=10", "InpQuietRef=0", "InpLowVolPct=1.00", "InpBodyFrac=0.35",
    "InpTargetR=2.5", "InpSlBufPts=30", "InpMinSlPts=60", "InpMaxSlPts=900",
    "InpBreakEvenR=1", "InpTrendTF=0", "InpStrictDir=false", "InpMaxOpen=10",
    "InpCoolBars=0", "InpWickMode=0", "InpAnomaly=false", "InpFakeBreak=false",
    "InpEngulf=false", "InpRisingVol=false", "InpConfirmMode=0", "InpOandaVolume=0",
]


def fixed(exclude):
    """BASE minus anything the grid is sweeping, so nothing is set twice."""
    ex = {e.split("=")[0] for e in exclude}
    return [b for b in BASE if b.split("=")[0] not in ex]


GRIDS = {
    # 1. THE SHAPE of the setup — how loud, how recent, how many bars.
    "shape": [
        "InpVolLookback=10||6||4||30||Y",
        "InpBigPct=0.80||0.50||0.15||0.95||Y",
        "InpBigAvg=1.20||1.00||0.20||1.80||Y",
        "InpSetupBars=2||2||1||3||Y",
    ],
    # 2. THE TRIGGER — what "quiet" has to mean.
    "trigger": [
        "InpLowVolPct=1.00||0.60||0.15||1.35||Y",
        "InpQuietRef=0||0||1||1||Y",
        "InpBodyFrac=0.35||0.15||0.15||0.60||Y",
        "InpStrictDir=0||0||1||1||Y",
    ],
    # 3. GEOMETRY — the part that decides how much a right answer is worth.
    "geom": [
        "InpTargetR=2.5||1.0||0.5||4.0||Y",
        "InpSlBufPts=30||10||20||90||Y",
        "InpBreakEvenR=1||0||1||1||Y",
        "InpMaxSlPts=900||600||400||1800||Y",
    ],
    # 4. THE LAWS THAT SHIP OFF — every one of them, together.
    "laws": [
        "InpWickMode=0||0||1||2||Y",
        "InpAnomaly=0||0||1||1||Y",
        "InpFakeBreak=0||0||1||1||Y",
        "InpEngulf=0||0||1||1||Y",
        "InpTrendTF=0||0||60||60||Y",
        "InpRisingVol=0||0||1||1||Y",
    ],
    # ── ROUND 2. Round 1 put four winners ON THE WALL of their range — TargetR at the
    # top of 1.0-4.0, VolLookback at the bottom of 6-30, BigAvg at the bottom of
    # 1.0-1.8, SlBufPts near the top of 10-90. A winner sitting on a wall was chosen by
    # the grid, not the data, so every one of those walls gets pushed here.
    "geom2": [
        "InpTargetR=4.0||3.0||1.0||8.0||Y",
        "InpSlBufPts=70||30||30||150||Y",
        "InpMaxSlPts=1000||800||400||2000||Y",
        "InpBreakEvenR=0||0||1||1||Y",
    ],
    "shape2": [
        "InpVolLookback=6||3||3||15||Y",
        "InpBigAvg=1.00||0.60||0.20||1.40||Y",
        "InpBigPct=0.80||0.65||0.15||0.95||Y",
        "InpWickMode=2||0||2||2||Y",
    ],
    # ── ROUND 3, THE INTERACTION. shape2 was run on the OLD geometry (2.5R, breakeven
    # on) so its numbers are not comparable to geom's. This pins the geometry that won
    # twice and sweeps the setup shape underneath it, which is the only way to see
    # whether a looser setup still pays once the target is 4R.
    "final": [
        "InpTargetR=4.0", "InpSlBufPts=70", "InpMaxSlPts=1000", "InpBreakEvenR=0",
        "InpVolLookback=6||6||4||14||Y",
        "InpBigAvg=1.00||0.80||0.20||1.40||Y",
        "InpBigPct=0.80||0.65||0.15||0.95||Y",
        "InpWickMode=0||0||2||2||Y",
    ],
    # ── ROUND 4. Round 3 pinned VolLookback, BigPct AND BigAvg at their floors, which
    # is the signature of a grid that has not found a minimum yet — or of an engine
    # being told to take everything. Push all three down until the number turns.
    "floor": [
        "InpTargetR=4.0", "InpSlBufPts=70", "InpMaxSlPts=1000", "InpBreakEvenR=0",
        "InpWickMode=2",
        "InpVolLookback=6||3||1||8||Y",
        "InpBigAvg=0.80||0.20||0.20||1.00||Y",
        "InpBigPct=0.65||0.20||0.15||0.80||Y",
    ],
    # ── LONG-WINDOW GEOMETRY. On 8 months of Axi bars both TargetR and MaxSlPts sat on
    # the ceiling, so push them. DRAWDOWN IS NOW A CONSTRAINT, not a footnote: the
    # 22k winner carried a 15% equity drawdown, which on a real account is the kind of
    # number that ends an account before the edge arrives.
    "geom3": [
        "InpTargetR=8.0||4.0||2.0||14.0||Y",
        "InpMaxSlPts=2000||1500||500||3500||Y",
        "InpSlBufPts=30||10||20||70||Y",
        "InpBreakEvenR=1||0||1||1||Y",
    ],
    # ── THE SANE FRONTIER. The unconstrained search DEGENERATES: every time TargetR and
    # MaxSlPts were extended the optimiser asked for more, reaching 14R / 3500pts for
    # +$62k at a 24% drawdown. That is not an edge, it is the discovery that on a
    # trending instrument "never take profit and use an enormous stop" wins a backtest.
    # It also stops being VSISA — the teacher's targets are 1:2 to 1:4 — and at 3500
    # points a single 0.10 ticket risks $350 against a $500 real account.
    # So the search is bounded to what is still his strategy and still survivable.
    "sane": [
        "InpTargetR=2.5||1.5||0.5||4.0||Y",
        "InpMaxSlPts=900||400||200||1200||Y",
        "InpSlBufPts=30||10||20||90||Y",
        "InpBreakEvenR=1||0||1||1||Y",
    ],
    "sane_shape": [
        "InpTargetR=3.0", "InpMaxSlPts=800", "InpSlBufPts=30", "InpBreakEvenR=1",
        "InpVolLookback=10||4||3||16||Y",
        "InpBigAvg=1.20||0.80||0.20||1.60||Y",
        "InpBigPct=0.80||0.50||0.15||0.95||Y",
        "InpWickMode=0||0||2||2||Y",
    ],
    # ── TIGHTER, NOT LOOSER. The long window wants SELECTIVITY: BigAvg 1.6 and
    # VolLookback 16 both landed on their ceilings, giving nearly the same money as the
    # high-frequency setting on a FIFTH of the trades (PF 1.40 vs 1.10, drawdown 1.5%
    # vs 5.9%). That is the exact opposite of what the September-only fit wanted, which
    # is itself the tell: 9 days rewards taking everything, 8 months rewards judgement.
    "tight": [
        "InpTargetR=3.0", "InpMaxSlPts=800", "InpSlBufPts=30", "InpBreakEvenR=1",
        "InpWickMode=0",
        "InpVolLookback=16||12||6||42||Y",
        "InpBigAvg=1.60||1.40||0.20||2.60||Y",
        "InpBigPct=0.65||0.50||0.15||0.95||Y",
    ],
    # ── HOW FAR BACK, FINALLY. VolLookback kept climbing (16 -> 42, still on the wall)
    # while BigAvg settled INTERIOR at 1.8. Worth noting where this is heading: the
    # original shipped default was 100, which Zee shortened to 10 by eye. The long
    # window is walking it back up.
    "look2": [
        "InpTargetR=3.0", "InpMaxSlPts=800", "InpSlBufPts=30", "InpBreakEvenR=1",
        "InpWickMode=0",
        "InpVolLookback=42||36||12||120||Y",
        "InpBigAvg=1.80||1.60||0.20||2.20||Y",
        "InpBigPct=0.80||0.65||0.15||0.95||Y",
    ],
    # 5. HOW MANY AT ONCE.
    "flow": [
        "InpMaxOpen=10||1||3||10||Y",
        "InpCoolBars=0||0||3||6||Y",
        "InpTargetR=2.5||1.5||0.5||3.0||Y",
    ],
}


def write_ini(path, name, grid, optimize, frm, to, period, model, delay, deposit):
    lines = ["[Tester]"]
    for k, v in [("Expert", "VSISA"), ("Symbol", SYMBOL), ("Period", period),
                 ("Model", model), ("FromDate", frm), ("ToDate", to),
                 ("Deposit", deposit), ("Currency", "USD"), ("Leverage", "1:500"),
                 ("ExecutionMode", delay),
                 ("Optimization", 1 if optimize else 0),
                 ("OptimizationCriterion", 0),
                 ("Report", name), ("ReplaceReport", 1),
                 ("ShutdownTerminal", 1), ("Visual", 0)]:
        lines.append("%s=%s" % (k, v))
    lines += ["", "[TesterInputs]"] + list(grid)
    path.write_text("\n".join(lines) + "\n", encoding="utf-16")


def kill_rig():
    """Only the rig's own exe, matched BY PATH — never the terminal Zee is watching."""
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process terminal64 -ErrorAction SilentlyContinue | "
                    "Where-Object { $_.Path -like 'C:\\axi_rig*' } | Stop-Process -Force"],
                   capture_output=True)


def sync_ea():
    """Always test the build that is actually deployed."""
    src = LIVE_AXI / "MQL5" / "Experts" / "VSISA.ex5"
    if src.exists():
        dst = RIG / "MQL5" / "Experts" / "VSISA.ex5"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def run(ini, timeout=10800):
    kill_rig()
    t0 = time.time()
    try:
        subprocess.run([str(EXE), "/portable", "/config:" + str(ini)],
                       timeout=timeout, capture_output=True)
    except subprocess.TimeoutExpired:
        print("[axi] TIMED OUT")
        kill_rig()
    return time.time() - t0


def fetch(name):
    REPORTS.mkdir(parents=True, exist_ok=True)
    for ext in (".xml", ".htm", ".html"):
        src = RIG / (name + ext)
        if src.exists():
            dst = REPORTS / (name + ext)
            shutil.copy2(src, dst)
            return dst
    return None


def num(x, d=0.0):
    try:
        return float(str(x).replace(" ", "").replace(",", "").replace("\u00a0", ""))
    except (TypeError, ValueError):
        return d


def parse_xml(p):
    try:
        tree = ET.parse(p)
    except Exception as e:  # noqa: BLE001
        print("[axi] cannot parse %s: %s" % (p.name, e))
        return []
    ns = "urn:schemas-microsoft-com:office:spreadsheet"
    out, head = [], None
    for row in tree.getroot().iter("{%s}Row" % ns):
        cells = []
        for c in row.iter("{%s}Cell" % ns):
            d = c.find("{%s}Data" % ns)
            cells.append("" if d is None or d.text is None else d.text.strip())
        if head is None:
            head = cells
            continue
        if len(cells) < len(head):
            cells += [""] * (len(head) - len(cells))
        out.append(dict(zip(head, cells)))
    return out


def col(row, *names):
    for n in names:
        for k in row:
            if k.lower().strip() == n.lower():
                return row[k]
    return ""


def per_day(p):
    """Realised P&L by broker day from an HTML report's DEALS table."""
    txt = ""
    for enc in ("utf-16", "utf-8"):
        try:
            txt = p.read_text(encoding=enc, errors="replace")
            if "<" in txt:
                break
        except Exception:
            continue
    i = txt.lower().find(">deals<")
    if i < 0:
        return {}, 0, 0
    day = defaultdict(float)
    w = l = 0
    for rw in re.findall(r"<tr[^>]*>(.*?)</tr>", txt[i:], re.S | re.I):
        c = [re.sub(r"<[^>]+>", "", x).replace("\u00a0", " ").strip()
             for x in re.findall(r"<td[^>]*>(.*?)</td>", rw, re.S | re.I)]
        if len(c) < 12 or c[4].lower() != "out":
            continue
        m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", c[0])
        if not m:
            continue

        def g(k):
            try:
                return float(re.sub(r"[^0-9.+-]", "", c[k]))
            except (ValueError, IndexError):
                return 0.0
        pr = g(8) + g(9) + g(10)
        day["%s-%s-%s" % m.groups()] += pr
        if pr > 0:
            w += 1
        elif pr < 0:
            l += 1
    return dict(day), w, l


def sweep(gridname, args):
    grid = GRIDS[gridname]
    inputs = fixed(grid) + grid
    name = "AXI_%s_%s" % (gridname, datetime.now().strftime("%H%M%S"))
    ini = ROOT / "mt5" / "_axi_sweep.ini"
    write_ini(ini, name, inputs, True, args.frm, args.to, args.period,
              args.model, args.delay, args.deposit)
    swept = [g.split("=")[0] for g in grid]
    print("\n=== GRID %s ===" % gridname.upper(), flush=True)
    for g in grid:
        print("   " + g)
    el = run(ini)
    rep = fetch(name)
    if not rep:
        print("[axi] %s: NO REPORT after %.0fs" % (gridname, el))
        return []
    rows = parse_xml(rep)
    scored = []
    for r in rows:
        scored.append({
            "profit": num(col(r, "Profit", "Net Profit")),
            "trades": int(num(col(r, "Trades", "Total Trades"))),
            "pf": num(col(r, "Profit Factor")),
            "dd": num(col(r, "Equity DD %", "Drawdown")),
            "vals": {s: col(r, s) for s in swept},
        })
    scored.sort(key=lambda x: -x["profit"])
    print("[axi] %s: %d passes in %.0fs" % (gridname, len(scored), el))
    hdr = "%9s %7s %6s %7s  " % ("profit", "trades", "PF", "DD%") + \
          "  ".join("%-13s" % s.replace("Inp", "") for s in swept)
    print(hdr)
    print("-" * len(hdr))
    for r in scored[:args.top]:
        print("%9.2f %7d %6.2f %7.2f  " % (r["profit"], r["trades"], r["pf"], r["dd"])
              + "  ".join("%-13s" % r["vals"].get(s, "") for s in swept))
    live = [r for r in scored if r["trades"] >= args.minlive]
    print("\n  %d/%d passes took >= %d trades" % (len(live), len(scored), args.minlive))
    if live:
        b = live[0]
        print("  BEST WITH ENOUGH TRADES: %.2f on %d trades, PF %.2f  |  %s"
              % (b["profit"], b["trades"], b["pf"],
                 "  ".join("%s=%s" % (k.replace("Inp", ""), v)
                           for k, v in b["vals"].items())))
    return scored


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--inputs", default="")
    ap.add_argument("--frm", "--from", dest="frm", default=FROM)
    ap.add_argument("--to", default=TO)
    ap.add_argument("--period", default="M5")
    ap.add_argument("--model", type=int, default=4)
    ap.add_argument("--delay", type=int, default=163)
    ap.add_argument("--deposit", type=int, default=50000)
    ap.add_argument("--top", type=int, default=18)
    ap.add_argument("--minlive", type=int, default=8)
    args = ap.parse_args()

    if not EXE.exists():
        sys.exit("[axi] no rig at %s" % EXE)
    sync_ea()
    print("[axi] rig %s · %s %s · %s -> %s · model %d"
          % (RIG, SYMBOL, args.period, args.frm, args.to, args.model), flush=True)

    if args.backtest:
        name = "AXI_bt_%s" % datetime.now().strftime("%H%M%S")
        ini = ROOT / "mt5" / "_axi_bt.ini"
        write_ini(ini, name, fixed(args.inputs.split()) + args.inputs.split(),
                  False, args.frm, args.to, args.period, args.model,
                  args.delay, args.deposit)
        el = run(ini)
        rep = fetch(name)
        if not rep:
            print("[axi] NO REPORT after %.0fs" % el)
            sys.exit(1)
        d, w, l = per_day(rep)
        print("[axi] %d days, %dW/%dL, net %.2f  (%.0fs)  -> %s"
              % (len(d), w, l, sum(d.values()), el, rep.name))
        for k in sorted(d):
            print("   %s  %9.2f" % (k, d[k]))
        return

    names = list(GRIDS) if args.all else ([args.grid] if args.grid else [])
    if not names:
        sys.exit("[axi] pick --grid <%s> or --all" % "|".join(GRIDS))
    for n in names:
        sweep(n, args)


if __name__ == "__main__":
    main()
