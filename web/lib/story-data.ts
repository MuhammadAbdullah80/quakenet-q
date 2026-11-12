// The landing page's data: the Ridgecrest case written by scripts/build_web_assets.py.
// Every number on the landing page comes from here; none is typed in by hand.
import story from "@/data/story.json";

export type Quake = [x: number, y: number, depth: number, magnitude: number, hours: number];

export const STORY = story as unknown as {
  event: {
    name: string;
    magnitude: number;
    lat: number;
    lon: number;
    depth_km: number;
    time_ms: number;
  };
  grid: { lat0: number; lon0: number; km_per_deg: number; extent_km: number };
  mainshock: [number, number, number];
  early: Quake[];
  later: Quake[];
  stations: { name: string; x: number; y: number }[];
  candidates: { id: number; x: number; y: number; risk: number; nearest_km: number }[];
  pick: number[];
  expert: number[];
  numbers: {
    decision_hours: number;
    early: number;
    later: number;
    stations: number;
    candidates: number;
    sensors: number;
    networks: number;
    runs: number;
    runs_exact: number;
    error_none_km: number;
    error_expert_km: number;
    error_pick_km: number;
  };
  sorted_errors: number[];
  pick_position: number;
  expert_position: number;
};

const n = STORY.numbers;

/** "35.770° N 117.599° W" */
export function fmtLatLonDeg(lat: number, lon: number): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(3)}° ${ns} ${Math.abs(lon).toFixed(3)}° ${ew}`;
}

/** "2019-07-06 03:19 UTC" */
export function fmtUtcMinute(ms: number): string {
  return new Date(ms).toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

/** "1, 3, 4 and 7" */
export function listAnd(items: readonly (string | number)[]): string {
  const parts = items.map(String);
  return parts.length < 2 ? parts.join("") : `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}`;
}

const WORDS = [
  "zero",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
  "eleven",
  "twelve",
];
const word = (k: number) => WORDS[k] ?? String(k);
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export const COPY = {
  headline: "Where do the sensors go?",
  caption: `Real aftershock data from the U.S. Geological Survey. Quantum circuit simulated in Qiskit. Every answer checked against all ${n.networks} options.`,
  label: [
    `M ${STORY.event.magnitude.toFixed(1)} ${STORY.event.name.split(",")[0]}`,
    fmtLatLonDeg(STORY.event.lat, STORY.event.lon),
    fmtUtcMinute(STORY.event.time_ms),
  ],
  fly: "Where the sensors go decides how sharply aftershocks can be located.",
  landscape:
    `${cap(word(n.decision_hours))} hours after the magnitude ${STORY.event.magnitude.toFixed(1)} mainshock near ` +
    `${STORY.event.name.split(",")[0]}, ${n.early} aftershocks had been recorded. The ${n.stations} permanent stations sat ` +
    `too far apart to locate them sharply. A response team had ${n.sensors} portable sensors and ${n.candidates} places to put them.`,
  station: `The circuit chose sites ${listAnd(STORY.pick)}. An exact search of all ${n.networks} options agrees.`,
  cardTitle: "Location error on later aftershocks",
  cardNote: `${n.later} aftershocks the planner never saw`,
  footer: "Proof of concept. The quantum circuit runs on a simulator and claims no speedup.",
};

export const PIPELINE = [
  { href: "/events", label: "Real aftershocks and stations" },
  { href: "/candidates", label: `${cap(word(n.candidates))} candidate sites` },
  { href: "/scoring", label: `A score for all ${n.networks} networks` },
  { href: "/quantum", label: `A quantum circuit picks ${word(n.sensors)}` },
  { href: "/self-check", label: "Exact search checks the pick" },
] as const;

export const STATS = [
  { value: String(n.early), label: `aftershocks in the first ${n.decision_hours} hours` },
  { value: String(n.networks), label: "possible networks, all checked" },
  { value: `${n.runs_exact} of ${n.runs}`, label: "quantum runs found the best network" },
  { value: `${n.error_pick_km.toFixed(2)} km`, label: "mean location error with the chosen sites" },
] as const;
