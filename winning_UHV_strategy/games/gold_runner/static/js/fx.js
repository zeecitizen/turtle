// fx.js - pooled particles + screen shake for Golden Gravity (F-ART). CONTRACT.md section 8.4.
//
//   FX.burst(kind, x, y, opts)   kinds: "dust","smoke","sparks","shavings","cash","bubbles","ticker","confetti","chips"
//   FX.update(dt)  dt in seconds        FX.draw(ctx)  draws in the ctx's current space (screen px, like the art)
//   FX.shake(amount_px, dur_s)          FX.offset() -> [dx, dy]  (one reused array; add it to the camera, never to hit boxes)
//   FX.clear()                          extras: FX.count(), FX.setScale(s)
//
// opts (all optional): n (count), s (px per unit, default FX.setScale or 95), dir (radians, 0 = right, -PI/2 = up; for dust / smoke /
//   bubbles a bare +1 / -1 means an up-and-sideways spray toward +x / -x), spread (radians),
//   speed (units/s), life (s), color ("#hex"), to: [x, y] (shavings fly there), onArrive(kind, x, y) (called once per shaving that lands),
//   floor (px y where chips / cash bounce or settle), w (spawn width in units, e.g. a wide molasses pit), vx, vy (units/s added: wind).
//
// Pooled: a fixed set of typed arrays, ring allocation, zero allocations per frame (a burst while the pool is full recycles the oldest).

import { P } from './palette.js';

const N = 1800;
const K = { dust: 1, smoke: 2, sparks: 3, shavings: 4, cash: 5, bubbles: 6, ticker: 7, confetti: 8, chips: 9 };
const KIND_ORDER = [2, 1, 6, 9, 5, 7, 8, 4, 3];       // draw order: smoke at the back, sparks (additive) on top

const kind = new Uint8Array(N);
const px = new Float32Array(N), py = new Float32Array(N), vx = new Float32Array(N), vy = new Float32Array(N);
const age = new Float32Array(N), life = new Float32Array(N), size = new Float32Array(N), grow = new Float32Array(N);
const rot = new Float32Array(N), vr = new Float32Array(N), drag = new Float32Array(N), grav = new Float32Array(N);
const sx = new Float32Array(N), sy = new Float32Array(N), cx = new Float32Array(N), cy = new Float32Array(N);
const tx = new Float32Array(N), ty = new Float32Array(N), seed = new Float32Array(N), floorY = new Float32Array(N);
const col = new Uint8Array(N), sub = new Uint8Array(N);
const cbf = new Array(N).fill(null);            // per-particle onArrive (a reference, no allocation)
const active = new Int32Array(N);
let nActive = 0, cursor = 0, defScale = 95, clock = 0;

// colour table (strings registered once; particles store an index)
const COLS = [];
const COLIDX = new Map();
function ci(hex) { let i = COLIDX.get(hex); if (i === undefined) { if (COLS.length >= 250) return 0; i = COLS.length; COLS.push(hex); COLIDX.set(hex, i); } return i; }
ci(P.ink);
const DUST = [ci('#d8c7a3'), ci('#c9b48c'), ci('#e9dcc0')];
const SMOKE = [ci('#2b2622'), ci('#3d3732'), ci('#4a443e')];
const SPARK = [ci('#fff2b0'), ci('#ffcc33'), ci('#ff9a3c'), ci('#ffffff')];
const SHAV = [ci('#e8edf2'), ci('#c9a24a'), ci('#a7adb7'), ci('#f0d68a')];
const NOTE = [ci('#8fc77a'), ci('#6fae5c'), ci('#a9d895')];
const COIN = [ci('#ffcc33'), ci('#f0b429')];
const CONF = [ci('#e0303a'), ci('#3fe6ff'), ci('#ffcc33'), ci('#5dff8a'), ci('#ff4fd8'), ci('#b44dff'), ci('#ffffff')];
const CHIP = [ci('#e0303a'), ci('#1f9e6e'), ci('#2d6fd6'), ci('#17171f'), ci('#ffcc33')];
const BUB = [ci('#6b3a17'), ci('#7d4620')];
const TICK = [ci('#f3f0e6'), ci('#efe6c8')];
const DUSTHI = ci('#fff6e0');
const WHITE = ci('#ffffff'), INK = 0, GOLDD = ci('#b8860b'), MOLHI = ci('#a0662f'), NOTEDK = ci('#3f6e33');


