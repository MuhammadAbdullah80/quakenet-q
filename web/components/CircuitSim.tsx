"use client";

import { useEffect, useRef, useState } from "react";

// What the backend is doing while a run is in progress, drawn as the circuit's steps: prepare every
// network of exactly 4 of the 10 sites, then each layer scores the networks and mixes between them,
// then the circuit is measured. A sweep moves through the steps; it illustrates the order of the
// work, not the circuit's live state, which the backend does not report until the run finishes.

const SITES = 10;

type Block = { kind: "prep" | "score" | "mix" | "measure"; label: string; x0: number; x1: number };

function layout(layers: number, w: number, left: number): Block[] {
  const units = 1.4 + layers * 2 + 1.1;
  const unit = (w - left - 12) / units;
  const blocks: Block[] = [];
  let x = left;
  const push = (kind: Block["kind"], label: string, size: number) => {
    blocks.push({ kind, label, x0: x + 4, x1: x + size * unit - 4 });
    x += size * unit;
  };
  push("prep", "Prepare: every 4 of 10", 1.4);
  for (let r = 1; r <= layers; r += 1) {
    push("score", layers > 1 ? `Layer ${r}: score` : "Score", 1);
    push("mix", "Mix", 1);
  }
  push("measure", "Measure", 1.1);
  return blocks;
}

