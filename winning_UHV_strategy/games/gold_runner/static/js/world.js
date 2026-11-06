// world.js (F-WORLD) - Golden Gravity: the street and the sky. Canvas 2D, procedural, no globals except per-world caches and pools.
//
// CONTRACT 8.3 API (exact):
//   makeWorld() -> world
//   world.drawSky(ctx,w,h,env,t)              sky by session/time + weather (sun/moon from day_frac, deco clouds, distant lightning)
//   world.drawSkyline(ctx,w,h,camX,env,t)     two parallax layers of New York high-rises (setbacks, Chrysler crowns, glass towers, antennas)
//   world.drawTerrain(ctx,view,terrain,env,t) underworks + pistons, the marble / ledger / gear street, chasms, scorch, weathered
//   world.groundYAt(view,terrain,xn) -> px    where feet stand at x_norm xn (heights + tilt); x is view.xToScreen(xn)
//   world.drawPit(ctx,view,pit,env,t)         the Spread Pit: bubbling molasses at the door, depth from pit.depth
//   world.drawFog(ctx,view,fromXn,env,t)      fog beyond the buyer
//   world.drawWeather(ctx,w,h,env,dt,t)       ash (dead), ticker-tape rain + lightning (storm), motes (calm/active); pooled particles
//   world.drawSeasonBand(ctx,w,env,t)         quiet strip at the very top: leaves toward the buyer / snow toward the bank
//   world.drawGrade(ctx,w,h,env,t)            golden hour, night (+ lamp light), wooden tint, freeze sepia + static, REPLAY marquee
// Extras (optional helpers, not required by the contract):
//   world.heightAt(terrain,xn) -> units      world.groundSlopeAt(view,terrain,xn) -> radians on screen
//   world.screenToXn(view,px) -> xn          world.tiltToRad(tilt,mirror) -> on-screen angle for a player-signed tilt
//   world.pitSinkAt(view,pit,xn) -> px a character standing there sinks into the molasses
//   world.drawPitFront(ctx,view,pit,env,t)   redraws the molasses skin over a character's feet (knee-deep look)
//   world.drawChasmRift(ctx,view,[xa,xb],env,t,{topAt,bottom})  the barrel's Void Chasm torn ON TOP of the bank's pier (settlement)
//
// Recommended draw order per frame:
//   drawSky, drawSkyline, drawSeasonBand, drawTerrain, drawPit, (bank, stakes, characters ...), [drawPitFront], drawFog, drawWeather, drawGrade
//
// GEOMETRY (binding for F-CORE): the walking line is
//      y(xn) = view.groundY - H(xn) * view.s + (view.xToScreen(xn) - view.pivotX) * tan(view.tiltRad)
//   H(xn) = terrain heights in units (1 unit = the Runner's height), smoothed + interpolated from terrain.h bins, clamped outside [x0,x1].
//   The tilt is a vertical SHEAR about pivotX: the ground line turns by exactly tiltRad and verticals (pistons, stakes) stay vertical, so a
//   point of the ground keeps screen x = view.xToScreen(xn) and groundYAt is exact. view.tiltRad is the ON-SCREEN angle (canvas convention:
//   positive = clockwise = the right end lower). F-CORE applies the side, e.g. tiltRad = world.tiltToRad(round.tilt, mirror).
//   Chasms / scorch / weathered are decals and never change the walking line: inside a chasm it bridges the void (cartoon physics).
// env = { session, day_frac, weather, vol, lightning, season, night, golden_hour, freeze, wooden, replay, mirror, tilt, t }
//   (+ optional env.lights = [{x, y, r}] screen-px light sources that stay lit under the night grade; default: the Buyer's lamp).
// Every env field may be missing or null: sensible defaults are used.

import { P, SKY, LINE, FONT, hexToRgb, rand, clamp, lerp, ease } from './palette.js';

const TAU = Math.PI * 2;
const DEG = Math.PI / 180;
export const MAX_TILT_RAD = 25 * DEG;

// ground cross-section, in units (multiply by view.s)
export const GROUND = {
  hillUnits: 1.1, hillExp: 0.7,          // terrain.h = 1 -> a hill 1.1 Runner tall; the exponent lifts small dwell into view
  back: 0.10, front: 0.07,               // the top face (walking surface) spans walk-back .. walk+front
  marble: 0.28, trim: 0.035, frieze: 0.24, gears: 0.2, iron: 0.09,
};
GROUND.slab = GROUND.front + GROUND.marble + GROUND.trim + GROUND.frieze + GROUND.gears + GROUND.iron;   // walking line -> slab underside

// ------------------------------------------------------------------------------------------------------------ small utilities
const RGBC = Object.create(null);
function RGB(hex) { let c = RGBC[hex]; if (!c) c = RGBC[hex] = hexToRgb(hex); return c; }
function mixc(a, b, t, out) {
  out = out || [0, 0, 0];
  out[0] = a[0] + (b[0] - a[0]) * t; out[1] = a[1] + (b[1] - a[1]) * t; out[2] = a[2] + (b[2] - a[2]) * t;
  return out;
}
function css(c, a) {
  const r = c[0] < 0 ? 0 : c[0] > 255 ? 255 : c[0] | 0, g = c[1] < 0 ? 0 : c[1] > 255 ? 255 : c[1] | 0, b = c[2] < 0 ? 0 : c[2] > 255 ? 255 : c[2] | 0;
  return a === undefined || a >= 1 ? `rgb(${r},${g},${b})` : `rgba(${r},${g},${b},${a < 0 ? 0 : a.toFixed(3)})`;
}
function shadec(c, k) { return k >= 0 ? mixc(c, [255, 255, 255], k) : mixc(c, [0, 0, 0], -k); }
function lumc(c) { return (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255; }
function satc(c, k) { const l = lumc(c) * 255; return [l + (c[0] - l) * k, l + (c[1] - l) * k, l + (c[2] - l) * k]; }
function qkey(c, step = 6) { return ((c[0] / step) | 0) + ',' + ((c[1] / step) | 0) + ',' + ((c[2] / step) | 0); }
const smooth01 = (e0, e1, x) => { const t = clamp((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); };
const fract = (x) => x - Math.floor(x);
const wrap = (v, m) => ((v % m) + m) % m;

function makeCanvas(w, h) {
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.ceil(w)); c.height = Math.max(1, Math.ceil(h));
  return c;
}
// smooth 1-D value noise in [0,1], deterministic per seed
function vnoise(x, seed = 0) {
  const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
  return lerp(rand(i * 1.731 + seed * 91.7), rand((i + 1) * 1.731 + seed * 91.7), u);
}
function fbm(x, seed = 0) { return vnoise(x, seed) * 0.6 + vnoise(x * 2.13, seed + 3) * 0.28 + vnoise(x * 4.7, seed + 7) * 0.12; }
// cheap radial soft blob sprite (white, alpha falloff) - tint by drawing with globalAlpha / composite
function softBlob(r, color = [255, 255, 255], inner = 0.0) {
  const c = makeCanvas(r * 2, r * 2), g = c.getContext('2d');
  const gr = g.createRadialGradient(r, r, r * inner, r, r, r);
  gr.addColorStop(0, css(color, 1)); gr.addColorStop(0.45, css(color, 0.55)); gr.addColorStop(1, css(color, 0));
  g.fillStyle = gr; g.fillRect(0, 0, r * 2, r * 2);
  return c;
}
function gearPath(g, cx, cy, r, teeth, toothH, rot = 0, hole = 0) {
  g.beginPath();
  const n = teeth * 4;
  for (let i = 0; i <= n; i++) {
    const a = rot + (i / n) * TAU, phase = i % 4;
    const rr = phase === 1 || phase === 2 ? r + toothH : r;
    const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr;
    if (i === 0) g.moveTo(x, y); else g.lineTo(x, y);
  }
  g.closePath();
  if (hole > 0) { g.moveTo(cx + hole, cy); g.arc(cx, cy, hole, 0, TAU, true); }
}

// ------------------------------------------------------------------------------------------------------------ env normalisation
const WEATHERS = { dead: 0.05, calm: 0.25, active: 0.55, storm: 0.95 };
function normEnv(src, out) {
  src = src || {};
  out.session = typeof src.session === 'string' ? src.session : 'london';
  out.day_frac = Number.isFinite(src.day_frac) ? wrap(src.day_frac, 1) : 0.4;
  out.weather = Object.prototype.hasOwnProperty.call(WEATHERS, src.weather) ? src.weather : 'calm';
  out.vol = Number.isFinite(src.vol) ? clamp(src.vol, 0, 1) : WEATHERS[out.weather];
  out.lightning = !!src.lightning;
  out.season = Number.isFinite(src.season) ? clamp(src.season, -1, 1) : 0;
  out.night = !!src.night; out.golden_hour = !!src.golden_hour; out.freeze = !!src.freeze;
  out.wooden = !!src.wooden; out.replay = !!src.replay; out.mirror = !!src.mirror;
  out.tilt = Number.isFinite(src.tilt) ? clamp(src.tilt, -1, 1) : 0;
  out.lights = Array.isArray(src.lights) ? src.lights : null;
  out.lampOnly = !!src.lampOnly;            // night fell on a long round: the Buyer's lamp is the only light (the city's windows go dark)
  return out;
}

// ------------------------------------------------------------------------------------------------------------ terrain profile + geometry
function terrainHash(tr) {
  let h = 2166136261 >>> 0;
  const put = (v) => { h = Math.imul(h ^ (Math.round((+v || 0) * 4096) | 0), 16777619) >>> 0; };
  put(tr.x0); put(tr.x1);
  const a = tr.h || []; put(a.length);
  for (let i = 0; i < a.length; i++) put(a[i]);
  const ch = tr.chasms || []; put(ch.length + 777); for (const p of ch) { put(p[0]); put(p[1]); }
  const we = tr.weathered || []; put(we.length + 555); for (const p of we) { put(p[0]); put(p[1]); }
  const sc = tr.scorch || []; put(sc.length + 999); for (const v of sc) put(v);
  return h;
}
function getProfile(W, tr) {
  if (!tr || !tr.h || !tr.h.length) return null;
  if (W._profObj === tr && W._prof) return W._prof;
  const key = terrainHash(tr);
  if (W._prof && W._prof.key === key) { W._profObj = tr; return W._prof; }
  const n = tr.h.length, raw = tr.h, u = new Float32Array(n);
  const K = [1, 2, 3, 2, 1];
  for (let i = 0; i < n; i++) {
    let s = 0;
    for (let j = -2; j <= 2; j++) s += (+raw[clamp(i + j, 0, n - 1)] || 0) * K[j + 2];
    u[i] = GROUND.hillUnits * Math.pow(clamp(s / 9, 0, 1), GROUND.hillExp);
  }
  let x0 = Number.isFinite(+tr.x0) ? +tr.x0 : -0.3, x1 = Number.isFinite(+tr.x1) ? +tr.x1 : 1.3;
  if (!(x1 > x0)) { x0 = -0.3; x1 = 1.3; }
  let maxU = 0; for (let i = 0; i < n; i++) if (u[i] > maxU) maxU = u[i];
  W._prof = { key, x0, x1, n, u, maxU, tr };
  W._profObj = tr;
  return W._prof;
}
// height of the walking line above the base, in units (Catmull-Rom between bin centres, clamped outside the bins)
function heightAt(prof, xn) {
  if (!prof) return 0;
  const n = prof.n, u = prof.u;
  if (n === 1) return u[0];
  const f = (xn - prof.x0) / (prof.x1 - prof.x0) * n - 0.5;
  if (!(f > 0)) return u[0];
  if (f >= n - 1) return u[n - 1];
  const i = f | 0, t = f - i;
  const p0 = u[i > 0 ? i - 1 : 0], p1 = u[i], p2 = u[i + 1], p3 = u[i + 2 < n ? i + 2 : n - 1];
  const t2 = t * t, t3 = t2 * t;
  const v = 0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (3 * p1 - p0 - 3 * p2 + p3) * t3);
  return v > 0 ? v : 0;
}
// the view's x mapping as screen = A * xn + B (xToScreen is affine in F-CORE's layout; mirror -> A < 0)
function viewAffine(view, out) {
  const a = view.xToScreen(0), b = view.xToScreen(1);
  out[0] = b - a; out[1] = a;
  if (!Number.isFinite(out[0]) || Math.abs(out[0]) < 1e-6) { out[0] = view.w || 1600; out[1] = 0; }
  return out;
}
function tanTilt(view) { const r = +view.tiltRad || 0; return Math.tan(clamp(r, -1.2, 1.2)); }
function walkY(view, prof, xn, k) {
  return view.groundY - heightAt(prof, xn) * view.s + (view.xToScreen(xn) - (Number.isFinite(view.pivotX) ? view.pivotX : view.w / 2)) * k;
}

// ============================================================================================================ SKY
// The sun is the session clock: dawn = Asia, high noon = London, the long aggressive afternoon = New York, night = the dead hours.
// Session sets the base gradient; weather modifies it (active = an aggressive warm horizon on top of the session; storm and dead override).
const SKYRGB = {}; for (const k in SKY) SKYRGB[k] = SKY[k].map((hx) => RGB(hx));
const C_WHITE = [255, 255, 255], C_BLACK = [0, 0, 0];
const C_HOTPINK = RGB('#e2506e'), C_HOTORANGE = RGB('#ff8a3d'), C_GOLDGLOW = RGB('#ffd27a'), C_DEEPPURPLE = RGB('#3b2a7a');
const C_STORMPURPLE = RGB('#3a1f5a'), C_NIGHTRED = RGB('#5a2440'), C_SEPIADARK = RGB('#3a2e1f');

function skyHorizon(W, h) {
  if (W._horizonY && W._horizonH) return W._horizonH === h ? W._horizonY : W._horizonY / W._horizonH * h;
  return 0.72 * h;
}
function mixStops(dst, pal, t) { for (let i = 0; i < 4; i++) mixc(dst[i], pal[i], t, dst[i]); }
function setStops(dst, pal) { for (let i = 0; i < 4; i++) { dst[i][0] = pal[i][0]; dst[i][1] = pal[i][1]; dst[i][2] = pal[i][2]; } }

// target sky state for this env (pure function of env; smoothed afterwards)
function skyTarget(W, E) {
  const T = W._skyT || (W._skyT = {
    stops: [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]], sunX: 0.5, sunE: 0.5, sunVis: 1, sunR: 1, sunCol: [255, 230, 170],
    moonX: 0.7, moonE: 0.6, moonVis: 0, stars: 0, rays: 0, kind: 'day', nightness: 0, warm: 0,
  });
  const hr = E.day_frac * 24, S = SKYRGB;
  let sx = 0.5, el = 0.6, nightness = 0, moonX = 0.7, moonE = 0.62, stars = 0;
  const isNight = E.night || E.session === 'dead' || E.session === 'closed';
  if (isNight) {
    setStops(T.stops, S.night);
    const p = E.session === 'dead' ? clamp((hr - 20.75) / 2.25, 0, 1) : fract(hr / 24 + 0.15);
    moonX = lerp(0.22, 0.78, p); moonE = 0.5 + 0.22 * Math.sin(Math.PI * p);
    el = -0.2; nightness = 1; stars = 1;
  } else if (E.session === 'asia') {
    const p = clamp(wrap(hr - 23, 24) / 9, 0, 1);
    setStops(T.stops, S.night); mixStops(T.stops, S.dawn, smooth01(0.0, 0.3, p));
    if (p > 0.8) mixStops(T.stops, S.noon, 0.4 * smooth01(0.8, 1, p));
    sx = lerp(0.1, 0.34, p); el = lerp(0.12, 0.44, smooth01(0.0, 1, p));
    nightness = 1 - smooth01(0.04, 0.32, p); stars = nightness * 0.85; moonX = 0.8; moonE = 0.55;
  } else if (E.session === 'newyork') {
    const p = clamp((hr - 13.5) / 7.25, 0, 1);
    setStops(T.stops, S.noon); mixStops(T.stops, S.afternoon, smooth01(0, 0.35, p));
    if (p > 0.78) mixStops(T.stops, S.golden, 0.45 * smooth01(0.78, 1, p));
    sx = lerp(0.6, 0.9, p); el = 0.66 * Math.pow(1 - p, 0.9) + 0.1;
    nightness = 0.25 * smooth01(0.85, 1, p);
  } else {   // london (and anything unknown): high noon
    const p = clamp((hr - 8) / 5.5, 0, 1);
    setStops(T.stops, S.noon); if (p < 0.12) mixStops(T.stops, S.dawn, 0.3 * (1 - p / 0.12));
    sx = lerp(0.34, 0.6, p); el = 0.62 + 0.26 * Math.sin(Math.PI * Math.min(1, p * 1.25));
  }
  let rays = 0.3, sunVis = smooth01(-0.06, 0.03, el), warm = 0;
  if (E.golden_hour && !isNight) {
    mixStops(T.stops, S.golden, 0.85); sx = 0.72; el = 0.2; sunVis = 1; rays = 0.9; warm = 1; nightness = 0;
  }
  // ---- weather
  const v = E.vol;
  let kind = isNight ? 'night' : 'day';
  if (E.weather === 'storm') {
    for (let i = 0; i < 4; i++) mixc(T.stops[i], S.storm[i], isNight ? 0.75 : 0.9 - i * 0.03, T.stops[i]);
    mixc(T.stops[3], C_STORMPURPLE, 0.35, T.stops[3]);
    sunVis *= 0.12; rays = 0; stars *= 0.08; kind = 'storm';
  } else if (E.weather === 'dead') {
    if (isNight) mixStops(T.stops, [C_SEPIADARK, C_SEPIADARK, mixc(C_SEPIADARK, S.dead[1], 0.3), mixc(C_SEPIADARK, S.dead[2], 0.35)], 0.6);
    else mixStops(T.stops, S.dead, 0.86);
    sunVis *= 0.5; rays = 0; stars *= 0.3; kind = 'dead';
  } else if (E.weather === 'active') {
    const a = 0.55 + 0.45 * clamp((v - 0.3) / 0.6, 0, 1);       // vol 0.55 -> ~0.74
    if (isNight) { mixc(T.stops[3], C_NIGHTRED, 0.45 * a, T.stops[3]); mixc(T.stops[2], C_NIGHTRED, 0.25 * a, T.stops[2]); }
    else {
      mixc(T.stops[0], C_DEEPPURPLE, 0.12 * a, T.stops[0]);
      mixc(T.stops[1], C_HOTPINK, 0.16 * a, T.stops[1]);
      mixc(T.stops[2], C_HOTORANGE, 0.52 * a, T.stops[2]);
      mixc(T.stops[3], C_GOLDGLOW, 0.6 * a, T.stops[3]);
      for (let i = 0; i < 4; i++) { const s = satc(T.stops[i], 1 + 0.25 * a); T.stops[i][0] = s[0]; T.stops[i][1] = s[1]; T.stops[i][2] = s[2]; }
      rays = 0.75 + 0.35 * a; warm = Math.max(warm, a);
    }
    kind = isNight ? 'night' : 'active';
  } else {   // calm: the plain session sky, a little hazy at the horizon
    mixc(T.stops[3], C_WHITE, 0.1, T.stops[3]);
    rays = Math.min(rays, 0.35);
    if (isNight) kind = 'night'; else kind = 'calm';
  }
  if (E.golden_hour && !isNight && kind !== 'storm' && kind !== 'dead') kind = 'golden';
  // sun colour: white-gold high up, orange near the horizon
  const low = 1 - smooth01(0.1, 0.5, el);
  mixc(RGB('#fff4d0'), RGB('#ff8a3a'), low * 0.9, T.sunCol);
  if (kind === 'dead') mixc(T.sunCol, RGB('#efe2c2'), 0.7, T.sunCol);
  if (kind === 'storm') mixc(T.sunCol, RGB('#8a6ab0'), 0.8, T.sunCol);
  T.sunX = E.mirror ? 1 - sx : sx; T.sunE = el; T.sunVis = isNight ? 0 : sunVis;
  T.sunR = (1 + 0.35 * low) * (kind === 'active' ? 1.12 : 1);
  T.moonX = E.mirror ? 1 - moonX : moonX; T.moonE = moonE; T.moonVis = isNight ? (kind === 'storm' ? 0.15 : kind === 'dead' ? 0.4 : 1) : nightness * 0.6;
  T.stars = stars; T.rays = rays * sunVis; T.kind = kind; T.nightness = nightness; T.warm = warm;
  return T;
}

const SKY_FIELDS = ['sunX', 'sunE', 'sunVis', 'sunR', 'moonX', 'moonE', 'moonVis', 'stars', 'rays', 'nightness', 'warm'];
function skyCurrent(W, T, t) {
  let C = W._skyC;
  const first = !C;
  if (first) C = W._skyC = { stops: [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]], sunCol: [0, 0, 0] };
  const dt = W._skyLastT == null ? 0 : clamp(t - W._skyLastT, 0, 0.25);
  W._skyLastT = t;
  const k = first ? 1 : 1 - Math.exp(-dt * 2.4);
  for (let i = 0; i < 4; i++) mixc(C.stops[i], T.stops[i], k, C.stops[i]);
  mixc(C.sunCol, T.sunCol, k, C.sunCol);
  for (const f of SKY_FIELDS) {
    C[f] = first ? T[f] : lerp(C[f], T[f], k);
  }
  C.kind = T.kind;
  return C;
}

// ---- sky sprites / caches
function starField(W, w, hy) {
  const key = w + 'x' + Math.round(hy);
  if (W._stars && W._stars.key === key) return W._stars.c;
  const c = makeCanvas(w, hy), g = c.getContext('2d');
  const n = Math.round(w * hy / 4200);
  for (let i = 0; i < n; i++) {
    const x = rand(i * 3.71 + 1) * w, y = Math.pow(rand(i * 5.13 + 2), 1.4) * hy * 0.95, r = 0.4 + Math.pow(rand(i * 7.7 + 3), 3) * 1.5;
    g.fillStyle = `rgba(${rand(i) > 0.8 ? '255,226,180' : '230,236,255'},${(0.35 + 0.65 * rand(i * 2.9)).toFixed(2)})`;
    g.beginPath(); g.arc(x, y, r, 0, TAU); g.fill();
  }
  for (let i = 0; i < Math.round(n / 22); i++) {      // four-point deco sparkles
    const x = rand(i * 9.1 + 4) * w, y = rand(i * 4.3 + 5) * hy * 0.7, r = 3 + rand(i * 6.6) * 4;
    g.fillStyle = 'rgba(255,246,220,0.9)';
    g.beginPath(); g.moveTo(x, y - r); g.lineTo(x + r * 0.22, y); g.lineTo(x, y + r); g.lineTo(x - r * 0.22, y); g.closePath(); g.fill();
    g.beginPath(); g.moveTo(x - r, y); g.lineTo(x, y + r * 0.22); g.lineTo(x + r, y); g.lineTo(x, y - r * 0.22); g.closePath(); g.fill();
  }
  W._stars = { key, c };
  return c;
}
function moonSprite(W, r) {
  r = Math.max(6, Math.round(r));
  if (W._moon && W._moon.r === r) return W._moon.c;
  const c = makeCanvas(r * 2 + 4, r * 2 + 4), g = c.getContext('2d'), cx = r + 2, cy = r + 2;
  const gr = g.createRadialGradient(cx - r * 0.3, cy - r * 0.3, r * 0.1, cx, cy, r);
  gr.addColorStop(0, '#fffbea'); gr.addColorStop(1, '#d9dcef');
  g.fillStyle = gr; g.beginPath(); g.arc(cx, cy, r, 0, TAU); g.fill();
  g.fillStyle = 'rgba(150,156,190,0.35)';
  for (let i = 0; i < 6; i++) { g.beginPath(); g.arc(cx + (rand(i * 3.3) - 0.5) * r, cy + (rand(i * 7.1) - 0.5) * r, r * (0.08 + 0.12 * rand(i)), 0, TAU); g.fill(); }
  g.globalCompositeOperation = 'destination-out';
  g.beginPath(); g.arc(cx + r * 0.55, cy - r * 0.18, r * 0.92, 0, TAU); g.fill();
  g.globalCompositeOperation = 'source-over';
  W._moon = { r, c };
  return c;
}
// Art Deco poster clouds: lobes resting on a flat capsule base; silhouette outline (no inner arcs), a highlight cap on every lobe,
// one flat shadow band along the bottom and a thin streamline stripe.
function cloudLobes(w, h, seed) {
  const n = 5 + Math.floor(rand(seed) * 3), L = [];
  for (let i = 0; i < n; i++) {
    const u = (i + 0.5) / n, prof = Math.pow(Math.sin(Math.PI * u), 0.8);
    const r = h * (0.26 + 0.46 * prof) * (0.86 + 0.28 * rand(seed + i * 1.7));
    L.push(w * (0.1 + 0.8 * u) + (rand(seed + i * 2.9) - 0.5) * w * 0.04, h - r * 0.86, r);
  }
  return L;
}
function cloudPath(g, x, y, w, h, L, grow) {
  g.beginPath();
  for (let i = 0; i < L.length; i += 3) { const cx = x + L[i], cy = y + L[i + 1], r = L[i + 2] + grow; g.moveTo(cx + r, cy); g.arc(cx, cy, r, 0, TAU); }
  const bx = x + w * 0.03 - grow, by = y + h * 0.6 - grow, bw = w * 0.94 + grow * 2, bh = h * 0.4 + grow * 2, rr = Math.min(bh / 2, h * 0.2 + grow);
  g.moveTo(bx + rr, by); g.arcTo(bx + bw, by, bx + bw, by + bh, rr); g.arcTo(bx + bw, by + bh, bx, by + bh, rr); g.arcTo(bx, by + bh, bx, by, rr); g.arcTo(bx, by, bx + bw, by, rr); g.closePath();
}
function cloudSprites(W, w, h, base, hi, sh, line) {
  const key = w + 'x' + h + '|' + qkey(base) + '|' + qkey(hi) + '|' + qkey(sh);
  if (W._clouds && W._clouds.key === key) return W._clouds.list;
  const list = [], lw = Math.max(1.2, h / 520);
  for (let i = 0; i < 5; i++) {
    const cw = Math.round(w * (0.1 + 0.12 * rand(i * 4.1 + 0.5))), ch = Math.round(cw * (0.3 + 0.08 * rand(i * 2.2 + 0.3)));
    const pad = Math.ceil(lw * 2 + 2), c = makeCanvas(cw + pad * 2, ch + pad * 2), g = c.getContext('2d'), seed = i * 13.7 + 2;
    const L = cloudLobes(cw, ch, seed);
    cloudPath(g, pad, pad, cw, ch, L, lw); g.fillStyle = css(line, 0.5); g.fill();          // silhouette outline
    cloudPath(g, pad, pad, cw, ch, L, 0); g.fillStyle = css(base); g.fill();
    g.save(); cloudPath(g, pad, pad, cw, ch, L, 0); g.clip();
    g.fillStyle = css(hi);
    for (let k = 0; k < L.length; k += 3) { const r = L[k + 2]; g.beginPath(); g.arc(pad + L[k] - r * 0.2, pad + L[k + 1] - r * 0.22, r * 0.72, 0, TAU); g.fill(); }
    const sgr = g.createLinearGradient(0, pad + ch * 0.7, 0, pad + ch);
    sgr.addColorStop(0, css(sh, 0)); sgr.addColorStop(0.35, css(sh, 0.9)); sgr.addColorStop(1, css(sh, 1));
    g.fillStyle = sgr; g.fillRect(pad, pad + ch * 0.7, cw, ch * 0.32);
    g.fillStyle = css(sh, 0.45); g.fillRect(pad + cw * 0.1, pad + ch * 0.62, cw * 0.8, Math.max(1, ch * 0.025));
    g.restore();
    list.push(c);
  }
  W._clouds = { key, list };
  return list;
}
function cloudColors(C) {
  const top = C.stops[0], mid = C.stops[1], low = C.stops[2], hor = C.stops[3];
  switch (C.kind) {
    case 'storm': return [RGB('#231d31'), RGB('#4b3b70'), RGB('#0c0a12'), RGB('#000000')];
    case 'dead': return [mixc(RGB('#cbb48e'), low, 0.4), RGB('#ddcca6'), RGB('#9a8460'), RGB('#6a573c')];
    case 'night': return [RGB('#1f2749'), RGB('#47568c'), RGB('#0e1428'), RGB('#05060f')];
    case 'golden': return [RGB('#ffbf7a'), RGB('#ffe9bd'), RGB('#c0503c'), RGB('#5a2026')];
    case 'active': return [mixc(RGB('#ffe1c0'), hor, 0.3), RGB('#fff8e6'), mixc(RGB('#d44f7a'), top, 0.2), RGB('#4a1f3a')];
    default: return [mixc(C_WHITE, hor, 0.18), RGB('#ffffff'), mixc(mixc(C_WHITE, mid, 0.45), top, 0.15), shadec(mid, -0.5)];
  }
}

