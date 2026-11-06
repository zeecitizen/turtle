"""
Main-Trade Exit Rule R:R Backtest (2026-05-05 night)

Question: would different exit rules (TP/SL/Trail variants) shift our main trades
from net-drag to net-positive while improving R:R toward 1.5:1?

Method:
  1. Parse every "MAIN OPENED ticket=X" event from EA logs (May 1-5)
     plus the implicit OPENING MAIN <DIR> X.XX lots <SYM> @ <PRICE> entry price.
  2. For each main, walk the tick CSV from entry timestamp forward,
     simulating candidate exit configurations independently.
  3. Aggregate per-variant: total P&L, WR, avg win/loss, R:R, max single loss.

Source data:
  EA logs:    %APPDATA%\\...\\MQL5\\Logs\\YYYYMMDD.log (UTF-16 LE)
  Tick CSVs:  %COMMON%\\Files\\shano_ticks_YYYY-MM-DD.csv
"""
import re
import csv
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

LOG_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs")
TICKS_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
OPEN_LOG = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_open_log.csv")
REPORT_PATH = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\MAIN_EXIT_RR_REPORT.md")

DOLLAR_PER_PT_PER_LOT = 100.0   # XAUUSD: 1 lot = 100 oz, $1 price move = $100 PnL
SLIP_COST_PER_TRADE = 1.0       # round-trip slip+spread cost ($)
WINDOW_SEC = 600                # 10-min window (most mains close <5min anyway)
LOG_TO_BROKER_OFFSET_HOURS = 1  # EA log uses local PC time (Berlin); tick CSV uses broker (UTC+3)


# ─── Historical main extraction ────────────────────────────────────────────

