// cyclist.js - the two riders who take the Merchant's place (Zee 2026-11-04): "the user is not into calculations -> he should be focused
// on playing the game not calculating numbers -> the Cyclist can be of 2 kinds to show what he's offering: a baby girl on a pink bicycle
// offering beautiful icecream -> means profits (click her to book profit); an thief riding a bicycle looking to take your coin away shows
// if we click it he'll rob us". No number on either: the rider IS the answer. Clicking either sends the same 'merchant' order (close at
// market); main.js picks the rider from the round's live result (> 0 = the girl, otherwise the thief).
//
// drawCyclist(ctx, x, y, s, st): (x, y) = where the wheels touch the ground, s = px per unit (the Runner is 1 unit tall).
// st: { kind: 'girl' | 'thief', roll (wheel turns, radians), t, facing (+1 rides right), tackled 0..1 (caught: tipped over) }.

const TAU = Math.PI * 2;
let FACING = 1;
function inked(c, fill, lw = 0.025) { c.fillStyle = fill; c.fill(); c.strokeStyle = '#2a1a10'; c.lineWidth = lw; c.stroke(); }
function line(c, pts, col, w) { c.strokeStyle = '#2a1a10'; c.lineWidth = w + 0.03; c.lineCap = 'round'; c.lineJoin = 'round'; c.beginPath(); c.moveTo(pts[0], pts[1]); for (let i = 2; i < pts.length; i += 2) c.lineTo(pts[i], pts[i + 1]); c.stroke(); c.strokeStyle = col; c.lineWidth = w; c.stroke(); }

function wheel(c, x, y, r, roll, rim, spoke) {
  c.beginPath(); c.arc(x, y, r, 0, TAU); c.strokeStyle = '#2a1a10'; c.lineWidth = 0.05; c.stroke();
  c.strokeStyle = rim; c.lineWidth = 0.03; c.stroke();
  c.strokeStyle = spoke; c.lineWidth = 0.01;
  for (let i = 0; i < 6; i++) { const a = roll + (i / 6) * TAU; c.beginPath(); c.moveTo(x, y); c.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r); c.stroke(); }
  c.fillStyle = '#2a1a10'; c.beginPath(); c.arc(x, y, 0.025, 0, TAU); c.fill();
}

function bike(c, roll, frame, rim, small) {
  const r = small ? 0.17 : 0.21, wb = small ? 0.5 : 0.62;
  const bx = -wb / 2, fx = wb / 2, wy = -r;
  wheel(c, bx, wy, r, roll, rim, 'rgba(255,255,255,0.7)');
  wheel(c, fx, wy, r, roll, rim, 'rgba(255,255,255,0.7)');
  const seat = [-0.06, wy - 0.3], bar = [fx - 0.06, wy - 0.36], crank = [0.0, wy];
  line(c, [bx, wy, crank[0], crank[1], fx - 0.08, wy - 0.28, seat[0] + 0.02, seat[1] + 0.04, bx, wy], frame, 0.035);
  line(c, [crank[0], crank[1], seat[0], seat[1]], frame, 0.035);
  line(c, [fx, wy, fx - 0.08, wy - 0.28, bar[0], bar[1]], frame, 0.035);
  c.beginPath(); c.ellipse(seat[0], seat[1] - 0.01, 0.08, 0.025, 0, 0, TAU); inked(c, '#2a1a10', 0.01);
  line(c, [bar[0] - 0.04, bar[1], bar[0] + 0.08, bar[1] - 0.03], '#444', 0.025);
  // pedals turning with the wheels
  const pa = roll * 0.8;
  line(c, [crank[0] + Math.cos(pa) * 0.08, crank[1] + Math.sin(pa) * 0.08, crank[0] - Math.cos(pa) * 0.08, crank[1] - Math.sin(pa) * 0.08], '#555', 0.02);
  return { seat, bar, crank, pa, wy, fx, bx };
}

