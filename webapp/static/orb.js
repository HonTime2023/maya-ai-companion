/**
 * orb.js — MAYA Super-Intelligence Orb v4
 *
 * FIXED: public `state` getter so app.js can route amplitude correctly.
 *
 * Visual effects driven by amplitude (0–1):
 *   • Multi-frequency distorted waveform edge  — spikes and breathes with voice
 *   • Dynamic colour shift  — interpolates toward bright/white at peak amplitude
 *   • Aurora plasma interior (moving radial gradients)
 *   • Concentric dashed data-rings (rotate at different speeds/directions)
 *   • Neural mesh (Fibonacci nodes + glowing connections, most active on thinking)
 *   • Plasma tendrils  — extend and brighten with amplitude during speaking
 *   • Expanding pulse rings  — emitted on amplitude spikes
 *   • Radar scan sweep during thinking
 *   • Geometric sigil (hexagon + counter-rotating triangle + core dot)
 *   • All colours via rgba(r,g,b,a) — zero hex manipulation
 */

class MayaOrb {
  constructor(canvasId) {
    this._canvas = document.getElementById(canvasId);
    this._ctx    = this._canvas ? this._canvas.getContext('2d') : null;
    this._W = 320; this._H = 320; this._R = 108;
    if (this._canvas) { this._canvas.width = this._W; this._canvas.height = this._H; }
    this._cx = 160; this._cy = 160;

    this._state     = 'idle';
    this._amp       = 0;      // smoothed current amplitude
    this._targetAmp = 0;      // raw amplitude set by app.js
    this._prevAmp   = 0;      // for spike detection
    this._t         = 0;
    this._scanAngle = -Math.PI / 2;

    // Expanding pulse rings emitted on amplitude spikes
    this._pulseRings = [];

    // Fibonacci-spiral neural nodes (22 points)
    this._nodes = [];
    const PHI = 2.39996;
    for (let i = 0; i < 22; i++) {
      const a = i * PHI;
      const r = this._R * (0.14 + (i / 22) * 0.77);
      this._nodes.push({
        x: this._cx + Math.cos(a) * r,
        y: this._cy + Math.sin(a) * r,
        r, a,
        size:       1.2 + Math.random() * 1.6,
        pulse:      Math.random() * Math.PI * 2,
        pulseSpeed: 0.018 + Math.random() * 0.038,
        active: false,
      });
    }

    // Particles
    this._particles = Array.from({ length: 72 }, () => this._mkParticle());

    if (this._ctx) this._loop();
  }

  // ── Public API ────────────────────────────────────────────────────────
  get state()        { return this._state; }
  setState(s)        { this._state = s; }
  setAmplitude(a)    { this._targetAmp = Math.min(1, Math.max(0, a)); }

  // ── Dynamic colour palette — shifts toward bright at high amplitude ───
  _pal(amp) {
    const lerp = (a, b, t) => Math.round(a + (b - a) * Math.min(1, t));
    switch (this._state) {
      case 'listening': return {
        c: `${lerp(0,140,amp)},${lerp(212,240,amp)},255`,
        a: `${lerp(0,120,amp)},255,${lerp(157,220,amp)}`,
      };
      case 'speaking': return {
        c: `${lerp(123,200,amp)},${lerp(47,100,amp)},255`,
        a: `255,${lerp(45,160,amp)},${lerp(206,255,amp)}`,
      };
      case 'thinking': return {
        c: `255,${lerp(184,220,amp)},${lerp(0,80,amp)}`,
        a: `255,${lerp(110,180,amp)},0`,
      };
      default: return {  // idle
        c: `${lerp(0,60,amp)},${lerp(212,228,amp)},255`,
        a: `0,${lerp(157,200,amp)},${lerp(200,255,amp)}`,
      };
    }
  }

  // ── Particle factory ──────────────────────────────────────────────────
  _mkParticle(fromEdge = false) {
    const angle = Math.random() * Math.PI * 2;
    const r = fromEdge
      ? this._R * (0.72 + Math.random() * 0.22)
      : Math.random() * this._R * 0.88;
    return {
      x: this._cx + Math.cos(angle) * r,
      y: this._cy + Math.sin(angle) * r,
      vx: (Math.random() - 0.5) * 0.44,
      vy: (Math.random() - 0.5) * 0.44,
      s:  0.5 + Math.random() * 1.8,
      life:  Math.random(),
      speed: 0.0035 + Math.random() * 0.0075,
    };
  }

