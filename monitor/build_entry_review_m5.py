"""build_entry_review_m5.py — MODULE 1 (v2): render the CONFIRMED-RULE detector's
entries on M5 (MT5 tick-count volume) for Zee to proof-read.

Implements the rules Zee confirmed this session:
  - trend = ONE camel-hump (HH/HL) BEFORE the retracement; ranging (both legs) rejected
  - retracement origin = counter-trend candle whose BODY breaks the prior
    same-direction candle's extreme
  - UHV = highest-volume counter-trend candle WITHIN the retracement (local peak)
  - breakout = the FIRST candle whose body crosses the UHV extreme (correct colour)
Timeframe M5; volume = MT5 tick-count magnitude; "red UHV" = bearish candle.

Output served by serve_setup_labels.py → setups.claudezeeshan.com/entries.html
Label ids "m5_001".. (fresh; old M1 e-labels preserved).
"""
from __future__ import annotations
import argparse, csv, json, sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
from screener_canonical_uhv_m1 import Bar, TICK_DIR

sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd
import mplfinance as mpf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(r"c:/Users/zeesh/Documents/GitHub/turtle")
OUT = REPO / "monitor" / "setup_labels"
OUT.mkdir(parents=True, exist_ok=True)
LB = 45
SL_BUF = 1.5


