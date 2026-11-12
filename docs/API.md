# QuakeNet-Q API contract (v1)

The Python API (`api/`) implements this contract. The Next.js console (`web/`) consumes it through its
own server code. Change this file first, then both sides.

## Conventions

- Base path `/api/v1`. JSON in and out. Times are ISO 8601 UTC. Distances are km in a local grid
  (x east, y north) centred on the event's study area.
- **Auth:** every request needs `Authorization: Bearer <QUAKENET_TOKEN>`. Missing or wrong → `401`.
- **Errors:** `{"error": {"code": "STRING_CODE", "message": "human-readable"}}` with the right status.
  Invalid input returns `422 INVALID_INPUT`.
  Codes: `UNAUTHORIZED`, `NOT_FOUND`, `INVALID_INPUT`, `RATE_LIMITED`, `JOB_RUNNING`, `NOT_BUILT`,
  `INTERNAL`.
- **Rate limits (per client IP):** reads 60/min; job creation 5/min; one running job at a time and at
  most 30 jobs per hour overall. Exceeded → `429` with a `Retry-After` header.
- **Sites** are integers `0..n-1` (candidate site IDs). A **network** is a sorted list of `k` site IDs.

## Endpoints

### `GET /health`
`{"status": "ok", "version": "0.2.0", "region": "local", "time_utc": "…"}`

### `GET /events`
```json
{"events": [{"id": "ridgecrest2019", "name": "Ridgecrest, California", "magnitude": 7.1,
             "time_utc": "2019-07-06T03:19:53Z", "region": "local", "available": true}]}
```

### `GET /events/{event_id}/instance`
```json
{"event_id": "ridgecrest2019", "n": 10, "k": 4, "decision_hours": 12,
 "mainshock": {"x": -4.4, "y": 2.2, "depth": 8.0},
 "design_events": [[x, y, depth], …], "valid_events": [[x, y, depth], …],
 "stations": [{"name": "CLC", "x": -4.3, "y": 7.3}],
 "candidates": [{"id": 0, "x": -4.5, "y": -5.6, "risk": 0.81}]}
```

### `GET /events/{event_id}/scoring?lam=150`
`lam` is a number in [0, 1000]; default 150.
```json
{"lam": 150, "feasible_networks": 210,
 "fidelity": [{"order": 2, "terms": 55, "spearman": 0.987, "max_abs_error": 98.7, "rank_of_its_optimum": 1}],
 "exact_optimum": [1, 3, 4, 7],
 "top_networks": [{"sites": [1, 3, 4, 7], "objective": 643.9, "risk": 2.06, "blur_km": 1.50, "rank": 1}]}
```
`top_networks` holds the best 20.

### `GET /events/{event_id}/baselines?lam=150`
```json
{"lam": 150,
 "no_new_sensors": {"blur_km": 2.73, "loc_error_mean_km": 2.99},
 "methods": [{"name": "Expert rule (azimuthal gap)", "sites": [0, 1, 2, 6], "objective": 350.6, "rank": 159,
              "risk": 2.25, "blur_km": 1.67, "loc_error_mean_km": 2.51}]}
```
Method names: `Exact (brute force)`, `Greedy forward`, `Backward elimination`, `Simulated annealing`,
`Expert rule (azimuthal gap)`, `Best by D_N criterion`.

### `POST /events/{event_id}/jobs`
Body: `{"kind": "qaoa", "reps": 1, "seed": 0, "shots": 1024, "lam": 150}`
Limits: `reps` 1–5, `seed` 0–9999, `shots` 128–4096, `lam` 0–1000. Returns `202`:
`{"job_id": "a1b2c3", "status": "queued"}`. If a job is already running → `409 JOB_RUNNING`.

### `GET /jobs/{job_id}`
```json
{"job_id": "a1b2c3", "kind": "qaoa", "event_id": "ridgecrest2019", "status": "done",
 "created_utc": "…", "finished_utc": "…", "error": null,
 "result": {
   "reps": 1, "seed": 0, "shots": 1024, "lam": 150, "seconds": 9.8,
   "ratio": 0.738, "p_opt": 0.051, "uniform_p_opt": 0.00476, "feasible": 1.0,
   "depth": 2336, "gates": 2978, "evaluations": 500,
   "exact_optimum": [1, 3, 4, 7],
   "top_counts": [{"sites": [1, 3, 4, 7], "count": 58, "objective": 643.9, "rank": 1}],
   "final": {"sites": [1, 3, 4, 7], "objective": 643.9, "rank": 1},
   "quantum_agreed": true}}
```
`status` is one of `queued`, `running`, `done`, `failed`. `result` is `null` until `done`.
`top_counts` holds the 10 most frequently measured networks. `quantum_agreed` is true when `final`
equals `exact_optimum`.

