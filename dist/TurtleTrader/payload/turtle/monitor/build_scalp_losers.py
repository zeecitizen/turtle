"""build_scalp_losers.py — MODULE: the FAST-SCALP (M1) loser loop.

Zee's real Feb-11 method is a fast scalp: many entries/day, harvest the micro-move in
seconds-minutes, ~92% WR. This builds the M1 fast-scalp, finds the LOSING TAKE setups,
and renders them with comment boxes so Zee can say what's wrong → tighten toward 92%.

M1, loose entry (more frequency) + fast harvest exit (arm1.5/give0.8, UHV-low SL).
Page: setups.claudezeeshan.com/losers.html  (key "loser_NNN").
"""
from __future__ import annotations
import json, sys, time
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
import build_entry_review_m5 as B
from build_entry_review_m5 import render
from case_engine import extract_features, describe
from pattern_matcher import classify
from feb11_exit_validation import load_ticks_by_date, find_idx, simulate_exit
import screener_canonical_uhv_m1 as S

OUT = Path(__file__).parent / "setup_labels"
EXIT = {"tp": 5.0, "sl": "uhv", "arm": 1.5, "give": 0.8}   # fast harvest
LOT = 0.10
BUST = int(time.time())
# fast-scalp loose entry (M1): more frequency, WR then tightened via Zee's loser comments
B.UHV_BODY_MIN = 0.2; B.MIN_ORIGIN_BREAK = 0.3; B.ER_MIN = 0.25; B.LB = 45

HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fast-scalp losers — why?</title><style>
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
</style></head><body><header><h1>🔍 Fast-scalp (M1) losers — what went wrong?</h1>
<div class="sub">__SUB__ &nbsp; Har loser pe likho: kya ghalat tha / tum yeh kyun na lete. Isse WR 80%→92% karenge.</div></header>
<div id="app"></div><script>
const S=__J__;let L={};
async function ld(){try{L=await(await fetch('/api/labels')).json()}catch(e){}rn()}
async function sv(id){const v=document.getElementById('t_'+id).value;const r=await fetch('/api/labels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx:id,who:'zee',label:v})});const e=document.getElementById('s_'+id);e.textContent=r.ok?'saved ✓':'err';setTimeout(()=>e.textContent='',2000)}
function rn(){const a=document.getElementById('app');a.innerHTML='';S.forEach(s=>{const p=(L[s.id]&&L[s.id].zee)||'';const notes=(s.notes||[]).map(n=>'• '+n).join('<br>');const d=document.createElement('div');d.className='card';d.innerHTML=`<div class="title">🧩 ${s.title}</div><div class="cap">${s.cap}</div><img src="${s.png}" loading="lazy"><div class="notes">${notes}</div><div class="row"><textarea id="t_${s.id}" placeholder="Why did this lose? / what would you do?">${p.replace(/</g,'&lt;')}</textarea><button onclick="sv('${s.id}')">Save</button><span class="saved" id="s_${s.id}"></span></div>`;a.appendChild(d)})}
ld();</script></body></html>"""


def main():
    csvs = sorted(S.TICK_DIR.glob("shano_ticks_2026-*.csv"))
    m1 = S.build_m1(csvs)
    ticks = load_ticks_by_date()
    for old in OUT.glob("loser_*.png"):
        try: old.unlink()
        except Exception: pass
    losers = []
    for s in B.detect_full(m1):
        f = extract_features(m1, s["o"], s["u"], s["i"], s["side"])
        if classify(f, s["side"])[1] != "TAKE": continue
        dt = s["open_t"] + timedelta(minutes=1)
        tk = ticks.get(dt.strftime("%Y-%m-%d"))
        if not tk: continue
        idx = find_idx(tk, dt)
        if idx is None: continue
        reason, p = simulate_exit(tk, idx, s["side"], s["entry"], EXIT, abs(s["entry"] - s["sl"]))
        usd = p * LOT * 100
        if usd >= 0: continue
        losers.append((s, usd, reason, f))
    meta = []
    for k, (s, usd, reason, f) in enumerate(losers, 1):
        png = OUT / f"loser_{k:03d}.png"
        if render(dict(s), m1, png):
            title, notes = describe(f, s["side"])
            meta.append({"id": f"loser_{k:03d}", "png": f"loser_{k:03d}.png?v={BUST}",
                         "title": f"#{k} {title} (M1 scalp)",
                         "cap": f"{s['side']} → ${usd:.1f} loss ({reason}) · {s['open_t'].strftime('%Y-%m-%d %H:%M')}",
                         "notes": notes})
    sub = f"{len(losers)} losing M1 fast-scalp setups (0.1 lot, fast harvest) — the ~20% that lost"
    (OUT / "losers.html").write_text(HTML.replace("__J__", json.dumps(meta)).replace("__SUB__", sub), encoding="utf-8")
    print(f"rendered {len(meta)} scalp losers -> losers.html")


if __name__ == "__main__":
    main()
