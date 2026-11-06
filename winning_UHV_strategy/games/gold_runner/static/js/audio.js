// audio.js - Golden Gravity: the sound of Ledger Street. WebAudio only; every sound is synthesised here (no audio files).
// Owner: F-AUDIO. Spec: CONTRACT.md §8.5, REQUIREMENTS.md §4 (sound bible: "nothing is informative by sound alone; everything sounds
// like what it is"). Taste: warm, 1920s-tinged, cartoon-physical, never shrill. Every tonal sound is in G major pentatonic
// (G A B D E): coins, pings, chimes, stakes, horns and the tether all sit on it, so stacks stay consonant (the bells keep
// their own inharmonic bronze partials, minor third included - that is what makes them bells).
//
// API (CONTRACT §8.5):
//   import { Audio } from './audio.js'          (also: import Audio from './audio.js'  /  import * as Audio from './audio.js')
//   Audio.init()                  call on the first user gesture; safe to call any number of times (re-resumes a suspended context)
//   Audio.muted                   getter (and setter) - mirrors setMuted
//   Audio.setMuted(bool)          fades the master; while muted play() is a no-op and the context is suspended (zero CPU)
//   Audio.setVolume(0..1)         master volume (default 0.8)
//   Audio.play(name, opts) -> bool  true when a voice started; false (silently) before init, while muted/suspended, when rate-limited,
//                                 or for an unknown name. Never throws.
//   Audio.setTether(0..1)         continuous rising bass hum (the rope to the anvil); exactly silent at 0. Cheap to call every frame.
//   Audio.setAmbience(env)        weather beds with crossfade. env = the world env of CONTRACT §8.3 ({weather, vol, session, night,
//                                 freeze, golden_hour, wooden, replay, ...}), or snap.market, or a whole snapshot, or a bare string
//                                 'dead'|'calm'|'active'|'storm'; null / 'off' = silence. Change-detected: cheap to call every frame.
//   Calls made before init() are remembered (mute, volume, tether, ambience) and applied when init() runs.
// Extras (optional): Audio.event(ev) maps a server event (CONTRACT §7.3) to its sound; Audio.duck(amount, secs); Audio.stopAll();
//   Audio.state(); Audio.NAMES (the 29 contract names); Audio.EXTRAS; Audio.render(...) offline render used by gallery_audio.html.
//
// play(name, opts) names (CONTRACT §8.5): footstep pistons bell anvil refused rat ping machete chime balloon fold thud chain needle
//   gunshot cash coin cough creak whoosh thunder molasses haggle wall stake page cards collector tick
// extra names: flap (split-flap riffle) click (soft cancel) clunk (bell rope) confirm (hold ring complete) whistle tackle stamp barrel
//   crane duck needle_drop (reconnect) klaxon trolley pigeons ticker (street ambience events)
// aliases: eject->balloon shavings->ping freeze->needle reconnect/unfreeze->needle_drop lightning->thunder step->footstep clang->anvil
//   shot/pistol->gunshot blunderbuss->cash bubble->molasses laugh->haggle bricks->wall shuffle->cards flip->page clack->tick
//
// opts (all optional):  vol 0..2 (alias gain/volume)   pan -1..1  (or x 0..1 = screen position)   pitch (alias rate) multiplier
//   delay s   when (AudioContext time)   intensity 0..1
//   footstep {intensity, wooden}   tick {tock}   pistons {amount 0..1 = size of the tilt change, dir +1 up / -1 down}
//   bell {session:'london'|'newyork'}   anvil {ok:false -> refused}   wall {ok:false -> refused, n bricks}
//   haggle {ok:true = ho-ho-HO (tag raised) | false = wah-wah (waved off)}   coin {step: profit step, climbs the pentatonic}
//   ping {step}   chime {step}   stake {golden}   rat {n snips}   thunder {dist 0 near .. 1 far, near:true}   molasses {n}
//   whoosh {dir, speed}   page {dir}   cash {n coins}   creak {iron}
//
// Engineering: every recipe builds a small node graph on any BaseAudioContext, so the realtime game and the offline self-test
// (gallery_audio.html) run the same code. Hot sounds (footsteps, ticks, coin clinks) are pre-synthesised into tiny buffers: one
// footstep = 3 nodes. Per-sound rate limits + voice caps + a global voice cap with priority stealing: 200 footsteps a second cost
// ~20 voices, the rest return after one comparison (and their energy accents the next step). Master: warm shelf -> glue
// compressor -> limiter -> bounded soft clip (|out| <= 0.97 by construction) -> volume/mute.

const NO = Object.freeze({});
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
const lerp = (a, b, t) => a + (b - a) * t;

export const NAMES = Object.freeze(['footstep', 'pistons', 'bell', 'anvil', 'refused', 'rat', 'ping', 'machete', 'chime', 'balloon',
  'fold', 'thud', 'chain', 'needle', 'gunshot', 'cash', 'coin', 'cough', 'creak', 'whoosh', 'thunder', 'molasses', 'haggle', 'wall',
  'stake', 'page', 'cards', 'collector', 'tick']);
export const EXTRAS = Object.freeze(['flap', 'click', 'clunk', 'confirm', 'whistle', 'tackle', 'stamp', 'barrel', 'crane', 'duck',
  'needle_drop', 'klaxon', 'trolley', 'pigeons', 'ticker']);
const ALIAS = {
  step: 'footstep', steps: 'footstep', footsteps: 'footstep', piston: 'pistons', tilt: 'pistons', clang: 'anvil', shot: 'gunshot',
  pistol: 'gunshot', shoot: 'gunshot', blunderbuss: 'cash', eject: 'balloon', hiss: 'balloon', shavings: 'ping', glass: 'ping',
  foldup: 'fold', fold_up: 'fold', link: 'chain', freeze: 'needle', unfreeze: 'needle_drop', reconnect: 'needle_drop',
  lightning: 'thunder', rumble: 'thunder', bubble: 'molasses', pit: 'molasses', laugh: 'haggle', horn: 'haggle', brick: 'wall',
  bricks: 'wall', shuffle: 'cards', flip: 'page', clack: 'tick', clock: 'tick', lock: 'collector',
};

// ------------------------------------------------------------------------------------------------ tuning constants (master)
const MAX_VOICES = 48;          // global voice cap
const VERB_RETURN = 0.55;       // reverb return level
const TRIM_GLUE = 0.72;         // cancels the glue compressor's automatic makeup gain (Chrome applies one)
const TRIM_LIM = 0.84;          // cancels the limiter's makeup gain
const WARMUP_S = 0.6;           // compressor settling time after the context starts (see buildMaster)
const COMP_DELAY = 0.012;       // two compressors x 6 ms look-ahead: the bypass is delayed to match
const AMB_LEVEL = 0.13;         // ambience beds sit far under the action
const CLIP_RANGE = 1.6;         // the soft clip curve covers |x| <= 1.6
const CLIP_KNEE = 0.66;         // linear (uncoloured) below this
const CLIP_MAX = 0.97;          // hard bound on the output

// ------------------------------------------------------------------------------------------------ small pure helpers
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const PENTA = [0, 2, 4, 7, 9];                 // G major pentatonic, semitones above G
function penta(step, base) {                  // base = a G (e.g. 783.99 = G5); step 0 = base, 1 = A, 2 = B, 3 = D, 4 = E, 5 = G'
  const o = Math.floor(step / 5), i = step - 5 * o;
  return base * Math.pow(2, o + PENTA[i] / 12);
}
function volCurve(v) { return Math.pow(clamp(v, 0, 1), 1.5); }

// JS-side DSP for pre-synthesised buffers (RBJ biquads, one-poles)
function biq(type, f, Q, sr) {
  const w = 2 * Math.PI * Math.min(f, sr * 0.45) / sr, cs = Math.cos(w), sn = Math.sin(w), al = sn / (2 * Q);
  let b0, b1, b2;
  if (type === 'lp') { b0 = (1 - cs) / 2; b1 = 1 - cs; b2 = b0; } else if (type === 'hp') { b0 = (1 + cs) / 2; b1 = -(1 + cs); b2 = b0; } else { b0 = al; b1 = 0; b2 = -al; }
  const a0 = 1 + al;
  return [b0 / a0, b1 / a0, b2 / a0, (-2 * cs) / a0, (1 - al) / a0];
}
function filt(x, k) {
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  for (let i = 0; i < x.length; i++) {
    const x0 = x[i], y0 = k[0] * x0 + k[1] * x1 + k[2] * x2 - k[3] * y1 - k[4] * y2;
    x2 = x1; x1 = x0; y2 = y1; y1 = y0; x[i] = y0;
  }
  return x;
}
function onePoleLP(x, fc, sr) { const k = Math.exp(-2 * Math.PI * fc / sr); let y = 0; for (let i = 0; i < x.length; i++) { y = x[i] * (1 - k) + y * k; x[i] = y; } return x; }
function onePoleHP(x, fc, sr) { const k = Math.exp(-2 * Math.PI * fc / sr); let y = 0, p = 0; for (let i = 0; i < x.length; i++) { const v = x[i]; y = k * (y + v - p); p = v; x[i] = y; } return x; }
function peakOf(x) { let m = 0; for (let i = 0; i < x.length; i++) { const a = Math.abs(x[i]); if (a > m) m = a; } return m; }
function normPeak(x, p) { const m = peakOf(x); if (m > 0) { const k = p / m; for (let i = 0; i < x.length; i++) x[i] *= k; } return x; }
function rmsOf(x) { let s = 0; for (let i = 0; i < x.length; i++) s += x[i] * x[i]; return Math.sqrt(s / Math.max(1, x.length)); }
function fadeOut(x, sr, secs) { const n = Math.min(x.length, Math.floor(sr * secs)); for (let i = 0; i < n; i++) x[x.length - 1 - i] *= i / n; return x; }
function removeDC(x) { let m = 0; for (let i = 0; i < x.length; i++) m += x[i]; m /= x.length; for (let i = 0; i < x.length; i++) x[i] -= m; return x; }
// make a loopable buffer: x has n + F samples; blend the extra tail into the head and drop it
function seamLoop(x, F) { const n = x.length - F, y = new Float32Array(n); y.set(x.subarray(0, n)); for (let i = 0; i < F; i++) { const t = i / F; y[i] = x[i] * t + x[n + i] * (1 - t); } return y; }

const NAN_SAFE = (v, d) => (Number.isFinite(v) ? v : d);

// ------------------------------------------------------------------------------------------------ the engine (one per context)
class Engine {
  constructor(ctx, { offline = false, seed = 1, master = true, verb = true, warmup = true } = {}) {
    this.ctx = ctx; this.offline = offline;
    this.rnd = offline ? mulberry32(seed) : Math.random;
    this.look = offline ? 0 : 0.012;            // realtime lookahead so envelopes start on time
    this._noise = {}; this._atoms = {}; this._bed = {}; this._ir = null;
    this.voices = []; this.lastT = Object.create(null);
    this.stepDebt = 0; this.stepRate = 0; this.stepT = -1e9; this.foot = 1; this.tickFlip = false;
    this.started = 0; this.dropped = 0; this.maxLive = 0; this.errors = [];
    this.muted = false; this.volume = 0.8; this.tension = 0; this.teth = null;
    this.resumeUntil = 0;   // performance.now() deadline: while a resume WE requested is pending, play() may schedule
    this.beds = null; this.ambKey = null; this.amb = null; this.ambNext = {}; this.prevFreeze = false;
    this.buildMaster(master, verb, warmup);
  }
  warm() {   // pre-build the hot buffers (called right after init, off the gesture's critical path)
    for (const k of ['white', 'pink', 'brown']) this.noiseBuf(k);
    for (const k of ['step', 'stepwood', 'tick', 'clink']) this.atom(k, 0);
  }

