#!/usr/bin/env node
// Capture real API responses from a running backend into web/snapshots/, so the
// site can show them when the backend is offline. Overwrites the placeholder
// (mock) files. Only GET endpoints are called; no run is started. Version 2
// endpoints (settings, feed, memory, noise, sequence, plan) are captured when the
// backend has them and skipped quietly on 404 or 501.
//
// Usage (from web/):
//   node --env-file=.env.local scripts/capture-snapshots.mjs [event_id] [lam]
//
// Reads BACKEND_URL and BACKEND_TOKEN from the environment. The token is never
// printed or written to a file.

import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SNAPSHOT_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "snapshots");
const ID_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;
const TIMEOUT_MS = 10_000;

function fail(message) {
  console.error(`capture-snapshots: ${message}`);
  process.exit(1);
}

const rawUrl = process.env.BACKEND_URL?.trim();
const token = process.env.BACKEND_TOKEN?.trim();
if (!rawUrl || !token) {
  fail("set BACKEND_URL and BACKEND_TOKEN (for example: node --env-file=.env.local scripts/capture-snapshots.mjs)");
}

let base;
try {
  const url = new URL(rawUrl);
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (url.protocol !== "https:" && !(url.protocol === "http:" && local)) {
    fail("BACKEND_URL must be https (http is allowed only for localhost)");
  }
  base = `${url.origin}/api/v1`;
} catch {
  fail("BACKEND_URL is not a valid URL");
}

async function get(path, { optional = false } = {}) {
  let response;
  try {
    response = await fetch(base + path, {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      redirect: "error",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (err) {
    fail(`GET ${path} did not complete (${err instanceof Error ? err.name : "error"}). Is the backend running?`);
  }
  let body = null;
  try {
    body = await response.json();
  } catch {
    // handled below
  }
  // Version 2 endpoints the backend does not have yet (501), or has nothing for (404).
  if (optional && (response.status === 404 || response.status === 501)) {
    console.log(`skipped ${path} (${response.status}): left the saved snapshot as it is`);
    return null;
  }
  if (!response.ok) {
    const code = body?.error?.code ?? "no error code";
    fail(`GET ${path} returned ${response.status} (${code})`);
  }
  if (body === null || typeof body !== "object") fail(`GET ${path} did not return a JSON object`);
  return body;
}

async function save(name, body) {
  // Captured files are real responses: they must not carry the mock marker.
  const clean = { ...body };
  delete clean.mock;
  delete clean.mock_note;
  await writeFile(join(SNAPSHOT_DIR, name), JSON.stringify(clean, null, 2) + "\n", "utf8");
  console.log(`saved snapshots/${name}`);
}

const [eventArg, lamArg] = process.argv.slice(2);
const lam = lamArg === undefined ? 150 : Number(lamArg);
if (!Number.isFinite(lam) || lam < 0 || lam > 1000) fail("lam must be a number from 0 to 1000");
if (eventArg !== undefined && !ID_PATTERN.test(eventArg)) fail("event_id has an unexpected form");

await mkdir(SNAPSHOT_DIR, { recursive: true });

const events = await get("/events");
const available = (events.events ?? []).filter((e) => e.available && ID_PATTERN.test(e.id));
const event = eventArg ? available.find((e) => e.id === eventArg) : available[0];
if (!event) fail(eventArg ? `event "${eventArg}" is not available on the backend` : "the backend lists no available event");
const eventPath = `/events/${encodeURIComponent(event.id)}`;

const instance = await get(`${eventPath}/instance`);
const scoring = await get(`${eventPath}/scoring?lam=${lam}`);
const baselines = await get(`${eventPath}/baselines?lam=${lam}`);

await save("events.json", events);
await save("instance.json", instance);
await save("scoring.json", scoring);
await save("baselines.json", baselines);

const jobs = await get("/jobs");
const finished = (jobs.jobs ?? []).find(
  (job) =>
    job.status === "done" && job.kind === "qaoa" && job.event_id === event.id && ID_PATTERN.test(job.job_id),
);
if (finished) {
  const job = await get(`/jobs/${encodeURIComponent(finished.job_id)}`);
  await save("job.json", job);
  if (job.result?.lam !== lam) {
    console.warn(
      `note: the saved job used lam ${job.result?.lam}, but scoring and baselines were saved for lam ${lam}.`,
    );
  }
} else {
  console.warn(
    `warning: no finished QAOA job for "${event.id}" on the backend. snapshots/job.json was NOT updated ` +
      "(it may still be the placeholder). Run one from the Quantum page, then capture again.",
  );
}

// Version 2 (the agent). Skipped quietly when the backend answers 404 or 501.
const optionalSnapshots = [
  ["settings.json", "/settings"],
  ["feed.json", "/feed"],
  ["memory.json", "/memory"],
  ["noise.json", "/noise"],
  ["sequence.json", `${eventPath}/sequence`],
  ["plan.json", `${eventPath}/plan`],
];
for (const [name, path] of optionalSnapshots) {
  const body = await get(path, { optional: true });
  if (body) await save(name, body);
}

console.log(`done: snapshots captured for "${event.id}" at lam ${lam}.`);
