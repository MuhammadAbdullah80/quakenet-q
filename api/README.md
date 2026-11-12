# QuakeNet-Q API

The HTTP service around the scientific core in `src/`. The contract is `docs/API.md`; the security
and hosting rules are in `docs/ARCHITECTURE.md` (sections 3, 4 and 6). No AI or LLM features.

## Run

```powershell
copy .env.example .env      # then set QUAKENET_TOKEN (32+ characters)
powershell -ExecutionPolicy Bypass -File scripts\start_server.ps1
```

The server listens on `127.0.0.1:8000` only and refuses to start without a valid token.

```powershell
curl.exe -H "Authorization: Bearer $env:QUAKENET_TOKEN" http://127.0.0.1:8000/api/v1/health
```

The OpenAPI document is at `/api/v1/openapi.json` (token required). There is no hosted docs page.

## Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `QUAKENET_TOKEN` | none, required | Shared secret, at least 32 printable ASCII characters |
| `QUAKENET_REGION` | `local` | Region label reported by `/health` and `/events` |
| `QUAKENET_JOBS_DIR` | `var/jobs` | Where job records are stored, one JSON file per job |
| `QUAKENET_QAOA_RESTARTS` | `2` | Optimiser budget: number of COBYLA starts per job (1 to 8) |
| `QUAKENET_QAOA_MAXITER` | `250` | Optimiser budget: COBYLA steps per start of a `qaoa` job |
| `QUAKENET_VAR_DIR` | parent of the jobs dir (`var`) | Agent state: `settings.json`, `memory/`, `sequences/`, `feed_state.json` |
| `QUAKENET_AGENT_RESTARTS` | `4` | Agent plan: random COBYLA starts on a cold start (spec FR-16) |
| `QUAKENET_AGENT_MAXITER` | `250` | Agent plan: COBYLA steps per start |
| `QUAKENET_AGENT_LOC_EVENTS` | `100` | Agent plan: aftershocks used for the location-error estimates |
| `QUAKENET_FEED_POLL_S` | `60` | Scheduler period: due live checks and, in live mode, the feed watcher |

The settings a scientist edits (trigger magnitude, sensors, move cost, live mode, ...) are not
environment variables: they are read and changed with `GET`/`PUT /api/v1/settings` and saved in
`var/settings.json`. A change applies to the next feed check or the next sequence, without a restart.

## Layout

| File | Role |
|---|---|
| `main.py` | App factory, wiring, mapping of errors to the contract's error shape |
| `security.py` | Token check (constant time), security headers, client IP, last-resort error barrier |
| `routes.py` | Thin routes: rate limit, call a service, return its result |
| `schemas.py` | Pydantic request and response shapes |
| `ratelimit.py` | In-memory sliding-window limiter per client IP |
| `config.py` | Settings from environment variables |
| `errors.py` | Domain errors (no HTTP types) |
| `services/events.py` | Event registry (the allowlist of event IDs) |
| `services/science.py` | Instance, scoring, baselines and the QAOA job, with in-process caches |
| `services/jobs.py` | One worker thread, one job at a time, hourly cap, records on disk |
| `services/agent.py` | v2: settings, memory, sequences, plans, feed, trigger, scheduler thread, noise cache |

The agent itself (no HTTP types) is in `src/agent/`: `settings.py`, `memory.py`, `planner.py`,
`sequence.py`, `feed.py`, and `toolkit.py` (the science functions it calls, replaceable by fakes in tests).

Events: Ridgecrest 2019 is built in (its v1 numbers are unchanged); every other event comes from
`src.instances.list_events()`, including live ones started from the feed.

## Try the agent

```powershell
$h = @{ Authorization = "Bearer $env:QUAKENET_TOKEN" }
# replay Ridgecrest for 24 simulated hours, one check per hour
Invoke-RestMethod -Method Post -Headers $h -ContentType application/json `
  -Body '{"kind":"sequence","hours":24,"step_hours":1}' http://127.0.0.1:8000/api/v1/events/ridgecrest2019/jobs
Invoke-RestMethod -Headers $h http://127.0.0.1:8000/api/v1/events/ridgecrest2019/sequence   # progress, step by step
Invoke-RestMethod -Headers $h http://127.0.0.1:8000/api/v1/events/ridgecrest2019/plan       # latest plan with reasons
# lower the trigger magnitude to 4.0 (applies to the next feed check)
Invoke-RestMethod -Method Put -Headers $h -ContentType application/json `
  -Body '{"trigger_magnitude":4.0}' http://127.0.0.1:8000/api/v1/settings
```

## Behaviour worth knowing

- **Client IP.** Rate limits use the `X-Client-IP` header when it holds a valid IP address, otherwise
  the socket peer. The header is trusted only because every request has already passed the token check.
- **Jobs.** A new job is refused with `409 JOB_RUNNING` while another is queued or running. A job that
  was unfinished when the server stopped is marked `failed` at the next start.
- **`PUT /settings` and `POST /feed/{usgs_id}/trigger`** count against the job-creation limit (5 per minute).
- **Live sequences** run their first plan as a job, then advance in real time in the scheduler thread.
  A sequence (replay or live) that was running when the server stopped is marked `failed` at the next start.
- **Feed unreachable:** `GET /feed` serves the last good copy; with none, `503 FEED_UNAVAILABLE`.
- **Rate limits and caches are in memory**, so they reset on restart. Job records do not.
- **Invalid input** returns `422 INVALID_INPUT`. The message names the field and the rule, never the value.
- **`retrieved_utc` in `/system`** is the cache file's modification time; the cached files do not
  record when they were downloaded.

## Tests

```powershell
python -m pytest tests/test_api.py -q
```
