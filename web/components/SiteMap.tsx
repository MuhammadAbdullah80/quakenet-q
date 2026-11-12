import type { CSSProperties } from "react";
import { Expand } from "@/components/Expand";
import type { Instance } from "@/lib/schemas";
import { fmt } from "@/lib/format";

// Plain SVG map in the event's local km grid (x east, y north). No map tiles.
// Works in both server and client components (no hooks, no browser APIs).

/** What the map needs. An Instance fits; so does a sequence step (risk may be unknown). */
export type MapData = Pick<
  Instance,
  "mainshock" | "design_events" | "valid_events" | "stations"
> & {
  /** Picks the relief image when one exists for this event's local grid. */
  event_id?: string;
  candidates: { id: number; x: number; y: number; risk?: number | null }[];
};

type Props = {
  instance: MapData;
  /** Sites to ring as "chosen" (solid blue ring). */
  chosen?: readonly number[];
  chosenLabel?: string;
  /** A second set to ring (dashed green ring), for example the exact optimum. */
  secondary?: readonly number[];
  secondaryLabel?: string;
  title: string;
  /** Legend text for the filled dots (default: aftershocks used to plan). */
  designLabel?: string;
  /** Legend text for the open dots (default: later aftershocks). */
  validLabel?: string;
  /** For maps that change step by step: no entrance sequence, new dots pop in at once. */
  live?: boolean;
  /** Sensor moves to draw as arrows from the old site to the new one. */
  moves?: readonly { from: number; to: number }[];
  /** Changing this replays the chosen rings' draw, for example on each replay step. */
  ringKey?: string | number;
};

// Real shaded relief drawn in the page palette (scripts/build_web_assets.py). Square, north up,
// covering -extent..+extent km of the event's local grid on both axes.
const RELIEF: Record<string, { href: string; extent: number }> = {
  ridgecrest2019: { href: "/relief/ridgecrest-900.webp", extent: 64 },
};

const NEUTRAL = { fill: "#dde3df", text: "#10291a" };

// Access risk, low to high, in five steps from pale sand to rust: one warm hue family, so lime
// stays free for chosen sites. Steps rather than a smooth ramp, because a smooth ramp passes a
// middle tone where neither ink nor white labels reach 4.5:1; every step here is above 5.5:1.
const RISK_STEPS: { fill: string; text: string }[] = [
  { fill: "#f4ead6", text: "#10291a" },
  { fill: "#e6c79a", text: "#10291a" },
  { fill: "#d49a58", text: "#10291a" },
  { fill: "#9e5530", text: "#ffffff" },
  { fill: "#6f2a14", text: "#ffffff" },
];

function riskColour(t: number): { fill: string; text: string } {
  const clamped = Math.min(1, Math.max(0, t));
  return RISK_STEPS[Math.min(RISK_STEPS.length - 1, Math.floor(clamped * RISK_STEPS.length))];
}

function niceStep(span: number): number {
  const rough = span / 6;
  const power = 10 ** Math.floor(Math.log10(rough));
  const unit = rough / power;
  return (unit < 1.5 ? 1 : unit < 3.5 ? 2 : unit < 7.5 ? 5 : 10) * power;
}

function star(cx: number, cy: number, outer: number): string {
  const points: string[] = [];
  for (let i = 0; i < 10; i += 1) {
    const r = i % 2 === 0 ? outer : outer * 0.42;
    const a = -Math.PI / 2 + (i * Math.PI) / 5;
    points.push(`${(cx + r * Math.cos(a)).toFixed(3)},${(cy + r * Math.sin(a)).toFixed(3)}`);
  }
  return points.join(" ");
}

function triangle(cx: number, cy: number, r: number): string {
  return `${cx},${cy - r} ${cx - r * 0.9},${cy + r * 0.75} ${cx + r * 0.9},${cy + r * 0.75}`;
}

