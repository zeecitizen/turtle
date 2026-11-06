"""hard_stop_what_if.py — "what if we close any trade the moment it goes
-$X adverse?" Calculated on TODAY's ACTUAL trades.

Method:
  1. Parse 20260514.log: pair [FILLED] (entry price/time/side/lots) with
     [CLOSED] (net P&L) by ticket.
  2. For each trade, scan M1 bars (rev_eng_m1_recent.csv) from entry bar
     to exit bar; compute MAE (max adverse excursion) in $.
  3. For each stop threshold T: if the trade's MAE reached -$T it would
     have been stopped → pnl = -T. Otherwise (never dipped -$T) keep the
     actual net P&L.

Caveats (stated honestly):
  - OHLC MAE: we see bar low/high, not the tick path. For same-minute
    trades the entry bar's low may include PRE-entry prices → MAE slightly
    overestimated → the stop looks like it fires a bit more than reality.
  - We also print a "strict" variant that ignores the entry bar's extreme
    (only counts MAE from the bar AFTER entry) as the optimistic bound.
"""
import re
from datetime import datetime, timedelta
from pathlib import Path

LOG = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs\20260514.log")
M1  = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\rev_eng_m1_recent.csv")
BROKER_OFFSET = timedelta(minutes=60)   # pinned earlier: broker = PC + 60min
CONTRACT = 100.0


def parse_log():
    text = LOG.read_bytes().decode("utf-16-le", errors="replace")
    fills = {}   # ticket -> dict
    closes = {}  # ticket -> dict
    for ln in text.splitlines():
        m_t = re.search(r"(\d{2}:\d{2}:\d{2})\.\d+", ln)
        if not m_t:
            continue
        pc_t = m_t.group(1)
        if "[FILLED]" in ln:
            m = re.search(r"\[FILLED\].*?(BUY|SELL)\s+ticket=(\d+)\s+@\s+([\d.]+)\s+lots=([\d.]+)", ln)
            if m:
                side = +1 if m.group(1) == "BUY" else -1
                tkt = int(m.group(2))
                fills[tkt] = {"pc_time": pc_t, "side": side,
                              "entry": float(m.group(3)), "lots": float(m.group(4))}
        elif "[CLOSED]" in ln and "net P&L" in ln:
            m = re.search(r"\[CLOSED\]\s+tkt=(\d+)\s+net P&L:\s+\$(-?[\d.]+)", ln)
            if m:
                closes[int(m.group(1))] = {"pc_time": pc_t, "net_pnl": float(m.group(2))}
    # pair
    trades = []
    for tkt, f in fills.items():
        if tkt not in closes:
            continue
        c = closes[tkt]
        trades.append({
            "ticket": tkt, "side": f["side"], "entry": f["entry"], "lots": f["lots"],
            "entry_pc": f["pc_time"], "exit_pc": c["pc_time"], "net_pnl": c["net_pnl"],
        })
    return trades


def load_bars():
    bars = []
    with open(M1, encoding="ascii", errors="replace") as fh:
        import csv
        for r in csv.DictReader(fh):
            bars.append({
                "time": datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                "high": float(r["high"]), "low": float(r["low"]),
            })
    bars.sort(key=lambda b: b["time"])
    return bars


def main():
    trades = parse_log()
    bars = load_bars()
    by_time = {b["time"]: i for i, b in enumerate(bars)}
    day = bars[-1]["time"].date()

    usable = []
    for t in trades:
        e_pc = datetime.combine(day, datetime.strptime(t["entry_pc"], "%H:%M:%S").time())
        x_pc = datetime.combine(day, datetime.strptime(t["exit_pc"], "%H:%M:%S").time())
        if x_pc < e_pc:
            x_pc += timedelta(days=1)   # crossed midnight (rare)
        e_b = (e_pc + BROKER_OFFSET).replace(second=0)
        x_b = (x_pc + BROKER_OFFSET).replace(second=0)
        # scan bars [e_b .. x_b]
        ppp = t["lots"] * CONTRACT
        mae_full = 0.0   # includes entry bar
        mae_strict = 0.0 # excludes entry bar
        cur = e_b
        first = True
        scanned = 0
        while cur <= x_b:
            if cur in by_time:
                b = bars[by_time[cur]]
                if t["side"] > 0:
                    adv = (t["entry"] - b["low"]) * ppp     # >0 = adverse
                else:
                    adv = (b["high"] - t["entry"]) * ppp
                mae_full = max(mae_full, adv)
                if not first:
                    mae_strict = max(mae_strict, adv)
                scanned += 1
            first = False
            cur += timedelta(minutes=1)
        if scanned == 0:
            continue
        t["mae_full"] = mae_full
        t["mae_strict"] = mae_strict
        usable.append(t)

    actual_net = sum(t["net_pnl"] for t in usable)
    n = len(usable)
    w = sum(1 for t in usable if t["net_pnl"] > 0)
    l = sum(1 for t in usable if t["net_pnl"] < 0)
    print(f"Paired & bar-matched trades today: {n}  ({w}W/{l}L)")
    print(f"ACTUAL net P&L of these trades: ${actual_net:+.2f}\n")

    print(f"{'stop':<7} {'MAE basis':<12} {'stopped':<9} {'kept':<7} {'sim net':<12} {'vs actual'}")
    print("-" * 62)
    for basis in ("mae_full", "mae_strict"):
        for T in (1.0, 2.0, 3.0, 4.0, 5.0):
            sim = 0.0
            stopped = 0
            for t in usable:
                if t[basis] >= T:           # trade dipped at least -$T → stopped
                    sim += -T
                    stopped += 1
                else:                        # never dipped that far → keep real outcome
                    sim += t["net_pnl"]
            kept = n - stopped
            tag = "(incl entry bar)" if basis == "mae_full" else "(excl entry bar)"
            print(f"-${T:<5.0f} {tag:<16} {stopped:<9} {kept:<7} ${sim:<+10.2f} ${sim-actual_net:+.2f}")
        print()

    # Of the trades that are currently WINNERS, how many dipped past each T?
    print("How many of today's WINNERS would the stop have killed (mae_full basis):")
    winners = [t for t in usable if t["net_pnl"] > 0]
    wsum = sum(t["net_pnl"] for t in winners)
    print(f"  {len(winners)} winners, total +${wsum:.2f}")
    for T in (1.0, 2.0, 3.0, 4.0, 5.0):
        killed = [t for t in winners if t["mae_full"] >= T]
        lost_profit = sum(t["net_pnl"] for t in killed)
        print(f"   -${T:.0f} stop kills {len(killed):>4}/{len(winners)} winners "
              f"(would forfeit +${lost_profit:.2f} of real profit, replace with -${T*len(killed):.2f})")


if __name__ == "__main__":
    main()
