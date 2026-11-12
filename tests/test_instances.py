"""Offline checks of src/instances.py: registry, loading, synthetic aftershocks, site selection."""
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from src import geometry, instances, sources
from src.instances import (EventData, event_from_usgs, list_events, load_event_data, make_instance,
                           planning_events, select_sites, synthetic_aftershocks)
from src.sources import QuakeNetError

FIXTURE_CACHE = Path(__file__).resolve().parent / "fixtures" / "cache"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    """Private events file, empty memo, offline; network use fails the test."""
    monkeypatch.setenv("QUAKENET_EVENTS_FILE", str(tmp_path / "events.json"))
    monkeypatch.setenv("QUAKENET_OFFLINE", "1")
    monkeypatch.setattr(sources, "_urlopen", lambda *a, **k: pytest.fail("network used in offline test"))
    instances.clear_memo()
    yield
    instances.clear_memo()


def fake_event(event_id="testquake", n_real=40, hours_max=24.0, pool_n=12, seed=0) -> EventData:
    rng = np.random.default_rng(seed)
    hours = np.sort(rng.uniform(0.1, hours_max, n_real))
    x = rng.uniform(-10, 10, n_real)
    after = np.column_stack([x, 0.5 * x + rng.normal(0, 1, n_real), rng.uniform(3, 12, n_real),
                             rng.uniform(2.5, 4.5, n_real), hours])
    st = np.array([[-30.0, -30.0], [30.0, -30.0], [30.0, 30.0], [-30.0, 30.0], [0.0, 40.0]])
    gx, gy = np.meshgrid(np.arange(-20, 21, 2.0), np.arange(-20, 21, 2.0))
    pool = np.column_stack([gx.ravel(), gy.ravel()])[:: max(1, 441 // (pool_n * 10))]
    return EventData(event_id=event_id, usgs_id="xx000", name="Test", magnitude=6.5,
                     time_utc=datetime(2020, 1, 1, tzinfo=timezone.utc), lat=38.0, lon=-118.0, depth_km=8.0,
                     lat0=38.0, lon0=-118.0, aftershocks=after, stations=st,
                     station_names=tuple(f"N.S{i}" for i in range(len(st))), pool=pool,
                     feasibility_checked=True, radius_km=50.0)


# ------------------------------------------------------------------ registry

def test_registry_lists_the_six_benchmarks():
    ev = list_events()
    assert [e["id"] for e in ev] == list(sources.BENCHMARKS)
    assert {e["kind"] for e in ev} == {"benchmark"}
    for e in ev:
        assert set(e) == {"id", "usgs_id", "name", "magnitude", "time_utc", "lat", "lon", "kind", "cached"}
        assert e["time_utc"].endswith("Z") and isinstance(e["cached"], bool)


def test_unknown_event_is_not_found():
    with pytest.raises(QuakeNetError) as err:
        load_event_data("atlantis1755")
    assert err.value.code == "NOT_FOUND"


def test_live_event_is_registered_and_persisted(monkeypatch, tmp_path):
    main = dict(id="us7000test", time_ms=1700000000000, mag=6.7, lat=-20.0, lon=-70.0, depth_km=30.0,
                place="Offshore Test")
    monkeypatch.setattr(sources, "fetch_mainshock", lambda uid: dict(main))
    built = fake_event("us7000test")
    calls = []

    def fake_build(event_id, entry, **kw):
        calls.append((event_id, entry, kw))
        return built
    monkeypatch.setattr(instances, "_build_event_data", fake_build)
    data = event_from_usgs("us7000test", station_radius_km=80)
    assert data is built and calls[0][2]["roads_online"] is True
    assert calls[0][1]["station_radius_km"] == 80 and calls[0][1]["kind"] == "live"
    saved = Path(tmp_path / "events.json").read_text()
    assert "us7000test" in saved
    instances.clear_memo()                                  # as after a restart
    live = [e for e in list_events() if e["kind"] == "live"]
    assert len(live) == 1 and live[0]["id"] == "us7000test" and live[0]["magnitude"] == 6.7
    assert load_event_data("us7000test") is built


def test_live_event_without_stations_is_refused_and_not_registered(monkeypatch):
    monkeypatch.setattr(sources, "fetch_mainshock", lambda uid: dict(
        id=uid, time_ms=1700000000000, mag=6.7, lat=-20.0, lon=-70.0, depth_km=30.0, place="Nowhere"))

    def no_stations(*a, **k):
        raise QuakeNetError("NO_STATIONS", "no permanent station within 100 km")
    monkeypatch.setattr(instances, "_build_event_data", no_stations)
    with pytest.raises(QuakeNetError) as err:
        event_from_usgs("us7000none")
    assert err.value.code == "NO_STATIONS"
    assert all(e["kind"] == "benchmark" for e in list_events())


@pytest.mark.parametrize("bad", ["", "a", "../etc/passwd", "x" * 41, "id with space"])
def test_live_event_id_is_validated(bad):
    with pytest.raises(QuakeNetError) as err:
        event_from_usgs(bad)
    assert err.value.code == "INVALID_INPUT"


def test_load_from_cached_fixture(monkeypatch):
    """South Napa fixture (small radii): the full loading path with no network."""
    monkeypatch.setenv("QUAKENET_CACHE_DIR", str(FIXTURE_CACHE))
    entry = instances._registry()["southnapa2014"]
    data = instances._build_event_data("southnapa2014", entry, radius_km=10.0, station_radius_km=15.0,
                                       pool_radius_km=6.0, days=2)
    assert data.lat0 == pytest.approx(data.lat) and data.lon0 == pytest.approx(data.lon)
    a = data.aftershocks
    assert a.shape[1] == 5 and np.all(np.diff(a[:, 4]) >= 0) and np.all(a[:, 3] >= 2.5)
    assert np.all((a[:, 4] > 0) & (a[:, 4] <= 48))
    assert len(data.stations) == len(data.station_names) > 0 and data.station_names[0].count(".") == 1
    assert data.feasibility_checked and len(data.pool) > 0
    lat, lon = data.to_latlon(*data.pool[0])
    assert isinstance(lat, float) and np.allclose(data.to_km(lat, lon), data.pool[0])


def test_ridgecrest_grid_stays_on_the_published_centre():
    entry = instances._registry()["ridgecrest2019"]
    # only the projection centre is checked here; the downloads come from the fixture of another event
    assert instances.RIDGECREST == "ridgecrest2019" and entry["usgs_id"] == "ci38457511"
    ev = fake_event("ridgecrest2019")
    cands, backups = select_sites(ev, ev.aftershocks, n=10)
    assert np.array_equal(cands, geometry.load_instance().candidates)
    assert len(backups) == 10


# ------------------------------------------------------------------ synthetic aftershocks

def test_synthetic_aftershocks_follow_the_stated_rules():
    s = synthetic_aftershocks(7.0, 8.0, n=500, seed=1, strike_deg=30.0)
    assert s.shape == (500, 5) and np.all(s[:, 4] == 0)
    assert np.all((s[:, 2] >= 1.0) & (s[:, 2] <= 20.0))
    assert np.all((s[:, 3] >= 2.5) & (s[:, 3] <= 6.0))
    # Gutenberg-Richter b = 1: about ten times fewer events per magnitude unit
    assert 5 < (s[:, 3] < 3.5).sum() / max((s[:, 3] >= 3.5).sum(), 1) < 20
    length = sources.rupture_length_km(7.0)
    along = s[:, 0] * np.sin(np.radians(30)) + s[:, 1] * np.cos(np.radians(30))
    across = s[:, 0] * np.cos(np.radians(30)) - s[:, 1] * np.sin(np.radians(30))
    assert np.abs(along).max() <= length / 2 + 1e-9 and np.abs(along).max() > 0.4 * length
    assert 1.5 < across.std() < 2.5
    assert instances._strike_of(s[:, :2]) == pytest.approx(30.0, abs=3.0)


def test_synthetic_aftershocks_are_deterministic():
    a = synthetic_aftershocks(6.5, 5.0, seed=4)
    assert np.array_equal(a, synthetic_aftershocks(6.5, 5.0, seed=4))
    assert not np.array_equal(a, synthetic_aftershocks(6.5, 5.0, seed=5))
    assert a.shape == (200, 5)


# ------------------------------------------------------------------ planning events

def test_planning_uses_real_events_when_enough():
    ev = fake_event(n_real=80, hours_max=24.0)
    events, synthetic = planning_events(ev, 12.0, min_real=30)
    assert not synthetic and np.all(events[:, 4] <= 12.0)
    assert len(events) == (ev.aftershocks[:, 4] <= 12.0).sum() >= 30


def test_planning_tops_up_with_synthetic_events():
    ev = fake_event(n_real=10, hours_max=24.0)
    events, synthetic = planning_events(ev, 12.0, min_real=30, seed=2)
    real = ev.aftershocks[ev.aftershocks[:, 4] <= 12.0]
    assert synthetic and len(events) == 200
    assert (events[:, 4] > 0).sum() == len(real)                 # synthetic events sit at hour 0
    again, _ = planning_events(ev, 12.0, min_real=30, seed=2)
    assert np.array_equal(events, again)
    assert np.abs(events[:, :2].mean(axis=0) - ev.epicentre_km).max() < 10


# ------------------------------------------------------------------ sites and instance

def test_select_sites_spreads_candidates_and_gives_backups():
    ev = fake_event()
    cands, backups = select_sites(ev, ev.aftershocks, n=6, min_spacing_km=4.0)
    assert cands.shape == (6, 2)
    d = np.linalg.norm(cands[:, None] - cands[None], axis=2)
    assert d[np.triu_indices(6, 1)].min() >= 4.0
    seen = set()
    for c, b in zip(cands, backups):
        assert len(b) <= 3
        for lat, lon in b:
            xy = ev.to_km(lat, lon)
            assert np.hypot(*(xy - c)) <= 3.0 + 1e-6
            assert (round(lat, 6), round(lon, 6)) not in seen
            seen.add((round(lat, 6), round(lon, 6)))


def test_make_instance_recomputes_risk_and_keeps_magnitudes():
    ev = fake_event(n_real=60)
    events, _ = planning_events(ev, 12.0)
    cands, _ = select_sites(ev, events, n=5)
    inst = make_instance(ev, cands, events, k=3)
    assert inst.n == 5 and inst.k == 3 and len(inst.design) == len(events)
    assert np.array_equal(inst.design_mag, events[:, 3])
    assert len(inst.valid) == (ev.aftershocks[:, 4] > events[:, 4].max()).sum()
    assert len(inst.valid_mag) == len(inst.valid)
    d = np.linalg.norm(cands[:, None] - events[None, :, :2], axis=2).min(axis=1)
    assert np.allclose(inst.risk, np.exp(-d / 5.0))
    sc = geometry.Scorer(inst, inst.design, hearing=True)          # magnitudes come from the instance
    assert np.isfinite(sc.d_score([0, 1, 2]))


def test_make_instance_with_explicit_validation_set():
    ev = fake_event(n_real=60)
    events, _ = planning_events(ev, 12.0)
    cands, _ = select_sites(ev, events, n=5)
    later = ev.aftershocks[ev.aftershocks[:, 4] > 20]
    inst = make_instance(ev, cands, events, valid=later[:, :3])
    assert len(inst.valid) == len(later) and inst.valid_mag is None
