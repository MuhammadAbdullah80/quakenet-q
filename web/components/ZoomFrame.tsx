"use client";

import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

// Magnify a map without crowding it: the map is drawn larger while every mark keeps its screen
// size (SiteMap counter-scales its marks by --mz), so close marks pull apart.
// Ways to zoom: the slider (1x to 8x, fine steps), the buttons (1.25x per press), pinch on a
// trackpad or Ctrl/Cmd + wheel (zooms at the pointer), double-click (Shift to zoom out), and a
// two-finger pinch on touch screens. Drag to pan. Plain scrolling still scrolls the page.

const MIN = 1;
const MAX = 8;
const STEP = 1.25;
const clamp = (z: number) => Math.min(MAX, Math.max(MIN, Math.round(z * 100) / 100));

type Anchor = { rx: number; ry: number; px: number; py: number };

export function ZoomFrame({ children, label }: { children: ReactNode; label: string }) {
  const [z, setZ] = useState(1);
  const [smooth, setSmooth] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const anchor = useRef<Anchor | null>(null);
  const zRef = useRef(1);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef<{ dist: number; z: number } | null>(null);
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  useEffect(() => {
    zRef.current = z;
  }, [z]);

  /** Zoom to `next`, keeping the content point under (px, py) in place. Defaults to the centre. */
  const zoomTo = (next: number, px?: number, py?: number, animate = true) => {
    const el = scrollRef.current;
    const target = clamp(next);
    if (!el || target === zRef.current) return;
    const x = px ?? el.clientWidth / 2;
    const y = py ?? el.clientHeight / 2;
    anchor.current = {
      rx: (el.scrollLeft + x) / el.scrollWidth,
      ry: (el.scrollTop + y) / el.scrollHeight,
      px: x,
      py: y,
    };
    setSmooth(animate);
    setZ(target);
  };

  // After the content resizes, scroll so the anchored point is back under the pointer.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    const a = anchor.current;
    if (!el || !a) return;
    el.scrollLeft = a.rx * el.scrollWidth - a.px;
    el.scrollTop = a.ry * el.scrollHeight - a.py;
    anchor.current = null;
  }, [z]);

  // Pinch on a trackpad arrives as a wheel event with ctrlKey; Ctrl/Cmd + wheel works the same.
  // Registered by hand because React's wheel listener is passive and cannot stop page zoom.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const factor = Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0025));
      zoomTo(zRef.current * factor, e.clientX - r.left, e.clientY - r.top, false);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const local = (e: { clientX: number; clientY: number }) => {
    const r = scrollRef.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  return (
    <div
      className="zoom-frame"
      style={{ "--mz": z } as CSSProperties}
      data-zoomed={z > 1}
      data-smooth={smooth}
    >
      <div className="zoom-controls" role="group" aria-label={`Zoom: ${label}`}>
        <button
          type="button"
          onClick={() => zoomTo(z / STEP)}
          disabled={z <= MIN}
          aria-label="Zoom out"
          title="Zoom out"
        >
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <circle cx="7" cy="7" r="4.5" />
            <path d="M10.4 10.4 14 14M5 7h4" />
          </svg>
        </button>
        <input
          className="zoom-slider"
          type="range"
          min={MIN}
          max={MAX}
          step={0.1}
          value={z}
          aria-label="Zoom level"
          aria-valuetext={`${z.toFixed(1)} times`}
          onChange={(e) => zoomTo(Number(e.target.value), undefined, undefined, false)}
        />
        <button
          type="button"
          onClick={() => zoomTo(z * STEP)}
          disabled={z >= MAX}
          aria-label="Zoom in"
          title="Zoom in"
        >
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <circle cx="7" cy="7" r="4.5" />
            <path d="M10.4 10.4 14 14M5 7h4M7 5v4" />
          </svg>
        </button>
        <span className="zoom-level" aria-hidden="true">
          {z.toFixed(1)}×
        </span>
        {z > 1 ? (
          <button type="button" className="zoom-reset" onClick={() => zoomTo(1)}>
            Reset
          </button>
        ) : null}
      </div>
      <div
        ref={scrollRef}
        className="zoom-scroll"
        tabIndex={0}
        aria-label={`${label}. Plus and minus keys zoom; when zoomed, drag or scroll to move.`}
        onKeyDown={(e) => {
          if (e.key === "+" || e.key === "=") zoomTo(z * STEP);
          if (e.key === "-" || e.key === "_") zoomTo(z / STEP);
          if (e.key === "0") zoomTo(1);
        }}
        onDoubleClick={(e) => {
          const p = local(e);
          zoomTo(e.shiftKey ? z / 1.6 : z * 1.6, p.x, p.y);
        }}
        onPointerDown={(e) => {
          if (e.button !== 0) return;
          const el = scrollRef.current!;
          pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
          el.setPointerCapture(e.pointerId);
          if (pointers.current.size === 2) {
            const [a, b] = [...pointers.current.values()];
            pinch.current = { dist: Math.hypot(a.x - b.x, a.y - b.y), z: zRef.current };
            drag.current = null;
          } else if (zRef.current > 1) {
            drag.current = { x: e.clientX, y: e.clientY, left: el.scrollLeft, top: el.scrollTop };
          }
        }}
        onPointerMove={(e) => {
          if (!pointers.current.has(e.pointerId)) return;
          pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
          const el = scrollRef.current!;
          if (pinch.current && pointers.current.size === 2) {
            const [a, b] = [...pointers.current.values()];
            const dist = Math.hypot(a.x - b.x, a.y - b.y);
            const mid = local({ clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2 });
            zoomTo(pinch.current.z * (dist / pinch.current.dist), mid.x, mid.y, false);
            return;
          }
          const d = drag.current;
          if (!d) return;
          el.scrollLeft = d.left - (e.clientX - d.x);
          el.scrollTop = d.top - (e.clientY - d.y);
        }}
        onPointerUp={(e) => {
          pointers.current.delete(e.pointerId);
          if (pointers.current.size < 2) pinch.current = null;
          drag.current = null;
          scrollRef.current?.releasePointerCapture?.(e.pointerId);
        }}
        onPointerCancel={(e) => {
          pointers.current.delete(e.pointerId);
          pinch.current = null;
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
