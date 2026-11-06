// yogi.js - Zee 2026-11-05: "during the day it should have a yogi master with an ORB sitting on the ground -> the orb shines when the diamond
// shines for 40 seconds and during this time the yogi starts jumping in happiness as his orb shines" + "make the yogi's dress n skin etc v v v
// detailed.. try your best to make it the most interactive yogi possible".
//
// Day = a UHV level is waiting and price is near it, or a breakout of the Turtle TV UHV 97.7% setting happened < ~2.1 min ago. A hint only:
// nothing here sends an order.
//
// What he does (all driven by the market or by Zee):
//   breathes (chest, shoulders, beard), blinks, his shawl and beard sway in the wind, prayer beads click through his fingers
//   near  0..1  how close price is to the waiting level: he levitates a little, the orb wakes from grey to a pulsing blue, one eye peeks
//   shine 0..1  the diamond (40 s): eyes wide, big smile, orb held high with rays and sparks, happy hops with knees tucked
//   calm        after the shine, until the day ends: a warm smile, the orb still glowing softly
//   look        his eyes follow the pointer when it is near him
//   poke        a click on him: he bows, "Om" floats up, petals fall
const TAU = Math.PI * 2;
const SKIN = '#c98a5a', SKIN_D = '#a86d43', SKIN_L = '#e0a777', SKIN_SH = 'rgba(90,45,20,0.25)';
const ROBE = '#e8781a', ROBE_D = '#b8560c', ROBE_L = '#ffa34a', SHAWL = '#c43d2a', SHAWL_D = '#8e2618', GOLD = '#f2c14e';

function petalsInit(st) {
  st.petals = [];
  for (let i = 0; i < 14; i++) st.petals.push({ x: (Math.random() - 0.5) * 2.2, y: -2.4 - Math.random() * 1.2, vy: 0.35 + Math.random() * 0.4, sp: Math.random() * TAU, c: i % 3 ? '#ff8fb1' : '#ffd36b' });
}

