// Turtle TV Tester - the Machine Learning tab (monitor/saad_view/ml.py). Zee 2026-10-21: "We should be able to run an ML algo and see its winrate.
// have all types of ML algos". Meta-labelling: a model decides which of the EA's own trades to take; trained on the first half, judged on the unseen half.
'use strict';
const MLS = { algos: null, picked: null, thr: 0.5, job: null, polling: false };
async function mlOpen() {
  if (!MLS.algos) { const s = await api('/api/ml_algos'); MLS.algos = s.algos; MLS.picked = new Set(s.algos); }
  const j = await api('/api/ml').catch(() => ({}));
  if (j && j.jid) MLS.job = j;
  if (TAB.tt === 'ml') renderPanel('tt');
  if (MLS.job && MLS.job.running) mlPoll();
}
async function mlPoll() {
  if (MLS.polling) return; MLS.polling = true;
  try { for (;;) { MLS.job = await api('/api/ml'); if (TAB.tt === 'ml') renderPanel('tt'); if (!MLS.job.running) break; await new Promise((r) => setTimeout(r, 700)); } } finally { MLS.polling = false; }
}
function mlCurve(c, base) {                                       // unseen-half net by threshold, against taking every trade
  const W = 170, H = 40, vals = c.map((x) => x.test.net), lo = Math.min(0, base, ...vals), hi = Math.max(1, base, ...vals), X = (i) => 3 + (i / (c.length - 1)) * (W - 6), Y = (v) => H - 3 - ((v - lo) / (hi - lo)) * (H - 6);
  return `<svg width="${W}" height="${H}" style="background:var(--panel);border-radius:4px"><line x1="3" x2="${W - 3}" y1="${Y(base)}" y2="${Y(base)}" stroke="#787b86" stroke-dasharray="3 3"/>` +
    `<polyline points="${vals.map((v, i) => `${X(i)},${Y(v)}`).join(' ')}" fill="none" stroke="#ffb74d" stroke-width="1.6"/><title>unseen-half net for thresholds 0.30 to 0.70 (dashed: all trades)</title></svg>`;
}
function pML() {
  if (!MLS.algos) { mlOpen(); return '<p class="note">Loading…</p>'; }
  const J = MLS.job, R = J && J.result;
  let h = `<div class="lab"><p class="note"><b>Machine learning on the EA's trades</b> (meta-labelling, like VSISA's ML filters). The EA keeps finding its setups; a model learns, from what
    was known at each entry (the setup candle, EMAs, ADX, ATR, recent returns, the hour, the range box…), whether that trade will win - and only the trades it trusts are taken.
    Trained on the first half, judged on the <b>unseen</b> half. Data: ${SRC.ds === 'm15' ? 'Blueberry 2023 → now (4 years)' : '2026 only - too few trades to learn from; use the 4 years'}. Python: a hypothesis until it runs in MT5.</p>
    <div class="bar">${MLS.algos.map((a) => `<label class="tog"><input type="checkbox" data-mla="${esc(a)}" ${MLS.picked.has(a) ? 'checked' : ''}> ${esc(a)}</label>`).join('')}</div>
    <div class="bar"><label>take a trade when the model's win chance ≥ <b id="mlThrV">${MLS.thr.toFixed(2)}</b> <input type="range" id="mlThr" min="0.3" max="0.7" step="0.025" value="${MLS.thr}"></label>
    <button id="mlGo" class="primary" ${J && J.running ? 'disabled' : ''}>🤖 Train &amp; test ${MLS.picked.size} algorithm${MLS.picked.size === 1 ? '' : 's'}</button></div>`;
  if (J && J.running) h += `<p class="note">⏳ ${esc(J.phase)} · ${J.progress}/${J.total} · ${J.seconds} s</p>`;
  if (J && J.error) h += `<p class="warn">⚠ ${esc(J.error)}</p>`;
  if (!R) return h + '</div>';
  const [LA, LB] = R.labels, B = R.base;
  h += `<p class="note">${R.n_train} trades to learn from (${LA}, ${R.wr_train}% winners) · ${R.n_test} unseen trades (${LB}, ${R.wr_test}% winners).
    Taking every trade: ${LB} <b>${B.test.wr}% · ${money(B.test.net)}</b>. AUC 0.5 = a coin flip, 1.0 = perfect; a model whose ${LA} AUC is far above its ${LB} AUC has memorised the past.</p>`;
  const rows = R.results.slice().sort((a, b) => b.at_thr.test.net - a.at_thr.test.net).map((r) => {
    const t = r.at_thr.test, c = r.chosen, better = t.net > B.test.net, wrUp = t.wr > B.test.wr;
    return `<tr class="${better ? 'both' : ''}"><td class="l"><b>${esc(r.algo)}</b> <span class="k">${r.seconds}s</span></td><td>${r.auc_train} → <b class="${r.auc_test >= 0.6 ? 'good' : r.auc_test < 0.53 ? 'bad' : ''}">${r.auc_test}</b></td>` +
      `<td>${t.n}</td><td class="${wrUp ? 'good' : 'bad'}"><b>${t.wr}%</b></td><td class="${cls(t.net - B.test.net)}">${money(t.net)}</td><td>${t.pf}</td>` +
      `<td class="k">${c.thr} → ${c.test.n} · ${c.test.wr}% · ${money(c.test.net)}</td><td>${mlCurve(r.curve, B.test.net)}</td></tr>`;
  });
  h += `<div class="scroll" style="max-height:560px">` + table(['Algorithm', `AUC ${LA} → ${LB}`, `${LB} trades taken`, 'Win rate', 'Net', 'PF', `threshold chosen on ${LA} only → ${LB}`, 'net by threshold'], rows) + '</div>';
  if (R.importance && R.importance.features) {
    const mx = Math.max(1e-9, ...R.importance.features.map((f) => f.importance));
    h += `<h4>What ${esc(R.importance.algo)} (best unseen AUC) looks at</h4>` + table(['Feature', 'Importance on the unseen half'], R.importance.features.slice(0, 10).map((f) =>
      `<tr><td class="l">${esc(f.feature)}</td><td style="text-align:left"><span style="display:inline-block;height:9px;width:${Math.max(1, (240 * Math.max(0, f.importance)) / mx)}px;background:#2962ff;border-radius:3px"></span> ${f.importance}</td></tr>`));
  }
  return h + '</div>';
}
document.addEventListener('change', (e) => {
  const a = e.target.dataset && e.target.dataset.mla;
  if (a) { if (e.target.checked) MLS.picked.add(a); else MLS.picked.delete(a); renderPanel('tt'); }
});
document.addEventListener('input', (e) => { if (e.target.id === 'mlThr') { MLS.thr = +e.target.value; $('#mlThrV').textContent = MLS.thr.toFixed(2); } });
document.addEventListener('click', async (e) => {
  if (e.target.id !== 'mlGo') return;
  const r = await api('/api/ml', { inputs: CUR, ds: SRC.ds === 'tv' ? 'year' : SRC.ds, algos: [...MLS.picked], thr: MLS.thr });
  if (r.error) return toast('⚠ ' + esc(r.error));
  MLS.job = { running: true, phase: 'starting', progress: 0, total: MLS.picked.size, seconds: 0 }; renderPanel('tt'); mlPoll();
});
