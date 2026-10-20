// Turtle TV Exit Lab - Claude's Exit Research Lab (the last section). Zee 2026-10-21: "visualizes the current setup. Then shows visually on drawing
// the profit if we drag diff things like drag the ATR slider, or choose an R:R ... i want it to be a claude intelligence ai based lab".
'use strict';
const RS = { sets: {}, reports: null, job: null, q: 'Why do my winners give back so much of their best move? Find the mechanism and design a better exit.' };
const SLIDERS = [
  { id: 'sl', label: 'Stop (x ATR)', min: 1, max: 30, step: 0.1, get: () => +(RS.sets.InpSlAtrMult || CUR.InpSlAtrMult), set: (v) => { RS.sets.InpSlAtrMult = String(v); }, ea: true },
  { id: 'tg', label: 'Target R:R (0 = the EA’s EMA target)', min: 0, max: 30, step: 0.25, get: () => (+LABS.form.tgt === 2 ? +LABS.form.tgt_k : 0),
    set: (v) => { if (v > 0) { LABS.form.tgt = 2; LABS.form.tgt_k = v; } else if (+LABS.form.tgt === 2) LABS.form.tgt = 0; } },
  { id: 'tr', label: 'Trail (x ATR behind the best, 0 = off)', min: 0, max: 30, step: 0.25, get: () => (+LABS.form.tr === 2 ? +LABS.form.tr_k : 0),
    set: (v) => { if (v > 0) { LABS.form.tr = 2; LABS.form.tr_k = v; } else if (+LABS.form.tr === 2) LABS.form.tr = 0; } },
  { id: 'ta', label: 'Trail starts at +R', min: 0, max: 30, step: 0.25, get: () => +LABS.form.tr_act, set: (v) => { LABS.form.tr_act = v; } },
  { id: 'be', label: 'Breakeven at +R (0 = off)', min: 0, max: 30, step: 0.25, get: () => +LABS.form.be_r, set: (v) => { LABS.form.be_r = v; } },
  { id: 'p1', label: 'Half off at +R (0 = off)', min: 0, max: 30, step: 0.25, get: () => +LABS.form.p1_r, set: (v) => { LABS.form.p1_r = v; LABS.form.p1_frac = 0.5; } },
];
function spark(trades) {                                           // the equity curve of the tested exit
  if (!trades || !trades.length) return '';
  const t = trades.slice().sort((a, b) => a[4] - b[4]); let c = 0; const ys = t.map((x) => (c += x[6]));
  const W = 440, H = 70, lo = Math.min(0, ...ys), hi = Math.max(1, ...ys), X = (i) => 6 + (i / Math.max(1, ys.length - 1)) * (W - 12), Y = (v) => H - 6 - ((v - lo) / (hi - lo)) * (H - 12);
  return `<svg viewBox="0 0 ${W} ${H}" class="dexsvg" style="max-width:580px"><rect x="1" y="1" width="${W - 2}" height="${H - 2}" rx="10" class="dexbox" style="stroke:#ff9800;stroke-width:2"/>` +
    `<line x1="6" x2="${W - 6}" y1="${Y(0)}" y2="${Y(0)}" stroke="#546e7a" stroke-dasharray="3 3"/><polyline points="${ys.map((v, i) => `${X(i)},${Y(v)}`).join(' ')}" fill="none" stroke="${c >= 0 ? '#00e676' : '#ff5252'}" stroke-width="2"/>` +
    `<text x="10" y="16" class="lt chipt">EQUITY OF THIS EXIT · ${money(c)}</text></svg>`;
}
const T0describe = () => (LABS.test && LABS.test.describe) || 'lab exit';
function gauges(T) {                                              // the result of the levers as lab dials: WR, PF, net, drawdown, trades, avg win / loss
  const s = T.stats.all, b = T.base.all, dial = (lbl, val, now, base, good, fmt) => {
    const d = now - base, up = good === 'up' ? d > 0 : d < 0, same = Math.abs(d) < 1e-9;
    return `<div class="gauge ${same ? '' : up ? 'g-up' : 'g-dn'}"><div class="acid"><b></b><i></i><i></i><i></i><i></i><i></i><i></i></div><div class="gv">${val}</div><div class="gl">${lbl}</div><div class="gd">${same ? 'same as yours' : (d > 0 ? '▲ ' : '▼ ') + fmt(Math.abs(d))}</div></div>`; };
  return `<div class="gauges">` + dial('WIN RATE', s.wr + '%', s.wr, b.wr, 'up', (x) => x.toFixed(1) + ' pts') + dial('PROFIT FACTOR', s.pf, s.pf, b.pf, 'up', (x) => x.toFixed(2)) +
    dial('NET', money(T.stats.total), T.stats.total, T.base.total, 'up', (x) => '$' + Math.round(x).toLocaleString()) + dial('MAX DRAWDOWN', money(-s.dd), s.dd, b.dd, 'down', (x) => '$' + Math.round(x).toLocaleString()) +
    dial('TRADES', s.n, s.n, b.n, 'up', (x) => String(Math.round(x))) + dial('AVG WIN / LOSS', `${money(s.avg_win)}<br>${money(s.avg_loss)}`, s.avg_win / Math.max(1, -s.avg_loss), b.avg_win / Math.max(1, -b.avg_loss), 'up', (x) => x.toFixed(2) + '× ratio') + '</div>';
}
function leverTips() {                                           // "Win 25% winrate by moving this slider to X": the best value of every lever, as lab buttons
  const W = LABS.sweep, key = JSON.stringify([labForm(), RS.sets]), J = LABS.main;
  const busy = J && J.running && J.action === 'sweep', pct = busy && J.total ? Math.round((100 * J.progress) / J.total) : 3;
  let h = `<div class="bar" style="margin-top:8px"><button data-rs="scan" class="dexbtn" ${busy ? 'disabled' : ''}>${busy ? '⏳ SCANNING…' : '🔬 SCAN THE LEVERS'}</button></div>`;
  if (busy) h += `<div class="dexprog"><div class="dexprog-t">⚗️ THE LAB IS TESTING EVERY LEVER · ${pct}%</div><div class="dexprog-bar"><i style="width:${pct}%"></i></div>
    <div class="dexprog-s">${esc(J.phase || 'warming up the beakers')} · ${J.progress || 0} of ${J.total || '…'} runs · ${J.seconds || 0} s</div></div>`;
  if (!W || !W.levers) return h + '<div class="k">tries every value of every lever on the data and offers the ones that raise the win rate, the profit factor or the net</div>';
  if (RS.scanKey !== key) h += '<p class="warn">the levers moved since the scan - scan again for fresh suggestions</p>';
  const now = W.now, names = { sl: 'Stop', tg: 'Target R:R', tr: 'Trail ATR', ta: 'Trail starts', be: 'Breakeven', p1: 'Half off' }, btn = [];
  for (const [lv, rows] of Object.entries(W.levers)) {
    const ok = rows.filter((r) => !r.stuck && r.n >= 20);
    const bw = ok.slice().sort((a, b) => b.wr - a.wr)[0], bn = ok.slice().sort((a, b) => b.net - a.net)[0], bp = ok.slice().sort((a, b) => b.pf - a.pf)[0];
    if (bw && bw.wr > now.wr + 0.4) btn.push([bw.wr - now.wr, `🧪 Win rate <b>${bw.wr}%</b> (now ${now.wr}%): ${names[lv]} → <b>${bw.v}</b> <span class="k">net ${money(bw.net)}</span>`, lv, bw.v]);
    if (bn && bn.net > now.net + 1000) btn.push([(bn.net - now.net) / 1e4, `💰 Net <b>${money(bn.net)}</b> (now ${money(now.net)}): ${names[lv]} → <b>${bn.v}</b> <span class="k">WR ${bn.wr}%</span>`, lv, bn.v]);
    if (bp && bp.pf > now.pf + 0.02 && bp !== bn) btn.push([(bp.pf - now.pf) * 10, `⚗️ Profit factor <b>${bp.pf}</b> (now ${now.pf}): ${names[lv]} → <b>${bp.v}</b> <span class="k">net ${money(bp.net)}</span>`, lv, bp.v]);
  }
  if (!btn.length) return h + '<p class="note">No lever beats the exit on the bench on its own - it already sits on its best values.</p>';
  return h + btn.sort((a, b) => b[0] - a[0]).map(([, txt, lv, v]) => `<button class="labsug" data-sug="${lv}|${v}">${txt}</button>`).join('');
}
function labTips(ea) {                                           // lab suggestions: the bubbling flask lights up when a lever reaches where they apply
  const st = +(ea.InpSlAtrMult || 0), far = Math.max(+LABS.form.tgt === 2 ? +LABS.form.tgt_k : 0, +LABS.form.tr === 2 ? +LABS.form.tr_k : 0, +LABS.form.tr_act, +LABS.form.be_r, +LABS.form.p1_r);
  const tip = (on, html) => `<div class="flasktip ${on ? 'on' : ''}"><span class="flask">⚗️<i></i><i></i><i></i></span><div>${html}</div></div>`;
  return `<div class="k" style="margin-top:8px;font:bold 11px 'Courier New',monospace;color:#ffd740">LAB SUGGESTIONS</div>` +
    tip(st >= 10, `<b>Large stops change which trades happen.</b> A stop of 10+ × ATR is often wider than your InpMaxRiskUsd ($${CUR.InpMaxRiskUsd} on your settings), so the EA skips those setups and the trade count drops.`) +
    tip(far >= 20, `<b>Very far targets or trails never fire.</b> At 20–30R almost every trade ends at the stop, the fallback or the day-close cut instead. If the result shows "never closed", lower it or add a time limit.`);
}
function labResearch() {
  const T = LABS.test, f = labForm(), lab = Object.fromEntries(Object.entries(f).filter(([k, v]) => k !== 'pess' && Number(v) !== Number(LABS.spec.default[k])));
  const ea = { ...CUR, ...RS.sets };
  if (!RS.formFromX) { RS.formFromX = true; const x = labFromX(CUR); if (x) LABS.form = { ...LABS.spec.default, ...x }; }   // the bench starts from your exit
  const key = JSON.stringify([diffDfl(CUR), SRC.ds]);                // settings loaded / changed since the bench last ran: run it again on them
  if ((!T || stale(T)) && RS.ranFor !== key && !(LABS.quick && LABS.quick.running)) { RS.ranFor = key; setTimeout(() => labStart('test', { lab: labForm(), sets: RS.sets }), 0); }
  let h = `<section class="dexlab"><h3 class="dexh">🧠 CLAUDE'S EXIT RESEARCH LAB</h3> <span class="k">drag a lever: the exit re-runs on the data and the drawing shows what it made</span>
    <div class="row" style="gap:14px;margin-top:8px;align-items:flex-start"><div style="flex:1 1 440px;max-width:580px">${labSvg(exitParts(ea, Object.keys(lab).length ? { ...LABS.spec.default, ...f } : null), 'THE EXIT ON THE BENCH', '#ff9800')}`;
  if (T) {
    const s = T.stats, b = T.base;
    h += `${stale(T) ? '<p class="warn">⏳ re-running on the settings on screen…</p>' : ''}<div class="dexres">${LABS.quick && LABS.quick.running ? '⏳ running…' : ''} <b class="${cls(s.total - b.total)}">${money(s.total)}</b> vs yours ${money(b.total)} ·
      WR <b>${s.all.wr}%</b> (yours ${b.all.wr}%) · ${labLabels()[0]} ${money(s.train.net)} · ${labLabels()[1]} ${money(s.test.net)}${s.stuck ? ' · <span class="bad">a trade never closed</span>' : ''}</div>${gauges(T)}${spark(T.trades)}`;
  }
  h += `</div><div class="levers dexpanel">${SLIDERS.filter((x) => !x.ea || String(CUR.InpSlMode) === '1').map((x) => { const v = x.get();
    return `<label class="lever"><span>${esc(x.label)} <b id="lv_${x.id}">${v}</b>${x.ea ? ' <span class="tag ea">EA</span>' : ''}</span><input type="range" data-lever="${x.id}" min="${x.min}" max="${x.max}" step="${x.step}" value="${v}"></label>`; }).join('')}
    <div class="bar"><button data-rs="save" class="dexbtn">💾 SAVE &amp; APPLY THIS EXIT</button><button data-rs="reset">Back to your exit</button></div>${leverTips()}${labTips(ea)}</div></div>`;
  const J = RS.job;
  h += `<h4 style="margin-top:14px">Ask Claude to research your exit</h4><div class="askBox" style="max-width:980px"><textarea id="rsQ" rows="2">${esc(RS.q)}</textarea>
    <button data-rs="go" class="dexbtn" ${J && J.running ? 'disabled' : ''}>${J && J.running ? '⏳ ' + esc(J.phase || 'researching') : '🧠 Research it'}</button></div>
    <p class="note">Claude runs the Exit Lab itself: it studies which trades give back and why, writes hypotheses, designs exits from them and tests each one. Every proposal is then re-tested here
    independently. Several minutes. Results are hypotheses until MT5 confirms them.</p>`;
  if (J && J.error) h += `<p class="warn">⚠ ${esc(J.error)}</p>`;
  for (const r of RS.reports || []) {
    const [LA, LB] = r.labels || labLabels(), b = r.base;
    h += `<details class="rsrep" ${r === RS.reports[0] ? 'open' : ''}><summary><b>${esc(r.at)}</b> · ${esc(r.question.slice(0, 90))} <span class="k">(${r.ds === 'm15' ? '4 years' : '2026'})</span></summary>
      <div class="crt" style="white-space:pre-wrap;margin:6px 0">${esc(r.report)}</div>` +
      table(['Claude’s proposal', 'The idea', LA, LB, 'Total', 'vs yours', 'WR', ''], (r.proposals || []).map((p, i) => { const v = p.verified || {};
        if (!v.train) return `<tr><td class="l">${esc(p.name)}</td><td class="l" colspan="7">could not be tested</td></tr>`;
        const both = v.train.net > b.train.net && v.test.net > b.test.net;
        return `<tr class="${both ? 'both' : ''}"><td class="l"><b>${esc(p.name)}</b><br><span class="k">${esc(p.describe || '')}</span></td><td class="l">${esc(p.philosophy || '')}</td>` +
          `<td>${money(v.train.net)}</td><td class="${cls(v.test.net - b.test.net)}">${money(v.test.net)}</td><td><b>${money(v.total)}</b></td><td class="${cls(v.total - b.total)}">${money(v.total - b.total)}</td>` +
          `<td>${v.wr}% <span class="k">(${b.wr}%)</span></td><td>${v.stuck ? '<span class="bad">never closed</span>' : `<button data-rsload="${esc(r.id)}|${i}">Load + test</button>`}</td></tr>`; })) + '</details>';
  }
  return h + '</section>';
}
async function saveExit() {                                     // the levers' exit becomes the EA's settings (v1.30 InpX*), on the chart, saved
  const box = document.createElement('div'); box.id = 'saveBox';
  const step = (pct, txt) => { box.innerHTML = `<div class="crt" style="min-width:360px"><div class="crth">💾 SAVING YOUR EXIT</div><div>${txt}</div><div class="prog" style="width:100%;margin-top:8px"><i style="width:${pct}%"></i></div></div>`; };
  document.body.appendChild(box); step(10, 'turning the exit into EA settings…');
  const f = labForm();
  CUR = { ...CUR, ...RS.sets, ...labToX(f) }; RS.sets = {}; ACTIVE_LAB = null; markForm();
  await new Promise((r) => setTimeout(r, 250)); step(40, 'running it on the chart…');
  await runSim();
  step(75, 'saving it with its result…');
  const r = await api('/api/save', { inputs: CUR, ds: SRC.ds, mode: SRC.mode, result: TT ? TT.year : null });
  await loadSaved();
  step(100, `<b>Saved!</b> as ${esc(r.name)} - it is your exit now (EA v1.30 settings): Check in MT5 / Export to MT5 work as usual.`);
  setTimeout(() => box.remove(), 2600);
}
async function rsLoad() { RS.reports = await api('/api/exitlab_research').catch(() => []); if (TAB.tt === 'lab') renderPanel('tt'); }
document.addEventListener('input', (e) => {
  const id = e.target.dataset && e.target.dataset.lever;
  if (id) { const x = SLIDERS.find((s) => s.id === id); x.set(+e.target.value); const o = document.getElementById('lv_' + id); if (o) o.textContent = e.target.value; }
});
document.addEventListener('change', (e) => {
  if (!(e.target.dataset && e.target.dataset.lever)) return;
  LABS.goResult = false;
  labStart('test', { lab: labForm(), sets: RS.sets });               // the exit on the bench, with the levers
});
document.addEventListener('click', async (e) => {
  const d = e.target.dataset || {};
  if (d.rs === 'save') saveExit();
  if (d.rs === 'scan') { RS.scanKey = JSON.stringify([labForm(), RS.sets]); LABS.main = { action: 'sweep', running: true, phase: 'warming up the beakers', progress: 0, total: 0, seconds: 0 }; renderPanel('tt'); labStart('sweep', { lab: labForm(), sets: RS.sets }); }
  if (d.sug) { const [lv, v] = d.sug.split('|'); SLIDERS.find((s) => s.id === lv).set(+v); RS.scanKey = JSON.stringify([labForm(), RS.sets]); labStart('test', { lab: labForm(), sets: RS.sets }); }
  if (d.rs === 'reset') { RS.sets = {}; LABS.form = { ...LABS.spec.default }; labStart('test', { lab: labForm() }); }
  if (d.rs === 'go') {
    RS.q = ($('#rsQ').value || '').trim() || RS.q;
    const r = await api('/api/exitlab_research', { inputs: CUR, ds: SRC.ds === 'tv' ? 'year' : SRC.ds, question: RS.q });
    if (r.error) return toast('⚠ ' + esc(r.error));
    RS.job = { running: true, phase: 'starting' }; renderPanel('tt');
    for (;;) {
      await new Promise((res) => setTimeout(res, 5000));
      const j = await api('/api/hyp_job?id=' + r.id).catch(() => null);
      if (!j) continue;
      RS.job = j;
      if (!j.running) break;
      if (TAB.tt === 'lab' && !labBusyUi()) renderPanel('tt');
    }
    await rsLoad();
    toast(RS.job.error ? '⚠ ' + esc(RS.job.error) : 'Claude’s research is in - at the end of the Exit Lab.', 12000);
  }
  if (d.rsload) {
    const [id, i] = d.rsload.split('|'), p = (RS.reports.find((r) => r.id === id) || {}).proposals[+i];
    LABS.form = { ...LABS.spec.default, ...p.lab }; RS.sets = { ...(p.sets || {}) }; labStart('test', { lab: labForm(), sets: RS.sets });
  }
});