function skyDraw(W, ctx, w, h, E, t) {
  const tA = W._animT(E, t);
  const hy = skyHorizon(W, h);
  const C = skyCurrent(W, skyTarget(W, E), t);
  const S = h / 9.5;   // ~ px per unit
  // 1. gradient
  const g = ctx.createLinearGradient(0, 0, 0, hy);
  g.addColorStop(0, css(C.stops[0])); g.addColorStop(0.42, css(C.stops[1])); g.addColorStop(0.78, css(C.stops[2])); g.addColorStop(1, css(C.stops[3]));
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, hy + 1);
  ctx.fillStyle = css(C.stops[3]); ctx.fillRect(0, hy, w, h - hy);
  // 2. stars
  if (C.stars > 0.02) {
    ctx.save(); ctx.globalAlpha = C.stars; ctx.drawImage(starField(W, w, hy), 0, 0);
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 18; i++) {      // twinklers
      const a = 0.5 + 0.5 * Math.sin(tA * (1.3 + rand(i) * 2.2) + i * 7.1);
      const x = rand(i * 17.3 + 9) * w, y = rand(i * 8.9 + 1) * hy * 0.75, r = 1.2 + 1.8 * rand(i * 3.3);
      ctx.fillStyle = `rgba(255,248,225,${(a * C.stars * 0.9).toFixed(3)})`;
      ctx.fillRect(x - r * 2.2, y - 0.5, r * 4.4, 1); ctx.fillRect(x - 0.5, y - r * 2.2, 1, r * 4.4);
    }
    ctx.restore();
  }
  // 3. sun: deco sunburst rays, glow, disc, rings, horizon slits
  const sunX = C.sunX * w, sunY = hy - C.sunE * hy * 0.92, sunR = 0.052 * h * C.sunR;
  if (C.sunVis > 0.01) {
    ctx.save();
    if (C.rays > 0.02) {
      const R = Math.max(w, hy) * 1.25, n = 18, rot = tA * 0.012;
      const rg = ctx.createRadialGradient(sunX, sunY, sunR, sunX, sunY, R);
      rg.addColorStop(0, css(shadec(C.sunCol, 0.3), 0.30 * C.rays)); rg.addColorStop(0.35, css(C.sunCol, 0.12 * C.rays)); rg.addColorStop(1, css(C.sunCol, 0));
      ctx.fillStyle = rg; ctx.globalCompositeOperation = 'lighter';
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const a = rot + (i / n) * TAU, half = (i % 2 ? 0.035 : 0.075), L = i % 2 ? R * 0.7 : R;
        ctx.moveTo(sunX, sunY); ctx.lineTo(sunX + Math.cos(a - half) * L, sunY + Math.sin(a - half) * L);
        ctx.lineTo(sunX + Math.cos(a + half) * L, sunY + Math.sin(a + half) * L); ctx.closePath();
      }
      ctx.fill();
    }
    ctx.globalCompositeOperation = 'lighter';
    const gl = ctx.createRadialGradient(sunX, sunY, sunR * 0.6, sunX, sunY, sunR * (C.kind === 'active' ? 7 : 5));
    gl.addColorStop(0, css(C.sunCol, (C.kind === 'active' ? 0.55 : 0.4) * C.sunVis)); gl.addColorStop(1, css(C.sunCol, 0));
    ctx.fillStyle = gl; ctx.beginPath(); ctx.arc(sunX, sunY, sunR * 7, 0, TAU); ctx.fill();
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = C.kind === 'dead' ? 0.55 * C.sunVis : C.sunVis;
    const dg = ctx.createRadialGradient(sunX - sunR * 0.3, sunY - sunR * 0.3, sunR * 0.1, sunX, sunY, sunR);
    dg.addColorStop(0, '#fffbe8'); dg.addColorStop(0.55, css(shadec(C.sunCol, 0.35))); dg.addColorStop(1, css(C.sunCol));
    ctx.fillStyle = dg; ctx.beginPath(); ctx.arc(sunX, sunY, sunR, 0, TAU); ctx.fill();
    if (C.kind !== 'dead' && C.kind !== 'storm') {
      ctx.strokeStyle = css(shadec(C.sunCol, 0.2), 0.7); ctx.lineWidth = Math.max(1.5, S * 0.03);
      ctx.beginPath(); ctx.arc(sunX, sunY, sunR * 1.2, 0, TAU); ctx.stroke();
      ctx.strokeStyle = css(C.sunCol, 0.35); ctx.lineWidth = Math.max(1, S * 0.015);
      ctx.beginPath(); ctx.arc(sunX, sunY, sunR * 1.42, 0, TAU); ctx.stroke();
      if (C.sunE < 0.32) {     // the deco sunset: horizontal slits through the lower half of a low sun
        ctx.save(); ctx.beginPath(); ctx.arc(sunX, sunY, sunR + 1, 0, TAU); ctx.clip();
        const band = css(mixc(C.stops[2], C.stops[3], 0.5));
        ctx.fillStyle = band; ctx.globalAlpha = smooth01(0.32, 0.18, C.sunE) * 0.9;
        for (let i = 0; i < 5; i++) {
          const yy = sunY + sunR * (0.12 + i * 0.19), th = sunR * (0.025 + i * 0.022);
          ctx.fillRect(sunX - sunR - 2, yy, sunR * 2 + 4, th);
        }
        ctx.restore();
      }
    }
    ctx.restore();
  }
  // 4. moon
  if (C.moonVis > 0.02) {
    const mr = 0.034 * h, mx = C.moonX * w, my = hy - C.moonE * hy * 0.92;
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    const mg = ctx.createRadialGradient(mx, my, mr * 0.5, mx, my, mr * 5);
    mg.addColorStop(0, `rgba(190,205,255,${(0.28 * C.moonVis).toFixed(3)})`); mg.addColorStop(1, 'rgba(190,205,255,0)');
    ctx.fillStyle = mg; ctx.beginPath(); ctx.arc(mx, my, mr * 5, 0, TAU); ctx.fill();
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = C.moonVis;
    const ms = moonSprite(W, mr); ctx.drawImage(ms, mx - ms.width / 2, my - ms.height / 2);
    ctx.restore();
  }
  // 5. horizon haze
  const hz = ctx.createLinearGradient(0, hy - 0.2 * h, 0, hy);
  const hzc = C.kind === 'storm' ? C_STORMPURPLE : mixc(C.stops[3], C_WHITE, C.kind === 'night' ? 0.05 : 0.25);
  hz.addColorStop(0, css(hzc, 0)); hz.addColorStop(1, css(hzc, C.kind === 'night' ? 0.25 : 0.5));
  ctx.fillStyle = hz; ctx.fillRect(0, hy - 0.2 * h, w, 0.2 * h + 1);
  // 6. clouds (deco poster clouds drifting with the daily-trend wind)
  const cc = cloudColors(C);
  const sprites = cloudSprites(W, w, h, cc[0], cc[1], cc[2], cc[3]);
  const kind = C.kind;
  const count = kind === 'storm' ? 15 : kind === 'active' ? 8 : kind === 'dead' ? 4 : kind === 'golden' ? 6 : kind === 'night' ? 5 : 5;
  const windDir = (E.season < -0.05 ? -1 : 1) * (E.mirror ? -1 : 1);
  const spd = (kind === 'storm' ? 34 : 8 + 22 * E.vol) * (w / 1600);
  ctx.save();
  for (let i = 0; i < count; i++) {
    const sp = sprites[i % sprites.length];
    const sc = kind === 'storm' ? 1.5 + 0.8 * rand(i * 5.3) : 0.7 + 0.5 * rand(i * 7.7);
    const cw = sp.width * sc, ch = sp.height * sc;
    const span = w + cw;
    const yy = kind === 'storm' ? hy * (-0.05 + 0.45 * rand(i * 3.1)) : hy * (0.05 + 0.36 * rand(i * 3.1 + 0.7));
    const xx = wrap(rand(i * 5.7 + 0.3) * span + windDir * spd * (0.6 + 0.8 * rand(i * 2.3)) * tA, span) - cw;
    ctx.globalAlpha = kind === 'dead' ? 0.55 : kind === 'storm' ? 0.96 : 0.92;
    ctx.drawImage(sp, xx, yy, cw, ch);
  }
  ctx.restore();
  // 7. storm: distant lightning flickering inside the clouds (stateless, by time buckets)
  if (kind === 'storm') {
    const per = 0.75, b = Math.floor(tA / per), ph = tA / per - b;
    if (rand(b * 3.17 + 11) < 0.25 + 0.4 * E.vol && ph < 0.24) {
      const inten = ph < 0.05 ? 1 : ph < 0.09 ? 0.25 : ph < 0.15 ? 0.85 : 0.3;
      const fx = rand(b * 7.3 + 1) * w, fy = hy * (0.12 + 0.35 * rand(b * 1.9 + 2));
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      const fg = ctx.createRadialGradient(fx, fy, 0, fx, fy, 0.3 * h);
      fg.addColorStop(0, `rgba(200,140,255,${(0.42 * inten).toFixed(3)})`); fg.addColorStop(1, 'rgba(120,60,200,0)');
      ctx.fillStyle = fg; ctx.fillRect(fx - 0.3 * h, fy - 0.3 * h, 0.6 * h, 0.6 * h);
      if (rand(b * 5.5 + 3) < 0.6) {       // a thin distant bolt from cloud to the horizon
        ctx.strokeStyle = `rgba(217,166,255,${(0.75 * inten).toFixed(3)})`; ctx.lineWidth = Math.max(1, S * 0.02);
        ctx.beginPath(); let x = fx, y = fy; ctx.moveTo(x, y);
        const steps = 9, dy = (hy - fy) / steps;
        for (let i = 1; i <= steps; i++) { x += (rand(b * 13 + i * 2.7) - 0.5) * 0.05 * h; y += dy; ctx.lineTo(x, y); }
        ctx.stroke();
        ctx.strokeStyle = `rgba(180,77,255,${(0.25 * inten).toFixed(3)})`; ctx.lineWidth = Math.max(3, S * 0.08); ctx.stroke();
      }
      ctx.restore();
    }
  }
  // 8. dead market: flat heavy sepia fog lying over the lower sky
  if (kind === 'dead') {
    ctx.save();
    for (let i = 0; i < 4; i++) {
      const yb = hy - (0.06 + i * 0.075) * h + Math.sin(tA * 0.15 + i * 1.7) * 0.006 * h, th = 0.09 * h;
      const fg = ctx.createLinearGradient(0, yb - th, 0, yb + th);
      fg.addColorStop(0, 'rgba(196,173,134,0)'); fg.addColorStop(0.5, `rgba(205,184,146,${(0.42 - i * 0.07).toFixed(3)})`); fg.addColorStop(1, 'rgba(196,173,134,0)');
      ctx.fillStyle = fg; ctx.fillRect(0, yb - th, w, th * 2);
    }
    ctx.restore();
  }
}

// ============================================================================================================ SKYLINE
// Two tileable layers (far: hazy, low contrast; near: darker, gold deco trims, lit windows) cached per lighting bucket and cross-faded
// when the bucket changes. Animated on top: rotating roof gears, the distant clock (real UTC from day_frac), chimney steam, beacons.
const SKY_TYPES_FAR = [['glass', 28], ['setback', 24], ['slab', 22], ['mast', 14], ['chrysler', 12]];     // Manhattan only (Zee 2026-11-04)
const SKY_TYPES_NEAR = [['glass', 28], ['slab', 24], ['setback', 20], ['mast', 14], ['chrysler', 14]];
function pickType(list, r) {
  let tot = 0; for (const e of list) tot += e[1];
  let a = r * tot; for (const e of list) { if ((a -= e[1]) < 0) return e[0]; }
  return list[0][0];
}
function genLayer(layer, T, S, hy, w) {
  const far = layer === 'far', seed = far ? 101 : 707, out = [];
  let x = -S * 0.2, i = 0;
  while (x < T) {
    const r1 = rand(seed + i * 7.31), r2 = rand(seed + i * 3.17 + 0.5), r3 = rand(seed + i * 5.71 + 0.25);
    const type = pickType(far ? SKY_TYPES_FAR : SKY_TYPES_NEAR, r1);
    let bw = S * (far ? lerp(0.45, 1.2, r2) : lerp(0.6, 1.6, r2));
    let bh = S * (far ? lerp(2.2, 4.6, Math.pow(r3, 0.8)) : lerp(1.2, 3.0, r3));                  // high-rise: taller and denser
    if (type === 'factory') { bw *= 1.5; bh *= far ? 0.42 : 0.5; }
    if (type === 'mast') { bw *= 0.75; bh *= 1.12; }
    if (type === 'glass') { bw *= 0.85; bh *= 1.1; }
    if (type === 'tank') { bw *= 0.8; bh *= 0.75; }
    if (type === 'billboard') { bw *= 1.3; bh *= 0.6; }
    if (type === 'dome') { bh *= 0.75; }
    out.push({ type, x, w: bw, top: hy - bh, base: hy, seed: seed + i * 11.3 });
    x += bw + S * (far ? rand(seed + i * 9.9) * 0.14 : rand(seed + i * 9.9) * 0.3 - 0.06);
    i++;
  }
  if (far) {   // the Empire State-style tower with its antenna at ~0.46 of the screen (it replaced the London-looking clock tower)
    const cx = 0.46 * w, cw = S * 0.9;
    for (let k = out.length - 1; k >= 0; k--) { const b = out[k]; if (b.x < cx + cw * 0.9 && b.x + b.w > cx - cw * 0.9) out.splice(k, 1); }
    out.push({ type: 'mast', x: cx - cw / 2, w: cw, top: hy - S * 5.2, base: hy, seed: 4242 });
  }
  return out;
}
function skylineGeom(W, w, h, hy) {
  const key = w + 'x' + h + 'x' + Math.round(hy);
  if (W._sl && W._sl.key === key) return W._sl;
  const S = h / 9.5, T = Math.round(Math.max(w, 900) * 1.6);
  W._sl = { key, S, T, hy, w, h, far: genLayer('far', T, S, hy, w), near: genLayer('near', T, S, hy, w), lit: null, prev: null };
  return W._sl;
}
function skylineColors(W, E) {
  const T = W._skyT || skyTarget(W, E), st = T.stops, k = T.kind;
  let far, nearInk, trimMix, lit;
  if (k === 'night') { far = mixc(st[2], C_BLACK, 0.3); nearInk = RGB('#070a18'); trimMix = 0.62; lit = 0.5; }
  else if (k === 'storm') { far = mixc(st[2], C_BLACK, 0.25); nearInk = RGB('#040308'); trimMix = 0.7; lit = 0.28; }
  else if (k === 'dead') { far = shadec(mixc(st[2], st[1], 0.5), -0.14); nearInk = RGB('#4a3a28'); trimMix = 0.55; lit = 0.05; }
  else if (k === 'golden') { far = shadec(mixc(st[2], st[1], 0.55), -0.3); nearInk = RGB('#2a1424'); trimMix = 0.3; lit = 0.3; }
  else if (k === 'active') { far = shadec(mixc(st[2], st[1], 0.45), -0.26); nearInk = RGB('#22142e'); trimMix = 0.3; lit = 0.12; }
  else { far = satc(shadec(mixc(st[3], st[1], 0.5), -0.2), 0.75); nearInk = RGB('#1c2336'); trimMix = 0.35; lit = 0.05; }
  lit = clamp(lit + T.nightness * 0.35, 0, 0.6);
  if (E.lampOnly) lit = 0;                  // REQUIREMENTS 4: after ten minutes the Buyer's lamp is the only light
  const near = mixc(far, nearInk, k === 'dead' ? 0.4 : 0.55);
  const trim = mixc(RGB(k === 'dead' ? P.brass : P.gold), near, trimMix);
  const glass = mixc(near, st[1], k === 'night' || k === 'storm' ? 0.12 : 0.4);
  const rim = mixc(st[3], C_WHITE, 0.2);
  const steam = k === 'night' ? RGB('#56608a') : k === 'storm' ? RGB('#2c2640') : k === 'dead' ? RGB('#bba680') : mixc(C_WHITE, st[3], 0.3);
  const key = k + '|' + qkey(far, 10) + '|' + qkey(near, 10) + '|' + Math.round(lit * 10);
  return { key, kind: k, far, near, trim, glass, rim, steam, lit, litCol: RGB('#ffcf6a'), night: k === 'night' || k === 'storm' };
}
function bands(g, x, y, w, h, base, hi, sh) {
  g.fillStyle = css(base); g.fillRect(x, y, w, h);
  g.fillStyle = css(hi); g.fillRect(x, y, w * 0.2, h);
  g.fillStyle = css(sh); g.fillRect(x + w * 0.74, y, w * 0.26, h);
}
const NEON_WIN = [RGB('#7ff3ff'), RGB('#ff7ad9'), RGB('#ffd36a'), RGB('#b48cff'), RGB('#7ff3ff')];
const NEON_RIM = [RGB('#ff4fa3'), RGB('#3fe0ff'), RGB('#ff9a3c'), RGB('#a66bff'), RGB('#ff5468'), RGB('#3fe0ff')];
function neonLine(g, x, y0, y1, c3, k, S, far) {          // a neon tube with its glow (drawn into the cached layer)
  if (y1 <= y0) return;
  const op = g.globalCompositeOperation; g.globalCompositeOperation = 'lighter';
  const gw = S * (far ? 0.16 : 0.28);
  const gr = g.createLinearGradient(x - gw, 0, x + gw, 0); gr.addColorStop(0, css(c3, 0)); gr.addColorStop(0.5, css(c3, 0.6 * Math.min(1, k))); gr.addColorStop(1, css(c3, 0));
  g.fillStyle = gr; g.fillRect(x - gw, y0, gw * 2, y1 - y0);
  g.fillStyle = css(mixc(c3, C_WHITE, 0.4), Math.min(1, 1.1 * k)); g.fillRect(x - Math.max(1.5, S * 0.02), y0, Math.max(3, S * 0.04), y1 - y0);
  g.globalCompositeOperation = op;
}
function windows(g, x, y, w, h, S, far, col, seed) {
  if (w < 4 || h < 4) return;
  const cw = S * (far ? 0.075 : 0.105), rh = S * (far ? 0.11 : 0.15), ww = S * (far ? 0.03 : 0.045), wh = S * (far ? 0.05 : 0.075);
  const cols = Math.max(1, Math.floor((w - S * 0.06) / cw)), rows = Math.max(1, Math.floor((h - S * 0.1) / rh));
  const x0 = x + (w - cols * cw) / 2 + (cw - ww) / 2;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const rv = rand(seed + r * 13.1 + c * 3.7), lit = rv < col.lit + 0.08;
      if (lit) g.fillStyle = css(NEON_WIN[Math.floor(rand(seed * 0.7 + r * 5.3 + c * 9.1) * NEON_WIN.length)], far ? 0.75 : 0.95);
      else if (far) continue;
      else g.fillStyle = css(col.glass, 0.85);
      g.fillRect(x0 + c * cw, y + S * 0.08 + r * rh, ww, wh);
    }
  }
}
const ACCENTS = { brick: RGB('#9a4a3a'), stone: RGB('#d6c7a1'), steel: RGB('#8fa3b8'), copper: RGB('#b06a3a'), slate: RGB('#4a5874'), verdigris: RGB('#4f9a86') };
const TYPE_ACCENT = { factory: ['brick', 'brick', 'copper'], dome: ['stone', 'stone', 'slate'], tank: ['copper', 'brick', 'slate'], billboard: ['slate'],
  setback: ['stone', 'slate', 'brick', 'steel'], slab: ['steel', 'slate', 'steel', 'stone'], chrysler: ['steel', 'steel', 'stone'], mast: ['steel', 'stone'], glass: ['steel', 'slate'], gear: ['brick', 'slate', 'copper'], clock: ['stone'] };
