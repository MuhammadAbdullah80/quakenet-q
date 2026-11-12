// Layout maths for horizontal bar charts. Pure, so it is unit-tested with node --test.

export type BarInput = { label: string; value: number; highlight?: boolean };
export type Bar = BarInput & { width: number }; // width: fraction 0..1 of the plot

function niceStep(max: number): number {
  const rough = max / 6;
  const power = 10 ** Math.floor(Math.log10(rough));
  const unit = rough / power;
  return (unit < 1.5 ? 1 : unit < 3.5 ? 2 : unit < 7.5 ? 5 : 10) * power;
}

export function layoutBars(
  items: readonly BarInput[],
  opts: { max?: number } = {},
): { bars: Bar[]; max: number; ticks: number[] } {
  const top = Math.max(0, ...items.map((item) => item.value));
  let max = opts.max ?? top;
  let ticks: number[] = [0];
  if (max > 0) {
    const step = niceStep(max);
    if (opts.max === undefined) max = Math.ceil(top / step) * step;
    ticks = [];
    for (let v = 0; v <= max + step / 1e6; v += step) ticks.push(Number(v.toFixed(6)));
  }
  const bars = items.map((item) => ({
    ...item,
    width: max > 0 ? Math.min(1, Math.max(0, item.value / max)) : 0,
  }));
  return { bars, max, ticks };
}
