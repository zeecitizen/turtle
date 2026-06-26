"""build_setup_labeller.py — generate the setup-labelling app.

Reads MT5 tester journal for all S1 entries (and missed-entries), renders each
setup as a candle chart with markers (UHV box, sweep arrow, breakout arrow,
entry, surrounding 30 M5 bars + volume sub-pane), then bundles them into a
single HTML page where Zee writes his analysis per setup. Server endpoint
saves his labels to JSON for later EA-fix-task generation.

Output:
  monitor/setup_labels/setups.html         (the labelling UI)
  monitor/setup_labels/setup_NNN.png       (one PNG per setup)
  monitor/setup_labels/setups_meta.json    (setup metadata)
  monitor/setup_labels/zee_labels.json     (his analysis, append-only)
"""
from __future__ import annotations
import csv, json, os, re, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

REPO = Path(r"c:/Users/zeesh/Documents/GitHub/turtle")
OUT  = REPO / "monitor" / "setup_labels"
OUT.mkdir(parents=True, exist_ok=True)
TICK_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
LOG_PATH = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/81A933A9AFC5DE3C23B15CAB19C63850/Tester/logs")

LINE_RE = re.compile(r"\S+\s+\d+\s+(\d+:\d+:\d+)\.\d+\s+Core\s+\d+\s+(\d{4}\.\d{2}\.\d{2}\s+\d+:\d+:\d+)\s+(.*)")
TRIG_RE = re.compile(r"\[S1\]\s+S1\s+(BUY|SELL)\s+LIVE TRIGGER.*entry=([\d\.]+)\s+sl=([\d\.]+)\s+tp=([\d\.]+).*uhv_shift=(\d+)\s+\(vol=(\d+)\)")
FILL_RE = re.compile(r"\[S1\]\s+\[FILLED\]\s+ticket=(\d+)")
SL_RE   = re.compile(r"stop loss triggered #(\d+)\s+(buy|sell)\s+[\d\.]+\s+XAUUSD\s+[\d\.]+\s+sl:\s+[\d\.]+\s+tp:\s+[\d\.]+\s+\[#\d+\s+(?:buy|sell)\s+[\d\.]+\s+XAUUSD\s+at\s+([\d\.]+)\]")
TP_RE   = re.compile(r"take profit triggered #(\d+)\s+(buy|sell)\s+[\d\.]+\s+XAUUSD\s+[\d\.]+\s+sl:\s+[\d\.]+\s+tp:\s+[\d\.]+\s+\[#\d+\s+(?:buy|sell)\s+[\d\.]+\s+XAUUSD\s+at\s+([\d\.]+)\]")


def read_log_text(p):
    with open(p, "rb") as f:
        data = f.read()
    try: return data.decode("utf-16-le", errors="replace")
    except Exception: return data.decode("utf-8", errors="replace")


def extract_trades(log_text, wall_from="19:00"):
    """Extract all v2.59 1wk trades with entry+close."""
    trades, pending = [], None
    for line in log_text.splitlines():
        m = LINE_RE.match(line)
        if not m: continue
        wall, sim, msg = m.group(1), m.group(2), m.group(3)
        if wall_from and wall < wall_from: continue

        t = TRIG_RE.search(msg)
        if t:
            pending = {
                "side": t.group(1),
                "entry": float(t.group(2)),
                "sl": float(t.group(3)),
                "tp": float(t.group(4)),
                "uhv_shift": int(t.group(5)),
                "uhv_vol": int(t.group(6)),
                "sim_open": sim, "wall_open": wall,
            }
            continue
        f = FILL_RE.search(msg)
        if f and pending is not None:
            pending["ticket"] = int(f.group(1))
            trades.append(pending); pending = None
            continue
        for rex, reason in ((SL_RE,"SL"), (TP_RE,"TP")):
            r = rex.search(msg)
            if r:
                ticket = int(r.group(1))
                price  = float(r.group(3))
                for tr in trades:
                    if tr.get("ticket")==ticket and "close_price" not in tr:
                        tr["close_price"] = price
                        tr["close_reason"] = reason
                        tr["sim_close"] = sim
                        break
    # outcome
    for tr in trades:
        if "close_price" in tr:
            pnl = (tr["close_price"]-tr["entry"]) if tr["side"]=="BUY" else (tr["entry"]-tr["close_price"])
            tr["pnl_pts"] = pnl
            tr["pnl_usd"] = pnl
            tr["outcome"] = "WIN" if pnl > 0 else "LOSS"
    return trades


