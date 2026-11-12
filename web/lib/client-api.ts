// Helpers for browser code that calls this console's own /api routes.
// The browser never calls the Python API.

type ApiError = { error?: { code?: string; message?: string } };

export async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/** Plain-language text for an error answer of one of this console's routes. */
export function errorMessage(status: number, body: unknown, retryAfter: string | null): string {
  const error = (body as ApiError | null)?.error;
  switch (error?.code) {
    case "JOB_RUNNING":
      return "A job is already in progress. Wait for it to finish, then try again.";
    case "RATE_LIMITED":
      return `Too many requests. ${retryAfter ? `Try again in ${retryAfter} s.` : "Try again in a minute."}`;
    case "BACKEND_OFFLINE":
      return "The backend is not reachable right now.";
    case "UNAUTHORIZED":
      return "Enter the team passcode first.";
    case "NOT_BUILT":
      return "The backend does not have this feature yet (501 NOT_BUILT).";
    default:
      return error?.message || `The request failed (status ${status}).`;
  }
}

export type Message = { tone: "error" | "info"; text: string };
