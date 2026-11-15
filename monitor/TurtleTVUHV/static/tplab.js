// Take Profit Lab: the Turtle TV tester at each take-profit distance, on the settings on screen.
const TPL = { res: null, busy: false, err: '' };
const TP_MODES = [
  { id: 0, title: 'EMA / Support + Partial & Trail', short: 'Manage the first target, partial close, breakeven and trailing stop.', icon: '🎯' },
  { id: 1, title: 'Next EMA Target', short: 'Close at the nearer fast or slow EMA beyond the entry.', icon: '↗' },
  { id: 2, title: 'Slow EMA Close-Back', short: 'Hold until a completed candle closes back across the slow EMA.', icon: '↩' },
];
const TPVIEW = { selected: null, results: {}, errors: {}, busy: false, key: '', seq: 0 };

function pTP() {
  if (TPVIEW.selected == null) return tpModePickerHTML();
  const r = TPL.res;
  let sweep = '';
  if (r) {
    const max = Math.max(1, ...r.rows.map((x) => Math.abs(x.net)));
    sweep = `<div class="crth" style="margin-top:12px">FIXED TARGET SWEEP</div><p class="note">${r.rows.length} runs in ${r.seconds} s on ${esc(r.ds)} · best: <b>${r.best.tp_pips ? r.best.tp_pips + ' pips' : "the settings' own targets"}</b> (${money(r.best.net)})</p>`;
    sweep += '<table><tr><th>Take profit</th><th>Trades</th><th>Net</th><th></th><th>Win rate</th><th>PF</th><th>Avg win</th><th>Avg loss</th><th>Worst</th></tr>';
    for (const x of r.rows) {
      const bar = Math.round((Math.abs(x.net) / max) * 160), best = x === r.best ? ' style="background:#1d3a2a"' : '';
      sweep += `<tr${best}><td>${x.tp_pips ? x.tp_pips + ' pips' : 'own targets'}</td><td>${x.n}</td><td class="${x.net >= 0 ? 'pos' : 'neg'}">${money(x.net)}</td>
        <td><div style="width:${bar}px;height:8px;background:${x.net >= 0 ? '#69f0ae' : '#ff5252'}"></div></td>
        <td>${x.wr ?? '–'}%</td><td>${x.pf ?? '–'}</td><td>${x.avg_win != null ? money(x.avg_win) : '–'}</td><td>${x.avg_loss != null ? money(x.avg_loss) : '–'}</td><td>${x.worst != null ? money(x.worst) : '–'}</td></tr>`;
    }
    sweep += '</table>';
  }
  const left = tunerHTML();
  const right = `<div class="crth">SCAN · EVERY TAKE-PROFIT SETTING</div>
    ${TPS.busy ? tpProgressHTML() : ''}<div class="bar"><button class="dexbtn" onclick="tpScanRun()" ${TPS.busy ? 'disabled' : ''}>${TPS.busy ? 'Scanning…' : 'Scan every take-profit setting'}</button>
    <button class="dexbtn sm" onclick="tpRun()" ${TPL.busy ? 'disabled' : ''}>${TPL.busy ? 'Running…' : 'Fixed-target sweep'}</button></div>
    ${TPL.err ? `<p class="note bad">${esc(TPL.err)}</p>` : ''}${tpScanHTML()}${tpaHTML()}${sweep}`;
  const mode = TP_MODES.find((item) => item.id === TPVIEW.selected);
  return `<div class="lab">
    <div class="bar" style="justify-content:space-between;align-items:center">
      <div><div class="k" style="font-size:10px">MODE ${mode.id}</div><div class="crth" style="font-size:15px">${mode.icon} ${esc(mode.title)}</div><p class="note">${esc(mode.short)}</p></div>
      <button class="dexbtn sm" onclick="tpBackToModes()">← Choose another exit style</button>
    </div>
    ${modeDetailIntro(mode)}
    <div style="margin-top:12px">${left}</div>
    <details class="dexpanel" style="margin-top:16px;padding:12px">
      <summary class="crth" style="cursor:pointer">TARGET SCANS &amp; TRADE-PATH ANALYSIS</summary>
      <div style="margin-top:12px">${right}</div>
    </details>
  </div>`;
}

function tpModePickerHTML() {
  tpModeResultsLoad();
  return `<div class="lab">
    <div class="crth" style="font-size:16px">🎯 TAKE PROFIT LAB · PICK AN EXIT STYLE</div>
    <p class="note">Choose how trades close. Each preview below runs the same current chart settings with that exit mode selected. Simulator results are hypotheses; the MT5 Strategy Tester is the judge.</p>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:14px">
      ${TP_MODES.map((mode) => {
        const result = TPVIEW.results[mode.id];
        const stats = result && result.stats;
        const error = TPVIEW.errors[mode.id];
        return `<button class="dexpanel" onclick="tpSelectMode(${mode.id})" style="display:block;text-align:left;width:100%;cursor:pointer;padding:18px;border:2px solid #26c6da;border-radius:12px;background:linear-gradient(145deg,#0b1424,#10251f);color:inherit;font:inherit">
          <div class="k" style="font-size:10px">MODE ${mode.id}</div><div style="font-size:24px">${mode.icon}</div><div class="crth" style="font-size:14px;margin:8px 0">${esc(mode.title)}</div>
          <div class="note" style="min-height:42px">${esc(mode.short)}</div>
          <div style="border-top:1px solid #29415b;padding-top:10px;margin-top:10px">
            <div class="k" style="font-size:10px">CURRENT SETTINGS · SIMULATOR HYPOTHESIS</div>
            ${stats ? `<b style="font-size:18px">${money(stats.net)}</b><div>${stats.n} trades · WR ${stats.wr ?? '–'}% · PF ${stats.pf ?? '–'}</div><div>Avg loss ${stats.avg_loss != null ? money(stats.avg_loss) : '–'} · Worst ${stats.worst != null ? money(stats.worst) : '–'}</div>`
              : `<div class="note ${error ? 'bad' : ''}">${error ? 'Preview failed: ' + esc(error) : TPVIEW.busy ? 'Calculating preview…' : 'Preview not available'}</div>`}
          </div>
          <div class="dexbtn sm" style="display:inline-block;margin-top:12px">Choose this exit style →</div>
        </button>`;
      }).join('')}
    </div>
  </div>`;
}

function tpModeResultsLoad() {
  const key = JSON.stringify([CUR, SRC.ds, SRC.mode]);
  if (TPVIEW.key === key && (TPVIEW.busy || TP_MODES.every((mode) => TPVIEW.results[mode.id] || TPVIEW.errors[mode.id]))) return;
  TPVIEW.key = key;
  TPVIEW.results = {};
  TPVIEW.errors = {};
  TPVIEW.busy = true;
  const seq = ++TPVIEW.seq;
  (async () => {
    for (const mode of TP_MODES) {
      if (TPVIEW.key !== key || TPVIEW.seq !== seq) return;
      try {
        TPVIEW.results[mode.id] = await api('/api/tplab_set', {
          inputs: CUR, ds: SRC.ds, mode: SRC.mode, overrides: { InpExitMode: mode.id },
        });
      } catch (error) {
        TPVIEW.errors[mode.id] = error.message;
      }
      if (TPVIEW.selected == null) renderPanel('tt');
    }
  })().finally(() => {
    if (TPVIEW.key === key && TPVIEW.seq === seq) {
      TPVIEW.busy = false;
      if (TPVIEW.selected == null) renderPanel('tt');
    }
  });
}