  // ---------------------------------------------------------------- graph helpers
  g(v = 1, dest = null) { const n = this.ctx.createGain(); n.gain.value = v; if (dest) n.connect(dest); return n; }
  f(type, freq, Q = 0.707, dest = null) {
    const b = this.ctx.createBiquadFilter(); b.type = type; b.frequency.value = Math.min(freq, this.ctx.sampleRate * 0.45); b.Q.value = Q;
    if (dest) b.connect(dest); return b;
  }
  o(type, freq, T, end, dest = null) {
    const o = this.ctx.createOscillator(); o.type = type; o.frequency.setValueAtTime(freq, T);
    if (dest) o.connect(dest); o.start(T); if (end != null) o.stop(end); return o;
  }
  n(kind, T, end, dest = null) {
    const s = this.ctx.createBufferSource(), b = this.noiseBuf(kind); s.buffer = b; s.loop = true;
    if (dest) s.connect(dest); s.start(T, this.rnd() * (b.duration - 0.2)); if (end != null) s.stop(end); return s;
  }
  pan(dest, v = 0) { const p = this.ctx.createStereoPanner(); p.pan.value = clamp(v, -1, 1); p.connect(dest); return p; }
  sweep(param, v0, v1, T, d, lin = false) {
    param.setValueAtTime(v0, T);
    if (lin) param.linearRampToValueAtTime(v1, T + d); else param.exponentialRampToValueAtTime(Math.max(1e-4, v1), T + d);
  }
  // percussive envelope: 0 -> peak in a, hold, exponential decay reaching -60 dB after d60
  env(p, T, peak, a, d60, hold = 0) {
    p.setValueAtTime(0, T); p.linearRampToValueAtTime(peak, T + a);
    if (hold > 0) p.setValueAtTime(peak, T + a + hold);
    p.setTargetAtTime(0, T + a + hold, d60 / 6.9);
    return T + a + hold + d60;
  }
  // a bank of decaying sines (bells, anvils, chimes, glass). parts: [ratio, amp, T60, beatHz]. Random phases, warmth ceiling 9.5 kHz.
  modal(dest, T, f0, parts, { attack = 0.002 } = {}) {
    const top = Math.min(9500, this.ctx.sampleRate * 0.45); let end = T;
    for (const [ratio, amp, t60, beat = 0] of parts) {
      const fr = f0 * ratio; if (fr > top || amp <= 0) continue;
      const g = this.g(0, dest), e = T + attack + t60 + 0.02;
      const mk = (freq, lvl) => { const o = this.ctx.createOscillator(); o.frequency.value = freq; o.connect(lvl === 1 ? g : this.g(lvl, g)); o.start(Math.max(0, T - this.rnd() / freq)); o.stop(e); };
      if (beat) { mk(fr, 0.6); mk(fr + beat, 0.4); } else mk(fr, 1);
      this.env(g.gain, T, amp, attack, t60);
      end = Math.max(end, e);
    }
    return end;
  }
  // filtered noise burst. White-noise bursts are roughly normalised so `peak` is about the real peak.
  burst(dest, T, { kind = 'white', type = 'bandpass', f = 1000, Q = 1, f1 = 0, sweep = 0, peak = 0.5, a = 0.001, d = 0.05, hold = 0, hp = 0, lp = 0 } = {}) {
    const end = T + a + hold + d, sr = this.ctx.sampleRate;
    let comp = 1;
    if (kind === 'white') {
      const bw = type === 'bandpass' ? f / Q : type === 'lowpass' ? f * 1.1 : sr * 0.5 - f;
      comp = clamp(1 / (1.85 * Math.sqrt(Math.max(1, 1.57 * bw) / (sr * 0.5))), 0.5, 4);
    }
    const s = this.n(kind, T, end + 0.03, null); let x = s;
    if (hp) { const h = this.f('highpass', hp, 0.7); x.connect(h); x = h; }
    const fl = this.f(type, f, Q); x.connect(fl); x = fl;
    if (f1) this.sweep(fl.frequency, f, f1, T, sweep || d);
    if (lp) { const l = this.f('lowpass', lp, 0.7); x.connect(l); x = l; }
    const g = this.g(0, dest); x.connect(g);
    this.env(g.gain, T, peak * comp, a, d, hold);
    return end;
  }
  // pitch-dropping sine thump (weight, body, impacts)
  thump(dest, T, { f0 = 120, f1 = 50, peak = 0.5, a = 0.002, d = 0.15, drop = 0, type = 'sine' } = {}) {
    const g = this.g(0, dest), e = T + a + d + 0.02;
    const o = this.o(type, f0, T, e, g);
    o.frequency.exponentialRampToValueAtTime(Math.max(1, f1), T + (drop || d * 0.5));
    this.env(g.gain, T, peak, a, d);
    return e;
  }
  // paper/card grains: one noise chain, a gain envelope of many fast grains (no per-grain nodes)
  crinkle(dest, T, len, { density = 50, f = [1800, 5000], Q = 1.4, peak = [0.05, 0.3], decay = [0.004, 0.014], gaps = null } = {}) {
    const r = this.rnd, end = T + len;
    const s = this.n('white', T, end + 0.08, null), bp = this.f('bandpass', f[0], Q), hp = this.f('highpass', 650, 0.7), g = this.g(0, dest);
    s.connect(bp); bp.connect(hp); hp.connect(g);
    g.gain.setValueAtTime(0, T); bp.frequency.setValueAtTime(f[0], T);
    const comp = 2.2;
    let t = T + 0.001 + r() * 0.01;
    while (t < end) {
      const rel = t - T;
      if (!gaps || !gaps.some(([a, b]) => rel >= a && rel < b)) {
        const pk = lerp(peak[0], peak[1], r() * r()) * comp, d = lerp(decay[0], decay[1], r());
        bp.frequency.setValueAtTime(lerp(f[0], f[1], r()), t);
        g.gain.setTargetAtTime(pk, t, 0.0003); g.gain.setTargetAtTime(0, t + 0.0012, d / 5);
      }
      t += -Math.log(1 - r() * 0.995) / density;
    }
    g.gain.setTargetAtTime(0, end, 0.004);
    return end + 0.05;
  }
  atomPlay(kind, i, dest, T, rate = 1, gain = 1) {
    const b = this.atom(kind, i), s = this.ctx.createBufferSource(); s.buffer = b; s.playbackRate.value = rate;
    s.connect(this.g(gain, dest)); s.start(T);
    return T + b.duration / rate;
  }
  clink(dest, T, i, rate = 1, gain = 0.3) { return this.atomPlay('clink', i, dest, T, rate, gain); }

  // ---------------------------------------------------------------- generated buffers
  noiseBuf(kind) {
    if (this._noise[kind]) return this._noise[kind];
    const c = this.ctx, sr = c.sampleRate, n = Math.floor(sr * 2.5), F = Math.floor(sr * 0.03), r = mulberry32(kind.length * 977 + 13);
    const b = c.createBuffer(2, n, sr);
    for (let ch = 0; ch < 2; ch++) {
      const x = new Float32Array(n + F);
      if (kind === 'pink') {
        let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
        for (let i = 0; i < x.length; i++) {
          const w = r() * 2 - 1;
          b0 = 0.99886 * b0 + w * 0.0555179; b1 = 0.99332 * b1 + w * 0.0750759; b2 = 0.969 * b2 + w * 0.153852;
          b3 = 0.8665 * b3 + w * 0.3104856; b4 = 0.55 * b4 + w * 0.5329522; b5 = -0.7616 * b5 - w * 0.016898;
          x[i] = b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362; b6 = w * 0.115926;
        }
      } else if (kind === 'brown') {
        let l = 0; for (let i = 0; i < x.length; i++) { l = (l + 0.02 * (r() * 2 - 1)) / 1.02; x[i] = l; }
      } else { for (let i = 0; i < x.length; i++) x[i] = r() * 2 - 1; }
      removeDC(x);
      const y = seamLoop(x, F);
      if (kind !== 'white') { const k = 0.25 / Math.max(1e-6, rmsOf(y)); for (let i = 0; i < y.length; i++) y[i] *= k; }
      b.getChannelData(ch).set(y);
    }
    return (this._noise[kind] = b);
  }
  atom(kind, i) {
    const arr = this._atoms[kind] || (this._atoms[kind] = this.makeAtoms(kind));
    return arr[((i % arr.length) + arr.length) % arr.length];
  }
  makeAtoms(kind) {
    const r = mulberry32(kind.charCodeAt(0) * 131 + kind.length), out = [];
    if (kind === 'step') for (let v = 0; v < 8; v++) out.push(this.synthStep(r, false));
    else if (kind === 'stepwood') for (let v = 0; v < 6; v++) out.push(this.synthStep(r, true));
    else if (kind === 'tick') for (let v = 0; v < 6; v++) out.push(this.synthTick(r, v >= 3));
    else for (let v = 0; v < 6; v++) out.push(this.synthClink(r));
    return out;
  }
  toBuf(chans) {
    const b = this.ctx.createBuffer(chans.length, chans[0].length, this.ctx.sampleRate);
    chans.forEach((x, i) => b.getChannelData(i).set(x)); return b;
  }
  synthStep(r, wood) {
    const sr = this.ctx.sampleRate, n = Math.floor(sr * (wood ? 0.2 : 0.17));
    const heel = new Float32Array(n), toe = new Float32Array(n), body = new Float32Array(n), x = new Float32Array(n);
    const hd = wood ? 0.035 : 0.014 + 0.01 * r();
    for (let i = 0; i < n; i++) { const t = i / sr; heel[i] = (r() * 2 - 1) * Math.exp(-6.9 * t / hd) * Math.min(1, t / 0.0008); }
    filt(heel, biq('bp', wood ? 650 + 250 * r() : 1400 + 900 * r(), wood ? 1.6 : 1.1, sr)); filt(heel, biq('hp', wood ? 180 : 450, 0.7, sr)); normPeak(heel, 1);
    const t0 = (wood ? 0.05 : 0.038) + 0.03 * r(), td = 0.01 + 0.01 * r();
    for (let i = Math.floor(t0 * sr); i < n; i++) { const t = i / sr - t0; toe[i] = (r() * 2 - 1) * Math.exp(-6.9 * t / td) * Math.min(1, t / 0.001); }
    filt(toe, biq('bp', wood ? 950 : 2600 + 900 * r(), 1.2, sr)); normPeak(toe, 1);
    const f0 = (wood ? 185 : 105) * (0.9 + 0.2 * r()); let ph = 0;
    for (let i = 0; i < n; i++) {
      const t = i / sr, fr = f0 * (0.7 + 0.3 * Math.exp(-t / 0.015)); ph += 2 * Math.PI * fr / sr;
      body[i] = Math.sin(ph) * Math.exp(-6.9 * t / (wood ? 0.09 : 0.06)) * Math.min(1, t / 0.0015);
    }
    const wt = wood ? 0.3 : 0.28 + 0.1 * r(), wb = wood ? 0.75 : 0.5;
    for (let i = 0; i < n; i++) x[i] = heel[i] + toe[i] * wt + body[i] * wb;
    fadeOut(x, sr, 0.012); normPeak(x, 0.9);
    return this.toBuf([x]);
  }
  synthTick(r, tock) {
    const sr = this.ctx.sampleRate, n = Math.floor(sr * 0.07), x = new Float32Array(n), ck = new Float32Array(n);
    for (let i = 0; i < Math.floor(sr * 0.0015); i++) ck[i] = (r() * 2 - 1) * (1 - i / (sr * 0.0015));
    filt(ck, biq('hp', 2500, 0.7, sr)); normPeak(ck, 1);
    const f1 = (tock ? 1750 : 2550) * (0.97 + 0.06 * r()), fb = tock ? 520 : 760;
    const p1 = r() * 6.28, p2 = r() * 6.28;
    for (let i = 0; i < n; i++) {
      const t = i / sr;
      x[i] = ck[i] * 0.7 + Math.sin(6.2832 * f1 * t + p1) * Math.exp(-6.9 * t / 0.018) + 0.5 * Math.sin(6.2832 * f1 * 1.57 * t + p2) * Math.exp(-6.9 * t / 0.009)
        + 0.35 * Math.sin(6.2832 * fb * t) * Math.exp(-6.9 * t / 0.025) * Math.min(1, t / 0.0008);
    }
    fadeOut(x, sr, 0.005); normPeak(x, 0.9);
    return this.toBuf([x]);
  }
  synthClink(r) {
    const sr = this.ctx.sampleRate, n = Math.floor(sr * 0.4), x = new Float32Array(n);
    const f = 1900 + 1500 * r(), R = [1, 1.506, 2.08, 2.68, 3.32], A = [1, 0.62, 0.45, 0.3, 0.2], D = [0.3, 0.22, 0.15, 0.1, 0.07];
    for (let k = 0; k < R.length; k++) {
      const fr = f * R[k]; if (fr > 9500) continue;
      const a = A[k] * (0.7 + 0.6 * r()), d = D[k] * (0.7 + 0.6 * r()), ph = r() * 6.28;
      for (let i = 0; i < n; i++) { const t = i / sr; x[i] += a * Math.sin(6.2832 * fr * t + ph) * Math.exp(-6.9 * t / d); }
    }
    for (let i = 0; i < Math.floor(sr * 0.0008); i++) x[i] = x[i] * (i / (sr * 0.0008)) + (r() * 2 - 1) * 0.5;
    fadeOut(x, sr, 0.01); normPeak(x, 0.9);
    return this.toBuf([x]);
  }
  bedBuf(kind) {
    if (this._bed[kind]) return this._bed[kind];
    const sr = this.ctx.sampleRate, r = mulberry32(kind.length * 7919 + 3), chans = [];
    if (kind === 'rain') {
      const n = Math.floor(sr * 4), F = Math.floor(sr * 0.05);
      for (let ch = 0; ch < 2; ch++) {
        const x = new Float32Array(n + F), body = new Float32Array(n + F);
        for (let i = 0; i < x.length; i++) { x[i] = r() * 2 - 1; body[i] = r() * 2 - 1; }
        onePoleHP(x, 700, sr); onePoleLP(x, 7000, sr); normPeak(x, 0.22);
        onePoleLP(body, 500, sr); onePoleLP(body, 500, sr); normPeak(body, 0.25);
        for (let i = 0; i < x.length; i++) x[i] += body[i];
        const drops = Math.floor(4 * 90);
        for (let k = 0; k < drops; k++) {
          const at = Math.floor(r() * n), a = 0.05 + 0.45 * Math.pow(r(), 3), fr = 1600 + 3200 * r(), tau = 0.0015 + 0.005 * r(), L = Math.floor(tau * 6 * sr);
          for (let i = 0; i < L; i++) { const t = i / sr; x[(at + i) % n] += a * Math.sin(6.2832 * fr * (1 - 0.3 * t / (tau * 6)) * t) * Math.exp(-t / tau); }
        }
        const y = seamLoop(x, F); normPeak(y, 0.9); chans.push(y);
      }
    } else if (kind === 'crickets') {
      const n = Math.floor(sr * 6), A = new Float32Array(n), B = new Float32Array(n);
      const chirps = (x, fr, every, jit, pulses, plen, gap) => {
        for (let t0 = r() * every; t0 < 6 - 0.3; t0 += every + (r() - 0.5) * jit) {
          for (let p = 0; p < pulses; p++) {
            const s = Math.floor((t0 + p * (plen + gap)) * sr), L = Math.floor(plen * sr), amp = 0.7 + 0.3 * r();
            for (let i = 0; i < L; i++) { const w = Math.sin(Math.PI * i / L); x[s + i] += amp * w * w * Math.sin(6.2832 * fr * (s + i) / sr); }
          }
        }
      };
      chirps(A, 4400, 0.62, 0.12, 3, 0.018, 0.014); chirps(B, 3950, 0.81, 0.2, 4, 0.014, 0.012);
      const L = new Float32Array(n), R = new Float32Array(n);
      for (let i = 0; i < n; i++) { L[i] = A[i] * 0.75 + B[i] * 0.3; R[i] = A[i] * 0.3 + B[i] * 0.75; }
      normPeak(L, 0.9); normPeak(R, 0.9); chans.push(L, R);
    } else {   // vinyl crackle (Time Freeze, replay)
      const n = Math.floor(sr * 4), F = Math.floor(sr * 0.03);
      for (let ch = 0; ch < 2; ch++) {
        const x = new Float32Array(n + F), hum = new Float32Array(n + F);
        for (let i = 0; i < x.length; i++) { x[i] = r() * 2 - 1; hum[i] = r() * 2 - 1; }
        onePoleHP(x, 2500, sr); normPeak(x, 0.035);
        onePoleLP(hum, 120, sr); onePoleLP(hum, 120, sr); normPeak(hum, 0.05);
        for (let i = 0; i < x.length; i++) x[i] += hum[i];
        const pops = Math.floor(4 * 28);
        for (let k = 0; k < pops; k++) {
          const at = Math.floor(r() * n), a = (0.06 + 0.7 * Math.pow(r(), 4)) * (r() < 0.5 ? -1 : 1), fr = 2000 + 4000 * r(), tau = 0.0002 + 0.0004 * r();
          for (let i = 0; i < Math.floor(tau * 8 * sr); i++) { const t = i / sr; x[(at + i) % n] += a * Math.cos(6.2832 * fr * t) * Math.exp(-t / tau); }
        }
        for (let k = 0; k < 4; k++) {   // a few soft thumps of dust
          const at = Math.floor(r() * n), a = 0.25 + 0.2 * r();
          for (let i = 0; i < Math.floor(0.012 * sr); i++) { const t = i / sr; x[(at + i) % n] += a * Math.sin(6.2832 * 90 * t) * Math.exp(-t / 0.003); }
        }
        const y = seamLoop(x, F); normPeak(y, 0.9); chans.push(y);
      }
    }
    return (this._bed[kind] = this.toBuf(chans));
  }
  irBuf() {   // the bank's marble hall: decorrelated stereo tail that darkens as it decays, plus early reflections
    if (this._ir) return this._ir;
    const sr = this.ctx.sampleRate, secs = 3.2, rt = 2.6, n = Math.floor(sr * secs), r = mulberry32(4242);
    const chans = [];
    for (let ch = 0; ch < 2; ch++) {
      const d = new Float32Array(n); let lp = 0, dec = 1; const step = Math.exp(-6.9 / (rt * sr));
      for (let i = 0; i < n; i++) {
        const t = i / sr, k = 0.15 + 0.78 * Math.min(1, t / 2.2);
        lp += (1 - k) * ((r() * 2 - 1) - lp);
        const fade = t < 0.008 ? 0 : t < 0.03 ? (t - 0.008) / 0.022 : 1;
        d[i] = lp * Math.sqrt((1 + k) / (1 - k)) * dec * fade; dec *= step;
      }
      [[0.009, 0.7], [0.0137, -0.5], [0.0191, 0.45], [0.0263, -0.38], [0.0347, 0.3], [0.0452, -0.25], [0.061, 0.18], [0.083, -0.12]]
        .forEach(([s, gg], j) => { const i = Math.floor((s + ch * 0.0017 * (j % 3)) * sr); if (i < n) d[i] += gg * 0.6; });
      chans.push(d);
    }
    return (this._ir = this.toBuf(chans));
  }

