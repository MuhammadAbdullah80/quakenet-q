import type { CSSProperties } from "react";
import { layoutBars, type BarInput } from "@/lib/bars";
import { Expand, type Explain } from "@/components/Expand";

// Horizontal bar chart built from plain elements, so labels stay real text and wrap on phones.
// Works in server and client components. The table next to each chart holds the same data.

type Props = {
  title: string;
  /** One line under the title, for example which direction is better. */
  note: string;
  unit: string;
  items: readonly BarInput[];
  digits?: number;
  max?: number;
  /** Text for the highlighted bars in the legend. */
  highlightLabel?: string;
  /** Shown beside the chart when it is expanded. */
  explain?: Explain;
};

export function BarChart({
  title,
  note,
  unit,
  items,
  digits = 2,
  max,
  highlightLabel,
  explain,
}: Props) {
  const layout = layoutBars(items, { max });
  const shown = layout.ticks.length > 6 ? layout.ticks.filter((_, i) => i % 2 === 0) : layout.ticks;
  const summary =
    `${title}. ${note} ` +
    layout.bars.map((bar) => `${bar.label}: ${bar.value.toFixed(digits)} ${unit}`).join("; ") +
    ".";

  const figure = (
    <figure className="bar-chart">
      <figcaption>
        <span className="bar-chart-title">{title}</span>
        <span className="bar-chart-note">{note}</span>
      </figcaption>
      <div
        className="bar-chart-body"
        role="img"
        aria-label={summary}
        style={
          {
            "--gstep": `${layout.max > 0 && layout.ticks.length > 1 ? (layout.ticks[1] / layout.max) * 100 : 100}%`,
          } as CSSProperties
        }
      >
        {layout.bars.map((bar) => (
          <div key={bar.label} className={bar.highlight ? "bar-row is-highlight" : "bar-row"}>
            <span className="bar-label">{bar.label}</span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: `${(bar.width * 100).toFixed(2)}%` }} />
            </span>
            <span className="bar-value">
              {bar.value.toFixed(digits)} <span className="bar-unit">{unit}</span>
            </span>
          </div>
        ))}
        <div className="bar-axis" aria-hidden="true">
          <span />
          <span className="bar-ticks">
            {shown.map((tick) => (
              <span
                key={tick}
                style={{ left: `${layout.max > 0 ? (tick / layout.max) * 100 : 0}%` }}
              >
                {Number(tick.toFixed(digits))}
              </span>
            ))}
          </span>
          <span />
        </div>
      </div>
      {highlightLabel ? (
        <p className="bar-legend">
          <span className="bar-swatch" aria-hidden="true" /> {highlightLabel}
        </p>
      ) : null}
    </figure>
  );
  return (
    <Expand
      title={title}
      explain={
        explain ?? {
          what: note,
          read: [
            "Each bar is one item; its length is the value, with the number at the end.",
            highlightLabel
              ? `Lime bars: ${highlightLabel.toLowerCase()}.`
              : "Hover a bar for its value.",
          ],
        }
      }
    >
      {figure}
    </Expand>
  );
}
