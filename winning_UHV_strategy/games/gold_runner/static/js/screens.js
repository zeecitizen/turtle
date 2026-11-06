// screens.js - the rooms around the street (F-CORE): loading, the lobby desk, the settlement scene (the map fold, the coin onto the
// stack, the shavings into the jar, the receipt, Another round / Enough for today), jammed / locked / shutters dressing, the Alley, the
// REPLAY fallback banner, the Time Freeze needle, and the safety ledger (DOM). Everything here is a physical object: brass, paper, wood,
// enamel - never a floating UI label. main.js passes a kit with the guarded art calls; this file works with placeholders alone.

import { VEHICLES, VEHICLE_WIDTH, drawVehicle } from './vehicles.js';
import { drawJarRat } from './rats.js';
import { drawCamel, camelState, drawCamelSign } from './diamondart.js';   // Zee 2026-11-04: the camel of his camel humps
import { P, LINE, FONT, inkStroke, rgba, mix, lighten, darken, shade, glow, rivet, roundRect, rand, clamp, lerp, ease } from './palette.js';

const TAU = Math.PI * 2;
let K = null;                                    // the kit from main.js
export function init(kit) { K = kit; }
const art = (...a) => (K ? K.art(...a) : false);

// ------------------------------------------------------------------------------------------------ small drawing helpers
function brassPlate(c, x, y, w, h, s, base = P.brass) {
  roundRect(c, x, y, w, h, Math.min(h * 0.3, 0.12 * s));
  shade(c, x, y, w, h, base);
  inkStroke(c, s, LINE.inkThin); c.stroke();
  c.strokeStyle = rgba(P.goldHot, 0.55); c.lineWidth = Math.max(1, 0.012 * s);
  roundRect(c, x + 3, y + 3, w - 6, h - 6, Math.min(h * 0.25, 0.1 * s)); c.stroke();
  rivet(c, x + 0.08 * s, y + h / 2, s); rivet(c, x + w - 0.08 * s, y + h / 2, s);
}
function engraved(c, text, x, y, px, color = P.ink, font = FONT.deco, align = 'center', weight = 'bold') {
  c.font = `${weight} ${Math.round(px)}px ${font}`; c.textAlign = align; c.textBaseline = 'middle';
  c.fillStyle = rgba('#ffffff', 0.35); c.fillText(text, x + 1, y + 1);
  c.fillStyle = color; c.fillText(text, x, y);
}
function paperRect(c, x, y, w, h, s, tone = P.paper) {
  c.save();
  c.shadowColor = 'rgba(0,0,0,0.35)'; c.shadowBlur = 0.12 * s; c.shadowOffsetY = 0.04 * s;
  c.beginPath(); c.rect(x, y, w, h); c.fillStyle = tone; c.fill();
  c.restore();
  inkStroke(c, s, LINE.hair, P.inkSoft); c.beginPath(); c.rect(x, y, w, h); c.stroke();
}
function fitFont(c, text, maxW, px, font, weight = '') {
  let p = px;
  c.font = `${weight} ${Math.round(p)}px ${font}`;
  while (p > 8 && c.measureText(text).width > maxW) { p -= 1; c.font = `${weight} ${Math.round(p)}px ${font}`; }
  return p;
}
function tallyMoney(usd) { return K ? K.money(usd || 0, K.riskOf(K.G.snap)) : String(usd); }
export function tagText(snap, target) {
  if (!snap || !snap.settings) return '';
  const st = snap.settings;
  return '+' + K.money(st.coin_oz * target, st.risk_usd);          // Zee 2026-11-04: the profit at that target, in green
}

// ================================================================================================ loading
export function drawLoading(c, W, H, t, status) {
  c.save();
  const g = c.createRadialGradient(W / 2, H * 0.42, 10, W / 2, H * 0.42, Math.max(W, H) * 0.7);
  g.addColorStop(0, '#3d2b18'); g.addColorStop(1, '#0d0906');
  c.fillStyle = g; c.fillRect(0, 0, W, H);
  // a deco sunburst behind the coin
  c.translate(W / 2, H * 0.42);
  for (let i = 0; i < 24; i++) {
    c.rotate(TAU / 24);
    c.fillStyle = i % 2 ? 'rgba(255,204,51,0.05)' : 'rgba(255,204,51,0.09)';
    c.beginPath(); c.moveTo(0, 0); c.lineTo(Math.max(W, H), -40); c.lineTo(Math.max(W, H), 40); c.closePath(); c.fill();
  }
  c.setTransform(c.getTransform());
  c.restore();
  const s = Math.min((W * 95) / 1600, (H * 95) / 900);
  c.save();
  art('drawCoin', c, W / 2, H * 0.42, 0.9 * s, { glow: 0.6 + 0.2 * Math.sin(t * 3), tarnish: 0, half: false, spin: (t * 0.45) % 1, t, wooden: false });
  c.restore();
  c.save();
  engraved(c, 'GOLDEN GRAVITY', W / 2, H * 0.62, 0.62 * s, P.gold, FONT.deco);
  engraved(c, 'the $1 heist', W / 2, H * 0.62 + 0.55 * s, 0.3 * s, P.brassLight, FONT.deco, 'center', 'italic');
  const msg = !status || status === 'connecting' ? 'Ledger Street is waking up' + '.'.repeat(1 + (Math.floor(t * 2) % 3))
    : status === 'reconnecting' ? 'looking for the street' + '.'.repeat(1 + (Math.floor(t * 2) % 3))
    : status === 'live' || status === 'open' ? 'waiting for the first price' + '.'.repeat(1 + (Math.floor(t * 2) % 3)) : status;   // the link is up, the market is not yet: never print a bare "live" here
  c.font = 'italic ' + Math.round(0.22 * s) + 'px ' + FONT.deco; c.textAlign = 'center'; c.fillStyle = 'rgba(240,214,138,0.75)';
  c.fillText(msg, W / 2, H * 0.62 + 1.15 * s);
  c.restore();
}

// ================================================================================================ corners: the cog and the page corner
export function cornerLayout(L) {
  const s = L.s;
  return { cog: { x: 0.6 * s, y: 0.62 * s, r: 0.42 * s }, page: { x: L.W - 0.42 * s, y: 0.42 * s, r: 0.62 * s } };
}
function drawCog(c, x, y, r, t, hover) {
  c.save(); c.translate(x, y); c.rotate(t * 0.15 + (hover ? t * 1.2 : 0));
  c.beginPath();
  const n = 10;
  for (let i = 0; i < n * 2; i++) { const a = (i / (n * 2)) * TAU, rr = i % 2 ? r * 0.78 : r; c.lineTo(Math.cos(a) * rr, Math.sin(a) * rr); }
  c.closePath(); shade(c, -r, -r, 2 * r, 2 * r, P.brass); inkStroke(c, r * 2.5, LINE.inkThin); c.stroke();
  c.beginPath(); c.arc(0, 0, r * 0.34, 0, TAU); c.fillStyle = P.ironDark; c.fill(); c.stroke();
  c.restore();
}
export function drawCorners(c, L, snap, G, t) {
  const C = cornerLayout(L), s = L.s, p = G.pointer;
  const hovCog = Math.hypot(p.x - C.cog.x, p.y - C.cog.y) < C.cog.r;
  drawCog(c, C.cog.x, C.cog.y, C.cog.r * (hovCog ? 1.08 : 1), t, hovCog);
  if (G.phase === 'lobby' || G.phase === 'aiming') {
    const hov = Math.hypot(p.x - C.page.x, p.y - C.page.y) < C.page.r;
    c.save(); c.translate(L.W, 0); c.scale(1, -1);
    art('drawPageCorner', c, 0, 0, s * (hov ? 1.12 : 1), { t, hover: hov });
    c.restore();
  }
}

// ================================================================================================ the lobby desk
export function lobbyLayout(L, k = 1) {
  const W = L.W, H = L.H, s = L.s;
  const off = (1 - ease(clamp(k, 0, 1))) * H * 0.36;
  const top = H - 0.42 * s + off;                // the counter's top surface (Zee 2026-11-04: no bottom panel, the street gets the screen)
  const fy = top + 0.24 * s;                     // the front panel
  const LL = { k, off, top, fy, bottom: H + 4 };
  // on the counter, left to right: the purse, the jar, the day's counter, the token and the note | (the runner) | tags, radio, cabinet
  LL.stack = { x: W * 0.034, y: top + 0.04 * s };
  LL.jar = { x: W * 0.138, y: top + 0.06 * s };
  LL.counter = { x: W * 0.248, y: top - 0.42 * s };
  LL.token = { x: W * 0.322, y: top }; LL.note = { x: W * 0.388, y: top };
  LL.token.hit = { x: LL.token.x - 0.34 * s, y: LL.token.y - 0.5 * s, w: 0.68 * s, h: 0.7 * s };
  LL.note.hit = { x: LL.note.x - 0.5 * s, y: LL.note.y - 0.5 * s, w: 1.0 * s, h: 0.7 * s };
  // Zee 2026-11-04: the targets are a row of vehicles standing on the counter (skate -> bike -> car -> jeep -> helicopter), no numbers
  LL.rack = { x: W * 0.5, y: top, w: W * 0.29 };
  const n = 0, tw = LL.rack.w / 5;                           // Zee 2026-11-04: no vehicles - the target is always the closest one
  LL.tags = [];
  for (let i = 0; i < n; i++) {
    const x = LL.rack.x + tw * (i + 0.5), y = top + 0.02 * s;
    LL.tags.push({ i, x, y, w: tw, h: 1.0 * s, hit: { x: x - tw / 2, y: top - 1.0 * s, w: tw, h: 1.05 * s } });
  }
  LL.radio = { x: W * 0.812, y: top + 0.05 * s }; LL.radio.hit = { x: LL.radio.x, y: LL.radio.y - 0.32 * s, r: 0.5 * s };
  LL.cabinet = { x: W * 0.918, y: top + 0.05 * s }; LL.cabinet.hit = { x: LL.cabinet.x - 0.55 * s, y: LL.cabinet.y - 1.5 * s, w: 1.1 * s, h: 1.5 * s };
  // the front panel: the huge badge | the tally slate | the trophy niche
  const ph = Math.max(0.5 * s, H - fy);
  LL.badge = { x: W * 0.148, y: fy + ph * 0.5, w: Math.min(W * 0.25, 4.2 * s), h: Math.min(ph * 0.66, 1.05 * s) };
  LL.slate = { x: W * 0.292, y: fy + ph * 0.1, w: W * 0.508, h: ph * 0.8 };
  LL.niche = { x: W * 0.815, y: fy + ph * 0.1, w: W * 0.17, h: ph * 0.8 };
  LL.shelf = { x: LL.niche.x + LL.niche.w / 2, y: LL.niche.y + LL.niche.h * 0.86 };
  // the runner stands at the door on the street behind the counter
  const xn = K && K.D.x != null ? K.D.x : 0.45, rx = L.xToScreen(xn), ry = L.gy(xn), f = L.facing;
  LL.pocket = { x: rx + f * 0.06 * s, y: ry - 0.42 * s };
  LL.hand = { x: rx + f * 0.32 * s, y: ry - 0.62 * s, r: 0.32 * s };
  return LL;
}

function drawDeskBody(c, L, LL, t, tone = '#5a2e1a') {
  const W = L.W, H = L.H, s = L.s, top = LL.top;
  c.save();
  const sg = c.createLinearGradient(0, top - 0.5 * s, 0, top);                  // the counter's shadow on the street
  sg.addColorStop(0, 'rgba(0,0,0,0)'); sg.addColorStop(1, 'rgba(0,0,0,0.35)');
  c.fillStyle = sg; c.fillRect(0, top - 0.5 * s, W, 0.5 * s);
  c.beginPath(); c.rect(-10, top, W + 20, 0.2 * s);                                // polished mahogany top
  const tg = c.createLinearGradient(0, top, 0, top + 0.2 * s);
  tg.addColorStop(0, lighten(tone, 0.3)); tg.addColorStop(1, tone); c.fillStyle = tg; c.fill();
  c.strokeStyle = rgba(darken(tone, 0.4), 0.35); c.lineWidth = 1;
  for (let i = 0; i < 9; i++) { const y = top + 0.03 * s + i * 0.018 * s; c.beginPath(); c.moveTo(0, y); for (let x = 0; x <= W; x += 40) c.lineTo(x, y + Math.sin(x * 0.01 + i) * 1.5); c.stroke(); }
  c.fillStyle = P.brass; c.fillRect(-10, top + 0.18 * s, W + 20, 0.06 * s);        // brass rail
  c.fillStyle = P.goldHot; c.fillRect(-10, top + 0.185 * s, W + 20, 0.012 * s);
  const fy = LL.fy;
  const fg = c.createLinearGradient(0, fy, 0, H);
  fg.addColorStop(0, darken(tone, 0.15)); fg.addColorStop(1, darken(tone, 0.55));
  c.fillStyle = fg; c.fillRect(-10, fy, W + 20, H - fy + 10);
  // framed sections with a deco fan behind the badge and the niche
  const frame = (x, y, w, h, fan) => {
    c.save();
    c.strokeStyle = rgba(P.brass, 0.6); c.lineWidth = Math.max(1, 0.025 * s); roundRect(c, x, y, w, h, 0.08 * s); c.stroke();
    c.strokeStyle = rgba('#000000', 0.4); roundRect(c, x + 2, y + 2, w, h, 0.08 * s); c.stroke();
    if (fan) {
      c.beginPath(); roundRect(c, x, y, w, h, 0.08 * s); c.clip();
      c.strokeStyle = rgba(P.brass, 0.14); c.lineWidth = 1;
      for (let a = 0; a <= 16; a++) { const an = Math.PI + (a / 16) * Math.PI; c.beginPath(); c.moveTo(x + w / 2, y + h); c.lineTo(x + w / 2 + Math.cos(an) * w, y + h + Math.sin(an) * w); c.stroke(); }
    }
    c.restore();
  };
  const ph = H - fy;
  if (false && ph > 0.4 * s) {
    frame(W * 0.012, fy + ph * 0.08, W * 0.27, ph * 0.84, true);
    if (LL.niche) frame(LL.niche.x, LL.niche.y, LL.niche.w, LL.niche.h, true);
  }
  for (let i = 0; i <= 12; i++) rivet(c, (i / 12) * W, fy + 0.06 * s, s);
  c.restore();
}

