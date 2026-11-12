// Shapes of the backend responses, following docs/API.md (v1).
// Every response is parsed with these before it is rendered, so a malformed
// reply becomes an error state instead of a broken page.
import { z } from "zod";
import { ID_PATTERN, LIMITS } from "@/lib/limits";

export { ID_PATTERN, LIMITS };

const sites = z.array(z.number().int().min(0));
const point3 = z.tuple([z.number(), z.number(), z.number()]);

export const healthSchema = z.object({
  status: z.string(),
  version: z.string(),
  region: z.string(),
  time_utc: z.string(),
});

export const eventSchema = z.object({
  id: z.string(),
  name: z.string(),
  magnitude: z.number(),
  time_utc: z.string(),
  region: z.string(),
  available: z.boolean(),
});
export const eventsSchema = z.object({ events: z.array(eventSchema) });

export const instanceSchema = z.object({
  event_id: z.string(),
  n: z.number().int(),
  k: z.number().int(),
  decision_hours: z.number(),
  mainshock: z.object({ x: z.number(), y: z.number(), depth: z.number() }),
  design_events: z.array(point3),
  valid_events: z.array(point3),
  stations: z.array(z.object({ name: z.string(), x: z.number(), y: z.number() })),
  candidates: z.array(
    z.object({ id: z.number().int(), x: z.number(), y: z.number(), risk: z.number() }),
  ),
});

export const scoringSchema = z.object({
  lam: z.number(),
  feasible_networks: z.number().int(),
  fidelity: z.array(
    z.object({
      order: z.number().int(),
      terms: z.number().int(),
      spearman: z.number(),
      max_abs_error: z.number(),
      rank_of_its_optimum: z.number().int(),
    }),
  ),
  exact_optimum: sites,
  top_networks: z.array(
    z.object({
      sites,
      objective: z.number(),
      risk: z.number(),
      blur_km: z.number(),
      rank: z.number().int(),
    }),
  ),
});

export const baselinesSchema = z.object({
  lam: z.number(),
  no_new_sensors: z.object({ blur_km: z.number(), loc_error_mean_km: z.number() }),
  methods: z.array(
    z.object({
      name: z.string(),
      sites,
      objective: z.number(),
      rank: z.number().int(),
      risk: z.number(),
      blur_km: z.number(),
      loc_error_mean_km: z.number(),
    }),
  ),
});

export const jobStatusSchema = z.enum(["queued", "running", "done", "failed"]);

export const jobResultSchema = z.object({
  reps: z.number().int(),
  seed: z.number().int(),
  shots: z.number().int(),
  lam: z.number(),
  seconds: z.number(),
  ratio: z.number(),
  p_opt: z.number(),
  uniform_p_opt: z.number(),
  feasible: z.number(),
  depth: z.number().int(),
  gates: z.number().int(),
  evaluations: z.number().int(),
  exact_optimum: sites,
  top_counts: z.array(
    z.object({ sites, count: z.number().int(), objective: z.number(), rank: z.number().int() }),
  ),
  final: z.object({ sites, objective: z.number(), rank: z.number().int() }),
  quantum_agreed: z.boolean(),
});

export const jobSchema = z.object({
  job_id: z.string(),
  kind: z.string(),
  event_id: z.string(),
  status: jobStatusSchema,
  created_utc: z.string().nullish(),
  finished_utc: z.string().nullish(),
  error: z.string().nullish(),
  result: jobResultSchema.nullish(),
});
export const jobsSchema = z.object({ jobs: z.array(jobSchema) });

export const jobCreatedSchema = z.object({ job_id: z.string(), status: jobStatusSchema });

export const systemSchema = z.object({
  jobs_running: z.number().int(),
  jobs_last_hour: z.number().int(),
  job_hourly_cap: z.number().int(),
  sources: z.array(
    z.object({
      name: z.string(),
      cached: z.boolean(),
      retrieved_utc: z.string().nullish(),
      url: z.string().nullish(),
    }),
  ),
});

/** Body accepted by this console's own "start a run" route handler. */
export const startJobSchema = z.strictObject({
  kind: z.literal("qaoa"),
  reps: z.number().int().min(LIMITS.reps.min).max(LIMITS.reps.max),
  seed: z.number().int().min(LIMITS.seed.min).max(LIMITS.seed.max),
  shots: z.number().int().min(LIMITS.shots.min).max(LIMITS.shots.max),
  lam: z.number().min(LIMITS.lam.min).max(LIMITS.lam.max),
});

export type Health = z.infer<typeof healthSchema>;
export type EventSummary = z.infer<typeof eventSchema>;
export type Events = z.infer<typeof eventsSchema>;
export type Instance = z.infer<typeof instanceSchema>;
export type Scoring = z.infer<typeof scoringSchema>;
export type Baselines = z.infer<typeof baselinesSchema>;
export type Job = z.infer<typeof jobSchema>;
export type JobResult = z.infer<typeof jobResultSchema>;
export type Jobs = z.infer<typeof jobsSchema>;
export type SystemInfo = z.infer<typeof systemSchema>;
export type StartJob = z.infer<typeof startJobSchema>;
