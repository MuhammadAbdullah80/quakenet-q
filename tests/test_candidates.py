"""Offline checks of the candidate pool: grid, roads, terrain, every filter, selection, backups."""
import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src import candidates, sources
from src.candidates import (apply_filters, bounding_box, build_candidate_pool, decode_terrarium, make_grid,
                            parse_overpass, road_distance_km, select_candidates, slope_degrees, tile_pixel,
                            zoom_for_lat)
from src.sources import BENCHMARKS, QuakeNetError, fetch_stations

FIXTURE_CACHE = Path(__file__).resolve().parent / "fixtures" / "cache"
NAPA = BENCHMARKS["southnapa2014"]


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setenv("QUAKENET_CACHE_DIR", str(FIXTURE_CACHE))
    monkeypatch.setenv("QUAKENET_OFFLINE", "1")
    monkeypatch.setattr(sources, "_urlopen", lambda *a, **k: pytest.fail("network used in offline test"))


def terrarium_png(elev: np.ndarray) -> bytes:
    v = np.round((np.asarray(elev, float) + 32768.0) * 256.0).astype(np.int64)
    rgb = np.stack([v // 65536, (v // 256) % 256, v % 256], axis=-1).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "PNG")
    return buf.getvalue()


# -------------------------------------------------------------------------------- grid

def test_grid_is_2km_inside_the_radius():
    g = make_grid(10.0)
    assert np.all(np.hypot(g[:, 0], g[:, 1]) <= 10.0)
    assert np.allclose(g % 2.0, 0) and len(np.unique(g, axis=0)) == len(g)
    assert [0.0, 0.0] in g.tolist() and [10.0, 0.0] in g.tolist() and [8.0, 8.0] not in g.tolist()
    assert len(g) == 81                         # lattice points with i^2 + j^2 <= 25
    assert abs(len(make_grid(50.0)) - np.pi * 50 ** 2 / 4) < 40


def test_bounding_box_contains_the_circle():
    s, w, n, e = bounding_box(61.0, -150.0, 50.0)
    assert n - 61.0 == pytest.approx(50 / 111.19) and 61.0 - s == pytest.approx(50 / 111.19)
    assert e - -150.0 == pytest.approx(50 / (111.19 * np.cos(np.radians(61.0))))


# ----------------------------------------------------------------------------- terrain

def test_terrarium_decoding_known_pixels():
    px = np.array([[[128, 0, 0], [128, 100, 128]], [[127, 255, 0], [134, 112, 64]]], np.uint8)
    buf = io.BytesIO()
    Image.fromarray(px).save(buf, "PNG")
    assert decode_terrarium(buf.getvalue()).tolist() == [[0.0, 100.5], [-1.0, 1648.25]]


def test_terrarium_round_trip_and_real_tile(offline):
    elev = np.linspace(-500.0, 4000.0, 256 * 256).reshape(256, 256)
    assert np.allclose(decode_terrarium(terrarium_png(elev)), elev, atol=1 / 256)
    tile = decode_terrarium(sources.http_get(candidates.TILE_URL.format(z=10, x=164, y=394)))
    assert tile.shape == (256, 256)
    assert 0 < np.median(tile) < 100 and 300 < tile.max() < 1500   # Napa valley floor to nearby hills
    assert 0.1 < (tile <= 0).mean() < 0.4                          # San Pablo Bay and tidal marsh


def test_tile_addressing():
    tx, ty, col, row = tile_pixel([38.2152, 0.0], [-122.3123, 0.0], 10)
    assert (tx[0], ty[0]) == (164, 394) and (tx[1], ty[1], col[1], row[1]) == (512, 512, 0, 0)
    assert zoom_for_lat(35.8) == 10 and zoom_for_lat(61.3) == 9 and zoom_for_lat(18.0) == 10
    assert candidates.pixel_size_m(61.3, zoom_for_lat(61.3)) <= 150 < candidates.pixel_size_m(61.3, 8)


def test_slope_of_a_tilted_plane():
    x = np.arange(64) * 100.0
    plane = np.tile(x * np.tan(np.radians(30.0)), (64, 1))
    assert np.allclose(slope_degrees(plane, 100.0), 30.0)
    assert np.allclose(slope_degrees(plane.T, 100.0), 30.0)
    assert np.allclose(slope_degrees(np.full((8, 8), 250.0), 100.0), 0.0)


def test_sample_terrain_reads_the_right_pixel(monkeypatch):
    elev = np.zeros((256, 256))
    elev[10, 20] = 777.0
    served = []
    monkeypatch.setattr(candidates, "http_get", lambda url: served.append(url) or terrarium_png(elev))
    n = 2 ** 10
    lon = (164 + 20.5 / 256) / n * 360.0 - 180.0
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * (394 + 10.5 / 256) / n))))
    e, s = candidates.sample_terrain([lat, lat], [lon, lon + 0.01], zoom=10)
    assert e.tolist() == [777.0, 0.0] and s[0] == 0.0 and s[1] == 0.0
    assert served == [candidates.TILE_URL.format(z=10, x=164, y=394)]       # one tile, fetched once


