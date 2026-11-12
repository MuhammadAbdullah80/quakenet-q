"use client";

import { useState } from "react";
import { SiteMap } from "@/components/SiteMap";
import { fmt, fmtPercent, fmtSites } from "@/lib/format";
import type { Sequence, SequenceStep } from "@/lib/schemas";
import { sequenceMapData, stageLabel } from "@/lib/sequence";

// Hour-by-hour view of one sequence. The sequence comes in as props from the
// server page; nothing here talks to the network.

function num(value: number | null | undefined, digits = 1, unit = ""): string {
  return typeof value === "number" ? `${fmt(value, digits)}${unit}` : "n/a";
}

function stageTag(step: SequenceStep) {
  const tone = step.stage === "replan" ? "tag-warn" : step.stage === "first_plan" ? "tag-ok" : "";
  return <span className={`tag ${tone}`}>{stageLabel(step.stage)}</span>;
}

export function SequenceViewer({ sequence, title }: { sequence: Sequence; title: string }) {
  const steps = sequence.steps;
  const [index, setIndex] = useState(Math.max(0, steps.length - 1));
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

  return (
    <section aria-labelledby="timeline-heading">
      <h2 id="timeline-heading">Hour by hour</h2>
      <div className="panel">
        <div className="field">
          <label htmlFor="step-slider">
            Step {safeIndex + 1} of {steps.length}: {valueText}
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
            onChange={(e) => setIndex(Number(e.target.value))}
          />
          <span className="hint">Use the arrow keys, Home and End to move between steps.</span>
        </div>
        <p className="small">
          <button
            type="button"
            className="secondary"
            onClick={() => setIndex(Math.max(0, safeIndex - 1))}
            disabled={safeIndex === 0}
          >
            Previous step
          </button>{" "}
          <button
            type="button"
            className="secondary"
            onClick={() => setIndex(Math.min(steps.length - 1, safeIndex + 1))}
            disabled={safeIndex === steps.length - 1}
          >
            Next step
          </button>
        </p>
      </div>

      <div className="columns">
        <SiteMap
          instance={sequenceMapData(sequence, step.hour)}
          title={`${title} at hour ${fmt(step.hour, 0)}`}
          chosen={step.sites}
          chosenLabel="Sensor in place at this step"
          secondary={movedFrom}
          secondaryLabel="Sensor moved away from here at this step"
          designLabel="Real aftershock by this hour"
        />
        <div>
          {step.drift ? (
            <div className="notice notice-warn">
              <p className="notice-title">Drift detected: the agent re-planned</p>
              <p>{step.drift_reason ?? "No reason given."}</p>
            </div>
          ) : null}
          <dl className="facts">
            <div>
              <dt>Hour after the mainshock</dt>
              <dd>{fmt(step.hour, 0)}</dd>
            </div>
            <div>
              <dt>Stage</dt>
              <dd>{stageTag(step)}</dd>
            </div>
            <div>
              <dt>Real aftershocks so far</dt>
              <dd>{step.aftershocks_real ?? "n/a"}</dd>
            </div>
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
              <dd>{typeof step.score_drop === "number" ? fmtPercent(step.score_drop, 0) : "n/a"}</dd>
            </div>
            <div>
              <dt>Sites in place</dt>
              <dd>{fmtSites(step.sites)}</dd>
            </div>
            {plan ? (
              <>
                <div>
                  <dt>Moves in this plan</dt>
                  <dd>
                    {moves.length === 0
                      ? "none"
                      : moves.map((m) => `${m.from} to ${m.to}`).join(", ")}
                  </dd>
                </div>
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
        </div>
      </div>

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
    </section>
  );
}
