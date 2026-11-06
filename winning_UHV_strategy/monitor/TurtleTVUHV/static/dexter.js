// Dexter's Lab (Zee 2026-10-26): every experiment on the LIVE setting - the one on the chart, loaded from a save. The setting is
// diagnosed from its own trades; each experiment runs on it in the Turtle TV tester, its sliders fine-tune it live, Autotune finds
// its best values, Autotune everything ranks them and stacks the winners into "Dexter's pick", and any of them can be applied
// (saved as the new setting) or verified in MT5. Tester numbers are hypotheses - MT5 decides.
const DXL = { spec: null, key: '', diag: null, diagBusy: false, params: {}, res: {}, busy: {}, tuned: {}, pick: null, job: null, poll: 0,
  objective: 'net', guard: true, mt5: null, mt5poll: 0, err: '', t: {}, open: {} };
const DXL_OBJ = { net: 'the most profit', net_dd: 'profit ÷ drawdown', worst: 'the smallest worst loss', pf: 'profit factor', wr: 'win rate' };

// ---------- the live setting ----------
function dxlKey() { return JSON.stringify([diffDfl(CUR), SRC.ds, SRC.mode]); }
function dxlSaveName() {
  const d = JSON.stringify(Object.entries(diffDfl(CUR)).sort());
  const s = (SAVEDS || []).find((x) => JSON.stringify(Object.entries(diffDfl({ ...DFL, ...x.inputs })).sort()) === d);
  return s ? s.name : null;
}
function dxlDsLabel() { const o = document.querySelector(`#srcDs option[value="${SRC.ds}"]`); return o ? o.textContent : SRC.ds; }
function dxlBody(extra) { return { inputs: CUR, ds: SRC.ds, mode: SRC.mode, ...extra }; }

async function dxlEnsure() {
  if (!DXL.spec) { try { DXL.spec = (await api('/api/dexlab_spec', {})).exps; } catch (e) { DXL.err = 'Could not load the experiments: ' + e.message; } }
  const k = dxlKey();
  if (DXL.key === k || DXL.diagBusy) return;
  DXL.key = k; DXL.diag = null; DXL.res = {}; DXL.tuned = {}; DXL.pick = null; DXL.params = {}; DXL.diagBusy = true; dxlRender();
  try {
    DXL.diag = await api('/api/dexlab_diag', dxlBody());
    for (const e of DXL.spec) {
      const p = {};
      for (const [n, , lo, hi, , def] of e.params) p[n] = def === 'auto' ? ((DXL.diag.defaults[e.key] || {})[n] ?? (lo + hi) / 2) : def;
      DXL.params[e.key] = p;
    }
    DXL.res.baseline = { stats: DXL.diag.base, sets: {} };
  } catch (e) { DXL.err = 'The diagnosis failed: ' + e.message; }
  DXL.diagBusy = false; dxlRender();
  if (DXL.diag && DXL.diag.base) dxlStart('all');
  dxlMt5Status();
}
function dxlRender() { if (TAB.tt === 'dexter') renderPanel('tt'); }

// ---------- scoring (same rules as the server's autotune) ----------
function dxlScore(s) {
  if (!s) return -1e18;
  return { net: s.net, net_dd: s.net_dd ?? -1e18, worst: s.worst + s.net / 1e9, pf: s.pf ?? -1e18, wr: s.wr + s.net / 1e12 }[DXL.objective] ?? s.net;
}
function dxlOk(s, base) { return !!s && (!DXL.guard || (s.train > 0 && s.test > 0 && s.n >= Math.max(10, base.n / 3) && s.dd <= 1.25 * Math.max(base.dd, 1) && s.worst >= 1.25 * Math.min(base.worst, -1))); }
function dxlVerdict(s, base) {
  if (!s || !base) return ['', ''];
  if (s === base) return ['REFERENCE', 'ea'];
  const better = dxlScore(s) > dxlScore(base);
  const halfWorse = (s.train < base.train && s.test > base.test) || (s.train > base.train && s.test < base.test);
  if (better && halfWorse) return ['ONE HALF ONLY', 'unt'];
  if (better && !dxlOk(s, base)) return ['FAILS THE GUARD', 'unt'];
  return better ? ['BETTER', 'lab'] : ['WORSE', 'unt'];
}

// ---------- jobs: run everything / autotune ----------
async function dxlStart(kind, key) {
  const r = await api('/api/dexlab_start', dxlBody({ kind, key, params: DXL.params, objective: DXL.objective, guard: DXL.guard }));
  if (r.error) { DXL.err = r.error; dxlRender(); return; }
  DXL.err = ''; DXL.job = { running: true, kind, phase: 'starting', done: 0, total: 1 };
  clearInterval(DXL.poll); DXL.poll = setInterval(dxlPoll, 900); dxlRender();
}
async function dxlPoll() {
  try {
    const j = await api('/api/dexlab_job', {}); DXL.job = j;
    if (!j.running) {
      clearInterval(DXL.poll); DXL.poll = 0;
      if (j.error) DXL.err = 'Dexter\'s Lab: ' + j.error;
      const r = j.result;
      if (r && r.kind === 'all') for (const [k, v] of Object.entries(r.runs)) DXL.res[k] = v;
      if (r && (r.kind === 'tune' || r.kind === 'tune_all')) {
        for (const [k, t] of Object.entries(r.tuned)) { DXL.tuned[k] = t; if (t.found) { DXL.params[k] = { ...t.params }; DXL.res[k] = t.result; } }
        if (r.pick) DXL.pick = r.pick;
      }
    }
  } catch (e) { clearInterval(DXL.poll); DXL.poll = 0; DXL.err = 'Lost contact with the lab: ' + e.message; }
  dxlRender();
}
async function dxlStop() { await api('/api/dexlab_stop', {}); }

// ---------- one experiment: a slider moved ----------
function dxlSlide(key, name, v) {
  DXL.params[key] = { ...DXL.params[key], [name]: Number(v) }; DXL.busy[key] = true;
  const lab = document.getElementById(`dxv_${key}_${name}`); if (lab) lab.textContent = v;
  clearTimeout(DXL.t[key]);
  DXL.t[key] = setTimeout(async () => {
    try { DXL.res[key] = await api('/api/dexlab_one', dxlBody({ key, params: DXL.params[key] })); } catch (e) { DXL.err = 'The run failed: ' + e.message; }
    DXL.busy[key] = false; dxlRender();
  }, 420);
}

// ---------- apply: the experiment becomes the setting (saved), and the lab re-reads it ----------
async function dxlApply(key, sets, title) {
  if (!sets || !Object.keys(sets).length) return;
  const box = document.createElement('div');
  box.style.cssText = 'position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.55);z-index:999';
  const step = (pct, txt) => { box.innerHTML = `<div class="crt" style="min-width:380px"><div class="crth">🧪 APPLYING ${esc(title).toUpperCase()}</div><div>${txt}</div><div class="dexprog-bar" style="margin-top:8px"><div style="height:100%;width:${pct}%;background:#ffd740"></div></div></div>`; };
  document.body.appendChild(box); step(15, 'writing the experiment into the settings…');
  CUR = { ...CUR, ...sets }; markForm();
  step(45, 'running it on the chart…'); await runSim();
  step(75, 'saving it…');
  try {
    const r = await api('/api/save', { inputs: CUR, ds: SRC.ds, mode: SRC.mode, result: TT ? TT.year : null });
    await loadSaved();
    step(100, `<b>Applied and saved</b> as ${esc(r.name)}. The lab now treats it as the baseline and re-runs every experiment on it.`);
  } catch (e) { step(100, `<span class="neg">Applied to the chart, but saving failed: ${esc(e.message)}</span>`); }
  setTimeout(() => box.remove(), 2800);
  DXL.key = ''; dxlEnsure();
}