function tpSelectMode(mode) {
  TPVIEW.selected = mode;
  TUN.activeMode = mode;
  TUN.over = { InpExitMode: String(mode) };
  TUN.err = '';
  TUN.res = null;
  TPBASE.key = '';
  TPBASE.res = null;
  TPBASE.busy = false;
  TPBASE.seq += 1;
  TPL.res = null;
  TPL.err = '';
  TPS.scan = null;
  TPA.res = null;
  renderPanel('tt');
}

function tpBackToModes() {
  TPVIEW.selected = null;
  TPVIEW.seq += 1;
  renderPanel('tt');
}

function modeDetailIntro(mode) {
  if (mode.id === 0) return `<div class="crt" style="margin:8px 0;padding:10px">
    <b>How it exits:</b> use the EA’s EMA/support target, then manage a partial close, breakeven and trailing stop. The cards below contain settings for this exit style.
  </div>`;
  if (mode.id === 1) return `<div class="crt" style="margin:8px 0;padding:10px">
    <b>How it exits:</b> at entry the EA chooses the nearer fast or slow EMA that is beyond entry; touching it closes the trade. If neither EMA is beyond entry, the fallback close rule applies. The cards below tune this mode and its optional Exit Lab rules.
  </div>`;
  const ema = CUR && CUR.InpEmaSlow != null ? esc(CUR.InpEmaSlow) : 'slow';
  return `<div class="crt" style="margin:8px 0;padding:10px">
    <b>How it exits:</b> a long closes after a completed candle closes below the ${ema} EMA; a short closes after a completed candle closes above it. The entry candle is not used for that close-back. The cards below tune Mode 2 and optional Exit Lab rules.
  </div>`;
}

async function tpRun() {
  TPL.busy = true; TPL.err = ''; renderPanel('tt');
  try {
    TPL.res = await api('/api/tplab', { inputs: tpInputs(), ds: SRC.ds, mode: SRC.mode });
  } catch (e) {
    TPL.err = 'The sweep failed: ' + (e && e.message ? e.message : e);
  }
  TPL.busy = false; renderPanel('tt');
}

// ---- slider (one run per move) and the scan over every take-profit setting
const TPS = { pips: 0, one: null, scan: null, busy: false, err: '', t: 0 };


function tpDiagram(rows, cur) {
  // net (bars) and win rate (line) by fixed target distance, the chosen distance marked
  const rs = rows.filter((x) => x.setting === 'InpFixTpPips').sort((a, b) => a.value - b.value);
  if (!rs.length) return '';
  const W = 560, H = 200, P = 34, xs = (i) => P + (i * (W - 2 * P)) / Math.max(1, rs.length - 1);
  const nets = rs.map((x) => x.net), lo = Math.min(0, ...nets), hi = Math.max(1, ...nets), y = (v) => H - P - ((v - lo) / (hi - lo || 1)) * (H - 2 * P);
  const wr = rs.map((x) => x.wr || 0), yw = (v) => H - P - (v / 100) * (H - 2 * P);
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px">`;
  rs.forEach((x, i) => {
    const bh = Math.abs(y(x.net) - y(0)), by = x.net >= 0 ? y(x.net) : y(0);
    s += `<rect x="${xs(i) - 12}" y="${by}" width="24" height="${Math.max(1, bh)}" fill="${x.net >= 0 ? '#69f0ae' : '#ff5252'}" opacity="0.7"/>`;
    s += `<text x="${xs(i)}" y="${H - 14}" font-size="10" text-anchor="middle" fill="#b0bec5">${x.value || 'own'}</text>`;
  });
  s += `<polyline fill="none" stroke="#ffd740" stroke-width="2" points="${rs.map((x, i) => `${xs(i)},${yw(x.wr || 0)}`).join(' ')}"/>`;
  s += `<line x1="${P}" x2="${W - P}" y1="${y(0)}" y2="${y(0)}" stroke="#567" stroke-dasharray="3 3"/>`;
  const cx = rs.findIndex((x) => x.value === cur);
  if (cx >= 0) s += `<line x1="${xs(cx)}" x2="${xs(cx)}" y1="${P}" y2="${H - P}" stroke="#fff" stroke-dasharray="4 3"/>`;
  return s + `<text x="${P}" y="14" font-size="11" fill="#b0bec5">bars: net $ · line: win rate % (yellow) · white line: current target</text></svg>`;
}

function tpSliderHTML() {
  const o = TPS.one;
  let h = `<div style="margin:10px 0"><label>Fixed target: <b>${TPS.pips ? TPS.pips + ' pips' : 'own targets'}</b></label><br>
    <input type="range" min="0" max="80" step="1" value="${TPS.pips}" oninput="tpSlide(this.value)" style="width:420px"></div>`;
  if (TPS.busy) h += '<p class="note">Running…</p>';
  if (o) h += `<p class="note">Net <b class="${o.stats.net >= 0 ? 'pos' : 'neg'}">${money(o.stats.net)}</b> · ${o.stats.n} trades · win rate ${o.stats.wr ?? '–'}% · PF ${o.stats.pf ?? '–'} · avg win ${o.stats.avg_win != null ? money(o.stats.avg_win) : '–'} · avg loss ${o.stats.avg_loss != null ? money(o.stats.avg_loss) : '–'}</p>`;
  return h;
}

function tpSlide(v) {
  TPS.pips = Number(v); TPS.busy = true; clearTimeout(TPS.t); renderPanel('tt');
  TPS.t = setTimeout(async () => {
    try {
      TPS.one = await api('/api/tplab_one', { inputs: tpInputs(), ds: SRC.ds, mode: SRC.mode, overrides: { InpFixTpPips: TPS.pips } });
    } catch (e) { TPS.err = 'The run failed: ' + e.message; }
    TPS.busy = false; renderPanel('tt');
  }, 350);
}

let TPS_POLL = 0;

async function tpScanRun() {
  TPS.busy = true; TPS.err = ''; TPS.prog = { done: 0, total: 0, current: 'starting…', seconds: 0 }; renderPanel('tt');
  try {
    const st = await api('/api/tplab_scan', { inputs: tpInputs(), ds: SRC.ds, mode: SRC.mode });
    if (st && st.busy) throw new Error('a scan is already running');
    clearInterval(TPS_POLL);
    TPS_POLL = setInterval(tpScanPoll, 900);
  } catch (e) { TPS.busy = false; TPS.err = 'The scan failed: ' + e.message; renderPanel('tt'); }
}

async function tpScanPoll() {
  try {
    const p = await api('/api/tplab_progress', {});
    TPS.prog = p;
    if (!p.running) {
      clearInterval(TPS_POLL); TPS.busy = false;
      if (p.error) TPS.err = 'The scan failed: ' + p.error; else TPS.scan = p.result;
    }
  } catch (e) { clearInterval(TPS_POLL); TPS.busy = false; TPS.err = 'Lost contact with the scan: ' + e.message; }
  renderPanel('tt');
}

function tpProgressHTML() {
  const p = TPS.prog || { done: 0, total: 0, current: '', seconds: 0 };
  const pct = p.total ? Math.round((100 * p.done) / p.total) : 0;
  return `<div class="dexprog"><div class="dexprog-t">SCANNING TAKE-PROFIT SETTINGS · ${pct}%</div>
    <div class="dexprog-bar"><div style="height:100%;width:${pct}%;background:repeating-linear-gradient(45deg,#00e676 0 10px,#00c853 10px 20px);transition:width .4s"></div></div>
    <div class="dexprog-s">${p.done} of ${p.total} runs · now: ${esc(p.current || '')} · ${p.seconds || 0} s</div></div>`;
}

