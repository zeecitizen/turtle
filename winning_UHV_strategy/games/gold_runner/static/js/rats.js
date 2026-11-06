// rats.js - the white rat (Zee 2026-11-04): "the empty jar on the bottom left -> it should be owned by a white rat holding this jar .. and the
// rat that digs the muddy spread on ground should be a clear white rat visibly digging the hole".
// drawWhiteRat(ctx, x, y, s, st): (x, y) = the ground under the rat, s = px per unit (the Runner is 1 unit tall).
// st: { pose: 'sit' | 'dig' | 'run' | 'bite' | 'hug', t, facing (+1 looks right), scale (default 1) }.
// drawJarRat(ctx, jarX, jarY, s, t, layer): the white rat sitting up behind the cost jar, hugging it - layer 'back' (before the jar) draws
// the body, layer 'front' (after the jar) draws the paws over the glass.

const TAU = Math.PI * 2;
const FUR = '#fbfaf6', FUR_SH = '#dcd8cf', PINK = '#f4a6b8', PINK_D = '#d97a92', INK = '#2a1a10';
function o(c, lw) { c.strokeStyle = INK; c.lineWidth = lw; c.stroke(); }

function head(c, t, lw, sniff) {
  // a pointed white head with a pink nose, a pink ear, a shiny eye and whiskers (head faces +x)
  c.beginPath(); c.moveTo(-0.06, -0.05); c.quadraticCurveTo(0.02, -0.08, 0.13, -0.015 + sniff); c.quadraticCurveTo(0.02, 0.03, -0.06, 0.03); c.closePath();
  c.fillStyle = FUR; c.fill(); o(c, lw);
  c.beginPath(); c.ellipse(-0.035, -0.07, 0.03, 0.04, -0.4, 0, TAU); c.fillStyle = FUR; c.fill(); o(c, lw);
  c.beginPath(); c.ellipse(-0.035, -0.07, 0.016, 0.025, -0.4, 0, TAU); c.fillStyle = PINK; c.fill();
  c.beginPath(); c.arc(0.135, -0.015 + sniff, 0.013, 0, TAU); c.fillStyle = PINK_D; c.fill();
  c.beginPath(); c.arc(0.035, -0.03, 0.011, 0, TAU); c.fillStyle = '#c01830'; c.fill();       // a ruby eye
  c.fillStyle = '#fff'; c.beginPath(); c.arc(0.039, -0.034, 0.004, 0, TAU); c.fill();
  c.strokeStyle = 'rgba(60,40,30,0.7)'; c.lineWidth = lw * 0.45;
  for (const d of [-0.012, 0, 0.012]) { c.beginPath(); c.moveTo(0.11, -0.01 + sniff + d * 0.3); c.lineTo(0.18, -0.03 + sniff + d * 1.6); c.stroke(); }
}

