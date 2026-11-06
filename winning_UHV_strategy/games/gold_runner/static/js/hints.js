// hints.js - volume hints drawn on the street (Zee 2026-11-04). The engine reads real bars and ticks (engine.py vsa_read / _update_hints);
// these only draw what it found - they never move the Runner or the street (the street is the price):
//   drawFrictionTrench  stopping volume against a losing slide: boots dig in, dust, torn grass, steam (buyers / sellers absorbing)
//   drawFaultLines      an upthrust / spring against a winning slide: glowing cracks spread across the hill (take the profit)
//   drawVortex          a liquidity sweep: a whirlwind of smoke and grass over the Runner
//   drawPolished        the quiet after the sweep: a wind-swept, polished groove along the path it cleared

const TAU = Math.PI * 2;
const rnd = (n) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };

export function drawFrictionTrench(c, x, y, s, t, f) {
  c.save();
  // two gouges dug into the ground behind his heels
  c.strokeStyle = 'rgba(70,45,25,0.85)'; c.lineWidth = Math.max(2, 0.05 * s); c.lineCap = 'round';
  for (const dx of [-0.12, 0.1]) { c.beginPath(); c.moveTo(x + dx * s, y + 0.01 * s); c.lineTo(x + dx * s - f * 0.45 * s, y + 0.03 * s); c.stroke(); }
  // a thick, rolling dust cloud at his boots
  for (let i = 0; i < 18; i++) {
    const ph = (t * (0.9 + rnd(i) * 0.6) + rnd(i * 3.1)) % 1, ang = rnd(i * 7.7) * Math.PI;
    const px = x - f * (0.1 + ph * 0.9) * s + Math.cos(ang + t) * 0.15 * s, py = y - (0.05 + ph * 0.55 + rnd(i * 2.3) * 0.2) * s;
    const r = (0.08 + ph * 0.22) * s;
    c.globalAlpha = 0.55 * (1 - ph); c.fillStyle = i % 3 ? '#c9a77a' : '#a88358';
    c.beginPath(); c.arc(px, py, r, 0, TAU); c.fill();
  }
  // torn grass and clods flying back
  for (let i = 0; i < 10; i++) {
    const ph = (t * 2.2 + rnd(i * 5.5)) % 1, px = x - f * ph * 0.8 * s, py = y - Math.sin(ph * Math.PI) * 0.45 * s;
    c.globalAlpha = 1 - ph; c.strokeStyle = i % 2 ? '#4f9a3a' : '#6b4423'; c.lineWidth = Math.max(1.5, 0.02 * s);
    c.beginPath(); c.moveTo(px, py); c.lineTo(px + Math.cos(t * 9 + i) * 0.05 * s, py + Math.sin(t * 9 + i) * 0.05 * s); c.stroke();
  }
  // steam rising: effort without progress
  for (let i = 0; i < 4; i++) {
    const ph = (t * 0.6 + i / 4) % 1;
    c.globalAlpha = 0.35 * (1 - ph); c.fillStyle = '#f2f2f6';
    c.beginPath(); c.arc(x + Math.sin(t * 2 + i) * 0.1 * s, y - (0.6 + ph * 0.9) * s, (0.06 + ph * 0.14) * s, 0, TAU); c.fill();
  }
  c.restore();
}

export function drawFaultLines(c, L, xn, t) {
  const s = L.s, pulse = 0.6 + 0.4 * Math.sin(t * 9);
  c.save(); c.lineCap = 'round'; c.lineJoin = 'round';
  for (let k = 0; k < 7; k++) {                                  // cracks fanning out from under the Runner, along the hill and down into it
    const dir = k % 2 ? 1 : -1, len = 0.06 + rnd(k * 3.7) * 0.12;
    let xa = xn, depth = 0;
    const pts = [];
    for (let j = 0; j <= 7; j++) {
      const u = j / 7, x2 = xn + dir * len * u, gx = L.xToScreen(x2), gy = L.gy(x2);
      depth += (rnd(k * 11 + j) - 0.3) * 0.18 * s;
      pts.push([gx + (rnd(k * 5 + j) - 0.5) * 0.08 * s, gy + 0.05 * s + Math.max(0, depth) + j * 0.06 * s * (k % 3 === 0 ? 1.8 : 0.6)]);
      xa = x2;
    }
    for (const [w, col, a] of [[0.07, '255,120,40', 0.35 * pulse], [0.025, '255,220,120', 0.95]]) {
      c.strokeStyle = `rgba(${col},${a.toFixed(3)})`; c.lineWidth = Math.max(1.5, w * s);
      c.beginPath(); pts.forEach(([px, py], i) => (i ? c.lineTo(px, py) : c.moveTo(px, py))); c.stroke();
    }
  }
  c.restore();
}

export function drawVortex(c, x, y, s, t) {
  c.save();
  for (let i = 0; i < 14; i++) {                                 // rings of white smoke spinning up a funnel
    const u = i / 14, rr = (0.25 + u * 0.75) * s, cy = y - u * 2.0 * s, a = t * (6 - u * 3) + i;
    c.globalAlpha = 0.35 + 0.4 * (1 - u); c.strokeStyle = '#ffffff'; c.lineWidth = Math.max(2, (0.12 - u * 0.05) * s);
    c.beginPath(); c.ellipse(x, cy, rr, rr * 0.28, 0, a, a + Math.PI * 1.4); c.stroke();
  }
  for (let i = 0; i < 16; i++) {                                 // grass and dirt whirling in it
    const u = (t * 0.7 + rnd(i * 2.9)) % 1, a = t * 7 + i * 2.1, rr = (0.25 + u * 0.7) * s;
    c.globalAlpha = 1 - u; c.fillStyle = i % 2 ? '#5fae45' : '#8a5a2b';
    c.fillRect(x + Math.cos(a) * rr, y - u * 2.0 * s + Math.sin(a) * rr * 0.28, Math.max(2, 0.03 * s), Math.max(2, 0.015 * s));
  }
  c.restore();
}

export function drawPolished(c, L, x0, x1, t) {
  const s = L.s, n = 24, lo = Math.min(x0, x1), hi = Math.max(x0, x1);
  c.save();
  c.beginPath();
  for (let i = 0; i <= n; i++) { const xn = lo + (hi - lo) * i / n; const px = L.xToScreen(xn), py = L.gy(xn) - 0.02 * s; i ? c.lineTo(px, py) : c.moveTo(px, py); }
  for (let i = n; i >= 0; i--) { const xn = lo + (hi - lo) * i / n; c.lineTo(L.xToScreen(xn), L.gy(xn) + 0.06 * s); }
  c.closePath();
  const g = c.createLinearGradient(L.xToScreen(lo), 0, L.xToScreen(hi), 0);
  g.addColorStop(0, 'rgba(210,240,255,0)'); g.addColorStop(0.2, 'rgba(210,240,255,0.75)'); g.addColorStop(0.8, 'rgba(230,248,255,0.75)'); g.addColorStop(1, 'rgba(210,240,255,0)');
  c.fillStyle = g; c.fill();
  for (let i = 0; i < 5; i++) {                                  // glints sliding along the polished groove
    const u = (t * 0.5 + i / 5) % 1, xn = lo + (hi - lo) * u, px = L.xToScreen(xn), py = L.gy(xn) + 0.01 * s, k = 0.06 * s * Math.sin(u * Math.PI);
    c.fillStyle = '#ffffff'; c.beginPath(); c.moveTo(px - k, py); c.lineTo(px, py - k * 0.3); c.lineTo(px + k, py); c.lineTo(px, py + k * 0.3); c.closePath(); c.fill();
  }
  c.restore();
}
