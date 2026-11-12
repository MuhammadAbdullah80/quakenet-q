import type { ReactNode } from "react";
import type { Loaded } from "@/lib/data";

const REASONS: Record<string, string> = {
  not_configured: "No backend is configured for this deployment.",
  timeout: "The backend did not answer within 10 seconds.",
  network: "The backend could not be reached.",
  gateway: "The tunnel answered, but the backend behind it is not running.",
};

export function Loading({ label }: { label: string }) {
  return (
    <div className="skeleton" role="status" aria-live="polite">
      <span className="visually-hidden">{label}</span>
      <span className="sk sk-bar" aria-hidden="true" />
      <span className="sk-row" aria-hidden="true">
        <span className="sk sk-tile" />
        <span className="sk sk-tile" />
        <span className="sk sk-tile" />
      </span>
      <span className="sk sk-block" aria-hidden="true" />
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="notice notice-info">
      <p>{children}</p>
    </div>
  );
}

/**
 * Shown once per page when any of its data came from a snapshot, or could not
 * be loaded because the backend is unreachable.
 */
export function OfflineBanner({ results }: { results: Loaded<unknown>[] }) {
  const down = results.find((r) => r.state === "snapshot" || r.state === "offline");
  if (!down || (down.state !== "snapshot" && down.state !== "offline")) return null;
  const mock = results.some((r) => r.state === "snapshot" && r.mock);
  return (
    <div className="notice notice-offline" role="status" aria-live="polite">
      <p className="notice-title">Offline: showing saved results</p>
      <p>
        {REASONS[down.reason]} Pages show snapshots saved with the site, and starting new runs is
        disabled.
      </p>
      {mock ? (
        <p>
          <strong>These saved results are placeholders (mock data), not real results.</strong> They
          only show what each page looks like until real snapshots are captured from the backend.
        </p>
      ) : null}
    </div>
  );
}

export function NotBuilt({ what }: { what: string }) {
  return (
    <div className="notice notice-info">
      <p className="notice-title">Not built yet</p>
      <p>
        {what} is designed but not built: the backend answered <code>501 NOT_BUILT</code>. This page
        will fill in when the backend module exists.
      </p>
    </div>
  );
}

/** Renders the non-data states of a load. Returns null when there is data. */
export function Problem({ result, what }: { result: Loaded<unknown>; what: string }) {
  switch (result.state) {
    case "live":
    case "snapshot":
      return null;
    case "offline":
      return (
        <div className="notice notice-warn">
          <p className="notice-title">No saved copy of {what}</p>
          <p>The backend is unreachable and there is no snapshot for this part of the page.</p>
        </div>
      );
    case "not_built":
      return <NotBuilt what={what} />;
    case "error":
      return (
        <div className="notice notice-error" role="alert" aria-live="assertive">
          <p className="notice-title">Could not load {what}</p>
          <p>
            {errorText(result.code)}{" "}
            <span className="muted">
              ({result.status} {result.code})
            </span>
          </p>
          {result.retryAfterSeconds ? <p>Try again in {result.retryAfterSeconds} s.</p> : null}
        </div>
      );
  }
}

function errorText(code: string): string {
  switch (code) {
    case "UNAUTHORIZED":
      return "The backend rejected this console's shared secret. Check BACKEND_TOKEN on both sides.";
    case "NOT_FOUND":
      return "The backend does not know this item.";
    case "INVALID_INPUT":
      return "The backend rejected the request values.";
    case "RATE_LIMITED":
      return "Too many requests. The backend is rate-limiting this address.";
    case "BAD_RESPONSE":
      return "The backend answered in a form this console does not understand (contract mismatch).";
    default:
      return "The backend reported an internal error.";
  }
}