// (x, y) = the ground under him; s = the scene scale; st = { shine, near, calm, t0poke, look: {x,y} | null, mem (persistent object) }
export function drawYogi(ctx, x, y, s, t, st) {
  const shine = clamp01(st.shine || 0), near = clamp01(st.near || 0), calm = st.calm ? 1 : 0;
  const mem = st.mem || {};
  const poke = st.t0poke != null ? t - st.t0poke : 99, bow = poke < 2.2 ? Math.sin(Math.min(1, poke / 2.2) * Math.PI) : 0;
  const breath = Math.sin(t * 1.3), sway = Math.sin(t * 0.9) * 0.5 + Math.sin(t * 2.3) * 0.2;
  const hop = shine > 0 ? Math.abs(Math.sin(t * 5.5)) : 0;
  const lift = hop * 0.6 * s * shine + (near > 0 ? 0.35 + 0.45 * near + 0.07 * Math.sin(t * 2) : 0) * s * (1 - shine);   // hops when happy, levitates when near
  const by = y - lift;
  const ap = st.appear == null ? 99 : st.appear;                 // seconds since he appeared (thunder + smoke)
  if (ap < 0.35) { drawBolt(ctx, x, y, s, t, ap); drawSmoke(ctx, x, y, s, ap); return { x, y: by - 0.7 * s, r: 0.75 * s }; }   // the strike, before he shows
  ctx.save();
  if (ap < 1.2) ctx.globalAlpha = Math.min(1, (ap - 0.35) / 0.6);   // he fades in out of the smoke

  // ---- the aura behind him (wakes with near, blazes with shine)
  const aura = Math.max(near * 0.35, shine * 0.9, calm * 0.25);
  if (aura > 0.01) {
    const ag = ctx.createRadialGradient(x, by - 0.75 * s, 0.1 * s, x, by - 0.75 * s, 1.6 * s);
    ag.addColorStop(0, `rgba(255,236,170,${0.45 * aura})`); ag.addColorStop(0.5, `rgba(255,190,90,${0.18 * aura})`); ag.addColorStop(1, 'rgba(255,190,90,0)');
    ctx.fillStyle = ag; ctx.beginPath(); ctx.arc(x, by - 0.75 * s, 1.6 * s, 0, TAU); ctx.fill();
  }

  // ---- shadow + mat (the mat stays on the ground)
  const shK = 1 - Math.min(0.5, lift / (1.2 * s));
  ctx.fillStyle = 'rgba(0,0,0,0.28)';
  ctx.beginPath(); ctx.ellipse(x, y + 0.03 * s, 0.62 * s * shK, 0.09 * s * shK, 0, 0, TAU); ctx.fill();
  drawMat(ctx, x, y, s);

  // ---- the body, bowing forward from the hips
  ctx.save();
  ctx.translate(x, by - 0.15 * s); ctx.rotate(bow * 0.45); ctx.translate(-x, -(by - 0.15 * s));
  const tuck = hop * shine;                                     // knees pulled up mid-hop
  drawLegs(ctx, x, by, s, tuck);
  const chest = 1 + breath * 0.025;
  drawTorso(ctx, x, by, s, chest, sway);
  const hx = x + sway * 0.01 * s, hy = by - 0.98 * s - breath * 0.01 * s;
  // arms + orb
  const orbUp = shine > 0.05;
  const ox = x, oy = orbUp ? hy - 0.5 * s - hop * 0.05 * s : by - 0.36 * s;
  drawArms(ctx, x, by, s, ox, oy, orbUp, breath);
  drawHead(ctx, hx, hy, s, t, { shine, near, calm, sway, look: st.look, mem, bow });
  drawBeads(ctx, x, by, s, t, orbUp);
  ctx.restore();

  drawOrb(ctx, ox + (bow ? 0.25 * bow * s : 0), oy, s, t, shine, near, calm);

  // ---- happy sparks while he hops
  if (shine > 0.05) {
    for (let i = 0; i < 8; i++) {
      const a = t * 2 + i * TAU / 8, r = (0.9 + 0.3 * Math.sin(t * 3 + i)) * s;
      star(ctx, x + Math.cos(a) * r, by - 0.9 * s + Math.sin(a) * r * 0.6, 0.06 * s * shine, `rgba(255,245,200,${0.8 * shine})`);
    }
  }
  // ---- poke: "Om" and falling petals
  if (poke < 3.5) {
    if (!mem.petals || mem.pokeT !== st.t0poke) { petalsInit(mem); mem.pokeT = st.t0poke; }
    const a = Math.max(0, 1 - poke / 3.5);
    ctx.save(); ctx.globalAlpha = a;
    ctx.font = `bold ${Math.round(0.42 * s)}px serif`; ctx.textAlign = 'center';
    ctx.fillStyle = '#ffe9a8'; ctx.strokeStyle = 'rgba(80,40,10,0.8)'; ctx.lineWidth = Math.max(2, 0.05 * s);
    const ty = hy - 0.7 * s - poke * 0.35 * s;
    ctx.strokeText('ॐ', x + 0.65 * s, ty); ctx.fillText('ॐ', x + 0.65 * s, ty);
    for (const p of mem.petals) {
      const py = by + (p.y + p.vy * poke * 1.6) * s, px = x + (p.x + 0.15 * Math.sin(t * 2 + p.sp)) * s;
      if (py > y) continue;
      ctx.fillStyle = p.c; ctx.beginPath(); ctx.ellipse(px, py, 0.05 * s, 0.025 * s, t * 3 + p.sp, 0, TAU); ctx.fill();
    }
    ctx.restore();
  }
  ctx.restore();
  if (ap < 2.6) { if (ap < 0.6) drawBolt(ctx, x, y, s, t, ap); drawSmoke(ctx, x, y, s, ap); }
  return { x, y: by - 0.7 * s, r: 0.75 * s };                    // his hit circle (a click pokes him)
}