// ---------- MT5 verification ----------
async function dxlMt5(items) {
  const r = await api('/api/dexlab_mt5', dxlBody({ items }));
  if (r.error) { DXL.err = r.error; dxlRender(); return; }
  DXL.err = ''; clearInterval(DXL.mt5poll); DXL.mt5poll = setInterval(dxlMt5Status, 4000); dxlMt5Status();
}
async function dxlMt5Status() {
  try {
    DXL.mt5 = await api('/api/dexlab_mt5_status', dxlBody());
    if (!DXL.mt5.busy && DXL.mt5poll) { clearInterval(DXL.mt5poll); DXL.mt5poll = 0; }
    if (DXL.mt5.busy && !DXL.mt5poll) DXL.mt5poll = setInterval(dxlMt5Status, 4000);
  } catch (e) { /* the MT5 panel just stays as it was */ }
  dxlRender();
}
function dxlMt5Of(key, sets) {
  const rs = (DXL.mt5 && DXL.mt5.results || []).filter((r) => r.key === key);
  if (!rs.length) return null;
  const r = rs[rs.length - 1];
  r.current = JSON.stringify(Object.entries(r.sets || {}).sort()) === JSON.stringify(Object.entries(sets || {}).map(([k, v]) => [k, String(v)]).sort());
  return r;
}

// ---------- drawing ----------
const dxlM = (v) => (v == null ? '–' : money(Number(v)));
function dxlDelta(a, b, good = 1, fmt = (x) => Math.round(x).toLocaleString('en-US')) {
  if (a == null || b == null) return '';
  const d = a - b; if (Math.abs(d) < 1e-9) return ' <small class="k">(=)</small>';
  return ` <small class="${d * good > 0 ? 'pos' : 'neg'}">(${d > 0 ? '+' : ''}${fmt(d)})</small>`;
}
function dxlSpark(eq, color) {
  if (!eq || eq.length < 2) return '';
  const W = 240, H = 46, lo = Math.min(0, ...eq), hi = Math.max(1, ...eq);
  const pts = eq.map((v, i) => `${(i * W / (eq.length - 1)).toFixed(1)},${(H - 3 - (v - lo) / (hi - lo) * (H - 6)).toFixed(1)}`).join(' ');
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" style="display:block"><line x1="0" x2="${W}" y1="${H - 3 - (0 - lo) / (hi - lo) * (H - 6)}" y2="${H - 3 - (0 - lo) / (hi - lo) * (H - 6)}" stroke="#37474f" stroke-dasharray="3 3"/><polyline fill="none" stroke="${color}" stroke-width="1.6" points="${pts}"/></svg>`;
}
function dxlCurve(curve, cur, unit) {                   // autotune: net for every value tried, the winner marked
  if (!curve || !curve.length) return '';
  const W = 240, H = 54, nets = curve.map((c) => c.net ?? 0), lo = Math.min(0, ...nets), hi = Math.max(1, ...nets), bw = W / curve.length;
  return `<svg viewBox="0 0 ${W} ${H + 12}" width="100%" style="display:block">${curve.map((c, i) => {
    const v = c.net ?? 0, y0 = H - (0 - lo) / (hi - lo) * H, y = H - (v - lo) / (hi - lo) * H;
    const col = Math.abs(c.v - cur) < 1e-9 ? '#ffd740' : !c.ok ? '#546e7a' : v >= 0 ? '#69f0ae' : '#ff5252';
    return `<rect x="${i * bw + 1}" y="${Math.min(y, y0)}" width="${bw - 2}" height="${Math.max(1, Math.abs(y0 - y))}" fill="${col}"><title>${c.v}${unit}: ${dxlM(c.net)}${c.ok ? '' : ' (fails the guard)'}</title></rect>`;
  }).join('')}<text x="0" y="${H + 10}" font-size="9" fill="#b0bec5">${curve[0].v}${unit}</text><text x="${W}" y="${H + 10}" font-size="9" fill="#b0bec5" text-anchor="end">${curve[curve.length - 1].v}${unit}</text></svg>`;
}
function dxlSquare(title, s, base, color) {
  if (!s) return `<div class="crt" style="flex:1 1 120px;min-width:0;font-size:11px;padding:6px 8px"><div class="crth" style="font-size:10px">${title}</div>…</div>`;
  const cmp = base && s !== base;
  return `<div class="crt" style="flex:1 1 120px;min-width:0;font-size:11px;padding:6px 8px;border-color:${color}"><div class="crth" style="font-size:10px;margin:0 0 3px">${title}</div>
    <div><b style="font-size:13px">${dxlM(s.net)}</b>${cmp ? dxlDelta(s.net, base.net) : ''}</div>
    <div>win rate <b>${s.wr}%</b>${cmp ? dxlDelta(s.wr, base.wr, 1, (x) => x.toFixed(1)) : ''} · PF <b>${s.pf ?? '–'}</b></div>
    <div>worst <b>${dxlM(s.worst)}</b>${cmp ? dxlDelta(s.worst, base.worst) : ''}</div>
    <div>avg win <b>${dxlM(s.avg_win)}</b>${cmp ? dxlDelta(s.avg_win, base.avg_win) : ''} / avg loss <b>${dxlM(s.avg_loss)}</b>${cmp ? dxlDelta(s.avg_loss, base.avg_loss) : ''}</div>
    <div>drawdown <b>${dxlM(s.dd)}</b>${cmp ? dxlDelta(s.dd, base.dd, -1) : ''}</div>
    <div>${s.n} trades · streak ${s.streak}</div></div>`;
}
function dxlHalves(s, base) {
  const L = (DXL.diag && DXL.diag.labels) || ['first half', 'second half'];
  const h = (v, b) => `<b class="${v > 0 ? 'pos' : 'neg'}">${dxlM(v)}</b>${b != null ? dxlDelta(v, b) : ''}`;
  return `<div class="note" style="margin:4px 0">${esc(L[0])}: ${h(s.train, base && s !== base ? base.train : null)} · ${esc(L[1])}: ${h(s.test, base && s !== base ? base.test : null)}</div>`;
}

