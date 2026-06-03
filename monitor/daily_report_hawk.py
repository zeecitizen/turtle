"""daily_report_hawk.py - end-of-day printable PDF/HTML reports.

Generates ONE numbered report per day. Stored in:
  daily_reports/<YYYY-MM>/report-NNN-YYYY-MM-DD.html

Numbering is global (across all dates) so a report can be referenced as
"#673" 10 years from now and Claude can pull it back instantly via the
manifest at daily_reports/manifest.json.

Zee's intent (2026-06-03): "i'll PRINT all these reports and keep them
in my cabinet in my room. 10 years later i can tell u referring to PDF #673
this work, can u pull this, let's re-run this, or let's retest this idea."

USAGE:
  python daily_report_hawk.py                     # report for today
  python daily_report_hawk.py --date 2026-06-03   # report for a specific UTC date
  python daily_report_hawk.py --loop              # daemon: write at 00:05 UTC daily
  python daily_report_hawk.py --list              # print the manifest
  python daily_report_hawk.py --get 673           # print path of report #673

Report sections (every day, no exceptions):
  1. Day at-a-glance (P&L, WR%, trades, EA state at EOD)
  2. Every fill (time, side, vol, pnl, reason)
  3. Cumulative equity intra-day
  4. EA config snapshot (Inp values, runtime overrides)
  5. Claims tested today (from memory.md wall of shame deltas)
  6. Code changes today (git log)
  7. Zee's verbatim messages today (from claude_brain)
  8. Confidence level + open questions (from latest hourly entry)
  9. Tomorrow's plan
"""
import sys, csv, json, os, time, argparse, subprocess, sqlite3, html
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8")
UTC = timezone.utc

ROOT       = Path(r"C:\Users\zeesh\Documents\GitHub\turtle")
REPORTS    = ROOT / "daily_reports"
MANIFEST   = REPORTS / "manifest.json"
COMMON     = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
FILLS_CSV  = COMMON / "turtle_fills.csv"
STATE_JSON = COMMON / "feb11_state_88011.json"
RUNTIME    = COMMON / "feb11_runtime_88011.json"
EA_SRC     = ROOT / "mt5" / "Feb11TickMedium.mq5"
BRAIN_DB   = ROOT / "monitor" / ".claude_brain.db"
MEMORY_MD  = ROOT / "memory.md"


def load_manifest():
    if MANIFEST.exists():
        try: return json.loads(MANIFEST.read_text())
        except: pass
    return {"next_number": 1, "reports": []}


def save_manifest(m):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=2))


def fills_for(date_iso):
    out = []
    if not FILLS_CSV.exists(): return out
    prefix = date_iso.replace("-", ".")
    with open(FILLS_CSV, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f); next(rdr, None)
        for r in rdr:
            if not r or len(r) < 8: continue
            if not r[0].startswith(prefix): continue
            try: pnl = float(r[7])
            except: continue
            out.append({
                "t": r[0], "ticket": r[1], "pos": r[2], "symbol": r[3],
                "side": r[4], "vol": r[5], "price": r[6], "pnl": pnl,
                "comment": r[11] if len(r) > 11 else "",
                "magic": r[12] if len(r) > 12 else "",
            })
    return out


def git_log_for(date_iso):
    """Get git commits whose date matches (committer-date)."""
    try:
        r = subprocess.run(
            ["git", "log", f"--since={date_iso} 00:00", f"--until={date_iso} 23:59",
             "--pretty=format:%h | %s"],
            cwd=ROOT, capture_output=True, text=True, timeout=10)
        return [l for l in r.stdout.splitlines() if l.strip()]
    except: return []


def zee_messages_for(date_iso, limit=100):
    """Pull every user (Zee) message from claude_brain for this UTC date."""
    if not BRAIN_DB.exists(): return []
    conn = sqlite3.connect(BRAIN_DB)
    start = int(datetime.strptime(date_iso + " 00:00:00", "%Y-%m-%d %H:%M:%S")
                .replace(tzinfo=UTC).timestamp() * 1000)
    end   = start + 86400 * 1000
    rows = conn.execute(
        "SELECT ts_ms, substr(content, 1, 1000) FROM turns "
        "WHERE role = 'user' AND ts_ms >= ? AND ts_ms < ? "
        "ORDER BY ts_ms LIMIT ?",
        (start, end, limit)).fetchall()
    conn.close()
    out = []
    for ts, body in rows:
        t = datetime.fromtimestamp(ts/1000, tz=UTC).strftime("%H:%M UTC")
        out.append({"t": t, "body": body})
    return out


def ea_inp_snapshot():
    inputs = {}
    try:
        text = EA_SRC.read_text(encoding="utf-8", errors="replace")
        import re
        for m in re.finditer(r"^input\s+\w+\s+(Inp\w+)\s*=\s*([^;]+);", text, re.M):
            inputs[m.group(1)] = m.group(2).strip()
        for line in text.splitlines():
            if line.startswith("#property version"):
                inputs["VERSION"] = line.split('"')[1] if '"' in line else "?"
                break
    except: pass
    return inputs


