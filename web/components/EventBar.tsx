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
    <div className="panel">
      <p>
        <strong>Earthquake:</strong> {current.name}, magnitude {fmt(current.magnitude, 1)},{" "}
        {fmtTime(current.time_utc)} <span className="muted">({current.id})</span>
      </p>
      {selectable.length > 1 ? (
        <form action={action} method="get">
          <div className="fields">
            <div className="field">
              <label htmlFor="event-picker">Show another earthquake</label>
              <select id="event-picker" name="event" defaultValue={current.id}>
                {selectable.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name} (M{fmt(e.magnitude, 1)})
                  </option>
                ))}
              </select>
            </div>
            <button type="submit" className="secondary">
              Show
            </button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
