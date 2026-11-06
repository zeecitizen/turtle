// main.js - Golden Gravity: the director (F-CORE).
//
// Composes every frame from the latest snapshot: the camera and the layout of CONTRACT 8.1 (the whole ladder on screen, the mirror world for
// a short, the ground rotated by the tilt about the runner, a gentle camera roll, FX shake), the draw order of the contract, interpolation
// (the runner's x and the tilt ease toward the latest snapshot - nothing is ever extrapolated), input with hold-to-confirm rings, the
// reactions to every event, and the screens (screens.js). art.js / world.js / fx.js / audio.js are loaded dynamically and every call is
// guarded: a missing or throwing function falls back to a simple placeholder so this file runs on its own.

import { P, SKY, LINE, FONT, inkStroke, rgba, mix, lighten, darken, shade, glow, rivet, roundRect, rand, clamp, lerp, ease } from './palette.js';
import { createNet, money } from './net.js';
import * as SCR from './screens.js';
import { drawCottageBank, cottageGeometry } from './bank2.js';
import { drawHumanBuyer } from './buyer2.js';
import { drawCyclist } from './cyclist.js';
import { VEHICLES, drawVehicle } from './vehicles.js';
import { drawHunterBack, drawHunterHat, drawShotgun } from './hunter.js';
import { drawIdleScene, IDLE_KINDS } from './idle.js';
import { drawWhiteRat } from './rats.js';
import { drawGem } from './diamondart.js';
import { drawYogi } from './yogi.js';
import { drawAngel, drawLightShield, drawBubble } from './angel.js';   // Zee 2026-11-06: the angel = the risk manager   // Zee 2026-11-05: the yogi and his orb (day = a breakout expected)   // Zee 2026-11-04: his UHV Diamond as a hint (the camel and the gem)
import { drawFrictionTrench, drawFaultLines, drawVortex, drawPolished } from './hints.js';   // Zee 2026-11-04: volume hints                          // Zee 2026-11-04: clear white rats               // Zee 2026-11-04: yoga, bird watching, a camp while the market sleeps   // Zee 2026-11-04: the Runner is a gold hunter at the start             // Zee 2026-11-04: targets are vehicles; the boss hands it over                       // Zee 2026-11-04: the ice-cream girl (profit) or the thief (loss)                   // Zee 2026-11-04: a human Buyer waiting on the hill, not a zeppelin   // Zee 2026-11-04: the small Gold Bank, a guard outside

const DEG = Math.PI / 180;
const TAU = Math.PI * 2;
const VIS_TILT_DEG = 18;                 // on-screen street angle at |tilt| = 1 (CONTRACT: max 25)
const params = new URLSearchParams(location.search);
const FIXTURE = params.get('fixture');
let DEBUG = params.has('debug');

const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const bootEl = document.getElementById('boot');
const liveFrameEl = document.getElementById('liveframe');
if (bootEl) bootEl.classList.add('gone');

// ======================================================================================================== guarded modules
const MOD = { art: null, world: null, fx: null, audio: null, loaded: false };
const MISSES = new Map();
function miss(name, err) {
  if (MISSES.has(name)) return;
  const msg = err ? String((err && err.message) || err).slice(0, 160) : 'missing';
  MISSES.set(name, msg);
  console.info('[main] placeholder for ' + name + ' (' + msg + ')');
}
async function loadModules() {
  const load = async (n) => {
    try { return await import(new URL('./' + n + '.js', import.meta.url).href); }
    catch (e) { MISSES.set(n + '.js', String(e && e.message || e).slice(0, 160)); console.warn('[main] ' + n + '.js not usable, placeholders in use: ' + String(e && e.message || e).slice(0, 120)); return null; }
  };
  const [art, world, fx, audio] = await Promise.all(['art', 'world', 'fx', 'audio'].map(load));
  MOD.art = art;
  if (world) {
    const mk = world.makeWorld || (world.default && world.default.makeWorld);
    if (typeof mk === 'function') { try { MOD.world = mk(); } catch (e) { miss('world.makeWorld', e); } }
    else miss('world.makeWorld', 'missing');
  }
  if (fx) MOD.fx = fx.FX || fx.default || null;
  if (audio) MOD.audio = audio.Audio || audio.default || null;
  MOD.loaded = true;
}

function guarded(c, f, self, args, label) {
  const isCtx = c && typeof c.save === 'function';
  if (isCtx) c.save();
  try { const v = f.apply(self, args); if (isCtx) c.restore(); return { ok: true, v }; }
  catch (e) { if (isCtx) { try { c.restore(); } catch (e2) { /* */ } } miss(label, e); return { ok: false }; }
}
// art.js call: art('drawRunner', ctx, x, y, s, st)
function art(name, ...args) {                                 // returns what art.js returned (RUNNER_PTS, BUYER_PTS...) or null
  const f = MOD.art && MOD.art[name];
  if (typeof f === 'function') { const r = guarded(args[0], f, MOD.art, args, 'art.' + name); if (r.ok) return r.v === undefined ? true : r.v; }
  else if (MOD.loaded) miss('art.' + name, MOD.art ? 'missing' : 'art.js absent');
  const fb = FB[name];
  if (fb) guarded(args[0], fb, FB, args, 'fallback.' + name);
  return null;
}
function artGeo(name, ...args) {                              // plain geometry helpers exported by art.js (bankGeometry ...)
  const f = MOD.art && MOD.art[name];
  if (typeof f !== 'function') return null;
  try { return f(...args); } catch (e) { miss('art.' + name, e); return null; }
}
const ptsOK = (p, k) => p && typeof p === 'object' && isFinite(p[k]);
let terrainFromWorld = true;                                 // drawTerrain and groundYAt always come from the SAME source
function wcall(name, ...args) {
  const w = MOD.world, f = w && w[name];
  if (typeof f === 'function') { const r = guarded(args[0], f, w, args, 'world.' + name); if (r.ok) return r.v; }
  else if (MOD.loaded) miss('world.' + name, w ? 'missing' : 'world.js absent');
  const fb = FBW[name];
  if (fb) { const r = guarded(args[0], fb, FBW, args, 'fallback.' + name); return r.v; }
  return undefined;
}
function terrainOK() {
  const w = MOD.world;
  return terrainFromWorld && w && typeof w.drawTerrain === 'function' && typeof w.groundYAt === 'function';
}
function drawTerrainAny(c, view, terrain, env, t) {
  if (terrainOK()) {
    const r = guarded(c, MOD.world.drawTerrain, MOD.world, [c, view, terrain, env, t], 'world.drawTerrain');
    if (r.ok) return;
    terrainFromWorld = false;
  }
  guarded(c, FBW.drawTerrain, FBW, [c, view, terrain, env, t], 'fallback.drawTerrain');
}
function groundYAt(view, terrain, xn) {
  if (terrainOK()) {
    try { const v = MOD.world.groundYAt(view, terrain, xn); if (isFinite(v)) return v; } catch (e) { miss('world.groundYAt', e); }
    terrainFromWorld = false;
  }
  return FBW.groundYAt(view, terrain, xn);
}
const FXK = {
  call(name, args) {
    const fx = MOD.fx, f = fx && fx[name];
    if (typeof f === 'function') { try { return f.apply(fx, args); } catch (e) { miss('fx.' + name, e); } }
    else if (MOD.loaded && fx) miss('fx.' + name, 'missing');
    return FBFX[name].apply(FBFX, args);
  },
  burst(kind, x, y, o) { return this.call('burst', [kind, x, y, o || {}]); },
  update(dt) { return this.call('update', [dt]); },
  draw(c) { c.save(); try { this.call('draw', [c]); } finally { c.restore(); } },
  shake(a, d) { return this.call('shake', [a, d]); },
  offset() { const o = this.call('offset', []); return Array.isArray(o) && isFinite(o[0]) && isFinite(o[1]) ? o : [0, 0]; },
  clear() { return this.call('clear', []); },
};
let audioReady = false;
const SNDLOG = [];                                            // every event sound asked for [name, ms]: one event must be voiced once
function snd(name, opts) {
  if (name !== 'footstep' && name !== 'tick') { SNDLOG.push([name, Math.round(performance.now())]); if (SNDLOG.length > 60) SNDLOG.shift(); }
  const a = MOD.audio;
  if (!a || !audioReady || typeof a.play !== 'function') return;
  try { a.play(name, opts || {}); } catch (e) { miss('audio.play:' + name, e); }
}
function audioCall(name, ...args) {
  const a = MOD.audio;
  if (!a || !audioReady || typeof a[name] !== 'function') return;
  try { a[name](...args); } catch (e) { miss('audio.' + name, e); }
}
function initAudio() {
  if (audioReady || !MOD.audio) return;
  try { if (typeof MOD.audio.init === 'function') MOD.audio.init(); audioReady = true; } catch (e) { miss('audio.init', e); }
  const snap = net.snap;
  if (audioReady && snap && snap.settings) audioCall('setMuted', !snap.settings.sound);
}

// ======================================================================================================== placeholder art (fallbacks)
const FB = {
  drawRunner(c, x, y, s, o = {}) {
    const f = o.facing || 1, pose = o.pose || 'idle', out = o.outfit || 'suit';
    c.globalAlpha *= o.alpha == null ? 1 : o.alpha;
    c.translate(x, y);
    const k = pose === 'kneel' ? 0.72 : pose === 'slide' || pose === 'ride' ? 0.86 : 1;
    if (pose === 'ride') { c.fillStyle = P.gold; c.beginPath(); c.ellipse(0, -0.03 * s, 0.32 * s, 0.06 * s, 0, 0, TAU); c.fill(); inkStroke(c, s, LINE.inkThin); c.stroke(); c.translate(0, -0.08 * s); }
    c.rotate(clamp(o.lean || 0, -1, 1) * 0.28 * f);
    const body = { suit: P.suit, tux: P.tux, undershirt: P.undershirt, boxers: P.boxers, dusty: P.suitDark, barrel: P.barrel, staked: P.suit }[out] || P.suit;
    const legs = out === 'boxers' ? P.skin : out === 'tux' ? P.tux : P.suitDark;
    inkStroke(c, s);
    c.strokeStyle = P.ink; c.lineWidth = Math.max(2, 0.07 * s);
    c.beginPath();
    if (pose === 'run') { const p = Math.sin((o.t || 0) * 10) * 0.12 * s; c.moveTo(0, -0.38 * s * k); c.lineTo(-p, 0); c.moveTo(0, -0.38 * s * k); c.lineTo(p, 0); }
    else if (pose === 'kneel') { c.moveTo(-0.05 * s, -0.3 * s); c.lineTo(-0.16 * s, -0.05 * s); c.lineTo(0.05 * s, 0); c.moveTo(0.05 * s, -0.3 * s); c.lineTo(0.12 * s, 0); }
    else { c.moveTo(-0.06 * s, -0.38 * s * k); c.lineTo(-0.1 * s, 0); c.moveTo(0.06 * s, -0.38 * s * k); c.lineTo(0.1 * s, 0); }
    c.stroke();
    c.strokeStyle = legs; c.lineWidth = Math.max(1, 0.045 * s); c.stroke();
    inkStroke(c, s);
    if (out === 'boxers') { roundRect(c, -0.13 * s, -0.46 * s * k, 0.26 * s, 0.12 * s, 0.03 * s); c.fillStyle = P.boxers; c.fill(); c.stroke(); }
    roundRect(c, -0.14 * s, -0.74 * s * k, 0.28 * s, out === 'boxers' ? 0.3 * s : 0.38 * s, 0.07 * s);
    shade(c, -0.14 * s, -0.74 * s * k, 0.28 * s, 0.38 * s, out === 'boxers' ? P.undershirt : body); c.stroke();
    if (out === 'suit' || out === 'dusty' || out === 'staked') { c.strokeStyle = P.suspender; c.lineWidth = 0.03 * s; c.beginPath(); c.moveTo(-0.07 * s, -0.72 * s * k); c.lineTo(-0.05 * s, -0.4 * s * k); c.moveTo(0.07 * s, -0.72 * s * k); c.lineTo(0.05 * s, -0.4 * s * k); c.stroke(); inkStroke(c, s); }
    if (out === 'tux') { c.fillStyle = P.shirt; c.beginPath(); c.moveTo(-0.05 * s, -0.74 * s * k); c.lineTo(0, -0.5 * s * k); c.lineTo(0.05 * s, -0.74 * s * k); c.fill(); }
    // arms
    c.lineWidth = Math.max(2, 0.06 * s); c.strokeStyle = P.ink; c.beginPath();
    const sh = -0.66 * s * k;
    if (pose === 'cheer' || pose === 'fly') { c.moveTo(-0.12 * s, sh); c.lineTo(-0.2 * s, sh - 0.3 * s); c.moveTo(0.12 * s, sh); c.lineTo(0.2 * s, sh - 0.3 * s); }
    else if (pose === 'aim') { c.moveTo(0.1 * f * s, sh); c.lineTo(0.42 * f * s, sh + 0.02 * s); c.moveTo(-0.1 * f * s, sh); c.lineTo(-0.16 * f * s, sh + 0.25 * s); }
    else if (pose === 'hold') { c.moveTo(0.12 * f * s, sh); c.lineTo(0.3 * f * s, sh + 0.06 * s); c.moveTo(-0.12 * f * s, sh); c.lineTo(-0.16 * f * s, sh + 0.26 * s); }
    else { c.moveTo(-0.12 * s, sh); c.lineTo(0.02 * f * s, sh + 0.16 * s); c.moveTo(0.12 * s, sh); c.lineTo(0.12 * f * s, sh + 0.16 * s); }
    c.stroke();
    // head
    inkStroke(c, s);
    c.beginPath(); c.arc(0, -0.86 * s * k, 0.15 * s, 0, TAU); c.fillStyle = o.wooden ? P.wood : P.skin; c.fill(); c.stroke();
    c.fillStyle = P.ink; c.beginPath(); c.arc(0.06 * f * s, -0.88 * s * k, 0.018 * s, 0, TAU); c.fill();
    if (o.hat) { c.fillStyle = P.tux; c.fillRect(-0.1 * s, -1.16 * s * k, 0.2 * s, 0.16 * s); c.fillRect(-0.16 * s, -1.0 * s * k, 0.32 * s, 0.035 * s); }
    else if (out !== 'boxers') { c.fillStyle = P.hair; c.beginPath(); c.arc(0, -0.9 * s * k, 0.15 * s, Math.PI, TAU); c.fill(); }
    if (o.cane) { c.strokeStyle = P.goldHot; c.lineWidth = 0.03 * s; c.beginPath(); c.moveTo(0.2 * f * s, -0.55 * s * k); c.lineTo(0.32 * f * s, 0); c.stroke(); }
    if (o.coin && o.coin.visible) FB.drawCoin(c, 0.15 * f * s, -0.55 * s * k, 0.12 * s, { ...o.coin, t: o.t, wooden: o.wooden });
    if (out === 'barrel') { c.translate(0, 0); FB.drawBarrel(c, 0, 0, s, { t: o.t }); }
  },
  drawTwin(c, x, y, s, o = {}) { FB.drawRunner(c, x, y, s, { ...o, outfit: 'suit', tint: P.twinBrass }); c.globalAlpha = (o.alpha || 0.7) * 0.5; c.fillStyle = P.twinBrass; c.beginPath(); c.arc(x, y - 0.6 * s, 0.4 * s, 0, TAU); c.fill(); },
  drawGhost(c, x, y, s, o = {}) { c.globalAlpha = o.alpha == null ? 0.3 : o.alpha; c.fillStyle = P.ghost; c.beginPath(); c.ellipse(x, y - 0.5 * s, 0.2 * s, 0.5 * s, 0, 0, TAU); c.fill(); c.beginPath(); c.arc(x, y - 0.95 * s, 0.15 * s, 0, TAU); c.fill(); },
  drawBank(c, x, y, s, o = {}) {
    const w = 3.4 * s, h = 4.6 * s, L = x - w / 2, T = y - h;
    inkStroke(c, s);
    c.beginPath(); c.rect(L, T + 0.5 * s, w, h - 0.5 * s); shade(c, L, T, w, h, o.wooden ? P.wood : P.iron); c.stroke();
    c.beginPath(); c.moveTo(L - 0.15 * s, T + 0.55 * s); c.lineTo(x, T); c.lineTo(L + w + 0.15 * s, T + 0.55 * s); c.closePath(); shade(c, L, T, w, 0.6 * s, P.brass); c.stroke();
    for (let i = 0; i < 4; i++) { const cx = L + (0.35 + i * 0.9) * s; c.beginPath(); c.rect(cx - 0.12 * s, T + 0.7 * s, 0.24 * s, h - 1.0 * s); shade(c, cx - 0.12 * s, T, 0.24 * s, h, P.ironLight); c.stroke(); }
    c.beginPath(); c.rect(x - 0.55 * s, T + 1.0 * s, 1.1 * s, 1.4 * s); c.fillStyle = '#120f0c'; c.fill(); c.strokeStyle = P.gold; c.lineWidth = LINE.deco * s * 2; c.stroke();
    const b = o.banker || {};
    c.fillStyle = P.ironLight; c.beginPath(); c.arc(x, T + 1.75 * s, 0.32 * s, 0, TAU); c.fill(); inkStroke(c, s); c.stroke();
    c.fillStyle = P.visor; c.fillRect(x - 0.3 * s, T + 1.55 * s, 0.6 * s, 0.12 * s);
    c.fillStyle = '#c0613b'; c.fillRect(x + 0.1 * s, T + 1.86 * s, 0.25 * s, 0.05 * s);
    if (b.mood === 'cards') { c.fillStyle = P.paper; for (let i = 0; i < 3; i++) c.fillRect(x - 0.6 * s + i * 0.25 * s, y - 0.4 * s, 0.18 * s, 0.26 * s); }
    c.beginPath(); c.rect(x - 0.45 * s, y - 1.3 * s, 0.9 * s, 1.3 * s); c.fillStyle = '#2a1d12'; c.fill(); inkStroke(c, s); c.stroke();
    if (o.shutters > 0) { const sh = (h - 0.6 * s) * clamp(o.shutters, 0, 1); c.fillStyle = P.ironDark; c.fillRect(L + 0.1 * s, T + 0.6 * s, w - 0.2 * s, sh); c.strokeStyle = P.ironLight; c.lineWidth = 1; for (let yy = T + 0.6 * s; yy < T + 0.6 * s + sh; yy += 0.12 * s) { c.beginPath(); c.moveTo(L + 0.1 * s, yy); c.lineTo(L + w - 0.1 * s, yy); c.stroke(); } }
    if (o.jammed) { c.strokeStyle = P.wood; c.lineWidth = 0.12 * s; c.beginPath(); c.moveTo(x - 0.55 * s, y - 1.25 * s); c.lineTo(x + 0.55 * s, y - 0.1 * s); c.moveTo(x + 0.55 * s, y - 1.25 * s); c.lineTo(x - 0.55 * s, y - 0.1 * s); c.stroke(); }
    if (b.mood === 'crane') { const k = b.crane || 0; c.strokeStyle = P.brass; c.lineWidth = 0.08 * s; c.beginPath(); c.moveTo(x + 0.3 * s, T + 2.1 * s); c.lineTo(x + (0.3 + 1.6 * k) * s * (o.facing || 1), y - 0.8 * s); c.stroke(); }
  },
  drawRoofSign(c, cx, cy, w, h, o = {}) {
    inkStroke(c, h / 0.9);
    roundRect(c, cx - w / 2, cy - h / 2, w, h, h * 0.12); c.fillStyle = P.ironDark; c.fill(); c.stroke();
    const text = String(o.text == null ? '' : o.text);
    const n = Math.max(6, text.length), tw = (w * 0.9) / n;
    const col = o.color === 'crimson' ? P.crimson : o.color === 'cyan' ? P.cyan : P.gold;
    c.font = 'bold ' + Math.round(tw * 1.25) + 'px ' + FONT.sign; c.textAlign = 'center'; c.textBaseline = 'middle';
    for (let i = 0; i < n; i++) {
      const ch = text[i - (n - text.length)] || ' ';
      const tx = cx - (w * 0.9) / 2 + tw * (i + 0.5);
      c.fillStyle = P.flap; c.fillRect(tx - tw * 0.44, cy - h * 0.34, tw * 0.88, h * 0.68);
      c.fillStyle = col; c.fillText(ch, tx, cy + 1);
    }
    if (o.hourglass) { c.fillStyle = P.goldHot; c.beginPath(); c.moveTo(cx + w / 2 + 6, cy - 12); c.lineTo(cx + w / 2 + 20, cy - 12); c.lineTo(cx + w / 2 + 6, cy + 12); c.lineTo(cx + w / 2 + 20, cy + 12); c.closePath(); c.fill(); }
  },
  drawBell(c, x, y, s, o = {}) {
    c.translate(x, y - 1.1 * s); c.rotate(Math.sin((o.t || 0) * 6) * 0.35 * (o.swing || 0));
    c.beginPath(); c.moveTo(-0.12 * s, 0.1 * s); c.quadraticCurveTo(-0.2 * s, 0.6 * s, -0.48 * s, 1.0 * s); c.lineTo(0.48 * s, 1.0 * s); c.quadraticCurveTo(0.2 * s, 0.6 * s, 0.12 * s, 0.1 * s); c.closePath();
    shade(c, -0.48 * s, 0, 0.96 * s, s, P.gold); inkStroke(c, s); c.stroke();
    if (o.shock > 0) { c.globalAlpha = 1 - o.shock; c.strokeStyle = P.goldHot; c.lineWidth = 3; c.beginPath(); c.arc(0, 0.9 * s, o.shock * 4 * s, 0, TAU); c.stroke(); }
  },
  drawBuyer(c, x, y, s, o = {}) {
    const by = y - 2.6 * s, f = o.facing || -1;
    c.fillStyle = P.emerald; c.beginPath(); c.ellipse(x + 0.6 * s * -f, by - 1.0 * s, 1.4 * s, 0.55 * s, 0, 0, TAU); c.fill(); inkStroke(c, s); c.stroke();
    c.beginPath(); c.rect(x - 0.6 * s, by - 0.25 * s, 1.2 * s, 0.4 * s); shade(c, x - 0.6 * s, by - 0.3 * s, 1.2 * s, 0.4 * s, P.brass); c.stroke();
    c.fillStyle = P.skin; c.beginPath(); c.arc(x, by - 0.42 * s, 0.17 * s, 0, TAU); c.fill(); c.stroke();
    c.fillStyle = P.tux; c.fillRect(x - 0.12 * s, by - 0.75 * s, 0.24 * s, 0.18 * s);
    if (o.tag) { c.strokeStyle = P.ink; c.lineWidth = 1; c.beginPath(); c.moveTo(x, by + 0.15 * s); c.lineTo(x, by + 0.45 * s); c.stroke(); roundRect(c, x - 0.38 * s, by + 0.45 * s, 0.76 * s, 0.32 * s, 0.05 * s); c.fillStyle = P.paper; c.fill(); c.stroke(); c.fillStyle = P.emeraldDark; c.font = 'bold ' + Math.round(0.2 * s) + 'px ' + FONT.deco; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(o.tag, x, by + 0.61 * s); }
  },
  drawMerchant(c, x, y, s, o = {}) {
    c.translate(x, y); inkStroke(c, s);
    c.beginPath(); c.arc(0, -0.22 * s, 0.22 * s, 0, TAU); c.fillStyle = P.ironDark; c.fill(); c.stroke();
    c.beginPath(); c.rect(-0.16 * s, -1.0 * s, 0.32 * s, 0.6 * s); shade(c, -0.16 * s, -1, 0.32 * s, 0.6 * s, P.trench); c.stroke();
    c.beginPath(); c.arc(0, -1.12 * s, 0.13 * s, 0, TAU); c.fillStyle = P.brass; c.fill(); c.stroke();
    roundRect(c, -0.42 * s, -1.6 * s, 0.84 * s, 0.3 * s, 0.05 * s); c.fillStyle = '#1a0b20'; c.fill(); c.strokeStyle = P.neonPink; c.lineWidth = 2; c.stroke();
    c.fillStyle = P.neonPink; c.font = 'bold ' + Math.round(0.18 * s) + 'px ' + FONT.sign; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(o.sign || '', 0, -1.45 * s);
  },
  drawRat(c, x, y, s, o = {}) { c.translate(x, y); c.scale(o.facing || 1, 1); c.fillStyle = '#7d7f86'; c.beginPath(); c.ellipse(0, -0.07 * s, 0.13 * s, 0.07 * s, 0, 0, TAU); c.fill(); inkStroke(c, s, LINE.inkThin); c.stroke(); c.beginPath(); c.moveTo(-0.12 * s, -0.06 * s); c.quadraticCurveTo(-0.3 * s, -0.2 * s, -0.36 * s, -0.02 * s); c.stroke(); c.fillStyle = P.crimson; c.beginPath(); c.arc(0.1 * s, -0.1 * s, 0.015 * s, 0, TAU); c.fill(); },
  drawAnvil(c, x, y, s, o = {}) {
    c.translate(x, y - (o.bounce || 0) * 0.3 * s); inkStroke(c, s);
    c.beginPath(); c.moveTo(-0.32 * s, -0.42 * s); c.lineTo(0.3 * s, -0.42 * s); c.lineTo(0.42 * s, -0.36 * s); c.lineTo(0.16 * s, -0.28 * s); c.lineTo(0.12 * s, -0.12 * s); c.lineTo(0.22 * s, 0); c.lineTo(-0.22 * s, 0); c.lineTo(-0.12 * s, -0.12 * s); c.lineTo(-0.16 * s, -0.28 * s); c.closePath();
    shade(c, -0.42 * s, -0.42 * s, 0.84 * s, 0.42 * s, P.iron); c.stroke();
    if (o.glow > 0) glow(c, 0, -0.3 * s, 0.6 * s, P.crimsonGlow, 0.4 * o.glow);
  },
  drawTether(c, x1, y1, x2, y2, s, o = {}) {
    const k = clamp(o.tension || 0, 0, 1), sag = (1 - k) * 0.6 * s, vib = k > 0.8 ? Math.sin((o.t || 0) * 60) * 2 : 0;
    c.strokeStyle = mix('#8a6a24', '#ff3b2f', k); c.lineWidth = Math.max(1.5, 0.03 * s); c.beginPath(); c.moveTo(x1, y1);
    c.quadraticCurveTo((x1 + x2) / 2, Math.max(y1, y2) + sag + vib, x2, y2); c.stroke();
  },
  drawStake(c, x, y, s, o = {}) {
    const col = o.golden ? P.gold : o.rusty ? '#8a4b2a' : P.brass;
    c.translate(x, y); inkStroke(c, s, LINE.inkThin);
    c.beginPath(); c.moveTo(-0.04 * s, 0); c.lineTo(-0.04 * s, -0.55 * s); c.lineTo(0, -0.62 * s); c.lineTo(0.04 * s, -0.55 * s); c.lineTo(0.04 * s, 0); c.closePath(); c.fillStyle = col; c.fill(); c.stroke();
    if (o.lit || o.golden) glow(c, 0, -0.58 * s, 0.22 * s, o.golden ? P.goldHot : P.gold, 0.7);
    if (o.label) { c.fillStyle = P.goldHot; c.font = 'bold ' + Math.round(0.16 * s) + 'px ' + FONT.deco; c.textAlign = 'center'; c.fillText(o.label, 0, -0.72 * s); }
  },
  drawWall(c, x, y, s, o = {}) { const b = clamp(o.build == null ? 1 : o.build, 0, 1), h = 0.9 * s * b; c.translate(x, y); c.beginPath(); c.rect(-0.16 * s, -h, 0.32 * s, h); shade(c, -0.16 * s, -h, 0.32 * s, h, P.brick); inkStroke(c, s); c.stroke(); c.strokeStyle = P.brickDark; c.lineWidth = 1; for (let yy = -0.15 * s; yy > -h; yy -= 0.15 * s) { c.beginPath(); c.moveTo(-0.16 * s, yy); c.lineTo(0.16 * s, yy); c.stroke(); } },
  drawCoin(c, cx, cy, r, o = {}) {
    const sp = Math.cos((o.spin || 0) * TAU);
    if (o.glow > 0) glow(c, cx, cy, r * 3, P.goldHot, 0.5 * o.glow);
    c.translate(cx, cy); c.scale(Math.max(0.15, Math.abs(sp)), 1);
    c.beginPath(); if (o.half) c.arc(0, 0, r, -Math.PI / 2, Math.PI / 2); else c.arc(0, 0, r, 0, TAU); c.closePath();
    c.fillStyle = o.wooden ? P.wood : mix(P.gold, '#6b6b55', clamp(o.tarnish || 0, 0, 1) * 0.7); c.fill(); inkStroke(c, r * 6, LINE.inkThin); c.stroke();
    c.strokeStyle = o.wooden ? darken(P.wood, 0.3) : P.goldDeep; c.lineWidth = Math.max(1, r * 0.15); c.beginPath(); c.arc(0, 0, r * 0.72, 0, TAU); c.stroke();
  },
  drawNote(c, cx, cy, s, o = {}) { c.translate(cx, cy); c.rotate(o.angle || 0); roundRect(c, -0.42 * s, -0.2 * s, 0.84 * s, 0.4 * s, 0.04 * s); c.fillStyle = '#9fd3a8'; c.fill(); inkStroke(c, s, LINE.inkThin); c.stroke(); c.fillStyle = P.emeraldDark; c.font = 'bold ' + Math.round(0.2 * s) + 'px ' + FONT.deco; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(o.label || '$1', 0, 0); },
  drawPistol(c, x, y, s, o = {}) { c.translate(x, y); c.scale(o.facing || 1, 1); c.rotate(-(o.recoil || 0) * 0.6); c.fillStyle = P.ironDark; c.fillRect(0, -0.04 * s, 0.26 * s, 0.07 * s); c.fillStyle = P.brass; c.fillRect(-0.02 * s, -0.02 * s, 0.07 * s, 0.14 * s); },
  drawMachete(c, x, y, s, o = {}) { c.translate(x, y); c.rotate(-1.2 + (o.swing || 0) * 2.4); c.fillStyle = P.rivet; c.beginPath(); c.moveTo(0, 0); c.lineTo(0.6 * s, -0.05 * s); c.lineTo(0.55 * s, 0.06 * s); c.closePath(); c.fill(); c.fillStyle = P.wood; c.fillRect(-0.15 * s, -0.03 * s, 0.15 * s, 0.07 * s); },
  drawBalloon(c, x, y, s, o = {}) { const k = clamp(o.inflate == null ? 1 : o.inflate, 0.05, 1), r = 0.65 * s * k; c.strokeStyle = P.ink; c.lineWidth = 1; c.beginPath(); c.moveTo(x, y); c.lineTo(x, y - 0.6 * s); c.stroke(); c.beginPath(); c.ellipse(x, y - 0.6 * s - r, r * 0.85, r, 0, 0, TAU); c.fillStyle = P.crimson; c.fill(); inkStroke(c, s); c.stroke(); if (o.words && k > 0.6) { c.fillStyle = P.paper; c.font = 'italic ' + Math.round(0.13 * s) + 'px ' + FONT.deco; c.textAlign = 'center'; c.fillText(o.words.slice(0, 22), x, y - 0.6 * s - r); } },
  drawBarrel(c, x, y, s, o = {}) { c.translate(x, y); c.beginPath(); c.ellipse(0, -0.42 * s, 0.34 * s, 0.45 * s, 0, 0, TAU); shade(c, -0.34 * s, -0.87 * s, 0.68 * s, 0.9 * s, P.barrel); inkStroke(c, s); c.stroke(); c.strokeStyle = P.barrelBand; c.lineWidth = 0.05 * s; for (const yy of [-0.2, -0.65]) { c.beginPath(); c.moveTo(-0.32 * s, yy * s); c.lineTo(0.32 * s, yy * s); c.stroke(); } },
  drawCollector(c, x, y, s, o = {}) { c.translate(x, y); inkStroke(c, s); c.beginPath(); c.rect(-0.2 * s, -1.3 * s, 0.4 * s, 1.3 * s); shade(c, -0.2 * s, -1.3 * s, 0.4 * s, 1.3 * s, P.collector); c.stroke(); c.beginPath(); c.arc(0, -1.45 * s, 0.16 * s, 0, TAU); c.fillStyle = '#d8d0c4'; c.fill(); c.stroke(); c.fillStyle = P.ironDark; c.fillRect(-0.18 * s, -1.66 * s, 0.36 * s, 0.1 * s); },
  drawJar(c, x, y, s, o = {}) { c.translate(x, y); const w = 0.38 * s, h = 0.5 * s; roundRect(c, -w / 2, -h, w, h, 0.06 * s); c.fillStyle = 'rgba(200,230,255,0.25)'; c.fill(); const f = clamp(o.fill || 0, 0, 1); c.fillStyle = P.gold; c.fillRect(-w / 2 + 3, -h * f + 0 - 2, w - 6, h * f); inkStroke(c, s, LINE.inkThin); roundRect(c, -w / 2, -h, w, h, 0.06 * s); c.stroke(); c.fillStyle = P.brass; c.fillRect(-w / 2 - 2, -h - 0.06 * s, w + 4, 0.07 * s); },
  drawRadio(c, x, y, s, o = {}) { c.translate(x, y); roundRect(c, -0.45 * s, -0.6 * s, 0.9 * s, 0.6 * s, 0.25 * s); shade(c, -0.45 * s, -0.6 * s, 0.9 * s, 0.6 * s, P.wood); inkStroke(c, s); c.stroke(); c.fillStyle = o.on ? P.goldHot : P.marbleDark; c.fillRect(-0.3 * s, -0.42 * s, 0.6 * s, 0.14 * s); },
  drawCabinet(c, x, y, s, o = {}) { c.translate(x, y); c.beginPath(); c.rect(-0.5 * s, -1.4 * s, 1.0 * s, 1.4 * s); c.fillStyle = 'rgba(180,220,255,0.18)'; c.fill(); inkStroke(c, s); c.strokeStyle = P.brassDark; c.stroke(); for (let i = 0; i < Math.min(o.coins || 0, 12); i++) FB.drawCoin(c, -0.3 * s + (i % 4) * 0.2 * s, -0.25 * s - Math.floor(i / 4) * 0.25 * s, 0.07 * s, {}); },
  drawTrophyShelf(c, x, y, s, o = {}) { c.translate(x, y); c.fillStyle = P.wood; c.fillRect(-0.7 * s, -0.06 * s, 1.4 * s, 0.06 * s); (o.trophies || []).slice(0, 5).forEach((t, i) => { c.fillStyle = P.gold; c.beginPath(); c.moveTo(-0.55 * s + i * 0.28 * s, -0.06 * s); c.lineTo(-0.45 * s + i * 0.28 * s, -0.06 * s); c.lineTo(-0.42 * s + i * 0.28 * s, -0.3 * s); c.lineTo(-0.58 * s + i * 0.28 * s, -0.3 * s); c.fill(); }); },
  drawCoinStack(c, x, y, s, o = {}) { const n = clamp(Math.round(Math.log10(1 + (o.usd || 0) * 10) * 5), 1, 14); for (let i = 0; i < n; i++) { c.beginPath(); c.ellipse(x, y - i * 0.05 * s, 0.22 * s, 0.07 * s, 0, 0, TAU); c.fillStyle = i % 2 ? P.gold : P.goldDeep; c.fill(); inkStroke(c, s, LINE.inkThin); c.stroke(); } },
  drawPageCorner(c, x, y, s, o = {}) { const r = (o.hover ? 0.75 : 0.6) * s; c.beginPath(); c.moveTo(x, y); c.lineTo(x - r, y); c.lineTo(x, y - r); c.closePath(); c.fillStyle = P.paper; c.fill(); inkStroke(c, s, LINE.inkThin); c.stroke(); },
  drawHoldRing(c, cx, cy, r, frac, o = {}) {
    c.lineCap = 'round';
    c.strokeStyle = 'rgba(26,20,16,0.55)'; c.lineWidth = Math.max(4, r * 0.28); c.beginPath(); c.arc(cx, cy, r, 0, TAU); c.stroke();
    c.strokeStyle = o.color || P.gold; c.lineWidth = Math.max(3, r * 0.2); c.beginPath(); c.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + TAU * clamp(frac, 0, 1)); c.stroke();
    if (o.label) { c.fillStyle = P.paper; c.font = 'bold ' + Math.round(r * 0.7) + 'px ' + FONT.deco; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(o.label, cx, cy + 1); }
  },
};

