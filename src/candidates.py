"""Reachable candidate sites for portable seismometers, for any earthquake (spec FR-6 to FR-8).

A pool is a 2 km grid inside the study radius, thinned by five filters:
  1. on land: elevation above sea level (AWS Terrain Tiles, "terrarium" encoding);
  2. slope under 20 degrees (same tiles);
  3. within 1.5 km of a road (OpenStreetMap through one Overpass query per event);
  4. at least 6 km from every permanent station (a new sensor there adds little);
  5. at least 3 km from supplied rupture points (crew safety).

If Overpass cannot be reached the pool is built from the grid and terrain only and is flagged
`feasibility_checked = False` (spec EC-5). The same flag is set if the terrain tiles fail.

All downloads go through `src.sources.http_get` (allowlist, cache, retries, offline mode).
Coordinates are local km about the mainshock epicentre, x east, y north.

Known limits, stated honestly:
  * "above sea level" does not detect lakes, and wrongly rejects land below sea level
    (for example parts of Death Valley);
  * slope is measured on pixels of roughly 75 to 150 m, so short steep ground is smoothed out;
  * only through-road classes are queried (ROAD_CLASSES), to keep the Overpass answer small.
"""
from __future__ import annotations

import io
import json
import math
import urllib.parse
from dataclasses import dataclass

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from src.sources import KM_PER_DEG, Projection, QuakeNetError, http_get

GRID_SPACING_KM = 2.0
ROAD_MAX_KM = 1.5
MAX_SLOPE_DEG = 20.0
MIN_STATION_GAP_KM = 6.0
MIN_RUPTURE_GAP_KM = 3.0
N_CANDIDATES = 10
MIN_SPACING_KM = 4.0
BACKUP_RADIUS_KM = 3.0
MAX_BACKUPS = 3

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Roads a field vehicle can use without local knowledge. Residential streets, service roads,
# tracks and paths are left out: they multiply the size of the answer many times over.
ROAD_CLASSES = ("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified")
ROAD_DENSIFY_KM = 0.2     # road lines are sampled at this step before distances are measured

TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
TILE_SIZE = 256
TARGET_PIXEL_M = 150.0    # zoom is chosen so that a pixel is at most this wide on the ground
EARTH_CIRCUMFERENCE_M = 40075016.686


# ------------------------------------------------------------------------------ grid

def make_grid(radius_km: float, spacing_km: float = GRID_SPACING_KM) -> np.ndarray:
    """(P, 2) grid nodes (x east, y north, km) inside a circle about the origin, origin included."""
    n = int(math.floor(radius_km / spacing_km))
    axis = np.arange(-n, n + 1) * spacing_km
    x, y = np.meshgrid(axis, axis, indexing="xy")
    xy = np.column_stack([x.ravel(), y.ravel()])
    return xy[np.hypot(xy[:, 0], xy[:, 1]) <= radius_km + 1e-9]


def bounding_box(lat0: float, lon0: float, radius_km: float) -> tuple[float, float, float, float]:
    """(south, west, north, east) in degrees of the square around the study circle."""
    dlat = radius_km / KM_PER_DEG
    dlon = radius_km / (KM_PER_DEG * math.cos(math.radians(lat0)))
    return lat0 - dlat, lon0 - dlon, lat0 + dlat, lon0 + dlon


# ----------------------------------------------------------------------------- roads

def overpass_url(bbox: tuple[float, float, float, float]) -> str:
    """One Overpass query for the `highway` ways of ROAD_CLASSES in a (south, west, north, east) box."""
    s, w, n, e = bbox
    query = (f'[out:json][timeout:25];way["highway"~"^({"|".join(ROAD_CLASSES)})$"]'
             f"({s:.4f},{w:.4f},{n:.4f},{e:.4f});out geom qt;")
    return f"{OVERPASS_URL}?data={urllib.parse.quote(query, safe='')}"


