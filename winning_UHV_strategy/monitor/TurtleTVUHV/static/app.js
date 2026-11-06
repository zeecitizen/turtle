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
let MTWAIT = null;                                           // a "Check in MT5" in flight: the MT5 section shows its progress, then the new run
let EXPORT_BUSY = false, EXPORT_PENDING = null, EXPORT_TIMER = null, EXPORT_PROGRESS = null;
let SEL = null, TAB = { tt: 'overview', mt: 'overview' }, firstView = true, simTimer = null, simSeq = 0, settingsTouched = false, tvKey = null, ASK = [];
const show = { trades: true, ghosts: true, setups: false, skips: false, mt5: false };
const SRC = { ds: 'm15', mode: 'ea' }, BARSET = {};                // the Turtle TV Tester's candles and rules
async function getBars(ds) { if (!BARSET[ds]) BARSET[ds] = await api('/api/bars?ds=' + ds); return BARSET[ds]; }
function mt5Period(ds = SRC.ds) { return ds === 'm5x' ? 'M5' : ds === 'year1' || ds === 'm1x' ? 'M1' : 'M15'; }

// ---------- helpers ----------
const money = (v, d = 0) => { const D = Math.abs(v) < 1000 ? Math.max(d, 2) : d;   // TurtleTVUHV: a 1-coin round is cents - show them
  return (v >= 0 ? '+$' : '−$') + Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: D, maximumFractionDigits: D }); };
const cls = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
const pct = (a, b) => (b ? ((100 * a) / b).toFixed(1) + '%' : '–');
const f2 = (v) => (v == null ? '–' : Math.abs(+v) < 10 ? (+v).toFixed(5) : (+v).toFixed(2));   // TurtleTVUHV: EUR/USD prices get 5 decimals, ADX etc. keep 2
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
function toast(html, ms = 9000) { const t = $('#toast'); t.classList.remove('tp-applied', 'tp-failed'); t.innerHTML = html; t.style.display = 'block'; clearTimeout(toast.h); toast.h = setTimeout(() => (t.style.display = 'none'), ms); }
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
  localization: { timeFormatter: fullFmt, priceFormatter: (v) => (Math.abs(v) >= 10 ? Math.round(v).toLocaleString('en-US') : Number(v).toFixed(5)) },   // TurtleTVUHV: EUR/USD prices 5 decimals; volume as whole ticks
};
function makeChart() {
  chart = LW.createChart($('#chart'), { ...BASE, crosshair: { mode: 0 },
    timeScale: { borderColor: '#2a2e39', timeVisible: true, secondsVisible: false, rightOffset: 8, barSpacing: 7, tickMarkFormatter: tickFmt } });
  candles = chart.addSeries(LW.CandlestickSeries, { upColor: C.up, downColor: C.down, borderVisible: false, wickUpColor: C.up, wickDownColor: C.down, priceLineVisible: false });
  const quiet = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false };
  emaF = chart.addSeries(LW.LineSeries, { ...quiet, color: C.fast, lineWidth: 2, visible: false });   // TurtleTVUHV: Saad's EMAs hidden (the camel humps are drawn instead)
  emaS = chart.addSeries(LW.LineSeries, { ...quiet, color: C.slow, lineWidth: 2, visible: false });
  adxS = chart.addSeries(LW.HistogramSeries, { priceLineVisible: false, lastValueVisible: true, priceFormat: { type: 'volume' } }, 1);   // TurtleTVUHV: the bottom pane = tick volume (what the UHV reads), not ADX
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
  adxS.setData(B.t.map((t, i) => ({ time: t + TZ, value: (B.v && B.v[i]) || 0, color: B.c[i] >= B.o[i] ? 'rgba(38,166,154,0.6)' : 'rgba(239,83,80,0.6)' })));
  drawCamel();
}
// TurtleTVUHV: Zee's camel humps (his Turtle Trader Desk indicator) - one rounded arch per hump, green = it ended higher than it started
// (uptrend: buys only), red = lower (downtrend: sells only). The same camel the tester trades on.
let CAMEL = null, camS = null;
async function drawCamel() {
  if (!CAMEL) { try { CAMEL = await api('/api/uhv_camel?ds=year1'); } catch (e) { return; } }
  if (!camS) camS = chart.addSeries(LW.LineSeries, { lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, lineType: 2 });
  camS.setData(CAMEL.pts.map(([t, v, c]) => ({ time: t + TZ, value: v, color: c })));
}
// TurtleTVUHV: Zee's UHV Diamond setups (ZeeUHV_Diamond v1.27 rules, PrimeXBT tick volume) - one arrow on the breakout candle
// (the setup fires at the close of that candle), green below for a buy, red above for a sell; a star = the EA v1.27 itself would take it,
// gold = royal (and the 15-minute market is clean)
let UHV = null, UHVM = null;
async function drawUhv() {
  if (!UHV) { try { UHV = await api('/api/uhv_setups?ds=year1'); } catch (e) { return; } }
  if (!UHV || !UHV.setups) return;
  const res = {}; ((UHVT && UHVT.trades) || []).forEach((r) => { res[r.t] = r; });
  const mk = UHV.setups.map((s) => { const r = res[s.t], won = r && r.pips > 0;      // the arrow's colour = the round's result (green won, red lost)
    const tag = s.royal ? '★ ROYAL ' : s.ea ? '★ EA ' : '';
    return { time: s.t - 60 + TZ, position: s.side > 0 ? 'belowBar' : 'aboveBar', shape: s.side > 0 ? 'arrowUp' : 'arrowDown', size: s.ea ? 3 : 2,
      color: !r ? '#9e9e9e' : won ? '#00e676' : '#ff1744',
      text: tag + (s.side > 0 ? 'BUY ' : 'SELL ') + (r ? (won ? '✓ +' : '✗ ') + r.pips.toFixed(1) : '') }; });
  if (UHVM) UHVM.setMarkers(mk); else UHVM = LW.createSeriesMarkers(candles, mk);
}
let UHVT = null, UHVR = null;
function uhvRes(r) { return r ? { _r: r } : {}; }
function uhvStats(rows) {
  const n = rows.length, w = rows.filter((r) => r.pips > 0), l = rows.filter((r) => r.pips <= 0), usd = rows.reduce((a, r) => a + r.usd, 0);
  const avg = (a, k) => a.length ? a.reduce((x, r) => x + r[k], 0) / a.length : 0;
  return { n, wins: w.length, wr: n ? 100 * w.length / n : 0, usd, per: n ? usd / n : 0, aw: avg(w, 'pips'), al: avg(l, 'pips'), secs: avg(rows, 'secs') };
}
function pUhvOverview() {
  if (!UHVT || !UHVT.trades) return '<p class="note">Loading the UHV rounds...</p>';
  const T = UHVT.trades, R = (UHVR && UHVR.trades) || [], rnd = uhvStats(R);
  const usd = (v) => (v >= 0 ? '+$' : '−$') + Math.abs(v).toFixed(2), c = (v) => v >= 0 ? 'var(--up, #26a69a)' : 'var(--down, #ef5350)';
  const g = uhvStats(T.filter((r) => r.game));
  const tile = (k, v, col) => `<div class="kpi"><div class="k">${k}</div><div class="v" style="${col ? 'color:' + col : ''}">${v}</div></div>`;
  const rows = [['Every UHV setup', T], ['One at a time (like the game)', T.filter((r) => r.game)], ['The v1.27 EA would take (★ EA)', T.filter((r) => r.ea)],
    ['Royal (★ ROYAL)', T.filter((r) => r.royal)], ['Buys', T.filter((r) => r.side > 0)], ['Sells', T.filter((r) => r.side < 0)], ['Random entries (the control)', R]];
  const tr = rows.map(([name, a]) => { const s = uhvStats(a); return `<tr><td>${name}</td><td>${s.n}</td><td>${s.wins}</td><td><b>${s.wr.toFixed(1)}%</b></td>
    <td style="color:${c(s.wr - rnd.wr)}">${a === R ? '—' : (s.wr - rnd.wr >= 0 ? '+' : '') + (s.wr - rnd.wr).toFixed(1)}</td><td style="color:${c(s.usd)}">${usd(s.usd)}</td>
    <td style="color:${c(s.per)}">${(s.per * 100 >= 0 ? '+' : '−') + Math.abs(s.per * 100).toFixed(1)}¢</td><td>${s.aw.toFixed(2)} / ${s.al.toFixed(2)}</td></tr>`; }).join('');
  const mon = {}; T.filter((r) => r.game).forEach((r) => { const k = new Date((r.t_in + TZ) * 1000).toISOString().slice(0, 7); (mon[k] = mon[k] || []).push(r); });
  const mrows = Object.keys(mon).sort().map((k) => { const s = uhvStats(mon[k]); return `<tr><td>${k}</td><td>${s.n}</td><td>${s.wr.toFixed(1)}%</td><td style="color:${c(s.usd)}">${usd(s.usd)}</td></tr>`; }).join('');
  return `<p class="note">Zee's UHV Diamond (ZeeUHV_Diamond v1.27 rules, OANDA off = PrimeXBT tick volume) · every setup played as one game round on
    <b>PrimeXBT's real ticks</b> (Mar 6 – Nov 4 2026): entry ${UHVT.latency_s}s after the breakout candle closes (buy at the ask, sell at the bid),
    target +${UHVT.tp_pips} / stop −${UHVT.sl_pips} pips from that fill, spread paid on the exit · 1 coin = ${UHVT.lot_eur.toLocaleString()} EUR (1 pip = $0.10) ·
    Python tick replay (a hypothesis until MT5 confirms it) · made ${esc(UHVT.made || '')}</p>
  <div class="kpis" style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:8px 0">
    ${tile('Rounds (one at a time)', g.n)}${tile('Win rate', g.wr.toFixed(1) + '%', c(g.wr - rnd.wr))}${tile('Random entries win', rnd.wr.toFixed(1) + '%')}${tile('Net at 1 coin', usd(g.usd), c(g.usd))}
    ${tile('Per round', (g.per >= 0 ? '+' : '−') + Math.abs(g.per * 100).toFixed(1) + '¢', c(g.per))}${tile('Avg win', '+' + g.aw.toFixed(2) + ' pips')}${tile('Avg loss', g.al.toFixed(2) + ' pips')}${tile('Avg time in a round', Math.round(g.secs) + ' s')}
  </div>
  <table class="tbl" style="width:100%"><tr><th>which rounds</th><th>rounds</th><th>wins</th><th>win rate</th><th>vs random</th><th>net (1 coin)</th><th>per round</th><th>avg win / loss (pips)</th></tr>${tr}</table>
  <h4 style="margin:12px 0 4px">By month (one at a time)</h4><table class="tbl"><tr><th>month</th><th>rounds</th><th>win rate</th><th>net</th></tr>${mrows}</table>`;
}
function drawEmas() {
  if (!TT || !TT.ef) return;
  emaF.setData(BARS.t.map((t, i) => ({ time: t + TZ, value: TT.ef[i] })));
  emaS.setData(BARS.t.map((t, i) => ({ time: t + TZ, value: TT.es[i] })));
  if (adxLine) { adxS.removePriceLine(adxLine); adxLine = null; }   // TurtleTVUHV: no ADX line on the volume pane
}