// the entrance: a lightning bolt strikes his mat, a white flash, then a ring of smoke billows out and drifts up (Zee 2026-11-05)
function drawBolt(ctx, x, y, s, t, ap) {
  const a = Math.max(0, 1 - ap / 0.6);
  ctx.save();
  ctx.globalAlpha = a;
  const fg = ctx.createRadialGradient(x, y - 0.6 * s, 0, x, y - 0.6 * s, 3 * s);
  fg.addColorStop(0, 'rgba(255,255,255,0.95)'); fg.addColorStop(1, 'rgba(200,220,255,0)');
  ctx.fillStyle = fg; ctx.beginPath(); ctx.arc(x, y - 0.6 * s, 3 * s, 0, TAU); ctx.fill();
  let px = x + 0.4 * s, py = y - 9 * s;
  ctx.strokeStyle = '#ffffff'; ctx.lineWidth = Math.max(3, 0.08 * s); ctx.shadowColor = '#bcd8ff'; ctx.shadowBlur = 25;
  ctx.beginPath(); ctx.moveTo(px, py);
  for (let i = 1; i <= 9; i++) { px = x + (i === 9 ? 0 : (Math.sin(i * 12.9 + Math.floor(t * 20)) * 0.45) * s); py = y - 9 * s + i * s; ctx.lineTo(px, py); }
  ctx.stroke();
  ctx.lineWidth = Math.max(1, 0.03 * s); ctx.strokeStyle = '#e8f2ff'; ctx.stroke();
  ctx.restore();
}
function drawSmoke(ctx, x, y, s, ap) {
  const k = Math.min(1, ap / 2.6);
  ctx.save();
  for (let i = 0; i < 16; i++) {
    const ang = (i / 16) * TAU + i * 0.4, dist = (0.3 + 1.3 * Math.sqrt(k)) * s * (0.8 + 0.3 * Math.sin(i * 7.1));
    const px = x + Math.cos(ang) * dist, py = y - 0.4 * s + Math.sin(ang) * dist * 0.45 - k * (0.6 + 0.4 * Math.sin(i)) * s;
    const r = (0.25 + 0.45 * k) * s * (0.8 + 0.4 * Math.sin(i * 3.3) ** 2), a = 0.75 * (1 - k);
    const g = ctx.createRadialGradient(px, py, 0, px, py, r);
    g.addColorStop(0, `rgba(235,232,240,${a})`); g.addColorStop(0.6, `rgba(190,185,200,${a * 0.6})`); g.addColorStop(1, 'rgba(160,155,170,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(px, py, r, 0, TAU); ctx.fill();
  }
  ctx.restore();
}

function clamp01(v) { return Math.max(0, Math.min(1, v)); }
function star(ctx, x, y, r, col) {
  ctx.fillStyle = col; ctx.beginPath();
  for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4, rr = i % 2 ? r * 0.35 : r; ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
  ctx.closePath(); ctx.fill();
}

function drawMat(ctx, x, y, s) {
  ctx.save();
  ctx.fillStyle = '#6e2b22'; ctx.beginPath(); ctx.ellipse(x, y, 0.7 * s, 0.11 * s, 0, 0, TAU); ctx.fill();
  ctx.strokeStyle = GOLD; ctx.lineWidth = Math.max(1, 0.015 * s);
  ctx.beginPath(); ctx.ellipse(x, y, 0.62 * s, 0.085 * s, 0, 0, TAU); ctx.stroke();
  ctx.setLineDash([0.03 * s, 0.03 * s]); ctx.beginPath(); ctx.ellipse(x, y, 0.5 * s, 0.065 * s, 0, 0, TAU); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = GOLD;                                          // tassels
  for (const sx of [-1, 1]) for (let i = 0; i < 3; i++) { ctx.fillRect(x + sx * (0.7 * s) - 0.006 * s + sx * 0.02 * s, y - 0.04 * s + i * 0.035 * s, sx * 0.05 * s, 0.01 * s); }
  ctx.restore();
}

function drawLegs(ctx, x, by, s, tuck) {
  const ly = by - 0.17 * s - tuck * 0.08 * s;
  // the dhoti over crossed legs: a wide lens with folds
  const g = ctx.createLinearGradient(x, ly - 0.15 * s, x, ly + 0.15 * s);
  g.addColorStop(0, ROBE_L); g.addColorStop(0.55, ROBE); g.addColorStop(1, ROBE_D);
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.moveTo(x - 0.55 * s, ly + 0.06 * s);
  ctx.quadraticCurveTo(x - 0.5 * s, ly - 0.17 * s, x, ly - 0.14 * s);
  ctx.quadraticCurveTo(x + 0.5 * s, ly - 0.17 * s, x + 0.55 * s, ly + 0.06 * s);
  ctx.quadraticCurveTo(x, ly + 0.2 * s, x - 0.55 * s, ly + 0.06 * s); ctx.fill();
  ctx.strokeStyle = ROBE_D; ctx.lineWidth = Math.max(1, 0.012 * s);   // folds
  for (const k of [-0.32, -0.12, 0.12, 0.32]) { ctx.beginPath(); ctx.moveTo(x + k * s, ly - 0.1 * s); ctx.quadraticCurveTo(x + k * 1.15 * s, ly, x + k * 1.05 * s, ly + 0.1 * s); ctx.stroke(); }
  ctx.strokeStyle = GOLD; ctx.lineWidth = Math.max(1, 0.018 * s);     // the gold hem
  ctx.beginPath(); ctx.moveTo(x - 0.53 * s, ly + 0.07 * s); ctx.quadraticCurveTo(x, ly + 0.19 * s, x + 0.53 * s, ly + 0.07 * s); ctx.stroke();
  // bare feet resting on the knees, soles up
  for (const sx of [-1, 1]) {
    const fx = x + sx * 0.3 * s, fy = ly - 0.05 * s;
    ctx.fillStyle = SKIN; ctx.beginPath(); ctx.ellipse(fx, fy, 0.1 * s, 0.05 * s, -sx * 0.35, 0, TAU); ctx.fill();
    ctx.fillStyle = '#e8a985'; ctx.beginPath(); ctx.ellipse(fx + sx * 0.01 * s, fy - 0.005 * s, 0.07 * s, 0.03 * s, -sx * 0.35, 0, TAU); ctx.fill();   // the sole
    ctx.fillStyle = SKIN_D;
    for (let i = 0; i < 5; i++) { ctx.beginPath(); ctx.arc(fx + sx * (0.075 + 0.006 * i) * s, fy - 0.035 * s + i * 0.016 * s, 0.012 * s, 0, TAU); ctx.fill(); }   // toes
    ctx.strokeStyle = GOLD; ctx.lineWidth = Math.max(1, 0.01 * s);  // an anklet
    ctx.beginPath(); ctx.ellipse(fx - sx * 0.07 * s, fy + 0.01 * s, 0.02 * s, 0.035 * s, 0, 0, TAU); ctx.stroke();
  }
}

function drawTorso(ctx, x, by, s, chest, sway) {
  const top = by - 0.82 * s, bot = by - 0.22 * s, w = 0.27 * s * chest;
  // bare skin on the right side of the chest (the robe crosses the left shoulder)
  const sk = ctx.createLinearGradient(x - w, top, x + w, top);
  sk.addColorStop(0, SKIN_D); sk.addColorStop(0.5, SKIN_L); sk.addColorStop(1, SKIN_D);
  ctx.fillStyle = sk;
  ctx.beginPath(); ctx.moveTo(x - w, bot); ctx.quadraticCurveTo(x - w * 1.08, top + 0.12 * s, x - 0.08 * s, top);
  ctx.lineTo(x + 0.08 * s, top); ctx.quadraticCurveTo(x + w * 1.08, top + 0.12 * s, x + w, bot); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = SKIN_SH; ctx.lineWidth = Math.max(1, 0.012 * s);   // collarbone + navel hint
  ctx.beginPath(); ctx.moveTo(x + 0.03 * s, top + 0.06 * s); ctx.quadraticCurveTo(x + 0.12 * s, top + 0.04 * s, x + 0.2 * s, top + 0.07 * s); ctx.stroke();
  // the robe: wraps the belly and goes over the left shoulder
  const rg = ctx.createLinearGradient(x - w, 0, x + w, 0);
  rg.addColorStop(0, ROBE_D); rg.addColorStop(0.4, ROBE); rg.addColorStop(1, ROBE_D);
  ctx.fillStyle = rg;
  ctx.beginPath(); ctx.moveTo(x - w * 1.02, bot); ctx.quadraticCurveTo(x - w * 1.1, top + 0.1 * s, x - 0.1 * s, top - 0.01 * s);
  ctx.lineTo(x + 0.02 * s, top + 0.02 * s); ctx.quadraticCurveTo(x + 0.05 * s, top + 0.3 * s, x + w * 1.02, bot - 0.08 * s);
  ctx.lineTo(x + w * 1.02, bot); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = ROBE_D; ctx.lineWidth = Math.max(1, 0.012 * s);    // drape folds
  for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.moveTo(x - 0.15 * s + i * 0.07 * s, top + 0.1 * s + i * 0.05 * s); ctx.quadraticCurveTo(x - 0.05 * s + i * 0.08 * s, top + 0.28 * s + i * 0.04 * s, x + 0.05 * s + i * 0.07 * s, bot - 0.05 * s); ctx.stroke(); }
  // the red shawl over the shoulder, its tail swaying in the wind
  ctx.fillStyle = SHAWL;
  ctx.beginPath(); ctx.moveTo(x - 0.12 * s, top - 0.02 * s); ctx.quadraticCurveTo(x - 0.32 * s, top + 0.05 * s, x - 0.3 * s, top + 0.3 * s);
  ctx.quadraticCurveTo(x - 0.36 * s - sway * 0.05 * s, top + 0.5 * s, x - 0.33 * s - sway * 0.08 * s, top + 0.6 * s);
  ctx.lineTo(x - 0.24 * s - sway * 0.06 * s, top + 0.58 * s); ctx.quadraticCurveTo(x - 0.22 * s, top + 0.3 * s, x - 0.05 * s, top + 0.03 * s); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = GOLD; ctx.lineWidth = Math.max(1, 0.014 * s);
  ctx.beginPath(); ctx.moveTo(x - 0.33 * s - sway * 0.08 * s, top + 0.6 * s); ctx.lineTo(x - 0.24 * s - sway * 0.06 * s, top + 0.58 * s); ctx.stroke();
  ctx.fillStyle = SHAWL_D; for (let i = 0; i < 4; i++) { ctx.fillRect(x - 0.33 * s + i * 0.025 * s - sway * 0.08 * s, top + 0.6 * s, 0.008 * s, 0.05 * s); }   // fringe
  // the sacred thread across the bare chest
  ctx.strokeStyle = '#f4efe0'; ctx.lineWidth = Math.max(1, 0.008 * s);
  ctx.beginPath(); ctx.moveTo(x + 0.02 * s, top + 0.02 * s); ctx.quadraticCurveTo(x + 0.14 * s, top + 0.25 * s, x + 0.24 * s, bot - 0.05 * s); ctx.stroke();
  // rudraksha necklace
  for (let i = 0; i < 11; i++) {
    const a = Math.PI * (0.15 + 0.7 * i / 10), nx = x + Math.cos(a) * 0.13 * s, ny = top + 0.02 * s + Math.sin(a) * 0.16 * s;
    ctx.fillStyle = '#5b2a17'; ctx.beginPath(); ctx.arc(nx, ny, 0.016 * s, 0, TAU); ctx.fill();
  }
  ctx.fillStyle = GOLD; ctx.beginPath(); ctx.arc(x, top + 0.19 * s, 0.025 * s, 0, TAU); ctx.fill();
}

