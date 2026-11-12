"use client";

import { useEffect, useState, type FormEvent } from "react";
import { CircuitSim } from "@/components/CircuitSim";
import { JobResultView } from "@/components/JobResultView";
import { ID_PATTERN, LIMITS } from "@/lib/limits";
import type { Instance, Job } from "@/lib/schemas";

// The browser only ever talks to this console's own /api routes, never to the
// Python API.

const POLL_MS = 2000;
const MAX_POLL_FAILURES = 5;

type Props = {
  eventId: string;
  instance: Instance | null;
  /** Newest finished job known when the page was rendered. */
  initialJob: Job | null;
  /** A job that was already queued or running when the page was rendered. */
  initialActiveJobId: string | null;
  /** False in offline mode: the form is disabled. */
  backendOnline: boolean;
  passcodeSet: boolean;
  initiallyUnlocked: boolean;
};

type Message = { tone: "error" | "info"; text: string };
type ApiError = { error?: { code?: string; message?: string } };

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function errorMessage(status: number, body: unknown, retryAfter: string | null): string {
  const error = (body as ApiError | null)?.error;
  switch (error?.code) {
    case "JOB_RUNNING":
      return "A run is already in progress. Wait for it to finish, then try again.";
    case "RATE_LIMITED":
      return `Too many runs started. ${retryAfter ? `Try again in ${retryAfter} s.` : "Try again in a minute."}`;
    case "BACKEND_OFFLINE":
      return "The backend is not reachable right now, so no run can be started.";
    case "UNAUTHORIZED":
      return "Enter the team passcode to start a run.";
    default:
      return error?.message || `The request failed (status ${status}).`;
  }
}

