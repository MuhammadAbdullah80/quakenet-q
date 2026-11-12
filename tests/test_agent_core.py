"""The agent on its own (src/agent): settings, memory, planner, sequences, feed. Offline, with fakes."""
from __future__ import annotations

import json
from itertools import combinations

import numpy as np
import pytest

from src.agent.feed import FEED_URL, Feed, FeedUnavailable, classify, parse_feed
from src.agent.memory import Memory, confidence_from_errors
from src.agent.planner import Budget, make_plan, with_move_cost
from src.agent.sequence import AgentSkip, SequenceRun, SequenceStore, run_replay
from src.agent.settings import DEFAULTS, LIMITS, AgentSettings, SettingsError
from src.qubo import build_objective
from tests.test_agent_fakes import CANDIDATES, POISON, Calls, FakeScorer, feed_body, make_event, make_toolkit

FAST = Budget(restarts=1, maxiter=5, loc_events=20)


def values(**changes) -> dict:
    return dict(DEFAULTS, **changes)


# ------------------------------------------------------------------------------- settings
def test_settings_defaults_and_limits_match_the_contract(tmp_path):
    body = AgentSettings(tmp_path / "settings.json").get()
    assert set(body) == set(DEFAULTS) | {"limits", "updated_utc"}
    assert body["trigger_magnitude"] == 6.5 and body["live_enabled"] is False and body["hearing_range"] is True
    assert body["limits"] == {k: list(v) for k, v in LIMITS.items()}
    assert set(body["limits"]) == set(DEFAULTS) - {"hearing_range", "live_enabled"}


def test_settings_are_saved_and_survive_a_restart(tmp_path):
    path = tmp_path / "settings.json"
    s = AgentSettings(path)
    out = s.update({"trigger_magnitude": 4.0, "sensors": 3, "live_enabled": True, "risk_weight": 0})
    assert (out["trigger_magnitude"], out["sensors"], out["live_enabled"], out["risk_weight"]) == (4.0, 3, True, 0)
    again = AgentSettings(path).get()
    assert again["trigger_magnitude"] == 4.0 and again["sensors"] == 3 and again["updated_utc"] == out["updated_utc"]
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("bad", [
    {"nope": 1}, {"sensors": 5}, {"sensors": 1}, {"sensors": 3.0}, {"sensors": "3"}, {"sensors": True},
    {"trigger_magnitude": 2.9}, {"trigger_magnitude": 9.1}, {"trigger_magnitude": float("nan")},
    {"trigger_magnitude": None}, {"live_enabled": 1}, {"live_enabled": "true"}, {"shots": 127},
    {"drift_score_drop": 0.95}, {"limits": {}}, {"updated_utc": "x"},
    {"sensors": 3, "shots": 99999}])                         # one bad key: the good one is not applied either
def test_bad_settings_change_nothing(tmp_path, bad):
    s = AgentSettings(tmp_path / "settings.json")
    before = s.get()
    with pytest.raises(SettingsError):
        s.update(bad)
    assert s.get() == before
    assert not (tmp_path / "settings.json").exists()


def test_damaged_settings_file_falls_back_to_defaults(tmp_path):
    (tmp_path / "settings.json").write_text("{not json")
    assert AgentSettings(tmp_path / "settings.json").values() == DEFAULTS
    (tmp_path / "settings.json").write_text(json.dumps({"values": {"sensors": 99}}))
    assert AgentSettings(tmp_path / "settings.json").values() == DEFAULTS


# ------------------------------------------------------------------------------- memory
def test_empty_memory(tmp_path):
    m = Memory(tmp_path)
    assert m.warm_start(10, 4, 3) is None and m.confidence() == "unrated"
    snap = m.snapshot()
    assert set(snap) == {"angles", "model_weights", "track_record", "confidence", "sequences"}
    assert snap["angles"] == [] and snap["track_record"] == [] and snap["sequences"] == 0
    assert [w["weight"] for w in snap["model_weights"]] == pytest.approx([1 / 3] * 3, abs=1e-3)