// --- tally icons (no trading words: suns, weather, an hourglass, a token, a note, a balloon, the twin) ---------------------
function icon(c, kind, x, y, r) {
  c.save(); c.translate(x, y); inkStroke(c, r * 4, LINE.inkThin);
  const sun = (h, col) => { c.fillStyle = col; c.beginPath(); c.arc(0, r * 0.55 - h * r, r * 0.42, 0, TAU); c.fill(); c.stroke(); c.strokeStyle = P.inkSoft; c.beginPath(); c.moveTo(-r, r * 0.55); c.lineTo(r, r * 0.55); c.stroke(); };
  switch (kind) {
    case 'asia': c.save(); c.beginPath(); c.rect(-r, -r, 2 * r, r * 1.55); c.clip(); sun(0.1, '#f08a5d'); c.restore(); break;
    case 'london': sun(1.0, P.gold); break;
    case 'newyork': sun(0.5, '#ff9a3c'); break;
    case 'dead': c.fillStyle = '#c9d2ff'; c.beginPath(); c.arc(0, 0, r * 0.5, 0.6, TAU - 0.6 + 0.0); c.arc(r * 0.2, -r * 0.05, r * 0.4, TAU - 0.9, 0.9, true); c.closePath(); c.fill(); c.stroke(); break;
    case 'calm': c.strokeStyle = P.emeraldDark; c.lineWidth = Math.max(1.5, r * 0.15); c.beginPath(); c.moveTo(-r * 0.8, 0); c.bezierCurveTo(-r * 0.3, -r * 0.3, r * 0.3, r * 0.3, r * 0.8, 0); c.stroke(); break;
    case 'active': c.strokeStyle = '#c0613b'; c.lineWidth = Math.max(1.5, r * 0.15); for (let i = -1; i <= 1; i++) { c.beginPath(); c.moveTo(-r * 0.8, i * r * 0.35); c.quadraticCurveTo(0, i * r * 0.35 - r * 0.25, r * 0.8, i * r * 0.35); c.stroke(); } break;
    case 'storm': c.fillStyle = '#4a4560'; c.beginPath(); c.arc(-r * 0.3, -r * 0.1, r * 0.35, 0, TAU); c.arc(r * 0.25, -r * 0.2, r * 0.42, 0, TAU); c.fill(); c.fillStyle = P.neonPurple; c.beginPath(); c.moveTo(0, r * 0.1); c.lineTo(-r * 0.25, r * 0.55); c.lineTo(0, r * 0.45); c.lineTo(-r * 0.15, r * 0.9); c.lineTo(r * 0.25, r * 0.3); c.lineTo(0, r * 0.38); c.closePath(); c.fill(); break;
    case 'deadw': c.fillStyle = P.ash; for (let i = 0; i < 6; i++) c.fillRect(-r * 0.7 + rand(i) * r * 1.4, -r * 0.7 + rand(i + 3) * r * 1.4, r * 0.18, r * 0.18); break;
    case 'quick': c.strokeStyle = P.ink; c.lineWidth = Math.max(1.5, r * 0.14); c.beginPath(); c.arc(0, 0, r * 0.62, 0, TAU); c.stroke(); c.beginPath(); c.moveTo(0, 0); c.lineTo(r * 0.4, -r * 0.2); c.stroke(); for (let i = 0; i < 3; i++) { c.beginPath(); c.moveTo(-r * 0.95, -r * 0.3 + i * r * 0.3); c.lineTo(-r * 0.7, -r * 0.3 + i * r * 0.3); c.stroke(); } break;
    case 'patient': c.fillStyle = P.brass; c.beginPath(); c.moveTo(-r * 0.45, -r * 0.7); c.lineTo(r * 0.45, -r * 0.7); c.lineTo(-r * 0.45, r * 0.7); c.lineTo(r * 0.45, r * 0.7); c.closePath(); c.fill(); c.stroke(); c.fillStyle = P.gold; c.beginPath(); c.moveTo(-r * 0.2, r * 0.7); c.lineTo(0, r * 0.35); c.lineTo(r * 0.2, r * 0.7); c.fill(); break;
    case 'wooden': c.fillStyle = P.wood; c.beginPath(); c.arc(0, 0, r * 0.6, 0, TAU); c.fill(); c.stroke(); c.strokeStyle = darken(P.wood, 0.35); c.beginPath(); c.arc(0, 0, r * 0.38, 0, TAU); c.stroke(); break;
    case 'live': c.fillStyle = '#9fd3a8'; roundRect(c, -r * 0.8, -r * 0.42, r * 1.6, r * 0.84, r * 0.1); c.fill(); c.stroke(); c.fillStyle = P.emeraldDark; c.beginPath(); c.arc(0, 0, r * 0.22, 0, TAU); c.fill(); break;
    case 'ejected': c.fillStyle = P.crimson; c.beginPath(); c.ellipse(0, -r * 0.2, r * 0.45, r * 0.55, 0, 0, TAU); c.fill(); c.stroke(); c.beginPath(); c.moveTo(0, r * 0.35); c.lineTo(0, r * 0.9); c.stroke(); break;
    case 'twin': c.fillStyle = P.twinBrass; c.beginPath(); c.arc(0, 0, r * 0.55, 0, TAU); c.fill(); c.stroke(); c.fillStyle = P.cyan; c.fillRect(-r * 0.4, -r * 0.12, r * 0.8, r * 0.18); break;
    default: break;
  }
  c.restore();
}
const CHALK = '#f1ede2', CHALK_DIM = 'rgba(241,237,226,0.45)', CHALK_GREEN = '#a9f0b9', CHALK_PINK = '#ffb3bd', CHALK_GOLD = '#ffe08a';
function chalkText(c, txt, x, y, px, col = CHALK, weight = '', font = FONT.deco, align = 'center') {
  c.font = `${weight} ${Math.round(px)}px ${font}`; c.textAlign = align; c.textBaseline = 'middle';
  c.fillStyle = 'rgba(255,255,255,0.08)'; c.fillText(txt, x + 0.8, y + 0.8);
  c.fillStyle = col; c.fillText(txt, x, y);
}
function miniAnvil(c, x, y, r) {
  c.save(); c.translate(x, y); c.fillStyle = '#9aa0aa'; c.strokeStyle = P.ink; c.lineWidth = 1;
  c.beginPath(); c.moveTo(-r, -r * 0.4); c.lineTo(r * 0.9, -r * 0.4); c.lineTo(r * 1.2, -r * 0.2); c.lineTo(r * 0.4, 0); c.lineTo(r * 0.3, r * 0.4);
  c.lineTo(r * 0.6, r * 0.6); c.lineTo(-r * 0.6, r * 0.6); c.lineTo(-r * 0.3, r * 0.4); c.lineTo(-r * 0.4, 0); c.closePath(); c.fill(); c.stroke();
  c.restore();
}
// the honest scoreboard: tallies that never merge, chalked on a slate in the counter's front panel. Icons, counts, money - no jargon.
export function drawSlate(c, R, s, snap, t, kind) {
  const lob = (snap && snap.lobby) || {}, T = lob.tallies || {}, st = (snap && snap.settings) || {};
  c.save();
  // brass frame + slate
  c.save(); c.shadowColor = 'rgba(0,0,0,0.5)'; c.shadowBlur = 0.12 * s; c.shadowOffsetY = 0.04 * s;
  roundRect(c, R.x - 0.07 * s, R.y - 0.07 * s, R.w + 0.14 * s, R.h + 0.14 * s, 0.1 * s); shade(c, R.x, R.y, R.w, R.h, P.brass); c.restore();
  inkStroke(c, s, LINE.inkThin); roundRect(c, R.x - 0.07 * s, R.y - 0.07 * s, R.w + 0.14 * s, R.h + 0.14 * s, 0.1 * s); c.stroke();
  roundRect(c, R.x, R.y, R.w, R.h, 0.05 * s);
  const sg = c.createLinearGradient(R.x, R.y, R.x + R.w * 0.4, R.y + R.h);
  sg.addColorStop(0, '#2c3a34'); sg.addColorStop(1, '#1a2421'); c.fillStyle = sg; c.fill();
  c.save(); c.clip();
  c.globalAlpha = 0.07; c.fillStyle = '#ffffff';                                 // old chalk smudges
  for (let i = 0; i < 9; i++) { c.beginPath(); c.ellipse(R.x + rand(i * 3.1) * R.w, R.y + rand(i * 7.7) * R.h, (0.4 + rand(i) * 0.8) * s, 0.1 * s, rand(i + 4) - 0.5, 0, TAU); c.fill(); }
  c.restore();
  for (const [dx, dy] of [[0.1, 0.1], [R.w - 0.1 * s, 0.1], [0.1, R.h - 0.1 * s], [R.w - 0.1 * s, R.h - 0.1 * s]]) rivet(c, R.x + (dx < 1 ? dx * s : dx), R.y + (dy < 1 ? dy * s : dy), s);
  // groups. When the engine keeps the Alley's own breakdown (tallies.wooden_by_session, wooden_by_weather, wooden_by_patience,
  // wooden_ejected, wooden_twin), the slate shows the breakdown of the coin in hand: WOODEN for the token, the real rounds for the note.
  const hasWood = !!T.wooden_by_session, useWood = hasWood && kind === 'wooden';
  const pick = (k) => (useWood ? T['wooden_' + k] : T[k]) || {};
  const bs = pick('by_session'), bw = pick('by_weather'), bp = pick('by_patience'), ej = pick('ejected'), tw = useWood ? T.wooden_twin : T.twin;
  const twinShown = !!(st.twin_unlocked || (tw && tw.n) || useWood);
  // REQUIREMENTS 9 / 11: the Alley's wooden rounds are labelled WOODEN everywhere and never merge with real ones. The client cannot split
  // them (it never computes a tally), so it reads the engine's shape: when the breakdowns count more rounds than there are real ones,
  // wooden rounds are inside them and those groups are chalked 'wood + real'; when they hold only real rounds they are chalked 'real'.
  const liveN = (T.live && T.live.n) || 0, woodN = (T.wooden && T.wooden.n) || 0;
  const sumN = (blk) => (blk ? Object.values(blk).reduce((a, v) => a + ((v && v.n) || 0), 0) : 0);
  const mixed = woodN > 0 && !hasWood && Math.max(sumN(bs), sumN(bw)) > liveN;
  const mixTag = useWood ? 'WOODEN' : !woodN ? '' : mixed ? 'wood + real' : 'real only';
  const groups = [
    { head: 'BY THE SUN', mix: true, cells: [['asia', bs.asia, 'dawn'], ['london', bs.london, 'noon'], ['newyork', bs.newyork, 'evening'], ['dead', bs.dead, 'night']] },
    { head: 'BY THE WEATHER', mix: true, cells: [['calm', bw.calm, 'calm'], ['active', bw.active, 'windy'], ['storm', bw.storm, 'storm'], ['deadw', bw.dead, 'ash']] },
    { head: 'BY PATIENCE', mix: true, cells: [['quick', bp.quick, '< 30 s'], ['patient', bp.patient, 'waited']] },
    { head: 'COINS', cells: [['wooden', T.wooden, 'WOODEN'], ['live', T.live, 'real']] },
    { head: 'LET GO', mix: true, cells: [['ejected', ej, 'balloon'], ['would', ej, 'the anvil']] },
    { head: 'TWIN', mix: true, cells: [['twin', tw, twinShown ? 'invited' : 'locked']] },
  ];
  const ncell = groups.reduce((a, g) => a + g.cells.length, 0);
  const pad = 0.12 * s, cw = (R.w - pad * 2) / ncell;
  const headY = R.y + R.h * (mixTag ? 0.11 : 0.13), tagY = R.y + R.h * 0.215;
  const iconY = R.y + R.h * (mixTag ? 0.39 : 0.36), numY = R.y + R.h * 0.62, netY = R.y + R.h * 0.8, capY = R.y + R.h * 0.93;
  const r = Math.min(cw * 0.26, R.h * (mixTag ? 0.11 : 0.13));
  let x = R.x + pad;
  groups.forEach((g, gi) => {
    const gw = cw * g.cells.length;
    chalkText(c, g.head, x + gw / 2, headY, Math.min(R.h * 0.1, 0.15 * s), CHALK_GOLD, 'bold', FONT.sign);
    if (g.mix && mixTag) {                                   // which coins this group counts, chalked under its head
      const px = Math.min(R.h * 0.075, 0.11 * s, (gw * 0.9) / (mixTag.length * 0.55));
      chalkText(c, mixTag, x + gw / 2, tagY, px, useWood ? '#e0b273' : mixed ? CHALK_PINK : CHALK_DIM, 'italic bold', FONT.deco);
    }
    if (gi > 0) { c.strokeStyle = CHALK_DIM; c.lineWidth = 1.2; c.setLineDash([3, 4]); c.beginPath(); c.moveTo(x, R.y + R.h * 0.08); c.lineTo(x, R.y + R.h * 0.92); c.stroke(); c.setLineDash([]); }
    g.cells.forEach(([kind, tal, cap], i) => {
      const cx = x + cw * (i + 0.5);
      const n = (tal && tal.n) || 0, wins = (tal && tal.wins) || 0;
      if (kind === 'would') {
        miniAnvil(c, cx, iconY, r * 0.75);
        const wv = (tal && tal.would_have_usd) || 0;
        // only rounds whose counterfactual has finished count: while the anvil is still being watched the cell says so, never 0.00
        const wn = tal && tal.would_have_n != null ? tal.would_have_n : n;
        chalkText(c, wn ? 'would' : n ? '…' : '–', cx, numY, Math.min(R.h * 0.12, 0.17 * s), CHALK_DIM, 'italic');
        if (wn) chalkText(c, (wv > 0 ? '+' : '') + tallyMoney(wv), cx, netY, Math.min(R.h * 0.11, 0.15 * s), wv >= 0 ? CHALK_GREEN : CHALK_PINK, 'bold');
      } else if (kind === 'twin' && !twinShown) {
        c.save(); c.globalAlpha = 0.5; icon(c, 'twin', cx, iconY, r); c.restore();
        const left = Math.max(0, 50 - ((snap.lobby && snap.lobby.live_rounds_total) || 0));
        chalkText(c, left + ' to go', cx, numY, Math.min(R.h * 0.1, 0.14 * s), CHALK_DIM, 'italic');
      } else {
        icon(c, kind, cx, iconY, r);
        chalkText(c, n ? `${wins}/${n}` : '–', cx, numY, Math.min(R.h * 0.14, 0.2 * s), n ? CHALK : CHALK_DIM, 'bold');
        if (n) { const nt = (tal && tal.net_usd) || 0; chalkText(c, (nt > 0 ? '+' : '') + tallyMoney(nt), cx, netY, Math.min(R.h * 0.11, 0.15 * s), nt >= 0 ? CHALK_GREEN : CHALK_PINK, 'bold'); }
      }
      chalkText(c, cap, cx, capY, Math.min(R.h * 0.085, 0.12 * s), CHALK_DIM, 'italic');
    });
    x += gw;
  });
  c.restore();
}

function drawTag(c, x, y, w, h, s, text, selected, t, i) {
  const sw = Math.sin(t * 1.6 + i * 1.3) * 0.06 + (selected ? Math.sin(t * 4) * 0.03 : 0);
  c.save(); c.translate(x, y - 0.42 * s); c.rotate(sw);
  c.strokeStyle = P.inkSoft; c.lineWidth = 1; c.beginPath(); c.moveTo(0, 0); c.lineTo(0, 0.28 * s); c.stroke();
  c.translate(0, 0.28 * s);
  if (selected) glow(c, 0, h / 2, w * 0.9, P.gold, 0.55);
  c.beginPath(); c.moveTo(-w / 2 + 0.06 * s, 0); c.lineTo(w / 2, 0); c.lineTo(w / 2, h); c.lineTo(-w / 2, h); c.lineTo(-w / 2, 0.08 * s); c.closePath();
  c.fillStyle = selected ? '#fff6d8' : P.paper; c.fill(); inkStroke(c, s, LINE.inkThin); c.stroke();
  if (selected) { c.strokeStyle = P.goldDeep; c.lineWidth = Math.max(2, 0.03 * s); c.stroke(); }
  c.fillStyle = P.ironDark; c.beginPath(); c.arc(-w / 2 + 0.1 * s, 0.1 * s, 0.025 * s, 0, TAU); c.fill();
  const px = fitFont(c, text, w * 0.8, 0.19 * s, FONT.deco, 'bold');
  c.fillStyle = selected ? '#0f7a3a' : '#1f8a4a'; c.textAlign = 'center'; c.textBaseline = 'middle';
  c.font = `bold ${Math.round(px)}px ${FONT.deco}`; c.fillText(text, 0.03 * s, h / 2 + 1);
  c.restore();
}