function drawGirl(c, roll, t) {
  const B = bike(c, roll, '#ff7fb6', '#ffd1e6', true);
  // a basket of flowers on the handlebars
  c.beginPath(); c.moveTo(B.fx - 0.02, B.bar[1] + 0.02); c.lineTo(B.fx + 0.16, B.bar[1] + 0.02); c.lineTo(B.fx + 0.13, B.bar[1] + 0.13); c.lineTo(B.fx + 0.01, B.bar[1] + 0.13); c.closePath(); inked(c, '#d9a35c', 0.015);
  for (let i = 0; i < 3; i++) { c.fillStyle = ['#ff8fb3', '#ffe066', '#ffffff'][i]; c.beginPath(); c.arc(B.fx + 0.03 + i * 0.05, B.bar[1] + 0.0, 0.03, 0, TAU); c.fill(); }
  // legs pedalling
  const k1 = [B.crank[0] + Math.cos(B.pa) * 0.08, B.crank[1] + Math.sin(B.pa) * 0.08], k2 = [B.crank[0] - Math.cos(B.pa) * 0.08, B.crank[1] - Math.sin(B.pa) * 0.08];
  const hip = [B.seat[0], B.seat[1] - 0.04];
  line(c, [hip[0], hip[1], hip[0] + 0.1, hip[1] + 0.12, k1[0], k1[1]], '#f6c9a8', 0.045);
  line(c, [hip[0], hip[1], hip[0] + 0.08, hip[1] + 0.13, k2[0], k2[1]], '#f6c9a8', 0.045);
  // a pink dress with white polka dots
  c.beginPath(); c.moveTo(hip[0] - 0.1, hip[1] + 0.04); c.lineTo(hip[0] + 0.14, hip[1] + 0.04); c.lineTo(hip[0] + 0.06, hip[1] - 0.3); c.lineTo(hip[0] - 0.04, hip[1] - 0.3); c.closePath(); inked(c, '#ff5fa2');
  c.fillStyle = '#ffffff'; for (const [dx, dy] of [[-0.03, -0.05], [0.06, -0.02], [0.01, -0.16], [0.07, -0.12]]) { c.beginPath(); c.arc(hip[0] + dx, hip[1] + dy, 0.012, 0, TAU); c.fill(); }
  // one arm on the bars, the other holding up a big ice-cream cone toward the Runner
  line(c, [hip[0] + 0.03, hip[1] - 0.26, B.bar[0] + 0.02, B.bar[1]], '#f6c9a8', 0.04);
  const wave = Math.sin(t * 4) * 0.03, hand = [hip[0] + 0.2, hip[1] - 0.48 + wave];
  line(c, [hip[0] + 0.03, hip[1] - 0.27, hip[0] + 0.14, hip[1] - 0.36, hand[0], hand[1]], '#f6c9a8', 0.04);
  c.save(); c.translate(hand[0] + 0.02, hand[1]);
  c.beginPath(); c.moveTo(-0.045, -0.03); c.lineTo(0.045, -0.03); c.lineTo(0, 0.13); c.closePath(); inked(c, '#e3a85b', 0.015);
  c.strokeStyle = '#b97c35'; c.lineWidth = 0.008; c.beginPath(); c.moveTo(-0.03, 0.0); c.lineTo(0.02, 0.06); c.moveTo(0.03, 0.0); c.lineTo(-0.02, 0.06); c.stroke();
  c.beginPath(); c.arc(0, -0.06, 0.06, 0, TAU); inked(c, '#ffb3cf', 0.015);           // strawberry
  c.beginPath(); c.arc(0.01, -0.13, 0.05, 0, TAU); inked(c, '#fff3d6', 0.015);         // vanilla
  c.fillStyle = '#d4183a'; c.beginPath(); c.arc(0.02, -0.19, 0.022, 0, TAU); c.fill();   // a cherry on top
  for (let i = 0; i < 4; i++) { c.fillStyle = ['#7ad3ff', '#ffe066', '#9be37a', '#ff8fb3'][i]; c.fillRect(-0.03 + i * 0.02, -0.12 + (i % 2) * 0.03, 0.012, 0.006); }
  c.restore();
  // head: rosy cheeks, a big smile, pigtails with bows
  c.save(); c.translate(hip[0] + 0.03, hip[1] - 0.42);
  for (const sx of [-1, 1]) { c.fillStyle = '#6b3b1e'; c.beginPath(); c.ellipse(sx * 0.12, 0.03, 0.04, 0.07, sx * 0.4, 0, TAU); c.fill(); c.fillStyle = '#ff5fa2'; c.beginPath(); c.moveTo(sx * 0.1, -0.03); c.lineTo(sx * 0.16, -0.07); c.lineTo(sx * 0.16, 0.0); c.closePath(); c.fill(); }
  c.beginPath(); c.arc(0, 0, 0.11, 0, TAU); inked(c, '#f6c9a8', 0.02);
  c.fillStyle = '#6b3b1e'; c.beginPath(); c.arc(0, -0.03, 0.11, Math.PI * 1.05, Math.PI * 1.95); c.fill();
  c.fillStyle = '#2a1a10'; c.beginPath(); c.arc(0.02, 0.0, 0.014, 0, TAU); c.arc(0.07, 0.0, 0.014, 0, TAU); c.fill();
  c.fillStyle = '#ff9db8'; c.beginPath(); c.arc(-0.01, 0.04, 0.02, 0, TAU); c.arc(0.09, 0.04, 0.02, 0, TAU); c.fill();
  c.strokeStyle = '#2a1a10'; c.lineWidth = 0.012; c.beginPath(); c.arc(0.045, 0.04, 0.03, 0.1 * Math.PI, 0.9 * Math.PI); c.stroke();
  c.restore();
  // little hearts floating up
  for (let i = 0; i < 2; i++) {
    const ph = (t * 0.6 + i * 0.5) % 1, hx = hip[0] + 0.3 + Math.sin(t * 2 + i) * 0.05, hy = hip[1] - 0.6 - ph * 0.4;
    c.globalAlpha = 1 - ph; c.fillStyle = '#ff5f8f';
    c.beginPath(); c.moveTo(hx, hy + 0.03); c.bezierCurveTo(hx - 0.06, hy - 0.02, hx - 0.02, hy - 0.06, hx, hy - 0.025); c.bezierCurveTo(hx + 0.02, hy - 0.06, hx + 0.06, hy - 0.02, hx, hy + 0.03); c.fill();
  }
  c.globalAlpha = 1;
}

