import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { LIMITS, SEQUENCE_LIMITS } from "@/lib/limits";
import savedJob from "@/snapshots/job.json";

export const metadata: Metadata = {
  title: "Guide",
  description: "How to use the QuakeNet-Q console, and what every map, chart and number means.",
};

const runSeconds = Math.round(savedJob.result.seconds);

const SECTIONS = [
  { id: "what", title: "What this site does" },
  { id: "live", title: "Live and offline" },
  { id: "pages", title: "The pages, one by one" },
  { id: "map", title: "Reading the map" },
  { id: "numbers", title: "Every number, explained" },
  { id: "run", title: "Starting a quantum run" },
  { id: "result", title: "What a result means" },
  { id: "limits", title: "Limits" },
] as const;

const PAGES: { href: string; name: string; what: ReactNode }[] = [
  {
    href: "/events",
    name: "Events",
    what: "The earthquakes the backend can plan for. Pick one here; the other pages remember your choice.",
  },
  {
    href: "/feed",
    name: "Live feed",
    what: "Real earthquakes from the past 24 hours, which ones are big enough to start the agent, and what it did with each.",
  },
  {
    href: "/candidates",
    name: "Candidates",
    what: "The map: aftershocks, permanent stations and the ten candidate sites, with a table of each.",
  },
  {
    href: "/scoring",
    name: "Scoring",
    what: "How every possible network is scored, and the best ones. You can change the risk weight and score again.",
  },
  {
    href: "/quantum",
    name: "Quantum",
    what: "Start a run of the quantum circuit, watch it, and see which networks it measured most often.",
  },
  {
    href: "/self-check",
    name: "Self-check",
    what: "The quantum pick next to the exact best network and the classical methods, with the location error of each.",
  },
  {
    href: "/plan",
    name: "Plan",
    what: "The agent's current plan: each site with the reason it was chosen, its risk, backup spots and a confidence rating.",
  },
  {
    href: "/monitor",
    name: "Monitor",
    what: "Replay a past earthquake hour by hour: aftershocks arriving, checks, re-plans and sensor moves on the map.",
  },
  {
    href: "/memory",
    name: "Memory",
    what: "What the agent has learned: circuit settings that worked, how much it trusts each travel-time model, how good its predictions were.",
  },
  {
    href: "/noise",
    name: "Noise study",
    what: "How the circuit copes when its gates make errors. A simulation on a smaller problem, not a hardware run.",
  },
  {
    href: "/settings",
    name: "Settings",
    what: "The values the agent works with, such as the magnitude that starts it. Saving needs the passcode.",
  },
  {
    href: "/system",
    name: "System",
    what: "Backend health, job counts, cached data sources and recent jobs.",
  },
];

type Term = { term: string; meaning: string; unit: string; better: string };

