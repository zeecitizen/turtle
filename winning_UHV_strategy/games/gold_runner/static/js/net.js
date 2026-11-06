// net.js - the wire between the engine and the picture (F-CORE).
//
// Server mode: EventSource on /api/stream ("snap" = the full snapshot every 100 ms, "ev" = discrete events), the clock offset taken from
// snap.t, linkAge() = seconds since the server last spoke, act() = POST /api/act with a nonce and sent_at in SERVER time. Nothing is sent
// while frozen (link silent > link_freeze_s or snap.freeze). The client never computes money: it only forwards intents.
//
// Fixture mode (?fixture=NAME): no server at all. static/fixtures/NAME.json is loaded, time is animated (age, tilt and x wobble), the
// fixture's events loop every few seconds, and actions are echoed locally as the engine would answer them, so the picture reacts
// (anvil to the next stake, wall, haggle, machete, merchant, eject, shoot -> a little random-walk round, ack -> lobby...). The fixture
// arithmetic below exists only to make offline play-feel possible; it never runs against a server.

const LINK_FREEZE_S = 2.0;

export function createNet(opts = {}) {
  return opts.fixture ? new FixtureNet(opts.fixture, opts.base || import.meta.url) : new ServerNet(opts);
}

const clone = (o) => (typeof structuredClone === 'function' ? structuredClone(o) : JSON.parse(JSON.stringify(o)));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const r2 = (v) => Math.round(v * 100) / 100;
const r5 = (v) => Math.round(v * 1e5) / 1e5;
const clampN = (v, a, b) => Math.max(a, Math.min(b, v));

class BaseNet {
  constructor() {
    this.snap = null;
    this.events = [];
    this.lastMsg = 0;
    this.offset = 0;
    this._offs = [];
    this.connected = false;
    this.status = 'connecting';
    this.linkFreezeS = LINK_FREEZE_S;
    this.sentCount = 0;
    this.log = [];            // last actions and answers (debug)
  }
  takeEvents() { const e = this.events; this.events = []; return e; }
  linkAge() { return this.lastMsg ? (performance.now() - this.lastMsg) / 1000 : Infinity; }
  serverNow() { return Date.now() / 1000 + this.offset; }
  frozen() { return !!this.snap && (this.linkAge() > this.linkFreezeS || !!this.snap.freeze); }
  _clock(t) {
    if (typeof t !== 'number' || !isFinite(t)) return;
    // est = true offset - latency; the largest recent estimate is the least-delayed one
    this._offs.push(t - Date.now() / 1000);
    if (this._offs.length > 60) this._offs.shift();
    this.offset = Math.max(...this._offs);
  }
  nonce() { return Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 9); }
  _note(entry) { this.log.push(entry); if (this.log.length > 30) this.log.shift(); }
}

