// bank2.js - the small Gold Bank (Zee 2026-11-04): "the bank on the left is so big its taking the entire screen.. i think we need a smaller
// bank with more natural reception and an old guy in a black hat walking and counting gold.. a guard sits outside. we can shoot the guard
// and then rob the banker to get 1 gold coin.. that's more natural.."
//
// A stone cottage with a tiled roof, a reception window where the old Banker (black top hat, white beard) paces behind his counter flipping
// a gold coin, an arched door, and a Guard dozing on a stool outside. Shooting = clicking the Guard (the same 'shoot' order as before):
// he topples, the Banker throws his hands up, the coin flies out (main.js arcs it from the Banker to the Runner).
//
// drawCottageBank(ctx, x, y, s, st) -> geometry; cottageGeometry(x, y, s, facing) -> the same without drawing.
// (x, y) = the bottom-centre of the facade at street level, s = px per unit (1 unit = the Runner's height), st.facing +1 = the door
// faces right (toward the street). st: { t, facing, shutters 0..1, jammed, night, wooden, banker: { mood } }.
// Banker moods (from main.js): smug (default, pacing), shot (robbed: hands up, the Guard is knocked over), sulk, gloat / crane, cards.

const TAU = Math.PI * 2;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const hash = (n) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };

const GEO = { sign: {}, bell: {}, door: {}, banker: {}, guard: {}, craneTip: {}, step: {} };
// unit layout (facing +1)
const U = {
  bodyW: 2.5, bodyH: 2.25, roofEave: 2.25, roofPeak: 3.05, roofOver: 0.22,
  win: { x0: -1.05, x1: 0.15, y0: -1.62, y1: -0.55 }, counterY: -0.74,
  door: { x0: 0.38, x1: 0.98, y0: -1.5, y1: -0.14 },
  guardX: 1.62,
  signCY: -3.5, signW: 1.9, signH: 0.78, bellY: -4.0,
};

export function cottageGeometry(x, y, s, facing = 1) {
  const f = facing < 0 ? -1 : 1;
  Object.assign(GEO.sign, { cx: x, cy: y + U.signCY * s, w: U.signW * s, h: U.signH * s });
  Object.assign(GEO.bell, { x, y: y + U.bellY * s });
  Object.assign(GEO.door, { x: x + f * ((U.door.x0 + U.door.x1) / 2) * s, y: y + ((U.door.y0 + U.door.y1) / 2) * s, w: (U.door.x1 - U.door.x0) * s, h: (U.door.y1 - U.door.y0) * s });
  Object.assign(GEO.banker, { x: x + f * ((U.win.x0 + U.win.x1) / 2) * s, y: y + (U.counterY - 0.25) * s, w: (U.win.x1 - U.win.x0) * s, h: 0.9 * s });
  Object.assign(GEO.guard, { x: x + f * U.guardX * s, y: y - 0.45 * s, w: 0.75 * s, h: 1.0 * s });
  Object.assign(GEO.craneTip, { x: x + f * 1.1 * s, y: y - 0.1 * s });
  Object.assign(GEO.step, { x: x + f * 0.68 * s, y: y - 0.1 * s });
  return GEO;
}

function palette(wood, night) {
  // Zee 2026-11-04: "more realistic colors of real boston bricks and an american bank" - red brick, pale mortar, limestone, slate
  const P = { wall: '#9a3f2c', wallD: '#6e2a1d', wallL: '#b5563f', mortar: '#d8cfc2', roof: '#3f444c', roofD: '#2a2e34', roofL: '#5a606a',
    trim: '#e8c35a', stone: '#e9e4d8', stoneD: '#b9b2a2', door: '#1f2a24' };
  P.bricks = ['#8f3626', '#a2452f', '#7d2c1f', '#b0513a', '#94402c', '#86331f', '#a84a35'];
  P.ink = '#2a1a10'; P.glass = night ? '#ffd27a' : '#fff1c9'; P.interior = night ? '#7a4a1f' : '#f2d9a8'; P.wood = '#7b4a26'; P.woodD = '#4f2e15';
  P.gold = '#ffcf3f'; P.goldD = '#c08a1c';
  return P;
}

function rr(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }
function inked(c, fill, lw = 0.035) { c.fillStyle = fill; c.fill(); c.strokeStyle = '#2a1a10'; c.lineWidth = lw; c.stroke(); }