function tpScanHTML() {
  const s = TPS.scan;
  if (!s) return '';
  let h = `<div class="crt">${s.rows.length} runs in ${s.seconds} s · on-screen settings: net <b>${money(s.base.net)}</b>, win rate <b>${s.base.wr ?? '–'}%</b></div>`;
  h += '<table><tr><th>Setting</th><th>Apply</th><th>Value</th><th>Trades</th><th>Net</th><th>Win rate</th><th>PF</th><th>Avg win</th><th>Avg loss</th></tr>';
  for (const x of s.rows) {
    const b = s.best[x.setting] === x ? ' style="background:#1d3a2a"' : '';
    h += `<tr${b}><td>${esc(tunLabel(x.setting))}</td><td><button class="dexbtn sm" onclick="tpApplySetting('${esc(x.setting)}', '${esc(x.value)}', 'scan')">Apply</button></td><td>${esc(x.value)}</td><td>${x.n}</td><td class="${x.net >= 0 ? 'pos' : 'neg'}">${money(x.net)}</td><td>${x.wr ?? '–'}%</td><td>${x.pf ?? '–'}</td><td>${x.avg_win != null ? money(x.avg_win) : '–'}</td><td>${x.avg_loss != null ? money(x.avg_loss) : '–'}</td></tr>`;
  }
  h += '</table><h4>Diagram: fixed target distance</h4>' + tpDiagram(s.rows, TPS.pips);
  return h;
}

async function tpApplySetting(name, rawValue, source) {
  if (!TUN.controls) await tunLoad();
  const known = name === 'InpFixTpPips' || (TUN.allControls && TUN.allControls.some((c) => c.name === name));
  const textValue = String(rawValue).toLowerCase();
  const value = typeof rawValue === 'boolean' || textValue === 'true' ? true
    : textValue === 'false' ? false : Number(rawValue);
  if (!known || (typeof value === 'number' && !Number.isFinite(value))) {
    toast('Could not apply this take-profit setting: invalid setting or value.');
    return;
  }
  const note = source === 'paths'
    ? `Applied the estimated ${value} pip target to the chart.`
    : `Applied ${name}=${value} to the chart.`;
  await tpApplyOverrides({ [name]: String(value) }, note);
}

async function tpApplyOverrides(overrides, note) {
  CUR = { ...CUR, InpExitMode: String(TPVIEW.selected), ...overrides };
  ACTIVE_LAB = null;
  settingsTouched = true;
  markForm();
  TAB.tt = 'overview';
  renderPanel('tt');
  clearTimeout(simTimer);
  try {
    const refreshed = await runSim();
    if (!refreshed) {
      tpApplyNotice('SETTING APPLIED · OVERVIEW NOT REFRESHED',
        `${note} The chart settings changed, but a newer update superseded this result or the simulation failed. Check the Overview before relying on it.`, true);
      return;
    }
    tpApplyNotice('SETTING APPLIED · OVERVIEW UPDATED',
      `${note} The Overview now shows the refreshed Turtle TV simulation. This is a hypothesis; verify it in the MT5 Strategy Tester.`, false);
  } catch (error) {
    tpApplyNotice('SETTING APPLIED · OVERVIEW UPDATE FAILED',
      `${note} The chart settings changed, but the simulation could not refresh: ${error.message || error}.`, true);
  }
}

function tpApplyNotice(title, message, failed) {
  toast(`<strong class="tp-notice-title">${esc(title)}</strong><span>${esc(message)}</span>`, 14000);
  $('#toast').classList.add(failed ? 'tp-failed' : 'tp-applied');
}

const M2 = { over: {}, base: null, res: null, baseBusy: false, busy: false, err: '', key: '', baseSeq: 0, seq: 0, timer: null };

function mode2Key() { return JSON.stringify([CUR, SRC.ds, SRC.mode]); }

function mode2Load() {
  if (!TUN.mode2Controls) {
    if (!TUN.loading) tunLoad().then(() => renderPanel('tt'));
    return;
  }
  const key = mode2Key();
  if (M2.key !== key) {
    M2.key = key;
    M2.base = null;
    M2.res = null;
    M2.err = '';
    M2.baseBusy = false;
    M2.busy = false;
    clearTimeout(M2.timer);
    M2.baseSeq += 1;
    M2.seq += 1;
  }
  if (M2.base || M2.baseBusy || M2.err) return;
  M2.baseBusy = true;
  const seq = ++M2.baseSeq;
  api('/api/tplab_set', { inputs: CUR, ds: SRC.ds, mode: SRC.mode, overrides: { InpExitMode: 2 } })
    .then((result) => {
      if (M2.key !== key || M2.baseSeq !== seq) return;
      M2.base = result;
      if (!Object.keys(M2.over).length) M2.res = result;
    })
    .catch((error) => {
      if (M2.key === key && M2.baseSeq === seq) M2.err = 'Could not run the Mode 2 baseline: ' + error.message;
    })
    .finally(() => {
      if (M2.key === key && M2.baseSeq === seq) {
        M2.baseBusy = false;
        renderPanel('tt');
      }
    });
}