// ------------------------------------------------------------------------------------------------------------------ server mode
class ServerNet extends BaseNet {
  constructor() {
    super();
    this.mode = 'server';
    this.es = null;
    this.backoff = 500;
    this._retryT = null;
    this.connect();
  }
  connect() {
    let es;
    try { es = new EventSource('/api/stream'); } catch (e) { this._retry(); return; }
    this.es = es;
    es.addEventListener('snap', (m) => {
      try {
        const s = JSON.parse(m.data);
        this.snap = s;                       // keep only the latest snapshot; the renderer reads it once per frame
        this._clock(s.t);
        this.lastMsg = performance.now();
        this.connected = true; this.status = 'live'; this.backoff = 500;
      } catch (e) { /* a torn frame: wait for the next one */ }
    });
    es.addEventListener('ev', (m) => {
      try { this.events.push(JSON.parse(m.data)); this.lastMsg = performance.now(); } catch (e) { /* ignore */ }
    });
    es.onopen = () => { this.status = 'open'; };
    es.onerror = () => {
      this.connected = false; this.status = 'reconnecting';
      if (es.readyState === 2) this._retry();          // CLOSED after an HTTP error: the browser will not retry by itself
    };
  }
  _retry() {
    if (this._retryT) return;
    this._retryT = setTimeout(() => {
      this._retryT = null;
      try { if (this.es) this.es.close(); } catch (e) { /* ignore */ }
      this.connect();
    }, this.backoff);
    this.backoff = Math.min(5000, this.backoff * 2);
  }
  async act(action, args = {}) {
    const nonce = this.nonce();
    if (this.frozen() && action !== 'kill') { const r = { accepted: false, why: 'frozen', nonce, local: true }; this._note({ action, ...r }); return r; }
    const body = { action, nonce, sent_at: this.serverNow(), args };
    this.sentCount++;
    try {
      const res = await fetch('/api/act', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), cache: 'no-store' });
      const j = await res.json();
      const r = { accepted: !!j.accepted, why: j.why ?? null, nonce };
      this._note({ action, ...r });
      return r;
    } catch (e) {
      const r = { accepted: false, why: 'network', nonce };
      this._note({ action, ...r });
      return r;
    }
  }
  async settings(obj) {
    try {
      const res = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj), cache: 'no-store' });
      return await res.json();
    } catch (e) { return { ok: false, why: 'network', settings: null }; }
  }
  async getJSON(path) {
    try { const r = await fetch(path, { cache: 'no-store' }); return r.ok ? await r.json() : null; } catch (e) { return null; }
  }
}

// ------------------------------------------------------------------------------------------------------------------ fixture mode
export function trim4(x) {                            // 4 decimals, trailing zeros dropped, never fewer than 2 (engine _trim4)
  const [w, f] = Math.abs(x).toFixed(4).replace(/0+$/, '').split('.');
  return w + '.' + (f || '').padEnd(2, '0');
}
export function money(usd, risk) {                    // same format as the engine: dollars, up to 4 decimals when risk < $1
  if (!isFinite(usd)) return '';
  if (risk < 1) {
    const v = Math.round(usd * 1e4) / 1e4;
    const s = '$' + trim4(v);
    return v < 0 ? '-' + s : s;
  }
  const s = '$' + Math.abs(usd).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return usd < -0.004 ? '-' + s : s;
}

function ladder(side, fill, sl, tp, banked = 0, qty = 1, qty0 = 1) {
  const sd0 = Math.abs(fill - sl), td0 = Math.abs(tp - fill), f = qty / qty0, span = sd0 + td0;
  return { a: (banked / qty0 - f * side * fill + sd0) / span, b: (f * side) / span, sd0, td0 };
}