export function drawLobby(c, L, LL, snap, G, t) {
  const s = L.s, st = snap.settings || {}, lim = snap.limits || {}, lob = snap.lobby || {};
  drawDeskBody(c, L, LL, t);
  c.save();
  drawPurseAndJar(c, LL, s, snap, t);                        // (the day's rounds / lost counter is not drawn: Zee 2026-11-04)
  // (the wooden token, the note, their plates and 'sign the ledger' are gone - Zee 2026-11-04: confusing. The coin is picked for him.)
  const drag = G.drag && G.drag.item, p = G.pointer;
  // ---- the vehicles on the counter: choose the round's target (1-5). The bigger the ambition, the bigger the ride the boss hands over.
  (st.targets || []).forEach((tg, i) => {
    const T = LL.tags[i]; if (!T) return;
    T.target = tg;
    const kind = VEHICLES[Math.min(i, VEHICLES.length - 1)], sel = Math.abs(tg - st.target) < 1e-9;
    const hov = p.x > T.hit.x && p.x < T.hit.x + T.hit.w && p.y > T.hit.y && p.y < T.hit.y + T.hit.h;
    const sc = Math.min(1, (T.w * 0.86) / ((VEHICLE_WIDTH[kind] || 1) * s)) * (sel ? 1.08 : 0.9);
    const lift = (hov ? 0.06 * s : 0) + (sel ? Math.abs(Math.sin(t * 3)) * 0.04 * s : 0);
    if (sel) {                                                   // a little gold pedestal under the chosen one
      c.save(); roundRect(c, T.x - T.w * 0.42, T.y - 0.06 * s, T.w * 0.84, 0.08 * s, 0.03 * s); shade(c, T.x - T.w * 0.42, T.y - 0.06 * s, T.w * 0.84, 0.08 * s, P.gold); inkStroke(c, s, LINE.hair); c.stroke(); c.restore();
    }
    c.save(); if (!sel && !hov) c.globalAlpha = 0.75;
    drawVehicle(c, kind, T.x, T.y - (sel ? 0.06 * s : 0) - lift, s, { t, scale: sc, shine: sel ? 1 : hov ? 0.4 : 0 });
    c.restore();
  });
  // ---- the radio (the calendar's storms) - click: sound on/off
  const nx = nextNews(snap);
  art('drawRadio', c, LL.radio.x, LL.radio.y, s, { on: !!st.sound, crackle: nx && nx.soon ? 0.8 : 0.15, t, text: null });
  if (nx && false) {                                  // Zee 2026-11-04: no news text, visuals only (storms still show as weather)
    c.save(); c.translate(LL.radio.x - 0.25 * s, LL.radio.y - 1.0 * s); c.rotate(-0.03);
    const px = fitFont(c, nx.text, 2.4 * s, nx.cloud ? 0.18 * s : 0.15 * s, FONT.deco, 'italic');
    c.font = `italic ${Math.round(px)}px ${FONT.deco}`;
    const wv = c.measureText(nx.text).width, iw = nx.cloud ? 0.42 * s : 0;
    paperRect(c, -(wv + iw) / 2 - 0.12 * s, -0.17 * s, wv + iw + 0.24 * s, 0.34 * s, s, nx.soon ? '#ffe2d6' : '#f4ecd2');
    if (nx.cloud) icon(c, 'storm', -(wv + iw) / 2 + iw * 0.45, -0.02 * s, 0.17 * s);   // a storm on the calendar
    c.fillStyle = nx.soon ? '#a4232b' : P.ink; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(nx.text, iw / 2, 0);
    c.restore();
  }
  // ---- the Buyer's cabinet and the brass Twin (invite: click or I)
  art('drawCabinet', c, LL.cabinet.x, LL.cabinet.y, s, { coins: (lob.cabinet || []).length, t });
  const twinOk = G.ui.kind === 'wooden' || st.twin_unlocked;
  if (!st.twin_invited) {
    c.save(); c.globalAlpha = twinOk ? 0.95 : 0.4;
    art('drawTwin', c, LL.cabinet.x, LL.cabinet.y - 0.14 * s, s * 0.6, { pose: 'idle', lean: 0, facing: -L.facing, t, alpha: 1 });
    c.restore();
  }
  if (!twinOk) {
    drawPadlock(c, LL.cabinet.x + 0.32 * s, LL.cabinet.y - 0.55 * s, 0.16 * s, s);
  } else {
    const H0 = LL.cabinet.hit, hov = p.x > H0.x && p.x < H0.x + H0.w && p.y > H0.y && p.y < H0.y + H0.h;
    if (hov && !st.twin_invited) { c.save(); glow(c, LL.cabinet.x, LL.cabinet.y - 0.6 * s, 0.8 * s, P.twinBrass, 0.35); c.restore(); }
  }
  // ---- the front panel: the huge badge, the honest slate, the trophy niche
  // the front panel (badge, slate, trophy niche) is not drawn: Zee 2026-11-04 "we dont need the whole panel at the bottom"
  // ---- the dragged token / note follows the hand; the pocket glows
  if (drag && drag !== 'anvil') {
    c.save(); glow(c, LL.pocket.x, LL.pocket.y, 0.65 * s, P.gold, 0.35 + 0.15 * Math.sin(t * 8)); c.restore();
    if (drag === 'wooden') art('drawCoin', c, p.x, p.y, 0.19 * s, { glow: 0.3, tarnish: 0, half: false, spin: (t * 0.8) % 1, t, wooden: true });
    else art('drawNote', c, p.x, p.y, s * 0.85, { label: K.noteLabel(snap), t, angle: Math.sin(t * 6) * 0.08 });
  }
  c.restore();
}
function slotOutline(c, kind, x, y, s) {
  c.save(); c.strokeStyle = rgba(P.paper, 0.35); c.setLineDash([4, 4]); c.lineWidth = 1.5;
  if (kind === 'coin') { c.beginPath(); c.arc(x, y, 0.18 * s, 0, TAU); c.stroke(); }
  else c.strokeRect(x - 0.33 * s, y - 0.16 * s, 0.66 * s, 0.32 * s);
  c.restore();
}
// Zee 2026-11-04: two binoculars beside the jar - the left lens shows the 5-minute trend, the right one the 15-minute trend: a little hill
// tilted the way the street would tilt (rising price = downhill toward the mafia on the right), a gold coin rolling down it.
function drawTrendGlasses(c, x, y, s, snap, t) {
  const m = snap.market || {};
  const one = (cx, tr, label) => {
    const r = 0.2 * s, known = tr != null && isFinite(tr), k = known ? clamp(+tr, -1, 1) : 0;
    c.save();
    // the binocular body: two barrels and a brass bridge with the timeframe engraved on it
    for (const dx of [-0.13 * s, 0.13 * s]) { roundRect(c, cx + dx - r * 1.05, y - r * 2.25, r * 2.1, r * 2.3, r * 0.45); c.fillStyle = '#1d1d22'; c.fill(); c.strokeStyle = '#000'; c.lineWidth = Math.max(1, 0.012 * s); c.stroke(); }
    roundRect(c, cx - 0.17 * s, y - r * 1.05, 0.34 * s, r * 0.75, r * 0.18); c.fillStyle = '#e2b34a'; c.fill(); c.strokeStyle = '#5a3a1e'; c.lineWidth = Math.max(1, 0.012 * s); c.stroke();
    c.fillStyle = '#2a1608'; c.font = `bold ${Math.round(0.15 * s)}px ${FONT.sign}`; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(label + 'm', cx, y - r * 0.67);   // the timeframe, readable
    // the big lens: the view of the trend
    const lx = cx, ly = y - r * 2.55;
    c.beginPath(); c.arc(lx, ly, r * 1.25, 0, TAU); c.fillStyle = '#c99a3a'; c.fill(); c.stroke();
    c.save(); c.beginPath(); c.arc(lx, ly, r * 1.07, 0, TAU); c.clip();
    const sky = c.createLinearGradient(0, ly - r, 0, ly + r); sky.addColorStop(0, '#7cc4f0'); sky.addColorStop(1, '#d8f0ff'); c.fillStyle = sky; c.fillRect(lx - r * 1.2, ly - r * 1.2, r * 2.4, r * 2.4);
    const a = k * 0.5, tn = Math.tan(a), gy = (px) => ly + r * 0.15 + (px - lx) * tn;
    c.beginPath(); c.moveTo(lx - r * 1.2, gy(lx - r * 1.2)); c.lineTo(lx + r * 1.2, gy(lx + r * 1.2)); c.lineTo(lx + r * 1.2, ly + r * 1.3); c.lineTo(lx - r * 1.2, ly + r * 1.3); c.closePath();
    c.fillStyle = '#6cc04a'; c.fill(); c.strokeStyle = '#3f8a2e'; c.lineWidth = Math.max(1, 0.012 * s); c.stroke();
    if (known && Math.abs(k) > 0.06) {                          // a gold coin rolling downhill, faster on a steeper trend
      const dir = Math.sign(k), u = (t * (0.35 + Math.abs(k) * 0.6)) % 1, px = lx - dir * r * 0.85 + dir * u * r * 1.7, cr = r * 0.2;
      const py = gy(px) - cr;
      c.fillStyle = '#ffcf3f'; c.beginPath(); c.arc(px, py, cr, 0, TAU); c.fill(); c.strokeStyle = '#a8741c'; c.lineWidth = Math.max(1, 0.01 * s); c.stroke();
      c.strokeStyle = '#a8741c'; c.beginPath(); c.moveTo(px, py); c.lineTo(px + Math.cos(u * 12 * dir) * cr * 0.8, py + Math.sin(u * 12 * dir) * cr * 0.8); c.stroke();
    } else if (known) { c.fillStyle = '#ffcf3f'; c.beginPath(); c.arc(lx, gy(lx) - r * 0.2, r * 0.2, 0, TAU); c.fill(); }   // flat: the coin just sits there
    else { c.fillStyle = 'rgba(40,40,60,0.35)'; c.fillRect(lx - r * 1.2, ly - r * 1.2, r * 2.4, r * 2.4); }                  // not enough history yet: fogged
    c.fillStyle = 'rgba(255,255,255,0.35)'; c.beginPath(); c.ellipse(lx - r * 0.45, ly - r * 0.5, r * 0.3, r * 0.15, -0.6, 0, TAU); c.fill();   // glass glint
    c.restore();
    c.restore();
  };
  one(x, m.trend5, '5');
  one(x + 0.72 * s, m.trend15, '15');
  // Zee 2026-11-04: beside the two trends, the camel of his camel humps (diamond.py) walks in place on the shelf
  const dia = (typeof window !== 'undefined' && window.__ggDia) || m.diamond || {};
  drawCamel(c, x + 1.72 * s, y + 0.02 * s, s * 0.78, t, camelState(dia, t));
  drawCamelSign(c, x + 1.72 * s, y - 0.55 * s, s * 0.9, t, dia);   // Zee 2026-11-05: the camel's reading in plain words
}
function purseUsd(snap, wooden) {                           // Zee 2026-11-04: the purse shows the capital after all the wins and losses
  const bal = snap.account ? +snap.account.balance || 0 : 25, tl = (snap.lobby && snap.lobby.tallies) || {};
  return wooden ? bal + (+((tl.wooden || {}).net_usd) || 0) : bal;
}
function drawPurseAndJar(c, LL, s, snap, t) {
  const lob = snap.lobby || {}, wooden = K.G.ui.kind === 'wooden';
  art('drawCoinStack', c, LL.stack.x, LL.stack.y, s, { usd: purseUsd(snap, wooden), t, noTag: true });   // the easel shows the purse
  purseEasel(c, LL.stack.x + 0.78 * s, LL.top, s, purseUsd(snap, wooden));
  const risk = K.riskOf(snap);
  drawJarRat(c, LL.jar.x, LL.jar.y, s, t, 'back');            // the white rat owns the cost jar
  art('drawJar', c, LL.jar.x, LL.jar.y, s, { fill: 1 - Math.exp(-(lob.jar_usd || 0) / (risk * 6)), t });
  drawJarRat(c, LL.jar.x, LL.jar.y, s, t, 'front');
  drawTrendGlasses(c, LL.jar.x + 1.25 * s, LL.top, s, snap, t);   // the 5- and 15-minute trends
  c.save(); c.translate(LL.jar.x + 0.3 * s, LL.jar.y - 0.2 * s); c.rotate(0.12);
  paperRect(c, -0.02 * s, -0.12 * s, 0.62 * s, 0.24 * s, s, '#f4ecd2');
  c.font = `italic bold ${Math.round(0.15 * s)}px ${FONT.deco}`; c.fillStyle = P.ink; c.textAlign = 'center'; c.textBaseline = 'middle';
  c.fillText(tallyMoney(lob.jar_usd || 0), 0.29 * s, 0);
  c.restore();
}
function purseEasel(c, x, y, s, usd) {                       // a brass easel plate beside the stack: the purse, to the cent
  const txt = '$' + Number(usd).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  c.save();
  c.strokeStyle = P.brassDark; c.lineWidth = Math.max(1, 0.025 * s);
  c.beginPath(); c.moveTo(x - 0.25 * s, y); c.lineTo(x - 0.15 * s, y - 0.3 * s); c.moveTo(x + 0.25 * s, y); c.lineTo(x + 0.15 * s, y - 0.3 * s); c.stroke();
  c.translate(x, y - 0.33 * s); c.rotate(-0.04);
  brassPlate(c, -0.5 * s, -0.17 * s, 1.0 * s, 0.32 * s, s);
  engraved(c, txt, 0, -0.01 * s, fitFont(c, txt, 0.76 * s, 0.2 * s, FONT.deco, 'bold'), P.ink);
  c.restore();
}
function drawNiche(c, LL, s, lob, t) {
  const N = LL.niche; if (!N) return;
  c.save();
  roundRect(c, N.x + 0.08 * s, N.y + 0.08 * s, N.w - 0.16 * s, N.h - 0.16 * s, 0.08 * s);
  const g = c.createLinearGradient(0, N.y, 0, N.y + N.h); g.addColorStop(0, '#1d0f08'); g.addColorStop(1, '#3a1d10'); c.fillStyle = g; c.fill();
  c.save(); c.clip(); glow(c, N.x + N.w / 2, N.y + 0.1 * s, N.w * 0.55, P.goldHot, 0.18); c.restore();
  art('drawTrophyShelf', c, LL.shelf.x, LL.shelf.y, s, { trophies: lob.trophies || [], t });
  c.fillStyle = 'rgba(200,230,255,0.07)'; c.beginPath(); c.moveTo(N.x + 0.1 * s, N.y + 0.1 * s); c.lineTo(N.x + N.w * 0.4, N.y + 0.1 * s); c.lineTo(N.x + N.w * 0.15, N.y + N.h - 0.1 * s); c.lineTo(N.x + 0.1 * s, N.y + N.h - 0.1 * s); c.fill();
  c.restore();
}

function drawPadlock(c, x, y, r, s) {
  c.save(); inkStroke(c, s, LINE.inkThin);
  c.strokeStyle = P.ironLight; c.lineWidth = r * 0.28; c.beginPath(); c.arc(x, y - r * 0.4, r * 0.55, Math.PI, TAU); c.stroke();
  c.strokeStyle = P.ink; c.lineWidth = 1; c.stroke();
  roundRect(c, x - r * 0.8, y - r * 0.4, r * 1.6, r * 1.3, r * 0.2); shade(c, x - r, y - r, 2 * r, 2 * r, P.brass); c.stroke();
  c.fillStyle = P.ink; c.beginPath(); c.arc(x, y + r * 0.15, r * 0.18, 0, TAU); c.fill();
  c.restore();
}

function drawChainedReason(c, x, y, s, lim, t, mode) {
  // a chain over the note and a small tag that says what it is waiting for
  c.save();
  c.strokeStyle = P.ironLight; c.lineWidth = 0.035 * s;
  for (let i = -3; i <= 3; i++) { c.beginPath(); c.ellipse(x + i * 0.12 * s, y + Math.sin(i) * 0.02 * s, 0.07 * s, 0.04 * s, 0.3, 0, TAU); c.stroke(); }
  drawPadlock(c, x + 0.42 * s, y + 0.06 * s, 0.11 * s, s);
  const why = lim.why_not_live;
  const text = why === 'alley' ? `${lim.alley_done || 0}/${lim.alley_needed || 5} wooden` + (lim.alley_eject_done ? '' : ' · eject 0/1') + (lim.alley_machete_needed && !lim.alley_machete_done ? ' · split 0/1' : '')
    : why === 'confirm' ? 'sign the ledger' : why === 'mode' ? (mode === 'replay' ? 'a replay: wooden only' : 'not on this street')
    : why === 'balance' ? 'purse too light' : why === 'shutters' ? 'shutters down' : 'not yet';
  c.translate(x, y - 0.5 * s); c.rotate(-0.05);
  c.font = `italic bold ${Math.round(0.13 * s)}px ${FONT.deco}`;
  const w = c.measureText(text).width + 0.2 * s;
  paperRect(c, -w / 2, -0.12 * s, w, 0.24 * s, s, '#fff4e0');
  c.fillStyle = '#7a1e24'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(text, 0, 0);
  c.restore();
}

