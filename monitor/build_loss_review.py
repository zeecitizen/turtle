"""build_loss_review.py — the REAL losing trades from MT5, drawn for Zee to comment on.

These are ACTUAL broker fills (not simulated): the 2026-07-31 losers that took the
account 1000 -> 309. Each is rendered with the OANDA M1 candles + volume around the
trade, entry/exit/stop marked, plus what the detector saw (RET / UHV / BRKT) so Zee
can say exactly where we went wrong.

Page: setups.claudezeeshan.com/losses.html  (comment box per trade -> zee_labels.json
key "loss_NN"). MT5 server time = UTC+3; OANDA bars are UTC.
"""
from __future__ import annotations
import csv, json, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
import build_entry_review_m5 as B
from case_engine import extract_features
from setup_strength import strength, lot_for

OUT = Path(__file__).parent / "setup_labels"
CF = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.csv")
MT5_UTC_OFFSET = 3          # Blueberry server = UTC+3
BUST = int(time.time())
G, R, GOLD, PUR, BLUE = "#16a34a", "#dc2626", "#b8860b", "#9333ea", "#2563eb"

# REAL fills from the MT5 History tab (2026-07-31). time is MT5 SERVER time.
TRADES = [
    dict(n=3,  t="18:49:44", side="SELL", lots=0.4,  entry=4040.19, exit=4043.34, usd=-126.00, skull=True),
    dict(n=6,  t="19:16:25", side="SELL", lots=0.4,  entry=4043.43, exit=4046.44, usd=-120.40, skull=True),
    dict(n=18, t="22:39:57", side="SELL", lots=0.4,  entry=4049.93, exit=4053.13, usd=-128.00, skull=True),
    dict(n=10, t="20:02:07", side="BUY",  lots=0.1,  entry=4045.61, exit=4042.67, usd=-29.40,  skull=False),
    dict(n=2,  t="18:40:44", side="BUY",  lots=0.01, entry=4043.37, exit=4040.48, usd=-2.89,   skull=False),
]
DAY = "2026-07-31"

HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Real losing trades — where did we go wrong?</title><style>
body{font-family:system-ui,Segoe UI,Arial;margin:0;background:#0b0f14;color:#e6edf3}
header{position:sticky;top:0;background:#111826;padding:14px 18px;border-bottom:1px solid #223;z-index:5}
h1{font-size:18px;margin:0}.sub{color:#b8c4d0;font-size:14px;margin-top:5px;line-height:1.6}
.card{margin:18px;background:#111826;border:1px solid #223;border-radius:10px;overflow:hidden}
.card.skull{border-color:#7f1d1d}
.card img{width:100%;display:block;background:#fff}
.title{padding:12px 14px 2px;font-size:17px;font-weight:700}
.cap{padding:0 14px 10px;color:#f87171;font-size:15px;font-weight:600}
.notes{padding:2px 14px 8px;color:#c9d4df;font-size:14px;line-height:1.7}
.row{display:flex;gap:8px;padding:10px 14px}
textarea{flex:1;min-height:70px;background:#0b0f14;color:#e6edf3;border:1px solid #334;border-radius:8px;padding:9px;font-size:14px}
button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:10px 18px;cursor:pointer}
.saved{color:#16a34a;font-size:13px;align-self:center}
</style></head><body><header><h1>💀 Real losing trades — kahan ghalat thay?</h1>
<div class="sub">__SUB__</div></header>
<div id="app"></div><script>
const S=__J__;let L={};
async function ld(){try{L=await(await fetch('/api/labels')).json()}catch(e){}rn()}
async function sv(id){const v=document.getElementById('t_'+id).value;const r=await fetch('/api/labels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx:id,who:'zee',label:v})});const e=document.getElementById('s_'+id);e.textContent=r.ok?'saved ✓':'err';setTimeout(()=>e.textContent='',2000)}
function rn(){const a=document.getElementById('app');a.innerHTML='';S.forEach(s=>{const p=(L[s.id]&&L[s.id].zee)||'';const notes=(s.notes||[]).map(n=>'• '+n).join('<br>');const d=document.createElement('div');d.className='card'+(s.skull?' skull':'');d.innerHTML=`<div class="title">${s.title}</div><div class="cap">${s.cap}</div><img src="${s.png}" loading="lazy"><div class="notes">${notes}</div><div class="row"><textarea id="t_${s.id}" placeholder="Yahan kya ghalat tha? / tum yeh kyun na lete?">${p.replace(/</g,'&lt;')}</textarea><button onclick="sv('${s.id}')">Save</button><span class="saved" id="s_${s.id}"></span></div>`;a.appendChild(d)})}
ld();</script></body></html>"""


def load_bars():
    bars = []
    with CF.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc).replace(tzinfo=None)
            bars.append(B.Bar(t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), int(r["volume"])))
    bars.sort(key=lambda b: b.t)
    return bars


def find_bar(bars, utc_dt, price):
    """Index of the bar covering utc_dt; fall back to the nearest bar whose range holds price."""
    best, bestd = None, 1e9
    for i, b in enumerate(bars):
        d = abs((b.t - utc_dt).total_seconds())
        if d < bestd and d <= 180:
            if b.l - 0.6 <= price <= b.h + 0.6 or d <= 60:
                best, bestd = i, d
    return best


def render(bars, i, tr, png):
    lo = max(0, i - 40); hi = min(len(bars), i + 20)
    seg = bars[lo:hi]
    if len(seg) < 10: return False
    fig, (ax, av) = plt.subplots(2, 1, figsize=(12, 6.4), gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    for x, b in enumerate(seg):
        col = G if b.c >= b.o else R
        ax.plot([x, x], [b.l, b.h], color=col, lw=1.2, solid_capstyle="round", zorder=1)
        ax.add_patch(Rectangle((x - 0.34, min(b.o, b.c)), 0.68, max(abs(b.c - b.o), 0.02),
                               facecolor=col, edgecolor=col, zorder=2))
        av.add_patch(Rectangle((x - 0.34, 0), 0.68, b.v, facecolor=col, alpha=0.7, edgecolor="none"))
    av.set_ylim(0, max(b.v for b in seg) * 1.15); av.set_xlim(-0.7, len(seg) - 0.3)
    ax.set_xlim(-0.7, len(seg) - 0.3)
    ex = i - lo
    stop = tr["entry"] + (3.0 if tr["side"] == "SELL" else -3.0)
    ax.axhline(tr["entry"], color=BLUE, lw=1.5, ls="-",  label=f'ENTRY {tr["entry"]:.2f}')
    ax.axhline(tr["exit"],  color=R,    lw=1.5, ls="--", label=f'EXIT {tr["exit"]:.2f} (stop)')
    ax.axvline(ex, color=BLUE, lw=1.0, ls=":", alpha=0.8)
    ax.annotate(f'{tr["side"]} {tr["lots"]}', (ex, tr["entry"]), xytext=(ex + 0.6, tr["entry"]),
                fontsize=10, fontweight="bold", color=BLUE,
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=BLUE, alpha=0.95))
    # what the detector saw — ONLY the single setup closest to this trade (Zee: 2 UHVs /
    # 2 RETs on one chart made it unreadable)
    labels = []
    near = [s for s in B.detect_full(bars) if lo <= s["i"] < hi and abs(s["i"] - i) <= 4]
    if near:
        s = min(near, key=lambda x: abs(x["i"] - i))
        for idx, txt, col2 in ((s["o"], "RET", PUR), (s["u"], "UHV", GOLD),
                               (s["i"], "BRKT", G if s["side"] == "BUY" else R)):
            if lo <= idx < hi:
                b = bars[idx]
                ax.annotate(txt, (idx - lo, b.h + (b.h - b.l) * 0.4), ha="center", fontsize=9,
                            fontweight="bold", color=col2,
                            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=col2, alpha=0.95))
        labels.append(s)
    ticks = list(range(0, len(seg), 8))
    ax.set_xticks([]); av.set_xticks(ticks)
    av.set_xticklabels([f"{(seg[t].t.hour + MT5_UTC_OFFSET) % 24:02d}:{seg[t].t.minute:02d}" for t in ticks], fontsize=8)
    ax.legend(loc="upper left", fontsize=9); ax.grid(True, ls=":", alpha=0.3); av.grid(True, axis="y", ls=":", alpha=0.3)
    av.set_ylabel("Vol", fontsize=9)
    ax.set_title(f'#{tr["n"]}  {tr["side"]} {tr["lots"]} lot @ {tr["entry"]:.2f}  →  ${tr["usd"]:+.2f}  (MT5 {tr["t"]})',
                 fontsize=13, fontweight="bold", loc="left")
    fig.tight_layout(); fig.savefig(png, dpi=85, bbox_inches="tight"); plt.close(fig)
    return labels


def main():
    B.UHV_BODY_MIN = 0.0; B.MIN_ORIGIN_BREAK = 0.0; B.ER_MIN = 0.0
    B.TREND_MIN_HUMP = 0.5; B.TREND_DOM = 0.0
    bars = load_bars()
    meta = []
    for tr in TRADES:
        hh, mm, ss = (int(x) for x in tr["t"].split(":"))
        utc = datetime.strptime(DAY, "%Y-%m-%d") + timedelta(hours=hh - MT5_UTC_OFFSET, minutes=mm)
        i = find_bar(bars, utc, tr["entry"])
        if i is None:
            print(f"  #{tr['n']}: no OANDA bar found near {utc} @ {tr['entry']}")
            continue
        png = OUT / f"loss_{tr['n']:02d}.png"
        labels = render(bars, i, tr, png)
        notes = [f"Entry {tr['entry']:.2f} → exit {tr['exit']:.2f} = {abs(tr['exit']-tr['entry']):.2f}pt against us (3pt stop hit)",
                 f"Lot {tr['lots']} → ${tr['usd']:+.2f}. Ek aisa loss ~{int(abs(tr['usd'])/11)} choti jeet kha jaata hai."]
        if labels:
            s = labels[0]
            f = extract_features(bars, s["o"], s["u"], s["i"], s["side"])
            st = strength(f); _, tier = lot_for(st)
            notes.append(f"Detector: {s['side']} · UHV vol {bars[s['u']].v} · strength {st:.2f} ({tier})")
        else:
            notes.append("Detector ka setup is trade ke aas-paas match nahi hua (OANDA vs MT5 feed timing).")
        meta.append({"id": f"loss_{tr['n']:02d}", "png": f"loss_{tr['n']:02d}.png?v={BUST}",
                     "skull": tr["skull"],
                     "title": f"{'💀 ' if tr['skull'] else ''}Trade #{tr['n']} · {tr['side']} {tr['lots']} lot",
                     "cap": f"${tr['usd']:+.2f} · MT5 {tr['t']} · entry {tr['entry']:.2f} → exit {tr['exit']:.2f}",
                     "notes": notes})
        print(f"  rendered #{tr['n']} ({tr['usd']:+.2f})")
    tot = sum(t["usd"] for t in TRADES)
    sub = (f"31 July ke REAL broker losses (total ${tot:+.2f} · account 1000 → 309). "
           f"Times = MT5 server (UTC+3). Har chart pe entry/exit/stop + detector ke RET/UHV/BRKT. "
           f"Batao har ek pe: <b>kahan ghalat thay</b>.")
    (OUT / "losses.html").write_text(HTML.replace("__J__", json.dumps(meta)).replace("__SUB__", sub), encoding="utf-8")
    print(f"losses.html: {len(meta)} trades")


if __name__ == "__main__":
    main()
