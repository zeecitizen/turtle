// art.js - every character and prop of Golden Gravity (F-ART). CONTRACT.md section 8.2 (exact names and signatures).
// Style: "Clockwork-Deco Casino" - THE RECIPE in palette.js: ink outline, flat base + one highlight band + one shadow band,
// gold deco trims, rivets, additive glows, cartoon proportions (1920s rubber-hose pie eyes), squash & stretch. Text in the world is a
// physical object (split-flap tiles, painted tags, neon tubes) and is never mirrored.
//
// CONVENTIONS (all functions):
//   * Signature (ctx, x, y, s, st) unless noted. s = px per unit (1 unit = the Runner's standing height, s ~ 95 at 1600x900).
//   * st.t = seconds (any clock; every animation is a pure function of st.t, so fixtures can loop it; time running backwards is fine).
//   * Pure drawing: the ctx state (transform, alpha, composite, styles) is always restored, even if a function fails.
//   * facing +1 = looks / faces right; -1 mirrors around x. Text is never mirrored (the roof sign and coin emblem un-flip themselves
//     even inside a mirrored world transform).
//   * Every st field is optional and defaulted. Nothing throws (an error is reported once to console.error and the frame goes on).
//   * Cheap: static parts are cached sprites (LRU, keyed by on-screen pixel size in 6% buckets, DPR / camera zoom aware); 46 mixed draws
//     cost ~2.5 ms per frame in headless Chrome (gallery_art.html?page=16 measures it: window.GG_BENCH).
//
// ANCHORS (x, y) - where the point you pass sits on the drawing:
//   drawRunner / drawTwin / drawGhost  feet on the ground, centre of the stance. Height 1.0 (head top). Returns RUNNER_PTS.
//   drawBank        bottom-centre of the facade (street level). 3.4 w x 4.6 h. Returns BANK_GEO (= bankGeometry(...)).
//   drawRoofSign    (cx, cy) = centre of the board, w x h in px (BANK_GEO.sign is the mount on the roof: 2.2 x 0.9 units).
//   drawBell        bottom-centre of the belfry frame, 1.1 tall incl. the frame (stand it on BANK_GEO.bell = the top of the sign).
//   drawBuyer       the ground point under the basket. The keel floats 2.6 above it, the envelope (2.4 wide) rides above the tycoon.
//                   DEFAULT facing = -1 (he looks left, down the street at the Runner, in the long world); pass +1 in the mirror world.
//                   Returns BUYER_PTS.
//   drawMerchant    wheel contact point on the ground. 1.25 tall to the hat; his neon sign rides above on a pole (to ~1.75).
//   drawRat         ground point under the rat (0.22 tall).  drawAnvil: bottom-centre (0.42 wide), returns ANVIL_PTS (the rope ring).
//   drawStake       ground point (0.62 tall).  drawWall: bottom-centre (0.32 w x 0.9 h).  drawBarrel: bottom-centre (0.85 tall).
//   drawCollector   feet (1.6 tall); the chain runs out to +x (about 1.7 units at chain = 1) and the "see you tomorrow" sign hangs there.
//   drawJar, drawRadio, drawCabinet, drawTrophyShelf, drawCoinStack: bottom-centre on the desk / shelf surface.
//   drawTether      from (x1,y1) (the Runner's belt: RUNNER_PTS.beltX/Y) to (x2,y2) (the anvil's ring: ANVIL_PTS.ringX/Y).
//   drawCoin        (cx, cy) centre, r px.  drawNote: (cx, cy) centre.  drawHoldRing: (cx, cy) centre, r px (label plate below).
//   drawPistol      the grip (where the hand holds it); the barrel points along facing.  drawMachete: the hand on the handle.
//   drawBalloon     the bottom of its rope, where the hands grip (the Runner's 'fly' pose has its hands at RUNNER_PTS.gripX/Y,
//                   which is (x, y - 1.08 s) when he hangs still).  Total height 1.3.
//   drawPageCorner  the page's corner point (bottom-right corner of the screen); the dog-ear rises up-left (ctx.scale(-1,1) for left).
//
// RETURNED POINTS (screen px; one reused object per function - copy what you keep):
//   RUNNER_PTS  {coinX, coinY, coinR, handX, handY, gripX, gripY, headX, headY, beltX, beltY}   (machete = the coin; tether = belt)
//   BANK_GEO    {sign:{cx,cy,w,h}, bell:{x,y}, door:{x,y,w,h}, banker:{x,y,w,h}, craneTip:{x,y}, step:{x,y}}
//               bankGeometry(x, y, s, facing, crane) gives the same without drawing (hit boxes: shoot = hold on BANK_GEO.banker).
//   BUYER_PTS   {tagX, tagY, tagR, gunX, gunY, loupeX, loupeY, mouthX, mouthY}   (haggle = hold on the tag; cash FX from the gun)
//   ANVIL_PTS   {ringX, ringY}
//
// EXTRA OPTIONAL FIELDS (additive to CONTRACT 8.2; safe to ignore):
//   drawRunner  face: expression override ('smile','grin','joy','smug','proud','determined','effort','focus','worried','sad','panic','ooh')
//               patience 0..1 (pistol glow in 'aim'), recoil 0..1 ('aim'), look -1..1 (eyes), blinkSeed. lean > 0 tilts toward facing.
//               wooden: the Apprentice = the same Runner and the same outfit (the clothes stay the result readout) with a wooden head,
//               wooden hands, ball joints and a wooden token (and a wooden board when riding).  coin.visible defaults to false.
//   drawTwin / drawGhost  same poses as the Runner (the Twin carries a brass token in the holding poses; alpha defaults .88 / .5).
//   drawBank    banker.mood also accepts any unknown string (drawn as 'smug').  shutters 0..1 covers door, doorway and windows.
//   drawRoofSign wooden (bool, the Alley's wooden cabinet).  The board keeps a fixed tile count per id (grows for longer text).
//   drawAnvil, drawMachete, drawCollector  facing.   drawTether groundY (px, the street the slack rope lies on).
//   drawMerchant roll defaults to st.t * 4 when omitted. duck 0..1: the sign pole swings back and down (clear of the Buyer's tag).

import { P, LINE, FONT, rgba, mix, lighten, darken, rand, clamp, lerp, ease, roundRect } from './palette.js';

//<<CORE
const TAU = Math.PI * 2;
const PI = Math.PI;

// ---------------------------------------------------------------- depth-tracked save/restore + the never-throw guard
let _depth = 0;
function sv(ctx) { ctx.save(); _depth++; }
function rs(ctx) { ctx.restore(); _depth--; }
const _reported = new Set();
function guard(name, fn) {
  return function guarded(...args) {
    const ctx = args[0];
    const d0 = _depth;
    try {
      return fn.apply(null, args);
    } catch (e) {
      if (!_reported.has(name)) { _reported.add(name); console.error('art.' + name + ' failed:', (e && e.stack) || e); }
      return null;
    } finally {
      while (_depth > d0) { try { ctx.restore(); } catch (_) { /* ignore */ } _depth--; }
    }
  };
}

// ---------------------------------------------------------------- colours (memoised; the hot paths use the precomputed C table)
const _cm = new Map();
function memo(k, f) { let v = _cm.get(k); if (v === undefined) { v = f(); if (_cm.size > 4000) _cm.clear(); _cm.set(k, v); } return v; }
const LI = (h, t = 0.25) => memo('l' + h + t, () => lighten(h, t));
const DK = (h, t = 0.3) => memo('d' + h + t, () => darken(h, t));
const MX = (a, b, t) => { t = Math.round(clamp(t, 0, 1) * 32) / 32; return memo('m' + a + b + t, () => mix(a, b, t)); };
const RA = (h, a) => { a = Math.round(clamp(a, 0, 1) * 100) / 100; return memo('a' + h + a, () => rgba(h, a)); };

// ---------------------------------------------------------------- unit space: translate to the anchor, scale by s (and facing)
// Inside, 1 = one Runner height, y grows downward, so "up" is negative. Line widths are in units (LINE.ink = 0.035).
function beginU(ctx, x, y, s, f = 1) {
  sv(ctx);
  ctx.translate(x, y);
  ctx.scale(s * (f < 0 ? -1 : 1), s);
  ctx.lineJoin = 'round'; ctx.lineCap = 'round';
}
function ink(ctx, w = LINE.ink, col = P.ink) { ctx.lineWidth = w; ctx.strokeStyle = col; }
// fill the current path, then the ink outline
function fo(ctx, fill, w = LINE.ink) { ctx.fillStyle = fill; ctx.fill(); ink(ctx, w); ctx.stroke(); }
function ellP(ctx, x, y, rx, ry, rot = 0) { ctx.beginPath(); ctx.ellipse(x, y, Math.abs(rx) + 1e-6, Math.abs(ry) + 1e-6, rot, 0, TAU); }
function circP(ctx, x, y, r) { ctx.beginPath(); ctx.arc(x, y, Math.abs(r), 0, TAU); }
function rrP(ctx, x, y, w, h, r) { roundRect(ctx, x, y, w, h, Math.max(0, r)); }
function polyP(ctx, pts, close = true) {
  ctx.beginPath(); ctx.moveTo(pts[0], pts[1]);
  for (let i = 2; i < pts.length; i += 2) ctx.lineTo(pts[i], pts[i + 1]);
  if (close) ctx.closePath();
}
// a limb: polyline with an ink border, the base colour and a thin highlight stripe
function limb(ctx, pts, w, base, hi = true) {
  ctx.beginPath(); ctx.moveTo(pts[0], pts[1]);
  for (let i = 2; i < pts.length; i += 2) ctx.lineTo(pts[i], pts[i + 1]);
  ctx.strokeStyle = P.ink; ctx.lineWidth = w + LINE.ink; ctx.stroke();
  ctx.strokeStyle = base; ctx.lineWidth = w; ctx.stroke();
  if (hi) {
    ctx.save(); ctx.translate(-w * 0.16, -w * 0.16);
    ctx.strokeStyle = LI(base, 0.3); ctx.lineWidth = w * 0.26; ctx.stroke();
    ctx.restore();
  }
}
// text at unit position (xu, yu), size in units; never mirrored (it undoes any flip in the current transform)
function textU(ctx, str, xu, yu, sizeU, opts) {
  opts = opts || {};
  const m = ctx.getTransform();
  const sx = Math.hypot(m.a, m.b) || 1, sy = Math.hypot(m.c, m.d) || 1;
  const flip = (m.a * m.d - m.b * m.c) < 0 ? -1 : 1;
  sv(ctx);
  ctx.translate(xu, yu);
  ctx.scale(flip / sx, 1 / sy);
  if (opts.rot) ctx.rotate(opts.rot * flip);
  const px = Math.max(1, sizeU * sy);
  ctx.font = (opts.weight || 'bold') + ' ' + px.toFixed(2) + 'px ' + (opts.font || FONT.deco);
  ctx.textAlign = opts.align || 'center'; ctx.textBaseline = opts.base || 'middle';
  if (opts.maxW) { const w = ctx.measureText(str).width, mw = opts.maxW * sx; if (w > mw) ctx.scale(mw / w, 1); }
  if (opts.stroke) { ctx.lineJoin = 'round'; ctx.lineWidth = opts.strokeW ? opts.strokeW * sy : px * 0.18; ctx.strokeStyle = opts.stroke; ctx.strokeText(str, 0, 0); }
  ctx.fillStyle = opts.color || P.ink; ctx.fillText(str, 0, 0);
  rs(ctx);
}

// ---------------------------------------------------------------- cached gradients (per ctx) and additive glows
const _gctx = new WeakMap();
function gcache(ctx) { let m = _gctx.get(ctx); if (!m) { m = new Map(); _gctx.set(ctx, m); } if (m.size > 3000) m.clear(); return m; }
function glowU(ctx, x, y, r, color, alpha = 0.6) {
  if (!(r > 0) || !(alpha > 0)) return;
  const m = gcache(ctx);
  let g = m.get('glow' + color);
  if (!g) { g = ctx.createRadialGradient(0, 0, 0, 0, 0, 1); g.addColorStop(0, rgba(color, 1)); g.addColorStop(0.35, rgba(color, 0.42)); g.addColorStop(1, rgba(color, 0)); m.set('glow' + color, g); }
  sv(ctx);
  ctx.globalCompositeOperation = 'lighter';
  ctx.globalAlpha *= clamp(alpha, 0, 1);
  ctx.translate(x, y); ctx.scale(r, r);
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, 1, 0, TAU); ctx.fill();
  rs(ctx);
}
function linG(ctx, key, x0, y0, x1, y1, stops) {
  const m = gcache(ctx);
  let g = m.get(key);
  if (!g) { g = ctx.createLinearGradient(x0, y0, x1, y1); for (let i = 0; i < stops.length; i += 2) g.addColorStop(stops[i], stops[i + 1]); m.set(key, g); }
  return g;
}
function radG(ctx, key, x0, y0, r0, x1, y1, r1, stops) {
  const m = gcache(ctx);
  let g = m.get(key);
  if (!g) { g = ctx.createRadialGradient(x0, y0, r0, x1, y1, r1); for (let i = 0; i < stops.length; i += 2) g.addColorStop(stops[i], stops[i + 1]); m.set(key, g); }
  return g;
}
// the recipe's shading for the current closed path: light upper-left -> base -> dark lower-right (cached per base + box)
function shadeU(ctx, x, y, w, h, base) {
  ctx.fillStyle = linG(ctx, 'sh' + base + x.toFixed(3) + y.toFixed(3) + w.toFixed(3) + h.toFixed(3), x, y, x + w * 0.6, y + h,
    [0, LI(base, 0.25), 0.35, base, 1, DK(base, 0.3)]);
  ctx.fill();
}

// ---------------------------------------------------------------- offscreen canvases: sprite cache (LRU) + scratch layers
function newCanvas(w, h) {
  w = Math.max(1, Math.ceil(w)); h = Math.max(1, Math.ceil(h));
  if (typeof OffscreenCanvas !== 'undefined') return new OffscreenCanvas(w, h);
  const c = document.createElement('canvas'); c.width = w; c.height = h; return c;
}
function pxScale(ctx) { const m = ctx.getTransform(); return Math.max(Math.hypot(m.a, m.b), Math.hypot(m.c, m.d)) || 1; }
const _sprites = new Map();
const SPRITE_MAX = 256;
// Draw a cached sprite inside unit space. box = [x0, y0, w, h] in units around the current origin; draw(c2) paints in unit space.
function sprite(ctx, key, box, draw) {
  const px = pxScale(ctx);
  const q = Math.max(4, Math.round(Math.pow(1.06, Math.round(Math.log(px) / 0.0582689))));   // 6% buckets (log 1.06)
  const k = key + '@' + q;
  let sp = _sprites.get(k);
  if (!sp) {
    const pad = 0.06;
    const W = (box[2] + pad * 2) * q, H = (box[3] + pad * 2) * q;
    if (W * H > 9e6) { draw(ctx); return; }
    const cv = newCanvas(W, H);
    const c2 = cv.getContext('2d');
    c2.translate((-box[0] + pad) * q, (-box[1] + pad) * q);
    c2.scale(q, q);
    c2.lineJoin = 'round'; c2.lineCap = 'round';
    const d0 = _depth;
    try { draw(c2); } catch (e) { if (!_reported.has(key)) { _reported.add(key); console.error('art sprite ' + key, e); } }
    _depth = d0;
    sp = { cv, x: box[0] - pad, y: box[1] - pad, w: box[2] + pad * 2, h: box[3] + pad * 2 };
    if (_sprites.size >= SPRITE_MAX) _sprites.delete(_sprites.keys().next().value);
    _sprites.set(k, sp);
  } else { _sprites.delete(k); _sprites.set(k, sp); }
  ctx.drawImage(sp.cv, sp.x, sp.y, sp.w, sp.h);
}
// scratch layers: draw opaque, then composite once with alpha (+ optional tint). A pool of 3 allows nesting.
const _layers = [];
let _layerTop = 0;
function withLayer(ctx, box, alpha, tint, tintA, draw) {
  const px = pxScale(ctx);
  const W = Math.ceil(box[2] * px) + 4, H = Math.ceil(box[3] * px) + 4;
  if (_layerTop >= 3 || W * H > 6e6) { sv(ctx); ctx.globalAlpha *= alpha; draw(ctx); rs(ctx); return; }
  let L = _layers[_layerTop];
  if (!L) { L = { cv: newCanvas(W, H) }; L.c = L.cv.getContext('2d'); _layers[_layerTop] = L; }
  if (L.cv.width < W || L.cv.height < H) { L.cv.width = Math.max(L.cv.width, W); L.cv.height = Math.max(L.cv.height, H); }
  const c2 = L.c;
  c2.setTransform(1, 0, 0, 1, 0, 0);
  c2.globalAlpha = 1; c2.globalCompositeOperation = 'source-over';
  c2.clearRect(0, 0, W, H);
  // the destination must be unflipped unit space (callers apply facing inside draw)
  c2.translate(2 - box[0] * px, 2 - box[1] * px);
  c2.scale(px, px);
  c2.lineJoin = 'round'; c2.lineCap = 'round';
  _layerTop++;
  const d0 = _depth;
  try { draw(c2); } finally { _depth = d0; _layerTop--; }
  if (tint) {
    c2.setTransform(1, 0, 0, 1, 0, 0);
    c2.globalCompositeOperation = 'source-atop';
    c2.globalAlpha = tintA;
    c2.fillStyle = tint; c2.fillRect(0, 0, W, H);
    c2.globalCompositeOperation = 'source-over'; c2.globalAlpha = 1;
  }
  sv(ctx);
  ctx.globalAlpha *= alpha;
  ctx.drawImage(L.cv, 0, 0, W, H, box[0] - 2 / px, box[1] - 2 / px, W / px, H / px);
  rs(ctx);
}
function rivetU(ctx, x, y, r = 0.018) {
  ctx.fillStyle = P.ink; ctx.beginPath(); ctx.arc(x + r * 0.25, y + r * 0.3, r * 1.15, 0, TAU); ctx.fill();
  ctx.fillStyle = P.rivet; ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.beginPath(); ctx.arc(x - r * 0.35, y - r * 0.35, r * 0.42, 0, TAU); ctx.fill();
}
const num = (v, d) => (typeof v === 'number' && isFinite(v) ? v : d);
const wob = (t, f, a, ph = 0) => Math.sin(t * f * TAU + ph) * a;
//>>CORE

//<<RUNNER
// ================================================================================================ THE RUNNER (one rig, many skins)
// Rig in units, facing right, feet at (0,0), y down. Poses are joint targets solved with 2-bone IK, so every pose keeps its
// proportions (head = 0.30 of the height, oversized hands and shoes) and the Twin / Ghost / Apprentice reuse it for free.
export const RUNNER_PTS = { coinX: 0, coinY: 0, coinR: 0, handX: 0, handY: 0, gripX: 0, gripY: 0, headX: 0, headY: 0, beltX: 0, beltY: 0 };
const RG = { hip: 0.445, thigh: 0.205, shin: 0.2, torso: 0.25, headR: 0.148, upper: 0.155, fore: 0.15,
  legW: 0.078, armW: 0.064, handR: 0.046, ankle: 0.044 };
const R = {
  rot: 0, lift: 0, sqx: 1, sqy: 1, hx: 0, hy: 0, ta: 0, sx: 0, sy: 0, hdx: 0, hdy: 0, ha: 0,
  ln: [0, 0, 0, 0, 0, 0], lf: [0, 0, 0, 0, 0, 0], fn: 0, ff: 0, an: [0, 0, 0, 0, 0, 0], af: [0, 0, 0, 0, 0, 0],
  expr: 'neutral', wind: 0, coin: 'none', cx: 0, cy: 0, cr: 0.17, board: 0, dust: 0, speed: 0, look: 0, blink: false, cane: 'none',
};
// 2-bone IK: root (ax,ay) -> joint -> end at (tx,ty) (clamped to reach). bend +1 puts the joint on the +x side when pointing down.
function ik(ax, ay, tx, ty, l1, l2, bend, o) {
  let dx = tx - ax, dy = ty - ay;
  let d = Math.hypot(dx, dy) || 1e-6;
  const maxd = l1 + l2 - 1e-4, mind = Math.abs(l1 - l2) + 0.02;
  if (d > maxd) { dx *= maxd / d; dy *= maxd / d; d = maxd; } else if (d < mind) { dx *= mind / d; dy *= mind / d; d = mind; }
  const a = Math.atan2(dy, dx);
  const A = Math.acos(clamp((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1));
  const ang = a - bend * A;
  o[0] = ax; o[1] = ay; o[2] = ax + Math.cos(ang) * l1; o[3] = ay + Math.sin(ang) * l1; o[4] = ax + dx; o[5] = ay + dy;
}
const frac = (v) => v - Math.floor(v);

function solvePose(pose, t, lean, coinVis, look) {
  lean = clamp(num(lean, 0), -1, 1);
  R.rot = 0; R.fly = 0; R.lift = 0; R.sqx = 1; R.sqy = 1; R.ha = 0; R.wind = 0.12; R.dust = 0; R.board = 0; R.speed = 0; R.cane = 'none';
  R.coin = coinVis ? 'hug' : 'none';
  let hx = 0, hy = -RG.hip, ta = 0.03;
  let nfx = 0.065, nfy = 0, ffx = -0.06, ffy = 0, nf = 0, ff = 0;
  let arms = coinVis ? 'hug' : 'rest';
  let nhx = 0.05, nhy = 0.29, fhx = -0.05, fhy = 0.29;        // hand targets relative to the shoulder
  let legBend = 1, expr = 'neutral';
  const breath = Math.sin(t * TAU * 0.45);
  switch (pose) {
    case 'run': {
      const ph = t * TAU * 1.8;
      hy = -0.418 + 0.02 * Math.cos(2 * ph); ta = 0.24; R.ha = -0.12; R.wind = 0.8; R.speed = 1;
      for (let leg = 0; leg < 2; leg++) {
        const p = ((ph + leg * PI) % TAU + TAU) % TAU;
        const fx = 0.2 * Math.cos(p) + 0.03;
        const fy = p < PI ? 0 : -0.19 * Math.sin(p - PI) * (1 - 0.5 * Math.cos(p));
        const rotF = p < PI ? (p < 0.35 ? -0.25 * (1 - p / 0.35) : (p > PI - 0.6 ? 0.5 * (p - (PI - 0.6)) / 0.6 : 0)) : 0.4 * Math.sin(p - PI) + 0.1;
        if (leg === 0) { nfx = fx; nfy = fy; nf = rotF; } else { ffx = fx; ffy = fy; ff = rotF; }
      }
      if (!coinVis) {
        arms = 'free';
        const a1 = -0.95 * Math.cos(ph), b1 = 0.95 * Math.cos(ph);
        nhx = Math.sin(a1) * RG.upper + Math.sin(a1 + 1.65) * RG.fore; nhy = Math.cos(a1) * RG.upper + Math.cos(a1 + 1.65) * RG.fore;
        fhx = Math.sin(b1) * RG.upper + Math.sin(b1 + 1.65) * RG.fore; fhy = Math.cos(b1) * RG.upper + Math.cos(b1 + 1.65) * RG.fore;
      }
      expr = 'determined';
      R.rot = lean * 0.18;
      break;
    }
    case 'slide': {
      const jit = Math.sin(t * 57) * 0.004;
      hx = -0.03 + jit; hy = -0.36; ta = -0.3 + Math.sin(t * 9) * 0.02; R.ha = 0.18; R.wind = 0.6; R.dust = 1;
      nfx = 0.27; nfy = 0; nf = -0.45; ffx = 0.0; ffy = 0; ff = 0.1;
      if (!coinVis) { arms = 'free'; nhx = -0.17 + Math.sin(t * 8) * 0.02; nhy = 0.1; fhx = -0.24; fhy = -0.02 + Math.sin(t * 7 + 1) * 0.03; }
      expr = 'ooh';
      R.rot = lean * 0.12;
      break;
    }
    case 'lean': {
      const a = clamp(0.32 + 0.38 * lean, -0.1, 0.75);
      const ph = t * TAU * 0.75;
      hy = -0.415; ta = 0.12 + a * 0.85; R.ha = -0.25 * a; R.wind = 0.6 + 0.6 * Math.abs(a);
      nfx = -0.2 - 0.12 * a + 0.025 * Math.sin(ph); nf = 0.35 * a; ffx = 0.13 + 0.03 * Math.sin(ph + PI); ffy = -0.012 * Math.max(0, Math.sin(ph)); ff = -0.05;
      hx = -0.03 * a;
      if (!coinVis) { arms = 'free'; nhx = 0.2; nhy = -0.08; fhx = -0.16; fhy = 0.18; }
      expr = a > 0.35 ? 'effort' : 'determined';
      break;
    }
    case 'kneel': {
      const sob = Math.sin(t * TAU * 1.1);
      hx = -0.02; hy = -0.245 + 0.006 * sob; ta = 0.36 + 0.025 * sob; R.ha = 0.32;
      nfx = -0.17; nfy = 0.012; nf = 2.95; ffx = -0.21; ffy = 0.012; ff = 2.95;
      R.coin = 'none';
      arms = 'free'; nhx = 0.1; nhy = 0.29; fhx = 0.05; fhy = 0.3;
      expr = 'sad';
      break;
    }
    case 'ride': {
      const w = Math.sin(t * TAU * 0.55);
      R.board = w * 0.07 + lean * 0.12; R.coin = 'board'; R.wind = 1; R.speed = 1;
      hx = -0.01; hy = -0.385 + 0.012 * Math.sin(t * TAU * 1.1); ta = 0.2; R.ha = -0.08;
      const bc = Math.cos(R.board), bs = Math.sin(R.board);
      nfx = 0.13 * bc; nfy = -0.115 + 0.13 * bs; ffx = -0.13 * bc; ffy = -0.115 - 0.13 * bs; nf = R.board; ff = R.board;
      arms = 'free'; nhx = 0.24; nhy = 0.1 + 0.02 * w; fhx = -0.21; fhy = -0.04 - 0.02 * w;
      R.cane = 'far';
      expr = 'grin';
      break;
    }
    case 'aim': {
      hy = -0.44; ta = 0.05; nfx = 0.15; ffx = -0.13; nf = 0; ff = 0;
      arms = 'free'; nhx = 0.29; nhy = 0.0 + Math.sin(t * 2.3) * 0.004; fhx = 0.24; fhy = 0.04;
      R.coin = 'none';
      expr = 'focus';
      R.rot = lean * 0.1;
      break;
    }
    case 'cheer': {
      const u = frac(t / 0.95), air = 4 * u * (1 - u);
      R.lift = 0.17 * Math.pow(air, 0.8);
      if (u < 0.07 || u > 0.93) { R.sqy = 0.88; R.sqx = 1.1; } else { R.sqy = 1 + 0.05 * air; R.sqx = 1 - 0.03 * air; }
      hy = -0.44 + (u < 0.07 || u > 0.93 ? 0.04 : 0);
      nfx = 0.07; nfy = -0.11 * air; ffx = -0.08; ffy = -0.15 * air; nf = 0.25 * air; ff = 0.45 * air;
      arms = 'free';
      const wave = Math.sin(t * TAU * 2.2) * 0.03;
      if (coinVis) { R.coin = 'overhead'; nhx = 0.12; nhy = -0.3; fhx = -0.1; fhy = -0.3; }
      else { nhx = 0.15 + wave; nhy = -0.27; fhx = -0.12 - wave; fhy = -0.27; }
      expr = 'joy';
      break;
    }
    case 'hold': {
      hy = -0.445 + 0.004 * breath; ta = 0.02; nfx = 0.06; ffx = -0.06; R.ha = 0.02 * breath;
      if (!coinVis) { arms = 'free'; nhx = 0.12; nhy = 0.2; fhx = 0.13; fhy = 0.19; }
      expr = 'smile';
      break;
    }
    case 'tackle': {
      hx = -0.1; hy = -0.43 + Math.sin(t * TAU * 1.3) * 0.015; ta = 1.3; R.ha = -0.2; R.wind = 1; R.speed = 1;
      legBend = -1;
      nfx = -0.5; nfy = -0.44; ffx = -0.46; ffy = -0.33; nf = -1.35; ff = -1.15;
      arms = 'free'; nhx = 0.3; nhy = 0.02; fhx = 0.28; fhy = 0.07;
      R.coin = coinVis ? 'tuck' : 'none';
      expr = 'effort';
      break;
    }
    case 'fly': {
      const sw = Math.sin(t * TAU * 0.5) * 0.11;
      R.fly = sw; R.lift = 0;
      hx = 0; hy = -0.535; ta = -0.02; R.ha = -0.22; R.wind = 0.3;
      const k = Math.sin(t * TAU * 1.5);
      nfx = 0.04 + 0.08 * k; nfy = -0.115 - 0.03 * Math.max(0, k); ffx = -0.05 - 0.08 * k; ffy = -0.13 + 0.03 * Math.min(0, k); nf = 0.45; ff = 0.55;
      arms = 'free'; nhx = 0.012; nhy = -0.29; fhx = -0.012; fhy = -0.29;
      R.coin = 'none';
      expr = 'ooh';
      break;
    }
    default: { // idle
      hy = -0.445 + 0.004 * breath; ta = 0.03; R.ha = 0.03 * breath;
      nfx = 0.065; ffx = -0.06;
      if (!coinVis) { arms = 'free'; nhx = 0.04; nhy = 0.29; fhx = -0.05; fhy = 0.285; }
      expr = 'smile';
      R.rot = lean * 0.15;
    }
  }
  R.hx = hx; R.hy = hy; R.ta = ta;
  const ux = Math.sin(ta), uy = -Math.cos(ta);
  R.sx = hx + ux * RG.torso; R.sy = hy + uy * RG.torso;
  R.hdx = R.sx + ux * 0.158 + Math.cos(ta) * 0.018; R.hdy = R.sy + uy * 0.158 + Math.sin(ta) * 0.018;
  R.ha += ta * 0.35;
  ik(hx, hy, nfx, nfy - RG.ankle, RG.thigh, RG.shin, legBend, R.ln);
  ik(hx - 0.012, hy, ffx, ffy - RG.ankle, RG.thigh, RG.shin, legBend, R.lf);
  R.fn = nf; R.ff = ff;
  // the coin: held in front of the chest, both arms behind it, only the hands grip the rim (the face stays visible)
  if (R.coin === 'hug') { R.cx = R.sx - ux * 0.13 + Math.cos(ta) * 0.165; R.cy = R.sy - uy * 0.13 + Math.sin(ta) * 0.165; R.cr = 0.17; }
  else if (R.coin === 'overhead') { R.cx = R.sx + 0.02; R.cy = R.sy - 0.5; R.cr = 0.17; }
  else if (R.coin === 'tuck') { R.cx = R.hx - Math.cos(ta) * 0.02 + ux * 0.12; R.cy = R.hy + uy * 0.12 + Math.sin(ta) * 0.02; R.cr = 0.15; }
  else if (R.coin === 'board') { R.cx = 0; R.cy = -0.07; R.cr = 0.34; }
  if (arms === 'hug') {
    ik(R.sx, R.sy, R.cx - 0.105, R.cy + 0.115, RG.upper, RG.fore, -1, R.an);
    ik(R.sx - 0.01, R.sy, R.cx + 0.1, R.cy - 0.115, RG.upper, RG.fore, -1, R.af);
  } else if (R.coin === 'overhead') {
    ik(R.sx, R.sy, R.cx + 0.13, R.cy + 0.1, RG.upper, RG.fore, 1, R.an);
    ik(R.sx - 0.01, R.sy, R.cx - 0.13, R.cy + 0.1, RG.upper, RG.fore, -1, R.af);
  } else {
    const nb = pose === 'cheer' || pose === 'fly' ? 1 : -1;
    ik(R.sx, R.sy, R.sx + nhx, R.sy + nhy, RG.upper, RG.fore, nb, R.an);
    ik(R.sx - 0.01, R.sy, R.sx + fhx, R.sy + fhy, RG.upper, RG.fore, pose === 'cheer' ? -1 : (pose === 'fly' ? -1 : -1), R.af);
  }
  R.expr = expr;
  R.look = num(look, 0);
}

// -------------------------------------------------------------------------------- outfits (skins on the rig)
const DUSTY = (c) => MX(c, '#b9ae98', 0.42);
const OUT = {
  suit: { torso: 'suit', shirt: P.shirt, sleeve: P.shirt, fore: P.skin, hand: P.skin, leg: P.suit, shin: P.suit, shoe: '#6b4226',
    cap: '#6e5a42', scarf: P.emerald, suspenders: P.suspender, rolled: true, expr: null },
  tux: { torso: 'tux', shirt: P.tux, sleeve: P.tux, fore: P.tux, hand: '#f7f5ee', leg: '#1d1d27', shin: '#1d1d27', shoe: '#111116',
    spats: true, tails: true, cap: null, hat: true, cane: true, expr: 'smug' },
  undershirt: { torso: 'undershirt', shirt: P.undershirt, sleeve: P.skin, fore: P.skin, hand: P.skin, leg: P.suit, shin: P.suit, shoe: '#6b4226',
    cap: null, hair: 'messy', tornKnee: true, dangle: P.suspender, expr: 'worried' },
  boxers: { torso: 'boxers', shirt: P.skin, sleeve: P.skin, fore: P.skin, hand: P.skin, leg: P.skin, shin: P.skin, shoe: '#26211d',
    socks: '#2b2b33', cap: null, hair: 'wild', blush: true, expr: 'panic' },
  dusty: { torso: 'suit', shirt: DUSTY(P.shirt), sleeve: DUSTY(P.shirt), fore: P.skin, hand: P.skin, leg: DUSTY(P.suit), shin: DUSTY(P.suit),
    shoe: DUSTY('#6b4226'), cap: DUSTY('#6e5a42'), capTilt: 0.35, scarf: DUSTY(P.emerald), suspenders: DUSTY(P.suspender), rolled: true,
    dust: true, tornKnee: true, tornElbow: true, expr: 'sad' },
  barrel: { torso: 'barrel', shirt: P.skin, sleeve: P.skin, fore: P.skin, hand: P.skin, leg: P.skin, shin: P.skin, shoe: '#6b4226',
    cap: null, hair: 'messy', expr: 'sad' },
  staked: { torso: 'suit', shirt: P.shirt, sleeve: P.shirt, fore: P.skin, hand: P.skin, leg: P.suit, shin: P.suit, shoe: '#6b4226',
    cap: '#6e5a42', scarf: P.emerald, suspenders: P.suspender, rolled: true, halfBack: true, expr: 'proud' },
};
const _woodified = new Map();
const BEECH = '#e0b273';
function woodify(O) {
  let W = _woodified.get(O);
  if (!W) {
    W = Object.assign({}, O);
    // the Apprentice is a carved puppet: pale varnished beech with dark grain (never a brown skin tone)
    for (const k of ['shirt', 'sleeve', 'fore', 'leg', 'shin']) if (W[k] === P.skin) W[k] = BEECH;
    W.hand = O.hand === P.skin ? BEECH : O.hand;
    W.woodSkin = true; W.skinC = BEECH; W.skinShadeC = '#a8743a'; W.blush = false;
    _woodified.set(O, W);
  }
  return W;
}
const WOOD = { torso: 'wood', shirt: P.wood, sleeve: P.wood, fore: P.wood, hand: '#c48a4c', leg: P.wood, shin: P.wood, shoe: '#8a5a2b', cap: null, expr: 'wood' };
const TWIN = { torso: 'twin', shirt: P.twinBrass, sleeve: P.twinBrass, fore: P.twinBrass, hand: P.brassLight, leg: P.twinBrass, shin: P.twinBrass, shoe: P.brassDark, cap: null, expr: 'twin' };

// -------------------------------------------------------------------------------- part painters (unit space, facing right)
function shoe(c, x, y, rot, col, far, spats) {
  c.save(); c.translate(x, y); c.rotate(rot);
  const base = far ? DK(col, 0.18) : col;
  c.beginPath();
  c.moveTo(-0.045, -0.02); c.quadraticCurveTo(-0.03, -0.045, 0.02, -0.04);
  c.quadraticCurveTo(0.09, -0.038, 0.118, 0.0); c.quadraticCurveTo(0.13, 0.04, 0.09, 0.042);
  c.lineTo(-0.04, 0.042); c.quadraticCurveTo(-0.062, 0.02, -0.045, -0.02); c.closePath();
  fo(c, base);
  c.fillStyle = DK(base, 0.45); c.fillRect(-0.04, 0.03, 0.13, 0.012);
  if (spats) { c.beginPath(); c.moveTo(-0.045, -0.02); c.quadraticCurveTo(-0.02, -0.05, 0.035, -0.038); c.lineTo(0.04, 0.012); c.lineTo(-0.048, 0.012); c.closePath(); fo(c, far ? '#cfcac0' : '#f2efe6', LINE.inkThin); }
  c.fillStyle = 'rgba(255,255,255,0.55)'; c.beginPath(); c.ellipse(0.075, -0.012, 0.022, 0.009, -0.3, 0, TAU); c.fill();
  c.restore();
}
function hand(c, x, y, col, far, r = RG.handR) {
  const base = far ? DK(col, 0.15) : col;
  c.beginPath(); c.arc(x, y, r, 0, TAU); fo(c, base);
  c.fillStyle = LI(base, 0.35); c.beginPath(); c.arc(x - r * 0.35, y - r * 0.35, r * 0.32, 0, TAU); c.fill();
}
// a two-segment limb with one ink pass, two colour passes and a highlight
function limb2(c, a, w, col1, col2) {
  c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(a[2], a[3]); c.lineTo(a[4], a[5]);
  c.strokeStyle = P.ink; c.lineWidth = w + LINE.ink; c.stroke();
  c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(a[2], a[3]); c.strokeStyle = col1; c.lineWidth = w; c.stroke();
  c.beginPath(); c.moveTo(a[2], a[3]); c.lineTo(a[4], a[5]); c.strokeStyle = col2; c.lineWidth = w; c.stroke();
  c.save(); c.translate(-w * 0.17, -w * 0.12);
  c.lineWidth = w * 0.24;
  c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(a[2], a[3]); c.strokeStyle = LI(col1, 0.3); c.stroke();
  c.beginPath(); c.moveTo(a[2], a[3]); c.lineTo(a[4], a[5]); c.strokeStyle = LI(col2, 0.3); c.stroke();
  c.restore();
}
function leg(c, a, O, far, footRot) {
  const k = far ? 0.16 : 0;
  const thighC = k ? DK(O.leg, k) : O.leg, shinC = k ? DK(O.shin, k) : O.shin;
  if (O.torso === 'wood' || O.torso === 'twin') {
    limb2(c, a, RG.legW * 0.82, thighC, shinC);
    joint(c, a[2], a[3], O, far, 0.042);
  } else if (O.torso === 'boxers' || O.torso === 'barrel') {
    limb2(c, a, RG.legW * 0.8, thighC, shinC);
    if (O.socks) { c.beginPath(); c.moveTo(lerp(a[2], a[4], 0.55), lerp(a[3], a[5], 0.55)); c.lineTo(a[4], a[5]);
      c.strokeStyle = P.ink; c.lineWidth = RG.legW * 0.86 + LINE.ink; c.stroke(); c.strokeStyle = far ? DK(O.socks, 0.15) : O.socks; c.lineWidth = RG.legW * 0.86; c.stroke();
      // garter clip
      const gx = lerp(a[2], a[4], 0.55), gy = lerp(a[3], a[5], 0.55);
      c.fillStyle = P.crimson; c.fillRect(gx - 0.012, gy - 0.008, 0.024, 0.016); }
    if (O.woodSkin) joint(c, a[2], a[3], WOOD, far, 0.038);
    // a few leg hairs
    if (!far && !O.woodSkin) { c.strokeStyle = P.inkSoft; c.lineWidth = LINE.hair;
      for (let i = 0; i < 3; i++) { const u = 0.15 + i * 0.12, px = lerp(a[2], a[4], u), py = lerp(a[3], a[5], u); c.beginPath(); c.moveTo(px + 0.02, py); c.lineTo(px + 0.035, py - 0.012); c.stroke(); } }
  } else {
    limb2(c, a, RG.legW, thighC, shinC);
    // trouser crease highlight + cuff
    const ex = a[4], ey = a[5], dx = a[4] - a[2], dy = a[5] - a[3], dl = Math.hypot(dx, dy) || 1;
    c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin;
    c.beginPath(); c.moveTo(ex - dx / dl * 0.03 - dy / dl * 0.04, ey - dy / dl * 0.03 + dx / dl * 0.04); c.lineTo(ex - dx / dl * 0.03 + dy / dl * 0.042, ey - dy / dl * 0.03 - dx / dl * 0.042); c.stroke();
    if (O.tornKnee && !far) {
      c.fillStyle = O.skinC || P.skin; c.beginPath(); c.ellipse(a[2] + 0.01, a[3] + 0.005, 0.024, 0.02, 0, 0, TAU); c.fill();
      c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin; c.beginPath();
      for (let i = 0; i <= 6; i++) { const ang = (i / 6) * TAU, rr = i % 2 ? 0.02 : 0.03; const px = a[2] + 0.01 + Math.cos(ang) * rr, py = a[3] + 0.005 + Math.sin(ang) * rr * 0.8; i ? c.lineTo(px, py) : c.moveTo(px, py); }
      c.closePath(); c.stroke();
    }
    if (O.torso === 'tux' && !far) { c.strokeStyle = '#3a3a4a'; c.lineWidth = 0.012; c.beginPath(); c.moveTo(a[0] + 0.02, a[1] + 0.02); c.lineTo(a[2] + 0.025, a[3]); c.lineTo(a[4] + 0.022, a[5] - 0.02); c.stroke(); }
  }
  shoe(c, a[4], a[5], footRot, O.shoe, far, O.spats);
}
function joint(c, x, y, O, far, r) {
  c.beginPath(); c.arc(x, y, r, 0, TAU);
  if (O.torso === 'twin') { fo(c, far ? DK(P.brass, 0.2) : P.brass, LINE.inkThin); rivetU(c, x, y, r * 0.35); }
  else { fo(c, far ? DK('#9a6634', 0.15) : '#9a6634', LINE.inkThin); c.fillStyle = 'rgba(255,255,255,0.35)'; c.beginPath(); c.arc(x - r * 0.3, y - r * 0.3, r * 0.35, 0, TAU); c.fill(); }
}
function arm(c, a, O, far, noHand) {
  const k = far ? 0.16 : 0;
  const up = k ? DK(O.sleeve, k) : O.sleeve, fo2 = k ? DK(O.fore, k) : O.fore;
  const w = O.torso === 'wood' || O.torso === 'twin' ? RG.armW * 0.82 : (O.sleeve === P.skin || O.sleeve === P.wood ? RG.armW * 0.85 : RG.armW);
  limb2(c, a, w, up, fo2);
  if (O.torso === 'wood' || O.torso === 'twin') { joint(c, a[0], a[1], O, far, 0.036); joint(c, a[2], a[3], O, far, 0.034); }
  else if (O.woodSkin && O.sleeve === P.wood) joint(c, a[2], a[3], WOOD, far, 0.032);
  if (O.rolled) {   // rolled-up sleeve cuff at the elbow
    const dx = a[2] - a[0], dy = a[3] - a[1], dl = Math.hypot(dx, dy) || 1;
    const cx = a[2] - dx / dl * 0.01, cy = a[3] - dy / dl * 0.01;
    c.save(); c.translate(cx, cy); c.rotate(Math.atan2(dy, dx));
    c.beginPath(); c.ellipse(0, 0, 0.026, w * 0.68, 0, 0, TAU); fo(c, k ? DK(LI(O.sleeve, 0.1), k) : LI(O.sleeve, 0.1), LINE.inkThin);
    c.restore();
    if (O.tornElbow && !far) { c.fillStyle = O.skinC || P.skin; c.beginPath(); c.arc(lerp(a[0], a[2], 0.6), lerp(a[1], a[3], 0.6), 0.016, 0, TAU); c.fill(); }
  }
  if (O.torso === 'tux') {   // white shirt cuff
    const dx = a[4] - a[2], dy = a[5] - a[3], dl = Math.hypot(dx, dy) || 1;
    c.save(); c.translate(a[4] - dx / dl * 0.035, a[5] - dy / dl * 0.035); c.rotate(Math.atan2(dy, dx));
    c.fillStyle = far ? '#d8d4ca' : '#f4f1ea'; c.fillRect(-0.012, -w * 0.5, 0.024, w); c.restore();
  }
  if (!noHand) hand(c, a[4], a[5], O.hand, far);
}
// the torso in its own frame (origin at the hip, -y up the spine)
function torso(c, O, t, wind) {
  const ty = -RG.torso;
  const path = () => {
    c.beginPath();
    c.moveTo(-0.078, 0.02); c.lineTo(0.074, 0.02);
    c.quadraticCurveTo(0.098, -0.12, 0.072, ty + 0.02);
    c.quadraticCurveTo(0.05, ty - 0.012, 0.0, ty - 0.012);
    c.quadraticCurveTo(-0.07, ty - 0.01, -0.075, ty + 0.04);
    c.quadraticCurveTo(-0.092, -0.1, -0.078, 0.02); c.closePath();
  };
  const T = O.torso;
  if (T === 'suit') {
    path(); shadeU(c, -0.09, ty, 0.19, 0.27, O.shirt); ink(c); c.stroke();
    // shirt folds
    c.strokeStyle = RA(P.ink, 0.35); c.lineWidth = LINE.hair * 1.4;
    c.beginPath(); c.moveTo(0.03, -0.17); c.quadraticCurveTo(0.05, -0.12, 0.035, -0.07); c.stroke();
    // trousers waist + belt line
    c.beginPath(); c.moveTo(-0.08, 0.02); c.lineTo(0.076, 0.02); c.lineTo(0.08, -0.05); c.lineTo(-0.084, -0.05); c.closePath(); fo(c, O.leg);
    // suspenders
    c.strokeStyle = P.ink; c.lineWidth = 0.034; c.beginPath(); c.moveTo(0.045, -0.045); c.quadraticCurveTo(0.075, -0.16, 0.03, ty + 0.005); c.stroke();
    c.beginPath(); c.moveTo(-0.055, -0.045); c.quadraticCurveTo(-0.07, -0.16, -0.035, ty + 0.0); c.stroke();
    c.strokeStyle = O.suspenders; c.lineWidth = 0.02; c.beginPath(); c.moveTo(0.045, -0.045); c.quadraticCurveTo(0.075, -0.16, 0.03, ty + 0.005); c.stroke();
    c.strokeStyle = DK(O.suspenders, 0.25); c.beginPath(); c.moveTo(-0.055, -0.045); c.quadraticCurveTo(-0.07, -0.16, -0.035, ty + 0.0); c.stroke();
    c.fillStyle = P.gold; c.beginPath(); c.arc(0.046, -0.05, 0.011, 0, TAU); c.fill(); c.strokeStyle = P.ink; c.lineWidth = LINE.hair; c.stroke();
    // collar
    c.beginPath(); c.moveTo(0.0, ty - 0.008); c.lineTo(0.05, ty + 0.03); c.lineTo(0.06, ty - 0.005); c.closePath(); fo(c, LI(O.shirt, 0.2), LINE.inkThin);
    if (O.dust) { c.fillStyle = RA('#8f8370', 0.55); for (let i = 0; i < 5; i++) { c.beginPath(); c.arc(-0.05 + rand(i * 3.1) * 0.1, -0.03 - rand(i * 7.7) * 0.2, 0.008 + rand(i) * 0.008, 0, TAU); c.fill(); } }
  } else if (T === 'tux') {
    path(); shadeU(c, -0.09, ty, 0.19, 0.27, P.tux); ink(c); c.stroke();
    // shirt front (white V) and lapels
    c.beginPath(); c.moveTo(0.01, ty - 0.005); c.lineTo(0.07, ty + 0.03); c.quadraticCurveTo(0.085, -0.13, 0.07, -0.07); c.lineTo(0.04, -0.06); c.closePath(); fo(c, P.shirt, LINE.inkThin);
    c.beginPath(); c.moveTo(0.0, ty); c.lineTo(0.045, -0.07); c.lineTo(0.02, -0.06); c.lineTo(-0.02, ty + 0.03); c.closePath(); fo(c, P.tuxLapel, LINE.inkThin);
    c.fillStyle = 'rgba(255,255,255,0.25)'; c.beginPath(); c.moveTo(0.004, ty + 0.01); c.lineTo(0.03, -0.09); c.lineTo(0.024, -0.09); c.closePath(); c.fill();
    // studs, white bow tie, red carnation, gold watch chain
    c.fillStyle = P.ink; for (let i = 0; i < 2; i++) { c.beginPath(); c.arc(0.062, -0.17 + i * 0.045, 0.006, 0, TAU); c.fill(); }
    c.beginPath(); c.moveTo(0.05, ty + 0.03); c.lineTo(0.09, ty + 0.012); c.lineTo(0.09, ty + 0.05); c.closePath(); c.moveTo(0.05, ty + 0.03); c.lineTo(0.015, ty + 0.012); c.lineTo(0.015, ty + 0.05); c.closePath(); fo(c, '#ffffff', LINE.inkThin);
    c.beginPath(); c.arc(-0.012, -0.175, 0.016, 0, TAU); fo(c, P.crimson, LINE.inkThin);
    c.strokeStyle = P.gold; c.lineWidth = 0.008; c.beginPath(); c.moveTo(0.06, -0.08); c.quadraticCurveTo(0.02, -0.04, -0.03, -0.075); c.stroke();
  } else if (T === 'undershirt') {
    path(); shadeU(c, -0.09, ty, 0.19, 0.27, O.skinC || P.skin); ink(c); c.stroke();
    // the tank top (with rips) over the skin
    c.beginPath(); c.moveTo(-0.078, 0.0); c.lineTo(0.074, 0.0); c.quadraticCurveTo(0.098, -0.12, 0.07, ty + 0.05);
    c.lineTo(0.045, ty + 0.0); c.quadraticCurveTo(0.02, ty + 0.06, -0.035, ty + 0.0); c.quadraticCurveTo(-0.09, -0.1, -0.078, 0.0); c.closePath();
    shadeU(c, -0.09, ty, 0.19, 0.27, O.shirt); ink(c, LINE.inkThin); c.stroke();
    c.strokeStyle = RA(P.ink, 0.25); c.lineWidth = LINE.hair; for (let i = 0; i < 5; i++) { c.beginPath(); c.moveTo(-0.05 + i * 0.025, -0.02); c.lineTo(-0.045 + i * 0.026, ty + 0.08); c.stroke(); }
    // rips: jagged dark holes showing skin
    const rip = (x, y, r) => { c.beginPath(); for (let i = 0; i < 8; i++) { const a = i / 8 * TAU, rr = r * (i % 2 ? 0.45 : 1); i ? c.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr * 0.8) : c.moveTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr * 0.8); } c.closePath(); c.fillStyle = O.skinShadeC || P.skinShade; c.fill(); c.strokeStyle = P.ink; c.lineWidth = LINE.hair * 1.5; c.stroke(); };
    rip(0.03, -0.15, 0.03); rip(-0.035, -0.07, 0.022); rip(0.05, -0.04, 0.018);
    c.beginPath(); c.moveTo(-0.08, 0.02); c.lineTo(0.076, 0.02); c.lineTo(0.078, -0.035); c.lineTo(-0.082, -0.035); c.closePath(); fo(c, O.leg);
    // dangling suspenders (loops at the hip, swinging)
    const sw = Math.sin(t * 5) * 0.03 - wind * 0.04;
    c.strokeStyle = P.ink; c.lineWidth = 0.032; c.beginPath(); c.moveTo(0.05, -0.0); c.quadraticCurveTo(0.07 + sw, 0.13, 0.0 + sw, 0.15); c.quadraticCurveTo(-0.04 + sw, 0.12, -0.05, 0.0); c.stroke();
    c.strokeStyle = O.dangle; c.lineWidth = 0.018; c.stroke();
  } else if (T === 'boxers') {
    path(); shadeU(c, -0.09, ty, 0.19, 0.27, O.skinC || P.skin); ink(c); c.stroke();
    c.strokeStyle = RA(P.ink, O.woodSkin ? 0 : 0.5); c.lineWidth = LINE.hair * 1.4;
    c.beginPath(); c.moveTo(0.03, -0.17); c.lineTo(0.036, -0.162); c.moveTo(0.05, -0.18); c.lineTo(0.055, -0.17); c.moveTo(0.045, -0.155); c.lineTo(0.05, -0.147); c.stroke();
    c.beginPath(); c.arc(0.05, -0.065, 0.006, 0, TAU); c.stroke();   // belly button
  } else if (T === 'barrel') {
    path(); shadeU(c, -0.09, ty, 0.19, 0.27, O.skinC || P.skin); ink(c); c.stroke();
  } else if (T === 'wood') {
    // two carved blocks + a dowel waist (an artist's mannequin)
    c.beginPath(); c.ellipse(0, -0.02, 0.07, 0.055, 0, 0, TAU); shadeU(c, -0.07, -0.08, 0.14, 0.11, P.wood); ink(c); c.stroke();
    c.beginPath(); c.moveTo(-0.075, -0.1); c.quadraticCurveTo(-0.09, ty, -0.02, ty - 0.01); c.lineTo(0.05, ty - 0.01); c.quadraticCurveTo(0.1, ty + 0.02, 0.08, -0.1); c.quadraticCurveTo(0.0, -0.06, -0.075, -0.1); c.closePath();
    shadeU(c, -0.09, ty, 0.19, 0.16, P.wood); ink(c); c.stroke();
    c.strokeStyle = RA('#6b4520', 0.6); c.lineWidth = LINE.hair; for (let i = 0; i < 3; i++) { c.beginPath(); c.arc(0.0, -0.17, 0.03 + i * 0.022, -2.6, -0.6); c.stroke(); }
  } else if (T === 'twin') {
    // a brass boiler chest with a gear window and a gauge
    path(); shadeU(c, -0.09, ty, 0.19, 0.27, P.twinBrass); ink(c); c.stroke();
    c.strokeStyle = RA(P.brassDark, 0.9); c.lineWidth = 0.012;
    c.beginPath(); c.moveTo(-0.08, -0.06); c.lineTo(0.085, -0.06); c.moveTo(-0.085, -0.19); c.lineTo(0.08, -0.19); c.stroke();
    for (let i = 0; i < 4; i++) { rivetU(c, -0.06 + i * 0.04, -0.06, 0.008); rivetU(c, -0.06 + i * 0.04, -0.19, 0.008); }
    c.beginPath(); c.arc(0.015, -0.125, 0.045, 0, TAU); fo(c, '#2a2118', LINE.inkThin);
    gear(c, 0.015, -0.125, 0.036, 8, t * 2.2, P.brassLight);
    c.beginPath(); c.arc(0.015, -0.125, 0.045, 0, TAU); ink(c, LINE.inkThin, P.brassDark); c.stroke();
  }
}
function gear(c, x, y, r, teeth, a, col) {
  c.save(); c.translate(x, y); c.rotate(a);
  c.beginPath();
  for (let i = 0; i < teeth * 2; i++) { const ang = (i / (teeth * 2)) * TAU, rr = i % 2 ? r * 0.78 : r; c.lineTo(Math.cos(ang - 0.12) * rr, Math.sin(ang - 0.12) * rr); c.lineTo(Math.cos(ang + 0.12) * rr, Math.sin(ang + 0.12) * rr); }
  c.closePath(); c.fillStyle = col; c.fill(); c.strokeStyle = P.ink; c.lineWidth = LINE.hair * 1.2; c.stroke();
  c.beginPath(); c.arc(0, 0, r * 0.28, 0, TAU); c.fillStyle = DK(col, 0.35); c.fill();
  c.restore();
}
// the head in its own frame (centre, facing right)
function head(c, O, st, t, expr, hatOn) {
  const r = RG.headR;
  const T = O.torso;
  if (T === 'wood' || O.woodSkin) {
    const wc = O.woodSkin ? BEECH : P.wood;
    c.beginPath(); c.ellipse(0, 0.005, r * 0.92, r, 0, 0, TAU); shadeU(c, -r, -r, r * 2, r * 2, wc); ink(c); c.stroke();
    // carved grain sweeping across the face and a knot on the cheek, clipped to the head; then the varnish shine
    c.save(); c.beginPath(); c.ellipse(0, 0.005, r * 0.92, r, 0, 0, TAU); c.clip();
    c.strokeStyle = RA('#6b3d14', 0.38); c.lineWidth = LINE.hair * 1.2;
    for (let i = -3; i <= 3; i++) { const yy = i * 0.042; c.beginPath(); c.moveTo(-r, yy - 0.012); c.bezierCurveTo(-0.05, yy - 0.04, 0.04, yy + 0.022, r, yy - 0.006); c.stroke(); }
    c.beginPath(); c.ellipse(-0.07, 0.055, 0.024, 0.015, 0.4, 0, TAU); c.stroke();
    c.beginPath(); c.ellipse(-0.07, 0.055, 0.01, 0.006, 0.4, 0, TAU); c.stroke();
    c.restore();
    c.fillStyle = 'rgba(255,255,255,0.38)'; c.beginPath(); c.ellipse(-0.045, -0.07, 0.048, 0.022, -0.5, 0, TAU); c.fill();
    c.strokeStyle = RA('#6b4520', 0.5); c.lineWidth = LINE.hair; c.beginPath(); c.arc(-0.02, -0.03, 0.06, -2.4, -0.7); c.stroke();
    const bl = blinkAt(t, 0.4);
    c.fillStyle = P.ink;
    if (bl) { c.fillRect(0.03, -0.012, 0.032, 0.008); c.fillRect(0.088, -0.014, 0.024, 0.008); }
    else { c.beginPath(); c.arc(0.048, -0.01, 0.017, 0, TAU); c.arc(0.1, -0.012, 0.014, 0, TAU); c.fill(); c.fillStyle = '#fff'; c.beginPath(); c.arc(0.053, -0.016, 0.006, 0, TAU); c.fill(); }
    c.fillStyle = RA(P.crimson, 0.45); c.beginPath(); c.ellipse(0.06, 0.04, 0.022, 0.013, 0, 0, TAU); c.fill();
    // the painted mouth follows the mood (the clothes still tell the result)
    c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin;
    if (expr === 'sad' || expr === 'worried') { c.beginPath(); c.arc(0.08, 0.085, 0.028, PI * 1.2, PI * 1.85); c.stroke(); }
    else if (expr === 'panic' || expr === 'ooh') { c.beginPath(); c.ellipse(0.085, 0.06, 0.014, 0.018, 0, 0, TAU); c.fillStyle = '#4a2a14'; c.fill(); c.stroke(); }
    else if (expr === 'determined' || expr === 'effort' || expr === 'focus') { c.beginPath(); c.moveTo(0.055, 0.06); c.lineTo(0.11, 0.055); c.stroke(); }
    else { c.beginPath(); c.arc(0.08, 0.035, 0.032, 0.35, 1.9); c.stroke(); }
    if (T === 'wood') { if (hatOn) topHat(c, '#9a6634', '#6b4520'); return; }
    if (hatOn) topHat(c, '#15151c', P.crimson);
    else if (O.cap) newsCap(c, O.cap, O.capTilt || 0);
    return;
  }
  if (T === 'twin') {
    c.beginPath(); c.arc(0, 0, r * 0.95, 0, TAU); shadeU(c, -r, -r, r * 2, r * 2, P.twinBrass); ink(c); c.stroke();
    c.strokeStyle = P.brassDark; c.lineWidth = 0.01; c.beginPath(); c.arc(0, 0, r * 0.95, PI * 1.05, PI * 1.95); c.stroke();
    rivetU(c, -0.08, -0.06, 0.009); rivetU(c, -0.1, 0.02, 0.009); rivetU(c, -0.06, 0.09, 0.009);
    // the EA visor: dark glass band with a sweeping light
    c.beginPath(); c.moveTo(-0.03, -0.05); c.lineTo(0.16, -0.055); c.quadraticCurveTo(0.175, 0.0, 0.155, 0.03); c.lineTo(-0.03, 0.03); c.closePath(); fo(c, '#0b2a2c');
    const sweep = (Math.sin(t * 2.4) * 0.5 + 0.5);
    c.save(); c.beginPath(); c.moveTo(-0.03, -0.05); c.lineTo(0.16, -0.055); c.quadraticCurveTo(0.175, 0.0, 0.155, 0.03); c.lineTo(-0.03, 0.03); c.closePath(); c.clip();
    c.fillStyle = RA(P.cyan, 0.85); c.fillRect(-0.03 + sweep * 0.15, -0.06, 0.035, 0.1);
    c.restore();
    glowU(c, 0.0 + sweep * 0.15, -0.012, 0.09, P.cyan, 0.5);
    textU(c, 'EA', 0.075, -0.011, 0.05, { color: P.cyanGlow, font: FONT.sign });
    // a little whistle that puffs
    c.fillStyle = P.brassDark; c.fillRect(-0.02, -r - 0.03, 0.03, 0.04); c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin; c.strokeRect(-0.02, -r - 0.03, 0.03, 0.04);
    const pf = frac(t * 0.6);
    if (pf < 0.5) { c.fillStyle = RA('#ffffff', 0.6 * (1 - pf * 2)); c.beginPath(); c.arc(-0.005 - pf * 0.06, -r - 0.05 - pf * 0.1, 0.02 + pf * 0.04, 0, TAU); c.fill(); }
    return;
  }
  // ear (behind), head, hair
  const skin = P.skin;
  c.beginPath(); c.ellipse(-0.035, 0.012, 0.032, 0.038, 0, 0, TAU); fo(c, skin, LINE.inkThin);
  c.strokeStyle = P.skinShade; c.lineWidth = 0.008; c.beginPath(); c.arc(-0.035, 0.014, 0.016, -1.2, 1.8); c.stroke();
  c.beginPath(); c.arc(0, 0, r, 0, TAU); c.fillStyle = skin; c.fill();
  // shadow band (lower right) + highlight band (upper left), the recipe on a sphere
  c.fillStyle = P.skinShade; c.beginPath(); c.arc(0, 0, r, -0.1, 1.95); c.quadraticCurveTo(0.02, 0.06, r * 0.99, -0.015); c.fill();
  c.fillStyle = 'rgba(255,255,255,0.32)'; c.beginPath(); c.ellipse(-0.045, -0.06, 0.05, 0.028, -0.5, 0, TAU); c.fill();
  c.beginPath(); c.arc(0, 0, r, 0, TAU); ink(c); c.stroke();
  // hair
  const hairC = P.hair;
  if (!O.cap || hatOn) {
    c.beginPath();
    if (O.hair === 'wild') {     // hair blown straight up (boxers)
      c.moveTo(-0.14, 0.03);
      const spikes = [[-0.16, -0.08], [-0.12, -0.2], [-0.07, -0.13], [-0.03, -0.24], [0.02, -0.14], [0.07, -0.22], [0.09, -0.11], [0.13, -0.15]];
      for (let i = 0; i < spikes.length; i++) { const k = Math.sin(t * 9 + i) * 0.008; c.lineTo(spikes[i][0] + k, spikes[i][1]); }
      c.quadraticCurveTo(0.06, -0.06, -0.02, -0.05); c.quadraticCurveTo(-0.07, -0.02, -0.08, 0.06); c.closePath();
    } else if (O.hair === 'messy') {
      c.arc(0, 0, r + 0.012, PI * 0.72, PI * 1.9);
      c.lineTo(0.12, -0.075); c.lineTo(0.06, -0.06); c.lineTo(0.08, -0.03); c.lineTo(0.02, -0.04); c.quadraticCurveTo(-0.06, -0.02, -0.075, 0.07); c.closePath();
    } else {                     // slicked 1920s side part with a wave
      c.arc(0, 0, r + 0.008, PI * 0.8, PI * 1.76);
      c.quadraticCurveTo(0.1, -0.06, 0.045, -0.085); c.quadraticCurveTo(0.0, -0.08, -0.03, -0.05); c.quadraticCurveTo(-0.07, -0.01, -0.085, 0.07); c.closePath();
    }
    fo(c, hairC, LINE.inkThin);
    c.strokeStyle = 'rgba(255,255,255,0.28)'; c.lineWidth = 0.012; c.beginPath(); c.arc(-0.01, -0.01, r - 0.035, PI * 1.15, PI * 1.5); c.stroke();
  } else {
    // sideburn + back hair under the cap
    c.beginPath(); c.moveTo(-0.13, -0.04); c.quadraticCurveTo(-0.16, 0.04, -0.1, 0.1); c.lineTo(-0.075, 0.07); c.quadraticCurveTo(-0.09, 0.0, -0.06, -0.06); c.closePath(); fo(c, hairC, LINE.inkThin);
  }
  face(c, O, st, t, expr);
  if (hatOn) topHat(c, '#15151c', P.crimson);
  else if (O.cap) newsCap(c, O.cap, O.capTilt || 0);
}
function blinkAt(t, seed) { return frac(t / 3.3 + seed) < 0.035; }
function face(c, O, st, t, expr) {
  const bl = (R.blink || blinkAt(t, num(st.blinkSeed, 0.13))) && expr !== 'panic';
  // eyes (3/4 view: near eye large, far eye narrower)
  const ex1 = 0.045, ey = -0.022, ex2 = 0.108;
  let lookX = 0.009 + R.look * 0.006, lookY = 0;
  let browL = 0, browR = 0, openK = 1;
  switch (expr) {
    case 'sad': browL = 0.03; browR = -0.02; lookY = 0.012; lookX = 0.004; openK = 0.75; break;
    case 'worried': browL = 0.025; browR = -0.018; openK = 1.05; break;
    case 'panic': browL = 0.03; browR = -0.025; openK = 1.25; break;
    case 'effort': browL = -0.025; browR = 0.02; openK = 0.55; break;
    case 'determined': browL = -0.018; browR = 0.012; openK = 0.85; break;
    case 'focus': browL = -0.02; browR = 0.02; openK = 0.6; break;
    case 'smug': browL = -0.008; browR = 0.0; openK = 0.6; break;
    case 'joy': openK = 0.0; break;
    case 'ooh': browL = 0.02; browR = -0.02; openK = 1.15; break;
    case 'proud': browL = -0.01; openK = 0.8; break;
    default: break;
  }
  // eyes: 1920s rubber-hose "pie eyes" (black ovals with a glint, shaped by slanted lids); only shock shows the whites
  const skinC = O.skinC || P.skin;
  const rx1 = 0.027, rx2 = 0.021;
  const ry1 = 0.047 * Math.max(0.15, openK), ry2 = 0.043 * Math.max(0.15, openK);
  const shock = expr === 'panic' || expr === 'ooh';
  if (bl && !shock) {
    c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin * 1.2;
    c.beginPath(); c.arc(ex1, ey - 0.004, 0.024, 0.15 * PI, 0.85 * PI); c.stroke();
    c.beginPath(); c.arc(ex2, ey - 0.006, 0.019, 0.15 * PI, 0.85 * PI); c.stroke();
  } else if (expr === 'joy') {
    c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin * 1.4;
    c.beginPath(); c.arc(ex1, ey + 0.012, 0.024, PI * 1.1, PI * 1.9); c.stroke();
    c.beginPath(); c.arc(ex2, ey + 0.01, 0.018, PI * 1.1, PI * 1.9); c.stroke();
  } else if (shock) {
    c.beginPath(); c.ellipse(ex1, ey, 0.033, 0.05, 0, 0, TAU); fo(c, '#ffffff', LINE.hair * 1.5);
    c.beginPath(); c.ellipse(ex2, ey - 0.002, 0.024, 0.046, 0, 0, TAU); fo(c, '#ffffff', LINE.hair * 1.5);
    c.fillStyle = P.ink; c.beginPath(); c.arc(ex1 + lookX, ey + lookY, 0.011, 0, TAU); c.arc(ex2 + lookX * 0.8, ey + lookY - 0.002, 0.009, 0, TAU); c.fill();
  } else {
    const oy = lookY * 0.6, ox = lookX * 0.5;
    c.fillStyle = P.ink;
    c.beginPath(); c.ellipse(ex1 + ox, ey + oy, rx1, ry1, 0, 0, TAU); c.fill();
    c.beginPath(); c.ellipse(ex2 + ox * 0.8, ey + oy - 0.002, rx2, ry2, 0, 0, TAU); c.fill();
    // the glint: a white wedge high in each eye
    c.fillStyle = '#ffffff';
    c.beginPath(); c.ellipse(ex1 + ox + 0.008, ey + oy - ry1 * 0.42, 0.009, Math.min(0.016, ry1 * 0.42), -0.3, 0, TAU); c.fill();
    c.beginPath(); c.ellipse(ex2 + ox * 0.8 + 0.006, ey + oy - ry2 * 0.42, 0.007, Math.min(0.013, ry2 * 0.42), -0.3, 0, TAU); c.fill();
    // lids: a skin-coloured cut over the top of the eye with an ink edge (angry slopes down to the nose, sad slopes up)
    let lid = null;
    if (expr === 'effort' || expr === 'focus' || expr === 'determined') lid = [-0.004, 0.022];
    else if (expr === 'sad' || expr === 'worried') lid = [0.02, -0.006];
    else if (expr === 'smug') lid = [0.006, 0.006];
    if (lid) {
      for (const [ex, rx, ry] of [[ex1, rx1, ry1], [ex2, rx2, ry2]]) {
        const yl = ey - ry * 0.25 + lid[0], yr = ey - ry * 0.25 + lid[1];
        c.fillStyle = skinC; c.beginPath(); c.moveTo(ex - rx - 0.01, yl); c.lineTo(ex + rx + 0.01, yr); c.lineTo(ex + rx + 0.01, ey - ry - 0.012); c.lineTo(ex - rx - 0.01, ey - ry - 0.012); c.closePath(); c.fill();
        c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin; c.beginPath(); c.moveTo(ex - rx - 0.004, yl + 0.001); c.lineTo(ex + rx + 0.004, yr + 0.001); c.stroke();
      }
    }
    if (expr === 'focus') { c.fillStyle = skinC; c.fillRect(ex2 - 0.03, ey - 0.06, 0.06, 0.05); c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin; c.beginPath(); c.moveTo(ex2 - 0.022, ey - 0.008); c.lineTo(ex2 + 0.022, ey - 0.012); c.stroke(); }
  }
  // brows
  c.strokeStyle = P.hair; c.lineWidth = 0.02;
  c.beginPath(); c.moveTo(ex1 - 0.032, ey - 0.06 + browL); c.lineTo(ex1 + 0.03, ey - 0.062 - browL * 0.5); c.stroke();
  c.beginPath(); c.moveTo(ex2 - 0.02, ey - 0.06 - browR * 0.5); c.lineTo(ex2 + 0.022, ey - 0.058 + browR); c.stroke();
  // nose: the big cartoon bulb that sticks out of the silhouette
  c.beginPath(); c.ellipse(0.142, 0.018, 0.034, 0.03, 0.2, 0, TAU); fo(c, P.skin, LINE.inkThin);
  c.fillStyle = 'rgba(255,255,255,0.5)'; c.beginPath(); c.arc(0.135, 0.008, 0.009, 0, TAU); c.fill();
  // cheeks
  if (O.blush || expr === 'effort' || expr === 'joy') { c.fillStyle = RA(P.blush, O.blush ? 0.7 : 0.45); c.beginPath(); c.ellipse(0.05, 0.05, 0.03, 0.016, 0, 0, TAU); c.fill(); }
  // mouth
  const mx = 0.085, my = 0.082;
  c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin;
  switch (expr) {
    case 'smile': case 'proud': c.beginPath(); c.arc(mx, my - 0.03, 0.035, 0.45, 1.95); c.stroke(); break;
    case 'smug': c.beginPath(); c.moveTo(mx - 0.035, my - 0.002); c.quadraticCurveTo(mx + 0.01, my + 0.018, mx + 0.04, my - 0.02); c.stroke(); break;
    case 'grin': case 'joy': {
      c.beginPath(); c.moveTo(mx - 0.04, my - 0.012); c.quadraticCurveTo(mx, my - 0.005, mx + 0.045, my - 0.02); c.quadraticCurveTo(mx + 0.03, my + 0.045, mx - 0.01, my + 0.03); c.closePath();
      fo(c, '#5a1d1d', LINE.inkThin);
      c.fillStyle = '#ffffff'; c.beginPath(); c.moveTo(mx - 0.035, my - 0.01); c.quadraticCurveTo(mx, my - 0.004, mx + 0.04, my - 0.018); c.lineTo(mx + 0.036, my - 0.002); c.quadraticCurveTo(mx, my + 0.008, mx - 0.03, my + 0.002); c.closePath(); c.fill();
      if (expr === 'joy') { c.fillStyle = P.blush; c.beginPath(); c.ellipse(mx + 0.008, my + 0.026, 0.016, 0.008, 0, 0, TAU); c.fill(); }
      break;
    }
    case 'determined': c.beginPath(); c.moveTo(mx - 0.03, my); c.lineTo(mx + 0.03, my - 0.006); c.stroke(); break;
    case 'effort': case 'focus': {
      c.beginPath(); rrP(c, mx - 0.032, my - 0.014, 0.064, 0.026, 0.008); fo(c, '#ffffff', LINE.inkThin);
      c.beginPath(); c.moveTo(mx - 0.03, my - 0.001); c.lineTo(mx + 0.03, my - 0.001); c.moveTo(mx - 0.01, my - 0.014); c.lineTo(mx - 0.01, my + 0.012); c.moveTo(mx + 0.01, my - 0.014); c.lineTo(mx + 0.01, my + 0.012); c.lineWidth = LINE.hair; c.stroke();
      break;
    }
    case 'sad': c.beginPath(); c.arc(mx, my + 0.03, 0.03, PI * 1.2, PI * 1.85); c.stroke(); break;
    case 'worried': c.beginPath(); c.moveTo(mx - 0.03, my + 0.005); c.quadraticCurveTo(mx - 0.01, my - 0.012, mx + 0.005, my + 0.004); c.quadraticCurveTo(mx + 0.02, my + 0.016, mx + 0.032, my - 0.004); c.stroke(); break;
    case 'panic': case 'ooh': c.beginPath(); c.ellipse(mx + 0.004, my + 0.004, 0.018, expr === 'panic' ? 0.026 : 0.02, 0, 0, TAU); fo(c, '#5a1d1d', LINE.inkThin); break;
    default: c.beginPath(); c.arc(mx, my - 0.02, 0.028, 0.6, 1.8); c.stroke();
  }
  if (expr === 'panic' || expr === 'worried') {   // a sweat drop
    const sd = frac(t * 0.9);
    c.fillStyle = '#bfe7ff'; c.beginPath(); c.moveTo(-0.06, -0.09 + sd * 0.05); c.quadraticCurveTo(-0.045, -0.06 + sd * 0.05, -0.06, -0.05 + sd * 0.05); c.quadraticCurveTo(-0.075, -0.06 + sd * 0.05, -0.06, -0.09 + sd * 0.05); c.fill();
    c.strokeStyle = P.ink; c.lineWidth = LINE.hair; c.stroke();
  }
}
function newsCap(c, col, tilt) {
  // a flat 1920s newsboy cap: broad puffy crown overhanging the back, short brim, eight-panel seams and a button
  c.save(); c.rotate(-0.04 - tilt * 0.45); c.translate(tilt * 0.025, tilt * 0.01);
  c.beginPath(); c.moveTo(0.05, -0.088); c.quadraticCurveTo(0.16, -0.106, 0.222, -0.074); c.quadraticCurveTo(0.2, -0.056, 0.07, -0.058); c.closePath();
  fo(c, DK(col, 0.42), LINE.inkThin);
  c.beginPath(); c.moveTo(-0.158, -0.008);
  c.bezierCurveTo(-0.215, -0.1, -0.15, -0.205, -0.025, -0.21);
  c.bezierCurveTo(0.095, -0.215, 0.18, -0.165, 0.168, -0.1);
  c.bezierCurveTo(0.155, -0.07, 0.05, -0.066, -0.158, -0.008); c.closePath();
  shadeU(c, -0.2, -0.215, 0.37, 0.21, col); ink(c); c.stroke();
  c.strokeStyle = RA(P.ink, 0.4); c.lineWidth = LINE.hair;
  c.beginPath(); c.moveTo(-0.02, -0.205); c.quadraticCurveTo(-0.11, -0.13, -0.135, -0.04); c.moveTo(-0.02, -0.205); c.quadraticCurveTo(0.08, -0.16, 0.13, -0.085); c.stroke();
  c.strokeStyle = RA('#ffffff', 0.25); c.lineWidth = 0.012; c.beginPath(); c.moveTo(-0.13, -0.11); c.quadraticCurveTo(-0.08, -0.18, 0.0, -0.19); c.stroke();
  c.fillStyle = RA(P.ink, 0.18); for (let i = 0; i < 7; i++) c.fillRect(-0.12 + i * 0.035, -0.15 + (i % 2) * 0.03, 0.012, 0.012);
  c.beginPath(); c.ellipse(-0.025, -0.212, 0.018, 0.011, 0, 0, TAU); fo(c, DK(col, 0.25), LINE.hair * 1.5);
  c.restore();
}
function topHat(c, col, band) {
  c.save(); c.rotate(-0.16); c.translate(-0.01, -0.035);
  c.beginPath(); c.ellipse(0.0, -0.11, 0.17, 0.035, 0, 0, TAU); fo(c, col);
  c.beginPath(); c.moveTo(-0.095, -0.115); c.lineTo(-0.105, -0.33); c.quadraticCurveTo(0.0, -0.35, 0.105, -0.33); c.lineTo(0.095, -0.115); c.quadraticCurveTo(0.0, -0.1, -0.095, -0.115); c.closePath();
  shadeU(c, -0.11, -0.35, 0.22, 0.24, col); ink(c); c.stroke();
  c.beginPath(); c.moveTo(-0.096, -0.13); c.lineTo(-0.099, -0.175); c.quadraticCurveTo(0.0, -0.165, 0.099, -0.175); c.lineTo(0.096, -0.13); c.quadraticCurveTo(0.0, -0.12, -0.096, -0.13); c.closePath(); fo(c, band, LINE.inkThin);
  c.fillStyle = 'rgba(255,255,255,0.22)'; c.fillRect(-0.06, -0.32, 0.026, 0.14);
  c.beginPath(); c.ellipse(0.0, -0.333, 0.105, 0.022, 0, 0, TAU); fo(c, LI(col, 0.12), LINE.inkThin);
  c.restore();
}
function cane(c, x, y, ang, t) {
  c.save(); c.translate(x, y); c.rotate(ang);
  c.strokeStyle = P.ink; c.lineWidth = 0.034; c.beginPath(); c.moveTo(0, -0.05); c.lineTo(0, 0.42); c.stroke();
  c.strokeStyle = '#141418'; c.lineWidth = 0.02; c.stroke();
  c.strokeStyle = P.gold; c.lineWidth = 0.022; c.beginPath(); c.moveTo(0, 0.37); c.lineTo(0, 0.42); c.stroke();
  // the diamond knob
  c.beginPath(); c.moveTo(0, -0.12); c.lineTo(0.04, -0.075); c.lineTo(0, -0.035); c.lineTo(-0.04, -0.075); c.closePath(); fo(c, '#dff7ff', LINE.inkThin);
  c.fillStyle = '#9fe3ff'; c.beginPath(); c.moveTo(0, -0.12); c.lineTo(0.04, -0.075); c.lineTo(0, -0.075); c.closePath(); c.fill();
  const tw = Math.max(0, Math.sin(t * 3.1)) ** 8;
  glowU(c, 0, -0.08, 0.07 + tw * 0.06, '#ffffff', 0.5 + tw * 0.5);
  if (tw > 0.2) { c.strokeStyle = '#ffffff'; c.lineWidth = 0.008; c.beginPath(); c.moveTo(-0.06 * tw, -0.08); c.lineTo(0.06 * tw, -0.08); c.moveTo(0, -0.14 * tw - 0.02); c.lineTo(0, -0.02); c.stroke(); }
  c.restore();
}
function scarf(c, O, t, wind) {
  // a neckerchief: the knot sits at the throat, two tails stream backward with the wind
  const nx = R.sx + Math.cos(R.ta) * 0.03, ny = R.sy + Math.sin(R.ta) * 0.03 - 0.01;
  const w = clamp(0.2 + wind, 0, 1.3);
  for (let i = 1; i >= 0; i--) {
    const ph = t * (8.5 + i * 2.1) + i * 1.7;
    const L = 0.15 + 0.09 * w - i * 0.03;
    const dir = PI - 0.15 - (1.15 - w) * 0.9 + i * 0.3 + Math.sin(ph) * 0.12 * w;
    const ex = nx + Math.cos(dir) * L, ey = ny + Math.sin(dir) * L * -1 + (1.2 - w) * 0.09;
    const mx = (nx + ex) / 2 + Math.sin(ph * 1.3) * 0.015, my = (ny + ey) / 2 + Math.cos(ph) * 0.02;
    c.beginPath(); c.moveTo(nx, ny - 0.016); c.quadraticCurveTo(mx, my - 0.03, ex, ey - 0.012);
    c.lineTo(ex - 0.012, ey + 0.026); c.quadraticCurveTo(mx, my + 0.018, nx, ny + 0.018); c.closePath();
    fo(c, i ? DK(O.scarf, 0.22) : O.scarf, LINE.inkThin);
  }
}
function tails(c, O, t, wind) {
  // swallowtail coat-tails hanging from the back of the waist, streaming backward with speed
  const bx = R.hx - Math.cos(R.ta) * 0.06, by = R.hy - Math.sin(R.ta) * 0.06 - 0.03;
  const flap = Math.sin(t * 10.5) * 0.1 * (0.25 + wind) + Math.sin(t * 17.3) * 0.04 * wind;
  c.save(); c.translate(bx, by); c.rotate(0.18 + 0.75 * wind + flap);
  c.beginPath(); c.moveTo(0.04, -0.02); c.lineTo(-0.045, -0.025);
  c.quadraticCurveTo(-0.075, 0.1, -0.08 - wind * 0.02, 0.215);
  c.lineTo(-0.025, 0.165); c.lineTo(0.02, 0.24 + wind * 0.01);
  c.quadraticCurveTo(0.05, 0.1, 0.04, -0.02); c.closePath();
  shadeU(c, -0.09, -0.03, 0.14, 0.27, '#22222c'); ink(c); c.stroke();
  c.strokeStyle = RA('#ffffff', 0.18); c.lineWidth = 0.01; c.beginPath(); c.moveTo(-0.035, 0.0); c.quadraticCurveTo(-0.055, 0.1, -0.06, 0.18); c.stroke();
  c.restore();
}
function barrelBody(c, t) {
  // a pickle barrel from the armpits to the knees, worn on two rope straps
  const x0 = R.hx, y0 = R.hy;
  c.save(); c.translate(x0, y0 + 0.02); c.rotate(R.ta * 0.5);
  const top = -0.25, bot = 0.17, w = 0.165;
  c.beginPath(); c.moveTo(-w * 0.9, top); c.quadraticCurveTo(-w * 1.18, (top + bot) / 2, -w * 0.9, bot); c.lineTo(w * 0.9, bot); c.quadraticCurveTo(w * 1.18, (top + bot) / 2, w * 0.9, top); c.closePath();
  shadeU(c, -w, top, w * 2, bot - top, P.barrel); ink(c); c.stroke();
  c.strokeStyle = RA(P.ink, 0.55); c.lineWidth = LINE.hair * 1.5;
  for (let i = -2; i <= 2; i++) { c.beginPath(); c.moveTo(i * w * 0.36, top + 0.005); c.quadraticCurveTo(i * w * 0.46, (top + bot) / 2, i * w * 0.36, bot - 0.005); c.stroke(); }
  for (const yy of [top + 0.06, bot - 0.06]) {
    c.beginPath(); c.moveTo(-w * 1.02, yy - 0.014); c.quadraticCurveTo(0, yy + 0.012, w * 1.02, yy - 0.014); c.lineTo(w * 1.02, yy + 0.012); c.quadraticCurveTo(0, yy + 0.038, -w * 1.02, yy + 0.012); c.closePath(); fo(c, P.barrelBand, LINE.inkThin);
    rivetU(c, -w * 0.6, yy + 0.01, 0.008); rivetU(c, w * 0.6, yy + 0.01, 0.008);
  }
  c.beginPath(); c.ellipse(0, top, w * 0.9, 0.03, 0, 0, TAU); fo(c, DK(P.barrel, 0.45), LINE.inkThin);
  textU(c, 'PICKLES', 0.005, (top + bot) / 2 + 0.005, 0.045, { color: '#3b6e2a', font: FONT.deco });
  c.restore();
  // rope shoulder straps holding the barrel up
  for (const [bx, by] of [[R.hx - 0.1, R.hy - 0.21], [R.hx + 0.11, R.hy - 0.22]]) {
    c.beginPath(); c.moveTo(bx, by); c.quadraticCurveTo((bx + R.sx) / 2, R.sy - 0.06, R.sx + 0.01, R.sy - 0.012);
    c.strokeStyle = P.ink; c.lineWidth = 0.032; c.stroke(); c.strokeStyle = '#c9a26a'; c.lineWidth = 0.018; c.stroke();
  }
}
function halfCoinBack(c, t) {
  const bx = R.sx - Math.cos(R.ta) * 0.085 + 0.005, by = (R.sy + R.hy) / 2 - 0.02;
  c.save(); c.translate(bx, by); c.rotate(-0.3);
  coinU(c, 0, 0, 0.13, { glow: 0.35, half: true, t }, LINE.inkThin);
  c.restore();
}
function strap(c) {
  c.strokeStyle = P.ink; c.lineWidth = 0.03;
  c.beginPath(); c.moveTo(R.sx - 0.06, R.sy + 0.01); c.lineTo(R.hx + 0.07, R.hy - 0.06); c.stroke();
  c.strokeStyle = '#7a4a22'; c.lineWidth = 0.018; c.stroke();
  c.fillStyle = P.gold; c.fillRect((R.sx + R.hx) / 2 - 0.01, (R.sy + R.hy) / 2 - 0.012, 0.022, 0.022);
}
function dustPuffs(c, t, x, y) {
  for (let i = 0; i < 4; i++) {
    const u = frac(t * 2.2 + i / 4);
    const px = x + 0.03 + u * 0.3, py = y - 0.015 - u * 0.12 - Math.sin(u * PI) * 0.03, r = 0.022 + u * 0.06;
    c.fillStyle = RA('#d8c7a3', 0.75 * (1 - u)); c.beginPath(); c.arc(px, py, r, 0, TAU); c.fill();
    c.fillStyle = RA('#fff3d6', 0.5 * (1 - u)); c.beginPath(); c.arc(px - r * 0.3, py - r * 0.3, r * 0.45, 0, TAU); c.fill();
  }
}
function speedLines(c, t) {
  c.strokeStyle = 'rgba(255,255,255,0.7)'; c.lineWidth = 0.012;
  for (let i = 0; i < 4; i++) {
    const u = frac(t * 3 + i * 0.27), y = -0.25 - i * 0.17 + R.hy * 0.2;
    c.globalAlpha *= 1 - u;
    c.beginPath(); c.moveTo(-0.28 - u * 0.25, y); c.lineTo(-0.48 - u * 0.25, y); c.stroke();
    c.globalAlpha /= Math.max(0.01, 1 - u);
  }
}
function dustCloud(c, t) {
  for (let i = 0; i < 3; i++) {
    const u = frac(t * 0.5 + i / 3);
    c.fillStyle = RA('#cbbd9f', 0.5 * (1 - u));
    c.beginPath(); c.arc(R.hx - 0.1 + i * 0.1 + u * 0.05, R.hy - 0.15 - u * 0.25, 0.03 + u * 0.05, 0, TAU); c.fill();
  }
}

// the figure, drawn in rig space (facing right). kind: 'runner' | 'twin' | 'ghost'
function figure(c, O, st, t, pose, coinSt, hatOn, caneOn) {
  const wind = R.wind;
  c.save();
  c.translate(0, -R.lift);
  if (R.rot) c.rotate(R.rot);
  if (R.sqx !== 1 || R.sqy !== 1) c.scale(R.sqx, R.sqy);
  if (R.fly) { c.translate(0, -1.08); c.rotate(R.fly); c.translate(0, 1.08); }
  if (R.speed && (pose === 'tackle' || pose === 'ride')) speedLines(c, t);
  // the coin as a snowboard, white-hot, under everything
  if (R.coin === 'board') {
    c.save(); c.translate(R.cx, R.cy); c.rotate(R.board);
    const woodB = O.woodSkin || O.torso === 'wood';
    if (!woodB) glowU(c, 0, -0.03, 0.4, P.goldHot, 0.3 * (coinSt.glow == null ? 1 : coinSt.glow) + 0.1);
    // trailing sparks
    for (let i = 0; i < 5; i++) { const u = frac(t * 2.5 + i / 5); c.fillStyle = RA(woodB ? '#d8c7a3' : P.goldHot, 1 - u); c.beginPath(); c.arc(-0.3 - u * 0.35, 0.02 + Math.sin(i * 7 + t * 9) * 0.03, 0.012 * (1 - u) + 0.004, 0, TAU); c.fill(); }
    c.beginPath(); c.ellipse(0, 0.018, 0.34, 0.07, 0, 0, TAU); fo(c, woodB ? '#8a5a2b' : P.goldDeep);
    c.beginPath(); c.ellipse(0, 0, 0.34, 0.07, 0, 0, TAU); fo(c, woodB ? P.wood : MX(P.gold, '#ffffff', 0.55 * num(coinSt.glow, 1)));
    c.beginPath(); c.ellipse(0, 0, 0.27, 0.05, 0, 0, TAU); ink(c, LINE.hair * 1.5, RA(P.goldDark, 0.8)); c.stroke();
    c.fillStyle = 'rgba(255,255,255,0.75)'; c.beginPath(); c.ellipse(-0.12, -0.02, 0.09, 0.014, -0.05, 0, TAU); c.fill();
    c.restore();
  }
  if (O.tails) tails(c, O, t, wind);
  if (O.scarf && O.torso !== 'twin') scarf(c, O, t, wind);
  if (O.halfBack) halfCoinBack(c, t);
  if (caneOn && R.cane === 'far') cane(c, R.af[4], R.af[5], -0.6 + Math.sin(t * 2) * 0.1, t);
  if (O.torso === 'twin') {   // wind-up key on the back
    const kx = R.sx - Math.cos(R.ta) * 0.1 + 0.01, ky = (R.sy + R.hy) / 2 - 0.03, kw = Math.abs(Math.cos(t * 3.2));
    c.strokeStyle = P.ink; c.lineWidth = 0.03; c.beginPath(); c.moveTo(kx + 0.04, ky); c.lineTo(kx - 0.04, ky); c.stroke(); c.strokeStyle = P.brass; c.lineWidth = 0.016; c.stroke();
    c.beginPath(); c.ellipse(kx - 0.07, ky, 0.03, 0.06 * kw + 0.008, 0, 0, TAU); fo(c, P.brassLight, LINE.inkThin);
  }
  const held = R.coin === 'hug' || R.coin === 'overhead';
  arm(c, R.af, O, true, held);
  leg(c, R.lf, O, true, R.ff);
  if (R.coin === 'tuck') coinU(c, R.cx, R.cy, R.cr, { glow: num(coinSt.glow, 0.5), tarnish: num(coinSt.tarnish, 0), half: !!coinSt.half, t, wooden: O.torso === 'wood' || O.woodSkin || coinSt.wooden, brass: O.torso === 'twin' }, LINE.ink);
  // torso in its own frame
  c.save(); c.translate(R.hx, R.hy); c.rotate(R.ta); torso(c, O, t, wind); c.restore();
  leg(c, R.ln, O, false, R.fn);
  if (O.torso === 'barrel') barrelBody(c, t);
  if (O.torso === 'boxers') boxerShorts(c, t);
  if (O.halfBack) strap(c);
  // neck
  c.strokeStyle = P.ink; c.lineWidth = 0.06 + LINE.ink;
  const nx0 = R.sx, ny0 = R.sy, nx1 = R.hdx, ny1 = R.hdy;
  c.beginPath(); c.moveTo(nx0, ny0); c.lineTo(lerp(nx0, nx1, 0.55), lerp(ny0, ny1, 0.55)); c.stroke();
  c.strokeStyle = O.torso === 'twin' ? P.brassDark : (O.torso === 'wood' || O.woodSkin) ? '#9a6634' : P.skinShade; c.lineWidth = 0.06; c.stroke();
  if (O.torso === 'tux') { c.beginPath(); c.moveTo(nx0 - 0.03, ny0 + 0.01); c.lineTo(nx0 + 0.035, ny0 - 0.005); c.lineTo(nx0 + 0.04, ny0 - 0.04); c.lineTo(nx0 - 0.02, ny0 - 0.03); c.closePath(); fo(c, P.shirt, LINE.inkThin); }
  // head
  c.save(); c.translate(R.hdx, R.hdy); c.rotate(R.ha);
  head(c, O, st, t, st.face || O.expr || R.expr, hatOn);
  c.restore();
  if (O.scarf && O.torso !== 'twin') {   // the knot sits over the neck
    const nx = R.sx + Math.cos(R.ta) * 0.035, ny = R.sy + Math.sin(R.ta) * 0.035 - 0.012;
    c.beginPath(); c.ellipse(nx + 0.01, ny, 0.034, 0.024, R.ta, 0, TAU); fo(c, O.scarf, LINE.inkThin);
  }
  // the held coin: the near arm goes behind it, the hands grip the rim in front
  if (held) {
    const cs = coinSt;
    arm(c, R.an, O, false, true);
    if (caneOn && R.coin === 'hug') cane(c, R.an[4] - 0.015, R.an[5] - 0.05, 0.3, t);
    if (O.torso === 'twin') coinU(c, R.cx, R.cy, R.cr, { glow: 0, wooden: false, brass: true, t, spin: 0 }, LINE.ink);
    else coinU(c, R.cx, R.cy, R.cr, { glow: num(cs.glow, 0.5), tarnish: num(cs.tarnish, 0), half: !!cs.half, spin: num(cs.spin, 0), t, wooden: O.torso === 'wood' || O.woodSkin || cs.wooden }, LINE.ink);
    hand(c, R.af[4], R.af[5], O.hand, false);
    hand(c, R.an[4], R.an[5], O.hand, false);
  } else arm(c, R.an, O, false);
  if (pose === 'aim' && st.pistol) {
    c.save(); c.translate(R.an[4], R.an[5]); c.rotate(Math.atan2(R.an[5] - R.an[3], R.an[4] - R.an[2]) * 0.25);
    pistolU(c, 0, 0, num(st.patience, 0), num(st.recoil, 0), t);
    c.restore();
    hand(c, R.an[4], R.an[5], O.hand, false);
  }
  if (caneOn && !held && (pose === 'idle' || pose === 'hold')) cane(c, R.an[4] + 0.02, R.an[5] - 0.02, 0.18, t);
  if (R.dust) dustPuffs(c, t, R.ln[4] + 0.06, 0);
  if (O.dust) dustCloud(c, t);
  c.restore();
}
function boxerShorts(c, t) {
  // polka-dot boxers around the hips and the tops of both thighs
  const ln = R.ln, lf = R.lf;
  const kx1 = lerp(ln[0], ln[2], 0.55), ky1 = lerp(ln[1], ln[3], 0.55), kx2 = lerp(lf[0], lf[2], 0.55), ky2 = lerp(lf[1], lf[3], 0.55);
  c.strokeStyle = P.ink; c.lineWidth = RG.legW * 1.55 + LINE.ink; c.lineCap = 'butt';
  c.beginPath(); c.moveTo(lf[0], lf[1]); c.lineTo(kx2, ky2); c.stroke();
  c.strokeStyle = DK(P.boxers, 0.15); c.lineWidth = RG.legW * 1.55; c.stroke();
  c.strokeStyle = P.ink; c.lineWidth = RG.legW * 1.55 + LINE.ink;
  c.beginPath(); c.moveTo(ln[0], ln[1]); c.lineTo(kx1, ky1); c.stroke();
  c.strokeStyle = P.boxers; c.lineWidth = RG.legW * 1.55; c.stroke();
  c.lineCap = 'round';
  c.beginPath(); c.ellipse(R.hx, R.hy - 0.005, 0.09, 0.06, R.ta, 0, TAU); c.fillStyle = P.boxers; c.fill();
  // waistband
  c.save(); c.translate(R.hx, R.hy); c.rotate(R.ta);
  c.beginPath(); rrP(c, -0.088, -0.07, 0.172, 0.03, 0.012); fo(c, '#fff4f6', LINE.inkThin);
  c.restore();
  c.fillStyle = P.polka;
  const dots = [[0.0, -0.01], [0.05, 0.02], [-0.045, 0.025], [0.02, 0.055], [-0.02, 0.06]];
  for (const d of dots) { c.beginPath(); c.arc(R.hx + d[0], R.hy + d[1], 0.011, 0, TAU); c.fill(); }
  c.beginPath(); c.arc(kx1 - 0.01, ky1 - 0.02, 0.01, 0, TAU); c.fill();
}

function drawFigure(ctx, x, y, s, st, O, kind) {
  const t = num(st.t, 0);
  const f = st.facing < 0 ? -1 : 1;
  const pose = POSES_OK.has(st.pose) ? st.pose : 'idle';
  const coin = st.coin || {};
  const coinVis = kind === 'runner' ? (coin.visible === undefined ? false : !!coin.visible) : (kind === 'twin' && (pose === 'idle' || pose === 'run' || pose === 'hold' || pose === 'lean' || pose === 'slide'));
  solvePose(pose, t, st.lean, coinVis && pose !== 'aim' && pose !== 'fly' && pose !== 'kneel', st.look);
  if (coinVis && pose === 'ride') R.coin = 'board';
  if (!coinVis && pose === 'ride') R.coin = 'board';
  const hatOn = st.hat === undefined ? !!O.hat : !!st.hat;
  const caneOn = st.cane === undefined ? !!O.cane : !!st.cane;
  const alpha = clamp(num(st.alpha, kind === 'ghost' ? 0.5 : kind === 'twin' ? 0.88 : 1), 0, 1);
  const tint = kind === 'ghost' ? '#cfeeff' : (st.tint || null);
  beginU(ctx, x, y, s, 1);
  const paint = (c) => { if (f < 0) c.scale(-1, 1); figure(c, O, st, t, pose, coin, hatOn, caneOn); };
  if (alpha < 0.999 || tint) {
    if (kind === 'ghost') glowU(ctx, 0, -0.5, 0.8, '#9fd8ff', 0.6 * alpha);
    if (kind === 'twin') glowU(ctx, 0, -0.5, 0.7, P.brassLight, 0.25 * alpha);
    withLayer(ctx, [-0.8, -1.55, 1.6, 1.68], kind === 'ghost' ? Math.min(1, alpha * 1.5) : alpha, tint, kind === 'ghost' ? 0.62 : 0.55, paint);
  } else paint(ctx);
  rs(ctx);
  // points for the caller (screen px)
  const cr = Math.cos(R.rot), sr = Math.sin(R.rot);
  const P2 = (ux, uy, ox, oy) => {
    if (R.fly) { const dx = ux, dy = uy + 1.08, cf = Math.cos(R.fly), sf = Math.sin(R.fly); ux = dx * cf - dy * sf; uy = dx * sf + dy * cf - 1.08; }
    const X = (ux * R.sqx) * cr - (uy * R.sqy) * sr, Y = (ux * R.sqx) * sr + (uy * R.sqy) * cr - R.lift; RUNNER_PTS[ox] = x + f * X * s; RUNNER_PTS[oy] = y + Y * s; };
  P2(R.cx, R.cy, 'coinX', 'coinY'); RUNNER_PTS.coinR = R.cr * s;
  P2(R.an[4], R.an[5], 'handX', 'handY');
  P2(0, -1.08, 'gripX', 'gripY');
  P2(R.hdx, R.hdy, 'headX', 'headY');
  P2(R.hx - 0.03, R.hy - 0.03, 'beltX', 'beltY');
  return RUNNER_PTS;
}
const POSES_OK = new Set(['idle', 'run', 'slide', 'lean', 'kneel', 'ride', 'aim', 'cheer', 'hold', 'tackle', 'fly']);

export const drawRunner = guard('drawRunner', function (ctx, x, y, s, st) {
  st = st || {};
  const base = OUT[st.outfit] || OUT.suit;
  const O = st.wooden ? woodify(base) : base;
  return drawFigure(ctx, x, y, s, st, O, 'runner');
});
export const drawTwin = guard('drawTwin', function (ctx, x, y, s, st) {
  st = st || {};
  return drawFigure(ctx, x, y, s, st, TWIN, 'twin');
});
export const drawGhost = guard('drawGhost', function (ctx, x, y, s, st) {
  st = st || {};
  return drawFigure(ctx, x, y, s, { pose: st.pose, facing: st.facing, t: st.t, alpha: num(st.alpha, 0.4), lean: st.lean, coin: { visible: st.pose !== 'aim' && st.pose !== 'fly' && st.pose !== 'kneel', glow: 0 } }, OUT.suit, 'ghost');
});
//>>RUNNER

//<<BANK
// ================================================================================================ THE BANK + THE BANKER
// A brutalist riveted-iron Art-Deco facade (3.4 w x 4.6 h): stepped crown, fluted columns with gold capitals, a vault door at street
// level, the Banker built into an upper doorway (cyborg vault-keeper: green visor, cigar, red lens), the crane, shutters, banners.
// The static stonework is one cached sprite per variant (iron / wood); everything that moves is drawn live on top.
export const BANK_GEO = { sign: { cx: 0, cy: 0, w: 0, h: 0 }, bell: { x: 0, y: 0 }, door: { x: 0, y: 0, w: 0, h: 0 },
  banker: { x: 0, y: 0, w: 0, h: 0 }, craneTip: { x: 0, y: 0 }, step: { x: 0, y: 0 } };
const BK = { W: 1.7, plinth: 0.24, top: 3.27, doorR: 0.5, doorTop: 1.0, balL: 1.88, balR: 0.56, balC: 2.62, mount: [0.66, -2.36] };
function craneTipU(crane) {
  const k = ease(clamp(crane, 0, 1));
  return [lerp(0.86, 2.3, k), lerp(-1.98, -0.66, k)];
}
// all in screen px: sign rect (centre), bell anchor (bottom of its frame), door, banker box (centre), crane tip, the step
export function bankGeometry(x, y, s, facing = 1, crane = 0) {
  const f = facing < 0 ? -1 : 1;
  BANK_GEO.sign.cx = x; BANK_GEO.sign.cy = y - 5.16 * s; BANK_GEO.sign.w = 2.2 * s; BANK_GEO.sign.h = 0.9 * s;
  BANK_GEO.bell.x = x; BANK_GEO.bell.y = y - 5.61 * s;
  BANK_GEO.door.x = x; BANK_GEO.door.y = y - 0.75 * s; BANK_GEO.door.w = 1.0 * s; BANK_GEO.door.h = 1.26 * s;
  BANK_GEO.banker.x = x; BANK_GEO.banker.y = y - 2.5 * s; BANK_GEO.banker.w = 1.1 * s; BANK_GEO.banker.h = 1.3 * s;
  const tip = craneTipU(crane);
  BANK_GEO.craneTip.x = x + f * tip[0] * s; BANK_GEO.craneTip.y = y + (tip[1] + 0.12) * s;
  BANK_GEO.step.x = x + f * 0.0 * s; BANK_GEO.step.y = y - 0.24 * s;
  return BANK_GEO;
}
function bankColours(wood) {
  return wood
    ? { iron: '#9a6a3c', dark: '#6b4423', light: '#c58f58', gold: '#e2ad4a', goldD: '#a8742a', glass: '#3b2a1c', interior: '#24160c', trim: '#f0c26a' }
    : { iron: P.iron, dark: P.ironDark, light: P.ironLight, gold: P.gold, goldD: P.goldDeep, glass: '#1e2a3a', interior: '#0f0a07', trim: P.goldHot };
}
function archPath(c, cx, bottom, halfW, springY) {
  // a doorway: straight sides from `bottom` up to `springY`, then a semicircle of radius halfW
  c.beginPath(); c.moveTo(cx - halfW, bottom); c.lineTo(cx - halfW, springY); c.arc(cx, springY, halfW, PI, 0); c.lineTo(cx + halfW, bottom); c.closePath();
}
function fluted(c, x0, y0, w, h, K) {
  c.beginPath(); c.rect(x0, y0, w, h); shadeU(c, x0, y0, w, h, K.iron); ink(c); c.stroke();
  c.strokeStyle = RA(P.ink, 0.45); c.lineWidth = 0.012;
  for (let i = 1; i < 4; i++) { const gx = x0 + (w * i) / 4; c.beginPath(); c.moveTo(gx, y0 + 0.08); c.lineTo(gx, y0 + h - 0.06); c.stroke(); }
  c.strokeStyle = RA('#ffffff', 0.16); c.lineWidth = 0.01;
  for (let i = 1; i < 4; i++) { const gx = x0 + (w * i) / 4 - 0.015; c.beginPath(); c.moveTo(gx, y0 + 0.08); c.lineTo(gx, y0 + h - 0.06); c.stroke(); }
  // stepped gold capital + base
  for (let k = 0; k < 2; k++) {
    const yy = k ? y0 + h - 0.1 : y0;
    c.beginPath(); c.rect(x0 - 0.04, yy, w + 0.08, 0.1); shadeU(c, x0 - 0.04, yy, w + 0.08, 0.1, K.gold); ink(c, LINE.inkThin); c.stroke();
    c.beginPath(); c.rect(x0 - 0.015, k ? yy - 0.04 : yy + 0.1, w + 0.03, 0.04); fo(c, K.goldD, LINE.inkThin);
  }
}
function bankFacade(c, wood) {
  const K = bankColours(wood);
  const W = BK.W;
  // ---- plinth + steps
  c.beginPath(); c.rect(-W, -BK.plinth, W * 2, BK.plinth); shadeU(c, -W, -BK.plinth, W * 2, BK.plinth, K.dark); ink(c); c.stroke();
  c.beginPath(); c.rect(-W, -BK.plinth, W * 2, 0.035); fo(c, K.gold, LINE.inkThin);
  for (let i = 0; i < 3; i++) {
    const sw = 1.36 - i * 0.14, sh = 0.075, sy = -sh * (i + 1);
    c.beginPath(); c.rect(-sw / 2, sy, sw, sh); shadeU(c, -sw / 2, sy, sw, sh, wood ? '#b07a44' : '#7b818c'); ink(c, LINE.inkThin); c.stroke();
    c.fillStyle = RA('#ffffff', 0.18); c.fillRect(-sw / 2 + 0.02, sy + 0.008, sw - 0.04, 0.012);
  }
  // ---- main block of riveted plates
  const top = -BK.top, bot = -BK.plinth;
  c.beginPath(); c.rect(-1.55, top, 3.1, bot - top); shadeU(c, -1.55, top, 3.1, bot - top, K.iron); ink(c); c.stroke();
  c.strokeStyle = RA(P.ink, 0.5); c.lineWidth = 0.012;
  for (let r = 0; r < 6; r++) {
    const yy = bot - 0.5 * (r + 1);
    if (yy > top) { c.beginPath(); c.moveTo(-1.55, yy); c.lineTo(1.55, yy); c.stroke(); }
    const off = r % 2 ? 0.31 : 0;
    for (let xx = -1.55 + off; xx < 1.55; xx += 0.62) { c.beginPath(); c.moveTo(xx, Math.max(top, yy)); c.lineTo(xx, Math.min(bot, yy + 0.5)); c.stroke(); }
  }
  if (wood) {   // planks + nail heads instead of plates
    c.strokeStyle = RA('#5a3a1c', 0.5); c.lineWidth = 0.008;
    for (let xx = -1.5; xx < 1.55; xx += 0.155) { c.beginPath(); c.moveTo(xx, top); c.lineTo(xx, bot); c.stroke(); }
  }
  for (let r = 0; r < 7; r++) {
    const yy = bot - 0.5 * r;
    if (yy < top) break;
    for (let xx = -1.5; xx < 1.52; xx += 0.1) rivetU(c, xx, yy - 0.03, wood ? 0.01 : 0.013);
  }
  // ---- door bay recess and the side bays
  c.beginPath(); c.rect(-0.62, -1.84, 1.24, 1.6); shadeU(c, -0.62, -1.84, 1.24, 1.6, K.dark); ink(c, LINE.inkThin); c.stroke();
  // windows (frames + glass; night light is drawn live)
  for (const sx of [-1, 1]) {
    for (const [wy0, wy1] of [[-0.42, -1.3], [-1.98, -2.92]]) {
      const cx = sx * 1.065, hw = 0.17;
      archPath(c, cx, wy0, hw + 0.04, wy1 + hw); fo(c, K.gold, LINE.inkThin);
      archPath(c, cx, wy0 - 0.02, hw, wy1 + hw); c.fillStyle = K.glass; c.fill(); ink(c, LINE.inkThin); c.stroke();
      c.strokeStyle = RA(P.ink, 0.8); c.lineWidth = 0.014; c.beginPath(); c.moveTo(cx, wy0 - 0.02); c.lineTo(cx, wy1); c.moveTo(cx - hw, (wy0 + wy1) / 2); c.lineTo(cx + hw, (wy0 + wy1) / 2); c.stroke();
      c.strokeStyle = RA('#ffffff', 0.22); c.lineWidth = 0.025; c.beginPath(); c.moveTo(cx - hw * 0.6, wy0 - 0.1); c.lineTo(cx - hw * 0.05, wy1 + 0.05); c.stroke();
      c.beginPath(); c.rect(cx - hw - 0.06, wy0 - 0.015, hw * 2 + 0.12, 0.05); fo(c, K.goldD, LINE.inkThin);
    }
  }
  // ---- columns
  fluted(c, -1.55, top, 0.25, bot - top, K); fluted(c, 1.3, top, 0.25, bot - top, K);
  fluted(c, -0.84, -1.84 - 1.4, 0.2, bot + 1.84 + 1.4, K); fluted(c, 0.64, -1.84 - 1.4, 0.2, bot + 1.84 + 1.4, K);
  // ---- banners on the outer columns (crimson velvet, gold fringe, a coin emblem)
  for (const sx of [-1, 1]) {
    const bx = sx * 1.425, by0 = -2.98, by1 = -1.72, bw = 0.2;
    c.beginPath(); c.moveTo(bx - bw / 2, by0); c.lineTo(bx + bw / 2, by0); c.lineTo(bx + bw / 2, by1); c.lineTo(bx, by1 + 0.09); c.lineTo(bx - bw / 2, by1); c.closePath();
    shadeU(c, bx - bw / 2, by0, bw, by1 - by0 + 0.1, wood ? '#a23b2c' : '#b3202c'); ink(c, LINE.inkThin); c.stroke();
    c.strokeStyle = K.gold; c.lineWidth = 0.014; c.beginPath(); c.moveTo(bx - bw / 2 + 0.02, by0 + 0.03); c.lineTo(bx - bw / 2 + 0.02, by1 - 0.02); c.moveTo(bx + bw / 2 - 0.02, by0 + 0.03); c.lineTo(bx + bw / 2 - 0.02, by1 - 0.02); c.stroke();
    c.beginPath(); c.arc(bx, by0 + 0.38, 0.065, 0, TAU); fo(c, K.gold, LINE.inkThin);
    c.beginPath(); for (let k = 0; k < 10; k++) { const a = -PI / 2 + k * PI / 5, rr = k % 2 ? 0.022 : 0.05; c.lineTo(bx + Math.cos(a) * rr, by0 + 0.38 + Math.sin(a) * rr); } c.closePath(); c.fillStyle = K.goldD; c.fill();
    c.beginPath(); c.rect(bx - bw / 2 - 0.02, by0 - 0.03, bw + 0.04, 0.035); fo(c, K.goldD, LINE.inkThin);
  }
  // ---- copper pipes up the sides with valve wheels
  for (const sx of [-1, 1]) {
    const px = sx * 1.625;
    c.strokeStyle = P.ink; c.lineWidth = 0.075; c.beginPath(); c.moveTo(px, -0.3); c.lineTo(px, -3.2); c.stroke();
    c.strokeStyle = wood ? '#8a5a2b' : '#b8673a'; c.lineWidth = 0.05; c.stroke();
    c.strokeStyle = RA('#ffffff', 0.3); c.lineWidth = 0.012; c.beginPath(); c.moveTo(px - 0.012, -0.3); c.lineTo(px - 0.012, -3.2); c.stroke();
    for (const jy of [-0.9, -1.7, -2.5]) { c.beginPath(); c.rect(px - 0.04, jy - 0.03, 0.08, 0.06); fo(c, K.goldD, LINE.inkThin); }
    c.beginPath(); c.arc(px, -1.25, 0.07, 0, TAU); ink(c, 0.02, P.ink); c.stroke(); c.beginPath(); c.arc(px, -1.25, 0.07, 0, TAU); ink(c, 0.012, K.gold); c.stroke();
    c.beginPath(); c.moveTo(px - 0.07, -1.25); c.lineTo(px + 0.07, -1.25); c.moveTo(px, -1.32); c.lineTo(px, -1.18); c.strokeStyle = K.gold; c.lineWidth = 0.012; c.stroke();
  }
  // ---- the main door arch: gold frame, keystone, sunburst above
  archPath(c, 0, bot, BK.doorR + 0.06, -BK.doorTop); fo(c, K.gold);
  archPath(c, 0, bot, BK.doorR, -BK.doorTop); c.fillStyle = K.interior; c.fill(); ink(c, LINE.inkThin); c.stroke();
  c.save(); c.beginPath(); c.moveTo(-0.33, -1.56); c.arc(0, -1.56, 0.33, PI, 0); c.closePath(); c.clip();
  for (let i = 0; i < 9; i++) { const a0 = PI + (i / 9) * PI, a1 = PI + ((i + 1) / 9) * PI; c.beginPath(); c.moveTo(0, -1.56); c.arc(0, -1.56, 0.34, a0, a1); c.closePath(); c.fillStyle = i % 2 ? K.goldD : K.gold; c.fill(); }
  c.restore();
  c.beginPath(); c.moveTo(-0.33, -1.56); c.arc(0, -1.56, 0.33, PI, 0); c.closePath(); ink(c, LINE.inkThin); c.stroke();
  c.beginPath(); c.moveTo(-0.07, -1.5); c.lineTo(0.07, -1.5); c.lineTo(0.05, -1.62); c.lineTo(-0.05, -1.62); c.closePath(); fo(c, K.gold, LINE.inkThin);
  // ---- the balcony opening (the Banker's doorway) with machinery inside
  archPath(c, 0, -BK.balL + 0.02, BK.balR + 0.06, -BK.balC); fo(c, K.gold);
  archPath(c, 0, -BK.balL + 0.02, BK.balR, -BK.balC); c.fillStyle = K.interior; c.fill(); ink(c, LINE.inkThin); c.stroke();
  c.save(); archPath(c, 0, -BK.balL + 0.02, BK.balR, -BK.balC); c.clip();
  c.globalAlpha = 0.55; gear(c, -0.36, -2.95, 0.2, 10, 0.2, wood ? '#7a5228' : '#4a4038'); gear(c, 0.38, -2.75, 0.16, 9, 0.5, wood ? '#7a5228' : '#4a4038');
  c.strokeStyle = wood ? '#6b4520' : '#5a3a22'; c.lineWidth = 0.06; c.beginPath(); c.moveTo(-0.5, -2.2); c.quadraticCurveTo(-0.2, -2.35, -0.15, -2.6); c.moveTo(0.5, -2.3); c.quadraticCurveTo(0.2, -2.45, 0.12, -2.6); c.stroke();
  c.globalAlpha = 1;
  c.restore();
  // ---- frieze (the name plate is drawn live so it never mirrors)
  c.beginPath(); c.rect(-1.62, -3.58, 3.24, 0.31); shadeU(c, -1.62, -3.58, 3.24, 0.31, K.dark); ink(c); c.stroke();
  c.fillStyle = K.gold;
  for (let i = 0; i < 26; i++) { const zx = -1.6 + i * 0.124; c.beginPath(); c.moveTo(zx, -3.27); c.lineTo(zx + 0.062, -3.31); c.lineTo(zx + 0.124, -3.27); c.closePath(); c.fill(); c.beginPath(); c.moveTo(zx, -3.58); c.lineTo(zx + 0.062, -3.54); c.lineTo(zx + 0.124, -3.58); c.closePath(); c.fill(); }
  // ---- stepped crown (three setbacks) with ribs, gold caps and a giant coin medallion
  const tiers = [[1.46, -3.58, -3.93], [1.24, -3.93, -4.27], [1.04, -4.27, -4.6]];
  for (let i = 0; i < tiers.length; i++) {
    const [hw, y0, y1] = tiers[i];
    c.beginPath(); c.rect(-hw, y1, hw * 2, y0 - y1); shadeU(c, -hw, y1, hw * 2, y0 - y1, K.iron); ink(c); c.stroke();
    c.strokeStyle = RA(P.ink, 0.45); c.lineWidth = 0.012;
    for (let xx = -hw + 0.12; xx < hw; xx += 0.16) { c.beginPath(); c.moveTo(xx, y0 - 0.02); c.lineTo(xx, y1 + 0.05); c.stroke(); }
    c.beginPath(); c.rect(-hw - 0.03, y1, hw * 2 + 0.06, 0.045); fo(c, K.gold, LINE.inkThin);
    for (const sx of [-1, 1]) { c.beginPath(); c.moveTo(sx * hw, y1); c.lineTo(sx * (hw - 0.06), y1 - 0.1); c.lineTo(sx * (hw - 0.12), y1); c.closePath(); fo(c, K.gold, LINE.inkThin); }
    for (let xx = -hw + 0.06; xx < hw; xx += 0.12) rivetU(c, xx, y0 - 0.03, 0.011);
  }
  c.beginPath(); c.arc(0, -3.98, 0.3, 0, TAU); fo(c, K.goldD); c.beginPath(); c.arc(0, -3.98, 0.24, 0, TAU); shadeU(c, -0.24, -4.22, 0.48, 0.48, K.gold); ink(c, LINE.inkThin); c.stroke();
  c.strokeStyle = K.goldD; c.lineWidth = 0.02; for (let i = 0; i < 24; i++) { const a = i / 24 * TAU; c.beginPath(); c.moveTo(Math.cos(a) * 0.255, -3.98 + Math.sin(a) * 0.255); c.lineTo(Math.cos(a) * 0.29, -3.98 + Math.sin(a) * 0.29); c.stroke(); }
  // ---- sign struts
  for (const sx of [-1, 1]) { c.beginPath(); c.rect(sx * 0.75 - 0.04, -4.72, 0.08, 0.13); fo(c, K.dark, LINE.inkThin); rivetU(c, sx * 0.75, -4.65, 0.012); }
}
// ---- the Banker
function bankerU(c, mood, crane, t, K) {
  const bob = Math.sin(t * TAU * 0.4) * 0.008;
  let lean = 0, by = 0, headTilt = 0, headY = 0;
  if (mood === 'eager') { lean = 0.06; by = 0.04; }
  if (mood === 'gloat') { headTilt = -0.15; by = Math.abs(Math.sin(t * 14)) * -0.015; }
  if (mood === 'shot') { const k = Math.max(0, 1 - frac(t / 1.6) * 2.2); headTilt = 0.25 * k; by = -0.04 * k; lean = -0.06 * k; }
  if (mood === 'sulk') { by = 0.05; headY = 0.03; }
  if (mood === 'cards') { by = 0.03; }
  c.save(); c.translate(lean * 0.5, by + bob);
  const sk = '#e8ad7a', skD = '#c08458';
  // pipes plugging him into the wall
  c.strokeStyle = P.ink; c.lineWidth = 0.075; c.beginPath(); c.moveTo(-0.3, -2.2); c.quadraticCurveTo(-0.5, -2.3, -0.52, -2.55); c.moveTo(0.3, -2.18); c.quadraticCurveTo(0.5, -2.25, 0.52, -2.5); c.stroke();
  c.strokeStyle = '#8a5a3a'; c.lineWidth = 0.05; c.stroke();
  // torso: burgundy waistcoat, white shirt V, gold buttons, watch chain
  c.beginPath(); c.moveTo(-0.4, -1.86); c.quadraticCurveTo(-0.46, -2.2, -0.34, -2.43); c.quadraticCurveTo(0, -2.52, 0.34, -2.43); c.quadraticCurveTo(0.46, -2.2, 0.4, -1.86); c.closePath();
  shadeU(c, -0.46, -2.52, 0.92, 0.66, '#7a2430'); ink(c); c.stroke();
  c.beginPath(); c.moveTo(-0.13, -2.47); c.lineTo(0.13, -2.47); c.lineTo(0.0, -2.2); c.closePath(); fo(c, P.shirt, LINE.inkThin);
  c.beginPath(); c.moveTo(0, -2.43); c.lineTo(-0.07, -2.47); c.lineTo(-0.07, -2.4); c.closePath(); c.moveTo(0, -2.43); c.lineTo(0.07, -2.47); c.lineTo(0.07, -2.4); c.closePath(); fo(c, P.ink, LINE.hair);
  for (let i = 0; i < 3; i++) { c.beginPath(); c.arc(0.0, -2.14 + i * 0.09, 0.018, 0, TAU); fo(c, K.gold, LINE.hair * 1.5); }
  c.strokeStyle = K.gold; c.lineWidth = 0.012; c.beginPath(); c.moveTo(0.02, -2.05); c.quadraticCurveTo(0.14, -1.98, 0.27, -2.07); c.stroke();
  // iron shoulder pauldrons
  for (const sx of [-1, 1]) { c.beginPath(); c.ellipse(sx * 0.36, -2.4, 0.13, 0.09, sx * 0.3, 0, TAU); shadeU(c, sx * 0.36 - 0.13, -2.49, 0.26, 0.18, P.ironLight); ink(c, LINE.inkThin); c.stroke(); rivetU(c, sx * 0.36, -2.41, 0.014); rivetU(c, sx * 0.29, -2.37, 0.011); }
  // arms by mood (left = human, right = brass prosthetic)
  bankerArms(c, mood, t, K, sk);
  // head
  c.save(); c.translate(0, -2.72 + headY); c.rotate(headTilt);
  // ears
  c.beginPath(); c.ellipse(-0.235, 0.0, 0.045, 0.06, 0, 0, TAU); fo(c, sk, LINE.inkThin); c.beginPath(); c.ellipse(0.235, 0.0, 0.045, 0.06, 0, 0, TAU); fo(c, sk, LINE.inkThin);
  // jowly face
  c.beginPath(); c.moveTo(-0.2, -0.12); c.quadraticCurveTo(-0.24, 0.1, -0.16, 0.19); c.quadraticCurveTo(0, 0.26, 0.16, 0.19); c.quadraticCurveTo(0.24, 0.1, 0.2, -0.12); c.quadraticCurveTo(0, -0.22, -0.2, -0.12); c.closePath();
  c.fillStyle = sk; c.fill();
  c.fillStyle = skD; c.beginPath(); c.moveTo(0.2, -0.05); c.quadraticCurveTo(0.24, 0.1, 0.16, 0.19); c.quadraticCurveTo(0.06, 0.24, -0.02, 0.23); c.quadraticCurveTo(0.14, 0.15, 0.2, -0.05); c.fill();
  c.beginPath(); c.moveTo(-0.2, -0.12); c.quadraticCurveTo(-0.24, 0.1, -0.16, 0.19); c.quadraticCurveTo(0, 0.26, 0.16, 0.19); c.quadraticCurveTo(0.24, 0.1, 0.2, -0.12); c.quadraticCurveTo(0, -0.22, -0.2, -0.12); c.closePath(); ink(c); c.stroke();
  // grey side hair
  for (const sx of [-1, 1]) { c.beginPath(); c.moveTo(sx * 0.2, -0.1); c.quadraticCurveTo(sx * 0.27, -0.02, sx * 0.21, 0.07); c.lineTo(sx * 0.18, -0.02); c.closePath(); fo(c, '#9aa0a8', LINE.hair * 1.5); }
  bankerFace(c, mood, t, K, sk);
  if (mood === 'sulk') {   // steam from both ears: the player is winning
    for (const sx of [-1, 1]) for (let i = 0; i < 3; i++) {
      const u = frac(t * 1.3 + i / 3 + (sx > 0 ? 0.17 : 0));
      c.fillStyle = RA('#ffffff', 0.85 * (1 - u)); c.beginPath(); c.arc(sx * (0.27 + u * 0.12), -0.02 - u * 0.2, 0.022 + u * 0.04, 0, TAU); c.fill();
      c.strokeStyle = RA(P.ink, 0.35 * (1 - u)); c.lineWidth = 0.008; c.stroke();
    }
  }
  if (mood === 'eager') {  // a greedy glint by the human eye
    const tw = 0.5 + 0.5 * Math.sin(t * 6);
    c.fillStyle = RA('#fff6c8', 0.6 + 0.4 * tw); c.beginPath();
    const gx = -0.19, gy = -0.12, L = 0.035 + 0.025 * tw;
    c.moveTo(gx, gy - L); c.lineTo(gx + 0.01, gy - 0.01); c.lineTo(gx + L, gy); c.lineTo(gx + 0.01, gy + 0.01); c.lineTo(gx, gy + L); c.lineTo(gx - 0.01, gy + 0.01); c.lineTo(gx - L, gy); c.lineTo(gx - 0.01, gy - 0.01); c.closePath(); c.fill();
    glowU(c, gx, gy, 0.06, P.goldHot, 0.5 * tw);
  }
  // the green visor (eyeshade) + its band
  c.beginPath(); c.moveTo(-0.215, -0.1); c.quadraticCurveTo(0, -0.17, 0.215, -0.1); c.lineTo(0.27, -0.04); c.quadraticCurveTo(0, -0.1, -0.27, -0.04); c.closePath();
  c.fillStyle = RA(P.visor, 0.82); c.fill(); ink(c, LINE.inkThin); c.stroke();
  c.fillStyle = RA('#c8ffd8', 0.35); c.beginPath(); c.moveTo(-0.18, -0.1); c.quadraticCurveTo(0, -0.15, 0.1, -0.13); c.lineTo(0.1, -0.11); c.quadraticCurveTo(0, -0.125, -0.18, -0.085); c.closePath(); c.fill();
  c.strokeStyle = P.ink; c.lineWidth = 0.03; c.beginPath(); c.moveTo(-0.2, -0.105); c.quadraticCurveTo(0, -0.175, 0.2, -0.105); c.stroke();
  c.strokeStyle = '#2a6b45'; c.lineWidth = 0.018; c.stroke();
  c.restore();
  c.restore();
}
function bankerFace(c, mood, t, K, sk) {
  const bl = blinkAt(t, 0.77);
  // the human eye (left) and the red cyborg lens (right)
  const closed = mood === 'gloat' || (bl && mood !== 'shot');
  if (mood === 'shot') {
    c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin; c.beginPath(); c.moveTo(-0.13, -0.05); c.lineTo(-0.07, 0.0); c.moveTo(-0.07, -0.05); c.lineTo(-0.13, 0.0); c.stroke();
  } else if (closed) {
    c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin; c.beginPath(); c.arc(-0.1, -0.02, 0.03, PI * 1.1, PI * 1.9); c.stroke();
  } else {
    const lid = mood === 'smug' || mood === 'cards' || mood === 'sulk' ? 0.5 : 0;
    c.beginPath(); c.ellipse(-0.1, -0.025, 0.035, 0.03, 0, 0, TAU); fo(c, '#fff', LINE.hair * 1.5);
    const lx = mood === 'sulk' ? -0.016 : mood === 'eager' ? 0.012 : 0.006;
    c.fillStyle = P.ink; c.beginPath(); c.arc(-0.1 + lx, -0.022, 0.016, 0, TAU); c.fill();
    if (lid) { c.fillStyle = sk; c.beginPath(); c.ellipse(-0.1, -0.04, 0.04, 0.025, 0, PI, TAU); c.fill(); c.fillRect(-0.14, -0.045, 0.08, 0.012); c.strokeStyle = P.ink; c.lineWidth = LINE.hair * 1.5; c.beginPath(); c.moveTo(-0.137, -0.034); c.lineTo(-0.063, -0.034); c.stroke(); }
    if (mood === 'eager') { c.fillStyle = '#fff'; c.beginPath(); c.arc(-0.095, -0.03, 0.006, 0, TAU); c.fill(); }
  }
  c.beginPath(); c.arc(0.1, -0.025, 0.05, 0, TAU); fo(c, K.goldD, LINE.inkThin);
  c.beginPath(); c.arc(0.1, -0.025, 0.033, 0, TAU); c.fillStyle = '#5a0a0a'; c.fill();
  const pulse = 0.6 + 0.4 * Math.sin(t * 3);
  c.fillStyle = MX('#ff3030', '#ffb0a0', mood === 'eager' ? 0.4 : 0); c.beginPath(); c.arc(0.1, -0.025, 0.018 + (mood === 'eager' ? 0.006 : 0), 0, TAU); c.fill();
  glowU(c, 0.1, -0.025, 0.07, '#ff2a2a', 0.45 * pulse);
  // brows
  c.strokeStyle = '#7d838c'; c.lineWidth = 0.03;
  const bA = mood === 'sulk' ? 0.03 : mood === 'eager' || mood === 'gloat' ? -0.015 : mood === 'smug' ? 0.012 : 0;
  c.beginPath(); c.moveTo(-0.15, -0.075 - bA); c.lineTo(-0.05, -0.075 + bA); c.stroke();
  c.beginPath(); c.moveTo(0.05, -0.085 + bA); c.lineTo(0.15, -0.085 - bA); c.stroke();
  // nose (round, ruddy)
  c.beginPath(); c.ellipse(0, 0.04, 0.05, 0.045, 0, 0, TAU); fo(c, '#e58a6a', LINE.inkThin);
  c.fillStyle = RA('#ffffff', 0.45); c.beginPath(); c.arc(-0.015, 0.025, 0.012, 0, TAU); c.fill();
  // mouth
  const mo = mood;
  if (mo === 'gloat' || mo === 'shot') {
    const open = mo === 'gloat' ? 0.06 + Math.abs(Math.sin(t * 14)) * 0.02 : 0.07;
    c.beginPath(); c.ellipse(0, 0.14, 0.075, open, 0, 0, TAU); fo(c, '#4a1414', LINE.inkThin);
    if (mo === 'gloat') { c.fillStyle = '#fff'; c.fillRect(-0.05, 0.14 - open + 0.005, 0.1, 0.022); c.fillStyle = K.gold; c.fillRect(0.012, 0.14 - open + 0.005, 0.022, 0.022); }
  } else if (mo === 'eager') {
    c.beginPath(); c.moveTo(-0.09, 0.115); c.quadraticCurveTo(0, 0.2, 0.09, 0.115); c.closePath(); fo(c, '#4a1414', LINE.inkThin);
    c.fillStyle = '#fff'; c.fillRect(-0.07, 0.117, 0.14, 0.022); c.fillStyle = K.gold; c.fillRect(0.02, 0.117, 0.024, 0.022);
  } else if (mo === 'sulk' || mo === 'cards') {
    c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin; c.beginPath(); c.arc(0, 0.19, 0.06, PI * 1.2, PI * 1.8); c.stroke();
  } else {
    c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin; c.beginPath(); c.moveTo(-0.07, 0.13); c.quadraticCurveTo(0.0, 0.15, 0.08, 0.11); c.stroke();
  }
  // handlebar moustache
  c.beginPath(); c.moveTo(0, 0.075); c.bezierCurveTo(-0.06, 0.06, -0.12, 0.08, -0.16, 0.05); c.bezierCurveTo(-0.18, 0.04, -0.19, 0.06, -0.175, 0.075); c.bezierCurveTo(-0.13, 0.13, -0.05, 0.11, 0, 0.1);
  c.bezierCurveTo(0.05, 0.11, 0.13, 0.13, 0.175, 0.075); c.bezierCurveTo(0.19, 0.06, 0.18, 0.04, 0.16, 0.05); c.bezierCurveTo(0.12, 0.08, 0.06, 0.06, 0, 0.075); c.closePath();
  fo(c, '#8d939c', LINE.inkThin);
  // the cigar (in the corner of the mouth) unless he just spat it
  if (mo !== 'shot') {
    const droop = mo === 'sulk' || mo === 'cards' ? 0.5 : mo === 'smug' ? -0.35 : mo === 'eager' ? Math.sin(t * 9) * 0.15 - 0.1 : -0.1;
    c.save(); c.translate(0.07, 0.13); c.rotate(droop);
    c.beginPath(); rrP(c, 0, -0.018, 0.2, 0.036, 0.016); fo(c, '#6b3a1e', LINE.inkThin);
    c.fillStyle = '#c0392b'; c.fillRect(0.03, -0.018, 0.02, 0.036); c.fillStyle = K.gold; c.fillRect(0.034, -0.018, 0.012, 0.036);
    c.fillStyle = '#9a9a9a'; c.fillRect(0.185, -0.016, 0.018, 0.032);
    const ember = 0.6 + 0.4 * Math.sin(t * 2.3);
    c.fillStyle = MX('#ff5a1f', '#ffd25a', ember); c.beginPath(); c.arc(0.205, 0, 0.014, 0, TAU); c.fill();
    glowU(c, 0.205, 0, 0.05, '#ff7a2a', 0.5 * ember);
    c.restore();
    // smoke wisps
    for (let i = 0; i < 3; i++) {
      const u = frac(t * 0.35 + i / 3), sx = 0.27 + Math.sin(u * 5 + i) * 0.04 + u * 0.05, sy = 0.1 - u * 0.5;
      c.fillStyle = RA('#d8d8d8', 0.45 * (1 - u)); c.beginPath(); c.arc(sx, sy, 0.025 + u * 0.05, 0, TAU); c.fill();
    }
  } else {
    // cough: black smoke bursting out, the cigar tumbling away
    const u = frac(t / 1.6);
    for (let i = 0; i < 5; i++) {
      const v = clamp(u * 1.6 - i * 0.08, 0, 1);
      if (v <= 0 || v >= 1) continue;
      c.fillStyle = RA('#1e1b19', 0.75 * (1 - v)); c.beginPath(); c.arc(0.05 + v * (0.25 + i * 0.05), 0.12 - v * (0.15 + i * 0.06), 0.04 + v * 0.09, 0, TAU); c.fill();
    }
    c.save(); c.translate(0.12 + u * 0.7, 0.1 - Math.sin(u * PI) * 0.5 + u * 0.3); c.rotate(u * 14);
    c.beginPath(); rrP(c, -0.1, -0.018, 0.2, 0.036, 0.016); fo(c, '#6b3a1e', LINE.inkThin); c.fillStyle = '#ff7a2a'; c.beginPath(); c.arc(0.1, 0, 0.014, 0, TAU); c.fill();
    c.restore();
  }
}
function bankerArms(c, mood, t, K, sk) {
  const sleeve = P.shirt, brass = P.brass;
  const L = [0, 0, 0, 0, 0, 0], Rr = [0, 0, 0, 0, 0, 0];
  const set = (a, x0, y0, x1, y1, x2, y2) => { a[0] = x0; a[1] = y0; a[2] = x1; a[3] = y1; a[4] = x2; a[5] = y2; };
  let lHand = true, rHand = true;
  switch (mood) {
    case 'smug': case 'sulk': {   // arms folded over the belly
      set(L, -0.38, -2.38, -0.44, -2.08, 0.16, -2.04);
      set(Rr, 0.38, -2.38, 0.44, -2.1, -0.14, -2.1);
      break;
    }
    case 'eager': {               // rubbing hands
      const r = Math.sin(t * 12) * 0.03;
      set(L, -0.38, -2.38, -0.42, -2.1, -0.02 + r, -2.14);
      set(Rr, 0.38, -2.38, 0.42, -2.1, 0.03 - r, -2.12);
      break;
    }
    case 'gloat': {               // one hand on the belly, one pointing down at the street
      set(L, -0.38, -2.38, -0.44, -2.12, -0.12, -2.02);
      const p = Math.sin(t * 7) * 0.02;
      set(Rr, 0.38, -2.38, 0.6, -2.3, 0.82, -2.12 + p);
      break;
    }
    case 'shot': {                // the throwing arm flung up
      const u = frac(t / 1.6), k = clamp(1 - u * 1.5, 0, 1);
      set(L, -0.38, -2.38, -0.5, -2.2, -0.38, -2.0);
      set(Rr, 0.38, -2.38, 0.58 + 0.06 * k, -2.62 - 0.12 * k, 0.62 + 0.15 * k, -2.92 - 0.12 * k);
      break;
    }
    case 'cards': {               // a fan of cards in the left hand, the right lays one down
      set(L, -0.38, -2.38, -0.44, -2.12, -0.22, -2.02);
      const lay = Math.sin(t * 1.3);
      set(Rr, 0.38, -2.38, 0.42, -2.1, 0.22 + lay * 0.06, -1.98);
      break;
    }
    case 'crane': default: {      // polite: hands clasped, a small bow
      set(L, -0.38, -2.38, -0.42, -2.1, -0.04, -2.04);
      set(Rr, 0.38, -2.38, 0.42, -2.1, 0.05, -2.04);
      break;
    }
  }
  limb2(c, L, 0.1, sleeve, sleeve);
  // sleeve garter
  c.strokeStyle = P.crimson; c.lineWidth = 0.025; c.beginPath(); c.moveTo(lerp(L[0], L[2], 0.55) - 0.04, lerp(L[1], L[3], 0.55)); c.lineTo(lerp(L[0], L[2], 0.55) + 0.04, lerp(L[1], L[3], 0.55)); c.stroke();
  limb2(c, Rr, 0.085, brass, P.brassDark);
  rivetU(c, Rr[2], Rr[3], 0.02);
  if (mood === 'cards') {
    // fan of cards
    c.save(); c.translate(L[4], L[5] - 0.03);
    for (let i = 0; i < 5; i++) { c.save(); c.rotate(-0.5 + i * 0.25); c.beginPath(); rrP(c, -0.03, -0.14, 0.07, 0.1, 0.01); fo(c, '#fffaf0', LINE.hair * 1.5); c.fillStyle = i % 2 ? P.crimson : P.ink; c.font = 'bold 0.04px ' + FONT.deco; c.textAlign = 'center'; c.fillText(i % 2 ? '♥' : '♠', 0.005, -0.1); c.restore(); }
    c.restore();
  }
  if (lHand) { c.beginPath(); c.arc(L[4], L[5], 0.05, 0, TAU); fo(c, sk, LINE.inkThin); }
  if (rHand) {   // the brass clamp hand
    c.save(); c.translate(Rr[4], Rr[5]);
    c.beginPath(); c.arc(0, 0, 0.045, 0, TAU); fo(c, P.brassLight, LINE.inkThin);
    c.strokeStyle = P.ink; c.lineWidth = 0.022; c.beginPath(); c.moveTo(0.02, -0.03); c.lineTo(0.06, -0.05); c.moveTo(0.03, 0.02); c.lineTo(0.065, 0.03); c.stroke();
    c.strokeStyle = P.brass; c.lineWidth = 0.012; c.stroke();
    c.restore();
  }
}
// the telescopic crane built into the facade beside the doorway
function craneU(c, crane, t, K) {
  const [mx, my] = BK.mount;
  const [tx, ty] = craneTipU(crane);
  const dx = tx - mx, dy = ty - my, L = Math.hypot(dx, dy), ang = Math.atan2(dy, dx);
  c.save(); c.translate(mx, my); c.rotate(ang);
  // mount: a riveted iron drum
  const sec = [[0, 0.12, P.ironLight], [L * 0.33, 0.095, P.iron], [L * 0.62, 0.075, '#e0b020']];
  for (let i = 0; i < 3; i++) {
    const x0 = sec[i][0], w = sec[i][1], x1 = i < 2 ? sec[i + 1][0] + 0.06 : L;
    c.beginPath(); c.rect(x0, -w / 2, x1 - x0, w); shadeU(c, x0, -w / 2, Math.max(0.05, x1 - x0), w, sec[i][2]); ink(c, LINE.inkThin); c.stroke();
    if (i === 2) {   // hazard stripes on the last section
      c.save(); c.beginPath(); c.rect(x0, -w / 2, x1 - x0, w); c.clip();
      c.fillStyle = P.ink; for (let xx = x0 - 0.1; xx < x1; xx += 0.09) { c.beginPath(); c.moveTo(xx, w / 2); c.lineTo(xx + 0.045, w / 2); c.lineTo(xx + 0.085, -w / 2); c.lineTo(xx + 0.04, -w / 2); c.closePath(); c.fill(); }
      c.restore(); c.beginPath(); c.rect(x0, -w / 2, x1 - x0, w); ink(c, LINE.inkThin); c.stroke();
    }
    rivetU(c, x0 + 0.03, 0, 0.012);
  }
  c.beginPath(); c.arc(0, 0, 0.1, 0, TAU); shadeU(c, -0.1, -0.1, 0.2, 0.2, P.ironLight); ink(c); c.stroke(); rivetU(c, 0, 0, 0.022);
  c.restore();
  // the claw at the tip (opens on the way, closes politely at full reach)
  const open = crane > 0.05 && crane < 0.97 ? 0.5 : 0.12;
  c.save(); c.translate(tx, ty);
  c.beginPath(); c.arc(0, 0, 0.05, 0, TAU); fo(c, P.iron, LINE.inkThin);
  for (const sx of [-1, 1]) {
    c.save(); c.rotate(sx * open);
    c.beginPath(); c.moveTo(0, 0.02); c.quadraticCurveTo(sx * 0.07, 0.08, sx * 0.03, 0.15); c.lineTo(sx * 0.0, 0.13); c.quadraticCurveTo(sx * 0.035, 0.08, -sx * 0.01, 0.03); c.closePath(); fo(c, P.ironLight, LINE.inkThin);
    c.restore();
  }
  c.restore();
}
function shutterU(c, x0, y0, w, h, k, K, lock) {
  if (k <= 0.001) return;
  const hh = h * clamp(k, 0, 1);
  c.beginPath(); c.rect(x0, y0, w, hh); shadeU(c, x0, y0, w, h, '#8d939c'); ink(c, LINE.inkThin); c.stroke();
  c.strokeStyle = RA(P.ink, 0.5); c.lineWidth = 0.01;
  for (let yy = y0 + 0.05; yy < y0 + hh; yy += 0.05) { c.beginPath(); c.moveTo(x0, yy); c.lineTo(x0 + w, yy); c.stroke(); }
  c.strokeStyle = RA('#ffffff', 0.25); for (let yy = y0 + 0.06; yy < y0 + hh; yy += 0.05) { c.beginPath(); c.moveTo(x0, yy); c.lineTo(x0 + w, yy); c.stroke(); }
  c.beginPath(); c.rect(x0 - 0.01, y0 + hh - 0.04, w + 0.02, 0.04); fo(c, '#5d636c', LINE.inkThin);
  if (lock && k > 0.98) {
    const lx = x0 + w / 2, ly = y0 + hh - 0.02;
    c.beginPath(); c.arc(lx, ly - 0.06, 0.04, PI, 0); ink(c, 0.025); c.stroke(); ink(c, 0.012, P.ironLight); c.stroke();
    c.beginPath(); rrP(c, lx - 0.055, ly - 0.06, 0.11, 0.09, 0.015); fo(c, K.gold, LINE.inkThin); c.fillStyle = P.ink; c.beginPath(); c.arc(lx, ly - 0.025, 0.01, 0, TAU); c.fill();
  }
}
export const drawBank = guard('drawBank', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const f = st.facing < 0 ? -1 : 1;
  const wood = !!st.wooden, night = !!st.night, jammed = !!st.jammed;
  const shut = clamp(num(st.shutters, 0), 0, 1);
  const bk = st.banker || {};
  const mood = typeof bk.mood === 'string' ? bk.mood : 'smug';
  const crane = clamp(num(bk.crane, 0), 0, 1);
  const K = bankColours(wood);
  beginU(ctx, x, y, s, f);
  const c = ctx;
  sprite(c, wood ? 'bankW' : 'bankI', [-1.8, -4.8, 3.6, 4.86], (c2) => bankFacade(c2, wood));
  // ---- the name plate (never mirrored)
  textU(c, 'GOLD BANK', 0, -3.425, 0.2, { color: K.gold, font: FONT.deco, stroke: P.ink, strokeW: 0.03, maxW: 2.6 });
  // ---- the vault behind the door: gold glow + stacked bars, the round door (open) or jammed shut
  const doorBot = -BK.plinth, dr = BK.doorR;
  c.save(); archPath(c, 0, doorBot, dr, -BK.doorTop); c.clip();
  if (!jammed) {
    glowU(c, 0, -0.45, 0.75, P.gold, night ? 0.5 : 0.35);
    for (let r = 0; r < 3; r++) for (let i = 0; i < 4 - r; i++) {
      const bx = -0.22 + i * 0.13 + r * 0.065, by = doorBot - 0.07 - r * 0.07;
      c.beginPath(); c.moveTo(bx - 0.06, by + 0.03); c.lineTo(bx + 0.06, by + 0.03); c.lineTo(bx + 0.045, by - 0.03); c.lineTo(bx - 0.045, by - 0.03); c.closePath(); fo(c, K.gold, LINE.hair * 1.5);
    }
  }
  c.restore();
  if (!jammed) {
    // the round vault door swung open on its hinge (seen edge-on)
    c.beginPath(); c.ellipse(-dr - 0.02, -0.74, 0.12, 0.47, 0, 0, TAU); shadeU(c, -dr - 0.14, -1.21, 0.24, 0.94, P.ironLight); ink(c); c.stroke();
    c.beginPath(); c.ellipse(-dr + 0.02, -0.74, 0.07, 0.4, 0, 0, TAU); fo(c, K.goldD, LINE.inkThin);
    for (let i = 0; i < 5; i++) rivetU(c, -dr - 0.03, -1.05 + i * 0.15, 0.014);
  } else {
    // shut tight: round door, spoke wheel, a wrench jammed in it, steam from the hinge, a red beacon
    c.beginPath(); c.arc(0, -0.74, 0.47, 0, TAU); shadeU(c, -0.47, -1.21, 0.94, 0.94, P.ironLight); ink(c); c.stroke();
    c.beginPath(); c.arc(0, -0.74, 0.4, 0, TAU); ink(c, 0.02, P.ironDark); c.stroke();
    for (let i = 0; i < 12; i++) { const a = i / 12 * TAU; rivetU(c, Math.cos(a) * 0.43, -0.74 + Math.sin(a) * 0.43, 0.014); }
    c.save(); c.translate(0, -0.74); c.rotate(Math.sin(t * 20) * 0.02);
    c.strokeStyle = P.ink; c.lineWidth = 0.05; for (let i = 0; i < 3; i++) { const a = i / 3 * PI; c.beginPath(); c.moveTo(Math.cos(a) * 0.2, Math.sin(a) * 0.2); c.lineTo(-Math.cos(a) * 0.2, -Math.sin(a) * 0.2); c.stroke(); }
    c.strokeStyle = K.gold; c.lineWidth = 0.028; for (let i = 0; i < 3; i++) { const a = i / 3 * PI; c.beginPath(); c.moveTo(Math.cos(a) * 0.2, Math.sin(a) * 0.2); c.lineTo(-Math.cos(a) * 0.2, -Math.sin(a) * 0.2); c.stroke(); }
    c.beginPath(); c.arc(0, 0, 0.2, 0, TAU); ink(c, 0.05); c.stroke(); c.beginPath(); c.arc(0, 0, 0.2, 0, TAU); ink(c, 0.028, K.gold); c.stroke();
    c.beginPath(); c.arc(0, 0, 0.05, 0, TAU); fo(c, K.goldD, LINE.inkThin);
    // the wrench
    c.rotate(-0.7); c.beginPath(); rrP(c, -0.04, -0.03, 0.62, 0.06, 0.02); fo(c, '#c8ccd2', LINE.inkThin);
    c.beginPath(); c.arc(0.62, 0, 0.07, 0.5, TAU - 0.5); c.lineTo(0.6, 0); c.closePath(); fo(c, '#c8ccd2', LINE.inkThin);
    c.restore();
    for (let i = 0; i < 3; i++) { const u = frac(t * 0.8 + i / 3); c.fillStyle = RA('#ffffff', 0.6 * (1 - u)); c.beginPath(); c.arc(-0.5 - u * 0.25, -0.95 - u * 0.2, 0.04 + u * 0.08, 0, TAU); c.fill(); }
    const bA = t * 5;
    c.beginPath(); rrP(c, -0.06, -1.62, 0.12, 0.09, 0.03); fo(c, '#3a0c0c', LINE.inkThin);
    c.beginPath(); c.arc(0, -1.66, 0.045, PI, 0); fo(c, '#ff3a2a', LINE.inkThin);
    glowU(c, Math.cos(bA) * 0.25, -1.66, 0.3, '#ff2a1a', 0.35 + 0.35 * Math.max(0, Math.cos(bA)));
  }
  // ---- marquee bulbs around the door arch, chasing
  for (let i = 0; i <= 12; i++) {
    const a = PI + (i / 12) * PI, bx = Math.cos(a) * (dr + 0.03), by = -BK.doorTop + Math.sin(a) * (dr + 0.03);
    const on = ((i + Math.floor(t * 6)) % 3) === 0;
    c.fillStyle = on ? '#fff6c8' : '#8a6a2a'; c.beginPath(); c.arc(bx, by, 0.022, 0, TAU); c.fill(); c.strokeStyle = P.ink; c.lineWidth = LINE.hair; c.stroke();
    if (on) glowU(c, bx, by, 0.07, P.goldHot, night ? 0.9 : 0.6);
  }
  // ---- night: lit windows
  if (night) {
    for (const sx of [-1, 1]) for (const [wy0, wy1] of [[-0.42, -1.3], [-1.98, -2.92]]) {
      const cx = sx * 1.065, hw = 0.17;
      archPath(c, cx, wy0 - 0.02, hw, wy1 + hw); c.fillStyle = RA('#ffcf6a', 0.85); c.fill();
      c.strokeStyle = RA(P.ink, 0.8); c.lineWidth = 0.014; c.beginPath(); c.moveTo(cx, wy0 - 0.02); c.lineTo(cx, wy1); c.moveTo(cx - hw, (wy0 + wy1) / 2); c.lineTo(cx + hw, (wy0 + wy1) / 2); c.stroke();
      glowU(c, cx, (wy0 + wy1) / 2, 0.45, '#ffb84a', 0.35 + 0.05 * Math.sin(t * 3 + sx));
    }
  }
  // ---- steam from the pipe vents
  for (const sx of [-1, 1]) for (let i = 0; i < 4; i++) {
    const u = frac(t * 0.42 + i / 4 + (sx > 0 ? 0.13 : 0));
    const px = sx * (1.625 + u * 0.12 + Math.sin(u * 6 + i) * 0.03), py = -3.22 - u * 0.5, r = 0.028 + u * 0.075;
    c.fillStyle = RA('#f6f3ee', 0.6 * (1 - u) * Math.min(1, u * 6)); c.beginPath(); c.arc(px, py, r, 0, TAU); c.fill();
    c.fillStyle = RA('#ffffff', 0.5 * (1 - u) * Math.min(1, u * 6)); c.beginPath(); c.arc(px - r * 0.3, py - r * 0.3, r * 0.5, 0, TAU); c.fill();
  }
  // ---- the Banker in his doorway, the balcony ledge in front of him
  const shutTop = shut > 0.001;
  c.save(); archPath(c, 0, -BK.balL + 0.02, BK.balR, -BK.balC); c.clip();
  c.translate(0, -1.9); c.scale(1.15, 1.15); c.translate(0, 1.9);
  bankerU(c, mood, crane, t, K);
  c.restore();
  // the ledge (in front of his belly) with a gold rail; cards laid out during a jam
  c.beginPath(); c.rect(-0.7, -1.98, 1.4, 0.12); shadeU(c, -0.7, -1.98, 1.4, 0.12, K.dark); ink(c); c.stroke();
  c.beginPath(); c.rect(-0.72, -2.02, 1.44, 0.045); fo(c, K.gold, LINE.inkThin);
  for (let i = 0; i < 8; i++) { const bx = -0.6 + i * 0.172; c.beginPath(); c.rect(bx - 0.015, -1.98, 0.03, 0.1); c.fillStyle = K.goldD; c.fill(); }
  if (mood === 'cards') {
    for (let i = 0; i < 4; i++) { c.save(); c.translate(-0.42 + i * 0.13, -2.05); c.rotate((i - 1.5) * 0.06); c.beginPath(); rrP(c, -0.04, -0.03, 0.08, 0.055, 0.008); fo(c, '#fffaf0', LINE.hair * 1.5); textU(c, ['A', '7', 'K', '3'][i], 0, -0.003, 0.035, { color: i % 2 ? P.crimson : P.ink, font: FONT.deco }); c.restore(); }
    // a card on the street step too
    c.save(); c.translate(0.32, -0.27); c.rotate(0.3); c.beginPath(); rrP(c, -0.05, -0.035, 0.1, 0.07, 0.01); fo(c, '#fffaf0', LINE.hair * 1.5); c.fillStyle = P.crimson; c.font = 'bold 0.045px ' + FONT.deco; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('♦', 0, 0); c.restore();
  }
  // ---- the crane (folded beside the doorway, or reaching into the street)
  if (mood === 'crane' || crane > 0) craneU(c, crane, t, K);
  else craneU(c, 0, t, K);
  // ---- shutters (iron roller shutters over every opening)
  if (shutTop) {
    shutterU(c, -BK.doorR - 0.02, -BK.doorTop - BK.doorR - 0.02, (BK.doorR + 0.02) * 2, BK.doorTop + BK.doorR + 0.02 - BK.plinth, shut, K, true);
    shutterU(c, -BK.balR - 0.02, -BK.balC - BK.balR - 0.02, (BK.balR + 0.02) * 2, BK.balC + BK.balR - BK.balL + 0.1, shut, K, false);
    for (const sx of [-1, 1]) for (const [wy0, wy1] of [[-0.42, -1.3], [-1.98, -2.92]]) shutterU(c, sx * 1.065 - 0.19, wy1 - 0.02, 0.38, wy0 - wy1 + 0.02, shut, K, false);
  }
  rs(ctx);
  return bankGeometry(x, y, s, f, crane);
});
//>>BANK

//<<SIGN
// ================================================================================================ THE ROOF SIGN (split-flap)
// A riveted iron cabinet with a gold trim and marquee bulbs; a row of flap tiles. When the text for an id changes, every changed
// character flips on its own hinge straight from the old glyph to the new one, all together, timed only from st.t.
// THE SIGN NEVER SHOWS A NUMBER THAT WAS NOT TRUE (the Golden Rule): no rolling through the digits in between, no stagger (a staggered
// row composes values that never existed: 1.01 -> 0.99 would read 0.01 then 0.91), and a new value arriving mid-flip first commits the
// one in flight. At any instant the composed row is the previous value or the current one; a flap lasts FLIP_STEP (50 ms), shorter
// than the 100 ms between snapshots, so the board is true within one frame of the engine. The tile count follows the text both ways
// (a word like LIQUIDATED never leaves the coin's value squeezed into ten narrow tiles); on a resize the new tiles flip in from blank.
// The hourglass flap (stale quote) folds in at the right end with draining sand.
const SIGNS = new Map();
const SIGN_COL = {
  crimson: [P.crimson, P.crimsonGlow], cyan: [P.cyan, P.cyanGlow], gold: [P.gold, P.goldHot], green: ['#3fe07a', '#a6ffc2'],
};
const FLIP_STEP = 0.05;
function signState(id, text, t, hg) {
  let S = SIGNS.get(id);
  const raw = String(text == null ? '' : text);
  const want = Math.max(5, raw.length);
  if (!S) {
    S = { n: want, target: null, cells: [], lastT: t, hgOn: !!hg, hgT: -10 };
    if (SIGNS.size > 64) SIGNS.delete(SIGNS.keys().next().value);
    SIGNS.set(id, S);
  }
  const padL = Math.floor((want - raw.length) / 2);
  const padded = ' '.repeat(padL) + raw + ' '.repeat(want - raw.length - padL);
  if (t < S.lastT - 0.25) { S.target = null; S.cells = []; }   // the clock went backwards (a looping fixture): snap
  S.lastT = t;
  if (S.target === null) {                                      // first sight: the board simply shows the text
    S.n = want; S.target = padded; S.cells = [];
    for (let i = 0; i < want; i++) S.cells.push({ from: padded[i], steps: [padded[i]], start: -1e9 });
  } else if (want !== S.n) {                                    // re-tiled (a word <-> the value): every tile flips in from blank
    S.n = want; S.target = padded; S.cells = [];
    for (let i = 0; i < want; i++) S.cells.push(padded[i] === ' ' ? { from: ' ', steps: [' '], start: -1e9 } : { from: ' ', steps: [padded[i]], start: t });
  } else if (padded !== S.target) {
    for (let i = 0; i < S.n; i++) {
      const to = padded[i], cell = S.cells[i];
      const last = cell.steps[cell.steps.length - 1];             // the glyph this tile last committed to (a true value)
      cell.from = last;                                           // a flap in flight is committed first: it never mixes two updates
      cell.steps = [to];
      cell.start = to === last ? -1e9 : t;                        // unchanged tiles rest; changed tiles all flip now, together
    }
    S.target = padded;
  }
  return S;
}
// debug / regression: what the board reads at time t (the settled glyph of every tile, ' ' for blank) and what it is heading to
export function roofSignDebug(id, t) {
  const S = SIGNS.get(id == null ? 'roof' : String(id));
  if (!S) return null;
  return { shown: S.cells.map((c) => cellChar(c, num(t, S.lastT))).join(''), target: S.target, n: S.n };
}
function cellChar(cell, t) {
  if (t < cell.start) return cell.from;
  const k = Math.floor((t - cell.start) / FLIP_STEP);
  return k >= cell.steps.length ? cell.steps[cell.steps.length - 1] : (k <= 0 ? cell.from : cell.steps[k - 1]);
}
function signFrame(c, W, wood) {
  // unit = the sign's height; the cabinet spans x in [-W/2, W/2], y in [-0.5, 0.5]
  const K = bankColours(wood);
  c.beginPath(); rrP(c, -W / 2, -0.5, W, 1, 0.08); shadeU(c, -W / 2, -0.5, W, 1, wood ? '#7a5230' : '#2b2e35'); ink(c, 0.04); c.stroke();
  c.beginPath(); rrP(c, -W / 2 + 0.055, -0.445, W - 0.11, 0.89, 0.05); ink(c, 0.03, K.gold); c.stroke();
  c.beginPath(); rrP(c, -W / 2 + 0.11, -0.33, W - 0.22, 0.66, 0.035); c.fillStyle = '#060608'; c.fill(); ink(c, 0.025); c.stroke();
  for (let i = 0; i < 2; i++) { const yy = i ? 0.47 : -0.47; for (let xx = -W / 2 + 0.1; xx < W / 2 - 0.05; xx += 0.2) rivetU(c, xx, yy, 0.016); }
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) {
    c.beginPath(); c.moveTo(sx * W / 2, sy * 0.5); c.lineTo(sx * (W / 2 - 0.16), sy * 0.5); c.lineTo(sx * W / 2, sy * 0.34); c.closePath(); fo(c, K.gold, 0.02);
  }
}
function flapTile(c, x, y, w, h, wood) {
  c.beginPath(); rrP(c, x, y, w, h, Math.min(w, h) * 0.12);
  c.fillStyle = wood ? '#2a1d12' : P.flap; c.fill();
}
function glyphHalf(c, ch, x, y, w, h, half, col, font, sy) {
  // draw the top (half = -1) or bottom (half = 1) half of a character, squashed vertically by sy about the hinge (y + h/2)
  if (ch === ' ') return;
  const hy = y + h / 2;
  c.save();
  c.beginPath(); if (half < 0) c.rect(x, y, w, h / 2); else c.rect(x, hy, w, h / 2); c.clip();
  c.translate(0, hy); c.scale(1, sy); c.translate(0, -hy);
  c.fillStyle = col; c.font = font; c.textAlign = 'center'; c.textBaseline = 'middle';
  c.fillText(ch, x + w / 2, hy + h * 0.04);
  c.restore();
}
export const drawRoofSign = guard('drawRoofSign', function (ctx, cx, cy, w, h, st) {
  st = st || {};
  w = num(w, 200); h = num(h, 80);
  if (!(w > 4 && h > 4)) return;
  const t = num(st.t, 0);
  const id = st.id == null ? 'roof' : String(st.id);
  const cols = SIGN_COL[st.color] || SIGN_COL.gold;
  const S = signState(id, st.text, t, st.hourglass);
  const wood = !!st.wooden;
  const W = w / h;
  sv(ctx);
  ctx.translate(cx, cy);
  { const m = ctx.getTransform(); if (m.a * m.d - m.b * m.c < 0) ctx.scale(-1, 1); }   // a mirrored world never mirrors the sign
  ctx.scale(h, h); ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  const c = ctx;
  sprite(c, 'signFrame' + W.toFixed(2) + (wood ? 'w' : ''), [-W / 2 - 0.04, -0.54, W + 0.08, 1.08], (c2) => signFrame(c2, W, wood));
  // marquee bulbs chasing along the top and bottom rails
  const nb = Math.max(6, Math.round((W - 0.3) / 0.16));
  for (let i = 0; i < nb; i++) {
    const bx = -W / 2 + 0.17 + (i * (W - 0.34)) / (nb - 1);
    for (const by of [-0.39, 0.39]) {
      const on = ((i + (by < 0 ? 0 : 2) + Math.floor(t * 5)) % 4) < 2;
      c.fillStyle = on ? '#fff3c4' : '#6b5122'; c.beginPath(); c.arc(bx, by, 0.028, 0, TAU); c.fill();
      if (on) glowU(c, bx, by, 0.085, P.goldHot, 0.55);
    }
  }
  // tiles
  const hg = !!st.hourglass;
  if (hg !== S.hgOn) { S.hgOn = hg; S.hgT = t; }
  const hgK = clamp((t - S.hgT) / 0.18, 0, 1), hgVis = S.hgOn ? hgK : 1 - hgK;
  const innerW = W - 0.3, hgW = 0.36 * Math.max(hgVis, 0.0001);
  const n = S.n;
  const cellW = Math.min((innerW - (hgVis > 0.01 ? hgW + 0.04 : 0)) / n, 0.6);
  const cellH = 0.6, gap = cellW * 0.08;
  const rowW = cellW * n + (hgVis > 0.01 ? hgW + 0.04 : 0);
  let x0 = -rowW / 2;
  const fpx = Math.min(cellH * 0.86, (cellW - gap) * 1.42);
  const font = 'bold ' + fpx.toFixed(3) + 'px ' + FONT.sign;
  const y0 = -cellH / 2;
  const glowCol = cols[1], col = cols[0];
  for (let i = 0; i < n; i++) {
    const cell = S.cells[i];
    const x = x0 + i * cellW + gap / 2, cw = cellW - gap;
    flapTile(c, x, y0, cw, cellH, wood);
    const ch = cellChar(cell, t);
    let anim = false;
    if (t >= cell.start) {
      const kf = (t - cell.start) / FLIP_STEP;
      const k = Math.floor(kf);
      if (k < cell.steps.length) {
        anim = true;
        const p = kf - k;
        const prev = k === 0 ? cell.from : cell.steps[k - 1], next = cell.steps[k];
        // behind: the new top half and the old bottom half
        glyphHalf(c, next, x, y0, cw, cellH, -1, col, font, 1);
        glyphHalf(c, prev, x, y0, cw, cellH, 1, col, font, 1);
        // the falling flap
        if (p < 0.5) {
          const sy = Math.cos(p * PI);
          c.save(); c.beginPath(); c.rect(x, y0 + cellH / 2 - (cellH / 2) * sy, cw, (cellH / 2) * sy); c.fillStyle = MX(P.flap, '#2c2c36', p); c.fill(); c.restore();
          glyphHalf(c, prev, x, y0, cw, cellH, -1, col, font, sy);
        } else {
          const sy = Math.sin((p - 0.5) * PI);
          c.save(); c.beginPath(); c.rect(x, y0 + cellH / 2, cw, (cellH / 2) * sy); c.fillStyle = MX('#2c2c36', P.flap, p); c.fill(); c.restore();
          glyphHalf(c, next, x, y0, cw, cellH, 1, col, font, sy);
        }
      }
    }
    if (!anim && ch !== ' ') {
      c.fillStyle = col; c.font = font; c.textAlign = 'center'; c.textBaseline = 'middle';
      c.fillText(ch, x + cw / 2, y0 + cellH / 2 + cellH * 0.04);
    }
    // the hinge line + side pins
    c.fillStyle = 'rgba(0,0,0,0.85)'; c.fillRect(x, y0 + cellH / 2 - 0.006, cw, 0.012);
    c.fillStyle = '#5a5a66'; c.fillRect(x - 0.008, y0 + cellH / 2 - 0.02, 0.016, 0.04); c.fillRect(x + cw - 0.008, y0 + cellH / 2 - 0.02, 0.016, 0.04);
  }
  // one soft additive glow over the digits (cheap: a few blobs, not one per glyph)
  for (let i = 0; i < n; i += 2) {
    if (S.target[i] === ' ' && (i + 1 >= n || S.target[i + 1] === ' ')) continue;
    glowU(c, x0 + (i + 1) * cellW, 0, cellW * 1.3, glowCol, 0.22);
  }
  // the hourglass flap
  if (hgVis > 0.01) {
    const hx = x0 + n * cellW + 0.04, hw = hgW;
    c.save(); c.translate(hx + hw / 2, 0); c.scale(1, hgVis); c.translate(-(hx + hw / 2), 0);
    flapTile(c, hx, y0, hw, cellH, wood);
    const u = frac(t / 2.4), flipping = u > 0.88, rot = flipping ? ((u - 0.88) / 0.12) * PI : 0;
    c.save(); c.translate(hx + hw / 2, 0); c.rotate(rot);
    const gw = Math.min(hw * 0.32, 0.12), gh = 0.2;
    c.strokeStyle = P.gold; c.lineWidth = 0.025;
    c.beginPath(); c.moveTo(-gw, -gh); c.lineTo(gw, -gh); c.moveTo(-gw, gh); c.lineTo(gw, gh); c.stroke();
    c.beginPath(); c.moveTo(-gw * 0.8, -gh); c.quadraticCurveTo(-gw * 0.8, -0.03, 0, 0); c.quadraticCurveTo(gw * 0.8, -0.03, gw * 0.8, -gh);
    c.moveTo(-gw * 0.8, gh); c.quadraticCurveTo(-gw * 0.8, 0.03, 0, 0); c.quadraticCurveTo(gw * 0.8, 0.03, gw * 0.8, gh); c.strokeStyle = P.goldHot; c.lineWidth = 0.014; c.stroke();
    const sand = flipping ? 0 : u / 0.88;
    c.fillStyle = col;
    c.beginPath(); c.moveTo(-gw * 0.6 * (1 - sand), -gh * (1 - sand) * 0.9 - 0.02); c.lineTo(gw * 0.6 * (1 - sand), -gh * (1 - sand) * 0.9 - 0.02); c.lineTo(0, -0.01); c.closePath(); c.fill();
    c.beginPath(); c.moveTo(-gw * 0.7, gh - 0.01); c.lineTo(gw * 0.7, gh - 0.01); c.lineTo(0, gh - 0.01 - gh * 0.75 * sand); c.closePath(); c.fill();
    if (!flipping) { c.fillRect(-0.004, -0.01, 0.008, gh * 0.9); }
    c.restore();
    glowU(c, hx + hw / 2, 0, hw * 0.9, glowCol, 0.25);
    c.restore();
  }
  // glass sheen over the whole window
  c.fillStyle = 'rgba(255,255,255,0.06)'; c.beginPath(); c.moveTo(-W / 2 + 0.12, -0.33); c.lineTo(-W / 2 + 0.6, -0.33); c.lineTo(-W / 2 + 0.3, 0.33); c.lineTo(-W / 2 + 0.12, 0.33); c.closePath(); c.fill();
  rs(ctx);
});
//>>SIGN

//<<BELL
// ================================================================================================ THE GOLDEN BELL
// An ornate cathedral bell in a riveted iron belfry (anchor = bottom-centre of the frame, 1.1 tall). swing 0..1 = amplitude;
// shock 0..1 = the shockwave rings travelling out (drive it 0 -> 1 after a ring). The clapper lags the bell.
function bellBody(c) {
  // bell profile in its own frame: pivot (yoke) at (0,0), lip at y = 0.62
  c.beginPath();
  c.moveTo(-0.1, 0.06); c.bezierCurveTo(-0.17, 0.07, -0.19, 0.18, -0.19, 0.3);
  c.bezierCurveTo(-0.19, 0.45, -0.25, 0.55, -0.33, 0.6); c.quadraticCurveTo(-0.34, 0.66, -0.28, 0.665);
  c.lineTo(0.28, 0.665); c.quadraticCurveTo(0.34, 0.66, 0.33, 0.6);
  c.bezierCurveTo(0.25, 0.55, 0.19, 0.45, 0.19, 0.3); c.bezierCurveTo(0.19, 0.18, 0.17, 0.07, 0.1, 0.06); c.closePath();
}
function bellSprite(c) {
  bellBody(c);
  const g = c.createLinearGradient(-0.33, 0, 0.33, 0);
  g.addColorStop(0, '#8a5a0a'); g.addColorStop(0.18, P.goldHot); g.addColorStop(0.42, P.gold); g.addColorStop(0.75, P.goldDeep); g.addColorStop(1, '#5a3a06');
  c.fillStyle = g; c.fill();
  ink(c, LINE.ink); c.stroke();
  // decorative bands, a frieze of beads and a sunburst emblem
  c.save(); bellBody(c); c.clip();
  for (const [yy, hh] of [[0.12, 0.03], [0.5, 0.025], [0.585, 0.045]]) { c.fillStyle = RA(P.goldDark, 0.85); c.fillRect(-0.4, yy, 0.8, hh); c.fillStyle = RA('#fff6cf', 0.6); c.fillRect(-0.4, yy, 0.8, hh * 0.3); }
  c.fillStyle = RA(P.goldDark, 0.8); for (let i = -4; i <= 4; i++) { c.beginPath(); c.arc(i * 0.045, 0.2, 0.012, 0, TAU); c.fill(); }
  c.translate(0, 0.36);
  for (let i = 0; i < 12; i++) { const a = (i / 12) * TAU; c.beginPath(); c.moveTo(0, 0); c.lineTo(Math.cos(a - 0.12) * 0.1, Math.sin(a - 0.12) * 0.1); c.lineTo(Math.cos(a + 0.12) * 0.1, Math.sin(a + 0.12) * 0.1); c.closePath(); c.fillStyle = i % 2 ? RA(P.goldDark, 0.7) : RA('#fff6cf', 0.55); c.fill(); }
  c.beginPath(); c.arc(0, 0, 0.045, 0, TAU); c.fillStyle = P.goldDeep; c.fill(); c.strokeStyle = P.ink; c.lineWidth = LINE.hair * 1.5; c.stroke();
  c.restore();
  // highlight streak
  c.strokeStyle = RA('#ffffff', 0.55); c.lineWidth = 0.03; c.beginPath(); c.moveTo(-0.12, 0.12); c.bezierCurveTo(-0.15, 0.3, -0.17, 0.42, -0.24, 0.56); c.stroke();
  // crown loops
  c.beginPath(); c.arc(0, 0.035, 0.05, PI, 0); ink(c, 0.05); c.stroke(); c.strokeStyle = P.goldDeep; c.lineWidth = 0.025; c.stroke();
}
function belfrySprite(c) {
  // two riveted iron posts, braces, a crossbeam with a gold deco cap and a finial (anchor = bottom-centre)
  for (const sx of [-1, 1]) {
    c.beginPath(); c.moveTo(sx * 0.4, 0); c.lineTo(sx * 0.33, -1.0); c.lineTo(sx * 0.27, -1.0); c.lineTo(sx * 0.32, 0); c.closePath(); shadeU(c, sx > 0 ? 0.27 : -0.4, -1, 0.13, 1, P.iron); ink(c); c.stroke();
    for (let i = 0; i < 5; i++) rivetU(c, sx * (0.36 - i * 0.013), -0.1 - i * 0.2, 0.012);
    c.strokeStyle = P.ink; c.lineWidth = 0.04; c.beginPath(); c.moveTo(sx * 0.35, -0.15); c.lineTo(sx * 0.12, -0.02); c.stroke(); c.strokeStyle = P.ironLight; c.lineWidth = 0.022; c.stroke();
  }
  c.beginPath(); c.rect(-0.46, -0.04, 0.92, 0.06); fo(c, P.ironDark, LINE.inkThin);
  c.beginPath(); c.rect(-0.44, -1.07, 0.88, 0.09); shadeU(c, -0.44, -1.07, 0.88, 0.09, P.iron); ink(c); c.stroke();
  c.beginPath(); c.moveTo(-0.38, -1.07); c.lineTo(-0.28, -1.16); c.lineTo(0.28, -1.16); c.lineTo(0.38, -1.07); c.closePath(); fo(c, P.gold, LINE.inkThin);
  c.beginPath(); c.moveTo(-0.06, -1.16); c.lineTo(0, -1.26); c.lineTo(0.06, -1.16); c.closePath(); fo(c, P.goldDeep, LINE.inkThin);
  for (let i = 0; i < 7; i++) rivetU(c, -0.36 + i * 0.12, -1.025, 0.012);
}
export const drawBell = guard('drawBell', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const sw = clamp(num(st.swing, 0), 0, 1), shock = clamp(num(st.shock, 0), 0, 1);
  beginU(ctx, x, y, s, 1);
  ctx.scale(0.875, 0.875);   // the whole belfry is 1.1 tall
  const c = ctx;
  sprite(c, 'belfry', [-0.5, -1.3, 1.0, 1.36], belfrySprite);
  const ang = sw * 0.55 * Math.sin(t * 2.7);
  const clap = sw * 0.55 * Math.sin(t * 2.7 - 0.9) * 1.25;
  const py = -0.94;
  // the yoke and its wheel
  c.save(); c.translate(0, py); c.rotate(ang);
  c.beginPath(); c.rect(-0.2, -0.05, 0.4, 0.06); fo(c, P.ironDark, LINE.inkThin);
  c.beginPath(); c.arc(0, -0.02, 0.06, 0, TAU); fo(c, P.goldDeep, LINE.inkThin);
  // clapper (behind the lip edge)
  c.save(); c.translate(0, 0.08); c.rotate(clap - ang);
  c.strokeStyle = P.ink; c.lineWidth = 0.03; c.beginPath(); c.moveTo(0, 0); c.lineTo(0, 0.56); c.stroke(); c.strokeStyle = P.ironLight; c.lineWidth = 0.015; c.stroke();
  c.beginPath(); c.arc(0, 0.6, 0.055, 0, TAU); fo(c, P.ironDark, LINE.inkThin);
  c.restore();
  c.translate(0, 0.0);
  sprite(c, 'bellbody', [-0.38, -0.04, 0.76, 0.75], bellSprite);
  c.restore();
  // the rope looping from the wheel down the post
  c.strokeStyle = P.ink; c.lineWidth = 0.03; c.beginPath(); c.moveTo(0.05 + ang * 0.2, py + 0.02); c.quadraticCurveTo(0.42, -0.6, 0.42 + Math.sin(t * 1.3) * 0.02, -0.02); c.stroke();
  c.strokeStyle = '#c9a26a'; c.lineWidth = 0.016; c.stroke();
  // motion lines while ringing
  if (sw > 0.25) {
    c.strokeStyle = RA(P.goldHot, sw * 0.8); c.lineWidth = 0.025;
    for (const sx of [-1, 1]) for (let i = 0; i < 3; i++) { const r = 0.45 + i * 0.08; c.beginPath(); c.arc(0, py + 0.35, r, sx > 0 ? -0.5 : PI - 0.5 + 0, sx > 0 ? 0.5 : PI + 0.5); c.stroke(); }
  }
  // shockwave rings + a bloom
  if (shock > 0 && shock < 1) {
    const cy = py + 0.36;
    glowU(c, 0, cy, 0.5 + shock * 1.2, P.goldHot, 0.45 * (1 - shock));
    for (let i = 0; i < 3; i++) {
      const k = clamp(shock * 1.25 - i * 0.12, 0, 1);
      if (k <= 0 || k >= 1) continue;
      c.strokeStyle = RA(i === 1 ? '#ffffff' : P.gold, (1 - k) * 0.9); c.lineWidth = 0.05 * (1 - k) + 0.01;
      c.beginPath(); c.ellipse(0, cy, 0.4 + k * 2.4, (0.4 + k * 2.4) * 0.75, 0, 0, TAU); c.stroke();
    }
  }
  rs(ctx);
});
//>>BELL

//<<BUYER
// ================================================================================================ THE BUYER (tycoon in a steam zeppelin)
// Anchor = the ground point under the basket. The gondola's keel floats 2.6 above it, the envelope (2.4 wide) rides above him.
// Local frame looks right; the default facing is -1 (he looks left, down the street at the Runner).
export const BUYER_PTS = { tagX: 0, tagY: 0, tagR: 0, gunX: 0, gunY: 0, loupeX: 0, loupeY: 0, mouthX: 0, mouthY: 0, holeX: 0, holeY: 0, holeAng: 0, holeF: 1 };
const BY = { keel: -2.6, rail: -3.16, envY: -4.5, envRX: 1.2, envRY: 0.5 };
function envelopePath(c) {
  c.beginPath();
  c.moveTo(-1.18, BY.envY);
  c.bezierCurveTo(-1.18, BY.envY - 0.42, -0.6, BY.envY - 0.52, 0.1, BY.envY - 0.52);
  c.bezierCurveTo(0.8, BY.envY - 0.52, 1.24, BY.envY - 0.3, 1.24, BY.envY);
  c.bezierCurveTo(1.24, BY.envY + 0.3, 0.8, BY.envY + 0.5, 0.1, BY.envY + 0.5);
  c.bezierCurveTo(-0.6, BY.envY + 0.5, -1.18, BY.envY + 0.4, -1.18, BY.envY); c.closePath();
}
function envelopeSprite(c) {
  // tail fins (behind)
  for (const [fy, col] of [[-0.42, P.emerald], [0.42, P.crimson]]) {
    c.beginPath(); c.moveTo(-0.85, BY.envY + fy * 0.4); c.lineTo(-1.42, BY.envY + fy * 1.05); c.lineTo(-1.5, BY.envY + fy * 0.95); c.lineTo(-1.32, BY.envY + fy * 0.2); c.closePath();
    shadeU(c, -1.5, BY.envY - 0.5, 0.7, 1, col); ink(c); c.stroke();
    c.strokeStyle = P.gold; c.lineWidth = 0.02; c.beginPath(); c.moveTo(-0.95, BY.envY + fy * 0.42); c.lineTo(-1.4, BY.envY + fy * 0.95); c.stroke();
  }
  // gores: gold and ivory stripes, clipped to the hull
  envelopePath(c); c.fillStyle = P.gold; c.fill();
  c.save(); envelopePath(c); c.clip();
  for (let i = -6; i <= 6; i++) {
    if (i % 2) continue;
    const x0 = i * 0.2;
    c.beginPath(); c.moveTo(x0 - 0.1, BY.envY - 0.6); c.quadraticCurveTo(x0 * 1.08 - 0.1, BY.envY, x0 - 0.1, BY.envY + 0.6); c.lineTo(x0 + 0.1, BY.envY + 0.6); c.quadraticCurveTo(x0 * 1.08 + 0.1, BY.envY, x0 + 0.1, BY.envY - 0.6); c.closePath();
    c.fillStyle = '#fbf3da'; c.fill();
  }
  // the recipe: light band top-left, shadow band bottom-right
  const g = c.createLinearGradient(0, BY.envY - 0.55, 0, BY.envY + 0.55);
  g.addColorStop(0, 'rgba(255,255,255,0.45)'); g.addColorStop(0.35, 'rgba(255,255,255,0)'); g.addColorStop(0.62, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(60,30,0,0.45)');
  c.fillStyle = g; c.fillRect(-1.3, BY.envY - 0.6, 2.6, 1.2);
  // seams
  c.strokeStyle = RA(P.goldDark, 0.6); c.lineWidth = 0.01;
  for (let i = -6; i <= 6; i++) { const x0 = i * 0.2 + 0.1; c.beginPath(); c.moveTo(x0, BY.envY - 0.6); c.quadraticCurveTo(x0 * 1.08, BY.envY, x0, BY.envY + 0.6); c.stroke(); }
  // the belly band with rivets and a name plate
  c.fillStyle = P.goldDeep; c.fillRect(-1.3, BY.envY + 0.05, 2.6, 0.07); c.fillStyle = RA('#fff6cf', 0.7); c.fillRect(-1.3, BY.envY + 0.05, 2.6, 0.015);
  c.restore();
  for (let xx = -0.95; xx < 1.05; xx += 0.13) rivetU(c, xx, BY.envY + 0.085, 0.011);
  envelopePath(c); ink(c, LINE.ink); c.stroke();
  // gold nose cone with a deco ornament
  c.beginPath(); c.moveTo(1.12, BY.envY - 0.24); c.quadraticCurveTo(1.34, BY.envY - 0.12, 1.36, BY.envY); c.quadraticCurveTo(1.34, BY.envY + 0.12, 1.12, BY.envY + 0.24); c.closePath();
  shadeU(c, 1.1, BY.envY - 0.25, 0.27, 0.5, P.goldHot); ink(c); c.stroke();
  c.beginPath(); c.arc(1.36, BY.envY, 0.035, 0, TAU); fo(c, P.crimson, LINE.inkThin);
  // a side medallion: a dollar sun
  c.beginPath(); c.arc(0.35, BY.envY - 0.16, 0.13, 0, TAU); fo(c, P.emerald, LINE.inkThin);
  c.beginPath(); c.arc(0.35, BY.envY - 0.16, 0.1, 0, TAU); ink(c, 0.012, P.gold); c.stroke();
}
function gondolaSprite(c) {
  // the hull: a gilded boat with a red velvet band, portholes and a brass rail
  const top = BY.rail, bot = BY.keel;
  c.beginPath(); c.moveTo(-0.72, top); c.lineTo(0.7, top); c.quadraticCurveTo(0.86, top, 0.84, top + 0.08);
  c.quadraticCurveTo(0.7, bot - 0.02, 0.2, bot); c.lineTo(-0.3, bot); c.quadraticCurveTo(-0.72, bot - 0.06, -0.78, top + 0.12); c.quadraticCurveTo(-0.8, top, -0.72, top); c.closePath();
  shadeU(c, -0.8, top, 1.66, bot - top, P.gold); ink(c); c.stroke();
  c.save(); c.clip();
  c.fillStyle = '#9c1c2a'; c.fillRect(-0.9, top + 0.14, 1.9, 0.2);
  c.fillStyle = RA('#ffffff', 0.18); c.fillRect(-0.9, top + 0.14, 1.9, 0.04);
  c.fillStyle = P.goldDeep; c.fillRect(-0.9, top + 0.12, 1.9, 0.025); c.fillRect(-0.9, top + 0.335, 1.9, 0.025);
  c.restore();
  for (let i = 0; i < 4; i++) {
    const px = -0.48 + i * 0.32;
    c.beginPath(); c.arc(px, top + 0.24, 0.07, 0, TAU); fo(c, P.goldDeep, LINE.inkThin);
    c.beginPath(); c.arc(px, top + 0.24, 0.05, 0, TAU); c.fillStyle = '#ffe9a8'; c.fill();
    c.fillStyle = RA('#ffffff', 0.7); c.beginPath(); c.arc(px - 0.015, top + 0.225, 0.015, 0, TAU); c.fill();
  }
  // scrollwork on the keel
  c.strokeStyle = P.goldDark; c.lineWidth = 0.014;
  c.beginPath(); c.moveTo(-0.5, bot - 0.08); c.bezierCurveTo(-0.3, bot - 0.16, -0.1, bot - 0.02, 0.1, bot - 0.1); c.bezierCurveTo(0.3, bot - 0.17, 0.45, bot - 0.06, 0.6, bot - 0.12); c.stroke();
  // the rail
  c.beginPath(); rrP(c, -0.78, top - 0.05, 1.62, 0.05, 0.02); fo(c, P.goldHot, LINE.inkThin);
  // the boiler at the stern with a chimney
  c.beginPath(); rrP(c, -0.86, top - 0.36, 0.26, 0.38, 0.06); shadeU(c, -0.86, top - 0.36, 0.26, 0.38, P.brass); ink(c); c.stroke();
  c.strokeStyle = P.brassDark; c.lineWidth = 0.014; for (let i = 0; i < 3; i++) { c.beginPath(); c.moveTo(-0.86, top - 0.28 + i * 0.1); c.lineTo(-0.6, top - 0.28 + i * 0.1); c.stroke(); }
  c.beginPath(); c.rect(-0.79, top - 0.55, 0.09, 0.2); fo(c, P.ironDark, LINE.inkThin);
  c.beginPath(); c.rect(-0.81, top - 0.58, 0.13, 0.04); fo(c, P.gold, LINE.inkThin);
  c.beginPath(); c.arc(-0.73, top - 0.18, 0.05, 0, TAU); fo(c, '#fff8e8', LINE.hair * 1.5);
  c.strokeStyle = P.ink; c.lineWidth = LINE.hair; c.beginPath(); c.moveTo(-0.73, top - 0.18); c.lineTo(-0.705, top - 0.205); c.stroke();
  // lantern brackets at the bow
  c.strokeStyle = P.ink; c.lineWidth = 0.025; c.beginPath(); c.moveTo(0.8, top + 0.02); c.lineTo(0.95, top - 0.06); c.stroke();
}
function tycoon(c, mood, t, champagne, K) {
  const sk = '#f2b48a';
  const laugh = mood === 'laugh';
  const shake = laugh ? Math.abs(Math.sin(t * 16)) * 0.02 : 0;
  const lean = mood === 'inspect' ? 0.28 : mood === 'pay' ? 0.12 : 0;
  c.save(); c.translate(0.05, BY.rail + 0.05 - shake); c.scale(1.25, 1.25); c.rotate(lean);
  // body: emerald velvet coat, gold waistcoat, white shirt, ermine collar
  c.beginPath(); c.moveTo(-0.3, 0.1); c.quadraticCurveTo(-0.36, -0.2, -0.22, -0.4); c.quadraticCurveTo(0, -0.47, 0.22, -0.4); c.quadraticCurveTo(0.38, -0.2, 0.32, 0.1); c.closePath();
  shadeU(c, -0.36, -0.47, 0.74, 0.57, P.emerald); ink(c); c.stroke();
  c.beginPath(); c.moveTo(-0.1, -0.38); c.quadraticCurveTo(0.0, -0.2, 0.0, 0.1); c.lineTo(0.22, 0.1); c.quadraticCurveTo(0.26, -0.2, 0.14, -0.38); c.closePath(); shadeU(c, -0.1, -0.38, 0.36, 0.48, P.gold); ink(c, LINE.inkThin); c.stroke();
  for (let i = 0; i < 3; i++) { c.beginPath(); c.arc(0.11, -0.22 + i * 0.09, 0.016, 0, TAU); fo(c, P.goldDeep, LINE.hair * 1.5); }
  c.strokeStyle = P.goldHot; c.lineWidth = 0.012; c.beginPath(); c.moveTo(0.12, -0.12); c.quadraticCurveTo(0.2, -0.06, 0.26, -0.11); c.stroke();
  // ermine collar
  c.beginPath(); c.ellipse(-0.02, -0.4, 0.27, 0.075, 0, 0, TAU); fo(c, '#fbfbf6', LINE.inkThin);
  c.fillStyle = P.ink; for (let i = 0; i < 5; i++) { c.beginPath(); c.ellipse(-0.2 + i * 0.09, -0.4 + (i % 2 ? 0.02 : -0.01), 0.008, 0.016, 0, 0, TAU); c.fill(); }
  // bow tie
  c.beginPath(); c.moveTo(0.06, -0.44); c.lineTo(0.0, -0.47); c.lineTo(0.0, -0.41); c.closePath(); c.moveTo(0.06, -0.44); c.lineTo(0.12, -0.47); c.lineTo(0.12, -0.41); c.closePath(); fo(c, P.crimson, LINE.hair * 1.5);
  // the far arm (behind the head line): tap / wave / point / loupe / gun support
  tycoonFarArm(c, mood, t, sk, K);
  // head
  let ht = 0, hx = 0.04, hy = -0.66;
  if (laugh) { ht = -0.35; hy -= 0.02; }
  if (mood === 'shake_head') ht = Math.sin(t * 11) * 0.22;
  if (mood === 'wave_off') ht = -0.28;
  if (mood === 'inspect') ht = 0.15;
  c.save(); c.translate(hx, hy); c.rotate(ht);
  tycoonHead(c, mood, t, sk, K);
  c.restore();
  c.restore();
  return lean;
}
function tycoonHead(c, mood, t, sk, K) {
  const r = 0.2;
  // jowls + double chin
  c.beginPath(); c.moveTo(-0.17, -0.1); c.quadraticCurveTo(-0.23, 0.1, -0.12, 0.2); c.quadraticCurveTo(0.03, 0.27, 0.18, 0.18); c.quadraticCurveTo(0.25, 0.06, 0.18, -0.12); c.quadraticCurveTo(0, -0.24, -0.17, -0.1); c.closePath();
  c.fillStyle = sk; c.fill();
  c.fillStyle = '#d98f66'; c.beginPath(); c.moveTo(0.18, -0.02); c.quadraticCurveTo(0.25, 0.06, 0.18, 0.18); c.quadraticCurveTo(0.08, 0.25, 0.0, 0.24); c.quadraticCurveTo(0.14, 0.15, 0.18, -0.02); c.fill();
  c.beginPath(); c.moveTo(-0.17, -0.1); c.quadraticCurveTo(-0.23, 0.1, -0.12, 0.2); c.quadraticCurveTo(0.03, 0.27, 0.18, 0.18); c.quadraticCurveTo(0.25, 0.06, 0.18, -0.12); c.quadraticCurveTo(0, -0.24, -0.17, -0.1); c.closePath(); ink(c); c.stroke();
  c.strokeStyle = RA(P.ink, 0.5); c.lineWidth = LINE.hair; c.beginPath(); c.arc(0.03, 0.17, 0.09, 0.4, 2.6); c.stroke();
  // ear
  c.beginPath(); c.ellipse(-0.16, 0.0, 0.04, 0.055, 0, 0, TAU); fo(c, sk, LINE.inkThin);
  // cheeks
  c.fillStyle = RA(P.blush, 0.6); c.beginPath(); c.ellipse(0.08, 0.06, 0.05, 0.03, 0, 0, TAU); c.fill();
  // eyes
  const closed = mood === 'laugh' || mood === 'wave_off' || (blinkAt(t, 0.51) && mood !== 'inspect');
  if (closed) {
    c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin;
    c.beginPath(); c.arc(0.05, -0.02, 0.025, PI * 1.1, PI * 1.9); c.stroke(); c.beginPath(); c.arc(0.13, -0.025, 0.02, PI * 1.1, PI * 1.9); c.stroke();
  } else if (mood !== 'inspect') {
    const half = mood === 'wait' || mood === 'tap';
    c.beginPath(); c.ellipse(0.05, -0.02, 0.026, 0.03, 0, 0, TAU); fo(c, '#fff', LINE.hair * 1.5);
    c.beginPath(); c.ellipse(0.135, -0.025, 0.02, 0.026, 0, 0, TAU); fo(c, '#fff', LINE.hair * 1.5);
    c.fillStyle = P.ink; c.beginPath(); c.arc(0.058, -0.018, 0.012, 0, TAU); c.arc(0.14, -0.022, 0.01, 0, TAU); c.fill();
    if (half) { c.fillStyle = sk; c.fillRect(0.02, -0.055, 0.065, 0.03); c.fillRect(0.11, -0.055, 0.05, 0.028); c.strokeStyle = P.ink; c.lineWidth = LINE.hair * 1.5; c.beginPath(); c.moveTo(0.022, -0.025); c.lineTo(0.08, -0.025); c.moveTo(0.115, -0.028); c.lineTo(0.155, -0.028); c.stroke(); }
  }
  // brows (white, bushy)
  c.strokeStyle = '#f3f3f3'; c.lineWidth = 0.026;
  const bt = mood === 'shake_head' || mood === 'tap' ? 0.02 : mood === 'wave_off' ? -0.02 : 0;
  c.beginPath(); c.moveTo(0.015, -0.075 + bt); c.lineTo(0.085, -0.08 - bt); c.moveTo(0.11, -0.082 - bt); c.lineTo(0.165, -0.075 + bt); c.stroke();
  c.strokeStyle = P.ink; c.lineWidth = LINE.hair; c.stroke();
  // nose
  c.beginPath(); c.ellipse(0.2, 0.035, 0.045, 0.04, 0.2, 0, TAU); fo(c, '#ec9a78', LINE.inkThin);
  c.fillStyle = RA('#ffffff', 0.5); c.beginPath(); c.arc(0.19, 0.022, 0.011, 0, TAU); c.fill();
  // mouth under the moustache
  if (mood === 'laugh') {
    const o = 0.05 + Math.abs(Math.sin(t * 16)) * 0.02;
    c.beginPath(); c.ellipse(0.12, 0.15, 0.06, o, 0, 0, TAU); fo(c, '#5a1414', LINE.inkThin);
    c.fillStyle = P.gold; c.fillRect(0.11, 0.15 - o + 0.004, 0.025, 0.02); c.fillStyle = '#fff'; c.fillRect(0.075, 0.15 - o + 0.004, 0.033, 0.02);
  } else if (mood === 'shake_head' || mood === 'tap') {
    c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin; c.beginPath(); c.arc(0.12, 0.19, 0.04, PI * 1.25, PI * 1.75); c.stroke();
  } else {
    c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin; c.beginPath(); c.arc(0.12, 0.1, 0.045, 0.5, 2.0); c.stroke();
  }
  // walrus moustache
  c.beginPath(); c.moveTo(0.05, 0.08); c.bezierCurveTo(0.02, 0.15, 0.1, 0.16, 0.14, 0.12); c.bezierCurveTo(0.2, 0.17, 0.27, 0.14, 0.25, 0.07); c.bezierCurveTo(0.2, 0.06, 0.1, 0.05, 0.05, 0.08); c.closePath();
  fo(c, '#f6f6f2', LINE.inkThin);
  // monocle (on the far eye) with its chain; it pops out when he laughs
  if (mood !== 'laugh' && mood !== 'inspect') {
    c.beginPath(); c.arc(0.135, -0.025, 0.038, 0, TAU); ink(c, 0.03); c.stroke(); ink(c, 0.016, P.gold); c.stroke();
    c.fillStyle = RA('#ffffff', 0.3); c.beginPath(); c.arc(0.125, -0.035, 0.012, 0, TAU); c.fill();
    c.strokeStyle = P.gold; c.lineWidth = 0.008; c.beginPath(); c.moveTo(0.17, -0.01); c.quadraticCurveTo(0.2, 0.15, 0.1, 0.3); c.stroke();
  } else if (mood === 'laugh') {
    const sw = Math.sin(t * 9) * 0.05;
    c.strokeStyle = P.gold; c.lineWidth = 0.008; c.beginPath(); c.moveTo(0.17, 0.0); c.quadraticCurveTo(0.22, 0.12, 0.2 + sw, 0.22); c.stroke();
    c.beginPath(); c.arc(0.2 + sw, 0.25, 0.034, 0, TAU); ink(c, 0.026); c.stroke(); ink(c, 0.014, P.gold); c.stroke();
  }
  // top hat
  c.save(); c.rotate(-0.1); c.translate(-0.01, -0.13);
  c.beginPath(); c.ellipse(0, 0, 0.24, 0.045, 0, 0, TAU); fo(c, '#17171f');
  c.beginPath(); c.moveTo(-0.15, -0.01); c.lineTo(-0.16, -0.32); c.quadraticCurveTo(0, -0.345, 0.16, -0.32); c.lineTo(0.15, -0.01); c.quadraticCurveTo(0, 0.01, -0.15, -0.01); c.closePath();
  shadeU(c, -0.16, -0.34, 0.32, 0.34, '#1d1d27'); ink(c); c.stroke();
  c.beginPath(); c.moveTo(-0.152, -0.04); c.lineTo(-0.154, -0.1); c.quadraticCurveTo(0, -0.09, 0.154, -0.1); c.lineTo(0.152, -0.04); c.quadraticCurveTo(0, -0.03, -0.152, -0.04); c.closePath(); fo(c, P.gold, LINE.inkThin);
  c.beginPath(); c.moveTo(0.09, -0.1); c.lineTo(0.12, -0.065); c.lineTo(0.09, -0.03); c.lineTo(0.06, -0.065); c.closePath(); fo(c, '#dff7ff', LINE.hair * 1.5);
  c.fillStyle = 'rgba(255,255,255,0.22)'; c.fillRect(-0.1, -0.3, 0.035, 0.19);
  c.beginPath(); c.ellipse(0, -0.322, 0.16, 0.03, 0, 0, TAU); fo(c, '#2a2a36', LINE.inkThin);
  c.restore();
  if (mood === 'inspect') {
    // the jeweller's loupe screwed into the near eye: a huge magnified eye
    c.beginPath(); c.moveTo(0.04, -0.03); c.lineTo(0.17, -0.03); c.lineTo(0.2, 0.0); c.lineTo(0.03, 0.0); c.closePath(); fo(c, P.ink, LINE.hair);
    c.beginPath(); c.arc(0.1, -0.02, 0.075, 0, TAU); fo(c, P.goldDeep, LINE.inkThin);
    c.beginPath(); c.arc(0.1, -0.02, 0.058, 0, TAU); c.fillStyle = '#eaf6ff'; c.fill();
    c.beginPath(); c.arc(0.11, -0.02, 0.034, 0, TAU); c.fillStyle = '#3a6a8a'; c.fill();
    c.fillStyle = P.ink; c.beginPath(); c.arc(0.115, -0.02, 0.018, 0, TAU); c.fill();
    c.fillStyle = '#fff'; c.beginPath(); c.arc(0.1, -0.035, 0.009, 0, TAU); c.fill();
  }
}
function tycoonFarArm(c, mood, t, sk, K) {
  const a = [0, 0, 0, 0, 0, 0];
  const set = (x1, y1, x2, y2) => { a[0] = -0.22; a[1] = -0.36; a[2] = x1; a[3] = y1; a[4] = x2; a[5] = y2; };
  let handShape = 'fist';
  switch (mood) {
    case 'tap': { const tp = Math.abs(Math.sin(t * 9)) * 0.03; set(-0.3, -0.12, -0.1, 0.06 - tp); handShape = 'tap'; break; }
    case 'wave_off': { const w = Math.sin(t * 10) * 0.25; set(-0.36, -0.55, -0.32 + Math.sin(w) * 0.06, -0.78); handShape = 'wave'; break; }
    case 'shake_head': { const w = Math.sin(t * 12) * 0.04; set(-0.32, -0.55, -0.22 + w, -0.72); handShape = 'finger'; break; }
    case 'inspect': set(-0.15, -0.3, 0.05, -0.55); handShape = 'loupe'; break;
    case 'pay': set(-0.12, -0.15, 0.18, -0.14); break;
    default: set(-0.3, -0.12, -0.18, 0.06); break;
  }
  limb2(c, a, 0.1, DK(P.emerald, 0.15), DK(P.emerald, 0.15));
  c.beginPath(); c.arc(a[4], a[5], 0.05, 0, TAU); fo(c, sk, LINE.inkThin);
  c.fillStyle = P.gold; c.beginPath(); c.arc(a[4] + 0.02, a[5] - 0.02, 0.012, 0, TAU); c.fill();
  if (handShape === 'finger') { c.strokeStyle = P.ink; c.lineWidth = 0.035; c.beginPath(); c.moveTo(a[4], a[5] - 0.03); c.lineTo(a[4] + 0.01, a[5] - 0.11); c.stroke(); c.strokeStyle = sk; c.lineWidth = 0.018; c.stroke(); }
  if (handShape === 'wave') { c.strokeStyle = RA(P.ink, 0.5); c.lineWidth = 0.012; c.beginPath(); c.arc(a[4], a[5], 0.1, -2.4, -1.6); c.stroke(); c.beginPath(); c.arc(a[4], a[5], 0.14, -2.3, -1.7); c.stroke(); }
}
function flute(c, x, y, ang, fill, t, empty) {
  c.save(); c.translate(x, y); c.rotate(ang);
  // stem + foot
  c.strokeStyle = P.ink; c.lineWidth = 0.025; c.beginPath(); c.moveTo(0, 0.0); c.lineTo(0, 0.12); c.stroke(); c.strokeStyle = '#e8f6ff'; c.lineWidth = 0.012; c.stroke();
  c.beginPath(); c.ellipse(0, 0.125, 0.04, 0.012, 0, 0, TAU); fo(c, '#e8f6ff', LINE.hair * 1.5);
  // bowl
  c.beginPath(); c.moveTo(-0.035, -0.2); c.lineTo(0.035, -0.2); c.quadraticCurveTo(0.03, -0.02, 0, 0.0); c.quadraticCurveTo(-0.03, -0.02, -0.035, -0.2); c.closePath();
  c.fillStyle = 'rgba(220,240,255,0.35)'; c.fill();
  if (!empty && fill > 0.02) {
    const ly = lerp(-0.005, -0.18, clamp(fill, 0, 1));
    c.save(); c.clip(); c.fillStyle = '#f6d36b'; c.fillRect(-0.05, ly, 0.1, 0.3);
    c.fillStyle = '#fff6cf'; for (let i = 0; i < 4; i++) { const u = frac(t * 0.8 + i / 4); const by = lerp(-0.01, ly, u); c.beginPath(); c.arc(-0.012 + (i % 2) * 0.022, by, 0.006, 0, TAU); c.fill(); }
    c.restore();
  }
  c.beginPath(); c.moveTo(-0.035, -0.2); c.lineTo(0.035, -0.2); c.quadraticCurveTo(0.03, -0.02, 0, 0.0); c.quadraticCurveTo(-0.03, -0.02, -0.035, -0.2); c.closePath();
  ink(c, LINE.inkThin); c.stroke();
  c.strokeStyle = 'rgba(255,255,255,0.8)'; c.lineWidth = 0.008; c.beginPath(); c.moveTo(-0.02, -0.18); c.lineTo(-0.012, -0.05); c.stroke();
  c.restore();
}
function blunderbuss(c, x, y, ang, t, fire) {
  c.save(); c.translate(x, y); c.rotate(ang);
  c.beginPath(); c.moveTo(-0.22, -0.03); c.lineTo(-0.05, -0.04); c.lineTo(-0.05, 0.04); c.lineTo(-0.25, 0.06); c.closePath(); fo(c, '#7a4a22', LINE.inkThin);
  c.beginPath(); c.moveTo(-0.06, -0.035); c.lineTo(0.3, -0.03); c.lineTo(0.42, -0.08); c.lineTo(0.43, 0.08); c.lineTo(0.3, 0.03); c.lineTo(-0.06, 0.035); c.closePath(); shadeU(c, -0.06, -0.08, 0.5, 0.16, P.gold); ink(c, LINE.inkThin); c.stroke();
  c.fillStyle = P.goldDark; c.fillRect(0.05, -0.035, 0.02, 0.07); c.fillRect(0.2, -0.032, 0.02, 0.064);
  c.beginPath(); c.ellipse(0.425, 0, 0.018, 0.08, 0, 0, TAU); fo(c, '#3a2a10', LINE.hair * 1.5);
  if (fire > 0.02) {
    glowU(c, 0.5, 0, 0.3 * fire + 0.08, P.goldHot, fire);
    c.fillStyle = RA('#fff3b0', fire); c.beginPath();
    for (let i = 0; i < 12; i++) { const a = (i / 12) * TAU, rr = (i % 2 ? 0.05 : 0.17) * (0.5 + fire * 0.7); c.lineTo(0.5 + Math.cos(a) * rr * 1.3, Math.sin(a) * rr); }
    c.closePath(); c.fill();
  }
  c.restore();
}
// the Buyer's price tag: the second of the two allowed numbers, so it is big (0.9 x 0.42 units, digits 0.24 tall - a quarter of the
// roof sign's) and inked; main.js redraws it in the lit layer (drawBuyerTag) so the storm, night and dead-market grades never bury it
const TAG_W = 0.9, TAG_H = 0.42;
function priceTag(c, x, y, ang, text) {
  c.save(); c.translate(x, y); c.rotate(ang);
  // string from the hull to the tag hole is drawn by the caller; the tag hangs from its hole at (-w/2 + 0.08, 0.08)
  const w = TAG_W, h = TAG_H;
  c.beginPath(); c.moveTo(-w / 2 + 0.09, 0.02); c.lineTo(w / 2, 0.02); c.lineTo(w / 2, 0.02 + h); c.lineTo(-w / 2, 0.02 + h); c.lineTo(-w / 2, 0.11); c.closePath();
  shadeU(c, -w / 2, 0.02, w, h, '#fbf1d6'); ink(c); c.stroke();
  c.beginPath(); c.moveTo(-w / 2 + 0.12, 0.055); c.lineTo(w / 2 - 0.035, 0.055); c.lineTo(w / 2 - 0.035, h - 0.015); c.lineTo(-w / 2 + 0.035, h - 0.015); c.lineTo(-w / 2 + 0.035, 0.13); c.closePath(); ink(c, 0.016, P.crimson); c.stroke();
  c.beginPath(); c.arc(-w / 2 + 0.08, 0.08, 0.032, 0, TAU); fo(c, P.goldDeep, LINE.hair * 1.5); c.beginPath(); c.arc(-w / 2 + 0.08, 0.08, 0.014, 0, TAU); c.fillStyle = P.ink; c.fill();
  textU(c, text, 0.05, 0.02 + h / 2 + 0.01, 0.24, { color: P.crimson, font: FONT.deco, maxW: w - 0.2, stroke: P.ink, strokeW: 0.022 });
  textU(c, text, 0.05, 0.02 + h / 2 + 0.01, 0.24, { color: P.crimson, font: FONT.deco, maxW: w - 0.2 });
  c.restore();
}
// the tag alone, at the hole drawBuyer reported (BUYER_PTS.holeX/holeY/holeAng/holeF): the lit-layer redraw of the Buyer's number
export const drawBuyerTag = guard('drawBuyerTag', function (ctx, x, y, s, st) {
  st = st || {};
  if (![x, y, s].every(isFinite) || st.tag == null || st.tag === '') return;
  const f = st.facing > 0 ? 1 : -1;
  beginU(ctx, x, y, s, f);
  ctx.rotate(num(st.ang, 0));                                   // the swing and the zeppelin's roll, as drawBuyer had them
  const hdx = -TAG_W / 2 + 0.08, hdy = 0.08;                    // the hole, relative to the tag's own origin
  if (st.glow > 0) glowU(ctx, 0.05 - hdx, 0.02 + TAG_H / 2 - hdy, 0.8, P.goldHot, 0.3 * clamp(st.glow, 0, 1));   // lit by the zeppelin's lamp
  priceTag(ctx, -hdx, -hdy, 0, String(st.tag));
  rs(ctx);
});
export const drawBuyer = guard('drawBuyer', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const f = st.facing > 0 ? 1 : -1;
  const mood = typeof st.mood === 'string' ? st.mood : 'wait';
  const champagne = clamp(num(st.champagne, 1), 0, 1);
  const tag = st.tag == null ? '' : String(st.tag);
  const bob = Math.sin(t * 1.1) * 0.05, tilt = Math.sin(t * 0.8) * 0.02;
  beginU(ctx, x, y, s, f);
  const c = ctx;
  // ground shadow
  c.fillStyle = 'rgba(0,0,0,0.16)'; c.beginPath(); c.ellipse(0, 0, 0.65 - bob, 0.07, 0, 0, TAU); c.fill();
  c.save(); c.translate(0, bob); c.rotate(tilt);
  // the price tag swinging on its string under the keel
  const swing = Math.sin(t * 1.6) * 0.16 + (mood === 'shake_head' ? Math.sin(t * 11) * 0.12 : 0);
  const ax = 0.08, ay = BY.keel - 0.01, L = 0.68;
  const hx = ax + Math.sin(swing) * L, hy = ay + Math.cos(swing) * L;
  const tagA = swing * 0.6, hdx = -TAG_W / 2 + 0.08, hdy = 0.08;
  const holeX = hx + hdx * Math.cos(tagA) - hdy * Math.sin(tagA), holeY = hy + hdx * Math.sin(tagA) + hdy * Math.cos(tagA);
  c.strokeStyle = P.ink; c.lineWidth = 0.022; c.beginPath(); c.moveTo(ax, ay); c.lineTo(holeX, holeY); c.stroke(); c.strokeStyle = '#d9c8a0'; c.lineWidth = 0.01; c.stroke();
  if (!st.noTag) priceTag(c, hx, hy, tagA, tag);
  // rigging lines from the gondola up to the envelope
  c.strokeStyle = RA(P.ink, 0.85); c.lineWidth = 0.014;
  for (const [x0, x1] of [[-0.7, -0.75], [-0.25, -0.3], [0.25, 0.3], [0.7, 0.75]]) { c.beginPath(); c.moveTo(x0, BY.rail - 0.03); c.lineTo(x1, BY.envY + 0.42); c.stroke(); }
  // the envelope + spinning propeller + steam
  sprite(c, 'zepEnv', [-1.56, BY.envY - 0.62, 3.0, 1.24], envelopeSprite);
  textU(c, '$', 0.35, BY.envY - 0.152, 0.15, { color: P.gold, font: FONT.deco });
  const pa = t * 22;
  c.save(); c.translate(-1.52, BY.envY);
  c.beginPath(); c.rect(-0.03, -0.03, 0.12, 0.06); fo(c, P.brassDark, LINE.hair * 1.5);
  c.fillStyle = 'rgba(230,230,230,0.25)'; c.beginPath(); c.ellipse(0, 0, 0.04, 0.32, 0, 0, TAU); c.fill();
  for (let i = 0; i < 2; i++) { const k = Math.sin(pa + i * PI); c.beginPath(); c.ellipse(0, k * 0.15, 0.03, Math.abs(k) * 0.15 + 0.01, 0, 0, TAU); fo(c, P.brass, LINE.hair * 1.5); }
  c.beginPath(); c.arc(0, 0, 0.035, 0, TAU); fo(c, P.gold, LINE.hair * 1.5);
  c.restore();
  // the tycoon behind the rail, then the hull over his legs
  const lean = tycoon(c, mood, t, champagne);
  sprite(c, 'zepGon', [-0.92, BY.rail - 0.62, 1.86, 0.66 + (BY.keel - BY.rail) + 0.04], gondolaSprite);
  // the bow lantern (glows warm; the only light at night)
  const lp = 0.75 + 0.25 * Math.sin(t * 3.1);
  c.beginPath(); rrP(c, 0.92, BY.rail - 0.13, 0.08, 0.13, 0.02); fo(c, '#ffe08a', LINE.inkThin);
  glowU(c, 0.96, BY.rail - 0.065, 0.32, P.goldHot, 0.55 * lp);
  // steam from the chimney
  for (let i = 0; i < 4; i++) {
    const u = frac(t * 0.5 + i / 4);
    c.fillStyle = RA('#ffffff', 0.62 * (1 - u) * Math.min(1, u * 5)); c.beginPath(); c.arc(-0.745 - u * 0.3, BY.rail - 0.6 - u * 0.45, 0.04 + u * 0.09, 0, TAU); c.fill();
  }
  // the near arm: the champagne flute (or the blunderbuss, or a sip)
  const sk = '#f2b48a';
  const sx0 = 0.05 + (Math.sin(lean) * 0.36 + 0.2) * 1.25, sy0 = BY.rail + 0.05 - Math.cos(lean) * 0.36 * 1.25;
  const arm = [sx0, sy0, 0, 0, 0, 0];
  let flAng = 0, flEmpty = champagne <= 0.02;
  let gun = false, fire = 0;
  if (mood === 'pay') {
    gun = true; fire = Math.max(0, 1 - frac(t / 1.3) * 4);
    arm[2] = sx0 + 0.18; arm[3] = sy0 + 0.12; arm[4] = sx0 + 0.34; arm[5] = sy0 + 0.1;
  } else if (mood === 'wave_off') {
    arm[2] = sx0 + 0.16; arm[3] = sy0 + 0.1; arm[4] = sx0 + 0.3; arm[5] = sy0 + 0.04; flAng = 2.4; flEmpty = true;
  } else {
    const sip = mood === 'wait' ? Math.max(0, Math.sin(frac(t / 5) * PI * 2) ) * (frac(t / 5) < 0.5 ? 1 : 0) : 0;
    arm[2] = sx0 + 0.14 - sip * 0.06; arm[3] = sy0 + 0.16 - sip * 0.12; arm[4] = sx0 + 0.27 - sip * 0.1; arm[5] = sy0 + 0.08 - sip * 0.3;
    flAng = mood === 'laugh' ? Math.sin(t * 16) * 0.25 : -sip * 0.6;
  }
  if (!gun) flute(c, arm[4] + 0.01, arm[5] - 0.02, flAng, champagne, t, flEmpty);
  limb2(c, arm, 0.1, P.emerald, P.emerald);
  c.beginPath(); c.arc(arm[4], arm[5], 0.052, 0, TAU); fo(c, sk, LINE.inkThin);
  c.fillStyle = P.gold; c.beginPath(); c.arc(arm[4] + 0.022, arm[5] - 0.022, 0.013, 0, TAU); c.fill();
  let gx = 0, gy = 0;
  if (gun) {
    const ga = 0.75;
    blunderbuss(c, arm[4] - 0.05, arm[5], ga, t, fire);
    gx = arm[4] - 0.05 + Math.cos(ga) * 0.5; gy = arm[5] + Math.sin(ga) * 0.5;
  }
  c.restore();
  rs(ctx);
  // points (screen px)
  const cr = Math.cos(tilt), sr = Math.sin(tilt);
  const toS = (ux, uy, kx, ky) => { const X = ux * cr - uy * sr, Y = ux * sr + uy * cr + bob; BUYER_PTS[kx] = x + f * X * s; BUYER_PTS[ky] = y + Y * s; };
  { const cx = 0.05, cy = 0.02 + TAG_H / 2, ca = Math.cos(tagA), sa = Math.sin(tagA);
    toS(hx + cx * ca - cy * sa, hy + cx * sa + cy * ca, 'tagX', 'tagY'); }
  BUYER_PTS.tagR = 0.46 * s;
  toS(holeX, holeY, 'holeX', 'holeY'); BUYER_PTS.holeAng = tilt + tagA; BUYER_PTS.holeF = f;
  toS(gun ? gx : 0.5, gun ? gy : BY.rail + 0.2, 'gunX', 'gunY');
  toS(0.18, BY.rail - 0.8, 'loupeX', 'loupeY');
  toS(0.2, BY.rail - 0.68, 'mouthX', 'mouthY');
  return BUYER_PTS;
});
//>>BUYER

//<<STREET
// ================================================================================================ THE STREET: merchant, rat, anvil, tether, stakes, walls
// ---- the Merchant: a trench-coated clockwork automaton on a unicycle, a neon sign on a pole showing the coin's value
export const drawMerchant = guard('drawMerchant', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const f = st.facing < 0 ? -1 : 1;
  const roll = num(st.roll, t * 4);
  const tk = clamp(num(st.tackled, 0), 0, 1);
  const sign = st.sign == null ? '' : String(st.sign);
  beginU(ctx, x, y, s, f);
  const c = ctx;
  // dust when knocked down
  if (tk > 0.05) {
    for (let i = 0; i < 5; i++) { const u = frac(t * 1.5 + i / 5); c.fillStyle = RA('#d8c7a3', 0.7 * (1 - u) * Math.min(1, tk * 2)); c.beginPath(); c.arc(-0.3 + i * 0.18 + u * 0.1, -0.05 - u * 0.2, 0.05 + u * 0.08, 0, TAU); c.fill(); }
  }
  c.save();
  c.rotate(-tk * 1.42);
  const bob = tk > 0 ? 0 : Math.sin(roll * 2) * 0.01;
  const wr = 0.19;
  // ---- the wheel
  c.save(); c.translate(0, -wr);
  c.beginPath(); c.arc(0, 0, wr, 0, TAU); fo(c, '#2a2626');
  c.beginPath(); c.arc(0, 0, wr * 0.78, 0, TAU); ink(c, 0.03, P.brass); c.stroke();
  c.strokeStyle = P.brassLight; c.lineWidth = 0.012;
  for (let i = 0; i < 8; i++) { const a = roll + (i / 8) * TAU; c.beginPath(); c.moveTo(0, 0); c.lineTo(Math.cos(a) * wr * 0.76, Math.sin(a) * wr * 0.76); c.stroke(); }
  c.beginPath(); c.arc(0, 0, 0.035, 0, TAU); fo(c, P.gold, LINE.hair * 1.5);
  c.restore();
  // ---- fork + seat post + seat
  c.strokeStyle = P.ink; c.lineWidth = 0.05; c.beginPath(); c.moveTo(0, -wr); c.lineTo(0, -0.56 + bob); c.stroke();
  c.strokeStyle = P.ironLight; c.lineWidth = 0.028; c.stroke();
  c.beginPath(); c.ellipse(-0.01, -0.57 + bob, 0.08, 0.025, 0, 0, TAU); fo(c, '#3b2a1e', LINE.inkThin);
  // ---- piston legs on the cranks
  const cr = 0.075;
  for (let leg = 1; leg >= 0; leg--) {
    const a = roll + leg * PI;
    const px = Math.cos(a) * cr, py = -wr + Math.sin(a) * cr;
    const hip = [0.0, -0.6 + bob];
    const o = [0, 0, 0, 0, 0, 0];
    ik(hip[0], hip[1], px, py - 0.015, 0.22, 0.2, 1, o);
    limb2(c, o, 0.05, leg ? DK(P.brass, 0.2) : P.brass, leg ? DK(P.brassDark, 0.2) : P.brassDark);
    rivetU(c, o[2], o[3], 0.014);
    c.beginPath(); rrP(c, px - 0.05, py - 0.02, 0.1, 0.035, 0.012); fo(c, leg ? '#3a3a3a' : '#555', LINE.hair * 1.5);
  }
  // ---- the trench coat (with a flapping tail) + belt + collar
  const flap = Math.sin(t * 9) * 0.03 + (tk ? 0 : 0.04);
  c.beginPath(); c.moveTo(-0.13, -1.0 + bob); c.lineTo(0.12, -1.0 + bob); c.quadraticCurveTo(0.17, -0.8, 0.15, -0.55 + bob);
  c.lineTo(-0.05, -0.5 + bob); c.lineTo(-0.2 - flap, -0.47 + bob); c.quadraticCurveTo(-0.2, -0.8, -0.13, -1.0 + bob); c.closePath();
  shadeU(c, -0.22, -1.0, 0.39, 0.55, P.trench); ink(c); c.stroke();
  c.beginPath(); c.rect(-0.18, -0.74 + bob, 0.34, 0.045); fo(c, '#3b2c1e', LINE.inkThin);
  c.beginPath(); rrP(c, 0.02, -0.75 + bob, 0.05, 0.065, 0.008); fo(c, P.gold, LINE.hair * 1.5);
  c.fillStyle = P.ink; for (let i = 0; i < 3; i++) { c.beginPath(); c.arc(0.09, -0.93 + i * 0.07 + bob, 0.012, 0, TAU); c.fill(); }
  c.beginPath(); c.moveTo(-0.13, -1.0 + bob); c.lineTo(-0.05, -1.08 + bob); c.lineTo(0.0, -0.95 + bob); c.closePath(); fo(c, DK(P.trench, 0.15), LINE.inkThin);
  c.beginPath(); c.moveTo(0.12, -1.0 + bob); c.lineTo(0.08, -1.08 + bob); c.lineTo(0.02, -0.95 + bob); c.closePath(); fo(c, DK(P.trench, 0.15), LINE.inkThin);
  // ---- the sign pole (from his back) and the neon sign. st.duck 0..1 swings the pole back and down (he ducks it under the Buyer's
  //      price tag, which hangs at the same height); the board itself stays level
  const swayP = Math.sin(t * 2.3) * 0.03 * (1 - tk);
  const duck = clamp(num(st.duck, 0), 0, 1) * (1 - tk), dA = duck * 1.15, dS = Math.sin(dA), dC = Math.cos(dA);
  const px0 = -0.15, py0 = -0.72 + bob;
  c.strokeStyle = P.ink; c.lineWidth = 0.04; c.beginPath(); c.moveTo(px0, py0); c.lineTo(px0 + swayP - 0.75 * dS, py0 - 0.75 * dC); c.stroke();
  c.strokeStyle = P.ironLight; c.lineWidth = 0.022; c.stroke();
  const sw = 0.66, sh = 0.26, scx = px0 + swayP - 0.88 * dS, scy = py0 - 0.88 * dC;
  c.save(); c.translate(scx, scy); c.rotate(swayP * 0.6);
  c.beginPath(); rrP(c, -sw / 2, -sh / 2, sw, sh, 0.04); fo(c, '#14101c');
  c.beginPath(); rrP(c, -sw / 2 + 0.025, -sh / 2 + 0.025, sw - 0.05, sh - 0.05, 0.03);
  const flick = (frac(t * 0.37) > 0.93 && frac(t * 7.1) > 0.5) || (tk > 0.3 && frac(t * 9) > 0.5) ? 0.25 : 1;
  ink(c, 0.016, RA(P.cyan, flick)); c.stroke();
  glowU(c, 0, 0, sw * 0.6, P.neonPink, 0.45 * flick);
  textU(c, sign, 0, 0.005, 0.13, { color: RA('#ffd6f6', flick), font: FONT.deco, stroke: RA(P.neonPink, flick), strokeW: 0.03, maxW: sw - 0.08 });
  for (const bxx of [-sw / 2, sw / 2]) rivetU(c, bxx * 0.9, -sh / 2 + 0.03, 0.012);
  if (tk > 0.3) { c.strokeStyle = RA(P.goldHot, frac(t * 11) > 0.5 ? 1 : 0); c.lineWidth = 0.014; c.beginPath(); c.moveTo(sw / 2, 0); c.lineTo(sw / 2 + 0.06, -0.05); c.lineTo(sw / 2 + 0.03, 0.0); c.lineTo(sw / 2 + 0.1, 0.03); c.stroke(); }
  c.restore();
  // ---- arms in sleeves (one on the pole, one on the hip)
  const aF = [-0.08, -0.96 + bob, -0.2, -0.85 + bob, px0 - 0.24 * dS, py0 - 0.23 * dC];         // the far hand stays on the pole
  const aN = [0.08, -0.96 + bob, 0.2, -0.82 + bob, 0.13, -0.7 + bob];
  limb2(c, aF, 0.07, DK(P.trench, 0.15), DK(P.trench, 0.15));
  c.beginPath(); c.arc(aF[4], aF[5], 0.035, 0, TAU); fo(c, P.brassLight, LINE.inkThin);
  limb2(c, aN, 0.07, P.trench, P.trench);
  c.beginPath(); c.arc(aN[4], aN[5], 0.035, 0, TAU); fo(c, P.brassLight, LINE.inkThin);
  // ---- the clockwork head + fedora (flies off when tackled)
  const hy = -1.13 + bob;
  c.save(); c.translate(0.01, hy);
  c.beginPath(); c.ellipse(0, 0, 0.1, 0.11, 0, 0, TAU); shadeU(c, -0.1, -0.11, 0.2, 0.22, P.brass); ink(c); c.stroke();
  rivetU(c, -0.07, -0.02, 0.01); rivetU(c, -0.06, 0.06, 0.01);
  if (tk > 0.4) { c.strokeStyle = P.ink; c.lineWidth = LINE.inkThin; for (const ex of [0.03, 0.075]) { c.beginPath(); c.moveTo(ex - 0.015, -0.03); c.lineTo(ex + 0.015, 0.0); c.moveTo(ex + 0.015, -0.03); c.lineTo(ex - 0.015, 0.0); c.stroke(); } }
  else {
    for (const ex of [0.03, 0.075]) { c.beginPath(); c.arc(ex, -0.015, 0.022, 0, TAU); fo(c, '#0c1a12', LINE.hair * 1.5); c.fillStyle = P.neonGreen; c.beginPath(); c.arc(ex + 0.004, -0.015, 0.012, 0, TAU); c.fill(); }
    glowU(c, 0.05, -0.015, 0.08, P.neonGreen, 0.4);
  }
  c.fillStyle = P.ink; for (let i = 0; i < 3; i++) c.fillRect(0.02 + i * 0.022, 0.045, 0.012, 0.03);
  c.restore();
  const hatFly = tk > 0.15 ? (tk - 0.15) / 0.85 : 0;
  c.save(); c.translate(0.0 - hatFly * 0.5, hy - 0.09 - hatFly * 0.55); c.rotate(-0.12 - hatFly * 2.2);
  c.beginPath(); c.ellipse(0, 0.0, 0.17, 0.035, 0, 0, TAU); fo(c, '#3b2c1e');
  c.beginPath(); c.moveTo(-0.1, 0.0); c.quadraticCurveTo(-0.11, -0.13, -0.02, -0.14); c.quadraticCurveTo(0.04, -0.1, 0.06, -0.13); c.quadraticCurveTo(0.11, -0.12, 0.1, 0.0); c.closePath();
  shadeU(c, -0.11, -0.14, 0.22, 0.14, '#4a3828'); ink(c); c.stroke();
  c.beginPath(); c.rect(-0.1, -0.045, 0.2, 0.03); fo(c, P.crimson, LINE.hair * 1.5);
  c.restore();
  // ---- gears and springs popping out when he goes down
  if (tk > 0.5) {
    const k = (tk - 0.5) * 2;
    for (let i = 0; i < 3; i++) { const u = frac(t * 0.9 + i / 3); gear(c, 0.05 + Math.cos(i * 2.1) * 0.3 * u, -0.9 - u * 0.4 + u * u * 0.3, 0.035, 7, t * 6 + i, P.brassLight); }
    void k;
  }
  c.restore();
  rs(ctx);
});

// ---- the Slippage Rat: razor blades and brass (0.22 tall). peek | bite | run
export const drawRat = guard('drawRat', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const ph = st.phase === 'bite' || st.phase === 'run' ? st.phase : 'peek';
  beginU(ctx, x, y, s, st.facing);
  const c = ctx;
  const run = ph === 'run', bite = ph === 'bite';
  const bob = run ? Math.abs(Math.sin(t * 22)) * 0.012 : 0;
  if (ph === 'peek') {
    // the hole and the head + paws peeking over its rim
    c.beginPath(); c.ellipse(0, -0.005, 0.11, 0.035, 0, 0, TAU); fo(c, '#120c08', LINE.inkThin);
    const up = 0.02 + Math.max(0, Math.sin(t * 1.7)) * 0.03;
    c.save(); c.beginPath(); c.rect(-0.3, -0.5, 0.6, 0.495); c.clip();
    ratHead(c, 0.0, -0.045 - up, t, false, 0);
    c.restore();
    c.fillStyle = P.brassDark; for (const px of [-0.04, 0.05]) { c.beginPath(); c.ellipse(px, -0.012, 0.025, 0.014, 0, 0, TAU); c.fill(); c.strokeStyle = P.ink; c.lineWidth = LINE.hair * 1.5; c.stroke(); }
    rs(ctx); return;
  }
  // tail: brass segments ending in a razor blade
  const tw = Math.sin(t * (run ? 14 : 4)) * 0.03;
  c.strokeStyle = P.ink; c.lineWidth = 0.03; c.beginPath(); c.moveTo(-0.1, -0.06 - bob); c.quadraticCurveTo(-0.22, -0.02 + tw, -0.3, -0.09 - tw); c.stroke();
  c.strokeStyle = P.brass; c.lineWidth = 0.016; c.stroke();
  c.save(); c.translate(-0.3, -0.09 - tw); c.rotate(-0.6 + tw * 4);
  c.beginPath(); c.moveTo(0, -0.025); c.lineTo(-0.07, -0.02); c.lineTo(-0.085, 0.0); c.lineTo(-0.07, 0.02); c.lineTo(0, 0.025); c.closePath(); fo(c, '#dfe6ee', LINE.hair * 1.5);
  c.fillStyle = P.ink; c.fillRect(-0.06, -0.004, 0.04, 0.008);
  c.restore();
  // legs
  for (let i = 0; i < 4; i++) {
    const lx = i < 2 ? -0.06 + i * 0.03 : 0.04 + (i - 2) * 0.03;
    const a = run ? Math.sin(t * 22 + i * PI * 0.5) * 0.5 : 0;
    c.strokeStyle = P.ink; c.lineWidth = 0.022; c.beginPath(); c.moveTo(lx, -0.05 - bob); c.lineTo(lx + Math.sin(a) * 0.035, -0.004); c.stroke();
    c.strokeStyle = P.brassDark; c.lineWidth = 0.011; c.stroke();
  }
  // body
  c.beginPath(); c.ellipse(-0.01, -0.075 - bob, 0.11, 0.06, -0.05, 0, TAU); shadeU(c, -0.12, -0.135, 0.22, 0.12, P.brass); ink(c, LINE.inkThin); c.stroke();
  c.strokeStyle = RA(P.brassDark, 0.9); c.lineWidth = 0.008; for (let i = 0; i < 3; i++) { c.beginPath(); c.arc(-0.01, -0.06 - bob, 0.05 + i * 0.02, -2.3, -0.9); c.stroke(); }
  rivetU(c, -0.05, -0.1 - bob, 0.008); rivetU(c, 0.02, -0.11 - bob, 0.008);
  // the head (bite lunges + snaps)
  const lunge = bite ? Math.max(0, Math.sin(t * 13)) * 0.03 : 0;
  ratHead(c, 0.1 + lunge, -0.09 - bob, t, bite, lunge);
  if (run) { c.strokeStyle = 'rgba(255,255,255,0.75)'; c.lineWidth = 0.008; for (let i = 0; i < 3; i++) { const u = frac(t * 4 + i / 3); c.beginPath(); c.moveTo(-0.16 - u * 0.1, -0.05 - i * 0.03); c.lineTo(-0.24 - u * 0.1, -0.05 - i * 0.03); c.stroke(); } }
  rs(ctx);
});
function ratHead(c, x, y, t, bite, lunge) {
  c.save(); c.translate(x, y);
  // razor-blade ear
  c.save(); c.translate(-0.02, -0.05); c.rotate(-0.35);
  c.beginPath(); rrP(c, -0.035, -0.045, 0.07, 0.07, 0.006); fo(c, '#e3eaf1', LINE.hair * 1.5);
  c.fillStyle = P.ink; c.fillRect(-0.02, -0.014, 0.04, 0.008); c.beginPath(); c.arc(-0.02, -0.01, 0.006, 0, TAU); c.arc(0.02, -0.01, 0.006, 0, TAU); c.fill();
  c.restore();
  // snout (with the jaw that snaps)
  const jaw = bite ? Math.max(0, Math.sin(t * 26)) * 0.35 : 0.05;
  c.save(); c.translate(0.02, 0.01); c.rotate(jaw);
  c.beginPath(); c.moveTo(-0.02, 0.0); c.lineTo(0.08, 0.005); c.lineTo(0.0, 0.025); c.closePath(); fo(c, P.brassDark, LINE.hair * 1.5);
  c.restore();
  c.beginPath(); c.moveTo(-0.055, 0.01); c.quadraticCurveTo(-0.05, -0.06, 0.02, -0.045); c.quadraticCurveTo(0.08, -0.03, 0.11, 0.0); c.quadraticCurveTo(0.05, 0.03, -0.055, 0.01); c.closePath();
  shadeU(c, -0.06, -0.06, 0.17, 0.09, P.brass); ink(c, LINE.inkThin); c.stroke();
  // steel buck teeth
  c.beginPath(); c.rect(0.085, 0.0, 0.016, 0.022); fo(c, '#f0f4f8', LINE.hair);
  // nose + red eye
  c.beginPath(); c.arc(0.11, -0.003, 0.011, 0, TAU); c.fillStyle = P.ink; c.fill();
  c.beginPath(); c.arc(0.025, -0.022, 0.014, 0, TAU); c.fillStyle = '#ff2a2a'; c.fill(); c.strokeStyle = P.ink; c.lineWidth = LINE.hair; c.stroke();
  glowU(c, 0.025, -0.022, 0.04, '#ff2a2a', 0.6);
  // wire whiskers
  c.strokeStyle = RA('#e8eef4', 0.9); c.lineWidth = 0.005;
  c.beginPath(); c.moveTo(0.09, 0.0); c.lineTo(0.15, -0.02); c.moveTo(0.09, 0.005); c.lineTo(0.155, 0.01); c.moveTo(0.085, 0.008); c.lineTo(0.14, 0.03); c.stroke();
  if (bite && jaw > 0.25) { for (let i = 0; i < 3; i++) { const a = -0.5 + i * 0.5; c.strokeStyle = P.goldHot; c.lineWidth = 0.008; c.beginPath(); c.moveTo(0.12 + Math.cos(a) * 0.02, 0.01 + Math.sin(a) * 0.02); c.lineTo(0.12 + Math.cos(a) * 0.06, 0.01 + Math.sin(a) * 0.06); c.stroke(); } }
  c.restore();
}

// ---- the 500-lb anvil (0.42 wide; the vault anvil = the stop). glow = red heat; bounce 0..1 = a refused hop
export const ANVIL_PTS = { ringX: 0, ringY: 0 };
function anvilSprite(c) {
  // feet, waist, body with heel + horn
  c.beginPath();
  c.moveTo(-0.16, 0); c.lineTo(-0.12, -0.05); c.lineTo(-0.07, -0.07); c.lineTo(-0.075, -0.15);
  c.quadraticCurveTo(-0.12, -0.16, -0.18, -0.17); c.lineTo(-0.18, -0.275); c.lineTo(0.13, -0.275);
  c.quadraticCurveTo(0.2, -0.26, 0.255, -0.225); c.quadraticCurveTo(0.18, -0.2, 0.12, -0.17);
  c.quadraticCurveTo(0.09, -0.16, 0.07, -0.15); c.lineTo(0.065, -0.07); c.lineTo(0.12, -0.05); c.lineTo(0.16, 0); c.lineTo(0.05, 0); c.lineTo(0.03, -0.03); c.lineTo(-0.03, -0.03); c.lineTo(-0.05, 0); c.closePath();
  shadeU(c, -0.18, -0.28, 0.44, 0.28, P.iron); ink(c); c.stroke();
  // the polished face
  c.beginPath(); c.moveTo(-0.18, -0.275); c.lineTo(0.13, -0.275); c.quadraticCurveTo(0.2, -0.26, 0.255, -0.225); c.lineTo(0.22, -0.23); c.quadraticCurveTo(0.17, -0.25, 0.12, -0.255); c.lineTo(-0.18, -0.255); c.closePath();
  c.fillStyle = '#c6ccd6'; c.fill();
  c.fillStyle = 'rgba(255,255,255,0.75)'; c.fillRect(-0.15, -0.272, 0.18, 0.008);
  // hardy hole + stamp
  c.fillStyle = P.ink; c.fillRect(-0.15, -0.255, 0.025, 0.015);
  rivetU(c, -0.12, -0.03, 0.01); rivetU(c, 0.1, -0.03, 0.01);
}
export const drawAnvil = guard('drawAnvil', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const g = clamp(num(st.glow, 0), 0, 1), b = clamp(num(st.bounce, 0), 0, 1);
  const f = st.facing < 0 ? -1 : 1;
  const hop = b > 0 && b < 1 ? Math.sin(PI * b) * 0.32 : 0;
  const land = b > 0.88 || (b > 0 && b < 0.1);
  const wob = b > 0 && b < 1 ? Math.sin(PI * b * 2) * 0.18 : 0;
  beginU(ctx, x, y, s, f);
  const c = ctx;
  // a contact shadow (shrinks as it hops)
  c.fillStyle = 'rgba(0,0,0,0.25)'; c.beginPath(); c.ellipse(0, 0, 0.19 * (1 - hop), 0.025, 0, 0, TAU); c.fill();
  c.save(); c.translate(0, -hop); c.rotate(wob);
  if (land) c.scale(1.12, 0.86);
  if (g > 0.02) glowU(c, 0, -0.18, 0.4, '#ff5a1f', 0.5 * g);
  sprite(c, 'anvil', [-0.2, -0.3, 0.48, 0.32], anvilSprite);
  textU(c, '500 LB', -0.034 * f, -0.216, 0.058, { color: 'rgba(255,255,255,0.4)', font: FONT.deco });
  textU(c, '500 LB', -0.03 * f, -0.212, 0.058, { color: 'rgba(0,0,0,0.75)', font: FONT.deco });
  if (g > 0.02) {
    c.globalCompositeOperation = 'lighter';
    c.fillStyle = RA('#ff6a1f', 0.55 * g); c.beginPath(); c.moveTo(-0.18, -0.275); c.lineTo(0.13, -0.275); c.quadraticCurveTo(0.2, -0.26, 0.255, -0.225); c.quadraticCurveTo(0.18, -0.2, 0.12, -0.17); c.lineTo(-0.18, -0.17); c.closePath(); c.fill();
    c.globalCompositeOperation = 'source-over';
    // heat shimmer
    c.strokeStyle = RA('#ffb07a', 0.5 * g); c.lineWidth = 0.008;
    for (let i = 0; i < 3; i++) { const u = frac(t * 0.8 + i / 3); c.beginPath(); c.moveTo(-0.1 + i * 0.1, -0.3 - u * 0.15); c.quadraticCurveTo(-0.08 + i * 0.1, -0.33 - u * 0.15, -0.1 + i * 0.1, -0.36 - u * 0.15); c.stroke(); }
  }
  // the tether ring on top of the horn root
  c.beginPath(); c.arc(0.1, -0.3, 0.03, 0, TAU); ink(c, 0.028); c.stroke(); ink(c, 0.014, P.brass); c.stroke();
  c.restore();
  if (land && b > 0) {   // a clang: spark lines at the base
    c.strokeStyle = P.goldHot; c.lineWidth = 0.012;
    for (let i = 0; i < 5; i++) { const a = PI + 0.3 + i * 0.6; c.beginPath(); c.moveTo(Math.cos(a) * 0.2, -0.02 + Math.sin(a) * 0.04); c.lineTo(Math.cos(a) * 0.3, -0.03 + Math.sin(a) * 0.1); c.stroke(); }
  }
  rs(ctx);
  ANVIL_PTS.ringX = x + f * 0.1 * s; ANVIL_PTS.ringY = y + (-0.3 - hop) * s;
  return ANVIL_PTS;
});

// ---- the tether: a hemp rope from the runner's belt to the anvil. tension 0 = slack sag, 1 = taut, red-hot, vibrating.
// Tension reads in three steps: slack (hemp, sagging onto the street), tight (> 0.3: a thin red glint along it), red-hot (> 0.45).
// st.groundAt(px) -> the street's surface y at screen x: a slack rope drapes over the street and the pit lip, never through the deck.
const TP = new Float32Array(44);
export const drawTether = guard('drawTether', function (ctx, x1, y1, x2, y2, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const k = clamp(num(st.tension, 0), 0, 1);
  if (![x1, y1, x2, y2, s].every(isFinite)) return;
  const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1;
  const nx = -dy / L, ny = dx / L;
  const sag = Math.pow(1 - k, 1.4) * (0.08 * s + L * 0.22);
  const hot = clamp((k - 0.45) / 0.55, 0, 1), tight = clamp((k - 0.3) / 0.15, 0, 1);
  const amp = hot * 0.022 * s;
  const N = 21;
  const groundAt = typeof st.groundAt === 'function' ? st.groundAt : null;
  const floor = num(st.groundY, Math.max(y1, y2) + 0.3 * s);   // a slack rope lies on the street, never through it
  for (let i = 0; i < N; i++) {
    const u = i / (N - 1);
    let px = x1 + dx * u, py = y1 + dy * u + sag * 4 * u * (1 - u);
    const v = amp * Math.sin(PI * u * 3) * Math.sin(t * 61 + u * 4);
    px += nx * v; py += ny * v;
    let g = floor;
    if (groundAt && i > 0 && i < N - 1) { const gg = groundAt(px); if (isFinite(gg)) g = gg; }
    if (py > g) py = g - (py - g) * 0.04;
    TP[i * 2] = px; TP[i * 2 + 1] = py;
  }
  sv(ctx);
  ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  const path = () => { ctx.beginPath(); ctx.moveTo(TP[0], TP[1]); for (let i = 1; i < N; i++) ctx.lineTo(TP[i * 2], TP[i * 2 + 1]); };
  const w = Math.max(2, 0.03 * s);
  if (hot > 0) { path(); ctx.globalCompositeOperation = 'lighter'; ctx.strokeStyle = RA('#ff5a1f', 0.35 * hot); ctx.lineWidth = w * 3.2; ctx.stroke(); ctx.globalCompositeOperation = 'source-over'; }
  path(); ctx.strokeStyle = P.ink; ctx.lineWidth = w + Math.max(1.5, LINE.ink * s); ctx.stroke();
  const col = MX('#c9a26a', '#ff5a1f', hot);
  path(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.stroke();
  if (tight > 0 && hot < 1) { path(); ctx.strokeStyle = RA('#ff3b2f', 0.75 * tight * (1 - hot)); ctx.lineWidth = Math.max(1, w * 0.3); ctx.stroke(); }   // tight: the red glint
  // the twist of the rope
  path(); ctx.strokeStyle = MX('#8a6a3a', '#ffd27a', hot); ctx.lineWidth = Math.max(1, w * 0.45); ctx.setLineDash([w * 0.5, w * 0.9]); ctx.lineDashOffset = -t * (hot ? 30 : 0); ctx.stroke(); ctx.setLineDash([]);
  path(); ctx.strokeStyle = RA('#ffffff', 0.25 + 0.4 * hot); ctx.lineWidth = Math.max(1, w * 0.18); ctx.translate(0, -w * 0.22); ctx.stroke();
  rs(ctx);
});

// ---- stakes: lit (a glowing lamp-gem), golden with initials, rusty; an optional paper tag
export const drawStake = guard('drawStake', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const golden = !!st.golden, rusty = !!st.rusty && !golden, lit = !!st.lit && !rusty;
  beginU(ctx, x, y, s, 1);
  const c = ctx;
  if (rusty) c.rotate(0.12);
  // a little mound / crack in the marble where it was driven in
  c.fillStyle = 'rgba(0,0,0,0.22)'; c.beginPath(); c.ellipse(0, 0, 0.07, 0.016, 0, 0, TAU); c.fill();
  const shaft = golden ? P.gold : rusty ? '#8a4a22' : P.ironLight;
  c.beginPath(); c.moveTo(-0.022, 0); c.lineTo(-0.036, -0.47); c.lineTo(0.036, -0.47); c.lineTo(0.022, 0); c.closePath();
  shadeU(c, -0.04, -0.47, 0.08, 0.47, shaft); ink(c, LINE.inkThin); c.stroke();
  c.fillStyle = RA('#ffffff', golden ? 0.5 : 0.3); c.fillRect(-0.022, -0.45, 0.01, 0.42);
  if (rusty) { c.fillStyle = RA('#4a2410', 0.8); for (let i = 0; i < 6; i++) { c.beginPath(); c.arc(-0.012 + rand(i * 5) * 0.024, -0.05 - rand(i * 3) * 0.38, 0.006 + rand(i) * 0.006, 0, TAU); c.fill(); } }
  // the tie ring: where the rope can be tied (st.eligible = the anvil may be dragged here now: it pulses)
  if (lit || golden) {
    const el = st.eligible ? 0.6 + 0.4 * Math.sin(t * 4 + x * 0.02) : 0;
    if (el > 0) glowU(c, 0.05, -0.28, 0.17, P.goldHot, 0.55 * el);
    c.beginPath(); c.ellipse(0.052, -0.28, 0.04, 0.046, 0, 0, TAU); ink(c, 0.03); c.stroke();
    c.strokeStyle = el > 0 ? MX(P.brass, '#fff2b0', el) : P.brass; c.lineWidth = 0.016; c.stroke();
    c.beginPath(); rrP(c, 0.012, -0.3, 0.03, 0.04, 0.008); fo(c, P.brassDark, LINE.hair * 1.5);
  }
  // collar
  c.beginPath(); rrP(c, -0.05, -0.505, 0.1, 0.045, 0.014); fo(c, golden ? P.goldHot : rusty ? '#6b3a18' : P.brass, LINE.inkThin);
  if (golden) {
    const tw = Math.pow(Math.max(0, Math.sin(t * 2.2 + x * 0.01)), 10);
    glowU(c, 0, -0.32, 0.18, P.goldHot, 0.3 + 0.3 * tw);
    c.beginPath(); rrP(c, -0.05, -0.3, 0.1, 0.07, 0.01); fo(c, P.goldDeep, LINE.hair * 1.5);
    textU(c, String(st.initials || '').slice(0, 3), 0, -0.264, 0.045, { color: '#fff6cf', font: FONT.deco });
  }
  // the head: a gem in a little brass cage (cracked and empty when rusty)
  if (!rusty) {
    const pulse = 0.75 + 0.25 * Math.sin(t * 3 + x * 0.02);
    if (lit || golden) glowU(c, 0, -0.57, 0.24 * (lit ? pulse : 0.8), lit ? P.goldHot : P.gold, lit ? 0.9 : 0.45);
    c.beginPath(); c.moveTo(0, -0.64); c.lineTo(0.05, -0.57); c.lineTo(0, -0.505); c.lineTo(-0.05, -0.57); c.closePath();
    fo(c, lit ? MX('#ffd25a', '#fff6cf', pulse - 0.5) : golden ? P.goldHot : '#7a5a2a', LINE.inkThin);
    c.fillStyle = RA('#ffffff', lit ? 0.85 : 0.35); c.beginPath(); c.moveTo(0, -0.61); c.lineTo(0.02, -0.57); c.lineTo(0, -0.565); c.closePath(); c.fill();
    c.strokeStyle = P.ink; c.lineWidth = LINE.hair; c.beginPath(); c.moveTo(-0.038, -0.565); c.lineTo(0.038, -0.565); c.stroke();
    if (lit) { const sp = frac(t * 0.7 + x * 0.003); c.fillStyle = RA(P.goldHot, 1 - sp); c.beginPath(); c.arc(0.05 + sp * 0.03, -0.6 - sp * 0.1, 0.008, 0, TAU); c.fill(); }
  } else {
    c.strokeStyle = P.ink; c.lineWidth = 0.02; c.beginPath(); c.moveTo(-0.03, -0.5); c.lineTo(-0.035, -0.56); c.moveTo(0.03, -0.5); c.lineTo(0.025, -0.55); c.stroke();
    c.strokeStyle = '#6b3a18'; c.lineWidth = 0.01; c.stroke();
  }
  // a paper tag on a string
  if (st.label) {
    const big = !!st.bigLabel, tw = big ? 0.42 : 0.2, th = big ? 0.15 : 0.085, ts = big ? 0.105 : 0.05;   // bigLabel: legible at play size
    c.strokeStyle = P.ink; c.lineWidth = 0.008; c.beginPath(); c.moveTo(0.02, -0.48); c.quadraticCurveTo(0.08, -0.45, 0.1, -0.4); c.stroke();
    c.save(); c.translate(0.1, -0.4); c.rotate(0.12 + Math.sin(t * 2) * 0.05);
    c.beginPath(); rrP(c, -0.02, 0.0, tw, th, 0.012); fo(c, '#fbf1d6', LINE.hair * 1.5);
    textU(c, String(st.label), tw / 2 - 0.02, th / 2 + 0.002, ts, { color: P.ink, font: FONT.deco, maxW: tw - 0.04 });
    c.restore();
  }
  rs(ctx);
});

// ---- the protective wall: bricks laid row by row (build 0..1), a brass coping, the rat chewing at its foot
function brickRows(c, rows, dropRow, drop) {
  const W = 0.32, bh = 0.075;
  for (let r = 0; r < rows; r++) {
    const yy = -bh * (r + 1) - (r === dropRow ? drop : 0);
    const off = r % 2 ? 0.08 : 0;
    for (let bx = -W / 2 - off; bx < W / 2; bx += 0.16) {
      const x0 = Math.max(-W / 2, bx), x1 = Math.min(W / 2, bx + 0.16);
      if (x1 - x0 < 0.01) continue;
      const base = MX(P.brick, P.brickLight, rand(r * 7 + bx * 13) * 0.6);
      c.beginPath(); c.rect(x0 + 0.004, yy + 0.004, x1 - x0 - 0.008, bh - 0.008); c.fillStyle = base; c.fill();
      c.fillStyle = RA('#ffffff', 0.16); c.fillRect(x0 + 0.008, yy + 0.008, x1 - x0 - 0.016, 0.012);
      c.fillStyle = RA('#000000', 0.18); c.fillRect(x0 + 0.008, yy + bh - 0.02, x1 - x0 - 0.016, 0.012);
    }
  }
}
function wallSprite(c) {
  const W = 0.32, H = 0.9;
  c.beginPath(); c.rect(-W / 2, -H, W, H); c.fillStyle = '#d9cbb0'; c.fill();
  brickRows(c, 12, -1, 0);
  c.beginPath(); c.rect(-W / 2, -H, W, H); ink(c, LINE.inkThin); c.stroke();
  c.beginPath(); rrP(c, -W / 2 - 0.03, -H - 0.06, W + 0.06, 0.07, 0.015); shadeU(c, -W / 2 - 0.03, -H - 0.06, W + 0.06, 0.07, P.brass); ink(c, LINE.inkThin); c.stroke();
  rivetU(c, -0.1, -H - 0.025, 0.012); rivetU(c, 0.1, -H - 0.025, 0.012);
}
export const drawWall = guard('drawWall', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const b = clamp(num(st.build, 1), 0, 1);
  beginU(ctx, x, y, s, 1);
  const c = ctx;
  c.fillStyle = 'rgba(0,0,0,0.2)'; c.beginPath(); c.ellipse(0, 0, 0.22, 0.03, 0, 0, TAU); c.fill();
  if (b >= 0.999) sprite(c, 'wall', [-0.2, -0.98, 0.4, 1.0], wallSprite);
  else if (b > 0) {
    const rowsF = b * 12, rows = Math.ceil(rowsF), part = rowsF - Math.floor(rowsF);
    const drop = rows > Math.floor(rowsF) ? (1 - ease(part)) * 0.25 : 0;
    c.beginPath(); c.rect(-0.16, -0.075 * Math.floor(rowsF), 0.32, 0.075 * Math.floor(rowsF)); c.fillStyle = '#d9cbb0'; c.fill();
    brickRows(c, rows, rows - 1, drop);
    c.beginPath(); c.rect(-0.16, -0.075 * Math.floor(rowsF), 0.32, 0.075 * Math.floor(rowsF)); ink(c, LINE.inkThin); c.stroke();
    // the trowel tapping the newest brick + mortar dust
    const ty = -0.075 * rows - drop;
    c.save(); c.translate(0.18, ty - 0.02 + Math.abs(Math.sin(t * 12)) * -0.03); c.rotate(-0.5);
    c.beginPath(); c.moveTo(0, 0); c.lineTo(0.09, -0.02); c.lineTo(0.09, 0.03); c.closePath(); fo(c, '#c8ccd2', LINE.hair * 1.5);
    c.strokeStyle = P.ink; c.lineWidth = 0.02; c.beginPath(); c.moveTo(0, 0.005); c.lineTo(-0.06, 0.02); c.stroke(); c.strokeStyle = P.wood; c.lineWidth = 0.012; c.stroke();
    c.restore();
    for (let i = 0; i < 3; i++) { const u = frac(t * 2 + i / 3); c.fillStyle = RA('#e8dcc0', 0.7 * (1 - u)); c.beginPath(); c.arc(-0.1 + i * 0.1, ty - u * 0.08, 0.012 + u * 0.02, 0, TAU); c.fill(); }
  }
  if (st.rat && b > 0.3) {
    // a gnawed hole at the foot of the wall, the rat chewing, shavings flying
    c.beginPath(); c.ellipse(0.06, -0.06, 0.07, 0.05, 0, 0, TAU); c.fillStyle = '#140d08'; c.fill(); ink(c, LINE.inkThin); c.stroke();
    c.save(); c.scale(0.9, 0.9); ratHeadPeek(c, 0.08, -0.06, t); c.restore();
    for (let i = 0; i < 3; i++) { const u = frac(t * 2.5 + i / 3); c.fillStyle = RA('#e8edf2', 1 - u); c.beginPath(); c.arc(0.16 + u * 0.12, -0.08 - Math.sin(u * PI) * 0.08, 0.008, 0, TAU); c.fill(); }
  }
  rs(ctx);
});
function ratHeadPeek(c, x, y, t) { ratHead(c, x, y, t, true, 0); }
//>>STREET

//<<COIN
// ------------------------------------------------------------------------------------------------ THE COIN (+ the pistol)
// coinU draws in the current unit space at (x, y) with radius r; the face is a cached sprite at radius 1 (keyed by pixel size,
// kind, half, tarnish and heat), the glow and the glint are live. spin 0..1 = one full turn about the vertical axis.
function halfPath(c) {
  c.beginPath(); c.moveTo(0.06, -1); c.arc(0, 0, 1, -PI / 2, PI / 2, true);
  const zz = [0.06, 0.78, -0.05, 0.55, 0.08, 0.3, -0.06, 0.08, 0.07, -0.16, -0.05, -0.4, 0.07, -0.62, -0.04, -0.84];
  for (let i = 0; i < zz.length; i += 2) c.lineTo(zz[i], zz[i + 1]);
  c.closePath();
}
function coinFace(c, kind, half, tarn, hot, inkW) {
  const wooden = kind === 'w', brass = kind === 'b';
  const rim = wooden ? '#8a5a2b' : brass ? P.brassDark : P.goldDeep;
  const face = wooden ? P.wood : brass ? P.twinBrass : MX(P.gold, P.goldHot, hot);
  c.save();
  if (half) { halfPath(c); c.clip(); }
  c.beginPath(); c.arc(0, 0, 1, 0, TAU); c.fillStyle = rim; c.fill();
  // milled edge
  if (!wooden) { c.strokeStyle = DK(rim, 0.35); c.lineWidth = 0.05; for (let i = 0; i < 28; i++) { const a = i / 28 * TAU; c.beginPath(); c.moveTo(Math.cos(a) * 0.86, Math.sin(a) * 0.86); c.lineTo(Math.cos(a) * 0.97, Math.sin(a) * 0.97); c.stroke(); } }
  // face with the recipe's bands
  c.beginPath(); c.arc(0, 0, 0.8, 0, TAU);
  const g = c.createLinearGradient(-0.8, -0.8, 0.5, 0.8);
  g.addColorStop(0, LI(face, 0.35)); g.addColorStop(0.4, face); g.addColorStop(1, DK(face, 0.22)); c.fillStyle = g; c.fill();
  c.strokeStyle = DK(rim, 0.2); c.lineWidth = 0.05; c.stroke();
  if (wooden) {
    c.strokeStyle = RA('#6b4520', 0.55); c.lineWidth = 0.04;
    for (let i = 1; i <= 3; i++) { c.beginPath(); c.ellipse(0.12, 0.08, 0.2 * i, 0.16 * i, 0.4, 0, TAU); c.stroke(); }
    // carved star
    c.beginPath(); for (let i = 0; i < 10; i++) { const a = -PI / 2 + i * PI / 5, rr = i % 2 ? 0.2 : 0.48; c.lineTo(Math.cos(a) * rr, Math.sin(a) * rr); } c.closePath();
    c.fillStyle = '#7a4a22'; c.fill(); c.strokeStyle = '#f0c088'; c.lineWidth = 0.04; c.save(); c.translate(-0.03, -0.03); c.stroke(); c.restore();
  } else if (brass) {
    gear(c, 0, 0, 0.5, 9, 0.2, LI(P.twinBrass, 0.15));
  } else {
    // ring of beads + an embossed dollar sign (light edge up-left, dark edge down-right)
    c.fillStyle = DK(face, 0.25); for (let i = 0; i < 16; i++) { const a = i / 16 * TAU; c.beginPath(); c.arc(Math.cos(a) * 0.64, Math.sin(a) * 0.64, 0.045, 0, TAU); c.fill(); }
    c.font = 'bold 1.05px ' + FONT.deco; c.textAlign = 'center'; c.textBaseline = 'middle';
    c.fillStyle = LI(face, 0.55); c.fillText('$', -0.04, 0.0);
    c.fillStyle = DK(face, 0.42); c.fillText('$', 0.04, 0.07);
    c.fillStyle = face; c.fillText('$', 0, 0.035);
  }
  if (tarn > 0.01) {
    c.fillStyle = RA('#3d2a12', tarn * 0.45); c.beginPath(); c.arc(0, 0, 1, 0, TAU); c.fill();
    for (let i = 0; i < 9; i++) {
      c.fillStyle = RA(i % 3 ? '#5b6a3a' : '#2e3a22', tarn * 0.8);
      c.beginPath(); c.ellipse(-0.7 + rand(i * 4.1) * 1.4, -0.7 + rand(i * 9.3) * 1.4, 0.1 + rand(i) * 0.18, 0.07 + rand(i * 2) * 0.12, rand(i * 3), 0, TAU); c.fill();
    }
  }
  c.restore();
  // ink outline
  if (half) halfPath(c); else { c.beginPath(); c.arc(0, 0, 1, 0, TAU); }
  c.strokeStyle = P.ink; c.lineWidth = inkW; c.stroke();
  if (half) { c.strokeStyle = RA('#fff6cf', 0.9); c.lineWidth = inkW * 0.4; c.beginPath(); c.moveTo(0.04, -0.9); c.lineTo(0.04, 0.9); c.stroke(); }
}
function coinU(c, x, y, r, st, inkU = LINE.ink) {
  if (!(r > 0)) return;
  const t = num(st.t, 0);
  const kind = st.wooden ? 'w' : st.brass ? 'b' : 'g';
  const glowA = clamp(num(st.glow, 0), 0, 1), tarn = clamp(num(st.tarnish, 0), 0, 1);
  const hot = kind === 'g' ? Math.round(glowA * 4) / 4 : 0, tq = Math.round(tarn * 5) / 5;
  const half = !!st.half;
  const k = Math.cos(num(st.spin, 0) * TAU);
  sv(c);
  c.translate(x, y);
  if (glowA > 0.02 && kind === 'g') glowU(c, 0, 0, r * (1.9 + glowA * 1.1), glowA > 0.75 ? P.goldHot : P.gold, 0.25 + glowA * 0.5);
  c.scale(r, r);
  // the edge when the coin turns
  if (Math.abs(k) < 0.98) {
    const ew = 0.16 * Math.sqrt(1 - k * k) * (k < 0 ? -1 : 1);
    c.beginPath(); rrP(c, Math.min(0, ew) - Math.abs(k) * 0.0, -1, Math.abs(ew) + 0.001, 2, 0.08);
    c.fillStyle = kind === 'w' ? '#8a5a2b' : kind === 'b' ? P.brassDark : P.goldDeep; c.fill();
    c.strokeStyle = P.ink; c.lineWidth = inkU / r; c.stroke();
    c.translate(ew * 0.5, 0);
  }
  c.scale(Math.max(0.04, Math.abs(k)), 1);
  const mm = c.getTransform();
  if ((k < 0) !== ((mm.a * mm.d - mm.b * mm.c) < 0)) c.scale(-1, 1);   // never show a mirrored emblem
  sprite(c, 'coin' + kind + (half ? 'h' : '') + tq + '_' + hot + '_' + Math.round(inkU / r * 100), [-1.1, -1.1, 2.2, 2.2], (c2) => coinFace(c2, kind, half, tq, hot, inkU / r));
  // glint
  if (kind !== 'w') {
    const gl = Math.pow(Math.max(0, Math.sin(t * 1.7 + x * 3)), 12);
    if (gl > 0.05) {
      c.fillStyle = RA('#ffffff', gl);
      c.beginPath(); const gx = -0.42, gy = -0.45, L = 0.45 * gl + 0.1;
      c.moveTo(gx, gy - L); c.lineTo(gx + 0.06, gy - 0.06); c.lineTo(gx + L, gy); c.lineTo(gx + 0.06, gy + 0.06); c.lineTo(gx, gy + L); c.lineTo(gx - 0.06, gy + 0.06); c.lineTo(gx - L, gy); c.lineTo(gx - 0.06, gy - 0.06); c.closePath(); c.fill();
    }
  }
  rs(c);
}
export const drawCoin = guard('drawCoin', function (ctx, cx, cy, r, st) {
  st = st || {};
  r = num(r, 16);
  if (r <= 0) return;
  sv(ctx);
  ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  coinU(ctx, cx, cy, r, st, Math.max(1.4, r * 0.16));
  rs(ctx);
});

// the pistol: a gilded Clockwork-Deco revolver. Unit space, grip at (x, y), barrel along +x. patience glow + recoil with a flash.
function pistolU(c, x, y, glowA, recoil, t) {
  recoil = clamp(recoil, 0, 1);
  c.save(); c.translate(x, y); c.rotate(-recoil * 0.55); c.translate(-recoil * 0.03, 0);
  if (glowA > 0.01) glowU(c, 0.1, -0.03, 0.22 + 0.04 * Math.sin(t * 5), P.goldHot, 0.35 * glowA);
  // grip (ivory with brass rivets)
  c.beginPath(); c.moveTo(-0.025, -0.035); c.lineTo(0.03, -0.035); c.lineTo(0.0, 0.07); c.quadraticCurveTo(-0.03, 0.09, -0.055, 0.065); c.closePath(); fo(c, '#efe3c2', LINE.inkThin);
  rivetU(c, -0.012, 0.02, 0.007);
  // frame + drum + barrel
  c.beginPath(); rrP(c, -0.035, -0.065, 0.09, 0.04, 0.012); fo(c, P.brass, LINE.inkThin);
  c.beginPath(); c.ellipse(0.04, -0.045, 0.034, 0.028, 0, 0, TAU); fo(c, P.goldDeep, LINE.inkThin);
  c.strokeStyle = P.ink; c.lineWidth = LINE.hair; c.beginPath(); c.moveTo(0.02, -0.045); c.lineTo(0.06, -0.045); c.moveTo(0.04, -0.07); c.lineTo(0.04, -0.02); c.stroke();
  c.beginPath(); rrP(c, 0.06, -0.06, 0.15, 0.026, 0.01); fo(c, P.gold, LINE.inkThin);
  c.fillStyle = 'rgba(255,255,255,0.6)'; c.fillRect(0.07, -0.056, 0.12, 0.006);
  for (let i = 0; i < 3; i++) { c.fillStyle = P.goldDark; c.fillRect(0.09 + i * 0.04, -0.062, 0.008, 0.03); }
  c.beginPath(); rrP(c, 0.2, -0.066, 0.03, 0.038, 0.008); fo(c, P.goldDeep, LINE.inkThin);
  // hammer + trigger guard
  c.beginPath(); c.moveTo(-0.03, -0.065); c.lineTo(-0.05, -0.085); c.lineTo(-0.035, -0.09); c.lineTo(-0.012, -0.066); c.closePath(); fo(c, P.ironLight, LINE.hair * 1.5);
  c.beginPath(); c.arc(0.02, -0.012, 0.022, 0.2, PI - 0.2); ink(c, LINE.inkThin); c.stroke();
  if (recoil > 0.05) {
    const k = recoil;
    glowU(c, 0.27, -0.047, 0.16 * k + 0.05, P.goldHot, 0.9 * k);
    c.fillStyle = RA('#fff6c8', k); c.beginPath();
    for (let i = 0; i < 10; i++) { const a = i / 10 * TAU, rr = (i % 2 ? 0.035 : 0.11) * (0.6 + k * 0.6); c.lineTo(0.27 + Math.cos(a) * rr * 1.3, -0.047 + Math.sin(a) * rr); }
    c.closePath(); c.fill();
  }
  c.restore();
}
export const drawPistol = guard('drawPistol', function (ctx, x, y, s, st) {
  st = st || {};
  beginU(ctx, x, y, s, st.facing);
  pistolU(ctx, 0, 0, clamp(num(st.glow, 0), 0, 1), num(st.recoil, 0), num(st.t, 0));
  rs(ctx);
});
//>>COIN

//<<PROPS
// ================================================================================================ PROPS: the note, machete, balloon, barrel, the Collector
// ---- the cent note (the lobby): an engraved banknote that flutters. (cx, cy) = centre.
function noteSprite(c) {
  const w = 0.56, h = 0.27;
  c.beginPath(); rrP(c, -w / 2, -h / 2, w, h, 0.02); shadeU(c, -w / 2, -h / 2, w, h, '#efe8c8'); ink(c, LINE.inkThin); c.stroke();
  c.beginPath(); rrP(c, -w / 2 + 0.02, -h / 2 + 0.02, w - 0.04, h - 0.04, 0.012); ink(c, 0.012, '#2f7a4a'); c.stroke();
  // guilloche border
  c.strokeStyle = RA('#2f7a4a', 0.55); c.lineWidth = 0.004;
  for (let i = 0; i < 3; i++) { c.beginPath(); for (let k = 0; k <= 60; k++) { const u = k / 60, xx = -w / 2 + 0.03 + u * (w - 0.06), yy = -h / 2 + 0.035 + Math.sin(u * 40 + i * 2) * 0.008; k ? c.lineTo(xx, yy) : c.moveTo(xx, yy); } c.stroke();
    c.beginPath(); for (let k = 0; k <= 60; k++) { const u = k / 60, xx = -w / 2 + 0.03 + u * (w - 0.06), yy = h / 2 - 0.035 + Math.sin(u * 40 + i * 2) * 0.008; k ? c.lineTo(xx, yy) : c.moveTo(xx, yy); } c.stroke(); }
  // centre vignette: the bank, engraved
  c.beginPath(); c.ellipse(0, 0.0, 0.085, 0.075, 0, 0, TAU); c.fillStyle = '#dcebd2'; c.fill(); ink(c, 0.008, '#2f7a4a'); c.stroke();
  c.fillStyle = '#2f7a4a'; c.beginPath(); c.moveTo(-0.05, 0.045); c.lineTo(0.05, 0.045); c.lineTo(0.05, -0.01); c.lineTo(0.03, -0.01); c.lineTo(0.03, -0.03); c.lineTo(0.0, -0.05); c.lineTo(-0.03, -0.03); c.lineTo(-0.03, -0.01); c.lineTo(-0.05, -0.01); c.closePath(); c.fill();
  c.fillStyle = '#dcebd2'; for (let i = 0; i < 3; i++) c.fillRect(-0.035 + i * 0.03, 0.0, 0.012, 0.04);
  c.fillStyle = RA('#c9a24a', 0.9); c.beginPath(); c.arc(-0.2, 0.0, 0.035, 0, TAU); c.fill(); c.beginPath(); c.arc(0.2, 0.0, 0.035, 0, TAU); c.fill();
}
export const drawNote = guard('drawNote', function (ctx, cx, cy, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const label = st.label == null ? '$0.01' : String(st.label);
  beginU(ctx, cx, cy, s, 1);
  const c = ctx;
  c.rotate(num(st.angle, 0));
  c.fillStyle = 'rgba(0,0,0,0.2)'; c.beginPath(); rrP(c, -0.27, -0.12, 0.56, 0.27, 0.02); c.fill();
  c.translate(-0.01, -0.012);
  // flutter: a slow wave along the note
  const wv = Math.sin(t * 2.6) * 0.04;
  c.transform(1, wv * 0.3, 0, 1 + wv * 0.15, 0, 0);
  sprite(c, 'note', [-0.3, -0.16, 0.6, 0.32], noteSprite);
  textU(c, label, -0.2, 0.0, 0.07, { color: '#2f7a4a', font: FONT.deco });
  textU(c, label, 0.2, 0.0, 0.07, { color: '#2f7a4a', font: FONT.deco });
  textU(c, 'LEDGER STREET', 0, -0.098, 0.03, { color: '#2f7a4a', font: FONT.deco, maxW: 0.36 });
  textU(c, label, 0, 0.098, 0.04, { color: '#2f7a4a', font: FONT.deco });
  rs(ctx);
});

// ---- the machete (the hand on the handle at (x, y)). swing 0..1 = raised behind -> slashed through, with a bullet-time arc
export const drawMachete = guard('drawMachete', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const sw = clamp(num(st.swing, 0), 0, 1);
  const f = st.facing < 0 ? -1 : 1;
  beginU(ctx, x, y, s, f);
  const c = ctx;
  const a0 = -2.2, a1 = 0.7;
  const a = sw > 0 ? lerp(a0, a1, ease(sw)) : -0.5 + Math.sin(t * 1.5) * 0.04;
  if (sw > 0.15 && sw < 0.95) {   // the slash trail
    const k = Math.sin(((sw - 0.15) / 0.8) * PI);
    c.save(); c.globalCompositeOperation = 'lighter';
    c.beginPath(); c.arc(0, 0, 0.5, a - 1.1, a, false); c.arc(0, 0, 0.18, a, a - 1.1, true); c.closePath();
    c.fillStyle = RA('#ffffff', 0.45 * k); c.fill();
    c.restore();
    c.strokeStyle = RA('#e8f6ff', 0.8 * k); c.lineWidth = 0.012; c.beginPath(); c.arc(0, 0, 0.52, a - 0.9, a - 0.05); c.stroke();
  }
  c.save(); c.rotate(a);
  // handle + guard
  c.beginPath(); rrP(c, -0.11, -0.025, 0.13, 0.05, 0.02); fo(c, '#6b3a1e', LINE.inkThin);
  rivetU(c, -0.075, 0, 0.009); rivetU(c, -0.035, 0, 0.009);
  c.beginPath(); rrP(c, 0.015, -0.045, 0.03, 0.09, 0.01); fo(c, P.gold, LINE.inkThin);
  // blade: a broad curve with a gleaming edge
  c.beginPath(); c.moveTo(0.04, -0.03); c.lineTo(0.38, -0.045); c.quadraticCurveTo(0.5, -0.05, 0.52, 0.0); c.quadraticCurveTo(0.45, 0.05, 0.3, 0.05); c.lineTo(0.04, 0.03); c.closePath();
  shadeU(c, 0.04, -0.05, 0.48, 0.1, '#b8c2cc'); ink(c, LINE.inkThin); c.stroke();
  c.strokeStyle = RA('#ffffff', 0.9); c.lineWidth = 0.012; c.beginPath(); c.moveTo(0.06, 0.022); c.lineTo(0.3, 0.04); c.quadraticCurveTo(0.44, 0.04, 0.5, 0.005); c.stroke();
  const gl = Math.pow(Math.max(0, Math.sin(t * 2.4)), 16);
  if (gl > 0.05) glowU(c, 0.3 + gl * 0.1, 0.0, 0.06, '#ffffff', gl);
  c.restore();
  rs(ctx);
});

// ---- the eject balloon: red, patched, the player's own words painted round its belly. (x, y) = the bottom of its rope.
export const drawBalloon = guard('drawBalloon', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const inf = clamp(num(st.inflate, 1), 0, 1);
  const k = 0.3 + 0.7 * ease(inf);
  const words = st.words == null ? '' : String(st.words);
  beginU(ctx, x, y, s, 1);
  const c = ctx;
  const sway = Math.sin(t * 1.3) * 0.04 * inf;
  const cy = -0.55 - 0.42 * k, rx = 0.37 * k, ry = 0.42 * k * (0.75 + 0.25 * inf);
  const ex = sway, droop = (1 - inf) * 0.1;
  // ropes from the grip to the neck ring
  const ny = cy + ry * 0.92 + droop;
  c.strokeStyle = P.ink; c.lineWidth = 0.012;
  for (const dx of [-0.07, 0, 0.07]) { c.beginPath(); c.moveTo(0, 0); c.lineTo(ex + dx * k, ny); c.stroke(); }
  c.beginPath(); c.arc(0, -0.01, 0.025, 0, TAU); ink(c, 0.018, P.brass); c.stroke();
  // envelope (wrinkled when limp)
  c.save(); c.translate(ex, cy);
  const env = () => {
    c.beginPath();
    const n = 28;
    for (let i = 0; i <= n; i++) {
      const a = (i / n) * TAU - PI / 2;
      const wr = 1 + (1 - inf) * 0.08 * Math.sin(a * 7 + t * 2);
      const px = Math.cos(a) * rx * wr, py = Math.sin(a) * ry * wr + (Math.sin(a) > 0 ? Math.sin(a) * ry * 0.12 : 0) + (a > 0 && a < PI ? droop * Math.sin(a) : 0);
      i ? c.lineTo(px, py) : c.moveTo(px, py);
    }
    c.closePath();
  };
  env();
  const g = c.createRadialGradient(-rx * 0.35, -ry * 0.4, 0.02, 0, 0, Math.max(rx, ry) * 1.1);
  g.addColorStop(0, LI(P.crimson, 0.35)); g.addColorStop(0.45, P.crimson); g.addColorStop(1, DK(P.crimson, 0.38));
  c.fillStyle = g; c.fill();
  // patches with stitches
  c.save(); env(); c.clip();
  const patches = [[-0.18, -0.18, 0.12, 0.1, '#b81d2a'], [0.16, 0.08, 0.11, 0.12, '#f05a6a'], [-0.06, 0.22, 0.13, 0.08, '#8e1420'], [0.2, -0.22, 0.08, 0.08, '#d8a0a8']];
  for (const [px, py, pw, ph, pc] of patches) {
    c.save(); c.translate(px * k, py * k); c.rotate(px * 2);
    c.beginPath(); c.rect(-pw * k / 2, -ph * k / 2, pw * k, ph * k); c.fillStyle = pc; c.fill();
    c.setLineDash([0.012, 0.01]); c.strokeStyle = RA('#fff0d8', 0.85); c.lineWidth = 0.006; c.strokeRect(-pw * k / 2 + 0.008, -ph * k / 2 + 0.008, pw * k - 0.016, ph * k - 0.016); c.setLineDash([]);
    c.restore();
  }
  c.restore();
  env(); ink(c); c.stroke();
  c.strokeStyle = RA('#ffffff', 0.6); c.lineWidth = 0.025 * k; c.beginPath(); c.ellipse(-rx * 0.4, -ry * 0.42, rx * 0.25, ry * 0.12, -0.6, 0, TAU); c.stroke();
  // the words, painted across the belly in up to two gently curved lines
  if (words && inf > 0.35) {
    const txt = words.length > 40 ? words.slice(0, 39) + '…' : words;
    let lines = [txt];
    if (txt.length > 13) { const mid = txt.lastIndexOf(' ', Math.ceil(txt.length / 2) + 2); const cut = mid > 2 ? mid : Math.ceil(txt.length / 2); lines = [txt.slice(0, cut).trim(), txt.slice(cut).trim()]; }
    const fs = Math.min(0.1, (rx * 1.45) / Math.max(4, Math.max(...lines.map((l) => l.length))) * 1.7) * (0.55 + 0.45 * inf);
    for (let li = 0; li < lines.length; li++) {
      const L = lines[li], n = L.length, yl = (lines.length === 1 ? 0.02 : (li ? 0.07 : -0.04)) * k;
      const w = Math.min(rx * 1.5, n * fs * 0.62);
      for (let i = 0; i < n; i++) {
        const u = n === 1 ? 0 : i / (n - 1) - 0.5;
        const px = u * w, py = yl + u * u * 0.08 * k;
        textU(c, L[i], px, py, fs, { color: '#fff6e0', font: FONT.deco, rot: -u * 0.35, stroke: '#5a0a10', strokeW: fs * 0.2 });
      }
    }
  }
  // neck + valve ring
  c.beginPath(); rrP(c, -0.05 * k, ry * 0.86 + droop, 0.1 * k, 0.05 * k + 0.01, 0.015); fo(c, P.goldDeep, LINE.inkThin);
  c.restore();
  rs(ctx);
});

// ---- the pickle barrel slammed over the Runner (after a gap through the stop): eyes blink in a knothole, his shoes stick out
export const drawBarrel = guard('drawBarrel', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  beginU(ctx, x, y, s, 1);
  const c = ctx;
  const wob = Math.sin(t * 7) * 0.012 * (frac(t / 4) < 0.25 ? 1 : 0);
  c.fillStyle = 'rgba(0,0,0,0.25)'; c.beginPath(); c.ellipse(0, 0, 0.36, 0.04, 0, 0, TAU); c.fill();
  // shoes sticking out under it
  shoe(c, -0.14, -0.035, 0.0, '#6b4226', false, false);
  c.save(); c.scale(-1, 1); shoe(c, -0.14, -0.035, 0.0, '#6b4226', true, false); c.restore();
  c.save(); c.rotate(wob);
  const top = -0.85, bot = -0.05, w = 0.3;
  c.beginPath(); c.moveTo(-w * 0.9, top); c.quadraticCurveTo(-w * 1.16, (top + bot) / 2, -w * 0.9, bot); c.lineTo(w * 0.9, bot); c.quadraticCurveTo(w * 1.16, (top + bot) / 2, w * 0.9, top); c.closePath();
  shadeU(c, -w * 1.16, top, w * 2.32, bot - top, P.barrel); ink(c); c.stroke();
  c.strokeStyle = RA(P.ink, 0.5); c.lineWidth = LINE.hair * 1.5;
  for (let i = -3; i <= 3; i++) { c.beginPath(); c.moveTo(i * w * 0.26, top + 0.01); c.quadraticCurveTo(i * w * 0.33, (top + bot) / 2, i * w * 0.26, bot - 0.01); c.stroke(); }
  for (const yy of [top + 0.1, (top + bot) / 2, bot - 0.1]) {
    c.beginPath(); c.moveTo(-w * 1.05, yy - 0.025); c.quadraticCurveTo(0, yy + 0.015, w * 1.05, yy - 0.025); c.lineTo(w * 1.05, yy + 0.02); c.quadraticCurveTo(0, yy + 0.06, -w * 1.05, yy + 0.02); c.closePath(); fo(c, P.barrelBand, LINE.inkThin);
    for (const rx of [-0.6, -0.2, 0.2, 0.6]) rivetU(c, rx * w, yy + 0.02, 0.012);
  }
  c.beginPath(); c.ellipse(0, top, w * 0.9, 0.05, 0, 0, TAU); fo(c, DK(P.barrel, 0.15), LINE.inkThin);
  c.strokeStyle = RA(P.ink, 0.4); c.lineWidth = LINE.hair; for (let i = -2; i <= 2; i++) { c.beginPath(); c.moveTo(i * 0.1, top - 0.04); c.lineTo(i * 0.1, top + 0.04); c.stroke(); }
  textU(c, 'PICKLES', 0, -0.33, 0.085, { color: '#3b6e2a', font: FONT.deco, stroke: '#e8d8a8', strokeW: 0.012 });
  // the knothole slit with two eyes
  c.beginPath(); c.ellipse(0.02, -0.6, 0.11, 0.045, 0, 0, TAU); c.fillStyle = '#0c0805'; c.fill(); ink(c, LINE.inkThin); c.stroke();
  const closed = !!st.blink || blinkAt(t, 0.3);
  const look = Math.sin(t * 0.7) * 0.02;
  for (const ex of [-0.025, 0.06]) {
    if (closed) { c.strokeStyle = '#f4f1ea'; c.lineWidth = 0.01; c.beginPath(); c.moveTo(ex - 0.018, -0.6); c.lineTo(ex + 0.018, -0.6); c.stroke(); }
    else { c.fillStyle = '#f4f1ea'; c.beginPath(); c.ellipse(ex, -0.6, 0.02, 0.024, 0, 0, TAU); c.fill(); c.fillStyle = P.ink; c.beginPath(); c.arc(ex + look, -0.598, 0.01, 0, TAU); c.fill(); }
  }
  c.restore();
  rs(ctx);
});

// ---- the Debt Collector: tall, grey, a kind face, a chain and a padlock. chain 0..1 = the chain laid across the street, link by link
export const drawCollector = guard('drawCollector', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const ch = clamp(num(st.chain, 0), 0, 1);
  const f = st.facing < 0 ? -1 : 1;
  beginU(ctx, x, y, s, f);
  const c = ctx;
  const breath = Math.sin(t * TAU * 0.3) * 0.006;
  c.fillStyle = 'rgba(0,0,0,0.2)'; c.beginPath(); c.ellipse(0, 0, 0.26, 0.035, 0, 0, TAU); c.fill();
  // legs + shoes
  for (const [lx, far] of [[-0.06, true], [0.06, false]]) {
    const o = [lx, -0.62, lx + 0.01, -0.32, lx, -0.05];
    limb2(c, o, 0.08, far ? DK('#5d6068', 0.15) : '#5d6068', far ? DK('#5d6068', 0.15) : '#5d6068');
    shoe(c, lx, -0.045, 0, '#2a2622', far, false);
  }
  // the long grey coat
  c.beginPath(); c.moveTo(-0.17, -1.3 + breath); c.lineTo(0.17, -1.3 + breath); c.quadraticCurveTo(0.24, -0.9, 0.22, -0.5); c.lineTo(-0.22, -0.5); c.quadraticCurveTo(-0.24, -0.9, -0.17, -1.3 + breath); c.closePath();
  shadeU(c, -0.24, -1.3, 0.48, 0.8, P.collector); ink(c); c.stroke();
  c.strokeStyle = RA(P.ink, 0.5); c.lineWidth = LINE.hair * 1.5; c.beginPath(); c.moveTo(0.02, -1.25); c.lineTo(0.03, -0.52); c.stroke();
  c.fillStyle = P.ink; for (let i = 0; i < 4; i++) { c.beginPath(); c.arc(0.06, -1.15 + i * 0.12, 0.012, 0, TAU); c.fill(); }
  // lapels + a soft blue tie
  c.beginPath(); c.moveTo(-0.06, -1.3); c.lineTo(0.0, -1.12); c.lineTo(0.06, -1.3); c.closePath(); fo(c, '#f2f0ea', LINE.inkThin);
  c.beginPath(); c.moveTo(-0.018, -1.29); c.lineTo(0.018, -1.29); c.lineTo(0.012, -1.16); c.lineTo(0.0, -1.13); c.lineTo(-0.012, -1.16); c.closePath(); fo(c, '#7aa6d6', LINE.hair * 1.5);
  // the ledger under the far arm
  c.beginPath(); rrP(c, -0.25, -1.05, 0.12, 0.2, 0.012); fo(c, '#6b3a1e', LINE.inkThin); c.fillStyle = '#efe6c8'; c.fillRect(-0.24, -1.04, 0.012, 0.18);
  limb2(c, [-0.15, -1.25, -0.22, -1.02, -0.12, -0.9], 0.075, DK(P.collector, 0.12), DK(P.collector, 0.12));
  c.beginPath(); c.arc(-0.12, -0.9, 0.04, 0, TAU); fo(c, P.skin, LINE.inkThin);
  // the near arm holding the chain
  const hx = 0.24, hy = -0.86;
  limb2(c, [0.15, -1.25, 0.24, -1.05, hx, hy], 0.075, P.collector, P.collector);
  // the chain: links laid one at a time toward the street, a padlock at the end
  const nL = Math.round(ch * 18);
  let px = hx, py = hy, lastX = hx, lastY = hy;
  for (let i = 0; i < nL; i++) {
    const u = (i + 1) / 18;
    const lx = hx + 0.03 + i * 0.09, ly = hy + 0.25 * Math.sin(Math.min(1, u * 2.2) * PI * 0.5) + Math.sin(i * 0.7) * 0.004;
    c.save(); c.translate((px + lx) / 2, (py + ly) / 2); c.rotate(Math.atan2(ly - py, lx - px));
    c.beginPath(); c.ellipse(0, 0, 0.055, i % 2 ? 0.014 : 0.03, 0, 0, TAU);
    ink(c, 0.028); c.stroke(); ink(c, 0.014, i % 2 ? '#8d939c' : '#b4bac4'); c.stroke();
    c.restore();
    px = lx; py = ly; lastX = lx; lastY = ly;
  }
  if (nL > 0) {
    c.beginPath(); c.arc(lastX + 0.05, lastY + 0.02, 0.035, PI, 0); ink(c, 0.03); c.stroke(); ink(c, 0.014, '#b4bac4'); c.stroke();
    c.beginPath(); rrP(c, lastX + 0.0, lastY + 0.02, 0.1, 0.09, 0.015); shadeU(c, lastX, lastY + 0.02, 0.1, 0.09, P.brass); ink(c, LINE.inkThin); c.stroke();
    c.fillStyle = P.ink; c.beginPath(); c.arc(lastX + 0.05, lastY + 0.06, 0.012, 0, TAU); c.fill(); c.fillRect(lastX + 0.046, lastY + 0.06, 0.008, 0.02);
    if (ch > 0.97) {   // the sign he hangs: see you tomorrow
      const sx = lastX + 0.05, sy = lastY + 0.12;
      c.strokeStyle = P.ink; c.lineWidth = 0.008; c.beginPath(); c.moveTo(sx, sy - 0.01); c.lineTo(sx - 0.26, sy + 0.05); c.moveTo(sx, sy - 0.01); c.lineTo(sx + 0.26, sy + 0.05); c.stroke();
      c.save(); c.translate(sx, sy + 0.12); c.rotate(Math.sin(t * 1.2) * 0.04);
      c.beginPath(); rrP(c, -0.36, -0.08, 0.72, 0.2, 0.02); shadeU(c, -0.36, -0.08, 0.72, 0.2, P.wood); ink(c, LINE.inkThin); c.stroke();
      textU(c, 'see you tomorrow', 0, 0.022, 0.085, { color: P.ink, font: FONT.deco, weight: 'italic bold', maxW: 0.66 });
      c.restore();
    }
  }
  c.beginPath(); c.arc(hx, hy, 0.042, 0, TAU); fo(c, P.skin, LINE.inkThin);
  // the head: a long kind face, round spectacles, a white moustache, a grey bowler
  c.save(); c.translate(0.02, -1.44 + breath); c.rotate(Math.sin(t * 0.6) * 0.03);
  c.beginPath(); c.ellipse(0, 0, 0.11, 0.135, 0, 0, TAU); c.fillStyle = '#efc79a'; c.fill();
  c.fillStyle = '#d8a878'; c.beginPath(); c.ellipse(0.04, 0.03, 0.07, 0.1, 0.3, -0.6, 1.8); c.fill();
  c.beginPath(); c.ellipse(0, 0, 0.11, 0.135, 0, 0, TAU); ink(c); c.stroke();
  c.beginPath(); c.ellipse(-0.105, 0.0, 0.025, 0.04, 0, 0, TAU); fo(c, '#efc79a', LINE.inkThin);
  c.fillStyle = RA(P.blush, 0.55); c.beginPath(); c.ellipse(0.04, 0.045, 0.03, 0.016, 0, 0, TAU); c.fill(); c.beginPath(); c.ellipse(-0.05, 0.045, 0.025, 0.014, 0, 0, TAU); c.fill();
  const bl = blinkAt(t, 0.66);
  for (const ex of [-0.035, 0.045]) {
    c.beginPath(); c.arc(ex, -0.01, 0.034, 0, TAU); ink(c, 0.012, '#c9a24a'); c.stroke();
    c.fillStyle = RA('#ffffff', 0.25); c.beginPath(); c.arc(ex, -0.01, 0.032, 0, TAU); c.fill();
    if (bl) { c.strokeStyle = P.ink; c.lineWidth = LINE.hair * 1.5; c.beginPath(); c.moveTo(ex - 0.014, -0.008); c.lineTo(ex + 0.014, -0.008); c.stroke(); }
    else { c.strokeStyle = P.ink; c.lineWidth = LINE.hair * 1.6; c.beginPath(); c.arc(ex, -0.004, 0.013, PI * 1.15, PI * 1.85); c.stroke(); }   // gentle upturned eyes
  }
  c.strokeStyle = '#c9a24a'; c.lineWidth = 0.008; c.beginPath(); c.moveTo(-0.001, -0.012); c.lineTo(0.011, -0.012); c.stroke();
  c.strokeStyle = '#d9dde3'; c.lineWidth = 0.016; c.beginPath(); c.moveTo(-0.07, -0.06); c.lineTo(-0.01, -0.055); c.moveTo(0.02, -0.055); c.lineTo(0.08, -0.06); c.stroke();
  c.beginPath(); c.ellipse(0.02, 0.03, 0.022, 0.03, 0, 0, TAU); fo(c, '#e9b98a', LINE.hair * 1.5);
  c.beginPath(); c.moveTo(0.02, 0.055); c.quadraticCurveTo(-0.03, 0.05, -0.065, 0.075); c.quadraticCurveTo(-0.02, 0.09, 0.02, 0.075); c.quadraticCurveTo(0.06, 0.09, 0.1, 0.075); c.quadraticCurveTo(0.07, 0.05, 0.02, 0.055); c.closePath(); fo(c, '#eef0f2', LINE.hair * 1.5);
  c.strokeStyle = P.ink; c.lineWidth = LINE.hair * 1.5; c.beginPath(); c.arc(0.02, 0.07, 0.03, 0.4, 2.7); c.stroke();
  // bowler
  c.beginPath(); c.ellipse(0, -0.1, 0.15, 0.03, 0, 0, TAU); fo(c, '#6d7078');
  c.beginPath(); c.moveTo(-0.1, -0.1); c.quadraticCurveTo(-0.11, -0.24, 0.0, -0.245); c.quadraticCurveTo(0.11, -0.24, 0.1, -0.1); c.closePath(); shadeU(c, -0.11, -0.25, 0.22, 0.15, '#7d8088'); ink(c); c.stroke();
  c.beginPath(); c.rect(-0.1, -0.13, 0.2, 0.025); fo(c, '#4a4d55', LINE.hair * 1.5);
  c.restore();
  rs(ctx);
});
//>>PROPS

//<<LOBBY
// ================================================================================================ THE LOBBY DESK
// ---- the mouse jar: a mason jar of metal shavings (every cent the rat ever took). fill 0..1
function jarGlass(c) {
  c.beginPath(); c.moveTo(-0.14, -0.4); c.quadraticCurveTo(-0.17, -0.38, -0.17, -0.32); c.lineTo(-0.17, -0.05); c.quadraticCurveTo(-0.17, 0, -0.12, 0); c.lineTo(0.12, 0); c.quadraticCurveTo(0.17, 0, 0.17, -0.05); c.lineTo(0.17, -0.32); c.quadraticCurveTo(0.17, -0.38, 0.14, -0.4); c.closePath();
}
export const drawJar = guard('drawJar', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const fl = clamp(num(st.fill, 0), 0, 1);
  beginU(ctx, x, y, s, 1);
  const c = ctx;
  c.fillStyle = 'rgba(0,0,0,0.2)'; c.beginPath(); c.ellipse(0, 0, 0.2, 0.03, 0, 0, TAU); c.fill();
  jarGlass(c); c.fillStyle = 'rgba(190,230,240,0.22)'; c.fill();
  // the shavings pile
  if (fl > 0.005) {
    const top = -0.02 - fl * 0.34;
    c.save(); jarGlass(c); c.clip();
    c.beginPath(); c.moveTo(-0.18, 0.01); c.lineTo(-0.18, top + 0.03); c.quadraticCurveTo(0, top - 0.04, 0.18, top + 0.03); c.lineTo(0.18, 0.01); c.closePath(); c.fillStyle = '#9aa2ac'; c.fill();
    for (let i = 0; i < 60; i++) {
      const px = -0.16 + rand(i * 3.3) * 0.32, py = top + 0.02 + rand(i * 7.1) * (0.02 - top);
      c.save(); c.translate(px, py); c.rotate(rand(i) * PI);
      c.fillStyle = i % 4 === 0 ? P.brass : i % 3 === 0 ? '#e8edf2' : '#bcc4ce'; c.fillRect(-0.014, -0.003, 0.028, 0.006);
      c.restore();
    }
    for (let i = 0; i < 3; i++) { const tw = Math.pow(Math.max(0, Math.sin(t * 2 + i * 2.1)), 12); if (tw > 0.1) glowU(c, -0.1 + i * 0.1, top + 0.04 + i * 0.03, 0.04, '#ffffff', tw); }
    c.restore();
  }
  // glass edges + highlight, the label with a rat, the lid
  jarGlass(c); ink(c, LINE.inkThin); c.stroke();
  c.strokeStyle = 'rgba(255,255,255,0.7)'; c.lineWidth = 0.02; c.beginPath(); c.moveTo(-0.12, -0.33); c.lineTo(-0.12, -0.06); c.stroke();
  c.strokeStyle = 'rgba(255,255,255,0.35)'; c.lineWidth = 0.008; c.beginPath(); c.moveTo(0.13, -0.3); c.lineTo(0.13, -0.08); c.stroke();
  c.beginPath(); rrP(c, -0.11, -0.2, 0.22, 0.1, 0.012); fo(c, '#f3e6c4', LINE.hair * 1.5);
  c.fillStyle = P.brassDark; c.beginPath(); c.ellipse(-0.04, -0.15, 0.03, 0.017, 0, 0, TAU); c.fill(); c.beginPath(); c.arc(-0.012, -0.157, 0.012, 0, TAU); c.fill();
  c.strokeStyle = P.brassDark; c.lineWidth = 0.006; c.beginPath(); c.moveTo(-0.07, -0.15); c.quadraticCurveTo(-0.09, -0.17, -0.095, -0.14); c.stroke();
  textU(c, 'COSTS', 0.045, -0.148, 0.032, { color: '#7a2a20', font: FONT.deco });
  c.beginPath(); rrP(c, -0.15, -0.47, 0.3, 0.08, 0.015); shadeU(c, -0.15, -0.47, 0.3, 0.08, P.brass); ink(c, LINE.inkThin); c.stroke();
  c.strokeStyle = RA(P.brassDark, 0.9); c.lineWidth = 0.008; for (let i = 0; i < 6; i++) { c.beginPath(); c.moveTo(-0.12 + i * 0.05, -0.46); c.lineTo(-0.12 + i * 0.05, -0.4); c.stroke(); }
  rs(ctx);
});

// ---- the radio (the calendar's storms): a 1920s cathedral set; on = lit dial, crackle = static, text = a ticker tape strip
function radioSprite(c) {
  c.beginPath(); c.moveTo(-0.22, 0); c.lineTo(-0.22, -0.3); c.bezierCurveTo(-0.22, -0.55, 0.22, -0.55, 0.22, -0.3); c.lineTo(0.22, 0); c.closePath();
  shadeU(c, -0.22, -0.55, 0.44, 0.55, '#8a5530'); ink(c); c.stroke();
  c.beginPath(); c.moveTo(-0.16, -0.12); c.lineTo(-0.16, -0.3); c.bezierCurveTo(-0.16, -0.47, 0.16, -0.47, 0.16, -0.3); c.lineTo(0.16, -0.12); c.closePath(); c.fillStyle = '#c8a46a'; c.fill(); ink(c, LINE.inkThin); c.stroke();
  // sunburst fretwork over the cloth
  c.save(); c.clip();
  c.strokeStyle = '#6b3d1e'; c.lineWidth = 0.022;
  for (let i = 0; i <= 6; i++) { const a = PI + (i / 6) * PI; c.beginPath(); c.moveTo(0, -0.14); c.lineTo(Math.cos(a) * 0.3, -0.14 + Math.sin(a) * 0.3); c.stroke(); }
  c.beginPath(); c.arc(0, -0.14, 0.12, PI, TAU); c.stroke();
  c.restore();
  c.strokeStyle = RA('#ffffff', 0.2); c.lineWidth = 0.012; c.beginPath(); c.moveTo(-0.19, -0.05); c.lineTo(-0.19, -0.3); c.bezierCurveTo(-0.19, -0.45, -0.1, -0.5, 0.0, -0.51); c.stroke();
  c.beginPath(); c.rect(-0.21, -0.03, 0.42, 0.03); fo(c, '#5a3418', LINE.inkThin);
  for (const kx of [-0.13, 0.13]) { c.beginPath(); c.arc(kx, -0.07, 0.025, 0, TAU); fo(c, P.brass, LINE.hair * 1.5); }
}
export const drawRadio = guard('drawRadio', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const on = !!st.on, cr = clamp(num(st.crackle, 0), 0, 1);
  beginU(ctx, x, y, s, 1);
  const c = ctx;
  c.fillStyle = 'rgba(0,0,0,0.2)'; c.beginPath(); c.ellipse(0, 0, 0.25, 0.03, 0, 0, TAU); c.fill();
  const jit = cr > 0 ? Math.sin(t * 60) * 0.004 * cr : 0;
  c.save(); c.translate(jit, 0);
  sprite(c, 'radio', [-0.25, -0.58, 0.5, 0.6], radioSprite);
  // the dial window
  c.beginPath(); c.ellipse(0, -0.075, 0.055, 0.03, 0, 0, TAU); fo(c, on ? '#ffd27a' : '#4a3a28', LINE.hair * 1.5);
  if (on) { const nd = 0.4 + Math.sin(t * 0.3) * 0.2; c.strokeStyle = P.crimson; c.lineWidth = 0.006; c.beginPath(); c.moveTo(0, -0.05); c.lineTo(Math.cos(PI + nd * PI) * 0.045, -0.05 + Math.sin(PI + nd * PI) * 0.03); c.stroke(); glowU(c, 0, -0.075, 0.12, '#ffb84a', 0.5); }
  if (on && cr > 0.02) {   // static: zigzag sparks over the grille
    c.strokeStyle = RA(P.lightning, cr); c.lineWidth = 0.012;
    for (let i = 0; i < 3; i++) { if (frac(t * 7 + i * 0.37) > 0.6) continue; const bx = -0.1 + i * 0.1; c.beginPath(); c.moveTo(bx, -0.45); c.lineTo(bx + 0.03, -0.5); c.lineTo(bx - 0.01, -0.53); c.lineTo(bx + 0.04, -0.6); c.stroke(); }
    glowU(c, 0, -0.5, 0.15, P.lightning, 0.3 * cr);
  }
  c.restore();
  // the ticker tape curling out of the slot on top
  if (st.text) {
    const txt = String(st.text);
    const L = Math.min(1.1, 0.07 * txt.length + 0.12);
    c.save(); c.translate(0.02, -0.53); c.rotate(-0.25 + Math.sin(t * 1.4) * 0.03);
    c.beginPath(); c.moveTo(0, 0); c.lineTo(L, -0.05); c.quadraticCurveTo(L + 0.08, -0.06, L + 0.1, -0.01); c.lineTo(L + 0.08, 0.04); c.quadraticCurveTo(L + 0.06, 0.0, L, 0.015); c.lineTo(0, 0.065); c.closePath();
    fo(c, P.ticker, LINE.hair * 1.5);
    c.save(); c.transform(1, -0.05 / L, 0, 1, 0, 0);
    textU(c, txt, L / 2 + 0.005, 0.035, 0.05, { color: '#3a2a1a', font: FONT.sign, maxW: L - 0.04 });
    c.restore();
    c.restore();
  }
  rs(ctx);
});

// ---- the Buyer's cabinet: every coin he ever paid for, on little stands behind glass
function cabinetSprite(c) {
  c.beginPath(); c.rect(-0.38, -1.1, 0.76, 1.1); shadeU(c, -0.38, -1.1, 0.76, 1.1, '#6b3a1e'); ink(c); c.stroke();
  c.beginPath(); c.moveTo(-0.42, -1.1); c.lineTo(0.42, -1.1); c.lineTo(0.36, -1.2); c.lineTo(-0.36, -1.2); c.closePath(); fo(c, P.gold, LINE.inkThin);
  c.beginPath(); c.moveTo(-0.12, -1.2); c.lineTo(0, -1.28); c.lineTo(0.12, -1.2); c.closePath(); fo(c, P.goldDeep, LINE.inkThin);
  c.beginPath(); c.rect(-0.32, -1.04, 0.64, 0.9); c.fillStyle = '#1a120c'; c.fill(); ink(c, LINE.inkThin); c.stroke();
  for (let i = 0; i < 3; i++) { const sy = -0.78 + i * 0.28; c.beginPath(); c.rect(-0.32, sy, 0.64, 0.025); fo(c, '#8a5a2b', LINE.hair * 1.5); }
  c.beginPath(); c.rect(-0.4, -0.12, 0.8, 0.12); shadeU(c, -0.4, -0.12, 0.8, 0.12, '#5a3418'); ink(c, LINE.inkThin); c.stroke();
  c.beginPath(); c.arc(0.0, -0.06, 0.025, 0, TAU); fo(c, P.brass, LINE.hair * 1.5);
}
export const drawCabinet = guard('drawCabinet', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const n = Math.max(0, Math.floor(num(st.coins, 0)));
  beginU(ctx, x, y, s, 1);
  const c = ctx;
  c.fillStyle = 'rgba(0,0,0,0.2)'; c.beginPath(); c.ellipse(0, 0, 0.44, 0.04, 0, 0, TAU); c.fill();
  sprite(c, 'cabinet', [-0.44, -1.3, 0.88, 1.32], cabinetSprite);
  const shown = Math.min(n, 15);
  for (let i = 0; i < shown; i++) {
    const row = Math.floor(i / 5), col = i % 5;
    const cx = -0.24 + col * 0.12, sy = -0.78 + row * 0.28 - 0.002;
    c.beginPath(); c.moveTo(cx - 0.02, sy); c.lineTo(cx + 0.02, sy); c.lineTo(cx, sy - 0.03); c.closePath(); c.fillStyle = P.brassDark; c.fill();
    coinU(c, cx, sy - 0.075, 0.045, { glow: 0, t, spin: 0 }, LINE.hair * 1.4);
  }
  if (n > 15) { c.beginPath(); rrP(c, -0.1, -0.2, 0.2, 0.06, 0.01); fo(c, P.gold, LINE.hair * 1.5); textU(c, '+' + (n - 15), 0, -0.168, 0.04, { color: P.ink, font: FONT.deco }); }
  // glass with a moving reflection
  c.save(); c.beginPath(); c.rect(-0.32, -1.04, 0.64, 0.9); c.clip();
  c.fillStyle = 'rgba(200,230,255,0.08)'; c.fillRect(-0.32, -1.04, 0.64, 0.9);
  const rx = -0.6 + frac(t * 0.08) * 1.4;
  c.fillStyle = 'rgba(255,255,255,0.18)'; c.beginPath(); c.moveTo(rx, -1.04); c.lineTo(rx + 0.1, -1.04); c.lineTo(rx - 0.2, -0.14); c.lineTo(rx - 0.3, -0.14); c.closePath(); c.fill();
  c.restore();
  c.strokeStyle = P.gold; c.lineWidth = 0.014; c.beginPath(); c.moveTo(0, -1.04); c.lineTo(0, -0.14); c.stroke();
  rs(ctx);
});

// ---- the trophy shelf (discipline trophies only): a cup, a medal, a statuette, a plaque or a star per key
function hashKey(k) { let h = 7; const s = String(k || ''); for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0; return h; }
function trophy(c, kind, t, glintPh) {
  if (kind === 0) {   // loving cup
    c.beginPath(); c.moveTo(-0.07, -0.26); c.lineTo(0.07, -0.26); c.quadraticCurveTo(0.07, -0.13, 0.0, -0.11); c.quadraticCurveTo(-0.07, -0.13, -0.07, -0.26); c.closePath(); shadeU(c, -0.07, -0.26, 0.14, 0.15, P.gold); ink(c, LINE.inkThin); c.stroke();
    for (const sx of [-1, 1]) { c.beginPath(); c.arc(sx * 0.08, -0.21, 0.03, sx > 0 ? -1.4 : 1.7, sx > 0 ? 1.4 : 4.6); ink(c, 0.024); c.stroke(); ink(c, 0.012, P.gold); c.stroke(); }
    c.beginPath(); c.rect(-0.012, -0.11, 0.024, 0.05); fo(c, P.goldDeep, LINE.hair * 1.5);
    c.beginPath(); rrP(c, -0.05, -0.065, 0.1, 0.065, 0.01); fo(c, '#3b2a1e', LINE.inkThin);
  } else if (kind === 1) {   // medal on a ribbon
    c.beginPath(); c.moveTo(-0.04, -0.27); c.lineTo(0.0, -0.15); c.lineTo(0.04, -0.27); c.closePath(); fo(c, P.crimson, LINE.hair * 1.5);
    c.beginPath(); c.moveTo(-0.015, -0.27); c.lineTo(0.0, -0.2); c.lineTo(0.015, -0.27); c.closePath(); c.fillStyle = '#ffffff'; c.fill();
    c.beginPath(); c.arc(0, -0.11, 0.05, 0, TAU); shadeU(c, -0.05, -0.16, 0.1, 0.1, P.gold); ink(c, LINE.inkThin); c.stroke();
    c.beginPath(); for (let i = 0; i < 10; i++) { const a = -PI / 2 + i * PI / 5, rr = i % 2 ? 0.014 : 0.032; c.lineTo(Math.cos(a) * rr, -0.11 + Math.sin(a) * rr); } c.closePath(); c.fillStyle = P.goldDeep; c.fill();
    c.beginPath(); rrP(c, -0.05, -0.05, 0.1, 0.05, 0.01); fo(c, '#3b2a1e', LINE.inkThin);
  } else if (kind === 2) {   // a little gold runner on a plinth
    c.beginPath(); rrP(c, -0.055, -0.07, 0.11, 0.07, 0.01); fo(c, '#3b2a1e', LINE.inkThin);
    c.fillStyle = P.gold; c.strokeStyle = P.ink; c.lineWidth = LINE.hair * 1.5;
    c.beginPath(); c.arc(0.01, -0.235, 0.022, 0, TAU); c.fill(); c.stroke();
    c.lineCap = 'round'; c.strokeStyle = P.ink; c.lineWidth = 0.03;
    c.beginPath(); c.moveTo(0.005, -0.21); c.lineTo(-0.005, -0.14); c.moveTo(-0.005, -0.14); c.lineTo(0.03, -0.1); c.lineTo(0.02, -0.07); c.moveTo(-0.005, -0.14); c.lineTo(-0.03, -0.1); c.lineTo(-0.05, -0.08); c.moveTo(0.0, -0.195); c.lineTo(0.04, -0.17); c.moveTo(0.0, -0.195); c.lineTo(-0.035, -0.18); c.stroke();
    c.strokeStyle = P.gold; c.lineWidth = 0.016; c.stroke();
  } else if (kind === 3) {   // a plaque
    c.beginPath(); rrP(c, -0.08, -0.22, 0.16, 0.22, 0.02); shadeU(c, -0.08, -0.22, 0.16, 0.22, '#7a4a22'); ink(c, LINE.inkThin); c.stroke();
    c.beginPath(); rrP(c, -0.055, -0.16, 0.11, 0.08, 0.01); fo(c, P.gold, LINE.hair * 1.5);
    c.strokeStyle = P.goldDark; c.lineWidth = 0.006; c.beginPath(); c.moveTo(-0.04, -0.13); c.lineTo(0.04, -0.13); c.moveTo(-0.04, -0.11); c.lineTo(0.03, -0.11); c.stroke();
  } else {   // a star on a stand
    c.beginPath(); c.rect(-0.01, -0.12, 0.02, 0.07); fo(c, P.goldDeep, LINE.hair * 1.5);
    c.beginPath(); for (let i = 0; i < 10; i++) { const a = -PI / 2 + i * PI / 5, rr = i % 2 ? 0.035 : 0.08; c.lineTo(Math.cos(a) * rr, -0.19 + Math.sin(a) * rr); } c.closePath(); shadeU(c, -0.08, -0.27, 0.16, 0.16, P.gold); ink(c, LINE.inkThin); c.stroke();
    c.beginPath(); rrP(c, -0.05, -0.05, 0.1, 0.05, 0.01); fo(c, '#3b2a1e', LINE.inkThin);
  }
  const gl = Math.pow(Math.max(0, Math.sin(t * 1.5 + glintPh)), 14);
  if (gl > 0.05) glowU(c, -0.03, -0.2, 0.05, '#ffffff', gl);
}
export const drawTrophyShelf = guard('drawTrophyShelf', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const list = Array.isArray(st.trophies) ? st.trophies.slice(0, 8) : [];
  beginU(ctx, x, y, s, 1);
  const c = ctx;
  // brackets + the plank
  for (const bx of [-0.55, 0.55]) { c.beginPath(); c.moveTo(bx - 0.03, 0); c.lineTo(bx + 0.03, 0); c.lineTo(bx + 0.03, 0.04); c.quadraticCurveTo(bx + 0.03, 0.14, bx - 0.03, 0.16); c.closePath(); fo(c, P.brassDark, LINE.inkThin); }
  c.beginPath(); rrP(c, -0.72, -0.01, 1.44, 0.06, 0.012); shadeU(c, -0.72, -0.01, 1.44, 0.06, '#8a5530'); ink(c, LINE.inkThin); c.stroke();
  c.fillStyle = P.gold; c.fillRect(-0.72, 0.035, 1.44, 0.01);
  const n = list.length;
  for (let i = 0; i < n; i++) {
    const tr = list[i] || {};
    const px = n === 1 ? 0 : -0.58 + (1.16 * i) / (n - 1);
    c.save(); c.translate(px, -0.01);
    trophy(c, hashKey(tr.key) % 5, t, i * 1.7);
    c.restore();
    if (tr.title) textU(c, String(tr.title), px, 0.022, 0.026, { color: '#fff6cf', font: FONT.deco, maxW: Math.min(0.3, 1.3 / Math.max(1, n)) });
  }
  if (!n) { c.strokeStyle = RA('#fff6cf', 0.25); c.setLineDash([0.02, 0.02]); c.lineWidth = 0.008; for (let i = 0; i < 4; i++) { c.beginPath(); c.rect(-0.55 + i * 0.36, -0.22, 0.14, 0.2); c.stroke(); } c.setLineDash([]); }
  rs(ctx);
});

// ---- the balance as a stack of coins with a paper tag
function fmtUsd(u) { if (!isFinite(u)) return ''; if (Math.abs(u) < 1) { const [w, f] = Math.abs(u).toFixed(4).replace(/0+$/, '').split('.'); return (u < 0 ? '-$' : '$') + w + '.' + (f || '').padEnd(2, '0'); } return '$' + u.toFixed(2); }
export const drawCoinStack = guard('drawCoinStack', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const usd = Math.max(0, num(st.usd, 0));
  const n = clamp(Math.round(1 + 3.2 * Math.log10(1 + usd * 100)), usd > 0 ? 1 : 0, 18);
  beginU(ctx, x, y, s, 1);
  const c = ctx;
  c.fillStyle = 'rgba(0,0,0,0.22)'; c.beginPath(); c.ellipse(0, 0, 0.17, 0.035, 0, 0, TAU); c.fill();
  const th = 0.03;
  for (let i = 0; i < n; i++) {
    const jx = (rand(i * 9.1) - 0.5) * 0.025, yy = -i * th - th / 2;
    c.beginPath(); c.ellipse(jx, yy + th * 0.3, 0.13, 0.035, 0, 0, PI); c.lineTo(jx - 0.13, yy - th * 0.2); c.ellipse(jx, yy - th * 0.2, 0.13, 0.035, 0, PI, 0, true); c.closePath();
    c.fillStyle = '#e0a82a'; c.fill(); ink(c, LINE.hair); c.stroke();
    c.strokeStyle = RA(P.goldDark, 0.55); c.lineWidth = 0.004; for (let k = -4; k <= 4; k++) { c.beginPath(); c.moveTo(jx + k * 0.028, yy + th * 0.25); c.lineTo(jx + k * 0.028, yy - th * 0.12); c.stroke(); }
    c.fillStyle = RA('#fff2b0', 0.5); c.fillRect(jx - 0.11, yy - th * 0.05, 0.05, th * 0.25);
    c.beginPath(); c.ellipse(jx, yy - th * 0.2, 0.13, 0.035, 0, 0, TAU); c.fillStyle = i === n - 1 ? P.goldHot : P.gold; c.fill(); ink(c, LINE.hair); c.stroke();
  }
  if (n > 0) {
    const ty = -n * th - th * 0.2;
    c.beginPath(); c.ellipse(0, ty, 0.09, 0.022, 0, 0, TAU); ink(c, 0.006, P.goldDeep); c.stroke();
    const gl = Math.pow(Math.max(0, Math.sin(t * 1.3)), 10);
    if (gl > 0.05) glowU(c, -0.05, ty - 0.005, 0.06, '#ffffff', gl);
  }
  // the tag on a string (st.noTag: the caller shows the purse on its own, bigger plate)
  if (!st.noTag) {
    c.strokeStyle = P.ink; c.lineWidth = 0.008; c.beginPath(); c.moveTo(0.1, -n * th * 0.6); c.quadraticCurveTo(0.17, -n * th * 0.5, 0.2, -0.05); c.stroke();
    c.save(); c.translate(0.2, -0.05); c.rotate(0.15 + Math.sin(t * 1.7) * 0.04);
    c.beginPath(); c.moveTo(-0.02, 0); c.lineTo(0.2, 0); c.lineTo(0.2, 0.09); c.lineTo(-0.02, 0.09); c.lineTo(-0.04, 0.045); c.closePath(); fo(c, '#fbf1d6', LINE.hair * 1.5);
    textU(c, fmtUsd(usd), 0.09, 0.047, 0.055, { color: P.ink, font: FONT.deco, maxW: 0.2 });
    c.restore();
  }
  rs(ctx);
});

// ---- the page corner (flip to the mirror world): a dog-ear at the bottom-right of the page, curling up to show its back
export const drawPageCorner = guard('drawPageCorner', function (ctx, x, y, s, st) {
  st = st || {};
  const t = num(st.t, 0);
  const k = (st.hover ? 0.66 : 0.48) + Math.sin(t * 2) * 0.015;
  const lift = st.hover ? 0.1 : 0.05;
  beginU(ctx, x, y, s, 1);
  const c = ctx;
  // where the corner was: a peek of the mirror world under the page (night blue with a gold glint)
  c.beginPath(); c.moveTo(0, 0); c.lineTo(-k, 0); c.lineTo(0, -k); c.closePath();
  c.fillStyle = '#1b2244'; c.fill();
  c.save(); c.clip(); glowU(c, -k * 0.2, -k * 0.2, k * 0.5, P.gold, 0.35); c.restore();
  // the soft shadow of the lifted flap
  c.fillStyle = 'rgba(0,0,0,0.3)'; c.beginPath(); c.moveTo(-k - 0.03, 0.0); c.lineTo(0.0, -k - 0.03); c.lineTo(-k * 0.95 - lift, -k * 0.95 - lift * 0.4); c.closePath(); c.fill();
  // the folded-back flap: the back of the page (a little darker, printed in reverse), curling at its tip
  const tx = -k - lift, ty = -k - lift * 0.3;
  c.beginPath(); c.moveTo(-k, 0); c.quadraticCurveTo(-k * 1.02 - lift * 0.5, -k * 0.55, tx, ty); c.quadraticCurveTo(-k * 0.55, -k * 1.02 - lift * 0.5, 0, -k); c.closePath();
  shadeU(c, -k - lift, -k - lift, k + lift, k + lift, '#e9dfc4'); ink(c, LINE.inkThin); c.stroke();
  c.save(); c.clip();
  c.strokeStyle = RA('#6b5a3a', 0.3); c.lineWidth = 0.008;
  for (let i = 1; i < 7; i++) { const u = i / 7; c.beginPath(); c.moveTo(-k * (1 - u * 0.15) + 0.02, -k * u); c.lineTo(-k * u, -k * (1 - u * 0.15) + 0.02); c.stroke(); }
  c.restore();
  // the fold line + a printed arrow: turn the page
  c.strokeStyle = RA('#ffffff', 0.7); c.lineWidth = 0.012; c.beginPath(); c.moveTo(-k + 0.01, -0.01); c.lineTo(-0.01, -k + 0.01); c.stroke();
  c.save(); c.translate(-k * 0.62, -k * 0.62);
  c.strokeStyle = P.crimson; c.lineWidth = 0.024; c.beginPath(); c.arc(0, 0, k * 0.17, -2.4, 0.9); c.stroke();
  const ax = Math.cos(0.9) * k * 0.17, ay = Math.sin(0.9) * k * 0.17;
  c.fillStyle = P.crimson; c.beginPath(); c.moveTo(ax + 0.035, ay - 0.012); c.lineTo(ax - 0.022, ay + 0.04); c.lineTo(ax - 0.03, ay - 0.032); c.closePath(); c.fill();
  c.restore();
  rs(ctx);
});

// ---- the hold-to-confirm ring: a brass gauge whose dial fills clockwise (cx, cy, r in px); label on a brass plate below
export const drawHoldRing = guard('drawHoldRing', function (ctx, cx, cy, r, frac0, st) {
  st = st || {};
  r = num(r, 30);
  if (!(r > 1)) return;
  const fr = clamp(num(frac0, 0), 0, 1);
  const col = st.color || P.gold;
  sv(ctx);
  ctx.translate(cx, cy); ctx.scale(r, r); ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  const c = ctx;
  const iw = Math.max(1.5 / r, 0.07);
  c.beginPath(); c.arc(0, 0, 1.12, 0, TAU); c.fillStyle = 'rgba(20,14,8,0.55)'; c.fill();
  c.beginPath(); c.arc(0, 0, 1.12, 0, TAU); ink(c, iw); c.stroke();
  c.beginPath(); c.arc(0, 0, 1.0, 0, TAU); ink(c, 0.2, P.ink); c.stroke(); ink(c, 0.13, P.brass); c.stroke();
  c.strokeStyle = P.brassLight; c.lineWidth = 0.04; c.beginPath(); c.arc(0, 0, 1.0, PI * 1.05, PI * 1.6); c.stroke();
  for (let i = 0; i < 12; i++) { const a = -PI / 2 + (i / 12) * TAU; c.strokeStyle = i / 12 < fr ? col : RA('#fff6cf', 0.45); c.lineWidth = 0.06; c.beginPath(); c.moveTo(Math.cos(a) * 0.72, Math.sin(a) * 0.72); c.lineTo(Math.cos(a) * 0.84, Math.sin(a) * 0.84); c.stroke(); }
  if (fr > 0) {
    c.save(); c.globalCompositeOperation = 'lighter';
    c.strokeStyle = RA(col, 0.35); c.lineWidth = 0.32; c.beginPath(); c.arc(0, 0, 1.0, -PI / 2, -PI / 2 + fr * TAU); c.stroke();
    c.restore();
    c.strokeStyle = col; c.lineWidth = 0.13; c.beginPath(); c.arc(0, 0, 1.0, -PI / 2, -PI / 2 + fr * TAU); c.stroke();
    const a = -PI / 2 + fr * TAU;
    c.beginPath(); c.arc(Math.cos(a), Math.sin(a), 0.13, 0, TAU); c.fillStyle = '#ffffff'; c.fill();
    if (fr >= 1) glowU(c, 0, 0, 1.6, col, 0.55);
  }
  c.beginPath(); c.arc(0, 0, 0.18, 0, TAU); c.fillStyle = P.brass; c.fill(); ink(c, iw * 0.7); c.stroke();
  if (st.label) {
    c.beginPath(); rrP(c, -0.8, 1.22, 1.6, 0.42, 0.1); shadeU(c, -0.8, 1.22, 1.6, 0.42, P.brass); ink(c, iw * 0.8); c.stroke();
    textU(c, String(st.label), 0, 1.44, 0.26, { color: P.ink, font: FONT.deco, maxW: 1.45 });
  }
  rs(ctx);
});
//>>LOBBY

//<<END
export const ART = {
  drawRunner, drawTwin, drawGhost, drawBank, drawRoofSign, drawBell, drawBuyer, drawMerchant, drawRat, drawAnvil, drawTether,
  drawStake, drawWall, drawCoin, drawNote, drawPistol, drawMachete, drawBalloon, drawBarrel, drawCollector, drawJar, drawRadio,
  drawCabinet, drawTrophyShelf, drawCoinStack, drawPageCorner, drawHoldRing, bankGeometry, drawBuyerTag, roofSignDebug,
  RUNNER_PTS, BANK_GEO, BUYER_PTS, ANVIL_PTS,
};
export default ART;