def parse_overpass(body: bytes) -> list[np.ndarray]:
    """Overpass JSON (`out geom`) -> one (n, 2) array of (lat, lon) per road."""
    data = json.loads(body)
    if "elements" not in data:
        raise QuakeNetError("FEED_UNAVAILABLE", "Overpass answer has no 'elements' list")
    # Overpass reports a query that ran out of time or memory in "remark", with HTTP 200.
    if not data["elements"] and "remark" in data:
        raise QuakeNetError("FEED_UNAVAILABLE", f"Overpass: {data['remark']}")
    roads = []
    for el in data["elements"]:
        geom = [p for p in el.get("geometry", []) if p]
        if el.get("type") == "way" and geom:
            roads.append(np.array([(p["lat"], p["lon"]) for p in geom], float))
    return roads


def fetch_roads(bbox: tuple[float, float, float, float]) -> list[np.ndarray]:
    return parse_overpass(http_get(overpass_url(bbox)))


def _densify(line: np.ndarray, step_km: float) -> np.ndarray:
    if len(line) < 2:
        return line
    seg = np.hypot(*np.diff(line, axis=0).T)
    dist = np.concatenate([[0.0], np.cumsum(seg)])
    if dist[-1] == 0.0:
        return line[:1]
    s = np.linspace(0.0, dist[-1], int(math.ceil(dist[-1] / step_km)) + 1)
    return np.column_stack([np.interp(s, dist, line[:, 0]), np.interp(s, dist, line[:, 1])])


def road_distance_km(xy: np.ndarray, roads_xy: list[np.ndarray]) -> np.ndarray:
    """Distance in km from each point to the nearest road line (inf if there are no roads).

    Roads are sampled every ROAD_DENSIFY_KM, so a distance near 1.5 km is exact to about 5 m.
    """
    pts = [_densify(np.asarray(r, float), ROAD_DENSIFY_KM) for r in roads_xy if len(r)]
    if not pts:
        return np.full(len(xy), np.inf)
    return cKDTree(np.vstack(pts)).query(np.asarray(xy, float))[0]


# --------------------------------------------------------------------------- terrain

def decode_terrarium(png: bytes) -> np.ndarray:
    """Terrarium PNG -> (256, 256) elevation in metres: R*256 + G + B/256 - 32768."""
    rgb = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.float64)
    return rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0 - 32768.0


def zoom_for_lat(lat: float, target_pixel_m: float = TARGET_PIXEL_M) -> int:
    """Smallest zoom whose pixels are at most target_pixel_m wide at this latitude (clipped to 7..12)."""
    z = math.ceil(math.log2(EARTH_CIRCUMFERENCE_M * math.cos(math.radians(lat)) / (TILE_SIZE * target_pixel_m)))
    return int(min(12, max(7, z)))