const TERMS: Term[] = [
  {
    term: "Candidate site",
    meaning: "A place where a portable sensor could go. Numbered 0 to 9.",
    unit: "",
    better: "",
  },
  { term: "Network", meaning: "One choice of 4 candidate sites.", unit: "", better: "" },
  {
    term: "Permanent station",
    meaning: "A sensor that was already there before the earthquake.",
    unit: "",
    better: "",
  },
  {
    term: "Aftershocks used to plan",
    meaning: "The aftershocks of the first hours, which the planner is allowed to see.",
    unit: "count",
    better: "",
  },
  {
    term: "Later aftershocks",
    meaning:
      "Aftershocks after the planning time. The planner never sees them; they are used only to test the plan.",
    unit: "count",
    better: "",
  },
  {
    term: "Risk",
    meaning: "How hard or dangerous a site is to reach.",
    unit: "0 to 1",
    better: "Lower",
  },
  {
    term: "Risk weight (lam)",
    meaning: `How strongly risk counts against a site. Default ${LIMITS.lam.default}.`,
    unit: `${LIMITS.lam.min} to ${LIMITS.lam.max}`,
    better: "Your choice",
  },
  {
    term: "Objective",
    meaning:
      "The score of a network: how much it improves locating aftershocks, minus the risk weight times its risk.",
    unit: "points",
    better: "Higher",
  },
  {
    term: "Rank",
    meaning: "Position of a network among all 210 possible ones, by objective.",
    unit: "1 to 210",
    better: "Lower (1 is best)",
  },
  {
    term: "Blur",
    meaning: "The predicted uncertainty when locating an aftershock with this network.",
    unit: "km",
    better: "Lower",
  },
  {
    term: "Location error",
    meaning:
      "The error measured in a simulated test: later aftershocks are located with the network and compared with where they really were.",
    unit: "km",
    better: "Lower",
  },
  {
    term: "Chance one measurement gives the best network (p_opt)",
    meaning: "How often a single measurement of the circuit lands on the best network.",
    unit: "%",
    better: "Higher",
  },
  {
    term: "Same chance for a random pick",
    meaning: "What p_opt would be if you picked one of the 210 networks at random: 1 in 210.",
    unit: "%",
    better: "",
  },
  {
    term: "Quantum compared with random",
    meaning: "p_opt divided by the random chance.",
    unit: "times",
    better: "Higher",
  },
  {
    term: "Approximation ratio",
    meaning:
      "Where the circuit's average result sits between the worst network (0) and the best (1).",
    unit: "0 to 1",
    better: "Higher",
  },
  {
    term: "Valid networks measured",
    meaning:
      "Share of measurements that picked exactly 4 sites. The circuit is built so this should be 100%.",
    unit: "%",
    better: "Higher",
  },
  {
    term: "Circuit depth, gates",
    meaning: "How long and how big the quantum circuit is.",
    unit: "count",
    better: "Lower is cheaper",
  },
  {
    term: "Rank agreement (Spearman)",
    meaning: "How well a simplified score orders the networks the same way as the exact score.",
    unit: "-1 to 1",
    better: "Higher (1 is perfect)",
  },
  {
    term: "Confidence",
    meaning:
      "How far the agent trusts a plan, from how well its past plans predicted their own score.",
    unit: "high, medium, low",
    better: "Higher",
  },
  {
    term: "Drift",
    meaning:
      "New aftershocks moving away from where the plan expected them. Enough drift makes the agent re-plan.",
    unit: "",
    better: "",
  },
];

function Swatch({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" className="guide-swatch">
      {children}
    </svg>
  );
}