function drawBuilding(g, b, col, far, ox, oy, S, anim) {
  const acc = TYPE_ACCENT[b.type] || ['slate'], accName = acc[Math.floor(rand(b.seed * 1.91) * acc.length) % acc.length];
  const accK = (far ? 0.1 : 0.26) * (col.kind === 'night' || col.kind === 'storm' ? 0.35 : col.kind === 'dead' ? 0.3 : 1);
  const base = mixc(mixc(far ? col.far : col.near, ACCENTS[accName], accK), RGB(rand(b.seed * 2.3) < 0.5 ? '#1e2457' : '#33215a'), far ? 0.3 : 0.5), hi = shadec(base, far ? 0.07 : 0.12), sh = shadec(base, far ? -0.07 : -0.22);
  const verd = mixc(base, ACCENTS.verdigris, far ? 0.15 : 0.5 * (accK / 0.26));
  const trim = far ? shadec(base, 0.12) : col.trim, line = shadec(base, -0.5);
  const X = b.x + ox, top = b.top - oy, bot = b.base - oy + S * 4, w = b.w, r = (k) => rand(b.seed + k * 1.37);
  g.lineWidth = Math.max(1, S * 0.012); g.strokeStyle = css(line, far ? 0 : 0.6);
  const outline = (x, y, ww, hh) => { if (!far) g.strokeRect(x + 0.5, y + 0.5, ww - 1, hh - 1); };
  const rim = (x, y, ww) => { g.fillStyle = css(col.rim, col.night ? 0.12 : 0.45); g.fillRect(x, y, ww, Math.max(1, S * 0.018)); };
  switch (b.type) {
    case 'setback': case 'mast': {
      const n = b.type === 'mast' ? 3 : 2 + Math.floor(r(1) * 3), fr = [0.56, 0.24, 0.12, 0.08];
      let tot = 0; for (let i = 0; i < n; i++) tot += fr[i];
      let y = b.base - oy, ww = w, xx = X;
      const Ht = b.base - b.top;
      for (let i = 0; i < n; i++) {
        const th = Ht * fr[i] / tot, ty = y - th;
        bands(g, xx, ty, ww, (i === 0 ? bot - ty : th + 1), base, hi, sh);
        if (i === 0) windows(g, xx, ty, ww, th, S, far, col, b.seed + i);
        else windows(g, xx, ty, ww, th, S, far, col, b.seed + i * 3);
        g.fillStyle = css(sh, 0.6);
        for (let px = xx + S * 0.12; px < xx + ww - S * 0.05; px += S * 0.14) g.fillRect(px, ty + S * 0.04, Math.max(1, S * 0.012), th - S * 0.04);
        g.fillStyle = css(trim); g.fillRect(xx - S * 0.02, ty, ww + S * 0.04, Math.max(1.5, S * 0.03));
        rim(xx, ty, ww); outline(xx, ty, ww, i === 0 ? bot - ty : th);
        y = ty; const nw = ww * (0.74 - r(i + 3) * 0.08); xx += (ww - nw) / 2; ww = nw;
      }
      const cx = xx + ww / 2;
      if (b.type === 'mast') {
        bands(g, cx - ww * 0.3, y - S * 0.22, ww * 0.6, S * 0.22, base, hi, sh);
        g.fillStyle = css(trim); g.fillRect(cx - ww * 0.36, y - S * 0.25, ww * 0.72, S * 0.04);
        g.fillStyle = css(base); g.beginPath(); g.moveTo(cx - S * 0.025, y - S * 0.24); g.lineTo(cx, y - S * 1.05); g.lineTo(cx + S * 0.025, y - S * 0.24); g.fill();
        anim.lights.push({ x: b.x + (cx - X), y: y + oy - S * 1.05 });
      } else if (r(9) < 0.55) {
        g.fillStyle = css(base); g.beginPath(); g.moveTo(cx - ww * 0.12, y); g.lineTo(cx, y - S * (0.35 + r(10) * 0.4)); g.lineTo(cx + ww * 0.12, y); g.fill();
        if (!far) { g.strokeStyle = css(col.trim, 0.8); g.beginPath(); g.moveTo(cx, y); g.lineTo(cx, y - S * (0.35 + r(10) * 0.4)); g.stroke(); }
      } else {
        for (let s = 0; s < 3; s++) { const sw = ww * (0.8 - s * 0.25), sh2 = S * 0.07; bands(g, cx - sw / 2, y - sh2 * (s + 1), sw, sh2 + 1, base, hi, sh); }
      }
      break;
    }
    case 'glass': {                       // a modern glass supertall (One World Trade Center style): tapering blue glass, a spire
      const Ht = b.base - b.top, cx = X + w / 2, tw = w * 0.5, sh0 = top + Ht * 0.1;
      const tint = mixc(base, RGB('#6fa3cf'), far ? 0.22 : 0.42);
      g.fillStyle = css(tint);
      g.beginPath(); g.moveTo(X, bot); g.lineTo(X, sh0); g.lineTo(cx - tw / 2, top); g.lineTo(cx + tw / 2, top); g.lineTo(X + w, sh0); g.lineTo(X + w, bot); g.closePath(); g.fill();
      if (!far) { g.strokeStyle = css(line, 0.6); g.stroke(); }
      g.fillStyle = css(shadec(tint, -0.2), 0.9);                                  // the shaded facet
      g.beginPath(); g.moveTo(cx, top); g.lineTo(cx + tw / 2, top); g.lineTo(X + w, sh0); g.lineTo(X + w, bot); g.lineTo(cx, bot); g.closePath(); g.fill();
      g.fillStyle = css(C_WHITE, far ? 0.07 : 0.14);                               // a sky reflection running up the glass
      g.beginPath(); g.moveTo(X + w * 0.12, bot); g.lineTo(X + w * 0.12, sh0 + Ht * 0.04); g.lineTo(X + w * 0.28, sh0); g.lineTo(X + w * 0.28, bot); g.closePath(); g.fill();
      g.fillStyle = css(shadec(tint, -0.35), far ? 0.18 : 0.3);                    // floor lines
      for (let yy = sh0 + S * 0.05; yy < bot; yy += S * (far ? 0.07 : 0.09)) g.fillRect(X, yy, w, Math.max(1, S * 0.007));
      if (col.lit > 0.12) windows(g, X, sh0, w, b.base - oy - sh0, S, far, col, b.seed);
      g.fillStyle = css(shadec(tint, 0.25)); g.fillRect(cx - S * 0.013, top - S * 0.7, S * 0.026, S * 0.7);   // the antenna
      anim.lights.push({ x: b.x + w / 2, y: b.top - S * 0.7 });
      break;
    }
    case 'slab': {
      bands(g, X, top, w, bot - top, base, hi, sh);
      windows(g, X, top + S * 0.1, w, b.base - b.top - S * 0.1, S, far, col, b.seed);
      g.fillStyle = css(sh, 0.55);
      for (let px = X + S * 0.1; px < X + w - S * 0.04; px += S * 0.16) g.fillRect(px, top + S * 0.12, Math.max(1, S * 0.016), bot - top);
      for (let s = 0; s < 3; s++) { const sw = w * (0.7 - s * 0.2); bands(g, X + (w - sw) / 2, top - S * 0.06 * (s + 1), sw, S * 0.06 + 1, base, hi, sh); }
      g.fillStyle = css(trim); g.fillRect(X, top + S * 0.06, w, Math.max(1.5, S * 0.025));
      rim(X, top, w); outline(X, top, w, bot - top);
      break;
    }
    case 'chrysler': {
      const crownH = Math.min(S * 0.9, (b.base - b.top) * 0.4), sy = top + crownH;
      bands(g, X, sy, w, bot - sy, base, hi, sh);
      windows(g, X, sy, w, b.base - oy - sy, S, far, col, b.seed);
      outline(X, sy, w, bot - sy);
      const cx = X + w / 2;
      for (let a = 0; a < 4; a++) {         // stacked deco arches with sunburst windows
        const aw = w * (0.92 - a * 0.2), ay = sy - a * crownH * 0.24;
        g.fillStyle = css(a % 2 ? hi : base);
        g.beginPath(); g.moveTo(cx - aw / 2, ay); g.arc(cx, ay, aw / 2, Math.PI, 0); g.closePath(); g.fill();
        if (!far) {
          g.strokeStyle = css(col.trim, 0.95); g.lineWidth = Math.max(1, S * 0.022);
          g.beginPath(); g.arc(cx, ay, aw / 2, Math.PI, 0); g.stroke();
          g.fillStyle = css(col.night ? col.litCol : col.glass, 0.9);
          for (let k = 0; k < 5; k++) {
            const an = Math.PI + (k + 0.5) / 5 * Math.PI, rr = aw * 0.42;
            const tx = cx + Math.cos(an) * rr, ty = ay + Math.sin(an) * rr;
            g.beginPath(); g.moveTo(tx, ty); g.lineTo(cx + Math.cos(an - 0.09) * rr * 0.72, ay + Math.sin(an - 0.09) * rr * 0.72);
            g.lineTo(cx + Math.cos(an + 0.09) * rr * 0.72, ay + Math.sin(an + 0.09) * rr * 0.72); g.fill();
          }
        }
      }
      g.fillStyle = css(far ? base : col.trim);
      g.beginPath(); g.moveTo(cx - S * 0.02, sy - crownH * 0.85); g.lineTo(cx, sy - crownH * 0.85 - S * 0.55); g.lineTo(cx + S * 0.02, sy - crownH * 0.85); g.fill();
      anim.lights.push({ x: b.x + w / 2, y: b.top + crownH * 0.15 - S * 0.55 });
      break;
    }
    case 'dome': {
      const bh = (b.base - b.top) * 0.55, by = b.base - oy - bh;
      bands(g, X, by, w, bot - by, base, hi, sh);
      g.fillStyle = css(far ? hi : shadec(base, 0.2), far ? 0.5 : 0.7);
      for (let px = X + S * 0.08; px < X + w - S * 0.06; px += S * 0.13) g.fillRect(px, by + S * 0.12, Math.max(1.5, S * 0.03), bh - S * 0.16);
      g.fillStyle = css(trim); g.fillRect(X - S * 0.03, by, w + S * 0.06, Math.max(2, S * 0.04));
      g.fillStyle = css(base); g.beginPath(); g.moveTo(X + w * 0.1, by); g.lineTo(X + w / 2, by - S * 0.18); g.lineTo(X + w * 0.9, by); g.fill();   // pediment
      const dw = w * 0.62, dy = by - S * 0.18, cx = X + w / 2;
      bands(g, cx - dw * 0.42, dy - S * 0.18, dw * 0.84, S * 0.19, base, hi, sh);
      g.fillStyle = css(shadec(verd, 0.12)); g.beginPath(); g.ellipse(cx, dy - S * 0.18, dw / 2, dw * 0.48, 0, Math.PI, 0); g.fill();
      g.fillStyle = css(sh, 0.8); g.beginPath(); g.ellipse(cx + dw * 0.12, dy - S * 0.18, dw * 0.38, dw * 0.44, 0, Math.PI * 1.5, 0); g.lineTo(cx + dw * 0.12, dy - S * 0.18); g.fill();
      if (!far) { g.strokeStyle = css(col.trim, 0.8); g.lineWidth = Math.max(1, S * 0.015); for (let k = -1; k <= 1; k++) { g.beginPath(); g.ellipse(cx, dy - S * 0.18, Math.abs(k) * dw * 0.28 + 0.5, dw * 0.48, 0, Math.PI, 0); g.stroke(); } }
      g.fillStyle = css(far ? base : col.trim); g.fillRect(cx - S * 0.04, dy - S * 0.18 - dw * 0.48 - S * 0.12, S * 0.08, S * 0.13);
      g.fillRect(cx - S * 0.008, dy - S * 0.18 - dw * 0.48 - S * 0.42, Math.max(1, S * 0.016), S * 0.32);
      outline(X, by, w, bot - by);
      break;
    }
    case 'gear': {
      bands(g, X, top, w, bot - top, base, hi, sh);
      windows(g, X, top + S * 0.05, w, b.base - b.top, S, far, col, b.seed);
      g.fillStyle = css(trim); g.fillRect(X - S * 0.02, top, w + S * 0.04, Math.max(2, S * 0.035));
      outline(X, top, w, bot - top);
      const gr = Math.min(w * 0.42, S * 0.55);
      g.fillStyle = css(sh); g.beginPath(); g.moveTo(X + w / 2 - gr * 0.35, top); g.lineTo(X + w / 2, top - gr * 0.5); g.lineTo(X + w / 2 + gr * 0.35, top); g.fill();
      anim.gears.push({ x: b.x + w / 2, y: b.top - gr * 0.12, r: gr, roof: b.top, dir: r(4) < 0.5 ? -1 : 1, spd: 0.15 + r(5) * 0.25, teeth: 10 + Math.floor(r(6) * 6) });
      break;
    }
    case 'factory': {
      const rh = (b.base - b.top), teeth = 3 + Math.floor(r(2) * 3), tw = w / teeth;
      const nch = 1 + Math.floor(r(3) * 3);
      for (let c = 0; c < nch; c++) {      // chimneys first (behind the roof)
        const cxp = X + w * (0.15 + 0.7 * (nch === 1 ? 0.5 : c / (nch - 1))), ch = S * (0.8 + r(c + 7) * 0.8) * (far ? 0.8 : 1), cwid = S * (far ? 0.09 : 0.13);
        const cy = top - ch;
        g.fillStyle = css(base); g.beginPath(); g.moveTo(cxp - cwid * 0.6, top + 2); g.lineTo(cxp - cwid * 0.42, cy); g.lineTo(cxp + cwid * 0.42, cy); g.lineTo(cxp + cwid * 0.6, top + 2); g.fill();
        g.fillStyle = css(sh, 0.8); g.fillRect(cxp + cwid * 0.12, cy, cwid * 0.3, ch);
        g.fillStyle = css(trim); g.fillRect(cxp - cwid * 0.5, cy + S * 0.05, cwid, Math.max(1.5, S * 0.03)); g.fillRect(cxp - cwid * 0.52, cy + S * 0.14, cwid * 1.04, Math.max(1, S * 0.02));
        g.fillStyle = css(shadec(base, -0.4)); g.fillRect(cxp - cwid * 0.5, cy - S * 0.03, cwid, S * 0.04);
        anim.chimneys.push({ x: b.x + (cxp - X), y: b.top - ch - S * 0.03, r: cwid });
      }
      bands(g, X, top + rh * 0.25, w, bot - top - rh * 0.25, base, hi, sh);
      for (let k = 0; k < teeth; k++) {
        const tx = X + k * tw;
        g.fillStyle = css(k % 2 ? base : hi); g.beginPath(); g.moveTo(tx, top + rh * 0.25 + 1); g.lineTo(tx + tw * 0.15, top); g.lineTo(tx + tw, top + rh * 0.25 + 1); g.fill();
        if (!far) { g.fillStyle = css(col.night ? col.litCol : col.glass, col.night ? 0.8 : 0.7); g.beginPath(); g.moveTo(tx + tw * 0.2, top + rh * 0.24); g.lineTo(tx + tw * 0.2, top + rh * 0.06); g.lineTo(tx + tw * 0.75, top + rh * 0.24); g.fill(); }
      }
      windows(g, X, top + rh * 0.3, w, rh * 0.7, S, far, col, b.seed);
      g.fillStyle = css(trim); g.fillRect(X, top + rh * 0.25, w, Math.max(1.5, S * 0.025));
      outline(X, top + rh * 0.25, w, bot - top);
      break;
    }
    case 'tank': {
      const legH = (b.base - b.top) * 0.45, ty = b.base - oy - legH, tw = w * 0.86, tx = X + (w - tw) / 2, tH = (b.base - b.top) * 0.4;
      g.strokeStyle = css(sh); g.lineWidth = Math.max(1.5, S * 0.03);
      g.beginPath();
      for (let k = 0; k < 4; k++) { const lx = tx + tw * (0.08 + k * 0.28); g.moveTo(lx, ty); g.lineTo(lx + (k < 2 ? -1 : 1) * S * 0.05, bot); }
      g.moveTo(tx + tw * 0.08, ty + legH * 0.3); g.lineTo(tx + tw * 0.92, ty + legH * 0.7); g.moveTo(tx + tw * 0.92, ty + legH * 0.3); g.lineTo(tx + tw * 0.08, ty + legH * 0.7);
      g.stroke();
      bands(g, tx, ty - tH, tw, tH, base, hi, sh);
      g.fillStyle = css(trim); g.fillRect(tx, ty - tH * 0.55, tw, Math.max(1.5, S * 0.025)); g.fillRect(tx, ty - S * 0.03, tw, Math.max(1.5, S * 0.03));
      g.fillStyle = css(hi); g.beginPath(); g.moveTo(tx - S * 0.03, ty - tH); g.lineTo(tx + tw / 2, ty - tH - S * 0.32); g.lineTo(tx + tw + S * 0.03, ty - tH); g.fill();
      g.fillStyle = css(sh, 0.8); g.beginPath(); g.moveTo(tx + tw / 2, ty - tH - S * 0.32); g.lineTo(tx + tw + S * 0.03, ty - tH); g.lineTo(tx + tw * 0.62, ty - tH); g.fill();
      outline(tx, ty - tH, tw, tH);
      break;
    }
    case 'billboard': {
      const postH = (b.base - b.top) * 0.45, by = b.base - oy - postH, bh = (b.base - b.top) * 0.55;
      g.fillStyle = css(sh); g.fillRect(X + w * 0.2, by, S * 0.05, bot - by); g.fillRect(X + w * 0.75, by, S * 0.05, bot - by);
      g.fillStyle = css(shadec(base, -0.1)); g.fillRect(X, by - bh, w, bh);
      g.fillStyle = css(col.trim); g.fillRect(X, by - bh, w, Math.max(2, S * 0.035)); g.fillRect(X, by - S * 0.035, w, Math.max(2, S * 0.035));
      const cx = X + w / 2, cy = by - bh / 2, rr = Math.min(bh * 0.32, w * 0.18);      // a giant painted coin: the street's emblem
      g.fillStyle = css(mixc(RGB(P.gold), base, col.night ? 0.25 : 0.45)); g.beginPath(); g.arc(cx, cy, rr, 0, TAU); g.fill();
      g.strokeStyle = css(mixc(RGB(P.goldDeep), base, 0.3)); g.lineWidth = Math.max(1, S * 0.025); g.beginPath(); g.arc(cx, cy, rr * 0.75, 0, TAU); g.stroke();
      for (let k = 0; k < 2; k++) { const sx2 = cx + (k ? 1 : -1) * w * 0.33; g.fillStyle = css(col.trim, 0.8); g.beginPath(); g.moveTo(sx2, cy - rr * 0.6); g.lineTo(sx2 + rr * 0.3, cy); g.lineTo(sx2, cy + rr * 0.6); g.lineTo(sx2 - rr * 0.3, cy); g.fill(); }
      outline(X, by - bh, w, bh);
      break;
    }
    case 'clock': {
      const shaftTop = top + S * 1.15, cx = X + w / 2;
      bands(g, X + w * 0.12, shaftTop, w * 0.76, bot - shaftTop, base, hi, sh);
      g.fillStyle = css(sh, 0.6);
      for (let px = X + w * 0.24; px < X + w * 0.84; px += w * 0.16) g.fillRect(px, shaftTop + S * 0.1, Math.max(1, S * 0.015), bot - shaftTop);
      const stageY = top + S * 0.32;
      bands(g, X, stageY, w, S * 0.86, base, hi, sh);                       // clock stage
      g.fillStyle = css(trim); g.fillRect(X - S * 0.03, stageY, w + S * 0.06, S * 0.04); g.fillRect(X - S * 0.03, stageY + S * 0.82, w + S * 0.06, S * 0.04);
      const fr = Math.min(w * 0.4, S * 0.36), fy = stageY + S * 0.43;
      g.fillStyle = css(shadec(trim, -0.2)); g.beginPath(); g.arc(cx, fy, fr * 1.12, 0, TAU); g.fill();
      g.fillStyle = css(col.night ? RGB('#fff1c4') : mixc(RGB(P.paper), base, far ? 0.45 : 0.15)); g.beginPath(); g.arc(cx, fy, fr, 0, TAU); g.fill();
      g.strokeStyle = css(shadec(base, -0.3)); g.lineWidth = Math.max(1, S * 0.02);
      g.beginPath();
      for (let k = 0; k < 12; k++) { const a = k / 12 * TAU, r1 = fr * (k % 3 ? 0.84 : 0.74); g.moveTo(cx + Math.cos(a) * r1, fy + Math.sin(a) * r1); g.lineTo(cx + Math.cos(a) * fr * 0.94, fy + Math.sin(a) * fr * 0.94); }
      g.stroke();
      const roofY = stageY;                                                  // stepped belfry + spire
      for (let s = 0; s < 3; s++) { const sw = w * (0.86 - s * 0.24); bands(g, cx - sw / 2, roofY - S * 0.11 * (s + 1), sw, S * 0.11 + 1, base, hi, sh); }
      g.fillStyle = css(base); g.beginPath(); g.moveTo(cx - w * 0.16, roofY - S * 0.33); g.lineTo(cx, roofY - S * 1.05); g.lineTo(cx + w * 0.16, roofY - S * 0.33); g.fill();
      g.fillStyle = css(sh, 0.8); g.beginPath(); g.moveTo(cx, roofY - S * 1.05); g.lineTo(cx + w * 0.16, roofY - S * 0.33); g.lineTo(cx + w * 0.04, roofY - S * 0.33); g.fill();
      anim.clock = { x: b.x + w / 2, y: b.top + S * 0.75, r: fr };
      anim.lights.push({ x: b.x + w / 2, y: b.top + S * 0.32 - S * 1.05 });
      break;
    }
  }
  // ---- neon (Zee 2026-11-04 reference): a bright rim down one edge, glowing strips on some towers
  {
    const Ht = b.base - b.top, k = clamp(0.8 + col.lit, 0.8, 1.3) * (far ? 0.75 : 1);
    const y0 = top + Ht * (b.type === 'setback' || b.type === 'mast' ? 0.44 : b.type === 'glass' ? 0.1 : b.type === 'chrysler' ? 0.3 : 0.02);
    const nc = NEON_RIM[Math.floor(rand(b.seed * 3.7) * NEON_RIM.length) % NEON_RIM.length];
    neonLine(g, rand(b.seed * 4.1) < 0.5 ? X + w - 1 : X + 1, y0, bot, nc, k, S, far);
    if (rand(b.seed * 5.3) < 0.38 && w > S * 0.5) {
      const sc = NEON_RIM[Math.floor(rand(b.seed * 6.1) * NEON_RIM.length) % NEON_RIM.length];
      neonLine(g, X + w * 0.32, y0 + S * 0.25, bot, sc, k * 0.8, S * 0.8, far);
      neonLine(g, X + w * 0.66, y0 + S * 0.45, bot, sc, k * 0.8, S * 0.8, far);
    }
  }
}
function buildLayerCanvas(G, list, layer, col) {
  const far = layer === 'far', S = G.S, T = G.T;
  let minTop = G.hy; for (const b of list) minTop = Math.min(minTop, b.top);
  const oy = Math.floor(minTop - S * 1.3), hgt = Math.ceil(G.h - oy + 2);
  const c = makeCanvas(T, hgt), g = c.getContext('2d');
  const anim = { gears: [], chimneys: [], lights: [], clock: null };
  if (far) {        // a viaduct running across the distance, for the bullion train
    const ty = G.hy - S * 0.95 - oy, deck = Math.max(2, S * 0.05), vc = shadec(col.far, -0.12);
    g.fillStyle = css(vc); g.fillRect(0, ty, T, deck);
    g.fillStyle = css(shadec(col.far, -0.06));
    for (let x = 0; x < T + S; x += S * 0.42) { g.beginPath(); g.moveTo(x, ty + deck); g.lineTo(x + S * 0.42, ty + deck); g.lineTo(x + S * 0.42, G.hy - oy + S); g.arc(x + S * 0.21, ty + deck + S * 0.32, S * 0.15, 0, Math.PI, true); g.lineTo(x, G.hy - oy + S); g.closePath(); g.fill(); }
    anim.trackY = G.hy - S * 0.95;
  }
  for (const b of list) {
    drawBuilding(g, b, col, far, 0, oy, S, anim);
    if (b.x + b.w > T) drawBuilding(g, b, col, far, -T, oy, S, { gears: [], chimneys: [], lights: [], clock: null });
    if (b.x < 0) drawBuilding(g, b, col, far, T, oy, S, { gears: [], chimneys: [], lights: [], clock: null });
  }
  // gear sprite for this layer
  const gr = Math.ceil(S * 0.6), gs = makeCanvas(gr * 2 + 6, gr * 2 + 6), gg = gs.getContext('2d');
  const gbase = far ? shadec(col.far, -0.03) : mixc(col.trim, col.near, 0.35);
  gearPath(gg, gr + 3, gr + 3, gr * 0.84, 12, gr * 0.14, 0, gr * 0.2);
  gg.fillStyle = css(gbase); gg.fill('evenodd');
  if (!far) {
    gg.strokeStyle = css(shadec(gbase, -0.45)); gg.lineWidth = Math.max(1, S * 0.015); gg.stroke();
    gg.strokeStyle = css(shadec(gbase, 0.3), 0.8); gg.beginPath(); gg.arc(gr + 3, gr + 3, gr * 0.6, 0, TAU); gg.stroke();
    gg.fillStyle = css(shadec(gbase, -0.3));
    for (let k = 0; k < 5; k++) { const a = k / 5 * TAU; gg.beginPath(); gg.arc(gr + 3 + Math.cos(a) * gr * 0.42, gr + 3 + Math.sin(a) * gr * 0.42, gr * 0.12, 0, TAU); gg.fill(); }
  }
  const steam = softBlob(Math.max(4, Math.round(S * 0.22)), col.steam);
  return { c, oy, anim, gear: gs, gearR: gr, steam };
}
function skylineLit(W, G, E, t) {
  const col = skylineColors(W, E);
  if (!G.lit || G.lit.key !== col.key) {
    const tb = performance.now();
    const built = { key: col.key, col, far: buildLayerCanvas(G, G.far, 'far', col), near: buildLayerCanvas(G, G.near, 'near', col), t0: t };
    W._stats.skylineBuilds++; W._stats.lastSkylineMs = +(performance.now() - tb).toFixed(2);
    G.prev = G.lit && Number.isFinite(t) ? G.lit : null;
    G.lit = built;
  }
  let f = 1;
  if (G.prev) { f = clamp((t - G.lit.t0) / 1.6, 0, 1); if (!(f < 1)) { G.prev = null; f = 1; } }
  return f;
}
function drawLayerTile(ctx, L, off, T, w) {
  const xo = wrap(off, T);
  ctx.drawImage(L.c, xo - T, L.oy); if (xo < w) ctx.drawImage(L.c, xo, L.oy);
}
function forTile(bx, off, T, w, m, fn) {
  const xo = wrap(off, T);
  for (let k = -1; k <= 1; k++) { const sx = bx + xo + k * T; if (sx > -m && sx < w + m) fn(sx); }
}
function skylineDraw(W, ctx, w, h, camX, E, t) {
  const tA = W._animT(E, t);
  const hy = skyHorizon(W, h);
  const G = skylineGeom(W, w, h, hy);
  const f = skylineLit(W, G, E, t);
  const S = G.S, T = G.T, lit = G.lit, col = lit.col;
  const mir = E.mirror, windDir = (E.season < -0.05 ? -1 : 1) * (mir ? -1 : 1);
  const C = W._skyC;
  for (const layer of ['far', 'near']) {
    // camX is a screen-space camera offset (F-CORE already signs it for the mirror world); the layer is drawn inside a flip when mirrored
    const off = -camX * (layer === 'far' ? 0.12 : 0.3) * (mir ? -1 : 1);
    ctx.save();
    if (mir) { ctx.translate(w, 0); ctx.scale(-1, 1); }
    if (G.prev) drawLayerTile(ctx, G.prev[layer], off, T, w);
    if (f < 1) ctx.globalAlpha = f;
    const L = lit[layer];
    drawLayerTile(ctx, L, off, T, w);
    ctx.globalAlpha = 1;
    {                                                    // neon haze rising from the streets (Zee 2026-11-04 reference)
      const hk = clamp(0.45 + col.lit, 0.45, 1) * (layer === 'far' ? 1 : 0.6), gH = S * (layer === 'far' ? 2.6 : 1.4);
      const hg = ctx.createLinearGradient(0, hy - gH, 0, hy + S * 0.2);
      hg.addColorStop(0, 'rgba(60,230,210,0)'); hg.addColorStop(0.55, `rgba(70,225,205,${(0.42 * hk).toFixed(3)})`); hg.addColorStop(1, `rgba(255,80,190,${(0.48 * hk).toFixed(3)})`);
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = hg; ctx.fillRect(-10, hy - gH, w + 20, gH + S * 0.2); ctx.restore();
    }
    // roof gears (clipped above the roof line so they stand on the building)
    for (const gr of L.anim.gears) {
      forTile(gr.x, off, T, w, gr.r * 1.5, (sx) => {
        ctx.save(); ctx.beginPath(); ctx.rect(sx - gr.r * 1.3, gr.roof - gr.r * 1.4, gr.r * 2.6, gr.r * 1.4); ctx.clip();
        ctx.translate(sx, gr.y); ctx.rotate(gr.dir * tA * gr.spd * (0.6 + E.vol));
        const sc = gr.r / L.gearR; ctx.scale(sc, sc);
        ctx.drawImage(L.gear, -L.gear.width / 2, -L.gear.height / 2);
        ctx.restore();
      });
    }
    // the bullion train crossing the viaduct: busier markets run it faster
    if (layer === 'far' && L.anim.trackY) {
      const ty = L.anim.trackY, spd = S * (0.5 + 1.6 * E.vol), car = S * 0.42, chh = S * 0.15, gap = S * 0.05;
      const head = wrap(tA * spd, T + car * 5) - car * 4;
      const night = col.night, body = shadec(col.far, -0.35), lit = night ? 'rgba(255,214,120,0.95)' : css(shadec(col.far, 0.25));
      forTile(head, off, T, w, car * 6, (sx) => {
        ctx.fillStyle = css(body);
        ctx.fillRect(sx, ty - chh, car, chh); ctx.fillRect(sx + car * 0.15, ty - chh * 1.55, car * 0.12, chh * 0.6);          // locomotive + stack
        ctx.fillRect(sx + car * 0.55, ty - chh * 1.35, car * 0.4, chh * 0.4);
        ctx.fillStyle = css(mixc(RGB(P.crimson), col.far, night ? 0.5 : 0.35)); ctx.fillRect(sx - car * 0.08, ty - chh * 0.35, car * 0.1, chh * 0.35);
        if (night) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; const lg = ctx.createRadialGradient(sx - car * 0.05, ty - chh * 0.6, 0, sx - car * 0.05, ty - chh * 0.6, S * 0.5); lg.addColorStop(0, 'rgba(255,230,160,0.7)'); lg.addColorStop(1, 'rgba(255,230,160,0)'); ctx.fillStyle = lg; ctx.fillRect(sx - S * 0.55, ty - chh * 0.6 - S * 0.5, S * 1, S * 1); ctx.restore(); }
        for (let k = 1; k <= 3; k++) {
          const cx0 = sx + k * (car + gap);
          ctx.fillStyle = css(body); ctx.fillRect(cx0, ty - chh * 0.8, car, chh * 0.8);
          ctx.fillStyle = css(mixc(RGB(P.gold), col.far, night ? 0.45 : 0.3));                                               // gold bars riding on top
          for (let q = 0; q < 3; q++) { ctx.beginPath(); ctx.moveTo(cx0 + car * (0.1 + q * 0.28), ty - chh * 0.8); ctx.lineTo(cx0 + car * (0.14 + q * 0.28), ty - chh * 1.15); ctx.lineTo(cx0 + car * (0.3 + q * 0.28), ty - chh * 1.15); ctx.lineTo(cx0 + car * (0.34 + q * 0.28), ty - chh * 0.8); ctx.fill(); }
          ctx.fillStyle = lit; ctx.fillRect(cx0 + car * 0.15, ty - chh * 0.55, car * 0.7, Math.max(1, chh * 0.18));
        }
        const sp2 = L.steam, sr2 = S * 0.12;
        for (let k = 0; k < 4; k++) { const age = fract(tA * 0.9 + k / 4); ctx.globalAlpha = (1 - age) * 0.45; const rr = sr2 * (0.5 + age * 1.6); ctx.drawImage(sp2, sx + car * 0.2 - age * S * 0.6 - rr, ty - chh * 1.6 - age * S * 0.5 - rr, rr * 2, rr * 2); }
        ctx.globalAlpha = 1;
      });
    }
    // chimney steam (stateless puffs drifting with the daily-trend wind)
    const sp = L.steam, sr = sp.width / 2;
    for (const ch of L.anim.chimneys) {
      forTile(ch.x, off, T, w, S * 2, (sx) => {
        for (let k = 0; k < 6; k++) {
          const age = fract(tA * (0.16 + 0.08 * E.vol) + k / 6 + rand(ch.x) * 0.5);
          const rr = S * (0.07 + age * 0.34) * (layer === 'far' ? 0.7 : 1);
          const px = sx + (mir ? -windDir : windDir) * age * S * (0.5 + 1.2 * E.vol) + Math.sin(tA * 1.3 + k * 2.1) * S * 0.04 * age;
          const py = ch.y - age * S * 1.5;
          ctx.globalAlpha = (1 - age) * (layer === 'far' ? 0.4 : 0.6) * (E.weather === 'storm' ? 0.6 : 1);
          ctx.drawImage(sp, px - rr, py - rr, rr * 2, rr * 2);
        }
      });
    }
    ctx.globalAlpha = 1;
    // night beacons on spires
    if (col.night || (C && C.nightness > 0.4)) {
      for (const lt of []) {                             // Zee 2026-11-04: the blinking antenna beacons were distracting - removed
        const on = fract(tA * 0.7 + rand(lt.x) * 3) < 0.45;
        if (!on) continue;
        forTile(lt.x, off, T, w, 20, (sx) => {
          ctx.save(); ctx.globalCompositeOperation = 'lighter';
          const rg = ctx.createRadialGradient(sx, lt.y, 0, sx, lt.y, S * 0.18);
          rg.addColorStop(0, 'rgba(255,90,80,0.9)'); rg.addColorStop(1, 'rgba(255,40,40,0)');
          ctx.fillStyle = rg; ctx.fillRect(sx - S * 0.18, lt.y - S * 0.18, S * 0.36, S * 0.36);
          ctx.restore();
        });
      }
    }
    ctx.restore();
    // the clock's hands (never mirrored: the time reads right even on the back of the page)
    if (L.anim.clock) {
      const ck = L.anim.clock;
      forTile(ck.x, off, T, w, ck.r * 2, (sx0) => {
        const sx = mir ? w - sx0 : sx0, hr = E.day_frac * 24, mn = (hr * 60) % 60;
        const ah = ((hr % 12) / 12) * TAU - Math.PI / 2, am = (mn / 60) * TAU - Math.PI / 2;
        ctx.save();
        if (col.night) { ctx.globalCompositeOperation = 'lighter'; const rg = ctx.createRadialGradient(sx, ck.y, ck.r * 0.5, sx, ck.y, ck.r * 2.4); rg.addColorStop(0, 'rgba(255,214,140,0.35)'); rg.addColorStop(1, 'rgba(255,214,140,0)'); ctx.fillStyle = rg; ctx.fillRect(sx - ck.r * 2.4, ck.y - ck.r * 2.4, ck.r * 4.8, ck.r * 4.8); ctx.globalCompositeOperation = 'source-over'; }
        ctx.strokeStyle = css(shadec(col.far, -0.55)); ctx.lineCap = 'round';
        ctx.lineWidth = Math.max(1.5, ck.r * 0.11); ctx.beginPath(); ctx.moveTo(sx, ck.y); ctx.lineTo(sx + Math.cos(ah) * ck.r * 0.5, ck.y + Math.sin(ah) * ck.r * 0.5); ctx.stroke();
        ctx.lineWidth = Math.max(1, ck.r * 0.07); ctx.beginPath(); ctx.moveTo(sx, ck.y); ctx.lineTo(sx + Math.cos(am) * ck.r * 0.8, ck.y + Math.sin(am) * ck.r * 0.8); ctx.stroke();
        ctx.fillStyle = css(RGB(P.goldDeep)); ctx.beginPath(); ctx.arc(sx, ck.y, Math.max(1.5, ck.r * 0.08), 0, TAU); ctx.fill();
        ctx.restore();
      });
    }
    // atmospheric haze between and in front of the layers
    const hzc = C ? (C.kind === 'storm' ? C_STORMPURPLE : C.kind === 'night' ? mixc(C.stops[3], C_BLACK, 0.2) : mixc(C.stops[3], C_WHITE, 0.15)) : C_WHITE;
    const hh = layer === 'far' ? S * 2.2 : S * 1.0, ha = layer === 'far' ? (C && C.kind === 'dead' ? 0.75 : 0.45) : (C && C.kind === 'dead' ? 0.55 : 0.18);
    const hg = ctx.createLinearGradient(0, hy - hh, 0, hy + S * 0.3);
    hg.addColorStop(0, css(hzc, 0)); hg.addColorStop(1, css(hzc, ha));
    ctx.fillStyle = hg; ctx.fillRect(-0.15 * w, hy - hh, w * 1.3, hh + S * 0.3);
  }
  if (C && C.kind === 'dead') {      // heavy sepia fog swallowing the skyline
    const fg = ctx.createLinearGradient(0, hy - S * 3.2, 0, hy);
    fg.addColorStop(0, 'rgba(200,178,140,0)'); fg.addColorStop(0.6, 'rgba(200,178,140,0.35)'); fg.addColorStop(1, 'rgba(206,186,150,0.62)');
    ctx.fillStyle = fg; ctx.fillRect(-0.15 * w, hy - S * 3.2, w * 1.3, S * 3.2);
  }
}