def test_angles_median_is_the_warm_start_and_persists(tmp_path):
    m = Memory(tmp_path)
    for theta in ([0.1, 0.2], [0.3, 0.4], [0.2, 0.9]):
        m.add_angles(10, 4, 1, theta)
    m.add_angles(8, 2, 1, [1.0, 1.0])
    assert m.warm_start(10, 4, 1) == pytest.approx([0.2, 0.4])
    assert m.warm_start(10, 4, 2) is None
    with pytest.raises(ValueError):
        m.add_angles(10, 4, 1, [0.1])
    angles = Memory(tmp_path).snapshot()["angles"]
    assert {a["key"]: a["count"] for a in angles} == {"10-4-1": 3, "8-2-1": 1}
    assert set(angles[0]) == {"key", "sensors", "candidates", "layers", "count", "median"}


@pytest.mark.parametrize("errors, level", [([], "unrated"), ([0.1, 0.25, 0.9], "high"), ([0.3, 0.5], "medium"),
                                           ([0.6, 0.1, 0.7], "low")])
def test_confidence_levels(errors, level):
    assert confidence_from_errors(errors) == level


def test_track_record_and_model_weights(tmp_path):
    m = Memory(tmp_path)
    entry = m.record("ev", 14, "replan", 640.0, 598.0)
    assert entry == dict(event_id="ev", hour=14, stage="replan", predicted_score=640.0, realised_score=598.0,
                         error=pytest.approx(42 / 640, abs=1e-4))
    assert m.confidence() == "high"
    m.update_model_weights({"uniform 5.5 km/s": 1.0, "uniform 6.0 km/s": 0.0, "uniform 6.5 km/s": 0.0})
    m.finish_sequence()
    again = Memory(tmp_path).snapshot()
    weights = {w["name"]: w["weight"] for w in again["model_weights"]}
    assert weights["uniform 5.5 km/s"] == pytest.approx(0.5, abs=1e-3)      # (1+1)/(1+2) against (0+1)/(1+2) twice
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-3)
    assert again["sequences"] == 1 and len(again["track_record"]) == 1


# ------------------------------------------------------------------------------- planner
def _instance_and_scorer(k=4):
    tk = make_toolkit()
    data = make_event()
    events, _ = tk.planning_events(data, 12, min_real=30)
    inst = tk.make_instance(data, CANDIDATES, events, k=k)
    return inst, FakeScorer(inst, events[:, :3])


def test_move_cost_is_exact_for_every_network():
    inst, scorer = _instance_and_scorer()
    base = build_objective(inst, scorer, 150.0, order=4)
    current = (0, 1, 2, 3)
    obj = with_move_cost(base, current, 40.0, 4)
    for s in combinations(range(10), 4):
        moves = 4 - len(set(s) & set(current))
        assert obj.value(s) == pytest.approx(base.value(s) - 40.0 * moves, abs=1e-6)
    assert with_move_cost(base, None, 40.0, 4) is base


def _plan(tmp_path, mode="good", current=None, memory=None, calls=None, **settings):
    calls = calls or Calls()
    tk = make_toolkit(calls, mode)
    data = make_event()
    events, _ = tk.planning_events(data, 12, min_real=30)
    memory = memory or Memory(tmp_path / "memory")
    plan = make_plan(data, events, CANDIDATES, current=current, settings=values(**settings), memory=memory,
                     toolkit=tk, budget=FAST)
    return plan, calls, memory