// deterministic-ish random (no allocation)
let rs = 12345;
function rnd() { rs = (rs * 1664525 + 1013904223) >>> 0; return rs / 4294967296; }
const rr = (a, b) => a + (b - a) * rnd();
const pick = (arr) => arr[(rnd() * arr.length) | 0];

function spawn() {
  // ring allocation: take the next slot (recycles the oldest when full)
  const i = cursor; cursor = (cursor + 1) % N;
  return i;
}

function burst(kindName, x, y, o) {
  const k = K[kindName];
  if (!k || !isFinite(x) || !isFinite(y)) return;
  o = o || {};
  const S = o.s > 0 ? o.s : defScale;
  let dir = typeof o.dir === 'number' && isFinite(o.dir) ? o.dir : -Math.PI / 2;
  // a bare +1 / -1 means 'toward +x / -x' for ground kinds (dust, smoke, bubbles): an up-and-sideways spray
  if ((k === 1 || k === 2 || k === 6) && (o.dir === 1 || o.dir === -1)) dir = -Math.PI / 2 + o.dir * 0.95;
  const n = Math.max(0, Math.min(400, o.n != null ? o.n | 0 : DEFN[k]));
  const userCol = o.color ? ci(o.color) : -1;
  const wx = (o.vx || 0) * S, wy = (o.vy || 0) * S;
  const spawnW = (o.w || 0) * S;
  const fl = typeof o.floor === 'number' ? o.floor : 1e9;
  const onArrive = typeof o.onArrive === 'function' ? o.onArrive : null;
  for (let j = 0; j < n; j++) {
    const i = spawn();
    kind[i] = k; age[i] = 0; seed[i] = rnd(); sub[i] = 0; cbf[i] = null; floorY[i] = fl;
    px[i] = x + (spawnW ? rr(-0.5, 0.5) * spawnW : 0); py[i] = y;
    rot[i] = rr(0, 6.283); vr[i] = 0; drag[i] = 0; grav[i] = 0; grow[i] = 1;
    let spread = typeof o.spread === 'number' ? o.spread : 0.8, sp = 1, lf = 1;
    switch (k) {
      case 1: // dust: soft puffs that grow and fade
        spread = o.spread ?? 2.4; sp = rr(0.3, 1.7) * (o.speed || 1); lf = rr(0.5, 1.05);
        size[i] = rr(0.03, 0.075) * S; grow[i] = rr(2.2, 3.4); drag[i] = 3.0; grav[i] = -0.18 * S; col[i] = userCol >= 0 ? userCol : pick(DUST);
        break;
      case 2: // smoke: dark billows that rise and swell
        spread = o.spread ?? 1.3; sp = rr(0.25, 1.0) * (o.speed || 1); lf = rr(1.3, 2.3);
        size[i] = rr(0.045, 0.1) * S; grow[i] = rr(3.0, 4.6); drag[i] = 1.5; grav[i] = -0.6 * S; col[i] = userCol >= 0 ? userCol : pick(SMOKE);
        break;
      case 3: // sparks: bright streaks, gravity, additive
        spread = o.spread ?? 2.4; sp = rr(1.6, 4.8) * (o.speed || 1); lf = rr(0.2, 0.55);
        size[i] = rr(0.012, 0.022) * S; drag[i] = 1.2; grav[i] = 3.2 * S; col[i] = userCol >= 0 ? userCol : pick(SPARK);
        break;
      case 4: { // shavings: hop up, then fly a curve to opts.to and ping
        spread = o.spread ?? 1.6; sp = rr(0.6, 1.4); lf = rr(0.75, 1.25) * (o.life || 1);
        size[i] = rr(0.022, 0.04) * S; vr[i] = rr(-16, 16); col[i] = userCol >= 0 ? userCol : pick(SHAV);
        const to = o.to || [x, y - 0.6 * S];
        sx[i] = px[i]; sy[i] = py[i]; tx[i] = to[0] + rr(-0.03, 0.03) * S; ty[i] = to[1] + rr(-0.02, 0.02) * S;
        const a = dir + rr(-spread / 2, spread / 2);
        cx[i] = (sx[i] + tx[i]) / 2 + Math.cos(a) * sp * 0.5 * S; cy[i] = Math.min(sy[i], ty[i]) - rr(0.35, 0.8) * S;
        cbf[i] = onArrive; life[i] = lf; vx[i] = 0; vy[i] = 0;
        continue;
      }
      case 5: // cash: banknotes + coins from the blunderbuss, flutter as they fall
        spread = o.spread ?? 0.7; sp = rr(2.0, 5.2) * (o.speed || 1); lf = rr(1.4, 2.4);
        sub[i] = rnd() < 0.35 ? 1 : 0;              // 1 = coin, 0 = note
        size[i] = (sub[i] ? rr(0.035, 0.05) : rr(0.07, 0.09)) * S; drag[i] = 2.2; grav[i] = 2.4 * S; vr[i] = rr(-9, 9);
        col[i] = userCol >= 0 ? userCol : sub[i] ? pick(COIN) : pick(NOTE);
        break;
      case 6: // bubbles: molasses bubbles that rise a little, swell and pop
        spread = o.spread ?? 0.5; sp = rr(0.05, 0.25); lf = rr(0.6, 1.4);
        size[i] = rr(0.015, 0.04) * S; grow[i] = rr(1.4, 2.2); drag[i] = 2; grav[i] = -0.15 * S; col[i] = userCol >= 0 ? userCol : pick(BUB);
        px[i] = x + (spawnW ? rr(-0.5, 0.5) * spawnW : rr(-0.12, 0.12) * S);
        break;
      case 7: // ticker tape strips: drift down, flutter and twist
        spread = o.spread ?? 1.2; sp = rr(0.3, 1.2) * (o.speed || 1); lf = rr(1.6, 3.2);
        size[i] = rr(0.1, 0.16) * S; drag[i] = 2.6; grav[i] = 0.9 * S; vr[i] = rr(-5, 5); col[i] = userCol >= 0 ? userCol : pick(TICK);
        break;
      case 8: // confetti
        spread = o.spread ?? 1.3; sp = rr(1.8, 4.5) * (o.speed || 1); lf = rr(1.4, 2.6);
        size[i] = rr(0.025, 0.042) * S; drag[i] = 2.4; grav[i] = 1.6 * S; vr[i] = rr(-12, 12); col[i] = userCol >= 0 ? userCol : pick(CONF);
        break;
      case 9: // casino chips: pop up, spin, bounce once on the floor
        spread = o.spread ?? 1.2; sp = rr(1.6, 3.6) * (o.speed || 1); lf = rr(1.2, 2.0);
        size[i] = rr(0.04, 0.055) * S; drag[i] = 0.6; grav[i] = 5.5 * S; vr[i] = rr(-10, 10); col[i] = userCol >= 0 ? userCol : pick(CHIP);
        break;
      default: break;
    }
    if (o.life && k !== 4) lf = o.life * rr(0.8, 1.2);
    const a = dir + rr(-spread / 2, spread / 2);
    vx[i] = Math.cos(a) * sp * S + wx; vy[i] = Math.sin(a) * sp * S + wy;
    if ((k === 1 || k === 2) && vy[i] > 0) vy[i] *= -0.35;   // dust and smoke never dive into the street: they skid off it
    life[i] = lf;
  }
}
const DEFN = [0, 14, 11, 18, 8, 26, 5, 14, 46, 10];

