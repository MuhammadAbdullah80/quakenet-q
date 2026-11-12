import "server-only";
import { createHash, createHmac, timingSafeEqual } from "node:crypto";

// Team passcode gate for starting runs. The cookie never contains the passcode
// itself: it holds an HMAC keyed by the passcode, so changing RUN_PASSCODE
// invalidates every existing cookie.

/** "__Host-" makes browsers require Secure, Path=/ and no Domain. */
export const RUN_COOKIE = "__Host-qn_run";

export const runCookieOptions = {
  httpOnly: true,
  secure: true,
  sameSite: "strict",
  path: "/",
  maxAge: 12 * 60 * 60,
} as const;

function passcode(): string | null {
  const value = process.env.RUN_PASSCODE;
  return value && value.length > 0 ? value : null;
}

export function passcodeConfigured(): boolean {
  return passcode() !== null;
}

/** Constant-time string comparison (hashing first hides the length too). */
function safeEqual(a: string, b: string): boolean {
  const ha = createHash("sha256").update(a, "utf8").digest();
  const hb = createHash("sha256").update(b, "utf8").digest();
  return timingSafeEqual(ha, hb);
}

export function passcodeMatches(candidate: string): boolean {
  const expected = passcode();
  if (!expected) return false;
  return safeEqual(candidate, expected);
}

export function runCookieValue(): string | null {
  const secret = passcode();
  if (!secret) return null;
  return createHmac("sha256", secret).update("quakenet-q/run-cookie/v1").digest("base64url");
}

export function runCookieValid(value: string | undefined): boolean {
  const expected = runCookieValue();
  if (!expected || !value) return false;
  return safeEqual(value, expected);
}

// Best-effort brake on passcode guessing. In-memory, so it is per server
// instance; the passcode must still be long enough not to be guessable.
const WINDOW_MS = 5 * 60 * 1000;
const MAX_ATTEMPTS = 10;
const attempts = new Map<string, { count: number; resetAt: number }>();

export function passcodeAttemptAllowed(key: string): {
  allowed: boolean;
  retryAfterSeconds: number;
} {
  const now = Date.now();
  if (attempts.size > 5000) {
    for (const [k, v] of attempts) if (v.resetAt <= now) attempts.delete(k);
  }
  const entry = attempts.get(key);
  if (!entry || entry.resetAt <= now) {
    attempts.set(key, { count: 1, resetAt: now + WINDOW_MS });
    return { allowed: true, retryAfterSeconds: 0 };
  }
  entry.count += 1;
  return {
    allowed: entry.count <= MAX_ATTEMPTS,
    retryAfterSeconds: Math.ceil((entry.resetAt - now) / 1000),
  };
}

/** Reject cross-site POSTs: when an Origin header is present it must be ours. */
export function sameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return true; // non-browser client; the SameSite=Strict cookie still applies
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}
