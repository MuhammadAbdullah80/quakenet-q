# QuakeNet-Q: System Architecture

Status: **draft for review**, 2026-11-12. Nothing in this document is built yet except the scientific
core's proof of concept. Items marked *(to verify)* have not been checked against the provider's
documentation.

## 1. Overview

```
 Browser
    │  HTTPS
    ▼
 Next.js frontend on Vercel (server-rendered)  ← test console; secrets never reach the browser
    │  typed JSON API (OpenAPI), over a secure tunnel with a shared secret (section 4)
    ▼
 Python API (FastAPI) on the team laptop  ── shared-secret check · rate limit · validation · error contract
    │
    ├── quakenet core (pure Python + Qiskit)   ← spec modules: candidates, physics, objective,
    │                                             quantum, baselines, agent, memory, report
    ├── outbound gateway  ── per-host limits · cache · retries · circuit breaker · host allowlist
    │        └── USGS feed · ComCat · FDSN stations · Overpass (roads) · terrain tiles
    └── job runner        ── one plan job per (event, stage); results stored on disk
```

**Why this shape**
- **Python core, Next.js front.** Qiskit is Python, so the science stays in one Python package. Next.js
  renders pages on the server, so the site arrives pre-loaded and API keys stay off the browser.
- **One typed contract** (OpenAPI generated from the Python API) joins the two halves. Frontend types are
  generated from it, never hand-copied.
- **Dependencies point inward.** The core knows nothing about HTTP or the frontend.

## 2. Geo-based design

**Goal:** serve each seismic region from a server close to its data sources and its users.

| Layer | Full design (later) | MVP / hackathon |
|---|---|---|
| Entry | Geo-DNS or anycast routes users to the nearest region | One server |
| Regions | For example: Americas, Europe–Mediterranean, Asia–Pacific; each watches its own earthquake feed and station services | One region setting in config |
| Load balancing | Regional load balancer in front of stateless API instances; health checks; failover to the next-nearest region | None needed |
| Plan jobs | Regional queue; exactly one job per (event, stage) through an idempotency key | In-process job runner with the same key |
| Storage | Per-region cache and plan store; memory (angles, model weights) replicated across regions | Local files |

**What we do now so scaling is configuration, not a rewrite**
- Every event, plan and cache entry carries a `region` field.
- The API is stateless; all state lives in the store behind an interface.
- Data sources sit behind the `EventSource` interface from the spec, so a region can use a different
  provider.
- Regional data providers other than USGS and IRIS (for example EMSC, ORFEUS-EIDA) are *(to verify)*.

**Trade-off:** multiple regions add cost and operational work, and the hackathon needs neither. This
section is design only until there is real demand.

## 3. Rate limiting

### 3.1 Calls we make (outbound)

One outbound gateway handles every external call:
- a per-host request budget (token bucket);
- a response cache, with URL and retrieval time recorded;
- a 30 s timeout and 3 retries with exponential backoff and jitter;
- obeys `429` and `Retry-After`;
- a circuit breaker per host, falling back to the cache or the spec's edge-case behaviour;
- a host allowlist, so only the hosts below can be called.

| Source | Use | Known limit | Our budget |
|---|---|---|---|
| USGS GeoJSON feed | Trigger | Feed refreshes about once a minute *(to verify)* | 1 request per minute |
| USGS ComCat event API | Aftershocks | 20,000 events per query (confirmed by an error-free test query) | 1 request per plan stage, cached |
| IRIS/EarthScope FDSN stations | Permanent stations | Usage guidelines *(to verify)* | 1 request per event, cached |
| Overpass API (OpenStreetMap) | Roads | Public usage policy *(to verify)* | 1 request per event, cached; grid-only fallback |
| AWS Terrain Tiles | Slope | No key; tested 2026-11-12 | Tiles cached on disk |

### 3.2 Calls made to us (inbound)

| Endpoint group | Limit per IP | Response when exceeded |
|---|---|---|
| Read endpoints (plans, events, status) | 60 per minute | `429` with `Retry-After` |
| Start a plan or replay | 5 per minute, and one running job per event | `429`, or `409` if already running |

## 4. Hosting: frontend on Vercel, backend on the team laptop (decided)

```
 Browser ──HTTPS──► Vercel (Next.js server code) ──HTTPS + secret──► tunnel address
                                                                         │ outbound link opened by the laptop
                                                                         ▼
                                                     Laptop: tunnel agent ──► Python API on 127.0.0.1
```

**Rules**

1. **The browser never calls the laptop.** Only Next.js server code does. The backend address and the
   secret live in Vercel environment variables (`BACKEND_URL`, `BACKEND_TOKEN`) and never reach the
   browser. No CORS is needed.
