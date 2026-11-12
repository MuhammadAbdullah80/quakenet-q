import { cookies } from "next/headers";
import { failureResponse, json, jsonError, readSmallJson } from "@/lib/api-response";
import { backendRequest } from "@/lib/backend";
import { clientIpFrom } from "@/lib/client-ip";
import { RUN_COOKIE, runCookieValid, sameOrigin } from "@/lib/passcode";
import { ID_PATTERN, jobCreatedSchema, startJobSchema } from "@/lib/schemas";

/**
 * Start a job: a QAOA run (kind "qaoa") or a replay of the earthquake (kind "sequence"). The browser calls this handler; only this handler calls the
 * Python API. Requires the team passcode cookie (see /api/passcode).
 */
export async function POST(request: Request, context: { params: Promise<{ eventId: string }> }) {
  if (!sameOrigin(request)) return jsonError(403, "FORBIDDEN", "Cross-site request refused.");

  const cookie = (await cookies()).get(RUN_COOKIE)?.value;
  if (!runCookieValid(cookie)) {
    return jsonError(401, "UNAUTHORIZED", "Enter the team passcode to start a run.");
  }

  const { eventId } = await context.params;
  if (!ID_PATTERN.test(eventId)) return jsonError(400, "INVALID_INPUT", "Unknown event.");

  const parsed = startJobSchema.safeParse(await readSmallJson(request));
  if (!parsed.success) {
    const fields = [...new Set(parsed.error.issues.map((issue) => String(issue.path[0] ?? "body")))];
    return jsonError(400, "INVALID_INPUT", `Check these values: ${fields.join(", ")}.`);
  }

  const result = await backendRequest(
    `/events/${encodeURIComponent(eventId)}/jobs`,
    jobCreatedSchema,
    { method: "POST", body: parsed.data, clientIp: clientIpFrom(request.headers) },
  );
  if (!result.ok) return failureResponse(result);
  if (!ID_PATTERN.test(result.data.job_id)) {
    return jsonError(502, "BAD_RESPONSE", "The backend sent an unexpected response.");
  }
  return json(result.data, 202);
}