export function QuantumConsole({
  eventId,
  instance,
  initialJob,
  initialActiveJobId,
  backendOnline,
  passcodeSet,
  initiallyUnlocked,
}: Props) {
  const [unlocked, setUnlocked] = useState(initiallyUnlocked);
  const [activeJobId, setActiveJobId] = useState<string | null>(initialActiveJobId);
  const [activeStatus, setActiveStatus] = useState<string>("queued");
  const [job, setJob] = useState<Job | null>(initialJob);
  const [message, setMessage] = useState<Message | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // Settings of the run in progress, for the circuit view.
  const [runSettings, setRunSettings] = useState<{ reps: number; shots: number }>({
    reps: LIMITS.reps.default,
    shots: LIMITS.shots.default,
  });

  // Poll the job every 2 s until it is done or failed.
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
        const body = await readJson(response);
        if (cancelled) return;
        if (!response.ok || !body) throw new Error("poll failed");
        failures = 0;
        const current = body as Job;
        setActiveStatus(current.status);
        if (current.status === "done") {
          setJob(current);
          setMessage({ tone: "info", text: `Run ${current.job_id} finished.` });
          setActiveJobId(null);
          return;
        }
        if (current.status === "failed") {
          setMessage({
            tone: "error",
            text: `Run ${current.job_id} failed${current.error ? `: ${current.error}` : "."}`,
          });
          setActiveJobId(null);
          return;
        }
      } catch {
        if (cancelled) return;
        failures += 1;
        if (failures >= MAX_POLL_FAILURES) {
          setMessage({
            tone: "error",
            text: "Lost contact with the backend while waiting for the run. Reload the page to check again.",
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
  }, [activeJobId]);

  async function startRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      kind: "qaoa",
      reps: Number(form.get("reps")),
      seed: Number(form.get("seed")),
      shots: Number(form.get("shots")),
      lam: Number(form.get("lam")),
    };
    setSubmitting(true);
    setMessage(null);
    try {
      const response = await fetch(`/api/events/${encodeURIComponent(eventId)}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await readJson(response);
      const jobId = (body as { job_id?: unknown } | null)?.job_id;
      if (response.status === 202 && typeof jobId === "string" && ID_PATTERN.test(jobId)) {
        setActiveStatus("queued");
        setRunSettings({ reps: payload.reps, shots: payload.shots });
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

  async function submitPasscode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const passcode = String(new FormData(formElement).get("passcode") ?? "");
    setSubmitting(true);
    setMessage(null);
    try {
      const response = await fetch("/api/passcode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ passcode }),
      });
      if (response.ok) {
        setUnlocked(true);
        formElement.reset();
        setMessage({
          tone: "info",
          text: "Passcode accepted. You can start runs from this browser.",
        });
      } else {
        const body = await readJson(response);
        setMessage({
          tone: "error",
          text:
            response.status === 401
              ? "That passcode is not correct."
              : errorMessage(response.status, body, response.headers.get("retry-after")),
        });
      }
    } catch {
      setMessage({ tone: "error", text: "The request could not be sent. Check your connection." });
    } finally {
      setSubmitting(false);
    }
  }

  async function forgetPasscode() {
    try {
      await fetch("/api/passcode", { method: "DELETE" });
    } finally {
      setUnlocked(false);
      setMessage({ tone: "info", text: "Passcode forgotten on this browser." });
    }
  }

  const running = activeJobId !== null;
  const canStart = backendOnline && passcodeSet && unlocked && !running && !submitting;

  return (
    <div>
      <section className="panel" aria-labelledby="run-heading">
        <h2 id="run-heading">Start a QAOA run</h2>

        {!backendOnline ? (
          <p className="notice notice-warn">
            Starting runs is disabled while the backend is offline.
          </p>
        ) : !passcodeSet ? (
          <p className="notice notice-warn">
            Starting runs is disabled: no team passcode is configured on this deployment
            (RUN_PASSCODE).
          </p>
        ) : !unlocked ? (
          <form onSubmit={submitPasscode} aria-describedby="passcode-help">
            <p id="passcode-help">
              Starting a run needs the team passcode. Reading results does not.
            </p>
            <div className="fields">
              <div className="field">
                <label htmlFor="passcode">Team passcode</label>
                <input
                  id="passcode"
                  name="passcode"
                  type="password"
                  autoComplete="current-password"
                  required
                  maxLength={200}
                />
              </div>
              <button type="submit" disabled={submitting}>
                Unlock
              </button>
            </div>
          </form>
        ) : null}

        <form onSubmit={startRun}>
          <fieldset disabled={!canStart} className="panel">
            <legend>Run settings</legend>
            <div className="fields">
              <div className="field">
                <label htmlFor="reps">Layers (reps)</label>
                <input
                  id="reps"
                  name="reps"
                  type="number"
                  required
                  step={1}
                  min={LIMITS.reps.min}
                  max={LIMITS.reps.max}
                  defaultValue={LIMITS.reps.default}
                  aria-describedby="reps-hint"
                />
                <span className="hint" id="reps-hint">
                  {LIMITS.reps.min} to {LIMITS.reps.max}
                </span>
              </div>
              <div className="field">
                <label htmlFor="seed">Random seed</label>
                <input
                  id="seed"
                  name="seed"
                  type="number"
                  required
                  step={1}
                  min={LIMITS.seed.min}
                  max={LIMITS.seed.max}
                  defaultValue={LIMITS.seed.default}
                  aria-describedby="seed-hint"
                />
                <span className="hint" id="seed-hint">
                  {LIMITS.seed.min} to {LIMITS.seed.max}
                </span>
              </div>
              <div className="field">
                <label htmlFor="shots">Measurements (shots)</label>
                <input
                  id="shots"
                  name="shots"
                  type="number"
                  required
                  step={1}
                  min={LIMITS.shots.min}
                  max={LIMITS.shots.max}
                  defaultValue={LIMITS.shots.default}
                  aria-describedby="shots-hint"
                />
                <span className="hint" id="shots-hint">
                  {LIMITS.shots.min} to {LIMITS.shots.max}
                </span>
              </div>
              <div className="field">
                <label htmlFor="run-lam">Risk weight (lam)</label>
                <input
                  id="run-lam"
                  name="lam"
                  type="number"
                  required
                  step="any"
                  min={LIMITS.lam.min}
                  max={LIMITS.lam.max}
                  defaultValue={LIMITS.lam.default}
                  aria-describedby="run-lam-hint"
                />
                <span className="hint" id="run-lam-hint">
                  {LIMITS.lam.min} to {LIMITS.lam.max}
                </span>
              </div>
              <button type="submit">{running ? "Run in progress" : "Start run"}</button>
            </div>
          </fieldset>
        </form>

        {unlocked && passcodeSet && backendOnline ? (
          <p className="small">
            <button type="button" className="secondary" onClick={forgetPasscode}>
              Forget passcode on this browser
            </button>
          </p>
        ) : null}

        <div aria-live="polite">
          {running ? (
            <>
              <CircuitSim
                layers={runSettings.reps}
                shots={runSettings.shots}
                status={activeStatus}
              />
              <p className="loading">
                Run {activeJobId} is {activeStatus}. Checking every 2 seconds
              </p>
            </>
          ) : null}
          {message ? (
            <p className={`notice ${message.tone === "error" ? "notice-error" : "notice-info"}`}>
              {message.text}
            </p>
          ) : null}
        </div>
      </section>

      <section aria-labelledby="result-heading">
        <h2 id="result-heading">Latest result</h2>
        {job?.result ? (
          <JobResultView job={job} instance={instance} />
        ) : (
          <p className="notice notice-info">
            No finished run for this earthquake yet. Start one above.
          </p>
        )}
      </section>
    </div>
  );
}