def parse_mains_from_log(log_path):
    """Extract every main trade from EA log: open ts/dir/lots/price + close ts/reason/pnl."""
    raw = log_path.read_bytes().replace(b"\x00", b"").decode("utf-8", errors="ignore")
    lines = raw.splitlines()

    # Map ticket -> opening info
    opens = {}
    closes = {}

    pending_entry = None  # "OPENING MAIN <DIR>" then next line "MAIN OPENED ticket=X"

    for line in lines:
        m_ts = re.search(r"(\d{2}:\d{2}:\d{2})", line[:50])
        if not m_ts:
            continue
        ts_str = m_ts.group(1)

        # OPENING MAIN <BUY|SELL> X.XX lots <SYM> @ PRICE (probe=N)
        m_open = re.search(r"OPENING MAIN (BUY|SELL) ([\d.]+) lots \w+ @ ([\d.]+) \(probe=(\d+)\)", line)
        if m_open:
            pending_entry = {"ts": ts_str, "dir": m_open.group(1).lower(),
                             "lots": float(m_open.group(2)), "price": float(m_open.group(3)),
                             "probe_ticket": m_open.group(4)}
            continue

        # MAIN OPENED ticket=X deal=Y | Z lots | burst=A/B | TYPE  (first-main path)
        m_opened = re.search(r"MAIN OPENED ticket=(\d+) deal=\d+ \| ([\d.]+) lots \| burst=(\d+)/\d+ \| (\w+)", line)
        if m_opened and pending_entry:
            tk = m_opened.group(1)
            opens[tk] = {
                "ts_str": pending_entry["ts"],
                "dir": pending_entry["dir"],
                "lots": float(m_opened.group(2)),
                "entry": pending_entry["price"],
                "burst_idx": int(m_opened.group(3)),
                "type": m_opened.group(4),
                "probe_ticket": pending_entry["probe_ticket"],
            }
            pending_entry = None
            continue

        # MACHINE GUN OPENED ticket=X | <DIR> Y.YY lots | burst=A/B  (burst-main path)
        m_mg = re.search(r"MACHINE GUN OPENED ticket=(\d+) \| (BUY|SELL) ([\d.]+) lots \| burst=(\d+)/\d+", line)
        if m_mg:
            tk = m_mg.group(1)
            # Burst entry price comes from "MACHINE GUN BUY/SELL @ PRICE" preceding line — try to find it
            opens[tk] = {
                "ts_str": ts_str,
                "dir": m_mg.group(2).lower(),
                "lots": float(m_mg.group(3)),
                "entry": None,  # will be filled from preceding line if available
                "burst_idx": int(m_mg.group(4)),
                "type": "BURST",
                "probe_ticket": None,
            }
            continue

        # Capture entry price from "OPENING MAIN..." OR similar burst-open lines
        m_burst_open = re.search(r"OPENING (?:BURST|MACHINE GUN) (BUY|SELL) ([\d.]+) lots \w+ @ ([\d.]+)", line)
        if m_burst_open:
            # Will associate with the next MACHINE GUN OPENED line (no probe ticket here)
            pending_entry = {"ts": ts_str, "dir": m_burst_open.group(1).lower(),
                             "lots": float(m_burst_open.group(2)), "price": float(m_burst_open.group(3)),
                             "probe_ticket": None}
            continue

        # CLOSED ticket=X | <REASON_TEXT> | $PNL
        m_close = re.search(r"CLOSED ticket=(\d+).*?\|\s*\$(-?[\d.]+)\s*$", line)
        if m_close:
            tk = m_close.group(1)
            # Avoid recording probe closures here (small lots), but include burst-mains
            if tk in opens and opens[tk]["lots"] >= 0.05:
                # Reason: text between first | and last |
                reason_match = re.search(r"CLOSED ticket=\d+ \| (.+) \|\s*\$", line)
                reason = reason_match.group(1)[:60] if reason_match else "unknown"
                closes[tk] = {"ts_str": ts_str, "actual_pnl": float(m_close.group(2)),
                              "actual_reason": reason}
            continue

    # Stitch open + close
    mains = []
    for tk, op in opens.items():
        if tk not in closes:
            continue
        if op["entry"] is None:
            continue  # skip mains without parseable entry price
        mains.append({
            "ticket": tk,
            "open_ts_str": op["ts_str"],
            "close_ts_str": closes[tk]["ts_str"],
            "dir": op["dir"],
            "lots": op["lots"],
            "entry": op["entry"],
            "burst_idx": op["burst_idx"],
            "type": op["type"],
            "actual_pnl": closes[tk]["actual_pnl"],
            "actual_reason": closes[tk]["actual_reason"],
        })
    return mains


def load_ticks(date_str):
    f = TICKS_DIR / f"shano_ticks_{date_str}.csv"
    if not f.exists():
        return []
    ticks = []
    with f.open("r", encoding="utf-8", errors="ignore") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            try:
                ticks.append((datetime.strptime(row[0], "%Y.%m.%d %H:%M:%S"), float(row[2]), float(row[3])))
            except (ValueError, IndexError):
                continue
    return ticks


def find_tick_idx(ticks, target_ts):
    lo, hi = 0, len(ticks) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if ticks[mid][0] < target_ts:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo < len(ticks) and ticks[lo][0] >= target_ts else None


# ─── Exit-rule simulators ──────────────────────────────────────────────────

