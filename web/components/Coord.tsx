import { fmtCoord } from "@/lib/coords";

/** A coordinate pair on one line, with the raw values as a hover hint. */
export function Coord({
  lat,
  lon,
  digits = 2,
}: {
  lat: number | null | undefined;
  lon: number | null | undefined;
  digits?: number;
}) {
  const text = fmtCoord(lat, lon, digits);
  return (
    <span className="coord" title={text === "n/a" ? undefined : `${lat}, ${lon}`}>
      {text}
    </span>
  );
}
