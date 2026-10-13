"""Data feed for the claudezeeshan.com main page (dashboard/claude_trader/ea_dashboard.html).

    py monitor/ea_dashboard_data.py    -> prints one JSON object

Everything comes from evidence on this machine, read at request time:
  * which EAs are running: the live Axi terminal's own log (MQL5/Logs/<today>.log) - each EA prints an
    init line with its version, and ENTRY / EXIT lines for every trade
  * live performance: the EA's trade CSV in Common/Files (one row per closed trade) + open trades from
    the log (an ENTRY with no EXIT yet)
  * backtest receipts: MT5 Strategy Tester results recorded in VERSION_HISTORY.md / report.md (fixed numbers)
  * report.md and VERSION.md, rendered to HTML each time, so the page never goes stale"""
import csv, datetime as dt, json, re, sys
from pathlib import Path
import markdown

REPO = Path(__file__).resolve().parents[1]
TERM = Path.home() / "AppData/Roaming/MetaQuotes/Terminal/6FBEE76C719DC78AB2AE839B5A0C7442"
COMMON = Path.home() / "AppData/Roaming/MetaQuotes/Terminal/Common/Files"

# The EAs the page knows about. "tag" is how the EA names itself in the Experts log.
EAS = [
    {"key": "saad15", "name": "Saad 15-min", "file": "Saad_strategy_15min", "magic": 88302, "tag": "SAAD-15min",
     "chart": "XAUUSD.pro · M15 · Axi", "csv": "Saad15_trades_XAUUSD.pro_88302.csv",
     "what": "Buys and sells gold on 15-minute candles when a pin bar, marubozu or hammer forms on the 9 or 50 EMA and its high/low breaks. "
             "Stop 35 pips beyond the candle; half the trade is banked at the first target, the rest trails $2 behind the price.",
     "backtest": {"label": "MT5 Strategy Tester · Axi real ticks · 1 lot · $25k · Jan 6 – Oct 8 2026", "net": 202222, "pf": 1.60,
                  "wr": 61.3, "dd": 13422, "worst_day": -3806, "losing_months": 0, "trades": 867, "per_day": 6.3,
                  "holdout": 67681, "holdout_label": "Jul 1 – Oct 8 (months never used for tuning)"}},
    {"key": "pyr3", "name": "Saad 15-min + pyramiding", "file": "Saad_strategy_15min_pyramiding_max_3", "magic": 88330, "tag": "SAAD-PYR3",
     "chart": "XAUUSD.pro · M15 · Axi", "csv": "Saad15_trades_XAUUSD.pro_88330.csv",
     "what": "The same trades as Saad 15-min, but when a trade moves 0.25 × ATR in our favour it adds 0.75× more, up to 5 positions (about 3 lots). "
             "Bigger wins on trends, bigger losses on reversals.",
     "backtest": {"label": "MT5 Strategy Tester · Axi real ticks · base 1 lot · $25k · Jan 6 – Oct 8 2026", "net": 479815, "pf": 1.58,
                  "wr": 52.2, "dd": 41825, "worst_day": -12338, "losing_months": 0, "trades": 867, "per_day": 6.3,
                  "holdout": 159646, "holdout_label": "Jul 1 – Oct 8"}},
]


def read_log(day):
    f = TERM / "MQL5" / "Logs" / f"{day:%Y%m%d}.log"
    if not f.exists():
        return []
    try:
        return f.read_bytes().decode("utf-16", errors="ignore").splitlines()
    except Exception:
        return []


def num(x):
    try:
        return float(x)
    except Exception:
        return 0.0


