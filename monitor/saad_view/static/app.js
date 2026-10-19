// Turtle TV - the year of Blueberry 15-min candles with the MT5 Strategy Tester's own trades (monitor/saad_view/server.py).
// Everything drawn here comes from the EA's export; this file only displays it.
'use strict';
const LW = window.LightweightCharts;
const $ = (s) => document.querySelector(s);
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const C = { up: '#26a69a', down: '#ef5350', win: '#00e676', loss: '#ff5252', fast: '#ff9800', slow: '#2962ff', adx: '#b39ddb', muted: '#787b86' };
let TZ = 18000;                         // display shift: Pakistan time = UTC+5
let RUN = null, INPUTS = null, RUNS = [], lastSeen = undefined, firstLoad = true;
let chart, candles, emaF, emaS, adxS, adxLine = null, TVL = null, focusLines = [], eqChart = null;
let TR = [], GH = [], EVB = new Map(), SEL = null, TAB = 'overview';
const show = { trades: true, ghosts: true, setups: false, skips: false };

// ---------- helpers ----------
const money = (v, d = 0) => (v >= 0 ? '+$' : '−$') + Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const cls = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
const pct = (a, b) => (b ? ((100 * a) / b).toFixed(1) + '%' : '–');
const f2 = (v) => (v == null ? '–' : (+v).toFixed(2));
const f1 = (v) => (v == null ? '–' : (+v).toFixed(1));
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const same = (a, b) => { const x = parseFloat(a), y = parseFloat(b); if (!isNaN(x) && !isNaN(y) && /^[-\d.]+$/.test(String(a).trim()) && /^[-\d.]+$/.test(String(b).trim())) return Math.abs(x - y) < 1e-9; return String(a).trim().toLowerCase() === String(b).trim().toLowerCase(); };
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
  return fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {})
    .then((r) => r.json());
}
function toast(html, ms = 8000) { const t = $('#toast'); t.innerHTML = html; t.style.display = 'block'; clearTimeout(toast.h); toast.h = setTimeout(() => (t.style.display = 'none'), ms); }
function setStatus(txt, c = '') { const s = $('#status'); s.textContent = txt; s.className = c; }
function box(k) { k = Math.round(k); if (!(k >= 0)) return '–'; const b = k % 21; return b === 20 ? '>100%' : `${b * 5}–${b * 5 + 5}%`; }
function barIdx(t) { const a = RUN.bars.t; let lo = 0, hi = a.length - 1, r = 0; while (lo <= hi) { const m = (lo + hi) >> 1; if (a[m] <= t) { r = m; lo = m + 1; } else hi = m - 1; } return r; }

// ---------- the chart ----------
const BASE = {
  autoSize: true,
  layout: { background: { type: 'solid', color: '#131722' }, textColor: '#d1d4dc', fontSize: 12, panes: { separatorColor: '#2a2e39', separatorHoverColor: '#363a45' } },
  grid: { vertLines: { color: '#1e222d' }, horzLines: { color: '#1e222d' } },
  rightPriceScale: { borderColor: '#2a2e39' },
  localization: { timeFormatter: fullFmt },
};
function makeChart() {
  chart = LW.createChart($('#chart'), {
    ...BASE,
    crosshair: { mode: 0 },
    timeScale: { borderColor: '#2a2e39', timeVisible: true, secondsVisible: false, rightOffset: 8, barSpacing: 7, tickMarkFormatter: tickFmt },
  });
  candles = chart.addSeries(LW.CandlestickSeries, { upColor: C.up, downColor: C.down, borderVisible: false, wickUpColor: C.up, wickDownColor: C.down, priceLineVisible: false });
  const quiet = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false };
  emaF = chart.addSeries(LW.LineSeries, { ...quiet, color: C.fast, lineWidth: 2 });
  emaS = chart.addSeries(LW.LineSeries, { ...quiet, color: C.slow, lineWidth: 2 });
  adxS = chart.addSeries(LW.LineSeries, { ...quiet, color: C.adx, lineWidth: 1, lastValueVisible: true }, 1);
  TVL = new TvLabels();
  candles.attachPrimitive(TVL);
  chart.subscribeCrosshairMove((p) => { if (RUN) legend(p && p.time != null ? barIdx(p.time - TZ) : RUN.bars.t.length - 1); });
  chart.subscribeClick((p) => {                             // click a trade's entry or exit candle -> that trade
    if (!RUN || !p || p.logical == null) return;
    const i = Math.round(p.logical), t = TR.find((x) => x.biIn === i || x.biOut === i);
    if (t) focusTrade(t);
  });
  requestAnimationFrame(() => { const ps = chart.panes(); if (ps.length > 1) ps[1].setHeight(90); });
}