function drawBadge(c, B, s, snap, kind) {
  const mode = snap.mode;
  const live = mode === 'live' && snap.settings.live_enabled && kind === 'live';
  const word = kind === 'wooden' ? 'WOODEN' : mode === 'live' ? 'LIVE' : mode === 'replay' ? 'REPLAY' : 'DEMO';
  const col = live || (mode === 'live' && kind === 'live') ? P.crimson : kind === 'wooden' ? P.wood : P.brass;
  const x = B.x, y = B.y, w = B.w, h = B.h;
  c.save();
  c.save(); c.shadowColor = 'rgba(0,0,0,0.5)'; c.shadowBlur = 0.15 * s; c.shadowOffsetY = 0.05 * s;
  roundRect(c, x - w / 2, y - h / 2, w, h, 0.22 * s); shade(c, x - w / 2, y - h / 2, w, h, col); c.restore();
  inkStroke(c, s); roundRect(c, x - w / 2, y - h / 2, w, h, 0.22 * s); c.stroke();
  c.strokeStyle = rgba(P.goldHot, 0.7); c.lineWidth = Math.max(1, 0.022 * s); roundRect(c, x - w / 2 + 6, y - h / 2 + 6, w - 12, h - 12, 0.17 * s); c.stroke();
  for (const dx of [-w / 2 + 0.16 * s, w / 2 - 0.16 * s]) for (const dy of [-h / 2 + 0.16 * s, h / 2 - 0.16 * s]) rivet(c, x + dx, y + dy, s);
  if (kind === 'wooden') {                                     // wood grain on the Alley's badge
    c.save(); roundRect(c, x - w / 2, y - h / 2, w, h, 0.22 * s); c.clip();
    c.strokeStyle = rgba(darken(P.wood, 0.5), 0.35); c.lineWidth = 1;
    for (let i = 0; i < 7; i++) { const yy = y - h / 2 + (i + 0.5) * (h / 7); c.beginPath(); c.moveTo(x - w / 2, yy); c.bezierCurveTo(x - w / 6, yy + 4, x + w / 6, yy - 4, x + w / 2, yy + 2); c.stroke(); }
    c.restore();
  }
  const spaced = word.split('').join(' ');
  const px = fitFont(c, spaced, w * 0.84, h * 0.62, FONT.deco, 'bold');
  c.font = `bold ${Math.round(px)}px ${FONT.deco}`; c.textAlign = 'center'; c.textBaseline = 'middle';
  c.fillStyle = rgba('#000000', 0.35); c.fillText(spaced, x + 2, y + 3);
  c.fillStyle = col === P.crimson ? '#fff0ee' : kind === 'wooden' ? '#2a1608' : P.ink; c.fillText(spaced, x, y + 1);
  c.restore();
}

function drawDayCounter(c, x, y, s, lim) {
  // a small split-flap stand on the counter: rounds today, coins lost today
  c.save();
  const w = 1.42 * s, h = 0.78 * s;
  c.beginPath(); c.moveTo(x - w * 0.42, y + h / 2 + 0.2 * s); c.lineTo(x - w * 0.3, y + h / 2); c.lineTo(x + w * 0.3, y + h / 2); c.lineTo(x + w * 0.42, y + h / 2 + 0.2 * s); c.closePath();
  shade(c, x - w / 2, y + h / 2, w, 0.2 * s, P.brassDark); inkStroke(c, s, LINE.inkThin); c.stroke();
  roundRect(c, x - w / 2, y - h / 2, w, h, 0.1 * s); shade(c, x - w / 2, y - h / 2, w, h, P.iron); c.stroke();
  const rows = [[`${lim.rounds_today || 0}/${lim.rounds_max || 30}`, 'rounds'], [`${Math.round(lim.loss_today_coins || 0)}/${lim.loss_max_coins || 10}`, 'lost']];
  rows.forEach(([v, label], i) => {
    const yy = y + (i - 0.5) * 0.34 * s;
    roundRect(c, x - w / 2 + 0.08 * s, yy - 0.13 * s, 0.72 * s, 0.26 * s, 0.04 * s); c.fillStyle = P.flap; c.fill();
    c.strokeStyle = P.flapLine; c.lineWidth = 1; c.beginPath(); c.moveTo(x - w / 2 + 0.08 * s, yy); c.lineTo(x - w / 2 + 0.8 * s, yy); c.stroke();
    c.font = `bold ${Math.round(0.17 * s)}px ${FONT.sign}`; c.fillStyle = P.goldHot; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(v, x - w / 2 + 0.44 * s, yy + 1);
    c.font = `italic ${Math.round(0.14 * s)}px ${FONT.deco}`; c.fillStyle = P.brassLight; c.textAlign = 'left'; c.fillText(label, x - w / 2 + 0.88 * s, yy + 1);
  });
  c.restore();
}

function nextNews(snap) {
  const m = snap.market || {}, now = snap.t;
  const n = (m.news || []).filter((e) => e.t > now - 60 * 15).sort((a, b) => a.t - b.t)[0];
  if (!n) return null;
  const d = n.t - now, mins = Math.round(Math.abs(d) / 60);
  const when = d < 0 ? `${mins}m ago` : mins >= 60 ? `in ${Math.floor(mins / 60)}h ${mins % 60}m` : `in ${mins}m`;
  // acceptance 12.9: no trading term on screen. The radio shows a storm cloud and the countdown; the event's name (a trading term such
  // as "US ISM Manufacturing PMI") only for a player who turned the plain-words line on.
  const plain = !!(K && K.plainOn && K.plainOn());
  return { text: plain ? `${n.title} · ${when}` : when, cloud: !plain, soon: Math.abs(d) < 15 * 60, high: n.impact === 'high' };
}

// ================================================================================================ the rest card ("Enough for today")
export function drawRest(c, L, snap, t) {
  const W = L.W, H = L.H, s = L.s;
  c.save();
  c.fillStyle = 'rgba(10,8,20,0.55)'; c.fillRect(0, 0, W, H);
  c.translate(W / 2, H * 0.38);
  c.strokeStyle = P.brassDark; c.lineWidth = 0.03 * s; c.beginPath(); c.moveTo(-0.9 * s, -1.3 * s); c.lineTo(0, -1.9 * s); c.lineTo(0.9 * s, -1.3 * s); c.stroke();
  c.rotate(Math.sin(t * 1.2) * 0.03);
  roundRect(c, -2.3 * s, -1.3 * s, 4.6 * s, 1.5 * s, 0.12 * s); shade(c, -2.3 * s, -1.3 * s, 4.6 * s, 1.5 * s, P.wood); inkStroke(c, s); c.stroke();
  engraved(c, 'gone home for today', 0, -0.75 * s, 0.42 * s, '#2a1608', FONT.deco, 'center', 'italic bold');
  engraved(c, 'the street will be here tomorrow  ·  click to come back', 0, -0.2 * s, 0.17 * s, '#3a1f0a', FONT.deco, 'center', 'italic');
  c.restore();
}

// ================================================================================================ settlement: the desk, the receipt
export function settleLayout(L) {
  const LL = lobbyLayout(L, 1), s = L.s, W = L.W, H = L.H;
  const SL = { ...LL };
  const rh = H * 0.37 + 0.1 * s;                                      // the receipt keeps its old height and stands on the counter
  SL.receipt = { x: W * 0.355, y: LL.top - rh + 0.1 * s, w: W * 0.25, h: rh };
  const ar = 0.78 * s, acx = W * 0.74, acy = LL.top - 1.15 * s;          // a round button (Zee 2026-11-04: circular, a cowboy on it)
  SL.again = { x: acx - ar, y: acy - ar, w: 2 * ar, h: 2 * ar, cx: acx, cy: acy, r: ar };
  SL.enough = { x: SL.again.x + SL.again.w + 0.35 * s, y: LL.top - 0.74 * s, w: 2.0 * s, h: 0.56 * s };
  return SL;
}

const OUTCOME_STAMP = { buyer: 'PAID', anvil: 'STOPPED', barrel: 'LIQUIDATED', merchant: 'SOLD', eject: 'LET GO', session: 'CLOSING BELL', kill: 'KILLED', outside: 'CLOSED ELSEWHERE' };
const OUTCOME_WORDS = { buyer: 'the boss paid', anvil: 'the anvil caught him', barrel: 'the ground gave way', merchant: 'sold to the Merchant', eject: 'the balloon lifted him', session: 'the Merchant insisted at the close', kill: 'the kill switch', outside: 'closed outside the game' };
// a stop that filled at or above break-even locked a gain in: it is stamped and worded as a win, never as the ordinary loss
const stopWon = (st) => !!st && (st.outcome === 'anvil' || st.outcome === 'barrel') && isFinite(st.result_usd) && st.result_usd >= 0;
function stampOf(st) {
  if (stopWon(st)) return { word: st.outcome === 'barrel' ? 'GAPPED' : 'LOCKED IN', col: '#1f7a4f' };
  if (st.outcome === 'merchant') return (+st.result_usd || 0) > 0 ? { word: 'SOLD', col: '#1f7a4f' } : { word: 'ROBBED', col: '#b3202a' };
  const word = OUTCOME_STAMP[st.outcome] || 'CLOSED';
  return { word, col: st.outcome === 'buyer' ? '#1f7a4f' : st.outcome === 'merchant' || st.outcome === 'eject' ? '#8a6a24' : '#b3202a' };
}
function wordsOf(st) {
  if (stopWon(st)) return st.outcome === 'barrel' ? 'the ground gave way, above his door' : 'the anvil locked in his gain';
  if (st.outcome === 'merchant') return (+st.result_usd || 0) > 0 ? 'the ice-cream girl bought it' : 'the thief snatched it';
  if (st.outcome === 'buyer' && st.side < 0) return 'the bank took the coin';
  return OUTCOME_WORDS[st.outcome] || st.outcome;
}

export function drawSettleDesk(c, L, SL, snap, G, t, k) {
  const s = L.s, W = L.W, st = snap.settlement; if (!st) return;
  drawDeskBody(c, L, SL, t);
  const risk = K.riskOf(snap);
  // ---- the stack (balance after) - the coin lands on it
  const bal = st.kind === 'wooden' ? purseUsd(snap, true) : st.balance_after != null ? st.balance_after : snap.account ? snap.account.balance : 0;
  art('drawCoinStack', c, SL.stack.x, SL.stack.y, s, { usd: bal, t, noTag: st.balance_after != null || !!snap.account });
  if (st.balance_after != null || snap.account) purseEasel(c, SL.stack.x + 0.78 * s, SL.top, s, bal);   // no account (a replay): no purse plate
  // ---- the jar
  const lob = snap.lobby || {};
  drawJarRat(c, SL.jar.x, SL.jar.y, s, t, 'back');
  art('drawJar', c, SL.jar.x, SL.jar.y, s, { fill: 1 - Math.exp(-(lob.jar_usd || 0) / (risk * 6)), t });
  drawJarRat(c, SL.jar.x, SL.jar.y, s, t, 'front');
  // ---- the coin (or its remains) arcs from the street onto the stack
  if (k >= 0 && k < 0.8) {
    const q = clamp(k / 0.8, 0, 1);
    const fx = W * 0.5, fy = L.H * 0.35, tx = SL.stack.x, ty = SL.stack.y - 0.5 * s;
    const px = lerp(fx, tx, q), py = lerp(fy, ty, q) - Math.sin(q * Math.PI) * 1.8 * s;
    const outcome = st.outcome;
    const lostStop = (outcome === 'anvil' || outcome === 'barrel') && !stopWon(st);
    art('drawCoin', c, px, py, 0.2 * s, { glow: outcome === 'buyer' || stopWon(st) ? 0.8 : 0.1, tarnish: lostStop ? 0.7 : 0, half: lostStop, spin: (q * 4) % 1, t, wooden: st.kind === 'wooden' });
  }
  // ---- the ticker machine and its receipt (the honest result)
  drawReceipt(c, SL.receipt, s, snap, st, t, k);
  // the day's counter stays honest on the front panel
  // ---- Another round: a round gold button with a cowboy on it (Zee 2026-11-04); "Enough for today" is hidden
  const appear = k < 0 ? 0 : clamp((k - 0.7) / 0.3, 0, 1);
  if (appear > 0) {
    const p = G.pointer, A = SL.again, hov = Math.hypot(p.x - A.cx, p.y - A.cy) < A.r;
    c.save(); c.globalAlpha = appear;
    drawCowboyButton(c, A.cx, A.cy, A.r * (hov ? 1.07 : 1 + 0.03 * Math.sin(t * 5)), t, hov, s);
    c.restore();
  }
}

function drawCowboyButton(c, x, y, r, t, hov, s) {
  c.save(); c.translate(x, y);
  glow(c, 0, 0, r * 1.5, P.gold, hov ? 0.5 : 0.28);
  // rope rim
  c.beginPath(); c.arc(0, 0, r, 0, TAU); c.fillStyle = '#c99a4a'; c.fill(); c.lineWidth = Math.max(2, r * 0.05); c.strokeStyle = '#2a1a10'; c.stroke();
  c.strokeStyle = '#8a6430'; c.lineWidth = Math.max(1, r * 0.03);
  for (let i = 0; i < 28; i++) { const a = (i / 28) * TAU; c.beginPath(); c.arc(Math.cos(a) * r * 0.93, Math.sin(a) * r * 0.93, r * 0.06, a + 0.6, a + 2.4); c.stroke(); }
  // a desert sunset disc
  c.save(); c.beginPath(); c.arc(0, 0, r * 0.84, 0, TAU); c.clip();
  const g = c.createLinearGradient(0, -r, 0, r); g.addColorStop(0, '#ffb347'); g.addColorStop(0.55, '#ff7a3d'); g.addColorStop(1, '#b8452a'); c.fillStyle = g; c.fillRect(-r, -r, 2 * r, 2 * r);
  c.fillStyle = 'rgba(255,240,180,0.85)'; c.beginPath(); c.arc(r * 0.35, r * 0.05, r * 0.28, 0, TAU); c.fill();
  c.fillStyle = '#7a3a22'; c.beginPath(); c.moveTo(-r, r * 0.55); c.lineTo(-r * 0.5, r * 0.3); c.lineTo(-r * 0.2, r * 0.5); c.lineTo(r * 0.3, r * 0.25); c.lineTo(r, r * 0.5); c.lineTo(r, r); c.lineTo(-r, r); c.closePath(); c.fill();
  // the cowboy: tipping his hat when hovered
  const tip = hov ? Math.sin(t * 10) * 0.15 - 0.15 : 0;
  c.save(); c.translate(-r * 0.05, r * 0.12);
  c.fillStyle = '#b3202a'; c.beginPath(); c.moveTo(-r * 0.3, r * 0.28); c.lineTo(r * 0.3, r * 0.28); c.lineTo(0, r * 0.55); c.closePath(); c.fill();     // bandana
  c.fillStyle = '#f0c4a0'; c.beginPath(); c.ellipse(0, 0, r * 0.3, r * 0.34, 0, 0, TAU); c.fill(); c.strokeStyle = '#2a1a10'; c.lineWidth = Math.max(1.5, r * 0.035); c.stroke();
  c.fillStyle = '#2a1a10'; c.beginPath(); c.arc(-r * 0.1, -r * 0.03, r * 0.035, 0, TAU); c.arc(r * 0.11, -r * 0.03, r * 0.035, 0, TAU); c.fill();
  if (hov) { c.strokeStyle = '#2a1a10'; c.beginPath(); c.moveTo(r * 0.06, -r * 0.03); c.lineTo(r * 0.16, -r * 0.03); c.stroke(); }                   // a wink
  c.fillStyle = '#5a3a1e'; c.beginPath(); c.moveTo(-r * 0.17, r * 0.1); c.quadraticCurveTo(0, r * 0.03, r * 0.17, r * 0.1); c.quadraticCurveTo(0, r * 0.17, -r * 0.17, r * 0.1); c.fill();   // moustache
  c.strokeStyle = '#2a1a10'; c.lineWidth = Math.max(1.5, r * 0.03); c.beginPath(); c.arc(0, r * 0.13, r * 0.11, 0.15 * Math.PI, 0.85 * Math.PI); c.stroke();   // grin
  c.save(); c.translate(0, -r * 0.2); c.rotate(tip);
  c.fillStyle = '#7b4a26'; c.beginPath(); c.ellipse(0, 0, r * 0.55, r * 0.11, 0, 0, TAU); c.fill(); c.strokeStyle = '#2a1a10'; c.lineWidth = Math.max(1.5, r * 0.03); c.stroke();   // brim
  c.beginPath(); c.moveTo(-r * 0.28, 0); c.quadraticCurveTo(-r * 0.3, -r * 0.42, -r * 0.08, -r * 0.36); c.quadraticCurveTo(0, -r * 0.3, r * 0.08, -r * 0.36); c.quadraticCurveTo(r * 0.3, -r * 0.42, r * 0.28, 0); c.closePath();
  c.fillStyle = '#8f5a2e'; c.fill(); c.stroke();
  c.fillStyle = '#3a2412'; c.fillRect(-r * 0.27, -r * 0.1, r * 0.54, r * 0.07);
  c.restore();
  c.restore();
  c.restore();
  // a short ribbon across the bottom: what the button does
  c.save(); c.translate(0, r * 0.72); c.rotate(-0.04);
  c.beginPath(); c.moveTo(-r * 0.75, -r * 0.13); c.lineTo(r * 0.75, -r * 0.13); c.lineTo(r * 0.65, 0); c.lineTo(r * 0.75, r * 0.13); c.lineTo(-r * 0.75, r * 0.13); c.lineTo(-r * 0.65, 0); c.closePath();
  c.fillStyle = '#b3202a'; c.fill(); c.strokeStyle = '#2a1a10'; c.lineWidth = Math.max(1.5, r * 0.03); c.stroke();
  c.fillStyle = '#fff3d6'; c.font = `bold ${Math.round(r * 0.17)}px ${FONT.deco}`; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('GO AGAIN!', 0, r * 0.01);
  c.restore();
  c.restore();
}

