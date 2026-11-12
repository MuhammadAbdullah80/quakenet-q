import { failureResponse, json, jsonError } from "@/lib/api-response";
import { backendRequest } from "@/lib/backend";
import { clientIpFrom } from "@/lib/client-ip";
import { ID_PATTERN, anyJobSchema } from "@/lib/schemas";

/** Job status for polling. Reading results needs no passcode. */
export async function GET(request: Request, context: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await context.params;
  if (!ID_PATTERN.test(jobId)) return jsonError(400, "INVALID_INPUT", "Unknown job.");

  const result = await backendRequest(`/jobs/${encodeURIComponent(jobId)}`, anyJobSchema, {
    clientIp: clientIpFrom(request.headers),
  });
  if (!result.ok) return failureResponse(result);
  return json(result.data);
}
