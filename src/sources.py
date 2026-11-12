"""Data sources for any earthquake: outbound gateway, USGS/IRIS fetchers, projection.

Everything QuakeNet-Q downloads goes through `http_get`, the single outbound gateway
(docs/ARCHITECTURE.md section 3.1, spec FR-5 and NFR-3):

  * host allowlist: only the hosts in ALLOWED_HOSTS can be called (redirects are checked too);
  * 30 s timeout, 3 retries with exponential backoff and jitter, honours 429 / Retry-After
    (Overpass: a 30 s pause after 429 or 406, as its usage policy asks);
  * requests are strictly sequential, with a minimum gap per host (EarthScope allows at most
    5 concurrent connections and 10 per second; we use 1 connection and 1 request per second);
  * every response is cached on disk under data/cache/, keyed by the SHA-256 of the URL,
    with a sidecar JSON recording the URL and the retrieval time;
  * offline mode (environment variable QUAKENET_OFFLINE=1) never touches the network and
    raises QuakeNetError("CACHE_MISS", ...) when a URL is not in the cache.

Sources (public, no API key):
  * USGS ComCat FDSN event service      -> mainshock and aftershocks (GeoJSON)
  * IRIS/EarthScope FDSN station service -> stations of all networks (text)

Conventions follow src/geometry.py: local kilometre grid, x east, y north.
"""
from __future__ import annotations

import gzip
import hashlib
import http.client
import json
import math
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_DIR = REPO_DIR / "data" / "cache"

# service.earthscope.org is not a source of its own: service.iris.edu answers every
# request with a 301 redirect to it (observed 2026-11-12), so it must be reachable.
ALLOWED_HOSTS = frozenset({
    "earthquake.usgs.gov",
    "service.iris.edu",
    "service.earthscope.org",
    "overpass-api.de",
    "s3.amazonaws.com",
})
USER_AGENT = "quakenet-q/0.2 (hackathon research prototype; cached, low-volume client)"
TIMEOUT_S = 30.0
RETRIES = 3                 # retries after the first attempt, so at most 4 attempts
BACKOFF_BASE_S = 1.0        # wait = base * 2**attempt + jitter
MAX_RETRY_AFTER_S = 120.0   # never sleep longer than this on a Retry-After header
# Politeness: minimum seconds between two network requests to the same host.
MIN_INTERVAL_S = {"s3.amazonaws.com": 0.05}
DEFAULT_MIN_INTERVAL_S = 1.0
# Hosts whose usage policy asks for a fixed pause after HTTP 429 or 406 (seconds).
SLOW_DOWN_PAUSE_S = {"overpass-api.de": 30.0}

KM_PER_DEG = 111.19         # same constant as src/geometry.py
TEMPORARY_WINDOW_DAYS = 30  # a station that starts within this many days is a "temporary deployment"
EXCLUDED_NETWORKS = frozenset({"SY"})  # SY = synthetic seismograms, not real instruments


