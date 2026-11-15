// game.js - Zee 2026-11-07: "a game settings page built into the TurtleTV UHV ... we can choose which setting we're having the game run on ...
// an entire table of the risk settings with ON/OFF ... the exact SL, TP, UHV, Breakout Candle etc core settings in an easy to read manner ...
// manage the entire game backend settings on 1 page" + "pick a saved setting from a list ... an 'apply to game' button".
var GAME = { data: null, pick: null, busy: false, adminEdit: null, msg: '' };

async function gameLoad() {
  try { GAME.data = await api('/api/game'); } catch (e) { GAME.data = { error: String(e) }; }
  if (GAME.pick == null && GAME.data && GAME.data.active) GAME.pick = GAME.data.active.file;
  if (GAME.pick == null && (SAVEDS || []).length) GAME.pick = SAVEDS[0].file;   // nothing applied yet: show the newest save
  if (TAB.tt === 'game') renderPanel('tt');
}

function gSaved(file) { return (SAVEDS || []).find((s) => s.file === file); }
function gInputsOf(file) { const s = gSaved(file); return s ? { ...DFL, ...(s.inputs || {}) } : null; }
function gNum(v) { const x = parseFloat(v); return isFinite(x) ? x : 0; }
function gOn(k, v) { return !same(String(v), String(DFL[k])); }
function gComment(k) { const L = Array.isArray(INPUTS) ? INPUTS : ((INPUTS && INPUTS.inputs) || []); const it = L.find((x) => x.name === k); return it ? (it.comment || '') : ''; }

// the risk measures, grouped by loss type (every filter the engine has; ON = differs from the engine default = acts)
const G_RISK = [
  ['Session & news', ['InpUhvNoClose', 'InpUhvFriCutAllNY', 'InpUhvFriCutNY', 'InpUhvLateUtcFrom', 'InpUhvHourFrom', 'InpUhvHourTo', 'InpUhvNewsNY', 'InpUhvHoliday', 'InpUhvSunOpenMins']],
  ['Spread / fill', ['InpUhvMaxTrigSpread', 'InpUhvMaxGapPips']],
  ['Risk manager (zones)', ['InpUhvRiskMgr', 'InpUhvSafeHumpsMin', 'InpUhvSafeHumpsMax', 'InpUhvSafeErMin', 'InpUhvSafeErMax', 'InpUhvSafeErBars', 'InpUhvSafeRangeAtr', 'InpUhvZStart', 'InpUhvZEnd', 'InpUhvZRange', 'InpUhvZSR', 'InpUhvZNews', 'InpUhvZClose', 'InpUhvZOpen', 'InpUhvHarvestWins']],
  ['Ranging', ['InpUhvBoxInside', 'InpUhvMaxFlips60', 'InpUhvMinErN', 'InpUhvMinSpanAtr', 'InpUhvRangeAtr', 'InpUhvMinAtrPips']],
  ['Trend shift', ['InpUhvShiftEma', 'InpUhvShiftStoch', 'InpUhvShiftAvwap']],
  ['Camel / structure', ['InpUhvV2Against', 'InpUhvNoLowerHigh', 'InpUhvStruct', 'InpUhvWickFake', 'InpUhvMinHumps', 'InpUhvMaxHumps', 'InpUhvFreshBreak', 'InpUhvBrokeHighs', 'InpUhvCounterAtr', 'InpUhvHtf5']],
  ['Support / resistance', ['InpUhvSellSup', 'InpUhvBuyRes', 'InpUhvWall', 'InpUhvSRAhead', 'InpUhvSRPips', 'InpUhvBigFig']],
  ['Exhausted / volatile', ['InpUhvMaxAtrPips', 'InpUhvSpikeAtr', 'InpUhvMaxRunAtr', 'InpUhvRunPips', 'InpUhvLoudBrk', 'InpUhvMaxSpan20Atr', 'InpUhvDeepRet']],
  ['Bad entry', ['InpUhvMinBrkRatio', 'InpUhvMinPos', 'InpUhvMinMoveAtr', 'InpUhvMaxStopPips', 'InpUhvMinVolRel', 'InpUhvMinTicks']],
  ['Saad filters (not in the game yet)', ['InpUhvSaad', 'InpUhvSaadShape', 'InpUhvSaadTrend', 'InpUhvSaadAdx', 'InpUhvSaadAtr', 'InpUhvSaadSession', 'InpUhvSaadSides', 'InpUhvSaadChop', 'InpUhvSaadSpread']],
];
const G_NOT_IN_GAME = new Set(['InpUhvSaad', 'InpUhvSaadShape', 'InpUhvSaadTrend', 'InpUhvSaadAdx', 'InpUhvSaadAtr', 'InpUhvSaadSession', 'InpUhvSaadSides',
  'InpUhvSaadChop', 'InpUhvSaadSpread', 'InpUhvLatency', 'InpUhvLossSecs', 'InpUhvMaxSecs', 'InpUhvHarvestWins']);