# ------------------------------------------------------------------------------- roads

def test_overpass_url_and_parsing():
    url = candidates.overpass_url((38.0, -122.5, 38.4, -122.1))
    assert url.startswith("https://overpass-api.de/api/interpreter?data=")
    query = candidates.urllib.parse.unquote(url.split("data=")[1])
    assert 'way["highway"' in query and "(38.0000,-122.5000,38.4000,-122.1000)" in query and "out geom" in query
    body = json.dumps(dict(elements=[
        dict(type="way", id=1, geometry=[dict(lat=38.0, lon=-122.0), dict(lat=38.1, lon=-122.0)]),
        dict(type="way", id=2, geometry=[]),
        dict(type="node", id=3, lat=38.0, lon=-122.0)])).encode()
    roads = parse_overpass(body)
    assert len(roads) == 1 and roads[0].tolist() == [[38.0, -122.0], [38.1, -122.0]]
    with pytest.raises(QuakeNetError):
        parse_overpass(json.dumps(dict(elements=[], remark="runtime error: Query timed out")).encode())


def test_road_distance_uses_the_line_not_only_its_ends():
    road = np.array([[-20.0, 0.0], [20.0, 0.0]])                 # one 40 km segment, two vertices
    pts = np.array([[0.0, 1.0], [3.3, -1.49], [0.0, 1.6], [23.0, 4.0]])
    d = road_distance_km(pts, [road])
    assert np.allclose(d, [1.0, 1.49, 1.6, 5.0], atol=0.01)
    assert np.all(np.isinf(road_distance_km(pts, [])))


# ----------------------------------------------------------------------------- filters

XY = np.array([[0.0, 0.0], [2.0, 0.0], [4.0, 0.0], [6.0, 0.0], [8.0, 0.0]])


def test_filter_land_keeps_only_points_above_sea_level():
    keep, funnel = apply_filters(XY, elevation_m=[-3.0, 0.0, 0.5, 120.0, -40.0])
    assert keep.tolist() == [False, False, True, True, False] and funnel == {"grid": 5, "on_land": 2}


def test_filter_slope_under_20_degrees():
    keep, _ = apply_filters(XY, slope_deg=[0.0, 19.9, 20.0, 35.0, 5.0])
    assert keep.tolist() == [True, True, False, False, True]


def test_filter_within_1500_m_of_a_road():
    keep, _ = apply_filters(XY, road_km=[0.0, 1.5, 1.51, np.inf, 0.7])
    assert keep.tolist() == [True, True, False, False, True]


def test_filter_6_km_from_every_permanent_station():
    keep, _ = apply_filters(XY, stations_xy=[[0.0, 5.0], [100.0, 100.0]])
    assert keep.tolist() == [False, False, True, True, True]       # distances 5.0, 5.39, 6.40, 7.81, 9.43
    assert apply_filters(XY, stations_xy=[[2.0, 6.0]])[0].tolist() == [True, True, True, True, True]
    assert apply_filters(XY, stations_xy=np.empty((0, 2)))[0].all()


def test_filter_3_km_from_rupture_points():
    keep, _ = apply_filters(XY, rupture_xy=[[3.0, 0.0], [8.0, 2.9]])
    assert keep.tolist() == [True, False, False, True, False]


def test_filters_combine_and_report_a_funnel():
    keep, funnel = apply_filters(XY, elevation_m=[5, 5, 5, 5, -1], slope_deg=[1, 1, 1, 30, 1],
                                 road_km=[0.1, 0.1, 9.0, 0.1, 0.1], stations_xy=[[-5.0, 0.0]],
                                 rupture_xy=[[50.0, 50.0]])
    assert keep.tolist() == [False, True, False, False, False]
    assert funnel == {"grid": 5, "on_land": 4, "slope": 3, "near_road": 2, "station_gap": 1, "rupture_gap": 1}


# -------------------------------------------------------------------------- pool (real)

def napa_pool(**kw):
    permanent, _ = fetch_stations(NAPA["lat"], NAPA["lon"], 15, NAPA["time"])
    return permanent, build_candidate_pool(NAPA["lat"], NAPA["lon"], 6, permanent,
                                           [(NAPA["lat"], NAPA["lon"])], station_gap_km=2.0, **kw)


