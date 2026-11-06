// diamondart.js - Zee's UHV Diamond on the street (2026-11-04). The engine reads his LAWS.md setup on the real 1-minute bars
// (diamond.py); these only draw what it found. Hints, never promises - nothing here moves the Runner or sends an order.
//   drawCamel  the trend in camel humps: walks the way the trend runs (right = up, toward the mafia; left = down, toward the bank),
//              carries as many humps as the trend has made, trots when the 15-minute market is clean, lies down when tired
//              (hump 4: his "hump 4 hmm maybe it shifts"), grazes when there is no trend (or his line 45 ended it)
//   drawGem    over the party to shoot: a ROUGH stone while a retracement has its UHV and waits; on the breakout it is CUT into a
//              brilliant - ROYAL (big, blue-white, crowned) only when the 15-minute chop meter says clean, otherwise cloudy GLASS;
//              1-3 sparks circle it for the laws that held; it SHATTERS if price falls back through the retracement

const TAU = Math.PI * 2;
const rnd = (n) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };

export function camelState(d, t) {                                     // the engine's Diamond reading -> how the camel moves
  d = d || {};
  const tired = (d.humps || 0) >= 4, moving = !!d.camel && !tired;    // "hump 1 trade, hump 2 trade, hump 3 trade, hump 4 hmm maybe it shifts"
  const mode = tired ? 'rest' : moving ? (d.clean ? 'trot' : 'walk') : 'graze';
  return { dir: d.camel || 1, humps: Math.min(3, d.humps || 1), mode, phase: t * (mode === 'trot' ? 7 : mode === 'walk' ? 3.5 : 0) };
}

