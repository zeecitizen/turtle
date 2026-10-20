// Turtle TV - tune the EA's settings like on TradingView: the Turtle TV Tester (monitor/saad_view/sim.py, ~10 ms a year) redraws the chart and its
// results instantly; the MT5 Strategy Tester below shows MT5's real result for the same settings ("Check in MT5"); "Ask Claude" sends the chart
// picture and the data behind it to Claude. Nothing here decides a trade.
'use strict';
const LW = window.LightweightCharts;
const $ = (s) => document.querySelector(s);
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const C = { up: '#26a69a', down: '#ef5350', win: '#00e676', loss: '#ff5252', fast: '#ff9800', slow: '#2962ff', adx: '#b39ddb', muted: '#787b86' };
const TRAIN_END = Date.UTC(2026, 6, 1) / 1000 - 3 * 3600;        // Jul 1 00:00 server time (the optimizer's train / test split)
let TZ = 18000;
let BARS = null, INPUTS = null, DFL = {}, CUR = {}, RUNS = [], lastSeen;
let TT = null, MT = null;                                      // { kind, events, TR, GH, EVB, ... }
let chart, candles, emaF, emaS, adxS, adxLine = null, TVL = null, focusLines = [], eq = {};
let ACTIVE_LAB = null;                                         // an Exit Lab exit running on the main tester too (a saved Exit Lab exit, loaded)
let SEL = null, TAB = { tt: 'overview', mt: 'overview' }, firstView = true, simTimer = null, simSeq = 0, tvKey = null, ASK = [];
const show = { trades: true, ghosts: true, setups: false, skips: false, mt5: false };
const SRC = { ds: 'year', mode: 'ea' }, BARSET = {};             // the Turtle TV Tester's candles and rules (Zee: "find out why ... october ... and fix it")
async function getBars(ds) { if (!BARSET[ds]) BARSET[ds] = await api('/api/bars?ds=' + ds); return BARSET[ds]; }

// ---------- helpers ----------
const money = (v, d = 0) => (v >= 0 ? '+$' : '−$') + Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const cls = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
const pct = (a, b) => (b ? ((100 * a) / b).toFixed(1) + '%' : '–');
const f2 = (v) => (v == null ? '–' : (+v).toFixed(2));
const f1 = (v) => (v == null ? '–' : (+v).toFixed(1));
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const isNum = (s) => /^-?\d+(\.\d+)?$/.test(String(s).trim());
const same = (a, b) => (isNum(a) && isNum(b) ? Math.abs(parseFloat(a) - parseFloat(b)) < 1e-9 : String(a).trim().toLowerCase() === String(b).trim().toLowerCase());
function hm(d) { let h = d.getUTCHours(); const ap = h >= 12 ? 'PM' : 'AM'; h = h % 12 || 12; return `${h}:${String(d.getUTCMinutes()).padStart(2, '0')} ${ap}`; }
function fullFmt(t) { const d = new Date(t * 1000); return `${DOW[d.getUTCDay()]} ${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${d.getUTCFullYear()}  ${hm(d)}`; }
function dt(t) { const d = new Date((t + TZ) * 1000); return `${MON[d.getUTCMonth()]} ${d.getUTCDate()}, ${hm(d)}`; }
function tickFmt(t, type) {
  const d = new Date(t * 1000);
  if (type === 0) return String(d.getUTCFullYear());
  if (type === 1) return MON[d.getUTCMonth()];
  if (type === 2) return `${d.getUTCDate()} ${MON[d.getUTCMonth()]}`;
  let h = d.getUTCHours(); const ap = h >= 12 ? 'p' : 'a'; h = h % 12 || 12;
  return `${h}:${String(d.getUTCMinutes()).padStart(2, '0')}${ap}`;
}
function api(path, body) {
  return fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}).then((r) => r.json());
}
function toast(html, ms = 9000) { const t = $('#toast'); t.innerHTML = html; t.style.display = 'block'; clearTimeout(toast.h); toast.h = setTimeout(() => (t.style.display = 'none'), ms); }
function setStatus(txt, c = '') { const s = $('#status'); s.textContent = txt; s.className = c; }
function box(k) { k = Math.round(k); if (!(k >= 0)) return '–'; const b = k % 21; return b === 20 ? '>100%' : `${b * 5}–${b * 5 + 5}%`; }
function barIdx(t) { const a = BARS.t; let lo = 0, hi = a.length - 1, r = 0; while (lo <= hi) { const m = (lo + hi) >> 1; if (a[m] <= t) { r = m; lo = m + 1; } else hi = m - 1; } return r; }
const diffDfl = (inp) => Object.fromEntries(Object.entries(inp).filter(([k, v]) => k in DFL && !same(v, DFL[k])));

// ---------- the chart ----------
const BASE = {
  autoSize: true,
  layout: { background: { type: 'solid', color: '#131722' }, textColor: '#d1d4dc', fontSize: 12, panes: { separatorColor: '#2a2e39', separatorHoverColor: '#363a45' } },
  grid: { vertLines: { color: '#1e222d' }, horzLines: { color: '#1e222d' } },
  rightPriceScale: { borderColor: '#2a2e39' },
  localization: { timeFormatter: fullFmt },
};
function makeChart() {
  chart = LW.createChart($('#chart'), { ...BASE, crosshair: { mode: 0 },
    timeScale: { borderColor: '#2a2e39', timeVisible: true, secondsVisible: false, rightOffset: 8, barSpacing: 7, tickMarkFormatter: tickFmt } });
  candles = chart.addSeries(LW.CandlestickSeries, { upColor: C.up, downColor: C.down, borderVisible: false, wickUpColor: C.up, wickDownColor: C.down, priceLineVisible: false });
  const quiet = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false };
  emaF = chart.addSeries(LW.LineSeries, { ...quiet, color: C.fast, lineWidth: 2 });
  emaS = chart.addSeries(LW.LineSeries, { ...quiet, color: C.slow, lineWidth: 2 });
  adxS = chart.addSeries(LW.LineSeries, { ...quiet, color: C.adx, lineWidth: 1, lastValueVisible: true }, 1);
  TVL = new TvLabels();
  candles.attachPrimitive(TVL);
  chart.subscribeCrosshairMove((p) => { if (BARS) legend(p && p.time != null ? barIdx(p.time - TZ) : BARS.t.length - 1); });
  chart.subscribeClick((p) => {
    if (!TT || !p || p.logical == null) return;
    if (p.point) {
      const V = VBTN.find((r) => p.point.x >= r.x && p.point.x <= r.x + r.w && p.point.y >= r.y && p.point.y <= r.y + r.h);
      if (V) { if (V.act === 'close') { VHIDE.add(V.key); VEXP.delete(V.key); saveHide(); } else if (VEXP.has(V.key)) VEXP.delete(V.key); else VEXP.add(V.key); redraw(); return; }
    }
    if (p.point) { const L = LBLS.find((r) => p.point.x >= r.x && p.point.x <= r.x + r.w && p.point.y >= r.y && p.point.y <= r.y + r.h); if (L) { focusTrade(L.t); openAsk(L.t, L); return; } }
    const i = Math.round(p.logical), t = TT.TR.find((x) => x.biIn === i || x.biOut === i);
    if (t) focusTrade(t);
  });
  requestAnimationFrame(() => { const ps = chart.panes(); if (ps.length > 1) ps[1].setHeight(80); });
}
function drawBars() {
  const B = BARS;
  candles.setData(B.t.map((t, i) => ({ time: t + TZ, open: B.o[i], high: B.h[i], low: B.l[i], close: B.c[i] })));
  adxS.setData(B.t.map((t, i) => ({ time: t + TZ, value: B.adx[i] })));
}
function drawEmas() {
  if (!TT || !TT.ef) return;
  emaF.setData(BARS.t.map((t, i) => ({ time: t + TZ, value: TT.ef[i] })));
  emaS.setData(BARS.t.map((t, i) => ({ time: t + TZ, value: TT.es[i] })));
  if (adxLine) adxS.removePriceLine(adxLine);
  adxLine = adxS.createPriceLine({ price: parseFloat(CUR.InpAdxMin) || 0, color: C.muted, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'ADX min' });
}

// events (Turtle TV Tester or MT5) -> trades, stand-asides, events by candle
function derive(kind, events, lots) {
  const D = { kind, events, TR: [], GH: [], EVB: new Map() };
  const ent = {}; let g = null;
  for (const e of events) {
    e.bi = barIdx(e.t);
    if (!D.EVB.has(e.bi)) D.EVB.set(e.bi, []);
    D.EVB.get(e.bi).push(e);
    if (e.type === 'entry') ent[e.num] = e;
    else if (e.type === 'exit' && ent[e.num]) {
      const n = ent[e.num];
      D.TR.push({ num: e.num, side: n.side, tIn: n.t, tOut: e.t, biIn: n.bi, biOut: e.bi, en: n.price, sl: n.sl, ex: e.price, pnl: e.v1, swap: e.v2, why: e.text, info: n.text, bucket: n.v2 });
    } else if (e.type === 'ghost') g = { side: e.side, tIn: e.t, biIn: e.bi, en: e.price, sl: e.sl, bucket: e.v2, info: e.text };
    else if (e.type === 'ghost_end' && g) { Object.assign(g, { tOut: e.t, biOut: e.bi, ex: e.price, why: e.text, pnl: (e.price - g.en) * g.side * lots * 100 }); D.GH.push(g); g = null; }
  }
  D.TR.sort((a, b) => a.tIn - b.tIn);
  return D;
}