function gCore(I, coin) {
  const tp = gNum(I.InpUhvFixTp), sm = String(I.InpUhvStopMode), rows = [];
  const usd = (pips) => `$${(pips * 1e-4 * coin).toFixed(2)} per coin (${coin.toLocaleString()} EUR)`;
  rows.push(['Entry', gNum(I.InpUhvPreBreak) > 0 ? `PRE-BREAK: enters ${I.InpUhvPreBreak} pip before the UHV level is reached (the game does this too)` :
    String(I.InpUhvEntry) === '1' ? 'instant: the tick that crosses the UHV level' : 'when the breakout candle closes']);
  rows.push(['Take profit', tp > 0 ? `${tp} pip from the fill → ${usd(tp)}` : `${I.InpUhvRR} × the risk (R:R)`]);
  rows.push(['Stop loss', sm === '1' ? `${I.InpUhvSlBeyond} pips beyond the retracement's extreme (≈ ${(gNum(I.InpUhvSlBeyond) + 2).toFixed(0)} pips → ≈ ${usd(gNum(I.InpUhvSlBeyond) + 2)})` :
    sm === '2' ? `${I.InpUhvSlBeyond} pips beyond the breakout candle` : `${I.InpUhvSlPips} pips from the fill (fixed) → ${usd(gNum(I.InpUhvSlPips))}`]);
  rows.push(['Breakeven', gNum(I.InpUhvBeR) > 0 ? `stop to the entry at +${I.InpUhvBeR} R` : 'off']);
  rows.push(['Time exit', gNum(I.InpUhvMaxSecs) > 0 ? `close after ${I.InpUhvMaxSecs} s` : gNum(I.InpUhvLossSecs) > 0 ? `close losers after ${I.InpUhvLossSecs} s` : 'off (the player ejects)']);
  rows.push(['Tester fill delay', `${I.InpUhvLatency} s (tester only)`]);
  rows.push(['UHV detection', `camel swing ${I.InpDetCamPiv ?? '1'} · trend flips after ${I.InpDetCamConfirm ?? '1'} hump(s) · retracement swing ${I.InpDetPivot ?? '3'} candles · looks back ${I.InpDetRetraceBack ?? '20'} candles · trend read over ${I.InpDetTrendLook ?? '20'}`]);
  rows.push(['UHV candle shape', `body ≥ ${Math.round(100 * gNum(I.InpDetUhvBody ?? 0.5))}% of its range`]);
  rows.push(['Breakout candle shape', `body ≥ ${Math.round(100 * gNum(I.InpDetMomBody ?? 0.7))}% of its range · cooldown ${I.InpDetCooldown ?? '3'} candles between setups`]);
  return rows;
}

