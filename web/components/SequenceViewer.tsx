"use client";

import { useEffect, useState } from "react";
import { SiteMap } from "@/components/SiteMap";
import { fmt, fmtPercent, fmtSites } from "@/lib/format";
import type { Sequence, SequenceStep } from "@/lib/schemas";
import { sequenceMapData, stageLabel } from "@/lib/sequence";
import { TableFold } from "@/components/TableFold";

// Hour-by-hour view of one sequence. The sequence comes in as props from the
// server page; nothing here talks to the network.

function num(value: number | null | undefined, digits = 1, unit = ""): string {
  return typeof value === "number" ? `${fmt(value, digits)}${unit}` : "n/a";
}

function stageTag(step: SequenceStep) {
  const tone = step.stage === "replan" ? "tag-warn" : step.stage === "first_plan" ? "tag-ok" : "";
  return <span className={`tag ${tone}`}>{stageLabel(step.stage)}</span>;
}

/** Hour-by-hour strip: new aftershocks per step as bars, re-plans and drift marked, a cursor. */
function Timeline({
  steps,
  index,
  onPick,
}: {
  steps: SequenceStep[];
  index: number;
  onPick: (i: number) => void;
}) {
  const h0 = steps[0].hour;
  const h1 = steps[steps.length - 1].hour;
  const span = h1 - h0 || 1;
  const fresh = steps.map((s, i) =>
    Math.max(0, (s.aftershocks_real ?? 0) - (i > 0 ? (steps[i - 1].aftershocks_real ?? 0) : 0)),
  );
  const most = Math.max(1, ...fresh);
  const W = 1000;
  const H = 120;
  const base = 96;
  const x = (h: number) => 12 + ((h - h0) / span) * (W - 24);
  const bw = Math.max(3, Math.min(26, (W - 24) / steps.length - 4));
  const replans = steps.filter((s) => s.stage === "replan").length;

  return (
    <figure className="timeline">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`New real aftershocks at each step, from hour ${fmt(h0, 0)} to ${fmt(h1, 0)}. ${replans} re-plans. Step ${index + 1} is selected.`}
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const hx = h0 + ((((e.clientX - r.left) / r.width) * W - 12) / (W - 24)) * span;
          let best = 0;
          steps.forEach((s, i) => {
            if (Math.abs(s.hour - hx) < Math.abs(steps[best].hour - hx)) best = i;
          });
          onPick(best);
        }}
      >
        <line x1="0" x2={W} y1={base} y2={base} className="tl-base" />
        {steps.map((s, i) => {
          const h = (fresh[i] / most) * 70;
          return (
            <g key={i} className={i <= index ? "tl-step is-past" : "tl-step"}>
              <rect
                x={x(s.hour) - bw / 2}
                y={base - h}
                width={bw}
                height={Math.max(1, h)}
                rx="1.5"
              />
              {s.drift ? (
                <rect
                  className="tl-drift"
                  x={x(s.hour) - bw / 2}
                  y={base + 6}
                  width={bw}
                  height="5"
                />
              ) : null}
              {s.stage === "replan" ? (
                <path
                  className="tl-replan"
                  d={`M${x(s.hour)},${base - h - 16} l6,7 l-6,7 l-6,-7 z`}
                />
              ) : null}
            </g>
          );
        })}
        <line
          className="tl-cursor"
          x1={x(steps[index].hour)}
          x2={x(steps[index].hour)}
          y1="4"
          y2={H - 4}
        />
      </svg>
      <figcaption className="timeline-key">
        <span>
          <i className="k-bar" aria-hidden="true" /> new real aftershocks in each step
        </span>
        <span>
          <i className="k-replan" aria-hidden="true" /> re-plan
        </span>
        <span>
          <i className="k-drift" aria-hidden="true" /> drift detected
        </span>
        <span className="timeline-ends">
          hour {fmt(h0, 0)} to {fmt(h1, 0)}
        </span>
      </figcaption>
    </figure>
  );
}