// ---------- TradingView-style labels (pine/saad_15min.pine: label.new / line.new), drawn on the chart canvas ----------
const TVC = { buy: '#2196f3', sell: '#e040fb', tag: 'rgba(54,58,69,0.92)', yel: '#ffeb3b', win: '#00e676', loss: '#f23645', grey: 'rgba(120,123,134,0.8)' };
const KIND = (k, side) => (k === 1 ? 'pin bar' : k === 2 ? (side > 0 ? 'hammer' : 'shooting star') : 'marubozu');
function rrect(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
// up = TradingView's label_up: the box hangs BELOW (x, y) with its pointer touching y; otherwise label_down (box above)
function tvTag(ctx, x, y, lines, bg, fg, up, px) {
  ctx.font = `${px}px "Trebuchet MS", -apple-system, Roboto, Arial, sans-serif`;
  const lh = Math.round(px * 1.3), pad = Math.round(px * 0.55), pt = Math.max(4, Math.round(px * 0.45));
  const w = Math.max(...lines.map((l) => ctx.measureText(l).width)) + 2 * pad, h = lines.length * lh + Math.round(pad * 0.8);
  const bx = Math.round(x - w / 2), by = up ? y + pt : y - pt - h;
  ctx.fillStyle = bg; rrect(ctx, bx, by, w, h, 3); ctx.fill();
  ctx.beginPath();
  if (up) { ctx.moveTo(x - pt, by + 1); ctx.lineTo(x, y); ctx.lineTo(x + pt, by + 1); } else { ctx.moveTo(x - pt, by + h - 1); ctx.lineTo(x, y); ctx.lineTo(x + pt, by + h - 1); }
  ctx.closePath(); ctx.fill();
  ctx.fillStyle = fg; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  lines.forEach((l, i) => ctx.fillText(l, x, by + Math.round(pad * 0.4) + lh * (i + 0.5)));
  return { x: bx, y: by, w, h };
}
let LBLS = [], NOTESD = {}, VBTN = [];
const VEXP = new Set(), VHIDE = new Set((() => { try { return JSON.parse(localStorage.getItem('tvVerdictHidden') || '[]'); } catch (e) { return []; } })());
const saveHide = () => { try { localStorage.setItem('tvVerdictHidden', JSON.stringify([...VHIDE])); } catch (e) { /* no storage */ } };
const tKey = (t) => `${t.tIn}_${t.side}`;
function wrap(s, n, max) {
  const out = []; let cur = '';
  for (const w of s.split(/\s+/)) { if ((cur + ' ' + w).trim().length > n) { out.push(cur); cur = w; } else cur = (cur + ' ' + w).trim(); }
  if (cur) out.push(cur);
  return out.length > max ? [...out.slice(0, max - 1), out[max - 1] + ' …'] : out;
}
function seg(ctx, x1, y1, x2, y2, color, width, dash) {
  if ([x1, y1, x2, y2].some((v) => v == null)) return;
  ctx.setLineDash(dash); ctx.strokeStyle = color; ctx.lineWidth = width;
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.setLineDash([]);
}
function tri(ctx, x, y, up, color, s) {
  ctx.fillStyle = color; ctx.beginPath();
  if (up) { ctx.moveTo(x, y + 2); ctx.lineTo(x - s, y + 2 + 1.6 * s); ctx.lineTo(x + s, y + 2 + 1.6 * s); } else { ctx.moveTo(x, y - 2); ctx.lineTo(x - s, y - 2 - 1.6 * s); ctx.lineTo(x + s, y - 2 - 1.6 * s); }
  ctx.closePath(); ctx.fill();
}
function drawTv(ctx) {
  if (!BARS || !TT) return;
  const ts = chart.timeScale(), vr = ts.getVisibleLogicalRange();
  if (!vr) return;
  const B = BARS, X = (i) => ts.logicalToCoordinate(i), Y = (p) => candles.priceToCoordinate(p);
  const sp = Math.abs((X(1) ?? 0) - (X(0) ?? 0)), full = sp >= 4.5, lo = Math.floor(vr.from) - 3, hi = Math.ceil(vr.to) + 3;
  const inView = (i) => i >= lo && i <= hi;
  const bb = parseInt(CUR.InpBreakBars || '1', 10);
  if (typeof drawLab === 'function') drawLab(ctx, X, Y, lo, hi, full);          // the Exit Lab's trades (static/exitlab.js)
  if (show.setups && sp >= 2.5) for (const e of TT.events) {
    if (e.type !== 'setup' || !inView(e.bi)) continue;
    const x = X(e.bi), yh = Y(e.price), yl = Y(e.sl), yb = Y(e.v1);
    if (x == null || yh == null || yl == null) continue;
    ctx.fillStyle = 'rgba(255,235,59,0.07)'; ctx.fillRect(x - sp, yh, 2 * sp, yl - yh);
    ctx.strokeStyle = 'rgba(255,235,59,0.6)'; ctx.lineWidth = 1; ctx.strokeRect(x - sp, yh, 2 * sp, yl - yh);
    seg(ctx, x, yb, X(e.bi + bb + 1), yb, TVC.yel, 1, [2, 2]);
    if (full) tvTag(ctx, x, e.side > 0 ? yh : yl, [`${e.side > 0 ? 'long' : 'short'} setup · ${KIND(Math.round(e.v2), e.side)}`], TVC.tag, TVC.yel, e.side < 0, 10);
  }
  if (show.skips && full && MT && MT.matches) for (const e of MT.events) {
    if (e.type !== 'skip' || !inView(e.bi)) continue;
    const x = X(e.bi), y = e.side > 0 ? Y(B.h[e.bi]) : Y(B.l[e.bi]);
    if (x != null && y != null) tvTag(ctx, x, y, ['✖ skip'], 'rgba(120,123,134,0.6)', '#fff', e.side < 0, 9);
  }
  if (show.ghosts) for (const g of TT.GH) {
    if (g.biOut != null ? g.biOut < lo || g.biIn > hi : !inView(g.biIn)) continue;
    const x1 = X(g.biIn);
    if (g.biOut != null) seg(ctx, x1, Y(g.en), X(g.biOut), Y(g.ex), TVC.grey, 1, [2, 3]);
    const ya = g.side > 0 ? Y(B.l[g.biIn]) : Y(B.h[g.biIn]);
    if (x1 == null || ya == null) continue;
    if (full) tvTag(ctx, x1, ya, [`stand aside (${g.side > 0 ? 'BUY' : 'SELL'})`], 'rgba(54,58,69,0.8)', '#9598a1', g.side > 0, 10);
    else tri(ctx, x1, ya, g.side > 0, TVC.grey, 3);
  }
  if (show.mt5 && MT) for (const t of MT.TR) {                  // MT5's own trades: small triangles at the fill price
    if (!inView(t.biIn)) continue;
    const x = X(t.biIn), y = Y(t.en);
    if (x != null && y != null) tri(ctx, x, y + (t.side > 0 ? 6 : -6), t.side > 0, t.pnl > 0 ? '#00bfa5' : '#ff6d00', 4);
  }
  LBLS = []; VBTN = [];
  if (!show.trades) return;
  for (const t of TT.TR) {
    if (t.biOut < lo || t.biIn > hi) continue;
    const x1 = X(t.biIn), x2 = X(t.biOut), rc = t.pnl > 0 ? TVC.win : TVC.loss, sel = SEL === t.num;
    seg(ctx, x1, Y(t.sl), x2 === x1 ? x1 + sp : x2, Y(t.sl), TVC.loss, 2, [6, 4]);
    seg(ctx, x1, Y(t.en), x2, Y(t.ex), rc, sel ? 3 : 2, [2, 3]);
    const ye = Y(t.ex);
    if (x2 != null && ye != null) {
      ctx.strokeStyle = rc; ctx.lineWidth = 2; ctx.beginPath();
      ctx.moveTo(x2 - 3, ye - 3); ctx.lineTo(x2 + 3, ye + 3); ctx.moveTo(x2 + 3, ye - 3); ctx.lineTo(x2 - 3, ye + 3); ctx.stroke();
    }
  }
  for (const t of TT.TR) {
    if (t.biOut < lo || t.biIn > hi) continue;
    const x1 = X(t.biIn), x2 = X(t.biOut), rc = t.pnl > 0 ? TVC.win : TVC.loss;
    const yIn = t.side > 0 ? Y(B.l[t.biIn]) : Y(B.h[t.biIn]), yOut = t.side > 0 ? Y(B.h[t.biOut]) : Y(B.l[t.biOut]);
    if (x1 != null && yIn != null) {
      if (full) {
        const r = tvTag(ctx, x1, yIn, [`${t.side > 0 ? '▲ BUY' : '▼ SELL'} #${t.num}`, f2(t.en), '💬 ask Claude'], t.side > 0 ? TVC.buy : TVC.sell, '#fff', t.side > 0, 12);
        LBLS.push({ t, ...r });
        const n = NOTESD[tKey(t)];
        if (n && n.length && !VHIDE.has(tKey(t))) {          // Claude's verdict, beyond the label (below a BUY's, above a SELL's)
          const a = n[n.length - 1].a.replace(/[*#`]/g, ''), ex = VEXP.has(tKey(t));
          const lines = ex ? a.split(/\n/).flatMap((p) => (p.trim() ? wrap(p, 70, 60) : [''])).slice(0, 60) : wrap(a.split(/\n\s*\n/)[0], 46, 4);
          const v = tvTag(ctx, x1, t.side > 0 ? r.y + r.h + 4 : r.y - 4, lines, 'rgba(41,98,255,0.95)', '#fff', t.side > 0, 11);
          const bs = 15, by = v.y + 2;                         // two buttons on its top-right corner: expand / collapse, close
          [['✕', 'close'], [ex ? '–' : '⤢', 'exp']].forEach(([s, act], k) => {
            const bx = v.x + v.w - (k + 1) * (bs + 2) - 1;
            ctx.fillStyle = 'rgba(19,23,34,0.85)'; rrect(ctx, bx, by, bs, bs, 3); ctx.fill();
            ctx.fillStyle = '#fff'; ctx.font = '11px Arial'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(s, bx + bs / 2, by + bs / 2 + 1);
            VBTN.push({ key: tKey(t), act, x: bx, y: by, w: bs, h: bs });
          });
        }
      }
      else tri(ctx, x1, yIn, t.side > 0, t.side > 0 ? TVC.buy : TVC.sell, 4);
    }
    if (full && x2 != null && yOut != null) tvTag(ctx, x2, yOut, [`EXIT #${t.num}`, money(t.pnl)], TVC.tag, rc, t.side < 0, 11);
  }
}
class TvLabels {
  constructor() { this._views = [{ zOrder: () => 'top', renderer: () => ({ draw: (target) => target.useMediaCoordinateSpace(({ context }) => drawTv(context)) }) }]; }
  attached({ requestUpdate }) { this._req = requestUpdate; }
  detached() { this._req = null; }
  updateAllViews() {}
  paneViews() { return this._views; }
  update() { if (this._req) this._req(); }
}
const redraw = () => { if (TVL) TVL.update(); };

function evText(e, who) {
  const S = e.side > 0 ? `<span style="color:${C.up}">BUY</span>` : `<span style="color:${C.down}">SELL</span>`, tag = who ? `<span class="k">${who}</span> ` : '';
  switch (e.type) {
    case 'setup': return `${tag}◆ SETUP ${S} · ${KIND(Math.round(e.v2), e.side)} · break at ${f2(e.v1)}`;
    case 'skip': return `${tag}<span class="k">✕ ${e.side > 0 ? 'BUY' : 'SELL'} skipped: ${esc(e.text)}</span>`;
    case 'entry': return `${tag}▶ ${S} #${e.num} at ${f2(e.price)} · stop ${f2(e.sl)} · range box ${box(e.v2)} · ${esc(e.text)}`;
    case 'exit': return `${tag}■ EXIT #${e.num} at ${f2(e.price)} · ${esc(e.text)} · <b class="${cls(e.v1)}">${money(e.v1, 2)}</b>`;
    case 'ghost': return `${tag}<span class="k">◇ stand aside (range box ${box(e.v2)} unticked): the ${e.side > 0 ? 'BUY' : 'SELL'} would have entered at ${f2(e.price)}</span>`;
    case 'ghost_end': return `${tag}<span class="k">◇ stand-aside over: ${esc(e.text)} at ${f2(e.price)}</span>`;
  }
  return '';
}
function legend(i) {
  const B = BARS, col = B.c[i] >= B.o[i] ? C.up : C.down, v = (x) => `<b style="color:${col}">${f2(x)}</b>`;
  let h = `<div><span class="k">${fullFmt(B.t[i] + TZ)}</span> &nbsp;O ${v(B.o[i])} H ${v(B.h[i])} L ${v(B.l[i])} C ${v(B.c[i])}</div>`;
  if (TT && TT.ef) h += `<div><span style="color:${C.fast}">EMA ${CUR.InpEmaFast} ${f2(TT.ef[i])}</span> &nbsp;<span style="color:#5b8def">EMA ${CUR.InpEmaSlow} ${f2(TT.es[i])}</span> &nbsp;<span style="color:${C.adx}">ADX ${f1(B.adx[i])}</span> &nbsp;<span class="k">ATR ${f2(B.atr[i])}</span></div>`;
  for (const e of (TT && TT.EVB.get(i)) || []) h += `<div class="ev">${evText(e, '')}</div>`;
  if (MT && MT.matches) for (const e of MT.EVB.get(i) || []) if (e.type === 'skip') h += `<div class="ev">${evText(e, '')}</div>`;
  if (show.mt5 && MT) for (const e of MT.EVB.get(i) || []) if (e.type === 'entry' || e.type === 'exit') h += `<div class="ev">${evText(e, 'MT5')}</div>`;
  $('#legend').innerHTML = h;
}
// ---------- ask Claude about one trade ----------
function tradeContext(t) {
  const B = BARS, a = Math.max(0, t.biIn - 60), b = Math.min(B.t.length - 1, t.biOut + 10), P = (i) => fullFmt(B.t[i] + TZ);
  const candles = []; for (let i = a; i <= b; i++) candles.push([P(i), +f2(B.o[i]), +f2(B.h[i]), +f2(B.l[i]), +f2(B.c[i]), TT.ef ? +f2(TT.ef[i]) : null, TT.es ? +f2(TT.es[i]) : null, +f1(B.adx[i]), +f2(B.atr[i]), i === t.biIn ? 'ENTRY' : i === t.biOut ? 'EXIT' : '']);
  const evs = []; for (let i = a; i <= b; i++) for (const e of TT.EVB.get(i) || []) evs.push({ at: P(i), type: e.type, side: e.side, price: e.price, sl: e.sl, v1: e.v1, v2: e.v2, text: e.text, num: e.num });
  let setup = null; for (let i = t.biIn; i >= Math.max(0, t.biIn - 8) && !setup; i--) for (const e of TT.EVB.get(i) || []) if (e.type === 'setup' && e.side === t.side) { setup = { at: P(i), kind: KIND(Math.round(e.v2), e.side), high: B.h[i], low: B.l[i], open: B.o[i], close: B.c[i], break_level: e.v1 }; break; }
  const same = (f) => { const s = TT.TR.filter(f), w = s.filter((x) => x.pnl > 0).length; return { trades: s.length, win_rate: s.length ? Math.round(100 * w / s.length) + '%' : '-', net: Math.round(s.reduce((q, x) => q + x.pnl, 0)) }; };
  const changed = {}; for (const k in CUR) if (DFL[k] !== undefined && String(CUR[k]) !== String(DFL[k])) changed[k] = CUR[k];
  return { trade: { num: t.num, side: t.side > 0 ? 'BUY' : 'SELL', entry_time: P(t.biIn), entry: t.en, stop: t.sl, exit_time: P(t.biOut), exit: t.ex, result_usd: Math.round(t.pnl), why_closed: t.why, entry_note: t.info, range_box: box(t.bucket) },
    setup_candle: setup, candles_columns: ['time PKT', 'open', 'high', 'low', 'close', `EMA ${CUR.InpEmaFast}`, `EMA ${CUR.InpEmaSlow}`, 'ADX', 'ATR', 'mark'], candles, decisions: evs,
    same_side_whole_data: same((x) => x.side === t.side), same_side_same_box: same((x) => x.side === t.side && Math.round(x.bucket) === Math.round(t.bucket)),
    data: SRC.ds, rules: SRC.mode, settings_changed_from_defaults: changed, key_settings: Object.fromEntries(['InpEmaFast', 'InpEmaSlow', 'InpAdxMin', 'InpSlAtrMult', 'InpMaxRiskUsd', 'InpBreakPips', 'InpBreakBars', 'InpExitMode', 'InpLots'].map((k) => [k, CUR[k]])) };
}
function askHtml(t, busy) {
  const n = NOTESD[tKey(t)] || [];
  return `<div class="row" style="justify-content:space-between;align-items:center"><b>💬 Ask Claude about ${t.side > 0 ? 'BUY' : 'SELL'} #${t.num}</b><button id="tAskX">✕</button></div>
    <div class="k">${fullFmt(t.tIn + TZ)} · ${f2(t.en)} → ${f2(t.ex)} · <span class="${cls(t.pnl)}">${money(t.pnl)}</span> · ${esc(t.why || '')}</div>
    <textarea id="tAskQ" placeholder="e.g. Why did this lose? Was the setup clean? What should the EA have seen?" ${busy ? 'disabled' : ''}></textarea>
    <div class="row" style="gap:8px;align-items:center"><button id="tAskGo" class="primary" ${busy ? 'disabled' : ''}>${busy ? '⏳ Claude is inspecting this trade…' : 'Send to Claude'}</button><span class="k">Claude sees the trade, 60 candles before it, EMAs, ADX, ATR and the EA's decisions.</span></div>
    ${n.map((x, i) => [x, i]).reverse().map(([x, i]) => `<div class="qa"><b>You:</b> ${esc(x.q)}\n<b>Claude</b> <span class="k">${esc(x.at)}</span>: ${esc(x.a)}</div>` + hypHtml(t, x, i)).join('')}`;
}
const HYPJ = {};                                               // running hypothesis jobs by `${key}|${idx}|${kind}`
function hypHtml(t, x, i) {
  if (!/hypothes/i.test(x.a)) return '';
  const k = tKey(t), jt = HYPJ[`${k}|${i}|test`], jf = HYPJ[`${k}|${i}|feature`], T = x.test;
  let h = `<div class="row" style="gap:6px;margin-top:6px"><button data-hyp="test" data-i="${i}" ${jt ? 'disabled' : ''}>${jt ? '⏳ ' + esc(jt.phase || 'testing') : (T ? '🧪 Test again' : '🧪 Test hypothesis')}</button></div>`;
  if (T) {
    const [LA, LB] = T.labels, B0 = T.base, tot0 = B0.train.net + B0.test.net, c = (s) => `${money(s.net)} · ${s.wr}% · ${s.n}`;
    h += `<div class="k" style="margin-top:4px">Tested on ${T.ds === 'm15' ? '4 years' : '2026'} (${esc(T.at)}). Your settings: ${LA} ${money(B0.train.net)} · ${LB} ${money(B0.test.net)} · total ${money(tot0)}</div>`;
    T.hyps.forEach((y, j) => {
      const ch = [Object.entries(y.changes || {}).map(([a, b]) => `${esc(a.replace(/^Inp/, ''))} ${esc(b)}`).join(', '), y.describe ? `Exit Lab: ${esc(y.describe)}` : ''].filter(Boolean).join(' · ');
      h += `<div style="border-left:3px solid #2962ff;padding:4px 6px;margin-top:6px"><b>${esc(y.hypothesis || '')}</b><div class="k">${esc(y.note || '')}${y.exact === false ? ' (approximate)' : ''}</div>`;
      if (y.train) {
        const tot = y.train.net + y.test.net, both = y.train.net > B0.train.net && y.test.net > B0.test.net;
        h += `<div>${ch}${y.lab && Object.keys(y.lab).length ? ' <span class="tag" style="background:rgba(255,152,0,.2);border-radius:8px;padding:1px 6px;font-size:10px">EA v1.30 (InpX)</span>' : ''}</div>` +
          `<div>${LA} <span class="${cls(y.train.net - B0.train.net)}">${c(y.train)}</span> · ${LB} <span class="${cls(y.test.net - B0.test.net)}">${c(y.test)}</span> · total <b class="${cls(tot - tot0)}">${money(tot)}</b> (${money(tot - tot0)} vs yours)${both ? ' <span class="good">✓ better in both halves</span>' : ''}</div>` +
          (y.noop ? '<div class="warn">No effect: none of this acts on these trades (same result as yours).</div>' : '') +
          (y.stuck ? `<div class="bad">⚠ A trade never closed (open for ${y.open_end.days} days until the end of the data): nothing in this exit closes it, so it blocks every later setup - the numbers are not usable.</div>` : '') +
          (y.mode0 ? '<div class="warn">Tested with exit mode 0 (the v1.23 exits) - the only mode where these inputs act, and the one where the tester and MT5 disagree.</div>' : '') +
          (y.lab && Object.keys(y.lab).length ? `<button data-hlab="${i}|${j}">Open in the Exit Lab</button> ` : `<button data-happly="${i}|${j}">Apply to the chart</button> `);
      } else if (y.invalid) h += `<div class="warn">These settings are not valid together (e.g. the slow EMA not above the fast one).</div>`;
      else h += `<div class="warn">Neither the EA's settings nor the Exit Lab can express this: it needs a new feature.</div>`;
      h += `<button data-hfeat="${i}|${j}" ${jf ? 'disabled' : ''}>${jf ? '⏳ ' + esc(jf.phase || '') : '🛠 Convert hypothesis to feature'}</button></div>`;
    });
  }
  for (const f of x.features || []) h += `<div class="qa"><b>Feature added</b> <span class="k">${esc(f.at)}</span> (${esc(f.which)}):\n${esc(f.report)}</div>`;
  return h;
}
async function hypRun(t, i, kind, which) {
  const k = tKey(t), id = `${k}|${i}|${kind}`;
  const r = await api('/api/hyp', { key: k, idx: i, kind, which, inputs: CUR, ds: SRC.ds === 'tv' ? 'year' : SRC.ds });
  if (r.error) { toast(esc(r.error)); return; }
  HYPJ[id] = { phase: 'starting' }; if (ASKT === t) $('#tAsk').innerHTML = askHtml(t, false);
  for (;;) {
    await new Promise((res) => setTimeout(res, 3000));
    const j = await api('/api/hyp_job?id=' + r.id).catch(() => null);
    if (!j) continue;
    HYPJ[id] = j;
    if (!j.running) break;
    if (ASKT === t) { const q = $('#tAskQ') && $('#tAskQ').value; $('#tAsk').innerHTML = askHtml(t, false); if (q) $('#tAskQ').value = q; }
  }
  delete HYPJ[id];
  if (HYPJ[id] === undefined) {
    const j = await api('/api/hyp_job?id=' + r.id);
    if (j.error) toast('Claude: ' + esc(j.error));
    if (kind === 'feature' && !j.error) toast('Claude finished the feature. Its report is in the chat box. Restart Turtle TV (start_turtle_tv.bat) and reload to use the new setting.', 15000);
  }
  NOTESD = await api('/api/trade_notes'); if (ASKT === t) $('#tAsk').innerHTML = askHtml(t, false); redraw();
}
let ASKT = null;
function openAsk(t, L) {
  ASKT = t; if (VHIDE.delete(tKey(t))) { saveHide(); redraw(); }
  const el = $('#tAsk'), W = $('#chartWrap').clientWidth, H = $('#chartWrap').clientHeight;
  el.innerHTML = askHtml(t, false); el.hidden = false;
  el.style.left = Math.max(4, Math.min(W - 390, L.x + L.w + 8)) + 'px'; el.style.top = Math.max(4, Math.min(H - 240, L.y - 20)) + 'px';
  setTimeout(() => $('#tAskQ') && $('#tAskQ').focus(), 0);
}
async function sendAsk() {
  const t = ASKT, q = ($('#tAskQ').value || '').trim();
  if (!t || !q) return;
  const el = $('#tAsk'); el.innerHTML = askHtml(t, true);
  const r = await api('/api/ask_trade', { key: tKey(t), question: q, context: tradeContext(t) }).catch((e) => ({ error: String(e) }));
  if (r.error) toast('Claude: ' + esc(r.error)); else { NOTESD[tKey(t)] = r.notes; VHIDE.delete(tKey(t)); saveHide(); }
  if (ASKT === t) el.innerHTML = askHtml(t, false);
  redraw();
}
document.addEventListener('click', (e) => {
  if (e.target.id === 'tAskX') { $('#tAsk').hidden = true; ASKT = null; }
  if (e.target.id === 'tAskGo') sendAsk();
  const d = e.target.dataset || {};
  if (d.hyp && ASKT) hypRun(ASKT, +d.i, 'test');
  if (d.hlab && ASKT) {                                       // a hypothesis that is an Exit Lab recipe: open it there and test it
    const [i, j] = d.hlab.split('|').map(Number), y = NOTESD[tKey(ASKT)][i].test.hyps[j];
    TAB.tt = 'lab'; labOpen().then(() => { LABS.form = { ...LABS.spec.default, ...y.lab }; renderPanel('tt'); labStart('test', { lab: labForm() }); });
    document.querySelector('#panelTT').scrollIntoView({ behavior: 'smooth' });
  }
  if (d.happly && ASKT) {
    const [i, j] = d.happly.split('|').map(Number), y = NOTESD[tKey(ASKT)][i].test.hyps[j];
    CUR = { ...DFL, ...y.inputs }; markForm(); scheduleSim(0);
    toast(`On the chart: ${esc(Object.entries(y.changes).map(([a, b]) => a.replace(/^Inp/, '') + ' ' + b).join(', '))}. Check it in MT5 before trusting it.`);
  }
  if (d.hfeat && ASKT) {
    const [i, j] = d.hfeat.split('|').map(Number), y = NOTESD[tKey(ASKT)][i].test.hyps[j];
    if (confirm(`Claude will add "${y.hypothesis}" to the EA as a new setting (off by default), mirror it on the chart, test it in MT5, record the version and commit. It takes several minutes. Go?`)) hypRun(ASKT, i, 'feature', y.hypothesis + (y.note ? ' - ' + y.note : ''));
  }
});
document.addEventListener('keydown', (e) => { if (e.target.id === 'tAskQ' && e.key === 'Enter' && (e.ctrlKey || e.metaKey)) sendAsk(); });
api('/api/trade_notes').then((n) => { NOTESD = n || {}; redraw(); }).catch(() => {});

function focusTrade(t) {
  SEL = t.num;
  chart.timeScale().setVisibleLogicalRange({ from: t.biIn - 40, to: t.biOut + 40 });
  focusLines.forEach((l) => candles.removePriceLine(l));
  focusLines = [
    candles.createPriceLine({ price: t.en, color: '#2962ff', lineWidth: 1, lineStyle: 0, axisLabelVisible: true, title: `#${t.num} entry` }),
    candles.createPriceLine({ price: t.sl, color: C.down, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'stop' }),
    candles.createPriceLine({ price: t.ex, color: t.pnl > 0 ? C.win : C.loss, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'exit ' + money(t.pnl) }),
  ];
  legend(t.biIn); redraw();
  if (TAB.tt === 'trades') renderPanel('tt');
}

// ---------- results (both testers use the same tabs) ----------
function stats(list) {
  const n = list.length, w = list.filter((t) => t.pnl > 0).length;
  const gw = list.filter((t) => t.pnl > 0).reduce((s, t) => s + t.pnl, 0), gl = list.filter((t) => t.pnl <= 0).reduce((s, t) => s + t.pnl, 0);
  let eqv = 0, peak = 0, dd = 0;
  for (const t of [...list].sort((a, b) => a.tOut - b.tOut)) { eqv += t.pnl; peak = Math.max(peak, eqv); dd = Math.max(dd, peak - eqv); }
  return { n, w, net: gw + gl, pf: gl < 0 ? (gw / -gl).toFixed(2) : n ? '∞' : '–', aw: w ? gw / w : 0, al: n - w ? gl / (n - w) : 0, dd };
}
function groupBy(list, key) { const m = new Map(); for (const t of list) { const k = key(t); if (!m.has(k)) m.set(k, []); m.get(k).push(t); } return m; }
const ym = (t) => { const d = new Date((t + TZ) * 1000); return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`; };
const table = (head, rows, foot) => `<table><tr>${head.map((x) => `<th>${x}</th>`).join('')}</tr>${rows.join('')}${foot || ''}</table>`;
const card = (l, v, c = '') => `<div class="card"><div class="l">${l}</div><div class="v ${c}">${v}</div></div>`;
const half = (list, a) => list.filter((t) => (a ? t.tIn < TRAIN_END : t.tIn >= TRAIN_END));
function ddTxt(dd) {
  const m = String(dd ?? '').match(/^([\d\s.,]+)\s*\(([\d.]+)%\)/);
  return m ? `$${Math.round(parseFloat(m[1].replace(/[\s,]/g, ''))).toLocaleString('en-US')} <small class="k">(${m[2]}%)</small>` : esc(dd ?? '–');
}
function pOverview(D) {
  const s = stats(D.TR), a = stats(half(D.TR, true)), b = stats(half(D.TR, false)), mt = D.kind === 'mt', R = mt ? D.run.report || {} : {};
  let h = '<div class="row"><div><div class="cards">';
  h += card(mt ? 'Net profit (MT5 report)' : 'Net profit', money(mt ? R.net ?? s.net : s.net), cls(s.net)) + card('Profit factor', mt ? R.pf ?? s.pf : s.pf) +
       card('Win rate', pct(s.w, s.n)) + card('Trades', `${s.n} <small class="k">(${s.w} won)</small>`);
  h += card('Max drawdown', mt ? ddTxt(R.dd) : '$' + Math.round(s.dd).toLocaleString('en-US') + ' <small class="k">(closed trades)</small>') +
       card('Jan – Jun', a.n ? `<span class="${cls(a.net)}">${money(a.net)}</span> <small class="k">${pct(a.w, a.n)}</small>` : '<small class="k">no candles</small>') +
       card('Jul – Oct', b.n ? `<span class="${cls(b.net)}">${money(b.net)}</span> <small class="k">${pct(b.w, b.n)}</small>` : '<small class="k">no trades</small>') + card('Stood aside', D.GH.length);
  h += '</div>';
  if (mt) {
    const r = D.run;
    h += `<p class="note">${esc(r.from)} – ${esc(r.to)} · ${esc(r.symbol)} real ticks · ${r.delay === 'none' ? 'no delay' : 'random delay'} · ${esc(r.inputs.InpLots)} lots · history quality ${esc(R.quality ?? '?')} · run "${esc(r.label)}" ${esc(r.created)}</p>`;
    h += D.matches ? `<p class="note">✓ These are exactly the settings on screen.</p>`
      : `<p class="warn">⚠ This MT5 run has different settings from the ones on screen: ${Object.entries(D.diff).map(([k, v]) => `${esc(k.replace(/^Inp/, ''))} ${esc(v[1])} here vs ${esc(v[0])} on screen`).join(', ')}. Press "Check in MT5" to run the screen's settings.</p>`;
  } else {
    h += `<p class="note">The Turtle TV Tester · ${SRC.ds === 'tv' ? "TradingView's candles" : 'Blueberry MT5 candles'} · ${{ ea: "v1.27's rules, real spread and swap", chart: "the chart's rules ($0.17 spread, no swap), 1-minute data everywhere", chart_blind: "TradingView's way: the chart's rules, and blind inside the entry candle before Oct 12 (it had no 1-minute data there) - this reproduces the chart's panel" }[SRC.mode]} · ${TT.ms} ms.
      On Blueberry candles with v1.27's rules it takes 194 of MT5's 198 trades; on TradingView's candles, TradingView's way, 60 of the chart's 62. MT5 below stays the judge.</p>`;
    if (TT.honest) {
      const ms = Object.keys(TT.months);
      h += `<h4>TradingView's way vs the same chart with 1-minute data everywhere</h4>` + table(['Month', "TradingView's way", 'With 1-minute data'],
        ms.map((m) => { const a = TT.months[m], b = TT.honest.months[m] || { n: 0, w: 0, net: 0 }; const [y, mo] = m.split('-');
          return `<tr><td>${MON[+mo - 1]} ${y}</td><td>${a.w}/${a.n} = ${pct(a.w, a.n)} · ${money(a.net)}</td><td class="${b.w / Math.max(1, b.n) < a.w / Math.max(1, a.n) - 0.005 ? 'bad' : ''}">${b.w}/${b.n} = ${pct(b.w, b.n)} · ${money(b.net)}</td></tr>`; }));
      if (TT.honest.flips.length) h += `<p class="warn">TradingView scores ${TT.honest.flips.length} trade${TT.honest.flips.length > 1 ? 's' : ''} differently from what really happened inside the candle: ` +
        TT.honest.flips.map((f) => `${dt(f.t)} ${f.side > 0 ? 'BUY' : 'SELL'} ${money(f.tv)} on the chart, really ${money(f.real)} (${esc(f.why)})`).join('; ') + '.</p>';
    }
    const ch = Object.entries(diffDfl(CUR));
    h += `<h4>Settings different from v1.27</h4><div class="chips">${ch.length ? ch.map(([k, v]) => `<span>${esc(k.replace(/^Inp/, ''))} = ${esc(v)}</span>`).join('') : '<span>none - v1.27 exactly</span>'}</div>`;
  }
  h += `</div><div><h4>Equity (closed trades)</h4><div class="eq" id="eq_${D.kind}"></div></div></div>`;
  return h;
}
function drawEquity(D) {
  if (eq[D.kind]) { eq[D.kind].remove(); eq[D.kind] = null; }
  const el = $('#eq_' + D.kind);
  if (!el) return;
  const c = LW.createChart(el, { ...BASE, localization: { timeFormatter: fullFmt, priceFormatter: (v) => '$' + Math.round(v).toLocaleString('en-US') },
    timeScale: { borderColor: '#2a2e39', tickMarkFormatter: tickFmt }, handleScroll: false, handleScale: false, crosshair: { mode: 0 } });
  const s = c.addSeries(LW.BaselineSeries, { baseValue: { type: 'price', price: 0 }, lineWidth: 2, priceLineVisible: false });
  const pts = []; let cum = 0;
  for (const t of [...D.TR].sort((a, b) => a.tOut - b.tOut)) {
    cum += t.pnl; const time = t.tOut + TZ;
    if (pts.length && pts[pts.length - 1].time >= time) pts[pts.length - 1].value = cum; else pts.push({ time, value: cum });
  }
  s.setData(pts); c.timeScale().fitContent();
  eq[D.kind] = c;
}
function monthRows(D) {
  const g = groupBy(D.TR, (t) => ym(t.tOut));
  return [...g.keys()].sort().map((k) => ({ month: k, ...stats(g.get(k)) }));
}
function pMonths(D) {
  const g = groupBy(D.TR, (t) => ym(t.tOut)), ga = groupBy(D.GH, (t) => ym(t.tIn));
  const o = D.kind === 'tt' ? MT : TT, go = o ? groupBy(o.TR, (t) => ym(t.tOut)) : new Map();
  const rows = [...g.keys()].sort().map((k) => {
    const s = stats(g.get(k)), [y, m] = k.split('-'), so = stats(go.get(k) || []);
    return `<tr class="click" data-month="${k}"><td>${MON[+m - 1]} ${y}</td><td>${s.n}</td><td>${s.w}</td><td>${pct(s.w, s.n)}</td><td class="${cls(s.net)}">${money(s.net)}</td><td>${s.pf}</td><td>${(ga.get(k) || []).length}</td>` +
      (o ? `<td class="k">${pct(so.w, so.n)}</td>` : '') + '</tr>';
  });
  const s = stats(D.TR), so = o ? stats(o.TR) : null;
  return `<p class="note">By the month a trade closed (${TZ ? 'Pakistan time' : 'UTC'}). Click a month to see it on the chart.</p>` +
    table(['Month', 'Trades', 'Wins', 'Win rate', 'Net', 'PF', 'Stood aside'].concat(o ? [D.kind === 'tt' ? 'MT5 win rate' : 'Turtle TV win rate'] : []), rows,
      `<tr class="tot"><td>Total</td><td>${s.n}</td><td>${s.w}</td><td>${pct(s.w, s.n)}</td><td class="${cls(s.net)}">${money(s.net)}</td><td>${s.pf}</td><td>${D.GH.length}</td>${o ? `<td>${pct(so.w, so.n)}</td>` : ''}</tr>`);
}
function pWeekdays(D) {
  const g = groupBy(D.TR, (t) => new Date((t.tIn + TZ) * 1000).getUTCDay());
  const rows = [1, 2, 3, 4, 5, 6, 0].filter((d) => g.has(d)).map((d) => {
    const s = stats(g.get(d));
    return `<tr><td>${DOW[d]}</td><td>${s.n}</td><td>${s.w}</td><td>${pct(s.w, s.n)}</td><td class="${cls(s.net)}">${money(s.net)}</td><td>${s.pf}</td><td>${money(s.net / s.n)}</td></tr>`;
  });
  return `<p class="note">By the weekday a trade opened (${TZ ? 'Pakistan time' : 'UTC'}).</p>` + table(['Day', 'Trades', 'Wins', 'Win rate', 'Net', 'PF', 'Per trade'], rows);
}
function pRange(D) {
  const inp = D.kind === 'mt' ? D.run.inputs : CUR;
  const one = (side, bands, off) => {
    const rows = [];
    for (let b = 0; b <= 20; b++) {
      const k = b + off, tr = D.TR.filter((t) => Math.round(t.bucket) === k), gh = D.GH.filter((t) => Math.round(t.bucket) === k), s = stats(tr);
      const on = (bands || '')[b] !== '0', gn = gh.reduce((a, t) => a + (t.pnl || 0), 0);
      const tick = D.kind === 'tt' ? `<input type="checkbox" data-band="${side === 'BUY' ? 'B' : 'S'}${b}" ${on ? 'checked' : ''}>` : (on ? '✓' : '–');
      rows.push(`<tr class="${on ? '' : 'dim'}"><td>${box(k)}</td><td>${tick}</td><td>${s.n || ''}</td><td>${s.n ? pct(s.w, s.n) : ''}</td><td class="${cls(s.net)}">${s.n ? money(s.net) : ''}</td><td>${gh.length || ''}</td><td class="${cls(gn)}">${gh.length ? money(gn) : ''}</td></tr>`);
    }
    const sd = side === 'BUY' ? 'B' : 'S';
    const btns = D.kind === 'tt' ? ` <button data-bands="${sd}1">Select all</button> <button data-bands="${sd}0">Deselect all</button> <button data-bands="${sd}L">Deselect all losing ranges</button>` : '';
    return `<div><h4>${side} - where the entry sat in the last ${side === 'BUY' ? inp.InpRangeLook : inp.InpRangeLookS} candles' range${btns}</h4>` +
      table(['Box', 'Ticked', 'Trades', 'Win rate', 'Net', 'Stood aside', 'Would have made'], rows) + '</div>';
  };
  const allOn = (inp.InpBandsB + inp.InpBandsS).indexOf('0') < 0;
  return (D.kind === 'tt' ? `<p><button class="go" data-bands="OFF" ${allOn ? 'disabled' : ''}>Turn ranges off</button> <span class="k">${allOn ? 'Ranges are off: every box trades.' : 'Ticks every box on both sides = no range filter.'}</span></p>` : '') +
    `<p class="note">Unticked boxes are grey: there the EA ${(D.kind === 'tt' ? CUR : inp).InpBandOff === '0' ? 'skips the trade' : 'stood aside'}. "Would have made" = the stand-aside trades' result (same stop and exit, no swap).</p>` +
    `<div class="row">${one('BUY', inp.InpBandsB, 0)}${one('SELL', inp.InpBandsS, 21)}</div>`;
}
function pTrades(D) {
  const rows = D.TR.map((t) => `<tr class="click ${D.kind === 'tt' && SEL === t.num ? 'sel' : ''}" data-num="${t.num}" data-kind="${D.kind}"><td>#${t.num}</td><td style="color:${t.side > 0 ? C.up : C.down}">${t.side > 0 ? 'BUY' : 'SELL'}</td>` +
    `<td>${dt(t.tIn)}</td><td>${f2(t.en)}</td><td>${f2(t.sl)}</td><td>${dt(t.tOut)}</td><td>${f2(t.ex)}</td><td style="text-align:left">${esc(t.why)}</td><td class="${cls(t.pnl)}">${money(t.pnl, 2)}</td></tr>`);
  return `<p class="note">Click a trade to see it on the chart.${D.kind === 'mt' ? ' Net includes swap, exactly as MT5 booked it.' : ' Net includes swap.'}</p><div class="scroll">` +
    table(['#', 'Side', 'Entry', 'Price', 'Stop', 'Exit', 'Price', 'Why it closed', 'Net'], rows) + '</div>';
}
function reason(s) {
  if (/^ADX/.test(s)) return 'ADX below the minimum (ranging market)';
  if (/stop too far/.test(s)) return 'stop too far (over the max risk)';
  if (/not broken/.test(s)) return 'the high / low was not broken in time';
  if (/unticked box/.test(s)) return 'entry in an unticked range box';
  if (/ATR/.test(s)) return 'ATR outside the volatility band';
  return s.replace(/\$?-?\d+(\.\d+)?%?/g, '#');
}
function pSkips(D) {
  if (D.kind === 'tt') {
    const s = TT.stats, n = s.setups || 1;
    const rows = [['ADX below the minimum (ranging market)', s.adx], ['the high / low was not broken in time', s.no_break], ['stop too far (over the max risk)', s.risk],
      ['ATR outside the volatility band', s.atr_band], ['entry in an unticked range box (skip mode)', s.band_skip], ['market closed in between', s.gap]]
      .filter((r) => r[1]).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<tr><td>${k}</td><td>${v}</td><td>${pct(v, n)}</td></tr>`);
    return `<p class="note">${(s.setups || 0).toLocaleString()} setups. <b>${TT.TR.length}</b> became trades, <b>${TT.GH.length}</b> stood aside, and these were skipped:</p>` +
      table(['Why the setup was not traded', 'Setups', 'Share'], rows);
  }
  const sk = D.events.filter((e) => e.type === 'skip'), setups = D.events.filter((e) => e.type === 'setup').length;
  const g = groupBy(sk, (e) => reason(e.text));
  const rows = [...g.entries()].sort((a, b) => b[1].length - a[1].length).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.length}</td><td>${pct(v.length, setups)}</td></tr>`);
  return `<p class="note">${setups.toLocaleString()} setups. <b>${D.TR.length}</b> became trades, <b>${D.GH.length}</b> stood aside, and these were skipped:</p>` +
    table(['Why the setup was not traded', 'Setups', 'Share'], rows);
}
let OPTS = null;
const OPTUI = { obj: 'ret_dd', boxes: false, keep: false };   // the optimizer's controls, kept across redraws
function pOpt() {
  const o = OPTS;
  const obj = OPTUI.obj;
  let h = `<div class="row" style="align-items:center;gap:10px"><b>Step optimizer</b>
    <label>Score <select id="oObj">${[['ret_dd', 'net ÷ max drawdown'], ['net', 'net profit'], ['pf', 'profit factor'], ['wr', 'win rate'], ['entries', 'Entries: try every entry setting'], ['exits', 'Exits: try every exit setting'], ['ranges', 'Range boxes: most boxes at 100%']].map(([v, l]) => `<option value="${v}" ${v === obj ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
    <label class="tog"><input type="checkbox" id="oBox" ${OPTUI.boxes ? 'checked' : ''}> include the range boxes</label>
    <label class="tog"><input type="checkbox" id="oKeep" ${OPTUI.keep ? 'checked' : ''}> keep optimizing (restarts)</label>
    <button id="oGo" class="primary">Optimize from the settings on screen</button><button id="oStop">Stop</button></div>
    <p class="note">Each setting is moved one step up and down; a step that helps is repeated until it stops helping; all settings, pass after pass, until nothing improves.
    The score is measured on <b>Jan – Jun</b> only. <b>Jul – Oct</b> is shown beside it but never used to choose: if it gets worse while Jan – Jun improves, the settings are memorising the past.</p>`;
  if (!o || !o.baseline) return h;
  const [LA, LB] = o.labels || ['Jan – Jun', 'Jul – Oct'];
  if (o.kind === 'ranges') {
    const B0 = o.baseline, F = o.final, line = (x) => `${money(x.net)} · WR ${x.wr}% · PF ${x.pf} · ${x.n} trades`;
    h += `<p class="note">${o.running ? '⏳ running' : o.error ? 'stopped: ' + esc(o.error) : '✓ done'} · ${o.evals} settings tried in ${o.seconds} s · ${o.passes} passes ·
      <b>${o.perfect}</b> range boxes at 100% in ${LA} (a box counts with ${o.min_box}+ trades, all winners). Every box starts ticked; a box that reaches 100% is <b>locked</b> - no later step may break it - and the search moves on to the next box.
      At the end only the 100% boxes are ticked. ${LB} is never looked at: it shows whether those boxes stay 100%.</p>`;
    if (B0) h += `<p class="note">Start (all boxes ticked): ${LA} ${line(B0.train)} · ${LB} ${line(B0.test)} · ${B0.perfect} boxes at 100%.</p>`;
    if (F) {
      h += `<h4>Result: only the 100% boxes ticked <button data-rfinal="1" class="primary">Apply this setting</button></h4>` +
        table(['', LA + ' (optimized on)', LB + ' (unseen)', 'Total'], [`<tr><td>Trades</td><td class="${cls(F.train.net)}">${line(F.train)}</td><td class="${cls(F.test.net)}">${line(F.test)}</td><td class="${cls(F.train.net + F.test.net)}"><b>${money(F.train.net + F.test.net)}</b></td></tr>`]) +
        `<p class="note">${F.kept} of ${F.boxes.length} boxes stayed 100% in ${LB}.</p>` +
        table(['Side', 'Box', LA, LB + ' (unseen)'], F.boxes.map((x) => `<tr><td>${x.side === 'B' ? 'BUY' : 'SELL'}</td><td>${box(x.box + (x.side === 'S' ? 21 : 0))}</td><td class="good">${x.n}/${x.n} = 100% · ${money(x.net)}</td>` +
          `<td class="${!x.tn ? 'k' : x.tw === x.tn ? 'good' : 'bad'}">${x.tn ? `${x.tw}/${x.tn} = ${pct(x.tw, x.tn)} · ${money(x.tnet)}` : 'no trades'}</td></tr>`));
    }
    if (o.steps.length) h += `<h4>Steps that added 100% boxes</h4><div class="scroll">` + table(['#', 'Setting', 'Step', 'Boxes at 100%', 'Trades in them', 'New boxes', ''], o.steps.map((s, i) =>
      `<tr><td>${i + 1}</td><td style="text-align:left">${esc(s.setting.replace(/^Inp/, ''))}</td><td>${esc(s.from)} → ${esc(s.to)}</td><td>${s.perfect}</td><td>${s.trades}</td><td class="k">${esc(s.new.join(', '))}</td><td><button data-rstep="${i}">Apply this setting</button></td></tr>`)) + '</div>';
    return h;
  }
  if (o.kind === 'survey') {
    const B0 = o.baseline, tot0 = B0.train.net + B0.test.net;
    h += `<p class="note">${o.running ? '⏳ running' : o.error ? 'stopped: ' + esc(o.error) : '✓ done'} · ${o.group === 'entries' ? 'every entry setting' : 'every exit setting'}, one at a time from the settings on screen · ${o.evals} tried in ${o.seconds} s.
      Your settings: ${LA} ${money(B0.train.net)} · ${LB} ${money(B0.test.net)} · total <b>${money(tot0)}</b>. Green rows beat yours on BOTH halves. Python's result is a hypothesis: MT5 decides.</p>`;
    h += `<div class="scroll">` + table(['Setting', 'Value', 'Also set', LA, LB, 'Total', 'vs yours', ''], o.rows.map((r, i) => {
      const both = r.train.net > B0.train.net && r.test.net > B0.test.net;
      const w = Object.entries(r.with || {}).map(([k, v]) => `${esc(k.replace(/^Inp/, ''))}=${esc(v)}`).join(' ');
      return `<tr${both ? ' style="background:rgba(0,230,118,.08)"' : ''}><td style="text-align:left">${esc(r.setting.replace(/^Inp/, ''))}</td><td>${esc(r.value.length > 12 ? 'all on' : r.value)}</td><td class="k">${w}${r.noop ? ' <span class="k">no effect</span>' : ''}${r.v123 ? ' <span class="bad" title="verify_settings.py: on the v1.23 exits the tester and MT5 move the result in opposite directions - check in MT5">⚠ v1.23 exits: tester ≠ MT5</span>' : ''}${!r.test.n ? ' <span class="bad">⚠ no trades in ' + LB + '</span>' : ''}</td>` +
        `<td class="${cls(r.train.net)}">${money(r.train.net)} · ${r.train.wr}% · ${r.train.n}</td><td class="${cls(r.test.net)}">${money(r.test.net)} · ${r.test.wr}% · ${r.test.n}</td>` +
        `<td class="${cls(r.total)}"><b>${money(r.total)}</b></td><td class="${cls(r.total - tot0)}">${money(r.total - tot0)}</td><td><button data-surv="${i}">Apply this setting</button></td></tr>`; })) + '</div>';
    return h;
  }
  const B = o.baseline, best = o.best, line = (x) => x ? `${money(x.net)} · WR ${x.wr}% · PF ${x.pf} · ${x.n} trades` : '–';
  h += `<p class="note">${o.running ? '⏳ running' : o.error ? 'stopped: ' + esc(o.error) : '✓ done'} · ${o.evals.toLocaleString()} settings tried in ${o.seconds} s (each one a full run over ${o.ds === 'm15' ? 'all 4 years' : 'the year'}) · ${o.passes} passes${o.restarts ? ' · ' + o.restarts + ' restarts' : ''}</p>`;
  h += table(['', `${LA} (optimized on)`, `${LB} (unseen)`, 'All'], [
    `<tr><td>Your settings</td><td>${line(B.train)}</td><td>${line(B.test)}</td><td>${line(B.year)}</td></tr>`,
    best ? `<tr class="tot"><td>Best found</td><td>${line(best.train)}</td><td class="${best.test && B.test && best.test.net < B.test.net ? 'bad' : 'pos'}">${line(best.test)}</td><td>${line(best.year)}</td></tr>` : '']);
  if (best && best.test && B.test && best.test.net < B.test.net) h += `<p class="warn">⚠ Better on ${LA} but WORSE on the unseen ${LB} (${money(best.test.net - B.test.net)}): these settings are fitting the past. Don't trust them without more evidence.</p>`;
  if (o.mt5 && o.mt5.run) {
    const r = RUNS.find((x) => x.id === o.mt5.run);
    h += r ? `<p class="note">✓ MT5 checked the best: <b>${money(r.net || 0)} · PF ${r.pf} · ${r.trades} trades</b> (no delay). Show it on the chart to compare both halves in the MT5 section.</p>`
           : `<p class="note">⏳ The best is running in MT5 now (about a minute); its result appears in the MT5 section.</p>`;
  } else if (best && Object.keys(best.changed).length && !o.running) h += `<p class="note">The best goes to MT5 automatically when the optimizer finishes.</p>`;
  if (best && Object.keys(best.changed).length) h += `<p><button id="oApply" class="go">Show the best on the chart</button> <span class="k">changes: ${Object.entries(best.changed).map(([k, v]) => `${esc(k.replace(/^Inp/, ''))} ${esc(CUR[k] ?? '')} → ${esc(v)}`).join(', ')}</span></p>`;
  const steps = o.log.map((l, i) => `<tr><td>${i + 1}</td><td style="text-align:left">${esc(l.run)}</td><td style="text-align:left">${esc(l.setting.replace(/^Inp/, ''))}</td><td>${esc(l.from)} → ${esc(l.to)}</td><td>${(+l.score).toFixed(2)}</td>` +
    `<td class="${cls(l.train.net)}">${money(l.train.net)} · ${l.train.wr}%</td><td class="${cls(l.test.net)}">${money(l.test.net)} · ${l.test.wr}%</td><td class="${cls(l.train.net + l.test.net)}"><b>${money(l.train.net + l.test.net)}</b></td><td class="k">${l.t}s</td>` +
    `<td>${l.inputs ? `<button data-step="${o.log.length > 200 ? i + o.log.length - 200 : i}">Apply this setting</button>` : ''}</td></tr>`);
  h += `<h4>Steps that helped</h4><div class="scroll">${table(['#', 'Run', 'Setting', 'Change', 'Score', LA, LB, 'Total', 'At', ''], steps)}</div>`;
  if (o.board && o.board.length > 1) h += `<h4>Best of each restart</h4>` + table(['Score', LA, LB, 'Total', 'Changes', ''],
    o.board.map((x, i) => `<tr><td>${(+x.score).toFixed(2)}</td><td>${money(x.train.net)} · ${x.train.wr}%</td><td class="${cls(x.test.net - B.test.net)}">${money(x.test.net)} · ${x.test.wr}%</td><td><b>${money(x.train.net + x.test.net)}</b></td>` +
      `<td style="text-align:left" class="k">${Object.entries(x.changed).map(([k, v]) => `${esc(k.replace(/^Inp/, ''))}=${esc(v)}`).join(' ')}</td><td><button data-board="${i}">show</button></td></tr>`));
  return h;
}
function renderPanel(sec) {
  document.querySelectorAll(`nav[data-sec="${sec}"] button`).forEach((b) => b.classList.toggle('on', b.dataset.t === TAB[sec]));
  const el = $(sec === 'tt' ? '#panelTT' : '#panelMT'), D = sec === 'tt' ? TT : MT;
  const keep = [...el.querySelectorAll('.scroll')].map((s) => s.scrollTop);              // redraws keep the lists where Zee scrolled them
  const back = () => el.querySelectorAll('.scroll').forEach((s, i) => { if (keep[i] != null) s.scrollTop = keep[i]; });
  if (sec === 'tt' && TAB.tt === 'opt') { el.innerHTML = pOpt(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'lab') { el.innerHTML = pLab(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'ml') { el.innerHTML = pML(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'lego') { el.innerHTML = pLego(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'mission') { el.innerHTML = pMission(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'stress') { el.innerHTML = pStress(); back(); return; }
  if (!D) { el.innerHTML = `<p class="note">${sec === 'mt' ? 'No MT5 run yet. Press "Check in MT5" to run the settings on screen in the Strategy Tester (about a minute).' : 'Loading…'}</p>`; return; }
  el.innerHTML = { overview: pOverview, months: pMonths, weekdays: pWeekdays, range: pRange, trades: pTrades, skips: pSkips }[TAB[sec]](D);
  back();
  if (TAB[sec] === 'overview') drawEquity(D);
}
function renderAll() { renderPanel('tt'); renderPanel('mt'); }

// ---------- the Turtle TV Tester: instant ----------
function scheduleSim(ms = 120) { clearTimeout(simTimer); simTimer = setTimeout(runSim, ms); }
async function runSim() {
  const seq = ++simSeq;
  const emaKey = `${SRC.ds}/${CUR.InpEmaFast}/${CUR.InpEmaSlow}`, needEma = !TT || TT.emaKey !== emaKey;
  const r = await api('/api/sim', { inputs: CUR, ema: needEma, setups: show.setups, ds: SRC.ds, mode: SRC.mode, lab: ACTIVE_LAB });   // EMAs / setups only when they are needed (smooth sliding)
  if (seq !== simSeq) return;                                  // a newer change is already on its way
  if (r.error) return toast('⚠ ' + esc(r.error));
  const keep = TT && !needEma ? { ef: TT.ef, es: TT.es } : { ef: r.ef, es: r.es };
  TT = Object.assign(derive('tt', r.events, parseFloat(CUR.InpLots || '1')), { ms: r.ms, stats: r.stats, year: r.year, emaKey, honest: r.honest, months: r.months, ...keep });
  drawEmas(); redraw(); await pickMt5(); renderAll();
  $('#simMs').textContent = `· Turtle TV Tester ${r.ms} ms`;
  $('#infoTT').textContent = `${SRC.ds === 'tv' ? "TradingView's candles" : 'Blueberry MT5 candles'} · ${{ ea: 'v1.27 rules', chart: "the chart's rules", chart_blind: "TradingView's way" }[SRC.mode]} · ` +
    `${r.year.n} trades · WR ${r.year.wr}% · ${money(r.year.net)} · PF ${r.year.pf} · ${r.ms} ms`;
  labBanner();
  const n = BARS.t.length;
  if (firstView) { chart.timeScale().setVisibleLogicalRange({ from: n - 1500, to: n + 5 }); firstView = false; }
  legend(n - 1);
  markForm();
}

// ---------- settings panel: sliders for numbers, words for choices (Zee: "make all settings with numbers to be like sliders") ----------
const ENUMS = {
  InpLongRule: [[0, 'on the fast EMA, exit at the slow'], [1, 'on the slow EMA, exit at the fast'], [2, 'both']],
  InpShortLine: [[0, 'on the slow EMA'], [1, 'on the fast EMA'], [2, 'on either EMA']],
  InpTouchMode: [[0, 'the candle touches the EMA'], [1, 'the wick touches, body on the trade side']],
  InpExitMode: [[0, 'v1.23 exits (MT5 only)'], [1, 'next EMA beyond the entry'], [2, 'close back across the slow EMA']],
  InpBandOff: [[0, 'skip the trade'], [1, 'stand aside while it would have run']],
  InpSlMode: [[0, 'pips beyond the setup candle'], [1, 'ATR × from the entry'], [2, '$ from the entry']],
  InpEntryMode: [[0, 'market order on the break'], [1, 'wait for a dip (MT5 only)'], [2, 'liquidity sweep (MT5 only)']],
};
function sliderRange(i, v) {
  let [lo, hi, st] = i.range || (() => {
    const d = Math.abs(parseFloat(i.default) || 0);
    if (i.type === 'int') return [0, Math.max(10, Math.ceil(d * 2)), 1];
    const h = Math.max(1, d * 2);
    return [0, +h.toFixed(2), h <= 2 ? 0.01 : h <= 10 ? 0.05 : h <= 100 ? 0.5 : 1];
  })();
  const x = parseFloat(v);
  if (!isNaN(x)) { lo = Math.min(lo, x); hi = Math.max(hi, x); }               // never clip the current value
  return [lo, hi, st];
}
function buildForm() {
  const groups = new Map();
  for (const i of INPUTS.inputs) { if (!groups.has(i.group)) groups.set(i.group, []); groups.get(i.group).push(i); }
  let h = '';
  for (const [g, list] of groups) {
    h += `<div class="igrp"><h5>${esc(g)}</h5>`;
    for (const i of list) {
      const v = CUR[i.name] ?? i.default;
      let field;
      if (ENUMS[i.name]) field = `<select data-n="${i.name}">${ENUMS[i.name].map(([k, l]) => `<option value="${k}" ${same(v, k) ? 'selected' : ''}>${k} · ${esc(l)}</option>`).join('')}</select>`;
      else if (i.type === 'bool') field = `<select data-n="${i.name}"><option ${String(v) === 'true' ? 'selected' : ''}>true</option><option ${String(v) !== 'true' ? 'selected' : ''}>false</option></select>`;
      else if (i.type === 'string') field = `<input data-n="${i.name}" value="${esc(v)}" spellcheck="false">`;
      else {
        const [lo, hi, st] = sliderRange(i, v);
        field = `<div class="sl"><input type="range" data-r="${i.name}" min="${lo}" max="${hi}" step="${st}" value="${esc(v)}"><input class="num" data-n="${i.name}" type="number" step="${st}" value="${esc(v)}"></div>`;
      }
      h += `<div class="inp ${i.sim ? '' : 'mt5'}" title="${esc(i.name)}: ${esc(i.comment)}${i.sim ? '' : ' · MT5 only: the Turtle TV Tester does not use it'}">` +
           `<span class="n">${esc(i.name.replace(/^Inp/, ''))}${i.sim ? '' : ' <small>(MT5 only)</small>'}</span>${field}</div>`;
    }
    h += '</div>';
  }
  $('#form').innerHTML = h;
  markForm();
}
function markForm() {
  document.querySelectorAll('#form [data-n], #form [data-r]').forEach((el) => {
    const n = el.dataset.n || el.dataset.r;
    if (document.activeElement !== el && String(el.value) !== String(CUR[n])) {
      if (el.dataset.r && parseFloat(CUR[n]) > parseFloat(el.max)) el.max = CUR[n];
      if (el.dataset.r && parseFloat(CUR[n]) < parseFloat(el.min)) el.min = CUR[n];
      el.value = CUR[n];
    }
    el.closest('.inp').classList.toggle('chg', !same(CUR[n], DFL[n]));
  });
}
function setBands(key, s) { CUR[key] = s; markForm(); scheduleSim(0); }
document.addEventListener('change', (e) => {
  const b = e.target.dataset && e.target.dataset.band;
  if (b) { const key = 'InpBands' + b[0], i = +b.slice(1), s = (CUR[key] || '').padEnd(21, '1').split(''); s[i] = e.target.checked ? '1' : '0'; setBands(key, s.join('')); }
  if (e.target.id === 'oObj') OPTUI.obj = e.target.value;
  if (e.target.id === 'oBox') OPTUI.boxes = e.target.checked;
  if (e.target.id === 'oKeep') OPTUI.keep = e.target.checked;
});
$('#form').addEventListener('input', (e) => {
  const el = e.target, n = el.dataset.n || el.dataset.r;
  if (!n || el.value === '') return;
  CUR[n] = el.value.trim();
  const twin = el.dataset.r ? el.parentElement.querySelector('[data-n]') : el.parentElement.querySelector('[data-r]');
  if (twin) twin.value = CUR[n];
  el.closest('.inp').classList.toggle('chg', !same(CUR[n], DFL[n]));
  scheduleSim(el.dataset.r ? 60 : 120);
});
async function setSource() {
  const ds = $('#srcDs').value, mode = $('#srcMode').value, keep = chart.timeScale().getVisibleRange();
  SRC.mode = mode;
  if (ds !== SRC.ds) {
    SRC.ds = ds; BARS = await getBars(ds); drawBars(); TT = null; MT = null;
  }
  await runSim();
  if (keep) try { chart.timeScale().setVisibleRange(keep); } catch (e) { /* outside the other candles */ }
  if (ds === 'tv' && BARS.ticks_until) toast(`TradingView's candles: Aug 3 → Oct 19. Inside them the Blueberry 1-minute candles until ${fullFmt(BARS.ticks_until + TZ)}, ` +
    'after that one step per candle. "TradingView\'s way" reproduces the chart\'s panel; "the chart\'s rules" shows what it would score with 1-minute data everywhere.', 12000);
}
$('#srcDs').onchange = setSource;
$('#srcMode').onchange = setSource;
$('#btnReset').onclick = () => { CUR = { ...DFL }; markForm(); scheduleSim(0); };
$('#btnSet').onclick = () => { document.body.classList.remove('ask-open'); document.body.classList.toggle('set-open'); };

// ---------- MT5 runs ----------
async function loadRuns() {
  RUNS = await api('/api/runs');
  $('#runSel').innerHTML = RUNS.length ? RUNS.map((r) => `<option value="${r.id}">${esc(r.label)} · ${money(r.net || 0)} · PF ${r.pf} · ${r.trades} trades · ${r.delay === 'none' ? 'no delay' : 'random delay'} · ${esc((r.created || '').slice(5))}</option>`).join('')
    : '<option>no MT5 runs yet</option>';
}
function runMatches(r) {
  const a = r.changed || {}, b = diffDfl(CUR);
  return Object.keys(a).length === Object.keys(b).length && Object.entries(b).every(([k, v]) => k in a && same(a[k], v));
}
async function pickMt5(forceId) {
  if (!RUNS.length) { MT = null; renderPanel('mt'); return; }
  const want = forceId || (RUNS.find(runMatches) || {}).id || (MT && MT.run.id) || RUNS[0].id;
  if (!MT || MT.run.id !== want) {
    const run = await api('/api/run?id=' + encodeURIComponent(want));
    MT = Object.assign(derive('mt', run.events, parseFloat(run.inputs.InpLots || '1')), { run });
  }
  const diff = {};
  for (const [k, v] of Object.entries(MT.run.inputs)) if (k in CUR && !same(v, CUR[k])) diff[k] = [CUR[k], v];
  MT.diff = diff; MT.matches = !Object.keys(diff).length;
  $('#runSel').value = MT.run.id;
  const s = stats(MT.TR);
  $('#infoMT').innerHTML = MT.matches ? `${s.n} trades · WR ${pct(s.w, s.n)} · ${money(MT.run.report.net ?? s.net)} · PF ${MT.run.report.pf}` : '<span class="warn">⚠ different settings from the screen</span>';
  renderPanel('mt'); redraw();
}
async function poll() {
  try {
    const s = await api('/api/status');
    ['#btnCheck', '#btnExport'].forEach((b) => ($(b).disabled = !!s.busy));
    if (s.busy) setStatus(`MT5 running "${s.label}" · ${s.phase} · ${s.elapsed ?? 0} s`, 'busy');
    else if (s.error) setStatus('last MT5 run failed: ' + s.error, 'err');
    else setStatus('');
    if (!s.busy && s.last && s.last !== lastSeen) {
      const first = lastSeen === undefined; lastSeen = s.last;
      if (!first) { await loadRuns(); MT = null; await pickMt5(s.last); toast(`MT5 result in: <b>${esc(MT.run.label)}</b> · ${money(MT.run.report.net || 0)} · PF ${MT.run.report.pf}`); }
    }
    const busyUi = document.activeElement && document.activeElement.closest && document.activeElement.closest('#panelTT') && /SELECT|INPUT/.test(document.activeElement.tagName);
    if (!busyUi && TAB.tt === 'opt' && OPTS && (OPTS.running || (OPTS.mt5 && OPTS.mt5.run && !RUNS.find((x) => x.id === OPTS.mt5.run)))) { OPTS = await api('/api/opt'); renderPanel('tt'); }
  } catch (e) { setStatus('Turtle TV server not reachable', 'err'); }
  setTimeout(poll, OPTS && OPTS.running ? 700 : 2000);
}

// ---------- TradingView ----------
async function takeTv(quiet) {
  const r = await api('/api/tv');
  if (r.error) { $('#tvDot').className = 'dot bad'; if (!quiet) toast('⚠ TradingView: ' + esc(r.error)); return; }
  $('#tvDot').className = 'dot ok'; $('#tvDot').title = `TradingView ${r.symbol} · read at ${r.at}`;
  const key = JSON.stringify(r.sets);
  if (quiet && key === tvKey) return;
  tvKey = key;
  CUR = { ...DFL, ...r.sets };
  markForm(); scheduleSim(0);
  if (!quiet || (r.notes || []).length) toast(`TradingView's settings are on the chart (${r.symbol}).` + (r.notes || []).map((n) => `<div class="warn">⚠ ${esc(n)}</div>`).join(''));
}
$('#btnTake').onclick = () => takeTv(false);
(function follow() { setTimeout(async () => { if ($('#tFollow').checked) { try { await takeTv(true); } catch (e) { /* TradingView closed */ } } follow(); }, 4000); })();

// ---------- Ask Claude: the chart picture + the data behind it ----------
function askContext() {
  const n = BARS.t.length, vr = chart.timeScale().getVisibleLogicalRange();
  const a = Math.max(0, Math.floor(vr ? vr.from : n - 80)), b = Math.min(n - 1, Math.ceil(vr ? vr.to : n - 1));
  const step = Math.max(1, Math.ceil((b - a + 1) / 150)), cs = [];
  for (let i = a; i <= b; i += step) cs.push({ time: fullFmt(BARS.t[i] + TZ), o: BARS.o[i], h: BARS.h[i], l: BARS.l[i], c: BARS.c[i], ema_fast: +f2(TT.ef[i]), ema_slow: +f2(TT.es[i]), adx: BARS.adx[i] });
  const tview = (D) => D.TR.filter((t) => t.biOut >= a && t.biIn <= b).map((t) => ({ num: t.num, side: t.side > 0 ? 'BUY' : 'SELL', entry: dt(t.tIn), entry_price: t.en, stop: t.sl,
    exit: dt(t.tOut), exit_price: t.ex, net: Math.round(t.pnl), why_closed: t.why, range_box: box(t.bucket) }));
  const sum = (D) => { const s = stats(D.TR), x = stats(half(D.TR, true)), y = stats(half(D.TR, false));
    return { trades: s.n, win_rate: pct(s.w, s.n), net: Math.round(s.net), pf: s.pf, max_dd_closed: Math.round(s.dd), jan_jun: { net: Math.round(x.net), wr: pct(x.w, x.n), trades: x.n },
      jul_oct: { net: Math.round(y.net), wr: pct(y.w, y.n), trades: y.n }, stood_aside: D.GH.length, months: monthRows(D).map((m) => ({ month: m.month, trades: m.n, wr: pct(m.w, m.n), net: Math.round(m.net) })) }; };
  return {
    time_zone: TZ ? 'Pakistan time (UTC+5)' : 'UTC', chart_view: `${fullFmt(BARS.t[a] + TZ)} to ${fullFmt(BARS.t[b] + TZ)}`,
    settings_changed_from_v127: diffDfl(CUR), all_settings: CUR,
    turtle_tv_tester: { ...sum(TT), skip_reasons: TT.stats }, trades_in_view: tview(TT),
    mt5: MT ? { same_settings_as_screen: MT.matches, run: MT.run.label, delay: MT.run.delay, report_net: MT.run.report.net, report_pf: MT.run.report.pf, ...sum(MT) } : null,
    optimizer: OPTS && OPTS.best ? { best_changes: OPTS.best.changed, best_train: OPTS.best.train, best_test: OPTS.best.test, baseline_train: OPTS.baseline.train, baseline_test: OPTS.baseline.test } : null,
    candles_in_view: cs,
  };
}
function md(s) {
  const e = esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>');
  return e.split(/\n{2,}/).map((p) => (/^\s*[-*] /m.test(p) ? '<ul>' + p.split(/\n/).map((l) => l.replace(/^\s*[-*] /, '')).filter(Boolean).map((l) => `<li>${l}</li>`).join('') + '</ul>'
    : /^#{1,4} /.test(p) ? `<h4>${p.replace(/^#{1,4} /, '')}</h4>` : `<p>${p.replace(/\n/g, '<br>')}</p>`)).join('');
}
function drawAsk() {
  $('#askLog').innerHTML = ASK.map((m) => `<div class="msg ${m.role}">${m.role === 'user' ? `<b>You:</b> ${esc(m.text)}` : m.pending ? '<span class="k">Claude is looking at the chart…</span>' : md(m.text)}</div>`).join('');
  $('#askLog').scrollTop = 1e9;
}
async function ask() {
  const q = $('#askQ').value.trim() || 'Look at the chart and the results. What do you see, and which setting changes would you test next to make the strategy better? Be specific.';
  $('#askQ').value = '';
  const img = chart.takeScreenshot().toDataURL('image/jpeg', 0.85).split(',')[1];
  const history = ASK.filter((m) => !m.pending).slice(-6).map((m) => ({ role: m.role, text: m.text }));
  ASK.push({ role: 'user', text: q }, { role: 'assistant', pending: true, text: '' });
  drawAsk();
  $('#btnAskGo').disabled = true;
  try {
    const r = await api('/api/ask', { question: q, image: img, context: askContext(), history });
    ASK[ASK.length - 1] = { role: 'assistant', text: r.error ? '⚠ ' + r.error : r.text };
  } catch (e) { ASK[ASK.length - 1] = { role: 'assistant', text: '⚠ ' + e }; }
  $('#btnAskGo').disabled = false;
  drawAsk();
}
$('#btnAsk').onclick = () => { document.body.classList.remove('set-open'); document.body.classList.toggle('ask-open'); if (document.body.classList.contains('ask-open')) $('#askQ').focus(); };
$('#btnAskGo').onclick = ask;
$('#askQ').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); } });

// ---------- saved settings ----------
let SAVEDS = [];
function labBanner() {                                          // the main tester says when it runs an Exit Lab exit on top of the EA
  let b = document.getElementById('labBanner');
  if (!ACTIVE_LAB) { if (b) b.remove(); return; }
  if (!b) { b = document.createElement('div'); b.id = 'labBanner'; $('#infoTT').parentNode.insertBefore(b, $('#infoTT')); }
  b.innerHTML = `⚗️ with the Exit Lab exit: <b>${esc(ACTIVE_LAB._d || 'lab exit')}</b> - not an EA setting yet (MT5 can't run it) <button id="labBannerOff" class="dexbtn sm">remove</button>`;
}
async function loadSaved() {
  SAVEDS = await api('/api/saved');
  const dsName = { year: 'Blueberry 2026 (ticks)', tv: "TradingView's candles", m15: 'Blueberry 2023 → now' };
  $('#panelSaved').innerHTML = SAVEDS.length ? table(['Saved', 'Candles', 'Trades', 'Win rate', 'Net', 'PF', 'Changes from v1.27', ''],
    SAVEDS.map((s, i) => { const r = s.result || {};
      return `<tr><td>${esc(s.name)}</td><td>${esc(dsName[s.ds] || s.ds || '')}</td><td>${r.n ?? ''}</td><td>${r.wr != null ? r.wr + '%' : ''}</td><td class="${cls(r.net || 0)}">${r.net != null ? money(r.net) : ''}</td><td>${r.pf ?? ''}</td>` +
        `<td style="text-align:left;white-space:normal" class="k">${Object.entries(s.changed || {}).map(([k, v]) => `${esc(k.replace(/^Inp/, ''))}=${esc(v)}`).join(' ') || 'none (v1.27)'}${s.lab_describe ? `<br><span style="color:#ffb74d">⚗️ Exit Lab exit: ${esc(s.lab_describe)}</span>` : ''}</td>` +
        `<td><button data-load="${i}">Load</button> <button data-del="${i}">Delete</button></td></tr>`; }))
    : '<p class="note">Nothing saved yet - press "💾 Save settings".</p>';
}
$('#btnSave').onclick = async () => {
  const r = await api('/api/save', { inputs: CUR, ds: SRC.ds, mode: SRC.mode, result: TT ? TT.year : null });
  await loadSaved(); toast(`Saved as <b>${esc(r.name)}</b> (bottom of the page).`);
};
document.addEventListener('click', async (e) => {
  const d = e.target.dataset || {};
  if (d.load != null) {
    const s = SAVEDS[+d.load]; CUR = { ...DFL, ...s.inputs };
    if (s.lab && Object.keys(s.lab).length) { if (typeof labOpen === 'function') await labOpen(); CUR = { ...CUR, ...labToX(s.lab) }; }   // an older save's lab exit: EA v1.30 settings now
    ACTIVE_LAB = null; markForm(); scheduleSim(0);
    if (s.lab && Object.keys(s.lab).length && typeof labOpen === 'function') { await labOpen(); LABS.form = { ...LABS.spec.default, ...s.lab }; }   // its Exit Lab exit back on the bench
    toast(`Loaded <b>${esc(s.name)}</b>.` + (s.lab_describe ? ` Its Exit Lab exit is back on the bench: ${esc(s.lab_describe)}.` : ''));
  }
  if (e.target.id === 'labBannerOff') { ACTIVE_LAB = null; labBanner(); scheduleSim(0); toast('The main tester runs the EA’s own exit again.'); }
  if (d.del != null) { const s = SAVEDS[+d.del]; if (confirm(`Delete the saved settings "${s.name}"?`)) { await api('/api/saved_delete', { name: s.name }); loadSaved(); } }
});

// ---------- buttons ----------
$('#btnCheck').onclick = async () => {
  const r = await api('/api/run', { sets: CUR, delay: 'none', label: Object.keys(diffDfl(CUR)).length ? '' : 'v1.27 defaults (no delay)' });
  if (r.error) return toast('⚠ ' + esc(r.error));
  toast('The settings on screen are running in the MT5 Strategy Tester (real ticks, no delay). The MT5 section updates when it is done, in about a minute.');
};
$('#btnExport').onclick = async () => {
  if (!MT || !MT.matches) return toast('First "Check in MT5": Export writes the settings together with their MT5 result.');
  const r = await api('/api/export', { id: MT.run.id });
  if (r.error) return toast('⚠ ' + esc(r.error));
  const terms = r.written.filter((w) => /MQL5/.test(w)).length;
  toast(`<b>Exported.</b> <code>${esc(r.json)}</code> (settings + MT5 result) and the preset <code>${esc(r.preset)}</code> in ${terms} MT5 terminal${terms === 1 ? '' : 's'} (EA inputs → Load).` +
    (r.run ? (r.existing ? ' A random-delay result already exists.' : ' A random-delay MT5 run started.') : ''), 14000);
};
$('#runSel').onchange = (e) => pickMt5(e.target.value);
$('#btnDel').onclick = async () => {
  if (!MT || !confirm(`Delete the MT5 run "${MT.run.label}"?`)) return;
  await api('/api/delete', { id: MT.run.id }); MT = null; await loadRuns(); await pickMt5();
};
[['trades', 'tTrades'], ['ghosts', 'tGhosts'], ['setups', 'tSetups'], ['skips', 'tSkips'], ['mt5', 'tMt5']].forEach(([k, id]) => ($('#' + id).onchange = (e) => {
  show[k] = e.target.checked;
  if (k === 'setups' && show.setups) scheduleSim(0); else redraw();          // setups are fetched only when shown
}));
$('#tz').onchange = (e) => { TZ = +e.target.value; const r = chart.timeScale().getVisibleLogicalRange(); drawBars(); drawEmas(); renderAll(); if (r) chart.timeScale().setVisibleLogicalRange(r); };
$('#jump').onkeydown = (e) => {
  if (e.key !== 'Enter' || !BARS) return;
  const d = Date.parse(e.target.value.trim().replace(/\./g, '-') + 'T00:00:00Z');
  if (isNaN(d)) return toast('Type a date like 2026-03-31');
  const i = barIdx(d / 1000 - TZ);
  chart.timeScale().setVisibleLogicalRange({ from: i - 20, to: i + 120 });
};
document.querySelectorAll('nav[data-sec]').forEach((nav) => (nav.onclick = async (e) => {
  const t = e.target.dataset.t, sec = nav.dataset.sec;
  if (!t) return;
  TAB[sec] = t;
  if (sec === 'tt' && t === 'opt') OPTS = await api('/api/opt');
  renderPanel(sec);
  if (sec === 'tt' && t === 'lab') labOpen();
  if (sec === 'tt' && t === 'ml') mlOpen();
  if (sec === 'tt' && t === 'mission') misOpen();
}));
document.addEventListener('click', async (e) => {
  const tr = e.target.closest('tr');
  if (tr && tr.dataset.num) {
    const D = tr.dataset.kind === 'mt' ? MT : TT, t = D.TR.find((x) => x.num === +tr.dataset.num);
    if (t) { if (D === TT) focusTrade(t); else chart.timeScale().setVisibleLogicalRange({ from: t.biIn - 40, to: t.biOut + 40 }); }
  }
  if (tr && tr.dataset.month) {
    const [y, m] = tr.dataset.month.split('-').map(Number);
    chart.timeScale().setVisibleLogicalRange({ from: barIdx(Date.UTC(y, m - 1, 1) / 1000 - TZ), to: barIdx(Date.UTC(y, m, 1) / 1000 - TZ) });
  }
  if (e.target.id === 'oGo') {
    await api('/api/optimize', { start: CUR, objective: $('#oObj').value, boxes: $('#oBox').checked, keep: $('#oKeep').checked, ds: SRC.ds === 'tv' ? 'year' : SRC.ds });
    OPTS = await api('/api/opt'); renderPanel('tt');
  }
  const bs = e.target.dataset && e.target.dataset.bands;
  if (bs === 'OFF') { CUR.InpBandsB = '1'.repeat(21); CUR.InpBandsS = '1'.repeat(21); markForm(); scheduleSim(0); }
  else if (bs && bs[1] === 'L') {                             // untick every box whose trades lost money; boxes without trades keep their tick
    const key = 'InpBands' + bs[0], off = bs[0] === 'B' ? 0 : 21, cur = (CUR[key] || '').padEnd(21, '1').split('');
    for (let b = 0; b <= 20; b++) { const n = TT.TR.filter((t) => Math.round(t.bucket) === b + off).reduce((a, t) => a + t.pnl, 0); if (n < 0) cur[b] = '0'; }
    setBands(key, cur.join(''));
  } else if (bs) setBands('InpBands' + bs[0], (bs[1] === '1' ? '1' : '0').repeat(21));
  if (e.target.id === 'oStop') { await api('/api/opt_stop', {}); OPTS = await api('/api/opt'); renderPanel('tt'); }
  if (e.target.id === 'oApply' && OPTS && OPTS.best) { CUR = { ...OPTS.best.inputs }; markForm(); scheduleSim(0); toast('The optimizer\'s best is on the chart; its MT5 check is in the MT5 section.'); }
  if (e.target.dataset && e.target.dataset.rfinal && OPTS && OPTS.final) { CUR = { ...DFL, ...OPTS.final.inputs }; markForm(); scheduleSim(0); toast('Applied: only the 100% range boxes ticked.'); }
  if (e.target.dataset && e.target.dataset.rstep != null && OPTS && OPTS.steps) { CUR = { ...DFL, ...OPTS.steps[+e.target.dataset.rstep].inputs }; markForm(); scheduleSim(0); toast('Applied this step, with its 100% boxes ticked.'); }
  if (e.target.dataset && e.target.dataset.surv != null && OPTS && OPTS.rows) {
    const r = OPTS.rows[+e.target.dataset.surv]; CUR = { ...DFL, ...r.inputs }; markForm(); scheduleSim(0);
    const w = Object.entries(r.with || {}).map(([k, v]) => k.replace(/^Inp/, '') + '=' + v).join(', ');
    toast(`Applied: ${esc(r.setting.replace(/^Inp/, ''))} = ${esc(r.value)}${w ? ' (with ' + esc(w) + ')' : ''}.`);
  }
  if (e.target.dataset && e.target.dataset.step != null && OPTS) {
    const l = OPTS.log[+e.target.dataset.step - Math.max(0, (OPTS.log_total || OPTS.log.length) - OPTS.log.length)] || OPTS.log[+e.target.dataset.step];
    if (l && l.inputs) { CUR = { ...DFL, ...l.inputs }; markForm(); scheduleSim(0); toast(`Applied step: ${esc(l.setting.replace(/^Inp/, ''))} ${esc(l.from)} → ${esc(l.to)} (with the steps before it in "${esc(l.run)}").`); }
  }
  if (e.target.dataset && e.target.dataset.board != null && OPTS) { CUR = { ...OPTS.board[+e.target.dataset.board].inputs }; markForm(); scheduleSim(0); }
});

(async function init() {
  makeChart();
  renderAll();
  setStatus('loading the year…', 'busy');
  SRC.ds = 'm15'; SRC.mode = 'ea';                    // start where Zee tunes: TradingView's candles, TradingView's way (= its panel)
  $('#srcDs').value = SRC.ds; $('#srcMode').value = SRC.mode;
  const [bars, inputs] = await Promise.all([getBars(SRC.ds), api('/api/inputs')]);
  BARS = bars; INPUTS = inputs;
  for (const i of INPUTS.inputs) DFL[i.name] = i.default;
  await loadRuns();
  const h = new URLSearchParams(location.hash.slice(1));
  CUR = { ...DFL };
  drawBars(); buildForm();
  try {                                                        // TradingView open? start from its settings, like the chart
    const tv = await Promise.race([api('/api/tv'), new Promise((_, rej) => setTimeout(() => rej(new Error('slow')), 15000))]);
    if (tv && tv.sets) { CUR = { ...DFL, ...tv.sets }; tvKey = JSON.stringify(tv.sets); $('#tvDot').className = 'dot ok'; $('#tvDot').title = `TradingView ${tv.symbol} · read at ${tv.at}`; markForm(); }
  } catch (e) { /* TradingView not open: v1.27's defaults */ }
  await runSim();
  if (h.get('tab')) { TAB.tt = h.get('tab'); renderPanel('tt'); }
  if (h.get('mt')) { TAB.mt = h.get('mt'); renderPanel('mt'); }
  if (h.get('trade')) { const t = TT.TR.find((x) => x.num === +h.get('trade')); if (t) focusTrade(t); }
  if (h.get('ask') === '1') document.body.classList.add('ask-open');
  setStatus('');
  loadSaved();
  poll();
})();