def build_m5_bars(tick_csv_paths, t_start, t_end):
    """Build M5 OHLCV bars from tick CSV(s) covering [t_start, t_end]."""
    rows = []
    for p in tick_csv_paths:
        try:
            with open(p, encoding="utf-8") as f:
                r = csv.DictReader(f)
                for row in r:
                    ts = row.get("ts_broker") or row.get("ts")
                    if not ts: continue
                    try: dt = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
                    except ValueError: continue
                    if dt < t_start or dt > t_end: continue
                    try:
                        bid = float(row["bid"]); ask = float(row["ask"])
                    except (KeyError, ValueError): continue
                    rows.append((dt, (bid+ask)/2))
        except Exception:
            continue
    if not rows: return None
    bars = {}
    for dt, mid in rows:
        floor_min = (dt.minute // 5) * 5
        bar_t = dt.replace(minute=floor_min, second=0, microsecond=0)
        b = bars.get(bar_t)
        if b is None:
            bars[bar_t] = {"open": mid, "high": mid, "low": mid, "close": mid, "volume": 1}
        else:
            if mid > b["high"]: b["high"] = mid
            if mid < b["low"]: b["low"] = mid
            b["close"] = mid
            b["volume"] += 1
    if not bars: return None
    df = pd.DataFrame.from_dict(bars, orient="index").sort_index()
    df.index.name = "Datetime"
    df.columns = ["Open","High","Low","Close","Volume"]
    return df


def render_setup(setup_idx, trade, df, png_path):
    if df is None or len(df) < 5:
        return False
    open_t = datetime.strptime(trade["sim_open"], "%Y.%m.%d %H:%M:%S")
    # UHV bar time: open_t - uhv_shift * 5min
    uhv_t = open_t - timedelta(minutes=5 * trade["uhv_shift"])
    # Annotate via mplfinance
    side = trade["side"]
    entry = trade["entry"]; sl=trade.get("sl"); tp=trade.get("tp")
    close_p = trade.get("close_price"); reason = trade.get("close_reason","?")
    outcome = trade.get("outcome","OPEN")
    pnl = trade.get("pnl_usd")
    pnl_str = f"{pnl:+.2f}$" if pnl is not None else "(open)"

    # Build addplots: SL/TP horizontal at the right side
    extra_ap = []
    if sl: extra_ap.append(mpf.make_addplot([sl]*len(df), color="red", linestyle=":", width=1, secondary_y=False))
    if tp: extra_ap.append(mpf.make_addplot([tp]*len(df), color="green", linestyle=":", width=1, secondary_y=False))

    # color UHV bar via marker series — only add if any non-NaN values
    uhv_marker = [float("nan")]*len(df)
    entry_marker = [float("nan")]*len(df)
    rng = df["High"].max() - df["Low"].min()
    if rng <= 0: rng = 1.0
    for i, t in enumerate(df.index):
        if abs((t - uhv_t).total_seconds()) < 150:  # within 2.5 min of an M5 bar centre
            uhv_marker[i] = df["High"].iloc[i] + rng*0.05
        if abs((t - open_t).total_seconds()) < 300:  # within 5 min
            entry_marker[i] = df["Low"].iloc[i] - rng*0.05 if side=="BUY" else df["High"].iloc[i] + rng*0.05
    if any(not (v != v) for v in uhv_marker):  # has any non-NaN
        extra_ap.append(mpf.make_addplot(uhv_marker, type="scatter", marker="v", color="goldenrod", markersize=200))
    if any(not (v != v) for v in entry_marker):
        extra_ap.append(mpf.make_addplot(entry_marker, type="scatter",
                                         marker="^" if side=="BUY" else "v",
                                         color="blue" if side=="BUY" else "red", markersize=300))

    title = f"Setup #{setup_idx}  |  {side}  |  {outcome} {pnl_str}  |  exit={reason}  |  {open_t.strftime('%Y-%m-%d %H:%M')}  |  UHV vol={trade['uhv_vol']}"

    try:
        kwargs = dict(
            type="candle", style="charles",
            volume=True, returnfig=True,
            title=title,
            figsize=(14, 7),
            warn_too_much_data=10000,
        )
        if extra_ap:
            kwargs["addplot"] = extra_ap
        fig, axes = mpf.plot(df, **kwargs)
        fig.savefig(png_path, dpi=70, bbox_inches="tight")
        plt.close(fig)
        return True
    except Exception as e:
        print(f"  render error: {e}")
        try: plt.close("all")
        except: pass
        return False


def main():
    log_files = sorted(LOG_PATH.glob("*.log"))
    if not log_files:
        print("No tester log files."); return
    log_path = log_files[-1]
    print(f"Reading {log_path}")
    text = read_log_text(log_path)
    trades = extract_trades(text, wall_from="19:00")
    print(f"Extracted {len(trades)} trades")

    # Get tick CSVs by date
    tick_csvs = sorted(TICK_DIR.glob("shano_ticks_2026-*.csv"))
    print(f"Tick CSVs available: {len(tick_csvs)}")

    meta = []
    n_rendered = 0
    for i, tr in enumerate(trades[:100], start=1):
        try:
            open_t = datetime.strptime(tr["sim_open"], "%Y.%m.%d %H:%M:%S")
        except ValueError:
            continue
        t_start = open_t - timedelta(minutes=80)
        t_end   = open_t + timedelta(minutes=80)
        # Find tick CSVs whose date overlaps
        date_csvs = []
        for d_offset in [-1, 0, 1]:
            dt_for_csv = (open_t + timedelta(days=d_offset)).strftime("%Y-%m-%d")
            csv_p = TICK_DIR / f"shano_ticks_{dt_for_csv}.csv"
            if csv_p.exists(): date_csvs.append(csv_p)
        df = build_m5_bars(date_csvs, t_start, t_end)
        if df is None or len(df) < 8:
            print(f"  setup #{i}: no data — skip")
            continue
        png_path = OUT / f"setup_{i:03d}.png"
        ok = render_setup(i, tr, df, png_path)
        if ok:
            meta.append({
                "idx": i, "trade": {**tr, "ticket": tr.get("ticket")},
                "png": png_path.name,
            })
            n_rendered += 1
            print(f"  setup #{i} rendered → {png_path.name}")
        else:
            print(f"  setup #{i}: render failed")

    # Save meta
    with open(OUT / "setups_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)

    # Build HTML
    html_parts = []
    html_parts.append("""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>S1Trader Setup Labels</title>
<style>
  body { font-family: -apple-system, sans-serif; background:#1e1e1e; color:#ddd; margin:0; padding:20px; }
  h1 { color:#fff; }
  .setup { background:#2a2a2a; margin: 20px 0; padding: 16px; border-radius:8px; }
  .setup h2 { margin: 0 0 10px 0; }
  .setup .meta { color:#888; font-size:12px; margin-bottom:10px; }
  .setup img { max-width:100%; border:1px solid #444; border-radius:4px; }
  .setup textarea { width:100%; min-height:60px; margin: 4px 0; background:#1a1a1a; color:#fff; border:1px solid #444; padding:8px; font-family:monospace; font-size:13px; }
  .setup .comment-block { margin-top: 12px; padding: 8px; background:#222; border-left: 3px solid #555; border-radius:4px; }
  .setup .comment-block label { color:#bbb; font-size:13px; display:block; margin-bottom:4px; }
  .setup .save-btn { background:#3b5fcc; color:#fff; border:none; padding:6px 14px; border-radius:4px; cursor:pointer; font-size:13px; }
  .setup .save-btn:hover { background:#4a70dd; }
  .setup .save-btn:disabled { background:#555; cursor:not-allowed; }
  .setup .status { margin-left: 10px; font-size:11px; color:#888; }
  .setup .saved { color:#4ade80; }
  .nav { position:fixed; top:10px; right:10px; background:#2a2a2a; padding:10px; border-radius:6px; }
  .nav a { color:#aaa; margin: 0 6px; text-decoration:none; }
</style>
</head><body>
<h1>S1Trader Setup Review — """ + str(len(meta)) + """ setups from v2.59 backtest</h1>
<p>For each setup, type your analysis. Saves automatically. Examples:
<br/>&nbsp; ✅ <b>"correct UHV — entry timing good"</b>
<br/>&nbsp; ❌ <b>"wrong UHV — should be the bigger volume bar 3 candles earlier"</b>
<br/>&nbsp; ⚠️ <b>"UHV correct but EA entered before sweep completed; should wait for sweep wick"</b>
</p>
<div class='nav'><a href='#top'>Top</a> · <a href='#bottom'>Bottom</a></div>
<a id='top'></a>
""")
    for m in meta:
        tr = m["trade"]
        outcome = tr.get("outcome","OPEN")
        pnl = tr.get("pnl_usd")
        pnl = pnl if pnl is not None else 0
        outcome_color = "#4ade80" if outcome=="WIN" else ("#ef4444" if outcome=="LOSS" else "#aaa")
        html_parts.append(f"""
<div class='setup' id='setup-{m['idx']}'>
  <h2>Setup #{m['idx']}</h2>
  <div class='meta'>
    <b>{tr['side']}</b> at {tr['sim_open']} | entry={tr['entry']:.2f} sl={tr['sl']:.2f} tp={tr['tp']:.2f}
    | UHV shift={tr['uhv_shift']} vol={tr['uhv_vol']}
    | exit={tr.get('close_reason','?')} @ {tr.get('close_price','?')}
    | <span style='color:{outcome_color};'><b>{outcome} {pnl:+.2f}$</b></span>
  </div>
  <img src='{m['png']}' />
  <div class='comment-block'>
    <label>🧔 <b>Zeeshan's analysis</b> <span class='status' id='status-zee-{m['idx']}'></span></label>
    <textarea id='text-zee-{m['idx']}' data-idx='{m['idx']}' data-who='zee' placeholder='Zee, your analysis of setup #{m['idx']}...'></textarea>
    <button class='save-btn' data-idx='{m['idx']}' data-who='zee'>💾 Save Zee's comment</button>
  </div>
  <div class='comment-block'>
    <label>👩 <b>Shano baji's analysis</b> <span class='status' id='status-shano-{m['idx']}'></span></label>
    <textarea id='text-shano-{m['idx']}' data-idx='{m['idx']}' data-who='shano' placeholder='Shano baji, your analysis...'></textarea>
    <button class='save-btn' data-idx='{m['idx']}' data-who='shano'>💾 Save Shano's comment</button>
  </div>
</div>
""")
    html_parts.append("""
<a id='bottom'></a>
<script>
async function loadLabels() {
  try {
    const r = await fetch('/api/labels');
    if (r.ok) {
      const j = await r.json();
      for (const idx in j) {
        const data = j[idx] || {};
        for (const who of ['zee','shano']) {
          const ta = document.getElementById('text-'+who+'-'+idx);
          if (ta && data[who]) {
            ta.value = data[who];
            document.getElementById('status-'+who+'-'+idx).innerHTML = '<span class="saved">✓ saved</span>';
          }
        }
      }
    }
  } catch (e) {}
}
async function saveLabel(idx, who, val, btn) {
  const status = document.getElementById('status-'+who+'-'+idx);
  status.innerHTML = 'saving...';
  if (btn) btn.disabled = true;
  try {
    await fetch('/api/labels', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({idx, who, label: val})});
    status.innerHTML = '<span class="saved">✓ saved</span>';
  } catch (e) {
    status.innerHTML = 'save failed';
  }
  if (btn) btn.disabled = false;
}
document.querySelectorAll('.save-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const idx = btn.dataset.idx;
    const who = btn.dataset.who;
    const ta  = document.getElementById('text-'+who+'-'+idx);
    saveLabel(idx, who, ta.value, btn);
  });
});
// Also keyboard shortcut Ctrl+Enter in any textarea = save that one
document.querySelectorAll('textarea').forEach(ta => {
  ta.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
      saveLabel(ta.dataset.idx, ta.dataset.who, ta.value);
    }
  });
});
loadLabels();
</script>
</body></html>
""")
    (OUT / "setups.html").write_text("".join(html_parts), encoding="utf-8")
    print(f"\nRendered {n_rendered} setups.")
    print(f"HTML: {OUT / 'setups.html'}")


if __name__ == "__main__":
    main()
