"use client";

import {
  geoDistance,
  geoGraticule10,
  geoOrthographic,
  geoPath,
  type GeoPermissibleObjects,
} from "d3-geo";
import { useEffect, useRef } from "react";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import land110 from "world-atlas/land-110m.json";
import worldQuakes from "@/data/world-quakes.json";
import { Expand } from "@/components/Expand";

// An interactive globe of earthquakes: drag to turn it, hover a dot for details. It settles on the
// data when the page opens and pulses only the points that matter (newest, or flagged). Every
// point is also listed in the table beside it, so the canvas is decoration for screen readers.

export type GlobePoint = {
  id: string;
  lat: number;
  lon: number;
  mag: number;
  title: string;
  detail: string;
  /** Drawn with a ring and a slow pulse, for example "reaches the trigger magnitude". */
  flag?: boolean;
  /** The newest point gets one pulse too. */
  newest?: boolean;
};

const LAND = feature(
  land110 as unknown as Topology,
  (land110 as unknown as Topology).objects.land as GeometryCollection,
) as GeoPermissibleObjects;
const GRATICULE = geoGraticule10();
const CONTEXT = worldQuakes.quakes as [number, number, number][];

function centroid(points: GlobePoint[]): [number, number] {
  if (!points.length) return [0, 20];
  let x = 0;
  let y = 0;
  let z = 0;
  for (const p of points) {
    const la = (p.lat * Math.PI) / 180;
    const lo = (p.lon * Math.PI) / 180;
    x += Math.cos(la) * Math.cos(lo);
    y += Math.cos(la) * Math.sin(lo);
    z += Math.sin(la);
  }
  const lon = (Math.atan2(y, x) * 180) / Math.PI;
  const lat = (Math.atan2(z, Math.hypot(x, y)) * 180) / Math.PI;
  return [lon, lat];
}

const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

