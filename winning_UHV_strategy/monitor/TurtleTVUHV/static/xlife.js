// EXTENDED Trade Lifecycle (xlife.py): every exit the tester and the EA both run, as a tree of switches.
// A draft (exit mode + one choice per module) runs on top of the chart's settings; every node carries what switching it costs or adds;
// the optimiser builds the best exit set per mode. Everything is a real EA input: Apply & save, then Verify in MT5. MT5 decides.
const XLF = {
  on: false, key: '', spec: null, sel: null, last: {}, ev: null, evBusy: false, evSeq: 0, imp: null, impKey: '', impBusy: false, prog: null,
  opt: null, optBusy: false, objective: 'net', guard: true, modes: { 0: true, 1: true, 2: true }, fold: {}, err: '', poll: 0, impT: 0, mt5: null, mt5poll: 0,
};

function xlfKey() { return JSON.stringify([CUR, SRC.ds, SRC.mode]); }
function xlfSelKey() { return JSON.stringify([XLF.key, XLF.sel]); }
function xlfBody(extra) { return { inputs: CUR, ds: SRC.ds, mode: SRC.mode, ...extra }; }
function xlfOpen() { XLF.on = true; renderPanel('tt'); }
function xlfClose() { XLF.on = false; renderPanel('tt'); }
function xlfMode() { return { m0: 0, m1: 1, m2: 2 }[XLF.sel && XLF.sel.mode] ?? 1; }
function xlfMod(k) { return XLF.spec && XLF.spec.modules.find((m) => m.key === k); }
function xlfLabel(m, id) { if (id === 'off') return m.off_label || 'off'; const v = m.variants.find((x) => x.id === id); return v ? v.label : id; }
const xlfM = (v) => (v == null ? '–' : money(v));
const xlfSign = (v) => (v == null ? '' : `<span class="${v >= 0 ? 'lf-pos' : 'lf-neg'}">${v >= 0 ? '+' : ''}${money(v)}</span>`);

function xlfLoad() {
  const key = xlfKey();
  if (XLF.key !== key) {
    XLF.key = key; XLF.spec = null; XLF.sel = null; XLF.ev = null; XLF.imp = null; XLF.last = {}; XLF.err = '';
    api('/api/xlife_spec', xlfBody()).then((sp) => {
      if (XLF.key !== key) return;
      XLF.spec = sp; XLF.sel = { ...sp.sel }; xlfEval();
    }).catch((e) => { XLF.err = 'Could not load the exit catalog: ' + e.message; renderPanel('tt'); });
  }
}

function xlfEval() {
  const seq = ++XLF.evSeq; XLF.evBusy = true; renderPanel('tt');
  api('/api/xlife_eval', xlfBody({ sel: XLF.sel })).then((r) => {
    if (seq !== XLF.evSeq) return;
    XLF.ev = r; XLF.evBusy = false; renderPanel('tt');
    clearTimeout(XLF.impT); XLF.impT = setTimeout(xlfImpacts, 400);
  }).catch((e) => { if (seq === XLF.evSeq) { XLF.evBusy = false; XLF.err = 'The tester failed: ' + e.message; renderPanel('tt'); } });
}

async function xlfImpacts() {
  if (XLF.optBusy) return;
  const k = xlfSelKey();
  const r = await api('/api/xlife_impacts', xlfBody({ sel: XLF.sel, objective: XLF.objective, guard: XLF.guard }));
  if (!r.ok) { XLF.err = r.error || 'the impact scan could not start'; renderPanel('tt'); return; }
  XLF.impBusy = true; XLF.impKey = k; xlfPollStart();
}

function xlfPollStart() { clearInterval(XLF.poll); XLF.poll = setInterval(xlfPoll, 900); }
async function xlfPoll() {
  let p;
  try { p = await api('/api/xlife_job', {}); } catch (e) { return; }
  XLF.prog = p;
  if (!p.running) {
    clearInterval(XLF.poll); XLF.poll = 0;
    if (p.kind === 'impacts') { XLF.impBusy = false; if (p.result) XLF.imp = { ...p.result, key: XLF.impKey }; }
    if (p.kind === 'optimise') { XLF.optBusy = false; if (p.result) XLF.opt = { ...p.result, key: XLF.key }; xlfImpacts(); }
    if (p.error) XLF.err = p.error;
  }
  renderPanel('tt');
}

