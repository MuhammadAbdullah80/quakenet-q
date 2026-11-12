import type { EventSummary } from "@/lib/schemas";
import { fmt, fmtTime } from "@/lib/format";

/** Shows which earthquake the page is about, with a picker when there are several. */
export function EventBar({
  events,
  current,
  action,
}: {
  events: EventSummary[];
  current: EventSummary;
  /** Path of the page, for the picker's GET form. */
  action: string;
}) {
  const selectable = events.filter((e) => e.available);
  return (
    <div className="event-bar">
      <p className="event-now">
        <span className="event-dot" aria-hidden="true" />
        <span className="event-name">{current.name}</span>
        <span className="event-meta">
          M {fmt(current.magnitude, 1)} · {fmtTime(current.time_utc).slice(0, 10)}
        </span>
      </p>
      {selectable.length > 1 ? (
        <form action={action} method="get" className="event-pick">
          <label htmlFor="event-picker">Earthquake</label>
          <select id="event-picker" name="event" defaultValue={current.id}>
            {selectable.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} (M{fmt(e.magnitude, 1)})
              </option>
            ))}
          </select>
          <button type="submit" className="secondary">
            Show
          </button>
        </form>
      ) : null}
    </div>
  );
}
