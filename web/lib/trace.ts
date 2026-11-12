// A seismogram-style trace from real event times and magnitudes, for decoration only: each event
// becomes a decaying wiggle whose size grows with magnitude, over a little seeded background noise.
// It is not a recorded waveform. Pure, so it is unit-tested with node --test.

export type TraceEvent = readonly [time: number, magnitude: number];

export type TraceOptions = {
  t0: number;
  t1: number;
  samples: number;
  seed: number;
  /** Background noise amplitude, 0..1. Default 0.035. */
  noise?: number;
};

/** Small deterministic PRNG (mulberry32). */
function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function synthTrace(events: readonly TraceEvent[], opts: TraceOptions): Float32Array {
  const { t0, t1, samples, seed } = opts;
  const noise = opts.noise ?? 0.035;
  const out = new Float32Array(samples);
  const span = t1 - t0 || 1;
  const dt = span / Math.max(1, samples - 1);
  const rand = rng(seed);

  for (const [time, mag] of events) {
    if (time > t1) continue;
    const amp = 10 ** (0.6 * (mag - 2));
    const tau = span * 0.004 * (1 + 0.6 * Math.max(0, mag - 2));
    const freq = 1 / (span * 0.003);
    const phase = rand() * Math.PI * 2;
    const start = Math.max(0, Math.ceil((time - t0) / dt));
    const end = Math.min(samples, Math.ceil((time + 6 * tau - t0) / dt));
    for (let i = start; i < end; i += 1) {
      const s = t0 + i * dt - time;
      out[i] += amp * Math.exp(-s / tau) * Math.sin(2 * Math.PI * freq * s + phase);
    }
  }

  let peak = 0;
  for (const v of out) peak = Math.max(peak, Math.abs(v));
  const scale = peak > 0 ? (0.95 - noise) / peak : 0;
  for (let i = 0; i < samples; i += 1) {
    const v = out[i] * scale + (rand() * 2 - 1) * noise;
    out[i] = Math.max(-1, Math.min(1, v));
  }
  return out;
}
