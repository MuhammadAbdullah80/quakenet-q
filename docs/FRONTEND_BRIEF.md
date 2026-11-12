# QuakeNet-Q: Frontend Redesign Brief

For the frontend developer. Read `docs/FRONTEND_HANDOFF.md` first: it covers setup, the current
pages, and the rules that must not be broken. This brief covers what to build next.

**Status on 2026-11-12:** the console restyle (section 6) is done on branch `frontend-improved`.
The landing page (section 4), guide page (section 5) and agent pages (section 7) are not started.
The live site at https://quakenet-q.vercel.app still shows the plain console until the branch is merged.
One change from section 2: `--lime-text` is `#3d6e0c`, because `#4f8a12` fails WCAG AA on mist
(decision 26).

## 1. What the team wants

1. A **landing page** that tells the project's story as one long pinned scroll, with 2D canvas and
   3D animation, using a **real Earth map**.
2. The **console pages** restyled in the same look, including the new agent pages (section 7).
3. A **guide page** that explains how to use the site and what every map, chart and number means.

Constraints from the team:
- Simple colours and a simple layout. Do not overload it.
- It must not look machine-made or templated.
- No em dashes anywhere in the copy. No small "eyebrow" labels above headings unless they carry
  real information, such as a time or a coordinate.
- Proper typography: a clear type scale, tabular numerals for data, correct units.
- Purposeful animation only.

The team has a reference prompt for a scroll-story site ("floating island fly-in") and will send it
to you separately. Take its **structure and motion**, not its subject or its images: do not use its
image or video files. Section 4 maps each of its beats to our project.

## 2. Design direction (proposal, open to your judgement)

**Subject:** seismology. Useful source material: seismogram traces, station codes such as CI.CLC,
shaded relief maps, coordinates, UTC times.

**Palette:** pale mist, one dark ink, one accent.

| Token | Value | Use |
|---|---|---|
| `--ink` | `#10291a` | Text, the globe, dark surfaces |
| `--ink2` | `#2c4434` | Secondary text |
| `--mist` | `#e7ebe8` | Page background |
| `--paper` | `#f6f7f4` | Panels |
| `--lime` | `#c6f35c` | Sensors and our chosen sites only |
| `--lime-text` | `#4f8a12` | The accent as text on light backgrounds |

Keep one meaning per colour: **lime means a sensor or a chosen site**. Earthquakes are pale dots on
the dark globe and ink dots on the pale terrain.

**Type:** IBM Plex Sans Condensed for headings, IBM Plex Sans for text, IBM Plex Mono for data and
labels. Qiskit is an IBM project and the team's design document already uses Plex, so the family ties
the pieces together. Load fonts with `next/font/google`, which self-hosts them. The security policy
blocks font CDNs.

**Signature element:** a real globe that the camera flies into, landing on a slab of real terrain
that floats in mist, with sensor masts standing on it.

## 3. Assets and data already prepared

All real data. Rebuild them with `python scripts/build_web_assets.py` (needs Python; you do not
have to run it).

| File | What it is |
|---|---|
| `web/public/relief/ridgecrest-2000.webp` (233 KB) and `ridgecrest-900.webp` (88 KB) | Shaded relief of the study area, drawn from real elevation data in the page palette. Square, north up, covering x and y from -64 to +64 km of the local grid |
| `web/data/world-quakes.json` | 1,224 real earthquakes of magnitude 6.5 and above since 2000, as `[lon, lat, magnitude]` |
| `web/data/story.json` | The Ridgecrest case and the headline numbers (see below) |

`story.json` fields:
- `event`: name, magnitude, `lat`, `lon`, `depth_km`, `time_ms` of the mainshock.
- `grid`: `lat0`, `lon0`, `km_per_deg`, `extent_km`. To convert local km to latitude and longitude:
  `lat = lat0 + y / km_per_deg` and `lon = lon0 + x / (km_per_deg * cos(lat0))`.
- `early` (550) and `later` (217): aftershocks as `[x_km, y_km, depth_km, magnitude, hours_after_mainshock]`.
  `early` is the first 12 hours, used for planning. `later` is used only for testing.
