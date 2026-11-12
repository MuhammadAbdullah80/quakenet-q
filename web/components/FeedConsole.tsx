"use client";

import Link from "next/link";
import { useState } from "react";
import { PasscodeGate } from "@/components/PasscodeGate";
import { errorMessage, readJson, type Message } from "@/lib/client-api";
import { fmt, fmtTime } from "@/lib/format";
import { ID_PATTERN, USGS_ID_PATTERN } from "@/lib/limits";
import type { FeedQuake } from "@/lib/schemas";
import { TableFold } from "@/components/TableFold";
import { Coord } from "@/components/Coord";

type Props = {
  quakes: FeedQuake[];
  backendOnline: boolean;
  passcodeSet: boolean;
  initiallyUnlocked: boolean;
};

const STATUS: Record<FeedQuake["status"], { label: string; tone: string }> = {
  below_threshold: { label: "below trigger", tone: "" },
  pending: { label: "pending", tone: "tag-warn" },
  skipped: { label: "skipped", tone: "tag-bad" },
  planned: { label: "planned", tone: "tag-ok" },
};

/** A row can be started by hand when it is at or above the trigger and not yet handled. */
function qualifies(quake: FeedQuake): boolean {
  return quake.status === "pending" && USGS_ID_PATTERN.test(quake.usgs_id);
}

function place(quake: FeedQuake): string {
  return quake.place?.trim() || "Unnamed place";
}

export function FeedConsole({ quakes, backendOnline, passcodeSet, initiallyUnlocked }: Props) {
  const [unlocked, setUnlocked] = useState(initiallyUnlocked);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [started, setStarted] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<Message | null>(null);
  const canStart = backendOnline && passcodeSet && unlocked && busyId === null;
  const anyQualifies = quakes.some(qualifies);

  async function trigger(quake: FeedQuake) {
    if (!USGS_ID_PATTERN.test(quake.usgs_id)) return;
    setBusyId(quake.usgs_id);
    setMessage(null);
    try {
      const response = await fetch(`/api/feed/${encodeURIComponent(quake.usgs_id)}/trigger`, {
        method: "POST",
      });
      const body = await readJson(response);
      const jobId = (body as { job_id?: unknown } | null)?.job_id;
      if (response.status === 202 && typeof jobId === "string" && ID_PATTERN.test(jobId)) {
        setStarted((s) => ({ ...s, [quake.usgs_id]: jobId }));
        setMessage({
          tone: "info",
          text: `The agent started on ${place(quake)} (job ${jobId}). The earthquake appears on the Events page once its data is ready; follow the job on the System page.`,
        });
      } else {
        if (response.status === 401) setUnlocked(false);
        setMessage({
          tone: "error",
          text: errorMessage(response.status, body, response.headers.get("retry-after")),
        });
      }
    } catch {
      setMessage({ tone: "error", text: "The request could not be sent. Check your connection." });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      {anyQualifies ? (
        <section className="panel" aria-labelledby="trigger-heading">
          <h2 id="trigger-heading">Start the agent by hand</h2>
          <PasscodeGate
            action="start the agent"
            backendOnline={backendOnline}
            passcodeSet={passcodeSet}
            unlocked={unlocked}
            onChange={setUnlocked}
            idPrefix="feed"
          />
          <div aria-live="polite">
            {message ? (
              <p className={`notice ${message.tone === "error" ? "notice-error" : "notice-info"}`}>
                {message.text}
              </p>
            ) : null}
          </div>
        </section>
      ) : null}

      <TableFold total={quakes.length} limit={8} noun="earthquakes">
        <div className="table-wrap">
          <table>
            <caption>Earthquakes in the past 24 hours, newest first ({quakes.length})</caption>
            <thead>
              <tr>
                <th scope="col" className="num">
                  Magnitude
                </th>
                <th scope="col">Place</th>
                <th scope="col">Time</th>
                <th scope="col" className="num">
                  Depth (km)
                </th>
                <th scope="col">Location</th>
                <th scope="col">Status</th>
                <th scope="col">Reason</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {quakes.map((quake) => {
                const status = STATUS[quake.status];
                const jobId = started[quake.usgs_id];
                return (
                  <tr key={quake.usgs_id}>
                    <td className="num">{fmt(quake.magnitude, 1)}</td>
                    <th scope="row">
                      {place(quake)} <span className="muted small">({quake.usgs_id})</span>
                    </th>
                    <td>{fmtTime(quake.time_utc)}</td>
                    <td className="num">
                      {typeof quake.depth_km === "number" ? fmt(quake.depth_km, 1) : "n/a"}
                    </td>
                    <td>
                      <Coord lat={quake.lat} lon={quake.lon} />
                    </td>
                    <td>
                      <span className={`tag ${status.tone}`}>{status.label}</span>
                    </td>
                    <td>{quake.reason ?? ""}</td>
                    <td>
                      {jobId ? (
                        <span>Started (job {jobId})</span>
                      ) : qualifies(quake) ? (
                        <button
                          type="button"
                          disabled={!canStart}
                          onClick={() => trigger(quake)}
                          aria-label={`Start the agent on this earthquake: magnitude ${fmt(quake.magnitude, 1)}, ${place(quake)}`}
                        >
                          {busyId === quake.usgs_id
                            ? "Starting"
                            : "Start the agent on this earthquake"}
                        </button>
                      ) : quake.status === "planned" &&
                        quake.event_id &&
                        ID_PATTERN.test(quake.event_id) ? (
                        <Link href={`/monitor?event=${quake.event_id}`}>
                          Open the monitor<span className="muted"> for {place(quake)}</span>
                        </Link>
                      ) : (
                        <span className="muted">n/a</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </TableFold>
    </>
  );
}