export function drawWhiteRat(ctx, x, y, s, st = {}) {
  const c = ctx, t = +st.t || 0, f = st.facing < 0 ? -1 : 1, sc = st.scale || 1, pose = st.pose || 'sit';
  const lw = 0.012;
  c.save();
  try {
    c.translate(x, y); c.scale(f * s * sc * 1.6, s * sc * 1.6);
    c.lineJoin = 'round'; c.lineCap = 'round';
    const run = pose === 'run', dig = pose === 'dig', bite = pose === 'bite';
    const bob = run ? Math.abs(Math.sin(t * 22)) * 0.012 : dig ? Math.abs(Math.sin(t * 16)) * 0.008 : 0;
    const sniff = Math.sin(t * 9) * 0.004;
    // the long pink tail
    const tw = Math.sin(t * (run ? 14 : 3)) * 0.03;
    c.strokeStyle = PINK_D; c.lineWidth = 0.014; c.beginPath(); c.moveTo(-0.1, -0.04); c.quadraticCurveTo(-0.24, -0.0 + tw, -0.32, -0.06 - tw); c.stroke();
    c.strokeStyle = PINK; c.lineWidth = 0.008; c.stroke();
    if (dig) {                                          // nose down, rump up, front paws scratching the ground in turns
      c.save(); c.rotate(0.35); c.translate(0, -bob);
      c.beginPath(); c.ellipse(-0.02, -0.065, 0.1, 0.055, 0, 0, TAU); c.fillStyle = FUR; c.fill(); o(c, lw);
      c.fillStyle = FUR_SH; c.beginPath(); c.ellipse(-0.02, -0.035, 0.08, 0.02, 0, 0, Math.PI); c.fill();
      c.save(); c.translate(0.08, -0.04); c.rotate(0.25); head(c, t, lw, sniff); c.restore();
      c.restore();
      const a = Math.sin(t * 18), b = Math.sin(t * 18 + Math.PI);
      for (const [px, k] of [[0.1, a], [0.13, b]]) { c.strokeStyle = PINK_D; c.lineWidth = 0.014; c.beginPath(); c.moveTo(px - 0.02, -0.03); c.lineTo(px + 0.02 * k, -0.002); c.stroke(); }
      c.strokeStyle = PINK_D; c.lineWidth = 0.016; c.beginPath(); c.moveTo(-0.08, -0.03); c.lineTo(-0.1, 0); c.moveTo(-0.04, -0.03); c.lineTo(-0.05, 0); c.stroke();
      // clods of earth flung back between the hind legs
      for (let i = 0; i < 5; i++) {
        const ph = (t * 2.2 + i / 5) % 1, cx = -0.05 - ph * 0.3, cy = -0.02 - Math.sin(ph * Math.PI) * 0.16;
        c.globalAlpha = 1 - ph * 0.7; c.fillStyle = i % 2 ? '#6b4423' : '#8a5a2b'; c.beginPath(); c.arc(cx, cy, 0.014 + (i % 3) * 0.004, 0, TAU); c.fill();
      }
      c.globalAlpha = 1;
    } else if (pose === 'sit' || pose === 'hug') {        // sitting up on its haunches
      c.translate(0, -bob);
      c.beginPath(); c.ellipse(-0.02, -0.08, 0.075, 0.09, -0.15, 0, TAU); c.fillStyle = FUR; c.fill(); o(c, lw);
      c.fillStyle = FUR_SH; c.beginPath(); c.ellipse(0.0, -0.06, 0.04, 0.06, -0.15, 0, TAU); c.fill();
      c.strokeStyle = PINK_D; c.lineWidth = 0.016; c.beginPath(); c.moveTo(-0.04, -0.01); c.lineTo(0.0, 0.0); c.stroke();
      c.save(); c.translate(0.02, -0.17); c.rotate(-0.25 + sniff * 3); head(c, t, lw, sniff); c.restore();
      if (pose === 'sit') { c.strokeStyle = PINK_D; c.lineWidth = 0.013; c.beginPath(); c.moveTo(0.02, -0.1); c.lineTo(0.06, -0.09); c.moveTo(0.02, -0.08); c.lineTo(0.06, -0.07); c.stroke(); }
    } else {                                            // run / bite: on all fours
      c.translate(0, -bob);
      c.beginPath(); c.ellipse(-0.01, -0.06, 0.11, 0.055, -0.05, 0, TAU); c.fillStyle = FUR; c.fill(); o(c, lw);
      c.fillStyle = FUR_SH; c.beginPath(); c.ellipse(-0.01, -0.03, 0.09, 0.02, 0, 0, Math.PI); c.fill();
      for (let i = 0; i < 4; i++) {
        const lx = i < 2 ? -0.07 + i * 0.03 : 0.04 + (i - 2) * 0.03, a = run ? Math.sin(t * 22 + i * Math.PI * 0.5) * 0.5 : 0;
        c.strokeStyle = PINK_D; c.lineWidth = 0.013; c.beginPath(); c.moveTo(lx, -0.03); c.lineTo(lx + Math.sin(a) * 0.035, -0.002); c.stroke();
      }
      const lunge = bite ? Math.max(0, Math.sin(t * 13)) * 0.03 : 0;
      c.save(); c.translate(0.08 + lunge, -0.05); head(c, t, lw, sniff); c.restore();
      if (bite) { c.fillStyle = '#fff'; c.fillRect(0.2 + lunge, -0.04, 0.012, 0.016); }
    }
  } catch (e) { if (!drawWhiteRat._err) { drawWhiteRat._err = true; console.error('drawWhiteRat', e); } }
  c.restore();
}

// the white rat that owns the cost jar: it sits up behind the jar, paws wrapped round the glass
export function drawJarRat(ctx, jx, jy, s, t, layer, sc = 1) {
  const c = ctx;
  c.save();
  try {
    c.translate(jx, jy); c.scale(s * sc, s * sc);
    if (layer === 'back') {
      c.save(); c.translate(0.16, 0.0); c.scale(-1.6, 1.6);           // body to the right of the jar, facing it
      c.beginPath(); c.ellipse(0.0, -0.1, 0.08, 0.1, 0.15, 0, TAU); c.fillStyle = FUR; c.fill(); o(c, 0.012);
      c.fillStyle = FUR_SH; c.beginPath(); c.ellipse(0.015, -0.08, 0.04, 0.06, 0.15, 0, TAU); c.fill();
      const tw = Math.sin(t * 3) * 0.03;
      c.strokeStyle = PINK_D; c.lineWidth = 0.014; c.beginPath(); c.moveTo(-0.05, -0.02); c.quadraticCurveTo(-0.2, 0.01 + tw, -0.25, -0.06 - tw); c.stroke();
      c.save(); c.translate(0.03, -0.2); c.rotate(-0.15 + Math.sin(t * 2) * 0.05); head(c, t, 0.012, Math.sin(t * 9) * 0.004); c.restore();
      c.restore();
    } else {
      c.fillStyle = FUR; c.strokeStyle = INK; c.lineWidth = 0.012;   // two paws hugging the glass
      for (const [px, py] of [[0.09, -0.2], [0.1, -0.12]]) { c.beginPath(); c.ellipse(px, py, 0.035, 0.022, -0.3, 0, TAU); c.fill(); c.stroke(); c.fillStyle = PINK; c.beginPath(); c.arc(px - 0.02, py, 0.008, 0, TAU); c.fill(); c.fillStyle = FUR; }
    }
  } catch (e) { if (!drawJarRat._err) { drawJarRat._err = true; console.error('drawJarRat', e); } }
  c.restore();
}
