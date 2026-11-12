"""Build the data and images used by the web landing page, all from real sources.

    python scripts/build_web_assets.py            # everything
    python scripts/build_web_assets.py --skip-relief --skip-world

Outputs
  web/public/relief/ridgecrest-2000.webp, ridgecrest-900.webp
      Shaded relief of the study area in the local km grid, from Mapzen Terrain Tiles on AWS
      (elevation data courtesy of the U.S. Geological Survey: 3DEP and SRTM).
  web/data/world-quakes.json
      Every magnitude 6.5+ earthquake since 2000 in the USGS ComCat catalogue: [lon, lat, mag].
  web/data/story.json
      The Ridgecrest instance and the headline numbers, read from results/results.json.

All downloads go through the outbound gateway in src/sources.py (allowlist, cache, retries).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.candidates import decode_terrarium  # noqa: E402
from src.geometry import DECISION_HOURS, KM_PER_DEG, LAT0, LON0, Scorer, load_instance, to_km  # noqa: E402
from src.location import location_errors  # noqa: E402
from src.sources import http_get  # noqa: E402

WEB = ROOT / "web"
EXTENT_KM = 64.0          # the relief covers x, y in [-64, 64] km of the local grid
ZOOM = 11
TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
WORLD_URL = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
             "&starttime=2000-01-01&endtime=2026-11-01&minmagnitude=6.5&orderby=time-asc")


# --------------------------------------------------------------------------- relief
def _mercator_px(lat, lon, zoom: int):
    n = 256.0 * 2**zoom
    x = (np.asarray(lon) + 180.0) / 360.0 * n
    rad = np.radians(lat)
    y = (1.0 - np.log(np.tan(rad) + 1.0 / np.cos(rad)) / math.pi) / 2.0 * n
    return x, y


def build_relief(size: int = 2000) -> None:
    from PIL import Image
    from scipy.ndimage import gaussian_filter, map_coordinates

    # output grid in local km (row 0 = north)
    axis = np.linspace(-EXTENT_KM, EXTENT_KM, size)
    xk, yk = np.meshgrid(axis, -axis)
    lat = LAT0 + yk / KM_PER_DEG
    lon = LON0 + xk / (KM_PER_DEG * math.cos(math.radians(LAT0)))
    px, py = _mercator_px(lat, lon, ZOOM)

    tx0, tx1 = int(px.min() // 256), int(px.max() // 256)
    ty0, ty1 = int(py.min() // 256), int(py.max() // 256)
    mosaic = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), dtype=np.float32)
    total = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    print(f"relief: {total} terrain tiles at zoom {ZOOM}")
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            tile = decode_terrarium(http_get(TILE_URL.format(z=ZOOM, x=tx, y=ty)))
            mosaic[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = tile

    elev = map_coordinates(mosaic, [py - ty0 * 256, px - tx0 * 256], order=1, mode="nearest")
    elev = gaussian_filter(elev, 1.2)
    print(f"relief: elevation {elev.min():.0f} to {elev.max():.0f} m")

    # hillshade: light from the north-west, blended with a softer light from the north
    cell_m = 2 * EXTENT_KM * 1000 / size
    gy, gx = np.gradient(elev * 2.2, cell_m)        # 2.2x vertical exaggeration
    slope = np.pi / 2 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(gy, -gx)

    def shade(azimuth_deg: float, altitude_deg: float) -> np.ndarray:
        az, alt = np.radians(360 - azimuth_deg + 90), np.radians(altitude_deg)
        return np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect)

    s = 0.7 * shade(315, 45) + 0.3 * shade(0, 60)
    flat = 0.7 * math.sin(math.radians(45)) + 0.3 * math.sin(math.radians(60))
    dark = np.clip((flat - s) / flat, 0, 1) ** 0.9
    light = np.clip((s - flat) / (1 - flat), 0, 1)

    # palette: pale mist in the valleys, lighter paper on high ground, ink-green shadows
    t = np.clip((elev - 500) / 2200, 0, 1)[..., None]
    low, high = np.array([214, 222, 216], float), np.array([238, 241, 236], float)
    ink, white = np.array([44, 68, 52], float), np.array([255, 255, 255], float)
    rgb = low + (high - low) * t
    rgb = rgb + (ink - rgb) * (dark[..., None] * 0.62)
    rgb = rgb + (white - rgb) * (light[..., None] * 0.55)
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")

    out = WEB / "public" / "relief"
    out.mkdir(parents=True, exist_ok=True)
    img.save(out / "ridgecrest-2000.webp", quality=80, method=6)
    img.resize((900, 900), Image.LANCZOS).save(out / "ridgecrest-900.webp", quality=78, method=6)
    for f in sorted(out.glob("*.webp")):
        print(f"relief: wrote {f.relative_to(ROOT)} ({f.stat().st_size // 1024} KB)")


# --------------------------------------------------------------------------- world earthquakes
def build_world() -> None:
    feats = json.loads(http_get(WORLD_URL))["features"]
    rows = [[round(f["geometry"]["coordinates"][0], 2), round(f["geometry"]["coordinates"][1], 2),
             f["properties"]["mag"]] for f in feats if f["properties"].get("mag") is not None]
    out = WEB / "data" / "world-quakes.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(source="USGS ComCat", min_magnitude=6.5, since="2000-01-01",
                                   until="2026-11-01", quakes=rows), separators=(",", ":")))
    print(f"world: {len(rows)} earthquakes of magnitude 6.5+ -> {out.relative_to(ROOT)}")


# --------------------------------------------------------------------------- story data
def build_story() -> None:
    events = json.loads((ROOT / "data" / "events.json").read_text())["events"]
    stations = json.loads((ROOT / "data" / "stations.json").read_text())["stations"]
    results = json.loads((ROOT / "results" / "results.json").read_text())
    inst = load_instance()

    main = max(events, key=lambda e: e["mag"])
    t0 = main["time_ms"]

    def rows(sel):
        xy = to_km([e["lat"] for e in sel], [e["lon"] for e in sel])
        return [[round(float(x), 2), round(float(y), 2), round(max(e["depth_km"], 0.5), 1), e["mag"],
                 round((e["time_ms"] - t0) / 3.6e6, 2)] for (x, y), e in zip(xy, sel)]

    early = [e for e in events if t0 < e["time_ms"] <= t0 + DECISION_HOURS * 3.6e6]
    later = [e for e in events if e["time_ms"] > t0 + DECISION_HOURS * 3.6e6]
    assert len(early) == len(inst.design) and len(later) == len(inst.valid)
    assert np.allclose(np.array(rows(early))[:, :2], inst.design[:, :2], atol=0.01)

    # every possible network, tested in the independent location experiment (same seed as the report)
    sets = inst.feasible_sets()
    print(f"story: locating later aftershocks with all {len(sets)} networks ...")
    errors = np.array([location_errors(inst, s, inst.valid, trials=1).mean() for s in sets])
    methods = results["methods"]
    pick = tuple(methods["Hybrid QAOA (XY mixer)"]["sites"])
    expert = tuple(methods["Expert rule (azimuthal gap)"]["sites"])
    order = np.argsort(errors)
    lt = results["location_test"]
    assert abs(float(errors.mean()) - lt["all_networks_mean_km"]) < 1e-6, "location test differs from results.json"

    runs = results["qaoa"]["runs"]
    by_layers = {}
    for p in sorted({r["reps"] for r in runs}):
        rs = [r for r in runs if r["reps"] == p]
        by_layers[str(p)] = dict(p_best=float(np.mean([r["xy_p_opt"] for r in rs])), gates=rs[0]["xy_gates"])

    nearest = [float(-5.0 * math.log(c)) for c in inst.risk]     # km to the nearest early aftershock
    scorer_valid = Scorer(inst, inst.valid)
    story = dict(
        event=dict(name="Ridgecrest, California", magnitude=main["mag"], lat=main["lat"], lon=main["lon"],
                   depth_km=main["depth_km"], time_ms=t0),
        grid=dict(lat0=LAT0, lon0=LON0, km_per_deg=KM_PER_DEG, extent_km=EXTENT_KM),
        mainshock=[round(float(v), 2) for v in inst.mainshock],
        early=rows(early), later=rows(later),
        stations=[dict(name=s["sta"], x=round(float(x), 2), y=round(float(y), 2))
                  for s, (x, y) in zip(stations, inst.stations)],
        candidates=[dict(id=i, x=round(float(x), 2), y=round(float(y), 2), risk=round(float(r), 2),
                         nearest_km=round(nearest[i], 1))
                    for i, ((x, y), r) in enumerate(zip(inst.candidates, inst.risk))],
        pick=list(pick), expert=list(expert),
        numbers=dict(
            decision_hours=DECISION_HOURS, early=len(early), later=len(later), stations=len(stations),
            candidates=inst.n, sensors=inst.k, networks=len(sets),
            terms_exact=next(f["terms"] for f in results["formulation"]["fidelity"] if f["order"] == 4),
            runs=len(runs), runs_exact=int(sum(r["xy_final_is_exact"] for r in runs)),
            uniform_p_best=results["qaoa"]["uniform_p_opt"], by_layers=by_layers,
            error_none_km=lt["no_new_sensors_mean_km"], error_average_km=lt["all_networks_mean_km"],
            error_expert_km=methods["Expert rule (azimuthal gap)"]["loc_error_mean_km"],
            error_pick_km=methods["Hybrid QAOA (XY mixer)"]["loc_error_mean_km"],
            pick_rank_in_test=lt["rank_of_qaoa_pick"],
            blur_none_km=results["blur"]["no_new_sensors_valid_km"], blur_pick_km=scorer_valid.blur_km(pick)),
        sorted_errors=[round(float(errors[i]), 3) for i in order],
        pick_position=int(np.where(order == sets.index(pick))[0][0]),
        expert_position=int(np.where(order == sets.index(expert))[0][0]),
    )
    out = WEB / "data" / "story.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(story, separators=(",", ":")))
    n = story["numbers"]
    print(f"story: wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB); "
          f"error {n['error_none_km']:.2f} -> {n['error_pick_km']:.2f} km, pick is "
          f"{story['pick_position'] + 1} of {len(sets)} in the sorted test")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-relief", action="store_true")
    ap.add_argument("--skip-world", action="store_true")
    ap.add_argument("--skip-story", action="store_true")
    args = ap.parse_args()
    if not args.skip_relief:
        build_relief()
    if not args.skip_world:
        build_world()
    if not args.skip_story:
        build_story()
