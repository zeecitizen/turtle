"""build_trend_game.py — the TREND GAME (Zee's idea, 2026-08-02).

Instead of hard-coding yet another trend proxy, Claude LOOKS at the chart and calls it
("Zee, this is an uptrend, right?"). Zee grades each call 0/10 or 10/10. When Claude's
eye matches Zee's reliably, the AI judgment replaces the hand-tuned numeric rules.

This script renders N real setups as clean charts (no verdict shown — Claude must judge
blind), then `apply_game_calls.py` writes Claude's calls into the page for grading.

Page: setups.claudezeeshan.com/game.html  (grade -> zee_labels.json key "game_NN")
"""
from __future__ import annotations
import argparse, csv, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
import build_entry_review_m5 as B

OUT = Path(__file__).parent / "setup_labels"
CALLS = Path(__file__).parent / "game_calls.json"
G, R, GOLD, PUR, BLUE = "#16a34a", "#dc2626", "#b8860b", "#9333ea", "#2563eb"


def load(csv_path, tz_off):
    bars = []
    with open(csv_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc).replace(tzinfo=None)
            bars.append(B.Bar(t, float(r["open"]), float(r["high"]), float(r["low"]),
                              float(r["close"]), float(r["volume"])))
    bars.sort(key=lambda b: b.t)
    return bars, tz_off


def draw(bars, s, png, tz_off):
    """Chart with the mechanical marks (RET/UHV/BRKT) but NO hint about the outcome."""
    i = s["i"]
    lo = max(0, i - 45); hi = min(len(bars), i + 3)      # no future bars — judge blind
    seg = bars[lo:hi]
    if len(seg) < 15: return False
    fig, (ax, av) = plt.subplots(2, 1, figsize=(12, 6.2), gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    for x, b in enumerate(seg):
        col = G if b.c >= b.o else R
        ax.plot([x, x], [b.l, b.h], color=col, lw=1.2, solid_capstyle="round", zorder=1)
        ax.add_patch(Rectangle((x - 0.34, min(b.o, b.c)), 0.68, max(abs(b.c - b.o), 0.02),
                               facecolor=col, edgecolor=col, zorder=2))
        av.add_patch(Rectangle((x - 0.34, 0), 0.68, b.v, facecolor=col, alpha=0.7, edgecolor="none"))
    av.set_ylim(0, max(b.v for b in seg) * 1.15)
    for a in (ax, av): a.set_xlim(-0.7, len(seg) - 0.3)
    for idx, txt, col2 in ((s["o"], "RET", PUR), (s["u"], "UHV", GOLD),
                           (s["i"], "BRKT", G if s["side"] == "BUY" else R)):
        if lo <= idx < hi:
            b = bars[idx]
            ax.annotate(txt, (idx - lo, b.h + (b.h - b.l) * 0.5), ha="center", fontsize=9,
                        fontweight="bold", color=col2,
                        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=col2, alpha=0.95))
    ticks = list(range(0, len(seg), 8))
    ax.set_xticks([]); av.set_xticks(ticks)
    av.set_xticklabels([f"{(seg[t].t.hour + tz_off) % 24:02d}:{seg[t].t.minute:02d}" for t in ticks], fontsize=8)
    ax.grid(True, ls=":", alpha=0.3); av.grid(True, axis="y", ls=":", alpha=0.3)
    av.set_ylabel("Vol", fontsize=9)
    ax.set_title(f'Engine wants: {s["side"]}   (judge the CONTEXT — trend / take or skip)',
                 fontsize=12, fontweight="bold", loc="left")
    fig.tight_layout(); fig.savefig(png, dpi=85, bbox_inches="tight"); plt.close(fig)
    return True


HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trend Game — grade Claude</title><style>
body{font-family:system-ui,Segoe UI,Arial;margin:0;background:#0b0f14;color:#e6edf3}
header{position:sticky;top:0;background:#111826;padding:14px 18px;border-bottom:1px solid #223;z-index:5}
h1{font-size:18px;margin:0}.sub{color:#b8c4d0;font-size:14px;margin-top:5px;line-height:1.6}
.card{margin:18px;background:#111826;border:1px solid #223;border-radius:10px;overflow:hidden}
.card img{width:100%;display:block;background:#fff}
.title{padding:12px 14px 4px;font-size:16px;font-weight:700}
.call{margin:0 14px 10px;padding:10px 12px;background:#0d1622;border:1px solid #24405e;border-radius:8px;font-size:15px;line-height:1.6}
.call b{color:#7dd3fc}
.row{display:flex;gap:8px;padding:8px 14px 14px;flex-wrap:wrap}
button{border:0;border-radius:8px;padding:10px 18px;font-size:15px;cursor:pointer;color:#fff}
.ok{background:#16a34a}.no{background:#dc2626}
input.why{flex:1;min-width:160px;background:#0b0f14;color:#e6edf3;border:1px solid #334;border-radius:8px;padding:9px;font-size:14px}
.done{color:#b8c4d0;font-size:14px;align-self:center}
</style></head><body><header><h1>🎮 Trend Game — Claude ka call, tumhare marks</h1>
<div class="sub">__SUB__</div></header>
<div id="app"></div><script>
const S=__J__;let L={};
async function ld(){try{L=await(await fetch('/api/labels')).json()}catch(e){}rn()}
async function sv(id,mark){const w=(document.getElementById('w_'+id).value||'').trim();
 const lab=mark+(w?': '+w:'');
 await fetch('/api/labels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx:id,who:'zee',label:lab})});
 document.getElementById('d_'+id).textContent=mark==='10/10'?'✅ 10/10':'❌ 0/10';}
function rn(){const a=document.getElementById('app');a.innerHTML='';S.forEach(s=>{const p=(L[s.id]&&L[s.id].zee)||'';
 const d=document.createElement('div');d.className='card';
 d.innerHTML=`<div class="title">${s.title}</div>
 <div class="call">🤖 <b>Claude:</b> ${s.call}</div>
 <img src="${s.png}" loading="lazy">
 <div class="row"><button class="ok" onclick="sv('${s.id}','10/10')">✅ 10/10 sahi</button>
 <button class="no" onclick="sv('${s.id}','0/10')">❌ 0/10 ghalat</button>
 <input class="why" id="w_${s.id}" placeholder="kya miss kiya?" value="${p.includes(':')?p.split(':').slice(1).join(':').trim().replace(/"/g,'&quot;'):''}">
 <span class="done" id="d_${s.id}">${p?p.split(':')[0]:''}</span></div>`;
 a.appendChild(d)})}
ld();</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_xauusd_m1_backup.csv")
    ap.add_argument("--tz", type=int, default=3, help="hours to add to UTC for the axis labels")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--build-page", action="store_true", help="write game.html using game_calls.json")
    args = ap.parse_args()

    bars, tz = load(args.data, args.tz)
    B.UHV_BODY_MIN = 0.0; B.MIN_ORIGIN_BREAK = 0.0; B.ER_MIN = 0.0
    B.TREND_MIN_HUMP = 0.5; B.TREND_DOM = 0.0          # loose: give the AI real variety
    setups = B.detect_full(bars)
    step = max(1, len(setups) // args.n)
    picked = setups[::step][:args.n]
    meta = []
    calls = json.loads(CALLS.read_text(encoding="utf-8")) if CALLS.exists() else {}
    for k, s in enumerate(picked, 1):
        gid = f"game_{k:02d}"
        png = OUT / f"{gid}.png"
        if not draw(bars, s, png, tz): continue
        t = bars[s["i"]].t
        meta.append({"id": gid, "png": f"{gid}.png?v={int(time.time())}",
                     "title": f"Setup {k} · engine wants {s['side']} · {(t.hour+tz)%24:02d}:{t.minute:02d}",
                     "call": calls.get(gid, "<i>(Claude ka call abhi aana baaki)</i>"),
                     "side": s["side"],
                     "time": f"{(t.hour+tz)%24:02d}:{t.minute:02d}"})
    sub = ("Claude ne chart DEKH kar call kiya (koi hardcoded rule nahi). Tum sirf marks do: "
           "✅ 10/10 agar sahi pehchana, ❌ 0/10 agar ghalat — aur likho kya miss kiya. "
           "Jab Claude ki aankh tumse milne lage, tab AI judgment live jayega.")
    (OUT / "game.html").write_text(HTML.replace("__J__", json.dumps(meta)).replace("__SUB__", sub), encoding="utf-8")
    print(f"game.html: {len(meta)} setups")
    for m in meta: print(f"  {m['id']}: {m['side']} @ {m['time']}")


if __name__ == "__main__":
    main()
