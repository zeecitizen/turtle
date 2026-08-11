"""memory_hawk.py - hourly honest progress journal.

Appends a structured entry to memory.md every hour. See memory.md header for
purpose and the required-fields spec.

Usage:
    python memory_hawk.py            # write ONE entry now and exit
    python memory_hawk.py --loop     # daemon: write at top of each hour, forever

The required fields (per Zee's spec 2026-06-03):
  - timestamp (UTC + Berlin + broker — we use UTC for the heading)
  - current winrate (today, week, all-time live)
  - confidence level + reasoning
  - current plan
  - achieved this hour

APPEND-ONLY rule (Zee 2026-06-03):
  - This script ONLY appends to memory.md. It never edits or deletes past entries.
  - Wall-of-shame entries are written by a HUMAN OR by claude-the-assistant in
    response to a real refutation/retraction. When an old wall-of-shame entry is
    later retracted, the corrector MUST append a new "retraction" row, never
    edit the original. History of the reasoning is the actual value of this file.
"""
import sys, csv, json, time, os, argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
UTC = timezone.utc

# Paths
ROOT       = Path(r"C:\Users\zeesh\Documents\GitHub\turtle")
MEMORY_MD  = ROOT / "memory.md"
COMMON     = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
FILLS_CSV  = COMMON / "turtle_fills.csv"
STATE_JSON = COMMON / "feb11_state_88011.json"
RUNTIME    = COMMON / "feb11_runtime_88011.json"
EA_SRC     = ROOT / "mt5" / "Feb11TickMedium.mq5"
STATE_FILE = ROOT / "monitor" / ".memory_hawk_state.json"  # for "achieved this hour" diff


def utc_now():
    return datetime.now(tz=UTC)


def pkt_str(dt_utc):
    # Pakistan Standard Time = UTC+5, no DST. Per Rule #9 in startup.bat —
    # always show Zee times in PKT until he tells us he's back in Germany.
    return (dt_utc + timedelta(hours=5)).strftime("%Y-%m-%d %H:%M PKT")


