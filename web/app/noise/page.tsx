import type { Metadata } from "next";
import { Suspense } from "react";
import { Empty, Loading, OfflineBanner, Problem } from "@/components/States";
import { loadNoise } from "@/lib/data";
import { fmt, fmtPercent } from "@/lib/format";
import type { Noise } from "@/lib/schemas";
import { Expand } from "@/components/Expand";

export const metadata: Metadata = { title: "Noise study" };

export default function NoisePage() {
  return (
    <>
      <h1>Noise study</h1>
      <p className="lede">
        How the quantum circuit holds up when its gates make errors. The same kind of circuit is run
        on a smaller version of the problem in a simulator that adds random gate errors.
      </p>
      <div className="notice notice-warn">
        <p className="notice-title">This is a simulation, not a run on a quantum computer.</p>
        <p>
          The gate errors are modelled on a classical computer. It is a stand-in for a hardware run,
          not a hardware result.
        </p>
      </div>
      <Suspense fallback={<Loading label="Loading the noise study" />}>
        <NoiseContent />
      </Suspense>
    </>
  );
}

async function NoiseContent() {
  const noise = await loadNoise();
  const data = noise.state === "live" || noise.state === "snapshot" ? noise.data : null;
  const points = data ? [...data.points].sort((a, b) => a.gate_error - b.gate_error) : [];
  return (
    <>
      <OfflineBanner results={[noise]} />
      <Problem result={noise} what="the noise study" />
      {data ? (
        <>
          <details className="more">
            <summary>About this simulation</summary>
            <dl className="facts">
              <div>
                <dt>Problem size</dt>
                <dd>
                  {data.instance ? `${data.instance.n} sites, choose ${data.instance.k}` : "n/a"}
                </dd>
              </div>
              <div>
                <dt>Circuit layers</dt>
                <dd>{data.instance?.layers ?? "n/a"}</dd>
              </div>
              <div>
                <dt>Earthquake</dt>
                <dd>{data.instance?.event_id ?? "n/a"}</dd>
              </div>
              <div>
                <dt>Chance for a random pick</dt>
                <dd>{fmtPercent(data.uniform_p_best, 2)}</dd>
              </div>
            </dl>
          </details>
          {data.note ? <p className="small muted">Backend note: {data.note}</p> : null}
          {points.length === 0 ? (
            <Empty>The noise study has no points yet.</Empty>
          ) : (
            <div className="columns">
              <NoiseChart points={points} uniform={data.uniform_p_best} />
              <NoiseTable points={points} uniform={data.uniform_p_best} />
            </div>
          )}
        </>
      ) : null}
    </>
  );
}

type Point = Noise["points"][number];