export function QuakeGlobe({
  points,
  label,
  flagLabel,
  dotLabel,
}: {
  points: GlobePoint[];
  label: string;
  flagLabel?: string;
  dotLabel: string;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    const tip = tipRef.current;
    const ctx = canvas?.getContext("2d");
    if (!wrap || !canvas || !tip || !ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const [clon, clat] = centroid(points);
    const target: [number, number] = [-clon, -Math.max(-60, Math.min(60, clat))];
    const rot: [number, number] = reduce ? [...target] : [target[0] + 70, target[1] + 12];
    const from: [number, number] = [...rot];
    let size = 0;
    let dpr = 1;
    let raf = 0;
    let start = 0;
    let visible = true;
    let dragging: { x: number; y: number; r: [number, number] } | null = null;
    let hover: GlobePoint | null = null;
    const pulsing = points.some((p) => p.flag || p.newest);

    const proj = geoOrthographic().clipAngle(90).precision(0.6);
    const path = geoPath(proj, ctx);

    const resize = () => {
      size = wrap.clientWidth;
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.width = Math.round(size * dpr);
      canvas.height = Math.round(size * dpr);
      canvas.style.height = `${size}px`;
    };

    const draw = (now: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, size, size);
      proj
        .scale(size * 0.47)
        .translate([size / 2, size / 2])
        .rotate(rot);
      const centre: [number, number] = [-rot[0], -rot[1]];
      const seen = (lon: number, lat: number) =>
        geoDistance([lon, lat], centre) < Math.PI / 2 - 0.01;

      // Soft halo, sphere, graticule, land.
      const glow = ctx.createRadialGradient(
        size / 2,
        size / 2,
        size * 0.44,
        size / 2,
        size / 2,
        size * 0.52,
      );
      const darkBase = document.documentElement.dataset.theme === "dark";
      glow.addColorStop(0, darkBase ? "rgba(198, 243, 92, 0.10)" : "rgba(16, 41, 26, 0.18)");
      glow.addColorStop(1, darkBase ? "rgba(198, 243, 92, 0)" : "rgba(16, 41, 26, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, size, size);
      ctx.beginPath();
      path({ type: "Sphere" });
      ctx.fillStyle = "#10291a";
      ctx.fill();
      ctx.strokeStyle = "rgba(232, 239, 233, 0.28)";
      ctx.lineWidth = 1.2;
      ctx.stroke();
      ctx.beginPath();
      path(GRATICULE);
      ctx.strokeStyle = "rgba(231, 235, 232, 0.07)";
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.beginPath();
      path(LAND);
      ctx.fillStyle = "#1f3d2b";
      ctx.fill();
      ctx.strokeStyle = "rgba(231, 235, 232, 0.2)";
      ctx.lineWidth = 0.7;
      ctx.stroke();

      // Context: every M6.5+ earthquake since 2000, very faint.
      ctx.fillStyle = "rgba(231, 235, 232, 0.16)";
      for (const [lon, lat] of CONTEXT) {
        if (!seen(lon, lat)) continue;
        const pt = proj([lon, lat]);
        if (!pt) continue;
        ctx.fillRect(pt[0] - 0.9, pt[1] - 0.9, 1.8, 1.8);
      }

      // The data, smallest first so big ones sit on top.
      const sorted = [...points].sort((a, b) => a.mag - b.mag);
      for (const p of sorted) {
        if (!seen(p.lon, p.lat)) continue;
        const pt = proj([p.lon, p.lat]);
        if (!pt) continue;
        const r = Math.max(2.2, 1.6 + (p.mag - 2.5) * 1.5);
        if ((p.flag || p.newest) && !reduce) {
          const phase = (((now / (p.flag ? 1800 : 2400)) % 1) + 1) % 1;
          ctx.beginPath();
          ctx.arc(pt[0], pt[1], r + 3 + phase * 16, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(231, 235, 232, ${0.7 * (1 - phase)})`;
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], r, 0, Math.PI * 2);
        ctx.fillStyle = p === hover ? "#ffffff" : "rgba(231, 235, 232, 0.88)";
        ctx.fill();
        if (p.flag || p === hover) {
          ctx.beginPath();
          ctx.arc(pt[0], pt[1], r + 3, 0, Math.PI * 2);
          ctx.strokeStyle = "#e7ebe8";
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      }
    };

    const loop = (now: number) => {
      raf = 0;
      if (!start) start = now;
      const t = reduce ? 1 : Math.min(1, (now - start) / 1600);
      if (!dragging && t < 1) {
        const e = ease(t);
        rot[0] = from[0] + (target[0] - from[0]) * e;
        rot[1] = from[1] + (target[1] - from[1]) * e;
      }
      draw(now);
      if (visible && (t < 1 || (pulsing && !reduce))) raf = requestAnimationFrame(loop);
    };
    const kick = () => {
      if (!raf) raf = requestAnimationFrame(loop);
    };

    const pick = (x: number, y: number): GlobePoint | null => {
      const centre: [number, number] = [-rot[0], -rot[1]];
      let best: GlobePoint | null = null;
      let bestD = 14;
      for (const p of points) {
        if (geoDistance([p.lon, p.lat], centre) > Math.PI / 2 - 0.01) continue;
        const pt = proj([p.lon, p.lat]);
        if (!pt) continue;
        const d = Math.hypot(pt[0] - x, pt[1] - y);
        if (d < bestD) {
          best = p;
          bestD = d;
        }
      }
      return best;
    };

    const onDown = (e: PointerEvent) => {
      dragging = { x: e.clientX, y: e.clientY, r: [rot[0], rot[1]] };
      start = -1e9; // stop the opening rotation
      canvas.setPointerCapture(e.pointerId);
      wrap.dataset.dragging = "true";
    };
    const onMove = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      if (dragging) {
        const k = 160 / size;
        rot[0] = dragging.r[0] + (e.clientX - dragging.x) * k;
        rot[1] = Math.max(-80, Math.min(80, dragging.r[1] - (e.clientY - dragging.y) * k));
        tip.hidden = true;
        hover = null;
        draw(performance.now());
        return;
      }
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const p = pick(x, y);
      if (p !== hover) {
        hover = p;
        draw(performance.now());
      }
      if (p) {
        tip.hidden = false;
        tip.querySelector(".globe-tip-title")!.textContent = p.title;
        tip.querySelector(".globe-tip-detail")!.textContent = p.detail;
        const left = Math.min(size - tip.offsetWidth - 4, Math.max(4, x + 14));
        const top = Math.max(4, y - tip.offsetHeight - 10);
        tip.style.transform = `translate(${left}px, ${top}px)`;
      } else {
        tip.hidden = true;
      }
    };
    const onUp = (e: PointerEvent) => {
      dragging = null;
      delete wrap.dataset.dragging;
      if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId);
    };
    const onLeave = () => {
      if (dragging) return;
      hover = null;
      tip.hidden = true;
      draw(performance.now());
    };

    resize();
    draw(performance.now());
    kick();
    // React to width changes only: setting the canvas height must not start a resize loop
    // (a height change can toggle a scrollbar, which changes the width, and so on).
    const ro = new ResizeObserver(() => {
      if (Math.abs(wrap.clientWidth - size) < 1) return;
      resize();
      draw(performance.now());
    });
    ro.observe(wrap);
    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) kick();
    });
    io.observe(wrap);
    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointercancel", onUp);
    canvas.addEventListener("pointerleave", onLeave);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointercancel", onUp);
      canvas.removeEventListener("pointerleave", onLeave);
    };
  }, [points]);

  return (
    <Expand
      title={label}
      clickToOpen={false}
      explain={{
        what: label,
        read: [
          "Each dot is an earthquake; bigger dots are bigger magnitudes.",
          ...(flagLabel ? [`Ringed dots: ${flagLabel}.`] : []),
          "Faint specks are every magnitude 6.5 and above earthquake since 2000, for context.",
          "Drag to turn the globe; hover a dot for its name, size and time.",
        ],
      }}
    >
      <figure className="globe">
        <div className="globe-stage" ref={wrapRef}>
          <canvas ref={canvasRef} aria-hidden="true" />
          <div className="globe-tip" ref={tipRef} hidden aria-hidden="true">
            <span className="globe-tip-title" />
            <span className="globe-tip-detail" />
          </div>
        </div>
        <figcaption>
          <span className="globe-caption">{label}</span>
          <span className="globe-key">
            <span className="key-dot" aria-hidden="true" /> {dotLabel}
            {flagLabel ? (
              <>
                <span className="key-ring" aria-hidden="true" /> {flagLabel}
              </>
            ) : null}
            <span className="key-faint" aria-hidden="true" /> M6.5 and above since 2000
          </span>
          <span className="globe-hint">Drag to turn the globe. Hover a dot for details.</span>
        </figcaption>
      </figure>
    </Expand>
  );
}