function xlfSet(k, id) {
  const m = xlfMod(k); if (!m) return;
  if (XLF.sel[k] !== 'off') XLF.last[k] = XLF.sel[k];
  XLF.sel = { ...XLF.sel, [k]: id }; XLF.imp = XLF.imp && { ...XLF.imp, key: '' };
  xlfEval();
}
function xlfToggle(k) {
  const m = xlfMod(k); if (!m || !m.off) return;
  if (XLF.sel[k] !== 'off') return xlfSet(k, 'off');
  const best = XLF.imp && XLF.imp.key === xlfSelKey() && XLF.imp.modules[k] && XLF.imp.modules[k].best;
  xlfSet(k, XLF.last[k] || best || m.variants[0].id);
}
function xlfReset() { XLF.sel = { ...XLF.spec.sel }; XLF.last = {}; xlfEval(); }
function xlfFold(f) { XLF.fold[f] = !XLF.fold[f]; renderPanel('tt'); }

// ---- the optimiser
async function xlfOptimise() {
  const modes = Object.entries(XLF.modes).filter(([, on]) => on).map(([m]) => Number(m));
  if (!modes.length) { toast('Pick at least one exit mode to search.'); return; }
  const r = await api('/api/xlife_optimise', xlfBody({ objective: XLF.objective, guard: XLF.guard, modes, sel: XLF.spec && XLF.spec.sel }));
  if (!r.ok) { XLF.err = r.error || 'could not start'; renderPanel('tt'); return; }
  XLF.optBusy = true; XLF.impBusy = false; XLF.err = ''; xlfPollStart(); renderPanel('tt');
}
async function xlfStop() { await api('/api/xlife_stop', {}); }
function xlfLoadOpt(md) { const r = XLF.opt && XLF.opt.modes[md]; if (!r) return; XLF.sel = { ...r.sel }; xlfEval(); window.scrollTo({ top: 0, behavior: 'smooth' }); }

// ---- what changes against the chart, apply & save, MT5
function xlfChanged(over) {
  const out = {};
  for (const [k, v] of Object.entries(over || {})) {
    const a = String(CUR[k] ?? '').toLowerCase(), b = String(v).toLowerCase();
    if (a !== b && !(a !== '' && !isNaN(a) && !isNaN(b) && Math.abs(Number(a) - Number(b)) < 1e-9)) out[k] = String(v);
  }
  return out;
}
async function xlfApply(over, title) {
  const ch = xlfChanged(over);
  if (!Object.keys(ch).length) { toast('Nothing to apply: this is already the setting on the chart.'); return; }
  CUR = { ...CUR, ...ch }; settingsTouched = true; markForm();
  toast(`Applying ${Object.keys(ch).length} EA input(s) and saving…`, 4000);
  await runSim();
  try {
    const r = await api('/api/save', { inputs: CUR, ds: SRC.ds, mode: SRC.mode, result: null });
    await loadSaved();
    toast(`Saved as <b>${esc(r.name)}</b>: ${esc(title)} is now the setting on the chart. Tester hypothesis - press Verify in MT5.`, 9000);
  } catch (e) { toast('Applied to the chart, but the save failed: ' + esc(e.message)); }
  renderPanel('tt');
}
async function xlfMt5(over, key, title) {
  const ch = xlfChanged(over);
  const r = await api('/api/dexlab_mt5', xlfBody({ items: [{ key, title, sets: ch }] }));
  if (r.error) { XLF.err = r.error; renderPanel('tt'); return; }
  toast('MT5 Strategy Tester started (2026 data on the rig). The result shows here when it finishes.', 6000);
  clearInterval(XLF.mt5poll); XLF.mt5poll = setInterval(xlfMt5Status, 4000); xlfMt5Status();
}
async function xlfMt5Status() {
  try { XLF.mt5 = await api('/api/dexlab_mt5_status', xlfBody()); } catch (e) { return; }
  if (!XLF.mt5.busy && XLF.mt5poll) { clearInterval(XLF.mt5poll); XLF.mt5poll = 0; }
  renderPanel('tt');
}
function xlfMt5Of(key, over) {
  const rs = (XLF.mt5 && XLF.mt5.results || []).filter((r) => r.key === key);
  if (!rs.length) return null;
  const r = rs[rs.length - 1], ch = xlfChanged(over);
  r.current = JSON.stringify(Object.entries(r.sets || {}).sort()) === JSON.stringify(Object.entries(ch).sort());
  return r;
}
function xlfMt5HTML(key, over) {
  const busy = XLF.mt5 && XLF.mt5.busy && (XLF.mt5.queue || []).includes(key);
  if (busy) return `<div class="lf-sub">⏳ ${esc(XLF.mt5.phase || 'MT5 running…')}</div>`;
  const r = xlfMt5Of(key, over);
  if (!r) return '';
  if (r.status !== 'complete') return `<div class="lf-sub lf-neg">MT5 failed: ${esc(r.error || '')}</div>`;
  return `<div class="lf-sub" style="color:#ffd740">MT5 ${r.current ? '' : '(an earlier version) '}· net <b>${xlfM(r.net)}</b> · PF ${r.pf ?? '–'} · DD ${r.dd ?? '–'} · ${r.trades ?? '–'} trades · largest loss ${xlfM(r.largest_loss)}</div>`;
}

