"""
parse_mt5_logs.py — parse MT5 daily logs to extract real EA trade events.

For each log file (YYYYMMDD.log, UTF-16 LE), extract:
  - SIGNAL events (entry detected, candidate to fire)
  - FILLED events (actual order fills with prices)
  - EXIT events (close reasons + P&L)
  - DEINIT/INIT events (which version was active)

Outputs:
  - Per-day count of fills + closes
  - Per-day net P&L (from [CLOSED] net P&L: $X lines)
  - Version-attribution (UhvL2 prefix = v3.30, UhvSweep prefix = v1.00)
"""
from __future__ import annotations
import os
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

LOGS_DIR = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "DBE9B8B347D025DD139E103EE3B63FD8" / "MQL5" / "Logs"


def parse_log(path: Path):
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-16-le")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    return text.splitlines()


def main():
    files = sorted(LOGS_DIR.glob("2026*.log"))
    print(f"Parsing {len(files)} daily logs.")
    print()

    per_day = {}
    for f in files:
        date_str = f.stem  # 20260513
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        lines = parse_log(f)
        # Track per-version stats
        v3_fills = 0; v3_closes = 0; v3_pnl = 0.0
        v1_fills = 0; v1_closes = 0; v1_pnl = 0.0
        v3_inits = 0; v1_inits = 0
        sl_hits = 0; peak_trails = 0; time_stops = 0
        other_exits = 0

        for ln in lines:
            if "UhvSweepExhaustion" not in ln: continue
            # Determine version by prefix
            is_v3 = "UhvL2 " in ln
            is_v1 = "UhvSweep " in ln and not is_v3

            if "[FILLED]" in ln:
                if is_v3: v3_fills += 1
                elif is_v1: v1_fills += 1
            elif "[CLOSED] net P&L:" in ln:
                m = re.search(r'\$(-?\d+\.\d+)', ln)
                if m:
                    pnl = float(m.group(1))
                    if is_v3:
                        v3_closes += 1; v3_pnl += pnl
                    elif is_v1:
                        v1_closes += 1; v1_pnl += pnl
            elif "[EXIT peak_trail]" in ln:
                peak_trails += 1
            elif "[EXIT time_stop]" in ln:
                time_stops += 1
            elif "[EXIT early_stop]" in ln or "[EXIT catastrophic]" in ln:
                other_exits += 1
            elif "[SIGNAL]" in ln and "BUY" not in ln and "SELL" not in ln:
                # Probably "[SIGNAL] BUY @ ..." → already counted
                pass
            elif "Init v3" in ln or "v3.30" in ln:
                v3_inits += 1
            elif "Init v" in ln or "[UhvSweep]" in ln and "version" in ln.lower():
                v1_inits += 1

        per_day[date_fmt] = {
            "v3_fills": v3_fills, "v3_closes": v3_closes, "v3_pnl": v3_pnl,
            "v1_fills": v1_fills, "v1_closes": v1_closes, "v1_pnl": v1_pnl,
            "peak_trails": peak_trails, "time_stops": time_stops, "other": other_exits,
            "v3_inits": v3_inits, "v1_inits": v1_inits,
        }

    # Print per-day breakdown
    print(f"{'date':<12} {'v3 fills':<9} {'v3 close':<9} {'v3 pnl':<10} {'v1 fills':<9} {'v1 close':<9} {'v1 pnl':<10} {'peakT':<7} {'tStop':<7}")
    print("-" * 110)
    total_v3_pnl = 0; total_v1_pnl = 0
    total_v3_closes = 0; total_v1_closes = 0
    for d in sorted(per_day):
        s = per_day[d]
        total_v3_pnl += s["v3_pnl"]; total_v3_closes += s["v3_closes"]
        total_v1_pnl += s["v1_pnl"]; total_v1_closes += s["v1_closes"]
        print(f"{d}   {s['v3_fills']:<9} {s['v3_closes']:<9} ${s['v3_pnl']:<+9.2f} {s['v1_fills']:<9} {s['v1_closes']:<9} ${s['v1_pnl']:<+9.2f} {s['peak_trails']:<7} {s['time_stops']:<7}")

    print()
    print(f"v3.30 totals: {total_v3_closes} closes  ${total_v3_pnl:+.2f}")
    print(f"v1.00 totals: {total_v1_closes} closes  ${total_v1_pnl:+.2f}")
    print(f"COMBINED: {total_v3_closes + total_v1_closes} closes  ${total_v3_pnl + total_v1_pnl:+.2f}")

    # Win rate from extract
    print()
    # We don't track W/L from this parse — would need to extract per-trade P&L
    # Let me extract that separately
    win_loss = {"v3": {"w":0,"l":0,"sum":0.0}, "v1": {"w":0,"l":0,"sum":0.0}}
    for f in files:
        for ln in parse_log(f):
            if "UhvSweepExhaustion" not in ln or "[CLOSED] net P&L:" not in ln: continue
            m = re.search(r'\$(-?\d+\.\d+)', ln)
            if not m: continue
            pnl = float(m.group(1))
            if "UhvL2 " in ln:
                bucket = win_loss["v3"]
            else:
                bucket = win_loss["v1"]
            bucket["sum"] += pnl
            if pnl > 0: bucket["w"] += 1
            elif pnl < 0: bucket["l"] += 1
    for ver, b in win_loss.items():
        n = b["w"] + b["l"]
        if n == 0: continue
        print(f"{ver.upper()}: {n} trades  W: {b['w']}  L: {b['l']}  WR: {b['w']/n*100:.1f}%  Net: ${b['sum']:+.2f}")


if __name__ == "__main__":
    main()
