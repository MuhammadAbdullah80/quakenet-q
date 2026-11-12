import assert from "node:assert/strict";
import { test } from "node:test";
import { synthTrace } from "./trace.ts";

const events = [
  [1, 3.0],
  [5, 5.0],
];

test("returns one sample per requested point, all within -1..1", () => {
  const tr = synthTrace(events, { t0: 0, t1: 10, samples: 400, seed: 1 });
  assert.equal(tr.length, 400);
  for (const v of tr) assert.ok(v >= -1 && v <= 1, `out of range: ${v}`);
});

test("is quiet before the first event: only background noise", () => {
  const tr = synthTrace(events, { t0: 0, t1: 10, samples: 400, seed: 1, noise: 0.03 });
  const before = tr.slice(0, 35); // t < 0.9
  assert.ok(Math.max(...before.map(Math.abs)) <= 0.03 + 1e-9);
});

test("a bigger magnitude gives a bigger peak near its time", () => {
  const tr = synthTrace(events, { t0: 0, t1: 10, samples: 400, seed: 1 });
  const peak = (a, b) => Math.max(...tr.slice(a, b).map(Math.abs));
  assert.ok(peak(200, 230) > peak(40, 70) * 3); // M5 at t=5 vs M3 at t=1
});

test("the same seed gives the same trace", () => {
  const a = synthTrace(events, { t0: 0, t1: 10, samples: 100, seed: 7 });
  const b = synthTrace(events, { t0: 0, t1: 10, samples: 100, seed: 7 });
  assert.deepEqual(Array.from(a), Array.from(b));
});

test("no events and no noise gives a flat line", () => {
  const tr = synthTrace([], { t0: 0, t1: 1, samples: 10, seed: 1, noise: 0 });
  assert.deepEqual(Array.from(tr), new Array(10).fill(0));
});