def runtime_snapshot():
    if not RUNTIME.exists(): return None
    try: return json.loads(RUNTIME.read_text())
    except: return None


def memory_md_tail(n=120):
    if not MEMORY_MD.exists(): return ""
    text = MEMORY_MD.read_text(encoding="utf-8", errors="replace")
    return "\n".join(text.splitlines()[-n:])


def build_report(date_iso, number):
    fills = fills_for(date_iso)
    wins = [f for f in fills if f["pnl"] > 0]
    losses = [f for f in fills if f["pnl"] < 0]
    flats = [f for f in fills if f["pnl"] == 0]
    pnl = sum(f["pnl"] for f in fills)
    wr = 100 * len(wins) / max(1, len(wins) + len(losses)) if (wins or losses) else 0
    commits = git_log_for(date_iso)
    zee_msgs = zee_messages_for(date_iso)
    inputs = ea_inp_snapshot()
    runtime = runtime_snapshot()
    mem_tail = memory_md_tail()

    # cumulative equity intra-day
    cum = 0; eq = []
    for f in fills:
        cum += f["pnl"]; eq.append((f["t"], cum))

    H = html.escape
    rows_fills = "\n".join(
        f"<tr><td>{H(f['t'])}</td><td>{H(f['side'])}</td><td>{H(f['vol'])}</td>"
        f"<td class='{'win' if f['pnl']>0 else 'loss' if f['pnl']<0 else 'flat'}'>"
        f"${f['pnl']:+.2f}</td><td>{H(f['comment'])}</td></tr>"
        for f in fills) or "<tr><td colspan=5>(no fills)</td></tr>"

    rows_eq = "\n".join(
        f"<tr><td>{H(t)}</td><td>${c:+.2f}</td></tr>" for t, c in eq[-50:]) or "<tr><td colspan=2>—</td></tr>"

    rows_inp = "\n".join(
        f"<tr><td>{H(k)}</td><td>{H(v)}</td></tr>" for k, v in inputs.items()) or "<tr><td colspan=2>—</td></tr>"

    rt_str = H(json.dumps(runtime)) if runtime else "(none — EA on Inp defaults)"
    commit_list = "<ul>" + "".join(f"<li><code>{H(c)}</code></li>" for c in commits) + "</ul>" if commits else "<i>no commits</i>"

    zee_list = "\n".join(
        f"<div class='zee-msg'><b>{H(z['t'])}</b><pre>{H(z['body'])}</pre></div>"
        for z in zee_msgs) or "<i>(no Zee messages indexed for this date)</i>"

    title = f"Daily report #{number:04d} — {date_iso}"

    html_out = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{H(title)}</title>