function dxlCard(e, base) {
  const r = DXL.res[e.key], s = r && r.stats, t = DXL.tuned[e.key], p = DXL.params[e.key] || {};
  const [vt, vc] = dxlVerdict(s, base);
  const sliders = e.params.map(([n, label, lo, hi, step, , unit]) => {
    const v = p[n] ?? lo;
    return `<label class="lever"><span>${esc(label)} <b id="dxv_${e.key}_${n}">${v}</b>${unit && unit !== '×' ? ' ' + esc(unit) : unit}</span>
      <input type="range" min="${lo}" max="${hi}" step="${step}" value="${v}" oninput="dxlSlide('${e.key}','${n}',this.value)"></label>`;
  }).join('');
  const sets = r && r.sets ? r.sets : null, m5 = sets ? dxlMt5Of(e.key, sets) : null;
  let mt5 = '';
  if (m5) mt5 = m5.status === 'complete'
    ? `<div class="crt" style="font-size:11px;border-color:${m5.current ? '#00e676' : '#546e7a'}"><div class="crth" style="font-size:10px">MT5 VERDICT${m5.current ? '' : ' · EARLIER VALUES'}</div>
       ${dxlM(m5.net)} · PF ${esc(String(m5.pf ?? '–'))} · drawdown ${esc(String(m5.dd ?? '–'))} · worst ${dxlM(m5.largest_loss)} · ${m5.trades} trades
       ${m5.run_id ? `<br><a href="/api/mt5_report?id=${esc(m5.run_id)}" target="_blank">MT5 report</a>` : ''}</div>`
    : `<div class="note bad">MT5: ${esc(m5.error || m5.status)}</div>`;
  const queued = DXL.mt5 && DXL.mt5.busy && (DXL.mt5.queue || []).includes(e.key);
  const tuneNote = t ? (t.found ? `<div class="note">🧠 autotuned for ${DXL_OBJ[DXL.objective]}: ${Object.entries(t.params).map(([k, v]) => `${esc(k)} ${v}`).join(' · ')}</div>
      ${e.params.length ? dxlCurve(t.curves[e.params[0][0]], t.params[e.params[0][0]], e.params[0][6] || '') : ''}`
    : '<div class="note bad">🧠 autotune found no value that passes the guard (both halves profitable, no extra risk)</div>') : '';
  const isBase = e.key === 'baseline';
  return `<div class="levers dexpanel" id="dxc_${e.key}" style="padding:10px;border-color:${vc === 'lab' ? '#00e676' : vc === 'unt' ? '#ff5252' : '#26c6da'}">
    <div class="crth" style="margin:0 0 3px;display:flex;justify-content:space-between;gap:6px"><span>${e.letter} · ${esc(e.title).toUpperCase()}</span>${vt ? `<span class="tag ${vc}">${vt}</span>` : ''}</div>
    <div class="note" style="margin:0 0 6px">${esc(e.why)}</div>${sliders}
    ${DXL.busy[e.key] ? '<div class="dexprog"><div class="dexprog-t">TESTING…</div></div>' : ''}
    ${isBase ? dxlSquare('THE LIVE SETTING', s, null, '#26c6da') : `<div style="display:flex;gap:6px;flex-wrap:wrap">${dxlSquare('BASELINE', base, null, '#37474f')}${dxlSquare('WITH THIS EXPERIMENT', s, base, '#ffd740')}</div>`}
    ${s ? dxlHalves(s, base) + dxlSpark(s.eq, vc === 'unt' ? '#ff8a80' : '#69f0ae') : ''}${tuneNote}${mt5}
    ${sets && Object.keys(sets).length ? `<div class="note" style="margin:2px 0">changes: ${Object.entries(sets).map(([k, v]) => `${esc(k.replace(/^Inp/, ''))} ${esc(String(v))}`).join(' · ')}</div>` : ''}
    ${isBase ? '' : `<div class="bar">
      <button class="dexbtn sm" onclick="dxlStart('tune','${e.key}')" ${DXL.job && DXL.job.running ? 'disabled' : ''}>🧠 Autotune</button>
      <button class="dexbtn sm" onclick='dxlApply("${e.key}", ${JSON.stringify(sets || {})}, ${JSON.stringify(e.letter + " · " + e.title)})' ${sets && Object.keys(sets).length ? '' : 'disabled'}>✔ Apply this experiment</button>
      <button class="dexbtn sm" onclick='dxlMt5([{key:"${e.key}",title:${JSON.stringify(e.letter + " · " + e.title)},sets:${JSON.stringify(sets || {})}}])' ${sets && !queued && !(DXL.mt5 && DXL.mt5.busy) ? '' : 'disabled'}>${queued ? 'MT5 queued…' : '🧪 Verify in MT5'}</button></div>`}
  </div>`;
}

function dxlDiagHTML() {
  if (DXL.diagBusy) return `<div class="dexprog"><div class="dexprog-t">READING EVERY TRADE OF THE LIVE SETTING…</div><div class="dexprog-s">time in trade, how far winners and losers dip, streaks, overlapping positions</div></div>`;
  const D = DXL.diag; if (!D || !D.base) return D ? `<p class="note">${esc((D.insights || [''])[0])}</p>` : '';
  const d = D.diag, b = D.base;
  const cell = (l, v) => `<div style="flex:1 1 130px"><div class="k" style="font-size:10px">${l}</div><b>${v}</b></div>`;
  return `<div class="crt"><div class="crth">THE DIAGNOSIS · ${b.n} TRADES OF THE LIVE SETTING</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin:6px 0">
      ${cell('NET', dxlM(b.net))}${cell('WIN RATE', b.wr + '%')}${cell('BREAK-EVEN WIN RATE', (d.breakeven_wr ?? '–') + '%')}${cell('AVG WIN / LOSS', `${dxlM(d.avg_win)} / ${dxlM(d.avg_loss)}`)}
      ${cell('WORST TRADE', dxlM(b.worst))}${cell('WORST PAIR OPEN TOGETHER', dxlM(b.worst_pair))}${cell('MAX DRAWDOWN', dxlM(b.dd))}${cell('LOSING STREAK', b.streak)}
      ${cell('WINNERS CLOSE IN', `${d.win_minutes.p50} min`)}${cell('LOSERS CLOSE IN', `${d.loss_minutes.p50} min`)}${cell('95% OF WINNERS DIP UNDER', '$' + d.win_mae.p95)}${cell('TYPICAL STOP', '$' + d.stop_p50)}
    </div>
    <div style="margin-top:6px">${D.insights.map((x) => `<div style="margin:3px 0">🔬 ${esc(x)}</div>`).join('')}</div></div>`;
}

function dxlBoard(base) {
  if (!DXL.spec || !base) return '';
  const rows = DXL.spec.filter((e) => e.key !== 'baseline' && DXL.res[e.key] && DXL.res[e.key].stats)
    .map((e) => ({ e, s: DXL.res[e.key].stats })).sort((a, b) => dxlScore(b.s) - dxlScore(a.s));
  if (!rows.length) return '';
  const h = (v) => `<span class="${v > 0 ? 'pos' : 'neg'}">${dxlM(v)}</span>`;
  return `<div class="crth" style="margin-top:12px">LEADERBOARD · RANKED BY ${DXL_OBJ[DXL.objective].toUpperCase()}</div>
    <table><tr><th>#</th><th>Experiment</th><th>Net</th><th>Win rate</th><th>PF</th><th>Worst</th><th>Drawdown</th><th>Trades</th><th>${esc((DXL.diag.labels || [])[0] || '1st')}</th><th>${esc((DXL.diag.labels || [])[1] || '2nd')}</th><th></th></tr>
    <tr style="opacity:.75"><td>–</td><td>0 · Baseline</td><td>${dxlM(base.net)}</td><td>${base.wr}%</td><td>${base.pf ?? '–'}</td><td>${dxlM(base.worst)}</td><td>${dxlM(base.dd)}</td><td>${base.n}</td><td>${h(base.train)}</td><td>${h(base.test)}</td><td></td></tr>
    ${rows.map(({ e, s }, i) => { const [vt, vc] = dxlVerdict(s, base); return `<tr onclick="document.getElementById('dxc_${e.key}').scrollIntoView({behavior:'smooth',block:'center'})" style="cursor:pointer">
      <td>${i + 1}</td><td>${e.letter} · ${esc(e.title)}</td><td>${dxlM(s.net)}${dxlDelta(s.net, base.net)}</td><td>${s.wr}%${dxlDelta(s.wr, base.wr, 1, (x) => x.toFixed(1))}</td>
      <td>${s.pf ?? '–'}</td><td>${dxlM(s.worst)}${dxlDelta(s.worst, base.worst)}</td><td>${dxlM(s.dd)}${dxlDelta(s.dd, base.dd, -1)}</td><td>${s.n}</td><td>${h(s.train)}</td><td>${h(s.test)}</td><td><span class="tag ${vc}">${vt}</span></td></tr>`; }).join('')}</table>`;
}