function drawArms(ctx, x, by, s, ox, oy, up, breath) {
  const sh = by - 0.78 * s + breath * 0.01 * s;
  for (const sx of [-1, 1]) {
    const shx = x + sx * 0.25 * s;
    const ex = up ? x + sx * 0.36 * s : x + sx * 0.33 * s, ey = up ? sh - 0.12 * s : by - 0.45 * s;
    const hx = ox + sx * 0.13 * s, hy = oy + (up ? 0.04 * s : 0.02 * s);
    ctx.strokeStyle = SKIN_D; ctx.lineCap = 'round'; ctx.lineWidth = 0.1 * s;
    ctx.beginPath(); ctx.moveTo(shx, sh); ctx.quadraticCurveTo(ex, ey, hx, hy); ctx.stroke();
    ctx.strokeStyle = SKIN; ctx.lineWidth = 0.075 * s;
    ctx.beginPath(); ctx.moveTo(shx, sh); ctx.quadraticCurveTo(ex, ey, hx, hy); ctx.stroke();
    if (sx < 0) {                                                 // the robe sleeve on the covered shoulder
      ctx.strokeStyle = ROBE; ctx.lineWidth = 0.11 * s;
      ctx.beginPath(); ctx.moveTo(shx, sh); ctx.lineTo(shx + (ex - shx) * 0.35, sh + (ey - sh) * 0.35); ctx.stroke();
    }
    ctx.strokeStyle = GOLD; ctx.lineWidth = Math.max(1, 0.012 * s);   // bracelets
    ctx.beginPath(); ctx.arc(hx - sx * 0.035 * s, hy, 0.04 * s, 0, TAU); ctx.stroke();
    ctx.fillStyle = SKIN; ctx.beginPath(); ctx.ellipse(hx, hy, 0.05 * s, 0.04 * s, 0, 0, TAU); ctx.fill();   // hands cupping the orb
  }
}