  // ---------------------------------------------------------------- master chain
  buildMaster(master, verb, warmup = true) {
    const c = this.ctx;
    this.mix = c.createGain();
    this.sfx = this.g(1, this.mix);
    this.tetherBus = this.g(1, this.mix);
    this.ambIn = c.createGain();
    this.ambFilt = this.f('lowpass', 16000, 0.5);
    this.ambDuck = this.g(1);
    this.ambLevel = this.g(AMB_LEVEL, this.mix);
    this.ambIn.connect(this.ambFilt); this.ambFilt.connect(this.ambDuck); this.ambDuck.connect(this.ambLevel);
    if (verb) {
      this.verbIn = c.createGain();
      const cv = c.createConvolver(); cv.normalize = true; cv.buffer = this.irBuf();
      this.verbIn.connect(cv); cv.connect(this.g(VERB_RETURN, this.mix));
    } else this.verbIn = null;
    const warm = this.f('highshelf', 7000, 0.7); warm.gain.value = -4; this.mix.connect(warm);
    this.out = c.createGain(); this.out.gain.value = volCurve(this.volume);
    if (master) {
      const trim = this.g(TRIM_GLUE); warm.connect(trim);
      const glue = c.createDynamicsCompressor();
      glue.threshold.value = -10; glue.knee.value = 6; glue.ratio.value = 2.5; glue.attack.value = 0.005; glue.release.value = 0.2;
      const trim2 = this.g(TRIM_LIM);
      const lim = c.createDynamicsCompressor();
      lim.threshold.value = -3; lim.knee.value = 0; lim.ratio.value = 20; lim.attack.value = 0.001; lim.release.value = 0.1;
      const pre = this.g(1 / CLIP_RANGE);
      const clip = c.createWaveShaper(); clip.curve = clipCurve(); clip.oversample = 'none';
      // Chrome's DynamicsCompressor starts with its detector at 0 and slams the gain shut for the first few hundred ms of a
      // context's life (measured: a footstep at 0.02 s came out 14 dB down). So for the first WARMUP_S the signal takes a bypass
      // (time-aligned with the compressors' 2 x 6 ms look-ahead, still through the bounded soft clip), then crossfades in.
      const compOut = this.g(0), byp = this.g(1), dl = c.createDelay(0.05); dl.delayTime.value = COMP_DELAY;
      trim.connect(glue); glue.connect(trim2); trim2.connect(lim); lim.connect(compOut); compOut.connect(pre);
      warm.connect(dl); dl.connect(byp); byp.connect(pre);
      pre.connect(clip); clip.connect(this.out);
      const t0 = c.currentTime + (warmup ? WARMUP_S : 0);
      compOut.gain.setValueAtTime(0, t0); compOut.gain.linearRampToValueAtTime(1, t0 + 0.05);
      byp.gain.setValueAtTime(1, t0); byp.gain.linearRampToValueAtTime(0, t0 + 0.05);
      this.warmUntil = t0 + 0.05;
    } else { warm.connect(this.out); this.warmUntil = 0; }
    this.out.connect(c.destination);
  }
  at(when) { const now = this.ctx.currentTime + this.look; return when != null && when > now ? when : now; }
  setVolume(v, when) {
    v = clamp(NAN_SAFE(+v, 0.8), 0, 1); if (Math.abs(v - this.volume) < 0.004 && this._volSet) return;
    this.volume = v; this._volSet = true;
    const T = this.at(when); this.out.gain.cancelScheduledValues(T); this.out.gain.setTargetAtTime(this.muted ? 0 : volCurve(v), T, 0.03);
  }
  setMuted(m, when) {
    m = !!m; if (m === this.muted) return; this.muted = m;
    const T = this.at(when); this.out.gain.cancelScheduledValues(T); this.out.gain.setTargetAtTime(m ? 0 : volCurve(this.volume), T, 0.04);
  }
  duck(amount = 0.5, secs = 1.5, when) {
    const T = this.at(when), p = this.ambDuck.gain;
    p.cancelScheduledValues(T); p.setTargetAtTime(clamp(amount, 0, 1), T, 0.04); p.setTargetAtTime(1, T + secs, Math.max(0.1, secs / 3));
  }
  // linear move with an exact anchor at T (so a ramp to 0 really reaches 0)
  lin(param, v, T, dur) {
    if (param.cancelAndHoldAtTime) param.cancelAndHoldAtTime(T); else { param.cancelScheduledValues(T); param.setValueAtTime(param.value, T); }
    param.linearRampToValueAtTime(v, T + dur);
  }
  smooth(param, v, T, tc) { param.cancelScheduledValues(T); param.setTargetAtTime(v, T, tc); }

  // ---------------------------------------------------------------- voices
  voice(name, R, o, T) {
    const c = this.ctx;
    const vol = NAN_SAFE(+(o.vol ?? o.gain ?? o.volume ?? 1), 1);
    const g = c.createGain(); g.gain.value = (R.gain ?? 0.5) * clamp(vol, 0, 2);
    let pan = o.pan != null ? +o.pan : o.x != null ? (+o.x - 0.5) * 1.4 : 0;
    if (R.panJitter) pan += (this.rnd() - 0.5) * 2 * R.panJitter;
    pan = clamp(NAN_SAFE(pan, 0), -1, 1);
    const bus = o.bus === 'amb' ? this.ambIn : this.sfx;
    const v = { name, prio: R.prio ?? 3, t0: T, end: T + (R.dur || 1), g, p: null, s: null };
    if (Math.abs(pan) > 0.01) { v.p = this.pan(bus, pan); g.connect(v.p); } else g.connect(bus);
    const send = o.verb ?? R.verb ?? 0;
    if (send > 0 && this.verbIn) { v.s = this.g(send, this.verbIn); g.connect(v.s); }
    return v;
  }
  admit(name, R, T) {
    let same = 0, live = 0, oldest = null, victim = null;
    for (const v of this.voices) {
      if (v.end <= T) continue;
      live++;
      if (v.name === name) { same++; if (!oldest || v.t0 < oldest.t0) oldest = v; }
      if (v.prio <= (R.prio ?? 3) && (!victim || v.prio < victim.prio || (v.prio === victim.prio && v.t0 < victim.t0))) victim = v;
    }
    if (same >= (R.max ?? 4)) { if (R.steal && oldest) { this.kill(oldest, T); live--; } else return false; }
    if (live >= MAX_VOICES) { if (victim && victim.end > T) this.kill(victim, T); else return false; live--; }
    this.maxLive = Math.max(this.maxLive, live + 1);
    return true;
  }
  kill(v, T) { const p = v.g.gain; p.cancelScheduledValues(T); p.setTargetAtTime(0, T, 0.008); v.end = Math.min(v.end, T + 0.06); }
  sweepVoices(now) {
    if (this.offline) { if (this.voices.length > 256) this.voices = this.voices.filter((v) => v.end > now); return; }
    let k = 0;
    for (const v of this.voices) {
      if (v.end < now - 0.1) { try { v.g.disconnect(); if (v.p) v.p.disconnect(); if (v.s) v.s.disconnect(); } catch (e) { /* already gone */ } } else this.voices[k++] = v;
    }
    this.voices.length = k;
  }
  stopAll(when) { const T = this.at(when); for (const v of this.voices) if (v.end > T) this.kill(v, T); }

  play(name, o, when) {
    o = o || NO;
    const n = RECIPES[name] ? name : ALIAS[name], R = n && RECIPES[n];
    if (!R) return false;
    const c = this.ctx;
    if (!this.offline && (this.muted || (c.state !== 'running' && !(this.resumeUntil > performance.now())))) return false;
    let T = this.at(when ?? o.when);
    if (o.delay) T += clamp(+o.delay || 0, 0, 30);
    if (n === 'footstep') {   // event-rate estimate (calls per second, tau 0.8 s) - drives the sprint timbre
      const dt = Math.max(0, T - this.stepT); this.stepRate = this.stepRate * Math.exp(-dt / 0.8) + 1 / 0.8; this.stepT = T;
    }
    const last = this.lastT[n] ?? -1e9, gap = R.gap ?? 0.05;
    if (T >= last && T - last < gap) { if (n === 'footstep') this.stepDebt++; this.dropped++; return false; }   // fast path
    if (!this.offline && this.voices.length > 96) this.sweepVoices(c.currentTime);
    if (T < last) for (const v of this.voices) if (v.name === n && Math.abs(v.t0 - T) < gap) { this.dropped++; return false; }   // a voice scheduled ahead
    if (!this.admit(n, R, T)) { this.dropped++; return false; }
    const v = this.voice(n, R, o, T);
    let dur = R.dur || 1;
    try { dur = R.fn(this, v.g, T, o, this.rnd) || dur; } catch (e) { if (this.errors.length < 20) this.errors.push(n + ': ' + (e && e.message)); }
    v.end = T + dur + 0.05;
    this.lastT[n] = Math.max(last, T); this.voices.push(v); this.started++;
    if (R.duck && this.beds) this.duck(R.duck[0], R.duck[1], T);
    return true;
  }

  // ---------------------------------------------------------------- the tether (a rope to the anvil: rising bass hum)
  ensureTether() {
    if (this.teth) return this.teth;
    const T = this.ctx.currentTime;
    const g = this.g(0, this.tetherBus);          // the level; ramps to exactly 0
    const vib = this.g(1, g);                     // 1 +- tremolo (the vibrating rope)
    const lp = this.f('lowpass', 150, 1.4, vib);
    const o1 = this.o('sawtooth', 49, T, null, lp), o2 = this.o('sawtooth', 49 * 1.004, T, null, lp);
    const sub = this.o('sine', 49, T, null, this.g(0.9, vib));
    const trem = this.o('sine', 4, T, null, null), tremDepth = this.g(0, vib.gain); trem.connect(tremDepth);
    const strain = this.g(0, g);                  // rope fibres creaking when nearly taut
    const sn = this.ctx.createBufferSource(); sn.buffer = this.noiseBuf('pink'); sn.loop = true;
    sn.connect(this.f('bandpass', 880, 7, strain)); sn.start(T);
    return (this.teth = { g, lp, o1, o2, sub, trem, tremDepth, strain });
  }
  setTether(x, when) {
    x = clamp(NAN_SAFE(+x, 0), 0, 1);
    if (Math.abs(x - this.tension) < 0.01 && !(x === 0 && this.tension !== 0) && this._tethSet) return;
    this._tethSet = true;
    this.tension = x;
    if (x <= 0 && !this.teth) return;
    const te = this.ensureTether(), T = this.at(when), d = 0.12;
    const f = 49 * (1 + 0.5 * x);                 // G1 rising a fifth to D2 at full tension
    this.lin(te.g.gain, x <= 0 ? 0 : 0.085 * Math.pow(x, 1.25), T, d);
    this.lin(te.o1.frequency, f, T, d); this.lin(te.o2.frequency, f * 1.004, T, d); this.lin(te.sub.frequency, f, T, d);
    this.lin(te.lp.frequency, 220 + 900 * x * x, T, d);
    this.lin(te.trem.frequency, 4 + 10 * x, T, d);
    this.lin(te.tremDepth.gain, 0.32 * x, T, d);
    this.lin(te.strain.gain, Math.max(0, x - 0.55) * 1.2, T, d);
  }

