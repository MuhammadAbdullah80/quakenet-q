"use client";

import { useEffect, useSyncExternalStore } from "react";

// Dark green is the base; this switches to the light theme and back, and remembers the choice.
// The theme lives on <html data-theme>; the button reads it from there so it is never out of step.
type Theme = "dark" | "light";
const KEY = "qn-theme";
const EVENT = "qn-theme-change";

const read = (): Theme => (document.documentElement.dataset.theme === "light" ? "light" : "dark");
const subscribe = (notify: () => void) => {
  window.addEventListener(EVENT, notify);
  return () => window.removeEventListener(EVENT, notify);
};

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  window.dispatchEvent(new Event(EVENT));
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, read, () => "dark" as Theme);

  // Restore a saved choice once on load.
  useEffect(() => {
    try {
      if (window.localStorage.getItem(KEY) === "light") apply("light");
    } catch {
      // Storage can be unavailable (private windows); keep the default.
    }
  }, []);

  const flip = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    apply(next);
    try {
      window.localStorage.setItem(KEY, next);
    } catch {
      // The theme still changes for this visit.
    }
  };

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={flip}
      aria-label={theme === "dark" ? "Switch to the light theme" : "Switch to the dark green theme"}
    >
      <svg viewBox="0 0 16 16" aria-hidden="true">
        {theme === "dark" ? (
          <>
            <circle cx="8" cy="8" r="3" />
            <path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M3.4 12.6l1.1-1.1M11.5 4.5l1.1-1.1" />
          </>
        ) : (
          <path d="M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5z" />
        )}
      </svg>
      {theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}
