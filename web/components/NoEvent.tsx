import { Empty, OfflineBanner, Problem } from "@/components/States";
import type { ResolvedEvent } from "@/lib/data";

/** What an event page shows when there is no earthquake to show. */
export function NoEvent({ resolved }: { resolved: ResolvedEvent }) {
  const { events } = resolved;
  return (
    <>
      <OfflineBanner results={[events]} />
      <Problem result={events} what="the list of earthquakes" />
      {events.state === "live" || events.state === "snapshot" ? (
        <Empty>No earthquake is available yet.</Empty>
      ) : null}
    </>
  );
}
