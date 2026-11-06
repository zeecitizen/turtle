// hunter.js - the Runner as a gold hunter (Zee 2026-11-04): "instead of a layman holding paper money iniitially we should show an expert
// hunter with a bow and arrow and holding a shotgun -> this indicates the player we're here to hunt for gold".
// Gear drawn around the Runner while he waits at the start (lobby) and aims (shoot): a longbow + quiver on his back, a wide-brim hunter's
// hat, and a double-barrel shotgun (resting on his shoulder in the lobby, levelled at the Guard when aiming).
// All take (ctx, ..., s, facing): s = px per unit (the Runner is 1 unit tall), facing +1 = he looks right.

const TAU = Math.PI * 2;
function inked(c, fill, lw = 0.02) { c.fillStyle = fill; c.fill(); c.strokeStyle = '#1a1210'; c.lineWidth = lw; c.stroke(); }

// behind the body: the quiver of arrows and the longbow slung across his back. (x, y) = his feet.
export function drawHunterBack(ctx, x, y, s, facing = 1) {
  const c = ctx, f = facing < 0 ? -1 : 1;
  c.save();
  try {
    c.translate(x, y); c.scale(f * s, s);
    // the longbow, slung diagonally
    c.save(); c.translate(-0.13, -0.62); c.rotate(-0.35);
    c.beginPath(); c.moveTo(0, -0.42); c.quadraticCurveTo(-0.17, 0, 0, 0.42); c.strokeStyle = '#1a1210'; c.lineWidth = 0.055; c.lineCap = 'round'; c.stroke();
    c.strokeStyle = '#8a5a2b'; c.lineWidth = 0.035; c.stroke();
    c.strokeStyle = '#efe6cf'; c.lineWidth = 0.008; c.beginPath(); c.moveTo(0, -0.42); c.lineTo(0, 0.42); c.stroke();
    c.fillStyle = '#3a2412'; c.fillRect(-0.12, -0.05, 0.05, 0.1);
    c.restore();
    // the quiver with fletched arrows
    c.save(); c.translate(-0.17, -0.7); c.rotate(0.35);
    for (let i = 0; i < 3; i++) {
      const ax = -0.03 + i * 0.03;
      c.strokeStyle = '#6b4526'; c.lineWidth = 0.012; c.beginPath(); c.moveTo(ax, -0.1); c.lineTo(ax, -0.34); c.stroke();
      c.fillStyle = ['#d4183a', '#f2f2f2', '#2f8fdc'][i]; c.beginPath(); c.moveTo(ax, -0.36); c.lineTo(ax - 0.025, -0.28); c.lineTo(ax, -0.3); c.lineTo(ax + 0.025, -0.28); c.closePath(); c.fill();
    }
    c.beginPath(); c.moveTo(-0.07, -0.14); c.lineTo(0.07, -0.14); c.lineTo(0.055, 0.2); c.lineTo(-0.055, 0.2); c.closePath(); inked(c, '#7a4a26');
    c.strokeStyle = '#3a2412'; c.lineWidth = 0.012; c.beginPath(); c.moveTo(-0.065, -0.05); c.lineTo(0.065, -0.05); c.moveTo(-0.06, 0.1); c.lineTo(0.06, 0.1); c.stroke();
    c.restore();
  } catch (e) { if (!drawHunterBack._err) { drawHunterBack._err = true; console.error('drawHunterBack', e); } }
  c.restore();
}

// a wide-brim hunter's hat with a feather. (hx, hy) = the head point the Runner reports.
export function drawHunterHat(ctx, hx, hy, s, facing = 1) {
  const c = ctx, f = facing < 0 ? -1 : 1;
  c.save();
  try {
    c.translate(hx, hy - 0.1 * s); c.scale(f * s, s);
    c.beginPath(); c.ellipse(0, 0.0, 0.2, 0.04, -0.05, 0, TAU); inked(c, '#5b4027');
    c.beginPath(); c.moveTo(-0.1, 0); c.quadraticCurveTo(-0.11, -0.13, -0.02, -0.13); c.lineTo(0.01, -0.11); c.lineTo(0.04, -0.13); c.quadraticCurveTo(0.12, -0.13, 0.11, 0); c.closePath(); inked(c, '#6e4c2e');
    c.fillStyle = '#2f2014'; c.fillRect(-0.105, -0.045, 0.215, 0.03);
    c.save(); c.translate(-0.08, -0.04); c.rotate(-0.9);                         // a pheasant feather in the band
    c.beginPath(); c.ellipse(0, -0.08, 0.022, 0.09, 0, 0, TAU); inked(c, '#b5652a', 0.01);
    c.strokeStyle = '#3a2412'; c.lineWidth = 0.006; c.beginPath(); c.moveTo(0, 0.01); c.lineTo(0, -0.16); c.stroke();
    c.restore();
  } catch (e) { if (!drawHunterHat._err) { drawHunterHat._err = true; console.error('drawHunterHat', e); } }
  c.restore();
}

// the double-barrel shotgun. (hx, hy) = the hand; aim = true levels it along facing, otherwise it rests up on his shoulder.
export function drawShotgun(ctx, hx, hy, s, facing = 1, aim = false, recoil = 0) {
  const c = ctx, f = facing < 0 ? -1 : 1;
  c.save();
  try {
    c.translate(hx, hy); c.scale(f * s, s);
    c.rotate(aim ? -0.04 - recoil * 0.25 : -1.15);
    c.translate(aim ? -0.14 - recoil * 0.05 : -0.12, 0);
    // stock
    c.beginPath(); c.moveTo(-0.22, 0.02); c.lineTo(-0.02, -0.01); c.lineTo(0.04, 0.03); c.lineTo(-0.02, 0.06); c.lineTo(-0.22, 0.09); c.closePath(); inked(c, '#7a4520');
    c.strokeStyle = 'rgba(255,255,255,0.18)'; c.lineWidth = 0.008; c.beginPath(); c.moveTo(-0.2, 0.04); c.lineTo(-0.04, 0.02); c.stroke();
    // receiver + two barrels
    c.beginPath(); c.rect(0.02, -0.025, 0.1, 0.05); inked(c, '#5a5f66', 0.015);
    c.beginPath(); c.rect(0.12, -0.025, 0.42, 0.024); inked(c, '#3b3f45', 0.012);
    c.beginPath(); c.rect(0.12, 0.0, 0.42, 0.024); inked(c, '#2f3237', 0.012);
    c.fillStyle = '#7a4520'; c.fillRect(0.14, 0.024, 0.16, 0.022);           // fore-end
    c.fillStyle = 'rgba(255,255,255,0.3)'; c.fillRect(0.13, -0.02, 0.4, 0.006);
    c.strokeStyle = '#1a1210'; c.lineWidth = 0.012; c.beginPath(); c.arc(0.05, 0.045, 0.025, 0, Math.PI); c.stroke();   // trigger guard
    if (aim && recoil > 0.3) {                                   // muzzle flash
      c.fillStyle = `rgba(255,210,90,${recoil.toFixed(3)})`; c.beginPath();
      for (let i = 0; i < 10; i++) { const a = (i / 10) * TAU, r = i % 2 ? 0.04 : 0.11; c.lineTo(0.6 + Math.cos(a) * r, Math.sin(a) * r); }
      c.closePath(); c.fill();
    }
  } catch (e) { if (!drawShotgun._err) { drawShotgun._err = true; console.error('drawShotgun', e); } }
  c.restore();
}
