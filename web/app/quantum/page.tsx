import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Suspense } from "react";
import { EventBar } from "@/components/EventBar";
import { NoEvent } from "@/components/NoEvent";
import { QuantumConsole } from "@/components/QuantumConsole";
import { Loading, OfflineBanner, Problem } from "@/components/States";
import { loadInstance, loadLatestJob, resolveEvent } from "@/lib/data";
import type { PageProps } from "@/lib/page-types";
import { passcodeConfigured, RUN_COOKIE, runCookieValid } from "@/lib/passcode";

export const metadata: Metadata = { title: "Quantum" };

export default function QuantumPage({ searchParams }: PageProps) {
  return (
    <>
      <h1>Quantum</h1>
      <p className="lede">
        The circuit is run many times; each run names one choice of 4 sites. The best choice should
        come up far more often than a random guess would.
      </p>
      <Suspense fallback={<Loading label="Loading the quantum module" />}>
        <QuantumContent searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function QuantumContent({ searchParams }: PageProps) {
  const resolved = await resolveEvent(await searchParams);
  if (!resolved.event) return <NoEvent resolved={resolved} />;
  const { events, event } = resolved;
  const [instance, jobs, cookieStore] = await Promise.all([
    loadInstance(event.id),
    loadLatestJob(event.id),
    cookies(),
  ]);
  const { latest, activeJobId } = jobs;
  const instanceData =
    instance.state === "live" || instance.state === "snapshot" ? instance.data : null;
  const job = latest.state === "live" || latest.state === "snapshot" ? latest.data : null;

  return (
    <>
      <OfflineBanner results={[events, instance, latest]} />
      <EventBar
        events={events.state === "live" || events.state === "snapshot" ? events.data.events : []}
        current={event}
        action="/quantum"
      />
      <Problem result={instance} what="the candidate sites" />
      <Problem result={latest} what="the latest quantum result" />
      <QuantumConsole
        key={event.id}
        eventId={event.id}
        instance={instanceData}
        initialJob={job}
        initialActiveJobId={activeJobId}
        backendOnline={events.state === "live"}
        passcodeSet={passcodeConfigured()}
        initiallyUnlocked={runCookieValid(cookieStore.get(RUN_COOKIE)?.value)}
      />
    </>
  );
}
