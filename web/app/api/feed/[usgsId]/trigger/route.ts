import { cookies } from "next/headers";
import { failureResponse, json, jsonError } from "@/lib/api-response";
import { backendRequest } from "@/lib/backend";
import { clientIpFrom } from "@/lib/client-ip";
import { RUN_COOKIE, runCookieValid, sameOrigin } from "@/lib/passcode";
import { ID_PATTERN, jobCreatedSchema, USGS_ID_PATTERN } from "@/lib/schemas";

/**
 * Start the agent by hand on a real earthquake from the USGS feed. Needs the
 * team passcode cookie, like starting a run.
 */
export async function POST(request: Request, context: { params: Promise<{ usgsId: string }> }) {
  if (!sameOrigin(request)) return jsonError(403, "FORBIDDEN", "Cross-site request refused.");

  const cookie = (await cookies()).get(RUN_COOKIE)?.value;
  if (!runCookieValid(cookie)) {
    return jsonError(401, "UNAUTHORIZED", "Enter the team passcode to start the agent.");
  }

  const { usgsId } = await context.params;
  if (!USGS_ID_PATTERN.test(usgsId)) return jsonError(400, "INVALID_INPUT", "Unknown earthquake.");

  const result = await backendRequest(
    `/feed/${encodeURIComponent(usgsId)}/trigger`,
    jobCreatedSchema,
    { method: "POST", clientIp: clientIpFrom(request.headers) },
  );
  if (!result.ok) return failureResponse(result);
  if (!ID_PATTERN.test(result.data.job_id)) {
    return jsonError(502, "BAD_RESPONSE", "The backend sent an unexpected response.");
  }
  return json(result.data, 202);
}
