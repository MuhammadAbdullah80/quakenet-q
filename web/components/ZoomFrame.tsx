"use client";

import { useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

// Magnify a map without crowding it: the map is drawn larger while every mark keeps its screen
// size (SiteMap counter-scales its marks by --mz), so close marks pull apart. Drag to pan when
// zoomed in. The view stays centred on the same spot as the zoom changes.

const STEPS = [1, 1.5, 2, 3, 4];

export function ZoomFrame({ children, label }: { children: ReactNode; label: string }) {
  const [step, setStep] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const centre = useRef({ x: 0.5, y: 0.5 });
  const drag = useRef<{ x: number; y: number; left: number; top: number; moved: boolean } | null>(
    null,
  );
  const z = STEPS[step];

  const remember = () => {
    const el = scrollRef.current;
    if (!el) return;
    centre.current = {
      x: (el.scrollLeft + el.clientWidth / 2) / el.scrollWidth,
      y: (el.scrollTop + el.clientHeight / 2) / el.scrollHeight,
    };
  };

  // After a zoom change, scroll so the same spot stays in the middle.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollLeft = centre.current.x * el.scrollWidth - el.clientWidth / 2;
    el.scrollTop = centre.current.y * el.scrollHeight - el.clientHeight / 2;
  }, [z]);

  const zoomTo = (next: number) => {
    remember();
    setStep(Math.max(0, Math.min(STEPS.length - 1, next)));
  };

  return (
    <div className="zoom-frame" style={{ "--mz": z } as CSSProperties} data-zoomed={z > 1}>
      <div className="zoom-controls" role="group" aria-label={`Zoom: ${label}`}>
        <button
          type="button"
          onClick={() => zoomTo(step - 1)}
          disabled={step === 0}
          aria-label="Zoom out"
          title="Zoom out"
        >
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <circle cx="7" cy="7" r="4.5" />
            <path d="M10.4 10.4 14 14M5 7h4" />
          </svg>
        </button>
        <span className="zoom-level" aria-live="polite">
          {z}×
        </span>
        <button
          type="button"
          onClick={() => zoomTo(step + 1)}
          disabled={step === STEPS.length - 1}
          aria-label="Zoom in"
          title="Zoom in"
        >
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <circle cx="7" cy="7" r="4.5" />
            <path d="M10.4 10.4 14 14M5 7h4M7 5v4" />
          </svg>
        </button>
        {step > 0 ? (
          <button
            type="button"
            className="zoom-reset"
            onClick={() => {
              centre.current = { x: 0.5, y: 0.5 };
              setStep(0);
            }}
          >
            Reset
          </button>
        ) : null}
      </div>
      <div
        ref={scrollRef}
        className="zoom-scroll"
        tabIndex={z > 1 ? 0 : -1}
        aria-label={
          z > 1 ? `${label}, zoomed ${z} times. Drag or use the scroll bars to move.` : undefined
        }
        onKeyDown={(e) => {
          if (e.key === "+" || e.key === "=") zoomTo(step + 1);
          if (e.key === "-") zoomTo(step - 1);
        }}
        onPointerDown={(e) => {
          if (z === 1 || e.button !== 0) return;
          const el = scrollRef.current!;
          drag.current = {
            x: e.clientX,
            y: e.clientY,
            left: el.scrollLeft,
            top: el.scrollTop,
            moved: false,
          };
          el.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          const d = drag.current;
          if (!d) return;
          const el = scrollRef.current!;
          if (Math.abs(e.clientX - d.x) + Math.abs(e.clientY - d.y) > 3) d.moved = true;
          el.scrollLeft = d.left - (e.clientX - d.x);
          el.scrollTop = d.top - (e.clientY - d.y);
        }}
        onPointerUp={(e) => {
          drag.current = null;
          scrollRef.current?.releasePointerCapture?.(e.pointerId);
        }}
        onPointerCancel={() => {
          drag.current = null;
        }}
      >
        <div className="zoom-content" style={{ width: `${z * 100}%` }}>
          {children}
        </div>
      </div>
    </div>
  );
}