2. **A tunnel, not an open port.** The laptop opens an outbound link to a relay that gives it a public
   HTTPS address. Nothing changes on the router or firewall, and the home IP address is not exposed.
3. **The API listens on 127.0.0.1 only**, so only the tunnel agent can reach it, not other devices on
   the same Wi-Fi.
4. **Every request must carry the shared secret** (`Authorization: Bearer …`), compared in constant
   time; anything else gets `401`. The secret is 32 random bytes, kept in a git-ignored `.env` on the
   laptop and in Vercel's settings, and replaced if it ever leaks.
5. **Long work runs as jobs.** Starting a plan returns a job ID at once; the page polls for progress.
   No request stays open for more than a few seconds, so tunnel and Vercel time limits do not matter.
6. **Runs are bounded.** Only benchmark earthquakes from an allowlist, fixed sizes (10 sites, 4
   sensors, at most 5 layers), one job at a time, and an hourly cap. Whether starting a run also needs
   a team passcode is open (Q12).
7. **When the laptop is off, the site still works.** Calls to the backend time out after 10 s; the site
   then shows saved snapshots (plan files for the benchmark replays, shipped with the frontend) and an
   "offline" banner.
8. **Scheduled work stays on the laptop:** the feed check, hourly monitoring, cache, plans and memory.
   No Vercel scheduled jobs or hosted storage are needed.
9. **One command starts the server:** the API and the tunnel together.

**Tunnel choice**

| Option | Stable address | On this laptop | Notes |
|---|---|---|---|
| **Tailscale Funnel (proposed)** | Yes | Tailscale is installed, running, and the team owns the tailnet | Funnel must be switched on once in the Tailscale admin console. Allowed ports and request limits *(to verify)* |
| Cloudflare Tunnel | Only with a domain on Cloudflare; otherwise the address changes on every start | Not installed | Free |
| ngrok | One fixed address on the free plan *(to verify)* | Not installed | Needs an account |

**Trade-offs accepted**
- Live features work only while the laptop is on, awake and online. It must stay plugged in (sleep
  while plugged in is already disabled on it).
- The tunnel address is public, and with Tailscale the machine's address is listed in public
  certificate logs. The shared secret is what protects the API, so it must stay secret.
- Each request makes one extra hop through the relay.

**Path to regions later:** `BACKEND_URL` becomes a table of region → backend address, and each regional
server replaces the laptop behind the same API contract.

## 5. Frontend test console (Next.js)

Purpose: a working page for **every module**, so each can be tested on its own. Visual design comes later.

| Page | What it exercises |
|---|---|
| Events | Feed check, replay picker, cached data with source URLs |
| Candidates | Site pool on a map: road, slope and spacing filters; backups |
| Scoring | D and DN scores, velocity models, top networks |
| Quantum | Run QAOA; show angles, success probability, measured networks |
| Self-check | Quantum choice against the exact optimum and the baselines |
| Plan | Final map, reasons per site, confidence; download `plan.json` |
| Monitor | Replay timeline, drift checks, re-plans |
| Memory | Stored angles, model weights, track record |
| System | Health, rate-limit counters, external-source status |

Server components fetch from the Python API, so pages arrive rendered. Each page has loading, empty and
error states. Long runs show progress by polling a job-status endpoint.

## 6. Security and engineering rules

These apply to every piece of code in the build.

| Area | Rule for this project |
|---|---|
| Secrets | Environment variables only; never in the frontend, logs or errors; secret scan before every commit |
| Rate limiting | Section 3; `429` with `Retry-After` |
| Input validation | Pydantic on every API input; allowlists for event IDs, regions and enum values |
| Outbound requests (SSRF) | Host allowlist; no user-supplied URLs are ever fetched |
| CORS | Not enabled. The browser talks only to the Vercel site, which calls the backend server-to-server |
| HTTP headers | CSP, HSTS, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` |
| Errors | Generic message to the client, full context in logs; correct status codes |
| XSS | No raw HTML from fetched data; everything escaped |
| AI | None. The app has no AI or LLM features (team decision) |
| Dependencies | Versions pinned; lockfiles committed; audit before release |
| Logging | Structured logs; no secrets |
| Resilience | Timeouts, retries, circuit breakers on every external call |
| Testing | Unit tests on the core; API contract tests; offline test suite under 60 s |
| Backend access | Shared secret on every request; API bound to 127.0.0.1; reachable only through the tunnel (section 4) |
| User accounts | None in the MVP. Needed before any multi-user deployment |

## 7. When this design stops fitting

- More than about 12 candidate sites: the exact score and exhaustive check become too slow (see the spec).
- Real users in several regions: move from one server to the multi-region layout in section 2.
- Private or paid data, or user accounts: authentication and per-user limits become mandatory.