export function drawCamel(c, x, y, s, t, st) {
  // st: { dir: -1|0|1 facing, humps: n, mode: 'walk'|'trot'|'graze'|'rest', phase: gait phase }
  const f = st.dir < 0 ? -1 : 1, n = Math.max(1, Math.min(3, st.humps || 1)), mode = st.mode;
  const rest = mode === 'rest', ph = st.phase || 0, k = s * 0.55;
  c.save();
  c.translate(x, y); c.scale(f, 1);
  const body = '#d9a95f', dark = '#b5823f', deep = '#8a5d2a';
  c.lineCap = 'round'; c.lineJoin = 'round';
  // shadow
  c.fillStyle = 'rgba(40,60,20,0.28)'; c.beginPath(); c.ellipse(0, 0.02 * k, 1.05 * k, 0.12 * k, 0, 0, TAU); c.fill();
  const lift = rest ? 0.62 * k : 0;                                    // lying down: the body sinks onto folded legs
  const bob = mode === 'trot' ? Math.abs(Math.sin(ph * 2)) * 0.05 * k : mode === 'walk' ? Math.abs(Math.sin(ph)) * 0.025 * k : 0;
  const by = -1.15 * k + lift - bob;                                   // body centre
  // legs (two pairs, diagonal gait)
  const legs = [[-0.55, 0], [-0.38, Math.PI], [0.42, Math.PI], [0.6, 0]];
  for (const [lx, off] of legs) {
    const back = lx < 0 ? dark : body;
    c.strokeStyle = off ? deep : back; c.lineWidth = 0.13 * k;
    if (rest) {                                                         // folded under the belly
      c.beginPath(); c.moveTo(lx * k, by + 0.25 * k); c.lineTo((lx + 0.18) * k, -0.05 * k); c.lineTo((lx - 0.1) * k, -0.04 * k); c.stroke();
      continue;
    }
    const sw = mode === 'graze' ? 0 : Math.sin(ph + off) * (mode === 'trot' ? 0.32 : 0.2);
    const kx = lx * k + sw * 0.25 * k, fx = lx * k + sw * 0.55 * k;
    c.beginPath(); c.moveTo(lx * k, by + 0.25 * k); c.lineTo(kx, -0.5 * k); c.lineTo(fx, -0.02 * k); c.stroke();
    c.fillStyle = deep; c.beginPath(); c.ellipse(fx + 0.04 * k, -0.02 * k, 0.09 * k, 0.04 * k, 0, 0, TAU); c.fill();
  }
  // body
  c.fillStyle = body;
  c.beginPath(); c.ellipse(0, by, 0.82 * k, 0.33 * k, 0, 0, TAU); c.fill();
  // the humps: one per completed swing of this trend
  const hx = n === 1 ? [0] : n === 2 ? [-0.3, 0.28] : [-0.42, 0, 0.4];
  for (let i = 0; i < n; i++) {
    const hh = (0.42 - (n === 3 && i === 2 ? 0.08 : 0)) * k;
    c.beginPath(); c.ellipse(hx[i] * k, by - 0.22 * k, 0.24 * k, hh, 0, Math.PI, TAU); c.fill();
  }
  // a red blanket with tassels under the humps
  c.fillStyle = '#b8323a'; c.beginPath(); c.ellipse(-0.05 * k, by - 0.12 * k, 0.5 * k, 0.16 * k, 0, 0, Math.PI); c.fill();
  c.fillStyle = '#f2c14e'; for (let i = 0; i < 5; i++) { c.beginPath(); c.arc((-0.45 + i * 0.2) * k, by + 0.06 * k, 0.035 * k, 0, TAU); c.fill(); }
  // tail
  c.strokeStyle = dark; c.lineWidth = 0.05 * k;
  c.beginPath(); c.moveTo(-0.8 * k, by - 0.05 * k); c.quadraticCurveTo(-0.95 * k, by + 0.1 * k + Math.sin(t * 3) * 0.04 * k, -0.9 * k, by + 0.35 * k); c.stroke();
  // neck and head
  const graze = mode === 'graze', sleepy = rest;
  const nx = 0.95 * k, ny = graze ? -0.25 * k + lift : sleepy ? by - 0.25 * k : by - 0.85 * k + bob;
  c.strokeStyle = body; c.lineWidth = 0.22 * k;
  c.beginPath(); c.moveTo(0.62 * k, by - 0.05 * k);
  c.quadraticCurveTo(graze ? 1.05 * k : 1.0 * k, graze ? by + 0.1 * k : by - 0.2 * k, nx, ny); c.stroke();
  c.fillStyle = body;
  c.beginPath(); c.ellipse(nx + 0.14 * k, ny, 0.24 * k, 0.12 * k, graze ? 0.5 : 0.1, 0, TAU); c.fill();
  c.fillStyle = dark; c.beginPath(); c.ellipse(nx + 0.36 * k, ny + (graze ? 0.1 : 0.02) * k, 0.07 * k, 0.06 * k, 0, 0, TAU); c.fill();   // muzzle
  c.beginPath(); c.ellipse(nx - 0.04 * k, ny - 0.13 * k, 0.04 * k, 0.07 * k, -0.3, 0, TAU); c.fill();                                  // ear
  // eye: open, or a sleepy line
  c.strokeStyle = '#2a1a0c'; c.fillStyle = '#2a1a0c'; c.lineWidth = Math.max(1, 0.03 * k);
  if (sleepy) { c.beginPath(); c.moveTo(nx + 0.08 * k, ny - 0.03 * k); c.lineTo(nx + 0.16 * k, ny - 0.02 * k); c.stroke(); }
  else { c.beginPath(); c.arc(nx + 0.12 * k, ny - 0.04 * k, 0.03 * k, 0, TAU); c.fill(); }
  // grazing: a tuft of grass at the muzzle; resting: three little z's
  if (graze) {
    c.strokeStyle = '#4f9a3a'; c.lineWidth = Math.max(1, 0.03 * k);
    for (let i = 0; i < 4; i++) { c.beginPath(); c.moveTo(nx + (0.3 + i * 0.05) * k, 0); c.lineTo(nx + (0.3 + i * 0.05 + Math.sin(t * 2 + i) * 0.03) * k, -0.16 * k); c.stroke(); }
  }
  c.restore();
  if (sleepy) {
    c.save(); c.fillStyle = 'rgba(255,255,255,0.9)'; c.font = `bold ${Math.round(0.22 * k)}px Georgia, serif`;
    for (let i = 0; i < 3; i++) { const p = (t * 0.4 + i / 3) % 1; c.globalAlpha = Math.sin(p * Math.PI); c.fillText('z', x + f * (0.95 + p * 0.4) * k, y - (1.0 + p * 0.7) * k); }
    c.restore();
  }
  if (mode === 'trot') {                                                // dust from the hooves on a clean, moving market
    c.save();
    for (let i = 0; i < 6; i++) {
      const p = (t * 1.5 + i / 6) % 1;
      c.globalAlpha = 0.45 * (1 - p); c.fillStyle = '#e6d3a8';
      c.beginPath(); c.arc(x - f * (0.6 + p * 0.9) * k, y - (0.05 + p * 0.25) * k, (0.06 + p * 0.12) * k, 0, TAU); c.fill();
    }
    c.restore();
  }
}