function derive() {
  TR = []; GH = []; EVB = new Map();
  const ent = {}; let g = null; const lots = parseFloat(RUN.inputs.InpLots || '1');
  for (const e of RUN.events) {
    e.bi = barIdx(e.t);
    if (!EVB.has(e.bi)) EVB.set(e.bi, []);
    EVB.get(e.bi).push(e);
    if (e.type === 'entry') ent[e.num] = e;
    else if (e.type === 'exit' && ent[e.num]) {
      const n = ent[e.num];
      TR.push({ num: e.num, side: n.side, tIn: n.t, tOut: e.t, biIn: n.bi, biOut: e.bi, en: n.price, sl: n.sl, ex: e.price, pnl: e.v1, swap: e.v2, why: e.text, info: n.text, bucket: n.v2 });
    } else if (e.type === 'ghost') g = { side: e.side, tIn: e.t, biIn: e.bi, en: e.price, sl: e.sl, bucket: e.v2, info: e.text };
    else if (e.type === 'ghost_end' && g) { Object.assign(g, { tOut: e.t, biOut: e.bi, ex: e.price, why: e.text, pnl: (e.price - g.en) * g.side * lots * 100 }); GH.push(g); g = null; }
  }
  if (g) GH.push(g);
  TR.sort((a, b) => a.tIn - b.tIn);
}

