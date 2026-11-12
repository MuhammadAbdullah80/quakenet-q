"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

// A full-screen walkthrough for presenting or recording: one idea per scene, a big caption, the
// real saved results animating underneath. Arrow keys or space move between scenes, P plays them
// on a timer, F toggles full screen, Escape leaves full screen.

export type Scene = {
  id: string;
  kicker: string;
  title: string;
  caption: string;
  content: ReactNode;
};

const SCENE_MS = 8000;

export function DemoPresenter({ scenes, savedTag }: { scenes: Scene[]; savedTag: string }) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const last = scenes.length - 1;

  const go = useCallback((i: number) => setIndex(Math.max(0, Math.min(last, i))), [last]);

  const toggleFull = useCallback(() => {
    const el = rootRef.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen?.();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      if (e.key === "ArrowRight" || e.key === " " || e.key === "PageDown") {
        e.preventDefault();
        setPlaying(false);
        setIndex((i) => Math.min(last, i + 1));
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        setPlaying(false);
        setIndex((i) => Math.max(0, i - 1));
      } else if (e.key === "Home") {
        setIndex(0);
      } else if (e.key === "End") {
        setIndex(last);
      } else if (e.key.toLowerCase() === "f") {
        toggleFull();
      } else if (e.key.toLowerCase() === "p") {
        setPlaying((p) => !p);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [last, toggleFull]);

  // Autoplay: move on every few seconds, stop at the last scene.
  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(() => {
      if (index >= last) setPlaying(false);
      else setIndex(index + 1);
    }, SCENE_MS);
    return () => window.clearTimeout(timer);
  }, [playing, index, last]);

  const scene = scenes[index];

  return (
    <div className="demo" ref={rootRef}>
      <div className="demo-top">
        <Link href="/" className="demo-brand">
          <span className="brand-mark" aria-hidden="true" />
          QuakeNet-Q
        </Link>
        <span className="demo-tag">{savedTag}</span>
        <Link href="/events" className="demo-exit">
          Leave the demo
        </Link>
      </div>

      <section className="demo-stage" aria-live="polite" aria-labelledby={`scene-${scene.id}`}>
        <div className="demo-text" key={`t-${scene.id}`}>
          <p className="demo-kicker">
            {String(index + 1).padStart(2, "0")} / {String(scenes.length).padStart(2, "0")} ·{" "}
            {scene.kicker}
          </p>
          <h1 id={`scene-${scene.id}`}>{scene.title}</h1>
          <p className="demo-caption">{scene.caption}</p>
        </div>
        <div className="demo-visual" key={`v-${scene.id}`}>
          {scene.content}
        </div>
      </section>

      <div className="demo-controls">
        <button
          type="button"
          className="secondary"
          onClick={() => go(index - 1)}
          disabled={index === 0}
        >
          Back
        </button>
        <button
          type="button"
          className="demo-play"
          onClick={() => setPlaying((p) => !p)}
          aria-pressed={playing}
        >
          <span className={playing ? "icon-pause" : "icon-play"} aria-hidden="true" />
          {playing ? "Pause" : "Play"}
        </button>
        <button type="button" onClick={() => go(index + 1)} disabled={index === last}>
          Next
        </button>
        <ol className="demo-dots" aria-label="Scenes">
          {scenes.map((s, i) => (
            <li key={s.id}>
              <button
                type="button"
                className={i === index ? "is-on" : undefined}
                aria-current={i === index ? "step" : undefined}
                aria-label={`Scene ${i + 1}: ${s.kicker}`}
                onClick={() => {
                  setPlaying(false);
                  go(i);
                }}
              >
                {playing && i === index ? <span className="demo-dot-fill" /> : null}
              </button>
            </li>
          ))}
        </ol>
        <button type="button" className="secondary demo-full" onClick={toggleFull}>
          Full screen
        </button>
        <span className="demo-keys">Arrow keys to move · P to play · F for full screen</span>
      </div>
    </div>
  );
}