export function SiteMap({
  instance,
  chosen = [],
  chosenLabel = "Chosen site",
  secondary = [],
  secondaryLabel = "Exact optimum",
  title,
  designLabel = "Aftershock used to plan",
  validLabel = "Later aftershock",
  live = false,
  moves = [],
  ringKey = 0,
}: Props) {
  const xs = [
    instance.mainshock.x,
    ...instance.design_events.map((e) => e[0]),
    ...instance.valid_events.map((e) => e[0]),
    // Live maps frame the activity; far stations are clipped at the edge.
    ...(live ? [] : instance.stations.map((s) => s.x)),
    ...instance.candidates.map((c) => c.x),
  ];
  const ys = [
    instance.mainshock.y,
    ...instance.design_events.map((e) => e[1]),
    ...instance.valid_events.map((e) => e[1]),
    ...(live ? [] : instance.stations.map((s) => s.y)),
    ...instance.candidates.map((c) => c.y),
  ];
  const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 1);
  const pad = span * 0.14;
  const cx = (Math.max(...xs) + Math.min(...xs)) / 2;
  const cy = (Math.max(...ys) + Math.min(...ys)) / 2;
  const half = span / 2 + pad;
  const minX = cx - half;
  const maxX = cx + half;
  const minY = cy - half;
  const maxY = cy + half;
  const size = 2 * half;
  const u = size / 100; // 1% of the map width, in km

  // SVG y grows downward; north must point up, so y is negated.
  const X = (x: number) => x;
  const Y = (y: number) => -y;

  const step = niceStep(size);
  const ticksX: number[] = [];
  for (let v = Math.ceil(minX / step) * step; v <= maxX; v += step) ticksX.push(v);
  const ticksY: number[] = [];
  for (let v = Math.ceil(minY / step) * step; v <= maxY; v += step) ticksY.push(v);

  const risks = instance.candidates
    .map((c) => c.risk)
    .filter((r): r is number => typeof r === "number");
  const hasRisk = risks.length > 0;
  const riskMin = hasRisk ? Math.min(...risks) : 0;
  const riskMax = hasRisk ? Math.max(...risks) : 0;
  const riskT = (risk: number) =>
    riskMax > riskMin ? (risk - riskMin) / (riskMax - riskMin) : 0.5;
  const fillFor = (risk: number | null | undefined) =>
    typeof risk === "number" ? riskColour(riskT(risk)) : NEUTRAL;

  const nDesign = Math.max(1, instance.design_events.length);
  const nValid = Math.max(1, instance.valid_events.length);
  const chosenSet = new Set(chosen);
  const secondarySet = new Set(secondary);
  const showSecondary = secondary.length > 0;
  const showChosen = chosen.length > 0;

  const description =
    `${title}. Local grid in kilometres, north up. ` +
    `${instance.candidates.length} candidate sites, ${instance.stations.length} permanent stations, ` +
    `Aftershocks: ${instance.design_events.length} marked "${designLabel.toLowerCase()}", ${instance.valid_events.length} marked "${validLabel.toLowerCase()}".` +
    (showChosen ? ` ${chosenLabel}: sites ${[...chosen].join(", ")}.` : "");

  const relief = instance.event_id ? RELIEF[instance.event_id] : undefined;

  const explain = {
    what: `${title}, on a grid in kilometres around the mainshock: x is east, y is north, north is up.`,
    read: [
      "The star is the mainshock; filled dots are aftershocks" +
        (instance.valid_events.length
          ? ", open dots are later ones kept back to test the plan."
          : "."),
      "Triangles are permanent stations that were already recording.",
      hasRisk
        ? "Numbered circles are the candidate sites, coloured from pale sand (easy to reach) to rust (risky)."
        : "Numbered circles are the candidate sites.",
      ...(showChosen ? [`Lime rings mark ${chosenLabel.toLowerCase()}s.`] : []),
      ...(moves.length ? ["Arrows show a sensor moving from one site to another."] : []),
      "Hover a mark to see its name and value.",
    ],
  };

  return (
    <Expand title={title} explain={explain}>
      <figure className="map-figure">
        <svg
          className={live ? "map-svg is-live" : "map-svg"}
          viewBox={`${minX} ${-maxY} ${size} ${size}`}
          role="img"
          aria-label={description}
        >
          {relief ? (
            <image
              className="map-relief"
              href={relief.href}
              x={-relief.extent}
              y={-relief.extent}
              width={2 * relief.extent}
              height={2 * relief.extent}
              preserveAspectRatio="none"
            />
          ) : null}
          <g className="map-grid" strokeWidth={u * 0.15}>
            {ticksX.map((v) => (
              <line key={`gx${v}`} x1={X(v)} x2={X(v)} y1={Y(minY)} y2={Y(maxY)} />
            ))}
            {ticksY.map((v) => (
              <line key={`gy${v}`} x1={X(minX)} x2={X(maxX)} y1={Y(v)} y2={Y(v)} />
            ))}
          </g>
          <g className="map-axis-label" fontSize={u * 2.4}>
            {ticksX.map((v) => (
              <text key={`tx${v}`} x={X(v) + u * 0.6} y={Y(minY) - u}>
                {v} km
              </text>
            ))}
            {ticksY.map((v) => (
              <text key={`ty${v}`} x={X(minX) + u * 0.6} y={Y(v) - u * 0.6}>
                {v} km
              </text>
            ))}
            <text x={X(maxX) - u * 5} y={Y(maxY) + u * 4} fontWeight="700">
              N ↑
            </text>
          </g>

          <g className="map-design">
            {instance.design_events.map((e, i) => (
              <circle
                key={i}
                cx={X(e[0])}
                cy={Y(e[1])}
                r={u * 0.6}
                style={{ "--i": (i / nDesign).toFixed(3) } as CSSProperties}
              />
            ))}
          </g>
          <g className="map-valid" strokeWidth={u * 0.3}>
            {instance.valid_events.map((e, i) => (
              <circle
                key={i}
                cx={X(e[0])}
                cy={Y(e[1])}
                r={u * 0.75}
                style={{ "--i": (i / nValid).toFixed(3) } as CSSProperties}
              />
            ))}
          </g>

          <g>
            {instance.stations.map((s) => (
              <g key={s.name}>
                <polygon
                  className="map-station"
                  strokeWidth={u * 0.3}
                  points={triangle(X(s.x), Y(s.y), u * 2)}
                >
                  <title>{`Permanent station ${s.name}`}</title>
                </polygon>
                <text
                  className="map-station-label"
                  x={X(s.x) + u * 2.6}
                  y={Y(s.y) + u}
                  fontSize={u * 2.6}
                  fontWeight="600"
                >
                  {s.name}
                </text>
              </g>
            ))}
          </g>

          <polygon
            className="map-mainshock"
            strokeWidth={u * 0.3}
            points={star(X(instance.mainshock.x), Y(instance.mainshock.y), u * 3)}
          >
            <title>{`Mainshock, depth ${fmt(instance.mainshock.depth, 1)} km`}</title>
          </polygon>

          {moves.length > 0 ? (
            <g className="map-moves" key={`moves-${ringKey}`}>
              <defs>
                <marker
                  id="map-arrow"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="5"
                  markerHeight="5"
                  orient="auto-start-reverse"
                >
                  <path d="M0,0 L10,5 L0,10 z" className="map-move-head" />
                </marker>
              </defs>
              {moves.map((m) => {
                const a = instance.candidates.find((c) => c.id === m.from);
                const b = instance.candidates.find((c) => c.id === m.to);
                if (!a || !b) return null;
                // Stop short of both circles so the arrow reads as "from here to there".
                const dx = X(b.x) - X(a.x);
                const dy = Y(b.y) - Y(a.y);
                const len = Math.hypot(dx, dy) || 1;
                const pad = u * 4.6;
                return (
                  <path
                    key={`${m.from}-${m.to}`}
                    className="map-move"
                    d={`M${X(a.x) + (dx / len) * pad},${Y(a.y) + (dy / len) * pad} L${X(b.x) - (dx / len) * pad},${Y(b.y) - (dy / len) * pad}`}
                    strokeWidth={u * 0.7}
                    markerEnd="url(#map-arrow)"
                    pathLength={1}
                  />
                );
              })}
            </g>
          ) : null}
          <g>
            {instance.candidates.map((c, k) => {
              const colour = fillFor(c.risk);
              return (
                <g key={c.id} className="map-site" style={{ "--k": k } as CSSProperties}>
                  {secondarySet.has(c.id) ? (
                    <circle
                      className="map-secondary"
                      cx={X(c.x)}
                      cy={Y(c.y)}
                      r={u * 5.2}
                      strokeWidth={u * 0.7}
                      strokeDasharray={`${u * 1.4} ${u}`}
                    />
                  ) : null}
                  {chosenSet.has(c.id) ? (
                    <g key={`ring-${ringKey}`}>
                      <circle
                        className="map-chosen-halo"
                        cx={X(c.x)}
                        cy={Y(c.y)}
                        r={u * 4.1}
                        strokeWidth={u * 1.7}
                      />
                      <circle
                        className="map-chosen"
                        cx={X(c.x)}
                        cy={Y(c.y)}
                        r={u * 4.1}
                        strokeWidth={u * 1}
                        pathLength={1}
                      />
                      <circle
                        className="map-chosen-pulse"
                        cx={X(c.x)}
                        cy={Y(c.y)}
                        r={u * 4.1}
                        strokeWidth={u * 0.6}
                      />
                    </g>
                  ) : null}
                  <circle
                    className="map-candidate"
                    cx={X(c.x)}
                    cy={Y(c.y)}
                    r={u * 2.7}
                    fill={colour.fill}
                    strokeWidth={u * 0.3}
                  >
                    <title>
                      {typeof c.risk === "number"
                        ? `Candidate site ${c.id}, risk ${fmt(c.risk)}`
                        : `Candidate site ${c.id}`}
                    </title>
                  </circle>
                  <text
                    x={X(c.x)}
                    y={Y(c.y)}
                    fontSize={u * 3.2}
                    fontWeight="700"
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill={colour.text}
                    pointerEvents="none"
                  >
                    {c.id}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        <figcaption>
          <ul className="map-legend">
            <li>
              <svg viewBox="0 0 20 20" aria-hidden="true">
                <polygon className="map-mainshock" strokeWidth="1" points={star(10, 10, 9)} />
              </svg>
              Mainshock
            </li>
            {instance.design_events.length > 0 ? (
              <li>
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <circle className="map-design" cx="10" cy="10" r="4" />
                </svg>
                {designLabel}
              </li>
            ) : null}
            {instance.valid_events.length > 0 ? (
              <li>
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <circle className="map-valid" cx="10" cy="10" r="5" strokeWidth="2" />
                </svg>
                {validLabel}
              </li>
            ) : null}
            <li>
              <svg viewBox="0 0 20 20" aria-hidden="true">
                <polygon className="map-station" strokeWidth="1" points={triangle(10, 10, 8)} />
              </svg>
              Permanent station
            </li>
            {hasRisk ? (
              <li className="risk-scale">
                <span>Candidate access risk</span>
                <span className="risk-steps" aria-hidden="true">
                  {RISK_STEPS.map((step) => (
                    <span key={step.fill} style={{ background: step.fill }} />
                  ))}
                </span>
                <span className="risk-ends">
                  {fmt(riskMin)} lowest to {fmt(riskMax)} highest
                </span>
              </li>
            ) : (
              <li>
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <circle className="map-candidate" cx="10" cy="10" r="8" fill={NEUTRAL.fill} />
                </svg>
                Candidate site (number inside)
              </li>
            )}
            {showChosen ? (
              <li>
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <circle className="map-chosen-halo" cx="10" cy="10" r="7" strokeWidth="5" />
                  <circle className="map-chosen" cx="10" cy="10" r="7" strokeWidth="3" />
                </svg>
                {chosenLabel}
              </li>
            ) : null}
            {showSecondary ? (
              <li>
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <circle
                    className="map-secondary"
                    cx="10"
                    cy="10"
                    r="8"
                    strokeWidth="2"
                    strokeDasharray="4 3"
                  />
                </svg>
                {secondaryLabel}
              </li>
            ) : null}
          </ul>
        </figcaption>
      </figure>
    </Expand>
  );
}