function dxlPickHTML(base) {
  const k = DXL.pick; if (!k) return '';
  if (!k.used.length) return '<div class="crt" style="margin-top:12px">🧠 DEXTER\'S PICK: no combination beat the baseline on ' + DXL_OBJ[DXL.objective] + ' with the guard on. The live setting is already the best the levers can make it.</div>';
  const titles = k.used.map((u) => { const e = DXL.spec.find((x) => x.key === u); return e ? `${e.letter} · ${e.title}` : u; });
  return `<div class="levers dexpanel" style="margin-top:12px;padding:12px;border-color:#ffd740">
    <div class="crth">🧠 DEXTER'S PICK · ${esc(titles.join(' + ')).toUpperCase()}</div>
    <div class="note">The autotuned experiments stacked one at a time, each kept only while ${DXL_OBJ[DXL.objective]} kept improving${DXL.guard ? ', both halves stayed profitable and the risk did not grow' : ''}.</div>
    <div style="display:flex;gap:6px;flex-wrap:wrap">${dxlSquare('BASELINE', base, null, '#37474f')}${dxlSquare("DEXTER'S PICK", k.stats, base, '#ffd740')}</div>
    ${k.stats ? dxlHalves(k.stats, base) + dxlSpark(k.stats.eq, '#ffd740') : ''}
    <div class="note">changes: ${Object.entries(k.sets).map(([a, v]) => `${esc(a.replace(/^Inp/, ''))} ${esc(String(v))}`).join(' · ')}</div>
    <div class="bar"><button class="dexbtn" onclick='dxlApply("pick", ${JSON.stringify(k.sets)}, "Dexter&#39;s pick")'>✔ APPLY DEXTER'S PICK</button>
      <button class="dexbtn sm" onclick='dxlMt5([{key:"pick",title:"Dexter&#39;s pick",sets:${JSON.stringify(k.sets)}}])' ${DXL.mt5 && DXL.mt5.busy ? 'disabled' : ''}>🧪 Verify in MT5</button></div>
    ${(() => { const m = dxlMt5Of('pick', k.sets); return m && m.status === 'complete' ? `<div class="crt" style="font-size:11px">MT5 VERDICT${m.current ? '' : ' · EARLIER PICK'}: ${dxlM(m.net)} · PF ${esc(String(m.pf))} · drawdown ${esc(String(m.dd))} · worst ${dxlM(m.largest_loss)}</div>` : ''; })()}
  </div>`;
}

function dxlArchive() {
  return `<details style="margin-top:16px"><summary class="crth" style="cursor:pointer">ARCHIVE · THE FIRST MT5 COMPARISON ON COPILOT'S REFERENCE SETTING</summary>
    <div id="dxlArch" class="note" style="margin-top:6px">${DXL.arch || 'loading…'}</div></details>`;
}
async function dxlArchLoad() {
  if (DXL.archLoaded) return; DXL.archLoaded = true;
  try {
    const st = await api('/api/dexter'), rs = st.results || [];
    DXL.arch = rs.length ? `<table><tr><th>Experiment</th><th>Net</th><th>PF</th><th>Drawdown</th><th>Worst</th><th>Trades</th></tr>${rs.map((r) => `<tr><td>${esc(r.title)}</td><td>${dxlM(r.net)}</td><td>${esc(String(r.pf ?? '–'))}</td><td>${esc(String(r.drawdown ?? '–'))}</td><td>${dxlM(r.largest_loss)}</td><td>${r.trades ?? '–'}</td></tr>`).join('')}</table><p class="note">Reference run ${esc(st.reference_id || '')}, MT5, Jan–Oct 2026.</p>` : 'No archived comparison.';
  } catch (e) { DXL.arch = 'Could not load the archive.'; }
  dxlRender();
}