function drawThief(c, roll, t) {
  const B = bike(c, roll, '#2f3338', '#555b63', false);
  const k1 = [B.crank[0] + Math.cos(B.pa) * 0.08, B.crank[1] + Math.sin(B.pa) * 0.08], k2 = [B.crank[0] - Math.cos(B.pa) * 0.08, B.crank[1] - Math.sin(B.pa) * 0.08];
  const hip = [B.seat[0], B.seat[1] - 0.04];
  line(c, [hip[0], hip[1], hip[0] + 0.13, hip[1] + 0.12, k1[0], k1[1]], '#2b2b33', 0.06);
  line(c, [hip[0], hip[1], hip[0] + 0.11, hip[1] + 0.14, k2[0], k2[1]], '#2b2b33', 0.06);
  // a sack of loot on his back with a big $
  c.beginPath(); c.ellipse(hip[0] - 0.17, hip[1] - 0.32, 0.14, 0.17, -0.3, 0, TAU); inked(c, '#b89a6a');
  c.save(); c.translate(hip[0] - 0.17, hip[1] - 0.31); c.scale(FACING, 1); c.fillStyle = '#5a4524'; c.font = 'bold 0.16px Georgia, serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('$', 0, 0.005); c.restore();
  // striped jumper, hunched forward
  c.beginPath(); c.moveTo(hip[0] - 0.1, hip[1] + 0.02); c.lineTo(hip[0] + 0.12, hip[1]); c.lineTo(hip[0] + 0.18, hip[1] - 0.38); c.lineTo(hip[0] - 0.02, hip[1] - 0.42); c.closePath(); inked(c, '#f2f2f2');
  c.save(); c.clip(); c.fillStyle = '#1d1d22'; for (let yy = hip[1] - 0.42; yy < hip[1] + 0.05; yy += 0.08) c.fillRect(hip[0] - 0.2, yy, 0.45, 0.04); c.restore();
  // one hand on the bars, the other reaching out with grabbing fingers
  line(c, [hip[0] + 0.15, hip[1] - 0.35, B.bar[0] + 0.02, B.bar[1]], '#1d1d22', 0.05);
  const grab = Math.sin(t * 7) * 0.02;
  line(c, [hip[0] + 0.15, hip[1] - 0.36, hip[0] + 0.32, hip[1] - 0.42, hip[0] + 0.46, hip[1] - 0.47 + grab], '#1d1d22', 0.05);
  c.strokeStyle = '#e8b892'; c.lineWidth = 0.02; c.lineCap = 'round';
  for (let i = -1; i <= 1; i++) { c.beginPath(); c.moveTo(hip[0] + 0.47, hip[1] - 0.47 + grab); c.quadraticCurveTo(hip[0] + 0.54, hip[1] - 0.5 + i * 0.03 + grab, hip[0] + 0.53, hip[1] - 0.44 + i * 0.03 + grab); c.stroke(); }
  // head: stubble, a black eye mask, a flat cap, a sly grin
  c.save(); c.translate(hip[0] + 0.15, hip[1] - 0.52);
  c.beginPath(); c.arc(0, 0, 0.11, 0, TAU); inked(c, '#e8b892', 0.02);
  c.fillStyle = 'rgba(60,50,40,0.35)'; c.beginPath(); c.arc(0.02, 0.05, 0.08, 0.1 * Math.PI, 0.9 * Math.PI); c.fill();
  c.fillStyle = '#111'; c.beginPath(); c.moveTo(-0.11, -0.02); c.lineTo(0.12, -0.03); c.lineTo(0.12, 0.03); c.lineTo(-0.11, 0.03); c.closePath(); c.fill();
  c.fillStyle = '#fff'; c.beginPath(); c.arc(0.03, 0.0, 0.016, 0, TAU); c.arc(0.08, 0.0, 0.016, 0, TAU); c.fill();
  c.fillStyle = '#111'; const look = Math.sin(t * 2) * 0.006; c.beginPath(); c.arc(0.035 + look, 0.0, 0.008, 0, TAU); c.arc(0.085 + look, 0.0, 0.008, 0, TAU); c.fill();
  c.strokeStyle = '#2a1a10'; c.lineWidth = 0.012; c.beginPath(); c.moveTo(0.01, 0.06); c.quadraticCurveTo(0.06, 0.09, 0.1, 0.05); c.stroke();
  c.beginPath(); c.moveTo(-0.12, -0.05); c.quadraticCurveTo(-0.05, -0.16, 0.1, -0.1); c.lineTo(0.18, -0.06); c.lineTo(-0.12, -0.04); c.closePath(); inked(c, '#3a3d44', 0.015);
  c.restore();
}

export function drawCyclist(ctx, x, y, s, st = {}) {
  const c = ctx, f = st.facing < 0 ? -1 : 1, t = +st.t || 0, roll = +st.roll || 0, tk = Math.max(0, Math.min(1, +st.tackled || 0));
  c.save();
  try {
    FACING = f;
    c.translate(x, y); c.scale(f * s, s);
    if (tk > 0) { c.rotate(-0.9 * tk); }
    else c.translate(0, -Math.abs(Math.sin(roll * 0.5)) * 0.01);
    if (st.kind === 'girl') drawGirl(c, roll, t); else drawThief(c, roll, t);
  } catch (e) {
    if (!drawCyclist._err) { drawCyclist._err = true; console.error('drawCyclist', e); }
  }
  c.restore();
}