  // ════════════════════════════════════════════════════════════════════
  //  MAIN DRAW LOOP
  // ════════════════════════════════════════════════════════════════════
  _draw() {
    if (!this._ctx) return;
    const ctx = this._ctx;
    const { _cx: cx, _cy: cy, _R: R } = this;

    // ── Amplitude smoothing — faster attack, slower decay ────────────
    const attackRate = 0.22;
    const decayRate  = 0.10;
    const rate = this._targetAmp > this._amp ? attackRate : decayRate;
    this._amp += (this._targetAmp - this._amp) * rate;
    this._t   += 0.016;

    const amp = this._amp;
    const t   = this._t;
    const { c: rgb, a: rgb2 } = this._pal(amp);
    const breathe  = Math.sin(t * 0.75) * 0.5 + 0.5;
    const isIdle   = this._state === 'idle';

    // ── Spike detection → emit pulse ring ────────────────────────────
    if (amp - this._prevAmp > 0.14 && amp > 0.4) {
      this._pulseRings.push({ r: R + 6, alpha: 0.55 + amp * 0.3 });
    }
    this._prevAmp = amp;

    ctx.clearRect(0, 0, this._W, this._H);

    // ── 1. EXPANDING PULSE RINGS (behind everything) ─────────────────
    this._pulseRings = this._pulseRings.filter(pr => pr.alpha > 0.01);
    for (const pr of this._pulseRings) {
      pr.r     += 2.8;
      pr.alpha *= 0.91;
      ctx.beginPath(); ctx.arc(cx, cy, pr.r, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${rgb},${pr.alpha.toFixed(3)})`;
      ctx.lineWidth = 1.4; ctx.stroke();
    }

    // ── 2. OUTER CORONA ──────────────────────────────────────────────
    const coronaAmp = isIdle ? breathe * 0.18 : amp;
    const coronaR   = R + 28 + coronaAmp * 90;
    const corona = ctx.createRadialGradient(cx, cy, R * 0.6, cx, cy, coronaR);
    corona.addColorStop(0,   `rgba(${rgb},${(0.16 + coronaAmp * 0.32).toFixed(3)})`);
    corona.addColorStop(0.4, `rgba(${rgb},${(0.04 + coronaAmp * 0.12).toFixed(3)})`);
    corona.addColorStop(1,   `rgba(${rgb},0)`);
    ctx.beginPath(); ctx.arc(cx, cy, coronaR, 0, Math.PI * 2);
    ctx.fillStyle = corona; ctx.fill();

    if (!isIdle) {
      // accent halo
      ctx.beginPath(); ctx.arc(cx, cy, R + 18 + amp * 36, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${rgb2},${(0.20 + amp * 0.40).toFixed(3)})`;
      ctx.lineWidth = 0.9; ctx.stroke();
    }

    // ── 3. CLIPPED ORB INTERIOR ───────────────────────────────────────
    ctx.save();
    this._clipWave(ctx, cx, cy, R, amp, t);

    ctx.fillStyle = '#040810';
    ctx.fillRect(0, 0, this._W, this._H);

    this._drawAurora   (ctx, cx, cy, R, rgb, rgb2, amp, t, breathe);
    this._drawDataRings(ctx, cx, cy, R, rgb, amp, t);
    this._drawNeural   (ctx, cx, cy, R, rgb, rgb2, amp, t);
    this._drawParticles(ctx, rgb, rgb2, amp);

    if (this._state === 'speaking')
      this._drawTendrils(ctx, cx, cy, R, rgb2, amp, t);

    if (this._state === 'thinking')
      this._drawScanSweep(ctx, cx, cy, R, rgb, t);

    // Flash burst on high amplitude (speaking/listening)
    if (amp > 0.55 && !isIdle) {
      const burstR = R * (0.35 + amp * 0.5);
      const burst  = ctx.createRadialGradient(cx, cy, 0, cx, cy, burstR);
      burst.addColorStop(0,   `rgba(${rgb2},${((amp - 0.5) * 0.25).toFixed(3)})`);
      burst.addColorStop(0.5, `rgba(${rgb2},${((amp - 0.5) * 0.08).toFixed(3)})`);
      burst.addColorStop(1,   `rgba(${rgb2},0)`);
      ctx.fillStyle = burst; ctx.fillRect(0, 0, this._W, this._H);
    }

    this._drawSigil(ctx, cx, cy, R, rgb, rgb2, amp, t, breathe);

    ctx.restore(); // end clip

    // ── 4. WAVEFORM BORDER ────────────────────────────────────────────
    this._drawWaveBorder(ctx, cx, cy, R, rgb, rgb2, amp, t);

    // ── 5. SPECULAR ───────────────────────────────────────────────────
    const hx = cx - R * 0.22, hy = cy - R * 0.3;
    const spec = ctx.createRadialGradient(hx, hy, 0, hx, hy, R * 0.38);
    spec.addColorStop(0, 'rgba(255,255,255,0.11)');
    spec.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.beginPath(); ctx.arc(hx, hy, R * 0.38, 0, Math.PI * 2);
    ctx.fillStyle = spec; ctx.fill();

    // ── 6. STATE LABEL ────────────────────────────────────────────────
    const lbl = document.querySelector('.orb-state-label');
    if (lbl) {
      const labels = { idle:'STANDBY', listening:'LISTENING', speaking:'SPEAKING', thinking:'PROCESSING' };
      lbl.textContent = labels[this._state] || 'STANDBY';
      lbl.className   = `orb-state-label ${this._state !== 'idle' ? this._state : ''}`;
    }
  }