export function CircuitSim({
  layers,
  shots,
  status,
  demo = false,
}: {
  layers: number;
  shots: number;
  status: string;
  /** Explaining how a run works (demo), rather than watching one in progress. */
  demo?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed((Date.now() - started) / 1000), 500);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const mono = getComputedStyle(document.documentElement).getPropertyValue("--font-mono").trim();
    let w = 0;
    let h = 0;
    let raf = 0;
    const nLayers = Math.max(1, Math.min(5, layers));

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (now: number) => {
      ctx.clearRect(0, 0, w, h);
      const left = w < 520 ? 34 : 54;
      const top = 30;
      const gap = (h - top - 14) / (SITES - 1);
      const wireY = (i: number) => top + i * gap;
      const blocks = layout(nLayers, w, left);
      const end = blocks[blocks.length - 1].x1;
      const period = 2600 + nLayers * 900;
      const sweep = reduce ? -1 : left + (((now % period) / period) * (end - left + 40) - 20);

      // Wires and site labels.
      ctx.font = `500 ${w < 520 ? 9 : 10.5}px ${mono || "monospace"}, monospace`;
      ctx.textBaseline = "middle";
      for (let i = 0; i < SITES; i += 1) {
        const y = wireY(i);
        ctx.fillStyle = "rgba(231, 235, 232, 0.7)";
        ctx.textAlign = "right";
        ctx.fillText(w < 520 ? String(i) : `site ${i}`, left - 8, y);
        ctx.strokeStyle = "rgba(231, 235, 232, 0.22)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(end + 6, y);
        ctx.stroke();
        // The part of the wire the sweep has passed glows a little.
        if (sweep > left) {
          ctx.strokeStyle = "rgba(231, 235, 232, 0.55)";
          ctx.beginPath();
          ctx.moveTo(left, y);
          ctx.lineTo(Math.min(sweep, end + 6), y);
          ctx.stroke();
        }
      }

      for (const b of blocks) {
        const active = sweep >= b.x0 && sweep <= b.x1 + 8;
        const done = reduce || sweep > b.x1 + 8;
        const a = active ? 1 : done ? 0.6 : 0.28;
        ctx.textAlign = "center";
        ctx.fillStyle = `rgba(231, 235, 232, ${active ? 1 : 0.6})`;
        ctx.textBaseline = "alphabetic";
        if (b.x1 - b.x0 > 40) ctx.fillText(b.label, (b.x0 + b.x1) / 2, top - 14);
        ctx.textBaseline = "middle";

        if (b.kind === "prep") {
          ctx.fillStyle = `rgba(231, 235, 232, ${0.08 + 0.14 * a})`;
          ctx.strokeStyle = `rgba(231, 235, 232, ${a})`;
          ctx.lineWidth = 1.3;
          ctx.beginPath();
          ctx.roundRect(b.x0, wireY(0) - 9, b.x1 - b.x0, wireY(SITES - 1) - wireY(0) + 18, 4);
          ctx.fill();
          ctx.stroke();
        } else if (b.kind === "score") {
          // Links between sites: the score has terms for pairs, triples and groups of four.
          const pairs = [
            [0, 3],
            [1, 6],
            [2, 8],
            [4, 7],
            [5, 9],
          ];
          pairs.forEach(([p, q], k) => {
            const x = b.x0 + ((k + 0.5) / pairs.length) * (b.x1 - b.x0);
            ctx.strokeStyle = `rgba(231, 235, 232, ${a})`;
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(x, wireY(p));
            ctx.lineTo(x, wireY(q));
            ctx.stroke();
            for (const i of [p, q]) {
              ctx.beginPath();
              ctx.arc(x, wireY(i), 3.2, 0, Math.PI * 2);
              ctx.fillStyle = `rgba(231, 235, 232, ${a})`;
              ctx.fill();
            }
          });
        } else if (b.kind === "mix") {
          // Neighbouring sites swap places: the mixer keeps exactly 4 chosen.
          for (let i = 0; i < SITES - 1; i += 2) {
            const x = (b.x0 + b.x1) / 2 + (i % 4 === 0 ? -6 : 6);
            ctx.strokeStyle = `rgba(231, 235, 232, ${a})`;
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(x - 7, wireY(i));
            ctx.lineTo(x + 7, wireY(i + 1));
            ctx.moveTo(x - 7, wireY(i + 1));
            ctx.lineTo(x + 7, wireY(i));
            ctx.stroke();
          }
        } else {
          for (let i = 0; i < SITES; i += 1) {
            const y = wireY(i);
            const cx = (b.x0 + b.x1) / 2;
            ctx.strokeStyle = `rgba(231, 235, 232, ${a})`;
            ctx.fillStyle = `rgba(16, 41, 26, 1)`;
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.roundRect(cx - 9, y - 7, 18, 14, 2);
            ctx.fill();
            ctx.stroke();
            // A meter needle that swings while this step is active.
            const swing = active ? Math.sin(now / 140 + i) * 0.6 : -0.5;
            ctx.beginPath();
            ctx.moveTo(cx, y + 4);
            ctx.lineTo(cx + Math.sin(swing) * 7, y + 4 - Math.cos(swing) * 7);
            ctx.stroke();
          }
        }
      }

      if (sweep > left && sweep < end + 10) {
        const g = ctx.createLinearGradient(sweep - 40, 0, sweep, 0);
        g.addColorStop(0, "rgba(231, 235, 232, 0)");
        g.addColorStop(1, "rgba(231, 235, 232, 0.12)");
        ctx.fillStyle = g;
        ctx.fillRect(sweep - 40, top - 10, 40, h - top);
        ctx.strokeStyle = "rgba(231, 235, 232, 0.9)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(sweep, top - 10);
        ctx.lineTo(sweep, h - 4);
        ctx.stroke();
      }
    };

    const loop = (now: number) => {
      draw(now);
      raf = requestAnimationFrame(loop);
    };
    resize();
    if (reduce) draw(0);
    else raf = requestAnimationFrame(loop);
    const ro = new ResizeObserver(() => {
      resize();
      if (reduce) draw(0);
    });
    ro.observe(canvas);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [layers]);

  return (
    <figure className="circuit">
      <div className="circuit-head">
        <span className="circuit-status">
          <span className="circuit-dot" aria-hidden="true" />
          {demo
            ? "How one run works"
            : status === "queued"
              ? "Waiting for the backend"
              : "Running on the simulator"}
        </span>
        {demo ? null : <span className="circuit-time">{Math.floor(elapsed)} s</span>}
      </div>
      <canvas ref={canvasRef} aria-hidden="true" />
      <figcaption>
        {demo ? "The steps of a run:" : "The steps of this run:"} prepare every network of 4 sites
        at once, then {layers} {layers === 1 ? "layer" : "layers"} of score and mix, then {shots}{" "}
        measurements. A run takes about a minute. This shows the order of the work, not the
        circuit&apos;s live state.
      </figcaption>
    </figure>
  );
}
