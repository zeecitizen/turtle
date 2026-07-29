"""build_oanda_losers.py — OANDA fast-scalp (dom=0, 110/day) loser loop + profit report.

Detects on OANDA:XAUUSD M1 (real volume, from oanda_bridge), high-frequency config
(dom=0), fast-harvest+stop-cap exit. Reports per-day profit at 0.1 lot, and renders the
LOSING setups with comment boxes so Zee can say what's wrong -> tighten toward higher WR.
Page: setups.claudezeeshan.com/losers.html
"""
from __future__ import annotations
import csv, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
import build_entry_review_m5 as B
from build_entry_review_m5 import render
from case_engine import extract_features, describe

OUT = Path(__file__).parent / "setup_labels"
CF = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.csv")
LOT = 0.10
BUST = int(time.time())
# high-frequency fast-scalp config (Zee 2026-07-29): dom=0 -> ~110/day, ~78% WR
CFG = dict(UHV_BODY_MIN=0.0, MIN_ORIGIN_BREAK=0.0, ER_MIN=0.0, TREND_MIN_HUMP=0.5, TREND_DOM=0.0)
EXIT = dict(arm=0.3, give=0.2, tp=3.0, cap=3.0)

HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OANDA fast-scalp losers</title><style>
body{font-family:system-ui,Segoe UI,Arial;margin:0;background:#0b0f14;color:#e6edf3}
header{position:sticky;top:0;background:#111826;padding:14px 18px;border-bottom:1px solid #223;z-index:5}
h1{font-size:18px;margin:0}.sub{color:#b8c4d0;font-size:14px;margin-top:4px}
.card{margin:18px;background:#111826;border:1px solid #223;border-radius:10px;overflow:hidden}
.card img{width:100%;display:block;background:#fff}
.title{padding:12px 14px 2px;font-size:16px;font-weight:600}
.cap{padding:0 14px 10px;color:#f87171;font-size:15px;font-weight:600}
.notes{padding:2px 14px 8px;color:#e6edf3;font-size:15px;line-height:1.75}
.row{display:flex;gap:8px;padding:10px 14px}
textarea{flex:1;min-height:60px;background:#0b0f14;color:#e6edf3;border:1px solid #334;border-radius:8px;padding:9px;font-size:14px}
button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:10px 18px;cursor:pointer}
.saved{color:#16a34a;font-size:13px;align-self:center}
</style></head><body><header><h1>🔍 OANDA fast-scalp losers — what went wrong?</h1>
<div class="sub">__SUB__ &nbsp; Har loser pe likho: kya ghalat tha / tum yeh kyun na lete. Isse WR upar karenge.</div></header>
<div id="app"></div><script>
const S=__J__;let L={};
async function ld(){try{L=await(await fetch('/api/labels')).json()}catch(e){}rn()}
async function sv(id){const v=document.getElementById('t_'+id).value;const r=await fetch('/api/labels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx:id,who:'zee',label:v})});const e=document.getElementById('s_'+id);e.textContent=r.ok?'saved ✓':'err';setTimeout(()=>e.textContent='',2000)}
function rn(){const a=document.getElementById('app');a.innerHTML='';S.forEach(s=>{const p=(L[s.id]&&L[s.id].zee)||'';const notes=(s.notes||[]).map(n=>'• '+n).join('<br>');const d=document.createElement('div');d.className='card';d.innerHTML=`<div class="title">🧩 ${s.title}</div><div class="cap">${s.cap}</div><img src="${s.png}" loading="lazy"><div class="notes">${notes}</div><div class="row"><textarea id="t_${s.id}" placeholder="Why did this lose? / what would you do?">${p.replace(/</g,'&lt;')}</textarea><button onclick="sv('${s.id}')">Save</button><span class="saved" id="s_${s.id}"></span></div>`;a.appendChild(d)})}
ld();</script></body></html>"""


def load_bars():
    bars = []
    with CF.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc).replace(tzinfo=None)
            bars.append(B.Bar(t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), int(r["volume"])))
    bars.sort(key=lambda b: b.t)
    return bars


def bar_exit(bars, i, side, entry):
    peak = 0.0
    for k in range(i + 1, min(i + 60, len(bars))):
        bb = bars[k]; favx = (entry - bb.l) if side == "SELL" else (bb.h - entry); peak = max(peak, favx)
        advc = (bb.c - entry) if side == "SELL" else (entry - bb.c)
        if favx >= EXIT["tp"]: return EXIT["tp"], "tp"
        if advc >= EXIT["cap"]: return -EXIT["cap"], "cap"
        favc = (entry - bb.c) if side == "SELL" else (bb.c - entry)
        if peak >= EXIT["arm"] and (peak - favc) >= EXIT["give"]: return peak - EXIT["give"], "harvest"
    bb = bars[min(i + 60, len(bars)) - 1]
    return ((entry - bb.c) if side == "SELL" else (bb.c - entry)), "eod"


def main():
    for k, v in CFG.items(): setattr(B, k, v)
    bars = load_bars()
    tmap = {b.t: i for i, b in enumerate(bars)}
    hrs = (bars[-1].t - bars[0].t).total_seconds() / 3600
    setups = B.detect_full(bars)
    pnls = []; losers = []
    for s in setups:
        i = tmap.get(s["open_t"])
        if i is None: continue
        pts, how = bar_exit(bars, i, s["side"], s["entry"]); usd = pts * LOT * 100
        pnls.append(usd)
        if usd < 0: losers.append((s, usd, how))
    w = [p for p in pnls if p > 0]
    wr = 100 * len(w) / max(len(pnls), 1); net = sum(pnls); perday = net / hrs * 24
    print(f"OANDA fast-scalp (dom=0): {len(pnls)} setups over {hrs:.1f}h ({len(pnls)/hrs*24:.0f}/day, {len(pnls)/hrs:.1f}/hr)")
    print(f"  WR {wr:.0f}%  net ${net:+.1f}  => PER DAY ~${perday:+.1f} @0.1 lot  (avg ${net/max(len(pnls),1):+.2f}/trade)")
    for old in OUT.glob("loser_*.png"):
        try: old.unlink()
        except Exception: pass
    meta = []
    for k, (s, usd, how) in enumerate(losers, 1):
        png = OUT / f"loser_{k:03d}.png"
        if render(dict(s), bars, png):
            title, notes = describe(extract_features(bars, s["o"], s["u"], s["i"], s["side"]), s["side"])
            meta.append({"id": f"loser_{k:03d}", "png": f"loser_{k:03d}.png?v={BUST}",
                         "title": f"#{k} {title}",
                         "cap": f"{s['side']} → ${usd:.1f} loss ({how}) · {s['open_t'].strftime('%m-%d %H:%M')}UTC",
                         "notes": notes})
    sub = f"{len(losers)} losing setups of {len(pnls)} ({wr:.0f}% WR, ~{perday:+.0f}$/day @0.1 lot). OANDA dom=0 fast-scalp."
    (OUT / "losers.html").write_text(HTML.replace("__J__", json.dumps(meta)).replace("__SUB__", sub), encoding="utf-8")
    print(f"rendered {len(meta)} losers -> losers.html")


if __name__ == "__main__":
    main()
