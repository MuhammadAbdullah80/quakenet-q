import "server-only";
import type { z } from "zod";
import baselinesRaw from "@/snapshots/baselines.json";
import eventsRaw from "@/snapshots/events.json";
import feedRaw from "@/snapshots/feed.json";
import instanceRaw from "@/snapshots/instance.json";
import jobRaw from "@/snapshots/job.json";
import memoryRaw from "@/snapshots/memory.json";
import noiseRaw from "@/snapshots/noise.json";
import planRaw from "@/snapshots/plan.json";
import scoringRaw from "@/snapshots/scoring.json";
import sequenceRaw from "@/snapshots/sequence.json";
import settingsRaw from "@/snapshots/settings.json";
import {
  baselinesSchema,
  eventsSchema,
  feedSchema,
  instanceSchema,
  jobSchema,
  memorySchema,
  noiseSchema,
  planSchema,
  scoringSchema,
  sequenceSchema,
  settingsSchema,
} from "@/lib/schemas";

// Saved API responses shipped with the frontend, used when the backend cannot
// be reached. Files marked `"mock": true` are placeholders, not real results.
// Refresh them from a running backend with `npm run capture-snapshots`.

export type Snapshot<T> = { data: T; mock: boolean };

function read<S extends z.ZodType>(schema: S, raw: unknown): Snapshot<z.infer<S>> | null {
  const parsed = schema.safeParse(raw);
  if (!parsed.success) return null;
  const mock = typeof raw === "object" && raw !== null && (raw as { mock?: unknown }).mock === true;
  return { data: parsed.data, mock };
}

/** The one event the per-event snapshots were captured for. */
function snapshotEventId(): string | null {
  return read(instanceSchema, instanceRaw)?.data.event_id ?? null;
}

function forEvent<T>(eventId: string, snapshot: Snapshot<T> | null): Snapshot<T> | null {
  return snapshot && snapshotEventId() === eventId ? snapshot : null;
}

export const snapshots = {
  events: () => read(eventsSchema, eventsRaw),
  instance: (eventId: string) => forEvent(eventId, read(instanceSchema, instanceRaw)),
  scoring: (eventId: string) => forEvent(eventId, read(scoringSchema, scoringRaw)),
  baselines: (eventId: string) => forEvent(eventId, read(baselinesSchema, baselinesRaw)),
  job: (eventId: string) => {
    const job = read(jobSchema, jobRaw);
    return job && job.data.event_id === eventId ? job : null;
  },
  settings: () => read(settingsSchema, settingsRaw),
  feed: () => read(feedSchema, feedRaw),
  memory: () => read(memorySchema, memoryRaw),
  noise: () => read(noiseSchema, noiseRaw),
  sequence: (eventId: string) => {
    const saved = read(sequenceSchema, sequenceRaw);
    return saved && saved.data.event_id === eventId ? saved : null;
  },
  plan: (eventId: string) => {
    const saved = read(planSchema, planRaw);
    return saved && saved.data.event_id === eventId ? saved : null;
  },
};
