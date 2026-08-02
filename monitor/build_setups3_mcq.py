"""build_setups3_mcq.py — render ALL detected canonical candidates with MCQ inputs.

For each setup: chart PNG + 5 multiple-choice radio questions covering trend,
retracement, UHV, breakout, and overall verdict. Saves answers as structured
JSON via POST /api/labels (key = m<idx>).
"""
from __future__ import annotations
import csv, json, sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

REPO = Path(r"C:/Users/zeesh/Documents/GitHub/turtle")
TICK_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
RESULTS = REPO / "monitor" / "strategy_lab" / "_canonical" / "results_fvg-none_29d.json"
OUT = REPO / "monitor" / "setup_labels"
OUT.mkdir(parents=True, exist_ok=True)


def build_m5(date_csvs, t_start, t_end):
    rows = []
    for p in date_csvs:
        try:
            with p.open(newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                for row in r:
                    ts = row.get("ts_broker") or row.get("ts") or row.get("t")
                    if not ts: continue
                    if "." in ts.split(" ", 1)[-1]:
                        ts = ts.rsplit(".", 1)[0]
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
    bars = {}
    for dt, mid in rows:
        floor_min = (dt.minute // 5) * 5
        bt = dt.replace(minute=floor_min, second=0, microsecond=0)
        b = bars.get(bt)
        if b is None: bars[bt] = [mid, mid, mid, mid, 1]
        else:
            b[1] = max(b[1], mid); b[2] = min(b[2], mid); b[3] = mid; b[4] += 1
    df = pd.DataFrame.from_dict(bars, orient="index").sort_index()
    df.index.name = "Datetime"
    df.columns = ["Open","High","Low","Close","Volume"]
    return df


def render(idx, fire, png_path):
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
    df = build_m5(date_csvs, t_start, t_end)
    if df is None or len(df) < 10: return False

    extra = []
    extra.append(mpf.make_addplot([sl]*len(df), color="red",   linestyle=":", width=1, secondary_y=False))
    extra.append(mpf.make_addplot([tp]*len(df), color="green", linestyle=":", width=1, secondary_y=False))
    extra.append(mpf.make_addplot([entry]*len(df), color="white", linestyle="--", width=0.7, secondary_y=False))

    rng = df["High"].max() - df["Low"].min()
    if rng <= 0: rng = 1.0
    origin_m = [float("nan")]*len(df); uhv_m = [float("nan")]*len(df); brk_m = [float("nan")]*len(df)
    for i, t in enumerate(df.index):
        if abs((t - origin_t).total_seconds()) < 150: origin_m[i] = df["Low"].iloc[i] - rng*0.07
        if abs((t - uhv_t).total_seconds()) < 150:    uhv_m[i]    = df["High"].iloc[i] + rng*0.05
        if abs((t - brk_t).total_seconds()) < 150:
            brk_m[i] = df["Low"].iloc[i] - rng*0.05 if side=="BUY" else df["High"].iloc[i] + rng*0.05
    def has_any(a): return any(not (v != v) for v in a)
    if has_any(origin_m): extra.append(mpf.make_addplot(origin_m, type="scatter", marker="s", color="cyan", markersize=180))
    if has_any(uhv_m):
        uhv_colour = "firebrick" if side == "BUY" else "limegreen"
        extra.append(mpf.make_addplot(uhv_m, type="scatter", marker="v", color=uhv_colour, markersize=240))
    if has_any(brk_m):
        bc = "blue" if side == "BUY" else "red"
        bm = "^" if side == "BUY" else "v"
        extra.append(mpf.make_addplot(brk_m, type="scatter", marker=bm, color=bc, markersize=300))

    title = (f"Setup #{idx}  |  {side}  |  {outcome} {pnl_str}  |  "
             f"UHV vol={fire['uhv_vol']} brk vol={fire['breakout_vol']} ratio={fire['breakout_vol']/fire['uhv_vol']:.2f}  |  "
             f"trend={'✓' if fire['soft_trend'] else '✗'} sweep={'✓' if fire['soft_sweep'] else '✗'} "
             f"strong_body={'✓' if fire['uhv_body_strong'] else '✗'}")
    try:
        fig, axes = mpf.plot(df, type="candle", style="charles", volume=True,
                              returnfig=True, addplot=extra, title=title,
                              figsize=(16, 8), warn_too_much_data=10000)
        fig.savefig(png_path, dpi=70, bbox_inches="tight")
        plt.close(fig)
        return True
    except Exception as e:
        print(f"  #{idx} render: {e}")
        try: plt.close("all")
        except: pass
        return False


# ── Binary verdict schema (simplified per Zee 2026-06-08) ──────────────
# Replaces the 5-question MCQ with: Correct / Incorrect + reason-if-incorrect.


def main():
    d = json.loads(RESULTS.read_text("utf-8"))
    fires = d["fires"]
    print(f"Loaded {len(fires)} canonical candidates.")
    cards = []
    for i, fire in enumerate(fires, 1):
        png = OUT / f"setup3_{i:03d}.png"
        if render(i, fire, png):
            cards.append((i, fire))
            if i % 5 == 0: print(f"  rendered through #{i}")
    print(f"\n{len(cards)} cards rendered.")

    rows_html = []
    for i, f in cards:
        pnl = f.get("pnl_usd")
        pnl_s = f"{pnl:+.2f}pts" if pnl is not None else "open"
        outcome_color = "#4ade80" if f["outcome"]=="WIN" else ("#ef4444" if f["outcome"]=="LOSS" else "#aaa")
        date_str = f["open_t"]
        rows_html.append(f"""
        <div class="card" id="card-{i}">
          <div class="hdr">
            <h2>Setup #{i} — {f['side']} · {date_str}</h2>
            <span class="badge" style="background:{outcome_color}">{f['outcome']} {pnl_s}</span>
          </div>
          <img src="setup3_{i:03d}.png" loading="lazy"/>
          <div class="quiz">
            <div class="verdict-row">
              <label class="verdict-opt verdict-correct">
                <input type="radio" name="v-{i}" value="correct" data-idx="{i}"/>
                <span>✅ Correct</span>
              </label>
              <label class="verdict-opt verdict-incorrect">
                <input type="radio" name="v-{i}" value="incorrect" data-idx="{i}"/>
                <span>❌ Incorrect</span>
              </label>
            </div>
            <div class="reason-row" id="reason-row-{i}" style="display:none;">
              <label>Reason for incorrect:</label>
              <textarea id="reason-{i}" data-idx="{i}" placeholder="Which gate failed? (e.g. 'Y not red', 'B doesn't cross UHV high', 'trend shifting')…"></textarea>
            </div>
            <button class="save-btn" data-idx="{i}">💾 Save</button>
            <span class="status" id="status-{i}"></span>
          </div>
        </div>""")

    html = f"""<!doctype html>
<html><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Canonical UHV Setups — MCQ labelling</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background: #0b0e14; color: #e6edf3;
    margin: 0; padding: 16px; }}
  h1 {{ font-size: 22px; margin: 6px 0; }}
  .intro {{ background: #161b22; padding: 14px; border-radius: 10px; margin-bottom: 18px;
    font-size: 13px; line-height: 1.5; border-left: 4px solid #f5c842; }}
  .intro b {{ color: #f5c842; }}
  .card {{ background: #161b22; padding: 16px; border-radius: 10px; margin-bottom: 22px; }}
  .hdr {{ display: flex; align-items: center; justify-content: space-between; }}
  .hdr h2 {{ font-size: 16px; margin: 0; }}
  .badge {{ padding: 4px 10px; border-radius: 6px; color: #000; font-weight: 600; font-size: 12px; }}
  img {{ width: 100%; max-width: 1200px; display: block; margin: 12px 0; border-radius: 6px; }}
  .quiz {{ margin-top: 10px; }}
  .verdict-row {{ display: flex; gap: 12px; margin-bottom: 10px; }}
  .verdict-opt {{ flex: 1; display: flex; align-items: center; padding: 12px 14px;
    background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
    cursor: pointer; font-size: 15px; font-weight: 600; gap: 8px;
    transition: all 0.15s; }}
  .verdict-opt:hover {{ background: #161b22; }}
  .verdict-opt input {{ width: 18px; height: 18px; margin: 0; cursor: pointer; }}
  .verdict-correct input:checked ~ span {{ color: #3fb950; }}
  .verdict-correct:has(input:checked) {{ background: rgba(63, 185, 80, 0.12); border-color: #3fb950; }}
  .verdict-incorrect input:checked ~ span {{ color: #f85149; }}
  .verdict-incorrect:has(input:checked) {{ background: rgba(248, 81, 73, 0.10); border-color: #f85149; }}
  .reason-row {{ margin: 12px 0; }}
  .reason-row label {{ display: block; font-size: 12px; color: #f85149; margin-bottom: 4px; font-weight: 600; }}
  .reason-row textarea {{ width: 100%; min-height: 60px; background: #0d1117; color: #e6edf3;
    border: 1px solid #30363d; padding: 10px; font-family: inherit; font-size: 14px; border-radius: 6px;
    line-height: 1.4; box-sizing: border-box; }}
  .reason-row textarea:focus {{ outline: 1px solid #f5c842; border-color: #f5c842; }}
  .save-btn {{ background: #238636; color: #fff; border: 0; padding: 8px 16px;
    font-size: 14px; border-radius: 6px; cursor: pointer; font-weight: 600; }}
  .save-btn:hover {{ background: #2ea043; }}
  .save-btn.saved {{ background: #1f6feb; }}
  .status {{ margin-left: 12px; font-size: 12px; color: #888; }}
  .progress {{ position: sticky; top: 0; background: #161b22; padding: 8px 14px; border-radius: 8px;
    margin-bottom: 14px; z-index: 100; border: 1px solid #30363d; }}
  .progress .bar {{ height: 6px; background: #30363d; border-radius: 3px; margin-top: 6px; overflow: hidden; }}
  .progress .fill {{ height: 100%; background: linear-gradient(90deg, #3fb950, #f5c842); width: 0%; transition: width 0.3s; }}
</style>
</head><body>

<h1>Canonical UHV — Setup Labelling ({len(cards)} setups)</h1>
<div class="progress">
  <span id="progress-text">0 / {len(cards)} labelled</span>
  <div class="bar"><div class="fill" id="progress-fill"></div></div>
</div>
<div class="intro">
  <b>How this works:</b> Look at each chart, click <b>✅ Correct</b> or <b>❌ Incorrect</b>.
  If Incorrect, type why in the reason box (Y/B/R shorthand works). Then hit Save.<br/><br/>
  <b>Markers:</b> 🟦 cyan ■ = retracement origin · 🔴 red ▼ = UHV (BUY) · 🟢 green ▼ = UHV (SELL) ·
  🔵 blue ▲ below = BUY breakout · 🔴 red ▼ above = SELL breakout · white dashed = entry · red dotted = SL · green dotted = TP.
</div>

{''.join(rows_html)}

<script>
const TOTAL = {len(cards)};
let labelledCount = 0;

async function save(idx) {{
  const card = document.getElementById('card-' + idx);
  const picked = card.querySelector(`input[name="v-${{idx}}"]:checked`);
  const verdict = picked ? picked.value : null;
  const reason = (document.getElementById('reason-' + idx) || {{value:''}}).value.trim();
  if (!verdict) {{
    const st = document.getElementById('status-' + idx);
    st.textContent = 'pick Correct or Incorrect first';
    return;
  }}
  const payload = {{
    idx: 'm' + idx, who: 'zee',
    label: JSON.stringify({{ verdict, reason }}),
  }};
  const st = document.getElementById('status-' + idx);
  const btn = card.querySelector('.save-btn');
  st.textContent = 'saving…';
  try {{
    const r = await fetch('/api/labels', {{
      method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(payload),
    }});
    const d = await r.json();
    if (d.ok) {{
      st.textContent = verdict === 'correct' ? 'saved ✓' : 'saved ✓ (reason logged)';
      btn.classList.add('saved');
      btn.textContent = '✓ Saved';
      updateProgress();
    }} else st.textContent = 'save failed';
  }} catch (e) {{ st.textContent = 'err: ' + e.message; }}
}}
function updateProgress() {{
  const saved = document.querySelectorAll('.save-btn.saved').length;
  document.getElementById('progress-text').textContent = saved + ' / ' + TOTAL + ' labelled';
  document.getElementById('progress-fill').style.width = (saved/TOTAL*100) + '%';
}}
// Reveal reason box only when Incorrect is picked
document.querySelectorAll('input[type=radio][name^="v-"]').forEach(r => {{
  r.addEventListener('change', () => {{
    const idx = r.dataset.idx;
    const row = document.getElementById('reason-row-' + idx);
    if (row) row.style.display = r.value === 'incorrect' ? 'block' : 'none';
    if (r.value === 'incorrect') {{
      const ta = document.getElementById('reason-' + idx);
      if (ta) setTimeout(() => ta.focus(), 50);
    }}
  }});
}});
document.querySelectorAll('.save-btn').forEach(b => {{
  b.addEventListener('click', () => save(b.dataset.idx));
}});
// Pre-load existing answers (both new {{verdict,reason}} and legacy {{answers,notes}} shapes)
fetch('/api/labels').then(r => r.json()).then(d => {{
  Object.entries(d).forEach(([key, comments]) => {{
    if (!key.startsWith('m')) return;
    const idx = key.substring(1);
    if (!comments.zee) return;
    try {{
      const data = JSON.parse(comments.zee);
      const card = document.getElementById('card-' + idx);
      if (!card) return;
      // New binary shape
      if (data.verdict) {{
        const sel = card.querySelector(`input[name="v-${{idx}}"][value="${{data.verdict}}"]`);
        if (sel) {{
          sel.checked = true;
          const row = document.getElementById('reason-row-' + idx);
          if (row && data.verdict === 'incorrect') row.style.display = 'block';
        }}
        if (data.reason) {{
          const ta = document.getElementById('reason-' + idx);
          if (ta) ta.value = data.reason;
        }}
      }} else if (data.answers || data.notes) {{
        // Legacy MCQ shape: keep their freeform notes as a reason hint, leave verdict blank
        if (data.notes) {{
          const ta = document.getElementById('reason-' + idx);
          if (ta) ta.value = data.notes;
          const row = document.getElementById('reason-row-' + idx);
          if (row) row.style.display = 'block';
        }}
      }}
      const btn = card.querySelector('.save-btn');
      btn.classList.add('saved'); btn.textContent = '✓ Saved';
    }} catch (_) {{}}
  }});
  updateProgress();
}});
</script>
</body></html>"""
    out_html = OUT / "setups3.html"
    out_html.write_text(html, encoding="utf-8")
    print(f"Wrote {out_html} ({len(cards)} cards)")
    print(f"Public URL: https://setups.claudezeeshan.com/setups3.html")


if __name__ == "__main__":
    main()
