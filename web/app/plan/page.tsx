import type { Metadata } from "next";
import { Suspense } from "react";
import { EventBar } from "@/components/EventBar";
import { ModuleProbe } from "@/components/ModuleProbe";
import { NoEvent } from "@/components/NoEvent";
import { Loading } from "@/components/States";
import { loadUnspecified, planPath, resolveEvent } from "@/lib/data";
import type { PageProps } from "@/lib/page-types";

export const metadata: Metadata = { title: "Plan" };

export default function PlanPage({ searchParams }: PageProps) {
  return (
    <>
      <h1>Plan</h1>
      <p className="lede">
        The final deployment plan for an earthquake: the chosen sites, the reason for each, and the
        confidence.
      </p>
      <Suspense fallback={<Loading label="Asking the backend" />}>
        <PlanContent searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function PlanContent({ searchParams }: PageProps) {
  const resolved = await resolveEvent(await searchParams);
  if (!resolved.event) return <NoEvent resolved={resolved} />;
  const { events, event } = resolved;
  const result = await loadUnspecified(planPath(event.id));
  return (
    <>
      <EventBar
        events={events.state === "live" || events.state === "snapshot" ? events.data.events : []}
        current={event}
        action="/plan"
      />
      <ModuleProbe result={result} what="The plan module" extra={[events]} />
    </>
  );
}
