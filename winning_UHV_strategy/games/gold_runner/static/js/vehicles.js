// vehicles.js - the target ladder as vehicles (Zee 2026-11-04): "remove the white hanging white papers .. its hard to process 4 numbers ..
// instead maybe we can show a series of cars -> skate -> cycle -> car -> jeep -> helicopter .. this symbolizes the greater our ambition the
// more expensive the vehicle we pick from .. and if we sell to the mafia boss we should be able to get that vehicle"
//
// VEHICLES[i] matches settings.targets[i] (smallest target = the skateboard). drawVehicle(ctx, kind, x, y, s, st): (x, y) = the ground point
// under its middle, s = px per unit (the Runner is 1 unit tall). st: { t, scale (default 1), facing, bow (a red prize bow), shine 0..1 }.

export const VEHICLES = ['skate', 'bike', 'car', 'jeep', 'heli'];
export const VEHICLE_WIDTH = { skate: 0.62, bike: 0.8, car: 1.15, jeep: 1.2, heli: 1.45 };   // units at scale 1
const TAU = Math.PI * 2;
function inked(c, fill, lw = 0.025) { c.fillStyle = fill; c.fill(); c.strokeStyle = '#1a1210'; c.lineWidth = lw; c.stroke(); }
function rr(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }
function tyre(c, x, y, r, spin, hub = '#c9ced6') {
  c.beginPath(); c.arc(x, y, r, 0, TAU); inked(c, '#1d1d20', 0.02);
  c.beginPath(); c.arc(x, y, r * 0.55, 0, TAU); inked(c, hub, 0.012);
  c.strokeStyle = '#7d848f'; c.lineWidth = 0.012;
  for (let i = 0; i < 4; i++) { const a = spin + i * Math.PI / 2; c.beginPath(); c.moveTo(x, y); c.lineTo(x + Math.cos(a) * r * 0.5, y + Math.sin(a) * r * 0.5); c.stroke(); }
}

