'use strict';
// Turtle Dashboard Server — pure Node.js, no npm install needed
// Runs on http://localhost:3456
const http = require('http');
const fs   = require('fs');
const path = require('path');

const PORT          = 3456;
const FILLS_CSV     = 'C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\turtle_fills.csv';
const NEWSFEED_IDX  = 'C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\newsfeed\\INDEX.json';
const HTML_FILE     = path.join(__dirname, 'index.html');

// ── helpers ────────────────────────────────────────────────────────────────────

function todayPrefix() {
  const n = new Date();
  return `${n.getFullYear()}.${String(n.getMonth()+1).padStart(2,'0')}.${String(n.getDate()).padStart(2,'0')}`;
}

// CSV datetimes are Moscow time (UTC+3). Convert to UTC Date for comparison.
function moscowToUtc(str) {
  const m = str.trim().match(/^(\d{4})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2}):(\d{2})$/);
  if (!m) return null;
  return new Date(Date.UTC(+m[1], +m[2]-1, +m[3], +m[4]-3, +m[5], +m[6]));
}

function parseFills() {
  try {
    const raw   = fs.readFileSync(FILLS_CSV, 'utf8');
    const lines = raw.trim().split('\n').filter(l => l.trim());

    const all = lines.map(line => {
      const p = line.split(',');
      return {
        datetime : p[0].trim(),
        ticket   : p[1] ? p[1].trim() : '',
        symbol   : p[3] ? p[3].trim() : 'XAUUSD',
        type     : p[4] ? p[4].trim() : '',
        lots     : p[5] ? parseFloat(p[5]) : 0,
        price    : p[6] ? parseFloat(p[6]) : 0,
        profit   : parseFloat(p[7]) || 0,
        tag      : p[p.length - 1] ? p[p.length - 1].trim() : '',
      };
    }).filter(f => f.datetime && f.type);

    const today = todayPrefix();
    const todayFills = all.filter(f => f.datetime.startsWith(today));

    // cumulative equity curve for today (sorted chronologically)
    let cum = 0;
    const equity = todayFills.map(f => {
      cum += f.profit;
      return { t: f.datetime.substring(11,16), v: parseFloat(cum.toFixed(2)) };
    });

    const wins   = todayFills.filter(f => f.profit > 0);
    const losses = todayFills.filter(f => f.profit < 0);
    const be     = todayFills.filter(f => f.profit === 0);
    const totalPL = todayFills.reduce((s, f) => s + f.profit, 0);
    const avgWin  = wins.length   ? wins.reduce((s,f)=>s+f.profit,0)/wins.length : 0;
    const avgLoss = losses.length ? losses.reduce((s,f)=>s+f.profit,0)/losses.length : 0;
    const winRate = todayFills.length ? (wins.length / todayFills.length * 100).toFixed(1) : '0.0';

    // consecutive streak from end
    let streak = 0;
    for (let i = todayFills.length - 1; i >= 0; i--) {
      if (todayFills[i].profit > 0) streak++;
      else break;
    }

    // last-hour window
    const oneHourAgo = new Date(Date.now() - 3600000);
    const lhFills  = todayFills.filter(f => {
      const dt = moscowToUtc(f.datetime);
      return dt && dt >= oneHourAgo;
    });
    const lhWins   = lhFills.filter(f => f.profit > 0);
    const lhLosses = lhFills.filter(f => f.profit < 0);
    const lhBe     = lhFills.filter(f => f.profit === 0);
    const lhPL     = lhFills.reduce((s, f) => s + f.profit, 0);
    const lhWR     = lhFills.length ? (lhWins.length / lhFills.length * 100).toFixed(1) : null;

    return {
      ok: true,
      today: {
        pl      : parseFloat(totalPL.toFixed(2)),
        wins    : wins.length,
        losses  : losses.length,
        be      : be.length,
        trades  : todayFills.length,
        winRate,
        avgWin  : parseFloat(avgWin.toFixed(2)),
        avgLoss : parseFloat(avgLoss.toFixed(2)),
        streak,
      },
      equity,
      last20: all.slice(-20).reverse(),
      lastHour: {
        pl     : parseFloat(lhPL.toFixed(2)),
        wins   : lhWins.length,
        losses : lhLosses.length,
        be     : lhBe.length,
        trades : lhFills.length,
        wr     : lhWR,  // null if no trades
      },
    };
  } catch(e) {
    return { ok: false, error: e.message, today: {}, equity: [], last20: [] };
  }
}

function parseNewsfeed() {
  try {
    let raw = fs.readFileSync(NEWSFEED_IDX, 'utf8');
    if (raw.charCodeAt(0) === 0xFEFF) raw = raw.slice(1); // strip BOM
    const index = JSON.parse(raw);
    return Object.entries(index)
      .map(([key, val]) => ({ cronId: key, ...val }))
      .filter(e => e.finished_at && e.summary)
      .sort((a, b) => new Date(b.finished_at) - new Date(a.finished_at))
      .slice(0, 20)
      .map(e => ({
        cronId     : e.cronId,
        summary    : e.summary,
        status     : e.status,
        flags      : e.flags || [],
        finished_at: e.finished_at,
      }));
  } catch(e) {
    return [];
  }
}

// ── HTTP server ────────────────────────────────────────────────────────────────

const server = http.createServer((req, res) => {
  const url = req.url.split('?')[0];

  if (url === '/api/data') {
    const payload = JSON.stringify({
      fills    : parseFills(),
      newsfeed : parseNewsfeed(),
      ts       : new Date().toISOString(),
    });
    res.writeHead(200, {
      'Content-Type'                : 'application/json',
      'Access-Control-Allow-Origin' : '*',
      'Cache-Control'               : 'no-store',
    });
    res.end(payload);
    return;
  }

  if (url === '/' || url === '/index.html') {
    try {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(fs.readFileSync(HTML_FILE, 'utf8'));
    } catch(e) {
      res.writeHead(500);
      res.end('Dashboard HTML missing: ' + e.message);
    }
    return;
  }

  res.writeHead(404);
  res.end('Not found');
});

server.on('error', e => {
  if (e.code === 'EADDRINUSE') {
    console.log(`Port ${PORT} already in use — dashboard already running at http://localhost:${PORT}`);
    process.exit(0);
  } else {
    console.error(e);
  }
});

server.listen(PORT, '127.0.0.1', () =>
  console.log(`Turtle Dashboard → http://localhost:${PORT}  (Ctrl+C to stop)`)
);
