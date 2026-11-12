// Shapes of the backend responses, following docs/API.md (v1 and version 2).
// Every response is parsed with these before it is rendered, so a malformed
// reply becomes an error state instead of a broken page. Fields that version 2
// adds to v1 endpoints are optional, so older backends and snapshots still parse.
import { z } from "zod";
import { ID_PATTERN, LIMITS, SEQUENCE_LIMITS, USGS_ID_PATTERN } from "@/lib/limits";

export { ID_PATTERN, LIMITS, SEQUENCE_LIMITS, USGS_ID_PATTERN };

const sites = z.array(z.number().int().min(0));
const point3 = z.tuple([z.number(), z.number(), z.number()]);
const latLon = z.object({ lat: z.number(), lon: z.number() });
const grid = z.object({ lat0: z.number(), lon0: z.number() });
const station = z.object({ name: z.string(), x: z.number(), y: z.number() });
const mainshock = z.object({ x: z.number(), y: z.number(), depth: z.number() });

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
  kind: z.enum(["benchmark", "live"]).nullish(),
  usgs_id: z.string().nullish(),
  lat: z.number().nullish(),
  lon: z.number().nullish(),
});
export const eventsSchema = z.object({ events: z.array(eventSchema) });

export const instanceSchema = z.object({
  event_id: z.string(),
  n: z.number().int(),
  k: z.number().int(),
  decision_hours: z.number(),
  mainshock,
  design_events: z.array(point3),
  valid_events: z.array(point3),
  stations: z.array(station),
  candidates: z.array(
    z.object({
      id: z.number().int(),
      x: z.number(),
      y: z.number(),
      risk: z.number(),
      lat: z.number().nullish(),
      lon: z.number().nullish(),
    }),
  ),
  grid: grid.nullish(),
  feasibility_checked: z.boolean().nullish(),
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
  objective: z.enum(["cvar", "mean"]).nullish(),
  warm_start: z.boolean().nullish(),
});

/** Result of a finished `sequence` job (a replay). */
export const sequenceJobResultSchema = z.object({
  event_id: z.string(),
  steps: z.number().int(),
});

/** A QAOA job with its result. */
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

/** A job of any kind (QAOA run or sequence), as listed and as polled by the browser. */
export const anyJobSchema = jobSchema.extend({
  result: z.union([jobResultSchema, sequenceJobResultSchema]).nullish(),
});
export const jobsSchema = z.object({ jobs: z.array(anyJobSchema) });

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

// ---- Version 2: the agent ----

export const settingsSchema = z.object({
  trigger_magnitude: z.number().optional(),
  station_radius_km: z.number().optional(),
  sensors: z.number().optional(),
  candidates: z.number().optional(),
  risk_weight: z.number().optional(),
  move_cost: z.number().optional(),
  monitor_interval_hours: z.number().optional(),
  monitor_hours: z.number().optional(),
  drift_centroid_km: z.number().optional(),
  drift_score_drop: z.number().optional(),
  min_real_aftershocks: z.number().optional(),
  qaoa_layers: z.number().optional(),
  shots: z.number().optional(),
  hearing_range: z.boolean().optional(),
  live_enabled: z.boolean().optional(),
  max_plans_per_hour: z.number().optional(),
  limits: z.record(z.string(), z.tuple([z.number(), z.number()])).nullish(),
  updated_utc: z.string().nullish(),
});

export const feedStatusSchema = z.enum(["below_threshold", "pending", "skipped", "planned"]);

export const feedSchema = z.object({
  retrieved_utc: z.string().nullish(),
  source_url: z.string().nullish(),
  threshold: z.number(),
  live_enabled: z.boolean(),
  quakes: z.array(
    z.object({
      usgs_id: z.string(),
      place: z.string().nullish(),
      magnitude: z.number(),
      time_utc: z.string().nullish(),
      lat: z.number().nullish(),
      lon: z.number().nullish(),
      depth_km: z.number().nullish(),
      would_trigger: z.boolean().nullish(),
      status: feedStatusSchema,
      reason: z.string().nullish(),
      event_id: z.string().nullish(),
    }),
  ),
});

const move = z.object({ from: z.number().int(), to: z.number().int() });

export const stepPlanSchema = z.object({
  sites,
  risk: z.array(z.number()).nullish(),
  objective: z.number().nullish(),
  exact_rank: z.number().int().nullish(),
  quantum_agreed: z.boolean().nullish(),
  retries: z.number().int().nullish(),
  p_opt_per_shot: z.number().nullish(),
  moves: z.array(move).nullish(),
  expected_error_km: z.number().nullish(),
  expert_rule_error_km: z.number().nullish(),
  seconds: z.number().nullish(),
});

export const sequenceStepSchema = z.object({
  hour: z.number(),
  stage: z.enum(["first_plan", "check", "replan"]),
  aftershocks_real: z.number().int().nullish(),
  aftershocks_used: z.number().int().nullish(),
  synthetic: z.boolean().nullish(),
  centroid: z.object({ x: z.number(), y: z.number() }).nullish(),
  centroid_shift_km: z.number().nullish(),
  predicted_score: z.number().nullish(),
  realised_score: z.number().nullish(),
  score_drop: z.number().nullish(),
  drift: z.boolean().nullish(),
  drift_reason: z.string().nullish(),
  sites,
  plan: stepPlanSchema.nullish(),
});

