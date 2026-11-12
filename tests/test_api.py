"""Contract tests for the HTTP API (docs/API.md). Offline; no network access."""
import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import create_app
from src.qaoa_solver import dicke_probabilities
from tests.test_agent_fakes import make_toolkit

TOKEN = "test-token-0123456789abcdef0123456789abcdef"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
V1 = "/api/v1"
EVENT = "ridgecrest2019"
JOB_BODY = {"kind": "qaoa", "reps": 1, "seed": 0, "shots": 256, "lam": 150}


def make_client(tmp_path, solver=None, **overrides) -> TestClient:
    """The v1 endpoints of the built-in Ridgecrest event; the science layer's event list is faked
    as empty, so these tests do not depend on it."""
    settings = Settings(token=TOKEN, jobs_dir=Path(tmp_path) / "jobs", **overrides)
    client = TestClient(create_app(settings, solver=solver, toolkit=make_toolkit(events={})),
                        raise_server_exceptions=False)
    client.headers.update(AUTH)
    return client


def fake_solver(h, k, reps, seed=0, restarts=1, shots=1024, init=None, maxiter=250):
    """Stands in for run_xy_qaoa where the test is about the job runner, not the circuit."""
    return dict(theta=[0.0] * (2 * reps), energy=0.0, trace=[0.0], probs=dicke_probabilities(10, 4),
                counts={(1, 3, 4, 7): shots - 3, (0, 1, 2, 3): 3}, depth=7, gates=9, evaluations=1)


def wait_for(client, job_id, timeout=90.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"{V1}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish in {timeout} s")


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == code
    assert "Traceback" not in response.text


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """Shared app for the read endpoints, so their caches are reused. Limits raised out of the way."""
    return make_client(tmp_path_factory.mktemp("shared"), solver=fake_solver, read_limit=10_000, job_limit=10_000)


# ------------------------------------------------------------------------------- start-up and auth
@pytest.mark.parametrize("token", [None, "", "short", "x" * 31, "has space " + "x" * 32])
def test_refuses_to_start_without_a_long_token(monkeypatch, token):
    if token is None:
        monkeypatch.delenv("QUAKENET_TOKEN", raising=False)
    else:
        monkeypatch.setenv("QUAKENET_TOKEN", token)
    with pytest.raises(RuntimeError) as err:
        create_app()
    assert not token or token not in str(err.value)


def test_starts_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("QUAKENET_TOKEN", TOKEN)
    monkeypatch.setenv("QUAKENET_JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("QUAKENET_QAOA_RESTARTS", "1")
    app = create_app()
    assert app.state.settings.qaoa_restarts == 1
    assert TOKEN not in repr(app.state.settings)
    assert TestClient(app).get(f"{V1}/health", headers=AUTH).status_code == 200


@pytest.mark.parametrize("headers", [
    {}, {"Authorization": "Bearer wrong-token-0123456789abcdef0123456789"}, {"Authorization": TOKEN},
    {"Authorization": f"Basic {TOKEN}"}, {"Authorization": f"Bearer {TOKEN}x"}, {"Authorization": b"Bearer " + bytes([233])}])
@pytest.mark.parametrize("path", ["/health", "/events", "/jobs", "/no-such-route"])
def test_401_without_or_with_wrong_token(tmp_path, headers, path):
    bare = TestClient(create_app(Settings(token=TOKEN, jobs_dir=tmp_path / "jobs")))
    assert_error(bare.get(V1 + path, headers=headers), 401, "UNAUTHORIZED")


def test_post_needs_auth_too(tmp_path):
    bare = TestClient(create_app(Settings(token=TOKEN, jobs_dir=tmp_path / "jobs")))
    assert_error(bare.post(f"{V1}/events/{EVENT}/jobs", json=JOB_BODY), 401, "UNAUTHORIZED")


def test_token_never_logged(tmp_path, caplog):
    caplog.set_level("DEBUG")
    c = make_client(tmp_path)
    c.get(f"{V1}/health")
    c.get(f"{V1}/health", headers={"Authorization": "Bearer nope"})
    assert TOKEN not in caplog.text


# ------------------------------------------------------------------------------- read endpoints
def test_health(client):
    r = client.get(f"{V1}/health")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"status", "version", "region", "time_utc"}
    assert (body["status"], body["version"], body["region"]) == ("ok", "0.2.0", "local")
    assert body["time_utc"].endswith("Z")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "access-control-allow-origin" not in r.headers