// the receipt's cost icons: a molasses drop for the pit, the rat, a brass toll token, a crescent moon for the night
function costIcon(c, kind, x, y, s, t) {
  if (kind === 'rat') { art('drawRat', c, x, y + 0.08 * s, s * 0.7, { phase: 'peek', t, facing: 1 }); return; }
  c.save(); c.translate(x, y); inkStroke(c, s, LINE.hair);
  const r = 0.085 * s;
  if (kind === 'pit') {                                   // a drop of molasses with a highlight
    c.beginPath(); c.moveTo(0, -r * 1.25); c.bezierCurveTo(r * 0.9, -r * 0.2, r * 0.95, r * 0.9, 0, r * 0.95); c.bezierCurveTo(-r * 0.95, r * 0.9, -r * 0.9, -r * 0.2, 0, -r * 1.25);
    c.fillStyle = P.molasses || '#3a1d0c'; c.fill(); c.stroke();
    c.fillStyle = 'rgba(255,220,160,0.6)'; c.beginPath(); c.ellipse(-r * 0.3, r * 0.15, r * 0.14, r * 0.26, -0.4, 0, TAU); c.fill();
  } else if (kind === 'toll') {                           // a brass toll token with a slot
    c.beginPath(); c.arc(0, 0, r, 0, TAU); shade(c, -r, -r, 2 * r, 2 * r, P.brass); c.stroke();
    c.fillStyle = P.ink; c.fillRect(-r * 0.12, -r * 0.55, r * 0.24, r * 1.1);
  } else if (kind === 'night') {                          // a crescent moon
    c.beginPath(); c.arc(0, 0, r, 0.35 * Math.PI, 1.65 * Math.PI, false); c.arc(r * 0.45, -r * 0.1, r * 0.78, 1.5 * Math.PI, 0.5 * Math.PI, true); c.closePath();
    c.fillStyle = '#f4e9b8'; c.fill(); c.stroke();
  }
  c.restore();
}
// Zee 2026-11-04: "this paper shouldn't be white -> a beautiful paper scroll with either an icecream or jail depending on who snatched us
// (pink girl on bike or the robber) and it should have funky fonts on cowboy theme". A parchment scroll unrolls between two wooden rollers.
const WEST = '"Rye", "Sancreek", "Playfair Display", Georgia, serif';
function scrollTitle(st) {
  const win = (+st.result_usd || 0) > 0;
  if (st.outcome === 'merchant') return win ? 'SWEET DEAL!' : 'ROBBED!';
  if (st.outcome === 'buyer') return 'PAYDAY!';
  if (st.outcome === 'anvil' || st.outcome === 'barrel') return win ? 'SAFE!' : 'JAILED!';
  if (st.outcome === 'eject') return 'FLEW OFF!';
  if (st.outcome === 'kill') return 'SHUT DOWN';
  return win ? 'YEEHAW!' : 'BUSTED!';
}
function scrollPicture(st) {
  const win = (+st.result_usd || 0) > 0;
  if (st.outcome === 'merchant') return win ? 'icecream' : 'jail';
  if (st.outcome === 'eject') return 'balloon';
  return win ? 'bag' : 'jail';
}
function drawIceCream(c, x, y, r, t) {
  c.save(); c.translate(x, y + Math.sin(t * 2) * r * 0.04);
  c.beginPath(); c.moveTo(-r * 0.42, -r * 0.1); c.lineTo(r * 0.42, -r * 0.1); c.lineTo(0, r * 1.05); c.closePath(); c.fillStyle = '#e0a458'; c.fill(); c.strokeStyle = '#6b3d18'; c.lineWidth = Math.max(1.5, r * 0.05); c.stroke();
  c.save(); c.clip(); c.strokeStyle = '#b97c35'; c.lineWidth = Math.max(1, r * 0.035);
  for (let i = -3; i <= 3; i++) { c.beginPath(); c.moveTo(i * r * 0.18 - r * 0.5, -r * 0.1); c.lineTo(i * r * 0.18 + r * 0.5, r * 1.0); c.stroke(); c.beginPath(); c.moveTo(i * r * 0.18 + r * 0.5, -r * 0.1); c.lineTo(i * r * 0.18 - r * 0.5, r * 1.0); c.stroke(); }
  c.restore();
  const scoop = (sx, sy, rr, col) => { c.beginPath(); c.arc(sx, sy, rr, 0, Math.PI * 2); c.fillStyle = col; c.fill(); c.strokeStyle = '#6b3d18'; c.stroke(); };
  scoop(-r * 0.2, -r * 0.3, r * 0.36, '#ffb3cf'); scoop(r * 0.22, -r * 0.32, r * 0.34, '#fff3d6'); scoop(0, -r * 0.7, r * 0.36, '#8a4b2a');
  c.fillStyle = '#d4183a'; c.beginPath(); c.arc(r * 0.05, -r * 1.08, r * 0.13, 0, Math.PI * 2); c.fill();
  c.strokeStyle = '#3a6b1e'; c.lineWidth = Math.max(1, r * 0.04); c.beginPath(); c.moveTo(r * 0.08, -r * 1.18); c.quadraticCurveTo(r * 0.2, -r * 1.35, r * 0.3, -r * 1.32); c.stroke();
  const sp = ['#7ad3ff', '#ffe066', '#9be37a', '#ff8fb3'];
  for (let i = 0; i < 8; i++) { c.fillStyle = sp[i % 4]; c.save(); c.translate(-r * 0.3 + (i % 4) * r * 0.2, -r * 0.55 - Math.floor(i / 4) * r * 0.3); c.rotate(i); c.fillRect(-r * 0.05, -r * 0.015, r * 0.1, r * 0.03); c.restore(); }
  c.restore();
}
function drawJail(c, x, y, w, h, t) {
  c.save(); c.translate(x, y);
  c.fillStyle = '#5a4a3a'; c.fillRect(-w / 2, -h / 2, w, h);                                   // the dark cell
  c.fillStyle = '#e8b892'; c.beginPath(); c.arc(0, -h * 0.05, h * 0.2, 0, Math.PI * 2); c.fill();   // a sad face behind the bars
  c.fillStyle = '#2a1a10'; c.beginPath(); c.arc(-h * 0.07, -h * 0.08, h * 0.025, 0, Math.PI * 2); c.arc(h * 0.07, -h * 0.08, h * 0.025, 0, Math.PI * 2); c.fill();
  c.strokeStyle = '#2a1a10'; c.lineWidth = Math.max(1.5, h * 0.025); c.beginPath(); c.arc(0, h * 0.06, h * 0.07, 1.15 * Math.PI, 1.85 * Math.PI); c.stroke();
  c.fillStyle = '#9fd8ff'; c.beginPath(); c.ellipse(h * 0.1, -h * 0.0 + ((t * 0.8) % 1) * h * 0.12, h * 0.02, h * 0.035, 0, 0, Math.PI * 2); c.fill();   // a tear
  c.fillStyle = '#7d848f'; c.strokeStyle = '#2a1a10'; c.lineWidth = Math.max(1, h * 0.012);
  for (let i = 0; i < 6; i++) { const bx = -w / 2 + (i + 0.5) * (w / 6); c.fillRect(bx - h * 0.03, -h / 2, h * 0.06, h); c.strokeRect(bx - h * 0.03, -h / 2, h * 0.06, h); }
  c.fillRect(-w / 2, -h * 0.18, w, h * 0.06); c.strokeRect(-w / 2, -h * 0.18, w, h * 0.06);
  c.strokeStyle = '#2a1a10'; c.lineWidth = Math.max(2, h * 0.03); c.strokeRect(-w / 2, -h / 2, w, h);
  c.restore();
}
function drawMoneyBag(c, x, y, r, t) {
  c.save(); c.translate(x, y + Math.sin(t * 2.4) * r * 0.04);
  c.beginPath(); c.moveTo(-r * 0.25, -r * 0.6); c.quadraticCurveTo(-r * 0.95, r * 0.0, -r * 0.6, r * 0.75); c.lineTo(r * 0.6, r * 0.75); c.quadraticCurveTo(r * 0.95, r * 0.0, r * 0.25, -r * 0.6); c.closePath();
  c.fillStyle = '#c9a15a'; c.fill(); c.strokeStyle = '#5a3a1e'; c.lineWidth = Math.max(1.5, r * 0.05); c.stroke();
  c.fillStyle = '#7a4a26'; c.fillRect(-r * 0.3, -r * 0.66, r * 0.6, r * 0.12);
  c.beginPath(); c.moveTo(-r * 0.2, -r * 0.66); c.lineTo(-r * 0.35, -r * 0.95); c.lineTo(0, -r * 0.8); c.lineTo(r * 0.35, -r * 0.95); c.lineTo(r * 0.2, -r * 0.66); c.closePath(); c.fillStyle = '#c9a15a'; c.fill(); c.stroke();
  c.fillStyle = '#2f6b2c'; c.font = `bold ${Math.round(r * 0.8)}px ${WEST}`; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('$', 0, r * 0.15);
  for (let i = 0; i < 3; i++) { const a = t * 2 + i * 2.1, sx = Math.cos(a) * r * 1.0, sy = Math.sin(a) * r * 0.5 - r * 0.2, k = r * 0.12 * (0.6 + 0.4 * Math.sin(t * 5 + i)); c.fillStyle = '#ffd84d'; c.beginPath(); c.moveTo(sx, sy - k); c.lineTo(sx + k * 0.25, sy); c.lineTo(sx, sy + k); c.lineTo(sx - k * 0.25, sy); c.closePath(); c.fill(); c.beginPath(); c.moveTo(sx - k, sy); c.lineTo(sx, sy + k * 0.25); c.lineTo(sx + k, sy); c.lineTo(sx, sy - k * 0.25); c.closePath(); c.fill(); }
  c.restore();
}
function drawBalloonPic(c, x, y, r, t) {
  c.save(); c.translate(x, y - Math.sin(t * 1.5) * r * 0.08);
  c.beginPath(); c.ellipse(0, -r * 0.2, r * 0.55, r * 0.68, 0, 0, Math.PI * 2); c.fillStyle = '#d4183a'; c.fill(); c.strokeStyle = '#5a1a14'; c.lineWidth = Math.max(1.5, r * 0.05); c.stroke();
  c.fillStyle = 'rgba(255,255,255,0.4)'; c.beginPath(); c.ellipse(-r * 0.2, -r * 0.45, r * 0.12, r * 0.2, -0.4, 0, Math.PI * 2); c.fill();
  c.strokeStyle = '#5a3a1e'; c.beginPath(); c.moveTo(0, r * 0.48); c.quadraticCurveTo(r * 0.15, r * 0.75, 0, r * 1.0); c.stroke();
  c.restore();
}

function drawReceipt(c, R, s, snap, st, t, k) {
  const risk = K.riskOf(snap);
  c.save();
  const rise = k < 0 ? 0 : ease(clamp(k / 0.9, 0, 1));
  const rollR = 0.11 * s, px = R.x + 0.1 * s, pw = R.w - 0.2 * s, top = R.y + rollR;
  const full = R.h - rollR * 2.2, ph = full * rise, bot = top + ph;
  // the parchment, unrolling downward
  if (ph > 4) {
    c.save();
    c.beginPath(); c.moveTo(px, top);
    for (let i = 0; i <= 12; i++) { const yy = top + ph * i / 12; c.lineTo(px + Math.sin(i * 2.3) * 0.02 * s, yy); }
    for (let i = 12; i >= 0; i--) { const yy = top + ph * i / 12; c.lineTo(px + pw + Math.sin(i * 1.7 + 1) * 0.02 * s, yy); }
    c.closePath();
    const g = c.createLinearGradient(px, 0, px + pw, 0); g.addColorStop(0, '#d9b97c'); g.addColorStop(0.12, '#f3dfb0'); g.addColorStop(0.5, '#f8e8c2'); g.addColorStop(0.88, '#f0d9a6'); g.addColorStop(1, '#cfa865');
    c.fillStyle = g; c.fill(); c.strokeStyle = '#8a5a2b'; c.lineWidth = Math.max(1.5, 0.02 * s); c.stroke();
    c.save(); c.clip();
    c.fillStyle = 'rgba(140,90,40,0.08)'; for (let i = 0; i < 5; i++) { c.beginPath(); c.arc(px + pw * (0.15 + 0.7 * ((i * 37) % 10) / 10), top + ph * (0.2 + 0.15 * i), 0.18 * s + i * 2, 0, TAU); c.fill(); }   // old stains
    const vg = c.createRadialGradient(px + pw / 2, top + ph / 2, Math.min(pw, ph) * 0.3, px + pw / 2, top + ph / 2, Math.max(pw, ph) * 0.75); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(110,60,20,0.28)');
    c.fillStyle = vg; c.fillRect(px - 10, top, pw + 20, ph);
    // the content (laid out for the fully unrolled scroll; the clip reveals it as it unrolls)
    const cx = px + pw / 2, win = (+st.result_usd || 0) > 0;
    const costs = st.costs || {};
    const items = [['the pit', costs.spread_usd, 'pit'], ['the rat', costs.slippage_usd, 'rat'], ['the toll', costs.fee_usd, 'toll'], ['the night', costs.financing_usd, 'night']].filter((x) => x[1] > 0);
    const notesN = (st.kind === 'wooden') + (st.twin_result_usd != null) + (st.would_have_usd != null);
    const need = (0.55 + 0.32 + 1.05 + 0.6 + 0.15 + items.length * 0.25 + 0.3 + notesN * 0.24) * s;
    const kk = clamp(full / need, 0.62, 1);
    let y = top + 0.42 * s * kk;
    const title = scrollTitle(st);
    c.textAlign = 'center'; c.textBaseline = 'middle';
    c.font = `${Math.round(fitFont(c, title, pw * 0.86, 0.46 * s * kk, WEST, ''))}px ${WEST}`;
    c.fillStyle = 'rgba(90,50,20,0.35)'; c.fillText(title, cx + 2, y + 3);
    c.fillStyle = win ? '#1f6b3a' : '#9e1b28'; c.fillText(title, cx, y);
    y += 0.34 * s * kk;
    c.font = `italic ${Math.round(0.16 * s * kk)}px "Playfair Display", Georgia, serif`; c.fillStyle = '#5a3a1e'; c.fillText(wordsOf(st), cx, y);
    y += 0.6 * s * kk;
    const pic = scrollPicture(st), pr = 0.4 * s * kk;
    if (pic === 'icecream') drawIceCream(c, cx, y + pr * 0.1, pr, t);
    else if (pic === 'jail') drawJail(c, cx, y, pw * 0.42, pr * 2.1, t);
    else if (pic === 'bag') drawMoneyBag(c, cx, y, pr, t);
    else drawBalloonPic(c, cx, y, pr, t);
    y += 0.95 * s * kk;
    const rt = String(st.result_text == null ? '' : st.result_text);
    const big = st.result_usd > 0 && rt[0] !== '+' ? '+' + rt : rt;
    c.font = `${Math.round(fitFont(c, big, pw * 0.82, 0.52 * s * kk, WEST, ''))}px ${WEST}`;
    c.fillStyle = 'rgba(90,50,20,0.3)'; c.fillText(big, cx + 2, y + 3);
    c.fillStyle = win ? '#1f7a3f' : '#a4232b'; c.fillText(big, cx, y);
    y += 0.38 * s * kk;
    // a rope divider, the costs, the time
    c.strokeStyle = '#8a5a2b'; c.lineWidth = Math.max(1, 0.012 * s); c.setLineDash([6, 4]); c.beginPath(); c.moveTo(px + 0.25 * s, y - 0.12 * s); c.lineTo(px + pw - 0.25 * s, y - 0.12 * s); c.stroke(); c.setLineDash([]);
    items.forEach(([name, usd, kind], i) => {
      const yy = y + i * 0.25 * s * kk;
      costIcon(c, kind, px + 0.38 * s, yy, s, t + i);
      c.font = `italic ${Math.round(0.14 * s)}px "Playfair Display", Georgia, serif`; c.fillStyle = '#3a2412'; c.textAlign = 'left'; c.fillText(name, px + 0.6 * s, yy);
      c.textAlign = 'right'; c.font = `${Math.round(0.14 * s)}px ${WEST}`; c.fillText('-' + K.money(usd, risk), px + pw - 0.25 * s, yy);
    });
    y += (items.length * 0.25 + 0.08) * s * kk;
    const mins = Math.floor((st.age_s || 0) / 60), secs = Math.round((st.age_s || 0) % 60);
    c.textAlign = 'center'; c.font = `italic ${Math.round(0.13 * s)}px "Playfair Display", Georgia, serif`; c.fillStyle = '#6b4526';
    c.fillText(`${mins ? mins + 'm ' : ''}${secs}s on the trail`, cx, y); y += 0.24 * s * kk;
    if (st.twin_result_usd != null) { c.fillText(`the Twin: ${(st.twin_result_usd > 0 ? '+' : '') + K.money(st.twin_result_usd, risk)}`, cx, y); y += 0.24 * s * kk; }
    if (st.would_have_usd != null) { c.fillText(`left alone, the anvil would have said ${(st.would_have_usd > 0 ? '+' : '') + K.money(st.would_have_usd, risk)}`, cx, y); y += 0.24 * s * kk; }
    if (st.kind === 'wooden') { c.fillText('wooden coin: no order was sent', cx, y); y += 0.24 * s * kk; }
    // the stamp, in the top corner
    if (k > 0.55) {
      if (!drawReceipt.stamped || drawReceipt.stamped !== st.id + st.outcome) { drawReceipt.stamped = st.id + st.outcome; K.snd('stamp'); }
      const sk = clamp((k - 0.55) / 0.2, 0, 1), sc = 1 + (1 - sk) * 1.5;
      const { word, col: colr } = stampOf(st);
      c.font = `${Math.round(0.17 * s)}px ${WEST}`; const ww = c.measureText(word).width + 0.2 * s;
      c.save(); c.translate(px + pw - ww * 0.42 - 0.08 * s, top + 0.95 * s * kk); c.rotate(0.22); c.scale(sc * 0.75, sc * 0.75); c.globalAlpha = sk * 0.8;
      c.strokeStyle = colr; c.lineWidth = 3; roundRect(c, -ww / 2, -0.16 * s, ww, 0.32 * s, 0.05 * s); c.stroke();
      c.fillStyle = colr; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(word, 0, 1);
      c.restore();
    }
    c.restore();
    c.restore();
  }
  // the two wooden rollers with brass knobs (the bottom one travels down as the scroll unrolls)
  const roller = (yy) => {
    const g2 = c.createLinearGradient(0, yy - rollR, 0, yy + rollR); g2.addColorStop(0, '#a8743f'); g2.addColorStop(0.5, '#7a4a22'); g2.addColorStop(1, '#4f2e15');
    roundRect(c, px - 0.08 * s, yy - rollR, pw + 0.16 * s, rollR * 2, rollR); c.fillStyle = g2; c.fill(); c.strokeStyle = '#2a1a10'; c.lineWidth = Math.max(1.5, 0.02 * s); c.stroke();
    for (const kx of [px - 0.12 * s, px + pw + 0.12 * s]) { c.beginPath(); c.arc(kx, yy, rollR * 1.15, 0, TAU); c.fillStyle = '#d9a53a'; c.fill(); c.stroke(); c.fillStyle = 'rgba(255,255,255,0.4)'; c.beginPath(); c.arc(kx - rollR * 0.3, yy - rollR * 0.3, rollR * 0.35, 0, TAU); c.fill(); }
  };
  roller(top);
  roller(Math.max(top + rollR * 2, bot));
  c.restore();
}