def simulate_exit_config(ticks, start_idx, direction, entry_price, lots, config):
    """Apply a single exit configuration, return (reason, pnl, age_sec, peak)."""
    if start_idx is None or start_idx >= len(ticks):
        return ("no_data", 0.0, 0, 0.0)

    dollar_per_pt = lots * DOLLAR_PER_PT_PER_LOT
    start_ts = ticks[start_idx][0]
    end_ts = start_ts + timedelta(seconds=WINDOW_SEC)
    peak_pnl = 0.0
    pnl = 0.0
    age = 0

    for i in range(start_idx, len(ticks)):
        ts, bid, ask = ticks[i]
        if ts > end_ts:
            cur = bid if direction == "buy" else ask
            move_pts = (cur - entry_price) if direction == "buy" else (entry_price - cur)
            return ("window_end", move_pts * dollar_per_pt - SLIP_COST_PER_TRADE, age, peak_pnl)

        cur = bid if direction == "buy" else ask
        move_pts = (cur - entry_price) if direction == "buy" else (entry_price - cur)
        pnl = move_pts * dollar_per_pt - SLIP_COST_PER_TRADE
        peak_pnl = max(peak_pnl, pnl)
        age = int((ts - start_ts).total_seconds())

        # Optional fixed TP
        if config.get("tp") and pnl >= config["tp"]:
            return ("tp", config["tp"], age, peak_pnl)
        # Optional fixed SL
        if config.get("sl") and pnl <= -config["sl"]:
            return ("sl", -config["sl"], age, peak_pnl)
        # Optional trail
        if config.get("trail_trig") and peak_pnl >= config["trail_trig"]:
            if (peak_pnl - pnl) >= config["trail_drop"]:
                return ("trail", peak_pnl - config["trail_drop"], age, peak_pnl)
        # Optional fearIdeal (catastrophic stop)
        if config.get("fear") and pnl <= -config["fear"]:
            return ("fear", -config["fear"], age, peak_pnl)
        # Optional no-green timeout
        if config.get("no_green_sec") and age >= config["no_green_sec"]:
            if peak_pnl < config.get("no_green_peak", 3.0) and pnl < 0:
                return ("no_green", pnl, age, peak_pnl)

    return ("eod", pnl, age, peak_pnl)


# ─── Variant configurations ───────────────────────────────────────────────

VARIANTS = {
    "current_live": {  # what the EA does NOW
        "trail_trig": 25.0, "trail_drop": 8.0, "fear": 60.0,
        "no_green_sec": 60, "no_green_peak": 3.0,
    },
    "current_old": {  # what was running yesterday (fearIdeal=$100)
        "trail_trig": 25.0, "trail_drop": 8.0, "fear": 100.0,
    },
    "trail_25_5":   { "trail_trig": 25.0, "trail_drop": 5.0, "fear": 60.0 },  # same trig, tighter drop
    "trail_22_6":   { "trail_trig": 22.0, "trail_drop": 6.0, "fear": 60.0 },  # slight conservative tighten
    "trail_22_5":   { "trail_trig": 22.0, "trail_drop": 5.0, "fear": 60.0 },
    "trail_20_5":   { "trail_trig": 20.0, "trail_drop": 5.0, "fear": 60.0 },  # aggressive
    "trail_18_4":   { "trail_trig": 18.0, "trail_drop": 4.0, "fear": 60.0 },  # very aggressive
    "trail_50_10":  { "trail_trig": 50.0, "trail_drop": 10.0, "fear": 60.0 },
    "trail_40_8":   { "trail_trig": 40.0, "trail_drop": 8.0, "fear": 60.0 },
    "tp90_sl60": {  # cousin's 1.5:1 R:R
        "tp": 90.0, "sl": 60.0,
    },
    "tp60_sl40": {  # 1.5:1 but smaller
        "tp": 60.0, "sl": 40.0,
    },
    "tp45_sl30": {  # tight 1.5:1
        "tp": 45.0, "sl": 30.0,
    },
    "tp120_sl60": {  # 2:1 R:R
        "tp": 120.0, "sl": 60.0,
    },
    "hybrid_tp50_then_trail": {  # bank $50, then trail rest
        "tp": 50.0, "sl": 60.0, "trail_trig": 50.0, "trail_drop": 5.0,
    },
}


# ─── Run backtest ──────────────────────────────────────────────────────────

