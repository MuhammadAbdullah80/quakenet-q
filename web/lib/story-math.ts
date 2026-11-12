// Pure maths for the landing-page story. No DOM, so it is unit-tested with node --test.

export type Grid = { lat0: number; lon0: number; km_per_deg: number };

/** Local grid km (x east, y north) to [lat, lon] in degrees (docs/FRONTEND_BRIEF.md section 3). */
export function kmToLatLon(x: number, y: number, grid: Grid): [number, number] {
  const lat = grid.lat0 + y / grid.km_per_deg;
  const lon = grid.lon0 + x / (grid.km_per_deg * Math.cos((grid.lat0 * Math.PI) / 180));
  return [lat, lon];
}

export type PlaneView = {
  /** Screen position of the plane centre, px. */
  cx: number;
  cy: number;
  scale: number;
  /** rotateX angle in radians; positive tips the top edge away. */
  tilt: number;
  /** Vertical shift of the plane, px, before perspective. */
  ty: number;
  /** CSS perspective distance, px. */
  perspective: number;
  /** Sideways shift of the plane, px, before perspective (translate3d x). */
  tx?: number;
};

/**
 * Screen position of a point (u, v) px from the centre of a plane drawn with
 * `perspective: P` and `translate3d(tx, ty, 0) rotateX(tilt) scale(s)`. Matches the browser's
 * own transform, so markers drawn on a flat canvas sit on the tilted image and labels stay upright.
 */
export function projectPlane(u: number, v: number, view: PlaneView): [number, number] {
  const Y = v * view.scale;
  const yRot = Y * Math.cos(view.tilt) + view.ty;
  const zRot = Y * Math.sin(view.tilt);
  const f = view.perspective / (view.perspective - zRot);
  return [view.cx + (u * view.scale + (view.tx ?? 0)) * f, view.cy + yRot * f];
}

/** Progress through the window a..b of an overall progress p, clamped to 0..1. */
export function segment(p: number, a: number, b: number): number {
  if (p <= a) return 0;
  if (p >= b) return 1;
  return (p - a) / (b - a);
}

/** Number of words to show when a paragraph of `count` words is `t` of the way written. */
export function wordsShown(t: number, count: number): number {
  return Math.max(0, Math.min(count, Math.round(t * count)));
}

export function easeInOut(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
}