function drawHead(ctx, hx, hy, s, t, o) {
  const { shine, near, calm, sway, look, mem } = o;
  // ears + neck
  ctx.fillStyle = SKIN_D;
  ctx.fillRect(hx - 0.05 * s, hy + 0.08 * s, 0.1 * s, 0.1 * s);
  for (const sx of [-1, 1]) { ctx.beginPath(); ctx.ellipse(hx + sx * 0.15 * s, hy, 0.035 * s, 0.055 * s, 0, 0, TAU); ctx.fill(); }
  ctx.fillStyle = GOLD; for (const sx of [-1, 1]) { ctx.beginPath(); ctx.arc(hx + sx * 0.155 * s, hy + 0.055 * s, 0.014 * s, 0, TAU); ctx.fill(); }   // earrings
  // face with shading
  const fg = ctx.createRadialGradient(hx - 0.04 * s, hy - 0.04 * s, 0.02 * s, hx, hy, 0.17 * s);
  fg.addColorStop(0, SKIN_L); fg.addColorStop(0.7, SKIN); fg.addColorStop(1, SKIN_D);
  ctx.fillStyle = fg; ctx.beginPath(); ctx.ellipse(hx, hy, 0.145 * s, 0.165 * s, 0, 0, TAU); ctx.fill();
  // tilak + three ash lines on the forehead
  ctx.strokeStyle = 'rgba(245,240,230,0.85)'; ctx.lineWidth = Math.max(1, 0.01 * s);
  for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.moveTo(hx - 0.08 * s, hy - 0.11 * s + i * 0.018 * s); ctx.quadraticCurveTo(hx, hy - 0.125 * s + i * 0.018 * s, hx + 0.08 * s, hy - 0.11 * s + i * 0.018 * s); ctx.stroke(); }
  ctx.fillStyle = '#d0202a'; ctx.beginPath(); ctx.arc(hx, hy - 0.09 * s, 0.014 * s, 0, TAU); ctx.fill();
  // white hair bun on top + hair at the sides
  ctx.fillStyle = '#f2f0ea';
  ctx.beginPath(); ctx.ellipse(hx, hy - 0.2 * s, 0.065 * s, 0.055 * s, 0, 0, TAU); ctx.fill();
  ctx.beginPath(); ctx.arc(hx, hy - 0.06 * s, 0.155 * s, Math.PI * 1.05, Math.PI * 1.95); ctx.lineWidth = 0.03 * s; ctx.strokeStyle = '#f2f0ea'; ctx.stroke();
  ctx.strokeStyle = '#d4cfc4'; ctx.lineWidth = Math.max(1, 0.008 * s);
  ctx.beginPath(); ctx.arc(hx, hy - 0.2 * s, 0.035 * s, 0, TAU); ctx.stroke();
  // eyebrows (bushy white), raised when happy
  const lift = (shine * 0.025 + near * 0.008) * s;
  ctx.strokeStyle = '#f5f3ee'; ctx.lineWidth = Math.max(2, 0.022 * s); ctx.lineCap = 'round';
  for (const sx of [-1, 1]) { ctx.beginPath(); ctx.moveTo(hx + sx * 0.025 * s, hy - 0.05 * s - lift); ctx.quadraticCurveTo(hx + sx * 0.06 * s, hy - 0.07 * s - lift, hx + sx * 0.1 * s, hy - 0.045 * s - lift); ctx.stroke(); }
  // eyes: closed in meditation; one peeks when price is close; wide open + looking at the pointer when the orb shines
  mem.blinkAt = mem.blinkAt || t + 3;
  if (t > mem.blinkAt + 0.15) mem.blinkAt = t + 2.5 + Math.random() * 3;
  const blink = t > mem.blinkAt && t < mem.blinkAt + 0.15;
  const open = shine > 0.05 ? 1 : 0, peek = near > 0.7 && !open ? 1 : 0;
  let lx = 0, ly = 0;
  if (look) { const dx = look.x - hx, dy = look.y - hy, d = Math.hypot(dx, dy) || 1; if (d < 6 * s) { lx = (dx / d) * 0.012 * s; ly = (dy / d) * 0.008 * s; } }
  for (const sx of [-1, 1]) {
    const ex = hx + sx * 0.055 * s, ey = hy - 0.015 * s;
    const isOpen = !blink && (open || (peek && sx > 0));
    if (isOpen) {
      ctx.fillStyle = '#fbf7ef'; ctx.beginPath(); ctx.ellipse(ex, ey, 0.03 * s, 0.02 * s, 0, 0, TAU); ctx.fill();
      ctx.fillStyle = '#3b2412'; ctx.beginPath(); ctx.arc(ex + lx, ey + ly, 0.013 * s, 0, TAU); ctx.fill();
      ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(ex + lx + 0.004 * s, ey + ly - 0.004 * s, 0.004 * s, 0, TAU); ctx.fill();
    } else {
      ctx.strokeStyle = '#3a2618'; ctx.lineWidth = Math.max(1, 0.012 * s);
      ctx.beginPath(); ctx.arc(ex, ey - 0.008 * s, 0.028 * s, 0.2, Math.PI - 0.2); ctx.stroke();      // serene closed lids
    }
  }
  // nose + cheeks (rosy when happy)
  ctx.strokeStyle = SKIN_D; ctx.lineWidth = Math.max(1, 0.012 * s);
  ctx.beginPath(); ctx.moveTo(hx, hy - 0.01 * s); ctx.quadraticCurveTo(hx + 0.02 * s, hy + 0.04 * s, hx - 0.005 * s, hy + 0.045 * s); ctx.stroke();
  if (shine + calm > 0) { ctx.fillStyle = `rgba(230,90,90,${0.3 * Math.max(shine, calm * 0.5)})`; for (const sx of [-1, 1]) { ctx.beginPath(); ctx.arc(hx + sx * 0.08 * s, hy + 0.04 * s, 0.025 * s, 0, TAU); ctx.fill(); } }
  // the long white beard and moustache, swaying
  const bg = ctx.createLinearGradient(hx, hy + 0.04 * s, hx, hy + 0.45 * s);
  bg.addColorStop(0, '#ffffff'); bg.addColorStop(1, '#d9d4c8');
  ctx.fillStyle = bg;
  const bs = sway * 0.03 * s;
  ctx.beginPath(); ctx.moveTo(hx - 0.13 * s, hy + 0.02 * s);
  ctx.quadraticCurveTo(hx - 0.14 * s, hy + 0.25 * s, hx - 0.02 * s + bs, hy + 0.42 * s);
  ctx.lineTo(hx + bs, hy + 0.46 * s); ctx.lineTo(hx + 0.02 * s + bs, hy + 0.42 * s);
  ctx.quadraticCurveTo(hx + 0.14 * s, hy + 0.25 * s, hx + 0.13 * s, hy + 0.02 * s);
  ctx.quadraticCurveTo(hx, hy + 0.12 * s, hx - 0.13 * s, hy + 0.02 * s); ctx.fill();
  ctx.strokeStyle = 'rgba(160,150,135,0.6)'; ctx.lineWidth = Math.max(1, 0.006 * s);
  for (let i = -3; i <= 3; i++) { ctx.beginPath(); ctx.moveTo(hx + i * 0.03 * s, hy + 0.1 * s); ctx.quadraticCurveTo(hx + i * 0.025 * s + bs * 0.5, hy + 0.25 * s, hx + i * 0.01 * s + bs, hy + 0.4 * s); ctx.stroke(); }
  // mouth: a calm line, a soft smile after the shine, a big open smile while it shines
  ctx.fillStyle = '#fbfaf5';                                       // the moustache over the mouth
  for (const sx of [-1, 1]) { ctx.beginPath(); ctx.ellipse(hx + sx * 0.04 * s, hy + 0.07 * s, 0.05 * s, 0.018 * s, sx * -0.3, 0, TAU); ctx.fill(); }
  if (shine > 0.05) {
    ctx.fillStyle = '#7a2a1c'; ctx.beginPath(); ctx.ellipse(hx, hy + 0.1 * s, 0.035 * s, 0.025 * s * (0.6 + 0.4 * Math.abs(Math.sin(t * 5.5))), 0, 0, Math.PI); ctx.fill();
  } else {
    ctx.strokeStyle = '#6a3a22'; ctx.lineWidth = Math.max(1, 0.01 * s);
    ctx.beginPath(); ctx.arc(hx, hy + 0.08 * s, 0.025 * s, 0.25, Math.PI - 0.25, false); ctx.stroke();
  }
}

