import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { QuakeGlobe } from "@/components/QuakeGlobe";
import { Empty, Loading, OfflineBanner, Problem } from "@/components/States";
import { loadEvents } from "@/lib/data";
import { fmt, fmtTime } from "@/lib/format";
import { ID_PATTERN } from "@/lib/limits";
import { Coord } from "@/components/Coord";

export const metadata: Metadata = { title: "Events" };

export default function EventsPage() {
  return (
    <>
      <h1>Events</h1>
      <p className="lede">
        The earthquakes the backend can plan for: past benchmark earthquakes and, once the agent has
        started on them, live ones from the USGS feed. Pick one to open its candidate sites.
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
  const showKind = list?.some((e) => e.kind) ?? false;
  const showLocation =
    list?.some((e) => typeof e.lat === "number" && typeof e.lon === "number") ?? false;
  return (
    <>
      <OfflineBanner results={[events]} />
      <Problem result={events} what="the list of earthquakes" />
      {list && list.length === 0 ? <Empty>The backend lists no earthquakes yet.</Empty> : null}
      {list && list.some((e) => typeof e.lat === "number" && typeof e.lon === "number") ? (
        <QuakeGlobe
          label="Where each earthquake struck."
          dotLabel="earthquake the backend can plan for"
          flagLabel={
            list.some((e) => e.kind === "live") ? "live earthquake the agent started on" : undefined
          }
          points={list
            .filter((e) => typeof e.lat === "number" && typeof e.lon === "number")
            .map((e) => ({
              id: e.id,
              lat: e.lat as number,
              lon: e.lon as number,
              mag: e.magnitude,
              title: e.name,
              detail: `M ${fmt(e.magnitude, 1)}, ${fmtTime(e.time_utc)}${e.kind ? `, ${e.kind}` : ""}`,
              flag: e.kind === "live",
            }))}
        />
      ) : null}
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
                {showKind ? <th scope="col">Kind</th> : null}
                {showLocation ? <th scope="col">Location</th> : null}
                <th scope="col">Data</th>
                <th scope="col">Open</th>
              </tr>
            </thead>
            <tbody>
              {list.map((event) => (
                <tr key={event.id}>
                  <th scope="row">{event.name}</th>
                  <td>
                    {event.id}
                    {event.usgs_id ? (
                      <span className="muted small"> (USGS {event.usgs_id})</span>
                    ) : null}
                  </td>
                  <td className="num">{fmt(event.magnitude, 1)}</td>
                  <td>{fmtTime(event.time_utc)}</td>
                  <td>{event.region}</td>
                  {showKind ? (
                    <td>
                      {event.kind === "live"
                        ? "live"
                        : event.kind === "benchmark"
                          ? "benchmark"
                          : "n/a"}
                    </td>
                  ) : null}
                  {showLocation ? (
                    <td>
                      <Coord lat={event.lat} lon={event.lon} />
                    </td>
                  ) : null}
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