function pDex() {
  dxlEnsure(); dxlArchLoad();
  const base = DXL.res.baseline && DXL.res.baseline.stats, name = dxlSaveName(), J = DXL.job, M = DXL.mt5;
  const opts = (SAVEDS || []).map((s, i) => `<option value="${i}" ${s.name === name ? 'selected' : ''}>${esc(s.name)}${s.result ? ` · ${money(s.result.net)} · WR ${s.result.wr}%` : ''}</option>`).join('');
  const prog = J && J.running ? `<div class="dexprog"><div class="dexprog-t">🧪 ${esc((J.phase || '').toUpperCase())} · ${J.total ? Math.min(100, Math.round(100 * J.done / J.total)) : 0}%</div>
    <div class="dexprog-bar"><div style="height:100%;width:${J.total ? Math.min(100, 100 * J.done / J.total) : 0}%;background:repeating-linear-gradient(45deg,#00e676 0 10px,#00c853 10px 20px);transition:width .4s"></div></div>
    <div class="dexprog-s">${J.done} of ${J.total} tester runs · ${J.seconds || 0} s</div></div>` : '';
  const mprog = M && M.busy ? `<div class="dexprog"><div class="dexprog-t">MT5 STRATEGY TESTER · ${M.current} OF ${M.total}</div><div class="dexprog-s">${esc(M.phase || '')}</div></div>` : '';
  const top = base ? DXL.spec.filter((e) => e.key !== 'baseline' && DXL.res[e.key] && DXL.res[e.key].stats && dxlVerdict(DXL.res[e.key].stats, base)[1] === 'lab')
    .sort((a, b) => dxlScore(DXL.res[b.key].stats) - dxlScore(DXL.res[a.key].stats)).slice(0, 3) : [];
  return `<div class="lab">
    <div class="crth" style="font-size:16px">🧪 DEXTER'S LAB · MAKE THE LIVE SETTING BETTER</div>
    <div class="levers dexpanel" style="padding:12px;margin:8px 0">
      <div class="crth" style="margin:0">WHICH SETTING IS IN THE LAB?</div>
      <div class="note" style="margin:4px 0">The one on the chart: <b>${name ? esc(name) : 'unsaved changes on the chart'}</b> · ${esc(dxlDsLabel())} · ${esc(SRC.mode === 'chart' ? "the chart's rules" : 'EA rules')}${base ? ` · ${base.n} trades · ${dxlM(base.net)}` : ''}</div>
      <div class="bar"><select id="dxlSave" style="background:#03140b;color:#b9f6ca;border:2px solid #37474f;border-radius:8px;font:12px 'Courier New',monospace;padding:4px;max-width:420px">
        <option value="">bring another saved setting to the lab…</option>${opts}</select>
        <span class="note">Objective:</span><select id="dxlObj" style="background:#03140b;color:#b9f6ca;border:2px solid #37474f;border-radius:8px;font:12px 'Courier New',monospace;padding:4px">
        ${Object.entries(DXL_OBJ).map(([k, v]) => `<option value="${k}" ${k === DXL.objective ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select>
        <label class="tog"><input type="checkbox" id="dxlGuard" ${DXL.guard ? 'checked' : ''}> guard: both halves profitable, no more than 25% extra drawdown or worst loss</label></div>
    </div>
    ${DXL.err ? `<p class="note bad">${esc(DXL.err)}</p>` : ''}
    ${dxlDiagHTML()}
    <div class="bar" style="margin:12px 0">
      <button class="dexbtn" onclick="dxlStart('all')" ${J && J.running || !base ? 'disabled' : ''}>▶ RUN EVERY EXPERIMENT</button>
      <button class="dexbtn" onclick="dxlStart('tune_all')" ${J && J.running || !base ? 'disabled' : ''}>🧠 AUTOTUNE EVERYTHING</button>
      <button class="dexbtn sm" onclick='dxlMt5(${JSON.stringify(top.map((e) => ({ key: e.key, title: e.letter + " · " + e.title, sets: DXL.res[e.key].sets })))})' ${top.length && !(M && M.busy) ? '' : 'disabled'}>🧪 Verify the top ${top.length || 3} in MT5</button>
      ${J && J.running ? '<button class="dexbtn sm" onclick="dxlStop()">■ Stop</button>' : ''}${M && M.busy ? '<button class="dexbtn sm" onclick="api(\'/api/dexlab_mt5_stop\',{})">■ Stop MT5</button>' : ''}
    </div>${prog}${mprog}
    <p class="note">Each experiment changes only what its card says, on the live setting, in the Turtle TV tester (instant). Move a slider to fine-tune it; 🧠 Autotune finds the values that give ${DXL_OBJ[DXL.objective]}${DXL.guard ? ' without taking more risk (both halves profitable, drawdown and worst loss at most 25% worse)' : ''}; ✔ Apply saves it as your setting; 🧪 Verify runs it in MT5 (2026, the rig's data) - MT5 decides.</p>
    ${dxlPickHTML(base)}${dxlBoard(base)}
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-top:12px">${(DXL.spec || []).map((e) => dxlCard(e, base)).join('')}</div>
    ${dxlArchive()}${dxlFindings()}</div>`;
}

// Research notes (Zee 2026-10-28: "note these findings down at the end of the page: Dexter's Lab where we can read it .. the ifs,whys and buts of ths strategy").
// Full notes + scripts: monitor/saad_view/research/ (RESEARCH_93pct_loss_2026-10-27.md, gates6.py, p4.py, rules_doc.py).
function dxlFindings() {
  const T = (head, rows) => `<div class="scroll"><table><tr>${head.map((h) => `<th>${h}</th>`).join('')}</tr>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')}</table></div>`;
  const H = (t) => `<div class="crth" style="margin-top:14px">${t}</div>`;
  return `<div class="levers dexpanel" style="margin-top:16px;padding:14px;border-color:#ffd740">
  <div class="crth" style="font-size:15px;margin:0">📓 LAB NOTEBOOK · THE IFS, WHYS AND BUTS OF THE 93.8% SETTING (Oct 27–28, 2026)</div>
  <p class="note">Setting <b>2026-10-25 05-58-25</b>: target 20 pips ($2 → +$400 at 2 lots), stop $25 (−$5,000). On 15-minute data 2023–2026: 1,852 trades, 93.8% win rate, +$264,191.
  Tester rows are hypotheses; rows marked <b>MT5</b> are real Strategy Tester runs (the rig covers Jan–Oct 2026 only).</p>

  ${H('1 · WHY THE BIG LOSS EXISTS')}
  <p class="note">The loss is the geometry, not bad setups: $2 target against a $25 stop = 12.5 : 1, so the strategy needs 92.6% wins just to break even.
  Winners dip deep before they win: half dip more than $1.78, 10% dip more than $9, 5% more than $13. <b>The wide stop IS the win rate.</b>
  A $5 stop keeps only 78% of winners, $10 keeps 91%, $15 keeps 96% - every tighter stop turns winners into losers almost as fast as it shrinks the loss.
  Most losers die on 1–3 violent candles (killer candle ≈ 2.2× ATR), not a slow drift.</p>

  ${H('2 · FILTERS AT ENTRY - NONE FINDS THE LOSERS')}
  <p class="note">A filter only pays if the trades it removes lose more than ~7.4% of the time. Every one below removes trades that still win ~93%, and the worst loss stays ≈ −$5,100.</p>
  ${T(['Filter', 'Kept', 'Win rate', 'Net', 'Removed trades lose', 'Verdict'], [
    ['None (the setting)', '1,852', '93.8%', '+$264,191', '–', ''],
    ['Camel humps (with / against trend)', '', '', '', '6.5–6.7% both', '✗ no separation'],
    ['EMA slopes 19/66/200/264/800, EMA 19 vs 66', '', '', '', '4.3–8.1%', '✗'],
    ['Chop: CHOP, ER, ADX, VHF, R²', '', '', '', 'max 8.1%, not in both halves', '✗'],
    ['ATR / shock / day range', '', '', '', 'big days lose LESS', '✗'],
    ['Tick speed ≥ 1× normal (real ticks)', '1,318', '94.4%', '+$190,515', '7.5%', '✗ −$74k'],
    ['Tick speed ≥ 2× normal', '392', '95.4%', '+$75,193', '6.6%', '✗ −$189k'],
    ['Heaviest ticks in the candle tail (POC)', '390', '94.9%', '+$63,786', '6.4%', '✗ −$200k'],
    ['H1 MACD histogram growing our way', '831', '94.6%', '+$149,150', '6.8%', '✗ −$115k'],
    ['H1 50 EMA sloping our way', '807', '93.8%', '+$119,331', '6.1%', '✗ −$145k'],
    ['M15 ATR(14) ≥ $3', '1,296', '93.7%', '+$174,275', '5.8%', '✗ −$90k'],
    ['London/NY overlap only', '532', '94.2%', '+$102,130', '6.3%', '✗ −$162k'],
    ['Liquidity swept first', '974', '93.8%', '+$138,625', '6.2%', '✗ −$126k'],
    ['InpTrendAlign (orange above blue) - MT5', '', '', '−$28,099 (2026)', '', '✗ vs −$4,101'],
  ])}

  <p class="note bad"><b>⚠ CORRECTION (Oct 28, later):</b> every MT5 row in sections 3, 4, 8 and 9 ran the EA on a <b>1-minute chart</b> (the Dexter's Lab MT5 button
  paired MT5 with the 1-minute tester data). These settings were tuned on <b>15-minute</b> candles, so those rows tested a different strategy. On a 15-minute chart MT5 matches
  the tester: section 11 has the clean 2023–2026 results. Read the 1-minute rows as "what happens on M1", not as a verdict on these settings.</p>
  ${H('3 · EXITS - BIGGER WIN IS THE ONLY LEVER MT5 BACKS')}
  ${T(['Change (MT5, Jan–Oct 2026)', 'Net', 'Trades', 'Win rate', 'Avg win', 'Worst'], [
    ['Saved (TP 20 pips, stop $25)', '−$4,101', '793', '92.9%', '$376', '−$5,182'],
    ['Stop $20', '−$6,328', '755', '', '$377', '−$4,220'],
    ['Stop $15', '−$8,346', '816', '', '$375', '−$3,434'],
    ['TP 25 pips', '+$17,977', '678', '92.3%', '$447', '−$5,388'],
    ['TP 30 pips', '+$5,290', '627', '90.9%', '$513', '−$5,388'],
    ['TP 35 pips', '+$26,722', '552', '90.6%', '$577', '−$5,388'],
    ['TP 40 pips', '+$29,101', '537', '89.8%', '$634', '−$5,388'],
  ])}
  <p class="note">Tester: a decay stop (cut trades underwater after N candles) lost money in every cell; ATR stops 2–6× worse on net AND worst loss.
  Note: the 4-year 15-minute tester said 2026 = +$64.8k for this setting; MT5 said −$4.1k. Exit interference again: every rule that closes a trade between stop and target cost money.</p>

  ${H('4 · PROBE / GHOST ENTRIES - RISK SMALL UNTIL IT PROVES ITSELF')}
  <p class="note">Open 0.01 (or a ghost) at the setup, add the 2 lots only once price confirms. Tested on saved setting <b>2026-10-27 23-50-31</b> (15-minute, 2023–2026: 994 trades, 46%, +$893,648, worst −$9,308).</p>
  ${T(['Variant', 'Win rate', 'Net', 'Worst'], [
    ['Saved, no probe', '46.0%', '+$893,648', '−$9,308'],
    ['After 4 candles in profit > $5', '40.4%', '+$162,431', '−$11,833'],
    ['After 4 candles > $10', '42.6%', '+$42,391', '−$11,833'],
    ['After 4 candles > $15 / $20', '43–44%', '≈ $0', '−$4.9 to −6.6k'],
    ['+ stop to ghost entry, after 1–3 candles > $2', '32–36%', '+$51k to +$82k', '−$4.0 to −4.5k'],
    ['+ stop to ghost entry, +$5 any time', '27.8%', '+$105,504', '−$1,840'],
    ['+ stop to ghost entry, +$0.50 any time', '6.3%', '−$34,264', '−$1,512'],
  ])}
  <p class="note">Why it fails: the big winners are already running when we confirm, so the 2 lots come in late and miss the move; a stop at the ghost entry gets knocked out by the
  normal pullback before the run. On the 93.8% setting (MT5 2026) probe 0.01 / +$0.50 made +$21,471 vs −$4,101, but the worst loss stayed −$5,293.
  Setting 23-50-31 itself was <b>−$53,392 in MT5 2026</b> (DD 55%) - the 4-year tester overstates 2026.</p>

  ${H('5 · THE ORIGINAL RULES (mt5/RULES_EMA_SAAD.md, as written, 1 lot)')}
  ${T(['Version', 'Trades', 'Win rate', 'Net', 'PF'], [
    ['As written', '6,639', '46.9%', '−$570,900', '0.77'],
    ['+ breakeven at $3', '8,006', '39.1%', '−$830,639', '0.64'],
    ['+ no chop (ER16 ≥ 0.11)', '5,709', '45.8%', '−$472,061', '0.77'],
    ['+ no chop (ADX ≥ 25)', '4,377', '44.6%', '−$387,402', '0.76'],
  ])}

  ${H('6 · THE BUTS - WHAT WE KNOW NOW')}
  <p class="note">• No filter known at entry separates the 6% losers from the 94% winners on this setting; it is a mean-reversion bounce and trend direction is irrelevant to it.<br>
  • The $5,000 loss can only be shrunk by shrinking the stop or the lots - and both shrink the wins at the same rate. There is no "100% cure" in the data.<br>
  • What MT5 supports: a bigger target (35–40 pips) - about +$27–29k in 2026 at ~90% win rate. The loss stays ~$5,400.<br>
  • Rank settings on MT5 or the 2026 tick-matched data before trusting the 4-year 15-minute tester for 2026.</p>

  ${H('7 · THE CURE HUNT (Oct 28) · EVERY METHOD FROM THE TWO NOTES, TRIED')}
  <p class="note">Same setting, 15-minute data 2023–2026, 1,852 trades. <b>Engine</b> = the Overview's tester with the method switched on.
  <b>Replay</b> = the engine's own entries replayed on real bid/ask ticks with the method acting (when it does not fire, the engine's result stands;
  the replay reproduces the engine within 2%: +$269,030 vs +$264,191). Halves = 2023–24 / 2025–26. Tester only - MT5 decides.</p>
  <p class="note"><b>Kaplan-Meier (how long trades live):</b> winners close in a median 10.6 min (75% within 49 min, 90% within 3 h); losers live a median
  131 min. The 83 big losers last 148 min, but reach −$10 within 36 min (median) - and 8.9% of WINNERS also dip beyond −$10 before winning.
  So time separates them only after the damage is mostly done.</p>
  ${T(['Method', 'How', 'Win rate', 'Net', 'Worst', 'Halves', 'Verdict'], [
    ['<b>Baseline</b>', 'engine', '93.8%', '+$264,191', '−$5,158', '+144k / +120k', ''],
    ['Time stop 2 / 4 / 8 / 12 candles', 'engine', '71–79%', '+$42k to +$82k', '−$5,158', 'half 1 ≈ $0', '✗ worst unchanged'],
    ['Stale stop (no profit after 4–8 candles)', 'engine', '74–78%', '+$44k to +$77k', '−$5,158', '', '✗'],
    ['Kinetic stop: tick speed < 0.25–0.6× normal', 'replay', '67–84%', '+$81k to +$142k', '−$5,060 to −$5,158', '', '✗'],
    ['Exponential stop $25·e^(−t/τ), τ 15 min', 'replay', '69.0%', '+$61,388', '−$3,584', '+2k / +59k', '✗'],
    ['… τ 60 min', 'replay', '81.1%', '+$93,844', '−$4,492', '', '✗'],
    ['… τ 480 min', 'replay', '90.4%', '+$181,751', '−$4,870', '+76k / +106k', '✗'],
    ['Ghost stop on the MID price (spread spikes ignored)', 'replay', '93.8%', '+$257,724', '−$5,158', '', '✗ 0 losers saved: the stops are real moves'],
    ['Ghost stop + 10 s confirmation', 'replay', '94.0%', '+$258,676', '−$6,178', '', '✗ 3 saved, worse slips'],
    ['TP 40 pips', 'engine', '88.1%', '+$241,404', '−$8,972', '+117k / +125k', '✗'],
    ['Barbell: half at 20 pips, half at 40', 'engine', '88.3%', '+$238,161', '−$5,656', '+121k / +117k', '✗ close, lower DD $16.2k'],
    ['Barbell + breakeven after lot 1', 'engine', '92.2%', '−$100,784', '−$5,656', '', '✗✗ BE kills lot 2'],
    ['Barbell 20 / 60 + breakeven', 'engine', '91.7%', '−$101,371', '−$5,656', '', '✗✗'],
    ['ATR pyramid: +0.5 lot after +1 ATR (TP 40)', 'replay', '88.6%', '+$293,207', '−$10,728', '', '✗ adds −$3.9k vs TP 40 alone'],
    ['Momentum pyramid: +1 lot at +$2 if H1 MACD + ATR rising', 'replay', '88.6%', '+$294,261', '−$10,963', '', '✗ adds −$2.8k'],
    ['ER sizing: clean setups 3 lots, messy 0.5', 'replay', '93.8%', '+$198,388', '−$7,694', '+112k / +86k', '✗ the internet way round loses'],
    ['ER sizing REVERSED: messy 3 lots, clean 0.5', 'replay', '93.8%', '+$289,380', '−$7,737', '+150k / +140k', '? both halves up, DD $15.8k - bigger worst'],
    ['Exit agent (PPO stand-in, learned on half 1)', 'replay', '91.8%', '+$290,554', '−$5,127', '+192k / <b>+98k</b>', '✗ half 2 worse than baseline (+120k): it memorised'],
    ['Reversal 3× after a stop-out (TP $2 / SL $25)', 'replay', '93.8%', '+$288,215', '−$20,242', '', '✗ worst ×4'],
    ['Reversal 3× (TP $10 / SL $10)', 'replay', '96.3%', '+$320,963', '−$11,320', '+169k / +152k', '? 46 of 83 won (55%)'],
    ['Reversal 3× (TP $25 / SL $25)', 'replay', '96.3%', '+$427,589', '−$20,300', '+196k / +232k', '? 45 of 83 won (54%), DD $60k'],
    ['Reversal 4× (TP $25 / SL $25)', 'replay', '96.3%', '+$482,055', '−$25,400', '', '? DD $80k'],
    ['Hedge USDJPY (corr −0.28), 50% / 100% β', 'replay*', '91.0 / 89.1%', '+$139k → +$115k / +$91k', '→ −$6,451 / −$9,539', '', '✗ big losers −$4,989 → −$4,855'],
    ['Hedge EURUSD (corr +0.38), 50% / 100% β', 'replay*', '88.1 / 84.1%', '→ +$92k / +$45k', '→ −$6,179 / −$12,786', '', '✗'],
    ['Hedge silver (corr +0.74), 50% / 100% β', 'replay*', '81.2 / 72.6%', '→ −$30k / −$199k', '→ −$5,556 / −$9,369', '', '✗ big losers → −$2,816, but every win pays it too'],
    ['Inversion: TP $25 / SL $2', 'engine', '16.1%', '−$100,352', '−$1,626', '−38k / −63k', '✗ proves the wide stop is needed'],
  ])}
  <p class="note">* Hedge test covers 2025–2026 only (1,082 trades, Axi M15 bars of USDJPY / EURUSD / silver exported with mt5/ExportRates.mq5);
  β from the previous 2,000 candles, spread cost included. Not tested: the L2 order book (we have no depth data) and a true PPO network
  (the agent above is the same state and actions with a simpler learner; it already shows the problem - out of sample it does worse).</p>
  <p class="note"><b>Verdict of the cure hunt:</b> nothing removes the $5,000 loss without removing more profit. Everything that cuts the loss early
  (time, tick speed, exponential stop, hedges) also cuts the winners that dip first. Three leads are worth an MT5 check, none is a cure:
  <b>(1) reversal after a stop-out</b> - it does not prevent the loss, it wins it back about 55% of the time (only 83 cases, could be luck; worst loss and DD grow);
  <b>(2) reversed ER sizing</b> - bigger on choppy setups, smaller on clean ones (both halves better, worst loss bigger);
  <b>(3) barbell 20/40 without breakeven</b> - about the same profit with a smaller drawdown. Scripts: research/cure_engine.py, cure_overlay.py, cure_hedge.py.</p>

  <p class="note bad">⚠ Sections 8–9: 1-minute chart runs - see the correction above and section 11.</p>
  ${H('8 · MT5 VERDICT ON THE TWO LEADS (Oct 28) · Blueberry real ticks, Jan–Oct 2026, M1')}
  <p class="note">The reversal was dropped (a coin flip at 3× size). ER sizing was coded into the EA as v1.37 (<code>InpErSize</code>: ER ≤ 0.12 → 3 lots, ER ≥ 0.21 → 0.5 lots, thresholds from 2023–24 only).
  The barbell uses existing EA inputs (<code>InpFixTpPips 40</code>, <code>InpXP1R 0.08</code> = half closed at +$2, <code>InpXP1Be false</code>). Random delay = MT5's latency model.</p>
  ${T(['Run (MT5)', 'Delay', 'Net', 'Trades', 'PF', 'Drawdown', 'Worst', 'Avg win / loss'], [
    ['93.8% saved', 'none', '−$4,101', '793', '0.99', '$48,315 (40.7%)', '−$5,182', '$376 / −$5,025'],
    ['93.8% saved', 'random', '−$18,331', '826', '0.94', '$62,313 (51.6%)', '−$5,364', '$381 / −$3,581'],
    ['<b>Barbell 20/40, no breakeven</b>', 'none', '<b>+$33,097</b>', '1,240', '1.11', '$41,783 (26.4%)', '−$5,180', '$508 / −$3,656'],
    ['<b>Barbell 20/40, no breakeven</b>', 'random', '+$3,867', '1,176', '1.01', '$49,470 (34.0%)', '−$6,044', '$515 / −$3,626'],
    ['ER sizing 3 / 0.5', 'none', '+$1,200', '946', '1.00', '$54,109 (40.3%)', '−$7,989', '$361 / −$4,643'],
    ['ER sizing 3 / 0.5', 'random', '−$12,560', '968', '0.96', '$56,773 (43.1%)', '−$7,833', '$364 / −$3,434'],
    ['ER sizing + barbell', 'none', '−$8,925', '1,339', '0.97', '$75,777 (49.9%)', '−$7,989', '$479 / −$4,112'],
    ['ER sizing + barbell', 'random', '−$351', '1,397', '1.00', '$67,314 (43.7%)', '−$8,022', '$484 / −$3,216'],
  ])}
  <p class="note"><b>Reading:</b> the barbell is the only lead that survives MT5: +$37k better than the saved setting without delay, +$22k better with random delay, and a lower drawdown -
  but with latency it only just breaks even. ER sizing does not survive MT5: the tester's +$25k gain becomes ≈ $0, and its bigger lots raise the worst loss to −$8k.
  As before, 2026 is a hard year for this setting in MT5 (−$4k to −$18k); the 4-year tester's numbers for it are far too kind.</p>

  ${H('9 · MICROSTRUCTURE GATES (Oct 28) · DTW, SYNTHETIC VPIN, GAUSSIAN HMM - BUILT INTO THE EA (v1.38) AND RUN IN MT5')}
  <p class="note">All three are computed by the EA itself on its own ticks, from models trained in Python on 2023–2025 entries only (research/micro.py, micro_export.py;
  files saad_dtw_paths.csv, saad_hmm3.csv, saad_hmm4.csv in Common Files). 2026 - the MT5 year - was never seen in training.
  <b>DTW</b>: the mid-price path of the 15 min before the entry (32 steps, turned the trade's way, scaled 0–1) vs 1,290 training paths; skip when ≥ X% of the 20 nearest lost.
  <b>VPIN</b>: tick test on the last 25,000 ticks, 50 buckets of 500; skip when VPIN is high AND the last 10 buckets' flow runs against the trade.
  <b>HMM</b>: 3 or 4 hidden states on M15 candles (return, tick volatility, EMA dispersion), Baum-Welch training, forward filter only (no hindsight); skip when P(toxic state) &gt; 0.75.
  <b>Parity check</b> (EA vs Python on the same 300 entries): VPIN corr 0.998, flow 0.999, HMM 1.000, DTW 0.89 - the EA computes what Python trained on.
  (A first HMM run read 1-minute candles on the M1 test chart - parity 0.14 - fixed to always read M15; only the fixed runs are below.)</p>
  ${T(['Gate (MT5, 2026, Blueberry ticks)', 'Delay', 'Net', 'Trades', 'Win rate*', 'PF', 'Drawdown', 'Worst'], [
    ['No gate (the 93.8% setting)', 'none', '−$4,101', '793', '92.9%', '0.99', '$48,315 (40.7%)', '−$5,182'],
    ['No gate', 'random', '−$18,331', '826', '89.8%', '0.94', '$62,313 (51.6%)', '−$5,364'],
    ['DTW ≥ 15% of nearest lost', 'none', '−$1,313', '791', '93.0%', '1.00', '$36,735', '−$5,182'],
    ['DTW ≥ 20%', 'none', '+$6,121', '793', '93.2%', '1.02', '$42,131', '−$5,182'],
    ['<b>VPIN ≥ 0.081 & flow ≤ −0.05 against</b>', 'none', '<b>+$14,978</b>', '803', '<b>93.4%</b>', '1.06', '$38,456 (28.8%)', '−$5,182'],
    ['<b>VPIN ≥ 0.081 & flow ≤ −0.05 against</b>', 'random', '<b>+$15,420</b>', '821', '<b>91.4%</b>', '1.06', '$43,766 (30.2%)', '−$5,326'],
    ['VPIN ≥ 0.074 & any flow against', 'none', '+$16,377', '811', '93.3%', '1.06', '$43,132', '−$5,182'],
    ['VPIN ≥ 0.074 & any flow against', 'random', '+$6,814', '849', '90.4%', '1.02', '$46,462', '−$5,354'],
    ['HMM 3 states, P(toxic) &gt; 0.75', 'none', '+$9,207', '736', '92.9%', '1.04', '$37,922 (31.3%)', '−$5,326'],
    ['HMM 4 states, P(toxic) &gt; 0.75', 'none', '+$17,049', '523', '92.5%', '1.10', '<b>$22,809 (19.7%)</b>', '−$5,182'],
    ['DTW 20% + VPIN + HMM (first, unfixed HMM)', 'none', '−$40,407', '793', '92.1%', '0.87', '$59,761', '−$6,878'],
  ])}
  <p class="note">* win rate solved from MT5's trades, net, average win and average loss.
  <b>Reading:</b> the VPIN gate (0.081 / 0.05) is the best result of the whole hunt in MT5: about +$19k better than no gate without delay and +$34k better with random delay,
  win rate +0.5 to +1.6 points, lower drawdown. The 4-state HMM halves the drawdown but trades a third less and does not raise the win rate. DTW is a small plus at 20%.
  <b>The buts:</b> one year only (the MT5 rig has 2026 ticks); each loss is ~$5,000, so +$19k is about 4 fewer losers - real, but small enough to be luck.
  The Python screen of the same VPIN gate said −$5.8k for 2026 (MT5 trades differ: one skipped trade moves every later one). None of the gates touches the size of the $5,000 loss.
  Next step to make it proof: put Blueberry's 2023–2025 ticks into the rig and run the VPIN gate on those years too.</p>

  ${H('10 · WIN-RATE COMBINATION (Oct 28) · SAVED AS 3 SETTINGS - AND THE HOLDOUT TRUTH')}
  <p class="note">Greedy search over the EA's filters, session hours (InpHours, v1.37) and every box of the ten new range-box families, target and stop fixed (research/wr_combine.py).
  Saved settings: <b>2026-10-28 13-00-01 WR 94.6 EA filters</b> (InpSessTo 18, BUY box 11 off, InpMinRangeAtr 1.0: 1,521 trades, 94.6%, +$218,788),
  <b>13-00-02 WR 95.8 boxes</b> (1,131 trades, 95.8%, +$227,788, PF 2.10) and <b>13-00-03 WR 96.1 boxes</b> (1,115 trades, 96.05%, +$237,551, PF 2.23, DD $14.8k).</p>
  <p class="note"><b>Holdout (research/wr_holdout.py):</b> the same search with every pick made on 2023–24 only. On those years the win rate climbed 93.4% → 97.3%;
  on 2025–26, never seen, it went 94.1% → 94.4–94.5% at best, then back to 93.7–94.1%, and profit there fell from +$156k to +$64–115k.
  <b>So most of the 96% is fitted to history; the real gain is about +0.2 to +0.4 points.</b> The one pick that held in both halves is InpSessTo 18 (no new entries after 18:00 server).
  The range-box families exist only in the Turtle TV tester so far - MT5 cannot check those settings until they are ported to the EA.</p>
  <p class="note">Later the same day a stricter search (research/wr_robust.py: every pick must raise the win rate in BOTH halves on its own) added two more saves:
  <b>2026-10-28 15-00-01 WR 96.6 robust</b> (continued from 96.1) and <b>15-00-02 WR 96.4 robust from base</b> (started fresh; 8 steps, both halves up at every step).
  The five range-box families these settings use (Keltner, value area, VWAP, Asian range, Initial Balance) were then ported into the EA (v1.38 TvBox_* inputs) - see section 11.</p>

  ${H('11 · THE CLEAN MT5 VERDICT · 15-MINUTE CHART, BLUEBERRY REAL TICKS, 2023 → OCT 2026 (Oct 28)')}
  <p class="note">Blueberry's 2023–2025 ticks (316.8M, the same feed as the tester) were loaded into the rigs as XAUUSD_BB3 (mt5/BbTickLoad.mq5, monitor/strategy_lab/bb3_install.py);
  2026 runs on XAUUSD_BB. Each year a separate run: $100,000, 2 lots, EA view build v1.38, M15 chart (research/mt5_years.py → mt5_years.json). Win rate solved from MT5's trades, net, average win / loss.
  <b>Parity:</b> the EA puts every entry in the same box as the tester for 100% of 604 entries (all five families); VPIN 0.998, HMM 1.000, DTW 0.84.
  <b>Bug found and fixed on the way:</b> an EMPTY input makes MT5's tester reuse the previous run's value - box masks leaked from one run into the next (280 trades instead of 507).
  The box inputs now default to all-ticked strings and axi_rig.run never sends an empty value; all rows below are from the clean re-run.</p>
  ${T(['MT5 · 15-min chart', 'Delay', '2023', '2024', '2025', '2026 (to Oct 17)', 'TOTAL net', 'Trades', '<b>Win rate</b>', 'Worst'], [
    ['Tester (Turtle TV Overview), the 93.8% save', '–', '+$27,464 · 92.3%', '+$79,544 · 94.1%', '+$91,586 · 94.5%', '+$64,759 · 93.8%', '+$264,191', '1,852', '93.8%', '−$5,158'],
    ['<b>MT5: the 93.8% save</b>', 'none', '+$27,150 · 92.3%', '+$79,944 · 94.1%', '+$92,184 · 94.6%', '+$55,485 · 93.9%', '<b>+$254,763</b>', '1,784', '<b>93.89%</b>', '−$5,158'],
    ['MT5: the 93.8% save', 'random', '+$27,116', '+$70,301', '+$81,419', '+$55,807', '+$234,643', '1,779', '93.37%', '−$5,178'],
    ['13-00-01 WR 94.6 EA filters', 'none', '+$27,535', '+$53,951', '+$74,930', '+$59,326', '+$215,742', '1,489', '94.63%', '−$5,211'],
    ['13-00-02 WR 95.8 boxes', 'none', '+$16,875', '+$68,312', '+$58,904', '+$78,163', '+$222,254', '1,119', '95.80%', '−$5,129'],
    ['13-00-03 WR 96.1 boxes', 'none', '+$17,175', '+$67,056', '+$62,882', '+$86,189', '+$233,301', '1,106', '96.02%', '−$5,129'],
    ['<b>15-00-01 WR 96.6 robust</b>', 'none', '+$21,470 · 94.2%', '+$60,706 · 97.1%', '+$62,476 · 95.6%', '+$84,917 · 98.4%', '<b>+$229,568</b>', '923', '<b>96.53%</b>', '−$5,129'],
    ['<b>15-00-01 WR 96.6 robust</b>', 'random', '+$21,154', '+$51,852', '+$59,112', '+$84,423', '+$216,540', '914', '95.95%', '−$5,118'],
    ['<b>15-00-02 WR 96.4 robust from base</b>', 'none', '+$26,411 · 94.9%', '+$66,209 · 96.7%', '+$54,960 · 95.2%', '+$81,673 · 98.0%', '<b>+$229,253</b>', '923', '<b>96.32%</b>', '−$5,123'],
    ['<b>15-00-02 WR 96.4 robust from base</b>', 'random', '+$25,793', '+$64,043', '+$50,498', '+$79,897', '+$220,231', '914', '95.84%', '−$5,118'],
    ['Gate: VPIN 0.081 / 0.05', 'none', '+$27,150', '+$79,944', '+$89,980', '+$48,279', '+$245,353', '1,761', '93.81%', '−$5,158'],
    ['Gate: VPIN 0.081 / 0.05', 'random', '+$28,398', '+$72,931', '+$82,091', '+$51,033', '+$234,453', '1,748', '93.65%', '−$5,328'],
    ['Gate: VPIN 0.074 / any flow against', 'none', '+$27,150', '+$71,476', '+$93,659', '+$41,230', '+$233,515', '1,680', '93.81%', '−$5,158'],
    ['Gate: HMM 4 states (leave-one-year-out models)', 'none', '+$7,665', '+$43,849', '+$68,465', '+$36,631', '+$156,610', '1,203', '93.60%', '−$5,129'],
    ['Gate: DTW 20% (leave-one-year-out paths)', 'none', '+$32,541', '+$66,186', '+$91,371', '+$49,629', '+$239,727', '1,750', '93.71%', '−$5,158'],
  ])}
  <p class="note"><b>Verdict:</b>
  (1) <b>The tester tells the truth on 15-minute charts</b>: MT5 +$254,763 / 93.89% vs tester +$264,191 / 93.8% over 3¾ years, every year within a few %. The "2026 is a losing year" story came from the 1-minute chart.
  (2) <b>The win-rate settings hold in MT5</b>: +0.7 to +2.6 points, profitable in every year, worst loss unchanged, profit −8% to −15%. The two robust saves: 96.5% / 96.3% (95.95% / 95.84% with random delay vs 93.37%).
  (3) The microstructure gates do not help on 15-minute charts: VPIN −$9k, DTW −$15k, HMM −$98k. The 1-minute VPIN "lead" does not carry over.
  <b>The but:</b> MT5 confirms execution, not the future - the boxes were chosen on these same years. The robust rule (both halves must improve) is the guard we have; live / forward trading is the real test.</p>
  </div>`;
}

document.addEventListener('change', async (e) => {
  if (e.target.id === 'dxlObj') { DXL.objective = e.target.value; dxlRender(); }
  if (e.target.id === 'dxlGuard') { DXL.guard = e.target.checked; dxlRender(); }
  if (e.target.id === 'dxlSave' && e.target.value !== '') {
    const s = SAVEDS[+e.target.value]; await applySave(s); await runSim(); DXL.key = ''; dxlEnsure();
  }
});
