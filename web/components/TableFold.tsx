"use client";

import { useId, useState, type ReactNode } from "react";

// Shows the first `limit` rows of the table inside it, with a button for the rest. The table is
// fully in the page either way; hidden rows are only folded away with CSS.
export function TableFold({
  children,
  total,
  limit = 6,
  noun = "rows",
}: {
  children: ReactNode;
  total: number;
  limit?: number;
  noun?: string;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  if (total <= limit + 2) return <>{children}</>;
  return (
    <div className="fold" data-open={open}>
      <div id={id} className={open ? "fold-body" : `fold-body fold-${limit}`}>
        {children}
      </div>
      <button
        type="button"
        className="fold-toggle secondary"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? `Show the first ${limit} only` : `Show all ${total} ${noun}`}
        <span className="fold-chevron" aria-hidden="true" />
      </button>
    </div>
  );
}
