import type { Metadata } from "next";
import { Suspense } from "react";
import { EventBar } from "@/components/EventBar";
import { ModuleProbe } from "@/components/ModuleProbe";
import { NoEvent } from "@/components/NoEvent";
import { Loading } from "@/components/States";
import { loadUnspecified, replayPath, resolveEvent } from "@/lib/data";
import type { PageProps } from "@/lib/page-types";

export const metadata: Metadata = { title: "Monitor" };

export default function MonitorPage({ searchParams }: PageProps) {
  return (
    <>
      <h1>Monitor</h1>
      <p className="lede">
        Replay of an earthquake over time: drift checks and re-plans as new aftershocks arrive.
      </p>
      <Suspense fallback={<Loading label="Asking the backend" />}>
        <MonitorContent searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function MonitorContent({ searchParams }: PageProps) {
  const resolved = await resolveEvent(await searchParams);
  if (!resolved.event) return <NoEvent resolved={resolved} />;
  const { events, event } = resolved;
  const result = await loadUnspecified(replayPath(event.id));
  return (
    <>
      <EventBar
        events={events.state === "live" || events.state === "snapshot" ? events.data.events : []}
        current={event}
        action="/monitor"
      />
      <ModuleProbe result={result} what="The monitor (replay) module" extra={[events]} />
    </>
  );
}
