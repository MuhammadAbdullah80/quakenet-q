import type { Metadata } from "next";
import { Suspense } from "react";
import { BarChart } from "@/components/BarChart";
import { EventBar } from "@/components/EventBar";
import { NoEvent } from "@/components/NoEvent";
import { Empty, Loading, OfflineBanner, Problem } from "@/components/States";
import { loadBaselines, loadLatestJob, parseLam, resolveEvent } from "@/lib/data";
import { fmt, fmtSites, fmtTime, sameSites } from "@/lib/format";
import type { PageProps } from "@/lib/page-types";

export const metadata: Metadata = { title: "Self-check" };

export default function SelfCheckPage({ searchParams }: PageProps) {
  return (
    <>
      <h1>Self-check</h1>
      <p className="lede">
        The quantum choice next to the exact optimum and the classical methods. Rank 1 is the best
        possible network. Location error is the mean error, in km, when locating later aftershocks.
      </p>
      <Suspense fallback={<Loading label="Loading the comparison" />}>
        <SelfCheckContent searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function SelfCheckContent({ searchParams }: PageProps) {
  const params = await searchParams;
  const resolved = await resolveEvent(params);
  if (!resolved.event) return <NoEvent resolved={resolved} />;
  const { events, event } = resolved;
  const { latest } = await loadLatestJob(event.id);
  const job = latest.state === "live" || latest.state === "snapshot" ? latest.data : null;
  const result = job?.result ?? null;
  // Compare like with like: by default use the risk weight of the latest quantum run.
  const lam = params.lam === undefined && result ? result.lam : parseLam(params.lam);
  const baselines = await loadBaselines(event.id, lam);
  const data = baselines.state === "live" || baselines.state === "snapshot" ? baselines.data : null;

  return (
    <>
      <OfflineBanner results={[events, baselines, latest]} />
      <EventBar
        events={events.state === "live" || events.state === "snapshot" ? events.data.events : []}
        current={event}
        action="/self-check"
      />

      <div className="columns">
        <section aria-labelledby="baselines-heading">
          <h2 id="baselines-heading">Classical methods</h2>
          <Problem result={baselines} what="the baselines" />
          {data ? (
            <details className="more">
              <summary>See the numbers: every method</summary>
              <div className="table-wrap">
                <table>
                  <caption>Baselines at risk weight (lam) {data.lam}</caption>
                  <thead>
                    <tr>
                      <th scope="col">Method</th>
                      <th scope="col">Sites</th>
                      <th scope="col" className="num">
                        Rank
                      </th>
                      <th scope="col" className="num">
                        Risk
                      </th>
                      <th scope="col" className="num">
                        Blur (km)
                      </th>
                      <th scope="col" className="num">
                        Location error (km)
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.methods.map((method) => {
                      const same = result ? sameSites(method.sites, result.final.sites) : false;
                      return (
                        <tr key={method.name} className={same ? "is-highlight" : undefined}>
                          <th scope="row">
                            {method.name}{" "}
                            {same ? <span className="tag tag-ok">same as quantum</span> : null}
                          </th>
                          <td className="nowrap">{fmtSites(method.sites)}</td>
                          <td className="num">{method.rank}</td>
                          <td className="num">{fmt(method.risk)}</td>
                          <td className="num">{fmt(method.blur_km)}</td>
                          <td className="num">{fmt(method.loc_error_mean_km)}</td>
                        </tr>
                      );
                    })}
                    <tr>
                      <th scope="row">No new sensors</th>
                      <td>none</td>
                      <td className="num">n/a</td>
                      <td className="num">n/a</td>
                      <td className="num">{fmt(data.no_new_sensors.blur_km)}</td>
                      <td className="num">{fmt(data.no_new_sensors.loc_error_mean_km)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </details>
          ) : null}
          {data ? (
            <BarChart
              title="Location error by method"
              explain={{
                what: "How far off each method's sensor layout would be, on average, when locating aftershocks it never saw.",
                read: [
                  "Shorter bars are better: less error in kilometres.",
                  "No new sensors is the starting point: only the permanent stations.",
                  "Lime bars are methods that chose the same sites as the quantum circuit.",
                ],
              }}
              note="Mean error locating the later aftershocks, in km. Lower is better."
              unit="km"
              items={[
                { label: "No new sensors", value: data.no_new_sensors.loc_error_mean_km },
                ...data.methods.map((method) => ({
                  label: method.name,
                  value: method.loc_error_mean_km,
                  highlight: result ? sameSites(method.sites, result.final.sites) : false,
                })),
              ]}
              highlightLabel={result ? "Same sites as the quantum pick" : undefined}
            />
          ) : null}
        </section>

        <section aria-labelledby="quantum-heading">
          <h2 id="quantum-heading">Latest quantum result</h2>
          <Problem result={latest} what="the latest quantum result" />
          {result && job ? (
            <>
              <div className={`notice ${result.quantum_agreed ? "notice-ok" : "notice-warn"}`}>
                <p className="notice-title">
                  {result.quantum_agreed
                    ? "The quantum choice matched the exact optimum."
                    : "The quantum choice did not match the exact optimum."}
                </p>
              </div>
              <dl className="facts">
                <div>
                  <dt>Quantum final pick</dt>
                  <dd>sites {fmtSites(result.final.sites)}</dd>
                </div>
                <div>
                  <dt>Rank of the pick</dt>
                  <dd>{result.final.rank}</dd>
                </div>
                <div>
                  <dt>Objective of the pick</dt>
                  <dd>{fmt(result.final.objective, 1)}</dd>
                </div>
                <div>
                  <dt>Exact optimum</dt>
                  <dd>sites {fmtSites(result.exact_optimum)}</dd>
                </div>
                <div>
                  <dt>Run settings</dt>
                  <dd>
                    reps {result.reps}, seed {result.seed}, shots {result.shots}, lam {result.lam}
                  </dd>
                </div>
                <div>
                  <dt>Job</dt>
                  <dd>
                    {job.job_id}, finished {fmtTime(job.finished_utc)}
                  </dd>
                </div>
              </dl>
              {data && data.lam !== result.lam ? (
                <p className="notice notice-warn">
                  The baselines use risk weight {data.lam} but the quantum run used {result.lam}, so
                  the two sides are not directly comparable.
                </p>
              ) : null}
            </>
          ) : latest.state === "live" || latest.state === "snapshot" ? (
            <Empty>
              No finished quantum run for this earthquake yet. Start one on the Quantum page.
            </Empty>
          ) : null}
        </section>
      </div>
    </>
  );
}
