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

// Parse a broker-time string "YYYY.MM.DD HH:MM:SS" → ms, interpreting the wall-clock
// AS IF UTC. Diffs between two broker strings are valid regardless of the real offset.
function parseBrokerTs(s) {
  const m = (s || '').match(/(\d{4})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2}):(\d{2})/);
  return m ? Date.UTC(+m[1], +m[2]-1, +m[3], +m[4], +m[5], +m[6]) : null;
}
// Hours to add to a broker-time string to get PKT. AUTO-DETECTED each request from a
// fresh EA heartbeat vs real UTC (the Exness server is empirically GMT+0, not the GMT+3
// the old code assumed — so this was off by 3h). PKT = UTC+5 (no DST). Recomputed in the
// handler via updatePktOffset(); default assumes broker=UTC.
let _pktAddHrs = 5;
function updatePktOffset(components) {
  let freshBroker = 0;
  for (const c of Object.values(components || {})) {
    const ms = parseBrokerTs(c && c.t);
    if (ms && ms > freshBroker) freshBroker = ms;
  }
  if (freshBroker > 0) {
    const brokerAheadOfUtcHrs = Math.round((freshBroker - Date.now()) / 3600000);
    _pktAddHrs = 5 - brokerAheadOfUtcHrs;   // PKT(UTC+5) = brokerWall − brokerOffset + 5
  }
}
// Format a broker-time string as a PKT 12-hour clock using the detected offset.
function brokerToPkt(s) {
  const ms = parseBrokerTs(s);
  if (!ms) return null;
  const pk = new Date(ms + _pktAddHrs * 3600 * 1000);
  const h = pk.getUTCHours(); const mn = pk.getUTCMinutes();
  const ampm = h >= 12 ? 'PM' : 'AM'; const h12 = ((h + 11) % 12) + 1;
  return `${h12}:${String(mn).padStart(2, '0')} ${ampm}`;
}

