// Deploy tab + the "Deploy EA to Server" button in Saved settings (Zee 2026-11-02: "create a deploy page where one can input the settings for
// server / folder path etc to deploy to.. and then in settings add a button next to Download MT5 -> Deploy EA to Server which when clicked
// compiles the current strategy in list of saved settings into an EA file and deploys and prints below the button Done! Deployed to... and
// shows a large deployment notification with progress"). Server: deploy.py via /api/deploy_target (GET/POST), /api/deploy_test, /api/deploy (POST {name} / GET state).
const DEP = { cfg: null, st: null, test: null, polling: false, form: {}, lastFor: {}, hist: null, fetching: false };
async function depFetchHistory() {                                 // scp the deployed EA's trade + skip CSVs from the server, summarise per skip reason
  DEP.fetching = true; renderPanel('tt');
  try { DEP.hist = await api('/api/deploy_history', {}); if (DEP.hist.error) toast('⚠ ' + esc(DEP.hist.error), 12000); } catch (e) { toast('⚠ ' + esc(e.message || e)); }
  DEP.fetching = false; renderPanel('tt');
}
function depHistoryBlock() {
  const H = DEP.hist || {}, S = H.summary;
  let h = `<h4>History of this deployment on the server <button class="dexbtn sm" id="depFetch" ${DEP.fetching ? 'disabled' : ''}>${DEP.fetching ? '⏳ fetching…' : '⬇ Fetch History'}</button></h4>`;
  if (!S) return h + '<p class="note">Not fetched yet. The deployed EA writes two CSVs into the server\'s Common\\Files: its closed trades (Saad15_trades_*.csv) and, since v1.40, every skipped entry followed as a virtual trade with the same entry, stop and TP until it resolves (Saad15_skips_*.csv). Fetch History pulls both and says, per skip reason, whether skipping cost or saved money.</p>';
  h += `<p class="note">fetched ${esc(S.fetched)} from ${esc(S.remote)} (${(S.files || []).length} files, ${S.secs}s) · <b>${S.closed}</b> closed trades · ${S.wins} wins${S.closed ? ` (${(100 * S.wins / S.closed).toFixed(1)}%)` : ''} · net <b class="${cls(S.net)}">${money(S.net)}</b> · <b>${S.skips}</b> skipped setups, ${S.skips_resolved} resolved, ${S.skips_pending} still running · skipped trades would have made <b class="${cls(S.skips_pnl)}">${money(S.skips_pnl)}</b></p>`;
  if (!S.files || !S.files.length) h += '<p class="warn">No Saad15_*.csv on the server yet - the EA writes them once it has traded / skipped something (InpLogCsv and InpSkipLog must be on in the deployed EA; deployments from this page turn them on).</p>';
  if (H.by_reason && H.by_reason.length) h += '<p class="note" style="margin-bottom:2px"><b>Were we skipping genuinely profitable setups?</b> (virtual outcome at the EA\'s lots; positive = skipping cost money)</p>' +
    table(['skip reason', 'skips', 'resolved', 'would hit TP', 'would hit stop', 'timeout', 'never triggered', 'pending', 'skipped trades would have made', 'verdict'],
      H.by_reason.map((b) => `<tr><td class="l">${esc(b.reason)}</td><td>${b.skips}</td><td>${b.resolved}</td><td class="pos">${b.tp || ''}</td><td class="neg">${b.stop || ''}</td><td>${b.timeout || ''}</td><td>${b.never_triggered || ''}</td><td>${b.pending || ''}</td><td class="${cls(b.pnl)}">${b.resolved ? money(b.pnl) : ''}</td><td class="l">${esc(b.verdict)}</td></tr>`));
  if (H.trades && H.trades.length) h += '<p class="note" style="margin-bottom:2px"><b>Trades taken</b> (last 300)</p><div class="scroll" style="max-height:320px">' +
    table(['entry time', 'side', 'entry', 'exit time', 'exit', 'reason', 'net', 'setup'], H.trades.slice().reverse().map((t) => `<tr><td>${esc(t.entry_time)}</td><td>${esc(t.side)}</td><td>${esc(t.entry)}</td><td>${esc(t.exit_time)}</td><td>${esc(t.exit)}</td><td class="l">${esc(t.exit_reason)}</td><td class="${cls(t.net_f || 0)}">${t.net_f != null ? money(t.net_f) : ''}</td><td class="l">${esc(t.setup || '')}</td></tr>`)) + '</div>';
  if (H.skips && H.skips.length) h += '<p class="note" style="margin-bottom:2px"><b>Skipped setups</b> (last 500, virtual outcome)</p><div class="scroll" style="max-height:320px">' +
    table(['skip time', 'side', 'reason', 'entry', 'sl', 'tp', 'outcome', 'exit time', 'would have made', 'best', 'worst', 'min'], H.skips.slice().reverse().map((r) => `<tr><td>${esc(r.skip_time)}</td><td>${esc(r.side)}</td><td class="l">${esc(r.reason)}</td><td>${esc(r.entry)}</td><td>${esc(r.sl)}</td><td>${esc(r.tp)}</td><td class="l">${esc(r.outcome)}</td><td>${esc(r.exit_time)}</td><td class="${cls(r.pnl_f || 0)}">${r.pnl_f != null ? money(r.pnl_f) : ''}</td><td>${esc(r.best_usd || '')}</td><td>${esc(r.worst_usd || '')}</td><td>${esc(r.hold_min || '')}</td></tr>`)) + '</div>';
  return h;
}
async function depOpen() {
  try { DEP.cfg = await api('/api/deploy_target'); DEP.form = { ...DEP.cfg, password: '' }; } catch (e) { DEP.cfg = { error: String(e) }; }
  try { DEP.st = await api('/api/deploy'); } catch (e) { /* ignore */ }
  if (TAB.tt === 'deploy') renderPanel('tt');
  if (DEP.st && DEP.st.running) depPoll();
}
async function depSave() {
  const body = { ...DEP.form }; if (!body.password) delete body.password;
  try { DEP.cfg = await api('/api/deploy_target', body); DEP.form = { ...DEP.cfg, password: '' }; toast('💾 Deploy target saved.'); } catch (e) { toast('⚠ ' + esc(e.message || e)); }
  renderPanel('tt');
}
async function depTest() {
  DEP.test = { running: true }; renderPanel('tt');
  try { DEP.test = await api('/api/deploy_test', { ...DEP.form, password: DEP.form.password || undefined }); } catch (e) { DEP.test = { ok: false, error: String(e) }; }
  renderPanel('tt');
}
async function depDeploy(name) {
  try { const r = await api('/api/deploy', { name }); if (r.error) { toast('⚠ ' + esc(r.error), 12000); return; } DEP.lastFor[name] = { running: true }; }
  catch (e) { toast('⚠ ' + esc(e.message || e)); return; }
  depBox(); depPoll();
}
async function depPoll() {
  if (DEP.polling) return; DEP.polling = true;
  try {
    for (;;) {
      try { DEP.st = await api('/api/deploy'); } catch (e) { break; }
      depBox();
      if (DEP.st.setting) DEP.lastFor[DEP.st.setting] = DEP.st;
      if (typeof renderSaved === 'function' && $('#panelSaved')) renderSaved();
      if (TAB.tt === 'deploy') renderPanel('tt');
      if (!DEP.st.running) break;
      await new Promise((r) => setTimeout(r, 1500));
    }
  } finally { DEP.polling = false; }
}
function depBox() {                                              // the large deployment notification with progress (same overlay family as #saveBox)
  const S = DEP.st || {};
  let el = $('#deployBox');
  if (!S.running && !S.done && !S.error) { if (el) el.remove(); return; }
  if (!el) { el = document.createElement('div'); el.id = 'deployBox'; el.style.cssText = 'position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.6);z-index:95'; document.body.appendChild(el); }
  const step = Math.max(0, +((S.phase || '').match(/^(\d)\/5/) || [0, 0])[1]), pct = S.done ? 100 : S.error ? 100 : Math.min(95, 8 + step * 18);
  el.innerHTML = `<div class="dex" style="width:min(760px,92vw);background:#131722;border:2px solid ${S.error ? '#ef5350' : S.done ? '#26a69a' : '#2962ff'};border-radius:14px;padding:22px 26px;box-shadow:0 10px 40px rgba(0,0,0,.6)">
    <div class="dexprog-t" style="font-size:20px;margin-bottom:8px">${S.error ? '❌ DEPLOYMENT FAILED' : S.done ? '✅ DONE! DEPLOYED' : '🚀 DEPLOYING EA TO SERVER'}</div>
    <div class="k" style="font-size:13px;margin-bottom:8px">${esc(S.setting || '')} → <b>${esc(S.ea || '')}</b> → ${esc(S.target || '')}</div>
    <div class="dexprog-bar" style="height:14px"><i style="width:${pct}%;background:${S.error ? '#ef5350' : S.done ? '#26a69a' : ''}"></i></div>
    <div style="font-size:15px;margin:10px 0 6px">${esc(S.phase || '')} <span class="k">· ${S.secs || 0} s</span></div>
    <pre style="max-height:220px;overflow:auto;font-size:12px;color:#cfd8dc;background:#0d1117;border-radius:8px;padding:8px;margin:0">${esc((S.log || []).join('\n'))}</pre>
    ${S.running ? '' : `<div class="bar" style="margin-top:12px"><button class="dexbtn" id="deployClose">Close</button>${S.done ? `<span class="good" style="font-size:14px">Done! Deployed to ${esc(S.target || '')}</span>` : ''}</div>`}</div>`;
}
document.addEventListener('click', (e) => {
  const t = e.target; if (!t) return;
  if (t.id === 'deployClose') { const el = $('#deployBox'); if (el) el.remove(); DEP.st = { ...DEP.st, done: false, error: null, closed: true }; return; }
  if (t.id === 'depSave') depSave();
  if (t.id === 'depTest') depTest();
  if (t.id === 'depFetch') depFetchHistory();
  const n = t.dataset && t.dataset.deployEa;
  if (n !== undefined) { if (confirm(`Compile "${n}" into an EA and deploy it to the server set on the Deploy page?`)) depDeploy(n); }
});
document.addEventListener('input', (e) => { const t = e.target; if (t && t.dataset && t.dataset.dep) DEP.form[t.dataset.dep] = t.type === 'checkbox' ? t.checked : t.value; });
function depStatusLine(name) {                                   // under the Saved-settings button: "Done! Deployed to ..."
  const s = DEP.lastFor[name]; if (!s) return '';
  if (s.running) return `<div class="k">⏳ ${esc(s.phase || 'deploying…')}</div>`;
  if (s.error) return `<div class="neg" style="white-space:normal">❌ ${esc(s.error)}</div>`;
  if (s.done) return `<div class="good" style="white-space:normal">Done! Deployed to ${esc(s.target || '')} as ${esc(s.ea || '')}</div>`;
  return '';
}
function pDeploy() {
  if (!DEP.cfg) { depOpen(); return '<p class="note">Loading…</p>'; }
  const c = DEP.cfg || {}, f = DEP.form || {}, S = DEP.st || {}, T = DEP.test;
  const inp = (k, label, type = 'text', w = 420, hint = '') => `<label class="lopt" style="width:100%;align-items:center"><span style="min-width:170px">${label}</span><input type="${type}" data-dep="${k}" value="${esc(f[k] ?? '')}" style="flex:1;max-width:${w}px" placeholder="${esc(hint)}"></label>`;
  let h = `<div class="lab dex"><h3 class="dexh">🚀 DEPLOY · SAVED SETTING → COMPILED EA → YOUR MT5 SERVER</h3>
    <p class="note">The <b>Deploy EA to Server</b> button in Saved settings bakes a setting's inputs into the EA's defaults (make_ea_from_settings.py), compiles it in MetaEditor (rig), and copies the .ex5 (+ source and includes) over SSH into the folder below. Then in that MT5: refresh the Navigator (or restart the terminal) and drag the EA onto the XAUUSD <b>M15</b> chart. The EA's <b>InpLots</b> default is the saved setting's (2 lots in most saves) - check it in the attach dialog.</p>
    <div class="dexpanel"><h4 style="margin-top:0">Target</h4>
    ${inp('name', 'Name', 'text', 420, 'AWS VM · PXBT MT5')}${inp('host', 'Host / IP', 'text', 300, '51.20.122.18')}${inp('user', 'SSH user', 'text', 300, 'Administrator')}
    ${inp('password', c.has_password ? 'SSH password (saved · leave blank to keep)' : 'SSH password', 'password', 300)}
    ${inp('remote_dir', 'MQL5\\Experts folder on the server', 'text', 760, 'C:\\Users\\<user>\\AppData\\Roaming\\MetaQuotes\\Terminal\\<id>\\MQL5\\Experts')}
    ${inp('rig', 'Compile rig (this laptop)', 'text', 160, 'axi4')}${inp('ea_prefix', 'EA name prefix', 'text', 200, 'Saad_')}
    <label class="lopt"><input type="checkbox" data-dep="include_source" ${f.include_source !== false ? 'checked' : ''}> also copy the .mq5 source and its .mqh includes</label>
    <label class="lopt"><input type="checkbox" data-dep="log_skips" ${f.log_skips !== false ? 'checked' : ''}> deployed EA logs its trades and its skipped setups as virtual trades (InpLogCsv + InpSkipLog on) - needed for Fetch History</label>
    ${inp('remote_common', 'Common\\Files folder on the server (the CSV logs)', 'text', 760, 'C:\\Users\\<user>\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files')}
    <div class="bar" style="margin-top:8px"><button class="dexbtn" id="depSave">💾 Save target</button><button class="dexbtn sm" id="depTest" ${T && T.running ? 'disabled' : ''}>🔌 Test connection</button>
    ${T ? (T.running ? '<span class="k">testing…</span>' : T.ok ? `<span class="good">✓ login ok · folder ${T.dir_ok ? 'exists' : '<b class="neg">MISSING</b>'} · MT5 terminal ${T.terminal_running ? 'running' : 'not running'} · ${T.secs}s</span>` : `<span class="neg">✗ ${esc(T.error || 'failed')}</span>`) : ''}</div>
    <p class="note">The password is stored only in monitor/saad_view/settings/deploy_target.json (git-ignored) on this laptop. The folder id is the terminal's data folder: in MT5 File → Open Data Folder → MQL5\\Experts.</p></div>`;
  h += `<h4>Last deployment</h4>${S.setting ? `<p class="note">${esc(S.setting)} → <b>${esc(S.ea || '')}</b> → ${esc(S.target || '')} · ${S.running ? '⏳ ' + esc(S.phase) : S.error ? '<span class="neg">❌ ' + esc(S.error) + '</span>' : S.done || (S.log || []).some((l) => l.includes('5/5')) ? '<span class="good">✅ done</span>' : ''} · ${S.secs || 0} s</p><pre class="note" style="white-space:pre-wrap">${esc((S.log || []).join('\n'))}</pre>` : '<p class="note">none yet this session</p>'}`;
  if (!DEP.hist && !DEP.fetching) { DEP.hist = {}; api('/api/deploy_history').then((x) => { DEP.hist = x; if (TAB.tt === 'deploy') renderPanel('tt'); }).catch(() => {}); }
  h += depHistoryBlock();
  if (S.history && S.history.length) h += '<h4>Deployments (this server session)</h4>' + table(['when', 'setting', 'EA', 'target', 'files', 's'], S.history.map((x) => `<tr><td>${esc(x.when)}</td><td class="l">${esc(x.setting)}</td><td>${esc(x.ea)}</td><td class="l">${esc(x.target)}</td><td class="l">${esc((x.files || []).join(', '))}</td><td>${x.secs}</td></tr>`));
  return h + '</div>';
}
