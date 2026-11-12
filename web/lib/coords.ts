// Latitude and longitude as people read them: "35.77° N, 117.60° W", never a bare minus sign.

export function fmtCoord(
  lat: number | null | undefined,
  lon: number | null | undefined,
  digits = 2,
): string {
  if (typeof lat !== "number" || typeof lon !== "number") return "n/a";
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(digits)}° ${ns}, ${Math.abs(lon).toFixed(digits)}° ${ew}`;
}