function drawBeads(ctx, x, by, s, t, up) {
  if (up) return;                                                  // both hands are on the orb while it shines
  const n = 9, step = Math.floor(t * 1.2) % n;                     // a bead clicks through his fingers every ~0.8 s
  for (let i = 0; i < n; i++) {
    const a = Math.PI * (0.1 + 0.8 * i / (n - 1)), bx = x + 0.43 * s + Math.cos(a) * 0.06 * s, byy = by - 0.33 * s + Math.sin(a) * 0.1 * s;
    ctx.fillStyle = i === step ? '#a4552b' : '#5b2a17'; ctx.beginPath(); ctx.arc(bx, byy, 0.017 * s, 0, TAU); ctx.fill();
  }
}

function drawOrb(ctx, ox, oy, s, t, shine, near, calm) {
  const wake = Math.max(near * (0.55 + 0.25 * Math.sin(t * (2 + 4 * near))), calm * 0.35);   // pulses faster as price gets closer
  const r = 0.13 * s * (1 + shine * 0.15);
  if (shine > 0.02) {
    const g = ctx.createRadialGradient(ox, oy, 0, ox, oy, 1.6 * s);
    g.addColorStop(0, `rgba(255,252,220,${0.8 * shine})`); g.addColorStop(0.25, `rgba(150,215,255,${0.4 * shine})`); g.addColorStop(1, 'rgba(150,215,255,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(ox, oy, 1.6 * s, 0, TAU); ctx.fill();
    ctx.strokeStyle = `rgba(255,255,230,${0.65 * shine})`; ctx.lineWidth = Math.max(1, 0.022 * s);
    for (let i = 0; i < 12; i++) {
      const a = t * 0.9 + (i * TAU) / 12, r1 = 0.22 * s, r2 = (0.5 + 0.15 * Math.sin(t * 4 + i)) * s;
      ctx.beginPath(); ctx.moveTo(ox + Math.cos(a) * r1, oy + Math.sin(a) * r1); ctx.lineTo(ox + Math.cos(a) * r2, oy + Math.sin(a) * r2); ctx.stroke();
    }
  } else if (wake > 0.02) {
    const g = ctx.createRadialGradient(ox, oy, 0, ox, oy, 0.55 * s);
    g.addColorStop(0, `rgba(150,215,255,${0.5 * wake})`); g.addColorStop(1, 'rgba(150,215,255,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(ox, oy, 0.55 * s, 0, TAU); ctx.fill();
  }
  const og = ctx.createRadialGradient(ox - 0.04 * s, oy - 0.045 * s, 0.01 * s, ox, oy, r);
  if (shine > 0.02) { og.addColorStop(0, '#ffffff'); og.addColorStop(0.45, '#d4f0ff'); og.addColorStop(1, '#5aaef8'); }
  else { const k = wake; og.addColorStop(0, mixc('#a7b0c4', '#e4f4ff', k)); og.addColorStop(1, mixc('#3a4462', '#3d86d6', k)); }
  ctx.fillStyle = og; ctx.beginPath(); ctx.arc(ox, oy, r, 0, TAU); ctx.fill();
  // swirling mist inside the orb
  ctx.save(); ctx.beginPath(); ctx.arc(ox, oy, r, 0, TAU); ctx.clip();
  ctx.strokeStyle = `rgba(255,255,255,${0.25 + 0.4 * Math.max(shine, wake)})`; ctx.lineWidth = Math.max(1, 0.012 * s);
  for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.arc(ox + Math.cos(t * 1.5 + i * 2) * 0.03 * s, oy + Math.sin(t * 1.5 + i * 2) * 0.03 * s, r * (0.4 + 0.18 * i), t * 2 + i, t * 2 + i + 2.2); ctx.stroke(); }
  ctx.restore();
  ctx.fillStyle = 'rgba(255,255,255,0.85)'; ctx.beginPath(); ctx.ellipse(ox - 0.045 * s, oy - 0.05 * s, 0.028 * s, 0.016 * s, -0.6, 0, TAU); ctx.fill();   // highlight
  if (!(shine > 0.02)) {                                           // the little lotus stand in his lap
    ctx.fillStyle = '#e88aa8';
    for (let i = -2; i <= 2; i++) { ctx.beginPath(); ctx.ellipse(ox + i * 0.04 * s, oy + r + 0.005 * s, 0.03 * s, 0.018 * s, i * 0.35, 0, TAU); ctx.fill(); }
  }
}

function mixc(a, b, k) {
  const pa = [1, 3, 5].map((i) => parseInt(a.substr(i, 2), 16)), pb = [1, 3, 5].map((i) => parseInt(b.substr(i, 2), 16));
  return '#' + pa.map((v, i) => Math.round(v + (pb[i] - v) * clamp01(k)).toString(16).padStart(2, '0')).join('');
}