export function SequenceViewer({ sequence, title }: { sequence: Sequence; title: string }) {
  const steps = sequence.steps;
  const [index, setIndex] = useState(Math.max(0, steps.length - 1));
  const [playing, setPlaying] = useState(false);

  // Play steps forward about once a second; stop at the end.
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setIndex((i) => {
        if (i >= steps.length - 1) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, 1100);
    return () => window.clearInterval(timer);
  }, [playing, steps.length]);

  if (steps.length === 0) {
    return (
      <div className="notice notice-info">
        <p>The sequence has no finished steps yet.</p>
      </div>
    );
  }
  const safeIndex = Math.min(index, steps.length - 1);
  const step = steps[safeIndex];
  const plan = step.plan ?? null;
  const moves = plan?.moves ?? [];
  const movedFrom = moves.map((m) => m.from).filter((id) => !step.sites.includes(id));
  const valueText = `Hour ${fmt(step.hour, 0)}, ${stageLabel(step.stage)}`;
  const prevReal = safeIndex > 0 ? (steps[safeIndex - 1].aftershocks_real ?? 0) : 0;
  const fresh = Math.max(0, (step.aftershocks_real ?? 0) - prevReal);
  const togglePlay = () => {
    if (!playing && safeIndex >= steps.length - 1) setIndex(0);
    setPlaying((p) => !p);
  };

  return (
    <section aria-labelledby="timeline-heading">
      <h2 id="timeline-heading">Hour by hour</h2>
      <div className="player">
        <div className="player-controls">
          <button type="button" className="player-play" onClick={togglePlay} aria-pressed={playing}>
            <span className={playing ? "icon-pause" : "icon-play"} aria-hidden="true" />
            {playing ? "Pause" : safeIndex >= steps.length - 1 ? "Replay from the start" : "Play"}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setPlaying(false);
              setIndex(Math.max(0, safeIndex - 1));
            }}
            disabled={safeIndex === 0}
          >
            Previous step
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setPlaying(false);
              setIndex(Math.min(steps.length - 1, safeIndex + 1));
            }}
            disabled={safeIndex === steps.length - 1}
          >
            Next step
          </button>
          <span className="player-pos" aria-live="polite">
            Step {safeIndex + 1} of {steps.length}: {valueText}
          </span>
        </div>
        <Timeline
          steps={steps}
          index={safeIndex}
          onPick={(i) => {
            setPlaying(false);
            setIndex(i);
          }}
        />
        <label className="visually-hidden" htmlFor="step-slider">
          Step
        </label>
        <input
          id="step-slider"
          className="slider"
          type="range"
          min={0}
          max={steps.length - 1}
          step={1}
          value={safeIndex}
          aria-valuetext={valueText}
          onChange={(e) => {
            setPlaying(false);
            setIndex(Number(e.target.value));
          }}
        />
      </div>

      <div className="columns replay-body">
        <SiteMap
          instance={sequenceMapData(sequence, step.hour)}
          title={`${title} at hour ${fmt(step.hour, 0)}`}
          chosen={step.sites}
          chosenLabel="Sensor in place at this step"
          secondary={movedFrom}
          secondaryLabel="Sensor moved away from here at this step"
          designLabel="Real aftershock by this hour"
          live
          moves={moves}
          ringKey={safeIndex}
        />
        <div>
          {step.drift ? (
            <div className="notice notice-warn">
              <p className="notice-title">Drift detected: the agent re-planned</p>
              <p>{step.drift_reason ?? "No reason given."}</p>
            </div>
          ) : null}
          <dl className="kpis">
            <div>
              <dt>Hour</dt>
              <dd>{fmt(step.hour, 0)}</dd>
              <span className="kpi-note">{stageTag(step)}</span>
            </div>
            <div>
              <dt>Aftershocks so far</dt>
              <dd>{step.aftershocks_real ?? "n/a"}</dd>
              <span className="kpi-note">{fresh} new in this step</span>
            </div>
            <div>
              <dt>Sensor moves</dt>
              <dd>{plan ? moves.length : 0}</dd>
              <span className="kpi-note">
                {moves.length
                  ? moves.map((m) => `${m.from} to ${m.to}`).join(", ")
                  : "sites " + fmtSites(step.sites)}
              </span>
            </div>
          </dl>
          <details className="more">
            <summary>This step in detail</summary>
            <dl className="facts">
              <div>
                <dt>Aftershocks used to plan</dt>
                <dd>
                  {step.aftershocks_used ?? "n/a"}
                  {step.synthetic ? " (simulated: too few real ones yet)" : ""}
                </dd>
              </div>
              <div>
                <dt>Shift of the aftershock centre</dt>
                <dd>{num(step.centroid_shift_km, 1, " km")}</dd>
              </div>
              <div>
                <dt>Predicted score</dt>
                <dd>{num(step.predicted_score)}</dd>
              </div>
              <div>
                <dt>Realised score</dt>
                <dd>{num(step.realised_score)}</dd>
              </div>
              <div>
                <dt>Score drop</dt>
                <dd>
                  {typeof step.score_drop === "number" ? fmtPercent(step.score_drop, 0) : "n/a"}
                </dd>
              </div>
              <div>
                <dt>Sites in place</dt>
                <dd>{fmtSites(step.sites)}</dd>
              </div>
              {plan ? (
                <>
                  <div>
                    <dt>Quantum choice matched the exact optimum</dt>
                    <dd>
                      {typeof plan.quantum_agreed === "boolean"
                        ? plan.quantum_agreed
                          ? "yes"
                          : `no (rank ${plan.exact_rank ?? "n/a"})`
                        : "n/a"}
                    </dd>
                  </div>
                  <div>
                    <dt>Expected location error, plan and expert rule</dt>
                    <dd>
                      {num(plan.expected_error_km, 2, " km")} and{" "}
                      {num(plan.expert_rule_error_km, 2, " km")}
                    </dd>
                  </div>
                </>
              ) : null}
            </dl>
          </details>
        </div>
      </div>

      <TableFold total={steps.length} limit={6} noun="steps">
        <div className="table-wrap">
          <table>
            <caption>All steps ({steps.length}). Re-plans are highlighted.</caption>
            <thead>
              <tr>
                <th scope="col" className="num">
                  Hour
                </th>
                <th scope="col">Stage</th>
                <th scope="col" className="num">
                  Real aftershocks
                </th>
                <th scope="col" className="num">
                  Used to plan
                </th>
                <th scope="col" className="num">
                  Centre shift (km)
                </th>
                <th scope="col" className="num">
                  Predicted score
                </th>
                <th scope="col" className="num">
                  Realised score
                </th>
                <th scope="col">Drift reason</th>
                <th scope="col">Sites</th>
                <th scope="col">View</th>
              </tr>
            </thead>
            <tbody>
              {steps.map((s, i) => (
                <tr
                  key={`${s.hour}-${i}`}
                  className={s.stage === "replan" ? "is-highlight" : undefined}
                  aria-current={i === safeIndex ? "step" : undefined}
                >
                  <th scope="row" className="num">
                    {fmt(s.hour, 0)}
                  </th>
                  <td>{stageTag(s)}</td>
                  <td className="num">{s.aftershocks_real ?? "n/a"}</td>
                  <td className="num">
                    {s.aftershocks_used ?? "n/a"}
                    {s.synthetic ? " (simulated)" : ""}
                  </td>
                  <td className="num">{num(s.centroid_shift_km)}</td>
                  <td className="num">{num(s.predicted_score)}</td>
                  <td className="num">{num(s.realised_score)}</td>
                  <td>{s.drift_reason ?? ""}</td>
                  <td>{fmtSites(s.sites)}</td>
                  <td>
                    {i === safeIndex ? (
                      <span className="muted">shown</span>
                    ) : (
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => setIndex(i)}
                        aria-label={`Show hour ${fmt(s.hour, 0)}`}
                      >
                        Show
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </TableFold>
    </section>
  );
}