// ---- drawing
function xlfCss() {
  if (document.getElementById('xlfCss')) return;
  const s = document.createElement('style'); s.id = 'xlfCss';
  s.textContent = `
  .xlf-card{height:100%;box-sizing:border-box;border:1px solid #12506e;border-radius:9px;background:linear-gradient(180deg,#03182a,#020d18);display:grid;
    grid-template-columns:178px 250px 150px 1fr;align-items:center;gap:8px;padding:5px 10px;font:11px Consolas,monospace;color:#cfefff;position:relative}
  .xlf-card.on{border-color:#00e5ff;box-shadow:0 0 12px #00e5ff33,inset 0 0 18px #00e5ff10}
  .xlf-card.off{opacity:.62;border-style:dashed}
  .xlf-card.off:hover{opacity:1}
  .xlf-name{font-weight:bold;letter-spacing:1px;color:#e8fbff;display:flex;align-items:center;gap:7px}
  .xlf-q{display:inline-block;width:14px;height:14px;border-radius:50%;border:1px solid #5f9db8;color:#5f9db8;text-align:center;line-height:13px;font-size:9px;cursor:help}
  .xlf-sw{width:34px;height:18px;border-radius:9px;background:#2a0612;border:1px solid #ff5c7a;position:relative;cursor:pointer;flex:none}
  .xlf-sw:after{content:'';position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;background:#ff5c7a;transition:left .2s}
  .xlf-sw.on{background:#003a2a;border-color:#4dffb0}.xlf-sw.on:after{left:18px;background:#4dffb0;box-shadow:0 0 8px #4dffb0}
  .xlf-sel{width:100%;background:#020f1b;color:#b9f6ff;border:1px solid #1d5b7a;border-radius:6px;font:11px Consolas,monospace;padding:3px}
  .xlf-st{font-size:10px;color:#6fa5bd;line-height:1.3}
  .xlf-imp{font-size:10px;line-height:1.35}
  .xlf-mini{background:#031a29;border:1px solid #00e5ff;color:#7ff6ff;border-radius:5px;font:10px Consolas,monospace;padding:1px 6px;cursor:pointer;margin-left:4px}
  .xlf-mini:hover{background:#00e5ff22}
  .xlf-seg{display:flex;gap:4px}.xlf-seg button{flex:1;background:#020f1b;border:1px solid #1d5b7a;color:#9cc9dc;border-radius:6px;font:10px Consolas,monospace;padding:4px 2px;cursor:pointer}
  .xlf-seg button.on{border-color:#00e5ff;color:#fff;background:#00e5ff26;box-shadow:0 0 10px #00e5ff55}
  .xlf-path{font-size:11px;margin:2px 0}.xlf-path b{color:#e8fbff}
  .xlf-mode{border:1px solid #12506e;border-radius:10px;padding:10px;background:linear-gradient(160deg,#041a2b,#020b15);flex:1 1 300px}
  .xlf-mode.win{border-color:#ffd740;box-shadow:0 0 18px #ffd74033}
  .xlf-tbl{width:100%;border-collapse:collapse;font-size:10.5px}.xlf-tbl td,.xlf-tbl th{padding:2px 5px;border-bottom:1px solid #0b2c40;text-align:left}
  .xlf-tbl th{color:#5f9db8;font-weight:normal;letter-spacing:1px}`;
  document.head.appendChild(s);
}

