// buyer2.js - the Buyer: a mafia boss at his table (Zee 2026-11-04): "he shouldn't be this fat -> he should be a mafia boss sitting on a
// table smoking a cigar waiting for us to come to him to sell gold .. if we're to say this is profit instead of writing numbers in red, we
// must write them in green and put it as a signboard from the mafia boss (a big bigger sign symbolising this is where we want to reach) and
// the mafia boss should have his people try to help us by calling us over encouraging us etc.."
//
// A slim boss in a black pinstripe suit and fedora sits at a little round table (whiskey, a stack of cash), cigar glowing, smoke curling.
// Behind him his big signboard shows, in green, the profit waiting at the target. Two of his men stand on the hill toward the Runner: one
// waves him over with both arms, the other cups a hand to his mouth calling and points at the boss. They cheer when the Runner is close,
// shrug when the price falls, and throw cash when the boss pays.
//
// drawHumanBuyer(ctx, x, y, s, st) -> points. (x, y) = the boss's spot on the walking line, s = px per unit (the Runner is 1 unit tall).
// st: { t, facing (+1 = local +x points toward the Runner; main.js passes -L.facing), mood, profit (text, e.g. "+$0.012"),
//       groundAt(px) -> y (the walking line at a screen x, so his men stand on the slope) }.
// moods: wait, inspect (the Runner is close), tap (price falling), laugh (haggle accepted), shake_head (haggle refused), wave_off, pay.

const TAU = Math.PI * 2;
export const HUMAN_BUYER_PTS = { tagX: 0, tagY: 0, tagR: 0, gunX: 0, gunY: 0, holeX: NaN, holeY: NaN, holeAng: 0, holeF: 1, box: null, goonX: NaN, goonY: NaN, bossX: NaN, bossY: NaN };
let FACING = 1, REACH = 0, INJURED = false;

function inked(c, fill, lw = 0.025) { c.fillStyle = fill; c.fill(); c.strokeStyle = '#1a1210'; c.lineWidth = lw; c.stroke(); }
function rr(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }
function limb(c, pts, col, w) { c.strokeStyle = '#1a1210'; c.lineWidth = w + 0.03; c.lineCap = 'round'; c.lineJoin = 'round'; c.beginPath(); c.moveTo(pts[0], pts[1]); for (let i = 2; i < pts.length; i += 2) c.lineTo(pts[i], pts[i + 1]); c.stroke(); c.strokeStyle = col; c.lineWidth = w; c.stroke(); }
function text(c, str, x, y, px, col, weight = 'bold') { c.save(); c.translate(x, y); c.scale(FACING, 1); c.font = `${weight} ${px}px "Playfair Display", Georgia, serif`; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillStyle = col; c.fillText(str, 0, 0); c.restore(); }
function bill(c, x, y, ang) { c.save(); c.translate(x, y); c.rotate(ang); rr(c, -0.1, -0.045, 0.2, 0.09, 0.01); inked(c, '#7fbf6a', 0.01); c.fillStyle = '#3f7a35'; c.beginPath(); c.arc(0, 0, 0.02, 0, TAU); c.fill(); c.restore(); }
function fedora(c, x, y, sc, band = '#7a1d24') {
  c.save(); c.translate(x, y); c.scale(sc, sc);
  c.beginPath(); c.ellipse(0, 0, 0.19, 0.04, 0, 0, TAU); inked(c, '#1b1b20', 0.02);
  c.beginPath(); c.moveTo(-0.12, 0); c.quadraticCurveTo(-0.13, -0.16, -0.03, -0.15); c.lineTo(0, -0.12); c.lineTo(0.03, -0.15); c.quadraticCurveTo(0.13, -0.16, 0.12, 0); c.closePath(); inked(c, '#232329', 0.02);
  c.fillStyle = band; c.fillRect(-0.12, -0.05, 0.24, 0.035);
  c.restore();
}
function face(c, x, y, skin, opts = {}) {
  c.save(); c.translate(x, y);
  c.beginPath(); c.ellipse(0, 0, 0.1, 0.12, 0, 0, TAU); inked(c, skin, 0.02);
  if (opts.glasses) { c.fillStyle = '#111'; rr(c, 0.0, -0.035, 0.06, 0.035, 0.01); c.fill(); rr(c, 0.065, -0.035, 0.035, 0.035, 0.01); c.fill(); c.fillRect(-0.02, -0.025, 0.12, 0.008); }
  else { c.fillStyle = '#1a1210'; c.beginPath(); c.arc(0.035, -0.02, 0.012, 0, TAU); c.arc(0.08, -0.02, 0.012, 0, TAU); c.fill(); }
  if (opts.moustache) { c.fillStyle = '#2a1d16'; c.beginPath(); c.ellipse(0.05, 0.04, 0.045, 0.014, 0, 0, TAU); c.fill(); }
  c.strokeStyle = '#1a1210'; c.lineWidth = 0.012; c.beginPath();
  if (opts.open) c.ellipse(0.055, 0.07, 0.025, 0.02 + 0.01 * Math.abs(Math.sin(opts.t * 8)), 0, 0, TAU);
  else if (opts.frown) c.arc(0.05, 0.1, 0.03, 1.15 * Math.PI, 1.85 * Math.PI);
  else c.arc(0.05, 0.05, 0.03, 0.15 * Math.PI, 0.85 * Math.PI);
  c.stroke();
  c.restore();
}

