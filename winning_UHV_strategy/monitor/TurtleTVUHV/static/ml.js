// Turtle TV Tester - the Machine Learning tab. Block 1 (2026-11-01, mlx/run.py): the institutional entry filter - Triple Barrier + Purged CV + SHAP + stacked boosting + ONNX, shown first.
// Block 2 (monitor/saad_view/ml.py). Zee 2026-10-21: "We should be able to run an ML algo and see its winrate.
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
function mlVerdict(R) {                                          // what the robots found, in one breath
  const B = R.base.test, rs = R.results;
  if (!rs.length) return 'no algorithm trained';
  const more = rs.filter((r) => r.at_thr.test.net > B.net), wr = rs.filter((r) => r.at_thr.test.wr > B.wr), best = rs.slice().sort((a, b) => b.at_thr.test.net - a.at_thr.test.net)[0];
  return `<div>${wr.length} of ${rs.length} brains raise the win rate on the unseen trades (${B.wr}% when taking every trade); <b>${more.length}</b> of them also make more money than taking every trade (${money(B.net)}).</div>` +
    `<div>${more.length ? `best: <b>${esc(best.algo)}</b> ${best.at_thr.test.wr}% · ${money(best.at_thr.test.net)} - worth an MT5 test as a filter` : 'so far the filter buys win rate with money: the skipped trades include big winners.'}</div>`;
}
// ---------- block 1 (2026-11-01): the institutional entry filter - mlx/run.py, shown FIRST on this tab ----------
// Zee: Triple Barrier labels (de Prado) on every M15 bar -> Purged K-Fold with a 24-bar embargo -> SHAP keeps the features that matter ->
// LightGBM + CatBoost stacked into a LogisticRegression -> ONNX -> the EA runs it at every M15 close (OnnxRun) and enters only when P > 0.75.
// This block only SHOWS simdata/mlx_results.json (the fixture simdata/mlx_results.sample.json until the real one exists) and starts the pipeline.
const MLX = { st: null, polling: false, spec: null, specLoading: false, specOpen: false, meta: null, metaLoading: false };
async function mlxMetaOpen() { if (MLX.metaLoading) return; MLX.metaLoading = true; try { MLX.meta = await api('/api/mlx_meta'); } catch (e) { MLX.meta = { error: String(e) }; } MLX.metaLoading = false; if (TAB.tt === 'ml') renderPanel('tt'); }
const mlxN = (v, d = 0) => (v === null || v === undefined || v === '' || Number.isNaN(+v) ? '–' : (+v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }));
const mlxPct = (v, d = 1) => (v === null || v === undefined || Number.isNaN(+v) ? '–' : `${(+v <= 1 ? 100 * +v : +v).toFixed(d)}%`);   // 0.374 or 37.4 -> 37.4%
const mlxMoney = (v) => (v === null || v === undefined || Number.isNaN(+v) ? '–' : `<span class="${cls(+v)}">${money(+v)}</span>`);
const mlxWr = (v) => (v === null || v === undefined || Number.isNaN(+v) ? '–' : `${(+v).toFixed(1)}%`);   // a win rate is always 0-100, never auto-scaled
const mlxShare = (a, n) => (n > 0 ? `<span class="k">${((100 * a) / n).toFixed(1)}%</span>` : '');
const mlxAuc = (v) => (v >= 0.6 ? 'good' : v < 0.52 ? 'bad' : '');
const mlxV = (k, v) => (v === null || v === undefined ? '–' : /(^|_)net$|_usd$|^pnl$/.test(k) ? mlxMoney(v) : /(^|_)wr$/.test(k) ? mlxPct(v) : typeof v === 'number' ? mlxN(v, Number.isInteger(v) ? 0 : 3) : typeof v === 'object' ? esc(JSON.stringify(v)) : esc(v));
function mlxAny(x) {                                             // whatever shape the pipeline (or the MT5 step) wrote: rows, a dict of rows, a dict
  if (Array.isArray(x) && x.length && typeof x[0] === 'object') { const cols = [...new Set(x.flatMap((r) => Object.keys(r)))]; return table(cols.map(esc), x.map((r) => `<tr>${cols.map((c, i) => `<td class="${i ? '' : 'l'}">${mlxV(c, r[c])}</td>`).join('')}</tr>`)); }
  if (x && typeof x === 'object') {
    const ks = Object.keys(x);
    if (ks.length && ks.every((k) => x[k] && typeof x[k] === 'object' && !Array.isArray(x[k]))) { const cols = [...new Set(ks.flatMap((k) => Object.keys(x[k])))]; return table(['', ...cols.map(esc)], ks.map((k) => `<tr class="${k === 'total' ? 'tot' : ''}"><td class="l">${esc(k)}</td>${cols.map((c) => `<td>${mlxV(c, x[k][c])}</td>`).join('')}</tr>`)); }
    return table(['', ''], ks.map((k) => `<tr><td class="l">${esc(k)}</td><td style="text-align:left">${mlxV(k, x[k])}</td></tr>`));
  }
  return `<pre class="note">${esc(typeof x === 'string' ? x : JSON.stringify(x, null, 1))}</pre>`;
}
async function mlxOpen() {                                       // first look: the job's state + the last results file
  MLX.st = { loading: true };
  try { MLX.st = await api('/api/mlx'); } catch (e) { MLX.st = { error: 'Turtle TV did not answer: ' + e }; }
  if (TAB.tt === 'ml') renderPanel('tt');
  if (MLX.st.running) mlxPoll();
}
async function mlxPoll() {                                       // every second while the pipeline runs (a restarting server is retried for 2 min)
  if (MLX.polling) return; MLX.polling = true;
  let miss = 0;
  try { for (;;) { await new Promise((r) => setTimeout(r, 1000)); try { MLX.st = await api('/api/mlx'); miss = 0; } catch (e) { if (++miss > 120) { MLX.st = { ...(MLX.st || {}), running: false, error: 'Turtle TV stopped answering' }; break; } continue; } if (TAB.tt === 'ml') renderPanel('tt'); if (!MLX.st.running) break; } } finally { MLX.polling = false; }
  if (TAB.tt === 'ml') renderPanel('tt');
}
function mlxMetaBlock() {                                        // 0b. the fix attempt: meta-labelling on the strategy's own trades (mlx/meta_train.py + mlx/meta_seq.py)
  if (!MLX.meta && !MLX.metaLoading) mlxMetaOpen();
  const Q = MLX.meta || {}, T = Q.tab, Sq = Q.seq;
  let h = `<div class="dexpanel" style="margin:10px 0"><h4 style="margin-top:0">0b · THE FIX ATTEMPT · META-LABELLING ON THE STRATEGY'S OWN TRADES <span class="k">(Zee: "find a way to make ML/AI that works for us on our strategy")</span></h4>`;
  if (!T && !Sq) return h + `<p class="note">${Q.error ? '⚠ ' + esc(Q.error) : MLX.metaLoading ? 'Loading…' : 'not run yet - mlx/meta_train.py and mlx/meta_seq.py write simdata/mlx_meta_results_*.json'}</p></div>`;
  const pct = (v) => (v == null ? '–' : (+v <= 1 ? (100 * +v) : +v).toFixed(2) + '%');
  const C = (T && T.baselines && T.baselines.setting_C_in_sample) || (Sq && Sq.baselines && Sq.baselines.setting_C_hand_filters_IN_SAMPLE) || {};
  const data = (T && T.data) || {};
  h += `<p class="note">The if-else EA stays the primary model (setup + side); the ML learns <b>P(this setup wins)</b> from the strategy's own trades. Universe = <b>setting C</b> (${esc('2026-11-01 08-38-10')}, Zee's standard: ${mlxN(C.n)} trades · ${pct(C.wr)} · ${mlxMoney(C.net)} · ${mlxN(C.full_stops)} full stops, <b>in-sample</b>) with every hand entry-filter OFF: <b>${mlxN(data.n_universe || (Sq && Sq.n_universe))}</b> setup+breakout trades at ${pct(data.universe_wr || (Sq && Sq.universe_wr))}. Features: 75 setup-state (which EMA, shape, EMA gap/slope, chop, breakout distance, open positions, recent results, day P&amp;L…) + the 85 bar features + side; labels = the trade's own win/loss; leave-one-year-out, every number out-of-sample unless marked. Turtle TV Tester = hypothesis.</p>`;
  const row = (name, r, extra = '') => `<tr><td class="l">${name}</td><td>${r.oos_auc != null ? mlxN(r.oos_auc, 3) : r.auc != null ? mlxN(r.auc, 3) : '–'}</td><td>${mlxN(r.logloss ?? r.oos_logloss, 4)}</td><td>${mlxN(r.base ?? r.logloss_class_freq ?? r.baseline_logloss, 4)}</td>${extra}</tr>`;
  const top = (fr) => (fr || []).find((x) => x.kind === 'top' && +x.value === 1615) || {};
  const tTop = top(T && T.frontier), sTop = top(Sq && Sq.frontier);
  const tOOS = (T && T.oos && T.oos.best) || {}, sOOS = (Sq && Sq.oos) || {};
  const rndT = (((T && T.baselines && T.baselines.random) || {}).rows || []).find((x) => +x.value === 1615), rndS = ((Sq && Sq.baselines && Sq.baselines.random_same_size) || {})['1615'];
  const rnd = rndT || rndS || {};
  const tmo0 = (T && T.baselines && T.baselines.time_only_model) || {}, tmo = tmo0.oos ? { oos_auc: tmo0.oos.auc, logloss: tmo0.oos.logloss, base: tmo0.oos.baseline_logloss, top1615: tmo0.oos.top1615 ? { n: 1615, ...tmo0.oos.top1615 } : null } : tmo0;
  const cell3 = (n, wr, net, fs) => `<td>${mlxN(n)} · ${wr == null ? '–' : pct(wr)} · ${mlxMoney(net)}${fs != null ? ` · <span class="k">${mlxN(fs)} full stops</span>` : ''}</td>`;
  h += `<table><tr><th>model</th><th>OOS AUC(win)</th><th>OOS log-loss</th><th>class-frequency log-loss</th><th>top-1,615 by P (out-of-sample)<br><span class="k">n · WR · net · full stops</span></th></tr>
    ${T ? row('Tabular boosting · 70 setup + 85 bar features + side (40 variants, best shown)', { oos_auc: tOOS.auc ?? T.oos_auc, logloss: tOOS.logloss, base: tOOS.baseline_logloss ?? tOOS.logloss_class_freq ?? T.baseline_logloss }, cell3(tTop.n, tTop.wr, tTop.net, tTop.full_stops)) : ''}
    ${Sq ? row('Sequence model · 1D-CNN on the last 48 candles + time + setup state (3 seeds)', { oos_auc: sOOS.auc, logloss: sOOS.logloss, base: sOOS.logloss_class_freq }, cell3(sTop.n, sTop.wr, sTop.net, sTop.full_stops)) : ''}
    ${tmo && (tmo.oos_auc != null || tmo.auc != null) ? row('Time-only baseline · hour, day of week, bar of day, side', tmo, `<td>${esc(String(tmo.top1615 && typeof tmo.top1615 === 'object' ? `${mlxN(tmo.top1615.n)} · ${pct(tmo.top1615.wr)} · ${money(+tmo.top1615.net || 0)}` : tmo.top1615 || '–'))}</td>`) : ''}
    <tr><td class="l">Random 1,615-trade subset of the universe (Monte-Carlo band)</td><td>0.500</td><td>–</td><td>–</td><td>${pct(rnd.wr ?? rnd.wr_expected)} expected · p95 ${pct(rnd.wr_p95)} · ${mlxMoney(rnd.net ?? rnd.net_expected)} · <span class="k">${mlxN(rnd.full_stops ?? rnd.full_stops_expected)} full stops</span></td></tr>
    <tr class="tot"><td class="l">Setting C's hand filters · <b>IN-SAMPLE</b> (hand-optimised on these same 4 years)</td><td>–</td><td>–</td><td>–</td>${cell3(C.n, C.wr, C.net, C.full_stops)}</tr></table>`;
  const sy = (Sq && Sq.baselines && Sq.baselines.ml_top1615_oos_per_year_vs_C) || null;
  if (sy && typeof sy === 'object') h += `<p class="note" style="margin-bottom:2px">per year · the ML's top-1,615 (out-of-sample, sequence model) beside C's own trades (in-sample)</p>` +
    table(['year', 'ML top-1,615 pick · n · WR · net · full stops', 'setting C in-sample · n · WR · net'], Object.keys(sy).sort().map((y) => { const a = sy[y].ml_top1615_pooled_pick || {}, c = sy[y].C_in_sample || {}; return `<tr><td class="l">${esc(y)}</td>${cell3(a.n, a.wr, a.net, a.full_stops)}${cell3(c.n, c.wr, c.net)}</tr>`; }));
  const cp = (Sq && Sq.candle_prediction) || null;
  h += `<div class="crt" style="margin:10px 0 4px"><div class="crth">▶ VERDICT · NO MODEL SHIPS</div>
    <div>1. <b>No out-of-sample skill in P(win)</b>: AUC ${mlxN(tOOS.auc ?? (T && T.oos_auc), 3)} (tabular) and ${mlxN(sOOS.auc, 3)} (sequence) - a coin flip is 0.5 - with the log-loss WORSE than knowing only the base rate. All 40 tabular variants sit between 0.43 and 0.51; permuting any feature block on average <i>improves</i> the held-out year.</div>
    <div>2. The ML's top-1,615 (${pct(tTop.wr)} / ${mlxMoney(tTop.net)}) lies inside the <b>random</b> band (${pct(rnd.wr ?? rnd.wr_expected)} expected, p95 ${pct(rnd.wr_p95)}); the sequence model's is below random. Neither recognises C's own trades (they rank at the 48th percentile) nor finds trades C misses (every added tranche comes in at the universe's 92%).</div>
    <div>3. <b>Anti-learning</b>: the calibration slopes were negative in 3 of 4 years - what separated winners from losers in the training years was reversed the next year.</div>
    <div>4. <b>The "fluent candles" test</b> (a sequence model trained to predict the candles themselves, 89k bars, out-of-sample): ${cp && typeof cp === 'object' ? Object.keys(cp).filter((k) => cp[k] && typeof cp[k] === 'object' && cp[k].auc != null).map((k) => `${esc(k.replace(/_/g, ' '))}: AUC <b>${mlxN(cp[k].auc, 3)}</b> · accuracy ${pct(cp[k].acc)} vs majority ${pct(cp[k].majority_acc)}`).join(' · ') : 'next-bar direction AUC 0.500, next-24-bar sign AUC 0.48'} - the candles cannot be predicted from their own past here.</div>
    <div>5. <b>The uncomfortable corollary</b>: a leave-one-year-out imitation of C's own filter family recognises C's picks (AUC 0.85) yet reaches only 92-94.5% in the held-out year, while C's picks show 96-98% there. C's five points over the universe look like <b>in-sample carving</b> - which is exactly why raising the hand-optimised win rate shrinks the trade count. Hypothesis; the test is a walk-forward re-optimisation (tune on 2023-25, read 2026 untouched) in MT5.</div>
    <div>6. What this does NOT say: that ML is useless for the EA. It says the <i>entry</i> outcome of a $400-vs-$5,200 trade is not predictable from anything known at the entry; the edge, if any, is in the exit and the geometry (doctrine: EXIT is the edge).</div></div>`;
  h += `<details class="dexsec"><summary>files · how to re-run</summary><p class="note">mlx/meta_features.py (py -m mlx.meta_features) → simdata/mlx_meta.npz + mlx_meta_spec.json · mlx/meta_train.py → simdata/mlx_meta_results_tab.json · mlx/meta_seq.py → simdata/mlx_meta_results_seq.json (ONNX of the all-years refit saved with a do-not-deploy note) · universe built by mlx/data.py build_entries(b_file=settings/saved/2026-11-01 08-38-10.json) → simdata/mlx_entries_C.npz</p></details></div>`;
  return h;
}
function pMLX() {
  if (!MLX.st) mlxOpen();
  const J = MLX.st || {}, R = J.result || null, S = (R && R.settings) || {}, bar = S.barriers || {}, bl = S.base_learners || [], sh = (R && R.shap) || {};
  const nAll = S.features_all ?? ((sh.top && sh.top.length) || 85), kept = sh.kept || S.kept || [], nKept = S.features_kept ?? (kept.length || null), thr = S.threshold ?? 0.75;
  const learner = (role, dflt) => { const b = bl.find((x) => x.role === role); return b ? `<b>${esc(b.name || '–')}</b>${b.substitute ? ' <span class="tag lab" title="no ARM64 wheel on this laptop; the x64 VM runs the real one">substitute on ARM64</span>' : ''}` : dflt; };
  const row = (k, v) => `<span class="k" style="white-space:nowrap">${k}</span><span>${v}</span>`;
  let h = `<div class="lab dex" style="margin-bottom:16px"><h3 class="dexh">🏛️ INSTITUTIONAL ENTRY FILTER · TRIPLE BARRIER + PURGED CV + SHAP + STACKED BOOSTING + ONNX · ${R && R.built ? 'built ' + esc(String(R.built).slice(0, 10)) : 'not built yet'}</h3>
    <p class="note"><b>A second brain for the ENTRY, built the way the desks build one</b> (López de Prado). Every M15 bar is labelled by what the market did next: +1.5 ATR touched first → <b>1</b>, −1.5 ATR first → <b>−1</b>, neither within 24 bars → <b>0</b>.
    A stacked model learns the bar's state (${nAll} values, no volume) under a purged, embargoed cross-validation (the model WEIGHTS never see their test fold; the SHAP feature list was chosen once on all four years); SHAP keeps the features that matter; the stack is exported to ONNX and the EA runs it
    at every M15 close and <b>would</b> enter only when P(barrier) &gt; ${thr}. Python = a hypothesis; MT5 judges.</p>
    <div class="dexpanel"><div style="display:grid;grid-template-columns:max-content 1fr;gap:3px 14px;font-size:12px">
    ${row('Labels', `Triple Barrier · upper <b>+${bar.up_atr ?? 1.5} ATR</b> · lower <b>−${bar.dn_atr ?? 1.5} ATR</b> · time <b>${bar.time_bars ?? 24} bars</b> → 1 / −1 / 0`)}
    ${row('Cross-validation', `Purged K-Fold · <b>${S.folds ?? 5} folds</b> · embargo <b>${S.embargo_bars ?? 24} bars</b> · Combinatorial Purged CV ${S.cpcv ? 'run (below)' : 'not run'}`)}
    ${row('Features', `<b>${nAll}</b> per bar (the FEATURE_SPEC) → <b>${nKept ?? '–'}</b> kept by SHAP${S.shap_method ? ` · ${esc(S.shap_method)}` : ''}`)}
    ${row('Base learner · LightGBM', learner('LightGBM', 'LightGBM (HistGradientBoosting stands in on ARM64)'))}
    ${row('Base learner · CatBoost', learner('CatBoost', 'CatBoost (XGBoost stands in on ARM64)'))}
    ${row('Meta-learner', `<b>${esc(S.meta || 'LogisticRegression')}</b> on the base learners' out-of-fold probabilities → softmax P(1) / P(−1) / P(0) (how calibrated: section 3b - fine between 0.3 and 0.6, off in the tails, untestable above 0.6)`)}
    ${row('Entry rule', `BUY when P(upper) &gt; <b>${thr}</b> · SELL when P(lower) &gt; <b>${thr}</b> · judged at the M15 close on the last closed bar`)}
    ${row('Spread feature', S.use_spread ? 'on' : 'off - the exporter writes 0, the model never sees it')}
    ${row('Volume', 'excluded - the Strategy Tester overwrites tick volume (4 per bar)')}
    ${row('Results', R ? `built ${esc(R.built || '–')}${J.sample ? ' · <b class="bad">SAMPLE</b>' : ''}` : 'none yet - run the pipeline')}</div>
    <div class="bar"><button id="mlxGo" class="dexbtn" ${J.running || J.loading ? 'disabled' : ''}>▶ RUN THE PIPELINE</button><button id="mlxRefresh" class="dexbtn sm">↻ refresh</button>
    <span class="k">labels → purged CV → SHAP → stack → ONNX → trading translation · writes simdata/mlx_results.json and simdata/mlx_models/ · long (the laptop is busy)</span></div>`;
  if (J.loading) h += '<p class="note">Loading…</p>';
  if (J.running) h += `<p class="note">⏳ <span class="prog"><i style="width:${J.total ? Math.min(100, (100 * J.progress) / J.total) : 3}%"></i></span> ${esc(J.phase || '')} · ${J.progress || 0}${J.total ? '/' + J.total : ''} · ${J.seconds || 0} s</p>`;
  else if (J.phase === 'done' && !J.error) h += `<p class="note">✔ the pipeline finished in ${J.seconds || 0} s</p>`;
  if (J.error) h += `<p class="warn">⚠ ${esc(J.error)}</p>`;
  if (J.built_module === false) h += '<p class="warn">mlx/run.py is not built yet - the button answers "the pipeline is not built yet"</p>';
  h += `<details class="dexsec" id="mlxSpecD" ${MLX.specOpen ? 'open' : ''}><summary>📄 THE FEATURE SPEC · mlx/FEATURE_SPEC.md · ${nAll} per-bar values in a fixed order, Python and MQL5 verbatim</summary>${MLX.spec ? `<pre style="white-space:pre-wrap;font-size:11px;max-height:440px;overflow:auto;color:#cfd8dc;margin:4px 0">${esc(MLX.spec)}</pre>` : '<p class="note">Loading…</p>'}</details></div>`;
  if (J.sample) h += '<p class="warn" style="font-weight:bold;font-size:13px">⚠ SAMPLE DATA - run the pipeline. Everything below is a typed rendering fixture (simdata/mlx_results.sample.json), not a result.</p>';
  if (!R) return h + '<p class="note">No results yet. The page reads simdata/mlx_results.json once the pipeline has written it.</p></div>';
  // 0. the verdict, computed from the data - the one thing to read
  const T0 = R.trading || {}, thrS = String(S.threshold ?? 0.75), reach = ((R.cv || {}).oof || {}).reach || {}, oof0 = (R.cv || {}).oof || {};
  const nAt = (src) => ((((src || {}).at || {})[thrS] || {}).total || {}).n, nB = nAt(T0.B), nU = nAt(T0.universe), nBall = (((T0.B || {}).all || {}).total || {}).n, nUall = (((T0.universe || {}).all || {}).total || {}).n;
  if (nB === 0 && nU === 0) h += `<div class="crt" style="margin:8px 0"><div class="crth">▶ VERDICT · THE GATE NEVER FIRES</div>
    <div>At P &gt; ${thrS} the model lets through <b>0 of ${mlxN(nBall)}</b> setting-B trades and <b>0 of ${mlxN(nUall)}</b> universe trades. Over ${mlxN(oof0.n)} out-of-fold bars the highest P(up) it ever said was <b>${mlxN(reach.max_p_up, 3)}</b> and the highest P(down) <b>${mlxN(reach.max_p_down, 3)}</b>; on B's own entries max P(side) is <b>${mlxN(((T0.B || {}).p_side || {}).max, 3)}</b>.</div>
    <div>Direction is a near coin flip: out-of-fold AUC up <b>${mlxN(oof0.auc_up, 3)}</b> · down <b>${mlxN(oof0.auc_down, 3)}</b> (0.5 = no skill), the same in every fold, every held-out year and every CPCV path. The lift over the baseline comes from the <b>no-touch</b> class (AUC ${mlxN(oof0.auc_none, 3)}): the model knows WHEN nothing happens in 24 bars (time of day, volatility), not WHICH WAY the price goes. On B's trades P(side) does not order the win rate (quintile table in section 5).</div>
    <div>So the MT5 run of the gate at ${thrS} shows zero trades by construction. Before an MT5 test means anything the threshold or the barrier geometry has to change - Zee's call, not made here. The 'fluent candle prediction' question has its answer in these AUCs.</div></div>`;
  else if (nB != null) h += `<p class="note"><b>At the EA's rule (P &gt; ${thrS})</b>: setting B keeps ${mlxN(nB)} of ${mlxN(nBall)} trades, the universe ${mlxN(nU)} of ${mlxN(nUall)} - Turtle TV Tester hypothesis, NOT PROMOTED, judged in section 7.</p>`;
  h += mlxMetaBlock();
  // 1. the labels
  const D = R.data || {}, yrs = Object.keys(D.years || {}).filter((y) => y !== 'total').sort(), tot = { n: 0, up: 0, down: 0, none: 0 };
  yrs.forEach((y) => { for (const k in tot) tot[k] += +((D.years[y] || {})[k] || 0); });
  const lrow = (name, v, c = '') => `<tr class="${c}"><td class="l">${esc(name)}</td><td>${mlxN(v.n)}</td><td><span class="good">${mlxN(v.up)}</span> ${mlxShare(v.up, v.n)}</td><td><span class="bad">${mlxN(v.down)}</span> ${mlxShare(v.down, v.n)}</td><td>${mlxN(v.none)} ${mlxShare(v.none, v.n)}</td></tr>`;
  h += '<h4>1 · TRIPLE BARRIER LABELS BY YEAR</h4>' + table(['year', 'bars', '1 · upper first', '−1 · lower first', '0 · neither in 24 bars'], [...yrs.map((y) => lrow(y, D.years[y] || {})), lrow('total', tot, 'tot')]) +
    `<p class="note">${mlxN(D.bars)} labelled bars${D.train_years ? ` · years in the model: ${D.train_years.map(esc).join(', ')}` : ''} · the 600 warm-up bars and the bars without 24 forward bars are dropped · both barriers in one bar is settled on the 1-minute candles, still tied → 0.</p>`;
  // 2. purged cross-validation
  const cv = R.cv || {}, oof = cv.oof || {}, folds = cv.folds || [], base = cv.baseline_logloss, vsBase = (v) => (v == null || base == null ? '' : v < base ? 'good' : 'bad');
  h += `<h4>2 · PURGED K-FOLD · ${folds.length || S.folds || '–'} FOLDS · EMBARGO ${S.embargo_bars ?? '–'} BARS</h4>` +
    table(['fold', 'test window', 'bars', 'log-loss', 'accuracy', 'AUC up', 'AUC down'],
      folds.map((f) => `<tr><td class="l">${esc(f.fold)}</td><td>${esc(f.test_from || '–')} → ${esc(f.test_to || '–')}</td><td>${mlxN(f.n_test)}</td><td class="${vsBase(f.logloss)}">${mlxN(f.logloss, 4)}</td><td>${mlxPct(f.acc)}</td><td class="${mlxAuc(f.auc_up)}">${mlxN(f.auc_up, 3)}</td><td class="${mlxAuc(f.auc_down)}">${mlxN(f.auc_down, 3)}</td></tr>`)
        .concat([`<tr class="tot"><td class="l">out-of-fold</td><td>every bar, scored by the fold that never trained on it</td><td>${mlxN(D.bars)}</td><td class="${vsBase(oof.logloss)}">${mlxN(oof.logloss, 4)}</td><td>${mlxPct(oof.acc)}</td><td class="${mlxAuc(oof.auc_up)}">${mlxN(oof.auc_up, 3)}</td><td class="${mlxAuc(oof.auc_down)}">${mlxN(oof.auc_down, 3)}</td></tr>`])) +
    `<p class="note">Baseline log-loss, predicting the class frequencies: <b>${mlxN(base, 4)}</b> → the stack ${oof.logloss == null || base == null ? '–' : oof.logloss < base ? `<b class="good">beats it by ${(base - oof.logloss).toFixed(4)}</b>` : '<b class="bad">does NOT beat it</b>'} · Brier up ${mlxN(oof.brier_up, 4)} · down ${mlxN(oof.brier_down, 4)} · AUC 0.5 = a coin flip, below 0.6 = almost none · accuracy ${mlxPct(oof.acc)} vs always-up ${tot.n ? mlxPct(tot.up / tot.n) : '–'} · AUC of the no-touch class <b>${mlxN(oof.auc_none, 3)}</b> - the lift is THERE, not in direction.
    Purging drops every training bar whose label was still being decided inside the test window; the embargo drops ${S.embargo_bars ?? '–'} more bars after it.</p>`;
  if (S.cpcv) h += '<p class="note"><b>Combinatorial Purged CV</b> (the extra)</p>' + mlxAny(S.cpcv);
  // 3. calibration
  const cal = cv.calibration || [], rc = oof.reach || {}, thr0 = +thr;
  if (rc.bars_p_up_gt) { const ks = Object.keys(rc.bars_p_up_gt); h += '<h4>3 · HOW FAR THE MODEL EVER REACHES · out-of-fold bars above each P</h4>' + table(['', ...ks.map((k) => `P &gt; ${esc(k)}${+k === thr0 ? ' ★' : ''}`), 'max'],
    [`<tr><td class="l">P(up)</td>${ks.map((k) => `<td class="${rc.bars_p_up_gt[k] ? '' : 'bad'}">${mlxN(rc.bars_p_up_gt[k])}</td>`).join('')}<td>${mlxN(rc.max_p_up, 3)}</td></tr>`,
     `<tr><td class="l">P(down)</td>${ks.map((k) => `<td class="${(rc.bars_p_down_gt || {})[k] ? '' : 'bad'}">${mlxN((rc.bars_p_down_gt || {})[k])}</td>`).join('')}<td>${mlxN(rc.max_p_down, 3)}</td></tr>`]) +
    `<p class="note">of ${mlxN(oof.n)} bars. A gate at ${thr} needs bars in the ★ column; 0 there means the EA's rule can never fire with this label geometry.</p>`; }
  if (cal.length) h += '<h4>3b · CALIBRATION · what the model said vs what happened</h4>' + table(['predicted P(up)', 'bars', 'mean predicted', 'actual share', 'gap'], cal.map((c) => { const g = c.actual == null || c.pred == null ? null : c.actual - c.pred, thin = !c.n || c.n < 30; return `<tr class="${thin ? 'dim' : ''}"><td class="l">${esc(c.bin)}</td><td>${mlxN(c.n)}</td><td>${c.n ? mlxN(c.pred, 3) : 'never predicted'}</td><td>${c.n ? mlxN(c.actual, 3) : '–'}</td><td class="${g == null || thin ? '' : Math.abs(g) < 0.03 ? 'good' : Math.abs(g) < 0.08 ? '' : 'bad'}">${g == null ? '–' : (g >= 0 ? '+' : '') + g.toFixed(3)}${thin && c.n ? ' <span class="k">(too few bars to read)</span>' : ''}</td></tr>`; })) +
    `<p class="note">Calibrated means a 0.75 is right 75% of the time. The EA's bins (&gt; ${thr}) are ${cal.some((c) => c.n && parseFloat(c.bin) >= thr0) ? 'populated - read their gap' : '<b>EMPTY</b> - the model never said ' + thr + ' about any bar'}; rows under 30 bars are greyed, their gap is noise.</p>`;
  // 4. SHAP
  const top = sh.top || [], keptSet = new Set(kept), mx = Math.max(1e-9, ...top.map((f) => +f.mean_abs || 0));
  h += `<h4>4 · SHAP · ${keptSet.size || nKept || '–'} OF ${top.length || nAll} FEATURES KEPT · ${esc(sh.method || S.shap_method || '–')}</h4>${sh.rule ? `<p class="note">rule: ${esc(sh.rule)}</p>` : ''}`;
  if (top.length) h += '<div class="scroll" style="max-height:440px">' + table(['#', 'feature', 'mean |SHAP| · the feature’s pull on P, averaged over every bar', ''], top.map((f, i) => { const on = keptSet.has(f.name); return `<tr class="${on ? 'both' : 'dim'}"><td>${i + 1}</td><td class="l">${esc(f.name)}</td><td style="text-align:left"><span style="display:inline-block;height:9px;width:${Math.max(1, (240 * Math.max(0, +f.mean_abs || 0)) / mx)}px;background:${on ? '#2962ff' : '#555'};border-radius:3px"></span> ${mlxN(f.mean_abs, 4)}</td><td class="${on ? 'good' : 'k'}">${on ? 'kept' : 'dropped'}</td></tr>`; })) + '</div>';
  else h += '<p class="note">–</p>';
  if (sh.dropped && sh.dropped.length) h += `<p class="note">dropped (${sh.dropped.length}): ${sh.dropped.map(esc).join(', ')}</p>`;
  // 5. the trading translation
  const T = R.trading || {}, thrs = (T.thresholds || [0.5, 0.6, 0.7, 0.75, 0.8, 0.9]).map((t) => +t);
  const atOf = (src, t) => (src.at || {})[String(t)] || (src.at || {})[t.toFixed(2)] || (src.at || {})[t.toFixed(1)] || null;
  const hi = (t) => (t === thr0 ? ' style="background:rgba(255,215,64,.13)"' : '');
  const cell = (v, st = '') => (v ? `<td${st}>${mlxN(v.n)} · ${v.n ? mlxWr(v.wr) : '–'} · ${mlxMoney(v.net)}</td>` : `<td${st}>–</td>`);
  const tblock = (title, src) => {
    if (!src || !src.all) return `<p class="note"><b>${title}</b>: –</p>`;
    const years = Object.keys(src.all).filter((y) => y !== 'total').sort().concat(src.all.total ? ['total'] : []);
    const q = src.by_p_quintile || [], atT = ((atOf(src, thr0) || {}).total || {}), at5 = ((atOf(src, 0.5) || {}).total || {});
    return `<p class="note" style="margin-bottom:2px"><b>${title}</b></p><table><tr><th colspan="${2 + thrs.length}" style="text-align:left;font-weight:normal"><span class="bad">Turtle TV Tester = HYPOTHESIS · NOT PROMOTED</span> · no MT5 run exists for any filtered column · Turtle TV 'In the EA' rows read 4-8% high vs MT5${src.no_oof ? ` · ${mlxN(src.no_oof)} trades without a probability (warm-up bars) sit in 'all' only` : ''}</th></tr><tr><th>year</th><th>all trades<br><span class="k">n · WR · net</span></th>${thrs.map((t) => `<th${hi(t)}>P &gt; ${t}${t === thr0 ? ' ★' : ''}<br><span class="k">n · WR · net</span></th>`).join('')}</tr>` +
      years.map((y) => `<tr class="${y === 'total' ? 'tot' : ''}"><td class="l">${esc(y)}</td>${cell(src.all[y])}${thrs.map((t) => cell((atOf(src, t) || {})[y], hi(t))).join('')}</tr>`).join('') + '</table>' +
      `<p class="note"><b>verdict</b> · at the EA's rule (P &gt; ${thr0}): <b>${atT.n ? `${mlxN(atT.n)} trades · ${mlxWr(atT.wr)} · ${mlxMoney(atT.net)}` : '0 trades'}</b>${at5.n ? ` · at P &gt; 0.5: ${mlxN(at5.n)} trades · ${mlxWr(at5.wr)} · ${mlxMoney(at5.net)}` : ''}${src.p_side ? ` · P(side) on these entries: mean ${mlxN(src.p_side.mean, 3)} · max ${mlxN(src.p_side.max, 3)}` : ''}</p>` +
      (q.length ? `<p class="note" style="margin-bottom:2px">WR by P(side) quintile - if P carried information, WR and net would rise from left to right:</p>` + table(['P(side)', 'trades', 'WR', 'net'], q.map((r) => `<tr><td class="l">${esc(r.p_side)}</td><td>${mlxN(r.n)}</td><td>${mlxWr(r.wr)}</td><td>${mlxMoney(r.net)}</td></tr>`)) : '');
  };
  h += `<h4>5 · TRADING TRANSLATION · the EA's own trades, all vs the ones the model lets through</h4><p class="note">${esc(T.rule || 'BUY if P(up) > thr, SELL if P(down) > thr, features of the last closed bar before the entry, OOF probabilities')} · the ★ column is the EA's rule (P &gt; ${thr}) · fewer trades at a higher win rate is only a gain if the net keeps up (STANDING GOAL: win rate at fixed geometry, never bought with money).</p>` +
    tblock('Setting B · settings/saved/2026-10-30 23-08-23 · an optimiser pick on these same 4 years = IN-SAMPLE · 1 loser in 399, so every subset is ≥ 99% by construction · MT5 receipt for "all": 395 / 99.75% / +$162,491 (random delay 389 / 99.74% / +$156,881)', T.B) +
    tblock('The setup UNIVERSE · B with every entry filter off, InpMaxPos 8 · in-sample too · check 2026 in the P &gt; 0.5 column before believing the total', T.universe);
  // 6. ONNX + the model files
  const O = R.onnx || {}, okO = /^(ok|done|exported|verified)/i.test(String(O.status || ''));
  h += `<h4>6 · ONNX EXPORT · what the EA loads with OnnxCreate</h4><p class="note">status: <b class="${okO ? 'good' : O.status ? 'bad' : ''}">${esc(O.status || '–')}</b> · max |ONNX − sklearn| over the dataset: <b>${O.max_abs_diff == null ? '–' : (+O.max_abs_diff).toExponential(2)}</b> · runtime: ${esc(O.runtime || '–')}</p>` +
    (O.files && O.files.length ? table(['file', 'bytes'], O.files.map((f) => `<tr><td class="l">${esc(f.path)}</td><td>${mlxN(f.bytes)}</td></tr>`)) : '');
  const M = R.models || {};
  if (M.main || M.loyo) h += `<p class="note"><b>models</b> · main: ${M.main ? `${esc(M.main.dir || '–')} (${(M.main.files || []).length} files)` : '–'} · leave-one-year-out: ${M.loyo ? Object.keys(M.loyo).sort().map((y) => `${esc(y)} → ${esc((M.loyo[y] || {}).dir || '–')}`).join(' · ') : '–'}</p>`;
  if (M.loyo && Object.values(M.loyo).some((m) => m && m.holdout)) h += '<p class="note" style="margin-bottom:2px"><b>leave-one-year-out · the held-out year scored by the model that never trained on it</b> (the one truly out-of-year Python number; these are the models MT5 runs)</p>' +
    table(['held-out year', 'train rows', 'held-out bars', 'log-loss', 'baseline', 'AUC up', 'AUC down', 'AUC no-touch'], Object.keys(M.loyo).sort().map((y) => { const m = M.loyo[y] || {}, ho = m.holdout || {}; return `<tr><td class="l">${esc(y)}</td><td>${mlxN(m.train_rows)}</td><td>${mlxN(ho.n)}</td><td class="${ho.logloss != null && ho.baseline_logloss != null ? (ho.logloss < ho.baseline_logloss ? 'good' : 'bad') : ''}">${mlxN(ho.logloss, 4)}</td><td>${mlxN(ho.baseline_logloss, 4)}</td><td class="${mlxAuc(ho.auc_up)}">${mlxN(ho.auc_up, 3)}</td><td class="${mlxAuc(ho.auc_down)}">${mlxN(ho.auc_down, 3)}</td><td class="${mlxAuc(ho.auc_none)}">${mlxN(ho.auc_none, 3)}</td></tr>`; }));
  // 7. MT5
  h += '<h4>7 · MT5 · THE ONLY JUDGE</h4>';
  if (R.mt5 == null) h += '<p class="warn">not yet run in MT5. The filter is judged there, year by year, with the leave-one-year-out model of that year (simdata/mlx_models/loyo_&lt;year&gt;/, trained on the other three) in the view EA with its ONNX gate on - against the same setting without the gate. Until that table exists, nothing above is a result.</p>';
  else if (R.mt5.rows) {
    const mt = R.mt5, byS = {};
    mt.rows.forEach((r) => { (byS[r.setting] = byS[r.setting] || []).push(r); });
    const tot = (rs) => ({ trades: rs.reduce((a, r) => a + (+r.trades || 0), 0), net: rs.reduce((a, r) => a + (+r.net || 0), 0) });
    h += `<p class="note">${esc(mt.protocol || '')}</p><p class="note"><b>verdict</b> · ${esc(mt.verdict || '')}</p>` +
      table(['setting', 'delay', ...['2023', '2024', '2025', '2026'].map((y) => `${y}<br><span class="k">trades · WR · net</span>`), '4 years<br><span class="k">trades · net</span>'],
        Object.keys(byS).sort().flatMap((st) => ['none', 'random'].map((d) => { const rs = byS[st].filter((r) => r.delay === d), t = tot(rs); const cellY = (y) => { const r = rs.find((x) => String(x.year) === y); return r ? `<td>${mlxN(r.trades)} · ${r.wr != null && r.trades ? esc(String(r.wr)) : r.trades ? '<span class="k">WR n/a</span>' : '–'} · ${mlxMoney(r.net)}</td>` : '<td>–</td>'; };
          return `<tr class="${/no gate/.test(st) ? 'tot' : ''}"><td class="l">${esc(st)}</td><td>${esc(d)}</td>${['2023', '2024', '2025', '2026'].map(cellY).join('')}<td><b>${mlxN(t.trades)}</b> · ${mlxMoney(t.net)}</td></tr>`; }))) +
      '<p class="note">MT5 is the judge: these are real Strategy Tester passes on Blueberry ticks. Random delay = the project rule for quoting.</p>' +
      (mt.caveats && mt.caveats.length ? `<ul class="note">${mt.caveats.map((c) => `<li>⚠ ${esc(c)}</li>`).join('')}</ul>` : '');
  } else h += mlxAny(R.mt5);
  const notes = R.notes || [];
  h += `<details class="dexsec"><summary>⏱ TIMINGS · VERSIONS · NOTES</summary><div class="row" style="gap:28px">${R.timings ? `<div><p class="note"><b>timings (s)</b></p>${mlxAny(R.timings)}</div>` : ''}${R.versions ? `<div><p class="note"><b>versions</b></p>${mlxAny(R.versions)}</div>` : ''}</div>${notes.length ? `<ul class="note">${notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}</details>`;
  // the honest part
  h += `<div class="crt" style="margin:12px 0 4px"><div class="crth">▶ READ THIS BEFORE BELIEVING ANY OF IT</div>
    <div>1. Every number on this screen is <b>Python</b> - a HYPOTHESIS. Only MT5's Strategy Tester, or live fills, can promote it (CLAUDE.md, 2026-08-08: a Python replay promised +$876 and really made −$657).</div>
    <div>2. The filter is judged in MT5 with <b>leave-one-year-out</b> models: the WEIGHTS that gate 2024 never saw a 2024 bar (the 50-feature SHAP list was picked once on all four years). One model that saw everything would be marking its own homework.</div>
    <div>3. "300 parameters" are the model's <b>constants</b> - trees, leaf values, coefficients. What the EA computes per bar is <b>${nAll} values</b>, the FEATURE_SPEC in a fixed order; SHAP keeps ${nKept ?? '–'} of them and the ONNX tensor follows that kept list.</div>
    <div>4. <b>No volume</b>: the Strategy Tester overwrites tick volume (4 per bar), so a volume feature could never be reproduced where the EA is judged.</div>
    <div>5. The trading translation scores each trade with <b>out-of-fold</b> probabilities on the last closed bar before the entry; spread is off, so the EA's own spread filter still decides.</div>
    <div>6. The EA's gate <b>defaults OFF</b>. Nothing here changes a live trade until Zee turns it on after the MT5 table above is green.</div></div></div>`;
  return h;
}
document.addEventListener('click', async (e) => {
  if (e.target.id === 'mlxRefresh') { MLX.st = null; renderPanel('tt'); return; }
  if (e.target.id !== 'mlxGo') return;
  e.target.disabled = true;
  const r = await api('/api/mlx', {}).catch((x) => ({ error: String(x) }));
  if (r.error) { e.target.disabled = false; return toast('⚠ ' + esc(r.error)); }
  MLX.st = { ...(MLX.st || {}), running: true, phase: 'starting', progress: 0, total: 0, seconds: 0, error: null }; renderPanel('tt'); mlxPoll();
});
document.addEventListener('toggle', (e) => {                       // the spec <details>: remember open/closed across re-renders, fetch the text once
  if (!e.target || e.target.id !== 'mlxSpecD') return;
  MLX.specOpen = e.target.open;
  if (MLX.specOpen && !MLX.spec && !MLX.specLoading) { MLX.specLoading = true; api('/api/mlx_spec').then((s) => { MLX.spec = s.text || '(mlx/FEATURE_SPEC.md could not be read)'; if (TAB.tt === 'ml') renderPanel('tt'); }).catch(() => { MLX.specLoading = false; }); }
}, true);
function pML() {
  if (!MLS.algos) { mlOpen(); return pMLX() + '<p class="note">Loading…</p>'; }
  const J = MLS.job, R = J && J.result;
  let h = pMLX() + `<div class="lab dex"><h3 class="dexh">🤖 DEXTER'S AI LAB · ${MLS.algos.length} ROBOT BRAINS</h3><p class="note"><b>Machine learning on the EA's trades</b> (meta-labelling, like VSISA's ML filters). The EA keeps finding its setups; a model learns, from what
    was known at each entry (the setup candle, EMAs, ADX, ATR, recent returns, the hour, the range box…), whether that trade will win - and only the trades it trusts are taken.
    Trained on the first half, judged on the <b>unseen</b> half. Data: ${SRC.ds === 'm15' ? 'Blueberry 2023 → now (4 years)' : '2026 only - too few trades to learn from; use the 4 years'}. Python: a hypothesis until it runs in MT5.</p>
    <div class="dexpanel"><div class="bar">${MLS.algos.map((a) => `<label class="tog"><input type="checkbox" data-mla="${esc(a)}" ${MLS.picked.has(a) ? 'checked' : ''}> ${esc(a)}</label>`).join('')}</div>
    <div class="bar"><label>take a trade when the model's win chance ≥ <b id="mlThrV">${MLS.thr.toFixed(2)}</b> <input type="range" id="mlThr" min="0.3" max="0.7" step="0.025" value="${MLS.thr}"></label>
    <button id="mlGo" class="dexbtn" ${J && J.running ? 'disabled' : ''}>🤖 TRAIN &amp; TEST ${MLS.picked.size} BRAIN${MLS.picked.size === 1 ? '' : 'S'}</button></div></div>`;
  if (J && J.running) h += `<p class="note">⏳ ${esc(J.phase)} · ${J.progress}/${J.total} · ${J.seconds} s</p>`;
  if (J && J.error) h += `<p class="warn">⚠ ${esc(J.error)}</p>`;
  if (!R) return h + '</div>';
  const [LA, LB] = R.labels, B = R.base;
  h += `<div class="crt" style="margin:10px 0"><div class="crth">▶ THE VERDICT</div>${mlVerdict(R)}</div><p class="note">${R.n_train} trades to learn from (${LA}, ${R.wr_train}% winners) · ${R.n_test} unseen trades (${LB}, ${R.wr_test}% winners).
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
