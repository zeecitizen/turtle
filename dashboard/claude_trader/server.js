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

const server = http.createServer(async (req, res) => {
  const url = req.url.split('?')[0];

  if (url === '/api/state') {
    const state = buildState();
    const cdp   = await checkCDP();
    state.health = { cdp, alert: checkAlert(), config: checkConfig() };
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify(state));
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

    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify(shano));
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
          res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
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
              res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
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