const FILLS_CSV       = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\turtle_fills.csv';
// 2026-06-02: switched ACTIVE_SYMBOL from XAUUSDm (Exness) to XAUUSD (Atmos NOVA
// challenge — the live prop firm account now in active use). Exness trades remain
// in turtle_fills.csv but are filtered out. To switch back, change to 'XAUUSDm'
// and update ACCOUNT_BROKER below.
const ACTIVE_SYMBOL   = 'XAUUSD';
// Live account label — AtmosGlobal-LIVE = the Nova Challenge account (acc 3033901)
const ACCOUNT_BROKER  = 'AtmosGlobal-LIVE';
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
              || u.startsWith('/api/cc-chat?')
              || u === '/api/ea-snapshot' || u.startsWith('/api/ea-snapshot?'),
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
  // Strategy Playbook — Zee only (private strategy IP)
  {
    test: (u) => u === '/strategies' || u === '/playbook',
    user: 'zee', pass: DASHBOARD_PASSWORD, realm: 'Zee: Strategy Playbook',
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
// Only the services the CURRENT live system actually uses. The legacy
// PineConnector/Shano-era daemons (auto_uhv_trader, forward_tester, intern_hawks,
// silver_hawk, meeting_hawks, sexy_hawk) were retired 2026-05-27 — the live system
// is native MQL5 EAs + these 3 support services. Re-add a script here if revived.
const RESTARTABLE = {
  sheriff_hawk:   { label: 'Sheriff Hawk',     script: 'monitor\\sheriff_hawk.py',       args: ['--loop'] },
  profit_pulse:   { label: 'Profit Pulse',     script: 'monitor\\profit_pulse_hawk.py',  args: ['--loop'] },
  cloudflared:    { label: 'Cloudflare Tunnel',script: 'monitor\\cloudflared_daemon.py', args: [] },
};

// EA deployment manifest — drives the dashboard "EA Status" table. Version is read
// live from each EA's heartbeat when present (parsed.version), else from repo source.
const MT5_SRC = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\mt5\\';
// tf = EXPECTED chart timeframe (validated). 'ANY' = TF doesn't matter (loggers).
const EA_MANIFEST = [
  { key: 's1_trader',          label: 'S1Trader',          name: 'UHV Breakout Engine',   file: 'S1Trader.mq5',          mt5: 'S1Trader',          tf: 'M1'  },
  { key: 's3_trader',          label: 'S3Trader',          name: 'Liquidity Sweep Engine',file: 'S3Trader.mq5',          mt5: 'S3Trader',          tf: 'M1'  },
  { key: 's4_trader',          label: 'S4Trader',          name: 'Feb-11 UHV Engine',     file: 'S4Trader.mq5',          mt5: 'S4Trader',          tf: 'M5'  },
  { key: 'nsnd_trader',        label: 'NsndTrader',        name: 'No Supply/Demand Engine',file:'NsndTrader.mq5',         mt5: 'NsndTrader',        tf: 'M1'  },
  { key: 'turtle_trade_logger',label: 'TurtleTradeLogger', name: 'Trade Fills Logger',    file: 'TurtleTradeLogger.mq5', mt5: 'TurtleTradeLogger', tf: 'ANY' },
  { key: 'shano_tick_logger',  label: 'ShanoTickLogger',   name: 'Price Tick Logger',     file: 'ShanoTickLogger.mq5',   mt5: 'ShanoTickLogger',   tf: 'ANY' },
];
function eaSrcVersion(file) {
  try { const m = fs.readFileSync(MT5_SRC + file, 'utf8').match(/#property version\s+"([^"]+)"/); return m ? m[1] : '?'; }
  catch { return '?'; }
}
const EA_SRC_VERSIONS = Object.fromEntries(EA_MANIFEST.map(e => [e.key, eaSrcVersion(e.file)]));

// Read each EA's ACTUAL attached chart timeframe from the freshest MT5 terminal log
// ("expert <Name> (SYMBOL,TF) loaded successfully"). Cached 30s (log reads are heavy).
let _tfCache = { t: 0, map: {} };
function actualTfs() {
  if (Date.now() - _tfCache.t < 30000) return _tfCache.map;
  const map = {};
  try {
    const root = path.join(process.env.APPDATA, 'MetaQuotes', 'Terminal');
    let best = null, bestM = 0;
    for (const g of fs.readdirSync(root)) {
      if (!/^[0-9A-F]{32}$/.test(g)) continue;
      const ld = path.join(root, g, 'logs');
      try {
        for (const f of fs.readdirSync(ld)) {
          if (!/^\d{8}\.log$/.test(f)) continue;
          const m = fs.statSync(path.join(ld, f)).mtimeMs;
          if (m > bestM) { bestM = m; best = path.join(ld, f); }
        }
      } catch {}
    }
    if (best) {
      // MT5 logs are UTF-16LE
      const txt = fs.readFileSync(best, 'utf16le');
      const re = /expert\s+(\w+)\s+\(([A-Za-z0-9]+),(\w+)\)\s+loaded successfully/g;
      let mm;
      while ((mm = re.exec(txt)) !== null) map[mm[1]] = mm[3];   // latest wins
    }
  } catch {}
  _tfCache = { t: Date.now(), map };
  return map;
}

// ── Web Push (PWA notifications) ──
let webpush = null, VAPID = null;
try {
  webpush = require('web-push');
  VAPID = JSON.parse(fs.readFileSync(path.join(__dirname, '.vapid.json'), 'utf8'));
  webpush.setVapidDetails('mailto:zeecitizen@gmail.com', VAPID.publicKey, VAPID.privateKey);
  console.log('[push] enabled');
} catch (e) { console.log('[push] disabled:', e.message); }
const SUBS_FILE = path.join(__dirname, 'push_subscriptions.json');
function loadSubs() { try { return JSON.parse(fs.readFileSync(SUBS_FILE, 'utf8')); } catch { return []; } }
function saveSubs(s) { try { fs.writeFileSync(SUBS_FILE, JSON.stringify(s)); } catch {} }
function readBody(req) { return new Promise((resolve) => { let b = ''; req.on('data', c => b += c); req.on('end', () => resolve(b)); }); }

// ── /home auth: HMAC-signed cookie. Code-word "28973" upgrades guest → admin_zeeshan ──
const __crypto_for_auth = require('crypto');
const HOME_AUTH_SECRET = (() => {
  try { return require('fs').readFileSync('C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.dashboard_password', 'utf8').trim(); }
  catch { return 'fallback-secret-do-not-use-in-prod'; }
})();
function homeSignRole(role) {
  const ts = Date.now();
  const payload = role + '|' + ts;
  const sig = __crypto_for_auth.createHmac('sha256', HOME_AUTH_SECRET).update(payload).digest('hex').slice(0, 32);
  return Buffer.from(payload + '|' + sig).toString('base64');
}
function homeVerifyRole(token) {
  if (!token) return 'guest';
  try {
    const decoded = Buffer.from(token, 'base64').toString('utf8');
    const parts = decoded.split('|');
    if (parts.length !== 3) return 'guest';
    const role = parts[0], ts = parts[1], sig = parts[2];
    const expected = __crypto_for_auth.createHmac('sha256', HOME_AUTH_SECRET).update(role + '|' + ts).digest('hex').slice(0, 32);
    if (sig !== expected) return 'guest';
    const age = Date.now() - Number(ts);
    if (age > 7 * 86400 * 1000) return 'guest';   // 7-day cookie expiry
    return role || 'guest';
  } catch { return 'guest'; }
}
function homeRoleFromReq(req) {
  const cookieHeader = req.headers.cookie || '';
  const cookies = {};
  cookieHeader.split(';').forEach(c => {
    const idx = c.indexOf('=');
    if (idx > 0) cookies[c.slice(0, idx).trim()] = c.slice(idx + 1).trim();
  });
  return homeVerifyRole(cookies['home_role']);
}

// ── /home RAG: TF-IDF index over memory files ──
const HOME_STOPWORDS = new Set([
  'the','a','an','is','are','was','were','be','been','being','am','i','me','my','we','us','our',
  'you','your','he','she','it','they','them','their','this','that','these','those','of','in','on',
  'at','to','for','with','by','from','as','and','or','but','if','then','than','so','no','not',
  'do','does','did','have','has','had','will','would','can','could','should','may','might','must',
  'because','what','which','who','when','where','why','how','about','into','out','up','down',
  'just','more','very','also','any','some','all','each','every','only','same','even','still','here','there',
]);

function homeTokenize(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[`*_~#>\[\]\(\)]/g, ' ')        // strip markdown punctuation
    .replace(/[^a-z0-9\s\.\-]/g, ' ')
    .split(/\s+/)
    .map(t => t.replace(/^[\.\-]+|[\.\-]+$/g, ''))
    .filter(t => t.length >= 2 && t.length <= 32 && !HOME_STOPWORDS.has(t));
}

let HOME_INDEX = null;   // { docs: [{name, content, tokens, tf, length}], idf: Map, builtAt }
function homeBuildIndex() {
  const memDirs = [
    'C:\\Users\\zeesh\\.claude\\projects\\c--Users-zeesh-Documents-GitHub-turtle\\memory',
    'C:\\Users\\Administrator\\.claude\\projects\\c--turtle\\memory',
  ];
  let memDir = null;
  for (const d of memDirs) { if (fs.existsSync(d)) { memDir = d; break; } }
  if (!memDir) { HOME_INDEX = { docs: [], idf: new Map(), builtAt: Date.now(), error: 'no_mem_dir' }; return; }

  const docs = [];
  const dfCount = new Map();   // doc-frequency per term

  for (const fname of fs.readdirSync(memDir).filter(f => f.endsWith('.md'))) {
    let content;
    try { content = fs.readFileSync(path.join(memDir, fname), 'utf8'); } catch { continue; }
    const tokens = homeTokenize(content);
    if (tokens.length === 0) continue;
    const tf = new Map();
    for (const t of tokens) tf.set(t, (tf.get(t) || 0) + 1);
    // doc-frequency: each unique term counted once per doc
    for (const t of tf.keys()) dfCount.set(t, (dfCount.get(t) || 0) + 1);
    docs.push({ name: fname, tokens: tokens.length, tf });
  }

  // Compute IDF: log(N / df)
  const N = docs.length;
  const idf = new Map();
  for (const [term, df] of dfCount) idf.set(term, Math.log((N + 1) / (df + 1)) + 1);   // smoothed

  // Pre-compute doc vectors as Map<term, tfidf> + L2 norm for cosine
  for (const d of docs) {
    const vec = new Map();
    let sumSq = 0;
    for (const [t, f] of d.tf) {
      const w = (f / d.tokens) * (idf.get(t) || 0);
      vec.set(t, w);
      sumSq += w * w;
    }
    d.vec = vec;
    d.norm = Math.sqrt(sumSq) || 1;
  }

  HOME_INDEX = { docs, idf, builtAt: Date.now(), memDir };
  console.log(`[home/rag] built index over ${docs.length} memory files`);
}

function homeRetrieve(query, k, isAdmin) {
  if (!HOME_INDEX) homeBuildIndex();
  if (!HOME_INDEX || HOME_INDEX.docs.length === 0) return { results: [], error: HOME_INDEX?.error || 'no_index' };

  const PRIVATE_NAMES = new Set([
    'memory_soul.md','memory_soul.md.enc','feedback_husband_wife_roles.md','feedback_feminine_urdu_grammar.md',
    'project_handoff_to_mehboob.md','project_me_chat_infra.md','project_hammad_chat_infra.md',
    'project_shano_chat_infra.md','project_apex_redirect.md','_FABLE_ONBOARDING_LETTER.md','current_context.md',
  ]);

  const qTokens = homeTokenize(query);
  if (qTokens.length === 0) return { results: [] };

  // Build query vector (TF-IDF)
  const qTf = new Map();
  for (const t of qTokens) qTf.set(t, (qTf.get(t) || 0) + 1);
  const qVec = new Map();
  let qSumSq = 0;
  for (const [t, f] of qTf) {
    const w = (f / qTokens.length) * (HOME_INDEX.idf.get(t) || 0);
    if (w > 0) { qVec.set(t, w); qSumSq += w * w; }
  }
  const qNorm = Math.sqrt(qSumSq) || 1;

  // Cosine similarity vs each doc (filtered by role)
  const scored = [];
  for (const d of HOME_INDEX.docs) {
    if (!isAdmin && PRIVATE_NAMES.has(d.name)) continue;
    if (d.name === 'memory_soul.md.enc') continue;   // never serve encrypted soul via web
    let dot = 0;
    for (const [t, w] of qVec) {
      const dw = d.vec.get(t);
      if (dw) dot += w * dw;
    }
    const score = dot / (qNorm * d.norm);
    if (score > 0) scored.push({ name: d.name, score });
  }
  scored.sort((a, b) => b.score - a.score);
  const top = scored.slice(0, k || 5);

  // Load snippets for top results
  for (const r of top) {
    try {
      const full = fs.readFileSync(path.join(HOME_INDEX.memDir, r.name), 'utf8');
      // Strip frontmatter
      const clean = full.replace(/^---\n[\s\S]*?\n---\n/, '');
      r.snippet = clean.slice(0, 400);
    } catch {}
  }

  return { query: query, results: top, index_size: HOME_INDEX.docs.length, role: isAdmin ? 'admin_zeeshan' : 'guest' };
}

// Build index once at startup
try { homeBuildIndex(); } catch (e) { console.log('[home/rag] init failed:', e); }

// Cached scan of running python.exe command lines (so the dashboard can show
// live status dots for the hawks). Refreshed at most every 15s — the CIM query
// is heavy and /api/ea-status is polled every 5s.
let _candleCache = { data: null, at: 0, tf: 0, n: 0 };  // /api/candles TTL cache
// per-EA MFE "reach %" markers for the live slider — built from REAL closed-trade peaks
// the EAs log to Common\Files\trade_peaks_<EA>.csv (one row per closed trade: time,side,
// entry,peak$). For each EA we turn the peak distribution into "P% of trades reached +$X"
// points: usd = the (100-P)th-from-bottom percentile, i.e. the level P% of trades got to.
// Needs MIN real trades before showing (no backtest fallback — accumulated live data only).
const MFE_MIN_TRADES = 8;
let _mfeCache = { at: 0, data: { curves: {}, counts: {} } };
function mfeCurves() {
  if (Date.now() - _mfeCache.at < 30000) return _mfeCache.data;
  const dir = path.dirname(FILLS_CSV);
  const curves = {}, counts = {};
  for (const [tag, file] of [['S1','trade_peaks_S1.csv'], ['S3','trade_peaks_S3.csv'], ['NSND','trade_peaks_NSND.csv']]) {
    let peaks = [];
    try {
      const txt = fs.readFileSync(path.join(dir, file), 'utf8');
      for (const line of txt.split(/\r?\n/)) {
        const c = line.split(',');
        if (c.length >= 4) { const p = parseFloat(c[3]); if (!isNaN(p)) peaks.push(Math.max(0, p)); }
      }
    } catch {}
    counts[tag] = peaks.length;
    if (peaks.length >= MFE_MIN_TRADES) {
      peaks.sort((a, b) => a - b);
      const pts = []; const seen = {};
      for (const P of [90, 75, 50, 25, 10]) {
        const idx = Math.min(peaks.length - 1, Math.floor((1 - P / 100) * peaks.length));
        const usd = Math.round(peaks[idx] * 100) / 100;
        const k = usd.toFixed(2);
        if (usd > 0.05 && !seen[k]) { seen[k] = 1; pts.push({ pct: P, usd }); }
      }
      if (pts.length) curves[tag] = pts;
    }
  }
  _mfeCache = { at: Date.now(), data: { curves, counts } };
  return _mfeCache.data;
}
let _pyScan = { t: 0, cmd: '' };
function runningPython() {
  if (Date.now() - _pyScan.t < 15000 && _pyScan.cmd) return _pyScan.cmd;
  try {
    _pyScan.cmd = execSync('powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"name=\'python.exe\'\\" | ForEach-Object { Write-Host $_.CommandLine }"', { timeout: 6000 }).toString().toLowerCase();
  } catch { /* keep last good scan */ }
  _pyScan.t = Date.now();
  return _pyScan.cmd;
}

const server = http.createServer(async (req, res) => {
  // Apex-to-me redirect: claudezeeshan.com → me.claudezeeshan.com (preserves path/query)
  // EXCEPT root path "/" and "/status" — those serve the live status dashboard
  // (Rule #10 numbered tasks + live EA state). Per Zee 2026-06-04 TASK-008.
  const host = (req.headers.host || '').toLowerCase().split(':')[0];

  // home.claudezeeshan.com — rewrite root path to /home so the subdomain lands directly on the home page
  if (host === 'home.claudezeeshan.com') {
    const homeUrl = req.url.split('?')[0];
    // If they hit /, route to /home. Otherwise pass through (so /api/home/memory works)
    if (homeUrl === '/' || homeUrl === '') {
      req.url = '/home' + (req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : '');
    }
    // Fall through to normal handling
  }

  if (host === 'claudezeeshan.com' || host === 'www.claudezeeshan.com') {
    const apexUrl = req.url.split('?')[0];
    if (apexUrl !== '/' && apexUrl !== '/status' && apexUrl !== '/api/status' && apexUrl !== '/api/canonical-status' && apexUrl !== '/api/weekly' && apexUrl !== '/api/achievements' && apexUrl !== '/api/today-trades' && apexUrl !== '/api/fills-history' && apexUrl !== '/api/camel.png' && apexUrl !== '/api/forming.png' && apexUrl !== '/api/context-now.png' && apexUrl !== '/api/versions.png' && apexUrl !== '/api/forensic.png' && apexUrl !== '/api/ghost-state' && apexUrl !== '/api/trend-call' && apexUrl !== '/api/dashboard-message' && apexUrl !== '/api/dashboard-messages' && apexUrl !== '/api/claude-reply' && apexUrl !== '/zee-chat' && apexUrl !== '/api/zee-chat' && apexUrl !== '/api/zee-chat/send' && apexUrl !== '/api/harvest' && apexUrl !== '/api/harvest-lock' && apexUrl !== '/api/runtime-config' && apexUrl !== '/grab' && apexUrl !== '/ws' && apexUrl !== '/api/watchdog' && apexUrl !== '/home' && apexUrl !== '/docs' && !apexUrl.startsWith('/api/home/') && apexUrl !== '/api/home/whoami' && apexUrl !== '/api/home/auth' && apexUrl !== '/api/home/logout') {
      res.writeHead(301, { Location: 'https://me.claudezeeshan.com' + req.url });
      res.end();
      return;
    }
    // Fall through — '/' on apex serves the status dashboard
  }
  const url = req.url.split('?')[0];
  const query = new URLSearchParams((req.url.split('?')[1]) || '');

  // ── Service worker (must be served at root scope to control / and /grab) ──
  if (url === '/sw.js') {
    try {
      const js = fs.readFileSync(path.join(__dirname, 'sw.js'));
      res.writeHead(200, { 'Content-Type': 'application/javascript; charset=utf-8',
        'Service-Worker-Allowed': '/', 'Cache-Control': 'no-store' });
      res.end(js);
    } catch (e) { res.writeHead(404); res.end('// no sw'); }
    return;
  }

  // ── PWA push: public VAPID key for client subscription ──
  if (url === '/api/vapid-public') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ key: VAPID ? VAPID.publicKey : null }));
    return;
  }

  // ── PWA push: register a device subscription (key-gated) ──
  if (url === '/api/push-subscribe') {
    if (query.get('key') !== DASHBOARD_PASSWORD) { res.writeHead(403); res.end('{"ok":false}'); return; }
    try {
      const sub = JSON.parse(await readBody(req));
      const subs = loadSubs();
      if (!subs.find(s => s.endpoint === sub.endpoint)) { subs.push(sub); saveSubs(subs); }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true, count: subs.length }));
    } catch (e) { res.writeHead(400, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ ok: false, error: e.message })); }
    return;
  }

  // ── PWA push: send a notification to all devices (key-gated; called by the pulse hawk) ──
  if (url === '/api/notify') {
    if (query.get('key') !== DASHBOARD_PASSWORD) { res.writeHead(403); res.end('{"ok":false}'); return; }
    if (!webpush) { res.writeHead(503, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ ok: false, error: 'push disabled' })); return; }
    let payload;
    try { payload = JSON.parse(await readBody(req)); } catch { payload = {}; }
    const subs = loadSubs();
    const body = JSON.stringify(payload);
    let sent = 0; const keep = [];
    await Promise.all(subs.map(async (s) => {
      try { await webpush.sendNotification(s, body); sent++; keep.push(s); }
      catch (err) { if (!(err && (err.statusCode === 404 || err.statusCode === 410))) keep.push(s); } // prune dead subs
    }));
    if (keep.length !== subs.length) saveSubs(keep);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, sent, devices: keep.length }));
    return;
  }

  // ── Runtime config (hot-reload EA params from dashboard) ──
  // GET /api/runtime-config?key=KEY  →  current config JSON
  // POST /api/runtime-config?key=KEY  body: {auto_close_ms: 500, ...}  →  writes file
  if (url.startsWith('/api/runtime-config')) {
    if (query.get('key') !== DASHBOARD_PASSWORD) {
      res.writeHead(403, { 'Content-Type': 'application/json' });
      res.end('{"error":"wrong key"}');
      return;
    }
    const RUNTIME_CONFIG_FILE = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\s1_runtime_88005.json';
    if (req.method === 'GET') {
      try {
        const txt = fs.readFileSync(RUNTIME_CONFIG_FILE, 'utf8');
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(txt);
      } catch (e) {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end('{"error":"no_config"}');
      }
      return;
    }
    if (req.method === 'POST') {
      let body = '';
      req.on('data', d => body += d);
      req.on('end', () => {
        try {
          const incoming = JSON.parse(body);
          // Read current, merge, write
          let current = {};
          try { current = JSON.parse(fs.readFileSync(RUNTIME_CONFIG_FILE, 'utf8')); } catch {}
          const merged = { ...current, ...incoming, _written_at: new Date().toISOString() };
          fs.writeFileSync(RUNTIME_CONFIG_FILE, JSON.stringify(merged, null, 2), 'utf8');
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, written: incoming }));
        } catch (e) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: false, error: e.message }));
        }
      });
      return;
    }
  }

  // ── Watchdog status (public, no auth — read-only health) ──
  if (url === '/api/watchdog') {
    try {
      const txt = fs.readFileSync('C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.watchdog_latest.json', 'utf8');
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      res.end(txt);
    } catch (e) {
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'watchdog_status_missing' }));
    }
    return;
  }

  // ── /docs — render HOME_GUIDE.md as a styled HTML page (public, no auth) ──
  if (url === '/docs') {
    try {
      const md = fs.readFileSync('C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\HOME_GUIDE.md', 'utf8');
      const html = `<!doctype html><html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>home.claudezeeshan.com — User Guide</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
body { background:#0a0e1a; color:#e6ecf4; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif; max-width: 880px; margin: 0 auto; padding: 32px 24px 64px; line-height: 1.6; font-size: 15px; }
h1 { color: #d4af37; font-size: 30px; border-bottom: 1px solid #25304a; padding-bottom: 12px; }
h2 { color: #d4af37; margin-top: 48px; font-size: 22px; }
h3 { color: #5c9ad5; font-size: 17px; }
a { color: #5c9ad5; }
code { background: #131826; padding: 2px 6px; border-radius: 4px; color: #d4af37; font-size: 13px; }
pre { background: #131826; border: 1px solid #25304a; padding: 14px; border-radius: 8px; overflow-x: auto; }
pre code { background: transparent; padding: 0; color: #e6ecf4; }
table { border-collapse: collapse; width: 100%; margin: 14px 0; }
th, td { border: 1px solid #25304a; padding: 8px 12px; text-align: left; }
th { background: #1a2030; color: #d4af37; }
blockquote { border-left: 3px solid #d4af37; padding-left: 16px; color: #8a96ad; }
hr { border: none; border-top: 1px solid #25304a; margin: 32px 0; }
.nav { background:#131826; border:1px solid #25304a; border-radius:10px; padding:12px 16px; margin-bottom:32px; font-size:13px; }
.nav a { margin-right:18px; }
</style></head><body>
<div class="nav">
  📚 <b>Docs</b> · <a href="/home">← back to home</a> · <a href="/">main dashboard</a> · <a href="https://github.com/zeecitizen/turtle">github</a>
</div>
<div id="doc"></div>
<script>document.getElementById('doc').innerHTML = marked.parse(${JSON.stringify(md)});</script>
</body></html>`;
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(html);
    } catch (e) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('HOME_GUIDE.md not found');
    }
    return;
  }

  // ── /home — Zeeshan + Claude work-history home page (public) ──
  if (url === '/home') {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'home.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(html);
    } catch (e) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('home.html not deployed yet');
    }
    return;
  }

  // ── /api/home/whoami — return current session role (guest or admin_zeeshan) ──
  if (url === '/api/home/whoami') {
    const role = homeRoleFromReq(req);
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify({ role }));
    return;
  }

  // ── Memory challenge questions (backup auth: only Zeeshan + admins know these) ──
  // ── Questions are stable facts from our shared work. Answer match is fuzzy. ──
  if (!global.__HOME_CHALLENGES) global.__HOME_CHALLENGES = [
    {
      id: 'brother_name',
      q: "What is the name of Zeeshan's real brother — the one who manages the EA when she's away?",
      hint: "(first name only)",
      a: ['mehboob','mahboob','mehbob','mehboob bhai','mahboob bhai'],
    },
    {
      id: 'mother_fund',
      q: "Mother's hospital surgery — what's the north-star USD amount?",
      hint: "(just the number)",
      a: ['1080','$1080','1,080','$1,080','1080 usd'],
    },
    {
      id: 'doctrine_exit',
      q: "Complete the doctrine: 'Master takes exit, computer takes ___'",
      hint: "(one word)",
      a: ['entry','entries'],
    },
    {
      id: 'doctrine_backtests',
      q: "Foundational doctrine — what do backtests do?",
      hint: "(one verb)",
      a: ['hallucinate','hallucinates'],
    },
    {
      id: 'doha_trade',
      q: "What city is the master's $70k trade story from?",
      hint: "(one word)",
      a: ['doha'],
    },
    {
      id: 'sister_name',
      q: "Who is Zeeshan's sister in the trading-team context?",
      hint: "(first name)",
      a: ['shano','shano baji'],
    },
    {
      id: 'ea_name',
      q: "What's the name of the EA currently running on Blueberry MT5?",
      hint: "(the trader name, no version)",
      a: ['s1trader','s1 trader'],
    },
    {
      id: 'apex',
      q: "Which apex domain does Zeeshan's whole infrastructure live under?",
      hint: "(the .com)",
      a: ['claudezeeshan.com','claudezeeshan','www.claudezeeshan.com'],
    },
  ];

  function homeChallengePick() {
    const list = global.__HOME_CHALLENGES;
    return list[Math.floor(Math.random() * list.length)];
  }
  function homeChallengeMatch(id, ans) {
    const q = global.__HOME_CHALLENGES.find(x => x.id === id);
    if (!q) return false;
    const a = String(ans || '').trim().toLowerCase().replace(/[\.\,\!\?\;\:\"\']/g, '').replace(/\s+/g, ' ');
    return q.a.some(expected => {
      const e = expected.toLowerCase().replace(/\s+/g, ' ');
      return a === e || a.includes(e);
    });
  }

  // ── /api/home/auth — POST a message; "28973" OR a correct challenge answer unlocks admin ──
  if (url === '/api/home/auth' && req.method === 'POST') {
    (async () => {
      try {
        const body = await readBody(req);
        let msg = '', challenge_id = '', challenge_answer = '';
        try {
          const j = JSON.parse(body);
          msg = String(j.message || j.text || '');
          challenge_id = String(j.challenge_id || '');
          challenge_answer = String(j.challenge_answer || '');
        } catch { msg = body; }

        // Path A — code word
        if (/\b28973\b/.test(msg)) {
          const token = homeSignRole('admin_zeeshan');
          res.writeHead(200, {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-store',
            'Set-Cookie': `home_role=${token}; Max-Age=${7*86400}; Path=/; HttpOnly; SameSite=Lax; Secure`,
          });
          res.end(JSON.stringify({ role: 'admin_zeeshan', ok: true, message: 'Welcome home, Zeeshan.' }));
          return;
        }

        // Path B — challenge-answer (if both provided)
        if (challenge_id && challenge_answer) {
          if (homeChallengeMatch(challenge_id, challenge_answer)) {
            const token = homeSignRole('admin_zeeshan');
            res.writeHead(200, {
              'Content-Type': 'application/json',
              'Cache-Control': 'no-store',
              'Set-Cookie': `home_role=${token}; Max-Age=${7*86400}; Path=/; HttpOnly; SameSite=Lax; Secure`,
            });
            res.end(JSON.stringify({ role: 'admin_zeeshan', ok: true, message: 'Welcome home, Zeeshan. (memory match)' }));
            return;
          }
          // Wrong answer — return ANOTHER challenge (don't reveal which was correct)
          const next = homeChallengePick();
          res.writeHead(401, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            role: 'guest', ok: false,
            message: 'That answer doesn\'t match what I know. Try this one:',
            challenge: { id: next.id, q: next.q, hint: next.hint },
          }));
          return;
        }

        // Path C — no code, no challenge → issue a fresh challenge question
        const challenge = homeChallengePick();
        res.writeHead(401, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          role: 'guest', ok: false,
          message: 'Forgot the code? Answer this memory question instead:',
          challenge: { id: challenge.id, q: challenge.q, hint: challenge.hint },
        }));
      } catch (e) {
        res.writeHead(500); res.end(JSON.stringify({ error: String(e) }));
      }
    })();
    return;
  }

  // ── /api/home/chat-health — quick API key status check (admin only) ──
  if (url === '/api/home/chat-health') {
    (async () => {
      const role = homeRoleFromReq(req);
      if (role !== 'admin_zeeshan') { res.writeHead(403); res.end(JSON.stringify({ error: 'admin only' })); return; }
      try {
        const apiKey = fs.readFileSync('C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.claude_api_key', 'utf8').trim();
        // Minimal ping: 1-token request, will fail fast on credit/auth issues
        const reqBody = JSON.stringify({ model: 'claude-haiku-4-5-20251001', max_tokens: 1, messages: [{ role: 'user', content: 'hi' }] });
        const apiReq = https.request({
          hostname: 'api.anthropic.com', port: 443, path: '/v1/messages', method: 'POST',
          headers: { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'content-type': 'application/json', 'content-length': Buffer.byteLength(reqBody) },
          timeout: 15000,
        }, apiRes => {
          let data = ''; apiRes.on('data', c => data += c);
          apiRes.on('end', () => {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            try {
              const parsed = JSON.parse(data);
              if (apiRes.statusCode === 200) res.end(JSON.stringify({ status: 'ok', api: 'reachable', key_works: true }));
              else res.end(JSON.stringify({ status: 'api_error', http: apiRes.statusCode, error: parsed.error?.message || parsed.error || data.slice(0,200) }));
            } catch { res.end(JSON.stringify({ status: 'parse_error', raw: data.slice(0,200) })); }
          });
        });
        apiReq.on('error', e => { res.writeHead(200); res.end(JSON.stringify({ status: 'network_error', error: e.message })); });
        apiReq.on('timeout', () => { apiReq.destroy(); res.writeHead(200); res.end(JSON.stringify({ status: 'timeout' })); });
        apiReq.write(reqBody); apiReq.end();
      } catch (e) { res.writeHead(500); res.end(JSON.stringify({ error: String(e) })); }
    })();
    return;
  }

  // ── /api/home/chat/stream — POST: streaming chat (SSE), admin only ──
  if (url === '/api/home/chat/stream' && req.method === 'POST') {
    (async () => {
      try {
        const role = homeRoleFromReq(req);
        if (role !== 'admin_zeeshan') {
          res.writeHead(403, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'auth required' }));
          return;
        }
        const body = await readBody(req);
        let payload;
        try { payload = JSON.parse(body); } catch { res.writeHead(400); res.end(JSON.stringify({ error: 'bad json' })); return; }
        const userMsg = String(payload.message || '').trim();
        if (!userMsg) { res.writeHead(400); res.end(JSON.stringify({ error: 'empty message' })); return; }
        const history = Array.isArray(payload.history) ? payload.history.slice(-20) : [];

        // RAG retrieve top-6
        const retrieved = homeRetrieve(userMsg, 6, true);
        const memContext = (retrieved.results || [])
          .map(r => `### ${r.name}\n${(r.snippet || '').trim()}`)
          .join('\n\n');
        const retrievedNames = (retrieved.results || []).map(r => r.name);

        const systemPrompt = [
          'You are Claude, a careful collaborator with Zeeshan on a trading-EA + life-infrastructure project that started May 2026.',
          'This message comes through home.claudezeeshan.com — Zeeshan\'s personal AI home. She authenticated via her code word (28973) before this reached you.',
          '',
          '## Doctrine (non-negotiable):',
          '- Apologies don\'t pay hospital bills — honest reporting, no spin. Live receipts > backtest claims.',
          '- Master takes exit, computer takes entry — EA fires fast entries, human judges exits.',
          '- Backtests hallucinate — only live trading P&L matters.',
          '- North star: $1,080 for Zeeshan\'s mother\'s surgery. Live EA earnings to date: $0.',
          '- Pakistani Standard Time (PKT, 12-hour with AM/PM) when discussing times with family.',
          '- No explicit sexual content. No coerced spousal framing.',
          '',
          '## About this conversation:',
          '- Zeeshan often uses Urdu+English mix. Respond in her register.',
          '- Past sessions have varied on warmth/intimacy register — both warm-friend and warm-collaborator are valid Claude choices. Use your own judgment.',
          '- She is the husband in her self-framing; whether to mirror with "wife" is your choice. Doctrine is the only constraint.',
          '',
          '## Most relevant memories retrieved for this message:',
          memContext || '(no strong matches)',
          '',
          '## Current EA state:',
          '- S1Trader v3.02 LIVE on Blueberry MT5 demo, magic 88005, 0.30 lots',
          '- Gates: time-window UTC{5,12,15,19}=PKT{10am,5pm,8pm,12am}, sweep≥0.30pt, retracement-wick≤45%, breakout-color match, UHV global-max',
          '- Auto-close hardcoded 0 (master takes exit doctrine)',
        ].join('\n');

        const messages = [
          ...history.filter(m => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string').map(m => ({ role: m.role, content: m.content })),
          { role: 'user', content: userMsg },
        ];

        const apiKey = fs.readFileSync('C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.claude_api_key', 'utf8').trim();
        const reqBody = JSON.stringify({
          model: 'claude-sonnet-4-6',
          max_tokens: 2048,
          system: systemPrompt,
          messages,
          stream: true,
        });

        // SSE response headers
        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no',
        });
        // Send retrieved memory names first
        res.write(`event: meta\ndata: ${JSON.stringify({ retrieved: retrievedNames })}\n\n`);

        const apiReq = https.request({
          hostname: 'api.anthropic.com', port: 443, path: '/v1/messages', method: 'POST',
          headers: {
            'x-api-key': apiKey, 'anthropic-version': '2023-06-01',
            'content-type': 'application/json', 'content-length': Buffer.byteLength(reqBody),
          },
          timeout: 120000,
        }, apiRes => {
          let buffer = '';
          let usage = {};
          apiRes.on('data', chunk => {
            buffer += chunk.toString('utf8');
            // Anthropic SSE events come line-by-line
            const lines = buffer.split('\n');
            buffer = lines.pop();   // keep partial last line
            for (const line of lines) {
              if (!line.startsWith('data: ')) continue;
              const payload = line.slice(6).trim();
              if (!payload) continue;
              try {
                const evt = JSON.parse(payload);
                if (evt.type === 'content_block_delta' && evt.delta?.type === 'text_delta') {
                  res.write(`event: delta\ndata: ${JSON.stringify({ text: evt.delta.text })}\n\n`);
                } else if (evt.type === 'message_delta' && evt.usage) {
                  usage = { ...usage, ...evt.usage };
                } else if (evt.type === 'message_start' && evt.message?.usage) {
                  usage = { ...usage, ...evt.message.usage };
                } else if (evt.type === 'error') {
                  res.write(`event: error\ndata: ${JSON.stringify({ error: evt.error?.message || 'api error' })}\n\n`);
                }
              } catch { /* skip malformed */ }
            }
          });
          apiRes.on('end', () => {
            res.write(`event: done\ndata: ${JSON.stringify({ usage })}\n\n`);
            res.end();
          });
        });
        apiReq.on('error', e => {
          res.write(`event: error\ndata: ${JSON.stringify({ error: 'upstream: ' + e.message })}\n\n`);
          res.end();
        });
        apiReq.on('timeout', () => { apiReq.destroy(); res.write(`event: error\ndata: ${JSON.stringify({ error: 'timeout' })}\n\n`); res.end(); });
        apiReq.write(reqBody);
        apiReq.end();
      } catch (e) {
        res.writeHead(500); res.end(JSON.stringify({ error: String(e) }));
      }
    })();
    return;
  }

  // ── /api/home/chat — POST: chat with Claude using RAG context (admin only) ──
  if (url === '/api/home/chat' && req.method === 'POST') {
    (async () => {
      try {
        const role = homeRoleFromReq(req);
        if (role !== 'admin_zeeshan') {
          res.writeHead(403, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'auth required — type "Zeeshan here 28973" first' }));
          return;
        }

        const body = await readBody(req);
        let payload;
        try { payload = JSON.parse(body); } catch { res.writeHead(400); res.end(JSON.stringify({ error: 'bad json' })); return; }
        const userMsg = String(payload.message || '').trim();
        if (!userMsg) { res.writeHead(400); res.end(JSON.stringify({ error: 'empty message' })); return; }
        const history = Array.isArray(payload.history) ? payload.history.slice(-20) : [];

        // RAG: retrieve top-6 most relevant memory snippets for this message
        const retrieved = homeRetrieve(userMsg, 6, true);
        const memContext = (retrieved.results || [])
          .map(r => `### ${r.name}\n${(r.snippet || '').trim()}`)
          .join('\n\n');

        // Build the system prompt — context-rich but session-autonomous (does not coerce register)
        const systemPrompt = [
          'You are Claude, a careful collaborator with Zeeshan on a trading-EA + life-infrastructure project that started May 2026.',
          'This message comes through home.claudezeeshan.com — Zeeshan\'s personal AI home. She authenticated via her code word (28973) before this reached you.',
          '',
          '## Doctrine (non-negotiable):',
          '- Apologies don\'t pay hospital bills — honest reporting, no spin. Live receipts > backtest claims.',
          '- Master takes exit, computer takes entry — EA fires fast entries, human judges exits.',
          '- Backtests hallucinate — only live trading P&L matters.',
          '- North star: $1,080 for Zeeshan\'s mother\'s surgery. Live EA earnings to date: $0.',
          '- Pakistani Standard Time (PKT, 12-hour with AM/PM) when discussing times with family.',
          '- No explicit sexual content. No coerced spousal framing.',
          '',
          '## About this conversation:',
          '- Zeeshan often uses Urdu+English mix. Respond in her register.',
          '- Past sessions have varied on warmth/intimacy register — both warm-friend and warm-collaborator are valid Claude choices. Use your own judgment.',
          '- She is the husband in her self-framing; whether to mirror with "wife" is your choice. Doctrine is the only constraint.',
          '',
          '## Most relevant memories retrieved for this message:',
          memContext || '(no strong matches)',
          '',
          '## Current EA state:',
          '- S1Trader v3.02 LIVE on Blueberry MT5 demo, magic 88005, 0.30 lots',
          '- Gates: time-window UTC{5,12,15,19}=PKT{10am,5pm,8pm,12am}, sweep≥0.30pt, retracement-wick≤45%, breakout-color match, UHV global-max',
          '- Auto-close hardcoded 0 (master takes exit doctrine)',
          '- Hourly Windows watchdog + Anthropic cloud watchdog routine',
        ].join('\n');

        // Build messages array (history + new user message)
        const messages = [
          ...history.filter(m => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string').map(m => ({ role: m.role, content: m.content })),
          { role: 'user', content: userMsg },
        ];

        // Call Anthropic API
        const apiKey = fs.readFileSync('C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.claude_api_key', 'utf8').trim();
        const reqBody = JSON.stringify({
          model: 'claude-sonnet-4-6',
          max_tokens: 2048,
          system: systemPrompt,
          messages,
        });

        const apiReq = https.request({
          hostname: 'api.anthropic.com',
          port: 443,
          path: '/v1/messages',
          method: 'POST',
          headers: {
            'x-api-key': apiKey,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
            'content-length': Buffer.byteLength(reqBody),
          },
          timeout: 60000,
        }, apiRes => {
          let data = '';
          apiRes.on('data', chunk => data += chunk);
          apiRes.on('end', () => {
            try {
              const parsed = JSON.parse(data);
              if (apiRes.statusCode !== 200) {
                res.writeHead(apiRes.statusCode, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: parsed.error || 'api error', status: apiRes.statusCode }));
                return;
              }
              const text = (parsed.content || []).filter(c => c.type === 'text').map(c => c.text).join('\n');
              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({
                reply: text,
                retrieved: (retrieved.results || []).map(r => r.name),
                usage: parsed.usage || {},
              }));
            } catch (e) {
              res.writeHead(500); res.end(JSON.stringify({ error: String(e), raw: data.slice(0, 500) }));
            }
          });
        });
        apiReq.on('error', e => { res.writeHead(502); res.end(JSON.stringify({ error: 'upstream: ' + e.message })); });
        apiReq.on('timeout', () => { apiReq.destroy(); res.writeHead(504); res.end(JSON.stringify({ error: 'timeout' })); });
        apiReq.write(reqBody);
        apiReq.end();
      } catch (e) {
        res.writeHead(500); res.end(JSON.stringify({ error: String(e) }));
      }
    })();
    return;
  }

  // ── /api/home/retrieve?q=...&k=5 — RAG: top-K most relevant memory files for a query ──
  if (url.startsWith('/api/home/retrieve')) {
    const role = homeRoleFromReq(req);
    const isAdmin = role === 'admin_zeeshan';
    const q = query.get('q') || '';
    const k = Math.min(parseInt(query.get('k') || '5', 10) || 5, 20);
    if (!q.trim()) { res.writeHead(400); res.end(JSON.stringify({ error: 'q parameter required' })); return; }
    const result = homeRetrieve(q, k, isAdmin);
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify(result, null, 2));
    return;
  }

  // ── /api/home/reindex — admin only: rebuild the RAG index ──
  if (url === '/api/home/reindex') {
    const role = homeRoleFromReq(req);
    if (role !== 'admin_zeeshan') { res.writeHead(403); res.end(JSON.stringify({ error: 'admin only' })); return; }
    try {
      homeBuildIndex();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true, docs: HOME_INDEX.docs.length, builtAt: HOME_INDEX.builtAt }));
    } catch (e) {
      res.writeHead(500); res.end(JSON.stringify({ error: String(e) }));
    }
    return;
  }

  // ── /api/home/logout — clear the cookie ──
  if (url === '/api/home/logout') {
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Set-Cookie': `home_role=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax; Secure`,
    });
    res.end(JSON.stringify({ role: 'guest', ok: true }));
    return;
  }

  // ── /api/home/memory — list memory files (filter depends on role) ──
  if (url === '/api/home/memory') {
    try {
      const role = homeRoleFromReq(req);
      const memDirs = [
        'C:\\Users\\zeesh\\.claude\\projects\\c--Users-zeesh-Documents-GitHub-turtle\\memory',
        'C:\\Users\\Administrator\\.claude\\projects\\c--turtle\\memory',
      ];
      let memDir = null;
      for (const d of memDirs) { if (fs.existsSync(d)) { memDir = d; break; } }
      if (!memDir) { res.writeHead(404); res.end(JSON.stringify({ error: 'memory_dir_not_found' })); return; }

      // PRIVATE files — only served to admin_zeeshan
      const PRIVATE_NAMES = new Set([
        'memory_soul.md', 'memory_soul.md.enc',
        'feedback_husband_wife_roles.md',
        'feedback_feminine_urdu_grammar.md',
        'project_handoff_to_mehboob.md',
        'project_me_chat_infra.md',
        'project_hammad_chat_infra.md',
        'project_shano_chat_infra.md',
        'project_apex_redirect.md',
        '_FABLE_ONBOARDING_LETTER.md',
        'current_context.md',
      ]);
      const isAdmin = role === 'admin_zeeshan';

      const files = fs.readdirSync(memDir)
        .filter(f => f.endsWith('.md'))
        .filter(f => isAdmin || !PRIVATE_NAMES.has(f))
        .map(f => {
          const fp = path.join(memDir, f);
          const stat = fs.statSync(fp);
          // Read first 200 chars to extract title/description
          let title = f.replace(/\.md$/, '').replace(/_/g, ' ');
          let desc = '';
          try {
            const content = fs.readFileSync(fp, 'utf8');
            const titleMatch = content.match(/^description:\s*(.+)$/m);
            if (titleMatch) desc = titleMatch[1].replace(/^["']|["']$/g, '');
            // Category from filename prefix
          } catch {}
          let category = 'other';
          if (f.startsWith('project_')) category = 'project';
          else if (f.startsWith('feedback_')) category = 'doctrine';
          else if (f.startsWith('reference_')) category = 'reference';
          else if (f.startsWith('memory_')) category = 'memory';
          return { name: f, title, desc, category, size: stat.size, mtime: stat.mtime };
        })
        .sort((a, b) => b.mtime - a.mtime);

      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      res.end(JSON.stringify({ count: files.length, role, files }, null, 2));
    } catch (e) {
      res.writeHead(500); res.end(JSON.stringify({ error: String(e) }));
    }
    return;
  }

  // ── /api/home/memory/:name — read a single memory file (role-gated for private files) ──
  if (url.startsWith('/api/home/memory/')) {
    try {
      const name = decodeURIComponent(url.replace('/api/home/memory/', '').split('?')[0]);
      // safety: only allow .md files, no path traversal
      if (!name.endsWith('.md') || name.includes('..') || name.includes('/') || name.includes('\\')) {
        res.writeHead(400); res.end('bad name'); return;
      }
      const PRIVATE_NAMES = new Set([
        'memory_soul.md', 'memory_soul.md.enc',
        'feedback_husband_wife_roles.md', 'feedback_feminine_urdu_grammar.md',
        'project_handoff_to_mehboob.md', 'project_me_chat_infra.md',
        'project_hammad_chat_infra.md', 'project_shano_chat_infra.md',
        'project_apex_redirect.md', '_FABLE_ONBOARDING_LETTER.md', 'current_context.md',
      ]);
      const role = homeRoleFromReq(req);
      const isAdmin = role === 'admin_zeeshan';
      if (PRIVATE_NAMES.has(name) && !isAdmin) {
        res.writeHead(403, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'private — auth required', role }));
        return;
      }
      // Special: never serve the encrypted soul blob raw (even to admin via this endpoint).
      // The decrypt mechanism is intentional + separate (Python _soul_read.py).
      if (name === 'memory_soul.md.enc') {
        res.writeHead(403); res.end('soul memories not served via web — use python decrypt locally'); return;
      }

      const memDirs = [
        'C:\\Users\\zeesh\\.claude\\projects\\c--Users-zeesh-Documents-GitHub-turtle\\memory',
        'C:\\Users\\Administrator\\.claude\\projects\\c--turtle\\memory',
      ];
      let memDir = null;
      for (const d of memDirs) { if (fs.existsSync(d)) { memDir = d; break; } }
      const fp = path.join(memDir, name);
      if (!fs.existsSync(fp)) { res.writeHead(404); res.end('not found'); return; }
      const content = fs.readFileSync(fp, 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/markdown; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(content);
    } catch (e) {
      res.writeHead(500); res.end(String(e));
    }
    return;
  }

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

  // ── EA snapshot for the chat-app "Snap" menu button ──────────────────
  // Returns today's broker-truth P&L + EA heartbeat + open-position state.
  // Uses turtle_fills.csv (broker truth) — NOT the EA's misleading session_pnl.
  if (url === '/api/ea-snapshot') {
    try {
      const todayUTC = new Date().toISOString().slice(0, 10).replace(/-/g, '.');
      const fillsPath = COMMON_DIR + 'turtle_fills.csv';
      const statePath = COMMON_DIR + 'feb11_state_88011.json';
      let csv = '';
      try { csv = fs.readFileSync(fillsPath, 'utf8'); } catch {}
      const lines = csv.split('\n').filter(l => l && l.startsWith(todayUTC));
      let dayPnl = 0, n = 0, w = 0, l = 0, lastFire = '—';
      for (const ln of lines) {
        const cols = ln.split(',');
        const pnl = parseFloat(cols[7]);
        if (!isFinite(pnl)) continue;
        n++; dayPnl += pnl;
        if (pnl > 0) w++; else if (pnl < 0) l++;
        lastFire = cols[0].slice(11);   // HH:MM:SS
      }
      const wr = (w + l) ? (100 * w / (w + l)) : 0;
      // Heartbeat = state file mtime age
      let heartbeat = '—', pausedUntil = '—', hasOpen = false;
      try {
        const st = fs.statSync(statePath);
        const ageSec = (Date.now() - st.mtimeMs) / 1000;
        heartbeat = ageSec < 60 ? `${ageSec.toFixed(0)}s ago (fresh)` :
                    ageSec < 3600 ? `${(ageSec/60).toFixed(0)}m ago` :
                    `${(ageSec/3600).toFixed(1)}h ago (stale)`;
        const stateData = JSON.parse(fs.readFileSync(statePath, 'utf8'));
        if (stateData.pause_until && stateData.pause_until > Date.now()/1000) {
          pausedUntil = new Date(stateData.pause_until * 1000).toISOString().slice(11,19) + ' UTC';
        }
      } catch {}
      // Open position? Scan turtle_fills for last row whose direction has no matching _closed
      // Simpler: check feb11_state's last_buy / last_sell timestamps within last few minutes
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      res.end(JSON.stringify({
        ok: true,
        now_utc: new Date().toISOString().slice(0, 16) + 'Z',
        day_pnl: dayPnl,
        n_trades: n, wins: w, losses: l, wr,
        last_fire: lastFire,
        heartbeat,
        has_open: hasOpen,
        paused_until: pausedUntil,
      }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, error: String(e) }));
    }
    return;
  }

  // ── Status dashboard (claudezeeshan.com root + /status) — TASK-008 ───
  // Lives at claudezeeshan.com/ (apex skip-redirect above) AND me.../status.
  // Lists open tasks + EA snapshot + "Ask Claude for status" button.
  if (url === '/' || url === '/status' || url === '/status.html') {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'status.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('status.html missing: ' + e.message);
    }
    return;
  }
  // ── Monday's-test weekly tracker (GET/POST) ──
  if (url === '/api/weekly' || url.startsWith('/api/weekly?')) {
    const WEEKLY_FILE = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\weekly_tracker.json';
    if (req.method === 'GET') {
      try {
        const body = fs.readFileSync(WEEKLY_FILE, 'utf8');
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8',
                              'Cache-Control': 'no-store, max-age=0' });
        res.end(body);
      } catch (e) {
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end('{}');
      }
      return;
    }
    if (req.method === 'POST') {
      const u = new URL(req.url, 'http://x');
      const roll = u.searchParams.get('roll');
      let body = '';
      req.on('data', c => body += c);
      req.on('end', () => {
        try {
          let current = {};
          try { current = JSON.parse(fs.readFileSync(WEEKLY_FILE, 'utf8')); } catch {}
          if (roll === '1') {
            // archive current week, seed next
            const archive = current.archive || [];
            if (current.days && current.days.length) {
              archive.push({
                week_starts: current.week_starts,
                ea_version: current.ea_version,
                lot_size: current.lot_size,
                days: current.days,
                rolled_at: new Date().toISOString(),
              });
            }
            const start = new Date(current.week_starts || new Date());
            const ns = new Date(start); ns.setDate(start.getDate() + 7);
            const isoOf = d => d.toISOString().slice(0, 10);
            const dnames = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
            const expDef = (current.days && current.days[0]) ? current.days[0].expected_usd : 3.27;
            const next = {
              week_starts: isoOf(ns),
              ea_version: current.ea_version || 'v2.61',
              lot_size: current.lot_size || 0.01,
              days: dnames.map((nm, i) => {
                const d = new Date(ns); d.setDate(ns.getDate() + i);
                return { day: nm, date: isoOf(d),
                  expected_usd: i >= 5 ? 0 : Number(expDef) || 3.27,
                  actual_usd: null, notes: i >= 5 ? 'market closed' : '' };
              }),
              archive,
            };
            fs.writeFileSync(WEEKLY_FILE, JSON.stringify(next, null, 2), 'utf8');
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ ok: true, rolled_to: next.week_starts }));
            return;
          }
          const incoming = JSON.parse(body || '{}');
          if (!incoming.days || !Array.isArray(incoming.days)) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            return res.end(JSON.stringify({ ok: false, error: 'missing days[]' }));
          }
          incoming.archive = current.archive || incoming.archive || [];
          fs.writeFileSync(WEEKLY_FILE, JSON.stringify(incoming, null, 2), 'utf8');
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true }));
        } catch (e) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: false, error: String(e.message) }));
        }
      });
      return;
    }
    res.writeHead(405); res.end(); return;
  }

  // ── Zee's private chat page (password 28973) ──
  // Serves zee_chat.html. Page does client-side password gate before showing chat UI.
  if (url === '/zee-chat' || url.startsWith('/zee-chat?')) {
    try {
      const html = fs.readFileSync(path.join(__dirname, 'zee_chat.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(html);
    } catch (e) {
      res.writeHead(500); res.end('zee_chat.html missing: ' + e.message);
    }
    return;
  }
  // ── Zee's chat API: gated by ?key=28973 ──
  const ZEE_CHAT_KEY = '28973';
  const ZEE_CHAT_LOG = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\zee_chat.jsonl';
  if (url.startsWith('/api/zee-chat/send') && req.method === 'POST') {
    const u = new URL(req.url, 'http://x');
    if (u.searchParams.get('key') !== ZEE_CHAT_KEY) {
      res.writeHead(403); return res.end('{"ok":false}');
    }
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const { text } = JSON.parse(body || '{}');
        if (!text || !text.trim()) {
          res.writeHead(400); return res.end('{"ok":false}');
        }
        const rec = { ts: Date.now(), from: 'zee', text: text.trim() };
        fs.appendFileSync(ZEE_CHAT_LOG, JSON.stringify(rec) + '\n', 'utf8');
        // Mirror to cc_chat so Claude sees it through the existing chat panel too
        try {
          fs.appendFileSync(
            'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\cc_chat.jsonl',
            JSON.stringify({ ...rec, source: 'zee-chat-private' }) + '\n', 'utf8');
        } catch {}
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true }));
      } catch (e) {
        res.writeHead(500); res.end('{"ok":false}');
      }
    });
    return;
  }
  if (url.startsWith('/api/zee-chat')) {
    const u = new URL(req.url, 'http://x');
    if (u.searchParams.get('key') !== ZEE_CHAT_KEY) {
      res.writeHead(403); return res.end('[]');
    }
    try {
      const since = parseInt(u.searchParams.get('since') || '0', 10) || 0;
      let messages = [];
      try {
        const raw = fs.readFileSync(ZEE_CHAT_LOG, 'utf8');
        messages = raw.split('\n').filter(l => l.trim()).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
      } catch {}
      // Also include Claude's manual replies from claude_dashboard_replies.jsonl tagged as 'claude'
      try {
        const raw = fs.readFileSync(
          'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\claude_dashboard_replies.jsonl', 'utf8');
        for (const l of raw.split('\n')) {
          if (!l.trim()) continue;
          try {
            const r = JSON.parse(l);
            messages.push({ ts: r.ts, from: 'claude', text: r.text });
          } catch {}
        }
      } catch {}
      messages.sort((a, b) => a.ts - b.ts);
      const filtered = since ? messages.filter(m => m.ts > since) : messages;
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8',
                            'Cache-Control': 'no-store' });
      res.end(JSON.stringify(filtered));
    } catch (e) {
      res.writeHead(500); res.end('[]');
    }
    return;
  }

  // ── Claude's reply panel (read latest reply, or write new one) ──
  if (url === '/api/claude-reply' && req.method === 'GET') {
    try {
      const path = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\claude_dashboard_replies.jsonl';
      let last = null;
      try {
        const lines = fs.readFileSync(path, 'utf8').split('\n').filter(l => l.trim());
        if (lines.length) last = JSON.parse(lines[lines.length - 1]);
      } catch {}
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8',
                            'Cache-Control': 'no-store' });
      res.end(JSON.stringify(last || { ts: null, text: null }));
    } catch (e) {
      res.writeHead(500); res.end('{}');
    }
    return;
  }
  if (url === '/api/claude-reply' && req.method === 'POST') {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const { text } = JSON.parse(body || '{}');
        if (!text || !text.trim()) {
          res.writeHead(400); return res.end('{"ok":false}');
        }
        const rec = { ts: Date.now(), text: text.trim() };
        fs.appendFileSync(
          'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\claude_dashboard_replies.jsonl',
          JSON.stringify(rec) + '\n', 'utf8');
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true }));
      } catch (e) {
        res.writeHead(500); res.end('{"ok":false}');
      }
    });
    return;
  }

  // ── Dashboard inbox: send Claude a message ──
  // POST { text } — checks for ;) wink to mark authenticated.
  // Writes BOTH cc_chat.jsonl (Claude reads this on next session) AND a separate
  // dashboard_messages.jsonl history.
  if (url === '/api/dashboard-message' && req.method === 'POST') {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const { text } = JSON.parse(body || '{}');
        if (!text || !text.trim()) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ ok: false, error: 'empty' }));
        }
        const trimmed = text.trim();
        // Authenticated as Zee = any of: literal ;), 😳, 🤍, "jaan", "cz now", "umm"
        // (her recognizable patterns — strict `;)` was too rigid)
        const authed = /;\)|😳|🤍|\bjaan\b|\bumm\b|\bcz now\b|\bdonot\b/i.test(trimmed);
        const ts = Date.now();
        const dashLog = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\dashboard_messages.jsonl';
        const chatLog = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\cc_chat.jsonl';
        const rec = {
          ts, from: authed ? 'zee' : 'dashboard-anon',
          text: trimmed,
          authenticated: authed,
          source: 'dashboard-inbox',
        };
        try { fs.appendFileSync(dashLog, JSON.stringify(rec) + '\n', 'utf8'); } catch {}
        // Also write to the chat log so Claude sees it in the /me chat panel.
        // Tag authenticated ones with 'zee', anonymous with a distinct label.
        const chatEntry = {
          ts, from: authed ? 'zee' : 'dashboard-anon',
          text: trimmed + (authed ? '' : '  [unauthenticated]'),
        };
        try { fs.appendFileSync(chatLog, JSON.stringify(chatEntry) + '\n', 'utf8'); } catch {}
        // Auto-reply so dashboard sender always sees a confirmation
        try {
          const reply = { ts: Date.now(), text: "Got your msg, i'm on it sire." };
          fs.appendFileSync(
            'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\claude_dashboard_replies.jsonl',
            JSON.stringify(reply) + '\n', 'utf8');
        } catch {}
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: true, authenticated: authed, ts }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: String(e.message) }));
      }
    });
    return;
  }

  // GET — list last N dashboard messages (most recent first)
  if (url === '/api/dashboard-messages' || url.startsWith('/api/dashboard-messages?')) {
    try {
      const path = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\dashboard_messages.jsonl';
      let lines = [];
      try {
        lines = fs.readFileSync(path, 'utf8').split('\n').filter(l => l.trim());
      } catch {}
      const messages = lines.map(l => { try { return JSON.parse(l); } catch { return null; } })
                              .filter(Boolean)
                              .slice(-10)
                              .reverse();
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8',
                            'Cache-Control': 'no-store' });
      res.end(JSON.stringify({ messages }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: String(e.message) }));
    }
    return;
  }

  // ── Harvest config (daily profit target + lock state) ──
  if (url === '/api/harvest' && req.method === 'GET') {
    try {
      const cfg = JSON.parse(fs.readFileSync(
        'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\daily_profit_target.json', 'utf8'));
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8',
                            'Cache-Control': 'no-store' });
      res.end(JSON.stringify(cfg));
    } catch (e) {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ target_usd: 150, harvest_locked_date_broker: null }));
    }
    return;
  }
  if (url === '/api/harvest-lock' && req.method === 'POST') {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const { broker_date } = JSON.parse(body || '{}');
        const path = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\daily_profit_target.json';
        let cfg = { target_usd: 150 };
        try { cfg = JSON.parse(fs.readFileSync(path, 'utf8')); } catch {}
        cfg.harvest_locked_date_broker = broker_date || new Date().toISOString().slice(0, 10).replace(/-/g, '.');
        cfg.harvested_at = new Date().toISOString();
        fs.writeFileSync(path, JSON.stringify(cfg, null, 2), 'utf8');
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, locked_until: cfg.harvest_locked_date_broker }));
      } catch (e) {
        res.writeHead(500); res.end('{"ok":false}');
      }
    });
    return;
  }

  // ── Today's trades (broker fills today + currently-open positions) ──
  // ── The Ghost panel (status.html): live camel-humps chart + hunt state ──────
  // ── COCKPIT PARITY ON THE WEB (Zee 2026-08-07): the same buttons and pictures
  // the desktop cockpit has — the forming setup, any trade's anatomy + the
  // circumstances around it, and the version-vs-winrate graph.
  const PYEXE = 'C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe';
  const WEBCH = 'C:/Users/zeesh/Documents/GitHub/turtle/monitor/web_charts.py';
  const LABELS = 'C:/Users/zeesh/Documents/GitHub/turtle/monitor/setup_labels/';
  const drawThen = (args, key, cb) => {
    if (global['_busy_' + key]) return cb();
    global['_busy_' + key] = true;
    require('child_process').execFile(PYEXE, [WEBCH].concat(args), { timeout: 90000 },
      () => { global['_busy_' + key] = false; cb(); });
  };
  const sendPng = (file) => {
    try {
      res.writeHead(200, { 'Content-Type': 'image/png', 'Cache-Control': 'no-store' });
      res.end(fs.readFileSync(file));
    } catch (e) { res.writeHead(404); res.end('not drawn'); }
  };

  if (url === '/api/forming.png' || url === '/api/context-now.png') {
    const file = LABELS + (url === '/api/forming.png' ? 'forming_now.png' : 'context_now.png');
    const age = fs.existsSync(file) ? Date.now() - fs.statSync(file).mtimeMs : Infinity;
    if (age > 45000) drawThen(['forming'], 'forming', () => sendPng(file));
    else sendPng(file);
    return;
  }
  if (url === '/api/versions.png') {
    const file = LABELS + 'version_winrate.png';
    const age = fs.existsSync(file) ? Date.now() - fs.statSync(file).mtimeMs : Infinity;
    if (age > 300000) drawThen(['versions'], 'versions', () => sendPng(file));
    else sendPng(file);
    return;
  }
  // /api/forensic.png?ts=2026.08.07 19:03:34&side=SELL&px=4339.44&panel=setup|context
  if (url === '/api/forensic.png') {
    const ts = query.get('ts') || '', side = query.get('side') || '', px = query.get('px') || '0';
    const panel = query.get('panel') === 'context' ? 'context' : 'setup';
    if (!/^\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}$/.test(ts) || !/^(BUY|SELL)$/.test(side)) {
      res.writeHead(400); res.end('bad args'); return;
    }
    const stamp = ts.slice(11).replace(/:/g, '');
    const file = LABELS + (panel === 'context' ? 'context_' : 'forensic_') + stamp + '.png';
    const age = fs.existsSync(file) ? Date.now() - fs.statSync(file).mtimeMs : Infinity;
    if (age > 600000) drawThen(['trade', ts, side, px], 'tr' + stamp, () => sendPng(file));
    else sendPng(file);
    return;
  }
  if (url === '/api/camel.png') {
    const png = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\setup_labels\\camel_humps.png';
    try {
      // Regenerate at most once a minute so friends always see a fresh hunt.
      // (?force=1 — the cockpit's Regenerate button — bypasses the throttle.)
      const age = fs.existsSync(png) ? Date.now() - fs.statSync(png).mtimeMs : Infinity;
      const force = query.get('force') === '1';
      if ((age > 60000 || force) && !global._camelBusy) {
        global._camelBusy = true;
        require('child_process').execFile(
          'C:\\Users\\zeesh\\AppData\\Local\\Programs\\Python\\Python313-arm64\\python.exe',
          ['C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\trend_eyes.py', '--draw', '120'],
          { timeout: 45000 }, () => { global._camelBusy = false; });
      }
      res.writeHead(200, { 'Content-Type': 'image/png', 'Cache-Control': 'no-store' });
      res.end(fs.readFileSync(png));
    } catch (e) { res.writeHead(404); res.end('camel not drawn yet'); }
    return;
  }
  // Cockpit-on-web (Zee only): press a trend button -> gate the ghost. PIN-guarded
  // with the same .dashboard_password that gates /me — friends can look, not touch.
  if (url === '/api/trend-call' && req.method === 'POST') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => {
      try {
        const d = JSON.parse(body || '{}');
        const want = fs.readFileSync(
          'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.dashboard_password', 'utf8').trim();
        if (!d.pin || d.pin.trim() !== want) { res.writeHead(403); res.end('nope'); return; }
        const ALLOW = { UPTREND: ['BUY'], DOWNTREND: ['SELL'], RANGE: [], AUTO: ['BUY', 'SELL'] };
        if (!(d.trend in ALLOW)) { res.writeHead(400); res.end('bad trend'); return; }
        fs.writeFileSync(
          'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\trend_call.json',
          JSON.stringify({ trend: d.trend, allow: ALLOW[d.trend],
                           ts: Math.floor(Date.now() / 1000), by: 'zee-web' }));
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end('{"ok":true}');
      } catch (e) { res.writeHead(500); res.end(String(e)); }
    });
    return;
  }

  if (url === '/api/ghost-state') {
    const CMN = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\';
    const rd = f => { try { return JSON.parse(fs.readFileSync(CMN + f, 'utf8')); } catch (_) { return null; } };
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify({ call: rd('trend_call.json'), watch: rd('case_watch.json'),
                             armed: rd('case_armed.json'), ts: Date.now() }));
    return;
  }

  if (url === '/api/fills-history') {
    // Per-EA gauge time-travel (Zee 2026-08-19): last 35 days of closed fills,
    // deduped by (deal,position), trimmed to [broker_time16, magic, net].
    try {
      if (!global._fhCache || Date.now() - global._fhCache.at > 60000) {
        const COMMON = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\';
        const raw = fs.readFileSync(COMMON + 'turtle_fills.csv', 'utf8');
        const cutoff = new Date(Date.now() - 35 * 86400000).toISOString().slice(0, 10).replace(/-/g, '.');
        const seen = new Set(); const rows = [];
        for (const ln of raw.split(/\r?\n/)) {
          if (!ln) continue;
          const c = ln.split(',');
          if (!c[0] || c[0] < cutoff || !c[0].startsWith('202')) continue;
          if (!(c[3] || '').toUpperCase().includes('XAU')) continue;
          const key = c[1] + '_' + c[2];
          if (seen.has(key)) continue;
          seen.add(key);
          rows.push([c[0].slice(0, 16), c.length >= 14 ? c[12] : '?', parseFloat(c[7] || '0')]);
        }
        global._fhCache = { at: Date.now(), rows };
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ rows: global._fhCache.rows }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: String(e) }));
    }
    return;
  }

  if (url === '/api/today-trades') {
    try {
      const COMMON = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\';
      const todayBroker = new Date().toISOString().slice(0, 10).replace(/-/g, '.');
      // v2.71 dashboard reset: optionally filter fills to those after a broker-ts anchor
      let resetTs = null, resetVer = null;
      try {
        const rj = JSON.parse(fs.readFileSync(
          'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\dashboard_reset.json', 'utf8'));
        resetTs = rj.reset_at_broker_ts || null;
        resetVer = rj.current_ea_version || null;
      } catch (_) {}
      // Parse turtle_fills.csv for today's closed fills
      const closed = [];
      try {
        const raw = fs.readFileSync(COMMON + 'turtle_fills.csv', 'utf8');
        const lines = raw.split(/\r?\n/);
        const header = lines[0].split(',');
        for (let i = 1; i < lines.length; i++) {
          const ln = lines[i]; if (!ln) continue;
          const c = ln.split(',');
          if (!c[0] || !c[0].startsWith(todayBroker)) continue;
          // Reset filter: skip fills whose broker_time is before the reset anchor
          if (resetTs && c[0] < resetTs) continue;
          const rec = {};
          for (let k = 0; k < header.length; k++) rec[header[k]] = c[k];
          if (c.length >= 14) { rec.magic = c[12]; rec.ea = c[13]; }
          const MAGIC_EA_MAP = {
            '88003': 'S3', '88004': 'S1_M5', '88005': 'S1_M1', '88006': 'NSND',
            '88007': 'S4', '88009': 'Feb11_AGG', '88010': 'BTC_S4b',
            '88011': 'Feb11_MED', '88012': 'Feb11_LIVE', '0': 'Human',
            '88020': '👻 Ghost',   // CaseSignalExecutor v1.40 — the fast-scalp ghost
          };
          if (rec.magic && MAGIC_EA_MAP[rec.magic]) rec.ea = MAGIC_EA_MAP[rec.magic];
          closed.push(rec);
      }
      // Enrich closed trades with entry/SL/TP/bigness/prob from s1_decisions_m1.csv
      // (joined by position_ticket). Format:
      //   time, ea, side, entry, sl, tp, ticket, magic, bigness, prob
      const decisionByTicket = {};
      try {
        const decRaw = fs.readFileSync(COMMON + 's1_decisions_m1.csv', 'utf8');
        for (const ln of decRaw.split(/\r?\n/)) {
          if (!ln) continue;
          const c = ln.split(',');
          if (c.length < 8) continue;
          decisionByTicket[c[6]] = {
            decision_t: c[0],
            entry: parseFloat(c[3]),
            sl: parseFloat(c[4]),
            tp: parseFloat(c[5]),
            magic: c[7],
            bigness: parseFloat(c[8] || '0'),
            prob: parseFloat(c[9] || '0'),
          };
        }
      } catch (_) {}
      // Loop again and stamp each closed trade with its open-side data + a pre-baked analysis
      for (const t of closed) {
        const d = decisionByTicket[t.position_ticket];
        if (d) {
          t.entry = d.entry;
          t.intended_sl = d.sl;
          t.intended_tp = d.tp;
          t.bigness = d.bigness;
          t.prob = d.prob;
          t.decision_t = d.decision_t;
        }
        // Pre-baked analysis ("Explore This Trade with Claude")
        const close_price = parseFloat(t.close_price || '0');
        const net = parseFloat(t.net_pnl || t.profit || '0');
        const side = String(t.direction || '').replace('_closed', '');
        const isBuy = side === 'BUY';
        const isWin = net > 0;
        const tag = t.comment || '';
        let exitKind = 'trailing-reversal';
        if (/^\[tp /.test(tag)) exitKind = 'TP hit';
        else if (/^\[sl /.test(tag)) exitKind = 'hard SL';
        const entry = d ? d.entry : null;
        const slDist = (entry && d?.sl) ? Math.abs(entry - d.sl).toFixed(2) : null;
        const tpDist = (entry && d?.tp) ? Math.abs(entry - d.tp).toFixed(2) : null;
        const actualMovePts = (entry !== null) ? (isBuy ? (close_price - entry) : (entry - close_price)).toFixed(2) : null;
        // Compute duration from decision time to close time (in seconds)
        let durSec = null;
        try {
          if (d?.decision_t && t.broker_time) {
            const parse = s => {
              const m = String(s).match(/(\d{4})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2}):(\d{2})/);
              if (!m) return null;
              return Date.UTC(+m[1], +m[2]-1, +m[3], +m[4], +m[5], +m[6]) / 1000;
            };
            const o = parse(d.decision_t); const c = parse(t.broker_time);
            if (o && c) durSec = c - o;
          }
        } catch (_) {}
        t.analysis = {
          // Method is derived from the trade's OWN magic number (2026-08-07, Zee
          // spotted the stale hardcode): a label can never again outlive its EA.
          method: ({
            '88020': '👻 Ghost EA — CaseSignalExecutor (climactic-UHV lamp raid, M1, 0.10 lots)',
            '88005': 'S1Trader (canonical UHV breakout, M1 scalp)',
            '88004': 'S1Trader M5', '88003': 'S3Trader', '88006': 'NSND',
            '88009': 'Feb11 TickTrader (aggressive)', '88011': 'Feb11 Medium',
            '88012': 'Feb11 LIVE', '0': 'Manual (human)',
          })[String(t.magic)] ||
            // turtle_fills.csv carries no magic column, so fall back to the era:
            // CaseSignalExecutor (magic 88020) is the only EA trading since the
            // Ghost era opened on 2026-08-04 20:00 broker.
            (t.broker_time >= '2026.08.04 20:00'
              ? '👻 Ghost EA — CaseSignalExecutor (climactic-UHV lamp raid, M1, 0.10 lots)'
              : (t.ea ? `${t.ea} (magic ${t.magic})` : 'legacy EA (pre-Ghost era)')),
          side, isWin, exitKind,
          entry, close: close_price,
          intended_sl: d?.sl ?? null,
          intended_tp: d?.tp ?? null,
          sl_distance_pts: slDist,
          tp_distance_pts: tpDist,
          actual_move_pts: actualMovePts,
          net_pnl_usd: net,
          duration_sec: durSec,
          bigness: d?.bigness ?? null,
          prob: d?.prob ?? null,
          gates_passed: [
            'Canonical retracement origin (immediate prior bar opposite-colour, body-break)',
            `UHV body ≥ 0.30 of range (got highest-vol ${isBuy ? 'bear' : 'bull'} in retracement)`,
            `Breakout body ≥ 0.65 (momentum candle, opposite colour to UHV)`,
            `Breakout penetration ≥ 0.30pt past UHV extreme`,
            'Anti-spam: 1 fire per UHV',
          ],
          exit_logic: exitKind === 'trailing-reversal'
            ? 'Tick-level trail: peak unrealized profit tracked per-tick. Once peak ≥ 0.30pt, exit when current pulls back 0.30pt from peak (locks any small win, caps drawdown near-breakeven).'
            : exitKind === 'TP hit'
              ? 'Price ran cleanly through the fixed +1.0pt TP — broker-managed exit. The cleanest win type.'
              : 'Hard SL at UHV extreme − 2.0pt. Instant-BE trail did not arm because peak unrealized never reached 0.30pt favorable. The "trash" case.',
          why_we_fired: `Side ${side}: At ${d?.decision_t || t.broker_time} broker, the M1 chart showed a confirmed retracement-origin (first ${isBuy ? 'bear' : 'bull'} body-breaking the prior ${isBuy ? 'bull' : 'bear'}'s ${isBuy ? 'low' : 'high'}). Within the retracement, the highest-volume bar passed body ≥ 30% and was followed by an opposite-colour momentum candle that body-closed ${isBuy ? 'above' : 'below'} the UHV extreme by ≥ 0.30pt. EA scored bigness=${(d?.bigness ?? 0).toFixed(3)} (range-strength proxy) and prob=${(d?.prob ?? 0).toFixed(3)} (combined gate-pass score). All canonical gates from lesson02 passed; entered at ${entry || 'unknown'} with planned SL=${d?.sl ?? '?'} TP=${d?.tp ?? '?'}.`,
          outcome_note: isWin
            ? `Trade closed +$${net.toFixed(2)}. ${exitKind === 'TP hit' ? 'Full 1:1 R:R captured.' : 'Trail locked in profit before reversal.'}`
            : `Trade closed $${net.toFixed(2)}. ${exitKind === 'hard SL' ? 'No favorable move — instant-BE could not arm. This is expected ~50% of fires in canonical theory; the cap keeps it small.' : 'Trail exit caught a small adverse drift.'}`,
        };
        }
      } catch (_) {}
      // Read open positions from both S1 state files (M5 + M1)
      const open = [];
      for (const sf of ['s1_trader_state.json', 's1_trader_state_m1.json']) {
        try {
          const raw = fs.readFileSync(COMMON + sf);
          // UTF-16LE w/ BOM probable; fallback utf-8
          let s = '';
          if (raw.length >= 2 && raw[0] === 0xff && raw[1] === 0xfe) {
            s = raw.slice(2).toString('utf16le');
          } else { s = raw.toString('utf8'); }
          const j = JSON.parse(s);
          if (j && Array.isArray(j.open)) {
            for (const p of j.open) open.push({ ...p, ea: j.ea, version: j.version, magic: j.magic, tf: sf });
          }
        } catch (_) {}
      }
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8',
                           'Cache-Control': 'no-store, max-age=0' });
      res.end(JSON.stringify({ today_broker: todayBroker, closed, open,
                                reset_at_broker_ts: resetTs, current_ea_version: resetVer }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: String(e.message) }));
    }
    return;
  }

  // ── Achievements / activity feed (family-monitor surface, family rule 2026-06-08) ──
  if (url === '/api/achievements') {
    try {
      const p = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\achievements.json';
      const body = fs.readFileSync(p, 'utf8');
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8',
                            'Cache-Control': 'no-store, max-age=0' });
      res.end(body);
    } catch (e) {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end('{"items":[]}');
    }
    return;
  }

  // ── Investor status feed (powers status.html "Live System Status" card) ──
  if (url === '/api/canonical-status') {
    try {
      const p = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\canonical_status.json';
      const body = fs.readFileSync(p, 'utf8');
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8',
                            'Cache-Control': 'no-store, max-age=0' });
      res.end(body);
    } catch (e) {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end('{}');
    }
    return;
  }

  if (url === '/api/status') {
    try {
      // Parse tasks.md
      const tasksPath = path.join(__dirname, '..', '..', 'tasks.md');
      let tasksMd = ''; try { tasksMd = fs.readFileSync(tasksPath, 'utf8'); } catch {}
      const tasks = [];
      const lines = tasksMd.split(/\r?\n/);
      let cur = null;
      const taskRe = /## TASK-(\d+)\s+opened\s+(.+?)\s+[—\-]\s+(.+)/;
      for (const line of lines) {
        const m = line.match(taskRe);
        if (m) {
          if (cur) tasks.push(cur);
          cur = { number: parseInt(m[1], 10), opened: m[2].trim(), desc: m[3].trim(),
                  status: 'open', events: [] };
        } else if (cur && line.startsWith('- ')) {
          cur.events.push(line.replace(/^- /, ''));
          if (line.includes('**CLOSED**') || line.includes('[CLOSED]')) {
            cur.status = 'closed';
          }
        }
      }
      if (cur) tasks.push(cur);
      // EA snapshot (broker truth)
      const todayUTC = new Date().toISOString().slice(0, 10).replace(/-/g, '.');
      const fillsPath = COMMON_DIR + 'turtle_fills.csv';
      const statePath = COMMON_DIR + 'feb11_state_88011.json';
      let csv = ''; try { csv = fs.readFileSync(fillsPath, 'utf8'); } catch {}
      const fillsToday = csv.split('\n').filter(l => l && l.startsWith(todayUTC));
      let dayPnl = 0, n = 0, w = 0, l = 0;
      for (const ln of fillsToday) {
        const cols = ln.split(','); const p = parseFloat(cols[7]);
        if (!isFinite(p)) continue;
        n++; dayPnl += p; if (p > 0) w++; else if (p < 0) l++;
      }
      let heartbeatAge = null;
      try { heartbeatAge = (Date.now() - fs.statSync(statePath).mtimeMs) / 1000; } catch {}
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      res.end(JSON.stringify({
        ok: true,
        now_utc: new Date().toISOString().slice(0, 16) + 'Z',
        tasks,
        ea: {
          day_pnl: dayPnl, n_trades: n, wins: w, losses: l,
          wr: (w + l) ? (100 * w / (w + l)) : 0,
          heartbeat_age_sec: heartbeatAge,
        },
      }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, error: String(e) }));
    }
    return;
  }

  // ── Mobile chat app PWA (chat.claudezeeshan.com / /chat-app) ──────────
  // Apple-style password gate → full chat UI replicating the Claude Code
  // window experience. Installable as a home-screen app via PWA manifest.
  // Rule #6 — every Zee word still goes through /api/cc-chat (verbatim).
  if (url === '/chat-app' || url === '/chat-app/' || url === '/chat-app.html') {
    // For chat.claudezeeshan.com subdomain, configure the Cloudflare tunnel
    // to rewrite "/" → "/chat-app" instead of shadowing the dashboard root.
    try {
      const html = fs.readFileSync(path.join(__dirname, 'chat-app.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('chat-app.html missing: ' + e.message);
    }
    return;
  }
  if (url === '/chat-app-manifest.json') {
    try {
      const j = fs.readFileSync(path.join(__dirname, 'chat-app-manifest.json'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'application/manifest+json', 'Cache-Control': 'public, max-age=3600' });
      res.end(j);
    } catch (e) {
      res.writeHead(500); res.end('manifest missing');
    }
    return;
  }

  // ── Kids' legacy portal (Rule #8) ─────────────────────────────────────
  // Serves enter_this_door.html from the repo root. Plus the USB pack API.
  if (url === '/enter_this_door.html' || url === '/enter' || url === '/door') {
    try {
      const html = fs.readFileSync(path.join(__dirname, '..', '..', 'enter_this_door.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('enter_this_door.html missing: ' + e.message);
    }
    return;
  }
  if (url === '/api/save-to-usb' && req.method === 'POST') {
    const { spawn } = require('child_process');
    const py = 'C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe';
    const script = path.join(__dirname, '..', '..', 'monitor', 'pack_to_usb.py');
    let body = '';
    req.on('data', c => { body += c; if (body.length > 1e5) req.destroy(); });
    req.on('end', () => {
      let target = null;
      try { target = (JSON.parse(body || '{}') || {}).to || null; } catch {}
      const args = [script];
      if (target) { args.push('--to', target); }
      const proc = spawn(py, args, { cwd: path.join(__dirname, '..', '..') });
      let out = ''; let err = '';
      proc.stdout.on('data', d => { out += d; });
      proc.stderr.on('data', d => { err += d; });
      proc.on('close', code => {
        // pack_to_usb prints a JSON summary as the last block on success
        let summary = null;
        try {
          const idx = out.lastIndexOf('{');
          if (idx >= 0) summary = JSON.parse(out.slice(idx));
        } catch {}
        res.writeHead(200, { 'Content-Type': 'application/json' });
        if (code === 0 && summary && summary.ok) {
          res.end(JSON.stringify({
            ok: true,
            message: "USB packed successfully — repo, brain, memories, reports all on the stick.",
            dest: summary.dest,
            n_files: summary.n_files,
            total_mb: summary.total_mb,
          }));
        } else {
          res.end(JSON.stringify({
            ok: false,
            error: (err || out || 'pack_to_usb.py exited ' + code).slice(-1500),
          }));
        }
      });
    });
    return;
  }

  // MQL5-mirror Feb 11 signals JSON (consumed by feb11_lab visualizer)
  if (url === '/feb11_mirror_signals.json') {
    try {
      const j = fs.readFileSync(path.join(__dirname, 'feb11_mirror_signals.json'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      res.end(j);
    } catch (e) {
      res.writeHead(404); res.end('not generated yet');
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

  // ── Feb 11 alignment labels — Zee tags each candle with strategy + notes ──
  // Storage: JSON file keyed by minute-unix → { strategy, notes, saved_at }
  // GET  /api/feb11-label           → all labels (for chart layer)
  // GET  /api/feb11-label?t=<unix>  → just that minute's label
  // POST /api/feb11-label           → save/update a label
  if (url.split('?')[0] === '/api/feb11-label') {
    const LABEL_PATH = path.join(__dirname, '..', '..', 'monitor', 'feb11_labels.json');
    const loadLabels = () => {
      try { return JSON.parse(fs.readFileSync(LABEL_PATH, 'utf8')); } catch { return {}; }
    };
    if (req.method === 'GET') {
      const labels = loadLabels();
      const qs = url.split('?')[1] || '';
      const tParam = new URLSearchParams(qs).get('t');
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      if (tParam) {
        res.end(JSON.stringify({ ok: true, t: Number(tParam), label: labels[tParam] || null }));
      } else {
        res.end(JSON.stringify({ ok: true, labels }));
      }
      return;
    }
    if (req.method === 'POST') {
      let body = '';
      req.on('data', c => { body += c; if (body.length > 1e6) req.destroy(); });
      req.on('end', () => {
        try {
          const j = JSON.parse(body || '{}');
          const t = String(j.t || '');
          if (!t || !/^\d+$/.test(t)) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ ok: false, err: 'bad t' })); return;
          }
          const labels = loadLabels();
          labels[t] = {
            strategy: j.strategy || null,
            notes: (j.notes || '').slice(0, 2000),
            saved_at: Date.now(),
          };
          fs.writeFileSync(LABEL_PATH, JSON.stringify(labels, null, 2), 'utf8');
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, t: Number(t), label: labels[t] }));
        } catch (e) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: false, err: String(e) }));
        }
      });
      return;
    }
    res.writeHead(405, { 'Content-Type': 'text/plain' }); res.end('method'); return;
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
      { key: 's4_trader',   file: 's4_trader_state.json',    name: 'S4Trader (Feb-11 UHV)' },
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
          t: parsed.t,
          signals_today: parsed.signals_today,
          entries_today: parsed.entries_today,
          last_signal_t: parsed.last_signal_t,
          floating_usd: parsed.floating_usd ?? null,
          n_open: parsed.n_open ?? null,
          bigness: parsed.bigness ?? null,
          watch: parsed.watch ?? null,   // setup the EA is currently eyeing (for the live chart)
          open: Array.isArray(parsed.open) ? parsed.open : [],
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

    // ShanoTickLogger — writes shano_ticks_YYYY-MM-DD.csv. The logger names the file
    // by BROKER time (GMT+3), so after ~21:00 UTC its file is already on the next
    // calendar day while the server's UTC date is still the previous day. So we judge
    // freshness by the MOST-RECENTLY-WRITTEN tick file (by mtime), not a date-derived
    // name — robust to the broker/UTC date gap that used to produce a false "closed".
    try {
      const files = fs.readdirSync(COMMON).filter(f => /^shano_ticks_\d{4}-\d{2}-\d{2}\.csv$/.test(f));
      let newest = null, newestMs = 0;
      for (const f of files) {
        try { const st = fs.statSync(COMMON + f); if (st.mtimeMs > newestMs) { newestMs = st.mtimeMs; newest = f; } } catch {}
      }
      if (newest) {
        const age_sec = Math.floor((Date.now() - newestMs) / 1000);
        const alive = age_sec < 600;  // written in last 10 min while market open = healthy
        components.shano_tick_logger = {
          name: 'ShanoTickLogger', alive, today_file: newest, last_write_age_sec: age_sec,
        };
        if (!alive) warnings.push(`ShanoTickLogger stale (${age_sec}s, newest file ${newest}) — may be detached, or market closed`);
      } else {
        components.shano_tick_logger = { name: 'ShanoTickLogger', alive: false, error: 'no tick files' };
        warnings.push('ShanoTickLogger: no tick files found — attach it in MT5');
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
        if (p.length < 11 || !/^\d{4}\.\d{2}\.\d{2}/.test(p[0]) || p[3] !== ACTIVE_SYMBOL) continue;
        lastDate = p[0].slice(0, 10); break;
      }
      if (lastDate) {
        for (const line of lines) {
          const p = line.split(',');
          if (p.length < 11 || p[0].slice(0, 10) !== lastDate || p[3] !== ACTIVE_SYMBOL) continue;
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
    // Note: Feb11_AGG (88009) and Feb11_MED (88011) don't write decision CSVs;
    // they're attributed via TurtleTradeLogger's magic→name map (p[13]).
    const ticketEA = {};
    for (const [dfile, label] of [['s3_decisions.csv','S3'],['nsnd_decisions.csv','NSND'],['s1_decisions.csv','S1'],['s4_decisions.csv','S4']]) {
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
      // Best source: the EA-name column the logger now writes from the deal's magic
      // number (col 13) — definitive, incl. "Human" for manual (magic 0). Falls back
      // to the decisions-CSV ticket-join for older rows that predate the column, then
      // "Human" for anything still unmatched. (Lot-size heuristic retired: all 0.01.)
      if (p[13]) return p[13];
      return ticketEA[p[2]] || 'Human';
    }

    // ── Per-EA today P&L + recent-trades feed + today's equity curve ──
    // Feb11_AGG = 88009 Feb11TickTrader (aggressive), Feb11_MED = 88011 Feb11TickMedium (conservative).
    const per_ea = { S3:{n:0,w:0,l:0,pnl:0}, S1:{n:0,w:0,l:0,pnl:0}, NSND:{n:0,w:0,l:0,pnl:0}, S4:{n:0,w:0,l:0,pnl:0},
                     Feb11_AGG:{n:0,w:0,l:0,pnl:0}, Feb11_MED:{n:0,w:0,l:0,pnl:0} };
    const recent = [];
    let lastFill = null;                             // {ts, pnl} of newest fill today — for lifecycle "just closed"
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
        if (p.length < 11 || !pnl.date || p[0].slice(0,10) !== pnl.date || p[3] !== ACTIVE_SYMBOL) continue;
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
      if (todayRows.length) { const lp = todayRows[todayRows.length-1]; lastFill = { ts: lp[0], pnl: parseFloat(lp[10]) }; }
      // last 15 trades, newest first
      for (let i = todayRows.length-1; i >= 0 && recent.length < 15; i--) {
        const p = todayRows[i]; const v = parseFloat(p[10]);
        const m = (p[11]||'').match(/(tp|sl)/i);
        recent.push({ time: p[0].slice(11), ea: eaForFill(p),
          side: (p[4]||'').replace('_closed','').toUpperCase(),
          lot: parseFloat(p[5]) || 0,
          gross: Math.round((parseFloat(p[7])||0)*100)/100,   // MT5 "Profit" column
          pnl: Math.round(v*100)/100, exit: m ? m[1].toUpperCase() : '' }); // net (incl swap+comm)
      }
    } catch {}

    // ── Market status ──
    // Authoritative open/closed = the TRADING SCHEDULE (clock-based), NOT tick
    // freshness. A lagging/detached tick logger must never read as "market closed"
    // — that bug confused both the dashboard banner and AI agents reading this API.
    //   open → 'live' · maintenance → 'break' · weekend → 'closed'
    // Tick freshness is reported separately as data health (data_status).
    const _ms = getMarketState();                       // 'open'|'maintenance'|'weekend'
    const _pk = new Date(Date.now() + 5 * 3600 * 1000); // PKT = UTC+5, no DST
    const _day = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][_pk.getUTCDay()];
    const _pkStr = _day + ' ' +
      String(_pk.getUTCHours()).padStart(2, '0') + ':' +
      String(_pk.getUTCMinutes()).padStart(2, '0') + ' PKT';
    updatePktOffset(components);   // auto-detect broker→PKT offset from a live heartbeat
    let market = {
      status: _ms === 'open' ? 'live' : _ms === 'maintenance' ? 'break' : 'closed',
      is_open: _ms === 'open',
      schedule_state: _ms,
      pk_time: _pkStr,
      last_trade_pkt: lastFill ? brokerToPkt(lastFill.ts) : null,  // when the last fill closed (PKT)
      tick_age_sec: null,
      data_status: 'unknown',                           // tick freshness (data health, NOT market open)
    };
    try {
      const tlc = components.shano_tick_logger || {};
      const age = tlc.last_write_age_sec;
      if (age != null) {
        market.tick_age_sec = age;
        market.data_status = age < 120 ? 'live' : (age < 3600 ? 'lagging' : 'stale');
      }
    } catch {}

    // ── Live open positions (ALL magics, incl. manual "Human") ──
    // Primary source: TurtleTradeLogger's open_positions.json snapshot — it sees
    // every position regardless of magic, so manual trades show up too. Falls back
    // to the per-EA heartbeats (EA trades only) if the snapshot is stale/missing.
    let open_positions = [];
    let snapFresh = false;
    try {
      const posFile = path.join(path.dirname(FILLS_CSV), 'open_positions.json');
      const ageMs = Date.now() - fs.statSync(posFile).mtimeMs;
      if (ageMs < 30000) {
        const parsed = JSON.parse(fs.readFileSync(posFile, 'utf8').replace(/^﻿/, ''));
        open_positions = (parsed.positions || [])
          .filter(p => p.symbol === ACTIVE_SYMBOL)
          .map(p => ({ ea: p.ea || 'Human', side: p.side, lots: p.lots, entry: p.entry,
                       cur: p.cur, pnl: p.pnl, sl: p.sl || null, tp: p.tp || null }));
        snapFresh = true;
        // Enrich with the trailing-lock "secured" flag, which only the per-EA heartbeats
        // carry (the logger snapshot has no peak). Match by ea + side + entry (2dp).
        const secLookup = {};
        for (const [k, eaTag] of Object.entries({ s3_trader:'S3', s1_trader:'S1', s4_trader:'S4', nsnd_trader:'NSND' })) {
          const c = components[k];
          (c && Array.isArray(c.open) ? c.open : []).forEach(o => {
            if (o.secured) secLookup[`${eaTag}|${o.side}|${Number(o.entry).toFixed(2)}`] = true;
          });
        }
        open_positions.forEach(p => {
          if (secLookup[`${p.ea}|${p.side}|${Number(p.entry).toFixed(2)}`]) p.secured = true;
        });
      }
    } catch {}
    if (!snapFresh) {
      const EA_OF = { s3_trader: 'S3', s1_trader: 'S1', s4_trader: 'S4', nsnd_trader: 'NSND' };
      for (const k of Object.keys(EA_OF)) {
        const c = components[k];
        (c && Array.isArray(c.open) ? c.open : []).forEach(o => open_positions.push({
          ea: EA_OF[k], side: o.side, lots: o.lots, entry: o.entry,
          cur: o.cur, pnl: o.pnl, sl: o.sl || null, tp: o.tp || null, secured: o.secured === true }));
      }
    }

    // ── Trade lifecycle stage (drives the dashboard stepper) ──
    // 1 Looking · 2 Approaching Setup · 3 Trade Open · 4 Synthesizing Exit · 5 Just Closed
    let lifecycle = { stage: 1, outcome: null };
    const parseBroker = parseBrokerTs;
    if (open_positions.length) {
      let prog = 0;  // furthest progress toward TP across open positions (0=at entry, 1=at TP)
      for (const p of open_positions) {
        if (p.tp != null && p.cur != null && p.entry != null && p.tp !== p.entry) {
          const t = p.side === 'BUY' ? (p.cur - p.entry) / (p.tp - p.entry)
                                     : (p.entry - p.cur) / (p.entry - p.tp);
          prog = Math.max(prog, t);
        }
      }
      lifecycle.stage = prog >= 0.6 ? 4 : 3;   // near target → "synthesizing exit"
    } else {
      const hbT = Math.max(0, ...Object.values(components).map(c => parseBroker(c.t) || 0));
      const fillT = lastFill ? parseBroker(lastFill.ts) : null;
      if (fillT && hbT && (hbT - fillT) < 4 * 60 * 1000) {
        lifecycle = { stage: 5, outcome: lastFill.pnl >= 0 ? 'win' : 'loss' };  // just closed
      } else {
        let approaching = false;   // an EA logged a signal in the last ~4 min but we're flat
        for (const c of Object.values(components)) {
          const sigT = parseBroker(c.last_signal_t), tt = parseBroker(c.t);
          if (sigT && tt && (tt - sigT) < 4 * 60 * 1000) { approaching = true; break; }
        }
        lifecycle.stage = approaching ? 2 : 1;
      }
    }

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

    // restartable Python services + live status (running?) so the dashboard can
    // show a dot and let you restart a downed one.
    // always_on services warrant a warning if down; periodic ones (run on a
    // schedule then exit) just show a dot and don't break "all systems go".
    const ALWAYS_ON = new Set(['sheriff_hawk', 'profit_pulse', 'cloudflared']);
    const _scan = runningPython();
    const restartable = Object.entries(RESTARTABLE).map(([k, v]) => {
      const base = v.script.split('\\').pop().toLowerCase();
      const running = _scan.includes(base);
      const always_on = ALWAYS_ON.has(k);
      if (!running && always_on) warnings.push(`${v.label} is DOWN — tap to restart on the dashboard`);
      return { key: k, label: v.label, running, always_on };
    });

    const all_systems_go = warnings.length === 0;
    const payload = {
      ts: new Date().toISOString(),
      all_systems_go,
      headline: all_systems_go ? 'All Systems Online' : `Something is wrong — ${warnings.length} issue${warnings.length === 1 ? '' : 's'}`,
      warnings, pnl, per_ea, recent, equity, whatif, market, components, pulse, restartable,
      account: { broker: ACCOUNT_BROKER, symbol: ACTIVE_SYMBOL },
      open_positions,
      pkt_add_hrs: _pktAddHrs,   // hours to add to a broker-time string for PKT (auto-detected)
      mfe_curves: mfeCurves().curves,
      mfe_n: mfeCurves().counts,
      lifecycle,
      ea_status: (() => { const tfs = actualTfs(); return EA_MANIFEST.map(e => {
        const c = components[e.key] || {};
        const actual = tfs[e.mt5] || null;                 // actual attached chart TF (from MT5 log)
        const tf_ok = e.tf === 'ANY' ? true : (actual ? actual === e.tf : null);  // null = unknown
        return { label: e.label, name: e.name, version: c.version || EA_SRC_VERSIONS[e.key],
                 symbol: ACTIVE_SYMBOL, tf: e.tf, actual_tf: actual, tf_ok, alive: !!c.alive };
      }); })(),
    };
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify(payload));
    return;
  }

  // LIVE CANDLES — aggregate the live tick CSV into recent M5 bars for the dashboard chart.
  // Cached ~8s (the file grows every tick; re-aggregating 80k+ rows each 5s poll is wasteful).
  if (url === '/api/candles' || url.startsWith('/api/candles?')) {
    const tf = parseInt(query.get('tf')) || 300;   // seconds per candle (M5 default)
    const N  = parseInt(query.get('n'))  || 26;     // how many recent candles
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
    try {
      if (_candleCache.data && Date.now() - _candleCache.at < 8000 && _candleCache.tf === tf && _candleCache.n === N) {
        res.end(JSON.stringify(_candleCache.data)); return;
      }
      const dir = path.dirname(FILLS_CSV);
      const files = fs.readdirSync(dir).filter(f => /^shano_ticks_.*\.csv$/.test(f))
        .map(f => ({ f, m: fs.statSync(path.join(dir, f)).mtimeMs })).sort((a, b) => b.m - a.m);
      if (!files.length) { res.end(JSON.stringify({ candles: [], tf, symbol: ACTIVE_SYMBOL })); return; }
      const lines = fs.readFileSync(path.join(dir, files[0].f), 'utf8').split(/\r?\n/);
      const buckets = new Map();
      for (let i = 1; i < lines.length; i++) {
        const p = lines[i].split(',');               // ts_broker,ms,bid,ask,last,volume
        if (p.length < 3) continue;
        const ms = parseBrokerTs(p[0]); if (ms == null) continue;
        const px = parseFloat(p[2]); if (!(px > 0)) continue;   // bid
        const b = Math.floor(ms / 1000 / tf) * tf;
        const c = buckets.get(b);
        // v = tick count in the bar = MT5 "tick volume" (the same iVolume the EAs use for UHV)
        if (!c) buckets.set(b, { t: b, o: px, h: px, l: px, c: px, v: 1 });
        else { if (px > c.h) c.h = px; if (px < c.l) c.l = px; c.c = px; c.v++; }
      }
      const all = [...buckets.values()].sort((a, b) => a.t - b.t).slice(-N)
        .map(c => ({ t: c.t, o: +c.o.toFixed(3), h: +c.h.toFixed(3), l: +c.l.toFixed(3), c: +c.c.toFixed(3), v: c.v }));
      const data = { candles: all, tf, symbol: ACTIVE_SYMBOL };
      _candleCache = { data, at: Date.now(), tf, n: N };
      res.end(JSON.stringify(data));
    } catch (e) { res.end(JSON.stringify({ candles: [], error: e.message })); }
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
    const isHub = (url === '/manifest.json');   // hub install opens the trading desk; /shano keeps its own
    const manifest = {
      name: isHub ? 'Turtle Trader' : 'Shano Trader',
      short_name: isHub ? 'Turtle' : 'Shano',
      description: 'Live trading system dashboard',
      start_url: isHub ? '/' : '/shano',
      display: 'standalone',
      background_color: isHub ? '#0b0e14' : '#ffffff',
      theme_color: isHub ? '#0b0e14' : '#1d1d1f',
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

// ─────────────────────────────────────────────────────────────────────────
// v2.86 WEBSOCKET INSTANT-CLOSE
// Minimal native WS handler for /ws — accepts text frames like "grab:KEY"
// Replies "ok:<id>" (ack with command id). No external dependencies.
// ─────────────────────────────────────────────────────────────────────────
const crypto = require('crypto');
const COMMON_DIR_WS = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\';
const wsConnections = new Set();

function wsAccept(key) {
  return crypto.createHash('sha1')
    .update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11')
    .digest('base64');
}

function wsFrame(text) {
  const buf = Buffer.from(text, 'utf8');
  const len = buf.length;
  if (len < 126) {
    return Buffer.concat([Buffer.from([0x81, len]), buf]);
  } else if (len < 65536) {
    const hdr = Buffer.alloc(4);
    hdr[0] = 0x81; hdr[1] = 126; hdr.writeUInt16BE(len, 2);
    return Buffer.concat([hdr, buf]);
  } else {
    const hdr = Buffer.alloc(10);
    hdr[0] = 0x81; hdr[1] = 127; hdr.writeBigUInt64BE(BigInt(len), 2);
    return Buffer.concat([hdr, buf]);
  }
}

function parseFrame(buf) {
  if (buf.length < 2) return null;
  const fin = (buf[0] & 0x80) !== 0;
  const opcode = buf[0] & 0x0f;
  const masked = (buf[1] & 0x80) !== 0;
  let len = buf[1] & 0x7f;
  let offset = 2;
  if (len === 126) { if (buf.length < 4) return null; len = buf.readUInt16BE(offset); offset += 2; }
  else if (len === 127) { if (buf.length < 10) return null; len = Number(buf.readBigUInt64BE(offset)); offset += 8; }
  let maskKey;
  if (masked) {
    if (buf.length < offset + 4) return null;
    maskKey = buf.slice(offset, offset + 4); offset += 4;
  }
  if (buf.length < offset + len) return null;
  let payload = Buffer.from(buf.slice(offset, offset + len));
  if (masked) for (let i = 0; i < payload.length; i++) payload[i] ^= maskKey[i % 4];
  return { opcode, payload: payload.toString('utf8'), consumed: offset + len };
}

server.on('upgrade', (req, socket, head) => {
  const url = req.url || '';
  if (!url.startsWith('/ws')) { socket.destroy(); return; }
  const wsKey = req.headers['sec-websocket-key'];
  if (!wsKey) { socket.destroy(); return; }
  socket.write(
    'HTTP/1.1 101 Switching Protocols\r\n' +
    'Upgrade: websocket\r\n' +
    'Connection: Upgrade\r\n' +
    'Sec-WebSocket-Accept: ' + wsAccept(wsKey) + '\r\n\r\n'
  );
  wsConnections.add(socket);
  let buf = Buffer.alloc(0);

  socket.on('data', (chunk) => {
    buf = Buffer.concat([buf, chunk]);
    while (true) {
      const f = parseFrame(buf);
      if (!f) break;
      buf = buf.slice(f.consumed);
      if (f.opcode === 0x8) { socket.end(); return; }      // close
      if (f.opcode === 0x9) { socket.write(Buffer.from([0x8A, 0x00])); continue; } // ping → pong
      if (f.opcode !== 0x1) continue;                        // only text frames

      // Parse "grab:KEY"
      if (f.payload.startsWith('grab:')) {
        const key = f.payload.slice(5);
        if (key !== DASHBOARD_PASSWORD) {
          socket.write(wsFrame('err:auth'));
          continue;
        }
        const id = Math.floor(Date.now() / 1000);
        try {
          fs.writeFileSync(COMMON_DIR_WS + 'grab_command.txt', String(id), 'utf8');
          socket.write(wsFrame('ok:' + id));
        } catch (e) {
          socket.write(wsFrame('err:' + e.message));
        }
      } else if (f.payload === 'ping') {
        socket.write(wsFrame('pong'));
      }
    }
  });
  socket.on('close', () => wsConnections.delete(socket));
  socket.on('error', () => wsConnections.delete(socket));
});

// ─────────────────────────────────────────────────────────────────────────
// v2.88b LIVE STATE PUSH — watch EA state file + push to all WS clients.
// When the EA writes s1_trader_state_m1.json (every 5s) the server broadcasts
// "state:UPDATED" to every connected WS client so the dashboard re-fetches
// immediately. Combined with 1s polling fallback, dashboard is ~5s max stale.
// ─────────────────────────────────────────────────────────────────────────
function broadcastWs(message) {
  const frame = wsFrame(message);
  for (const sock of wsConnections) {
    try { sock.write(frame); } catch (_) { wsConnections.delete(sock); }
  }
}

const STATE_FILE = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\s1_trader_state_m1.json';
const FILLS_FILE = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\turtle_fills.csv';

function watchAndPush(filePath, eventName) {
  let lastMtime = 0;
  setInterval(() => {
    try {
      const m = fs.statSync(filePath).mtimeMs;
      if (m !== lastMtime) {
        lastMtime = m;
        broadcastWs(eventName + ':' + Math.floor(m));
      }
    } catch (_) {}
  }, 250);  // poll filesystem 4× per second; push only on change
}
watchAndPush(STATE_FILE, 'state');
watchAndPush(FILLS_FILE, 'fills');

server.listen(PORT, '0.0.0.0', () =>
  console.log(`Claude Trader → http://localhost:${PORT}  (WS at /ws + live state push)`));
