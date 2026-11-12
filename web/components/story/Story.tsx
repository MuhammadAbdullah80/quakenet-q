"use client";

import {
  geoDistance,
  geoGraticule10,
  geoOrthographic,
  geoPath,
  type GeoPermissibleObjects,
} from "d3-geo";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import land110 from "world-atlas/land-110m.json";
import worldQuakes from "@/data/world-quakes.json";
import { COPY, PIPELINE, STORY } from "@/lib/story-data";
import { easeInOut, projectPlane, segment, wordsShown } from "@/lib/story-math";

// The landing-page scroll story (docs/FRONTEND_BRIEF.md section 4). One requestAnimationFrame loop
// draws everything from a smoothed scroll progress; per-frame values go to refs and styles, never
// to React state. Canvases are decoration (aria-hidden); every sentence is real DOM text.

const LAND = feature(
  land110 as unknown as Topology,
  (land110 as unknown as Topology).objects.land as GeometryCollection,
) as GeoPermissibleObjects;
const GRATICULE = geoGraticule10();
const QUAKES = worldQuakes.quakes as [number, number, number][];
const EVENT: [number, number] = [STORY.event.lon, STORY.event.lat];
const PICK = new Set(STORY.pick);
const EARTH_KM = 6371;
const DPR_CAP = 1.5;
const LANDSCAPE_WORDS = COPY.landscape.split(" ");

// Beats as windows of overall progress p (0..1 across the pinned section).
const B = {
  heroOut: [0.07, 0.15],
  turn: [0.03, 0.22],
  zoom: [0.13, 0.36],
  flyIn: [0.17, 0.23],
  flyOut: [0.29, 0.34],
  mistIn: [0.3, 0.36],
  mistOut: [0.37, 0.44],
  quakes: [0.44, 0.6],
  masts: [0.48, 0.6],
  words: [0.45, 0.6],
  landOut: [0.64, 0.69],
  shift: [0.64, 0.72],
  lime: [0.69, 0.74],
  stationIn: [0.7, 0.75],
  count: [0.73, 0.84],
  rows: [0.76, 0.86],
} as const;
const seg = (p: number, w: readonly [number, number]) => segment(p, w[0], w[1]);

type Size = { w: number; h: number; dpr: number; mobile: boolean };

type Els = {
  globe: HTMLCanvasElement | null;
  marks: HTMLCanvasElement | null;
  plane: HTMLDivElement | null;
  mist: HTMLDivElement | null;
  hero: HTMLDivElement | null;
  caption: HTMLParagraphElement | null;
  label: HTMLDivElement | null;
  fly: HTMLParagraphElement | null;
  land: HTMLDivElement | null;
  words: HTMLSpanElement[];
  clock: HTMLSpanElement | null;
  station: HTMLDivElement | null;
  count: HTMLSpanElement | null;
  spark: SVGPathElement | null;
  rows: HTMLLIElement[];
};

function fontVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v ? `${v}, ${fallback}` : fallback;
}

function show(el: HTMLElement | SVGElement | null, opacity: number, extra = "") {
  if (!el) return;
  el.style.opacity = opacity.toFixed(3);
  el.style.visibility = opacity < 0.01 ? "hidden" : "visible";
  if (extra) el.style.transform = extra;
}

/** Terrain geometry for a given progress; shared by the CSS plane and the marker canvas. */
function terrainView(p: number, size: Size) {
  const { w, h, mobile } = size;
  const side = mobile ? Math.min(w * 1.5, h * 1.05) : Math.min(Math.max(w * 0.8, h * 1.2), 1500);
  const settle = easeInOut(seg(p, [0.36, 0.5]));
  const shift = mobile ? 0 : easeInOut(seg(p, B.shift));
  return {
    side,
    kmPx: side / (2 * STORY.grid.extent_km),
    view: {
      cx: w / 2,
      cy: h / 2,
      scale: 0.92 + 0.08 * settle,
      tilt: ((62 - 8 * settle) * Math.PI) / 180,
      ty: mobile ? h * 0.12 : h * 0.06,
      tx: shift * w * 0.2,
      perspective: Math.max(w, h) * 1.1,
    },
  };
}