// ============================================================================================================ TERRAIN
// The street slab (top face of crushed marble, ledger-book hills, marble blocks, gold deco trim, gear band, riveted iron) is rendered once
// into a cache in xn-space and drawn each frame with ONE shear transform. Per frame: the underworks, telescoping pistons, the clockwork gear
// band (turns when the street tilts), chasm voids, scorch embers, sparks and steam.
function initPools(W) {
  W._spk = { n: 180, x: new Float32Array(180), y: new Float32Array(180), vx: new Float32Array(180), vy: new Float32Array(180), life: new Float32Array(180), i: 0 };
  W._stm = { n: 60, x: new Float32Array(60), y: new Float32Array(60), vx: new Float32Array(60), vy: new Float32Array(60), life: new Float32Array(60), r: new Float32Array(60), i: 0 };
  if (typeof initWeatherPools === 'function') initWeatherPools(W);
}
function wrapDraw(g, size, fn) { for (let ox = -size; ox <= size; ox += size) for (let oy = -size; oy <= size; oy += size) fn(ox, oy); }
function terrainMaterials(W, s) {
  const key = Math.round(s * 2);
  if (W._mat && W._mat.key === key) return W._mat;
  const M = { key };
  // marble: warm white with grey and a few gold veins (tileable)
  {
    const N = 256, c = makeCanvas(N, N), g = c.getContext('2d');
    g.fillStyle = P.marble; g.fillRect(0, 0, N, N);
    for (let i = 0; i < 22; i++) {
      const x = rand(i * 3.3) * N, y = rand(i * 7.7) * N, r = 18 + rand(i * 1.1) * 46;
      wrapDraw(g, N, (ox, oy) => { const gr = g.createRadialGradient(x + ox, y + oy, 0, x + ox, y + oy, r); gr.addColorStop(0, rand(i) > 0.5 ? 'rgba(200,192,175,0.28)' : 'rgba(255,253,246,0.4)'); gr.addColorStop(1, 'rgba(200,192,175,0)'); g.fillStyle = gr; g.fillRect(x + ox - r, y + oy - r, r * 2, r * 2); });
    }
    for (let v = 0; v < 9; v++) {
      const gold = v >= 7, pts = []; let x = rand(v * 5.1) * N, y = rand(v * 2.9) * N, ang = rand(v * 8.3) * TAU;
      for (let j = 0; j < 16; j++) { pts.push(x, y); ang += (rand(v * 31 + j) - 0.5) * 1.1; x += Math.cos(ang) * 18; y += Math.sin(ang) * 18; }
      g.strokeStyle = gold ? 'rgba(214,170,60,0.75)' : `rgba(150,141,124,${(0.25 + rand(v) * 0.35).toFixed(2)})`;
      g.lineWidth = gold ? 1.2 : 0.6 + rand(v * 4.4) * 1.6; g.lineJoin = 'round';
      wrapDraw(g, N, (ox, oy) => { g.beginPath(); for (let j = 0; j < pts.length; j += 2) { if (j === 0) g.moveTo(pts[j] + ox, pts[j + 1] + oy); else g.lineTo(pts[j] + ox, pts[j + 1] + oy); } g.stroke(); });
    }
    M.marble = c;
  }
  // ledger stacks: page edges and leather covers of old ledger books (the hills are piles of ledgers where the market dwelt)
  {
    const N = 192, Hh = 72, c = makeCanvas(N, Hh), g = c.getContext('2d');
    const covers = ['#7a3b2e', '#2f4f6e', '#3f5e3a', '#6b2f4a', '#8a6a24'];
    let y = 0, k = 0;
    while (y < Hh) {
      const cover = k % 4 === 0;
      const th = cover ? 3 : 2 + (rand(k * 3.1) * 2 | 0);
      g.fillStyle = cover ? covers[k % covers.length] : ['#efe6c8', '#f8f1dc', '#e4d8b4', '#f2e9cc'][k % 4];
      g.beginPath(); g.moveTo(0, y);
      for (let x = 0; x <= N; x += 16) g.lineTo(x, y + Math.sin(x / N * TAU * 2 + k) * 0.6);
      g.lineTo(N, y + th); g.lineTo(0, y + th); g.closePath(); g.fill();
      if (!cover) { g.fillStyle = 'rgba(159,182,201,0.55)'; g.fillRect(0, y + th - 1, N, 0.6); }
      else { g.fillStyle = 'rgba(255,214,120,0.6)'; for (let x = (k * 37) % 48; x < N; x += 48) g.fillRect(x, y + 1, 6, 1); }
      g.fillStyle = 'rgba(90,70,40,0.35)'; g.fillRect(0, y + th, N, 0.8);
      y += th + 0.8; k++;
    }
    M.ledger = c;
  }
  // crushed marble gravel for the walking surface (tileable)
  {
    const N = 128, c = makeCanvas(N, N), g = c.getContext('2d');
    g.fillStyle = '#efe9dc'; g.fillRect(0, 0, N, N);
    const cols = [P.marbleShade, P.marbleVein, '#ffffff', '#fbf7ee', P.marbleDark, '#d8cfbd'];
    for (let i = 0; i < 260; i++) {
      const x = rand(i * 1.9) * N, y = rand(i * 4.7) * N, r = 0.8 + rand(i * 2.3) * 2.6, n = 4 + (rand(i) * 2 | 0);
      g.fillStyle = i % 37 === 0 ? P.gold : i % 29 === 0 ? '#f0e4c0' : cols[i % cols.length];
      wrapDraw(g, N, (ox, oy) => { g.beginPath(); for (let j = 0; j < n; j++) { const a = j / n * TAU + rand(i + j); const rr = r * (0.6 + 0.4 * rand(i * 3 + j)); if (j === 0) g.moveTo(x + ox + Math.cos(a) * rr, y + oy + Math.sin(a) * rr); else g.lineTo(x + ox + Math.cos(a) * rr, y + oy + Math.sin(a) * rr); } g.closePath(); g.fill(); });
    }
    M.gravel = c;
  }
  // the underworks wall far below the street: dark iron, big gear silhouettes, pipes, furnace glints
  {
    const N = 256, c = makeCanvas(N, N), g = c.getContext('2d');
    g.fillStyle = '#16131a'; g.fillRect(0, 0, N, N);
    for (let i = 0; i < 5; i++) {
      const x = rand(i * 6.1) * N, y = rand(i * 2.7) * N, r = 26 + rand(i * 9.3) * 40;
      wrapDraw(g, N, (ox, oy) => { gearPath(g, x + ox, y + oy, r, 10 + i * 2, r * 0.16, i, r * 0.25); g.fillStyle = '#211b22'; g.fill('evenodd'); g.strokeStyle = '#2b2329'; g.lineWidth = 2; g.stroke(); });
    }
    g.strokeStyle = '#2a2227'; g.lineWidth = 5;
    for (let i = 0; i < 4; i++) { const y = rand(i * 4.9 + 1) * N; g.beginPath(); g.moveTo(0, y); g.lineTo(N, y); g.stroke(); g.fillStyle = '#332a2e'; for (let x = 20; x < N; x += 64) g.fillRect(x, y - 5, 7, 10); }
    for (let i = 0; i < 9; i++) { const x = rand(i * 8.8) * N, y = rand(i * 5.5) * N; g.fillStyle = 'rgba(255,120,40,0.28)'; g.fillRect(x, y, 3, 2); }
    M.under = c;
  }
  // gear sprites for the gear band (big + small, brass, ink outline, highlight)
  const mkGear = (r, teeth, base) => {
    const R = Math.ceil(r * 1.3) + 2, c = makeCanvas(R * 2, R * 2), g = c.getContext('2d');
    gearPath(g, R, R, r, teeth, r * 0.22, 0, r * 0.22);
    const gr = g.createLinearGradient(R - r, R - r, R + r, R + r);
    gr.addColorStop(0, css(shadec(RGB(base), 0.3))); gr.addColorStop(0.45, base); gr.addColorStop(1, css(shadec(RGB(base), -0.35)));
    g.fillStyle = gr; g.fill('evenodd');
    g.lineWidth = Math.max(1, s * LINE.inkThin); g.strokeStyle = P.ink; g.lineJoin = 'round'; g.stroke();
    g.strokeStyle = 'rgba(255,240,190,0.55)'; g.lineWidth = Math.max(1, s * 0.008); g.beginPath(); g.arc(R, R, r * 0.62, Math.PI * 1.05, Math.PI * 1.75); g.stroke();
    for (let k = 0; k < 4; k++) { const a = k / 4 * TAU + 0.4; g.fillStyle = 'rgba(26,20,16,0.55)'; g.beginPath(); g.arc(R + Math.cos(a) * r * 0.45, R + Math.sin(a) * r * 0.45, r * 0.11, 0, TAU); g.fill(); }
    return c;
  };
  M.gearBig = mkGear(Math.max(4, GROUND.gears * s * 0.44), 12, P.brass);
  M.gearSmall = mkGear(Math.max(3, GROUND.gears * s * 0.3), 9, P.gold);
  M.gearRBig = GROUND.gears * s * 0.44; M.gearRSmall = GROUND.gears * s * 0.3;
  M.puff = softBlob(Math.max(6, Math.round(s * 0.2)), [235, 232, 225]);
  {   // a big dark gear for the deep underworks
    const r = Math.max(10, s * 0.8), R = Math.ceil(r * 1.25) + 2, c = makeCanvas(R * 2, R * 2), g = c.getContext('2d');
    gearPath(g, R, R, r, 16, r * 0.14, 0, r * 0.18);
    const gr = g.createLinearGradient(R - r, R - r, R + r, R + r); gr.addColorStop(0, '#5a4630'); gr.addColorStop(0.5, '#3a2c1f'); gr.addColorStop(1, '#221912');
    g.fillStyle = gr; g.fill('evenodd'); g.lineWidth = Math.max(1, s * 0.015); g.strokeStyle = '#120c08'; g.stroke();
    g.strokeStyle = 'rgba(255,190,110,0.25)'; g.lineWidth = Math.max(1, s * 0.03); g.beginPath(); g.arc(R, R, r * 0.7, 0, TAU); g.stroke();
    for (let k = 0; k < 6; k++) { const a = k / 6 * TAU; g.fillStyle = '#16100b'; g.beginPath(); g.ellipse(R + Math.cos(a) * r * 0.45, R + Math.sin(a) * r * 0.45, r * 0.13, r * 0.2, a, 0, TAU); g.fill(); }
    M.bgGear = c;
  }
  W._mat = M;
  return M;
}

// ---- the cached slab ----------------------------------------------------------------------------------------------------------------
// the terrain-independent part of the slab below the flat front edge, cached per (scale, xn range): marble course, gold trim, frieze, gear
// backing, riveted iron. Its y = 0 is the flat front edge.
function slabBase(W, xa, xb, D, s, Wc) {
  const key = Math.round(s * 4) + '|' + Math.round(D * 4) + '|' + xa.toFixed(5) + '|' + Wc;
  if (W._slabBase && W._slabBase.key === key) return W._slabBase;
  const M = terrainMaterials(W, s);
  const marblePx = GROUND.marble * s, trimPx = GROUND.trim * s, gearsPx = GROUND.gears * s, ironPx = GROUND.iron * s;
  const vF0 = 0, Hc = Math.ceil((GROUND.slab - GROUND.front) * s + 3);
  const c = makeCanvas(Wc, Hc), g = c.getContext('2d');
  g.fillStyle = g.createPattern(M.marble, 'repeat'); g.fillRect(0, 0, Wc, marblePx + 1);
  // 3. marble band: blocks with bevelled joints, light from the upper left
  {
    const y0 = vF0, bh = marblePx;
    const lg = g.createLinearGradient(0, y0, 0, y0 + bh);
    lg.addColorStop(0, 'rgba(255,255,255,0.35)'); lg.addColorStop(0.25, 'rgba(255,255,255,0)'); lg.addColorStop(0.7, 'rgba(60,50,40,0)'); lg.addColorStop(1, 'rgba(60,50,40,0.28)');
    g.fillStyle = lg; g.fillRect(0, y0, Wc, bh);
    const jw = s * 1.15, j0 = Math.floor(xa * D / jw);
    for (let j = j0; j * jw < xb * D; j++) {
      const u = j * jw - xa * D + (rand(j * 3.7) - 0.5) * s * 0.2;
      if (u < -4 || u > Wc + 4) continue;
      g.fillStyle = 'rgba(80,70,58,0.55)'; g.fillRect(u, y0 + 1, Math.max(1, s * 0.012), bh - 1);
      g.fillStyle = 'rgba(255,255,255,0.6)'; g.fillRect(u + Math.max(1, s * 0.012), y0 + 1, Math.max(1, s * 0.01), bh - 1);
    }
    g.fillStyle = 'rgba(80,70,58,0.3)'; g.fillRect(0, y0 + bh * 0.52, Wc, Math.max(1, s * 0.008));
  }
  // 4. gold deco trim with a zigzag
  {
    const y0 = vF0 + marblePx;
    g.fillStyle = P.gold; g.fillRect(0, y0, Wc, trimPx);
    g.fillStyle = P.goldHot; g.fillRect(0, y0, Wc, Math.max(1, trimPx * 0.22));
    g.fillStyle = P.goldDark; g.fillRect(0, y0 + trimPx * 0.8, Wc, Math.max(1, trimPx * 0.2));
    g.strokeStyle = P.goldDeep; g.lineWidth = Math.max(1, s * 0.01); g.beginPath();
    const zp = s * 0.14, zo = wrap(-xa * D, zp);
    for (let u = zo - zp; u < Wc + zp; u += zp) { g.moveTo(u, y0 + trimPx * 0.25); g.lineTo(u + zp / 2, y0 + trimPx * 0.72); g.lineTo(u + zp, y0 + trimPx * 0.25); }
    g.stroke();
  }
  // 4b. Art Deco frieze: brass sunburst fans and chevron stacks on near-black green marble
  const friezePx = GROUND.frieze * s;
  {
    const y0 = vF0 + marblePx + trimPx, F = friezePx;
    g.fillStyle = '#132620'; g.fillRect(0, y0, Wc, F);
    const fg = g.createLinearGradient(0, y0, 0, y0 + F);
    fg.addColorStop(0, 'rgba(255,255,255,0.10)'); fg.addColorStop(0.3, 'rgba(255,255,255,0)'); fg.addColorStop(1, 'rgba(0,0,0,0.35)');
    g.fillStyle = fg; g.fillRect(0, y0, Wc, F);
    const Pm = s * 1.15, j0 = Math.floor(xa * D / Pm) - 1, lw = Math.max(1, s * 0.012);
    g.lineCap = 'butt';
    for (let j = j0; j * Pm < xb * D + Pm; j++) {
      const u = j * Pm - xa * D;
      if (u < -Pm || u > Wc + Pm) continue;
      const cy = y0 + F - Math.max(1, s * 0.02), R = F * 0.86;
      for (let q = 0; q < 9; q++) {       // sunburst fan
        const a0 = Math.PI + (q / 9) * Math.PI, a1 = Math.PI + ((q + 1) / 9) * Math.PI;
        g.fillStyle = q % 2 ? '#8a6a24' : P.brass;
        g.beginPath(); g.moveTo(u, cy); g.arc(u, cy, R, a0 + 0.02, a1 - 0.02); g.closePath(); g.fill();
      }
      g.fillStyle = '#132620'; g.beginPath(); g.arc(u, cy, R * 0.42, Math.PI, 0); g.fill();
      g.fillStyle = P.gold; g.beginPath(); g.arc(u, cy, R * 0.3, Math.PI, 0); g.fill();
      g.strokeStyle = P.goldHot; g.lineWidth = lw; g.beginPath(); g.arc(u, cy, R * 0.3, Math.PI * 1.1, Math.PI * 1.5); g.stroke();
      const cu = u + Pm / 2;               // chevron stack between the fans
      g.strokeStyle = P.brass; g.lineWidth = Math.max(1.2, s * 0.018);
      for (let q = 0; q < 3; q++) { const yy = y0 + F * (0.28 + q * 0.22), ww = F * (0.55 - q * 0.08); g.beginPath(); g.moveTo(cu - ww, yy + ww * 0.5); g.lineTo(cu, yy); g.lineTo(cu + ww, yy + ww * 0.5); g.stroke(); }
      g.fillStyle = P.brassDark; g.fillRect(u + Pm * 0.22, y0 + F * 0.15, lw, F * 0.75); g.fillRect(u + Pm * 0.78, y0 + F * 0.15, lw, F * 0.75);
    }
    g.fillStyle = P.brass; g.fillRect(0, y0, Wc, Math.max(1, s * 0.012)); g.fillRect(0, y0 + F - Math.max(1, s * 0.012), Wc, Math.max(1, s * 0.012));
  }
  // 5. gear band backing (the gears themselves turn per frame) + 6. riveted iron
  {
    const y0 = vF0 + marblePx + trimPx + friezePx;
    g.fillStyle = P.ironDark; g.fillRect(0, y0, Wc, gearsPx);
    const ig = g.createLinearGradient(0, y0, 0, y0 + gearsPx);
    ig.addColorStop(0, 'rgba(0,0,0,0.55)'); ig.addColorStop(0.3, 'rgba(0,0,0,0)'); ig.addColorStop(1, 'rgba(255,200,120,0.08)');
    g.fillStyle = ig; g.fillRect(0, y0, Wc, gearsPx);
    const y1 = y0 + gearsPx;
    g.fillStyle = P.iron; g.fillRect(0, y1, Wc, ironPx);
    g.fillStyle = P.ironLight; g.fillRect(0, y1, Wc, Math.max(1, ironPx * 0.14));
    g.fillStyle = P.ironDark; g.fillRect(0, y1 + ironPx * 0.82, Wc, ironPx * 0.18 + 2);
    const rp = s * 0.3, ro = wrap(-xa * D, rp);
    for (let u = ro; u < Wc; u += rp) {
      const r = Math.max(1, 0.02 * s);
      g.fillStyle = P.rivet; g.beginPath(); g.arc(u, y1 + ironPx * 0.48, r, 0, TAU); g.fill();
      g.fillStyle = 'rgba(255,255,255,0.7)'; g.beginPath(); g.arc(u - r * 0.35, y1 + ironPx * 0.48 - r * 0.35, r * 0.4, 0, TAU); g.fill();
    }
    g.lineWidth = Math.max(1, s * LINE.ink); g.strokeStyle = P.ink; g.beginPath(); g.moveTo(0, Hc - 1.5); g.lineTo(Wc, Hc - 1.5); g.stroke();
    g.lineWidth = Math.max(1, s * LINE.inkThin); g.beginPath(); g.moveTo(0, y0); g.lineTo(Wc, y0); g.moveTo(0, vF0 + marblePx); g.lineTo(Wc, vF0 + marblePx); g.stroke();
  }
  W._slabBase = { key, c };
  return W._slabBase;
}
function buildSlab(W, prof, tr, xa, xb, D, s) {
  const M = terrainMaterials(W, s);
  const backPx = GROUND.back * s, frontPx = GROUND.front * s, slabPx = GROUND.slab * s;
  const marblePx = GROUND.marble * s, trimPx = GROUND.trim * s, gearsPx = GROUND.gears * s, ironPx = GROUND.iron * s;
  const maxHill = (prof ? prof.maxU : 0) * s;
  const vG = Math.ceil(maxHill + backPx + 10);
  const Wc = Math.min(8192, Math.ceil((xb - xa) * D)), Hc = Math.ceil(vG + slabPx + 3);
  const t0 = performance.now();
  let c = W._slab && W._slab.c;
  if (!c || c.width !== Wc || c.height !== Hc) c = makeCanvas(Wc, Hc);
  const g = c.getContext('2d');
  g.setTransform(1, 0, 0, 1, 0, 0); g.globalAlpha = 1; g.globalCompositeOperation = 'source-over'; g.clearRect(0, 0, Wc, Hc);
  const step = 3, n = Math.ceil(Wc / step) + 1;
  const U = new Float32Array(n), VW = new Float32Array(n);
  for (let i = 0; i < n; i++) { const u = Math.min(i * step, Wc); U[i] = u; VW[i] = vG - heightAt(prof, xa + u / D) * s; }
  const vAt = (u) => vG - heightAt(prof, xa + u / D) * s;
  const xnOf = (u) => xa + u / D;
  const vF0 = vG + frontPx;            // flat front edge
  const pat = (img) => g.createPattern(img, 'repeat');
  // silhouette path (top face + front face) for clipping decals
  const sil = new Path2D();
  sil.moveTo(0, Hc); for (let i = 0; i < n; i++) sil.lineTo(U[i], VW[i] - backPx); sil.lineTo(Wc, Hc); sil.closePath();
  // 1. the static base (terrain-independent, cached per scale and range)
  g.drawImage(slabBase(W, xa, xb, D, s, Wc).c, 0, vF0);
  // 2. hills: piles of ledger books (where the market dwelt)
  const hill = new Path2D();
  hill.moveTo(0, vF0); for (let i = 0; i < n; i++) hill.lineTo(U[i], Math.min(vF0, VW[i] + frontPx)); hill.lineTo(Wc, vF0); hill.closePath();
  if (maxHill > 1) {
    g.save(); g.clip(hill);
    g.fillStyle = '#e9dfc0'; g.fillRect(0, 0, Wc, vF0);
    // stacked ledger books: rows of books with leather covers and cream page blocks; boundaries on a fixed grid in xn so they never shuffle
    const COV = ['#7a3b2e', '#2f4f6e', '#3f5e3a', '#6b2f4a', '#8a6a24', '#4a2f6b', '#9a4a22'];
    const PAGES = ['#f4ecd2', '#efe4c4', '#f8f2de', '#e8dcb8'];
    const rowH = Math.max(5, s * 0.085), cell = Math.max(10, s * 0.32), X0 = xa * D;
    const rows = Math.ceil((maxHill + frontPx) / rowH) + 1;
    g.lineJoin = 'miter';
    for (let r = 0; r < rows; r++) {
      const yb = vF0 - r * rowH, yt = yb - rowH, jit = (q) => (rand(q * 3.7 + r * 11.3) - 0.5) * rowH * 0.18;
      let j = Math.floor(X0 / cell) - 1;
      const jEnd = Math.ceil((X0 + Wc) / cell) + 1;
      let start = j * cell - X0, startJ = j;
      for (j = j + 1; j <= jEnd; j++) {
        if (rand(j * 7.31 + r * 101.1) > 0.42 && j - startJ < 4) continue;
        const u0 = start, u1 = j * cell - X0 - 1, cov = COV[(Math.floor(rand(startJ * 3.1 + r * 17.7) * COV.length)) % COV.length];
        const dy = jit(startJ), bh = rowH - 1;
        let vis = false;
        for (let q = 0; q <= 4 && !vis; q++) if (vAt(u0 + (u1 - u0) * q / 4) + frontPx < yb) vis = true;
        if (!vis || u1 < -2 || u0 > Wc + 2) { start = j * cell - X0; startJ = j; continue; }
        g.fillStyle = PAGES[(startJ + r) & 3]; g.fillRect(u0, yt + dy, u1 - u0, bh);
        g.fillStyle = cov; g.fillRect(u0, yt + dy, u1 - u0, Math.max(1.2, bh * 0.2)); g.fillRect(u0, yt + dy + bh * 0.8, u1 - u0, Math.max(1.2, bh * 0.2));
        g.fillRect(rand(startJ * 5.5 + r) < 0.5 ? u0 : u1 - Math.max(2, s * 0.03), yt + dy, Math.max(2, s * 0.03), bh);
        g.fillStyle = 'rgba(159,182,201,0.5)'; g.fillRect(u0 + 2, yt + dy + bh * 0.48, u1 - u0 - 4, Math.max(0.6, bh * 0.07));
        if (rand(startJ * 9.9 + r) < 0.3) { g.fillStyle = 'rgba(255,214,120,0.85)'; g.fillRect(u0 + (u1 - u0) * 0.4, yt + dy + 1, Math.max(2, s * 0.06), Math.max(1, bh * 0.12)); }
        g.lineWidth = Math.max(0.8, s * 0.011); g.strokeStyle = 'rgba(26,20,16,0.75)'; g.strokeRect(u0, yt + dy, u1 - u0, bh);
        start = j * cell - X0; startJ = j;
      }
    }
    // gears buried in the piles
    for (let xn = Math.ceil(xa * 9) / 9; xn < xb; xn += 1 / 9) {
      const idx = Math.round(xn * 9), u = (xn - xa) * D, top = vAt(u) + frontPx, depth = vF0 - top;
      if (depth < s * 0.2 || rand(idx * 4.31) > 0.35) continue;
      const rr = Math.min(depth * 0.35, s * (0.06 + rand(idx * 5.5) * 0.06)), gy = top + depth * (0.35 + rand(idx * 3.9) * 0.4);
      gearPath(g, u, gy, rr, 9, rr * 0.25, rand(idx), rr * 0.3);
      g.fillStyle = P.brass; g.fill('evenodd'); g.lineWidth = Math.max(1, s * LINE.inkThin); g.strokeStyle = P.ink; g.stroke();
    }
    // highlight band under the crest + contact shadow above the marble
    g.lineWidth = s * 0.1; g.strokeStyle = 'rgba(255,250,235,0.32)'; g.beginPath();
    for (let i = 0; i < n; i++) { const v = VW[i] + frontPx + s * 0.05; if (i === 0) g.moveTo(U[i], v); else g.lineTo(U[i], v); }
    g.stroke();
    const sg = g.createLinearGradient(0, vF0 - s * 0.16, 0, vF0);
    sg.addColorStop(0, 'rgba(40,30,20,0)'); sg.addColorStop(1, 'rgba(40,30,20,0.35)');
    g.fillStyle = sg; g.fillRect(0, vF0 - s * 0.16, Wc, s * 0.16);
    g.restore();
  }
  // 3-6. the static base below the flat front edge (marble course, gold trim, deco frieze, gear backing, iron): cached separately
  // 7. the walking surface: crushed marble top face
  {
    const top = new Path2D();
    for (let i = 0; i < n; i++) { if (i === 0) top.moveTo(U[i], VW[i] - backPx); else top.lineTo(U[i], VW[i] - backPx); }
    for (let i = n - 1; i >= 0; i--) top.lineTo(U[i], VW[i] + frontPx);
    top.closePath();
    g.fillStyle = pat(M.gravel); g.fill(top);
    g.save(); g.clip(top);
    g.lineWidth = backPx * 0.9; g.strokeStyle = 'rgba(90,80,64,0.22)'; g.beginPath();
    for (let i = 0; i < n; i++) { if (i === 0) g.moveTo(U[i], VW[i] - backPx); else g.lineTo(U[i], VW[i] - backPx); }
    g.stroke();
    g.lineWidth = Math.max(1.5, frontPx * 0.5); g.strokeStyle = 'rgba(255,255,255,0.5)'; g.beginPath();
    for (let i = 0; i < n; i++) { if (i === 0) g.moveTo(U[i], VW[i] + frontPx - 1); else g.lineTo(U[i], VW[i] + frontPx - 1); }
    g.stroke();
    // flat marble chips, ledger scraps (deterministic per xn: stable while the price moves)
    for (let xn = Math.ceil(xa * 100) / 100; xn < xb; xn += 1 / 100) {
      const idx = Math.round(xn * 100), r = rand(idx * 1.37);
      if (r > 0.55) continue;
      const u = (xn - xa) * D + (rand(idx * 2.1) - 0.5) * 4, v = vAt(u) - backPx * 0.8 + (backPx + frontPx * 0.7) * rand(idx * 3.3);
      const rr = (1 + rand(idx * 5.9) * 2.6) * s / 95, m = 4 + (rand(idx) * 2 | 0);
      g.fillStyle = ['#ffffff', P.marbleShade, P.marbleVein, '#f8f3e8', P.marbleDark][idx % 5];
      g.beginPath();
      for (let j = 0; j < m; j++) { const a = j / m * TAU + r * 3; const q = rr * (0.6 + 0.5 * rand(idx * 7 + j)); if (j === 0) g.moveTo(u + Math.cos(a) * q * 1.4, v + Math.sin(a) * q * 0.6); else g.lineTo(u + Math.cos(a) * q * 1.4, v + Math.sin(a) * q * 0.6); }
      g.closePath(); g.fill();
    }
    for (let xn = Math.ceil(xa * 24) / 24; xn < xb; xn += 1 / 24) {
      const idx = Math.round(xn * 24);
      if (rand(idx * 9.13) > 0.32) continue;
      const u = (xn - xa) * D, v = vAt(u) - backPx * 0.3 + rand(idx * 2.7) * backPx * 0.6, pw = s * 0.15, ph = s * 0.05, sk = (rand(idx * 4.4) - 0.5) * s * 0.06;
      g.fillStyle = P.ledger; g.beginPath(); g.moveTo(u - pw / 2 + sk, v - ph / 2); g.lineTo(u + pw / 2 + sk, v - ph / 2); g.lineTo(u + pw / 2 - sk, v + ph / 2); g.lineTo(u - pw / 2 - sk, v + ph / 2); g.closePath(); g.fill();
      g.lineWidth = Math.max(0.6, s * 0.006); g.strokeStyle = 'rgba(159,182,201,0.9)';
      g.beginPath(); g.moveTo(u - pw * 0.4, v - ph * 0.1); g.lineTo(u + pw * 0.4, v - ph * 0.1); g.moveTo(u - pw * 0.4, v + ph * 0.25); g.lineTo(u + pw * 0.3, v + ph * 0.25); g.stroke();
      g.strokeStyle = 'rgba(26,20,16,0.5)'; g.stroke();
    }
    g.restore();
    // ink: the front edge is THE line the feet stand just behind; a softer line marks the back edge
    g.lineJoin = 'round'; g.lineCap = 'round';
    g.lineWidth = Math.max(1, s * LINE.inkThin); g.strokeStyle = P.inkSoft; g.beginPath();
    for (let i = 0; i < n; i++) { if (i === 0) g.moveTo(U[i], VW[i] - backPx); else g.lineTo(U[i], VW[i] - backPx); }
    g.stroke();
    g.lineWidth = Math.max(1, s * LINE.ink); g.strokeStyle = P.ink; g.beginPath();
    for (let i = 0; i < n; i++) { if (i === 0) g.moveTo(U[i], VW[i] + frontPx); else g.lineTo(U[i], VW[i] + frontPx); }
    g.stroke();
  }
  // 7b. the path crumbles: chips broken out of the front edge, hairline cracks running down the face
  for (let xn = Math.ceil(xa * 32) / 32; xn < xb; xn += 1 / 32) {
    const idx = Math.round(xn * 32), r = rand(idx * 6.13);
    if (r > 0.26) continue;
    const u = (xn - xa) * D + (rand(idx * 2.7) - 0.5) * s * 0.2, vf = vAt(u) + frontPx;
    const w1 = s * (0.03 + 0.05 * rand(idx * 3.3)), w2 = s * (0.03 + 0.05 * rand(idx * 4.4)), d = s * (0.03 + 0.05 * rand(idx * 5.5));
    g.fillStyle = '#9d9585'; g.beginPath(); g.moveTo(u - w1, vf - 0.5); g.lineTo(u + w2, vf - 0.5); g.lineTo(u + w2 * 0.3, vf + d); g.lineTo(u - w1 * 0.4, vf + d * 0.7); g.closePath(); g.fill();
    g.fillStyle = 'rgba(60,50,40,0.35)'; g.beginPath(); g.moveTo(u - w1 * 0.4, vf + d * 0.7); g.lineTo(u + w2 * 0.3, vf + d); g.lineTo(u + w2, vf - 0.5); g.closePath(); g.fill();
    g.lineWidth = Math.max(1, s * LINE.inkThin); g.strokeStyle = P.ink; g.stroke();
    if (r < 0.13) {
      let cu = u, cv = vf + d * 0.8;
      g.lineWidth = Math.max(0.7, s * 0.008); g.strokeStyle = 'rgba(40,32,24,0.7)'; g.beginPath(); g.moveTo(cu, cv);
      for (let q = 0; q < 4; q++) { cu += (rand(idx * 9 + q) - 0.5) * s * 0.1; cv += s * (0.03 + 0.04 * rand(idx * 7 + q)); g.lineTo(cu, cv); }
      g.stroke();
    }
  }
  // 8. pages sticking out of the ledger hills
  if (maxHill > 1) {
    for (let xn = Math.ceil(xa * 40) / 40; xn < xb; xn += 1 / 40) {
      const idx = Math.round(xn * 40), u = (xn - xa) * D, top = vAt(u) + frontPx, depth = vF0 - top;
      if (depth < s * 0.12 || rand(idx * 6.6) > 0.5) continue;
      const py = top + depth * (0.25 + rand(idx * 1.9) * 0.6), pl = s * (0.07 + rand(idx * 2.8) * 0.08), dir = rand(idx * 3.9) < 0.5 ? -1 : 1;
      g.fillStyle = '#fbf5e2'; g.beginPath(); g.moveTo(u, py); g.lineTo(u + dir * pl, py + s * 0.012); g.lineTo(u + dir * pl * 0.9, py + s * 0.035); g.lineTo(u, py + s * 0.03); g.closePath(); g.fill();
      g.lineWidth = Math.max(0.8, s * 0.008); g.strokeStyle = 'rgba(26,20,16,0.6)'; g.stroke();
    }
  }
  // 9. weathered stretches: left behind by the market, fading to grey (subtle desaturation, cracks)
  for (const wr of (tr && tr.weathered) || []) {
    const ua = (Math.min(wr[0], wr[1]) - xa) * D, ub = (Math.max(wr[0], wr[1]) - xa) * D;
    if (ub < 0 || ua > Wc || ub - ua < 1) continue;
    const fade = Math.min(s * 0.5, (ub - ua) / 2);
    g.save(); g.clip(sil);
    const grd = g.createLinearGradient(ua, 0, ub, 0);
    const f = fade / (ub - ua);
    grd.addColorStop(0, 'rgba(128,128,128,0)'); grd.addColorStop(f, 'rgba(128,128,128,0.75)'); grd.addColorStop(1 - f, 'rgba(128,128,128,0.75)'); grd.addColorStop(1, 'rgba(128,128,128,0)');
    g.globalCompositeOperation = 'saturation'; g.fillStyle = grd; g.fillRect(ua, 0, ub - ua, Hc);
    g.globalCompositeOperation = 'source-over';
    const grd2 = g.createLinearGradient(ua, 0, ub, 0);
    grd2.addColorStop(0, 'rgba(96,94,88,0)'); grd2.addColorStop(f, 'rgba(96,94,88,0.2)'); grd2.addColorStop(1 - f, 'rgba(96,94,88,0.2)'); grd2.addColorStop(1, 'rgba(96,94,88,0)');
    g.fillStyle = grd2; g.fillRect(ua, 0, ub - ua, Hc);
    for (let xn = Math.ceil(xnOf(ua) * 60) / 60; xn < xnOf(ub); xn += 1 / 60) {       // lichen + dust on the walking surface
      const idx = Math.round(xn * 60); if (rand(idx * 4.7) > 0.45) continue;
      const u = (xn - xa) * D, v = vAt(u) - backPx * 0.6 + rand(idx * 2.3) * backPx;
      g.fillStyle = rand(idx) < 0.5 ? 'rgba(120,128,98,0.55)' : 'rgba(150,146,136,0.6)';
      g.beginPath(); g.ellipse(u, v, s * (0.03 + 0.04 * rand(idx * 3.1)), s * 0.012, 0, 0, TAU); g.fill();
    }
    g.strokeStyle = 'rgba(60,56,50,0.55)'; g.lineWidth = Math.max(0.7, s * 0.009);
    for (let xn = Math.ceil(xnOf(ua) * 14) / 14; xn < xnOf(ub); xn += 1 / 14) {
      const idx = Math.round(xn * 14); if (rand(idx * 2.2) > 0.55) continue;
      let u = (xn - xa) * D, v = vAt(u) + frontPx + 1;
      g.beginPath(); g.moveTo(u, v);
      for (let j = 0; j < 4; j++) { u += (rand(idx * 9 + j) - 0.5) * s * 0.12; v += s * (0.04 + rand(idx * 5 + j) * 0.06); g.lineTo(u, v); }
      g.stroke();
    }
    g.restore();
  }
  // 10. scorch craters where wicks blew
  for (const sx of (tr && tr.scorch) || []) {
    const u = (sx - xa) * D; if (u < -s || u > Wc + s) continue;
    const v = vAt(u);
    g.save(); g.clip(sil);
    g.translate(u, v); g.scale(1, (backPx + frontPx) / (s * 0.5));
    const rg = g.createRadialGradient(0, 0, 0, 0, 0, s * 0.5);
    rg.addColorStop(0, 'rgba(18,10,6,0.97)'); rg.addColorStop(0.35, 'rgba(30,18,10,0.9)'); rg.addColorStop(0.65, 'rgba(60,40,26,0.55)'); rg.addColorStop(1, 'rgba(60,40,26,0)');
    g.fillStyle = rg; g.beginPath(); g.arc(0, 0, s * 0.5, 0, TAU); g.fill();
    g.strokeStyle = 'rgba(12,7,4,0.8)'; g.lineWidth = Math.max(1, s * 0.035); g.beginPath(); g.ellipse(0, 0, s * 0.2, s * 0.15, 0, 0, TAU); g.stroke();
    g.strokeStyle = 'rgba(255,150,60,0.35)'; g.lineWidth = Math.max(1, s * 0.012); g.beginPath(); g.ellipse(0, 0, s * 0.13, s * 0.09, 0, Math.PI * 0.9, Math.PI * 1.9); g.stroke();
    g.strokeStyle = 'rgba(20,12,8,0.7)'; g.lineWidth = Math.max(0.8, s * 0.012);
    for (let q = 0; q < 7; q++) { const a = q / 7 * TAU + rand(sx * 50 + q); g.beginPath(); g.moveTo(Math.cos(a) * s * 0.2, Math.sin(a) * s * 0.15); g.lineTo(Math.cos(a) * s * (0.32 + 0.12 * rand(q + sx)), Math.sin(a) * s * (0.24 + 0.08 * rand(q * 3 + sx))); g.stroke(); }
    g.fillStyle = 'rgba(240,226,190,0.7)';
    for (let q = 0; q < 5; q++) { const a = rand(sx * 9 + q) * TAU, r = s * (0.25 + 0.15 * rand(q * 7 + sx)); g.fillRect(Math.cos(a) * r, Math.sin(a) * r * 0.8, s * 0.03, s * 0.02); }
    g.setTransform(1, 0, 0, 1, 0, 0);
    const sm = g.createLinearGradient(0, v + frontPx, 0, v + frontPx + s * 0.45);
    sm.addColorStop(0, 'rgba(30,20,14,0.6)'); sm.addColorStop(1, 'rgba(30,20,14,0)');
    g.fillStyle = sm; g.beginPath(); g.moveTo(u - s * 0.2, v + frontPx); g.lineTo(u + s * 0.2, v + frontPx); g.lineTo(u + s * 0.08, v + frontPx + s * 0.45); g.lineTo(u - s * 0.1, v + frontPx + s * 0.45); g.fill();
    g.strokeStyle = 'rgba(20,12,8,0.75)'; g.lineWidth = Math.max(0.8, s * 0.01);
    for (let j = 0; j < 4; j++) {
      let cu = u + (j - 1.5) * s * 0.09, cv = v + frontPx;
      g.beginPath(); g.moveTo(cu, cv);
      for (let q = 0; q < 4; q++) { cu += (rand(sx * 99 + j * 7 + q) - 0.5) * s * 0.1 + (j - 1.5) * s * 0.02; cv += s * 0.06; g.lineTo(cu, cv); }
      g.stroke();
    }
    g.restore();
  }
  // 11. void chasms: torn through the whole page of the street (the hole is transparent; the void is drawn behind, per frame)
  const tears = [];
  for (const ch of (tr && tr.chasms) || []) {
    const ua = (Math.min(ch[0], ch[1]) - xa) * D, ub = (Math.max(ch[0], ch[1]) - xa) * D;
    if (ub < -s || ua > Wc + s) continue;
    const L = [], R = [], seed = ch[0] * 77.7;
    for (let v = -4; v <= Hc + 6; v += 5) {
      const zz = ((v / 5) & 1) ? 1 : -1;
      L.push(ua + (fbm(v * 0.045, seed) - 0.5) * s * 0.16 + zz * s * 0.018, v);
      R.push(ub + (fbm(v * 0.045, seed + 5) - 0.5) * s * 0.16 - zz * s * 0.018, v);
    }
    tears.push([L, R]);
    g.save(); g.globalCompositeOperation = 'destination-out'; g.beginPath();
    for (let i = 0; i < L.length; i += 2) { if (i === 0) g.moveTo(L[i], L[i + 1]); else g.lineTo(L[i], L[i + 1]); }
    for (let i = R.length - 2; i >= 0; i -= 2) g.lineTo(R[i], R[i + 1]);
    g.closePath(); g.fill(); g.restore();
    g.save(); g.clip(sil); g.lineJoin = 'round';
    for (const E of [L, R]) {
      g.beginPath(); for (let i = 0; i < E.length; i += 2) { if (i === 0) g.moveTo(E[i], E[i + 1]); else g.lineTo(E[i], E[i + 1]); }
      g.strokeStyle = 'rgba(246,239,220,0.95)'; g.lineWidth = Math.max(2, s * 0.05); g.stroke();
      g.strokeStyle = 'rgba(180,77,255,0.8)'; g.lineWidth = Math.max(1.5, s * 0.022); g.stroke();
      g.strokeStyle = P.voidEdge; g.lineWidth = Math.max(1, s * 0.01); g.stroke();
    }
    g.restore();
  }
  W._stats.slabBuilds++; W._stats.lastSlabMs = +(performance.now() - t0).toFixed(2);
  return { c, xa, xb, D, s, vG, Wc, Hc, key: null, tears };
}

