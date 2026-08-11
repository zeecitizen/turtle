"""build_entry_review.py — MODULE 1: render the CURRENT detector's UHV entries
as charts for Zeeshan to proof-read.

Reuses the live entry logic (screener_canonical_uhv_m1.detect) — the same
canonical UHV-breakout detection the EA mirrors — and renders each detected
entry as an M1 candle chart with markers:
   O = retracement origin,  Y = UHV candle,  B = breakout candle,
   entry / SL / TP horizontal lines, volume sub-pane.

Output (served by serve_setup_labels.py → setups.claudezeeshan.com):
   monitor/setup_labels/entry_NNN.png
   monitor/setup_labels/entries.html      (proof-read UI, ids "e001"…)
Labels save to the same zee_labels.json (append-only, e-prefixed keys — old
M5 labels 1..48 are preserved).

Usage: py monitor/build_entry_review.py --days 12 --max 40
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
from screener_canonical_uhv_m1 import build_m1, detect, TICK_DIR  # reuse detector

sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd
import mplfinance as mpf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(r"c:/Users/zeesh/Documents/GitHub/turtle")
OUT = REPO / "monitor" / "setup_labels"
OUT.mkdir(parents=True, exist_ok=True)


def bars_index(bars):
    return {b.t: i for i, b in enumerate(bars)}


def slice_df(bars, i0, i1):
    seg = bars[i0:i1]
    idx = [b.t for b in seg]
    df = pd.DataFrame({
        "Open":  [b.o for b in seg],
        "High":  [b.h for b in seg],
        "Low":   [b.l for b in seg],
        "Close": [b.c for b in seg],
        "Volume":[b.v for b in seg],
    }, index=pd.DatetimeIndex(idx, name="Datetime"))
    return df, seg


def marker_series(seg, target_t, value_fn):
    return [value_fn(b) if b.t == target_t else float("nan") for b in seg]


def render(setup, bars, bidx, png_path):
    try:
        o_t = datetime.strptime(setup.origin_t, "%Y-%m-%d %H:%M")
        u_t = datetime.strptime(setup.uhv_t, "%Y-%m-%d %H:%M")
        b_t = datetime.strptime(setup.breakout_t, "%Y-%m-%d %H:%M")
    except ValueError:
        return False
    oi = bidx.get(o_t); ui = bidx.get(u_t); bi = bidx.get(b_t)
    if ui is None or bi is None:
        return False
    lo = max(0, (oi if oi is not None else ui) - 15)
    hi = min(len(bars), bi + 26)
    df, seg = slice_df(bars, lo, hi)
    if len(df) < 6:
        return False
    rng = max(df["High"].max() - df["Low"].min(), 1e-6)
    side = setup.side

    aps = []
    # SL / TP / entry horizontal lines
    aps.append(mpf.make_addplot([setup.entry]*len(df), color="#2563eb", width=1.0))
    aps.append(mpf.make_addplot([setup.sl]*len(df), color="#dc2626", linestyle=":", width=1.0))
    aps.append(mpf.make_addplot([setup.tp]*len(df), color="#16a34a", linestyle=":", width=1.0))
    # O origin (below), Y uhv (above, gold), B breakout (arrow)
    o_ser = marker_series(seg, o_t, lambda b: b.l - rng*0.06) if oi is not None else [float("nan")]*len(seg)
    y_ser = marker_series(seg, u_t, lambda b: b.h + rng*0.06)
    b_ser = marker_series(seg, b_t, lambda b: (b.l - rng*0.10) if side == "BUY" else (b.h + rng*0.10))
    if any(v == v for v in o_ser):
        aps.append(mpf.make_addplot(o_ser, type="scatter", marker="o", color="#9333ea", markersize=90))
    aps.append(mpf.make_addplot(y_ser, type="scatter", marker="v", color="goldenrod", markersize=180))
    aps.append(mpf.make_addplot(b_ser, type="scatter",
                                marker="^" if side == "BUY" else "v",
                                color="#16a34a" if side == "BUY" else "#dc2626", markersize=220))

    title = (f"{side}  |  entry {setup.entry}  SL {setup.sl}  TP {setup.tp}  |  "
             f"UHV vol {setup.uhv_vol}  Bvol {setup.breakout_vol}  |  {setup.open_t}")
    try:
        fig, _ = mpf.plot(df, type="candle", style="charles", volume=True,
                          addplot=aps, returnfig=True, figsize=(13, 7),
                          title=title, warn_too_much_data=100000,
                          tight_layout=True)
        fig.savefig(png_path, dpi=72, bbox_inches="tight")
        plt.close(fig)
        return True
    except Exception as e:
        print(f"  render error: {e}")
        try: plt.close("all")
        except Exception: pass
        return False


HTML_HEAD = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Entry Proof-Read — Module 1</title>
<style>
 body{font-family:system-ui,Segoe UI,Arial;margin:0;background:#0b0f14;color:#e6edf3}
 header{position:sticky;top:0;background:#111826;padding:14px 18px;border-bottom:1px solid #223;z-index:5}
 h1{font-size:18px;margin:0}
 .sub{color:#9aa7b4;font-size:13px;margin-top:4px}
 .card{margin:18px;background:#111826;border:1px solid #223;border-radius:10px;overflow:hidden}
 .card img{width:100%;display:block;background:#fff}
 .meta{padding:8px 14px;color:#9aa7b4;font-size:13px;border-top:1px solid #223}
 .row{display:flex;gap:8px;padding:10px 14px;align-items:flex-start}
 textarea{flex:1;min-height:70px;background:#0b0f14;color:#e6edf3;border:1px solid #334;border-radius:8px;padding:8px;font-size:14px}
 button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:9px 16px;font-size:14px;cursor:pointer}
 .saved{color:#16a34a;font-size:13px;margin-left:8px}
 .legend{color:#9aa7b4;font-size:13px}
</style></head><body>
<header><h1>🦅 Module 1 — Entry Proof-Read</h1>
<div class="sub">Har entry ko dekho: kya yeh ek VALID UHV breakout hai? &nbsp; <span class="legend">🟣 O=origin &nbsp; 🔻 Y=UHV &nbsp; ▲/▼ B=breakout &nbsp; blue=entry, red=SL, green=TP</span></div></header>
<div id="app"></div>
<script>
const SETUPS = __SETUPS_JSON__;
let LABELS = {};
async function loadLabels(){ try{ LABELS = await (await fetch('/api/labels')).json(); }catch(e){} render(); }
async function save(id){
  const v = document.getElementById('t_'+id).value;
  const r = await fetch('/api/labels',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({idx:id, who:'zee', label:v})});
  const el = document.getElementById('s_'+id); el.textContent = r.ok ? 'saved ✓' : 'error';
  setTimeout(()=>el.textContent='',2000);
}
function render(){
  const app = document.getElementById('app'); app.innerHTML='';
  SETUPS.forEach(s=>{
    const prev = (LABELS[s.id]&&LABELS[s.id].zee)||'';
    const div = document.createElement('div'); div.className='card';
    div.innerHTML = `<img src="${s.png}" loading="lazy">
      <div class="meta">#${s.id} &nbsp; ${s.side} &nbsp; ${s.open_t} &nbsp; UHVvol ${s.uhv_vol} · Bvol ${s.breakout_vol}</div>
      <div class="row"><textarea id="t_${s.id}" placeholder="valid? / kya ghalat hai...">${prev.replace(/</g,'&lt;')}</textarea>
      <button onclick="save('${s.id}')">Save</button><span class="saved" id="s_${s.id}"></span></div>`;
    app.appendChild(div);
  });
}
loadLabels();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=12)
    ap.add_argument("--max", type=int, default=40)
    args = ap.parse_args()

    tick_csvs = sorted(TICK_DIR.glob("shano_ticks_2026-*.csv"))[-args.days:]
    if not tick_csvs:
        print("no tick csvs"); return
    print(f"Loading {len(tick_csvs)} tick CSVs ({tick_csvs[0].stem[-10:]} … {tick_csvs[-1].stem[-10:]})")
    bars = build_m1(tick_csvs)
    print(f"Built {len(bars)} M1 bars")
    fires = detect(bars)
    print(f"Detected {len(fires)} entries")
    fires = fires[-args.max:]  # most recent batch
    bidx = bars_index(bars)

    # clean old entry_*.png
    for old in OUT.glob("entry_*.png"):
        try: old.unlink()
        except Exception: pass

    setups_meta = []
    n = 0
    for k, s in enumerate(fires, start=1):
        sid = f"e{k:03d}"
        png = OUT / f"entry_{k:03d}.png"
        if render(s, bars, bidx, png):
            n += 1
            setups_meta.append({"id": sid, "png": f"entry_{k:03d}.png", "side": s.side,
                                "open_t": s.open_t, "uhv_vol": s.uhv_vol, "breakout_vol": s.breakout_vol})
    html = HTML_HEAD.replace("__SETUPS_JSON__", json.dumps(setups_meta))
    (OUT / "entries.html").write_text(html, encoding="utf-8")
    print(f"Rendered {n} setups → {OUT/'entries.html'}")
    print(f"Serve: py monitor/serve_setup_labels.py  → https://setups.claudezeeshan.com/entries.html")


if __name__ == "__main__":
    main()
