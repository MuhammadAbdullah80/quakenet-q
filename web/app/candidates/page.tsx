import type { Metadata } from "next";
import { Suspense } from "react";
import { EventBar } from "@/components/EventBar";
import { NoEvent } from "@/components/NoEvent";
import { SiteMap } from "@/components/SiteMap";
import { Empty, Loading, OfflineBanner, Problem } from "@/components/States";
import { loadInstance, resolveEvent } from "@/lib/data";
import { fmt } from "@/lib/format";
import type { PageProps } from "@/lib/page-types";

export const metadata: Metadata = { title: "Candidates" };

export default function CandidatesPage({ searchParams }: PageProps) {
  return (
    <>
      <h1>Candidates</h1>
      <p className="lede">
        The candidate sites for portable seismometers, with the aftershocks and permanent stations
        around them. Coordinates are kilometres in a local grid (x east, y north). Risk is the
        access risk of a site.
      </p>
      <Suspense fallback={<Loading label="Loading candidate sites" />}>
        <CandidatesContent searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function CandidatesContent({ searchParams }: PageProps) {
  const resolved = await resolveEvent(await searchParams);
  if (!resolved.event) return <NoEvent resolved={resolved} />;
  const { events, event } = resolved;
  const instance = await loadInstance(event.id);
  const data = instance.state === "live" || instance.state === "snapshot" ? instance.data : null;

  return (
    <>
      <OfflineBanner results={[events, instance]} />
      <EventBar
        events={events.state === "live" || events.state === "snapshot" ? events.data.events : []}
        current={event}
        action="/candidates"
      />
      <Problem result={instance} what="the candidate sites" />
      {data ? (
        <>
          <dl className="facts">
            <div>
              <dt>Candidate sites (n)</dt>
              <dd>{data.n}</dd>
            </div>
            <div>
              <dt>Sensors to place (k)</dt>
              <dd>{data.k}</dd>
            </div>
            <div>
              <dt>Decision time after the mainshock</dt>
              <dd>{fmt(data.decision_hours, 0)} hours</dd>
            </div>
            <div>
              <dt>Aftershocks used to plan</dt>
              <dd>{data.design_events.length}</dd>
            </div>
            <div>
              <dt>Later aftershocks (held out)</dt>
              <dd>{data.valid_events.length}</dd>
            </div>
            <div>
              <dt>Mainshock</dt>
              <dd>
                x {fmt(data.mainshock.x, 1)} km, y {fmt(data.mainshock.y, 1)} km, depth{" "}
                {fmt(data.mainshock.depth, 1)} km
              </dd>
            </div>
          </dl>

          <div className="columns">
            <SiteMap instance={data} title={`Candidate sites for ${event.name}`} />
            <div>
              {data.candidates.length === 0 ? (
                <Empty>This earthquake has no candidate sites.</Empty>
              ) : (
                <div className="table-wrap">
                  <table>
                    <caption>Candidate sites</caption>
                    <thead>
                      <tr>
                        <th scope="col" className="num">
                          Site
                        </th>
                        <th scope="col" className="num">
                          x (km)
                        </th>
                        <th scope="col" className="num">
                          y (km)
                        </th>
                        <th scope="col" className="num">
                          Risk
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.candidates.map((c) => (
                        <tr key={c.id}>
                          <th scope="row" className="num">
                            {c.id}
                          </th>
                          <td className="num">{fmt(c.x, 1)}</td>
                          <td className="num">{fmt(c.y, 1)}</td>
                          <td className="num">{fmt(c.risk)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {data.stations.length > 0 ? (
                <div className="table-wrap">
                  <table>
                    <caption>Permanent stations</caption>
                    <thead>
                      <tr>
                        <th scope="col">Name</th>
                        <th scope="col" className="num">
                          x (km)
                        </th>
                        <th scope="col" className="num">
                          y (km)
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.stations.map((s) => (
                        <tr key={s.name}>
                          <th scope="row">{s.name}</th>
                          <td className="num">{fmt(s.x, 1)}</td>
                          <td className="num">{fmt(s.y, 1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </>
  );
}
