// Turtle TV Tester - the Research tab (Zee 2026-11-01): "i zeeshan reads a research paper on the internet -> downloads it -> gives it to claude
// via this webpage to parse and build into an EA and test and validate and finally save the results in a list from which i can then pick it up
// by clicking Save setting which then brings it to our saved settings". Upload a PDF -> a headless Claude Fable 5.1 (low effort, no ultracode) builds a
// candidate from the base saved setting + the paper's idea, runs it in the Turtle TV tester (hypothesis) and in MT5 (the judge) -> the paper lands
// in the list below with its overview -> "Save this new setting" copies it into Saved settings with its paper's name as provenance.
// Server: /api/research, /api/research_upload, /api/research_build, /api/research_log, /api/research_stop, /api/research_save, /api/research_assist,
// /api/research_delete (server.py + papers/job.py). This file only renders what the job wrote (result.json contract) and presses the buttons.
'use strict';
const RES = { st: null, loading: false, polling: false, sel: '', base: '', notes: '', err: '', busy: '', logs: {}, logOpen: {}, saved: {}, uploading: false };
const rsN = (v, d = 0) => (v === null || v === undefined || v === '' || Number.isNaN(+v) ? '–' : (+v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }));
const rsWr = (v) => (v === null || v === undefined || v === '' || Number.isNaN(+v) ? '–' : `${(+v).toFixed(1)}%`);
const rsMoney = (v) => (v === null || v === undefined || v === '' || Number.isNaN(+v) ? '–' : `<span class="${cls(+v)}">${money(+v)}</span>`);
const rsTxt = (v) => (v === null || v === undefined || v === '' ? '–' : esc(typeof v === 'object' ? JSON.stringify(v) : v));
const rsLimit = (e) => /5-hour|five-hour|usage limit|hit your .*limit/i.test(String(e || ''));           // Claude's 5-hour usage limit - a retry later, not a bug
function rsElapsed(s) { s = Math.max(0, Math.round(+s || 0)); const m = Math.floor(s / 60), h = Math.floor(m / 60); return h ? `${h}h ${String(m % 60).padStart(2, '0')}m` : m ? `${m}m ${String(s % 60).padStart(2, '0')}s` : `${s}s`; }
function rsShort(t, n = 60) { t = String(t || ''); return t.length > n ? t.slice(0, n - 1) + '…' : t; }
function rsBadge(s) {                                               // the saved-settings row: "📄 <paper>" when a save came from a research paper
  const src = s && s.source;
  if (!src || src.kind !== 'research_paper') return '';
  const tip = `from the research paper "${src.paper || ''}"${src.id ? ` · ${src.id}` : ''}${src.built ? ` · built ${src.built}` : ''}${src.needs_code && src.needs_code.required ? ' · needs EA code (see the Research tab)' : ''}`;
  return ` <span class="rsbadge" style="font-size:10px;border-radius:8px;padding:1px 6px;background:rgba(255,152,0,.2);color:#ffb74d;white-space:nowrap" title="${esc(tip)}">📄 ${esc(rsShort(src.paper || 'research paper', 40))}</span>`;
}
function rsStatusTag(p) {
  const R = RES.st || {}, running = R.running && R.running.id === p.id, st = running ? 'running' : (p.status || (p.result ? p.result.status : '') || 'uploaded');
  const look = { uploaded: ['background:rgba(41,98,255,.3);color:#90caf9', 'UPLOADED'], running: ['background:rgba(255,152,0,.3);color:#ffd740', '⏳ RUNNING'],
    done: ['background:rgba(0,230,118,.22);color:#69f0ae', '✓ DONE'], failed: ['background:rgba(242,54,69,.3);color:#ff8a80', rsLimit(p.error) ? '⛔ 5-HOUR LIMIT' : '✗ FAILED'] }[st] || ['background:#333;color:#ccc', String(st).toUpperCase()];
  return `<span style="font:bold 10px 'Courier New',monospace;letter-spacing:.06em;border-radius:8px;padding:2px 8px;${look[0]}">${look[1]}</span>`;
}