function skate(c, t) {
  c.beginPath(); c.moveTo(-0.3, -0.12); c.quadraticCurveTo(-0.34, -0.17, -0.27, -0.16); c.lineTo(0.27, -0.16); c.quadraticCurveTo(0.34, -0.17, 0.3, -0.12); c.lineTo(-0.3, -0.12); c.closePath();
  inked(c, '#ff6b3d', 0.02);
  c.fillStyle = '#ffd23f'; c.fillRect(-0.18, -0.155, 0.36, 0.02);
  c.fillStyle = '#7d848f'; c.fillRect(-0.22, -0.12, 0.06, 0.03); c.fillRect(0.16, -0.12, 0.06, 0.03);
  for (const wx of [-0.2, 0.2]) { c.beginPath(); c.arc(wx, -0.05, 0.05, 0, TAU); inked(c, '#f4f1ea', 0.015); }
}
function bike(c, t) {
  const r = 0.17;
  for (const wx of [-0.27, 0.27]) { c.beginPath(); c.arc(wx, -r, r, 0, TAU); c.strokeStyle = '#1d1d20'; c.lineWidth = 0.04; c.stroke(); c.strokeStyle = '#c9ced6'; c.lineWidth = 0.01; for (let i = 0; i < 6; i++) { const a = t * 2 + i * TAU / 6; c.beginPath(); c.moveTo(wx, -r); c.lineTo(wx + Math.cos(a) * r, -r + Math.sin(a) * r); c.stroke(); } }
  c.strokeStyle = '#1a1210'; c.lineWidth = 0.055; c.lineCap = 'round'; c.lineJoin = 'round';
  const path = () => { c.beginPath(); c.moveTo(-0.27, -r); c.lineTo(-0.02, -r); c.lineTo(0.18, -0.42); c.lineTo(-0.1, -0.42); c.lineTo(-0.02, -r); c.moveTo(-0.27, -r); c.lineTo(-0.1, -0.42); c.moveTo(0.27, -r); c.lineTo(0.2, -0.5); c.lineTo(0.12, -0.52); c.moveTo(-0.1, -0.42); c.lineTo(-0.12, -0.48); };
  path(); c.stroke(); c.strokeStyle = '#2f8fdc'; c.lineWidth = 0.03; path(); c.stroke();
  c.beginPath(); c.ellipse(-0.12, -0.5, 0.07, 0.022, 0, 0, TAU); inked(c, '#1d1d20', 0.01);
}
function car(c, t) {
  c.beginPath(); c.moveTo(-0.55, -0.12); c.lineTo(-0.55, -0.3); c.quadraticCurveTo(-0.5, -0.36, -0.36, -0.37); c.lineTo(-0.22, -0.55); c.quadraticCurveTo(-0.15, -0.6, 0.05, -0.6);
  c.lineTo(0.2, -0.6); c.quadraticCurveTo(0.28, -0.58, 0.34, -0.38); c.lineTo(0.5, -0.35); c.quadraticCurveTo(0.57, -0.32, 0.57, -0.2); c.lineTo(0.57, -0.12); c.closePath();
  inked(c, '#d6232f', 0.03);
  c.beginPath(); c.moveTo(-0.18, -0.38); c.lineTo(-0.1, -0.53); c.lineTo(0.03, -0.53); c.lineTo(0.03, -0.38); c.closePath(); inked(c, '#bfe3ff', 0.015);
  c.beginPath(); c.moveTo(0.07, -0.38); c.lineTo(0.07, -0.53); c.lineTo(0.19, -0.53); c.quadraticCurveTo(0.24, -0.5, 0.27, -0.38); c.closePath(); inked(c, '#bfe3ff', 0.015);
  c.fillStyle = 'rgba(255,255,255,0.35)'; c.fillRect(-0.5, -0.31, 0.95, 0.03);
  c.fillStyle = '#ffe680'; c.beginPath(); c.ellipse(0.55, -0.27, 0.025, 0.035, 0, 0, TAU); c.fill();
  c.fillStyle = '#c9ced6'; c.fillRect(-0.57, -0.17, 0.08, 0.04); c.fillRect(0.5, -0.17, 0.08, 0.04);
  tyre(c, -0.32, -0.1, 0.1, t * 3); tyre(c, 0.34, -0.1, 0.1, t * 3);
}
function jeep(c, t) {
  rr(c, -0.58, -0.5, 1.12, 0.36, 0.04); inked(c, '#4f6b36', 0.03);
  c.beginPath(); c.moveTo(-0.3, -0.5); c.lineTo(-0.22, -0.78); c.lineTo(0.22, -0.78); c.lineTo(0.3, -0.5); c.closePath(); c.strokeStyle = '#1a1210'; c.lineWidth = 0.05; c.stroke(); c.strokeStyle = '#2f3a24'; c.lineWidth = 0.03; c.stroke();
  c.beginPath(); c.moveTo(-0.26, -0.52); c.lineTo(-0.2, -0.74); c.lineTo(0.2, -0.74); c.lineTo(0.26, -0.52); c.closePath(); c.fillStyle = 'rgba(191,227,255,0.6)'; c.fill();
  c.fillStyle = '#2f3a24'; for (let i = 0; i < 5; i++) c.fillRect(0.4, -0.46 + i * 0.05, 0.12, 0.025);       // grille
  c.fillStyle = '#ffe680'; c.beginPath(); c.arc(0.5, -0.43, 0.035, 0, TAU); c.fill();
  c.beginPath(); c.arc(-0.62, -0.36, 0.1, 0, TAU); inked(c, '#1d1d20', 0.02);                               // the spare on the back
  c.fillStyle = '#fff'; c.font = 'bold 0.12px Georgia, serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
  tyre(c, -0.33, -0.13, 0.14, t * 3, '#9aa0aa'); tyre(c, 0.33, -0.13, 0.14, t * 3, '#9aa0aa');
}
function heli(c, t) {
  const spin = t * 30;
  c.strokeStyle = '#1a1210'; c.lineWidth = 0.035; c.lineCap = 'round';
  c.beginPath(); c.moveTo(-0.35, -0.03); c.lineTo(0.35, -0.03); c.moveTo(-0.22, -0.03); c.lineTo(-0.18, -0.18); c.moveTo(0.2, -0.03); c.lineTo(0.16, -0.18); c.stroke();   // skids
  c.beginPath(); c.moveTo(-0.15, -0.38); c.lineTo(-0.82, -0.44); c.lineTo(-0.82, -0.36); c.lineTo(-0.15, -0.28); c.closePath(); inked(c, '#f2b705', 0.02);          // tail boom
  c.save(); c.translate(-0.82, -0.42); c.rotate(spin * 1.3);
  c.fillStyle = 'rgba(40,40,40,0.75)'; c.fillRect(-0.12, -0.012, 0.24, 0.024); c.restore();
  c.beginPath(); c.ellipse(0.05, -0.33, 0.32, 0.18, 0, 0, TAU); inked(c, '#f2b705', 0.03);                                                              // cabin
  c.beginPath(); c.ellipse(0.17, -0.37, 0.15, 0.11, 0, -Math.PI * 0.6, Math.PI * 0.45); c.closePath(); inked(c, '#bfe3ff', 0.015);
  c.fillStyle = '#1a1210'; c.fillRect(0.0, -0.53, 0.06, 0.05);
  c.save(); c.translate(0.03, -0.55); c.scale(1, 0.18);
  const w = Math.abs(Math.cos(spin)) * 0.75 + 0.1;
  c.fillStyle = 'rgba(30,30,30,0.7)'; c.beginPath(); c.ellipse(0, 0, w, 0.12, 0, 0, TAU); c.fill(); c.restore();
  c.fillStyle = 'rgba(40,40,40,0.18)'; c.beginPath(); c.ellipse(0.03, -0.55, 0.8, 0.03, 0, 0, TAU); c.fill();
}