  // ---------------------------------------------------------------- ambience beds (crossfaded) + street events
  ensureBeds() {
    if (this.beds) return this.beds;
    const T = this.ctx.currentTime, B = {};
    const loop = (buf, dest, off) => { const s = this.ctx.createBufferSource(); s.buffer = buf; s.loop = true; s.connect(dest); s.start(T, off); return s; };
    // wind: pink noise through a wandering band, slow swells; B.gust multiplies it for gusts
    B.wind = this.g(0, this.ambIn); B.gust = this.g(1, B.wind); const wAm = this.g(1, B.gust);
    const wbp = this.f('bandpass', 430, 1.5, this.f('lowpass', 1100, 0.7, wAm));
    loop(this.noiseBuf('pink'), wbp, 0.31);
    this.o('sine', 0.071, T, null, this.g(230, wbp.frequency));
    this.o('sine', 0.113, T, null, this.g(0.35, wAm.gain));
    // the street: distant traffic rumble (brown) + a crowd murmur band (pink) that breathes
    B.street = this.g(0, this.ambIn);
    B.streetLp = this.f('lowpass', 420, 0.7, B.street);
    loop(this.noiseBuf('brown'), B.streetLp, 0.77);
    B.murmur = this.g(0, B.street); const mAm = this.g(1, B.murmur);
    loop(this.noiseBuf('pink'), this.f('bandpass', 760, 0.9, this.f('lowpass', 2200, 0.7, mAm)), 1.43);
    this.o('sine', 0.17, T, null, this.g(0.3, mAm.gain));
    // rain (storm)
    B.rain = this.g(0, this.ambIn);
    loop(this.bedBuf('rain'), this.f('highpass', 220, 0.7, B.rain), 0);
    // crickets (night)
    B.crickets = this.g(0, this.ambIn);
    loop(this.bedBuf('crickets'), this.f('lowpass', 5200, 0.7, B.crickets), 0);
    // vinyl crackle (Time Freeze / replay) - after the freeze filter so it stays crisp
    B.crackle = this.g(0, this.ambLevel);
    loop(this.bedBuf('crackle'), B.crackle, 0);
    return (this.beds = B);
  }
  setAmbience(env, when) {
    const a = normEnv(env), key = ambKey(a);
    if (key === this.ambKey) return false;
    this.ambKey = key; this.amb = a;
    const B = this.ensureBeds(), T = this.at(when), tg = bedTargets(a);
    const tc = a.freeze !== this.prevFreeze ? 0.12 : 0.9; this.prevFreeze = a.freeze;
    for (const k of ['wind', 'street', 'murmur', 'rain', 'crickets', 'crackle']) this.smooth(B[k].gain, tg[k], T, tc);
    this.smooth(B.streetLp.frequency, tg.streetLp, T, tc);
    this.smooth(this.ambFilt.frequency, tg.filt, T, tc * 0.6);
    this.smooth(this.ambLevel.gain, tg.level * AMB_LEVEL, T, tc);
    return true;
  }
  // schedule street events in [from, to). Realtime: called every 200 ms with a 0.7 s horizon. Offline: once for the whole render.
  tickAmbience(from, to) {
    const a = this.amb;
    if (!a || this.muted || !this.beds) return;
    if (a.freeze) { this.ambNext = {}; return; }   // the street holds its breath
    const r = this.rnd, list = ambEvents(a), seen = {};
    for (const e of list) {
      seen[e.key] = 1;
      let t = this.ambNext[e.key];
      if (t == null) t = from + lerp(e.first[0], e.first[1], r());
      while (t < to) {
        if (t >= from - 0.05) {
          if (e.gust) this.gust(t, e.gust * (0.6 + 0.6 * r()));
          else this.play(e.name, Object.assign({ bus: 'amb', when: t, pan: (r() - 0.5) * 1.4 }, e.opts ? e.opts(r) : null));
        }
        t += lerp(e.every[0], e.every[1], r());
      }
      this.ambNext[e.key] = t;
    }
    for (const k of Object.keys(this.ambNext)) if (!seen[k]) delete this.ambNext[k];
  }
  gust(T, amount) {
    const p = this.beds.gust.gain; p.setTargetAtTime(1 + amount, T, 0.5); p.setTargetAtTime(1, T + 1.2 + amount, 0.9);
  }
  tick() {
    const now = this.ctx.currentTime;
    this.sweepVoices(now);
    this.tickAmbience(now + this.look, now + 0.7);
  }
}

// ------------------------------------------------------------------------------------------------ ambience tables
const WEATHERS = ['dead', 'calm', 'active', 'storm'];
function normEnv(env) {
  if (env == null || env === '' || env === 'off' || env === 'none') return { weather: 'off', off: true, vol: null, session: null, night: false, freeze: false, golden: false, wooden: false, replay: false };
  if (typeof env === 'string') return { weather: WEATHERS.includes(env) ? env : 'calm', vol: null, session: null, night: false, freeze: false, golden: false, wooden: false, replay: false };
  const m = env.market && typeof env.market === 'object' ? env.market : env;      // accepts a whole snapshot too
  const rd = env.round && typeof env.round === 'object' ? env.round : null;
  const w = String(m.weather ?? env.weather ?? 'calm');
  const session = m.session ?? env.session ?? null;
  return {
    weather: WEATHERS.includes(w) ? w : 'calm',
    vol: Number.isFinite(+(m.vol ?? env.vol)) && (m.vol ?? env.vol) != null ? clamp(+(m.vol ?? env.vol), 0, 1) : null,
    session,
    night: !!(env.night ?? (rd && rd.night)) || session === 'dead' || session === 'closed',
    freeze: !!(env.freeze ?? m.freeze),
    golden: !!(env.golden_hour ?? (rd && rd.golden_hour)),
    wooden: !!(env.wooden ?? (rd && rd.kind === 'wooden')),
    replay: !!(env.replay ?? (env.mode === 'replay')),
  };
}
function ambKey(a) {
  return [a.weather, a.vol == null ? '-' : Math.round(a.vol * 5), a.session || '-', a.night ? 1 : 0, a.freeze ? 1 : 0, a.golden ? 1 : 0, a.wooden ? 1 : 0, a.replay ? 1 : 0].join('|');
}
function bedTargets(a) {
  const W = a.weather, v = a.vol ?? { dead: 0.05, calm: 0.25, active: 0.55, storm: 0.95 }[W];
  const sess = { asia: 0.75, london: 1, newyork: 1.12, dead: 0.45, closed: 0.35 }[a.session] ?? 1;
  const t = { wind: 0, street: 0, murmur: 0, rain: 0, crickets: 0, crackle: 0, streetLp: 420, filt: 16000, level: 1 };
  if (a.off) return t;
  if (W === 'dead') { t.wind = 0.65; t.street = 0.1; t.streetLp = 260; }
  else if (W === 'calm') { t.wind = 0.1; t.street = 0.5 * sess; t.murmur = 0.22 * sess; t.streetLp = 420; }
  else if (W === 'active') { t.wind = 0.08; t.street = 0.62 * sess; t.murmur = 0.42 * sess; t.streetLp = 800 + 700 * v; }
  else { t.wind = 1.0 + 0.6 * v; t.street = 0.08; t.rain = 1.2 + 0.8 * v; t.streetLp = 300; }
  if (a.night) { if (W !== 'storm') t.crickets = 0.16; t.murmur *= 0.3; t.street *= 0.5; }
  if (a.wooden) t.filt = 3500;
  if (a.replay) t.crackle = 0.25;
  if (a.freeze) { t.filt = 520; t.level = 0.45; t.crackle = 0.85; }
  return t;
}
function ambEvents(a) {
  const W = a.weather, s = { asia: 0.7, london: 1, newyork: 1.15 }[a.session] ?? 1, ev = [];
  if (a.off) return ev;
  const k = (x) => x / s;   // busier sessions -> shorter gaps
  if (W === 'dead') {
    ev.push({ key: 'gust', gust: 0.9, every: [6, 12], first: [1, 5] });
    ev.push({ key: 'creak', name: 'creak', every: [18, 35], first: [6, 16], opts: () => ({ vol: 1.0, iron: true, verb: 0.35 }) });
  } else if (W === 'calm') {
    ev.push({ key: 'gust', gust: 0.4, every: [10, 20], first: [3, 8] });
    if (!a.night) {
      ev.push({ key: 'klaxon', name: 'klaxon', every: [k(22), k(45)], first: [4, 14], opts: () => ({ vol: 1.0 }) });
      ev.push({ key: 'trolley', name: 'trolley', every: [k(25), k(50)], first: [8, 20], opts: () => ({ vol: 1.6 }) });
      ev.push({ key: 'pigeons', name: 'pigeons', every: [30, 60], first: [10, 30], opts: () => ({ vol: 1.3 }) });
    }
  } else if (W === 'active') {
    if (!a.night) {
      ev.push({ key: 'klaxon', name: 'klaxon', every: [k(10), k(25)], first: [2, 8], opts: () => ({ vol: 1.3 }) });
      ev.push({ key: 'trolley', name: 'trolley', every: [k(14), k(30)], first: [5, 12], opts: () => ({ vol: 1.8 }) });
      ev.push({ key: 'pigeons', name: 'pigeons', every: [25, 50], first: [8, 25], opts: () => ({ vol: 1.3 }) });
    }
    ev.push({ key: 'ticker', name: 'ticker', every: [k(5), k(10)], first: [0.5, 3], opts: () => ({ vol: 2.0 }) });
  } else {
    ev.push({ key: 'rumble', name: 'thunder', every: [6, 14], first: [1.5, 5], opts: (r) => ({ dist: 0.6 + 0.4 * r(), vol: 0.9 }) });
    ev.push({ key: 'gust', gust: 1.4, every: [4, 9], first: [0.5, 3] });
  }
  if (a.golden) ev.push({ key: 'hourglass', name: 'tick', every: [0.5, 0.5], first: [0.1, 0.2], opts: () => ({ vol: 0.45, pan: 0, bus: 'sfx' }) });
  return ev;
}

// ------------------------------------------------------------------------------------------------ soft clip curve (bounded)
let _curve = null;
function clipCurve() {
  if (_curve) return _curve;
  const N = 8192, c = new Float32Array(N), K = CLIP_KNEE, M = CLIP_MAX;
  for (let i = 0; i < N; i++) {
    const x = (i / (N - 1) * 2 - 1) * CLIP_RANGE, ax = Math.abs(x);
    c[i] = ax <= K ? x : Math.sign(x) * (K + (M - K) * Math.tanh((ax - K) / (M - K)));
  }
  return (_curve = c);
}

// ------------------------------------------------------------------------------------------------ THE SOUND BIBLE (recipes)
// Each recipe: { fn(E, out, T, o, r) -> duration s, dur: max length (offline render), gain: voice level, verb: reverb send,
//                prio: 1..10 (stealing), gap: min seconds between starts, max: concurrent voices, steal: replace own oldest,
//                panJitter, duck: [ambience level, seconds] }
const RECIPES = {};
function def(name, spec) { RECIPES[name] = spec; }
const P = (o) => NAN_SAFE(+(o.pitch ?? o.rate ?? 1), 1) || 1;

// ticks = footsteps. Pre-synthesised heel-toe-body buffers; alternating feet; sprint timbre when ticks come fast.
def('footstep', {
  dur: 0.25, gain: 0.42, prio: 1, gap: 0.045, max: 8, steal: true, panJitter: 0.12,
  fn(E, out, T, o, r) {
    E.foot = -E.foot;
    const debt = Math.min(E.stepDebt, 6); E.stepDebt = 0;
    const sprint = clamp((E.stepRate - 4) / 12, 0, 1);
    const pr = P(o) * (1 + (r() - 0.5) * 0.1 + E.foot * 0.02 + sprint * 0.08);
    const lvl = (0.55 + 0.45 * clamp(o.intensity ?? 0.6, 0, 1)) * (1 + 0.07 * debt) * (1 - 0.25 * sprint);
    return E.atomPlay(o.wooden ? 'stepwood' : 'step', Math.floor(r() * 8), out, T, pr, lvl) - T;
  },
});

// a crisp clockwork tick (escapement / split-flap / hourglass); alternates tick-tock
def('tick', {
  dur: 0.1, gain: 0.34, prio: 1, gap: 0.03, max: 6, steal: true,
  fn(E, out, T, o, r) {
    E.tickFlip = !E.tickFlip; const tock = o.tock ?? !E.tickFlip;
    return E.atomPlay('tick', (tock ? 3 : 0) + Math.floor(r() * 3), out, T, P(o) * (0.98 + 0.04 * r()), 1) - T;
  },
});

// tilt change = pistons: the iron linkage clanks, groans (stick-slip) up or down, and vents steam
def('pistons', {
  dur: 1.4, gain: 0.42, prio: 4, gap: 0.3, max: 2, steal: true, verb: 0.12,
  fn(E, out, T, o, r) {
    const amt = clamp(o.amount ?? o.intensity ?? 0.6, 0.15, 1), dir = (o.dir ?? 1) >= 0 ? 1 : -1, p = P(o);
    const len = 0.45 + 0.45 * amt;
    E.modal(out, T, 140 * p, [[1, 0.3, 0.45], [2.31, 0.2, 0.3], [3.89, 0.12, 0.18], [5.6, 0.06, 0.1]]);
    E.burst(out, T, { f: 1100, Q: 0.8, peak: 0.22, d: 0.05 });
    const f0 = (dir > 0 ? 52 : 74) * p, f1 = (dir > 0 ? 74 : 50) * p, stop = T + len + 0.4;
    // groan: sawtooth -> iron resonance; envelope gain then a stick-slip modulator (1 +- 0.4)
    const lp = E.f('lowpass', 650, 0.7, out), bp = E.f('bandpass', 190, 2.5, lp);
    const mod = E.g(1, bp), envg = E.g(0, mod);
    const saw = E.o('sawtooth', f0, T, stop, envg); saw.frequency.exponentialRampToValueAtTime(f1, T + len);
    E.env(envg.gain, T + 0.02, 1.0 * amt, 0.09, 0.3, Math.max(0.05, len - 0.12));
    E.o('square', 20 + 7 * r(), T, stop, E.g(0.4, mod.gain));
    // metallic friction partial
    const bp2 = E.f('bandpass', 620 * p, 7, out), env2 = E.g(0, bp2);
    const saw2 = E.o('sawtooth', f0 * 3.02, T, stop, env2); saw2.frequency.exponentialRampToValueAtTime(f1 * 3.02, T + len);
    E.env(env2.gain, T + 0.05, 0.6 * amt, 0.12, 0.25, Math.max(0.05, len - 0.22));
    // the steam vents
    E.burst(out, T + 0.12, { type: 'highpass', f: 2400, Q: 0.5, peak: 0.1 * amt, a: 0.04, d: 0.55, lp: 6500 });
    return len + 0.75;
  },
});