### `GET /jobs`
`{"jobs": [ …same objects without "result"… ]}`, newest first, at most 50.

### `GET /system`
```json
{"jobs_running": 0, "jobs_last_hour": 3, "job_hourly_cap": 30,
 "sources": [{"name": "USGS ComCat", "cached": true, "retrieved_utc": "…", "url": "…"}]}
```

## Version 2: the agent

Everything below is new in v2. All v1 endpoints keep their shapes, with the additions noted.
Numbers in the examples are illustrative. `GET /events/{id}/replay` from v1 is removed; use
`/sequence`.

### Changes to v1 endpoints

- `GET /events`: each event gains `"kind": "benchmark" | "live"`, `"usgs_id"`, `"lat"`, `"lon"`.
  `available` is true when the event's data is cached or can be downloaded.
- `GET /events/{id}/instance`: gains `"grid": {"lat0": 35.75, "lon0": -117.55}` (centre of the local
  km grid), `"feasibility_checked": true` (false when the road check was unavailable), and each
  candidate gains `"lat"` and `"lon"`.
- `POST /events/{id}/jobs`: `kind` may also be `"sequence"` (see below). A `qaoa` job result gains
  `"objective": "cvar" | "mean"` and `"warm_start": true | false`.

### `GET /settings`
Settings a scientist can edit. `limits` gives the allowed range of each numeric setting.
```json
{"trigger_magnitude": 6.5, "station_radius_km": 100, "sensors": 4, "candidates": 10,
 "risk_weight": 150, "move_cost": 40, "monitor_interval_hours": 1, "monitor_hours": 72,
 "drift_centroid_km": 5, "drift_score_drop": 0.2, "min_real_aftershocks": 30,
 "qaoa_layers": 3, "shots": 1024, "hearing_range": true, "live_enabled": false,
 "max_plans_per_hour": 4,
 "limits": {"trigger_magnitude": [3.0, 9.0], "station_radius_km": [20, 300], "sensors": [2, 4],
            "candidates": [8, 10], "risk_weight": [0, 1000], "move_cost": [0, 500],
            "monitor_interval_hours": [1, 12], "monitor_hours": [6, 168],
            "drift_centroid_km": [1, 50], "drift_score_drop": [0.05, 0.9],
            "min_real_aftershocks": [5, 200], "qaoa_layers": [1, 5], "shots": [128, 4096],
            "max_plans_per_hour": [1, 20]},
 "updated_utc": "2026-11-12T15:00:00Z"}
```

### `PUT /settings`
Body: any subset of the editable keys (everything except `limits` and `updated_utc`). Values
outside `limits`, unknown keys or wrong types return `422 INVALID_INPUT` and change nothing.
Returns the full settings object. Counts as a job creation for rate limiting (5 per minute).
Settings are saved to disk and survive a restart.

### `GET /feed`
Recent real earthquakes from the USGS live feed (past 24 hours, magnitude 2.5 and above), newest
first, at most 100, with what the agent did or would do with each. The backend refreshes the feed
at most once a minute.
```json
{"retrieved_utc": "...",
 "source_url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson",
 "threshold": 6.5, "live_enabled": false,
 "quakes": [{"usgs_id": "us7000abcd", "place": "42 km SSW of Example, Country", "magnitude": 4.6,
             "time_utc": "...", "lat": 1.23, "lon": 4.56, "depth_km": 10.0,
             "would_trigger": false, "status": "below_threshold", "reason": null,
             "event_id": null}]}
```
`status` is one of:
- `below_threshold`;
- `pending`: at or above the threshold, but live mode is off or it has not been processed yet;
- `skipped`: at or above the threshold but unusable; `reason` says why, for example
  `"no permanent station within 100 km"`;
- `planned`: a sequence exists and `event_id` is set.

### `POST /feed/{usgs_id}/trigger`
Start the agent by hand on a real earthquake from the feed, exactly as live mode would. Returns
`202` with `{"job_id": "...", "status": "queued"}`, or `422 INVALID_INPUT` with the skip reason.
Job creation limits apply.