function xlfImpHTML(m, sel) {
  const ok = XLF.imp && XLF.imp.key === xlfSelKey(), im = ok && XLF.imp.modules[m.key];
  if (!im) return `<span class="lf-sub">${XLF.impBusy || XLF.evBusy ? 'measuring…' : ''}</span>`;
  const cur = sel[m.key], on = m.off ? cur !== 'off' : true;
  const best = im.best && im.alts[im.best], bestUp = best && best.d > 0;
  let h = '';
  if (m.off && on && im.off) {
    const d = im.off.d;
    h += `<div>${d > 0 ? '✂ switching it off <b class="lf-pos">adds ' : 'switching it off costs <b class="lf-neg">'}${money(Math.abs(d))}</b>${im.off.ok ? '' : ' <span title="fails the guard: more risk than the live setting">⚠</span>'}</div>`;
  }
  if (bestUp) h += `<div>${on && m.off ? 'better preset' : m.off ? 'best preset' : 'better'}: ${esc(xlfLabel(m, im.best))} ${xlfSign(best.d)}<button class="xlf-mini" onclick="xlfSet('${m.key}','${im.best}')">use</button></div>`;
  else if (!m.off || !on) h += `<div class="lf-sub">${m.off ? 'no preset helps here' : 'the current choice is the best'}${XLF.guard ? ' (guard on)' : ''}</div>`;
  return h || '<span class="lf-sub">no better preset</span>';
}

function xlfCard(m, sel, total) {
  const cur = sel[m.key], on = m.off ? cur !== 'off' : true, by = XLF.ev && XLF.ev.by_module[m.key];
  const st = !on ? 'switched off' : by ? `closes <b style="color:#e8fbff">${by.n}</b> trades (${Math.round((100 * by.n) / Math.max(1, total))}%) · ${xlfSign(by.net)}` : 'on · closes no trade itself';
  let ctl;
  if (m.key === 'mode') {
    const im = XLF.imp && XLF.imp.key === xlfSelKey() && XLF.imp.modules.mode;
    ctl = `<div class="xlf-seg" style="grid-column:2 / span 2">${m.variants.map((v) => {
      const a = im && im.alts[v.id];
      return `<button class="${cur === v.id ? 'on' : ''}" onclick="xlfSet('mode','${v.id}')" title="${esc(v.label)}">${esc(v.label.split(' · ')[0])} ${a ? (a.d >= 0 ? '+' : '') + money(a.d) : cur === v.id ? '●' : ''}</button>`;
    }).join('')}</div>`;
  } else {
    ctl = `<select class="xlf-sel" onchange="xlfSet('${m.key}', this.value)">${m.off ? `<option value="off" ${cur === 'off' ? 'selected' : ''}>${esc(m.off_label || 'off')}</option>` : ''}${m.variants.map((v) => `<option value="${esc(v.id)}" ${cur === v.id ? 'selected' : ''}>${esc(v.label)}</option>`).join('')}</select>`;
  }
  return `<div xmlns="http://www.w3.org/1999/xhtml" class="xlf-card ${on ? 'on' : 'off'}">
    <div class="xlf-name">${m.off ? `<span class="xlf-sw ${on ? 'on' : ''}" onclick="xlfToggle('${m.key}')" title="switch on / off"></span>` : '<span style="width:34px;text-align:center;color:#00e5ff">◆</span>'}
      <span>${esc(m.name.toUpperCase())}</span><span class="xlf-q" title="${esc(m.def)}">?</span></div>
    ${ctl}${m.key === 'mode' ? '' : `<div class="xlf-st">${st}</div>`}
    <div class="xlf-imp">${m.key === 'mode' ? `<div class="xlf-st">${st}</div>` : ''}${xlfImpHTML(m, sel)}</div>
  </div>`;
}

