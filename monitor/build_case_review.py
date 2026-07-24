"""build_case_review.py — Claude pre-labels candidate UHV setups; Zee clicks
Correct / Wrong. Each confirmed case grows the CBR database (cases.json).

Flow:
  1. seed the case DB from Zee's M5 proof-reads (case_engine.build_cases)
  2. generate NEW candidate setups from other tick-days (detect_full on M5)
  3. for each candidate, kNN-classify against the DB -> Claude's proposed verdict
     + nearest case id + reason
  4. render each chart and build a Correct/Wrong page (setups.claudezeeshan.com)
Zee's click saves {idx, label:"correct"/"wrong"} -> apply_case_labels.py folds
the confirmed verdicts back into cases.json.
"""
from __future__ import annotations
import argparse, json, sys, time
from datetime import timedelta

BUST = int(time.time())  # cache-buster so browsers reload freshly-rendered charts
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
from build_entry_review_m5 import build_m5, detect_full, render
from case_engine import build_cases, extract_features, knn_verdict, describe
import screener_canonical_uhv_m1 as S

OUT = Path(__file__).parent / "setup_labels"


HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Case Review — Correct/Wrong</title><style>
body{font-family:system-ui,Segoe UI,Arial;margin:0;background:#0b0f14;color:#e6edf3}
header{position:sticky;top:0;background:#111826;padding:14px 18px;border-bottom:1px solid #223;z-index:5}
h1{font-size:18px;margin:0}.sub{color:#9aa7b4;font-size:13px;margin-top:4px}
.card{margin:18px;background:#111826;border:1px solid #223;border-radius:10px;overflow:hidden}
.card img{width:100%;display:block;background:#fff}
.title{padding:12px 14px 2px;font-size:16px;font-weight:600;color:#e6edf3}
.caption{padding:0 14px 10px;color:#9aa7b4;font-size:13px}
.notes{padding:2px 14px 6px;color:#9aa7b4;font-size:13px;line-height:1.6}
.guess{padding:6px 14px 10px;font-size:15px}
.v{color:#16a34a;font-weight:600}.x{color:#dc2626;font-weight:600}
.row{display:flex;gap:10px;padding:10px 14px}
button{border:0;border-radius:8px;padding:11px 22px;font-size:15px;cursor:pointer;color:#fff}
.ok{background:#16a34a}.no{background:#dc2626}.done{color:#9aa7b4;font-size:14px;margin-left:6px;align-self:center}
input.why{flex:1;min-width:120px;background:#0b0f14;color:#e6edf3;border:1px solid #334;border-radius:8px;padding:9px 10px;font-size:14px}
</style></head><body><header><h1>🧩 Case Review — Claude guesses, you confirm</h1>
<div class="sub">Har setup pe Claude ka andaaza dikhta hai. Sahi ho to ✓ Correct, warna ✗ Wrong. Bas.</div></header>
<div id="app"></div><script>
const S=__J__;let L={};
async function ld(){try{L=await(await fetch('/api/labels')).json()}catch(e){}rn()}
async function sv(id,val){let lab=val;if(val==='wrong'){const w=(document.getElementById('w_'+id).value||'').trim();lab='wrong'+(w?': '+w:'');}await fetch('/api/labels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx:id,who:'zee',label:lab})});document.getElementById('d_'+id).textContent=val==='correct'?'✓ saved':'✗ saved';}
function rn(){const a=document.getElementById('app');a.innerHTML='';S.forEach(s=>{const prev=(L[s.id]&&L[s.id].zee)||'';const g=s.guess==='valid'?`<span class="v">VALID</span>`:`<span class="x">INVALID</span>`;const d=document.createElement('div');d.className='card';d.innerHTML=`<div class="title">🧩 ${s.title}</div><div class="caption">${s.caption}</div><img src="${s.png}" loading="lazy"><div class="notes">${(s.notes||[]).map(n=>'• '+n).join('<br>')}</div><div class="guess">🤖 Claude verdict: ${g} &nbsp;—&nbsp; similar to: ${s.near_desc} · conf ${s.conf}</div><div class="row"><button class="ok" onclick="sv('${s.id}','correct')">✓ Correct</button><button class="no" onclick="sv('${s.id}','wrong')">✗ Wrong</button><input class="why" id="w_${s.id}" placeholder="Why wrong? (kya ghalat hai)" value="${(prev&&prev.indexOf('wrong:')===0)?prev.slice(6).trim().replace(/"/g,'&quot;'):''}"><span class="done" id="d_${s.id}">${prev?(prev==='correct'?'✓ saved':'✗ saved'):''}</span></div>`;a.appendChild(d)})}
ld();</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-day", type=int, default=20)  # candidates from earlier window
    ap.add_argument("--to-day", type=int, default=9)
    ap.add_argument("--max", type=int, default=40)
    args = ap.parse_args()

    cases = build_cases()
    print(f"seed DB: {len(cases)} cases")

    all_csvs = sorted(S.TICK_DIR.glob("shano_ticks_2026-*.csv"))
    cand_csvs = all_csvs[-args.from_day:-args.to_day] if args.to_day else all_csvs[-args.from_day:]
    bars = build_m5(cand_csvs)
    setups = detect_full(bars)
    print(f"candidate setups: {len(setups)}")
    setups = setups[:args.max]

    for old in OUT.glob("case_*.png"):
        try: old.unlink()
        except Exception: pass

    meta = []
    for k, s in enumerate(setups, 1):
        f = extract_features(bars, s["o"], s["u"], s["i"], s["side"])
        valid, near, conf = knn_verdict(f, cases, k=3, side=s["side"])
        near_case = next((c for c in cases if c["id"] == near), None)
        if near_case:
            nt, _ = describe(near_case["features"], near_case.get("side", s["side"]))
            near_desc = near_case.get("reason") or nt
        else:
            near_desc = "no similar case yet"
        title, notes = describe(f, s["side"])
        png = OUT / f"case_{k:03d}.png"
        s_render = dict(s); s_render["entry"] = s["entry"]  # render expects entry/sl/o/u/i/side
        if render(s_render, bars, png):
            caption = f"{s['side']} M5 · entry {s['entry']} · SL {s['sl']} · {s['open_t'].strftime('%Y-%m-%d %H:%M')}"
            meta.append({"id": f"case_{k:03d}", "png": f"case_{k:03d}.png?v={BUST}", "side": s["side"],
                         "title": f"#{k} {title}", "caption": caption, "notes": notes,
                         "guess": "valid" if valid else "invalid", "near_desc": near_desc,
                         "conf": f"{conf:.0%}"})
    (OUT / "entries.html").write_text(HTML.replace("__J__", json.dumps(meta)), encoding="utf-8")
    print(f"rendered {len(meta)} candidates -> entries.html (Correct/Wrong page)")
    print("Zee: setups.claudezeeshan.com/entries.html")


if __name__ == "__main__":
    main()