// ======================================================================================================== placeholder world (fallbacks)
function skyKey(env) {
  if (env.freeze) return 'freeze';
  if (env.weather === 'storm') return 'storm';
  if (env.night || env.session === 'dead' || env.session === 'closed') return 'night';
  if (env.weather === 'dead') return 'dead';
  if (env.golden_hour) return 'golden';
  if (env.session === 'asia') return 'dawn';
  if (env.session === 'newyork') return 'afternoon';
  return 'noon';
}
const FBW = {
  drawSky(c, w, h, env, t) {
    const k = SKY[skyKey(env)] || SKY.noon;
    const g = c.createLinearGradient(0, 0, 0, h * 0.75);
    k.forEach((col, i) => g.addColorStop(i / (k.length - 1), col));
    c.fillStyle = g; c.fillRect(-10, -10, w + 20, h + 20);
    const sx = w * (0.08 + 0.84 * ((env.day_frac + 0.75) % 1)), sy = h * (0.62 - 0.45 * Math.sin(Math.PI * ((env.day_frac + 0.75) % 1)));
    if (skyKey(env) !== 'storm' && !env.night) { glow(c, sx, sy, h * 0.18, P.goldHot, 0.5); c.fillStyle = '#fff6d0'; c.beginPath(); c.arc(sx, sy, h * 0.035, 0, TAU); c.fill(); }
  },
  drawSkyline(c, w, h, camX, env, t) {
    for (let layer = 0; layer < 2; layer++) {
      const par = layer ? 0.5 : 0.25, base = h * 0.725, col = layer ? 'rgba(40,36,48,0.55)' : 'rgba(60,56,70,0.35)';
      c.fillStyle = col;
      for (let i = -2; i < 26; i++) {
        const bw = w * (0.04 + 0.03 * rand(i * 7 + layer)), bh = h * (0.12 + 0.28 * rand(i * 13 + layer * 3)) * (layer ? 0.8 : 1.1);
        const x = ((i * w * 0.055 - camX * par) % (w * 1.4) + w * 1.4) % (w * 1.4) - w * 0.2;
        c.fillRect(x, base - bh, bw, bh);
        c.beginPath(); c.moveTo(x, base - bh); c.lineTo(x + bw / 2, base - bh - bw * 0.6); c.lineTo(x + bw, base - bh); c.fill();
      }
    }
  },
  terrainH(terrain, xn) {
    if (!terrain || !terrain.h || !terrain.h.length) return 0.2;
    const n = terrain.h.length, u = ((xn - terrain.x0) / (terrain.x1 - terrain.x0)) * n - 0.5;
    const i = Math.floor(u), f = u - i, a = terrain.h[clamp(i, 0, n - 1)], b = terrain.h[clamp(i + 1, 0, n - 1)];
    return a + (b - a) * f;
  },
  groundYAt(view, terrain, xn) {
    const xs = view.xToScreen(xn);
    return view.groundY + (xs - view.pivotX) * Math.tan(view.tiltRad) - FBW.terrainH(terrain, xn) * 0.5 * view.s;
  },
  drawTerrain(c, view, terrain, env, t) {
    const x0 = -0.45, x1 = 1.35, N = 120, pts = [];
    for (let i = 0; i <= N; i++) { const xn = x0 + ((x1 - x0) * i) / N; pts.push([view.xToScreen(xn), FBW.groundYAt(view, terrain, xn), xn]); }
    const bottom = view.h + 400;
    c.beginPath(); c.moveTo(pts[0][0], bottom); pts.forEach((p) => c.lineTo(p[0], p[1])); c.lineTo(pts[N][0], bottom); c.closePath();
    const g = c.createLinearGradient(0, view.groundY - view.s, 0, view.h);
    g.addColorStop(0, P.marble); g.addColorStop(0.18, P.marbleShade); g.addColorStop(0.2, P.ledger); g.addColorStop(1, P.gear);
    c.fillStyle = g; c.fill();
    inkStroke(c, view.s); c.beginPath(); pts.forEach((p, i) => (i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1]))); c.stroke();
    (terrain && terrain.chasms || []).forEach(([a, b]) => {
      const xa = view.xToScreen(a), xb = view.xToScreen(b), ya = FBW.groundYAt(view, terrain, a), yb = FBW.groundYAt(view, terrain, b);
      c.beginPath(); c.moveTo(xa, ya); c.lineTo(xb, yb); c.lineTo((xa + xb) / 2, view.h + 50); c.closePath(); c.fillStyle = P.voidc; c.fill(); c.strokeStyle = P.voidEdge; c.lineWidth = 3; c.stroke();
    });
    (terrain && terrain.scorch || []).forEach((xn) => { const x = view.xToScreen(xn), y = FBW.groundYAt(view, terrain, xn); c.fillStyle = P.scorch; c.beginPath(); c.ellipse(x, y + 3, 0.25 * view.s, 0.06 * view.s, view.tiltRad, 0, TAU); c.fill(); });
  },
  drawPit(c, view, pit, env, t) {
    if (!pit) return;
    const xa = view.xToScreen(pit.x0), xb = view.xToScreen(pit.x1), x = (xa + xb) / 2, w = Math.max(0.5 * view.s, Math.abs(xb - xa));
    const y = view.groundY + (x - view.pivotX) * Math.tan(view.tiltRad);
    c.fillStyle = P.molasses; c.beginPath(); c.ellipse(x, y + 2, w / 2 + 0.1 * view.s, 0.12 * view.s + pit.depth * 0.1 * view.s, view.tiltRad, 0, TAU); c.fill();
    c.fillStyle = P.molassesHi; c.beginPath(); c.ellipse(x - w * 0.1, y, w * 0.3, 0.05 * view.s, view.tiltRad, 0, TAU); c.fill();
  },
  drawFog(c, view, fromXn, env, t) {
    const xa = view.xToScreen(fromXn), xb = view.xToScreen(fromXn + 0.3);
    const g = c.createLinearGradient(xa, 0, xb, 0); g.addColorStop(0, 'rgba(235,235,245,0)'); g.addColorStop(1, 'rgba(235,235,245,0.85)');
    c.fillStyle = g; const L = Math.min(xa, view.mirror ? 0 : xa), R = view.mirror ? xa : view.w; c.fillRect(Math.min(L, R), 0, Math.abs(R - L) + 1, view.h);
  },
  drawWeather(c, w, h, env, dt, t) {
    if (env.weather === 'storm') { c.strokeStyle = 'rgba(243,240,230,0.5)'; c.lineWidth = 2; for (let i = 0; i < 60; i++) { const x = (rand(i) * w + t * 80 * (0.5 + rand(i + 9))) % w, y = (rand(i * 3) * h + t * 300) % h; c.beginPath(); c.moveTo(x, y); c.lineTo(x - 4, y + 12); c.stroke(); } }
    if (env.weather === 'dead') { c.fillStyle = 'rgba(189,182,168,0.6)'; for (let i = 0; i < 50; i++) { const x = (rand(i) * w + Math.sin(t + i) * 20) % w, y = (rand(i * 5) * h + t * 25) % h; c.fillRect(x, y, 2, 2); } }
  },
  drawSeasonBand(c, w, env, t) {
    const g = c.createLinearGradient(0, 0, 0, 14); g.addColorStop(0, 'rgba(26,20,16,0.55)'); g.addColorStop(1, 'rgba(26,20,16,0)'); c.fillStyle = g; c.fillRect(0, 0, w, 14);
    const dir = env.season >= 0 ? 1 : -1, col = env.season >= 0 ? P.leaf : P.snow;
    c.fillStyle = col; for (let i = 0; i < 24; i++) { const x = (((rand(i) * w + t * 30 * dir * (env.mirror ? -1 : 1)) % w) + w) % w; c.fillRect(x, 3 + rand(i * 2) * 6, 4, 3); }
  },
  drawGrade(c, w, h, env, t) {
    if (env.freeze) { c.fillStyle = 'rgba(112,86,50,0.45)'; c.fillRect(0, 0, w, h); for (let i = 0; i < 400; i++) { c.fillStyle = Math.random() < 0.5 ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)'; c.fillRect(Math.random() * w, Math.random() * h, 2, 2); } }
    else if (env.night) { c.fillStyle = 'rgba(10,16,48,0.38)'; c.fillRect(0, 0, w, h); }
    else if (env.golden_hour) { c.fillStyle = 'rgba(255,150,40,0.16)'; c.fillRect(0, 0, w, h); }
    if (env.wooden) { c.fillStyle = 'rgba(176,122,62,0.10)'; c.fillRect(0, 0, w, h); }
    if (env.replay) SCR.drawReplayFallback(c, w, h, t);
  },
};

// ======================================================================================================== placeholder FX (fallback)
const FBFX = {
  parts: [], sh: 0, shT: 0, shD: 1, off: [0, 0],
  burst(kind, x, y, o = {}) {
    const n = o.n || ({ dust: 10, smoke: 8, sparks: 14, shavings: 8, cash: 16, bubbles: 8, ticker: 12, confetti: 20, chips: 10 }[kind] || 8);
    const col = { dust: '#d8c9a8', smoke: '#3a3a3a', sparks: '#ffd27a', shavings: '#ffe08a', cash: '#9fd3a8', bubbles: '#f0e0b0', ticker: '#f3f0e6', confetti: '#ff4fd8', chips: '#e0303a' }[kind] || '#fff';
    for (let i = 0; i < n && this.parts.length < 400; i++) {
      const a = Math.random() * TAU, v = 40 + Math.random() * 160;
      this.parts.push({ kind, x, y, vx: Math.cos(a) * v + (o.dir || 0) * 60, vy: Math.sin(a) * v - 60, life: 0.6 + Math.random() * 0.8, age: 0, col, to: o.to || null, r: kind === 'smoke' ? 6 : 2.5 });
    }
  },
  update(dt) {
    for (const p of this.parts) {
      p.age += dt;
      if (p.to) { const k = clamp(p.age / p.life, 0, 1); p.x += (p.to[0] - p.x) * Math.min(1, dt * 4); p.y += (p.to[1] - p.y) * Math.min(1, dt * 4) - Math.sin(k * Math.PI) * 2; }
      else { p.vy += (p.kind === 'smoke' || p.kind === 'bubbles' ? -60 : 260) * dt; p.x += p.vx * dt; p.y += p.vy * dt; }
    }
    this.parts = this.parts.filter((p) => p.age < p.life);
    if (this.shT > 0) { this.shT -= dt; const k = this.sh * Math.max(0, this.shT / this.shD); this.off = [(Math.random() * 2 - 1) * k, (Math.random() * 2 - 1) * k]; } else this.off = [0, 0];
  },
  draw(c) { for (const p of this.parts) { c.globalAlpha = 1 - p.age / p.life; c.fillStyle = p.col; c.beginPath(); c.arc(p.x, p.y, p.r + (p.kind === 'smoke' ? p.age * 14 : 0), 0, TAU); c.fill(); } c.globalAlpha = 1; },
  shake(a, d) { this.sh = Math.max(this.sh * Math.max(0, this.shT / this.shD), a); this.shT = d || 0.4; this.shD = d || 0.4; },
  offset() { return this.off; },
  clear() { this.parts = []; },
  setScale() { /* the placeholder particles do not scale */ },
};

// ======================================================================================================== state
const net = createNet({ fixture: FIXTURE, base: import.meta.url });
const G = {
  W: 1600, H: 900, dpr: 1, t: 0, now: 0, timeScale: 1, slowmo: 0,
  snap: null, phase: null, prevPhase: null, firstPhase: null,
  L: null, env: null, lobbyL: null, settleL: null,
  hold: null, drag: null, hover: null, pointer: { x: -1, y: -1, down: false },
  ui: { kind: 'wooden', plain: null, rest: false, safetyOpen: false, debug: DEBUG, noteBack: 0, flash: null },
  settle: null, pendings: {}, refusedNonces: new Set(),
  last: null, echoes: [], frames: 0, fps: 0,
};
const D = { x: null, tilt: 0, v: 0, pan: 0, mx: null, twinX: null, anvilX: null, tpX: null, side: 1, mirror: false, flip: null, roll: 0,
  lastTick: null, tiltSign: 0, desk: 1, freezeK: 0, distance: 0, lastAnvilKind: null };