def build_m5(csvs):
    rows = []
    for p in csvs:
        with p.open(encoding="utf-8", errors="ignore") as f:
            for r in csv.DictReader(f):
                ts = r.get("ts_broker") or r.get("ts") or r.get("t")
                if not ts: continue
                if "." in ts.split(" ", 1)[-1]: ts = ts.rsplit(".", 1)[0]
                try: dt = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S"); mid = (float(r["bid"]) + float(r["ask"])) / 2
                except Exception: continue
                rows.append((dt, mid))
    rows.sort(); b = {}
    for dt, mid in rows:
        k = dt.replace(minute=(dt.minute // 5) * 5, second=0, microsecond=0)
        if k not in b: b[k] = [mid, mid, mid, mid, 1]
        else:
            e = b[k]; e[1] = max(e[1], mid); e[2] = min(e[2], mid); e[3] = mid; e[4] += 1
    return [Bar(k, *b[k]) for k in sorted(b)]


def prior_opp(bars, o, side):
    for k in range(o - 1, max(o - 12, -1), -1):
        if side == "BUY" and bars[k].is_bull: return bars[k].l
        if side == "SELL" and bars[k].is_bear: return bars[k].h
    return None

def is_origin(bars, o, side):
    if side == "BUY" and not bars[o].is_bear: return False
    if side == "SELL" and not bars[o].is_bull: return False
    e = prior_opp(bars, o, side)
    return e is not None and (bars[o].c < e if side == "BUY" else bars[o].c > e)

def humps(bars, at):
    day = bars[at].t.date(); lo = at
    while lo > 0 and (at - lo) < LB and bars[lo - 1].t.date() == day: lo -= 1
    seg = bars[lo:at]
    if len(seg) < 5: return 0, 0
    up = 0; mn = seg[0].l
    for b in seg: mn = min(mn, b.l); up = max(up, b.h - mn)
    dn = 0; mx = seg[0].h
    for b in seg: mx = max(mx, b.h); dn = max(dn, mx - b.l)
    return up, dn

def trend_ok(bars, o, side, minh=4.0, R=1.6):
    up, dn = humps(bars, o)
    return (up >= minh and up >= dn * R) if side == "BUY" else (dn >= minh and dn >= up * R)


def retr_zone_start(bars, o, side, back=12):
    """The retracement ZONE begins at the swing extreme the pullback comes from —
    the UHV (highest-vol counter-trend candle) can lie here, BEFORE the body-break
    origin (Zee, 2026-07-25). Return the index of that swing high (BUY) / low (SELL)."""
    look = max(0, o - back)
    if side == "BUY":
        return max(range(look, o + 1), key=lambda k: bars[k].h)
    return min(range(look, o + 1), key=lambda k: bars[k].l)


def detect_full(bars):
    out = []; n = len(bars)
    for i in range(3, n):
        b = bars[i]
        for side in ("BUY", "SELL"):
            if side == "BUY" and not b.is_bull: continue
            if side == "SELL" and not b.is_bear: continue
            o = None
            for j in range(i - 1, max(i - LB, 0), -1):
                if is_origin(bars, j, side): o = j; break
            if o is None or not trend_ok(bars, o, side): continue
            rs = retr_zone_start(bars, o, side)   # UHV can be BEFORE the origin (Zee 2026-07-25)
            best = None
            for k in range(rs, i):
                c = bars[k]; col = c.is_bear if side == "BUY" else c.is_bull
                if not col: continue
                if k - 1 >= 0 and bars[k - 1].v >= c.v: continue
                if k + 1 < n and bars[k + 1].v >= c.v: continue
                if best is None or c.v > bars[best].v: best = k
            if best is None: continue
            U = bars[best]
            lvl = U.h if side == "BUY" else U.l
            first = None
            for k in range(best + 1, i + 1):
                cc = bars[k]
                if side == "BUY" and cc.is_bull and cc.c > lvl: first = k; break
                if side == "SELL" and cc.is_bear and cc.c < lvl: first = k; break
            if first != i: continue
            sl = U.l - SL_BUF if side == "BUY" else U.h + SL_BUF
            out.append({"side": side, "i": i, "o": o, "u": best,
                        "entry": round(b.c, 2), "sl": round(sl, 2),
                        "open_t": b.t, "origin_t": bars[o].t, "uhv_t": U.t,
                        "uhv_vol": U.v, "b_vol": b.v})
    return out


def render(s, bars, png):
    oi, ui, bi = s["o"], s["u"], s["i"]
    lo = max(0, oi - 12); hi = min(len(bars), bi + 8)
    seg = bars[lo:hi]
    if len(seg) < 6: return False
    df = pd.DataFrame({"Open": [b.o for b in seg], "High": [b.h for b in seg],
                       "Low": [b.l for b in seg], "Close": [b.c for b in seg],
                       "Volume": [b.v for b in seg]},
                      index=pd.DatetimeIndex([b.t for b in seg], name="Datetime"))
    rng = max(df["High"].max() - df["Low"].min(), 1e-6)
    side = s["side"]
    aps = [mpf.make_addplot([s["entry"]] * len(df), color="#2563eb", width=1.0),
           mpf.make_addplot([s["sl"]] * len(df), color="#dc2626", linestyle=":", width=1.0)]
    title = f"{side} M5 | entry {s['entry']} SL {s['sl']} | UHVvol {s['uhv_vol']} Bvol {s['b_vol']} | {s['open_t'].strftime('%Y-%m-%d %H:%M')}"
    try:
        fig, axes = mpf.plot(df, type="candle", style="charles", volume=True, addplot=aps,
                             returnfig=True, figsize=(13, 7), title=title, warn_too_much_data=100000, tight_layout=True)
        ax = axes[0]
        def lab(idx, txt, above, color):
            b = bars[idx]; x = idx - lo
            y = b.h + rng * 0.09 if above else b.l - rng * 0.09
            ax.annotate(txt, (x, y), ha="center", va="bottom" if above else "top",
                        fontsize=9, fontweight="bold", color=color,
                        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=color, alpha=0.9))
        lab(oi, "RET.STRTS", False, "#9333ea")   # retracement starts (origin)
        lab(ui, "UHV", True, "#b8860b")           # ultra-high-volume candle
        lab(bi, "BRKOUT", side == "BUY", "#16a34a" if side == "BUY" else "#dc2626")  # breakout
        fig.savefig(png, dpi=72, bbox_inches="tight"); plt.close(fig); return True
    except Exception as e:
        print("render err", e); plt.close("all"); return False


HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Entry Proof-Read M5</title><style>
body{font-family:system-ui,Segoe UI,Arial;margin:0;background:#0b0f14;color:#e6edf3}
header{position:sticky;top:0;background:#111826;padding:14px 18px;border-bottom:1px solid #223;z-index:5}
h1{font-size:18px;margin:0}.sub{color:#9aa7b4;font-size:13px;margin-top:4px}
.card{margin:18px;background:#111826;border:1px solid #223;border-radius:10px;overflow:hidden}
.card img{width:100%;display:block;background:#fff}.meta{padding:8px 14px;color:#9aa7b4;font-size:13px;border-top:1px solid #223}
.row{display:flex;gap:8px;padding:10px 14px}textarea{flex:1;min-height:70px;background:#0b0f14;color:#e6edf3;border:1px solid #334;border-radius:8px;padding:8px;font-size:14px}
button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:9px 16px;cursor:pointer}.saved{color:#16a34a;font-size:13px;margin-left:8px}
</style></head><body><header><h1>🦅 Module 1 (M5) — Entry Proof-Read</h1>
<div class="sub">Confirmed rules on M5 (MT5 volume). 🟣 O=origin 🔻 Y=UHV ▲/▼ B=breakout, blue=entry, red=SL. Har entry: valid? / kya ghalat?</div></header>
<div id="app"></div><script>
const S=__J__;let L={};
async function ld(){try{L=await(await fetch('/api/labels')).json()}catch(e){}rn()}
async function sv(id){const v=document.getElementById('t_'+id).value;const r=await fetch('/api/labels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx:id,who:'zee',label:v})});const e=document.getElementById('s_'+id);e.textContent=r.ok?'saved ✓':'err';setTimeout(()=>e.textContent='',2000)}
function rn(){const a=document.getElementById('app');a.innerHTML='';S.forEach(s=>{const p=(L[s.id]&&L[s.id].zee)||'';const d=document.createElement('div');d.className='card';d.innerHTML=`<img src="${s.png}" loading="lazy"><div class="meta">#${s.id} ${s.side} ${s.open_t} · UHVvol ${s.uhv_vol} · Bvol ${s.b_vol}</div><div class="row"><textarea id="t_${s.id}" placeholder="valid? / kya ghalat...">${p.replace(/</g,'&lt;')}</textarea><button onclick="sv('${s.id}')">Save</button><span class="saved" id="s_${s.id}"></span></div>`;a.appendChild(d)})}
ld();</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=8); args = ap.parse_args()
    csvs = sorted(TICK_DIR.glob("shano_ticks_2026-*.csv"))[-args.days:]
    bars = build_m5(csvs)
    print(f"M5 bars: {len(bars)}")
    setups = detect_full(bars)
    print(f"detected: {len(setups)}")
    for old in OUT.glob("m5_*.png"):
        try: old.unlink()
        except Exception: pass
    meta = []
    for k, s in enumerate(setups, 1):
        sid = f"m5_{k:03d}"; png = OUT / f"m5_{k:03d}.png"
        if render(s, bars, png):
            meta.append({"id": sid, "png": f"m5_{k:03d}.png", "side": s["side"],
                         "open_t": s["open_t"].strftime("%Y-%m-%d %H:%M"),
                         "uhv_vol": s["uhv_vol"], "b_vol": s["b_vol"]})
    (OUT / "entries.html").write_text(HTML.replace("__J__", json.dumps(meta)), encoding="utf-8")
    print(f"rendered {len(meta)} → entries.html  (setups.claudezeeshan.com/entries.html)")


if __name__ == "__main__":
    main()