def test_plan_agrees_cold_then_warm_start(tmp_path):
    plan, calls, memory = _plan(tmp_path, qaoa_layers=2)
    p = plan.public
    assert set(p) == {"sites", "risk", "objective", "exact_rank", "quantum_agreed", "retries", "p_opt_per_shot",
                      "moves", "expected_error_km", "expert_rule_error_km", "seconds"}
    assert p["quantum_agreed"] is True and p["retries"] == 0 and p["exact_rank"] == 1 and p["moves"] == []
    assert len(p["sites"]) == 4 and p["sites"] == sorted(p["sites"]) and len(p["risk"]) == 4
    first = calls.solver[0]
    assert (first["reps"], first["init"], first["restarts"], first["cvar_alpha"], first["has_diag"]) == (2, None, 1, 0.1, True)
    assert memory.warm_start(10, 4, 2) == pytest.approx([0.1, 0.2, 0.3, 0.4])
    assert plan.details["warm_start"] is False and plan.details["objective_kind"] == "cvar"
    for site in plan.details["sites"]:
        assert site["reason"].endswith("km from the nearest aftershock.") and site["reason"][0].isupper()
    assert sum("Largest gain of any single site" in s["reason"] for s in plan.details["sites"]) <= 1

    plan2, calls, _ = _plan(tmp_path, memory=memory, calls=calls, qaoa_layers=2)
    assert calls.solver[1]["init"] == pytest.approx([0.1, 0.2, 0.3, 0.4]) and calls.solver[1]["restarts"] == 0
    assert plan2.details["warm_start"] is True


def test_disagreement_retries_twice_then_publishes_the_exact_optimum(tmp_path):
    plan, calls, memory = _plan(tmp_path, mode="bad", qaoa_layers=1, shots=256)
    assert [(c["reps"], c["shots"]) for c in calls.solver] == [(1, 256), (3, 4096), (5, 4096)]
    assert calls.solver[1]["init"] is not None and len(calls.solver[1]["init"]) == 6
    p = plan.public
    assert p["quantum_agreed"] is False and p["retries"] == 2 and p["exact_rank"] == 1
    assert plan.details["quantum_rank"] == 2
    good, _, _ = _plan(tmp_path / "other", mode="good", qaoa_layers=1)
    assert p["sites"] == good.public["sites"]                                  # the exact optimum
    assert {a["key"] for a in memory.snapshot()["angles"]} == {"10-4-1", "10-4-3", "10-4-5"}


def test_move_cost_keeps_sensors_in_place(tmp_path):
    free, _, _ = _plan(tmp_path / "a", qaoa_layers=1)
    current = tuple(i for i in range(10) if i not in free.sites)[:4]
    stay, _, _ = _plan(tmp_path / "b", current=current, qaoa_layers=1, move_cost=500)
    assert stay.sites == tuple(sorted(current)) and stay.public["moves"] == []
    move, _, _ = _plan(tmp_path / "c", current=current, qaoa_layers=1, move_cost=0)
    assert move.sites == free.sites
    assert len(move.public["moves"]) == 4
    assert all(set(m) == {"from", "to"} and m["from"] in current and m["to"] in free.sites for m in move.public["moves"])


def test_real_circuit_through_the_planner(tmp_path):
    """The real CVaR QAOA (src.qaoa_solver) on a 8-candidate, 2-sensor plan with a tiny budget."""
    from src.qaoa_solver import run_xy_qaoa
    tk = make_toolkit()
    tk = tk.__class__(**{**tk.__dict__, "solver": run_xy_qaoa})
    data = make_event()
    events, _ = tk.planning_events(data, 12, min_real=30)
    plan = make_plan(data, events, CANDIDATES[:8], current=None,
                     settings=values(sensors=2, candidates=8, qaoa_layers=1, shots=256),
                     memory=Memory(tmp_path), toolkit=tk, budget=Budget(restarts=1, maxiter=4, retries=0, loc_events=10))
    assert len(plan.sites) == 2 and 0 <= plan.public["p_opt_per_shot"] <= 1
    assert plan.details["objective_kind"] == "cvar"


