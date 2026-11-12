import type { Instance, Job } from "@/lib/schemas";
import { fmt, fmtPercent, fmtSites, fmtTime, sameSites } from "@/lib/format";
import { BarChart } from "@/components/BarChart";
import { SiteMap } from "@/components/SiteMap";
import { TableFold } from "@/components/TableFold";
import { Expand } from "@/components/Expand";

// Shows one finished QAOA job. Used on the Quantum page (server-rendered and
// after polling in the browser) and on the Self-check page.

export function JobResultView({
  job,
  instance,
  showMap = true,
}: {
  job: Job;
  instance: Instance | null;
  showMap?: boolean;
}) {
  const result = job.result;
  if (!result) return null;
  const lift = result.uniform_p_opt > 0 ? result.p_opt / result.uniform_p_opt : null;

  return (
    <div>
      <div className={`notice ${result.quantum_agreed ? "notice-ok" : "notice-warn"}`}>
        <p className="notice-title">
          {result.quantum_agreed
            ? "The quantum choice matched the exact optimum."
            : "The quantum choice did not match the exact optimum."}
        </p>
        <p>
          Final pick: sites {fmtSites(result.final.sites)} (rank {result.final.rank}, objective{" "}
          {fmt(result.final.objective, 1)}). Exact optimum: sites {fmtSites(result.exact_optimum)}.
        </p>
      </div>

      <Expand
        title="Quantum circuit against a random pick"
        explain={{
          what: "How often one measurement of the circuit gave the best network, next to how often a random pick would.",
          read: [
            "The big number is how many times more often the circuit found the best network.",
            "A random pick finds it 1 time in 210.",
            "Higher is better. It does not need to reach 100%: the best of the most measured networks is kept.",
          ],
        }}
      >
        <div
          className="lift"
          role="img"
          aria-label={`The circuit measured the best network ${fmtPercent(result.p_opt, 2)} of the time, against ${fmtPercent(result.uniform_p_opt, 2)} for a random pick${lift === null ? "" : `: ${fmt(lift, 1)} times more often`}.`}
        >
          <p className="lift-head">
            <span className="lift-x">{lift === null ? "n/a" : `${fmt(lift, 1)}×`}</span>
            <span className="lift-text">
              more often than a random pick, the circuit measured the best network
            </span>
          </p>
          <div className="lift-bars" aria-hidden="true">
            <span className="lift-row is-q">
              <span className="lift-name">Quantum circuit</span>
              <span className="lift-track">
                <span
                  className="lift-fill"
                  style={{
                    width: `${Math.min(100, (result.p_opt / Math.max(result.p_opt, result.uniform_p_opt)) * 100)}%`,
                  }}
                />
              </span>
              <span className="lift-val">{fmtPercent(result.p_opt, 2)}</span>
            </span>
            <span className="lift-row">
              <span className="lift-name">Random pick</span>
              <span className="lift-track">
                <span
                  className="lift-fill"
                  style={{
                    width: `${Math.min(100, (result.uniform_p_opt / Math.max(result.p_opt, result.uniform_p_opt)) * 100)}%`,
                  }}
                />
              </span>
              <span className="lift-val">{fmtPercent(result.uniform_p_opt, 2)}</span>
            </span>
          </div>
        </div>
      </Expand>

      <dl className="kpis">
        <div>
          <dt>Valid networks</dt>
          <dd>{fmtPercent(result.feasible, 1)}</dd>
          <span className="kpi-note">of measurements picked exactly 4 sites</span>
        </div>
        <div>
          <dt>Approximation ratio</dt>
          <dd>{fmt(result.ratio, 3)}</dd>
          <span className="kpi-meter" aria-hidden="true">
            <span style={{ width: `${Math.max(0, Math.min(1, result.ratio)) * 100}%` }} />
          </span>
          <span className="kpi-note">0 is the worst network, 1 the best</span>
        </div>
        <div>
          <dt>Run time</dt>
          <dd>{fmt(result.seconds, 1)} s</dd>
          <span className="kpi-note">
            {result.reps} {result.reps === 1 ? "layer" : "layers"}, {result.shots} measurements
          </span>
        </div>
      </dl>

      <details className="more">
        <summary>Run details</summary>
        <dl className="facts">
          <div>
            <dt>Settings</dt>
            <dd>
              reps {result.reps}, seed {result.seed}, shots {result.shots}, lam {result.lam}
            </dd>
          </div>
          {result.objective ? (
            <div>
              <dt>Optimiser target</dt>
              <dd>
                {result.objective === "cvar"
                  ? "best part of the outcomes (CVaR)"
                  : "average of all outcomes"}
              </dd>
            </div>
          ) : null}
          {typeof result.warm_start === "boolean" ? (
            <div>
              <dt>Started from remembered angles</dt>
              <dd>{result.warm_start ? "yes" : "no"}</dd>
            </div>
          ) : null}
          <div>
            <dt>Circuit</dt>
            <dd>
              depth {result.depth}, {result.gates} gates
            </dd>
          </div>
          <div>
            <dt>Optimiser evaluations</dt>
            <dd>{result.evaluations}</dd>
          </div>
          <div>
            <dt>Job</dt>
            <dd>
              {job.job_id}, finished {fmtTime(job.finished_utc)}
            </dd>
          </div>
        </dl>
      </details>

      <BarChart
        title="Times each network was measured"
        explain={{
          what: "Every measurement of the circuit picks one network of 4 sites. This counts how often each network came up.",
          read: [
            "Longer bars came up more often.",
            "The lime bar is the best possible network, found by checking all 210.",
            "It does not have to be the longest bar. What matters is that it comes up far more often than a random pick would.",
          ],
        }}
        note={`Out of ${result.shots} measurements. The best network should come up far more often than a random pick would.`}
        unit="times"
        digits={0}
        items={result.top_counts.map((row) => ({
          label: fmtSites(row.sites),
          value: row.count,
          highlight: sameSites(row.sites, result.exact_optimum),
        }))}
        highlightLabel={`Exact optimum: sites ${fmtSites(result.exact_optimum)}`}
      />

      <div className="columns">
        <details className="more">
          <summary>See the numbers: measured networks</summary>
          <TableFold total={result.top_counts.length} limit={5} noun="networks">
            <div className="table-wrap">
              <table>
                <caption>
                  Most frequently measured networks (top {result.top_counts.length})
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Sites</th>
                    <th scope="col" className="num">
                      Times measured
                    </th>
                    <th scope="col" className="num">
                      Objective
                    </th>
                    <th scope="col" className="num">
                      Rank
                    </th>
                    <th scope="col">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {result.top_counts.map((row) => {
                    const isFinal = sameSites(row.sites, result.final.sites);
                    const isOptimum = sameSites(row.sites, result.exact_optimum);
                    return (
                      <tr
                        key={row.sites.join("-")}
                        className={isFinal ? "is-highlight" : undefined}
                      >
                        <td className="nowrap">{fmtSites(row.sites)}</td>
                        <td className="num">{row.count}</td>
                        <td className="num">{fmt(row.objective, 1)}</td>
                        <td className="num">{row.rank}</td>
                        <td>
                          {isFinal ? <span className="tag tag-ok">final pick</span> : null}{" "}
                          {isOptimum ? <span className="tag">exact optimum</span> : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </TableFold>
        </details>

        {showMap && instance ? (
          <SiteMap
            instance={instance}
            title="Sites chosen by the quantum run"
            chosen={result.final.sites}
            chosenLabel="Quantum final pick"
            secondary={result.quantum_agreed ? [] : result.exact_optimum}
            secondaryLabel="Exact optimum"
          />
        ) : null}
      </div>
    </div>
  );
}