function xlfTree() {
  const sp = XLF.spec, sel = XLF.sel, md = xlfMode(), total = XLF.ev && XLF.ev.stats ? XLF.ev.stats.n : 1;
  const W = 1240, CX = 70, HX = 280, KX = 420, KW = 810, KH = 54, GAP = 64, FG = 26;
  const fams = sp.families.map((f) => {
    const mods = sp.modules.filter((m) => m.family === f.key);
    const live = mods.filter((m) => m.modes.includes(md)), hidden = mods.length - live.length;
    return { ...f, live, hidden };
  }).filter((f) => f.live.length || f.hidden);
  let y = 40; const rows = [];
  for (const f of fams) {
    const folded = XLF.fold[f.key] || !f.live.length;
    const n = folded ? 1 : f.live.length;
    f.y0 = y; f.h = n * GAP; f.cy = y + f.h / 2 - GAP / 2 + KH / 2; f.folded = folded;
    if (!folded) f.live.forEach((m, i) => rows.push({ m, f, y: y + i * GAP }));
    y += f.h + FG;
  }
  const H = y + 10, cy = H / 2;
  const fn = (f) => f.live.reduce((a, m) => a + ((XLF.ev && XLF.ev.by_module[m.key]) ? XLF.ev.by_module[m.key].n : 0), 0);
  let s = `<svg class="lf-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMin meet">
    <defs><pattern id="xlfGrid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#0b2c40" stroke-width=".6"/></pattern>
    <filter id="xlfGlow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <radialGradient id="xlfHalo"><stop offset="0" stop-color="#00e5ff" stop-opacity=".35"/><stop offset="1" stop-color="#00e5ff" stop-opacity="0"/></radialGradient></defs>
    <rect width="${W}" height="${H}" fill="url(#xlfGrid)"/>`;
  for (const f of fams) {                                              // trunk -> family hub
    const n = fn(f), w = 1.5 + 10 * n / Math.max(1, total), live = n > 0;
    s += `<path d="M${CX + 40} ${cy} C${CX + 140} ${cy}, ${HX - 140} ${f.cy}, ${HX - 58} ${f.cy}" stroke="${live ? '#00e5ff' : '#2b4a5c'}" stroke-width="${w}" fill="none" opacity=".3"/>
      ${live ? `<path class="lf-flow" d="M${CX + 40} ${cy} C${CX + 140} ${cy}, ${HX - 140} ${f.cy}, ${HX - 58} ${f.cy}" stroke="#7ff6ff" stroke-width="${Math.max(1.2, w / 3)}" fill="none"/>` : ''}
      <g class="lf-node" onclick="xlfFold('${f.key}')" filter="url(#xlfGlow)"><polygon points="${HX - 58},${f.cy} ${HX - 44},${f.cy - 22} ${HX + 44},${f.cy - 22} ${HX + 58},${f.cy} ${HX + 44},${f.cy + 22} ${HX - 44},${f.cy + 22}" fill="#06121f" stroke="${live ? '#00e5ff' : '#2b4a5c'}"/>
      <text x="${HX}" y="${f.cy - 3}" fill="${live ? '#7ff6ff' : '#5f9db8'}" font-size="9.5" text-anchor="middle" letter-spacing="1">${esc(f.name.toUpperCase())}</text>
      <text x="${HX}" y="${f.cy + 11}" fill="#5f9db8" font-size="8.5" text-anchor="middle">${f.folded ? (f.live.length ? '▸ ' + f.live.length + ' folded' : 'not in mode ' + md) : (n ? n + ' trades' : '') + (f.hidden ? ` · ${f.hidden} hidden` : '')}</text></g>`;
  }
  for (const r of rows) {                                              // hub -> module card
    const m = r.m, by = XLF.ev && XLF.ev.by_module[m.key], on = m.off ? sel[m.key] !== 'off' : true, yy = r.y + KH / 2;
    const n = by ? by.n : 0, col = !on ? '#3a4f5c' : n ? (by.net >= 0 ? '#4dffb0' : '#ff5c7a') : '#00e5ff';
    const w = on ? 1.2 + 9 * n / Math.max(1, total) : 1;
    s += `<path d="M${HX + 58} ${r.f.cy} C${HX + 100} ${r.f.cy}, ${KX - 60} ${yy}, ${KX} ${yy}" stroke="${col}" stroke-width="${w}" fill="none" opacity="${on ? 0.45 : 0.5}" ${on ? '' : 'stroke-dasharray="3 5"'}/>
      ${on && n ? `<path class="lf-flow" d="M${HX + 58} ${r.f.cy} C${HX + 100} ${r.f.cy}, ${KX - 60} ${yy}, ${KX} ${yy}" stroke="${col}" stroke-width="${Math.max(1, w / 2.5)}" fill="none"/>` : ''}
      <foreignObject x="${KX}" y="${r.y}" width="${KW}" height="${KH}">${xlfCard(m, sel, total)}</foreignObject>`;
  }
  const st = XLF.ev && XLF.ev.stats;                                    // the entry core
  s += `<circle cx="${CX}" cy="${cy}" r="62" fill="url(#xlfHalo)"/><circle class="lf-pulse" cx="${CX}" cy="${cy}" r="34" fill="none" stroke="#00e5ff" stroke-width="1.5"/>
    <g filter="url(#xlfGlow)"><circle cx="${CX}" cy="${cy}" r="40" fill="#021626" stroke="#00e5ff" stroke-width="3"/>
    <text x="${CX}" y="${cy - 7}" fill="#7ff6ff" font-size="9" text-anchor="middle" letter-spacing="2">ENTRY</text>
    <text x="${CX}" y="${cy + 12}" fill="#fff" font-size="18" font-weight="bold" text-anchor="middle">${st ? st.n : '…'}</text>
    <text x="${CX}" y="${cy + 25}" fill="#5f9db8" font-size="8" text-anchor="middle">trades</text></g>`;
  return s + '</svg>';
}

