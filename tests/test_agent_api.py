"""Contract tests of the v2 endpoints (docs/API.md, "Version 2: the agent"). Offline, with fakes."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import create_app
from tests.test_agent_fakes import QuakeNetErrorLike, feed_body, make_event, make_toolkit
from tests.test_api import AUTH, TOKEN, V1, assert_error, wait_for

FEED = [("ci1234567", 6.9, 2.5, 36.0, -118.0), ("us7000aaaa", 4.6, 1.0, 35.0, -117.0),
        ("nost000001", 7.2, 3.0, 10.0, 10.0), ("nc0000001", 3.1, 0.5, 38.0, -122.0)]
SEQ_KEYS = {"event_id", "mode", "status", "hours_done", "hours_total", "started_utc", "finished_utc", "settings",
            "grid", "feasibility_checked", "mainshock", "stations", "candidates", "aftershocks", "steps",
            "current_sites", "plans_made", "moves_total"}
STEP_KEYS = {"hour", "stage", "aftershocks_real", "aftershocks_used", "synthetic", "centroid", "centroid_shift_km",
             "predicted_score", "realised_score", "score_drop", "drift", "drift_reason", "sites", "plan"}
PLAN_KEYS = {"event_id", "stage", "hour", "created_utc", "sites", "moves", "objective", "exact_rank", "quantum_agreed",
             "p_opt_per_shot", "expected_error_km", "expert_rule_error_km", "confidence", "feasibility_checked"}
NOISE = {"instance": {"n": 6, "k": 2, "layers": 1, "event_id": "ridgecrest2019"},
         "points": [{"gate_error": 0.0, "p_best": 0.31, "valid": 1.0}, {"gate_error": 0.001, "p_best": 0.27, "valid": 0.93}],
         "uniform_p_best": 0.0667, "note": "Simulated depolarising noise. Not a hardware run."}


class Get:
    def __init__(self, rows=FEED):
        self.rows, self.fail, self.calls = rows, False, 0

    def __call__(self, url, max_age_s=None):
        self.calls += 1
        if self.fail:
            raise OSError("down")
        return feed_body(self.rows)


class Noise:
    calls = 0

    def __call__(self):
        Noise.calls += 1
        return dict(NOISE)


def make(tmp_path, *, get=None, usgs=None, **overrides):
    usgs = usgs if usgs is not None else {
        "ci1234567": make_event("live_ci1234567", "ci1234567", hours_old=2.5),
        "nost000001": QuakeNetErrorLike("NO_STATIONS")}
    tk = make_toolkit(usgs=usgs)
    settings = Settings(token=TOKEN, jobs_dir=Path(tmp_path) / "jobs", agent_restarts=1, agent_maxiter=5,
                        agent_loc_events=20, **overrides)
    app = create_app(settings, toolkit=tk, feed_get=get or Get(), noise=Noise())
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update(AUTH)
    return client


@pytest.fixture
def c(tmp_path):
    return make(tmp_path, read_limit=10_000, job_limit=10_000)


# ------------------------------------------------------------------------------- auth
@pytest.mark.parametrize("method, path", [("get", "/settings"), ("put", "/settings"), ("get", "/feed"),
                                          ("post", "/feed/ci1234567/trigger"), ("get", "/memory"), ("get", "/noise"),
                                          ("get", "/events/fakequake/sequence"), ("get", "/events/fakequake/plan")])
def test_v2_endpoints_need_the_token(tmp_path, method, path):
    bare = TestClient(create_app(Settings(token=TOKEN, jobs_dir=tmp_path / "jobs"), toolkit=make_toolkit()))
    assert_error(getattr(bare, method)(V1 + path), 401, "UNAUTHORIZED")


# ------------------------------------------------------------------------------- events
def test_events_list_every_registered_event(c):
    events = c.get(f"{V1}/events").json()["events"]
    assert [e["id"] for e in events] == ["ridgecrest2019", "fakequake"]
    fake = events[1]
    assert set(fake) == {"id", "name", "magnitude", "time_utc", "region", "available", "kind", "usgs_id", "lat", "lon"}
    assert (fake["kind"], fake["usgs_id"], fake["available"]) == ("benchmark", "xx0001", True)
    assert fake["time_utc"].endswith("Z")


def test_instance_of_a_registered_event(c):
    body = c.get(f"{V1}/events/fakequake/instance").json()
    assert body["grid"] == {"lat0": 35.0, "lon0": -117.0} and body["feasibility_checked"] is True
    assert body["n"] == 10 and body["k"] == 4 and len(body["candidates"]) == 10
    assert all({"lat", "lon"} <= set(cand) for cand in body["candidates"])


# ------------------------------------------------------------------------------- settings
def test_get_and_put_settings(tmp_path):
    c = make(tmp_path)
    body = c.get(f"{V1}/settings").json()
    assert body["trigger_magnitude"] == 6.5 and body["limits"]["sensors"] == [2, 4] and body["updated_utc"]
    r = c.put(f"{V1}/settings", json={"trigger_magnitude": 4.0, "move_cost": 0, "hearing_range": False})
    assert r.status_code == 200
    assert (r.json()["trigger_magnitude"], r.json()["move_cost"], r.json()["hearing_range"]) == (4.0, 0, False)
    assert set(r.json()) == set(body)
    again = make(tmp_path)                                               # survives a restart
    assert again.get(f"{V1}/settings").json()["trigger_magnitude"] == 4.0


@pytest.mark.parametrize("bad", [{"nope": 1}, {"sensors": 5}, {"sensors": 3.5}, {"sensors": "3"}, {"sensors": True},
                                 {"trigger_magnitude": None}, {"live_enabled": "yes"}, {"limits": {}},
                                 {"updated_utc": "x"}, {"sensors": 3, "shots": 5000}, [1, 2]])
def test_bad_settings_are_rejected_and_change_nothing(c, bad):
    before = c.get(f"{V1}/settings").json()
    assert_error(c.put(f"{V1}/settings", json=bad), 422, "INVALID_INPUT")
    assert c.get(f"{V1}/settings").json() == before


def test_put_settings_counts_as_a_job_creation(tmp_path):
    c = make(tmp_path)
    codes = [c.put(f"{V1}/settings", json={"shots": 256}).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]
    assert_error(c.post(f"{V1}/feed/ci1234567/trigger"), 429, "RATE_LIMITED")


# ------------------------------------------------------------------------------- feed and trigger
def test_feed_shape_and_the_threshold_takes_effect_at_once(c):
    body = c.get(f"{V1}/feed").json()
    assert set(body) == {"retrieved_utc", "source_url", "threshold", "live_enabled", "quakes"}
    assert body["source_url"] == "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
    assert (body["threshold"], body["live_enabled"]) == (6.5, False)
    rows = {q["usgs_id"]: q for q in body["quakes"]}
    assert set(rows["ci1234567"]) == {"usgs_id", "place", "magnitude", "time_utc", "lat", "lon", "depth_km",
                                      "would_trigger", "status", "reason", "event_id"}
    assert rows["us7000aaaa"]["status"] == "below_threshold" and rows["ci1234567"]["status"] == "pending"
    c.put(f"{V1}/settings", json={"trigger_magnitude": 4.0})
    rows = {q["usgs_id"]: q for q in c.get(f"{V1}/feed").json()["quakes"]}
    assert rows["us7000aaaa"]["would_trigger"] is True and rows["us7000aaaa"]["status"] == "pending"


def test_feed_unreachable(tmp_path):
    get = Get()
    get.fail = True
    c = make(tmp_path, get=get)
    assert_error(c.get(f"{V1}/feed"), 503, "FEED_UNAVAILABLE")


@pytest.mark.parametrize("uid", ["US7000AAAA", "abc", "a" * 21, "..%2F..%2Fx", "ci-123456"])
def test_trigger_validates_the_usgs_id(c, uid):
    r = c.post(f"{V1}/feed/{uid}/trigger")
    assert r.status_code in (404, 422) and r.json()["error"]["code"] in ("INVALID_INPUT", "NOT_FOUND")


def test_trigger_refuses_with_a_reason(c):
    assert_error(c.post(f"{V1}/feed/zz9999999/trigger"), 404, "NOT_FOUND")
    r = c.post(f"{V1}/feed/us7000aaaa/trigger")
    assert_error(r, 422, "INVALID_INPUT")
    assert "below the trigger magnitude 6.5" in r.json()["error"]["message"]


def test_trigger_runs_a_live_sequence(c):
    r = c.post(f"{V1}/feed/ci1234567/trigger")
    assert r.status_code == 202 and set(r.json()) == {"job_id", "status"}
    job = wait_for(c, r.json()["job_id"])
    assert job["status"] == "done", job
    assert job["result"] == {"event_id": "live_ci1234567", "steps": 1} and job["event_id"] == "live_ci1234567"
    seq = c.get(f"{V1}/events/live_ci1234567/sequence").json()
    assert seq["mode"] == "live" and seq["status"] == "running" and seq["steps"][0]["hour"] == 2
    assert all(a[4] <= 2 for a in seq["aftershocks"])
    rows = {q["usgs_id"]: q for q in c.get(f"{V1}/feed").json()["quakes"]}
    assert (rows["ci1234567"]["status"], rows["ci1234567"]["event_id"]) == ("planned", "live_ci1234567")
    again = c.post(f"{V1}/feed/ci1234567/trigger")
    assert_error(again, 422, "INVALID_INPUT")
    # the scheduler advances the live sequence in real time
    agent = c.app.state.agent
    agent.advance_live()
    assert len(c.get(f"{V1}/events/live_ci1234567/sequence").json()["steps"]) == 1     # nothing due yet
    agent.clock = lambda: time.time() + 70 * 3600
    agent.advance_live()
    seq = c.get(f"{V1}/events/live_ci1234567/sequence").json()
    assert seq["status"] == "done" and seq["hours_done"] == 72 and len(seq["steps"]) == 71
    assert agent.live_running() == []


def test_trigger_without_stations_is_skipped_with_the_reason(c):
    job = wait_for(c, c.post(f"{V1}/feed/nost000001/trigger").json()["job_id"])
    assert job["status"] == "failed" and job["error"] == "Skipped: no permanent station within 100 km"
    row = {q["usgs_id"]: q for q in c.get(f"{V1}/feed").json()["quakes"]}["nost000001"]
    assert (row["status"], row["reason"]) == ("skipped", "no permanent station within 100 km")
    r = c.post(f"{V1}/feed/nost000001/trigger")
    assert_error(r, 422, "INVALID_INPUT")
    assert "no permanent station" in r.json()["error"]["message"]


def test_live_watcher_starts_new_quakes_within_the_hourly_limit(c):
    agent = c.app.state.agent
    agent.tick()
    assert c.get(f"{V1}/jobs").json()["jobs"] == []                       # live mode is off by default
    c.put(f"{V1}/settings", json={"live_enabled": True, "max_plans_per_hour": 1})
    agent.tick()
    jobs = c.get(f"{V1}/jobs").json()["jobs"]
    assert len(jobs) == 1 and jobs[0]["kind"] == "sequence"
    assert wait_for(c, jobs[0]["job_id"])["status"] == "done"
    agent.tick()                                                          # nost000001 qualifies, but the limit is 1
    assert len(c.get(f"{V1}/jobs").json()["jobs"]) == 1
    row = {q["usgs_id"]: q for q in c.get(f"{V1}/feed").json()["quakes"]}["nost000001"]
    assert row["status"] == "pending" and row["reason"] == "hourly plan limit reached"


def test_watcher_failures_never_reach_the_api(c, monkeypatch):
    c.put(f"{V1}/settings", json={"live_enabled": True})
    agent = c.app.state.agent

    def broken(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(agent.feed, "quakes", broken)
    agent.tick()                                                           # logged, not raised
    assert c.get(f"{V1}/health").status_code == 200


# ------------------------------------------------------------------------------- sequences, plans, memory
@pytest.mark.parametrize("body", [{"kind": "sequence", "hours": 5}, {"kind": "sequence", "hours": 169},
                                  {"kind": "sequence", "step_hours": 0}, {"kind": "sequence", "step_hours": 13},
                                  {"kind": "sequence", "hours": "6"}, {"kind": "sequence", "hours": 6.0},
                                  {"kind": "sequence", "reps": 1}])
def test_bad_sequence_bodies(c, body):
    assert_error(c.post(f"{V1}/events/fakequake/jobs", json=body), 422, "INVALID_INPUT")


def test_replay_job_and_the_sequence_plan_and_memory_endpoints(c):
    assert_error(c.get(f"{V1}/events/fakequake/sequence"), 404, "NOT_FOUND")
    assert_error(c.get(f"{V1}/events/fakequake/plan"), 404, "NOT_FOUND")
    c.put(f"{V1}/settings", json={"qaoa_layers": 1})
    r = c.post(f"{V1}/events/fakequake/jobs", json={"kind": "sequence", "hours": 24, "step_hours": 1})
    assert r.status_code == 202
    job = wait_for(c, r.json()["job_id"])
    assert job["status"] == "done" and job["kind"] == "sequence"
    assert job["result"] == {"event_id": "fakequake", "steps": 25}

    seq = c.get(f"{V1}/events/fakequake/sequence").json()
    assert set(seq) == SEQ_KEYS and seq["mode"] == "replay" and seq["status"] == "done"
    assert (seq["hours_done"], seq["hours_total"]) == (24, 24)
    assert set(seq["settings"]) == {"sensors", "candidates", "risk_weight", "move_cost", "drift_centroid_km",
                                    "drift_score_drop"}
    assert set(seq["candidates"][0]) == {"id", "x", "y", "lat", "lon", "backups"}
    assert set(seq["candidates"][0]["backups"][0]) == {"lat", "lon"}
    assert all(len(a) == 5 for a in seq["aftershocks"])
    assert all(set(s) == STEP_KEYS for s in seq["steps"])
    first = seq["steps"][0]
    assert first["stage"] == "first_plan" and set(first["plan"]) == {
        "sites", "risk", "objective", "exact_rank", "quantum_agreed", "retries", "p_opt_per_shot", "moves",
        "expected_error_km", "expert_rule_error_km", "seconds"}
    replan = next(s for s in seq["steps"] if s["stage"] == "replan")
    assert replan["plan"]["moves"] and set(replan["plan"]["moves"][0]) == {"from", "to"}

    plan = c.get(f"{V1}/events/fakequake/plan").json()
    assert set(plan) == PLAN_KEYS and plan["stage"] == "replan" and plan["hour"] == replan["hour"]
    assert set(plan["sites"][0]) == {"id", "x", "y", "lat", "lon", "risk", "single_gain", "reason", "backups"}
    assert plan["confidence"] in ("high", "medium", "low", "unrated")

    mem = c.get(f"{V1}/memory").json()
    assert set(mem) == {"angles", "model_weights", "track_record", "confidence", "sequences"}
    assert mem["sequences"] == 1 and mem["angles"][0]["key"] == "10-4-1" and mem["track_record"]
    assert set(mem["track_record"][0]) == {"event_id", "hour", "stage", "predicted_score", "realised_score", "error"}
    assert mem["confidence"] in ("high", "medium", "low")


def test_sequence_job_uses_the_settings_by_default(c):
    c.put(f"{V1}/settings", json={"monitor_hours": 6, "monitor_interval_hours": 3, "qaoa_layers": 1})
    job = wait_for(c, c.post(f"{V1}/events/fakequake/jobs", json={"kind": "sequence"}).json()["job_id"])
    assert job["result"] == {"event_id": "fakequake", "steps": 3}


def test_sequence_counts_against_one_job_at_a_time(c):
    c.put(f"{V1}/settings", json={"qaoa_layers": 1})
    first = c.post(f"{V1}/events/fakequake/jobs", json={"kind": "sequence", "hours": 168, "step_hours": 1})
    assert first.status_code == 202
    second = c.post(f"{V1}/events/fakequake/jobs", json={"kind": "qaoa"})
    if second.status_code != 202:                                         # the first one may already be done
        assert_error(second, 409, "JOB_RUNNING")
    wait_for(c, first.json()["job_id"])


def test_noise_is_cached(c):
    Noise.calls = 0
    assert c.get(f"{V1}/noise").json() == NOISE
    assert c.get(f"{V1}/noise").status_code == 200 and Noise.calls == 1


def test_unknown_event_sequence_is_404(c):
    for path in ("/events/nope/sequence", "/events/nope/plan", "/events/BAD!/sequence"):
        assert_error(c.get(V1 + path), 404, "NOT_FOUND")
