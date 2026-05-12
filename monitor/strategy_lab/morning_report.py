"""
morning_report.py — generates a clean morning report for Zee combining:
  - Live EA state (heartbeat)
  - Today's trades parsed from MT5 logs
  - Cumulative since v3.30 deploy
  - Overnight analysis findings summary
"""
import csv
import json
import os
import re
import statistics
import time
from datetime import datetime, timedelta
from pathlib import Path

COMMON  = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
LOGS    = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "DBE9B8B347D025DD139E103EE3B63FD8" / "MQL5" / "Logs"
HEARTBEAT = COMMON / "uhv_sweep_state.json"


def parse_today_trades():
    today = datetime.now().strftime("%Y%m%d")
    log_file = LOGS / f"{today}.log"
    if not log_file.exists():
        return []
    text = log_file.read_bytes().decode("utf-16-le", errors="replace")
    trades = []
    open_signal = None; pending_exit_reason = None; pending_peak = None
    for ln in text.splitlines():
        if "UhvL2" not in ln or "UhvSweepExhaustion" not in ln: continue
        time_m = re.search(r"(\d{2}:\d{2}:\d{2})\.\d+", ln)
        ts = time_m.group(1) if time_m else "?"
        if "[SIGNAL]" in ln:
            m = re.search(r"\[SIGNAL\]\s+(BUY|SELL)\s+@\s+([\d.]+).*?SL=([\d.]+).*?R=([\d.]+)", ln)
            if m:
                open_signal = {"time": ts, "side": m.group(1), "price": float(m.group(2)),
                               "sl": float(m.group(3)), "r": float(m.group(4))}
                pending_exit_reason = None; pending_peak = None
        elif "[EXIT" in ln:
            m = re.search(r"\[EXIT\s+(\w+)\].*?pnl=\$(-?\d+\.\d+).*?peak=\$(-?\d+\.\d+)", ln)
            if m and open_signal:
                pending_exit_reason = m.group(1)
                pending_peak = float(m.group(3))
        elif "[CLOSED] net P&L:" in ln:
            # Authoritative P&L from history. Combine with prior [EXIT] info if any.
            m = re.search(r"net P&L:\s+\$(-?\d+\.\d+)", ln)
            if m and open_signal:
                trades.append({
                    "open_time": open_signal["time"], "side": open_signal["side"],
                    "open_price": open_signal["price"], "r": open_signal["r"],
                    "close_time": ts,
                    "exit_reason": pending_exit_reason or "sl",  # if no [EXIT], must be broker-side SL
                    "pnl": float(m.group(1)),
                    "peak": pending_peak if pending_peak is not None else 0,
                })
                open_signal = None; pending_exit_reason = None; pending_peak = None
    return trades