// ---- the old Banker: black top hat, white beard, round glasses, waistcoat; seen from the waist up behind the counter
function drawBanker(c, x, y, t, mood, dir) {
  c.save(); c.translate(x, y);
  const robbed = mood === 'shot', glad = mood === 'gloat' || mood === 'crane', sad = mood === 'sulk', angry = mood === 'angry';
  const bob = robbed ? 0 : Math.abs(Math.sin(t * 3.2)) * 0.025;
  c.translate(0, -bob);
  if (robbed) c.rotate(Math.sin(t * 30) * 0.05);
  // body (waistcoat over a white shirt, black coat)
  c.beginPath(); c.moveTo(-0.24, 0.18); c.quadraticCurveTo(-0.27, -0.28, 0, -0.33); c.quadraticCurveTo(0.27, -0.28, 0.24, 0.18); c.closePath(); inked(c, '#1d1b22');
  c.beginPath(); c.moveTo(-0.11, 0.18); c.lineTo(-0.1, -0.28); c.lineTo(0.1, -0.28); c.lineTo(0.11, 0.18); c.closePath(); inked(c, '#7a2330', 0.02);
  c.fillStyle = '#d9b44a'; c.beginPath(); c.arc(0, -0.12, 0.018, 0, TAU); c.arc(0, -0.02, 0.018, 0, TAU); c.fill();
  // arms: counting a coin in front of him, or both hands up when robbed
  c.strokeStyle = '#1d1b22'; c.lineWidth = 0.085; c.lineCap = 'round';
  const flip = (t * 1.6) % 1;
  if (angry) {                          // furious: shaking a fist at the Runner who robbed him
    const sh = Math.sin(t * 18) * 0.03;
    c.beginPath(); c.moveTo(-0.2, -0.2); c.quadraticCurveTo(-0.22, -0.02, -0.02, -0.04); c.moveTo(0.2, -0.22); c.lineTo(0.3 * dir, -0.45 + sh); c.stroke();
    c.fillStyle = '#f1c9a5'; c.beginPath(); c.arc(0.3 * dir, -0.5 + sh, 0.06, 0, TAU); c.fill(); c.strokeStyle = '#2a1a10'; c.lineWidth = 0.015; c.stroke();
  } else if (robbed) {
    c.beginPath(); c.moveTo(-0.2, -0.22); c.lineTo(-0.32, -0.55); c.moveTo(0.2, -0.22); c.lineTo(0.32, -0.55); c.stroke();
    c.fillStyle = '#f1c9a5'; c.beginPath(); c.arc(-0.32, -0.58, 0.05, 0, TAU); c.arc(0.32, -0.58, 0.05, 0, TAU); c.fill();
  } else {
    c.beginPath(); c.moveTo(-0.2, -0.2); c.quadraticCurveTo(-0.22, -0.02, -0.06 * dir + 0.05, -0.04); c.moveTo(0.2, -0.2); c.quadraticCurveTo(0.24, -0.02, 0.1 * dir, -0.06); c.stroke();
    c.fillStyle = '#f1c9a5'; c.beginPath(); c.arc(0.1 * dir, -0.06, 0.045, 0, TAU); c.fill();
    // the coin he flips: up, spinning, back into the hand
    const cy = -0.08 - Math.sin(flip * Math.PI) * 0.32, sx = Math.abs(Math.cos(flip * TAU * 2));
    c.save(); c.translate(0.1 * dir, cy); c.scale(Math.max(0.15, sx), 1);
    c.beginPath(); c.arc(0, 0, 0.045, 0, TAU); c.fillStyle = '#ffcf3f'; c.fill(); c.strokeStyle = '#a8741c'; c.lineWidth = 0.012; c.stroke(); c.restore();
  }
  // head
  c.fillStyle = angry ? '#f29a86' : '#f1c9a5'; c.beginPath(); c.ellipse(0, -0.45, 0.13, 0.14, 0, 0, TAU); c.fill(); c.strokeStyle = '#2a1a10'; c.lineWidth = 0.025; c.stroke();
  // white beard and moustache
  c.beginPath(); c.moveTo(-0.13, -0.44); c.quadraticCurveTo(-0.12, -0.24, 0, -0.22); c.quadraticCurveTo(0.12, -0.24, 0.13, -0.44); c.quadraticCurveTo(0, -0.36, -0.13, -0.44); inked(c, '#f4f1ea', 0.02);
  // round glasses + eyes
  c.strokeStyle = '#2a1a10'; c.lineWidth = 0.014;
  for (const ex of [-0.05, 0.05]) { c.beginPath(); c.arc(ex + 0.02 * dir, -0.48, 0.035, 0, TAU); c.fillStyle = 'rgba(220,240,255,0.6)'; c.fill(); c.stroke(); }
  c.fillStyle = '#2a1a10';
  const blink = !robbed && ((t * 0.31) % 1) < 0.045;
  for (const ex of [-0.05, 0.05]) { c.beginPath(); if (blink) c.fillRect(ex + 0.03 * dir - 0.012, -0.482, 0.024, 0.004); else c.arc(ex + 0.03 * dir, -0.48 + (robbed ? -0.01 : 0), robbed ? 0.016 : 0.01, 0, TAU); c.fill(); }
  if (!robbed && !angry && ((t * 0.13) % 1) < 0.08) { c.fillStyle = '#f1c9a5'; c.beginPath(); c.arc(0.0, -0.5, 0.035, 0, TAU); c.fill(); c.strokeStyle = '#2a1a10'; c.lineWidth = 0.01; c.stroke(); }   // a finger pushing the glasses up
  if (angry) { c.strokeStyle = '#2a1a10'; c.lineWidth = 0.02; c.beginPath(); c.moveTo(-0.09, -0.56); c.lineTo(-0.01, -0.52); c.moveTo(0.11, -0.56); c.lineTo(0.03, -0.52); c.stroke(); }   // furious brows
  // mouth
  c.strokeStyle = '#2a1a10'; c.lineWidth = 0.016; c.beginPath();
  if (angry) { c.moveTo(-0.04, -0.32); c.lineTo(-0.015, -0.345); c.lineTo(0.015, -0.32); c.lineTo(0.04, -0.345); }   // gritted teeth
  else if (robbed) { c.ellipse(0, -0.33, 0.025, 0.03, 0, 0, TAU); }
  else if (glad) { c.arc(0, -0.37, 0.04, 0.15 * Math.PI, 0.85 * Math.PI); }
  else if (sad) { c.arc(0, -0.31, 0.035, 1.15 * Math.PI, 1.85 * Math.PI); }
  else { c.moveTo(-0.03, -0.34); c.lineTo(0.03, -0.34); }
  c.stroke();
  // black top hat
  c.fillStyle = '#141218'; c.beginPath(); c.ellipse(0, -0.57, 0.19, 0.04, 0, 0, TAU); c.fill(); c.strokeStyle = '#2a1a10'; c.lineWidth = 0.02; c.stroke();
  rr(c, -0.11, -0.86, 0.22, 0.3, 0.02); inked(c, '#141218', 0.02);
  c.fillStyle = '#6b2330'; c.fillRect(-0.11, -0.64, 0.22, 0.045);
  c.restore();
}