function drawGlobe(ctx: CanvasRenderingContext2D, p: number, size: Size) {
  const { w, h, dpr, mobile } = size;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  if (p > B.mistIn[1] + 0.01) return;

  const turn = easeInOut(seg(p, B.turn));
  const zoom = seg(p, B.zoom);
  const base = Math.min(w, h) * (mobile ? 0.46 : 0.4);
  // End scale matches the terrain's px per km, so the switch under the mist keeps the same size.
  const end = EARTH_KM * terrainView(1, size).kmPx * 0.9;
  const r = base * Math.pow(end / base, zoom * zoom);
  const heroCy = h * (mobile ? 0.25 : 0.4) + base;
  const cy = heroCy + (h / 2 - heroCy) * turn;
  const lon = -EVENT[0] + 32 * (1 - turn);
  const lat = -EVENT[1] + 18 * (1 - turn);

  const proj = geoOrthographic()
    .scale(r)
    .translate([w / 2, cy])
    .rotate([lon, lat])
    .clipAngle(90)
    .precision(0.5);
  const path = geoPath(proj, ctx);
  const centre: [number, number] = [-lon, -lat];

  ctx.beginPath();
  path({ type: "Sphere" });
  ctx.fillStyle = "#10291a";
  ctx.fill();

  ctx.beginPath();
  path(GRATICULE);
  ctx.strokeStyle = "rgba(231, 235, 232, 0.07)";
  ctx.lineWidth = 1;
  ctx.stroke();

  ctx.beginPath();
  path(LAND);
  ctx.fillStyle = "#1f3d2b";
  ctx.fill();
  ctx.strokeStyle = "rgba(231, 235, 232, 0.22)";
  ctx.lineWidth = 0.8;
  ctx.stroke();

  const dotScale = Math.min(1.6, 0.6 + r / 900);
  ctx.fillStyle = "rgba(231, 235, 232, 0.6)";
  for (const [qlon, qlat, mag] of QUAKES) {
    if (geoDistance([qlon, qlat], centre) > Math.PI / 2 - 0.02) continue;
    const pt = proj([qlon, qlat]);
    if (!pt) continue;
    ctx.beginPath();
    ctx.arc(pt[0], pt[1], (mag - 5.9) * 1.6 * dotScale, 0, Math.PI * 2);
    ctx.fill();
  }

  const at = proj(EVENT);
  if (at) {
    ctx.beginPath();
    ctx.arc(at[0], at[1], 11 + 4 * zoom, 0, Math.PI * 2);
    ctx.strokeStyle = "#c6f35c";
    ctx.lineWidth = 2.5;
    ctx.stroke();
  }
  return at;
}