function update(dt) {
  if (!(dt > 0)) return;
  dt = Math.min(dt, 0.1);
  clock += dt;
  updShake(dt);
  let n = 0;
  for (let i = 0; i < N; i++) {
    const k = kind[i];
    if (!k) continue;
    age[i] += dt;
    if (age[i] >= life[i]) {
      if (k === 4) arrive(i);
      kind[i] = 0; continue;
    }
    if (k === 4) {
      // quadratic bezier from (sx,sy) via (cx,cy) to (tx,ty), eased in so they gather then whoosh
      let u = age[i] / life[i]; u = u * u * (3 - 2 * u);
      const a = 1 - u;
      px[i] = a * a * sx[i] + 2 * a * u * cx[i] + u * u * tx[i];
      py[i] = a * a * sy[i] + 2 * a * u * cy[i] + u * u * ty[i];
      rot[i] += vr[i] * dt;
    } else {
      const d = Math.exp(-drag[i] * dt);
      vx[i] *= d; vy[i] = vy[i] * d + grav[i] * dt;
      if (k === 5 || k === 7 || k === 8) {      // flutter: a sideways sway that grows as they slow
        const sway = Math.sin(clock * (5 + seed[i] * 4) + seed[i] * 20) * size[i] * 6;
        px[i] += (vx[i] + sway) * dt;
        if (vy[i] > 0) vy[i] = Math.min(vy[i], (k === 8 ? 1.1 : 0.8) * defScale * (0.5 + seed[i]));
      } else px[i] += vx[i] * dt;
      py[i] += vy[i] * dt;
      rot[i] += vr[i] * dt;
      if (py[i] > floorY[i]) {
        if (k === 9 && sub[i] === 0) { py[i] = floorY[i]; vy[i] = -Math.abs(vy[i]) * 0.45; vx[i] *= 0.7; sub[i] = 1; }
        else if (k === 9 || k === 5) { py[i] = floorY[i]; vy[i] = 0; vx[i] *= 0.8; vr[i] *= 0.85; }
      }
    }
    active[n++] = i;
  }
  nActive = n;
}
function arrive(i) {
  const f = cbf[i];
  cbf[i] = null;
  if (f) { try { f('shavings', tx[i], ty[i]); } catch (e) { /* the caller's problem, never ours */ } }
}

