"""extract_today_trades.py — pull today's trades since 'goodnight' (~22:00 PC
2026-05-14) from the EA's own logs, pair entries with exits, and write a CSV
with everything needed for P&L pattern analysis.

TurtleTradeLogger died — `turtle_fills.csv` stops at 09:50 broker yesterday.
But UhvSweepExhaustion v3.49 logs every fill ([PROBE]/[FILLED] for opens,
[DEAL_OUT]/[CLOSED] for closes), so we reconstruct from there.

Output: monitor/strategy_lab/trades_since_goodnight.csv
"""
import csv
import re
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs")
OUT = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\trades_since_goodnight.csv")
BROKER_OFFSET = timedelta(minutes=60)   # PC → broker

# Cutoff: "after last night goodnight" — wrap was ~22:00 PC on 2026-05-14
CUTOFF_PC = datetime(2026, 5, 14, 21, 30)


def parse_logs():
    fills = {}    # ticket -> {pc_time, side, entry, lots, kind (PROBE/REAL)}
    closes = {}   # position_id -> {pc_time, net_pnl}
    for log in (LOG_DIR / "20260514.log", LOG_DIR / "20260515.log"):
        if not log.exists(): continue
        text = log.read_bytes().decode("utf-16-le", errors="replace")
        for ln in text.splitlines():
            m_t = re.search(r"(\d{2}:\d{2}:\d{2})\.\d+", ln)
            if not m_t: continue
            tstr = m_t.group(1)
            # determine the log's day from filename
            date_str = log.stem  # e.g. "20260515"
            pc_dt = datetime.strptime(f"{date_str} {tstr}", "%Y%m%d %H:%M:%S")

            # v3.49 opens: [PROBE] SIDE LOTS @ PRICE tkt=N ...
            m = re.search(r"\[PROBE\]\s+(BUY|SELL)\s+([\d.]+)\s+@\s+([\d.]+)\s+tkt=(\d+)", ln)
            if m:
                fills[int(m.group(4))] = {
                    "pc_time": pc_dt, "kind": "PROBE",
                    "side": m.group(1), "lots": float(m.group(2)),
                    "entry": float(m.group(3)),
                }
            # v3.49 main fires: [PROBE_RECOVERED→MAIN] SIDE LOTS @ PRICE tkt=N ...
            m = re.search(r"\[PROBE_RECOVERED.{0,3}MAIN\]\s+(BUY|SELL)\s+([\d.]+)\s+@\s+([\d.]+)\s+tkt=(\d+)", ln)
            if m:
                fills[int(m.group(4))] = {
                    "pc_time": pc_dt, "kind": "MAIN",
                    "side": m.group(1), "lots": float(m.group(2)),
                    "entry": float(m.group(3)),
                }
            # v3.48 legacy: [FILLED] (PROBE|REAL) SIDE ticket=N @ PRICE lots=L
            m = re.search(r"\[FILLED\]\s+(?:(PROBE|REAL)\s+)?(BUY|SELL)\s+ticket=(\d+)\s+@\s+([\d.]+)\s+lots=([\d.]+)", ln)
            if m:
                fills[int(m.group(3))] = {
                    "pc_time": pc_dt,
                    "kind": m.group(1) or ("PROBE" if float(m.group(5)) < 0.05 else "MAIN"),
                    "side": m.group(2),
                    "entry": float(m.group(4)),
                    "lots": float(m.group(5)),
                }
            # closes — v3.49 emits [DEAL_OUT] pos=N net=$X
            m = re.search(r"\[DEAL_OUT\]\s+pos=(\d+)\s+net=\$(-?[\d.]+)", ln)
            if m:
                closes[int(m.group(1))] = {"pc_time": pc_dt, "net_pnl": float(m.group(2))}
            # legacy "[CLOSED] tkt=N net P&L: $X"
            m = re.search(r"\[CLOSED\]\s+tkt=(\d+)\s+net P&L:\s+\$(-?[\d.]+)", ln)
            if m:
                closes[int(m.group(1))] = {"pc_time": pc_dt, "net_pnl": float(m.group(2))}

    trades = []
    for tkt, f in fills.items():
        if tkt not in closes: continue
        c = closes[tkt]
        if c["pc_time"] < CUTOFF_PC: continue
        trades.append({
            "open_pc":  f["pc_time"],
            "close_pc": c["pc_time"],
            "open_broker":  f["pc_time"]  + BROKER_OFFSET,
            "close_broker": c["pc_time"] + BROKER_OFFSET,
            "ticket": tkt,
            "kind": f["kind"],
            "side": f["side"],
            "lots": f["lots"],
            "entry": f["entry"],
            "net_pnl": c["net_pnl"],
            "hold_sec": int((c["pc_time"] - f["pc_time"]).total_seconds()),
        })
    trades.sort(key=lambda x: x["open_pc"])
    return trades


def main():
    trades = parse_logs()
    if not trades:
        print("No trades found after goodnight cutoff.")
        return
    cum = 0.0
    last_close = None
    rows = []
    for tr in trades:
        cum += tr["net_pnl"]
        gap = int((tr["open_pc"] - last_close).total_seconds()) if last_close else 0
        rows.append({
            "open_broker_time":  tr["open_broker"].strftime("%Y-%m-%d %H:%M:%S"),
            "close_broker_time": tr["close_broker"].strftime("%Y-%m-%d %H:%M:%S"),
            "broker_hour": tr["open_broker"].hour,
            "ticket": tr["ticket"],
            "kind": tr["kind"],
            "side": tr["side"],
            "lots": tr["lots"],
            "entry": tr["entry"],
            "net_pnl": tr["net_pnl"],
            "hold_seconds": tr["hold_sec"],
            "gap_from_prev_close_s": gap,
            "cumulative_pnl": round(cum, 2),
            "outcome": "WIN" if tr["net_pnl"] > 0 else ("LOSS" if tr["net_pnl"] < 0 else "FLAT"),
        })
        last_close = tr["close_pc"]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows: w.writerow(r)

    n = len(rows)
    w_n = sum(1 for r in rows if r["outcome"] == "WIN")
    l_n = sum(1 for r in rows if r["outcome"] == "LOSS")
    probes = sum(1 for r in rows if r["kind"] == "PROBE")
    reals  = sum(1 for r in rows if r["kind"] == "MAIN")
    net    = sum(r["net_pnl"] for r in rows)
    print(f"Wrote {n} trades to:")
    print(f"  {OUT}\n")
    print(f"Range (broker time): {rows[0]['open_broker_time']} → {rows[-1]['close_broker_time']}")
    print(f"  PROBE: {probes}   REAL: {reals}")
    print(f"  {w_n}W / {l_n}L  ({100*w_n/(w_n+l_n):.0f}% WR)")
    print(f"  Net P&L: ${net:+.2f}")
    print(f"  Worst single trade: ${min(r['net_pnl'] for r in rows):+.2f}")
    print(f"  Best  single trade: ${max(r['net_pnl'] for r in rows):+.2f}")


if __name__ == "__main__":
    main()