// one of his men: black suit, fedora, standing; pose 'wave' (both arms over the head), 'call' (hand to mouth, pointing at the boss),
// 'cheer' (fists up, jumping), 'shrug', 'throw' (tossing bills)
function drawGoon(c, t, pose, seed, kp = 1) {
  const jump = pose === 'cheer' || pose === 'throw' ? Math.abs(Math.sin(t * 8 + seed)) * 0.08 : 0;
  c.save(); c.translate(0, -jump);
  const knocked = pose === 'knocked', ke = kp * kp * (3 - 2 * kp);
  if (knocked) { c.translate(-0.1 - ke * 0.15, 0); c.rotate(-1.3 * ke); pose = 'shrug'; }
  else { c.translate(Math.sin(t * 0.6 + seed) * 0.012, -Math.sin(t * 1.5 + seed) * 0.008); c.rotate(Math.sin(t * 0.6 + seed) * 0.015); }   // breathing, shifting his weight
  if (pose === 'reach' || pose === 'reach2') c.rotate(0.05 + 0.12 * REACH);     // leaning in toward the Runner
  limb(c, [-0.06, -0.55, -0.07, -0.04], '#18181d', 0.1); limb(c, [0.06, -0.55, 0.08, -0.04], '#18181d', 0.1);
  c.fillStyle = '#0d0d0d'; c.beginPath(); c.ellipse(-0.05, -0.02, 0.09, 0.035, 0, 0, TAU); c.ellipse(0.1, -0.02, 0.09, 0.035, 0, 0, TAU); c.fill();
  c.beginPath(); c.moveTo(-0.17, -0.52); c.quadraticCurveTo(-0.2, -0.98, -0.12, -1.04); c.lineTo(0.12, -1.04); c.quadraticCurveTo(0.2, -0.98, 0.17, -0.52); c.closePath(); inked(c, '#1f1f26');
  c.beginPath(); c.moveTo(-0.05, -1.04); c.lineTo(0, -0.86); c.lineTo(0.05, -1.04); c.closePath(); inked(c, '#efefef', 0.012);
  c.fillStyle = '#111'; c.fillRect(-0.015, -1.0, 0.03, 0.12);
  const skin = seed % 2 ? '#d9a882' : '#e9bf9b';
  let w = Math.sin(t * 7 + seed);
  let L, R;
  if (pose === 'wave') { L = [-0.15, -0.98, -0.3 + w * 0.06, -1.25, -0.22 + w * 0.1, -1.45]; R = [0.15, -0.98, 0.3 - w * 0.06, -1.25, 0.24 - w * 0.1, -1.45]; }
  else if (pose === 'call') { L = [-0.15, -0.98, -0.32, -0.95, -0.55, -1.0]; R = [0.15, -0.98, 0.18, -0.88, 0.12, -1.07]; }   // L points back at the boss
  else if (pose === 'cheer') { L = [-0.15, -0.98, -0.25, -1.2, -0.2, -1.42]; R = [0.15, -0.98, 0.25, -1.2, 0.2, -1.42]; }
  else if (pose === 'reach') { const e = REACH; R = [0.15, -0.98, 0.33 + 0.08 * e, -0.86, 0.47 + 0.14 * e + w * 0.008, -0.76]; L = [-0.15, -0.98, -0.27, -0.82, -0.15, -0.64]; }   // the free hand on his hip, so his partner's reach over his shoulder shows
  else if (pose === 'reach2') { const e = REACH; R = [0.15, -0.98, 0.42 + 0.06 * e, -1.2, 0.64 + 0.12 * e + w * 0.008, -1.3]; L = [-0.15, -0.98, -0.3, -0.92, -0.34, -1.05]; }   // over his partner's shoulder
  else if (pose === 'throw') { L = [-0.15, -0.98, -0.28, -1.15, -0.25, -1.4]; R = [0.15, -0.98, 0.32, -1.18, 0.35 + w * 0.05, -1.38]; }
  else if (pose === 'aim') { L = [-0.15, -0.98, -0.28, -0.9, -0.3, -0.75]; R = [0.15, -0.98, 0.36, -1.0, 0.56, -1.02]; w = 0; }   // a pistol levelled at the Runner
  else if (pose === 'guard') { L = [-0.15, -0.98, 0.05, -0.86, 0.14, -0.9]; R = [0.15, -0.98, -0.04, -0.84, -0.12, -0.88]; w = 0; }   // arms folded, guarding the cash
  else { L = [-0.15, -0.98, -0.3, -0.92, -0.32, -1.08]; R = [0.15, -0.98, 0.3, -0.92, 0.32, -1.08]; }               // shrug
  limb(c, L, '#1f1f26', 0.09); limb(c, R, '#1f1f26', 0.09);
  for (const H of [L, R]) { c.fillStyle = skin; c.beginPath(); c.arc(H[4], H[5], 0.045, 0, TAU); c.fill(); }
  if (pose === 'aim') { c.fillStyle = '#1d1d22'; c.fillRect(R[4] - 0.01, R[5] - 0.035, 0.15, 0.04); c.fillRect(R[4] - 0.01, R[5] - 0.01, 0.04, 0.07); }
  if (pose === 'reach' || pose === 'reach2') {                   // an open hand, fingers stretching out toward the Runner
    c.strokeStyle = skin; c.lineWidth = 0.022; c.lineCap = 'round';
    for (let i = -1; i <= 1; i++) { const wig = Math.sin(t * 9 + i * 1.3 + seed) * 0.012; c.beginPath(); c.moveTo(R[4] + 0.02, R[5] + i * 0.018); c.lineTo(R[4] + 0.075 + wig, R[5] + i * 0.03 - 0.005); c.stroke(); }
    c.beginPath(); c.moveTo(R[4], R[5] - 0.02); c.lineTo(R[4] + 0.03, R[5] - 0.055); c.stroke();
  }
  if (pose === 'throw') for (let i = 0; i < 3; i++) { const ph = (t * 1.5 + i / 3 + seed * 0.2) % 1; bill(c, R[4] + ph * 0.3, R[5] - ph * 0.5 + ph * ph * 0.6, t * 6 + i); }
  face(c, 0.01, -1.17, skin, { glasses: seed % 2 === 1, moustache: seed % 2 === 0, open: pose === 'call' || pose === 'cheer' || pose === 'wave', frown: pose === 'shrug', t });
  if (!knocked) fedora(c, 0.01, -1.27, 0.85, '#333');
  if (INJURED) {                          // shot during the robbery: a bandage round the head, a plaster on the cheek
    c.fillStyle = '#f4f1ea'; c.fillRect(-0.105, -1.235, 0.22, 0.045); c.fillStyle = '#c4242f'; c.beginPath(); c.arc(-0.04, -1.215, 0.016, 0, TAU); c.fill();
    c.save(); c.translate(0.07, -1.13); c.rotate(0.5); c.fillStyle = '#e8cfa4'; c.fillRect(-0.03, -0.012, 0.06, 0.024); c.restore();
  }
  if (knocked) {                                   // his fedora flies off and rolls away
    c.restore(); c.save();
    const k2 = Math.min(1, kp); fedora(c, -0.2 - k2 * 0.4, -1.27 + k2 * 1.25 - Math.sin(k2 * Math.PI) * 0.4, 0.85, '#333');
    c.restore(); c.save(); c.translate(-0.1 - ke * 0.15, 0); c.rotate(-1.3 * ke);
  }
  if (knocked) { for (let i = 0; i < 4; i++) { const a = t * 5 + i * (TAU / 4), sx = Math.cos(a) * 0.18, sy = -1.42 + Math.sin(a) * 0.06; c.fillStyle = '#ffe14d'; c.beginPath(); for (let j = 0; j < 10; j++) { const aa = (j / 10) * TAU - Math.PI / 2, r = j % 2 ? 0.018 : 0.045; c.lineTo(sx + Math.cos(aa) * r, sy + Math.sin(aa) * r); } c.closePath(); c.fill(); } }
  if (pose === 'call') {                                          // sound arcs from the cupped hand: "over here!"
    c.strokeStyle = 'rgba(255,255,255,0.85)'; c.lineWidth = 0.018; c.lineCap = 'round';
    for (let i = 0; i < 3; i++) { const ph = (t * 1.6 + i / 3) % 1, r = 0.1 + ph * 0.3; c.globalAlpha = 1 - ph; c.beginPath(); c.arc(0.12, -1.12, r, -0.5, 0.5); c.stroke(); }
    c.globalAlpha = 1;
  }
  c.restore();
}