// ---- the Guard on his stool: blue coat, peaked cap, musket upright; dozes; knocked over when shot
function drawGuard(c, x, t, knocked, alert = false) {
  c.save(); c.translate(x, 0);
  // the stool
  c.strokeStyle = '#4f2e15'; c.lineWidth = 0.05; c.lineCap = 'round';
  c.beginPath(); c.moveTo(-0.16, 0); c.lineTo(-0.1, -0.42); c.moveTo(0.16, 0); c.lineTo(0.1, -0.42); c.stroke();
  rr(c, -0.2, -0.47, 0.4, 0.07, 0.02); inked(c, '#8a5a30', 0.02);
  const kk = knocked > 0 ? knocked * knocked * (3 - 2 * knocked) : 0;
  if (knocked > 0) {                    // tipped over backwards off the stool in a quick arc, stars circling
    c.translate(-0.15 - kk * 0.12, -0.3 + kk * 0.18); c.rotate(-1.35 * kk); c.translate(0.15, 0.3);
  }
  const breath = knocked > 0 ? 0 : Math.sin(t * 1.6) * 0.012;
  c.translate(0, -breath);
  // legs (seated)
  c.strokeStyle = '#2b3a66'; c.lineWidth = 0.1;
  c.beginPath(); c.moveTo(-0.06, -0.48); c.lineTo(0.18, -0.46); c.lineTo(0.2, -0.05); c.moveTo(0.04, -0.48); c.lineTo(0.26, -0.44); c.lineTo(0.28, -0.05); c.stroke();
  c.fillStyle = '#1a1410'; c.beginPath(); c.ellipse(0.24, -0.03, 0.08, 0.035, 0, 0, TAU); c.ellipse(0.32, -0.03, 0.08, 0.035, 0, 0, TAU); c.fill();
  // body: blue coat with brass buttons and a belt
  const nod = knocked > 0 || alert ? 0 : Math.max(0, Math.sin(t * 0.9)) * 0.08;
  c.beginPath(); c.moveTo(-0.17, -0.45); c.quadraticCurveTo(-0.2, -0.9, 0, -0.93); c.quadraticCurveTo(0.2, -0.9, 0.17, -0.45); c.closePath(); inked(c, '#34488a');
  c.fillStyle = '#2a1a10'; c.fillRect(-0.17, -0.58, 0.34, 0.05);
  c.fillStyle = '#e6b94f'; for (const by of [-0.66, -0.76, -0.86]) { c.beginPath(); c.arc(0.02, by, 0.017, 0, TAU); c.fill(); }
  // the musket: upright against his shoulder, or levelled at the Runner when he fires back (Zee 2026-11-04: the bank shoots back)
  if (alert) { c.strokeStyle = '#5a3a1e'; c.lineWidth = 0.05; c.beginPath(); c.moveTo(0.0, -0.82); c.lineTo(0.55, -0.86); c.stroke(); c.strokeStyle = '#7d848f'; c.lineWidth = 0.025; c.beginPath(); c.moveTo(0.4, -0.86); c.lineTo(0.85, -0.88); c.stroke(); }
  else { c.strokeStyle = '#5a3a1e'; c.lineWidth = 0.05; c.beginPath(); c.moveTo(0.2, -0.38); c.lineTo(0.24, -1.25); c.stroke();
  c.strokeStyle = '#7d848f'; c.lineWidth = 0.025; c.beginPath(); c.moveTo(0.235, -1.0); c.lineTo(0.245, -1.38); c.stroke(); }
  c.strokeStyle = '#34488a'; c.lineWidth = 0.08; c.beginPath(); c.moveTo(0.12, -0.84); c.quadraticCurveTo(0.22, -0.74, 0.22, -0.66); c.stroke();
  c.fillStyle = '#f1c9a5'; c.beginPath(); c.arc(0.22, -0.66, 0.04, 0, TAU); c.fill();
  // head nodding off, cap
  const track = alert ? -0.12 + Math.sin(t * 0.7) * 0.05 : 0;      // a hostile guard keeps his head turned to the Runner
  c.save(); c.translate(0, -1.03 + nod); c.rotate(nod * 1.5 + track);
  c.fillStyle = '#f1c9a5'; c.beginPath(); c.ellipse(0, 0, 0.11, 0.12, 0, 0, TAU); c.fill(); c.strokeStyle = '#2a1a10'; c.lineWidth = 0.022; c.stroke();
  c.strokeStyle = '#2a1a10'; c.lineWidth = 0.014; c.beginPath();
  if (knocked > 0) { for (const ex of [-0.035, 0.045]) { c.moveTo(ex - 0.018, -0.02); c.lineTo(ex + 0.018, 0.01); c.moveTo(ex + 0.018, -0.02); c.lineTo(ex - 0.018, 0.01); } }
  else if (alert) { c.stroke(); const bl = ((t * 0.37) % 1) < 0.05; c.fillStyle = '#2a1a10'; c.beginPath(); if (bl) { c.fillRect(-0.05, -0.007, 0.03, 0.006); c.fillRect(0.03, -0.007, 0.03, 0.006); } else { c.arc(-0.035, -0.005, 0.014, 0, TAU); c.arc(0.045, -0.005, 0.014, 0, TAU); } c.fill(); c.beginPath(); }   // wide awake, blinking
  else { c.moveTo(-0.055, -0.005); c.lineTo(-0.015, -0.005); c.moveTo(0.025, -0.005); c.lineTo(0.065, -0.005); }   // eyes shut, dozing
  c.stroke();
  c.fillStyle = '#5a3a24'; c.beginPath(); c.ellipse(0.01, 0.045, 0.05, 0.015, 0, 0, TAU); c.fill();                    // moustache
  if (!(knocked > 0)) {                  // the peaked cap (knocked off and flying when he is shot - drawn below)
  c.beginPath(); c.moveTo(-0.12, -0.05); c.lineTo(0.12, -0.05); c.lineTo(0.1, -0.15); c.lineTo(-0.1, -0.15); c.closePath(); inked(c, '#24315e', 0.018);
  c.fillStyle = '#1a1a1a'; c.beginPath(); c.ellipse(0.06, -0.05, 0.1, 0.025, 0, 0, TAU); c.fill();
  c.fillStyle = '#e6b94f'; c.beginPath(); c.arc(0, -0.1, 0.022, 0, TAU); c.fill();
  }
  c.restore();
  c.restore();
  // dozing Zs, or stars when knocked out (unrotated, above the stool)
  c.save(); c.translate(x, 0);
  if (knocked > 0) {                     // his cap flies off in an arc and lands on the ground beside him
    const k2 = Math.min(1, knocked), hx = 0.1 + k2 * 0.45, hy = -1.15 + k2 * 1.13 - Math.sin(k2 * Math.PI) * 0.45;
    c.save(); c.translate(hx, hy); c.rotate(k2 * 2.6);
    c.beginPath(); c.moveTo(-0.12, 0.05); c.lineTo(0.12, 0.05); c.lineTo(0.1, -0.05); c.lineTo(-0.1, -0.05); c.closePath(); inked(c, '#24315e', 0.018);
    c.fillStyle = '#1a1a1a'; c.beginPath(); c.ellipse(0.06, 0.05, 0.1, 0.025, 0, 0, TAU); c.fill(); c.restore();
  }
  if (knocked > 0) {
    for (let i = 0; i < 4; i++) {
      const a = t * 5 + i * (TAU / 4), sx = -0.3 + Math.cos(a) * 0.22, sy = -0.75 + Math.sin(a) * 0.07;
      c.fillStyle = '#ffe14d'; c.beginPath();
      for (let j = 0; j < 10; j++) { const aa = (j / 10) * TAU - Math.PI / 2, r = j % 2 ? 0.02 : 0.05; c.lineTo(sx + Math.cos(aa) * r, sy + Math.sin(aa) * r); }
      c.closePath(); c.fill();
    }
  } else if (!alert) {
    for (let i = 0; i < 3; i++) {
      const ph = ((t * 0.35) + i / 3) % 1;
      c.globalAlpha = Math.sin(ph * Math.PI) * 0.8;
      c.fillStyle = '#ffffff'; c.font = `italic bold ${(0.12 + ph * 0.08).toFixed(3)}px Georgia, serif`; c.textAlign = 'center';
      c.save(); c.scale(1, 1); c.fillText('z', 0.15 + ph * 0.3, -1.2 - ph * 0.45); c.restore();
    }
    c.globalAlpha = 1;
  }
  c.restore();
}

