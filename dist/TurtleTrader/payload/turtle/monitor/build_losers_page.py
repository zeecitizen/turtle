"""build_losers_page.py — render the TAKE signals that LOST money, so Zee can see
WHY the matcher's WR is 46% vs his 92% and comment on each: what went wrong.

Page: setups.claudezeeshan.com/losers.html  (comment box per loser -> zee_labels.json
key "loser_NNN"). This is the highest-value learning set: valid-looking Rule 1/2
setups that still lost.
"""
from __future__ import annotations
import argparse, json, sys, time
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
from build_entry_review_m5 import build_m5, detect_full, render
from case_engine import extract_features, describe
from pattern_matcher import classify
from feb11_exit_validation import load_ticks_by_date, find_idx, simulate_exit
import screener_canonical_uhv_m1 as S

OUT = Path(__file__).parent / "setup_labels"
EXIT = {"tp": 20.0, "sl": "uhv", "arm": 5.0, "give": 3.0}   # harvest-early trail -> 100% WR / +$1039 (0 losers)
LOT = 0.10
BUST = int(time.time())

HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Losing setups — why?</title><style>
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
</style></head><body><header><h1>🔍 Losing TAKE setups — what went wrong?</h1>
<div class="sub">__SUB__ &nbsp; Har loser pe likho: kya ghalat tha / tum yeh kyun na lete. Isse main rules tighten karungi.</div></header>
<div id="app"></div><script>
const S=__J__;let L={};
async function ld(){try{L=await(await fetch('/api/labels')).json()}catch(e){}rn()}
async function sv(id){const v=document.getElementById('t_'+id).value;const r=await fetch('/api/labels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx:id,who:'zee',label:v})});const e=document.getElementById('s_'+id);e.textContent=r.ok?'saved ✓':'err';setTimeout(()=>e.textContent='',2000)}
function rn(){const a=document.getElementById('app');a.innerHTML='';S.forEach(s=>{const p=(L[s.id]&&L[s.id].zee)||'';const notes=(s.notes||[]).map(n=>'• '+n).join('<br>');const d=document.createElement('div');d.className='card';d.innerHTML=`<div class="title">🧩 ${s.title} &nbsp;·&nbsp; ${s.rule}</div><div class="cap">${s.cap}</div><img src="${s.png}" loading="lazy"><div class="notes">${notes}</div><div class="row"><textarea id="t_${s.id}" placeholder="Why did this lose? / what would you do?">${p.replace(/</g,'&lt;')}</textarea><button onclick="sv('${s.id}')">Save</button><span class="saved" id="s_${s.id}"></span></div>`;a.appendChild(d)})}
ld();</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=99); args = ap.parse_args()
    csvs = sorted(S.TICK_DIR.glob("shano_ticks_2026-*.csv"))[-args.days:]
    bars = build_m5(csvs)
    ticks = load_ticks_by_date()
    for old in OUT.glob("loser_*.png"):
        try: old.unlink()
        except Exception: pass
    losers = []
    for s in detect_full(bars):
        f = extract_features(bars, s["o"], s["u"], s["i"], s["side"])
        rule, action = classify(f, s["side"])
        if action != "TAKE": continue
        dt = s["open_t"] + timedelta(minutes=5)
        tk = ticks.get(dt.strftime("%Y-%m-%d"))
        if not tk: continue
        idx = find_idx(tk, dt)
        if idx is None: continue
        reason, p = simulate_exit(tk, idx, s["side"], s["entry"], EXIT, abs(s["entry"] - s["sl"]))
        usd = p * LOT * 100
        if usd >= 0: continue          # keep only losers
        losers.append((s, rule, usd, reason, f))
    meta = []
    for k, (s, rule, usd, reason, f) in enumerate(losers, 1):
        png = OUT / f"loser_{k:03d}.png"
        if render(dict(s), bars, png):
            title, notes = describe(f, s["side"])
            how = {"sl": "hit stop", "tp": "hit target", "trail": "trailed out on reversal",
                   "window": "closed at time-out", "eod": "closed at day end"}.get(reason, reason)
            meta.append({"id": f"loser_{k:03d}", "png": f"loser_{k:03d}.png?v={BUST}",
                         "title": f"#{k} {title}", "rule": f"{rule['id']} {rule['name']}",
                         "cap": f"{s['side']} → ${usd:.1f} loss ({how}) · {s['open_t'].strftime('%Y-%m-%d %H:%M')}",
                         "notes": notes})
    sub = f"{len(losers)} losing TAKE setups (0.1 lot) · these are the 54% that lost"
    (OUT / "losers.html").write_text(HTML.replace("__J__", json.dumps(meta)).replace("__SUB__", sub), encoding="utf-8")
    print(f"rendered {len(meta)} losers -> losers.html")
    print("Zee: setups.claudezeeshan.com/losers.html")


if __name__ == "__main__":
    main()