def test_events(client):
    body = client.get(f"{V1}/events").json()
    assert body == {"events": [{"id": EVENT, "name": "Ridgecrest, California", "magnitude": 7.1,
                                "time_utc": "2019-07-06T03:19:53Z", "region": "local", "available": True,
                                "kind": "benchmark", "usgs_id": "ci38457511", "lat": 35.7695,
                                "lon": -117.5993333}]}


def test_event_metadata_matches_the_cached_data():
    from src.geometry import DATA_DIR
    main = max(json.loads((DATA_DIR / "events.json").read_text())["events"], key=lambda e: e["mag"])
    assert main["mag"] == 7.1 and main["time_ms"] // 1000 == 1562383193   # 2019-07-06T03:19:53Z


def test_instance(client):
    r = client.get(f"{V1}/events/{EVENT}/instance")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"event_id", "n", "k", "decision_hours", "mainshock", "design_events", "valid_events",
                         "stations", "candidates", "grid", "feasibility_checked"}
    assert body["grid"] == {"lat0": 35.75, "lon0": -117.55}
    assert body["feasibility_checked"] is False        # the v1 candidates are a plain grid, not road-checked
    assert (body["event_id"], body["n"], body["k"], body["decision_hours"]) == (EVENT, 10, 4, 12)
    assert set(body["mainshock"]) == {"x", "y", "depth"} and body["mainshock"]["depth"] == 8.0
    assert len(body["design_events"]) > 100 and len(body["valid_events"]) > 100
    assert all(len(e) == 3 for e in body["design_events"] + body["valid_events"])
    assert len(body["stations"]) == 14 and set(body["stations"][0]) == {"name", "x", "y"}
    assert [c["id"] for c in body["candidates"]] == list(range(10))
    assert all(set(c) == {"id", "x", "y", "risk", "lat", "lon"} and 0 <= c["risk"] <= 1 for c in body["candidates"])
    assert all(35.4 <= c["lat"] <= 36.1 and -117.9 <= c["lon"] <= -117.2 for c in body["candidates"])


def test_scoring(client):
    r = client.get(f"{V1}/events/{EVENT}/scoring")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"lam", "feasible_networks", "fidelity", "exact_optimum", "top_networks"}
    assert body["lam"] == 150 and body["feasible_networks"] == 210
    assert [f["order"] for f in body["fidelity"]] == [2, 3, 4]
    assert all(set(f) == {"order", "terms", "spearman", "max_abs_error", "rank_of_its_optimum"}
               for f in body["fidelity"])
    assert [f["terms"] for f in body["fidelity"]] == [55, 175, 385]
    assert body["fidelity"][2]["max_abs_error"] < 1e-6 and body["fidelity"][2]["rank_of_its_optimum"] == 1
    assert body["exact_optimum"] == [1, 3, 4, 7]
    top = body["top_networks"]
    assert len(top) == 20 and [t["rank"] for t in top] == list(range(1, 21))
    assert all(set(t) == {"sites", "objective", "risk", "blur_km", "rank"} for t in top)
    assert top[0]["sites"] == body["exact_optimum"]
    assert [t["objective"] for t in top] == sorted((t["objective"] for t in top), reverse=True)
    assert all(t["sites"] == sorted(t["sites"]) and len(t["sites"]) == 4 for t in top)


def test_scoring_depends_on_lam(client):
    a = client.get(f"{V1}/events/{EVENT}/scoring", params={"lam": 0}).json()
    b = client.get(f"{V1}/events/{EVENT}/scoring", params={"lam": 400}).json()
    assert a["lam"] == 0 and b["lam"] == 400
    assert a["top_networks"][0]["risk"] > b["top_networks"][0]["risk"]


def test_baselines(client):
    r = client.get(f"{V1}/events/{EVENT}/baselines", params={"lam": 150})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"lam", "no_new_sensors", "methods"}
    assert set(body["no_new_sensors"]) == {"blur_km", "loc_error_mean_km"}
    assert [m["name"] for m in body["methods"]] == [
        "Exact (brute force)", "Greedy forward", "Backward elimination", "Simulated annealing",
        "Expert rule (azimuthal gap)", "Best by D_N criterion"]
    for m in body["methods"]:
        assert set(m) == {"name", "sites", "objective", "rank", "risk", "blur_km", "loc_error_mean_km"}
        assert len(m["sites"]) == 4 and 1 <= m["rank"] <= 210
        assert m["blur_km"] < body["no_new_sensors"]["blur_km"]
    assert body["methods"][0]["sites"] == [1, 3, 4, 7] and body["methods"][0]["rank"] == 1


