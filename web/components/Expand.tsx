"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

// Any chart or map can open large on the same screen, next to a plain explanation of what it
// shows and how to read it. Uses the native <dialog>, so focus is trapped and returned, and
// Escape closes it. Minimise, Escape or a click outside the panel closes it.

export type Explain = {
  /** One sentence: what the picture shows. */
  what: string;
  /** Short points: how to read it. */
  read: string[];
};

export function Expand({
  title,
  explain,
  children,
  clickToOpen = true,
}: {
  title: string;
  explain: Explain;
  children: ReactNode;
  /** False for interactive charts (drag, hover) where a click means something else. */
  clickToOpen?: boolean;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <div className="expand">
      <div
        className={clickToOpen ? "expand-target is-clickable" : "expand-target"}
        onClick={clickToOpen ? () => setOpen(true) : undefined}
      >
        {children}
      </div>
      <button
        type="button"
        className="expand-button"
        onClick={() => setOpen(true)}
        aria-label={`Expand: ${title}`}
        title="Expand"
      >
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <path d="M2 6V2h4M14 6V2h-4M2 10v4h4M14 10v4h-4" />
        </svg>
      </button>

      <dialog
        ref={dialogRef}
        className="expand-dialog"
        aria-label={title}
        onClose={() => setOpen(false)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setOpen(false);
        }}
      >
        {open ? (
          <div className="expand-panel">
            <header className="expand-head">
              <h2>{title}</h2>
              <button type="button" className="secondary" onClick={() => setOpen(false)}>
                Minimise
              </button>
            </header>
            <div className="expand-body">
              <div className="expand-figure">{children}</div>
              <aside className="expand-explain">
                <h3>What this shows</h3>
                <p>{explain.what}</p>
                <h3>How to read it</h3>
                <ul>
                  {explain.read.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </aside>
            </div>
          </div>
        ) : null}
      </dialog>
    </div>
  );
}
