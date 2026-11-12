"""Data-quality check of the six benchmark earthquakes (spec risk R-2).

For each earthquake in src.sources.BENCHMARKS this downloads, through the outbound gateway
(one request per endpoint per event, everything cached under data/cache/):
  * the mainshock from USGS ComCat;
  * M >= 2.5 earthquakes within the study radius for 7 days after the mainshock;
  * stations of all networks within the radius (IRIS/EarthScope FDSN);
  * roads (Overpass) and terrain tiles, to build the candidate pool.
It then writes 2026-11-12_data_quality.md and .json next to this file. Every number in the
report comes from this script. Re-running it uses the cache and needs no network:

    python research/benchmarks/data_quality.py            # uses the cache, downloads what is missing
    QUAKENET_OFFLINE=1 python research/benchmarks/data_quality.py   # cache only
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from src import candidates, sources  # noqa: E402

STEM = "2026-11-12_data_quality"
EARLY_HOURS, LATE_DAYS = 12, 7
# Verdict thresholds. 30 early aftershocks is the spec's EC-3 limit below which real events
# must be blended with synthetic ones; 10 is the number of candidates the agent selects (FR-8).
MIN_EARLY, MIN_LATE, MIN_PERMANENT, MIN_POOL = 30, 100, 4, 10


def check(key: str, b: dict) -> dict:
    out = dict(key=key, name=b["name"], usgs_id=b["usgs_id"], errors=[])
    try:
        main = sources.fetch_mainshock(b["usgs_id"])
    except sources.QuakeNetError as err:
        out["errors"].append(f"mainshock: {err}")
        return out
    t0 = datetime.fromtimestamp(main["time_ms"] / 1000, timezone.utc)
    radius = sources.study_radius_km(main["mag"])
    out.update(mag=main["mag"], time=t0.isoformat(), lat=main["lat"], lon=main["lon"],
               depth_km=main["depth_km"], place=main["place"], radius_km=round(radius, 1),
               registry_matches=bool(abs(main["lat"] - b["lat"]) < 1e-3 and abs(main["lon"] - b["lon"]) < 1e-3
                                     and abs(main["mag"] - b["mag"]) < 0.01
                                     and abs((sources._as_utc(b["time"]) - t0).total_seconds()) < 1))

    try:
        quakes = sources.fetch_aftershocks(main["lat"], main["lon"], radius, t0, t0 + timedelta(days=LATE_DAYS))
        after = [q for q in quakes if q["time_ms"] > main["time_ms"] and q["id"] != main["id"]]
        cut = main["time_ms"] + EARLY_HOURS * 3600e3
        out.update(aftershocks_0_12h=sum(q["time_ms"] <= cut for q in after),
                   aftershocks_12h_7d=sum(q["time_ms"] > cut for q in after),
                   comcat_rows=len(quakes))
    except sources.QuakeNetError as err:
        out["errors"].append(f"aftershocks: {err}")

    permanent = []
    try:
        permanent, temporary = sources.fetch_stations(main["lat"], main["lon"], radius, t0)
        nets = Counter(s["net"] for s in temporary)
        out.update(permanent_stations=len(permanent),
                   permanent_networks=dict(sorted(Counter(s["net"] for s in permanent).items())),
                   temporary_stations=len(temporary), temporary_networks=dict(sorted(nets.items())))
    except sources.QuakeNetError as err:
        out["errors"].append(f"stations: {err}")

    # No mapped rupture trace is available from these sources, so the only "rupture point"
    # here is the mainshock epicentre. The agent will pass the early aftershock cloud instead.
    # The road query box uses the registry's 4-decimal epicentre, as src/instances.py does, so the
    # cached Overpass answer is found whatever ComCat's 5th decimal says (about 10 m).
    pool = candidates.build_candidate_pool(main["lat"], main["lon"], radius, permanent,
                                           [(main["lat"], main["lon"])],
                                           road_bbox=candidates.bounding_box(b["lat"], b["lon"], radius))
    out.update(pool_size=len(pool), funnel=pool.funnel, feasibility_checked=pool.feasibility_checked,
               roads_checked=pool.roads_checked, terrain_checked=pool.terrain_checked,
               pool_warnings=list(pool.warnings))
    if pool.roads_checked:
        info = sources.cache_info(candidates.overpass_url(candidates.bounding_box(b["lat"], b["lon"], radius)))
        out["overpass_bytes"] = info["bytes"] if info else None
    out["verdict"], out["reasons"] = verdict(out)
    return out


def verdict(r: dict) -> tuple[str, list[str]]:
    bad, thin = [], []
    if r["errors"]:
        bad.append("a required download failed")
    if r.get("permanent_stations", 0) == 0:
        bad.append("no permanent station in the radius")
    elif r["permanent_stations"] < MIN_PERMANENT:
        thin.append(f"only {r['permanent_stations']} permanent stations")
    if r.get("aftershocks_0_12h", 0) < MIN_EARLY:
        thin.append(f"only {r.get('aftershocks_0_12h', 0)} aftershocks in the first 12 h (under {MIN_EARLY}: "
                    "the plan must blend in synthetic events, EC-3)")
    if r.get("aftershocks_12h_7d", 0) < MIN_LATE:
        thin.append(f"only {r.get('aftershocks_12h_7d', 0)} later aftershocks to validate on (under {MIN_LATE})")
    if r["pool_size"] < MIN_POOL:
        bad.append(f"candidate pool of {r['pool_size']} is under {MIN_POOL}")
    if not r["feasibility_checked"]:
        thin.append("road or terrain check did not run, pool is not feasibility-checked")
    if r.get("temporary_stations", 0) == 0:
        thin.append("no temporary stations in the metadata, so no comparison with a real deployment")
    if bad:
        return "not usable as is", bad + thin
    return ("usable with caveats", thin) if thin else ("usable", [])


def render(rows: list[dict]) -> str:
    def nets(d):
        return ", ".join(f"{k} ({v})" for k, v in d.items()) if d else "none"

    lines = [
        "# Benchmark earthquakes: data-quality check",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by "
        "`research/benchmarks/data_quality.py`. Every number below comes from that script, run on the "
        "responses cached in `data/cache/` (each has a sidecar with its URL and retrieval time).",
        "",
        "This answers risk R-2 of the design spec: are the six planned benchmark earthquakes usable?",
        "",
        "## How to read it",
        "",
        "- **Radius**: the study radius of spec FR-3, max(50 km, 2 x rupture length). Rupture length is the "
        "Wells & Coppersmith (1994) subsurface length for all fault types, log10 L = -2.44 + 0.59 M.",
        "- **Aftershocks**: USGS ComCat earthquakes with M >= 2.5 inside the radius, after the mainshock. "
        "\"0-12 h\" is what a planner would know at decision time; \"12 h-7 d\" is what the plan is tested on.",
        "- **Permanent stations**: stations of any network in the IRIS/EarthScope metadata that were operating "
        "at the mainshock time. This counts every listed station, including strong-motion sites and long-running "
        "temporary experiments, and it does not check that a station was actually recording.",
        "- **Temporary stations**: stations whose first listed epoch starts within 30 days after the mainshock. "
        "This is how a rapid-response deployment shows up, but an unrelated experiment that happened to start "
        "in that month is counted too. Deployments that were never archived at EarthScope are missed.",
        "- **Candidate pool**: 2 km grid points left after the filters of spec FR-6 (on land, slope under 20 "
        "degrees, within 1.5 km of a road, 6 km from permanent stations, 3 km from the rupture). The only "
        "rupture point used here is the mainshock epicentre, because no mapped rupture trace is downloaded.",
        f"- **Verdict rule** (in the script): *not usable* if a download failed, no permanent station, or fewer "
        f"than {MIN_POOL} pool points; *usable with caveats* if under {MIN_EARLY} early aftershocks, under "
        f"{MIN_LATE} later ones, under {MIN_PERMANENT} permanent stations, no temporary stations, or the pool "
        "was not feasibility-checked; otherwise *usable*.",
        "",
        "## Summary",
        "",
        "| Earthquake | USGS event ID | M | Radius (km) | Aftershocks 0-12 h | Aftershocks 12 h-7 d | "
        "Permanent stations | Temporary stations (networks) | Candidate pool | Feasibility checked | Verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if "mag" not in r:
            lines.append(f"| {r['name']} | {r['usgs_id']} | - | - | - | - | - | - | - | - | FAILED: {r['errors'][0]} |")
            continue
        temp = f"{r.get('temporary_stations', 'failed')}"
        if r.get("temporary_networks"):
            temp += f" ({', '.join(r['temporary_networks'])})"
        lines.append(
            f"| {r['name']} | {r['usgs_id']} | {r['mag']:.1f} | {r['radius_km']:.0f} | "
            f"{r.get('aftershocks_0_12h', 'failed')} | {r.get('aftershocks_12h_7d', 'failed')} | "
            f"{r.get('permanent_stations', 'failed')} | {temp} | {r['pool_size']} | "
            f"{'yes' if r['feasibility_checked'] else '**no**'} | {r['verdict']} |")
    lines += ["", "## Per earthquake", ""]
    for r in rows:
        lines.append(f"### {r['name']} ({r['usgs_id']})")
        lines.append("")
        if "mag" not in r:
            lines += [f"- **Failed:** {e}" for e in r["errors"]] + [""]
            continue
        lines += [
            f"- ComCat: M {r['mag']}, {r['time']}, lat {r['lat']:.4f}, lon {r['lon']:.4f}, depth {r['depth_km']} km "
            f"(\"{r['place']}\"). Matches the `BENCHMARKS` registry: {'yes' if r['registry_matches'] else '**NO**'}.",
            f"- Study radius: {r['radius_km']} km.",
        ]
        if "aftershocks_0_12h" in r:
            note = " **This is the ComCat limit of 20,000 rows, so the count is truncated.**" \
                if r["comcat_rows"] >= 20000 else ""
            lines.append(f"- Aftershocks M >= 2.5: {r['aftershocks_0_12h']} in the first 12 h, "
                         f"{r['aftershocks_12h_7d']} from 12 h to 7 days.{note}")
        if "permanent_stations" in r:
            lines.append(f"- Permanent stations: {r['permanent_stations']}. By network: {nets(r['permanent_networks'])}.")
            lines.append(f"- Temporary stations: {r['temporary_stations']}. By network: {nets(r['temporary_networks'])}.")
        funnel = " -> ".join(f"{k} {v}" for k, v in r["funnel"].items())
        lines.append(f"- Candidate pool: {r['pool_size']} points. Filter funnel: {funnel}.")
        lines.append(f"- Roads checked: {'yes' if r['roads_checked'] else '**no**'}"
                     + (f" (Overpass answer {r['overpass_bytes'] / 1e6:.1f} MB)" if r.get("overpass_bytes") else "")
                     + f"; terrain checked: {'yes' if r['terrain_checked'] else '**no**'}.")
        lines += [f"- **Warning:** {w}" for w in r["pool_warnings"]]
        lines += [f"- **Failed:** {e}" for e in r["errors"]]
        lines.append(f"- **Verdict: {r['verdict']}.**" + (" " + "; ".join(r["reasons"]) + "." if r["reasons"] else ""))
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    rows = []
    for key, b in sources.BENCHMARKS.items():
        print(f"{b['name']} ...", flush=True)
        rows.append(check(key, b))
        print(json.dumps({k: v for k, v in rows[-1].items() if k not in ("permanent_networks",)}, default=str),
              flush=True)
    (HERE / f"{STEM}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    notes = HERE / f"{STEM}_notes.md"
    text = render(rows)
    if notes.exists():
        text += "\n" + notes.read_text(encoding="utf-8")
    (HERE / f"{STEM}.md").write_text(text, encoding="utf-8")
    print(f"wrote {HERE / (STEM + '.md')}")


if __name__ == "__main__":
    main()