// the Golden Bell (London / New York open): bronze partials with beating, clapper strike, pressure wave, sub-bass bloom
def('bell', {
  dur: 8.5, gain: 0.5, prio: 10, gap: 1.0, max: 2, verb: 0.5, duck: [0.4, 3.0],
  fn(E, out, T, o, r) {
    const ny = o.session === 'newyork', prime = (ny ? 146.83 : 196.0) * P(o);
    E.modal(out, T, prime, [
      [0.5, 0.26, 8.0, 0.6], [1.0, 0.24, 6.0, 0.9], [1.19, 0.18, 4.5, 1.3], [1.5, 0.08, 3.6], [2.0, 0.3, 4.0, 1.7],
      [2.51, 0.09, 2.6], [2.66, 0.07, 2.2], [3.01, 0.11, 2.0], [4.17, 0.07, 1.3], [5.43, 0.045, 0.8], [6.79, 0.025, 0.5]], { attack: 0.003 });
    E.burst(out, T, { f: 2300, Q: 1.1, peak: 0.22, d: 0.05, lp: 6000 });
    E.thump(out, T, { f0: 300, f1: 150, peak: 0.16, d: 0.09 });
    E.burst(out, T, { kind: 'brown', type: 'lowpass', f: 180, Q: 0.7, peak: 0.5, a: 0.008, d: 0.9 });
    const bloom = prime / 4, bg = E.g(0, out);
    const s1 = E.o('sine', bloom * 1.06, T, T + 6, bg); s1.frequency.exponentialRampToValueAtTime(bloom, T + 0.6);
    const s2 = E.o('sine', bloom * 2.12, T, T + 6, E.g(0.35, bg)); s2.frequency.exponentialRampToValueAtTime(bloom * 2, T + 0.6);
    bg.gain.setValueAtTime(0, T); bg.gain.linearRampToValueAtTime(0.5, T + 0.35); bg.gain.setTargetAtTime(0, T + 0.35, 0.8);
    return 8.1;
  },
});

// the anvil lands: a cathedral clang (inharmonic iron modes, hammer transient, heavy thud), long hall tail
def('anvil', {
  dur: 3.6, gain: 0.5, prio: 8, gap: 0.15, max: 3, verb: 0.45, duck: [0.6, 1.2],
  fn(E, out, T, o, r) {
    if (o.ok === false) return RECIPES.refused.fn(E, out, T, o, r);
    const f0 = 293.66 * P(o);   // D4
    E.modal(out, T, f0, [[1, 0.26, 2.8, 0.7], [1.594, 0.14, 1.9], [2.136, 0.13, 1.6, 1.1], [2.653, 0.11, 1.3], [2.756, 0.09, 1.5],
      [3.6, 0.07, 0.9], [4.15, 0.05, 0.65], [5.4, 0.03, 0.4], [6.9, 0.018, 0.25]], { attack: 0.0015 });
    E.burst(out, T, { f: 3600, Q: 0.9, peak: 0.42, d: 0.03, hp: 1500 });
    E.thump(out, T, { f0: 120, f1: 52, peak: 0.45, d: 0.22 });
    return 3.3;
  },
});

// refused: a damped clang, then the anvil bounces back (each bounce smaller and sooner) with a cartoon boing
def('refused', {
  dur: 1.6, gain: 0.5, prio: 7, gap: 0.2, max: 2, verb: 0.2,
  fn(E, out, T, o, r) {
    const f0 = 261.63 * P(o);
    E.modal(out, T, f0, [[1, 0.26, 0.9], [1.594, 0.14, 0.6], [2.136, 0.12, 0.5], [2.756, 0.09, 0.45], [3.6, 0.06, 0.3], [5.4, 0.03, 0.15]], { attack: 0.0015 });
    E.burst(out, T, { f: 3200, Q: 0.9, peak: 0.32, d: 0.025, hp: 1200 });
    E.thump(out, T, { f0: 130, f1: 60, peak: 0.4, d: 0.16 });
    const times = [0.27, 0.45, 0.57, 0.65, 0.7], amps = [0.6, 0.36, 0.2, 0.11, 0.06];
    times.forEach((dt, i) => {
      const t = T + dt, a = amps[i];
      E.modal(out, t, f0 * (1.02 + 0.01 * i), [[1, 0.22 * a, 0.25], [2.756, 0.12 * a, 0.12], [5.4, 0.05 * a, 0.06]], { attack: 0.001 });
      E.thump(out, t, { f0: 150, f1: 70, peak: 0.32 * a, d: 0.06 });
    });
    const bg = E.g(0, E.f('lowpass', 1400, 0.7, out)), t1 = T + 0.27;
    const tri = E.o('triangle', 200 * P(o), t1, t1 + 0.7, bg); tri.frequency.exponentialRampToValueAtTime(120 * P(o), t1 + 0.55);
    E.o('sine', 11, t1, t1 + 0.7, E.g(16, tri.frequency));
    E.env(bg.gain, t1, 0.14, 0.01, 0.55);
    return 1.3;
  },
});

// the Slippage Rat: razor snips (blade scrape rising, blades meeting), and a tiny squeak
def('rat', {
  dur: 0.9, gain: 1.1, prio: 5, gap: 0.12, max: 3,
  fn(E, out, T, o, r) {
    const n = clamp(Math.round(o.n ?? 3), 1, 6), p = P(o), lp = E.f('lowpass', 7500, 0.7, out);
    let t = T;
    for (let i = 0; i < n; i++) {
      E.burst(lp, t, { f: 2400 * p, f1: 5200 * p, sweep: 0.035, Q: 4, peak: 0.28, a: 0.004, d: 0.04 });
      E.modal(lp, t + 0.034, 4100 * p * (0.96 + 0.08 * r()), [[1, 0.15, 0.05], [1.48, 0.07, 0.03]], { attack: 0.0005 });
      E.burst(lp, t + 0.034, { f: 1300, Q: 1.2, peak: 0.12, d: 0.012 });
      t += 0.072 + 0.02 * r();
    }
    if (n >= 2 && o.squeak !== false) {
      const g = E.g(0, lp), s = E.o('sine', 2300 * p, t, t + 0.14, g);
      s.frequency.linearRampToValueAtTime(3000 * p, t + 0.04); s.frequency.linearRampToValueAtTime(2600 * p, t + 0.09);
      E.env(g.gain, t, 0.045, 0.008, 0.09);
    }
    return t - T + 0.18;
  },
});

// shavings into the jar = glass pings (G pentatonic, so cascades twinkle and never clash)
def('ping', {
  dur: 0.8, gain: 0.26, prio: 2, gap: 0.035, max: 10, steal: true, panJitter: 0.25,
  fn(E, out, T, o, r) {
    const f = penta(o.step != null ? Math.round(o.step) : Math.floor(r() * 7), 1567.98) * P(o);
    E.modal(out, T, f, [[1, 0.3, 0.6], [2.32, 0.1, 0.32], [4.25, 0.04, 0.16], [6.8, 0.015, 0.08]], { attack: 0.0008 });
    E.burst(out, T, { f: 6000, Q: 1, peak: 0.05, d: 0.006 });
    return 0.66;
  },
});

// machete: bullet-time whoosh across the stereo field over a slow-motion pitch dive, then one bright chime at the cut
def('machete', {
  dur: 2.8, gain: 0.5, prio: 8, gap: 0.4, max: 2, verb: 0.35,
  fn(E, out, T, o, r) {
    const p = P(o), pn = E.pan(out, -0.6); E.sweep(pn.pan, -0.6, 0.6, T, 0.8, true);
    const ns = E.n('white', T, T + 0.95, null), bp = E.f('bandpass', 300, 2.2), g = E.g(0, pn);
    bp.frequency.setValueAtTime(300, T); bp.frequency.exponentialRampToValueAtTime(2600, T + 0.42); bp.frequency.exponentialRampToValueAtTime(650, T + 0.85);
    ns.connect(bp); bp.connect(g);
    g.gain.setValueAtTime(0, T); g.gain.linearRampToValueAtTime(0.9, T + 0.4); g.gain.linearRampToValueAtTime(0, T + 0.9);
    const dg = E.g(0, E.f('lowpass', 500, 0.7, out));
    E.o('sine', 196 * p, T, T + 1.0, dg).frequency.exponentialRampToValueAtTime(49 * p, T + 0.8);
    E.o('sawtooth', 98 * p, T, T + 1.0, E.g(0.3, dg)).frequency.exponentialRampToValueAtTime(24.5 * p, T + 0.8);
    E.env(dg.gain, T, 0.32, 0.06, 0.8, 0.1);
    const tc = T + 0.44;
    E.modal(out, tc, 1567.98 * p, [[1, 0.26, 1.8, 2.2], [2.0, 0.07, 0.9], [3.0, 0.035, 0.5], [4.2, 0.018, 0.3]], { attack: 0.001 });
    E.burst(out, tc, { f: 5000, Q: 0.8, peak: 0.1, d: 0.01 });
    return 2.4;
  },
});

// one warm tubular chime (D6 unless a step is given)
def('chime', {
  dur: 3.2, gain: 0.6, prio: 5, gap: 0.08, max: 4, verb: 0.35,
  fn(E, out, T, o, r) {
    const f = (o.step != null ? penta(Math.round(o.step), 783.99) : 1174.66) * P(o);
    E.modal(out, T, f, [[1, 0.28, 2.4, 1.1], [2.0, 0.1, 1.5], [3.0, 0.05, 0.9], [4.16, 0.03, 0.55], [5.43, 0.015, 0.3]], { attack: 0.0015 });
    E.burst(out, T, { type: 'lowpass', f: 3000, Q: 0.7, peak: 0.07, d: 0.008 });
    return 2.6;
  },
});

// eject = balloon hiss: gas rushing in (rising), rubber stretching, the valve closing, a soft lift-off whoosh
def('balloon', {
  dur: 2.2, gain: 0.85, prio: 7, gap: 0.5, max: 2,
  fn(E, out, T, o, r) {
    const p = P(o), ns = E.n('white', T, T + 1.3, null), hp = E.f('highpass', 900, 0.7), bp = E.f('bandpass', 1800 * p, 1.1), lp = E.f('lowpass', 7000, 0.7);
    E.sweep(bp.frequency, 1800 * p, 4200 * p, T, 1.15);
    const g = E.g(0, out); ns.connect(hp); hp.connect(bp); bp.connect(lp); lp.connect(g);
    g.gain.setValueAtTime(0, T); g.gain.linearRampToValueAtTime(0.5, T + 0.12); g.gain.linearRampToValueAtTime(0.62, T + 1.0); g.gain.linearRampToValueAtTime(0, T + 1.22);
    const rg = E.g(0, E.f('lowpass', 2000, 0.7, out));
    const s = E.o('triangle', 480 * p, T, T + 1.25, rg); s.frequency.exponentialRampToValueAtTime(760 * p, T + 1.15);
    E.o('sine', 9, T, T + 1.25, E.g(14, s.frequency));
    rg.gain.setValueAtTime(0, T); rg.gain.linearRampToValueAtTime(0.05, T + 0.3); rg.gain.linearRampToValueAtTime(0, T + 1.2);
    E.burst(out, T + 1.21, { f: 2400, Q: 1.5, peak: 0.22, d: 0.015 });
    E.burst(out, T + 1.2, { kind: 'pink', f: 380, f1: 950, sweep: 0.6, Q: 1.2, peak: 0.5, a: 0.25, d: 0.5 });
    return 2.0;
  },
});

// fold-up = paper: crinkle grains in two folds, two swishes, the crease
def('fold', {
  dur: 1.0, gain: 1.4, prio: 5, gap: 0.3, max: 2,
  fn(E, out, T, o, r) {
    E.crinkle(out, T, 0.66, { density: 55, f: [1800, 5200], Q: 1.4, peak: [0.06, 0.3], gaps: [[0.29, 0.36]] });
    E.burst(out, T, { kind: 'pink', f: 600, f1: 2200, sweep: 0.14, Q: 0.9, peak: 0.35, a: 0.08, d: 0.2 });
    E.burst(out, T + 0.34, { kind: 'pink', f: 700, f1: 2400, sweep: 0.14, Q: 0.9, peak: 0.35, a: 0.07, d: 0.2 });
    E.burst(out, T + 0.63, { f: 3400, Q: 1.2, peak: 0.32, d: 0.012 });
    E.burst(out, T + 0.635, { type: 'lowpass', f: 700, Q: 0.7, peak: 0.2, d: 0.03 });
    return 0.82;
  },
});

// a coin thuds onto the stack, chinks, and settles (wobbling faster and faster)
def('thud', {
  dur: 1.1, gain: 0.5, prio: 5, gap: 0.08, max: 3, verb: 0.08,
  fn(E, out, T, o, r) {
    const p = P(o);
    E.thump(out, T, { f0: 150 * p, f1: 62 * p, peak: 0.55, d: 0.2, drop: 0.07 });
    E.burst(out, T, { type: 'lowpass', f: 650, Q: 0.7, peak: 0.3, d: 0.05 });
    E.clink(out, T + 0.002, Math.floor(r() * 6), p, 0.35);
    let t = T + 0.1, dt = 0.075, a = 0.16;
    for (let k = 0; k < 7; k++) { E.clink(out, t, k, (1.1 + 0.04 * k) * p, a); t += dt; dt *= 0.76; a *= 0.8; }
    return t - T + 0.42;
  },
});

// the Collector's chain: one link at a time (link on link, twice), with the heavy iron underneath
def('chain', {
  dur: 0.7, gain: 0.5, prio: 5, gap: 0.12, max: 4, verb: 0.15,
  fn(E, out, T, o, r) {
    const f = 1850 * P(o) * (0.92 + 0.16 * r()), PT = [[1, 0.22, 0.12], [1.62, 0.14, 0.09], [2.44, 0.08, 0.06], [3.1, 0.05, 0.04]];
    E.modal(out, T, f, PT, { attack: 0.0006 });
    E.burst(out, T, { f: 4200, Q: 1, peak: 0.15, d: 0.006 });
    E.modal(out, T + 0.034, f * 1.13, PT.map(([a, b, c]) => [a, b * 0.6, c]), { attack: 0.0006 });
    E.burst(out, T + 0.034, { f: 4600, Q: 1, peak: 0.1, d: 0.005 });
    E.thump(out, T, { f0: 330, f1: 240, peak: 0.12, d: 0.06 });
    return 0.45;
  },
});