function mode2Value(control) {
  const raw = Object.prototype.hasOwnProperty.call(M2.over, control.name)
    ? M2.over[control.name] : (CUR[control.name] ?? control.vals[0]);
  if (control.kind === 'enum') {
    const normalized = raw === true || String(raw).toLowerCase() === 'true' ? 1
      : raw === false || String(raw).toLowerCase() === 'false' ? 0 : raw;
    const option = control.options.find(([value]) => String(value) === String(normalized));
    return option ? option[0] : control.vals[0];
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : control.min;
}

function mode2Set(name, raw, kind) {
  const control = TUN.mode2Controls.find((item) => item.name === name);
  if (!control) return;
  if (kind === 'num') {
    const value = Number(raw);
    if (!Number.isFinite(value) || value < control.min || value > control.max) {
      M2.err = `Invalid value for ${control.label}.`;
      renderPanel('tt');
      return;
    }
    M2.over[name] = value;
  } else {
    const option = control.options.find(([value]) => String(value) === String(raw));
    if (!option) {
      M2.err = `Invalid choice for ${control.label}.`;
      renderPanel('tt');
      return;
    }
    M2.over[name] = option[0];
  }
  M2.res = null;
  M2.err = '';
  M2.busy = true;
  const key = mode2Key(), seq = ++M2.seq;
  M2.key = key;
  clearTimeout(M2.timer);
  M2.timer = setTimeout(() => {
    if (M2.key !== key || M2.seq !== seq) return;
    renderPanel('tt');
    api('/api/tplab_set', {
      inputs: CUR, ds: SRC.ds, mode: SRC.mode,
      overrides: { ...M2.over, InpExitMode: 2 },
    }).then((result) => {
      if (M2.key === key && M2.seq === seq) M2.res = result;
    }).catch((error) => {
      if (M2.key === key && M2.seq === seq) M2.err = 'The Mode 2 comparison failed: ' + error.message;
    }).finally(() => {
      if (M2.key === key && M2.seq === seq) {
        M2.busy = false;
        renderPanel('tt');
      }
    });
  }, 300);
}

function mode2Reset() {
  M2.over = {};
  M2.res = M2.base;
  M2.err = '';
  clearTimeout(M2.timer);
  M2.seq += 1;
  M2.busy = false;
  renderPanel('tt');
}

function mode2Stats(title, result, loading) {
  const s = result && result.stats;
  return `<div class="crt" style="flex:1 1 145px;min-width:135px;padding:8px">
    <div class="crth" style="font-size:10px;margin:0 0 5px">${title}</div>
    ${s ? `<b>${money(s.net)}</b><div>${s.n} trades · WR ${s.wr ?? '–'}%</div><div>PF ${s.pf ?? '–'}</div>
      <div>Avg loss ${s.avg_loss != null ? money(s.avg_loss) : '–'} · Worst ${s.worst != null ? money(s.worst) : '–'}</div>` : `<div>${loading ? 'Running…' : 'No result yet'}</div>`}
  </div>`;
}

function mode2HTML() {
  mode2Load();
  if (!TUN.mode2Controls) return `<section class="dexpanel" style="padding:14px;margin:12px 0"><div class="crth">MODE 2 VISUALIZER</div><p class="note">${TUN.err ? esc(TUN.err) : 'Loading Mode 2 controls…'}</p></section>`;
  const emaControl = TUN.mode2Controls.find((control) => control.name === 'InpEmaSlow');
  const ema = esc(mode2Value(emaControl));
  let controls = '';
  const groups = [...new Set(TUN.mode2Controls.map((control) => control.group))];
  for (const group of groups) {
    controls += `<div class="dexpanel" style="padding:10px;min-width:220px;flex:1 1 260px">
      <div class="crth" style="font-size:11px;margin:0 0 8px">${esc(group).toUpperCase()}</div>`;
    for (const control of TUN.mode2Controls.filter((item) => item.group === group)) {
      const value = mode2Value(control);
      if (control.kind === 'num') {
        const min = Math.min(control.min, value), max = Math.max(control.max, value);
        controls += `<label class="lever"><span>${esc(control.label)} <b>${esc(value)}</b></span>
          <input type="range" min="${min}" max="${max}" step="${control.step}" value="${esc(value)}"
            oninput="mode2Set('${esc(control.name)}', this.value, 'num')"></label>`;
      } else {
        controls += `<label class="lever"><span>${esc(control.label)}</span><select
          onchange="mode2Set('${esc(control.name)}', this.value, 'enum')"
          style="background:#03140b;color:#b9f6ca;border:2px solid #37474f;border-radius:8px;font:12px 'Courier New',monospace;padding:3px">
          ${control.options.map(([option, label]) => `<option value="${esc(option)}" ${String(option) === String(value) ? 'selected' : ''}>${esc(label)}</option>`).join('')}
        </select></label>`;
      }
    }
    controls += '</div>';
  }
  const overrideCount = Object.keys(M2.over).length;
  const candidate = overrideCount ? M2.res : (M2.res || M2.base);
  return `<section class="dexpanel" style="padding:14px;margin:12px 0;border:2px solid #26c6da;background:linear-gradient(145deg,#0b1424,#10251f)">
    <div class="crth" style="font-size:15px">MODE 2 VISUALIZER · CLOSE BACK ACROSS THE SLOW EMA</div>
    <p class="note">Mode 2 has no EMA-price target. It exits on a completed candle close back across the slow EMA (currently ${ema} EMA). The entry candle is not used for that close-back. The broker stop and fixed TP (if enabled), plus optional Exit Lab rules, can still close the trade first.</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:stretch;margin:12px 0">
      <div class="crt" style="flex:1 1 260px;padding:10px"><b class="pos">LONG</b><div style="margin-top:8px">Entry → wait for a completed candle → close below the ${ema} EMA → <b>close position</b></div></div>
      <div class="crt" style="flex:1 1 260px;padding:10px"><b class="neg">SHORT</b><div style="margin-top:8px">Entry → wait for a completed candle → close above the ${ema} EMA → <b>close position</b></div></div>
    </div>
    <p class="note">Preview always forces <b>InpExitMode=2</b>, even if the chart currently uses another mode. These simulator figures are hypotheses only—not MT5 results or a recommendation.</p>
    ${M2.err ? `<p class="note bad">${esc(M2.err)}</p>` : ''}
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0">
      ${mode2Stats('MODE 2 BASELINE · CURRENT INPUTS', M2.base, M2.baseBusy)}
      ${mode2Stats(overrideCount ? 'MODE 2 CANDIDATE · SIMULATOR HYPOTHESIS' : 'MODE 2 PREVIEW · NO OVERRIDES', candidate, M2.busy || M2.baseBusy)}
    </div>
    <div class="bar"><button class="dexbtn sm" onclick="mode2Reset()" ${overrideCount ? '' : 'disabled'}>Reset Mode 2 controls</button>
      <button class="dexbtn" onclick="tpApplyMode2()" ${M2.busy ? 'disabled' : ''}>Apply Mode 2 settings to chart</button>
      ${M2.busy ? '<span class="note">Running Mode 2 comparison…</span>' : ''}</div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px">${controls}</div>
  </section>`;
}

async function tpApplyMode2() {
  const overrides = Object.fromEntries(Object.entries(M2.over).map(([name, value]) => [name, String(value)]));
  overrides.InpExitMode = '2';
  await tpApplyOverrides(overrides,
    `Applied Mode 2${Object.keys(M2.over).length ? ` with ${Object.keys(M2.over).length} tuned override${Object.keys(M2.over).length === 1 ? '' : 's'}` : ''}.`);
}

// ---- trade paths: how far each trade went for us, and what each target distance would earn (an estimate; the tester confirms)
const TPA = { res: null, busy: false, err: '' };

function tpaBars(vals, labels, W, H, color) {
  const max = Math.max(1, ...vals.map(Math.abs)), P = 28, bw = (W - 2 * P) / vals.length;
  let s = `<svg viewBox="0 0 ${W} ${H + 20}" width="100%" style="max-width:${W}px">`;
  vals.forEach((v, i) => {
    const h = (Math.abs(v) / max) * (H - 2 * P), x = P + i * bw + 2, y = v >= 0 ? H - P - h : H - P;
    s += `<rect x="${x}" y="${y}" width="${bw - 4}" height="${Math.max(1, h)}" fill="${v >= 0 ? color : '#ff5252'}" opacity="0.8"/>`;
    s += `<text x="${x + (bw - 4) / 2}" y="${H - 10}" font-size="9" text-anchor="middle" fill="#b0bec5">${labels[i]}</text>`;
  });
  return s + '</svg>';
}

function tpaScatter(pts, W, H) {
  const P = 30, xm = Math.max(10, ...pts.map((p) => p[0])), ym = Math.max(1, ...pts.map((p) => Math.abs(p[1])));
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px"><line x1="${P}" x2="${W - P}" y1="${H / 2}" y2="${H / 2}" stroke="#567"/>`;
  for (const [m, p] of pts) s += `<circle cx="${P + (m / xm) * (W - 2 * P)}" cy="${H / 2 - (p / ym) * (H / 2 - P)}" r="2" fill="${p >= 0 ? '#69f0ae' : '#ff5252'}" opacity="0.5"/>`;
  return s + `<text x="${P}" y="12" font-size="10" fill="#b0bec5">x: best move for us (pips) · y: trade result (± $${Math.round(ym)})</text></svg>`;
}

async function tpaRun() {
  TPA.busy = true; TPA.err = ''; renderPanel('tt');
  try { TPA.res = await api('/api/tplab_paths', { inputs: tpInputs(), ds: SRC.ds, mode: SRC.mode }); }
  catch (e) { TPA.err = 'The analysis failed: ' + e.message; }
  TPA.busy = false; renderPanel('tt');
}

function tpaHTML() {
  let h = `<div style="margin-top:14px"><button class="dexbtn" onclick="tpaRun()" ${TPA.busy ? 'disabled' : ''}>${TPA.busy ? 'Analysing every trade…' : 'Analyse trade paths'}</button>`;
  if (TPA.err) h += `<p class="note bad">${esc(TPA.err)}</p>`;
  const r = TPA.res;
  if (r && r.trades) {
    const b = r.best;
    h += `<h4>Trade paths · ${r.trades} trades</h4>
      <p class="note">Median best move for us: <b>${r.mfe_median} pips</b> · 75th percentile <b>${r.mfe_p75}</b> · median worst move against us <b>${r.mae_median}</b> · p75 <b>${r.mae_p75}</b>.
      Suggested fixed target (estimate): <b>${b.tp} pips</b> → ${b.hit_rate}% of trades reach it, estimated net ${money(b.est_net)} (actual ${money(r.actual_net)}).</p>`;
    h += '<p class="note">' + r.note + '</p>';
    h += '<h4>Target curve (estimate)</h4>' + tpaBars(r.curve.map((c) => c.est_net), r.curve.map((c) => c.tp), 560, 180, '#69f0ae');
    h += '<table><tr><th>Target</th><th>Apply</th><th>Trades reaching it</th><th>Estimated net</th><th>Per trade</th></tr>' +
      r.curve.map((c) => `<tr${c === b ? ' style="background:#1d3a2a"' : ''}><td>${c.tp} pips</td><td><button class="dexbtn sm" onclick="tpApplySetting('InpFixTpPips', '${esc(c.tp)}', 'paths')">Apply</button></td><td>${c.hit_rate}%</td><td class="${c.est_net >= 0 ? 'pos' : 'neg'}">${money(c.est_net)}</td><td>${money(c.est_avg)}</td></tr>`).join('') + '</table>';
    h += '<h4>How far trades go for us (best move, pips)</h4>' + tpaBars(r.mfe_hist.counts, r.mfe_hist.edges.slice(0, -1).map((e) => e), 560, 160, '#ffd740');
    h += '<h4>Best move vs result, each trade</h4>' + tpaScatter(r.scatter, 560, 220);
  } else if (r) h += '<p class="note">No trades on these settings.</p>';
  return h + '</div>';
}

// ---- the tuner: every take-profit setting as a slider or a choice; changes stack and the tester re-runs
const TUN = { controls: null, mode1Controls: null, mode2Controls: null, allControls: null, activeMode: null, loading: null, over: {}, res: null, busy: false, err: '', t: 0 };

async function tunLoad() {
  if (TUN.controls && TUN.mode1Controls && TUN.mode2Controls) return;
  if (TUN.loading) return TUN.loading;
  TUN.loading = (async () => {
    try {
      const payload = await api('/api/tplab_controls', {});
      TUN.controls = payload.controls;
      TUN.mode1Controls = payload.mode1_controls;
      TUN.mode2Controls = payload.mode2_controls;
      TUN.allControls = [...TUN.controls, ...TUN.mode1Controls, ...TUN.mode2Controls];
      TUN.err = '';
    } catch (e) {
      TUN.err = 'Could not load the settings list: ' + e.message;
    } finally {
      TUN.loading = null;
    }
  })();
  return TUN.loading;
}

function selectedControls() {
  if (TUN.activeMode === 1) return TUN.mode1Controls || [];
  if (TUN.activeMode === 2) return TUN.mode2Controls || [];
  if (TUN.activeMode === 0) return (TUN.controls || []).filter((control) =>
    control.mode0_only || ['InpFixTpPips', 'InpTp1Be', 'InpSlMode', 'InpSlPips', 'InpSlAtrMult', 'InpSlUsd', 'InpMaxRiskUsd'].includes(control.name));
  return [];
}

function tpInputs() {
  const mode = TPVIEW.selected == null ? CUR.InpExitMode : TPVIEW.selected;
  return { ...CUR, InpExitMode: String(mode) };
}

function tunLabel(name) {
  const control = TUN.allControls && TUN.allControls.find((item) => item.name === name);
  return control ? control.label : name;
}

function tunShow(v, c) {
  if (c.kind === 'enum') return c.options.find((o) => o[0] === v || String(o[0]) === String(v))?.[1] ?? String(v);
  return String(v);
}

// ---- exit mode switch (Dexter style) and what each mode means
function exitMode() {
  return TPVIEW.selected == null ? Number(CUR.InpExitMode || 0) : TPVIEW.selected;
}

// ---- the tuner: one square per group of settings, each with its own sliders, its own result and its own save
const CARD = {};                                    // mode/group -> { over, res, busy, t }
const TPBASE = { res: null, busy: false, key: '', seq: 0 };    // the original settings' result (cached until the settings change)
const M2TUNES = {};
const M2TUNER = { name: '', group: '', busy: false, polling: false, error: '', timer: 0, seq: 0 };

function mode2CardOverrides() {
  const overrides = {};
  for (const [key, card] of Object.entries(CARD)) {
    if (key.startsWith('2:')) Object.assign(overrides, card.over);
  }
  return overrides;
}

function mode2TuneContext(name) {
  const overrides = mode2CardOverrides();
  delete overrides[name];
  return JSON.stringify([CUR, SRC.ds, SRC.mode, overrides]);
}

function mode2TuneHTML(control, group) {
  const tune = M2TUNES[control.name];
  const stale = tune && tune.context !== mode2TuneContext(control.name);
  const running = M2TUNER.busy && M2TUNER.name === control.name;
  let h = `<div style="margin:2px 0 8px 10px;padding:7px;border-left:2px solid #26c6da;background:#07131c">
    <button class="dexbtn sm" onclick="mode2TuneStart('${group}','${control.name}')" ${M2TUNER.busy ? 'disabled' : ''}>
      ${running ? 'Auto-tuning…' : 'Auto-tune this setting'}</button>
    <div class="note" style="margin:4px 0 0">Tests every allowed value for this setting only; other Mode 2 inputs stay fixed. Results are simulator hypotheses.</div>`;
  if (M2TUNER.error && M2TUNER.name === control.name)
    h += `<div class="note bad">${esc(M2TUNER.error)}</div>`;
  if (running) {
    const p = M2TUNES[control.name] || {};
    const pct = p.total ? Math.round(100 * p.done / p.total) : 0;
    h += `<div class="dexprog"><div class="dexprog-t">TESTING VALUE ${p.current == null ? '…' : esc(p.current)} · ${pct}%</div>
      <div class="dexprog-bar"><div style="height:100%;width:${pct}%;background:#00c853;transition:width .3s"></div></div>
      <div class="dexprog-s">${p.done || 0} of ${p.total || '…'} values tested</div></div>`;
  } else if (tune && tune.result) {
    if (stale) h += '<div class="note">Other inputs changed since this scan. Run it again before applying its result.</div>';
    else {
      const result = tune.result, best = result.best, stats = best.stats, base = result.baseline;
      const testedRange = control.kind === 'num'
        ? `${control.min}–${control.max} in ${control.step} steps`
        : `${control.options.length} available choices`;
      const delta = stats.net - base.net;
      h += `<div class="note" style="margin-top:6px">${result.material_effect
        ? `Best of ${result.tested} tested values (${testedRange})`
        : 'No material effect: all tested values returned the same metrics'} · simulator hypothesis</div>
        <div style="font-size:11px;margin:4px 0">Net <b class="${stats.net >= 0 ? 'pos' : 'neg'}">${money(stats.net)}</b> · ${stats.n} trades · WR ${stats.wr ?? '–'}% · PF ${stats.pf ?? '–'}<br>
        Avg win ${stats.avg_win != null ? money(stats.avg_win) : '–'} · Avg loss ${stats.avg_loss != null ? money(stats.avg_loss) : '–'} · vs current ${delta >= 0 ? '+' : ''}${money(delta)}</div>`;
      if (result.material_effect)
        h += `<button class="dexbtn sm" onclick="mode2ApplyTune('${group}','${control.name}')">Apply best tested value: ${esc(tunShow(best.value, control))} for ${money(stats.net)} net</button>`;
    }
  }
  return h + '</div>';
}

let M2TUNE_POLL = 0;

async function mode2TuneStart(group, name) {
  if (M2TUNER.busy) return;
  const controls = selectedControls(), control = controls.find((item) => item.name === name);
  if (!control || TUN.activeMode !== 2) return;
  const context = mode2TuneContext(name);
  const seq = ++M2TUNER.seq;
  M2TUNER.name = name; M2TUNER.group = group; M2TUNER.busy = true; M2TUNER.error = '';
  M2TUNES[name] = { context, running: true, done: 0, total: 0, current: null };
  renderPanel('tt');
  try {
    const started = await api('/api/tplab_tune', {
      inputs: tpInputs(), ds: SRC.ds, mode: SRC.mode, name, overrides: mode2CardOverrides(),
    });
    if (seq !== M2TUNER.seq) return;
    if (!started.ok) throw new Error(started.error || 'The auto-tuner could not start.');
    clearInterval(M2TUNE_POLL);
    M2TUNE_POLL = setInterval(mode2TunePoll, 800);
    await mode2TunePoll();
  } catch (error) {
    if (seq === M2TUNER.seq) {
      M2TUNER.error = error.message || String(error);
      M2TUNER.busy = false;
      M2TUNES[name] = { ...M2TUNES[name], running: false };
      renderPanel('tt');
    }
  }
}

async function mode2TunePoll() {
  if (!M2TUNER.busy || M2TUNER.polling) return;
  M2TUNER.polling = true;
  const seq = M2TUNER.seq, name = M2TUNER.name;
  try {
    const progress = await api('/api/tplab_tune_progress', {});
    if (seq !== M2TUNER.seq) return;
    M2TUNES[name] = { ...progress, context: M2TUNES[name]?.context };
    if (!progress.running) {
      clearInterval(M2TUNE_POLL);
      M2TUNER.busy = false;
      M2TUNER.error = progress.error || '';
    }
  } catch (error) {
    clearInterval(M2TUNE_POLL);
    M2TUNER.busy = false;
    M2TUNER.error = 'Could not read auto-tuner progress: ' + (error.message || error);
  } finally {
    M2TUNER.polling = false;
    if (seq === M2TUNER.seq) renderPanel('tt');
  }
}

function mode2ApplyTune(group, name) {
  const tune = M2TUNES[name], control = selectedControls().find((item) => item.name === name);
  if (!tune || !tune.result || !control || tune.context !== mode2TuneContext(name)) {
    toast('These results are stale. Run the auto-tuner again before applying.');
    return;
  }
  cardSet(group, name, tune.result.best.value, control.kind);
}

function baseLoad() {
  const key = JSON.stringify([tpInputs(), SRC.ds, SRC.mode]);
  if (TPBASE.key === key && (TPBASE.res || TPBASE.busy)) return;
  TPBASE.key = key; TPBASE.res = null; TPBASE.busy = true;
  const seq = ++TPBASE.seq;
  api('/api/tplab_set', { inputs: tpInputs(), ds: SRC.ds, mode: SRC.mode, overrides: {} })
    .then((r) => {
      if (TPBASE.key !== key || TPBASE.seq !== seq) return;
      TPBASE.res = r; TPBASE.busy = false; renderPanel('tt');
    })
    .catch(() => {
      if (TPBASE.key !== key || TPBASE.seq !== seq) return;
      TPBASE.busy = false; TPBASE.key = '';
    });
}
function resSquare(title, st, cls) {
  return `<div class="crt" style="flex:1 1 110px;min-width:0;font-size:11px;padding:6px 8px">
    <div class="crth" style="font-size:10px;margin:0 0 3px">${title}</div>
    ${st ? `<div><b class="${st.net >= 0 ? '' : ''}" style="font-size:13px">${money(st.net)}</b></div>
      <div>${st.n} trades</div><div>win rate <b>${st.wr ?? '–'}%</b></div><div>PF <b>${st.pf ?? '–'}</b></div>` : '<div>…</div>'}
  </div>`;
}
function cardOf(g) { return (CARD[g] = CARD[g] || { over: {}, res: null, busy: false, t: 0 }); }

function tunerHTML() {
  const controls = selectedControls();
  if (!controls.length) {
    if (!TUN.loading) tunLoad().then(() => renderPanel('tt'));
    return `<p class="note">${TUN.err ? esc(TUN.err) : 'Loading this exit style’s settings…'}</p>`;
  }
  const groups = [...new Set(controls.map((control) => control.group))];
  let h = `<div class="crth">TUNE THIS EXIT STYLE</div>
    <p class="note">Change related settings and compare them against this exit style’s current inputs. Simulator output is a hypothesis; MT5 Strategy Tester confirms results.</p>
    ${TUN.err ? `<p class="note bad">${esc(TUN.err)}</p>` : ''}${tpAutoTopHTML(groups)}`;
  h += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;margin-top:10px">';
  for (const g of groups) h += cardHTML(g, controls.filter((control) => control.group === g));
  return h + '</div>';
}

function cardHTML(g, ctrls) {
  const key = `${TUN.activeMode}:${g}`;
  const k = cardOf(key), n = Object.keys(k.over).length;
  let h = `<div class="levers dexpanel" style="border-color:${n ? '#ffd740' : '#26c6da'};padding:10px">
    <div class="crth" style="margin:0 0 6px">${esc(g).toUpperCase()}${n ? ` <span class="tag lab">${n} CHANGED</span>` : ''}</div>`;
  for (const c of ctrls) {
    const raw = c.name in k.over ? k.over[c.name] : CUR[c.name];
    const cur = c.kind === 'enum'
      ? (c.options.find(([value]) => String(value) === String(raw) || String(value) === String(raw).toLowerCase())?.[0] ?? c.vals[0])
      : (Number.isFinite(Number(raw)) ? Number(raw) : c.min);
    const min = c.kind === 'num' ? Math.min(c.min, cur) : c.min;
    const max = c.kind === 'num' ? Math.max(c.max, cur) : c.max;
    if (c.kind === 'num')
      h += `<label class="lever"><span>${esc(c.label)} <b>${cur}</b></span><input type="range" min="${min}" max="${max}" step="${c.step}" value="${cur}" oninput="cardSet('${key}','${c.name}', this.value, 'num')"></label>`;
    else
      h += `<label class="lever"><span>${esc(c.label)}</span><select onchange="cardSet('${key}','${c.name}', this.value, 'enum')" style="background:#03140b;color:#b9f6ca;border:2px solid #37474f;border-radius:8px;font:12px 'Courier New',monospace;padding:3px">${c.options.map(([v, t]) => `<option value="${v}" ${String(v) === String(cur) ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select></label>`;
    if (TUN.activeMode === 2) h += mode2TuneHTML(c, key);
  }
  h += tpAutoCardHTML(g);
  if (k.busy) h += '<div class="dexprog"><div class="dexprog-t">TESTING…</div></div>';
  baseLoad();
  const b = TPBASE.res ? TPBASE.res.stats : null, a = k.res ? k.res.stats : null;
  h += `<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">${resSquare('ORIGINAL SETTINGS', b)}${resSquare('CHANGED SETTINGS', a)}</div>`;
  if (a && b) { const d = a.net - b.net; h += `<div class="note" style="margin:4px 0">this change: <b class="${d >= 0 ? 'pos' : 'neg'}">${d >= 0 ? '+' : ''}${money(d)}</b></div>`; }
  h += `<div class="bar"><button class="dexbtn sm" onclick="cardSave('${key}')" ${n ? '' : 'disabled'}>💾 APPLY &amp; SAVE SETTINGS</button>
    <button class="dexbtn sm" onclick="cardReset('${key}')" ${n ? '' : 'disabled'}>Reset</button></div>`;
  return h + '</div>';
}

function cardSet(g, name, raw, kind) {
  const c = selectedControls().find((x) => x.name === name), k = cardOf(g);
  k.over[name] = kind === 'num' ? Number(raw) : (c.options.find((o) => String(o[0]) === String(raw))?.[0] ?? raw);
  k.busy = true; clearTimeout(k.t); renderPanel('tt');
  k.t = setTimeout(async () => {
    try { k.res = await api('/api/tplab_set', { inputs: tpInputs(), ds: SRC.ds, mode: SRC.mode, overrides: { ...k.over } }); TUN.err = ''; }
    catch (e) { TUN.err = 'The run failed: ' + e.message; }
    k.busy = false; renderPanel('tt');
  }, 350);
}

function cardReset(g) { const k = cardOf(g); k.over = {}; k.res = null; renderPanel('tt'); }

async function cardSave(g) {
  const k = cardOf(g);
  if (!Object.keys(k.over).length) return;
  const over = { ...k.over }; k.over = {}; k.res = null;
  await saveOverrides(g.replace(/^\d+:/, ''), over);
}

async function saveOverrides(title, over) {
  const box = document.createElement('div'); box.id = 'saveBox';
  box.style.cssText = 'position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.55);z-index:999';
  const step = (pct, txt) => { box.innerHTML = `<div class="crt" style="min-width:360px"><div class="crth">💾 SAVING ${esc(title).toUpperCase()}</div><div>${txt}</div><div class="dexprog-bar" style="margin-top:8px"><div style="height:100%;width:${pct}%;background:#ffd740"></div></div></div>`; };
  document.body.appendChild(box); step(10, 'making these the current settings…');
  CUR = { ...CUR, InpExitMode: String(TUN.activeMode), ...Object.fromEntries(Object.entries(over).map(([n, v]) => [n, String(v)])) };
  settingsTouched = true; markForm(); renderPanel('tt');
  step(40, 'running it on the chart…');
  await runSim();
  step(75, 'saving it with its result…');
  try {
    const r = await api('/api/save', { inputs: CUR, ds: SRC.ds, mode: SRC.mode, result: null });
    await loadSaved();
    step(100, `<b>Saved!</b> as ${esc(r.name)} · these are your settings now.`);
  } catch (e) { step(100, `<span class="neg">Could not save: ${esc(e.message)}</span>`); }
  setTimeout(() => box.remove(), 2600);
  renderPanel('tt');
}

// ---- auto-tune: one box, or every box + the best combination (tplab.auto_start). Tester hypotheses; MT5 decides.
const TPAU = { busy: false, group: null, prog: null, groups: {}, stack: null, base: null, key: '', guard: true, err: '', poll: 0 };

function tpAutoKey() { return JSON.stringify([tpInputs(), SRC.ds, SRC.mode]); }

function tpAutoFresh() {
  if (TPAU.key && TPAU.key !== tpAutoKey() && !TPAU.busy) { TPAU.groups = {}; TPAU.stack = null; TPAU.base = null; TPAU.key = ''; }
}

async function tpAutoStart(group) {
  if (TPAU.busy) return;
  const card = group == null ? null : cardOf(`${TUN.activeMode}:${group}`);
  TPAU.busy = true; TPAU.group = group; TPAU.err = ''; TPAU.prog = { done: 0, total: 0, phase: 'starting…', seconds: 0 };
  if (TPAU.key !== tpAutoKey()) { TPAU.groups = {}; TPAU.stack = null; TPAU.base = null; }
  TPAU.key = tpAutoKey();
  if (group == null) TPAU.stack = null;
  renderPanel('tt');
  try {
    const st = await api('/api/tplab_auto', { inputs: tpInputs(), ds: SRC.ds, mode: SRC.mode, group, start: card ? card.over : {}, guard: TPAU.guard });
    if (!st.ok) throw new Error(st.error || 'could not start');
    clearInterval(TPAU.poll); TPAU.poll = setInterval(tpAutoPoll, 900);
  } catch (e) { TPAU.busy = false; TPAU.err = 'Auto-tune failed: ' + e.message; renderPanel('tt'); }
}

async function tpAutoPoll() {
  try {
    const p = await api('/api/tplab_auto_progress', {});
    TPAU.prog = p;
    if (p.base) TPAU.base = p.base;
    Object.assign(TPAU.groups, p.groups || {});
    if (p.stack) TPAU.stack = p.stack;
    if (!p.running) {
      clearInterval(TPAU.poll); TPAU.busy = false;
      if (p.error) TPAU.err = 'Auto-tune failed: ' + p.error;
    }
  } catch (e) { clearInterval(TPAU.poll); TPAU.busy = false; TPAU.err = 'Lost contact with the auto-tune: ' + e.message; }
  renderPanel('tt');
}

async function tpAutoStop() { try { await api('/api/tplab_auto_stop', {}); } catch (e) { /* the poll reports it */ } }

function tpAutoUse(group) {                         // put the box's best values on its sliders (then Apply & Save as usual)
  const r = TPAU.groups[group];
  if (!r || !r.found) return;
  const k = cardOf(`${TUN.activeMode}:${group}`);
  k.over = { ...r.changed };
  k.res = { stats: r.stats };
  renderPanel('tt');
}

function tpAutoWas(c, n) {                          // the original value of a setting, shown the way its control shows it
  if (!c) return CUR[n];
  if (c.kind !== 'enum') return CUR[n];
  const t = String(CUR[n]).toLowerCase(), v = t === 'true' ? '1' : t === 'false' ? '0' : t;
  const o = c.options.find(([x]) => String(x).toLowerCase() === v);
  return o ? o[1] : CUR[n];
}

function tpAutoChanges(changed) {
  const ctrls = selectedControls();
  return Object.entries(changed).map(([n, v]) => {
    const c = ctrls.find((x) => x.name === n);
    return `<div>${esc(c ? c.label : n)}: <span style="color:#90a4ae">${esc(tpAutoWas(c, n) ?? '–')}</span> → <b style="color:#ffd740">${esc(c ? tunShow(v, c) : v)}</b></div>`;
  }).join('');
}

function tpAutoCurve(pts, best) {                   // net across the tested values of one setting; the winner marked
  const ok = pts.filter((p) => p.net != null);
  if (ok.length < 2) return '';
  const W = 210, H = 34, lo = Math.min(...ok.map((p) => p.net)), hi = Math.max(...ok.map((p) => p.net));
  const x = (i) => 3 + (i * (W - 6)) / (ok.length - 1), y = (v) => H - 3 - ((v - lo) / (hi - lo || 1)) * (H - 6);
  const bi = ok.findIndex((p) => String(p.v) === String(best));
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" style="display:block"><polyline fill="none" stroke="#26c6da" stroke-width="1.5" points="${ok.map((p, i) => `${x(i)},${y(p.net)}`).join(' ')}"/>
    ${ok.map((p, i) => p.ok ? '' : `<circle cx="${x(i)}" cy="${y(p.net)}" r="2" fill="#ff5252"/>`).join('')}
    ${bi >= 0 ? `<circle cx="${x(bi)}" cy="${y(ok[bi].net)}" r="3.5" fill="#ffd740"/>` : ''}</svg>`;
}

function tpAutoProgHTML() {
  const p = TPAU.prog || {}, pct = p.total ? Math.min(100, Math.round((100 * p.done) / p.total)) : 0;
  return `<div class="dexprog"><div class="dexprog-t">AUTO-TUNING · ${esc(p.phase || '')} · ${pct}%</div>
    <div class="dexprog-bar"><div style="height:100%;width:${pct}%;background:repeating-linear-gradient(45deg,#ffd740 0 10px,#ffab00 10px 20px);transition:width .4s"></div></div>
    <div class="dexprog-s">${p.done || 0} of ~${p.total || '…'} tester runs · ${p.seconds || 0} s
      <button class="dexbtn sm" style="margin-left:8px" onclick="tpAutoStop()">Stop</button></div></div>`;
}

function tpAutoCardHTML(g) {
  tpAutoFresh();
  const r = TPAU.groups[g], running = TPAU.busy && (TPAU.group === g || (TPAU.group == null && TPAU.prog && TPAU.prog.phase === g));
  let h = `<div style="margin:8px 0 4px;padding:7px;border:1px dashed #ffd740;border-radius:8px;background:#141208">
    <button class="dexbtn sm" onclick="tpAutoStart('${esc(g)}')" ${TPAU.busy ? 'disabled' : ''}>⚡ ${running ? 'Auto-tuning…' : 'Auto-tune this box'}</button>`;
  if (running) h += tpAutoProgHTML();
  else if (r && TPAU.base) {
    const b = TPAU.base, s = r.stats;
    if (!r.found) h += `<div class="note" style="margin:4px 0 0">Tested every setting in this box: <b>nothing beats the current values</b>${TPAU.guard ? ' within the guard' : ''}.</div>`;
    else {
      const d = s.net - b.net;
      h += `<div style="font-size:11px;margin-top:6px"><div class="k" style="font-size:10px">BEST VALUES FOUND</div>${tpAutoChanges(r.changed)}
        <div style="margin-top:4px">net <b>${money(s.net)}</b> <b class="${d >= 0 ? 'pos' : 'neg'}">(${d >= 0 ? '+' : ''}${money(d)})</b> · WR ${s.wr}% · ${s.n} trades · avg win ${money(s.avg_win)} / avg loss ${money(s.avg_loss)} · worst ${money(s.worst)} · DD ${money(s.dd)}</div>
        ${Object.keys(r.changed).map((n) => `<div class="note" style="margin:3px 0 0">${esc((selectedControls().find((x) => x.name === n) || {}).label || tunLabel(n))}: net per value tested (yellow = best, red = fails the guard)</div>${tpAutoCurve((r.curves || {})[n] || [], r.changed[n])}`).join('')}
        <button class="dexbtn sm" style="margin-top:6px" onclick="tpAutoUse('${esc(g)}')">Use these values ↓</button></div>`;
    }
  }
  return h + '</div>';
}

function tpAutoTopHTML(groups) {
  tpAutoFresh();
  const b = TPAU.base, st = TPAU.stack, rows = groups.filter((g) => TPAU.groups[g]);
  let h = `<section class="dexpanel" style="padding:12px;margin:10px 0;border:2px solid #ffd740;background:linear-gradient(145deg,#17140a,#0b1424)">
    <div class="bar" style="justify-content:space-between;align-items:center;flex-wrap:wrap">
      <div><div class="crth" style="font-size:14px;margin:0">⚡ AUTO-TUNE · BEST VALUES FOR THIS EXIT STYLE</div>
        <div class="note" style="margin:2px 0 0">Tunes every box below for the most profit, then stacks the box winners that keep adding profit. Tester hypotheses on ${esc(SRC.ds)}; the MT5 Strategy Tester decides.</div></div>
      <div class="bar" style="align-items:center"><label class="note" style="margin:0" title="Reject any value that adds more than 25% drawdown or a 25% bigger worst loss, cuts trades below a third, or turns a profitable half of the data negative"><input type="checkbox" ${TPAU.guard ? 'checked' : ''} onchange="TPAU.guard=this.checked" ${TPAU.busy ? 'disabled' : ''}> guard: no more risk</label>
        <button class="dexbtn" onclick="tpAutoStart(null)" ${TPAU.busy ? 'disabled' : ''}>⚡ ${TPAU.busy && TPAU.group == null ? 'Tuning all…' : 'Tune all boxes'}</button></div>
    </div>
    ${TPAU.err ? `<p class="note bad">${esc(TPAU.err)}</p>` : ''}${TPAU.busy && TPAU.group == null ? tpAutoProgHTML() : ''}`;
  if (b && (st || rows.length)) {
    const best = st && st.groups.length ? st.stats : null;
    h += `<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">${resSquare('ORIGINAL SETTINGS', b)}${best ? resSquare('BEST COMBINATION', best) : ''}
      ${best ? `<div class="crt" style="flex:2 1 220px;font-size:11px;padding:6px 8px"><div class="crth" style="font-size:10px;margin:0 0 3px">BEST COMBINATION · ${st.groups.map(esc).join(' + ')}</div>
        <div>net <b class="${best.net - b.net >= 0 ? 'pos' : 'neg'}">${best.net - b.net >= 0 ? '+' : ''}${money(best.net - b.net)}</b> · avg win ${money(best.avg_win)} / avg loss ${money(best.avg_loss)} · worst ${money(best.worst)} (was ${money(b.worst)}) · DD ${money(best.dd)} (was ${money(b.dd)})</div>
        ${tpAutoChanges(st.over)}
        <button class="dexbtn sm" style="margin-top:6px" onclick="saveOverrides('best combination', TPAU.stack.over)" ${TPAU.busy ? 'disabled' : ''}>💾 APPLY &amp; SAVE THE BEST COMBINATION</button></div>`
        : st ? `<div class="note">No box beats the original settings${TPAU.guard ? ' within the guard' : ''}.</div>` : ''}</div>`;
    h += '<table style="margin-top:8px;font-size:11px"><tr><th>Box</th><th>Best values</th><th>Net</th><th>vs original</th><th>WR</th><th>Worst</th><th>DD</th><th></th></tr>' +
      rows.map((g) => {
        const r = TPAU.groups[g], s = r.stats, d = s.net - b.net;
        const vals = r.found ? Object.entries(r.changed).map(([n, v]) => { const c = selectedControls().find((x) => x.name === n); return esc(n.replace(/^Inp/, '')) + ' ' + esc(c ? tunShow(v, c) : v); }).join(', ') : '<span class="note">keep current</span>';
        return `<tr${st && st.groups.includes(g) ? ' style="background:#1d3a2a"' : ''}><td>${esc(g)}</td><td>${vals}</td>
          <td>${money(s.net)}</td><td class="${d >= 0 ? 'pos' : 'neg'}">${r.found ? (d >= 0 ? '+' : '') + money(d) : '–'}</td><td>${s.wr}%</td><td>${money(s.worst)}</td><td>${money(s.dd)}</td>
          <td>${r.found ? `<button class="dexbtn sm" onclick="tpAutoUse('${esc(g)}')">Use</button>` : ''}</td></tr>`;
      }).join('') + '</table>';
  }
  return h + '</section>';
}
