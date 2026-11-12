# QuakeNet-Q: Frontend Handoff

For the frontend developer. Everything you need is in the `web/` folder of this repo.

## 1. What the project is

After a big earthquake, response teams place a few portable seismometers (earthquake sensors) to
record the aftershocks. QuakeNet-Q decides **which 4 of 10 candidate sites** to use. A quantum
optimisation algorithm, running in a Python backend, makes the choice.

The frontend is a **test console**: one page per backend module, so each can be checked by hand.
It works and is live, but it is plain. **Your job is to make it look and feel good without breaking
how it works.**

- Live site: https://quakenet-q.vercel.app
- Hackathon: Qiskit Fall Fest 2026, domain "Disaster Response"

## 2. Run it on your machine

You need Node.js 24 and npm. You do **not** need Python or the backend.

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

With no `.env.local` file the app runs in **offline mode**. It shows real saved results from
`web/snapshots/` with an "offline: showing saved results" banner. Every page works this way except
starting a new quantum run. This is enough for nearly all design work.

Checks to run before you push:

```bash
npm run lint
npm run typecheck
npm run build
```

## 3. Tech stack

| Item | Version or choice |
|---|---|
| Framework | Next.js 16.4.6, App Router, server-rendered |
| UI | React 19.3, TypeScript |
| Validation | zod 4 |
| Styling | One plain CSS file, `app/globals.css`. No Tailwind, no component library |
| Charts and maps | Hand-written SVG in `components/SiteMap.tsx` |

**Next.js 16 differs from older versions.** Read `web/AGENTS.md` and the guides in
`node_modules/next/dist/docs/` before you change routing, caching or data fetching.

## 4. Pages

| Route | What it shows | Status |
|---|---|---|
| `/events` | List of earthquakes | Working |
| `/candidates` | Map of aftershocks, permanent stations and the 10 candidate sites | Working |
| `/scoring` | How each network scores; top 20 networks; a risk-weight control | Working |
| `/quantum` | Start a quantum run, watch its progress, see the result on the map | Working |
| `/self-check` | Quantum pick compared with exact search and other methods | Working |
| `/plan`, `/monitor`, `/memory` | Placeholders that show "not built yet" | Backend not built |
| `/system` | Health, job list, data sources | Working |

`/` redirects to `/events`.

## 5. Where things live

```
web/
  app/                 pages (one folder per route) and route handlers in app/api/
  app/globals.css      all styles
  components/          Nav, SiteMap (SVG map), QuantumConsole, JobResultView, States, ...
  lib/backend.ts       server-only client for the Python API   ← do not import in client code
  lib/data.ts          loads data, falls back to snapshots when the backend is unreachable
  lib/schemas.ts       zod schemas for every API response (the data shapes)
  lib/passcode.ts      passcode cookie for starting runs
  snapshots/*.json     saved real API responses used in offline mode
```

The data shapes are in `web/lib/schemas.ts`, and the full backend contract is in `docs/API.md`.

## 6. How data flows

```
Browser ──► Next.js server (Vercel) ──► Python API on the team laptop
```

- The **browser never calls the Python API**. Pages are server components that fetch on the server.
- Starting a run goes through our own route handlers: `POST /api/passcode`, then
  `POST /api/events/{id}/jobs`. The Quantum page then polls `GET /api/jobs/{id}` every 2 seconds.
- If the backend does not answer within 10 seconds, pages show the snapshots.

## 7. Rules you must keep

These are security and reliability rules. Please do not change them without asking.

1. **No secrets in the browser.** Never use a `NEXT_PUBLIC_` prefix for `BACKEND_URL`,
   `BACKEND_TOKEN` or `RUN_PASSCODE`. Never import `lib/backend.ts` into a client component.
2. **Never call the backend from the browser.** All backend calls stay in server code.
3. **No `dangerouslySetInnerHTML`.** Render all data as text.
4. **Keep the security headers** in `next.config.ts`.
5. **Keep the passcode check** on starting runs, and the offline fallback.
6. **No third-party scripts, analytics, map tiles or CDNs** without asking. The security policy blocks
   them, and the map is drawn from our own data.
7. **No AI or chatbot features.** This is a team decision.
8. **Do not commit `.env.local` or anything in `.vercel/`.**

## 8. What you are free to change

- All visual design: layout, colours, typography, spacing, icons, dark mode.
- Navigation and page structure, as long as every module stays reachable.
- The map and tables: better legends, hover details, zoom, highlighting of chosen sites.
- Charts for the results. Adding a chart library through npm is fine; loading one from a CDN is not.
- Loading, empty and error states.
- Mobile layout.
- A landing page that explains the project in plain words.

Please keep it accessible: semantic HTML, labelled form controls, visible keyboard focus, and enough
colour contrast (WCAG AA).

## 9. Words you will see in the data

| Term | Meaning |
|---|---|
| Candidate site | A place where a portable sensor could go. Numbered 0 to 9 |
| Network | A choice of 4 candidate sites |
| Permanent station | A sensor that was already there before the earthquake |
| Design events / valid events | Aftershocks used to plan / later aftershocks used to test |
| Risk | How hard or dangerous a site is to reach, from 0 to 1 |
| `lam` (risk weight) | How strongly risk counts against a site. Default 150 |
| Objective | The score of a network. Higher is better |
| Rank | Position of a network among all 210 possible ones. 1 is best |
| Blur (km) | Predicted uncertainty when locating aftershocks. Lower is better |
| Location error (km) | Error measured in a simulated location test. Lower is better |
| QAOA | The quantum optimisation algorithm that picks the network |
| reps (layers) | How many times the circuit repeats its two steps. More is slower and usually better |
| shots | How many times the circuit is measured |
| `p_opt` | Chance that one measurement gives the best network |
| `quantum_agreed` | True when the quantum pick equals the exact best network |

Coordinates are kilometres on a local grid: x points east, y points north.

## 10. Testing against the live backend (optional)

You only need this to test starting a real quantum run. Ask the team for three values and put them
in `web/.env.local` (never commit this file):

```
BACKEND_URL=...      # address of the team's backend
BACKEND_TOKEN=...    # shared secret
RUN_PASSCODE=...     # passcode for starting runs
```

The backend runs on a team member's laptop, so it is only reachable while that laptop is on. If it
is off, the app shows the offline snapshots.

## 11. Deploying

The site is deployed on Vercel as project `quakenet-q`, with root directory `web/`. Deployments are
done by the team; send a pull request and we will deploy it. Preview links can be shared on request.

## 12. Read next

- `web/README.md`: more detail on offline mode, environment variables and security.
- `docs/API.md`: the backend contract (endpoints and JSON shapes).
- `docs/ARCHITECTURE.md`: the whole system. Section 5 lists the pages; section 6 lists the rules.