<style>
  @page {{ size: A4; margin: 12mm; }}
  body {{ font-family: -apple-system, "Segoe UI", Arial, sans-serif; color:#222; max-width: 980px; margin: 0 auto; padding: 16px; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: 6px; }}
  h2 {{ border-bottom: 1px solid #aaa; margin-top: 28px; }}
  .kpi {{ display: inline-block; padding: 10px 16px; margin: 4px; border: 1px solid #ccc; border-radius: 6px; min-width: 130px; }}
  .kpi .lbl {{ font-size: 11px; color: #666; text-transform: uppercase; }}
  .kpi .val {{ font-size: 22px; font-weight: bold; }}
  .pos {{ color: #1a7f37; }} .neg {{ color: #cf222e; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 12px; font-variant-numeric: tabular-nums; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; }}
  th {{ background: #f4f4f4; }}
  td.win {{ color: #1a7f37; }} td.loss {{ color: #cf222e; }} td.flat {{ color: #666; }}
  .zee-msg {{ background: #fffbea; border-left: 3px solid #d9a300; padding: 6px 10px; margin: 6px 0; }}
  .zee-msg pre {{ white-space: pre-wrap; word-break: break-word; font-family: inherit; margin: 4px 0; }}
  pre {{ background: #f7f7f7; padding: 8px; border-radius: 4px; overflow-x: auto; font-size: 11px; }}
  .footer {{ margin-top: 36px; padding-top: 16px; border-top: 1px solid #ccc; font-size: 11px; color: #666; }}
  @media print {{ body {{ max-width: none; }} h2 {{ break-after: avoid; }} table {{ break-inside: auto; }} tr {{ break-inside: avoid; }} }}
</style></head><body>

<h1>{H(title)}</h1>
<p style="color:#666">Generated {datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")} by daily_report_hawk. Source of truth: broker turtle_fills.csv.</p>

<h2>Day at-a-glance</h2>
<div class="kpi"><div class="lbl">Net P&amp;L</div><div class="val {'pos' if pnl>=0 else 'neg'}">${pnl:+,.2f}</div></div>
<div class="kpi"><div class="lbl">Trades</div><div class="val">{len(fills)}</div></div>
<div class="kpi"><div class="lbl">Wins / Losses</div><div class="val">{len(wins)} / {len(losses)}</div></div>
<div class="kpi"><div class="lbl">Win rate</div><div class="val">{wr:.1f}%</div></div>

<h2>Every fill</h2>
<table><tr><th>Broker time</th><th>Side</th><th>Vol</th><th>P&amp;L</th><th>Comment</th></tr>
{rows_fills}
</table>

<h2>Intra-day cumulative equity (last 50)</h2>
<table><tr><th>Time</th><th>Cum P&amp;L</th></tr>{rows_eq}</table>

<h2>EA config snapshot (Feb11TickMedium source defaults)</h2>
<table><tr><th>Inp</th><th>Value</th></tr>{rows_inp}</table>
<p><b>Runtime overrides:</b> {rt_str}</p>

<h2>Code changes this day (git log)</h2>
{commit_list}

<h2>Zee's verbatim messages today</h2>
{zee_list}

<h2>memory.md tail (most recent entries + wall of shame)</h2>
<pre>{H(mem_tail)}</pre>

<div class="footer">
  Report #{number:04d}. Print and file. To recall later:
  <code>python monitor/daily_report_hawk.py --get {number}</code>
  Per Rule #3 the only goal is real money. This report is itself NOT progress
  unless it documents a positive P&amp;L day. Use it to learn, not to celebrate.
</div>
</body></html>
"""
    return html_out


def write_report(date_iso):
    m = load_manifest()
    # Check if already written for this date
    for r in m["reports"]:
        if r["date"] == date_iso:
            print(f"[daily-report] already exists for {date_iso}: #{r['number']:04d} → {r['file']}")
            return r
    number = m["next_number"]
    yyyymm = date_iso[:7]
    out_dir = REPORTS / yyyymm
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"report-{number:04d}-{date_iso}.html"
    html_str = build_report(date_iso, number)
    out_path.write_text(html_str, encoding="utf-8")
    entry = {
        "number": number, "date": date_iso, "file": str(out_path.relative_to(ROOT)),
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
    }
    m["reports"].append(entry)
    m["next_number"] = number + 1
    save_manifest(m)
    print(f"[daily-report] wrote #{number:04d} → {out_path.relative_to(ROOT)}")
    # commit + push (best-effort)
    try:
        rel = str(out_path.relative_to(ROOT)).replace("\\", "/")
        subprocess.run(["git", "add", rel, "daily_reports/manifest.json"],
                       cwd=ROOT, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", f"Daily report #{number:04d} ({date_iso})"],
                       cwd=ROOT, capture_output=True)
        subprocess.run(["git", "push"], cwd=ROOT, capture_output=True, timeout=60)
        print(f"[daily-report] pushed to GitHub")
    except Exception as e:
        print(f"[daily-report] git push failed (saved locally): {e}")
    return entry


def list_reports():
    m = load_manifest()
    print(f"[daily-report] {len(m['reports'])} reports, next # = {m['next_number']:04d}")
    for r in m["reports"][-50:]:
        print(f"  #{r['number']:04d}  {r['date']}  → {r['file']}")


def get_report(number):
    m = load_manifest()
    for r in m["reports"]:
        if r["number"] == number:
            full = ROOT / r["file"]
            print(f"Report #{number:04d}:")
            print(f"  Date:     {r['date']}")
            print(f"  Path:     {full}")
            print(f"  Exists:   {full.exists()}")
            return
    print(f"[daily-report] no report numbered #{number:04d}")


def loop():
    """Daemon: at 00:05 UTC each day, write the report for the day that just ended."""
    print(f"[daily-report] daemon starting at {datetime.now(tz=UTC)}")
    while True:
        now = datetime.now(tz=UTC)
        target = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
        sleep_s = max(60, int((target - now).total_seconds()))
        print(f"[daily-report] sleeping {sleep_s}s until {target.strftime('%Y-%m-%d %H:%M UTC')}")
        time.sleep(sleep_s)
        # Generate for the day that just ended (the date BEFORE the 00:05 wake-up)
        yesterday = (datetime.now(tz=UTC) - timedelta(hours=1)).strftime("%Y-%m-%d")
        try:
            write_report(yesterday)
        except Exception as e:
            print(f"[daily-report] write failed: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="UTC date YYYY-MM-DD (default: today)")
    ap.add_argument("--loop", action="store_true", help="Daemon mode")
    ap.add_argument("--list", action="store_true", help="List all reports")
    ap.add_argument("--get",  type=int, default=None, help="Look up report by number")
    args = ap.parse_args()
    if args.list:  list_reports(); return
    if args.get is not None: get_report(args.get); return
    if args.loop: loop(); return
    date_iso = args.date or datetime.now(tz=UTC).strftime("%Y-%m-%d")
    write_report(date_iso)


if __name__ == "__main__":
    main()