# ------------------------------------------------------------------------------- sequences
def test_replay_detects_drift_replans_with_moves_and_never_sees_the_future(tmp_path):
    calls = Calls()
    tk = make_toolkit(calls)
    store, memory = SequenceStore(tmp_path / "seq"), Memory(tmp_path / "mem")
    FakeScorer.seen.clear()
    result = run_replay(make_event(), hours=24, step_hours=1, settings=values(qaoa_layers=1), toolkit=tk,
                        memory=memory, store=store, budget=FAST)
    assert result == {"event_id": "fakequake", "steps": 25}
    seq = store.load("fakequake")
    assert seq["status"] == "done" and seq["hours_done"] == 24 and seq["finished_utc"]
    steps = seq["steps"]
    assert [s["hour"] for s in steps] == list(range(25))
    assert steps[0]["stage"] == "first_plan" and steps[0]["synthetic"] is True and steps[0]["aftershocks_real"] == 0
    assert all(s["stage"] == "check" and s["plan"] is None for s in steps[1:12])
    replans = [s for s in steps if s["stage"] == "replan"]
    assert replans and all(s["hour"] > 12 and s["drift"] and s["drift_reason"] for s in replans)
    assert "centroid moved" in replans[0]["drift_reason"]
    assert sum(len(s["plan"]["moves"]) for s in replans) == seq["moves_total"] > 0
    assert seq["plans_made"] == 1 + len(replans) and seq["current_sites"] == steps[-1]["sites"]
    # no data from after the simulated time
    assert all(h <= 24 for h in calls.planning_hours)
    assert all(np.abs(ev).max() < 500 for ev in FakeScorer.seen)
    assert all(a[4] <= 24 for a in seq["aftershocks"]) and len(seq["aftershocks"]) == 80
    for s in steps:
        assert s["aftershocks_real"] == sum(a[4] <= s["hour"] for a in seq["aftershocks"])
    # memory: one sequence, a track record, weights updated
    snap = memory.snapshot()
    assert snap["sequences"] == 1 and len(snap["track_record"]) >= 1 and snap["confidence"] != "unrated"
    assert store.load_plan("fakequake")["stage"] == "replan"


def test_sequence_is_saved_after_every_step(tmp_path):
    store = SequenceStore(tmp_path)
    run = SequenceRun(make_event(), mode="replay", hours=6, step_hours=3, settings=values(qaoa_layers=1),
                      toolkit=make_toolkit(), memory=Memory(tmp_path / "m"), store=store, budget=FAST)
    assert run.hours() == [0, 3, 6]
    started = store.load("fakequake")
    assert started["status"] == "running" and started["steps"] == [] and started["finished_utc"] is None
    run.step(0)
    seq = store.load("fakequake")
    assert seq["status"] == "running" and len(seq["steps"]) == 1 and seq["hours_total"] == 6
    assert len(seq["candidates"]) == 10 and set(seq["candidates"][0]) == {"id", "x", "y", "lat", "lon", "backups"}
    plan = store.load_plan("fakequake")
    assert plan["stage"] == "first_plan" and plan["confidence"] == "unrated" and len(plan["sites"]) == 4
    store.mark_interrupted()
    assert store.load("fakequake")["status"] == "failed"


def test_too_few_sites_is_a_skip(tmp_path):
    tk = make_toolkit()
    tk = tk.__class__(**{**tk.__dict__, "select_sites": lambda data, events, n=10: (CANDIDATES[:5], [[]] * 5)})
    with pytest.raises(AgentSkip, match="insufficient reachable sites"):
        run_replay(make_event(), hours=6, step_hours=6, settings=values(), toolkit=tk, memory=Memory(tmp_path),
                   store=SequenceStore(tmp_path / "s"), budget=FAST)
    assert SequenceStore(tmp_path / "s").load("fakequake")["status"] == "failed"


# ------------------------------------------------------------------------------- feed
QUAKES = [("us7000aaaa", 4.6, 1.0, 35.0, -117.0), ("ci1234567", 6.9, 2.0, 36.0, -118.0),
          ("BAD-ID", 7.0, 1.0, 0, 0), ("nc0000001", 3.1, 0.5, 38.0, -122.0)]


