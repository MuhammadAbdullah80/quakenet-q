import type { Metadata } from "next";
import Link from "next/link";
import { BarChart } from "@/components/BarChart";
import { CircuitSim } from "@/components/CircuitSim";
import { DemoPresenter, type Scene } from "@/components/DemoPresenter";
import { QuakeGlobe } from "@/components/QuakeGlobe";
import { SiteMap } from "@/components/SiteMap";
import { fmt, fmtSites, sameSites } from "@/lib/format";
import { sequenceMapData } from "@/lib/sequence";
import { snapshots } from "@/lib/snapshots";
import { listAnd } from "@/lib/story-data";

// A presenter walkthrough for demos and video. Every scene animates the saved results that ship
// with the site (the same files offline mode uses), so nothing on screen is invented.

export const metadata: Metadata = {
  title: "Demo",
  description: "A step-by-step walkthrough of QuakeNet-Q for presenting and recording.",
};

export default function DemoPage() {
  const events = snapshots.events();
  const eventId = events?.data.events.find((e) => e.available)?.id ?? "ridgecrest2019";
  const event = events?.data.events.find((e) => e.id === eventId);
  const instance = snapshots.instance(eventId);
  const job = snapshots.job(eventId);
  const sequence = snapshots.sequence(eventId);
  const anyMock = [events, instance, job, sequence].some((s) => s?.mock);
  const result = job?.data.result ?? null;
  const inst = instance?.data ?? null;

  const scenes: Scene[] = [];

  scenes.push({
    id: "quake",
    kicker: "The problem",
    title: "Where do the sensors go?",
    caption:
      "After a big earthquake, a response team has a handful of portable sensors and a few hours to place them, so the aftershocks can be located sharply.",
    content: (
      <QuakeGlobe
        label={event ? `${event.name}, magnitude ${fmt(event.magnitude, 1)}` : "The earthquakes"}
        dotLabel="earthquake"
        flagLabel="the case in this demo"
        points={(events?.data.events ?? [])
          .filter((e) => typeof e.lat === "number" && typeof e.lon === "number")
          .map((e) => ({
            id: e.id,
            lat: e.lat as number,
            lon: e.lon as number,
            mag: e.magnitude,
            title: e.name,
            detail: `M ${fmt(e.magnitude, 1)}`,
            flag: e.id === eventId,
          }))}
      />
    ),
  });

  if (inst) {
    scenes.push({
      id: "sites",
      kicker: "The data",
      title: `${inst.n} places a sensor could go`,
      caption: `Real aftershocks from the first ${inst.decision_hours} hours, the stations that were already there, and ${inst.n} candidate sites. Darker sites are harder to reach.`,
      content: <SiteMap instance={inst} title={`Aftershocks and candidate sites`} />,
    });
  }

  if (result) {
    scenes.push({
      id: "circuit",
      kicker: "The quantum step",
      title: "One circuit weighs every choice at once",
      caption:
        "The circuit starts with every network of 4 sites in play, then layers that reward good networks and mix between them. Measuring it picks one network.",
      content: <CircuitSim layers={result.reps} shots={result.shots} status="done" demo />,
    });

    const top = result.top_counts.slice(0, 6);
    scenes.push({
      id: "counts",
      kicker: "The measurements",
      title: "The best network keeps coming up",
      caption: `Out of ${result.shots} measurements, the best possible network (lime) came up again and again.`,
      content: (
        <BarChart
          title="How often each network was measured"
          note="The six networks measured most often."
          unit="times"
          digits={0}
          items={top.map((row) => ({
            label: fmtSites(row.sites),
            value: row.count,
            highlight: sameSites(row.sites, result.exact_optimum),
          }))}
          highlightLabel="Best possible network"
        />
      ),
    });

    const lift = result.uniform_p_opt > 0 ? result.p_opt / result.uniform_p_opt : null;
    if (lift !== null) {
      scenes.push({
        id: "lift",
        kicker: "The result",
        title: `${fmt(lift, 1)} times better than guessing`,
        caption:
          "One measurement of the circuit finds the best network far more often than picking at random would.",
        content: (
          <div className="demo-lift">
            <div className="demo-lift-row">
              <span>Quantum circuit</span>
              <span className="demo-lift-track">
                <span className="demo-lift-fill is-q" style={{ width: "100%" }} />
              </span>
            </div>
            <div className="demo-lift-row">
              <span>Random pick</span>
              <span className="demo-lift-track">
                <span
                  className="demo-lift-fill"
                  style={{ width: `${Math.max(1.5, (1 / lift) * 100)}%` }}
                />
              </span>
            </div>
          </div>
        ),
      });
    }

    if (inst) {
      scenes.push({
        id: "check",
        kicker: "The check",
        title: "Checked against all 210 options",
        caption: result.quantum_agreed
          ? `The circuit chose sites ${listAnd(result.final.sites)}. An exact search of every possible network agrees.`
          : `The circuit chose sites ${listAnd(result.final.sites)}. The exact best was ${listAnd(result.exact_optimum)}, shown dashed.`,
        content: (
          <SiteMap
            instance={inst}
            title="The chosen sites"
            chosen={result.final.sites}
            chosenLabel="Chosen site"
            secondary={result.quantum_agreed ? [] : result.exact_optimum}
          />
        ),
      });
    }
  }

  const seq = sequence?.data ?? null;
  const moveStep = seq?.steps.find((s) => (s.plan?.moves ?? []).length > 0) ?? null;
  if (seq && moveStep) {
    const moves = moveStep.plan?.moves ?? [];
    scenes.push({
      id: "agent",
      kicker: "The agent",
      title: "It keeps watching, and moves a sensor when needed",
      caption: `As new aftershocks arrive, the agent checks the plan every hour. At hour ${fmt(moveStep.hour, 0)} they had drifted, so it moved a sensor.`,
      content: (
        <SiteMap
          instance={sequenceMapData(seq, moveStep.hour)}
          title={`Hour ${fmt(moveStep.hour, 0)} of the replay`}
          chosen={moveStep.sites}
          chosenLabel="Sensor in place"
          secondary={moves.map((m) => m.from).filter((id) => !moveStep.sites.includes(id))}
          secondaryLabel="Sensor moved away"
          designLabel="Real aftershock by this hour"
          moves={moves}
          live
        />
      ),
    });
  }

  scenes.push({
    id: "end",
    kicker: "Try it",
    title: "Every step, with the real data behind it",
    caption:
      "A proof of concept: the circuit runs on a simulator and claims no speedup, and every answer is checked exactly.",
    content: (
      <ul className="demo-links">
        <li>
          <Link href="/candidates">Candidate sites</Link>
        </li>
        <li>
          <Link href="/quantum">Run the circuit</Link>
        </li>
        <li>
          <Link href="/monitor">Replay the agent</Link>
        </li>
        <li>
          <Link href="/guide">Read the guide</Link>
        </li>
      </ul>
    ),
  });

  return (
    <DemoPresenter
      scenes={scenes}
      savedTag={anyMock ? "Placeholder data" : "Saved results from the team's runs"}
    />
  );
}
