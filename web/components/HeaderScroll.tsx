"use client";

import { useEffect } from "react";

// On console pages the header sticks to the top, slides away while you scroll down and comes
// back as soon as you scroll up. It never hides while keyboard focus is inside it.
export function HeaderScroll() {
  useEffect(() => {
    const header = document.querySelector<HTMLElement>(".site-header");
    if (!header) return;
    let last = window.scrollY;
    let frame = 0;
    const update = () => {
      frame = 0;
      const y = window.scrollY;
      const delta = y - last;
      header.dataset.scrolled = String(y > 8);
      // Only keyboard focus pins it; a mouse click also leaves focus on the link.
      if (header.querySelector(":focus-visible") || y < header.offsetHeight) {
        header.dataset.hidden = "false";
      } else if (delta > 6) {
        header.dataset.hidden = "true";
      } else if (delta < -6) {
        header.dataset.hidden = "false";
      }
      if (Math.abs(delta) > 6) last = y;
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    const onFocus = () => {
      if (header.querySelector(":focus-visible")) header.dataset.hidden = "false";
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    header.addEventListener("focusin", onFocus);
    return () => {
      window.removeEventListener("scroll", onScroll);
      header.removeEventListener("focusin", onFocus);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);
  return null;
}