- `stations` (14): `name`, `x`, `y`. `candidates` (10): `id`, `x`, `y`, `risk`, `nearest_km`.
- `pick`: the four sites the quantum circuit chose, `[1, 3, 4, 7]`. `expert`: a field rule's choice.
- `numbers`: counts, success rates per circuit layer, and location errors in km
  (`error_none_km` 3.00, `error_expert_km` 2.63, `error_pick_km` 2.31).
- `sorted_errors`: the location error of all 210 possible networks, best first. `pick_position` and
  `expert_position` are indexes into it.

Libraries already added to `web/package.json` for the globe: `d3-geo`, `topojson-client`,
`world-atlas` (public-domain Natural Earth land outlines). Import `world-atlas/land-110m.json`.

**Credits to show on the site:** earthquake data from the U.S. Geological Survey; station data from
EarthScope; land outlines from Natural Earth; elevation from Mapzen Terrain Tiles on AWS, with data
courtesy of the U.S. Geological Survey.

## 4. Landing page: the scroll story

One section about 640vh tall with a sticky 100vh stage, then a white panel that slides up.

| Beat | Reference prompt | Our version |
|---|---|---|
| 1. Hero | Floating island, one-line headline | A dark globe on pale mist, drawn on a 2D canvas, with the 1,224 real earthquakes as pale dots and a lime ring on Ridgecrest. Headline: "Where do the sensors go?" The top of the globe just covers the bottom of the letters |
| 2. Fly-in | Video scrub into the island | Scroll rotates the globe to California and zooms in. A sentence resolves out of blur in white over the dark globe. Then a mist whiteout hides the switch to the terrain |
| 3. Landscape | Paragraph writes in, hotspots pop | The terrain image as a tilted 3D plane (CSS `perspective` and `rotateX`). The 550 aftershocks appear in the order they happened, with a clock. Stations and the ten candidate sites rise as masts. A paragraph writes in word by word |
| 4. Station | Glass card, count-up, feature list | The four chosen sites turn lime. A glass card counts the location error down from 3.00 km to 2.31 km, with a sparkline of `sorted_errors`. A five-row list of the pipeline steps, each linking to its console page |
| 5. Panel | Three tilt cards, four count-up stats | "Run it yourself": three cards linking to Candidates, Quantum and Self-check, and four stats |

**Copy to start from** (edit freely; keep it plain and true):
- Hero caption: "Real aftershock data from the U.S. Geological Survey. Quantum circuit simulated in
  Qiskit. Every answer checked against all 210 options."
- Globe label at Ridgecrest: "M 7.1 Ridgecrest", "35.770° N 117.599° W", "2019-07-06 03:19 UTC".
- Fly-in sentence: "Where the sensors go decides how sharply aftershocks can be located."
- Landscape paragraph: "Twelve hours after the magnitude 7.1 mainshock near Ridgecrest, 550
  aftershocks had been recorded. The 14 permanent stations sat too far apart to locate them sharply.
  A response team had 4 portable sensors and 10 places to put them."
- Station heading: "The circuit chose sites 1, 3, 4 and 7. An exact search of all 210 options agrees."
- Card: "Location error on later aftershocks", "217 aftershocks the planner never saw".
- Pipeline rows: 01 Real aftershocks and stations, 02 Ten candidate sites, 03 A score for all 210
  networks, 04 A quantum circuit picks four, 05 Exact search checks the pick.
- Stats: 550 aftershocks in the first 12 hours; 210 possible networks, all checked; 15 of 15 quantum
  runs found the best network; 2.31 km mean location error with the chosen sites.
- Footer line: "Proof of concept. The quantum circuit runs on a simulator and claims no speedup."

**Technique notes**
- **Globe:** `geoOrthographic().clipAngle(90)` with `geoPath(projection, ctx)`. Draw the sphere, a
  faint graticule, the land, then the earthquake dots. Test visibility with `geoDistance` before
  drawing a dot. Zoom exponentially with scroll so the fall feels steady.
- **Terrain plane:** a square element holding the relief image, inside a parent with `perspective`.
  Transform: `translate3d(0, ty, 0) rotateX(θ) scale(s)`. Fade its edges with a radial `mask-image`
  so it reads as a slab floating in mist.