// Time Freeze = a record needle lifting: crackle under a warm chord, the turntable spins down, the stylus skates, the arm lifts
def('needle', {
  dur: 1.5, gain: 0.9, prio: 9, gap: 0.5, max: 1, duck: [0.3, 0.8],
  fn(E, out, T, o, r) {
    const cr = E.ctx.createBufferSource(); cr.buffer = E.bedBuf('crackle'); cr.loop = true;
    const cg = E.g(0, out); cr.connect(cg); cr.start(T, r() * 2); cr.stop(T + 0.4);
    cg.gain.setValueAtTime(0, T); cg.gain.linearRampToValueAtTime(0.8, T + 0.02); cg.gain.setValueAtTime(0.8, T + 0.3); cg.gain.linearRampToValueAtTime(0, T + 0.33);
    const chord = E.g(0, E.f('lowpass', 1300, 0.7, out));
    [196, 246.94, 293.66].forEach((f) => { const s = E.o('triangle', f, T, T + 0.9, E.g(0.33, chord)); s.frequency.setValueAtTime(f, T + 0.05); s.frequency.exponentialRampToValueAtTime(f * 0.22, T + 0.7); });
    chord.gain.setValueAtTime(0, T); chord.gain.linearRampToValueAtTime(0.3, T + 0.03); chord.gain.setTargetAtTime(0, T + 0.2, 0.1);
    const zt = T + 0.2, zn = E.n('white', zt, zt + 0.17, null), zb = E.f('bandpass', 1400, 4.5);
    E.o('sawtooth', 38, zt, zt + 0.17, E.g(350, zb.frequency));
    E.sweep(zb.frequency, 1600, 500, zt, 0.13);
    const zg = E.g(0, out); zn.connect(zb); zb.connect(zg); E.env(zg.gain, zt, 1.4, 0.005, 0.13);
    E.burst(out, T + 0.33, { f: 950, Q: 2, peak: 0.25, d: 0.02 });
    E.thump(out, T + 0.33, { f0: 95, f1: 60, peak: 0.25, d: 0.08 });
    return 1.2;
  },
});

// Zee 2026-11-04: "the initial shotgun's shot to guard -> it should give a shot sound essentially making the user alert" - a loud
// shotgun BLAST: a sharp crack, a deep boom, a wide noise body, a rolling echo off the towers, then the pump racking (chk-chk)
def('gunshot', {
  dur: 2.2, gain: 1.0, prio: 10, gap: 0.15, max: 2, verb: 0.45, duck: [0.25, 1.0],
  fn(E, out, T, o, r) {
    const p = P(o);
    E.burst(out, T, { type: 'highpass', f: 2200, Q: 0.7, peak: 1.0, a: 0.0003, d: 0.07 });                       // the crack
    E.thump(out, T, { f0: 140 * p, f1: 38 * p, peak: 1.0, d: 0.42, drop: 0.09 });                                // the boom
    E.burst(out, T, { kind: 'brown', type: 'lowpass', f: 2600, f1: 280, sweep: 0.35, Q: 0.6, peak: 1.0, a: 0.001, d: 0.5 });   // the body
    E.burst(out, T, { f: 1300 * p, Q: 3, peak: 0.6, a: 0.0004, d: 0.05 });
    E.burst(out, T + 0.22, { kind: 'pink', type: 'lowpass', f: 700, f1: 220, sweep: 0.8, Q: 0.6, peak: 0.45, a: 0.05, d: 1.1 });   // the echo
    E.burst(out, T + 0.55, { f: 2400, Q: 4, peak: 0.35, a: 0.0005, d: 0.03 });                                   // chk
    E.burst(out, T + 0.68, { f: 1800, Q: 4, peak: 0.4, a: 0.0005, d: 0.04 });                                    // chk
    return 1.8;
  },
});

// the Buyer pays: a golden blunderbuss BOOM, then a shower of coins (and a flutter of notes)
def('cash', {
  dur: 3.0, gain: 0.5, prio: 9, gap: 0.5, max: 2, verb: 0.3, duck: [0.5, 2.0],
  fn(E, out, T, o, r) {
    E.thump(out, T, { f0: 80, f1: 32, peak: 0.8, d: 0.6, drop: 0.25 });
    E.burst(out, T, { kind: 'brown', type: 'lowpass', f: 1400, f1: 350, sweep: 0.3, Q: 0.7, peak: 0.8, a: 0.002, d: 0.45 });
    E.burst(out, T, { f: 2000, Q: 0.7, peak: 0.32, a: 0.0005, d: 0.03 });
    const n = clamp(Math.round(o.n ?? 26), 6, 40), pans = [E.pan(out, -0.6), E.pan(out, 0), E.pan(out, 0.6)];
    for (let i = 0; i < n; i++) {
      const u = r(), t = T + 0.12 + 1.45 * Math.pow(u, 1.7);
      E.clink(pans[Math.floor(r() * 3)], t, Math.floor(r() * 6), 0.8 + 0.5 * r(), 0.07 + 0.16 * r() * (1 - 0.5 * u));
    }
    E.crinkle(out, T + 0.2, 0.9, { density: 25, f: [1500, 4000], Q: 1.2, peak: [0.02, 0.07] });
    return 2.3;
  },
});

// a coin chime per profit step: climbs G major pentatonic from G5
def('coin', {
  dur: 1.4, gain: 0.6, prio: 4, gap: 0.05, max: 6, steal: true, verb: 0.18,
  fn(E, out, T, o, r) {
    const f = penta(clamp(Math.round(o.step ?? 0), -6, 15), 783.99) * P(o);
    E.modal(out, T, f, [[1, 0.26, 1.0, 1.4], [2.0, 0.09, 0.55], [2.76, 0.05, 0.32], [5.4, 0.015, 0.12]], { attack: 0.0008 });
    E.burst(out, T, { f: 5200, Q: 1, peak: 0.07, d: 0.004 });
    return 1.05;
  },
});

// the Banker coughs black smoke: breathy formant bursts over a ring-modulated (cyborg) gravel
def('cough', {
  dur: 1.1, gain: 0.7, prio: 5, gap: 0.4, max: 1, verb: 0.12,
  fn(E, out, T, o, r) {
    const p = P(o);
    for (const [dt, a, len] of [[0, 1.0, 0.17], [0.25, 0.7, 0.12], [0.43, 0.9, 0.21]]) {
      const t = T + dt, stop = t + len + 0.12;
      const ns = E.n('white', t, stop, null), g = E.g(0, out);
      const fa = E.f('bandpass', 820 * p, 1.6, g), fb = E.f('bandpass', 2100 * p, 2.2, E.g(0.5, g));
      ns.connect(fa); ns.connect(fb);
      E.env(g.gain, t, 1.6 * a, 0.006, len);
      const bz = E.g(0, E.f('lowpass', 1100, 0.8, out)), rm = E.g(0, bz);
      E.o('sawtooth', 108 * p * (1 + 0.05 * r()), t, stop, rm);
      E.o('sine', 233 * p, t, stop, rm.gain);
      E.env(bz.gain, t, 0.32 * a, 0.005, len * 0.8);
      E.thump(out, t, { f0: 170 * p, f1: 90 * p, peak: 0.22 * a, d: 0.05 });
    }
    return 0.86;
  },
});

// a creak (wood, or an iron hinge): irregular stick-slip impulses exciting body resonances
def('creak', {
  dur: 1.3, gain: 0.5, prio: 3, gap: 0.3, max: 2, verb: 0.15,
  fn(E, out, T, o, r) {
    const iron = !!o.iron, p = P(o), len = 0.55 + 0.4 * r(), stop = T + len + 0.1;
    const g = E.g(0, out), src = E.o('sawtooth', 40 * p, T, stop, null);
    src.frequency.linearRampToValueAtTime((70 + 25 * r()) * p, T + len * 0.4);
    src.frequency.linearRampToValueAtTime((48 + 10 * r()) * p, T + len * 0.8);
    src.frequency.linearRampToValueAtTime(58 * p, T + len);
    const wn = E.n('brown', T, stop, null), wl = E.f('lowpass', 25, 0.7); wn.connect(wl); wl.connect(E.g(40, src.frequency));
    const hp = E.f('highpass', 250, 0.7); src.connect(hp);
    (iron ? [900, 1900, 3300] : [620, 1350, 2500]).forEach((fr, i) => hp.connect(E.f('bandpass', fr * p, iron ? 11 : 7, E.g([1, 0.6, 0.32][i], g))));
    g.gain.setValueAtTime(0, T); g.gain.linearRampToValueAtTime(2.2, T + 0.06); g.gain.setValueAtTime(2.2, T + len - 0.12); g.gain.linearRampToValueAtTime(0, T + len);
    return len + 0.12;
  },
});

// a whoosh (something fast goes by), panning in its direction
def('whoosh', {
  dur: 1.4, gain: 0.5, prio: 3, gap: 0.08, max: 3,
  fn(E, out, T, o, r) {
    const sp = clamp(o.speed ?? 1, 0.4, 3), len = 0.45 / sp, dir = (o.dir ?? 1) >= 0 ? 1 : -1;
    const pn = E.pan(out, -0.5 * dir); E.sweep(pn.pan, -0.5 * dir, 0.5 * dir, T, len, true);
    const ns = E.n('pink', T, T + len + 0.05, null), bp = E.f('bandpass', 350, 1.3), g = E.g(0, pn);
    ns.connect(bp); bp.connect(g);
    bp.frequency.setValueAtTime(350, T); bp.frequency.exponentialRampToValueAtTime(1800 * P(o), T + len * 0.45); bp.frequency.exponentialRampToValueAtTime(500, T + len);
    g.gain.setValueAtTime(0, T); g.gain.linearRampToValueAtTime(2.4, T + len * 0.45); g.gain.linearRampToValueAtTime(0, T + len);
    return len + 0.05;
  },
});

// thunder: a crack for near strikes, then a rolling brown-noise rumble, low-passed and delayed by distance
def('thunder', {
  dur: 7.5, gain: 0.52, prio: 7, gap: 0.6, max: 3, verb: 0.3, duck: [0.6, 2.5],
  fn(E, out, T, o, r) {
    const dist = clamp(o.dist ?? (o.near ? 0 : 0.35), 0, 1);
    if (dist < 0.55) {
      const k = 1 - dist / 0.55;
      E.burst(out, T, { type: 'highpass', f: 1000, Q: 0.6, peak: 0.38 * k, a: 0.001, d: 0.12, lp: 9000 });
      E.burst(out, T + 0.01, { f: 2600, Q: 0.6, peak: 0.13 * k, a: 0.002, d: 0.35 });
      E.thump(out, T, { f0: 90, f1: 40, peak: 0.42 * k, d: 0.5 });
    }
    const t0 = T + 0.05 + dist * 1.2, len = 3.2 + 1.6 * r(), rolls = [];
    let t = t0;
    for (let i = 0, n = 7 + Math.floor(r() * 5); i < n && t < t0 + len; i++) {
      const pk = (1 - i / (n + 2)) * (0.5 + 0.5 * r()) * (1 - 0.5 * dist), at = 0.04 + 0.2 * r(), dec = 0.2 + 0.5 * r();
      rolls.push([t, pk, at, dec]); t += at + dec * (0.5 + 0.8 * r());
    }
    const tEnd = t, stop = tEnd + 3.0;
    const n1 = E.n('brown', t0, stop, null), lp1 = E.f('lowpass', 320 - 170 * dist, 0.7), g1 = E.g(0, out); n1.connect(lp1); lp1.connect(g1);
    const n2 = E.n('brown', t0, stop, null), lp2 = E.f('lowpass', 85, 0.7), g2 = E.g(0, out); n2.connect(lp2); lp2.connect(g2);
    g1.gain.setValueAtTime(0, t0); g2.gain.setValueAtTime(0, t0);
    for (const [tt, pk, at, dec] of rolls) {
      g1.gain.setTargetAtTime(pk * 1.75, tt, at / 3); g2.gain.setTargetAtTime(pk * 2.05, tt, at / 2);
      g1.gain.setTargetAtTime(pk * 0.5, tt + at, dec / 3); g2.gain.setTargetAtTime(pk * 0.8, tt + at, dec / 2.5);
    }
    g1.gain.setTargetAtTime(0, tEnd, 0.4); g2.gain.setTargetAtTime(0, tEnd, 0.45);
    return stop - T;
  },
});

// the Spread Pit: thick molasses bubbles (rising "blorp", a tiny pop, a low gloop)
def('molasses', {
  dur: 0.7, gain: 0.32, prio: 2, gap: 0.07, max: 4, steal: true, panJitter: 0.2,
  fn(E, out, T, o, r) {
    const n = clamp(Math.round(o.n ?? (1 + Math.floor(r() * 2))), 1, 4), p = P(o), lp = E.f('lowpass', 1300, 0.7, out);
    let t = T, end = T;
    for (let i = 0; i < n; i++) {
      const f0 = (130 + 90 * r()) * p, len = 0.045 + 0.03 * r(), g = E.g(0, lp);
      const s = E.o('sine', f0, t, t + len + 0.14, g); s.frequency.exponentialRampToValueAtTime(f0 * 2.7, t + len);
      E.env(g.gain, t, 0.5, 0.004, len + 0.06);
      E.burst(lp, t + len, { f: 1500, Q: 1.5, peak: 0.07, d: 0.006 });
      E.thump(lp, t, { f0: 75, f1: 55, peak: 0.16, d: 0.1 });
      end = Math.max(end, t + len + 0.14); t += 0.07 + 0.11 * r();
    }
    return end - T + 0.02;
  },
});

// haggle: the Buyer's laugh as a brass horn - ho-ho-HO! (tag raised) or wah-wah-waaah (waved off)
def('haggle', {
  dur: 1.8, gain: 0.27, prio: 6, gap: 0.3, max: 2, verb: 0.2,
  fn(E, out, T, o, r) {
    const ok = o.ok !== false, p = P(o);
    const notes = ok ? [[196, 0.12, 0], [246.94, 0.12, 0.17], [293.66, 0.32, 0.34]] : [[293.66, 0.2, 0], [246.94, 0.2, 0.26], [196, 0.6, 0.52]];
    let end = T;
    notes.forEach(([f0, len, dt], i) => {
      const t = T + dt, last = i === notes.length - 1, f = f0 * p, stop = t + len + 0.2;
      const lp = E.f('lowpass', 500, 1.2), envg = E.g(0), mod = E.g(1);
      const s1 = E.o('sawtooth', f, t, stop, lp), s2 = E.o('square', f * 1.004, t, stop, E.g(0.4, lp));
      lp.connect(envg); envg.connect(mod);
      mod.connect(E.f('bandpass', 520, 3.5, out)); mod.connect(E.f('bandpass', 880, 4, E.g(0.6, out))); mod.connect(E.g(0.25, out));
      lp.frequency.setValueAtTime(400, t); lp.frequency.linearRampToValueAtTime(2200, t + 0.04); lp.frequency.setTargetAtTime(900, t + 0.05, 0.1);
      envg.gain.setValueAtTime(0, t); envg.gain.linearRampToValueAtTime(1, t + 0.025); envg.gain.setValueAtTime(0.9, t + len - 0.04); envg.gain.linearRampToValueAtTime(0, t + len + 0.06);
      if (ok) E.o('sine', 9, t, stop, E.g(0.45, mod.gain));   // chuckle
      if (last) {
        E.o('sine', 5.5, t, stop, E.g(f * 0.012, s1.frequency)); E.o('sine', 5.5, t, stop, E.g(f * 0.012, s2.frequency));
        if (!ok) { E.sweep(s1.frequency, f, f * 0.94, t + 0.15, len - 0.15, true); E.sweep(s2.frequency, f * 1.004, f * 0.944, t + 0.15, len - 0.15, true); }
      }
      end = Math.max(end, stop);
    });
    return end - T + 0.05;
  },
});

