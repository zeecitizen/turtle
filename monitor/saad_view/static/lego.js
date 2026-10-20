// Turtle TV Tester - Strategy Lego (monitor/saad_view/lego.py). Zee 2026-10-21: "we work on the core fundamentals of the strategy visually. it explains
// how we find a maribuzu. let's us replace the maribuzu. or which emas we consider ... like a lego builder for our strategy".
'use strict';
const LEGO = { sel: 'candle', lego: { ma: 'ema', loc: 'ea', candle: 'ea', loc_k: 0.5, mom_body: 0.6, mom_atr: 1.0 }, sets: {}, res: null, busy: false };
const LV = (k) => (k in LEGO.sets ? LEGO.sets[k] : CUR[k]);          // a value with the brick's changes on top
const onoff = (k) => !['false', '0', ''].includes(String(LV(k)).toLowerCase());
function brickList() {
  const L = LEGO.lego, f = LV('InpEmaFast'), s = LV('InpEmaSlow');
  const shapes = [['InpUsePin', 'pin bar'], ['InpHammer', 'hammer'], ['InpStar', 'shooting star'], ['InpMarubozu', 'marubozu']].filter(([k]) => onoff(k)).map(([, n]) => n);
  return [
    { id: 'ma', color: '#e53935', title: '1 · THE LINES', now: `${L.ma.toUpperCase()} ${f} / ${s}`, lab: L.ma !== 'ema' },
    { id: 'loc', color: '#fb8c00', title: '2 · WHERE', now: L.loc === 'ea' ? 'candle touches the EMA' : { near_fast: 'near the fast line', near_slow: 'near the slow line', trend: 'trend side only', any: 'anywhere' }[L.loc], lab: L.loc !== 'ea' },
    { id: 'candle', color: '#fdd835', title: '3 · THE CANDLE', now: L.candle === 'ea' ? (shapes.join(', ') || 'no shape on!') : { ea_engulf: 'EA shapes + engulfing', engulfing: 'engulfing', inside: 'inside bar', outside: 'outside bar', momentum: 'momentum candle', any: 'any candle' }[L.candle], lab: L.candle !== 'ea' },
    { id: 'filters', color: '#43a047', title: '4 · FILTERS', now: [+LV('InpAdxMin') ? `ADX ≥ ${LV('InpAdxMin')}` : 'no ADX', (LV('InpBandsB') + LV('InpBandsS')).includes('0') ? 'range boxes' : 'no boxes', `${LV('InpSessFrom')}-${LV('InpSessTo')}h`].join(' · ') },
    { id: 'trigger', color: '#1e88e5', title: '5 · THE TRIGGER', now: { 0: `break by ${LV('InpBreakPips') / 10}$ in ${LV('InpBreakBars')} candle(s)`, 1: 'dip after the break', 2: 'liquidity sweep' }[String(LV('InpEntryMode'))] },
    { id: 'stop', color: '#8e24aa', title: '6 · THE STOP', now: { 1: `${LV('InpSlAtrMult')} × ATR`, 2: `$${LV('InpSlUsd')}`, 0: `setup candle + $${LV('InpSlPips') / 10}` }[String(LV('InpSlMode'))] + (+LV('InpMaxRiskUsd') ? ` (max $${LV('InpMaxRiskUsd')})` : '') },
    { id: 'exit', color: '#546e7a', title: '7 · THE EXIT', now: { 0: 'v1.23 TP1 + trail', 1: 'next EMA beyond the entry', 2: 'close across the slow EMA' }[String(LV('InpExitMode'))] },
  ];
}
function brickSvg(b, on) {
  const studs = [18, 48, 78, 108].map((x) => `<rect x="${x}" y="2" width="20" height="9" rx="3" fill="${b.color}" stroke="rgba(0,0,0,.35)"/>`).join('');
  return `<svg viewBox="0 0 146 84" class="brick ${on ? 'on' : ''}" data-brick="${b.id}">${studs}<rect x="2" y="9" width="142" height="72" rx="8" fill="${b.color}" stroke="rgba(0,0,0,.45)" stroke-width="2"/>` +
    `<text x="73" y="30" class="bt">${b.title}</text><foreignObject x="6" y="36" width="134" height="44"><div xmlns="http://www.w3.org/1999/xhtml" class="bn">${esc(b.now)}</div></foreignObject>` +
    (b.lab ? '<rect x="96" y="12" width="44" height="13" rx="6" fill="#111"/><text x="118" y="22" class="btag">LAB</text>' : '') + '</svg>';
}
function candleSvg(kind) {                                          // a little picture of each setup candle (a BUY version)
  const C = { pin: [30, 34, 12, 64, 'pin bar: tiny body on top, long lower wick'], hammer: [26, 34, 10, 66, 'hammer: lower wick ≥ 2.5× the body'], maru: [14, 66, 10, 70, 'marubozu: almost all body'],
    star: [56, 64, 14, 68, 'shooting star (a SELL): long upper wick'], engulf: [20, 68, 16, 70, 'engulfing: the body swallows the last one'], inside: [36, 52, 30, 58, 'inside bar: inside the last candle'] }[kind];
  const [bt, bb, wt, wb, tip] = C;
  const red = kind === 'star';
  let s = `<svg viewBox="0 0 60 80" width="46" height="62" class="dx" data-tip="${esc(tip)}">`;
  if (kind === 'engulf' || kind === 'inside') s += kind === 'engulf' ? '<rect x="8" y="30" width="12" height="26" fill="#ef5350"/><line x1="14" x2="14" y1="24" y2="62" stroke="#ef5350"/>' : '<rect x="8" y="14" width="14" height="52" fill="#26a69a" opacity=".6"/><line x1="15" x2="15" y1="8" y2="72" stroke="#26a69a"/>';
  const x = kind === 'engulf' || kind === 'inside' ? 34 : 24;
  return s + `<line x1="${x + 6}" x2="${x + 6}" y1="${wt}" y2="${wb}" stroke="${red ? '#ef5350' : '#26a69a'}" stroke-width="2"/><rect x="${x}" y="${bt}" width="12" height="${bb - bt}" fill="${red ? '#ef5350' : '#26a69a'}"/></svg>`;
}
function opt(name, value, label, cur) { return `<label class="lopt ${String(cur) === String(value) ? 'on' : ''}"><input type="radio" name="${name}" value="${value}" ${String(cur) === String(value) ? 'checked' : ''} data-lg="${name}"> ${label}</label>`; }
function tog(k, label) { return `<label class="lopt ${onoff(k) ? 'on' : ''}"><input type="checkbox" data-lgs="${k}" ${onoff(k) ? 'checked' : ''}> ${label}</label>`; }
function num(k, label, step) { return `<label class="lopt">${label} <input type="number" data-lgn="${k}" value="${LV(k)}" step="${step}" style="width:70px"></label>`; }
function legoPanel() {
  const L = LEGO.lego, b = LEGO.sel;
  if (b === 'ma') return `<h4>The lines that define the trend and the location</h4><p class="note">The EA watches two moving averages of the 15-minute closes. A setup must sit on one of them (piece 2), and the exit aims at them (piece 7).</p>` +
    opt('ma', 'ema', 'EMA - exponential, the EA’s (recent candles count more)', L.ma) + opt('ma', 'sma', 'SMA - simple average <span class="tag lab">lab</span>', L.ma) + opt('ma', 'wma', 'WMA - weighted average <span class="tag lab">lab</span>', L.ma) +
    `<div class="bar">${num('InpEmaFast', 'fast line length', 1)} ${num('InpEmaSlow', 'slow line length', 1)}</div>`;
  if (b === 'loc') return `<h4>Where the setup candle must be</h4><p class="note">The EA's rule: a BUY setup candle touches the fast or slow EMA (InpLongRule ${LV('InpLongRule')}), a SELL setup touches the ${{ 0: 'slow', 1: 'fast', 2: 'fast or slow' }[String(LV('InpShortLine'))]} EMA, within ${LV('InpTouchPips') / 10}$ (InpTouchPips).</p>` +
    opt('loc', 'ea', 'On an EMA (the EA’s rule)', L.loc) + opt('loc', 'near_fast', 'Near the fast line, within k × ATR <span class="tag lab">lab</span>', L.loc) + opt('loc', 'near_slow', 'Near the slow line, within k × ATR <span class="tag lab">lab</span>', L.loc) +
    opt('loc', 'trend', 'Trend side only: BUY above the slow line, SELL below <span class="tag lab">lab</span>', L.loc) + opt('loc', 'any', 'Anywhere: no location rule <span class="tag lab">lab</span>', L.loc) +
    `<label class="lopt">k = <input type="number" data-lgk="loc_k" value="${L.loc_k}" step="0.1" style="width:60px"> ATR</label>`;
  if (b === 'candle') return `<h4>How the EA finds its setup candle</h4><div class="row" style="gap:12px">${['pin', 'hammer', 'maru', 'star', 'engulf', 'inside'].map(candleSvg).join('')}</div>
    <p class="note"><b>Pin bar</b>: body ≤ ${LV('InpBodyMax')} of the range, the long wick ≥ ${LV('InpWickMin')} of it, the other wick (the nose) ≤ ${LV('InpNoseMax')}.
    <b>Hammer / shooting star</b>: the long wick ≥ ${LV('InpHamRatio')} × the body, the nose ≤ ${LV('InpHamNose')} of the range. <b>Marubozu</b>: body ≥ ${LV('InpMaruBody')} of the range.
    Every shape needs a range ≥ ${LV('InpMinRangeAtr')} × ATR. Hover a candle for its picture's meaning.</p>
    <div class="bar">${tog('InpUsePin', 'pin bar')} ${tog('InpHammer', 'hammer')} ${tog('InpStar', 'shooting star')} ${tog('InpMarubozu', 'marubozu')}</div>
    <div class="bar">${num('InpBodyMax', 'pin body ≤', 0.05)} ${num('InpWickMin', 'pin wick ≥', 0.05)} ${num('InpNoseMax', 'nose ≤', 0.05)} ${num('InpMaruBody', 'marubozu body ≥', 0.05)} ${num('InpMinRangeAtr', 'range ≥ ATR ×', 0.05)}</div>
    <h4>…or replace the whole piece</h4>` + Object.entries({ ea: 'The EA’s shapes (above)', ea_engulf: 'The EA’s shapes + engulfing', engulfing: 'Engulfing only', inside: 'Inside bar (breaks either way)',
      outside: 'Outside bar', momentum: 'Momentum candle: body ≥ 60% of the range and range ≥ 1 ATR', any: 'Any candle (its colour gives the side)' }).map(([v, l]) => opt('candle', v, l + (v === 'ea' ? '' : ' <span class="tag lab">lab</span>'), L.candle)).join('');
  if (b === 'filters') return `<h4>Filters: a setup must pass all of these</h4><div class="bar">${num('InpAdxMin', 'ADX ≥ (0 = off)', 1)} ${num('InpSessFrom', 'trade from hour', 1)} ${num('InpSessTo', 'until hour', 1)}</div>
    <div class="bar"><label class="lopt"><input type="checkbox" data-lgbox="1" ${(LV('InpBandsB') + LV('InpBandsS')).includes('0') ? 'checked' : ''}> range boxes on (unticked boxes: stand aside)</label>
    ${tog('InpSkipBothEma', 'skip a candle that touches both EMAs')} ${tog('InpTrendAlign', 'fast above slow for a BUY')} ${tog('InpPriceSide', 'close on the trend side of the slow EMA')}</div>`;
  if (b === 'trigger') return `<h4>What fires the entry after the setup candle</h4>` + opt('ent', 0, 'Break of its high (BUY) / low (SELL)', LV('InpEntryMode')) + opt('ent', 1, 'Wait for a dip after the break', LV('InpEntryMode')) + opt('ent', 2, 'Liquidity sweep, then the break', LV('InpEntryMode')) +
    `<div class="bar">${num('InpBreakPips', 'break by (pips)', 1)} ${num('InpBreakBars', 'within candles', 1)}</div>`;
  if (b === 'stop') return `<h4>The first stop (1R)</h4>` + opt('slm', 1, 'ATR multiple', LV('InpSlMode')) + opt('slm', 2, 'Fixed $', LV('InpSlMode')) + opt('slm', 0, 'Beyond the setup candle', LV('InpSlMode')) +
    `<div class="bar">${num('InpSlAtrMult', '× ATR', 0.1)} ${num('InpSlUsd', '$', 1)} ${num('InpSlPips', 'candle + pips', 1)} ${num('InpMaxRiskUsd', 'skip if stop > $', 1)}</div>`;
  return `<h4>The exit</h4>` + opt('exm', 1, 'Next EMA beyond the entry (mode 1)', LV('InpExitMode')) + opt('exm', 2, 'Close back across the slow EMA (mode 2)', LV('InpExitMode')) + opt('exm', 0, 'v1.23 exits (mode 0)', LV('InpExitMode')) +
    `<p><button data-legoexit="1">Open the Exit Lab for everything else</button></p>`;
}
function pLego() {
  const bricks = brickList(), R = LEGO.res, labUsed = bricks.some((b) => b.lab);
  let h = `<div class="lab dex"><h3 class="dexh">🧱 DEXTER'S STRATEGY LEGO WORKSHOP</h3><p class="note"><b>Strategy Lego.</b> The strategy taken apart into its pieces. Click a brick to see how it works and to change it or swap it for another piece.
    <span class="tag lab">LAB</span> pieces are not in the EA yet (the tester runs them, MT5 cannot). Everything else here is the EA's own inputs.</p>
    <div class="legorow">${bricks.map((b, i) => brickSvg(b, b.id === LEGO.sel) + (i < bricks.length - 1 ? '<span class="arrowr">➜</span>' : '')).join('')}</div>
    <div class="dexpanel">${legoPanel()}</div><div class="bar"><button id="legoGo" class="dexbtn" ${LEGO.busy ? 'disabled' : ''}>${LEGO.busy ? '⏳ BUILDING…' : '🧱 BUILD &amp; TEST'}</button>
    <button id="legoReset">Back to the EA</button><button id="legoFly" class="dexbtn">🚀 FLY IT IN MISSION CONTROL</button>${!labUsed && Object.keys(LEGO.sets).length ? '<button id="legoApply">Apply to the chart</button>' : ''}</div>`;
  if (R) {
    const [LA, LB] = R.labels, a = R.lego, y = R.yours, row = (n, s) => `<tr><td class="l">${n}</td><td class="${cls(s.train.net)}">${money(s.train.net)} · ${s.train.wr}%</td><td class="${cls(s.test.net)}">${money(s.test.net)} · ${s.test.wr}%</td><td><b>${money(s.total)}</b></td><td>${s.all.wr}%</td><td>${s.all.n}</td><td>${s.all.pf}</td><td>${money(-s.all.dd)}</td><td>${money(s.sides.BUY.net)} / ${money(s.sides.SELL.net)}</td></tr>`;
    h += table(['', LA, LB, 'Total', 'WR', 'Trades', 'PF', 'Max DD', 'BUY / SELL'], [row('The EA (yours)', y), row('<b>This build</b>', a)]) +
      `<p class="note">${a.train.net > y.train.net && a.test.net > y.test.net ? '<span class="good">✓ better than yours in both halves.</span>' : '<span class="warn">not better in both halves.</span>'} ${R.ds === 'm15' ? '4 years' : '2026'} · Python: a hypothesis until MT5.</p>`;
  }
  return h + '</div>';
}
async function legoRun() {
  LEGO.busy = true; renderPanel('tt');
  LEGO.res = await api('/api/lego_test', { inputs: CUR, sets: LEGO.sets, lego: LEGO.lego, ds: SRC.ds === 'tv' ? 'year' : SRC.ds }).catch((e) => ({ error: String(e) }));
  LEGO.busy = false;
  if (LEGO.res.error) { toast('⚠ ' + esc(LEGO.res.error)); LEGO.res = null; }
  renderPanel('tt');
}
document.addEventListener('click', (e) => {
  const br = e.target.closest && e.target.closest('[data-brick]');
  if (br) { LEGO.sel = br.dataset.brick; renderPanel('tt'); return; }
  if (e.target.id === 'legoGo') legoRun();
  if (e.target.id === 'legoFly') { CUR = { ...CUR, ...LEGO.sets }; LEGO.sets = {}; markForm(); scheduleSim(0); MIS.lego = { ...LEGO.lego }; TAB.tt = 'mission'; renderPanel('tt'); toast('The build is in Mission Control (its EA settings are on the chart): press LAUNCH.'); }
  if (e.target.id === 'legoReset') { LEGO.lego = { ma: 'ema', loc: 'ea', candle: 'ea', loc_k: 0.5, mom_body: 0.6, mom_atr: 1.0 }; LEGO.sets = {}; LEGO.res = null; renderPanel('tt'); }
  if (e.target.id === 'legoApply') { CUR = { ...CUR, ...LEGO.sets }; LEGO.sets = {}; markForm(); scheduleSim(0); toast('The EA settings from the bricks are on the chart.'); }
  if (e.target.dataset && e.target.dataset.legoexit) { TAB.tt = 'lab'; renderPanel('tt'); labOpen(); }
});
document.addEventListener('change', (e) => {
  const d = e.target.dataset || {};
  if (!(d.lg || d.lgs || d.lgn || d.lgk || d.lgbox)) return;
  if (d.lg === 'ma' || d.lg === 'loc' || d.lg === 'candle') LEGO.lego[d.lg] = e.target.value;
  if (d.lg === 'ent') LEGO.sets.InpEntryMode = e.target.value;
  if (d.lg === 'slm') LEGO.sets.InpSlMode = e.target.value;
  if (d.lg === 'exm') LEGO.sets.InpExitMode = e.target.value;
  if (d.lgs) LEGO.sets[d.lgs] = e.target.checked ? 'true' : 'false';
  if (d.lgn) LEGO.sets[d.lgn] = e.target.value;
  if (d.lgk) LEGO.lego[d.lgk] = +e.target.value;
  if (d.lgbox) { if (e.target.checked) { delete LEGO.sets.InpBandsB; delete LEGO.sets.InpBandsS; } else { LEGO.sets.InpBandsB = '1'.repeat(21); LEGO.sets.InpBandsS = '1'.repeat(21); } }
  renderPanel('tt'); legoRun();
});