- **Markers on the tilted plane:** draw them on a flat canvas above the plane and project each point
  yourself, so labels stay upright. For a point `(u, v)` px from the plane centre:
  `Y = v·s`, `y' = Y·cosθ + ty`, `z' = Y·sinθ`, `f = P / (P − z')`,
  `screen = (cx + u·s·f, cy + y'·f)`. Local km map to px by `u = x·k`, `v = −y·k`.
- **One `requestAnimationFrame` loop** drives everything from a smoothed scroll progress. Do not put
  per-frame values in React state; write to refs and styles.
- Pause the loop when the story is off screen.

## 5. Guide page (`/guide`)

Plain language for someone new to both earthquakes and quantum computing. Suggested sections:

1. What this site does, in three sentences.
2. Live and offline: what the "showing saved results" banner means; what the passcode is for.
3. A walk through the console, page by page: what you see and how to read it.
4. How to read the map: each symbol, the risk colours, the rings around chosen sites.
5. How to read each table and chart. For every number give its meaning, its unit, and whether
   higher or lower is better. The glossary in `FRONTEND_HANDOFF.md` section 9 is a starting point.
6. Starting a quantum run: what layers, seed, measurements and risk weight do, and how long a run
   takes (about 30 to 70 seconds).
7. What the result means: chance per measurement against a random pick, valid networks, the final
   pick against the exact best.
8. Limits: simulator only, no speedup claimed, simplified physics, one fully tested earthquake.

## 6. Console restyle

- Apply the palette and type to the existing pages. Keep every control and state working.
- Put the relief image under the SVG map in `components/SiteMap.tsx` for Ridgecrest. The map already
  uses local km, so the image goes at x = -64, y = -64 (after the y flip), 128 km wide.
- Replace the heavy table grid with horizontal rules. Use mono, uppercase, small table headers.
- Add simple charts where they help: location error by method on Self-check, and times measured
  per network on Quantum. Build them in SVG or with an npm library; no CDN.
- Remove the em dashes that exist in the current copy.

## 7. New pages for the agent (backend in progress)

The backend team is building the agent now. The data shapes are fixed in `docs/API.md`, section
"Version 2: the agent". Until the endpoints exist they return an error, so build against the JSON
examples in that document and add snapshot files for offline mode.

| Page | Endpoint | What it should let a person do |
|---|---|---|
| Settings | `GET` and `PUT /settings` | Edit the trigger magnitude and the other settings, within the `limits` the backend returns. Saving needs the team passcode, like starting a run |
| Live feed | `GET /feed`, `POST /feed/{usgs_id}/trigger` | See recent real earthquakes, which ones reach the trigger magnitude, and what the agent did. Start the agent on one by hand |
| Plan | `GET /events/{id}/plan` | See the current site plan: each site with its reason, risk and backup spots, plus confidence |
| Monitor | `GET /events/{id}/sequence`, `POST /events/{id}/jobs` with `kind: "sequence"` | Start a replay of a past earthquake and scrub through it hour by hour: aftershocks arriving, drift checks, re-plans and sensor moves on the map |
| Memory | `GET /memory` | See what the agent has learned: stored circuit settings, model weights, how good its predictions were |
| Noise study | `GET /noise` | A chart of success chance against gate error. Label it clearly as a simulation, not a hardware run |

New `PUT` and `POST` calls must go through our own route handlers with the passcode check, exactly
like `app/api/events/[eventId]/jobs/route.ts`.

## 8. Quality bar

- Works at 390 px wide and up. Visible keyboard focus. `prefers-reduced-motion` respected.
- Text contrast meets WCAG AA. Canvases are `aria-hidden`; the story text is real DOM text.
- `npm run lint`, `npm run typecheck` and `npm run build` pass.
- The landing page stays smooth on a mid-range laptop. Cap canvas pixel ratio at 1.5.
- No secrets in the browser, no third-party scripts, fonts, tiles or CDNs.

## 9. How to deliver

Work on a branch and open a pull request. The team reviews, then deploys to Vercel. Ask for a
preview link if you want to check a build on a phone.