const DRAW = { skate, bike, car, jeep, heli };

export function drawVehicle(ctx, kind, x, y, s, st = {}) {
  const c = ctx, t = +st.t || 0, sc = st.scale || 1, f = st.facing < 0 ? -1 : 1;
  c.save();
  try {
    c.translate(x, y); c.scale(f * s * sc, s * sc);
    if (st.shine > 0) {                                           // a golden spotlight from below
      const g = c.createRadialGradient(0, -0.3, 0, 0, -0.3, 0.9); g.addColorStop(0, `rgba(255,225,120,${(0.55 * st.shine).toFixed(3)})`); g.addColorStop(1, 'rgba(255,225,120,0)');
      c.fillStyle = g; c.fillRect(-1, -1.3, 2, 1.4);
    }
    c.fillStyle = 'rgba(0,0,0,0.22)'; c.beginPath(); c.ellipse(0, 0, (VEHICLE_WIDTH[kind] || 1) * 0.45, 0.04, 0, 0, TAU); c.fill();
    (DRAW[kind] || car)(c, t);
    if (st.bow) {                                                 // a big red prize bow on top
      const by = kind === 'skate' ? -0.25 : kind === 'bike' ? -0.62 : kind === 'heli' ? -0.62 : kind === 'jeep' ? -0.86 : -0.68;
      c.save(); c.translate(0, by);
      for (const sx of [-1, 1]) { c.beginPath(); c.moveTo(0, 0); c.quadraticCurveTo(sx * 0.16, -0.14, sx * 0.17, 0.0); c.quadraticCurveTo(sx * 0.12, 0.06, 0, 0); inked(c, '#d4183a', 0.015); }
      c.beginPath(); c.arc(0, 0, 0.035, 0, TAU); inked(c, '#b3132f', 0.012);
      c.restore();
    }
  } catch (e) {
    if (!drawVehicle._err) { drawVehicle._err = true; console.error('drawVehicle', e); }
  }
  c.restore();
}