class QuakeNetError(Exception):
    """Error contract of the spec: a short machine-readable code plus a message."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# --------------------------------------------------------------------------- gateway

_sleep = time.sleep          # replaced in tests
_last_request: dict[str, float] = {}


class _AllowlistRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only if its target is on the allowlist."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_host(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_AllowlistRedirect)


def _urlopen(req: urllib.request.Request, timeout: float):  # replaced in tests
    return _OPENER.open(req, timeout=timeout)


def cache_dir() -> Path:
    """Cache directory: data/cache/, or the QUAKENET_CACHE_DIR environment variable."""
    return Path(os.environ.get("QUAKENET_CACHE_DIR") or DEFAULT_CACHE_DIR)


def is_offline() -> bool:
    return os.environ.get("QUAKENET_OFFLINE", "").strip().lower() in {"1", "true", "yes"}


def _check_host(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in ALLOWED_HOSTS:
        raise QuakeNetError("HOST_NOT_ALLOWED", f"outbound gateway refuses {parts.scheme}://{host or '?'}; "
                            f"allowed hosts (https only): {', '.join(sorted(ALLOWED_HOSTS))}")
    return host


def cache_paths(url: str) -> tuple[Path, Path]:
    """(body file, sidecar file) for a URL. The body is stored gzip-compressed."""
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    d = cache_dir()
    return d / f"{key}.body.gz", d / f"{key}.meta.json"


def cache_info(url: str) -> dict | None:
    """Sidecar of a cached URL (url, retrieved_utc, status, bytes, sha256), or None."""
    _, meta = cache_paths(url)
    return json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else None


def _cache_write(url: str, body: bytes, status: int) -> None:
    body_path, meta_path = cache_paths(url)
    body_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = body_path.with_suffix(".tmp")
    with open(tmp, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(body)
    os.replace(tmp, body_path)
    meta = dict(url=url, retrieved_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                status=status, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8")


def _retry_after_seconds(headers) -> float | None:
    value = headers.get("Retry-After") if headers is not None else None
    if not value:
        return None
    try:
        return max(0.0, min(float(value), MAX_RETRY_AFTER_S))
    except ValueError:
        return None  # HTTP-date form: fall back to our own backoff


def _throttle(host: str) -> None:
    gap = MIN_INTERVAL_S.get(host, DEFAULT_MIN_INTERVAL_S)
    last = _last_request.get(host)
    if last is not None:
        wait = gap - (time.monotonic() - last)
        if wait > 0:
            _sleep(wait)
    _last_request[host] = time.monotonic()


def cache_age_s(url: str) -> float | None:
    """Seconds since a cached URL was retrieved (from its sidecar), or None if it is not cached."""
    info = cache_info(url)
    if not info or not cache_paths(url)[0].exists():
        return None
    try:
        got = datetime.strptime(info["retrieved_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        return math.inf          # unreadable sidecar: treat the copy as infinitely old
    return max(0.0, (datetime.now(timezone.utc) - got).total_seconds())


def http_get(url: str, *, max_age_s: float | None = None, retries: int | None = None,
             timeout_s: float | None = None) -> bytes:
    """GET a URL through the outbound gateway and return the response body.

    Order of checks: allowlist, cache, offline mode, network. Raises QuakeNetError with code
    HOST_NOT_ALLOWED, CACHE_MISS (offline and not cached) or FEED_UNAVAILABLE (network failed
    after all retries, or the server refused the request).

    Optional (the defaults keep the original behaviour):
      * max_age_s: a cached copy older than this many seconds is fetched again. If the fetch
        fails the error is raised (the caller may then read the stale copy with max_age_s=None).
        In offline mode the cached copy is served whatever its age, because offline mode never
        touches the network.
      * retries: retries after the first attempt (default RETRIES = 3).
      * timeout_s: per-attempt timeout (default TIMEOUT_S = 30 s).
    """
    host = _check_host(url)
    body_path, meta_path = cache_paths(url)
    if body_path.exists() and meta_path.exists():
        age = cache_age_s(url) if max_age_s is not None else None
        if max_age_s is None or is_offline() or (age is not None and age <= max_age_s):
            return gzip.decompress(body_path.read_bytes())
    if is_offline():
        raise QuakeNetError("CACHE_MISS", f"offline mode (QUAKENET_OFFLINE=1) and no cached copy of {url} "
                            f"in {cache_dir()}")

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    last_error = "no attempt made"
    n_retries = RETRIES if retries is None else max(0, int(retries))
    timeout = TIMEOUT_S if timeout_s is None else float(timeout_s)
    for attempt in range(n_retries + 1):
        wait = BACKOFF_BASE_S * 2 ** attempt + random.uniform(0.0, BACKOFF_BASE_S)
        _throttle(host)
        try:
            with _urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
                    body = gzip.decompress(body)
                status = int(getattr(resp, "status", 200) or 200)
            _cache_write(url, body, status)
            return body
        except urllib.error.HTTPError as err:
            last_error = f"HTTP {err.code}"
            if host in SLOW_DOWN_PAUSE_S and err.code in (429, 406):
                # Overpass usage policy: on 429 or 406, pause 30 s before trying again.
                wait = max(SLOW_DOWN_PAUSE_S[host], _retry_after_seconds(err.headers) or 0.0)
            elif err.code == 429 or err.code >= 500:
                wait = _retry_after_seconds(err.headers) or wait
            else:  # 4xx other than 429: the request itself is wrong, retrying cannot help
                raise QuakeNetError("FEED_UNAVAILABLE", f"{host} answered HTTP {err.code} for {url}") from err
        except (urllib.error.URLError, http.client.HTTPException, OSError) as err:
            last_error = f"{type(err).__name__}: {err}"
        if attempt < n_retries:
            _sleep(wait)
    raise QuakeNetError("FEED_UNAVAILABLE", f"{host} failed after {n_retries + 1} attempts ({last_error}): {url}")


# ------------------------------------------------------------------------ projection

class Projection:
    """Equirectangular projection about a centre: lat/lon <-> local km (x east, y north).

    Same formula as src/geometry.py::to_km, but the centre is a parameter. Accurate to well
    under 1% within about 150 km of the centre, which covers every study radius we use.
    """

    def __init__(self, lat0: float, lon0: float):
        self.lat0, self.lon0 = float(lat0), float(lon0)
        self._kx = math.cos(math.radians(self.lat0)) * KM_PER_DEG

    def to_km(self, lat, lon) -> np.ndarray:
        lat, lon = np.asarray(lat, float), np.asarray(lon, float)
        return np.stack([(lon - self.lon0) * self._kx, (lat - self.lat0) * KM_PER_DEG], axis=-1)

    def to_latlon(self, x, y) -> tuple[np.ndarray, np.ndarray]:
        x, y = np.asarray(x, float), np.asarray(y, float)
        return self.lat0 + y / KM_PER_DEG, self.lon0 + x / self._kx


def rupture_length_km(mag: float) -> float:
    """Subsurface rupture length, Wells & Coppersmith (1994), all slip types: log10 L = -2.44 + 0.59 M."""
    return 10.0 ** (-2.44 + 0.59 * mag)


def study_radius_km(mag: float) -> float:
    """Spec FR-3: R = max(50 km, 2 x rupture length)."""
    return max(50.0, 2.0 * rupture_length_km(mag))


# --------------------------------------------------------------------------- fetchers

USGS_EVENT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
IRIS_STATION_URL = "https://service.iris.edu/fdsnws/station/1/query"


def _as_utc(t) -> datetime:
    """Accept a datetime (naive means UTC) or an ISO 8601 string; return an aware UTC datetime."""
    if isinstance(t, str):
        t = datetime.fromisoformat(t.strip().replace("Z", "+00:00"))
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)


def _fmt_time(t) -> str:
    return _as_utc(t).strftime("%Y-%m-%dT%H:%M:%S")


def _event_row(feature: dict) -> dict:
    lon, lat, depth = feature["geometry"]["coordinates"][:3]
    p = feature["properties"]
    return dict(id=feature["id"], time_ms=p["time"], mag=p["mag"], lat=lat, lon=lon,
                depth_km=depth, place=p.get("place"))


def mainshock_url(usgs_event_id: str) -> str:
    return f"{USGS_EVENT_URL}?eventid={urllib.parse.quote(usgs_event_id, safe='')}&format=geojson"


def aftershocks_url(lat: float, lon: float, radius_km: float, start, end, min_mag: float = 2.5) -> str:
    return (f"{USGS_EVENT_URL}?format=geojson&eventtype=earthquake"
            f"&starttime={_fmt_time(start)}&endtime={_fmt_time(end)}"
            f"&latitude={lat:.4f}&longitude={lon:.4f}&maxradiuskm={radius_km:.1f}"
            f"&minmagnitude={min_mag:.1f}&orderby=time-asc")


def stations_url(lat: float, lon: float, radius_km: float, at_time) -> str:
    t0 = _as_utc(at_time)
    return (f"{IRIS_STATION_URL}?level=station&format=text"
            f"&latitude={lat:.4f}&longitude={lon:.4f}&maxradius={radius_km / KM_PER_DEG:.4f}"
            f"&starttime={_fmt_time(t0)}&endtime={_fmt_time(t0 + timedelta(days=TEMPORARY_WINDOW_DAYS))}")


def parse_events(body: bytes) -> list[dict]:
    """ComCat GeoJSON FeatureCollection -> rows {id, time_ms, mag, lat, lon, depth_km, place}.

    An empty body (HTTP 204, no events) gives an empty list. Events without a magnitude or a
    depth are dropped: they cannot be used for planning.
    """
    if not body.strip():
        return []
    rows = [_event_row(f) for f in json.loads(body)["features"]]
    return [r for r in rows if r["mag"] is not None and r["depth_km"] is not None]


def fetch_mainshock(usgs_event_id: str) -> dict:
    """One event from ComCat by its USGS id: {id, time_ms, mag, lat, lon, depth_km, place}."""
    feature = json.loads(http_get(mainshock_url(usgs_event_id)))
    return _event_row(feature)


def fetch_aftershocks(lat: float, lon: float, radius_km: float, start, end, min_mag: float = 2.5) -> list[dict]:
    """Earthquakes with magnitude >= min_mag within radius_km of (lat, lon), start <= time <= end.

    Sorted by time. The mainshock itself is returned too if it falls inside the window; filter
    on time_ms when only later events are wanted. ComCat returns at most 20,000 events a query.
    """
    return parse_events(http_get(aftershocks_url(lat, lon, radius_km, start, end, min_mag)))


def _parse_station_time(text: str) -> datetime | None:
    text = text.strip()
    return _as_utc(text) if text else None


def parse_stations(body: bytes, at_time) -> tuple[list[dict], list[dict]]:
    """FDSN station text (one row per station epoch) -> (permanent, temporary).

    permanent: first listed epoch starts at or before at_time (operating at the mainshock).
    temporary: first listed epoch starts after at_time and within 30 days of it.
    Rows: {net, sta, lat, lon, elev_m, name, start, end} with ISO 8601 UTC times (end may be None).
    """
    t0 = _as_utc(at_time)
    limit = t0 + timedelta(days=TEMPORARY_WINDOW_DAYS)
    merged: dict[tuple[str, str], dict] = {}
    for line in body.decode("utf-8", errors="replace").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 8 or cols[0] in EXCLUDED_NETWORKS:
            continue
        net, sta, lat, lon, elev, name, start, end = cols[:8]
        start_t, end_t = _parse_station_time(start), _parse_station_time(end)
        if start_t is None or (end_t is not None and end_t <= t0):
            continue
        row = merged.get((net, sta))
        if row is None:
            merged[(net, sta)] = dict(net=net, sta=sta, lat=float(lat), lon=float(lon),
                                      elev_m=float(elev) if elev else None, name=name,
                                      _start=start_t, _end=end_t)
        else:  # several epochs of one station: keep the earliest start and the latest end
            row["_start"] = min(row["_start"], start_t)
            row["_end"] = None if (row["_end"] is None or end_t is None) else max(row["_end"], end_t)
    permanent, temporary = [], []
    for row in merged.values():
        start_t, end_t = row.pop("_start"), row.pop("_end")
        row["start"] = start_t.isoformat()
        row["end"] = end_t.isoformat() if end_t else None
        if start_t <= t0:
            permanent.append(row)
        elif start_t <= limit:
            temporary.append(row)
    key = lambda r: (r["net"], r["sta"])
    return sorted(permanent, key=key), sorted(temporary, key=key)


def fetch_stations(lat: float, lon: float, radius_km: float, at_time) -> tuple[list[dict], list[dict]]:
    """Stations of all networks within radius_km of (lat, lon): (permanent, temporary).

    "Permanent" means operating at at_time (the mainshock); "temporary" means the station began
    within 30 days after it, which is how a rapid-response deployment shows up in the metadata.
    """
    return parse_stations(http_get(stations_url(lat, lon, radius_km, at_time)), at_time)


# ------------------------------------------------------------------------- benchmarks

# Verified against USGS ComCat on 2026-11-12 (preferred event id, origin time, hypocentre,
# magnitude). `aliases` are other ids ComCat lists for the same event.
BENCHMARKS: dict[str, dict] = {
    "ridgecrest2019": dict(name="Ridgecrest 2019", region="California", usgs_id="ci38457511",
                           aliases=("us70004bn0",), mag=7.1, time="2019-07-06T03:19:53.040Z",
                           lat=35.7695, lon=-117.5993, depth_km=8.0),
    "southnapa2014": dict(name="South Napa 2014", region="California", usgs_id="nc72282711",
                          aliases=("usb000s5tp",), mag=6.02, time="2014-08-24T10:20:44.070Z",
                          lat=38.2152, lon=-122.3123, depth_km=11.12),
    "montecristo2020": dict(name="Monte Cristo Range 2020", region="Nevada", usgs_id="nn00725272",
                            aliases=("us70009gj8",), mag=6.5, time="2020-05-15T11:03:27.176Z",
                            lat=38.1689, lon=-117.8497, depth_km=2.7),
    "anchorage2018": dict(name="Anchorage 2018", region="Alaska", usgs_id="ak018fcnsk91",
                          aliases=("ak20419010", "us1000hyfh"), mag=7.1, time="2018-11-30T17:29:29.330Z",
                          lat=61.3464, lon=-149.9552, depth_km=46.7),
    "ferndale2022": dict(name="Ferndale 2022", region="California", usgs_id="nc73821036",
                         aliases=("us6000jahm",), mag=6.4, time="2022-12-20T10:34:24.770Z",
                         lat=40.525, lon=-124.423, depth_km=17.91),
    "puertorico2020": dict(name="Puerto Rico 2020", region="Caribbean", usgs_id="pr2020007007",
                           aliases=("us70006vll",), mag=6.4, time="2020-01-07T08:24:27.370Z",
                           lat=17.9578, lon=-66.8113, depth_km=6.0),
}