const A = { bellSwing: 0, bellShock: 1, anvilBounce: 0, buyerMood: null, buyerT: 0, bankerMood: null, bankerT: 0, rat: null,
  walls: new Map(), stakeFlash: [], fillSign: 0, fillPrice: null, coinArc: null, recoil: 0, lightning: 0, machete: 0, tackle: 0,
  balloon: 0, smoke: 0, dustT: 0, ropeTug: 0, refuse: null, noteBounce: 0, shutterRattle: 0, collectorT: 0, needle: 0, stampT: 0, pistons: 0 };
window.GG = { G, D, A, net, debug: {}, MISSES, ERRORS: null };

// ======================================================================================================== helpers
const fmtPrice = (p) => { const dp = (G.snap && G.snap.settings && G.snap.settings.price_dp) || 2; return isFinite(p) ? Number(p).toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp }) : ''; };
function riskOf(snap) { return (snap && snap.settings && snap.settings.risk_usd) || (snap && snap.round && snap.round.risk_usd) || 0.01; }
function fmtMoney(usd, snap) { return money(usd, riskOf(snap)); }
function interpPath(path, age) {
  if (!path || !path.length) return null;
  if (age <= path[0][0]) return path[0][1];
  for (let i = 1; i < path.length; i++) {
    if (path[i][0] >= age) { const [a0, x0] = path[i - 1], [a1, x1] = path[i]; return x0 + ((x1 - x0) * (age - a0)) / Math.max(1e-6, a1 - a0); }
  }
  return null;                                                  // the ghost's round was over by this age
}
function easeTo(cur, target, k, dt) { return cur == null || !isFinite(cur) ? target : cur + (target - cur) * (1 - Math.exp(-k * dt)); }
function inRound(ph) { return ph === 'sending' || ph === 'open' || ph === 'closing' || ph === 'settled'; }
// a stop that filled at or above break-even locked a gain in: drawn as a win (LOCKED IN, cyan, standing), never as the ordinary loss
function stopWon(st) { return !!st && (st.outcome === 'anvil' || st.outcome === 'barrel') && isFinite(st.result_usd) && st.result_usd >= 0; }

// ======================================================================================================== layout / camera (CONTRACT 8.1)
function computeLayout() {
  const W = G.W, H = G.H, snap = G.snap;
  const s = Math.min((W * 93) / 1600, (H * 93) / 900);
  const mirror = D.mirror;
  const span = 1.78, lo = -0.42 + D.pan;                       // a little more room beyond the target for the boss's group
  const xToScreen = (xn) => { const u = (xn - lo) / span; return mirror ? W * (1 - u) : W * u; };
  const xFromScreen = (px) => lo + span * (mirror ? 1 - px / W : px / W);
  const groundY = H * 0.725;
  const runnerX = D.x == null ? 0.45 : D.x;
  const pivotX = xToScreen(runnerX);
  // the street seesaws about the runner (max VIS_TILT_DEG at |tilt| = 1); its ends stay on screen and the bank end never climbs
  // above the bank's door, so the facade is never buried (the bank stands on its own pier and does not tilt)
  let tn = Math.tan(clamp(D.tilt, -1, 1) * VIS_TILT_DEG * DEG * (mirror ? -1 : 1));
  const maxDown = H * 0.965 - groundY;
  for (const [xe, maxUp] of [[-0.02, 1.55 * s], [1.15, groundY - H * 0.36]]) {
    const d = xToScreen(xe) - pivotX;
    if (Math.abs(d) < 1) continue;
    const dy = d * tn;
    if (dy > maxDown) tn = maxDown / d; else if (dy < -maxUp) tn = -maxUp / d;
  }
  const tiltRad = Math.atan(tn);
  const view = { xToScreen, groundY, tiltRad, pivotX, w: W, h: H, s, mirror };
  const r = snap && snap.round, pv = snap && snap.preview, st = snap && snap.settlement;
  let terrain = (inRound(G.phase) && r ? r.terrain : pv ? pv.terrain : r ? r.terrain : null) || { x0: -0.3, x1: 1.3, h: [], chasms: [], scorch: [], weathered: [] };
  if (st && st.chasm && G.phase === 'settled') terrain = { ...terrain, chasms: [...(terrain.chasms || []), st.chasm] };
  const facing = mirror ? -1 : 1;
  // Zee 2026-11-04: two regimes, one world - the bank is always on the left and the mafia always on the right. Buying: rob the bank, carry
  // the coin right to the mafia. Selling (the mirrored street): rob the mafia, carry the coin left to the bank, whose Guard waits at the target.
  const bankX = mirror ? xToScreen(D.tpX || 1) - 1.62 * s : xToScreen(-0.22), bankY = groundY;
  const bank = { x: bankX, y: bankY, w: 2.6 * s, h: 3.1 * s, top: bankY - 3.1 * s, dest: !!mirror };
  const geo = cottageGeometry(bankX, bankY, s, 1);
  if (geo && geo.sign && isFinite(geo.sign.cy)) {               // art.js knows where its sign, belfry and banker sit
    bank.sign = { ...geo.sign }; bank.bell = { ...geo.bell }; bank.banker = { ...geo.banker };
    bank.door = geo.door ? { ...geo.door } : null; bank.step = geo.step ? { ...geo.step } : null;
    bank.guard = geo.guard ? { ...geo.guard } : null;
  } else {
    bank.sign = { cx: bankX, cy: bankY - 5.12 * s, w: 2.2 * s, h: 0.9 * s };
    bank.bell = { x: bankX, y: bankY - 5.57 * s };
    bank.banker = { x: bankX, y: bankY - 2.45 * s, w: 1.1 * s, h: 1.4 * s };
    bank.door = { x: bankX, y: bankY - 0.25 * s, w: 1.0 * s, h: 1.2 * s }; bank.step = { x: bankX, y: bankY - 0.25 * s };
  }
  const roll = D.roll, rollScale = 1 + Math.abs(Math.sin(roll)) * 1.3;
  G.L = { W, H, s, mirror, facing, lo, span, xToScreen, xFromScreen, groundY, pivotX, pivotY: groundY, tiltRad, view, terrain, bank, roll, rollScale,
    gy: (xn) => groundYAt(view, terrain, xn) };
  G.L.jar = { x: W * 0.035 + 0.3 * s, y: H - 0.3 * s };
  G.L.eject = { x: W - 0.95 * s, y: H - 0.95 * s, r: 0.42 * s };
  if (MOD.fx && G.fxScale !== s) { G.fxScale = s; FXK.call('setScale', [s]); }   // particles sized in units, like everything else
  return G.L;
}
function applyCamera(c, sx, sy) {
  const L = G.L;
  c.translate(sx, sy);
  if (D.flip) { const k = Math.max(0.015, Math.abs(Math.cos(Math.PI * D.flip.p))); c.translate(L.W / 2, 0); c.scale(k, 1); c.translate(-L.W / 2, 0); }
  if (L.roll) { c.translate(L.pivotX, L.pivotY); c.rotate(L.roll); c.scale(L.rollScale, L.rollScale); c.translate(-L.pivotX, -L.pivotY); }
}
function toLayout(px, py) {                     // pointer -> layout coordinates (inverse camera roll; the shake is never applied to hit boxes)
  const L = G.L;
  if (!L || !L.roll) return [px, py];
  const dx = (px - L.pivotX) / L.rollScale, dy = (py - L.pivotY) / L.rollScale, c = Math.cos(-L.roll), s = Math.sin(-L.roll);
  return [L.pivotX + dx * c - dy * s, L.pivotY + dx * s + dy * c];
}

// ======================================================================================================== interpolation
function updateInterp(dt) {
  const snap = G.snap; if (!snap) return;
  if (G.phase === 'lobby' && !robbing && !A.volley) G.ui.kind = snap.limits && snap.limits.live_allowed ? 'live' : 'wooden';   // no plates to pick from any more
  if (G.phase === 'lobby' && !robbing && !A.volley) { A.robbedSide = null; A.knockAt = null; }
  const ph = G.phase, r = snap.round, pv = snap.preview;
  const frozen = net.frozen();
  D.freezeK = easeTo(D.freezeK, frozen ? 1 : 0, 6, G.realDt || 0.016);      // the needle moves on real time
  const side = (inRound(ph) && r ? r.side : pv ? pv.side : snap.settings ? snap.settings.side : 1) || 1;
  const wantMirror = side < 0;
  if (wantMirror !== D.mirror) { D.mirror = wantMirror; D.flip = null; }   // Zee 2026-11-04: no page-flip animation (bank and mafia never move anyway)
  if (D.flip) { D.flip.p += dt / 0.75; if (D.flip.p >= 0.5 && D.mirror !== D.flip.to) D.mirror = D.flip.to; if (D.flip.p >= 1) D.flip = null; }
  // A page that opens (or reloads) inside a freeze has never eased toward anything: seed the picture from the snapshot first, so the
  // frozen street shows the true result (runner, outfit, Merchant, anvil, Buyer) and not a default spot - the Golden Rule holds in sepia.
  if (D.x == null) {
    if (inRound(ph) && r && isFinite(r.x)) {
      D.x = r.x; D.tilt = clamp(r.tilt || 0, -1, 1);
      if (r.merchant && isFinite(r.merchant.x)) D.mx = r.merchant.x;
      if (r.anvil && isFinite(r.anvil.x)) D.anvilX = r.anvil.x;
      if (r.twin && isFinite(r.twin.x)) D.twinX = r.twin.x;
      if (isFinite(r.x_tp)) { D.tpX = r.x_tp; D.pan = Math.max(0, r.x_tp - 1.1); }
    } else if (pv && isFinite(pv.x_entry)) { D.x = pv.x_entry; D.tilt = clamp((pv.tilt || 0) * (ph === 'lobby' ? 0.55 : 1), -1, 1); D.tpX = 1.0; D.anvilX = 0; }
  }
  if (frozen) return;                                       // Time Freeze: the picture holds still
  let tx, tt;
  if (inRound(ph) && r) { tx = r.x; tt = G.settle && G.settle.stage === 'desk' ? 0 : r.tilt; }   // behind the desk the street comes to rest
  else if (pv) { tx = pv.x_entry; tt = (pv.tilt || 0) * (ph === 'lobby' ? 0.55 : 1); }
  else { tx = 0.45; tt = 0; }
  if (!isFinite(tx)) tx = 0.45;
  const prev = D.x;
  const jump = prev != null && Math.abs(tx - prev) > 0.08;
  if (jump && D.wasFrozen) snd('whoosh');
  D.x = easeTo(D.x, tx, jump ? 6 : 11, dt);
  if (prev != null && dt > 0) D.v = easeTo(D.v, (D.x - prev) / dt, 5, dt);
  D.tilt = easeTo(D.tilt, clamp(tt || 0, -1, 1), 4.5, dt);
  D.roll = easeTo(D.roll, G.L ? G.L.tiltRad * 0.1 : 0, 2.5, dt);
  if (r && inRound(ph)) {
    if (r.merchant) D.mx = easeTo(D.mx, r.merchant.x, 4, dt);
    if (r.twin) D.twinX = easeTo(D.twinX, r.twin.x, 8, dt);
    if (r.anvil) D.anvilX = easeTo(D.anvilX, r.anvil.x, 7, dt);
    D.tpX = easeTo(D.tpX, r.x_tp, 3, dt);
  } else if (pv) {
    D.tpX = easeTo(D.tpX, 1.0, 3, dt); D.anvilX = easeTo(D.anvilX, 0, 6, dt);
  }
  // the camera pans just enough to keep the whole zeppelin (its tail and propeller reach 1.65 units past the Buyer) on screen after a
  // haggle, on any aspect ratio (CONTRACT 8.1: the full ladder stays visible; haggles past 1.1 pan the camera)
  const sNow = G.L ? G.L.s : Math.min((G.W * 93) / 1600, (G.H * 93) / 900);
  const ovf = (((D.tpX || 1) + 0.42) / 1.62) * G.W + 1.65 * sNow - (G.W - 6);
  const wantPan = Math.max(0, (D.tpX || 1) - 1.1, (ovf / G.W) * 1.62);
  D.pan = easeTo(D.pan, wantPan, 2, dt);
  D.wasFrozen = false;
  // footsteps: one per tick increment, at most two per frame however far the count jumped
  const tc = snap.feed ? snap.feed.tick_count : null;
  if (tc != null) {
    if (D.lastTick != null && tc > D.lastTick) {
      const n = Math.min(2, tc - D.lastTick), wood = r ? r.kind === 'wooden' : G.ui.kind === 'wooden';
      for (let i = 0; i < n; i++) snd('footstep', { intensity: clamp(0.35 + Math.abs(D.v) * 6 + (snap.feed.ticks_per_s || 2) * 0.05, 0, 1), wooden: wood, delay: i * 0.07, x: G.L ? G.L.pivotX / G.L.W : 0.5 });
    }
    D.lastTick = tc;
  }
  // pistons when the tilt changes sign (with hysteresis)
  const sg = D.tilt > 0.08 ? 1 : D.tilt < -0.08 ? -1 : D.tiltSign;
  if (sg !== D.tiltSign && D.tiltSign !== 0 && inRound(ph)) { snd('pistons', { dir: sg, amount: clamp(Math.abs(D.tilt) * 2, 0.3, 1) }); A.pistons = 1; if (G.L) FXK.burst('sparks', G.L.pivotX, G.L.groundY + 0.3 * G.L.s, { n: 8 }); }
  D.tiltSign = sg;
}

// ======================================================================================================== events (CONTRACT 7.3)
function bankerPos() { const L = G.L; return L ? [L.bank.banker.x, L.bank.banker.y] : [0, 0]; }
function guardPos() { const L = G.L; if (L && L.mirror && D.goonPos) return D.goonPos; const g = L && (L.bank.guard || L.bank.banker); return g ? [g.x, g.y] : [0, 0]; }
function coinFrom() { return guardPos(); }   // Zee 2026-11-04: the coin drops from the very man who was shot (the guard / the front henchman)
// a barrel drags him across the chasm into the Vault: a fill far through the stop maps beyond the screen's edge, so he (and the barrel
// over him) is drawn at the bank's door, never off screen. Only the picture: the receipt carries the deal's real number.
function barrelXn(xn) {
  const L = G.L, st = G.snap && G.snap.settlement;
  if (G.phase === 'settled' && st && st.outcome === 'barrel' && L && L.bank && isFinite(xn)) return Math.max(xn, L.xFromScreen(L.bank.x));
  return xn;
}
function runnerPos() { const L = G.L; if (!L) return [0, 0]; const xn = barrelXn(D.x == null ? 0.45 : D.x); return [L.xToScreen(xn), L.gy(xn)]; }
function coinPos() {
  if (ptsOK(D.pts, 'coinX') && D.pts.coinR > 0) return [D.pts.coinX, D.pts.coinY];
  const [x, y] = runnerPos(); const s = G.L ? G.L.s : 95; return [x + 0.15 * s * (G.L ? G.L.facing : 1), y - 0.55 * s];
}
function beltPos() {
  if (ptsOK(D.pts, 'beltX')) return [D.pts.beltX, D.pts.beltY];
  const [x, y] = runnerPos(); const s = G.L ? G.L.s : 95; return [x, y - 0.5 * s];
}
function jarPos() { if (G.lobbyL && G.phase === 'lobby') return [G.lobbyL.jar.x, G.lobbyL.jar.y - 0.3 * G.L.s]; if (G.settleL && G.settle && G.settle.stage === 'desk') return [G.settleL.jar.x, G.settleL.jar.y - 0.3 * G.L.s]; return [G.L.jar.x, G.L.jar.y - 0.3 * G.L.s]; }

function handleEv(ev) {
  if (!ev || !ev.type) return;
  const L = G.L, s = L ? L.s : 95;
  G.echoes.push({ t: +G.now.toFixed(0), ...ev }); if (G.echoes.length > 20) G.echoes.shift();
  switch (ev.type) {
    case 'accepted': G.last = { ...(G.last || {}), echo: 'accepted', action: ev.action }; delete G.pendings[ev.action]; break;
    case 'refused': if (!G.refusedNonces.has(ev.nonce)) { G.refusedNonces.add(ev.nonce); refusalFx(ev.action, ev.why); } G.last = { ...(G.last || {}), echo: 'refused', why: ev.why, action: ev.action }; delete G.pendings[ev.action]; break;
    case 'refused_broker': refusalFx(ev.action, ev.why || 'broker'); break;
    case 'fill': {
      A.dig = { t: 0, dur: 1.1 };                               // the rat digs the spread pit now, on the trade's side
      const [bx, by] = coinFrom();
      { const L3 = G.L, r3 = G.snap && G.snap.round; G.lastCoin = { from: [bx, by], side: r3 ? r3.side : null, mirror: !!(L3 && L3.mirror),
        bank: L3 && L3.bank ? [L3.bank.banker.x, L3.bank.banker.y] : null, boss: D.bossPos ? [...D.bossPos] : null }; }   // for the self-test (window.__gg)
      A.coinArc = { t: 0, from: [bx, by], dur: 0.7 };
      { const L2 = G.L, s2 = L2 ? L2.s : 0, back = L2 ? (L2.mirror ? -1 : 1) * 0.35 * s2 : 0;   // run to the fallen man and pick the coin up beside him
        const toY = L2 ? (L2.mirror ? L2.gy(L2.xFromScreen(bx + back)) : L2.bank.y) : by;
        A.fetch = { t: 0, dur: 1.4, to: bx + back, toY }; }
      snd('coin'); FXK.burst('smoke', bx, by, { n: 10 }); A.smoke = 1.2;
      setTimeout(() => { const [x, y] = runnerPos(); FXK.burst('bubbles', x, y, { n: 12 }); snd('molasses'); FXK.shake(3, 0.3); }, 700);
      break;
    }
    case 'bell': A.bellSwing = 1; A.bellShock = 0; snd('bell', { session: ev.session }); FXK.shake(5, 0.8); break;
    case 'rat': startRat(ev); break;            // the snips play when the teeth meet the coin
    case 'stake': A.stakeFlash.push({ x: ev.x, t: 0 }); snd('stake'); if (L) FXK.burst('sparks', L.xToScreen(ev.x), L.gy(ev.x) - 0.6 * s, { n: 10 }); break;
    case 'anvil':
      if (ev.ok) { snd('anvil'); FXK.shake(4, 0.35); if (L) FXK.burst('sparks', L.xToScreen(ev.x), L.gy(ev.x) - 0.2 * s, { n: 16 }); }
      else refusalFx('anvil_next', ev.why || 'refused');
      break;
    case 'wall':
      if (ev.ok) { A.walls.set(String(ev.x), 0); snd('wall', { n: 6 }); if (L) FXK.burst('dust', L.xToScreen(ev.x), L.gy(ev.x), { n: 14 }); }
      else refusalFx('wall', ev.why || 'refused');
      break;
    case 'haggle':
      if (ev.ok) { const r = G.snap && G.snap.round; A.buyerMood = r && r.haggles >= r.haggle_max ? 'wave_off' : 'laugh'; A.buyerT = 1.8; snd('haggle', { ok: true }); }
      else refusalFx('haggle', ev.why || 'refused');
      break;
    case 'machete':
      if (ev.ok) { A.machete = 1; G.slowmo = 0.9; snd('machete'); setTimeout(() => snd('chime'), 450); setTimeout(() => snd('stake', { golden: true }), 900); const [x, y] = coinPos(); FXK.burst('sparks', x, y, { n: 18 }); FXK.burst('cash', x, y, { n: 6 }); }
      else refusalFx('machete', ev.why || 'refused');
      break;
    case 'settled': startSettle(ev.outcome); break;
    case 'lightning': {                                          // Zee 2026-11-06: lightning only under a risky sky (risk level 2-3), never in the sun
      const rk = (G.snap && G.snap.market && G.snap.market.risk) || {};
      if (rk.level == null || rk.level >= 2) { A.lightning = 1; FXK.shake(6, 0.5); setTimeout(() => snd('thunder', { near: true }), 280); }
      break;
    }
    case 'freeze': A.needle = 1; break;                      // the needle's sound plays on the frozen transition in frame(), once
    default: break;
  }
}

function startRat(ev) {
  const r = G.snap && G.snap.round;
  const from = r && r.anvil ? r.anvil.x : 0;
  A.rat = { t: 0, from, why: ev.why, usd: ev.usd, bit: false };
}

let lastRefusalSound = 0;
function refuseSnd(name, opts) {                              // a refusal is voiced once, however many messages report it
  const now = performance.now();
  if (now - lastRefusalSound < 450) return;
  lastRefusalSound = now; snd(name, opts);
}
const lastRefuseFx = {};
function refusalFx(action, why) {
  const L = G.L, s = L ? L.s : 95, nowMs = performance.now();
  // the act reply, the 'refused' / 'refused_broker' / result events and round.last_refusal can all report one refusal: show it once
  if (lastRefuseFx[action] && nowMs - lastRefuseFx[action] < 1500) return;
  lastRefuseFx[action] = nowMs;
  A.refuse = { action, why, t: 0 };
  if (why === 'frozen' || why === 'stale') { snd('needle', { up: true }); A.needle = 1; return; }
  const voice = { anvil_next: ['anvil', { ok: false }], wall: ['wall', { ok: false }], haggle: ['haggle', { ok: false }], shoot: ['duck', {}] }[action];
  if (voice) refuseSnd(voice[0], voice[1]); else refuseSnd('refused');
  switch (action) {
    case 'fund': A.noteBounce = 1; if (G.snap && G.snap.market && G.snap.market.shutters.down) A.shutterRattle = 1; break;
    case 'shoot': { A.bankerMood = 'sulk'; A.bankerT = 1.2; const [bx, by] = bankerPos(); FXK.burst('sparks', bx, by, { n: 12 }); FXK.burst('smoke', bx, by, { n: 5 }); break; }
    case 'anvil_next': A.anvilBounce = 1; break;
    case 'wall': { const [x, y] = runnerPos(); FXK.burst('dust', x - (L ? L.facing : 1) * 0.5 * s, y, { n: 8 }); break; }
    case 'haggle': A.buyerMood = 'shake_head'; A.buyerT = 1.6; break;
    case 'machete': { const [x, y] = coinPos(); FXK.burst('sparks', x, y, { n: 8 }); break; }
    case 'merchant': if (L && D.mx != null) FXK.burst('sparks', L.xToScreen(D.mx), L.gy(D.mx), { n: 10 }); break;
    case 'eject': A.balloon = 0; { const [x, y] = runnerPos(); FXK.burst('smoke', x, y - 1.3 * s, { n: 8 }); } break;
    default: break;
  }
}

function startSettle(outcome) {
  if (G.settle && G.settle.outcome === outcome && G.settle.stage !== 'done') return;
  G.settle = { t: 0, outcome, stage: 'react', cap: null, deskT: 0, coinDone: false, shavingsDone: false };
  A.stampT = 0;
  const [x, y] = runnerPos(), s = G.L ? G.L.s : 95;
  switch (outcome) {
    case 'buyer': snd('cash'); A.buyerMood = 'pay'; A.buyerT = 3; if (G.L) { const [bx, by] = buyerXY(G.L); FXK.burst('cash', bx, by - 1.2 * s, { n: 24 }); } break;
    case 'anvil':
      if (stopWon(G.snap && G.snap.settlement)) { snd('anvil'); setTimeout(() => snd('chime'), 450); setTimeout(() => snd('stamp'), 1300); FXK.shake(3, 0.3); FXK.burst('sparks', x, y - 0.5 * s, { n: 12 }); break; }
      snd('anvil'); setTimeout(() => snd('crane'), 500); setTimeout(() => snd('stamp'), 1300); FXK.shake(4, 0.4); FXK.burst('dust', x, y, { n: 16 }); break;
    case 'barrel': snd('barrel'); setTimeout(() => snd('stamp'), 900); FXK.shake(9, 0.7); FXK.burst('smoke', x, y, { n: 16 }); break;
    case 'merchant': snd('tackle'); FXK.burst('dust', x, y, { n: 22 }); A.tackle = 1; break;
    case 'eject': snd('balloon'); A.balloon = Math.max(A.balloon, 0.4); break;
    case 'kill': snd('chain'); break;
    default: snd('thud'); break;
  }
}