function draw(ctx) {
  if (!nActive) return;
  ctx.save();
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  for (let o = 0; o < KIND_ORDER.length; o++) {
    const k = KIND_ORDER[o];
    let lastCol = -1;
    if (k === 3) ctx.globalCompositeOperation = 'lighter';
    for (let j = 0; j < nActive; j++) {
      const i = active[j];
      if (kind[i] !== k) continue;
      const u = age[i] / life[i];
      const c = col[i];
      switch (k) {
        case 1: { // dust
          const r = size[i] * (1 + (grow[i] - 1) * u);
          ctx.globalAlpha = 0.6 * (1 - u) * Math.min(1, u * 8);
          if (c !== lastCol) { ctx.fillStyle = COLS[c]; lastCol = c; }
          ctx.beginPath(); ctx.arc(px[i], py[i], r, 0, 6.2832); ctx.fill();
          ctx.globalAlpha *= 0.6; ctx.fillStyle = COLS[DUSTHI]; ctx.beginPath(); ctx.arc(px[i] - r * 0.3, py[i] - r * 0.3, r * 0.55, 0, 6.2832); ctx.fill(); lastCol = -1;
          break;
        }
        case 2: { // smoke: billow + a lighter inner puff
          const r = size[i] * (1 + (grow[i] - 1) * Math.sqrt(u));
          ctx.globalAlpha = 0.62 * (1 - u) * Math.min(1, u * 6);
          if (c !== lastCol) { ctx.fillStyle = COLS[c]; lastCol = c; }
          ctx.beginPath(); ctx.arc(px[i], py[i], r, 0, 6.2832); ctx.fill();
          ctx.beginPath(); ctx.arc(px[i] - r * 0.45, py[i] - r * 0.3, r * 0.62, 0, 6.2832); ctx.fill();
          break;
        }
        case 3: { // sparks: a streak along the velocity
          ctx.globalAlpha = Math.min(1, (1 - u) * 1.6);
          if (c !== lastCol) { ctx.strokeStyle = COLS[c]; lastCol = c; }
          ctx.lineWidth = size[i] * (1 - u * 0.6);
          ctx.beginPath(); ctx.moveTo(px[i], py[i]); ctx.lineTo(px[i] - vx[i] * 0.03, py[i] - vy[i] * 0.03); ctx.stroke();
          break;
        }
        case 4: { // shavings: a curled metal sliver with a glint
          ctx.globalAlpha = 1;
          const r = size[i];
          ctx.translate(px[i], py[i]); ctx.rotate(rot[i]);
          ctx.fillStyle = COLS[INK]; ctx.beginPath(); ctx.ellipse(0, 0, r * 1.15, r * 0.42, 0, 0, 6.2832); ctx.fill();
          ctx.fillStyle = COLS[c]; ctx.beginPath(); ctx.ellipse(0, 0, r, r * 0.28, 0, 0, 6.2832); ctx.fill();
          if (((clock * 6 + seed[i] * 10) | 0) % 3 === 0) { ctx.fillStyle = COLS[WHITE]; ctx.beginPath(); ctx.arc(-r * 0.3, -r * 0.05, r * 0.22, 0, 6.2832); ctx.fill(); }
          ctx.rotate(-rot[i]); ctx.translate(-px[i], -py[i]);
          lastCol = -1;
          break;
        }
        case 5: { // cash: notes (flipping rectangles) and coins
          ctx.globalAlpha = Math.min(1, (1 - u) * 3);
          const r = size[i];
          const flip = Math.cos(rot[i] * 1.3);
          ctx.translate(px[i], py[i]); ctx.rotate(rot[i] * 0.4);
          if (sub[i] === 1) {
            ctx.fillStyle = COLS[INK]; ctx.beginPath(); ctx.ellipse(0, 0, r * Math.abs(flip) + 1, r + 1, 0, 0, 6.2832); ctx.fill();
            ctx.fillStyle = COLS[c]; ctx.beginPath(); ctx.ellipse(0, 0, r * Math.abs(flip) * 0.82 + 0.5, r * 0.82, 0, 0, 6.2832); ctx.fill();
          } else {
            const w = r * 1.0, h = r * 0.5 * Math.abs(flip) + 0.6;
            ctx.fillStyle = COLS[NOTEDK]; ctx.fillRect(-w - 1, -h - 1, w * 2 + 2, h * 2 + 2);
            ctx.fillStyle = COLS[c]; ctx.fillRect(-w, -h, w * 2, h * 2);
            ctx.fillStyle = COLS[NOTEDK]; ctx.fillRect(-w * 0.25, -h * 0.55, w * 0.5, h * 1.1);
          }
          ctx.rotate(-rot[i] * 0.4); ctx.translate(-px[i], -py[i]);
          lastCol = -1;
          break;
        }
        case 6: { // bubbles: a glossy dome, then a pop ring
          const r = size[i] * (1 + (grow[i] - 1) * u);
          if (u < 0.85) {
            ctx.globalAlpha = 0.95;
            ctx.fillStyle = COLS[INK]; ctx.beginPath(); ctx.arc(px[i], py[i], r + 1, 0, 6.2832); ctx.fill();
            ctx.fillStyle = COLS[c]; ctx.beginPath(); ctx.arc(px[i], py[i], r, 0, 6.2832); ctx.fill();
            ctx.fillStyle = COLS[MOLHI]; ctx.beginPath(); ctx.arc(px[i] - r * 0.35, py[i] - r * 0.35, r * 0.3, 0, 6.2832); ctx.fill();
          } else {
            const q = (u - 0.85) / 0.15;
            ctx.globalAlpha = 1 - q; ctx.strokeStyle = COLS[MOLHI]; ctx.lineWidth = Math.max(1, r * 0.25);
            ctx.beginPath(); ctx.arc(px[i], py[i], r * (1 + q * 1.2), 0, 6.2832); ctx.stroke();
          }
          lastCol = -1;
          break;
        }
        case 7: { // ticker tape: a twisting strip with printed dashes
          ctx.globalAlpha = Math.min(1, (1 - u) * 2.5);
          const L = size[i], h = L * 0.17 * (0.35 + 0.65 * Math.abs(Math.cos(rot[i] * 1.7)));
          ctx.translate(px[i], py[i]); ctx.rotate(rot[i] * 0.5);
          ctx.fillStyle = COLS[c]; ctx.fillRect(-L / 2, -h / 2, L, h);
          ctx.fillStyle = COLS[INK]; ctx.globalAlpha *= 0.55;
          for (let d = -0.4; d < 0.45; d += 0.18) ctx.fillRect(L * d, -h * 0.15, L * 0.08, h * 0.3);
          ctx.rotate(-rot[i] * 0.5); ctx.translate(-px[i], -py[i]);
          lastCol = -1;
          break;
        }
        case 8: { // confetti: a square that flips in 3D
          ctx.globalAlpha = Math.min(1, (1 - u) * 2.5);
          const r = size[i], w = r * Math.abs(Math.cos(rot[i])) + 0.5;
          if (c !== lastCol) { ctx.fillStyle = COLS[c]; lastCol = c; }
          ctx.translate(px[i], py[i]); ctx.rotate(rot[i] * 0.3);
          ctx.fillRect(-w / 2, -r / 2, w, r);
          ctx.rotate(-rot[i] * 0.3); ctx.translate(-px[i], -py[i]);
          break;
        }
        case 9: { // chips: a coloured disc with white edge marks, seen at a tilt
          ctx.globalAlpha = Math.min(1, (1 - u) * 3);
          const r = size[i], fy = 0.35 + 0.65 * Math.abs(Math.cos(rot[i]));
          ctx.translate(px[i], py[i]);
          ctx.fillStyle = COLS[INK]; ctx.beginPath(); ctx.ellipse(0, 0, r + 1, r * fy + 1, 0, 0, 6.2832); ctx.fill();
          ctx.fillStyle = COLS[c]; ctx.beginPath(); ctx.ellipse(0, 0, r, r * fy, 0, 0, 6.2832); ctx.fill();
          ctx.strokeStyle = COLS[WHITE]; ctx.lineWidth = Math.max(1, r * 0.22); ctx.setLineDash([r * 0.35, r * 0.45]);
          ctx.beginPath(); ctx.ellipse(0, 0, r * 0.78, r * fy * 0.78, 0, rot[i], rot[i] + 6.2832); ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = COLS[WHITE]; ctx.globalAlpha *= 0.5; ctx.beginPath(); ctx.ellipse(0, 0, r * 0.38, r * fy * 0.38, 0, 0, 6.2832); ctx.fill();
          ctx.translate(-px[i], -py[i]);
          lastCol = -1;
          break;
        }
        default: break;
      }
    }
    if (k === 3) ctx.globalCompositeOperation = 'source-over';
  }
  ctx.restore();
}