def tile_pixel(lat, lon, zoom: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Web-Mercator tile (x, y) and pixel (column, row) inside it, for each lat/lon."""
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    n = 2 ** zoom
    fx = (lon + 180.0) / 360.0 * n
    fy = (1.0 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2.0 * n
    tx, ty = np.floor(fx).astype(int), np.floor(fy).astype(int)
    col = np.clip(((fx - tx) * TILE_SIZE).astype(int), 0, TILE_SIZE - 1)
    row = np.clip(((fy - ty) * TILE_SIZE).astype(int), 0, TILE_SIZE - 1)
    return tx, ty, col, row


def pixel_size_m(lat: float, zoom: int) -> float:
    return EARTH_CIRCUMFERENCE_M * math.cos(math.radians(lat)) / (TILE_SIZE * 2 ** zoom)


def slope_degrees(elev: np.ndarray, pixel_m: float) -> np.ndarray:
    """Slope angle in degrees of an elevation grid with square pixels pixel_m wide."""
    dz_dy, dz_dx = np.gradient(np.asarray(elev, float), pixel_m)
    return np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))


def _tile_centre_lat(ty: int, zoom: int) -> float:
    return math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * (ty + 0.5) / 2 ** zoom))))


def sample_terrain(lat, lon, zoom: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(elevation in m, slope in degrees) at each lat/lon, from cached AWS Terrain Tiles.

    Only the tiles that contain a point are downloaded. Slope is computed inside each tile.
    """
    lat, lon = np.atleast_1d(np.asarray(lat, float)), np.atleast_1d(np.asarray(lon, float))
    zoom = zoom_for_lat(float(np.mean(lat))) if zoom is None else zoom
    tx, ty, col, row = tile_pixel(lat, lon, zoom)
    elev, slope = np.empty(len(lat)), np.empty(len(lat))
    for x, y in sorted({(int(a), int(b)) for a, b in zip(tx, ty)}):
        tile = decode_terrarium(http_get(TILE_URL.format(z=zoom, x=x, y=y)))
        tile_slope = slope_degrees(tile, pixel_size_m(_tile_centre_lat(y, zoom), zoom))
        m = (tx == x) & (ty == y)
        elev[m], slope[m] = tile[row[m], col[m]], tile_slope[row[m], col[m]]
    return elev, slope


# ------------------------------------------------------------------------------ pool

@dataclass(frozen=True)
class CandidatePool:
    lat0: float
    lon0: float
    radius_km: float
    xy: np.ndarray            # (P, 2) local km about (lat0, lon0), x east, y north
    lat: np.ndarray           # (P,)
    lon: np.ndarray           # (P,)
    elevation_m: np.ndarray   # (P,) NaN if the terrain was not checked
    slope_deg: np.ndarray     # (P,) NaN if the terrain was not checked
    road_km: np.ndarray       # (P,) distance to the nearest road, NaN if roads were not checked
    feasibility_checked: bool  # False if the road or the terrain check could not be done (EC-5)
    roads_checked: bool
    terrain_checked: bool
    funnel: dict              # points left after each filter, in order
    warnings: tuple

    def __len__(self) -> int:
        return len(self.xy)


def apply_filters(xy: np.ndarray, *, elevation_m=None, slope_deg=None, road_km=None,
                  stations_xy=None, rupture_xy=None, road_max_km: float = ROAD_MAX_KM,
                  max_slope_deg: float = MAX_SLOPE_DEG, station_gap_km: float = MIN_STATION_GAP_KM,
                  rupture_gap_km: float = MIN_RUPTURE_GAP_KM) -> tuple[np.ndarray, dict]:
    """Boolean keep-mask over xy and the funnel {filter name: points left}. A filter whose
    input is None (not available) is skipped and does not appear in the funnel."""
    xy = np.asarray(xy, float).reshape(-1, 2)
    keep = np.ones(len(xy), bool)
    funnel = {"grid": int(keep.sum())}

    def step(name: str, ok) -> None:
        keep[:] = keep & np.asarray(ok, bool)
        funnel[name] = int(keep.sum())

    def min_dist(points) -> np.ndarray:
        points = np.asarray(points, float).reshape(-1, 2)
        if not len(points):
            return np.full(len(xy), np.inf)
        return cKDTree(points).query(xy)[0]

    if elevation_m is not None:
        step("on_land", np.asarray(elevation_m, float) > 0.0)
    if slope_deg is not None:
        step("slope", np.asarray(slope_deg, float) < max_slope_deg)
    if road_km is not None:
        step("near_road", np.asarray(road_km, float) <= road_max_km)
    if stations_xy is not None:
        step("station_gap", min_dist(stations_xy) >= station_gap_km)
    if rupture_xy is not None:
        step("rupture_gap", min_dist(rupture_xy) >= rupture_gap_km)
    return keep, funnel


def _latlon_pairs(points) -> np.ndarray:
    """Accept rows of (lat, lon) or dicts with 'lat' and 'lon'; return an (n, 2) array."""
    points = list(points) if points is not None else []
    if points and isinstance(points[0], dict):
        points = [(p["lat"], p["lon"]) for p in points]
    return np.asarray(points, float).reshape(-1, 2)


def build_candidate_pool(lat0: float, lon0: float, radius_km: float, stations=(), rupture_points=(), *,
                         grid_km: float = GRID_SPACING_KM, road_max_km: float = ROAD_MAX_KM,
                         max_slope_deg: float = MAX_SLOPE_DEG, station_gap_km: float = MIN_STATION_GAP_KM,
                         rupture_gap_km: float = MIN_RUPTURE_GAP_KM, zoom: int | None = None) -> CandidatePool:
    """Pool of reachable candidate points around (lat0, lon0) (spec FR-6).

    stations and rupture_points are rows of (lat, lon) or dicts with 'lat' and 'lon'; pass the
    permanent stations. Never raises for a failed download: a failed road or terrain check is
    skipped, recorded in `warnings`, and sets feasibility_checked = False.
    """
    proj = Projection(lat0, lon0)
    grid = make_grid(radius_km, grid_km)
    lat, lon = proj.to_latlon(grid[:, 0], grid[:, 1])
    warnings = []

    elev = slope = None
    try:
        elev, slope = sample_terrain(lat, lon, zoom)
    except (QuakeNetError, OSError, ValueError) as err:
        warnings.append(f"terrain tiles unavailable, land and slope filters skipped: {err}")

    road = None
    try:
        roads = fetch_roads(bounding_box(lat0, lon0, radius_km))
        road = road_distance_km(grid, [proj.to_km(r[:, 0], r[:, 1]) for r in roads])
    except (QuakeNetError, ValueError) as err:
        warnings.append(f"Overpass unavailable, road filter skipped (grid and terrain only): {err}")

    st, rp = _latlon_pairs(stations), _latlon_pairs(rupture_points)
    keep, funnel = apply_filters(
        grid, elevation_m=elev, slope_deg=slope, road_km=road,
        stations_xy=proj.to_km(st[:, 0], st[:, 1]), rupture_xy=proj.to_km(rp[:, 0], rp[:, 1]),
        road_max_km=road_max_km, max_slope_deg=max_slope_deg,
        station_gap_km=station_gap_km, rupture_gap_km=rupture_gap_km)

    nan = np.full(len(grid), np.nan)
    return CandidatePool(
        lat0=float(lat0), lon0=float(lon0), radius_km=float(radius_km),
        xy=grid[keep], lat=lat[keep], lon=lon[keep],
        elevation_m=(nan if elev is None else elev)[keep],
        slope_deg=(nan if slope is None else slope)[keep],
        road_km=(nan if road is None else road)[keep],
        feasibility_checked=road is not None and elev is not None,
        roads_checked=road is not None, terrain_checked=elev is not None,
        funnel=funnel, warnings=tuple(warnings))


# ------------------------------------------------------------------------- selection

@dataclass(frozen=True)
class Selection:
    indices: tuple    # pool indices of the selected candidates, best gain first
    backups: tuple    # backups[i]: up to 3 pool indices near indices[i], nearest first

    def __len__(self) -> int:
        return len(self.indices)


def select_candidates(pool, gains, n: int = N_CANDIDATES, min_spacing_km: float = MIN_SPACING_KM, *,
                      backup_radius_km: float = BACKUP_RADIUS_KM, max_backups: int = MAX_BACKUPS) -> Selection:
    """Greedy spread selection (spec FR-8) and backup points (FR-7).

    Repeatedly takes the pool point with the highest gain that is at least min_spacing_km from
    every point already taken, until n are taken or none is left. Fewer than n may come back
    (spec EC-4); the caller decides what to do then. Ties go to the lower pool index.

    Backups are unselected pool points within backup_radius_km of a candidate. Each backup
    serves one candidate only, so two failed sites never compete for the same fallback.

    pool is a CandidatePool or a (P, 2) array of km coordinates; gains has one value per point.
    Points with a non-finite gain are never selected but can be backups.
    """
    xy = np.asarray(getattr(pool, "xy", pool), float).reshape(-1, 2)
    gains = np.asarray(gains, float)
    if gains.shape != (len(xy),):
        raise ValueError(f"gains must have one value per pool point: {gains.shape} vs {len(xy)} points")

    chosen: list[int] = []
    for i in np.argsort(-np.where(np.isfinite(gains), gains, -np.inf), kind="stable"):
        if len(chosen) >= n:
            break
        if not np.isfinite(gains[i]):
            break
        if all(np.hypot(*(xy[i] - xy[j])) >= min_spacing_km for j in chosen):
            chosen.append(int(i))

    used = set(chosen)
    backups = []
    for i in chosen:
        d = np.hypot(*(xy - xy[i]).T)
        near = [int(j) for j in np.argsort(d, kind="stable") if d[j] <= backup_radius_km and int(j) not in used]
        near = near[:max_backups]
        used.update(near)
        backups.append(tuple(near))
    return Selection(tuple(chosen), tuple(backups))
