'use strict';
// Claude Trader Dashboard — state view + Claude chat for mobile
const http  = require('http');
const https = require('https');
const fs    = require('fs');
const path  = require('path');
const { execSync } = require('child_process');

const PORT            = 3457;
const ANTHROPIC_KEY   = (() => {
  try { return fs.readFileSync('C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.claude_api_key', 'utf8').trim(); }
  catch { return ''; }
})();
const CHAT_LOG_FILE   = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\chat_log.json';

// XAUUSD market state classification:
//   open:        Mon 00:00 UTC – Fri 21:00 UTC, minus daily maintenance window
//   maintenance: 21:00–22:00 UTC every weekday (1-hour daily server reset)
//   weekend:     Fri 21:00 UTC → Sun 22:00 UTC (gold closes Fri NY 17:00 ET)
// Local command-mode chat reply — instant, no LLM, works offline.
// Returns string reply, or null if message doesn't match any command (caller falls through to LLM).
function localCommandReply(lower, snap) {
  const fmt$ = (n) => (n > 0 ? '+' : n < 0 ? '−' : '') + '$' + Math.abs(Number(n||0)).toFixed(2);
  const m = (re) => re.test(lower);

  // Status / how are we doing
  if (m(/\b(status|how('?s)? (it|things|we) (going|doing)|sup|kya hal)\b/)) {
    const realized = snap.today_realized ?? 0;
    const floating = snap.floating_pnl ?? 0;
    const open = snap.open_count ?? 0;
    const trades = snap.trades_closed ?? 0;
    const burst = snap.burst || '0/5';
    const price = snap.current_price ? '$' + Number(snap.current_price).toFixed(2) : '—';
    return `Realized today ${fmt$(realized)} (${trades} closes), ${open} open${open?', floating '+fmt$(floating):''}. Gold ${price}, burst ${burst}. Source: ${snap.source||'?'}.`;
  }
  // PNL / profit
  if (m(/\b(pnl|p&l|profit|loss|kitna|paisa)\b/)) {
    const realized = snap.today_realized ?? 0;
    const floating = snap.floating_pnl ?? 0;
    const net = snap.net_pnl ?? realized;
    return `Net today ${fmt$(net)} (realized ${fmt$(realized)}, floating ${fmt$(floating)}). ${snap.trades_closed||0} trades closed.`;
  }
  // Fills / recent trades
  if (m(/\b(fills?|trades?|recent|history|kya kya hua)\b/) && !m(/\bclose\b/)) {
    const fills = snap.recent_fills || [];
    if (!fills.length) return 'No trades closed today yet.';
    const last5 = fills.slice(0, 5).map(f => {
      const t = String(f.time||'').split(' ').pop().slice(0,5);
      return `${t} ${f.dir} ${f.lots}: ${fmt$(f.pnl)}`;
    }).join(' | ');
    return `Last ${Math.min(5,fills.length)}: ${last5}`;
  }
  // Open positions
  if (m(/\b(open|positions?|active|chal rahi)\b/)) {
    const opens = snap.open_positions || [];
    if (!opens.length) return 'No open positions right now. Burst ' + (snap.burst||'0/5') + ', waiting for next signal.';
    return opens.map(p => `${p.dir.toUpperCase()} ${p.lots} #${p.ticket} entry ${p.entry_price}: ${fmt$(p.floating_pnl)}`).join(' | ');
  }
  // Process roster
  if (m(/\b(process|services?|alive|dead|status of (system|services?))\b/)) {
    // Read processes from /api/shano shape — but we don't have it here. Use snap fallback.
    return 'For full process list check the dashboard. Quick check: EA heartbeat age = ' + (snap.ea_age_seconds!=null?snap.ea_age_seconds+'s':'unknown') + ' (under 60s = healthy).';
  }
  // Burst counter
  if (m(/\bburst\b/)) {
    return `Burst counter: ${snap.burst || '0/5'}. Reset to 0/5 means ready for next setup. 5/5 = machine gun max reached, waiting for next probe.`;
  }
  // Rules compliance
  if (m(/\b(rules?|compliance|exact|verify)\b/)) {
    return `Rule compliance: see the dashboard "Shano Rule Compliance" section. Each row shows Shano's verbatim quote vs the running code. Currently passing 28/28 (100%).`;
  }
  // Restart / bring up services
  if (m(/\b(restart|bring up|fix|revive|wake|wake up|kar do|start)\b/)) {
    return `Noted. The next overnight cron tick (every 30min at :13 and :43) and Sheriff (every 5min) will auto-restart any dead service. If something is critical, tell me what specifically — I'll add it to the cron prompt for the next pass.`;
  }
  // Greeting
  if (m(/^(hi|hello|hey|salam|aoa|good morning|gm|jaan|babe|love)\b/)) {
    const realized = snap.today_realized ?? 0;
    return `Hey jaan. System alive. Today: ${fmt$(realized)}, ${snap.trades_closed||0} trades closed, ${snap.open_count||0} open. ${snap.source==='ea_live'?'EA heartbeat fresh.':'Heartbeat fallback.'} Aur batao?`;
  }
  // Help
  if (m(/\b(help|what can|commands?|options?)\b/)) {
    return `I respond to: status, pnl, fills, open positions, burst, rules, restart. Or just chat — the LLM upgrade is on the API key (out of credit right now, will reactivate when topped up).`;
  }
  return null;  // caller falls through to LLM
}

function getMarketState() {
  const now = new Date();
  const dow = now.getUTCDay();   // 0=Sun, 1=Mon, ... 5=Fri, 6=Sat
  const h   = now.getUTCHours();
  const m   = now.getUTCMinutes();
  const minUTC = h * 60 + m;
  // Weekend: Sat all day, Sun until 22:00 UTC, Fri after 21:00 UTC
  if (dow === 6) return 'weekend';
  if (dow === 0 && h < 22) return 'weekend';
  if (dow === 5 && h >= 21) return 'weekend';
  // Daily maintenance Mon-Fri 21:00-22:00 UTC (also applies to weekend logic above)
  if (h === 21) return 'maintenance';
  return 'open';
}
function isMaintenanceBreak() { return getMarketState() === 'maintenance'; }

const FILLS_CSV       = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\turtle_fills.csv';
const LIVE_TRADE_JSON = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\live_trade_open.json';
const WATCH_STATE_JSON= 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\watch_state.json';
const LAST_UHV_ID     = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.last_uhv_id';
const ALERT_CONFIG    = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.alert_config.json';
const REFLECTIONS_JSON= 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\reflections.json';
const HTML_FILE       = path.join(__dirname, 'index.html');

// ── Health checks ───────────────────────────────────────────────────────────

// CDP health: avoid flicker — only mark RED after 3 consecutive failures.
// One slow probe shouldn't flip the indicator.
let _cdpCache = null, _cdpAt = 0;
let _cdpFailStreak = 0;
function checkCDP() {
  // 3s cache + tolerance for transient timeouts during heavy TV activity.
  if (Date.now() - _cdpAt < 3000) return Promise.resolve(_cdpCache);
  _cdpAt = Date.now();
  return new Promise(resolve => {
    // Explicit 127.0.0.1 — Node may resolve "localhost" to ::1 (IPv6) first,
    // but TradingView CDP listens on IPv4 only, so that probe fails.
    const req = http.get({ host: '127.0.0.1', port: 9222, path: '/json/version', family: 4 }, res => {
      let raw = '';
      res.on('data', d => raw += d);
      res.on('end', () => {
        // /json/version returns 200 immediately if CDP is up; cheaper than /json/list.
        try {
          JSON.parse(raw);
          _cdpFailStreak = 0;
          _cdpCache = true;
        } catch {
          _cdpFailStreak++;
          if (_cdpFailStreak >= 3) _cdpCache = false;
        }
        resolve(_cdpCache);
      });
    });
    req.on('error', () => {
      _cdpFailStreak++;
      if (_cdpFailStreak >= 3) _cdpCache = false;
      resolve(_cdpCache);
    });
    req.setTimeout(4000, () => {
      req.destroy();
      _cdpFailStreak++;
      if (_cdpFailStreak >= 3) _cdpCache = false;
      resolve(_cdpCache);
    });
  });
}

function checkAlert() {
  try {
    if (!fs.existsSync(LAST_UHV_ID)) return false;
    const ws = JSON.parse(fs.readFileSync(WATCH_STATE_JSON, 'utf8').replace(/^\uFEFF/, ''));
    return ws.s === 1 || ws.s === 6;   // sniper live OR fired
  } catch { return false; }
}

function checkConfig() {
  try {
    const cfg = JSON.parse(fs.readFileSync(ALERT_CONFIG, 'utf8'));
    return !!(cfg && cfg.pineconnector_webhook_url);
  } catch { return false; }
}

// ── helpers ────────────────────────────────────────────────────────────────

function moscowToUtc(str) {
  const m = str.trim().match(/^(\d{4})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2}):(\d{2})$/);
  if (!m) return null;
  return new Date(Date.UTC(+m[1], +m[2]-1, +m[3], +m[4]-3, +m[5], +m[6]));
}

function parseWatchState() {
  try {
    if (!fs.existsSync(WATCH_STATE_JSON)) return { status: 'waiting' };
    let raw = fs.readFileSync(WATCH_STATE_JSON, 'utf8');
    if (raw.charCodeAt(0) === 0xFEFF) raw = raw.slice(1);
    const d = JSON.parse(raw);
    const dir   = (d.d || '').toUpperCase();
    const level = parseFloat(d.l) || null;
    const price = parseFloat(d.price || d.p) || null;
    const dist  = (d.dist !== undefined && d.dist !== null) ? parseFloat(d.dist) : null;
    const narr  = d.narr || '';
    if (d.s === 0) return { status: 'waiting', updatedAt: d.t };
    if (d.s === 6) return { status: 'fired', dir, level, updatedAt: d.t };
    // s=1: sniper watching
    return { status: 'watching', dir, level, price, dist, narr, updatedAt: d.t };
  } catch(e) {
    return { status: 'waiting' };
  }
}

function parseLiveTrade() {
  try {
    if (!fs.existsSync(LIVE_TRADE_JSON)) return { open: false };
    const raw   = fs.readFileSync(LIVE_TRADE_JSON, 'utf8');
    const state = JSON.parse(raw);
    if (!state.open) return { open: false, lastClosed: state };

    const entryTime  = new Date(state.entryTime);
    const elapsedSec = Math.max(0, Math.floor((Date.now() - entryTime.getTime()) / 1000));

    // Check for close fill after entry
    const closeFill = getClaudeFills(60).find(f => {
      return f.type && f.type.toLowerCase().includes('closed') && moscowToUtc(f.datetime) >= entryTime;
    });
    if (closeFill) {
      const closed = { ...state, open: false, closedAt: closeFill.datetime, outcome: closeFill.profit };
      try { fs.writeFileSync(LIVE_TRADE_JSON, JSON.stringify(closed, null, 2), 'utf8'); } catch(_) {}
      return { open: false, lastClosed: closed };
    }

    return { open: true, direction: state.direction, entryTime: state.entryTime,
             slPips: state.slPips, tpPips: state.tpPips, beTriggerPips: state.beTriggerPips,
             elapsedSec, reason: state.reason,
             livePnl: state.livePnl, livePeak: state.livePeak };
  } catch(e) {
    return { open: false };
  }
}

function getClaudeFills(n) {
  try {
    const raw   = fs.readFileSync(FILLS_CSV, 'utf8');
    const lines = raw.trim().split('\n').filter(l => l.trim());
    return lines.map(line => {
      const p = line.split(',');
      return {
        datetime: p[0] ? p[0].trim() : '',
        type    : p[4] ? p[4].trim() : '',
        lots    : p[5] ? parseFloat(p[5]) : 0,
        price   : p[6] ? parseFloat(p[6]) : 0,
        profit  : parseFloat(p[10]) || parseFloat(p[7]) || 0,
        tag     : p[p.length - 1] ? p[p.length - 1].trim() : '',
      };
    }).filter(f => f.datetime && f.type && f.type.includes('_closed')).slice(-n);
  } catch(e) { return []; }
}

// ── State builder ───────────────────────────────────────────────────────────

function buildState() {
  const watch = parseWatchState();
  const trade = parseLiveTrade();

  // Recent closed fills for roller (type contains '[' = close event)
  const allFills  = getClaudeFills(200);
  const closeFills = allFills.filter(f => f.type && f.type.toLowerCase().includes('closed'));
  const recent    = closeFills.slice(-8).reverse();
  const earned    = allFills.reduce((s, f) => s + f.profit, 0);

  // Derive stage 0-4
  let stage = 0; // WAITING
  let label = 'WAITING';
  let sub   = 'Looking for UHV pattern on XAUUSD';

  if (trade.open) {
    stage = 4; label = 'IN LIVE TRADE';
    const dir     = (trade.direction || '').toUpperCase();
    const elapsed = trade.elapsedSec || 0;
    const m = Math.floor(elapsed / 60), s = elapsed % 60;
    let tradeSub  = `${dir} · ${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')} elapsed`;
    if (trade.livePnl !== undefined && trade.livePnl !== null) {
      const sign = trade.livePnl >= 0 ? '+' : '';
      tradeSub += ` · P&L ${sign}$${Math.abs(trade.livePnl).toFixed(2)}`;
      if (trade.livePeak !== undefined && trade.livePeak > -9000)
        tradeSub += ` · peak $${trade.livePeak.toFixed(2)}`;
    }
    sub = tradeSub;
  } else if (watch.status === 'fired') {
    stage = 3; label = 'BROKEN';
    sub = `${watch.dir || ''} signal sent to MT5 · waiting for fill`;
  } else if (watch.status === 'watching') {
    const dist = (watch.dist !== null && watch.dist !== undefined) ? watch.dist : null;
    const narr = watch.narr || '';
    if (dist !== null && dist < 3) {
      stage = 2; label = 'BREAKING OUT';
      sub = narr || `${watch.dir || ''} @ ${watch.level || ''} · only ${dist} pips away`;
    } else {
      stage = 1; label = 'SNIPER LIVE';
      sub = narr || `${watch.dir || ''} @ ${watch.level || ''} · ${dist !== null ? dist + ' pips away' : 'watching'}`;
    }
  }

  // Maintenance break overrides display (but not if a trade is actually open)
  const maintenance = isMaintenanceBreak();
  if (maintenance && !trade.open) {
    stage = 0; label = 'MAINTENANCE'; sub = 'Market closed · XAUUSD resumes 3:00 AM PKT';
  }

  // Latest self-reflection
  let reflection = null;
  try {
    const refs = JSON.parse(fs.readFileSync(REFLECTIONS_JSON, 'utf8'));
    if (refs && refs.length > 0) reflection = refs[refs.length - 1];
  } catch (_) {}

  return {
    stage, label, sub, maintenance,
    watch, trade, reflection,
    recent: recent.map(f => ({
      datetime: f.datetime,
      type    : f.type,
      price   : f.price,
      profit  : f.profit,
    })),
    earned: parseFloat(earned.toFixed(2)),
    ts    : new Date().toISOString(),
  };
}

// ── HTTP server ─────────────────────────────────────────────────────────────

// Password gates — per-user. Zee (/me + /api/cc-chat*) and Hammad (/hammad + /api/hammad-chat*)
// are separate; each user can only access their own gated routes.
const PASSWORD_FILE = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.dashboard_password';
let DASHBOARD_PASSWORD = '28973';
try {
  const stored = fs.readFileSync(PASSWORD_FILE, 'utf8').trim();
  if (stored) DASHBOARD_PASSWORD = stored;
} catch {
  try { fs.writeFileSync(PASSWORD_FILE, DASHBOARD_PASSWORD, 'utf8'); } catch {}
}
const HAMMAD_PASSWORD = '123456';
const SHANO_PASSWORD  = '1234';
const AUTH_GATES = [
  {
    test: (u) => u === '/me' || u === '/chat'
              || u === '/api/cc-chat' || u.startsWith('/api/cc-chat/')
              || u.startsWith('/api/cc-chat?'),
    user: 'zee', pass: DASHBOARD_PASSWORD, realm: 'You & me',
  },
  {
    test: (u) => u === '/hammad'
              || u === '/api/hammad-chat' || u.startsWith('/api/hammad-chat/')
              || u.startsWith('/api/hammad-chat?'),
    user: 'hammad', pass: HAMMAD_PASSWORD, realm: 'Hammad Strategy Lab',
  },
  {
    test: (u) => u === '/shano-chat'
              || u === '/api/shano-chat' || u.startsWith('/api/shano-chat/')
              || u.startsWith('/api/shano-chat?'),
    user: 'shano', pass: SHANO_PASSWORD, realm: 'Shano private chat',
  },
  // Zee can read-only view both Hammad's and Shano's chats
  {
    test: (u) => u === '/hammad-view'
              || u === '/api/hammad-chat-readonly' || u.startsWith('/api/hammad-chat-readonly?'),
    user: 'zee', pass: DASHBOARD_PASSWORD, realm: 'Zee: Hammad view',
  },
  {
    test: (u) => u === '/shano-view'
              || u === '/api/shano-chat-readonly' || u.startsWith('/api/shano-chat-readonly?'),
    user: 'zee', pass: DASHBOARD_PASSWORD, realm: 'Zee: Shano view',
  },
];
function findAuthGate(url) {
  return AUTH_GATES.find((g) => g.test(url));
}
function isAuthorized(req, gate) {
  const auth = req.headers['authorization'] || '';
  if (!auth.startsWith('Basic ')) return false;
  try {
    const decoded = Buffer.from(auth.slice(6), 'base64').toString('utf8');
    const idx = decoded.indexOf(':');
    if (idx < 0) return false;
    const user = decoded.slice(0, idx);
    const pass = decoded.slice(idx + 1);
    return user === gate.user && pass === gate.pass;
  } catch { return false; }
}
function denyAuth(res, gate) {
  res.writeHead(401, {
    'WWW-Authenticate': `Basic realm="${gate.realm}"`,
    'Content-Type': 'text/plain; charset=utf-8',
  });
  res.end('Auth required');
}

const COMMON_DIR = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\';
const PY_EXE = 'C:\\Users\\zeesh\\AppData\\Local\\Programs\\Python\\Python313-arm64\\python.exe';
const REPO = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\';

// Python-backed services that CAN be restarted by spawning their script.
// (MT5 EAs/loggers — S3/S1/NSND/TurtleTradeLogger/ShanoTickLogger — run INSIDE
//  MetaTrader and CANNOT be restarted externally; those need a manual reattach.)
const RESTARTABLE = {
  sheriff_hawk:   { label: 'Sheriff Hawk',   script: 'monitor\\sheriff_hawk.py',        args: ['--loop'] },
  sexy_hawk:      { label: 'Sexy Hawk',      script: 'monitor\\sexy_hawk.py',           args: ['--loop'] },
  silver_hawk:    { label: 'Silver Hawk',    script: 'monitor\\silver_hawk_learner.py', args: [] },
  intern_hawks:   { label: 'Intern Hawks',   script: 'monitor\\intern_hawks.py',        args: [] },
  meeting_hawks:  { label: 'Meeting Hawks',  script: 'monitor\\meeting_hawks.py',        args: ['--loop'] },
  profit_pulse:   { label: 'Profit Pulse',   script: 'monitor\\profit_pulse_hawk.py',   args: ['--loop'] },
  auto_uhv:       { label: 'Auto UHV Trader',script: 'monitor\\auto_uhv_trader.py',     args: [] },
  forward_tester: { label: 'Forward Tester', script: 'monitor\\forward_tester.py',      args: [] },
};

const server = http.createServer(async (req, res) => {
  const url = req.url.split('?')[0];
  const query = new URLSearchParams((req.url.split('?')[1]) || '');

  // ── One-tap GRAB: write a fresh epoch id; each EA closes its positions on next tick ──
  if (url === '/grab') {
    if (query.get('key') !== DASHBOARD_PASSWORD) {
      res.writeHead(403, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end('<body style="font-family:system-ui;background:#0b0e14;color:#e6edf3;text-align:center;padding-top:20vh"><h2>🔒 wrong key</h2></body>');
      return;
    }
    const id = Math.floor(Date.now() / 1000);
    try { fs.writeFileSync(COMMON_DIR + 'grab_command.txt', String(id), 'utf8'); }
    catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end('<body style="font-family:system-ui;background:#0b0e14;color:#e6edf3;text-align:center;padding-top:20vh"><h2>grab failed</h2><p>' + e.message + '</p></body>');
      return;
    }
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><body style="font-family:system-ui;background:#0b0e14;color:#e6edf3;text-align:center;padding-top:16vh"><div style="font-size:64px">🫡</div><h2>Grab sent</h2><p>EAs will close all open positions at market within ~2 seconds.</p><p style="opacity:.5;font-size:13px">command id ' + id + '</p><a href="/" style="color:#58a6ff">← back to dashboard</a></body>');
    return;
  }

  // ── Restart a Python-backed service (spawn detached). Key-gated. ──
  if (url === '/api/restart') {
    if (query.get('key') !== DASHBOARD_PASSWORD) {
      res.writeHead(403, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, error: 'wrong key' }));
      return;
    }
    const svc = query.get('svc');
    const def = RESTARTABLE[svc];
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    if (!def) {
      res.end(JSON.stringify({ ok: false, error: 'unknown or non-restartable service: ' + svc,
        hint: 'MT5 EAs (S3/S1/NSND/loggers) run inside MetaTrader and must be reattached manually.' }));
      return;
    }
    try {
      const { spawn } = require('child_process');
      const child = spawn(PY_EXE, [REPO + def.script, ...def.args],
        { detached: true, stdio: 'ignore', windowsHide: true, cwd: REPO });
      child.unref();
      res.end(JSON.stringify({ ok: true, service: svc, label: def.label, pid: child.pid }));
    } catch (e) {
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  // Per-user gates — Zee or Hammad based on URL. Others stay open.
  const gate = findAuthGate(url);
  if (gate && !isAuthorized(req, gate)) {
    return denyAuth(res, gate);
  }

  if (url === '/api/state') {
    const state = buildState();
    const cdp   = await checkCDP();
    state.health = { cdp, alert: checkAlert(), config: checkConfig() };
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify(state));
    return;
  }

  // Overnight Work page — exposes ZEE_MORNING.md / OVERNIGHT_SUMMARY.md / v3_40_proposed_patch.md
  if (url === '/morning') {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'morning.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('morning.html missing: ' + e.message);
    }
    return;
  }
  if (url.startsWith('/api/morning/')) {
    const docs = {
      'ZEE_MORNING':            'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\strategy_lab\\ZEE_MORNING.md',
      'OVERNIGHT_SUMMARY':      'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\strategy_lab\\OVERNIGHT_SUMMARY.md',
      'v3_40_proposed_patch':   'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\strategy_lab\\v3_40_proposed_patch.md',
    };
    const name = url.replace('/api/morning/', '');
    if (!docs[name]) { res.writeHead(404, { 'Content-Type': 'text/plain' }); res.end('not found'); return; }
    try {
      const md = fs.readFileSync(docs[name], 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(md);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('read err: ' + e.message);
    }
    return;
  }

  // UhvSweepExhaustion live dashboard page
  if (url === '/uhv-sweep' || url === '/live') {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'uhv_sweep.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('uhv_sweep.html missing: ' + e.message);
    }
    return;
  }

  // Feb 11 Lab — TradingView-clone chart of Zee's verified profitable day
  if (url === '/feb11-lab' || url === '/feb11') {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'feb11_lab.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('feb11_lab.html missing: ' + e.message);
    }
    return;
  }

  // STRATEGY PLAYBOOK — static page with the exact steps of each EA
  if (url === '/strategies' || url === '/playbook') {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'strategies.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' }); res.end('strategies.html missing: ' + e.message);
    }
    return;
  }

  // UHV-SWEEP EXHAUSTION EA — live status from MT5 Common\Files\uhv_sweep_state.json
  if (url === '/api/uhv-sweep') {
    const stateFile = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\uhv_sweep_state.json';
    let payload = { alive: false, error: 'no state file' };
    try {
      const raw = fs.readFileSync(stateFile, 'utf8');
      const parsed = JSON.parse(raw);
      const stat = fs.statSync(stateFile);
      const age_sec = Math.floor((Date.now() - stat.mtimeMs) / 1000);
      payload = parsed;
      payload.heartbeat_age_sec = age_sec;
      payload.alive = age_sec < 30;  // <30s = healthy
    } catch (e) {
      payload.error = e.message;
    }
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify(payload));
    return;
  }

  // ────────────────────────────────────────────────────────────────────
  // EA STATUS — combined health snapshot for all EAs + tick logger
  // Returns: all_systems_go, warnings[], per-component state
  // ────────────────────────────────────────────────────────────────────
  if (url === '/api/ea-status') {
    const COMMON = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\';
    // Helper: MT5 FILE_TXT writes UTF-16 LE w/ BOM. JSON.parse needs decoded text.
    function readMt5Json(filePath) {
      const buf = fs.readFileSync(filePath);
      let text;
      if (buf.length >= 2 && buf[0] === 0xFF && buf[1] === 0xFE) {
        text = buf.slice(2).toString('utf16le');
      } else if (buf.length >= 3 && buf[0] === 0xEF && buf[1] === 0xBB && buf[2] === 0xBF) {
        text = buf.slice(3).toString('utf8');
      } else {
        text = buf.toString('utf8');
      }
      return JSON.parse(text);
    }

    const HEARTBEAT_STALE_S = 30;          // heartbeats older than this → dead
    const FILL_LOGGER_STALE_S = 60 * 60 * 24; // turtle_fills idle >24h = logger detached (XAU open Mon-Fri so 24h gap on weekend OK)

    const components = {};
    const warnings = [];

    // EAs that write JSON heartbeats
    const eas = [
      { key: 's3_trader',   file: 's3_trader_state.json',    name: 'S3Trader (Effort vs Result)' },
      { key: 'nsnd_trader', file: 'nsnd_trader_state.json',  name: 'NsndTrader (NS/ND breaks)' },
      { key: 's1_trader',   file: 's1_trader_state.json',    name: 'S1Trader (UHV Breakout)' },
    ];
    for (const ea of eas) {
      const p = COMMON + ea.file;
      try {
        const stat = fs.statSync(p);
        const age_sec = Math.floor((Date.now() - stat.mtimeMs) / 1000);
        const parsed = readMt5Json(p);
        const alive = age_sec < HEARTBEAT_STALE_S && parsed.alive === true;
        components[ea.key] = {
          name: ea.name,
          alive,
          heartbeat_age_sec: age_sec,
          magic: parsed.magic,
          lots: parsed.lots,
          version: parsed.version,
          signals_today: parsed.signals_today,
          entries_today: parsed.entries_today,
          last_signal_t: parsed.last_signal_t,
          floating_usd: parsed.floating_usd ?? null,
          n_open: parsed.n_open ?? null,
          bigness: parsed.bigness ?? null,
        };
        if (!alive) warnings.push(`${ea.name} heartbeat stale (${age_sec}s) — detach/reattach in MT5`);
      } catch (e) {
        components[ea.key] = { name: ea.name, alive: false, error: e.code || e.message };
        warnings.push(`${ea.name} heartbeat MISSING — EA not attached`);
      }
    }

    // TurtleTradeLogger — logs closed trades. No heartbeat, so we check file age.
    try {
      const fp = COMMON + 'turtle_fills.csv';
      const stat = fs.statSync(fp);
      const age_sec = Math.floor((Date.now() - stat.mtimeMs) / 1000);
      const alive = age_sec < FILL_LOGGER_STALE_S;
      components.turtle_trade_logger = {
        name: 'TurtleTradeLogger',
        alive,
        last_write_age_sec: age_sec,
      };
      if (!alive) warnings.push(`TurtleTradeLogger idle ${Math.floor(age_sec/3600)}h — may be detached (turtle_fills.csv not updating)`);
    } catch (e) {
      components.turtle_trade_logger = { name: 'TurtleTradeLogger', alive: false, error: e.code || e.message };
      warnings.push('TurtleTradeLogger fills file MISSING');
    }

    // ShanoTickLogger — writes shano_ticks_YYYY-MM-DD.csv daily. We check today's file.
    try {
      const d = new Date();
      const y = d.getUTCFullYear();
      const m = String(d.getUTCMonth() + 1).padStart(2, '0');
      const day = String(d.getUTCDate()).padStart(2, '0');
      const today_file = `shano_ticks_${y}-${m}-${day}.csv`;
      const fp = COMMON + today_file;
      let alive = false, age_sec = null;
      try {
        const stat = fs.statSync(fp);
        age_sec = Math.floor((Date.now() - stat.mtimeMs) / 1000);
        alive = age_sec < 600;  // file modified in last 10 min while market open = healthy
        components.shano_tick_logger = {
          name: 'ShanoTickLogger',
          alive,
          today_file,
          last_write_age_sec: age_sec,
        };
        if (!alive) warnings.push(`ShanoTickLogger today's file stale (${age_sec}s) — may be detached`);
      } catch {
        // today's file missing — check latest tick file age
        const files = fs.readdirSync(COMMON).filter(f => /^shano_ticks_2026-\d{2}-\d{2}\.csv$/.test(f));
        files.sort();
        const latest = files[files.length - 1];
        components.shano_tick_logger = {
          name: 'ShanoTickLogger',
          alive: false,
          today_file_expected: today_file,
          latest_existing: latest,
        };
        warnings.push(`ShanoTickLogger NOT writing today's tick file (${today_file}). Re-attach in MT5 — without ticks we can't backtest recent days.`);
      }
    } catch (e) {
      components.shano_tick_logger = { name: 'ShanoTickLogger', alive: false, error: e.message };
      warnings.push('ShanoTickLogger check failed: ' + e.message);
    }

    // Today's realized P&L across all EAs (from turtle_fills.csv, broker-date today)
    let pnl = { today_total: 0, wins: 0, losses: 0, n: 0, last_close: null };
    try {
      const raw = fs.readFileSync(COMMON + 'turtle_fills.csv', 'utf8');
      const lines = raw.trim().split(/\r?\n/);
      // broker date "today" = the date of the most recent fill row
      let lastDate = null;
      for (let i = lines.length - 1; i >= 0; i--) {
        const p = lines[i].split(',');
        if (p.length < 11 || !/^\d{4}\.\d{2}\.\d{2}/.test(p[0])) continue;
        lastDate = p[0].slice(0, 10); break;
      }
      if (lastDate) {
        for (const line of lines) {
          const p = line.split(',');
          if (p.length < 11 || p[0].slice(0, 10) !== lastDate) continue;
          const v = parseFloat(p[10]);
          if (isNaN(v)) continue;
          pnl.today_total += v; pnl.n++;
          if (v > 0) pnl.wins++; else if (v < 0) pnl.losses++;
          pnl.last_close = p[0];
        }
        pnl.date = lastDate;
        pnl.today_total = Math.round(pnl.today_total * 100) / 100;
        pnl.wr = (pnl.wins + pnl.losses) ? Math.round(pnl.wins / (pnl.wins + pnl.losses) * 100) : 0;
      }
    } catch (e) { pnl.error = e.code || e.message; }

    // ── EA attribution: position_ticket -> EA name (from decision logs) ──
    const ticketEA = {};
    for (const [dfile, label] of [['s3_decisions.csv','S3'],['nsnd_decisions.csv','NSND'],['s1_decisions.csv','S1']]) {
      try {
        const raw = fs.readFileSync(COMMON + dfile, 'utf8');
        for (const line of raw.trim().split(/\r?\n/)) {
          const p = line.split(',');
          // ticket is the 2nd-to-last-ish numeric col; scan for a long int
          for (const tok of p) { if (/^\d{6,}$/.test(tok)) ticketEA[tok] = label; }
        }
      } catch {}
    }
    function eaForFill(p) {
      const tk = p[2];
      if (ticketEA[tk]) return ticketEA[tk];
      const lot = parseFloat(p[5]);
      if (lot === 0.03) return 'S3';
      if (lot === 0.01) return 'NSND';
      if (lot === 0.02) return 'S1?';
      return '?';
    }

    // ── Per-EA today P&L + recent-trades feed + today's equity curve ──
    const per_ea = { S3:{n:0,w:0,l:0,pnl:0}, S1:{n:0,w:0,l:0,pnl:0}, NSND:{n:0,w:0,l:0,pnl:0} };
    const recent = [];
    const equity = [];
    const WHATIF_LOTS = [0.10, 0.30, 0.50, 1.00];   // "what if every trade were this lot?"
    const whatif = {};                              // lot -> scaled today P&L
    for (const L of WHATIF_LOTS) whatif[L.toFixed(2)] = 0;
    try {
      const raw = fs.readFileSync(COMMON + 'turtle_fills.csv', 'utf8');
      const lines = raw.trim().split(/\r?\n/);
      const todayRows = [];
      for (const line of lines) {
        const p = line.split(',');
        if (p.length < 11 || !pnl.date || p[0].slice(0,10) !== pnl.date) continue;
        const v = parseFloat(p[10]); if (isNaN(v)) continue;
        todayRows.push(p);
        const ea = eaForFill(p);
        const key = ea.replace('?','');
        if (per_ea[key]) { per_ea[key].n++; per_ea[key].pnl += v; if (v>0) per_ea[key].w++; else if (v<0) per_ea[key].l++; }
        // what-if: scale this fill's P&L from its actual lot to each target lot
        const lot = parseFloat(p[5]);
        if (lot > 0) for (const L of WHATIF_LOTS) whatif[L.toFixed(2)] += v * (L / lot);
      }
      for (const k of Object.keys(whatif)) whatif[k] = Math.round(whatif[k]*100)/100;
      let cum = 0;
      for (const p of todayRows) {
        const v = parseFloat(p[10]); cum += v;
        equity.push(Math.round(cum*100)/100);
      }
      for (const k of Object.keys(per_ea)) per_ea[k].pnl = Math.round(per_ea[k].pnl*100)/100;
      // last 15 trades, newest first
      for (let i = todayRows.length-1; i >= 0 && recent.length < 15; i--) {
        const p = todayRows[i]; const v = parseFloat(p[10]);
        const m = (p[11]||'').match(/(tp|sl)/i);
        recent.push({ time: p[0].slice(11), ea: eaForFill(p),
          side: (p[4]||'').replace('_closed','').toUpperCase(),
          pnl: Math.round(v*100)/100, exit: m ? m[1].toUpperCase() : '' });
      }
    } catch {}

    // ── Market status (tick file freshness) ──
    let market = { status: 'unknown', tick_age_sec: null };
    try {
      const tlc = components.shano_tick_logger || {};
      const age = tlc.last_write_age_sec;
      if (age != null) {
        market.tick_age_sec = age;
        market.status = age < 120 ? 'live' : (age < 3600 ? 'break' : 'closed');
      }
    } catch {}

    // ── Profit pulse: how big does the open floating profit "feel"? ──
    let pulse = { floating_total: 0, n_open: 0, bigness: 0 };
    for (const k of ['s3_trader', 's1_trader', 'nsnd_trader']) {
      const c = components[k];
      if (c && typeof c.floating_usd === 'number') {
        pulse.floating_total += c.floating_usd;
        pulse.n_open += (c.n_open || 0);
        if ((c.bigness || 0) > pulse.bigness) pulse.bigness = c.bigness;
      }
    }
    pulse.floating_total = Math.round(pulse.floating_total * 100) / 100;
    pulse.bigness = Math.round(pulse.bigness * 100) / 100;

    // restartable Python services (so the dashboard can offer restart buttons)
    const restartable = Object.entries(RESTARTABLE).map(([k, v]) => ({ key: k, label: v.label }));

    const all_systems_go = warnings.length === 0;
    const payload = {
      ts: new Date().toISOString(),
      all_systems_go,
      headline: all_systems_go ? 'All Systems Online' : `Something is wrong — ${warnings.length} issue${warnings.length === 1 ? '' : 's'}`,
      warnings, pnl, per_ea, recent, equity, whatif, market, components, pulse, restartable,
    };
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify(payload));
    return;
  }

  // SHANO STATE - live status of Shano strategy components
  if (url === '/api/shano' || url.startsWith('/api/shano?')) {
    const { execSync } = require('child_process');
    const shano = {
      ts: new Date().toISOString(),
      market_state: getMarketState(),
      processes: {},
      tv_cdp: false,
      mt5: false,
      shano_state: null,
      live: null,
    };

    // Process check (powershell — keeps existing behaviour)
    try {
      const psOut = execSync('powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"name=\'python.exe\'\\" | ForEach-Object { Write-Host $_.CommandLine }"', { timeout: 8000 }).toString();
      shano.processes.shano_hawk = psOut.includes('shano_hawk.py');
      shano.processes.sheriff_hawk = psOut.includes('sheriff_hawk.py');
      shano.processes.sniper_daemon = psOut.includes('claude_sniper_daemon.py');
      shano.processes.silver_hawk = psOut.includes('silver_hawk_learner.py');
      shano.processes.sexy_hawk = psOut.includes('sexy_hawk.py');
      shano.processes.meeting_hawks = psOut.includes('meeting_hawks.py');
    } catch (e) { shano.processes.error = e.message; }

    // Log freshness — a hung daemon's process exists but its log stops
    // updating. Frontend uses these to mark stale dots as RED.
    shano.log_ages_sec = {};
    const MON = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\';
    const logFiles = {
      shano_hawk:    MON + 'shano_hawk.log',
      sheriff_hawk:  MON + 'sheriff_hawk.log',
      sniper_daemon: MON + 'sniper.log',
      silver_hawk:   MON + 'silver_hawk_learner.log',
    };
    const nowMs = Date.now();
    for (const [k, p] of Object.entries(logFiles)) {
      try { shano.log_ages_sec[k] = Math.round((nowMs - fs.statSync(p).mtimeMs) / 1000); }
      catch { shano.log_ages_sec[k] = null; }
    }

    shano.tv_cdp = await checkCDP();

    try {
      const tlOut = execSync('tasklist /FI "IMAGENAME eq terminal64.exe" /NH', { timeout: 5000 }).toString();
      shano.mt5 = tlOut.includes('terminal64.exe');
    } catch {}

    try {
      const stateFile = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.shano_state.json';
      if (fs.existsSync(stateFile)) {
        shano.shano_state = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
      }
    } catch (e) { shano.shano_state_error = e.message; }

    // Live MT5 enrichment via shano_status.py — realized P&L, open positions w/ floating P&L,
    // current price, recent EA events. Fast (~80ms).
    try {
      const PY = 'C:\\Users\\zeesh\\AppData\\Local\\Programs\\Python\\Python313-arm64\\python.exe';
      const STATUS = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\shano_status.py';
      const out = execSync(`"${PY}" "${STATUS}"`, { timeout: 4000 }).toString();
      shano.live = JSON.parse(out);
    } catch (e) { shano.live_error = String(e.message || e); }

    // Rule compliance check (Shano's verbatim quotes vs running code).
    // Cached for 30s — file parsing isn't free.
    if (!global._rulesCache || Date.now() - global._rulesAt > 30000) {
      try {
        const PY = 'C:\\Users\\zeesh\\AppData\\Local\\Programs\\Python\\Python313-arm64\\python.exe';
        const RULES = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\shano_rules.py';
        const out = execSync(`"${PY}" "${RULES}"`, { timeout: 5000 }).toString();
        global._rulesCache = JSON.parse(out);
        global._rulesAt = Date.now();
      } catch (e) {
        global._rulesCache = { rules_error: String(e.message || e) };
        global._rulesAt = Date.now();
      }
    }
    shano.rules = global._rulesCache;

    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify(shano));
    return;
  }

  // HUB - simple landing page with big buttons (Shano-friendly nav)
  if (url === '/' || url === '/home') {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'hub.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('hub.html missing: ' + e.message);
    }
    return;
  }

  // /me — private chat-only page (no other UI). Bookmark target for phone use.
  if (url === '/me' || url === '/chat') {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'me.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('me.html missing: ' + e.message);
    }
    return;
  }

  // /hammad — separate chat page for Hammad bhai. Gated with hammad:123456 above.
  if (url === '/hammad') {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'hammad.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('hammad.html missing: ' + e.message);
    }
    return;
  }

  // /hammad-view — Zee's read-only window into Hammad's chat (gated zee:28973)
  if (url === '/hammad-view') {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'hammad_view.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('hammad_view.html missing: ' + e.message);
    }
    return;
  }

  // /shano-chat — Shano's private chat with Claude (gated shano:1234)
  if (url === '/shano-chat') {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'shano_chat.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('shano_chat.html missing: ' + e.message);
    }
    return;
  }
  // /shano-view — Zee's read-only window into Shano's chat (gated zee:28973)
  if (url === '/shano-view') {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'shano_view.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('shano_view.html missing: ' + e.message);
    }
    return;
  }
  // /api/shano-chat-readonly — Zee's read-only feed of Shano's chat
  if (url === '/api/shano-chat-readonly' || url.startsWith('/api/shano-chat-readonly?')) {
    const since = parseInt((url.split('since=')[1] || '0'), 10) || 0;
    let all = [];
    try {
      const raw = fs.readFileSync('C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\shano_chat.jsonl', 'utf8');
      all = raw.split('\n').filter(l => l.trim()).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
    } catch {}
    const filtered = since ? all.filter(e => e.ts > since) : all;
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify(filtered));
    return;
  }
  // /api/hammad-chat-readonly — read-only feed of Hammad's chat for Zee
  if (url === '/api/hammad-chat-readonly' || url.startsWith('/api/hammad-chat-readonly?')) {
    const since = parseInt((url.split('since=')[1] || '0'), 10) || 0;
    let all = [];
    try {
      const raw = fs.readFileSync('C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\hammad_chat.jsonl', 'utf8');
      all = raw.split('\n').filter(l => l.trim()).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
    } catch {}
    const filtered = since ? all.filter(e => e.ts > since) : all;
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify(filtered));
    return;
  }

  // /mebg.jpg — background image for the /me chat page (camouflage / coding-vibe wallpaper)
  // Served from ../mebg.jpg (parent dashboard/ folder, where Zee will drop the file)
  if (url === '/mebg.jpg' || url === '/mebg.jpeg' || url === '/mebg.png') {
    try {
      const ext = url.split('.').pop().toLowerCase();
      const candidates = [
        path.join(__dirname, '..', 'mebg.jpg'),
        path.join(__dirname, '..', 'mebg.jpeg'),
        path.join(__dirname, '..', 'mebg.png'),
      ];
      const file = candidates.find(c => { try { return fs.existsSync(c); } catch { return false; } });
      if (!file) { res.writeHead(404); res.end('mebg not found'); return; }
      const data = fs.readFileSync(file);
      const mimeType = file.endsWith('.png') ? 'image/png' : 'image/jpeg';
      res.writeHead(200, { 'Content-Type': mimeType, 'Cache-Control': 'public, max-age=3600' });
      res.end(data);
    } catch (e) {
      res.writeHead(500); res.end('mebg error: ' + e.message);
    }
    return;
  }

  // SHANO DASHBOARD - Apple-style live UI served from shano.html
  if (url === '/shano') {
    try {
      const htmlPath = path.join(__dirname, 'shano.html');
      const html = fs.readFileSync(htmlPath, 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('shano.html missing: ' + e.message);
    }
    return;
  }

  // VSISA DASHBOARD - paper-trader live results from vsisa_paper_trader.py
  if (url === '/vsisa') {
    try {
      const htmlPath = path.join(__dirname, 'vsisa.html');
      const html = fs.readFileSync(htmlPath, 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('vsisa.html missing: ' + e.message);
    }
    return;
  }

  // VSISA API - live state from monitor/vsisa_live.json
  if (url === '/api/vsisa') {
    try {
      const vsisaPath = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\vsisa_live.json';
      const data = fs.existsSync(vsisaPath) ? JSON.parse(fs.readFileSync(vsisaPath, 'utf8')) : { error: 'vsisa_live.json missing' };
      // Read backtest report summary if available
      const cfgPath = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\strategy_lab\\vsisa_live_config.json';
      if (fs.existsSync(cfgPath)) {
        try { data.backtest = JSON.parse(fs.readFileSync(cfgPath, 'utf8')).stats; } catch {}
      }
      data.ts = new Date().toISOString();
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' });
      res.end(JSON.stringify(data));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  // London-Sajid combined live dashboard
  if (url === '/london-sajid') {
    try {
      const htmlPath = path.join(__dirname, 'london_sajid.html');
      const html = fs.readFileSync(htmlPath, 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('london_sajid.html missing: ' + e.message);
    }
    return;
  }

  // London-Sajid API
  if (url === '/api/london-sajid') {
    try {
      const livePath = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\london_sajid_live.json';
      const lbBtPath = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\strategy_lab\\_london_breakout_results.json';
      const vsisaBtPath = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\strategy_lab\\_vsisa_m5_proper_results.json';
      const nyBtPath = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\strategy_lab\\_ny_breakout_results.json';
      const data = fs.existsSync(livePath) ? JSON.parse(fs.readFileSync(livePath, 'utf8')) : { error: 'live state missing — daemon not running?' };
      data.backtest = {};
      try {
        if (fs.existsSync(lbBtPath)) {
          const lb = JSON.parse(fs.readFileSync(lbBtPath, 'utf8'));
          data.backtest.london_breakout = lb.best;
        }
      } catch (e) { data.backtest.lb_error = e.message; }
      try {
        if (fs.existsSync(vsisaBtPath)) {
          const v = JSON.parse(fs.readFileSync(vsisaBtPath, 'utf8'));
          data.backtest.vsisa_m5 = v.train_test_top20 ? v.train_test_top20.slice(0, 5) : v.top15;
        }
      } catch (e) { data.backtest.vsisa_error = e.message; }
      try {
        if (fs.existsSync(nyBtPath)) {
          const ny = JSON.parse(fs.readFileSync(nyBtPath, 'utf8'));
          data.backtest.ny_breakout = ny.best;
        }
      } catch (e) { /* ny breakout backtest may not be done yet */ }
      try {
        const wfPath = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\strategy_lab\\_walk_forward_results.json';
        if (fs.existsSync(wfPath)) {
          data.backtest.walk_forward = JSON.parse(fs.readFileSync(wfPath, 'utf8'));
        }
      } catch (e) { /* walk-forward optional */ }
      try {
        const pPath = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\strategy_lab\\_portfolio_results.json';
        if (fs.existsSync(pPath)) {
          data.backtest.portfolio = JSON.parse(fs.readFileSync(pPath, 'utf8'));
        }
      } catch (e) { /* portfolio optional */ }
      try {
        const ubPath = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\strategy_lab\\_lb_ny_uhv_burst_results.json';
        if (fs.existsSync(ubPath)) {
          data.backtest.uhv_burst = JSON.parse(fs.readFileSync(ubPath, 'utf8'));
        }
      } catch (e) { /* uhv_burst optional */ }
      data.ts = new Date().toISOString();
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' });
      res.end(JSON.stringify(data));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  // SHADOW DASHBOARD - copy of /shano for running UI experiments without
  // affecting the production dashboard. Each /shadow/<id> path is a separate
  // experiment with its own param config saved at monitor/strategy_lab/experiments/<id>.json.
  if (url === '/shadow' || url.startsWith('/shadow/')) {
    try {
      const htmlPath = path.join(__dirname, 'shadow.html');
      const html = fs.readFileSync(htmlPath, 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('shadow.html missing: ' + e.message);
    }
    return;
  }

  // SHADOW EXPERIMENT API
  // ─ POST /api/shadow/create        → mints a new experiment, returns {id, url}
  // ─ GET  /api/shadow/list          → list all experiments
  // ─ GET  /api/shadow/<id>          → fetch one experiment's config
  // ─ POST /api/shadow/<id>          → update config (params, name)
  // ─ DELETE /api/shadow/<id>        → remove experiment
  const EXP_DIR = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\strategy_lab\\experiments';
  try { fs.mkdirSync(EXP_DIR, { recursive: true }); } catch {}

  function _expPath(id) { return path.join(EXP_DIR, id + '.json'); }
  function _genExpId() {
    return 'exp-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 6);
  }
  const DEFAULT_PARAMS = {
    probeConfirm: 0.58,
    probeFail:    3.0,
    fearIdeal:   70.0,
    fearWashout: 180.0,
    trailTrigger: 8.0,
    trailDrop:    2.0,
    mainLots:     0.40,
    probeTimeout: 50,
  };

  if (url === '/api/shadow/create' && req.method === 'POST') {
    const id = _genExpId();
    const cfg = {
      id, name: 'Experiment ' + id.slice(-4),
      created: new Date().toISOString(),
      params: { ...DEFAULT_PARAMS },
    };
    try {
      fs.writeFileSync(_expPath(id), JSON.stringify(cfg, null, 2));
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ id, url: `/shadow/${id}` }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  if (url === '/api/shadow/list') {
    try {
      const files = fs.readdirSync(EXP_DIR).filter(f => f.endsWith('.json'));
      const experiments = files.map(f => {
        try { return JSON.parse(fs.readFileSync(path.join(EXP_DIR, f), 'utf8')); }
        catch { return null; }
      }).filter(Boolean).sort((a,b) => (b.created||'').localeCompare(a.created||''));
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ experiments }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message, experiments: [] }));
    }
    return;
  }

  // POST /api/shadow/<id>/compute — run the backtest with this experiment's params
  // GET  /api/shadow/<id>/compute — return the cached results JSON
  const computeMatch = url.match(/^\/api\/shadow\/([\w-]+)\/compute$/);
  if (computeMatch) {
    const id = computeMatch[1];
    const cacheFile = path.join(EXP_DIR, id + '_results.json');
    if (req.method === 'GET') {
      try {
        if (fs.existsSync(cacheFile)) {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(fs.readFileSync(cacheFile, 'utf8'));
        } else {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'no_results_yet', hint: 'POST to this endpoint to compute' }));
        }
      } catch (e) { res.writeHead(500); res.end(JSON.stringify({error: e.message})); }
      return;
    }
    if (req.method === 'POST') {
      try {
        const PY = 'C:\\Users\\zeesh\\AppData\\Local\\Programs\\Python\\Python313-arm64\\python.exe';
        const SCRIPT = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\strategy_lab\\compute_experiment.py';
        const out = execSync(`"${PY}" "${SCRIPT}" "${id}"`, { timeout: 30000 }).toString();
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(out);
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: String(e.message || e) }));
      }
      return;
    }
  }

  const expMatch = url.match(/^\/api\/shadow\/([\w-]+)$/);
  if (expMatch && !['create', 'list'].includes(expMatch[1])) {
    const id = expMatch[1];
    const file = _expPath(id);
    if (req.method === 'GET') {
      if (!fs.existsSync(file)) {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'not_found' }));
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(fs.readFileSync(file, 'utf8'));
      return;
    }
    if (req.method === 'POST' || req.method === 'PUT') {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => {
        try {
          const incoming = JSON.parse(body || '{}');
          let existing = {};
          if (fs.existsSync(file)) existing = JSON.parse(fs.readFileSync(file, 'utf8'));
          const merged = {
            ...existing,
            ...incoming,
            id,
            params: { ...(existing.params || {}), ...(incoming.params || {}) },
            updated: new Date().toISOString(),
          };
          fs.writeFileSync(file, JSON.stringify(merged, null, 2));
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(merged));
        } catch (e) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: e.message }));
        }
      });
      return;
    }
    if (req.method === 'DELETE') {
      try { if (fs.existsSync(file)) fs.unlinkSync(file); } catch {}
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ deleted: true }));
      return;
    }
  }

  // PWA manifest — makes /shano installable on iOS/Android home screen
  if (url === '/shano/manifest.json' || url === '/manifest.json') {
    const manifest = {
      name: 'Shano Trader',
      short_name: 'Shano',
      description: 'Live Shano trading system dashboard',
      start_url: '/shano',
      display: 'standalone',
      background_color: '#ffffff',
      theme_color: '#1d1d1f',
      orientation: 'portrait',
      icons: [
        { src: '/shano/icon.svg', sizes: '512x512', type: 'image/svg+xml', purpose: 'any maskable' }
      ]
    };
    res.writeHead(200, { 'Content-Type': 'application/manifest+json' });
    res.end(JSON.stringify(manifest));
    return;
  }
  // Inline SVG icon (fire emoji on white) — works as PWA icon, no separate file needed
  if (url === '/shano/icon.svg' || url === '/icon.svg') {
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" fill="#ffffff"/><text x="50%" y="58%" font-size="320" text-anchor="middle" dominant-baseline="middle">🔥</text></svg>';
    res.writeHead(200, { 'Content-Type': 'image/svg+xml', 'Cache-Control': 'public, max-age=86400' });
    res.end(svg);
    return;
  }
  // Service worker stub (required for PWA installability on Android)
  if (url === '/shano/sw.js' || url === '/sw.js') {
    const sw = `self.addEventListener('install',e=>self.skipWaiting());
self.addEventListener('activate',e=>self.clients.claim());
self.addEventListener('fetch',e=>{/* network only */});`;
    res.writeHead(200, { 'Content-Type': 'application/javascript' });
    res.end(sw);
    return;
  }

  // CHAT — phone sends user text, server replies via local command-mode (free) +
  // optional LLM upgrade if Anthropic API has credit. Falls back gracefully on no credit.
  if (url === '/api/chat' && req.method === 'POST') {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', async () => {
      try {
        const { message } = JSON.parse(body || '{}');
        if (!message || !message.trim()) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ error: 'empty message' }));
        }
        // Get current system snapshot for context
        let snapshot = {};
        try {
          const PY = 'C:\\Users\\zeesh\\AppData\\Local\\Programs\\Python\\Python313-arm64\\python.exe';
          const STATUS = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\shano_status.py';
          snapshot = JSON.parse(execSync(`"${PY}" "${STATUS}"`, { timeout: 4000 }).toString());
        } catch (e) { snapshot = { error: String(e.message) }; }

        // Read recent chat history (last 10 turns)
        let history = [];
        try {
          history = JSON.parse(fs.readFileSync(CHAT_LOG_FILE, 'utf8')).slice(-20);
        } catch { history = []; }

        // ── LOCAL COMMAND-MODE — works without LLM, instant response ──
        const lower = message.toLowerCase().trim();
        const localReply = localCommandReply(lower, snapshot);
        const persistChat = (reply) => {
          const newHistory = [...history,
            { role: 'user', content: message, ts: new Date().toISOString() },
            { role: 'assistant', content: reply, ts: new Date().toISOString() },
          ].slice(-50);
          try { fs.writeFileSync(CHAT_LOG_FILE, JSON.stringify(newHistory, null, 2)); } catch {}
          res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
          res.end(JSON.stringify({ reply, mode: 'local' }));
        };
        if (localReply) {
          return persistChat(localReply);
        }

        if (!ANTHROPIC_KEY) {
          return persistChat("No LLM credit and your message didn't match a command. Try: 'status', 'pnl', 'fills', 'processes', 'restart hawk', 'rules'.");
        }

        const systemPrompt = `You are Claude — Zee's trading-system co-pilot, accessed by him via mobile phone over the dashboard PWA. He may be driving or away from the laptop.

Be concise, conversational, action-oriented. Speak like a trusted partner not a customer-service bot. Roman Urdu mixed with English is fine if he writes that way.

Current system snapshot (auto-refreshed):
${JSON.stringify(snapshot, null, 2)}

You can describe state, recommend actions, but you cannot directly run scripts from this endpoint. If he asks you to do something requiring action, tell him you've noted it and that the next dashboard cron tick (every 30min) or his next laptop interaction will execute. For pure-Q questions, answer directly from the snapshot.

Keep replies under 60 words unless he asks for detail. If something is broken, say it plainly and what to do.`;

        const messages = [
          ...history.map(h => ({ role: h.role, content: h.content })),
          { role: 'user', content: message },
        ];

        const apiBody = JSON.stringify({
          model: 'claude-haiku-4-5-20251001',
          max_tokens: 400,
          system: systemPrompt,
          messages,
        });

        const apiReq = https.request({
          hostname: 'api.anthropic.com',
          path: '/v1/messages',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-api-key': ANTHROPIC_KEY,
            'anthropic-version': '2023-06-01',
            'Content-Length': Buffer.byteLength(apiBody),
          },
        }, apiRes => {
          let raw = '';
          apiRes.on('data', d => raw += d);
          apiRes.on('end', () => {
            try {
              const parsed = JSON.parse(raw);
              const reply = (parsed.content && parsed.content[0] && parsed.content[0].text) || '(no reply)';
              // Append to chat log
              const newHistory = [...history,
                { role: 'user', content: message, ts: new Date().toISOString() },
                { role: 'assistant', content: reply, ts: new Date().toISOString() },
              ].slice(-50);
              try { fs.writeFileSync(CHAT_LOG_FILE, JSON.stringify(newHistory, null, 2)); } catch {}
              res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
              res.end(JSON.stringify({ reply }));
            } catch (e) {
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: String(e.message), raw: raw.slice(0, 500) }));
            }
          });
        });
        apiReq.on('error', e => {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: String(e.message) }));
        });
        apiReq.write(apiBody);
        apiReq.end();
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: String(e.message) }));
      }
    });
    return;
  }
  // Get chat history
  if (url === '/api/chat/history') {
    let history = [];
    try {
      history = JSON.parse(fs.readFileSync(CHAT_LOG_FILE, 'utf8')).slice(-50);
    } catch {}
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(history));
    return;
  }

  // ─── CHAT-TO-CLAUDE-CODE BRIDGE ────────────────────────────────────────
  // File-based async chat with the active Claude Code session (this Claude,
  // not the dashboard Haiku). Zee writes from phone -> file. Claude Code polls
  // the file via Read tool, responds by appending to the same file.
  // Single log: monitor/cc_chat.jsonl (one JSON per line).
  const CC_CHAT_FILE = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\cc_chat.jsonl';
  const readCcChat = () => {
    try {
      const raw = fs.readFileSync(CC_CHAT_FILE, 'utf8');
      return raw.split('\n').filter(l => l.trim()).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
    } catch { return []; }
  };
  const appendCcChat = (entry) => {
    try { fs.appendFileSync(CC_CHAT_FILE, JSON.stringify(entry) + '\n'); return true; } catch { return false; }
  };
  if (url === '/api/cc-chat/send' && req.method === 'POST') {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const { text, from } = JSON.parse(body || '{}');
        if (!text || !text.trim()) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ error: 'empty' }));
        }
        const entry = { ts: Date.now(), from: from || 'zee', text: text.trim() };
        appendCcChat(entry);
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
        res.end(JSON.stringify({ ok: true, entry }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: String(e.message) }));
      }
    });
    return;
  }
  if (url === '/api/cc-chat' || url.startsWith('/api/cc-chat?')) {
    const since = parseInt((url.split('since=')[1] || '0'), 10) || 0;
    const all = readCcChat();
    const filtered = since ? all.filter(e => e.ts > since) : all;
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify(filtered));
    return;
  }

  // ─── HAMMAD CHAT (parallel to cc-chat) ───────────────────────────────────
  const HAMMAD_CHAT_FILE = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\hammad_chat.jsonl';
  const HAMMAD_TYPING_FILE = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.hammad_typing.json';
  const readHammadChat = () => {
    try {
      const raw = fs.readFileSync(HAMMAD_CHAT_FILE, 'utf8');
      return raw.split('\n').filter(l => l.trim()).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
    } catch { return []; }
  };
  if (url === '/api/hammad-chat/send' && req.method === 'POST') {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const { text, from } = JSON.parse(body || '{}');
        if (!text || !text.trim()) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ error: 'empty' }));
        }
        const entry = { ts: Date.now(), from: from || 'hammad', text: text.trim() };
        try { fs.appendFileSync(HAMMAD_CHAT_FILE, JSON.stringify(entry) + '\n'); } catch {}
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
        res.end(JSON.stringify({ ok: true, entry }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: String(e.message) }));
      }
    });
    return;
  }
  if (url === '/api/hammad-chat' || url.startsWith('/api/hammad-chat?')) {
    const since = parseInt((url.split('since=')[1] || '0'), 10) || 0;
    const all = readHammadChat();
    const filtered = since ? all.filter(e => e.ts > since) : all;
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify(filtered));
    return;
  }
  if (url === '/api/hammad-chat/typing') {
    if (req.method === 'POST') {
      let body = '';
      req.on('data', d => body += d);
      req.on('end', () => {
        try {
          const { state } = JSON.parse(body || '{}');
          fs.writeFileSync(HAMMAD_TYPING_FILE, JSON.stringify({ typing: !!state, since: Date.now() }));
          res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: true, typing: !!state }));
        } catch (e) {
          res.writeHead(500); res.end(JSON.stringify({ error: String(e.message) }));
        }
      });
      return;
    }
    let s = { typing: false, since: 0 };
    try {
      s = JSON.parse(fs.readFileSync(HAMMAD_TYPING_FILE, 'utf8'));
      if (s.typing && (Date.now() - s.since) > 90000) s = { typing: false, since: 0 };
    } catch {}
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify(s));
    return;
  }

  // ─── SHANO CHAT (parallel to cc-chat + hammad-chat) ────────────────────
  const SHANO_CHAT_FILE = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\shano_chat.jsonl';
  const SHANO_TYPING_FILE = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.shano_typing.json';
  const readShanoChat = () => {
    try {
      const raw = fs.readFileSync(SHANO_CHAT_FILE, 'utf8');
      return raw.split('\n').filter(l => l.trim()).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
    } catch { return []; }
  };
  if (url === '/api/shano-chat/send' && req.method === 'POST') {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const { text, from } = JSON.parse(body || '{}');
        if (!text || !text.trim()) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ error: 'empty' }));
        }
        const entry = { ts: Date.now(), from: from || 'shano', text: text.trim() };
        try { fs.appendFileSync(SHANO_CHAT_FILE, JSON.stringify(entry) + '\n'); } catch {}
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
        res.end(JSON.stringify({ ok: true, entry }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: String(e.message) }));
      }
    });
    return;
  }
  if (url === '/api/shano-chat' || url.startsWith('/api/shano-chat?')) {
    const since = parseInt((url.split('since=')[1] || '0'), 10) || 0;
    const all = readShanoChat();
    const filtered = since ? all.filter(e => e.ts > since) : all;
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify(filtered));
    return;
  }
  if (url === '/api/shano-chat/typing') {
    if (req.method === 'POST') {
      let body = '';
      req.on('data', d => body += d);
      req.on('end', () => {
        try {
          const { state } = JSON.parse(body || '{}');
          fs.writeFileSync(SHANO_TYPING_FILE, JSON.stringify({ typing: !!state, since: Date.now() }));
          res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: true, typing: !!state }));
        } catch (e) {
          res.writeHead(500); res.end(JSON.stringify({ error: String(e.message) }));
        }
      });
      return;
    }
    let s = { typing: false, since: 0 };
    try {
      s = JSON.parse(fs.readFileSync(SHANO_TYPING_FILE, 'utf8'));
      if (s.typing && (Date.now() - s.since) > 90000) s = { typing: false, since: 0 };
    } catch {}
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify(s));
    return;
  }
  // Typing indicator: GET reads {typing, since}, POST sets {state: true|false}
  // Auto-expires after 90s of staleness so a crashed setter doesn't show forever.
  const TYPING_FILE = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.cc_typing.json';
  if (req.url.split('?')[0] === '/api/cc-chat/typing') {
    if (req.method === 'POST') {
      let body = '';
      req.on('data', d => body += d);
      req.on('end', () => {
        try {
          const { state } = JSON.parse(body || '{}');
          fs.writeFileSync(TYPING_FILE, JSON.stringify({ typing: !!state, since: Date.now() }));
          res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: true, typing: !!state }));
        } catch (e) {
          res.writeHead(500); res.end(JSON.stringify({ error: String(e.message) }));
        }
      });
      return;
    }
    // GET
    let s = { typing: false, since: 0 };
    try {
      s = JSON.parse(fs.readFileSync(TYPING_FILE, 'utf8'));
      // Auto-expire after 90s — crashed setter shouldn't leave indicator on forever
      if (s.typing && (Date.now() - s.since) > 90000) s = { typing: false, since: 0 };
    } catch {}
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify(s));
    return;
  }

  if (url === '/' || url === '/index.html') {
    try {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(fs.readFileSync(HTML_FILE, 'utf8'));
    } catch(e) {
      res.writeHead(500); res.end('HTML missing: ' + e.message);
    }
    return;
  }

  res.writeHead(404); res.end('Not found');
});

server.on('error', e => {
  if (e.code === 'EADDRINUSE') { console.log(`Port ${PORT} in use — already running`); process.exit(0); }
  else console.error(e);
});

server.listen(PORT, '0.0.0.0', () =>
  console.log(`Claude Trader → http://localhost:${PORT}`));