function render() {
  const B = RUN.bars, n = B.t.length, T = (i) => B.t[i] + TZ;
  candles.setData(B.t.map((t, i) => ({ time: t + TZ, open: B.o[i], high: B.h[i], low: B.l[i], close: B.c[i] })));
  const line = (arr) => B.t.map((t, i) => (arr[i] == null || arr[i] === 0 ? { time: t + TZ } : { time: t + TZ, value: arr[i] }));
  emaF.setData(line(B.ef)); emaS.setData(line(B.es)); adxS.setData(line(B.adx));
  if (adxLine) adxS.removePriceLine(adxLine);
  adxLine = adxS.createPriceLine({ price: parseFloat(RUN.inputs.InpAdxMin) || 0, color: C.muted, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'ADX min' });
  markers();
  focusLines.forEach((l) => candles.removePriceLine(l)); focusLines = [];
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
  if (!RUN) return;
  const ts = chart.timeScale(), vr = ts.getVisibleLogicalRange();
  if (!vr) return;
  const B = RUN.bars, X = (i) => ts.logicalToCoordinate(i), Y = (p) => candles.priceToCoordinate(p);
  const sp = Math.abs((X(1) ?? 0) - (X(0) ?? 0)), full = sp >= 4.5, lo = Math.floor(vr.from) - 3, hi = Math.ceil(vr.to) + 3;
  const inView = (i) => i >= lo && i <= hi;
  const bb = parseInt(RUN.inputs.InpBreakBars || '1', 10);
  if (show.setups && sp >= 2.5) for (const e of RUN.events) {
    if (e.type !== 'setup' || !inView(e.bi)) continue;
    const x = X(e.bi), yh = Y(e.price), yl = Y(e.sl), yb = Y(e.v1);
    if (x == null || yh == null || yl == null) continue;
    ctx.fillStyle = 'rgba(255,235,59,0.07)'; ctx.fillRect(x - sp, yh, 2 * sp, yl - yh);
    ctx.strokeStyle = 'rgba(255,235,59,0.6)'; ctx.lineWidth = 1; ctx.strokeRect(x - sp, yh, 2 * sp, yl - yh);
    seg(ctx, x, yb, X(e.bi + bb + 1), yb, TVC.yel, 1, [2, 2]);
    if (full) tvTag(ctx, x, e.side > 0 ? yh : yl, [`${e.side > 0 ? 'long' : 'short'} setup · ${KIND(Math.round(e.v2), e.side)}`], TVC.tag, TVC.yel, e.side < 0, 10);
  }
  if (show.skips && full) for (const e of RUN.events) {
    if (e.type !== 'skip' || !inView(e.bi)) continue;
    const x = X(e.bi), y = e.side > 0 ? Y(B.h[e.bi]) : Y(B.l[e.bi]);
    if (x != null && y != null) tvTag(ctx, x, y, ['✖ skip'], 'rgba(120,123,134,0.6)', '#fff', e.side < 0, 9);
  }
  if (show.ghosts) for (const g of GH) {
    if (g.biOut != null ? g.biOut < lo || g.biIn > hi : !inView(g.biIn)) continue;
    const x1 = X(g.biIn), y1 = Y(g.en);
    if (g.biOut != null) seg(ctx, x1, y1, X(g.biOut), Y(g.ex), TVC.grey, 1, [2, 3]);
    const ya = g.side > 0 ? Y(B.l[g.biIn]) : Y(B.h[g.biIn]);
    if (x1 == null || ya == null) continue;
    if (full) tvTag(ctx, x1, ya, [`stand aside (${g.side > 0 ? 'BUY' : 'SELL'})`], 'rgba(54,58,69,0.8)', '#9598a1', g.side > 0, 10);
    else tri(ctx, x1, ya, g.side > 0, TVC.grey, 3);
  }
  if (!show.trades) return;
  for (const t of TR) {
    if (t.biOut < lo || t.biIn > hi) continue;
    const x1 = X(t.biIn), x2 = X(t.biOut), rc = t.pnl > 0 ? TVC.win : TVC.loss, sel = SEL === t.num;
    seg(ctx, x1, Y(t.sl), x2 === x1 ? x1 + sp : x2, Y(t.sl), TVC.loss, 2, [6, 4]);                      // the stop: red dashed
    seg(ctx, x1, Y(t.en), x2, Y(t.ex), rc, sel ? 3 : 2, [2, 3]);                                       // entry -> exit: dotted
    const ye = Y(t.ex);
    if (x2 != null && ye != null) {
      ctx.strokeStyle = rc; ctx.lineWidth = 2; ctx.beginPath();
      ctx.moveTo(x2 - 3, ye - 3); ctx.lineTo(x2 + 3, ye + 3); ctx.moveTo(x2 + 3, ye - 3); ctx.lineTo(x2 - 3, ye + 3); ctx.stroke();
    }
  }
  for (const t of TR) {                                       // labels on top of every line
    if (t.biOut < lo || t.biIn > hi) continue;
    const x1 = X(t.biIn), x2 = X(t.biOut), rc = t.pnl > 0 ? TVC.win : TVC.loss;
    const yIn = t.side > 0 ? Y(B.l[t.biIn]) : Y(B.h[t.biIn]), yOut = t.side > 0 ? Y(B.h[t.biOut]) : Y(B.l[t.biOut]);
    if (x1 != null && yIn != null) {
      if (full) tvTag(ctx, x1, yIn, [`${t.side > 0 ? '▲ BUY' : '▼ SELL'} #${t.num}`, f2(t.en)], t.side > 0 ? TVC.buy : TVC.sell, '#fff', t.side > 0, 12);
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
function markers() { if (TVL) TVL.update(); }

function evText(e) {
  const S = e.side > 0 ? `<span style="color:${C.up}">BUY</span>` : `<span style="color:${C.down}">SELL</span>`;
  switch (e.type) {
    case 'setup': return `◆ SETUP ${S}: ${esc(e.text)} · break at ${f2(e.v1)}`;
    case 'skip': return `<span class="k">✕ ${e.side > 0 ? 'BUY' : 'SELL'} skipped: ${esc(e.text)}</span>`;
    case 'entry': return `▶ ${S} #${e.num} at ${f2(e.price)} · stop ${f2(e.sl)} · range box ${box(e.v2)} · ${esc(e.text)}`;
    case 'exit': return `■ EXIT #${e.num} at ${f2(e.price)} · ${esc(e.text)} · <b class="${cls(e.v1)}">${money(e.v1, 2)}</b>`;
    case 'ghost': return `<span class="k">◇ stand aside (range box ${box(e.v2)} unticked): the ${e.side > 0 ? 'BUY' : 'SELL'} would have entered at ${f2(e.price)}</span>`;
    case 'ghost_end': return `<span class="k">◇ stand-aside over: ${esc(e.text)} at ${f2(e.price)}</span>`;
  }
  return '';
}
function legend(i) {
  const B = RUN.bars, I = RUN.inputs, col = B.c[i] >= B.o[i] ? C.up : C.down, v = (x) => `<b style="color:${col}">${f2(x)}</b>`;
  let h = `<div><span class="k">${fullFmt(B.t[i] + TZ)}</span> &nbsp;O ${v(B.o[i])} H ${v(B.h[i])} L ${v(B.l[i])} C ${v(B.c[i])}</div>`;
  h += `<div><span style="color:${C.fast}">EMA ${I.InpEmaFast} ${f2(B.ef[i])}</span> &nbsp;<span style="color:#5b8def">EMA ${I.InpEmaSlow} ${f2(B.es[i])}</span> &nbsp;<span style="color:${C.adx}">ADX ${f1(B.adx[i])}</span> &nbsp;<span class="k">ATR ${f2(B.atr[i])}</span></div>`;
  for (const e of EVB.get(i) || []) h += `<div class="ev">${evText(e)}</div>`;
  $('#legend').innerHTML = h;
}

function focusTrade(t) {
  SEL = t.num;
  chart.timeScale().setVisibleLogicalRange({ from: t.biIn - 40, to: t.biOut + 40 });
  focusLines.forEach((l) => candles.removePriceLine(l));
  focusLines = [
    candles.createPriceLine({ price: t.en, color: '#2962ff', lineWidth: 1, lineStyle: 0, axisLabelVisible: true, title: `#${t.num} entry` }),
    candles.createPriceLine({ price: t.sl, color: C.down, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'stop' }),
    candles.createPriceLine({ price: t.ex, color: t.pnl > 0 ? C.win : C.loss, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'exit ' + money(t.pnl) }),
  ];
  legend(t.biIn);
  markers();
  if (TAB === 'trades') renderPanel();
}

// ---------- the results under the chart ----------
function stats(list) {
  const n = list.length, w = list.filter((t) => t.pnl > 0).length;
  const gw = list.filter((t) => t.pnl > 0).reduce((s, t) => s + t.pnl, 0), gl = list.filter((t) => t.pnl <= 0).reduce((s, t) => s + t.pnl, 0);
  return { n, w, net: gw + gl, pf: gl < 0 ? (gw / -gl).toFixed(2) : n ? '∞' : '–', aw: w ? gw / w : 0, al: n - w ? gl / (n - w) : 0 };
}
function groupBy(list, key) { const m = new Map(); for (const t of list) { const k = key(t); if (!m.has(k)) m.set(k, []); m.get(k).push(t); } return m; }
const ym = (t) => { const d = new Date((t + TZ) * 1000); return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`; };

function pOverview() {
  const R = RUN.report || {}, s = stats(TR), I = RUN.inputs;
  const best = TR.reduce((a, t) => (t.pnl > (a?.pnl ?? -1e18) ? t : a), null), worst = TR.reduce((a, t) => (t.pnl < (a?.pnl ?? 1e18) ? t : a), null);
  const card = (l, v, c = '') => `<div class="card"><div class="l">${l}</div><div class="v ${c}">${v}</div></div>`;
  let h = '<div class="row"><div><div class="cards">';
  h += card('Net profit (MT5 report)', money(R.net ?? s.net), cls(R.net ?? s.net)) + card('Profit factor', R.pf ?? s.pf) + card('Win rate', pct(s.w, s.n)) + card('Trades', `${s.n} <small class="k">(${s.w} won)</small>`);
  h += card('Max drawdown', ddTxt(R.dd)) + card('Average win', money(s.aw), 'pos') + card('Average loss', money(s.al), 'neg') + card('Stood aside', GH.length);
  h += '</div>';
  h += `<p class="note">${esc(RUN.from)} – ${esc(RUN.to)} · ${esc(RUN.symbol)} (Blueberry real ticks) · ${RUN.delay === 'none' ? 'no delay' : 'random delay'} · $${(RUN.deposit || 0).toLocaleString()} deposit · ${esc(I.InpLots)} lots · history quality ${esc(R.quality ?? '?')}<br>`;
  h += `Best trade ${best ? `#${best.num} ${money(best.pnl)}` : '–'} · worst ${worst ? `#${worst.num} ${money(worst.pnl)}` : '–'} · EA ${esc(RUN.ea)} (v${esc(RUN.version)}) · run ${esc(RUN.id)}</p>`;
  const ch = Object.entries(RUN.changed || {});
  h += `<h4>Settings different from the EA's defaults</h4><div class="chips">${ch.length ? ch.map(([k, v]) => `<span>${esc(k.replace(/^Inp/, ''))} = ${esc(v)}</span>`).join('') : '<span>none - the EA exactly as it is</span>'}</div>`;
  if ((RUN.notes || []).length) h += `<h4>On the chart but not in the EA</h4>` + RUN.notes.map((n) => `<div class="warn">⚠ ${esc(n)}</div>`).join('');
  h += '</div><div><h4>Equity (closed trades)</h4><div id="equity"></div></div></div>';
  return h;
}
function ddTxt(dd) {
  const m = String(dd ?? '').match(/^([\d\s.,]+)\s*\(([\d.]+)%\)/);
  return m ? `$${Math.round(parseFloat(m[1].replace(/[\s,]/g, ''))).toLocaleString('en-US')} <small class="k">(${m[2]}%)</small>` : esc(dd ?? '–');
}
function drawEquity() {
  if (eqChart) { eqChart.remove(); eqChart = null; }
  const el = $('#equity');
  if (!el) return;
  eqChart = LW.createChart(el, { ...BASE, localization: { timeFormatter: fullFmt, priceFormatter: (v) => '$' + Math.round(v).toLocaleString('en-US') }, timeScale: { borderColor: '#2a2e39', tickMarkFormatter: tickFmt }, handleScroll: false, handleScale: false, crosshair: { mode: 0 } });
  const s = eqChart.addSeries(LW.BaselineSeries, { baseValue: { type: 'price', price: 0 }, lineWidth: 2, priceLineVisible: false });
  const pts = []; let cum = 0;
  for (const t of [...TR].sort((a, b) => a.tOut - b.tOut)) {
    cum += t.pnl; const time = t.tOut + TZ;
    if (pts.length && pts[pts.length - 1].time >= time) pts[pts.length - 1].value = cum; else pts.push({ time, value: cum });
  }
  s.setData(pts); eqChart.timeScale().fitContent();
}
function table(head, rows, foot) {
  return `<table><tr>${head.map((x) => `<th>${x}</th>`).join('')}</tr>${rows.join('')}${foot || ''}</table>`;
}
function pMonths() {
  const g = groupBy(TR, (t) => ym(t.tOut)), ga = groupBy(GH, (t) => ym(t.tIn));
  const keys = [...g.keys()].sort();
  const rows = keys.map((k) => {
    const s = stats(g.get(k)), [y, m] = k.split('-');
    return `<tr class="click" data-month="${k}"><td>${MON[+m - 1]} ${y}</td><td>${s.n}</td><td>${s.w}</td><td>${pct(s.w, s.n)}</td><td class="${cls(s.net)}">${money(s.net)}</td><td>${s.pf}</td><td>${(ga.get(k) || []).length}</td></tr>`;
  });
  const s = stats(TR);
  return `<p class="note">By the month a trade closed (${TZ ? 'Pakistan time' : 'UTC'}). Click a month to see it on the chart.</p>` +
    table(['Month', 'Trades', 'Wins', 'Win rate', 'Net', 'PF', 'Stood aside'], rows,
      `<tr class="tot"><td>Total</td><td>${s.n}</td><td>${s.w}</td><td>${pct(s.w, s.n)}</td><td class="${cls(s.net)}">${money(s.net)}</td><td>${s.pf}</td><td>${GH.length}</td></tr>`);
}
function pWeekdays() {
  const g = groupBy(TR, (t) => new Date((t.tIn + TZ) * 1000).getUTCDay());
  const rows = [1, 2, 3, 4, 5, 6, 0].filter((d) => g.has(d)).map((d) => {
    const s = stats(g.get(d));
    return `<tr><td>${DOW[d]}</td><td>${s.n}</td><td>${s.w}</td><td>${pct(s.w, s.n)}</td><td class="${cls(s.net)}">${money(s.net)}</td><td>${s.pf}</td><td>${money(s.net / s.n)}</td></tr>`;
  });
  return `<p class="note">By the weekday a trade opened (${TZ ? 'Pakistan time' : 'UTC'}).</p>` + table(['Day', 'Trades', 'Wins', 'Win rate', 'Net', 'PF', 'Per trade'], rows);
}
function pRange() {
  const one = (side, bands, off) => {
    const rows = [];
    for (let b = 0; b <= 20; b++) {
      const k = b + off, tr = TR.filter((t) => Math.round(t.bucket) === k), gh = GH.filter((t) => Math.round(t.bucket) === k), s = stats(tr);
      const on = (bands || '')[b] !== '0', gn = gh.reduce((a, t) => a + (t.pnl || 0), 0);
      rows.push(`<tr class="${on ? '' : 'dim'}"><td>${box(k)}</td><td>${on ? '✓' : '–'}</td><td>${s.n || ''}</td><td>${s.n ? pct(s.w, s.n) : ''}</td><td class="${cls(s.net)}">${s.n ? money(s.net) : ''}</td><td>${gh.length || ''}</td><td class="${cls(gn)}">${gh.length ? money(gn) : ''}</td></tr>`);
    }
    return `<div><h4>${side} - where the entry sat in the last ${side === 'BUY' ? RUN.inputs.InpRangeLook : RUN.inputs.InpRangeLookS} candles' range</h4>` +
      table(['Box', 'Ticked', 'Trades', 'Win rate', 'Net', 'Stood aside', 'Would have made'], rows) + '</div>';
  };
  return `<p class="note">Unticked boxes are grey: there the EA stood aside. "Would have made" = the stand-aside trades' result (same stop and exit, no swap or spread cost).</p>` +
    `<div class="row">${one('BUY', RUN.inputs.InpBandsB, 0)}${one('SELL', RUN.inputs.InpBandsS, 21)}</div>`;
}
function pTrades() {
  const rows = TR.map((t) => `<tr class="click ${SEL === t.num ? 'sel' : ''}" data-num="${t.num}"><td>#${t.num}</td><td style="color:${t.side > 0 ? C.up : C.down}">${t.side > 0 ? 'BUY' : 'SELL'}</td>` +
    `<td>${dt(t.tIn)}</td><td>${f2(t.en)}</td><td>${f2(t.sl)}</td><td>${dt(t.tOut)}</td><td>${f2(t.ex)}</td><td style="text-align:left">${esc(t.why)}</td><td class="${cls(t.pnl)}">${money(t.pnl, 2)}</td></tr>`);
  return `<p class="note">Click a trade to see it on the chart. Net includes swap and commission, exactly as MT5 booked it.</p>` +
    table(['#', 'Side', 'Entry', 'Price', 'Stop', 'Exit', 'Price', 'Why it closed', 'Net'], rows);
}
function reason(s) {
  if (/^ADX/.test(s)) return 'ADX below the minimum (ranging market)';
  if (/stop too far/.test(s)) return 'stop too far (over the max risk)';
  if (/not broken/.test(s)) return 'the high / low was not broken in time';
  if (/unticked box/.test(s)) return 'entry in an unticked range box';
  if (/ATR/.test(s)) return 'ATR outside the volatility band';
  return s.replace(/\$?-?\d+(\.\d+)?%?/g, '#');
}
function pSkips() {
  const sk = RUN.events.filter((e) => e.type === 'skip'), setups = RUN.events.filter((e) => e.type === 'setup').length;
  const g = groupBy(sk, (e) => reason(e.text));
  const rows = [...g.entries()].sort((a, b) => b[1].length - a[1].length).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.length}</td><td>${pct(v.length, setups)}</td></tr>`);
  return `<p class="note">${setups.toLocaleString()} setups were found. <b>${TR.length}</b> became trades, <b>${GH.length}</b> stood aside (unticked range box), and these were skipped. A setup that appeared while a trade was already open is not counted as a setup.</p>` +
    table(['Why the setup was not traded', 'Setups', 'Share'], rows);
}
function renderPanel() {
  document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('on', b.dataset.t === TAB));
  if (!RUN) { $('#panel').innerHTML = '<p class="note">The first MT5 run is going - the year appears here when it is done (about a minute).</p>'; return; }
  $('#runInfo').textContent = `${RUN.label} · ${RUN.created}`;
  $('#panel').innerHTML = { overview: pOverview, months: pMonths, weekdays: pWeekdays, range: pRange, trades: pTrades, skips: pSkips }[TAB]();
  if (TAB === 'overview') drawEquity();
}

// ---------- runs, status, TradingView ----------
async function loadRuns(selectId) {
  RUNS = await api('/api/runs');
  $('#runSel').innerHTML = RUNS.length ? RUNS.map((r) => `<option value="${r.id}">${esc(r.label)} · ${money(r.net || 0)} · PF ${r.pf} · ${r.trades} trades · ${esc((r.created || '').slice(5))}</option>`).join('')
    : '<option>no MT5 runs yet</option>';
  const id = selectId || (RUN && RUN.id) || (RUNS[0] && RUNS[0].id);
  if (id) { $('#runSel').value = id; if (!RUN || RUN.id !== id) await loadRun(id); }
}
async function loadRun(id) {
  setStatus('loading the run…');
  const keep = firstLoad ? null : chart.timeScale().getVisibleLogicalRange();
  RUN = await api('/api/run?id=' + encodeURIComponent(id));
  derive(); render(); renderPanel();
  const n = RUN.bars.t.length;
  chart.timeScale().setVisibleLogicalRange(keep || { from: n - 1500, to: n + 5 });
  firstLoad = false;
  legend(n - 1);
  setStatus('');
}
async function poll() {
  try {
    const s = await api('/api/status'), f = s.follow || {};
    $('#tvDot').className = 'dot ' + (f.on ? (f.connected ? 'ok' : 'bad') : '');
    $('#tvDot').title = f.on ? (f.connected ? `TradingView ${f.symbol || ''} - read at ${f.at}` : 'TradingView not reachable: ' + (f.err || '')) : 'not following TradingView';
    $('#tFollow').checked = !!f.on;
    ['#btnRun', '#btnTake', '#btnExport'].forEach((b) => ($(b).disabled = !!s.busy));
    if (s.busy) setStatus(`MT5 running "${s.label}" · ${s.phase} · ${s.elapsed ?? 0} s`, 'busy');
    else if (s.error) setStatus('last run failed: ' + s.error, 'err');
    else if (f.on && f.waiting) setStatus('TradingView changed - waiting for it to settle…', 'busy');
    else if (f.on && f.err) setStatus('TradingView: ' + f.err, 'err');
    else setStatus(f.msg || '');
    if (!s.busy && s.last && s.last !== lastSeen) {
      lastSeen = s.last;
      if (!RUN || RUN.id !== s.last) { await loadRuns(s.last); toast(`New MT5 result: <b>${esc(RUN.label)}</b> · ${money(RUN.report.net || 0)} · PF ${RUN.report.pf}`); }
    }
  } catch (e) { setStatus('Turtle TV server not reachable', 'err'); }
  setTimeout(poll, 2000);
}

// ---------- settings ----------
function openSettings() {
  const groups = new Map();
  for (const i of INPUTS.inputs) { if (!groups.has(i.group)) groups.set(i.group, []); groups.get(i.group).push(i); }
  let h = '';
  for (const [g, list] of groups) {
    h += `<div class="igrp"><h5>${esc(g)}</h5>`;
    for (const i of list) {
      const v = RUN ? RUN.inputs[i.name] ?? i.default : i.default, chg = !same(v, i.default);
      const field = i.type === 'bool'
        ? `<select data-n="${i.name}"><option ${String(v) === 'true' ? 'selected' : ''}>true</option><option ${String(v) !== 'true' ? 'selected' : ''}>false</option></select>`
        : `<input data-n="${i.name}" value="${esc(v)}">`;
      h += `<div class="inp ${chg ? 'chg' : ''}" title="${esc(i.comment)}"><span class="n">${esc(i.name)}</span>${field}<span class="c">${esc(i.comment.slice(0, 170))} · default ${esc(i.default)}</span></div>`;
    }
    h += '</div>';
  }
  $('#eaName').textContent = `${INPUTS.ea} (v${INPUTS.version}) - the values of the run on screen; changed ones are orange`;
  $('#form').innerHTML = h;
  if (RUN) { $('#fFrom').value = RUN.from; $('#fTo').value = RUN.to; $('#fDelay').value = RUN.delay; }
  $('#modal').classList.add('open');
}
$('#form').addEventListener('input', (e) => {
  const el = e.target, i = INPUTS.inputs.find((x) => x.name === el.dataset.n);
  if (i) el.parentElement.classList.toggle('chg', !same(el.value, i.default));
});
$('#btnSettings').onclick = openSettings;
$('#btnCancel').onclick = () => $('#modal').classList.remove('open');
$('#btnReset').onclick = () => document.querySelectorAll('#form [data-n]').forEach((el) => {
  const i = INPUTS.inputs.find((x) => x.name === el.dataset.n); el.value = i.default; el.parentElement.classList.remove('chg');
});
$('#btnRun').onclick = async () => {
  const sets = {};
  document.querySelectorAll('#form [data-n]').forEach((el) => (sets[el.dataset.n] = el.value.trim()));
  const r = await api('/api/run', { sets, from: $('#fFrom').value.trim(), to: $('#fTo').value.trim(), delay: $('#fDelay').value, label: $('#fLabel').value });
  if (r.error) return toast('⚠ ' + esc(r.error));
  $('#modal').classList.remove('open');
  toast('MT5 run started - the chart and results update by themselves when it is done (about a minute).');
};

// ---------- header controls ----------
$('#runSel').onchange = (e) => loadRun(e.target.value);
$('#btnDel').onclick = async () => {
  if (!RUN || RUNS.length < 2 || !confirm(`Delete the run "${RUN.label}"?`)) return;
  await api('/api/delete', { id: RUN.id }); RUN = null; await loadRuns();
};
$('#tFollow').onchange = async (e) => {
  await api('/api/follow', { on: e.target.checked, delay: 'none' });   // tuning: no delay = the same number for the same settings
  toast(e.target.checked ? 'Following TradingView: change a setting on the Saad indicator and Turtle TV runs it in MT5 with no delay, so only your change moves the number (it waits 5 s for you to finish). Export to MT5 adds the realistic random-delay result.' : 'Stopped following TradingView.');
};
$('#btnTake').onclick = async () => {
  setStatus('reading TradingView…', 'busy');
  const r = await api('/api/tv_take', { delay: 'none' });
  if (r.error) return toast('⚠ ' + esc(r.error));
  const notes = (r.notes || []).map((n) => `<div class="warn">⚠ ${esc(n)}</div>`).join('');
  if (r.existing) { await loadRuns(r.id); toast('TradingView\'s settings were already run in MT5 - showing that run.' + notes); }
  else toast('TradingView\'s settings are running in MT5…' + notes);
};
$('#btnExport').onclick = async () => {
  if (!RUN) return;
  const r = await api('/api/export', { id: RUN.id });
  if (r.error) return toast('⚠ ' + esc(r.error));
  const terms = r.written.filter((w) => /MQL5/.test(w)).length;
  toast(`<b>Exported.</b> <code>${esc(r.json)}</code> (settings + this MT5 result) and the preset <code>${esc(r.preset)}</code>, in ${terms} MT5 terminal${terms === 1 ? '' : 's'}: EA inputs → Load.` +
    (r.run ? (r.run === RUN.id ? '' : r.existing ? ' The random-delay result already exists - see the runs list.' : ' A random-delay MT5 run started; its result appears below the chart.') : ''), 14000);
};
['trades', 'ghosts', 'setups', 'skips'].forEach((k) => ($('#t' + k[0].toUpperCase() + k.slice(1)).onchange = (e) => { show[k] = e.target.checked; markers(); }));
$('#tz').onchange = (e) => { TZ = +e.target.value; if (RUN) { const r = chart.timeScale().getVisibleLogicalRange(); render(); renderPanel(); if (r) chart.timeScale().setVisibleLogicalRange(r); } };
$('#jump').onkeydown = (e) => {
  if (e.key !== 'Enter' || !RUN) return;
  const d = Date.parse(e.target.value.trim().replace(/\./g, '-') + 'T00:00:00Z');
  if (isNaN(d)) return toast('Type a date like 2026-03-31');
  const i = barIdx(d / 1000 - TZ);
  chart.timeScale().setVisibleLogicalRange({ from: i - 20, to: i + 120 });
};
$('#tabs').onclick = (e) => { if (e.target.dataset.t) { TAB = e.target.dataset.t; history.replaceState(null, '', '#tab=' + TAB); renderPanel(); } };
$('#panel').onclick = (e) => {
  const tr = e.target.closest('tr');
  if (!tr || !RUN) return;
  if (tr.dataset.num) { const t = TR.find((x) => x.num === +tr.dataset.num); if (t) focusTrade(t); }
  if (tr.dataset.month) {
    const [y, m] = tr.dataset.month.split('-').map(Number);
    const a = Date.UTC(y, m - 1, 1) / 1000 - TZ, b = Date.UTC(y, m, 1) / 1000 - TZ;
    chart.timeScale().setVisibleLogicalRange({ from: barIdx(a), to: barIdx(b) });
  }
};

(async function init() {
  makeChart();
  renderPanel();
  INPUTS = await api('/api/inputs');
  await loadRuns();
  const h = new URLSearchParams(location.hash.slice(1));
  if (h.get('tab')) { TAB = h.get('tab'); renderPanel(); }
  if (h.get('trade') && RUN) { const t = TR.find((x) => x.num === +h.get('trade')); if (t) focusTrade(t); }
  poll();
})();