// ---------------------------------------------------------------- screen shake (trauma that decays; smooth, not jittery)
let shAmp = 0, shT = 0, shDur = 0;
const OFF = [0, 0];
function shake(amount, dur) {
  amount = +amount || 0; dur = +dur || 0.3;
  if (amount <= 0) return;
  if (shT <= 0 || amount >= shAmp * (shT / Math.max(1e-3, shDur))) { shAmp = amount; shDur = dur; shT = dur; }
}
function updShake(dt) { if (shT > 0) shT = Math.max(0, shT - dt); }
function offset() {
  if (shT <= 0) { OFF[0] = 0; OFF[1] = 0; return OFF; }
  const k = shT / shDur, a = shAmp * k * k;
  OFF[0] = a * (Math.sin(clock * 47.3) * 0.6 + Math.sin(clock * 83.1 + 1.3) * 0.4);
  OFF[1] = a * (Math.sin(clock * 53.7 + 2.1) * 0.6 + Math.sin(clock * 71.9 + 0.4) * 0.4);
  return OFF;
}
function clear() { kind.fill(0); cbf.fill(null); nActive = 0; shT = 0; OFF[0] = 0; OFF[1] = 0; }
function count() { return nActive; }
function setScale(s) { if (s > 0) defScale = s; }

export const FX = { burst, update, draw, shake, offset, clear, count, setScale, KINDS: Object.keys(K) };
export { burst, update, draw, shake, offset, clear, count, setScale };
export default FX;
