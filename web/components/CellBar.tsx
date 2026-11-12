import type { ReactNode } from "react";

// A slim bar inside a table cell, so a column can be compared at a glance. The bar runs between
// the column's lowest and highest value (never empty, so the smallest still shows); the number
// stays as text beside it.
export function CellBar({
  value,
  min,
  max,
  children,
}: {
  value: number;
  min: number;
  max: number;
  children: ReactNode;
}) {
  const t = max > min ? (value - min) / (max - min) : 1;
  const width = 12 + Math.max(0, Math.min(1, t)) * 88;
  return (
    <span className="cell-bar">
      <span className="cell-bar-track" aria-hidden="true">
        <span className="cell-bar-fill" style={{ width: `${width}%` }} />
      </span>
      <span className="cell-bar-text">{children}</span>
    </span>
  );
}
