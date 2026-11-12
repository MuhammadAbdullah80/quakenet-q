import { cookies } from "next/headers";
import { z } from "zod";
import { json, jsonError, readSmallJson } from "@/lib/api-response";
import { clientIpFrom } from "@/lib/client-ip";
import {
  passcodeAttemptAllowed,
  passcodeConfigured,
  passcodeMatches,
  RUN_COOKIE,
  runCookieOptions,
  runCookieValue,
  sameOrigin,
} from "@/lib/passcode";

const bodySchema = z.strictObject({ passcode: z.string().min(1).max(200) });

/** Check the team passcode and, if right, set the cookie that allows starting runs. */
export async function POST(request: Request) {
  if (!sameOrigin(request)) return jsonError(403, "FORBIDDEN", "Cross-site request refused.");

  const limit = passcodeAttemptAllowed(clientIpFrom(request.headers) ?? "unknown");
  if (!limit.allowed) {
    return jsonError(429, "RATE_LIMITED", "Too many passcode attempts. Try again later.", {
      "Retry-After": String(limit.retryAfterSeconds),
    });
  }

  const parsed = bodySchema.safeParse(await readSmallJson(request));
  if (!parsed.success) return jsonError(400, "INVALID_INPUT", "Send a passcode.");

  const value = runCookieValue();
  if (!passcodeConfigured() || !value || !passcodeMatches(parsed.data.passcode)) {
    return jsonError(401, "UNAUTHORIZED", "That passcode is not correct.");
  }

  (await cookies()).set(RUN_COOKIE, value, runCookieOptions);
  return json({ ok: true });
}

/** Forget the passcode on this browser. */
export async function DELETE(request: Request) {
  if (!sameOrigin(request)) return jsonError(403, "FORBIDDEN", "Cross-site request refused.");
  (await cookies()).set(RUN_COOKIE, "", { ...runCookieOptions, maxAge: 0 });
  return json({ ok: true });
}
