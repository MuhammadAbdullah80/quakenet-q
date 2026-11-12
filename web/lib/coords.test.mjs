import assert from "node:assert/strict";
import { test } from "node:test";
import { fmtCoord } from "./coords.ts";

test("north and west get hemisphere letters, not minus signs", () => {
  assert.equal(fmtCoord(35.7695, -117.5993), "35.77° N, 117.60° W");
});

test("south and east", () => {
  assert.equal(fmtCoord(-12.5, 45.25), "12.50° S, 45.25° E");
});

test("digits are configurable", () => {
  assert.equal(fmtCoord(35.7, -117.5, 3), "35.700° N, 117.500° W");
});

test("missing values read n/a", () => {
  assert.equal(fmtCoord(null, 10), "n/a");
  assert.equal(fmtCoord(10, undefined), "n/a");
});
