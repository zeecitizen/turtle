// Exit Lab's Validation (Zee 2026-10-22): every setting the Exit Lab's scan suggests - what it does, its result in the tester and in MT5,
// when it was last run, and whether MT5 matches the tester. Written by validation_run.py (invisible MT5 rig, 2026, 1-minute candles).
'use strict';
const VAL = { data: null, loading: false };
async function valLoad() {
  if (VAL.loading) return; VAL.loading = true;
  try { VAL.data = await api('/api/validation'); } catch (e) { VAL.data = { rows: [], count: 0, of: 0, comments: {} }; }
  VAL.loading = false; if (TAB.tt === 'validation') renderPanel('tt');
}
function pValidation() {
  if (!VAL.data) { valLoad(); return '<p class="note">Loading the validation…</p>'; }
  const D = VAL.data, rows = D.rows || [], C = D.comments || {};
  const ok = rows.filter((x) => x.match).length, bad = rows.length - ok;
  const running = D.count < D.of && D.of > 0;
  let h = `<div class="lab dex"><h3 class="dexh">✅ EXIT LAB'S VALIDATION · EVERY SUGGESTED SETTING, TESTED IN MT5</h3>
    <p class="note">MT5 against MT5: the primary save runs in MT5 once as the baseline; then each suggested change runs in MT5 (2026, 1-minute, real ticks).
    A change is <b>validated</b> when MT5's net goes up against the baseline. Trades and the tester are shown for reference only.</p>
    <div class="gauges">${valDial('VALIDATED', ok, 'g-up')}${valDial('DIFFERS', bad, bad ? 'g-dn' : '')}${valDial('TESTED', rows.length, '')}${valDial('OF', D.of || 0, '')}</div>`;
  if (running) h += `<div class="dexprog"><div class="dexprog-t">⚗️ TESTING EVERY SUGGESTED SETTING IN MT5 · ${D.count} of ${D.of}</div><div class="dexprog-bar"><i style="width:${Math.round(100 * D.count / Math.max(1, D.of))}%"></i></div><div class="dexprog-s">invisible rig · this page refreshes as results arrive</div></div>`;
  h += `<div class="bar"><button id="valRefresh" class="dexbtn sm">refresh</button></div>`;
  const L = D.loss || { rows: [], count: 0, of: 0 };
  h += `<h3 style="margin-top:14px">✂️ THE LOSS CUTTER'S SUGGESTIONS · VALIDATED IN MT5</h3>
    <p class="note">The loss cutter's own top suggestions for the primary save, run the same way (tester and MT5, 2026, 1-minute).
    ${L.count} of ${L.of || 0} tested.</p>` + valRows(L.rows || [], C);
  h += `<h3 style="margin-top:14px">🧠 EXIT RESEARCH LAB'S SCAN · EVERY SUGGESTED SETTING</h3>`;
  h += valRows(rows, C);
  return h + '</div>';
}
function valRows(rows, C) {
  return rows.map((x) => {
    const col = x.match ? '#00e676' : '#ff5252', mt = x.mt5 || {}, te = x.tester || {}, bl = x.baseline || {};
    return `<div class="sltest" style="--lamp:${col}"><div class="slhead" style="cursor:default"><span class="lamp"></span><b>${esc(x.label)}</b>
      <span class="sltag">${x.match ? 'VALIDATED IN MT5' : 'NOT IMPROVED IN MT5'}</span></div>
      <div class="slhl">${esc(C[x.key] || '')}</div>
      <div class="slbody"><div>suggested: <b>${esc(x.from)} → ${esc(x.to)}</b> <span class="k">(${esc(x.group)})</span></div>
      <div>MT5 baseline (primary save): <b class="${cls(bl.net || 0)}">${bl.net == null ? '–' : money(bl.net)}</b> · ${bl.trades ?? '–'} trades</div>
      <div>MT5 with the change: <b class="${cls(mt.net || 0)}">${mt.net == null ? 'no result' : money(mt.net)}</b> · ${mt.trades ?? '–'} trades · <b class="${cls(x.delta_mt5 || 0)}">${x.delta_mt5 == null ? '' : (x.delta_mt5 >= 0 ? '▲ ' : '▼ ') + money(x.delta_mt5)}</b></div>
      <div class="k">tester (for reference): ${te.trades} trades · ${money(te.net)}</div>
      <div class="k">last run ${esc(x.at || '')}${mt.run ? ' · MT5 report ' + esc(mt.run) : ''}</div></div></div>`;
  }).join('') || '<p class="note">No results yet.</p>';
}
function valDial(lbl, val, cls2) {
  return `<div class="gauge slg ${cls2}"><div class="acid"><b></b><i></i><i></i><i></i><i></i><i></i><i></i></div><div class="gv">${val}</div><div class="gl">${lbl}</div></div>`;
}
document.addEventListener('click', (e) => { if (e.target && e.target.id === 'valRefresh') valLoad(); });