// ================================================================================================ the map fold
// The street folds like a map: the right half over the left, then the top down, then the little packet flies to the desk. The paper's
// back is a printed street map (aged paper, a deco border, the street grid, a compass rose, fold creases); it folds down onto the dark
// mahogany of the counter, never onto a half-drawn scene, and the packet lands with the outcome inked on it like a rubber stamp.
function mapBack(c, x, y, w, h) {
  if (!(w > 1 && h > 1)) return;
  const g = c.createLinearGradient(x, y, x + w, y + h);
  g.addColorStop(0, '#f1e4c2'); g.addColorStop(0.55, '#e4d0a0'); g.addColorStop(1, '#cbb07a');
  c.fillStyle = g; c.fillRect(x, y, w, h);
  c.save(); c.beginPath(); c.rect(x, y, w, h); c.clip();
  const m = Math.min(w, h);
  for (let i = 0; i < 16; i++) {                                   // foxing, the age spots of an old map
    c.fillStyle = 'rgba(140,96,40,' + (0.04 + 0.07 * rand(i * 3.3)).toFixed(3) + ')';
    c.beginPath(); c.arc(x + rand(i * 7.1) * w, y + rand(i * 2.7) * h, (0.01 + 0.035 * rand(i + 0.5)) * m, 0, TAU); c.fill();
  }
  const step = Math.max(12, m / 7);                                 // the printed street grid of the map's other side
  c.strokeStyle = 'rgba(122,90,18,0.16)'; c.lineWidth = 1;
  for (let gx = x + step * 0.6; gx < x + w; gx += step) { c.beginPath(); c.moveTo(gx, y); c.lineTo(gx + step * 0.15, y + h); c.stroke(); }
  for (let gy = y + step * 0.7; gy < y + h; gy += step) { c.beginPath(); c.moveTo(x, gy); c.lineTo(x + w, gy - step * 0.1); c.stroke(); }
  c.strokeStyle = 'rgba(122,90,18,0.28)'; c.lineWidth = 2;          // one avenue across it
  c.beginPath(); c.moveTo(x, y + h * 0.62); c.bezierCurveTo(x + w * 0.3, y + h * 0.5, x + w * 0.6, y + h * 0.75, x + w, y + h * 0.58); c.stroke();
  const inset = Math.max(4, m * 0.03);                              // the deco border with stepped corners
  c.strokeStyle = 'rgba(110,78,20,0.6)'; c.lineWidth = 2; c.strokeRect(x + inset, y + inset, w - inset * 2, h - inset * 2);
  c.lineWidth = 1; c.strokeRect(x + inset * 1.7, y + inset * 1.7, w - inset * 3.4, h - inset * 3.4);
  for (const [cx, cy] of [[x + inset, y + inset], [x + w - inset, y + inset], [x + inset, y + h - inset], [x + w - inset, y + h - inset]]) {
    c.fillStyle = 'rgba(110,78,20,0.55)'; c.fillRect(cx - inset * 0.6, cy - inset * 0.6, inset * 1.2, inset * 1.2);
  }
  const rr = m * 0.16, rx = x + w - inset * 2.5 - rr, ry = y + h - inset * 2.5 - rr;   // a compass rose
  c.save(); c.translate(rx, ry); c.strokeStyle = 'rgba(110,78,20,0.55)'; c.lineWidth = 1;
  c.beginPath(); c.arc(0, 0, rr, 0, TAU); c.stroke(); c.beginPath(); c.arc(0, 0, rr * 0.7, 0, TAU); c.stroke();
  for (let i = 0; i < 4; i++) {
    c.rotate(Math.PI / 2); c.beginPath(); c.moveTo(0, -rr * 1.05); c.lineTo(rr * 0.16, 0); c.lineTo(-rr * 0.16, 0); c.closePath();
    c.fillStyle = i % 2 ? 'rgba(164,35,43,0.55)' : 'rgba(110,78,20,0.6)'; c.fill();
  }
  c.restore();
  c.strokeStyle = 'rgba(255,255,255,0.35)'; c.lineWidth = 1.5;     // the creases where it has been folded before
  c.beginPath(); c.moveTo(x + w / 2, y); c.lineTo(x + w / 2, y + h); c.moveTo(x, y + h / 2); c.lineTo(x + w, y + h / 2); c.stroke();
  c.strokeStyle = 'rgba(90,60,20,0.2)'; c.lineWidth = 1;
  c.beginPath(); c.moveTo(x + w / 2 + 1.5, y); c.lineTo(x + w / 2 + 1.5, y + h); c.moveTo(x, y + h / 2 + 1.5); c.lineTo(x + w, y + h / 2 + 1.5); c.stroke();
  c.restore();
}
function foldTable(c, W, H, a) {                                    // the dark mahogany the map is folded on, lit by the desk lamp
  if (a <= 0.003) return;
  c.save(); c.globalAlpha = a;
  const g = c.createRadialGradient(W * 0.45, H * 0.45, 10, W * 0.5, H * 0.5, Math.max(W, H) * 0.75);
  g.addColorStop(0, '#6a3b20'); g.addColorStop(0.55, '#3b1f10'); g.addColorStop(1, '#160b05');
  c.fillStyle = g; c.fillRect(0, 0, W, H);
  c.strokeStyle = 'rgba(20,8,2,0.35)'; c.lineWidth = 1;
  for (let i = 0; i < 26; i++) { const y = (i + 0.5) * H / 26; c.beginPath(); c.moveTo(0, y); for (let x = 0; x <= W; x += 60) c.lineTo(x, y + Math.sin(x * 0.006 + i * 1.7) * 4); c.stroke(); }
  c.restore();
}
export function drawFold(c, cap, p, W, H, dpr, st) {
  const half = W / 2;
  const back = (x, y, w, h) => mapBack(c, x, y, w, h);
  const src = (sx, sy, sw, sh, dx, dy, dw, dh) => c.drawImage(cap, sx * dpr, sy * dpr, sw * dpr, sh * dpr, dx, dy, dw, dh);
  c.save();
  foldTable(c, W, H, p < 0.8 ? 1 : 1 - ease((p - 0.8) / 0.2));     // the desk scene shows through only as the packet flies to it
  if (p < 0.45) {
    const q = p / 0.45, k = Math.cos(Math.PI * q);
    src(0, 0, half, H, 0, 0, half, H);                                     // the left half stays
    c.save(); c.translate(half, 0);
    if (k > 0) {
      c.scale(k, 1); src(half, 0, half, H, 0, 0, half, H);
      c.fillStyle = 'rgba(0,0,0,' + (0.45 * (1 - k)) + ')'; c.fillRect(0, 0, half, H);
    } else {
      c.fillStyle = 'rgba(0,0,0,' + (0.3 * (1 + k)) + ')'; c.fillRect(-half, 0, half, H);   // shadow on the left half
      c.scale(k, 1); back(0, 0, half, H);
    }
    c.restore();
  } else if (p < 0.8) {
    const q = (p - 0.45) / 0.35, k = Math.cos(Math.PI * q);
    back(0, 0, half, H / 2);
    c.save(); c.translate(0, H / 2);
    if (k > 0) { c.scale(1, k); back(0, 0, half, H / 2); c.fillStyle = 'rgba(0,0,0,' + (0.35 * (1 - k)) + ')'; c.fillRect(0, 0, half, H / 2); }
    else { c.scale(1, k); back(0, 0, half, H / 2); }
    c.restore();
  } else {
    const q = ease((p - 0.8) / 0.2);
    const w = lerp(half, W * 0.12, q), h = lerp(H / 2, H * 0.1, q);
    const x = lerp(0, W * 0.47, q), y = lerp(0, H * 0.62, q);
    c.globalAlpha = 1 - q * 0.6;
    c.translate(x + w / 2, y + h / 2); c.rotate(q * 0.25);
    c.save(); c.shadowColor = 'rgba(0,0,0,0.45)'; c.shadowBlur = 12; c.shadowOffsetY = 6; c.fillStyle = '#e4d0a0'; c.fillRect(-w / 2, -h / 2, w, h); c.restore();
    back(-w / 2, -h / 2, w, h);
    if (st) {                                                              // the outcome, inked on the packet like a rubber stamp
      const sp = stampOf(st), word = sp.word, col = sp.col;
      const px = Math.max(9, Math.min(h * 0.26, (w * 0.8) / Math.max(4, word.length * 0.62)));
      c.save(); c.rotate(-0.14);
      c.font = 'bold ' + Math.round(px) + 'px ' + FONT.deco; c.textAlign = 'center'; c.textBaseline = 'middle';
      const tw = c.measureText(word).width + px * 0.9, th = px * 1.5;
      c.globalAlpha *= 0.85; c.strokeStyle = col; c.lineWidth = Math.max(1.5, px * 0.12);
      roundRect(c, -tw / 2, -th / 2, tw, th, px * 0.25); c.stroke();
      c.lineWidth = Math.max(1, px * 0.05); roundRect(c, -tw / 2 + px * 0.18, -th / 2 + px * 0.18, tw - px * 0.36, th - px * 0.36, px * 0.18); c.stroke();
      c.fillStyle = col; c.fillText(word, 0, px * 0.05);
      c.restore();
    }
  }
  c.restore();
}

// ================================================================================================ the plain-words ribbon (L)
export function drawPlainRibbon(c, L, text, p, t) {
  if (!text || p <= 0) return;
  const s = L.s, b = L.bank;
  c.save();
  c.font = `italic ${Math.round(0.21 * s)}px ${FONT.deco}`;
  const full = c.measureText(text).width + 0.6 * s;
  const maxW = L.W * 0.62;
  const lines = [];
  if (full > maxW) {                                       // two lines on a wider ribbon
    const words = text.split(' '); let cur = '';
    for (const w of words) { const n = cur ? cur + ' ' + w : w; if (c.measureText(n).width > maxW - 0.6 * s && cur) { lines.push(cur); cur = w; } else cur = n; }
    if (cur) lines.push(cur);
  } else lines.push(text);
  const rw = Math.min(maxW, Math.max(...lines.map((l) => c.measureText(l).width)) + 0.7 * s) * ease(p);
  const rh = (0.36 + 0.28 * (lines.length - 1)) * s;
  const x0 = L.mirror ? b.sign.cx - b.sign.w / 2 - rw : b.sign.cx + b.sign.w / 2, y0 = b.sign.cy - rh / 2 + 0.25 * s;
  c.translate(x0, y0);
  const wave = (x) => Math.sin(x / (1.6 * s) + t * 1.5) * 0.06 * s;
  c.beginPath(); c.moveTo(0, wave(0));
  for (let x = 0; x <= rw; x += 8) c.lineTo(x, wave(x));
  c.lineTo(rw, rh + wave(rw)); c.lineTo(rw + 0.18 * s, rh / 2 + wave(rw)); c.lineTo(rw, wave(rw));
  for (let x = rw; x >= 0; x -= 8) c.lineTo(x, rh + wave(x));
  c.closePath();
  c.save(); c.shadowColor = 'rgba(0,0,0,0.4)'; c.shadowBlur = 0.12 * s; c.shadowOffsetY = 0.05 * s; c.fillStyle = '#fbf3dc'; c.fill(); c.restore();
  inkStroke(c, s, LINE.inkThin); c.stroke();
  c.save(); c.beginPath(); c.rect(0, -0.3 * s, rw, rh + 0.6 * s); c.clip();
  c.fillStyle = P.ink; c.textAlign = 'left'; c.textBaseline = 'middle';
  lines.forEach((l, i) => c.fillText(l, 0.3 * s, (0.18 + 0.28 * i) * s + wave(0.3 * s)));
  c.restore();
  c.restore();
}