function xlfHud() {
  const s = XLF.ev && XLF.ev.stats, b = XLF.ev && XLF.ev.live;
  if (!s) return `<div class="lf-scan"></div>`;
  const ch = XLF.ev.changed || {}, nch = Object.keys(ch).length;
  const cell = (k, v, d) => `<div class="lf-cell"><div class="lf-k">${k}</div><div class="lf-v">${v}</div><div class="lf-d">${d || '&nbsp;'}</div></div>`;
  const dd = (a, z, inv) => (b ? `<span class="${(inv ? z - a : a - z) >= 0 ? 'lf-pos' : 'lf-neg'}">${a - z >= 0 ? '+' : ''}${Math.abs(a - z) >= 100 ? money(a - z) : Math.round((a - z) * 10) / 10}</span> vs live` : '');
  return `<div class="lf-hud">
    ${cell('DRAFT NET', `<span class="${s.net >= 0 ? 'lf-pos' : 'lf-neg'}">${money(s.net)}</span>`, dd(s.net, b.net))}
    ${cell('TRADES', s.n, dd(s.n, b.n))}
    ${cell('WIN RATE', s.wr + '%', dd(s.wr, b.wr))}
    ${cell('PROFIT FACTOR', s.pf ?? '–', 'live ' + (b.pf ?? '–'))}
    ${cell('AVG WIN / LOSS', `${money(s.avg_win)} / ${money(s.avg_loss)}`, `live ${money(b.avg_win)} / ${money(b.avg_loss)}`)}
    ${cell('WORST LOSS', `<span class="lf-neg">${money(s.worst)}</span>`, dd(s.worst, b.worst))}
    ${cell('MAX DRAWDOWN', money(s.dd), dd(s.dd, b.dd, true))}
    ${cell('BOTH HALVES', `${xlfSign(s.train)} / ${xlfSign(s.test)}`, 'train / test')}
  </div>
  <div class="bar" style="align-items:center;flex-wrap:wrap;gap:6px">
    <span class="lf-sub" title="${esc(Object.entries(ch).map(([k, v]) => k + '=' + v).join('\n'))}">${nch ? `<b style="color:#ffd740">${nch} EA input(s) differ from the chart</b> (hover to see them)` : 'The draft is the setting on the chart.'}</span>
    <button class="lf-b" onclick="xlfReset()" ${nch ? '' : 'disabled'}>↺ BACK TO THE CHART'S SETTING</button>
    <button class="lf-b red" onclick="xlfApply(XLF.ev.over, 'the drafted exit set')" ${nch ? '' : 'disabled'}>💾 APPLY &amp; SAVE THIS EXIT SET</button>
    <button class="lf-b" onclick="xlfMt5(XLF.ev.over, 'xlf_draft', 'Extended lifecycle · draft')" ${nch ? '' : 'disabled'}>✓ VERIFY THE DRAFT IN MT5</button>
    ${XLF.evBusy ? '<span class="lf-sub">re-running the tester…</span>' : ''}${XLF.impBusy ? `<span class="lf-sub">measuring every switch… ${XLF.prog ? XLF.prog.done + '/' + XLF.prog.total : ''}</span>` : ''}
  </div>${xlfMt5HTML('xlf_draft', XLF.ev.over)}`;
}