export function drawHumanBuyer(ctx, x, y, s, st = {}) {
  const t = +st.t || 0, f = st.facing < 0 ? -1 : 1, mood = st.mood || 'wait';
  const P = HUMAN_BUYER_PTS, c = ctx;
  FACING = f; REACH = Math.max(0, Math.min(1, +st.reach || 0)); INJURED = !!st.injured;
  const gAt = (px) => { const v = typeof st.groundAt === 'function' ? st.groundAt(px) : y; return isFinite(v) ? v : y; };
  const BX = -1.75, bx0 = x + f * BX * s, by0 = gAt(bx0);             // the boss's group stands back from the hand-off point
  const toS = (ux, uy) => [bx0 + f * ux * s, by0 + uy * s];
  const paying = mood === 'pay', close = mood === 'inspect' || mood === 'laugh', falling = mood === 'tap', refused = mood === 'shake_head' || mood === 'wave_off';
  c.save();
  try {
    // ---- the big signboard behind the boss: the green profit waiting here (not when they are being robbed: then the bank is the goal)
    if (!st.robbed) {
    c.save(); c.translate(bx0, by0); c.scale(f * s, s);
    const SX = -0.55, SY = -2.15, SW = 1.7, SH = 0.72;
    for (const px of [SX - SW * 0.32, SX + SW * 0.32]) { c.beginPath(); c.rect(px - 0.04, SY + SH - 0.02, 0.08, -SY - SH + 0.02); inked(c, '#5a3a1e', 0.015); }
    c.save(); c.translate(SX, SY + SH / 2); c.rotate(Math.sin(t * 0.8) * 0.012);
    const glowA = 0.25 + 0.15 * Math.sin(t * 3);
    c.shadowColor = `rgba(80,255,140,${glowA.toFixed(3)})`; c.shadowBlur = 0.35 * s;
    rr(c, -SW / 2, -SH / 2, SW, SH, 0.06); inked(c, '#123d22', 0.04); c.shadowBlur = 0;
    rr(c, -SW / 2 + 0.06, -SH / 2 + 0.06, SW - 0.12, SH - 0.12, 0.04); c.strokeStyle = '#e8c35a'; c.lineWidth = 0.025; c.stroke();
    for (let i = 0; i < 14; i++) { const a = i / 14; const bx = -SW / 2 + 0.03 + a * (SW - 0.06); c.fillStyle = (Math.floor(t * 4) + i) % 2 ? '#fff6b0' : '#c9a23a'; c.beginPath(); c.arc(bx, -SH / 2 + 0.03, 0.018, 0, TAU); c.arc(bx, SH / 2 - 0.03, 0.018, 0, TAU); c.fill(); }
    text(c, st.profit || '', 0, 0.02, 0.36, '#5dff8f');
    c.restore();
    c.restore();
    { const [tx, ty] = toS(SX, SY + SH / 2); P.tagX = tx; P.tagY = ty; P.tagR = 0.75 * s; }   // the haggle target
    }
    // ---- the prize: the vehicle the player picked, parked under the sign with a red bow (main.js draws it by the Runner once paid)
    if (st.vehicle && typeof st.drawVehicle === 'function' && !st.prizeTaken && !st.robbed) {
      const [vx, vy] = toS(-1.3, 0);
      st.drawVehicle(c, st.vehicle, vx, vy, s, { t, scale: st.vehicle === 'heli' ? 0.75 : 0.8, facing: -f, bow: true, shine: 0.5 });
    }
    // ---- the boss at his table
    c.save(); c.translate(bx0, by0); c.scale(f * s, s);
    // chair (behind him)
    c.strokeStyle = '#3a2412'; c.lineWidth = 0.05; c.lineCap = 'round';
    c.beginPath(); c.moveTo(-0.32, 0); c.lineTo(-0.3, -0.48); c.lineTo(-0.36, -1.0); c.moveTo(-0.02, 0); c.lineTo(-0.04, -0.48); c.stroke();
    rr(c, -0.36, -0.52, 0.36, 0.06, 0.02); inked(c, '#7a1d24', 0.015);
    // body seated: slim black pinstripe suit, legs crossed under the table
    limb(c, [-0.18, -0.52, 0.12, -0.5, 0.14, -0.06], '#1b1b22', 0.1);
    limb(c, [-0.12, -0.5, 0.18, -0.6, 0.3, -0.42], '#1b1b22', 0.1);
    c.fillStyle = '#0d0d0d'; c.beginPath(); c.ellipse(0.2, -0.03, 0.09, 0.035, 0, 0, TAU); c.ellipse(0.36, -0.4, 0.08, 0.035, -0.5, 0, TAU); c.fill();
    const lean = close ? 0.06 : 0, lb = paying ? Math.abs(Math.sin(t * 8)) * 0.03 : 0;
    c.save(); c.translate(lean, -lb);
    c.beginPath(); c.moveTo(-0.27, -0.52); c.quadraticCurveTo(-0.28, -0.98, -0.2, -1.05); c.lineTo(-0.0, -1.05); c.quadraticCurveTo(0.06, -0.98, 0.04, -0.52); c.closePath(); inked(c, '#1b1b22');
    c.save(); c.clip(); c.strokeStyle = 'rgba(255,255,255,0.14)'; c.lineWidth = 0.007; for (let xx = -0.28; xx < 0.06; xx += 0.04) { c.beginPath(); c.moveTo(xx, -1.06); c.lineTo(xx, -0.5); c.stroke(); } c.restore();
    c.beginPath(); c.moveTo(-0.14, -1.05); c.lineTo(-0.09, -0.86); c.lineTo(-0.04, -1.05); c.closePath(); inked(c, '#f2f2f2', 0.012);
    c.fillStyle = '#9e1b28'; c.fillRect(-0.105, -1.02, 0.03, 0.14);
    c.fillStyle = '#f2f2f2'; c.beginPath(); c.moveTo(-0.24, -0.96); c.lineTo(-0.2, -0.99); c.lineTo(-0.19, -0.94); c.closePath(); c.fill();   // pocket square
    // arms: one on the table (tapping, or wagging a finger, or throwing cash), one holding the cigar
    const tapY = Math.abs(Math.sin(t * (falling ? 9 : 2))) * 0.02;
    let hand = [0.36, -0.66 - tapY];
    if (paying) hand = [0.42, -1.25];
    else if (refused) hand = [0.3, -1.05 + Math.sin(t * 14) * 0.03];
    else if (falling) hand = [0.05, -0.95];                             // checks his watch
    limb(c, [-0.04, -0.98, 0.16, -0.78, hand[0], hand[1]], '#1b1b22', 0.08);
    c.fillStyle = '#e2b48f'; c.beginPath(); c.arc(hand[0], hand[1], 0.04, 0, TAU); c.fill();
    c.fillStyle = '#e8c35a'; c.beginPath(); c.arc(hand[0] + 0.01, hand[1] + 0.01, 0.014, 0, TAU); c.fill();   // a gold ring
    if (paying) for (let i = 0; i < 4; i++) bill(c, hand[0] + 0.05 + i * 0.03, hand[1] - 0.05 - (i % 2) * 0.04, t * 5 + i);
    { const [gx, gy] = toS(hand[0], hand[1]); P.gunX = gx; P.gunY = gy; }
    const cigH = [0.02, -1.2];
    limb(c, [-0.2, -0.98, -0.02, -0.98, cigH[0], cigH[1]], '#1b1b22', 0.08);
    c.fillStyle = '#e2b48f'; c.beginPath(); c.arc(cigH[0], cigH[1], 0.04, 0, TAU); c.fill();
    // head: slim face, slicked hair, sunglasses, the fedora
    face(c, -0.08, -1.18, '#e2b48f', { glasses: true, moustache: true, open: mood === 'laugh' || paying, frown: refused || falling, t });
    fedora(c, -0.08, -1.28, 1.0);
    // the cigar in his mouth: glowing tip, curling smoke
    const pull = (Math.sin(t * 0.9) + 1) / 2;
    c.save(); c.translate(-0.02, -1.13); c.rotate(-0.15);
    rr(c, 0, -0.012, 0.15, 0.026, 0.01); inked(c, '#6b4423', 0.01);
    c.fillStyle = '#c8a46a'; c.fillRect(0.02, -0.012, 0.02, 0.026);
    c.fillStyle = `rgba(255,${(90 + 100 * pull) | 0},40,1)`; c.beginPath(); c.arc(0.152, 0.001, 0.016, 0, TAU); c.fill();
    c.restore();
    for (let i = 0; i < 2; i++) {                    // every few seconds he blows a smoke ring that drifts up and widens
      const ph = (t * 0.22 + i * 0.5) % 1; c.globalAlpha = 0.55 * (1 - ph); c.strokeStyle = '#ededf2'; c.lineWidth = 0.025 * (1 - ph * 0.5);
      c.beginPath(); c.ellipse(0.12 + ph * 0.25, -1.18 - ph * 0.9, 0.04 + ph * 0.12, 0.02 + ph * 0.05, 0.2, 0, TAU); c.stroke();
    }
    c.globalAlpha = 1;
    for (let i = 0; i < 6; i++) {
      const ph = (t * 0.3 + i / 6) % 1, sx = 0.14 + Math.sin(t * 1.2 + i * 1.7) * 0.06 * ph + ph * 0.1, sy = -1.15 - ph * 0.75;
      c.globalAlpha = 0.5 * (1 - ph); c.fillStyle = '#e8e8ec'; c.beginPath(); c.arc(sx, sy, 0.03 + ph * 0.1, 0, TAU); c.fill();
    }
    c.globalAlpha = 1;
    c.restore();
    // the little round table in front of him: whiskey, a stack of cash, a pile of gold coins
    c.strokeStyle = '#1a1210'; c.lineWidth = 0.06; c.beginPath(); c.moveTo(0.42, 0); c.lineTo(0.42, -0.68); c.stroke();
    c.strokeStyle = '#3a2412'; c.lineWidth = 0.035; c.stroke();
    c.beginPath(); c.ellipse(0.42, -0.02, 0.16, 0.035, 0, 0, TAU); inked(c, '#3a2412', 0.015);
    c.beginPath(); c.ellipse(0.42, -0.7, 0.3, 0.06, 0, 0, TAU); inked(c, '#5c3520', 0.02);
    rr(c, 0.22, -0.82, 0.14, 0.1, 0.01); inked(c, '#86c46f', 0.01); c.fillStyle = '#f2e6c4'; c.fillRect(0.22, -0.78, 0.14, 0.02);   // cash stack
    rr(c, 0.48, -0.86, 0.07, 0.13, 0.015); inked(c, 'rgba(230,240,255,0.6)', 0.012); c.fillStyle = '#c8822a'; c.fillRect(0.485, -0.8, 0.06, 0.06);   // whiskey
    c.restore();
    // ---- his men on the slope toward the Runner
    // Zee 2026-11-04: "the mafia guys should extend a hand trying to reach us ... we touched their hand, now we're safe, profit booked" -
    // the front man's fingertips sit exactly on the target (the origin), so touching his hand IS the take-profit filling.
    const goonPose = st.robbed ? (mood === 'shot' ? 'knocked' : st.alert ? 'aim' : 'guard') : paying ? 'throw' : refused ? 'shrug' : null;
    const nK = Math.max(0, Math.min(3, +st.knocked || 0));
    const front = st.robbed ? [[-0.2, 1], [-0.7, 2], [-1.2, 3]] : [[-0.5, 1], [-1.05, 2]];
    const kp = Array.isArray(st.knockProg) ? st.knockProg : [1, 1, 1];
    const men = front.map(([dx, seed], i) => [dx, i < nK ? 'knocked' : st.robbed ? (st.alert ? 'aim' : 'guard') : (goonPose || (i === 0 ? 'reach' : 'reach2')), seed, kp[i] ?? 1]).reverse();
    { const gx = x + f * (st.robbed ? -0.2 : -0.5) * s; P.goonX = gx; P.goonY = gAt(gx) - 0.6 * s; P.bossX = bx0 + f * -0.1 * s; P.bossY = by0 - 1.0 * s; }
    { const xa = x + f * 0.25 * s, xb = bx0 + f * -3.1 * s, top = Math.min(by0, y) - 2.4 * s; P.box = { x: Math.min(xa, xb), y: top, w: Math.abs(xb - xa), h: Math.max(by0, y) + 0.1 * s - top }; }
    for (const [dx, pose, seed, mk] of men) {
      const gx = x + f * dx * s, gy = gAt(gx);
      if (!isFinite(gy)) continue;
      c.save(); c.translate(gx, gy); c.scale(f * s * 0.95, s * 0.95);
      drawGoon(c, t, pose, seed, mk);
      c.restore();
    }
  } catch (e) {
    if (!drawHumanBuyer._err) { drawHumanBuyer._err = true; console.error('drawHumanBuyer', e); }
  }
  c.restore();
  return P;
}