function facetPath(c, r) {                                              // a brilliant cut seen from the side: crown on top, pavilion below
  c.beginPath();
  c.moveTo(-r, -0.15 * r); c.lineTo(-0.55 * r, -0.62 * r); c.lineTo(0.55 * r, -0.62 * r); c.lineTo(r, -0.15 * r); c.lineTo(0, r); c.closePath();
}

export function drawGem(c, x, y, s, t, st) {
  // st: { stage: 'rough'|'cut'|'shatter', royal, laws, alpha, age, shatterT }
  const a = st.alpha == null ? 1 : st.alpha;
  if (a <= 0.01) return;
  c.save();
  c.globalAlpha = a;
  const bob = Math.sin(t * 2.2) * 0.06 * s;
  y += bob;
  if (st.stage === 'rough') {
    const r = 0.28 * s, pulse = 0.5 + 0.5 * Math.sin(t * 3);
    c.fillStyle = `rgba(170,210,255,${(0.18 + 0.15 * pulse).toFixed(3)})`; c.beginPath(); c.arc(x, y, r * 1.9, 0, TAU); c.fill();
    c.fillStyle = '#7c8ea3'; c.strokeStyle = '#4b5a6b'; c.lineWidth = Math.max(1, 0.025 * s);
    c.beginPath();
    for (let i = 0; i < 9; i++) { const ang = (i / 9) * TAU, rr = r * (0.75 + rnd(i * 3.3) * 0.4); i ? c.lineTo(x + Math.cos(ang) * rr, y + Math.sin(ang) * rr * 0.85) : c.moveTo(x + Math.cos(ang) * rr, y + Math.sin(ang) * rr * 0.85); }
    c.closePath(); c.fill(); c.stroke();
    c.fillStyle = 'rgba(210,235,255,0.75)'; c.beginPath(); c.moveTo(x - 0.3 * r, y - 0.4 * r); c.lineTo(x + 0.1 * r, y - 0.55 * r); c.lineTo(x - 0.05 * r, y - 0.1 * r); c.closePath(); c.fill();
    const g = (t * 0.7) % 1;                                             // a single glint crawling over the stone
    c.fillStyle = `rgba(255,255,255,${Math.sin(g * Math.PI).toFixed(3)})`; star(c, x + (g - 0.5) * r * 1.2, y - 0.3 * r, 0.12 * s);
    c.restore();
    return;
  }
  if (st.stage === 'shatter') {
    const p = Math.min(1, (st.shatterT || 0) / 1.2);
    for (let i = 0; i < 12; i++) {
      const ang = rnd(i * 7.1) * TAU, d = p * (0.6 + rnd(i) * 0.9) * s;
      c.globalAlpha = a * (1 - p);
      c.fillStyle = i % 2 ? '#cfe6ff' : '#9fb8d6';
      c.beginPath(); const px = x + Math.cos(ang) * d, py = y + Math.sin(ang) * d + p * p * 0.8 * s;
      c.moveTo(px, py - 0.06 * s); c.lineTo(px + 0.05 * s, py + 0.04 * s); c.lineTo(px - 0.05 * s, py + 0.05 * s); c.closePath(); c.fill();
    }
    c.restore();
    return;
  }
  const royal = !!st.royal, r = (royal ? 0.55 : 0.34) * s, spin = Math.cos(t * 1.6), sx = 0.35 + 0.65 * Math.abs(spin);
  // light: a slow rotating starburst for royal, a faint halo for glass
  if (royal) {
    c.save(); c.translate(x, y); c.rotate(t * 0.4);
    for (let i = 0; i < 12; i++) {
      const g = c.createLinearGradient(0, 0, Math.cos(i * TAU / 12) * 2.6 * r, Math.sin(i * TAU / 12) * 2.6 * r);
      g.addColorStop(0, 'rgba(220,240,255,0.55)'); g.addColorStop(1, 'rgba(220,240,255,0)');
      c.fillStyle = g; c.beginPath(); c.moveTo(0, 0);
      c.arc(0, 0, 2.6 * r, i * TAU / 12 - 0.09, i * TAU / 12 + 0.09); c.closePath(); c.fill();
    }
    c.restore();
  }
  const halo = c.createRadialGradient(x, y, 0, x, y, r * 2.2);
  halo.addColorStop(0, royal ? 'rgba(200,235,255,0.75)' : 'rgba(210,238,255,0.65)'); halo.addColorStop(1, 'rgba(200,235,255,0)');
  c.fillStyle = halo; c.beginPath(); c.arc(x, y, r * 2.2, 0, TAU); c.fill();
  // the stone, spinning (squashed by cos)
  c.save(); c.translate(x, y); c.scale(sx, 1);
  facetPath(c, r);
  const body = c.createLinearGradient(-r, -r, r, r);
  if (royal) { body.addColorStop(0, '#ffffff'); body.addColorStop(0.35, '#bfe6ff'); body.addColorStop(0.7, '#6fb6ff'); body.addColorStop(1, '#e8f6ff'); }
  else { body.addColorStop(0, '#ffffff'); body.addColorStop(0.4, '#d8f0ff'); body.addColorStop(0.75, '#8fc8ff'); body.addColorStop(1, '#f0faff'); }   // every diamond bright (Zee)
  c.fillStyle = body; c.fill();
  c.strokeStyle = royal ? 'rgba(255,255,255,0.95)' : 'rgba(120,130,140,0.9)'; c.lineWidth = Math.max(1, 0.02 * s); c.stroke();
  c.beginPath();                                                         // facet lines
  c.moveTo(-r, -0.15 * r); c.lineTo(r, -0.15 * r);
  for (const fx of [-0.55, -0.18, 0.18, 0.55]) { c.moveTo(fx * r, -0.62 * r); c.lineTo(fx * 0.6 * r, -0.15 * r); c.lineTo(0, r); }
  c.stroke();
  if (royal) {                                                           // fire: rainbow flashes inside the stone
    const cols = ['#ff6b6b', '#ffd84d', '#6bff9e', '#6bc8ff', '#c78bff'];
    for (let i = 0; i < 5; i++) { const ph = (t * 1.3 + i / 5) % 1; c.fillStyle = cols[i]; c.globalAlpha = a * 0.6 * Math.sin(ph * Math.PI); c.beginPath(); c.arc((rnd(i) - 0.5) * r, (rnd(i + 9) - 0.2) * r * 0.8, 0.08 * r + 0.06 * r * ph, 0, TAU); c.fill(); }
    c.globalAlpha = a;
  }
  c.restore();
  if (royal) {                                                           // a small gold crown sits on the royal stone
    const cy = y - 0.75 * r;
    c.fillStyle = '#f2c14e'; c.strokeStyle = '#a77a16'; c.lineWidth = Math.max(1, 0.015 * s);
    c.beginPath(); c.moveTo(x - 0.35 * r, cy); c.lineTo(x - 0.4 * r, cy - 0.35 * r); c.lineTo(x - 0.18 * r, cy - 0.15 * r); c.lineTo(x, cy - 0.45 * r);
    c.lineTo(x + 0.18 * r, cy - 0.15 * r); c.lineTo(x + 0.4 * r, cy - 0.35 * r); c.lineTo(x + 0.35 * r, cy); c.closePath(); c.fill(); c.stroke();
  }
  // the laws that held: 1-3 sparks circling the stone
  const nl = Math.max(0, Math.min(3, st.laws || 0));
  for (let i = 0; i < nl; i++) {
    const ang = t * 1.8 + i * TAU / nl;
    c.fillStyle = royal ? '#fff6c8' : '#e8ecf0';
    star(c, x + Math.cos(ang) * r * 1.55, y + Math.sin(ang) * r * 0.55, (royal ? 0.11 : 0.08) * s * (0.8 + 0.2 * Math.sin(t * 6 + i)));
  }
  c.restore();
}

