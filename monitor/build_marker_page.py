"""build_marker_page.py — HIS chart, and he marks the setups on it.

Zee, 2026-08-24: "is there a way that i annotate setups on tradingview chart and you
read them from there? can we establish such a way? that would help you gauge what i
think is the method."

TradingView refused the job: an anonymous chart is read-only, and its sign-in will not
run in a debug-enabled browser (Google blocks it). So the marks are made on the same
OANDA candles the EA judges — which is better anyway, because a rectangle cannot tell
me WHICH candle he thinks is the UHV, and that ambiguity has already cost us twice.

He clicks three candles per setup — the three anchors every law turns on:
    1) where the RETRACEMENT STARTS — his own convention, confirmed 2026-08-24:
       "yes i'm marking where the retracement starts", i.e. the FIRST RED of the
       pullback. The law's origin (the last GREEN whose low that red breaks) sits one
       candle earlier and is derived from his mark, not asked of him.
    2) the UHV                  (the loudest red of that pullback)
    3) the BREAKOUT             (the candle that takes the UHV's high)
Saved to setup_labels/zee_marks.json via the labeller server, then graded by
grade_marks.py: for each of his setups, did the EA take it, and if not, WHICH LAW
refused it.

    py monitor/build_marker_page.py              # build from the OANDA archive
    py monitor/serve_setup_labels.py             # then open /mark.html
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = pathlib.Path(__file__).parent
OUT = HERE / "setup_labels"
COMMON = pathlib.Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
HIST = HERE / "strategy_lab" / "oanda_m1_history.csv"
BROKER_OFFSET_H = 3          # Blueberry server = UTC+3
PKT_OFFSET_H = 5             # Pakistan = UTC+5


def load_bars(days: int):
    """Every OANDA minute we have, newest `days` days, keyed in BROKER time (what the
    EA's clock uses) with PKT shown to him. Archive first, live window on top."""
    rows = {}
    for src in (HIST, COMMON / "oanda_m1.csv"):
        if not src.exists():
            continue
        for r in csv.DictReader(src.open(encoding="utf-8", errors="replace")):
            u = r.get("time_unix")
            if not u:
                continue
            rows.setdefault(int(u), (float(r["open"]), float(r["high"]),
                                     float(r["low"]), float(r["close"]),
                                     int(float(r["volume"]))))
    if not rows:
        return []
    newest = max(rows)
    cutoff = newest - days * 86400
    out = []
    for u in sorted(rows):
        if u < cutoff:
            continue
        o, h, l, c, v = rows[u]
        srv = dt.datetime.fromtimestamp(u, dt.UTC).replace(tzinfo=None) + dt.timedelta(hours=BROKER_OFFSET_H)
        out.append({"t": u, "s": srv.strftime("%Y.%m.%d %H:%M"), "o": o, "h": h,
                    "l": l, "c": c, "v": v})
    return out


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mark the setups</title><style>
*{box-sizing:border-box} body{margin:0;background:#ffffff;color:#16202a;
 font-family:system-ui,Segoe UI,Arial}
header{padding:10px 14px;background:#f4f6f8;border-bottom:1px solid #d9dfe5;
 display:flex;gap:14px;align-items:center;flex-wrap:wrap}
h1{font-size:15px;margin:0;font-weight:600}
select,button{background:#ffffff;color:#16202a;border:1px solid #c3ccd5;
 border-radius:6px;padding:6px 10px;font-size:13px;cursor:pointer}
button.go{background:#0a9d4f;border-color:#0a8944;color:#fff}
button.clr{background:#d92b3a;border-color:#bb2331;color:#fff}
#wrap{position:relative} canvas{display:block;cursor:crosshair}
#hint{padding:8px 14px;font-size:13px;color:#4a5a6a;background:#fbfcfd;
 border-bottom:1px solid #e4e9ee}
.tag{display:inline-block;padding:2px 8px;border-radius:5px;font-size:12px;
 margin-right:6px;color:#fff}
.origin{background:#1d6fbf} .uhv{background:#c2273c} .brk{background:#0a9d4f}
#list{padding:10px 14px;font-size:12.5px;color:#3c4a58;max-height:190px;overflow:auto}
#list div{padding:3px 0;border-bottom:1px solid #eef1f4}
#msg{margin-left:auto;font-size:12.5px;color:#0a8944}
</style></head><body>
<header>
  <h1>Mark the setups &mdash; your OANDA candles</h1>
  <select id="day"></select>
  <span class="tag origin">1 retracement starts</span>
  <span class="tag uhv">2 UHV</span>
  <span class="tag brk">3 breakout</span>
  <select id="side"><option value="buy">buy</option><option value="sell">sell</option></select>
  <button class="go" id="save">Save setup</button>
  <button class="clr" id="clear">Clear picks</button>
  <button id="livebtn" style="background:#1d6fbf;border-color:#1a5fa5;color:#fff">
    Visualize LIVE trade</button>
  <label style="font-size:12.5px;color:#4a5a6a">vol
    <input id="volh" type="range" min="70" max="360" value="170" style="vertical-align:middle">
  </label>
  <span id="msg"></span>
</header>
<div id="hint">Click the three candles in order: the candle where the <b>retracement
 starts</b> (the first red that breaks the last green's low), then the
 <b>UHV</b>, then the <b>breakout</b>. The UHV's level is drawn forward as a dashed line
 &mdash; the breakout must close its <b>body</b> through it. Scroll to zoom, drag to pan.
 Times are PKT. One candle may hold two roles &mdash; click it twice.
 <b>Right-click</b> a candle to undo its last role.</div>
<div id="wrap"><canvas id="c"></canvas></div>
<div id="list"></div>
<script>
const BARS = __BARS__;
const PKT_SHIFT = __PKT_SHIFT__;      // seconds to add to unix for PKT display
let picks = [], marks = [], view = {i0: 0, n: 260}, drag = null;
let trade = null;      // the EA's fired trade, drawn from its own [LAWX] stamp
let VOL_H = 170;              // volume pane height — he asked for a bigger
                              // scale: at 64px the bars were too short to
                              // compare, and comparing them IS the UHV law
const cv = document.getElementById('c'), cx = cv.getContext('2d');

function pkt(t){ const d = new Date((t + PKT_SHIFT) * 1000);
  return d.toISOString().slice(11,16); }
function pktDay(t){ const d = new Date((t + PKT_SHIFT) * 1000);
  return d.toISOString().slice(0,10); }

const days = [...new Set(BARS.map(b => pktDay(b.t)))].sort();
const sel = document.getElementById('day');
days.forEach(d => { const o = document.createElement('option'); o.value = d;
  o.textContent = d; sel.appendChild(o); });
sel.value = days[days.length - 1];
sel.onchange = () => { const i = BARS.findIndex(b => pktDay(b.t) === sel.value);
  view.i0 = Math.max(0, i); draw(); };

function resize(){ cv.width = window.innerWidth; cv.height = Math.max(430,
  window.innerHeight - 210); draw(); }
window.addEventListener('resize', resize);

function slice(){ return BARS.slice(view.i0, view.i0 + view.n); }

function draw(){
  const bs = slice(); if (!bs.length) return;
  const W = cv.width, H = cv.height, volH = VOL_H, padT = 12, padB = 20;
  const chartH = H - volH - padT - padB;
  const hi = Math.max(...bs.map(b => b.h)), lo = Math.min(...bs.map(b => b.l));
  const vmax = Math.max(...bs.map(b => b.v)) || 1;
  const bw = W / bs.length, y = p => padT + (hi - p) / (hi - lo || 1) * chartH;
  cx.fillStyle = '#ffffff'; cx.fillRect(0, 0, W, H);
  bs.forEach((b, i) => {
    const x = i * bw + bw / 2, up = b.c >= b.o;
    const tags = picks.filter(p => p.t === b.t);
    cx.strokeStyle = up ? '#0a9d4f' : '#d92b3a'; cx.lineWidth = 1;
    cx.beginPath(); cx.moveTo(x, y(b.h)); cx.lineTo(x, y(b.l)); cx.stroke();
    cx.fillStyle = up ? '#0a9d4f' : '#d92b3a';
    const top = y(Math.max(b.o, b.c)), hgt = Math.max(1, Math.abs(y(b.o) - y(b.c)));
    cx.fillRect(x - bw * 0.34, top, Math.max(1, bw * 0.68), hgt);
    cx.fillStyle = up ? 'rgba(10,157,79,.40)' : 'rgba(217,43,58,.40)';
    const vh = b.v / vmax * volH;
    cx.fillRect(x - bw * 0.34, H - padB - vh, Math.max(1, bw * 0.68), vh);
    tags.forEach((tag, ti) => {
      const col = tag.role === 'origin' ? '#1d6fbf' :
                  tag.role === 'uhv' ? '#c2273c' : '#0a8944';
      // A PLUMB LINE DOWN TO THE VOLUME (2026-08-24, his request: "draw a vertical
      // line down from the candle to the volume so i can see which candle corresponds
      // to the highest volume"). The UHV law is decided in the volume pane, and
      // matching a candle to its bar by eye across 300 columns is guesswork.
      cx.save();
      cx.setLineDash(tag.role === 'uhv' ? [] : [3, 3]);
      cx.strokeStyle = col; cx.globalAlpha = tag.role === 'uhv' ? 0.55 : 0.3;
      cx.lineWidth = tag.role === 'uhv' ? 1.5 : 1;
      cx.beginPath(); cx.moveTo(x, padT); cx.lineTo(x, H - padB); cx.stroke();
      cx.restore();
      // outline its volume bar and print the number, so the comparison is read, not judged
      const vhh = b.v / vmax * volH;
      cx.strokeStyle = col; cx.lineWidth = 2;
      cx.strokeRect(x - bw * 0.5, H - padB - vhh, bw, vhh);
      if (ti === 0){
        cx.fillStyle = col; cx.font = 'bold 10px system-ui';
        const vt = String(b.v), vw = cx.measureText(vt).width;
        cx.fillText(vt, x - vw / 2, H - padB - vhh - 3);
      }
      cx.fillStyle = col;
      // and the candle itself
      cx.lineWidth = 2;
      cx.strokeRect(x - bw * 0.5, y(b.h) - 6, bw, y(b.l) - y(b.h) + 12);
      cx.font = '10px system-ui';
      cx.fillText(tag.role === 'origin' ? 'RETR' : (tag.role === 'breakout' ? 'BRK' : 'UHV'),
                  x - bw * 0.5, y(b.h) - 9 - ti * 11);
    });
  });
  // THE EA'S OWN TRADE, drawn from what it stamped when it fired (2026-08-24, his
  // request: "how else would i know which candle was the UHV which was considered for
  // breakout, and which candle did the breakout"). Its three anchors, its level, and
  // the entry/stop/target it actually used.
  if (trade){
    const roles = [[trade.origin,'ORIGIN','#1d6fbf'], [trade.uhv,'UHV','#c2273c'],
                   [trade.breakout,'BREAKOUT','#0a8944']];
    roles.forEach(([srv, label, col], ri) => {
      const bi = bs.findIndex(b => b.s === srv); if (bi < 0) return;
      const b = bs[bi], x = bi * bw + bw / 2;
      cx.save(); cx.strokeStyle = col; cx.globalAlpha = .5; cx.lineWidth = 1.5;
      cx.beginPath(); cx.moveTo(x, padT); cx.lineTo(x, H - padB); cx.stroke(); cx.restore();
      cx.strokeStyle = col; cx.lineWidth = 2;
      cx.strokeRect(x - bw * 0.5, y(b.h) - 6, bw, y(b.l) - y(b.h) + 12);
      const vhh = b.v / vmax * volH;
      cx.strokeRect(x - bw * 0.5, H - padB - vhh, bw, vhh);
      cx.fillStyle = col; cx.font = 'bold 10px system-ui';
      cx.fillText(label + ' ' + b.v, x - bw * 0.5, y(b.h) - 10);
    });
    // the level the breakout had to close through, and the trade's own geometry
    [[trade.uhv_high, 'UHV high ' + trade.uhv_high.toFixed(2), '#c2273c', [6,4]],
     [trade.entry,    'entry '    + trade.entry.toFixed(2),    '#16202a', []],
     [trade.stop,     'stop '     + trade.stop.toFixed(2),     '#d92b3a', [2,3]],
     [trade.target,   'target '   + trade.target.toFixed(2),   '#0a9d4f', [2,3]]
    ].forEach(([price, label, col, dash]) => {
      const yy = y(price); if (yy < padT - 30 || yy > padT + chartH + 30) return;
      cx.save(); cx.setLineDash(dash); cx.strokeStyle = col; cx.lineWidth = 1.3;
      cx.beginPath(); cx.moveTo(0, yy); cx.lineTo(W, yy); cx.stroke(); cx.restore();
      cx.font = 'bold 11px system-ui';
      const tw2 = cx.measureText(label).width;
      cx.fillStyle = 'rgba(255,255,255,.88)'; cx.fillRect(W - tw2 - 10, yy - 13, tw2 + 8, 14);
      cx.fillStyle = col; cx.fillText(label, W - tw2 - 6, yy - 3);
    });
  }

  // THE LEVEL. The moment he marks a UHV, its high (buy) or low (sell) is drawn
  // forward as a dashed line — the price the breakout candle has to close its body
  // through. It is the same level the EA's BreakoutOK() tests, so what he sees here
  // and what the machine judges are the same number.
  const up_ = picks.find(p => p.role === 'uhv');
  if (up_){
    const ub = BARS.find(b => b.t === up_.t);
    if (ub){
      const buy = document.getElementById('side').value === 'buy';
      const lvl = buy ? ub.h : ub.l;
      const yl = y(lvl);
      if (yl > padT - 40 && yl < padT + chartH + 40){
        const ui = bs.findIndex(b => b.t === ub.t);
        const x0 = ui >= 0 ? ui * bw + bw / 2 : 0;
        cx.save();
        cx.setLineDash([6, 4]); cx.strokeStyle = '#c2273c'; cx.lineWidth = 1.5;
        cx.beginPath(); cx.moveTo(x0, yl); cx.lineTo(W, yl); cx.stroke();
        cx.restore();
        cx.fillStyle = '#c2273c'; cx.font = 'bold 11px system-ui';
        const lab = (buy ? 'UHV high ' : 'UHV low ') + lvl.toFixed(2);
        const tw = cx.measureText(lab).width;
        cx.fillStyle = 'rgba(255,255,255,.85)';
        cx.fillRect(W - tw - 10, yl - 13, tw + 8, 14);
        cx.fillStyle = '#c2273c';
        cx.fillText(lab, W - tw - 6, yl - 3);
      }
    }
  }

  cx.strokeStyle = '#e4e9ee'; cx.lineWidth = 1;
  cx.beginPath(); cx.moveTo(0, H - padB - volH - 4); cx.lineTo(W, H - padB - volH - 4);
  cx.stroke();
  cx.fillStyle = '#6b7885'; cx.font = '11px system-ui';
  for (let i = 0; i < bs.length; i += Math.ceil(bs.length / 10))
    cx.fillText(pkt(bs[i].t), i * bw, H - 5);
  cx.fillText(hi.toFixed(2), 4, padT + 9); cx.fillText(lo.toFixed(2), 4, padT + chartH);
  cx.fillText('vol max ' + vmax, 4, H - padB - volH + 10);
}

cv.addEventListener('wheel', e => { e.preventDefault();
  view.n = Math.max(40, Math.min(900, Math.round(view.n * (e.deltaY > 0 ? 1.15 : .87))));
  draw(); }, {passive:false});
cv.addEventListener('mousedown', e => drag = {x: e.clientX, i0: view.i0});
window.addEventListener('mouseup', () => drag = null);
cv.addEventListener('mousemove', e => { if (!drag) return;
  const bw = cv.width / view.n, d = Math.round((drag.x - e.clientX) / bw);
  view.i0 = Math.max(0, Math.min(BARS.length - 10, drag.i0 + d)); draw(); });

// ONE CANDLE CAN HOLD MORE THAN ONE ROLE (2026-08-24, his catch: "there's no way to
// mark the origin candle as the uhv, as if i click the origin again it vanishes the
// origin"). A left click always assigns the NEXT role, so origin and UHV may be the
// same candle. Right-click removes that candle's most recent role.
function barAt(e){ const bs = slice(), bw = cv.width / bs.length;
  return bs[Math.floor(e.offsetX / bw)]; }

cv.addEventListener('click', e => {
  if (drag && Math.abs(e.clientX - drag.x) > 3) return;
  const b = barAt(e); if (!b) return;
  const roles = ['origin', 'uhv', 'breakout'];
  if (picks.length >= 3) return msg('three already picked — Save, or right-click to undo',
                                    '#b8760a');
  picks.push({t: b.t, s: b.s, role: roles[picks.length]});
  draw(); render();
});

cv.addEventListener('contextmenu', e => {
  e.preventDefault();
  const b = barAt(e); if (!b) return;
  for (let i = picks.length - 1; i >= 0; i--)
    if (picks[i].t === b.t) { picks.splice(i, 1); break; }
  draw(); render();
});

function msg(t, c){ const m = document.getElementById('msg');
  m.style.color = c || '#0a8944'; m.textContent = t;
  setTimeout(() => { if (m.textContent === t) m.textContent = ''; }, 4000); }

function render(){
  const l = document.getElementById('list');
  l.innerHTML = (picks.length ? '<div><b>picking:</b> ' + picks.map(p =>
      (p.role === 'origin' ? 'retr' : p.role) + ' ' + pkt(p.t)).join(' &rarr; ') + '</div>' : '') +
    marks.map(m => '<div>' + m.side.toUpperCase() + '  origin ' + m.origin.slice(11) +
      '  UHV ' + m.uhv.slice(11) + '  breakout ' + m.breakout.slice(11) +
      '  <span style="color:#8a95a1">' + m.origin.slice(0,10) + '</span></div>').join('');
}

document.getElementById('livebtn').onclick = async () => {
  const ts = await (await fetch('/api/trades')).json();
  if (ts.error || !ts.length) return msg(ts.error || 'the EA has not fired yet', '#b8760a');
  trade = ts[ts.length - 1];                       // the newest one it stamped
  const bi = BARS.findIndex(b => b.s === trade.breakout);
  if (bi < 0) return msg('its breakout candle is not in this chart window', '#b8760a');
  view.n = 90; view.i0 = Math.max(0, bi - 55);     // frame the setup
  sel.value = pktDay(BARS[bi].t);
  msg(trade.side.toUpperCase() + '  UHV ' + trade.uhv.slice(11) + ' vol ' + trade.uhv_vol +
      '  ->  breakout ' + trade.breakout.slice(11) + ' vol ' + trade.brk_vol +
      (trade.held !== null ? '  (held ' + trade.held + '%)' : ''));
  draw();
};
document.getElementById('side').onchange = () => draw();   // level flips high <-> low
document.getElementById('volh').oninput = e => { VOL_H = +e.target.value; draw(); };
document.getElementById('clear').onclick = () => { picks = []; draw(); render(); };
document.getElementById('save').onclick = async () => {
  if (picks.length !== 3) return msg('pick all three candles first', '#b8760a');
  const body = {side: document.getElementById('side').value,
    origin: picks[0].s, uhv: picks[1].s, breakout: picks[2].s};
  const r = await fetch('/api/marks', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const j = await r.json();
  if (j.ok){ msg('saved — ' + j.total + ' setups marked'); picks = []; await refresh(); }
  else msg(j.error || 'save failed', '#c2273c');
  draw();
};

async function refresh(){ marks = await (await fetch('/api/marks')).json(); render(); }
refresh(); sel.onchange(); resize();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=8)
    a = ap.parse_args()
    bars = load_bars(a.days)
    if not bars:
        print("no OANDA bars found — is the bridge running?")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    html = (PAGE.replace("__BARS__", json.dumps(bars, separators=(",", ":")))
                .replace("__PKT_SHIFT__", str(PKT_OFFSET_H * 3600)))
    (OUT / "mark.html").write_text(html, encoding="utf-8")
    d0, d1 = bars[0]["s"][:10], bars[-1]["s"][:10]
    print(f"  mark.html written — {len(bars)} candles, {d0} .. {d1} (broker dates)")
    print(f"  serve:  py monitor/serve_setup_labels.py")
    print(f"  open :  http://127.0.0.1:8765/mark.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