def parse_open_log_csv():
    """shano_open_log.csv has entry prices + slip for every main since EA hot-tracks fills.
    Format: send_ts,fill_ts,latency_us,ticket,symbol,direction,lots,intended_bid,intended_ask,
            intended_price,actual_fill,slip_pts,is_burst,comment
    """
    if not OPEN_LOG.exists():
        return []
    mains = []
    with OPEN_LOG.open("r", encoding="utf-8", errors="ignore") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                send_ts = datetime.strptime(row["send_ts"], "%Y.%m.%d %H:%M:%S")
                date_str = send_ts.strftime("%Y-%m-%d")
                mains.append({
                    "ticket": row["ticket"],
                    "open_ts_str": send_ts.strftime("%H:%M:%S"),  # broker time already
                    "date": date_str,
                    "dir": row["direction"].lower(),
                    "lots": float(row["lots"]),
                    "entry": float(row["actual_fill"]),  # actual broker fill
                    "burst_idx": 1 if row["is_burst"] == "FIRST" else 2,
                    "type": row["is_burst"],
                    "actual_pnl": None,  # not in this CSV
                    "actual_reason": "",
                    "slip_pts": float(row["slip_pts"]),
                    "is_broker_time": True,  # CSV is broker time, no offset needed
                })
            except (ValueError, KeyError):
                continue
    return mains


