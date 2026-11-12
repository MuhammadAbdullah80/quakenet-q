import "server-only";
import type { BackendFailure } from "@/lib/backend";

// Responses of this console's own route handlers use the same error shape as
// the backend contract: {"error": {"code", "message"}}.

const NO_STORE = { "Cache-Control": "no-store" };

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return Response.json(body, { status, headers: { ...NO_STORE, ...headers } });
}

export function jsonError(
  status: number,
  code: string,
  message: string,
  headers: Record<string, string> = {},
): Response {
  return json({ error: { code, message } }, status, headers);
}

export function failureResponse(failure: BackendFailure): Response {
  if (failure.kind === "unreachable") {
    return jsonError(503, "BACKEND_OFFLINE", "The backend is not reachable right now.");
  }
  if (failure.kind === "api") {
    // The backend's own 401 means this console's shared secret is wrong. That is
    // a server fault, not the visitor's, so it must not look like a passcode error.
    if (failure.code === "UNAUTHORIZED") {
      return jsonError(502, "BACKEND_REJECTED", "The backend rejected this console's credentials.");
    }
    const headers: Record<string, string> = {};
    if (failure.retryAfterSeconds) headers["Retry-After"] = String(failure.retryAfterSeconds);
    return jsonError(failure.status, failure.code, failure.message, headers);
  }
  return jsonError(502, "BAD_RESPONSE", "The backend sent an unexpected response.");
}

/** Read a small JSON body; null when it is missing, too large or not JSON. */
export async function readSmallJson(request: Request, maxBytes = 2048): Promise<unknown | null> {
  const type = request.headers.get("content-type") ?? "";
  if (!type.toLowerCase().startsWith("application/json")) return null;
  const text = await request.text();
  if (text.length === 0 || text.length > maxBytes) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}
