"""build_rule_diagrams.py — render each RULE STENCIL as a clean, idealized schematic
diagram (not real data) + a rules.html page Zee validates (Rule 1 / Rule 2 ...).

The diagrams are the human-facing "stencil": the canonical shape the live
pattern-matcher (pattern_matcher.py) checks the market against.
"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch

HERE = Path(__file__).parent
OUT = HERE / "setup_labels"
STENCIL = json.loads((HERE / "rules_stencil.json").read_text(encoding="utf-8"))

G, R, GOLD, PUR = "#16a34a", "#dc2626", "#b8860b", "#9333ea"

# idealized candle sequences per rule: (open, high, low, close, volume)
# + markers: index of RET(origin), UHV, BRKT (None if n/a)
DIAGRAMS = {
    "Rule 1": {  # uptrend -> red pullback (UHV) -> green momentum breakout
        "c": [(100,102.4,99.8,102),(102,104.6,101.8,104.3),(104.3,107.2,104.1,106.9),
              (106.9,107.1,105.2,105.5),(105.5,105.7,102.6,103.0),(103.0,103.4,102.5,102.9),
              (102.9,106.6,102.8,106.3),(106.3,107.0,106.0,106.6)],
        "v": [520,640,760,600,1050,380,720,560], "ret":3, "uhv":4, "brkt":6,
    },
    "Rule 2": {  # downtrend -> green pullback (UHV) -> red momentum breakout (mirror)
        "c": [(100,100.2,97.6,98.0),(98.0,98.2,95.4,95.7),(95.7,95.9,92.8,93.1),
              (93.1,94.8,92.9,94.5),(94.5,97.4,94.3,97.0),(97.0,97.5,96.6,97.1),
              (97.1,97.2,93.4,93.7),(93.7,94.0,93.0,93.4)],
        "v": [520,640,760,600,1050,380,720,560], "ret":3, "uhv":4, "brkt":6,
    },
    "Rule 3": {  # ranging / choppy — no direction
        "c": [(100,101.2,99.2,99.6),(99.6,101.0,99.0,100.8),(100.8,101.3,99.4,99.8),
              (99.8,101.1,99.1,100.6),(100.6,101.2,99.3,99.7),(99.7,101.0,99.2,100.5),
              (100.5,101.2,99.3,99.8),(99.8,100.9,99.1,100.4)],
        "v": [600,560,620,580,600,560,610,590], "ret":None, "uhv":None, "brkt":None,
    },
    "Rule 4": {  # uptrend + UHV, but breakout is a WICK (closes back)
        "c": [(100,102.4,99.8,102),(102,104.6,101.8,104.3),(104.3,107.2,104.1,106.9),
              (106.9,107.1,105.2,105.5),(105.5,105.7,102.6,103.0),(103.0,103.4,102.5,102.9),
              (102.9,106.6,102.7,103.3),(103.3,103.6,102.6,103.0)],
        "v": [520,640,760,600,1050,380,700,540], "ret":3, "uhv":4, "brkt":6,
    },
    "Rule 5": {  # marginal UHV — pullback red candles all similar volume
        "c": [(100,102.4,99.8,102),(102,104.6,101.8,104.3),(104.3,107.2,104.1,106.9),
              (106.9,107.1,105.2,105.5),(105.5,105.7,104.0,104.2),(104.2,104.4,102.7,102.9),
              (102.9,106.6,102.8,106.3),(106.3,107.0,106.0,106.6)],
        "v": [520,640,760,600,640,620,720,560], "ret":3, "uhv":4, "brkt":6,
    },
    "Rule 6": {  # wrong side / no retracement — buying but no body-break origin (downtrend-ish)
        "c": [(100,100.2,97.8,98.1),(98.1,98.4,96.0,96.3),(96.3,96.6,94.2,94.5),
              (94.5,96.4,94.3,96.1),(96.1,96.6,95.2,95.6),(95.6,98.8,95.5,98.5),
              (98.5,98.9,98.0,98.6),(98.6,99.1,98.2,98.9)],
        "v": [700,760,720,560,600,780,540,520], "ret":None, "uhv":None, "brkt":5,
    },
}


def draw(rule, d, png):
    fig, (ax, av) = plt.subplots(2, 1, figsize=(7.5, 5.2), gridspec_kw={"height_ratios": [3, 1]},
                                 sharex=True)
    cs = d["c"]; vols = d["v"]
    for x, (o, h, l, c) in enumerate(cs):
        col = G if c >= o else R
        ax.plot([x, x], [l, h], color=col, lw=1.4, zorder=1, solid_capstyle="round")
        ax.add_patch(Rectangle((x - 0.32, min(o, c)), 0.64, max(abs(c - o), 0.06),
                               facecolor=col, edgecolor=col, zorder=2))
        av.add_patch(Rectangle((x - 0.32, 0), 0.64, vols[x], facecolor=col, alpha=0.75, edgecolor="none"))
    av.set_ylim(0, max(vols) * 1.15); av.set_xlim(-0.7, len(cs) - 0.3)
    lo = min(l for _, _, l, _ in cs); hi = max(h for _, h, _, _ in cs); pad = (hi - lo) * 0.14
    ax.set_ylim(lo - pad, hi + pad * 1.4)
    ax.set_xlim(-0.7, len(cs) - 0.3)

    def tag(idx, txt, above, color):
        if idx is None: return
        o, h, l, c = cs[idx]
        y = h + pad * 0.5 if above else l - pad * 0.5
        ax.annotate(txt, (idx, y), ha="center", va="bottom" if above else "top",
                    fontsize=9, fontweight="bold", color=color,
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=color, alpha=0.95))
    tag(d["ret"], "RET", False, PUR)
    tag(d["uhv"], "UHV", True, GOLD)
    side = rule.get("side", "any")
    tag(d["brkt"], "BRKT", side != "SELL", G if side == "BUY" else R)

    take = rule["action"] == "TAKE"
    ax.text(0.015, 0.96, ("✓ TAKE" if take else "✗ SKIP"), transform=ax.transAxes,
            ha="left", va="top", fontsize=13, fontweight="bold", color=(G if take else R),
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=(G if take else R)))
    ax.set_title(f"{rule['id']} — {rule['name']}", fontsize=13, fontweight="bold", loc="left")
    for a in (ax, av):
        a.set_xticks([]); a.grid(True, axis="y", ls=":", alpha=0.35)
    av.set_ylabel("Vol", fontsize=9)
    fig.tight_layout()
    fig.savefig(png, dpi=80, bbox_inches="tight"); plt.close(fig)


HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rule Stencils — validate</title><style>
body{font-family:system-ui,Segoe UI,Arial;margin:0;background:#0b0f14;color:#e6edf3}
header{position:sticky;top:0;background:#111826;padding:14px 18px;border-bottom:1px solid #223;z-index:5}
h1{font-size:18px;margin:0}.sub{color:#b8c4d0;font-size:14px;margin-top:4px}
.card{margin:18px;background:#111826;border:1px solid #223;border-radius:10px;overflow:hidden}
.card img{width:100%;display:block;background:#fff}
.name{padding:12px 14px 4px;font-size:17px;font-weight:600}
.plain{padding:0 14px 12px;color:#e6edf3;font-size:15px;line-height:1.7}
.row{display:flex;gap:10px;padding:10px 14px}
button{border:0;border-radius:8px;padding:11px 22px;font-size:15px;cursor:pointer;color:#fff}
.ok{background:#16a34a}.no{background:#dc2626}.done{color:#b8c4d0;font-size:14px;align-self:center}
input.why{flex:1;min-width:120px;background:#0b0f14;color:#e6edf3;border:1px solid #334;border-radius:8px;padding:9px 10px;font-size:14px}
</style></head><body><header><h1>📐 Rule Stencils — validate the rulebook</h1>
<div class="sub">Har Rule ek canonical setup ka simple diagram hai. Sahi ho to ✓ Correct, warna ✗ Wrong + kya badlein. Yeh stencils se live market match hoga.</div></header>
<div id="app"></div><script>
const S=__J__;let L={};
async function ld(){try{L=await(await fetch('/api/labels')).json()}catch(e){}rn()}
async function sv(id,val){let lab=val;if(val==='wrong'){const w=(document.getElementById('w_'+id).value||'').trim();lab='wrong'+(w?': '+w:'');}await fetch('/api/labels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx:id,who:'zee',label:lab})});document.getElementById('d_'+id).textContent=val==='correct'?'✓ saved':'✗ saved';}
function rn(){const a=document.getElementById('app');a.innerHTML='';S.forEach(s=>{const prev=(L[s.id]&&L[s.id].zee)||'';const d=document.createElement('div');d.className='card';d.innerHTML=`<div class="name">${s.id} — ${s.name} &nbsp;<b style="color:${s.action==='TAKE'?'#16a34a':'#dc2626'}">${s.action}</b></div><div class="plain">${s.plain}</div><img src="${s.png}" loading="lazy"><div class="row"><button class="ok" onclick="sv('${s.id}','correct')">✓ Correct</button><button class="no" onclick="sv('${s.id}','wrong')">✗ Wrong</button><input class="why" id="w_${s.id}" placeholder="What to change?" value="${(prev&&prev.indexOf('wrong:')===0)?prev.slice(6).trim().replace(/"/g,'&quot;'):''}"><span class="done" id="d_${s.id}">${prev?(prev==='correct'?'✓ saved':'✗ saved'):''}</span></div>`;a.appendChild(d)})}
ld();</script></body></html>"""


def main():
    import time
    bust = int(time.time())
    meta = []
    for rule in STENCIL["rules"]:
        rid = rule["id"]
        d = DIAGRAMS.get(rid)
        if not d: continue
        fn = rid.replace(" ", "").lower()
        png = OUT / f"{fn}.png"
        draw(rule, d, png)
        meta.append({"id": rid, "name": rule["name"], "action": rule["action"],
                     "plain": rule["plain"], "png": f"{fn}.png?v={bust}"})
    (OUT / "rules.html").write_text(HTML.replace("__J__", json.dumps(meta)), encoding="utf-8")
    print(f"rendered {len(meta)} rule diagrams -> rules.html")
    print("Zee: setups.claudezeeshan.com/rules.html")


if __name__ == "__main__":
    main()