// ---- per-frame pieces ---------------------------------------------------------------------------------------------------------------
function drawPiston(ctx, x, yTop, yBase, s, j, glint) {
  const L = yBase - yTop;
  if (L < s * 0.1) return;
  const w0 = s * 0.24, w1 = s * 0.165, w2 = s * 0.1, lw = Math.max(1, s * LINE.inkThin);
  const L0 = Math.min(L, Math.max(s * 0.3, L * 0.4)), L1 = Math.max(0, (L - L0) * 0.55);
  const seg = (cx, y0, y1, ww, base) => {
    if (y1 - y0 < 1) return;
    const b = RGB(base);
    ctx.fillStyle = base; ctx.fillRect(cx - ww / 2, y0, ww, y1 - y0);
    ctx.fillStyle = css(shadec(b, 0.32)); ctx.fillRect(cx - ww / 2 + ww * 0.12, y0, ww * 0.18, y1 - y0);
    ctx.fillStyle = css(shadec(b, -0.35)); ctx.fillRect(cx + ww * 0.22, y0, ww * 0.28, y1 - y0);
    ctx.lineWidth = lw; ctx.strokeStyle = P.ink; ctx.strokeRect(cx - ww / 2, y0, ww, y1 - y0);
  };
  // top rod (polished steel), middle sleeve (steel), bottom cylinder (brass)
  seg(x, yTop, yBase - L0 - L1 + s * 0.04, w2, '#cfd6de');
  if (glint > 0) { ctx.fillStyle = `rgba(255,255,255,${(0.7 * glint).toFixed(3)})`; ctx.fillRect(x - w2 * 0.3, yTop + 2, w2 * 0.2, Math.max(2, (L - L0 - L1) * 0.6)); }
  seg(x, yBase - L0 - L1, yBase - L0 + s * 0.05, w1, '#98a2ae');
  seg(x, yBase - L0, yBase, w0, P.brass);
  // collars
  ctx.fillStyle = P.brassDark; ctx.fillRect(x - w1 * 0.62, yBase - L0 - L1 - s * 0.012, w1 * 1.24, s * 0.04); ctx.strokeRect(x - w1 * 0.62, yBase - L0 - L1 - s * 0.012, w1 * 1.24, s * 0.04);
  ctx.fillStyle = P.goldDeep; ctx.fillRect(x - w0 * 0.6, yBase - L0 - s * 0.02, w0 * 1.2, s * 0.055); ctx.strokeRect(x - w0 * 0.6, yBase - L0 - s * 0.02, w0 * 1.2, s * 0.055);
  // the clevis under the slab
  ctx.fillStyle = P.ironDark; ctx.beginPath(); ctx.moveTo(x - s * 0.15, yTop); ctx.lineTo(x + s * 0.15, yTop); ctx.lineTo(x + w2 * 0.7, yTop + s * 0.1); ctx.lineTo(x - w2 * 0.7, yTop + s * 0.1); ctx.closePath(); ctx.fill(); ctx.stroke();
  const r = Math.max(1, 0.025 * s);
  ctx.fillStyle = P.rivet; ctx.beginPath(); ctx.arc(x, yTop + s * 0.055, r, 0, TAU); ctx.fill();
  // base plate
  ctx.fillStyle = P.iron; ctx.fillRect(x - s * 0.19, yBase - s * 0.035, s * 0.38, s * 0.05); ctx.strokeRect(x - s * 0.19, yBase - s * 0.035, s * 0.38, s * 0.05);
  // a pressure gauge on every third piston: the needle reads the extension
  if (j % 3 === 0 && L0 > s * 0.28) {
    const gx = x, gy = yBase - L0 * 0.5, gr = s * 0.07;
    ctx.fillStyle = P.paper; ctx.beginPath(); ctx.arc(gx, gy, gr, 0, TAU); ctx.fill(); ctx.stroke();
    const a = Math.PI * 0.8 + clamp(L / (s * 5), 0, 1) * Math.PI * 1.4;
    ctx.strokeStyle = P.crimson; ctx.lineWidth = Math.max(1, s * 0.012); ctx.beginPath(); ctx.moveTo(gx, gy); ctx.lineTo(gx + Math.cos(a) * gr * 0.8, gy + Math.sin(a) * gr * 0.8); ctx.stroke();
    ctx.strokeStyle = P.ink; ctx.lineWidth = lw;
  }
}
// a spring piston: iron housing, steel rod, a copper coil that stretches and squashes with the street
function drawSpringPiston(ctx, x, yTop, yBase, s, glint) {
  const L = yBase - yTop;
  if (L < s * 0.1) return;
  const lw = Math.max(1, s * LINE.inkThin), hw = s * 0.27, Lh = Math.min(L * 0.38, s * 0.42), yh = yBase - Lh;
  ctx.lineWidth = lw; ctx.strokeStyle = P.ink;
  ctx.fillStyle = '#c3cbd4'; ctx.fillRect(x - s * 0.035, yTop, s * 0.07, yh - yTop); ctx.strokeRect(x - s * 0.035, yTop, s * 0.07, yh - yTop);
  if (glint > 0) { ctx.fillStyle = `rgba(255,255,255,${(0.6 * glint).toFixed(3)})`; ctx.fillRect(x - s * 0.02, yTop + 3, s * 0.015, (yh - yTop) * 0.7); }
  const top = yTop + s * 0.12, bot = yh - s * 0.02, nC = 8, amp = s * 0.11;
  if (bot > top + 2) {
    ctx.beginPath(); ctx.moveTo(x, top);
    for (let i = 0; i <= nC * 2; i++) ctx.lineTo(x + (i % 2 ? amp : -amp) * (i === 0 || i === nC * 2 ? 0 : 1), top + (bot - top) * i / (nC * 2));
    ctx.lineJoin = 'round'; ctx.strokeStyle = P.ink; ctx.lineWidth = Math.max(2, s * 0.05); ctx.stroke();
    ctx.strokeStyle = '#c87533'; ctx.lineWidth = Math.max(1.2, s * 0.028); ctx.stroke();
    ctx.strokeStyle = 'rgba(255,210,160,0.6)'; ctx.lineWidth = Math.max(0.6, s * 0.009); ctx.stroke();
  }
  ctx.lineWidth = lw; ctx.strokeStyle = P.ink;
  const gr = ctx.createLinearGradient(x - hw / 2, 0, x + hw / 2, 0);
  gr.addColorStop(0, P.ironLight); gr.addColorStop(0.35, P.iron); gr.addColorStop(1, P.ironDark);
  ctx.fillStyle = gr; ctx.fillRect(x - hw / 2, yh, hw, Lh); ctx.strokeRect(x - hw / 2, yh, hw, Lh);
  ctx.fillStyle = P.brass; ctx.fillRect(x - hw * 0.56, yh, hw * 1.12, s * 0.045); ctx.strokeRect(x - hw * 0.56, yh, hw * 1.12, s * 0.045);
  ctx.fillRect(x - hw * 0.56, yBase - s * 0.07, hw * 1.12, s * 0.04); ctx.strokeRect(x - hw * 0.56, yBase - s * 0.07, hw * 1.12, s * 0.04);
  if (Lh > s * 0.25) {      // a valve wheel on the housing
    const vx = x + hw * 0.5 + s * 0.05, vy = yh + Lh * 0.45, vr = s * 0.065;
    ctx.strokeStyle = P.crimson; ctx.lineWidth = Math.max(1.2, s * 0.02); ctx.beginPath(); ctx.arc(vx, vy, vr, 0, TAU); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(vx - vr, vy); ctx.lineTo(vx + vr, vy); ctx.moveTo(vx, vy - vr); ctx.lineTo(vx, vy + vr); ctx.stroke();
    ctx.strokeStyle = P.ink; ctx.lineWidth = lw;
  }
  ctx.fillStyle = P.ironDark; ctx.beginPath(); ctx.moveTo(x - s * 0.14, yTop); ctx.lineTo(x + s * 0.14, yTop); ctx.lineTo(x + s * 0.06, yTop + s * 0.1); ctx.lineTo(x - s * 0.06, yTop + s * 0.1); ctx.closePath(); ctx.fill(); ctx.stroke();
  ctx.fillStyle = P.rivet; ctx.beginPath(); ctx.arc(x, yTop + s * 0.055, Math.max(1, 0.025 * s), 0, TAU); ctx.fill();
}
function slabFor(W, view, prof, tr, A, B) {
  const s = view.s, w = view.w, D = Math.abs(A);
  let l = (-80 - B) / A, r = (w + 80 - B) / A; if (l > r) { const q = l; l = r; r = q; }
  const S = W._slab, key = (prof ? prof.key : 0) + '|' + Math.round(s * 2);
  if (S && S.key === key && S.xa <= l && S.xb >= r && Math.abs(S.D - D) / D < 0.04) return S;
  const pad = 0.35, xa = l - pad, xb = r + pad;
  const built = buildSlab(W, prof, tr, xa, xb, D, s);
  built.key = key;
  W._slab = built;
  return built;
}
function emitSpark(W, x, y, vx, vy) {
  const P2 = W._spk, i = P2.i; P2.i = (i + 1) % P2.n;
  P2.x[i] = x; P2.y[i] = y; P2.vx[i] = vx; P2.vy[i] = vy; P2.life[i] = 0.35 + Math.random() * 0.4;
}
function emitSteam(W, x, y, vx, vy, r) {
  const P2 = W._stm, i = P2.i; P2.i = (i + 1) % P2.n;
  P2.x[i] = x; P2.y[i] = y; P2.vx[i] = vx; P2.vy[i] = vy; P2.life[i] = 1; P2.r[i] = r;
}
function terrainDraw(W, ctx, view, tr, E, t) {
  const tA = W._animT(E, t);
  const prof = getProfile(W, tr);
  const aff = viewAffine(view, W._aff), A = aff[0], B = aff[1];
  const s = view.s, w = view.w, h = view.h, gy = view.groundY, k = tanTilt(view);
  const px = Number.isFinite(view.pivotX) ? view.pivotX : w / 2;
  const M = terrainMaterials(W, s);
  const slabPx = GROUND.slab * s, backPx = GROUND.back * s;
  const dt = W._terrT == null ? 0 : clamp(tA - W._terrT, 0, 0.1); W._terrT = tA;
  const tilt = Math.atan(k);
  const rate = dt > 0 && W._tiltPrev != null ? (tilt - W._tiltPrev) / dt : 0; W._tiltPrev = tilt;
  W._tiltRate = lerp(W._tiltRate || 0, rate, 0.3);
  W._gearRot = (W._gearRot || 0) + (tilt - (W._gearTilt ?? tilt)) * 28; W._gearTilt = tilt;
  const moving = clamp(Math.abs(W._tiltRate) / 0.25, 0, 1);
  const yBot = (x) => gy + slabPx + (x - px) * k;
  const xl = -60, xr = w + 60;
  // Zee 2026-11-04: "instead of the gears and levers at the bottom underneath earth ... the ground is a hilltop lush green ... on left is
  // a water lake where we'll drown and on the right is the paradise garden where we're happy". The walking line is unchanged (it IS the
  // price); only what is painted around it changed: lake behind the stop, green hill under the street, garden beyond the Buyer.
  let xnL = (xl - B) / A, xnR = (xr - B) / A; if (xnL > xnR) { const q = xnL; xnL = xnR; xnR = q; }
  const xnNear = A > 0 ? xnL : xnL, xnFar = xnR;
  hillDraw(W, ctx, view, prof, E, tA, A, B, k, xnNear, xnFar);
  // 3. void columns behind the chasm holes: black tears with a purple edge, all the way down
  const chasms = (tr && tr.chasms) || [];
  for (const ch of chasms) {
    let xa = A * Math.min(ch[0], ch[1]) + B, xb = A * Math.max(ch[0], ch[1]) + B; if (xa > xb) { const q = xa; xa = xb; xb = q; }
    xa -= s * 0.12; xb += s * 0.12;
    if (xb < -20 || xa > w + 20) continue;
    ctx.save(); ctx.beginPath();
    const n = Math.max(2, Math.ceil((xb - xa) / 4));
    for (let i = 0; i <= n; i++) { const x = xa + (xb - xa) * i / n; const y = walkY(view, prof, (x - B) / A, k) - backPx; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
    ctx.lineTo(xb, h + 60); ctx.lineTo(xa, h + 60); ctx.closePath();
    const pulse = 0.75 + 0.25 * Math.sin(tA * 2.6 + ch[0] * 10);
    const vg = ctx.createLinearGradient(xa, 0, xb, 0);
    vg.addColorStop(0, css(RGB(P.neonPurple), 0.55 * pulse)); vg.addColorStop(0.18, css(RGB(P.voidEdge), 0.9)); vg.addColorStop(0.35, P.voidc);
    vg.addColorStop(0.65, P.voidc); vg.addColorStop(0.82, css(RGB(P.voidEdge), 0.9)); vg.addColorStop(1, css(RGB(P.neonPurple), 0.55 * pulse));
    ctx.fillStyle = vg; ctx.fill(); ctx.clip();
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 14; i++) {        // motes sinking into nothing
      const ph = fract(tA * (0.07 + rand(i * 3.1 + ch[0]) * 0.08) + rand(i * 7.7));
      const mx = xa + (xb - xa) * (0.2 + 0.6 * rand(i * 5.3 + ch[1])), my = gy - s * 0.2 + ph * (h - gy + s * 0.4);
      ctx.fillStyle = `rgba(190,110,255,${(0.6 * (1 - ph)).toFixed(3)})`; ctx.fillRect(mx, my, Math.max(1, s * 0.02), Math.max(1, s * 0.02));
    }
    ctx.restore();
  }
  // 4. the grassy crest the Runner walks on, the boardwalk over the lake, the paradise garden beyond the Buyer
  hillTopDraw(W, ctx, view, prof, E, tA, A, B, k, xnNear, xnFar);
  // 5b. golden hour: long shadows of the skyline lying across the street, leaning away from the low sun
  if (E.golden_hour) {
    const away = E.mirror ? 1 : -1, frontPx = GROUND.front * s;
    ctx.save();
    for (let j = Math.floor(xnL / 0.16) - 1; j <= Math.ceil(xnR / 0.16) + 1; j++) {
      const xn0 = j * 0.16 + 0.04 * Math.sin(j * 7.3), wdx = 0.045 + 0.035 * rand(j * 2.1);
      const xa = A * xn0 + B, xb = A * (xn0 + wdx) + B, ya = walkY(view, prof, xn0, k), yb = walkY(view, prof, xn0 + wdx, k);
      const sk = away * s * 0.55;
      const sh = ctx.createLinearGradient(0, Math.min(ya, yb) - backPx, 0, Math.max(ya, yb) + frontPx + s * 0.45);
      sh.addColorStop(0, 'rgba(70,20,40,0.30)'); sh.addColorStop(0.35, 'rgba(70,20,40,0.22)'); sh.addColorStop(1, 'rgba(70,20,40,0)');
      ctx.fillStyle = sh; ctx.beginPath();
      ctx.moveTo(xa - sk, ya - backPx); ctx.lineTo(xb - sk, yb - backPx); ctx.lineTo(xb + sk * 0.2, yb + frontPx + s * 0.45); ctx.lineTo(xa + sk * 0.2, ya + frontPx + s * 0.45);
      ctx.closePath(); ctx.fill();
    }
    ctx.restore();
  }
  // 6. scorch embers + smoke wisps
  for (const sx of (tr && tr.scorch) || []) {
    const x = A * sx + B; if (x < -s || x > w + s) continue;
    const y = walkY(view, prof, sx, k);
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 5; i++) {
      const fl = 0.5 + 0.5 * Math.sin(tA * (5 + i * 1.7) + i * 2.3 + sx * 30);
      ctx.fillStyle = `rgba(255,${120 + i * 15},40,${(0.55 * fl).toFixed(3)})`;
      ctx.fillRect(x + (rand(i * 3.3 + sx) - 0.5) * s * 0.3, y + (rand(i * 1.7 + sx) - 0.5) * s * 0.06, Math.max(1.5, s * 0.025), Math.max(1.5, s * 0.02));
    }
    ctx.restore();
    for (let i = 0; i < 3; i++) {
      const ph = fract(tA * 0.22 + i / 3 + sx), rr = s * (0.06 + ph * 0.2);
      ctx.globalAlpha = 0.28 * (1 - ph);
      ctx.drawImage(M.puff, x - rr + Math.sin(tA + i) * s * 0.05 * ph, y - s * 0.05 - ph * s * 0.8 - rr, rr * 2, rr * 2);
    }
    ctx.globalAlpha = 1;
  }
  // 7. sparks + steam (pooled)
  const SP = W._spk;
  ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.lineWidth = Math.max(1.5, s * 0.024); ctx.lineCap = 'round';
  for (let i = 0; i < SP.n; i++) {
    if (SP.life[i] <= 0) continue;
    SP.life[i] -= dt; SP.vy[i] += s * 9 * dt; SP.x[i] += SP.vx[i] * dt; SP.y[i] += SP.vy[i] * dt;
    const L = clamp(SP.life[i] / 0.5, 0, 1);
    ctx.strokeStyle = `rgba(255,${(180 + 60 * L) | 0},90,${L.toFixed(3)})`;
    ctx.beginPath(); ctx.moveTo(SP.x[i], SP.y[i]); ctx.lineTo(SP.x[i] - SP.vx[i] * 0.04, SP.y[i] - SP.vy[i] * 0.04); ctx.stroke();
  }
  ctx.restore();
  const ST = W._stm;
  for (let i = 0; i < ST.n; i++) {
    if (ST.life[i] <= 0) continue;
    ST.life[i] -= dt * 0.8; ST.x[i] += ST.vx[i] * dt; ST.y[i] += ST.vy[i] * dt;
    const L = clamp(ST.life[i], 0, 1), rr = ST.r[i] * (2.2 - L * 1.2);
    ctx.globalAlpha = 0.45 * L; ctx.drawImage(M.puff, ST.x[i] - rr, ST.y[i] - rr, rr * 2, rr * 2);
  }
  ctx.globalAlpha = 1;
}

