import type { Metadata } from "next";
import { Suspense } from "react";
import { Empty, Loading, OfflineBanner, Problem } from "@/components/States";
import { loadMemory } from "@/lib/data";
import { fmt, fmtPercent } from "@/lib/format";
import { stageLabel } from "@/lib/sequence";
import { TableFold } from "@/components/TableFold";

export const metadata: Metadata = { title: "Memory" };

export default function MemoryPage() {
  return (
    <>
      <h1>Memory</h1>
      <p className="lede">
        Settings that worked well before, how much the agent trusts each speed model of the ground,
        and how good its past predictions were.
      </p>
      <Suspense fallback={<Loading label="Loading the memory" />}>
        <MemoryContent />
      </Suspense>
    </>
  );
}

const CONFIDENCE: Record<string, string> = {
  high: "high",
  medium: "medium",
  low: "low",
  unrated: "unrated (not enough past plans)",
};

function num(value: number | null | undefined, digits = 1): string {
  return typeof value === "number" ? fmt(value, digits) : "n/a";
}

async function MemoryContent() {
  const memory = await loadMemory();
  const data = memory.state === "live" || memory.state === "snapshot" ? memory.data : null;
  return (
    <>
      <OfflineBanner results={[memory]} />
      <Problem result={memory} what="the memory" />
      {data ? (
        <>
          <dl className="facts">
            <div>
              <dt>Confidence level</dt>
              <dd>{data.confidence ? (CONFIDENCE[data.confidence] ?? data.confidence) : "n/a"}</dd>
            </div>
            <div>
              <dt>Sequences remembered</dt>
              <dd>{data.sequences ?? "n/a"}</dd>
            </div>
          </dl>

          <h2>Stored circuit angles</h2>
          {data.angles.length === 0 ? (
            <Empty>No angles stored yet.</Empty>
          ) : (
            <div className="table-wrap">
              <table>
                <caption>
                  Median QAOA angles by problem size (sensors, candidates, layers). Used to
                  warm-start the next run of the same size.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Key</th>
                    <th scope="col" className="num">
                      Sensors
                    </th>
                    <th scope="col" className="num">
                      Candidates
                    </th>
                    <th scope="col" className="num">
                      Layers
                    </th>
                    <th scope="col" className="num">
                      Runs
                    </th>
                    <th scope="col">Median angles (radians)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.angles.map((a) => (
                    <tr key={a.key}>
                      <th scope="row">{a.key}</th>
                      <td className="num">{a.sensors ?? "n/a"}</td>
                      <td className="num">{a.candidates ?? "n/a"}</td>
                      <td className="num">{a.layers ?? "n/a"}</td>
                      <td className="num">{a.count ?? "n/a"}</td>
                      <td>{a.median.map((v) => fmt(v, 3)).join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h2>Model weights</h2>
          {data.model_weights.length === 0 ? (
            <Empty>No model weights stored yet.</Empty>
          ) : (
            <div className="table-wrap">
              <table>
                <caption>How much the agent trusts each travel-time model</caption>
                <thead>
                  <tr>
                    <th scope="col">Model</th>
                    <th scope="col" className="num">
                      Weight
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.model_weights.map((m) => (
                    <tr key={m.name}>
                      <th scope="row">{m.name}</th>
                      <td className="num">{fmt(m.weight, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h2>Track record</h2>
          {data.track_record.length === 0 ? (
            <Empty>No plans have been checked against what happened yet.</Empty>
          ) : (
            <TableFold total={data.track_record.length} limit={6} noun="plans">
              <div className="table-wrap">
                <table>
                  <caption>
                    Past plans: the score each plan predicted and the score it reached once the
                    later aftershocks were known. Error is the relative difference.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Earthquake</th>
                      <th scope="col" className="num">
                        Hour
                      </th>
                      <th scope="col">Stage</th>
                      <th scope="col" className="num">
                        Predicted score
                      </th>
                      <th scope="col" className="num">
                        Realised score
                      </th>
                      <th scope="col" className="num">
                        Error
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.track_record.map((t, i) => (
                      <tr key={`${t.event_id}-${t.hour ?? "x"}-${i}`}>
                        <th scope="row">{t.event_id}</th>
                        <td className="num">{num(t.hour, 0)}</td>
                        <td>{stageLabel(t.stage)}</td>
                        <td className="num">{num(t.predicted_score)}</td>
                        <td className="num">{num(t.realised_score)}</td>
                        <td className="num">
                          {typeof t.error === "number" ? fmtPercent(t.error, 1) : "n/a"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </TableFold>
          )}
        </>
      ) : null}
    </>
  );
}