// ======================================================================================================== actions + holds (CONTRACT 8.6)
const HOLD_KEYS = { Space: 'shoot', KeyA: 'anvil_next', KeyW: 'wall', KeyM: 'machete', KeyH: 'haggle', KeyT: 'merchant', KeyE: 'eject', KeyK: 'kill' };
// Zee 2026-11-04: "we dont need holds.. dont hold. click n it happens" - 0 = fire on press. Only the kill switch keeps a hold.
const HOLD_DUR = { shoot: 0, anvil_next: 0, wall: 0, machete: 0, haggle: 0, merchant: 0, eject: 0, kill: 2.0 };
const HOLD_COLOR = { shoot: P.gold, anvil_next: P.brassLight, wall: P.brickLight, machete: P.goldHot, haggle: P.emeraldLight, merchant: P.neonPink, eject: P.crimson, kill: P.crimson };
const HOLD_LABEL = { shoot: 'SPACE', anvil_next: 'A', wall: 'W', machete: 'M', haggle: 'H', merchant: 'T', eject: 'E', kill: 'K' };
function actionValid(action) {
  const ph = G.phase;
  if (action === 'kill') return true;
  if (action === 'shoot') return ph === 'aiming';
  if (['anvil_next', 'wall', 'machete', 'haggle', 'merchant', 'eject'].includes(action)) return ph === 'open';
  return false;
}
function startHold(action, src, extra = {}) {
  if (!G.L || !actionValid(action)) return false;
  G.hold = { action, src, t0: performance.now(), dur: HOLD_DUR[action] ?? 0.5, frac: 0, fired: false, ...extra };   // real time, not frame time
  if (!G.hold.ring) {                                            // pin the ring to its target now, so it never jumps when the phase moves on
    if (action === 'kill') { const C = SCR.cornerLayout(G.L); G.hold.ring = [C.cog.x, C.cog.y]; G.hold.screen = true; }
    else if (action === 'eject') { G.hold.ring = [G.L.eject.x, G.L.eject.y]; G.hold.screen = true; }
    else { const tg = worldTargets().find((w) => w.action === action); if (tg) G.hold.ring = tg.ring; }
  }
  if (G.hold.dur <= 0) { updateHold(); return true; }           // a click acts at once (the ring just pops)
  snd('click', { vol: 0.45 });
  return true;
}
function cancelHold(reason) {
  if (G.hold && !G.hold.fired) { snd('click'); G.last = { action: G.hold.action, result: 'cancelled', why: reason || 'released early' }; }
  G.hold = null;
}
function releaseHold(reason) {                // on key/pointer release: a ring that completed in real time fires even if no frame saw it
  const h = G.hold; if (!h) return;
  if (!h.fired && (performance.now() - h.t0) / 1000 >= h.dur) updateHold();
  if (G.hold && !G.hold.fired) cancelHold(reason); else G.hold = null;
}
function updateHold() {
  const h = G.hold; if (!h) return;
  h.frac = h.dur > 0 ? clamp((performance.now() - h.t0) / 1000 / h.dur, 0, 1) : 1;
  if (h.frac >= 1 && !h.fired) {
    h.fired = true; h.firedAt = performance.now(); snd('confirm');
    if (h.action === 'kill') { SCR.Safety.open({ armKill: true }); G.hold = null; return; }
    fire(h.action, h.args || {});
  }
}
async function fire(action, args = {}) {
  const t0 = performance.now();
  if (action === 'merchant') {                                 // Zee 2026-11-04: no rider = nothing to sell to; the girl = a sale that must be a profit
    if (!D.cycKind) return { accepted: false, why: 'no_rider' };
    if (D.cycKind === 'girl') args = { ...args, need_profit: true };
  }
  if (net.frozen()) {                                          // during a freeze nothing is sent: the release says the needle is up
    snd('needle', { up: true }); A.needle = 1; A.refuse = { action, why: 'frozen', t: 0 };
    G.last = { action, result: 'not sent', why: 'frozen (needle up)', t: t0 };
    return { accepted: false, why: 'frozen' };
  }
  G.pendings[action] = t0;
  // the player's own gesture gets its sound at once; the world's answer waits for the engine
  if (action === 'shoot') { if (!A.quietShot) snd('gunshot', { vol: 2 }); setTimeout(() => snd('cough'), 420); A.recoil = 1; A.bankerMood = 'shot'; A.bankerT = 1.4; const [bx, by] = guardPos(); FXK.burst('smoke', bx, by, { n: 20 }); FXK.burst('sparks', bx, by, { n: 12 }); FXK.shake(9, 0.4); }
  if (action === 'eject') { A.balloon = Math.max(A.balloon, 0.15); snd('balloon'); }
  if (action === 'merchant') { snd('whistle'); }
  if (action === 'machete') { A.machete = Math.max(A.machete, 0.01); }
  G.last = { action, result: 'sent', t: t0, args };
  const res = await net.act(action, args);
  G.last = { ...G.last, result: res.accepted ? 'accepted' : 'refused', why: res.why, nonce: res.nonce, rtt: Math.round(performance.now() - t0) };
  if (!res.accepted && !G.refusedNonces.has(res.nonce)) { G.refusedNonces.add(res.nonce); refusalFx(action, res.why); }
  if (res.accepted || res.why) delete G.pendings[action];
  return res;
}
async function tapAction(action, args = {}) {             // non-money taps (fund via Enter, ack, flip, target, twin, unfund)
  const res = await fire(action, args);
  if (action === 'fund' && res.accepted) { snd('coin'); }
  if (action === 'ack' && res.accepted) { G.settle = null; }
  return res;
}
function fundArgs() {
  const st = G.snap.settings;
  return { kind: G.ui.kind, side: st.side || 1, target: (st.targets && st.targets.length ? Math.min(...st.targets) : st.target), twin: !!st.twin_invited };   // always the closest target
}
function doFund() {
  const snap = G.snap; if (!snap || G.phase !== 'lobby') return;
  if (G.ui.kind === 'live' && !snap.limits.live_allowed) { refusalFx('fund', snap.limits.why_not_live); return; }
  tapAction('fund', fundArgs());
}
// Zee 2026-11-04: "the bank should be clickable from the start and the player should not be needing to be clicked to activate it" -
// one click on the bank / the Guard (or Space) in the lobby funds the round and fires the shot as soon as the street says 'aiming'.
let robbing = false;
// Zee 2026-11-04: "if we shoot multiple men from the bank -> shoot thrice -> we pick up 3x the trade coins". Every click on the bank (or the
// mafia) / Space within ~0.9 s shoots one more man, up to three; when the volley ends the robbery is made with that many coins.
function volleyShot(side) {
  if (G.phase !== 'lobby' || robbing) return;
  if (A.volley && A.volley.side !== side) return;
  if (!A.volley) A.volley = { side, n: 0, until: 0 };
  if (A.volley.n >= 3) return;
  A.volley.n += 1; A.volley.until = performance.now() + 900;
  (A.knockAt = A.knockAt || { 1: [], '-1': [] })[side][A.volley.n - 1] = performance.now();
  snd('gunshot', { vol: 1.6 }); A.recoil = 1; FXK.shake(6, 0.25);
  const L = G.L;
  if (L) { const g = side > 0 ? [L.bank.guard.x + (A.volley.n - 1) * 0.48 * L.s, L.bank.guard.y] : (D.goonPos ? [D.goonPos[0] + (A.volley.n - 1) * 0.5 * L.s, D.goonPos[1]] : [L.W * 0.85, L.H * 0.6]);
    FXK.burst('smoke', g[0], g[1], { n: 12 }); FXK.burst('sparks', g[0], g[1], { n: 8 }); }
}
function knockProgress(side) {                                // 0..1 per man: how far through his fall he is (1 = lying down)
  const at = (A.knockAt && A.knockAt[side]) || [], now = performance.now();
  return [0, 1, 2].map((i) => (isFinite(at[i]) ? clamp((now - at[i]) / 450, 0, 1) : 1));
}
function knockedCount(side) {                                  // how many of that party lie knocked over right now
  if (A.volley && A.volley.side === side) return A.volley.n;
  if (A.robbedSide === side && G.phase !== 'lobby' && G.phase !== 'aiming') return A.robbedN || 1;
  return 0;
}
async function robBank(side = 1, coins = 1) {                  // side +1: rob the bank (buy); -1: rob the mafia (sell)
  const snap = G.snap; if (!snap || G.phase !== 'lobby' || robbing) return;
  if (G.ui.kind === 'live' && !snap.limits.live_allowed) { refusalFx('fund', snap.limits.why_not_live); return; }
  robbing = true;
  try {
    A.robbedSide = side; A.robbedN = coins;
    const res = await tapAction('fund', { ...fundArgs(), side, coins });
    if (!res || !res.accepted) return;
    const t0 = performance.now();
    while (G.phase !== 'aiming' && performance.now() - t0 < 3000) await new Promise((r) => setTimeout(r, 30));
    if (G.phase !== 'aiming') return;
    // Zee 2026-11-04: robbing AGAINST the trend starts a shootout - the guard (or the henchmen) fire back and nothing is sent; the shot that
    // lands (the real order) goes out the moment the street tilts our way, unless the player waves the white flag (Esc) first.
    const fav = () => { const pv = G.snap && G.snap.preview; return pv && isFinite(pv.tilt) ? +pv.tilt : 0; };
    if (fav() < -0.05) {
      A.shootout = { side, t: 0, next: 0.05, enemyNext: 0.5, eflash: 0, stop: false };
      while (A.shootout && !A.shootout.stop && G.phase === 'aiming' && fav() < 0.05) await new Promise((r) => setTimeout(r, 80));
      const so = A.shootout; A.shootout = null;
      if (!so || so.stop) { if (G.phase === 'aiming') await tapAction('unfund', {}); return; }
      if (G.phase !== 'aiming') return;
    }
    A.quietShot = true;                                        // the volley already fired: the robbery shot itself stays quiet
    await fire('shoot', {});
  } finally { robbing = false; A.shootout = null; A.quietShot = false; }
}
function stopShootout() { if (A.shootout) { A.shootout.stop = true; snd('page'); } }
function mafiaHitRect(L) { const b = D.mafiaBox; return b ? { x: b.x, y: b.y, w: b.w, h: b.h } : { x: L.W * 0.78, y: L.H * 0.4, w: L.W * 0.2, h: L.H * 0.35 }; }
function bankHitRect(L) {
  const s = L.s, gd = L.bank.guard || L.bank.banker;
  return { x: Math.min(gd.x, L.bank.x) - 1.5 * s, y: L.bank.top + 0.2 * s, w: Math.abs(gd.x - L.bank.x) + 3.0 * s, h: L.bank.y - L.bank.top };   // + the three guards
}
function doAck(rest) {
  if (G.phase !== 'settled') return;
  if (rest) G.ui.rest = true;
  tapAction('ack', {});
}
function doFlip() {
  if (G.phase !== 'lobby' && G.phase !== 'aiming') return;
  const side = (G.snap.settings.side || 1) > 0 ? -1 : 1;
  tapAction('flip', { side });
}
function togglePlain() { G.ui.plain = !plainOn(); snd('page'); }
// Zee 2026-11-04: "we dont need a white banner on top describing what happened. its a game" - the plain-words line is gone for good
function plainOn() { return false; }
function toggleSound() {
  const st = G.snap && G.snap.settings; if (!st) return;
  const on = !st.sound;
  st.sound = on;                                            // optimistic; the server echoes the truth in the next snapshot
  audioCall('setMuted', !on);
  net.settings({ sound: on });
  if (on) snd('tick');
}

// ---------------------------------------------------------------------------------------------------- keyboard
const KEYLOG = [];
function keyLog(type, e, note) { KEYLOG.push(`${Math.round(performance.now())} ${type} ${e.code}${e.repeat ? ' rep' : ''}${note ? ' ' + note : ''}`); if (KEYLOG.length > 16) KEYLOG.shift(); }
window.addEventListener('keydown', (e) => {
  if (wakeUp() && !e.repeat) { e.preventDefault(); return; }
  keyLog('down', e, G.hold ? 'hold=' + G.hold.action : '');
  initAudio();
  if (SCR.Safety.isOpen()) { if (e.code === 'Escape') { SCR.Safety.close(); e.preventDefault(); } return; }
  if (e.code === 'Space' || e.code === 'Enter' || e.code === 'Tab') e.preventDefault();
  if (e.repeat) return;
  const ph = G.phase;
  if (G.ui.rest && ph === 'lobby') { G.ui.rest = false; return; }
  const holdAction = HOLD_KEYS[e.code];
  if (holdAction && actionValid(holdAction)) { if (!G.hold) startHold(holdAction, 'key', { code: e.code }); return; }
  switch (e.code) {
    case 'Enter': if (ph === 'lobby') doFund(); else if (ph === 'settled') doAck(false); break;
    case 'Space': if (ph === 'settled') doAck(false); else if (ph === 'lobby') volleyShot(A.volley ? A.volley.side : 1); else if (ph === 'open' && !G.hold) startHold('eject', 'key', { code: e.code }); break;   // Zee 2026-11-04: Space = the eject button during a round
    case 'KeyF': doFlip(); break;
    case 'KeyL': togglePlain(); break;
    case 'KeyS': toggleSound(); break;
    case 'KeyI': if (ph === 'lobby' || ph === 'aiming') inviteTwin(); break;
    case 'Escape': if (A.shootout) stopShootout(); else if (ph === 'aiming') tapAction('unfund', {}); break;
    case 'Digit1': case 'Digit2': case 'Digit3': case 'Digit4': case 'Digit5': { break;   // Zee 2026-11-04: no target choice (always the closest)
      const st = G.snap && G.snap.settings; if (!st || (ph !== 'lobby' && ph !== 'aiming')) break;
      const tg = st.targets[+e.code.slice(5) - 1]; if (tg != null) { snd('page'); tapAction('set_target', { target: tg }); }
      break;
    }
    case 'KeyO': if (ph === 'lobby') { G.ui.kind = 'wooden'; snd('coin'); } break;
    case 'KeyN': if (ph === 'lobby') { G.ui.kind = 'live'; snd('page'); } break;
    case 'Backquote': G.ui.debug = !G.ui.debug; break;
    default: break;
  }
});
window.addEventListener('keyup', (e) => {
  keyLog('up', e, G.hold ? 'hold=' + G.hold.action + (G.hold.fired ? ' fired' : '') : 'nohold');
  if (G.hold && G.hold.src === 'key' && G.hold.code === e.code) releaseHold('released early');
});
window.addEventListener('blur', () => { if (G.hold && !G.hold.fired) cancelHold('focus lost'); G.drag = null; });
function inviteTwin() {
  const snap = G.snap; if (!snap) return;
  const st = snap.settings, allowed = G.ui.kind === 'wooden' || st.twin_unlocked;
  if (!allowed) { refusalFx('invite_twin', 'locked'); return; }
  snd('chime'); tapAction('invite_twin', { on: !st.twin_invited }); st.twin_invited = !st.twin_invited;
}

// ---------------------------------------------------------------------------------------------------- pointer (mouse + touch)
const hitCircle = (h, x, y) => h && Math.hypot(x - h.x, y - h.y) <= h.r;
const hitRect = (h, x, y) => h && x >= h.x && x <= h.x + h.w && y >= h.y && y <= h.y + h.h;
function worldTargets() {                                     // hit boxes in layout space (before shake), rebuilt every frame
  const L = G.L, snap = G.snap; if (!L || !snap) return [];
  const s = L.s, out = [], ph = G.phase, r = snap.round;
  if (ph === 'aiming' && A.shootout) {                       // the white flag: stop firing, nothing is sent
    const [rx, ry] = runnerPos(); out.push({ id: 'flag', kind: 'tap', circle: { x: rx + L.facing * -0.55 * s, y: ry - 1.55 * s, r: 0.4 * s }, tap: stopShootout });
  }
  if (ph === 'aiming' && !A.shootout) {                      // shoot the Guard outside the bank (the whole little bank also counts)
    const gd = L.bank.guard || L.bank.banker;
    if (L.mirror) out.push({ id: 'mafia', kind: 'hold', action: 'shoot', rect: mafiaHitRect(L), ring: D.goonPos || [gd.x, gd.y] });   // selling: shoot the mafia
    else out.push({ id: 'guard', kind: 'hold', action: 'shoot', rect: bankHitRect(L), ring: [gd.x, gd.y] });
  }
  if (D.yogiHit && (ph === 'lobby' || ph === 'aiming')) {   // Zee 2026-11-05: poke the yogi - he bows, "Om", petals (nothing is sent)
    out.push({ id: 'yogi', kind: 'tap', circle: D.yogiHit, tap: () => { D.yogiPoke = G.t; snd('chime', { x: 0.4 }); } });
  }
  if (ph === 'lobby') {                                      // no need to click the Runner first: whom you rob picks the direction
    if (D.gemHit) { const gh = D.gemHit; out.push({ id: 'gem', kind: 'tap', circle: gh, tap: () => volleyShot(gh.side) }); }
    out.push({ id: 'rob', kind: 'tap', rect: bankHitRect(L), tap: () => volleyShot(1) });
    out.push({ id: 'robmafia', kind: 'tap', rect: mafiaHitRect(L), tap: () => volleyShot(-1) });
  }
  if (ph === 'open' && r) {
    out.push({ id: 'eject', kind: 'hold', action: 'eject', circle: L.eject, ring: [L.eject.x, L.eject.y] });
    if (ptsOK(D.buyerPts, 'tagX')) {
      const B = D.buyerPts, rr0 = Math.max(B.tagR || 0, 0.42 * s);
      out.push({ id: 'tag', kind: 'hold', action: 'haggle', circle: { x: B.tagX, y: B.tagY, r: rr0 }, ring: [B.tagX, B.tagY] });
    } else {
      const [bx, by] = buyerXY(L);
      out.push({ id: 'tag', kind: 'hold', action: 'haggle', rect: { x: bx - 0.75 * s, y: by - 3.0 * s, w: 1.5 * s, h: 1.6 * s }, ring: [bx, by - 2.0 * s] });
    }
    const [cx, cy] = coinPos();
    out.push({ id: 'coin', kind: 'hold', action: 'machete', circle: { x: cx, y: cy, r: 0.26 * s }, ring: [cx, cy] });
    const ax = L.xToScreen(D.anvilX == null ? r.anvil.x : D.anvilX), ay = L.gy(D.anvilX == null ? r.anvil.x : D.anvilX);
    out.push({ id: 'anvil', kind: 'drag', action: 'anvil_next', rect: { x: ax - 0.45 * s, y: ay - 0.6 * s, w: 0.9 * s, h: 0.65 * s }, ring: [ax, ay - 0.7 * s] });
    const [rx, ry] = runnerPos();
    const bxw = rx - L.facing * 0.75 * s;
    out.push({ id: 'behind', kind: 'hold', action: 'wall', rect: { x: Math.min(bxw, rx - L.facing * 0.2 * s) - (L.facing > 0 ? 0.35 * s : 0), y: ry - 1.1 * s, w: 0.9 * s, h: 1.2 * s }, ring: [bxw, ry - 0.6 * s] });
    // (the wall spot right behind the Runner wins over a rider passing there: a wall click must never turn into a sale - Zee 2026-11-04)
    if (r.merchant && r.merchant.visible && D.mx != null && D.cycKind) { const mx = L.xToScreen(D.mx), my = L.gy(D.mx); out.push({ id: 'merchant', kind: 'hold', action: 'merchant', rect: { x: mx - 0.5 * s, y: my - 1.7 * s, w: 1.0 * s, h: 1.7 * s }, ring: [mx, my - 0.9 * s] }); }
  }
  const rope = bellRope(L);                                   // the bell's rope: pulling it gives a dull clunk (it marks time, it never advises)
  out.push({ id: 'rope', kind: 'tap', circle: { x: rope.x1, y: rope.y1 + 0.05 * s, r: 0.22 * s }, tap: () => { A.ropeTug = 1; snd('clunk'); } });
  if (ph === 'settled' && G.settle) out.push({ id: 'sign', kind: 'tap', rect: { x: L.bank.sign.cx - L.bank.sign.w / 2, y: L.bank.sign.cy - L.bank.sign.h / 2, w: L.bank.sign.w, h: L.bank.sign.h }, tap: togglePlain });
  return out;
}
function screenTargets() {                                    // lobby / settlement / global objects (screens.js layouts)
  const out = [], ph = G.phase, snap = G.snap;
  const C = SCR.cornerLayout(G.L);
  out.push({ id: 'cog', kind: 'tap', circle: C.cog, tap: () => { snd('page'); SCR.Safety.open({}); } });
  if (ph === 'lobby' || ph === 'aiming') out.push({ id: 'page', kind: 'tap', circle: C.page, tap: doFlip });
  if (ph === 'lobby' && G.lobbyL && snap) {
    const LL = G.lobbyL;
    out.push({ id: 'radio', kind: 'tap', circle: LL.radio.hit, tap: toggleSound });
    LL.tags.forEach((tg) => out.push({ id: 'tag' + tg.target, kind: 'tap', rect: tg.hit, tap: () => { snd('page'); tapAction('set_target', { target: tg.target }); } }));
    out.push({ id: 'twin', kind: 'tap', rect: LL.cabinet.hit, tap: inviteTwin });
    out.push({ id: 'held', kind: 'drag', circle: LL.hand, item: G.ui.kind });
  }
  if (ph === 'aiming' && G.lobbyL) out.push({ id: 'pocket', kind: 'tap', circle: { ...G.lobbyL.pocket, r: G.L.s * 0.3 }, tap: () => tapAction('unfund', {}) });
  if (ph === 'settled' && G.settleL && G.settle && G.settle.stage === 'desk') {
    out.push({ id: 'again', kind: 'tap', rect: G.settleL.again, tap: () => doAck(false) });
    out.push({ id: 'receipt', kind: 'tap', rect: G.settleL.receipt, tap: togglePlain });
  }
  return out;
}
function pick(px, py) {
  const [lx, ly] = toLayout(px, py);
  for (const t of screenTargets()) if ((t.circle && hitCircle(t.circle, px, py)) || (t.rect && hitRect(t.rect, px, py))) return t;
  for (const t of worldTargets()) if ((t.circle && hitCircle(t.circle, lx, ly)) || (t.rect && hitRect(t.rect, lx, ly))) return t;
  return null;
}
function pointerXY(e) { const b = canvas.getBoundingClientRect(); return [e.clientX - b.left, e.clientY - b.top]; }
canvas.addEventListener('pointerdown', (e) => {
  const woke = wakeUp();                                      // a click on a dozing Runner wakes him (ready, shotgun up)...
  initAudio();
  if (SCR.Safety.isOpen()) return;
  if (document.activeElement !== canvas) focusGame();          // the click-to-focus fallback
  const [x, y] = pointerXY(e);
  G.pointer = { x, y, down: true };
  try { canvas.setPointerCapture(e.pointerId); } catch (er) { /* */ }
  if (G.ui.rest && G.phase === 'lobby') { G.ui.rest = false; return; }
  const t = pick(x, y);
  if (woke && !(t && (t.id === 'rob' || t.id === 'robmafia' || t.id === 'gem'))) return;   // ...and a click on a party (or the gem) also fires: click n it happens
  if (!t) return;
  if (t.kind === 'tap') { t.tap(); return; }
  if (t.kind === 'hold') { startHold(t.action, 'pointer', { ring: t.ring, target: t.id }); return; }
  if (t.kind === 'drag') {
    if (t.item) { G.drag = { item: t.item, x, y, x0: x, y0: y, from: t.id }; if (G.ui.kind !== t.item) { G.ui.kind = t.item; snd(t.item === 'wooden' ? 'coin' : 'page'); } return; }
    if (t.id === 'anvil') { G.drag = { item: 'anvil', x, y, x0: x, y0: y }; snd('chain'); }
  }
});
canvas.addEventListener('pointermove', (e) => {
  const [x, y] = pointerXY(e);
  G.pointer.x = x; G.pointer.y = y;
  const d = G.drag;
  if (d) {
    d.x = x; d.y = y;
    if (d.item === 'anvil') {                                  // drag the anvil onto a lit stake: the ring fills while it hovers there
      const st = stakeUnder(x, y);
      if (st && (!G.hold || G.hold.target !== 'stake')) startHold('anvil_next', 'drag', { target: 'stake', ring: st.ring });
      if (!st && G.hold && G.hold.target === 'stake' && !G.hold.fired) cancelHold('moved off the stake');
    }
    return;
  }
  if (G.hold && G.hold.src === 'pointer' && !G.hold.fired) {   // sliding off the target cancels
    const t = pick(x, y);
    if (!t || t.id !== G.hold.target) cancelHold('slid off');
  }
  const t = pick(x, y);
  canvas.className = t ? (t.kind === 'drag' ? 'grab' : 'point') : '';
});
function endPointer(e) {
  const [x, y] = pointerXY(e);
  G.pointer.down = false;
  const d = G.drag; G.drag = null;
  if (d && d.item && d.item !== 'anvil' && G.lobbyL) {
    const P0 = G.lobbyL.pocket;
    if (Math.hypot(x - P0.x, y - P0.y) < G.L.s * 0.75) { G.ui.kind = d.item; doFund(); }
    else if (Math.hypot(x - d.x0, y - d.y0) > 4) snd('tick');
  }
  if (G.hold && (G.hold.src === 'pointer' || G.hold.src === 'drag')) releaseHold('released early');
}
canvas.addEventListener('pointerup', endPointer);
canvas.addEventListener('pointercancel', () => {             // the OS took the touch away: that is never a confirmation
  G.pointer.down = false; G.drag = null;
  if (G.hold && (G.hold.src === 'pointer' || G.hold.src === 'drag')) cancelHold('touch cancelled');
});
canvas.addEventListener('contextmenu', (e) => e.preventDefault());
function stakeUnder(px, py) {
  const L = G.L, r = G.snap && G.snap.round; if (!L || !r) return null;
  const [lx, ly] = toLayout(px, py);
  for (const st of r.stakes || []) {
    if (!st.lit) continue;
    const sx = L.xToScreen(st.x), sy = L.gy(st.x);
    if (Math.abs(lx - sx) < 0.35 * L.s && ly > sy - 0.95 * L.s && ly < sy + 0.25 * L.s) return { st, ring: [sx, sy - 0.75 * L.s] };
  }
  return null;
}

