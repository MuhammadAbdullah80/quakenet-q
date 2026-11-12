import { OfflineBanner, Problem } from "@/components/States";
import type { Loaded } from "@/lib/data";

/**
 * For modules whose response shape is not in the contract yet: shows the
 * "not built yet" state on 501, otherwise the raw JSON as plain text.
 */
export function ModuleProbe({
  result,
  what,
  extra = [],
}: {
  result: Loaded<unknown>;
  what: string;
  /** Other loads on the page that may have come from a snapshot. */
  extra?: Loaded<unknown>[];
}) {
  return (
    <>
      <OfflineBanner results={[...extra, result]} />
      <Problem result={result} what={what} />
      {result.state === "live" ? (
        <section aria-labelledby="raw-heading">
          <h2 id="raw-heading">Backend response</h2>
          <p className="muted">
            The backend answered. This console has no dedicated view for this module yet, so the
            response is shown as received.
          </p>
          <pre className="raw" tabIndex={0}>
            {JSON.stringify(result.data, null, 2)}
          </pre>
        </section>
      ) : null}
    </>
  );
}