def test_baselines_are_cached(client):
    client.get(f"{V1}/events/{EVENT}/baselines")
    t0 = time.perf_counter()
    assert client.get(f"{V1}/events/{EVENT}/baselines").status_code == 200
    assert time.perf_counter() - t0 < 0.2


def test_system(client):
    body = client.get(f"{V1}/system").json()
    assert set(body) == {"jobs_running", "jobs_last_hour", "job_hourly_cap", "sources"}
    assert body["jobs_running"] == 0 and body["job_hourly_cap"] == 30
    assert all(set(s) == {"name", "cached", "retrieved_utc", "url"} for s in body["sources"])
    assert body["sources"][0]["name"] == "USGS ComCat" and body["sources"][0]["cached"] is True
    assert body["sources"][0]["url"].startswith("https://earthquake.usgs.gov/")


@pytest.mark.parametrize("path", [f"/events/{EVENT}/plan", f"/events/{EVENT}/sequence", f"/events/{EVENT}/replay"])
def test_no_sequence_yet_and_replay_removed(client, path):
    assert_error(client.get(V1 + path), 404, "NOT_FOUND")


# ------------------------------------------------------------------------------- validation and errors
@pytest.mark.parametrize("path", ["/events/tohoku2011/instance", "/events/tohoku2011/scoring",
                                  "/events/tohoku2011/baselines", "/events/..%2F..%2Fetc/instance",
                                  "/events/tohoku2011/plan", "/jobs/zzzzzz", "/jobs/..%2Fsecret", "/nope"])
def test_unknown_things_are_404(client, path):
    assert_error(client.get(V1 + path), 404, "NOT_FOUND")


@pytest.mark.parametrize("lam", ["-1", "1000.5", "abc", "nan", "inf", ""])
@pytest.mark.parametrize("endpoint", ["scoring", "baselines"])
def test_bad_lam_is_rejected(client, endpoint, lam):
    assert_error(client.get(f"{V1}/events/{EVENT}/{endpoint}", params={"lam": lam}), 422, "INVALID_INPUT")


@pytest.mark.parametrize("change", [
    {"kind": "anneal"}, {"reps": 0}, {"reps": 6}, {"reps": 1.5}, {"reps": "2"}, {"seed": -1}, {"seed": 10000},
    {"shots": 127}, {"shots": 4097}, {"lam": -0.1}, {"lam": 1001}, {"lam": "x"}, {"reps": True},
    {"url": "http://169.254.169.254/"}, {"restarts": 50}])
def test_bad_job_bodies_are_rejected(client, change):
    assert_error(client.post(f"{V1}/events/{EVENT}/jobs", json={**JOB_BODY, **change}), 422, "INVALID_INPUT")


def test_malformed_or_missing_job_body(client):
    url = f"{V1}/events/{EVENT}/jobs"
    assert_error(client.post(url, content=b"{not json", headers={"Content-Type": "application/json"}),
                 422, "INVALID_INPUT")
    assert_error(client.post(url, json={"reps": 1}), 422, "INVALID_INPUT")
    assert_error(client.post(url, json=[1, 2]), 422, "INVALID_INPUT")


def test_validation_message_does_not_echo_input(client):
    r = client.post(f"{V1}/events/{EVENT}/jobs", json={**JOB_BODY, "kind": "<script>alert(1)</script>"})
    assert_error(r, 422, "INVALID_INPUT")
    assert "script" not in r.text


def test_job_for_unknown_event_is_404(client):
    assert_error(client.post(f"{V1}/events/tohoku2011/jobs", json=JOB_BODY), 404, "NOT_FOUND")


def test_wrong_method_uses_the_error_contract(client):
    r = client.delete(f"{V1}/jobs")
    assert r.status_code == 405 and set(r.json()["error"]) == {"code", "message"}


def test_internal_errors_are_generic(tmp_path, caplog):
    def broken(*a, **k):
        raise RuntimeError("secret detail in C:/private/path")
    c = make_client(tmp_path)
    c.app.state.science.instance = broken
    r = c.get(f"{V1}/events/{EVENT}/instance")
    assert_error(r, 500, "INTERNAL")
    assert "secret detail" not in r.text
    assert "secret detail" in caplog.text          # full detail goes to the log


