import type { Metadata } from "next";
import { Suspense } from "react";
import { Empty, Loading, OfflineBanner, Problem } from "@/components/States";
import { backendConfigured } from "@/lib/backend";
import { loadHealth, loadJobs, loadSystem } from "@/lib/data";
import { fmtTime } from "@/lib/format";
import { passcodeConfigured } from "@/lib/passcode";
import { TableFold } from "@/components/TableFold";

export const metadata: Metadata = { title: "System" };

export default function SystemPage() {
  return (
    <>
      <h1>System</h1>
      <p className="lede">
        A quick health check: is the backend running, how many jobs have run, and where the data
        comes from.
      </p>
      <Suspense fallback={<Loading label="Checking the backend" />}>
        <SystemContent />
      </Suspense>
    </>
  );
}

function statusTag(status: string) {
  const tone = status === "done" ? "tag-ok" : status === "failed" ? "tag-bad" : "tag-warn";
  return <span className={`tag ${tone}`}>{status}</span>;
}

async function SystemContent() {
  const [health, system, jobs] = await Promise.all([loadHealth(), loadSystem(), loadJobs()]);
  return (
    <>
      <OfflineBanner results={[health, system, jobs]} />

      <section aria-labelledby="console-heading">
        <h2 id="console-heading">This console</h2>
        <dl className="facts">
          <div>
            <dt>Backend address and secret</dt>
            <dd>{backendConfigured() ? "configured" : "not configured"}</dd>
          </div>
          <div>
            <dt>Team passcode for starting runs</dt>
            <dd>{passcodeConfigured() ? "configured" : "not configured (runs disabled)"}</dd>
          </div>
          <div>
            <dt>Backend reachable</dt>
            <dd>{health.state === "live" ? "yes" : "no"}</dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="health-heading">
        <h2 id="health-heading">Health</h2>
        <Problem result={health} what="the health check" />
        {health.state === "live" ? (
          <dl className="facts">
            <div>
              <dt>Status</dt>
              <dd>{health.data.status}</dd>
            </div>
            <div>
              <dt>API version</dt>
              <dd>{health.data.version}</dd>
            </div>
            <div>
              <dt>Region</dt>
              <dd>{health.data.region}</dd>
            </div>
            <div>
              <dt>Backend clock</dt>
              <dd>{fmtTime(health.data.time_utc)}</dd>
            </div>
          </dl>
        ) : null}
      </section>

      <section aria-labelledby="limits-heading">
        <h2 id="limits-heading">Job counters and data sources</h2>
        <Problem result={system} what="the system counters" />
        {system.state === "live" ? (
          <>
            <dl className="facts">
              <div>
                <dt>Jobs running now</dt>
                <dd>{system.data.jobs_running}</dd>
              </div>
              <div>
                <dt>Jobs in the last hour</dt>
                <dd>
                  {system.data.jobs_last_hour} of {system.data.job_hourly_cap} allowed
                </dd>
              </div>
            </dl>
            {system.data.sources.length === 0 ? (
              <Empty>No external data sources are listed.</Empty>
            ) : (
              <div className="table-wrap">
                <table>
                  <caption>External data sources</caption>
                  <thead>
                    <tr>
                      <th scope="col">Source</th>
                      <th scope="col">Cached</th>
                      <th scope="col">Retrieved</th>
                      <th scope="col">Address</th>
                    </tr>
                  </thead>
                  <tbody>
                    {system.data.sources.map((source) => (
                      <tr key={source.name}>
                        <th scope="row">{source.name}</th>
                        <td>{source.cached ? "yes" : "no"}</td>
                        <td>{fmtTime(source.retrieved_utc)}</td>
                        {/* Shown as text on purpose: backend data is never turned into a link. */}
                        <td className="clip" title={source.url ?? undefined}>
                          {source.url ?? "n/a"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : null}
      </section>

      <section aria-labelledby="jobs-heading">
        <h2 id="jobs-heading">Recent jobs</h2>
        <Problem result={jobs} what="the job list" />
        {jobs.state === "live" && jobs.data.jobs.length === 0 ? (
          <Empty>No jobs have been run yet.</Empty>
        ) : null}
        {jobs.state === "live" && jobs.data.jobs.length > 0 ? (
          <TableFold total={jobs.data.jobs.length} limit={6} noun="jobs">
            <div className="table-wrap">
              <table>
                <caption>Newest first, at most 50</caption>
                <thead>
                  <tr>
                    <th scope="col">Job</th>
                    <th scope="col">Kind</th>
                    <th scope="col">Earthquake</th>
                    <th scope="col">Status</th>
                    <th scope="col">Created</th>
                    <th scope="col">Finished</th>
                    <th scope="col">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.data.jobs.map((job) => (
                    <tr key={job.job_id}>
                      <th scope="row">{job.job_id}</th>
                      <td>{job.kind}</td>
                      <td>{job.event_id}</td>
                      <td>{statusTag(job.status)}</td>
                      <td>{fmtTime(job.created_utc)}</td>
                      <td>{fmtTime(job.finished_utc)}</td>
                      <td>{job.error ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TableFold>
        ) : null}
      </section>
    </>
  );
}
