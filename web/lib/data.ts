import "server-only";
import { headers } from "next/headers";
import { z } from "zod";
import { backendRequest, type BackendFailure, type UnreachableReason } from "@/lib/backend";
import { clientIpFrom } from "@/lib/client-ip";
import {
  baselinesSchema,
  eventsSchema,
  healthSchema,
  ID_PATTERN,
  instanceSchema,
  jobSchema,
  jobsSchema,
  LIMITS,
  scoringSchema,
  systemSchema,
  type EventSummary,
  type Events,
  type Job,
} from "@/lib/schemas";
import { snapshots, type Snapshot } from "@/lib/snapshots";

/** What a page gets for each thing it asks the backend for. */
export type Loaded<T> =
  | { state: "live"; data: T }
  /** Backend unreachable: a saved snapshot is shown instead. */
  | { state: "snapshot"; data: T; mock: boolean; reason: UnreachableReason }
  /** Backend unreachable and nothing saved for this. */
  | { state: "offline"; reason: UnreachableReason }
  /** 501 NOT_BUILT. */
  | { state: "not_built" }
  | { state: "error"; status: number; code: string; message: string; retryAfterSeconds: number | null };

export function failureToLoaded<T>(
  failure: BackendFailure,
  snapshot: Snapshot<T> | null = null,
): Loaded<T> {
  if (failure.kind === "unreachable") {
    return snapshot
      ? { state: "snapshot", data: snapshot.data, mock: snapshot.mock, reason: failure.reason }
      : { state: "offline", reason: failure.reason };
  }
  if (failure.kind === "api") {
    if (failure.code === "NOT_BUILT") return { state: "not_built" };
    return {
      state: "error",
      status: failure.status,
      code: failure.code,
      message: failure.message,
      retryAfterSeconds: failure.retryAfterSeconds,
    };
  }
  return {
    state: "error",
    status: failure.status,
    code: "BAD_RESPONSE",
    message: failure.message,
    retryAfterSeconds: null,
  };
}

/** Reading request headers also marks the caller as request-time rendered. */
async function visitorIp(): Promise<string | null> {
  return clientIpFrom(await headers());
}

async function load<S extends z.ZodType>(
  path: string,
  schema: S,
  snapshot: () => Snapshot<z.infer<S>> | null = () => null,
): Promise<Loaded<z.infer<S>>> {
  const result = await backendRequest(path, schema, { clientIp: await visitorIp() });
  if (result.ok) return { state: "live", data: result.data };
  return failureToLoaded(result, snapshot());
}

const eventPath = (eventId: string) => `/events/${encodeURIComponent(eventId)}`;

export function parseLam(raw: string | string[] | undefined): number {
  const value = Number(Array.isArray(raw) ? raw[0] : raw);
  if (raw === undefined || raw === "" || !Number.isFinite(value)) return LIMITS.lam.default;
  return Math.min(LIMITS.lam.max, Math.max(LIMITS.lam.min, value));
}

export const loadEvents = () => load("/events", eventsSchema, snapshots.events);

export const loadInstance = (eventId: string) =>
  load(`${eventPath(eventId)}/instance`, instanceSchema, () => snapshots.instance(eventId));

export const loadScoring = (eventId: string, lam: number) =>
  load(`${eventPath(eventId)}/scoring?lam=${lam}`, scoringSchema, () => snapshots.scoring(eventId));

export const loadBaselines = (eventId: string, lam: number) =>
  load(`${eventPath(eventId)}/baselines?lam=${lam}`, baselinesSchema, () =>
    snapshots.baselines(eventId),
  );

export const loadHealth = () => load("/health", healthSchema);
export const loadSystem = () => load("/system", systemSchema);
export const loadJobs = () => load("/jobs", jobsSchema);

/** Endpoints whose response shape is not in the contract yet (plan, replay, memory). */
export const loadUnspecified = (path: string) => load(path, z.unknown());
export const planPath = (eventId: string) => `${eventPath(eventId)}/plan`;
export const replayPath = (eventId: string) => `${eventPath(eventId)}/replay`;

export type LatestJob = {
  /** Newest finished QAOA job for the event (with its result), if any. */
  latest: Loaded<Job | null>;
  /** A job for the event that is still queued or running, if any. */
  activeJobId: string | null;
};

export async function loadLatestJob(eventId: string): Promise<LatestJob> {
  const jobs = await loadJobs();
  if (jobs.state !== "live") {
    if (jobs.state === "offline") {
      const saved = snapshots.job(eventId);
      if (saved) {
        return {
          latest: { state: "snapshot", data: saved.data, mock: saved.mock, reason: jobs.reason },
          activeJobId: null,
        };
      }
    }
    return { latest: jobs as Loaded<never>, activeJobId: null };
  }
  const mine = jobs.data.jobs.filter((job) => job.event_id === eventId && job.kind === "qaoa");
  const active = mine.find((job) => job.status === "queued" || job.status === "running");
  const activeJobId = active && ID_PATTERN.test(active.job_id) ? active.job_id : null;
  const done = mine.find((job) => job.status === "done" && ID_PATTERN.test(job.job_id));
  if (!done) return { latest: { state: "live", data: null }, activeJobId };
  const detail = await load(`/jobs/${encodeURIComponent(done.job_id)}`, jobSchema, () =>
    snapshots.job(eventId),
  );
  return { latest: detail, activeJobId };
}

export type ResolvedEvent = {
  events: Loaded<Events>;
  /** The event the page should show: the requested one if allowed, else the first available. */
  event: EventSummary | null;
};

type SearchParams = Record<string, string | string[] | undefined>;

export async function resolveEvent(searchParams: SearchParams): Promise<ResolvedEvent> {
  const events = await loadEvents();
  if (events.state !== "live" && events.state !== "snapshot") return { events, event: null };
  const requested = Array.isArray(searchParams.event) ? searchParams.event[0] : searchParams.event;
  // Allowlist: only IDs the backend itself listed are ever used in a backend path.
  const usable = events.data.events.filter((e) => e.available && ID_PATTERN.test(e.id));
  const event = usable.find((e) => e.id === requested) ?? usable[0] ?? null;
  return { events, event };
}