// events (Turtle TV Tester or MT5) -> trades, stand-asides, events by candle
function derive(kind, events, lots) {
  const D = { kind, events, TR: [], GH: [], EVB: new Map() };
  const ent = {}; let g = null;
  for (const e of events) {
    e.bi = e.t < BARS.t[0] ? -1 : barIdx(e.t);                  // before the chart's first candle (the 4-year M1 data draws 2026 only): counted, not drawn
    if (e.bi >= 0) { if (!D.EVB.has(e.bi)) D.EVB.set(e.bi, []); D.EVB.get(e.bi).push(e); }
    if (e.type === 'entry') ent[e.num] = e;
    else if (e.type === 'exit' && ent[e.num]) {
      const n = ent[e.num];
      D.TR.push({ num: e.num, side: n.side, tIn: n.t, tOut: e.t, biIn: n.bi, biOut: e.bi, en: n.price, sl: n.sl, ex: e.price, pnl: e.v1, swap: e.v2, why: e.text, info: n.text, bucket: n.v2 });
    } else if (e.type === 'ghost') g = { side: e.side, tIn: e.t, biIn: e.bi, en: e.price, sl: e.sl, bucket: e.v2, info: e.text };
    else if (e.type === 'ghost_end' && g) { Object.assign(g, { tOut: e.t, biOut: e.bi, ex: e.price, why: e.text, pnl: (e.price - g.en) * g.side * 100000 * parseFloat((D.kind === 'mt' ? {} : CUR).InpUhvLots || '1') }); D.GH.push(g); g = null; }   // TurtleTVUHV: EUR/USD lots
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
  const B = BARS, col = B.c[i] >= B.o[i] ? C.up : C.down, v = (x) => `<b style="color:${col}">${Number(x).toFixed(5)}</b>`;
  let h = `<div><span class="k">${fullFmt(B.t[i] + TZ)}</span> &nbsp;O ${v(B.o[i])} H ${v(B.h[i])} L ${v(B.l[i])} C ${v(B.c[i])}</div>`;
  if (TT) h += `<div><span style="color:${C.adx}">ADX ${f2(B.adx[i])}</span> &nbsp;<span class="k">ATR ${(+B.atr[i]).toFixed(5)}</span></div>`;   // TurtleTVUHV: Saad's EMAs removed (irrelevant to UHV)
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
  return { n, w, net: gw + gl, pf: gl < 0 ? (gw / -gl).toFixed(2) : n ? '∞' : '–', aw: w ? gw / w : 0, al: n - w ? gl / (n - w) : 0, worst: n ? Math.min(...list.map((t) => t.pnl)) : 0, dd };
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
function pOverviewStats(D) {
  const s = stats(D.TR), a = stats(half(D.TR, true)), b = stats(half(D.TR, false)), mt = D.kind === 'mt', R = mt ? D.run.report || {} : {};
  const Y26 = Date.UTC(2026, 0, 1) / 1000 - 3 * 3600, longA = D.TR.length && D.TR[0].tIn < Y26, y26 = stats(D.TR.filter((x) => x.tIn >= Y26));   // a multi-year tester: the first half is years, not Jan – Jun
  let h = '<div class="cards">';
  h += card(mt ? 'Net profit (MT5 report)' : 'Net profit', money(mt ? R.net ?? s.net : s.net), cls(s.net)) + card('Profit factor', mt ? R.pf ?? s.pf : s.pf) +
       card('Win rate', pct(s.w, s.n)) + card('Trades', `${s.n} <small class="k">(${s.w} won)</small>`);
  h += card('Avg win', s.n ? `<span class="pos">${money(s.aw)}</span>` : '–') + card('Avg loss', s.n ? `<span class="neg">${money(s.al)}</span>` : '–') + card('Worst loss', s.n ? `<span class="neg">${money(s.worst)}</span>` : '–');
  h += card('Max drawdown', mt ? ddTxt(R.dd) : '$' + Math.round(s.dd).toLocaleString('en-US') + ' <small class="k">(closed trades)</small>') +
       card(longA ? `${new Date(D.TR[0].tIn * 1000).toLocaleString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' })} – Jun 2026` : 'Jan – Jun', a.n ? `<span class="${cls(a.net)}">${money(a.net)}</span> <small class="k">${pct(a.w, a.n)}</small>` : '<small class="k">no candles</small>') +
       (longA ? card('2026 only (= MT5 period)', y26.n ? `<span class="${cls(y26.net)}">${money(y26.net)}</span> <small class="k">${pct(y26.w, y26.n)} · ${y26.n} trades</small>` : '<small class="k">no trades</small>') : '') +
       card('Jul – Oct', b.n ? `<span class="${cls(b.net)}">${money(b.net)}</span> <small class="k">${pct(b.w, b.n)}</small>` : '<small class="k">no trades</small>') + card('Stood aside', D.GH.length);
  return h + '</div>';
}
function pOverview(D) {
  const mt = D.kind === 'mt', R = mt ? D.run.report || {} : {};
  let h = '<div class="row"><div>' + pOverviewStats(D);
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
// Zee 2026-11-02 (Range boxes): "add these as checkboxes ... the filters that you found that can cut losers ... we can just check a box on any
// setting to cut its losers". Each box = one of B's (2026-10-30 23-08-23) filter groups with B's exact values; ticking it writes those inputs into the
// setting on the chart, unticking restores what was there. Beside each box: what it did to THIS setting's trades (losers / winners removed, net change)
// and what it did to C's 1,615 trades in research/risk_assessor_C.py. Honest caveat: on C none of them is loser-selective (they remove winners at
// nearly the same rate) - B's 99.75% is a volume filter. Turtle TV Tester = hypothesis; MT5 judges.
let LCF = [
  { key: 'gap', name: "EMA gap ≥ 22.5 pips", set: { InpEmaGapPips: '22.5' }, off: { InpEmaGapPips: '0' }, c: '18 of 46 losers (39%) · 509 of 1,569 winners (32%) · 1.2×' },
  { key: 'sess', name: 'Session to 19:00 + hour 11 off', set: { InpSessTo: '19', InpHours: '111111111110111111111111' }, off: { InpSessTo: '24', InpHours: '111111111111111111111111' }, c: '11 losers (24%) · 268 winners (17%) · 1.4×' },
  { key: 'bands', name: 'Price bands B/S + BandOff', set: { InpBandsB: '111111101111001111110', InpBandsS: '111110100000101001101', InpBandOff: '1' }, off: { InpBandsB: '111111111111111111111', InpBandsS: '111111111111111111111', InpBandOff: '0' }, c: '32 losers (70%) · 900 winners (57%) · 1.2×' },
  { key: 'shape', name: 'Stricter hammer shape, no stars', set: { InpHamRatio: '2.25', InpHamNose: '0.8', InpNoseMax: '0.05', InpStar: 'false' }, off: { InpHamRatio: '1.25', InpHamNose: '0.5', InpNoseMax: '0.15', InpStar: 'true' }, c: '12 losers (26%) · 338 winners (22%) · 1.2×' },
  { key: 'touch', name: 'Touch 3.5 pips + MinRangeAtr 0.8', set: { InpTouchPips: '3.5', InpMinRangeAtr: '0.8' }, off: { InpTouchPips: '6.5', InpMinRangeAtr: '0.75' }, c: '6 losers (13%) · 249 winners (16%) · 0.8×' },
  { key: 'day', name: 'Day caps $2000 target / 2% loss', set: { InpDayTargetUsd: '2000', InpDayLossPct: '2' }, off: { InpDayTargetUsd: '0', InpDayLossPct: '0' }, c: '2 losers (4%) · 36 winners (2%)' },
  { key: 'tvbox', name: 'TvBox kelt_S / vwap_B masks', set: { TvBox_kelt_S: '110111111111', TvBox_vwap_B: '11101111' }, off: { TvBox_kelt_S: '111111111111', TvBox_vwap_B: '11111111' }, c: '1 loser (2%) · 9 winners (0.6%)' },
  { key: 'exits', name: "B's exits (Friday 22h exit, no candle exit)", set: { InpXFriHour: '22', InpXCx: '0', InpXCxN: '2' }, off: { InpXFriHour: '0', InpXCx: '0', InpXCxN: '2' }, c: '0 losers · 33 winners' },
];
const LCF_FALLBACK = LCF;
let LCF_CAT = null;
async function lcfCatalog() {                                    // GET /api/lcf_catalog: B's groups + the top-20 single filters from the all-saves scan on C (research/filter_scan_C.json)
  try { const c = await api('/api/lcf_catalog'); if (c && c.groups && c.groups.length) { LCF = c.groups.map((g) => ({ key: g.key, name: g.name, set: g.set, off: g.off, source: g.source, c: g.on_c ? `${g.on_c.cut_losers} losers · ${g.on_c.cut_winners} winners · net of cut ${money(g.on_c.cut_net)} · ${g.on_c.selectivity == null ? '–' : g.on_c.selectivity + '×'}` : (LCF_FALLBACK.find((f) => f.key === g.key) || {}).c || '' })); LCF_CAT = c; } } catch (e) { LCF_CAT = { error: String(e) }; }
  if (TAB.tt === 'range') renderPanel('tt');
}
const LCFS = { prev: {}, base: null, baseKey: '', m: null, polling: false, auto: (() => { try { return localStorage.getItem('lcfAuto') !== '0'; } catch (e) { return true; } })(), timer: null };       // m: the server's measurement of each box on this setting (GET /api/lcf)
const lcfKey = () => JSON.stringify([CUR, SRC.ds]);              // the inputs on the chart, as the identity of a measurement
async function lcfMeasure() {                                     // one tester run per box on the setting on the chart (~1 min), then the columns fill
  let key = '';
  try { const r = await api('/api/lcf', { inputs: CUR, ds: SRC.ds }); if (r.error) { toast('⚠ ' + esc(r.error)); return; } key = r.key; } catch (e) { toast('⚠ ' + esc(e.message || e)); return; }
  lcfPoll(key);
}
function lcfAutoKick() {                                          // Zee: the table populates by itself on the Range boxes page and after every tick/untick (debounced; one measurement at a time)
  if (!LCFS.auto) return;
  clearTimeout(LCFS.timer);
  LCFS.timer = setTimeout(async () => {
    if (TAB.tt !== 'range' || !LCFS.auto) return;
    const M = LCFS.m || {};
    if (M.running) return;                                        // the running one finishes first; the next render re-kicks for the new inputs
    if (M.rows && Object.keys(M.rows).length && !M.stale && LCFS.mKey === lcfKey()) return;   // already measured for exactly these inputs
    lcfMeasure();
  }, 1500);
}
async function lcfStop() {
  LCFS.auto = false; try { localStorage.setItem('lcfAuto', '0'); } catch (e) { /* private window */ }
  try { await api('/api/lcf', { stop: true }); } catch (e) { /* ignore */ }
  renderPanel('tt');
}
async function lcfPoll(key) {                                     // rows are shown only when the server measured exactly the inputs on the chart (key)
  if (LCFS.polling) return; LCFS.polling = true;
  try {
    if (!key) { try { key = (await api('/api/lcf', { inputs: CUR, ds: SRC.ds, probe: true })).key; } catch (e) { key = ''; } }
    for (;;) { try { LCFS.m = await api('/api/lcf?key=' + encodeURIComponent(key || '')); } catch (e) { break; } if (TAB.tt === 'range') renderPanel('tt'); if (!LCFS.m.running) break; await new Promise((r) => setTimeout(r, 2000)); }
  } finally { LCFS.polling = false; LCFS.mKey = lcfKey(); if (TAB.tt === 'range') renderPanel('tt'); }
}                 // prev: the setting's own values before a box was ticked; base: trade list with no box ticked
const lcfOn = (f) => Object.entries(f.set).every(([k, v]) => same(CUR[k], v));
const lcfTrades = (D) => { const m = new Map(); (D.TR || []).forEach((t) => m.set(t.tIn + '|' + Math.sign(t.side), t.pnl || 0)); return m; };
function pLoserCut(D) {
  if (D.kind !== 'tt') return '';
  const anyOn = LCF.some(lcfOn), cur = lcfTrades(D);
  if (!anyOn) { LCFS.base = cur; LCFS.baseKey = `${CUR.InpEmaFast}/${CUR.InpEmaSlow}/${SRC.ds}`; }
  else if (!LCFS.base) LCFS.base = cur;                           // the page opened with B's values already in place: the first comparison point is the current run
  const base = LCFS.base, stale = base && LCFS.baseKey !== `${CUR.InpEmaFast}/${CUR.InpEmaSlow}/${SRC.ds}`;
  let removedL = 0, removedW = 0, dNet = 0, added = 0;
  if (base && anyOn) {
    base.forEach((pnl, k) => { if (!cur.has(k)) { if (pnl > 0) removedW++; else removedL++; } });
    cur.forEach((pnl, k) => { if (!base.has(k)) added++; });
    dNet = [...cur.values()].reduce((a, b) => a + b, 0) - [...base.values()].reduce((a, b) => a + b, 0);
  }
  const baseL = base ? [...base.values()].filter((v) => v <= 0).length : 0, baseW = base ? base.size - baseL : 0;
  if (!LCF_CAT) { LCF_CAT = { loading: true }; lcfCatalog(); }
  if ((!LCFS.m || LCFS.mKey !== lcfKey()) && !LCFS.polling) lcfPoll();     // the inputs changed: re-check whether a measurement exists for them
  lcfAutoKick();
  const M = LCFS.m || {}, mrows = M.rows || {}, mb = M.base || {};
  const mcell = (f) => { const r = mrows[f.key]; if (!r) return '<td></td>'.repeat(10);
    const sel = r.selectivity == null ? '–' : r.selectivity >= 999 ? '∞' : r.selectivity.toFixed(2) + '×';
    return `<td>${r.cut_n || ''}</td><td>${r.cut_n ? r.cut_wr + '%' : ''}</td><td class="${r.cut_n ? cls(r.cut_net) : ''}">${r.cut_n ? money(r.cut_net) : ''}</td>` +
      `<td class="${r.removed_losers ? 'pos' : ''}">${r.removed_losers || ''}</td><td class="${r.removed_winners ? 'neg' : ''}">${r.removed_winners || ''}</td><td>${r.added_n ? `+${r.added_n}` : ''}</td>` +
      `<td>${r.with_n}</td><td>${r.with_wr}%</td><td class="${cls(r.with_net)}" title="${r.already_on ? 'already unticked: these trades are blocked now' : 'the total if you untick this box'}">${money(r.with_net)}</td><td class="${cls(r.with_net - r.without_net)}">${r.with_net - r.without_net >= 0 ? '+' : ''}${money(r.with_net - r.without_net)}</td>` +
      `<td class="${r.selectivity == null ? '' : r.selectivity >= 2.8 ? 'pos' : 'neg'}">${sel}</td>`; };
  const rows = LCF.map((f) => `<tr class="${lcfOn(f) ? 'dim' : ''}"><td style="text-align:left" title="${esc(Object.entries(f.set).map(([k, v]) => `${k}=${v}`).join(' · '))} · on C: ${esc(f.c)}">${esc(f.name)}</td><td><input type="checkbox" data-lcf="${f.key}" ${lcfOn(f) ? '' : 'checked'}></td>${mcell(f)}</tr>`).join('') +
    (mrows.all ? `<tr class="tot"><td style="text-align:left">All of B's entry filters together</td><td></td>${mcell({ key: 'all' })}</tr>` : '');
  const mstate = M.running ? `⏳ measuring ${esc(M.phase || '')}…` : M.base && !M.stale ? `measured on THIS setting (${mb.n} trades, ${mb.losers} losers) in ${M.secs} s${M.error ? ' · ⚠ ' + esc(M.error) : ''}` : 'not measured yet for the inputs on the chart - press the button';
  const sel = base && removedW && baseL && baseW ? (removedL / baseL) / (removedW / baseW) : null;     // rate ratio; > 2.8 adds money at $400-win / $4,900-loss geometry
  const live = anyOn && base ? `<p class="note"><b>With the unticked boxes, this setting's trades:</b> <span class="${removedL ? 'pos' : ''}">${removedL} of ${baseL} losers removed</span> · <span class="${removedW ? 'neg' : ''}">${removedW} of ${baseW} winners removed</span>${sel != null ? ` · selectivity <b class="${sel >= 2.8 ? 'pos' : 'neg'}">${sel.toFixed(2)}×</b> (break-even 2.8×)` : removedL && !removedW ? ' · selectivity ∞ (no winner removed)' : ''}${added ? ` · ${added} new trades appeared (freed positions)` : ''} · net <b class="${cls(dNet)}">${dNet >= 0 ? '+' : ''}${money(dNet)}</b>${stale ? ' · <span class="neg">EMA periods or data changed since the no-box snapshot: untick everything once to refresh it</span>' : ''}</p>` :
    `<p class="note">Like the other range boxes: ticked = those trades are allowed. <b>Untick a box to remove the trades it describes</b> (the filter's inputs go into the setting on the chart, the form shows them as changed, the tester re-runs, Overview updates); this line then shows how many of <b>this setting's</b> losers and winners disappeared and the net change. Re-ticking restores the setting's own values.</p>`;
  const scanInfo = LCF_CAT && LCF_CAT.scan ? (LCF_CAT.scan.complete ? `${LCF_CAT.scan.candidates} filter values from every saved setting were measured on C; the top 20 by losing money cut are listed under B's groups` : LCF_CAT.scan.candidates ? `all-saves scan running: ${LCF_CAT.scan.candidates} of ~204 filter values measured so far` : 'all-saves scan not run yet (research/filter_scan_C.py)') : '';
  return `<div><h4>✂ Loser-cutting filters - B's groups and the top filters of every saved setting, measured on C</h4>${scanInfo ? `<p class="note">${scanInfo}</p>` : ''}` +
    `<p>${LCFS.auto ? `<button class="go" id="lcfStop">⏹ Stop auto-measuring</button>` : `<button class="go" id="lcfAutoOn">▶ Auto-measure on</button> <button id="lcfMeasure" ${M.running ? 'disabled' : ''}>Measure once</button>`} <span class="k">${mstate} · one tester run per box · hover a filter name for the inputs it writes and its numbers on C</span></p>` +
    table(['Box = the trades this filter would remove', 'Ticked = they trade', 'Trades', 'Win rate', 'Net of those trades', 'Losers cut', 'Winners cut', 'New trades', 'Total trades if unticked', 'Win rate', 'Total', 'Change ±', 'Loss : Wins'], rows.split('</tr>').filter(Boolean).map((r) => r + '</tr>')) +
    `<p class="note"><b>Loss : Wins</b> = share of this setting's losers the box removes ÷ share of its winners it removes (1× = a blind cut, ∞ = only losers). Unticking a box adds money only if it removes losers at ≥ 2.8× the rate it removes winners (1,569 × $400 ÷ 46 × $4,900 on C). B's run at 1.2-1.4×: they raise the win rate and lower the net (research/risk_assessor_C.json). Turtle TV tester = hypothesis; MT5 judges.</p>` + live + '</div>';
}
document.addEventListener('click', (e) => {
  if (!e.target) return;
  if (e.target.id === 'lcfMeasure') lcfMeasure();
  if (e.target.id === 'lcfStop') lcfStop();
  if (e.target.id === 'lcfAutoOn') { LCFS.auto = true; try { localStorage.setItem('lcfAuto', '1'); } catch (err) { /* private window */ } renderPanel('tt'); }
});
document.addEventListener('change', (e) => {
  const k = e.target.dataset && e.target.dataset.lcf;
  if (!k) return;
  const f = LCF.find((x) => x.key === k);
  if (!e.target.checked) { LCFS.prev[k] = Object.fromEntries(Object.keys(f.set).map((n) => [n, CUR[n]])); Object.assign(CUR, f.set); }   // untick = remove those trades = apply the filter
  else {                                                        // re-tick = allow them again: restore what the setting had, else the group's neutral 'off' values
    const prev = LCFS.prev[k] || {};
    Object.keys(f.set).forEach((n) => { CUR[n] = prev[n] !== undefined && !same(prev[n], f.set[n]) ? prev[n] : f.off[n]; });
    delete LCFS.prev[k];
  }
  settingsTouched = true; markForm(); scheduleSim(0);
});
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
  return pLoserCut(D) + (D.kind === 'tt' ? `<p><button class="go" data-bands="OFF" ${allOn ? 'disabled' : ''}>Turn ranges off</button> <span class="k">${allOn ? 'Ranges are off: every box trades.' : 'Ticks every box on both sides = no range filter.'}</span></p>` : '') +
    `<p class="note">Unticked boxes are grey: there the EA ${(D.kind === 'tt' ? CUR : inp).InpBandOff === '0' ? 'skips the trade' : 'stood aside'}. "Would have made" = the stand-aside trades' result (same stop and exit, no swap).</p>` +
    `<div class="row">${one('BUY', inp.InpBandsB, 0)}${one('SELL', inp.InpBandsS, 21)}</div>` + pHours(D, inp) + pRbox(D);
}
// Session hours (EA v1.37 InpHours, Zee 2026-10-28: "add a session ranges filter where i can check box particular seesions with a higher winrate").
// One box per server hour of the ENTRY. An unticked hour has no trades in the run, so its last numbers with every hour ticked are shown grey.
let HOURSNAP = null;
const SESS = { Asia: [1, 2, 3, 4, 5, 6, 7, 8, 9], London: [10, 11, 12, 13, 14, 15], 'New York': [15, 16, 17, 18, 19, 20, 21, 22] };
function pHours(D, inp) {
  const hrs = String(inp.InpHours || '1'.repeat(24)).padEnd(24, '1'), all = hrs.indexOf('0') < 0, tt = D.kind === 'tt';
  const g = new Map(); for (const t of D.TR) { const h = Math.floor(t.tIn / 3600) % 24; if (!g.has(h)) g.set(h, []); g.get(h).push(t); }
  const st = {}; for (let h = 0; h < 24; h++) st[h] = g.has(h) ? stats(g.get(h)) : null;
  if (tt && all) HOURSNAP = st;
  const tot = stats(D.TR), rows = [];
  for (let h = 0; h < 24; h++) {
    const on = hrs[h] !== '0', s = on ? st[h] : (HOURSNAP && HOURSNAP[h]);
    const tick = tt ? `<input type="checkbox" data-hour="${h}" ${on ? 'checked' : ''}>` : (on ? '✓' : '–');
    const sess = Object.entries(SESS).filter(([, v]) => v.includes(h)).map(([k]) => k).join(' · ');
    const better = s && s.n && s.w / s.n > tot.w / Math.max(1, tot.n);
    rows.push(`<tr class="${on ? '' : 'dim'}"><td>${String(h).padStart(2, '0')}:00</td><td class="k">${sess}</td><td>${tick}</td><td>${s && s.n ? s.n : ''}</td>` +
      `<td class="${s && s.n ? (better ? 'pos' : 'neg') : ''}">${s && s.n ? pct(s.w, s.n) : ''}</td><td class="${s ? cls(s.net) : ''}">${s && s.n ? money(s.net) : ''}</td></tr>`);
  }
  const btns = tt ? ` <button data-hours="ALL">Select all</button> <button data-hours="LOW">Deselect hours below ${pct(tot.w, tot.n)} win rate</button> <button data-hours="LOSE">Deselect losing hours</button>` +
    Object.keys(SESS).map((k) => ` <button data-hours="S:${k}">Only ${k}</button>`).join('') : '';
  return `<h4 style="margin-top:16px">SESSION HOURS - server hour of the entry${btns}</h4>` +
    `<p class="note">Untick an hour to stop new entries in it (EA input InpHours, v1.37). Green win rate = above the run's ${pct(tot.w, tot.n)}. ` +
    `Unticked hours show grey, with their numbers from the last run where every hour was ticked${HOURSNAP ? '' : ' (tick all once to fill them)'}. Server time = the data's broker clock; check in MT5 before trusting it.</p>` +
    table(['Hour', 'Session', 'Ticked', 'Trades', 'Win rate', 'Net'], rows);
}
// rbox.py range-box families (Zee 2026-10-28): VWAP bands, Initial Balance, premium / discount, Keltner, expansion, value area.
// Turtle TV tester inputs TvBox_<family>_<B|S> ("1" = trade); unticked boxes stop new entries there, so the Overview changes with them.
let RBSNAP = {};
function pRbox(D) {
  if (D.kind !== 'tt') return '';
  const R = D.rbox;
  if (!R) return `<p class="note">More range boxes (VWAP, Initial Balance, premium / discount, Keltner, expansion, value area) appear on the 15-minute datasets.</p>`;
  if (R.error) return `<p class="note bad">Range-box families: ${esc(R.error)}</p>`;
  const lab = new Map(R.rows.map((r) => [r[0] + '|' + r[1], r.slice(2)]));
  let h = `<h3 style="margin-top:18px">MORE RANGE BOXES · where the entry sat in six other ranges</h3><p class="note">Tick / untick a box: entries in unticked boxes are skipped and the Overview, List of trades and every page re-run with it.
    Unticked boxes show grey with their numbers from the last run where that family was all ticked. Turtle TV tester only for now (the EA does not have these yet) - hypothesis until MT5 checks it.</p>`;
  R.spec.forEach((fam, f) => {
    h += `<h4>${esc(fam.title)}</h4><div class="row">`;
    for (const [sd, side] of [['B', 1], ['S', -1]]) {
      const key = `TvBox_${fam.key}_${sd}`, mask = String(CUR[key] || '').padEnd(fam.boxes.length, '1'), all = mask.indexOf('0') < 0;
      const st = fam.boxes.map((_, b) => stats(D.TR.filter((t) => Math.sign(t.side) === side && (lab.get(t.tIn + '|' + Math.sign(t.side)) || [])[f] === b)));
      if (all) RBSNAP[key] = st;
      const tot = stats(D.TR.filter((t) => Math.sign(t.side) === side));
      const rows = fam.boxes.map((name, b) => {
        const on = mask[b] !== '0', s = on ? st[b] : (RBSNAP[key] || [])[b];
        const better = s && s.n && s.w / s.n > tot.w / Math.max(1, tot.n);
        return `<tr class="${on ? '' : 'dim'}"><td>${esc(name)}</td><td><input type="checkbox" data-rb="${key}" data-rbi="${b}" data-rbn="${fam.boxes.length}" ${on ? 'checked' : ''}></td>` +
          `<td>${s && s.n ? s.n : ''}</td><td class="${s && s.n ? (better ? 'pos' : 'neg') : ''}">${s && s.n ? pct(s.w, s.n) : ''}</td><td class="${s ? cls(s.net) : ''}">${s && s.n ? money(s.net) : ''}</td></tr>`;
      }).join('');
      h += `<div><h4>${side > 0 ? 'BUY' : 'SELL'} <button data-rball="${key}">Select all</button> <button data-rblow="${key}" data-rbf="${f}" data-rbside="${side}">Deselect below ${pct(tot.w, tot.n)} win rate</button></h4>` +
        table(['Box', 'Ticked', 'Trades', 'Win rate', 'Net'], [rows]) + '</div>';
    }
    h += '</div>';
  });
  return h;
}
document.addEventListener('change', (e) => {
  const k = e.target.dataset && e.target.dataset.rb;
  if (!k) return;
  const n = +e.target.dataset.rbn, m = String(CUR[k] || '').padEnd(n, '1').slice(0, n).split('');
  m[+e.target.dataset.rbi] = e.target.checked ? '1' : '0'; CUR[k] = m.join(''); markForm(); scheduleSim(0);
});
document.addEventListener('click', (e) => {
  const d = e.target.dataset || {};
  if (d.rball) { CUR[d.rball] = '1'.repeat(+(document.querySelector(`[data-rb="${d.rball}"]`) || {}).dataset?.rbn || 16); markForm(); scheduleSim(0); }
  if (d.rblow) {
    const st = RBSNAP[d.rblow]; if (!st) { toast('Tick every box of this family once first, so each box has its numbers.'); return; }
    const side = +d.rbside, tot = stats(TT.TR.filter((t) => Math.sign(t.side) === side)), wr = tot.w / Math.max(1, tot.n);
    CUR[d.rblow] = st.map((s) => (s && s.n && s.w / s.n < wr ? '0' : '1')).join(''); markForm(); scheduleSim(0);
  }
});
function setHours(s) { CUR.InpHours = s; markForm(); scheduleSim(0); }
document.addEventListener('change', (e) => {
  const h = e.target.dataset && e.target.dataset.hour;
  if (h == null) return;
  const s = String(CUR.InpHours || '1'.repeat(24)).padEnd(24, '1').split(''); s[+h] = e.target.checked ? '1' : '0'; setHours(s.join(''));
});
document.addEventListener('click', (e) => {
  const a = e.target.dataset && e.target.dataset.hours;
  if (!a) return;
  if (a === 'ALL') return setHours('1'.repeat(24));
  if (a.startsWith('S:')) { const v = SESS[a.slice(2)]; return setHours([...Array(24)].map((_, i) => v.includes(i) ? '1' : '0').join('')); }
  const src = HOURSNAP; if (!src) { toast('Tick every hour once first, so each hour has its numbers.'); return; }
  const tot = stats(TT.TR), wr = tot.w / Math.max(1, tot.n), cur = String(CUR.InpHours || '1'.repeat(24)).padEnd(24, '1').split('');
  for (let i = 0; i < 24; i++) { const s = src[i]; if (!s || !s.n) continue; if (a === 'LOW' ? s.w / s.n < wr : s.net < 0) cur[i] = '0'; }
  setHours(cur.join(''));
});
// Zee 2026-11-06: a comment box + Save in front of every loss; the comments are read later to find a pattern among the losses
let LOSSC = null, CLC = null;
const tradeId = (t) => { const d = new Date(Math.round(t.tIn) * 1000), p = (n) => String(n).padStart(2, '0');
  return `${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}-${p(d.getUTCHours())}${p(d.getUTCMinutes())}${p(d.getUTCSeconds())}-${t.side > 0 ? 'B' : 'S'}`; };
async function clcLoad() { try { const a = await (await fetch('/api/claude_loss_comments')).json(); CLC = {}; (a || []).forEach((x) => { CLC[x.id] = x; }); } catch (e) { CLC = {}; } if (TAB.tt === 'trades') renderPanel('tt'); }
const lossKey = (t) => `${t.side > 0 ? 'B' : 'S'}|${Math.round(t.tIn)}|${(+t.en).toFixed(5)}`;
async function lossLoad() { try { LOSSC = await (await fetch('/api/loss_comments')).json(); } catch (e) { LOSSC = {}; } if (TAB.tt === 'trades') renderPanel('tt'); }
function pTrades(D) {
  const notes = D.kind === 'tt';
  if (notes && LOSSC === null) { LOSSC = {}; lossLoad(); }
  if (notes && CLC === null) { CLC = {}; clcLoad(); }
  const nLoss = notes ? D.TR.filter((t) => t.pnl < 0).length : 0, nDone = notes ? D.TR.filter((t) => t.pnl < 0 && LOSSC[lossKey(t)]).length : 0;
  const rows = D.TR.map((t) => {
    const k = lossKey(t), c = notes && LOSSC[k] ? LOSSC[k].comment : '';
    const box = !notes ? '' : t.pnl < 0
      ? `<td class="lossnote" style="min-width:260px"><input data-lckey="${esc(k)}" value="${esc(c)}" placeholder="why did this one lose?" style="width:190px"> <button data-lcsave="${esc(k)}" class="dexbtn sm">${c ? '✓ Saved' : 'Save'}</button></td>`
      : '<td></td>';
    const cc = notes && t.pnl < 0 && CLC[tradeId(t)] ? CLC[tradeId(t)] : null;
    const cbox = !notes ? '' : cc
      ? `<td style="text-align:left;min-width:320px;max-width:520px;font-size:12px"><b>${esc(cc.cause || '')}</b>${cc.avoidable_before_entry ? ' · <span class="pos">avoidable</span>' : ''}<br>${esc(cc.comment || '')}</td>`
      : '<td></td>';
    return `<tr class="click ${D.kind === 'tt' && SEL === t.num ? 'sel' : ''}" data-num="${t.num}" data-kind="${D.kind}"><td>#${t.num}</td><td style="color:${t.side > 0 ? C.up : C.down}">${t.side > 0 ? 'BUY' : 'SELL'}</td>` +
      `<td>${dt(t.tIn)}</td><td>${f2(t.en)}</td><td>${f2(t.sl)}</td><td>${dt(t.tOut)}</td><td>${f2(t.ex)}</td><td style="text-align:left">${esc(t.why)}</td><td class="${cls(t.pnl)}">${money(t.pnl, 2)}</td>${box}${cbox}</tr>`;
  });
  const head = ['#', 'Side', 'Entry', 'Price', 'Stop', 'Exit', 'Price', 'Why it closed', 'Net'].concat(notes ? ['Your comment on the loss', "Claude's reading of the loss (chart study)"] : []);
  return `<p class="note">Click a trade to see it on the chart.${D.kind === 'mt' ? ' Net includes swap, exactly as MT5 booked it.' : ' Net includes swap.'}` +
    (notes ? ` · <b>${nDone} of ${nLoss}</b> losses commented (Enter or Save stores a comment; an empty box removes it).` : '') + `</p><div class="scroll">` +
    table(head, rows) + '</div>';
}
async function lossSave(k) {
  const inp = document.querySelector(`input[data-lckey="${CSS.escape(k)}"]`); if (!inp) return;
  const t = TT.TR.find((x) => lossKey(x) === k) || {};
  const trade = { side: t.side, entry_time: t.tIn, entry: t.en, stop: t.sl, exit_time: t.tOut, exit: t.ex, net: t.pnl, why: t.why };
  let r = null;
  try { r = await (await fetch('/api/loss_comment', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key: k, comment: inp.value, trade }) })).json(); } catch (e) { r = null; }
  if (r && r.ok) {
    if (inp.value.trim()) LOSSC[k] = { comment: inp.value.trim() }; else delete LOSSC[k];
    const btn = document.querySelector(`button[data-lcsave="${CSS.escape(k)}"]`); if (btn) btn.textContent = inp.value.trim() ? '✓ Saved' : 'Save';
  } else alert('Could not save the comment');
}
document.addEventListener('keydown', (e) => { const k = e.target && e.target.dataset && e.target.dataset.lckey; if (k && e.key === 'Enter') { e.preventDefault(); lossSave(k); } });
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
let RISK_OPTS = null, RISK_REF = null, RISK_SCAN_INPUTS = null;
const RISK_SLIDERS = [
  ['InpSlMode', 0, 2, 1, 'Which stop formula is active: fixed pips, ATR distance, or price distance.', 'stop'],
  ['InpSlPips', 5, 150, 5, 'Stop distance in pips; active only in stop mode 0.', 'stop', '0'],
  ['InpSlAtrMult', 0.5, 3, 0.1, 'ATR stop multiplier; active only in stop mode 1.', 'stop', '1'],
  ['InpSlUsd', 1, 50, 0.5, 'Price-distance stop from entry (not account-currency USD); active only in stop mode 2.', 'stop', '2'],
  ['InpMaxRiskUsd', 0, 40, 1, 'Skips entries whose stop distance is wider than this price distance; it does not cap an open loss.', 'stop'],
  ['InpXLossCap', 0, 25, 1, 'Optional price-distance clamp on the entry stop; applies when the Exit Lab module is active.', 'stop'],
  ['InpFixTpPips', 0, 100, 5, 'Fixed broker target in pips (0.1 XAUUSD price units per pip).', 'target'],
  ['InpXDecayBars', 0, 48, 4, 'After this many candles, tighten the stop to the selected R level; 0 disables it.', 'time'],
  ['InpXDecayR', -1, 0.5, 0.25, 'Stop level in R after the decay timer; negative values still allow a loss.', 'time'],
  ['InpXStaleBars', 0, 48, 4, 'Close if the configured progress is not reached by this many candles; 0 disables it.', 'time'],
  ['InpXStaleR', 0, 2, 0.1, 'Minimum progress in R required by the stale-trade timer.', 'time'],
  ['InpXMaxBars', 0, 48, 4, 'Maximum hold in candles; 0 disables the time exit.', 'time'],
  ['InpCloseLossMins', 0, 120, 5, 'Close a losing trade this many minutes before session close; not time since entry.', 'session'],
  ['InpBeUsd', 0, 50, 0.5, 'Legacy break-even setting; only applies in exit mode 0.', 'target', '0'],
  ['InpLots', 0.01, 5, 0.01, 'Fixed lot size when InpRiskPct is 0.', 'size'],
  ['InpRiskPct', 0, 5, 0.05, 'Position sizing as a percentage of equity; 0 uses fixed InpLots.', 'size'],
  ['InpDayLossUsd', 0, 10000, 250, 'Stops new entries after this daily loss in account currency; does not close the open trade.', 'daily'],
  ['InpDayLossPct', 0, 10, 0.25, 'Stops new entries after this percentage loss from the day-start equity.', 'daily'],
];
let RISK_GROUPS = ['stop', 'time'];
let RISK_AUTO = true;
try { RISK_AUTO = localStorage.getItem('riskAuto') !== '0'; } catch (error) {}
const OPTUI = { obj: 'ret_dd', boxes: false, keep: false };   // the optimizer's controls, kept across redraws
function pOpt() {
  const o = OPTS;
  const obj = OPTUI.obj;
  const objectives = [['ret_dd', 'net ÷ max drawdown'], ['net', 'net profit'], ['pf', 'profit factor'], ['wr', 'win rate']];
  if (o && Array.isArray(o.objectives) && o.objectives.includes('avg_loss')) objectives.push(['avg_loss', 'Cut down Avg Loss']);
  if (o && Array.isArray(o.objectives) && o.objectives.includes('worst_loss')) objectives.push(['worst_loss', 'Cut down Worst Loss']);
  objectives.push(['entries', 'Entries: try every entry setting'], ['exits', 'Exits: try every exit setting'], ['ranges', 'Range boxes: most boxes at 100%']);
  let h = `<div class="row" style="align-items:center;gap:10px"><b>Step optimizer</b>
    <label>Score <select id="oObj">${objectives.map(([v, l]) => `<option value="${v}" ${v === obj ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
    <label class="tog"><input type="checkbox" id="oBox" ${OPTUI.boxes ? 'checked' : ''}> include the range boxes</label>
    <label class="tog"><input type="checkbox" id="oKeep" ${OPTUI.keep ? 'checked' : ''}> keep optimizing (restarts)</label>
    <button id="oGo" class="primary">Optimize from the settings on screen</button><button id="oStop">Stop</button></div>
    <p class="note">Each setting is moved one step up and down; a step that helps is repeated until it stops helping; all settings, pass after pass, until nothing improves.
    ${obj === 'avg_loss' ? '“Cut down Avg Loss” ranks settings by the average P&L of losing trades: a result closer to zero is better.' : ''}
    ${obj === 'worst_loss' ? '“Cut down Worst Loss” ranks settings by the single largest losing trade in the training period: a result closer to zero is better. It cannot distinguish strategies with no losing trades, so compare trade counts and the held-out period as well.' : ''}
    The score is measured on the training period only. The held-out period is shown beside it but never used to choose: if it gets worse while training improves, the settings are memorising the past.</p>`;
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
  const B = o.baseline, best = o.best, line = (x) => x ? `${money(x.net)} · WR ${x.wr}% · PF ${x.pf} · ${x.n} trades${o.objective === 'avg_loss' ? ` · avg loss ${money(x.avg_loss)}` : ''}${o.objective === 'worst_loss' ? ` · worst loss ${money(x.worst_loss)}` : ''}` : '–';
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
  const n0 = (B.train.n || 0) + (B.test.n || 0);                 // the trade count vs your settings': is the score bought by cutting trades?
  const ntd = (a, b) => { const n = (a.n || 0) + (b.n || 0), f = n0 ? n / n0 : 1;
    return `<td class="${f < 0.5 ? 'bad' : f < 0.8 ? 'warn' : ''}" title="${a.n} + ${b.n} trades; your settings: ${n0}">${n.toLocaleString()} <span class="k">(${Math.round(100 * f)}%)</span></td>`; };
  const scoreText = (score) => o.objective === 'avg_loss' || o.objective === 'worst_loss' ? money(score) : (+score).toFixed(2);
  const scoreLabel = o.objective === 'avg_loss' ? 'Avg loss score' : o.objective === 'worst_loss' ? 'Worst loss score' : 'Score';
  const steps = o.log.map((l, i) => `<tr><td>${i + 1}</td><td style="text-align:left">${esc(l.run)}</td><td style="text-align:left">${esc(l.setting.replace(/^Inp/, ''))}</td><td>${esc(l.from)} → ${esc(l.to)}</td><td>${scoreText(l.score)}</td>` +
    `<td class="${cls(l.train.net)}">${money(l.train.net)} · ${l.train.wr}%</td><td class="${cls(l.test.net)}">${money(l.test.net)} · ${l.test.wr}%</td><td class="${cls(l.train.net + l.test.net)}"><b>${money(l.train.net + l.test.net)}</b></td>${ntd(l.train, l.test)}<td class="k">${l.t}s</td>` +
    `<td>${l.inputs ? `<button data-step="${o.log.length > 200 ? i + o.log.length - 200 : i}">Apply this setting</button>` : ''}</td></tr>`);
  h += `<h4>Steps that helped</h4><div class="scroll">${table(['#', 'Run', 'Setting', 'Change', scoreLabel, LA, LB, 'Total', 'Trades (vs yours)', 'At', ''], steps)}</div>`;
  if (o.board && o.board.length > 1) h += `<h4>Best of each restart</h4>` + table([scoreLabel, LA, LB, 'Total', 'Trades (vs yours)', 'Changes', ''],
    o.board.map((x, i) => `<tr><td>${scoreText(x.score)}</td><td>${money(x.train.net)} · ${x.train.wr}%${o.objective === 'avg_loss' ? ` · avg loss ${money(x.train.avg_loss)}` : ''}${o.objective === 'worst_loss' ? ` · worst loss ${money(x.train.worst_loss)}` : ''}</td><td class="${cls(x.test.net - B.test.net)}">${money(x.test.net)} · ${x.test.wr}%${o.objective === 'avg_loss' ? ` · avg loss ${money(x.test.avg_loss)}` : ''}${o.objective === 'worst_loss' ? ` · worst loss ${money(x.test.worst_loss)}` : ''}</td><td><b>${money(x.train.net + x.test.net)}</b></td>${ntd(x.train, x.test)}` +
      `<td style="text-align:left" class="k">${Object.entries(x.changed).map(([k, v]) => `${esc(k.replace(/^Inp/, ''))}=${esc(v)}`).join(' ')}</td><td><button data-board="${i}">show</button></td></tr>`));
  return h;
}
function pRisk() {
  const ref = RISK_REF, inp = ref && ref.inputs || {}, report = ref && ref.report || {}, ts = report.trade_stats || {};
  const run = ref && RUNS.find((x) => x.id === ref.id), mode = String(CUR.InpSlMode ?? inp.InpSlMode ?? '');
  const stopName = mode === '2' ? 'InpSlUsd' : mode === '1' ? 'InpSlAtrMult' : 'InpSlPips';
  const sameAsReport = ref && Object.entries(inp).every(([k, v]) => same(CUR[k], v));
  const o = RISK_OPTS;
  const scanInputs = RISK_SCAN_INPUTS || (o && o.risk_inputs);
  const scanStale = !!(o && o.baseline) && (!scanInputs || Object.entries(scanInputs).some(([k, v]) => !same(CUR[k], v)));
  const scanPct = o && o.running ? Math.min(95, Math.max(3, Math.round(100 * o.evals / (o.evals + Math.max(1, o.space_size || 30))))) : 100;
  let h = `<div class="risk-hero dex"><div><div class="crth">DEXTER'S RISK MANAGER · TAIL-LOSS WORKSHOP</div>
    <h3>One loss should not erase a long run of wins.</h3>
    <p>Start with the loss mechanism MT5 actually used. Compare safeguards without quietly “winning” by throwing away almost all your trades.</p></div>
    <div class="risk-stamp"><b>${ref ? esc(ref.id) : 'MT5 REPORT'}</b><span>${ref ? esc(ref.period || 'M15') + ' · ' + esc(ref.created || '') : 'loading measured report…'}</span></div></div>`;
  if (typeof pProbe === 'function') h += pProbe();                 // 01 · Probe entry (v1.36): the first setting
  h += `<section class="risk-card risk-overview"><h4>LIVE OVERVIEW · EFFECT OF YOUR SETTINGS</h4>
    ${TT ? pOverviewStats(TT) : '<p class="note">Waiting for the Turtle TV preview…</p>'}
    <p class="note">This is the current Turtle TV preview and refreshes when you finish changing a slider. Treat simulated results as a hypothesis; verify the settings in MT5 Strategy Tester before promoting them.</p></section>`;
  if (!ref) return h + '<p class="note">Loading the reference MT5 report…</p>';
  h += `<div class="risk-stats">
    <div class="risk-stat"><span>MT5 net</span><b>${money(report.net || 0)}</b></div>
    <div class="risk-stat"><span>Worst trade</span><b class="neg">${money(ts.largest_loss || run && run.worst || 0)}</b></div>
    <div class="risk-stat"><span>Average win / loss</span><b>${money(ts.avg_win || run && run.avg_win || 0)} <i>/</i> <span class="neg">${money(ts.avg_loss || run && run.avg_loss || 0)}</span></b></div>
    <div class="risk-stat"><span>Win rate · trades</span><b>${ref.execution_stats && ref.execution_stats.wr != null ? ref.execution_stats.wr + '%' : run && run.wr != null ? run.wr + '%' : '–'} · ${report.trades || '–'}</b></div>
    <div class="risk-stat"><span>Max drawdown</span><b>${esc(report.dd || '–')}</b></div>
    <div class="risk-stat"><span>One worst loss costs</span><b>${ts.avg_win ? (Math.abs(ts.largest_loss) / ts.avg_win).toFixed(1) : '–'} average wins</b></div></div>`;
  h += `<div class="risk-alert"><b>Read the stop correctly:</b> In this run, <code>InpSlMode=2</code> makes <code>InpSlUsd=25</code> the active stop distance. At 2 lots, a $25 XAUUSD move is roughly <b>$5,000 nominal exposure</b> (25 × 100 oz × 2 lots), before spread, execution gaps or slippage. That lines up with the $${Math.abs(ts.largest_loss || 0).toLocaleString()} observed worst trade; it is not a guaranteed loss ceiling.</div>`;
  const sliderGroups = [...new Set(RISK_SLIDERS.map((x) => x[5]))];
  const sliderLabel = (name, value) => name === 'InpSlMode'
    ? `${value} · ${['fixed pips', 'ATR distance', 'price distance'][Number(value)] || 'unknown'}`
    : name === 'InpRiskPct' || name === 'InpDayLossPct' ? `${value}%`
      : name === 'InpLots' ? `${Number(value).toFixed(2)} lots`
        : value;
  const sliders = sliderGroups.map((group) => `<div class="risk-slider-group"><h5>${esc(group === 'stop' ? 'STOP & ENTRY GUARDS' : group === 'time' ? 'TIME-BASED EXITS' : group === 'target' ? 'TARGET & BREAK-EVEN' : group === 'size' ? 'POSITION SIZE' : group === 'daily' ? 'DAILY CIRCUIT BREAKERS' : 'SESSION CLOSE')}</h5>` +
    RISK_SLIDERS.filter((x) => x[5] === group).map(([name, min, max, step, help, _group, activeMode]) => {
      const value = String(CUR[name] ?? inp[name] ?? 0), num = Number(value);
      const lo = Math.min(min, Number.isFinite(num) ? num : min), hi = Math.max(max, Number.isFinite(num) ? num : max);
      const inactive = (activeMode != null && activeMode !== mode) || (name === 'InpBeUsd' && String(CUR.InpExitMode ?? inp.InpExitMode) !== '0');
      const status = activeMode != null ? (inactive ? `inactive in stop mode ${mode}` : 'active stop') :
        name === 'InpBeUsd' && inactive ? 'inactive in this exit mode' : '';
      return `<label class="risk-slider ${inactive ? 'inactive' : ''}"><span class="risk-slider-title"><b>${esc(name)}</b><strong id="riskValue_${name}">${esc(sliderLabel(name, value))}</strong></span>
        <input type="range" data-risk-slider="${esc(name)}" min="${lo}" max="${hi}" step="${step}" value="${esc(value)}">
        <span class="risk-slider-help">${status ? `<em>${esc(status)}</em> · ` : ''}${esc(help)}</span></label>`;
    }).join('') + '</div>').join('');
  h += `<div class="risk-pair"><section class="risk-card"><h4>THE SETTINGS THAT MATTER · LIVE SLIDERS</h4>
    <p class="note">Each slider changes the chart settings and refreshes the Turtle TV preview. Inactive stop inputs remain visible so their values are clear, but only the selected stop mode’s input controls the active stop.</p>
    <div class="risk-sliders">${sliders}</div>
    <p class="note">For the reference report, the active stop is <code>InpSlUsd=25</code>. <code>InpSlAtrMult=1.7</code> and <code>InpSlPips=95</code> are inactive in mode 2. Also, <code>InpMaxRiskUsd</code> skips wide-stop entries; it is not an open-trade dollar-loss cap.</p></section>
    <section class="risk-card"><h4>FOUR PRACTICAL LEVERS</h4>
      <div class="risk-lever"><b>01 · Bound the active stop</b><span>Scan <code>${esc(stopName)}</code>; also test <code>InpXLossCap</code> and the entry-only <code>InpMaxRiskUsd</code>. Tighter stops can increase stop-outs.</span></div>
      <div class="risk-lever"><b>02 · Cut a trade that stalls</b><span>Test <code>InpXDecayBars</code> + <code>InpXDecayR</code>, <code>InpXStaleBars</code>, and <code>InpXMaxBars</code>. On M15, 4 bars = 1 hour. These change exits, not just entries.</span></div>
      <div class="risk-lever"><b>03 · Size to the stop</b><span><code>InpRiskPct</code> is currently 0, so fixed <code>InpLots=${esc(inp.InpLots)}</code> is used. Pick a conservative risk fraction to make wide stops use fewer lots.</span>
        <div class="risk-size">Use the <code>InpRiskPct</code> slider in “The settings that matter” to tune sizing.</div></div>
      <div class="risk-lever"><b>04 · Guard the day, not the open trade</b><span><code>InpDayLossUsd</code> stops new entries after the day’s loss threshold. It is a portfolio guard, not a per-trade stop. The report already has <code>InpDayLossPct=${esc(inp.InpDayLossPct)}</code>.</span></div>
    </section></div>`;
  h += `<section class="risk-card risk-scan"><div class="risk-head"><div><h4>RISK SCAN · KEEP THE STRATEGY IN THE TEST</h4>
    <p>Tests every configured grid value for each selected lever, one control at a time, on <b>${esc(SRC.ds)}</b>. Candidates must retain at least <b>70% of baseline training trades</b>. The held-out period is reported, never used to select. No setting is applied automatically; nothing here changes your EA or saved defaults.</p></div>
    <div class="risk-actions"><button id="riskScan" class="dexbtn" ${o && o.running ? 'disabled' : ''}>${o && o.running ? '⏳ SCANNING…' : '🔬 SCAN EVERY SELECTED SETTING'}</button>
      <button id="riskStop" class="dexbtn sm" ${!o || !o.running ? 'disabled' : ''}>Stop scan</button></div></div>
    <div class="risk-groups">
      ${[['stop', 'Active stop + stop-distance guard'], ['time', 'Loss decay + stale/time exits'], ['target', 'Fixed target trade-off'], ['session', 'Session-close loss exit'], ['daily', 'Daily new-entry circuit breaker']]
        .map(([value, label]) => `<label><input type="checkbox" class="riskGroup" value="${value}" ${RISK_GROUPS.includes(value) ? 'checked' : ''}> ${label}</label>`).join('')}
    </div>
    <label class="risk-auto"><input type="checkbox" id="riskAuto" ${RISK_AUTO ? 'checked' : ''}> scan again after every pick</label>
    ${sameAsReport ? '<p class="risk-good">✓ Chart inputs match the MT5 reference run.' : `<p class="risk-warn">⚠ Chart settings do not match the MT5 reference. <button class="dexbtn sm" data-risk-load="1">Load ${esc(ref.id)} settings to chart</button> before scanning that exact configuration.</p>`}
    <p class="note">The search objective is the least severe single losing trade, not net profit. Historical simulator results are hypotheses only. Review trades, drawdown, the held-out period and MT5 fills before deciding.</p>
    ${!o ? '<p class="note">Choose risk levers and start a scan to compare candidates.</p>' : ''}
    ${o && o.error ? `<p class="bad">Scan failed: ${esc(o.error)}</p>` : ''}
    ${o && o.baseline ? `<div class="risk-progress"><b>${o.running ? '🧪 THE LAB IS TESTING EVERY SETTING' : o.error ? 'SCAN STOPPED' : '✓ SCAN COMPLETE'} · ${o.evals} simulations</b><div><i style="width:${scanPct}%"></i></div><span>${o.running ? 'Candidates update as the scan proceeds' : `${o.seconds}s · `}training trade floor ${o.trade_floor || 30}</span></div>
      <div class="risk-results">${[['Your starting settings', o.baseline], ['Best candidate', o.best]].map(([title, x]) => x ? `<div class="risk-result"><h4>${title}</h4><p><b>${esc(o.labels && o.labels[0] || 'Train')}:</b> ${money(x.train.net)} · ${x.train.n} trades · worst ${money(x.train.worst_loss)} · avg loss ${money(x.train.avg_loss)}</p>
        <p><b>${esc(o.labels && o.labels[1] || 'Test')}:</b> ${money(x.test.net)} · ${x.test.n} trades · worst ${money(x.test.worst_loss)} · avg loss ${money(x.test.avg_loss)}</p></div>` : '').join('')}</div>
      ${scanStale ? '<p class="risk-warn">⚠ This scan has no matching chart-settings snapshot or the chart changed since it ran. Rescan before applying suggestions.</p>' : ''}
      ${o.best && o.best.changed && Object.keys(o.best.changed).length ? `<p>Top combined training-period suggestion: <code>${Object.entries(o.best.changed).map(([k,v]) => `${esc(k)}=${esc(v)}`).join(' · ')}</code>
        <button class="dexbtn sm" data-risk-best="1" ${scanStale ? 'disabled' : ''}>Apply combined candidate</button></p>` : ''}
      ${o.log && o.log.length ? (() => {
        const ranked = o.log.map((x, index) => ({ ...x, index })).filter((x) => x.year)
          .sort((a, b) => b.train.worst_loss - a.train.worst_loss).slice(0, 12);
        const baseline = o.baseline.year;
        const stale = scanStale;
        const delta = (value, base, suffix = '') => {
          const d = value - base;
          return `<span class="${cls(d)}">${d > 0 ? '+' : ''}${Number(d).toFixed(suffix === ' pts' ? 1 : 2)}${suffix}</span>`;
        };
        const deltaMoney = (value, base) => `<span class="${cls(value - base)}">${money(value - base)}</span>`;
        return `<h4>RANKED SUGGESTIONS · PICK THE BEST RISK TRADE-OFF</h4><p class="note">Ranked by training worst loss. Each card shows full-period totals and both halves. Simulator output is a hypothesis; compare the trade-offs and validate picks in MT5.</p>
          <div class="risk-suggestions">${ranked.map((x, i) => {
            const yr = x.year, improvement = Math.abs(o.baseline.train.worst_loss) - Math.abs(x.train.worst_loss);
            const sideEffects = [];
            const netDelta = yr.net - baseline.net, wrDelta = yr.wr - baseline.wr, pfDelta = yr.pf - baseline.pf;
            sideEffects.push(Math.abs(netDelta) < 1 ? 'net unchanged' : `${money(netDelta)} net`);
            sideEffects.push(Math.abs(wrDelta) < 0.05 ? 'WR unchanged' : `${wrDelta < 0 ? '−' : '+'}${Math.abs(wrDelta).toFixed(1)} pts WR`);
            sideEffects.push(Math.abs(pfDelta) < 0.005 ? 'PF unchanged' : `${pfDelta < 0 ? '−' : '+'}${Math.abs(pfDelta).toFixed(2)} PF`);
            return `<article class="risk-suggestion" style="--rank:${i}"><span class="risk-rank">#${i + 1}</span>
              <div class="risk-suggestion-main"><b>🛡 ${esc(x.setting.replace(/^Inp/, ''))} ${esc(x.from)} → ${esc(x.to)}</b>
                <p class="risk-total"><strong>${money(yr.net)} net</strong> · WR ${yr.wr}% · PF ${yr.pf} · ${yr.n.toLocaleString()} trades · avg loss ${money(yr.avg_loss)} · worst ${money(yr.worst_loss)}</p>
                <p class="risk-delta">vs yours: ${deltaMoney(yr.net, baseline.net)} net · ${delta(yr.wr, baseline.wr, ' pts')} WR · ${delta(yr.pf, baseline.pf, ' PF')} · ${yr.n - baseline.n > 0 ? '+' : ''}${yr.n - baseline.n} trades</p>
                <p class="risk-halves"><b>${esc(o.labels && o.labels[0] || 'Train')}:</b> ${money(x.train.net)} · WR ${x.train.wr}% · PF ${x.train.pf} · ${x.train.n} trades · worst ${money(x.train.worst_loss)}<br>
                  <b>${esc(o.labels && o.labels[1] || 'Held-out')}:</b> ${money(x.test.net)} · WR ${x.test.wr}% · PF ${x.test.pf} · ${x.test.n} trades · worst ${money(x.test.worst_loss)}</p>
              </div><button class="risk-pick" data-risk-step="${x.index}" ${stale ? 'disabled' : ''}><span>TRADE FOR</span><b>${money(x.train.worst_loss)} train worst</b><small>${improvement > 0 ? `cuts tail by $${Math.round(improvement).toLocaleString()}` : 'worst-loss change'}<br>Side effect: ${sideEffects.join(' · ')}</small><strong>Pick this option →</strong></button></article>`;
          }).join('')}</div>${!ranked.length ? '<p class="note">This scan predates full-period metrics. Run it again to get complete ranked cards.</p>' : ''}`;
      })() : o.best && o.best.changed && Object.keys(o.best.changed).length ? '<p class="note">No individual improvement steps were recorded; use the top candidate when the scan finishes.</p>' : '<p class="note">No selected risk change improved the training worst-loss score while meeting the trade floor.</p>'}` : ''}</section>`;
  h += `<p class="risk-foot">MT5 remains the judge. After applying a hypothesis, use <b>Check in MT5</b> in the header; compare the actual report before saving or exporting. No Python result is promoted here.</p>`;
  return h;
}
function riskScanMatchesChart() {
  const scanned = RISK_SCAN_INPUTS || (RISK_OPTS && RISK_OPTS.risk_inputs);
  return !!scanned && Object.entries(scanned).every(([key, value]) => same(CUR[key], value));
}
function renderPanel(sec) {
  document.querySelectorAll(`nav[data-sec="${sec}"] button`).forEach((b) => b.classList.toggle('on', b.dataset.t === TAB[sec]));
  const el = $(sec === 'tt' ? '#panelTT' : '#panelMT'), D = sec === 'tt' ? TT : MT;
  const keep = [...el.querySelectorAll('.scroll')].map((s) => s.scrollTop);              // redraws keep the lists where Zee scrolled them
  const back = () => el.querySelectorAll('.scroll').forEach((s, i) => { if (keep[i] != null) s.scrollTop = keep[i]; });
  if (sec === 'tt' && TAB.tt === 'opt') { el.innerHTML = pOpt(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'lab') { el.innerHTML = pLab(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'tp') { el.innerHTML = pTP(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'dexter') { el.innerHTML = pDex(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'life') { el.innerHTML = pLife(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'ml') { el.innerHTML = pML(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'research') { el.innerHTML = pResearch(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'deploy') { el.innerHTML = pDeploy(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'lego') { el.innerHTML = pLego(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'mission') { el.innerHTML = pMission(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'stress') { el.innerHTML = pStress(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'validation') { el.innerHTML = pValidation(); back(); return; }
  if (sec === 'tt' && TAB.tt === 'risk') { el.innerHTML = pRisk(); back(); if (typeof probeEval === 'function' && !PROBE.res) probeEval(); return; }
  if (sec === 'tt' && TAB.tt === 'validation') { el.innerHTML = pValidation(); back(); return; }
  if (sec === 'mt' && MTWAIT) { el.innerHTML = `<div class="dexprog"><div class="dexprog-t">⏳ MT5 IS RUNNING THE SETTINGS ON SCREEN</div><div class="dexprog-bar"><i style="width:${Math.min(95, 3 + (Date.now() - MTWAIT.t0) / 900)}%"></i></div>
    <div class="dexprog-s">${esc(MTWAIT.phase || 'starting')} · the result replaces this when it lands (about a minute)</div></div>`; return; }
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
  const r = await api('/api/sim', { inputs: CUR, ema: needEma, setups: show.setups, ds: SRC.ds, mode: SRC.mode, lab: ACTIVE_LAB, prune: typeof LF_APPLIED !== 'undefined' ? LF_APPLIED.map((c) => c.r) : [] });   // EMAs / setups only when they are needed (smooth sliding)
  if (seq !== simSeq) return false;                            // a newer change is already on its way
  while (!BARS) await new Promise((res) => setTimeout(res, 50));   // TurtleTVUHV: the UHV answer can arrive before the candles - place trades only once they are here
  if (r.error) { toast('⚠ ' + esc(r.error)); return false; }
  const keep = TT && !needEma ? { ef: TT.ef, es: TT.es } : { ef: r.ef, es: r.es };
  TT = Object.assign(derive('tt', r.events, parseFloat(CUR.InpLots || '1')), { ms: r.ms, stats: r.stats, year: r.year, rbox: r.rbox, emaKey, honest: r.honest, months: r.months, ...keep });
  if (BARS) { drawEmas(); redraw(); }
  renderAll();
  await pickMt5();
  $('#simMs').textContent = `· Turtle TV Tester ${r.ms} ms`;
  $('#infoTT').textContent = `${SRC.ds === 'tv' ? "TradingView's candles" : 'Blueberry MT5 candles'} · ${{ ea: 'v1.27 rules', chart: "the chart's rules", chart_blind: "TradingView's way" }[SRC.mode]} · ` +
    `${r.year.n} trades · WR ${r.year.wr}% · ${money(r.year.net)} · PF ${r.year.pf} · ${r.ms} ms`;
  labBanner();
  if (typeof lfBanner === 'function') lfBanner();
  if (BARS) {
    const n = BARS.t.length;
    if (firstView) { chart.timeScale().setVisibleLogicalRange({ from: n - 1500, to: n + 5 }); firstView = false; }
    legend(n - 1);
  }
  markForm();
  return true;
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
  let h = `<div class="dexsearch"><input id="fSearch" placeholder="🔎 search a setting…" oninput="formFilter(this.value)">
    <button class="dexbtn sm" onclick="formAll(true)">open all</button><button class="dexbtn sm" onclick="formAll(false)">close all</button></div>`;
  for (const [g, list] of groups) {
    const nChg = list.filter((i) => !same(CUR[i.name] ?? i.default, DFL[i.name])).length;
    h += `<details class="igrp dexsec" open><summary><span>${esc(g).toUpperCase()}</span><span class="dexcount">${list.length}${nChg ? ` · <b class="chgn">${nChg} CHANGED</b>` : ''}</span></summary>`;
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
    h += '</details>';
  }
  $('#form').innerHTML = h;
  markForm();
}
function formFilter(q) {                                  // search: only the settings whose name or comment matches stay
  q = q.trim().toLowerCase();
  document.querySelectorAll('#form .igrp').forEach((g) => {
    let any = false;
    g.querySelectorAll('.inp').forEach((r) => { const hit = !q || r.title.toLowerCase().includes(q); r.style.display = hit ? '' : 'none'; any = any || hit; });
    g.style.display = any ? '' : 'none'; if (q) g.open = true;
  });
}
function formAll(open) { document.querySelectorAll('#form .igrp').forEach((g) => { g.open = open; }); }
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
  if (e.target.closest && e.target.closest('#form')) settingsTouched = true;
  if (e.target.classList && e.target.classList.contains('riskGroup')) {
    RISK_GROUPS = [...document.querySelectorAll('.riskGroup:checked')].map((x) => x.value);
  }
  if (e.target.id === 'riskAuto') {
    RISK_AUTO = e.target.checked;
    try { localStorage.setItem('riskAuto', RISK_AUTO ? '1' : '0'); } catch (error) {}
  }
  if (e.target.dataset && e.target.dataset.riskSlider) {
    CUR[e.target.dataset.riskSlider] = e.target.value;
    settingsTouched = true;
    markForm();
    scheduleSim(0);
    renderPanel('tt');
  }
  const b = e.target.dataset && e.target.dataset.band;
  if (b) { const key = 'InpBands' + b[0], i = +b.slice(1), s = (CUR[key] || '').padEnd(21, '1').split(''); s[i] = e.target.checked ? '1' : '0'; setBands(key, s.join('')); }
  if (e.target.id === 'oObj') OPTUI.obj = e.target.value;
  if (e.target.id === 'oBox') OPTUI.boxes = e.target.checked;
  if (e.target.id === 'oKeep') OPTUI.keep = e.target.checked;
});
$('#form').addEventListener('input', (e) => {
  const el = e.target, n = el.dataset.n || el.dataset.r;
  if (!n || el.value === '') return;
  settingsTouched = true;
  CUR[n] = el.value.trim();
  const twin = el.dataset.r ? el.parentElement.querySelector('[data-n]') : el.parentElement.querySelector('[data-r]');
  if (twin) twin.value = CUR[n];
  el.closest('.inp').classList.toggle('chg', !same(CUR[n], DFL[n]));
  scheduleSim(el.dataset.r ? 60 : 120);
});
document.addEventListener('input', (e) => {
  const el = e.target;
  const name = el.dataset && el.dataset.riskSlider;
  if (!name || el.value === '') return;
  CUR[name] = el.value;
  settingsTouched = true;
  const out = document.getElementById(`riskValue_${name}`);
  if (out) {
    const value = el.value;
    out.textContent = name === 'InpSlMode' ? `${value} · ${['fixed pips', 'ATR distance', 'price distance'][Number(value)]}` :
      name === 'InpRiskPct' || name === 'InpDayLossPct' ? `${value}%` :
        name === 'InpLots' ? `${Number(value).toFixed(2)} lots` : value;
  }
});
document.addEventListener('change', (e) => {
  if (e.target && e.target.dataset && e.target.dataset.riskSlider) scheduleSim(0);
});
async function setSource() {
  const ds = $('#srcDs').value, mode = $('#srcMode').value, keep = chart.timeScale().getVisibleRange();
  SRC.mode = mode;
  $('#brandTf').textContent = "EURUSD · PrimeXBT ticks · 1 min";
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
  updateReportButton();
  renderSaved();
  resumeExportProgress();
}
function updateReportButton() {
  const button = $('#btnReport');
  if (!button) return;
  const run = MT && MT.matches && RUNS.find((x) => x.id === MT.run.id && x.has_report);
  button.disabled = !run;
  button.title = run ? `Download the MT5 Strategy Tester HTML report for ${run.label} (${run.period || 'M15'})`
    : 'Select settings with a completed MT5 run and an available tester report';
}
function runMatches(r) {
  const a = r.changed || {}, b = diffDfl(CUR);
  return (r.period || 'M15') === mt5Period() &&
    Object.keys(a).length === Object.keys(b).length && Object.entries(b).every(([k, v]) => k in a && same(a[k], v));
}
async function pickMt5(forceId) {
  if (!RUNS.length) { MT = null; updateReportButton(); renderPanel('mt'); return; }
  const want = forceId || (RUNS.find(runMatches) || {}).id || (MT && MT.run.id) || RUNS[0].id;
  if (!MT || MT.run.id !== want) {
    const run = await api('/api/run?id=' + encodeURIComponent(want));
    MT = Object.assign(derive('mt', run.events, parseFloat(run.inputs.InpLots || '1')), { run });
  }
  const diff = {};
  for (const [k, v] of Object.entries(MT.run.inputs)) if (k in CUR && !same(v, CUR[k])) diff[k] = [CUR[k], v];
  MT.diff = diff; MT.matches = !Object.keys(diff).length && (MT.run.period || 'M15') === mt5Period();
  updateReportButton();
  $('#runSel').value = MT.run.id;
  const s = stats(MT.TR);
  $('#infoMT').innerHTML = MT.matches ? `${s.n} trades · WR ${pct(s.w, s.n)} · ${money(MT.run.report.net ?? s.net)} · PF ${MT.run.report.pf}` : '<span class="warn">⚠ different settings or timeframe from the screen</span>';
  renderPanel('mt'); redraw();
}
async function poll() {
  try {
    const s = await api('/api/status');
    $('#btnCheck').disabled = !!s.busy || EXPORT_BUSY || !!EXPORT_PENDING;
    $('#btnExport').disabled = !!s.busy || EXPORT_BUSY || !!EXPORT_PENDING;
    if (s.busy) setStatus(`MT5 running "${s.label}" · ${s.phase} · ${s.elapsed ?? 0} s`, 'busy');
    else if (s.error) setStatus('last MT5 run failed: ' + s.error, 'err');
    else setStatus('');
    if (MTWAIT && s.busy) { MTWAIT.phase = `${s.phase} · ${s.elapsed ?? 0} s`; renderPanel('mt'); }
    if (MTWAIT && !s.busy && s.error && Date.now() - MTWAIT.t0 > 4000) {
      if (EXPORT_PENDING) {
        EXPORT_PENDING = null;
        $('#btnExport').disabled = false;
        toast('⚠ Export stopped because the required MT5 Strategy Tester run failed: ' + esc(s.error), 14000);
      }
      MTWAIT = null; renderPanel('mt');
    }
    if (!s.busy && s.last && (s.last !== lastSeen || (MTWAIT && s.last !== MTWAIT.prev && (!MT || MT.run.id !== s.last)))) {
      const first = lastSeen === undefined && !MTWAIT; lastSeen = s.last;
      if (!first) {
        MTWAIT = null; await loadRuns(); MT = null; await pickMt5(s.last); loadSaved();
        toast(`MT5 result in: <b>${esc(MT.run.label)}</b> · ${money(MT.run.report.net || 0)} · PF ${MT.run.report.pf}`);
        if (EXPORT_PENDING && EXPORT_PENDING.id === s.last) await finishExportAfterTest();
      }
    }
    const busyUi = document.activeElement && document.activeElement.closest && document.activeElement.closest('#panelTT') && /SELECT|INPUT/.test(document.activeElement.tagName);
    if (!busyUi && TAB.tt === 'opt' && OPTS && (OPTS.running || (OPTS.mt5 && OPTS.mt5.run && !RUNS.find((x) => x.id === OPTS.mt5.run)))) { OPTS = await api('/api/opt'); renderPanel('tt'); }
    const riskInputFocused = document.activeElement && document.activeElement.closest &&
      document.activeElement.closest('#panelTT') && document.activeElement.matches('input[type=range], input[type=checkbox]');
    if (TAB.tt === 'risk' && RISK_OPTS && RISK_OPTS.running && !riskInputFocused) { RISK_OPTS = await api('/api/risk_opt'); renderPanel('tt'); }
  } catch (e) { setStatus('Turtle TV server not reachable', 'err'); }
  setTimeout(poll, OPTS && OPTS.running || RISK_OPTS && RISK_OPTS.running ? 700 : 2000);
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
// the primary save: loads into the chart and everywhere on every page start (Zee 2026-10-21)
let PRIM = null;                                             // the primary save's name, from the server's settings/primary.txt (any browser)
function primName() { return PRIM; }
async function setPrim(name) { PRIM = name; await api('/api/primary', { name }); }
async function applySave(s) {
  CUR = { ...DFL, ...s.inputs };
  if (s.lab && Object.keys(s.lab).length) { if (typeof labOpen === 'function') await labOpen(); CUR = { ...CUR, ...labToX(s.lab) }; }   // an older save's lab exit: EA v1.30 settings now
  ACTIVE_LAB = null; markForm();
  if (s.lab && Object.keys(s.lab).length && typeof labOpen === 'function') { await labOpen(); LABS.form = { ...LABS.spec.default, ...s.lab }; }   // its Exit Lab exit back on the bench
}
function matchingSaveRuns(s) {
  const want = diffDfl({ ...DFL, ...s.inputs });
  return RUNS.filter((x) => { const a = x.changed || {}; return (x.period || 'M15') === mt5Period(s.ds) &&
    Object.keys(a).length === Object.keys(want).length && Object.entries(want).every(([k, v]) => k in a && same(a[k], v)); });
}
function saveRun(s) { return matchingSaveRuns(s)[0]; }           // the newest MT5 run of exactly this save's settings
function candidateRun(s) { return matchingSaveRuns(s).find((x) => x.has_candidate); }
function exportProgressMarkup(progress) {
  const stages = [
    ['preparing', 'Preparing the complete EA settings'],
    ['generating', 'Generating the separate EA source'],
    ['waiting', 'Waiting for the isolated MT5 test rig'],
    ['compiling', 'Compiling in MetaEditor'],
    ['testing', 'Testing the compiled EA in MT5 Strategy Tester'],
    ['installing', 'Installing source, binary, and preset in MT5'],
    ['ready', 'Export complete'],
  ];
  const phase = String(progress.phase || 'working');
  const index = Math.max(0, stages.findIndex(([key]) => phase.toLowerCase().includes(key)));
  const percent = Math.round((index / (stages.length - 1)) * 100);
  if (progress.error || phase === 'failed') {
    return `<div class="warn"><b>EA export failed</b><br>${esc(progress.error || 'See the Export to MT5 error notification.')}</div>`;
  }
  return `<div data-ea-export-progress="${esc(progress.id)}" class="ea-export-progress">` +
    `<b>EA generation · step ${index + 1} of ${stages.length - 1}</b>` +
    `<progress value="${percent}" max="100" style="display:block;width:100%;height:9px;margin:4px 0"></progress>` +
    `<span>${esc(phase)}</span><br><span class="k">${Math.round(progress.seconds || 0)} sec</span>` +
    `${progress.candidate ? `<br><code>${esc(progress.candidate)}</code>` : ''}</div>`;
}
function candidateCell(s, run, progress) {
  const savedExports = s.candidate_exports || [];
  const records = savedExports.length ? savedExports : run && run.candidate ? [run.candidate] : [];
  let html = '<td style="text-align:left;white-space:normal;min-width:300px">';
  if (progress) html += exportProgressMarkup(progress);
  if (!records.length) return html + (progress ? '</td>' : '<span class="k">No compiled EA recorded for this setting.</span></td>');
  html += records.map((c) => {
    const t = c.tester || {};
    const paths = (c.compiled_paths || []).map((path) => `<code style="display:block;word-break:break-all">${esc(path)}</code>`).join('');
    const presets = (c.preset_paths || []).map((path) => `<code style="display:block;word-break:break-all">${esc(path)}</code>`).join('');
    const metrics = [
      t.net != null ? `${money(Number(t.net))} net` : null,
      t.pf != null ? `PF ${esc(t.pf)}` : null,
      t.trades != null ? `${esc(t.trades)} trades` : null,
      t.wr ? `${esc(t.wr)} WR` : null,
      t.avg_win != null ? `Avg win ${money(Number(t.avg_win))}` : null,
      t.avg_loss != null ? `Avg loss ${money(Number(t.avg_loss))}` : null,
      t.dd ? `DD ${esc(t.dd)}` : null,
    ].filter(Boolean).join(' · ') || 'Tester metrics unavailable';
    const testPeriod = [c.tester_symbol, c.tester_period, c.tester_from && c.tester_to ? `${c.tester_from}–${c.tester_to}` : null]
      .filter(Boolean).map(esc).join(' · ');
    return `<div style="padding:5px 0;border-bottom:1px solid var(--line)">` +
      `<b>${esc(c.name || 'Candidate EA')} v${esc(c.version || '?')}</b><br>` +
      `<span class="k">Compiled: ${esc(c.compiled_at || 'date unavailable')}</span><br>` +
      `<b>${metrics}</b>${t.quality ? `<br><span class="k">${esc(t.quality)}</span>` : ''}` +
      `${testPeriod ? `<br><span class="k">Test: ${testPeriod}</span>` : ''}` +
      `${c.tester_deposit != null ? `<br><span class="k">Deposit: ${money(Number(c.tester_deposit))}</span>` : ''}` +
      `<br><span class="k">Compiled EA:</span>${paths || '<br><span class="k">Path unavailable</span>'}` +
      `<span class="k">Source:</span><br><code style="word-break:break-all">${esc(c.source_path || 'unavailable')}</code>` +
      (presets ? `<span class="k">Preset:</span>${presets}` : '') +
      (c.report_url ? `<br><a href="${esc(c.report_url)}" target="_blank" rel="noopener">Open MT5 tester report</a>` : '') +
      (!c.available ? '<br><span class="warn">Recorded path; compiled file is not currently present there.</span>' : '') +
      `</div>`;
  }).join('');
  return html + '</td>';
}
function updateExportProgress(id, progress) {
  EXPORT_PROGRESS = progress;
  document.querySelectorAll('[data-ea-export-progress]').forEach((element) => {
    if (element.dataset.eaExportProgress === id) element.outerHTML = exportProgressMarkup(progress);
  });
}
function resumeExportProgress() {
  const active = RUNS.find((run) => run.export_state && run.export_state.busy);
  if (!active || (EXPORT_BUSY && EXPORT_PROGRESS && EXPORT_PROGRESS.id === active.id)) return;
  const state = active.export_state;
  EXPORT_BUSY = true;
  EXPORT_PROGRESS = { ...state, id: active.id };
  $('#btnExport').disabled = true;
  clearInterval(EXPORT_TIMER);
  EXPORT_TIMER = setInterval(() => pollExport(active.id, { candidate: state.candidate }), 1800);
  pollExport(active.id, { candidate: state.candidate });
}
function mtWrCell(s) {
  const run = saveRun(s);
  if (!run || run.wr == null) return '<td class="k" title="no MT5 run of these settings yet - Watch MT5 result runs it">–</td>';
  const g = s.result && s.result.wr != null ? run.wr - s.result.wr : null;
  const dd = String(run.dd || '').split('(')[0].replace(/\s/g, '');
  return `<td style="text-align:left;white-space:normal;min-width:190px" title="MT5 ${esc(run.from)} - ${esc(run.to)} · ${run.trades} trades · ${money(run.net || 0)} · PF ${run.pf}${g != null ? ` · ${g >= 0 ? '+' : ''}${g.toFixed(1)} pts vs the portal` : ''}">` +
    `MT5 Win rate: <b>${run.wr}%</b>, Avg win: <span class="pos">${money(run.avg_win)}</span>, Avg loss: <span class="neg">${money(run.avg_loss)}</span>, Worst loss: <span class="neg">${money(run.worst)}</span>, ` +
    `Max drawdown: ${dd ? money(-Number(dd)) : '–'}, Break-even win rate: <b class="${run.be_wr != null && run.wr - run.be_wr < 10 ? 'bad' : ''}">${run.be_wr ?? '–'}%</b></td>`;
}
async function loadSaved() {
  SAVEDS = await api('/api/saved');
  renderSaved();
}
function renderSaved() {
  const dsName = { year: 'Blueberry 2026 (ticks)', tv: "TradingView's candles", m15: 'Blueberry 2023 → now' };
  $('#panelSaved').innerHTML = SAVEDS.length ? table(['Saved', 'Candles', 'Trades', 'Win rate', 'MT5 Winrate', 'Net', 'PF', 'Changes from v1.27', 'Compiled MT5 EA / final tester result', ''],
    SAVEDS.map((s, i) => { const r = s.result || {};
      const exportRun = candidateRun(s);
      const progressRun = EXPORT_PROGRESS && matchingSaveRuns(s).find((run) => run.id === EXPORT_PROGRESS.id);
      const eaButton = exportRun && exportRun.has_candidate
        ? `<button data-download-ea="${esc(exportRun.id)}" title="Download the tested source and compiled EA; open its MT5 folder">Download MT5 Compiled EA</button>`
        : '<button disabled title="Export and test this setting with the top-menu Export to MT5 button first">Download MT5 Compiled EA</button>';
      return `<tr><td>${esc(s.name)}${typeof rsBadge === 'function' ? rsBadge(s) : ''}</td><td>${esc(dsName[s.ds] || s.ds || '')}</td><td>${r.n ?? ''}</td><td>${r.wr != null ? r.wr + '%' : ''}</td>${mtWrCell(s)}<td class="${cls(r.net || 0)}">${r.net != null ? money(r.net) : ''}</td><td>${r.pf ?? ''}</td>` +
        `<td style="text-align:left;white-space:normal" class="k">${Object.entries(s.changed || {}).map(([k, v]) => `${esc(k.replace(/^Inp/, ''))}=${esc(v)}`).join(' ') || 'none (v1.27)'}${s.lab_describe ? `<br><span style="color:#ffb74d">⚗️ Exit Lab exit: ${esc(s.lab_describe)}</span>` : ''}</td>` +
        candidateCell(s, exportRun, progressRun ? EXPORT_PROGRESS : null) +
        `<td><button data-load="${i}">Load</button> <button data-del="${i}">Delete</button> ` +
        (primName() === s.name ? `<button data-unprim="1" class="dexbtn sm" title="loads on every startup - click to stop">⭐ Primary (default on startup)</button>`
          : `<button data-prim="${i}">Make Primary: Set as Default on Startup</button>`) + ` <button data-watch="${i}">Watch MT5 result</button> ${eaButton} <button data-deploy-ea="${esc(s.name)}" class="dexbtn sm" title="compile this setting into an EA and copy it to the server set on the Deploy tab" ${typeof DEP !== 'undefined' && DEP.st && DEP.st.running ? 'disabled' : ''}>🚀 Deploy EA to Server</button>${typeof depStatusLine === 'function' ? depStatusLine(s.name) : ''}</td></tr>`; }))
    : '<p class="note">Nothing saved yet - press "💾 Save settings".</p>';
}

async function downloadCandidateEA(id) {
  const response = await fetch('/api/export_package?id=' + encodeURIComponent(id));
  if (!response.ok) {
    let message = 'Could not download the compiled EA.';
    try { const body = await response.json(); message = body.error || message; } catch (e) { /* keep the explicit default error */ }
    throw new Error(message);
  }
  const blob = await response.blob(), url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `Saad_strategy_15min_TurtleTV_${id}.zip`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return response.headers.get('X-EA-Location');
}

$('#btnSave').onclick = async () => {
  const r = await api('/api/save', { inputs: CUR, ds: SRC.ds, mode: SRC.mode, result: TT ? TT.year : null });
  await loadSaved(); toast(`Saved as <b>${esc(r.name)}</b> (bottom of the page).`);
};
document.addEventListener('click', async (e) => {
  const d = e.target.dataset || {};
  if (d.downloadEa != null) {
    try {
      const location = await downloadCandidateEA(d.downloadEa);
      toast(`Downloading the <b>source + compiled EA</b>. Explorer opened at <code>${esc(location || 'the MT5 Experts folder')}</code>.`, 14000);
    } catch (error) {
      toast('⚠ ' + esc(error.message || error), 14000);
    }
  }
  if (d.load != null) {
    settingsTouched = true;
    const s = SAVEDS[+d.load]; await applySave(s); scheduleSim(0);
    toast(`Loaded <b>${esc(s.name)}</b>.` + (s.lab_describe ? ` Its Exit Lab exit is back on the bench: ${esc(s.lab_describe)}.` : ''));
  }
  if (e.target.id === 'labBannerOff') { ACTIVE_LAB = null; labBanner(); scheduleSim(0); toast('The main tester runs the EA’s own exit again.'); }
  if (d.watch != null) {                                       // the newest MT5 run of exactly this save's settings, into the MT5 Strategy Tester section
    const s = SAVEDS[+d.watch];
    await loadRuns();
    const run = saveRun(s);
    if (run) { MT = null; await pickMt5(run.id); document.querySelector('#panelMT').scrollIntoView({ behavior: 'smooth', block: 'start' });
      toast(`MT5 result for <b>${esc(s.name)}</b>: ${money(run.net || 0)} · PF ${run.pf} · ${run.trades} trades (${esc(run.created || '')}).` + (runMatches(run) ? '' : ' Its settings or timeframe differ from the chart - Load the save to compare them side by side.')); }
    else if (confirm(`MT5 has not run "${s.name}" yet. Load it and run it in MT5 now (about a minute)?`)) { await applySave(s); scheduleSim(0); $('#btnCheck').click(); }
  }
  if (d.prim != null) { const s = SAVEDS[+d.prim]; await setPrim(s.name); loadSaved();
    toast(`⭐ <b>${esc(s.name)}</b> is your primary: it loads into the chart and everywhere each time the page opens.`); }
  if (d.unprim) { await setPrim(null); loadSaved(); toast('No primary any more: the page starts from TradingView / v1.27 again.'); }
  if (d.del != null) { const s = SAVEDS[+d.del]; if (confirm(`Delete the saved settings "${s.name}"?`)) { await api('/api/saved_delete', { name: s.name }); loadSaved(); } }
});

// ---------- buttons ----------
async function requestMt5Check(inputs, period) {
  const r = await api('/api/run', { sets: inputs, delay: 'none', period,
    label: Object.keys(diffDfl(inputs)).length ? '' : 'EA defaults (no delay)' });
  if (r.error) {
    toast('⚠ ' + esc(r.error));
    return null;
  }
  MTWAIT = { prev: MT && MT.run.id, id: r.id, t0: Date.now() }; renderPanel('mt');
  toast('The settings are running in the MT5 Strategy Tester on real ticks.');
  return r.id;
}

$('#btnCheck').onclick = async () => { await requestMt5Check(CUR, mt5Period()); };
$('#btnExport').onclick = async () => {
  if (EXPORT_BUSY) return;
  if (!MT || !MT.matches) {
    const snapshot = JSON.parse(JSON.stringify(CUR));
    const period = mt5Period();
    EXPORT_PENDING = { id: null, inputs: snapshot, period };
    try {
      const started = await requestMt5Check(snapshot, period);
      if (!started) { EXPORT_PENDING = null; return; }
      EXPORT_PENDING.id = started;
      $('#btnExport').disabled = true;
      return toast('No matching completed MT5 run was selected. Running these settings first; the compiled EA export will continue automatically when that test finishes.', 30000);
    } catch (error) {
      EXPORT_PENDING = null;
      $('#btnExport').disabled = false;
      toast('⚠ Could not start the required MT5 test: ' + esc(error.message || error), 14000);
      return;
    }
  }
  await startExport(MT.run.id);
};

async function finishExportAfterTest() {
  const pending = EXPORT_PENDING;
  EXPORT_PENDING = null;
  if (JSON.stringify(CUR) !== JSON.stringify(pending.inputs) || mt5Period() !== pending.period || !MT || !MT.matches) {
    $('#btnExport').disabled = false;
    toast('Export stopped: chart settings or timeframe changed while MT5 was testing. Check the current settings again before exporting.', 14000);
    return;
  }
  await startExport(MT.run.id);
}

async function startExport(id) {
  if (EXPORT_BUSY) return;
  EXPORT_BUSY = true;
  $('#btnExport').disabled = true;
  EXPORT_PROGRESS = { id, busy: true, phase: 'preparing the complete production EA settings', seconds: 0 };
  renderSaved();
  try {
    const r = await api('/api/export', { id });
    if (r.error) throw new Error(r.error);
    updateExportProgress(id, { id, candidate: r.candidate, busy: true, phase: 'preparing the complete production EA settings', seconds: 0 });
    toast(`<b>EA export started.</b> <code>${esc(r.candidate)}.mq5</code> is being generated, compiled, and tested in MT5 Strategy Tester before it is copied to MT5.`, 30000);
    clearInterval(EXPORT_TIMER);
    EXPORT_TIMER = setInterval(() => pollExport(id, r), 1800);
    await pollExport(id, r);
  } catch (error) {
    EXPORT_BUSY = false;
    $('#btnExport').disabled = false;
    updateExportProgress(id, { id, phase: 'failed', error: error.message || String(error) });
    toast('⚠ EA export failed: ' + esc(error.message || error), 14000);
  }
};

async function pollExport(id, started) {
  if (!EXPORT_BUSY) return;
  try {
    const state = await api('/api/export_status?id=' + encodeURIComponent(id));
    if (state.error && !state.phase) throw new Error(state.error);
    if (state.busy) {
      updateExportProgress(id, { ...state, id });
      toast(`<b>EA export · ${esc(state.phase || 'working')}</b><br>${esc(started.candidate)} · ${Math.round(state.seconds || 0)} sec`, 30000);
      return;
    }
    clearInterval(EXPORT_TIMER);
    EXPORT_BUSY = false;
    $('#btnExport').disabled = false;
    if (state.error) {
      updateExportProgress(id, { ...state, id, phase: 'failed' });
      throw new Error(state.error);
    }
    EXPORT_PROGRESS = null;
    const result = state.result, metrics = result.tester || {};
    let refreshWarning = '';
    try { await loadRuns(); await loadSaved(); }
    catch (error) { refreshWarning = `<br><span class="warn">Saved-settings list could not refresh: ${esc(error.message || error)}</span>`; }
    const terminals = result.installed.map((path) => `<code>${esc(path)}</code>`).join('<br>');
    const warnings = result.install_errors.length ? `<br><span class="warn">Some terminals could not be updated: ${esc(result.install_errors.join('; '))}</span>` : '';
    const random = result.random_run ? (result.random_existing
      ? '<br>A random-delay MT5 run already exists for these settings.'
      : `<br>Random-delay run ${esc(result.random_run)} started.`) : '';
    toast(`<b>EA ready to attach.</b> <code>${esc(result.candidate)}.ex5</code> compiled and tested in MT5 Strategy Tester.<br>
      Candidate result: ${money(metrics.net || 0)} · PF ${esc(metrics.pf ?? '–')} · ${esc(metrics.trades ?? '–')} trades · ${esc(metrics.quality || 'MT5 report saved')}.<br>
      Installed in:<br>${terminals}${warnings}${random}${refreshWarning}<br><a href="${esc(result.report)}">Download candidate Strategy Tester report</a><br>
      Source: <code>${esc(started.json)}</code> · original preset: <code>${esc(started.preset)}</code>`, 30000);
  } catch (error) {
    clearInterval(EXPORT_TIMER);
    EXPORT_BUSY = false;
    $('#btnExport').disabled = false;
    updateExportProgress(id, { id, phase: 'failed', error: error.message || String(error) });
    toast('⚠ EA export failed: ' + esc(error.message || error), 14000);
  }
}
$('#btnReport').onclick = async () => {
  if (!MT || !MT.matches) return toast('First select settings with a completed MT5 Strategy Tester run.');
  try {
    const response = await fetch('/api/mt5_report?id=' + encodeURIComponent(MT.run.id));
    if (!response.ok) {
      const error = await response.json();
      return toast('⚠ ' + esc(error.error || 'Could not download the MT5 report.'));
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = `MT5_Strategy_Tester_${MT.run.id}.htm`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    toast('⚠ Could not download the MT5 report: ' + esc(error.message || error));
  }
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
  const previous = TAB[sec];
  if (sec === 'tt' && t === 'tp' && previous !== t && typeof TPVIEW !== 'undefined') TPVIEW.selected = null;
  TAB[sec] = t;
  if (sec === 'tt' && t === 'opt') OPTS = await api('/api/opt');
  if (sec === 'tt' && t === 'risk') {
    try {
      const [ref, state] = await Promise.all([RISK_REF ? Promise.resolve(RISK_REF) : api('/api/risk_reference'), api('/api/risk_opt')]);
      if (ref.error) throw new Error(ref.error);
      if (state.error) throw new Error(state.error);
      RISK_REF = ref; RISK_OPTS = state;
      if (state.groups && state.groups.length) RISK_GROUPS = state.groups;
      if (state.risk_inputs) RISK_SCAN_INPUTS = { ...state.risk_inputs };
    } catch (error) { toast('⚠ Risk Manager: ' + esc(error.message || error)); }
  }
  renderPanel(sec);
  if (sec === 'tt' && t === 'lab') labOpen();
  if (sec === 'tt' && t === 'ml') mlOpen();
  if (sec === 'tt' && t === 'research') resOpen();
  if (sec === 'tt' && t === 'mission') misOpen();
}));
document.addEventListener('click', async (e) => {
  const lcs = e.target.closest('[data-lcsave]');
  if (lcs) { e.stopPropagation(); lossSave(lcs.dataset.lcsave); return; }
  if (e.target.closest('input[data-lckey]')) return;                 // typing a loss comment never jumps the chart
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
    const started = await api('/api/optimize', { start: CUR, objective: $('#oObj').value, boxes: $('#oBox').checked, keep: $('#oKeep').checked, ds: SRC.ds === 'tv' ? 'year' : SRC.ds });
    if (started.error) { toast('⚠ ' + esc(started.error)); return; }
    OPTS = await api('/api/opt'); renderPanel('tt');
  }
  if (e.target.id === 'riskScan') {
    const groups = [...document.querySelectorAll('.riskGroup:checked')].map((x) => x.value);
    RISK_GROUPS = groups;
    RISK_SCAN_INPUTS = { ...CUR };
    const r = await api('/api/risk_scan', { inputs: CUR, groups, ds: SRC.ds === 'tv' ? 'year' : SRC.ds });
    if (r.error) { RISK_SCAN_INPUTS = null; toast('⚠ ' + esc(r.error)); return; }
    RISK_GROUPS = r.groups || groups;
    RISK_OPTS = await api('/api/risk_opt');
    if (RISK_OPTS.groups && RISK_OPTS.groups.length) RISK_GROUPS = RISK_OPTS.groups;
    renderPanel('tt');
  }
  if (e.target.id === 'riskStop') {
    await api('/api/risk_stop', {}); RISK_OPTS = await api('/api/risk_opt'); renderPanel('tt');
  }
  if (e.target.dataset.riskLoad) {
    if (!RISK_REF) return toast('⚠ The reference MT5 settings have not loaded yet.');
    CUR = { ...DFL, ...RISK_REF.inputs }; ACTIVE_LAB = null; settingsTouched = true; markForm();
    $('#srcDs').value = RISK_REF.period === 'M15' ? 'm15' : RISK_REF.period === 'M5' ? 'm5x' : 'year1';
    await setSource(); renderPanel('tt');
    toast(`Loaded the exact inputs from MT5 run ${esc(RISK_REF.id)} into the chart. This does not change saved settings or the EA.`);
  }
  if (e.target.dataset.riskBest && RISK_OPTS && RISK_OPTS.best) {
    if (!riskScanMatchesChart()) return toast('⚠ These suggestions are stale because the chart settings changed. Scan again first.');
    CUR = { ...DFL, ...RISK_OPTS.best.inputs }; ACTIVE_LAB = null; settingsTouched = true; markForm(); scheduleSim(0);
    toast('Applied the risk scan candidate to the chart only. Verify it in MT5 before saving or exporting.');
    if (RISK_AUTO) {
      const groups = RISK_GROUPS.length ? RISK_GROUPS : (RISK_OPTS.groups || []);
      RISK_SCAN_INPUTS = { ...CUR };
      const scan = await api('/api/risk_scan', { inputs: CUR, groups, ds: SRC.ds === 'tv' ? 'year' : SRC.ds });
      if (scan.error) { RISK_SCAN_INPUTS = null; toast('⚠ Could not rescan after the pick: ' + esc(scan.error)); return; }
      RISK_GROUPS = scan.groups || groups;
      RISK_OPTS = await api('/api/risk_opt');
      renderPanel('tt');
    }
  }
  if (e.target.dataset.riskStep != null && RISK_OPTS && RISK_OPTS.log) {
    if (!riskScanMatchesChart()) return toast('⚠ These suggestions are stale because the chart settings changed. Scan again first.');
    const step = RISK_OPTS.log[+e.target.dataset.riskStep];
    if (step && step.inputs) { CUR = { ...DFL, ...step.inputs }; ACTIVE_LAB = null; settingsTouched = true; markForm(); scheduleSim(0);
      toast('Applied this risk-scan suggestion to the chart only. Verify it in MT5 before saving or exporting.');
      if (RISK_AUTO) {
        const groups = RISK_GROUPS.length ? RISK_GROUPS : (RISK_OPTS.groups || []);
        RISK_SCAN_INPUTS = { ...CUR };
        const scan = await api('/api/risk_scan', { inputs: CUR, groups, ds: SRC.ds === 'tv' ? 'year' : SRC.ds });
        if (scan.error) { RISK_SCAN_INPUTS = null; toast('⚠ Could not rescan after the pick: ' + esc(scan.error)); return; }
        RISK_GROUPS = scan.groups || groups;
        RISK_OPTS = await api('/api/risk_opt');
        renderPanel('tt');
      } else {
        renderPanel('tt');
      }
    }
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
  setStatus('loading settings…', 'busy');
  SRC.ds = $('#srcDs').value; SRC.mode = $('#srcMode').value;
  $('#srcDs').disabled = true;
  $('#srcDs').value = SRC.ds; $('#srcMode').value = SRC.mode;
  const h = new URLSearchParams(location.hash.slice(1));
  const [inputs, saved, primary] = await Promise.all([
    api('/api/inputs'), api('/api/saved'), api('/api/primary').catch(() => ({})),
  ]);
  INPUTS = inputs;
  for (const i of INPUTS.inputs) DFL[i.name] = i.default;
  CUR = { ...DFL };
  SAVEDS = Array.isArray(saved) ? saved : [];
  PRIM = primary.name || null;
  buildForm();
  const pn = PRIM;                                       // a primary save wins over TradingView and the defaults
  if (pn) {
    const s = SAVEDS.find((x) => x.name === pn);
    if (s) {
      CUR = { ...DFL, ...s.inputs };
      if (s.lab && Object.keys(s.lab).length) CUR = { ...CUR, ...labToX(s.lab) };
      markForm(); setTimeout(() => toast(`⭐ Started from your primary settings <b>${esc(pn)}</b>.`), 500);
    }
    else await setPrim(null);
  }
  renderSaved();
  if (h.get('tab')) { TAB.tt = h.get('tab'); renderPanel('tt'); }
  if (h.get('mt')) { TAB.mt = h.get('mt'); renderPanel('mt'); }
  if (h.get('ask') === '1') document.body.classList.add('ask-open');
  poll();

  (async () => {
    try {
      const tv = await Promise.race([api('/api/tv'), new Promise((_, rej) => setTimeout(() => rej(new Error('slow')), 15000))]);
      if (!PRIM && !settingsTouched && tv && tv.sets) {
        CUR = { ...DFL, ...tv.sets }; tvKey = JSON.stringify(tv.sets);
        $('#tvDot').className = 'dot ok'; $('#tvDot').title = `TradingView ${tv.symbol} · read at ${tv.at}`; markForm();
        scheduleSim(0);
      }
    } catch (e) { /* TradingView not open: use the defaults or primary save */ }
  })();

  setStatus('loading the candles…', 'busy');
  const simTask = runSim();
  let bars;
  try {
    bars = await getBars(SRC.ds);
  } catch (e) {
    $('#srcDs').disabled = false;
    setStatus('chart data failed to load: ' + (e.message || e), 'err');
    toast('⚠ Chart data failed to load: ' + esc(e.message || e));
    return;
  }
  BARS = bars; drawBars();
  $('#srcDs').disabled = false;
  try { await simTask; } catch (e) { /* retried below */ }
  if (!TT) await runSim();                                   // TurtleTVUHV: the first call can stall during start-up - ask once more
  if (TT && firstView) {
    drawEmas(); redraw();
    const n = BARS.t.length;
    chart.timeScale().setVisibleLogicalRange({ from: n - 1500, to: n + 5 }); firstView = false;
    legend(n - 1);
  }
  if (h.get('trade')) { const t = TT.TR.find((x) => x.num === +h.get('trade')); if (t) focusTrade(t); }
  setStatus('');
  loadRuns().then(async () => { await pickMt5(); });
})();
