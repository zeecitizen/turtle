// angel.js - Zee 2026-11-06: "inside the game make a new character.. the angel comes in to bless us -> that angel is the physical appearance
// of the risk manager -> the angel is there to stop the yogi declaring a diamond if there's too much risk -> if we've managed risk the angel
// gives our player a shield (a bubble around the player) and in case the risk manager is stopping the trade the angel can put two light
// planes / shields in front of the bank / mafia which stop the player from shooting due to risk-not-allowed".
// The engine decides (engine.py _risk_verdict: the loss study's risk manager); these only draw it. Nothing here sends an order.
const TAU = Math.PI * 2;

// the angel, floating; st = { mode: 'bless' | 'block', alpha 0..1 }
export function drawAngel(ctx, x, y, s, t, st) {
  const a = Math.max(0, Math.min(1, st.alpha == null ? 1 : st.alpha)), block = st.mode === 'block';
  if (a <= 0.01) return;
  const bob = Math.sin(t * 1.6) * 0.12 * s, flap = Math.sin(t * (block ? 2.2 : 3.4)) * 0.18;
  const cy = y + bob;
  ctx.save();
  ctx.globalAlpha = a;
  // heavenly glow (golden when blessing, cool white-blue when blocking)
  const g = ctx.createRadialGradient(x, cy, 0.2 * s, x, cy, 2.6 * s);
  g.addColorStop(0, block ? 'rgba(200,225,255,0.55)' : 'rgba(255,236,170,0.6)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, cy, 2.6 * s, 0, TAU); ctx.fill();
  // wings (feathered: three layers of soft scallops)
  for (const sx of [-1, 1]) {
    ctx.save();
    ctx.translate(x + sx * 0.18 * s, cy - 0.35 * s);
    ctx.rotate(sx * (0.25 + flap));
    for (let layer = 0; layer < 3; layer++) {
      const len = (1.25 - layer * 0.28) * s, w = (0.55 - layer * 0.12) * s;
      ctx.fillStyle = layer === 0 ? 'rgba(255,255,255,0.95)' : layer === 1 ? 'rgba(236,242,255,0.95)' : 'rgba(214,226,250,0.95)';
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.quadraticCurveTo(sx * len * 0.55, -w * 1.4, sx * len, -w * 0.6);
      for (let i = 0; i < 5; i++) {                       // the feather scallops along the lower edge
        const px = sx * len * (1 - i / 5), py = -w * 0.6 + (w * 0.9) * (i / 5);
        ctx.quadraticCurveTo(px - sx * len * 0.06, py + 0.16 * s, sx * len * (1 - (i + 1) / 5), -w * 0.6 + (w * 0.9) * ((i + 1) / 5));
      }
      ctx.closePath(); ctx.fill();
      ctx.strokeStyle = 'rgba(170,185,220,0.5)'; ctx.lineWidth = Math.max(1, 0.01 * s); ctx.stroke();
    }
    ctx.restore();
  }
  // robe (flowing, with a golden sash)
  const rg = ctx.createLinearGradient(x, cy - 0.4 * s, x, cy + 1.1 * s);
  rg.addColorStop(0, '#ffffff'); rg.addColorStop(1, block ? '#c9d9f4' : '#f5e9c8');
  ctx.fillStyle = rg;
  ctx.beginPath();
  ctx.moveTo(x - 0.22 * s, cy - 0.45 * s);
  ctx.quadraticCurveTo(x - 0.55 * s, cy + 0.5 * s, x - 0.48 * s + Math.sin(t * 2) * 0.05 * s, cy + 1.1 * s);
  ctx.quadraticCurveTo(x, cy + 1.25 * s, x + 0.48 * s + Math.sin(t * 2 + 1) * 0.05 * s, cy + 1.1 * s);
  ctx.quadraticCurveTo(x + 0.55 * s, cy + 0.5 * s, x + 0.22 * s, cy - 0.45 * s);
  ctx.closePath(); ctx.fill();
  ctx.strokeStyle = 'rgba(180,160,110,0.45)'; ctx.lineWidth = Math.max(1, 0.012 * s);
  for (const k of [-0.2, 0, 0.2]) { ctx.beginPath(); ctx.moveTo(x + k * s * 0.6, cy - 0.1 * s); ctx.quadraticCurveTo(x + k * s, cy + 0.6 * s, x + k * s * 1.3, cy + 1.12 * s); ctx.stroke(); }
  ctx.strokeStyle = '#e7b93e'; ctx.lineWidth = Math.max(2, 0.05 * s);
  ctx.beginPath(); ctx.moveTo(x - 0.3 * s, cy + 0.05 * s); ctx.quadraticCurveTo(x, cy + 0.15 * s, x + 0.3 * s, cy + 0.05 * s); ctx.stroke();
  // arms: raised in blessing, or held out flat (stop)
  ctx.strokeStyle = '#f2d3b5'; ctx.lineCap = 'round'; ctx.lineWidth = 0.08 * s;
  ctx.beginPath();
  if (block) { ctx.moveTo(x - 0.2 * s, cy - 0.3 * s); ctx.lineTo(x - 0.75 * s, cy - 0.35 * s); ctx.moveTo(x + 0.2 * s, cy - 0.3 * s); ctx.lineTo(x + 0.75 * s, cy - 0.35 * s); }
  else { ctx.moveTo(x - 0.2 * s, cy - 0.3 * s); ctx.lineTo(x - 0.45 * s, cy - 0.85 * s); ctx.moveTo(x + 0.2 * s, cy - 0.3 * s); ctx.lineTo(x + 0.45 * s, cy - 0.85 * s); }
  ctx.stroke();
  if (block) {                                            // open palms facing out: STOP
    ctx.fillStyle = '#f2d3b5';
    for (const sx of [-1, 1]) { ctx.beginPath(); ctx.ellipse(x + sx * 0.8 * s, cy - 0.38 * s, 0.07 * s, 0.11 * s, 0, 0, TAU); ctx.fill(); }
  } else {                                                // sparkles rising from the raised hands
    for (let i = 0; i < 6; i++) {
      const ph = (t * 0.8 + i / 6) % 1, sx = i % 2 ? 1 : -1;
      sparkle(ctx, x + sx * 0.45 * s + Math.sin(i * 3 + t) * 0.1 * s, cy - 0.9 * s - ph * 0.8 * s, 0.06 * s * (1 - ph), `rgba(255,240,180,${1 - ph})`);
    }
  }
  // head, hair, face
  ctx.fillStyle = '#f7ddc4'; ctx.beginPath(); ctx.arc(x, cy - 0.62 * s, 0.17 * s, 0, TAU); ctx.fill();
  ctx.fillStyle = '#f3d27a';                              // golden curls
  ctx.beginPath(); ctx.arc(x, cy - 0.68 * s, 0.19 * s, Math.PI * 1.05, Math.PI * 1.95); ctx.fill();
  for (const sx of [-1, 1]) { ctx.beginPath(); ctx.ellipse(x + sx * 0.16 * s, cy - 0.55 * s, 0.06 * s, 0.13 * s, 0, 0, TAU); ctx.fill(); }
  ctx.strokeStyle = '#7a5a3a'; ctx.lineWidth = Math.max(1, 0.012 * s);
  ctx.beginPath(); ctx.arc(x - 0.06 * s, cy - 0.62 * s, 0.025 * s, 0.2, Math.PI - 0.2); ctx.moveTo(x + 0.085 * s, cy - 0.62 * s); ctx.arc(x + 0.06 * s, cy - 0.62 * s, 0.025 * s, 0.2, Math.PI - 0.2); ctx.stroke();
  ctx.beginPath();
  if (block) { ctx.moveTo(x - 0.04 * s, cy - 0.53 * s); ctx.lineTo(x + 0.04 * s, cy - 0.53 * s); }
  else ctx.arc(x, cy - 0.55 * s, 0.04 * s, 0.2, Math.PI - 0.2);
  ctx.stroke();
  // halo
  ctx.strokeStyle = block ? 'rgba(190,220,255,0.95)' : 'rgba(255,215,90,0.95)'; ctx.lineWidth = Math.max(2, 0.045 * s);
  ctx.shadowColor = ctx.strokeStyle; ctx.shadowBlur = 14;
  ctx.beginPath(); ctx.ellipse(x, cy - 0.92 * s, 0.2 * s, 0.06 * s, 0, 0, TAU); ctx.stroke();
  ctx.restore();
}

// a wall of light in front of the bank / the mafia: the risk manager says no (x = centre, yTop .. yBot)
export function drawLightShield(ctx, x, yTop, yBot, s, t, alpha) {
  const a = Math.max(0, Math.min(1, alpha == null ? 1 : alpha)), w = 0.42 * s, h = yBot - yTop;
  if (a <= 0.01) return;
  ctx.save();
  ctx.globalAlpha = a;
  const g = ctx.createLinearGradient(x - w, 0, x + w, 0);
  g.addColorStop(0, 'rgba(160,210,255,0)'); g.addColorStop(0.5, 'rgba(225,240,255,0.55)'); g.addColorStop(1, 'rgba(160,210,255,0)');
  ctx.fillStyle = g; ctx.fillRect(x - w, yTop, 2 * w, h);
  ctx.strokeStyle = 'rgba(235,245,255,0.95)'; ctx.lineWidth = Math.max(2, 0.04 * s); ctx.shadowColor = '#bfe0ff'; ctx.shadowBlur = 18;
  ctx.beginPath(); ctx.moveTo(x, yTop); ctx.lineTo(x, yBot); ctx.stroke();
  ctx.shadowBlur = 0;
  for (let i = 0; i < 7; i++) {                           // shimmering runes / ripples moving up the wall
    const ph = (t * 0.5 + i / 7) % 1;
    ctx.strokeStyle = `rgba(255,255,255,${0.55 * (1 - Math.abs(ph - 0.5) * 2)})`; ctx.lineWidth = Math.max(1, 0.015 * s);
    ctx.beginPath(); ctx.ellipse(x, yBot - ph * h, w * 0.75, 0.05 * s, 0, 0, TAU); ctx.stroke();
  }
  for (let i = 0; i < 5; i++) sparkle(ctx, x + Math.sin(t * 2 + i * 1.7) * w * 0.6, yTop + ((t * 0.3 + i * 0.21) % 1) * h, 0.05 * s, 'rgba(255,255,255,0.9)');
  ctx.restore();
}

// the protective bubble around the runner: risk managed
export function drawBubble(ctx, x, y, r, t, alpha) {
  const a = Math.max(0, Math.min(1, alpha == null ? 1 : alpha));
  if (a <= 0.01) return;
  ctx.save();
  ctx.globalAlpha = a;
  const rr = r * (1 + 0.03 * Math.sin(t * 2.4));
  const g = ctx.createRadialGradient(x - rr * 0.35, y - rr * 0.35, rr * 0.1, x, y, rr);
  g.addColorStop(0, 'rgba(255,255,255,0.10)'); g.addColorStop(0.75, 'rgba(170,220,255,0.10)'); g.addColorStop(1, 'rgba(150,210,255,0.38)');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, rr, 0, TAU); ctx.fill();
  ctx.strokeStyle = 'rgba(200,235,255,0.75)'; ctx.lineWidth = Math.max(1.5, rr * 0.03); ctx.shadowColor = '#a8dcff'; ctx.shadowBlur = 12;
  ctx.beginPath(); ctx.arc(x, y, rr, 0, TAU); ctx.stroke();
  ctx.shadowBlur = 0;
  ctx.strokeStyle = 'rgba(255,255,255,0.7)'; ctx.lineWidth = Math.max(1, rr * 0.04);   // the glint
  ctx.beginPath(); ctx.arc(x, y, rr * 0.82, Math.PI * 1.1, Math.PI * 1.45); ctx.stroke();
  const hue = (t * 40) % 360;                                                           // a soft rainbow sheen drifting round the rim
  ctx.strokeStyle = `hsla(${hue},90%,75%,0.35)`; ctx.lineWidth = Math.max(1, rr * 0.025);
  ctx.beginPath(); ctx.arc(x, y, rr * 0.96, t, t + 1.4); ctx.stroke();
  ctx.restore();
}

function sparkle(ctx, x, y, r, col) {
  if (r <= 0) return;
  ctx.fillStyle = col; ctx.beginPath();
  for (let i = 0; i < 8; i++) { const a = (i * Math.PI) / 4, rr = i % 2 ? r * 0.35 : r; ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
  ctx.closePath(); ctx.fill();
}
