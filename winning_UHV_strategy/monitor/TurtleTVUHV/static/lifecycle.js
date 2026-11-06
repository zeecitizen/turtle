// Trade Lifecycle: the tree of every path a trade takes under the settings on the chart (lifecycle.py).
// Before the entry: setups and the filters that reject them. After it: one branch per exit, split into winners and losers.
// ✂ cuts a branch (that exit switched off, test only) and the tester re-runs; every branch carries a forecast of its cut.
let LF_APPLIED = [];                                 // tree cuts applied to the main tester (Overview, List of trades, chart)
const LIFE = { key: '', res: null, busy: false, err: '', pruned: [], sel: null, seq: 0 };

function lfCss() {
  if (document.getElementById('lfCss')) return;
  const s = document.createElement('style'); s.id = 'lfCss';
  s.textContent = `
  .lf-wrap{background:radial-gradient(ellipse at 40% 30%,#06243a 0%,#020a14 60%,#01050b 100%);border:1px solid #0f3b55;border-radius:14px;padding:14px;color:#cfefff;font-family:'Consolas','Courier New',monospace;box-shadow:inset 0 0 60px #00e5ff14,0 0 24px #00e5ff10}
  .lf-h{font-size:15px;letter-spacing:3px;color:#7ff6ff;text-shadow:0 0 8px #00e5ff}
  .lf-sub{font-size:11px;color:#6fa5bd}
  .lf-hud{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
  .lf-cell{flex:1 1 120px;border:1px solid #12506e;background:linear-gradient(180deg,#04192a,#020d18);border-radius:8px;padding:6px 9px;position:relative;overflow:hidden}
  .lf-cell:before{content:'';position:absolute;left:0;top:0;width:3px;height:100%;background:#00e5ff;box-shadow:0 0 8px #00e5ff}
  .lf-k{font-size:9px;letter-spacing:2px;color:#5f9db8}
  .lf-v{font-size:16px;font-weight:bold;color:#e8fbff}
  .lf-d{font-size:10px}
  .lf-pos{color:#4dffb0;text-shadow:0 0 6px #00ff9555}.lf-neg{color:#ff5c7a;text-shadow:0 0 6px #ff1f4f55}
  .lf-svg{width:100%;display:block}
  .lf-flow{stroke-dasharray:3 11;animation:lfdash 1.1s linear infinite}
  .lf-flow.slow{animation-duration:2.4s}
  @keyframes lfdash{to{stroke-dashoffset:-28}}
  @keyframes lfpulse{0%{r:34;opacity:.9}100%{r:62;opacity:0}}
  .lf-pulse{animation:lfpulse 2.2s ease-out infinite}
  .lf-node{cursor:pointer;transition:filter .2s}
  .lf-node:hover{filter:brightness(1.35) drop-shadow(0 0 6px #00e5ff)}
  .lf-card .lf-front,.lf-card .lf-back{transform-box:fill-box;transform-origin:center;transition:transform .18s ease-in}
  .lf-back{transform:scaleX(0);pointer-events:none}
  .lf-card.on .lf-front{transform:scaleX(0)}
  .lf-back.on{transform:scaleX(1);transition:transform .18s ease-out .18s}
  .lf-def{font:9.5px/1.25 Consolas,monospace;color:#e8fbff;padding:5px 8px;height:100%;box-sizing:border-box;overflow:hidden}
  .lf-def b{color:#ffd740;letter-spacing:1px;font-size:9px;display:block;margin-bottom:2px}
  .lf-btn{cursor:pointer}.lf-btn:hover circle{fill:#ff1f4f}
  .lf-panel{border:1px solid #12506e;border-radius:10px;background:linear-gradient(160deg,#041a2b,#020b15);padding:12px;margin-top:10px}
  .lf-chip{display:inline-flex;gap:6px;align-items:center;border:1px dashed #ff5c7a;color:#ffb3c1;border-radius:20px;padding:2px 10px;margin:2px;font-size:11px}
  .lf-b{background:#031a29;border:1px solid #00e5ff;color:#7ff6ff;border-radius:6px;padding:4px 10px;font:11px Consolas,monospace;cursor:pointer;letter-spacing:1px}
  .lf-b:hover{background:#00e5ff22;box-shadow:0 0 10px #00e5ff55}.lf-b.red{border-color:#ff5c7a;color:#ff9fb2}.lf-b.red:hover{background:#ff1f4f22}
  .lf-b:disabled{opacity:.4;cursor:default}
  .lf-bar{height:8px;border-radius:4px;background:#0a2a3d;overflow:hidden;margin:2px 0 6px}
  .lf-verdict{border-left:3px solid #ffd740;padding:6px 10px;background:#1a160622;margin:8px 0;font-size:12px}
  .lf-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:6px;margin:6px 0}
  .lf-scan{position:relative;height:3px;background:#0a2a3d;overflow:hidden;border-radius:2px;margin:8px 0}
  .lf-scan:after{content:'';position:absolute;left:-30%;width:30%;height:100%;background:linear-gradient(90deg,transparent,#00e5ff,transparent);animation:lfscan 1.2s linear infinite}
  @keyframes lfscan{to{left:100%}}`;
  document.head.appendChild(s);
}

