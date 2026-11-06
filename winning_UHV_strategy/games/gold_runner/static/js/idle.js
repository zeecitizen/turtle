// idle.js - what the Runner does while the market goes nowhere (Zee 2026-11-04): "if the market is not going anywhere initially, the player
// has nothing to do but wait for the tilt: do yoga, watch birds, build a camp and sleep .. make these beautiful waiting idle animations
// (if the user clicks the character it becomes ready with a shotgun)".
//
// drawIdleScene(ctx, kind, x, y, s, t, f, runner): (x, y) = his feet, s = px per unit, f = facing. runner(ctx, x, y, s, st) draws the Runner
// (art.js drawRunner, passed in by main.js so the outfit and the wooden Apprentice stay right). kind: 'yoga' | 'birds' | 'camp'.
// k (0..1) fades the scene in.

const TAU = Math.PI * 2;
const ease = (u) => u * u * (3 - 2 * u);
function inked(c, fill, lw) { c.fillStyle = fill; c.fill(); c.strokeStyle = '#2a1a10'; c.lineWidth = lw; c.stroke(); }

function shotgunOnGround(c, x, y, s) {
  c.save(); c.translate(x, y - 0.03 * s); c.rotate(-0.04);
  c.fillStyle = '#7a4520'; c.fillRect(-0.32 * s, -0.025 * s, 0.22 * s, 0.05 * s);
  c.fillStyle = '#3b3f45'; c.fillRect(-0.1 * s, -0.02 * s, 0.42 * s, 0.035 * s);
  c.restore();
}

function yoga(c, x, y, s, t, f, runner, wooden) {
  // a purple mat, the shotgun laid down, slow sun salutations with a breathing glow
  c.save(); c.fillStyle = '#8a5cc2'; c.strokeStyle = '#2a1a10'; c.lineWidth = Math.max(1, 0.015 * s);
  c.beginPath(); c.ellipse(x, y + 0.01 * s, 0.6 * s, 0.07 * s, 0, 0, TAU); c.fill(); c.stroke();
  c.fillStyle = '#a77fd8'; c.beginPath(); c.ellipse(x, y - 0.005 * s, 0.5 * s, 0.045 * s, 0, 0, TAU); c.fill(); c.restore();
  shotgunOnGround(c, x - f * 0.9 * s, y, s);
  const breath = (Math.sin(t * 0.9) + 1) / 2, cyc = Math.floor(t / 4) % 2;
  c.save(); c.globalCompositeOperation = 'lighter';
  const g = c.createRadialGradient(x, y - 0.6 * s, 0, x, y - 0.6 * s, (0.7 + 0.3 * breath) * s); g.addColorStop(0, `rgba(200,170,255,${(0.25 * breath).toFixed(3)})`); g.addColorStop(1, 'rgba(200,170,255,0)');
  c.fillStyle = g; c.fillRect(x - s, y - 1.6 * s, 2 * s, 1.7 * s); c.restore();
  runner(c, x, y - breath * 0.02 * s, s * (1 + breath * 0.02), { pose: cyc ? 'cheer' : 'lean', lean: cyc ? 0 : -0.5 + breath * 0.2, face: 'smile', facing: f });
  for (let i = 0; i < 3; i++) {                                 // floating calm sparkles
    const ph = (t * 0.25 + i / 3) % 1, sx = x + Math.sin(t * 0.7 + i * 2) * 0.5 * s, sy = y - 0.4 * s - ph * 1.0 * s;
    c.globalAlpha = Math.sin(ph * Math.PI) * 0.8; c.fillStyle = '#e9dcff'; c.beginPath(); c.arc(sx, sy, 0.03 * s, 0, TAU); c.fill();
  }
  c.globalAlpha = 1;
}