class FixtureNet extends BaseNet {
  constructor(name, base) {
    super();
    this.mode = 'fixture';
    this.name = name;
    this.loaded = false;
    this.status = 'loading fixture ' + name;
    this.motion = 'wobble';
    this.speed = 1;
    const url = new URL('../fixtures/' + encodeURIComponent(name) + '.json', base);
    fetch(url, { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then((j) => this._start(j))
      .catch((e) => { this.status = 'fixture "' + name + '" not found'; console.error('[net] fixture', name, String(e)); });
  }

  _start(j) {
    this.fixture = j;
    this.cur = clone(j.snap);
    this.loopEvents = (j.events || []).map(clone);
    this.t0 = performance.now();
    this.wall0 = this.cur.t;
    this.tick0 = this.cur.feed ? this.cur.feed.tick_count : 0;
    this.lastT = 0;
    // remember the price-anchored stakes and the terrain of the fixture so locally rebuilt previews/rounds keep the same street
    const src = this.cur.round || this.cur.preview;
    this.srcLadder = src ? { a: src.a, b: src.b } : null;
    this.srcTerrain = src ? clone(src.terrain) : null;
    this.stakePrices = src ? (src.stakes || []).map((s) => s.price) : [];
    this.srcGhosts = this.cur.round ? clone(this.cur.round.ghosts || []) : [];
    this._anchor();
    this.loaded = true; this.connected = true; this.status = 'fixture';
    this.snap = this.cur;
    this.lastMsg = performance.now();
    this._timer = setInterval(() => this._tick(), 100);
    this._tick();
    setTimeout(() => this._replayEvents(), 900);
    this._evTimer = setInterval(() => this._replayEvents(), 5200);
  }

  _anchor() {                                              // the values the wobble oscillates around
    const s = this.cur, r = s.round, p = s.preview;
    this.anch = {
      x: r ? r.x : null, tilt: r ? r.tilt : (p ? p.tilt : 0), age: r ? r.age_s : 0, patience: p ? p.patience_s : 0,
      mx: r && r.merchant ? r.merchant.x : null, twinX: r && r.twin ? r.twin.x : null, t: this.lastT,
    };
  }

  _replayEvents() {
    if (!this.loaded || this.motion !== 'wobble') return;
    this.loopEvents.forEach((e, i) => setTimeout(() => this.events.push(clone(e)), i * 350));
  }

  _tick() {
    const now = performance.now();
    const e = ((now - this.t0) / 1000) * this.speed;
    const dt = Math.max(0, e - this.lastT);
    this.lastT = e;
    const s = this.cur;
    s.t = this.wall0 + e;
    if (s.feed) s.feed.tick_count = this.tick0 + Math.floor(e * 2.4 + 0.6 * Math.sin(e * 1.7));
    if (s.quote && s.feed && s.feed.ok) s.quote.ts = s.t - (s.feed.age_s || 0.2);
    if (s.market) s.market.day_frac = (s.market.day_frac + dt / 86400) % 1;
    const r = s.round, p = s.preview, A = this.anch, k = e - A.t;
    if (r && (s.phase === 'open' || s.phase === 'sending' || s.phase === 'closing')) {
      r.age_s = A.age + k;
      if (this.motion === 'walk') this._walk(dt);
      else if (this.motion === 'wobble' && !s.freeze) {
        r.x = r5(A.x + 0.012 * Math.sin(k * 1.3) + 0.006 * Math.sin(k * 3.1 + 1));
        r.tilt = r5(clampN(A.tilt + 0.12 * Math.sin(k * 0.7) + 0.05 * Math.sin(k * 2.3), -1, 1));
        this._revalue(r);
      }
      if (r.merchant && A.mx != null && this.motion === 'wobble') r.merchant.x = r5(A.mx + 0.035 * Math.sin(k * 0.45));
      if (r.twin && A.twinX != null && this.motion === 'wobble') r.twin.x = r5(A.twinX + 0.01 * Math.sin(k * 1.1 + 2));
      r.night = r.night || r.age_s > 600;
      r.tarnish = Math.min(1, r.age_s / 900);
    }
    if (p && (s.phase === 'lobby' || s.phase === 'aiming')) {
      p.tilt = r5(clampN(A.tilt + 0.1 * Math.sin(k * 0.6) + 0.04 * Math.sin(k * 1.9), -1, 1));
      if (s.phase === 'aiming' && p.at_door) p.patience_s = A.patience + k;
    }
    this.snap = s;
    this.lastMsg = now;                                      // the "link" is this animator: never freezes unless the fixture says so
  }

  _revalue(r) {                                              // fixture only: the roof sign follows the wobbling runner
    if (!r || !isFinite(r.x)) return;
    const R = r.x * (r.stop_dist0 + r.target_dist0) - r.stop_dist0;   // result per initial ounce, price units
    r.result_usd = R * r.qty0;
    r.value_usd = r.risk_usd + r.result_usd;
    r.pnl_usd = r.result_usd - (r.banked_usd || 0);
    r.value_text = money(r.value_usd, r.risk_usd);
    if (r.b) r.mark = r2((r.x - r.a) / r.b);
  }

  _walk(dt) {                                                // a locally created round: a gentle random walk of the mark price
    const s = this.cur, r = s.round;
    if (!r || s.phase !== 'open') return;
    const steps = Math.max(1, Math.round(dt / 0.1));
    for (let i = 0; i < steps; i++) {
      const g = (Math.random() + Math.random() + Math.random() - 1.5) * 0.06 + this.drift;
      this.mid += g;
      if (Math.random() < 0.02) this.drift = (Math.random() - 0.5) * 0.012;
    }
    const sp = s.quote.spread || 0.33;
    s.quote.bid = r2(this.mid - sp / 2); s.quote.ask = r2(this.mid + sp / 2); s.quote.mid = r5(this.mid);
    this.hist.push([s.t, this.mid]);
    while (this.hist.length && this.hist[0][0] < s.t - 10) this.hist.shift();
    const dmid = this.mid - this.hist[0][1];
    r.tilt = r5(clampN((r.side * dmid) / 0.6, -1, 1));
    r.mark = r.side > 0 ? s.quote.bid : s.quote.ask;
    r.x = r5(r.a + r.b * r.mark);
    this._revalue(r);
    r.mark = r.side > 0 ? s.quote.bid : s.quote.ask;
    r.stakes.forEach((st) => { st.passed = r.side * (r.mark - st.price) > 0.05; });
    r.can_anvil = r.stakes.some((st) => st.passed && r.side * (st.price - r.sl) > 0);
    r.can_haggle = r.x >= r.x_tp - 0.12 && r.tilt > 0 && r.haggles < r.haggle_max;
    if (r.twin) {
      r.twin.x = r5(r.x);
      const best = this._nextStake(r);
      if (best) r.twin.anvil_x = r5(r.a + r.b * (best.price - 0.01 * r.side));
    }
    if (r.merchant) {
      r.merchant.x += r.merchant.dir * dt * 0.05;
      if (r.merchant.x < -0.05) { r.merchant.x = 1.12; }
    }
    // the broker's stops: a long's SL/TP trigger on the bid, a short's on the ask (fixture copy of the rule)
    if (r.side * (r.mark - r.sl) <= 0) this._settle(r.x <= r.x_entry ? 'anvil' : 'anvil', r.sl);
    else if (r.side * (r.mark - r.tp) >= 0) this._settle('buyer', r.tp);
  }

  _nextStake(r) {
    const c = r.stakes.filter((st) => st.lit && st.passed && r.side * (st.price - 0.01 * r.side - r.sl) > 0.001 &&
      r.side * (r.mark - st.price) > 0.05);
    c.sort((a, b) => r.side * (a.price - b.price));
    return c[0] || null;
  }

  _remapTerrain(a, b) {
    const src = this.srcTerrain, L = this.srcLadder;
    if (!src || !L) return { x0: -0.3, x1: 1.3, h: new Array(96).fill(0.2), chasms: [], scorch: [], weathered: [] };
    const n = src.h.length, out = [];
    for (let i = 0; i < n; i++) {
      const xn = src.x0 + ((src.x1 - src.x0) * (i + 0.5)) / n;
      const price = (xn - a) / b;
      const xo = L.a + L.b * price;
      const j = Math.floor(((xo - src.x0) / (src.x1 - src.x0)) * n);
      out.push(j >= 0 && j < n ? src.h[j] : 0);
    }
    const mapX = (x) => r5(a + b * ((x - L.a) / L.b));
    return {
      x0: src.x0, x1: src.x1, h: out, scorch: (src.scorch || []).map(mapX).filter((x) => x > src.x0 && x < src.x1),
      chasms: (src.chasms || []).map(([p, q]) => [mapX(p), mapX(q)].sort((u, v) => u - v)),
      weathered: (src.weathered || []).map(([p, q]) => [mapX(p), mapX(q)].sort((u, v) => u - v)),
    };
  }

  _preview(side, target) {
    const s = this.cur, q = s.quote, sd = s.settings.stop_dist;
    const entry = side > 0 ? q.ask : q.bid;
    const sl = r2(entry - side * sd), tp = r2(entry + side * target);
    const { a, b } = ladder(side, entry, sl, tp);
    const mark = side > 0 ? q.bid : q.ask;
    const xm = r5(a + b * mark), xe = r5(a + b * entry);
    const stakes = this.stakePrices.map((p) => ({ price: p, x: r5(a + b * (p - 0.01 * side)), lit: true }))
      .filter((st) => st.x >= -0.05 && st.x <= 1.05);
    return { entry, stop: sl, target_price: tp, side, a: r5(a), b: r5(b), x_entry: xe, x_mark: xm, tilt: 0.2 * side,
      patience_s: 0, at_door: false, stakes, terrain: this._remapTerrain(a, b), pit: { x0: Math.min(xm, xe), x1: Math.max(xm, xe), depth: 0.55 } };
  }

  _refuse(why, extra = []) { return { accepted: false, why, events: extra }; }

  async act(action, args = {}) {
    const nonce = this.nonce();
    if (!this.loaded) return { accepted: false, why: 'loading', nonce };
    if (this.frozen() && action !== 'kill') { const r = { accepted: false, why: 'frozen', nonce, local: true }; this._note({ action, ...r }); return r; }
    this.sentCount++;
    await sleep(60 + Math.random() * 70);
    let res;
    try { res = this._apply(action, args || {}); } catch (e) { console.error('[net] fixture echo', action, e); res = { accepted: false, why: 'fixture: ' + e.message }; }
    this.events.push(res.accepted ? { type: 'accepted', nonce, action, why: null } : { type: 'refused', nonce, action, why: res.why });
    (res.events || []).forEach((ev) => this.events.push(ev));
    const out = { accepted: !!res.accepted, why: res.why || null, nonce };
    this._note({ action, ...out });
    return out;
  }

  async settings(obj) {
    const st = this.cur.settings;
    if (obj.live_enabled === true && obj.confirm_word !== 'CONFIRM') return { ok: false, why: 'confirm', settings: st };
    for (const k of ['coin_oz', 'stop_dist', 'sound', 'plain_line', 'eject_words', 'live_enabled']) if (k in obj) st[k] = obj[k];
    st.risk_usd = r5(st.coin_oz * st.stop_dist);
    st.money_unit = st.risk_usd < 1 ? 'cents' : 'dollars';
    st.can_split = st.coin_oz >= 0.02;
    this.cur.limits.alley_machete_needed = st.can_split;
    await sleep(80);
    return { ok: true, why: null, settings: clone(st) };
  }

  async getJSON() { return null; }

  _apply(action, a) {
    const s = this.cur, ph = s.phase, r = s.round, st = s.settings, sh = s.market.shutters;
    switch (action) {
      case 'fund': {
        if (ph !== 'lobby') return this._refuse('phase');
        if (sh && sh.down) return this._refuse(sh.reason || 'shutters');
        if (a.kind === 'live' && !s.limits.live_allowed) return this._refuse(s.limits.why_not_live || 'alley');
        if (a.side) st.side = a.side;
        if (a.target) st.target = a.target;
        if ('twin' in a) st.twin_invited = !!a.twin;
        this.fundKind = a.kind || 'wooden';
        s.preview = this._preview(st.side, st.target);
        s.preview.at_door = true; s.preview.patience_s = 0;
        s.phase = 'aiming';
        this._anchor();
        return { accepted: true };
      }
      case 'unfund':
        if (ph !== 'aiming') return this._refuse('phase');
        s.phase = 'lobby'; s.preview.at_door = false; this._anchor();
        return { accepted: true };
      case 'flip': {
        if (ph !== 'lobby' && ph !== 'aiming') return this._refuse('phase');
        st.side = a.side === -1 ? -1 : 1;
        const door = s.preview ? s.preview.at_door : false;
        s.preview = this._preview(st.side, st.target); s.preview.at_door = door; this._anchor();
        return { accepted: true };
      }
      case 'set_target': {
        if (ph !== 'lobby' && ph !== 'aiming') return this._refuse('phase');
        if (!st.targets.includes(a.target)) return this._refuse('target');
        st.target = a.target;
        const door = s.preview ? s.preview.at_door : false;
        s.preview = this._preview(st.side, st.target); s.preview.at_door = door; this._anchor();
        return { accepted: true };
      }
      case 'invite_twin':
        st.twin_invited = !!a.on;
        return { accepted: true };
      case 'shoot': {
        if (ph !== 'aiming') return this._refuse('phase');
        if (sh && sh.down) return this._refuse(sh.reason || 'shutters');
        s.phase = 'sending';
        this.motion = 'none';
        setTimeout(() => this._open(), 380);
        return { accepted: true };
      }
      case 'anvil_next': {
        if (ph !== 'open' || !r) return this._refuse('phase');
        const nx = this._nextStake(r);
        if (!nx) return this._refuse('no_stake', [{ type: 'anvil', ok: false, x: r.anvil.x }]);
        r.sl = r2(nx.price - 0.01 * r.side);
        nx.used = true;
        r.anvil = { price: r.sl, x: r5(r.a + r.b * r.sl), kind: 'stake', pending: false };
        r.x_sl = r.anvil.x;
        r.can_anvil = !!this._nextStake(r);
        return { accepted: true, events: [{ type: 'anvil', ok: true, x: r.anvil.x }] };
      }
      case 'wall': {
        if (ph !== 'open' || !r) return this._refuse('phase');
        if (r.walls_left <= 0) return this._refuse('walls_max', [{ type: 'wall', ok: false, x: r.x }]);
        let price = r2(r.mark - r.side * 0.3);
        if (r.side * (price - r.sl) <= 0.001) return this._refuse('not_tighter', [{ type: 'wall', ok: false, x: r.x }]);
        const x = r5(r.a + r.b * price);
        r.walls.push({ price, x });
        r.walls_left -= 1; r.can_wall = r.walls_left > 0;
        r.sl = price; r.anvil = { price, x, kind: 'wall', pending: false }; r.x_sl = x;
        return { accepted: true, events: [{ type: 'wall', ok: true, x }] };
      }
      case 'haggle': {
        if (ph !== 'open' || !r) return this._refuse('phase');
        const behind = r.stakes.filter((k) => k.passed && r.side * (k.price - r.sl) > 0).sort((p, q) => r.side * (q.price - p.price))[0];
        if (r.haggles >= r.haggle_max || r.x < r.x_tp - 0.12 || r.tilt <= 0 || !behind) return this._refuse('not_now', [{ type: 'haggle', ok: false }]);
        r.haggles += 1;
        r.tp = r2(r.tp + r.side * 0.1);
        r.x_tp = r5(r.a + r.b * r.tp);
        r.target_dist = r2(r.target_dist + 0.1);
        r.sl = r2(behind.price - 0.01 * r.side); behind.used = true;
        r.anvil = { price: r.sl, x: r5(r.a + r.b * r.sl), kind: 'haggle', pending: false }; r.x_sl = r.anvil.x;
        r.tag_text = money(r.risk_usd + r.qty * Math.abs(r.tp - r.fill) + (r.banked_usd || 0), r.risk_usd);
        return { accepted: true, events: [{ type: 'haggle', ok: true }] };
      }
      case 'machete': {
        if (ph !== 'open' || !r) return this._refuse('phase');
        if (r.machete_done || r.qty < 0.02 - 1e-9) return this._refuse('chained', [{ type: 'machete', ok: false, usd: 0 }]);
        const half = Math.floor((r.qty / 2) / 0.01 + 1e-9) * 0.01;
        const banked = r2(r.side * (r.mark - r.fill) * half * 1e4) / 1e4;
        r.banked_usd = (r.banked_usd || 0) + banked;
        r.qty = r5(r.qty - half);
        r.machete_done = true; r.can_machete = false;
        const L = ladder(r.side, r.fill, r.fill - r.side * r.stop_dist0, r.fill + r.side * r.target_dist0, r.banked_usd, r.qty, r.qty0);
        r.a = r5(L.a); r.b = r5(L.b);
        const X = (p) => r5(r.a + r.b * p);
        r.x = X(r.mark); r.x_entry = X(r.fill); r.x_sl = X(r.sl); r.x_tp = X(r.tp);
        r.anvil.x = r.x_sl;
        r.stakes.forEach((k) => { k.x = X(k.price - 0.01 * r.side); });
        r.walls.forEach((w) => { w.x = X(w.price); });
        const gusd = r.banked_usd - r.qty * Math.abs(r.fill - r.sl) * (r.side * (r.sl - r.fill) < 0 ? 1 : -1);
        r.golden = { price: r.sl, x: r.x_sl, usd: r5(gusd), text: money(gusd, r.risk_usd) };
        this._revalue(r);
        this._anchor();
        return { accepted: true, events: [{ type: 'machete', ok: true, usd: banked }] };
      }
      case 'merchant':
      case 'eject': {
        if (ph !== 'open' || !r) return this._refuse('phase');
        s.phase = 'closing';
        this.motion = 'none';
        setTimeout(() => this._settle(action, r.mark), action === 'eject' ? 900 : 650);
        return { accepted: true };
      }
      case 'ack': {
        if (ph !== 'settled') return this._refuse('phase');
        s.phase = 'lobby';
        s.round = null; s.settlement = null;
        s.preview = this._preview(st.side, st.target);
        this.motion = 'wobble';
        this._anchor();
        return { accepted: true };
      }
      case 'kill': {
        if (r && (ph === 'open' || ph === 'closing')) this._settle('kill', r.mark);
        s.market.shutters = { down: true, reason: 'locked', until: s.t + 3600 * 12 };
        s.limits.locked_until = s.market.shutters.until;
        return { accepted: true };
      }
      default:
        return this._refuse('unknown');
    }
  }

  _open() {
    const s = this.cur, p = s.preview, st = s.settings, q = s.quote;
    if (!p) return;
    const side = p.side, coin = st.coin_oz;
    const slip = Math.round(Math.random() * 3) / 100;
    const fill = r2(p.entry + side * slip);
    const sl = r2(fill - side * st.stop_dist), tp = r2(fill + side * st.target);
    const L = ladder(side, fill, sl, tp, 0, coin, coin);
    const a = r5(L.a), b = r5(L.b), X = (pr) => r5(a + b * pr);
    const mark = side > 0 ? q.bid : q.ask;
    this.mid = q.mid; this.drift = 0; this.hist = [[s.t, q.mid]];
    const risk = st.risk_usd;
    const stakes = this.stakePrices.map((pr) => ({ price: pr, x: X(pr - 0.01 * side), lit: true, passed: side * (mark - pr) > 0.05, used: false }))
      .filter((k) => k.x >= -0.05 && k.x <= 1.05);
    const r = {
      id: 'fixture-' + Date.now(), kind: this.fundKind || 'wooden', side, qty: coin, qty0: coin, opened_t: s.t, age_s: 0,
      patience_s: p.patience_s, fill, sl, tp, stop_dist0: L.sd0, target_dist0: L.td0, target_dist: L.td0, mark, spread: q.spread,
      a, b, x: X(mark), x_entry: X(fill), x_sl: X(sl), x_tp: X(tp), tilt: p.tilt,
      pnl_usd: 0, banked_usd: 0, result_usd: 0, value_usd: risk, risk_usd: risk, value_text: money(risk, risk),
      tag_text: money(risk + coin * L.td0, risk),
      anvil: { price: sl, x: X(sl), kind: 'vault', pending: false }, stakes, walls: [], walls_left: 99, golden: null,
      haggles: 0, haggle_max: 3, can_haggle: false, can_wall: true, can_anvil: false, can_machete: coin >= 0.02, machete_done: false,
      merchant: { x: 1.1, visible: true, dir: -1, insists: false },
      terrain: this._remapTerrain(a, b), pit: { x0: Math.min(X(mark), X(fill)), x1: Math.max(X(mark), X(fill)), depth: 0.55 },
      night: false, golden_hour: false, tarnish: 0,
      twin: st.twin_invited ? { x: X(mark), anvil_x: X(sl), state: 'running', result_usd: null } : null,
      ghosts: this.srcGhosts, rat: [{ t: s.t, usd: r5(q.spread * coin), why: 'spread' }], pending: null, last_refusal: null,
    };
    this._revalue(r);
    s.round = r; s.preview = null; s.phase = 'open';
    this.motion = 'walk';
    this._anchor();
    this.events.push({ type: 'fill', side, price: fill, qty: coin });
    setTimeout(() => this.events.push({ type: 'rat', usd: r5(q.spread * coin), why: 'spread' }), 500);
    if (slip > 0) setTimeout(() => this.events.push({ type: 'rat', usd: r5(slip * coin), why: 'slippage' }), 900);
  }

  _settle(outcome, exitPrice) {
    const s = this.cur, r = s.round;
    if (!r || s.phase === 'settled') return;
    const res = r5((r.banked_usd || 0) + r.side * (exitPrice - r.fill) * r.qty);
    const names = { buyer: 'the take profit sold it', anvil: 'the stop loss sold it', merchant: 'you sold it to the merchant at market',
      eject: 'you ejected at market', kill: 'the kill switch closed it' };
    const verb = r.side > 0 ? 'Bought' : 'Sold';
    const sp = (r.rat || []).filter((b) => b.why === 'spread').reduce((t, b) => t + b.usd, 0);
    const sl = (r.rat || []).filter((b) => b.why === 'slippage').reduce((t, b) => t + b.usd, 0);
    const bal = s.account ? r5(s.account.balance + (r.kind === 'wooden' ? 0 : res)) : null;
    s.settlement = {
      id: r.id, kind: r.kind, side: r.side, outcome, result_usd: res, result_text: money(res, r.risk_usd),
      costs: { spread_usd: r5(sp), slippage_usd: r5(sl), fee_usd: 0, financing_usd: 0 }, fill: r.fill, exit: exitPrice, qty0: r.qty0,
      age_s: Math.round(r.age_s), chasm: null, balance_after: bal, twin_result_usd: r.twin ? r5(r.side * (exitPrice - r.fill) * r.qty0) : null,
      would_have_usd: (outcome === 'eject' || outcome === 'merchant') ? -r.risk_usd : null, t: s.t,
      plain: `${verb} ${r.qty0.toFixed(2)} oz of gold at ${r.fill.toLocaleString('en-US', { minimumFractionDigits: 2 })}; ${names[outcome] || outcome} at ${Number(exitPrice).toLocaleString('en-US', { minimumFractionDigits: 2 })}: ${money(res, r.risk_usd)} after a ${money(sp, r.risk_usd)} spread.`,
    };
    r.x = r5(r.a + r.b * exitPrice); r.mark = exitPrice;
    this._revalue(r);
    s.phase = 'settled';
    this.motion = 'none';
    if (s.account && r.kind !== 'wooden') { s.account.balance = bal; s.account.equity = bal; }
    s.limits.rounds_today += 1;
    if (r.kind === 'wooden') s.limits.alley_done = Math.min(s.limits.alley_needed, s.limits.alley_done + 1);
    s.lobby.jar_usd = r5(s.lobby.jar_usd + sp + sl);
    s.lobby.jar_bites += (r.rat || []).length;
    if (outcome === 'buyer') s.lobby.cabinet.push({ t: s.t, usd: res, kind: r.kind });
    this.events.push({ type: 'settled', outcome });
  }
}
