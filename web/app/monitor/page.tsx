import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Suspense } from "react";
import { EventBar } from "@/components/EventBar";
import { NoEvent } from "@/components/NoEvent";
import { SequenceStarter } from "@/components/SequenceStarter";
import { SequenceViewer } from "@/components/SequenceViewer";
import { Empty, Loading, OfflineBanner, Problem } from "@/components/States";
import { isNotFound, loadActiveJobId, loadSequence, loadSettings, resolveEvent } from "@/lib/data";
import { fmt, fmtSites, fmtTime } from "@/lib/format";
import { SEQUENCE_LIMITS } from "@/lib/limits";
import type { PageProps } from "@/lib/page-types";
import { passcodeConfigured, RUN_COOKIE, runCookieValid } from "@/lib/passcode";
import type { Sequence } from "@/lib/schemas";

export const metadata: Metadata = { title: "Monitor" };

export default function MonitorPage({ searchParams }: PageProps) {
  return (
    <>
      <h1>Monitor</h1>
      <p className="lede">
        The agent&apos;s run on one earthquake over time: a first plan, then regular checks as new
        aftershocks arrive, with a re-plan when they drift away from what the plan expected.
      </p>
      <Suspense fallback={<Loading label="Loading the monitor" />}>
        <MonitorContent searchParams={searchParams} />
      </Suspense>
    </>
  );
}

function clampInt(value: unknown, min: number, max: number, fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.min(max, Math.max(min, Math.round(value)));
}

async function MonitorContent({ searchParams }: PageProps) {
  const resolved = await resolveEvent(await searchParams);
  if (!resolved.event) return <NoEvent resolved={resolved} />;
  const { events, event } = resolved;
  const [sequence, settings, activeJobId, cookieStore] = await Promise.all([
    loadSequence(event.id),
    loadSettings(),
    loadActiveJobId(event.id, "sequence"),
    cookies(),
  ]);
  const data = sequence.state === "live" || sequence.state === "snapshot" ? sequence.data : null;
  const saved = settings.state === "live" ? settings.data : null;
  const { hours: H, step_hours: S } = SEQUENCE_LIMITS;

  return (
    <>
      <OfflineBanner results={[events, sequence]} />
      <EventBar
        events={events.state === "live" || events.state === "snapshot" ? events.data.events : []}
        current={event}
        action="/monitor"
      />
      <SequenceStarter
        key={event.id}
        eventId={event.id}
        defaultHours={clampInt(saved?.monitor_hours, H.min, H.max, H.default)}
        defaultStepHours={clampInt(saved?.monitor_interval_hours, S.min, S.max, S.default)}
        initialActiveJobId={activeJobId}
        backendOnline={events.state === "live"}
        passcodeSet={passcodeConfigured()}
        initiallyUnlocked={runCookieValid(cookieStore.get(RUN_COOKIE)?.value)}
      />
      {isNotFound(sequence) ? (
        <Empty>No sequence has been run for this earthquake yet. Start a replay above.</Empty>
      ) : (
        <Problem result={sequence} what="the sequence" />
      )}
      {data ? (
        <>
          <SequenceSummary sequence={data} />
          <SequenceViewer
            key={`${data.event_id}-${data.steps.length}`}
            sequence={data}
            title={event.name}
          />
        </>
      ) : null}
    </>
  );
}

function SequenceSummary({ sequence }: { sequence: Sequence }) {
  return (
    <section aria-labelledby="summary-heading">
      <h2 id="summary-heading">Sequence</h2>
      {sequence.status === "running" ? (
        <p className="notice notice-info">
          This sequence is still running. The steps below are the ones finished so far; reload the
          page to see more.
        </p>
      ) : null}
      {sequence.status === "failed" ? (
        <p className="notice notice-error">This sequence failed before it finished.</p>
      ) : null}
      {sequence.feasibility_checked === false ? (
        <p className="notice notice-warn">
          The road check was unavailable, so the sites were not checked for access.
        </p>
      ) : null}
      <dl className="kpis">
        <div>
          <dt>Plans made</dt>
          <dd>{sequence.plans_made ?? "n/a"}</dd>
        </div>
        <div>
          <dt>Sensor moves in total</dt>
          <dd>{sequence.moves_total ?? "n/a"}</dd>
        </div>
        <div>
          <dt>Sites in place now</dt>
          <dd>{sequence.current_sites ? fmtSites(sequence.current_sites) : "n/a"}</dd>
        </div>
      </dl>
      <details className="more">
        <summary>More detail</summary>
        <dl className="facts">
          <div>
            <dt>Mode</dt>
            <dd>
              {sequence.mode === "replay" ? "replay (simulated clock)" : (sequence.mode ?? "n/a")}
            </dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{sequence.status}</dd>
          </div>
          <div>
            <dt>Hours done</dt>
            <dd>
              {typeof sequence.hours_done === "number" ? fmt(sequence.hours_done, 0) : "n/a"} of{" "}
              {typeof sequence.hours_total === "number" ? fmt(sequence.hours_total, 0) : "n/a"}
            </dd>
          </div>
          <div>
            <dt>Started, finished</dt>
            <dd>
              {fmtTime(sequence.started_utc)}, {fmtTime(sequence.finished_utc)}
            </dd>
          </div>
          <div>
            <dt>Real aftershocks in the replayed period</dt>
            <dd>{sequence.aftershocks.length}</dd>
          </div>
        </dl>
      </details>
      {sequence.settings && Object.keys(sequence.settings).length > 0 ? (
        <p className="small muted">
          Settings used:{" "}
          {Object.entries(sequence.settings)
            .map(([key, value]) => `${key.replaceAll("_", " ")} ${String(value)}`)
            .join(", ")}
          .
        </p>
      ) : null}
    </section>
  );
}