### Sequences: the agent's run on one earthquake
A sequence is a first plan at hour 0 (from simulated aftershocks when too few real ones exist),
then a check every `monitor_interval_hours`, with a re-plan when drift is detected.

- **Replay** of a past earthquake: `POST /events/{id}/jobs` with
  `{"kind": "sequence", "hours": 48, "step_hours": 1}`. `hours` is 6 to 168 and `step_hours` is
  1 to 12; both are optional and default to the settings. The job plays the earthquake forward
  with a simulated clock and never uses data from after the simulated time. Its `result` is
  `{"event_id": "...", "steps": 49}`.
- **Live**: when `live_enabled` is true, the backend starts a sequence for each new feed earthquake
  at or above `trigger_magnitude` that has a permanent station within `station_radius_km`, at
  most `max_plans_per_hour` per hour. Live sequences advance in real time.

### `GET /events/{id}/sequence`
`404 NOT_FOUND` when no sequence has been run for this event.
```json
{"event_id": "ridgecrest2019", "mode": "replay", "status": "done",
 "hours_done": 48, "hours_total": 48, "started_utc": "...", "finished_utc": "...",
 "settings": {"sensors": 4, "candidates": 10, "risk_weight": 150, "move_cost": 40,
              "drift_centroid_km": 5, "drift_score_drop": 0.2},
 "grid": {"lat0": 35.75, "lon0": -117.55}, "feasibility_checked": true,
 "mainshock": {"x": -4.4, "y": 2.2, "depth": 8.0},
 "stations": [{"name": "CLC", "x": -4.3, "y": 7.3}],
 "candidates": [{"id": 0, "x": -4.5, "y": -5.6, "lat": 35.70, "lon": -117.60,
                 "backups": [{"lat": 35.71, "lon": -117.62}]}],
 "aftershocks": [[-3.1, 4.2, 7.5, 3.4, 0.25]],
 "steps": [{"hour": 0, "stage": "first_plan", "aftershocks_real": 0, "aftershocks_used": 200,
            "synthetic": true, "centroid": {"x": -4.4, "y": 2.2}, "centroid_shift_km": 0.0,
            "predicted_score": 512.3, "realised_score": null, "score_drop": null,
            "drift": false, "drift_reason": null, "sites": [1, 3, 4, 7],
            "plan": {"sites": [1, 3, 4, 7], "risk": [0.9, 0.1, 0.9, 0.2], "objective": 512.3,
                     "exact_rank": 1, "quantum_agreed": true, "retries": 0,
                     "p_opt_per_shot": 0.11, "moves": [], "expected_error_km": 2.4,
                     "expert_rule_error_km": 2.7, "seconds": 41.0}}],
 "current_sites": [1, 3, 4, 7], "plans_made": 3, "moves_total": 2}
```
- `status` is `running`, `done` or `failed`. While running, `steps` holds the steps finished so far.
- `stage` is `first_plan` (hour 0), `check` (no change; `plan` is null) or `replan` (drift; `plan`
  is set).
- `sites` in a step are the sites in place after that step. A move is `{"from": site, "to": site}`.
- Each aftershock is `[x, y, depth, magnitude, hours_after_mainshock]`. The list holds every real
  aftershock of the replayed period, so a client can show those with `hours <= step.hour`.
- `risk` in a plan is the access risk of each chosen site, recomputed at that plan.
- `drift_reason` is `"centroid moved 8.2 km"`, `"score fell 31%"`, or both joined by `"; "`.

### `GET /events/{id}/plan`
The latest plan of the event's sequence, with a reason for each site. `404` when no sequence exists.
```json
{"event_id": "ridgecrest2019", "stage": "replan", "hour": 14, "created_utc": "...",
 "sites": [{"id": 1, "x": 4.5, "y": -5.6, "lat": 35.70, "lon": -117.50, "risk": 0.88,
            "single_gain": 364.0,
            "reason": "Largest gain of any single site; 0.6 km from the nearest aftershock.",
            "backups": [{"lat": 35.71, "lon": -117.52}]}],
 "moves": [{"from": 2, "to": 7}], "objective": 643.9, "exact_rank": 1, "quantum_agreed": true,
 "p_opt_per_shot": 0.11, "expected_error_km": 2.31, "expert_rule_error_km": 2.63,
 "confidence": "medium", "feasibility_checked": true}
```
`confidence` is `high`, `medium`, `low` or `unrated`, taken from the track record in memory.