// ---------- state ----------
async function resOpen() {                                          // first look (and after every button): the papers + the running job
  if (RES.loading) return; RES.loading = true;
  try { RES.st = await api('/api/research'); RES.err = ''; } catch (e) { RES.err = 'Turtle TV did not answer: ' + (e.message || e); RES.st = RES.st || { papers: [] }; }
  RES.loading = false;
  const S = RES.st || {};
  if (!RES.base || !(S.bases || []).includes(RES.base)) RES.base = S.default_base || (S.bases || [])[0] || '';
  const P = S.papers || [];
  if (!RES.sel || !P.some((p) => p.id === RES.sel)) { const cand = P.filter((p) => p.status !== 'done'); RES.sel = (cand[0] || P[0] || {}).id || ''; }
  resRender();
  if (S.running) resPoll();
}
function resRender() { if (TAB.tt === 'research') renderPanel('tt'); }
async function resPoll() {                                          // every 3 s while a job runs: the state + the tail of its log; the progress block only
  if (RES.polling) return; RES.polling = true;
  let miss = 0;
  try {
    for (;;) {
      await new Promise((r) => setTimeout(r, 3000));
      let st;
      try { st = await api('/api/research'); miss = 0; } catch (e) { if (++miss > 40) { RES.err = 'Turtle TV stopped answering while the job ran'; break; } continue; }
      const was = RES.st && RES.st.running ? RES.st.running.id : null;
      RES.st = st;
      if (st.running) { try { RES.logs[st.running.id] = await api('/api/research_log?id=' + encodeURIComponent(st.running.id)); } catch (e) { /* the log is optional */ } }
      const now = st.running ? st.running.id : null;
      const prog = TAB.tt === 'research' && typeof document !== 'undefined' && document.querySelector ? document.querySelector('#rsProg') : null;
      if (now && now === was && prog) prog.outerHTML = rsProgress(); else resRender();
      if (!now) break;
    }
  } finally { RES.polling = false; }
  if (RES.st && !RES.st.running) { const last = RES.st.papers && RES.st.papers.find((p) => p.status === 'done' || p.status === 'failed'); if (last) resLog(last.id, false); }
  resRender();
}
async function resLog(id, open = true) {
  try { RES.logs[id] = await api('/api/research_log?id=' + encodeURIComponent(id)); } catch (e) { RES.logs[id] = { lines: ['(no log: ' + (e.message || e) + ')'] }; }
  if (open) RES.logOpen[id] = !RES.logOpen[id];
  resRender();
}
async function resUpload(file) {                                     // the PDF as base64 -> the store; the new paper becomes the selected one
  if (!file) return;
  if (!/\.pdf$/i.test(file.name)) { toast('⚠ Only a PDF can be uploaded here.'); return; }
  RES.uploading = true; resRender();
  try {
    const b64 = await new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(',')[1] || ''); r.onerror = () => bad(new Error('could not read the file')); r.readAsDataURL(file); });
    const r = await api('/api/research_upload', { name: file.name, b64 });
    if (r.error) throw new Error(r.error);
    RES.sel = r.id;
    toast(`📄 <b>${esc(r.title || file.name)}</b> uploaded (${r.pages ?? '?'} pages). Now press <b>CREATE SAVED SETTING OUT OF THIS PAPER</b>.`);
  } catch (e) { toast('⚠ Upload failed: ' + esc(e.message || e), 14000); }
  RES.uploading = false;
  await resOpen();
}
async function resUrl() {                                            // a .pdf URL -> the server downloads it, keeps a copy in turtle/research/, stores it and starts the build
  const url = (RES.url || '').trim();
  if (!/^https?:\/\/.+\.pdf(\?|#|$)/i.test(url)) { toast('⚠ Give a URL that starts with http(s):// and ends with .pdf'); return; }
  RES.uploading = true; resRender();
  try {
    const r = await api('/api/research_url', { url, base: RES.base || undefined, notes: RES.notes || undefined, start: true });
    if (r.error) throw new Error(r.error);
    RES.sel = r.id; RES.url = '';
    const b = r.build || {};
    toast(`📄 <b>${esc(r.title || url)}</b> fetched (${r.pages ?? '?'} pages)${r.saved_copy ? ', copy kept in turtle/research' : ''}. ${b.ok ? '🧠 Claude is building the setting now (20-90 min).' : '⚠ Build not started: ' + esc(b.error || '')}`, 14000);
  } catch (e) { toast('⚠ Fetch failed: ' + esc(e.message || e), 14000); }
  RES.uploading = false;
  await resOpen();
}
async function resBuild(id) {
  if (!id) { toast('⚠ Upload a paper first (or pick one in the list).'); return; }
  RES.busy = 'build'; resRender();
  try {
    const r = await api('/api/research_build', { id, base: RES.base || undefined, notes: RES.notes || undefined });
    if (r.error) throw new Error(r.error);
    toast('🧠 Claude Fable 5.1 (low effort) is reading the paper and building the setting. 20-90 minutes; the progress shows below.', 12000);
  } catch (e) { toast('⚠ ' + esc(e.message || e), 14000); }
  RES.busy = '';
  await resOpen();
}
async function resStop(id) {
  if (typeof confirm === 'function' && !confirm('Stop the Claude job? Whatever it wrote so far stays in the store; the paper shows as failed.')) return;
  try { const r = await api('/api/research_stop', { id }); if (r.error) throw new Error(r.error); toast('■ The job was stopped.'); } catch (e) { toast('⚠ ' + esc(e.message || e)); }
  await resOpen();
}
async function resSave(id) {
  RES.busy = 'save:' + id; resRender();
  try {
    const r = await api('/api/research_save', { id });
    if (r.error) throw new Error(r.error);
    RES.saved[id] = r;
    if (typeof loadSaved === 'function') await loadSaved();
    toast(`💾 Saved as <b>${esc(r.name)}</b> - it is in Saved settings (bottom of the page) with its paper's badge.` + (r.needs_code && r.needs_code.required ? ' <b>It needs EA code</b> - ask Claude below.' : ''), 14000);
  } catch (e) { toast('⚠ Save failed: ' + esc(e.message || e), 14000); }
  RES.busy = '';
  resRender();
}
async function resAssist(id) {
  RES.busy = 'assist:' + id; resRender();
  try { const r = await api('/api/research_assist', { id }); if (r.error) throw new Error(r.error); toast('🤖 Claude is implementing the EA code the candidate needs (input defaulting OFF, version bump, no commit). Progress below.', 12000); }
  catch (e) { toast('⚠ ' + esc(e.message || e), 14000); }
  RES.busy = '';
  await resOpen();
}
async function resDelete(id, title) {
  if (typeof confirm === 'function' && !confirm(`Delete the paper "${title}" and everything the job wrote for it? A setting already saved to Saved settings stays.`)) return;
  try { const r = await api('/api/research_delete', { id }); if (r.error) throw new Error(r.error); } catch (e) { toast('⚠ ' + esc(e.message || e)); }
  delete RES.logs[id]; delete RES.logOpen[id]; delete RES.saved[id];
  await resOpen();
}

// ---------- pieces ----------
function rsProgress() {                                              // the running job: phase, elapsed, the tail of its log, Stop
  const S = RES.st || {}, J = S.running;
  if (!J) return '<div id="rsProg"></div>';
  const p = (S.papers || []).find((x) => x.id === J.id) || {}, L = (RES.logs[J.id] || {}).lines || [], tail = L.slice(-8);
  const mins = (+J.seconds || 0) / 60, w = Math.min(96, 4 + (mins / 60) * 90);
  return `<div id="rsProg" class="dexprog"><div class="dexprog-t">⏳ CLAUDE FABLE 5.1 IS WORKING ON "${esc(rsShort(p.title || J.id, 70))}" · ${esc(J.phase || 'starting')} · ${rsElapsed(J.seconds)}
      <button class="dexbtn sm" data-rs="stop" data-rid="${esc(J.id)}" style="float:right">■ Stop</button></div>
    <div class="dexprog-bar"><i style="width:${w}%"></i></div>
    <div class="dexprog-s">a run takes 20-90 minutes: read the paper → map its ideas to the EA → build the candidate in the Turtle TV tester → MT5 2023-2026 none/random on axi5,axi6 → result.json. The page refreshes every 3 s.</div>
    ${tail.length ? `<pre class="crt" style="margin:6px 0 0;max-height:170px;overflow:auto;white-space:pre-wrap">${tail.map((l) => esc(l)).join('\n')}</pre>` : '<div class="dexprog-s k">waiting for the first log line…</div>'}</div>`;
}
function rsMt5Map(M) {                                               // {year|total}{delay} -> row
  const m = {};
  for (const r of (M && M.rows) || []) { const y = String(r.year ?? ''), d = String(r.delay ?? 'none'); (m[y] = m[y] || {})[d] = r; }
  if (M && M.total_none) (m.total = m.total || {}).none = M.total_none;
  if (M && M.total_random) (m.total = m.total || {}).random = M.total_random;
  return m;
}
const rsCell3 = (r) => (r ? `${rsN(r.trades ?? r.n)} · ${rsWr(r.wr)} · ${rsMoney(r.net)}` : '–');
function rsTesterMt5(R) {                                            // tester (hypothesis) beside MT5 none/random, the base's MT5 beside it, per year + total
  const T = R.tester || {}, PY = T.per_year || {}, M = rsMt5Map(R.mt5), B = rsMt5Map(R.base_mt5);
  const years = [...new Set([...Object.keys(PY), ...Object.keys(M), ...Object.keys(B)].filter((y) => y !== 'total'))].sort();
  if (!years.length && !T.n && !M.total && !B.total) return '<p class="note">No tester or MT5 numbers yet.</p>';
  const row = (y, t, m, b, tot) => `<tr class="${tot ? 'tot' : ''}"><td class="l">${esc(y)}</td><td title="Turtle TV Tester = hypothesis">${t ? rsCell3(t) : '–'}</td><td>${rsCell3(m.none)}</td><td><b>${rsCell3(m.random)}</b></td><td class="k">${rsCell3(b.none)}</td><td class="k">${rsCell3(b.random)}</td></tr>`;
  const rows = years.map((y) => row(y, PY[y], M[y] || {}, B[y] || {}, false));
  rows.push(row('total', T.n != null ? { n: T.n, wr: T.wr, net: T.net } : null, M.total || {}, B.total || {}, true));
  const bn = (R.base_setting && R.base_setting.name) || 'base';
  return table(['', 'Turtle TV Tester (hypothesis)<br><span class="k">trades · WR · net</span>', 'MT5 no delay<br><span class="k">trades · WR · net</span>', 'MT5 random delay ★<br><span class="k">the judge</span>', `base ${esc(rsShort(bn, 24))}<br><span class="k">MT5 no delay</span>`, `base ${esc(rsShort(bn, 24))}<br><span class="k">MT5 random</span>`], rows) +
    (T.pf != null || T.worst_loss != null || T.dd != null ? `<div class="note">tester: PF ${rsN(T.pf, 2)} · worst loss ${rsMoney(T.worst_loss)} · drawdown ${T.dd != null ? rsMoney(-Math.abs(+T.dd)) : '–'} - all of it a hypothesis; the MT5 random-delay column decides.</div>` : '');
}
function rsIdeas(ideas) {
  if (!Array.isArray(ideas) || !ideas.length) return '<p class="note">No ideas extracted.</p>';
  const imp = (v) => (v === true || v === 'true' ? '<span class="good">✓ inputs exist</span>' : v === 'needs_code' ? '<span style="color:#ffd740">🛠 new EA code</span>' : v === false || v === 'false' ? '<span class="bad">✗ not in this EA</span>' : rsTxt(v));
  return table(['#', 'Idea from the paper', 'Where', 'Implementable', 'Mapping to the EA'],
    ideas.map((x, i) => `<tr><td>${i + 1}</td><td class="l" style="white-space:normal;max-width:360px">${rsTxt(x.idea)}</td><td>${rsTxt(x.where)}</td><td>${imp(x.implementable)}</td><td class="l k" style="white-space:normal;max-width:380px">${rsTxt(x.mapping)}</td></tr>`));
}
function rsSetting(R) {
  const s = R.setting || {}, ch = s.changed || {}, nc = R.needs_code || {};
  const diff = Object.entries(ch).map(([k, v]) => `${esc(k.replace(/^Inp/, ''))}=${esc(v)}`).join(' ');
  return `<div style="margin-top:8px"><b>Candidate setting:</b> ${rsTxt(s.name)} <span class="k">· ${esc(s.ds || 'm15')} · ${esc(s.mode || 'ea')}</span>
      ${s.note ? `<div class="note">${esc(s.note)}</div>` : ''}
      <div class="k" style="font-size:12px;white-space:normal"><b>Changes vs the EA defaults:</b> ${diff || 'none'}</div>
      ${nc.required ? `<div class="warn">🛠 This candidate needs EA code that does not exist yet${nc.version ? ` (EA ${esc(nc.version)})` : ''}: ${rsTxt(nc.summary)}${(nc.inputs || []).length ? ` · new inputs: ${esc((nc.inputs || []).join(', '))}` : ''}${(nc.files || []).length ? ` · files: ${esc((nc.files || []).join(', '))}` : ''}. Save it, then ask Claude to implement the code (defaults OFF, version bump, no commit).</div>` : '<div class="note">No new EA code needed - the candidate uses inputs the EA already has.</div>'}</div>`;
}
function rsPaper(p) {                                                // one paper: header, summary, ideas, tester vs MT5, verdict, buttons
  const S = RES.st || {}, R = p.result || null, running = S.running && S.running.id === p.id, anyRunning = !!S.running, done = (p.status === 'done' || (R && R.status === 'done')) && !!R;
  const canSave = done && p.has_setting !== false && !running, saved = RES.saved[p.id], nc = (R && R.needs_code) || (saved && saved.needs_code) || {};
  const limit = p.status === 'failed' && rsLimit(p.error), logOpen = RES.logOpen[p.id], L = (RES.logs[p.id] || {}).lines || [];
  const base = (R && R.base_setting && R.base_setting.name) || p.base_setting || '';
  let h = `<div class="dexpanel" id="rsp_${esc(p.id)}" style="${RES.sel === p.id ? 'box-shadow:0 0 0 3px #ffd740 inset' : ''}">
    <div class="bar" style="margin:0 0 4px"><label class="lopt" title="the paper the CREATE button acts on"><input type="radio" name="rsSel" data-rs="sel" data-rid="${esc(p.id)}" ${RES.sel === p.id ? 'checked' : ''}></label>
      <b style="font-size:14px">${rsTxt(p.title || p.file)}</b> ${rsStatusTag(p)}
      <span class="k">${esc(p.uploaded || '')} · ${rsN(p.pages)} pages · ${esc(p.file || '')}${base ? ` · base: <b>${esc(base)}</b>` : ''}${R && R.year ? ` · ${esc(R.year)}` : ''}${R && R.authors ? ` · ${esc(Array.isArray(R.authors) ? R.authors.join(', ') : R.authors)}` : ''}${R && R.dry ? ' · <span style="color:#ffd740">DRY RUN (fake result)</span>' : ''}</span></div>`;
  if (p.status === 'failed') h += `<div class="warn">${limit ? '⛔ <b>Claude hit its 5-hour usage limit</b> - nothing wrong with the paper. Wait for the window to reset, then press Retry.' : `✗ The job failed${p.exit_code != null ? ` (exit ${esc(p.exit_code)})` : ''}: ${rsTxt(p.error)}`}</div>`;
  if (R) {
    h += `<div style="margin-top:6px;white-space:normal;max-width:980px">${rsTxt(R.summary)}</div>`;
    h += `<details class="dexsec" ${done ? 'open' : ''}><summary>IDEAS FROM THE PAPER → THE EA <span class="k">${Array.isArray(R.ideas) ? R.ideas.length : 0}</span></summary>${rsIdeas(R.ideas)}</details>`;
    h += `<details class="dexsec" open><summary>TURTLE TV TESTER (HYPOTHESIS) vs MT5 (THE JUDGE) <span class="k">per year · none / random delay · the base beside it</span></summary>${rsTesterMt5(R)}${rsSetting(R)}</details>`;
    h += `<div class="crt" style="margin-top:8px"><div class="crth">▶ VERDICT · MT5 RANDOM DELAY IS THE JUDGE</div>${rsTxt(R.verdict)}${R.built ? `<div class="k" style="color:#81c784;margin-top:4px">built ${esc(R.built)}</div>` : ''}</div>`;
  } else if (!running && p.status !== 'failed') h += '<p class="note">Not built yet - select it and press CREATE SAVED SETTING OUT OF THIS PAPER.</p>';
  h += `<div class="bar" style="margin:8px 0 0">
      <button class="dexbtn" data-rs="save" data-rid="${esc(p.id)}" ${canSave && RES.busy !== 'save:' + p.id ? '' : 'disabled'} title="${canSave ? 'copies the candidate into Saved settings with the paper as its source' : 'available when the job is done and wrote a setting'}">💾 SAVE THIS NEW SETTING TO SETTINGS</button>
      ${saved ? `<span class="good">saved as <b>${esc(saved.name)}</b></span>` : ''}
      ${p.status === 'failed' || (done && !running) ? `<button class="dexbtn sm" data-rs="build" data-rid="${esc(p.id)}" ${anyRunning || RES.busy === 'build' ? 'disabled' : ''}>${p.status === 'failed' ? '↻ Retry' : '↻ Build again'}</button>` : ''}
      ${!R && !running && p.status !== 'failed' ? `<button class="dexbtn sm" data-rs="build" data-rid="${esc(p.id)}" ${anyRunning || RES.busy === 'build' ? 'disabled' : ''}>🧠 Build</button>` : ''}
      ${running ? `<button class="dexbtn sm" data-rs="stop" data-rid="${esc(p.id)}">■ Stop</button>` : ''}
      <button class="dexbtn sm" data-rs="log" data-rid="${esc(p.id)}">📜 log</button>
      <button class="dexbtn sm" data-rs="del" data-rid="${esc(p.id)}" data-title="${esc(p.title || p.file || p.id)}" ${running ? 'disabled' : ''}>🗑 delete</button></div>`;
  if (saved && nc.required) h += `<div class="warn" style="margin-top:6px">🛠 The saved setting needs EA code that is not in the EA yet (${rsTxt(nc.summary)}). The saved file carries the plan; the EA does not run it until the code exists.
      <button class="dexbtn sm" data-rs="assist" data-rid="${esc(p.id)}" ${anyRunning || RES.busy === 'assist:' + p.id ? 'disabled' : ''}>🤖 ASK CLAUDE TO IMPLEMENT THE EA CODE</button></div>`;
  if (logOpen) h += `<pre class="crt" style="margin:6px 0 0;max-height:320px;overflow:auto;white-space:pre-wrap">${L.length ? L.map((l) => esc(l)).join('\n') : '(empty log)'}</pre>`;
  return h + '</div>';
}

// ---------- the page ----------
function pResearch() {
  if (!RES.st && !RES.loading) resOpen();
  const S = RES.st || {}, P = S.papers || [], C = S.claude || {}, J = S.running, sel = P.find((p) => p.id === RES.sel);
  let h = `<div class="lab dex"><h3 class="dexh">📄 RESEARCH · FROM PAPER TO EA SETTING</h3>
    <p class="note">Upload a research paper (PDF). <b>Claude Fable 5.1</b> (low effort, no sub-agents - Zee: credits) reads it, maps its ideas onto the Saad 15-min EA, builds a candidate from the <b>base saved setting</b> plus the paper's idea,
    runs it in the Turtle TV tester (a hypothesis) and then in <b>MT5</b> on M15 2023-2026 with and without random delay (the judge), and writes the result into the list below. <b>Save this new setting</b> copies the candidate into Saved settings,
    marked with the paper it came from. If the idea needs code the EA does not have, the saved file says so and Claude can be asked to implement it (input defaulting OFF, version bump, nothing committed).</p>`;
  if (RES.err) h += `<p class="warn">⚠ ${esc(RES.err)}</p>`;
  if (S.claude && !C.found) h += `<p class="warn">⚠ claude.exe was not found (${esc(C.exe || 'no path')}) - uploads work, but a build cannot start on this machine.</p>`;
  h += `<div class="dexpanel"><div class="bar">
      <label class="lopt">1 · the paper <input type="file" id="rsFile" accept=".pdf,application/pdf" ${RES.uploading ? 'disabled' : ''}>${RES.uploading ? ' <span class="k">uploading…</span>' : ''}</label>
      <label class="lopt">or a PDF URL <input type="text" id="rsUrl" placeholder="https://…/paper.pdf" style="min-width:300px" value="${esc(RES.url || '')}" ${RES.uploading ? 'disabled' : ''}>
        <button class="dexbtn sm" id="rsFetch" ${RES.uploading || J || (S.claude && !C.found) ? 'disabled' : ''} title="downloads the PDF, keeps a copy in turtle/research/, and starts the build at once">⬇ FETCH &amp; BUILD</button></label>
      <label class="lopt">base setting <select id="rsBase" title="the saved setting the candidate starts from">${(S.bases || []).map((b) => `<option value="${esc(b)}" ${b === RES.base ? 'selected' : ''}>${esc(b)}${b === S.default_base ? ' (default)' : ''}</option>`).join('') || '<option value="">(no saved settings)</option>'}</select></label>
    </div>
    <label class="lopt" style="align-items:flex-start;width:100%">notes for Claude <textarea id="rsNotes" rows="2" style="flex:1;min-width:360px;max-width:900px" placeholder="optional: what you want tried from this paper, e.g. 'only the exit idea, keep my stop and TP'">${esc(RES.notes)}</textarea></label>
    <div class="bar" style="margin-top:8px">
      <button class="dexbtn" id="rsCreate" data-rs="build" data-rid="${esc(RES.sel)}" ${!sel || J || RES.busy === 'build' || (S.claude && !C.found) ? 'disabled' : ''} title="${sel ? 'builds from: ' + esc(sel.title || sel.file || '') : 'upload or select a paper first'}">🧠 CREATE SAVED SETTING OUT OF THIS PAPER</button>
      <span class="k">${sel ? `acts on <b>${esc(rsShort(sel.title || sel.file || sel.id, 60))}</b>${sel.status === 'done' ? ' (already built - this rebuilds it)' : ''}` : P.length ? 'select a paper in the list below (the radio button)' : 'upload a paper first'} · one job at a time · 20-90 min</span>
    </div></div>`;
  h += rsProgress();
  h += `<h4 style="margin:14px 0 4px">RESEARCH PAPERS IN THE SYSTEM <span class="k">${P.length}</span></h4>`;
  h += P.length ? P.map(rsPaper).join('') : '<p class="note">No papers yet. Upload a PDF above.</p>';
  h += `<p class="note" style="margin-top:10px">Every Python / Turtle TV Tester number on this page is a <b>hypothesis</b> (it overstates win rates by ~16 points). The MT5 random-delay column is the verdict. A failed run that says "5-hour limit" is Claude's usage window, not the paper: retry later.</p></div>`;
  return h;
}

// ---------- wiring ----------
document.addEventListener('change', (e) => {
  const t = e.target;
  if (!t || TAB.tt !== 'research') return;
  if (t.id === 'rsFile' && t.files && t.files[0]) resUpload(t.files[0]);
  if (t.id === 'rsBase') RES.base = t.value;
  if (t.id === 'rsUrl') RES.url = t.value;
  if (t.dataset && t.dataset.rs === 'sel') { RES.sel = t.dataset.rid; resRender(); }
});
document.addEventListener('input', (e) => { if (e.target && e.target.id === 'rsNotes') RES.notes = e.target.value; if (e.target && e.target.id === 'rsUrl') RES.url = e.target.value; });
document.addEventListener('keydown', (e) => { if (e.target && e.target.id === 'rsUrl' && e.key === 'Enter') { e.preventDefault(); resUrl(); } });
document.addEventListener('click', async (e) => {
  if (e.target && e.target.id === 'rsFetch') { resUrl(); return; }
  const b = e.target.closest ? e.target.closest('[data-rs]') : null;
  if (!b || b.disabled || b.dataset.rs === 'sel') return;
  const id = b.dataset.rid, k = b.dataset.rs;
  if (k === 'build') resBuild(id);
  else if (k === 'stop') resStop(id);
  else if (k === 'save') resSave(id);
  else if (k === 'assist') resAssist(id);
  else if (k === 'log') resLog(id, true);
  else if (k === 'del') resDelete(id, b.dataset.title || id);
});
