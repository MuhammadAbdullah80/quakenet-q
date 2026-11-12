import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { EventBar } from "@/components/EventBar";
import { NoEvent } from "@/components/NoEvent";
import { SiteMap, type MapData } from "@/components/SiteMap";
import { Empty, Loading, OfflineBanner, Problem } from "@/components/States";
import {
  isNotFound,
  loadInstance,
  loadPlan,
  loadSequence,
  resolveEvent,
  type Loaded,
} from "@/lib/data";
import { fmt, fmtPercent, fmtTime } from "@/lib/format";
import type { PageProps } from "@/lib/page-types";
import type { Plan } from "@/lib/schemas";
import { sequenceMapData, stageLabel } from "@/lib/sequence";
import { Coord } from "@/components/Coord";

export const metadata: Metadata = { title: "Plan" };

export default function PlanPage({ searchParams }: PageProps) {
  return (
    <>
      <h1>Plan</h1>
      <p className="lede">
        The agent&apos;s latest plan for an earthquake: where each sensor goes and why, which
        sensors move, and how far the plan can be trusted.
      </p>
      <Suspense fallback={<Loading label="Loading the plan" />}>
        <PlanContent searchParams={searchParams} />
      </Suspense>
    </>
  );
}

const CONFIDENCE: Record<string, string> = {
  high: "high: past plans predicted their score well",
  medium: "medium: past plans were roughly right",
  low: "low: past plans were often off",
  unrated: "unrated: not enough past plans to judge",
};

async function PlanContent({ searchParams }: PageProps) {
  const resolved = await resolveEvent(await searchParams);
  if (!resolved.event) return <NoEvent resolved={resolved} />;
  const { events, event } = resolved;
  const plan = await loadPlan(event.id);
  const data = plan.state === "live" || plan.state === "snapshot" ? plan.data : null;

  // The map uses the sequence's own candidate sites when it can (the agent may
  // use other sites than the benchmark instance), else the instance.
  let map: MapData | null = null;
  let mapNote: string | null = null;
  let designLabel: string | undefined;
  const extra: Loaded<unknown>[] = [];
  if (data) {
    const sequence = await loadSequence(event.id);
    if (sequence.state === "live" || sequence.state === "snapshot") {
      extra.push(sequence);
      map = sequenceMapData(sequence.data, data.hour ?? Number.POSITIVE_INFINITY);
      mapNote = "Dots are the real aftershocks recorded up to the hour of this plan.";
      designLabel = "Aftershock so far";
    } else {
      const instance = await loadInstance(event.id);
      if (instance.state === "live" || instance.state === "snapshot") {
        extra.push(instance);
        map = instance.data;
        mapNote =
          "The sequence could not be loaded, so the map shows the benchmark candidate sites. Site numbers may not match if the agent used other candidates.";
      }
    }
  }

  return (
    <>
      <OfflineBanner results={[events, plan, ...extra]} />
      <EventBar
        events={events.state === "live" || events.state === "snapshot" ? events.data.events : []}
        current={event}
        action="/plan"
      />
      {isNotFound(plan) ? (
        <Empty>
          The agent has not planned for this earthquake yet. Start a replay on the{" "}
          <Link href={`/monitor?event=${event.id}`}>Monitor page</Link>.
        </Empty>
      ) : (
        <Problem result={plan} what="the plan" />
      )}
      {data ? (
        <PlanView
          plan={data}
          map={map}
          mapNote={mapNote}
          designLabel={designLabel}
          title={event.name}
        />
      ) : null}
    </>
  );
}

