// detlab.js - the 🔧 Detector Lab page. Zee 2026-11-08: "we might want to fine-tune/improve our detectors which are handling these kinds of
// fixes/losses/risk.. let's build web pages for each detector that detects this kind of loss and add them to TurtleTVUHV: Ranging -> page describes
// how we currently detect a ranging market -> it pastes screenshots of the failures of ranging we encountered in my labelled setups, with diagrams
// i can fine tune, with labelling options i can label to improve the accuracy of the detector ... The only way forward is to have the ability to
// fix broken detectors so they're not causing a lossy trade!"
// Backend: detlab.py (4 detectors = bundles of the engine's own loss filters). Every number here is a Python TESTER ESTIMATE - a hypothesis until MT5.
var DL = {
  det: 'ranging', file: null, data: null, params: {}, ev: null, est: null, labels: {}, filter: 'all',
  loading: false, loadT0: 0, loadMsg: '', error: null, cards: {}, evalT: null, evalSeq: 0, evalBusy: false,
  fit: { running: false, job: null, phase: '', progress: 0, total: 1, result: null, objective: '', error: null },
  learned: null, learnedBusy: false, propose: { busy: false, text: '' }, asks: {},
  test: { running: false, job: null, phase: '', result: null, error: null }, saving: false, descOpen: true,
  scan: { running: false, job: null, phase: '', progress: 0, total: 1, result: null, error: null },   // Zee 2026-11-08: "Scan for tuned settings" - the auto-tuner
  // Zee 2026-11-08: "Scan for maximizing trades -> a greedy, hungry for trade scanner which tries to include more and more trades with minimal loss of
  // winrate". Backend hungry.py: a greedy path of one-lever moves, each a FULL engine run; tol = win-rate points the path may lose vs the start.
  // tol = win-rate points the path may lose; det = also try the UHV detection inputs (slow: off by default - review 2026-11-08: the first click took
  // 6-11 min with it on); rounds = the greedy steps (server caps 30); greedy = how a round's pick is ranked (hungry.GREEDY). ONE shared result:
  // the hungry scanner is detector-agnostic, so it is NOT stashed per detector (review 2026-11-08: a card click made the result look lost).
  hungry: { running: false, stopping: false, job: null, phase: '', progress: 0, total: 1, result: null, error: null, tol: '0', det: false, rounds: 8, greedy: 'auto', open: {} },
  applied: null,                                               // {trades, losses, wr, per_day, net, from}: the FULL-engine numbers of an applied 🍖 point - the stats card shows them instead of the slider-only estimate
  otherText: {},                                               // {key: the server's change text} for the "other changes" chips (one spelling with the path table: '1 → off')
  byDet: {},                                                   // {det: {params, sliders, fit, test, learned, propose, asks, scan}} - a card click never throws the tuning away
  drafts: {},                                                   // {id: note text being typed} - survives a full re-render (a fit / test finishing)
};
var DL_DETS = [['ranging', '📦', 'Ranging market'], ['sr', '🧱', 'Support / resistance'], ['trend', '🔀', 'Trend shift / against the trend'], ['choppy', '🌊', 'Choppy tape']];
var DL_COL = { ranging: '#f5c542', sr: '#e06c75', trend: '#61afef', choppy: '#56b6c2' };

