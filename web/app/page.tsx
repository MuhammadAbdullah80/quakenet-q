import type { Metadata } from "next";
import Link from "next/link";
import { Story } from "@/components/story/Story";
import { COPY, PIPELINE, STATS } from "@/lib/story-data";

export const metadata: Metadata = {
  title: { absolute: "QuakeNet-Q: where do the sensors go?" },
  description:
    "After a big earthquake, where should the first portable seismometers go? A quantum circuit picks 4 of 10 sites, and an exact search of all 210 options checks it.",
};

const CARDS = [
  {
    href: "/candidates",
    title: "Candidates",
    text: "The aftershocks, the permanent stations and the ten places a sensor could go, on real terrain.",
  },
  {
    href: "/quantum",
    title: "Quantum",
    text: "Start a run of the circuit and watch which networks it measures most often.",
  },
  {
    href: "/self-check",
    title: "Self-check",
    text: "The quantum pick next to the exact best network and the classical methods.",
  },
] as const;

export default function HomePage() {
  return (
    <>
      <Story />
      <section className="story-panel" aria-labelledby="run-heading">
        <div className="story-panel-inner">
          <h2 id="run-heading">Run it yourself</h2>
          <p className="lede">
            Every page of the console shows one step, with the real data behind it. Start with the
            map, run the circuit, then check its answer.
          </p>
          <ul className="run-cards">
            {CARDS.map((card) => (
              <li key={card.href}>
                <Link href={card.href} className="run-card">
                  <span className="run-card-title">{card.title}</span>
                  <span className="run-card-text">{card.text}</span>
                  <span className="run-card-go" aria-hidden="true">
                    Open →
                  </span>
                </Link>
              </li>
            ))}
          </ul>

          <dl className="run-stats">
            {STATS.map((stat) => (
              <div key={stat.label}>
                <dt>{stat.label}</dt>
                <dd>{stat.value}</dd>
              </div>
            ))}
          </dl>

          <div className="run-steps">
            <h2>Step by step</h2>
            <ol className="story-pipeline is-static">
              {PIPELINE.map((row, i) => (
                <li key={row.href}>
                  <Link href={row.href}>
                    <span className="row-num">{String(i + 1).padStart(2, "0")}</span>
                    {row.label}
                  </Link>
                </li>
              ))}
            </ol>
            <p>
              New here? The <Link href="/guide">guide</Link> explains every map, chart and number,
              and the <Link href="/demo">demo</Link> walks through the whole story in eight steps.
            </p>
          </div>

          <p className="story-footnote">{COPY.footer}</p>
        </div>
      </section>
    </>
  );
}