def main():
    print("═" * 75)
    print(" UhvSweepExhaustion v3.30 — Morning Report")
    print(f" Generated {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("═" * 75)

    # Live state
    print("\n📊 LIVE EA STATE")
    if HEARTBEAT.exists():
        d = json.load(HEARTBEAT.open())
        age = time.time() - HEARTBEAT.stat().st_mtime
        print(f"  EA:       {d.get('ea')}")
        print(f"  Hbt age:  {age:.1f}s  {'⚠️  STALE' if age > 60 else '✓ fresh'}")
        print(f"  Bid/Ask:  {d.get('bid')}/{d.get('ask')}")
        print(f"  Open:     {d.get('position_open')}")
        print(f"  Today:    {d.get('signals_today')} signals  {d.get('entries_today')} entries  {d.get('exits_today')} exits")
        print(f"  Realized: ${d.get('realized_today_usd'):+.2f}")
    else:
        print("  ⚠️  Heartbeat file missing")

    # Today's trades
    print("\n📈 TODAY'S TRADES (from MT5 log)")
    trades = parse_today_trades()
    if not trades:
        print("  (none yet)")
    else:
        print(f"  {'open':<10} {'side':<6} {'price':<9} {'R':<6} {'close':<10} {'reason':<12} {'pnl':<8} {'peak':<8}")
        print("  " + "-" * 80)
        net = 0; wins = 0; losses = 0
        for t in trades:
            print(f"  {t['open_time']:<10} {t['side']:<6} {t['open_price']:<9.2f} ${t['r']:<5.2f} {t['close_time']:<10} {t['exit_reason']:<12} ${t['pnl']:<+7.2f} ${t['peak']:<+7.2f}")
            net += t['pnl']
            if t['pnl'] > 0: wins += 1
            elif t['pnl'] < 0: losses += 1
        n = wins + losses
        wr = wins/n*100 if n else 0
        print(f"\n  Today summary: {n} trades  {wins}W/{losses}L  WR {wr:.1f}%  Net ${net:+.2f}")

    # All-time v3.30 (since deploy ~05-12)
    print("\n📚 SINCE v3.30 DEPLOY (05-12)")
    files = sorted(LOGS.glob("20260512.log")) + sorted(LOGS.glob("20260513.log"))
    all_pnls = []
    for f in files:
        text = f.read_bytes().decode("utf-16-le", errors="replace")
        for ln in text.splitlines():
            if "UhvL2" not in ln or "net P&L:" not in ln: continue
            m = re.search(r"\$(-?\d+\.\d+)", ln)
            if m: all_pnls.append(float(m.group(1)))
    if all_pnls:
        w = sum(1 for p in all_pnls if p > 0)
        l = sum(1 for p in all_pnls if p < 0)
        net = sum(all_pnls)
        wr = w/(w+l)*100 if (w+l) else 0
        avg_w = statistics.mean([p for p in all_pnls if p > 0]) if w else 0
        avg_l = statistics.mean([p for p in all_pnls if p < 0]) if l else 0
        print(f"  Total: {len(all_pnls)} trades  {w}W/{l}L  WR {wr:.1f}%")
        print(f"  Net P&L: ${net:+.2f}")
        print(f"  Avg win: ${avg_w:+.2f}  Avg loss: ${avg_l:+.2f}")
        print(f"  Best: ${max(all_pnls):+.2f}  Worst: ${min(all_pnls):+.2f}")
    else:
        print("  (no v3.30 trades yet)")

    # Files committed
    print("\n📝 OVERNIGHT WORK (Python analysis in monitor/strategy_lab/)")
    print("  - multi_day_backtest.py    OHLC sim (limited by no tick data)")
    print("  - match_zee_feb11_tuner.py Grid search vs Zee's 20 entries")
    print("  - multi_day_entry_density.py  220-280 signals/day, uniform")
    print("  - signal_quality_scorer.py 17.8K-signal feature dataset")
    print("  - signal_filter_analysis.py  Bucket analysis by feature")
    print("  - signal_filter_combos.py  Stacked filter testing")
    print("  - ea_win_boundary.py       94.4% baseline WR measurement")
    print("  - filter_vs_zee_feb11.py   ⚠️ Filters BLOCK Zee's actual trades!")
    print("  - parse_mt5_logs.py        This log-parser")
    print("  - OVERNIGHT_SUMMARY.md     Full writeup")

    print("\n💡 KEY FINDINGS")
    print("  1. Quality filters reduce SL rate BUT block 14-17/20 of Zee's actual trades.")
    print("     → DO NOT add filters. v3.30 detector stays as-is.")
    print("  2. Mechanical loss-caps don't work on M1 XAU (noise hits any tight stop).")
    print("  3. Strategy fires consistently (220-280/day) — no quiet days to filter.")
    print("  4. Edge is in EXIT timing (your discretionary watching).")
    print("  5. ⚠️ DUAL-EA RACE: H1 chart has stale v1.00. Remove it.")

    print("\n🌅 MORNING ACTION CHECKLIST")
    print("  □ Right-click H1 chart → Expert Advisors → Remove (stale v1.00)")
    print("  □ Verify heartbeat now reads v3.30 cleanly")
    print("  □ Run MT5 Strategy Tester for 4-5 more days (decision quality)")
    print("  □ Decide: scale demo→real ($500 cap) if multi-day looks good")

    print()
    print("═" * 75)


if __name__ == "__main__":
    main()