// ======================================================================================================== env (world.js input)
function uhvDay(snap) {                                        // Zee 2026-11-05: day = a UHV level waiting for its breakout, or a 97.7% breakout < ~2.1 min ago
  const d = (typeof window !== 'undefined' && window.__ggDia) || (snap && snap.market && snap.market.diamond) || {};   // (__ggDia: screenshot self-tests only)
  if (d.expect == null && d.u97_age == null && !d.cut) return true;   // no reading yet (or not EUR/USD): keep the old sky
  return !!d.expect || !!d.cut || (d.u97_age != null && d.u97_age < 126);
}
function uhvSteady(snap) {                                     // Zee 2026-11-05: the yogi appears only once the day is steady - then thunder + smoke
  const now = G.t || 0, raw = uhvDay(snap);
  if (D.uhvRawAt == null || raw !== D.uhvRaw) { D.uhvRaw = raw; D.uhvRawAt = now; }
  const held = now - D.uhvRawAt;
  if (D.uhvOn == null) D.uhvOn = raw;                              // the first frame: no drama for what was already there
  else if (!D.uhvOn && raw && held >= 2.0) {
    D.uhvOn = true; D.yogiAppear = now;
    const ph = G.phase;
    if (ph === 'lobby' || ph === 'aiming') { A.lightning = 1; FXK.shake(6, 0.5); snd('thunder', { near: true }); }
  } else if (D.uhvOn && !raw && held >= 4.0) D.uhvOn = false;
  return D.uhvOn;
}
function riskSky(m) {                                         // Zee 2026-11-06: "sunshine means zero risk -> rain has levels -> more risk more rain"
  const r = (typeof window !== 'undefined' && window.__ggRisk) || (m && m.risk);
  if (!r || r.level == null) return null;
  return r.level >= 3 ? 'storm' : 'calm';                       // levels 1-2 rain through drawRiskRain over a calm sky; 0 = clear sun
}
function drawRiskRain(snap, W, H, t) {                         // drizzle (1) / rain (2) over the street; the storm (3) is the world's own
  const r = (typeof window !== 'undefined' && window.__ggRisk) || (snap.market && snap.market.risk) || {};
  const lv = r.level == null ? 0 : r.level;
  if (lv === 1 || lv === 2) {
    ctx.save();
    ctx.fillStyle = `rgba(40,52,78,${lv === 1 ? 0.10 : 0.22})`; ctx.fillRect(0, 0, W, H);   // the light goes grey under the cloud
    const n = lv === 1 ? 70 : 230, len = lv === 1 ? 10 : 18, sp = lv === 1 ? 420 : 760;
    ctx.strokeStyle = lv === 1 ? 'rgba(220,232,255,0.45)' : 'rgba(205,222,250,0.6)'; ctx.lineWidth = lv === 1 ? 1 : 1.6;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = ((rand(i * 7.3) * W + t * 60 * (0.6 + rand(i))) % W + W) % W, y = (rand(i * 3.1) * H + t * sp * (0.8 + 0.4 * rand(i * 1.7))) % H;
      ctx.moveTo(x, y); ctx.lineTo(x - len * 0.25, y + len);
    }
    ctx.stroke();
    ctx.restore();
  }
  if (lv >= 2 && (G.phase === 'lobby' || G.phase === 'aiming' || G.phase === 'open')) {   // thunder: more risk, more (and closer) thunder
    const n = Math.max(1, r.n || 1), every = lv === 2 ? 28 : Math.max(2.5, 11 / n);          // rain: a distant rumble ~every 28 s; storm: 11 s / dangers
    if (D.thunderAt == null) D.thunderAt = t + every * (0.4 + 0.6 * Math.random());
    if (t >= D.thunderAt) {
      D.thunderAt = t + every * (0.6 + 0.8 * Math.random());
      if (lv >= 3) { A.lightning = 1; FXK.shake(4 + 2 * Math.min(n, 3), 0.4); }
      snd('thunder', lv >= 3 ? { near: true } : { dist: 0.85, vol: 0.6 });
    }
  } else D.thunderAt = null;
  if (r.why) {                                                  // the sky's reason, small, top centre
    const icon = ['☀️', '🌦️', '🌧️', '⛈️'][Math.max(0, Math.min(3, lv))];
    const word = ['zero risk', 'low risk', 'risky', 'danger'][Math.max(0, Math.min(3, lv))];
    const txt = `${icon}  ${word}${lv === 0 ? '' : ': ' + r.why}`;
    ctx.save(); ctx.font = 'bold 15px sans-serif'; ctx.textAlign = 'center';
    const w = ctx.measureText(txt).width + 26, x0 = W / 2 + 230, y0 = 44;
    ctx.fillStyle = ['rgba(255,214,90,0.85)', 'rgba(120,150,190,0.85)', 'rgba(60,80,120,0.88)', 'rgba(40,30,70,0.9)'][Math.max(0, Math.min(3, lv))];
    roundRect(ctx, x0 - w / 2, y0 - 16, w, 26, 12); ctx.fill();
    ctx.fillStyle = lv === 0 ? '#3a2a00' : '#eef3ff'; ctx.fillText(txt, x0, y0 + 2); ctx.restore();
  }
}
function buildEnv() {
  const snap = G.snap, m = (snap && snap.market) || {}, r = snap && snap.round, ph = G.phase;
  const rr = inRound(ph) ? r : null;
  return {
    session: m.session || 'london', day_frac: m.day_frac == null ? 0.4 : m.day_frac,
    weather: riskSky(m) || m.weather || 'calm', vol: m.vol || 0.3,   // Zee 2026-11-06: the weather IS the risk now (riskSky)
    lightning: !!m.lightning && A.lightning > 0.2 || A.lightning > 0.5, season: m.season || 0,
    night: !!(rr && rr.night) || m.session === 'dead' || m.session === 'closed' || ((ph === 'lobby' || ph === 'aiming') && !uhvSteady(snap)),   // no entry expected: night
    golden_hour: !!(rr && rr.golden_hour), freeze: net.frozen(),
    wooden: rr ? rr.kind === 'wooden' : (ph === 'lobby' || ph === 'aiming') && G.ui.kind === 'wooden',
    replay: snap && snap.mode === 'replay', mirror: D.mirror, tilt: D.tilt, t: G.t, lights: envLights(),
    lampOnly: !!(rr && rr.night),                          // a long round's night: the Buyer's lamp is the only light
  };
}

function envLights() {
  const L = G.L; if (!L) return null;
  const s = L.s, [bx, by] = buyerXY(L), out = [{ x: bx, y: by - 1.2 * s, r: 2.0 * s }, { x: L.bank.sign.cx, y: L.bank.sign.cy, r: 1.5 * s }];
  if (G.phase === 'open' || G.phase === 'closing') { const [cx, cy] = coinPos(); out.push({ x: cx, y: cy, r: 0.9 * s }); }
  if (L.roll) {                                                  // the grade is drawn in screen space; the street under the camera roll
    const c = Math.cos(L.roll), sn = Math.sin(L.roll);
    for (const p of out) { const dx = (p.x - L.pivotX) * L.rollScale, dy = (p.y - L.pivotY) * L.rollScale; p.x = L.pivotX + dx * c - dy * sn; p.y = L.pivotY + dx * sn + dy * c; p.r *= L.rollScale; }
  }
  return out;
}

// ======================================================================================================== the characters' moods and poses
function bankerMood() {
  const snap = G.snap, ph = G.phase, r = snap.round, sh = snap.market && snap.market.shutters;
  if (A.bankerT > 0 && A.bankerMood) return A.bankerMood;
  if (sh && sh.down && sh.reason === 'jam') return 'cards';
  if (ph === 'sending') return 'shot';
  if (ph === 'settled' && snap.settlement) {
    const st = snap.settlement, o = st.outcome;
    if (stopWon(st)) return 'sulk';                              // the anvil locked in his gain: the Banker pays, he does not collect
    return o === 'anvil' ? 'crane' : o === 'barrel' ? 'gloat' : o === 'buyer' ? 'sulk' : 'smug';
  }
  if ((ph === 'open' || ph === 'closing') && r) { if (D.x < r.x_entry - 0.15) return 'eager'; if (D.x > r.x_entry + 0.22) return 'sulk'; }
  return 'smug';
}
function buyerMood() {
  const snap = G.snap, ph = G.phase, r = snap.round;
  if (A.buyerT > 0 && A.buyerMood) return A.buyerMood;
  if (ph === 'settled' && snap.settlement) return snap.settlement.outcome === 'buyer' ? 'pay' : 'wait';
  if ((ph === 'open' || ph === 'closing') && r) { if (r.haggles >= r.haggle_max) return 'wave_off'; if (D.x > r.x_tp - 0.16) return 'inspect'; if (D.tilt < -0.35) return 'tap'; }
  return 'wait';
}
function outfitFor(r) {
  const st = G.snap.settlement, ph = G.phase;
  if (ph === 'settled' && st) {
    if (st.outcome === 'barrel') return G.settle && G.settle.t > 0.55 ? 'barrel' : 'dusty';
    if (st.outcome === 'anvil' && !stopWon(st)) return 'dusty';   // the ordinary loss; an anvil that locked in a gain is a win
  }
  if (r.machete_done) return 'staked';
  return outfitBand(r).outfit;
}
// the health bar made of clothes, measured as the share of the way travelled: toward the Buyer (the target) on the profit side, toward
// the vault anvil (the initial stop, x 0) on the loss side. Suit around the door; the hat at 35 % of the way to the Buyer; the tuxedo,
// the top hat and the ride beyond 70 %. The undershirt from a third of the way to the anvil, the polka-dot boxers from two thirds.
function outfitBand(r) {
  const xe = isFinite(r.x_entry) ? r.x_entry : 0.45, x = D.x ?? r.x;
  if (!isFinite(x)) return { outfit: 'suit', hat: false };
  const tp = Math.max(xe + 0.05, isFinite(r.x_tp) ? Math.min(r.x_tp, 1) : 1);
  const up = (x - xe) / (tp - xe), down = (xe - x) / Math.max(0.05, xe);
  if (up >= 0.7) return { outfit: 'tux', hat: true };
  if (up >= 0.35) return { outfit: 'suit', hat: true };
  if (down >= 2 / 3) return { outfit: 'boxers', hat: false };
  if (down >= 1 / 3) return { outfit: 'undershirt', hat: false };
  return { outfit: 'suit', hat: false };
}
function drawTreasure(cx, cy, r, s, t) {                    // Zee 2026-11-04: "make it something like a real treasure we're holding (shiny and awesome)"
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const pulse = 0.75 + 0.25 * Math.sin(t * 4);
  const g = ctx.createRadialGradient(cx, cy, r * 0.3, cx, cy, r * 3.2); g.addColorStop(0, `rgba(255,230,120,${(0.55 * pulse).toFixed(3)})`); g.addColorStop(0.4, 'rgba(255,190,60,0.22)'); g.addColorStop(1, 'rgba(255,170,40,0)');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, r * 3.2, 0, TAU); ctx.fill();
  for (let i = 0; i < 8; i++) {                               // slow god-rays turning around it
    const a = t * 0.6 + i * (TAU / 8), len = r * (2.4 + 0.6 * Math.sin(t * 3 + i));
    ctx.fillStyle = `rgba(255,225,130,${(0.18 * pulse).toFixed(3)})`;
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(a - 0.08) * len, cy + Math.sin(a - 0.08) * len); ctx.lineTo(cx + Math.cos(a + 0.08) * len, cy + Math.sin(a + 0.08) * len); ctx.closePath(); ctx.fill();
  }
  const sweep = ((t * 0.7) % 1.6) - 0.3;                     // a glint sweeping across the face
  if (sweep > -0.2 && sweep < 1.2) { ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, r, 0, TAU); ctx.clip(); ctx.fillStyle = 'rgba(255,255,255,0.65)'; ctx.translate(cx - r + sweep * 2 * r, cy); ctx.rotate(0.5); ctx.fillRect(-r * 0.12, -r * 1.5, r * 0.24, r * 3); ctx.restore(); }
  for (let i = 0; i < 4; i++) {                               // four-point stars twinkling around it
    const ph = (t * 0.9 + i * 0.27) % 1, a = i * 1.7 + t * 0.3, d = r * (1.3 + 0.5 * i % 2), sx = cx + Math.cos(a) * d, sy = cy + Math.sin(a) * d, k = Math.sin(ph * Math.PI) * r * 0.45;
    ctx.fillStyle = '#fff6c8'; ctx.beginPath(); ctx.moveTo(sx, sy - k); ctx.lineTo(sx + k * 0.22, sy - k * 0.22); ctx.lineTo(sx + k, sy); ctx.lineTo(sx + k * 0.22, sy + k * 0.22); ctx.lineTo(sx, sy + k); ctx.lineTo(sx - k * 0.22, sy + k * 0.22); ctx.lineTo(sx - k, sy); ctx.lineTo(sx - k * 0.22, sy - k * 0.22); ctx.closePath(); ctx.fill();
  }
  ctx.restore();
}
function drawShootout(L, t) {                                 // the defenders' muzzle flash + tracer, and the white flag
  const so = A.shootout; if (!so || !L) return;
  const s = L.s, [rx, ry] = runnerPos();
  const src = L.mirror ? D.goonPos : (L.bank.guard ? [L.bank.guard.x + 0.3 * s, L.bank.guard.y - 0.35 * s] : null);
  if (src && so.eflash > 0) {
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    ctx.strokeStyle = `rgba(255,230,140,${(0.9 * so.eflash).toFixed(3)})`; ctx.lineWidth = Math.max(2, 0.03 * s); ctx.lineCap = 'round';
    const tx = lerp(src[0], rx, 0.85), ty = lerp(src[1], ry - 0.6 * s, 0.85);
    ctx.beginPath(); ctx.moveTo(lerp(src[0], tx, 1 - so.eflash), lerp(src[1], ty, 1 - so.eflash)); ctx.lineTo(tx, ty); ctx.stroke();
    const fl = 0.25 * s * so.eflash; ctx.fillStyle = `rgba(255,200,80,${so.eflash.toFixed(3)})`;
    ctx.beginPath(); for (let i = 0; i < 10; i++) { const a = (i / 10) * TAU, rr = i % 2 ? fl * 0.4 : fl; ctx.lineTo(src[0] + Math.cos(a) * rr, src[1] + Math.sin(a) * rr); } ctx.closePath(); ctx.fill();
    ctx.restore();
  }
  // the white flag on a stick beside the Runner: click it to stop firing
  const fx = rx + L.facing * -0.55 * s, fy = ry - 1.0 * s;
  ctx.save();
  ctx.strokeStyle = '#6b4526'; ctx.lineWidth = Math.max(2, 0.035 * s); ctx.beginPath(); ctx.moveTo(fx, fy + 0.25 * s); ctx.lineTo(fx, fy - 0.85 * s); ctx.stroke();
  ctx.fillStyle = '#ffffff'; ctx.strokeStyle = '#2a1a10'; ctx.lineWidth = Math.max(1, 0.015 * s); ctx.beginPath();
  const wv = Math.sin(t * 6) * 0.05 * s, dir = -L.facing;
  ctx.moveTo(fx, fy - 0.85 * s); ctx.quadraticCurveTo(fx + dir * 0.22 * s, fy - 0.85 * s + wv, fx + dir * 0.45 * s, fy - 0.8 * s); ctx.lineTo(fx + dir * 0.45 * s, fy - 0.52 * s);
  ctx.quadraticCurveTo(fx + dir * 0.22 * s, fy - 0.57 * s - wv, fx, fy - 0.55 * s); ctx.closePath(); ctx.fill(); ctx.stroke();
  ctx.restore();
}
function pitNow(rr) {                                          // the spread pit as it stands now (null before the fill: only the rat is there)
  if (!rr || !rr.pit || G.phase === 'sending') return null;
  if (!A.dig) return rr.pit;
  const k = ease(clamp(A.dig.t / A.dig.dur, 0, 1)), p = rr.pit, mid = (p.x0 + p.x1) / 2;
  return { ...p, depth: (p.depth || 0) * k, x0: mid + (p.x0 - mid) * (0.25 + 0.75 * k), x1: mid + (p.x1 - mid) * (0.25 + 0.75 * k) };
}
function drawDiggingRat(p, L, t) {                             // the rat gnaws the ground open, dirt flying, then scurries off
  const s = L.s, mid = (p.x0 + p.x1) / 2, k = A.dig.t / A.dig.dur;
  let xn = mid, phase = 'bite';
  if (k > 1) { phase = 'run'; xn = mid + (p.x1 - p.x0 || 0.05) * 3 * (k - 1); }
  const x = L.xToScreen(xn), y = L.gy(xn);
  if (k <= 1 && Math.random() < 0.5) FXK.burst('dust', x, y - 0.05 * s, { n: 3 });
  if (k <= 1 && Math.random() < 0.08) snd('rat', { n: 1, vol: 0.5 });
  drawWhiteRat(ctx, x, y, s, { pose: phase === 'bite' ? 'dig' : 'run', t, facing: phase === 'run' ? L.facing : -L.facing });
}
G.ui.lastInput = performance.now();
function idleNow() {                                           // after 8 quiet seconds on a flat street he passes the time (25 s per activity)
  if (G.phase !== 'lobby' || robbing || G.ui.rest) { G.ui.idleStart = null; return null; }
  const now = performance.now();
  if (now - (G.ui.lastInput || 0) < 8000 || Math.abs(D.tilt) > 0.22) { G.ui.idleStart = null; return null; }
  if (!G.ui.idleStart) G.ui.idleStart = now;
  const el = (now - G.ui.idleStart) / 1000;
  return { kind: IDLE_KINDS[Math.floor(el / 25) % IDLE_KINDS.length], k: Math.min(1, el / 0.8) };
}
function wakeUp() {                                           // true when he was idling (the input only wakes him)
  const was = !!(G.ui.idleStart && G.phase === 'lobby');
  if (was && G.L) { const [rx, ry] = runnerPos(); FXK.burst('dust', rx, ry, { n: 10 }); snd('click', { vol: 0.6 }); }
  G.ui.lastInput = performance.now(); G.ui.idleStart = null;
  return was;
}
function drawHunterFace(pts, s, f) {                         // Zee 2026-11-04: "more texture on his face -> a dead serious hunter, not a kid"
  if (!ptsOK(pts, 'headX')) return;
  const hx = pts.headX, hy = pts.headY;
  ctx.save();
  ctx.fillStyle = 'rgba(70,45,30,0.38)';                       // stubble along the jaw
  for (let i = 0; i < 26; i++) { const a = 0.15 * Math.PI + (i / 26) * 0.75 * Math.PI, r = (0.07 + ((i * 7) % 5) * 0.004) * s; ctx.fillRect(hx + f * 0.012 * s + Math.cos(a) * r * f, hy + 0.012 * s + Math.sin(a) * r * 0.85, Math.max(1, 0.008 * s), Math.max(1, 0.008 * s)); }
  ctx.strokeStyle = 'rgba(55,35,22,0.9)'; ctx.lineWidth = Math.max(1.5, 0.018 * s); ctx.lineCap = 'round';   // heavy, stern brows
  ctx.beginPath(); ctx.moveTo(hx + f * 0.012 * s, hy - 0.05 * s); ctx.lineTo(hx + f * 0.05 * s, hy - 0.035 * s); ctx.moveTo(hx + f * 0.065 * s, hy - 0.036 * s); ctx.lineTo(hx + f * 0.095 * s, hy - 0.046 * s); ctx.stroke();
  ctx.strokeStyle = 'rgba(190,90,90,0.75)'; ctx.lineWidth = Math.max(1, 0.008 * s);   // an old scar across the cheek
  ctx.beginPath(); ctx.moveTo(hx - f * 0.01 * s, hy - 0.01 * s); ctx.lineTo(hx + f * 0.02 * s, hy + 0.035 * s); ctx.stroke();
  ctx.restore();
}
function diaState(snap) {                                     // the Diamond reading (diamond.py): the camel always, the gem before a side is picked
  const d = (typeof window !== 'undefined' && window.__ggDia) || (snap.market && snap.market.diamond) || {};
  return d;
}
function drawDiamondGem(snap, L, t, dt) {
  const d = diaState(snap), ph = G.phase, s = L.s;
  const key = d.cut ? d.cut + ':' + (d.id || 0) : null, show = ph === 'lobby' || ph === 'aiming';
  if (key && key !== D.diaKey && show && !d.shattered && (d.age || 0) < 20) {                // a new diamond was cut: a chime (two for a royal one)
    snd('chime', { x: d.cut > 0 ? 0.2 : 0.8 });
    if (d.royal) snd('chime', { x: d.cut > 0 ? 0.2 : 0.8, delay: 0.18 });
  }
  if (key) D.diaKey = key;
  if (d.shattered && !D.diaShatter) { D.diaShatter = { t0: t, side: d.cut }; if (show) snd('ping'); }
  if (!d.shattered && D.diaShatter && t - D.diaShatter.t0 > 1.5) D.diaShatter = null;
  D.gemHit = null;
  if (!show) return;
  const side = D.diaShatter ? D.diaShatter.side : d.cut;          // Zee: a diamond means a breakout - no waiting stone any more
  if (!side) return;
  let x, y;
  if (side > 0) {                                                   // a buy: the gem waits over the bank (shoot the bank)
    if (!L.bank || !L.bank.sign) return;
    x = L.bank.sign.cx + 2.4 * s; y = L.bank.sign.cy + 1.25 * s;
  } else {                                                          // a sell: over the mafia's table (shoot the mafia)
    if (!D.bossPos) return;
    x = D.bossPos[0] - 1.2 * s; y = D.bossPos[1] - 1.15 * s;
  }
  if (D.diaShatter) { drawGem(ctx, x, y, s, t, { stage: 'shatter', shatterT: t - D.diaShatter.t0 }); return; }
  D.gemHit = { x, y, r: 0.6 * s, side };                          // a click on the gem robs the party under it
  if (d.cut) {
    const age = d.age || 0, alpha = Math.max(0, Math.min(1, (40 - age) / 6));   // full brightness, gone 40 s after the breakout
    drawGem(ctx, x, y, s, t, { stage: 'cut', royal: !!d.royal, laws: d.laws || 0, alpha });
  } else drawGem(ctx, x, y, s, t, { stage: 'rough', alpha: 0.9 });
}
function drawAngelScene(snap, L, t, ph) {                     // the angel blesses (bubble on the runner) or blocks (light shields at the bank / mafia)
  const d = diaState(snap), ag = d.angel, s = L.s, idle = ph === 'lobby' || ph === 'aiming';
  if (ag) {
    const age = ag.age || 0, alpha = Math.max(0, Math.min(1, Math.min(age / 0.8, (40 - age) / 5)));
    const key = ag.mode + ':' + Math.round((G.t || 0) - age);
    if (key !== D.angelKey) { D.angelKey = key; if (idle && age < 3) snd(ag.mode === 'block' ? 'ping' : 'chime', { x: 0.5 }); }
    drawAngel(ctx, G.W * 0.56, L.groundY - 3.4 * s, s * 1.25, t, { mode: ag.mode, alpha });
    if (alpha > 0.05) {                                       // what the angel says, in a small scroll under her
      ctx.save(); ctx.globalAlpha = alpha; ctx.font = `bold ${Math.round(0.22 * s)}px sans-serif`; ctx.textAlign = 'center';
      const txt = ag.mode === 'block' ? `risk not allowed: ${ag.why}` : 'blessed: risk managed';
      const w = ctx.measureText(txt).width + 0.4 * s, x0 = G.W * 0.56, y0 = L.groundY - 1.75 * s;
      ctx.fillStyle = ag.mode === 'block' ? 'rgba(30,45,80,0.82)' : 'rgba(80,60,15,0.82)'; roundRect(ctx, x0 - w / 2, y0 - 0.22 * s, w, 0.34 * s, 0.08 * s); ctx.fill();
      ctx.fillStyle = ag.mode === 'block' ? '#dcecff' : '#ffe9a6'; ctx.fillText(txt, x0, y0 + 0.04 * s); ctx.restore();
    }
    if (ag.mode === 'block' && idle && alpha > 0.05) {         // two walls of light: in front of the bank and in front of the mafia
      if (L.bank && L.bank.sign) drawLightShield(ctx, L.bank.sign.cx + 2.6 * s, L.groundY - 3.0 * s, L.groundY + 0.2 * s, s, t, alpha);
      if (D.bossPos) drawLightShield(ctx, D.bossPos[0] - 1.6 * s, D.bossPos[1] - 2.6 * s, D.bossPos[1] + 0.6 * s, s, t, alpha);
    }
    if (ag.mode === 'bless') D.blessT = (G.t || 0) - age;
  }
  const r = snap.round;
  if (r && inRound(ph) && D.blessT != null && D.blessRid !== r.id && (G.t || 0) - D.blessT < 45) D.blessRid = r.id;   // the round shot on a blessing
  const blessedIdle = idle && D.blessT != null && (G.t || 0) - D.blessT < 40;
  const blessedRound = r && inRound(ph) && ph !== 'settled' && D.blessRid === r.id;
  if (blessedIdle || blessedRound) {
    const [rx, ry] = runnerPos();
    drawBubble(ctx, rx, ry - 0.85 * s, 1.05 * s, t, 1);
  }
}
function hintState(snap) {                                    // which volume hints to show now, relative to the player's trade
  const h = (typeof window !== 'undefined' && window.__ggHints) || (snap.market && snap.market.hints) || {}, r = snap.round, ph = G.phase;   // (__ggHints: screenshot self-tests only)
  const inR = (ph === 'open' || ph === 'closing') && r;
  const side = inR ? r.side : (snap.settings && snap.settings.side) || 1, res = inR ? (+r.result_usd || 0) : 0;
  const out = {
    side,
    trench: !!h.stopping && (inR ? h.stopping === side && res < 0 : ph === 'lobby'),        // buyers (sellers) absorbing against a losing slide
    cracks: !!h.trap && (inR ? h.trap === -side && res > 0 : ph === 'lobby'),               // a trap against a winning slide: take the profit
    vortex: !!h.sweep && (inR || ph === 'lobby'),
    polished: (inR || ph === 'lobby') ? (h.polished || 0) : 0,
  };
  return out.trench || out.cracks || out.vortex || out.polished ? out : null;
}
function drawNotes(x, y, s, t, f) {                            // music notes floating up while he dances
  ctx.save();
  for (let i = 0; i < 3; i++) {
    const ph = (t * 0.5 + i / 3) % 1, nx = x + f * (0.25 + 0.3 * ph) * s + Math.sin(t * 3 + i * 2) * 0.08 * s, ny = y - ph * 0.8 * s;
    ctx.globalAlpha = Math.sin(ph * Math.PI) * 0.9; ctx.fillStyle = ['#ffd84d', '#ff7ad9', '#7ff3ff'][i];
    ctx.beginPath(); ctx.ellipse(nx, ny, 0.05 * s, 0.038 * s, -0.4, 0, TAU); ctx.fill();
    ctx.fillRect(nx + 0.035 * s, ny - 0.2 * s, Math.max(1.5, 0.015 * s), 0.2 * s);
    ctx.beginPath(); ctx.moveTo(nx + 0.05 * s, ny - 0.2 * s); ctx.quadraticCurveTo(nx + 0.13 * s, ny - 0.15 * s, nx + 0.11 * s, ny - 0.08 * s); ctx.lineWidth = Math.max(1.5, 0.015 * s); ctx.strokeStyle = ctx.fillStyle; ctx.stroke();
  }
  ctx.restore();
}
function drawGloomCloud(x, y, s, t) {                         // a little grey rain cloud that follows him when the coin is sinking
  ctx.save();
  ctx.fillStyle = 'rgba(110,118,135,0.92)';
  ctx.beginPath(); for (const [dx, dy, r] of [[-0.18, 0, 0.13], [0, -0.07, 0.17], [0.18, 0, 0.13], [0.02, 0.05, 0.14]]) { ctx.moveTo(x + (dx + r) * s, y + dy * s); ctx.arc(x + dx * s, y + dy * s, r * s, 0, TAU); } ctx.fill();
  ctx.strokeStyle = 'rgba(160,190,230,0.85)'; ctx.lineWidth = Math.max(1, 0.014 * s); ctx.lineCap = 'round';
  for (let i = 0; i < 6; i++) { const ph = (t * 1.6 + i / 6) % 1, dx = (-0.2 + i * 0.08) * s, dy = (0.12 + ph * 0.45) * s; ctx.globalAlpha = 1 - ph; ctx.beginPath(); ctx.moveTo(x + dx, y + dy); ctx.lineTo(x + dx - 0.02 * s, y + dy + 0.08 * s); ctx.stroke(); }
  ctx.restore();
}
function poseFor(r, outfit) {
  const ph = G.phase, st = G.snap.settlement;
  if (ph === 'sending') return 'idle';
  if (ph === 'closing') return A.balloon > 0.1 ? 'fly' : 'tackle';
  if (ph === 'settled' && st) {
    switch (st.outcome) { case 'buyer': return 'cheer'; case 'anvil': return stopWon(st) ? (G.settle && G.settle.t < 2.2 ? 'cheer' : 'idle') : 'kneel'; case 'merchant': return G.settle && G.settle.t < 1.2 ? 'tackle' : 'idle'; case 'eject': return 'fly'; default: return 'idle'; }
  }
  const v = D.v, tl = D.tilt;
  if (outfit === 'tux' && tl > 0.3) return 'ride';
  if (Math.abs(v) > 0.03) return Math.sign(v) === Math.sign(tl) && Math.abs(tl) > 0.15 ? 'slide' : 'run';
  if (Math.abs(tl) > 0.25) return 'lean';
  return 'idle';
}
function tetherTension(r) {
  const dist = (D.x == null ? r.x : D.x) - (D.anvilX == null ? r.anvil.x : D.anvilX);
  const close = clamp(1 - dist / 0.4, 0, 1);
  const pull = D.tilt < 0 ? -D.tilt : 0;
  return clamp(0.08 + 0.55 * close + 0.45 * pull * (0.4 + 0.6 * close), 0, 1);
}

