"use client";

import { usePathname } from "next/navigation";
import { Suspense } from "react";

// One plain sentence on every console page: which step of the process this is and what happens
// here. The main navbar is the only navigation.

const STEPS = [
  {
    paths: ["/events", "/feed"],
    now: "An earthquake has happened. Pick it here; everything after this works on its aftershocks.",
  },
  {
    paths: ["/candidates"],
    now: "There are 10 places a portable sensor could go. Here you see them with the aftershocks so far.",
  },
  {
    paths: ["/scoring"],
    now: "There are 210 ways to choose 4 of the 10 sites. Each one gets a score for how well it would locate aftershocks.",
  },
  {
    paths: ["/quantum"],
    now: "A quantum circuit searches those 210 choices and lands on the good ones far more often than chance.",
  },
  {
    paths: ["/self-check"],
    now: "The quantum answer is checked against the exact best answer and against simpler methods.",
  },
  {
    paths: ["/plan"],
    now: "The agent turns the answer into a plan: where each sensor goes and why.",
  },
  {
    paths: ["/monitor"],
    now: "As new aftershocks arrive, the agent checks every hour and moves a sensor if they drift.",
  },
] as const;

const BEHIND: Record<string, string> = {
  "/memory": "Behind the scenes: what the agent remembers between earthquakes.",
  "/noise": "Behind the scenes: how errors in real quantum hardware would affect the circuit.",
  "/settings": "Behind the scenes: the numbers the agent works with.",
  "/system": "Behind the scenes: whether the backend is running, and where the data comes from.",
};

function Strip() {
  const path = usePathname() ?? "";
  const at = STEPS.findIndex((s) => (s.paths as readonly string[]).includes(path));

  if (at < 0) {
    const note = BEHIND[path];
    return note ? <p className="steps-note">{note}</p> : null;
  }
  return (
    <p className="steps-now">
      <strong>
        Step {at + 1} of {STEPS.length}.
      </strong>{" "}
      {STEPS[at].now}
    </p>
  );
}

export function StepStrip() {
  return (
    <Suspense fallback={null}>
      <Strip />
    </Suspense>
  );
}