def main():
    dates = ["2026-04-30", "2026-05-01", "2026-05-04", "2026-05-05"]

    # Primary source: shano_open_log.csv (actual fills, all 6 mains incl bursts)
    all_mains = parse_open_log_csv()

    # Fallback / supplement: parse from EA logs for days NOT in open log
    csv_dates = {m["date"] for m in all_mains}
    for d in dates:
        if d in csv_dates:
            continue
        log_date = d.replace("-", "")
        log_path = LOG_DIR / f"{log_date}.log"
        if not log_path.exists():
            continue
        for m in parse_mains_from_log(log_path):
            m["date"] = d
            m["is_broker_time"] = False  # EA log uses local time
            all_mains.append(m)

    if not all_mains:
        print("No historical mains found in logs. Exiting.")
        return

    print(f"Found {len(all_mains)} historical mains across {len(dates)} days\n")
    for m in all_mains:
        actual_str = f"actual ${m['actual_pnl']:+.2f}" if m.get('actual_pnl') is not None else "actual unknown"
        print(f"  {m['date']} {m['open_ts_str']} {m['dir']:>4} "
              f"{m['lots']:.2f}lot @{m['entry']:.2f} -> {actual_str}")
    print()

    # Pre-load ticks
    ticks_by_date = {d: load_ticks(d) for d in dates}

    # Run each variant
    print(f"{'Variant':<28} {'Trades':>7} {'Wins':>5} {'Loss':>5} {'WR%':>6} "
          f"{'AvgW':>7} {'AvgL':>7} {'R:R':>5} {'MaxDD':>8} {'Net P&L':>10}")
    print("-" * 100)

    variant_results = {}
    for var_name, cfg in VARIANTS.items():
        trades = []
        for m in all_mains:
            ticks = ticks_by_date.get(m["date"], [])
            if not ticks:
                continue
            tick_date = ticks[0][0].date()
            try:
                t_only = datetime.strptime(m["open_ts_str"], "%H:%M:%S").time()
                ts_base = datetime.combine(tick_date, t_only)
                # CSV-sourced mains are already broker time; EA-log mains need +1h
                ts = ts_base if m.get("is_broker_time") else ts_base + timedelta(hours=LOG_TO_BROKER_OFFSET_HOURS)
            except ValueError:
                continue
            idx = find_tick_idx(ticks, ts)
            if idx is None:
                continue
            reason, pnl, age, peak = simulate_exit_config(ticks, idx, m["dir"], m["entry"], m["lots"], cfg)
            trades.append({
                "main": m, "reason": reason, "pnl": round(pnl, 2),
                "age_sec": age, "peak": round(peak, 2),
            })

        wins = [t["pnl"] for t in trades if t["pnl"] > 0]
        losses = [t["pnl"] for t in trades if t["pnl"] < 0]
        wr = (100.0 * len(wins) / len(trades)) if trades else 0
        avg_w = sum(wins)/len(wins) if wins else 0
        avg_l = sum(losses)/len(losses) if losses else 0
        rr = (avg_w / abs(avg_l)) if avg_l else 0
        max_dd = min(losses) if losses else 0
        net = sum(t["pnl"] for t in trades)
        variant_results[var_name] = {"trades": trades, "wins": len(wins), "losses": len(losses),
                                       "wr": wr, "avg_w": avg_w, "avg_l": avg_l, "rr": rr,
                                       "max_dd": max_dd, "net": net}
        print(f"{var_name:<28} {len(trades):>7} {len(wins):>5} {len(losses):>5} "
              f"{wr:>5.1f}% ${avg_w:>+6.2f} ${avg_l:>+6.2f} {rr:>4.2f} "
              f"${max_dd:>+7.2f} ${net:>+9.2f}")

    # Per-trade detail for top 3 variants by net P&L
    print()
    top3 = sorted(variant_results.items(), key=lambda kv: kv[1]["net"], reverse=True)[:3]
    for name, r in top3:
        print(f"\n=== {name}: ${r['net']:+.2f} net ({len(r['trades'])} trades, {r['wr']:.1f}% WR) ===")
        for t in r["trades"]:
            m = t["main"]
            print(f"  {m['date']} {m['open_ts_str']}  {m['dir']:>4} {m['lots']:.2f}lot "
                  f"@{m['entry']:.2f} -> ${t['pnl']:+8.2f}  ({t['reason']:>10}, {t['age_sec']:>3}s, peak ${t['peak']:+.2f})")

    # Decision
    current_net = variant_results.get("current_live", {}).get("net", 0)
    print(f"\nBaseline current_live net: ${current_net:+.2f}")
    print(f"\nVariants beating current_live by >$30:")
    for name, r in sorted(variant_results.items(), key=lambda kv: kv[1]["net"], reverse=True):
        if r["net"] > current_net + 30 and r["wr"] >= 50 and len(r["trades"]) >= 5:
            improvement = r["net"] - current_net
            print(f"  +${improvement:.2f} : {name} (net ${r['net']:+.2f}, {r['wr']:.1f}% WR, R:R {r['rr']:.2f})")

    # Write report
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        f.write(f"# Main-Trade Exit Rule R:R Backtest\n\n")
        f.write(f"Run: {datetime.now().isoformat(timespec='minutes')}\n")
        f.write(f"Sample: {len(all_mains)} historical mains across {len([d for d in dates if any(m['date']==d for m in all_mains)])} days.\n\n")
        f.write(f"## Variant comparison\n\n")
        f.write(f"| Variant | Trades | Wins | Loss | WR% | Avg Win | Avg Loss | R:R | Max Loss | Net P&L |\n")
        f.write(f"|---|---|---|---|---|---|---|---|---|---|\n")
        for name, r in sorted(variant_results.items(), key=lambda kv: kv[1]["net"], reverse=True):
            f.write(f"| {name} | {len(r['trades'])} | {r['wins']} | {r['losses']} | "
                    f"{r['wr']:.1f}% | ${r['avg_w']:+.2f} | ${r['avg_l']:+.2f} | {r['rr']:.2f} | "
                    f"${r['max_dd']:+.2f} | **${r['net']:+.2f}** |\n")
        f.write("\n## Per-trade detail (top 3 variants)\n\n")
        for name, r in top3:
            f.write(f"### {name} (${r['net']:+.2f} net)\n\n")
            for t in r["trades"]:
                m = t["main"]
                f.write(f"- {m['date']} {m['open_ts_str']}  **{m['dir']}** {m['lots']:.2f}lot "
                        f"@{m['entry']:.2f} -> ${t['pnl']:+.2f}  ({t['reason']}, {t['age_sec']}s, peak ${t['peak']:+.2f})\n")
            f.write("\n")
    print(f"\nReport written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
