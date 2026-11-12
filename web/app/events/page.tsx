import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { Empty, Loading, OfflineBanner, Problem } from "@/components/States";
import { loadEvents } from "@/lib/data";
import { fmt, fmtTime } from "@/lib/format";
import { ID_PATTERN } from "@/lib/limits";

export const metadata: Metadata = { title: "Events" };

export default function EventsPage() {
  return (
    <>
      <h1>Events</h1>
      <p className="lede">
        The benchmark earthquakes the backend can plan for. Pick one to open its candidate sites.
      </p>
      <Suspense fallback={<Loading label="Loading earthquakes" />}>
        <EventsContent />
      </Suspense>
    </>
  );
}

async function EventsContent() {
  const events = await loadEvents();
  const list = events.state === "live" || events.state === "snapshot" ? events.data.events : null;
  return (
    <>
      <OfflineBanner results={[events]} />
      <Problem result={events} what="the list of earthquakes" />
      {list && list.length === 0 ? <Empty>The backend lists no earthquakes yet.</Empty> : null}
      {list && list.length > 0 ? (
        <div className="table-wrap">
          <table>
            <caption>Earthquakes ({list.length})</caption>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">ID</th>
                <th scope="col" className="num">
                  Magnitude
                </th>
                <th scope="col">Time</th>
                <th scope="col">Region</th>
                <th scope="col">Data</th>
                <th scope="col">Open</th>
              </tr>
            </thead>
            <tbody>
              {list.map((event) => (
                <tr key={event.id}>
                  <th scope="row">{event.name}</th>
                  <td>{event.id}</td>
                  <td className="num">{fmt(event.magnitude, 1)}</td>
                  <td>{fmtTime(event.time_utc)}</td>
                  <td>{event.region}</td>
                  <td>
                    {event.available ? (
                      <span className="tag tag-ok">available</span>
                    ) : (
                      <span className="tag tag-warn">not available</span>
                    )}
                  </td>
                  <td>
                    {event.available && ID_PATTERN.test(event.id) ? (
                      <Link href={`/candidates?event=${event.id}`}>
                        Candidate sites<span className="muted"> for {event.name}</span>
                      </Link>
                    ) : (
                      <span className="muted">n/a</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}
