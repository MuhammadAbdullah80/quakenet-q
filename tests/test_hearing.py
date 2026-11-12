"""Hearing range, velocity ensemble and the unchanged defaults of Scorer / location_errors."""
import json
from pathlib import Path

import numpy as np
import pytest

from src import geometry
from src.geometry import Instance, Scorer, load_instance, pick_sigma, snr, wa_amplitude_mm
from src.location import location_errors

ROOT = Path(__file__).resolve().parent.parent
PUBLISHED = json.loads((ROOT / "results" / "results.json").read_text())
LAM = 150.0


@pytest.fixture(scope="module")
def ridgecrest():
    return load_instance()


def tiny(mags=(3.0, 3.0)):
    """Four permanent stations on a 20 km square, two candidates, two shallow events."""
    stations = np.array([[-10.0, -10.0], [10.0, -10.0], [10.0, 10.0], [-10.0, 10.0]])
    cands = np.array([[0.0, 2.0], [60.0, 0.0]])
    events = np.array([[0.0, 0.0, 5.0], [1.0, -1.0, 6.0]])
    return Instance(events, events.copy(), stations, ("A", "B", "C", "D"), cands, np.zeros(2),
                    np.array([0.0, 0.0, 5.0]), k=1, design_mag=np.array(mags), valid_mag=np.array(mags))


# ------------------------------------------------------------------ defaults must not move

def test_instance_still_builds_positionally_and_has_no_magnitudes(ridgecrest):
    assert ridgecrest.design_mag is None and ridgecrest.valid_mag is None


def test_default_scorer_reproduces_the_published_results(ridgecrest):
    exact = PUBLISHED["methods"]["Exact (brute force)"]
    design, valid = Scorer(ridgecrest, ridgecrest.design), Scorer(ridgecrest, ridgecrest.valid)
    sel = exact["sites"]
    obj = design.d_score(sel) - LAM * float(ridgecrest.risk[sel].sum()) - design.d_score([])
    assert obj == exact["objective"]
    assert valid.blur_km(sel) == exact["blur_valid_km"]


def test_default_location_errors_reproduce_the_published_results(ridgecrest):
    exact = PUBLISHED["methods"]["Exact (brute force)"]
    err = location_errors(ridgecrest, tuple(exact["sites"]), ridgecrest.valid, trials=3)
    assert float(err.mean()) == exact["loc_error_mean_km"]


# ------------------------------------------------------------------ the attenuation law

def test_amplitude_matches_the_ml_definition():
    # Local magnitude scale: an M 3.0 event at 100 km gives 1 mm on a Wood-Anderson instrument.
    assert wa_amplitude_mm(3.0, 100.0) == pytest.approx(1.0)
    assert wa_amplitude_mm(4.0, 100.0) == pytest.approx(10.0)
    assert wa_amplitude_mm(3.0, 50.0) > wa_amplitude_mm(3.0, 100.0) > wa_amplitude_mm(3.0, 200.0)


def test_small_events_are_not_heard_far_away():
    assert snr(2.5, 10.0) > geometry.MIN_SNR > snr(2.5, 150.0)
    assert snr(4.0, 150.0) > geometry.MIN_SNR


def test_pick_error_grows_as_snr_falls_and_is_infinite_below_5():
    s = pick_sigma(np.array([100.0, geometry.SNR_GOOD, 7.0, 4.9]))
    assert s[0] == s[1] == geometry.SIGMA_T
    assert geometry.SIGMA_T < s[2] < np.inf and s[3] == np.inf


# ------------------------------------------------------------------ Scorer with hearing range

def test_hearing_drops_a_station_that_cannot_hear_the_event():
    inst = tiny(mags=(2.5, 2.5))
    sc = Scorer(inst, inst.design, hearing=True)
    assert sc.d_score([1]) == pytest.approx(sc.d_score([]))          # 60 km away: not heard
    assert sc.d_score([0]) > sc.d_score([])                           # 2 km away: heard


def test_hearing_with_big_events_counts_every_station():
    inst = tiny(mags=(6.0, 6.0))
    sc = Scorer(inst, inst.design, hearing=True)
    assert sc.d_score([1]) > sc.d_score([]) + 1e-6


def test_hearing_takes_magnitudes_from_the_instance_or_the_events():
    inst = tiny(mags=(2.5, 2.5))
    a = Scorer(inst, inst.design, hearing=True).d_score([0])
    b = Scorer(inst, inst.design, mags=[2.5, 2.5], hearing=True).d_score([0])
    c = Scorer(inst, np.column_stack([inst.design, [2.5, 2.5], [0, 0]]), hearing=True).d_score([0])
    assert a == pytest.approx(b) == pytest.approx(c)
    plain = Instance(*[getattr(inst, f) for f in ("design", "valid", "stations", "station_names",
                                                    "candidates", "risk", "mainshock")])
    with pytest.raises(ValueError):
        Scorer(plain, plain.design, hearing=True)


def test_hearing_scores_stay_finite_when_few_stations_hear(ridgecrest):
    mags = np.full(len(ridgecrest.design), 2.5)
    sc = Scorer(ridgecrest, ridgecrest.design, mags=mags, hearing=True)
    assert np.isfinite(sc.d_score([])) and np.isfinite(sc.blur_km([0, 1, 2, 3]))
    assert sc.d_score([0, 1, 2, 3]) > sc.d_score([])


# ------------------------------------------------------------------ velocity ensemble

def test_velocity_ensemble_is_the_weighted_mean(ridgecrest):
    ev = ridgecrest.design[:50]
    sel = [1, 3]
    one = {v: Scorer(ridgecrest, ev, velocities=[v]).d_score(sel) for v in (5.5, 6.5)}
    mix = Scorer(ridgecrest, ev, velocities=[5.5, 6.5], weights=[0.25, 0.75]).d_score(sel)
    assert mix == pytest.approx(0.25 * one[5.5] + 0.75 * one[6.5])
    # one model at the default velocity equals the default scorer
    assert Scorer(ridgecrest, ev, velocities=[geometry.V_P]).d_score(sel) == pytest.approx(
        Scorer(ridgecrest, ev).d_score(sel))


def test_velocity_weights_must_match():
    inst = tiny()
    with pytest.raises(ValueError):
        Scorer(inst, inst.design, velocities=[5.0, 6.0], weights=[1.0])


# ------------------------------------------------------------------ location test with hearing

def test_location_with_hearing_ignores_unheard_stations():
    inst = tiny(mags=(2.5, 2.5))
    near = location_errors(inst, (0,), inst.design, trials=2, hearing=True)
    assert near.shape == (4,) and np.all(np.isfinite(near))
    # the far candidate cannot hear these events, so adding it changes nothing
    base = location_errors(inst, (), inst.design, trials=2, hearing=True)
    far = location_errors(inst, (1,), inst.design, trials=2, hearing=True)
    assert np.allclose(base, far)


def test_location_with_hearing_reports_nan_when_under_four_stations_hear():
    inst = tiny(mags=(0.5, 0.5))
    err = location_errors(inst, (), inst.design, trials=1, hearing=True)
    assert np.all(np.isnan(err))