export function drawCottageBank(ctx, x, y, s, st = {}) {
  const t = +st.t || 0, f = st.facing < 0 ? -1 : 1;
  const wood = !!st.wooden, night = !!st.night, jammed = !!st.jammed;
  const shut = clamp(+st.shutters || 0, 0, 1);
  const mood = (st.banker && st.banker.mood) || 'smug';
  const K = palette(wood, night);
  const c = ctx;
  c.save();
  try {
    c.translate(x, y); c.scale(f * s, s);
    c.lineJoin = 'round';
    const hw = U.bodyW / 2;
    // chimney + smoke (behind the roof)
    rr(c, -0.95, -U.roofPeak + 0.15, 0.24, 0.6, 0.02); inked(c, K.wallD);
    for (let i = 0; i < 4; i++) {
      const ph = ((t * 0.18) + i / 4) % 1;
      c.globalAlpha = 0.45 * (1 - ph); c.fillStyle = '#f2efe8';
      c.beginPath(); c.arc(-0.83 + Math.sin(t * 0.8 + i) * 0.08 - ph * 0.25, -U.roofPeak + 0.05 - ph * 0.9, 0.08 + ph * 0.16, 0, TAU); c.fill();
    }
    c.globalAlpha = 1;
    // walls: Boston red brick in running bond, every brick its own shade, pale mortar joints, limestone quoins at the corners
    c.beginPath(); c.rect(-hw, -U.bodyH, U.bodyW, U.bodyH); c.fillStyle = K.mortar; c.fill();
    c.save(); c.beginPath(); c.rect(-hw, -U.bodyH, U.bodyW, U.bodyH); c.clip();
    const bw = 0.2, bh = 0.075, gap = 0.014;
    for (let r = 0, yy = -0.16 - bh; yy > -U.bodyH - bh; r++, yy -= bh) {
      const off = r % 2 ? bw / 2 : 0;
      for (let q = 0, xx = -hw - off; xx < hw; q++, xx += bw) {
        c.fillStyle = K.bricks[Math.floor(hash(r * 31 + q * 7) * K.bricks.length)];
        c.fillRect(xx + gap / 2, yy + gap / 2, bw - gap, bh - gap);
      }
    }
    c.fillStyle = 'rgba(255,255,255,0.10)'; c.fillRect(-hw, -U.bodyH, 0.2, U.bodyH);
    c.fillStyle = 'rgba(0,0,0,0.14)'; c.fillRect(hw - 0.22, -U.bodyH, 0.22, U.bodyH);
    c.restore();
    for (const qx of [-hw, hw - 0.14]) {                    // limestone quoins, alternating long and short
      for (let r = 0, yy = -0.16; yy > -U.bodyH + 0.01; r++, yy -= 0.2) {
        const long = r % 2 === 0, x0 = qx < 0 ? qx : (long ? qx - 0.08 : qx);
        c.beginPath(); c.rect(x0, yy - 0.18, long ? 0.22 : 0.14, 0.18); inked(c, K.stone, 0.012);
      }
    }
    c.beginPath(); c.rect(-hw, -U.bodyH, U.bodyW, U.bodyH); c.strokeStyle = '#2a1a10'; c.lineWidth = 0.035; c.stroke();
    // stone base + steps up to the door
    c.beginPath(); c.rect(-hw - 0.05, -0.16, U.bodyW + 0.1, 0.16); inked(c, K.stoneD);              // granite base course
    c.beginPath(); c.rect(U.door.x0 - 0.08, -0.1, (U.door.x1 - U.door.x0) + 0.16, 0.1); inked(c, '#9c917f', 0.02);
    // roof: tiles
    c.beginPath(); c.moveTo(-hw - U.roofOver, -U.roofEave); c.lineTo(0, -U.roofPeak); c.lineTo(hw + U.roofOver, -U.roofEave); c.closePath(); inked(c, K.roof);
    c.save(); c.clip();
    for (let r = 0, yy = -U.roofEave; yy > -U.roofPeak - 0.12; r++, yy -= 0.11) {            // slate shingles, staggered rows
      const off = r % 2 ? 0.09 : 0;
      for (let q = 0, xx = -2 - off; xx < 2; q++, xx += 0.18) {
        const k = hash(r * 13 + q * 5);
        c.fillStyle = k < 0.33 ? K.roof : k < 0.66 ? '#4a5059' : '#363b42';
        c.fillRect(xx + 0.008, yy - 0.11 + 0.008, 0.18 - 0.016, 0.11 - 0.008);
      }
    }
    c.fillStyle = 'rgba(255,255,255,0.10)'; c.beginPath(); c.moveTo(-hw - U.roofOver, -U.roofEave); c.lineTo(0, -U.roofPeak); c.lineTo(-0.15, -U.roofEave); c.closePath(); c.fill();
    c.restore();
    c.fillStyle = K.roofD; c.fillRect(-hw - U.roofOver, -U.roofEave, U.bodyW + 2 * U.roofOver, 0.05);
    c.beginPath(); c.rect(-hw - 0.08, -U.roofEave + 0.05, U.bodyW + 0.16, 0.1); inked(c, K.stone, 0.015);     // white cornice
    c.fillStyle = K.stoneD; for (let xx = -hw; xx < hw; xx += 0.12) c.fillRect(xx, -U.roofEave + 0.15, 0.06, 0.04);   // dentils
    // the GOLD BANK board under the eave (text never mirrored)
    rr(c, -0.85, -2.04, 1.7, 0.25, 0.03); inked(c, '#16191c', 0.025);
    c.save(); c.translate(0, -1.915); c.scale(f, 1);
    c.fillStyle = K.trim; c.font = 'bold 0.17px "Playfair Display", Georgia, serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
    c.fillText('GOLD BANK', 0, 0.01); c.restore();
    // the reception window: the warm room, the counter, the Banker pacing and flipping a coin
    const W0 = U.win;
    c.beginPath(); c.rect(W0.x0, W0.y0, W0.x1 - W0.x0, W0.y1 - W0.y0); inked(c, K.interior);
    c.save(); c.beginPath(); c.rect(W0.x0, W0.y0, W0.x1 - W0.x0, W0.y1 - W0.y0); c.clip();
    c.fillStyle = night ? 'rgba(255,190,90,0.35)' : 'rgba(255,255,255,0.15)'; c.fillRect(W0.x0, W0.y0, W0.x1 - W0.x0, 0.5);
    // shelves of gold behind him
    c.fillStyle = K.woodD; c.fillRect(W0.x0, -1.32, W0.x1 - W0.x0, 0.035);
    for (let i = 0; i < 7; i++) { c.fillStyle = i % 2 ? K.gold : K.goldD; rr(c, W0.x0 + 0.08 + i * 0.16, -1.43, 0.12, 0.11, 0.02); c.fill(); }
    const span = (W0.x1 - W0.x0) / 2 - 0.25, mid = (W0.x0 + W0.x1) / 2;
    const robbed = mood === 'shot';
    const px = robbed ? mid : mid + Math.sin(t * 0.55) * span, dir = Math.cos(t * 0.55) >= 0 ? 1 : -1;
    drawBanker(c, px, U.counterY + 0.02, t, mood, robbed ? 1 : dir);
    // the counter, with a coin pile and a ledger
    c.beginPath(); c.rect(W0.x0, U.counterY, W0.x1 - W0.x0, W0.y1 - U.counterY); inked(c, K.wood, 0.02);
    c.fillStyle = K.woodD; c.fillRect(W0.x0, U.counterY, W0.x1 - W0.x0, 0.04);
    for (let i = 0; i < 4; i++) { c.fillStyle = K.gold; c.beginPath(); c.ellipse(W0.x0 + 0.2 + i * 0.05, U.counterY - 0.02 - i * 0.025, 0.07, 0.022, 0, 0, TAU); c.fill(); c.strokeStyle = K.goldD; c.lineWidth = 0.01; c.stroke(); }
    c.fillStyle = '#f4ecd2'; c.fillRect(W0.x1 - 0.42, U.counterY - 0.03, 0.26, 0.04);
    c.restore();
    // window frame, mullions, sill
    c.strokeStyle = '#f4f1ea'; c.lineWidth = 0.06; c.strokeRect(W0.x0, W0.y0, W0.x1 - W0.x0, W0.y1 - W0.y0);
    c.beginPath(); c.rect(W0.x0 - 0.1, W0.y0 - 0.14, (W0.x1 - W0.x0) + 0.2, 0.12); inked(c, K.stone, 0.015);   // limestone lintel
    c.lineWidth = 0.03; c.beginPath(); c.moveTo(W0.x0, -1.42 + 0.0); c.stroke();
    c.beginPath(); c.moveTo(W0.x0, W0.y0 + 0.42); c.lineTo(W0.x1, W0.y0 + 0.42); c.stroke();
    c.fillStyle = 'rgba(255,255,255,0.18)'; c.beginPath(); c.moveTo(W0.x0 + 0.1, W0.y0); c.lineTo(W0.x0 + 0.35, W0.y0); c.lineTo(W0.x0 + 0.05, W0.y0 + 0.4); c.lineTo(W0.x0, W0.y0 + 0.4); c.closePath(); c.fill();
    rr(c, W0.x0 - 0.08, W0.y1, (W0.x1 - W0.x0) + 0.16, 0.07, 0.02); inked(c, K.stone, 0.02);
    // flower box under the window
    rr(c, W0.x0 + 0.05, W0.y1 + 0.07, (W0.x1 - W0.x0) - 0.1, 0.13, 0.02); inked(c, '#6b4526', 0.02);
    for (let i = 0; i < 8; i++) { c.fillStyle = ['#ff8fb3', '#ffe066', '#ffffff', '#ff6b6b'][i % 4]; c.beginPath(); c.arc(W0.x0 + 0.13 + i * 0.13, W0.y1 + 0.06 + (i % 2) * 0.03, 0.045, 0, TAU); c.fill(); }
    // the arched door
    const D = U.door, dw = D.x1 - D.x0, dcx = (D.x0 + D.x1) / 2, spring = D.y0 + dw / 2;
    c.beginPath(); c.arc(dcx, spring, dw / 2 + 0.09, Math.PI, 0); c.lineTo(D.x1 + 0.09, spring); c.lineTo(D.x0 - 0.09, spring); c.closePath(); inked(c, K.stone, 0.015);   // limestone arch
    rr(c, dcx - 0.06, D.y0 - 0.12, 0.12, 0.14, 0.01); inked(c, K.stone, 0.015);                                                 // keystone
    c.beginPath(); c.moveTo(D.x0, D.y1); c.lineTo(D.x0, spring); c.arc(dcx, spring, dw / 2, Math.PI, 0); c.lineTo(D.x1, D.y1); c.closePath(); inked(c, K.door);
    c.save(); c.clip(); c.strokeStyle = K.woodD; c.lineWidth = 0.02;
    c.strokeStyle = 'rgba(255,255,255,0.12)';
    for (const yy of [D.y0 + 0.35, D.y0 + 0.75]) { c.strokeRect(D.x0 + 0.08, yy, dw - 0.16, 0.3); }
    c.restore();
    c.fillStyle = K.trim; c.beginPath(); c.arc(D.x1 - 0.1, (D.y0 + D.y1) / 2 + 0.1, 0.03, 0, TAU); c.fill();
    // a lantern beside the door
    c.strokeStyle = '#2a1a10'; c.lineWidth = 0.02; c.beginPath(); c.moveTo(D.x1 + 0.12, -1.55); c.lineTo(D.x1 + 0.2, -1.55); c.stroke();
    rr(c, D.x1 + 0.13, -1.55, 0.13, 0.2, 0.03); inked(c, night ? '#ffd27a' : '#fbe7a8', 0.02);
    if (night) { const g = c.createRadialGradient(D.x1 + 0.2, -1.45, 0, D.x1 + 0.2, -1.45, 0.7); g.addColorStop(0, 'rgba(255,200,100,0.45)'); g.addColorStop(1, 'rgba(255,200,100,0)'); c.fillStyle = g; c.fillRect(D.x1 - 0.5, -2.15, 1.4, 1.4); }
    // shutters (news / dead hours) roll down over the window and the door; a jam nails planks across the door
    if (shut > 0.01) {
      const drop = (yy0, yy1, x0, x1) => {
        const hh = (yy1 - yy0) * shut;
        c.beginPath(); c.rect(x0, yy0, x1 - x0, hh); inked(c, '#8a5a30', 0.02);
        c.strokeStyle = '#5a3a1e'; c.lineWidth = 0.015;
        for (let yy = yy0 + 0.09; yy < yy0 + hh; yy += 0.09) { c.beginPath(); c.moveTo(x0, yy); c.lineTo(x1, yy); c.stroke(); }
      };
      drop(W0.y0, W0.y1, W0.x0, W0.x1); drop(D.y0, D.y1, D.x0, D.x1);
    }
    if (jammed) {
      c.strokeStyle = '#8a5a30'; c.lineWidth = 0.09; c.lineCap = 'butt';
      c.beginPath(); c.moveTo(D.x0 - 0.06, D.y0 + 0.2); c.lineTo(D.x1 + 0.06, D.y1 - 0.25); c.moveTo(D.x1 + 0.06, D.y0 + 0.2); c.lineTo(D.x0 - 0.06, D.y1 - 0.25); c.stroke();
    }
    // the Guard outside the door (knocked over while the Banker is being robbed)
    // Zee 2026-11-04: three guards - each one shot in the volley lies knocked over; the ones still up aim at the Runner when he is hostile
    const nK = st.knocked != null ? Math.max(0, Math.min(3, +st.knocked || 0)) : (mood === 'shot' ? 1 : 0);
    const kp = Array.isArray(st.knockProg) ? st.knockProg : [1, 1, 1];
    for (let i = 2; i >= 0; i--) drawGuard(c, U.guardX + i * 0.48, t + i * 1.3, i < nK ? Math.max(0.001, kp[i] ?? 1) : 0, !!st.alert && i >= nK);
    // the roof-sign posts (the split-flap board itself is drawn by main.js in the lit layer)
    c.strokeStyle = '#4f2e15'; c.lineWidth = 0.05;
    c.beginPath(); c.moveTo(-0.55, U.signCY + U.signH / 2); c.lineTo(-0.45, -U.roofEave - 0.42); c.moveTo(0.55, U.signCY + U.signH / 2); c.lineTo(0.45, -U.roofEave - 0.42); c.stroke();
  } catch (e) {
    if (!drawCottageBank._err) { drawCottageBank._err = true; console.error('drawCottageBank', e); }
  }
  c.restore();
  return cottageGeometry(x, y, s, f);
}
