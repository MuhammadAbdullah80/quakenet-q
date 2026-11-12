import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Suspense } from "react";
import { FeedConsole } from "@/components/FeedConsole";
import { FeedSummary } from "@/components/FeedSummary";
import { QuakeGlobe } from "@/components/QuakeGlobe";
import { Empty, Loading, OfflineBanner, Problem } from "@/components/States";
import { loadFeed } from "@/lib/data";
import { fmt, fmtTime } from "@/lib/format";
import { passcodeConfigured, RUN_COOKIE, runCookieValid } from "@/lib/passcode";

export const metadata: Metadata = { title: "Live feed" };

export default function FeedPage() {
  return (
    <>
      <h1>Live feed</h1>
      <p className="lede">
        Every earthquake of magnitude 2.5 or more in the last 24 hours, straight from the U.S.
        Geological Survey. Only a big one (the trigger size) would start the agent.
      </p>
      <Suspense fallback={<Loading label="Loading the live feed" />}>
        <FeedContent />
      </Suspense>
    </>
  );
}

async function FeedContent() {
  const [feed, cookieStore] = await Promise.all([loadFeed(), cookies()]);
  const data = feed.state === "live" || feed.state === "snapshot" ? feed.data : null;
  // The most recent quake gets one pulse on the globe.
  const newest = (data?.quakes ?? []).reduce(
    (a, q) => ((q.time_utc ?? "") > a ? (q.time_utc ?? "") : a),
    "",
  );
  return (
    <>
      <OfflineBanner results={[feed]} />
      <Problem result={feed} what="the live feed" />
      {data ? (
        <>
          <details className="more">
            <summary>About this feed</summary>
            <dl className="facts">
              <div>
                <dt>Trigger magnitude</dt>
                <dd>{fmt(data.threshold, 1)} or larger</dd>
              </div>
              <div>
                <dt>Live mode</dt>
                <dd>
                  {data.live_enabled
                    ? "on: the agent starts by itself"
                    : "off: the agent starts only by hand"}
                </dd>
              </div>
              <div>
                <dt>Feed retrieved</dt>
                <dd>{fmtTime(data.retrieved_utc)}</dd>
              </div>
              <div>
                <dt>Source</dt>
                {/* Shown as text on purpose: backend data is never turned into a link. */}
                <dd>{data.source_url ?? "n/a"}</dd>
              </div>
            </dl>
          </details>
          <p className="small muted">
            Status: <strong>below trigger</strong> is smaller than the trigger magnitude;{" "}
            <strong>pending</strong> is large enough but not handled yet (or live mode is off);{" "}
            <strong>skipped</strong> is large enough but unusable, with the reason;{" "}
            <strong>planned</strong> means the agent has made a plan for it.
          </p>
          {data.quakes.length > 0 ? (
            <FeedSummary quakes={data.quakes} threshold={data.threshold} />
          ) : null}
          {data.quakes.some((q) => typeof q.lat === "number" && typeof q.lon === "number") ? (
            <QuakeGlobe
              label={`The past 24 hours: ${data.quakes.length} earthquakes of magnitude 2.5 and above.`}
              dotLabel="earthquake, sized by magnitude"
              flagLabel={`reaches the trigger magnitude${typeof data.threshold === "number" ? ` (${fmt(data.threshold, 1)})` : ""}`}
              points={data.quakes
                .filter((q) => typeof q.lat === "number" && typeof q.lon === "number")
                .map((q) => ({
                  id: q.usgs_id,
                  lat: q.lat as number,
                  lon: q.lon as number,
                  mag: q.magnitude,
                  title: q.place ?? q.usgs_id,
                  detail: `M ${fmt(q.magnitude, 1)}, ${fmtTime(q.time_utc)}${typeof q.depth_km === "number" ? `, ${fmt(q.depth_km, 0)} km deep` : ""}`,
                  flag: q.would_trigger === true,
                  newest: !!q.time_utc && q.time_utc === newest,
                }))}
            />
          ) : null}
          {data.quakes.length === 0 ? (
            <Empty>No earthquakes of magnitude 2.5 or more in the past 24 hours.</Empty>
          ) : (
            <FeedConsole
              quakes={data.quakes}
              backendOnline={feed.state === "live"}
              passcodeSet={passcodeConfigured()}
              initiallyUnlocked={runCookieValid(cookieStore.get(RUN_COOKIE)?.value)}
            />
          )}
        </>
      ) : null}
    </>
  );
}
