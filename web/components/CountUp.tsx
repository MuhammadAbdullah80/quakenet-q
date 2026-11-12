"use client";

import { useEffect } from "react";

// Headline numbers (KPI tiles, home stats, feed counts) count up once when they scroll into view.
// The page always renders the real text; this only animates toward it and ends on the exact
// original string. Skipped under reduced motion. Screen readers read the final value.

const SELECTOR = ".kpis dd, .run-stats dd, .status-count, .lift-x";
const NUMBER = /^(\D*?)(\d[\d,]*(?:\.\d+)?)([\s\S]*)$/;
const MS = 900;

function animate(el: HTMLElement) {
  const original = el.textContent ?? "";
  const m = NUMBER.exec(original.trim());
  if (!m) return;
  const [, pre, num, post] = m;
  const target = Number(num.replace(/,/g, ""));
  if (!Number.isFinite(target) || target === 0) return;
  const decimals = num.includes(".") ? num.split(".")[1].length : 0;
  el.setAttribute("aria-label", original.trim());
  const start = performance.now();
  const step = (now: number) => {
    const t = Math.min(1, (now - start) / MS);
    const eased = 1 - (1 - t) ** 3;
    if (t < 1) {
      el.textContent = `${pre}${(target * eased).toFixed(decimals)}${post}`;
      requestAnimationFrame(step);
    } else {
      el.textContent = original;
      el.removeAttribute("aria-label");
    }
  };
  requestAnimationFrame(step);
}

export function CountUp() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          io.unobserve(entry.target);
          animate(entry.target as HTMLElement);
        }
      },
      { threshold: 0.6 },
    );
    const seen = new WeakSet<Element>();
    // Only touch numbers React has already hydrated: streamed content arrives as plain HTML first,
    // and changing it before React takes over causes a hydration mismatch.
    const hydrated = (el: Element) => Object.keys(el).some((k) => k.startsWith("__reactFiber"));
    const scan = () => {
      document.querySelectorAll<HTMLElement>(SELECTOR).forEach((el) => {
        if (seen.has(el) || !hydrated(el)) return;
        // Only plain text values; anything with markup inside is left alone.
        if (el.children.length > 0) return;
        seen.add(el);
        io.observe(el);
      });
    };
    scan();
    // Sections stream in after the first paint; pick up new tiles as they arrive.
    let timer = 0;
    const later = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(scan, 400);
    };
    const mo = new MutationObserver(later);
    const main = document.getElementById("main");
    if (main) mo.observe(main, { childList: true, subtree: true });
    later();
    return () => {
      window.clearTimeout(timer);
      io.disconnect();
      mo.disconnect();
    };
  }, []);
  return null;
}