function birds(c, x, y, s, t, f, runner) {
  // sitting on a tree stump, binoculars up, a flock crossing the sky; now and then one lands on his hat
  c.save(); c.translate(x - f * 0.05 * s, y);
  c.beginPath(); c.rect(-0.18 * s, -0.32 * s, 0.36 * s, 0.32 * s); inked(c, '#8a5a2b', Math.max(1, 0.015 * s));
  c.fillStyle = '#c99a5a'; c.beginPath(); c.ellipse(0, -0.32 * s, 0.18 * s, 0.05 * s, 0, 0, TAU); c.fill(); c.stroke();
  c.strokeStyle = '#8a5a2b'; c.lineWidth = Math.max(1, 0.008 * s); c.beginPath(); c.ellipse(0, -0.32 * s, 0.1 * s, 0.025 * s, 0, 0, TAU); c.stroke();
  c.restore();
  shotgunOnGround(c, x + f * 0.75 * s, y, s);
  runner(c, x, y - 0.22 * s, s, { pose: 'idle', lean: -0.15, face: 'ooh', facing: f });
  // binoculars at his eyes, pointed up at the birds
  const hx = x + f * 0.1 * s, hy = y - 1.13 * s;
  c.save(); c.translate(hx, hy); c.rotate(-0.5 * f);
  c.fillStyle = '#1d1d1f'; c.fillRect(0, -0.07 * s, 0.13 * s, 0.06 * s); c.fillRect(0, 0.01 * s, 0.13 * s, 0.06 * s);
  c.fillStyle = '#c99a3a'; c.fillRect(0.1 * s, -0.065 * s, 0.03 * s, 0.05 * s); c.fillRect(0.1 * s, 0.015 * s, 0.03 * s, 0.05 * s);
  c.restore();
  // the flock: wing-beating Vs drifting across
  for (let i = 0; i < 6; i++) {
    const ph = ((t * 0.06) + i * 0.035) % 1, bx = x - 5 * s + ph * 10 * s + (i % 3) * 0.3 * s, by = y - 3.2 * s - (i % 3) * 0.25 * s - Math.sin(t + i) * 0.1 * s;
    const wing = Math.sin(t * 9 + i) * 0.08 * s;
    c.strokeStyle = '#2a2230'; c.lineWidth = Math.max(1.5, 0.025 * s); c.lineCap = 'round';
    c.beginPath(); c.moveTo(bx - 0.14 * s, by - wing); c.quadraticCurveTo(bx - 0.06 * s, by - 0.06 * s, bx, by); c.quadraticCurveTo(bx + 0.06 * s, by - 0.06 * s, bx + 0.14 * s, by - wing); c.stroke();
  }
  if (Math.floor(t / 7) % 2 === 1) {                          // a little bird resting on his hat
    const by = y - 1.48 * s;
    c.fillStyle = '#4fa3d9'; c.beginPath(); c.ellipse(x, by, 0.07 * s, 0.05 * s, 0, 0, TAU); c.fill();
    c.beginPath(); c.arc(x + f * 0.06 * s, by - 0.04 * s, 0.035 * s, 0, TAU); c.fill();
    c.fillStyle = '#ffb33a'; c.beginPath(); c.moveTo(x + f * 0.095 * s, by - 0.045 * s); c.lineTo(x + f * 0.13 * s, by - 0.035 * s); c.lineTo(x + f * 0.095 * s, by - 0.025 * s); c.fill();
    c.fillStyle = '#111'; c.beginPath(); c.arc(x + f * 0.07 * s, by - 0.05 * s, 0.008 * s, 0, TAU); c.fill();
  }
}

