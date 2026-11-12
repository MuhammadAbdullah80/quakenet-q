// Input limits from docs/API.md. No imports, so browser code can use it cheaply.

export const LIMITS = {
  reps: { min: 1, max: 5, default: 1 },
  seed: { min: 0, max: 9999, default: 0 },
  shots: { min: 128, max: 4096, default: 1024 },
  lam: { min: 0, max: 1000, default: 150 },
} as const;

/** Event and job IDs that may be placed in a backend path. */
export const ID_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;