// a wall goes up: bricks clack (clay on clay), a trowel scrapes between, the last one thunks home
def('wall', {
  dur: 1.8, gain: 0.5, prio: 6, gap: 0.3, max: 2, verb: 0.12,
  fn(E, out, T, o, r) {
    if (o.ok === false) return RECIPES.refused.fn(E, out, T, o, r);
    const n = clamp(Math.round(o.n ?? 4), 1, 8), p = P(o), times = [0, 0.32, 0.6, 0.84, 1.04, 1.2, 1.33, 1.43].slice(0, n);
    times.forEach((dt, i) => {
      const t = T + dt, last = i === n - 1;
      E.burst(out, t, { f: 1400 * p * (0.85 + 0.3 * r()), Q: 2.5, peak: 0.4, d: 0.04 });
      E.thump(out, t, { f0: 430 * p, f1: 300 * p, peak: 0.22, d: 0.05 });
      E.thump(out, t, { f0: 125, f1: 78, peak: last ? 0.5 : 0.28, d: last ? 0.2 : 0.08 });
      if (!last) E.burst(out, t + 0.13, { f: 3200, Q: 3, peak: 0.06, a: 0.03, d: 0.09 });
    });
    return times[n - 1] + 0.35;
  },
});

// a stake lights: a glowing tink (shimmering beat) over a warm swell; golden stakes ring a chord
def('stake', {
  dur: 2.2, gain: 0.6, prio: 4, gap: 0.12, max: 3, verb: 0.4,
  fn(E, out, T, o, r) {
    const gold = !!o.golden, p = P(o), f = 1975.53 * p;   // B6
    E.modal(out, T, f, [[1, 0.22, 0.95, 6.5], [2.0, 0.05, 0.5], [3.01, 0.025, 0.3]], { attack: 0.0008 });
    if (gold) E.modal(out, T + 0.03, f / 2, [[1, 0.16, 1.4, 3], [1.5, 0.06, 0.9]], { attack: 0.001 });
    const pad = E.g(0, E.f('lowpass', 2500, 0.7, out));
    (gold ? [587.33, 783.99, 987.77] : [587.33, 783.99]).forEach((nf) => E.o('sine', nf * p, T, T + 1.6, E.g(0.33, pad)));
    pad.gain.setValueAtTime(0, T); pad.gain.linearRampToValueAtTime(0.12, T + 0.25); pad.gain.setTargetAtTime(0, T + 0.3, 0.2);
    return 1.65;
  },
});

// a page turns (the mirror world): swish, flutter, landing
def('page', {
  dur: 1.0, gain: 1.0, prio: 4, gap: 0.25, max: 2,
  fn(E, out, T, o, r) {
    const dir = (o.dir ?? 1) >= 0 ? 1 : -1, pn = E.pan(out, -0.35 * dir); E.sweep(pn.pan, -0.35 * dir, 0.35 * dir, T, 0.4, true);
    E.burst(pn, T, { kind: 'pink', f: 700, f1: 2800, sweep: 0.18, Q: 0.9, peak: 0.8, a: 0.11, d: 0.28 });
    E.crinkle(pn, T + 0.04, 0.3, { density: 40, f: [2000, 5000], Q: 1.3, peak: [0.03, 0.12] });
    E.burst(out, T + 0.38, { type: 'lowpass', f: 900, Q: 0.7, peak: 0.28, d: 0.05 });
    E.burst(out, T + 0.385, { f: 2500, Q: 1.2, peak: 0.08, d: 0.01 });
    return 0.6;
  },
});

// cards: a riffle shuffle (two half-decks interleaving), the bridge, the deck squared on the step
def('cards', {
  dur: 1.7, gain: 1.2, prio: 3, gap: 0.6, max: 1,
  fn(E, out, T, o, r) {
    const mk = (dest, stop) => { const ns = E.n('white', T, stop, null), bp = E.f('bandpass', 2800, 1.6), hp = E.f('highpass', 900, 0.7), g = E.g(0, dest); ns.connect(bp); bp.connect(hp); hp.connect(g); g.gain.setValueAtTime(0, T); return g; };
    const gl = mk(E.pan(out, -0.25), T + 1.05), gr = mk(E.pan(out, 0.25), T + 1.05);
    let t = T + 0.01, k = 0;
    while (t < T + 0.78) {
      const u = (t - T) / 0.78, g = (k++ & 1) ? gl : gr, pk = 0.35 + 0.25 * r();
      g.gain.setTargetAtTime(pk, t, 0.0003); g.gain.setTargetAtTime(0, t + 0.0012, 0.0012);
      t += (0.022 - 0.011 * Math.sin(Math.PI * u)) * (0.85 + 0.3 * r());
    }
    const gb = mk(out, T + 1.05);
    for (t = T + 0.82; t < T + 0.98; t += 0.004 + 0.002 * r()) { const pk = 0.25 * (1 - (t - T - 0.82) / 0.16); gb.gain.setTargetAtTime(pk, t, 0.0003); gb.gain.setTargetAtTime(0, t + 0.001, 0.001); }
    gl.gain.setTargetAtTime(0, T + 0.8, 0.003); gr.gain.setTargetAtTime(0, T + 0.8, 0.003); gb.gain.setTargetAtTime(0, T + 0.99, 0.003);
    [1.06, 1.19].forEach((dt) => { E.burst(out, T + dt, { f: 900, Q: 1.5, peak: 0.3, d: 0.02 }); E.thump(out, T + dt, { f0: 210, f1: 150, peak: 0.12, d: 0.03 }); });
    return 1.36;
  },
});

// the Debt Collector: chain links drawn one at a time, then the padlock snaps shut
def('collector', {
  dur: 2.8, gain: 0.9, prio: 8, gap: 1.0, max: 1, verb: 0.25, duck: [0.5, 2.0],
  fn(E, out, T, o, r) {
    [0, 0.4, 0.78, 1.12].forEach((dt, i) => RECIPES.chain.fn(E, E.g(0.75 + 0.08 * i, out), T + dt, { pitch: P(o) * (1 - 0.03 * i) }, r));
    const t = T + 1.5;
    E.burst(out, t, { f: 2200, Q: 3, peak: 0.42, d: 0.012 });
    E.modal(out, t, 1800 * P(o), [[1, 0.18, 0.08], [1.61, 0.12, 0.06], [2.33, 0.07, 0.04]]);
    E.thump(out, t, { f0: 190, f1: 120, peak: 0.32, d: 0.08 });
    E.burst(out, t + 0.055, { f: 2600, Q: 3, peak: 0.25, d: 0.008 });
    E.modal(out, t + 0.055, 2300 * P(o), [[1, 0.1, 0.05], [1.5, 0.06, 0.03]]);
    return 2.1;
  },
});

// ---------------------------------------------------------------- extras
def('flap', {   // split-flap riffle (the roof sign changing)
  dur: 0.5, gain: 1.1, prio: 2, gap: 0.04, max: 4,
  fn(E, out, T, o, r) {
    const n = clamp(Math.round(o.n ?? 4), 1, 10); let t = T;
    for (let i = 0; i < n; i++) { E.burst(out, t, { f: 1700 * (0.9 + 0.2 * r()), Q: 2, peak: 0.28, d: 0.008 }); E.modal(out, t, 1100 * (0.95 + 0.1 * r()), [[1, 0.08, 0.02]]); t += 0.026 + 0.008 * r(); }
    return t - T + 0.05;
  },
});
def('click', {   // soft click: a hold ring released early (cancel)
  dur: 0.15, gain: 0.8, prio: 2, gap: 0.04, max: 3,
  fn(E, out, T, o, r) { E.burst(out, T, { f: 1200, Q: 1.2, peak: 0.2, d: 0.006 }); E.modal(out, T, 880 * P(o), [[1, 0.1, 0.015]]); return 0.06; },
});
def('confirm', {   // hold ring complete: a satisfying lever ka-chunk
  dur: 0.4, gain: 0.4, prio: 4, gap: 0.08, max: 2,
  fn(E, out, T, o, r) {
    E.burst(out, T, { f: 1800, Q: 1.5, peak: 0.25, d: 0.01 }); E.modal(out, T, 1500, [[1, 0.06, 0.03]]);
    E.burst(out, T + 0.06, { f: 700, Q: 1.2, peak: 0.3, d: 0.03 }); E.thump(out, T + 0.06, { f0: 160, f1: 100, peak: 0.3, d: 0.08 });
    return 0.22;
  },
});
def('clunk', {   // the bell rope pulled by hand: a dull clunk (the bell marks time, it does not advise)
  dur: 1.0, gain: 0.45, prio: 3, gap: 0.3, max: 1, verb: 0.2,
  fn(E, out, T, o, r) {
    E.thump(out, T, { f0: 160, f1: 110, peak: 0.45, d: 0.12 }); E.burst(out, T, { type: 'lowpass', f: 700, Q: 0.7, peak: 0.3, d: 0.05 });
    E.modal(out, T + 0.01, 98, [[1, 0.06, 0.5], [2.0, 0.03, 0.3]]);
    return 0.6;
  },
});
def('whistle', {   // whistle for the Merchant: a two-finger "fweeet!"
  dur: 0.8, gain: 0.32, prio: 5, gap: 0.3, max: 1,
  fn(E, out, T, o, r) {
    const p = P(o), lp = E.f('lowpass', 4200, 0.7, out), g = E.g(0, lp), s = E.o('sine', 1500 * p, T, T + 0.5, g);
    s.frequency.exponentialRampToValueAtTime(2350 * p, T + 0.16); s.frequency.setValueAtTime(2350 * p, T + 0.3); s.frequency.exponentialRampToValueAtTime(2150 * p, T + 0.42);
    E.o('sine', 7, T, T + 0.5, E.g(25, s.frequency));
    g.gain.setValueAtTime(0, T); g.gain.linearRampToValueAtTime(0.35, T + 0.05); g.gain.setValueAtTime(0.35, T + 0.34); g.gain.linearRampToValueAtTime(0, T + 0.44);
    E.burst(lp, T, { f: 2200, Q: 6, peak: 0.08, a: 0.04, d: 0.4 });
    return 0.5;
  },
});
def('tackle', {   // tackle the Merchant: body thud + dust whoosh
  dur: 1.0, gain: 0.5, prio: 6, gap: 0.3, max: 1,
  fn(E, out, T, o, r) {
    E.thump(out, T, { f0: 95, f1: 48, peak: 0.6, d: 0.22 }); E.burst(out, T, { type: 'lowpass', f: 900, Q: 0.7, peak: 0.35, d: 0.06 });
    E.burst(out, T + 0.03, { kind: 'pink', type: 'lowpass', f: 1300, f1: 400, sweep: 0.5, Q: 0.6, peak: 0.4, a: 0.1, d: 0.55 });
    E.crinkle(out, T + 0.02, 0.25, { density: 30, f: [900, 2500], Q: 1, peak: [0.02, 0.08] });
    return 0.75;
  },
});
def('stamp', {   // STOPPED / LIQUIDATED: a rubber stamp on the sign
  dur: 0.5, gain: 0.5, prio: 6, gap: 0.2, max: 1, verb: 0.1,
  fn(E, out, T, o, r) {
    E.thump(out, T, { f0: 130, f1: 70, peak: 0.5, d: 0.09 }); E.burst(out, T, { f: 1800, Q: 0.8, peak: 0.4, d: 0.025 });
    E.burst(out, T + 0.004, { f: 500, Q: 1.2, peak: 0.3, d: 0.03 });
    return 0.35;
  },
});
def('barrel', {   // the pickle barrel slams down (liquidated): hollow wood, iron hoops rattle
  dur: 1.2, gain: 0.5, prio: 8, gap: 0.5, max: 1, verb: 0.2,
  fn(E, out, T, o, r) {
    E.modal(out, T, 110, [[1, 0.25, 0.3], [2.15, 0.15, 0.18], [3.45, 0.1, 0.12], [5.36, 0.06, 0.07]], { attack: 0.002 });
    E.burst(out, T, { type: 'lowpass', f: 1500, Q: 0.7, peak: 0.45, d: 0.07 }); E.thump(out, T, { f0: 80, f1: 45, peak: 0.6, d: 0.28 });
    for (let k = 0; k < 3; k++) E.clink(out, T + 0.03 + 0.06 * k + 0.02 * r(), k, 0.55 + 0.1 * r(), 0.12);
    return 0.9;
  },
});
def('crane', {   // the Banker's crane arm: servo whirr out, clamp, whirr back
  dur: 1.3, gain: 0.65, prio: 5, gap: 0.5, max: 1,
  fn(E, out, T, o, r) {
    const g = E.g(0, E.f('bandpass', 900, 3, out)), mod = E.g(1, g), saw = E.o('sawtooth', 180, T, T + 1.1, mod);
    saw.frequency.exponentialRampToValueAtTime(320, T + 0.5); saw.frequency.setValueAtTime(320, T + 0.6); saw.frequency.exponentialRampToValueAtTime(160, T + 1.05);
    E.o('square', 38, T, T + 1.1, E.g(0.35, mod.gain));
    g.gain.setValueAtTime(0, T); g.gain.linearRampToValueAtTime(0.5, T + 0.05); g.gain.linearRampToValueAtTime(0.3, T + 0.5); g.gain.linearRampToValueAtTime(0.45, T + 0.62); g.gain.linearRampToValueAtTime(0, T + 1.06);
    E.burst(out, T + 0.55, { f: 2600, Q: 2.5, peak: 0.3, d: 0.012 }); E.modal(out, T + 0.55, 1900, [[1, 0.1, 0.07], [1.6, 0.06, 0.05]]);
    return 1.1;
  },
});
def('duck', {   // the Banker ducks (a refused order): quick whoosh down + the visor knocks the frame
  dur: 0.6, gain: 0.65, prio: 5, gap: 0.3, max: 1,
  fn(E, out, T, o, r) {
    E.burst(out, T, { kind: 'pink', f: 1600, f1: 400, sweep: 0.18, Q: 1.2, peak: 0.6, a: 0.04, d: 0.18 });
    E.modal(out, T + 0.17, 1300, [[1, 0.12, 0.1], [2.7, 0.05, 0.05]]); E.thump(out, T + 0.17, { f0: 200, f1: 140, peak: 0.2, d: 0.05 });
    return 0.4;
  },
});
def('needle_drop', {   // reconnect: the needle drops back, crackle returns, the turntable spins up
  dur: 1.3, gain: 0.8, prio: 8, gap: 0.5, max: 1,
  fn(E, out, T, o, r) {
    E.thump(out, T, { f0: 110, f1: 65, peak: 0.3, d: 0.1 }); E.burst(out, T, { f: 800, Q: 1.5, peak: 0.2, d: 0.02 });
    const cr = E.ctx.createBufferSource(); cr.buffer = E.bedBuf('crackle'); cr.loop = true; const cg = E.g(0, out); cr.connect(cg); cr.start(T, r() * 2); cr.stop(T + 1.0);
    cg.gain.setValueAtTime(0, T); cg.gain.linearRampToValueAtTime(0.6, T + 0.03); cg.gain.setValueAtTime(0.6, T + 0.6); cg.gain.linearRampToValueAtTime(0, T + 0.95);
    const chord = E.g(0, E.f('lowpass', 1300, 0.7, out));
    [196, 246.94, 293.66].forEach((f) => { const s = E.o('triangle', f * 0.25, T, T + 1.0, E.g(0.33, chord)); s.frequency.exponentialRampToValueAtTime(f, T + 0.35); });
    chord.gain.setValueAtTime(0, T); chord.gain.linearRampToValueAtTime(0.25, T + 0.3); chord.gain.setTargetAtTime(0, T + 0.4, 0.12);
    return 1.0;
  },
});
def('klaxon', {   // a distant motor-car horn: aa-OO-gah (street ambience)
  dur: 1.6, gain: 0.4, prio: 1, gap: 2, max: 1, verb: 0.4,
  fn(E, out, T, o, r) {
    const p = P(o) * (0.9 + 0.2 * r()), lp = E.f('lowpass', 1500, 0.7, out), g = E.g(0);
    g.connect(E.f('bandpass', 700, 2, lp)); g.connect(E.f('bandpass', 1200, 3, E.g(0.6, lp)));
    const s = E.o('sawtooth', 200 * p, T, T + 1.0, g), q = E.o('square', 201 * p, T, T + 1.0, E.g(0.5, g));
    for (const x of [s, q]) { x.frequency.exponentialRampToValueAtTime(330 * p, T + 0.35); x.frequency.setValueAtTime(330 * p, T + 0.55); x.frequency.exponentialRampToValueAtTime(250 * p, T + 0.72); }
    g.gain.setValueAtTime(0, T); g.gain.linearRampToValueAtTime(0.5, T + 0.05); g.gain.linearRampToValueAtTime(0.6, T + 0.5);
    g.gain.linearRampToValueAtTime(0.25, T + 0.56); g.gain.linearRampToValueAtTime(0.55, T + 0.62); g.gain.linearRampToValueAtTime(0, T + 0.86);
    return 1.0;
  },
});
def('trolley', {   // a distant trolley bell: ding-ding
  dur: 2.2, gain: 0.4, prio: 1, gap: 2, max: 1, verb: 0.45,
  fn(E, out, T, o, r) {
    const lp = E.f('lowpass', 3000, 0.7, out), f = 1318.51 * P(o);
    for (const dt of [0, 0.28]) E.modal(lp, T + dt, f, [[1, 0.25, 0.9, 2], [2.32, 0.1, 0.5], [3.9, 0.05, 0.3]], { attack: 0.001 });
    return 1.3;
  },
});
def('pigeons', {   // pigeons take off: a flurry of wing claps
  dur: 1.2, gain: 0.4, prio: 1, gap: 2, max: 1, verb: 0.25,
  fn(E, out, T, o, r) {
    const ns = E.n('white', T, T + 1.0, null), bp = E.f('bandpass', 1200, 0.8), g = E.g(0, out); ns.connect(bp); bp.connect(g);
    g.gain.setValueAtTime(0, T);
    let t = T, a = 1.6;
    for (let k = 0; k < 11; k++) { g.gain.setTargetAtTime(a * (0.7 + 0.3 * r()), t, 0.004); g.gain.setTargetAtTime(0, t + 0.018, 0.012); t += 0.085 + 0.02 * r(); a *= 0.9; }
    return t - T + 0.1;
  },
});
def('ticker', {   // a stock-ticker machine chattering in an office upstairs
  dur: 3.0, gain: 0.6, prio: 1, gap: 2, max: 1, verb: 0.2,
  fn(E, out, T, o, r) {
    const len = 1.2 + 1.3 * r(), stop = T + len + 0.1;
    const ns = E.n('white', T, stop, null), bp = E.f('bandpass', 3400, 2), g = E.g(0, out); ns.connect(bp); bp.connect(g);
    const tg = E.g(0, out); E.o('sine', 2200, T, stop, tg);
    g.gain.setValueAtTime(0, T); tg.gain.setValueAtTime(0, T);
    for (let t = T; t < T + len; t += 0.05 + 0.03 * r()) {
      const pk = 0.8 + 0.6 * r();
      g.gain.setTargetAtTime(pk, t, 0.0003); g.gain.setTargetAtTime(0, t + 0.001, 0.0012);
      tg.gain.setTargetAtTime(0.06 * pk, t, 0.0005); tg.gain.setTargetAtTime(0, t + 0.002, 0.003);
    }
    return len + 0.12;
  },
});

