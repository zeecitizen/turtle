// Turtle TV Exit Lab - the drawing: YOUR exit next to the exit being tried.
// Zee 2026-10-21: "a diagramatic representation of 2 exits ... themed like Dexter DD Laboratory ... hover to see explanation of diff parts of the exit"
'use strict';
function exitParts(ea, lab) {                                     // what closes a trade, as drawable parts (R = entry-to-stop distance)
  const P = [], L = lab || {}, n = (k) => Number(L[k] || 0), m = String(ea.InpExitMode), mode = lab && m === '0' ? '1' : m;
  const sl = String(ea.InpSlMode) === '1' ? `${ea.InpSlAtrMult} x ATR from the entry` : String(ea.InpSlMode) === '2' ? `$${ea.InpSlUsd} from the entry` : `beyond the setup candle + $${(+ea.InpSlPips / 10)}`;
  P.push({ t: 'stop', r: -1, label: 'STOP -1R', tip: `The first stop: ${sl}. This distance is "1R".${+ea.InpMaxRiskUsd ? ` A setup whose stop would be more than $${ea.InpMaxRiskUsd} away is not traded.` : ''}` });
  P.push({ t: 'entry', r: 0, label: 'ENTRY', tip: "The break of the setup candle's high (BUY) or low (SELL). Drawn for a BUY; a SELL is the mirror image." });
  const tgt = n('tgt');
  if (tgt >= 2) P.push({ t: 'target', r: tgt === 2 ? n('tgt_k') : 2, label: tgt === 2 ? `TARGET ${n('tgt_k')}R` : tgt === 3 ? `TARGET ${n('tgt_k')} ATR` : `TARGET $${n('tgt_k')}`, tip: 'A fixed take-profit: the whole trade closes when price gets there.' });
  else if (tgt === 1) P.push({ t: 'none', label: 'NO TARGET', tip: 'No take-profit: a trail, a time limit, a close-based rule or the stop ends the trade.' });
  else if (mode === '1') P.push({ t: 'ema', label: 'NEXT EMA BEYOND', tip: 'Exit mode 1: the target is the nearer EMA beyond the entry (chosen at entry from the live EMAs). The whole trade closes when price touches it.' });
  else if (mode === '2') P.push({ t: 'closeslow', label: 'OUT: CLOSE ACROSS SLOW EMA', tip: 'Exit mode 2: no target - out after a 15-minute candle CLOSES back across the slow EMA.' });
  else P.push({ t: 'target', r: 1.6, label: 'TP1 + TRAIL (v1.23)', tip: 'Exit mode 0, the v1.23 exits: TP1 at the exit EMA / last support, a partial close, then a trail. The tester and MT5 disagree on these.' });
  if (+ea.InpFixTpPips > 0) P.push({ t: 'target', r: 1.4, label: `FIXED TP $${ea.InpFixTpPips / 10}`, tip: `InpFixTpPips: every order carries a broker take-profit $${ea.InpFixTpPips / 10} from the entry.` });
  if (mode === '1' && tgt === 0) {
    const fb = n('fb');
    P.push({ t: 'chip', label: fb === 2 ? 'NO EMA BEYOND? NO FALLBACK' : `NO EMA BEYOND? CLOSE ACROSS ${fb === 1 ? 'SLOW' : 'FAST'} EMA${n('fb_buf') ? ` +${n('fb_buf')}ATR` : ''}${n('fb_n') > 1 ? ` x${n('fb_n')}` : ''}`,
      tip: fb === 2 ? 'When no EMA lies beyond the entry, only the stop (or the other rules) closes the trade.'
        : `The fallback: when BOTH EMAs are on the wrong side at the entry there is no target, so the trade closes after a candle closes back across the ${fb === 1 ? 'slow' : 'fast'} EMA${n('fb_buf') ? ` by at least ${n('fb_buf')} x ATR` : ''}${n('fb_n') > 1 ? `, ${n('fb_n')} closes in a row` : ''}.` });
  }
  if (n('p1_r')) P.push({ t: 'partial', r: n('p1_r'), label: `${Math.round(100 * n('p1_frac'))}% OFF @${n('p1_r')}R`, tip: `A partial close: ${Math.round(100 * n('p1_frac'))}% of the trade closes at +${n('p1_r')}R${n('p1_be') ? ', then the stop moves to the entry' : ''}; the rest runs on.` });
  if (n('p2_r')) P.push({ t: 'partial', r: n('p2_r'), label: `${Math.round(100 * n('p2_frac'))}% OFF @${n('p2_r')}R`, tip: `A second partial close: ${Math.round(100 * n('p2_frac'))}% at +${n('p2_r')}R.` });
  if (n('be_r')) P.push({ t: 'be', r: n('be_r'), label: `BREAKEVEN @${n('be_r')}R`, tip: `Once the trade has been +${n('be_r')}R in profit, the stop jumps to the entry${n('be_off') ? ` + ${n('be_off')}R` : ''}: from then on it cannot lose.` });
  if (n('lock_r')) P.push({ t: 'lock', r: n('lock_r'), label: `LOCK LADDER ${n('lock_r')}R`, tip: `Every ${n('lock_r')}R of profit the stop climbs one step: at +${n('lock_r')}R to the entry, at +${2 * n('lock_r')}R to +${n('lock_r')}R, and so on.` });
  const tr = n('tr');
  if (tr) {
    const how = { 1: `$${n('tr_k')} behind the best price`, 2: `${n('tr_k')} x ATR behind the best price`, 3: `keeping ${n('tr_k')}% of the best profit`, 4: 'under the fast EMA (moved at each close)',
      5: 'under the slow EMA (moved at each close)', 6: "under the previous candle's low", 7: `under the lowest low of ${n('tr_k')} candles`, 8: 'under the last swing low' }[tr];
    P.push({ t: 'trail', act: n('tr_act'), label: 'TRAILING STOP', tip: `A trailing stop ${how}${n('tr_act') ? `, switched on at +${n('tr_act')}R` : ''}. It only ever moves the trade's way.` });
  }
  const cx = n('cx');
  if (cx) P.push({ t: 'chip', label: 'OUT: ' + { 1: 'CLOSE ACROSS FAST EMA', 2: 'CLOSE ACROSS SLOW EMA', 3: 'EMA CROSS', 4: 'OPPOSITE SIGNAL', 5: 'ENGULFING AGAINST', 6: `${n('cx_n')} CANDLES AGAINST` }[cx],
    tip: 'A close-based exit for every trade, judged at each 15-minute close' + (n('cx_when') === 1 ? ' (only while in profit)' : n('cx_when') === 2 ? ' (only while in loss)' : '') + (n('cx_after') ? `, ignoring the first ${n('cx_after')} candles` : '') + '.' });
  if (n('max_bars')) P.push({ t: 'time', at: n('max_bars'), label: `${n('max_bars')} CANDLES: OUT`, tip: `Whatever happens, the trade closes after ${n('max_bars')} candles (${n('max_bars') / 4} hours).` });
  if (n('stale_bars')) P.push({ t: 'time', at: n('stale_bars'), label: `NOT +${n('stale_r')}R? OUT`, tip: `After ${n('stale_bars')} candles, a trade that is not at least +${n('stale_r')}R in profit is closed.` });
  if (n('adx_exit')) P.push({ t: 'chip', label: `OUT WHEN ADX < ${n('adx_exit')}`, tip: 'The trend fades: out when ADX falls below this.' });
  if (n('fri_hour')) P.push({ t: 'chip', label: `FRIDAY ${n('fri_hour')}:00: OUT`, tip: 'Nothing is held into the weekend after this hour (server time).' });
  if (+ea.InpCloseLossMins > 0) P.push({ t: 'chip', label: `LOSERS OUT ${ea.InpCloseLossMins} MIN BEFORE CLOSE`, tip: `InpCloseLossMins: ${ea.InpCloseLossMins} minutes before the daily close, a trade in loss is closed.` });
  return P;
}
function labSvg(parts, title, color) {
  const W = 470, H = 270, x0 = 36, x1 = W - 14, top = 34, bot = H - 58;
  const rmax = Math.max(2.8, ...parts.filter((p) => p.r != null).map((p) => p.r)) + 0.4, rmin = -1.4;
  const Y = (r) => top + ((rmax - r) / (rmax - rmin)) * (bot - top), X = (c) => x0 + 14 + (c / 24) * (x1 - x0 - 28);
  const path = [0, 0.25, -0.45, 0.3, 0.95, 0.6, 1.35, 1.05, 1.85, 1.45, 2.35, 1.95, 2.6].map((r, i, a) => [X((i * 24) / (a.length - 1)), r]);
  const g = (p, inner) => `<g class="dx" data-tip="${esc(p.tip)}">${inner}</g>`, ln = (y, c) => `<line x1="${x0}" x2="${x1}" y1="${y}" y2="${y}" class="lv ${c}"/>`;
  let s = `<svg viewBox="0 0 ${W} ${H}" class="dexsvg"><rect x="3" y="3" width="${W - 6}" height="${H - 6}" rx="16" class="dexbox" style="stroke:${color}"/>` +
    `<rect x="3" y="3" width="${W - 6}" height="24" rx="12" class="dexhead" style="fill:${color}"/><text x="${W / 2}" y="20" class="dext">${esc(title)}</text>` +
    [10, W - 10].map((cx) => [36, H - 10].map((cy) => `<circle cx="${cx}" cy="${cy}" r="3.2" class="rivet"/>`).join('')).join('') +
    `<polyline points="${path.map(([x, r]) => `${x},${Y(r)}`).join(' ')}" class="dexpath"/><text x="${X(3)}" y="${Y(-0.45) + 14}" class="lt pathl">··· price (a BUY)</text>`;
  for (const p of parts) {
    const y = p.r != null ? Y(p.r) : 0;
    if (p.t === 'stop') s += g(p, ln(y, 'stop') + `<text x="${x0 + 2}" y="${y + 13}" class="lt stop">☠ ${p.label}</text>`);
    else if (p.t === 'entry') s += g(p, ln(y, 'entry') + `<text x="${x0 + 2}" y="${y - 5}" class="lt entry">▶ ${p.label}</text>`);
    else if (p.t === 'target') s += g(p, ln(y, 'tgt') + `<text x="${x1 - 4}" y="${y - 5}" class="lt tgt" text-anchor="end">🎯 ${p.label}</text>`);
    else if (p.t === 'ema') s += g(p, `<path d="M${x0} ${Y(rmax - 0.3)} C ${X(8)} ${Y(rmax - 0.5)}, ${X(16)} ${Y(2.5)}, ${x1} ${Y(2.45)}" class="lv emac"/><text x="${x1 - 4}" y="${Y(2.45) - 7}" class="lt ema" text-anchor="end">🎯 ${p.label} (touch)</text>`);
    else if (p.t === 'partial') s += g(p, ln(y, 'part') + `<text x="${x1 - 4}" y="${y - 4}" class="lt part" text-anchor="end">⚗ ${p.label}</text>`);
    else if (p.t === 'be') s += g(p, `<circle cx="${X(7)}" cy="${y}" r="5" class="dotbe"/><path d="M${X(7)} ${Y(-1)} L${X(7)} ${Y(0)} L${x1} ${Y(0)}" class="lv be"/><text x="${X(7) + 7}" y="${y + 4}" class="lt be">⚡ ${p.label}</text>`);
    else if (p.t === 'lock') s += g(p, `<polyline points="${X(6)},${Y(-1)} ${X(6)},${Y(0)} ${X(12)},${Y(0)} ${X(12)},${Y(p.r)} ${X(18)},${Y(p.r)} ${X(18)},${Y(2 * p.r)} ${x1},${Y(2 * p.r)}" class="lv lock"/><text x="${X(12) + 4}" y="${Y(p.r) + 13}" class="lt lock">🪜 ${p.label}</text>`);
    else if (p.t === 'trail') {
      let best = -9;
      const pts = path.map(([x, r]) => { best = Math.max(best, r); return [x, best < Math.max(p.act, 0.01) ? -1 : Math.max(-1, best - 1)]; });
      s += g(p, `<polyline points="${pts.map(([x, r]) => `${x},${Y(r)}`).join(' ')}" class="lv trail"/><text x="${X(15)}" y="${Y(0.55)}" class="lt trail">🐍 ${p.label}</text>`);
    } else if (p.t === 'time') { const x = Math.min(x1 - 6, X(Math.min(24, p.at * 1.5))); s += g(p, `<line x1="${x}" x2="${x}" y1="${top}" y2="${bot}" class="lv time"/><text x="${x - 3}" y="${top + 12}" class="lt time" text-anchor="end">⏰ ${p.label}</text>`); }
  }
  const chips = parts.filter((p) => p.t === 'chip' || p.t === 'none' || p.t === 'closeslow');
  chips.forEach((p, i) => { const cw = (W - 30) / 2, x = 12 + (i % 2) * (cw + 6), y = bot + 16 + Math.floor(i / 2) * 17;
    s += g(p, `<rect x="${x}" y="${y - 11}" width="${cw}" height="15" rx="5" class="chip"/><text x="${x + 6}" y="${y}" class="lt chipt">🧫 ${esc(p.label.slice(0, 42))}</text>`); });
  return s + '</svg>';
}
function labDrawings() {
  const f = labForm(), lab = Object.fromEntries(Object.entries(f).filter(([k, v]) => k !== 'pess' && Number(v) !== Number(LABS.spec.default[k])));
  const same = !Object.keys(lab).length;
  return `<section class="dexlab"><h3 class="dexh">🧪 DEXTER'S EXIT LABORATORY</h3> <span class="k">hover any part of a specimen to see what it does · B follows the builder below</span>
    <div class="row" style="gap:14px;margin-top:8px">${typeof ACTIVE_LAB !== 'undefined' && ACTIVE_LAB
      ? labSvg(exitParts(CUR, { ...LABS.spec.default, ...ACTIVE_LAB }), 'SPECIMEN A: YOUR EXIT (THE EA + THE LOADED LAB EXIT)', '#26c6da')
      : labSvg(exitParts(CUR, null), 'SPECIMEN A: YOUR EXIT (THE EA ON SCREEN)', '#26c6da')}` +
    `${labSvg(exitParts(CUR, same ? null : { ...LABS.spec.default, ...f }), same ? 'SPECIMEN B: SAME AS A - PICK A TRY OR BUILD ONE' : 'SPECIMEN B: THE EXIT BEING TRIED', '#ff9800')}</div></section>`;
}
(function () {
  const tip = document.createElement('div'); tip.id = 'dexTip'; document.body.appendChild(tip);
  document.addEventListener('mousemove', (e) => {
    const gg = e.target.closest && e.target.closest('.dx');
    if (!gg) { tip.style.display = 'none'; return; }
    tip.textContent = gg.dataset.tip; tip.style.display = 'block';
    tip.style.left = Math.min(window.innerWidth - 340, e.clientX + 16) + 'px'; tip.style.top = (e.clientY + 16) + 'px';
  });
})();