function NoiseChart({ points, uniform }: { points: Point[]; uniform: number }) {
  const W = 560;
  const H = 340;
  const m = { top: 20, right: 24, bottom: 52, left: 64 };
  const iw = W - m.left - m.right;
  const ih = H - m.top - m.bottom;
  // Gate errors span 0 to 1% in roughly log steps, so a linear axis piles the small ones on top
  // of each other. log10(1 + v / 0.0001) keeps 0 at the origin and spreads the rest evenly.
  const xs = (v: number) => Math.log10(1 + v / 0.0001);
  const xMax = Math.max(...points.map((p) => xs(p.gate_error)), 0) || 1;
  const yTop = Math.max(...points.map((p) => p.p_best), uniform, 0.01);
  const yStep = yTop > 0.5 ? 0.1 : yTop > 0.2 ? 0.05 : yTop > 0.1 ? 0.02 : 0.01;
  const yMax = Math.ceil((yTop * 1.05) / yStep) * yStep;
  const x = (v: number) => m.left + (xs(v) / xMax) * iw;
  const y = (v: number) => m.top + ih - (v / yMax) * ih;
  const yTicks: number[] = [];
  for (let v = 0; v <= yMax + 1e-9; v += yStep) yTicks.push(Number(v.toFixed(6)));
  const xTicks = points.map((p) => p.gate_error);
  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(p.gate_error)},${y(p.p_best)}`)
    .join(" ");
  const first = points[0];
  const last = points[points.length - 1];
  const label =
    `Line chart: chance that one measurement gives the best network, against gate error. ` +
    `It goes from ${fmtPercent(first.p_best, 1)} at gate error ${fmtPercent(first.gate_error, 2)} ` +
    `to ${fmtPercent(last.p_best, 1)} at gate error ${fmtPercent(last.gate_error, 2)}. ` +
    `A random pick gives ${fmtPercent(uniform, 2)}. The table next to the chart has every value.`;

  return (
    <Expand
      title="Success against gate error (simulation)"
      explain={{
        what: "What happens to the circuit when its gates make mistakes, in a simulation on a smaller version of the problem.",
        read: [
          "Left to right, the gates make more errors. Higher on the chart is better.",
          "The solid line is the chance one measurement gives the best network.",
          "The dashed line is a random pick. While the solid line stays above it, the circuit still helps.",
          "This is a simulation on a classical computer, not a run on quantum hardware.",
        ],
      }}
    >
      <figure className="chart-figure">
        <svg className="chart-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
          <g className="chart-grid">
            {yTicks.map((v) => (
              <line key={`gy${v}`} x1={m.left} x2={m.left + iw} y1={y(v)} y2={y(v)} />
            ))}
          </g>
          <g className="chart-axis-label" fontSize="12">
            {yTicks.map((v) => (
              <text
                key={`ty${v}`}
                x={m.left - 8}
                y={y(v)}
                textAnchor="end"
                dominantBaseline="middle"
              >
                {fmtPercent(v, 0)}
              </text>
            ))}
            {xTicks.map((v) => (
              <text key={`tx${v}`} x={x(v)} y={m.top + ih + 18} textAnchor="middle">
                {fmtPercent(v, v > 0 && v < 0.001 ? 2 : 1)}
              </text>
            ))}
            <text x={m.left + iw / 2} y={H - 8} textAnchor="middle">
              Gate error, chance a gate goes wrong (log scale)
            </text>
            <text
              x={14}
              y={m.top + ih / 2}
              textAnchor="middle"
              transform={`rotate(-90 14 ${m.top + ih / 2})`}
            >
              Chance of the best network
            </text>
          </g>
          <line className="chart-axis" x1={m.left} x2={m.left + iw} y1={y(0)} y2={y(0)} />
          <line
            className="chart-reference"
            x1={m.left}
            x2={m.left + iw}
            y1={y(uniform)}
            y2={y(uniform)}
            strokeDasharray="6 4"
          />
          <text
            className="chart-reference-label"
            x={m.left + iw}
            y={y(uniform) - 6}
            textAnchor="end"
            fontSize="12"
          >
            Random pick ({fmtPercent(uniform, 2)})
          </text>
          <path className="chart-line" d={path} pathLength={1} />
          {points.map((p) => (
            <circle
              key={p.gate_error}
              className="chart-point"
              cx={x(p.gate_error)}
              cy={y(p.p_best)}
              r={5}
            >
              <title>{`Gate error ${fmtPercent(p.gate_error, 2)}: best network ${fmtPercent(p.p_best, 1)}`}</title>
            </circle>
          ))}
        </svg>
        <figcaption className="small muted">
          Solid line: simulated circuit with noise. Dashed line: what a random pick of a network
          would give.
        </figcaption>
      </figure>
    </Expand>
  );
}

function NoiseTable({ points, uniform }: { points: Point[]; uniform: number }) {
  return (
    <details className="more">
      <summary>See the numbers: every gate error</summary>
      <div className="table-wrap">
        <table>
          <caption>Simulated results by gate error</caption>
          <thead>
            <tr>
              <th scope="col" className="num">
                Gate error
              </th>
              <th scope="col" className="num">
                Chance of the best network
              </th>
              <th scope="col" className="num">
                Compared with random
              </th>
              <th scope="col" className="num">
                Valid networks measured
              </th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.gate_error}>
                <th scope="row" className="num">
                  {fmtPercent(p.gate_error, 2)}
                </th>
                <td className="num">{fmtPercent(p.p_best, 1)}</td>
                <td className="num">
                  {uniform > 0 ? `${fmt(p.p_best / uniform, 1)} times` : "n/a"}
                </td>
                <td className="num">
                  {typeof p.valid === "number" ? fmtPercent(p.valid, 0) : "n/a"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
