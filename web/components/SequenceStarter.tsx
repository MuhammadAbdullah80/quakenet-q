"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { PasscodeGate } from "@/components/PasscodeGate";
import { errorMessage, readJson, type Message } from "@/lib/client-api";
import { ID_PATTERN, SEQUENCE_LIMITS } from "@/lib/limits";

// Starts a replay (a "sequence" job) through this console's own route handler
// and polls it every 2 s, like the Quantum page. The browser never calls the
// Python API.

const POLL_MS = 2000;
const MAX_POLL_FAILURES = 5;

type Props = {
  eventId: string;
  defaultHours: number;
  defaultStepHours: number;
  initialActiveJobId: string | null;
  backendOnline: boolean;
  passcodeSet: boolean;
  initiallyUnlocked: boolean;
};

type PolledJob = { job_id?: string; status?: string; error?: string | null };

export function SequenceStarter({
  eventId,
  defaultHours,
  defaultStepHours,
  initialActiveJobId,
  backendOnline,
  passcodeSet,
  initiallyUnlocked,
}: Props) {
  const router = useRouter();
  const [unlocked, setUnlocked] = useState(initiallyUnlocked);
  const [activeJobId, setActiveJobId] = useState<string | null>(initialActiveJobId);
  const [activeStatus, setActiveStatus] = useState("queued");
  const [message, setMessage] = useState<Message | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!activeJobId) return;
    let cancelled = false;
    let failures = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const response = await fetch(`/api/jobs/${encodeURIComponent(activeJobId)}`, {
          cache: "no-store",
        });
        const body = (await readJson(response)) as PolledJob | null;
        if (cancelled) return;
        if (!response.ok || !body) throw new Error("poll failed");
        failures = 0;
        setActiveStatus(String(body.status ?? "unknown"));
        if (body.status === "done") {
          setMessage({ tone: "info", text: `Replay ${activeJobId} finished.` });
          setActiveJobId(null);
          router.refresh();
          return;
        }
        if (body.status === "failed") {
          setMessage({
            tone: "error",
            text: `Replay ${activeJobId} failed${body.error ? `: ${body.error}` : "."}`,
          });
          setActiveJobId(null);
          router.refresh();
          return;
        }
      } catch {
        if (cancelled) return;
        failures += 1;
        if (failures >= MAX_POLL_FAILURES) {
          setMessage({
            tone: "error",
            text: "Lost contact with the backend while waiting for the replay. Reload the page to check again.",
          });
          setActiveJobId(null);
          return;
        }
      }
      timer = setTimeout(poll, POLL_MS);
    };

    timer = setTimeout(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [activeJobId, router]);

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const hours = Number(form.get("hours"));
    const stepHours = Number(form.get("step_hours"));
    const { hours: H, step_hours: S } = SEQUENCE_LIMITS;
    if (!Number.isInteger(hours) || hours < H.min || hours > H.max) {
      setMessage({ tone: "error", text: `Hours must be a whole number from ${H.min} to ${H.max}.` });
      return;
    }
    if (!Number.isInteger(stepHours) || stepHours < S.min || stepHours > S.max) {
      setMessage({
        tone: "error",
        text: `Step must be a whole number of hours from ${S.min} to ${S.max}.`,
      });
      return;
    }
    setSubmitting(true);
    setMessage(null);
    try {
      const response = await fetch(`/api/events/${encodeURIComponent(eventId)}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: "sequence", hours, step_hours: stepHours }),
      });
      const body = await readJson(response);
      const jobId = (body as { job_id?: unknown } | null)?.job_id;
      if (response.status === 202 && typeof jobId === "string" && ID_PATTERN.test(jobId)) {
        setActiveStatus("queued");
        setActiveJobId(jobId);
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
      setSubmitting(false);
    }
  }

  const running = activeJobId !== null;
  const canStart = backendOnline && passcodeSet && unlocked && !running && !submitting;
  const { hours: H, step_hours: S } = SEQUENCE_LIMITS;

  return (
    <section className="panel" aria-labelledby="replay-heading">
      <h2 id="replay-heading">Start a replay</h2>
      <p>
        A replay plays the earthquake forward on a simulated clock: a first plan at hour 0, then a
        check at every step, with a re-plan when the aftershocks drift. It never uses data from after
        the simulated time.
      </p>
      <PasscodeGate
        action="start a replay"
        backendOnline={backendOnline}
        passcodeSet={passcodeSet}
        unlocked={unlocked}
        onChange={setUnlocked}
        idPrefix="replay"
      />
      <form onSubmit={start}>
        <fieldset disabled={!canStart} className="panel">
          <legend>Replay settings</legend>
          <div className="fields">
            <div className="field">
              <label htmlFor="hours">Hours to replay</label>
              <input
                id="hours"
                name="hours"
                type="number"
                required
                step={1}
                min={H.min}
                max={H.max}
                defaultValue={defaultHours}
                aria-describedby="hours-hint"
              />
              <span className="hint" id="hours-hint">
                {H.min} to {H.max}
              </span>
            </div>
            <div className="field">
              <label htmlFor="step_hours">Hours between checks</label>
              <input
                id="step_hours"
                name="step_hours"
                type="number"
                required
                step={1}
                min={S.min}
                max={S.max}
                defaultValue={defaultStepHours}
                aria-describedby="step-hint"
              />
              <span className="hint" id="step-hint">
                {S.min} to {S.max}
              </span>
            </div>
            <button type="submit">{running ? "Replay in progress" : "Start replay"}</button>
          </div>
        </fieldset>
      </form>
      <div aria-live="polite">
        {running ? (
          <p className="loading">
            Replay {activeJobId} is {activeStatus}. Checking every 2 seconds
          </p>
        ) : null}
        {message ? (
          <p className={`notice ${message.tone === "error" ? "notice-error" : "notice-info"}`}>
            {message.text}
          </p>
        ) : null}
      </div>
    </section>
  );
}