function star(c, x, y, r) {
  c.beginPath();
  for (let i = 0; i < 8; i++) { const ang = i * Math.PI / 4, rr = i % 2 ? r * 0.3 : r; i ? c.lineTo(x + Math.cos(ang) * rr, y + Math.sin(ang) * rr) : c.moveTo(x + Math.cos(ang) * rr, y + Math.sin(ang) * rr); }
  c.closePath(); c.fill();
}

// Zee 2026-11-05: "make the camel-reading symbolism a bit easier ... think of something more visual". A signboard over the camel says it
// in plain words: the side (big arrow + BUYS / SELLS, green / red; WAIT grey with no trend), and the humps as coloured hump icons with
// the count, turning amber "TIRED" from the 4th hump. (x, y) = the sign's bottom centre.
export function drawCamelSign(c, x, y, s, t, d) {
  d = d || {};
  const side = d.camel || 0, n = d.humps || 0, tired = side && n >= 4;
  const col = !side ? '#8a8f99' : tired ? '#e0a020' : side > 0 ? '#2fb24a' : '#d8423a';
  const word = !side ? 'WAIT' : side > 0 ? 'BUYS' : 'SELLS';
  const w = 1.6 * s, h = 0.62 * s, bx = x - w / 2, by = y - h - 0.25 * s;
  c.save();
  c.fillStyle = '#5a3a1e'; c.fillRect(x - 0.025 * s, by + h, 0.05 * s, 0.25 * s);          // the post
  const pulse = side ? 0.5 + 0.5 * Math.sin(t * 3) : 0;
  if (side) { c.shadowColor = col; c.shadowBlur = (6 + 8 * pulse) * (s / 60); }
  c.fillStyle = '#2b1d12'; roundR(c, bx, by, w, h, 0.08 * s); c.fill();
  c.shadowBlur = 0;
  c.lineWidth = Math.max(2, 0.04 * s); c.strokeStyle = col; roundR(c, bx, by, w, h, 0.08 * s); c.stroke();
  // the arrow
  const ax = bx + 0.22 * s, ay = by + 0.22 * s, ar = 0.13 * s;
  c.fillStyle = col; c.beginPath();
  if (side > 0) { c.moveTo(ax, ay - ar); c.lineTo(ax + ar, ay + ar * 0.7); c.lineTo(ax - ar, ay + ar * 0.7); }
  else if (side < 0) { c.moveTo(ax, ay + ar); c.lineTo(ax + ar, ay - ar * 0.7); c.lineTo(ax - ar, ay - ar * 0.7); }
  else { c.rect(ax - ar, ay - ar * 0.25, 2 * ar, ar * 0.5); }
  c.closePath(); c.fill();
  c.font = `bold ${Math.round(0.24 * s)}px sans-serif`; c.textAlign = 'left'; c.textBaseline = 'middle';
  c.fillText(tired ? 'TIRED' : word, bx + 0.42 * s, ay + 0.01 * s);
  // the humps: one icon per hump in a row (up to 5), plus the number
  if (side) {
    const k = Math.min(5, n), hy = by + h - 0.15 * s;
    for (let i = 0; i < 5; i++) {
      const hx = bx + 0.16 * s + i * 0.17 * s;
      c.fillStyle = i < k ? col : 'rgba(255,255,255,0.12)';
      c.beginPath(); c.moveTo(hx - 0.07 * s, hy + 0.05 * s); c.quadraticCurveTo(hx, hy - 0.11 * s, hx + 0.07 * s, hy + 0.05 * s); c.closePath(); c.fill();
    }
    c.fillStyle = '#f4ecd2'; c.font = `bold ${Math.round(0.15 * s)}px sans-serif`; c.textAlign = 'right';
    c.fillText(n + (n === 1 ? ' hump' : ' humps'), bx + w - 0.07 * s, hy + 0.01 * s);
  } else {
    c.fillStyle = '#f4ecd2'; c.font = `${Math.round(0.13 * s)}px sans-serif`; c.textAlign = 'center';
    c.fillText('no trend - no setups', x, by + h - 0.14 * s);
  }
  c.restore();
}
function roundR(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }
