"""Offline checks of the outbound gateway, the USGS/IRIS fetchers and the projection.

Fixtures in tests/fixtures/cache are real responses (South Napa 2014, small radius) saved by
the gateway itself, so the fetchers run here exactly as in production but with no network.
"""
import email.message
import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from src import sources
from src.sources import (BENCHMARKS, Projection, QuakeNetError, fetch_aftershocks, fetch_mainshock,
                         fetch_stations, http_get, parse_events, parse_stations, study_radius_km)

FIXTURE_CACHE = Path(__file__).resolve().parent / "fixtures" / "cache"
NAPA = BENCHMARKS["southnapa2014"]
URL = "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&x=1"


class FakeResponse:
    def __init__(self, body=b"ok", status=200, headers=None):
        self._body, self.status, self.headers = body, status, headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code, headers=None):
    msg = email.message.Message()
    for k, v in (headers or {}).items():
        msg[k] = v
    return urllib.error.HTTPError("https://x", code, "err", msg, None)


@pytest.fixture
def net(monkeypatch, tmp_path):
    """Empty cache, online mode, a scripted network and a recorded (not real) sleep."""
    monkeypatch.setenv("QUAKENET_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("QUAKENET_OFFLINE", raising=False)
    monkeypatch.setattr(sources, "_throttle", lambda host: None)   # per-host gap is tested separately
    state = dict(calls=[], sleeps=[], script=[])

    def fake_urlopen(req, timeout):
        state["calls"].append((req, timeout))
        step = state["script"].pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    monkeypatch.setattr(sources, "_urlopen", fake_urlopen)
    monkeypatch.setattr(sources, "_sleep", state["sleeps"].append)
    return state


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setenv("QUAKENET_CACHE_DIR", str(FIXTURE_CACHE))
    monkeypatch.setenv("QUAKENET_OFFLINE", "1")
    monkeypatch.setattr(sources, "_urlopen", lambda *a, **k: pytest.fail("network used in offline test"))


# ----------------------------------------------------------------------------- gateway

@pytest.mark.parametrize("url", [
    "https://example.com/data",
    "http://earthquake.usgs.gov/fdsnws/event/1/query",       # plain http
    "https://earthquake.usgs.gov.evil.example/query",         # look-alike host
    "https://evil.example/?u=https://earthquake.usgs.gov/",
    "file:///etc/passwd",
])
def test_gateway_refuses_hosts_off_the_allowlist(net, url):
    with pytest.raises(QuakeNetError) as err:
        http_get(url)
    assert err.value.code == "HOST_NOT_ALLOWED"
    assert net["calls"] == []


def test_allowlist_is_exactly_the_documented_hosts():
    assert sources.ALLOWED_HOSTS == {"earthquake.usgs.gov", "service.iris.edu", "service.earthscope.org",
                                     "overpass-api.de", "s3.amazonaws.com"}


def test_redirects_are_followed_only_to_allowed_hosts():
    handler = sources._AllowlistRedirect()
    req = sources.urllib.request.Request("https://service.iris.edu/fdsnws/station/1/query?a=1")
    new = handler.redirect_request(req, None, 301, "Moved", {},
                                   "https://service.earthscope.org/fdsnws/station/1/query?a=1")
    assert new.full_url.startswith("https://service.earthscope.org/")
    with pytest.raises(QuakeNetError) as err:
        handler.redirect_request(req, None, 301, "Moved", {}, "https://evil.example/steal")
    assert err.value.code == "HOST_NOT_ALLOWED"


def test_success_is_cached_with_url_and_retrieval_time(net):
    net["script"] = [FakeResponse(b"hello")]
    assert http_get(URL) == b"hello"
    assert http_get(URL) == b"hello"          # second call: cache, no network
    assert len(net["calls"]) == 1
    req, timeout = net["calls"][0]
    assert timeout == 30.0
    agent = req.get_header("User-agent")
    assert agent.startswith("quakenet-q/") and "@" not in agent
    body_path, meta_path = sources.cache_paths(URL)
    assert body_path.name.startswith(sources.hashlib.sha256(URL.encode()).hexdigest())
    meta = json.loads(meta_path.read_text())
    assert meta["url"] == URL and meta["bytes"] == 5
    retrieved = datetime.strptime(meta["retrieved_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert abs((datetime.now(timezone.utc) - retrieved).total_seconds()) < 60
    assert sources.cache_info(URL) == meta


def test_gzip_responses_are_decoded(net):
    net["script"] = [FakeResponse(sources.gzip.compress(b"plain"), headers={"Content-Encoding": "gzip"})]
    assert http_get(URL) == b"plain"


def test_three_retries_with_growing_backoff_then_success(net):
    net["script"] = [TimeoutError("slow"), urllib.error.URLError("dns"), http_error(503), FakeResponse(b"late")]
    assert http_get(URL) == b"late"
    assert len(net["calls"]) == 4
    waits = net["sleeps"]
    assert len(waits) == 3
    for attempt, wait in enumerate(waits):                    # base * 2**attempt plus jitter in [0, base]
        assert 2 ** attempt <= wait <= 2 ** attempt + 1.0


def test_gives_up_after_four_attempts_and_caches_nothing(net):
    net["script"] = [TimeoutError("slow")] * 4
    with pytest.raises(QuakeNetError) as err:
        http_get(URL)
    assert err.value.code == "FEED_UNAVAILABLE" and "4 attempts" in err.value.message
    assert len(net["calls"]) == 4
    assert not sources.cache_paths(URL)[0].exists()


def test_429_honours_retry_after(net):
    net["script"] = [http_error(429, {"Retry-After": "7"}), FakeResponse(b"ok")]
    assert http_get(URL) == b"ok"
    assert net["sleeps"] == [7.0]


def test_overpass_pauses_30_seconds_on_429_and_406(net):
    url = "https://overpass-api.de/api/interpreter?data=x"
    net["script"] = [http_error(429), http_error(406), FakeResponse(b"{}")]
    assert http_get(url) == b"{}"
    assert net["sleeps"] == [30.0, 30.0]


def test_requests_to_one_host_are_spaced_out(monkeypatch):
    sleeps = []
    monkeypatch.setattr(sources, "_last_request", {})
    monkeypatch.setattr(sources, "_sleep", sleeps.append)
    sources._throttle("service.iris.edu")
    assert sleeps == []                                        # first request: no wait
    sources._throttle("service.iris.edu")
    assert len(sleeps) == 1 and 0.9 < sleeps[0] <= 1.0         # at most one request per second
    sources._throttle("earthquake.usgs.gov")
    assert len(sleeps) == 1                                    # another host has its own clock


def test_client_errors_are_not_retried(net):
    net["script"] = [http_error(400)]
    with pytest.raises(QuakeNetError) as err:
        http_get(URL)
    assert err.value.code == "FEED_UNAVAILABLE" and "400" in err.value.message
    assert len(net["calls"]) == 1


def test_offline_mode_raises_cache_miss_without_network(net, monkeypatch):
    monkeypatch.setenv("QUAKENET_OFFLINE", "1")
    with pytest.raises(QuakeNetError) as err:
        http_get(URL)
    assert err.value.code == "CACHE_MISS" and URL in err.value.message
    assert net["calls"] == []


def test_offline_mode_serves_cached_copies(net, monkeypatch):
    net["script"] = [FakeResponse(b"kept")]
    http_get(URL)
    monkeypatch.setenv("QUAKENET_OFFLINE", "1")
    assert http_get(URL) == b"kept"
    assert len(net["calls"]) == 1


# ---------------------------------------------------------------------------- fetchers

def test_fetch_mainshock_matches_the_registry(offline):
    m = fetch_mainshock(NAPA["usgs_id"])
    assert m["id"] == "nc72282711"
    assert m["mag"] == pytest.approx(NAPA["mag"], abs=0.01)
    assert m["lat"] == pytest.approx(NAPA["lat"], abs=1e-3) and m["lon"] == pytest.approx(NAPA["lon"], abs=1e-3)
    assert m["depth_km"] == pytest.approx(NAPA["depth_km"], abs=0.01)
    assert m["time_ms"] == int(sources._as_utc(NAPA["time"]).timestamp() * 1000)


def test_fetch_aftershocks_parses_sorted_events(offline):
    t0 = sources._as_utc(NAPA["time"])
    rows = fetch_aftershocks(NAPA["lat"], NAPA["lon"], 10, t0, "2014-08-26T10:20:44Z")
    assert len(rows) == 7 and rows[0]["id"] == "nc72282711"
    times = [r["time_ms"] for r in rows]
    assert times == sorted(times)
    proj = Projection(NAPA["lat"], NAPA["lon"])
    for r in rows:
        assert r["mag"] >= 2.5
        assert np.hypot(*proj.to_km(r["lat"], r["lon"])) <= 10.5
        assert set(r) >= {"id", "time_ms", "mag", "lat", "lon", "depth_km"}


def test_parse_events_handles_empty_and_incomplete_rows():
    assert parse_events(b"") == []

    def feature(mag, depth):
        return dict(id="a", properties=dict(time=1, mag=mag, place="p"),
                    geometry=dict(coordinates=[-120.0, 35.0, depth]))

    body = json.dumps(dict(features=[feature(3.0, 5.0), feature(None, 5.0), feature(3.0, None)])).encode()
    assert len(parse_events(body)) == 1


def test_fetch_stations_splits_permanent_and_temporary(offline):
    permanent, temporary = fetch_stations(NAPA["lat"], NAPA["lon"], 15, NAPA["time"])
    t0 = sources._as_utc(NAPA["time"])
    assert len(permanent) == 12 and len(temporary) == 199
    assert {"BK", "NC"} <= {s["net"] for s in permanent}
    assert all(datetime.fromisoformat(s["start"]) <= t0 for s in permanent)
    assert all(0 <= (datetime.fromisoformat(s["start"]) - t0).days <= 30 for s in temporary)
    assert all(datetime.fromisoformat(s["start"]) > t0 for s in temporary)
    keys = [(s["net"], s["sta"]) for s in permanent + temporary]
    assert len(keys) == len(set(keys))


def test_parse_stations_rules():
    body = b"""#Network | Station | Latitude | Longitude | Elevation | SiteName | StartTime | EndTime
CI|OLD|35.0|-117.0|900.0|Running since 1999|1999-01-01T00:00:00|
CI|TWO|35.1|-117.1|900.0|Two epochs, first one before|2010-01-01T00:00:00|2019-07-10T00:00:00
CI|TWO|35.1|-117.1|900.0|Two epochs, first one before|2019-07-10T00:00:00|
GS|TMP|35.2|-117.2|800.0|Installed four days later|2019-07-10T03:00:00.0000|2019-09-01T00:00:00
ZZ|LATE|35.3|-117.3|800.0|Starts 40 days later|2019-08-15T00:00:00|
CI|GONE|35.4|-117.4|800.0|Closed before the mainshock|2001-01-01T00:00:00|2015-01-01T00:00:00
SY|FAKE|35.5|-117.5|0.0|Synthetic network|1990-01-01T00:00:00|
"""
    permanent, temporary = parse_stations(body, "2019-07-06T03:19:53Z")
    assert [s["sta"] for s in permanent] == ["OLD", "TWO"]
    assert [s["sta"] for s in temporary] == ["TMP"]
    assert permanent[1]["start"].startswith("2010-01-01") and permanent[1]["end"] is None
    assert temporary[0]["lat"] == 35.2 and temporary[0]["elev_m"] == 800.0
    assert parse_stations(b"", "2019-07-06T03:19:53Z") == ([], [])


def test_urls_are_deterministic():
    a = sources.stations_url(35.7695, -117.5993, 50, "2019-07-06T03:19:53.040Z")
    b = sources.stations_url(35.7695, -117.5993, 50.0, datetime(2019, 7, 6, 3, 19, 53, 40000))
    assert a == b and "starttime=2019-07-06T03:19:53&endtime=2019-08-05T03:19:53" in a
    assert "level=station" in a and "format=text" in a and "network=" not in a


# ----------------------------------------------------------------- projection, registry

def test_projection_round_trip_and_scale():
    proj = Projection(61.3464, -149.9552)
    rng = np.random.default_rng(0)
    lat = 61.3464 + rng.uniform(-1, 1, 200)
    lon = -149.9552 + rng.uniform(-2, 2, 200)
    xy = proj.to_km(lat, lon)
    lat2, lon2 = proj.to_latlon(xy[:, 0], xy[:, 1])
    assert np.allclose(lat, lat2, atol=1e-10) and np.allclose(lon, lon2, atol=1e-10)
    assert np.allclose(proj.to_km(61.3464, -149.9552), [0, 0])
    east, north = proj.to_km(61.3464, -148.9552), proj.to_km(62.3464, -149.9552)
    assert north == pytest.approx([0, 111.19]) and east[0] == pytest.approx(111.19 * np.cos(np.radians(61.3464)))


def test_projection_matches_existing_geometry_module():
    from src import geometry
    proj = Projection(geometry.LAT0, geometry.LON0)
    assert np.allclose(proj.to_km([35.5, 36.0], [-117.8, -117.3]), geometry.to_km([35.5, 36.0], [-117.8, -117.3]))


def test_study_radius():
    assert study_radius_km(6.0) == 50.0
    assert study_radius_km(7.1) == pytest.approx(2 * 10 ** (-2.44 + 0.59 * 7.1))


def test_benchmark_registry():
    assert set(BENCHMARKS) == {"ridgecrest2019", "southnapa2014", "montecristo2020", "anchorage2018",
                               "ferndale2022", "puertorico2020"}
    assert BENCHMARKS["ridgecrest2019"]["usgs_id"] == "ci38457511"
    for b in BENCHMARKS.values():
        assert 5.9 < b["mag"] < 7.2 and -90 < b["lat"] < 90 and -180 < b["lon"] < 0
        assert sources._as_utc(b["time"]).year in range(2014, 2023)
