"""Earthquake events for the agent: registry, cached data, synthetic aftershocks, site selection.

This is the only door the agent (`src/agent/`) and the API (`api/`) use to reach real earthquake
data. Signatures are fixed by docs/API.md ("Internal interfaces between the science layer and
the agent"); the internals are free.

Registry
  * the six benchmark earthquakes of `src.sources.BENCHMARKS` (kind "benchmark");
  * live earthquakes registered by `event_from_usgs` (kind "live"), saved in var/events.json
    (or the file named by QUAKENET_EVENTS_FILE) so they survive a restart.

Data of one event (`EventData`), all through the outbound gateway and its cache:
  * mainshock from USGS ComCat; aftershocks M >= 2.5 within the study radius for 7 days;
  * permanent stations (operating at the mainshock) within the study radius (benchmarks) or
    `station_radius_km` (live events), from IRIS/EarthScope;
  * the candidate pool of src.candidates (2 km grid, land, slope, roads, station and rupture gaps).
    Roads are read from the cache only (a slow Overpass must not hold up a request). When the
    road answer is missing the pool is grid plus terrain and `feasibility_checked` is False.
    `retry_road_query` asks Overpass once more, politely.

Local km grid: x east, y north about (lat0, lon0). For Ridgecrest 2019 the centre stays at
src.geometry.LAT0/LON0 so site numbers match the published proof of concept; every other event is
centred on its epicentre.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from . import candidates as cands
from . import sources
from .geometry import (LAT0, LON0, N_CANDIDATES, PRIOR_KM, PRIOR_S, RISK_LENGTH_KM, SIGMA_T, Instance, _rows,
                       load_instance)
from .sources import Projection, QuakeNetError

REPO_DIR = Path(__file__).resolve().parent.parent
AFTERSHOCK_DAYS = 7          # aftershocks are read for this long after the mainshock
MIN_MAG = 2.5                # catalogue cut-off of the aftershocks
MIN_DEPTH_KM = 0.5           # depths are clipped here (as in src.geometry.load_instance)
SYNTH_TOTAL = 200            # planning set size when real aftershocks are topped up
SYNTH_CROSS_KM = 2.0         # standard deviation of synthetic events across the fault
SYNTH_DEPTH_SD_KM = 3.0      # standard deviation of synthetic depths about the mainshock depth
SYNTH_DEPTH_RANGE = (1.0, 20.0)
GR_B = 1.0                   # Gutenberg-Richter b-value of synthetic magnitudes
LIVE_MAX_AGE_S = 600.0       # aftershocks of a live event younger than 8 days are re-read every 10 min
LIVE_MEMO_S = 600.0
RIDGECREST = "ridgecrest2019"
_USGS_ID = re.compile(r"^[A-Za-z0-9_-]{2,40}$")


def events_file() -> Path:
    return Path(os.environ.get("QUAKENET_EVENTS_FILE") or REPO_DIR / "var" / "events.json")


# --------------------------------------------------------------------------- data class

@dataclass(frozen=True)
class EventData:
    event_id: str                    # our id, for example "ridgecrest2019"
    usgs_id: str
    name: str
    magnitude: float
    time_utc: datetime
    lat: float
    lon: float
    depth_km: float
    lat0: float                      # centre of the local km grid (x east, y north)
    lon0: float
    aftershocks: np.ndarray          # (M, 5): x_km, y_km, depth_km, magnitude, hours_after_mainshock
    stations: np.ndarray             # (S, 2) permanent stations in km
    station_names: tuple[str, ...]
    pool: np.ndarray                 # (P, 2) reachable candidate points in km
    feasibility_checked: bool        # False when the road check was unavailable
    radius_km: float

    def to_latlon(self, x_km, y_km) -> tuple[float, float]:
        lat, lon = Projection(self.lat0, self.lon0).to_latlon(x_km, y_km)
        if np.ndim(lat) == 0:
            return float(lat), float(lon)
        return lat, lon

    def to_km(self, lat, lon) -> np.ndarray:
        return Projection(self.lat0, self.lon0).to_km(lat, lon)

    @property
    def epicentre_km(self) -> np.ndarray:
        return self.to_km(self.lat, self.lon)


# --------------------------------------------------------------------------- registry

_lock = threading.RLock()
_memo: dict[tuple, tuple[float, EventData]] = {}


def _benchmark_entry(key: str, b: dict) -> dict:
    return dict(usgs_id=b["usgs_id"], aliases=list(b.get("aliases", ())), name=b["name"], mag=float(b["mag"]),
                time=b["time"], lat=float(b["lat"]), lon=float(b["lon"]), depth_km=float(b["depth_km"]),
                kind="benchmark", station_radius_km=None)


def _live_entries() -> dict[str, dict]:
    path = events_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.get("events", {}).items() if isinstance(v, dict) and v.get("kind") == "live"}


def _save_live(entries: dict[str, dict]) -> None:
    path = events_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(dict(events=entries), indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _registry() -> dict[str, dict]:
    reg = {k: _benchmark_entry(k, b) for k, b in sources.BENCHMARKS.items()}
    for k, v in _live_entries().items():
        reg.setdefault(k, v)
    return reg


def _t0(entry: dict) -> datetime:
    return sources._as_utc(entry["time"])


def _urls(entry: dict) -> dict[str, str]:
    """The three gateway URLs an event needs, built exactly as research/benchmarks/data_quality.py does."""
    radius = sources.study_radius_km(entry["mag"])
    t0 = _t0(entry)
    st_radius = entry.get("station_radius_km") or radius
    return dict(mainshock=sources.mainshock_url(entry["usgs_id"]),
                aftershocks=sources.aftershocks_url(entry["lat"], entry["lon"], radius, t0,
                                                    t0 + timedelta(days=AFTERSHOCK_DAYS)),
                stations=sources.stations_url(entry["lat"], entry["lon"], st_radius, t0))


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def list_events() -> list[dict]:
    """Every registered event: id, usgs_id, name, magnitude, time_utc, lat, lon, kind, cached.

    `cached` is True when the mainshock, aftershock and station answers are all in the cache, so
    the event can be loaded with no network.
    """
    out = []
    for key, e in _registry().items():
        out.append(dict(id=key, usgs_id=e["usgs_id"], name=e["name"], magnitude=e["mag"], time_utc=_iso(_t0(e)),
                        lat=e["lat"], lon=e["lon"], kind=e["kind"],
                        cached=all(sources.cache_info(u) is not None for u in _urls(e).values())))
    return out


# --------------------------------------------------------------------------- loading

def _get(url: str, max_age_s: float | None) -> bytes:
    """Gateway read; for a stale live copy whose refresh fails, fall back to the cached copy."""
    try:
        return sources.http_get(url, max_age_s=max_age_s)
    except QuakeNetError as err:
        if max_age_s is not None and err.code == "FEED_UNAVAILABLE" and sources.cache_info(url):
            return sources.http_get(url)
        raise


def _build_event_data(event_id: str, entry: dict, *, radius_km: float | None = None,
                      station_radius_km: float | None = None, pool_radius_km: float | None = None,
                      days: float = AFTERSHOCK_DAYS, roads_online: bool = False,
                      max_age_s: float | None = None) -> EventData:
    """Download (or read from the cache) everything one event needs. The radius arguments exist
    for tests with small fixtures; by default they follow spec FR-3."""
    main = sources._event_row(json.loads(sources.http_get(sources.mainshock_url(entry["usgs_id"]))))
    t0 = datetime.fromtimestamp(main["time_ms"] / 1000, timezone.utc)
    radius = sources.study_radius_km(main["mag"]) if radius_km is None else float(radius_km)
    st_radius = station_radius_km or entry.get("station_radius_km") or radius
    pool_radius = radius if pool_radius_km is None else float(pool_radius_km)

    lat0, lon0 = (LAT0, LON0) if event_id == RIDGECREST else (main["lat"], main["lon"])
    proj = Projection(lat0, lon0)

    body = _get(sources.aftershocks_url(main["lat"], main["lon"], radius, t0, t0 + timedelta(days=days)), max_age_s)
    rows = [q for q in sources.parse_events(body)
            if q["time_ms"] > main["time_ms"] and q["id"] != main["id"] and q["mag"] >= MIN_MAG]
    rows.sort(key=lambda q: q["time_ms"])
    if rows:
        xy = proj.to_km([q["lat"] for q in rows], [q["lon"] for q in rows])
        after = np.column_stack([xy, np.clip([q["depth_km"] for q in rows], MIN_DEPTH_KM, None),
                                 [q["mag"] for q in rows],
                                 [(q["time_ms"] - main["time_ms"]) / 3.6e6 for q in rows]])
    else:
        after = np.zeros((0, 5))

    permanent, _ = sources.parse_stations(_get(sources.stations_url(main["lat"], main["lon"], st_radius, t0), None), t0)
    if not permanent:
        raise QuakeNetError("NO_STATIONS", f"no permanent station within {st_radius:.0f} km of {entry['usgs_id']}")
    stations = proj.to_km([s["lat"] for s in permanent], [s["lon"] for s in permanent])
    names = tuple(f"{s['net']}.{s['sta']}" for s in permanent)

    pool = cands.build_candidate_pool(main["lat"], main["lon"], pool_radius, permanent,
                                      [(main["lat"], main["lon"])], roads_online=roads_online,
                                      road_bbox=_road_bbox(entry, pool_radius_km))
    pool_xy = proj.to_km(pool.lat, pool.lon) if len(pool) else np.zeros((0, 2))

    arrays = [after, stations, pool_xy]
    for a in arrays:
        a.setflags(write=False)
    return EventData(event_id=event_id, usgs_id=entry["usgs_id"], name=entry["name"], magnitude=float(main["mag"]),
                     time_utc=t0, lat=float(main["lat"]), lon=float(main["lon"]), depth_km=float(main["depth_km"]),
                     lat0=float(lat0), lon0=float(lon0), aftershocks=after, stations=stations, station_names=names,
                     pool=pool_xy, feasibility_checked=bool(pool.feasibility_checked), radius_km=float(radius))


def _live_max_age(entry: dict) -> float | None:
    """Live events younger than 8 days still gain aftershocks, so their answer is refreshed."""
    if entry["kind"] != "live":
        return None
    young = datetime.now(timezone.utc) - _t0(entry) < timedelta(days=AFTERSHOCK_DAYS + 1)
    return LIVE_MAX_AGE_S if young else None


def load_event_data(event_id: str) -> EventData:
    """EventData of a registered event. QuakeNetError NOT_FOUND (not registered), CACHE_MISS
    (offline and not cached) or FEED_UNAVAILABLE (a download failed)."""
    entry = _registry().get(event_id)
    if entry is None:
        raise QuakeNetError("NOT_FOUND", f"no event {event_id!r}; see list_events()")
    key = (event_id, str(sources.cache_dir()))
    with _lock:
        hit = _memo.get(key)
        if hit and (entry["kind"] == "benchmark" or time.monotonic() - hit[0] < LIVE_MEMO_S):
            return hit[1]
    data = _build_event_data(event_id, entry, max_age_s=_live_max_age(entry))
    with _lock:
        _memo[key] = (time.monotonic(), data)
    return data


def clear_memo() -> None:
    with _lock:
        _memo.clear()


def event_from_usgs(usgs_id: str, *, station_radius_km: float = 100.0) -> EventData:
    """Any USGS event by its ComCat id. Registers it as kind "live" (saved to var/events.json).

    A benchmark's own id (or alias) returns that benchmark. QuakeNetError INVALID_INPUT (bad id),
    NOT_FOUND (ComCat does not know it), NO_STATIONS (no permanent station within
    station_radius_km), CACHE_MISS or FEED_UNAVAILABLE.
    """
    if not isinstance(usgs_id, str) or not _USGS_ID.match(usgs_id):
        raise QuakeNetError("INVALID_INPUT", "usgs_id must be 2 to 40 letters, digits, '_' or '-'")
    if not 0 < float(station_radius_km) <= 1000:
        raise QuakeNetError("INVALID_INPUT", "station_radius_km must be in (0, 1000]")
    for key, b in sources.BENCHMARKS.items():
        if usgs_id.lower() in {b["usgs_id"].lower(), *(a.lower() for a in b.get("aliases", ()))}:
            return load_event_data(key)
    try:
        main = sources.fetch_mainshock(usgs_id)
    except QuakeNetError as err:
        if err.code == "FEED_UNAVAILABLE" and ("HTTP 404" in err.message or "HTTP 400" in err.message):
            raise QuakeNetError("NOT_FOUND", f"USGS ComCat has no event {usgs_id}") from err
        raise
    event_id = usgs_id.lower()
    t0 = datetime.fromtimestamp(main["time_ms"] / 1000, timezone.utc)
    entry = dict(usgs_id=main["id"] or usgs_id, aliases=[], name=main.get("place") or f"M{main['mag']} {usgs_id}",
                 mag=float(main["mag"]), time=_iso(t0), lat=float(main["lat"]), lon=float(main["lon"]),
                 depth_km=float(main["depth_km"]), kind="live", station_radius_km=float(station_radius_km))
    # Build before registering, so an event with no station is never listed.
    data = _build_event_data(event_id, entry, roads_online=True, max_age_s=_live_max_age(entry))
    with _lock:
        live = _live_entries()
        live[event_id] = entry
        _save_live(live)
        _memo[(event_id, str(sources.cache_dir()))] = (time.monotonic(), data)
    return data


def _road_bbox(entry: dict, radius_km: float | None = None) -> tuple[float, float, float, float]:
    """Box of an event's road query, from the registry's epicentre (rounded to 4 decimals for the
    benchmarks). ComCat's own coordinates can differ in the 5th decimal (about 10 m), which would
    change the query text and miss the cached answer; the difference is far below the 2 km grid."""
    radius = sources.study_radius_km(entry["mag"]) if radius_km is None else float(radius_km)
    return cands.bounding_box(entry["lat"], entry["lon"], radius)


def retry_road_query(event_id: str, pause_s: float = 30.0) -> dict:
    """Ask Overpass for an event's roads once more, politely: one attempt, a pause of `pause_s`
    after a failure (429, 406, 5xx or timeout), one retry, then stop. The gateway identifies the
    app in its User-Agent. Returns {"event_id", "ok", "attempts", "error"}."""
    entry = _registry().get(event_id)
    if entry is None:
        raise QuakeNetError("NOT_FOUND", f"no event {event_id!r}")
    url = cands.overpass_url(_road_bbox(entry))
    if sources.cache_info(url):
        return dict(event_id=event_id, ok=True, attempts=0, error=None)
    error = None
    for attempt in (1, 2):
        try:
            body = sources.http_get(url, retries=0, timeout_s=120.0)
            try:
                cands.parse_overpass(body)
            except (QuakeNetError, ValueError):
                for f in sources.cache_paths(url):      # an error answer must not stay cached
                    f.unlink(missing_ok=True)
                raise
            clear_memo()
            return dict(event_id=event_id, ok=True, attempts=attempt, error=None)
        except (QuakeNetError, ValueError) as err:
            error = str(err)
            if attempt == 1:
                sources._sleep(pause_s)
    return dict(event_id=event_id, ok=False, attempts=2, error=error)


# --------------------------------------------------------------------------- synthetic aftershocks

def synthetic_aftershocks(magnitude: float, depth_km: float, *, n: int = 200, seed: int = 0,
                          strike_deg: float | None = None) -> np.ndarray:
    """(n, 5) synthetic aftershocks about the epicentre at (0, 0): x, y, depth, magnitude, hours = 0.

    * Positions: uniform along a line through the epicentre whose length is the subsurface rupture
      length of Wells & Coppersmith (1994), log10 L = -2.44 + 0.59 M, with a strike of `strike_deg`
      (clockwise from north; drawn from the seed when None) and normal scatter of 2 km across it.
    * Depths: normal about the mainshock depth (sd 3 km), clipped to 1-20 km.
    * Magnitudes: Gutenberg-Richter with b = 1 above 2.5, truncated one unit below the mainshock
      (the largest aftershock is usually about 1.2 units smaller, Bath's law).
    A crude prior for the first hours; deterministic for a given seed.
    """
    rng = np.random.default_rng(seed)
    strike = rng.uniform(0.0, 180.0) if strike_deg is None else float(strike_deg)
    length = sources.rupture_length_km(float(magnitude))
    along = rng.uniform(-length / 2, length / 2, size=n)
    across = rng.normal(0.0, SYNTH_CROSS_KM, size=n)
    s = np.radians(strike)
    u, w = np.array([np.sin(s), np.cos(s)]), np.array([np.cos(s), -np.sin(s)])  # along and across strike
    xy = along[:, None] * u + across[:, None] * w
    depth = np.clip(rng.normal(float(depth_km), SYNTH_DEPTH_SD_KM, size=n), *SYNTH_DEPTH_RANGE)
    m_max = max(float(magnitude) - 1.0, MIN_MAG + 0.1)
    beta = GR_B * np.log(10.0)
    q = rng.uniform(0.0, 1.0, size=n)
    mags = MIN_MAG - np.log(1.0 - q * (1.0 - np.exp(-beta * (m_max - MIN_MAG)))) / beta
    return np.column_stack([xy, depth, mags, np.zeros(n)])


def _strike_of(xy: np.ndarray) -> float | None:
    """Strike (degrees clockwise from north, 0-180) of the main axis of an epicentre cloud."""
    if len(xy) < 5:
        return None
    c = np.cov((xy - xy.mean(axis=0)).T)
    vals, vecs = np.linalg.eigh(c)
    if vals[-1] <= 1.5 * max(vals[0], 1e-12):       # no clear direction
        return None
    vx, vy = vecs[:, -1]
    return float(np.degrees(np.arctan2(vx, vy)) % 180.0)


def planning_events(data: EventData, at_hours: float, *, min_real: int = 30,
                    seed: int = 0) -> tuple[np.ndarray, bool]:
    """Real aftershocks with hours <= at_hours; when fewer than min_real exist they are topped up
    with synthetic ones (centred on the epicentre, strike from the real ones when they show one)
    to SYNTH_TOTAL events. Returns (events (E, 5), synthetic_used)."""
    real = data.aftershocks[data.aftershocks[:, 4] <= at_hours] if len(data.aftershocks) else np.zeros((0, 5))
    if len(real) >= min_real:
        return np.array(real), False
    synth = synthetic_aftershocks(data.magnitude, data.depth_km, n=max(SYNTH_TOTAL - len(real), min_real),
                                  seed=seed, strike_deg=_strike_of(real[:, :2]))
    synth[:, :2] += data.epicentre_km
    return np.vstack([synth, real]), True


# --------------------------------------------------------------------------- candidate sites

def single_site_gains(stations: np.ndarray, points: np.ndarray, events: np.ndarray) -> np.ndarray:
    """D-criterion gain of adding each point alone to the permanent network, summed over events:
    sum_e log(1 + g^T F_e^-1 g / sigma^2) (matrix determinant lemma). A weak prior keeps F_e
    invertible when few stations exist; it does not change the ranking much."""
    xyz = np.asarray(events, float)[:, :3]
    gp = _rows(xyz, np.asarray(stations, float).reshape(-1, 2))
    base = np.einsum("esi,esj->eij", gp, gp) / SIGMA_T**2 + np.diag([PRIOR_KM**-2] * 3 + [PRIOR_S**-2])
    inv = np.linalg.inv(base)
    out = np.empty(len(points))
    for start in range(0, len(points), 500):             # chunks keep memory small
        g = _rows(xyz, np.asarray(points, float)[start:start + 500])
        quad = np.einsum("epi,eij,epj->ep", g, inv, g) / SIGMA_T**2
        out[start:start + 500] = np.log1p(quad).sum(axis=0)
    return out


def _backups(pool: np.ndarray, chosen_xy: np.ndarray, exclude=()) -> list[list[int]]:
    """Up to MAX_BACKUPS pool points within BACKUP_RADIUS_KM of each candidate, nearest first,
    each serving one candidate only (same rule as src.candidates.select_candidates)."""
    used = set(exclude)
    out = []
    for c in chosen_xy:
        if not len(pool):
            out.append([])
            continue
        d = np.hypot(*(pool - c).T)
        near = [int(j) for j in np.argsort(d, kind="stable")
                if d[j] <= cands.BACKUP_RADIUS_KM and int(j) not in used][:cands.MAX_BACKUPS]
        used.update(near)
        out.append(near)
    return out


def select_sites(data: EventData, events: np.ndarray, *, n: int = 10,
                 min_spacing_km: float = 4.0) -> tuple[np.ndarray, list[list[tuple[float, float]]]]:
    """(candidates (n, 2) in km, up to 3 backup (lat, lon) points per candidate).

    Ridgecrest 2019 with n = 10: the ten candidates of src.geometry.load_instance(), in the same
    order, so site numbers match the published experiment (backups still come from the pool).
    Every other case: greedy spread selection (spec FR-8) on single-site gain over `events`.
    Fewer than n come back when the pool is too small (spec EC-4).
    """
    pool = np.asarray(data.pool, float).reshape(-1, 2)
    if data.event_id == RIDGECREST and n == N_CANDIDATES:
        chosen = np.array(load_instance().candidates, float)
        backups = _backups(pool, chosen)
    else:
        gains = single_site_gains(data.stations, pool, events) if len(pool) else np.zeros(0)
        sel = cands.select_candidates(pool, gains, n=n, min_spacing_km=min_spacing_km)
        chosen = pool[list(sel.indices)] if len(sel) else np.zeros((0, 2))
        backups = [list(b) for b in sel.backups]
    latlon = [[data.to_latlon(*pool[j]) for j in b] for b in backups]
    return chosen, latlon


def make_instance(data: EventData, candidates: np.ndarray, events: np.ndarray, *, k: int = 4,
                  valid: np.ndarray | None = None) -> Instance:
    """src.geometry.Instance for a plan. Design events = `events`; access risk is recomputed from
    them (exp(-d / 5 km), d = distance to the nearest design epicentre, as in load_instance).

    valid: later aftershocks to test on, (V, 3) or (V, 5). When None: every real aftershock later
    than the latest event in `events` (all of them when `events` has no time column or only
    synthetic events at hour 0).
    """
    ev = np.asarray(events, float)
    design = np.column_stack([ev[:, :2], np.clip(ev[:, 2], MIN_DEPTH_KM, None)])
    design_mag = ev[:, 3].copy() if ev.shape[1] >= 4 else None
    if valid is None:
        t_dec = float(ev[:, 4].max()) if ev.shape[1] >= 5 and len(ev) else 0.0
        valid = data.aftershocks[data.aftershocks[:, 4] > t_dec] if len(data.aftershocks) else np.zeros((0, 5))
    valid = np.asarray(valid, float).reshape(-1, np.shape(valid)[1] if np.ndim(valid) == 2 else 3)
    valid_xyz = np.column_stack([valid[:, :2], np.clip(valid[:, 2], MIN_DEPTH_KM, None)])
    valid_mag = valid[:, 3].copy() if valid.shape[1] >= 4 else None
    cand = np.asarray(candidates, float).reshape(-1, 2)
    if len(design):
        d = np.linalg.norm(cand[:, None] - design[None, :, :2], axis=2).min(axis=1)
    else:
        d = np.full(len(cand), np.inf)
    risk = np.exp(-d / RISK_LENGTH_KM)
    epi = data.epicentre_km
    mainshock = np.array([epi[0], epi[1], max(data.depth_km, MIN_DEPTH_KM)])
    return Instance(design, valid_xyz, np.array(data.stations, float), tuple(data.station_names), cand, risk,
                    mainshock, k=k, design_mag=design_mag, valid_mag=valid_mag)
