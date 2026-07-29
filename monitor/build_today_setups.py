"""build_today_setups.py — LIVE "Today's Setups" page for Zee.

setups.claudezeeshan.com/today.html — shows every OANDA fast-scalp setup that formed
TODAY (so far) as a chart photo, the expected setups/hour rate + projection for the
rest of the day, and a comment box per setup (persists by stable id). Run --loop to
keep it fresh as new setups form; the page also auto-refreshes in the browser.

Data: OANDA:XAUUSD M1 from oanda_bridge (Common/Files/oanda_m1.csv). Config: dom=0
fast-scalp (~115/day). PNGs are cached by id so regeneration only renders NEW setups.
"""
from __future__ import annotations
import argparse, csv, json, sys, time
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
TZ_OFFSET = 2   # OANDA/Zee chart display = UTC+2 (Munich)
CFG = dict(UHV_BODY_MIN=0.0, MIN_ORIGIN_BREAK=0.0, ER_MIN=0.0, TREND_MIN_HUMP=0.5, TREND_DOM=0.0)
EXIT = dict(arm=0.3, give=0.2, tp=3.0, cap=3.0)

HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="90"><title>Today's Setups</title><style>
body{font-family:system-ui,Segoe UI,Arial;margin:0;background:#0b0f14;color:#e6edf3}
header{position:sticky;top:0;background:#111826;padding:14px 18px;border-bottom:1px solid #223;z-index:5}
h1{font-size:19px;margin:0}.rate{color:#7dd3fc;font-size:15px;margin-top:6px;line-height:1.6}
.rate b{color:#e6edf3}.sub{color:#8b97a3;font-size:12px;margin-top:4px}
.card{margin:16px;background:#111826;border:1px solid #223;border-radius:10px;overflow:hidden}
.card img{width:100%;display:block;background:#fff}
.title{padding:11px 14px 2px;font-size:15px;font-weight:600}
.cap{padding:0 14px 8px;font-size:14px;font-weight:600}
.pos{color:#4ade80}.neg{color:#f87171}.pend{color:#fbbf24}
.notes{padding:2px 14px 6px;color:#c9d4df;font-size:14px;line-height:1.6}
.row{display:flex;gap:8px;padding:8px 14px 12px}
textarea{flex:1;min-height:52px;background:#0b0f14;color:#e6edf3;border:1px solid #334;border-radius:8px;padding:8px;font-size:14px}
button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:9px 16px;cursor:pointer}
.saved{color:#16a34a;font-size:13px;align-self:center}
.empty{padding:30px 18px;color:#8b97a3}
</style></head><body><header><h1>📸 Today's Setups — XAUUSD (OANDA)</h1>
<div class="rate">__RATE__</div><div class="sub">__SUB__</div></header>
<div id="app"></div><script>
const S=__J__;let L={};
async function ld(){try{L=await(await fetch('/api/labels')).json()}catch(e){}rn()}
async function sv(id){const v=document.getElementById('t_'+id).value;const r=await fetch('/api/labels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx:id,who:'zee',label:v})});const e=document.getElementById('s_'+id);e.textContent=r.ok?'saved ✓':'err';setTimeout(()=>e.textContent='',2000)}
function rn(){const a=document.getElementById('app');if(!S.length){a.innerHTML='<div class="empty">Aaj abhi tak koi setup nahi bana. Naye bante hi yahan aa jayenge (page har 90s refresh hota hai).</div>';return}a.innerHTML='';S.forEach(s=>{const p=(L[s.id]&&L[s.id].zee)||'';const notes=(s.notes||[]).map(n=>'• '+n).join('<br>');const d=document.createElement('div');d.className='card';d.innerHTML=`<div class="title">🧩 ${s.title}</div><div class="cap ${s.cls}">${s.cap}</div><img src="${s.png}" loading="lazy"><div class="notes">${notes}</div><div class="row"><textarea id="t_${s.id}" placeholder="Comment (kya lagta hai / lete ya nahi)">${p.replace(/</g,'&lt;')}</textarea><button onclick="sv('${s.id}')">Save</button><span class="saved" id="s_${s.id}"></span></div>`;a.appendChild(d)})}
ld();</script></body></html>"""


def load_bars():
    bars = []
    if not CF.exists(): return bars
    with CF.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc).replace(tzinfo=None)
            bars.append(B.Bar(t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), int(r["volume"])))
    bars.sort(key=lambda b: b.t)
    return bars


def outcome(bars, i, side, entry):
    if i + 3 >= len(bars): return None, "pending"   # too recent to resolve
    peak = 0.0
    for k in range(i + 1, min(i + 60, len(bars))):
        bb = bars[k]; favx = (entry - bb.l) if side == "SELL" else (bb.h - entry); peak = max(peak, favx)
        advc = (bb.c - entry) if side == "SELL" else (entry - bb.c)
        if favx >= EXIT["tp"]: return EXIT["tp"] * LOT * 100, "tp"
        if advc >= EXIT["cap"]: return -EXIT["cap"] * LOT * 100, "cap"
        favc = (entry - bb.c) if side == "SELL" else (bb.c - entry)
        if peak >= EXIT["arm"] and (peak - favc) >= EXIT["give"]: return (peak - EXIT["give"]) * LOT * 100, "harvest"
    if i + 60 >= len(bars): return None, "pending"
    bb = bars[min(i + 60, len(bars)) - 1]
    return ((entry - bb.c) if side == "SELL" else (bb.c - entry)) * LOT * 100, "eod"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--loop", type=int, default=0); args = ap.parse_args()
    for k, v in CFG.items(): setattr(B, k, v)
    while True:
        bars = load_bars()
        if bars:
            today = bars[-1].t.date()
            tmap = {b.t: i for i, b in enumerate(bars)}
            todays = [s for s in B.detect_full(bars) if s["open_t"].date() == today]
            # hours elapsed today (from first bar today to latest)
            tbars = [b for b in bars if b.t.date() == today]
            hrs = max((tbars[-1].t - tbars[0].t).total_seconds() / 3600, 0.1) if tbars else 0.1
            rate = len(todays) / hrs
            resolved = [outcome(bars, tmap[s["open_t"]], s["side"], s["entry"])[0] for s in todays]
            done = [r for r in resolved if r is not None]
            wins = sum(1 for r in done if r > 0); net = sum(done)
            wr = 100 * wins / max(len(done), 1)
            nums = {s2["open_t"]: k for k, s2 in enumerate(todays, 1)}   # Setup 1 = first today
            meta = []
            for s in reversed(todays):   # newest first
                disp = (s["open_t"].hour + TZ_OFFSET) % 24
                sid = f"today_{s['open_t'].strftime('%H%M')}_{s['side']}"
                png = OUT / f"{sid}.png"
                if not png.exists():
                    render(dict(s), bars, png)
                usd, how = outcome(bars, tmap[s["open_t"]], s["side"], s["entry"])
                if usd is None:
                    cap = f"{s['side']} @ {disp:02d}:{s['open_t'].minute:02d} — ⏳ pending"; cls = "pend"
                else:
                    cls = "pos" if usd >= 0 else "neg"
                    cap = f"{s['side']} @ {disp:02d}:{s['open_t'].minute:02d} — ${usd:+.1f} ({how})"
                title, notes = describe(extract_features(bars, s["o"], s["u"], s["i"], s["side"]), s["side"])
                meta.append({"id": sid, "png": f"{sid}.png", "title": f"Setup {nums[s['open_t']]} · {title}",
                             "cap": cap, "cls": cls, "notes": notes})
            proj = rate * 24
            rateline = (f"<b>{len(todays)}</b> setups so far today ({hrs:.1f}h) &nbsp;·&nbsp; "
                        f"<b>{rate:.1f}/hour</b> &nbsp;·&nbsp; projected <b>~{proj:.0f}/day</b><br>"
                        f"resolved: {len(done)} &nbsp;·&nbsp; WR <b>{wr:.0f}%</b> &nbsp;·&nbsp; "
                        f"net <b>${net:+.0f}</b> @0.1 lot &nbsp;·&nbsp; day-projection <b>~${(net/max(len(done),1))*len(todays)*24/max(len(todays),1):+.0f}/day</b>")
            sub = f"OANDA fast-scalp · updated {datetime.now().strftime('%H:%M')} · times in Munich (UTC+2) · page auto-refreshes 90s"
            html = HTML.replace("__J__", json.dumps(meta)).replace("__RATE__", rateline).replace("__SUB__", sub)
            (OUT / "today.html").write_text(html, encoding="utf-8")
            print(f"today.html: {len(todays)} setups, {rate:.1f}/hr, WR {wr:.0f}%, net ${net:+.0f}")
        if args.loop <= 0: break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
