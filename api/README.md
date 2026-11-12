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

To add an event, register another `EventSpec` in `services/events.py`.

## Behaviour worth knowing

- **Client IP.** Rate limits use the `X-Client-IP` header when it holds a valid IP address, otherwise
  the socket peer. The header is trusted only because every request has already passed the token check.
- **Jobs.** A new job is refused with `409 JOB_RUNNING` while another is queued or running. A job that
  was unfinished when the server stopped is marked `failed` at the next start.
- **Rate limits and caches are in memory**, so they reset on restart. Job records do not.
- **Invalid input** returns `422 INVALID_INPUT`. The message names the field and the rule, never the value.
- **`retrieved_utc` in `/system`** is the cache file's modification time; the cached files do not
  record when they were downloaded.

## Tests

```powershell
python -m pytest tests/test_api.py -q
```
