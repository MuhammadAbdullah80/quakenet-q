import assert from "node:assert/strict";
import { test } from "node:test";
import { layoutBars } from "./bars.ts";

test("widths are fractions of the nice max", () => {
  const { bars, max, ticks } = layoutBars([
    { label: "a", value: 3 },
    { label: "b", value: 2.31 },
  ]);
  assert.equal(max, 3);
  assert.deepEqual(ticks, [0, 0.5, 1, 1.5, 2, 2.5, 3]);
  assert.equal(bars[0].width, 1);
  assert.equal(bars[1].width, 2.31 / 3);
});

test("explicit max wins and widths are clamped to 0..1", () => {
  const { bars } = layoutBars(
    [
      { label: "a", value: 12 },
      { label: "b", value: -1 },
    ],
    { max: 10 },
  );
  assert.equal(bars[0].width, 1);
  assert.equal(bars[1].width, 0);
});

test("empty and all-zero inputs do not divide by zero", () => {
  assert.deepEqual(layoutBars([]).bars, []);
  assert.equal(layoutBars([{ label: "a", value: 0 }]).bars[0].width, 0);
});