// ======================================================================================================== roof sign
function roofSign() {
  const snap = G.snap, ph = G.phase, r = snap.round, st = snap.settlement, sh = snap.market && snap.market.shutters;
  const hourglass = !snap.quote || (snap.feed && snap.feed.age_s > 2) || net.frozen();
  const now = snap.t;
  const clock = (until) => { const d = Math.max(0, (until || now) - now); const h = Math.floor(d / 3600), m = Math.floor((d % 3600) / 60), sec = Math.floor(d % 60); return h > 0 ? `${h}h${String(m).padStart(2, '0')}` : `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`; };
  // the sign never shows the gold price: before the shot the coin's stake ("the bank clearly shows $1 written on top of it"), during
  // the round the coin's live value (crimson below the stake, cyan above), after it the coin's final value (stake + result: on a
  // TP fill exactly the Buyer's tag). The signed result is the receipt's business.
  if (ph === 'sending') return { text: '· · ·', color: 'gold', hourglass };
  // Zee 2026-11-04: the sign shows the PROFIT or LOSS only (not stake + result): +$0.04 in green, -$0.03 in red
  if ((ph === 'open' || ph === 'closing') && r) return { text: signedMoney(r.result_usd, snap), color: profitColor(r.result_usd), hourglass };
  if (ph === 'settled' && st) {
    const alt = Math.floor(G.t / 2.2) % 2 === 0, won = stopWon(st);
    if (st.outcome === 'anvil' && alt) return won ? { text: 'LOCKED IN', color: 'cyan', hourglass: false } : { text: 'STOPPED', color: 'crimson', hourglass: false };
    if (st.outcome === 'barrel' && alt && !won) return { text: 'LIQUIDATED', color: 'crimson', hourglass: false };
    return { text: signedMoney(st.result_usd, snap), color: profitColor(st.result_usd), hourglass: false };
  }
  if (sh && sh.down) {
    if (sh.reason === 'jam') return { text: clock(sh.until || snap.limits.jam_until), color: 'crimson', hourglass: false };
    if (sh.reason === 'locked') return { text: 'TOMORROW', color: 'crimson', hourglass: false };
    if (sh.until) return { text: 'OPEN ' + clock(sh.until), color: 'crimson', hourglass };
    return { text: 'CLOSED', color: 'crimson', hourglass };
  }
  return { text: signedMoney(0, snap), color: 'gold', hourglass };          // before the shot: nothing won or lost yet
}
function signedMoney(usd, snap) { const v = +usd || 0, txt = money(v, riskOf(snap)); return v > 0 ? '+' + txt : txt; }
function profitColor(usd) { const v = +usd || 0; return v > 1e-9 ? 'green' : v < -1e-9 ? 'crimson' : 'gold'; }
function stakeText(snap) { const r = riskOf(snap); return money(r, r); }          // e.g. 1.00 cents: the coin's stake, formatted like the engine
function finalValueText(snap, st) {
  if (st.value_text) return st.value_text;                                          // the engine's own number
  const risk = (snap.round && snap.round.risk_usd) || riskOf(snap);
  return money(risk + (st.result_usd || 0), risk);
}
// the Buyer's tag - the second allowed number - drawn with the roof sign in the lit layer: after the storm / night / dead-market grades
// (under the grade only in a freeze, like the sign), glowing in the zeppelin lamp's light when the street is dark
function drawBuyerTagLit(L, t) {
  const B = D.buyerTag; if (!B || !B.text) return;
  const env = G.env || {}, dark = env.night || env.weather === 'storm' || env.weather === 'dead' || env.session === 'dead';
  art('drawBuyerTag', ctx, B.x, B.y, L.s, { tag: B.text, ang: B.ang, facing: B.f, t, glow: dark && !env.freeze ? 1 : 0 });
}
function drawRoofSignLit(L, t) {
  const b = L.bank, sign = roofSign();
  art('drawRoofSign', ctx, b.sign.cx, b.sign.cy, b.sign.w, b.sign.h, { id: 'roof', text: sign.text, color: sign.color, hourglass: !!sign.hourglass, t,
    wooden: !!(G.env && G.env.wooden) });
}

// ======================================================================================================== drawing: the frame
function drawFrame(dt) {
  const snap = G.snap, L = G.L, env = G.env, t = G.t, W = L.W, H = L.H, s = L.s, ph = G.phase;
  const r = snap.round, pv = snap.preview, st = snap.settlement;
  const rr = inRound(ph) ? r : null;
  const [sx, sy] = FXK.offset();
  const frozenDt = net.frozen() ? 0 : dt;
  // ---- sky (no roll) -------------------------------------------------------------------------------
  ctx.save();
  ctx.fillStyle = P.ink; ctx.fillRect(0, 0, W, H);
  if (D.flip) { const k = Math.max(0.015, Math.abs(Math.cos(Math.PI * D.flip.p))); ctx.translate(W / 2, 0); ctx.scale(k, 1); ctx.translate(-W / 2, 0); }
  ctx.translate(sx * 0.3, sy * 0.3);
  wcall('drawSky', ctx, W, H, env, t);
  ctx.restore();
  // ---- the world (camera roll + shake) ----------------------------------------------------------------
  ctx.save();
  applyCamera(ctx, sx, sy);
  const camX = (L.mirror ? -1 : 1) * ((D.x || 0.45) * W * 0.35 + D.pan * W);
  wcall('drawSkyline', ctx, W, H, camX, env, t);
  ctx.restore();
  ctx.save();
  if (D.flip) { const k = Math.max(0.015, Math.abs(Math.cos(Math.PI * D.flip.p))); ctx.translate(W / 2, 0); ctx.scale(k, 1); ctx.translate(-W / 2, 0); }
  wcall('drawSeasonBand', ctx, W, env, t);
  ctx.restore();

  ctx.save();
  applyCamera(ctx, sx, sy);
  drawTerrainAny(ctx, L.view, L.terrain, env, t);
  const pit = pitNow(rr);                                      // Zee 2026-11-04: no pit before a side is picked; the rat digs it after the fill
  if (pit && ph !== 'settled') wcall('drawPit', ctx, L.view, pit, env, t);
  if (A.dig && rr && rr.pit) drawDiggingRat(rr.pit, L, t);
  const HS = hintState(snap);
  if (HS && D.x != null) {
    if (HS.cracks) drawFaultLines(ctx, L, D.x, t);
    if (HS.polished) drawPolished(ctx, L, D.x, D.x + 0.28 * HS.polished * HS.side, t);
  }
  drawBankGroup(snap, L, env, t);                            // after the terrain: the seesawing street passes behind the bank's pier
  if (ph === 'settled' && st && st.outcome === 'barrel' && st.chasm) drawBarrelRift(st, L, env, t);   // ...but a gap tears through it
  drawDoorPlate(L, rr || pv, t);
  const deskStage = !!(G.settle && (G.settle.stage === 'fold' || G.settle.stage === 'desk'));
  drawStakes(snap, L, rr, pv, t);
  if (rr && !deskStage) drawAnvilTether(rr, L, t);
  if (rr && rr.golden && !deskStage) drawGoldenStake(rr, L, t);   // in front of the anvil: after the machete the vault anvil stands exactly on it
  drawBuyerGroup(snap, L, rr, pv, t);                         // behind the riders and the Runner (Zee: the girl must never hide)
  const tackling = rr && ((ph === 'closing' && G.last && G.last.action === 'merchant') || (ph === 'settled' && snap.settlement && snap.settlement.outcome === 'merchant' && G.settle && G.settle.t < 2.4));
  if (tackling && !deskStage) drawTackledMerchant(rr, L, t);
  else if (rr && rr.merchant && rr.merchant.visible && D.mx != null && ph !== 'settled') drawMerchant(rr, L, t);
  if (rr && !deskStage) drawRat(rr, L, t, dt);
  if (rr && !deskStage) drawGhostsTwin(rr, L, t);
  const sh = snap.market && snap.market.shutters;
  if (!deskStage) drawRunnerGroup(snap, L, rr, pv, t);
  drawShootout(L, t);
  drawDiamondGem(snap, L, t, dt);                              // the gem over the party to shoot (lobby / aiming only)
  drawAngelScene(snap, L, t, ph);                              // Zee 2026-11-06: the risk manager's verdict on the last breakout
  if ((ph === 'lobby' || ph === 'aiming') && uhvSteady(snap)) {   // the yogi sits on the ground by day; his orb shines with the diamond (40 s)
    const dd = diaState(snap);
    const shine = dd.cut ? Math.max(0, Math.min(1, (40 - (dd.age || 0)) / 6)) : 0;
    const near = dd.level_pips != null ? Math.max(0, Math.min(1, 1 - Math.max(0, dd.level_pips) / 1.5)) : 0;   // 1 = price at the level
    const calm = !dd.cut && dd.u97_age != null && dd.u97_age < 126;
    D.yogiMem = D.yogiMem || {};
    D.yogiHit = drawYogi(ctx, W * 0.36, L.groundY - 0.5 * s, s * 1.5, t, { shine, near, calm, look: G.pointer, t0poke: D.yogiPoke, mem: D.yogiMem, appear: D.yogiAppear != null ? t - D.yogiAppear : 99 });
  } else D.yogiHit = null;
  if (HS && D.x != null) {
    const hx = L.xToScreen(D.x), hy = L.gy(D.x);
    if (HS.trench) drawFrictionTrench(ctx, hx, hy, L.s, t, L.facing);
    if (HS.vortex) drawVortex(ctx, hx, hy, L.s, t);
  }
  wcall('drawFog', ctx, L.view, (D.tpX || 1) + 0.45, env, t);   // beyond the boss's whole group (he must stand in clear air)
  if (sh && sh.down && ph === 'lobby' && sh.reason === 'locked') SCR.drawLocked(ctx, L, snap, G, t);
  ctx.restore();

  // ---- the lit layer: the roof sign and the foreground furniture stay legible under the storm, night and dead-market grades. During
  //      a Time Freeze they are drawn under the grade so they go sepia with everything else (nothing can be sent then).
  const frozenNow = net.frozen();
  const litLayer = () => {
    ctx.save(); applyCamera(ctx, sx, sy); drawRoofSignLit(L, t); drawBuyerTagLit(L, t);
    SCR.drawNeedle(ctx, L, net.frozen(), t, Math.max(D.freezeK || 0, net.frozen() ? 1 : 0));   // the gramophone on the roof sign
    ctx.restore();
    drawForeground(snap, L, rr, ph, sh, t, dt);
    ctx.save(); ctx.translate(sx, sy); FXK.draw(ctx); ctx.restore();   // particles fly over the desk (the shavings into the jar)
  };
  if (frozenNow) litLayer();
  // ---- weather and grade over the street (world.js: its lightning strike + flash is the only lightning flash)
  wcall('drawWeather', ctx, W, H, env, frozenDt, t);
  drawRiskRain(snap, W, H, t);                                // Zee 2026-11-06: rain = risk (0 sun .. 3 storm)
  wcall('drawGrade', ctx, W, H, env, t);
  if (!frozenNow) litLayer();
  if (D.flip) drawPageShadow(W, H, D.flip.p);

  // ---- hold rings and overlays -----------------------------------------------------------------------------------
  drawHoldRing(L, t);
  SCR.drawCorners(ctx, L, snap, G, t);
  SCR.drawModeBadge(ctx, L, snap, G, t);
  if (G.ui.rest && ph === 'lobby') SCR.drawRest(ctx, L, snap, t);
  liveFrameEl.hidden = !(snap.mode === 'live' && (snap.settings.live_enabled || (r && r.kind === 'live')));
  if (G.ui.debug) drawDebug(L);
}

// the foreground furniture: the lobby desk, the settlement desk, the shutter plaque, the eject button, the jar
function drawForeground(snap, L, rr, ph, sh, t, dt) {
  G.lobbyL = null; G.settleL = null;
  if (D.deskInit !== true) { D.desk = ph === 'lobby' ? 1 : 0; D.deskInit = true; }
  D.desk = easeTo(D.desk, ph === 'lobby' ? 1 : 0, 5, G.realDt || dt);          // UI furniture moves on real time, even in a freeze
  if (ph === 'lobby' || ph === 'aiming' || D.desk > 0.01) {
    G.lobbyL = SCR.lobbyLayout(L, D.desk);
    if (D.desk > 0.01) SCR.drawLobby(ctx, L, G.lobbyL, snap, G, t);
  }
  if (ph === 'aiming' && !G.lobbyL) G.lobbyL = SCR.lobbyLayout(L, 0);
  if (ph === 'settled' && G.settle) drawSettlement(snap, L, t, dt);
  if (sh && sh.down && ph === 'lobby' && sh.reason !== 'locked' && sh.reason !== 'jam') SCR.drawShutterPlaque(ctx, L, sh, snap.t, t, A.shutterRattle);
  if (ph === 'open' && rr) SCR.drawEjectButton(ctx, L, G, t, snap.settings.eject_words, !!G.pendings.eject);
  if (rr && ph !== 'settled') SCR.drawJar(ctx, L, snap, t);
}

function drawPageShadow(W, H, p) {
  const k = Math.abs(Math.cos(Math.PI * p)), w = W * k;
  ctx.save();
  const g = ctx.createLinearGradient(W / 2 - w / 2, 0, W / 2 + w / 2, 0);
  const dark = 0.55 * (1 - k);
  g.addColorStop(0, `rgba(0,0,0,${dark})`); g.addColorStop(0.5, `rgba(255,240,200,${0.18 * (1 - k)})`); g.addColorStop(1, `rgba(0,0,0,${dark})`);
  ctx.fillStyle = g; ctx.fillRect(W / 2 - w / 2, 0, w, H);
  ctx.restore();
}

function drawBankGroup(snap, L, env, t) {
  const s = L.s, b = L.bank, ph = G.phase, sh = snap.market && snap.market.shutters, f = 1;
  // the little island the bank stands on, in the lake (the street seesaws, the bank does not)
  ctx.save();
  {
    const px0 = b.x - b.w / 2 - 0.25 * s, pw = b.w + 0.5 * s, top = b.y - 0.04 * s, depth = b.dest ? L.H - b.y + 0.5 * s : 1.1 * s;
    ctx.beginPath(); ctx.moveTo(px0, top);
    if (b.dest) { ctx.lineTo(px0, top + depth); ctx.lineTo(px0 + pw, top + depth); }      // selling: a straight stone pier down into the garden
    else for (let i = 0; i <= 10; i++) { const x = px0 + pw * (i / 10); ctx.lineTo(x, top + depth * (0.75 + 0.25 * Math.sin(i * 1.9)) + (i === 0 || i === 10 ? -0.4 * s : 0)); }
    ctx.lineTo(px0 + pw, top); ctx.closePath();
    const g = ctx.createLinearGradient(0, top, 0, top + depth); g.addColorStop(0, '#9b8f7d'); g.addColorStop(1, '#5d564c');
    ctx.fillStyle = g; ctx.fill(); inkStroke(ctx, s, LINE.inkThin); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.12)';
    for (let i = 0; i < 7; i++) { ctx.beginPath(); ctx.ellipse(px0 + pw * (0.1 + 0.13 * i), top + depth * (0.3 + 0.25 * ((i * 7) % 3) / 2), 0.18 * s, 0.08 * s, 0, 0, TAU); ctx.fill(); }
    ctx.fillStyle = '#7fcf55'; ctx.fillRect(px0, top - 0.02 * s, pw, 0.1 * s);
    ctx.fillStyle = '#5fae45'; ctx.fillRect(px0, top + 0.07 * s, pw, 0.03 * s);
  }
  ctx.restore();
  const shutters = sh && sh.down && sh.reason !== 'jam' && ph !== 'open' && ph !== 'closing' ? 1 : 0;
  D.shut = D.shut == null ? shutters : easeTo(D.shut, shutters, 3, 1 / 60);
  const rattle = A.shutterRattle > 0 ? Math.sin(t * 60) * A.shutterRattle * 0.04 * s : 0;
  const crane = !b.dest && ph === 'settled' && snap.settlement && snap.settlement.outcome === 'anvil' && !stopWon(snap.settlement) && G.settle ? clamp((G.settle.t - 0.3) / 1.2, 0, 1) : 0;
  let bm = bankerMood();
  const hostile = !b.dest && (ph === 'sending' || ph === 'open' || ph === 'closing');   // buying: the robbed bank is furious all round
  if (hostile && bm !== 'shot') bm = 'angry';
  if (b.dest) {                                              // selling: the bank is not robbed, it waits happily for the coin
    const st0 = snap.settlement;
    bm = ph === 'settled' && st0 && st0.outcome === 'buyer' ? 'gloat' : (bm === 'shot' || bm === 'sulk' || bm === 'crane') ? 'smug' : bm;
  }
  const bg = drawCottageBank(ctx, b.x + rattle, b.y, s, { t, facing: f, shutters: D.shut, jammed: !!(sh && sh.down && sh.reason === 'jam'),
    night: !!G.env.night, wooden: !!G.env.wooden, banker: { mood: bm, crane }, alert: !!(A.shootout && A.shootout.side > 0) || hostile, fireFlash: A.shootout ? A.shootout.eflash : 0, knocked: knockedCount(1), knockProg: knockProgress(1), runnerX: D.x != null ? L.xToScreen(D.x) : null });
  if (bg && bg.craneTip && isFinite(bg.craneTip.x)) b.craneTip = { x: bg.craneTip.x, y: bg.craneTip.y };
  // (the roof sign is drawn in the lit layer, after the weather and the grade: drawRoofSignLit)
  // the Golden Bell on its belfry above the sign; the rope runs over a pulley at the roof corner and hangs to the street
  art('drawBell', ctx, b.bell.x, b.bell.y, s, { swing: A.bellSwing, shock: A.bellShock < 1 ? A.bellShock : 0, t });
  const rope = bellRope(L);
  ctx.save();
  const sway = Math.sin(t * 5) * (A.bellSwing + A.ropeTug) * 0.12 * s;
  ctx.strokeStyle = '#d8c08a'; ctx.lineWidth = Math.max(1.5, 0.022 * s); ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(rope.x0, rope.y0); ctx.quadraticCurveTo((rope.x0 + rope.px) / 2, rope.py - 0.05 * s, rope.px, rope.py);
  ctx.quadraticCurveTo(rope.px + sway, (rope.py + rope.y1) / 2, rope.x1 + sway * 0.5, rope.y1 + A.ropeTug * 0.15 * s); ctx.stroke();
  ctx.beginPath(); ctx.arc(rope.px, rope.py, 0.07 * s, 0, TAU); shade(ctx, rope.px - 0.07 * s, rope.py - 0.07 * s, 0.14 * s, 0.14 * s, P.brass); inkStroke(ctx, s, LINE.inkThin); ctx.stroke();
  ctx.fillStyle = P.crimson; ctx.beginPath(); ctx.ellipse(rope.x1 + sway * 0.5, rope.y1 + 0.08 * s + A.ropeTug * 0.15 * s, 0.05 * s, 0.1 * s, 0, 0, TAU); ctx.fill(); ctx.stroke();
  ctx.restore();
  if (sh && sh.down && sh.reason === 'jam' && ph === 'lobby') SCR.drawJamDressing(ctx, L, snap, t);
}
// The barrel's Void Chasm (REQUIREMENTS 5.4: drawn where the price jumped, so the player sees exactly why the anvil never caught). An
// initial-stop gap always lands at x < 0, under the bank's iron pier, which the street passes behind - so the chasm is torn again on top
// of the pier: it opens from the stop (the anvil) back to the fill (where the runner was dragged), and its far lip bites 0.03 into the
// street so it reads as the ground giving way at the door. A gap out on the open street is already torn in the terrain itself.
function drawBarrelRift(st, L, env, t) {
  const lo = Math.min(st.chasm[0], st.chasm[1]), hi = Math.max(st.chasm[0], st.chasm[1]);
  if (!isFinite(lo) || !isFinite(hi) || lo > -0.02) return;
  const s = L.s, b = L.bank, k = ease(clamp(((G.settle ? G.settle.t : 9) - 0.15) / 0.55, 0, 1));
  if (k <= 0) return;
  const pa = b.x - b.w / 2 - 0.1 * s, pb = b.x + b.w / 2 + 0.1 * s, pierTop = b.y - 0.04 * s;
  // a chasm that also reaches out onto the street is torn there by the terrain itself: the rift then ends at the pier's street-side
  // edge (never a second void and rim on top of the first); otherwise its lip bites 0.03 into the street
  const edge = L.xFromScreen(L.facing > 0 ? pb : pa);
  const right = hi > 0.01 ? edge : Math.max(hi, 0) + 0.03, left = lerp(right - 0.02, lo + 0.015, k);   // tears open from the stop toward the vault
  wcall('drawChasmRift', ctx, L.view, [left, right], env, t, {
    topAt: (px) => (px >= Math.min(pa, pb) && px <= Math.max(pa, pb) ? pierTop : L.gy(L.xFromScreen(px))), bottom: L.H + 30 });
}
function bellRope(L) {
  const s = L.s, b = L.bank, f = 1;
  return { x0: b.bell.x - f * 0.32 * s, y0: b.bell.y - 0.3 * s, px: b.x - f * (b.w / 2 + 0.1 * s), py: b.y - 2.3 * s,
    x1: b.x - f * (b.w / 2 + 0.18 * s), y1: b.y - 0.55 * s };
}

