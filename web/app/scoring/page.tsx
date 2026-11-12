import type { Metadata } from "next";
import { Suspense } from "react";
import { EventBar } from "@/components/EventBar";
import { LamForm } from "@/components/LamForm";
import { NoEvent } from "@/components/NoEvent";
import { Empty, Loading, OfflineBanner, Problem } from "@/components/States";
import { loadScoring, parseLam, resolveEvent } from "@/lib/data";
import { fmt, fmtSites, sameSites } from "@/lib/format";
import type { PageProps } from "@/lib/page-types";
import { TableFold } from "@/components/TableFold";

export const metadata: Metadata = { title: "Scoring" };

export default function ScoringPage({ searchParams }: PageProps) {
  return (
    <>
      <h1>Scoring</h1>
      <p className="lede">
        Each choice of 4 sites gets one score: how sharply it would locate aftershocks, minus a
        penalty for risky sites. Higher is better. Below are the best choices.
      </p>
      <Suspense fallback={<Loading label="Loading scores" />}>
        <ScoringContent searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function ScoringContent({ searchParams }: PageProps) {
  const params = await searchParams;
  const resolved = await resolveEvent(params);
  if (!resolved.event) return <NoEvent resolved={resolved} />;
  const { events, event } = resolved;
  const requestedLam = parseLam(params.lam);
  const scoring = await loadScoring(event.id, requestedLam);
  const data = scoring.state === "live" || scoring.state === "snapshot" ? scoring.data : null;
  const offline = scoring.state === "snapshot" || scoring.state === "offline";

  return (
    <>
      <OfflineBanner results={[events, scoring]} />
      <EventBar
        events={events.state === "live" || events.state === "snapshot" ? events.data.events : []}
        current={event}
        action="/scoring"
      />
      <LamForm
        action="/scoring"
        eventId={event.id}
        lam={data?.lam ?? requestedLam}
        disabled={offline}
      />
      <Problem result={scoring} what="the scores" />
      {data ? (
        <>
          <dl className="facts">
            <div>
              <dt>Risk weight (lam)</dt>
              <dd>{data.lam}</dd>
            </div>
            <div>
              <dt>Possible networks</dt>
              <dd>{data.feasible_networks}</dd>
            </div>
            <div>
              <dt>Best network (exact optimum)</dt>
              <dd>sites {fmtSites(data.exact_optimum)}</dd>
            </div>
          </dl>

          {data.fidelity.length === 0 ? (
            <Empty>No fidelity rows were returned.</Empty>
          ) : (
            <details className="more">
              <summary>How close the simplified scores are to the exact one</summary>
              <div className="table-wrap">
                <table>
                  <caption>
                    Order is the largest group of sites whose joint effect is kept. Rank agreement
                    is the Spearman correlation with the exact objective (1 is perfect).
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col" className="num">
                        Order
                      </th>
                      <th scope="col" className="num">
                        Terms
                      </th>
                      <th scope="col" className="num">
                        Rank agreement (Spearman)
                      </th>
                      <th scope="col" className="num">
                        Largest error
                      </th>
                      <th scope="col" className="num">
                        True rank of its best network
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.fidelity.map((row) => (
                      <tr key={row.order}>
                        <th scope="row" className="num">
                          {row.order}
                        </th>
                        <td className="num">{row.terms}</td>
                        <td className="num">{fmt(row.spearman, 3)}</td>
                        <td className="num">{fmt(row.max_abs_error, 1)}</td>
                        <td className="num">{row.rank_of_its_optimum}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}

          <h2>Top networks</h2>
          {data.top_networks.length === 0 ? (
            <Empty>No networks were returned.</Empty>
          ) : (
            <TableFold total={data.top_networks.length} limit={5} noun="networks">
              <div className="table-wrap">
                <table>
                  <caption>The best {data.top_networks.length} networks by exact objective</caption>
                  <thead>
                    <tr>
                      <th scope="col" className="num">
                        Rank
                      </th>
                      <th scope="col">Sites</th>
                      <th scope="col" className="num">
                        Objective
                      </th>
                      <th scope="col" className="num">
                        Risk
                      </th>
                      <th scope="col" className="num">
                        Blur (km)
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_networks.map((row) => (
                      <tr
                        key={row.sites.join("-")}
                        className={
                          sameSites(row.sites, data.exact_optimum) ? "is-highlight" : undefined
                        }
                      >
                        <th scope="row" className="num">
                          {row.rank}
                        </th>
                        <td className="nowrap">{fmtSites(row.sites)}</td>
                        <td className="num">{fmt(row.objective, 1)}</td>
                        <td className="num">{fmt(row.risk)}</td>
                        <td className="num">{fmt(row.blur_km)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </TableFold>
          )}
          <p className="small muted">
            Blur is the predicted uncertainty, in km, when locating later aftershocks with the
            network. Lower is better.
          </p>
        </>
      ) : null}
    </>
  );
}
