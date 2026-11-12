// Helpers for showing an agent sequence. No server imports: used by the
// Monitor slider in the browser as well as by server pages.
import type { MapData } from "@/components/SiteMap";
import type { Sequence } from "@/lib/schemas";

/** Map of a sequence showing only the real aftershocks that had happened by `hour`. */
export function sequenceMapData(sequence: Sequence, hour: number): MapData {
  return {
    mainshock: sequence.mainshock,
    stations: sequence.stations,
    candidates: sequence.candidates.map((c) => ({ id: c.id, x: c.x, y: c.y, risk: null })),
    design_events: sequence.aftershocks
      .filter((a) => a[4] <= hour)
      .map((a) => [a[0], a[1], a[2]] as [number, number, number]),
    valid_events: [],
  };
}

export const STAGE_LABEL: Record<string, string> = {
  first_plan: "first plan",
  check: "check, no change",
  replan: "re-plan",
};

export function stageLabel(stage: string | null | undefined): string {
  if (!stage) return "n/a";
  return STAGE_LABEL[stage] ?? stage;
}

export function fmtLatLon(lat: number | null | undefined, lon: number | null | undefined): string {
  if (typeof lat !== "number" || typeof lon !== "number") return "n/a";
  return `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
}