// ================================================================================================ shutters, jam, locked, alley
export function drawShutterPlaque(c, L, sh, now, t, rattle) {
  const s = L.s, b = L.bank, x = b.x + (rattle ? Math.sin(t * 50) * rattle * 4 : 0), y = b.top + 2.3 * s;
  c.save();
  c.translate(x, y); c.rotate(Math.sin(t * 1.3) * 0.02);
  c.strokeStyle = P.ironLight; c.lineWidth = 0.02 * s; c.beginPath(); c.moveTo(-0.5 * s, -0.75 * s); c.lineTo(0, -1.05 * s); c.lineTo(0.5 * s, -0.75 * s); c.stroke();
  // an enamel plaque
  c.beginPath(); c.arc(0, 0, 0.75 * s, 0, TAU); c.fillStyle = '#f2ead5'; c.fill(); inkStroke(c, s); c.stroke();
  c.strokeStyle = P.crimson; c.lineWidth = 0.06 * s; c.beginPath(); c.arc(0, 0, 0.66 * s, 0, TAU); c.stroke();
  reasonIcon(c, sh.reason, 0, -0.08 * s, 0.42 * s, t);
  if (sh.until) {                                     // the same countdown the roof sign clacks (one clock, one format)
    const d = Math.max(0, sh.until - (now || 0)), hh = Math.floor(d / 3600), mm = Math.floor((d % 3600) / 60), ss = Math.floor(d % 60);
    const txt = hh > 0 ? `${hh}h${String(mm).padStart(2, '0')}` : `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
    c.font = `bold ${Math.round(0.17 * s)}px ${FONT.sign}`; c.fillStyle = P.ink; c.textAlign = 'center'; c.textBaseline = 'middle';
    c.fillText(txt, 0, 0.45 * s);
  }
  c.restore();
}
function reasonIcon(c, reason, x, y, r, t) {
  c.save(); c.translate(x, y); inkStroke(c, r * 3, LINE.inkThin);
  switch (reason) {
    case 'dead_hours': c.fillStyle = '#2a2f52'; c.beginPath(); c.arc(0, 0, r, 0, TAU); c.fill(); c.fillStyle = '#f4f0c8'; c.beginPath(); c.arc(-r * 0.15, 0, r * 0.62, 0, TAU); c.fill(); c.fillStyle = '#2a2f52'; c.beginPath(); c.arc(r * 0.12, -r * 0.12, r * 0.55, 0, TAU); c.fill();
      c.fillStyle = '#f4f0c8'; for (let i = 0; i < 4; i++) { c.beginPath(); c.arc(r * (0.25 + 0.15 * i), r * (0.35 - 0.3 * (i % 2)), r * 0.05, 0, TAU); c.fill(); } break;
    case 'news': c.fillStyle = '#4a4560'; c.beginPath(); c.arc(-r * 0.35, 0, r * 0.45, 0, TAU); c.arc(r * 0.3, -r * 0.15, r * 0.55, 0, TAU); c.arc(r * 0.1, r * 0.2, r * 0.4, 0, TAU); c.fill();
      c.fillStyle = P.neonPurple; c.beginPath(); c.moveTo(0, r * 0.2); c.lineTo(-r * 0.3, r * 0.75); c.lineTo(0, r * 0.62); c.lineTo(-r * 0.15, r * 1.1); c.lineTo(r * 0.3, r * 0.45); c.lineTo(0, r * 0.52); c.closePath(); c.fill(); break;
    case 'weekend': case 'market_closed': c.fillStyle = '#fff'; c.fillRect(-r * 0.75, -r * 0.65, r * 1.5, r * 1.4); c.strokeRect(-r * 0.75, -r * 0.65, r * 1.5, r * 1.4); c.fillStyle = P.crimson; c.fillRect(-r * 0.75, -r * 0.65, r * 1.5, r * 0.38);
      c.fillStyle = P.ink; c.font = `bold ${Math.round(r * 0.6)}px ${FONT.deco}`; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(reason === 'weekend' ? 'S S' : '✕', 0, r * 0.25); break;
    case 'no_feed': c.strokeStyle = P.ink; c.lineWidth = r * 0.14; c.beginPath(); c.moveTo(-r, -r * 0.1); c.quadraticCurveTo(-r * 0.4, -r * 0.4, -r * 0.12, 0); c.moveTo(r * 0.12, 0.05 * r); c.quadraticCurveTo(r * 0.4, r * 0.4, r, r * 0.1); c.stroke();
      c.strokeStyle = P.gold; c.lineWidth = r * 0.08; for (let i = 0; i < 3; i++) { c.beginPath(); c.moveTo(-r * 0.1, 0); c.lineTo(-r * 0.1 + Math.cos(i * 2) * r * 0.3, Math.sin(i * 2) * r * 0.3); c.stroke(); } break;
    case 'rounds_max': c.fillStyle = P.paper; roundRect(c, -r * 0.8, -r * 0.5, r * 1.6, r, r * 0.1); c.fill(); c.stroke(); c.fillStyle = P.ink; for (let i = 0; i < 10; i++) { c.beginPath(); c.arc(-r * 0.6 + (i % 5) * r * 0.3, -r * 0.2 + Math.floor(i / 5) * r * 0.4, r * 0.08, 0, TAU); c.fill(); } break;
    default: c.fillStyle = P.ironDark; c.beginPath(); c.arc(0, 0, r * 0.7, 0, TAU); c.fill(); break;
  }
  c.restore();
}
export function drawJamDressing(c, L, snap, t) {
  const s = L.s, b = L.bank, f = L.facing;
  c.save();
  // the playing cards fanned on the step
  for (let i = 0; i < 5; i++) {
    c.save(); c.translate(b.x + f * (0.75 + i * 0.12) * s, b.y - 0.06 * s); c.rotate((i - 2) * 0.22 + Math.sin(t + i) * 0.02);
    roundRect(c, -0.09 * s, -0.26 * s, 0.18 * s, 0.26 * s, 0.025 * s); c.fillStyle = '#fbf8f0'; c.fill(); inkStroke(c, s, LINE.hair); c.stroke();
    c.fillStyle = i % 2 ? P.crimson : P.ink; c.font = `bold ${Math.round(0.12 * s)}px ${FONT.deco}`; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(['♠', '♥', '♣', '♦', '♠'][i], 0, -0.13 * s);
    c.restore();
  }
  // a plank sign nailed over the door: three stops in a row
  c.translate(b.x, b.y - 1.55 * s); c.rotate(-0.06);
  roundRect(c, -1.0 * s, -0.2 * s, 2.0 * s, 0.4 * s, 0.05 * s); shade(c, -1.0 * s, -0.2 * s, 2.0 * s, 0.4 * s, P.wood); inkStroke(c, s); c.stroke();
  for (const dx of [-0.88, 0.88]) { c.fillStyle = P.ironLight; c.beginPath(); c.arc(dx * s, 0, 0.03 * s, 0, TAU); c.fill(); }
  engraved(c, 'door jammed', 0, 0, 0.2 * s, '#2a1608', FONT.deco, 'center', 'italic bold');
  c.restore();
}
export function drawLocked(c, L, snap, G, t) {
  const s = L.s, b = L.bank, f = L.facing;
  const k = clamp(((G.now || 0) / 1000) % 1000 / 1.5, 0, 1);
  c.save();
  // the chain across the facade, one link at a time
  const x0 = b.x - b.w / 2 + 0.15 * s, x1 = b.x + b.w / 2 - 0.15 * s, y0 = b.y - 1.9 * s;
  const n = 22;
  for (let i = 0; i < n; i++) {
    const u = i / (n - 1), x = lerp(x0, x1, u), y = y0 + Math.sin(u * Math.PI) * 0.35 * s;
    c.save(); c.translate(x, y); c.rotate(i % 2 ? 0 : Math.PI / 2 * 0.0);
    c.strokeStyle = P.ironLight; c.lineWidth = 0.035 * s; c.beginPath(); c.ellipse(0, 0, i % 2 ? 0.09 * s : 0.05 * s, i % 2 ? 0.05 * s : 0.08 * s, 0, 0, TAU); c.stroke();
    c.strokeStyle = P.ink; c.lineWidth = 1; c.stroke();
    c.restore();
  }
  drawPadlock(c, b.x, y0 + 0.5 * s, 0.26 * s, s);
  // "see you tomorrow" hanging from the chain
  c.save(); c.translate(b.x, y0 + 0.95 * s); c.rotate(Math.sin(t * 0.9) * 0.04);
  c.strokeStyle = P.ink; c.lineWidth = 1; c.beginPath(); c.moveTo(-0.6 * s, -0.35 * s); c.lineTo(0, -0.62 * s); c.lineTo(0.6 * s, -0.35 * s); c.stroke();
  roundRect(c, -1.15 * s, -0.35 * s, 2.3 * s, 0.6 * s, 0.08 * s); shade(c, -1.15 * s, -0.35 * s, 2.3 * s, 0.6 * s, '#efe6c8'); inkStroke(c, s); c.stroke();
  engraved(c, 'see you tomorrow', 0, -0.05 * s, fitFont(c, 'see you tomorrow', 2.0 * s, 0.27 * s, FONT.deco, 'italic bold'), '#3a2a6a', FONT.deco, 'center', 'italic bold');   // fits the plank
  c.restore();
  // the Debt Collector at the door: kind face, grey coat, the chain in his hand
  const cx = b.x + f * (b.w / 2 + 0.7 * s);
  art('drawCollector', c, cx, b.y, s, { t, chain: 1 });
  c.restore();
}
export function drawAlleySign(c, L, t, phase) {
  const s = L.s, b = L.bank, f = L.facing;
  const x = b.x + f * (b.w / 2 + 0.05 * s), y = b.top + 1.25 * s;
  c.save();
  c.strokeStyle = P.ironDark; c.lineWidth = 0.05 * s; c.beginPath(); c.moveTo(x - f * 0.05 * s, y); c.lineTo(x + f * 1.25 * s, y); c.stroke();
  c.translate(x + f * 0.65 * s, y); c.rotate(Math.sin(t * 1.1) * 0.06);
  c.strokeStyle = P.ink; c.lineWidth = 1.2; c.beginPath(); c.moveTo(-0.45 * s, 0); c.lineTo(-0.45 * s, 0.22 * s); c.moveTo(0.45 * s, 0); c.lineTo(0.45 * s, 0.22 * s); c.stroke();
  roundRect(c, -0.62 * s, 0.22 * s, 1.24 * s, 0.62 * s, 0.07 * s); shade(c, -0.62 * s, 0.22 * s, 1.24 * s, 0.62 * s, P.wood); inkStroke(c, s); c.stroke();
  c.strokeStyle = rgba(darken(P.wood, 0.45), 0.5); c.lineWidth = 1; for (let i = 0; i < 4; i++) { c.beginPath(); c.moveTo(-0.58 * s, (0.32 + i * 0.13) * s); c.lineTo(0.58 * s, (0.33 + i * 0.13) * s); c.stroke(); }
  engraved(c, 'PAPER', 0, 0.4 * s, 0.17 * s, '#2a1608', FONT.deco);
  engraved(c, 'ALLEY', 0, 0.62 * s, 0.17 * s, '#2a1608', FONT.deco);
  c.restore();
}

// ================================================================================================ round furniture: the eject button, the jar
export function drawEjectButton(c, L, G, t, words, pending) {
  const s = L.s, E = L.eject;
  c.save();
  c.translate(E.x, E.y);
  // brass pedestal
  c.beginPath(); c.moveTo(-0.42 * s, 0.55 * s); c.lineTo(-0.28 * s, 0.05 * s); c.lineTo(0.28 * s, 0.05 * s); c.lineTo(0.42 * s, 0.55 * s); c.closePath();
  shade(c, -0.42 * s, 0, 0.84 * s, 0.55 * s, P.brass); inkStroke(c, s); c.stroke();
  // painted balloon on the pedestal
  c.fillStyle = P.crimson; c.beginPath(); c.ellipse(0, 0.26 * s, 0.08 * s, 0.1 * s, 0, 0, TAU); c.fill();
  c.strokeStyle = P.ink; c.lineWidth = 1; c.beginPath(); c.moveTo(0, 0.36 * s); c.lineTo(0, 0.46 * s); c.stroke();
  // the mushroom button
  const press = G.hold && G.hold.action === 'eject' ? 0.05 * s * G.hold.frac : 0;
  c.beginPath(); c.ellipse(0, 0.04 * s, 0.3 * s, 0.08 * s, 0, 0, TAU); c.fillStyle = P.ironDark; c.fill(); c.stroke();
  c.beginPath(); c.ellipse(0, -0.06 * s + press, 0.27 * s, 0.13 * s, 0, Math.PI, TAU); c.lineTo(0.27 * s, 0.02 * s); c.ellipse(0, 0.02 * s, 0.27 * s, 0.07 * s, 0, 0, Math.PI); c.closePath();
  shade(c, -0.27 * s, -0.2 * s, 0.54 * s, 0.26 * s, P.crimson); c.stroke();
  if (pending) glow(c, 0, -0.05 * s, 0.6 * s, P.crimsonGlow, 0.35 + 0.2 * Math.sin(t * 10));
  c.restore();
}
export function drawJar(c, L, snap, t) {
  const s = L.s, J = L.jar, lob = snap.lobby || {}, risk = K.riskOf(snap);
  c.save();
  // a small brass bracket in the corner holds the jar during a round
  c.fillStyle = P.brassDark; c.fillRect(J.x - 0.35 * s, J.y, 0.7 * s, 0.06 * s);
  drawJarRat(c, J.x, J.y, s, t, 'back', 0.85);
  art('drawJar', c, J.x, J.y, s * 0.85, { fill: 1 - Math.exp(-(lob.jar_usd || 0) / (risk * 6)), t });
  drawJarRat(c, J.x, J.y, s, t, 'front', 0.85);
  drawTrendGlasses(c, J.x + 0.95 * s, J.y + 0.04 * s, s * 0.85, snap, t);   // the 5- and 15-minute trends, in a round too
  c.restore();
}

// ================================================================================================ badge (rounds), needle, replay
export function drawModeBadge(c, L, snap, G, t) {
  if (G.phase === 'lobby' || (G.phase === 'settled' && G.settle && G.settle.stage !== 'react')) return;
  const s = L.s, r = snap.round;
  const wooden = r ? r.kind === 'wooden' : G.ui.kind === 'wooden';
  if (snap.mode === 'replay') return;                             // world.js hangs its REPLAY marquee across the sky
  const word = wooden ? 'PAPER ALLEY' : snap.mode === 'live' ? 'LIVE' : 'DEMO';
  const col = wooden ? P.wood : snap.mode === 'live' ? P.crimson : P.brass;
  const w = (wooden ? 2.3 : 1.4) * s, h = 0.46 * s;
  const x = L.mirror ? 1.3 * s : 4.1 * s, y = 0.42 * s;
  c.save();
  c.strokeStyle = P.ironDark; c.lineWidth = Math.max(1, 0.02 * s);
  c.beginPath(); c.moveTo(x + 0.2 * s, -2); c.lineTo(x + 0.2 * s, y); c.moveTo(x + w - 0.2 * s, -2); c.lineTo(x + w - 0.2 * s, y); c.stroke();
  c.translate(x + w / 2, y); c.rotate(Math.sin(t * 0.9) * 0.025);
  roundRect(c, -w / 2, 0, w, h, 0.08 * s); shade(c, -w / 2, 0, w, h, col); inkStroke(c, s, LINE.inkThin); c.stroke();
  if (wooden) { c.save(); roundRect(c, -w / 2, 0, w, h, 0.08 * s); c.clip(); c.strokeStyle = rgba(darken(P.wood, 0.5), 0.35); c.lineWidth = 1; for (let i = 0; i < 4; i++) { const yy = (i + 0.5) * h / 4; c.beginPath(); c.moveTo(-w / 2, yy); c.bezierCurveTo(-w / 6, yy + 3, w / 6, yy - 3, w / 2, yy + 1); c.stroke(); } c.restore(); }
  rivet(c, -w / 2 + 0.2 * s, 0.08 * s, s); rivet(c, w / 2 - 0.2 * s, 0.08 * s, s);
  engraved(c, word, 0, h / 2 + 1, 0.21 * s, snap.mode === 'live' && !wooden ? '#fff' : wooden ? '#2a1608' : P.ink, wooden ? FONT.deco : FONT.sign);
  c.restore();
}
// The Time Freeze needle: a brass gramophone that lives on the bank's roof, on top of the split-flap sign (the outer corner, clear of the
// belfry and the bell rope). While the line is live its record turns under the needle; when the line goes quiet (or the engine reports a
// freeze) the record runs down and the tonearm lifts - k = 0 needle down .. 1 needle up. A physical object, no label: it is drawn in the
// lit layer, so in a freeze it goes sepia with everything else.
export function drawNeedle(c, L, up, t, k = 0) {
  const s = L.s, b = L.bank, f = L.facing;
  if (!b || !b.sign) return;
  const lift = clamp(k, 0, 1);
  let bx = b.sign.cx - f * b.sign.w * 0.36;                        // on the sign cabinet's outer top corner
  const by = b.sign.cy - b.sign.h / 2 - 0.01 * s;
  {                                                                 // a panned camera (after a haggle) must not push it under the corner cog / page
    const C = cornerLayout(L), reach = 0.34 * s;
    if (f > 0) bx += clamp(C.cog.x + C.cog.r + 4 - (bx - reach), 0, 0.12 * s);
    else bx -= clamp(bx + reach - (L.W - 0.8 * s), 0, 0.12 * s);
  }
  c.save();
  c.translate(bx, by); c.scale(f, 1);                              // facing: mirrored with the bank in the short world
  const u = s * 0.9;
  inkStroke(c, u, LINE.inkThin);
  // the cabinet
  roundRect(c, -0.24 * u, -0.17 * u, 0.48 * u, 0.17 * u, 0.03 * u); shade(c, -0.24 * u, -0.17 * u, 0.48 * u, 0.17 * u, P.wood); c.stroke();
  c.fillStyle = P.brassDark; c.fillRect(-0.24 * u, -0.05 * u, 0.48 * u, 0.018 * u);
  c.fillStyle = P.brass; c.beginPath(); c.arc(0.17 * u, -0.09 * u, 0.025 * u, 0, TAU); c.fill(); c.stroke();      // the crank boss
  // the record on its platter
  const spin = (G_spin.a += (1 - lift) * 0.12);
  c.beginPath(); c.ellipse(0, -0.19 * u, 0.2 * u, 0.055 * u, 0, 0, TAU); c.fillStyle = '#121014'; c.fill(); c.stroke();
  c.strokeStyle = 'rgba(255,255,255,0.14)'; c.lineWidth = 1;
  for (let i = 1; i < 4; i++) { c.beginPath(); c.ellipse(0, -0.19 * u, 0.2 * u * i / 4, 0.055 * u * i / 4, 0, 0, TAU); c.stroke(); }
  c.strokeStyle = 'rgba(255,255,255,0.35)'; c.lineWidth = Math.max(1, 0.012 * u);   // the shine turns with the record
  c.beginPath(); c.ellipse(0, -0.19 * u, 0.15 * u, 0.04 * u, 0, spin, spin + 0.7); c.stroke();
  c.fillStyle = P.crimson; c.beginPath(); c.ellipse(0, -0.19 * u, 0.055 * u, 0.016 * u, 0, 0, TAU); c.fill();
  // the horn: a brass morning glory on a curved neck, rising straight up (clear of the cog and the belfry)
  c.save();
  c.strokeStyle = P.ink; c.lineWidth = 0.07 * u; c.lineCap = 'round';
  c.beginPath(); c.moveTo(-0.15 * u, -0.17 * u); c.quadraticCurveTo(-0.24 * u, -0.28 * u, -0.12 * u, -0.4 * u); c.stroke();
  c.strokeStyle = P.brass; c.lineWidth = 0.045 * u; c.stroke();
  c.translate(-0.12 * u, -0.4 * u); c.rotate(-0.12);
  c.beginPath(); c.moveTo(-0.03 * u, 0); c.quadraticCurveTo(-0.08 * u, -0.18 * u, -0.2 * u, -0.3 * u); c.lineTo(0.2 * u, -0.3 * u); c.quadraticCurveTo(0.08 * u, -0.18 * u, 0.03 * u, 0); c.closePath();
  shade(c, -0.2 * u, -0.3 * u, 0.4 * u, 0.3 * u, P.gold); inkStroke(c, u, LINE.inkThin); c.stroke();
  c.beginPath(); c.ellipse(0, -0.3 * u, 0.2 * u, 0.05 * u, 0, 0, TAU); c.fillStyle = P.brassDark; c.fill(); c.stroke();
  c.beginPath(); c.ellipse(0, -0.3 * u, 0.13 * u, 0.03 * u, 0, 0, TAU); c.fillStyle = '#1a120a'; c.fill();
  c.restore();
  // the tonearm: pivots at the back corner; rests on the record (k 0) and lifts clear of it (k 1)
  c.save();
  c.translate(0.2 * u, -0.22 * u);
  c.rotate(-0.15 - lift * 0.75 + (up ? Math.sin(t * 3) * 0.02 * lift : 0));
  c.strokeStyle = P.ink; c.lineWidth = 0.05 * u; c.lineCap = 'round'; c.beginPath(); c.moveTo(0, 0); c.lineTo(-0.2 * u, 0.02 * u); c.stroke();
  c.strokeStyle = P.brassLight; c.lineWidth = 0.028 * u; c.stroke();
  c.fillStyle = P.ironDark; c.fillRect(-0.24 * u, -0.005 * u, 0.06 * u, 0.04 * u);
  c.restore();
  c.beginPath(); c.arc(0.2 * u, -0.22 * u, 0.035 * u, 0, TAU); shade(c, 0.165 * u, -0.255 * u, 0.07 * u, 0.07 * u, P.brass); inkStroke(c, u, LINE.inkThin); c.stroke();
  c.restore();
}
const G_spin = { a: 0 };
export function drawReplayFallback(c, w, h, t) {
  // a biplane tows REPLAY across the sky (used only when world.js does not draw its own banner)
  const s = Math.min((w * 95) / 1600, (h * 95) / 900);
  const x = ((t * 60) % (w + 12 * s)) - 6 * s, y = h * 0.16 + Math.sin(t * 0.8) * 0.15 * s;
  c.save();
  c.strokeStyle = P.ink; c.lineWidth = 1.5; c.beginPath(); c.moveTo(x, y); c.lineTo(x - 0.9 * s, y + 0.1 * s); c.stroke();
  const bw = 5.2 * s, bh = 0.8 * s, bx = x - 0.9 * s - bw;
  c.beginPath(); c.moveTo(bx, y - bh / 2);
  for (let i = 0; i <= 20; i++) c.lineTo(bx + (bw * i) / 20, y - bh / 2 + Math.sin(i * 0.8 + t * 4) * 0.06 * s);
  for (let i = 20; i >= 0; i--) c.lineTo(bx + (bw * i) / 20, y + bh / 2 + Math.sin(i * 0.8 + t * 4) * 0.06 * s);
  c.closePath(); c.fillStyle = '#fbf3dc'; c.fill(); inkStroke(c, s, LINE.inkThin); c.stroke();
  engraved(c, 'R E P L A Y', bx + bw / 2, y + 2, 0.55 * s, P.crimson, FONT.deco);
  c.fillStyle = P.crimson; c.beginPath(); c.ellipse(x + 0.3 * s, y, 0.45 * s, 0.12 * s, 0, 0, TAU); c.fill(); inkStroke(c, s, LINE.inkThin); c.stroke();
  c.fillStyle = P.brass; c.fillRect(x, y - 0.35 * s, 0.6 * s, 0.06 * s); c.fillRect(x, y + 0.2 * s, 0.6 * s, 0.06 * s);
  c.restore();
}

// ================================================================================================ the safety ledger (DOM)
export const Safety = {
  el: null, isOpenFlag: false, killT: null,
  isOpen() { return this.isOpenFlag; },
  open(opts = {}) {
    const el = document.getElementById('safety');
    if (!el || !K) return;
    this.el = el;
    this.build(opts);
    el.hidden = false; this.isOpenFlag = true;
    const first = el.querySelector(opts.armKill ? '.kill' : 'button');
    if (first) first.focus();
  },
  close() {
    if (this.el) { this.el.hidden = true; this.el.innerHTML = ''; }
    this.isOpenFlag = false; this.stopKill();
    if (K && K.focusGame) K.focusGame();                       // the ledger's inputs had the focus: give the keys back to the street
  },
  build(opts) {
    const snap = K.G.snap || {}, st = snap.settings || {}, lim = snap.limits || {}, el = this.el;
    const esc = (v) => String(v == null ? '' : v).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
    const risk = (coin, stop) => K.money(coin * stop, coin * stop);
    const dp = st.price_dp || 2, sym = st.symbol || 'XAU/USD', base = sym.split('/')[0];   // Zee 2026-11-04: the ledger speaks the symbol's units
    const coinWords = dp >= 4 ? `${Number(st.coin_oz || 0).toLocaleString()} ${base}` : `${Number(st.coin_oz || 0).toFixed(2)} oz of gold`;
    const stopWords = (d) => dp >= 4 ? `${+(d * 10 ** (dp - 1)).toFixed(1)} pips` : `$${Number(d).toFixed(2)} of gold`;
    const stops = st.stop_choices || [1, 2, 3];
    const live = snap.mode === 'live';
    const whyText = { alley: `finish the Alley first: ${lim.alley_done || 0} of ${lim.alley_needed || 5} wooden rounds${lim.alley_eject_done ? '' : ', one of them an eject'}${lim.alley_machete_needed && !lim.alley_machete_done ? ', one a machete' : ''}`,
      confirm: 'type CONFIRM below to sign', mode: 'only on the live street (this is ' + esc(snap.mode || '?') + ' mode)', balance: 'the purse is lighter than one coin and its margin', shutters: 'the shutters are down' };
    el.innerHTML = `
      <div class="ledger" role="dialog" aria-label="Safety ledger">
        <div class="holes"></div>
        <div class="stamp ${live ? 'live' : ''}">${live ? 'LIVE STREET' : esc((snap.mode || 'sim').toUpperCase()) + ' STREET'}</div>
        <h1>The Safety Ledger <small>all that can be changed</small></h1>
        <h2>The coin</h2>
        <div class="row"><label>One coin</label><span class="hint">${coinWords} &middot; its stop risks ${risk(st.coin_oz || 0, st.stop_dist || 0)} &middot; up to 3 coins: shoot 1-3 men in one volley</span></div>
        <div class="row"><label>Stop distance</label><span class="choice">${stops.map((d) => `<span class="chip ${Math.abs(d - st.stop_dist) < 1e-9 ? 'on' : ''}" data-stop="${d}">${stopWords(d)}</span>`).join('')}</span></div>
        <h2>The street</h2>
        <div class="row"><label>Sound</label><span class="switch ${st.sound ? 'on' : ''}" data-toggle="sound"><span class="knob"></span><span>${st.sound ? 'on' : 'off'}</span></span></div>
        <div class="row"><label>Words on the balloon</label><input type="text" maxlength="40" id="ejw" value="${esc(st.eject_words)}" placeholder="what you tell yourself when you let go"><button data-save="eject_words">ink it</button></div>
        <h2>Real money</h2>
        <div class="row"><label>Live switch</label><span class="switch live ${st.live_enabled ? 'on' : ''} ${snap.mode === 'replay' ? 'disabled' : ''}" data-live="1"><span class="knob"></span><span>${st.live_enabled ? (live ? 'ON - real orders' : 'ON - the real note trades the ' + esc(snap.mode || 'sim') + ' broker (pretend money)') : 'off'}</span></span></div>
        <div class="row"><span class="hint">${lim.live_allowed ? 'The real note is free to use.' : esc(whyText[lim.why_not_live] || 'not yet')}</span></div>
        <div class="row"><label>Type the word</label><input type="text" id="cfw" maxlength="12" placeholder="CONFIRM" autocomplete="off"><button data-confirm="1">${st.live_enabled ? 'switch live off' : 'sign: go live'}</button></div>
        <div class="row danger"><label>Kill switch</label><button class="kill ${opts.armKill ? 'armed' : ''}" id="killbtn"><i></i><span>HOLD 2 s: close the game's coin and lock the street</span></button></div>
        <div class="row"><span class="hint">Closes only the position this game opened. Your own trades on the account are never touched.</span></div>
        <h2>Today's limits</h2>
        <div class="limits">rounds <b>${lim.rounds_today ?? 0}</b> / ${lim.rounds_max ?? 30} &nbsp;·&nbsp; coins lost <b>${Number(lim.loss_today_coins || 0).toFixed(1)}</b> / ${lim.loss_max_coins ?? 10} &nbsp;·&nbsp; stops in a row <b>${lim.stops_in_row ?? 0}</b> / 3<br>
        wooden rounds <b>${lim.alley_done ?? 0}</b> / ${lim.alley_needed ?? 5} &nbsp;·&nbsp; eject done <b>${lim.alley_eject_done ? 'yes' : 'no'}</b> &nbsp;·&nbsp; live allowed <b>${lim.live_allowed ? 'yes' : 'no'}</b></div>
        <div class="msg" id="smsg"></div>
        <button class="close" data-close="1">close the ledger (Esc)</button>
      </div>`;
    const msg = (t, ok) => { const m = el.querySelector('#smsg'); if (m) { m.textContent = t; m.className = 'msg' + (ok ? ' ok' : ''); } };
    const send = async (obj, okText) => {
      const r = await K.net.settings(obj);
      if (r && r.ok) { msg(okText || 'written', true); if (r.settings && K.G.snap) Object.assign(K.G.snap.settings, r.settings); setTimeout(() => this.isOpenFlag && this.build({}), 250); }
      else msg('refused: ' + ((r && r.why) || 'no answer'), false);
      return r;
    };
    el.onclick = (e) => {
      const tg = e.target.closest('[data-coin],[data-stop],[data-toggle],[data-save],[data-confirm],[data-close],[data-live]');
      if (!tg) { if (e.target === el) this.close(); return; }
      if (tg.dataset.close) { this.close(); return; }
      if (tg.dataset.coin) send({ coin_oz: +tg.dataset.coin }, 'coin size written');
      if (tg.dataset.stop) send({ stop_dist: +tg.dataset.stop }, 'anvil distance written');
      if (tg.dataset.toggle) { const k = tg.dataset.toggle; send({ [k]: !st[k] }, k + ' written'); if (k === 'sound') K.snd('tick'); }
      if (tg.dataset.save) { const v = el.querySelector('#ejw').value.slice(0, 40); send({ eject_words: v }, 'the balloon is painted'); }
      // on the live street the switch means real orders; on the sim street the same signature trades the sim broker with pretend money
      if (tg.dataset.live) { msg(live ? 'type CONFIRM below and press the button to sign: real orders, real money' : 'sign below with CONFIRM to trade the ' + (snap.mode || 'sim') + ' broker: pretend money', true); }
      if (tg.dataset.confirm) {
        const word = (el.querySelector('#cfw').value || '').trim();
        if (st.live_enabled) send({ live_enabled: false }, 'live is off');
        else if (word !== 'CONFIRM') msg('the word is CONFIRM, in capitals', false);
        else send({ live_enabled: true, confirm_word: 'CONFIRM' }, 'signed: the live switch is on');
      }
    };
    const kb = el.querySelector('#killbtn');
    const startKill = (e) => { e.preventDefault(); this.stopKill(); const t0 = performance.now(); const bar = kb.querySelector('i');
      this.killT = setInterval(() => { const f = Math.min(1, (performance.now() - t0) / 2000); bar.style.width = (f * 100) + '%';
        if (f >= 1) { this.stopKill(); K.net.act('kill', {}).then((r) => { msg(r.accepted ? 'killed: the game’s coin is closed and the street is locked' : 'kill refused: ' + r.why, r.accepted); K.snd('chain'); }); } }, 30); };
    kb.addEventListener('pointerdown', startKill);
    kb.addEventListener('keydown', (e) => { if ((e.code === 'Space' || e.code === 'Enter') && !e.repeat) startKill(e); });
    const stop = () => { this.stopKill(); const bar = kb.querySelector('i'); if (bar) bar.style.width = '0%'; };
    kb.addEventListener('pointerup', stop); kb.addEventListener('pointerleave', stop); kb.addEventListener('keyup', stop);
    el.querySelectorAll('input').forEach((inp) => inp.addEventListener('keydown', (e) => e.stopPropagation()));
  },
  stopKill() { if (this.killT) { clearInterval(this.killT); this.killT = null; } },
};
