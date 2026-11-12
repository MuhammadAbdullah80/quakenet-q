import assert from "node:assert/strict";
import { test } from "node:test";
import { kmToLatLon, projectPlane, segment, wordsShown } from "./story-math.ts";

const close = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test("kmToLatLon puts the grid origin at lat0, lon0", () => {
  const grid = { lat0: 35.75, lon0: -117.55, km_per_deg: 111.19 };
  const [lat, lon] = kmToLatLon(0, 0, grid);
  close(lat, 35.75);
  close(lon, -117.55);
});

test("kmToLatLon moves north by y / km_per_deg and east scaled by cos(lat0)", () => {
  const grid = { lat0: 60, lon0: 10, km_per_deg: 100 };
  const [lat, lon] = kmToLatLon(50, 100, grid);
  close(lat, 61);
  close(lon, 11); // 50 / (100 * cos 60°) = 1
});

test("projectPlane with no tilt is a plain scale about the centre", () => {
  const [sx, sy] = projectPlane(10, -20, { cx: 400, cy: 300, scale: 2, tilt: 0, ty: 0, perspective: 1000 });
  close(sx, 420);
  close(sy, 260);
});

test("projectPlane foreshortens the far half of a tilted plane", () => {
  const view = { cx: 0, cy: 0, scale: 1, tilt: Math.PI / 3, ty: 0, perspective: 1000 };
  const [, far] = projectPlane(0, -100, view);
  const [, near] = projectPlane(0, 100, view);
  assert.ok(Math.abs(far) < Math.abs(near), "far edge should look shorter");
  close(far, -100 * Math.cos(Math.PI / 3) * (1000 / (1000 + 100 * Math.sin(Math.PI / 3))));
});

test("segment maps p onto 0..1 between a and b and clamps outside", () => {
  assert.equal(segment(0.1, 0.2, 0.4), 0);
  close(segment(0.3, 0.2, 0.4), 0.5);
  assert.equal(segment(0.9, 0.2, 0.4), 1);
});

test("wordsShown reveals words in proportion and never exceeds the count", () => {
  assert.equal(wordsShown(0, 10), 0);
  assert.equal(wordsShown(0.5, 10), 5);
  assert.equal(wordsShown(1.2, 10), 10);
});

test("projectPlane shifts sideways by tx before perspective", () => {
  const view = { cx: 100, cy: 0, scale: 1, tilt: Math.PI / 4, ty: 0, perspective: 800, tx: 50 };
  const [sx, sy] = projectPlane(10, -40, view);
  const z = -40 * Math.sin(Math.PI / 4);
  const f = 800 / (800 - z);
  close(sx, 100 + (10 + 50) * f);
  close(sy, -40 * Math.cos(Math.PI / 4) * f);
});
