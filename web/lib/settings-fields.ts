// The settings a scientist can edit (docs/API.md, version 2: GET/PUT /settings).
// No server imports, so the settings form in the browser can use it too.
import { z } from "zod";

export type NumberSetting = {
  key: string;
  label: string;
  help: string;
  integer: boolean;
  /** Allowed range from docs/API.md, used when the backend sends no `limits`. */
  range: readonly [number, number];
};

export type BooleanSetting = { key: string; label: string; help: string };

export const NUMBER_SETTINGS: readonly NumberSetting[] = [
  {
    key: "trigger_magnitude",
    label: "Trigger magnitude",
    help: "The agent starts on earthquakes of this magnitude or larger.",
    integer: false,
    range: [3.0, 9.0],
  },
  {
    key: "station_radius_km",
    label: "Station radius (km)",
    help: "An earthquake is used only if a permanent station lies within this distance of it.",
    integer: false,
    range: [20, 300],
  },
  {
    key: "sensors",
    label: "Sensors to place",
    help: "How many portable seismometers the agent places.",
    integer: true,
    range: [2, 4],
  },
  {
    key: "candidates",
    label: "Candidate sites",
    help: "How many possible sites the agent chooses from.",
    integer: true,
    range: [8, 10],
  },
  {
    key: "risk_weight",
    label: "Risk weight (lam)",
    help: "How strongly the access risk of a site counts against it.",
    integer: false,
    range: [0, 1000],
  },
  {
    key: "move_cost",
    label: "Move cost",
    help: "Score a re-plan must gain to move one sensor. Higher means fewer moves.",
    integer: false,
    range: [0, 500],
  },
  {
    key: "monitor_interval_hours",
    label: "Check interval (hours)",
    help: "Hours between two checks for drift.",
    integer: true,
    range: [1, 12],
  },
  {
    key: "monitor_hours",
    label: "Monitoring period (hours)",
    help: "How long the agent keeps watching one earthquake.",
    integer: true,
    range: [6, 168],
  },
  {
    key: "drift_centroid_km",
    label: "Drift: centre shift (km)",
    help: "Re-plan when the centre of the aftershocks has moved this far.",
    integer: false,
    range: [1, 50],
  },
  {
    key: "drift_score_drop",
    label: "Drift: score drop (fraction)",
    help: "Re-plan when the realised score falls by this fraction of the predicted one (0.2 is 20%).",
    integer: false,
    range: [0.05, 0.9],
  },
  {
    key: "min_real_aftershocks",
    label: "Real aftershocks needed",
    help: "With fewer real aftershocks than this, the plan uses simulated ones.",
    integer: true,
    range: [5, 200],
  },
  {
    key: "qaoa_layers",
    label: "Quantum circuit layers",
    help: "How many times the QAOA circuit repeats its two steps.",
    integer: true,
    range: [1, 5],
  },
  {
    key: "shots",
    label: "Measurements (shots)",
    help: "How many times the quantum circuit is measured per plan.",
    integer: true,
    range: [128, 4096],
  },
  {
    key: "max_plans_per_hour",
    label: "Most plans per hour",
    help: "Live mode starts at most this many new earthquakes per hour.",
    integer: true,
    range: [1, 20],
  },
];

export const BOOLEAN_SETTINGS: readonly BooleanSetting[] = [
  {
    key: "hearing_range",
    label: "Model hearing range",
    help: "A station only counts for an aftershock it would hear clearly (signal-to-noise of 5 or more).",
  },
  {
    key: "live_enabled",
    label: "Live mode",
    help: "Start the agent by itself on new earthquakes from the USGS feed at or above the trigger magnitude.",
  },
];

export type SettingLimits = Partial<Record<string, readonly [number, number]>>;

/** Range of one numeric setting: the backend's `limits` if sent, else the documented range. */
export function rangeOf(field: NumberSetting, limits: SettingLimits | null | undefined) {
  const fromBackend = limits?.[field.key];
  return fromBackend && fromBackend[0] <= fromBackend[1] ? fromBackend : field.range;
}

/**
 * Schema for a settings update: any non-empty subset of the editable keys,
 * each within its range. Unknown keys are refused.
 */
export function settingsUpdateSchema(limits?: SettingLimits | null) {
  const shape: Record<string, z.ZodOptional<z.ZodNumber | z.ZodBoolean>> = {};
  for (const field of NUMBER_SETTINGS) {
    const [min, max] = rangeOf(field, limits);
    let schema = z.number().min(min).max(max);
    if (field.integer) schema = schema.int();
    shape[field.key] = schema.optional();
  }
  for (const field of BOOLEAN_SETTINGS) shape[field.key] = z.boolean().optional();
  return z
    .strictObject(shape)
    .refine((value) => Object.keys(value).length > 0, { message: "Send at least one setting." });
}