# ------------------------------------------------------------------------------- rate limits
def test_read_rate_limit(tmp_path):
    c = make_client(tmp_path)
    assert all(c.get(f"{V1}/health").status_code == 200 for _ in range(60))
    r = c.get(f"{V1}/health")
    assert_error(r, 429, "RATE_LIMITED")
    assert 1 <= int(r.headers["retry-after"]) <= 60
    # another client behind the proxy has its own budget; a malformed header does not get one
    assert c.get(f"{V1}/health", headers={"X-Client-IP": "203.0.113.9"}).status_code == 200
    assert c.get(f"{V1}/health", headers={"X-Client-IP": "not-an-ip"}).status_code == 429


def test_rate_limit_is_per_client_ip(tmp_path):
    c = make_client(tmp_path, read_limit=2)
    one, two = {"X-Client-IP": "198.51.100.1"}, {"X-Client-IP": "2001:db8::1"}
    assert [c.get(f"{V1}/health", headers=one).status_code for _ in range(3)] == [200, 200, 429]
    assert [c.get(f"{V1}/health", headers=two).status_code for _ in range(3)] == [200, 200, 429]


def test_job_creation_rate_limit(tmp_path):
    c = make_client(tmp_path, solver=fake_solver)
    codes = []
    for _ in range(6):
        r = c.post(f"{V1}/events/{EVENT}/jobs", json=JOB_BODY)
        codes.append(r.status_code)
        if r.status_code == 202:
            wait_for(c, r.json()["job_id"])
    assert codes == [202] * 5 + [429]
    assert_error(r, 429, "RATE_LIMITED")
    assert int(r.headers["retry-after"]) >= 1
    assert c.get(f"{V1}/jobs").status_code == 200      # reads have a separate budget


def test_hourly_job_cap(tmp_path):
    c = make_client(tmp_path, solver=fake_solver, hourly_cap=2)
    for _ in range(2):
        wait_for(c, c.post(f"{V1}/events/{EVENT}/jobs", json=JOB_BODY).json()["job_id"])
    r = c.post(f"{V1}/events/{EVENT}/jobs", json=JOB_BODY)
    assert_error(r, 429, "RATE_LIMITED")
    assert 1 <= int(r.headers["retry-after"]) <= 3600
    system = c.get(f"{V1}/system").json()
    assert (system["jobs_last_hour"], system["job_hourly_cap"]) == (2, 2)


# ------------------------------------------------------------------------------- jobs
def test_409_while_a_job_runs(tmp_path):
    started, release = threading.Event(), threading.Event()

    def blocking(*args, **kwargs):
        started.set()
        assert release.wait(30)
        return fake_solver(*args, **kwargs)

    c = make_client(tmp_path, solver=blocking)
    first = c.post(f"{V1}/events/{EVENT}/jobs", json=JOB_BODY)
    assert first.status_code == 202
    assert set(first.json()) == {"job_id", "status"} and first.json()["status"] == "queued"
    try:
        assert started.wait(30)
        job = c.get(f"{V1}/jobs/{first.json()['job_id']}").json()
        assert job["status"] == "running" and job["result"] is None and job["finished_utc"] is None
        assert c.get(f"{V1}/system").json()["jobs_running"] == 1
        assert_error(c.post(f"{V1}/events/{EVENT}/jobs", json=JOB_BODY), 409, "JOB_RUNNING")
    finally:
        release.set()
    assert wait_for(c, first.json()["job_id"])["status"] == "done"
    assert c.post(f"{V1}/events/{EVENT}/jobs", json=JOB_BODY).status_code == 202


def test_failed_job_reports_a_generic_error(tmp_path, caplog):
    def broken(*args, **kwargs):
        raise RuntimeError("secret solver detail")

    c = make_client(tmp_path, solver=broken)
    job = wait_for(c, c.post(f"{V1}/events/{EVENT}/jobs", json=JOB_BODY).json()["job_id"])
    assert job["status"] == "failed" and job["result"] is None and job["finished_utc"]
    assert job["error"] and "secret" not in job["error"]
    assert "secret solver detail" in caplog.text


