// palette.js - the ONE shared style source for every visual module of Golden Gravity (art.js, world.js, fx.js, main.js, screens.js).
// Style: "Clockwork-Deco Casino" (REQUIREMENTS.md, Art Bible) - 1920s Wall Street gold, riveted iron and brass, cartoon physics.
//
// THE RECIPE (every drawn object follows it, so four modules look like one game):
//  1. Ink outline: P.ink at LINE.ink * s px (s = pixels per unit, 1 unit = the Runner's standing height). Round joins and caps.
//  2. Flat base fill, then ONE highlight band (light from the upper left, ~25% lighter, soft-edged) and ONE shadow band
//     (lower right, ~30% darker). Use shade(ctx, ...) / lighten() / darken() below - no other lighting model.
//  3. Important objects get a gold deco trim (P.gold, LINE.deco * s): bank, bell, buyer's carriage, roof sign, stakes, coin rim.
//  4. Iron and brass get rivets (rivet()), small and regular.
//  5. Glows are additive radial gradients (glow()), never blur filters (too slow).
//  6. Cartoon proportions: Runner head = 0.30 of his height; hands and feet slightly oversized; squash & stretch on landings.
//  7. Text in the world is a physical object: split-flap tiles, painted tags, neon tubes - never a floating UI label.

export const P = {
  ink: '#1a1410', inkSoft: 'rgba(26,20,16,0.55)', paper: '#f6efdc',
  // brass / gold
  gold: '#ffcc33', goldHot: '#fff2b0', goldDeep: '#b8860b', goldDark: '#7a5a12',
  brass: '#c9a24a', brassDark: '#8a6a24', brassLight: '#f0d68a',
  // iron / bank
  iron: '#3b3f47', ironDark: '#23262c', ironLight: '#6b717c', rivet: '#a7adb7',
  brick: '#8e3b2e', brickDark: '#5e241b', brickLight: '#b8584a',
  visor: '#2fb36b',
  // buyer / emerald
  emerald: '#1f9e6e', emeraldDark: '#0f5c40', emeraldLight: '#6fe0b0',
  // street
  marble: '#e9e4d8', marbleVein: '#b9b2a2', marbleShade: '#c8c1b1', marbleDark: '#8f887a',
  ledger: '#efe6c8', ledgerLine: '#9fb6c9', gear: '#8c7a55',
  weathered: '#9a978f', scorch: '#2b1d14', voidc: '#050208', voidEdge: '#3a1450',
  molasses: '#2a160b', molassesHi: '#6b3a17', molassesFoam: '#a0662f',
  // signs
  crimson: '#e0303a', crimsonGlow: '#ff5a5f', cyan: '#3fe6ff', cyanGlow: '#a8f6ff', flap: '#121214', flapLine: '#2c2c33',
  neonPurple: '#b44dff', neonPink: '#ff4fd8', neonGreen: '#5dff8a',
  // people
  skin: '#f3d3bc', skinShade: '#d9a98c',   // Zee 2026-11-04: a fair-skinned, dead-serious hunter
  hair: '#3a2615', blush: '#ff8a80',
  suit: '#7a6a55', suitDark: '#54493a', suspender: '#a4372c', tux: '#17171f', tuxLapel: '#2a2a36', shirt: '#f4f1ea',
  undershirt: '#efe9d6', boxers: '#e85d75', polka: '#ffffff', barrel: '#8a5a2b', barrelBand: '#4a4a4a', wood: '#b07a3e',
  trench: '#5b4b3a', twinBrass: '#d8b25a', ghost: 'rgba(200,230,255,0.35)', collector: '#7d8088',
  // atmosphere
  sepia: '#9c7a4f', ash: '#bdb6a8', ticker: '#f3f0e6', leaf: '#d9822b', snow: '#f4f8ff', lightning: '#d9a6ff',
};

// sky gradients, top -> horizon (world.js blends between neighbours by day_frac and weather)
export const SKY = {
  dawn:      ['#2a2950', '#7b4c7a', '#f08a5d', '#ffd29a'],   // Asia
  noon:      ['#2d6fd6', '#5fa8ff', '#a9d8ff', '#e8f6ff'],   // London
  afternoon: ['#2f4fa8', '#e08b4b', '#ffb36b', '#ffe0a8'],   // New York, the long aggressive sunset
  golden:    ['#3a2a52', '#c0613b', '#ff9a3c', '#ffd27a'],   // golden hour (last minute before the Merchant insists)
  night:     ['#05060f', '#0d1530', '#1a2244', '#2a2f52'],   // dead hours / a round older than 10 minutes
  storm:     ['#020204', '#0b0b14', '#16121f', '#221a2e'],   // news / volatility spike
  dead:      ['#5a4a35', '#8a7454', '#a88f68', '#c4ad86'],   // flat sepia fog, falling ash
  freeze:    ['#3b3328', '#5e5241', '#7d6e57', '#9a8a70'],   // Time Freeze (link lost)
};

export const LINE = { ink: 0.035, inkThin: 0.02, deco: 0.016, hair: 0.01 };   // in units: multiply by s
export const FONT = {
  sign: '"Courier New", Courier, monospace',      // split-flap digits
  deco: 'Georgia, "Times New Roman", serif',       // painted signs, tags, the plain-words line
  ui: 'system-ui, "Segoe UI", sans-serif',         // the safety screen only
};

// ------------------------------------------------------------------ shared helpers (use them; do not re-invent)
export function inkStroke(ctx, s, w = LINE.ink, color = P.ink) {
  ctx.lineWidth = Math.max(1, w * s); ctx.strokeStyle = color; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
}
export function hexToRgb(h) {
  const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
export function rgba(h, a) { const [r, g, b] = hexToRgb(h); return `rgba(${r},${g},${b},${a})`; }
export function mix(h1, h2, t) {
  const a = hexToRgb(h1), b = hexToRgb(h2);
  const c = a.map((v, i) => Math.round(v + (b[i] - v) * t));
  return '#' + c.map((v) => v.toString(16).padStart(2, '0')).join('');
}
export const lighten = (h, t = 0.25) => mix(h, '#ffffff', t);
export const darken = (h, t = 0.3) => mix(h, '#000000', t);

// fill the current path with the recipe's base + highlight + shadow (bounding box x,y,w,h in px)
export function shade(ctx, x, y, w, h, base) {
  const g = ctx.createLinearGradient(x, y, x + w * 0.6, y + h);
  g.addColorStop(0, lighten(base, 0.25)); g.addColorStop(0.35, base); g.addColorStop(1, darken(base, 0.3));
  ctx.fillStyle = g; ctx.fill();
}
// additive radial glow (cheap): call between ctx.save()/restore()
export function glow(ctx, x, y, r, color, alpha = 0.6) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, rgba(color, alpha)); g.addColorStop(1, rgba(color, 0));
  const op = ctx.globalCompositeOperation; ctx.globalCompositeOperation = 'lighter';
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  ctx.globalCompositeOperation = op;
}
export function rivet(ctx, x, y, s) {
  const r = Math.max(1, 0.018 * s);
  ctx.fillStyle = P.rivet; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.beginPath(); ctx.arc(x - r * 0.35, y - r * 0.35, r * 0.4, 0, Math.PI * 2); ctx.fill();
}
export function roundRect(ctx, x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
// deterministic pseudo-random for stable textures (marble veins, rivet jitter): rand(seed) in [0,1)
export function rand(seed) { const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }
export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export const lerp = (a, b, t) => a + (b - a) * t;
export const ease = (t) => t * t * (3 - 2 * t);