function drawMarks(ctx: CanvasRenderingContext2D, p: number, size: Size, fonts: { mono: string }) {
  const { w, h, dpr, mobile } = size;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const appear = seg(p, B.mistIn);
  if (appear <= 0) return;

  const { kmPx, view } = terrainView(p, size);
  const at = (x: number, y: number) => projectPlane(x * kmPx, -y * kmPx, view);
  ctx.globalAlpha = appear;

  // Aftershocks in the order they happened.
  const hours = seg(p, B.quakes) * STORY.numbers.decision_hours;
  ctx.fillStyle = "rgba(16, 41, 26, 0.55)";
  for (const q of STORY.early) {
    if (q[4] > hours) break;
    const [sx, sy] = at(q[0], q[1]);
    ctx.beginPath();
    ctx.arc(sx, sy, 0.6 + (q[3] - 2) * 0.55, 0, Math.PI * 2);
    ctx.fill();
  }

  // Mainshock.
  const [mx, my] = at(STORY.mainshock[0], STORY.mainshock[1]);
  ctx.beginPath();
  for (let i = 0; i < 10; i += 1) {
    const rr = i % 2 === 0 ? 9 : 3.8;
    const a = -Math.PI / 2 + (i * Math.PI) / 5;
    ctx.lineTo(mx + rr * Math.cos(a), my + rr * Math.sin(a));
  }
  ctx.closePath();
  ctx.fillStyle = "#f6f7f4";
  ctx.fill();
  ctx.strokeStyle = "#10291a";
  ctx.lineWidth = 1.5;
  ctx.stroke();

  const rise = easeInOut(seg(p, B.masts));
  if (rise > 0) {
    const tall = (mobile ? 22 : 34) * rise;
    const lime = seg(p, B.lime);
    ctx.font = `500 ${mobile ? 9 : 11}px ${fonts.mono}`;
    ctx.textAlign = "center";

    for (const s of STORY.stations) {
      const [gx, gy] = at(s.x, s.y);
      ctx.strokeStyle = "rgba(16, 41, 26, 0.8)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(gx, gy);
      ctx.lineTo(gx, gy - tall);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(gx, gy - tall - 6);
      ctx.lineTo(gx - 5, gy - tall + 3);
      ctx.lineTo(gx + 5, gy - tall + 3);
      ctx.closePath();
      ctx.fillStyle = "#10291a";
      ctx.fill();
      if (!mobile && rise > 0.6) {
        ctx.fillStyle = "rgba(16, 41, 26, 0.85)";
        ctx.fillText(s.name, gx, gy - tall - 10);
      }
    }

    for (const c of STORY.candidates) {
      const [gx, gy] = at(c.x, c.y);
      const chosen = PICK.has(c.id) ? lime : 0;
      const top = gy - tall * 1.25;
      ctx.strokeStyle = "#10291a";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(gx, gy);
      ctx.lineTo(gx, top);
      ctx.stroke();
      const rad = mobile ? 8 : 10;
      if (chosen > 0) {
        ctx.beginPath();
        ctx.arc(gx, top, rad + 5 * chosen, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(198, 243, 92, ${chosen})`;
        ctx.lineWidth = 4;
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.arc(gx, top, rad, 0, Math.PI * 2);
      ctx.fillStyle = chosen > 0.5 ? "#c6f35c" : "#f6f7f4";
      ctx.fill();
      ctx.strokeStyle = "#10291a";
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.fillStyle = "#10291a";
      ctx.textBaseline = "middle";
      ctx.fillText(String(c.id), gx, top + 0.5);
      ctx.textBaseline = "alphabetic";
    }
  }
  ctx.globalAlpha = 1;
}

function sparkPath(): { d: string; pick: [number, number]; expert: [number, number] } {
  const errs = STORY.sorted_errors;
  const lo = Math.min(...errs);
  const hi = Math.max(...errs);
  const X = (i: number) => (i / (errs.length - 1)) * 200;
  const Y = (v: number) => 44 - ((v - lo) / (hi - lo || 1)) * 40;
  const d = errs
    .map((v, i) => `${i === 0 ? "M" : "L"}${X(i).toFixed(2)},${Y(v).toFixed(2)}`)
    .join(" ");
  return {
    d,
    pick: [X(STORY.pick_position), Y(errs[STORY.pick_position])],
    expert: [X(STORY.expert_position), Y(errs[STORY.expert_position])],
  };
}

const SPARK = sparkPath();

function StoryStage({ fixed }: { fixed?: number }) {
  const els = useRef<Els>({
    globe: null,
    marks: null,
    plane: null,
    mist: null,
    hero: null,
    caption: null,
    label: null,
    fly: null,
    land: null,
    words: [],
    clock: null,
    station: null,
    count: null,
    spark: null,
    rows: [],
  });
  const stageRef = useRef<HTMLDivElement>(null);
  const pinned = fixed === undefined;

  useEffect(() => {
    const stage = stageRef.current;
    const e = els.current;
    if (!stage || !e.globe || !e.marks) return;
    const gctx = e.globe.getContext("2d");
    const mctx = e.marks.getContext("2d");
    if (!gctx || !mctx) return;
    const fonts = { mono: fontVar("--font-mono", "monospace") };
    const size: Size = { w: 1, h: 1, dpr: 1, mobile: false };
    const sparkLen = e.spark?.getTotalLength() ?? 1;
    if (e.spark) e.spark.style.strokeDasharray = String(sparkLen);
    const { none, pick } = { none: STORY.numbers.error_none_km, pick: STORY.numbers.error_pick_km };

    const resize = () => {
      const rect = stage.getBoundingClientRect();
      size.w = rect.width;
      size.h = rect.height;
      size.dpr = Math.min(window.devicePixelRatio || 1, DPR_CAP);
      size.mobile = rect.width < 700;
      for (const c of [e.globe, e.marks]) {
        if (!c) continue;
        c.width = Math.round(size.w * size.dpr);
        c.height = Math.round(size.h * size.dpr);
      }
    };

    const render = (p: number) => {
      const at = drawGlobe(gctx, p, size);
      drawMarks(mctx, p, size, fonts);

      const heroO = 1 - seg(p, B.heroOut);
      show(e.hero, heroO, `translate3d(0, ${(-30 * seg(p, B.heroOut)).toFixed(1)}px, 0)`);
      show(e.caption, heroO);
      if (e.label) {
        show(e.label, heroO * (at ? 1 : 0));
        if (at) {
          // Right of the ring, or left of it when that would leave the screen.
          const lw = e.label.offsetWidth;
          const lx = at[0] + 22 + lw > size.w - 8 ? at[0] - 22 - lw : at[0] + 22;
          e.label.style.transform = `translate3d(${lx.toFixed(1)}px, ${(at[1] - 14).toFixed(1)}px, 0)`;
        }
      }

      const flyO = seg(p, B.flyIn) * (1 - seg(p, B.flyOut));
      show(e.fly, flyO);
      if (e.fly) e.fly.style.filter = `blur(${((1 - seg(p, B.flyIn)) * 10).toFixed(1)}px)`;

      const mist = seg(p, B.mistIn) * (1 - seg(p, B.mistOut));
      show(e.mist, mist);

      const { side, view } = terrainView(p, size);
      if (e.plane) {
        e.plane.style.width = `${side}px`;
        e.plane.style.height = `${side}px`;
        e.plane.style.marginLeft = `${-side / 2}px`;
        e.plane.style.marginTop = `${-side / 2}px`;
        e.plane.style.transform = `translate3d(${(view.tx ?? 0).toFixed(1)}px, ${view.ty.toFixed(1)}px, 0) rotateX(${view.tilt.toFixed(4)}rad) scale(${view.scale.toFixed(4)})`;
        show(e.plane, seg(p, B.mistIn));
      }
      if (e.plane?.parentElement)
        e.plane.parentElement.style.perspective = `${view.perspective.toFixed(0)}px`;

      const landO = seg(p, [0.42, 0.47]) * (1 - seg(p, B.landOut));
      show(e.land, landO);
      const shown = wordsShown(seg(p, B.words), LANDSCAPE_WORDS.length);
      e.words.forEach((wEl, i) => {
        if (wEl) wEl.style.opacity = i < shown ? "1" : "0.12";
      });
      if (e.clock) {
        const hrs = seg(p, B.quakes) * STORY.numbers.decision_hours;
        const count = STORY.early.filter((q) => q[4] <= hrs).length;
        e.clock.textContent = `Hour ${hrs.toFixed(1).padStart(4, "0")} · ${count} aftershocks`;
      }

      show(e.station, seg(p, B.stationIn));
      const c = easeInOut(seg(p, B.count));
      if (e.count) e.count.textContent = (none - (none - pick) * c).toFixed(2);
      if (e.spark) e.spark.style.strokeDashoffset = (sparkLen * (1 - c)).toFixed(1);
      e.rows.forEach((row, i) => {
        if (!row) return;
        const t = seg(p, [B.rows[0] + i * 0.018, B.rows[0] + i * 0.018 + 0.03]);
        show(row, t, `translate3d(${(12 * (1 - t)).toFixed(1)}px, 0, 0)`);
      });
    };

    resize();
    if (!pinned) {
      render(fixed);
      const ro = new ResizeObserver(() => {
        resize();
        render(fixed);
      });
      ro.observe(stage);
      return () => ro.disconnect();
    }

    const section = stage.parentElement!;
    let target = 0;
    let current = 0;
    let raf = 0;
    let visible = true;
    const progress = () => {
      const rect = section.getBoundingClientRect();
      const run = rect.height - window.innerHeight;
      return run > 0 ? Math.min(1, Math.max(0, -rect.top / run)) : 0;
    };
    const tick = () => {
      raf = 0;
      current += (target - current) * 0.14;
      if (Math.abs(target - current) < 0.0004) current = target;
      render(current);
      if (current !== target && visible) raf = requestAnimationFrame(tick);
    };
    const kick = () => {
      target = progress();
      if (!raf && visible) raf = requestAnimationFrame(tick);
    };
    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) kick();
    });
    io.observe(section);
    const ro = new ResizeObserver(() => {
      resize();
      render(current);
    });
    ro.observe(stage);
    window.addEventListener("scroll", kick, { passive: true });
    current = target = progress();
    render(current);
    return () => {
      window.removeEventListener("scroll", kick);
      io.disconnect();
      ro.disconnect();
      if (raf) cancelAnimationFrame(raf);
    };
  }, [fixed, pinned]);

  return (
    <div className={pinned ? "story-stage" : "story-stage is-fixed"} ref={stageRef}>
      <div className="story-terrain-wrap" aria-hidden="true">
        <div
          className="story-plane"
          ref={(node) => {
            els.current.plane = node;
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- decorative layer inside a 3D transform */}
          <img
            src="/relief/ridgecrest-2000.webp"
            alt=""
            width={2000}
            height={2000}
            decoding="async"
          />
        </div>
      </div>
      <canvas
        className="story-canvas"
        ref={(node) => {
          els.current.globe = node;
        }}
        aria-hidden="true"
      />
      <canvas
        className="story-canvas"
        ref={(node) => {
          els.current.marks = node;
        }}
        aria-hidden="true"
      />
      <div
        className="story-mist"
        ref={(node) => {
          els.current.mist = node;
        }}
        aria-hidden="true"
      />

      <div
        className="story-hero"
        ref={(node) => {
          els.current.hero = node;
        }}
      >
        <h1>{COPY.headline}</h1>
      </div>
      <p
        className="story-caption"
        ref={(node) => {
          els.current.caption = node;
        }}
      >
        {COPY.caption}
      </p>
      <div
        className="story-label"
        ref={(node) => {
          els.current.label = node;
        }}
        aria-hidden="true"
      >
        {COPY.label.map((line) => (
          <span key={line}>{line}</span>
        ))}
      </div>

      <p
        className="story-fly"
        ref={(node) => {
          els.current.fly = node;
        }}
      >
        {COPY.fly}
      </p>

      <div
        className="story-land"
        ref={(node) => {
          els.current.land = node;
        }}
      >
        <span
          className="story-clock"
          ref={(node) => {
            els.current.clock = node;
          }}
          aria-hidden="true"
        />
        <p>
          {LANDSCAPE_WORDS.map((word, i) => (
            <span
              key={i}
              ref={(node) => {
                if (node) els.current.words[i] = node;
              }}
            >
              {word}{" "}
            </span>
          ))}
        </p>
      </div>

      <div
        className="story-station"
        ref={(node) => {
          els.current.station = node;
        }}
      >
        <h2>{COPY.station}</h2>
        <div className="story-card">
          <p className="story-card-title">{COPY.cardTitle}</p>
          <p className="story-card-value">
            <span
              ref={(node) => {
                els.current.count = node;
              }}
            >
              {STORY.numbers.error_pick_km.toFixed(2)}
            </span>{" "}
            km
          </p>
          <p className="story-card-note">
            {COPY.cardNote}. Down from {STORY.numbers.error_none_km.toFixed(2)} km with no new
            sensors.
          </p>
          <svg className="story-spark" viewBox="-4 -4 208 56" aria-hidden="true">
            <path
              ref={(node) => {
                els.current.spark = node;
              }}
              d={SPARK.d}
            />
            <circle className="spark-expert" cx={SPARK.expert[0]} cy={SPARK.expert[1]} r="3.5" />
            <circle className="spark-pick" cx={SPARK.pick[0]} cy={SPARK.pick[1]} r="4.5" />
          </svg>
          <p className="story-card-key">
            <span className="key-pick" aria-hidden="true" /> our pick, {STORY.pick_position + 1} of{" "}
            {STORY.sorted_errors.length}
            <span className="key-expert" aria-hidden="true" /> field rule,{" "}
            {STORY.expert_position + 1}
          </p>
        </div>
        <ol className="story-pipeline">
          {PIPELINE.map((row, i) => (
            <li
              key={row.href}
              ref={(node) => {
                if (node) els.current.rows[i] = node;
              }}
            >
              <Link href={row.href}>
                <span className="row-num">{String(i + 1).padStart(2, "0")}</span>
                {row.label}
              </Link>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return reduced;
}

export function Story() {
  const reduced = usePrefersReducedMotion();
  if (reduced) {
    // No pinned scroll, zoom or blur: the opening view, the text, then the final view.
    return (
      <div className="story story-static">
        <StoryStage fixed={0} />
        <div className="story-static-text">
          <p className="story-static-fly">{COPY.fly}</p>
          <p>{COPY.landscape}</p>
        </div>
        <StoryStage fixed={0.9} />
      </div>
    );
  }
  return (
    <section className="story" aria-label="The story of one earthquake">
      <StoryStage />
    </section>
  );
}