### `GET /memory`
What the agent has learned across earthquakes.
```json
{"angles": [{"key": "10-4-3", "sensors": 4, "candidates": 10, "layers": 3, "count": 5,
             "median": [0.21, 0.4, 0.33, 0.9, 1.2, 0.7]}],
 "model_weights": [{"name": "uniform 6.0 km/s", "weight": 0.4}],
 "track_record": [{"event_id": "ridgecrest2019", "hour": 14, "stage": "replan",
                   "predicted_score": 640.0, "realised_score": 598.0, "error": 0.07}],
 "confidence": "medium", "sequences": 3}
```

### `GET /noise`
A stand-in for a hardware run: the same kind of circuit on a reduced instance (6 sites, choose 2),
simulated with gate noise. It is a simulation, not a run on a quantum computer.
```json
{"instance": {"n": 6, "k": 2, "layers": 1, "event_id": "ridgecrest2019"},
 "points": [{"gate_error": 0.0, "p_best": 0.31, "valid": 1.0},
            {"gate_error": 0.001, "p_best": 0.27, "valid": 0.93}],
 "uniform_p_best": 0.0667, "note": "Simulated depolarising noise. Not a hardware run."}
```

## Internal interfaces between the science layer and the agent

The API services and the agent loop (`src/agent/`, `api/`) call the science layer only through
these functions. Signatures are fixed; internals are free.

```python
# src/instances.py
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
    aftershocks: np.ndarray          # (M, 5): x_km, y_km, depth_km, magnitude, hours_after_mainshock;
                                     # sorted by time; magnitude >= 2.5; up to 7 days
    stations: np.ndarray             # (S, 2) permanent stations in km
    station_names: tuple[str, ...]
    pool: np.ndarray                 # (P, 2) reachable candidate points in km
    feasibility_checked: bool        # False when the road check was unavailable
    radius_km: float

    def to_latlon(self, x_km, y_km) -> tuple[float, float]: ...

def list_events() -> list[dict]      # id, usgs_id, name, magnitude, time_utc, lat, lon, kind, cached
def load_event_data(event_id: str) -> EventData              # QuakeNetError NOT_FOUND / CACHE_MISS / FEED_UNAVAILABLE
def event_from_usgs(usgs_id: str, *, station_radius_km: float = 100.0) -> EventData
        # any USGS event; registers it as kind "live"; QuakeNetError NO_STATIONS when none in range
def synthetic_aftershocks(magnitude: float, depth_km: float, *, n: int = 200, seed: int = 0,
                          strike_deg: float | None = None) -> np.ndarray     # (n, 5), hours = 0
def planning_events(data: EventData, at_hours: float, *, min_real: int = 30,
                    seed: int = 0) -> tuple[np.ndarray, bool]
        # real aftershocks with hours <= at_hours, topped up with synthetic ones when fewer
        # than min_real exist; returns (events (E, 5), synthetic_used)
def select_sites(data: EventData, events: np.ndarray, *, n: int = 10,
                 min_spacing_km: float = 4.0) -> tuple[np.ndarray, list[list[tuple[float, float]]]]
        # (candidates (n, 2) in km, up to 3 backup (lat, lon) points per candidate)
def make_instance(data: EventData, candidates: np.ndarray, events: np.ndarray, *, k: int = 4,
                  valid: np.ndarray | None = None) -> Instance
        # src.geometry.Instance; risk is recomputed from `events`; Instance gains optional
        # design_mag and valid_mag arrays

# src/geometry.py
Scorer(inst, events, *, mags=None, hearing: bool = False)
        # hearing=True: pick error grows as signal-to-noise falls, and a station whose
        # signal-to-noise is below 5 for an event does not count for that event

# src/qaoa_solver.py
run_xy_qaoa(h, k, reps, seed=0, restarts=4, shots=1024, init=None, maxiter=250,
            cvar_alpha: float | None = None, diag: np.ndarray | None = None) -> dict
        # cvar_alpha set (for example 0.1): minimise the mean of the best alpha fraction of the
        # outcome distribution, using `diag`, the classical energy of every basis state.
        # The returned dict gains "objective": "cvar" | "mean".
```
