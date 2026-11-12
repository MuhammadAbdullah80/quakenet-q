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

### Not built yet
`GET /events/{event_id}/plan`, `GET /events/{event_id}/replay`, `GET /memory` return
`501 NOT_BUILT` until the agent loop exists.
