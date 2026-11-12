import type { FeedQuake } from "@/lib/schemas";
import { fmt, fmtTime } from "@/lib/format";
import { Expand } from "@/components/Expand";

// The feed at a glance, before the full list: how many earthquakes in each state, how big they
// were, and the largest one. Every number is counted from the same list the table shows.

const STATUS: { key: string; label: string; hint: string }[] = [
  { key: "planned", label: "Planned", hint: "the agent made a plan" },
  { key: "pending", label: "Pending", hint: "big enough, not handled yet" },
  { key: "skipped", label: "Skipped", hint: "big enough, but unusable" },
  { key: "below_threshold", label: "Below trigger", hint: "smaller than the trigger" },
];

const BINS = [
  { lo: 2.5, hi: 3, label: "2.5" },
  { lo: 3, hi: 4, label: "3" },
  { lo: 4, hi: 5, label: "4" },
  { lo: 5, hi: 6, label: "5" },
  { lo: 6, hi: 99, label: "6+" },
];

export function FeedSummary({ quakes, threshold }: { quakes: FeedQuake[]; threshold: number }) {
  const byStatus = new Map<string, number>();
  for (const q of quakes) byStatus.set(q.status, (byStatus.get(q.status) ?? 0) + 1);
  const bins = BINS.map((b) => ({
    ...b,
    count: quakes.filter((q) => q.magnitude >= b.lo && q.magnitude < b.hi).length,
  }));
  const most = Math.max(1, ...bins.map((b) => b.count));
  const largest = quakes.reduce<FeedQuake | null>(
    (a, q) => (a === null || q.magnitude > a.magnitude ? q : a),
    null,
  );

  return (
    <div className="feed-summary">
      <ul className="status-tiles" aria-label="Earthquakes by status">
        {STATUS.map((s) => (
          <li key={s.key} className={`status-tile is-${s.key}`}>
            <span className="status-count">{byStatus.get(s.key) ?? 0}</span>
            <span className="status-label">{s.label}</span>
            <span className="status-hint">{s.hint}</span>
          </li>
        ))}
      </ul>

      <Expand
        title="Earthquakes in the past 24 hours, by magnitude"
        explain={{
          what: "How many of the past day's earthquakes fell in each magnitude band.",
          read: [
            "Each bar runs from its label up to the next label.",
            "Striped bars are at or above the trigger magnitude, big enough to start the agent.",
            "Most earthquakes are small; big ones are rare.",
          ],
        }}
      >
        <figure className="mag-hist">
          <figcaption>By magnitude (each bar runs from its label to the next)</figcaption>
          <ol>
            {bins.map((b, i) => (
              <li key={b.label} className={b.lo >= threshold ? "is-trigger" : undefined}>
                <span
                  className="mag-bar"
                  style={{ "--h": b.count / most, "--i": i } as React.CSSProperties}
                >
                  <span className="mag-n">{b.count}</span>
                </span>
                <span className="mag-label">M {b.label}</span>
              </li>
            ))}
          </ol>
          <p className="mag-note">Trigger magnitude: {fmt(threshold, 1)}</p>
        </figure>
      </Expand>

      {largest ? (
        <div className="feed-largest">
          <span className="feed-largest-kicker">Largest in the past 24 hours</span>
          <span className="feed-largest-mag">M {fmt(largest.magnitude, 1)}</span>
          <span className="feed-largest-place">{largest.place ?? largest.usgs_id}</span>
          <span className="feed-largest-time">{fmtTime(largest.time_utc)}</span>
        </div>
      ) : null}
    </div>
  );
}