def test_pool_from_cached_real_data(offline):
    permanent, pool = napa_pool()
    assert pool.feasibility_checked and pool.roads_checked and pool.terrain_checked and pool.warnings == ()
    assert pool.funnel == {"grid": 29, "on_land": 20, "slope": 20, "near_road": 17, "station_gap": 15,
                           "rupture_gap": 11}
    assert len(pool) == 11 == len(pool.lat) == len(pool.road_km)
    assert np.all(pool.elevation_m > 0) and np.all(pool.slope_deg < 20) and np.all(pool.road_km <= 1.5)
    proj = sources.Projection(NAPA["lat"], NAPA["lon"])
    assert np.allclose(proj.to_km(pool.lat, pool.lon), pool.xy)
    assert np.all(np.hypot(pool.xy[:, 0], pool.xy[:, 1]) >= 3.0)
    st = proj.to_km([s["lat"] for s in permanent], [s["lon"] for s in permanent])
    assert np.linalg.norm(pool.xy[:, None] - st[None], axis=2).min() >= 2.0


def test_pool_falls_back_to_grid_and_terrain_when_overpass_fails(offline, monkeypatch):
    def down(bbox):
        raise QuakeNetError("FEED_UNAVAILABLE", "overpass-api.de failed after 4 attempts")
    monkeypatch.setattr(candidates, "fetch_roads", down)
    _, pool = napa_pool()
    assert pool.feasibility_checked is False and pool.roads_checked is False and pool.terrain_checked
    assert "near_road" not in pool.funnel and pool.funnel["rupture_gap"] == len(pool) == 13
    assert np.all(np.isnan(pool.road_km)) and np.all(pool.elevation_m > 0)
    assert len(pool.warnings) == 1 and "Overpass" in pool.warnings[0]


def test_pool_offline_cache_miss_is_flagged_not_fatal(monkeypatch, tmp_path):
    monkeypatch.setenv("QUAKENET_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("QUAKENET_OFFLINE", "1")
    pool = build_candidate_pool(10.0, 10.0, 4.0)
    assert not pool.feasibility_checked and not pool.terrain_checked and len(pool.warnings) == 2
    assert len(pool) == pool.funnel["grid"] == 13 and "CACHE_MISS" in pool.warnings[0]


# --------------------------------------------------------------------------- selection

def test_selection_is_greedy_by_gain_with_4_km_spacing():
    xy = make_grid(12.0)
    gains = -np.hypot(xy[:, 0] - 1.0, xy[:, 1] - 0.5)             # best near (1, 0.5)
    sel = select_candidates(xy, gains, n=10)
    idx = list(sel.indices)
    assert len(idx) == 10 and len(set(idx)) == 10
    assert idx[0] == int(np.argmax(gains))
    d = np.linalg.norm(xy[idx][:, None] - xy[idx][None], axis=2)
    assert d[np.triu_indices(10, 1)].min() >= 4.0
    for pos, i in enumerate(idx):                                 # greedy: nothing better was skipped
        for j in np.flatnonzero(gains > gains[i]):
            assert j in idx[:pos] or np.linalg.norm(xy[idx[:pos]] - xy[j], axis=1).min() < 4.0


def test_backups_are_close_unselected_and_not_shared():
    xy = make_grid(12.0)
    gains = np.cos(xy[:, 0]) + np.sin(xy[:, 1] / 3.0)
    sel = select_candidates(xy, gains)
    assert len(sel.backups) == len(sel.indices) == 10
    flat = [j for b in sel.backups for j in b]
    assert len(flat) == len(set(flat)) and not set(flat) & set(sel.indices)
    for i, b in zip(sel.indices, sel.backups):
        assert 1 <= len(b) <= 3
        d = np.linalg.norm(xy[list(b)] - xy[i], axis=1)
        assert np.all(d <= 3.0) and np.all(np.diff(d) >= 0)


def test_selection_returns_fewer_when_the_pool_is_small():
    xy = np.array([[0.0, 0.0], [1.0, 0.0], [5.0, 0.0], [5.0, 2.5], [30.0, 0.0]])
    sel = select_candidates(xy, [1.0, 5.0, 3.0, 2.0, np.nan], n=10)
    assert sel.indices == (1, 2)                # 0 and 3 are within 4 km of a better point; 4 has no gain
    assert sel.backups == ((0,), (3,))
    assert select_candidates(np.empty((0, 2)), []).indices == ()
    with pytest.raises(ValueError):
        select_candidates(xy, [1.0, 2.0])


def test_selection_accepts_a_pool_object(offline):
    _, pool = napa_pool()
    sel = select_candidates(pool, -np.hypot(pool.xy[:, 0], pool.xy[:, 1]), n=3)
    assert len(sel) == 3 and all(0 <= i < len(pool) for i in sel.indices)
