"""build_setups2_canonical.py — render the CANONICAL fires with full overlays.

Reads `monitor/strategy_lab/_canonical/results_fvg-none_10d.json` and produces
`monitor/setup_labels/setups2.html` showing each canonical fire with:
  - 🟦 Retracement origin marker
  - 🟡/🟢 UHV bar (colour-validated for direction)
  - 🔴/🔵 Breakout candle (colour-validated)
  - SL / TP horizontal lines
  - Volume pane
  - Pass/fail badge

Served via the existing port-8765 server → https://setups.claudezeeshan.com/setups2.html
"""
from __future__ import annotations
import csv, json, sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(r"C:/Users/zeesh/Documents/GitHub/turtle")
TICK_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
RESULTS = REPO / "monitor" / "strategy_lab" / "_canonical" / "results_fvg-none_10d.json"
OUT = REPO / "monitor" / "setup_labels"
OUT.mkdir(parents=True, exist_ok=True)


def build_m5_bars(date_csvs: list[Path], t_start: datetime, t_end: datetime) -> pd.DataFrame | None:
    rows = []
    for p in date_csvs:
        try:
            with p.open(newline="", encoding="utf-8") as f:
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
                    rows.append((dt, (bid + ask) / 2))
        except Exception: continue
    if not rows: return None
    rows.sort()
    bars: dict = {}
    for dt, mid in rows:
        floor_min = (dt.minute // 5) * 5
        bt = dt.replace(minute=floor_min, second=0, microsecond=0)
        b = bars.get(bt)
        if b is None:
            bars[bt] = [mid, mid, mid, mid, 1]
        else:
            b[1] = max(b[1], mid); b[2] = min(b[2], mid); b[3] = mid; b[4] += 1
    df = pd.DataFrame.from_dict(bars, orient="index").sort_index()
    df.index.name = "Datetime"
    df.columns = ["Open","High","Low","Close","Volume"]
    return df


def render(idx: int, fire: dict, png_path: Path) -> bool:
    open_t   = datetime.strptime(fire["open_t"],     "%Y-%m-%d %H:%M")
    uhv_t    = datetime.strptime(fire["uhv_t"],      "%Y-%m-%d %H:%M")
    origin_t = datetime.strptime(fire["origin_t"],   "%Y-%m-%d %H:%M")
    brk_t    = datetime.strptime(fire["breakout_t"], "%Y-%m-%d %H:%M")
    side  = fire["side"]
    entry = fire["entry"]; sl = fire["sl"]; tp = fire["tp"]
    outcome = fire.get("outcome", "OPEN")
    pnl = fire.get("pnl_usd")
    pnl_str = f"{pnl:+.2f}pts" if pnl is not None else "(open)"

    t_start = open_t - timedelta(minutes=90)
    t_end   = open_t + timedelta(minutes=60)
    date_csvs = []
    for d_offset in [-1, 0, 1]:
        d = (open_t + timedelta(days=d_offset)).strftime("%Y-%m-%d")
        p = TICK_DIR / f"shano_ticks_{d}.csv"
        if p.exists(): date_csvs.append(p)
    df = build_m5_bars(date_csvs, t_start, t_end)
    if df is None or len(df) < 10:
        print(f"  setup #{idx}: no data — skip"); return False

    extra = []
    extra.append(mpf.make_addplot([sl]*len(df), color="red",   linestyle=":", width=1, secondary_y=False))
    extra.append(mpf.make_addplot([tp]*len(df), color="green", linestyle=":", width=1, secondary_y=False))
    extra.append(mpf.make_addplot([entry]*len(df), color="white", linestyle="--", width=0.7, secondary_y=False))

    rng = df["High"].max() - df["Low"].min()
    if rng <= 0: rng = 1.0
    origin_m = [float("nan")]*len(df)
    uhv_m    = [float("nan")]*len(df)
    brk_m    = [float("nan")]*len(df)

    for i, t in enumerate(df.index):
        if abs((t - origin_t).total_seconds()) < 150:
            origin_m[i] = df["Low"].iloc[i] - rng*0.07
        if abs((t - uhv_t).total_seconds()) < 150:
            uhv_m[i] = df["High"].iloc[i] + rng*0.05
        if abs((t - brk_t).total_seconds()) < 150:
            brk_m[i] = df["Low"].iloc[i] - rng*0.05 if side=="BUY" else df["High"].iloc[i] + rng*0.05

    def has_any(arr): return any(not (v != v) for v in arr)
    if has_any(origin_m):
        extra.append(mpf.make_addplot(origin_m, type="scatter", marker="s", color="cyan", markersize=180))
    if has_any(uhv_m):
        # canonical UHV colour: red dot for BUY-setup UHV (bearish), green dot for SELL-setup UHV (bullish)
        uhv_colour = "firebrick" if side == "BUY" else "limegreen"
        extra.append(mpf.make_addplot(uhv_m, type="scatter", marker="v", color=uhv_colour, markersize=240))
    if has_any(brk_m):
        brk_colour = "blue" if side == "BUY" else "red"
        brk_marker = "^" if side == "BUY" else "v"
        extra.append(mpf.make_addplot(brk_m, type="scatter", marker=brk_marker, color=brk_colour, markersize=300))

    title = (f"Canonical #{idx}  |  {side}  |  {outcome} {pnl_str}  |  "
             f"E={entry:.2f}  SL={sl:.2f}  TP={tp:.2f}  |  "
             f"UHV_v={fire['uhv_vol']}  brk_v={fire['breakout_vol']} "
             f"(ratio={fire['breakout_vol']/fire['uhv_vol']:.2f})  |  "
             f"trend={'✓' if fire['soft_trend'] else '✗'}  sweep={'✓' if fire['soft_sweep'] else '✗'}  "
             f"strong_body={'✓' if fire['uhv_body_strong'] else '✗'}")
    try:
        fig, axes = mpf.plot(df, type="candle", style="charles", volume=True,
                              returnfig=True, addplot=extra, title=title,
                              figsize=(16, 8), warn_too_much_data=10000)
        fig.savefig(png_path, dpi=70, bbox_inches="tight")
        plt.close(fig)
        return True
    except Exception as e:
        print(f"  render #{idx}: {e}")
        try: plt.close("all")
        except: pass
        return False


def main():
    d = json.loads(RESULTS.read_text(encoding="utf-8"))
    fires = d["fires"]
    print(f"Loaded {len(fires)} canonical fires.")
    cards = []
    for i, fire in enumerate(fires, 1):
        png = OUT / f"setup2_{i:03d}.png"
        if render(i, fire, png):
            cards.append((i, fire))
            print(f"  rendered #{i} → {png.name}")

    # Build HTML
    rows_html = []
    for i, f in cards:
        pnl = f.get("pnl_usd")
        pnl_s = f"{pnl:+.2f}pts" if pnl is not None else "open"
        outcome_color = "#4ade80" if f["outcome"]=="WIN" else ("#ef4444" if f["outcome"]=="LOSS" else "#aaa")
        rows_html.append(f"""
        <div class="card">
          <div class="hdr">
            <h2>Canonical Setup #{i} — {f['side']}</h2>
            <span class="badge" style="background:{outcome_color}">{f['outcome']} {pnl_s}</span>
          </div>
          <img src="setup2_{i:03d}.png" loading="lazy"/>
          <div class="comment-block">
            <label>🧔 <b>Zeeshan's verdict</b> <span class="status" id="status-zee-{i}"></span></label>
            <textarea id="text-zee-{i}" data-idx="{i}" data-who="zee" placeholder="Is this canonical? Y/B/R shorthand…"></textarea>
            <button class="save-btn" data-idx="{i}" data-who="zee">💾 Save Zee's verdict</button>
          </div>
          <div class="comment-block">
            <label>👩 <b>Shano baji's verdict</b> <span class="status" id="status-shano-{i}"></span></label>
            <textarea id="text-shano-{i}" data-idx="{i}" data-who="shano" placeholder="Shano baji ka feedback…"></textarea>
            <button class="save-btn" data-idx="{i}" data-who="shano">💾 Save Shano's verdict</button>
          </div>
        </div>""")

    html = f"""<!doctype html>
<html><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Canonical UHV Setups — review</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background: #0b0e14; color: #e6edf3;
    margin: 0; padding: 16px; }}
  h1 {{ font-size: 22px; margin: 6px 0; }}
  .intro {{ background: #161b22; padding: 14px; border-radius: 10px; margin-bottom: 18px;
    font-size: 14px; line-height: 1.5; border-left: 4px solid #3fb950; }}
  .intro b {{ color: #ffd166; }}
  .card {{ background: #161b22; padding: 16px; border-radius: 10px; margin-bottom: 22px; }}
  .hdr {{ display: flex; align-items: center; justify-content: space-between; }}
  .hdr h2 {{ font-size: 17px; margin: 0; }}
  .badge {{ padding: 4px 10px; border-radius: 6px; color: #000; font-weight: 600; font-size: 13px; }}
  img {{ width: 100%; max-width: 1200px; display: block; margin: 12px 0; border-radius: 6px; }}
  .comment-block {{ margin-top: 12px; }}
  label {{ display: block; margin-bottom: 6px; font-size: 14px; }}
  textarea {{ width: 100%; min-height: 70px; background: #0d1117; color: #e6edf3;
    border: 1px solid #30363d; padding: 8px; font-family: inherit; font-size: 14px; border-radius: 6px; resize: vertical; }}
  .save-btn {{ background: #238636; color: #fff; border: 0; padding: 8px 14px;
    font-size: 14px; border-radius: 6px; margin-top: 6px; cursor: pointer; font-weight: 600; }}
  .save-btn:hover {{ background: #2ea043; }}
  .status {{ font-size: 12px; color: #7d8590; margin-left: 8px; }}
  .legend {{ font-size: 13px; color: #c9d1d9; }}
  .legend span {{ margin-right: 14px; }}
</style>
</head><body>

<h1>Canonical UHV Setups (75% WR, PF 5.13)</h1>
<div class="intro">
  <b>What this is:</b> These are the <b>{len(cards)} setups my new canonical detector found in the last 10 days of XAUUSD ticks</b>,
  built strictly per your spec + your 36-label feedback. Result: <b>75% WR / PF 5.13 / +32.67 pts</b>.
  Versus the old EA's 59% WR / PF 1.59 from 41 trades on a similar window.<br/><br/>
  <b>Markers:</b>
  <span class="legend">
    <span>🟦 Cyan ■ = retracement origin (opposite-colour body breaks prior extreme)</span>
    <span>🔴 Red ▼ above bar = UHV for BUY setup (bearish, max-vol)</span>
    <span>🟢 Green ▼ above bar = UHV for SELL setup (bullish, max-vol)</span>
    <span>🔵 Blue ▲ below bar = BUY breakout (closes above UHV high, opposite colour, lower vol, momentum)</span>
    <span>🔴 Red ▼ above bar = SELL breakout (closes below UHV low)</span>
    <span>⬜ White dashed = entry</span>
    <span>🟥 Red dotted = SL</span>
    <span>🟩 Green dotted = TP</span>
  </span>
  <br/><br/>
  <b>Your verdict per card:</b> say "canonical" if this would have been a setup you'd take, or note which gate is wrong using Y/B/R shorthand.
</div>

{''.join(rows_html)}

<script>
async function save(idx, who) {{
  const text = document.getElementById('text-'+who+'-'+idx).value;
  const st = document.getElementById('status-'+who+'-'+idx);
  st.textContent = 'saving…';
  try {{
    const r = await fetch('/api/labels', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ idx: 'c'+idx, who, label: text }})
    }});
    const d = await r.json();
    st.textContent = d.ok ? 'saved ✓' : 'save failed';
    setTimeout(()=> st.textContent = '', 2000);
  }} catch (e) {{ st.textContent = 'error: ' + e.message; }}
}}
document.querySelectorAll('.save-btn').forEach(b => {{
  b.addEventListener('click', () => save(b.dataset.idx, b.dataset.who));
}});
// Pre-load existing labels
fetch('/api/labels').then(r => r.json()).then(d => {{
  Object.entries(d).forEach(([key, comments]) => {{
    if (!key.startsWith('c')) return;
    const idx = key.substring(1);
    ['zee','shano'].forEach(who => {{
      if (comments[who]) {{
        const ta = document.getElementById('text-'+who+'-'+idx);
        if (ta) ta.value = comments[who];
      }}
    }});
  }});
}});
</script>
</body></html>"""
    out_html = OUT / "setups2.html"
    out_html.write_text(html, encoding="utf-8")
    print(f"\nWrote {out_html}  ({len(cards)} cards)")
    print(f"Public URL: https://setups.claudezeeshan.com/setups2.html")


if __name__ == "__main__":
    main()