function xlfOptHTML() {
  const p = XLF.prog, busy = XLF.optBusy;
  let h = `<div class="lf-panel" style="border-color:#ffd740">
    <div class="bar" style="justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
      <div><div class="lf-h" style="font-size:13px;color:#ffd740;text-shadow:0 0 8px #ffab00">🧠 FIND THE BEST EXIT SET · EVERY MODE, EVERY EXIT</div>
      <div class="lf-sub">Per exit mode: starts bare (no optional exits), then adds the switch that helps most, swaps presets and drops what stops paying,
        until nothing improves. The rankings show what every preset is worth on its own. Tester hypotheses on ${esc(SRC.ds)}: verify the winner in MT5.</div></div>
      <div class="bar" style="align-items:center;gap:6px;flex-wrap:wrap">
        <span class="lf-k">MODES</span>${[0, 1, 2].map((m) => `<label class="lf-sub"><input type="checkbox" ${XLF.modes[m] ? 'checked' : ''} ${busy ? 'disabled' : ''} onchange="XLF.modes[${m}]=this.checked"> ${m}</label>`).join('')}
        <select class="xlf-sel" style="width:auto" ${busy ? 'disabled' : ''} onchange="XLF.objective=this.value">
          ${[['net', 'most profit'], ['net_dd', 'profit ÷ drawdown'], ['pf', 'profit factor']].map(([v, t]) => `<option value="${v}" ${XLF.objective === v ? 'selected' : ''}>${t}</option>`).join('')}</select>
        <label class="lf-sub" title="reject anything with more than 25% extra drawdown, a 25% bigger worst loss, under a third of the trades, or a profitable half of the data turned negative"><input type="checkbox" ${XLF.guard ? 'checked' : ''} ${busy ? 'disabled' : ''} onchange="XLF.guard=this.checked"> guard: no more risk than live</label>
        ${busy ? `<button class="lf-b red" onclick="xlfStop()">■ STOP</button>` : `<button class="lf-b" style="border-color:#ffd740;color:#ffd740" onclick="xlfOptimise()">🧠 SEARCH ALL EXITS</button>`}
      </div></div>`;
  if (busy && p) {
    const pct = p.total ? Math.min(99, Math.round((100 * p.done) / p.total)) : 0;
    h += `<div class="dexprog" style="margin-top:8px"><div class="dexprog-t">SEARCHING · ${esc(p.phase || '')}</div>
      <div class="dexprog-bar"><div style="height:100%;width:${pct}%;background:repeating-linear-gradient(45deg,#ffd740 0 10px,#ffab00 10px 20px);transition:width .4s"></div></div>
      <div class="dexprog-s">${p.done} tester runs · ${p.seconds} s</div></div>`;
  }
  const o = XLF.opt;
  if (o && o.key === XLF.key) {
    const ref = o.ref, best = o.best;
    if (best != null) {
      const w = o.modes[best], bs = w.stats;
      const fams = {};
      for (const m of XLF.spec.modules) if (m.modes.includes(best) && m.off && w.sel[m.key] !== 'off') (fams[m.family] = fams[m.family] || []).push(`${m.name}: ${xlfLabel(m, w.sel[m.key])}`);
      const stop = xlfMod('stop');
      h += `<div class="lf-verdict" style="border-color:#ffd740;margin-top:10px;font-size:12.5px">👑 <b>BEST: EXIT MODE ${best}</b> · ${money(bs.net)} (live ${money(ref.net)}) · WR ${bs.wr}% · worst ${money(bs.worst)} · DD ${money(bs.dd)}
        <div class="lf-sub" style="margin-top:4px">stop: <b>${esc(xlfLabel(stop, w.sel.stop))}</b> · ${XLF.spec.families.filter((f) => fams[f.key]).map((f) => `${esc(f.name.toLowerCase())}: <b>${fams[f.key].map(esc).join(' + ')}</b>`).join(' · ') || 'no optional exits'}</div></div>`;
    }
    h += '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px">';
    for (const [md, r] of Object.entries(o.modes)) {
      const s = r.stats;
      h += `<div class="xlf-mode ${Number(md) === best ? 'win' : ''}">
        <div class="bar" style="justify-content:space-between"><div class="lf-h" style="font-size:12px">${Number(md) === best ? '👑 ' : ''}MODE ${md}</div>
          <div class="lf-v" style="font-size:15px">${s ? `<span class="${s.net >= 0 ? 'lf-pos' : 'lf-neg'}">${money(s.net)}</span>` : '–'}</div></div>
        ${s ? `<div class="lf-sub">${s.n} trades · WR ${s.wr}% · PF ${s.pf ?? '–'} · avg ${money(s.avg_win)} / ${money(s.avg_loss)} · worst ${money(s.worst)} · DD ${money(s.dd)}${r.score == null ? ' · <span class="lf-neg">fails the guard</span>' : ''}</div>` : ''}
        <div style="margin:6px 0">${r.path.map((p, i) => `<div class="xlf-path">${i ? `<span style="color:${p.step === 'drop' ? '#ff5c7a' : p.step === 'swap' ? '#ffd740' : '#4dffb0'}">${p.step === 'drop' ? '−' : p.step === 'swap' ? '⇄' : '+'}</span> <b>${esc(p.name)}</b>: ${esc(p.label)} ${xlfSign(p.d)}` : `◇ ${esc(p.label)}: ${p.stats ? money(p.stats.net) : '–'}`}</div>`).join('')}</div>
        <div class="bar" style="gap:6px;flex-wrap:wrap"><button class="lf-b" onclick="xlfLoadOpt(${md})">⟁ LOAD INTO THE TREE</button>
          <button class="lf-b red" onclick="xlfApply(XLF.opt.modes[${md}].over, 'the best mode-${md} exit set')">💾 APPLY &amp; SAVE</button>
          <button class="lf-b" onclick="xlfMt5(XLF.opt.modes[${md}].over, 'xlf_opt${md}', 'Extended lifecycle · best mode ${md}')">✓ VERIFY IN MT5</button></div>
        ${xlfMt5HTML('xlf_opt' + md, r.over)}</div>`;
    }
    h += '</div>';
    const rk = best != null && o.rankings[best];
    if (rk) {
      h += `<div class="lf-k" style="margin:12px 0 4px">RANKINGS · EVERY PRESET ALONE ON BARE MODE ${best} (bare: ${money(o.modes[best].bare && o.modes[best].bare.net)})</div><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:10px">`;
      for (const f of XLF.spec.families) {
        const l = rk[f.key]; if (!l || !l.length) continue;
        h += `<div><div class="lf-k" style="color:#7ff6ff">BEST ${esc(f.name.toUpperCase())}</div><table class="xlf-tbl"><tr><th>preset</th><th>net</th><th>vs bare</th><th>WR</th><th>worst</th></tr>${l.slice(0, 6).map((x, i) =>
          `<tr><td>${i === 0 ? '🥇 ' : ''}${esc(x.name)}: ${esc(x.label)}${x.ok ? '' : ' <span title="fails the guard">⚠</span>'}</td><td>${money(x.net)}</td><td>${xlfSign(x.d)}</td><td>${x.wr}%</td><td>${money(x.worst)}</td></tr>`).join('')}</table></div>`;
      }
      h += '</div>';
    }
  }
  return h + '</div>';
}

function pXLife() {
  lfCss(); xlfCss(); xlfLoad();
  if (!XLF.mt5 && !XLF.mt5poll) xlfMt5Status();
  let h = `<div class="lf-wrap">
    <div class="bar" style="justify-content:space-between;align-items:flex-start;flex-wrap:wrap">
      <div><div class="lf-h">⟁⟁ EXTENDED LIFECYCLE · EVERY EXIT WE HAVE</div>
      <div class="lf-sub">Every exit the tester and the EA both run, as a switch. Flip one and the tester re-runs the whole draft; each node says what switching it costs
        or which preset would add the most. Everything here is a real EA input: apply it, then verify it in MT5. Data ${esc(SRC.ds)}.</div></div>
      <button class="lf-b" onclick="xlfClose()">← BACK TO THE CURRENT LIFECYCLE</button>
    </div>`;
  if (XLF.err) h += `<p class="note bad">${esc(XLF.err)} <a style="cursor:pointer" onclick="XLF.err='';renderPanel('tt')">✕</a></p>`;
  if (!XLF.spec || !XLF.sel) return h + '<div class="lf-scan"></div><div class="lf-sub">Loading every exit…</div></div>';
  h += xlfHud() + xlfOptHTML() + `<div style="margin-top:10px">${xlfTree()}</div>`;
  return h + '</div>';
}
