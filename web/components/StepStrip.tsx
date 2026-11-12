"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";

// Where this page sits in the whole story, with one plain sentence about what happens here.
// Shown on every console page, so a newcomer always knows the step and what comes next.

const STEPS = [
  {
    paths: ["/events", "/feed"],
    href: "/events",
    short: "Pick an earthquake",
    now: "An earthquake has happened. Pick it here; everything after this works on its aftershocks.",
  },
  {
    paths: ["/candidates"],
    href: "/candidates",
    short: "Find sites",
    now: "There are 10 places a portable sensor could go. Here you see them with the aftershocks so far.",
  },
  {
    paths: ["/scoring"],
    href: "/scoring",
    short: "Score every choice",
    now: "There are 210 ways to choose 4 of the 10 sites. Each one gets a score for how well it would locate aftershocks.",
  },
  {
    paths: ["/quantum"],
    href: "/quantum",
    short: "Quantum pick",
    now: "A quantum circuit searches those 210 choices and lands on the good ones far more often than chance.",
  },
  {
    paths: ["/self-check"],
    href: "/self-check",
    short: "Check it",
    now: "The quantum answer is checked against the exact best answer and against simpler methods.",
  },
  {
    paths: ["/plan"],
    href: "/plan",
    short: "Plan",
    now: "The agent turns the answer into a plan: where each sensor goes and why.",
  },
  {
    paths: ["/monitor"],
    href: "/monitor",
    short: "Watch and re-plan",
    now: "As new aftershocks arrive, the agent checks every hour and moves a sensor if they drift.",
  },
] as const;

const BEHIND: Record<string, string> = {
  "/memory": "Behind the scenes: what the agent remembers between earthquakes.",
  "/noise": "Behind the scenes: how errors in real quantum hardware would affect the circuit.",
  "/settings": "Behind the scenes: the numbers the agent works with.",
  "/system": "Behind the scenes: whether the backend is running, and where the data comes from.",
};

const EVENT_ID = /^[A-Za-z0-9_-]{1,64}$/;

function Strip() {
  const path = usePathname() ?? "";
  const params = useSearchParams();
  const event = params.get("event");
  const query = event && EVENT_ID.test(event) ? `?event=${event}` : "";
  const at = STEPS.findIndex((s) => (s.paths as readonly string[]).includes(path));

  if (at < 0) {
    const note = BEHIND[path];
    return note ? <p className="steps-note">{note}</p> : null;
  }
  return (
    <nav className="steps" aria-label="Where this page sits in the process">
      <ol>
        {STEPS.map((s, i) => (
          <li key={s.href} className={i < at ? "is-done" : i === at ? "is-now" : undefined}>
            <Link href={`${s.href}${query}`} aria-current={i === at ? "step" : undefined}>
              <span className="steps-num">{i + 1}</span>
              <span className="steps-name">{s.short}</span>
            </Link>
          </li>
        ))}
      </ol>
      <p className="steps-now">
        <strong>
          Step {at + 1} of {STEPS.length}.
        </strong>{" "}
        {STEPS[at].now}
      </p>
    </nav>
  );
}

export function StepStrip() {
  return (
    <Suspense fallback={null}>
      <Strip />
    </Suspense>
  );
}