// ============================================================================================================ THE HILL
// Zee 2026-11-04: a lush green hilltop instead of the iron underworks. xnL / xnR = the smallest / largest x_norm on screen (mirror-safe:
// every position goes through A * xn + B, so in the mirror world the lake sits on the right, at the stop's side, and the garden on the left).
const HILL_XS = -0.04;                                   // the shore: the hill starts just behind the stop (x 0); behind it, the lake
function hillWaterY(view, prof, k) {
  const s = view.s, h = view.h;
  return clamp(Math.max(view.groundY + 0.75 * s, walkY(view, prof, HILL_XS, k) + 0.25 * s), 0, h - 0.12 * s);
}
function hillDraw(W, ctx, view, prof, E, tA, A, B, k, xnL, xnR) {
  const s = view.s, w = view.w, h = view.h;
  const backPx = GROUND.back * s, frontPx = GROUND.front * s;
  const X = (xn) => A * xn + B, Y = (xn) => walkY(view, prof, xn, k);
  const xs = HILL_XS, xFar = xnR + 0.05;
  // 1. the lake where a stopped Runner drowns: level water, drifting ripples, lily pads
  const waterY = hillWaterY(view, prof, k);
  const lakeEnd = X(0.45), lakeEdge = A > 0 ? -60 : w + 60;
  const lx0 = Math.min(lakeEdge, lakeEnd), lx1 = Math.max(lakeEdge, lakeEnd);
  ctx.save();
  const lg = ctx.createLinearGradient(0, waterY, 0, h);
  lg.addColorStop(0, '#8fd3ee'); lg.addColorStop(0.3, '#4aa3cf'); lg.addColorStop(1, '#1b4c7a');
  ctx.fillStyle = lg; ctx.fillRect(lx0, waterY, lx1 - lx0, h - waterY + 60);
  ctx.strokeStyle = '#ffffff'; ctx.lineCap = 'round'; ctx.lineWidth = Math.max(1, s * 0.016);
  const deep = Math.max(1, h - waterY);
  for (let i = 0; i < 22; i++) {
    const f = 0.05 + rand(i * 3.1) * 0.9, yy = waterY + f * deep;
    const xx = lx0 + fract(rand(i * 7.3) + tA * 0.015 * (0.4 + rand(i * 1.3))) * (lx1 - lx0);
    const ln = s * (0.1 + rand(i * 1.9) * 0.22) * (0.6 + f);
    ctx.globalAlpha = 0.15 + 0.35 * Math.pow(Math.sin(tA * 1.4 + i * 1.7), 2);
    ctx.beginPath(); ctx.moveTo(xx - ln / 2, yy); ctx.lineTo(xx + ln / 2, yy); ctx.stroke();
  }
  ctx.globalAlpha = 0.6; ctx.fillStyle = '#ffffff'; ctx.fillRect(lx0, waterY, lx1 - lx0, Math.max(1.5, s * 0.02));
  ctx.globalAlpha = 1;
  for (let i = 0; i < 6; i++) {
    const xx = X(-0.36 + i * 0.075 + rand(i * 4.4) * 0.03), yy = waterY + s * (0.14 + rand(i * 2.7) * 0.4);
    if (xx < lx0 || xx > lx1) continue;
    ctx.fillStyle = '#3f9150'; ctx.beginPath(); ctx.moveTo(xx, yy); ctx.ellipse(xx, yy, s * 0.12, s * 0.04, 0, 0.35, TAU - 0.05); ctx.closePath(); ctx.fill();
    if (i % 2 === 0) { ctx.fillStyle = '#ffc2d9'; ctx.beginPath(); ctx.arc(xx + s * 0.03, yy - s * 0.02, s * 0.028, 0, TAU); ctx.fill(); }
  }
  ctx.restore();
  // 2. the hill body: its crest is the walking line; the near flank slides into the lake just behind the stop
  const n = Math.max(48, Math.ceil(Math.abs(A * (xFar - xs)) / 6));
  ctx.save();
  ctx.beginPath();
  for (let i = 0; i <= n; i++) { const xn = xs + (xFar - xs) * i / n; const x = X(xn), y = Y(xn) - backPx; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
  ctx.lineTo(X(xFar), h + 60); ctx.lineTo(X(0.36), h + 60);
  ctx.quadraticCurveTo(X(0.03), waterY + 0.25 * s, X(xs), Y(xs) + frontPx);
  ctx.closePath();
  const top = Math.min(Y(xs), Y(xFar), Y(0.5)) - backPx;
  const hg = ctx.createLinearGradient(0, top, 0, h);
  hg.addColorStop(0, '#7fcf55'); hg.addColorStop(0.3, '#57a843'); hg.addColorStop(1, '#2c6a31');
  ctx.fillStyle = hg; ctx.fill();
  ctx.clip();
  ctx.strokeStyle = 'rgba(255,255,240,0.10)'; ctx.lineWidth = Math.max(2, s * 0.06);          // soft rolling bands down the flank
  for (let b = 1; b <= 4; b++) {
    ctx.beginPath();
    for (let i = 0; i <= n; i += 2) { const xn = xs + (xFar - xs) * i / n; const x = X(xn), y = Y(xn) + s * (0.32 * b + 0.07 * Math.sin(xn * 8 + b * 2)); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
    ctx.stroke();
  }
  const FL = ['#ffe066', '#ff8fb3', '#ffffff', '#c99bff', '#ff7a7a'];                         // wild flowers, denser toward the garden
  for (let i = 0; i < 90; i++) {
    const u = rand(i * 5.17), xn = xs + Math.pow(u, 0.8) * (xFar - xs), x = X(xn), y = Y(xn) + s * (0.22 + rand(i * 2.31) * 2.4);
    if (y > h + 4) continue;
    const r = s * (0.02 + rand(i * 9.1) * 0.022);
    ctx.fillStyle = FL[i % 5]; ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
    ctx.fillStyle = 'rgba(255,214,90,0.9)'; ctx.beginPath(); ctx.arc(x, y, r * 0.35, 0, TAU); ctx.fill();
  }
  ctx.restore();
  ctx.save(); ctx.strokeStyle = '#3d7a34'; ctx.lineWidth = Math.max(1.5, s * 0.022); ctx.lineCap = 'round';   // reeds at the shore
  for (let i = 0; i < 9; i++) {
    const xn = xs + 0.005 + i * 0.012, x = X(xn) + (rand(i * 3.3) - 0.5) * s * 0.1, y = waterY + s * 0.02, hh = s * (0.22 + rand(i * 6.1) * 0.25);
    const sw = Math.sin(tA * 1.6 + i) * s * 0.03;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.quadraticCurveTo(x + sw * 0.5, y - hh * 0.5, x + sw, y - hh); ctx.stroke();
    if (i % 3 === 0) { ctx.fillStyle = '#6b4423'; ctx.beginPath(); ctx.ellipse(x + sw, y - hh, s * 0.018, s * 0.05, 0, 0, TAU); ctx.fill(); }
  }
  ctx.restore();
}
function hillTopDraw(W, ctx, view, prof, E, tA, A, B, k, xnL, xnR) {
  const s = view.s;
  const backPx = GROUND.back * s, frontPx = GROUND.front * s;
  const X = (xn) => A * xn + B, Y = (xn) => walkY(view, prof, xn, k);
  const xs = HILL_XS, xFar = xnR + 0.05, xNear = xnL - 0.05;
  const waterY = hillWaterY(view, prof, k);
  // the boardwalk from the bank's door over the lake to the shore
  if (xNear < xs) {
    const nb = Math.max(8, Math.ceil(Math.abs(A * (xs - xNear)) / 8));
    ctx.save();
    ctx.fillStyle = '#6b4526';
    for (let xn = Math.ceil(xNear / 0.07) * 0.07; xn < xs; xn += 0.07) {          // posts down into the water
      const x = X(xn), y = Y(xn) + frontPx;
      ctx.fillRect(x - s * 0.035, y, s * 0.07, Math.max(0, waterY + s * 0.1 - y));
    }
    ctx.beginPath();
    for (let i = 0; i <= nb; i++) { const xn = xNear + (xs - xNear) * i / nb; const x = X(xn), y = Y(xn) - backPx; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
    for (let i = nb; i >= 0; i--) { const xn = xNear + (xs - xNear) * i / nb; ctx.lineTo(X(xn), Y(xn) + frontPx + s * 0.05); }
    ctx.closePath(); ctx.fillStyle = '#b8834c'; ctx.fill();
    ctx.strokeStyle = '#5a3a1e'; ctx.lineWidth = Math.max(1, s * 0.012); ctx.stroke();
    ctx.beginPath();
    for (let xn = Math.ceil(xNear / 0.018) * 0.018; xn < xs; xn += 0.018) { const x = X(xn); ctx.moveTo(x, Y(xn) - backPx); ctx.lineTo(x, Y(xn) + frontPx + s * 0.05); }
    ctx.stroke();
    ctx.restore();
  }
  // the grassy crest: a bright top face and a fringe of blades swaying along its front edge
  const n = Math.max(48, Math.ceil(Math.abs(A * (xFar - xs)) / 6));
  ctx.save();
  ctx.beginPath();
  for (let i = 0; i <= n; i++) { const xn = xs + (xFar - xs) * i / n; const x = X(xn), y = Y(xn) - backPx; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
  for (let i = n; i >= 0; i--) { const xn = xs + (xFar - xs) * i / n; ctx.lineTo(X(xn), Y(xn) + frontPx); }
  ctx.closePath();
  const top = Math.min(Y(xs), Y(xFar), Y(0.5)) - backPx;
  const gg = ctx.createLinearGradient(0, top, 0, top + (backPx + frontPx) * 3);
  gg.addColorStop(0, '#b9ec7c'); gg.addColorStop(1, '#8fd560');
  ctx.fillStyle = gg; ctx.fill();
  ctx.strokeStyle = 'rgba(40,90,30,0.55)'; ctx.lineWidth = Math.max(1, s * 0.015);
  ctx.beginPath();
  for (let i = 0; i <= n; i++) { const xn = xs + (xFar - xs) * i / n; const x = X(xn), y = Y(xn) + frontPx; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
  ctx.stroke();
  ctx.strokeStyle = '#4f9a3a'; ctx.lineWidth = Math.max(1, s * 0.014); ctx.lineCap = 'round';
  ctx.beginPath();
  const bstep = Math.max(5, s * 0.06), xA = Math.min(X(xs), X(xFar)), xB = Math.max(X(xs), X(xFar));
  for (let x = xA, j = 0; x <= xB; x += bstep, j++) {
    const xn = (x - B) / A, y = Y(xn) + frontPx, hh = s * (0.05 + rand(j * 1.7) * 0.06), sw = Math.sin(tA * 2 + j * 0.9) * s * 0.015;
    ctx.moveTo(x, y + s * 0.02); ctx.quadraticCurveTo(x + sw * 0.5, y - hh * 0.5, x + sw, y - hh);
  }
  ctx.stroke();
  ctx.restore();
  // the paradise garden beyond the Buyer: blossom trees, a warm glow, falling petals, butterflies
  const gx0 = 1.04;
  if (xFar > gx0) {
    const cx = X(1.18), cy = Y(1.18) - s * 0.9;
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    const rg = ctx.createRadialGradient(cx, cy, 0, cx, cy, s * 3.2);
    rg.addColorStop(0, 'rgba(255,220,150,0.30)'); rg.addColorStop(0.5, 'rgba(255,170,200,0.12)'); rg.addColorStop(1, 'rgba(255,170,200,0)');
    ctx.fillStyle = rg; ctx.fillRect(cx - s * 3.2, cy - s * 3.2, s * 6.4, s * 6.4);
    ctx.restore();
    const BL = ['#ffc2d9', '#ff9ec4', '#ffffff', '#ffd9e8'];
    for (let ti = 0; ti < 4; ti++) {
      const xn = gx0 + 0.04 + ti * 0.085; if (xn > xFar + 0.1) break;
      const x = X(xn), y = Y(xn) - backPx * 0.3, th = s * (0.95 + rand(ti * 3.7) * 0.5), cr = s * (0.42 + rand(ti * 1.9) * 0.18);
      ctx.save();
      ctx.strokeStyle = '#6b4526'; ctx.lineWidth = s * 0.09; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(x, y); ctx.quadraticCurveTo(x + s * 0.06, y - th * 0.5, x, y - th); ctx.stroke();
      ctx.lineWidth = s * 0.04; ctx.beginPath(); ctx.moveTo(x, y - th * 0.6); ctx.lineTo(x - s * 0.22, y - th * 0.85); ctx.moveTo(x, y - th * 0.7); ctx.lineTo(x + s * 0.2, y - th * 0.95); ctx.stroke();
      for (let q = 0; q < 16; q++) {
        const a = rand(ti * 11 + q * 1.3) * TAU, rr = cr * Math.sqrt(rand(ti * 7 + q * 2.1));
        const bx = x + Math.cos(a) * rr * 1.2, by = y - th - cr * 0.15 + Math.sin(a) * rr * 0.8;
        ctx.fillStyle = BL[q % 4]; ctx.beginPath(); ctx.arc(bx, by, cr * (0.32 + rand(q * 5.5 + ti) * 0.18), 0, TAU); ctx.fill();
      }
      ctx.restore();
    }
    ctx.save();
    for (let i = 0; i < 10; i++) {
      const ph = fract(tA * (0.06 + rand(i * 2.9) * 0.05) + rand(i * 8.1));
      const xn = gx0 + rand(i * 4.7) * 0.4, x = X(xn) + Math.sin(tA * 1.2 + i) * s * 0.25, y = Y(xn) - s * 1.6 + ph * s * 1.7;
      ctx.globalAlpha = 0.85 * (1 - ph * 0.6); ctx.fillStyle = '#ffd1e3';
      ctx.beginPath(); ctx.ellipse(x, y, s * 0.03, s * 0.018, tA * 2 + i, 0, TAU); ctx.fill();
    }
    ctx.globalAlpha = 1;
    for (let i = 0; i < 4; i++) {
      const xn = gx0 + 0.05 + rand(i * 6.3) * 0.3, x = X(xn) + Math.sin(tA * 0.7 + i * 2) * s * 0.5, y = Y(xn) - s * (0.6 + 0.4 * Math.sin(tA * 0.9 + i));
      const flap = Math.abs(Math.sin(tA * 12 + i * 3)), wv = s * 0.06;
      ctx.fillStyle = ['#ffd84d', '#9fd8ff', '#ff9ec4', '#c99bff'][i];
      ctx.beginPath(); ctx.ellipse(x - wv * 0.5 * flap, y, wv * 0.6 * flap + 1, wv * 0.5, 0, 0, TAU); ctx.ellipse(x + wv * 0.5 * flap, y, wv * 0.6 * flap + 1, wv * 0.5, 0, 0, TAU); ctx.fill();
    }
    ctx.restore();
  }
}

// ============================================================================================================ CHASM RIFT
// The barrel's Void Chasm torn on TOP of whatever stands there (the bank's iron pier covers x < 0, where every initial-stop gap lands):
// a crack that splits the pier and the street from their top surface down into the void, narrowing as it goes, purple-rimmed, with torn
// iron flaking into it. span = [xa, xb] in x_norm; opts.topAt(px) -> the top surface y at screen x (pier top / walking line);
// opts.bottom = the bottom y. Screen space, mirror-safe (the two ends are sorted after xToScreen).
function riftDraw(W, ctx, view, span, E, t, opts) {
  const tA = W._animT(E, t), s = view.s, h = view.h;
  let xL = view.xToScreen(Math.min(span[0], span[1])), xR = view.xToScreen(Math.max(span[0], span[1]));
  if (xL > xR) { const q = xL; xL = xR; xR = q; }
  if (!(xR - xL > 2)) return;
  const topAt = typeof opts.topAt === 'function' ? opts.topAt : () => view.groundY;
  const bottom = Number.isFinite(opts.bottom) ? opts.bottom : h + 40;
  const seed = (span[0] * 97.3 + span[1] * 13.1) % 50;
  const n = Math.max(6, Math.ceil((xR - xL) / 6));
  const T = [];                                                     // the jagged top edge (the torn surface)
  for (let i = 0; i <= n; i++) {
    const x = xL + (xR - xL) * i / n;
    const edge = Math.min(1, Math.min(i, n - i) / 3);
    T.push(x, topAt(x) + edge * (0.02 * s + (fbm(i * 0.37, seed) - 0.5) * 0.07 * s));
  }
  const L = [], R = [];                                             // the two cracked walls, narrowing toward the bottom
  const y0L = T[1], y0R = T[T.length - 1], depth = Math.max(1, bottom - Math.min(y0L, y0R));
  for (let v = 0; v <= 1.0001; v += 0.04) {
    const nar = (xR - xL) * 0.16 * v, zz = (Math.round(v * 25) & 1) ? 1 : -1;
    L.push(xL + nar + (fbm(v * 6.1, seed + 3) - 0.5) * 0.14 * s + zz * 0.016 * s, y0L + v * (bottom - y0L));
    R.push(xR - nar + (fbm(v * 6.1, seed + 9) - 0.5) * 0.14 * s - zz * 0.016 * s, y0R + v * (bottom - y0R));
  }
  const path = () => {
    ctx.beginPath();
    for (let i = 0; i < T.length; i += 2) { if (i === 0) ctx.moveTo(T[i], T[i + 1]); else ctx.lineTo(T[i], T[i + 1]); }
    for (let i = 0; i < R.length; i += 2) ctx.lineTo(R[i], R[i + 1]);
    for (let i = L.length - 2; i >= 0; i -= 2) ctx.lineTo(L[i], L[i + 1]);
    ctx.closePath();
  };
  ctx.save();
  // the void: purple glowing walls, black deep, a faint furnace far below
  path();
  const pulse = 0.75 + 0.25 * Math.sin(tA * 2.6 + seed);
  const vg = ctx.createLinearGradient(xL, 0, xR, 0);
  vg.addColorStop(0, css(RGB(P.neonPurple), 0.85 * pulse)); vg.addColorStop(0.1, css(RGB(P.voidEdge), 1)); vg.addColorStop(0.3, P.voidc);
  vg.addColorStop(0.7, P.voidc); vg.addColorStop(0.9, css(RGB(P.voidEdge), 1)); vg.addColorStop(1, css(RGB(P.neonPurple), 0.85 * pulse));
  ctx.fillStyle = vg; ctx.fill();
  const dg = ctx.createLinearGradient(0, Math.min(y0L, y0R), 0, bottom);
  dg.addColorStop(0, 'rgba(120,40,200,0.30)'); dg.addColorStop(0.35, 'rgba(0,0,0,0)'); dg.addColorStop(1, 'rgba(0,0,0,0.55)');
  ctx.fillStyle = dg; ctx.fill();
  ctx.save(); path(); ctx.clip();
  ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 22; i++) {                                    // motes sinking into nothing
    const ph = fract(tA * (0.08 + rand(i * 3.1 + seed) * 0.1) + rand(i * 7.7));
    const mx = xL + (xR - xL) * (0.12 + 0.76 * rand(i * 5.3 + seed)), my = Math.min(y0L, y0R) + ph * depth;
    ctx.fillStyle = `rgba(190,110,255,${(0.7 * (1 - ph)).toFixed(3)})`; ctx.fillRect(mx, my, Math.max(1.5, s * 0.025), Math.max(1.5, s * 0.025));
  }
  ctx.globalCompositeOperation = 'source-over';
  for (let i = 0; i < 7; i++) {                                     // torn iron and marble flakes tumbling down
    const ph = fract(tA * (0.18 + 0.12 * rand(i * 2.9 + seed)) + rand(i * 4.1 + seed));
    const fx = xL + (xR - xL) * (0.2 + 0.6 * rand(i * 6.7 + seed)) + Math.sin(tA * 2 + i) * s * 0.06;
    const fy = Math.min(y0L, y0R) + ph * depth * 0.9, sz = s * (0.04 + 0.05 * rand(i * 1.3 + seed)) * (1 - ph * 0.5);
    ctx.save(); ctx.translate(fx, fy); ctx.rotate(tA * (1.5 + i * 0.4) + i);
    ctx.globalAlpha = 1 - ph * 0.85;
    ctx.fillStyle = i % 3 === 0 ? '#e9e1cf' : i % 3 === 1 ? P.ironLight : P.brass;
    ctx.beginPath(); ctx.moveTo(-sz, -sz * 0.4); ctx.lineTo(sz * 0.8, -sz * 0.6); ctx.lineTo(sz, sz * 0.5); ctx.lineTo(-sz * 0.6, sz * 0.6); ctx.closePath(); ctx.fill();
    ctx.lineWidth = Math.max(1, s * 0.01); ctx.strokeStyle = P.ink; ctx.stroke();
    ctx.restore();
  }
  ctx.restore();
  // the torn rims: ink, a pale broken edge, the purple burn
  ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  const rims = [[T, false], [L, false], [R, false]];
  for (const [E2] of rims) {
    ctx.beginPath(); for (let i = 0; i < E2.length; i += 2) { if (i === 0) ctx.moveTo(E2[i], E2[i + 1]); else ctx.lineTo(E2[i], E2[i + 1]); }
    ctx.strokeStyle = P.ink; ctx.lineWidth = Math.max(3, s * 0.06); ctx.stroke();
    ctx.strokeStyle = 'rgba(246,239,220,0.95)'; ctx.lineWidth = Math.max(2, s * 0.032); ctx.stroke();
    ctx.strokeStyle = 'rgba(180,77,255,0.85)'; ctx.lineWidth = Math.max(1.5, s * 0.016); ctx.stroke();
  }
  ctx.globalCompositeOperation = 'lighter';
  ctx.strokeStyle = css(RGB(P.neonPurple), 0.35 * pulse); ctx.lineWidth = Math.max(4, s * 0.12);
  ctx.beginPath(); for (let i = 0; i < T.length; i += 2) { if (i === 0) ctx.moveTo(T[i], T[i + 1]); else ctx.lineTo(T[i], T[i + 1]); } ctx.stroke();
  ctx.restore();
}

// ============================================================================================================ SPREAD PIT
// A cutaway trench in the street at the bank door, filled with bubbling black molasses; its depth is pit.depth (0..1 -> 0..0.62 units).
// drawPit has no terrain argument: it uses the terrain of this world's last drawTerrain call (same frame), so the trench sits on the street.
function pitGeom(W, view, pit) {
  const prof = getProfile(W, W._lastTerrain), k = tanTilt(view), s = view.s;
  let xa = view.xToScreen(Math.min(pit.x0, pit.x1)), xb = view.xToScreen(Math.max(pit.x0, pit.x1));
  if (xa > xb) { const q = xa; xa = xb; xb = q; }
  const ww = xb - xa;
  const D = clamp(+pit.depth || 0, 0, 1) * 0.62 * s;
  const aff = viewAffine(view, W._aff), A = aff[0], B = aff[1];
  return { prof, k, s, xa, xb, ww, D, A, B };
}
function pitDraw(W, ctx, view, pit, E, t, front) {
  if (!Number.isFinite(+pit.x0) || !Number.isFinite(+pit.x1)) return;
  const tA = W._animT(E, t);
  const G = pitGeom(W, view, pit);
  const { prof, k, s, xa, xb, ww, D, A, B } = G;
  if (ww < 3 || xb < -s || xa > view.w + s) return;
  const backPx = GROUND.back * s, frontPx = GROUND.front * s;
  const Dp = Math.max(s * 0.08, D);
  const n = Math.max(6, Math.ceil(ww / 3));
  const yw = (x) => walkY(view, prof, (x - B) / A, k);
  const xc = (xa + xb) / 2;
  const slosh = clamp((W._tiltRate || 0) * 2, -1, 1);
  // the vat is level in the street's frame: its liquid sits at the lower rim, its floor is flat, the tilt shears both
  const px0 = Number.isFinite(view.pivotX) ? view.pivotX : view.w / 2;
  const hMin = Math.min(heightAt(prof, (xa - B) / A), heightAt(prof, (xb - B) / A));
  const base = (x) => view.groundY - hMin * s + (x - px0) * k;
  const ywc = base(xc);
  const yb = (x) => base(x) + frontPx + Dp;
  const rc = Math.min(Dp * 0.55, ww * 0.3);
  const ySurf = (x) => { const u = (x - xa) / ww; return ywc + (base(x) - ywc) * 0.62 + s * 0.04 + Math.sin(u * 9 + tA * 2.2) * s * 0.007 + slosh * (u - 0.5) * s * 0.12 * Math.sin(tA * 6); };
  const vat = new Path2D();
  vat.moveTo(xa, yw(xa) - backPx); vat.lineTo(xa, yb(xa) - rc); vat.quadraticCurveTo(xa, yb(xa), xa + rc, yb(xa + rc));
  vat.lineTo(xb - rc, yb(xb - rc)); vat.quadraticCurveTo(xb, yb(xb), xb, yb(xb) - rc); vat.lineTo(xb, yw(xb) - backPx);
  for (let i = n; i >= 0; i--) { const x = xa + ww * i / n; vat.lineTo(x, yw(x) - backPx); }
  vat.closePath();
  ctx.save();
  if (!front) {
    ctx.fillStyle = '#140a04'; ctx.fill(vat);                     // the dark inside of the vat
  }
  ctx.clip(vat);
  if (!front) {      // tide marks on the back wall: how high the molasses has been
    ctx.strokeStyle = 'rgba(160,102,47,0.25)'; ctx.lineWidth = Math.max(1, s * 0.01);
    for (let q = 1; q <= 3; q++) { ctx.beginPath(); ctx.moveTo(xa, yw(xa) - backPx * (1 - q * 0.22)); ctx.lineTo(xb, yw(xb) - backPx * (1 - q * 0.22)); ctx.stroke(); }
  }
  // molasses body (cutaway): glossy brown at the surface, black at the floor
  const body = new Path2D();
  body.moveTo(xa, ySurf(xa));
  for (let i = 0; i <= n; i++) { const x = xa + ww * i / n; body.lineTo(x, ySurf(x)); }
  body.lineTo(xb, yb(xb) + s); body.lineTo(xa, yb(xa) + s); body.closePath();
  const mg = ctx.createLinearGradient(0, ywc, 0, ywc + frontPx + Dp);
  mg.addColorStop(0, '#4a2810'); mg.addColorStop(0.2, '#24120a'); mg.addColorStop(1, '#060302');
  ctx.fillStyle = mg; ctx.fill(body);
  // the surface skin seen from above
  const skin = new Path2D();
  for (let i = 0; i <= n; i++) { const x = xa + ww * i / n; if (i === 0) skin.moveTo(x, ySurf(x) - backPx * 0.8); else skin.lineTo(x, ySurf(x) - backPx * 0.8); }
  for (let i = n; i >= 0; i--) { const x = xa + ww * i / n; skin.lineTo(x, ySurf(x) + 1); }
  skin.closePath();
  const sg = ctx.createLinearGradient(0, ywc - backPx, 0, ywc + s * 0.04);
  sg.addColorStop(0, '#120804'); sg.addColorStop(0.55, '#2c170a'); sg.addColorStop(1, '#5a3214');
  ctx.fillStyle = sg; ctx.fill(skin);
  ctx.strokeStyle = 'rgba(255,226,186,0.75)'; ctx.lineWidth = Math.max(1.2, s * 0.022); ctx.lineCap = 'round';
  ctx.beginPath();
  const g0 = 0.14 + 0.05 * Math.sin(tA * 0.7), g1 = 0.46 + 0.05 * Math.sin(tA * 0.9);
  for (let i = 0; i <= 12; i++) { const u = lerp(g0, g1, i / 12), x = xa + ww * u; const y = ySurf(x) - backPx * 0.45; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
  ctx.stroke();
  ctx.strokeStyle = 'rgba(255,214,160,0.3)'; ctx.lineWidth = Math.max(1, s * 0.01);
  ctx.beginPath(); for (let i = 0; i <= 8; i++) { const u = lerp(0.6, 0.82, i / 8), x = xa + ww * u; const y = ySurf(x) - backPx * 0.3; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); } ctx.stroke();
  ctx.fillStyle = P.molassesFoam;
  for (const side of [0, 1]) {
    for (let i = 0; i < 4; i++) {
      const u = side ? 1 - 0.035 - i * 0.03 : 0.035 + i * 0.03, x = xa + ww * u;
      ctx.beginPath(); ctx.arc(x, ySurf(x) - backPx * (0.2 + 0.3 * rand(i + side * 5)), Math.max(1, s * (0.024 - i * 0.004)), 0, TAU); ctx.fill();
    }
  }
  // bubbles: grow, wobble, pop (stateless)
  const nb = 3 + Math.floor(ww / (s * 0.26));
  for (let i = 0; i < nb; i++) {
    const per = 1.6 + rand(i * 3.7) * 2.4, ph = fract(tA / per + rand(i * 1.3));
    const x = xa + ww * (0.12 + 0.76 * rand(i * 5.1)), y = ySurf(x) - backPx * (0.15 + 0.5 * rand(i * 2.9));
    if (ph < 0.82) {
      const r = s * (0.035 + 0.06 * rand(i * 7.7)) * ease(ph / 0.82);
      ctx.fillStyle = '#1c0e06'; ctx.beginPath(); ctx.arc(x, y - r * 0.4, r, Math.PI, 0); ctx.closePath(); ctx.fill();
      ctx.lineWidth = Math.max(0.8, s * 0.01); ctx.strokeStyle = P.ink; ctx.stroke();
      ctx.strokeStyle = 'rgba(255,214,160,0.55)'; ctx.lineWidth = Math.max(0.8, s * 0.008); ctx.beginPath(); ctx.arc(x, y - r * 0.4, r * 0.8, Math.PI * 1.1, Math.PI * 1.6); ctx.stroke();
      ctx.fillStyle = 'rgba(255,230,190,0.95)'; ctx.beginPath(); ctx.arc(x - r * 0.35, y - r * 0.9, Math.max(0.9, r * 0.2), 0, TAU); ctx.fill();
    } else {
      const q = (ph - 0.82) / 0.18, r = s * (0.03 + 0.06 * rand(i * 7.7)) * (0.6 + q);
      ctx.strokeStyle = `rgba(160,102,47,${(0.9 * (1 - q)).toFixed(3)})`; ctx.lineWidth = Math.max(0.8, s * 0.012);
      ctx.beginPath(); ctx.ellipse(x, y, r, r * 0.35, 0, 0, TAU); ctx.stroke();
      for (let d = 0; d < 3; d++) { ctx.fillStyle = `rgba(42,22,11,${(1 - q).toFixed(3)})`; ctx.beginPath(); ctx.arc(x + (d - 1) * r * 0.8, y - q * s * 0.12 * (1 + (d === 1)), Math.max(0.8, s * 0.012), 0, TAU); ctx.fill(); }
    }
  }
  for (let i = 0; i < 5; i++) {        // trapped bubbles drifting up in the cutaway
    const ph = fract(tA * 0.16 + rand(i * 9.1)), x = xa + ww * (0.15 + 0.7 * rand(i * 4.4));
    const y = lerp(yb(x) - s * 0.04, ySurf(x) + s * 0.03, ph);
    ctx.strokeStyle = 'rgba(160,102,47,0.6)'; ctx.lineWidth = Math.max(0.8, s * 0.008);
    ctx.beginPath(); ctx.arc(x + Math.sin(tA * 2 + i) * s * 0.01, y, Math.max(1, s * 0.016), 0, TAU); ctx.stroke();
  }
  ctx.restore();
  if (front) return;
  // the riveted brass frame of the vat (walls + floor), lips on the top face, molasses oozing over the lips
  const frame = new Path2D();
  frame.moveTo(xa, yw(xa) - backPx * 0.55); frame.lineTo(xa, yb(xa) - rc); frame.quadraticCurveTo(xa, yb(xa), xa + rc, yb(xa + rc));
  frame.lineTo(xb - rc, yb(xb - rc)); frame.quadraticCurveTo(xb, yb(xb), xb, yb(xb) - rc); frame.lineTo(xb, yw(xb) - backPx * 0.55);
  const rimW = Math.max(2.5, s * 0.055);
  ctx.save();
  ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  ctx.strokeStyle = P.ink; ctx.lineWidth = rimW + 2 * Math.max(1, s * LINE.ink * 0.7); ctx.stroke(frame);
  ctx.strokeStyle = P.brass; ctx.lineWidth = rimW; ctx.stroke(frame);
  ctx.strokeStyle = 'rgba(255,242,176,0.8)'; ctx.lineWidth = Math.max(1, rimW * 0.25); ctx.stroke(frame);
  const riv = (x, y) => { const r = Math.max(1, s * 0.016); ctx.fillStyle = P.brassDark; ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill(); ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.beginPath(); ctx.arc(x - r * 0.3, y - r * 0.3, r * 0.4, 0, TAU); ctx.fill(); };
  for (const xw of [xa, xb]) { const y0 = yw(xw) - backPx * 0.2, y1 = yb(xw) - rc; for (let y = y0; y < y1; y += s * 0.14) riv(xw, y); }
  for (let x = xa + rc; x < xb - rc; x += s * 0.2) riv(x, yb(x));
  for (const [xw, dir] of [[xa, -1], [xb, 1]]) {          // lips
    const y = yw(xw) - backPx * 0.7, lw = rimW * 1.8;
    ctx.fillStyle = P.brass; ctx.beginPath(); ctx.rect(dir < 0 ? xw - lw : xw - rimW * 0.4, y, lw + rimW * 0.4, backPx * 0.55); ctx.fill();
    ctx.lineWidth = Math.max(1, s * LINE.inkThin); ctx.strokeStyle = P.ink; ctx.stroke();
    // molasses oozing over the lip
    const len = s * (0.04 + 0.06 * (0.5 + 0.5 * Math.sin(tA * 0.8 + xw * 0.01))), bx = xw + dir * rimW * 0.4, r = Math.max(1.5, s * 0.028);
    ctx.fillStyle = P.molasses; ctx.beginPath(); ctx.moveTo(bx - r, y); ctx.lineTo(bx + r, y); ctx.lineTo(bx + r * 0.6, y + len); ctx.arc(bx, y + len, r * 0.6, 0, Math.PI); ctx.closePath(); ctx.fill();
    ctx.fillStyle = 'rgba(255,214,160,0.55)'; ctx.fillRect(bx - r * 0.5, y + 1, Math.max(1, r * 0.3), len * 0.7);
  }
  ctx.restore();
}

// ============================================================================================================ FOG (beyond the buyer)
function fogColors(W, E) {
  const kind = (W._skyC && W._skyC.kind) || (E.weather === 'storm' ? 'storm' : E.weather === 'dead' ? 'dead' : E.night ? 'night' : 'calm');
  switch (kind) {
    case 'storm': return [RGB('#2b2140'), 0.9];
    case 'dead': return [RGB('#bea887'), 0.93];
    case 'night': return [RGB('#2a3453'), 0.86];
    case 'golden': return [RGB('#ffc489'), 0.78];
    case 'active': return [RGB('#ffdcb0'), 0.66];   // an active market thins the fog
    default: return [RGB('#f1e9d6'), 0.82];
  }
}
function fogDraw(W, ctx, view, fromXn, E, t) {
  const tA = W._animT(E, t);
  const [fc, dens] = fogColors(W, E);
  const x0 = view.xToScreen(fromXn), x1 = view.xToScreen(fromXn + 0.1);
  const dir = x1 >= x0 ? 1 : -1, span = Math.abs(x1 - x0) * 1.6, s = view.s, w = view.w, h = view.h;
  const edge = dir > 0 ? w + 20 : -20;
  if ((dir > 0 && x0 > w + 10) || (dir < 0 && x0 < -10)) return;
  ctx.save();
  const g = ctx.createLinearGradient(x0, 0, x0 + dir * span, 0);
  g.addColorStop(0, css(fc, 0)); g.addColorStop(0.55, css(fc, dens * 0.7)); g.addColorStop(1, css(fc, dens));
  ctx.fillStyle = g;
  ctx.fillRect(Math.min(x0, edge), 0, Math.abs(edge - x0), h);
  // billowing puffs along the front, denser near the ground
  const key = qkey(fc);
  if (!W._fogPuff || W._fogPuff.key !== key || W._fogPuff.r !== Math.round(s * 0.9)) W._fogPuff = { key, r: Math.round(s * 0.9), c: softBlob(Math.round(s * 0.9), fc) };
  const pc = W._fogPuff.c;
  for (let i = 0; i < 14; i++) {
    const depth = rand(i * 3.3), r = s * (0.8 + 1.3 * rand(i * 5.1)) * (1 + 0.08 * Math.sin(tA * 0.4 + i));
    const x = x0 + dir * (depth * span * 1.1 + Math.sin(tA * 0.13 + i * 1.7) * s * 0.25);
    const y = h * (0.12 + 0.82 * Math.pow(rand(i * 7.9), 0.6)) + Math.sin(tA * 0.2 + i) * s * 0.1;
    ctx.globalAlpha = dens * (0.35 + 0.5 * depth);
    ctx.drawImage(pc, x - r, y - r, r * 2, r * 2);
  }
  ctx.globalAlpha = 1;
  // glints of gold teasing from inside the fog (prices nobody has been to yet)
  ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 7; i++) {
    const tw = Math.max(0, Math.sin(tA * (0.9 + rand(i) * 1.3) + i * 4.1));
    if (tw < 0.2) continue;
    const x = x0 + dir * span * (0.5 + 1.2 * rand(i * 2.7)), y = h * (0.2 + 0.6 * rand(i * 6.3)), r = s * 0.07 * tw;
    ctx.fillStyle = `rgba(255,214,110,${(0.6 * tw * dens).toFixed(3)})`;
    ctx.beginPath(); ctx.moveTo(x, y - r * 2); ctx.lineTo(x + r * 0.35, y); ctx.lineTo(x, y + r * 2); ctx.lineTo(x - r * 0.35, y); ctx.closePath(); ctx.fill();
    ctx.beginPath(); ctx.moveTo(x - r * 2, y); ctx.lineTo(x, y + r * 0.35); ctx.lineTo(x + r * 2, y); ctx.lineTo(x, y - r * 0.35); ctx.closePath(); ctx.fill();
  }
  ctx.restore();
}

// ============================================================================================================ SEASON BAND
// The quiet strip at the very top: a brass rail with a recessed channel; autumn leaves blow toward the Buyer when the day's trend favours
// the player's side, snow drifts toward the Bank when it does not. Stateless (a function of time), so it costs nothing to keep.
function leafSprites(W, sz) {
  sz = Math.max(6, Math.round(sz));
  if (W._leaves && W._leaves.sz === sz) return W._leaves;
  const cols = [P.leaf, '#c2412d', '#e2b13c', '#b5651d'], list = [];
  cols.forEach((col, ci) => {
    const c = makeCanvas(sz * 2, sz * 2), g = c.getContext('2d'), r = sz * 0.85;
    g.translate(sz, sz); g.rotate(0.5);
    g.beginPath();
    if (ci % 2 === 0) {        // almond leaf
      g.moveTo(0, -r); g.quadraticCurveTo(r * 0.8, -r * 0.15, 0, r * 0.75); g.quadraticCurveTo(-r * 0.8, -r * 0.15, 0, -r);
    } else {                   // lobed (oak-like) leaf
      const pts = 9;
      for (let i = 0; i <= pts * 2; i++) {
        const u = i / (pts * 2), y = -r + u * r * 1.7, side = i <= pts ? 1 : -1, v = i <= pts ? u * 2 : (1 - u) * 2;
        const wid = r * 0.55 * Math.sin(Math.PI * Math.min(1, v)) * (i % 2 ? 0.62 : 1);
        const yy = i <= pts ? -r + v * r * 1.7 : -r + v * r * 1.7;
        if (i === 0) g.moveTo(0, -r); else g.lineTo(side * wid, yy);
      }
      g.closePath();
    }
    g.fillStyle = col; g.fill();
    g.lineWidth = Math.max(1, sz * 0.08); g.strokeStyle = 'rgba(26,20,16,0.75)'; g.stroke();
    g.strokeStyle = 'rgba(255,232,190,0.7)'; g.lineWidth = Math.max(0.7, sz * 0.055);
    g.beginPath(); g.moveTo(0, r * 0.95); g.lineTo(0, -r * 0.7);
    for (let q = 0; q < 3; q++) { const y = -r * 0.4 + q * r * 0.35; g.moveTo(0, y + r * 0.15); g.lineTo(r * 0.28, y - r * 0.05); g.moveTo(0, y + r * 0.15); g.lineTo(-r * 0.28, y - r * 0.05); }
    g.stroke();
    g.strokeStyle = 'rgba(90,50,20,0.9)'; g.lineWidth = Math.max(1, sz * 0.07); g.beginPath(); g.moveTo(0, r * 0.7); g.lineTo(r * 0.06, r * 1.05); g.stroke();
    list.push(c);
  });
  const fl = makeCanvas(sz, sz), fg = fl.getContext('2d');
  const gr = fg.createRadialGradient(sz / 2, sz / 2, 0, sz / 2, sz / 2, sz / 2);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.5, 'rgba(244,248,255,0.85)'); gr.addColorStop(1, 'rgba(244,248,255,0)');
  fg.fillStyle = gr; fg.fillRect(0, 0, sz, sz);
  W._leaves = { sz, list, flake: fl };
  return W._leaves;
}
function seasonDraw(W, ctx, w, E, t) {
  const tA = W._animT(E, t);
  const bh = clamp(Math.round(w * 0.018), 12, 30);
  const se = E.season, mag = Math.abs(se), dirBuyer = E.mirror ? -1 : 1;
  ctx.save();
  const g = ctx.createLinearGradient(0, 0, 0, bh);
  g.addColorStop(0, 'rgba(20,14,10,0.42)'); g.addColorStop(1, 'rgba(20,14,10,0.16)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, bh);
  // particles
  if (mag > 0.05) {
    const L = leafSprites(W, bh * 0.42);
    const n = Math.round(3 + 22 * mag), spd = (24 + 80 * mag) * (w / 1600);
    for (let i = 0; i < n; i++) {
      const r1 = rand(i * 3.71 + 0.2), r2 = rand(i * 1.93 + 0.7);
      if (se > 0) {
        const x = wrap(r1 * (w + 60) + dirBuyer * spd * (0.7 + 0.6 * r2) * tA, w + 60) - 30;
        const y = bh * (0.5 + 0.28 * Math.sin(tA * (1.4 + r2) + i * 2.3));
        const sp = L.list[i % L.list.length], sz = sp.width * (0.7 + 0.5 * r2);
        ctx.save(); ctx.translate(x, y); ctx.rotate(tA * (2 + 3 * r2) * dirBuyer + i); ctx.scale(Math.cos(tA * (3 + r2 * 2) + i), 1);
        ctx.globalAlpha = 0.95; ctx.drawImage(sp, -sz / 2, -sz / 2, sz, sz); ctx.restore();
      } else {
        const x = wrap(r1 * (w + 40) - dirBuyer * spd * 0.6 * (0.6 + 0.6 * r2) * tA + Math.sin(tA * 0.8 + i) * 8, w + 40) - 20;
        const y = bh * (0.25 + 0.6 * fract(r2 + tA * 0.05 * (0.5 + r1)));
        const sz = bh * (0.18 + 0.22 * r2);
        ctx.globalAlpha = 0.9; ctx.drawImage(L.flake, x - sz / 2, y - sz / 2, sz, sz);
      }
    }
    ctx.globalAlpha = 1;
    if (se < -0.35) {     // snow settling on the rail
      ctx.fillStyle = 'rgba(244,248,255,0.9)';
      for (let x = 0; x < w; x += bh * 0.7) { const hh = bh * 0.12 * (0.6 + 0.4 * Math.sin(x * 0.07)); ctx.beginPath(); ctx.ellipse(x, bh - 1, bh * 0.45, hh, 0, Math.PI, 0); ctx.fill(); }
    }
  }
  // the brass rail (deco moulding) with rivets
  ctx.fillStyle = P.brassDark; ctx.fillRect(0, bh - 1, w, 4);
  ctx.fillStyle = P.brass; ctx.fillRect(0, bh, w, 2);
  ctx.fillStyle = P.goldHot; ctx.fillRect(0, bh, w, 1);
  ctx.fillStyle = P.ink; ctx.fillRect(0, bh + 3, w, 1);
  for (let x = 40; x < w; x += 140) {
    ctx.fillStyle = P.rivet; ctx.beginPath(); ctx.arc(x, bh + 1, 1.8, 0, TAU); ctx.fill();
    ctx.fillStyle = P.goldDeep; ctx.beginPath(); ctx.moveTo(x + 50, bh - 1); ctx.lineTo(x + 56, bh - 5); ctx.lineTo(x + 62, bh - 1); ctx.fill();
  }
  ctx.restore();
}

// ============================================================================================================ WEATHER
// Pooled particles in typed arrays (allocated once): ash (dead), ticker tape rain + tape stuck to the glass + lightning (storm),
// warm motes (calm / active), ledger pages tumbling in the wind (active / storm). Global mood washes: storm darkens, dead goes sepia.
// set ctx to (caller matrix m) x [a b c d e f]
function setXf(ctx, m, a, b, c, d, e, f) {
  ctx.setTransform(m.a * a + m.c * b, m.b * a + m.d * b, m.a * c + m.c * d, m.b * c + m.d * d, m.a * e + m.c * f + m.e, m.b * e + m.d * f + m.f);
}
function initWeatherPools(W) {
  const F = (n) => new Float32Array(n);
  W._ash = { n: 240, x: F(240), y: F(240), vx: F(240), vy: F(240), rot: F(240), vr: F(240), sz: F(240), v: F(240) };
  W._tape = { n: 180, x: F(180), y: F(180), vx: F(180), vy: F(180), rot: F(180), vr: F(180), sz: F(180), v: F(180) };
  W._stuck = { n: 12, x: F(12), y: F(12), rot: F(12), sz: F(12), v: F(12), life: F(12), max: F(12), i: 0 };
  W._mote = { n: 80, x: F(80), y: F(80), vx: F(80), vy: F(80), ph: F(80), sz: F(80) };
  W._bolt = { main: F(2 * 33), br: F(2 * 17 * 3), nbr: 0, life: 0, max: 0.5, x: 0, y: 0 };   // segment counts must be powers of two
  W._wx = { kind: null, wh: '', flash: 0, nextStrike: 0, prevLightning: false };
}
function weatherSprites(W, s) {
  const key = Math.round(s);
  if (W._wxs && W._wxs.key === key) return W._wxs;
  const X = { key, ash: [], tape: [] };
  for (let i = 0; i < 5; i++) {
    const r = Math.max(3, s * (0.035 + 0.02 * rand(i))), c = makeCanvas(r * 2 + 2, r * 2 + 2), g = c.getContext('2d');
    g.translate(r + 1, r + 1); g.beginPath();
    for (let j = 0; j < 6; j++) { const a = j / 6 * TAU + rand(i * 7 + j), q = r * (0.45 + 0.55 * rand(i * 3 + j)); if (j === 0) g.moveTo(Math.cos(a) * q, Math.sin(a) * q * 0.7); else g.lineTo(Math.cos(a) * q, Math.sin(a) * q * 0.7); }
    g.closePath(); g.fillStyle = ['#bdb6a8', '#9c958a', '#d4cec2', '#7e786f', '#c9bfae'][i]; g.fill();
    X.ash.push(c);
  }
  for (let i = 0; i < 6; i++) {    // ticker tape: off-white paper strip printed with abstract glyph marks (no readable numbers)
    const L = Math.round(s * (0.42 + 0.25 * rand(i * 2.2))), Hh = Math.max(4, Math.round(s * 0.075)), c = makeCanvas(L + 2, Hh + 2), g = c.getContext('2d');
    g.fillStyle = P.ticker; g.fillRect(1, 1, L, Hh);
    g.fillStyle = 'rgba(160,150,120,0.35)'; g.fillRect(1, 1 + Hh * 0.8, L, Hh * 0.2);
    g.fillStyle = 'rgba(30,30,40,0.75)';
    let x = 3;
    while (x < L - 4) {
      const kind = rand(i * 31 + x);
      if (kind < 0.6) { g.fillRect(x, 1 + Hh * 0.28, Math.max(1, s * 0.012), Hh * 0.42); x += s * 0.03; }
      else if (kind < 0.8) { g.beginPath(); g.moveTo(x, 1 + Hh * 0.7); g.lineTo(x + Hh * 0.25, 1 + Hh * 0.25); g.lineTo(x + Hh * 0.5, 1 + Hh * 0.7); g.fillStyle = rand(x) < 0.5 ? 'rgba(30,140,80,0.85)' : 'rgba(200,40,50,0.85)'; g.fill(); g.fillStyle = 'rgba(30,30,40,0.75)'; x += Hh * 0.7; }
      else x += s * 0.05;
    }
    g.strokeStyle = 'rgba(26,20,16,0.35)'; g.lineWidth = 1; g.strokeRect(1, 1, L, Hh);
    X.tape.push(c);
  }
  X.mote = softBlob(Math.max(3, Math.round(s * 0.05)), [255, 220, 140]);
  {   // a ledger page tumbling in the wind
    const pw = Math.round(s * 0.34), ph = Math.round(s * 0.44), c = makeCanvas(pw + 4, ph + 4), g = c.getContext('2d');
    g.fillStyle = P.ledger; g.fillRect(2, 2, pw, ph);
    g.strokeStyle = 'rgba(159,182,201,0.9)'; g.lineWidth = 1;
    for (let y = 2 + ph * 0.15; y < ph; y += ph * 0.1) { g.beginPath(); g.moveTo(2, y); g.lineTo(2 + pw, y); g.stroke(); }
    g.strokeStyle = 'rgba(224,48,58,0.7)'; g.beginPath(); g.moveTo(2 + pw * 0.18, 2); g.lineTo(2 + pw * 0.18, 2 + ph); g.stroke();
    g.fillStyle = 'rgba(40,40,60,0.6)';
    for (let y = 2 + ph * 0.18; y < ph; y += ph * 0.1) g.fillRect(2 + pw * 0.25, y - 3, pw * (0.2 + 0.5 * rand(y)), 1.5);
    g.strokeStyle = P.ink; g.lineWidth = Math.max(1, s * LINE.inkThin); g.strokeRect(2, 2, pw, ph);
    X.page = c;
  }
  X.bulb = softBlob(Math.max(4, Math.round(s * 0.09)), [255, 236, 170]);
  W._wxs = X;
  return X;
}
function respawnAsh(A, i, w, h, any) {
  A.x[i] = Math.random() * (w + 80) - 40; A.y[i] = any ? Math.random() * h : -10 - Math.random() * 40;
  A.vx[i] = (Math.random() - 0.5) * 12; A.vy[i] = 18 + Math.random() * 30; A.rot[i] = Math.random() * TAU; A.vr[i] = (Math.random() - 0.5) * 2;
  A.sz[i] = 0.6 + Math.random() * 0.9; A.v[i] = (Math.random() * 5) | 0;
}
function respawnTape(T, i, w, h, any, wind) {
  T.x[i] = Math.random() * (w + 300) - 150 - wind * 120; T.y[i] = any ? Math.random() * h : -20 - Math.random() * 120;
  T.vx[i] = wind * (120 + Math.random() * 120); T.vy[i] = 420 + Math.random() * 380; T.rot[i] = Math.random() * TAU; T.vr[i] = (Math.random() - 0.5) * 9;
  T.sz[i] = 0.5 + Math.random() * 0.45; T.v[i] = (Math.random() * 6) | 0;
}
function respawnMote(M, i, w, h) {
  M.x[i] = Math.random() * w; M.y[i] = Math.random() * h * 0.85; M.vx[i] = (Math.random() - 0.5) * 10; M.vy[i] = (Math.random() - 0.5) * 6;
  M.ph[i] = Math.random() * TAU; M.sz[i] = 0.5 + Math.random();
}
function boltLine(arr, n, x0, y0, x1, y1, rough) {
  arr[0] = x0; arr[1] = y0; arr[2 * n] = x1; arr[2 * n + 1] = y1;
  for (let step = n; step > 1; step >>= 1) {
    for (let i = 0; i < n; i += step) {
      const a = i, b = i + step, m = (a + b) >> 1;
      const len = Math.hypot(arr[2 * b] - arr[2 * a], arr[2 * b + 1] - arr[2 * a + 1]);
      arr[2 * m] = (arr[2 * a] + arr[2 * b]) / 2 + (Math.random() - 0.5) * len * rough;
      arr[2 * m + 1] = (arr[2 * a + 1] + arr[2 * b + 1]) / 2 + (Math.random() - 0.5) * len * rough * 0.3;
    }
  }
}
const BOLT_COLS = ['rgba(180,77,255,0.22)', 'rgba(200,120,255,0.65)', 'rgba(255,245,255,0.95)'];
function strike(W, w, h) {
  const B = W._bolt, v = W._lastView, tr = W._lastTerrain;
  let gx = w * (0.12 + 0.76 * Math.random()), gy = 0.72 * h;
  if (v && v.w === w) {
    const xn = W.screenToXn(v, gx);
    gy = walkY(v, getProfile(W, tr), xn, tanTilt(v)) - GROUND.back * v.s * 0.5;
  }
  const sx = gx + (Math.random() - 0.5) * w * 0.3;
  boltLine(B.main, 32, sx, -10, gx, gy, 0.55);
  B.nbr = 3;
  for (let k = 0; k < 3; k++) {
    const at = 6 + ((Math.random() * 18) | 0), bx = B.main[2 * at], by = B.main[2 * at + 1];
    const tmp = B.br.subarray(k * 34, k * 34 + 34);
    boltLine(tmp, 16, bx, by, bx + (Math.random() - 0.5) * h * 0.4, by + h * (0.12 + Math.random() * 0.18), 0.6);
  }
  B.life = B.max = 0.5; B.x = gx; B.y = gy;
  W._wx.flash = 1;
  if (W._spk) for (let q = 0; q < 26; q++) emitSpark(W, gx, gy, (Math.random() - 0.5) * h * 0.9, -Math.random() * h * 0.6);
}
function weatherDraw(W, ctx, w, h, E, dt, t) {
  const tA = W._animT(E, t);
  const m0 = ctx.getTransform();          // compose with the caller's transform (shake, DPR)
  if (E.freeze) dt = 0;
  const s = W._lastView ? W._lastView.s : h / 9.5;
  const X = weatherSprites(W, s), WX = W._wx;
  const kind = E.weather, wind = (E.season < -0.05 ? -1 : 1) * (E.mirror ? -1 : 1) * (0.4 + E.vol);
  const prewarm = WX.kind !== kind || WX.wh !== w + 'x' + h;
  WX.kind = kind; WX.wh = w + 'x' + h;
  const sc = w / 1600;
  // ---- global mood washes
  if (kind === 'storm') {
    ctx.save(); ctx.globalCompositeOperation = 'multiply'; ctx.fillStyle = 'rgb(160,165,180)'; ctx.fillRect(0, 0, w, h); ctx.restore();
  } else if (kind === 'dead') {
    ctx.save();
    ctx.globalCompositeOperation = 'color'; ctx.globalAlpha = 0.45; ctx.fillStyle = P.sepia; ctx.fillRect(0, 0, w, h);
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
    ctx.fillStyle = 'rgba(190,165,125,0.16)'; ctx.fillRect(0, 0, w, h);
    const gy = W._horizonY && W._horizonH === h ? W._horizonY : 0.72 * h;
    const fg = ctx.createLinearGradient(0, gy - 0.18 * h, 0, gy + 0.12 * h);
    fg.addColorStop(0, 'rgba(200,178,140,0)'); fg.addColorStop(0.55, 'rgba(204,182,146,0.38)'); fg.addColorStop(1, 'rgba(200,178,140,0)');
    ctx.fillStyle = fg; ctx.fillRect(0, gy - 0.18 * h, w, 0.3 * h);
    ctx.restore();
  }
  // ---- ash (dead market)
  if (kind === 'dead') {
    const A = W._ash, n = Math.round(A.n * (0.55 + 0.45 * (1 - E.vol)));
    if (prewarm) for (let i = 0; i < A.n; i++) respawnAsh(A, i, w, h, true);
    for (let i = 0; i < n; i++) {
      A.x[i] += (A.vx[i] + wind * 14 + Math.sin(tA * 0.9 + i) * 10) * dt * sc; A.y[i] += A.vy[i] * dt * sc; A.rot[i] += A.vr[i] * dt;
      if (A.y[i] > h + 10 || A.x[i] < -50 || A.x[i] > w + 50) respawnAsh(A, i, w, h, false);
      const sp = X.ash[A.v[i]], z = A.sz[i] * sc * 1.2;
      const c = Math.cos(A.rot[i]) * z, sn = Math.sin(A.rot[i]) * z;
      setXf(ctx, m0, c, sn, -sn, c, A.x[i], A.y[i]);
      ctx.globalAlpha = 0.85; ctx.drawImage(sp, -sp.width / 2, -sp.height / 2);
    }
    ctx.setTransform(m0); ctx.globalAlpha = 1;
  }
  // ---- rain (Zee 2026-11-04: "why is it raining flying papers.. it can be natural rain drops (very very realistic)"): thin slanted
  // streaks in three depths, faster and brighter up close, each ending in a small splash ring on the ground. Storm = a downpour, active =
  // a drizzle, calm / dead = dry.
  if (kind === 'storm' || kind === 'active') {
    const NR = 520;
    const R = W._rain || (W._rain = { x: new Float32Array(NR), y: new Float32Array(NR), z: new Float32Array(NR), end: new Float32Array(NR), init: false });
    const SPN = 90;
    const SPL = W._splash || (W._splash = { x: new Float32Array(SPN), y: new Float32Array(SPN), life: new Float32Array(SPN), z: new Float32Array(SPN), i: 0 });
    const n = kind === 'storm' ? Math.round(300 + 220 * clamp(E.vol, 0, 1)) : Math.round(70 + 70 * clamp(E.vol, 0, 1));
    const gy = W._horizonY && W._horizonH === h ? W._horizonY : 0.72 * h;
    const slant = clamp(wind * 0.16, -0.35, 0.35);
    const respawn = (i, anywhere) => {
      R.z[i] = 0.25 + Math.random() * 0.75;
      R.x[i] = -0.15 * w + Math.random() * w * 1.3;
      R.y[i] = anywhere ? Math.random() * h : -Math.random() * h * 0.25;
      R.end[i] = gy - 0.05 * h + R.z[i] * (h - gy) * 1.05;            // nearer drops land lower on the screen
    };
    if (prewarm || !R.init) { for (let i = 0; i < NR; i++) respawn(i, true); R.init = true; }
    ctx.save(); ctx.lineCap = 'round';
    const heavy = kind === 'storm' ? 1.25 : 0.9;
    for (let band = 0; band < 3; band++) {                                // far, middle, near: one path each
      const z0 = 0.25 + band * 0.25, z1 = z0 + 0.25;
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const z = R.z[i]; if (z < z0 || z >= z1) continue;
        const v = (1100 + 1500 * z) * sc;                                // px / s
        R.y[i] += v * dt; R.x[i] += v * dt * slant;
        if (R.y[i] > R.end[i]) {
          if (z > 0.45 && Math.random() < 0.6) { const j = SPL.i; SPL.i = (j + 1) % SPN; SPL.x[j] = R.x[i]; SPL.y[j] = R.end[i]; SPL.life[j] = 1; SPL.z[j] = z; }
          respawn(i, false); continue;
        }
        const len = (14 + 38 * z) * sc * heavy;
        ctx.moveTo(R.x[i], R.y[i]); ctx.lineTo(R.x[i] - slant * len, R.y[i] - len);
      }
      const zm = (z0 + z1) / 2;
      ctx.strokeStyle = `rgba(205,218,235,${(0.12 + 0.38 * zm).toFixed(3)})`;
      ctx.lineWidth = Math.max(0.7, (0.6 + 1.5 * zm) * sc);
      ctx.stroke();
    }
    // splashes: a little crown of droplets and a fading ring
    ctx.strokeStyle = 'rgba(220,232,245,0.7)'; ctx.fillStyle = 'rgba(220,232,245,0.8)';
    for (let j = 0; j < SPN; j++) {
      if (SPL.life[j] <= 0) continue;
      SPL.life[j] -= dt * 4;
      const L = clamp(SPL.life[j], 0, 1), k = 1 - L, z = SPL.z[j], r = (3 + 9 * z) * sc * (0.4 + k);
      ctx.globalAlpha = L * 0.8; ctx.lineWidth = Math.max(0.6, 1.1 * z * sc);
      ctx.beginPath(); ctx.ellipse(SPL.x[j], SPL.y[j], r, r * 0.28, 0, 0, TAU); ctx.stroke();
      for (let q = -1; q <= 1; q += 2) { ctx.beginPath(); ctx.arc(SPL.x[j] + q * r * 0.7, SPL.y[j] - (6 * z * sc) * Math.sin(k * Math.PI), Math.max(0.7, 1.3 * z * sc), 0, TAU); ctx.fill(); }
    }
    ctx.globalAlpha = 1;
    // a soft grey veil of distant rain over the scene in a storm
    if (kind === 'storm') { ctx.fillStyle = 'rgba(170,180,200,0.10)'; ctx.fillRect(0, 0, w, h); }
    ctx.restore();
  }
  // ---- lightning: strikes while env.lightning (a spike right now)
  if (E.lightning && !E.freeze) {
    if (!WX.prevLightning || tA >= WX.nextStrike) { strike(W, w, h); WX.nextStrike = tA + 0.9 + Math.random() * 1.7; }
  }
  WX.prevLightning = E.lightning;
  const B = W._bolt;
  if (B.life > 0) {
    B.life -= dt;
    const L = clamp(B.life / B.max, 0, 1), fl = L > 0.75 ? 1 : L > 0.62 ? 0.35 : L;
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    const path = (arr, n) => { ctx.beginPath(); ctx.moveTo(arr[0], arr[1]); for (let i = 1; i <= n; i++) ctx.lineTo(arr[2 * i], arr[2 * i + 1]); };
    for (let pass = 0; pass < 3; pass++) {
      const lw = pass === 0 ? s * 0.22 : pass === 1 ? s * 0.08 : Math.max(1.5, s * 0.025);
      ctx.globalAlpha = fl; ctx.lineWidth = lw; ctx.strokeStyle = BOLT_COLS[pass];
      path(B.main, 32); ctx.stroke();
      ctx.lineWidth = lw * 0.6;
      for (let k = 0; k < B.nbr; k++) { path(B.br.subarray(k * 34, k * 34 + 34), 16); ctx.stroke(); }
    }
    const rg = ctx.createRadialGradient(B.x, B.y, 0, B.x, B.y, s * 1.4);
    rg.addColorStop(0, `rgba(230,180,255,${(0.8 * fl).toFixed(3)})`); rg.addColorStop(1, 'rgba(180,77,255,0)');
    ctx.globalAlpha = 1; ctx.fillStyle = rg; ctx.fillRect(B.x - s * 1.4, B.y - s * 1.4, s * 2.8, s * 2.8);
    ctx.restore();
  }
  if (WX.flash > 0) {
    const f = WX.flash;
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    ctx.fillStyle = `rgba(150,90,220,${(0.32 * f).toFixed(3)})`; ctx.fillRect(0, 0, w, h);
    ctx.restore();
    WX.flash = Math.max(0, f - dt * 3.2);
  }
  // ---- motes in the light (calm / active), ledger pages tumbling across (active / storm)
  if (kind === 'calm' || kind === 'active') {
    const M = W._mote, n = kind === 'active' ? 60 : 22;
    if (prewarm) for (let i = 0; i < M.n; i++) respawnMote(M, i, w, h);
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < n; i++) {
      M.x[i] += (M.vx[i] + wind * 8) * dt * sc; M.y[i] += (M.vy[i] + Math.sin(tA * 0.7 + M.ph[i]) * 6) * dt * sc;
      if (M.x[i] < -10 || M.x[i] > w + 10 || M.y[i] < -10 || M.y[i] > h) respawnMote(M, i, w, h);
      const a = (0.25 + 0.35 * Math.sin(tA * 1.7 + M.ph[i])) * (kind === 'active' ? 1 : 0.7), r = X.mote.width * 0.5 * M.sz[i] * sc;
      if (a <= 0) continue;
      ctx.globalAlpha = a; ctx.drawImage(X.mote, M.x[i] - r, M.y[i] - r, r * 2, r * 2);
    }
    ctx.restore();
  }
  if (false) {                                     // ledger pages tumbling across: removed (Zee 2026-11-04, no flying papers)
    const pg = X.page;
    for (let i = 0; i < 3; i++) {
      const cyc = 8 + 5 * rand(i * 3.3), cycle = Math.floor(tA / cyc + rand(i)), ph = fract(tA / cyc + rand(i));
      if (ph > 0.5) continue;
      const u = ph / 0.5, dirn = wind >= 0 ? 1 : -1;
      const x = dirn > 0 ? lerp(-0.1 * w, 1.1 * w, u) : lerp(1.1 * w, -0.1 * w, u);
      const y = h * (0.2 + 0.45 * rand(cycle * 7.1 + i)) + Math.sin(u * 9 + i) * h * 0.04;
      const z = sc * (kind === 'storm' ? 1.1 : 0.9), a = tA * (2 + i) * dirn;
      const c = Math.cos(a) * z, sn = Math.sin(a) * z, fl = Math.cos(tA * 3.1 + i * 2);
      setXf(ctx, m0, c * fl, sn * fl, -sn, c, x, y);
      ctx.globalAlpha = 0.95; ctx.drawImage(pg, -pg.width / 2, -pg.height / 2);
    }
    ctx.setTransform(m0); ctx.globalAlpha = 1;
  }
}

// ============================================================================================================ GRADE
// Last pass over the whole frame: golden hour (amber, long shadows, low light shafts), night (blue multiply with the Buyer's lamp as the
// only light), wooden Alley (warm tint, wood vignette), Time Freeze (sepia + static + scratches), REPLAY marquee across the sky.
function noiseTiles(W) {
  if (W._noise) return W._noise;
  const list = [];
  for (let k = 0; k < 4; k++) {
    const N = 192, c = makeCanvas(N, N), g = c.getContext('2d'), im = g.createImageData(N, N), d = im.data;
    for (let i = 0; i < N * N; i++) { const v = (Math.random() * 255) | 0; d[i * 4] = v; d[i * 4 + 1] = v; d[i * 4 + 2] = v; d[i * 4 + 3] = Math.random() < 0.5 ? 0 : (Math.random() * 120) | 0; }
    g.putImageData(im, 0, 0); list.push(c);
  }
  W._noise = list;
  return list;
}
function defaultLights(W, w, h, E) {
  const v = W._lastView;
  if (v && v.w === w) {
    const s = v.s, tr = W._lastTerrain, prof = getProfile(W, tr), k = tanTilt(v);
    return [
      { x: v.xToScreen(1.07), y: walkY(v, prof, 1.07, k) - 2.75 * s, r: 2.8 * s },     // the Buyer's lamp
      { x: v.xToScreen(-0.22), y: v.groundY - 4.9 * s, r: 1.5 * s },                    // the roof sign
    ];
  }
  const S = h / 9.47, xb = E.mirror ? 0.123 * w : 0.877 * w, xs = E.mirror ? 0.877 * w : 0.123 * w;
  return [{ x: xb, y: 0.72 * h - 2.75 * S, r: 2.8 * S }, { x: xs, y: 0.72 * h - 4.9 * S, r: 1.5 * S }];
}
function replayMarquee(W, w, h) {
  const key = w + 'x' + h;
  if (W._replay && W._replay.key === key) return W._replay;
  const text = 'REPLAY', meas = makeCanvas(10, 10).getContext('2d');
  meas.font = `900 100px ${FONT.deco}`;
  const fs = Math.round(Math.min(h * 0.26, 100 * (w * 0.74) / Math.max(1, meas.measureText(text).width)));
  meas.font = `900 ${fs}px ${FONT.deco}`;
  const tw = Math.ceil(meas.measureText(text).width + fs * 0.6), th = Math.ceil(fs * 1.25);
  const c = makeCanvas(tw, th), g = c.getContext('2d');
  g.font = `900 ${fs}px ${FONT.deco}`; g.textBaseline = 'middle'; g.textAlign = 'center';
  const gr = g.createLinearGradient(0, th * 0.15, 0, th * 0.85);
  gr.addColorStop(0, P.goldHot); gr.addColorStop(0.45, P.gold); gr.addColorStop(0.55, P.goldDeep); gr.addColorStop(1, P.gold);
  g.lineJoin = 'round'; g.lineWidth = fs * 0.12; g.strokeStyle = P.crimson; g.strokeText(text, tw / 2, th / 2);
  g.lineWidth = fs * 0.05; g.strokeStyle = P.ink; g.strokeText(text, tw / 2, th / 2);
  g.fillStyle = gr; g.fillText(text, tw / 2, th / 2);
  // bulbs: sample the glyph mask on a grid, keep points just inside the edge
  const mask = makeCanvas(tw, th), mg = mask.getContext('2d');
  mg.font = g.font; mg.textBaseline = 'middle'; mg.textAlign = 'center'; mg.fillStyle = '#fff'; mg.fillText(text, tw / 2, th / 2);
  const data = mg.getImageData(0, 0, tw, th).data, step = Math.max(6, Math.round(fs * 0.085)), bulbs = [];
  const inside = (x, y) => x >= 0 && y >= 0 && x < tw && y < th && data[(y * tw + x) * 4 + 3] > 140;
  for (let y = step; y < th - step; y += step) {
    for (let x = step; x < tw - step; x += step) {
      if (!inside(x, y)) continue;
      const d = Math.round(step * 0.9);
      if (!inside(x + d, y) || !inside(x - d, y) || !inside(x, y + d) || !inside(x, y - d)) bulbs.push(x, y);
    }
  }
  W._replay = { key, c, tw, th, fs, bulbs: new Float32Array(bulbs) };
  return W._replay;
}
function gradeDraw(W, ctx, w, h, E, t) {
  const tA = W._animT(E, t);
  const v = W._lastView, s = v && v.w === w ? v.s : h / 9.47;
  const gy = v && v.w === w ? v.groundY : 0.72 * h;
  // golden hour: amber light, a low sun's shafts, long shadows across the street
  if (E.golden_hour && !E.freeze) {
    ctx.save();
    ctx.globalCompositeOperation = 'soft-light'; ctx.globalAlpha = 0.55; ctx.fillStyle = '#ff9a3c'; ctx.fillRect(0, 0, w, h);
    ctx.globalCompositeOperation = 'multiply'; ctx.globalAlpha = 0.5;
    const mg = ctx.createLinearGradient(0, 0, 0, h); mg.addColorStop(0, '#ffe6c0'); mg.addColorStop(1, '#e8996a');
    ctx.fillStyle = mg; ctx.fillRect(0, 0, w, h);
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    const sunLeft = !!E.mirror, sx = sunLeft ? -0.1 * w : 1.1 * w, sy = gy - 0.12 * h;
    for (let i = 0; i < 6; i++) {        // long shadows: dark bands stretching away from the low sun across the street
      const x0 = w * (0.08 + i * 0.17 + 0.03 * Math.sin(i * 3.1)), len = w * 0.55, wd = s * (0.25 + 0.2 * rand(i));
      const dir = sunLeft ? 1 : -1;
      const lg = ctx.createLinearGradient(x0, 0, x0 + dir * len, 0);
      lg.addColorStop(0, 'rgba(60,24,30,0.22)'); lg.addColorStop(1, 'rgba(60,24,30,0)');
      ctx.fillStyle = lg; ctx.beginPath();
      ctx.moveTo(x0, gy - s * 0.06); ctx.lineTo(x0 + wd, gy - s * 0.06); ctx.lineTo(x0 + dir * len + wd, gy + s * 0.12); ctx.lineTo(x0 + dir * len, gy + s * 0.12); ctx.closePath(); ctx.fill();
    }
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 4; i++) {
      const ty = gy - h * (0.08 + i * 0.1), spread = h * (0.04 + 0.03 * i);
      const lg = ctx.createLinearGradient(sx, 0, sunLeft ? w : 0, 0);
      lg.addColorStop(0, 'rgba(255,190,110,0.14)'); lg.addColorStop(1, 'rgba(255,190,110,0)');
      ctx.fillStyle = lg; ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(sunLeft ? w : 0, ty - spread); ctx.lineTo(sunLeft ? w : 0, ty + spread); ctx.closePath(); ctx.fill();
    }
    ctx.restore();
  }
  // night: everything sinks into blue; the Buyer's lamp is the only light (holes in the dark)
  const nightK = E.night ? 1 : (E.session === 'dead' || E.session === 'closed') ? 0.75 : 0;
  if (nightK > 0) {
    const gw = Math.max(2, Math.round(w / 3)), gh = Math.max(2, Math.round(h / 3));
    if (!W._nightC || W._nightC.width !== gw || W._nightC.height !== gh) W._nightC = makeCanvas(gw, gh);
    const g = W._nightC.getContext('2d');
    g.globalCompositeOperation = 'source-over';
    const vg = g.createLinearGradient(0, 0, 0, gh);
    const lerpc = (a, b) => `rgb(${Math.round(lerp(255, a[0], nightK))},${Math.round(lerp(255, a[1], nightK))},${Math.round(lerp(255, a[2], nightK))})`;
    vg.addColorStop(0, lerpc([210, 216, 245])); vg.addColorStop(gy / h * 0.85, lerpc([120, 130, 190])); vg.addColorStop(1, lerpc([78, 86, 150]));
    g.fillStyle = vg; g.fillRect(0, 0, gw, gh);
    g.globalCompositeOperation = 'lighter';
    const lights = E.lights || defaultLights(W, w, h, E);
    for (const L of lights) {
      if (!L || !Number.isFinite(L.x) || !Number.isFinite(L.y)) continue;
      const r = (Number.isFinite(L.r) ? L.r : s * 2) / 3, x = L.x / 3, y = L.y / 3;
      const lg = g.createRadialGradient(x, y, 0, x, y, r);
      lg.addColorStop(0, 'rgba(160,130,80,1)'); lg.addColorStop(0.5, 'rgba(110,90,55,0.6)'); lg.addColorStop(1, 'rgba(110,90,55,0)');
      g.fillStyle = lg; g.fillRect(x - r, y - r, r * 2, r * 2);
    }
    ctx.save();
    ctx.globalCompositeOperation = 'multiply'; ctx.imageSmoothingEnabled = true;
    ctx.drawImage(W._nightC, 0, 0, w, h);
    ctx.globalCompositeOperation = 'lighter';
    for (const L of lights) {
      if (!L || !Number.isFinite(L.x)) continue;
      const r = (Number.isFinite(L.r) ? L.r : s * 2) * 0.6;
      const lg = ctx.createRadialGradient(L.x, L.y, 0, L.x, L.y, r);
      lg.addColorStop(0, `rgba(255,200,120,${(0.16 * nightK).toFixed(3)})`); lg.addColorStop(1, 'rgba(255,200,120,0)');
      ctx.fillStyle = lg; ctx.fillRect(L.x - r, L.y - r, r * 2, r * 2);
    }
    ctx.restore();
  }
  // the wooden Alley: warm tint, wood vignette
  if (E.wooden) {
    ctx.save();
    ctx.globalCompositeOperation = 'soft-light'; ctx.globalAlpha = 0.5; ctx.fillStyle = '#ffae5e'; ctx.fillRect(0, 0, w, h);
    ctx.globalCompositeOperation = 'multiply'; ctx.globalAlpha = 1; ctx.fillStyle = '#fff1dc'; ctx.fillRect(0, 0, w, h);
    ctx.globalCompositeOperation = 'source-over';
    const rg = ctx.createRadialGradient(w / 2, h * 0.48, Math.min(w, h) * 0.35, w / 2, h * 0.5, Math.max(w, h) * 0.75);
    rg.addColorStop(0, 'rgba(90,50,20,0)'); rg.addColorStop(1, 'rgba(90,50,20,0.42)');
    ctx.fillStyle = rg; ctx.fillRect(0, 0, w, h);
    ctx.restore();
  }
  // Time Freeze: the picture goes sepia and the film shows its grain
  if (E.freeze) {
    ctx.save();
    ctx.globalCompositeOperation = 'color'; ctx.globalAlpha = 0.92; ctx.fillStyle = P.sepia; ctx.fillRect(0, 0, w, h);
    ctx.globalCompositeOperation = 'multiply'; ctx.globalAlpha = 1; ctx.fillStyle = '#f3e3c8'; ctx.fillRect(0, 0, w, h);
    ctx.globalCompositeOperation = 'source-over';
    const nt = noiseTiles(W), tile = nt[Math.floor(t * 24) % nt.length];
    const pat = ctx.createPattern(tile, 'repeat');
    const ox = Math.floor(Math.random() * 192), oy = Math.floor(Math.random() * 192);
    ctx.translate(-ox, -oy); ctx.globalAlpha = 0.55; ctx.fillStyle = pat; ctx.fillRect(ox, oy, w + 192, h + 192); ctx.translate(ox, oy);
    ctx.globalAlpha = 1;
    for (let i = 0; i < 2; i++) {         // tracking bands rolling down
      const y = fract(t * (0.13 + i * 0.07) + i * 0.5) * h;
      ctx.fillStyle = 'rgba(255,245,225,0.12)'; ctx.fillRect(0, y, w, h * 0.012);
      ctx.fillStyle = 'rgba(40,30,20,0.12)'; ctx.fillRect(0, y + h * 0.012, w, h * 0.006);
    }
    for (let i = 0; i < 3; i++) {         // film scratches
      if (rand(Math.floor(t * 12) * 3.1 + i) < 0.5) continue;
      const x = rand(Math.floor(t * 12) * 7.3 + i * 2) * w;
      ctx.fillStyle = 'rgba(255,248,230,0.35)'; ctx.fillRect(x, 0, 1.2, h);
    }
    const rg = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.3, w / 2, h / 2, Math.max(w, h) * 0.72);
    rg.addColorStop(0, 'rgba(50,34,20,0)'); rg.addColorStop(1, 'rgba(50,34,20,0.55)');
    ctx.fillStyle = rg; ctx.fillRect(0, 0, w, h);
    ctx.restore();
  }
  // REPLAY: a giant casino marquee hung across the sky on cables, bulbs chasing
  if (E.replay) {
    const R = replayMarquee(W, w, h), X = weatherSprites(W, s);
    // centred between the bank's roof sign and the Buyer's zeppelin (either world), so neither ever hides behind it
    const scale = Math.min(1, (w * 0.56) / R.tw), dw = R.tw * scale, dh = R.th * scale;
    const x0 = clamp(0.5 * w - dw / 2, w * 0.01, w * 0.99 - dw), y0 = Math.max(h * 0.035, h * 0.18 - dh / 2);
    ctx.save();
    ctx.strokeStyle = 'rgba(26,20,16,0.8)'; ctx.lineWidth = Math.max(1, s * 0.012);
    ctx.beginPath();
    for (const fx of [0.12, 0.38, 0.62, 0.88]) { ctx.moveTo(x0 + dw * fx, -2); ctx.lineTo(x0 + dw * fx, y0 + dh * 0.22); }
    ctx.stroke();
    ctx.globalAlpha = 0.92; ctx.drawImage(R.c, x0, y0, dw, dh);
    ctx.globalAlpha = 1;
    const chase = Math.floor(tA * 8), br = X.bulb, bulbR = Math.max(2, R.fs * 0.035 * scale);
    for (let i = 0; i < R.bulbs.length; i += 2) {
      const bx = x0 + R.bulbs[i] * scale, by = y0 + R.bulbs[i + 1] * scale, on = ((i >> 1) + chase) % 4 !== 0;
      ctx.fillStyle = on ? '#fff6d6' : '#8a6a24'; ctx.beginPath(); ctx.arc(bx, by, bulbR, 0, TAU); ctx.fill();
      if (on) { ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 0.6; ctx.drawImage(br, bx - bulbR * 3, by - bulbR * 3, bulbR * 6, bulbR * 6); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over'; }
    }
    ctx.restore();
  }
}