// ------------------------------------------------------------------------------------------------ server events -> sounds (optional)
function eventSounds(ev) {
  if (!ev || typeof ev !== 'object') return [];
  switch (ev.type) {
    case 'refused': case 'refused_broker': return [['refused', { vol: 0.8 }]];
    case 'fill': return [['whoosh', { dir: 1, speed: 1.4 }], ['molasses', { n: 3, delay: 0.32 }]];
    case 'bell': return [['bell', { session: ev.session }]];
    case 'rat': return [['rat', { n: ev.usd > 0.005 ? 3 : 2 }]];
    case 'stake': return [['stake', {}]];
    case 'anvil': return [[ev.ok === false ? 'refused' : 'anvil', {}]];
    case 'wall': return [[ev.ok === false ? 'refused' : 'wall', {}]];
    case 'haggle': return [['haggle', { ok: ev.ok !== false }]];
    case 'machete': return ev.ok === false ? [['refused', {}]] : [['machete', {}], ['stake', { golden: true, delay: 0.5 }]];
    case 'lightning': return [['thunder', { near: true }]];
    case 'freeze': return [[ev.on === false ? 'needle_drop' : 'needle', {}]];
    case 'settled': {
      const tail = [['fold', { delay: 1.6 }], ['thud', { delay: 2.3 }], ['ping', { delay: 2.6 }], ['ping', { delay: 2.75 }], ['ping', { delay: 2.9 }]];
      const head = { buyer: [['cash', {}]], anvil: [['anvil', {}], ['crane', { delay: 0.7 }], ['stamp', { delay: 1.2 }]],
        barrel: [['barrel', {}], ['stamp', { delay: 0.8 }]], merchant: [['tackle', {}], ['coin', { step: 2, delay: 0.4 }]],
        eject: [['balloon', {}]], session: [['flap', { n: 6 }], ['coin', { step: 1, delay: 0.3 }]], kill: [['chain', {}], ['stamp', { delay: 0.5 }]],
        outside: [['page', {}]] }[ev.outcome] || [['flap', {}]];
      return head.concat(tail);
    }
    default: return [];
  }
}

// ------------------------------------------------------------------------------------------------ the realtime singleton
const S = { ctx: null, eng: null, muted: false, volume: 0.8, tension: 0, env: null, timer: 0, suspT: 0, hooked: false };
export let muted = false;

// resume a context we want running; for 0.6 s play() may schedule into it (e.g. unmute + a sound in the same tick), so the sound
// plays the moment the context wakes. Bounded, so a resume the browser blocks can never pile up stale sounds.
function wake() {
  if (!S.ctx || S.ctx.state === 'running' || S.ctx.state === 'closed') return null;
  if (S.eng) S.eng.resumeUntil = performance.now() + 600;
  let p = null; try { p = S.ctx.resume(); } catch (e) { p = null; }
  if (p && p.catch) p.catch(() => {});
  return p;
}
function hookGesture() {
  if (S.hooked || typeof window === 'undefined') return;
  S.hooked = true;
  const go = () => {
    if (!S.ctx) return;
    if (S.ctx.state === 'running' || S.muted) return;
    const p = wake(); if (p && p.then) p.then(() => { if (S.ctx.state === 'running') { S.hooked = false; off(); } }).catch(() => {});
  };
  const evs = ['pointerdown', 'keydown', 'touchend', 'mousedown'];
  const off = () => evs.forEach((e) => window.removeEventListener(e, go, true));
  evs.forEach((e) => window.addEventListener(e, go, true));
}
function init() {
  try {
    if (!S.ctx) {
      const AC = globalThis.AudioContext || globalThis.webkitAudioContext;
      if (!AC) return false;
      S.ctx = new AC({ latencyHint: 'interactive' });
      S.eng = new Engine(S.ctx, { offline: false });
      S.eng.setVolume(S.volume); S.eng.setMuted(S.muted);
      if (S.env != null) S.eng.setAmbience(S.env);
      if (S.tension > 0) S.eng.setTether(S.tension);
      S.timer = setInterval(() => { const e = S.eng; if (e && S.ctx.state === 'running') e.tick(); }, 200);
      setTimeout(() => { try { if (S.eng) S.eng.warm(); } catch (e) { /* */ } }, 0);
    }
    if (S.ctx.state !== 'running' && !S.muted) {
      wake();
      hookGesture();
    } else if (S.muted && S.ctx.state === 'running') {
      clearTimeout(S.suspT); S.suspT = setTimeout(() => { if (S.muted && S.ctx.state === 'running') S.ctx.suspend().catch(() => {}); }, 350);
    }
    return true;
  } catch (e) { return false; }
}
function play(name, opts) {
  const e = S.eng; if (!e) return false;
  try { return e.play(name, opts); } catch (err) { return false; }
}
function setMuted(m) {
  m = !!m; if (m === S.muted) return; S.muted = m; muted = m;
  const e = S.eng; if (!e) return;
  try {
    e.setMuted(m);
    clearTimeout(S.suspT);
    if (m) S.suspT = setTimeout(() => { if (S.muted && S.ctx.state === 'running') S.ctx.suspend().catch(() => {}); }, 350);
    else if (S.ctx.state !== 'running') { wake(); hookGesture(); }
  } catch (err) { /* never throw into the game loop */ }
}
function setVolume(v) { S.volume = clamp(NAN_SAFE(+v, 0.8), 0, 1); try { if (S.eng) S.eng.setVolume(S.volume); } catch (e) { /* */ } }
function setTether(x) { S.tension = clamp(NAN_SAFE(+x, 0), 0, 1); try { if (S.eng) S.eng.setTether(S.tension); } catch (e) { /* */ } }
function setAmbience(env) { S.env = env; try { if (S.eng) S.eng.setAmbience(env); } catch (e) { /* */ } }
function onEvent(ev) { let any = false; for (const [n, o] of eventSounds(ev)) any = play(n, o) || any; return any; }
function duck(amount, secs) { try { if (S.eng && S.eng.beds) S.eng.duck(amount, secs); } catch (e) { /* */ } }
function stopAll() { try { if (S.eng) S.eng.stopAll(); } catch (e) { /* */ } }
function state() {
  const e = S.eng;
  return { ready: !!e, running: !!(S.ctx && S.ctx.state === 'running'), ctxState: S.ctx ? S.ctx.state : 'none', muted: S.muted, volume: S.volume,
    tension: S.tension, ambience: e ? e.ambKey : null, voices: e ? e.voices.filter((v) => v.end > S.ctx.currentTime).length : 0,
    started: e ? e.started : 0, dropped: e ? e.dropped : 0, errors: e ? e.errors.slice() : [] };
}

// ------------------------------------------------------------------------------------------------ offline rendering (self-test)
// script: a sound name, or fn(engine) that schedules plays (use when=...) and may return info. Same Engine, same recipes.
export const OFFLINE_T0 = 0.7;   // offline renders start sounds here, after the master's warm-up crossfade
export async function renderOffline(script, { seconds = 0, sampleRate = 48000, seed = 1, master = true, verb = true, volume = 1, warmup = true } = {}) {
  const OAC = globalThis.OfflineAudioContext || globalThis.webkitOfflineAudioContext;
  if (!OAC) throw new Error('no OfflineAudioContext');
  const secs = seconds || (typeof script === 'string' ? OFFLINE_T0 + soundDur(script) + (verb ? 1.6 : 0.2) : 3);
  const c = new OAC(2, Math.ceil(secs * sampleRate), sampleRate);
  const eng = new Engine(c, { offline: true, seed, master, verb, warmup });
  eng.setVolume(volume);
  const info = typeof script === 'string' ? eng.play(script, {}, OFFLINE_T0) : script(eng);
  const buffer = await c.startRendering();
  return { buffer, engine: eng, info };
}
export function soundDur(name) { const n = RECIPES[name] ? name : ALIAS[name]; return n ? RECIPES[n].dur || 1 : 0; }
export function hasSound(name) { return !!(RECIPES[name] || RECIPES[ALIAS[name]]); }
export { Engine as _Engine };

export const Audio = {
  init, play, setMuted, setVolume, setTether, setAmbience,
  event: onEvent, duck, stopAll, state, render: renderOffline, soundDur, hasSound, NAMES, EXTRAS,
  get muted() { return S.muted; }, set muted(v) { setMuted(v); },
  get ready() { return !!S.eng; },
  get ctx() { return S.ctx; },
};
export default Audio;
export { init, play, setMuted, setVolume, setTether, setAmbience, onEvent as event, duck, stopAll, state };
