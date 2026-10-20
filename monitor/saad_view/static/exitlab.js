// Turtle TV - the Exit Lab (monitor/saad_view/exitlab.py). Zee 2026-10-20: "create an Exit Lab tab where we can test out all the different kinds of
// exits possible. including trailing, partial close etc. the exit lab should be really really intelligently made."
// The entries stay the EA's (the settings on screen); only the exit changes. Every exit runs in the Turtle TV Tester's own engine.
'use strict';
const LABS = { spec: null, main: null, quick: null, diag: null, test: null, cat: null, search: null, heat: null, form: null, fam: 'all', sort: 'total',
  both: false, showLab: false, obj: 'net', heatPair: 0, polling: false, feat: null };
const HEAT_PAIRS = [
  { name: 'Target in R  ×  breakeven at R', base: { tgt: 2 }, fx: 'tgt_k', xs: [1, 1.5, 2, 2.5, 3, 4], fy: 'be_r', ys: [0, 0.5, 0.75, 1, 1.5, 2] },
  { name: 'ATR trail (k)  ×  trail starts at R', base: { tr: 2 }, fx: 'tr_k', xs: [1, 1.5, 2, 2.5, 3, 4], fy: 'tr_act', ys: [0, 0.5, 1, 1.5, 2] },
  { name: 'Keep % of the best profit  ×  starts at R', base: { tr: 3 }, fx: 'tr_k', xs: [30, 40, 50, 60, 70, 80], fy: 'tr_act', ys: [0.5, 1, 1.5, 2] },
  { name: 'N-candle trail  ×  starts at R', base: { tr: 7 }, fx: 'tr_k', xs: [3, 5, 7, 10, 15, 20], fy: 'tr_act', ys: [0, 0.5, 1, 2] },
  { name: 'Partial at R  ×  share closed', base: { p1_be: 1 }, fx: 'p1_r', xs: [0.5, 0.75, 1, 1.5, 2], fy: 'p1_frac', ys: [0.25, 0.33, 0.5, 0.67, 0.75] },
  { name: 'Fallback buffer (ATR)  ×  closes in a row', base: {}, fx: 'fb_buf', xs: [0, 0.1, 0.25, 0.5, 0.75, 1], fy: 'fb_n', ys: [1, 2, 3] },
  { name: 'No progress after N candles  ×  ... less than R', base: {}, fx: 'stale_bars', xs: [4, 6, 8, 12, 16, 24], fy: 'stale_r', ys: [0, 0.25, 0.5, 1] },
];
const SLOT = { diagnose: 'diag', test: 'test', catalogue: 'cat', search: 'search', heatmap: 'heat' };
if (/(^|[#&])labshow=1/.test(location.hash)) LABS.showLab = true;           // a link straight to the lab's trades on the chart

// ---------- plumbing ----------
async function labOpen() {
  if (LABS.opening) return LABS.opening;                        // renders call this until the spec is in: one load, not several
  LABS.opening = labOpen1().finally(() => { LABS.opening = null; });
  return LABS.opening;
}
async function labOpen1() {
  if (!LABS.spec) { LABS.spec = await api('/api/exitlab_spec'); LABS.form = { ...LABS.spec.default }; }
  const s = await api('/api/exitlab?full=1').catch(() => ({}));
  labTake(s);
  if (LABS.test && LABS.test.lab && !LABS._formSet) LABS.form = { ...LABS.spec.default, ...LABS.test.lab };   // the builder shows the exit of the result below it
  LABS._formSet = true;
  if (TAB.tt === 'lab') renderPanel('tt');
  if (LABS.showLab) redraw();
  if ((s.main && s.main.running) || (s.quick && s.quick.running)) labPoll();
}
function labTake(s) {
  const take = (j) => {
    if (!(j && j.done && j.result && !j.error)) return;
    const slot = SLOT[j.action], prev = LABS[slot], id = j.jid || (j.action + j.seconds + JSON.stringify(j.req || {}) + JSON.stringify(j.result.sets || {}) + (j.result.describe || ''));
    if (prev && prev._id === id) return;
    LABS[slot] = Object.assign(j.result, { _id: id, _labels: j.labels, _ds: j.ds, _req: j.req });
    if (slot === 'test' && LABS.showLab) redraw();
    if (slot === 'test' && LABS.goResult) { LABS.goResult = false; setTimeout(() => { const e = document.querySelector('#labResult'); if (e) e.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 150); }
  };
  for (const j of Object.values((s && s.done) || {})) take(j);
  for (const k of ['main', 'quick']) { const j = s && s[k]; if (j) { LABS[k] = j; take(j); } }
}
const labBusyUi = () => { const a = document.activeElement; return LABS.mouse || (a && a.closest && a.closest('#panelTT') && /SELECT|INPUT|TEXTAREA/.test(a.tagName)); };
document.addEventListener('mousedown', () => { LABS.mouse = true; });      // a redraw between mouse-down and mouse-up would swallow the click
document.addEventListener('mouseup', () => { setTimeout(() => { LABS.mouse = false; }, 0); });
async function labPoll() {
  if (LABS.polling) return;
  LABS.polling = true;
  try {
    for (;;) {
      const s = await api('/api/exitlab').catch(() => null);
      if (s) labTake(s);
      const running = s && ((s.main && s.main.running) || (s.quick && s.quick.running));
      if (TAB.tt === 'lab' && (!labBusyUi() || !running)) renderPanel('tt');
      if (!running) break;
      await new Promise((r) => setTimeout(r, 900));
    }
  } finally { LABS.polling = false; }
}
async function labStart(action, extra = {}) {
  if (!LABS.spec) await labOpen();
  const r = await api('/api/exitlab', { action, inputs: CUR, ds: SRC.ds === 'tv' ? 'year' : SRC.ds, ...extra });
  if (r.error) return toast('⚠ ' + esc(r.error));
  const k = action === 'test' || action === 'diagnose' ? 'quick' : 'main';
  LABS[k] = { action, running: true, phase: 'starting', progress: 0, total: 0, seconds: 0 };
  if (TAB.tt === 'lab') renderPanel('tt');
  labPoll();
}
const labForm = () => Object.fromEntries(Object.entries(LABS.form).map(([k, v]) => [k, Number(v)]));
function labShow(cond) {                                         // "tgt>=2", "cx>=1&&cx<=3", "tr==1||tr==2"
  if (!cond) return true;
  return cond.split('||').some((o) => o.split('&&').every((a) => {
    const m = a.match(/^(\w+)(>=|<=|==|>|<)(-?[\d.]+)$/);
    if (!m) return true;
    const v = Number(LABS.form[m[1]]), c = Number(m[3]);
    return { '>=': v >= c, '<=': v <= c, '==': v === c, '>': v > c, '<': v < c }[m[2]];
  }));
}
function labLabels() {
  for (const k of ['cat', 'test', 'diag', 'search', 'heat']) if (LABS[k] && LABS[k]._labels) return LABS[k]._labels;
  for (const k of ['main', 'quick']) if (LABS[k] && LABS[k].labels) return LABS[k].labels;
  return SRC.ds === 'm15' ? ['2023 – 2024', '2025 – 2026'] : ['Jan – Jun', 'Jul – Oct'];
}
const canon = (o) => JSON.stringify(Object.keys(o).sort().map((k) => [k, String(o[k])]));
function stale(R) {                                              // results of other settings or other data must say so
  if (!R || !R._req) return '';
  const a = canon(diffDfl({ ...DFL, ...(R._req.inputs || {}) })), b = canon(diffDfl(CUR)), ds = SRC.ds === 'tv' ? 'year' : SRC.ds;
  if (a === b && R._req.ds === ds) return '';
  return `<p class="warn">⚠ This was run on ${R._req.ds === 'm15' ? 'the 4 years' : '2026'}${a !== b ? ' with other EA settings than the ones on screen' : ''} - press its button again for the settings and data on screen.</p>`;
}
const EVIDENCE = `<div class="hintbox">📜 <b>Evidence already on file (MT5, not Python):</b> 2026-08-10, five identical entries - the structural stop + target alone made +$187.50;
  every rule that closed a trade between them cost money (breakeven locks +$57.80 to +$127.30, the give-back ratchet +$12.90). 2026-10-19 (betest, v1.26, full year):
  partials and %-breakeven ~no change, a $8 breakeven -$22k, fixed +$X targets and locks cut profit hard (close at +$8: +$53k). The EMA target stayed.
  A lab row has to beat that history in MT5, not just here.</div>`;
const CALIB = `<div class="hintbox">📏 <b>How far to trust the "In the EA" rows (MT5 check, 2026-10-20, 2026 data, no delay - the same trades in all four):</b>
  stop $12 MT5 +$260,289 (lab +$272,607) · your exit +$242,911 (lab +$253,432) · stop 1.4 x ATR +$241,710 (lab +$259,983) · exit mode 2 +$180,909 (lab +$189,223).
  The lab reads 4-8% high and swapped the two closest (1.4 ATR vs yours: +$6.6k in the lab, -$1.2k in MT5). <b>For these rows a difference under ~4% of the total is a tie</b> (marked ≈).
  <b>"Lab only" rows have no MT5 check yet</b> - their new code (targets, trails, time exits, long holds) is unproven until "Make it an EA setting" and MT5.</div>`;
const tie = (d, base) => Math.abs(d) < Math.max(5000, 0.04 * Math.abs(base));
const mm = (s) => `${money(s.net)} <span class="k">· ${s.wr}% · ${s.n}</span>`;

// ---------- the panel ----------
function pLab() {
  if (!LABS.spec) { labOpen(); return '<p class="note">Loading the Exit Lab…</p>'; }
  const [LA, LB] = labLabels(), ncat = LABS.cat ? LABS.cat.rows.length : 150;
  const dsName = SRC.ds === 'm15' ? 'Blueberry 2023 → now (4 years)' : '2026 (Blueberry real ticks)';
  let h = `<div class="lab"><p class="note"><b>Exit Lab.</b> The entries stay your EA's (the settings on screen); only the exit changes. Every exit runs in the
    Turtle TV Tester's own engine, inside every minute, so a trade held longer still blocks the next setup. Data: <b>${dsName}</b>${SRC.ds === 'tv' ? ' (the lab uses Blueberry 2026 for TradingView\'s candles)' : ''}.
    ${SRC.mode !== 'ea' ? '<span class="warn">The lab always uses the EA’s own rules (real spread and swap), not the chart’s.</span> ' : ''}Choices are made on <b>${LA}</b>; <b>${LB}</b> is the test. <span class="tag ea">In the EA</span> = MT5 can check it now · <span class="tag lab">Lab only</span> = a hypothesis until it is built into the EA and MT5 confirms it.</p>`;
  h += `<div class="bar"><button data-lab="diagnose">🩺 Where do my exits leave money?</button><button data-lab="catalogue" class="primary">🧪 Test every exit (${ncat})</button>
    <button data-lab="search">🧠 Find the best exit for me</button><label>choose by <select id="labObj">${[['net', `net on ${LA}`], ['ret_dd', 'net ÷ drawdown'], ['pf', 'profit factor'], ['wr', 'win rate']]
      .map(([v, l]) => `<option value="${v}" ${v === LABS.obj ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select></label><button data-lab="stop">Stop</button></div>`;
  for (const k of ['main', 'quick']) {
    const J = LABS[k];
    if (J && J.running) h += `<p class="note">⏳ <span class="prog"><i style="width:${J.total ? Math.min(100, (100 * J.progress) / J.total) : 3}%"></i></span> ${esc(J.phase || '')} · ${J.progress || 0}${J.total ? '/' + J.total : ''} · ${J.seconds || 0} s</p>`;
    else if (J && J.error) h += `<p class="warn">⚠ ${esc(J.action)} stopped: ${esc(J.error)}</p>`;
  }
  h += labDrawings();                                          // the two specimens first (static/exitlab_draw.js)
  if (LABS.diag) h += labDiag(LABS.diag, LA, LB);
  h += labBuilder(LA, LB);
  if (LABS.cat) h += labCatalogue(LABS.cat, LA, LB);
  if (LABS.search) h += labSearch(LABS.search, LA, LB);
  h += labHeat(LA, LB);
  return h + '</div>';
}

// ---------- 1. where the exits leave money ----------
function labDiag(d, LA, LB) {
  const a = d.stats.all;
  let h = `<section><h3>🩺 Where your exits leave money</h3>${stale(d)}` +
    (d.stats.stuck ? `<p class="bad">⚠ One of your trades (or a stand-aside) never closed: open since ${esc(dt(d.stats.open_end.since))} until the end of the data (${d.stats.open_end.days} days) - it blocks every later setup.</p>` : '') +
    (String(CUR.InpExitMode) === '0' ? '<p class="warn">Your exit is mode 0 (the v1.23 exits): the tester and MT5 disagree on those - read this diagnosis as approximate.</p>' : '') + `<div class="cards">` +
    card('Trades · win rate', `${a.n} · ${a.wr}%`) + card('Net', money(a.net), cls(a.net)) +
    card('Winners keep', `${d.winners.capture_pct}% <small class="k">of their best move</small>`) +
    card('Losers that were +1R first', `${d.losers_were_1r.n} <small class="k">${money(d.losers_were_1r.net)}</small>`) +
    card('After a rule closed a trade (next 4 h)', `${d.early.n} <small class="k">went +1R on first ·</small> ${d.early.right} <small class="k">went −1R first</small>`) +
    card('After a stop-out (next 4 h)', `${d.stop_back.n} <small class="k">came back +1R first ·</small> ${d.stop_back.right} <small class="k">fell 1R more first</small>`) +
    card("Winners' deepest dip (3 in 4)", `≤ ${d.mae_winners_r.p75}R`) + card('Stop distance', `$${d.risk.p50} <small class="k">typical, $${d.risk.p90} wide</small>`) + '</div>';
  h += labHints(d);
  const eb = d.early_by || {};
  h += `<div class="row"><div><h4>How your trades end · price in the next 4 h</h4>` + table(['Reason', 'Trades', 'Win rate', 'Net', '+1R on first', '−1R against first'], Object.entries(d.stats.why).map(([k, v]) =>
    `<tr><td>${esc(k)}</td><td>${v.n}</td><td>${pct(v.wins, v.n)}</td><td class="${cls(v.net)}">${money(v.net)}</td><td>${eb[k] ? `${eb[k].early} <span class="k">(${pct(eb[k].early, eb[k].n)})</span>` : ''}</td><td>${eb[k] ? `${eb[k].right} <span class="k">(${pct(eb[k].right, eb[k].n)})</span>` : ''}</td></tr>`)) + '</div>';
  h += `<div><h4>How far trades went your way first</h4>` + table(['Best move ≥', 'Trades'], Object.entries(d.reach).map(([k, v]) => `<tr><td>${k}</td><td>${v}%</td></tr>`)) +
    `<p class="note" style="max-width:220px">R = the distance from the entry to the first stop.</p></div>`;
  h += `<div><h4>Best move vs result, every trade (R)</h4>${labScatter(d.scatter)}<p class="note" style="max-width:360px">On the blue line = the exit took the whole move.
    Far below it = the trade gave most of it back. Red dots right of 1R = losers that were +1R first.</p></div></div>`;
  return h + '</section>';
}
function labHints(d) {
  const H = [], s = d.stats.all, lose = Math.round(s.n * (1 - s.wr / 100));
  if (d.losers_were_1r.n >= Math.max(3, 0.1 * lose)) H.push([`${d.losers_were_1r.n} losing trades were at least +1R in profit first and still lost $${Math.abs(d.losers_were_1r.net).toLocaleString('en-US')}. A breakeven or a partial close at 1R would save some of them - but it also stops winners that dip back before running.`, { be_r: 1 }, 'breakeven at +1R']);
  if (d.winners.capture_pct < 55) H.push([`Winners keep only ${d.winners.capture_pct}% of their best move (${money(d.winners.giveback)} given back). A trail could keep more of it.`, { tr: 2, tr_k: 2, tr_act: 1 }, 'trail 2 ATR from +1R']);
  const e = d.early, sb = d.stop_back;
  if (e.n > 1.25 * e.right) H.push([`After the ${e.of} trades closed by a rule (not the stop), price went another +1R their way before −1R against in ${e.n}, and −1R first in ${e.right}: the rules close too early more often than not. The fallback (close back across the fast EMA) is the first suspect - see "Price after the exit" by reason below.`, { fb_n: 2 }, 'the fallback needs 2 closes']);
  else if (e.right > 1.25 * e.n) H.push([`After the ${e.of} trades closed by a rule, price went −1R against before +1R on in ${e.right} and +1R first in only ${e.n}: the exit rules mostly get out at the right time.`, null, '']);
  else H.push([`After the ${e.of} trades closed by a rule, +1R on came first in ${e.n} and −1R against first in ${e.right}: about a coin flip - exit timing alone is not where the money is.`, null, '']);
  if (sb.n > 1.25 * sb.right) H.push([`After ${sb.of} stop-outs, price came back +1R (about to the entry) before falling 1R more in ${sb.n}, and fell 1R more first in ${sb.right}: the stop is often too tight. A wider stop also makes every loser bigger - test it (an EA setting: Stop x ATR, in the list below).`, null, '']);
  if (d.mae_winners_r.p75 < 0.5) H.push([`3 winners in 4 never went below −${d.mae_winners_r.p75}R before working: the stop gives winners more room than they use. A tighter stop is an EA setting (Stop x ATR) - test it in the list below.`, null, '']);
  if (!H.length) H.push(['Nothing stands out: your exit already keeps most of the move. Test every exit to be sure.', null, '']);
  return H.map(([t, lab, nm]) => `<div class="hintbox">💡 ${t} ${lab ? `<button data-lload="${esc(JSON.stringify(lab))}">Try: ${esc(nm)}</button>` : ''}</div>`).join('');
}
function labScatter(pts) {
  if (!pts || !pts.length) return '';
  const W = 380, H = 230, P = 30;
  const xmax = Math.min(6, Math.max(2, ...pts.map((p) => p[0]))), ymin = Math.max(-2.5, Math.min(-1.2, ...pts.map((p) => p[1]))), ymax = Math.min(6, Math.max(1, ...pts.map((p) => p[1])));
  const X = (v) => P + (Math.min(Math.max(v, 0), xmax) / xmax) * (W - P - 8), Y = (v) => 8 + (1 - (Math.max(ymin, Math.min(ymax, v)) - ymin) / (ymax - ymin)) * (H - P - 8);
  const d = Math.min(xmax, ymax);
  let s = `<svg width="${W}" height="${H}" style="background:var(--panel);border-radius:6px">` +
    `<line x1="${X(0)}" y1="${Y(0)}" x2="${X(xmax)}" y2="${Y(0)}" stroke="#4a4f5c"/>` +
    `<line x1="${X(0)}" y1="${Y(-1)}" x2="${X(xmax)}" y2="${Y(-1)}" stroke="#7a3434" stroke-dasharray="3 3"/>` +
    `<line x1="${X(0)}" y1="${Y(0)}" x2="${X(d)}" y2="${Y(d)}" stroke="#2962ff" stroke-dasharray="4 3"/>` +
    `<line x1="${X(1)}" y1="${Y(ymin)}" x2="${X(1)}" y2="${Y(ymax)}" stroke="#363a45" stroke-dasharray="2 4"/>`;
  for (const p of pts) s += `<circle cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="2.6" fill="${p[1] > 0 ? '#00e676' : '#ff5252'}" fill-opacity=".65"><title>${esc(dt(p[3]))} ${p[2] > 0 ? 'BUY' : 'SELL'}: best +${p[0]}R, result ${p[1]}R</title></circle>`;
  s += `<text x="${W - 112}" y="${H - 8}">best move (R) →</text><text x="4" y="14">result (R)</text><text x="${X(d) - 64}" y="${Y(d) + 14}">whole move</text>` +
    `<text x="${P + 4}" y="${Y(-1) - 4}">full stop −1R</text><text x="${X(1) + 3}" y="${H - 8}">1R</text>`;
  return s + '</svg>';
}

// ---------- 2. build an exit ----------
function labField(x) {
  const v = LABS.form[x.f], chg = Number(v) !== Number(x.d);
  let inp;
  if (x.t === 'sel') inp = `<select data-lf="${x.f}">${x.opts.map(([k, l]) => `<option value="${k}" ${Number(v) === k ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
  else if (x.t === 'bool') inp = `<input type="checkbox" data-lf="${x.f}" ${Number(v) ? 'checked' : ''}>`;
  else inp = `<input type="number" data-lf="${x.f}" value="${v}" step="${x.step}"${x.min != null ? ` min="${x.min}"` : ''}${x.max != null ? ` max="${x.max}"` : ''}>`;
  return `<label class="fl ${chg ? 'chg' : ''}"><span>${esc(x.label)}</span>${inp}</label>`;
}
function labBuilder(LA, LB) {
  const m0 = String(CUR.InpExitMode) === '0';
  let h = `<section><h3>🔧 Build an exit</h3><p class="note">Combine any of these - the first rule to fire closes the trade (partials close part of it, the rest runs on).
    They work on top of exit modes 1 and 2${m0 ? ' - <span class="warn">your settings use exit mode 0, so the lab runs them on exit mode 1</span>' : ''}. Stand-asides (unticked range boxes) keep the EA's exit.</p>${EVIDENCE}<div class="grid">`;
  for (const [title, hint, fields] of LABS.spec.groups) h += `<fieldset><legend>${esc(title)}</legend>${hint ? `<p class="hint">${esc(hint)}</p>` : ''}${fields.filter((x) => labShow(x.show)).map(labField).join('')}</fieldset>`;
  h += `</div><div class="bar"><button data-lab="test" class="primary">▶ Test this exit</button><button data-lab="reset">Reset to the EA's own exit</button>
    <label class="tog"><input type="checkbox" id="labShowChart" ${LABS.showLab ? 'checked' : ''}> show this exit's trades on the chart (orange)</label></div>`;
  if (LABS.test) h += labTestResult(LABS.test, LA, LB);
  return h + '</section>';
}
function labStatsRow(name, s) {
  return `<tr><td class="l">${name}</td><td class="${cls(s.train.net)}">${mm(s.train)}</td><td class="${cls(s.test.net)}">${mm(s.test)}</td><td class="${cls(s.total)}"><b>${money(s.total)}</b></td>` +
    `<td>${s.all.wr}%</td><td>${s.all.pf}</td><td>${money(-s.all.dd)}</td><td>${money(s.all.avg_win)} / ${money(s.all.avg_loss)}</td><td>${s.all.streak}</td></tr>`;
}
function labTestResult(T, LA, LB) {
  const s = T.stats, b = T.base, both = s.train.net > b.train.net && s.test.net > b.test.net, isEA = !Object.keys(T.lab || {}).filter((k) => k !== 'pess').length;
  let h = `<h4 id="labResult">Result · ${esc(T.describe)}${Object.keys(T.sets || {}).length ? ' · ' + esc(Object.entries(T.sets).map(([k, v]) => `${k.replace(/^Inp/, '')} ${v}`).join(', ')) : ''}</h4>${stale(T)}` +
    table(['', LA, LB, 'Total', 'WR', 'PF', 'Max DD', 'Avg win / loss', 'Losing streak'], [labStatsRow("Your EA's exit", b), labStatsRow('This exit', s)]);
  const wv = T.worst, onlyOpt = s.total > b.total && wv.total < wv.base_total;
  if (s.stuck) h += `<p class="bad">⚠ A trade (or a stand-aside) never closed: open since ${esc(dt(s.open_end.since))} until the end of the data (${s.open_end.days} days). Nothing in this exit closes it
    (no target and no rule for a winner), so it blocks every later setup - these numbers are not usable. Add a target, a trail or a time limit.</p>`;
  h += `<p class="note">${isEA && tie(s.total - b.total, b.total) && s.changed ? '<span class="warn">≈ A tie: the difference is within the lab’s error against MT5 (~4%).</span> ' : ''}${!isEA ? '<span class="tag lab">Lab only: no MT5 check yet</span> ' : ''}${both ? '<span class="good">✓ Better than yours in both halves.</span>' : s.total > b.total ? '<span class="warn">Better in total but not in both halves - the unseen half decides.</span>' : '<span class="bad">Not better than your exit.</span>'}
    ${s.changed} trades end differently · ${s.new} new and ${s.gone} missing entries (a trade held longer or shorter changes which setups can enter) · partial closes in ${s.partials} trades ·
    longest trade ${s.longest_h} h${s.longest_h > 48 ? ' <span class="bad">(a trade stayed open for days - this exit can hold a loser a long time)</span>' : ''}.
    Adverse move first inside every minute: ${money(wv.total)} vs yours ${money(wv.base_total)}${onlyOpt ? ' <span class="bad">⚠ it only wins when the minute is read in the optimistic order</span>' : wv.total === s.total ? ' (same - no minute held both the stop and the exit)' : ''}.</p>`;
  const whyT = table(['Ended by', 'Trades', 'Win rate', 'Net'], Object.entries(s.why).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.n}</td><td>${pct(v.wins, v.n)}</td><td class="${cls(v.net)}">${money(v.net)}</td></tr>`));
  const ys = Object.keys(s.years);
  const yT = table(['Year', 'Trades', 'WR', 'This exit', 'Yours'], ys.map((y) => { const a = s.years[y], c = (b.years || {})[y] || { net: 0 };
    return `<tr><td>${y}</td><td>${a.n}</td><td>${a.wr}%</td><td class="${cls(a.net)}">${money(a.net)}</td><td class="k">${money(c.net)}</td></tr>`; }));
  const sd = (x, nm) => (x.sides || {})[nm] || { n: 0, net: 0, train: 0, test: 0, wr: 0 };
  const sT = table(['Side', 'Trades', 'WR', LA, LB, 'This exit', 'Yours'], ['BUY', 'SELL'].map((nm) => { const a = sd(s, nm), c = sd(b, nm);
    return `<tr><td>${nm}</td><td>${a.n}</td><td>${a.wr}% <span class="k">(${c.wr}%)</span></td><td class="${cls(a.train - c.train)}">${money(a.train)}</td><td class="${cls(a.test - c.test)}">${money(a.test)}</td><td class="${cls(a.net)}"><b>${money(a.net)}</b></td><td class="k">${money(c.net)}</td></tr>`; }));
  h += `<div class="row"><div><h4>How the trades ended</h4>${whyT}</div><div><h4>Year by year</h4>${yT}</div><div><h4>BUY and SELL (a bull market favours holding longs)</h4>${sT}</div></div>`;
  const D = T.diffs;
  if (D && D.n + D.new.n + D.gone.n === 0) h += '<p class="warn">This exit changed nothing: no rule of it fired on these trades.</p>';
  else if (D) {
    const dl = (rows) => table(['Entry', '', 'Yours', 'This exit', 'Difference'], rows.map((r) => `<tr class="click" data-ltime="${r[0]}"><td>${esc(dt(r[0]))}</td><td>${r[1] > 0 ? 'BUY' : 'SELL'}</td>` +
      `<td class="${cls(r[2])}">${money(r[2])} <span class="k">${esc(r[4])}</span></td><td class="${cls(r[3])}">${money(r[3])} <span class="k">${esc(r[5])}</span></td><td class="${cls(r[8])}"><b>${money(r[8])}</b></td></tr>`));
    h += `<p class="note">Same entries, different exits: ${D.n} trades end differently - ${D.up} better, ${D.n - D.up} worse. Entries it added: ${D.new.n} (${money(D.new.net)}) · entries it lost: ${D.gone.n} (${money(D.gone.net)}). Click a trade to see it on the chart.</p>`;
    h += `<div class="row"><div><h4>Helped most</h4>${dl(D.gain.filter((r) => r[8] > 0))}</div><div><h4>Hurt most</h4>${dl(D.loss.filter((r) => r[8] < 0))}</div></div>`;
  }
  if (!isEA) {
    const F = LABS.feat;
    h += `<div class="bar"><button data-lab="feature" ${F && F.running ? 'disabled' : ''}>🛠 Make it an EA setting</button><span class="k">Claude builds this exit into the EA (off by default), mirrors it in the tester, runs MT5 off vs on, records the version and commits.</span></div>`;
    if (F) h += F.running ? `<p class="note">⏳ ${esc(F.phase || 'working')}</p>` : F.error ? `<p class="warn">⚠ ${esc(F.error)}</p>` : F.result ? `<div class="hintbox" style="white-space:pre-wrap">${esc(F.result.report)}</div>` : '';
  } else if (Object.keys(T.sets || {}).length) h += `<div class="bar"><button data-lapply="1">Apply to the chart</button><button data-lmt5t="1">Check in MT5</button></div>`;
  return h;
}

// ---------- 3. every exit, ranked ----------
function labCatalogue(C, LA, LB) {
  const b = C.base, fams = [...new Set(C.rows.map((r) => r.fam))];
  let rows = C.rows.map((r, i) => ({ r, i })).filter(({ r }) => LABS.fam === 'all' || r.fam === LABS.fam);
  if (LABS.both) rows = rows.filter(({ r }) => r.stats.train.net > b.train.net && r.stats.test.net > b.test.net);
  const key = { total: (r) => r.stats.total, test: (r) => r.stats.test.net, train: (r) => r.stats.train.net, wr: (r) => r.stats.all.wr, pf: (r) => r.stats.all.pf, dd: (r) => -r.stats.all.dd }[LABS.sort];
  rows.sort((x, y) => key(y.r) - key(x.r));
  const nb = C.rows.filter((r) => r.stats.train.net > b.train.net && r.stats.test.net > b.test.net);
  let h = `<section><h3>🧪 Every exit, ranked</h3>${stale(C)}${C.stopped ? `<p class="warn">Stopped early: ${C.rows.length} of ${C.of} exits tested (the search will test them all again).</p>` : ''}<p class="note">${C.rows.length} exits on the same entries. Your EA's exit: ${LA} ${money(b.train.net)} · ${LB} ${money(b.test.net)} · total <b>${money(b.total)}</b> · WR ${b.all.wr}%.
    <b>${nb.length}</b> beat it in both halves (green rows, ${nb.filter((r) => r.kind === 'ea').length} of them in the EA already). <b>Robust</b> ✓ = the values either side in its family also beat yours.
    <b>Worst order</b> = the adverse move first inside every minute (the best 20 only). <b>Changed</b> = trades that end differently from yours.</p>${CALIB}${EVIDENCE}`;
  h += `<div class="bar">family <select id="labFam"><option value="all">all (${C.rows.length})</option>${fams.map((f) => `<option ${f === LABS.fam ? 'selected' : ''}>${esc(f)}</option>`).join('')}</select>
    sort by <select id="labSort">${[['total', 'total'], ['test', LB + ' (unseen)'], ['train', LA], ['wr', 'win rate'], ['pf', 'profit factor'], ['dd', 'smallest drawdown']]
      .map(([v, l]) => `<option value="${v}" ${v === LABS.sort ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>
    <label class="tog"><input type="checkbox" id="labBoth" ${LABS.both ? 'checked' : ''}> only the ones better in both halves</label></div>`;
  h += `<div class="scroll" style="max-height:560px">` + table(['Exit', '', LA, LB, 'Total', 'vs yours', 'WR', 'PF', 'Max DD', 'Trades', 'Changed', 'Longest', 'Robust', 'Worst order', ''], rows.map(({ r, i }) => {
    const s = r.stats, both = s.train.net > b.train.net && s.test.net > b.test.net;
    const tag = r.kind === 'ea' ? `<span class="tag ea">In the EA</span>${r.trust === 'untrusted' ? '<span class="tag unt" title="verify_settings.py: the tester and MT5 move the result in opposite directions on this setting">⚠ tester ≠ MT5</span>' : r.trust === 'check' ? '<span class="tag unt" title="the tester and MT5 differ in size on this setting">check in MT5</span>' : ''}` : '<span class="tag lab">Lab only</span>';
    const w = r.worst ? `<span class="${r.worst.total >= r.worst.base_total ? '' : 'bad'}" title="yours in the same order: ${money(r.worst.base_total)}">${money(r.worst.total)}</span>` : '';
    return `<tr class="${both ? 'both' : ''}"><td class="l"><b>${esc(r.name)}</b><br><span class="k">${esc(r.fam)}</span></td><td>${tag}</td>` +
      `<td class="${cls(s.train.net - b.train.net)}">${money(s.train.net)}</td><td class="${cls(s.test.net - b.test.net)}">${money(s.test.net)}</td><td><b>${money(s.total)}</b></td>` +
      `<td class="${r.kind === 'ea' && tie(s.total - b.total, b.total) ? 'k' : cls(s.total - b.total)}" title="${r.kind === 'ea' && tie(s.total - b.total, b.total) ? 'within the lab’s error against MT5: a tie' : ''}">${r.kind === 'ea' && tie(s.total - b.total, b.total) ? '≈ ' : ''}${money(s.total - b.total)}</td><td>${s.all.wr}%</td><td>${s.all.pf}</td><td>${money(-s.all.dd)}</td><td>${s.all.n}</td>` +
      `<td>${!s.changed && !s.new && !s.gone ? '<span class="k" title="no rule of this exit fired on these trades">no effect</span>' : s.changed}</td>` +
      `<td>${s.stuck ? `<span class="bad" title="open since ${esc(dt(s.open_end.since))} until the end of the data">never closed</span>` : s.longest_h > 48 ? `<span class="bad">${s.longest_h} h</span>` : s.longest_h + ' h'}</td><td>${r.plateau ? '✓' : ''}</td><td>${w}</td>` +
      `<td><button data-lrow="${i}">${r.kind === 'ea' ? 'Test it' : 'Load + test'}</button>${r.kind === 'ea' ? ` <button data-lmt5="${i}">Check in MT5</button>` : ''}</td></tr>`;
  })) + '</div></section>';
  return h;
}

// ---------- 4. the smart search ----------
function labSearch(S, LA, LB) {
  const b = S.base;
  let h = `<section><h3>🧠 The best exits found</h3>${stale(S)}<p class="note">Started from the 6 best exits on ${LA}; every number was moved one step at a time and every other kind of exit was tried on top,
    keeping a change only if ${LA} improved. ${LB} was never looked at - it is the test. <b>Robust</b> = of the one-step changes either side of every number, how many still beat yours in both halves.
    <b>Worst order</b> = the adverse move first inside every minute (yours: ${money(S.base_worst)}). All of these are <b>Lab only: no MT5 check yet</b>.</p>`;
  h += table(['Exit', LA, LB, 'Total', 'vs yours', 'WR', 'Robust', 'Worst order', ''], S.finals.map((f, i) => {
    const s = f.stats, both = s.train.net > b.train.net && s.test.net > b.test.net, pl = f.plateau || [0, 0];
    return `<tr class="${both ? 'both' : ''}"><td class="l"><b>${esc(f.describe)}</b><br><span class="k">from: ${esc(f.seed)}</span></td><td>${mm(s.train)}</td><td class="${cls(s.test.net - b.test.net)}">${mm(s.test)}</td>` +
      `<td><b>${money(s.total)}</b></td><td class="${cls(s.total - b.total)}">${money(s.total - b.total)}</td><td>${s.all.wr}%</td><td class="${pl[1] && pl[0] / pl[1] >= 0.7 ? 'good' : 'bad'}">${pl[0]}/${pl[1]}</td>` +
      `<td class="${f.worst >= S.base_worst ? '' : 'bad'}">${money(f.worst)}</td><td><button data-lfin="${i}">Load + test</button></td></tr>`;
  }));
  if (S.log.length) h += `<details><summary class="k">The ${S.log.length} steps that helped (${LA} only)</summary>` + table(['Started from', 'Change', LA, LB, 'Total'],
    S.log.map((l) => `<tr><td class="l">${esc(l.stage)}</td><td class="l">${esc(l.change)}</td><td>${money(l.train.net)}</td><td class="${cls(l.test.net - b.test.net)}">${money(l.test.net)}</td><td>${money(l.total)}</td></tr>`)) + '</details>';
  return h + '</section>';
}

// ---------- 5. two numbers against each other ----------
function labHeat(LA, LB) {
  let h = `<section><h3>🗺️ Two numbers against each other</h3><p class="note">Every combination of two numbers on the same entries, starting from the exit in the builder.
    A good setting sits on a green plateau; one green cell among red ones is luck. ✓ = better than yours in both halves.</p>
    <div class="bar"><select id="labPair">${HEAT_PAIRS.map((p, i) => `<option value="${i}" ${i === LABS.heatPair ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</select><button data-lab="heatmap">Run the grid</button></div>`;
  const R = LABS.heat;
  if (R && R.grid) {
    const b = R.base, all = R.grid.flat(), mx = Math.max(1, ...all.map((c) => Math.abs(c.total - b.total)));
    h += `${stale(R)}<p class="note">${esc(R.describe)} · each cell: total, then ${LA} / ${LB} · yours ${money(b.total)}</p>`;
    h += `<table class="heat"><tr><th>${esc(R.fy)} ↓ · ${esc(R.fx)} →</th>${R.xs.map((x) => `<th>${x}</th>`).join('')}</tr>` + R.grid.map((row, yi) => `<tr><th>${R.ys[yi]}</th>${row.map((c, xi) => {
      const d = (c.total - b.total) / mx, col = d >= 0 ? `rgba(0,230,118,${(0.06 + 0.5 * d).toFixed(2)})` : `rgba(255,82,82,${(0.06 + 0.5 * -d).toFixed(2)})`;
      const both = c.train > b.train.net && c.test > b.test.net;
      if (c.stuck) return `<td class="k" data-lheat="${xi}|${yi}" title="a trade never closed with these values: not usable">never closed</td>`;
      return `<td style="background:${col}" data-lheat="${xi}|${yi}" title="${c.n} trades · WR ${c.wr}% - click to load">${money(c.total)}${both ? ' ✓' : ''}<br><span class="k">${money(c.train)} / ${money(c.test)}</span></td>`;
    }).join('')}</tr>`).join('') + '</table>';
  }
  return h + '</section>';
}

// ---------- the chart: this exit's trades (orange) ----------
function drawLab(ctx, X, Y, lo, hi, full) {
  if (!LABS.showLab || !LABS.test || !LABS.test.trades || !BARS) return;
  for (const t of LABS.test.trades) {                            // [side, tIn, en, sl, tOut, ex, pnl, why, mfe, mae, r0, partials]
    const bi = barIdx(t[1]), bo = barIdx(t[4]);
    if (bo < lo || bi > hi) continue;
    const x1 = X(bi), x2 = X(bo), y1 = Y(t[2]), y2 = Y(t[5]);
    if (x1 == null || x2 == null || y1 == null || y2 == null) continue;
    ctx.setLineDash([3, 3]); ctx.strokeStyle = '#ffb74d'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = t[6] > 0 ? '#00e676' : '#ff5252'; ctx.beginPath(); ctx.arc(x2, y2, 3.5, 0, 7); ctx.fill();
    ctx.strokeStyle = '#ffb74d'; ctx.lineWidth = 1; ctx.stroke();
    if (full) { ctx.font = '10px "Trebuchet MS", Arial'; ctx.fillStyle = '#ffb74d'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.fillText(`LAB ${money(t[6])} · ${t[7]}${t[11] ? ' · partial' : ''}`, x2 + 6, y2 - 6); }
  }
}

// ---------- events ----------
async function labFeature() {
  const T = LABS.test;
  if (!T || !T.lab) return;
  if (!confirm(`Claude will build "${T.describe}" into the EA as new settings (off by default), mirror it in the tester, run MT5 off vs on, record the version and commit. It takes several minutes. Go?`)) return;
  const r = await api('/api/exitlab_feature', { lab: T.lab, stats: { [labLabels()[0]]: T.stats.train, [labLabels()[1]]: T.stats.test, total: T.stats.total }, labels: labLabels(), ds: T._ds });
  if (r.error) return toast('⚠ ' + esc(r.error));
  LABS.feat = { running: true, phase: 'starting' };
  renderPanel('tt');
  for (;;) {
    await new Promise((res) => setTimeout(res, 4000));
    const j = await api('/api/hyp_job?id=' + r.id).catch(() => null);
    if (!j) continue;
    LABS.feat = j;
    if (TAB.tt === 'lab' && !labBusyUi()) renderPanel('tt');
    if (!j.running) break;
  }
  toast(LABS.feat.error ? '⚠ ' + esc(LABS.feat.error) : 'Claude finished: the report is under the Exit Lab result. Restart Turtle TV (start_turtle_tv.bat) to use the new setting.', 15000);
}
function labRunRow(r) {
  if (r.kind === 'ea') labStart('test', { sets: r.sets });
  else { LABS.form = { ...LABS.spec.default, ...r.lab }; labStart('test', { lab: labForm() }); }
}
async function labMt5(name, sets) {
  const r = await api('/api/run', { sets: { ...CUR, ...sets }, delay: 'none', label: `Exit Lab: ${name}` });
  if (r.error) return toast('⚠ ' + esc(r.error));
  toast(`"${esc(name)}" is running in the MT5 Strategy Tester (real ticks, no delay). Its result appears in the MT5 section in about a minute.`);
}
document.addEventListener('click', (e) => {
  const d = e.target.dataset || {}, row = e.target.closest && e.target.closest('tr[data-ltime]');
  if (row && BARS) {
    const i = barIdx(+row.dataset.ltime); chart.timeScale().setVisibleLogicalRange({ from: i - 40, to: i + 60 });
    LABS.showLab = true; const cb = document.querySelector('#labShowChart'); if (cb) cb.checked = true; redraw();
  }
  if (d.lab) {
    const a = d.lab;
    if (a === 'diagnose' || a === 'catalogue') labStart(a);
    else if (a === 'search') labStart('search', { objective: LABS.obj });
    else if (a === 'stop') api('/api/exitlab_stop', {});
    else if (a === 'test') labStart('test', { lab: labForm() });
    else if (a === 'reset') { LABS.form = { ...LABS.spec.default }; renderPanel('tt'); }
    else if (a === 'heatmap') {
      const p = HEAT_PAIRS[LABS.heatPair];
      labStart('heatmap', { lab: { ...labForm(), ...p.base }, fx: p.fx, fy: p.fy, xs: p.xs, ys: p.ys });
    } else if (a === 'feature') labFeature();
  }
  if (d.lload) { LABS.form = { ...LABS.spec.default, ...JSON.parse(d.lload) }; LABS.goResult = true; toast('Testing it - the result opens under "Build an exit".'); labStart('test', { lab: labForm() }); }
  if (d.lrow != null && LABS.cat) { LABS.goResult = true; labRunRow(LABS.cat.rows[+d.lrow]); }
  if (d.lmt5 != null && LABS.cat) { const r = LABS.cat.rows[+d.lmt5]; labMt5(r.name, r.sets); }
  if (d.lmt5t && LABS.test) labMt5(LABS.test.describe + ' ' + Object.entries(LABS.test.sets).map(([k, v]) => `${k.replace(/^Inp/, '')} ${v}`).join(', '), LABS.test.sets);
  if (d.lapply && LABS.test) { CUR = { ...CUR, ...LABS.test.sets }; markForm(); scheduleSim(0); toast('On the chart: ' + esc(Object.entries(LABS.test.sets).map(([k, v]) => `${k.replace(/^Inp/, '')} ${v}`).join(', '))); }
  if (d.lfin != null && LABS.search) { LABS.goResult = true; LABS.form = { ...LABS.spec.default, ...LABS.search.finals[+d.lfin].lab }; labStart('test', { lab: labForm() }); }
  if (d.lheat && LABS.heat) { LABS.goResult = true;
    const [xi, yi] = d.lheat.split('|').map(Number), R = LABS.heat;
    LABS.form = { ...LABS.spec.default, ...R.lab, [R.fx]: R.xs[xi], [R.fy]: R.ys[yi] };
    labStart('test', { lab: labForm() });
  }
});
document.addEventListener('input', (e) => {
  const t = e.target, f = t.dataset && t.dataset.lf;
  if (f && t.type === 'number') {
    LABS.form[f] = Number(t.value);
    const x = LABS.spec && LABS.spec.groups.flatMap((g) => g[2]).find((y) => y.f === f), lab = t.closest('label');
    if (x && lab) lab.classList.toggle('chg', Number(t.value) !== Number(x.d));
  }
});
document.addEventListener('change', (e) => {
  const t = e.target, f = t.dataset && t.dataset.lf;
  if (f) {
    LABS.form[f] = t.type === 'checkbox' ? (t.checked ? 1 : 0) : Number(t.value);
    clearTimeout(LABS.redrawT);                                // redraw (fields that appear / disappear) once a click on a button has landed
    LABS.redrawT = setTimeout(() => { if (TAB.tt === 'lab') renderPanel('tt'); }, t.type === 'number' ? 300 : 0);   // also redraws specimen B
    return;
  }
  if (t.id === 'labFam') { LABS.fam = t.value; renderPanel('tt'); }
  if (t.id === 'labSort') { LABS.sort = t.value; renderPanel('tt'); }
  if (t.id === 'labBoth') { LABS.both = t.checked; renderPanel('tt'); }
  if (t.id === 'labObj') LABS.obj = t.value;
  if (t.id === 'labPair') LABS.heatPair = +t.value;
  if (t.id === 'labShowChart') { LABS.showLab = t.checked; redraw(); }
});