function PlanView({
  plan,
  map,
  mapNote,
  designLabel,
  title,
}: {
  plan: Plan;
  map: MapData | null;
  mapNote: string | null;
  designLabel: string | undefined;
  title: string;
}) {
  const siteIds = plan.sites.map((s) => s.id);
  const moves = plan.moves ?? [];
  return (
    <>
      {typeof plan.quantum_agreed === "boolean" ? (
        <div className={`notice ${plan.quantum_agreed ? "notice-ok" : "notice-warn"}`}>
          <p className="notice-title">
            {plan.quantum_agreed
              ? "The quantum choice matched the exact optimum."
              : "The quantum choice did not match the exact optimum."}
          </p>
          <p>
            Exact rank of the chosen network: {plan.exact_rank ?? "n/a"} (1 is the best possible).
          </p>
        </div>
      ) : null}
      {plan.feasibility_checked === false ? (
        <p className="notice notice-warn">
          The road check was unavailable for this plan, so the sites were not checked for access.
        </p>
      ) : null}

      <dl className="kpis">
        <div>
          <dt>Confidence</dt>
          <dd>{plan.confidence ? (CONFIDENCE[plan.confidence] ?? plan.confidence) : "n/a"}</dd>
        </div>
        <div>
          <dt>Expected location error, this plan</dt>
          <dd>
            {typeof plan.expected_error_km === "number"
              ? `${fmt(plan.expected_error_km)} km`
              : "n/a"}
          </dd>
        </div>
        <div>
          <dt>Expected location error, expert rule</dt>
          <dd>
            {typeof plan.expert_rule_error_km === "number"
              ? `${fmt(plan.expert_rule_error_km)} km`
              : "n/a"}
          </dd>
        </div>
      </dl>
      <details className="more">
        <summary>More detail</summary>
        <dl className="facts">
          <div>
            <dt>Stage</dt>
            <dd>{stageLabel(plan.stage)}</dd>
          </div>
          <div>
            <dt>Hour after the mainshock</dt>
            <dd>{typeof plan.hour === "number" ? fmt(plan.hour, 0) : "n/a"}</dd>
          </div>
          <div>
            <dt>Made</dt>
            <dd>{fmtTime(plan.created_utc)}</dd>
          </div>
          <div>
            <dt>Objective (score)</dt>
            <dd>{typeof plan.objective === "number" ? fmt(plan.objective, 1) : "n/a"}</dd>
          </div>
          <div>
            <dt>Chance one measurement gives the best network</dt>
            <dd>
              {typeof plan.p_opt_per_shot === "number" ? fmtPercent(plan.p_opt_per_shot, 1) : "n/a"}
            </dd>
          </div>
        </dl>
      </details>

      <h2>Moves</h2>
      {moves.length === 0 ? (
        <p>No sensor moves in this plan.</p>
      ) : (
        <ul>
          {moves.map((m) => (
            <li key={`${m.from}-${m.to}`}>
              Move the sensor at site {m.from} to site {m.to}.
            </li>
          ))}
        </ul>
      )}

      <h2>Chosen sites ({plan.sites.length})</h2>
      {plan.sites.length === 0 ? (
        <Empty>The plan lists no sites.</Empty>
      ) : (
        <ul className="cards">
          {plan.sites.map((site) => (
            <li className="panel" key={site.id}>
              <h3>Site {site.id}</h3>
              <p>{site.reason ?? "No reason given."}</p>
              <dl className="pairs">
                <dt>Access risk</dt>
                <dd>{typeof site.risk === "number" ? fmt(site.risk) : "n/a"}</dd>
                <dt>Gain if it were the only new site</dt>
                <dd>{typeof site.single_gain === "number" ? fmt(site.single_gain, 1) : "n/a"}</dd>
                <dt>Location</dt>
                <dd>
                  <Coord lat={site.lat} lon={site.lon} />
                </dd>
                <dt>Local grid</dt>
                <dd>
                  x {fmt(site.x, 1)} km, y {fmt(site.y, 1)} km
                </dd>
                <dt>Backup spots</dt>
                <dd>
                  {site.backups && site.backups.length > 0
                    ? site.backups.map((b, i) => <Coord key={i} lat={b.lat} lon={b.lon} />)
                    : "none"}
                </dd>
              </dl>
            </li>
          ))}
        </ul>
      )}

      {map ? (
        <section aria-labelledby="plan-map-heading">
          <h2 id="plan-map-heading">Map</h2>
          {mapNote ? <p className="small muted">{mapNote}</p> : null}
          <SiteMap
            instance={map}
            title={`Planned sites for ${title}`}
            chosen={siteIds}
            chosenLabel="Planned site"
            designLabel={designLabel}
          />
        </section>
      ) : null}
    </>
  );
}