def ea_state(ea, logs_by_day):
    st = {"running": False, "version": None, "last_seen": None, "open": [], "init_line": None}
    tag = ea["tag"]
    for day, lines in logs_by_day:
        for ln in lines:
            if f"[{tag}]" not in ln:
                continue
            parts = ln.split("\t")
            ts = f"{day:%Y-%m-%d} {parts[2][:8]}" if len(parts) > 2 else f"{day:%Y-%m-%d}"
            st["last_seen"] = ts
            m = re.search(rf"\[{re.escape(tag)}\] (v\d+\.\d+)", ln)
            if m:
                st["version"], st["init_line"] = m.group(1), ts
    # open trades: ENTRY #n with no later EXIT #n (in the latest session's numbering)
    entries, exits = {}, set()
    for day, lines in logs_by_day:
        for ln in lines:
            if f"[{tag}] ENTRY #" in ln:
                m = re.search(r"ENTRY #(\d+) (BUY|SELL) ([\d.]+) lots @ ([\d.]+) \| SL ([\d.]+) \(risk \$([\d.]+)\)", ln)
                if m: entries[m.group(1)] = {"num": int(m.group(1)), "side": m.group(2), "lots": num(m.group(3)), "entry": num(m.group(4)),
                                             "sl": num(m.group(5)), "risk": num(m.group(6)), "time": f"{day:%Y-%m-%d} " + ln.split("\t")[2][:8]}
            elif f"[{tag}] EXIT #" in ln:
                m = re.search(r"EXIT #(\d+)", ln)
                if m: exits.add(m.group(1))
            elif f"[{tag}] v" in ln:                       # a fresh attach restarts the numbering
                entries, exits = {}, set()
    st["open"] = [e for k, e in entries.items() if k not in exits]
    if st["last_seen"]:
        last = dt.datetime.strptime(st["last_seen"][:19], "%Y-%m-%d %H:%M:%S") if len(st["last_seen"]) > 10 else None
        st["running"] = last is not None and (dt.datetime.now() - last).total_seconds() < 36 * 3600
    return st


def live_stats(ea):
    f = COMMON / ea["csv"]
    rows = []
    if f.exists():
        with f.open(encoding="utf-8", errors="ignore") as fh:
            for r in csv.DictReader(fh):
                if r.get("num") == "num" or not r.get("exit_time"):
                    continue
                rows.append(r)
    nets = [num(r["net"]) for r in rows]
    today = dt.date.today().strftime("%Y.%m.%d")
    by_day = {}
    for r in rows:
        by_day.setdefault(r["exit_time"][:10], 0.0)
        by_day[r["exit_time"][:10]] += num(r["net"])
    trades = [{"side": r["side"], "entry_time": r["entry_time"], "entry": num(r["entry"]), "exit_time": r["exit_time"],
               "exit": num(r["exit"]), "reason": r["exit_reason"], "net": num(r["net"]), "setup": r.get("setup", "")} for r in rows]
    return {"trades": len(nets), "wins": sum(n > 0 for n in nets), "losses": sum(n <= 0 for n in nets),
            "net": round(sum(nets), 2), "win_rate": round(100 * sum(n > 0 for n in nets) / len(nets), 1) if nets else None,
            "best": max(nets) if nets else None, "worst": min(nets) if nets else None,
            "today": round(by_day.get(today, 0.0), 2), "days": [{"day": k, "net": round(v, 2)} for k, v in sorted(by_day.items())],
            "recent": trades[-12:][::-1], "source": str(f.name), "first": rows[0]["entry_time"] if rows else None}


def md_html(path):
    p = REPO / path
    if not p.exists():
        return f"<p>{path} not found</p>", None
    src = p.read_text(encoding="utf-8")
    html = markdown.markdown(src, extensions=["tables", "fenced_code", "sane_lists"])
    html = html.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
    return html, dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def main():
    now = dt.datetime.now()
    logs = [(d, read_log(d)) for d in (now.date() - dt.timedelta(days=1), now.date())]
    eas = []
    for ea in EAS:
        e = {k: v for k, v in ea.items()}
        e["state"] = ea_state(ea, logs)
        e["live"] = live_stats(ea)
        eas.append(e)
    report_html, report_at = md_html("report.md")
    versions_html, versions_at = md_html("VERSION.md")
    print(json.dumps({"generated": now.strftime("%Y-%m-%d %H:%M:%S"), "eas": eas,
                      "report_html": report_html, "report_updated": report_at,
                      "versions_html": versions_html, "versions_updated": versions_at}))


if __name__ == "__main__":
    main()