// ---------- helpers ----------
function dlPk(t) {                                              // Zee's convention: Pakistani time, 12-hour with AM/PM
  const d = new Date((t + 5 * 3600) * 1000); let h = d.getUTCHours(); const m = d.getUTCMinutes(), ap = h >= 12 ? 'PM' : 'AM'; h = h % 12 || 12;
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${h}:${String(m).padStart(2, '0')} ${ap} PKT`;
}
function dlHm(t) { const d = new Date((t + 5 * 3600) * 1000); const h = d.getUTCHours(); return `${h % 12 || 12}:${String(d.getUTCMinutes()).padStart(2, '0')}${h >= 12 ? 'p' : 'a'}`; }
function dlDay(t) { const d = new Date((t + 5 * 3600) * 1000); const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']; return `${d.getUTCDate()} ${MON[d.getUTCMonth()]}`; }
function dlTitle(det) { const x = DL_DETS.find((d) => d[0] === det); return x ? x[2] : det; }
function dlEmoji(det) { const x = DL_DETS.find((d) => d[0] === det); return x ? x[1] : ''; }
function dlFmt(v) { const n = parseFloat(v); if (!isFinite(n)) return String(v); return String(+n.toFixed(4)); }
function dlPct(v) { return v == null || !isFinite(v) ? '–' : (+v).toFixed(2) + '%'; }
function dlJobId(r) { if (!r) return null; if (typeof r.job === 'string' || typeof r.job === 'number') return String(r.job); if (r.job && typeof r.job === 'object') return String(r.job.id ?? r.job.job ?? ''); return r.id != null ? String(r.id) : null; }
function dlJob(j) { return j && j.job && typeof j.job === 'object' ? j.job : j; }
function dlItems() { return DL.data && DL.data.dataset ? DL.data.dataset.items || [] : []; }
function dlVerdict(id) { return (DL.ev && DL.ev.verdicts && DL.ev.verdicts[id]) || { fires: false, why: 'not evaluated yet', overlay: [] }; }
function dlLabel(id) { return (DL.labels && DL.labels[id]) || {}; }
function dlCurVal(p) { return DL.params[p.key] != null ? DL.params[p.key] : p.value; }
function dlChanged() {                                          // every override that differs from the setting: the sliders AND the "other changes" (a hungry path point)
  const d = DL.data && DL.data.describe; if (!d) return {}; const out = {};
  for (const p of d.params) if (DL.params[p.key] != null && !same(DL.params[p.key], p.value)) out[p.key] = DL.params[p.key];
  for (const k of dlOtherKeys()) out[k] = DL.params[k];
  return out;
}
function dlSliderKeys() { const d = DL.data && DL.data.describe; return new Set(d ? (d.params || []).map((p) => p.key) : []); }
function dlBaseVal(k) {                                         // the saved setting's value of ANY input (describe.current for the sliders; the save's inputs, else the EA default)
  const d = DL.data && DL.data.describe; if (d && d.current && d.current[k] != null) return d.current[k];
  const s = (SAVEDS || []).find((x) => x.file === DL.file); if (s && s.inputs && s.inputs[k] != null) return s.inputs[k];
  return typeof DFL !== 'undefined' && DFL[k] != null ? DFL[k] : null;
}
function dlOtherKeys() {                                        // keys in DL.params that are not this detector's sliders (HourFrom, RiskMgr, bands… from an applied hungry point)
  const sk = dlSliderKeys(); return Object.keys(DL.params).filter((k) => !sk.has(k) && !same(DL.params[k], dlBaseVal(k)));
}
const DL_HSTORE = 'dlHungry';                                   // localStorage: the running hunt's job id, so a page reload (the CDP refresh after a server restart) re-attaches instead of losing 5-10 min
function dlHStoreSet(o) { try { if (o) localStorage.setItem(DL_HSTORE, JSON.stringify(o)); else localStorage.removeItem(DL_HSTORE); } catch (e) { /* private window */ } }
function dlHStoreGet() { try { return JSON.parse(localStorage.getItem(DL_HSTORE) || 'null'); } catch (e) { return null; } }
function dlRender() { if (typeof TAB !== 'undefined' && TAB.tt === 'detlab') { dlSaveDrafts(); renderPanel('tt'); } }     // never redraw another tab from a finishing job
function dlResetState(keepCards) {                              // a new setting: nothing tuned, fitted, learned, asked or tested carries over
  DL.params = {}; DL.fit.result = null; DL.fit.error = null; DL.learned = null; DL.propose.text = ''; DL.test.result = null; DL.test.error = null; DL.asks = {}; DL.data = null;
  DL.scan.result = null; DL.scan.error = null; DL.hungry.result = null; DL.hungry.error = null; DL.applied = null; DL.otherText = {};
  if (!keepCards) { DL.cards = {}; DL.byDet = {}; }
}
function dlTuned() { return !!(Object.keys(DL.params).length || DL.fit.result || DL.test.result || DL.propose.text || DL.learned || DL.scan.result || DL.hungry.result); }
function dlJobsRunning() { return DL.fit.running || DL.test.running || DL.scan.running || DL.hungry.running; }
function dlStash() {                                            // the current detector's tuning, kept per detector (review 2026-11-08: a card click wiped it). DL.hungry is NOT stashed: one shared result
  DL.byDet[DL.det] = { params: DL.params, sliders: [...dlSliderKeys()], fit: { ...DL.fit, running: false }, test: { ...DL.test, running: false }, learned: DL.learned, propose: { ...DL.propose, busy: false }, asks: DL.asks,
    scan: { ...DL.scan, running: false } };
}
function dlRestore(det) {
  // the non-slider overrides (an applied 🍖 point's HourFrom / RiskMgr / bands …) travel with the page: visible + savable from ANY detector, as the
  // "Other changes" strip promises (review 2026-11-08: they were stashed with the detector, so S/R showed an empty strip and saved without them).
  // The stash of the detector we return to keeps only ITS sliders - an ✕-dropped other change on this page must not come back from an old stash.
  const carry = {}; for (const k of dlOtherKeys()) carry[k] = DL.params[k];
  const b = DL.byDet[det], own = {};
  if (b) { const sl = new Set(b.sliders || []); for (const [k, v] of Object.entries(b.params || {})) if (!sl.size || sl.has(k)) own[k] = v; }
  DL.params = { ...own, ...carry }; DL.learned = b ? b.learned : null; DL.asks = b ? b.asks || {} : {};
  DL.fit = b ? b.fit : { running: false, job: null, phase: '', progress: 0, total: 1, result: null, objective: '', error: null };
  DL.test = b ? b.test : { running: false, job: null, phase: '', result: null, error: null };
  DL.propose = b ? b.propose : { busy: false, text: '' };
  DL.scan = b && b.scan ? b.scan : { running: false, job: null, phase: '', progress: 0, total: 1, result: null, error: null };
  DL.data = null;
}
function dlSaveDrafts() { document.querySelectorAll('[data-dln]').forEach((el) => { const id = el.dataset.dln, L = dlLabel(id); if (el.value !== (L.note || '')) DL.drafts[id] = el.value; else delete DL.drafts[id]; }); }
function dlDefaultFile() {
  if (DL.file && (SAVEDS || []).find((s) => s.file === DL.file)) return DL.file;
  const pn = typeof primName === 'function' ? primName() : null;
  const prim = pn ? (SAVEDS || []).find((s) => s.name === pn) : null;
  if (prim) return prim.file;
  const fav = (SAVEDS || []).find((s) => s.file === '2026-11-07 12-09-37');        // the setting whose 19 losses Zee labelled
  return fav ? fav.file : ((SAVEDS || [])[0] || {}).file || null;
}
// tp / fp / fn / tn from Zee's labels and the current verdicts (computed here so a fresh label counts at once)
function dlCounts(useGuess) {
  const c = { tp: 0, fp: 0, fn: 0, tn: 0, n: 0 };
  for (const it of dlItems()) {
    const lab = useGuess ? it.zee_says : dlLabel(it.id).label;
    if (lab !== 'yes' && lab !== 'no') continue;
    const f = dlVerdict(it.id).fires; c.n++;
    if (lab === 'yes') { if (f) c.tp++; else c.fn++; } else { if (f) c.fp++; else c.tn++; }
  }
  return c;
}
function dlKind(it) { return it.kind === 'loss' ? `LOSS ${money(it.pnl)}` : it.kind === 'twin' ? `winner twin ${money(it.pnl)}` : `random winner ${money(it.pnl)}`; }
function dlShow(it) {                                           // the gallery filter
  const f = DL.filter, v = dlVerdict(it.id), lab = dlLabel(it.id).label;
  if (f === 'loss') return !it.win;
  if (f === 'win') return !!it.win;
  if (f === 'unl') return lab !== 'yes' && lab !== 'no';
  if (f === 'dis') return (lab === 'yes' && !v.fires) || (lab === 'no' && v.fires) || (!lab && v.fires && it.win) || (!lab && !v.fires && !it.win && it.zee_says === 'yes');
  return true;
}

// ---------- CSS (injected once; the rest of the page's look comes from index.html) ----------
function dlCss() {
  if (document.getElementById('dlCss')) return;
  const s = document.createElement('style'); s.id = 'dlCss';
  s.textContent = `
  .dl h3 { margin: 0 0 6px; } .dl h4 { margin: 12px 0 6px; font-size: 13px; }
  .dl .cards4 { display: grid; grid-template-columns: repeat(4, minmax(170px, 1fr)); gap: 8px; max-width: 1240px; }
  .dl .dcard { background: var(--panel); border: 2px solid transparent; border-radius: 8px; padding: 8px 10px; cursor: pointer; text-align: left; color: var(--text); font: inherit; }
  .dl .dcard.on { border-color: var(--c); } .dl .dcard .t { font-weight: 700; font-size: 13px; } .dl .dcard .b { color: var(--muted); font-size: 11px; margin-top: 3px; line-height: 1.35; }
  .dl .how { background: var(--panel); border-left: 3px solid var(--c); padding: 8px 12px; margin: 8px 0; max-width: 1240px; font-size: 12.5px; }
  .dl .how p { margin: 4px 0; } .dl .how .on { color: var(--win); } .dl .how .off { color: var(--muted); }
  .dl .prow { display: grid; grid-template-columns: 330px 1fr 86px; gap: 10px; align-items: center; padding: 4px 0; border-bottom: 1px solid rgba(42,46,57,.6); max-width: 1240px; }
  .dl .prow .nm { font-size: 12.5px; } .dl .prow .nm small { display: block; color: var(--muted); font-size: 10.5px; }
  .dl .prow.chg .nm { color: var(--warn); } .dl .prow input[type=range] { width: 100%; accent-color: var(--c); } .dl .prow input.num { width: 84px; padding: 2px 6px; }
  .dl .prow select { width: 140px; } .dl .prow .cm { grid-column: 1 / -1; color: var(--muted); font-size: 11px; margin-top: -3px; }
  .dl .stats { display: grid; grid-template-columns: repeat(3, minmax(220px, 1fr)); gap: 8px; max-width: 1240px; margin: 10px 0; }
  .dl .stats .card .v { font-size: 15px; } .dl .stats .card .l { font-size: 11px; }
  .dl .bar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 8px 0; }
  .dl .prog { height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; width: 280px; display: inline-block; vertical-align: middle; } .dl .prog i { display: block; height: 100%; background: var(--c); }
  .dl .fbtn { padding: 3px 10px; } .dl .fbtn.on { background: var(--accent); border-color: var(--accent); color: #fff; }
  .dl .gal { display: grid; grid-template-columns: repeat(auto-fill, minmax(560px, 1fr)); gap: 12px; margin-top: 8px; }
  .dl .item { background: var(--panel); border-radius: 8px; padding: 8px 10px; border-left: 4px solid #444; }
  .dl .item.loss { border-left-color: var(--loss); } .dl .item.win { border-left-color: #2e7d5b; }
  .dl .item canvas { width: 100%; height: auto; background: #12151c; border: 1px solid var(--line); border-radius: 6px; display: block; }
  .dl .ihead { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 12px; margin-bottom: 4px; }
  .dl .kind { font-weight: 700; padding: 1px 7px; border-radius: 8px; font-size: 11px; } .dl .kind.loss { background: rgba(255,82,82,.25); color: #ff8a80; } .dl .kind.win { background: rgba(0,230,118,.15); color: #69f0ae; }
  .dl .vbadge { font-weight: 700; padding: 2px 8px; border-radius: 8px; font-size: 11px; } .dl .vbadge.fires { background: #c62828; color: #fff; } .dl .vbadge.silent { background: #3a3f4b; color: #bbb; }
  .dl .why { color: var(--muted); font-size: 11.5px; margin: 3px 0; white-space: normal; }
  .dl .quote { border-left: 3px solid var(--warn); background: rgba(255,183,77,.08); padding: 4px 8px; margin: 5px 0; font-size: 12px; font-style: italic; }
  .dl .hint { color: var(--muted); font-size: 11px; }
  .dl .lbl button { padding: 3px 10px; } .dl .lbl button.on.yes { background: #2e7d32; border-color: #2e7d32; color: #fff; } .dl .lbl button.on.no { background: #c62828; border-color: #c62828; color: #fff; } .dl .lbl button.on.unsure { background: #5b5f6b; border-color: #5b5f6b; color: #fff; }
  .dl .lbl input { flex: 1; min-width: 160px; }
  .dl .ask { background: #131722; border: 1px solid var(--line); border-radius: 6px; padding: 6px 10px; margin-top: 6px; font-size: 12px; white-space: pre-wrap; max-height: 320px; overflow: auto; }
  .dl .ovn { color: var(--muted); font-size: 11px; margin-top: 3px; }
  .dl table.rank td.l { text-align: left; white-space: normal; max-width: 460px; font-size: 11.5px; }
  .dl .spin { display: inline-block; width: 11px; height: 11px; border: 2px solid var(--muted); border-top-color: var(--text); border-radius: 50%; animation: dlspin .8s linear infinite; vertical-align: middle; }
  .dl .other { background: var(--panel); border-left: 3px solid var(--warn); padding: 6px 10px; margin: 6px 0; max-width: 1240px; font-size: 12px; }
  .dl .other .chip { display: inline-block; background: #131722; border: 1px solid var(--line); border-radius: 10px; padding: 1px 8px; margin: 2px 4px 2px 0; }
  .dl .other .chip button { padding: 0 5px; font-size: 11px; margin-left: 4px; }
  .dl .hopts { display: inline-flex; gap: 6px; align-items: center; font-size: 11.5px; color: var(--muted); } .dl .hopts select { padding: 1px 4px; }
  .dl .hungry table.rank tr.ok { background: rgba(76,175,80,0.12); } .dl .hungry table.rank tr.pick { outline: 1px solid var(--warn); }
  .dl .hungry table.rank tr.step0 td { color: var(--muted); }
  .dl .hungry table.rank tr.err td { color: var(--muted); }
  .dl .hungry canvas { background: #12151c; border: 1px solid var(--line); border-radius: 6px; display: block; cursor: crosshair; }
  .dl .fold { cursor: pointer; user-select: none; } .dl .fold:hover { color: var(--text); }
  @keyframes dlspin { to { transform: rotate(360deg); } }`;
  document.head.appendChild(s);
}

// Zee 2026-11-08: "if i click one of the saved settings -> Load button -> this scanning on detector page should now use that particular loaded
// setting" - app.js calls this after Load; the picker, the charts, the sliders and 🔭 Scan all follow the loaded save.
function detlabFollow(file) {
  if (!file || file === DL.file) return;
  if (dlJobsRunning()) { toast('⏳ the Detector Lab keeps its current setting until the running scan / fit / test finishes'); return; }
  dlResetState(false); DL.file = file;
  if (typeof TAB !== 'undefined' && TAB.tt === 'detlab') detlabLoad(true);   // open now: reload; otherwise the next visit loads this setting
}

// ---------- loading ----------
async function detlabLoad(force) {
  dlCss();
  const file = dlDefaultFile();
  if (!file) { DL.error = 'No saved settings yet - save one on the main page first.'; if (TAB.tt === 'detlab') renderPanel('tt'); return; }
  if (!force && DL.data && DL.file === file && DL.data.describe && DL.data.describe.key === DL.det) { if (TAB.tt === 'detlab') renderPanel('tt'); return; }
  if (DL.file !== file) dlResetState(false);
  DL.file = file; DL.loading = true; DL.loadT0 = Date.now(); DL.error = null; DL.loadMsg = 'Loading the detector…';
  dlRender();
  const det = DL.det, seq = ++DL.evalSeq;
  // the first GET blocks on the server while the engine runs (5-60 s): tick the seconds so Zee sees it is alive
  const tick = setInterval(() => {
    const secs = Math.round((Date.now() - DL.loadT0) / 1000);
    if (secs >= 2) { DL.loadMsg = `Building the dataset (engine run)… ${secs}s`; const m = document.getElementById('dlLoadMsg'); if (m) m.textContent = DL.loadMsg; }
  }, 1000);
  let r = null;
  try {
    for (;;) {                                                  // the first load builds the dataset (an engine run, ~5-60 s): poll / retry up to 3 minutes
      try { r = await api(`/api/detlab?det=${encodeURIComponent(det)}&file=${encodeURIComponent(file)}`); } catch (e) { r = { _net: String(e) }; }
      if (seq !== DL.evalSeq || DL.det !== det) return;          // Zee moved on (another detector / setting) while this one was loading
      if (r && r.describe && r.dataset) break;
      const busy = r && (r.building || r.pending || r.running || /build|engine|running|busy|wait/i.test(String(r.error || r.why || r._net || '')));
      const secs = Math.round((Date.now() - DL.loadT0) / 1000);
      if (r && r.error && !busy) { DL.error = String(r.error); break; }
      if (secs > 180) { DL.error = 'The dataset did not come back in 3 minutes - is the server alive? Try again.'; break; }
      await new Promise((res) => setTimeout(res, 3000));
      if (seq !== DL.evalSeq || DL.det !== det) return;
    }
  } finally { clearInterval(tick); }
  DL.loading = false;
  if (r && r.describe) {
    DL.data = r; DL.labels = r.labels || {}; DL.ev = r.eval || null; DL.est = r.estimate || null;
    DL.cards[det] = { labelled: r.eval && r.eval.labelled, fired: r.eval && r.eval.fired, n: r.eval && r.eval.n, est: r.estimate };
    if (Object.keys(DL.params).length) dlEval(0);              // sliders already moved (e.g. a fit row applied before a reload): re-evaluate with them
    dlOtherCards();
    dlHungryReattach();                                        // a hunt started before a page reload is still running on the server: pick it up
  }
  dlRender();
}
async function dlOtherCards() {                                 // the badges of the other three detectors (fast once the dataset is cached)
  for (const [d] of DL_DETS) {
    if (DL.cards[d] || !DL.file) continue;
    try {
      const r = await api(`/api/detlab?det=${encodeURIComponent(d)}&file=${encodeURIComponent(DL.file)}`);
      if (r && r.eval) DL.cards[d] = { labelled: r.eval.labelled, fired: r.eval.fired, n: r.eval.n, est: r.estimate };
    } catch (e) { /* the badge just stays empty */ }
    const el = document.getElementById('dlCards'); if (el) el.innerHTML = dlCardsHtml();
  }
}
function dlEval(delay) {                                        // the sliders moved: re-evaluate (debounced), redraw verdicts + stats + overlays only
  clearTimeout(DL.evalT);
  DL.evalT = setTimeout(async () => {
    const seq = ++DL.evalSeq, det = DL.det, file = DL.file;
    DL.evalBusy = true; const st = document.getElementById('dlEvalState'); if (st) st.innerHTML = '<span class="spin"></span> evaluating…';
    try {
      const r = await api('/api/detlab/eval', { det, file, params: DL.params });
      if (seq !== DL.evalSeq || DL.det !== det) return;
      if (r && r.error) { toast('⚠ Detector Lab: ' + esc(r.error)); return; }
      DL.ev = r.eval || DL.ev; DL.est = r.estimate || DL.est;
      DL.cards[det] = { labelled: DL.ev && DL.ev.labelled, fired: DL.ev && DL.ev.fired, n: DL.ev && DL.ev.n, est: DL.est };
      dlRefresh();
    } catch (e) { toast('⚠ Detector Lab eval: ' + esc(e.message || e)); }
    finally { DL.evalBusy = false; const s2 = document.getElementById('dlEvalState'); if (s2) s2.innerHTML = ''; }
  }, delay == null ? 300 : delay);
}
function dlResetHtml() {                                        // the "reset N changes" button beside the sliders (refreshed after every slider move)
  const n = Object.keys(dlChanged()).length;
  return n ? `<button data-dl="reset" style="padding:1px 8px;font-size:11px">reset ${n} change${n > 1 ? 's' : ''}</button>` : '';
}
function dlRefresh() {                                          // partial refresh: stats strip, cards, verdict badges, label buttons, overlays, filter, reset button
  const st = document.getElementById('dlStats'); if (st) st.innerHTML = dlStatsHtml();
  const rs = document.getElementById('dlReset'); if (rs) rs.innerHTML = dlResetHtml();
  const ot = document.getElementById('dlOther'); if (ot) ot.innerHTML = dlOtherHtml();
  const cd = document.getElementById('dlCards'); if (cd) cd.innerHTML = dlCardsHtml();
  for (const it of dlItems()) {
    const v = document.getElementById('dlv_' + it.id); if (v) v.innerHTML = dlVerdictHtml(it);
    const l = document.getElementById('dll_' + it.id); if (l) l.innerHTML = dlLabelHtml(it);
    const cv = document.getElementById('dlc_' + it.id); if (cv) dlDraw(cv, it, dlVerdict(it.id));
  }
  dlApplyFilter();
}
function dlApplyFilter() {
  let n = 0;
  for (const it of dlItems()) { const el = document.getElementById('dli_' + it.id); if (!el) continue; const s = dlShow(it); el.style.display = s ? '' : 'none'; if (s) n++; }
  const c = document.getElementById('dlCount'); if (c) c.textContent = `${n} of ${dlItems().length} charts`;
  document.querySelectorAll('.dl .fbtn').forEach((b) => b.classList.toggle('on', b.dataset.dlf === DL.filter));
}

// ---------- render ----------
function pDetlab() {
  dlCss();
  const c = DL_COL[DL.det];
  let h = `<div class="dl" style="--c:${c}"><h3>🔧 Detector Lab - fix the detectors that let a losing trade through</h3>`;
  h += `<p class="note">Four loss detectors, each a bundle of the engine's own filters. Pick a saved setting, pick a detector: the page shows how it detects
    that kind of loss NOW, the charts of the losses it missed (with the detector's drawing on top), and sliders to tune it. Label the charts YES / NO so the
    fitter and the learned model know what you mean, then test the tuned detector in the tester and save it as a setting. Every number on this page is a
    <b>tester estimate</b> (Python engine on PrimeXBT ticks) - a hypothesis until MT5 confirms it.</p>`;
  const opts = (SAVEDS || []).map((s) => `<option value="${esc(s.file)}" ${s.file === DL.file ? 'selected' : ''}>${esc(s.file)} - ${esc(String(s.name || '').slice(0, 100))}</option>`).join('');
  h += `<div class="bar"><b>Setting</b> <select id="dlFile" style="max-width:720px" ${dlJobsRunning() ? 'disabled title="locked while a scan / fit / test runs on this setting"' : ''}>${opts}</select> <button data-dl="reload" title="Reload the dataset">↻</button>`;
  if (DL.data && DL.data.dataset && DL.data.dataset.base) { const b = DL.data.dataset.base; h += `<span class="k">${b.trades} trades · ${b.losses} losses · win rate <b>${dlPct(b.wr)}</b> · ${b.per_day}/day · net ${money(b.net || 0)} <i>(tester estimate)</i></span>`; }
  h += '</div>';
  h += `<div id="dlCards" class="cards4">${dlCardsHtml()}</div>`;
  if (DL.error) h += `<p class="warn">⚠ ${esc(DL.error)} <button data-dl="reload">try again</button></p>`;
  if (DL.loading || (!DL.data && !DL.error)) { if (!DL.loading && !DL.error) detlabLoad(); h += `<p class="note" style="margin-top:14px"><span class="spin"></span> <span id="dlLoadMsg">${esc(DL.loadMsg || 'Loading…')}</span> - the first time a setting is opened the engine runs once (its 3,000 trades, then the charts); after that it is cached.</p></div>`; return h; }
  if (!DL.data) return h + '</div>';
  const D = DL.data.describe, ds = DL.data.dataset;
  // the description
  h += `<h4>${D.emoji} ${esc(D.title)} - how the engine detects it now <button data-dl="desc" style="padding:1px 8px;font-size:11px">${DL.descOpen ? 'hide' : 'show'}</button></h4>`;
  if (DL.descOpen) {
    h += '<div class="how">' + D.how.map((p) => `<p>${esc(p)}</p>`).join('');
    h += `<table style="margin-top:6px"><tr><th>Sub-rule</th><th>State</th><th style="text-align:left">What it checks (with the values of this setting)</th><th style="text-align:left">Engine inputs</th></tr>`;
    for (const r of D.rules) h += `<tr><td>${esc(r.name)}</td><td class="${r.on ? 'on' : 'off'}">${r.on ? 'ON' : 'off'}</td><td style="text-align:left;white-space:normal;max-width:620px">${esc(r.text)}</td><td style="text-align:left" class="k">${r.inputs.map((x) => x.replace(/^Inp/, '')).join(', ')}</td></tr>`;
    h += '</table></div>';
  }
  // the sliders
  const chg = dlChanged();
  h += `<h4>Tune it <span class="k" style="font-weight:400">- the sliders are the engine's inputs; a tuned detector IS a setting</span> <span id="dlEvalState"></span> <span id="dlReset">${dlResetHtml()}</span></h4>`;
  for (const p of D.params) {
    const v = dlCurVal(p), isChg = DL.params[p.key] != null && !same(DL.params[p.key], p.value);
    h += `<div class="prow ${isChg ? 'chg' : ''}" id="dlp_${p.key}"><div class="nm">${esc(p.label)}<small>${esc(p.key)} · setting: ${esc(dlFmt(p.value))}${isChg ? ` → now ${esc(dlFmt(v))}` : ''}</small></div>`;
    if (p.type === 'enum') {
      h += `<div><select data-dlp="${p.key}">${(p.options || []).map((o) => `<option value="${esc(o)}" ${same(o, v) ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select></div><div></div>`;
    } else {
      h += `<div><input type="range" data-dlp="${p.key}" data-dlw="range" min="${p.min}" max="${p.max}" step="${p.step}" value="${esc(dlFmt(v))}"></div>
        <div><input class="num" type="number" data-dlp="${p.key}" data-dlw="num" min="${p.min}" max="${p.max}" step="${p.step}" value="${esc(dlFmt(v))}"></div>`;
    }
    if (p.comment) h += `<div class="cm">${esc(p.comment)}</div>`;
    h += '</div>';
  }
  h += `<div id="dlOther">${dlOtherHtml()}</div>`;             // overrides that are not this detector's sliders (an applied 🍖 path point): visible + savable from any detector page
  // the stats strip
  h += `<div id="dlStats" class="stats">${dlStatsHtml()}</div>`;
  // the buttons
  const busy = DL.fit.running || DL.test.running || DL.saving || DL.scan.running || DL.hungry.running;
  h += `<div class="bar">
    <button data-dl="scan" class="dexbtn sm" ${busy ? 'disabled' : ''} title="The auto-tuner: like the Exit Lab's Scanner - every value of every slider of THIS detector, one at a time, each a FULL engine run; the rows that raise the win rate (or cut losses at the same win rate) are marked as suggestions you can Apply">🔭 Scan ${esc(dlTitle(DL.det))}</button>
    <button data-dl="scan" data-all="1" class="dexbtn sm" ${busy ? 'disabled' : ''} title="The same scan over the inputs of ALL FOUR detectors in one table (a few minutes)">🔭 Scan all four detectors</button>
    <button data-dl="hungry" class="dexbtn sm" ${busy ? 'disabled' : ''} title="Zee: 'a greedy, hungry for trade scanner which tries to include more and more trades with minimal loss of winrate'. Every input that gates how many trades are taken (sessions, spread, setups, risk manager, loss filters, Saad switches, range boxes, entry, UHV detection) is loosened one step at a time, each step a FULL engine run; the step that adds the most trades while the win rate stays within the tolerance is taken, then it hunts again from there. Trade geometry and the fill model never move.">🍖 Scan for maximizing trades</button>
    <span class="hopts" id="dlHOpts">${dlHOptsHtml()}</span>
    <button data-dl="fit" data-obj="labels" class="dexbtn sm" ${busy ? 'disabled' : ''} title="Search the parameter grid for the values that agree best with your YES / NO labels">🎯 Fit to my labels</button>
    <button data-dl="fit" data-obj="losses" class="dexbtn sm" ${busy ? 'disabled' : ''} title="Search for the values that cut the most losses of this setting without cutting winners (tester estimate)">🪓 Fit for fewest losses</button>
    <button data-dl="fit" data-obj="both" class="dexbtn sm" ${busy ? 'disabled' : ''} title="Both at once">⚖️ Both</button>
    <button data-dl="learned" ${DL.learnedBusy ? 'disabled' : ''} title="A tiny logistic model on the labelled charts, leave-one-out accuracy">🧠 Learned model</button>
    <button data-dl="propose" ${DL.propose.busy ? 'disabled' : ''} title="Claude reads every chart's features, your labels and the rules, and proposes a fix (may take minutes)">🤖 Propose a fix</button>
    <button data-dl="test" class="go" ${busy ? 'disabled' : ''} title="Run the FULL engine with these values laid over the setting (the honest tester number)">🧪 Test in tester</button>
    <button data-dl="save" class="primary" ${busy ? 'disabled' : ''} title="Write a new saved setting: this setting's inputs + the detector's values">💾 Save as setting</button></div>`;
  h += `<div id="dlScan">${dlScanHtml()}</div><div id="dlHungry" class="hungry">${dlHungryHtml()}</div><div id="dlFit">${dlFitHtml()}</div><div id="dlLearned">${dlLearnedHtml()}</div><div id="dlPropose">${dlProposeHtml()}</div><div id="dlTest">${dlTestHtml()}</div>`;
  // the gallery
  h += `<h4>The charts <span class="k" style="font-weight:400">- every loss of the setting, two winning twins per loss (same side, nearest in time), 24 random winners. Candles after the entry are faded: the detector never sees them.</span></h4>`;
  h += `<div class="bar">${[['all', 'All'], ['loss', 'Losses'], ['win', 'Winners'], ['dis', 'Disagreements'], ['unl', 'Unlabelled']].map(([k, t]) => `<button class="fbtn ${DL.filter === k ? 'on' : ''}" data-dlf="${k}">${t}</button>`).join('')}
    <span class="k" id="dlCount"></span> <span class="hint">Disagreements = fires but you said NO, silent but you said YES, fires on an unlabelled winner, or silent on a loss your comment calls ${esc(D.title.toLowerCase())}.</span></div>`;
  h += '<div class="gal">';
  for (const it of ds.items) h += dlItemHtml(it);
  h += '</div></div>';
  setTimeout(dlAfterRender, 0);
  return h;
}
function dlAfterRender() {
  for (const it of dlItems()) { const cv = document.getElementById('dlc_' + it.id); if (cv) dlDraw(cv, it, dlVerdict(it.id)); }
  dlApplyFilter(); dlHungryDraw();
}
function dlOtherHtml() {                                        // "other changes": DL.params keys that are not this detector's sliders, each with a ✕
  const ks = dlOtherKeys(); if (!ks.length) return '';
  const txt = (k) => {                                          // the path table's spelling ('1 → off') when the change came from a 🍖 point, else from → to
    const t = DL.otherText && DL.otherText[k]; if (t && same(t.to, DL.params[k])) return `<span class="k">${esc(t.text)}</span>`;
    return `${esc(k.replace(/^Inp(Uhv)?/, ''))} <span class="k">${esc(dlFmt(dlBaseVal(k) == null ? '?' : dlBaseVal(k)))}</span> → <b>${esc(dlFmt(DL.params[k]))}</b>`;
  };
  return `<div class="other"><b>Other changes</b> <span class="k">- inputs of this setting moved by a 🍖 path point or another detector's sliders; they ride along with 🧪 Test and 💾 Save from ANY detector page${DL.applied ? '' : ' (the "Whole setting" estimate below only knows this detector\'s sliders - 🧪 Test gives the full number)'}</span><br>` +
    ks.map((k) => `<span class="chip">${txt(k)}<button data-dl="dropother" data-key="${esc(k)}" title="drop this change">✕</button></span>`).join('') + '</div>';
}
function dlCardsHtml() {
  return DL_DETS.map(([d, e, t]) => {
    const c = DL.cards[d]; let b = 'loading…';
    if (c) {
      const L = c.labelled || {}, n = L.n || 0, acc = n ? Math.round(100 * (L.tp + L.tn) / n) : null;
      b = (n ? `accuracy <b>${acc}%</b> on ${n} label${n > 1 ? 's' : ''} (catches ${L.tp}/${L.tp + L.fn} YES, ${L.fp} false alarm${L.fp === 1 ? '' : 's'})` : 'no labels yet') +
        `<br>fires on ${c.fired ?? '?'} of ${c.n ?? '?'} charts` + (c.est ? `<br>cuts ${c.est.losses_cut}/${c.est.base_losses} losses, ${c.est.winners_cut} winners <i>(est.)</i>` : '');
    } else if (DL.loading && d === DL.det) b = DL.loadMsg || 'loading…';
    return `<button class="dcard ${d === DL.det ? 'on' : ''}" style="--c:${DL_COL[d]}" data-dl="det" data-det="${d}"><div class="t">${e} ${esc(t)}</div><div class="b">${b}</div></button>`;
  }).join('');
}
function dlStatsHtml() {
  const c = dlCounts(false), g = dlCounts(true), e = DL.est, n = dlItems().length, fired = DL.ev ? DL.ev.fired : 0;
  let a = `<div class="card"><div class="l">Your labels (YES = this IS ${esc(dlTitle(DL.det).toLowerCase())})</div>`;
  if (c.n) a += `<div class="v">catches ${c.tp} of ${c.tp + c.fn} YES · false alarms on ${c.fp} of ${c.fp + c.tn} NO</div><div class="l">accuracy ${Math.round(100 * (c.tp + c.tn) / c.n)}% on ${c.n} labelled charts · misses ${c.fn}</div>`;
  else a += `<div class="v">no labels yet</div><div class="l">press YES / NO under the charts - the fitter and the learned model use them</div>`;
  a += '</div>';
  a += `<div class="card"><div class="l">On the ${n} charts · Zee's comment keywords as a guess</div><div class="v">fires on ${fired} of ${n}</div><div class="l">${g.n ? `vs your comments: catches ${g.tp} of ${g.tp + g.fn} that say "${esc(dlTitle(DL.det).toLowerCase())}", ${g.fp} on ones that say no` : 'no comment mentions this detector'}</div></div>`;
  const A = DL.applied, bb = (DL.data && DL.data.dataset && DL.data.dataset.base) || null;
  if (A && dlOtherKeys().length) {                             // an applied 🍖 point: one number for one state on one screen (review 2026-11-08: the card said 976 above a path row saying 1002)
    const dT = bb ? A.trades - bb.trades : null, dW = bb ? A.wr - bb.wr : null, cls = dW > 0.005 ? 'pos' : dW < -0.005 ? 'neg' : '';
    a += `<div class="card"><div class="l">Whole setting · from ${esc(A.from || 'the 🍖 path')} · <b>full engine, tester estimate</b></div><div class="v"><b>${A.trades}</b> trades ${dlHDelta(dT)} · <b>${A.losses}</b> losses ${bb ? dlHDelta(A.losses - bb.losses, 0, true) : ''}</div>
      <div class="l">win rate <b class="${cls}">${dlPct(A.wr)}</b>${bb ? ` (setting ${dlPct(bb.wr)})` : ''} · ${A.per_day}/day · ${money(A.net || 0)} · move a slider or drop a chip and it is an estimate again (press 🧪 Test)</div></div>`;
  } else if (e) {
    const d = e.wr_est - e.wr_base, cls = d > 0.005 ? 'pos' : d < -0.005 ? 'neg' : '';
    a += `<div class="card"><div class="l">Whole setting (${e.trades} trades) · <b>tester estimate</b></div><div class="v">cuts ${e.losses_cut} of ${e.base_losses} losses and ${e.winners_cut} winners</div>
      <div class="l">→ est. win rate <b class="${cls}">${dlPct(e.wr_est)}</b> (base ${dlPct(e.wr_base)}) · ${e.trades_left} trades left${e.per_day_left != null ? ` (${e.per_day_left}/day)` : ''} · an approximation: press 🧪 Test for the full engine</div>
      ${e.loosens && e.loosens.length ? `<div class="l warn">⚠ these values LOOSEN ${esc(e.loosens.join(', '))} (on in this setting): that lets in trades the estimate cannot see - only 🧪 Test knows</div>` : ''}</div>`;
  } else a += '<div class="card"><div class="l">Whole setting</div><div class="v">–</div></div>';
  return a;
}
function dlFitHtml() {
  const f = DL.fit; if (!f.running && !f.result && !f.error) return '';
  let h = '';
  if (f.running) h += `<div class="bar"><span class="spin"></span> Fitting (${esc(f.objective)}): ${esc(f.phase || '…')} <span class="prog"><i style="width:${Math.min(100, 100 * (f.progress || 0) / Math.max(f.total || 1, 1))}%"></i></span> ${f.progress || 0}/${f.total || '?'} evaluations</div>`;
  if (f.error) h += `<p class="warn">⚠ fit: ${esc(f.error)}</p>`;
  const R = f.result; if (!R || !R.ranked) return h;
  const keys = Object.keys((R.ranked[0] || {}).params || {});
  const st = Object.entries(R.start || {});
  h += `<h4>Fit result (${esc(R.objective)}${R.requested && R.requested !== R.objective ? `, you asked for ${esc(R.requested)}` : ''}) <span class="k" style="font-weight:400">- ${R.evaluations} parameter sets tried · labels: ${esc(R.labels_from || '?')} · ${esc(R.note || 'tester estimate')}</span></h4>`;
  h += `<p class="hint">Started from ${st.length ? 'your sliders: ' + st.map(([k, v]) => `${esc(k.replace(/^Inp/, ''))} = <b>${esc(dlFmt(v))}</b>`).join(', ') : 'the saved setting (no slider moved)'}. The "Changes vs the setting" column compares each row with the SAVED setting.</p>`;
  const bb = (DL.data.dataset && DL.data.dataset.base) || {};
  h += `<div class="scroll"><table class="rank"><tr><th>#</th><th style="text-align:left">Changes vs the setting</th><th>Agrees with labels</th><th>tp / fp / fn / tn</th><th>Losses cut</th><th>Winners cut</th><th>Est. win rate</th><th>Score</th><th title="the top ${R.full_checked || 3} rows were run through the FULL engine (base: ${bb.trades} trades · ${bb.losses} losses · ${dlPct(bb.wr)} · ${money(bb.net || 0)})">Full engine run</th><th></th></tr>`;
  R.ranked.forEach((r, i) => {
    const ch = r.changed || Object.fromEntries(keys.filter((k) => !same(r.params[k], (DL.data.describe.current || {})[k])).map((k) => [k, r.params[k]]));
    const diff = Object.entries(ch).map(([k, v]) => `${k.replace(/^Inp/, '')} = <b>${esc(dlFmt(v))}</b>`).join(', ') || '<span class="k">no change</span>';
    const F = r.full, fcls = F && F.losses != null ? (F.losses < bb.losses ? 'pos' : F.losses > bb.losses ? 'neg' : '') : '';
    const full = !F ? '<span class="k">–</span>' : F.error ? `<span class="warn">${esc(F.error)}</span>` : `<span class="${fcls}">${F.trades} trades · <b>${F.losses}</b> losses · ${dlPct(F.wr)} · ${money(F.net || 0)}</span>`;
    h += `<tr><td>${i + 1}</td><td class="l">${diff}</td><td>${r.agree == null ? '–' : Math.round(100 * r.agree) + '%'}</td><td>${r.tp}/${r.fp}/${r.fn}/${r.tn}</td><td>${r.losses_cut} of ${R.base ? R.base.losses : '?'}</td><td>${r.winners_cut}</td><td class="${r.wr_est > r.wr_base ? 'pos' : r.wr_est < r.wr_base ? 'neg' : ''}">${dlPct(r.wr_est)}</td><td>${r.score}</td><td style="white-space:nowrap">${full}</td><td><button data-dl="apply" data-i="${i}" style="padding:1px 8px">Apply</button></td></tr>`;
  });
  h += '</table></div><p class="hint">Only values that make a rule STRICTER than the setting\'s are searched (a looser rule lets in trades the estimate has never seen). The top rows were run through the full engine - the honest tester number; the rest are estimates. Apply sets the sliders to a row; 🧪 Test runs the full engine on it.</p>';
  return h;
}
function dlScanHtml() {                                         // Zee 2026-11-08: the auto-tuner's table - fills while the scan runs (like the Exit Lab's Scanner)
  const s = DL.scan; if (!s.running && !s.result && !s.error) return '';
  let h = '';
  if (s.running) h += `<div class="bar"><span class="spin"></span> Scanning: ${esc(s.phase || '…')} <span class="prog"><i style="width:${Math.min(100, 100 * (s.progress || 0) / Math.max(s.total || 1, 1))}%"></i></span> ${s.progress || 0}/${s.total || '?'} full engine runs</div>`;
  if (s.error) h += `<p class="warn">⚠ scan: ${esc(s.error)}</p>`;
  const R = s.result; if (!R || !R.base) return h;
  const b = R.base, rows = R.rows || [], sug = rows.filter((r) => r.suggest);
  const st = Object.entries(R.start || {});
  h += `<h4>🔭 Scan for tuned settings - ${s.all ? 'all four detectors' : esc(dlTitle(DL.det))} <span class="k" style="font-weight:400">- ${R.evaluations} of ${R.total} values tried${s.running ? ' so far' : ''} · <b class="${sug.length ? 'pos' : ''}">${sug.length} suggestion${sug.length === 1 ? '' : 's'}</b> · ${esc(R.note || '')}</span></h4>`;
  h += `<p class="hint">Start: ${st.length ? 'your sliders (' + st.map(([k, v]) => `${esc(k.replace(/^Inp/, ''))} = <b>${esc(dlFmt(v))}</b>`).join(', ') + ')' : 'the saved setting'} → <b>${b.trades}</b> trades · ${b.per_day}/day · <b>${b.losses}</b> losses · <b>${dlPct(b.wr)}</b> · ${money(b.net || 0)}. Each row changes ONE value; ranked by win rate, then fewer losses, then more trades. <span class="pos">Green rows</span> raise the win rate (or cut losses at the same win rate): press <b>Apply</b> to put that value on the slider, then 💾 Save as setting.</p>`;
  const dd = (x, dec, inv) => { if (x == null) return ''; const g = (inv ? -x : x) > 0 ? 'pos' : (inv ? -x : x) < 0 ? 'neg' : ''; return `<span class="${g}">${x > 0 ? '+' : ''}${dec ? (+x).toFixed(dec) : x}</span>`; };
  // Zee 2026-11-09: "can you make the results table columns sortable" - click a column: descending, again: ascending, a third time: the scan's
  // own rank (win rate → fewer losses → more trades). # stays the scan's rank; Apply keeps the row's real index.
  const SO = s.sort, keyOf = { 1: (r) => `${r.key} ${r.to}`, 2: (r) => r.trades, 3: (r) => r.per_day, 4: (r) => r.losses, 5: (r) => r.wr, 6: (r) => r.net };
  const th = (c, label, left) => { const on = SO && SO.c === c; return `<th ${left ? 'style="text-align:left"' : ''}><span data-dl="scansort" data-c="${c}" style="cursor:pointer;user-select:none" title="sort by ${label} (click again to flip, third click = scan rank)">${label}${on ? (SO.dir === 'asc' ? ' ▲' : ' ▼') : ' <span class="k">⇅</span>'}</span></th>`; };
  let order = rows.map((_, i) => i);
  if (SO && keyOf[SO.c]) order.sort((a, b) => { const x = keyOf[SO.c](rows[a]), y = keyOf[SO.c](rows[b]); if (x == null && y == null) return a - b; if (x == null) return 1; if (y == null) return -1;
    const d = typeof x === 'string' ? x.localeCompare(y) : x - y; return (SO.dir === 'asc' ? d : -d) || a - b; });
  h += `<div class="scroll"><table class="rank"><tr><th>#</th>${th(1, 'Change (one value)', true)}${th(2, 'Trades')}${th(3, '/day')}${th(4, 'Losses')}${th(5, 'Win rate')}${th(6, 'Net')}<th></th></tr>`;
  order.forEach((i) => { const r = rows[i];
    h += `<tr class="${r.suggest ? 'sug' : ''}" style="${r.suggest ? 'background:rgba(76,175,80,0.12)' : ''}"><td>${i + 1}</td><td class="l">${r.suggest ? '✅ ' : ''}${s.all && r.emoji ? r.emoji + ' ' : ''}<b>${esc(r.key.replace(/^Inp/, ''))}</b> ${esc(dlFmt(r.from))} → <b>${esc(dlFmt(r.to))}</b> <span class="k">· ${esc(r.rule)}</span></td>
      <td>${r.trades} ${dd(r.d_trades)}</td><td>${r.per_day}</td><td><b>${r.losses}</b> ${dd(r.d_losses, 0, true)}</td><td><b>${dlPct(r.wr)}</b> ${dd(r.d_wr, 2)}</td><td>${money(r.net || 0)} ${dd(r.d_net, 2)}</td>
      <td><button data-dl="scanapply" data-i="${i}" style="padding:1px 8px">Apply</button></td></tr>`;
  });
  h += '</table></div>';
  if (R.errors && R.errors.length) h += `<p class="warn">${R.errors.length} value(s) failed to run: ${esc(R.errors.map((e) => `${e.key} ${e.to}`).join(', '))}</p>`;
  h += '<p class="hint">Every row is the FULL engine (not an estimate), so looser values are allowed here - the tester sees the trades they let in. One value at a time, like the Exit Lab Scanner; after applying one, scan again from there to stack a second. Tester estimate: a hypothesis until MT5 confirms it.</p>';
  return h;
}
// ---------- 🍖 Scan for maximizing trades (Zee 2026-11-08: "trades more per day at same winrate") ----------
// Backend hungry.py (POST /api/detlab/hungry → job; GET ?job= → {phase, progress, total, done, error, stop, result:{base, start, path, rounds, frontier,
// ceiling, note}}). Every point carries params = the FULL diff vs the saved setting, so Apply / Save need one click. Every number = tester estimate.
var DL_GREEDY = [['auto', 'auto (most trades at 0, cheapest above 0)'], ['most', 'most trades'], ['free', 'no new losses first'], ['cheapest', 'cheapest trades per win-rate point']];
function dlHOptsHtml() {
  const H = DL.hungry, dis = H.running ? 'disabled' : '';
  return `<label title="How many win-rate points (vs the start) the path may lose. 0 = the same win rate">lose at most <select id="dlHTol" ${dis}>${['0', '0.05', '0.1', '0.25', '0.5'].map((t) => `<option value="${t}" ${same(t, H.tol) ? 'selected' : ''}>${t === '0' ? '0 - same win rate' : t + ' pts'}</option>`).join('')}</select></label>
    <label title="Which acceptable move a round takes. most trades = the biggest gain (with a start below 100% it may take +100 trades with one new loss over +10 with none, because the win rate rises); no new losses first = Zee's order (win rate, fewest losses, then trades); cheapest = the most trades per win-rate point spent, so two cheap moves fit a tolerance where one big one would have spent it all. auto = most trades at tolerance 0, cheapest above it">pick <select id="dlHGreedy" ${dis}>${DL_GREEDY.map(([k, t]) => `<option value="${k}" ${k === (H.greedy || 'auto') ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
    <label title="Greedy steps (one lever per step). Stops earlier when no lever adds trades within the tolerance">rounds <select id="dlHRounds" ${dis}>${[4, 8, 16, 30].map((n) => `<option value="${n}" ${n === +(H.rounds || 8) ? 'selected' : ''}>${n}</option>`).join('')}</select></label>
    <label title="The InpDet* detection inputs (CamPiv, humps, pivot, bodies, cooldown) change WHICH setups exist: every value builds a new setups file (1-2 min each, cached afterwards). Off: the fast hunt (~1 min). On: +5-10 min"><input type="checkbox" id="dlHDet" ${H.det ? 'checked' : ''} ${dis}> tick for the deeper hunt (UHV detection settings, +5-10 min - run it once the fast hunt stops)</label>
    ${H.running ? `<button data-dl="hungrystop" ${H.stopping ? 'disabled' : ''} title="Finish the running engine calls, keep the path found so far">${H.stopping ? '⏹ stopping…' : '⏹ Stop'}</button>` : ''}`;
}
function dlHChange(p) {                                         // one point's "change" text: the server's string, or key from → to
  if (!p) return '';
  if (typeof p.change === 'string' && p.change) return esc(p.change);
  const c = p.change && typeof p.change === 'object' ? p.change : p;
  if (c.label && c.key == null) return esc(c.label);
  if (c.key == null) return (p.step === 0 || p.step == null) ? 'the setting' : '?';
  return `<b>${esc(String(c.key).replace(/^Inp/, ''))}</b> ${esc(dlFmt(c.from))} → <b>${esc(dlFmt(c.to))}</b>${c.label ? ` <span class="k">· ${esc(c.label)}</span>` : ''}${c.group ? ` <span class="k">[${esc(c.group)}]</span>` : ''}`;
}
function dlHHalves(p) { const a = p && p.h1, b = p && p.h2; if (!a && !b) return '–'; const f = (x) => x && x.wr != null ? dlPct(x.wr) : '–'; return `<span title="Mar-Jun: ${a ? a.trades + ' trades, ' + a.losses + ' losses' : '?'} · Jul-Nov: ${b ? b.trades + ' trades, ' + b.losses + ' losses' : '?'}">${f(a)} / ${f(b)}</span>`; }
function dlHMwr(v, dT, removed, added) {                       // the TRUE marginal win rate of the trades a move ADDED (hungry.py diffs the two trade lists by entry time); ~ = it also dropped trades
  if (v == null || !isFinite(v) || (added != null && added <= 0) || (added == null && dT != null && dT <= 0)) return '–';
  const w = Math.max(0, Math.min(100, +v)), sw = removed > 0 ? `<span class="k" title="this move also dropped ${removed} of the trades the step before took (a swap, not a superset): the rate is for the ${added != null ? added : '?'} trades it added">~</span>` : '';
  return `${sw}<span class="${w >= 99.995 ? 'pos' : w < 90 ? 'neg' : ''}">${w.toFixed(1)}%</span>`;
}
function dlHDelta(x, dec, inv) { if (x == null || !isFinite(x)) return ''; if (x === 0) return '<span class="k">±0</span>'; const s = inv ? -x : x; const g = s > 0 ? 'pos' : s < 0 ? 'neg' : ''; return `<span class="${g}">${x > 0 ? '+' : ''}${dec ? (+x).toFixed(dec) : Math.round(x)}</span>`; }
function dlHWhy(why) {                                          // the stop reason's advice, by reason (review 2026-11-08: 'try a tolerance' was appended to every outcome)
  const w = String(why || '');
  if (/tolerance/i.test(w)) return ' This setting sits on its win-rate ceiling at this tolerance - try a tolerance above 0, or tick the deeper hunt.';
  if (/no lever left/i.test(w)) return ' Every gate is already at its loosest - only the deeper hunt (detection settings) can find more.';
  if (/rounds done/i.test(w)) return ' Press 🍖 Keep hunting to continue from the last step.';
  return '';
}
function dlHRowPicked(r, i, R) { if (r.picked) return true; const p = R && (R.pick != null ? R.pick : R.picked); if (p == null) return false; /* hungry.py: rounds[i].pick = {key, to, change} */ if (typeof p === 'number') return p === i; if (typeof p === 'object') return p.key === r.key && same(p.to, r.to); return false; }
function dlHungryHtml() {
  const s = DL.hungry; if (!s.running && !s.result && !s.error) return '';
  let h = '';
  const busy = DL.saving || s.running, dis = busy ? 'disabled' : '';
  if (s.running) h += `<div class="bar"><span class="spin"></span> 🍖 Hunting for trades: ${esc(s.phase || 'starting…')} <span class="prog"><i style="width:${Math.min(100, 100 * (s.progress || 0) / Math.max(s.total || 1, 1))}%"></i></span> ${/ of /.test(String(s.phase || '')) ? '' : `${s.progress || 0}/${s.total || '?'} candidates this round`} ${s.stopping ? '<span class="warn">· stopping after the running engine calls</span>' : ''}</div>`;
  if (s.error) h += `<p class="warn">⚠ hungry scan: ${esc(s.error)}</p>`;
  const R = s.result; if (!R || !R.base) return h;
  const B = R.base, path = R.path || [], last = path.length ? path[path.length - 1] : B, days = (R.ceiling && R.ceiling.days) || B.days || (DL.data && DL.data.dataset && DL.data.dataset.base && DL.data.dataset.base.days) || null;   // hungry.run(): days with data = the /day basis
  const st = Object.entries(R.start || {}), O = R.opts || {};
  const rankTxt = { most: 'most trades', free: 'no new losses first', cheapest: 'cheapest trades per win-rate point' }[O.rank] || null;
  h += `<h4>🍖 Scan for maximizing trades <span class="k" style="font-weight:400">- more trades per day at the same win rate (lose at most ${esc(String(O.tol != null ? O.tol : s.tol || '0'))} pts${rankTxt ? `, pick: ${rankTxt}` : ''}${O.max_rounds ? `, ${O.max_rounds} rounds` : ''}${(O.include_det != null ? O.include_det : s.det) ? ', detection settings included' : ''})${s.running ? '' : s.stopped ? ' · <b class="warn">stopped by you</b>' : ' · finished'}</span></h4>
    <p class="hint">${esc(R.note || 'tester estimate')}</p>`;
  // (a) the ceiling: how many setups the data holds, how many the setting takes, what blocks the rest (plain words from hungry.BLOCK_NAMES, not the engine's counter keys)
  const C = R.ceiling || {}; const bl = C.blocked || {}, nm = C.names || {};
  const blTxt = Object.entries(bl).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${esc(nm[k] || (k === 'busy' ? 'busy (one trade at a time)' : k.replace(/_/g, ' ')))} <b>${v}</b>`).join(', ');
  h += `<p class="hint">Ceiling: the data has <b>${C.setups != null ? C.setups.toLocaleString() : '?'}</b> setups${days ? ` over ${days} days with data (the /day basis)` : ''}; the start takes <b>${(C.taken != null ? C.taken : B.trades)}</b> = ${B.per_day}/day${blTxt ? `; blocked by ${blTxt}` : ''}${C.ghosts ? `; ${C.ghosts} stood-aside ghosts (an unticked range box)` : ''}${C.unexplained ? `; ${C.unexplained} unexplained (no tick / no fill within 24 h)` : ''}. Start: ${st.length ? 'your sliders (' + st.map(([k, v]) => `${esc(k.replace(/^Inp/, ''))} = <b>${esc(dlFmt(v))}</b>`).join(', ') + ')' : 'the saved setting'} → <b>${B.trades}</b> trades · <b>${B.losses}</b> losses · <b>${dlPct(B.wr)}</b> · ${money(B.net || 0)}. Trade geometry (stops, targets, RR, latency, lots) never moves - only the gates that decide WHICH setups are taken.</p>`;
  // (b) the path: step 0 = the setting, one row per accepted move
  h += `<div class="scroll"><table class="rank"><tr><th>Step</th><th style="text-align:left">Change (one lever, cumulative)</th><th>Trades</th><th>/day</th><th>Losses</th><th>Win rate</th><th title="win rate Mar-Jun / Jul-Nov">Halves</th><th title="the true marginal win rate of the trades this step added (the two runs' trade lists diffed by entry time); ~ = the step also dropped some trades">Added trades' WR</th><th>Net</th><th></th></tr>`;
  const rows = path.length ? path : [{ step: 0, ...B, params: {} }];
  rows.forEach((p, i) => {
    const prev = i ? rows[i - 1] : null, step = p.step != null ? p.step : i;
    const dT = prev ? p.trades - prev.trades : null, dD = prev ? p.per_day - prev.per_day : null, dL = prev ? p.losses - prev.losses : null, dW = prev ? p.wr - prev.wr : null;
    const wr0 = rows[0].wr, cls = p.wr > wr0 + 0.005 ? 'pos' : p.wr < wr0 - 0.005 ? 'neg' : '';
    h += `<tr class="${i === 0 ? 'step0' : ''}"><td>${step}</td><td class="l">${i === 0 ? '<span class="k">the setting' + (st.length ? ' + your sliders' : '') + '</span>' : dlHChange(p)}</td>
      <td><b>${p.trades}</b> ${dlHDelta(dT)}</td><td>${p.per_day} ${dlHDelta(dD, 2)}</td><td><b>${p.losses}</b> ${dlHDelta(dL, 0, true)}</td><td class="${cls}"><b>${dlPct(p.wr)}</b> ${dlHDelta(dW, 2)}</td><td>${dlHHalves(p)}</td><td>${i === 0 ? '–' : dlHMwr(p.m_wr, dT, p.d_removed, p.d_added)}</td><td>${money(p.net || 0)}</td>
      <td style="white-space:nowrap">${i === 0 ? '' : `<button data-dl="hungryapply" data-i="${i}" ${dis} style="padding:1px 8px" title="Put every change up to this step on the page (sliders + other changes); 🧪 Test re-runs it">Apply up to here</button> <button data-dl="hungrysave" data-i="${i}" ${dis} style="padding:1px 8px" title="Save this step as a new setting">💾 Save</button>`}</td></tr>`;
  });
  h += '</table></div>';
  const why = R.why_stopped || R.stop_reason || '';
  if (!s.running && path.length < 2) {
    const w = why || 'no lever adds trades within the tolerance';
    h += `<p class="hint">${/by you/.test(w) ? `⏹ Stopped by you after ${R.evaluations || 0} engine runs - what was found stays below (round tables, chart).` : `Stopped: ${esc(w)}.${dlHWhy(w)}`}</p>`;
  }
  else if (path.length > 1) h += `<p class="hint">Path so far: <b>${B.trades} → ${last.trades}</b> trades (${B.per_day} → ${last.per_day}/day, ${dlHDelta(last.trades - B.trades)}) at <b>${dlPct(last.wr)}</b> (start ${dlPct(B.wr)}), ${last.losses - B.losses >= 0 ? '+' : ''}${last.losses - B.losses} losses${!s.running && why ? ` · ${/^stopped/i.test(why) ? '' : 'stopped: '}<b>${esc(why)}</b>${esc(dlHWhy(why))}` : ''}${R.secs ? ` · ${Math.round(R.secs)} s, ${R.evaluations || 0} engine runs` : ''}. Each step is the FULL engine (tester estimate); the halves tell you if the extra trades come from one regime only. <b>Apply up to here</b> puts a step's changes on the page, 💾 saves it as a setting - then MT5.${!s.running ? ` <button data-dl="hungrymore" ${dis} style="padding:1px 8px" title="Apply the last step and start a new hunt from there (same tolerance / pick / rounds)">🍖 Keep hunting from step ${last.step != null ? last.step : path.length - 1}</button>` : ''}</p>`;
  // (c) the frontier chart: x = trades/day, y = win rate; grey = every evaluated point, yellow = the path, star = the start; a click applies the nearest point
  h += `<div style="margin:8px 0"><canvas id="dlHungryCv" width="720" height="260"></canvas><div class="hint" id="dlHungryHover">${DL_HHOVER0}</div></div>`;
  // (d) the per-round candidate tables: the running round open (the table fills in sight), the others folded; every row has Apply / 💾 (a frontier point the path did not take is one click, not a re-run)
  (R.rounds || []).forEach((rd, ri) => {
    const r = rd.round != null ? rd.round : ri + 1, rws = rd.rows || [], ok = rws.filter((x) => x.ok).length, isLast = ri === R.rounds.length - 1, nErr = rws.filter((x) => x.error).length;
    const open = s.open[r] != null ? !!s.open[r] : (s.running && isLast);
    const taken = rd.pick != null || rd.picked != null || rws.some((x) => x.picked);
    h += `<h4 class="fold" data-dl="hfold" data-r="${r}">${open ? '▾' : '▸'} Round ${r} <span class="k" style="font-weight:400">- ${rws.length} candidate${rws.length === 1 ? '' : 's'} run, <b class="${ok ? 'pos' : ''}">${ok} within the tolerance</b>${nErr ? `, <span class="warn">${nErr} failed</span>` : ''}${taken ? ' · 🍖 one taken' : s.running && isLast ? ' · running' : ' · none taken'}</span></h4>`;
    if (!open) return;
    h += `<div class="scroll"><table class="rank"><tr><th>#</th><th style="text-align:left">Change (vs the step before)</th><th>Trades</th><th>Δ/day</th><th>Losses</th><th>Win rate</th><th title="the true marginal win rate of the trades this move added; ~ = it also dropped some">Added trades' WR</th><th title="win rate Mar-Jun / Jul-Nov">Halves</th><th>Net</th><th></th></tr>`;
    rws.forEach((x, i) => {
      if (x.error) { h += `<tr class="err"><td>${i + 1}</td><td class="l">${dlHChange(x)}</td><td colspan="8" class="warn" style="text-align:left">⚠ did not run: ${esc(x.error)}</td></tr>`; return; }
      const pk = dlHRowPicked(x, i, rd);
      h += `<tr class="${x.ok ? 'ok' : ''} ${pk ? 'pick' : ''}"><td>${i + 1}</td><td class="l">${pk ? '🍖 ' : x.ok ? '✅ ' : ''}${dlHChange(x)}</td><td>${x.trades} ${dlHDelta(x.d_trades)}</td><td>${dlHDelta(x.d_per_day, 2)}</td><td>${x.losses} ${dlHDelta(x.d_losses, 0, true)}</td><td>${dlPct(x.wr)} ${dlHDelta(x.d_wr, 2)}</td><td>${dlHMwr(x.m_wr, x.d_trades, x.d_removed, x.d_added)}</td><td>${dlHHalves(x)}</td><td>${money(x.net || 0)}</td>
        <td style="white-space:nowrap">${pk ? '<span class="k">on the path</span>' : `<button data-dl="hungryrow" data-r="${ri}" data-i="${i}" ${dis} style="padding:1px 8px" title="Put this candidate (the step before + this one change) on the page">Apply</button> <button data-dl="hungryrowsave" data-r="${ri}" data-i="${i}" ${dis} style="padding:1px 8px" title="Save this candidate as a new setting">💾</button>`}</td></tr>`;
    });
    h += '</table></div>';
  });
  h += `<p class="hint">Greedy: each round every lever is loosened one step from the current point; of the steps that keep the win rate within the tolerance the pick is ${rankTxt ? `<b>${rankTxt}</b>` : 'the most trades'} (the "pick" option: <i>most trades</i> may take +100 trades with one new loss over +10 with none when the start is below 100%, because the win rate rises; <i>no new losses first</i> follows win rate → fewest losses → trades; <i>cheapest</i> buys trades per win-rate point so two cheap moves fit a tolerance one big move would spend). A lever that adds trades at a lower marginal win rate than the setting is the price of volume - the tolerance decides how much of that price to pay. Any row or dot can be applied or saved, not only the path. Tester estimate throughout: a hypothesis until MT5 confirms it.</p>`;
  return h;
}
var DL_HHOVER0 = 'Frontier - every candidate the scan ran (grey), the Pareto frontier (blue), the accepted path (yellow, numbered), the start (★). Hover a dot to read it, click it to apply it to the page.';
var DL_HPTS = [];                                               // the frontier chart's dots in pixels, for the hover legend
function dlHungryDraw() {
  const cv = document.getElementById('dlHungryCv'); const R = DL.hungry.result; if (!cv || !R || !R.base) return;
  const box = cv.parentElement; if (box && box.clientWidth > 100) cv.width = Math.min(1400, Math.max(720, box.clientWidth - 8));   // the panel's width, not a fixed 720
  const x = cv.getContext('2d'), W = cv.width, H = cv.height, L = 58, Rm = 26, T = 14, Bm = 34;
  x.clearRect(0, 0, W, H); DL_HPTS = [];
  const B = R.base, path = R.path && R.path.length ? R.path : [{ step: 0, ...B }];
  const all = []; for (const rd of (R.rounds || [])) for (const r of (rd.rows || [])) if (r.per_day != null && r.wr != null) all.push({ ...r, kind: 'cand', round: rd.round });
  const fr = (R.frontier || []).filter((p) => p.per_day != null && p.wr != null);
  const pts = [...all, ...fr, ...path];
  if (!pts.length) return;
  const tol = parseFloat(DL.hungry.tol || '0') || 0;
  // y: from 3 pts under the start (the tolerance band always in view) to 100. x: the points that matter = those in that y window; a RiskMgr 0→3 at
  // 39 trades/day and 98.4% would otherwise squash the path into a sliver (seen 2026-11-08) - such outliers are clamped at the right edge as ▸
  const yFloor = B.wr - Math.max(3, tol + 1);
  let y0 = Math.max(yFloor, Math.min(...pts.map((p) => p.wr))), y1 = Math.max(...pts.map((p) => p.wr), 100);
  y0 = Math.min(y0, B.wr - Math.max(tol, 0.1) - 0.25);
  const xFloor = B.wr - Math.max(1, tol + 0.5);                 // the x range follows the points near the tolerance band; the rest are clamped at the right edge
  const inY = pts.filter((p) => p.wr >= xFloor - 1e-9), xs = (inY.length ? inY : pts).map((p) => p.per_day);
  let x0 = Math.min(...xs), x1 = Math.max(...xs);
  if (x1 - x0 < 0.2) { x0 -= 0.1; x1 += 0.1; } const padX = (x1 - x0) * 0.06; x0 -= padX; x1 += padX; const padY = (y1 - y0) * 0.08 || 0.1; y0 -= padY; y1 += padY * 1.5;   // headroom above 100% for the step labels
  const xEdge = W - Rm + 10, clamped = (p) => p.per_day > x1 || p.wr < y0;
  const px = (v) => v > x1 ? xEdge : Math.max(L, L + (v - x0) / (x1 - x0) * (W - L - Rm)), py = (v) => Math.min(H - Bm, T + (y1 - v) / (y1 - y0) * (H - T - Bm));
  // axes + grid
  x.strokeStyle = '#2a2e39'; x.fillStyle = '#787b86'; x.font = '10px system-ui, sans-serif'; x.lineWidth = 1;
  const yt = 5; for (let i = 0; i <= yt; i++) { const v = y0 + (y1 - y0) * i / yt, yy = py(v); x.beginPath(); x.moveTo(L, yy); x.lineTo(W - Rm, yy); x.stroke(); x.textAlign = 'right'; x.fillText(v.toFixed(2) + '%', L - 4, yy + 3); }
  const xt = 6; for (let i = 0; i <= xt; i++) { const v = x0 + (x1 - x0) * i / xt, xx = px(v); x.beginPath(); x.moveTo(xx, T); x.lineTo(xx, H - Bm); x.stroke(); x.textAlign = 'center'; x.fillText(v.toFixed(2), xx, H - Bm + 12); }
  x.textAlign = 'center'; x.fillStyle = '#d1d4dc'; x.fillText('trades per day →', (L + W - Rm) / 2, H - 4);
  x.save(); x.translate(11, (T + H - Bm) / 2); x.rotate(-Math.PI / 2); x.fillText('win rate →', 0, 0); x.restore();
  // the tolerance band: win rates the path may accept
  if (tol > 0) { x.fillStyle = 'rgba(255,183,77,0.08)'; x.fillRect(L, py(B.wr), W - L - Rm, py(B.wr - tol) - py(B.wr)); }
  x.strokeStyle = 'rgba(255,183,77,0.5)'; x.setLineDash([3, 3]); x.beginPath(); x.moveTo(L, py(B.wr - tol)); x.lineTo(W - Rm, py(B.wr - tol)); x.stroke(); x.setLineDash([]);
  // every evaluated candidate: grey (green-grey when within the tolerance)
  const tri = (X, Y, col) => { x.fillStyle = col; x.beginPath(); x.moveTo(X - 3, Y - 4); x.lineTo(X + 4, Y); x.lineTo(X - 3, Y + 4); x.closePath(); x.fill(); };   // ▸ = off the chart (right / below)
  let nOut = 0;
  for (const p of all) { const X = px(p.per_day), Y = py(p.wr), col = p.ok ? 'rgba(105,240,174,0.45)' : 'rgba(120,123,134,0.55)'; if (clamped(p)) { nOut++; tri(X, Y, col); } else { x.fillStyle = col; x.beginPath(); x.arc(X, Y, 2.6, 0, Math.PI * 2); x.fill(); } DL_HPTS.push({ X, Y, p, kind: `round ${p.round} candidate${p.ok ? ' (within tolerance)' : ''}${clamped(p) ? ' - off the chart' : ''}` }); }
  if (nOut) { x.fillStyle = '#787b86'; x.font = '10px system-ui, sans-serif'; x.textAlign = 'right'; x.fillText(`▸ ${nOut} far off (many more trades at a much lower win rate) - clamped at the edge, hover to read`, W - Rm, T + 10); }
  // the Pareto frontier: blue, joined
  if (fr.length) {
    const sf = [...fr].sort((a, b) => a.per_day - b.per_day);
    x.strokeStyle = 'rgba(97,175,239,0.7)'; x.lineWidth = 1; x.beginPath(); let pen = false; sf.forEach((p) => { const X = px(p.per_day), Y = py(p.wr); if (clamped(p)) { pen = false; return; } if (pen) x.lineTo(X, Y); else x.moveTo(X, Y); pen = true; }); x.stroke();
    for (const p of sf) { const X = px(p.per_day), Y = py(p.wr); if (clamped(p)) tri(X, Y, '#61afef'); else { x.fillStyle = '#61afef'; x.beginPath(); x.arc(X, Y, 3.2, 0, Math.PI * 2); x.fill(); } DL_HPTS.push({ X, Y, p, kind: 'frontier point' + (clamped(p) ? ' - off the chart' : '') }); }
  }
  // the path: yellow line with step numbers; the start as a star
  x.strokeStyle = '#f5c542'; x.lineWidth = 2; x.beginPath(); path.forEach((p, i) => { const X = px(p.per_day), Y = py(p.wr); if (i) x.lineTo(X, Y); else x.moveTo(X, Y); }); x.stroke();
  path.forEach((p, i) => {
    const X = px(p.per_day), Y = py(p.wr);
    if (i === 0) { x.fillStyle = '#fff'; x.beginPath(); for (let k = 0; k < 10; k++) { const r = k % 2 ? 3 : 7, a = -Math.PI / 2 + k * Math.PI / 5; x.lineTo(X + r * Math.cos(a), Y + r * Math.sin(a)); } x.closePath(); x.fill(); }
    else {
      x.fillStyle = '#f5c542'; x.beginPath(); x.arc(X, Y, 4.5, 0, Math.PI * 2); x.fill();
      // the step number: inside the dot when the steps are apart, else staggered above the dot with a leader (tiny steps pile on the start otherwise)
      const near = path.some((q, j) => j !== i && Math.hypot(px(q.per_day) - X, py(q.wr) - Y) < 14);
      x.font = 'bold 9px system-ui, sans-serif'; x.textAlign = 'center';
      if (!near) { x.fillStyle = '#111'; x.fillText(String(p.step != null ? p.step : i), X, Y + 3.2); }
      else {                                                    // one horizontal row of labels with GREY leaders: a staggered yellow staircase read as the win rate falling (review 2026-11-08)
        const up = Y > T + 30, ly = up ? Y - 12 : Y + 14, lx = X + 8 + 12 * (i - 1);
        x.strokeStyle = '#787b86'; x.lineWidth = 1; x.beginPath(); x.moveTo(X, Y); x.lineTo(lx, ly + (up ? 2 : -2)); x.stroke(); x.fillStyle = '#f5c542'; x.fillText(String(p.step != null ? p.step : i), lx + 3, ly + 3);
      }
    }
    DL_HPTS.push({ X, Y, p, kind: i === 0 ? 'the start (★)' : `path step ${p.step != null ? p.step : i}` });
  });
  // the zoom inset: a +0.1/day path on a 12/day axis is a 1% sliver (review 2026-11-08) - when the path spans < 8% of the x axis, redraw it big on the right
  const pd = path.map((p) => p.per_day), pw = path.map((p) => p.wr);
  if (path.length > 1 && (Math.max(...pd) - Math.min(...pd)) < 0.08 * (x1 - x0)) {
    const iL = L + Math.round((W - L - Rm) * 0.56), iR = W - Rm - 6, iT = T + 18, iB = T + 18 + Math.round((H - T - Bm) * 0.6);
    let ix0 = Math.min(...pd), ix1 = Math.max(...pd); const ipad = Math.max((ix1 - ix0) * 0.25, 0.02); ix0 -= ipad; ix1 += ipad;
    let iy0 = Math.min(...pw, B.wr - Math.max(tol, 0.05)) - 0.03, iy1 = Math.max(...pw) + 0.03;
    const ipx = (v) => iL + 28 + (v - ix0) / (ix1 - ix0) * (iR - iL - 34), ipy = (v) => iT + 10 + (iy1 - v) / (iy1 - iy0) * (iB - iT - 22);
    x.fillStyle = 'rgba(18,21,28,0.94)'; x.fillRect(iL, iT, iR - iL, iB - iT); x.strokeStyle = '#3a3f4b'; x.lineWidth = 1; x.strokeRect(iL, iT, iR - iL, iB - iT);
    x.fillStyle = '#787b86'; x.font = '9px system-ui, sans-serif'; x.textAlign = 'left'; x.fillText('zoom: the path (trades/day → ; win rate ↑)', iL + 4, iT + 9);
    x.textAlign = 'right'; x.fillText(iy1.toFixed(2) + '%', iL + 26, ipy(iy1) + 3); x.fillText(iy0.toFixed(2) + '%', iL + 26, ipy(iy0) + 3);
    x.textAlign = 'center'; x.fillText(ix0.toFixed(2), ipx(ix0), iB - 2); x.fillText(ix1.toFixed(2), ipx(ix1), iB - 2);
    if (tol > 0) { x.fillStyle = 'rgba(255,183,77,0.08)'; x.fillRect(iL + 28, ipy(B.wr), iR - iL - 34, Math.max(0, ipy(Math.max(B.wr - tol, iy0)) - ipy(B.wr))); }
    x.strokeStyle = 'rgba(255,183,77,0.5)'; x.setLineDash([3, 3]); x.beginPath(); x.moveTo(iL + 28, ipy(B.wr)); x.lineTo(iR - 6, ipy(B.wr)); x.stroke(); x.setLineDash([]);
    x.strokeStyle = '#f5c542'; x.lineWidth = 2; x.beginPath(); path.forEach((p, i) => { const X = ipx(p.per_day), Y = ipy(p.wr); if (i) x.lineTo(X, Y); else x.moveTo(X, Y); }); x.stroke();
    path.forEach((p, i) => {
      const X = ipx(p.per_day), Y = ipy(p.wr);
      if (i === 0) { x.fillStyle = '#fff'; x.beginPath(); for (let k = 0; k < 10; k++) { const r = k % 2 ? 3 : 7, a = -Math.PI / 2 + k * Math.PI / 5; x.lineTo(X + r * Math.cos(a), Y + r * Math.sin(a)); } x.closePath(); x.fill(); }
      else { x.fillStyle = '#f5c542'; x.beginPath(); x.arc(X, Y, 6, 0, Math.PI * 2); x.fill(); x.fillStyle = '#111'; x.font = 'bold 9px system-ui, sans-serif'; x.textAlign = 'center'; x.fillText(String(p.step != null ? p.step : i), X, Y + 3.2); }
      DL_HPTS.push({ X, Y, p, kind: (i === 0 ? 'the start (★)' : `path step ${p.step != null ? p.step : i}`) + ' [zoom]' });
    });
  }
  cv.onmousemove = dlHungryHover;                              // bound to the canvas (it is re-created on every render), not the document
  cv.onmouseleave = () => { const el = document.getElementById('dlHungryHover'); if (el) el.textContent = DL_HHOVER0; cv.title = ''; };
  cv.onclick = dlHungryClick;
}
function dlHungryNearest(ev) {
  const cv = ev.target; if (!cv || cv.id !== 'dlHungryCv' || !DL_HPTS.length) return null;
  const rc = cv.getBoundingClientRect(), mx = (ev.clientX - rc.left) * cv.width / rc.width, my = (ev.clientY - rc.top) * cv.height / rc.height;
  let best = null, bd = 14 * 14;
  for (const d of DL_HPTS) { const dd = (d.X - mx) ** 2 + (d.Y - my) ** 2; if (dd < bd) { bd = dd; best = d; } }
  return best;
}
function dlHPointText(best) {
  const p = best.p;
  return `${best.kind}: ${p.change || p.key ? dlHChange(p).replace(/<[^>]+>/g, '') : 'the setting'} → ${p.trades} trades · ${p.per_day}/day · ${p.losses} losses · ${dlPct(p.wr)}${p.m_wr != null && (p.d_added == null ? (p.d_trades == null || p.d_trades > 0) : p.d_added > 0) ? ` · added trades' WR ${p.d_removed > 0 ? '~' : ''}${Math.max(0, Math.min(100, +p.m_wr)).toFixed(1)}%` : ''}${p.net != null ? ` · ${money(p.net)}` : ''} (tester estimate)`;
}
function dlHungryHover(ev) {
  const cv = ev.target, best = dlHungryNearest(ev); const el = document.getElementById('dlHungryHover'); if (!el || !cv) return;
  if (!best) { el.textContent = DL_HHOVER0; cv.title = ''; return; }
  const txt = dlHPointText(best) + (best.p.params ? ' - click to apply' : '');
  el.textContent = txt; cv.title = txt;
}
function dlHungryClick(ev) {                                     // a dot the path did not take is one click away (review 2026-11-08: only path steps had Apply)
  const best = dlHungryNearest(ev); if (!best || !best.p || !best.p.params || DL.saving || DL.hungry.running) return;
  const p = best.p, B = DL.hungry.result && DL.hungry.result.base;
  const off = B && p.wr < B.wr - 0.005 ? ` This dot is OFF the path: ${(B.wr - p.wr).toFixed(2)} pts win rate below the start.` : '';
  if (!confirm(`Apply ${dlHPointText(best)}?${off}\n\nEvery change up to this point goes on the page (sliders + other changes); 🧪 Test re-runs it, 💾 Save keeps it.`)) return;
  dlHungryApplyPoint(p, best.kind.replace(/ \[zoom\]$/, ''));
}

function dlLearnedHtml() {
  const L = DL.learned; if (DL.learnedBusy) return '<div class="bar"><span class="spin"></span> fitting the learned model…</div>'; if (!L) return '';
  let h = `<div class="how"><b>🧠 Learned model</b> ${L.acc_loo != null ? `· leave-one-out accuracy <b>${Math.round(100 * L.acc_loo)}%</b> on ${L.n} labelled charts (majority guess ${L.majority != null ? Math.round(100 * L.majority) + '%' : '–'})` : ''}<p>${esc(L.text || '')}</p>`;
  const co = Object.entries(L.coef || {}); if (co.length) h += `<p class="k">weights: ${co.map(([k, v]) => `${esc(k)} ${v > 0 ? '+' : ''}${v}`).join(' · ')}</p>`;
  return h + '</div>';
}
function dlProposeHtml() { const p = DL.propose; if (p.busy) return '<div class="bar"><span class="spin"></span> Claude is reading the charts, the labels and the rules… (this can take a few minutes)</div>'; return p.text ? `<div class="how"><b>🤖 Claude's proposed fix for ${esc(dlTitle(DL.det))}</b> <span class="k">- a hypothesis: set the sliders, test, then MT5</span><div class="ask">${esc(p.text)}</div></div>` : ''; }
function dlTestHtml() {
  const t = DL.test; if (t.running) return `<div class="bar"><span class="spin"></span> Full engine run: ${esc(t.phase || 'running…')}</div>`;
  if (t.error) return `<p class="warn">⚠ test: ${esc(t.error)}</p>`;
  const r = t.result; if (!r) return '';
  const b = (DL.data.dataset && DL.data.dataset.base) || {};
  const d = (a, c, inv) => { if (a == null || c == null) return ''; const x = a - c; const cls = (inv ? -x : x) > 0 ? 'pos' : (inv ? -x : x) < 0 ? 'neg' : ''; return ` <span class="${cls}">(${x > 0 ? '+' : ''}${+x.toFixed(2)} vs base)</span>`; };
  return `<div class="how"><b>🧪 Full tester run with these values</b> <span class="k">- tester estimate (Python engine); run MT5 before believing it</span>
    <div class="cards" style="margin-top:6px"><div class="card"><div class="v">${r.trades}</div><div class="l">trades${d(r.trades, b.trades)} · ${r.per_day}/day</div></div>
    <div class="card"><div class="v ${r.losses < b.losses ? 'pos' : r.losses > b.losses ? 'neg' : ''}">${r.losses}</div><div class="l">losses${d(r.losses, b.losses, true)}</div></div>
    <div class="card"><div class="v">${dlPct(r.wr)}</div><div class="l">win rate${d(r.wr, b.wr)}</div></div>
    <div class="card"><div class="v">${money(r.net || 0)}</div><div class="l">net${d(r.net, b.net)} · ${r.secs}s</div></div></div></div>`;
}
function dlVerdictHtml(it) {
  const v = dlVerdict(it.id);
  const notes = (v.overlay || []).filter((p) => p.type === 'note' && !(v.why || '').includes(p.text)).map((p) => esc(p.text));
  return `<span class="vbadge ${v.fires ? 'fires' : 'silent'}">${v.fires ? 'FIRES - would skip this trade' : 'silent - would trade'}</span> <span class="why">${esc(v.why || '')}</span>` + (notes.length ? `<div class="ovn">${notes.join(' · ')}</div>` : '');
}
function dlLabelHtml(it) {
  const L = dlLabel(it.id), t = dlTitle(DL.det).toLowerCase();
  return `<button class="yes ${L.label === 'yes' ? 'on' : ''}" data-dll="yes" data-dlid="${it.id}" title="this IS ${esc(t)}">YES, this is ${esc(t)}</button>
    <button class="no ${L.label === 'no' ? 'on' : ''}" data-dll="no" data-dlid="${it.id}" title="this is NOT ${esc(t)}">NO</button>
    <button class="unsure ${L.label === 'unsure' ? 'on' : ''}" data-dll="unsure" data-dlid="${it.id}">unsure</button>
    <input data-dln="${it.id}" value="${esc(DL.drafts[it.id] != null ? DL.drafts[it.id] : (L.note || ''))}" placeholder="note (Enter saves)">${DL.drafts[it.id] != null ? '<span class="hint warn">unsaved - press Enter</span>' : L.saved ? `<span class="hint">saved ${esc(L.saved)}</span>` : ''}`;
}
function dlItemHtml(it) {
  const t = dlTitle(DL.det).toLowerCase(), a = DL.asks[it.id] || {};
  let h = `<div class="item ${it.win ? 'win' : 'loss'}" id="dli_${it.id}"><div class="ihead"><span class="kind ${it.win ? 'win' : 'loss'}">${esc(dlKind(it))}</span>
    <b>${it.side > 0 ? 'BUY' : 'SELL'}</b> <span class="k">${esc(it.id)}</span> <span>${esc(it.when || dlPk(it.t_in))}</span> <span class="k">fill ${(+it.fill).toFixed(5)} · UHV level ${(+it.level).toFixed(5)} · stop ${(+it.stop).toFixed(5)}</span>
    <button data-dl="ask" data-dlid="${it.id}" style="margin-left:auto;padding:2px 8px" ${a.busy ? 'disabled' : ''}>🤖 Ask Claude</button></div>`;
  h += `<canvas id="dlc_${it.id}" width="1120" height="400"></canvas>`;
  h += `<div id="dlv_${it.id}" style="margin-top:5px">${dlVerdictHtml(it)}</div>`;
  if (it.comment) h += `<div class="quote">Zee: "${esc(it.comment)}"</div>`;
  if (it.zee_says) h += `<div class="hint">Zee's comment says: <b>${it.zee_says === 'yes' ? t : 'not ' + t}</b> (keyword guess from the comment - your label below overrides it)</div>`;
  else if (!it.win && !it.comment) h += '<div class="hint">No comment from Zee on this loss yet.</div>';
  h += `<div class="lbl bar" id="dll_${it.id}" style="margin:6px 0 0">${dlLabelHtml(it)}</div>`;
  h += `<div id="dla_${it.id}">${a.busy ? '<div class="bar"><span class="spin"></span> asking Claude (can take a minute or two)…</div>' : a.text ? `<div class="ask">${esc(a.text)}</div>` : ''}</div></div>`;
  return h;
}

// ---------- the chart (candles + volume, like research/trend_labels/index.html, plus the detector's drawing) ----------
function dlDraw(cv, it, vd) {
  const x = cv.getContext('2d'), W = cv.width, H = cv.height, b = it.bars, n = b.o.length, nb = it.n_before || 120, base = it.k - nb + 1;
  const RW = 78, top = 8, vh = 64, bottom = 18, ph = H - vh - bottom - top, PL = (W - RW) / n;
  const ov = (vd && vd.overlay) || [], col = DL_COL[DL.det] || '#ffd54a';
  x.clearRect(0, 0, W, H);
  let lo = Math.min(...b.l, it.level), hi = Math.max(...b.h, it.level);
  const span0 = hi - lo || 1e-4;                                 // overlay levels near the price join the scale; far-away ones are drawn clipped
  const near = (p) => isFinite(p) && p > lo - span0 * 0.6 && p < hi + span0 * 0.6;
  for (const p of ov) {
    if (p.type === 'hline' && near(p.y)) { lo = Math.min(lo, p.y); hi = Math.max(hi, p.y); }
    if (p.type === 'box') { if (near(p.top)) hi = Math.max(hi, p.top); if (near(p.bot)) lo = Math.min(lo, p.bot); }
  }
  const pad = (hi - lo) * 0.08 || 1e-5, mn = lo - pad, mx = hi + pad;
  const y = (p) => top + (mx - p) / (mx - mn) * ph, cx = (i) => i * PL + PL / 2, vm = Math.max(1, ...b.v);
  x.font = '12px sans-serif'; x.textAlign = 'left';
  // every text label goes through label(): it remembers where the others sit and nudges itself up / down until it stands clear (the detector's
  // drawings all crowd the last 45 candles, so without this the box, swing and level names were painted on top of each other)
  const placed = [], LH = 13;
  const label = (txt, X, Y, color, align, font) => {
    if (!txt) return;
    x.font = font || '12px sans-serif';
    const w = x.measureText(txt).width;
    let x0 = align === 'right' ? X - w : align === 'center' ? X - w / 2 : X;
    x0 = Math.max(2, Math.min(W - RW - w - 2, x0));
    const lo2 = top + LH, hi2 = H - bottom - vh - 2;
    const hit = (yy) => yy < lo2 || yy > hi2 || placed.some((r) => x0 < r.x1 + 3 && x0 + w > r.x0 - 3 && yy - LH < r.y1 && yy > r.y0);
    let y0 = Math.max(lo2, Math.min(hi2, Y));
    for (let t = 1; t <= 30 && hit(y0); t++) y0 = Y + Math.ceil(t / 2) * LH * (t % 2 ? 1 : -1);
    if (hit(y0)) y0 = Math.max(lo2, Math.min(hi2, Y));
    placed.push({ x0, x1: x0 + w, y0: y0 - LH, y1: y0 });
    x.fillStyle = color; x.textAlign = 'left'; x.fillText(txt, x0, y0); x.font = '12px sans-serif';
  };
  for (let g = 0; g <= 6; g++) {                                 // grid + prices
    const p = mn + (mx - mn) * g / 6, yy = y(p);
    x.strokeStyle = '#222833'; x.beginPath(); x.moveTo(0, yy); x.lineTo(W - RW, yy); x.stroke();
    x.fillStyle = '#7d8696'; x.fillText(p.toFixed(5), W - RW + 6, yy + 4);
  }
  // the entry line: everything right of it happened AFTER the entry (faded; the detector never sees it)
  const ex = nb * PL;
  x.fillStyle = 'rgba(255,255,255,0.03)'; x.fillRect(ex, 0, W - RW - ex, H - bottom);
  x.strokeStyle = 'rgba(255,213,74,0.35)'; x.setLineDash([3, 3]); x.beginPath(); x.moveTo(ex, 0); x.lineTo(ex, H - bottom); x.stroke(); x.setLineDash([]);
  for (let i = 0; i < n; i++) {                                  // candles + volume
    const c = cx(i), up = b.c[i] >= b.o[i];
    x.globalAlpha = i >= nb ? 0.35 : 1;
    x.strokeStyle = x.fillStyle = up ? '#26a69a' : '#ef5350';
    x.beginPath(); x.moveTo(c, y(b.h[i])); x.lineTo(c, y(b.l[i])); x.stroke();
    const t = y(Math.max(b.o[i], b.c[i])), bt = y(Math.min(b.o[i], b.c[i]));
    x.fillRect(c - PL * 0.35, t, PL * 0.7, Math.max(1, bt - t));
    const vv = b.v[i] / vm * (vh - 6);
    x.globalAlpha = i >= nb ? 0.2 : 0.6; x.fillRect(c - PL * 0.35, H - bottom - vv, PL * 0.7, vv); x.globalAlpha = 1;
    if (i % 20 === 0) { x.fillStyle = '#7d8696'; x.fillText((i === 0 && dlDay(b.t[0]) !== dlDay(b.t[n - 1]) ? dlDay(b.t[0]) + ' ' : '') + dlHm(b.t[i]), c - 14, H - 4); }
  }
  x.fillStyle = '#7d8696'; x.fillText('PKT', W - RW + 6, H - 4);
  x.fillText('ticks', 4, H - bottom - vh + 10);
  // the verdict in the corner, then the entry arrow's text: they take their places first, the detector's drawing goes around them
  if (vd) label(vd.fires ? `${dlEmoji(DL.det)} FIRES` : `${dlEmoji(DL.det)} silent`, 6, 16, vd.fires ? '#ff5252' : '#8b8f98', 'left', 'bold 12px sans-serif');
  // Zee 2026-11-06: an arrow above THIS candle (k, the last closed candle; the entry happens in the next minute)
  const lx = cx(nb - 1), ay = Math.max(46, y(b.h[nb - 1]) - 14);
  x.fillStyle = '#ffd54a'; x.beginPath(); x.moveTo(lx, ay); x.lineTo(lx - 9, ay - 16); x.lineTo(lx + 9, ay - 16); x.closePath(); x.fill();
  x.fillRect(lx - 2, ay - 40, 4, 26);
  label(`THIS candle ${dlHm(b.t[nb - 1])} → ${it.side > 0 ? 'BUY' : 'SELL'} in the next minute`, lx - 14, ay - 26, '#ffd54a', 'right', 'bold 13px sans-serif');
  label('after the entry →', ex + 4, H - vh - bottom - 4, '#7d8696');
  // UHV level (dashed yellow) + the retracement extreme (dotted grey) + the UHV candle tag
  x.strokeStyle = '#ffd54a'; x.setLineDash([6, 4]); x.beginPath(); x.moveTo(0, y(it.level)); x.lineTo(W - RW, y(it.level)); x.stroke(); x.setLineDash([]);
  label(`${it.side > 0 ? 'BUY' : 'SELL'} level ${(+it.level).toFixed(5)}`, 6, y(it.level) - 5, '#ffd54a');
  if (it.extreme != null && it.extreme > mn && it.extreme < mx) {
    x.strokeStyle = 'rgba(170,170,170,0.6)'; x.setLineDash([2, 4]); x.beginPath(); x.moveTo(0, y(it.extreme)); x.lineTo(W - RW, y(it.extreme)); x.stroke(); x.setLineDash([]);
    label('retracement extreme', 6, y(it.extreme) + 12, '#9aa4b2');
  }
  const ui = it.ku != null ? it.ku - base : -1;
  if (ui >= 0 && ui < n) label('UHV', cx(ui), y(b.l[ui]) + 13, 'rgba(255,213,74,0.9)', 'center', 'bold 11px sans-serif');
  // the detector's drawing (every k is absolute: window index = k - base)
  const ix = (k) => k - base, inside = (i) => i >= -0.5 && i <= n - 0.5, clamp = (i) => Math.max(-0.5, Math.min(n - 0.5, i));
  const ylim = (p) => Math.max(top - 2, Math.min(H - bottom - vh + 2, y(p)));
  for (const p of ov) {
    const c = p.color || col;
    if (p.type === 'hline') {
      x.strokeStyle = c; x.setLineDash([8, 4]); x.beginPath(); x.moveTo(0, ylim(p.y)); x.lineTo(W - RW, ylim(p.y)); x.stroke(); x.setLineDash([]);
      label(p.label, W - RW - 6, ylim(p.y) - 4, c, 'right');
    } else if (p.type === 'box') {
      const i0 = ix(p.k0), i1 = ix(p.k1); if (i1 < -0.5 || i0 > n - 0.5) continue;
      const x0 = (clamp(i0) + 0.5) * PL - PL * 0.5, x1 = (clamp(i1) + 0.5) * PL + PL * 0.5, t = ylim(p.top), bt = ylim(p.bot);
      x.fillStyle = c; x.globalAlpha = 0.13; x.fillRect(x0, t, x1 - x0, bt - t); x.globalAlpha = 1;
      x.strokeStyle = c; x.lineWidth = 1.5; x.strokeRect(x0, t, x1 - x0, bt - t); x.lineWidth = 1;
      label(p.label, x0 + 4, t - 4 < top + 14 ? bt + 14 : t - 4, c);
    } else if (p.type === 'line') {
      const pts = (p.pts || []).filter((q) => inside(ix(q[0]))); if (pts.length < 1) continue;
      x.strokeStyle = c; x.lineWidth = 2; x.beginPath(); pts.forEach((q, j) => { const X = cx(ix(q[0])), Y = ylim(q[1]); if (j) x.lineTo(X, Y); else x.moveTo(X, Y); }); x.stroke(); x.lineWidth = 1;
      if (p.label) { const q = pts[pts.length - 1]; label(p.label, cx(ix(q[0])) + 4, ylim(q[1]) - 5, c); }
    } else if (p.type === 'marker') {
      const i = ix(p.k); if (!inside(i)) continue;
      const X = cx(i), Y = ylim(p.y);
      x.fillStyle = c; x.beginPath(); x.arc(X, Y, 4, 0, Math.PI * 2); x.fill();
      label(p.text, X, Y - 8, c, 'center', 'bold 11px sans-serif');
    } else if (p.type === 'vline') {
      const i = ix(p.k); if (!inside(i)) continue;
      x.strokeStyle = c; x.setLineDash([4, 3]); x.beginPath(); x.moveTo(cx(i), top); x.lineTo(cx(i), H - bottom - vh); x.stroke(); x.setLineDash([]);
      label(p.label, cx(i) + 4, top + 24, c);
    }
  }
}

// ---------- actions ----------
async function dlSetLabel(id, label, note) {
  const cur = dlLabel(id);
  if (label == null) label = cur.label || '';
  if (note == null) note = cur.note || '';
  if (!label && !note) delete DL.labels[id]; else DL.labels[id] = { label, note, saved: cur.saved };
  dlRefresh();
  try {
    const r = await api('/api/detlab/label', { det: DL.det, id, label, note });
    if (r && r.error) { toast('⚠ label not saved: ' + esc(r.error)); return; }
    const L = r && r.labels ? r.labels : (r && typeof r === 'object' && !('ok' in r) && !('error' in r) ? r : null);
    if (L && (L[id] || Object.keys(L).length || !label)) DL.labels = L;
    dlRefresh();
  } catch (e) { toast('⚠ label not saved: ' + esc(e.message || e)); }
}
async function dlFitStart(objective) {
  const f = DL.fit; f.running = true; f.objective = objective; f.error = null; f.result = null; f.phase = 'starting'; f.progress = 0; f.total = 1;
  dlJobBox('dlFit', dlFitHtml());
  const t0 = Date.now();
  try {
    const r = await api('/api/detlab/fit', { det: DL.det, file: DL.file, objective, params: DL.params });
    if (r && r.error) throw new Error(r.error);
    const jid = dlJobId(r); const j0 = dlJob(r);
    if (!jid && j0 && j0.done) { dlFitDone(j0); return; }
    if (!jid) throw new Error('no job id in the answer');
    f.job = jid;
    for (;;) {
      await new Promise((res) => setTimeout(res, 1500));
      if (!f.running) return;
      if (Date.now() - t0 > 20 * 60 * 1000) throw new Error('the fit did not finish in 20 minutes - is the server alive?');
      let j; try { j = dlJob(await api('/api/detlab/fit?job=' + encodeURIComponent(jid))); } catch (e) { continue; }
      if (!j) continue;
      f.phase = j.phase || ''; f.progress = j.progress || 0; f.total = j.total || f.total;
      const el = document.getElementById('dlFit'); if (el) el.innerHTML = dlFitHtml();
      if (j.error) throw new Error(j.error);
      if (j.done) { dlFitDone(j); return; }
    }
  } catch (e) { f.running = false; f.error = String(e.message || e); dlJobBox('dlFit', dlFitHtml()); }
}
async function dlScanStart(all) {                                // Zee 2026-11-08: the auto-tuner - a job, polled; the table fills as rows arrive
  const s = DL.scan; s.running = true; s.error = null; s.result = null; s.phase = 'starting (the first run compiles the engine)'; s.progress = 0; s.total = 1; s.all = !!all;
  dlJobBox('dlScan', dlScanHtml());
  const t0 = Date.now();
  try {
    const r = await api('/api/detlab/scan', { det: all ? 'all' : DL.det, file: DL.file, params: DL.params });
    if (r && r.error) throw new Error(r.error);
    const jid = dlJobId(r); if (!jid) throw new Error('no job id in the answer');
    s.job = jid;
    for (;;) {
      await new Promise((res) => setTimeout(res, 2000));
      if (!s.running) return;
      if (Date.now() - t0 > 60 * 60 * 1000) throw new Error('the scan did not finish in an hour - is the server alive?');
      let j; try { j = dlJob(await api('/api/detlab/scan?job=' + encodeURIComponent(jid))); } catch (e) { continue; }
      if (!j) continue;
      s.phase = j.phase || ''; s.progress = j.progress || 0; s.total = j.total || s.total; s.result = j.result || s.result;
      const el = document.getElementById('dlScan'); if (el) el.innerHTML = dlScanHtml();
      if (j.error) throw new Error(j.error);
      if (j.done) {
        s.running = false; s.phase = 'done';
        const n = s.result && s.result.suggestions;
        toast(n ? `🔭 Scan done: ${n} value${n === 1 ? '' : 's'} raise${n === 1 ? 's' : ''} the win rate (tester estimate). Green rows - press Apply.` : '🔭 Scan done: no single value beats the current setting on win rate.');
        dlJobBox('dlScan', dlScanHtml()); return;
      }
    }
  } catch (e) { s.running = false; s.error = String(e.message || e); dlJobBox('dlScan', dlScanHtml()); }
}
function dlScanApply(i) {
  const R = DL.scan.result; if (!R || !R.rows || !R.rows[i]) return;
  const r = R.rows[i], cur = (DL.data.describe && DL.data.describe.current) || {};
  DL.params = {};
  for (const [k, v] of Object.entries(r.params || {})) if (!same(v, cur[k])) DL.params[k] = v;
  toast(`Applied ${esc(r.key.replace(/^Inp/, ''))} = ${esc(dlFmt(r.to))} to the sliders - 💾 Save as setting keeps it, 🔭 Scan again stacks a second value on top.`);
  dlRender(); dlEval(0);
}
// 🍖 the hungry scanner: POST /api/detlab/hungry {det, file, params, tol, include_det, max_rounds} → {job}; GET /api/detlab/hungry?job= every 2 s;
// POST /api/detlab/hungry_stop {job} to stop. The path table, the chart and the round tables fill while it runs.
async function dlHungryStart() {
  const s = DL.hungry;
  const tolEl = document.getElementById('dlHTol'), detEl = document.getElementById('dlHDet'), rEl = document.getElementById('dlHRounds'), gEl = document.getElementById('dlHGreedy');
  if (tolEl) s.tol = tolEl.value; if (detEl) s.det = !!detEl.checked; if (rEl) s.rounds = +rEl.value || 8; if (gEl) s.greedy = gEl.value || 'auto';
  s.running = true; s.stopping = false; s.stopped = false; s.error = null; s.result = null; s.open = {}; s.phase = 'starting (the base run compiles the engine)'; s.progress = 0; s.total = 1; s.job = null;
  dlJobBox('dlHungry', dlHungryHtml());
  const t0 = Date.now();
  try {
    const r = await api('/api/detlab/hungry', { det: DL.det, file: DL.file, params: DL.params, tol: parseFloat(s.tol) || 0, include_det: !!s.det, max_rounds: s.rounds || 8, greedy: s.greedy || 'auto' });
    if (r && r.error) throw new Error(r.error);
    const jid = dlJobId(r); if (!jid) throw new Error('no job id in the answer');
    s.job = jid;
    dlHStoreSet({ job: jid, file: DL.file, det: DL.det, tol: s.tol, det_on: s.det, rounds: s.rounds, greedy: s.greedy, t0 });
    await dlHungryPoll(jid, t0);
  } catch (e) { s.running = false; s.stopping = false; s.error = String(e.message || e); dlHStoreSet(null); dlJobBox('dlHungry', dlHungryHtml()); dlHungryDraw(); }
}
async function dlHungryPoll(jid, t0) {                           // GET ?job= every 2 s until done; shared by a fresh start and a re-attach after a reload
  const s = DL.hungry; let fails = 0;
  try {
    for (;;) {
      await new Promise((res) => setTimeout(res, 2000));
      if (!s.running || s.job !== jid) return;
      if (Date.now() - t0 > 4 * 60 * 60 * 1000) throw new Error('the hungry scan did not finish in 4 hours - is the server alive?');
      let j; try { j = dlJob(await api('/api/detlab/hungry?job=' + encodeURIComponent(jid))); fails = 0; }
      catch (e) { if (++fails >= 10) { const err = new Error('server unreachable for 20 s - the hunt may still be running on the server; reload the page to re-attach'); err.keep = true; throw err; } continue; }
      if (!j) continue;
      if (j.error && /no such job/i.test(String(j.error))) throw new Error('the server no longer has this hunt (was it restarted?) - press 🍖 again');
      s.phase = j.phase || ''; s.progress = j.progress || 0; s.total = j.total || s.total; s.result = j.result || s.result; if (j.stop) s.stopping = true;
      const el = document.getElementById('dlHungry'); if (el) { el.innerHTML = dlHungryHtml(); dlHungryDraw(); }
      if (j.error) throw new Error(j.error);
      if (j.done) {
        s.running = false; s.stopping = false; s.stopped = !!j.stop; s.phase = 'done'; dlHStoreSet(null);
        const R = s.result, path = (R && R.path) || [], B = R && R.base, last = path.length ? path[path.length - 1] : null, why = (R && R.why_stopped) || '';
        if (B && last && path.length > 1) toast(`🍖 Hungry scan ${s.stopped ? 'stopped' : 'done'}: <b>+${last.trades - B.trades} trades</b> (${B.per_day} → ${last.per_day}/day) at <b>${dlPct(last.wr)}</b> (start ${dlPct(B.wr)}), ${last.losses - B.losses >= 0 ? '+' : ''}${last.losses - B.losses} losses, in ${path.length - 1} step${path.length === 2 ? '' : 's'} - tester estimate. Apply a step or 💾 Save it, then MT5.`);
        else if (s.stopped) toast(`⏹ Hungry scan stopped by you after ${(R && R.evaluations) || 0} engine runs - no step was accepted yet; the candidates run so far stay in the round table.`);
        else toast(`🍖 Hungry scan done: ${why ? esc(why) : 'no lever adds trades within the tolerance (' + s.tol + ' pts)'}.${esc(dlHWhy(why || 'tolerance'))}`);
        dlJobBox('dlHungry', dlHungryHtml()); dlHungryDraw(); return;
      }
    }
  } catch (e) { s.running = false; s.stopping = false; s.error = String(e.message || e); if (!e.keep) dlHStoreSet(null); dlJobBox('dlHungry', dlHungryHtml()); dlHungryDraw(); }
}
function dlHungryReattach() {                                    // after a page reload: the hunt started on this setting is still on the server (DETLAB_JOBS keeps the last 50)
  const st = dlHStoreGet(); const s = DL.hungry;
  if (!st || !st.job || s.running) return;
  if (st.file !== DL.file) return;                             // another setting is open: leave the record for its own page
  s.running = true; s.stopping = false; s.stopped = false; s.error = null; s.result = null; s.job = st.job; s.phase = 're-attaching to the hunt that was running before the reload…';
  if (st.tol != null) s.tol = st.tol; if (st.det_on != null) s.det = !!st.det_on; if (st.rounds) s.rounds = st.rounds; if (st.greedy) s.greedy = st.greedy;
  dlJobBox('dlHungry', dlHungryHtml());
  dlHungryPoll(st.job, st.t0 || Date.now());
}
async function dlHungryStop() {
  const s = DL.hungry; if (!s.running || !s.job) return;
  s.stopping = true; dlJobBox('dlHungry', dlHungryHtml());
  try { const r = await api('/api/detlab/hungry_stop', { job: s.job }); if (r && r.error) toast('⚠ stop: ' + esc(r.error)); else toast('⏹ stopping after the running engine calls - the path found so far stays'); }
  catch (e) { toast('⚠ stop: ' + esc(e.message || e)); }
}
function dlHungryPoint(i) { const R = DL.hungry.result; const path = R && R.path; return path && path[i] ? path[i] : null; }
function dlHungryRow(ri, i) { const R = DL.hungry.result; const rd = R && R.rounds && R.rounds[ri]; return rd && rd.rows && rd.rows[i] && !rd.rows[i].error ? rd.rows[i] : null; }
function dlHPointName(p, kind) { return kind || (p.step != null ? `🍖 step ${p.step}` : p.round != null ? `🍖 round ${p.round} candidate` : '🍖 point'); }
function dlHChangeTexts(p) {                                    // {key: {text, to}} for the "other changes" chips: the path steps up to this point, then the point's own change
  const out = {}, R = DL.hungry.result, path = (R && R.path) || [];
  for (const q of path) if (q.key && q.step != null && (p.step == null || q.step <= p.step) && q.change) out[q.key] = { text: q.change, to: q.to };
  if (p.step == null && p.key && p.change) out[p.key] = { text: p.change, to: p.to };
  return out;
}
function dlHungryApplyPoint(p, kind) {                           // any point (path step, round row, chart dot): its params = the FULL diff vs the saved setting
  if (!p) return;
  DL.params = {};
  for (const [k, v] of Object.entries(p.params || {})) if (!same(v, dlBaseVal(k))) DL.params[k] = v;
  DL.otherText = dlHChangeTexts(p);
  const from = dlHPointName(p, kind);
  DL.applied = { trades: p.trades, losses: p.losses, wr: p.wr, per_day: p.per_day, net: p.net, from };
  const n = Object.keys(DL.params).length, B = DL.hungry.result && DL.hungry.result.base;
  const off = B && p.wr < B.wr - 0.005 ? ` <span class="warn">Off the path: −${(B.wr - p.wr).toFixed(2)} pts win rate vs the start.</span>` : '';
  toast(`Applied ${esc(from)}: ${n} change${n === 1 ? '' : 's'} on the page (sliders + "other changes") → ${p.trades} trades · ${dlPct(p.wr)} (tester estimate).${off} 🧪 Test re-runs it, 💾 Save as setting keeps it.`);
  dlRender(); dlEval(0);
}
function dlHungryApply(i) { dlHungryApplyPoint(dlHungryPoint(i), `🍖 step ${i}`); }      // "Apply up to here" on a path row
async function dlHungrySavePoint(p, kind) {
  if (!p) return;
  const base = (DL.data && DL.data.dataset && DL.data.dataset.name) || DL.file, from = dlHPointName(p, kind);
  const name = prompt('Name for the new saved setting', `${base} + hungry ${from.replace(/^🍖 /, '')} (${p.trades} trades)`);
  if (name == null) return;
  DL.saving = true; dlJobBox('dlHungry', dlHungryHtml());
  try {
    const r = await api('/api/detlab/save', { det: DL.det, file: DL.file, params: p.params || {}, name });
    if (r && r.error) throw new Error(r.error);
    toast(`💾 Saved <b>${esc(r.file || name)}</b> - the setting's inputs + ${esc(from)} (${p.trades} trades · ${dlPct(p.wr)} tester estimate). Run it in MT5 for its real result.`);
    if (typeof loadSaved === 'function') await loadSaved();
  } catch (e) { toast('⚠ not saved: ' + esc(e.message || e)); }
  DL.saving = false; dlJobBox('dlHungry', dlHungryHtml()); dlHungryDraw();
}
function dlHungrySave(i) { return dlHungrySavePoint(dlHungryPoint(i), `🍖 step ${i}`); }
function dlHungryMore() {                                        // 🍖 Keep hunting: apply the last step, start again from it (the server starts from DL.params)
  const R = DL.hungry.result, path = (R && R.path) || []; if (path.length < 2 || DL.hungry.running) return;
  dlHungryApplyPoint(path[path.length - 1], `🍖 step ${path[path.length - 1].step != null ? path[path.length - 1].step : path.length - 1}`);
  setTimeout(dlHungryStart, 50);                                // after the render: dlHungryStart reads the option controls
}
function dlJobBox(id, html) {                                    // partial refresh of one job box + the buttons' disabled state
  const el = document.getElementById(id); if (el) el.innerHTML = html;
  const busy = DL.fit.running || DL.test.running || DL.saving || DL.scan.running || DL.hungry.running;
  document.querySelectorAll('.dl [data-dl="fit"], .dl [data-dl="test"], .dl [data-dl="save"], .dl [data-dl="scan"], .dl [data-dl="hungry"], .dl [data-dl="hungryapply"], .dl [data-dl="hungrysave"], .dl [data-dl="hungryrow"], .dl [data-dl="hungryrowsave"], .dl [data-dl="hungrymore"]').forEach((b) => { b.disabled = busy; });
  const fs = document.getElementById('dlFile'); if (fs) fs.disabled = dlJobsRunning();   // the picker is locked while a job runs on this setting
  const ho = document.getElementById('dlHOpts'); if (ho) ho.innerHTML = dlHOptsHtml();     // the tolerance / detection options lock while it runs; ⏹ Stop appears
  if (!el) dlRender();                                          // the box is not on the page (another tab): the full render stays the fallback
}
function dlFitDone(j) {
  const f = DL.fit; f.running = false; f.result = j.result || j; f.phase = 'done';
  if (f.result && f.result.ranked && f.result.ranked.length) toast(`🎯 Fit done: best row cuts ${f.result.ranked[0].losses_cut} losses, ${f.result.ranked[0].winners_cut} winners (tester estimate). Press Apply on a row.`);
  else toast('Fit finished with no rows.');
  dlJobBox('dlFit', dlFitHtml());
}
function dlApply(i) {
  const R = DL.fit.result; if (!R || !R.ranked || !R.ranked[i]) return;
  const r = R.ranked[i], cur = (DL.data.describe && DL.data.describe.current) || {};
  DL.params = {};
  for (const [k, v] of Object.entries(r.params || {})) if (!same(v, cur[k])) DL.params[k] = v;
  dlRender(); dlEval(0);
}
async function dlLearned() {
  DL.learnedBusy = true; const el = document.getElementById('dlLearned'); if (el) el.innerHTML = dlLearnedHtml();
  try {
    const r = await api('/api/detlab/learned', { det: DL.det, file: DL.file, params: DL.params });
    DL.learned = r && r.error ? { text: '⚠ ' + r.error } : (r && r.learned) || r;       // the server answers {learned: {...}, features: {...}}
  }
  catch (e) { DL.learned = { text: '⚠ ' + (e.message || e) }; }
  DL.learnedBusy = false; const e2 = document.getElementById('dlLearned'); if (e2) e2.innerHTML = dlLearnedHtml();
}
async function dlAsk(id) {
  DL.asks[id] = { busy: true, text: '' }; const el = document.getElementById('dla_' + id); if (el) el.innerHTML = '<div class="bar"><span class="spin"></span> asking Claude (can take a minute or two)…</div>';
  const bt = document.querySelector(`[data-dl="ask"][data-dlid="${id}"]`); if (bt) bt.disabled = true;
  try { const r = await api('/api/detlab/ask', { det: DL.det, file: DL.file, id, params: DL.params }); DL.asks[id] = { busy: false, text: r && r.error ? '⚠ ' + r.error : (r && r.text) || '(no answer)' }; }
  catch (e) { DL.asks[id] = { busy: false, text: '⚠ ' + (e.message || e) }; }
  const e2 = document.getElementById('dla_' + id); if (e2) e2.innerHTML = `<div class="ask">${esc(DL.asks[id].text)}</div>`;
  if (bt) bt.disabled = false;
}
async function dlPropose() {
  DL.propose = { busy: true, text: '' }; const el = document.getElementById('dlPropose'); if (el) el.innerHTML = dlProposeHtml();
  try { const r = await api('/api/detlab/propose', { det: DL.det, file: DL.file, params: DL.params }); DL.propose = { busy: false, text: r && r.error ? '⚠ ' + r.error : (r && r.text) || '(no answer)' }; }
  catch (e) { DL.propose = { busy: false, text: '⚠ ' + (e.message || e) }; }
  const e2 = document.getElementById('dlPropose'); if (e2) e2.innerHTML = dlProposeHtml();
}
async function dlTest() {
  const t = DL.test; t.running = true; t.error = null; t.result = null; t.phase = 'running the engine (5-60 s)'; dlJobBox('dlTest', dlTestHtml());
  const t0 = Date.now();
  try {
    const r = await api('/api/detlab/test', { det: DL.det, file: DL.file, params: DL.params });
    if (r && r.error) throw new Error(r.error);
    let j = dlJob(r);
    if (j && j.trades != null && j.wr != null) { t.result = j; }                         // answered straight away
    else if (j && j.result && j.done) { t.result = j.result; }                          // the server waited up to 10 s and the job finished
    else {
      const jid = dlJobId(r); if (!jid) throw new Error('no job id in the answer');
      for (;;) {
        await new Promise((res) => setTimeout(res, 1500));
        if (Date.now() - t0 > 10 * 60 * 1000) throw new Error('the engine run did not finish in 10 minutes - is the server alive?');
        try { j = dlJob(await api('/api/detlab/test?job=' + encodeURIComponent(jid))); } catch (e) { continue; }
        if (!j) continue;
        t.phase = j.phase || t.phase; const el = document.getElementById('dlTest'); if (el) el.innerHTML = dlTestHtml();
        if (j.error) throw new Error(j.error);
        if (j.done) { t.result = j.result || j; break; }
      }
    }
    t.running = false;
    if (t.result) toast(`🧪 Full run: ${t.result.trades} trades, ${t.result.losses} losses, win rate ${dlPct(t.result.wr)}, net ${money(t.result.net || 0)} - tester estimate`);
  } catch (e) { t.running = false; t.error = String(e.message || e); }
  dlJobBox('dlTest', dlTestHtml());
}
async function dlSave() {
  const base = (DL.data.dataset && DL.data.dataset.name) || DL.file;
  const name = prompt('Name for the new saved setting', `${base} + ${dlTitle(DL.det)} fix`);
  if (name == null) return;
  if (!Object.keys(DL.params).length && !confirm('No slider was changed - save a copy of the setting anyway?')) return;
  DL.saving = true; dlRender();
  try {
    const r = await api('/api/detlab/save', { det: DL.det, file: DL.file, params: DL.params, name });
    if (r && r.error) throw new Error(r.error);
    toast(`💾 Saved <b>${esc(r.file || name)}</b> - the setting's inputs with the ${esc(dlTitle(DL.det))} values. Run it in the tester / MT5 for its real result.`);
    if (typeof loadSaved === 'function') await loadSaved();   // app.js: SAVEDS = await api('/api/saved'); renderSaved() - the new file shows in the picker
  } catch (e) { toast('⚠ not saved: ' + esc(e.message || e)); }
  DL.saving = false; dlRender();
}

// ---------- events ----------
document.addEventListener('input', (e) => {
  const k = e.target.dataset && e.target.dataset.dlp; if (!k || !DL.data) return;
  const p = (DL.data.describe.params || []).find((q) => q.key === k); if (!p) return;
  let v = e.target.value;
  if (p.type !== 'enum') { const n = parseFloat(v); if (!isFinite(n)) return; v = String(+n.toFixed(6)); }
  if (same(v, p.value)) delete DL.params[k]; else DL.params[k] = v;          // back at the setting's value = no override
  if (DL.applied) { DL.applied = null; const st = document.getElementById('dlStats'); if (st) st.innerHTML = dlStatsHtml(); }   // the 🍖 point's full-engine numbers no longer describe the page
  const row = document.getElementById('dlp_' + k);
  if (row) {
    row.classList.toggle('chg', DL.params[k] != null);
    row.querySelectorAll('[data-dlp]').forEach((el) => { if (el !== e.target) el.value = v; });
    const sm = row.querySelector('.nm small'); if (sm) sm.textContent = `${k} · setting: ${dlFmt(p.value)}${DL.params[k] != null ? ` → now ${dlFmt(v)}` : ''}`;
  }
  dlEval(300);
});
document.addEventListener('change', (e) => {
  if (e.target.id === 'dlFile') {
    if (e.target.value !== DL.file) {
      // review 2026-11-08: a picker change during a 🍖 run showed setting A's path under setting B, and Apply / Save wrote A's diff onto B
      if (dlJobsRunning()) { toast('⏳ the Detector Lab keeps its setting until the running scan / fit / test finishes'); e.target.value = DL.file; return; }
      dlStash();
      const tuned = Object.values(DL.byDet).some((b) => b && (Object.keys(b.params || {}).length || (b.fit && b.fit.result) || (b.test && b.test.result) || (b.propose && b.propose.text) || (b.scan && b.scan.result))) || !!(DL.hungry && DL.hungry.result);
      if (tuned && !confirm('Another setting: the sliders, fit, test, proposals and the 🍖 / 🔭 scan results you have on this setting will be dropped. Continue?')) { e.target.value = DL.file; return; }
      dlResetState(false); DL.file = e.target.value; detlabLoad(true);
    }
    return;
  }
  if (e.target.id === 'dlHTol') { DL.hungry.tol = e.target.value; return; }                              // 🍖 options: one shared set (DL.hungry is not per detector)
  if (e.target.id === 'dlHDet') { DL.hungry.det = !!e.target.checked; return; }
  if (e.target.id === 'dlHRounds') { DL.hungry.rounds = +e.target.value || 8; return; }
  if (e.target.id === 'dlHGreedy') { DL.hungry.greedy = e.target.value || 'auto'; return; }
  const k = e.target.dataset && e.target.dataset.dlp;
  if (k && e.target.tagName === 'SELECT') e.target.dispatchEvent(new Event('input', { bubbles: true }));
});
document.addEventListener('keydown', (e) => {
  const id = e.target.dataset && e.target.dataset.dln;
  if (id && e.key === 'Enter') { e.preventDefault(); delete DL.drafts[id]; dlSetLabel(id, null, e.target.value); }
});
document.addEventListener('click', async (e) => {
  const lb = e.target.closest('[data-dll]');
  if (lb) { const id = lb.dataset.dlid, lab = lb.dataset.dll, cur = dlLabel(id).label; const inp = document.querySelector(`[data-dln="${id}"]`); dlSetLabel(id, cur === lab ? '' : lab, inp ? inp.value : null); return; }
  const fb = e.target.closest('[data-dlf]');
  if (fb) { DL.filter = fb.dataset.dlf; dlApplyFilter(); return; }
  const b = e.target.closest('[data-dl]'); if (!b) return;
  const a = b.dataset.dl;
  if (a === 'det') {                                                                                        // per-detector tuning + the badges stay
    if (DL.det === b.dataset.det) return;
    if (dlJobsRunning()) { toast('⏳ wait for the running fit / test / scan to finish before switching detector'); return; }
    dlStash(); DL.det = b.dataset.det; dlRestore(DL.det); detlabLoad(true); return;
  }
  if (a === 'reload') { if (dlTuned() && !confirm('Reload drops the sliders, fit, test and proposals of this detector. Continue?')) return; dlResetState(false); detlabLoad(true); return; }
  if (a === 'desc') { DL.descOpen = !DL.descOpen; dlRender(); return; }
  if (a === 'reset') { DL.params = {}; DL.applied = null; DL.otherText = {}; dlRender(); dlEval(0); return; }
  if (a === 'fit') { dlFitStart(b.dataset.obj || 'both'); return; }
  if (a === 'apply') { dlApply(+b.dataset.i); return; }
  if (a === 'scan') { dlScanStart(!!b.dataset.all); return; }
  if (a === 'scanapply') { dlScanApply(+b.dataset.i); return; }
  if (a === 'scansort') { const c = +b.dataset.c, S = DL.scan.sort; DL.scan.sort = !S || S.c !== c ? { c, dir: 'desc' } : S.dir === 'desc' ? { c, dir: 'asc' } : null; dlRender(); return; }
  if (a === 'hungry') { dlHungryStart(); return; }                                                        // 🍖 Scan for maximizing trades
  if (a === 'hungrystop') { dlHungryStop(); return; }
  if (a === 'hungryapply') { dlHungryApply(+b.dataset.i); return; }
  if (a === 'hungrysave') { dlHungrySave(+b.dataset.i); return; }
  if (a === 'hungryrow') { const p = dlHungryRow(+b.dataset.r, +b.dataset.i); if (p) dlHungryApplyPoint(p, `🍖 round ${p.round != null ? p.round : +b.dataset.r + 1} candidate`); return; }
  if (a === 'hungryrowsave') { const p = dlHungryRow(+b.dataset.r, +b.dataset.i); if (p) dlHungrySavePoint(p, `🍖 round ${p.round != null ? p.round : +b.dataset.r + 1} candidate`); return; }
  if (a === 'hungrymore') { dlHungryMore(); return; }
  if (a === 'hfold') { const r = b.dataset.r; const R = DL.hungry.result, rd = (R && R.rounds || []).find((q) => String(q.round) === String(r)), isLast = rd && R.rounds[R.rounds.length - 1] === rd; const cur = DL.hungry.open[r] != null ? !!DL.hungry.open[r] : !!(DL.hungry.running && isLast); DL.hungry.open[r] = !cur; const el = document.getElementById('dlHungry'); if (el) { el.innerHTML = dlHungryHtml(); dlHungryDraw(); } return; }
  if (a === 'dropother') { delete DL.params[b.dataset.key]; DL.applied = null; delete DL.otherText[b.dataset.key]; dlRender(); dlEval(0); return; }   // ✕ on an "other change": the 🍖 point's numbers no longer hold
  if (a === 'learned') { dlLearned(); return; }
  if (a === 'propose') { dlPropose(); return; }
  if (a === 'ask') { dlAsk(b.dataset.dlid); return; }
  if (a === 'test') { dlTest(); return; }
  if (a === 'save') { dlSave(); return; }
});