function camp(c, x, y, s, t, f) {
  // a canvas tent, a crackling campfire, the Runner asleep in his sleeping bag, snoring
  const tx = x - f * 0.9 * s;
  c.save(); c.translate(tx, y);
  c.beginPath(); c.moveTo(-0.6 * s, 0); c.lineTo(0, -0.95 * s); c.lineTo(0.6 * s, 0); c.closePath(); inked(c, '#d9b46a', Math.max(1.5, 0.02 * s));
  c.beginPath(); c.moveTo(-0.16 * s, 0); c.lineTo(0, -0.62 * s); c.lineTo(0.16 * s, 0); c.closePath(); c.fillStyle = '#5a3a1e'; c.fill();
  c.strokeStyle = '#8a5a2b'; c.lineWidth = Math.max(1, 0.012 * s); c.beginPath(); c.moveTo(0, -0.95 * s); c.lineTo(0, -1.12 * s); c.stroke();
  c.fillStyle = '#d4183a'; c.beginPath(); c.moveTo(0, -1.12 * s); c.lineTo(0.18 * s, -1.06 * s); c.lineTo(0, -1.0 * s); c.fill();   // a pennant
  c.restore();
  // the campfire: logs, flames, sparks, a warm glow
  const fx = x + f * 0.75 * s;
  c.save(); c.globalCompositeOperation = 'lighter';
  const fl = 0.8 + 0.2 * Math.sin(t * 13) * Math.sin(t * 7.3);
  const g = c.createRadialGradient(fx, y - 0.2 * s, 0, fx, y - 0.2 * s, 1.3 * s * fl); g.addColorStop(0, 'rgba(255,170,60,0.45)'); g.addColorStop(1, 'rgba(255,120,40,0)');
  c.fillStyle = g; c.fillRect(fx - 1.4 * s, y - 1.5 * s, 2.8 * s, 1.6 * s); c.restore();
  c.save(); c.strokeStyle = '#5a3a1e'; c.lineWidth = 0.06 * s; c.lineCap = 'round';
  c.beginPath(); c.moveTo(fx - 0.2 * s, y - 0.02 * s); c.lineTo(fx + 0.2 * s, y - 0.08 * s); c.moveTo(fx - 0.2 * s, y - 0.08 * s); c.lineTo(fx + 0.2 * s, y - 0.02 * s); c.stroke();
  for (const [col, w, h] of [['#ff6a1f', 0.17, 0.42], ['#ffb12e', 0.12, 0.32], ['#fff0a0', 0.06, 0.18]]) {
    const hh = h * s * (0.85 + 0.25 * Math.sin(t * 11 + w * 20));
    c.fillStyle = col; c.beginPath(); c.moveTo(fx - w * s, y - 0.06 * s); c.quadraticCurveTo(fx - w * 0.6 * s, y - hh * 0.6, fx + Math.sin(t * 6) * 0.03 * s, y - 0.06 * s - hh); c.quadraticCurveTo(fx + w * 0.6 * s, y - hh * 0.6, fx + w * s, y - 0.06 * s); c.closePath(); c.fill();
  }
  for (let i = 0; i < 4; i++) { const ph = (t * 0.8 + i / 4) % 1; c.globalAlpha = 1 - ph; c.fillStyle = '#ffd36a'; c.fillRect(fx + Math.sin(t * 3 + i * 2) * 0.12 * s, y - 0.3 * s - ph * 0.9 * s, 0.025 * s, 0.025 * s); }
  c.globalAlpha = 1; c.restore();
  // the sleeping bag with him in it, breathing
  const br = (Math.sin(t * 1.3) + 1) / 2;
  c.save(); c.translate(x, y);
  c.beginPath(); c.ellipse(0, -0.11 * s - br * 0.01 * s, 0.55 * s, (0.13 + br * 0.012) * s, 0, 0, TAU); inked(c, '#3f7a52', Math.max(1.5, 0.02 * s));
  c.strokeStyle = '#2f5c3c'; c.lineWidth = Math.max(1, 0.01 * s); for (let i = -2; i <= 2; i++) { c.beginPath(); c.moveTo(i * 0.15 * s, -0.22 * s); c.lineTo(i * 0.15 * s, 0); c.stroke(); }
  const hx = -f * 0.5 * s;
  c.beginPath(); c.arc(hx, -0.16 * s, 0.13 * s, 0, TAU); inked(c, '#e8b892', Math.max(1, 0.015 * s));        // his head on a pillow
  c.fillStyle = '#6e4c2e'; c.beginPath(); c.arc(hx, -0.2 * s, 0.13 * s, Math.PI * 1.05, Math.PI * 1.95); c.fill();
  c.strokeStyle = '#2a1a10'; c.lineWidth = Math.max(1, 0.012 * s); c.beginPath(); c.moveTo(hx - 0.06 * s, -0.15 * s); c.lineTo(hx - 0.02 * s, -0.15 * s); c.moveTo(hx + 0.02 * s, -0.15 * s); c.lineTo(hx + 0.06 * s, -0.15 * s); c.stroke();
  c.restore();
  for (let i = 0; i < 3; i++) {                                  // Zzz
    const ph = ((t * 0.35) + i / 3) % 1;
    c.globalAlpha = Math.sin(ph * Math.PI) * 0.9; c.fillStyle = '#ffffff';
    c.font = `italic bold ${Math.round((0.16 + ph * 0.12) * s)}px Georgia, serif`; c.textAlign = 'center';
    c.fillText('z', x - f * 0.45 * s + f * ph * 0.35 * s, y - 0.4 * s - ph * 0.7 * s);
  }
  c.globalAlpha = 1;
  shotgunOnGround(c, x + f * 0.2 * s, y + 0.02 * s, s);
}

export const IDLE_KINDS = ['yoga', 'birds', 'camp'];
export function drawIdleScene(ctx, kind, x, y, s, t, f, runner, k = 1) {
  ctx.save();
  try {
    ctx.globalAlpha = ease(Math.max(0, Math.min(1, k)));
    if (kind === 'yoga') yoga(ctx, x, y, s, t, f, runner);
    else if (kind === 'birds') birds(ctx, x, y, s, t, f, runner);
    else camp(ctx, x, y, s, t, f);
  } catch (e) { if (!drawIdleScene._err) { drawIdleScene._err = true; console.error('drawIdleScene', e); } }
  ctx.restore();
}
