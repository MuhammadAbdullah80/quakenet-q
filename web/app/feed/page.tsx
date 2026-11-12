import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Suspense } from "react";
import { FeedConsole } from "@/components/FeedConsole";
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
        Real earthquakes of magnitude 2.5 and above from the past 24 hours, from the USGS live feed,
        with what the agent did or would do with each one. The backend refreshes the feed at most
        once a minute.
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
  return (
    <>
      <OfflineBanner results={[feed]} />
      <Problem result={feed} what="the live feed" />
      {data ? (
        <>
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
          <p className="small muted">
            Status: <strong>below trigger</strong> is smaller than the trigger magnitude;{" "}
            <strong>pending</strong> is large enough but not handled yet (or live mode is off);{" "}
            <strong>skipped</strong> is large enough but unusable, with the reason;{" "}
            <strong>planned</strong> means the agent has made a plan for it.
          </p>
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
