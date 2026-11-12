import "server-only";
import { unstable_rethrow } from "next/navigation";
import type { z } from "zod";

// The only place that talks to the Python API. Server-side only: BACKEND_URL
// and BACKEND_TOKEN must never be sent to the browser.

const API_BASE_PATH = "/api/v1";
const TIMEOUT_MS = 10_000;
/** After a failed connection, skip further attempts for this long so one page
 *  does not wait for several 10 s timeouts in a row. */
const DOWN_MEMO_MS = 15_000;

const KNOWN_CODES = [
  "UNAUTHORIZED",
  "NOT_FOUND",
  "INVALID_INPUT",
  "RATE_LIMITED",
  "JOB_RUNNING",
  "NOT_BUILT",
  "INTERNAL",
] as const;
export type BackendErrorCode = (typeof KNOWN_CODES)[number];

export type UnreachableReason = "not_configured" | "timeout" | "network" | "gateway";

export type BackendResult<T> =
  | { ok: true; status: number; data: T }
  /** Backend not configured, not reachable, or timed out: use snapshots. */
  | { ok: false; kind: "unreachable"; reason: UnreachableReason }
  /** The backend answered with its error contract. */
  | {
      ok: false;
      kind: "api";
      status: number;
      code: BackendErrorCode;
      message: string;
      retryAfterSeconds: number | null;
    }
  /** The backend answered, but not with what docs/API.md describes. */
  | { ok: false; kind: "invalid"; status: number; message: string };

export type BackendFailure = Exclude<BackendResult<never>, { ok: true }>;

let downUntil = 0;

function config(): { base: string; token: string } | null {
  const rawUrl = process.env.BACKEND_URL?.trim();
  const token = process.env.BACKEND_TOKEN?.trim();
  if (!rawUrl || !token) return null;
  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    return null;
  }
  const local =
    url.hostname === "localhost" || url.hostname === "127.0.0.1" || url.hostname === "[::1]";
  // The token must not travel in clear text, except to a backend on this machine.
  if (url.protocol !== "https:" && !(url.protocol === "http:" && local)) return null;
  return { base: url.origin + API_BASE_PATH, token };
}

export function backendConfigured(): boolean {
  return config() !== null;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT";
  body?: unknown;
  /** Visitor IP, forwarded so the backend can rate-limit per visitor. */
  clientIp?: string | null;
};

/**
 * Call the backend. `path` is relative to /api/v1 and must be built from
 * validated pieces only (never from a user-supplied URL).
 */
export async function backendRequest<S extends z.ZodType>(
  path: string,
  schema: S,
  options: RequestOptions = {},
): Promise<BackendResult<z.infer<S>>> {
  const cfg = config();
  if (!cfg) return { ok: false, kind: "unreachable", reason: "not_configured" };
  if (performance.now() < downUntil) return { ok: false, kind: "unreachable", reason: "network" };

  const headers: Record<string, string> = {
    Authorization: `Bearer ${cfg.token}`,
    Accept: "application/json",
  };
  if (options.clientIp) headers["X-Client-IP"] = options.clientIp;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(cfg.base + path, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (err) {
    // Next.js aborts pending work with its own errors when a prerender pass ends.
    // Those are not backend failures: hand them back to the framework.
    unstable_rethrow(err);
    downUntil = performance.now() + DOWN_MEMO_MS;
    const timedOut =
      err instanceof Error && (err.name === "TimeoutError" || err.name === "AbortError");
    const cause = err instanceof Error ? (err.cause as { code?: unknown } | undefined) : undefined;
    // Path and error class only: never the backend address or the token.
    console.warn(
      JSON.stringify({
        level: "warn",
        msg: "backend unreachable",
        path,
        error: err instanceof Error ? err.name : "unknown",
        code: typeof cause?.code === "string" ? cause.code : undefined,
        detail: process.env.NODE_ENV !== "production" && err instanceof Error ? err.message : undefined,
      }),
    );
    return { ok: false, kind: "unreachable", reason: timedOut ? "timeout" : "network" };
  }

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (response.ok) {
    const parsed = schema.safeParse(payload);
    if (parsed.success) return { ok: true, status: response.status, data: parsed.data };
    // Details go to the server log only (path and status; never the token).
    console.error(
      JSON.stringify({
        level: "error",
        msg: "backend response did not match the contract",
        path,
        status: response.status,
      }),
    );
    return {
      ok: false,
      kind: "invalid",
      status: response.status,
      message: "The backend sent an unexpected response.",
    };
  }

  const error = readErrorContract(payload);
  if (error) {
    const retry = Number(response.headers.get("retry-after"));
    return {
      ok: false,
      kind: "api",
      status: response.status,
      code: error.code,
      message: error.message,
      retryAfterSeconds: Number.isFinite(retry) && retry > 0 ? Math.ceil(retry) : null,
    };
  }

  // A gateway error without the API's error body comes from the tunnel relay:
  // the laptop is off or asleep.
  if (response.status === 502 || response.status === 503 || response.status === 504) {
    downUntil = performance.now() + DOWN_MEMO_MS;
    return { ok: false, kind: "unreachable", reason: "gateway" };
  }
  return {
    ok: false,
    kind: "invalid",
    status: response.status,
    message: "The backend sent an unexpected response.",
  };
}

function readErrorContract(payload: unknown): { code: BackendErrorCode; message: string } | null {
  if (typeof payload !== "object" || payload === null) return null;
  const error = (payload as { error?: unknown }).error;
  if (typeof error !== "object" || error === null) return null;
  const { code, message } = error as { code?: unknown; message?: unknown };
  const known = KNOWN_CODES.find((c) => c === code);
  if (!known) return null;
  return { code: known, message: typeof message === "string" ? message.slice(0, 500) : "" };
}