class FakeGet:
    def __init__(self, body=None, fail=False):
        self.body, self.fail, self.calls = body or feed_body(QUAKES), fail, []

    def __call__(self, url, max_age_s=None):
        self.calls.append((url, max_age_s))
        if self.fail:
            raise OSError("down")
        return self.body


def test_parse_feed_newest_first_and_skips_malformed():
    quakes = parse_feed(feed_body(QUAKES))
    assert [q["usgs_id"] for q in quakes] == ["nc0000001", "us7000aaaa", "ci1234567"]
    assert set(quakes[0]) >= {"usgs_id", "place", "magnitude", "time_utc", "lat", "lon", "depth_km"}


@pytest.mark.parametrize("threshold, triggering", [(6.5, {"ci1234567"}), (4.0, {"ci1234567", "us7000aaaa"}),
                                                   (3.0, {"ci1234567", "us7000aaaa", "nc0000001"})])
def test_classification_follows_the_threshold(threshold, triggering):
    quakes = parse_feed(feed_body(QUAKES))
    rows = [classify(q, values(trigger_magnitude=threshold), {}) for q in quakes]
    assert {r["usgs_id"] for r in rows if r["would_trigger"]} == triggering
    assert all(r["status"] == ("pending" if r["would_trigger"] else "below_threshold") for r in rows)


def test_classification_uses_the_remembered_state():
    q = parse_feed(feed_body(QUAKES))[2]
    assert classify(q, values(), {q["usgs_id"]: {"status": "planned", "event_id": "ev1"}})["status"] == "planned"
    row = classify(q, values(), {q["usgs_id"]: {"status": "skipped", "reason": "no permanent station within 100 km"}})
    assert (row["status"], row["reason"]) == ("skipped", "no permanent station within 100 km")


def test_feed_reads_at_most_once_a_minute_and_falls_back(tmp_path):
    now = [1000.0]
    get = FakeGet()
    feed = Feed(tmp_path / "state.json", http_get=get, clock=lambda: now[0])
    snap = feed.snapshot(values())
    assert snap["source_url"] == FEED_URL and snap["threshold"] == 6.5 and len(snap["quakes"]) == 3
    assert get.calls == [(FEED_URL, 60)]
    feed.snapshot(values())
    now[0] += 59
    feed.snapshot(values())
    assert len(get.calls) == 1
    now[0] += 2
    get.fail = True
    assert len(feed.snapshot(values())["quakes"]) == 3                        # last good copy
    assert len(get.calls) == 2
    with pytest.raises(FeedUnavailable):
        Feed(tmp_path / "other.json", http_get=FakeGet(fail=True)).snapshot(values())


def test_feed_state_persists_and_gates_starts(tmp_path):
    feed = Feed(tmp_path / "state.json", http_get=FakeGet())
    q = feed.find("ci1234567")
    assert feed.reason_not_to_start(q, values()) is None
    assert "below the trigger magnitude" in feed.reason_not_to_start(feed.find("us7000aaaa"), values())
    assert feed.reason_not_to_start(feed.find("us7000aaaa"), values(trigger_magnitude=4.0)) is None
    feed.mark("ci1234567", "planned", event_id="ev1")
    again = Feed(tmp_path / "state.json", http_get=FakeGet())
    assert again.state()["ci1234567"]["event_id"] == "ev1" and again.started_last_hour() == 1
    assert "already started" in again.reason_not_to_start(q, values())
    with pytest.raises(ValueError):
        feed.mark("../etc", "planned")


def test_track_record_error_uses_information_scale(tmp_path):
    """A net score near zero must not blow up the relative error (it is measured on information gain)."""
    from src.agent.memory import Memory
    m = Memory(tmp_path)
    e = m.record("ev", 0, "first", predicted=0.5, realised=0.0, scale=50.0)
    assert e["error"] == 0.01
    e = m.record("ev", 1, "check", predicted=10.0, realised=8.0)
    assert e["error"] == 0.2