function pGame() {
  const D = GAME.data;
  let h = '<h3>🎮 Game settings - what the live game runs on</h3>';
  if (!D) { gameLoad(); return h + '<p class="note">Loading…</p>'; }
  if (!D.game_running) h += '<p class="warn">The game server (127.0.0.1:8790) is not answering - start it to apply settings.</p>';
  const L = D.live || {};
  h += `<div class="k">Game: ${esc(L.mode || '?')} · ${esc(L.symbol || '')} · phase ${esc(L.phase || '?')} · balance ${L.balance != null ? '$' + L.balance : '?'} · feed ${L.feed_ok ? '✅' : '⛔'}</div>`;
  // 1. the setting feeding the game
  const act = D.active;
  h += `<div class="lossblock" style="margin-top:8px"><b>Feeding the game now:</b> ${act ? `<b>${esc(act.file)}</b> - ${esc(act.name || '')} <span class="k">(applied ${esc(act.activated || '')})</span>` : "the game's own built-in rules (no Turtle TV setting applied)"}`;
  const opts = (SAVEDS || []).map((s) => `<option value="${esc(s.file)}" ${s.file === GAME.pick ? 'selected' : ''}>${esc(s.file)} - ${esc(String(s.name || '').slice(0, 110))}</option>`).join('');
  h += `<div class="bar" style="margin-top:6px"><select id="gPick" style="max-width:780px">${opts}</select>
    <button data-g="apply" class="dexbtn" ${GAME.busy ? 'disabled' : ''}>✅ Apply to game</button>
    <button data-g="own" class="dexbtn sm" ${GAME.busy || !act ? 'disabled' : ''}>Use the game's own rules</button>
    <button data-g="reload" class="dexbtn sm">↻ Refresh</button></div>`;
  if (GAME.msg) h += `<div class="k" style="margin-top:4px">${GAME.msg}</div>`;
  h += '<div class="k">The game re-reads the setting on its next breakout - no restart. Its entries, take profit and stop then come from this setting.</div></div>';
  // 2. core settings of the picked setting
  const I = gInputsOf(GAME.pick || (act && act.file));
  const coin = (D.live && D.admin && D.admin.running && D.admin.running.coin) || 5000;
  if (I) {
    h += `<h4 style="margin-top:12px">Core settings of <b>${esc(GAME.pick)}</b>${act && act.file === GAME.pick ? ' (feeding the game)' : ''}</h4><table class="t"><tbody>`;
    for (const [k, v] of gCore(I, coin)) h += `<tr><td style="width:180px"><b>${esc(k)}</b></td><td>${esc(v)}</td></tr>`;
    h += '</tbody></table>';
    // 3. the risk table
    h += '<h4 style="margin-top:12px">Risk measures (ON = this setting uses it)</h4><table class="t"><thead><tr><th>Loss type</th><th>Setting</th><th>ON / OFF</th><th>Value</th><th>What it does</th></tr></thead><tbody>';
    let nOn = 0;
    for (const [grp, keys] of G_RISK) {
      keys.filter((k) => k in DFL).forEach((k, i) => {
        const on = gOn(k, I[k]); if (on) nOn++;
        const ng = G_NOT_IN_GAME.has(k) && on;
        h += `<tr style="${on ? 'background:rgba(40,160,80,0.10)' : 'opacity:0.75'}"><td>${i === 0 ? '<b>' + esc(grp) + '</b>' : ''}</td><td>${esc(k.replace(/^Inp/, ''))}</td>` +
          `<td><b style="color:${on ? '#2e9e4f' : '#888'}">${on ? 'ON' : 'off'}</b>${ng ? ' <span class="neg">⚠ not in game</span>' : ''}</td><td>${esc(String(I[k]))}</td><td class="k">${esc(gComment(k))}</td></tr>`;
      });
    }
    h += `</tbody></table><div class="k">${nOn} risk measures ON.</div>`;
  }
  // 4. the game's own backend settings (its admin page)
  const A = D.admin && D.admin.admin, F = (D.admin && D.admin.fields) || [];
  if (A && A.profiles) {
    if (!GAME.adminEdit) GAME.adminEdit = JSON.parse(JSON.stringify(A));
    const E = GAME.adminEdit, prof = E.profiles[E.active] || {};
    h += `<h4 style="margin-top:12px">Game backend settings (the game's admin page) · symbol <select id="gSym">${Object.keys(E.profiles).map((k) => `<option ${k === E.active ? 'selected' : ''}>${esc(k)}</option>`).join('')}</select></h4>`;
    h += '<table class="t"><thead><tr><th>Setting</th><th>Value</th><th>Meaning</th></tr></thead><tbody>';
    for (const [key, label, help, typ] of F) {
      if (!(key in prof)) continue;
      const val = prof[key], v = Array.isArray(val) ? val.join(', ') : val;
      const inp = typ === 'bool' || typeof val === 'boolean' ? `<input type="checkbox" data-gadm="${esc(key)}" ${val ? 'checked' : ''}>`
        : `<input data-gadm="${esc(key)}" value="${esc(String(v))}" style="width:160px">`;
      h += `<tr><td>${esc(label)}</td><td>${inp}</td><td class="k">${esc(help)}</td></tr>`;
    }
    h += `</tbody></table><div class="bar"><button data-g="adminsave" class="dexbtn">💾 Save game settings</button>
      <button data-g="adminapply" class="dexbtn sm">⚙ Apply now (rebuilds the game; never during a round)</button></div>`;
  }
  return h;
}

document.addEventListener('change', (e) => {
  if (e.target.id === 'gPick') { GAME.pick = e.target.value; GAME.msg = ''; renderPanel('tt'); }
  if (e.target.id === 'gSym' && GAME.adminEdit) { GAME.adminEdit.active = e.target.value; renderPanel('tt'); }
  const k = e.target.dataset && e.target.dataset.gadm;
  if (k && GAME.adminEdit) {
    const prof = GAME.adminEdit.profiles[GAME.adminEdit.active], old = prof[k];
    let v = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    if (Array.isArray(old)) v = String(v).split(',').map((x) => parseFloat(x)).filter((x) => isFinite(x));
    else if (typeof old === 'number') { const n = parseFloat(v); if (isFinite(n)) v = n; }
    prof[k] = v;
  }
});
document.addEventListener('click', async (e) => {
  const b = e.target.closest('[data-g]'); if (!b) return;
  const a = b.dataset.g;
  if (a === 'reload') { GAME.adminEdit = null; GAME.msg = ''; await gameLoad(); return; }
  GAME.busy = true; renderPanel('tt');
  try {
    if (a === 'apply') {
      const r = await api('/api/game_apply', { file: GAME.pick });
      GAME.msg = r.ok ? `✅ <b>${esc(GAME.pick)}</b> now feeds the game's entries.` : `⚠ ${esc(r.why || 'failed')}`;
    }
    if (a === 'own') { const r = await api('/api/game_apply', { file: '' }); GAME.msg = r.ok ? "The game is back on its own built-in rules." : '⚠ failed'; }
    if (a === 'adminsave') { const r = await api('/api/game_admin', { admin: GAME.adminEdit }); GAME.msg = r.ok ? '💾 Game settings saved - press Apply now to use them.' : `⚠ ${esc(r.why || r._error || 'not saved')}`; }
    if (a === 'adminapply') { const r = await api('/api/game_admin_apply', {}); GAME.msg = r.ok ? '⚙ The game rebuilt with the saved settings.' : `⚠ ${esc(r.why || r._error || 'not applied')}`; }
  } finally { GAME.busy = false; GAME.adminEdit = a === 'adminsave' || a === 'adminapply' ? null : GAME.adminEdit; await gameLoad(); }
});
