import { cookies } from "next/headers";
import { failureResponse, json, jsonError, readSmallJson } from "@/lib/api-response";
import { backendRequest } from "@/lib/backend";
import { clientIpFrom } from "@/lib/client-ip";
import { RUN_COOKIE, runCookieValid, sameOrigin } from "@/lib/passcode";
import { settingsSchema } from "@/lib/schemas";
import { settingsUpdateSchema } from "@/lib/settings-fields";

/**
 * Save agent settings. Like starting a run, this needs the team passcode
 * cookie. The body is checked against the documented ranges here; the backend
 * checks it again against its own limits.
 */
export async function PUT(request: Request) {
  if (!sameOrigin(request)) return jsonError(403, "FORBIDDEN", "Cross-site request refused.");

  const cookie = (await cookies()).get(RUN_COOKIE)?.value;
  if (!runCookieValid(cookie)) {
    return jsonError(401, "UNAUTHORIZED", "Enter the team passcode to change settings.");
  }

  const parsed = settingsUpdateSchema().safeParse(await readSmallJson(request));
  if (!parsed.success) {
    const fields = [
      ...new Set(
        parsed.error.issues.flatMap((issue) =>
          issue.code === "unrecognized_keys"
            ? issue.keys.map((key) => `unknown setting "${key.slice(0, 40)}"`)
            : [String(issue.path[0] ?? "body")],
        ),
      ),
    ];
    return jsonError(400, "INVALID_INPUT", `Check these values: ${fields.join(", ")}.`);
  }

  const result = await backendRequest("/settings", settingsSchema, {
    method: "PUT",
    body: parsed.data,
    clientIp: clientIpFrom(request.headers),
  });
  if (!result.ok) return failureResponse(result);
  return json(result.data);
}
