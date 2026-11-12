import type { Instance } from "@/lib/schemas";
import { fmt } from "@/lib/format";

// Plain SVG map in the event's local km grid (x east, y north). No map tiles.
// Works in both server and client components (no hooks, no browser APIs).

type Props = {
  instance: Instance;
  /** Sites to ring as "chosen" (solid blue ring). */
  chosen?: readonly number[];
  chosenLabel?: string;
  /** A second set to ring (dashed green ring), for example the exact optimum. */
  secondary?: readonly number[];
  secondaryLabel?: string;
  title: string;
};

const RAMP: [number, number, number][] = [
  [255, 243, 214],
  [240, 138, 60],
  [143, 29, 29],
];

function riskColour(t: number): { fill: string; text: string } {
  const clamped = Math.min(1, Math.max(0, t));
  const scaled = clamped * (RAMP.length - 1);
  const i = Math.min(RAMP.length - 2, Math.floor(scaled));
  const f = scaled - i;
  const rgb = RAMP[i].map((c, k) => Math.round(c + (RAMP[i + 1][k] - c) * f));
  const luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255;
  return { fill: `rgb(${rgb.join(",")})`, text: luminance > 0.55 ? "#16202b" : "#ffffff" };
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
}: Props) {
  const xs = [
    instance.mainshock.x,
    ...instance.design_events.map((e) => e[0]),
    ...instance.valid_events.map((e) => e[0]),
    ...instance.stations.map((s) => s.x),
    ...instance.candidates.map((c) => c.x),
  ];
  const ys = [
    instance.mainshock.y,
    ...instance.design_events.map((e) => e[1]),
    ...instance.valid_events.map((e) => e[1]),
    ...instance.stations.map((s) => s.y),
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

  const risks = instance.candidates.map((c) => c.risk);
  const riskMin = Math.min(...risks);
  const riskMax = Math.max(...risks);
  const riskT = (risk: number) => (riskMax > riskMin ? (risk - riskMin) / (riskMax - riskMin) : 0.5);

  const chosenSet = new Set(chosen);
  const secondarySet = new Set(secondary);
  const showSecondary = secondary.length > 0;
  const showChosen = chosen.length > 0;

  const description =
    `${title}. Local grid in kilometres, north up. ` +
    `${instance.candidates.length} candidate sites, ${instance.stations.length} permanent stations, ` +
    `${instance.design_events.length} aftershocks used to plan, ${instance.valid_events.length} later aftershocks.` +
    (showChosen ? ` ${chosenLabel}: sites ${[...chosen].join(", ")}.` : "");

  const low = riskColour(0);
  const high = riskColour(1);

  return (
    <figure className="map-figure">
      <svg
        className="map-svg"
        viewBox={`${minX} ${-maxY} ${size} ${size}`}
        role="img"
        aria-label={description}
      >
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
            <circle key={i} cx={X(e[0])} cy={Y(e[1])} r={u * 0.6} />
          ))}
        </g>
        <g className="map-valid" strokeWidth={u * 0.3}>
          {instance.valid_events.map((e, i) => (
            <circle key={i} cx={X(e[0])} cy={Y(e[1])} r={u * 0.75} />
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

        <g>
          {instance.candidates.map((c) => {
            const colour = riskColour(riskT(c.risk));
            return (
              <g key={c.id}>
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
                  <circle
                    className="map-chosen"
                    cx={X(c.x)}
                    cy={Y(c.y)}
                    r={u * 4}
                    strokeWidth={u * 0.9}
                  />
                ) : null}
                <circle
                  className="map-candidate"
                  cx={X(c.x)}
                  cy={Y(c.y)}
                  r={u * 2.7}
                  fill={colour.fill}
                  strokeWidth={u * 0.3}
                >
                  <title>{`Candidate site ${c.id}, risk ${fmt(c.risk)}`}</title>
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
          <li>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <circle className="map-design" cx="10" cy="10" r="4" />
            </svg>
            Aftershock used to plan
          </li>
          <li>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <circle className="map-valid" cx="10" cy="10" r="5" strokeWidth="2" />
            </svg>
            Later aftershock
          </li>
          <li>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <polygon className="map-station" strokeWidth="1" points={triangle(10, 10, 8)} />
            </svg>
            Permanent station
          </li>
          <li>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <circle className="map-candidate" cx="10" cy="10" r="8" fill={low.fill} />
            </svg>
            Candidate, lowest risk ({fmt(riskMin)})
          </li>
          <li>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <circle className="map-candidate" cx="10" cy="10" r="8" fill={high.fill} />
            </svg>
            Candidate, highest risk ({fmt(riskMax)})
          </li>
          {showChosen ? (
            <li>
              <svg viewBox="0 0 20 20" aria-hidden="true">
                <circle className="map-chosen" cx="10" cy="10" r="7.5" strokeWidth="3" />
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
  );
}