// the screen angle of the walking line at xn (world.js shears the street: verticals stay vertical, the ground line turns)
function slopeAt(L, xn) {
  const e = 0.004;
  let xa = L.xToScreen(xn - e), xb = L.xToScreen(xn + e), ya = L.gy(xn - e), yb = L.gy(xn + e);
  if (xb < xa) { let q = xa; xa = xb; xb = q; q = ya; ya = yb; yb = q; }
  const v = Math.atan2(yb - ya, (xb - xa) || 1e-6);
  return isFinite(v) ? v : 0;
}
function drawDoorPlate(L, src, t) {                         // a brass threshold in the street at the entry price: "the door"
  if (!src || !isFinite(src.x_entry)) return;
  const s = L.s, x = L.xToScreen(src.x_entry), y = L.gy(src.x_entry);
  ctx.save();
  ctx.translate(x, y); ctx.transform(1, Math.tan(slopeAt(L, src.x_entry)), 0, 1, 0, 0);   // lies in the sheared street
  ctx.fillStyle = P.goldDeep; ctx.fillRect(-0.03 * s, -0.02 * s, 0.06 * s, 0.1 * s);
  glow(ctx, 0, 0, 0.18 * s, P.gold, 0.25);
  ctx.restore();
}

function drawStakes(snap, L, rr, pv, t) {
  const s = L.s, list = rr ? rr.stakes : pv ? pv.stakes : [];
  const anvilPrice = rr && rr.anvil ? rr.anvil.price : null;
  for (const st of list || []) {
    if (st.x < L.lo - 0.05 || st.x > L.lo + L.span + 0.05) continue;
    const x = L.xToScreen(st.x), y = L.gy(st.x);
    const atAnvil = anvilPrice != null && Math.abs(st.price - 0.01 * (rr.side || 1) - anvilPrice) < 0.006;
    const fl = A.stakeFlash.find((f) => Math.abs(f.x - st.x) < 0.01);
    const eligible = !!(rr && st.passed && st.lit && !st.used && rr.side * (st.price - rr.sl) > 0);   // the anvil may be dragged here now
    if (eligible) { ctx.save(); glow(ctx, x, y - 0.05 * s, 0.35 * s, P.gold, 0.35 + 0.15 * Math.sin(t * 3 + st.x * 20)); ctx.restore(); }
    // lit stakes stand taller than the old rusty ones, with a tie ring for the rope (eligible: the ring pulses)
    art('drawStake', ctx, x, y, s * (st.lit && !st.used ? 1.25 : 1), { lit: !!st.lit, golden: false, rusty: !!(st.used && !atAnvil), initials: '', t, label: null, eligible });
    if (fl) { ctx.save(); glow(ctx, x, y - 0.6 * s, (0.3 + fl.t) * s, P.goldHot, Math.max(0, 0.8 - fl.t)); ctx.restore(); }
  }
  if (rr) for (const w of rr.walls || []) {
    const key = String(w.x); let b = 1;
    if (A.walls.has(key)) { b = clamp(A.walls.get(key) / 0.8, 0, 1); }
    // bricks stand upright on the sheared street, sunk just enough that neither bottom corner floats
    const x = L.xToScreen(w.x), y = L.gy(w.x) + Math.abs(Math.tan(slopeAt(L, w.x))) * 0.16 * s;
    art('drawWall', ctx, x, y, s, { build: b, t, rat: !!(A.rat && A.rat.why === 'slippage') });
  }
}

// the golden stake (the round's worst remaining outcome after the machete). The re-projected vault anvil lands exactly on it - that is
// the proof the stake rule is right - so it is drawn after the anvil, in front of it, and its paper tag is big enough to read.
function drawGoldenStake(rr, L, t) {
  const s = L.s, g = rr.golden, x = L.xToScreen(g.x), y = L.gy(g.x);
  ctx.save(); glow(ctx, x, y - 0.35 * s, 0.75 * s, P.goldHot, 0.35 + 0.1 * Math.sin(t * 2.2)); ctx.restore();   // the banked floor glows
  art('drawStake', ctx, x, y, s * 1.15, { lit: true, golden: true, rusty: false, initials: 'ZZ', t, label: g.text, bigLabel: true });
}
function drawAnvilTether(r, L, t) {
  const s = L.s, ax0 = D.anvilX == null ? r.anvil.x : D.anvilX;
  let ax = L.xToScreen(ax0), ay = L.gy(ax0);
  const st = G.snap.settlement;
  const tension = G.phase === 'settled' ? (st && (st.outcome === 'anvil' || st.outcome === 'barrel') ? 1 : 0.05) : tetherTension(r);
  G.tension = tension;
  const pending = !!G.pendings.anvil_next || !!G.pendings.wall || !!G.pendings.haggle || (r.anvil && r.anvil.pending);
  const dragging = !!(G.drag && G.drag.item === 'anvil');
  let ang = 0, shear = 0;                                         // resting: its flat base follows the sheared ground; dragged: it swings
  if (dragging) { const [lx, ly] = toLayout(G.drag.x, G.drag.y); ax = lx; ay = ly + 0.25 * s; ang = Math.sin(t * 9) * 0.08; }
  else shear = Math.tan(slopeAt(L, ax0));
  ctx.save(); ctx.translate(ax, ay); if (ang) ctx.rotate(ang); if (shear) ctx.transform(1, shear, 0, 1, 0, 0); ctx.translate(-ax, -ay);
  const pts = art('drawAnvil', ctx, ax, ay, s, { glow: dragging ? 0.6 : pending ? 0.5 + 0.5 * Math.sin(t * 9) : r.anvil.kind === 'vault' ? 0 : 0.25, t,
    bounce: A.anvilBounce, facing: L.facing, kind: r.anvil.kind });
  ctx.restore();
  let rx = ax + L.facing * 0.2 * s, ry = ay - 0.18 * s;
  if (ptsOK(pts, 'ringX')) {                                     // the ring point, through the anvil's own transform
    const dx = pts.ringX - ax, dy = pts.ringY - ay, c = Math.cos(ang), sn = Math.sin(ang);
    rx = ax + dx * c - dy * sn; ry = ay + dx * sn + dy * c + dx * shear;
  }
  const hideRope = G.phase === 'settled' && st && st.outcome !== 'anvil' && st.outcome !== 'barrel' && G.settle && G.settle.t > 1;
  if (!hideRope) {                                                // the slack rope lies on the street (and the pit lip), never through the deck
    const [bx, by] = beltPos();
    art('drawTether', ctx, bx, by, rx, ry, s, { tension: dragging ? 0.3 : tension, t, groundAt: (px) => L.gy(L.xFromScreen(px)) - 0.02 * s });
  }
}

const GIRL_MARGIN = 0.0008;                                       // = engine merchant_profit_margin
function drawMerchant(r, L, t) {
  const s = L.s, m = r.merchant, x = L.xToScreen(D.mx), y = L.gy(D.mx);
  D.distance = (D.distance || 0) + Math.abs((D.mx - (D.lastMx == null ? D.mx : D.lastMx)) * L.W / L.span);
  D.lastMx = D.mx;
  const facing = (m.dir || -1) * (L.mirror ? -1 : 1);
  // his neon sign rides at the height of the Buyer's price tag: where the two would overlap he ducks the pole (both stay readable)
  let want = 0;
  if (ptsOK(D.buyerPts, 'tagX')) {
    const B = D.buyerPts, gx = Math.abs(x - facing * 0.15 * s - B.tagX) - 0.85 * s, gy = Math.abs(y - 1.6 * s - B.tagY) - 0.5 * s;
    if (gy < 0) want = clamp(1 - gx / (0.7 * s), 0, 1);
  }
  D.duck = easeTo(D.duck || 0, want, 9, G.realDt || 0.016);
  // no number on him any more: the rider IS the offer. Selling now would book a profit -> the girl with the ice cream; a loss -> the thief.
  // Zee 2026-11-04: the girl appears only when selling is a sure profit (ahead by the safety margin the engine also checks); between zero
  // and that margin nobody rides (she vanishes until she is profitable again); the thief only when selling would be a loss.
  const res = +r.result_usd || 0, prev = D.cycKind, M = isFinite(r.girl_margin_usd) ? +r.girl_margin_usd : GIRL_MARGIN;
  const kind = res >= M ? 'girl' : res <= 0 ? 'thief' : null;
  if (prev && kind && prev !== kind) { FXK.burst('smoke', x, y - 0.5 * s, { n: 10 }); snd(kind === 'girl' ? 'chime' : 'click'); }
  D.cycKind = kind;
  if (kind) drawCyclist(ctx, x, y, s, { kind, roll: D.distance / (0.2 * s), t, facing, tackled: A.tackle });
  if (m.insists) { ctx.save(); glow(ctx, x, y - 1.4 * s, 0.6 * s, P.neonPink, 0.4 + 0.2 * Math.sin(t * 8)); ctx.restore(); }
}

function drawTackledMerchant(r, L, t) {
  const s = L.s, f = L.facing, xn = (D.x == null ? r.x : D.x);
  const x = L.xToScreen(xn) + f * 0.55 * s, y = L.gy(xn);
  const k = clamp(A.tackle, 0, 1);
  const st0 = G.snap && G.snap.settlement, won = st0 ? (+st0.result_usd || 0) > 0 : (+r.result_usd || 0) > 0;
  drawCyclist(ctx, x, y, s, { kind: won ? 'girl' : 'thief', roll: G.t * 3, t, facing: -f, tackled: 1 - k * 0.0 });
  if (Math.random() < 0.3) FXK.burst('dust', x, y, { n: 2 });
}
function drawRat(r, L, t, dt) {
  const R = A.rat; if (!R) return;
  const s = L.s, toX = D.x == null ? r.x : D.x;
  const tr = 0.9, bite = 0.7;
  let xn, phase;
  if (R.t < tr) { xn = lerp(R.from, toX, ease(R.t / tr)); phase = R.t < 0.25 ? 'peek' : 'run'; }
  else if (R.t < tr + bite) { xn = toX; phase = 'bite'; if (!R.bit) { R.bit = true; snd('rat', { n: 3 }); const [cx, cy] = coinPos(); const [jx, jy] = jarPos(); FXK.burst('shavings', cx, cy, { to: [jx, jy], n: 6 + Math.round(clamp((R.usd || 0) / riskOf(G.snap) * 40, 0, 10)) }); setTimeout(() => snd('ping'), 650); setTimeout(() => snd('ping'), 820); } }
  else if (R.t < tr * 2 + bite) { xn = lerp(toX, R.from, ease((R.t - tr - bite) / tr)); phase = 'run'; }
  else { A.rat = null; return; }
  const x = L.xToScreen(xn), y = L.gy(xn);
  const dir = (phase === 'run' && R.t > tr ? -1 : 1) * Math.sign(toX - R.from || 1) * L.facing;
  drawWhiteRat(ctx, x, y, s, { pose: phase === 'peek' ? 'sit' : phase, t, facing: dir });
}

function drawGhostsTwin(r, L, t) {
  const s = L.s, f = L.facing;
  for (const g of r.ghosts || []) {
    const xg = interpPath(g.path, r.age_s);
    if (xg == null) continue;
    art('drawGhost', ctx, L.xToScreen(xg), L.gy(xg) - 0.06 * s, s * 0.96, { pose: 'run', facing: f, t: t + g.id.length, alpha: 0.32 });
  }
  if (r.twin && D.twinX != null) {
    // the Twin runs one lane behind: a brass track along the back of the street, so he is visible even when his result equals the
    // player's. Only depth separates them (set back, smaller, dimmer); his x is his own result, never nudged for legibility.
    const lane = 0.72 * s, ks = 0.72;
    const laneY = (xn) => L.gy(xn) - lane;
    ctx.save();
    ctx.globalAlpha = 0.85; ctx.lineCap = 'round';
    const xa = -0.02, xb = Math.max(1.02, (D.tpX || 1) + 0.02);
    for (let xn = 0; xn <= xb + 1e-6; xn += 0.1) {               // the posts
      const px = L.xToScreen(xn), gy = L.gy(xn);
      ctx.strokeStyle = P.ink; ctx.lineWidth = Math.max(2.5, 0.045 * s); ctx.beginPath(); ctx.moveTo(px, gy - lane); ctx.lineTo(px, gy - 0.02 * s); ctx.stroke();
      ctx.strokeStyle = P.brassDark; ctx.lineWidth = Math.max(1.2, 0.022 * s); ctx.stroke();
    }
    ctx.beginPath();                                               // the rail
    for (let xn = xa, i = 0; xn <= xb + 1e-6; xn += 0.02, i++) { const px = L.xToScreen(xn), py = laneY(xn); if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py); }
    ctx.strokeStyle = P.ink; ctx.lineWidth = Math.max(3, 0.06 * s); ctx.stroke();
    ctx.strokeStyle = P.brass; ctx.lineWidth = Math.max(1.5, 0.03 * s); ctx.stroke();
    ctx.strokeStyle = rgba(P.goldHot, 0.6); ctx.lineWidth = Math.max(1, 0.01 * s); ctx.translate(0, -0.008 * s); ctx.stroke();
    ctx.restore();
    const ax = L.xToScreen(r.twin.anvil_x), ay = laneY(r.twin.anvil_x);
    const tx = L.xToScreen(D.twinX), ty = laneY(D.twinX);
    ctx.save(); ctx.globalAlpha = 0.6;
    art('drawTether', ctx, ax, ay - 0.25 * s * ks, tx, ty - 0.45 * s * ks, s * ks, { tension: 0.2, t });
    art('drawAnvil', ctx, ax, ay, s * ks * 0.9, { glow: 0, t, bounce: 0 });
    ctx.restore();
    art('drawTwin', ctx, tx, ty, s * ks, { pose: r.twin.state === 'done' ? 'idle' : 'run', lean: D.tilt * 0.6, facing: f, t, alpha: 0.78 });
  }
}

function keepPts(p) {
  if (!ptsOK(p, 'coinX')) return;
  D.pts = { coinX: p.coinX, coinY: p.coinY, coinR: p.coinR, handX: p.handX, handY: p.handY, gripX: p.gripX, gripY: p.gripY,
    headX: p.headX, headY: p.headY, beltX: p.beltX, beltY: p.beltY };
}
function drawRunnerGroup(snap, L, rr, pv, t) {
  const s = L.s, ph = G.phase, f = L.facing;
  const xn = barrelXn(D.x != null ? D.x : rr && isFinite(rr.x) ? rr.x : pv && isFinite(pv.x_entry) ? pv.x_entry : 0.45);   // never a made-up spot
  let x = L.xToScreen(xn), y = L.gy(xn);
  if (ph === 'lobby' || ph === 'aiming') {
    if (A.flinch > 0) x += Math.sin(A.flinch * 30) * 0.06 * s * A.flinch;   // ducking a bullet
    const wooden = G.ui.kind === 'wooden';
    const aimF = -f;                                           // at the door, facing the Banker
    const patience = pv && ph === 'aiming' ? clamp(((pv.patience_s || 0) - 30) / 6, 0, 1) : 0;
    if (patience > 0) {                                        // the patience glow: inked gold sparkles and a ring at his feet, never on the pistol
      ctx.save();
      ctx.globalAlpha = patience;
      ctx.lineWidth = Math.max(3, 0.06 * s); ctx.strokeStyle = P.ink;
      ctx.beginPath(); ctx.ellipse(x, y + 0.02 * s, 0.6 * s, 0.13 * s, 0, 0, TAU); ctx.stroke();
      ctx.lineWidth = Math.max(2, 0.035 * s); ctx.strokeStyle = P.gold; ctx.stroke();
      glow(ctx, x, y - 0.5 * s, 1.1 * s, P.gold, 0.22 + 0.06 * Math.sin(t * 1.6));
      for (let i = 0; i < 6; i++) {
        const a0 = t * 0.8 + i * (TAU / 6), rr = (0.62 + 0.06 * Math.sin(t * 1.3 + i)) * s;
        const px = x + Math.cos(a0) * rr, py = y - 0.6 * s + Math.sin(a0) * rr * 0.5, k = 0.06 * s * (0.8 + 0.3 * Math.sin(t * 3 + i));
        ctx.beginPath();
        for (let j = 0; j < 8; j++) { const aa = (j / 8) * TAU, rk = j % 2 ? k * 0.38 : k; ctx.lineTo(px + Math.cos(aa) * rk, py + Math.sin(aa) * rk); }
        ctx.closePath(); ctx.fillStyle = P.gold; ctx.fill(); ctx.lineWidth = Math.max(1, 0.012 * s); ctx.strokeStyle = P.ink; ctx.stroke();
      }
      ctx.restore();
    }
    if (snap.settings.twin_invited) art('drawTwin', ctx, x - f * 0.6 * s, y - 0.1 * s, s * 0.92, { pose: 'idle', lean: 0, facing: ph === 'aiming' ? aimF : f, t, alpha: 0.75 });
    const bounce = A.noteBounce > 0 ? Math.sin(A.noteBounce * Math.PI * 3) * 0.12 * s * A.noteBounce : 0;
    const holding = ph === 'lobby' && !(G.drag && G.drag.item);
    const hugToken = false;                                   // Zee 2026-11-04: no coin before the shot - both runners hold a note; the Banker hurls the coin
    if (hugToken) { ctx.save(); glow(ctx, x + f * 0.1 * s, y - 0.55 * s + bounce, 0.38 * s, P.gold, 0.35); ctx.restore(); }
    const idle = ph === 'lobby' ? idleNow() : null;
    if (idle) {                                               // the market is asleep: so is he (click him, or any key, and he is ready again)
      const wooden0 = G.ui.kind === 'wooden';
      drawIdleScene(ctx, idle.kind, x, y, s, t, f, (c2, xx, yy, ss, o) => art('drawRunner', c2, xx, yy, ss, { outfit: 'suit', pose: o.pose, lean: o.lean,
        facing: o.facing, t, face: o.face, coin: { visible: false }, hat: false, cane: false, alpha: 1, wooden: false, tint: null }), idle.k);
      return;
    }
    drawWhiteRat(ctx, x + f * 0.6 * s, y, s, { pose: 'sit', t, facing: -f });   // the white rat waits to dig the pit once a side is picked
    drawHunterBack(ctx, x, y, s, ph === 'aiming' ? aimF : f);          // a longbow and a quiver on his back
    const pts = art('drawRunner', ctx, x, y + (hugToken ? bounce * 0.3 : 0), s, { outfit: 'suit', pose: ph === 'aiming' ? 'aim' : 'hold', lean: ph === 'aiming' ? 0 : D.tilt * 0.3,
      facing: ph === 'aiming' ? aimF : f, t, coin: hugToken ? { visible: true, glow: 0.25, tarnish: 0, half: false, spin: (t * 0.25) % 1, wooden: true } : { visible: false },
      hat: false, cane: false, alpha: 1, wooden: false, tint: null, face: ph === 'aiming' ? 'focus' : 'determined' });   // Zee 2026-11-04: a fair, dead-serious hunter (never the wooden puppet)          // the Alley's runner is the Apprentice, a wooden puppet
    keepPts(pts);
    drawHunterFace(pts, s, ph === 'aiming' ? aimF : f);
    const hx = ptsOK(pts, 'handX') ? pts.handX : x + (ph === 'aiming' ? aimF : f) * 0.32 * s;
    const hy = ptsOK(pts, 'handY') ? pts.handY : y - 0.62 * s;
    // Zee 2026-11-04: "an expert hunter with a bow and arrow and holding a shotgun -> we're here to hunt for gold" (no paper money)
    if (ptsOK(pts, 'headX')) drawHunterHat(ctx, pts.headX, pts.headY, s, ph === 'aiming' ? aimF : f);
    if (ph === 'aiming') drawShotgun(ctx, hx, hy, s, aimF, true, A.recoil);   // (a shootout makes him fire again and again: A.recoil pulses)
    else if (holding) drawShotgun(ctx, hx, hy + bounce, s, f, false);
    return;
  }
  if (!rr) return;
  const outfit = outfitFor(rr);
  let pose = poseFor(rr, outfit);
  if (A.fetch && (ph === 'open' || ph === 'sending')) {         // Zee 2026-11-04: he runs to fetch the coin, then back to where the price says he stands
    const k = A.fetch.t / A.fetch.dur, u = k < 0.4 ? ease(k / 0.4) : k < 0.55 ? 1 : 1 - ease((k - 0.55) / 0.45);
    x = lerp(x, A.fetch.to, u); y = lerp(y, isFinite(A.fetch.toY) ? A.fetch.toY : y, u); pose = 'run';
  }
  const st = snap.settlement;
  const pit = pitNow(rr);
  let sink = 0;
  if (pit && (ph === 'open' || ph === 'sending' || ph === 'closing')) { const v = wcall('pitSinkAt', L.view, pit, xn); sink = isFinite(v) ? v : 0; }
  let lift = 0;
  if ((ph === 'closing' && A.balloon > 0) || (ph === 'settled' && st && st.outcome === 'eject')) {
    const k = ph === 'settled' ? clamp((G.settle ? G.settle.t : 0) / 2.0, 0, 1) : 0;
    lift = ease(k) * 1.6 * s;
  }
  // the barrel falls over him (rare: a gap through the stop)
  if (ph === 'settled' && st && st.outcome === 'barrel' && G.settle && G.settle.t <= 0.55) {
    const k = G.settle.t / 0.55;
    art('drawBarrel', ctx, x, y - (1 - k * k) * 4 * s, s, { t, blink: false });
  }
  const wooden = rr.kind === 'wooden';
  const value = clamp((xn - rr.x_entry) / Math.max(0.05, 1 - rr.x_entry), 0, 1);
  const coinVisible = ph !== 'sending' || (A.coinArc && A.coinArc.t >= A.coinArc.dur);
  if ((ph === 'open' || ph === 'closing') && pose === 'slide' && (A.dustT -= 1 / 60) <= 0) { A.dustT = 0.12; FXK.burst('dust', x - f * Math.sign(D.v || 1) * 0.12 * s, y, { n: 3, dir: -Math.sign(D.v) * f }); }
  const lost = ph === 'settled' && st && (st.outcome === 'anvil' || st.outcome === 'barrel') && !stopWon(st) && G.settle && G.settle.t > 1.2;
  // Zee 2026-11-04: "if a trade is going in our direction we're visibly happier and if its going in loss we're sad (dancing or sad)"
  let face, bob = 0, lean = D.tilt, mood = 0;
  if (ph === 'open' && rr.risk_usd > 0) {
    mood = (+rr.result_usd || 0) / rr.risk_usd;                 // -1 at the stop, 0 at break-even, > 0 ahead
    face = mood > 0.6 ? 'joy' : mood > 0.15 ? 'grin' : mood > 0.02 ? 'smug' : mood > -0.08 ? 'determined' : mood > -0.3 ? 'worried' : mood > -0.7 ? 'sad' : 'panic';
    const still = pose === 'idle' || pose === 'lean';
    if (mood > 0.15 && still) {                                // a little dance: hops, sway, arms up on the beat
      const beat = t * 3.2;
      bob = Math.abs(Math.sin(beat * Math.PI)) * 0.07 * s;
      lean = Math.sin(beat * Math.PI * 0.5) * 0.35;
      if (mood > 0.4 && Math.floor(beat) % 2 === 0) pose = 'cheer';
      if (Math.random() < 0.04) FXK.burst('sparks', x, y - 1.2 * s, { n: 2 });
    } else if (mood < -0.15 && still) {                        // shoulders down, a slow sigh
      bob = -Math.abs(Math.sin(t * 0.8)) * 0.02 * s; lean = -0.15;
    }
  }
  if (face && mood > 0.15) drawNotes(x, y - 1.25 * s - bob, s, t, f);
  const pts = art('drawRunner', ctx, x, y - lift + sink - bob, s, { outfit, pose, lean, facing: f, t, face,
    coin: { visible: coinVisible && !lost && !(A.fetch && A.fetch.t / A.fetch.dur < 0.4), glow: Math.max(0.8, value), tarnish: rr.tarnish || 0, half: !!rr.machete_done, spin: (t * 0.4) % 1, wooden: false },
    hat: outfit === 'tux' || (outfit === 'suit' && outfitBand(rr).hat), cane: pose === 'ride', alpha: 1, wooden: false, tint: null });
  keepPts(pts);
  drawHunterFace(pts, s, f);
  if (face && mood < -0.5) drawGloomCloud(x, y - 1.55 * s, s, t);
  if (coinVisible && !lost && ptsOK(pts, 'coinX') && !(A.fetch && A.fetch.t / A.fetch.dur < 0.4)) drawTreasure(pts.coinX, pts.coinY, Math.max(pts.coinR || 0, 0.12 * s), s, t);
  if (sink > 0) wcall('drawPitFront', ctx, L.view, pit, G.env, t);
  if (lift > 0 || (ph === 'closing' && A.balloon > 0)) {
    const gx = ptsOK(pts, 'gripX') ? pts.gripX : x, gy = ptsOK(pts, 'gripY') ? pts.gripY : y - lift - 1.05 * s;
    art('drawBalloon', ctx, gx, gy, s, { words: snap.settings.eject_words || '', inflate: clamp(A.balloon + (ph === 'settled' ? 1 : 0), 0, 1), t });
  }
  if (A.machete > 0.01) { const [cx, cy] = coinPos(); art('drawMachete', ctx, cx - f * 0.1 * s, cy - 0.15 * s, s, { swing: 1 - A.machete, t }); }
  // the coin hurled by the Banker
  if (A.coinArc && A.coinArc.t < A.coinArc.dur) {
    const k = A.coinArc.t / A.coinArc.dur, [bx, by] = A.coinArc.from, [cx, cy] = coinPos();
    const px = lerp(bx, cx, k), py = lerp(by, cy, k) - Math.sin(k * Math.PI) * 1.6 * s;
    art('drawCoin', ctx, px, py, 0.17 * s, { glow: 0.5, tarnish: 0, half: false, spin: (k * 3) % 1, t, wooden });
  }
}

