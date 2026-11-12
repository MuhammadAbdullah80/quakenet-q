"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { STORY } from "@/lib/story-data";
import { synthTrace, type TraceEvent } from "@/lib/trace";

// A seismograph band behind each console page's title. The pen draws in when the page opens, from
// the real times and magnitudes of the Ridgecrest aftershocks; each page shows its own 3-hour slice.
// Decoration only (aria-hidden); the label says what it is.

const EVENTS: TraceEvent[] = [...STORY.early, ...STORY.later]
  .map((q) => [q[4], q[3]] as const)
  .sort((a, b) => a[0] - b[0]);
const ORDER = [
  "/events",
  "/feed",
  "/candidates",
  "/scoring",
  "/quantum",
  "/self-check",
  "/plan",
  "/monitor",
  "/memory",
  "/noise",
  "/settings",
  "/system",
  "/guide",
];
const WINDOW_H = 3;
const DRAW_MS = 1500;

function windowFor(path: string): [number, number] {
  const i = Math.max(0, ORDER.indexOf(path));
  const last = EVENTS.at(-1)?.[0] ?? 24;
  const t0 = ((i * 1.7) % Math.max(1, last - WINDOW_H)) + 0.05;
  return [t0, t0 + WINDOW_H];
}

function hhmm(h: number): string {
  const m = Math.round(h * 60);
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

export function PageTrace() {
  const path = usePathname() ?? "";
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [t0, t1] = windowFor(path);
  const count = EVENTS.filter((e) => e[0] >= t0 && e[0] < t1).length;

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let start = 0;
    let w = 0;
    let h = 0;
    let trace: Float32Array = new Float32Array(0);

    const setup = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = rect.width;
      h = rect.height;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      trace = synthTrace(EVENTS, { t0, t1, samples: Math.max(60, Math.round(w / 1.5)), seed: 11 });
    };

    const draw = (t: number) => {
      ctx.clearRect(0, 0, w, h);
      // Ink follows the theme: light lines on the dark green base, dark lines on the light one.
      const rgb =
        document.documentElement.dataset.theme === "dark" ? "232, 239, 233" : "16, 41, 26";
      const mid = h * 0.56;
      const amp = h * 0.36;
      const n = trace.length;
      const upto = Math.max(1, Math.floor(n * t));
      // Hour ticks along the baseline.
      ctx.strokeStyle = `rgba(${rgb}, 0.14)`;
      ctx.lineWidth = 1;
      for (let k = Math.ceil(t0 * 2) / 2; k <= t1; k += 0.5) {
        const x = ((k - t0) / (t1 - t0)) * w;
        ctx.beginPath();
        ctx.moveTo(x, mid + amp + 4);
        ctx.lineTo(x, mid + amp + (k % 1 === 0 ? 12 : 8));
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.moveTo(0, mid);
      ctx.lineTo(w, mid);
      ctx.strokeStyle = `rgba(${rgb}, 0.08)`;
      ctx.stroke();

      ctx.beginPath();
      for (let i = 0; i < upto; i += 1) {
        const x = (i / (n - 1)) * w;
        const y = mid - trace[i] * amp;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = `rgba(${rgb}, 0.5)`;
      ctx.lineWidth = 1.25;
      ctx.lineJoin = "round";
      ctx.stroke();

      if (t < 1) {
        const x = ((upto - 1) / (n - 1)) * w;
        const y = mid - trace[upto - 1] * amp;
        ctx.beginPath();
        ctx.arc(x, y, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = "#c6f35c";
        ctx.fill();
        ctx.strokeStyle = "#10291a";
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }
    };

    const tick = (now: number) => {
      if (!start) start = now;
      const p = Math.min(1, (now - start) / DRAW_MS);
      draw(1 - (1 - p) ** 3);
      if (p < 1) raf = requestAnimationFrame(tick);
    };

    setup();
    if (reduce) draw(1);
    else raf = requestAnimationFrame(tick);
    // Redraw complete on real resizes only; the observer also fires once when it starts.
    const ro = new ResizeObserver(() => {
      if (Math.abs(canvas.getBoundingClientRect().width - w) < 1) return;
      cancelAnimationFrame(raf);
      setup();
      draw(1);
    });
    ro.observe(canvas);
    const onTheme = () => draw(1);
    window.addEventListener("qn-theme-change", onTheme);
    return () => {
      window.removeEventListener("qn-theme-change", onTheme);
      ro.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [t0, t1]);

  if (path === "/" || path === "" || path === "/demo") return null;
  return (
    <div
      className="page-trace"
      aria-hidden="true"
      title={`Ridgecrest 2019, hours ${hhmm(t0)} to ${hhmm(t1)} after the mainshock: ${count} aftershocks. The trace is drawn from their times and sizes.`}
    >
      <canvas ref={canvasRef} />
    </div>
  );
}
