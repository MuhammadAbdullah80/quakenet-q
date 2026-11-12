# QuakeNet-Q test console (`web/`)

A plain, server-rendered Next.js app with one page per module of QuakeNet-Q. It consumes the Python
API described in [`docs/API.md`](../docs/API.md) and follows the hosting and security rules in
[`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) (sections 4 to 6).

- Next.js 16 (App Router, TypeScript, Cache Components), React 19, zod. No other runtime dependencies.
- No AI features, no analytics, no external map tiles, fonts or CDNs.

## How it talks to the backend

```
Browser ──► this app (pages and /api routes, server code) ──► Python API  (BACKEND_URL + /api/v1)
```

- **The browser never calls the Python API.** Only server code does, through `lib/backend.ts`
  (marked `server-only`). It adds `Authorization: Bearer <BACKEND_TOKEN>`, forwards the visitor's IP
  as `X-Client-IP`, gives up after 10 s, and turns the API's error contract into typed results.
- Every backend response is checked against the shapes in `lib/schemas.ts` before it is shown. All
  backend data is rendered as text (no raw HTML, and URLs from the backend are not turned into links).
- **Reading needs no passcode. Starting a run, starting the agent and saving settings do.** The browser posts to this app's own route
  handlers:

| Route | Purpose |
|---|---|
| `POST /api/passcode` | Checks the team passcode (constant-time) and sets an `httpOnly`, `Secure`, `SameSite=Strict` cookie for 12 hours. `DELETE` forgets it. |
| `POST /api/events/{id}/jobs` | Starts a QAOA run (`kind: "qaoa"`) or a replay (`kind: "sequence"`, optional `hours` 6 to 168 and `step_hours` 1 to 12). Needs the cookie (otherwise `401`), validates the body with zod against the limits in `docs/API.md`, then calls the backend. |
| `GET /api/jobs/{id}` | Job status of any kind, polled every 2 s by the Quantum and Monitor pages. |
| `PUT /api/settings` | Saves agent settings. Needs the cookie, checks same-origin, validates the body with zod (known keys only, documented ranges), forwards it and returns the saved settings. |
| `POST /api/feed/{usgsId}/trigger` | Starts the agent on a real earthquake from the feed. Needs the cookie; the ID must match `^[a-z0-9]{4,20}# QuakeNet-Q test console (`web/`)

A plain, server-rendered Next.js app with one page per module of QuakeNet-Q. It consumes the Python
API described in [`docs/API.md`](../docs/API.md) and follows the hosting and security rules in
[`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) (sections 4 to 6).

- Next.js 16 (App Router, TypeScript, Cache Components), React 19, zod. No other runtime dependencies.
- No AI features, no analytics, no external map tiles, fonts or CDNs.

## How it talks to the backend

```
Browser ──► this app (pages and /api routes, server code) ──► Python API  (BACKEND_URL + /api/v1)
```

- **The browser never calls the Python API.** Only server code does, through `lib/backend.ts`
  (marked `server-only`). It adds `Authorization: Bearer <BACKEND_TOKEN>`, forwards the visitor's IP
  as `X-Client-IP`, gives up after 10 s, and turns the API's error contract into typed results.
- Every backend response is checked against the shapes in `lib/schemas.ts` before it is shown. All
  backend data is rendered as text (no raw HTML, and URLs from the backend are not turned into links).
- **Reading needs no passcode. Starting a run, starting the agent and saving settings do.** The browser posts to this app's own route
  handlers:

| Route | Purpose |
|---|---|
| `POST /api/passcode` | Checks the team passcode (constant-time) and sets an `httpOnly`, `Secure`, `SameSite=Strict` cookie for 12 hours. `DELETE` forgets it. |
. |

## Pages

| Page | Backend calls |
|---|---|
| `/` | None. The scroll story, built from `data/story.json`, `data/world-quakes.json` and `public/relief/` |
| `/guide` | None. How to use the site and what every number means |
| `/events` | `GET /events` (shows kind and location when the backend sends them) |
| `/feed` | `GET /feed`; start the agent on a qualifying earthquake |
| `/candidates` | `GET /events/{id}/instance` (SVG map in km, plus tables) |
| `/scoring` | `GET /events/{id}/scoring?lam=` |
| `/quantum` | `GET /jobs`, `GET /jobs/{id}`; start a run and poll it |
| `/self-check` | `GET /events/{id}/baselines?lam=` next to the latest quantum result |
| `/plan` | `GET /events/{id}/plan` (map from `GET /events/{id}/sequence`) |
| `/monitor` | `GET /events/{id}/sequence`, `GET /settings`, `GET /jobs`; start a replay, poll it, step through it hour by hour |
| `/memory` | `GET /memory` |
| `/noise` | `GET /noise` (a simulation, not a hardware run) |
| `/settings` | `GET /settings`; save with the passcode |
| `/system` | `GET /health`, `GET /system`, `GET /jobs` |

Every page shows "Not built yet" when the backend answers `501 NOT_BUILT`; Plan and Monitor say
that no agent run exists yet on `404 NOT_FOUND`.

The earthquake is chosen with `?event=<id>`; without it the first available one is used.

## Environment variables

Copy `.env.example` to `.env.local` (git-ignored) and fill it in. All three are **server-side
secrets: never give them a `NEXT_PUBLIC_` prefix.**

| Variable | Meaning |
|---|---|
| `BACKEND_URL` | Origin of the Python API, without a path (the app appends `/api/v1`). Must be `https`, except `http://localhost` or `http://127.0.0.1` for a backend on the same machine. |
| `BACKEND_TOKEN` | The shared secret the Python API expects as a bearer token. |
| `RUN_PASSCODE` | Team passcode needed to start a run. If empty or missing, starting runs is disabled. Use a long one: it is the only thing between a visitor and the laptop's CPU. |

If `BACKEND_URL` or `BACKEND_TOKEN` is missing or invalid, the app runs in offline mode.

## Run locally

Needs Node 20.9 or newer (developed on Node 24).

```bash
cd web
npm install
cp .env.example .env.local      # then edit it; e.g. BACKEND_URL=http://127.0.0.1:8000
npm run dev                     # http://localhost:3000
```

Other commands:

```bash
npm run build       # production build
npm run start       # serve the production build
npm run lint        # eslint
npm run typecheck   # generate route types, then tsc --noEmit
```

To see offline mode, start the app with no `.env.local` (or with the backend stopped).

The passcode cookie is `Secure`. Chrome, Edge and Firefox accept it on `http://localhost`; Safari
does not, so use another browser (or HTTPS) to test starting runs locally.

## Offline mode

When the backend is not configured, cannot be reached, does not answer within 10 s, or the tunnel
answers 502/503/504 without the API's error body:

- pages render from the saved API responses in `snapshots/` (`events`, `instance`, `scoring`,
  `baselines`, one finished `job`, and for version 2 `settings`, `feed`, `sequence`, `plan`,
  `memory`, `noise`);
- a banner says **"Offline: showing saved results"**;
- starting runs, starting the agent, saving settings and the `lam` control are disabled;
- `/system` has no snapshot and says so.

After a failed connection the app does not retry for 15 s, so an offline page loads at once instead
of waiting 10 s for every call.

### Placeholder snapshots

Files marked `"mock": true` are placeholders (today: the six version 2 files, `settings`, `feed`,
`sequence`, `plan`, `memory` and `noise`). They were built from the examples in
`docs/API.md` plus invented filler, and **are not real results**; the banner says so whenever one is
shown. Replace them with real responses from a running backend:

```bash
cd web
node --env-file=.env.local scripts/capture-snapshots.mjs            # first available event, lam 150
node --env-file=.env.local scripts/capture-snapshots.mjs ridgecrest2019 150
```

The script only sends `GET` requests (`/events`, `/events/{id}/instance`, `/scoring`, `/baselines`,
`/jobs`, `/jobs/{id}`, and the version 2 endpoints `/settings`, `/feed`, `/memory`, `/noise`,
`/events/{id}/sequence`, `/events/{id}/plan`) and overwrites the files without the mock marker. A
version 2 endpoint that answers 404 or 501 is skipped and its placeholder is kept. It needs one finished
QAOA job on the backend for `job.json`; if there is none it warns and leaves that file alone.
Snapshots are compiled into the build, so rebuild (or redeploy) after capturing.

## Security

- Headers on every response, set in `next.config.ts`: Content-Security-Policy, HSTS,
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, plus
  Permissions-Policy and Cross-Origin-Opener-Policy.
- The CSP allows same-origin resources only. It has to allow inline scripts and styles
  (`'unsafe-inline'`), because pages are partially prerendered and a per-request nonce cannot be
  attached to a prerendered shell. No `dangerouslySetInnerHTML` is used anywhere.
- State-changing routes refuse cross-site requests (Origin check), on top of the `SameSite=Strict`
  cookie. Passcode attempts are limited to 10 per 5 minutes per address (per server instance).
- Event and job IDs are checked against a strict pattern, and event IDs against the backend's own
  list, before they are put in a backend path. No user-supplied URL is ever fetched.
- Secrets are read from the environment only and never logged. Server logs are JSON lines.

## Deploying on Vercel (not done yet)

1. Import the repository in Vercel and set **Root Directory** to `web/`. The framework preset
   (Next.js) and the default build command (`next build`) need no change.
2. Add `BACKEND_URL` (the tunnel's HTTPS address), `BACKEND_TOKEN` and `RUN_PASSCODE` as
   environment variables for Production (and Preview if wanted). Mark them sensitive.
3. Capture real snapshots and commit them before deploying, so the offline view is real.
4. Deploy. With the laptop off, the site shows the snapshots and the offline banner.

Nothing else is needed on Vercel: no scheduled jobs, storage or edge configuration.