export const sequenceSchema = z.object({
  event_id: z.string(),
  mode: z.string().nullish(),
  status: z.enum(["running", "done", "failed"]),
  hours_done: z.number().nullish(),
  hours_total: z.number().nullish(),
  started_utc: z.string().nullish(),
  finished_utc: z.string().nullish(),
  settings: z.record(z.string(), z.union([z.number(), z.boolean(), z.string()])).nullish(),
  grid: grid.nullish(),
  feasibility_checked: z.boolean().nullish(),
  mainshock,
  stations: z.array(station),
  candidates: z.array(
    z.object({
      id: z.number().int(),
      x: z.number(),
      y: z.number(),
      lat: z.number().nullish(),
      lon: z.number().nullish(),
      backups: z.array(latLon).nullish(),
    }),
  ),
  /** Each aftershock is [x, y, depth, magnitude, hours_after_mainshock]. */
  aftershocks: z.array(z.tuple([z.number(), z.number(), z.number(), z.number(), z.number()])),
  steps: z.array(sequenceStepSchema),
  current_sites: sites.nullish(),
  plans_made: z.number().int().nullish(),
  moves_total: z.number().int().nullish(),
});

export const confidenceSchema = z.enum(["high", "medium", "low", "unrated"]);

export const planSchema = z.object({
  event_id: z.string(),
  stage: z.string().nullish(),
  hour: z.number().nullish(),
  created_utc: z.string().nullish(),
  sites: z.array(
    z.object({
      id: z.number().int(),
      x: z.number(),
      y: z.number(),
      lat: z.number().nullish(),
      lon: z.number().nullish(),
      risk: z.number().nullish(),
      single_gain: z.number().nullish(),
      reason: z.string().nullish(),
      backups: z.array(latLon).nullish(),
    }),
  ),
  moves: z.array(move).nullish(),
  objective: z.number().nullish(),
  exact_rank: z.number().int().nullish(),
  quantum_agreed: z.boolean().nullish(),
  p_opt_per_shot: z.number().nullish(),
  expected_error_km: z.number().nullish(),
  expert_rule_error_km: z.number().nullish(),
  confidence: confidenceSchema.nullish(),
  feasibility_checked: z.boolean().nullish(),
});

export const memorySchema = z.object({
  angles: z.array(
    z.object({
      key: z.string(),
      sensors: z.number().int().nullish(),
      candidates: z.number().int().nullish(),
      layers: z.number().int().nullish(),
      count: z.number().int().nullish(),
      median: z.array(z.number()),
    }),
  ),
  model_weights: z.array(z.object({ name: z.string(), weight: z.number() })),
  track_record: z.array(
    z.object({
      event_id: z.string(),
      hour: z.number().nullish(),
      stage: z.string().nullish(),
      predicted_score: z.number().nullish(),
      realised_score: z.number().nullish(),
      error: z.number().nullish(),
    }),
  ),
  confidence: confidenceSchema.nullish(),
  sequences: z.number().int().nullish(),
});

export const noiseSchema = z.object({
  instance: z
    .object({
      n: z.number().int(),
      k: z.number().int(),
      layers: z.number().int().nullish(),
      event_id: z.string().nullish(),
    })
    .nullish(),
  points: z.array(
    z.object({ gate_error: z.number(), p_best: z.number(), valid: z.number().nullish() }),
  ),
  uniform_p_best: z.number(),
  note: z.string().nullish(),
});

// ---- Bodies accepted by this console's own route handlers ----

const startQaoaSchema = z.strictObject({
  kind: z.literal("qaoa"),
  reps: z.number().int().min(LIMITS.reps.min).max(LIMITS.reps.max),
  seed: z.number().int().min(LIMITS.seed.min).max(LIMITS.seed.max),
  shots: z.number().int().min(LIMITS.shots.min).max(LIMITS.shots.max),
  lam: z.number().min(LIMITS.lam.min).max(LIMITS.lam.max),
});

const startSequenceSchema = z.strictObject({
  kind: z.literal("sequence"),
  hours: z.number().int().min(SEQUENCE_LIMITS.hours.min).max(SEQUENCE_LIMITS.hours.max).optional(),
  step_hours: z
    .number()
    .int()
    .min(SEQUENCE_LIMITS.step_hours.min)
    .max(SEQUENCE_LIMITS.step_hours.max)
    .optional(),
});

/** Body of "start a job": a QAOA run or a replay of an earthquake (sequence). */
export const startJobSchema = z.discriminatedUnion("kind", [startQaoaSchema, startSequenceSchema]);

export type Health = z.infer<typeof healthSchema>;
export type EventSummary = z.infer<typeof eventSchema>;
export type Events = z.infer<typeof eventsSchema>;
export type Instance = z.infer<typeof instanceSchema>;
export type Scoring = z.infer<typeof scoringSchema>;
export type Baselines = z.infer<typeof baselinesSchema>;
export type Job = z.infer<typeof jobSchema>;
export type AnyJob = z.infer<typeof anyJobSchema>;
export type JobResult = z.infer<typeof jobResultSchema>;
export type Jobs = z.infer<typeof jobsSchema>;
export type SystemInfo = z.infer<typeof systemSchema>;
export type StartJob = z.infer<typeof startJobSchema>;
export type Settings = z.infer<typeof settingsSchema>;
export type Feed = z.infer<typeof feedSchema>;
export type FeedQuake = Feed["quakes"][number];
export type Sequence = z.infer<typeof sequenceSchema>;
export type SequenceStep = z.infer<typeof sequenceStepSchema>;
export type Plan = z.infer<typeof planSchema>;
export type Memory = z.infer<typeof memorySchema>;
export type Noise = z.infer<typeof noiseSchema>;
