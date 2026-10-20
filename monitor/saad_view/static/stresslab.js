// Turtle TV Tester - the Stress Lab (monitor/saad_view/stress.py, 32 robustness tests). Zee 2026-10-21: "just like we have an Exit lab can u have the
// stress test lab where we run all kinds of stress tests (we already built the code for them)".
'use strict';
const SL = { st: null, polling: false, filter: 'all', open: {} };
const CAT = { I: ['🔬', 'Is the edge real, or fitted to the past?'], II: ['🎛️', 'Do the settings sit on a plateau?'], III: ['⚙️', 'Does it survive worse execution?'],
  IV: ['🌪️', 'Does it survive other markets and noisy prices?'], V: ['💰', 'Can the account survive it?'], VI: ['🧾', 'Is the test itself honest?'] };
const LAMP = { PASS: ['#00e676', 'PASS'], WARN: ['#ffd740', 'WARN'], FAIL: ['#ff5252', 'FAIL'], 'N/A': ['#78909c', 'N/A'] };
async function slOpen() { SL.st = await api('/api/stress').catch(() => null); if (TAB.tt === 'stress') renderPanel('tt'); if (SL.st && SL.st.running) slPoll(); }
async function slPoll() {
  if (SL.polling) return; SL.polling = true;
  try { for (;;) { SL.st = await api('/api/stress'); if (TAB.tt === 'stress') renderPanel('tt'); if (!SL.st.running) break; await new Promise((r) => setTimeout(r, 800)); } } finally { SL.polling = false; }
}
function slHist(H) {                                              // a histogram, with the real strategy's value marked
  const W = 420, Hh = 120, n = H.counts.length, mx = Math.max(1, ...H.counts), lo = H.edges[0], hi = H.edges[H.edges.length - 1], X = (v) => 6 + ((v - lo) / Math.max(1e-9, hi - lo)) * (W - 12);
  let s = `<svg viewBox="0 0 ${W} ${Hh}" class="crtsvg" style="max-width:460px;background:#03140b;border-radius:8px">`;
  H.counts.forEach((c, i) => { const x0 = X(H.edges[i]), x1 = X(H.edges[i + 1]), h = ((Hh - 26) * c) / mx; s += `<rect x="${x0 + 0.5}" y="${Hh - 16 - h}" width="${Math.max(1, x1 - x0 - 1)}" height="${h}" fill="#26a69a"><title>${H.edges[i]} … ${H.edges[i + 1]}: ${c}</title></rect>`; });
  if (H.mark != null) s += `<line x1="${X(H.mark)}" x2="${X(H.mark)}" y1="6" y2="${Hh - 14}" stroke="#ffd740" stroke-width="2" stroke-dasharray="4 2"/><text x="${X(H.mark) + 3}" y="14" class="crtt" style="fill:#ffd740">yours</text>`;
  s += `<text x="6" y="${Hh - 3}" class="crtt">${(+lo).toLocaleString()}</text><text x="${W - 6}" y="${Hh - 3}" class="crtt" text-anchor="end">${(+hi).toLocaleString()}</text>`;
  return s + '</svg>';
}
function slHeat(M) {
  const all = M.z.flat().filter((v) => v != null), lo = Math.min(...all), hi = Math.max(...all);
  return `<table class="heat"><tr><th>${esc(M.yname || '')} ↓ · ${esc(M.xname || '')} →</th>${M.x.map((x) => `<th>${esc(x)}</th>`).join('')}</tr>` + M.z.map((row, i) => `<tr><th>${esc(M.y[i])}</th>${row.map((v) => {
    if (v == null) return '<td></td>';
    const d = (v - lo) / Math.max(1e-9, hi - lo); return `<td style="background:hsl(${Math.round(120 * d)},60%,${18 + 14 * d}%);min-width:46px;font-size:10px">${Math.round(v / 1000)}k</td>`; }).join('')}</tr>`).join('') + '</table>';
}
function pStress() {
  if (!SL.st && !SL.opened) { SL.opened = true; slOpen(); }
  const S = SL.st || {}, R = S.result, busy = S.running, pct = Math.round((100 * (S.progress || 0)) / (S.total || 32));
  let h = `<div class="lab dex"><h3 class="dexh">🧯 DEXTER'S STRESS LAB · 32 WAYS TO BREAK A STRATEGY</h3>
    <p class="note">The settings on screen go through 32 robustness tests on the 2026 Blueberry data with the EA's own rules: overfitting statistics, parameter plateaus, worse fills,
    noisy and scrambled prices, Monte Carlo drawdowns and data audits. A strategy that only works on the exact past fails here. Python tests on the fast engine - MT5 stays the judge of any setting they suggest.</p>
    <div class="bar"><button id="slGo" class="dexbtn" ${busy ? 'disabled' : ''}>${busy ? '⏳ STRESSING…' : '🧯 RUN ALL 32 STRESS TESTS'}</button><span class="k">about 35 seconds</span></div>`;
  if (busy) h += `<div class="dexprog"><div class="dexprog-t">⚗️ BREAKING THE STRATEGY ON PURPOSE · ${pct}%</div><div class="dexprog-bar"><i style="width:${Math.max(3, pct)}%"></i></div>
    <div class="dexprog-s">${esc(S.phase || '')} · ${S.progress || 0} of 32 tests · ${S.seconds || 0} s</div></div>`;
  if (S.error) h += `<p class="warn">⚠ ${esc(S.error)}</p>`;
  if (!R) return h + '</div>';
  if (S.req && canon(diffDfl({ ...DFL, ...S.req })) !== canon(diffDfl(CUR))) h += '<p class="warn">⚠ These results are for other settings than the ones on screen - run the tests again.</p>';
  const cnt = { PASS: 0, WARN: 0, FAIL: 0, 'N/A': 0 }; R.tests.forEach((x) => { cnt[x.status] = (cnt[x.status] || 0) + 1; });
  const verdict = cnt.FAIL ? (cnt.FAIL >= 4 ? 'Fragile: it breaks in several ways' : 'Mostly robust, with weak spots to look at') : cnt.WARN > 6 ? 'Robust, with warnings' : 'Robust';
  h += `<div class="crt" style="margin:10px 0"><div class="crth">▶ THE VERDICT: ${esc(verdict.toUpperCase())}</div>
    <div>your settings on 2026: ${R.base.n} trades · ${money(R.base.net)} · WR ${R.base.wr}% · PF ${R.base.pf} · max drawdown ${money(-R.base.dd)} · run ${esc(R.at)} in ${R.seconds} s</div></div>`;
  h += `<div class="gauges">${Object.entries(cnt).map(([k, v]) => `<div class="gauge slg" style="border-color:${LAMP[k][0]}"><div class="acid"><b></b><i></i><i></i><i></i><i></i><i></i><i></i></div><div class="gv">${v}</div><div class="gl">${k}</div></div>`).join('')}</div>`;
  h += `<div class="bar">${[['all', 'all 32'], ['FAIL', 'fails'], ['WARN', 'warnings'], ['PASS', 'passes']].map(([k, l]) => `<button data-slf="${k}" class="${SL.filter === k ? 'dexbtn sm' : ''}">${l}</button>`).join(' ')}</div>`;
  for (const [c, [icon, title]] of Object.entries(CAT)) {
    const tests = R.tests.filter((x) => x.cat === c && (SL.filter === 'all' || x.status === SL.filter));
    if (!tests.length) continue;
    h += `<section><h3>${icon} ${c} · ${esc(title)}</h3>` + tests.map((x) => {
      const [col, lbl] = LAMP[x.status] || LAMP['N/A'], open = SL.open[x.id];
      let body = '';
      if (open) {
        if (x.table) body += table(x.table.head.map(esc), x.table.rows.map((r) => `<tr>${r.map((v) => `<td>${esc(v)}</td>`).join('')}</tr>`));
        if (x.hist) body += slHist(x.hist);
        if (x.heat) body += slHeat(x.heat);
      }
      return `<div class="sltest" style="--lamp:${col}"><button class="slhead" data-slt="${x.id}"><span class="lamp"></span><b>${esc(x.name)}</b> <span class="sltag">${lbl}</span>
        <span class="k">${open ? '▲' : '▼'}</span></button><div class="slhl">${esc(x.headline)}</div>${open ? `<div class="slbody">${body}</div>` : ''}</div>`;
    }).join('') + '</section>';
  }
  return h + '</div>';
}
document.addEventListener('click', async (e) => {
  const t = e.target.closest ? e.target.closest('[data-slt],[data-slf],#slGo') : null;
  if (!t) return;
  if (t.id === 'slGo') {
    const r = await api('/api/stress', { inputs: CUR });
    if (r.error) return toast('⚠ ' + esc(r.error));
    SL.st = { running: true, progress: 0, total: 32, phase: 'starting' }; renderPanel('tt'); slPoll();
  }
  if (t.dataset.slf) { SL.filter = t.dataset.slf; renderPanel('tt'); }
  if (t.dataset.slt) { SL.open[t.dataset.slt] = !SL.open[t.dataset.slt]; renderPanel('tt'); }
});