def berlin_str(dt_utc):
    # Retained for reference; do NOT use as Zee's primary display per Rule #9.
    return (dt_utc + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M Berlin")


def load_fills(today_only=True, last_n_days=None):
    out = []
    if not FILLS_CSV.exists(): return out
    today_prefix = utc_now().strftime("%Y.%m.%d")
    cutoff_prefix = None
    if last_n_days is not None:
        cutoff = utc_now() - timedelta(days=last_n_days)
        cutoff_prefix = cutoff.strftime("%Y.%m.%d")
    with open(FILLS_CSV, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f); next(rdr, None)
        for r in rdr:
            if not r or len(r) < 8: continue
            try:
                pnl = float(r[7]); vol = r[5]; t = r[0]
            except: continue
            if today_only and not t.startswith(today_prefix): continue
            if cutoff_prefix and t[:10].replace(".", "-") < cutoff_prefix.replace(".", "-"): continue
            out.append({"t": t, "side": r[4], "vol": vol, "pnl": pnl})
    return out


def winrate(fills):
    w = sum(1 for f in fills if f["pnl"] > 0)
    l = sum(1 for f in fills if f["pnl"] < 0)
    if (w + l) == 0: return None, 0, 0, 0
    pnl = sum(f["pnl"] for f in fills)
    return 100 * w / (w + l), w, l, pnl


def read_ea_version():
    try:
        text = EA_SRC.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if line.startswith("#property version"):
                return line.split('"')[1] if '"' in line else "?"
    except: pass
    return "?"


def read_state():
    if not STATE_JSON.exists(): return {}
    try: return json.loads(STATE_JSON.read_text())
    except: return {}


def read_runtime():
    if not RUNTIME.exists(): return None
    try: return json.loads(RUNTIME.read_text())
    except: return None


def load_state():
    if not STATE_FILE.exists(): return {}
    try: return json.loads(STATE_FILE.read_text())
    except: return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def confidence_assessment(today_fills_pnl, week_wr, week_n):
    """Honest auto-assessment. Bias toward LOW unless real data justifies higher.
    Reasoning: a Claude session writing this auto-journal should NOT inflate
    its own confidence. The human verifies confidence by editing the file."""
    if week_n < 10:
        return "LOW", f"only {week_n} trades in last 7 days, insufficient sample"
    if week_wr is None:
        return "LOW", "no decisive wins or losses to compute WR"
    if today_fills_pnl <= -100:
        return "LOW", f"today P&L ${today_fills_pnl:+.2f} is significantly negative"
    if week_wr < 50:
        return "LOW", f"7-day WR {week_wr:.0f}% < 50%, no statistical edge"
    if week_wr < 60:
        return "MEDIUM", f"7-day WR {week_wr:.0f}% (50-60%) — positive but marginal"
    if week_wr < 75:
        return "MEDIUM", f"7-day WR {week_wr:.0f}% (60-75%) — solid but unverified vs backtest"
    return "MEDIUM", f"7-day WR {week_wr:.0f}% looks high, requires verification vs backtest"


def build_entry(achieved_lines=None):
    now = utc_now()
    ts_utc = now.strftime("%Y-%m-%d %H:%M UTC")
    ts_pkt = pkt_str(now)   # Rule #9: PKT is primary for Zee
    today_fills = load_fills(today_only=True)
    week_fills = load_fills(today_only=False, last_n_days=7)
    today_wr, today_w, today_l, today_pnl = winrate(today_fills)
    week_wr, week_w, week_l, week_pnl = winrate(week_fills)

    ea_version = read_ea_version()
    state = read_state()
    runtime = read_runtime()

    conf_level, conf_why = confidence_assessment(today_pnl, week_wr, week_w + week_l)

    runtime_str = (
        f"`{json.dumps(runtime)}`" if runtime
        else "(none — EA on Inp defaults)"
    )

    lines = []
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"## {ts_pkt}  ({ts_utc})")
    lines.append("")
    lines.append("### 📊 Live state")
    lines.append(f"- EA source: Feb11TickMedium v{ea_version}, magic 88011, 0.05 lots, Atmos LIVE")
    lines.append(f"- Runtime overrides: {runtime_str}")
    if state:
        lines.append(f"- State file: session_pnl=${state.get('session_pnl', 0):+.2f}  "
                     f"consec_losses={state.get('consec_losses', 0)}  "
                     f"pause_until={state.get('pause_until', 0)}")
    lines.append("")
    lines.append("### 💰 Today P&L (broker truth from turtle_fills.csv)")
    if today_fills:
        wr_str = f"{today_wr:.1f}%" if today_wr is not None else "n/a"
        lines.append(f"- Net: ${today_pnl:+.2f}  ({today_w}W / {today_l}L = {wr_str} WR, n={len(today_fills)})")
    else:
        lines.append(f"- No fills yet today")
    lines.append("")
    lines.append("### 📈 Last 7 days (live, broker truth)")
    if week_fills:
        wr_str = f"{week_wr:.1f}%" if week_wr is not None else "n/a"
        lines.append(f"- Net: ${week_pnl:+.2f}  ({week_w}W / {week_l}L = {wr_str} WR, n={len(week_fills)})")
    else:
        lines.append(f"- No fills in last 7 days")
    lines.append("")
    lines.append("### 🔒 Confidence level (auto-assessed, conservative bias)")
    lines.append(f"- **{conf_level}** — {conf_why}")
    lines.append(f"- (Human override allowed — Zee can edit this line directly)")
    lines.append("")
    lines.append("### 📋 Current plan")
    plan = load_state().get("current_plan", "(no plan recorded — Zee or Claude must set via _set_plan helper)")
    lines.append(f"- {plan}")
    lines.append("")
    lines.append("### ✅ Achieved this hour")
    if achieved_lines:
        for line in achieved_lines: lines.append(f"- {line}")
    else:
        # Best-effort: count new fills since last entry
        prev = load_state()
        prev_today_n = prev.get("today_fills_n", 0)
        prev_today_pnl = prev.get("today_pnl", 0.0)
        delta_n = len(today_fills) - prev_today_n
        delta_pnl = today_pnl - prev_today_pnl
        if delta_n > 0:
            lines.append(f"- {delta_n} new fills this hour, ${delta_pnl:+.2f} net change")
        else:
            lines.append(f"- No new fills this hour (EA paused or quiet)")
    lines.append("")
    lines.append("### ⚠️ Risks / red flags")
    if today_pnl <= -200: lines.append(f"- ❗ Today's loss ${today_pnl:+.2f} approaching halt-line −$250")
    if today_pnl <= -350: lines.append(f"- 🚨 Today's loss past halt-line — EA should be paused")
    if state.get("consec_losses", 0) >= 3: lines.append(f"- ❗ {state['consec_losses']} consecutive losses on EA's books")
    if not runtime: lines.append(f"- (Runtime override file absent — EA on raw Inp defaults)")
    # Always include a generic reminder
    lines.append(f"- Note: confidence above is auto-set conservatively. Do NOT promote to HIGH without backtest-vs-live reconciliation.")
    lines.append("")

    # Save state for next hour's "achieved this hour" diff
    persist = load_state()
    persist["today_fills_n"] = len(today_fills)
    persist["today_pnl"] = today_pnl
    persist["last_run_ts_utc"] = now.timestamp()
    save_state(persist)

    return "\n".join(lines)


def write_entry(achieved_lines=None):
    entry = build_entry(achieved_lines=achieved_lines)
    with open(MEMORY_MD, "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    print(f"[memory_hawk] appended entry at {utc_now().strftime('%H:%M UTC')}")
    return entry


def set_plan(text):
    """Update the 'current plan' line that the next hourly entry will use."""
    state = load_state()
    state["current_plan"] = text
    save_state(state)
    print(f"[memory_hawk] plan set: {text}")


def loop():
    """Daemon: write entry at the top of each hour, forever."""
    print(f"[memory_hawk] daemon starting at {utc_now()}")
    while True:
        try:
            write_entry()
        except Exception as e:
            print(f"[memory_hawk] write failed: {e}")
        # Sleep until top of next hour
        now = utc_now()
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=10, microsecond=0)
        sleep_s = max(60, int((next_hour - now).total_seconds()))
        print(f"[memory_hawk] sleeping {sleep_s}s until {next_hour.strftime('%H:%M UTC')}")
        time.sleep(sleep_s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true", help="Run as hourly daemon")
    ap.add_argument("--plan", type=str, default=None, help="Update the current plan line")
    ap.add_argument("--achieved", nargs="*", default=None, help="Bullet items for 'achieved this hour'")
    args = ap.parse_args()

    if args.plan is not None:
        set_plan(args.plan)
        return 0
    if args.loop:
        loop()
        return 0
    write_entry(achieved_lines=args.achieved)
    return 0


if __name__ == "__main__":
    sys.exit(main())