export default function GuidePage() {
  return (
    <div className="guide">
      <aside className="guide-toc" aria-labelledby="toc-heading">
        <p id="toc-heading" className="guide-toc-title">
          On this page
        </p>
        <ol>
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`}>{s.title}</a>
            </li>
          ))}
        </ol>
      </aside>

      <article className="guide-body">
        <h1>Guide</h1>
        <p className="lede">
          How to use this site, written for someone new to both earthquakes and quantum computing.
        </p>

        <section id="what" aria-labelledby="what-h">
          <h2 id="what-h">What this site does</h2>
          <p>
            After a big earthquake, a response team puts a few portable seismometers (sensors that
            record ground shaking) near the aftershocks, so the aftershocks can be located sharply.
            QuakeNet-Q decides which 4 of 10 possible places to use. A quantum optimisation
            algorithm makes the choice, and an exact search of all 210 possible choices checks it.
          </p>
          <p>
            The <Link href="/">home page</Link> tells the story of one real earthquake: Ridgecrest,
            California, 2019. The other pages are a test console, one page per step.
          </p>
        </section>

        <section id="live" aria-labelledby="live-h">
          <h2 id="live-h">Live and offline</h2>
          <p>
            The quantum circuit and the agent run in a Python program on a team laptop. This site
            talks to it from its own server; your browser never contacts the laptop.
          </p>
          <div className="notice notice-offline">
            <p className="notice-title">Offline: showing saved results</p>
            <p>
              This banner means the laptop is not reachable right now. Every page still works, using
              real results saved earlier. Only starting new runs is switched off.
            </p>
          </div>
          <p>
            <strong>The passcode</strong> is for starting a quantum run, starting a replay or saving
            settings. Each of these uses the laptop&apos;s processor, so only the team can start
            them. Reading never needs the passcode.
          </p>
        </section>

        <section id="pages" aria-labelledby="pages-h">
          <h2 id="pages-h">The pages, one by one</h2>
          <dl className="guide-pages">
            {PAGES.map((p) => (
              <div key={p.href}>
                <dt>
                  <Link href={p.href}>{p.name}</Link>
                </dt>
                <dd>{p.what}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section id="map" aria-labelledby="map-h">
          <h2 id="map-h">Reading the map</h2>
          <p>
            The map is a flat grid in kilometres around the mainshock: x points east, y points
            north, and north is up. For Ridgecrest it sits on shaded relief drawn from real
            elevation data, so you can see the valleys and ranges.
          </p>
          <ul className="guide-legend">
            <li>
              <Swatch>
                <polygon
                  className="map-mainshock"
                  strokeWidth="1"
                  points="10,1 12.1,7.1 18.6,7.2 13.4,11.1 15.3,17.3 10,13.6 4.7,17.3 6.6,11.1 1.4,7.2 7.9,7.1"
                />
              </Swatch>
              <span>
                <strong>Star:</strong> the mainshock, the big earthquake itself.
              </span>
            </li>
            <li>
              <Swatch>
                <circle className="map-design" cx="10" cy="10" r="4" />
              </Swatch>
              <span>
                <strong>Filled dots:</strong> aftershocks the planner could see.
              </span>
            </li>
            <li>
              <Swatch>
                <circle className="map-valid" cx="10" cy="10" r="5" strokeWidth="2" />
              </Swatch>
              <span>
                <strong>Open dots:</strong> later aftershocks, kept back to test the plan.
              </span>
            </li>
            <li>
              <Swatch>
                <polygon className="map-station" strokeWidth="1" points="10,2 2.8,16 17.2,16" />
              </Swatch>
              <span>
                <strong>Triangles:</strong> permanent stations, with their codes.
              </span>
            </li>
            <li>
              <Swatch>
                <circle className="map-candidate" cx="10" cy="10" r="8" fill="rgb(255,243,214)" />
              </Swatch>
              <span>
                <strong>Numbered circles:</strong> the candidate sites. Pale means low risk, dark
                red means high risk.
              </span>
            </li>
            <li>
              <Swatch>
                <circle className="map-chosen-halo" cx="10" cy="10" r="7" strokeWidth="5" />
                <circle className="map-chosen" cx="10" cy="10" r="7" strokeWidth="3" />
              </Swatch>
              <span>
                <strong>Lime ring:</strong> a chosen site. Lime always means a sensor or a chosen
                site, nothing else.
              </span>
            </li>
            <li>
              <Swatch>
                <circle
                  className="map-secondary"
                  cx="10"
                  cy="10"
                  r="8"
                  strokeWidth="2"
                  strokeDasharray="4 3"
                />
              </Swatch>
              <span>
                <strong>Dashed ring:</strong> a second set to compare, such as the exact best
                network when the quantum pick differs, or a site a sensor just moved away from.
              </span>
            </li>
          </ul>
          <p className="small muted">
            Hover or focus a mark to see its name and value. The legend under each map lists only
            the marks on that map.
          </p>
        </section>

        <section id="numbers" aria-labelledby="numbers-h">
          <h2 id="numbers-h">Every number, explained</h2>
          <p>
            For each number: what it means, its unit, and whether higher or lower is better. A blank
            means neither.
          </p>
          <div className="table-wrap">
            <table>
              <caption className="visually-hidden">Terms used on the console pages</caption>
              <thead>
                <tr>
                  <th scope="col">Term</th>
                  <th scope="col">Meaning</th>
                  <th scope="col">Unit</th>
                  <th scope="col">Better</th>
                </tr>
              </thead>
              <tbody>
                {TERMS.map((t) => (
                  <tr key={t.term}>
                    <th scope="row">{t.term}</th>
                    <td>{t.meaning}</td>
                    <td className="nowrap">{t.unit}</td>
                    <td>{t.better}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section id="run" aria-labelledby="run-h">
          <h2 id="run-h">Starting a quantum run</h2>
          <p>
            On <Link href="/quantum">Quantum</Link>, enter the passcode, choose the settings and
            press <strong>Start run</strong>. The page checks the run every 2 seconds. A run takes
            about a minute: the saved run took {runSeconds} seconds with {LIMITS.reps.default}{" "}
            layer. More layers take longer.
          </p>
          <dl className="guide-pages">
            <div>
              <dt>Layers (reps)</dt>
              <dd>
                How many times the circuit repeats its two steps: one that rewards good networks and
                one that mixes between them. More layers are slower and usually find the best
                network more often. {LIMITS.reps.min} to {LIMITS.reps.max}, default{" "}
                {LIMITS.reps.default}.
              </dd>
            </div>
            <div>
              <dt>Random seed</dt>
              <dd>
                Fixes the random choices, so the same settings give the same result again.{" "}
                {LIMITS.seed.min} to {LIMITS.seed.max}, default {LIMITS.seed.default}.
              </dd>
            </div>
            <div>
              <dt>Measurements (shots)</dt>
              <dd>
                How many times the finished circuit is measured. Each measurement gives one network.
                {` ${LIMITS.shots.min} to ${LIMITS.shots.max}, default ${LIMITS.shots.default}.`}
              </dd>
            </div>
            <div>
              <dt>Risk weight (lam)</dt>
              <dd>
                How much a site&apos;s risk counts against it. 0 ignores risk; higher values avoid
                risky sites more. {LIMITS.lam.min} to {LIMITS.lam.max}, default {LIMITS.lam.default}
                .
              </dd>
            </div>
          </dl>
          <p>
            A replay on <Link href="/monitor">Monitor</Link> works the same way. It replays{" "}
            {SEQUENCE_LIMITS.hours.min} to {SEQUENCE_LIMITS.hours.max} hours, with a check every{" "}
            {SEQUENCE_LIMITS.step_hours.min} to {SEQUENCE_LIMITS.step_hours.max} hours.
          </p>
        </section>

        <section id="result" aria-labelledby="result-h">
          <h2 id="result-h">What a result means</h2>
          <ol className="guide-steps">
            <li>
              <strong>Chance per measurement against a random pick.</strong> With 210 networks, a
              random pick finds the best one 1 time in 210 (0.48%). If the circuit finds it 5% of
              the time, it is about ten times better than random. That is the headline number.
            </li>
            <li>
              <strong>Valid networks.</strong> The circuit is built so every measurement picks
              exactly 4 sites. This should read 100%.
            </li>
            <li>
              <strong>The final pick against the exact best.</strong> After measuring, the program
              scores the 10 networks measured most often and keeps the best of them. Because 210
              networks is few enough to check every one, the page can say for certain whether the
              quantum pick is the best. A green notice means it is; an amber one means it is not,
              and the exact best is shown with a dashed ring.
            </li>
            <li>
              <strong>The most measured network is not always the best one.</strong> The bar chart
              on Quantum can show another network measured more often. What matters is that the best
              network comes up far more often than chance, so it is among the measurements.
            </li>
          </ol>
        </section>

        <section id="limits" aria-labelledby="limits-h">
          <h2 id="limits-h">Limits</h2>
          <ul className="guide-limits">
            <li>
              <strong>Simulator only.</strong> The quantum circuit runs on a classical computer that
              simulates it. The noise study is a simulation too.
            </li>
            <li>
              <strong>No speedup claimed.</strong> At 210 options, checking every one is instant.
              The project shows the method works and can be checked, not that it is faster.
            </li>
            <li>
              <strong>Simplified physics.</strong> Simple wave-speed models, no 3D wave paths, and
              assumed noise levels for how far a sensor can hear.
            </li>
            <li>
              <strong>One earthquake studied in depth.</strong> Ridgecrest 2019 is the main case.
              Five more earthquakes have benchmark runs, and on only 1 of those 5 did the optimised
              network beat the field rule in the simulated location test. The score being optimised
              does not always predict the location error, and we report that as it is.
            </li>
          </ul>
        </section>
      </article>
    </div>
  );
}
