import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { QuakeGlobe } from "@/components/QuakeGlobe";
import { Empty, Loading, OfflineBanner, Problem } from "@/components/States";
import { loadEvents } from "@/lib/data";
import { fmt, fmtTime } from "@/lib/format";
import { ID_PATTERN } from "@/lib/limits";
import { Coord } from "@/components/Coord";
import { CellBar } from "@/components/CellBar";

export const metadata: Metadata = { title: "Events" };

export default function EventsPage() {
  return (
    <>
      <h1>Events</h1>
      <p className="lede">
        Each earthquake here comes with its real aftershocks and ten places a sensor could go. The
        globe shows where they struck; pick one in the list to follow it through the steps.
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
  const mags = list ? list.map((e) => e.magnitude) : [];
  const magMin = Math.min(...mags) - 0.5;
  const magMax = Math.max(...mags);
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
                <th scope="col">Earthquake</th>
                <th scope="col" className="num">
                  Magnitude
                </th>
                <th scope="col">Date</th>
                {showKind ? <th scope="col">Kind</th> : null}
                {showLocation ? <th scope="col">Location</th> : null}
                <th scope="col">
                  <span className="visually-hidden">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.map((event) => (
                <tr key={event.id} title={event.usgs_id ? `USGS event ${event.usgs_id}` : event.id}>
                  <th scope="row">{event.name}</th>
                  <td className="num">
                    <CellBar value={event.magnitude} min={magMin} max={magMax}>
                      {fmt(event.magnitude, 1)}
                    </CellBar>
                  </td>
                  <td className="nowrap">{fmtTime(event.time_utc).slice(0, 10)}</td>
                  {showKind ? (
                    <td>
                      {event.kind === "live" ? (
                        <span className="tag tag-ok">live</span>
                      ) : event.kind === "benchmark" ? (
                        <span className="tag">benchmark</span>
                      ) : (
                        "n/a"
                      )}
                    </td>
                  ) : null}
                  {showLocation ? (
                    <td>
                      <Coord lat={event.lat} lon={event.lon} />
                    </td>
                  ) : null}
                  <td className="nowrap">
                    {event.available && ID_PATTERN.test(event.id) ? (
                      <Link href={`/candidates?event=${event.id}`} className="row-open">
                        Open sites<span className="visually-hidden"> for {event.name}</span>
                        <span aria-hidden="true"> →</span>
                      </Link>
                    ) : (
                      <span className="tag tag-warn">no data yet</span>
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
