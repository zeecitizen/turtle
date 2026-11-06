// Risk Manager · Probe entry (EA v1.36, Zee 2026-10-27: "take a small 0.01 probe trade -> if the trade fails we loose little -> if the trade is
// going in our direction ... we increase the lotsize only then"). Sliders re-run the loaded setting with / without the probe; Apply puts the
// probe into the loaded setting (Overview, List of trades, MT5 all follow). Tester numbers are hypotheses - Verify in MT5.
const PROBE = { sets: null, res: null, tune: null, busy: false, tuning: false, seq: 0, timer: 0 };
const PROBE_SLIDERS = [
  ['InpProbeMode', 0, 2, 1, 'off · 1 = add once price moves our way · 2 = add once it dipped and came back'],
  ['InpProbeLots', 0.01, 0.5, 0.01, 'the probe: opened at the entry; the rest of InpLots waits'],
  ['InpProbeUsd', 0, 3, 0.05, '$ of price in our favour (from the probe\'s entry) that confirms the trade; 0 = back at the entry'],
  ['InpProbeDipUsd', 0.5, 12, 0.5, 'mode 2 only: the dip against us that must come first'],
];
function probeSets() {
  if (!PROBE.sets) {
    PROBE.sets = {};
    for (const [k] of PROBE_SLIDERS) PROBE.sets[k] = String(CUR[k] ?? DFL[k] ?? (k === 'InpProbeMode' ? 0 : 0));
    if (PROBE.sets.InpProbeMode === '0') PROBE.sets.InpProbeMode = '1';      // the card opens on the idea itself
  }
  return PROBE.sets;
}
function probeLabel(k, v) {
  if (k === 'InpProbeMode') return ['off', '1 · moves our way', '2 · dip, then back'][+v] || v;
  if (k === 'InpProbeLots') return (+v).toFixed(2) + ' lots';
  return '$' + (+v).toFixed(2);
}
function probeStat(t, s, ref) {
  if (!s) return `<div class="probe-col"><h5>${t}</h5><p class="note">running…</p></div>`;
  const d = (a, b, inv) => ref ? `<i class="${(inv ? b - a : a - b) >= 0 ? 'pos' : 'neg'}">${money(a - b)}</i>` : '';
  return `<div class="probe-col"><h5>${t}</h5>
    <p><span>Net</span><b class="${s.net >= 0 ? 'pos' : 'neg'}">${money(s.net)}</b>${ref ? d(s.net, ref.net) : ''}</p>
    <p><span>Win rate · trades</span><b>${s.wr}% · ${s.n}</b>${ref ? `<i>${(s.wr - ref.wr).toFixed(1)} pts</i>` : ''}</p>
    <p><span>Avg win / loss</span><b>${money(s.avg_win)} / <span class="neg">${money(s.avg_loss)}</span></b></p>
    <p><span>Worst loss</span><b class="neg">${money(s.worst)}</b>${ref ? d(s.worst, ref.worst) : ''}</p>
    <p><span>Drawdown</span><b>${money(-s.dd)}</b>${ref ? d(-s.dd, -ref.dd) : ''}</p>
    <p><span>Both halves</span><b>${money(s.train)} · ${money(s.test)}</b></p></div>`;
}
function probeBody() {
  const r = PROBE.res, on = r && r.on, off = r && r.off;
  let h = `<div class="probe-cols">${probeStat('Loaded setting · no probe', off)}${probeStat('With this probe', on, off)}</div>`;
  if (on && off) {
    const better = on.net > off.net, safer = on.worst > off.worst;
    h += `<p class="${better ? 'risk-good' : 'risk-warn'}">${better ? '✓' : '⚠'} The probe ${better ? 'adds' : 'costs'} <b>${money(on.net - off.net)}</b>,
      worst loss ${safer ? 'smaller' : 'bigger'} by ${money(Math.abs(on.worst - off.worst))}. Tester hypothesis on ${esc(SRC.ds)} — press Verify in MT5 before trusting it.</p>`;
  }
  if (PROBE.tune) {
    const o = PROBE.tune.off;
    h += `<h5>AUTO-TUNE · best confirmation distances (mode ${esc(probeSets().InpProbeMode)})</h5><div class="scroll"><table><tr><th>Confirm $</th><th>Dip $</th><th>Net</th><th>vs no probe</th><th>WR</th><th>Worst</th><th>DD</th><th></th></tr>` +
      PROBE.tune.rows.map((x, i) => `<tr><td>$${x.sets.InpProbeUsd}</td><td>${probeSets().InpProbeMode === '2' ? '$' + x.sets.InpProbeDipUsd : '–'}</td><td class="${x.stats.net >= 0 ? 'pos' : 'neg'}">${money(x.stats.net)}</td>` +
        `<td class="${x.stats.net >= o.net ? 'pos' : 'neg'}">${money(x.stats.net - o.net)}</td><td>${x.stats.wr}%</td><td class="neg">${money(x.stats.worst)}</td><td>${money(-x.stats.dd)}</td>` +
        `<td><button class="dexbtn sm" data-probe-pick="${i}">use</button></td></tr>`).join('') + '</table></div>';
  }
  return h;
}
function pProbe() {
  const s = probeSets(), applied = String(CUR.InpProbeMode ?? '0') !== '0';
  const sliders = PROBE_SLIDERS.map(([k, mn, mx, st, help]) => {
    const dim = k === 'InpProbeDipUsd' && s.InpProbeMode !== '2';
    return `<label class="risk-slider ${dim ? 'inactive' : ''}"><span class="risk-slider-title"><b>${k}</b><strong id="probeVal_${k}">${esc(probeLabel(k, s[k]))}</strong></span>
      <input type="range" data-probe="${k}" min="${mn}" max="${mx}" step="${st}" value="${esc(s[k])}"><span class="risk-slider-help">${esc(help)}</span></label>`;
  }).join('');
  return `<section class="risk-card probe-card"><div class="risk-head"><div><h4>01 · PROBE ENTRY · RISK SMALL UNTIL THE TRADE PROVES ITSELF</h4>
    <p>Open a small probe at the entry. The rest of your ${esc(CUR.InpLots || '')} lots join only when price confirms the trade.
    Same stop and target for everything. EA v1.36 inputs, so MT5 can verify it.</p></div>
    <div class="risk-actions"><button class="dexbtn" id="probeApply">✓ APPLY TO THE LOADED SETTING</button>
      <button class="dexbtn sm" id="probeTune" ${PROBE.tuning ? 'disabled' : ''}>${PROBE.tuning ? '⏳ tuning…' : '🎛 Auto-tune'}</button>
      ${applied ? '<button class="dexbtn sm" id="probeOff">Remove the probe</button>' : ''}
      <button class="dexbtn sm" id="probeMt5">Verify in MT5</button></div></div>
    ${applied ? `<p class="risk-good">✓ Applied: the loaded setting runs with probe mode ${esc(CUR.InpProbeMode)} (${esc(CUR.InpProbeLots)} lots, confirm $${esc(CUR.InpProbeUsd)}${CUR.InpProbeMode === '2' ? ', dip $' + esc(CUR.InpProbeDipUsd) : ''}). Overview and List of trades include it.</p>` : ''}
    <div class="risk-sliders">${sliders}</div><div id="probeBody">${probeBody()}</div><div id="probeMt5Out" class="note"></div></section>`;
}
function probeBase() { const b = { ...CUR }; for (const [k] of PROBE_SLIDERS) delete b[k]; return b; }
async function probeEval() {
  const seq = ++PROBE.seq;
  PROBE.res = null; const el = document.getElementById('probeBody'); if (el) el.innerHTML = probeBody();
  const r = await api('/api/probe_eval', { inputs: probeBase(), ds: SRC.ds, mode: SRC.mode, probe: probeSets() });
  if (seq !== PROBE.seq) return;
  if (r.error) { toast('⚠ Probe: ' + esc(r.error)); return; }
  PROBE.res = r; const e2 = document.getElementById('probeBody'); if (e2) e2.innerHTML = probeBody();
}
function probeRefresh() { if (TAB.tt === 'risk') renderPanel('tt'); probeEval(); }
document.addEventListener('input', (e) => {
  const k = e.target.dataset && e.target.dataset.probe;
  if (!k) return;
  probeSets()[k] = e.target.value;
  const v = document.getElementById('probeVal_' + k); if (v) v.textContent = probeLabel(k, e.target.value);
  clearTimeout(PROBE.timer); PROBE.timer = setTimeout(probeEval, 350);
});
document.addEventListener('click', async (e) => {
  const id = e.target.id, pick = e.target.dataset && e.target.dataset.probePick;
  if (pick != null && PROBE.tune) { Object.assign(probeSets(), PROBE.tune.rows[+pick].sets); probeRefresh(); return; }
  if (id === 'probeApply') {
    CUR = { ...CUR, ...probeSets() }; settingsTouched = true; markForm(); scheduleSim(0);
    toast('✓ Probe applied to the loaded setting'); setTimeout(() => { if (TAB.tt === 'risk') renderPanel('tt'); }, 50); return;
  }
  if (id === 'probeOff') { CUR = { ...CUR, InpProbeMode: '0' }; settingsTouched = true; markForm(); scheduleSim(0); setTimeout(() => renderPanel('tt'), 50); return; }
  if (id === 'probeTune') {
    PROBE.tuning = true; renderPanel('tt');
    const r = await api('/api/probe_tune', { inputs: probeBase(), ds: SRC.ds, mode: SRC.mode, probe: probeSets() });
    PROBE.tuning = false;
    if (r.error) toast('⚠ Probe tune: ' + esc(r.error)); else { PROBE.tune = r; if (r.rows.length) Object.assign(probeSets(), r.rows[0].sets); }
    probeRefresh(); return;
  }
  if (id === 'probeMt5') {
    const out = document.getElementById('probeMt5Out');
    const r = await api('/api/dexlab_mt5', { inputs: probeBase(), ds: SRC.ds, items: [{ key: 'probe_off', title: 'no probe', sets: { InpProbeMode: '0' } },
      { key: 'probe_' + Object.values(probeSets()).join('_'), title: 'probe ' + Object.entries(probeSets()).map(([k, v]) => k.replace('InpProbe', '') + ' ' + v).join(' · '), sets: probeSets() }] });
    if (out) out.textContent = r.error ? '⚠ ' + r.error : '⏳ MT5 is running both (2026, on the loaded dataset timeframe)…';
    if (!r.error) probeMt5Poll();
  }
});
async function probeMt5Poll() {
  const st = await api('/api/dexlab_mt5_status', { inputs: probeBase(), ds: SRC.ds });
  const out = document.getElementById('probeMt5Out');
  const rows = (st.results || []).filter((x) => x.key.startsWith('probe_')).slice(-6);
  if (out) out.innerHTML = (st.busy ? `⏳ ${esc(st.phase)} (${st.current}/${st.total})<br>` : '') + rows.map((x) => x.status === 'complete'
    ? `<b>MT5 · ${esc(x.title)}</b>: ${money(+x.net || 0)} · ${x.trades} trades · worst ${money(+x.largest_loss || 0)} · avg win ${money(+x.avg_win || 0)} / loss ${money(+x.avg_loss || 0)} · DD ${esc(x.dd)}`
    : `MT5 · ${esc(x.title)}: ${esc(x.error || x.status)}`).join('<br>');
  if (st.busy) setTimeout(probeMt5Poll, 4000);
}