// @@INSERT-SECTIONS-ABOVE@@ ----------------------------------------------------------------------------------------- the World

class World {
  constructor() {
    this._env = normEnv(null, {});
    this._paused = 0; this._lastRealT = null;
    this._aff = [1, 0];
    this._horizonY = null; this._lastView = null; this._lastTerrain = null;
    this._prof = null; this._profObj = null;
    this._stats = { slabBuilds: 0, lastSlabMs: 0, skylineBuilds: 0, lastSkylineMs: 0 };
    if (typeof initPools === 'function') initPools(this);
  }
  // animation clock: stands still while env.freeze (Time Freeze stops the world; only the static noise moves)
  _animT(E, t) {
    if (this._lastRealT === null) this._lastRealT = t;
    const dt = t - this._lastRealT;
    if (dt > 0 && dt < 1 && E.freeze) this._paused += dt;
    if (dt !== 0) this._lastRealT = t;
    return t - this._paused;
  }
  drawSky(ctx, w, h, env, t) {
    const E = normEnv(env, this._env);
    if (typeof skyDraw === 'function') return skyDraw(this, ctx, w, h, E, t);
    ctx.fillStyle = SKY.noon[1]; ctx.fillRect(0, 0, w, h);
  }
  drawSkyline(ctx, w, h, camX, env, t) {
    const E = normEnv(env, this._env);
    if (typeof skylineDraw === 'function') return skylineDraw(this, ctx, w, h, +camX || 0, E, t);
  }
  drawTerrain(ctx, view, terrain, env, t) {
    const E = normEnv(env, this._env);
    this._lastView = view; this._lastTerrain = terrain; this._horizonY = view.groundY;
    if (typeof terrainDraw === 'function') return terrainDraw(this, ctx, view, terrain, E, t);
    const prof = getProfile(this, terrain), k = tanTilt(view);
    ctx.fillStyle = P.marble; ctx.beginPath(); ctx.moveTo(0, view.h);
    for (let x = 0; x <= view.w; x += 8) ctx.lineTo(x, walkY(view, prof, this.screenToXn(view, x), k));
    ctx.lineTo(view.w, view.h); ctx.closePath(); ctx.fill();
  }
  groundYAt(view, terrain, xn) {
    return walkY(view, getProfile(this, terrain), xn, tanTilt(view));
  }
  drawPit(ctx, view, pit, env, t) {
    const E = normEnv(env, this._env);
    if (pit && typeof pitDraw === 'function') return pitDraw(this, ctx, view, pit, E, t, false);
  }
  drawChasmRift(ctx, view, span, env, t, opts) {
    const E = normEnv(env, this._env);
    if (Array.isArray(span) && span.length === 2 && span.every(Number.isFinite)) return riftDraw(this, ctx, view, span, E, t, opts || {});
  }
  drawPitFront(ctx, view, pit, env, t) {
    const E = normEnv(env, this._env);
    if (pit && typeof pitDraw === 'function') return pitDraw(this, ctx, view, pit, E, t, true);
  }
  drawFog(ctx, view, fromXn, env, t) {
    const E = normEnv(env, this._env);
    if (typeof fogDraw === 'function') return fogDraw(this, ctx, view, Number.isFinite(fromXn) ? fromXn : 1.12, E, t);
  }
  drawWeather(ctx, w, h, env, dt, t) {
    const E = normEnv(env, this._env);
    if (typeof weatherDraw === 'function') return weatherDraw(this, ctx, w, h, E, Number.isFinite(dt) ? clamp(dt, 0, 0.1) : 0.016, t);
  }
  drawSeasonBand(ctx, w, env, t) {
    const E = normEnv(env, this._env);
    if (typeof seasonDraw === 'function') return seasonDraw(this, ctx, w, E, t);
  }
  drawGrade(ctx, w, h, env, t) {
    const E = normEnv(env, this._env);
    if (typeof gradeDraw === 'function') return gradeDraw(this, ctx, w, h, E, t);
  }
  // ---- extras
  debugStrike(w, h) { if (typeof strike === 'function') strike(this, w, h); }
  stats() { return { ...this._stats }; }
  heightAt(terrain, xn) { return heightAt(getProfile(this, terrain), xn); }
  // the screen angle of the walking line at xn (canvas convention, left-to-right on screen, mirror-safe)
  groundSlopeAt(view, terrain, xn) {
    const e = 0.004;
    let xa = view.xToScreen(xn - e), xb = view.xToScreen(xn + e);
    let ya = this.groundYAt(view, terrain, xn - e), yb = this.groundYAt(view, terrain, xn + e);
    if (xb < xa) { let s = xa; xa = xb; xb = s; s = ya; ya = yb; yb = s; }
    return Math.atan2(yb - ya, (xb - xa) || 1e-6);
  }
  screenToXn(view, px) { const a = viewAffine(view, this._aff); return (px - a[1]) / a[0]; }
  tiltToRad(tilt, mirror) { return clamp(+tilt || 0, -1, 1) * MAX_TILT_RAD * (mirror ? -1 : 1); }
  pitSinkAt(view, pit, xn) {
    if (!pit || !Number.isFinite(pit.x0) || !Number.isFinite(pit.x1)) return 0;
    const a = Math.min(pit.x0, pit.x1), b = Math.max(pit.x0, pit.x1);
    if (xn <= a || xn >= b || b - a < 1e-6) return 0;
    const u = (xn - a) / (b - a);
    return clamp(+pit.depth || 0, 0, 1) * 0.62 * view.s * Math.pow(Math.sin(Math.PI * u), 0.6) * 0.7;
  }
}

export function makeWorld() { return new World(); }
export default makeWorld;