// the vocabulary card on the back of each exit (hover flips it)
const LF_DEF = {
  1: 'The initial stop-loss price was hit. The full planned loss: nothing closed the trade earlier.',
  2: 'Exit mode 1 target: price touched the next EMA beyond the entry.',
  3: 'Exit mode 2 built-in exit: a completed candle CLOSED back across the slow EMA. Fires in profit or loss. Catches a failed move before the stop.',
  4: 'Day-close loss cut: a losing trade closed at the end of the day.',
  5: 'Take profit: the broker target price was touched.',
  6: 'Trailing / locked stop above the entry was hit: banks part of the move.',
  7: 'Breakeven: the stop had moved to the entry and was hit. A scratch trade.',
  8: 'Time exit: held the maximum number of candles, closed at the market.',
  9: 'Exit Lab target: a fixed distance from the entry set at open. Touch it and the trade closes at once, mid-candle. Only ever fires in profit.',
  11: 'Partial: part of the position closed at a profit level; the rest runs on.',
  12: 'Optional extra Exit Lab rule: a completed candle confirms your chosen signal against the trade (fast EMA, EMA cross, opposite signal, engulfing, N candles).',
  13: 'No progress: after N candles the trade had not made enough profit - closed as dead.',
  14: 'ADX faded: the trend strength fell below the exit level.',
  15: 'Friday close: closed before the weekend at whatever price. Can be a big win OR a big loss.',
  16: 'Decay stop: after N candles the stop was pulled toward the entry and was hit.',
  17: 'Loss cut: part of a losing trade closed early to shrink the full loss.',
};
let LF_BACKS = [];                                    // the cards' back faces, drawn last (on top of every branch)
function lfFlip(r, on) {
  document.querySelectorAll(`[data-lfc="${r}"]`).forEach((e) => e.classList.toggle('on', !!on));
}
function lfDefCard(r, why, x, y, w, h, col) {         // the front's hover area stays put; the back is a taller card on the top layer
  const W = 250, H = 118, cx = x + w / 2, cy = y + h / 2;
  LF_BACKS.push(lfDefBack(r, why, cx - W / 2, cy - H / 2, W, H));
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="transparent"/>`;
}
function lfDefBack(r, why, x, y, w, h) {
  return `<g class="lf-back" data-lfc="${r}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10" fill="#0a1a10" stroke="#ffd740" stroke-width="1.5" filter="url(#lfGlow)"/>
    <foreignObject x="${x}" y="${y}" width="${w}" height="${h}"><div xmlns="http://www.w3.org/1999/xhtml" class="lf-def" style="font-size:11px;line-height:1.35;padding:8px 10px"><b>${esc(why.toUpperCase())} · DEFINITION</b>${esc(LF_DEF[r] || why)}</div></foreignObject></g>`;
}

// sub-branches: one exit's trades split along a dimension (trade row: side, minutes, pnl, best move, worst move, hour UTC)
const LF_DIMS = {
  result: { label: 'Result size', f: (t, r) => { const W = Math.max(1, r.stats.avg_win), L = Math.max(1, -r.stats.avg_loss);
    return t[2] > W ? [0, `▲▲ big win (> ${money(W)})`] : t[2] > 0 ? [1, '▲ small win'] : t[2] >= -L ? [2, '▼ small loss'] : [3, `▼▼ big loss (< −${money(L)})`]; } },
  side: { label: 'Direction', f: (t) => (t[0] > 0 ? [0, 'BUY trades'] : [1, 'SELL trades']) },
  time: { label: 'Time held', f: (t) => (t[1] < 15 ? [0, 'under 15 min'] : t[1] < 60 ? [1, '15 min – 1 h'] : t[1] < 240 ? [2, '1 – 4 h'] : t[1] < 1440 ? [3, '4 – 24 h'] : [4, 'over a day']) },
  session: { label: 'Session (UTC entry hour)', f: (t) => (t[5] < 7 ? [0, 'Asia 00–07'] : t[5] < 13 ? [1, 'London 07–13'] : t[5] < 21 ? [2, 'New York 13–21'] : [3, 'late 21–24']) },
  mfe: { label: 'Best move for us first', f: (t) => (t[3] < 2 ? [0, 'never +$2'] : t[3] < 10 ? [1, 'reached +$2 – 10'] : t[3] < 25 ? [2, 'reached +$10 – 25'] : [3, 'reached +$25 or more']) },
  mae: { label: 'Worst move against first', f: (t) => (t[4] < 2 ? [0, 'under −$2 against'] : t[4] < 10 ? [1, '−$2 – 10 against'] : t[4] < 25 ? [2, '−$10 – 25 against'] : [3, 'over −$25 against']) },
};
LIFE.dim = 'result';
function lfSplit(b, r) {
  if (!b.trades) return null;
  const d = LF_DIMS[LIFE.dim], g = {};
  for (const t of b.trades) { const [k, label] = d.f(t, r); (g[k] = g[k] || { k, label, n: 0, net: 0, w: 0 }); g[k].n++; g[k].net += t[2]; if (t[2] > 0) g[k].w++; }
  return Object.values(g).sort((a, z) => a.k - z.k).map((x) => ({ ...x, wr: Math.round((1000 * x.w) / x.n) / 10, avg: x.net / x.n }));
}
function lfDim(k) { LIFE.dim = k; renderPanel('tt'); }

function lfKey() { return JSON.stringify([CUR, SRC.ds, SRC.mode, LIFE.pruned]); }

function lfLoad() {
  const key = lfKey();
  if (LIFE.key === key && (LIFE.res || LIFE.busy || LIFE.err)) return;
  LIFE.key = key; LIFE.busy = true; LIFE.err = '';
  const seq = ++LIFE.seq;
  api('/api/lifecycle', { inputs: CUR, ds: SRC.ds, mode: SRC.mode, pruned: LIFE.pruned })
    .then((r) => { if (seq === LIFE.seq) { LIFE.res = r; if (LIFE.sel != null && !r.branches.some((b) => b.r === LIFE.sel)) LIFE.sel = null; } })
    .catch((e) => { if (seq === LIFE.seq) LIFE.err = 'The tree could not be grown: ' + e.message; })
    .finally(() => { if (seq === LIFE.seq) { LIFE.busy = false; renderPanel('tt'); } });
}

function lfCut(r) { if (!LIFE.pruned.includes(r)) LIFE.pruned = [...LIFE.pruned, r].sort((a, b) => a - b); LIFE.sel = null; renderPanel('tt'); }
function lfRestore(r) { LIFE.pruned = LIFE.pruned.filter((x) => x !== r); renderPanel('tt'); }
function lfReset() { LIFE.pruned = []; LIFE.sel = null; renderPanel('tt'); }
function lfSelect(r) { LIFE.sel = LIFE.sel === r ? null : r; renderPanel('tt'); }

async function lfApply(r) {                          // make the cut real: the EA input that switches this exit off
  const b = (LIFE.res.cut || []).find((x) => x.r === r) || (LIFE.res.branches || []).find((x) => x.r === r);
  if (!b || !b.ea_cut) return;
  CUR = { ...CUR, ...b.ea_cut };
  LIFE.pruned = LIFE.pruned.filter((x) => x !== r);
  settingsTouched = true; markForm(); renderPanel('tt');
  await runSim();
  toast(`Applied to the chart: ${Object.entries(b.ea_cut).map(([k, v]) => k + '=' + v).join(', ')} (${esc(b.why)} off). Save it from the settings panel to keep it. Tester hypothesis: MT5 decides.`, 9000);
  renderPanel('tt');
}

const lfM = (v) => (v == null ? '–' : money(v));
const lfD = (v, inv) => (v == null ? '' : `<span class="${(inv ? -v : v) >= 0 ? 'lf-pos' : 'lf-neg'}">${v >= 0 ? '+' : ''}${typeof v === 'number' && Math.abs(v) >= 100 ? money(v) : v}</span>`);
const lfEsc = (s) => esc(String(s)).replace(/'/g, '&#39;');

function lfHud(s, b) {
  const cell = (k, v, d) => `<div class="lf-cell"><div class="lf-k">${k}</div><div class="lf-v">${v}</div><div class="lf-d">${d || '&nbsp;'}</div></div>`;
  const cmp = LIFE.pruned.length && b;
  return `<div class="lf-hud">
    ${cell('NET', `<span class="${s.net >= 0 ? 'lf-pos' : 'lf-neg'}">${lfM(s.net)}</span>`, cmp ? lfD(s.net - b.net) + ' vs uncut' : '')}
    ${cell('TRADES', s.n, cmp ? lfD(s.n - b.n) : '')}
    ${cell('WIN RATE', s.wr + '%', cmp ? lfD(Math.round((s.wr - b.wr) * 10) / 10) + ' pts' : '')}
    ${cell('PROFIT FACTOR', s.pf ?? '–', cmp ? 'was ' + (b.pf ?? '–') : '')}
    ${cell('AVG WIN / LOSS', `${lfM(s.avg_win)} <span style="color:#5f9db8">/</span> ${lfM(s.avg_loss)}`, cmp ? `was ${lfM(b.avg_win)} / ${lfM(b.avg_loss)}` : '')}
    ${cell('WORST LOSS', `<span class="lf-neg">${lfM(s.worst)}</span>`, cmp ? lfD(s.worst - b.worst) : '')}
    ${cell('MAX DRAWDOWN', lfM(s.dd), cmp ? lfD(s.dd - b.dd, true) : '')}
  </div>`;
}

function lfTree(r) {
  const br = r.branches, cut = r.cut || [];
  const RH = 92, W = 1240, top = 60, SUBH = 40;
  const items = [...br.map((b) => ({ b, subs: LIFE.sel === b.r ? lfSplit(b, r) : null })), ...cut.map((c) => ({ c }))];
  items.forEach((it) => { it.h = it.subs ? Math.max(RH, it.subs.length * SUBH + 24) : RH; });
  const used = items.reduce((a, it) => a + it.h, 0);
  const H = Math.max(420, top * 2 + used);
  let acc = top + (H - top * 2 - used) / 2;
  items.forEach((it) => { it.y = acc + it.h / 2; acc += it.h; });
  const X0 = 90, XF = 300, XE = 520, XB = 800, XL = 1110, cy = H / 2;
  const maxN = Math.max(1, ...br.map((b) => b.n));
  LF_BACKS = [];
  let s = `<svg class="lf-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
    <defs>
      <pattern id="lfGrid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#0b2c40" stroke-width=".6"/></pattern>
      <filter id="lfGlow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <linearGradient id="lfCore" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#00e5ff"/><stop offset="1" stop-color="#2979ff"/></linearGradient>
      <radialGradient id="lfHalo"><stop offset="0" stop-color="#00e5ff" stop-opacity=".35"/><stop offset="1" stop-color="#00e5ff" stop-opacity="0"/></radialGradient>
    </defs>
    <rect width="${W}" height="${H}" fill="url(#lfGrid)"/>
    <text x="${X0}" y="24" fill="#5f9db8" font-size="11" text-anchor="middle" letter-spacing="2">BEFORE</text>
    <text x="${XE}" y="24" fill="#5f9db8" font-size="11" text-anchor="middle" letter-spacing="2">ENTRY</text>
    <text x="${XB}" y="24" fill="#5f9db8" font-size="11" text-anchor="middle" letter-spacing="2">HOW THE TRADE ENDS</text>
    <text x="${XL}" y="24" fill="#5f9db8" font-size="11" text-anchor="middle" letter-spacing="2">RESULT</text>
    <line x1="${(XE + XF) / 2 + 40}" x2="${(XE + XF) / 2 + 40}" y1="34" y2="${H - 10}" stroke="#0f3b55" stroke-dasharray="2 6"/>`;
  // before the entry: setups -> filters -> entry
  const rej = r.skips.reduce((a, k) => a + k.n, 0);
  s += `<path d="M${X0 + 60} ${cy} L${XF - 62} ${cy}" stroke="#00e5ff" stroke-width="3" fill="none" opacity=".35"/>
    <path class="lf-flow slow" d="M${X0 + 60} ${cy} L${XF - 62} ${cy}" stroke="#7ff6ff" stroke-width="3" fill="none"/>
    <path d="M${XF + 62} ${cy} L${XE - 46} ${cy}" stroke="#00e5ff" stroke-width="4" fill="none" opacity=".35"/>
    <path class="lf-flow" d="M${XF + 62} ${cy} L${XE - 46} ${cy}" stroke="#7ff6ff" stroke-width="4" fill="none"/>
    <g filter="url(#lfGlow)"><rect x="${X0 - 62}" y="${cy - 34}" width="124" height="68" rx="10" fill="#03182a" stroke="#00e5ff"/>
    <text x="${X0}" y="${cy - 12}" fill="#7ff6ff" font-size="10" text-anchor="middle" letter-spacing="2">SETUPS</text>
    <text x="${X0}" y="${cy + 10}" fill="#e8fbff" font-size="20" font-weight="bold" text-anchor="middle">${r.setups.toLocaleString()}</text>
    <text x="${X0}" y="${cy + 26}" fill="#5f9db8" font-size="9" text-anchor="middle">found by the rules</text></g>
    <g filter="url(#lfGlow)"><polygon points="${XF - 62},${cy} ${XF - 40},${cy - 34} ${XF + 40},${cy - 34} ${XF + 62},${cy} ${XF + 40},${cy + 34} ${XF - 40},${cy + 34}" fill="#0a1424" stroke="#ffd740"/>
    <text x="${XF}" y="${cy - 10}" fill="#ffd740" font-size="10" text-anchor="middle" letter-spacing="2">FILTERS</text>
    <text x="${XF}" y="${cy + 10}" fill="#ffe9a6" font-size="15" text-anchor="middle">−${rej.toLocaleString()}</text>
    <text x="${XF}" y="${cy + 25}" fill="#8d7a3e" font-size="9" text-anchor="middle">rejected</text></g>`;
  r.skips.forEach((k, i) => {
    const y = cy + 70 + i * 34, x2 = XF + 30;
    s += `<path d="M${XF} ${cy + 34} C${XF} ${y - 10}, ${XF} ${y}, ${x2 - 14} ${y}" stroke="#ff5c7a" stroke-width="1.2" fill="none" stroke-dasharray="3 3" opacity=".8"/>
      <text x="${x2 - 8}" y="${y + 4}" fill="#ff9fb2" font-size="10">✕ ${esc(k.label)} · ${k.n.toLocaleString()}</text>`;
  });
  // the entry core
  s += `<circle cx="${XE}" cy="${cy}" r="70" fill="url(#lfHalo)"/><circle class="lf-pulse" cx="${XE}" cy="${cy}" r="34" fill="none" stroke="#00e5ff" stroke-width="1.5"/>
    <g filter="url(#lfGlow)"><circle cx="${XE}" cy="${cy}" r="44" fill="#021626" stroke="url(#lfCore)" stroke-width="3"/>
    <circle cx="${XE}" cy="${cy}" r="37" fill="none" stroke="#00e5ff" stroke-width=".7" stroke-dasharray="2 4"/>
    <text x="${XE}" y="${cy - 8}" fill="#7ff6ff" font-size="9" text-anchor="middle" letter-spacing="2">TRADES</text>
    <text x="${XE}" y="${cy + 12}" fill="#ffffff" font-size="20" font-weight="bold" text-anchor="middle">${r.entries}</text>
    <text x="${XE}" y="${cy + 26}" fill="#5f9db8" font-size="8" text-anchor="middle">${r.stats ? r.stats.wr + '% win' : ''}</text></g>`;
  // the branches: live exits, then the cut ones
  items.forEach((it) => {
    const y = it.y;
    if (it.c) {
      const c = it.c;
      s += `<path d="M${XE + 44} ${cy} C${XE + 160} ${cy}, ${XB - 200} ${y}, ${XB - 120} ${y}" stroke="#ff5c7a" stroke-width="1.5" fill="none" stroke-dasharray="4 6" opacity=".55"/>
        <g transform="translate(${XB - 128},${y})"><text font-size="16" fill="#ff5c7a" text-anchor="middle" y="5" filter="url(#lfGlow)">✂</text></g>
        <g class="lf-node lf-card" data-lfc="${c.r}" onmouseenter="lfFlip(${c.r},1)" onmouseleave="lfFlip(${c.r},0)" onclick="lfSelect(${c.r})">${lfDefCard(c.r, c.why, XB - 105, y - 26, 210, 52)}<g class="lf-front"><rect x="${XB - 105}" y="${y - 26}" width="210" height="52" rx="8" fill="#1a0610" stroke="#ff5c7a" stroke-dasharray="5 4"/>
        <text x="${XB}" y="${y - 6}" fill="#ff9fb2" font-size="11" text-anchor="middle" letter-spacing="1">${esc(c.why.toUpperCase())}</text>
        <text x="${XB}" y="${y + 12}" fill="#ff5c7a" font-size="10" text-anchor="middle">CUT · trades flow to other exits</text></g></g>
        <g class="lf-btn" onclick="lfRestore(${c.r})"><rect x="${XB + 112}" y="${y - 12}" width="66" height="24" rx="12" fill="#031a29" stroke="#00e5ff"/><text x="${XB + 145}" y="${y + 4}" fill="#7ff6ff" font-size="10" text-anchor="middle">RESTORE</text></g>`;
      return;
    }
    const b = it.b, col = b.net >= 0 ? '#4dffb0' : '#ff5c7a', w = 2 + 12 * (b.n / maxN), sel = LIFE.sel === b.r;
    s += `<path d="M${XE + 44} ${cy} C${XE + 160} ${cy}, ${XB - 200} ${y}, ${XB - 108} ${y}" stroke="${col}" stroke-width="${w}" fill="none" opacity=".25"/>
      <path class="lf-flow" d="M${XE + 44} ${cy} C${XE + 160} ${cy}, ${XB - 200} ${y}, ${XB - 108} ${y}" stroke="${col}" stroke-width="${Math.max(1.5, w / 2.5)}" fill="none"/>
      <text x="${XB - 150}" y="${y - 6 - w / 2}" fill="${col}" font-size="10" text-anchor="middle">${b.share}%</text>
      <g class="lf-node lf-card" data-lfc="${b.r}" onmouseenter="lfFlip(${b.r},1)" onmouseleave="lfFlip(${b.r},0)" onclick="lfSelect(${b.r})" ${sel ? 'filter="url(#lfGlow)"' : ''}>${lfDefCard(b.r, b.why, XB - 105, y - 32, 210, 64)}<g class="lf-front"><rect x="${XB - 105}" y="${y - 32}" width="210" height="64" rx="8" fill="#03182a" stroke="${sel ? '#ffffff' : col}" stroke-width="${sel ? 2 : 1.2}"/>
      <rect x="${XB - 105}" y="${y - 32}" width="5" height="64" rx="2" fill="${col}"/>
      <text x="${XB - 92}" y="${y - 14}" fill="#e8fbff" font-size="11" letter-spacing="1">${esc(b.why.toUpperCase())}</text>
      <text x="${XB - 92}" y="${y + 3}" fill="${col}" font-size="14" font-weight="bold">${money(b.net)}</text>
      <text x="${XB - 92}" y="${y + 20}" fill="#6fa5bd" font-size="9.5">${b.n} trades · ${b.wr}% win · avg ${money(b.avg)} · ${b.mins} min</text></g></g>
      <g class="lf-btn" onclick="lfCut(${b.r})"><title>Cut this exit (test only): re-run with it switched off</title><circle cx="${XB + 125}" cy="${y}" r="13" fill="#2a0612" stroke="#ff5c7a"/><text x="${XB + 125}" y="${y + 5}" fill="#ffd0da" font-size="13" text-anchor="middle">✂</text></g>`;
    if (b.impact) s += `<text x="${XB + 125}" y="${y + 27}" fill="${b.impact.net >= 0 ? '#4dffb0' : '#ff5c7a'}" font-size="9" text-anchor="middle">${b.impact.net >= 0 ? '+' : ''}${money(b.impact.net)}</text>`;
    if (it.subs) {                                   // expanded: this exit's sub-branches, fanned out to the right
      const tot = Math.max(1, b.n), y0 = y - ((it.subs.length - 1) * SUBH) / 2;
      s += `<text x="${XL + 30}" y="${y0 - 26}" fill="#ffd740" font-size="9.5" text-anchor="middle" letter-spacing="1">${esc(LF_DIMS[LIFE.dim].label.toUpperCase())} ▸ click again to fold</text>`;
      it.subs.forEach((g, j) => {
        const yy = y0 + j * SUBH, c = g.net >= 0 ? '#4dffb0' : '#ff5c7a', pct = Math.round((1000 * g.n) / tot) / 10;
        s += `<path d="M${XB + 140} ${y} C${XB + 200} ${y}, ${XL - 140} ${yy}, ${XL - 80} ${yy}" stroke="${c}" stroke-width="${1 + 9 * g.n / tot}" fill="none" opacity=".3"/>
          <path class="lf-flow" d="M${XB + 140} ${y} C${XB + 200} ${y}, ${XL - 140} ${yy}, ${XL - 80} ${yy}" stroke="${c}" stroke-width="${Math.max(1, 3 * g.n / tot)}" fill="none"/>
          <text x="${XL - 96}" y="${yy - 5}" fill="${c}" font-size="9" text-anchor="end">${pct}%</text>
          <g filter="url(#lfGlow)"><rect x="${XL - 80}" y="${yy - 16}" width="204" height="32" rx="7" fill="#020f1b" stroke="${c}" stroke-width="1"/>
          <rect x="${XL - 80}" y="${yy - 16}" width="${Math.max(3, 204 * g.n / tot)}" height="3" rx="1" fill="${c}" opacity=".8"/></g>
          <text x="${XL - 70}" y="${yy - 2}" fill="#e8fbff" font-size="10">${esc(g.label)}</text>
          <text x="${XL - 70}" y="${yy + 11}" fill="${c}" font-size="9.5">${g.n} trades · ${money(g.net)} · ${g.wr}% win · avg ${money(g.avg)}</text>`;
      });
      return;
    }
    // winners and losers
    [['W', b.wins, '#4dffb0', -18], ['L', b.losses, '#ff5c7a', 18]].forEach(([t, g, c, dy]) => {
      if (!g.n) return;
      const yy = y + dy;
      s += `<path d="M${XB + 140} ${y} C${XB + 190} ${y}, ${XL - 120} ${yy}, ${XL - 70} ${yy}" stroke="${c}" stroke-width="${1 + 5 * g.n / maxN}" fill="none" opacity=".45"/>
        <rect x="${XL - 70}" y="${yy - 11}" width="160" height="22" rx="11" fill="#020f1b" stroke="${c}" stroke-width=".8"/>
        <text x="${XL - 58}" y="${yy + 4}" fill="${c}" font-size="10">${t === 'W' ? '▲' : '▼'} ${g.n} ${t === 'W' ? 'wins' : 'losses'}  ${money(g.net)}</text>`;
    });
  });
  return s + LF_BACKS.join('') + '</svg>';
}

function lfDetail(r) {
  const b = r.branches.find((x) => x.r === LIFE.sel), c = (r.cut || []).find((x) => x.r === LIFE.sel);
  if (c) return `<div class="lf-panel"><div class="lf-h" style="font-size:13px">✂ ${esc(c.why.toUpperCase())} · CUT</div><p class="lf-sub">${esc(c.text)}</p>
    <p style="font-size:12px">This exit is switched off in the test, and its trades now end through the other branches. The HUD above compares the result with the uncut tree.</p>
    <div class="bar"><button class="lf-b" onclick="lfRestore(${c.r})">RESTORE THIS BRANCH</button>
    ${c.ea_cut ? `<button class="lf-b red" onclick="lfApply(${c.r})">MAKE IT REAL · ${esc(Object.entries(c.ea_cut).map(([k, v]) => k + '=' + v).join(', '))}</button>` : '<span class="lf-sub">No EA input switches this exit off yet: the cut is test only.</span>'}</div></div>`;
  if (!b) return `<div class="lf-panel lf-sub">Click a branch to open it: what it does, its trades, and what cutting it would do. ✂ cuts a branch and re-runs the tester.</div>`;
  const im = b.impact, maxF = Math.max(1, ...b.fate.map((f) => f.n));
  const fate = b.fate.map((f) => {
    const d = f.net - f.was;
    return `<div style="font-size:11px">${f.n} → <b>${esc(f.why)}</b> · now ${money(f.was)} → would be ${money(f.net)} ${lfD(d)}</div>
      <div class="lf-bar"><div style="height:100%;width:${(100 * f.n) / maxF}%;background:${d >= 0 ? 'linear-gradient(90deg,#00c97a,#4dffb0)' : 'linear-gradient(90deg,#c2002f,#ff5c7a)'}"></div></div>`;
  }).join('') + (b.gone.n ? `<div class="lf-sub">${b.gone.n} trades would not be taken at all (positions held longer block new entries): ${money(b.gone.net)} that was theirs.</div>` : '');
  return `<div class="lf-panel">
    <div class="bar" style="justify-content:space-between;align-items:center"><div class="lf-h" style="font-size:13px">◈ ${esc(b.why.toUpperCase())}</div>
      <div class="bar"><button class="lf-b red" onclick="lfCut(${b.r})">✂ CUT THIS BRANCH (TEST)</button>
      ${b.ea_cut ? `<button class="lf-b" onclick="lfApply(${b.r})">TURN OFF IN THE SETTINGS · ${esc(Object.entries(b.ea_cut).map(([k, v]) => k + '=' + v).join(', '))}</button>` : ''}</div></div>
    <p style="font-size:12px;margin:6px 0">${esc(b.text)}</p>
    <div class="lf-grid">
      <div class="lf-cell"><div class="lf-k">TRADES</div><div class="lf-v">${b.n}</div><div class="lf-d">${b.share}% of all</div></div>
      <div class="lf-cell"><div class="lf-k">NET</div><div class="lf-v ${b.net >= 0 ? 'lf-pos' : 'lf-neg'}">${money(b.net)}</div><div class="lf-d">avg ${money(b.avg)}</div></div>
      <div class="lf-cell"><div class="lf-k">WIN RATE</div><div class="lf-v">${b.wr}%</div><div class="lf-d">${b.wins.n} W / ${b.losses.n} L</div></div>
      <div class="lf-cell"><div class="lf-k">AVG WIN / LOSS</div><div class="lf-v" style="font-size:13px">${money(b.avg_win)} / ${money(b.avg_loss)}</div><div class="lf-d">best ${money(b.best)} · worst ${money(b.worst)}</div></div>
      <div class="lf-cell"><div class="lf-k">TIME IN TRADE</div><div class="lf-v">${b.mins}m</div><div class="lf-d">median</div></div>
      <div class="lf-cell"><div class="lf-k">PRICE EXCURSION</div><div class="lf-v" style="font-size:13px">+$${b.mfe} / −$${b.mae}</div><div class="lf-d">avg best / worst move</div></div>
    </div>
    <div class="lf-verdict">${esc(b.verdict)}</div>
    ${im ? `<div class="lf-k" style="margin-top:8px">FORECAST · IF THIS BRANCH IS CUT</div>
      <div class="lf-grid">
        <div class="lf-cell"><div class="lf-k">NET</div><div class="lf-v">${lfD(im.net)}</div><div class="lf-d">→ ${money(im.after.net)}</div></div>
        <div class="lf-cell"><div class="lf-k">WIN RATE</div><div class="lf-v">${lfD(im.wr)} pts</div><div class="lf-d">→ ${im.after.wr}%</div></div>
        <div class="lf-cell"><div class="lf-k">WORST LOSS</div><div class="lf-v">${lfD(im.worst)}</div><div class="lf-d">→ ${money(im.after.worst)}</div></div>
        <div class="lf-cell"><div class="lf-k">DRAWDOWN</div><div class="lf-v">${lfD(im.dd, true)}</div><div class="lf-d">→ ${money(im.after.dd)}</div></div>
        <div class="lf-cell"><div class="lf-k">AVG WIN / LOSS</div><div class="lf-v" style="font-size:13px">${money(im.after.avg_win)} / ${money(im.after.avg_loss)}</div><div class="lf-d">after the cut</div></div>
      </div>
      <div class="lf-k" style="margin:8px 0 4px">WHERE ITS ${b.n} TRADES WOULD END INSTEAD</div>${fate}` : ''}
  </div>`;
}

function pLife() {
  if (typeof XLF !== 'undefined' && XLF.on) return pXLife();
  lfCss(); lfLoad();
  const r = LIFE.res;
  let h = `<div class="lf-wrap">
    <div class="bar" style="justify-content:space-between;align-items:flex-start;flex-wrap:wrap">
      <div><div class="lf-h">⟁ TRADE LIFECYCLE · EVERY PATH A TRADE TAKES</div>
      <div class="lf-sub">The settings on the chart · data ${esc(SRC.ds)}. Branch thickness = how many trades take that path, colour = what it earns.
        ✂ switches an exit off (test only) and re-runs the tester. Tester hypotheses: the MT5 Strategy Tester decides.</div></div>
      <div class="bar"><button class="lf-b" style="border-color:#ffd740;color:#ffd740;box-shadow:0 0 12px #ffd74044" onclick="xlfOpen()">⟁⟁ VIEW EXTENDED LIFECYCLE · EVERY EXIT</button>
        ${LIFE.pruned.length && LIFE.res && !LIFE.busy ? `<button class="lf-b red" onclick="lfApplyTree()">▶ APPLY THIS PRUNED TREE · SEE IT IN OVERVIEW &amp; LIST OF TRADES</button>` : ''}
        ${LF_APPLIED.length ? `<button class="lf-b" onclick="lfUnapply()">REMOVE APPLIED CUTS (${LF_APPLIED.length})</button>` : ''}
        ${LIFE.pruned.length ? `<button class="lf-b" onclick="lfReset()">RESTORE THE WHOLE TREE</button>` : ''}</div>
    </div>`;
  if (LIFE.pruned.length && r) h += `<div style="margin-top:6px">${(r.cut || []).map((c) => `<span class="lf-chip">✂ ${esc(c.why)} <a style="cursor:pointer;color:#7ff6ff" onclick="lfRestore(${c.r})">restore</a></span>`).join('')}</div>`;
  if (LIFE.busy) h += `<div class="lf-scan"></div><div class="lf-sub">Growing the tree: the tester runs once per branch to forecast each cut…</div>`;
  if (LIFE.err) h += `<p class="note bad">${esc(LIFE.err)}</p>`;
  if (r && r.stats) {
    const open = LIFE.sel != null && r.branches.find((b) => b.r === LIFE.sel);
    h += lfHud(r.stats, r.base);
    h += open ? `<div class="bar" style="align-items:center;gap:6px;margin:4px 0"><span class="lf-k">SPLIT ${esc(open.why.toUpperCase())} BY</span>${Object.entries(LF_DIMS).map(([k, d]) =>
      `<button class="lf-b${LIFE.dim === k ? '' : ''}" style="${LIFE.dim === k ? 'background:#00e5ff33;box-shadow:0 0 10px #00e5ff66' : ''}" onclick="lfDim('${k}')">${esc(d.label)}</button>`).join('')}</div>`
      : `<div class="lf-sub" style="margin:4px 0">Click an exit to expand it into its sub-branches.</div>`;
    h += lfTree(r) + lfDetail(r);
    if (r.open_at_end) h += `<div class="lf-sub" style="margin-top:6px">${r.open_at_end} trade(s) still open at the end of the data are not in the tree.</div>`;
  } else if (r) h += '<p class="lf-sub">No trades on these settings.</p>';
  return h + '</div>';
}

// ---- apply the pruned tree to the main tester: Overview, List of trades and the chart then show the cut tree (test only)
async function lfApplyTree() {
  LF_APPLIED = (LIFE.res && LIFE.res.cut || []).map((c) => ({ r: c.r, why: c.why }));
  await runSim();
  TAB.tt = 'overview'; renderPanel('tt');
  toast(`Applied the pruned tree: ${LF_APPLIED.map((c) => '✂ ' + esc(c.why)).join(', ')}. Overview and List of trades now show it. Test only - the EA cannot run these cuts; MT5 decides.`, 9000);
}
async function lfUnapply() { LF_APPLIED = []; await runSim(); renderPanel('tt'); toast('The tree cuts are removed: the main tester runs every exit again.'); }
function lfBanner() {
  let b = document.getElementById('lfBanner');
  if (!LF_APPLIED.length) { if (b) b.remove(); return; }
  if (!b) { b = document.createElement('div'); b.id = 'lfBanner'; $('#infoTT').parentNode.insertBefore(b, $('#infoTT')); }
  b.style.cssText = 'border:1px dashed #ff5c7a;background:#1a0610;color:#ffb3c1;padding:4px 10px;border-radius:8px;margin:4px 0;font-size:12px';
  b.innerHTML = `⟁ Trade Lifecycle cuts applied: <b>${LF_APPLIED.map((c) => '✂ ' + esc(c.why)).join(', ')}</b> - test only, not an EA setting (MT5 can't run it) <button class="dexbtn sm" onclick="lfUnapply()">remove</button>`;
}