function noteLabel(snap) { const r = riskOf(snap); return r < 1 ? money(r, r) : '$' + Math.round(r); }

function buyerXY(L) {
  const xn = D.tpX || 1;
  return [L.xToScreen(xn), L.gy(xn)];                           // his feet on the walking line at the target
}
function drawBuyerGroup(snap, L, rr, pv, t) {
  const robbed = !!L.mirror;                                  // selling: the mafia are the ones robbed (Zee 2026-11-04)
  const s = L.s, [x, y] = robbed ? [L.xToScreen(-0.04), L.gy(-0.04)] : buyerXY(L);
  const tag = rr ? rr.tag_text : SCR.tagText(snap, snap.settings.target);
  const champ = rr ? clamp(1 - (rr.haggles || 0) / (rr.haggle_max || 3), 0, 1) : 1;
  const lit = !!(MOD.art && typeof MOD.art.drawBuyerTag === 'function');   // the tag itself is redrawn in the lit layer (drawBuyerTagLit)
  // Zee 2026-11-04: the boss's sign shows, in green, the PROFIT waiting at the target (never the coin's value, never in red)
  const risk = riskOf(snap);
  let profitUsd = null;
  if (rr) { if (rr.tag_text && isFinite(rr.tp) && isFinite(rr.fill)) profitUsd = (rr.qty || snap.settings.coin_oz) * Math.abs(rr.tp - rr.fill) + (rr.banked_usd || 0); }
  else if (snap.settings) profitUsd = snap.settings.coin_oz * snap.settings.target;
  const profit = profitUsd == null ? '' : '+' + money(profitUsd, risk);
  const tgt = rr && isFinite(rr.target) ? rr.target : snap.settings.target, tlist = snap.settings.targets || [];
  let vi = tlist.findIndex((v) => Math.abs(v - tgt) < 1e-9); if (vi < 0) vi = 1;
  const vehicle = null;                                      // (no vehicles any more - Zee 2026-11-04)
  const won = G.phase === 'settled' && snap.settlement && snap.settlement.outcome === 'buyer';
  const reach = rr && isFinite(rr.x_tp) && D.x != null ? clamp((D.x - (rr.x_tp - 0.35)) / 0.35, 0, 1) : 0.25;   // the hands stretch as he nears
  const shotNow = (A.bankerMood === 'shot' && A.bankerT > 0) || G.phase === 'sending';
  const pts = drawHumanBuyer(ctx, x, y, s, { mood: robbed ? (shotNow ? 'shot' : 'shake_head') : buyerMood(), profit, t, facing: -1,
    groundAt: (px) => L.gy(L.xFromScreen(px)), reach, vehicle, drawVehicle, prizeTaken: won, robbed, alert: !!(A.shootout && A.shootout.side < 0) || (robbed && (G.phase === 'open' || G.phase === 'closing' || G.phase === 'sending')),
    injured: robbed && (G.phase === 'open' || G.phase === 'closing' || G.phase === 'sending' || G.phase === 'settled'), knocked: knockedCount(-1), knockProg: knockProgress(-1) });
  if (pts && pts.box) D.mafiaBox = { ...pts.box };
  if (pts && isFinite(pts.goonX)) D.goonPos = [pts.goonX, pts.goonY];
  if (pts && isFinite(pts.bossX)) D.bossPos = [pts.bossX, pts.bossY];
  if (false && won && D.x != null) {                          // (the vehicle prize is gone)
    const vx = L.xToScreen(D.x) - L.facing * 0.9 * s, vy = L.gy(D.x);
    drawVehicle(ctx, vehicle, vx, vy, s, { t, scale: vehicle === 'heli' ? 0.9 : 0.85, facing: L.facing, bow: true, shine: 1 });
    if (Math.random() < 0.2) FXK.burst('sparks', vx, vy - 0.5 * s, { n: 3 });
  }
  if (robbed && L.bank && L.bank.sign) D.buyerPts = { tagX: L.bank.sign.cx, tagY: L.bank.sign.cy, tagR: 0.8 * s, gunX: L.bank.banker.x, gunY: L.bank.banker.y };   // selling: haggle at the bank's sign; it pays from the window
  else if (ptsOK(pts, 'tagX')) D.buyerPts = { tagX: pts.tagX, tagY: pts.tagY, tagR: pts.tagR, gunX: pts.gunX, gunY: pts.gunY };
  D.buyerTag = lit && ptsOK(pts, 'holeX') ? { x: pts.holeX, y: pts.holeY, ang: pts.holeAng, f: pts.holeF, text: tag } : null;
  if (G.phase === 'settled' && snap.settlement && snap.settlement.outcome === 'buyer' && G.settle && G.settle.t < 2.2 && Math.random() < 0.25) {
    const gx = ptsOK(pts, 'gunX') ? pts.gunX : x, gy = ptsOK(pts, 'gunY') ? pts.gunY : y - 2.3 * s;
    FXK.burst('cash', gx, gy, { n: 2 });
  }
}

function drawHoldRing(L, t) {
  const h = G.hold; if (!h) return;
  const s = L.s;
  let pop = 0;
  if (h.fired) { pop = (performance.now() - (h.firedAt || 0)) / 1000; if (pop > 0.35) return; }   // a short pop, then the ring is gone
  let [px, py] = h.ring || [L.W / 2, L.H / 2];
  if (h.src !== 'drag' && !h.screen && L.roll) {                // world-space rings follow the camera roll
    const dx = (px - L.pivotX) * L.rollScale, dy = (py - L.pivotY) * L.rollScale, c = Math.cos(L.roll), sn = Math.sin(L.roll);
    px = L.pivotX + dx * c - dy * sn; py = L.pivotY + dx * sn + dy * c;
  }
  const frozen = net.frozen();
  ctx.save();
  if (pop > 0) { ctx.globalAlpha = 1 - pop / 0.35; }
  art('drawHoldRing', ctx, px, py, 0.36 * s * (1 + pop * 1.2), h.fired ? 1 : h.frac, { color: frozen ? P.sepia : HOLD_COLOR[h.action] || P.gold, label: HOLD_LABEL[h.action] || '' });
  ctx.restore();
}

// ---------------------------------------------------------------------------------------------------- settlement scene
function drawSettlement(snap, L, t, dt) {
  const S = G.settle, st = snap.settlement; if (!S || !st) return;
  const W = L.W, H = L.H;
  if (S.stage === 'react') { S.stage = 'desk'; S.deskT = 0.6; }   // Zee 2026-11-04: no fold, the receipt shows the result at once
  if (S.stage === 'react' && S.t > 2.6) {                     // (unused) capture the street and fold it like a map
    S.stage = 'fold'; S.foldT = 0; snd('fold');
    try {
      const cap = document.createElement('canvas'); cap.width = canvas.width; cap.height = canvas.height;
      cap.getContext('2d').drawImage(canvas, 0, 0); S.cap = cap;
    } catch (e) { S.cap = null; }
  }
  if (S.stage === 'fold') {
    G.settleL = SCR.settleLayout(L);
    SCR.drawSettleDesk(ctx, L, G.settleL, snap, G, t, -1);
    if (S.cap) SCR.drawFold(ctx, S.cap, clamp(S.foldT / 1.3, 0, 1), W, H, G.dpr, st);
    if (S.foldT > 1.3) { S.stage = 'desk'; S.deskT = 0; snd('thud'); }
  } else if (S.stage === 'desk') {
    G.settleL = SCR.settleLayout(L);
    SCR.drawSettleDesk(ctx, L, G.settleL, snap, G, t, S.deskT);
    if (!S.coinDone && S.deskT > 0.75) { S.coinDone = true; snd('coin'); setTimeout(() => snd('thud'), 120); }
    if (!S.shavingsDone && S.deskT > 1.0) {
      S.shavingsDone = true;
      const c = st.costs || {}, SL = G.settleL, n = ['spread_usd', 'slippage_usd', 'fee_usd', 'financing_usd'].filter((k) => c[k] > 0).length;
      for (let i = 0; i < n; i++) setTimeout(() => { FXK.burst('shavings', SL.receipt.x + SL.receipt.w * 0.5, SL.receipt.y + 20, { to: [SL.jar.x, SL.jar.y - 0.3 * L.s], n: 5 }); setTimeout(() => snd('ping'), 600); }, i * 260);
    }
    if (plainOn()) SCR.drawPlainRibbon(ctx, L, st.plain, clamp((S.deskT - 0.6) / 0.9, 0, 1), t);
  }
}

// ---------------------------------------------------------------------------------------------------- debug
function drawDebug(L) {
  const snap = G.snap, lines = [
    `phase ${G.phase}  mode ${snap.mode}  ${net.mode}  fps ${G.fps}  link ${net.linkAge().toFixed(2)}s  frozen ${net.frozen()}`,
    `x ${D.x == null ? '-' : D.x.toFixed(3)}  tilt ${D.tilt.toFixed(2)}  v ${D.v.toFixed(3)}  mirror ${D.mirror}  roll ${(D.roll / DEG).toFixed(1)}deg`,
    `hold ${G.hold ? G.hold.action + ' ' + G.hold.frac.toFixed(2) : '-'}  last ${G.last ? JSON.stringify(G.last).slice(0, 110) : '-'}`,
    `misses: ${[...MISSES.keys()].slice(0, 8).join(', ')}${MISSES.size > 8 ? ' +' + (MISSES.size - 8) : ''}`,
  ];
  ctx.save(); ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(8, L.H - 18 * lines.length - 14, Math.min(L.W - 16, 980), 18 * lines.length + 8);
  ctx.fillStyle = '#9f9'; ctx.font = '12px ' + FONT.sign; lines.forEach((l, i) => ctx.fillText(l, 14, L.H - 18 * lines.length + i * 18)); ctx.restore();
}

// ======================================================================================================== the loop
function resize() {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const w = Math.max(320, canvas.clientWidth || window.innerWidth), h = Math.max(240, canvas.clientHeight || window.innerHeight);
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
  G.W = w; G.H = h; G.dpr = dpr;
}
window.addEventListener('resize', resize);

function tickTimers(dt) {
  const d = dt;
  A.bellSwing = Math.max(0, A.bellSwing - d * 0.22);
  A.bellShock = Math.min(1, A.bellShock + d * 0.7);
  A.anvilBounce = Math.max(0, A.anvilBounce - d * 1.8);
  A.buyerT -= d; A.bankerT -= d;
  A.recoil = Math.max(0, A.recoil - d * 4);
  A.flinch = Math.max(0, (A.flinch || 0) - d * 5);
  { const hs = G.snap && hintState(G.snap); if (hs && hs.cracks && Math.random() < d * 2.5) FXK.shake(3, 0.3); }   // the ground shudders on a trap
  if (A.shootout) {
    const so = A.shootout; so.t += d; so.eflash = Math.max(0, so.eflash - d * 6);
    if (so.t >= so.next) { so.next = so.t + 0.9; A.recoil = 1; snd('gunshot', { vol: 1.0 }); const [gx, gy] = guardPos(); FXK.burst('sparks', gx, gy, { n: 6 }); FXK.burst('smoke', gx, gy, { n: 3 }); }
    if (so.t >= so.enemyNext) { so.enemyNext = so.t + 0.9 + Math.random() * 0.3; so.eflash = 1; A.flinch = 1; snd('gunshot', { vol: 0.6, pitch: 1.45 }); const [rx, ry] = runnerPos(); FXK.burst('dust', rx, ry, { n: 6 }); }
  }
  if (A.fetch) { A.fetch.t += d; if (A.fetch.t >= A.fetch.dur) A.fetch = null; }
  if (A.volley && performance.now() > A.volley.until) { const v = A.volley; A.volley = null; robBank(v.side, v.n); }
  if (A.dig) { A.dig.t += d; if (A.dig.t >= A.dig.dur + 0.7) A.dig = null; }
  A.lightning = Math.max(0, A.lightning - d * 2.5);
  A.machete = Math.max(0, A.machete - d * 1.4);
  A.tackle = Math.max(0, A.tackle - d * 0.8);
  A.noteBounce = Math.max(0, A.noteBounce - d * 1.5);
  A.shutterRattle = Math.max(0, A.shutterRattle - d * 1.6);
  A.needle = Math.max(0, A.needle - d * 0.6);
  A.pistons = Math.max(0, A.pistons - d);
  A.smoke = Math.max(0, A.smoke - d);
  A.ropeTug = Math.max(0, A.ropeTug - d * 1.5);
  if (A.coinArc) A.coinArc.t += d;
  if (A.rat) A.rat.t += d;
  for (const [k, v] of A.walls) A.walls.set(k, v + d);
  A.stakeFlash.forEach((f) => (f.t += d)); A.stakeFlash = A.stakeFlash.filter((f) => f.t < 1.2);
  if (A.refuse) { A.refuse.t += d; if (A.refuse.t > 2) A.refuse = null; }
  if (G.phase === 'closing' && G.snap && G.snap.round && G.pendings.eject !== undefined) A.balloon = Math.min(1, A.balloon + d * 1.2);
  if (G.settle) { G.settle.t += d; if (G.settle.stage === 'fold') G.settle.foldT += d; if (G.settle.stage === 'desk') G.settle.deskT += d; }
}

function onPhaseChange(from, to) {
  const snap = G.snap;
  if (to === 'settled' && !G.settle && snap.settlement) startSettle(snap.settlement.outcome);
  if (to !== 'settled') { if (G.settle && to === 'lobby') FXK.clear(); G.settle = null; }
  if (to === 'aiming') snd('whoosh');
  if (to === 'lobby' && from === 'aiming') snd('coin');
  if (to === 'open' && from === 'sending') { /* landing is handled by the fill event */ }
  if (to === 'open' && from !== 'sending' && from !== 'closing' && from) { /* joined mid-round: nothing to replay */ }
  if (to === 'lobby') { A.balloon = 0; A.rat = null; A.walls.clear(); }
  if (to === 'closing') { if (G.pendings.merchant !== undefined || (G.last && G.last.action === 'merchant')) A.tackle = 1; }
}

let lastNow = performance.now(), fpsAcc = 0, fpsN = 0, lastAmbience = 0, lastTetherSent = 0;
function frame(now) {
  requestAnimationFrame(frame);
  let dt = Math.min(0.05, Math.max(0, (now - lastNow) / 1000));
  lastNow = now; G.now = now; G.realDt = dt;
  fpsAcc += dt; fpsN++; if (fpsAcc > 1) { G.fps = Math.round(fpsN / fpsAcc); fpsAcc = 0; fpsN = 0; }
  resize();
  ctx.setTransform(G.dpr, 0, 0, G.dpr, 0, 0);
  const snap = net.snap;
  G.snap = snap;
  const ready = snap && (snap.quote || snap.phase !== 'lobby' || snap.round);
  if (!ready) {
    SCR.drawLoading(ctx, G.W, G.H, now / 1000, net.status);
    exposeDebug();
    return;
  }
  // time: bullet-time for the machete, a full stop during a freeze
  if (G.slowmo > 0) G.slowmo -= dt;
  const frozen = net.frozen();
  if (frozen && !D.frozenNow) { D.frozenNow = true; snd('needle', { up: true }); A.needle = 1; }
  if (!frozen && D.frozenNow) { D.frozenNow = false; D.wasFrozen = true; snd('needle_drop'); }
  G.timeScale = easeTo(G.timeScale, frozen ? 0 : G.slowmo > 0 ? 0.3 : 1, frozen ? 9 : 6, dt);
  const adt = dt * G.timeScale;
  G.t += adt;
  // phase transitions (the layout exists before any reaction needs it)
  if (!G.L) computeLayout();
  if (snap.phase !== G.phase) { G.prevPhase = G.phase; G.phase = snap.phase; if (!G.firstPhase) G.firstPhase = snap.phase; onPhaseChange(G.prevPhase, G.phase); }
  // events: drained once per frame
  computeLayout();
  for (const ev of net.takeEvents()) handleEv(ev);
  if (snap.round && snap.round.last_refusal && snap.round.last_refusal.t !== D.lastRefusalT) {
    if (D.lastRefusalT !== undefined) refusalFx(snap.round.last_refusal.action, snap.round.last_refusal.why);
    D.lastRefusalT = snap.round.last_refusal.t;
  }
  updateInterp(adt || (frozen ? 0 : dt));
  computeLayout();
  G.env = buildEnv();
  updateHold();
  tickTimers(adt);
  FXK.update(adt);
  if (now - lastAmbience > 1500) {
    lastAmbience = now; audioCall('setAmbience', G.env);
    const sh = snap.market && snap.market.shutters;
    if (sh && sh.down && G.phase === 'lobby') {
      if (sh.reason === 'jam' && Math.random() < 0.45) snd('cards');
      if (sh.reason === 'locked' && Math.random() < 0.3) snd('collector');
    }
  }
  if (now - lastTetherSent > 100) { lastTetherSent = now; audioCall('setTether', G.phase === 'open' ? (G.tension || 0) : 0); }
  try { drawFrame(adt); } catch (e) { reportError(e); }
  exposeDebug();
}
const ERRORS = [];
window.GG.ERRORS = ERRORS;
function reportError(e) {
  const m = String(e && e.stack || e).slice(0, 400);
  if (!ERRORS.includes(m)) { ERRORS.push(m); console.error('[main] frame error', m); }
  ctx.setTransform(G.dpr, 0, 0, G.dpr, 0, 0);
}
function exposeDebug() {
  const snap = G.snap;
  window.GG.debug = {
    phase: G.phase, mode: snap ? snap.mode : null, net: net.mode, status: net.status, frozen: net.frozen(), fps: G.fps,
    hold: G.hold ? { action: G.hold.action, frac: +G.hold.frac.toFixed(2), fired: G.hold.fired } : null,
    last: G.last, echoes: G.echoes.slice(-8), misses: Object.fromEntries(MISSES), errors: ERRORS.slice(-5),
    x: D.x, tilt: D.tilt, mirror: D.mirror, settle: G.settle ? { stage: G.settle.stage, t: +G.settle.t.toFixed(2) } : null,
    modules: { art: !!MOD.art, world: !!MOD.world, fx: !!MOD.fx, audio: !!MOD.audio, loaded: MOD.loaded }, sent: net.sentCount, keys: KEYLOG.slice(-8),
    sounds: SNDLOG.slice(-30), focus: document.activeElement === canvas, sign: G.snap && G.L ? roofSign().text : null,
  };
}

// keys reach the game without a first click where the browser allows it (pointerdown still focuses, as the fallback)
function focusGame() {
  try { canvas.focus({ preventScroll: true }); } catch (e) { /* */ }
  try { window.focus(); } catch (e) { /* */ }
}
focusGame();
window.addEventListener('load', focusGame);
document.addEventListener('visibilitychange', () => { if (!document.hidden && !SCR.Safety.isOpen()) focusGame(); });

SCR.init({ art, wcall, FXK, snd, net, G, D, A, money, fmtPrice, fmtMoney, riskOf, noteLabel, plainOn, togglePlain, doAck, toggleSound, focusGame });
resize();
loadModules().finally(() => { exposeDebug(); });
requestAnimationFrame(frame);

// a tiny read-only hook for the screenshot self-tests: which party handed over the last coin
try { window.__gg = { lastCoin: () => G.lastCoin || null, phase: () => G.phase }; } catch (e) { /* no window */ }