def test_jobs_survive_a_restart(tmp_path):
    c = make_client(tmp_path, solver=fake_solver)
    ids = [wait_for(c, c.post(f"{V1}/events/{EVENT}/jobs", json={**JOB_BODY, "seed": s}).json()["job_id"])["job_id"]
           for s in (1, 2)]
    (tmp_path / "jobs" / "broken.json").write_text("{not json")          # a corrupt record is skipped

    again = make_client(tmp_path, solver=fake_solver)
    listed = again.get(f"{V1}/jobs").json()["jobs"]
    assert [j["job_id"] for j in listed] == ids[::-1]                    # newest first
    assert all(set(j) == {"job_id", "kind", "event_id", "status", "created_utc", "finished_utc", "error"}
               for j in listed)
    full = again.get(f"{V1}/jobs/{ids[1]}").json()
    assert full["status"] == "done" and full["result"]["seed"] == 2
    assert again.get(f"{V1}/system").json()["jobs_last_hour"] == 2


def test_job_interrupted_by_a_restart_is_marked_failed(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / "abc123.json").write_text(json.dumps(dict(
        job_id="abc123", kind="qaoa", event_id=EVENT, status="running", created_utc="2026-11-12T10:00:00Z",
        finished_utc=None, error=None, result=None, params=dict(reps=1, seed=0, shots=256, lam=150.0))))
    c = make_client(tmp_path, solver=fake_solver)
    job = c.get(f"{V1}/jobs/abc123").json()
    assert job["status"] == "failed" and job["error"]
    assert c.post(f"{V1}/events/{EVENT}/jobs", json=JOB_BODY).status_code == 202


def test_job_list_is_capped_at_50(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    for i in range(60):
        (jobs / f"{i:06x}.json").write_text(json.dumps(dict(
            job_id=f"{i:06x}", kind="qaoa", event_id=EVENT, status="done",
            created_utc=f"2026-11-10T10:{i:02d}:00Z", finished_utc=f"2026-11-10T10:{i:02d}:09Z", error=None,
            result=None, params=dict(reps=1, seed=0, shots=256, lam=150.0))))
    listed = make_client(tmp_path).get(f"{V1}/jobs").json()["jobs"]
    assert len(listed) == 50 and listed[0]["job_id"] == f"{59:06x}"


def test_full_qaoa_job_with_a_tiny_budget(tmp_path, monkeypatch):
    """The real circuit, Estimator and Sampler, with the optimiser capped at 8 steps to stay fast.
    The angles are therefore poor, but the pipeline is the real one."""
    c = make_client(tmp_path, qaoa_restarts=1, qaoa_maxiter=8)
    r = c.post(f"{V1}/events/{EVENT}/jobs", json=JOB_BODY)
    assert r.status_code == 202
    job = wait_for(c, r.json()["job_id"])
    assert job["status"] == "done", job
    assert set(job) == {"job_id", "kind", "event_id", "status", "created_utc", "finished_utc", "error", "result"}
    assert (job["kind"], job["event_id"], job["error"]) == ("qaoa", EVENT, None)
    res = job["result"]
    assert set(res) == {"reps", "seed", "shots", "lam", "seconds", "ratio", "p_opt", "uniform_p_opt", "feasible",
                        "depth", "gates", "evaluations", "exact_optimum", "top_counts", "final", "quantum_agreed",
                        "objective", "warm_start"}
    assert (res["objective"], res["warm_start"]) == ("mean", False)
    assert (res["reps"], res["seed"], res["shots"], res["lam"]) == (1, 0, 256, 150)
    assert res["exact_optimum"] == [1, 3, 4, 7]
    assert res["uniform_p_opt"] == pytest.approx(1 / 210)
    assert res["feasible"] == pytest.approx(1.0)       # the XY mixer never leaves the 4-site networks
    assert 0 <= res["p_opt"] <= 1 and 0 <= res["ratio"] <= 1
    assert 1 <= res["evaluations"] <= 8 and res["depth"] > 0 and res["gates"] > 0
    top = res["top_counts"]
    assert 1 <= len(top) <= 10 and all(set(t) == {"sites", "count", "objective", "rank"} for t in top)
    assert [t["count"] for t in top] == sorted((t["count"] for t in top), reverse=True)
    assert sum(t["count"] for t in top) <= 256
    assert set(res["final"]) == {"sites", "objective", "rank"}
    assert res["final"]["objective"] == max(t["objective"] for t in top)
    assert isinstance(res["quantum_agreed"], bool)
    assert res["quantum_agreed"] == (res["final"]["sites"] == res["exact_optimum"])
