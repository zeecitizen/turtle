// Turtle TV Tester - Mission Control (monitor/saad_view/mission.py). Zee 2026-10-21: "think of cool features which can further let me make the strategy
// profitable on a day to day basis .. for example. i run an EA tomorrow using some capital and it brings in some profit."
'use strict';
const MIS = { lego: null, capital: 1000, mode: 'risk', risk: 1, lots: 0.01, lev: 500, maxdd: 20, withLab: false, job: null, polling: false };
function misEquity(R) {
  const ys = R.equity, W = 640, H = 150, lo = Math.min(0, ...ys), hi = Math.max(1, ...ys), X = (i) => 8 + (i / Math.max(1, ys.length - 1)) * (W - 16), Y = (v) => H - 18 - ((v - lo) / (hi - lo)) * (H - 30);
  const yr = R.dates.map((d, i) => [d.slice(0, 4), i]).filter((x, i, a) => i === 0 || x[0] !== a[i - 1][0]);
  return `<svg viewBox="0 0 ${W} ${H}" class="crtsvg" style="max-width:980px"><line x1="8" x2="${W - 8}" y1="${Y(0)}" y2="${Y(0)}" stroke="#1b5e20" stroke-dasharray="3 3"/>` +
    yr.map(([y, i]) => `<line x1="${X(i)}" x2="${X(i)}" y1="10" y2="${H - 18}" stroke="#123"/><text x="${X(i) + 3}" y="${H - 5}" class="crtt">${y}</text>`).join('') +
    `<polyline points="${ys.map((v, i) => `${X(i)},${Y(v)}`).join(' ')}" fill="none" stroke="#69f0ae" stroke-width="2"/><text x="12" y="16" class="crtt">EQUITY AT ${R.lots} LOTS · ${money(ys[ys.length - 1] || 0)}</text></svg>`;
}
function misForm(F) {
  const ys = F.curve, W = 300, H = 60, lo = Math.min(...ys), hi = Math.max(...ys, lo + 1), X = (i) => 4 + (i / Math.max(1, ys.length - 1)) * (W - 8), Y = (v) => H - 4 - ((v - lo) / (hi - lo)) * (H - 8);
  return `<svg viewBox="0 0 ${W} ${H}" class="crtsvg" style="max-width:320px"><line x1="4" x2="${W - 4}" y1="${Y(0)}" y2="${Y(0)}" stroke="#1b5e20" stroke-dasharray="3 3"/><polyline points="${ys.map((v, i) => `${X(i)},${Y(v)}`).join(' ')}" fill="none" stroke="#ffd740" stroke-width="1.5"/></svg>`;
}
function pMission() {
  if (!MIS.opened) { MIS.opened = true; misOpen(); }                 // opened straight onto this tab: fetch the last mission
  const J = MIS.job, R = J && J.result, benchLab = typeof LABS !== 'undefined' && LABS.spec ? Object.keys(labForm()).filter((k) => k !== 'pess' && Number(labForm()[k]) !== Number(LABS.spec.default[k])) : [];
  let h = `<div class="lab dex"><h3 class="dexh">🚀 DEXTER'S MISSION CONTROL · RUN IT TOMORROW</h3>
    <p class="note">You give the capital; the lab sizes the trade, replays the strategy's real days at that size, simulates 2,000 futures from them and tests the EA's own daily stop and target.
    The settings on screen, ${SRC.ds === 'm15' ? 'Blueberry 2023 → now' : '2026'}. Python: a hypothesis until MT5 confirms it.</p>
    <div class="dexpanel"><div class="bar">
      <label class="lopt">Capital $ <input type="number" id="misCap" value="${MIS.capital}" step="100" style="width:90px"></label>
      <label class="lopt"><input type="radio" name="misMode" value="risk" ${MIS.mode === 'risk' ? 'checked' : ''}> risk <input type="number" id="misRisk" value="${MIS.risk}" step="0.25" style="width:60px">% of the capital per trade</label>
      <label class="lopt"><input type="radio" name="misMode" value="lots" ${MIS.mode === 'lots' ? 'checked' : ''}> fixed <input type="number" id="misLots" value="${MIS.lots}" step="0.01" style="width:70px"> lots</label>
      <label class="lopt">leverage 1:<input type="number" id="misLev" value="${MIS.lev}" step="100" style="width:70px"></label>
      <label class="lopt">the drawdown I can live with <input type="number" id="misDD" value="${MIS.maxdd}" step="5" style="width:55px">%</label>
      ${benchLab.length ? `<label class="lopt"><input type="checkbox" id="misLab" ${MIS.withLab ? 'checked' : ''}> with the Exit Lab's exit (${benchLab.length} change${benchLab.length > 1 ? 's' : ''})</label>` : ''}
      ${MIS.lego ? `<label class="lopt"><input type="checkbox" id="misLego" checked> with the Strategy Lego build (${esc(Object.entries(MIS.lego).filter(([k, v]) => ['ma', 'loc', 'candle'].includes(k) && !['ema', 'ea'].includes(v)).map(([k, v]) => k + ': ' + v).join(', ') || 'EA pieces')})</label>` : ''}
      <button id="misGo" class="dexbtn" ${J && J.running ? 'disabled' : ''}>${J && J.running ? '⏳ ' + esc(J.phase) : '🚀 LAUNCH'}</button></div></div>`;
  if (J && J.error) h += `<p class="warn">⚠ ${esc(J.error)}</p>`;
  if (!R) return h + '</div>';
  const D = R.days, F = R.futures, toBig = R.recommended_lots < 0.01, over = R.lots > R.recommended_lots + 1e-9;
  h += `<div class="row" style="gap:14px;margin-top:10px"><div class="crt" style="flex:1 1 420px">
    <div class="crth">▶ TOMORROW'S MISSION</div>
    <div>capital <b>$${R.capital.toLocaleString()}</b> · size <b>${R.lots} lots</b> · a typical stop risks <b>$${R.risk_per_trade}</b> (${R.risk_per_trade_pct}%) · margin ~$${R.margin}</div>
    <div>a day with trades: <b>${D.green_pct}%</b> end green · ~${D.trades_per_day} trades a day · average day <b>${money(D.avg_traded)}</b></div>
    <div>a good day (1 in 20): <b>${money(D.good_day)}</b> · a bad day (1 in 20): <b>${money(D.bad_day)}</b> · worst day seen <b>${money(D.worst)}</b></div>
    <div>about <b>${money(D.per_month)}</b> a month on average · worst month seen <b>${money(D.worst_month)}</b> · red days in a row up to <b>${D.red_streak}</b></div>
    <div style="margin-top:6px" class="${toBig || over ? 'crtbad' : 'crtok'}">${toBig ? `⚠ Even 0.01 lots is too big for $${R.capital.toLocaleString()} at a ${R.max_dd_pct}% drawdown limit: it needs about <b>$${R.min_capital_001.toLocaleString()}</b>.`
      : over ? `⚠ ${R.lots} lots is above the size that keeps a bad year under ${R.max_dd_pct}%: <b>${R.recommended_lots} lots</b>. <button data-misapply="${R.recommended_lots}" class="dexbtn sm">use ${R.recommended_lots}</button>`
        : `✓ ${R.lots} lots stays inside your ${R.max_dd_pct}% drawdown in 95% of simulated years (up to ${R.recommended_lots} lots would).`}
      ${R.recommended_lots >= 0.01 ? `<button class="dexbtn sm" data-mislots="${Math.min(R.lots, R.recommended_lots)}">put ${Math.min(R.lots, R.recommended_lots)} lots on the chart</button>` : ''}</div>
    ${R.stuck ? '<div class="crtbad">⚠ a trade never closes with this exit - not usable</div>' : ''}</div>
    <div class="crt" style="flex:0 1 340px"><div class="crth">▶ IS THE EDGE ALIVE?</div>
      <div>last 30 trading days: <b>${money(R.form.last30)}</b> - better than <b>${R.form.pct}%</b> of all 30-day stretches (typical ${money(R.form.median30)})</div>
      <div class="${R.form.pct < 10 ? 'crtbad' : R.form.pct < 30 ? 'crtwarn' : 'crtok'}">${R.form.pct < 10 ? '⚠ the worst form in its history - think twice' : R.form.pct < 30 ? 'weaker than usual' : '✓ in normal or better form'}</div>
      ${misForm(R.form)}<div class="k">30-day P&L, rolling, over the data</div></div></div>`;
  h += `<div class="crt" style="margin-top:10px">${misEquity(R)}<div class="k">${R.days.n} trading days · net ${money(D.net)} · max drawdown ${money(-D.max_dd)} (${D.max_dd_pct}% of the capital)${R.with_lab ? ' · exit: ' + esc(R.lab) : ''}</div></div>`;
  h += `<h4>2,000 futures, bootstrapped from the real days (5-day blocks)</h4>` + table(['', 'Chance to be up', 'Typical', 'Bad case (1 in 20)', 'Good case (1 in 20)', 'Drawdown (1 in 20)', `Deeper than ${R.max_dd_pct}%`, 'Margin call'],
    Object.entries(F).map(([k, v]) => `<tr><td>${k}</td><td><b>${v.up_pct}%</b></td><td class="${cls(v.median)}">${money(v.median)}</td><td class="${cls(v.p5)}">${money(v.p5)}</td><td class="pos">${money(v.p95)}</td><td>${money(-v.dd_p95)}</td>` +
      `<td class="${v.deep_dd_pct > 10 ? 'bad' : ''}">${v.deep_dd_pct}%</td><td class="${v.ruin_pct > 0 ? 'bad' : ''}">${v.ruin_pct}%</td></tr>`));
  const base = R.grid[0][0];
  h += `<h4>Daily guardrails at ${R.lots} lots - the EA's own InpDayLossUsd / InpDayTargetUsd (no new trades for the day once hit)</h4>
    <p class="note">Each cell is the whole history replayed with that daily stop and target: net, worst day, green days. Green = more net than no guardrails. "Apply" puts the size and both limits on the chart, ready for "Check in MT5".</p>` +
    `<table class="heat"><tr><th>daily stop ↓ · target →</th>${R.grid[0].map((c) => `<th>${c.target ? '+$' + c.target : 'none'}</th>`).join('')}</tr>` +
    R.grid.map((row) => `<tr><th>${row[0].stop ? '−$' + row[0].stop : 'none'}</th>${row.map((c) => { const d = c.net - base.net;
      return `<td style="background:${d > 0 ? 'rgba(0,230,118,.18)' : d < 0 ? 'rgba(255,82,82,.12)' : 'transparent'}"><b>${money(c.net)}</b><br><span class="k">worst day ${money(c.worst)} · ${c.green_pct}% green</span><br>` +
        `<button class="dexbtn sm" data-misgr="${R.lots}|${c.stop}|${c.target}">Apply</button></td>`; }).join('')}</tr>`).join('') + '</table>';
  return h + '</div>';
}
async function misPoll() {
  if (MIS.polling) return; MIS.polling = true;
  try { for (;;) { MIS.job = await api('/api/mission'); if (TAB.tt === 'mission') renderPanel('tt'); if (!MIS.job.running) break; await new Promise((r) => setTimeout(r, 700)); } } finally { MIS.polling = false; }
}
async function misOpen() {
  const j = await api('/api/mission').catch(() => ({}));
  if (j && j.jid) {
    MIS.job = j;
    if (j.result) { MIS.capital = j.result.capital; MIS.maxdd = j.result.max_dd_pct; }   // the form shows what the result was run with
    if (TAB.tt === 'mission') renderPanel('tt');
    if (j.running) misPoll();
  }
}
document.addEventListener('change', (e) => {
  const t = e.target;
  if (t.name === 'misMode') MIS.mode = t.value;
  const m = { misCap: 'capital', misRisk: 'risk', misLots: 'lots', misLev: 'lev', misDD: 'maxdd' }[t.id];
  if (m) MIS[m] = +t.value;
  if (t.id === 'misLab') MIS.withLab = t.checked;
  if (t.id === 'misLego' && !t.checked) MIS.lego = null;
});
document.addEventListener('click', async (e) => {
  const d = e.target.dataset || {};
  if (e.target.id === 'misGo') {
    const r = await api('/api/mission', { inputs: CUR, ds: SRC.ds === 'tv' ? 'year' : SRC.ds, capital: MIS.capital, mode: MIS.mode, lots: MIS.lots, risk_pct: MIS.risk, leverage: MIS.lev, max_dd: MIS.maxdd,
      lab: MIS.withLab && typeof labForm === 'function' ? labForm() : null, lego: MIS.lego || null });
    if (r.error) return toast('⚠ ' + esc(r.error));
    MIS.job = { running: true, phase: 'launching' }; renderPanel('tt'); misPoll();
  }
  if (d.misapply) { MIS.mode = 'lots'; MIS.lots = +d.misapply; renderPanel('tt'); $('#misGo').click(); }
  if (d.mislots) { CUR = { ...CUR, InpLots: d.mislots, InpRiskPct: '0' }; markForm(); scheduleSim(0); toast(`${d.mislots} lots are on the chart - "Check in MT5" to confirm, "Export to MT5" for the .set file.`); }
  if (d.misgr) {
    const [lots, stop, tgt] = d.misgr.split('|');
    CUR = { ...CUR, InpLots: lots, InpRiskPct: '0', InpDayLossUsd: stop, InpDayTargetUsd: tgt }; markForm(); scheduleSim(0);
    toast(`On the chart: ${lots} lots, daily stop $${stop}, daily target $${tgt}. Press "Check in MT5" to confirm it.`);
  }
});