  // ════════════════════════════════════════════════════════════════════
  //  CLIP SHAPE — distorted waveform circle
  // ════════════════════════════════════════════════════════════════════
  _clipWave(ctx, cx, cy, R, amp, t) {
    const N = 96;
    ctx.beginPath();
    for (let i = 0; i <= N; i++) {
      const angle = (i / N) * Math.PI * 2;
      const d = R
        + Math.sin(angle * 4  + t * 1.1) * (2 + amp * 14)
        + Math.sin(angle * 9  - t * 1.7) * (1 + amp *  8);
      const x = cx + Math.cos(angle) * d;
      const y = cy + Math.sin(angle) * d;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.clip();
  }

  // ════════════════════════════════════════════════════════════════════
  //  WAVEFORM BORDER — 3 layers
  // ════════════════════════════════════════════════════════════════════
  _drawWaveBorder(ctx, cx, cy, R, rgb, rgb2, amp, t) {
    // Layer 1 — primary waveform outline
    const N = 220;
    ctx.beginPath();
    for (let i = 0; i <= N; i++) {
      const angle = (i / N) * Math.PI * 2;
      const d = R
        + Math.sin(angle * 4  + t * 1.1) * (2 + amp * 14)
        + Math.sin(angle * 9  - t * 1.7) * (1 + amp *  8)
        + Math.sin(angle * 17 + t * 2.4) * (amp * 6);
      const x = cx + Math.cos(angle) * d;
      const y = cy + Math.sin(angle) * d;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = `rgba(${rgb},${(0.50 + amp * 0.45).toFixed(3)})`;
    ctx.lineWidth   = 1.8; ctx.stroke();

    // Layer 2 — accent counter-wave
    ctx.beginPath();
    for (let i = 0; i <= N; i++) {
      const angle = (i / N) * Math.PI * 2;
      const d = R + 5
        + Math.sin(angle * 4  + t * 1.1 + Math.PI) * (1 + amp * 8)
        + Math.sin(angle * 6  - t * 1.4)            * (amp * 9);
      const x = cx + Math.cos(angle) * d;
      const y = cy + Math.sin(angle) * d;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = `rgba(${rgb2},${(0.14 + amp * 0.36).toFixed(3)})`;
    ctx.lineWidth   = 0.8; ctx.stroke();

    // Layer 3 — outer glow ring (simple circle) at peak
    if (amp > 0.3) {
      ctx.beginPath(); ctx.arc(cx, cy, R + 22 + amp * 28, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${rgb},${((amp - 0.3) * 0.25).toFixed(3)})`;
      ctx.lineWidth = 3; ctx.stroke();
    }
  }

  // ════════════════════════════════════════════════════════════════════
  //  AURORA PLASMA
  // ════════════════════════════════════════════════════════════════════
  _drawAurora(ctx, cx, cy, R, rgb, rgb2, amp, t, breathe) {
    const ox = Math.cos(t * 0.28) * R * 0.18;
    const oy = Math.sin(t * 0.35) * R * 0.18;
    const g1 = ctx.createRadialGradient(cx + ox, cy + oy, 0, cx, cy, R);
    g1.addColorStop(0,    `rgba(${rgb},${(0.14 + amp * 0.26 + breathe * 0.04).toFixed(3)})`);
    g1.addColorStop(0.38, `rgba(${rgb},${(0.05 + amp * 0.12).toFixed(3)})`);
    g1.addColorStop(0.72, `rgba(${rgb2},${(0.03 + amp * 0.07).toFixed(3)})`);
    g1.addColorStop(1,    `rgba(0,0,0,0)`);
    ctx.fillStyle = g1; ctx.fillRect(0, 0, this._W, this._H);

    const sx = cx + Math.cos(t * 0.48) * R * 0.32;
    const sy = cy + Math.sin(t * 0.61) * R * 0.32;
    const g2 = ctx.createRadialGradient(sx, sy, 0, sx, sy, R * 0.75);
    g2.addColorStop(0,   `rgba(${rgb2},${(0.10 + amp * 0.22).toFixed(3)})`);
    g2.addColorStop(0.55,`rgba(${rgb2},${(0.02 + amp * 0.07).toFixed(3)})`);
    g2.addColorStop(1,   `rgba(${rgb2},0)`);
    ctx.fillStyle = g2; ctx.fillRect(0, 0, this._W, this._H);

    // Breathing core
    const cR = R * (0.26 + amp * 0.38 + breathe * 0.05);
    const gc = ctx.createRadialGradient(cx, cy, 0, cx, cy, cR);
    gc.addColorStop(0,   `rgba(${rgb},${(0.26 + amp * 0.44 + breathe * 0.06).toFixed(3)})`);
    gc.addColorStop(0.5, `rgba(${rgb},${(0.08 + amp * 0.18).toFixed(3)})`);
    gc.addColorStop(1,   `rgba(${rgb},0)`);
    ctx.fillStyle = gc; ctx.fillRect(0, 0, this._W, this._H);
  }

  // ════════════════════════════════════════════════════════════════════
  //  DATA RINGS
  // ════════════════════════════════════════════════════════════════════
  _drawDataRings(ctx, cx, cy, R, rgb, amp, t) {
    const rings = [
      { rF: 0.52, spd: 0.0080, dir:  1, dash: [5, 10], a: 0.09 + amp * 0.18 },
      { rF: 0.69, spd: 0.0048, dir: -1, dash: [3, 16], a: 0.07 + amp * 0.16 },
      { rF: 0.85, spd: 0.0120, dir:  1, dash: [7,  7], a: 0.09 + amp * 0.20 },
    ];
    for (const ring of rings) {
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(ring.dir * t * ring.spd * 60);
      ctx.translate(-cx, -cy);
      ctx.beginPath(); ctx.arc(cx, cy, R * ring.rF, 0, Math.PI * 2);
      ctx.setLineDash(ring.dash);
      ctx.strokeStyle = `rgba(${rgb},${ring.a.toFixed(3)})`;
      ctx.lineWidth = 0.7; ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }
  }

  // ════════════════════════════════════════════════════════════════════
  //  NEURAL MESH
  // ════════════════════════════════════════════════════════════════════
  _drawNeural(ctx, cx, cy, R, rgb, rgb2, amp, t) {
    const nodes    = this._nodes;
    const isThink  = this._state === 'thinking';
    const isSpeak  = this._state === 'speaking';
    const isListen = this._state === 'listening';
    const thresh   = R * 0.56;

    for (const n of nodes) {
      n.pulse += n.pulseSpeed;
      n.active = Math.sin(n.pulse) > (isThink ? 0.2 : 0.5);
    }

    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dist = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
        if (dist > thresh) continue;
        const both  = nodes[i].active && nodes[j].active;
        const base  = isThink ? 0.14 : (isSpeak ? 0.09 : (isListen ? 0.06 : 0.03));
        const extra = both ? (0.20 + amp * 0.28) : 0;
        const alpha = (base + extra) * (1 - dist / thresh);
        if (alpha < 0.012) continue;
        ctx.beginPath();
        ctx.moveTo(nodes[i].x, nodes[i].y);
        ctx.lineTo(nodes[j].x, nodes[j].y);
        ctx.strokeStyle = `rgba(${both ? rgb2 : rgb},${alpha.toFixed(3)})`;
        ctx.lineWidth   = both ? (0.75 + amp * 0.5) : 0.35;
        ctx.stroke();
      }
    }

    for (const n of nodes) {
      const bright    = Math.sin(n.pulse) * 0.5 + 0.5;
      const baseAlpha = isThink ? 0.35 + amp * 0.35 : (isSpeak ? 0.24 + amp * 0.40 : (isListen ? 0.18 : 0.08));
      const alpha     = baseAlpha * bright;
      const size      = n.size * (0.65 + bright * 0.5 + (n.active ? amp * 1.0 : 0));
      if (n.active && amp > 0.04) {
        const ng = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, size * 5);
        ng.addColorStop(0, `rgba(${rgb2},${(alpha * 0.6).toFixed(3)})`);
        ng.addColorStop(1, `rgba(${rgb2},0)`);
        ctx.beginPath(); ctx.arc(n.x, n.y, size * 5, 0, Math.PI * 2);
        ctx.fillStyle = ng; ctx.fill();
      }
      ctx.beginPath(); ctx.arc(n.x, n.y, Math.max(0.3, size), 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${n.active ? rgb2 : rgb},${alpha.toFixed(3)})`;
      ctx.fill();
    }
  }

  // ════════════════════════════════════════════════════════════════════
  //  PARTICLES
  // ════════════════════════════════════════════════════════════════════
  _drawParticles(ctx, rgb, rgb2, amp) {
    const active = this._state !== 'idle';
    for (const p of this._particles) {
      p.life += p.speed;
      if (p.life > 1) Object.assign(p, this._mkParticle(active));
      p.x += p.vx; p.y += p.vy;
      if (Math.hypot(p.x - this._cx, p.y - this._cy) > this._R * 0.94)
        Object.assign(p, this._mkParticle(false));
      const alpha = Math.sin(p.life * Math.PI) * (active ? 0.45 + amp * 0.50 : 0.14);
      ctx.beginPath(); ctx.arc(p.x, p.y, p.s, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${rgb},${alpha.toFixed(3)})`;
      ctx.fill();
    }
  }

  // ════════════════════════════════════════════════════════════════════
  //  PLASMA TENDRILS (speaking — always on, scale with amplitude)
  // ════════════════════════════════════════════════════════════════════
  _drawTendrils(ctx, cx, cy, R, rgb2, amp, t) {
    const count   = 8;
    const minLen  = R * 0.18;   // visible even at amp=0
    const maxExtra= R * 0.75;
    for (let i = 0; i < count; i++) {
      const baseA  = (i / count) * Math.PI * 2 + t * 0.35;
      const len    = minLen + amp * maxExtra;
      const wobble = Math.sin(t * 1.8 + i * 1.2) * 0.55;
      const cpA    = baseA + wobble;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(baseA + 0.3) * R * 0.3, cy + Math.sin(baseA + 0.3) * R * 0.3);
      ctx.quadraticCurveTo(
        cx + Math.cos(cpA) * len * 0.55,
        cy + Math.sin(cpA) * len * 0.55,
        cx + Math.cos(baseA) * len,
        cy + Math.sin(baseA) * len
      );
      ctx.strokeStyle = `rgba(${rgb2},${(0.08 + amp * 0.38).toFixed(3)})`;
      ctx.lineWidth   = 0.8 + amp * 0.7;
      ctx.stroke();

      // tip glow
      const tipX = cx + Math.cos(baseA) * len;
      const tipY = cy + Math.sin(baseA) * len;
      const tg   = ctx.createRadialGradient(tipX, tipY, 0, tipX, tipY, 4 + amp * 5);
      tg.addColorStop(0, `rgba(${rgb2},${(amp * 0.65).toFixed(3)})`);
      tg.addColorStop(1, `rgba(${rgb2},0)`);
      ctx.beginPath(); ctx.arc(tipX, tipY, 4 + amp * 5, 0, Math.PI * 2);
      ctx.fillStyle = tg; ctx.fill();
    }
  }

  // ════════════════════════════════════════════════════════════════════
  //  RADAR SCAN SWEEP (thinking only)
  // ════════════════════════════════════════════════════════════════════
  _drawScanSweep(ctx, cx, cy, R, rgb, t) {
    this._scanAngle = (this._scanAngle + 0.028) % (Math.PI * 2);
    const a = this._scanAngle, sweep = 0.85, rScan = R * 0.93;
    const steps = 14;
    for (let i = 0; i < steps; i++) {
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, rScan, a - sweep * (1 - i / steps), a - sweep * (1 - (i + 1) / steps));
      ctx.closePath();
      ctx.fillStyle = `rgba(${rgb},${((i / steps) * 0.11).toFixed(3)})`;
      ctx.fill();
    }
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(a) * rScan, cy + Math.sin(a) * rScan);
    ctx.strokeStyle = `rgba(${rgb},0.55)`; ctx.lineWidth = 1.3; ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx + Math.cos(a) * rScan, cy + Math.sin(a) * rScan, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${rgb},0.9)`; ctx.fill();
    ctx.beginPath(); ctx.arc(cx, cy, rScan, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(${rgb},0.10)`; ctx.lineWidth = 0.6; ctx.stroke();
  }

  // ════════════════════════════════════════════════════════════════════
  //  GEOMETRIC SIGIL
  // ════════════════════════════════════════════════════════════════════
  _drawSigil(ctx, cx, cy, R, rgb, rgb2, amp, t, breathe) {
    const r1  = R * (0.115 + amp * 0.09 + breathe * 0.012);
    const rot = t * 0.38;

    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const a = (i / 6) * Math.PI * 2 + rot;
      i === 0
        ? ctx.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1)
        : ctx.lineTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
    }
    ctx.closePath();
    ctx.strokeStyle = `rgba(${rgb},${(0.30 + amp * 0.50).toFixed(3)})`;
    ctx.lineWidth   = 0.9; ctx.stroke();

    const r2 = r1 * 0.54;
    ctx.beginPath();
    for (let i = 0; i < 3; i++) {
      const a = (i / 3) * Math.PI * 2 - rot * 1.7;
      i === 0
        ? ctx.moveTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2)
        : ctx.lineTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2);
    }
    ctx.closePath();
    ctx.strokeStyle = `rgba(${rgb2},${(0.24 + amp * 0.55).toFixed(3)})`;
    ctx.lineWidth   = 0.8; ctx.stroke();

    const dR = 2.8 + amp * 4.5 + breathe * 0.8;
    const dg = ctx.createRadialGradient(cx, cy, 0, cx, cy, dR * 3);
    dg.addColorStop(0,    `rgba(${rgb},${(0.60 + amp * 0.35).toFixed(3)})`);
    dg.addColorStop(0.45, `rgba(${rgb},${(0.15 + amp * 0.20).toFixed(3)})`);
    dg.addColorStop(1,    `rgba(${rgb},0)`);
    ctx.beginPath(); ctx.arc(cx, cy, dR * 3, 0, Math.PI * 2);
    ctx.fillStyle = dg; ctx.fill();
    ctx.beginPath(); ctx.arc(cx, cy, dR, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(255,255,255,${(0.55 + amp * 0.40 + breathe * 0.08).toFixed(3)})`;
    ctx.fill();
  }

  // ════════════════════════════════════════════════════════════════════
  _loop() { this._draw(); requestAnimationFrame(() => this._loop()); }
}
