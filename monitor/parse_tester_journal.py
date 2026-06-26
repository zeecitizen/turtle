"""parse_tester_journal.py — extract real trade outcomes from MT5 tester log.

The HTML report parser is unreliable. The MT5 tester journal log contains every
LIVE TRIGGER, FILL, close (SL/TP/end-of-test), with exact prices. Pair them.

Usage:
    py monitor/parse_tester_journal.py [--log <path>] [--from-wall HH:MM]
"""
from __future__ import annotations
import argparse, os, re, sys
from collections import defaultdict
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_LOG = r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\81A933A9AFC5DE3C23B15CAB19C63850\Tester\logs"


def load_log_text(path):
    with open(path, "rb") as f:
        data = f.read()
    try:
        return data.decode("utf-16-le", errors="replace")
    except Exception:
        return data.decode("utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=None)
    ap.add_argument("--from-wall", default=None, help="filter to events with wallclock >= HH:MM")
    args = ap.parse_args()

    if args.log is None:
        d = DEFAULT_LOG
        files = sorted(os.listdir(d))
        args.log = os.path.join(d, files[-1])
    print(f"Reading {args.log}")
    text = load_log_text(args.log)
    lines = text.splitlines()
    print(f"  {len(lines):,} log lines, {len(text):,} bytes")

    # Regex for log line structure: "<id>\t<core>\t<wallclock>.<ms>\tCore <n>\t<simtime> <message>"
    line_re = re.compile(
        r"\S+\s+\d+\s+(\d+:\d+:\d+)\.\d+\s+Core\s+\d+\s+(\d{4}\.\d{2}\.\d{2}\s+\d+:\d+:\d+)\s+(.*)"
    )
    trigger_re = re.compile(r"\[S1\]\s+S1\s+(BUY|SELL)\s+LIVE TRIGGER.*entry=([\d\.]+)\s+sl=([\d\.]+)\s+tp=([\d\.]+).*uhv_shift=(\d+)\s+\(vol=(\d+)\)")
    fill_re = re.compile(r"\[S1\]\s+\[FILLED\]\s+ticket=(\d+)")
    # "stop loss triggered #10 sell 0.01 XAUUSD 4441.57 sl: 4453.89 tp: 4429.25 [#12 buy 0.01 XAUUSD at 4453.89]"
    sl_re = re.compile(r"stop loss triggered #(\d+)\s+(buy|sell)\s+[\d\.]+\s+XAUUSD\s+[\d\.]+\s+sl:\s+[\d\.]+\s+tp:\s+[\d\.]+\s+\[#\d+\s+(?:buy|sell)\s+[\d\.]+\s+XAUUSD\s+at\s+([\d\.]+)\]")
    tp_re = re.compile(r"take profit triggered #(\d+)\s+(buy|sell)\s+[\d\.]+\s+XAUUSD\s+[\d\.]+\s+sl:\s+[\d\.]+\s+tp:\s+[\d\.]+\s+\[#\d+\s+(?:buy|sell)\s+[\d\.]+\s+XAUUSD\s+at\s+([\d\.]+)\]")
    close_end_re = re.compile(r"position closed due end of test at ([\d\.]+)\s+\[#(\d+)\s+(buy|sell)")

    trades = []
    pending_trigger = None  # (side, entry, sl, tp, uhv_shift, uhv_vol, simtime, wallclock)

    wall_filter = None
    if args.from_wall:
        wall_filter = args.from_wall

    for line in lines:
        m = line_re.match(line)
        if not m:
            continue
        wall, sim, msg = m.group(1), m.group(2), m.group(3)
        if wall_filter and wall < wall_filter:
            continue

        t = trigger_re.search(msg)
        if t:
            pending_trigger = {
                "side": t.group(1),
                "entry": float(t.group(2)),
                "sl": float(t.group(3)),
                "tp": float(t.group(4)),
                "uhv_shift": int(t.group(5)),
                "uhv_vol": int(t.group(6)),
                "sim_open": sim,
                "wall_open": wall,
            }
            continue

        f = fill_re.search(msg)
        if f and pending_trigger is not None:
            pending_trigger["ticket"] = int(f.group(1))
            trades.append(pending_trigger)
            pending_trigger = None
            continue

        # close events
        ce = close_end_re.search(msg)
        if ce:
            close_price = float(ce.group(1))
            ticket = int(ce.group(2))
            # find matching open trade by ticket
            for tr in trades:
                if tr.get("ticket") == ticket and "close_price" not in tr:
                    tr["close_price"] = close_price
                    tr["close_reason"] = "end_of_test"
                    tr["sim_close"] = sim
                    break
            continue

        sm = sl_re.search(msg)
        if sm:
            ticket = int(sm.group(1))
            close_price = float(sm.group(3))
            for tr in trades:
                if tr.get("ticket") == ticket and "close_price" not in tr:
                    tr["close_price"] = close_price
                    tr["close_reason"] = "SL"
                    tr["sim_close"] = sim
                    break
            continue

        tm = tp_re.search(msg)
        if tm:
            ticket = int(tm.group(1))
            close_price = float(tm.group(3))
            for tr in trades:
                if tr.get("ticket") == ticket and "close_price" not in tr:
                    tr["close_price"] = close_price
                    tr["close_reason"] = "TP"
                    tr["sim_close"] = sim
                    break
            continue

    # Compute outcomes
    closed = [t for t in trades if "close_price" in t]
    wins = []
    losses = []
    for tr in closed:
        if tr["side"] == "BUY":
            pnl = tr["close_price"] - tr["entry"]
        else:
            pnl = tr["entry"] - tr["close_price"]
        tr["pnl_pts"] = pnl
        # XAUUSD at 0.01 lots: 1.0 price-point = $1 USD P&L (100 oz × 0.01 = 1 oz, $1 per $1 price move)
        tr["pnl_usd"] = pnl * 1.0
        if pnl > 0:
            wins.append(tr)
        else:
            losses.append(tr)

    print(f"\n=== TRADE OUTCOMES (wall>={wall_filter or 'all'}) ===")
    print(f"  Total trades:    {len(trades)}")
    print(f"  Closed:          {len(closed)}")
    print(f"  Open (no close): {len(trades) - len(closed)}")
    if closed:
        net = sum(t["pnl_usd"] for t in closed)
        wr = 100 * len(wins) / len(closed)
        avg_win = sum(t["pnl_usd"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl_usd"] for t in losses) / len(losses) if losses else 0
        gross_p = sum(t["pnl_usd"] for t in wins)
        gross_l = abs(sum(t["pnl_usd"] for t in losses))
        pf = gross_p / gross_l if gross_l > 0 else float("inf")
        print(f"  Wins:            {len(wins)} ({wr:.1f}% WR)")
        print(f"  Losses:          {len(losses)}")
        print(f"  Avg win:         ${avg_win:.2f}")
        print(f"  Avg loss:        ${avg_loss:.2f}")
        print(f"  Net P/L:         ${net:.2f}")
        print(f"  Profit factor:   {pf:.2f}")

        # By side
        for side in ("BUY", "SELL"):
            sc = [t for t in closed if t["side"] == side]
            sw = [t for t in sc if t["pnl_usd"] > 0]
            if sc:
                print(f"  {side}: {len(sc)} trades, {100*len(sw)/len(sc):.1f}% WR, net ${sum(t['pnl_usd'] for t in sc):.2f}")


if __name__ == "__main__":
    main()
